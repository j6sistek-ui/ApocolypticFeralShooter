"""ContactPowerUpStyles.py - quick review grid of one preview round (plain Python + PIL).
Usage: python Scripts/ContactPowerUpStyles.py <round> <suffix:close|10m> <out.png> [tile_width]"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont
rnd, suf, out = sys.argv[1], sys.argv[2], sys.argv[3]
tw = int(sys.argv[4]) if len(sys.argv) > 4 else 480
src = 'D:/AFS_Comparisons/PowerUps_20261031/Styles/stills/' + rnd
fs = sorted(glob.glob(src + '/S??_*_%s.png' % suf))
th = int(tw * 682 / 1274)
cols = 4
rows = (len(fs) + cols - 1) // cols
sheet = Image.new('RGB', (cols * tw, rows * th), (20, 20, 20))
try:
    font = ImageFont.truetype('arialbd.ttf', 26)
except Exception:
    font = ImageFont.load_default()
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGB').resize((tw, th))
    d = ImageDraw.Draw(im)
    d.text((8, 6), os.path.basename(f)[:3], fill=(255, 255, 0), font=font, stroke_width=2, stroke_fill=(0, 0, 0))
    sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
sheet.save(out)
print(out, len(fs))
