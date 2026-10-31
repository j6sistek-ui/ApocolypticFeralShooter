"""RenderPropSheet.py - look at a folder of GLB props before deciding what they are for (2026-10-31).

  blender -b --python M:/UnrealProjects/AFS/Scripts/Blender/RenderPropSheet.py -- <folder_with_glbs> <out_folder>

Each GLB is imported into an empty scene (read_homefile, never factory settings), framed, and rendered twice with
Workbench in texture colour: a 3/4 view and a front view, 512 px. Writes <out>/<name>_34.png, <name>_front.png and
<out>/props.json (triangles, size in metres, materials, texture sizes, object count). A contact sheet is assembled
afterwards with PIL by the caller.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
SRC, OUT = args[0], args[1]
os.makedirs(OUT, exist_ok=True)
rows = {}


def frame_and_render(name):
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre, size = (lo + hi) / 2, hi - lo
    radius = max(size.length / 2, 1e-3)
    cam_data = bpy.data.cameras.new('cam')
    cam_data.lens = 50
    cam = bpy.data.objects.new('cam', cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.display.shading.light = 'STUDIO'
    sc.display.shading.color_type = 'TEXTURE'
    sc.display.shading.show_cavity = True
    sc.render.resolution_x = sc.render.resolution_y = 512
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new('w')
    dist = radius / math.tan(math.radians(18)) * 1.15
    for tag, (az, el) in (('34', (40, 20)), ('front', (0, 5))):
        a, e = math.radians(az), math.radians(el)
        # glTF imports Y-up as Z-up: front is -Y in Blender.
        cam.location = centre + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, '%s_%s.png' % (name, tag))
        bpy.ops.render.render(write_still=True)
    return size


for fn in sorted(os.listdir(SRC)):
    if not fn.lower().endswith('.glb'):
        continue
    name = os.path.splitext(fn)[0]
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, fn))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    mats = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
    tex = sorted({'%s %dx%d' % (i.name, i.size[0], i.size[1]) for i in bpy.data.images if i.size[0]})
    size = frame_and_render(name)
    rows[name] = {'file': fn, 'objects': len(meshes), 'triangles': tris,
                  'size_m': [round(size.x, 3), round(size.y, 3), round(size.z, 3)],
                  'materials': mats, 'textures': tex}
    print('PROP', name, tris, [round(v, 2) for v in size], flush=True)

json.dump(rows, open(os.path.join(OUT, 'props.json'), 'w'), indent=1)
print('PROP_SHEET_DONE', len(rows), flush=True)
