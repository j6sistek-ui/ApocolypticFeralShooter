"""MakeHeadhunterBloodTextures.py - the two blood masks for the Headhunter tube (2026-11-01). Plain Python + numpy + PIL.

  py M:/UnrealProjects/AFS/Scripts/MakeHeadhunterBloodTextures.py

Out: M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Headhunter/Blood/
  T_HH_GlassBloodStatic.png  2048 x 512, wraps round SM_Headhunter_GlassBlood (u round the tube, u 0.25 = front,
                             0.75 = back; row 0 = top of the shell under the cap, last row = under the tube ring).
                             R = blood thickness (0 none .. 1 thick run core), G = age (0 fresh red .. 1 older, darker),
                             B = streak direction hint (unused for now). The layout follows the concept close-up:
                             a heavy smeared band just above the pool, runs of every width (a few long ones from the
                             very top, most starting low), spatter dots denser low, wiped smears; the front centre
                             (behind the skull and crosshair) and the back centre are kept lighter so the skull reads.
  T_HH_Spatter.png           512 x 512, one headshot splat (exit spatter) centred: R = thickness. Mapped by the glass
                             material onto SpatterSizeCm around the hit point, revealed and run downwards by the actor.
Deterministic (fixed seeds): a re-run gives the same files.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = 'M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Headhunter/Blood/'
os.makedirs(OUT, exist_ok=True)
CIRC_CM, HEIGHT_CM = 210.0, 43.7      # shell circumference and height (headhunter_clean.json)
POOL_FROM_TOP_CM = 43.7 - (117.0 - 108.8)   # the pool surface, measured down from the shell top
SS = 2                                # supersampling while drawing
PXCM = 10 * SS                        # canvas px per cm


def value_noise(shape, cells, rng, octaves=3):
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cy, cx = max(2, int(cells[0] * 2 ** o)), max(2, int(cells[1] * 2 ** o))
        g = rng.random((cy + 1, cx + 1)).astype(np.float32)
        g[:, -1] = g[:, 0]                       # wraps horizontally
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(img, np.float32) / 255
        tot += amp
        amp *= 0.5
    return out / tot


def draw_run(d, x, y0, length, w, rng, wrapw):
    """A run: a wobbly vertical stroke tapering from width w at the bulb (bottom) to ~0.4 w at the top, a bulb at
    the end, and sometimes a thinner side trail. Drawn in canvas px; x wraps."""
    steps = max(4, int(length / 2))
    pts = []
    ph = rng.random() * 6.28
    for i in range(steps + 1):
        t = i / steps
        yy = y0 + t * length
        xx = x + math.sin(ph + yy * 0.035) * w * 0.6 + rng.normal(0, w * 0.06)
        ww = w * (0.35 + 0.65 * t ** 0.7)
        pts.append((xx, yy, ww))
    for off in (0, -wrapw, wrapw):
        for (xa, ya, wa), (xb, yb, wb) in zip(pts, pts[1:]):
            d.polygon([(xa - wa + off, ya), (xa + wa + off, ya), (xb + wb + off, yb), (xb - wb + off, yb)], fill=255)
        xe, ye, we = pts[-1]
        r = we * rng.uniform(1.15, 1.55)
        d.ellipse([xe - r + off, ye - r * 0.9, xe + r + off, ye + r * 1.25], fill=255)


def glass_static():
    rng = np.random.default_rng(20261101)
    W, H = int(CIRC_CM * PXCM), int(HEIGHT_CM * PXCM)
    img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(img)
    pool_y = POOL_FROM_TOP_CM * PXCM

    def keep(u, ycm):
        """Lighter zones: the front centre (behind the skull / crosshair) and the back centre (headshot target)."""
        if ycm > POOL_FROM_TOP_CM - 4.0:
            return 1.0
        du_f = abs(((u - 0.25 + 0.5) % 1.0) - 0.5)
        du_b = abs(((u - 0.75 + 0.5) % 1.0) - 0.5)
        if du_f < 0.11:
            return 0.06 + 0.94 * (du_f / 0.11) ** 2
        if du_b < 0.07:
            return 0.35
        return 0.75
        return 1.0
    # 1. long runs from the very top (a few, like the concept's top-right run)
    n_long = 0
    while n_long < 12:
        u = rng.random()
        if rng.random() > keep(u, 10):
            continue
        n_long += 1
        length = rng.uniform(14, 34) * PXCM
        draw_run(d, u * W, rng.uniform(-0.5, 1.2) * PXCM, length, rng.uniform(0.18, 0.55) * PXCM / 2, rng, W)
    # 2. runs starting lower (most of them), denser low
    n = 0
    while n < 200:
        u = rng.random()
        ystart = POOL_FROM_TOP_CM - 1.5 - (rng.random() ** 2.4) * (POOL_FROM_TOP_CM - 6)
        if rng.random() > keep(u, ystart + 3):
            continue
        n += 1
        length = min(rng.uniform(1.5, 13.0) * (0.5 + ystart / POOL_FROM_TOP_CM), POOL_FROM_TOP_CM - ystart + 1.5)
        width = rng.uniform(0.15, 0.32) if rng.random() < 0.65 else rng.uniform(0.35, 0.85)
        draw_run(d, u * W, ystart * PXCM, length * PXCM, width * PXCM / 2, rng, W)
    # 3. spatter dots, clustered, denser low
    centres = [(rng.random(), POOL_FROM_TOP_CM - (rng.random() ** 1.5) * 26) for _ in range(26)]
    dots = 0
    while dots < 2000:
        if rng.random() < 0.65:
            cu, cy = centres[rng.integers(len(centres))]
            u = (cu + rng.normal(0, 0.025)) % 1.0
            ycm = cy + rng.normal(0, 3.0)
        else:
            u = rng.random()
            ycm = POOL_FROM_TOP_CM - (rng.random() ** 2.2) * POOL_FROM_TOP_CM
        if ycm < 0 or rng.random() > keep(u, ycm):
            continue
        dots += 1
        r = (0.03 + rng.random() ** 3 * 0.26) * PXCM
        x, y = u * W, ycm * PXCM
        e = rng.uniform(0.8, 1.5)
        for off in (0, -W, W):
            d.ellipse([x - r + off, y - r * e, x + r + off, y + r * e * 1.1], fill=255)
    arr = np.asarray(img, np.float32) / 255
    # 4. heavy smeared band just above the pool, ragged top edge, plus wiped smears lower down
    yy = (np.arange(H, dtype=np.float32) / PXCM)[:, None] * np.ones((1, W), np.float32)
    nz = value_noise((H, W), (6, 60), rng, 4)
    nz2 = value_noise((H, W), (14, 140), rng, 3)
    band_top = POOL_FROM_TOP_CM - (0.6 + 2.8 * nz2 ** 1.6)  # ragged, ~0.6 - 3.4 cm above the surface
    band = np.clip((yy - band_top) / 1.2, 0, 1) * (0.55 + 0.45 * nz)
    band *= (nz2 > 0.32 - 0.25 * np.clip((yy - band_top) / 4.0, 0, 1))
    smear = np.clip((nz - 0.62) * 4.0, 0, 1) * (yy > POOL_FROM_TOP_CM - 16) * (yy < POOL_FROM_TOP_CM - 3)
    arr = np.maximum(arr, np.maximum(band, smear * 0.55))
    a8 = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.3 * SS))
    thick = Image.fromarray(np.clip(np.asarray(a8, np.float32) * 1.25, 0, 255).astype(np.uint8))
    thick = thick.resize((2048, 512), Image.LANCZOS)
    age = value_noise((512, 2048), (5, 40), np.random.default_rng(7), 3)
    age = np.clip((age - 0.3) * 1.6, 0, 1)
    rgb = np.dstack([np.asarray(thick), (age * 255).astype(np.uint8), np.zeros((512, 2048), np.uint8)])
    Image.fromarray(rgb, 'RGB').save(OUT + 'T_HH_GlassBloodStatic.png')
    return float((np.asarray(thick) > 90).mean())


def spatter():
    """Exit spatter: irregular central blob, radial spikes ending in droplets, satellite droplets, a few drips."""
    rng = np.random.default_rng(1101)
    S = 1024
    img = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(img)
    c = S / 2
    # central blob: noisy-radius polygon
    pts = []
    base = S * 0.13
    ph = rng.random(5) * 6.28
    for i in range(96):
        a = 2 * math.pi * i / 96
        r = base * (1 + 0.22 * math.sin(3 * a + ph[0]) + 0.15 * math.sin(7 * a + ph[1]) + 0.1 * math.sin(13 * a + ph[2]))
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=255)
    # spikes
    for i in range(16):
        a = rng.uniform(0, 2 * math.pi)
        L = S * rng.uniform(0.16, 0.34)
        w0 = S * rng.uniform(0.018, 0.04)
        p0 = (c + base * 0.7 * math.cos(a), c + base * 0.7 * math.sin(a))
        p1 = (c + L * math.cos(a), c + L * math.sin(a))
        n = (-math.sin(a), math.cos(a))
        d.polygon([(p0[0] + n[0] * w0, p0[1] + n[1] * w0), (p1[0] + n[0] * w0 * 0.15, p1[1] + n[1] * w0 * 0.15),
                   (p1[0] - n[0] * w0 * 0.15, p1[1] - n[1] * w0 * 0.15), (p0[0] - n[0] * w0, p0[1] - n[1] * w0)],
                  fill=255)
        r = w0 * rng.uniform(0.6, 1.2)
        q = (c + (L + r * 1.5) * math.cos(a), c + (L + r * 1.5) * math.sin(a))
        d.ellipse([q[0] - r, q[1] - r, q[0] + r, q[1] + r], fill=255)
    # satellites: smaller further out, elongated radially
    for i in range(650):
        a = rng.uniform(0, 2 * math.pi)
        dist = S * (0.1 + rng.random() ** 1.6 * 0.38)
        r = S * 0.02 * (1.15 - dist / (S * 0.5)) * rng.uniform(0.25, 1.0)
        x, y = c + dist * math.cos(a), c + dist * math.sin(a)
        el = 1 + dist / S * 2.5
        ex, ey = abs(math.cos(a)) * el + abs(math.sin(a)), abs(math.sin(a)) * el + abs(math.cos(a))
        d.ellipse([x - r * ex, y - r * ey, x + r * ex, y + r * ey], fill=255)
    # drips from the lower half of the blob (they run in the material too; these are the first few mm)
    for i in range(7):
        x = c + rng.uniform(-base * 0.9, base * 0.9)
        w = S * rng.uniform(0.006, 0.016)
        y0 = c + base * 0.5
        L = S * rng.uniform(0.05, 0.16)
        d.polygon([(x - w, y0), (x + w, y0), (x + w * 0.8, y0 + L), (x - w * 0.8, y0 + L)], fill=255)
        d.ellipse([x - w * 1.4, y0 + L - w, x + w * 1.4, y0 + L + w * 1.8], fill=255)
    img = img.filter(ImageFilter.GaussianBlur(2.2)).resize((512, 512), Image.LANCZOS)
    a = np.clip(np.asarray(img, np.float32) * 1.3, 0, 255).astype(np.uint8)
    Image.fromarray(np.dstack([a, a, np.zeros_like(a)]), 'RGB').save(OUT + 'T_HH_Spatter.png')


cov = glass_static()
spatter()
print('HH_TEXTURES done static_coverage=%.3f' % cov)
