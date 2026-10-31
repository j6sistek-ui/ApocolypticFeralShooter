"""SplitHorrorGrenades.py - split the owner's Tripo "gas canister 3d model.glb" (really four horror grenades fused into one
mesh) into four separate meshes, no cleanup (owner 2026-10-31: "split it, dont clean it").

Blender 5.2 headless:  blender -b --python SplitHorrorGrenades.py -- <src.glb> <out_dir>
Method: separate by loose parts, take the four largest shells as the grenade bodies (they sit in a row along X),
assign every other shell (rings, spikes, drips, skulls) to the nearest body by horizontal distance, join each cluster,
put the origin at the body's bounding-box centre and the object at the world origin, keep the shared material and its
embedded 4K textures, export one GLB per grenade (Interchange imports GLB with materials + textures) plus a proof render.
Names left to right (by X): Grenade_Horror_01_Biohazard, 02_Cage, 03_Teeth, 04_Skull.
Receipt: <out_dir>/split_receipt.json.  Never calls read_factory_settings (wipes the owner's extension wheels).
"""
import bpy
import bmesh
import json
import os
import sys

from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
NAMES = ['Grenade_Horror_01_Biohazard', 'Grenade_Horror_02_Cage', 'Grenade_Horror_03_Teeth', 'Grenade_Horror_04_Skull']
R = {'src': SRC, 'out': OUT, 'grenades': [], 'warnings': []}

bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
src = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert len(src) == 1, src
obj = src[0]
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.separate(type='LOOSE')
bpy.ops.object.mode_set(mode='OBJECT')
parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']
R['loose_parts'] = len(parts)


def bbox_world(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def volume(o):
    lo, hi = bbox_world(o)
    d = hi - lo
    return d.x * d.y * d.z


# Bodies = the four largest shells by bounding volume, provided they are spread along X.
parts_sorted = sorted(parts, key=volume, reverse=True)
bodies = []
for o in parts_sorted:
    lo, hi = bbox_world(o)
    c = (lo + hi) / 2
    if all(abs(c.x - ((bbox_world(b)[0] + bbox_world(b)[1]) / 2).x) > 0.12 for b in bodies):
        bodies.append(o)
    if len(bodies) == 4:
        break
assert len(bodies) == 4, 'expected four grenade bodies, found %d' % len(bodies)
bodies.sort(key=lambda b: ((bbox_world(b)[0] + bbox_world(b)[1]) / 2).x)
centres = [(bbox_world(b)[0] + bbox_world(b)[1]) / 2 for b in bodies]
clusters = {i: [b] for i, b in enumerate(bodies)}
for o in parts:
    if o in bodies:
        continue
    lo, hi = bbox_world(o)
    c = (lo + hi) / 2
    # horizontal distance to each body's bounding box (0 if inside its X/Y span)
    best, bi = None, None
    for i, b in enumerate(bodies):
        blo, bhi = bbox_world(b)
        dx = max(blo.x - c.x, 0, c.x - bhi.x)
        dy = max(blo.y - c.y, 0, c.y - bhi.y)
        d = (dx * dx + dy * dy) ** .5
        if best is None or d < best:
            best, bi = d, i
    clusters[bi].append(o)

for i, name in enumerate(NAMES):
    group = clusters[i]
    bpy.ops.object.select_all(action='DESELECT')
    for o in group:
        o.select_set(True)
    bpy.context.view_layer.objects.active = bodies[i]
    bpy.ops.object.join()
    g = bpy.context.view_layer.objects.active
    g.name = name
    g.data.name = name
    lo, hi = bbox_world(g)
    centre = (lo + hi) / 2
    # origin at the bounding-box centre, object at the world origin
    bpy.context.scene.cursor.location = centre
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    g.location = (0, 0, 0)
    dims = [round(d, 4) for d in g.dimensions]
    tris = sum(len(p.vertices) - 2 for p in g.data.polygons)
    out_glb = os.path.join(OUT, name + '.glb')
    bpy.ops.object.select_all(action='DESELECT')
    g.select_set(True)
    bpy.ops.export_scene.gltf(filepath=out_glb, use_selection=True, export_format='GLB', export_apply=True,
                              export_image_format='AUTO', export_yup=True)
    R['grenades'].append({'name': name, 'parts': len(group), 'tris': tris, 'dims_m': dims,
                          'centre_in_source_m': [round(v, 4) for v in centre], 'glb': out_glb,
                          'bytes': os.path.getsize(out_glb)})
    print('SPLIT', json.dumps(R['grenades'][-1]), flush=True)
    g.hide_render = True

# proof render: all four side by side at the origin spaced 0.3 m apart
objs = [bpy.data.objects[n] for n in NAMES]
for k, g in enumerate(objs):
    g.hide_render = False
    g.location = ((k - 1.5) * 0.3, 0, 0)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x, sc.render.resolution_y = 1600, 700
cam_data = bpy.data.cameras.new('C')
cam = bpy.data.objects.new('C', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
cam_data.lens = 50
cam.location = Vector((0.6, -1.6, 0.55))
cam.rotation_euler = (Vector((0, 0, 0.05)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = os.path.join(OUT, 'proof_split.png')
bpy.ops.render.render(write_still=True)
with open(os.path.join(OUT, 'split_receipt.json'), 'w') as f:
    json.dump(R, f, indent=1)
print('SPLIT_DONE', json.dumps({'parts': R['loose_parts'], 'grenades': [(g['name'], g['parts'], g['tris']) for g in R['grenades']]}), flush=True)
