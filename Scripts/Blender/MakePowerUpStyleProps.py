"""MakePowerUpStyleProps.py - build the small street props the power-up style looks need, one GLB each (Blender 5.2, headless).

Run:  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --python Scripts/Blender/MakePowerUpStyleProps.py
Never --factory-startup / read_factory_settings (wipes the owner's extension wheels): the scene is cleared with
bpy.ops.wm.read_homefile(use_empty=True).
Out: M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps/SM_PU_<Name>.glb (metres, Z up, pivot bottom centre or
the stated point). Material slots are named so the Unreal authoring script can bind its own materials by slot name.
  FlareStick    road flare lying on its side (Body / Cap / Tip)              look 1
  Chemlight     snapped glowstick lying on its side (Tube / Cap)             look 2
  Beacon        small military strobe beacon (Body / Lens)                   look 3
  ProjectorPuck grimy holo-projector puck (Body / Trim / Lens)               look 4
  ScrapRing     rusted scrap-plate ring, 6 hazard lamps (Metal / Lights)     look 11
  NeonCross     storefront neon tube outline of a medical cross (Lit / Dead / Frame), stands in the XZ plane   look 13
  NeonTrefoil   neon tube outline of the radiation trefoil (Lit / Dead / Frame)                                look 13
  SearchLight   emergency work-light pointing up (Body / Lens)               look 14
  Shaft         open cylinder r 0.5 m, h 1 m, V runs 0 (bottom) -> 1 (top)  looks 3, 8, 14 (beams, columns)
  ConeShaft     open cone r 0.1 -> 0.5 m over 1 m, same UVs                   looks 4, 8, 14
  DustMotes     300 tiny motes scattered in a 0.45 m x 1.6 m cylinder (Motes) look 8
"""
import math
import os
import random

import bmesh
import bpy

OUT = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps'
os.makedirs(OUT, exist_ok=True)
random.seed(1031)


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


def join_and_export(name, objs, smart_uv=True):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = 'SM_PU_' + name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    if smart_uv:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
    path = os.path.join(OUT, 'SM_PU_%s.glb' % name)
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format='GLB', export_apply=True)
    print('PROP', name, len(o.data.polygons), 'faces ->', path)


def cyl(r, depth, loc=(0, 0, 0), rot=(0, 0, 0), verts=24, m=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    if m:
        assign(o, m)
    return o


def box(sx, sy, sz, loc=(0, 0, 0), rot=(0, 0, 0), m=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.scale = (sx, sy, sz)
    if m:
        assign(o, m)
    return o


def uvsphere(r, loc=(0, 0, 0), m=None, seg=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=seg, ring_count=rings)
    o = bpy.context.active_object
    if m:
        assign(o, m)
    return o


def flare_stick():
    reset()
    body, cap, tip = mat('Body', (0.6, 0.05, 0.03, 1)), mat('Cap', (0.1, 0.1, 0.1, 1)), mat('Tip', (1, 0.6, 0.3, 1))
    r = 0.016
    parts = [cyl(r, 0.20, (0, 0, r), (0, math.pi / 2, 0), m=body),
             cyl(r * 1.12, 0.035, (-0.115, 0, r), (0, math.pi / 2, 0), m=cap),
             cyl(r * 0.8, 0.02, (0.11, 0, r), (0, math.pi / 2, 0), m=tip)]
    s = uvsphere(r * 0.85, (0.122, 0, r), m=tip)
    s.scale = (1.3, 1, 1)
    parts.append(s)
    join_and_export('FlareStick', parts)


def chemlight():
    reset()
    tube, cap = mat('Tube', (0.9, 0.2, 0.2, 1)), mat('Cap', (0.15, 0.15, 0.15, 1))
    r = 0.0085
    t = cyl(r, 0.15, (0, 0, r), (0, math.pi / 2, 0), m=tube)
    e = uvsphere(r, (0.075, 0, r), m=tube)
    c = cyl(r * 1.1, 0.014, (-0.08, 0, r), (0, math.pi / 2, 0), m=cap)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.008, minor_radius=0.002, location=(-0.094, 0, r), rotation=(math.pi / 2, 0, 0))
    hook = bpy.context.active_object
    assign(hook, cap)
    join_and_export('Chemlight', [t, e, c, hook])


def beacon():
    reset()
    body, lens = mat('Body', (0.08, 0.09, 0.07, 1)), mat('Lens', (1, 1, 1, 1))
    b = box(0.10, 0.065, 0.035, (0, 0, 0.0175), m=body)
    bev = b.modifiers.new('bev', 'BEVEL')
    bev.width = 0.004
    bev.segments = 2
    bpy.context.view_layer.objects.active = b
    bpy.ops.object.modifier_apply(modifier='bev')
    collar = cyl(0.026, 0.008, (0.0, 0, 0.039), m=body)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.022, location=(0.0, 0, 0.043), segments=20, ring_count=10)
    dome = bpy.context.active_object
    assign(dome, lens)
    # keep the top half of the sphere only
    bm = bmesh.new()
    bm.from_mesh(dome.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.001], context='VERTS')
    bm.to_mesh(dome.data)
    bm.free()
    cage = []
    for k in range(4):
        a = k * math.pi / 2
        cage.append(box(0.003, 0.003, 0.03, (math.cos(a) * 0.024, math.sin(a) * 0.024, 0.056), m=body))
    ant = cyl(0.002, 0.07, (0.04, 0.022, 0.07), m=body)
    join_and_export('Beacon', [b, collar, dome, ant] + cage)


