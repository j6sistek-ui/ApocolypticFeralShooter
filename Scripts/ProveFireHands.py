"""ProveFireHands.py - headless proof of design A1 / A2 / B2 on the current assets (CPU, -nullrhi PIE of L_NYC_Survival).

What it proves, per tick of a fixed-step PIE (same boot / aim / tick path as MeasureHandAxes.py):
  A1/A2  M4A1 (DA_GunRig_M4A1, Rifle stance): aim, then a 5-shot burst (DA_AFS_Ballista is automatic, 8 rounds/s):
         on EVERY tick the left palm (midpoint hand_l / middle_01_l) is within 4 cm of the gun's hand_l_target and never
         ahead of the muzzle (dot(palm - grip_r, gun forward) < muzzle.x - 3 cm); no TPFireAction montage ran on the
         CLS driver (UHoverLocomotionBridge::IsActionPlaying false throughout); the stance fire additive
         (DA_HoverPilot.RifleFireAdd = MA_Rifle_Fire_Add) kicked the upper body: max spine_03 / head rotation change
         from the pre-burst baseline is recorded (design A1 asks 2-10 deg at the peak; the proof records the peak).
  B2     Synthetic test: UHoverAuthoring::SetSupportHandOverride drives the left-hand delta / curl in place of the rig
         bone: a 90 deg roll about gun X with curl 0.3, then curl 1.5, then restored. hand_l's world rotation must equal
         D * baseline (D = gun_q * Rx(90) * gun_q^-1) within 10 deg while the palm stays on the target (< 4 cm), the
         finger joints (index/middle/ring/pinky _02 vs _01) open at 0.3 and close at 1.5 relative to the aim pose, and
         everything returns to the baseline after the restore.
  A1/A2  EM_08 (DA_GunRig_EM08 applied in place, Pistol stance): aim, three shots 0.5 s apart, same per-tick checks.
  C2     Sanity of HoverAuthoring.measure_frame_luminance on two existing capture stills (CPU image decode).
Receipt: D:/AFS_Comparisons/GunRigs_20261029/fire_hand_proof.json (log fire_hand_proof.log). Changes only the Play world.

Run (never concurrently with another AFS editor):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/ProveFireHands.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/fire_hand_proof.log"
"""
import json
import math
import re
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'fire_hand_proof.json'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
RIG_EM08 = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08'
STILLS = Path('D:/AFS_Comparisons/GunProof_20261030/stills')
TIMEOUT = 300
SETTLE_S = 1.5
COMP = u.RelativeTransformSpace.RTS_COMPONENT
FINGERS = ['index', 'middle', 'ring', 'pinky']
EA = u.EditorAssetLibrary
R = {'ok': False, 'errors': [], 'notes': [], 'assertions': [], 'pie': {}, 'result': {},
     'claim': 'CPU only (-nullrhi): fixed-step PIE of L_NYC_Survival; numbers from the live meshes every tick; no pixels'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'pt': None, 'phase': None,
     'last_t': None, 'done': False, 'handle': None, 'rig': None, 'rows': [], 'base': None, 'ammo0': None,
     'released': None, 'shot': 0, 'shot_t': None}


# ------------------------------------------------------------------------------------------------ math
def log(*a):
    print('FIRE_HANDS', *a, flush=True)


def assertion(name, ok, measured, expected=None):
    R['assertions'].append({'name': name, 'ok': bool(ok), 'measured': measured, 'expected': expected})
    log('ASSERT', 'PASS' if ok else 'FAIL', name, json.dumps(measured, default=str)[:400])


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


def v3(v):
    return [float(v.x), float(v.y), float(v.z)]


def q4(q):
    return [float(q.x), float(q.y), float(q.z), float(q.w)]


def sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def add(a, b):
    return [a[i] + b[i] for i in range(3)]


def mul(a, s):
    return [a[i] * s for i in range(3)]


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def length(a):
    return math.sqrt(dot(a, a))


def rnd(a, n=3):
    return [round(x, n) for x in a] if a is not None else None


def q_rotate(q, v):
    qv = q[:3]
    t = mul(cross(qv, v), 2.0)
    return add(add(v, mul(t, q[3])), cross(qv, t))


