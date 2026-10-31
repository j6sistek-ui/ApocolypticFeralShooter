"""BindPistolAim.py - the pistol stance pose for Vexa (design item 5), CPU only (-nullrhi).

How MF_Rifle_Idle_ADS plays on Vexa today: /Game/HoverPrototype/Animations/MF_Rifle_Idle_ADS is a plain copy of
the Flight demo clip and still targets /Game/Flight/Demo/Characters/Mannequins/Meshes/SK_Mannequin (no
CompatibleSkeletons entry either way; the Vexa skeletons list none). The body is a C++ FAnimInstanceProxy
(FHoverAnimProxy) whose FAnimNode_SequencePlayer_Standalone takes the sequence directly, so the only thing that
matters is the engine's runtime bone-NAME remapping (FSkeletonRemapping) between the clip's skeleton and Vexa's;
USkeleton::IsCompatibleForEditor only filters editor asset pickers. This script does the same for the pistol:
  1. duplicates /Game/CLS/Example/SetupYourHeroExample/Anims/Pistol/MF_Pistol_Idle_ADS (9.03 s loop, CLS
     SK_Mannequin) to /Game/HoverPrototype/Animations/MF_Pistol_Idle_ADS, skeleton left as is (like the rifle copy);
  2. proves both poses on Vexa's mesh through HoverAuthoring.describe_sequence_on_mesh, which samples the pose the
     runtime way (UAnimSequence::GetAnimationPose with the MESH's bone container): track bones missing on Vexa,
     bones moved off the reference pose, hand positions; the pistol copy must read like the rifle reference and
     put both hands together (two-handed grip);
  3. sets DA_HoverPilot.PistolAim to the copy and saves it (read back);
  4. unless --no-pie: a short -nullrhi PIE of L_NYC_Survival: aim with the M4A1 (rifle stance), swap the held rig
     to DA_GunRig_EM08 with Stance=Pistol set IN MEMORY (AuthorGunRigs.py writes it to disk in the Import phase),
     and samples AHoverPilot.get_stance_aim_pose, the left palm -> grip_l distance (support IK landing on the
     pistol's grip_l) and hand_r; then scans the log after 'PISTOL_POSE pie start' for anim/skeleton errors.

Receipt: D:/AFS_Comparisons/GunRigs_20261029/pistol_pose.json
Run:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/BindPistolAim.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/pistol_pose.log"
"""
import json
import math
import re
import sys
import time
import traceback
from pathlib import Path

import unreal as u

ARGS = sys.argv[1:]
DO_PIE = '--no-pie' not in ARGS
OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'pistol_pose.json'
SRC = '/Game/CLS/Example/SetupYourHeroExample/Anims/Pistol/MF_Pistol_Idle_ADS'
DST_DIR = '/Game/HoverPrototype/Animations'
DST = DST_DIR + '/MF_Pistol_Idle_ADS'
RIFLE = DST_DIR + '/MF_Rifle_Idle_ADS'
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'
RIG_EM08 = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
BONES = ['hand_l', 'hand_r', 'middle_01_l', 'middle_01_r', 'lowerarm_l', 'upperarm_l', 'upperarm_r', 'head']
TIMEOUT = 240
EA = u.EditorAssetLibrary
R = {'ok': False, 'errors': [], 'notes': [], 'assertions': [], 'author': {}, 'compat': {}, 'pie': {},
     'claim': 'CPU only (-nullrhi): asset duplicate + DA binding, pose sampled through the runtime remap path, '
              'short PIE with the EM_08 rig forced to Stance=Pistol in memory; no pixels'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'pt': None, 'phase': None,
     'last_t': None, 'done': False, 'handle': None, 'rig': None, 'samples': [], 'rifle_samples': []}


def log(*a):
    print('PISTOL_POSE', *a, flush=True)


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


def dist(a, b):
    return round(math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3))), 2) if a and b else None


