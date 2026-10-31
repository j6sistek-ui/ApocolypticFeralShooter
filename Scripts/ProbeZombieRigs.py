"""ProbeZombieRigs.py - can the zombie packs play on the NYC roster skeletons (2026-10-31).

  UnrealEditor-Cmd.exe <AFS.uproject> -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProbeZombieRigs.py

Read-only. Writes D:/AFS_Comparisons/ZombieDiversity_20261031/rigs.json:
  skeletons  bone count, the first bones, compatible skeletons, and how many bones of each source pack skeleton
             exist by name in each roster skeleton
  montages   slot names, length, root motion and notifies of the montages the roster uses and could use
  classes    rotation flags on the NYC zombie class default object and the vendor zombie blueprint
"""
import json
import os
import traceback

import unreal as u

OUT = 'D:/AFS_Comparisons/ZombieDiversity_20261031/rigs.json'
R = {'errors': [], 'skeletons': {}, 'overlap': {}, 'montages': {}, 'sequences': {}, 'classes': {}}
L = u.EditorAssetLibrary

ROSTER = {
    'Standard01': '/Game/HoverPrototype/ZombieEngine/Variants/Standard01/SK_Standard01_Skeleton',
    'Standard02': '/Game/HoverPrototype/ZombieEngine/Variants/Standard02/SK_Standard02_Skeleton',
    'Standard03': '/Game/HoverPrototype/ZombieEngine/Variants/Standard03/SK_Standard03_Skeleton',
    'Standard04': '/Game/HoverPrototype/ZombieEngine/Variants/Standard04/SK_Standard04_Skeleton',
    'Brute': '/Game/HoverPrototype/ZombieEngine/Variants/Brute/SK_Brute_Skeleton',
    'Kid': '/Game/HoverPrototype/ZombieEngine/Variants/Kid/SK_Kid_Skeleton',
}
SOURCES = {
    'ZESP': '/Game/ZESP/Demo/Characters/Mannequins/Meshes/SK_Mannequin',
    'ZAP_UE5': '/Game/ZombieAnimationPack/Demo/EpicContent/Mannequin_UE5/Meshes/SKEL_Mannequin',
    'ZAP_UE4': '/Game/ZombieAnimationPack/Demo/EpicContent/Mannequin_UE4/Mesh/SKEL_UE4_Mannequin',
    'Etherion': '/Game/Zombie/Meshes/SKEL_Zombie',
    'Feral': '/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton',
}
MONTAGES = [
    '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/AM_Attack_01',
    '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/AM_Death',
    '/Game/HoverPrototype/ZombieEngine/Variants/Brute/AM_Brute_Stomp',
    '/Game/HoverPrototype/NYC/Zombies/AM_NYC_Kid_Pounce',
    '/Game/HoverPrototype/ZombieEngine/Variants/Lakeside/Horror/Variety/AM_Attack_A',
    '/Game/Zombie/Animations/Anim_Zombie_Attack_Montage',
    '/Game/Zombie/Animations/Anim_Zombie_Attack_MontageUpper',
    '/Game/Zombie/Animations/Anim_Zombie_Attack_HighBashLoop_Montage',
]
SEQUENCES = [
    '/Game/ZombieAnimationPack/Animations/Mannequin_UE5/anim_Walk_A',
    '/Game/ZombieAnimationPack/Animations/Mannequin_UE5/anim_Attack_A',
    '/Game/ZombieAnimationPack/Animations/Mannequin_UE5/anim_Burst_A',
    '/Game/Zombie/Animations/Anim_Zombie_Walk',
    '/Game/Zombie/Animations/Anim_Zombie_Run',
    '/Game/Zombie/Animations/Anim_Zombie_Roar',
    '/Game/Zombie/Animations/Anim_Zombie_KickForward',
    '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/AS_Walking_Anim',
]


def bones_of(skel):
    try:
        return [str(n) for n in skel.get_editor_property('bone_tree')] if False else None
    except Exception:  # noqa: BLE001
        return None


def skel_bones(skel_path):
    """Bone names through a mesh that uses the skeleton (the reference skeleton is not exposed on USkeleton)."""
    skel = L.load_asset(skel_path)
    if not skel:
        return None, None
    mesh = skel.get_editor_property('preview_mesh') if 'preview_mesh' in (type(skel).__doc__ or '') else None
    if not mesh:
        ar = u.AssetRegistryHelpers.get_asset_registry()
        flt = u.ARFilter(class_paths=[u.TopLevelAssetPath('/Script/Engine', 'SkeletalMesh')])
        for a in ar.get_assets(flt):
            tag = str(a.get_tag_value('Skeleton') or '')
            if skel_path in tag:
                mesh = a.get_asset()
                break
    names = []
    if mesh:
        n = u.SkeletalMeshEditorSubsystem if False else None
        try:
            ref = mesh.get_editor_property('skeleton')
        except Exception:  # noqa: BLE001
            ref = None
        i = 0
        while True:
            try:
                name = mesh.get_bone_name(i) if hasattr(mesh, 'get_bone_name') else None
            except Exception:  # noqa: BLE001
                name = None
            if not name or str(name) == 'None':
                break
            names.append(str(name))
            i += 1
    return skel, (mesh, names)


