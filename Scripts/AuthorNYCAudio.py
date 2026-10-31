"""Import the NYC placeholder audio (owner's free membership sets, converted to WAV) as SoundWaves.

Run via Unreal -ExecutePythonScript with -nullrhi. Creates/updates only assets under
/Game/HoverPrototype/Audio/NYC/. Loops are flagged on the crowd and feeding beds. Receipt under
D:/AFS_Comparisons/NYCSurvival_<date>/audio_receipt.json.
"""
import hashlib, json, time, traceback
from pathlib import Path
import unreal as u

SRC = Path('M:/UnrealProjects/AFS/SourceAssets/Audio')
DEST_ROOT = '/Game/HoverPrototype/Audio/NYC'
GROUPS = {  # source folder -> (dest subfolder, looping)
    'CP_Weapons_20261029/CP_Rifle_1': ('Weapons/Rifle1', False),
    'CP_Weapons_20261029/CP_Rifle_2': ('Weapons/Rifle2', False),
    'CP_Weapons_20261029/CP_Pistol_1': ('Weapons/Pistol1', False),
    'CP_Weapons_20261029/CP_Pistol_2': ('Weapons/Pistol2', False),
    'CP_Weapons_20261029/CP_Shotgun': ('Weapons/Shotgun', False),
    'CP_Weapons_20261029/CP_Sniper': ('Weapons/Sniper', False),
    'SWSW_Zombie_20261029/SWSW_Zombie_Crowd': ('Zombies/Crowd', True),
    'SWSW_Zombie_20261029/SWSW_Zombie_Voice_Pack_Gore_Eating_Flesh_Disgusting_Muddy_Squishy': ('Zombies/Feeding', True),
    'WW2_Weapons_20261029/WW2_MachineGun_Fire': ('Weapons/WW2_MachineGun', False),
    'WW2_Weapons_20261029/WW2_Rifle': ('Weapons/WW2_Rifle', False),
    'Footsteps_20261029/WW2_Walking_Concrete': ('Player/Footsteps/Walk_Concrete', False),
    'Footsteps_20261029/WW2_Walking_Dirt': ('Player/Footsteps/Walk_Dirt', False),
    'Footsteps_20261029/WW2_Walking_Puddle': ('Player/Footsteps/Walk_Puddle', False),
    'Footsteps_20261029/WW2_Run_Concrete': ('Player/Footsteps/Run_Concrete', False),
    'Footsteps_20261029/WW2_Run_Puddle': ('Player/Footsteps/Run_Puddle', False),
    'Vehicles_20261029/CP_Cybercar': ('Vehicles/Cybercar', True),
    'Vehicles_20261029/CP_Cybertruck': ('Vehicles/Cybertruck', True),
    'Gameplay_20261029/Damage_metal_wound': ('Gameplay/HitMetalWound', False),
    'Gameplay_20261029/Bladecutting': ('Gameplay/KatanaCut', False),
    'Gameplay_20261029/Sharpening blade': ('Gameplay/KatanaSharpen', False),
    'Gameplay_20261029/First Aid': ('Gameplay/FirstAid', False),
    'Gameplay_20261029/Item pickup': ('Gameplay/ItemPickup', False),
}
out = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d')); out.mkdir(parents=True, exist_ok=True)
content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
r = {'imported': [], 'updated': [], 'errors': [], 'hashes': {}}
EA = u.EditorAssetLibrary
try:
    tools = u.AssetToolsHelpers.get_asset_tools()
    for folder, (sub, loop) in GROUPS.items():
        dest = f'{DEST_ROOT}/{sub}'
        tasks = []
        for wav in sorted((SRC / folder).glob('*.wav')):
            name = wav.stem
            path = f'{dest}/{name}'
            if EA.does_asset_exist(path):
                r['updated'].append(path)
            else:
                t = u.AssetImportTask()
                t.filename = str(wav); t.destination_path = dest; t.destination_name = name
                t.automated = True; t.replace_existing = True; t.save = True
                tasks.append(t)
        if tasks:
            tools.import_asset_tasks(tasks)
            for t in tasks:
                for p in t.imported_object_paths: r['imported'].append(str(p))
        for wav in sorted((SRC / folder).glob('*.wav')):
            path = f'{dest}/{wav.stem}'
            sw = u.load_asset(path)
            if not sw: r['errors'].append('missing after import: ' + path); continue
            if loop and not sw.get_editor_property('looping'):
                sw.set_editor_property('looping', True); EA.save_loaded_asset(sw, False)
            f = content / (path[len('/Game/'):] + '.uasset')
            if f.exists(): r['hashes'][path] = hashlib.sha256(f.read_bytes()).hexdigest()
except Exception:
    r['errors'].append(traceback.format_exc())
(out / 'audio_receipt.json').write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
u.log_warning(f"NYC_AUDIO imported={len(r['imported'])} updated={len(r['updated'])} errors={len(r['errors'])}")
u.SystemLibrary.quit_editor()