# ---------------------------------------------------------------------------------------------- author
def author():
    A = R['author']
    if EA.does_asset_exist(DST):
        A['duplicate'] = 'existing'
    else:
        dup = EA.duplicate_asset(SRC, DST)
        if not dup:
            raise RuntimeError('duplicate_asset %s -> %s failed' % (SRC, DST))
        if not EA.save_asset(DST, False):
            R['errors'].append('save failed for ' + DST)
        A['duplicate'] = 'created'
    pistol = load(DST)
    rifle = load(RIFLE)
    A['pistol'] = {'path': DST, 'skeleton': pathish(pistol.get_editor_property('skeleton')),
                   'length_s': round(pistol.get_play_length(), 3)}
    A['rifle'] = {'path': RIFLE, 'skeleton': pathish(rifle.get_editor_property('skeleton')),
                  'length_s': round(rifle.get_play_length(), 3)}
    assertion('pistol copy is an AnimSequence of ~9.03 s', isinstance(pistol, u.AnimSequence) and
              abs(pistol.get_play_length() - 9.03) < 0.1, A['pistol'], '9.03 s loop')
    # Vexa's body mesh from the DA's body parts: the part named for her (SK_Vexa_SelectedOutfit; the list also
    # carries the XANDRA head / hair meshes on the same bone names), else the first part.
    da = load(DA_PATH)
    parts = list(da.get_editor_property('body_parts') or [])
    meshes = [pt.get_editor_property('mesh') for pt in parts]
    meshes = [m for m in meshes if m]
    mesh = next((m for m in meshes if 'Vexa' in m.get_name()), meshes[0] if meshes else None)
    A['body_part_meshes'] = [pathish(m) for m in meshes]
    if not mesh:
        raise RuntimeError('DA_HoverPilot.body_parts carries no mesh')
    A['vexa_mesh'] = pathish(mesh)
    A['vexa_skeleton'] = pathish(mesh.get_editor_property('skeleton'))
    C = R['compat']
    for key, seq in (('rifle', rifle), ('pistol', pistol)):
        C[key] = json.loads(u.HoverAuthoring.describe_sequence_on_mesh(seq, mesh, 0.0, BONES))
    # The rifle pose is the known-good reference: the pistol copy must remap the same way.
    rf, pi = C['rifle'], C['pistol']
    assertion('pistol pose evaluates on Vexa (bones moved off the reference pose, like the rifle reference)',
              pi.get('bones_off_reference_pose', 0) >= 20 and rf.get('bones_off_reference_pose', 0) >= 20,
              {'rifle': rf.get('bones_off_reference_pose'), 'pistol': pi.get('bones_off_reference_pose'),
               'mesh_bones': pi.get('mesh_bones')}, '>= 20 each')
    assertion('pistol pose has no more track bones missing on Vexa than the rifle pose',
              len(pi.get('track_bones_missing_on_mesh', [])) <= len(rf.get('track_bones_missing_on_mesh', [])),
              {'rifle_missing': rf.get('track_bones_missing_on_mesh'), 'pistol_missing': pi.get('track_bones_missing_on_mesh')})
    hands = {}
    for key, c in (('rifle', rf), ('pistol', pi)):
        cs = c.get('component_space_cm', {})
        hands[key] = {'hand_l_to_hand_r_cm': dist(cs.get('hand_l'), cs.get('hand_r')),
                      'hand_l': cs.get('hand_l'), 'hand_r': cs.get('hand_r')}
    C['hands'] = hands
    assertion('pistol pose is two-handed (hand_l closer to hand_r than in the rifle pose)',
              hands['pistol']['hand_l_to_hand_r_cm'] is not None and hands['rifle']['hand_l_to_hand_r_cm'] is not None
              and hands['pistol']['hand_l_to_hand_r_cm'] < hands['rifle']['hand_l_to_hand_r_cm'], hands)
    # Bind DA_HoverPilot.PistolAim.
    before = pathish(da.get_editor_property('pistol_aim'))
    if before != DST:
        da.set_editor_property('pistol_aim', pistol)
        if not EA.save_loaded_asset(da, False):
            R['errors'].append('save failed for ' + DA_PATH)
        A['da_saved'] = True
    after = pathish(load(DA_PATH).get_editor_property('pistol_aim'))
    A['da_pistol_aim'] = {'before': before, 'after': after}
    assertion('DA_HoverPilot.PistolAim == ' + DST, after == DST, A['da_pistol_aim'], DST)
    A['da_rifle_aim'] = pathish(da.get_editor_property('rifle_aim'))


