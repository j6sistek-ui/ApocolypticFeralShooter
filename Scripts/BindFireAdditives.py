"""BindFireAdditives.py - the stance fire reactions as frame-0 additives for the rigged guns (design A1), CPU only.

Why: with a rigged gun the body used to play the feel tier's TPFireAction (MM_Rifle_Fire) as a montage on the CLS
driver every 4th shot; that path drops the aim layer and the support IK, so the left hand followed the retargeted
RIFLE fire clip to a handguard's distance, ahead of a 30 cm SMG's or a revolver's muzzle (owner screenshots
2026-10-30). The proxy now plays the stance's own fire reaction as a LOCAL-SPACE ADDITIVE over the stance aim pose,
before the layered blend and the support IK, so both hands ride the recoil with the gun. This script makes the assets:
  1. duplicates /Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/MM_Rifle_Fire  -> /Game/HoverPrototype/Animations/MA_Rifle_Fire_Add
                /Game/CLS/Example/SetupYourHeroExample/Anims/Pistol/MM_Pistol_Fire -> /Game/HoverPrototype/Animations/MA_Pistol_Fire_Add
     (same duplicate_asset pattern as BindPistolAim.py; the skeleton stays the CLS mannequin's, the runtime bone-name
     remap plays it on Vexa like the aim poses);
  2. HoverAuthoring.make_frame_additive(copy, 0): AdditiveAnimType AAT_LocalSpaceBase, RefPoseType ABPT_AnimFrame,
     RefFrameIndex 0 (its own first frame is the base, so the additive is exactly the authored recoil and nothing else),
     saved, read back, and UAnimSequence::IsValidAdditive() asserted true on the reloaded asset;
  3. DA_HoverPilot.RifleFireAdd / PistolFireAdd bound to the copies (saved, read back).

Receipt: D:/AFS_Comparisons/GunRigs_20261029/fire_additives.json
Run:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/BindFireAdditives.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/fire_additives.log"
"""
import json
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'fire_additives.json'
DST_DIR = '/Game/HoverPrototype/Animations'
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'
CLIPS = [
    ('rifle', '/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/MM_Rifle_Fire', DST_DIR + '/MA_Rifle_Fire_Add',
     'rifle_fire_add'),
    ('pistol', '/Game/CLS/Example/SetupYourHeroExample/Anims/Pistol/MM_Pistol_Fire', DST_DIR + '/MA_Pistol_Fire_Add',
     'pistol_fire_add'),
]
# EAdditiveAnimationType::AAT_LocalSpaceBase == 1, EAdditiveBasePoseType::ABPT_AnimFrame == 3 (AnimTypes.h).
AAT_LOCAL_SPACE_BASE, ABPT_ANIM_FRAME = 1, 3
EA = u.EditorAssetLibrary
R = {'ok': False, 'errors': [], 'assertions': [], 'clips': {}, 'da': {},
     'claim': 'CPU only (-nullrhi): asset duplicates + additive settings through HoverAuthoring.make_frame_additive, '
              'DA_HoverPilot binding; read back after save and reload; no PIE, no pixels'}


def log(*a):
    print('FIRE_ADD', *a, flush=True)


def assertion(name, ok, measured, expected=None):
    R['assertions'].append({'name': name, 'ok': bool(ok), 'measured': measured, 'expected': expected})
    log('ASSERT', 'PASS' if ok else 'FAIL', name, json.dumps(measured, default=str)[:300])


def save():
    R['ok'] = not R['errors'] and all(a['ok'] for a in R['assertions'])
    RECEIPT.write_text(json.dumps(R, indent=1, default=str))


def load(path):
    if not EA.does_asset_exist(path):
        raise RuntimeError('missing asset ' + path)
    a = EA.load_asset(path)
    if not a:
        raise RuntimeError('failed to load ' + path)
    return a


def pathish(v):
    return str(v.get_path_name()).split('.')[0] if v is not None else None


def enum_int(v):
    """An unreal enum value (or int) as its integer."""
    try:
        return int(v)
    except Exception:
        try:
            return int(v.value)
        except Exception:
            return str(v)


def additive_state(seq):
    return {'additive_anim_type': str(seq.get_editor_property('additive_anim_type')),
            'ref_pose_type': str(seq.get_editor_property('ref_pose_type')),
            'ref_frame_index': seq.get_editor_property('ref_frame_index'),
            'ref_pose_seq': pathish(seq.get_editor_property('ref_pose_seq')),
            'is_valid_additive': bool(u.HoverAuthoring.is_valid_additive(seq)),
            'length_s': round(seq.get_play_length(), 4), 'skeleton': pathish(seq.get_editor_property('skeleton'))}


