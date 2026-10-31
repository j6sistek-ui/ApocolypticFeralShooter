"""BakeSkinToV10.py - bake the Base Female Body pack's skin onto the Female Basemesh V10's OWN UV layout.

V10 has four materials (Head/Torso/Arms/Legs), each with the full 0-1 UV square. Per material this bakes a 2K BaseColor
(emission trick: the pack's BaseColor feeds an Emission shader so metal/shading never darkens it) and a 2K Normal from the
pack body (+ its eye mesh, so V10's eyelids/eyes read the eyeball texture instead of the socket interior) with
Selected-to-Active, Cycles CPU, cage extrusion 1 % and max ray distance 5 % of height, Margin 16.
Outputs: D:/Female Basemesh V10 (1)/PackSkinBake/T_V10_<Mat>_{BaseColor,Normal}.png, V10_PackSkin_Baked.blend,
proof renders under D:/AFS_Comparisons/Basemesh_20261031/V10_Baked/.  Blender 5.2 headless (no factory settings).
"""
import bpy
import json
import os
from mathutils import Vector

V10 = r'D:\Female Basemesh V10 (1)\FemaleBasemeshv10.fbx'
PACK = r'D:\BlendGLB\Base_Female_Body-aa959940\fbx\source_extracted\Base_Female_LP_Quad.fbx'
TD = r'D:\BlendGLB\Base_Female_Body-aa959940\additional-files\textures_extracted\Main'
TEXOUT = r'D:\Female Basemesh V10 (1)\PackSkinBake'
SAVE = r'D:\Female Basemesh V10 (1)\V10_PackSkin_Baked.blend'
PROOF = r'D:\AFS_Comparisons\Basemesh_20261031\V10_Baked'
SIZE = int(os.environ.get('BAKE_SIZE', '2048'))
SAMPLES = int(os.environ.get('BAKE_SAMPLES', '4'))
for d in (TEXOUT, PROOF):
    os.makedirs(d, exist_ok=True)
