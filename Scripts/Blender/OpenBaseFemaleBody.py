"""OpenBaseFemaleBody.py - open the Fab "Base Female Body" LP_Quad in an interactive Blender with its PBR set wired
and the viewport in Material Preview, then save as D:/BlendGLB/Base_Female_Body-aa959940/Base_Female_Body.blend.
Run:  blender --python OpenBaseFemaleBody.py   (GUI; never --factory-startup on this machine)
"""
import bpy
import os

SRC = r'D:\BlendGLB\Base_Female_Body-aa959940\fbx\source_extracted\Base_Female_LP_Quad.fbx'
TD = r'D:\BlendGLB\Base_Female_Body-aa959940\additional-files\textures_extracted\Main'
SAVE = r'D:\BlendGLB\Base_Female_Body-aa959940\Base_Female_Body.blend'
SETS = {'body': 'body', 'underwear': 'Underwear', 'eyes1': 'Eyes1'}


def img(name):
    return bpy.data.images.get(name) or bpy.data.images.load(os.path.join(TD, name))


def main():
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
    imported = list(bpy.context.selected_objects)
    col = bpy.data.collections.new('Base Female Body')
    bpy.context.scene.collection.children.link(col)
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    for m in {s.material for o in imported for s in o.material_slots if s.material}:
        key = next((v for k, v in SETS.items() if k in m.name.lower()), None)
        if not key:
            continue
        m.use_nodes = True
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if not bsdf:
            continue

        def tex(suffix, non_color=False, y=0):
            n = nt.nodes.new('ShaderNodeTexImage')
            n.image = img('T_Base_Female_%s_%s.tga' % (key, suffix))
            n.location = (-600, y)
            if non_color:
                n.image.colorspace_settings.name = 'Non-Color'
            return n
        bc = tex('BaseColor', y=300)
        nt.links.new(bc.outputs['Color'], bsdf.inputs['Base Color'])
        nt.nodes.active = bc
        nt.links.new(tex('Roughness', True, 0).outputs['Color'], bsdf.inputs['Roughness'])
        nt.links.new(tex('Metallic', True, -300).outputs['Color'], bsdf.inputs['Metallic'])
        no = tex('Normal', True, -600)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.location = (-300, -600)
        nt.links.new(no.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    bpy.ops.wm.save_as_mainfile(filepath=SAVE)


def frame_views():
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.shading.type = 'MATERIAL'
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            if region:
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_all()
    return None


main()
bpy.app.timers.register(frame_views, first_interval=1.0)