def author_clip(key, src, dst, da_field):
    C = R['clips'][key] = {'src': src, 'dst': dst, 'da_field': da_field}
    if EA.does_asset_exist(dst):
        C['duplicate'] = 'existing'
    else:
        if not EA.duplicate_asset(src, dst):
            raise RuntimeError('duplicate_asset %s -> %s failed' % (src, dst))
        C['duplicate'] = 'created'
    seq = load(dst)
    if not isinstance(seq, u.AnimSequence):
        raise RuntimeError('%s is a %s, not an AnimSequence' % (dst, seq.get_class().get_name()))
    C['before'] = additive_state(seq)
    # The CLS sources are themselves MESH-space additives (MM_Rifle_Fire: AAT_RotationOffsetMeshSpace, ABPT_AnimFrame
    # 22 on itself; MM_Pistol_Fire: ABPT_LocalAnimFrame 24): the copies become LOCAL-space, frame-0-based ones.
    C['source'] = additive_state(load(src))
    C['make'] = json.loads(u.HoverAuthoring.make_frame_additive(seq, 0))
    if not EA.save_loaded_asset(seq, False):
        R['errors'].append('save failed for ' + dst)
    C['saved'] = True
    # Read back from a fresh load (the saved package), not the in-memory object.
    again = load(dst)
    C['after'] = additive_state(again)
    C['source_after'] = additive_state(load(src))
    assertion('%s copy is AAT_LocalSpaceBase / ABPT_AnimFrame / frame 0 after save' % key,
              'LOCAL_SPACE_BASE' in C['after']['additive_anim_type'].upper().replace(' ', '_') or
              C['make'].get('additive_anim_type') == AAT_LOCAL_SPACE_BASE,
              {k: C['after'][k] for k in ('additive_anim_type', 'ref_pose_type', 'ref_frame_index')},
              'AAT_LocalSpaceBase, ABPT_AnimFrame, 0')
    assertion('%s copy base frame is ANIM_FRAME 0' % key,
              ('ANIM_FRAME' in C['after']['ref_pose_type'].upper() or C['make'].get('ref_pose_type') == ABPT_ANIM_FRAME)
              and C['after']['ref_frame_index'] == 0, C['after'])
    assertion('%s copy IsValidAdditive() on the reloaded asset (base = itself at frame 0)' % key,
              C['after']['is_valid_additive'] and C['after']['ref_pose_seq'] == dst, C['after'])
    assertion('%s source MM clip left untouched' % key, C['source'] == C['source_after'],
              {'before': C['source'], 'after': C['source_after']})
    assertion('%s copy keeps the source length' % key,
              abs(C['after']['length_s'] - C['source']['length_s']) < 1e-3,
              {'copy': C['after']['length_s'], 'source': C['source']['length_s']})
    return seq


def main():
    try:
        seqs = {}
        for key, src, dst, field in CLIPS:
            seqs[key] = author_clip(key, src, dst, field)
        da = load(DA_PATH)
        changed = False
        for key, src, dst, field in CLIPS:
            before = pathish(da.get_editor_property(field))
            if before != dst:
                da.set_editor_property(field, seqs[key])
                changed = True
            R['da'][field] = {'before': before}
        for field, default in (('rifle_recoil_scale', 1.0), ('pistol_recoil_scale', 1.0)):
            R['da'][field] = da.get_editor_property(field)
        if changed and not EA.save_loaded_asset(da, False):
            R['errors'].append('save failed for ' + DA_PATH)
        R['da']['saved'] = changed
        again = load(DA_PATH)
        for key, src, dst, field in CLIPS:
            after = pathish(again.get_editor_property(field))
            R['da'][field]['after'] = after
            assertion('DA_HoverPilot.%s == %s' % (field, dst), after == dst, R['da'][field], dst)
        R['da']['pistol_aim'] = pathish(again.get_editor_property('pistol_aim'))
        R['da']['rifle_aim'] = pathish(again.get_editor_property('rifle_aim'))
    except Exception:
        R['errors'].append(traceback.format_exc())
    save()
    log('RESULT ok=%s assertions=%d failed=%d errors=%d receipt=%s' % (
        R['ok'], len(R['assertions']), sum(1 for a in R['assertions'] if not a['ok']), len(R['errors']), RECEIPT))
    for e in R['errors']:
        print('FIRE_ADD error', e[:800], flush=True)


main()
u.SystemLibrary.quit_editor()
