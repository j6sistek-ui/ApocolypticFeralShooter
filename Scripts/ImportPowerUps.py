"""ImportPowerUps.py - import the cleaned Tripo power-up GLBs as static meshes (nullrhi, Interchange glTF).

Source: M:/UnrealProjects/AFS/SourceAssets/PowerUps/Clean/PU_NN_Name.glb (written by Scripts/Blender/CleanPowerUps.py:
one object, pivot at bottom centre, readable front on Blender -Y, 45 cm hand items / 60 cm crates and vest,
one material with BaseColor + ORM + Normal).
Target: /Game/HoverPrototype/PowerUps/Meshes/<Name>/SM_<Name> plus its material and textures beside it
(textures capped at 2048, never edits anything outside that folder).

Which models: a list. Pass it as the env var POWERUPS="PU_06_Medkit,PU_17_Nuke" (or as script arguments,
-ExecutePythonScript="Scripts/ImportPowerUps.py PU_06_Medkit PU_17_Nuke"). No list = all 15 in the Clean folder.
Receipt: D:/AFS_Comparisons/PowerUps_20261031/Styles/import_receipt.json (bounds, min/max, triangles, materials,
texture sizes) so facing and scale can be checked without opening the editor.
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput -ExecutePythonScript=<this>
"""
import glob
import json
import os
import sys
import time

import unreal as u

SRC_DIR = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/Clean'
DEST = '/Game/HoverPrototype/PowerUps/Meshes'
OUT_DIR = os.environ.get('POWERUP_IMPORT_OUT', 'D:/AFS_Comparisons/PowerUps_20261031/Styles')
MAX_TEX = 2048

wanted = [a for a in sys.argv[1:] if a.startswith('PU_')]
if not wanted and os.environ.get('POWERUPS'):
    wanted = [s.strip() for s in os.environ['POWERUPS'].split(',') if s.strip()]
ALL = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(SRC_DIR + '/PU_*.glb'))
NAMES = wanted or ALL
R = {'ok': True, 'errors': [], 'imported': {}, 'requested': NAMES, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
EAL = u.EditorAssetLibrary


def log(*a):
    print('POWERUP_IMPORT', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def describe_mesh(path):
    sm = u.load_asset(path)
    if not isinstance(sm, u.StaticMesh):
        return None
    box = sm.get_bounding_box()
    mn, mx = box.min, box.max
    return {'path': sm.get_path_name(),
            'size_cm': [round(mx.x - mn.x, 2), round(mx.y - mn.y, 2), round(mx.z - mn.z, 2)],
            'min': [round(mn.x, 2), round(mn.y, 2), round(mn.z, 2)],
            'max': [round(mx.x, 2), round(mx.y, 2), round(mx.z, 2)],
            'tris_lod0': sm.get_num_triangles(0),
            'materials': [m.material_interface.get_path_name() if m.material_interface else None for m in sm.static_materials]}


def import_one(name):
    src = '%s/%s.glb' % (SRC_DIR, name)
    if not os.path.exists(src):
        err('missing ' + src)
        return
    folder = '%s/%s' % (DEST, name)
    task = u.AssetImportTask()
    task.filename = src
    task.destination_path = folder
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.imported_object_paths or [])
    # Interchange may put things in subfolders: scan the whole folder as well.
    paths = sorted(set(p.split('.')[0] for p in paths) | set(p.split('.')[0] for p in EAL.list_assets(folder, True, False)))
    meshes, textures, materials = [], [], []
    for p in paths:
        a = u.load_asset(p)
        if isinstance(a, u.StaticMesh):
            meshes.append(p)
        elif isinstance(a, u.Texture2D):
            if a.get_editor_property('max_texture_size') != MAX_TEX:
                a.set_editor_property('max_texture_size', MAX_TEX)
                EAL.save_loaded_asset(a)
            textures.append({'path': p, 'size': [a.blueprint_get_size_x(), a.blueprint_get_size_y()],
                             'srgb': a.get_editor_property('srgb')})
        elif isinstance(a, u.MaterialInterface):
            materials.append(p)
    if not meshes:
        err('no static mesh imported for ' + name)
        return
    main_mesh = meshes[0].split('.')[0]
    target = '%s/SM_%s' % (folder, name)
    if main_mesh != target:
        if EAL.does_asset_exist(target):
            EAL.delete_asset(target)
        if EAL.rename_asset(main_mesh, target):
            main_mesh = target
    sm = u.load_asset(main_mesh)
    # Pickups are not walls: simple box collision is enough, and Nanite stays off (5k-tri props, translucent overlays).
    EAL.save_loaded_asset(sm)
    R['imported'][name] = {'mesh': describe_mesh(main_mesh), 'textures': textures, 'materials': materials,
                           'objects': len(paths)}
    log(name, json.dumps(R['imported'][name]['mesh']))


def main():
    log('requested', NAMES)
    for n in NAMES:
        try:
            import_one(n)
        except Exception as e:  # noqa: BLE001
            import traceback
            err('%s: %s\n%s' % (n, e, traceback.format_exc()))


try:
    main()
finally:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_DIR + '/import_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s imported=%d errors=%d' % (R['ok'], len(R['imported']), len(R['errors'])))
    u.SystemLibrary.quit_editor()