def q_inv(q):
    return [-q[0], -q[1], -q[2], q[3]]


def q_mul(a, b):
    """UE FQuat a*b: rotate by b first, then a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz]


def q_deg(a, b):
    """Angle between two rotations (deg), double cover folded."""
    d = min(1.0, abs(sum(a[i] * b[i] for i in range(4))))
    return math.degrees(2.0 * math.acos(d))


def q_axis(axis, deg):
    s = math.sin(math.radians(deg) / 2.0)
    return [axis[0] * s, axis[1] * s, axis[2] * s, math.cos(math.radians(deg) / 2.0)]


# ------------------------------------------------------------------------------------------------ PIE reads
def world():
    return u.HoverAuthoring.get_playtest_world()


def gun(p):
    return p.get_editor_property('world_gun_skel')


def mesh_loc(p, name):
    try:
        return v3(p.mesh.get_socket_location(name)) if p.mesh.does_socket_exist(name) else None
    except Exception:
        return None


def mesh_quat(p, name):
    try:
        return q4(p.mesh.get_socket_rotation(name).quaternion())
    except Exception:
        return None


def gun_world(p, name):
    g = gun(p)
    try:
        return v3(g.get_socket_location(name)) if g.does_socket_exist(name) else None
    except Exception:
        return None


def gun_comp(p, name):
    g = gun(p)
    try:
        return g.get_socket_transform(name, COMP) if g.does_socket_exist(name) else None
    except Exception:
        return None


def press(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


def phase(name, t, **kw):
    S['phase'] = name
    S['pt'] = t
    S.update(kw)
    log('phase', name, 't=%.3f' % t)


def rig_name(p):
    r = p.get_gun_rig()
    return r.get_name() if r else None


def weapon(p):
    c = p.get_editor_property('combat')
    return c.get_weapon() if c else None


def ammo(p):
    w = weapon(p)
    return w.get_current_clip_ammo() if w else None


def clip_name(p):
    try:
        inst = gun(p).get_anim_instance()
        a = inst.get_animation_asset() if inst else None
        return a.get_name() if a else None
    except Exception:
        return None


def action_playing(p):
    try:
        lb = p.get_editor_property('locomotion_bridge')
        return bool(lb.is_action_playing()) if lb else None
    except Exception as e:
        R['notes'].append('is_action_playing: %s' % e)
        return None


def finger_bends(p):
    """Bend at each _02 joint: the rotation angle between _01 and _02 (deg), per finger."""
    out = {}
    for f in FINGERS:
        a, b = mesh_quat(p, '%s_01_l' % f), mesh_quat(p, '%s_02_l' % f)
        out[f] = round(q_deg(a, b), 2) if a and b else None
    return out


def sample(p, t):
    g = gun(p)
    gt = g.get_world_transform()
    gq, go = q4(gt.rotation), v3(gt.translation)
    fwd = q_rotate(gq, [1.0, 0.0, 0.0])
    hand_l, mid_l = mesh_loc(p, 'hand_l'), mesh_loc(p, 'middle_01_l')
    hand_r, mid_r = mesh_loc(p, 'hand_r'), mesh_loc(p, 'middle_01_r')
    palm_l = mul(add(hand_l, mid_l), 0.5)
    palm_r = mul(add(hand_r, mid_r), 0.5)
    target, grip_r, grip_l = gun_world(p, 'hand_l_target'), gun_world(p, 'grip_r'), gun_world(p, 'grip_l')
    mz = gun_comp(p, 'muzzle')
    muzzle_x = float(mz.translation.x) if mz else None
    along = dot(sub(palm_l, grip_r), fwd) if grip_r else None
    tq = gun_comp(p, 'hand_l_target')
    hl = mesh_quat(p, 'hand_l')
    cr = S['pc'].get_control_rotation()
    try:
        inst = p.mesh.get_anim_instance()
        add_name = inst.get_editor_property('stance_fire_add')
        add_name = add_name.get_name() if add_name else None
    except Exception as e:
        add_name = None
        if not R['notes'] or 'stance_fire_add' not in R['notes'][-1]:
            R['notes'].append('stance_fire_add read failed (%s): %s' % (
                p.mesh.get_anim_instance().get_class().get_name() if p.mesh.get_anim_instance() else None, e))
    return {'t': round(t, 3), 'rig': rig_name(p), 'clip': clip_name(p), 'ammo': ammo(p), 'aiming': bool(p.is_aiming()),
            'palm_to_target_cm': round(length(sub(palm_l, target)), 2) if target else None,
            'palm_to_grip_l_cm': round(length(sub(palm_l, grip_l)), 2) if grip_l else None,
            'palm_r_to_grip_r_cm': round(length(sub(palm_r, grip_r)), 2) if grip_r else None,
            'palm_along_gun_cm': round(along, 2) if along is not None else None, 'muzzle_x_cm': muzzle_x,
            'palm_ahead_of_muzzle': (along > muzzle_x - 3.0) if along is not None and muzzle_x is not None else None,
            'action_playing': action_playing(p), 'stance_fire_add': add_name,
            'hand_l_q': hl, 'gun_q': gq, 'hand_l_in_gun_q': rnd(q_mul(q_inv(gq), hl), 4) if hl else None,
            'target_rot_gun_q': rnd(q4(tq.rotation), 4) if tq else None,
            'spine_03_q': mesh_quat(p, 'spine_03'), 'head_q': mesh_quat(p, 'head'), 'hand_r_q': mesh_quat(p, 'hand_r'),
            'control_pitch': round(float(cr.pitch), 2), 'fingers': finger_bends(p)}


def kick_of(rows, base):
    """Peak rotation change (deg) of the upper body vs the baseline tick, per bone, over the rows."""
    out = {}
    for key in ('spine_03_q', 'head_q', 'hand_r_q'):
        vals = [q_deg(r[key], base[key]) for r in rows if r.get(key) and base.get(key)]
        out[key.replace('_q', '_max_deg')] = round(max(vals), 2) if vals else None
        if vals:
            out[key.replace('_q', '_peak_t')] = rows[max(range(len(vals)), key=lambda i: vals[i])]['t']
    pitches = [r['control_pitch'] for r in rows]
    out['control_pitch_span_deg'] = round(max(pitches) - min(pitches), 2) if pitches else None
    return out


def analyse_burst(label, rows, base, want_shots):
    fired = (base['ammo'] - rows[-1]['ammo']) if base.get('ammo') is not None and rows[-1].get('ammo') is not None else None
    dists = [r['palm_to_target_cm'] for r in rows if r['palm_to_target_cm'] is not None]
    ahead = [r for r in rows if r['palm_ahead_of_muzzle']]
    acts = [r for r in rows if r['action_playing']]
    out = {'ticks': len(rows), 'shots_fired': fired, 'palm_to_target_max_cm': max(dists) if dists else None,
           'palm_to_target_mean_cm': round(sum(dists) / len(dists), 3) if dists else None,
           'palm_along_gun_max_cm': max(r['palm_along_gun_cm'] for r in rows if r['palm_along_gun_cm'] is not None),
           'muzzle_x_cm': rows[0]['muzzle_x_cm'], 'ticks_palm_ahead_of_muzzle': len(ahead),
           'ticks_action_playing': len(acts), 'action_playing_seen_none': all(r['action_playing'] is not None for r in rows),
           'stance_fire_add': rows[0]['stance_fire_add'], 'clips_seen': sorted(set(r['clip'] for r in rows if r['clip'])),
           'kick': kick_of(rows, base),
           'palm_r_to_grip_r_max_cm': max(r['palm_r_to_grip_r_cm'] for r in rows if r['palm_r_to_grip_r_cm'] is not None)}
    assertion('%s: %d rounds fired' % (label, want_shots), fired == want_shots, fired, want_shots)
    assertion('%s: left palm within 4 cm of hand_l_target on every tick' % label,
              dists and out['palm_to_target_max_cm'] <= 4.0, {'max': out['palm_to_target_max_cm'], 'ticks': len(dists)},
              '<= 4 cm')
    assertion('%s: left palm never ahead of the muzzle' % label, not ahead,
              {'ticks_ahead': len(ahead), 'palm_along_max': out['palm_along_gun_max_cm'], 'muzzle_x': out['muzzle_x_cm']},
              'dot(palm - grip_r, fwd) < muzzle.x - 3 cm')
    assertion('%s: no driver montage (IsActionPlaying false throughout)' % label,
              out['action_playing_seen_none'] and not acts, {'ticks_action_playing': len(acts), 'ticks': len(rows)})
    assertion('%s: right palm within 4 cm of grip_r on every tick' % label, out['palm_r_to_grip_r_max_cm'] <= 4.0,
              out['palm_r_to_grip_r_max_cm'], '<= 4 cm')
    return out


# ------------------------------------------------------------------------------------------------ phases
def run_phase(w, p, t, el):
    ph = S['phase']
    if ph == 'boot':
        if rig_name(p) == 'DA_GunRig_M4A1' and el >= 2.5:
            press('RightMouseButton', True)
            phase('aim', t)
        elif el > 20:
            raise RuntimeError('boot: rig never became DA_GunRig_M4A1 (rig=%s)' % rig_name(p))
    elif ph == 'aim':
        if el >= SETTLE_S:
            S['base'] = sample(p, t)
            R['pie']['m4a1_baseline'] = S['base']
            assertion('M4A1 aim: stance additive bound (MA_Rifle_Fire_Add) and support hand on grip_l before the burst',
                      S['base']['stance_fire_add'] == 'MA_Rifle_Fire_Add' and S['base']['palm_to_target_cm'] is not None
                      and S['base']['palm_to_target_cm'] <= 4.0,
                      {k: S['base'][k] for k in ('stance_fire_add', 'palm_to_target_cm', 'rig', 'aiming')})
            press('LeftMouseButton', True)
            phase('burst', t, rows=[], released=None, ammo0=S['base']['ammo'])
    elif ph == 'burst':
        S['rows'].append(sample(p, t))
        a = S['rows'][-1]['ammo']
        if S['released'] is None and a is not None and S['ammo0'] - a >= 5:
            press('LeftMouseButton', False)
            S['released'] = t
        if S['released'] is None and el > 3.0:
            press('LeftMouseButton', False)
            S['released'] = t
            R['notes'].append('burst: trigger released on timeout (ammo %s -> %s)' % (S['ammo0'], a))
        if S['released'] is not None and t - S['released'] >= 0.6:
            R['pie']['m4a1_burst_rows'] = S['rows']
            R['result']['m4a1_burst'] = analyse_burst('M4A1 5-shot burst', S['rows'], S['base'], 5)
            k = R['result']['m4a1_burst']['kick']
            assertion('M4A1 burst: the stance additive visibly kicks the upper body (spine_03 peak 2-10 deg)',
                      k.get('spine_03_max_deg') is not None and 2.0 <= k['spine_03_max_deg'] <= 10.0, k, '2-10 deg')
            u.HoverAuthoring.set_support_hand_override(p, True, u.Rotator(roll=90.0, pitch=0.0, yaw=0.0), 0.3)
            phase('override_a', t, rows=[])
    elif ph in ('override_a', 'override_b', 'restore'):
        if el >= 0.5:
            S['rows'].append(sample(p, t))
        if el >= 0.8:
            row = S['rows'][-1]
            base = S['base']
            gq = row['gun_q']
            # D in gun space is the override rotator's own quaternion (UE: FRotator roll +90 == FQuat(X, -90), the
            # rotator's X component is -sin(roll/2)), moved into world space by the gun's world rotation, exactly as
            # FHoverSupportHandNode composes GunRotation * HandRotation * GunRotation^-1.
            d_gun = q4(u.Rotator(roll=90.0, pitch=0.0, yaw=0.0).quaternion())
            expect = q_mul(q_mul(q_mul(gq, d_gun), q_inv(gq)), base['hand_l_q'])
            err_turned = q_deg(row['hand_l_q'], expect)
            R['notes'].append('override rotator roll 90 -> gun-space quat %s (hand-built FQuat(X,+90) would be %s)' % (
                rnd(d_gun, 4), rnd(q_axis([1.0, 0.0, 0.0], 90.0), 4))) if ph == 'override_a' else None
            err_base = q_deg(row['hand_l_q'], base['hand_l_q'])
            fb, f0 = row['fingers'], base['fingers']
            dbend = {f: round(fb[f] - f0[f], 2) for f in FINGERS if fb.get(f) is not None and f0.get(f) is not None}
            mean_d = sum(dbend.values()) / len(dbend) if dbend else None
            res = {'ticks': len(S['rows']), 'hand_l_vs_expected_turned_deg': round(err_turned, 2),
                   'hand_l_vs_baseline_deg': round(err_base, 2), 'palm_to_target_cm': row['palm_to_target_cm'],
                   'finger_bend_delta_deg': dbend, 'finger_bend_delta_mean_deg': round(mean_d, 2) if mean_d is not None else None,
                   'finger_bend_now': fb, 'finger_bend_baseline': f0, 'aiming': row['aiming']}
            R['result'][ph] = res
            if ph == 'override_a':
                assertion('B2: hand_l turned 90 deg about gun X (world rotation == D * baseline within 10 deg)',
                          err_turned <= 10.0 and err_base >= 60.0, {'vs_turned': res['hand_l_vs_expected_turned_deg'],
                                                                   'vs_baseline': res['hand_l_vs_baseline_deg']})
                assertion('B2: palm still within 4 cm of hand_l_target while turned',
                          row['palm_to_target_cm'] is not None and row['palm_to_target_cm'] <= 4.0,
                          row['palm_to_target_cm'], '<= 4 cm')
                assertion('B2: curl 0.3 opens the fingers (mean _02 bend drops >= 3 deg vs the aim pose)',
                          mean_d is not None and mean_d <= -3.0, res['finger_bend_delta_deg'], '<= -3 deg')
                u.HoverAuthoring.set_support_hand_override(p, True, u.Rotator(roll=90.0, pitch=0.0, yaw=0.0), 1.5)
                phase('override_b', t, rows=[])
            elif ph == 'override_b':
                assertion('B2: curl 1.5 closes the fingers (mean _02 bend rises >= 3 deg vs the aim pose)',
                          mean_d is not None and mean_d >= 3.0, res['finger_bend_delta_deg'], '>= 3 deg')
                u.HoverAuthoring.set_support_hand_override(p, False, u.Rotator(roll=0.0, pitch=0.0, yaw=0.0), 1.0)
                phase('restore', t, rows=[])
            else:
                assertion('B2: restore returns hand_l and the fingers to the aim pose (< 5 deg / < 2 deg)',
                          err_base <= 5.0 and mean_d is not None and abs(mean_d) <= 2.0,
                          {'hand_l_vs_baseline_deg': res['hand_l_vs_baseline_deg'], 'finger_mean': res['finger_bend_delta_mean_deg']})
                p.apply_gun_rig(S['rig'])
                phase('em08_aim', t)
    elif ph == 'em08_aim':
        if el >= SETTLE_S:
            S['base'] = sample(p, t)
            R['pie']['em08_baseline'] = S['base']
            assertion('EM_08 aim: rig applied, PistolFireAdd bound (MA_Pistol_Fire_Add), palm on grip_l',
                      S['base']['rig'] == 'DA_GunRig_EM08' and S['base']['stance_fire_add'] == 'MA_Pistol_Fire_Add' and
                      S['base']['palm_to_target_cm'] is not None and S['base']['palm_to_target_cm'] <= 4.0,
                      {k: S['base'][k] for k in ('rig', 'stance_fire_add', 'palm_to_target_cm', 'aiming')})
            phase('em08_shots', t, rows=[], shot=0, shot_t=None)
    elif ph == 'em08_shots':
        S['rows'].append(sample(p, t))
        if S['shot_t'] is None:
            if S['shot'] < 3 and el >= 0.1:
                press('LeftMouseButton', True)
                S['shot_t'] = t
            elif S['shot'] >= 3 and el >= 0.6:
                R['pie']['em08_rows'] = S['rows']
                R['result']['em08_shots'] = analyse_burst('EM_08 three shots', S['rows'], S['base'], 3)
                R['result']['em08_shots']['cylinder_angle'] = p.get_editor_property('gun_cylinder_angle')
                press('RightMouseButton', False)
                phase('finish', t)
            return
        dt = t - S['shot_t']
        if 0 < dt < 0.04:
            press('LeftMouseButton', False)
        if dt >= 0.5:
            S['shot'] += 1
            S['shot_t'] = None
            S['pt'] = t
    elif ph == 'finish':
        finish()


def luma_sanity():
    L = R['result']['luminance_helper'] = {}
    for name in ('M4A1_c_before.png', 'M4A1_c_burst1_t2.png', 'EM21_c_before.png', 'EM21_c_burst1_t2.png'):
        fn = STILLS / name
        if not fn.exists():
            L[name] = {'missing': True}
            continue
        try:
            L[name] = json.loads(u.HoverAuthoring.measure_frame_luminance(str(fn), 0.6))
        except Exception as e:
            L[name] = {'error': str(e)}
    ok = [v for v in L.values() if v.get('ok')]
    assertion('C2 helper: measure_frame_luminance decodes the existing 1920x1080 stills (mean luma, saturated fraction)',
              bool(ok) and all(v.get('width') == 1920 and 0 <= v['mean_luma'] <= 255 for v in ok),
              {k: {kk: v.get(kk) for kk in ('ok', 'width', 'mean_luma', 'saturated_fraction')} for k, v in L.items()})
    if L.get('M4A1_c_before.png', {}).get('ok') and L.get('M4A1_c_burst1_t2.png', {}).get('ok'):
        b, s = L['M4A1_c_before.png'], L['M4A1_c_burst1_t2.png']
        L['m4a1_old_capture_flash_luma_ratio_receiver_cam'] = round(s['mean_luma'] / max(1e-3, b['mean_luma']), 3)
    if L.get('EM21_c_before.png', {}).get('ok') and L.get('EM21_c_burst1_t2.png', {}).get('ok'):
        b, s = L['EM21_c_before.png'], L['EM21_c_burst1_t2.png']
        L['em21_old_capture_flash_luma_ratio_receiver_cam'] = round(s['mean_luma'] / max(1e-3, b['mean_luma']), 3)


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
        return
    lines = Path(path).read_text(errors='replace').splitlines()
    marks = [i for i, l in enumerate(lines) if 'FIRE_HANDS pie start' in l]
    pie = marks[-1] if marks else 0
    bad = [l.strip()[:300] for l in lines[pie:] if re.search(r'Error|ensure|Ensure condition|Assertion failed', l) and
           re.search(r'Anim|Skeleton|Retarget|HOVER_GUN|Sequence|Bone|Additive|Pose', l) and 'FIRE_HANDS' not in l]
    L['anim_error_lines'] = bad[:20]
    L['hover_gun_lines'] = [l.strip()[:200] for l in lines[pie:] if 'HOVER_GUN ' in l][:10]
    assertion('PIE log: no anim/skeleton/additive error or ensure lines', not bad, bad[:5])


def finish():
    if S['end']:
        return
    try:
        press('LeftMouseButton', False)
        press('RightMouseButton', False)
    except Exception:
        pass
    try:
        luma_sanity()
    except Exception:
        R['errors'].append('luma: ' + traceback.format_exc())
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    S['end'] = time.monotonic()


def complete():
    try:
        harvest_log()
    except Exception:
        R['errors'].append('harvest: ' + traceback.format_exc())
    save()
    log('RESULT ok=%s assertions=%d failed=%d errors=%d receipt=%s' % (
        R['ok'], len(R['assertions']), sum(1 for a in R['assertions'] if not a['ok']), len(R['errors']), RECEIPT))
    for key in ('m4a1_burst', 'em08_shots'):
        res = R['result'].get(key)
        if res:
            log(key, json.dumps({k: res[k] for k in ('shots_fired', 'palm_to_target_max_cm', 'ticks_palm_ahead_of_muzzle',
                                                     'ticks_action_playing', 'kick')}, default=str))
    for e in R['errors']:
        print('FIRE_HANDS error', e[:800], flush=True)


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
            raise RuntimeError('timeout in phase %s' % S['phase'])
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
            log('pie start')
            phase('boot', t)
        cls = getattr(u, 'ZE_ZombieCharacter', None)
        if cls:
            for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
                z.destroy_actor()
        run_phase(w, p, t, t - S['pt'])
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('FIRE_HANDS_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


def main():
    S['rig'] = load(RIG_EM08)
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        R['errors'].append('load_level failed')
        save()
        u.SystemLibrary.quit_editor()
        return
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick)


main()
