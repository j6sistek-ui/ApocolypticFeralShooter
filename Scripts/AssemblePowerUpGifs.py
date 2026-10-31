"""AssemblePowerUpGifs.py - turn the frames from Scripts/RecordPowerUpGifs.py into looping GIFs (system Python + PIL).

Run with the normal Python (not inside Unreal):  python M:/UnrealProjects/AFS/Scripts/AssemblePowerUpGifs.py
In : D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs/frames/record.json + frames/S<NN>_<Key>/f###.png (1274x682 captures)
Out: gifs/look_<NN>_<name>.gif (one look, 640x360, loops forever) and gifs/round2_motion_grid.gif (all recorded looks
     tiled with a number + name label); gifs/assemble.json with sizes, palettes and per-look frame-difference stats.
Frames are cropped to a 16:9 box around the pair (the neon signs at the top stay in) and scaled. One adaptive palette
is shared by all frames of a GIF (no dithering), so still background pixels stay identical between frames and the
GIF only stores what moves. Frame times alternate 70/70/60 ms = 15 fps on average (GIF delays are in 1/100 s).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

ROOT = Path('D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs')
FRAMES = ROOT / 'frames'
LOOK_MAX = 4.0e6
LOOK_T = 4
GRID_T = 6
GRID_MAX = 8.0e6
FONT_BIG = 'C:/Windows/Fonts/impact.ttf'
FONT_NAME = 'C:/Windows/Fonts/bahnschrift.ttf'


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def crop_box(w, h):
    cw = min(w, 960)
    ch = round(cw * 9 / 16)
    x0 = (w - cw) // 2
    y0 = max(0, min(8, h - ch))
    return (x0, y0, x0 + cw, y0 + ch)


def durations(n, fps):
    if fps == 15:
        pat = [70, 70, 60]
        return [pat[i % 3] for i in range(n)]
    return [round(1000 / fps / 10) * 10] * n


def label(img, n, name, big, small, pad=6):
    d = ImageDraw.Draw(img, 'RGBA')
    num = str(n)
    bn = d.textbbox((0, 0), num, font=big)
    bs = d.textbbox((0, 0), name, font=small)
    wn, hn = bn[2] - bn[0], bn[3] - bn[1]
    ws, hs = bs[2] - bs[0], bs[3] - bs[1]
    w = pad + wn + pad + ws + pad
    h = max(hn, hs) + 2 * pad
    y0 = img.size[1] - h          # bottom-left: the neon signs live at the top of the frame
    d.rectangle((0, y0, w, y0 + h), fill=(0, 0, 0, 170))
    d.text((pad - bn[0], y0 + pad - bn[1]), num, font=big, fill=(255, 255, 255, 255))
    d.text((pad + wn + pad - bs[0], y0 + pad + (hn - hs) - bs[1]), name, font=small, fill=(235, 235, 235, 255))


def shared_palette(frames, colors=255):
    """One adaptive palette for all frames: quantize a strip built from every 3rd frame."""
    pick = frames[::3]
    w, h = pick[0].size
    strip = Image.new('RGB', (w, h * len(pick)))
    for i, f in enumerate(pick):
        strip.paste(f, (0, i * h))
    small = strip.resize((w // 2, h * len(pick) // 2), Image.BILINEAR)
    return small.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)


def save_gif(frames, path, fps, colors=255, thresh=0):
    """Shared palette, no dithering. thresh > 0: a pixel whose quantized colour moved by at most `thresh` (max channel,
    0..255) from what is already on screen is written as transparent (disposal 1 keeps the previous frame), so the
    GIF stores only real motion; the shown image never drifts more than `thresh` from the quantized frame."""
    colors = min(colors, 255)
    pal = shared_palette(frames, colors)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    dur = durations(len(q), fps)
    if thresh <= 0:
        q[0].save(path, save_all=True, append_images=q[1:], loop=0, duration=dur, disposal=1, optimize=False)
        return path.stat().st_size
    flat = (pal.getpalette() or [])[:768]
    flat += [0] * (768 - len(flat))
    rgb = np.array(flat, dtype=np.int16).reshape(256, 3)
    TR = 255
    idx = [np.array(x, dtype=np.uint8) for x in q]
    disp = rgb[idx[0]].copy()
    out = []
    for i, ix in enumerate(idx):
        if i == 0:
            o = ix
        else:
            cur = rgb[ix]
            changed = np.abs(cur - disp).max(-1) > thresh
            o = np.where(changed, ix, TR).astype(np.uint8)
            disp[changed] = cur[changed]
        im = Image.fromarray(o, 'P')
        im.putpalette(flat)
        out.append(im)
    out[0].save(path, save_all=True, append_images=out[1:], loop=0, duration=dur, disposal=1, optimize=False,
                transparency=TR)
    return path.stat().st_size


def decode_error(path, frames):
    """Mean / max per-frame abs difference between the decoded GIF and the source frames (catches encoder surprises)."""
    g = Image.open(path)
    errs = []
    for i, f in enumerate(frames):
        g.seek(i)
        a = np.asarray(g.convert('RGB'), dtype=np.int16)
        b = np.asarray(f.convert('RGB'), dtype=np.int16)
        errs.append(float(np.abs(a - b).mean()))
    return round(sum(errs) / len(errs), 2), round(max(errs), 2), g.n_frames


def motion_stats(frames):
    """Mean absolute frame-to-frame difference (0..255) and the loop seam (last -> first) on the same scale."""
    g = [f.convert('L') for f in frames]
    diffs = [ImageStat.Stat(ImageChops.difference(g[i], g[i + 1])).mean[0] for i in range(len(g) - 1)]
    seam = ImageStat.Stat(ImageChops.difference(g[-1], g[0])).mean[0]
    first_vs_mid = ImageStat.Stat(ImageChops.difference(g[0], g[len(g) // 2])).mean[0]
    return {'step_mean': round(sum(diffs) / len(diffs), 3), 'step_min': round(min(diffs), 3),
            'step_max': round(max(diffs), 3), 'seam': round(seam, 3), 'first_vs_mid': round(first_vs_mid, 3),
            'identical_steps': sum(1 for d in diffs if d < 1e-4)}


def slug(name):
    return re.sub(r'[^A-Za-z0-9]+', '', name.title())


def main():
    rec = json.loads((FRAMES / 'record.json').read_text())
    fps = int(rec.get('fps', 15))
    out = {'fps': fps, 'looks': [], 'errors': []}
    tiles = []
    for n in rec['order']:
        look = next((v for v in rec['looks'].values() if v['n'] == n), None)
        if not look:
            out['errors'].append('look %d not recorded' % n)
            continue
        d = Path(look['dir'])
        files = sorted(d.glob('f*.png'))
        if len(files) < 2:
            out['errors'].append('look %d: %d frames' % (n, len(files)))
            continue
        raw = [Image.open(f).convert('RGB') for f in files]
        box = crop_box(*raw[0].size)
        big = [im.crop(box) for im in raw]
        stats = motion_stats([im.resize((320, 180), Image.BILINEAR) for im in big])
        name = look['name']
        path = ROOT / ('look_%02d_%s.gif' % (n, slug(name)))
        fr = [im.resize((640, 360), Image.LANCZOS) for im in big]
        for f in fr:
            label(f, n, name, font(FONT_BIG, 26), font(FONT_NAME, 18), pad=5)
        size = save_gif(fr, path, fps, thresh=LOOK_T)
        width = 640
        if size > LOOK_MAX:
            width = 560
            fr = [im.resize((560, 315), Image.LANCZOS) for im in big]
            for f in fr:
                label(f, n, name, font(FONT_BIG, 24), font(FONT_NAME, 16), pad=5)
            size = save_gif(fr, path, fps, thresh=LOOK_T)
        if size > LOOK_MAX:
            size = save_gif(fr, path, fps, colors=128, thresh=LOOK_T)
        derr = decode_error(path, fr)
        out['looks'].append({'n': n, 'name': name, 'gif': str(path), 'bytes': size, 'width': width,
                             'frames': len(fr), 'crop': box, 'motion': stats, 'decode_err': derr})
        tiles.append((n, name, big))
        print('look %2d %-22s %6.2f MB  %s decode %s' % (n, name, size / 1e6, stats, derr), flush=True)

    if tiles:
        nframes = min(len(t[2]) for t in tiles)
        for cols, tw in ((3, 400), (3, 360), (2, 400), (3, 320), (3, 280)):
            th = round(tw * 9 / 16)
            rows = (len(tiles) + cols - 1) // cols
            gap = 4
            W = cols * tw + (cols + 1) * gap
            H = rows * th + (rows + 1) * gap
            bigf, smallf = font(FONT_BIG, max(22, tw // 11)), font(FONT_NAME, max(14, tw // 22))
            frames = []
            for i in range(nframes):
                canvas = Image.new('RGB', (W, H), (12, 12, 12))
                for k, (n, name, big) in enumerate(tiles):
                    tile = big[i].resize((tw, th), Image.LANCZOS)
                    label(tile, n, name, bigf, smallf, pad=4)
                    canvas.paste(tile, (gap + (k % cols) * (tw + gap), gap + (k // cols) * (th + gap)))
                frames.append(canvas)
            path = ROOT / 'round2_motion_grid.gif'
            size = save_gif(frames, path, fps, thresh=GRID_T)
            print('grid %dx%d tiles %dx%d -> %dx%d %.2f MB' % (cols, rows, tw, th, W, H, size / 1e6), flush=True)
            out['grid'] = {'gif': str(path), 'bytes': size, 'cols': cols, 'tile': [tw, th], 'size': [W, H],
                           'looks': [t[0] for t in tiles]}
            if size <= GRID_MAX:
                out['grid']['decode_err'] = decode_error(path, frames)
                print('grid decode', out['grid']['decode_err'])
                break
    (ROOT / 'assemble.json').write_text(json.dumps(out, indent=1))
    return 0 if not out['errors'] else 1


if __name__ == '__main__':
    sys.exit(main())
