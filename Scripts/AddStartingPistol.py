"""AddStartingPistol.py - give NYC Survival a starting sidearm (owner 2026-10-31: "Y to switch weapons, have the
pistol on hand").

  UnrealEditor-Cmd.exe <AFS.uproject> -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/AddStartingPistol.py

1. Owned definition /Game/HoverPrototype/NYC/Weapons/DA_NYC_Pistol: a duplicate of the vendor DA_Weapon_Pistol_001
   whose WeaponActorClass is AHoverCyberRifle, so the EM_08 revolver rig (hand-tracked reload, feel tier) plays in
   real play instead of the vendor BP_Weapon_Pistol_001 actor.
2. DA_HoverPilot.GunRigs: exact key DA_NYC_Pistol -> DA_GunRig_EM08 (the normalised DA_Weapon_Pistol entry stays).
3. DA_NYCWaves StartingEquipment through UHoverAuthoring.ConfigureCityStartingGear(270, 2, with_sidearm=True):
   Ballista slot 1, pistol slot 2 (+ DA_AMMO_Pistol), grenades keep their slot.
Receipt D:/AFS_Comparisons/Playtest_20261031/starting_pistol.json. Re-runnable.
"""
import json
import os

import unreal as u

L = u.EditorAssetLibrary
VENDOR = '/Game/ZESP/ZE/Data/Weapons/DA_Weapon_Pistol_001'
OWNED_DIR = '/Game/HoverPrototype/NYC/Weapons'
OWNED = OWNED_DIR + '/DA_NYC_Pistol'
WAVES = '/Game/HoverPrototype/NYC/DA_NYCWaves'
PILOT = '/Game/HoverPrototype/DA_HoverPilot'
RIG = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08'
OUT = 'D:/AFS_Comparisons/Playtest_20261031/starting_pistol.json'
R = {'errors': [], 'notes': []}
try:
    if not L.does_directory_exist(OWNED_DIR):
        L.make_directory(OWNED_DIR)
    if not L.does_asset_exist(OWNED):
        assert L.duplicate_asset(VENDOR, OWNED), 'duplicate failed'
        R['notes'].append('duplicated ' + VENDOR)
    d = L.load_asset(OWNED)
    d.set_editor_property('weapon_actor_class', u.HoverCyberRifle)
    L.save_loaded_asset(d, False)
    R['pistol'] = {'path': OWNED, 'actor_class': str(d.get_editor_property('weapon_actor_class'))}
    pilot = L.load_asset(PILOT)
    rig = L.load_asset(RIG)
    assert pilot and rig, 'DA_HoverPilot or DA_GunRig_EM08 missing'
    stored = u.HoverAuthoring.bind_gun_rig(pilot, u.Name('DA_NYC_Pistol'), rig, True)
    L.save_loaded_asset(pilot, False)
    R['rig_binding'] = str(stored)
    waves = L.load_asset(WAVES)
    assert waves, 'DA_NYCWaves missing'
    ok = u.HoverAuthoring.configure_city_starting_gear(waves, 270, 2, True)
    L.save_loaded_asset(waves, False)
    gear = waves.get_editor_property('starting_equipment')
    R['gear'] = {'ok': ok,
                 'weapons': [(str(w.get_editor_property('weapon_definition').get_name()), w.get_editor_property('quickbar_slot'))
                             for w in gear.get_editor_property('starting_weapons')],
                 'ammo': [str(a.get_name()) for a in gear.get_editor_property('starting_ammo')],
                 'grenade_slot': gear.get_editor_property('grenade_quickbar_slot'),
                 'grenades': gear.get_editor_property('grenade_count')}
except Exception as e:  # noqa: BLE001
    import traceback
    R['errors'].append(traceback.format_exc())
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(R, open(OUT, 'w'), indent=1, default=str)
print('STARTING_PISTOL_DONE', json.dumps(R, default=str)[:900], flush=True)
u.SystemLibrary.quit_editor()
