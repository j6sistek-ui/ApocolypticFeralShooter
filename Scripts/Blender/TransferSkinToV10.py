"""TransferSkinToV10.py - give the Female Basemesh V10 the Base Female Body pack's skin textures.

The pack's TGAs are laid out for the pack body's own UV atlas, so they cannot be assigned to V10 directly (V10 has four
overlapping 0-1 UV squares and no textures). Instead: load both bodies, scale/align the pack body onto V10 (same height,
same floor, same centre), transfer the pack body's UVs onto V10 by nearest-face interpolation (Data Transfer modifier),
give V10 one material wired to the pack's 4K set, render proofs, save D:/Female Basemesh V10/V10_PackSkin.blend.
Where the bodies differ (arm angle, hand pose, face proportions) the nearest-surface mapping is approximate: judge the
renders. Blender 5.2 headless:  blender -b --python TransferSkinToV10.py
"""
import bpy
import os
from mathutils import Vector

V10 = r'D:\Female Basemesh V10 (1)\FemaleBasemeshv10.fbx'
PACK = r'D:\BlendGLB\Base_Female_Body-aa959940\fbx\source_extracted\Base_Female_LP_Quad.fbx'
TD = r'D:\BlendGLB\Base_Female_Body-aa959940\additional-files\textures_extracted\Main'
OUT = r'D:\AFS_Comparisons\Basemesh_20261031\V10_PackSkin'
SAVE = r'D:\Female Basemesh V10 (1)\V10_PackSkin.blend'
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_homefile(use_empty=True)


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


v10_objs = import_fbx(V10)
v10 = max((o for o in v10_objs if o.type == 'MESH'), key=lambda o: len(o.data.polygons))
pack_objs = import_fbx(PACK)
pack = next(o for o in pack_objs if o.type == 'MESH' and o.name.startswith('Body'))
for o in pack_objs:
    if o is not pack and o.type == 'MESH':
        o.hide_render = True
        o.hide_viewport = True
# apply transforms so the bounds are honest
for o in (v10, pack):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    mw = o.matrix_world.copy()  # keep the FBX parent empty's rotation/scale when detaching
    o.parent = None
    o.matrix_world = mw
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
lo_v, hi_v = bbox(v10)
lo_p, hi_p = bbox(pack)
# scale the pack body to V10's height, then align floor and horizontal centre
s = (hi_v.z - lo_v.z) / (hi_p.z - lo_p.z)
pack.scale = (s, s, s)
bpy.context.view_layer.update()
lo_p, hi_p = bbox(pack)
pack.location += Vector(((lo_v.x + hi_v.x) / 2 - (lo_p.x + hi_p.x) / 2, (lo_v.y + hi_v.y) / 2 - (lo_p.y + hi_p.y) / 2, lo_v.z - lo_p.z))
bpy.context.view_layer.update()
lo_p, hi_p = bbox(pack)
report = {'v10_dims': [round(d, 3) for d in v10.dimensions], 'pack_scale': round(s, 4), 'pack_dims_after': [round(d, 3) for d in pack.dimensions],
          'v10_bbox': [[round(c, 3) for c in lo_v], [round(c, 3) for c in hi_v]], 'pack_bbox': [[round(c, 3) for c in lo_p], [round(c, 3) for c in hi_p]]}
# transfer UVs: pack -> v10 by nearest face interpolated
uv = v10.data.uv_layers.new(name='map1')  # same name as the pack's layer: the modifier matches destination by NAME
v10.data.uv_layers.active = uv
uv.active_render = True
mod = v10.modifiers.new('PackUV', 'DATA_TRANSFER')
mod.object = pack
mod.use_loop_data = True
mod.data_types_loops = {'UV'}
mod.loop_mapping = 'POLYINTERP_NEAREST'
mod.layers_uv_select_src = 'map1'
mod.layers_uv_select_dst = 'NAME'
bpy.ops.object.select_all(action='DESELECT')
v10.select_set(True)
bpy.context.view_layer.objects.active = v10
bpy.ops.object.modifier_apply(modifier='PackUV')
# one material on V10 wired to the pack's body set
mat = bpy.data.materials.new('V10_PackSkin')
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')


def tex(suffix, non_color=False, y=0):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(os.path.join(TD, 'T_Base_Female_body_%s.tga' % suffix))
    n.location = (-700, y)
    if non_color:
        n.image.colorspace_settings.name = 'Non-Color'
    return n


bc = tex('BaseColor', y=300)
nt.links.new(bc.outputs['Color'], bsdf.inputs['Base Color'])
nt.nodes.active = bc
nt.links.new(tex('Roughness', True, 0).outputs['Color'], bsdf.inputs['Roughness'])
no = tex('Normal', True, -600)
nm = nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(no.outputs['Color'], nm.inputs['Color'])
nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
v10.data.materials.clear()
v10.data.materials.append(mat)
# the pack body also carries the real texture for the side-by-side
pm = pack.data.materials[0] if pack.data.materials else None
if pm:
    pm.use_nodes = True
    for n in [n for n in pm.node_tree.nodes if n.type == 'TEX_IMAGE']:
        pm.node_tree.nodes.remove(n)
    pb = next((n for n in pm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if pb:
        n = pm.node_tree.nodes.new('ShaderNodeTexImage')
        n.image = bc.image
        pm.node_tree.links.new(n.outputs['Color'], pb.inputs['Base Color'])
        pm.node_tree.nodes.active = n
# renders: V10 alone (front, head, back), then pack beside it for reference
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'STUDIO'
sc.display.shading.color_type = 'TEXTURE'
sc.render.resolution_x, sc.render.resolution_y = 900, 1200
cam_data = bpy.data.cameras.new('C')
cam = bpy.data.objects.new('C', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
cam_data.lens = 60
ctr = (lo_v + hi_v) / 2
rad = (hi_v - lo_v).length / 2
pack.hide_render = True


def shot(name, d, target=None, dist=2.3):
    d = d.normalized()
    t = target or ctr
    cam.location = t + d * rad * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(OUT, name + '.png')
    bpy.ops.render.render(write_still=True)


shot('v10_front', Vector((0, -1, 0.05)))
shot('v10_back', Vector((0, 1, 0.05)))
head = Vector((ctr.x, ctr.y, hi_v.z - (hi_v.z - lo_v.z) * 0.08))
shot('v10_head', Vector((0, -1, 0)), head, 0.55)
shot('v10_hands', Vector((0, -1, 0.2)), Vector((ctr.x, ctr.y, lo_v.z + (hi_v.z - lo_v.z) * 0.45)), 1.1)
pack.hide_render = False
pack.location.x += (hi_v.x - lo_v.x) * 1.1
shot('both_front', Vector((0, -1, 0.05)), ctr + Vector(((hi_v.x - lo_v.x) * 0.55, 0, 0)), 3.0)
bpy.ops.wm.save_as_mainfile(filepath=SAVE)
import json
json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
print('TRANSFER_DONE', json.dumps(report), flush=True)