# ---------------------------------------------------------------------------------------------- PIE
def world():
    return u.HoverAuthoring.get_playtest_world()


def mesh_loc(p, name):
    try:
        v = p.mesh.get_socket_location(name)
        return [v.x, v.y, v.z]
    except Exception:
        return None


def gun_world(p, name):
    g = p.get_editor_property('world_gun_skel')
    try:
        if not g.does_socket_exist(name):
            return None
        v = g.get_socket_location(name)
        return [v.x, v.y, v.z]
    except Exception:
        return None


def sample(p, t):
    a, b = mesh_loc(p, 'hand_l'), mesh_loc(p, 'middle_01_l')
    palm = [(a[i] + b[i]) * 0.5 for i in range(3)] if a and b else None
    rig = p.get_gun_rig()
    pose = p.get_stance_aim_pose()
    hr = p.mesh.get_socket_rotation('hand_r')
    return {'t': round(t, 3), 'rig': rig.get_name() if rig else None,
            'stance': str(rig.get_editor_property('stance')) if rig else None,
            'stance_pose': pose.get_name() if pose else None, 'aiming': p.is_aiming(),
            'palm_to_grip_l_cm': dist(palm, gun_world(p, 'grip_l')),
            'wrist_to_grip_l_cm': dist(mesh_loc(p, 'hand_l'), gun_world(p, 'grip_l')),
            'hand_l_to_hand_r_cm': dist(mesh_loc(p, 'hand_l'), mesh_loc(p, 'hand_r')),
            'hand_r_to_grip_r_cm': dist(mesh_loc(p, 'hand_r'), gun_world(p, 'grip_r')),
            'hand_r_rot': [round(hr.roll, 1), round(hr.pitch, 1), round(hr.yaw, 1)]}


def rig_name(p):
    r = p.get_gun_rig()
    return r.get_name() if r else None


