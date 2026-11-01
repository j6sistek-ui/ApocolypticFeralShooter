"""MakeWalkingVideo.py - before / after video and contact sheet from ProveWalking.py frames (2026-11-01).

Plain Python 3 with Pillow (not Unreal). Re-run after the ProveWalking runs (before + after, survival / explore /
postapo):

  python M:/UnrealProjects/AFS/Scripts/MakeWalkingVideo.py [root]

root defaults to D:/AFS_Comparisons/Walking_20261101. Writes walking_before_after.mp4 (1280x720, ~26 s, labelled)
and walking_contact_sheet.png there. Each segment is a 2 x 2 grid (segments() lists the phases and cases: before,
after_r1, mid_r2, after), side camera at foot height and 3/4 camera, 10 fps (real time), each segment played twice. ffmpeg: FFMPEG env, PATH, or the imageio_ffmpeg
wheel in Blender's extensions folder.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else 'D:/AFS_Comparisons/Walking_20261101')
W, H = 1280, 720
FPS = 10


def font(size):
    for name in ('arialbd.ttf', 'arial.ttf', 'segoeui.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


F_BIG, F_MID, F_SMALL = font(40), font(24), font(18)


def ffmpeg():
    exe = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if exe:
        return exe
    hits = glob.glob(os.path.expandvars(r'%APPDATA%\Blender Foundation\Blender\*\extensions\.local\lib\python*'
                                        r'\site-packages\imageio_ffmpeg\binaries\ffmpeg-*.exe'))
    if not hits:
        raise SystemExit('ffmpeg not found')
    return hits[-1]


def frames(phase, m, case, view):
    return sorted(glob.glob(str(ROOT / phase / m / 'frames' / ('%s_%s_[0-9]*.png' % (case, view)))))


def panel(path, label, colour, w=640, h=360):
    im = Image.open(path).convert('RGB') if path else Image.new('RGB', (W, H), (20, 20, 20))
    # Drop the HUD margins a little and keep 16:9.
    im = im.crop((80, 45, 1200, 675)).resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    tw = d.textlength(label, font=F_SMALL)
    d.rectangle((0, 0, tw + 16, 28), fill=colour)
    d.text((8, 4), label, font=F_SMALL, fill=(255, 255, 255))
    return im


def grid(title, cells, n):
    """cells: 4 x (frame list, label, colour) in reading order; returns n composed frames."""
    out = []
    for i in range(n):
        canvas = Image.new('RGB', (W, H), (0, 0, 0))
        for k, (lst, label, colour) in enumerate(cells):
            path = lst[min(i, len(lst) - 1)] if lst else None
            canvas.paste(panel(path, label, colour), ((k % 2) * 640, (k // 2) * 360))
        d = ImageDraw.Draw(canvas)
        tw = d.textlength(title, font=F_MID)
        d.rectangle(((W - tw) / 2 - 12, H / 2 - 18, (W + tw) / 2 + 12, H / 2 + 18), fill=(0, 0, 0))
        d.text(((W - tw) / 2, H / 2 - 14), title, font=F_MID, fill=(255, 230, 120))
        out.append(canvas)
    return out


def card(lines, n):
    im = Image.new('RGB', (W, H), (12, 12, 16))
    d = ImageDraw.Draw(im)
    y = 220
    for i, line in enumerate(lines):
        f = F_BIG if i == 0 else F_MID
        tw = d.textlength(line, font=f)
        d.text(((W - tw) / 2, y), line, font=f, fill=(255, 255, 255) if i == 0 else (200, 200, 200))
        y += 70 if i == 0 else 40
    return [im] * n


RED, GREEN, BLUE = (170, 30, 30), (20, 130, 50), (30, 70, 160)


def before_after(m, case, title, b_label, a_label):
    return grid(title, [(frames('before', m, case, 'side'), 'BEFORE ' + b_label + ' | side', RED),
                        (frames('after', m, case, 'side'), 'AFTER ' + a_label + ' | side', GREEN),
                        (frames('before', m, case, 'q34'), 'BEFORE | 3/4', RED),
                        (frames('after', m, case, 'q34'), 'AFTER | 3/4', GREEN)], 30)


def quad(title, cells):
    """cells: 4 x (phase, map, case, view, label, colour)."""
    return grid(title, [(frames(ph, m, c, v), lab, col) for ph, m, c, v, lab, col in cells], 30)


def segments():
    """2026-11-01 review round 2. Phases: before (pre-fix), after_r1 (first fix: in-air pose gone, still a walk with
    skating feet), mid_r2 (move-limit fix, crouch still 400 cm/s), after (all fixes; test pads in third person)."""
    seg = []
    seg.append(card(['Vexa walking fix - 2026-11-01 (review round 2)',
                     'NYC Survival Life Engine walk, crouch / hold-B on 3 maps',
                     'side camera at foot height and 3/4, real time, each clip twice'], 25))
    seg.append(before_after('survival', 'life_walk', 'Life Engine walk: original bug', '(in-air pose)', '(jog)') * 2)
    seg.append(quad('Life Engine walk: round 1 vs now (5 m/s)', [
        ('after_r1', 'survival', 'life_walk', 'side', 'ROUND 1 (walk clip, feet skate) | side', RED),
        ('after', 'survival', 'life_walk', 'side', 'NOW (jog cycle) | side', GREEN),
        ('after_r1', 'survival', 'life_walk', 'q34', 'ROUND 1 | 3/4', RED),
        ('after', 'survival', 'life_walk', 'q34', 'NOW | 3/4', GREEN)]) * 2)
    seg.append(quad('Now: Life Engine vs Classic, same input', [
        ('after', 'survival', 'life_walk', 'side', 'LIFE ENGINE | side', GREEN),
        ('after', 'survival', 'classic_walk', 'side', 'CLASSIC | side', BLUE),
        ('after', 'survival', 'life_walk', 'q34', 'LIFE ENGINE | 3/4', GREEN),
        ('after', 'survival', 'classic_walk', 'q34', 'CLASSIC | 3/4', BLUE)]) * 2)
    seg.append(quad('Crouch walk (tap B, W): 400 cm/s vs 300 cm/s (clip speed)', [
        ('mid_r2', 'survival', 'life_crouch', 'side', 'BEFORE 400 cm/s | side', RED),
        ('after', 'survival', 'life_crouch', 'side', 'AFTER 300 cm/s | side', GREEN),
        ('mid_r2', 'survival', 'life_crouch', 'q34', 'BEFORE | 3/4', RED),
        ('after', 'survival', 'life_crouch', 'q34', 'AFTER | 3/4', GREEN)]) * 2)
    seg.append(quad('Crouch walk now, third person: NYC Survival / Exploration / PostApo', [
        ('after', 'survival', 'life_crouch', 'side', 'NYC Survival | side', GREEN),
        ('after', 'explore', 'classic_crouch', 'side', 'NYC Exploration | side', BLUE),
        ('after', 'postapo', 'classic_crouch', 'side', 'PostApo desert | side', BLUE),
        ('after', 'postapo', 'classic_crouch', 'q34', 'PostApo desert | 3/4', BLUE)]) * 2)
    seg.append(quad('Crouched, moving sideways (D): one forward crouch clip', [
        ('after', 'survival', 'life_crouchstrafe', 'side', 'NYC Survival | side', GREEN),
        ('after', 'explore', 'classic_crouchstrafe', 'side', 'NYC Exploration | side', BLUE),
        ('after', 'survival', 'life_crouchstrafe', 'q34', 'NYC Survival | 3/4', GREEN),
        ('after', 'postapo', 'classic_crouchstrafe', 'q34', 'PostApo desert | 3/4', BLUE)]) * 2)
    seg.append(quad('Hold B at rest, then W (crawl), third person', [
        ('after', 'survival', 'life_crawl', 'side', 'NYC Survival | side', GREEN),
        ('after', 'explore', 'classic_crawl', 'side', 'NYC Exploration | side', BLUE),
        ('after', 'postapo', 'classic_crawl', 'side', 'PostApo desert | side', BLUE),
        ('after_r1', 'explore', 'classic_crawl', 'side', 'Exploration FIRST PERSON (round 1) | side', RED)]) * 2)
    seg.append(quad('Hold B while walking (dive, then W)', [
        ('after', 'survival', 'life_holdmove', 'side', 'NYC Survival | side', GREEN),
        ('after', 'explore', 'classic_holdmove', 'side', 'NYC Exploration | side', BLUE),
        ('after', 'survival', 'life_holdmove', 'q34', 'NYC Survival | 3/4', GREEN),
        ('after', 'postapo', 'classic_holdmove', 'side', 'PostApo desert | side', BLUE)]) * 2)
    return seg


def contact_sheet():
    rows = [('before', 'survival', 'life_walk', 'BEFORE Life Engine walk (in-air pose)'),
            ('after_r1', 'survival', 'life_walk', 'ROUND 1 Life Engine walk (walk clip)'),
            ('after', 'survival', 'life_walk', 'NOW Life Engine walk (jog)'),
            ('after', 'survival', 'classic_walk', 'NOW Classic walk'),
            ('mid_r2', 'survival', 'life_crouch', 'BEFORE crouch 400 cm/s NYC Survival'),
            ('after', 'survival', 'life_crouch', 'NOW crouch 300 cm/s NYC Survival'),
            ('after', 'explore', 'classic_crouch', 'NOW crouch NYC Exploration'),
            ('after', 'postapo', 'classic_crouch', 'NOW crouch PostApo'),
            ('after', 'survival', 'life_crawl', 'NOW hold-B crawl NYC Survival'),
            ('after', 'postapo', 'classic_crawl', 'NOW hold-B crawl PostApo'),
            ('after', 'survival', 'life_holdmove', 'NOW hold B moving NYC Survival')]
    cols, cw, ch, lw = 6, 320, 180, 300
    sheet = Image.new('RGB', (lw + cols * cw, len(rows) * ch), (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    for r, (phase, m, case, label) in enumerate(rows):
        lst = frames(phase, m, case, 'side')
        words, lines, cur = label.split(), [], ''
        for w in words:
            if len(cur) + len(w) > 24:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + ' ' + w).strip()
        lines.append(cur)
        d.text((10, r * ch + ch / 2 - 12 * len(lines)), chr(10).join(lines), font=F_SMALL, fill=(255, 255, 255))
        for c in range(cols):
            if not lst:
                break
            path = lst[min(len(lst) - 1, c * max(1, len(lst) // cols))]
            im = Image.open(path).convert('RGB').crop((160, 0, 1120, 540)).resize((cw, ch), Image.LANCZOS)
            sheet.paste(im, (lw + c * cw, r * ch))
    sheet.save(ROOT / 'walking_contact_sheet.png')


def main():
    tmp = Path(tempfile.mkdtemp(prefix='walkvid_'))
    n = 0
    for seg in segments():
        for im in seg:
            im.save(tmp / ('f%05d.png' % n))
            n += 1
    out = ROOT / 'walking_before_after.mp4'
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', str(tmp / 'f%05d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', '-crf', '20', str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    contact_sheet()
    print('frames', n, 'seconds', n / FPS, out)


if __name__ == '__main__':
    main()
