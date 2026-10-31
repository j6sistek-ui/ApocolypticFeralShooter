"""ImportGrenades.py - import the owner's two Fab GLB grenade models as static meshes (nullrhi, Interchange glTF).

Sources (untrusted downloads, read in place, never executed):
  D:/FABDOWNLOADS/VaultCache/FabLibrary/Sci_Fi_Grenade-aa9f002f/glb/converted/12k_followers_celebration_sci_fi_grenade.glb
      (spherical sci-fi grenade, orange core, 4K textures, 166 MB)
  D:/FABDOWNLOADS/VaultCache/FabLibrary/Scifi_Grenade-b69e231a/glb/converted/scifi_grenade.glb
      (canister grenade with pin + lever, 14 MB)
Targets: /Game/HoverPrototype/Props/Grenades/SM_Grenade_Sphere, /Game/HoverPrototype/Props/Grenades/SM_Grenade_Canister
(+ their materials/textures beside them, textures capped at 2048). Receipt: D:/AFS_Comparisons/Grenades_20261031/import_receipt.json.
Usage: UnrealEditor-Cmd.exe AFS.uproject -ExecutePythonScript="Scripts/ImportGrenades.py" -nullrhi -unattended ...
"""
import json
import os
import time

import unreal as u

SOURCES = [
    ('D:/FABDOWNLOADS/VaultCache/FabLibrary/Sci_Fi_Grenade-aa9f002f/glb/converted/12k_followers_celebration_sci_fi_grenade.glb', 'Grenade_Sphere'),
    ('D:/FABDOWNLOADS/VaultCache/FabLibrary/Scifi_Grenade-b69e231a/glb/converted/scifi_grenade.glb', 'Grenade_Canister'),
    # Owner's Tripo gas canister (2026-10-31 02:10): 32.8k tris, one material (colour + normal + packed metal/roughness),
    # ~100 x 50 x 29 cm lying on its side; already textured, so it needs no Painter pass first.
    # The owner's Tripo "gas canister" turned out to be four horror grenades in one mesh; split (no cleanup) by
    # Scripts/Blender/SplitHorrorGrenades.py on 2026-10-31 into one GLB each (shared 4K textures embedded in every file).
    ('M:/UnrealProjects/AFS/SourceAssets/Grenades/Horror/Grenade_Horror_01_Biohazard.glb', 'Horror_01_Biohazard'),
    ('M:/UnrealProjects/AFS/SourceAssets/Grenades/Horror/Grenade_Horror_02_Cage.glb', 'Horror_02_Cage_BloodBomb'),
    ('M:/UnrealProjects/AFS/SourceAssets/Grenades/Horror/Grenade_Horror_03_Teeth.glb', 'Horror_03_Teeth'),
    ('M:/UnrealProjects/AFS/SourceAssets/Grenades/Horror/Grenade_Horror_04_Skull.glb', 'Horror_04_Skull'),
]
DEST = '/Game/HoverPrototype/Props/Grenades'
# --only=Name[,Name] limits the run (the two grenades wait for the owner's Painter pass; the canister can go in now).
ONLY = [a.split('=', 1)[1] for a in __import__('sys').argv[1:] if a.startswith('--only=')]
if ONLY:
    SOURCES = [s for s in SOURCES if s[1] in ONLY[0].split(',')]
OUT_DIR = 'D:/AFS_Comparisons/Grenades_20261031'
R = {'ok': True, 'errors': [], 'imported': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
EAL = u.EditorAssetLibrary


def log(*a):
    print('GRENADE_IMPORT', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def describe_mesh(path):
    sm = u.load_asset(path)
    if not isinstance(sm, u.StaticMesh):
        return None
    b = sm.get_bounds()
    ext = b.box_extent
    return {'path': path, 'size_cm': [round(ext.x * 2, 2), round(ext.y * 2, 2), round(ext.z * 2, 2)],
            'tris_lod0': sm.get_num_triangles(0), 'materials': [m.material_interface.get_path_name() if m.material_interface else None
                                                               for m in sm.static_materials]}


def main():
    for src, name in SOURCES:
        if not os.path.exists(src):
            err('missing ' + src)
            continue
        folder = '%s/%s' % (DEST, name)
        task = u.AssetImportTask()
        task.filename = src
        task.destination_path = folder
        task.automated = True
        task.replace_existing = True
        task.save = True
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = list(task.imported_object_paths or [])
        log(name, 'imported objects:', len(paths))
        meshes, textures = [], []
        for p in paths:
            a = u.load_asset(p)
            if isinstance(a, u.StaticMesh):
                meshes.append(p)
            elif isinstance(a, u.Texture2D):
                a.set_editor_property('max_texture_size', 2048)
                EAL.save_loaded_asset(a)
                textures.append(p)
        if not meshes:
            # Interchange may import into subfolders; scan the folder.
            for p in EAL.list_assets(folder, True, False):
                a = u.load_asset(p)
                if isinstance(a, u.StaticMesh):
                    meshes.append(p)
                elif isinstance(a, u.Texture2D):
                    a.set_editor_property('max_texture_size', 2048)
                    EAL.save_loaded_asset(a)
                    textures.append(p)
        if not meshes:
            err('no static mesh imported for ' + name)
            continue
        # Rename the first mesh to SM_<name> if it is not already.
        main_mesh = meshes[0]
        wanted = '%s/SM_%s' % (folder, name)
        if main_mesh.split('.')[0] != wanted and not EAL.does_asset_exist(wanted):
            if EAL.rename_asset(main_mesh, wanted):
                main_mesh = wanted
        R['imported'][name] = {'mesh': describe_mesh(main_mesh), 'all_meshes': meshes, 'textures': textures, 'objects': len(paths)}
        log(name, json.dumps(R['imported'][name]['mesh']))


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    err('exception %s\n%s' % (e, traceback.format_exc()))
finally:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_DIR + '/import_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s errors=%d' % (R['ok'], len(R['errors'])))
    u.SystemLibrary.quit_editor()