def press(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


def phase(name, t):
    S['phase'] = name
    S['pt'] = t
    log('phase', name, 't=%.3f' % t)


def run_phase(w, p, t, el):
    ph = S['phase']
    if ph == 'boot':
        if rig_name(p) == 'DA_GunRig_M4A1' and el >= 2.5:
            press('RightMouseButton', True)
            phase('rifle_aim', t)
        elif el > 20:
            raise RuntimeError('boot: rig never became DA_GunRig_M4A1 (rig=%s)' % rig_name(p))
    elif ph == 'rifle_aim':
        if el >= 0.8:
            S['rifle_samples'].append(sample(p, t))
        if el >= 1.2:
            R['pie']['rifle_stance'] = S['rifle_samples'][-1]
            assertion('PIE: rifle rig holds MF_Rifle_Idle_ADS', S['rifle_samples'][-1]['stance_pose'] == 'MF_Rifle_Idle_ADS',
                      S['rifle_samples'][-1]['stance_pose'], 'MF_Rifle_Idle_ADS')
            p.apply_gun_rig(S['rig'])
            phase('pistol_aim', t)
    elif ph == 'pistol_aim':
        if el >= 1.0:
            S['samples'].append(sample(p, t))
        if el >= 2.0:
            last = S['samples'][-1]
            R['pie']['pistol_stance'] = last
            R['pie']['pistol_samples'] = S['samples']
            assertion('PIE: EM_08 rig (Stance=Pistol in memory) holds MF_Pistol_Idle_ADS',
                      last['rig'] == 'DA_GunRig_EM08' and last['stance_pose'] == 'MF_Pistol_Idle_ADS',
                      {k: last[k] for k in ('rig', 'stance', 'stance_pose')}, 'MF_Pistol_Idle_ADS')
            assertion('PIE: left palm lands on the revolver grip_l under the pistol pose (<= 6 cm)',
                      last['palm_to_grip_l_cm'] is not None and last['palm_to_grip_l_cm'] <= 6.0,
                      {k: last[k] for k in ('palm_to_grip_l_cm', 'wrist_to_grip_l_cm', 'hand_l_to_hand_r_cm',
                                            'hand_r_to_grip_r_cm')}, '<= 6 cm')
            press('RightMouseButton', False)
            phase('finish', t)
    elif ph == 'finish':
        finish()


def log_path():
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        return m.group(1) if m else None
    except Exception:
        return None


def harvest_log():
    try:
        u.SystemLibrary.execute_console_command(None, 'FlushLog')
    except Exception:
        pass
    path = log_path()
    L = R['pie']['log'] = {'path': path}
    if not path or not Path(path).exists():
        L['note'] = 'abslog not found; pass -abslog=... to scan for anim errors'
        return
    lines = Path(path).read_text(errors='replace').splitlines()
    marks = [i for i, l in enumerate(lines) if 'PISTOL_POSE pie start' in l]
    pie = marks[-1] if marks else 0
    bad = [l.strip()[:300] for l in lines[pie:] if re.search(r'Error|ensure|Ensure condition', l) and
           re.search(r'Anim|Skeleton|Retarget|Compatible|HOVER_GUN|Sequence|Bone', l) and 'PISTOL_POSE' not in l]
    warn = [l.strip()[:300] for l in lines[pie:] if 'Warning' in l and
            re.search(r'Skeleton|Retarget|Compatible|MF_Pistol|MF_Rifle|remap', l, re.I) and 'PISTOL_POSE' not in l]
    L['anim_error_lines'] = bad[:20]
    L['skeleton_warning_lines'] = warn[:20]
    L['hover_gun_lines'] = [l.strip()[:200] for l in lines[pie:] if 'HOVER_GUN ' in l][-4:]
    assertion('PIE log: no anim/skeleton error or ensure lines', not bad, bad[:5])
    assertion('PIE log: no skeleton/retarget warnings naming the stance poses', not warn, warn[:5])


def finish():
    if S['end']:
        return
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    S['end'] = time.monotonic()


def complete():
    harvest_log()
    save()
    log('RESULT ok=%s assertions=%d failed=%d errors=%d receipt=%s' % (
        R['ok'], len(R['assertions']), sum(1 for a in R['assertions'] if not a['ok']), len(R['errors']), RECEIPT))
    for e in R['errors']:
        print('PISTOL_POSE error', e[:500], flush=True)


def tick(_dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                if not S['done']:
                    S['done'] = True
                    complete()
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('PIE timeout in phase %s' % S['phase'])
        if not S['play']:
            if time.monotonic() - S['start'] > 5:
                u.HoverAuthoring.set_playtest_fixed_step(True)
                u.HoverAuthoring.start_playtest()
                S['play'] = True
            return
        w = world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        if S['pc'] != pc:
            S['pc'] = pc
            u.HoverAuthoring.isolate_test_input(pc)
        p = pc.get_controlled_pawn()
        t = u.GameplayStatics.get_time_seconds(w)
        if t == S['last_t']:
            return
        S['last_t'] = t
        if S['pt'] is None:
            phase('boot', t)
        cls = getattr(u, 'ZE_ZombieCharacter', None)
        if cls:
            for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
                z.destroy_actor()
        run_phase(w, p, t, t - S['pt'])
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PISTOL_POSE_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


def main():
    try:
        author()
    except Exception:
        R['errors'].append('author: ' + traceback.format_exc())
    save()
    if not DO_PIE or R['errors']:
        log('RESULT ok=%s (no PIE) errors=%d receipt=%s' % (R['ok'], len(R['errors']), RECEIPT))
        for e in R['errors']:
            print('PISTOL_POSE error', e[:500], flush=True)
        u.SystemLibrary.quit_editor()
        return
    # EditorAssetLibrary refuses to load during PIE: fetch the rig now and force the pistol stance in memory only
    # (AuthorGunRigs.py writes Stance=Pistol to disk in the Import phase; this run must not).
    S['rig'] = load(RIG_EM08)
    S['rig'].set_editor_property('stance', u.HoverGunStance.PISTOL)
    R['pie']['rig_stance_in_memory'] = str(S['rig'].get_editor_property('stance'))
    log('pie start')
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        R['errors'].append('load_level %s failed' % MAP)
        save()
        u.SystemLibrary.quit_editor()
        return
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick)


main()
