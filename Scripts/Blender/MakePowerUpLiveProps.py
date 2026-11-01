"""MakePowerUpLiveProps.py - neon icon meshes for the live power-up displays that round 1 did not make (Blender 5.2, headless).

Run:  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --python Scripts/Blender/MakePowerUpLiveProps.py
Never --factory-startup / read_factory_settings (wipes the owner's extension wheels): the scene is cleared with
bpy.ops.wm.read_homefile(use_empty=True).
Out: M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps/SM_PU_<Name>.glb, same conventions as
Scripts/Blender/MakePowerUpStyleProps.py (metres, sign in the XZ plane facing -Y, slots Lit / Dead / Frame) so
Scripts/AuthorPowerUpLive.py imports it next to NeonCross / NeonTrefoil.
  NeonAmmo   three standing cartridges in neon tube outline (Max Ammo, look 13); the middle tip is the dead tube
The tube helpers are copied from MakePowerUpStyleProps.py (that script runs every prop on import).
"""
import math
import os

import bpy

OUT = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps'
os.makedirs(OUT, exist_ok=True)
TUBE_R = 0.0075          # neon tube radius (m), same as the cross and trefoil
BULLET_W = 0.085         # cartridge width
BULLET_GAP = 0.13        # centre to centre
BASE_Z, MOUTH_Z, TIP_Z = -0.19, 0.045, 0.19


def reset():
    bpy.ops.wm.read_homefile(use_empty=True)


def mat(name, color=(0.5, 0.5, 0.5, 1)):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
    return m


def assign(obj, m):
    obj.data.materials.clear()
    obj.data.materials.append(m)


def box(sx, sy, sz, loc=(0, 0, 0), m=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.scale = (sx, sy, sz)
    if m:
        assign(o, m)
    return o


def tube_from_points(points, radius, m, name):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    sp = cu.splines.new('POLY')
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p[0], p[1], p[2], 1)
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(m)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.ops.object.convert(target='MESH')
    return bpy.context.active_object


def round_corners(pts, rad, n=4):
    out = []
    L = len(pts)
    for i in range(L):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % L]
        d0 = [(p1[j] - p0[j]) for j in range(3)]
        d1 = [(p2[j] - p1[j]) for j in range(3)]
        l0 = math.sqrt(sum(c * c for c in d0)) or 1
        l1 = math.sqrt(sum(c * c for c in d1)) or 1
        r = min(rad, l0 * 0.45, l1 * 0.45)
        a = [p1[j] - d0[j] / l0 * r for j in range(3)]
        b = [p1[j] + d1[j] / l1 * r for j in range(3)]
        for k in range(n + 1):
            t = k / n
            out.append([(1 - t) ** 2 * a[j] + 2 * (1 - t) * t * p1[j] + t * t * b[j] for j in range(3)])
    return out


def join_and_export(name, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = 'SM_PU_' + name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    path = os.path.join(OUT, 'SM_PU_%s.glb' % name)
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format='GLB', export_apply=True)
    print('PROP', name, len(o.data.polygons), 'faces ->', path)


def neon_frame(parts, frame, w, h, y=0.025):
    for z in (h * 0.3, -h * 0.3):
        parts.append(box(w, 0.006, 0.01, (0, y, z), m=frame))
    for x in (-w * 0.35, 0, w * 0.35):
        parts.append(box(0.012, y, 0.012, (x, y / 2, h * 0.3), m=frame))
        parts.append(box(0.012, y, 0.012, (x, y / 2, -h * 0.3), m=frame))
    parts.append(box(0.07, 0.04, 0.045, (w * 0.42, y + 0.02, -h * 0.3 - 0.03), m=frame))  # transformer box


def cartridge(cx):
    """Right side of the case up to the mouth, the rounded nose to the tip, back down the left side; open at the
    bottom middle (the electrode gap). Returns (outline run, nose run): the nose is split off so it can die."""
    hw = BULLET_W / 2
    right = [[cx + 0.004, 0, BASE_Z], [cx + hw, 0, BASE_Z], [cx + hw, 0, MOUTH_Z]]
    nose = []
    for i in range(1, 15):
        s = i / 14.0
        nose.append([cx + hw * 0.92 * math.sqrt(max(0.0, 1 - s ** 2)), 0, MOUTH_Z + (TIP_Z - MOUTH_Z) * s])
    for i in range(13, 0, -1):
        s = i / 14.0
        nose.append([cx - hw * 0.92 * math.sqrt(max(0.0, 1 - s ** 2)), 0, MOUTH_Z + (TIP_Z - MOUTH_Z) * s])
    left = [[cx - hw, 0, MOUTH_Z], [cx - hw, 0, BASE_Z], [cx - 0.004, 0, BASE_Z]]
    case = round_corners(right, 0.012)[1:-1]
    case_left = round_corners(left, 0.012)[1:-1]
    return [right[0]] + case + [[cx + hw, 0, MOUTH_Z]], nose, [[cx - hw, 0, MOUTH_Z]] + case_left + [left[-1]]


def neon_ammo():
    reset()
    lit, dead, frame = mat('Lit', (1, 0.7, 0.2, 1)), mat('Dead', (0.3, 0.3, 0.3, 1)), mat('Frame', (0.1, 0.1, 0.1, 1))
    parts = []
    for k, cx in enumerate((-BULLET_GAP, 0.0, BULLET_GAP)):
        rside, nose, lside = cartridge(cx)
        parts.append(tube_from_points(rside, TUBE_R, lit, 'r%d' % k))
        parts.append(tube_from_points(lside, TUBE_R, lit, 'l%d' % k))
        parts.append(tube_from_points(nose, TUBE_R, dead if k == 1 else lit, 'n%d' % k))
        hw = BULLET_W / 2 - 0.016            # the case mouth line, a short separate tube
        parts.append(tube_from_points([[cx - hw, 0, MOUTH_Z - 0.02], [cx + hw, 0, MOUTH_Z - 0.02]], TUBE_R * 0.8, lit,
                                      'm%d' % k))
        rim = BULLET_W / 2 - 0.012           # the rim groove near the base
        parts.append(tube_from_points([[cx - rim, 0, BASE_Z + 0.03], [cx + rim, 0, BASE_Z + 0.03]], TUBE_R * 0.8, lit,
                                      'g%d' % k))
    neon_frame(parts, frame, 0.46, 0.42)
    join_and_export('NeonAmmo', parts)


neon_ammo()
print('LIVE_PROPS_DONE')