bpy.ops.wm.read_homefile(use_empty=True)


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def detach_apply(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    mw = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = mw
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


v10 = max((o for o in import_fbx(V10) if o.type == 'MESH'), key=lambda o: len(o.data.polygons))
pack_objs = import_fbx(PACK)
pack = next(o for o in pack_objs if o.type == 'MESH' and o.name.startswith('Body'))
eyes = next((o for o in pack_objs if o.type == 'MESH' and o.name.startswith('Eyes')), None)
sources = [pack] + ([eyes] if eyes else [])
for o in pack_objs:
    if o.type == 'MESH' and o not in sources:
        o.hide_render = True
        o.hide_viewport = True
for o in [v10] + sources:
    detach_apply(o)
lo_v, hi_v = bbox(v10)
lo_p, hi_p = bbox(pack)
s = (hi_v.z - lo_v.z) / (hi_p.z - lo_p.z)
for o in sources:
    o.scale = (s, s, s)
bpy.context.view_layer.update()
lo_p, hi_p = bbox(pack)
shift = Vector(((lo_v.x + hi_v.x) / 2 - (lo_p.x + hi_p.x) / 2, (lo_v.y + hi_v.y) / 2 - (lo_p.y + hi_p.y) / 2, lo_v.z - lo_p.z))
for o in sources:
    o.location += shift
bpy.context.view_layer.update()
height = hi_v.z - lo_v.z

# Source materials: BaseColor -> Emission for the colour pass; a Normal-map-fed Principled for the normal pass.
imgs = {}


def img(name):
    if name not in imgs:
        imgs[name] = bpy.data.images.load(os.path.join(TD, name))
    return imgs[name]


def wire_source(o, setname):
    for slot in o.material_slots:
        m = slot.material
        if not m:
            continue
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new('ShaderNodeOutputMaterial')
        emit = nt.nodes.new('ShaderNodeEmission')
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bc = nt.nodes.new('ShaderNodeTexImage')
        bc.image = img('T_Base_Female_%s_BaseColor.tga' % setname)
        nm_t = nt.nodes.new('ShaderNodeTexImage')
        nm_t.image = img('T_Base_Female_%s_Normal.tga' % setname)
        nm_t.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(bc.outputs['Color'], emit.inputs['Color'])
        nt.links.new(bc.outputs['Color'], bsdf.inputs['Base Color'])
        nt.links.new(nm_t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        m['emit'] = emit.name
        m['bsdf'] = bsdf.name
        m['out'] = out.name


wire_source(pack, 'body')
if eyes:
    wire_source(eyes, 'Eyes1')


def set_pass(mode):
    for o in sources:
        for slot in o.material_slots:
            m = slot.material
            if not m:
                continue
            nt = m.node_tree
            out = nt.nodes[m['out']]
            for l in list(out.inputs['Surface'].links):
                nt.links.remove(l)
            nt.links.new(nt.nodes[m['emit'] if mode == 'color' else m['bsdf']].outputs[0], out.inputs['Surface'])


# Bake settings
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = SAMPLES
sc.render.bake.use_selected_to_active = True
sc.render.bake.cage_extrusion = height * 0.01
sc.render.bake.max_ray_distance = height * 0.05
sc.render.bake.margin = 16
sc.render.bake.use_clear = True
sc.render.bake.use_pass_direct = False
sc.render.bake.use_pass_indirect = False
sc.render.bake.use_pass_color = True
for o in sources:
    o.hide_render = False
baked = {}
# Cycles refuses to bake while ANY material on the active object holds an uninitialised image node (the FBX import's
# dead '.'/'Untitled' references), so reset every V10 material to a bare Principled before the loop.
for slot in v10.material_slots:
    if slot.material:
        slot.material.use_nodes = True
        nt0 = slot.material.node_tree
        nt0.nodes.clear()
        o0 = nt0.nodes.new('ShaderNodeOutputMaterial')
        b0 = nt0.nodes.new('ShaderNodeBsdfPrincipled')
        nt0.links.new(b0.outputs[0], o0.inputs[0])
for im in list(bpy.data.images):
    if not im.has_data and im.users == 0:
        bpy.data.images.remove(im)
for idx, slot in enumerate(v10.material_slots):
    m = slot.material
    if not m:
        continue
    short = m.name.replace('_Mat', '')
    nt = m.node_tree
    out = next(n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL')
    bsdf = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for passname, colorspace, is_normal in (('BaseColor', 'sRGB', False), ('Normal', 'Non-Color', True)):
        image = bpy.data.images.new('T_V10_%s_%s' % (short, passname), SIZE, SIZE, alpha=False)
        image.colorspace_settings.name = colorspace
        node = nt.nodes.new('ShaderNodeTexImage')
        node.image = image
        nt.nodes.active = node
        set_pass('normal' if is_normal else 'color')
        bpy.ops.object.select_all(action='DESELECT')
        for o in sources:
            o.select_set(True)
        v10.select_set(True)
        bpy.context.view_layer.objects.active = v10
        v10.active_material_index = idx
        # bake only this material's faces: select them, limit by material via the active material index + selected faces
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.material_slot_select()
        bpy.ops.object.mode_set(mode='OBJECT')
        sc.render.bake.use_selected_to_active = True
        bpy.ops.object.bake(type='NORMAL' if is_normal else 'EMIT', use_selected_to_active=True, use_clear=True,
                            cage_extrusion=height * 0.01, max_ray_distance=height * 0.05, margin=16, normal_space='TANGENT')
        path = os.path.join(TEXOUT, image.name + '.png')
        image.filepath_raw = path
        image.file_format = 'PNG'
        image.save()
        baked.setdefault(short, {})[passname] = path
        if is_normal:
            nm = nt.nodes.new('ShaderNodeNormalMap')
            nt.links.new(node.outputs['Color'], nm.inputs['Color'])
            nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
        else:
            nt.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
            nt.nodes.active = node
        print('BAKED', image.name, flush=True)
    # keep the BaseColor node active for the Workbench proof
    for n in nt.nodes:
        if n.type == 'TEX_IMAGE' and n.image and 'BaseColor' in n.image.name:
            nt.nodes.active = n
# Proof renders of V10 alone with the baked set
for o in sources:
    o.hide_render = True
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


def shot(name, d, target=None, dist=2.3):
    d = d.normalized()
    t = target or ctr
    cam.location = t + d * rad * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(PROOF, name + '.png')
    bpy.ops.render.render(write_still=True)


shot('v10_front', Vector((0, -1, 0.05)))
shot('v10_back', Vector((0, 1, 0.05)))
shot('v10_head', Vector((0, -1, 0)), Vector((ctr.x, ctr.y, hi_v.z - height * 0.08)), 0.55)
shot('v10_head_34', Vector((0.8, -1, 0.1)), Vector((ctr.x, ctr.y, hi_v.z - height * 0.08)), 0.55)
bpy.ops.wm.save_as_mainfile(filepath=SAVE)
json.dump({'baked': baked, 'scale': s, 'height': height}, open(os.path.join(PROOF, 'bake_report.json'), 'w'), indent=1)
print('BAKE_DONE', json.dumps(baked), flush=True)
