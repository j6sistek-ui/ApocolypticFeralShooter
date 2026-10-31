"""Export the perk-machine base meshes and their textures to SourceAssets for Substance Painter.

Run via Unreal -ExecutePythonScript with -RenderOffscreen. Reads only; writes FBX/PNG under
SourceAssets/PerkMachine and a receipt JSON. No assets are modified or saved.
"""
import json, os, traceback
import unreal as u

out = os.path.join(u.Paths.convert_relative_path_to_full(u.Paths.project_dir()), 'SourceAssets', 'PerkMachine')
os.makedirs(out, exist_ok=True)
receipt = {'meshes': {}, 'textures': {}, 'errors': []}
MESHES = ['/Game/CyberPunkBarAssetSet01/StaticMeshes/SM_VendingMachine01',
          '/Game/CyberPunkBarAssetSet01/StaticMeshes/SM_BarVendingMAchine01']
TEXTURES = ['/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine01_Base',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine01_Normal',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine01_ORM',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine01_Emissive',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine0002Mat_Base',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine0002Mat_Normal',
            '/Game/CyberPunkBarAssetSet01/Textures/T_VendingMachine0002Mat_orm']


def mesh_info(m):
    b = m.get_bounds()
    info = {'tris_lod0': m.get_num_triangles(0), 'verts_lod0': m.get_num_vertices(0), 'lods': m.get_num_lods(),
            'uv_channels': m.get_num_uv_channels(0), 'extent_cm': [round(v, 1) for v in (b.box_extent.x * 2, b.box_extent.y * 2, b.box_extent.z * 2)],
            'origin_cm': [round(v, 1) for v in (b.origin.x, b.origin.y, b.origin.z)],
            'materials': [(s.material_slot_name and str(s.material_slot_name), s.material_interface.get_path_name() if s.material_interface else None) for s in m.static_materials],
            'sockets': [str(s.socket_name) for s in m.sockets]}
    return info


tasks = []
try:
    for p in MESHES:
        m = u.load_asset(p)
        assert m, p
        receipt['meshes'][p] = mesh_info(m)
        t = u.AssetExportTask()
        t.object = m
        t.filename = os.path.join(out, p.split('/')[-1] + '.fbx')
        t.exporter = u.StaticMeshExporterFBX()
        opt = u.FbxExportOption()
        opt.collision = False
        opt.vertex_color = False
        opt.level_of_detail = False
        opt.ascii = False
        t.options = opt
        t.automated = True
        t.replace_identical = True
        t.prompt = False
        tasks.append(t)
    for p in TEXTURES:
        tx = u.load_asset(p)
        assert tx, p
        receipt['textures'][p] = {'size': [tx.blueprint_get_size_x(), tx.blueprint_get_size_y()], 'srgb': tx.srgb,
                                  'compression': str(tx.compression_settings), 'source_format': str(tx.get_editor_property('source') and 'has_source')}
        t = u.AssetExportTask()
        t.object = tx
        t.filename = os.path.join(out, p.split('/')[-1] + '.png')
        t.exporter = u.TextureExporterPNG()
        t.automated = True
        t.replace_identical = True
        t.prompt = False
        tasks.append(t)
    ok = u.Exporter.run_asset_export_tasks(tasks)
    receipt['run_ok'] = bool(ok)
    receipt['files'] = {f: os.path.getsize(os.path.join(out, f)) for f in sorted(os.listdir(out))}
except Exception:
    receipt['errors'].append(traceback.format_exc())
with open(os.path.join(out, 'export_receipt.json'), 'w', encoding='utf-8') as fh:
    json.dump(receipt, fh, indent=1, default=str)
u.log_warning('ExportVendingMachine receipt: ' + json.dumps(receipt, default=str)[:4000])