def projector_puck():
    reset()
    body, trim, lens = mat('Body', (0.2, 0.2, 0.2, 1)), mat('Trim', (0.05, 0.05, 0.05, 1)), mat('Lens', (0.5, 0.8, 1, 1))
    p = cyl(0.14, 0.05, (0, 0, 0.033), verts=40, m=body)
    bev = p.modifiers.new('bev', 'BEVEL')
    bev.width = 0.01
    bev.segments = 3
    bpy.context.view_layer.objects.active = p
    bpy.ops.object.modifier_apply(modifier='bev')
    ring = cyl(0.07, 0.012, (0, 0, 0.062), verts=32, m=trim)
    ln = cyl(0.05, 0.008, (0, 0, 0.068), verts=32, m=lens)
    parts = [p, ring, ln]
    for k in range(3):
        a = k * 2 * math.pi / 3 + 0.4
        parts.append(cyl(0.018, 0.012, (math.cos(a) * 0.1, math.sin(a) * 0.1, 0.006), verts=12, m=trim))
    for k in range(10):
        a = k * 2 * math.pi / 10
        parts.append(box(0.006, 0.03, 0.022, (math.cos(a) * 0.141, math.sin(a) * 0.141, 0.033), (0, 0, a), m=trim))
    # a dented cable stub
    parts.append(cyl(0.008, 0.08, (0.16, -0.03, 0.02), (0, math.pi / 2, 0.3), m=trim))
    join_and_export('ProjectorPuck', parts)


def scrap_ring():
    reset()
    metal, lights = mat('Metal', (0.35, 0.2, 0.1, 1)), mat('Lights', (1, 0.5, 0.1, 1))
    parts = []
    R = 0.5
    n = 11
    for k in range(n):
        a = k * 2 * math.pi / n + random.uniform(-0.05, 0.05)
        arc = 2 * math.pi * R / n * random.uniform(1.0, 1.25)
        h = random.uniform(0.012, 0.03)
        p = box(0.10 * random.uniform(0.85, 1.15), arc, 0.012,
                (math.cos(a) * R, math.sin(a) * R, h),
                (random.uniform(-0.08, 0.08), random.uniform(-0.06, 0.06), a), m=metal)
        parts.append(p)
        if k % 3 == 0:  # bent rebar / bolt stubs
            parts.append(cyl(0.006, 0.06, (math.cos(a) * (R + 0.03), math.sin(a) * (R + 0.03), 0.03), (0.4, 0.2, a), verts=8, m=metal))
    # inner lip of a cut tyre rim / pipe flange
    bpy.ops.mesh.primitive_torus_add(major_radius=R - 0.065, minor_radius=0.012, location=(0, 0, 0.012), major_segments=48, minor_segments=8)
    lip = bpy.context.active_object
    assign(lip, metal)
    parts.append(lip)
    for k in range(6):
        a = k * 2 * math.pi / 6 + 0.25
        x, y = math.cos(a) * (R + 0.005), math.sin(a) * (R + 0.005)
        parts.append(box(0.05, 0.045, 0.028, (x, y, 0.045), (0, 0, a), m=metal))
        parts.append(box(0.032, 0.03, 0.012, (x, y, 0.064), (0, 0, a), m=lights))
    join_and_export('ScrapRing', parts)


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
    """Bend a closed polygon's corners like a glass-blower would (neon tubes never have sharp corners)."""
    out = []
    L = len(pts)
    for i in range(L):
        p0, p1, p2 = pts[i - 1], pts[i], pts[(i + 1) % L]
        d0 = [(p1[j] - p0[j]) for j in range(3)]
        d1 = [(p2[j] - p1[j]) for j in range(3)]
        l0 = math.sqrt(sum(c * c for c in d0)) or 1
        l1 = math.sqrt(sum(c * c for c in d1)) or 1
        a = [p1[j] - d0[j] / l0 * rad for j in range(3)]
        b = [p1[j] + d1[j] / l1 * rad for j in range(3)]
        for k in range(n + 1):
            t = k / n
            q = [(1 - t) ** 2 * a[j] + 2 * (1 - t) * t * p1[j] + t * t * b[j] for j in range(3)]
            out.append(q)
    return out


