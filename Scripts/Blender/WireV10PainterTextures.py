"""WireV10PainterTextures.py - put the owner's Substance Painter export for the Female Basemesh V10 on the mesh the
way Painter shows it: one Principled BSDF per material (Head/Torso/Arms/Legs) with BaseColor (sRGB), Roughness,
Metallic and Normal (Non-Color, DirectX-style green flip optional), Displacement ignored for the viewport, Alpha off.
Renders proofs with Eevee (not Workbench, which ignores roughness/normal) under a neutral studio HDRI-less 3-point
light, so the look matches Painter's lit viewport, and saves V10_PainterTextures.blend beside the V10 files.
Usage: blender -b --python WireV10PainterTextures.py -- [--flip-green] [--src <folder>]
"""
import bpy
import os
import sys

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FLIP = '--flip-green' in argv
SRC = argv[argv.index('--src') + 1] if '--src' in argv else r'C:\Users\j6sis\OneDrive\Desktop'
V10 = r'D:\Female Basemesh V10 (1)\FemaleBasemeshv10.fbx'
SAVE = r'D:\Female Basemesh V10 (1)\V10_PainterTextures.blend'
PROOF = r'D:\AFS_Comparisons\Basemesh_20261031\PainterTextures'
os.makedirs(PROOF, exist_ok=True)
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.import_scene.fbx(filepath=V10)
o = max((x for x in bpy.data.objects if x.type == 'MESH'), key=lambda x: len(x.data.polygons))
bpy.context.view_layer.objects.active = o
o.select_set(True)
mw = o.matrix_world.copy()
o.parent = None
o.matrix_world = mw
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
report = {}
for slot in o.material_slots:
    m = slot.material
    if not m:
        continue
    base = m.name  # Head_Mat etc. = the Painter texture-set names
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    found = {}

    def tex(suffix, non_color, y):
        p = os.path.join(SRC, '%s_%s.png' % (base, suffix))
        if not os.path.exists(p):
            found[suffix] = None
            return None
        im = bpy.data.images.get(os.path.basename(p)) or bpy.data.images.load(p)
        if non_color:
            im.colorspace_settings.name = 'Non-Color'
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = im
        n.location = (-700, y)
        found[suffix] = os.path.basename(p)
        return n
    bc = tex('BaseColor', False, 400)
    if bc:
        nt.links.new(bc.outputs['Color'], bsdf.inputs['Base Color'])
        nt.nodes.active = bc
    ro = tex('Roughness', True, 100)
    if ro:
        nt.links.new(ro.outputs['Color'], bsdf.inputs['Roughness'])
    me = tex('Metallic', True, -200)
    if me:
        nt.links.new(me.outputs['Color'], bsdf.inputs['Metallic'])
    no = tex('Normal', True, -500)
    if no:
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.location = (-350, -500)
        if FLIP:
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'
            inv.inputs[0].default_value = 1.0
            comb = nt.nodes.new('ShaderNodeCombineColor')
            nt.links.new(no.outputs['Color'], sep.inputs['Color'])
            nt.links.new(sep.outputs['Red'], comb.inputs['Red'])
            nt.links.new(sep.outputs['Green'], inv.inputs[1])
            nt.links.new(inv.outputs[0], comb.inputs['Green'])
            nt.links.new(sep.outputs['Blue'], comb.inputs['Blue'])
            nt.links.new(comb.outputs['Color'], nm.inputs['Color'])
        else:
            nt.links.new(no.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    m.blend_method = 'OPAQUE'
    report[base] = found
# 3-point light + Eevee proofs
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE' if hasattr(bpy.types, 'SceneEEVEE') else 'BLENDER_EEVEE_NEXT'
try:
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
except TypeError:
    sc.render.engine = 'BLENDER_EEVEE'
w = bpy.data.worlds.new('W')
sc.world = w
w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.6, 0.6, 0.65, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 0.6
from mathutils import Vector
pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (lo + hi) / 2
rad = (hi - lo).length / 2
for name, loc, energy in (('key', (1.5, -2.5, 2.6), 600), ('fill', (-2.5, -2.0, 1.6), 250), ('rim', (0.5, 2.5, 2.2), 400)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = 2.0
    lo_ = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo_)
    lo_.location = Vector(loc)
    lo_.rotation_euler = (ctr - lo_.location).to_track_quat('-Z', 'Y').to_euler()
cam_data = bpy.data.cameras.new('C')
cam = bpy.data.objects.new('C', cam_data)
sc.collection.objects.link(cam)
sc.camera = cam
cam_data.lens = 60
sc.render.resolution_x, sc.render.resolution_y = 900, 1200
sc.view_settings.view_transform = 'Standard'


def shot(name, d, target=None, dist=2.3):
    d = d.normalized()
    t = target or ctr
    cam.location = t + d * rad * dist
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(PROOF, name + ('_flip' if FLIP else '') + '.png')
    bpy.ops.render.render(write_still=True)


shot('front', Vector((0, -1, 0.05)))
shot('back', Vector((0, 1, 0.05)))
shot('head', Vector((0, -1, 0)), Vector((ctr.x, ctr.y, hi.z - (hi.z - lo.z) * 0.08)), 0.55)
shot('head_34', Vector((0.8, -1, 0.1)), Vector((ctr.x, ctr.y, hi.z - (hi.z - lo.z) * 0.08)), 0.55)
bpy.ops.wm.save_as_mainfile(filepath=SAVE)
import json
print('WIRE_DONE', json.dumps({'textures': report, 'flip_green': FLIP, 'engine': sc.render.engine}), flush=True)
