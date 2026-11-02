"""MakeWeatherVideo.py - labelled weather video, contact sheet and Clear-vs-baseline check from ProveWeather.py output.

Plain Python 3 with Pillow (not Unreal). Re-run after Scripts/ProveWeather.py (and once, before the weather actor
existed, ProveWeather.py with WEATHER_BASELINE=1):

  python M:/UnrealProjects/AFS/Scripts/MakeWeatherVideo.py [root]

root defaults to D:/AFS_Comparisons/Weather_20261101. Writes there:
  weather_nyc.mp4            1280x720, 30 fps, the recorded segments in order (Clear player / street, the menu
                             switch to Rain through its blend, rain street, the switch to Snow, snow street, Clear
                             again), each with a caption bar; plus the storm flash stills held for a moment.
  weather_contact_sheet.png  the stills (clear / rain / storm / snow / cloudy / clear-again x player / street /
                             close) labelled.
  clear_check.json           mean absolute pixel difference (0-255) of the Clear stills against the baseline
                             (no weather actor) and of clear-again against the first Clear, on the 3D area
                             (HUD margins cropped); zombies and animation differ between runs, so small numbers
                             are expected, a lighting change shows as a large one.
ffmpeg: FFMPEG env, PATH, or the imageio_ffmpeg wheel in Blender's extensions folder (as MakeWalkingVideo.py).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else 'D:/AFS_Comparisons/Weather_20261101')
W, H, FPS, SRC_FPS = 1280, 720, 30, 15
SEGMENTS = [  # (frame prefix, caption)
    ('v01_clear_player', 'CLEAR (default) - player view at spawn'),
    ('v02_clear_street', 'CLEAR - street view'),
    ('v03_to_rain_player', 'F6 menu: Weather > Rain - 6 s blend, player view'),
    ('v04_rain_street', 'RAIN - street view (wet streets, splashes, rain loop)'),
    ('v05_to_snow_player', 'F6 menu: Weather > Snow - 6 s blend, player view'),
    ('v06_snow_street', 'SNOW - street view (snow cover on up-facing surfaces)'),
    ('v07_clear_after_street', 'CLEAR again - the map\'s own lighting restored'),
]


def font(size):
    for name in ('arialbd.ttf', 'arial.ttf', 'segoeui.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_BIG, F_SMALL = font(30), font(20)


def ffmpeg():
    exe = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if exe:
        return exe
    hits = glob.glob(os.path.expandvars(r'%APPDATA%\Blender Foundation\Blender\*\extensions\.local\lib\python*'
                                        r'\site-packages\imageio_ffmpeg\binaries\ffmpeg-*.exe'))
    if not hits:
        raise SystemExit('ffmpeg not found')
    return hits[-1]


def caption(im, text, sub=''):
    src = im.convert('RGB')
    if src.size[0] > W or src.size[1] > H:
        src = src.resize((W, H), Image.BILINEAR)
    # The offscreen viewport is 1274 x 682: letterbox it (no stretch); the caption bar sits on the bottom margin.
    im = Image.new('RGB', (W, H), (0, 0, 0))
    im.paste(src, ((W - src.size[0]) // 2, 0))
    d = ImageDraw.Draw(im, 'RGBA')
    d.rectangle((0, H - 64, W, H), fill=(0, 0, 0, 170))
    d.text((24, H - 56), text, font=F_BIG, fill=(255, 255, 255))
    if sub:
        tw = d.textlength(sub, font=F_SMALL)
        d.text((W - tw - 24, H - 46), sub, font=F_SMALL, fill=(190, 210, 230))
    return im


def video():
    tmp = Path(tempfile.mkdtemp(prefix='afs_weather_'))
    n = 0
    used = {}
    for prefix, text in SEGMENTS:
        files = sorted(glob.glob(str(ROOT / 'frames' / (prefix + '_[0-9]*.png'))))
        used[prefix] = len(files)
        for i, f in enumerate(files):
            # ProveWeather.py records at 15 fps of game time; ffmpeg reads 15 fps and writes 30 (real speed).
            caption(Image.open(f), text, 'AFS NYC Survival - Dreamrise weather - %.1f s' % (i / 15.0)).save(
                tmp / ('f%05d.jpg' % n), quality=94)
            n += 1
        if prefix == 'v04_rain_street':  # storm flash stills, held 0.5 s each
            for f in sorted(glob.glob(str(ROOT / 'stills' / 'storm_flash_*.png')))[:2] + \
                    sorted(glob.glob(str(ROOT / 'stills' / 'storm_street.png'))):
                im = caption(Image.open(f), 'STORM - rain + thunder (BP_Thunder strike, sky flash)', Path(f).stem)
                for _ in range(SRC_FPS // 2):
                    im.save(tmp / ('f%05d.jpg' % n), quality=94)
                    n += 1
    out = ROOT / 'weather_nyc.mp4'
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-framerate', str(SRC_FPS), '-i', str(tmp / 'f%05d.jpg'),
                    '-r', str(FPS), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print('video', out, '%d source frames = %.1f s' % (n, n / SRC_FPS), json.dumps(used))


def sheet():
    rows = ['clear', 'rain', 'storm', 'snow', 'cloudy', 'clear_after']
    cols = ['player', 'street', 'close']
    tw, th = 427, 240
    im = Image.new('RGB', (110 + tw * len(cols), 30 + th * len(rows)), (18, 18, 22))
    d = ImageDraw.Draw(im)
    for c, name in enumerate(cols):
        d.text((110 + c * tw + 8, 6), name, font=F_SMALL, fill=(220, 220, 220))
    for r, row in enumerate(rows):
        d.text((8, 30 + r * th + th // 2 - 10), row.replace('_', ' '), font=F_SMALL, fill=(220, 220, 220))
        for c, col in enumerate(cols):
            f = ROOT / 'stills' / ('%s_%s.png' % (row, col))
            if f.exists():
                im.paste(Image.open(f).convert('RGB').resize((tw, th), Image.LANCZOS), (110 + c * tw, 30 + r * th))
    out = ROOT / 'weather_contact_sheet.png'
    im.save(out)
    print('sheet', out)


def diff(a, b):
    box = (0, 80, 1270, 560)  # the 3D area between the HUD text blocks
    ia = Image.open(a).convert('RGB').crop(box)
    ib = Image.open(b).convert('RGB').crop(box)
    st = ImageStat.Stat(ImageChops.difference(ia, ib))
    return round(sum(st.mean) / 3, 2), [round(x, 1) for x in ImageStat.Stat(ia).mean], [round(x, 1) for x in ImageStat.Stat(ib).mean]


def clear_check():
    out = {}
    pairs = [('baseline/clear_player.png', 'stills/clear_player.png'), ('baseline/clear_street.png', 'stills/clear_street.png'),
             ('stills/clear_player.png', 'stills/clear_after_player.png'), ('stills/clear_street.png', 'stills/clear_after_street.png'),
             ('stills/clear_street.png', 'stills/rain_street.png'), ('stills/clear_street.png', 'stills/snow_street.png')]
    for a, b in pairs:
        if (ROOT / a).exists() and (ROOT / b).exists():
            m, ma, mb = diff(ROOT / a, ROOT / b)
            out['%s vs %s' % (a, b)] = {'mean_abs_diff': m, 'mean_rgb_a': ma, 'mean_rgb_b': mb}
    (ROOT / 'clear_check.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    clear_check()
    sheet()
    video()