def densify(pts, step=0.008, closed=True):
    out = []
    L = len(pts)
    for i in range(L if closed else L - 1):
        a, b = pts[i], pts[(i + 1) % L]
        d = math.sqrt(sum((b[j] - a[j]) ** 2 for j in range(3)))
        n = max(1, int(d / step))
        for k in range(n):
            t = k / n
            out.append([a[j] + (b[j] - a[j]) * t for j in range(3)])
    return out


def split_runs(pts, cuts):
    """Split a closed point loop into runs at the given indices (small gaps = electrode ends)."""
    runs = []
    idx = sorted(cuts)
    for i in range(len(idx)):
        a, b = idx[i], idx[(i + 1) % len(idx)]
        run = pts[a:b + 1] if b > a else pts[a:] + pts[:b + 1]
        runs.append(run[1:-1] if len(run) > 3 else run)
    return runs


def neon_frame(parts, frame, w, h, y=0.025):
    for z in (h * 0.3, -h * 0.3):
        parts.append(box(w, 0.006, 0.01, (0, y, z), m=frame))
    for x in (-w * 0.35, 0, w * 0.35):
        parts.append(box(0.012, y, 0.012, (x, y / 2, h * 0.3), m=frame))
        parts.append(box(0.012, y, 0.012, (x, y / 2, -h * 0.3), m=frame))
    parts.append(box(0.07, 0.04, 0.045, (w * 0.42, y + 0.02, -h * 0.3 - 0.03), m=frame))  # transformer box


