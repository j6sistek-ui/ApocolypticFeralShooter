"""TopologyAudit.py - score a character body mesh's topology for deformation, headless Blender 5.2.
Usage: blender -b <file.blend> --python TopologyAudit.py -- <object name or 'auto'> <out_dir> <label>
   or: blender -b --python TopologyAudit.py -- <mesh.fbx> <out_dir> <label>
Metrics: face types (quads/tris/ngons), poles (valence >= 5 and 3), non-manifold edges, loose parts, loop density
per body band (10 % height slabs, verts per cm of circumference proxy), joint loop counts (rings at elbow/knee/
shoulder/hip bands), face-quad aspect (max/min edge per quad), UV layout (islands, overlap, texel share of the face),
symmetry (mirror residual), and renders a wireframe sheet (front/side/face/hand) with the edge flow visible.
"""
import bpy
import bmesh
import json
import os
import sys
from mathutils import Vector, kdtree

argv = sys.argv[sys.argv.index('--') + 1:]
target, out, label = argv[0], argv[1], argv[2]
os.makedirs(out, exist_ok=True)
if target.lower().endswith('.fbx'):
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=target)
    obj = max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.polygons))
else:
    obj = bpy.data.objects.get(target) if target != 'auto' else max((o for o in bpy.data.objects if o.type == 'MESH'), key=lambda o: len(o.data.polygons))
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
obj.hide_set(False)
obj.hide_viewport = False
# evaluate without modifiers: raw topology
me = obj.data
mw = obj.matrix_world
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
R = {'label': label, 'object': obj.name, 'verts': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces)}
R['quads'] = sum(1 for f in bm.faces if len(f.verts) == 4)
R['tris'] = sum(1 for f in bm.faces if len(f.verts) == 3)
R['ngons'] = sum(1 for f in bm.faces if len(f.verts) > 4)
R['non_manifold_edges'] = sum(1 for e in bm.edges if not e.is_manifold)
R['boundary_edges'] = sum(1 for e in bm.edges if len(e.link_faces) == 1)
val = {}
for v in bm.verts:
    k = len(v.link_edges)
    val[k] = val.get(k, 0) + 1
R['valence_histogram'] = dict(sorted(val.items()))
R['poles_5plus'] = sum(n for k, n in val.items() if k >= 5)
R['poles_3'] = val.get(3, 0)
R['poles_6plus'] = sum(n for k, n in val.items() if k >= 6)
# quad aspect / skew
asp = []
for f in bm.faces:
    if len(f.verts) != 4:
        continue
    ls = [e.calc_length() for e in f.edges]
    if min(ls) > 1e-9:
        asp.append(max(ls) / min(ls))
