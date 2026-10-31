"""MakePowerUpStyleTextures.py - draw the procedural masks the power-up style looks need (plain Python, PIL + numpy).

Writes grayscale/RGB PNG masks to M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleTextures/ (Scripts/AuthorPowerUpStyles.py
imports them into /Game/HoverPrototype/PowerUps/Styles/Shared/Textures). All white-on-black masks; the materials tint them.
  T_PU_SprayCircle_Cross / _Trefoil  look 12: a spray-painted ring + icon on asphalt (worn, overspray, scavenger tick marks)
  T_PU_Hazard_Cross / _Trefoil       look 9: a stencilled hazard-diamond placard (R = lines, G = interior fill)
  T_PU_Noise                         tileable fbm noise (smoke, veins, dropouts, grime)
  T_PU_White                         plain white default for the mask slots
Usage: python Scripts/MakePowerUpStyleTextures.py
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleTextures'
N = 1024
rng = np.random.default_rng(31)


def fbm_tileable(size, octaves=6, base=4, seed=0):
    r = np.random.default_rng(seed)
    acc = np.zeros((size, size), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        cells = base * (2 ** o)
        g = r.random((cells, cells)).astype(np.float32)
        # bilinear, wrapping (tileable)
        xs = np.arange(size) * cells / size
        x0 = np.floor(xs).astype(int)
        fx = xs - x0
        fx = fx * fx * (3 - 2 * fx)
        x1 = (x0 + 1) % cells
        x0 = x0 % cells
        a = g[x0][:, x0]
        b = g[x0][:, x1]
        c = g[x1][:, x0]
        d = g[x1][:, x1]
        fxr = fx[None, :]
        fyr = fx[:, None]
        v = (a * (1 - fxr) + b * fxr) * (1 - fyr) + (c * (1 - fxr) + d * fxr) * fyr
        acc += v * amp
        tot += amp
        amp *= 0.5
    acc /= tot
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    return acc


def spray_stroke(draw_arr, pts, width, density=1.0, seed=1):
    """Accumulate a spray stroke along a polyline into a float array: a soft core plus random overspray dots."""
    r = np.random.default_rng(seed)
    img = Image.new('L', (N, N), 0)
    d = ImageDraw.Draw(img)
    d.line([tuple(p) for p in pts], fill=255, width=int(width), joint='curve')
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - width / 2, p[1] - width / 2, p[0] + width / 2, p[1] + width / 2], fill=255)
    core = np.asarray(img.filter(ImageFilter.GaussianBlur(width * 0.12)), np.float32) / 255.0
    # overspray: dots scattered around the path with a gaussian falloff
    halo = np.zeros((N, N), np.float32)
    pts = np.asarray(pts, np.float32)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = float(seg.sum()) if len(seg) else 1.0
    ndots = int(total * 6 * density)
    if len(seg):
        cum = np.concatenate([[0], np.cumsum(seg)])
        t = r.random(ndots) * total
        idx = np.clip(np.searchsorted(cum, t) - 1, 0, len(seg) - 1)
        f = (t - cum[idx]) / np.maximum(seg[idx], 1e-6)
        base = pts[idx] + (pts[idx + 1] - pts[idx]) * f[:, None]
        off = r.normal(0, width * 0.75, (ndots, 2))
        p = (base + off).astype(int)
        ok = (p[:, 0] >= 0) & (p[:, 0] < N) & (p[:, 1] >= 0) & (p[:, 1] < N)
        p = p[ok]
        np.add.at(halo, (p[:, 1], p[:, 0]), r.random(len(p)).astype(np.float32) * 0.9)
    halo = np.asarray(Image.fromarray(np.clip(halo * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255.0
    draw_arr += core + halo * 0.8
    return draw_arr


def circle_pts(cx, cy, r, a0, a1, n=240, wobble=0.0, seed=2):
    rr = np.random.default_rng(seed)
    ph = rr.random(3) * 6.28
    out = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        w = 1 + wobble * (math.sin(a * 3 + ph[0]) * 0.5 + math.sin(a * 7 + ph[1]) * 0.3 + math.sin(a * 13 + ph[2]) * 0.2)
        out.append((cx + math.cos(a) * r * w, cy + math.sin(a) * r * w))
    return out


def cross_strokes(cx, cy, arm, half):
    # two overlapping fat strokes = the medical cross, sprayed by hand (slightly off-square)
    return [[(cx - arm, cy + 6), (cx + arm, cy - 4)], [(cx + 5, cy - arm), (cx - 4, cy + arm)]], half * 2


def trefoil_mask(cx, cy, r_in, r_out, r_hub, stencil=True, width=None):
    img = Image.new('L', (N, N), 0)
    d = ImageDraw.Draw(img)
    for k in range(3):
        a0 = -90 + k * 120 - 30
        d.pieslice([cx - r_out, cy - r_out, cx + r_out, cy + r_out], a0, a0 + 60, fill=255)
    d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=0)
    d.ellipse([cx - r_hub, cy - r_hub, cx + r_hub, cy + r_hub], fill=255)
    return np.asarray(img, np.float32) / 255.0


def wear(arr, amount, seed):
    n = fbm_tileable(N, 6, 6, seed)
    mask = np.clip((n - amount) / 0.18, 0, 1)
    speck = (np.random.default_rng(seed + 5).random((N, N)) > 0.06).astype(np.float32)
    return arr * (0.35 + 0.65 * mask) * speck


def save(arr, name, mode='L'):
    os.makedirs(OUT, exist_ok=True)
    if mode == 'L':
        im = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), 'L').convert('RGB')
    else:
        im = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), 'RGB')
    im.save(os.path.join(OUT, name + '.png'))
    print('wrote', name)


def spray_circle(icon):
    a = np.zeros((N, N), np.float32)
    c = N / 2
    # the ring: one hand-sprayed loop that overshoots its start a little
    a = spray_stroke(a, circle_pts(c, c, 392, -1.9, -1.9 + 2 * math.pi + 0.45, wobble=0.025, seed=3), 34, 1.1, seed=4)
    # scavenger tick marks outside the ring (N/E/S/W), like a search-and-rescue mark
    for k in range(4):
        ang = k * math.pi / 2 + 0.2
        p0 = (c + math.cos(ang) * 432, c + math.sin(ang) * 432)
        p1 = (c + math.cos(ang) * 492, c + math.sin(ang) * 492)
        a = spray_stroke(a, [p0, p1], 22, 0.9, seed=10 + k)
    if icon == 'cross':
        strokes, w = cross_strokes(c, c, 215, 62)
        for i, s in enumerate(strokes):
            a = spray_stroke(a, s, w, 1.2, seed=20 + i)
    else:
        tre = trefoil_mask(c, c, 92, 262, 58)
        tre = np.asarray(Image.fromarray((tre * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)), np.float32) / 255.0
        a += tre
        # overspray around the stencil edges
        edge = np.asarray(Image.fromarray((tre * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(26)), np.float32) / 255.0
        a += np.clip(edge - tre, 0, 1) * (np.random.default_rng(7).random((N, N)) > 0.55) * 0.9
    a = np.clip(a, 0, 1.2)
    a = wear(a, 0.28, 41 if icon == 'cross' else 42)
    return np.clip(a, 0, 1)


def hazard(icon):
    lines = Image.new('L', (N, N), 0)
    fill = Image.new('L', (N, N), 0)
    dl = ImageDraw.Draw(lines)
    df = ImageDraw.Draw(fill)
    c = N / 2
    R1, R2 = 490, 430  # outer / inner diamond half-diagonals
    dia = lambda r: [(c, c - r), (c + r, c), (c, c + r), (c - r, c)]
    dl.polygon(dia(R1), fill=255)
    dl.polygon(dia(R2), fill=0)
    df.polygon(dia(R2 - 6), fill=255)
    # stencil bridges in the border (the gaps a spray stencil leaves)
    for ang in (0.0, math.pi / 2, math.pi, 1.5 * math.pi):
        x = c + math.cos(ang + math.pi / 4) * (R1 + R2) / 2 * 0.72
        y = c + math.sin(ang + math.pi / 4) * (R1 + R2) / 2 * 0.72
        dl.rectangle([x - 9, y - 9, x + 9, y + 9], fill=0)
    if icon == 'cross':
        w, L = 78, 230
        dl.rectangle([c - w, c - L, c + w, c + L], fill=255)
        dl.rectangle([c - L, c - w, c + L, c + w], fill=255)
        # stencil bridges in the cross
        dl.rectangle([c - w, c - 8, c - w + 40, c + 8], fill=0)
        dl.rectangle([c + w - 40, c - 8, c + w, c + 8], fill=0)
    else:
        tre = trefoil_mask(c, c, 70, 250, 50)
        tl = np.maximum(np.asarray(lines, np.float32) / 255.0, tre)
        lines = Image.fromarray((tl * 255).astype(np.uint8))
        dl = ImageDraw.Draw(lines)
        for k in range(3):
            ang = math.radians(-90 + k * 120)
            x, y = c + math.cos(ang) * 160, c + math.sin(ang) * 160
            dl.ellipse([x - 7, y - 7, x + 7, y + 7], fill=0)
    la = np.asarray(lines.filter(ImageFilter.GaussianBlur(1.6)), np.float32) / 255.0
    halo = np.asarray(lines.filter(ImageFilter.GaussianBlur(14)), np.float32) / 255.0
    la = la + np.clip(halo - la, 0, 1) * (np.random.default_rng(9).random((N, N)) > 0.7) * 0.6
    la = wear(la, 0.22, 51 if icon == 'cross' else 52)
    fa = np.asarray(fill.filter(ImageFilter.GaussianBlur(3)), np.float32) / 255.0 * (0.6 + 0.4 * fbm_tileable(N, 5, 4, 60))
    rgb = np.stack([np.clip(la, 0, 1), np.clip(fa, 0, 1), np.zeros((N, N), np.float32)], -1)
    return rgb


if __name__ == '__main__':
    save(spray_circle('cross'), 'T_PU_SprayCircle_Cross')
    save(spray_circle('trefoil'), 'T_PU_SprayCircle_Trefoil')
    save(hazard('cross'), 'T_PU_Hazard_Cross', 'RGB')
    save(hazard('trefoil'), 'T_PU_Hazard_Trefoil', 'RGB')
    n = fbm_tileable(512, 6, 4, 77)
    save(n, 'T_PU_Noise')
    save(np.ones((64, 64), np.float32), 'T_PU_White')
    print('STYLE_TEXTURES_DONE')