def neon_cross():
    reset()
    lit, dead, frame = mat('Lit', (1, 0.2, 0.2, 1)), mat('Dead', (0.3, 0.3, 0.3, 1)), mat('Frame', (0.1, 0.1, 0.1, 1))
    a, w = 0.19, 0.065  # arm half-length, arm half-width (sign plane = XZ, faces -Y)
    poly = [(w, 0, a), (w, 0, w), (a, 0, w), (a, 0, -w), (w, 0, -w), (w, 0, -a), (-w, 0, -a), (-w, 0, -w), (-a, 0, -w),
            (-a, 0, w), (-w, 0, w), (-w, 0, a)]
    pts = densify(round_corners(poly, 0.018))
    n = len(pts)
    # cut in the middle of the arm ends (electrode gaps of about 1.6 cm); run 1 is the dead tube
    runs = split_runs(pts, [n // 24, n // 24 + n // 4, n // 24 + n // 2, n // 24 + 3 * n // 4])
    parts = []
    for i, r in enumerate(runs):
        parts.append(tube_from_points(r, 0.0075, dead if i == 1 else lit, 'run%d' % i))
    # a second inner tube on the long bar, like a double-stroke sign
    neon_frame(parts, frame, 0.46, 0.42)
    join_and_export('NeonCross', parts, smart_uv=True)


def neon_trefoil():
    reset()
    lit, dead, frame = mat('Lit', (1, 0.6, 0.2, 1)), mat('Dead', (0.3, 0.3, 0.3, 1)), mat('Frame', (0.1, 0.1, 0.1, 1))
    parts = []
    hub = [(math.cos(t) * 0.032, 0, math.sin(t) * 0.032) for t in [i * 2 * math.pi / 28 for i in range(28)]]
    parts.append(tube_from_points(hub + [hub[0]], 0.0065, lit, 'hub'))
    r0, r1 = 0.055, 0.19
    for k in range(3):
        c = math.radians(90 + k * 120)
        a0, a1 = c - math.radians(30), c + math.radians(30)
        outer = [(math.cos(a0 + (a1 - a0) * i / 16) * r1, 0, math.sin(a0 + (a1 - a0) * i / 16) * r1) for i in range(17)]
        inner = [(math.cos(a1 - (a1 - a0) * i / 8) * r0, 0, math.sin(a1 - (a1 - a0) * i / 8) * r0) for i in range(9)]
        loop = round_corners(outer + inner, 0.012, 3)
        if k == 2:  # the dead segment: the outer arc of the bottom-right blade
            m = len(loop)
            parts.append(tube_from_points(loop[:m // 2], 0.0075, dead, 'b%da' % k))
            parts.append(tube_from_points(loop[m // 2 + 1:] + [loop[0]], 0.0075, lit, 'b%db' % k))
        else:
            parts.append(tube_from_points(loop + [loop[0]], 0.0075, lit, 'b%d' % k))
    neon_frame(parts, frame, 0.44, 0.40)
    join_and_export('NeonTrefoil', parts, smart_uv=True)


def search_light():
    reset()
    body, lens = mat('Body', (0.15, 0.15, 0.13, 1)), mat('Lens', (1, 1, 0.9, 1))
    parts = [box(0.2, 0.14, 0.03, (0, 0, 0.015), m=body)]
    for y in (-0.06, 0.06):
        parts.append(box(0.02, 0.012, 0.11, (0, y, 0.08), m=body))
    h = cyl(0.075, 0.12, (0, 0, 0.13), verts=28, m=body)
    parts.append(h)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.075, minor_radius=0.008, location=(0, 0, 0.19), major_segments=28, minor_segments=6)
    rim = bpy.context.active_object
    assign(rim, body)
    parts.append(rim)
    parts.append(cyl(0.068, 0.006, (0, 0, 0.191), verts=28, m=lens))
    for k in range(4):
        parts.append(box(0.004, 0.13, 0.004, (-0.045 + k * 0.03, 0, 0.197), m=body))  # guard bars
    join_and_export('SearchLight', parts)


def open_tube(name, r0, r1, segs=48, rings=8):
    reset()
    m = mat('Beam', (1, 1, 1, 1))
    me = bpy.data.meshes.new(name)
    verts, faces, uvs = [], [], []
    for j in range(rings + 1):
        v = j / rings
        r = r0 + (r1 - r0) * v
        for i in range(segs + 1):
            a = i / segs * 2 * math.pi
            verts.append((math.cos(a) * r, math.sin(a) * r, v))
    for j in range(rings):
        for i in range(segs):
            a = j * (segs + 1) + i
            faces.append((a, a + 1, a + segs + 2, a + segs + 1))
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            j, i = divmod(vi, segs + 1)
            uvl.data[li].uv = (i / segs, j / rings)
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    join_and_export(name, [o], smart_uv=False)


def dust_motes():
    reset()
    m = mat('Motes', (1, 1, 1, 1))
    bm = bmesh.new()
    for k in range(300):
        r = 0.45 * math.sqrt(random.random())
        a = random.random() * 2 * math.pi
        z = random.random() * 1.6
        s = random.uniform(0.0025, 0.006)
        ret = bmesh.ops.create_icosphere(bm, subdivisions=0, radius=s)
        bmesh.ops.translate(bm, verts=ret['verts'], vec=(math.cos(a) * r, math.sin(a) * r, z))
    me = bpy.data.meshes.new('DustMotes')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m)
    o = bpy.data.objects.new('DustMotes', me)
    bpy.context.scene.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    join_and_export('DustMotes', [o])


for fn in (flare_stick, chemlight, beacon, projector_puck, scrap_ring, neon_cross, neon_trefoil, search_light, dust_motes):
    fn()
open_tube('Shaft', 0.5, 0.5)
open_tube('ConeShaft', 0.1, 0.5)
print('STYLE_PROPS_DONE')
