"""Renders every EM gun in its FBX file orientation (Blender world after import, Z up)
from -Y, plus EM_04/EM_09/EM_26 from all three axes, to confirm muzzle direction
and the 'rotated in file' flags. Output: _survey_tiles/fileaxes_sheet.png and _axes_EM_NN_*.png.
"""
import bpy, os, glob, math
import numpy as np

PACK = r"M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns"
ROOT = os.path.join(PACK, "FBX", "EM_Apocalyptic_Guns_FBX")
TMP = os.path.join(PACK, "_survey_tiles")
W, H, COLS = 512, 288, 6


def shoot(o, view, label, out):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    if not sc.world:
        sc.world = bpy.data.worlds.new("w")
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(0), co.max(0)
    c, e = (lo + hi) / 2, hi - lo
    for ob in [x for x in sc.objects if x.type in ('CAMERA', 'FONT')]:
        bpy.data.objects.remove(ob)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'
    cam.data.clip_end = 10000
    # view: '-Y' front (X right, Z up), '+X' side (Y right... ), '+Z' top (X right, Y up)
    if view == '-Y':
        s = max(e[0], e[2] * W / H) * 1.15
        cam.location = (c[0], lo[1] - 50, c[2]); cam.rotation_euler = (math.radians(90), 0, 0)
    elif view == '-X':
        s = max(e[1], e[2] * W / H) * 1.15
        cam.location = (lo[0] - 50, c[1], c[2]); cam.rotation_euler = (math.radians(90), 0, math.radians(-90))
    else:
        s = max(e[0], e[1] * W / H) * 1.15
        cam.location = (c[0], c[1], hi[2] + 50); cam.rotation_euler = (0, 0, 0)
    cam.data.ortho_scale = s
    sc.camera = cam
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "EM_*", "*.fbx")))
    tiles = []
    for f in files:
        g = os.path.basename(os.path.dirname(f))[:5]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=f)
        o = [x for x in bpy.context.scene.objects if x.type == 'MESH'][0]
        o.data.transform(o.matrix_world)
        o.matrix_world.identity()
        p = os.path.join(TMP, "_file_%s.png" % g)
        shoot(o, '-Y', g, p)
        tiles.append(p)
        if g in ("EM_04", "EM_09", "EM_26"):
            for v in ('-X', '+Z'):
                shoot(o, v, g, os.path.join(TMP, "_axes_%s_%s.png" % (g, v.replace('+', 'p').replace('-', 'm'))))
    rows = math.ceil(len(tiles) / COLS)
    sheet = np.zeros((rows * H, COLS * W, 4), np.float32)
    for k, p in enumerate(tiles):
        px = np.array(bpy.data.images.load(p).pixels[:], np.float32).reshape(H, W, 4)
        r, c = k // COLS, k % COLS
        y0 = (rows - 1 - r) * H
        sheet[y0:y0 + H, c * W:(c + 1) * W] = px
    im = bpy.data.images.new("s", COLS * W, rows * H, alpha=True)
    im.pixels.foreach_set(sheet.ravel())
    im.filepath_raw = os.path.join(TMP, "fileaxes_sheet.png")
    im.file_format = 'PNG'
    im.save()
    print("WROTE", im.filepath_raw)


main()