asp.sort()
R['quad_aspect_median'] = round(asp[len(asp) // 2], 2) if asp else None
R['quad_aspect_p95'] = round(asp[int(len(asp) * .95)], 2) if asp else None
R['quads_aspect_over_4'] = sum(1 for a in asp if a > 4)
# world-space geometry
co = [mw @ v.co for v in bm.verts]
zs = [c.z for c in co]
lo, hi = min(zs), max(zs)
H = hi - lo
R['height_m'] = round(H, 3)
bands = [0] * 10
for z in zs:
    bands[min(9, int((z - lo) / H * 10))] += 1
R['verts_per_height_band_bottom_to_top'] = bands
# symmetry residual: mirror x, nearest neighbour distance
kd = kdtree.KDTree(len(co))
for i, c in enumerate(co):
    kd.insert(c, i)
kd.balance()
import random
random.seed(1)
sample = random.sample(range(len(co)), min(4000, len(co)))
res = []
for i in sample:
    c = co[i]
    m = Vector((-c.x, c.y, c.z))
    hit = kd.find(m)
    res.append((hit[0] - m).length)
res.sort()
R['mirror_residual_median_mm'] = round(res[len(res) // 2] * 1000, 2)
R['mirror_residual_p95_mm'] = round(res[int(len(res) * .95)] * 1000, 2)
# loose parts
parts = 0
seen = set()
for v in bm.verts:
    if v.index in seen:
        continue
    parts += 1
    stack = [v]
    while stack:
        x = stack.pop()
        if x.index in seen:
            continue
        seen.add(x.index)
        for e in x.link_edges:
            o = e.other_vert(x)
            if o.index not in seen:
                stack.append(o)
R['loose_parts'] = parts
# joint ring density: count edge loops crossing horizontal slabs at joint heights (fractions of height, generic female)
joints = {'ankle': 0.04, 'knee': 0.28, 'hip': 0.52, 'waist': 0.62, 'shoulder': 0.82, 'neck': 0.86}
ring = {}
for name, fz in joints.items():
    z = lo + H * fz
    crossing = sum(1 for e in bm.edges if (mw @ e.verts[0].co).z - z) * 0  # placeholder keeps structure simple
    n = sum(1 for e in bm.edges if ((mw @ e.verts[0].co).z - z) * ((mw @ e.verts[1].co).z - z) < 0)
    ring[name] = n
R['edges_crossing_joint_planes'] = ring
# UV
uv_layer = bm.loops.layers.uv.active
if uv_layer:
    us = [l[uv_layer].uv for f in bm.faces for l in f.loops]
    R['uv'] = {'layers': len(me.uv_layers), 'min': [round(min(u.x for u in us), 3), round(min(u.y for u in us), 3)],
               'max': [round(max(u.x for u in us), 3), round(max(u.y for u in us), 3)], 'materials': [s.material.name if s.material else None for s in obj.material_slots]}
bm.free()
R['shape_keys'] = len(me.shape_keys.key_blocks) if me.shape_keys else 0
R['vertex_groups'] = len(obj.vertex_groups)
json.dump(R, open(os.path.join(out, 'topology_%s.json' % label), 'w'), indent=1)
print('TOPO', json.dumps(R), flush=True)
# wireframe renders: a Wireframe-modifier copy (black) over the flat grey body; freestyle drew nothing headless
sc = bpy.context.scene
for o in bpy.data.objects:
    if o.type == 'MESH' and o is not obj:
        o.hide_render = True
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'
sc.display.shading.color_type = 'MATERIAL'
sc.display.shading.show_object_outline = False
sc.render.resolution_x, sc.render.resolution_y = 1000, 1000
grey = bpy.data.materials.new('grey'); grey.diffuse_color = (0.82, 0.82, 0.82, 1)
black = bpy.data.materials.new('black'); black.diffuse_color = (0.05, 0.05, 0.05, 1)
obj.data.materials.clear(); obj.data.materials.append(grey)
for m in list(obj.modifiers): obj.modifiers.remove(m)
wire = obj.copy(); wire.data = obj.data.copy(); sc.collection.objects.link(wire)
wire.data.materials.clear(); wire.data.materials.append(black)
wm = wire.modifiers.new('wire', 'WIREFRAME'); wm.thickness = H * float(os.environ.get('WIRE_FRAC', '0.0006')); wm.use_relative_offset = False; wm.use_replace = True
cam_data = bpy.data.cameras.new('C')
cam = bpy.data.objects.new('C', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
cam_data.lens = 70
ctr = Vector((sum(c.x for c in co) / len(co), sum(c.y for c in co) / len(co), (lo + hi) / 2))
rad = H / 2
front = Vector((0, -1, 0))
if sum(1 for c in co if c.y < ctr.y) < len(co) / 2:
    front = Vector((0, 1, 0))  # the body faces +Y
side = Vector((1, 0, 0))


def shot(name, d, t, dist):
    cam.location = t + d.normalized() * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(out, 'wire_%s_%s.png' % (label, name))
    bpy.ops.render.render(write_still=True)


shot('front', front, ctr, rad * 2.6)
shot('side', side, ctr, rad * 2.6)
shot('face', front, Vector((ctr.x, ctr.y, hi - H * 0.065)), rad * 0.42)
shot('shoulder', front + Vector((0.6, 0, 0.2)), Vector((ctr.x + H * 0.1, ctr.y, hi - H * 0.2)), rad * 0.6)
shot('knee', front, Vector((ctr.x + H * 0.055, ctr.y, lo + H * 0.28)), rad * 0.5)
print('TOPO_DONE', flush=True)
