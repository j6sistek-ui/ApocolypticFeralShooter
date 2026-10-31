"""SheetPowerUpStyles.py - phone-readable contact sheets of the 14 power-up looks (plain Python + PIL).

Picks, per look, the newest round that rendered it (PU_SHEET_ROUNDS, newest last, default r4,r5) and writes to
D:/AFS_Comparisons/PowerUps_20261031/Styles/:
  styles_sheet.png        2 columns x 7 rows, 3/4 shot at ~2.5 m, big number + 2-4 word name per tile
  styles_sheet_10m.png    the same looks from 10 m (full frame, not zoomed: that is the honest distance read);
                          the three that read best at distance carry a "STRONG AT 10 M" tag
  styles_sheet_pulse.png  the nuke's ticking-bomb heartbeat (rest / half / peak) in the two strongest looks
Usage: python Scripts/SheetPowerUpStyles.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import PowerUpStyleRecipes as REC  # noqa: E402

BASE = 'D:/AFS_Comparisons/PowerUps_20261031/Styles'
ROUNDS = os.environ.get('PU_SHEET_ROUNDS', 'r4,r5').split(',')
STRONG_10M = [3, 14, 8]
PULSE_LOOKS = [4, 13]
TW, TH, BAR = 640, 344, 74


def font(sz, bold=True):
    for name in (('arialbd.ttf' if bold else 'arial.ttf'), 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(name, sz)
        except Exception:  # noqa: BLE001
            pass
    return ImageFont.load_default()


def still(look, suffix):
    tag = 'S%02d_%s_%s.png' % (look['n'], look['key'], suffix)
    for r in reversed(ROUNDS):
        p = '%s/stills/%s/%s' % (BASE, r, tag)
        if os.path.exists(p):
            return p
    return None


def tile(look, suffix, crop=True, badge=None):
    p = still(look, suffix)
    t = Image.new('RGB', (TW, TH + BAR), (14, 14, 16))
    if p:
        im = Image.open(p).convert('RGB')
        w, h = im.size
        if crop:  # trim the empty upper corners a little so the pair fills the tile
            cw, ch = int(w * 0.9), int(h * 0.9)
            x0, y0 = (w - cw) // 2, int((h - ch) * 0.2)
            im = im.crop((x0, y0, x0 + cw, y0 + ch))
        t.paste(im.resize((TW, TH)), (0, BAR))
    d = ImageDraw.Draw(t)
    d.rectangle([0, 0, TW, BAR], fill=(24, 24, 28))
    d.ellipse([8, 6, 70, 68], fill=(235, 190, 40))
    num = str(look['n'])
    f = font(40)
    tw = d.textlength(num, font=f)
    d.text((39 - tw / 2, 13), num, fill=(10, 10, 10), font=f)
    d.text((84, 14), look['name'], fill=(245, 245, 245), font=font(40))
    if badge:
        bf = font(24)
        bw = d.textlength(badge, font=bf)
        d.rectangle([TW - bw - 22, BAR + 10, TW - 8, BAR + 46], fill=(235, 190, 40))
        d.text((TW - bw - 15, BAR + 14), badge, fill=(10, 10, 10), font=bf)
    return t


def sheet(suffix, title, sub, out, crop, badges=None):
    cols, rows = 2, 7
    head = 120
    S = Image.new('RGB', (cols * TW + 3 * 8, head + rows * (TH + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 12), title, fill=(255, 255, 255), font=font(42))
    d.text((14, 66), sub, fill=(200, 200, 200), font=font(26, bold=False))
    for i, lk in enumerate(REC.LOOKS):
        badge = (badges or {}).get(lk['n'])
        t = tile(lk, suffix, crop, badge)
        S.paste(t, (8 + (i % cols) * (TW + 8), head + (i // cols) * (TH + BAR + 8)))
    S.save(out)
    print('wrote', out, S.size)


def pulse_sheet(out):
    fw, fh = 420, 300
    head = 110
    S = Image.new('RGB', (3 * fw + 4 * 8, head + len(PULSE_LOOKS) * (fh + BAR + 8) + 8), (8, 8, 10))
    d = ImageDraw.Draw(S)
    d.text((14, 10), 'The Nuke ticking: rest / half / peak', fill=(255, 255, 255), font=font(40))
    d.text((14, 62), 'scale +12 %, glow and light x3 at the peak, 1.25 Hz (rises toward detonation in game)',
           fill=(200, 200, 200), font=font(24, bold=False))
    for j, n in enumerate(PULSE_LOOKS):
        lk = next(x for x in REC.LOOKS if x['n'] == n)
        y = head + j * (fh + BAR + 8)
        bar = Image.new('RGB', (3 * fw + 2 * 8, BAR), (24, 24, 28))
        bd = ImageDraw.Draw(bar)
        bd.ellipse([8, 6, 70, 68], fill=(235, 190, 40))
        f = font(40)
        bd.text((39 - bd.textlength(str(n), font=f) / 2, 13), str(n), fill=(10, 10, 10), font=f)
        bd.text((84, 14), lk['name'], fill=(245, 245, 245), font=f)
        S.paste(bar, (8, y))
        for i in range(3):
            p = still(lk, 'pulse%d' % i)
            if p:
                im = Image.open(p).convert('RGB')
                w, h = im.size
                cw = int(h * fw / fh)
                x0 = (w - cw) // 2
                S.paste(im.crop((x0, 0, x0 + cw, h)).resize((fw, fh)), (8 + i * (fw + 8), y + BAR))
            d.text((16 + i * (fw + 8), y + BAR + 8), ('rest', 'half', 'peak')[i], fill=(255, 230, 120), font=font(30))
    S.save(out)
    print('wrote', out, S.size)


if __name__ == '__main__':
    sheet('close', 'AFS power-up looks: pick a number',
          'medkit left (red), nuke right (orange-white); dusk street, about 2.5 m', BASE + '/styles_sheet.png', True)
    sheet('10m', 'Same looks from 10 m', 'full frame, not zoomed; the pair is in the middle of each shot',
          BASE + '/styles_sheet_10m.png', False, {n: 'STRONG AT 10 M' for n in STRONG_10M})
    pulse_sheet(BASE + '/styles_sheet_pulse.png')
