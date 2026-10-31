"""SheetPowerUpStyles2.py - phone-readable sheets of the round-2 power-up looks (plain Python + PIL).

Stills come from Scripts/PreviewPowerUpStyles2.py (D:/AFS_Comparisons/PowerUps_20261031/Styles/R2/stills/<round>/).
Writes to D:/AFS_Comparisons/PowerUps_20261031/Styles/:
  round2_sheet.png           kept looks first (5 6 7 8 13), then the new ones (15-23); 3/4 shot at about 2.5 m
  round2_sheet_10m.png       the same from 10 m: full frame (the honest distance read) with a 3x inset of the pair
  round2_sheet_pulse.png     the Nuke's heartbeat (rest / peak / after) in 23 and the three strongest looks
  round2_combo23.png         look 23 (the owner's 5+6+13 combo) on its own: close, 10 m, pulse frames
  round1_vs_round2_kept.png  round 1 (left) against round 2 (right) for 5, 6, 7, 8, 13
Usage: python Scripts/SheetPowerUpStyles2.py   (PU2_SHEET_ROUND=r5 picks the still folder)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.modules.setdefault('unreal', None)
sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import PowerUpStyleRecipes2 as REC2  # noqa: E402

BASE = 'D:/AFS_Comparisons/PowerUps_20261031/Styles'
ROUND = os.environ.get('PU2_SHEET_ROUND', 'r5')
R2 = '%s/R2/stills/%s' % (BASE, ROUND)
R1 = ['%s/stills/r5' % BASE, '%s/stills/r4' % BASE]   # round 1: newest first
STRONG_10M = [8, 13, 17, 23]
PULSE_LOOKS = [23, 20, 21, 6]
TW, TH, BAR = 640, 344, 74
GOLD = (235, 190, 40)
TEAL = (60, 200, 190)
SHORT = {5: 'Radioactive', 6: 'Blood Relic', 7: 'Infected', 8: 'Dust Shaft', 13: 'Busted Neon', 15: 'Energy Swirl',
         16: 'Arc Crawl', 17: 'Soul Wisps', 18: 'Ember Corona', 19: 'Inner Glow', 20: 'Heartbeat', 21: 'Toxic Aura',
         22: 'Rarity Mist', 23: 'Combo 5+6+13'}


def font(sz, bold=True):
    for name in (('arialbd.ttf' if bold else 'arial.ttf'), 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:  # noqa: BLE001
            pass
    return ImageFont.load_default()


def r2_still(look, suffix):
    p = '%s/S%02d_%s_%s.png' % (R2, look['n'], look['key'], suffix)
    return p if os.path.exists(p) else None


def r1_still(n, key, suffix):
    for d in R1:
        p = '%s/S%02d_%s_%s.png' % (d, n, key, suffix)
        if os.path.exists(p):
            return p
    return None


def crop_close(im):
    w, h = im.size
    cw, ch = int(w * 0.9), int(h * 0.9)
    x0, y0 = (w - cw) // 2, int((h - ch) * 0.2)
    return im.crop((x0, y0, x0 + cw, y0 + ch))


def label_bar(d, n, name, width, color=GOLD, tag=None):
    d.rectangle([0, 0, width, BAR], fill=(24, 24, 28))
    d.ellipse([8, 6, 70, 68], fill=color)
    num = str(n)
    f = font(36 if len(num) > 1 else 40)
    tw = d.textlength(num, font=f)
    d.text((39 - tw / 2, 15), num, fill=(10, 10, 10), font=f)
    d.text((84, 14), name, fill=(245, 245, 245), font=font(40))
    if tag:
        bf = font(22)
        bw = d.textlength(tag, font=bf)
        d.rectangle([width - bw - 22, 22, width - 8, 54], fill=(60, 60, 70))
        d.text((width - bw - 15, 25), tag, fill=(240, 240, 240), font=bf)


def tile(look, suffix, crop=True, badge=None, inset=False):
    p = r2_still(look, suffix)
    t = Image.new('RGB', (TW, TH + BAR), (14, 14, 16))
    if p:
        im = Image.open(p).convert('RGB')
        src = im
        if crop:
            im = crop_close(im)
        t.paste(im.resize((TW, TH)), (0, BAR))
        if inset:   # the pair at 10 m, magnified 3x, bottom right (the full frame stays the honest read)
            w, h = src.size
            cw, ch = int(w * 0.24), int(h * 0.24)
            x0, y0 = int(w * 0.5 - cw / 2), int(h * 0.46 - ch / 2)
            iw, ih = 300, int(300 * ch / cw)
            ins = src.crop((x0, y0, x0 + cw, y0 + ch)).resize((iw, ih))
            d0 = ImageDraw.Draw(t)
            d0.rectangle([TW - iw - 10, TH + BAR - ih - 10, TW - 6, TH + BAR - 6], fill=(235, 235, 235))
            t.paste(ins, (TW - iw - 8, TH + BAR - ih - 8))
            d0.text((TW - iw - 4, TH + BAR - ih - 6), '3x', fill=(255, 255, 255), font=font(20), stroke_width=2,
                    stroke_fill=(0, 0, 0))
    d = ImageDraw.Draw(t)
    kept = look.get('r1')
    label_bar(d, look['n'], SHORT[look['n']], TW, TEAL if kept else GOLD,
              'KEPT' if kept else ('OWNER COMBO' if look['n'] == 23 else 'NEW'))
    if badge:
        bf = font(24)
        bw = d.textlength(badge, font=bf)
        d.rectangle([TW - bw - 22, BAR + 10, TW - 8, BAR + 46], fill=GOLD)
        d.text((TW - bw - 15, BAR + 14), badge, fill=(10, 10, 10), font=bf)
    return t


def sheet(suffix, title, sub, out, crop, badges=None, inset=False):
    looks = REC2.LOOKS
    cols, rows = 2, (len(looks) + 1) // 2
    head = 120
    S = Image.new('RGB', (cols * TW + 3 * 8, head + rows * (TH + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 12), title, fill=(255, 255, 255), font=font(40))
    d.text((14, 64), sub, fill=(200, 200, 200), font=font(24, bold=False))
    for i, lk in enumerate(looks):
        t = tile(lk, suffix, crop, (badges or {}).get(lk['n']), inset)
        S.paste(t, (8 + (i % cols) * (TW + 8), head + (i // cols) * (TH + BAR + 8)))
    S.save(out)
    print('wrote', out, S.size)


def pulse_strip(S, d, lk, y, fw, fh):
    bar = Image.new('RGB', (3 * fw + 2 * 8, BAR), (24, 24, 28))
    label_bar(ImageDraw.Draw(bar), lk['n'], SHORT[lk['n']], 3 * fw + 16)
    S.paste(bar, (8, y))
    for i in range(3):
        p = r2_still(lk, 'pulse%d' % i)
        if p:
            im = Image.open(p).convert('RGB')
            w, h = im.size
            cw = int(h * fw / fh)
            x0 = (w - cw) // 2
            S.paste(im.crop((x0, 0, x0 + cw, h)).resize((fw, fh)), (8 + i * (fw + 8), y + BAR))
        d.text((16 + i * (fw + 8), y + BAR + 8), ('rest', 'peak', 'after the beat')[i], fill=(255, 230, 120),
               font=font(30), stroke_width=2, stroke_fill=(0, 0, 0))


def pulse_sheet(out):
    fw, fh = 420, 300
    head = 110
    S = Image.new('RGB', (3 * fw + 4 * 8, head + len(PULSE_LOOKS) * (fh + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 10), 'The Nuke ticking: rest / peak / after', fill=(255, 255, 255), font=font(40))
    d.text((14, 62), 'swells 12 %, glow and light x3 at the peak, 1.25 Hz (rises toward detonation in game)',
           fill=(200, 200, 200), font=font(24, bold=False))
    for j, n in enumerate(PULSE_LOOKS):
        lk = next(x for x in REC2.LOOKS if x['n'] == n)
        pulse_strip(S, d, lk, head + j * (fh + BAR + 8), fw, fh)
    S.save(out)
    print('wrote', out, S.size)


def combo_sheet(out):
    lk = next(x for x in REC2.LOOKS if x['n'] == 23)
    W = 2 * TW + 24
    fw, fh = (W - 32) // 3, 300
    head = 110
    S = Image.new('RGB', (W, head + (TH + BAR + 8) + (fh + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 10), 'Look 23: Radioactive + Blood Relic + Busted Neon', fill=(255, 255, 255), font=font(38))
    d.text((14, 60), 'sick-green seams and specks (5), deep type-colour mist on the rim (6), neon icon (13)',
           fill=(200, 200, 200), font=font(24, bold=False))
    S.paste(tile(lk, 'close', True), (8, head))
    S.paste(tile(lk, '10m', False, None, True), (16 + TW, head))
    pulse_strip(S, d, lk, head + TH + BAR + 8, fw, fh)
    S.save(out)
    print('wrote', out, S.size)


def kept_compare(out):
    pairs = [lk for lk in REC2.LOOKS if lk.get('r1')]
    head = 120
    S = Image.new('RGB', (2 * TW + 24, head + len(pairs) * (TH + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 12), 'Kept looks: round 1 (left) vs round 2 (right)', fill=(255, 255, 255), font=font(40))
    d.text((14, 66), 'round 2: no ground rings, pools or splats; items readable; fixes from the checker',
           fill=(200, 200, 200), font=font(24, bold=False))
    for j, lk in enumerate(pairs):
        y = head + j * (TH + BAR + 8)
        for i, p in enumerate((r1_still(lk['n'], lk['key'], 'close'), r2_still(lk, 'close'))):
            t = Image.new('RGB', (TW, TH + BAR), (14, 14, 16))
            if p:
                t.paste(crop_close(Image.open(p).convert('RGB')).resize((TW, TH)), (0, BAR))
            label_bar(ImageDraw.Draw(t), lk['n'], SHORT[lk['n']], TW, (120, 120, 130) if i == 0 else TEAL,
                      'ROUND 1' if i == 0 else 'ROUND 2')
            S.paste(t, (8 + i * (TW + 8), y))
    S.save(out)
    print('wrote', out, S.size)


if __name__ == '__main__':
    sheet('close', 'AFS power-up looks, round 2: pick a number',
          'kept looks first (teal), then new (gold); medkit left (red), nuke right (orange); about 2.5 m',
          BASE + '/round2_sheet.png', True)
    sheet('10m', 'Round 2 from 10 m', 'full frame, not zoomed; the 3x inset (bottom right) shows the pair',
          BASE + '/round2_sheet_10m.png', False, {n: 'STRONG AT 10 M' for n in STRONG_10M}, inset=True)
    pulse_sheet(BASE + '/round2_sheet_pulse.png')
    combo_sheet(BASE + '/round2_combo23.png')
    kept_compare(BASE + '/round1_vs_round2_kept.png')