try:
    names_by = {}
    for label, path in list(ROSTER.items()) + list(SOURCES.items()):
        skel, (mesh, names) = skel_bones(path)
        row = {'path': path, 'mesh': mesh.get_path_name() if mesh else None, 'bone_count': len(names),
               'bones_head': names[:40]}
        if skel:
            try:
                row['compatible'] = [s.get_path_name() for s in skel.get_editor_property('compatible_skeletons')]
            except Exception as e:  # noqa: BLE001
                row['compatible'] = 'ERR %s' % e
        R['skeletons'][label] = row
        names_by[label] = set(names)
    for r in ROSTER:
        R['overlap'][r] = {s: '%d/%d' % (len(names_by[r] & names_by[s]), len(names_by[s])) for s in SOURCES}
        R['overlap'][r]['missing_from_ZAP_UE5'] = sorted(names_by['ZAP_UE5'] - names_by[r])[:30]
        R['overlap'][r]['missing_from_Etherion'] = sorted(names_by['Etherion'] - names_by[r])[:30]
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

try:
    for p in MONTAGES:
        m = L.load_asset(p)
        if not m:
            R['montages'][p] = None
            continue
        row = {'length': round(m.get_editor_property('sequence_length') if 'sequence_length' in (type(m).__doc__ or '')
                               else m.get_play_length(), 3)}
        try:
            row['slots'] = [str(t.get_editor_property('slot_name')) for t in m.get_editor_property('slot_anim_tracks')]
        except Exception as e:  # noqa: BLE001
            row['slots'] = 'ERR %s' % e
        try:
            row['skeleton'] = m.get_editor_property('skeleton').get_path_name()
        except Exception:  # noqa: BLE001
            pass
        try:
            row['notifies'] = [(str(n.get_editor_property('notify_name')), round(n.get_editor_property('trigger_time_offset'), 3)
                                if False else None) for n in m.get_editor_property('notifies')]
        except Exception as e:  # noqa: BLE001
            row['notifies'] = 'ERR %s' % e
        R['montages'][p] = row
    for p in SEQUENCES:
        a = L.load_asset(p)
        if not a:
            R['sequences'][p] = None
            continue
        R['sequences'][p] = {'length': round(a.get_play_length(), 3),
                             'root_motion': a.get_editor_property('enable_root_motion'),
                             'skeleton': a.get_editor_property('skeleton').get_path_name()}
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

try:
    for label, cls_path in (('AHoverNYCZombie', '/Script/HoverFlight.HoverNYCZombie'),
                            ('AHoverCyberZombie', '/Script/HoverFlight.HoverCyberZombie')):
        cls = u.load_class(None, cls_path)
        cdo = u.get_default_object(cls)
        mv = cdo.get_editor_property('character_movement')
        R['classes'][label] = {
            'use_controller_rotation_yaw': cdo.get_editor_property('use_controller_rotation_yaw'),
            'orient_rotation_to_movement': mv.get_editor_property('orient_rotation_to_movement'),
            'use_controller_desired_rotation': mv.get_editor_property('use_controller_desired_rotation'),
            'rotation_rate': str(mv.get_editor_property('rotation_rate')),
            'anim_class': str(cdo.get_editor_property('mesh').get_editor_property('anim_class')),
            'ai_class': str(cdo.get_editor_property('ai_controller_class')),
        }
    for label, cls_path in (('AHoverNYCZombieAI', '/Script/HoverFlight.HoverNYCZombieAI'),):
        cdo = u.get_default_object(u.load_class(None, cls_path))
        row = {}
        for prop in ('set_control_rotation_from_pawn_orientation', 'allow_strafe', 'stop_ai_logic_on_unposses'):
            try:
                row[prop] = cdo.get_editor_property(prop)
            except Exception as e:  # noqa: BLE001
                row[prop] = 'ERR %s' % str(e)[:80]
        R['classes'][label] = row
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(R, open(OUT, 'w'), indent=1, default=str)
print('ZOMBIE_RIGS_DONE errors=%d' % len(R['errors']), flush=True)
u.SystemLibrary.quit_editor()
