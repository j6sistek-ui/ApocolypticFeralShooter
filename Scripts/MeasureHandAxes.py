"""MeasureHandAxes.py - left-hand axis conventions and the native pistol palm offset, in GUN space (CPU, -nullrhi).

Why: the rig scripts (Scripts/Blender/Rig*.py) are about to key hand_l_target ROTATION deltas and a finger CURL.
A delta only means something against the aim pose's hand orientation, so this measures, in the held gun's own
frame (WorldGunSkel component space: X forward, Y right, Z up, origin at grip_r; the root BONE carries the FBX
x100 scale, so only rotations and relative positions are used, never component-space scale):
  1. the left hand's finger direction (middle_01_l - hand_l) and palm normal, and hand_l's local X/Y/Z axes,
     for the Rifle stance (DA_GunRig_M4A1, MF_Rifle_Idle_ADS) and the Pistol stance (DA_GunRig_EM08 applied in
     place, MF_Pistol_Idle_ADS), each aimed and settled >= 1 s under fixed-step PIE of L_NYC_Survival;
  2. the NATIVE (no support IK) left palm offset from the right palm, i.e. where the pose author put the left
     hand relative to where UpdateGunTransform seats grip_r (bGripAtPalm), from the stance pose evaluated on
     Vexa's mesh through HoverAuthoring.describe_sequence_on_mesh (mannequin component space) and mapped into
     gun space with the live mannequin->gun rotation measured in PIE (nominal mapping: mannequin +Y = gun +X
     forward, mannequin -X = gun +Y right, +Z = up; both are reported and compared);
  3. a sentence for hand_l's local axis convention, derived from the numbers.
Palm-normal rule: of hand_l's six signed local axes (+-X, +-Y, +-Z in gun space) take the one with the largest
dot against the direction from the left PALM towards the gun's reference point after removing its component
along the finger direction (Rifle: the barrel axis above the support hand, gun-space (hand_l_target.x, 0,
muzzle.z), live palm; Pistol: the right palm (grip_r) as seen from the NATIVE pose's left palm, because the live
palm is IK-forced straight under the right hand), then Gram-Schmidt it against the finger direction. Two
geometric cross-checks (left hand, UE frame, componentwise cross): a palm-up left hand held forward has its thumb
lateral = LEFT (-Y), so palm normal N = cross(thumb_base_dir, F) and N = cross(index_base_dir, pinky_base_dir);
both stances must pick the same hand axis (the bone frame is pose-independent).

Receipt: D:/AFS_Comparisons/GunRigs_20261029/hand_axes.json   log beside it (hand_axes.log via -abslog)
Run:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/MeasureHandAxes.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/hand_axes.log"
"""
import json
import math
import re
import sys
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'hand_axes.json'
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'
RIG_EM08 = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08'
RIG_M4A1 = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_M4A1'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
POSE_BONES = ['hand_l', 'middle_01_l', 'middle_03_l', 'thumb_01_l', 'thumb_02_l', 'index_01_l', 'pinky_01_l',
              'hand_r', 'middle_01_r', 'thumb_01_r', 'lowerarm_l']
GUN_POINTS = ['grip_r', 'grip_l', 'hand_l_target', 'muzzle', 'mag_well', 'sight', 'ejection_port']
TIMEOUT = 240
SETTLE_S = 1.5       # aim hold before the measurement window (>= 1 s settled)
WINDOW_S = 0.5       # ticks averaged / checked for stability after SETTLE_S
EA = u.EditorAssetLibrary
R = {'ok': False, 'errors': [], 'notes': [], 'assertions': [], 'poses': {}, 'pie': {}, 'result': {},
     'claim': 'CPU only (-nullrhi): fixed-step PIE of L_NYC_Survival, M4A1 rig aimed (Rifle) then DA_GunRig_EM08 '
              'applied in place (Pistol), hand_l axes read from the live mesh in WorldGunSkel component space; '
              'native palm offsets from the stance poses evaluated on Vexa through describe_sequence_on_mesh.'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'pt': None, 'phase': None,
     'last_t': None, 'done': False, 'handle': None, 'rig': None, 'samples': {'rifle': [], 'pistol': []}}


# ------------------------------------------------------------------------------------------------ math
def log(*a):
    print('HAND_AXES', *a, flush=True)


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


def norm(a):
    n = math.sqrt(dot(a, a))
    return [a[i] / n for i in range(3)] if n > 1e-9 else [0.0, 0.0, 0.0]


def length(a):
    return math.sqrt(dot(a, a))


def rnd(a, n=3):
    return [round(x, n) for x in a] if a is not None else None


def q_rotate(q, v):
    """FQuat::RotateVector: T = 2 * cross(Q.xyz, V); V + W * T + cross(Q.xyz, T)."""
    qv = q[:3]
    t = mul(cross(qv, v), 2.0)
    return add(add(v, mul(t, q[3])), cross(qv, t))


def q_inv(q):
    return [-q[0], -q[1], -q[2], q[3]]


def q_mul(a, b):
    """UE FQuat a*b: rotate by b first, then a (so (a*b).RotateVector(v) == a.Rotate(b.Rotate(v)))."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def q_angle_deg(a, b):
    d = min(1.0, abs(sum(a[i] * b[i] for i in range(4))))
    return math.degrees(2.0 * math.acos(d))


def angle_deg(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(norm(a), norm(b))))))


def perp(v, axis):
    """v minus its component along the unit axis."""
    return sub(v, mul(axis, dot(v, axis)))


def axis_label(i, sign):
    return ('+' if sign > 0 else '-') + 'XYZ'[i]


def pick_axis(axes, direction):
    """The signed hand axis (gun space) best aligned with direction; returns (label, dot, axis_vector)."""
    best = None
    for i in range(3):
        for sign in (1, -1):
            a = mul(axes[i], sign)
            d = dot(a, norm(direction))
            if best is None or d > best[1]:
                best = (axis_label(i, sign), d, a)
    return best


def describe_axis(v, tol=0.5):
    """Human label of a gun-space unit vector: dominant axis plus a secondary lean when > tol * dominant."""
    names = ['forward (+X)', 'right (+Y)', 'up (+Z)']
    negs = ['back (-X)', 'left (-Y)', 'down (-Z)']
    order = sorted(range(3), key=lambda i: -abs(v[i]))
    i = order[0]
    s = (names if v[i] > 0 else negs)[i]
    j = order[1]
    if abs(v[j]) > tol * abs(v[i]):
        s += ' leaning ' + (names if v[j] > 0 else negs)[j].split(' ')[0]
    return s


# ------------------------------------------------------------------------------------------------ poses (editor)
def eval_pose(seq, mesh, t):
    d = json.loads(u.HoverAuthoring.describe_sequence_on_mesh(seq, mesh, t, POSE_BONES))
    cs = d.get('component_space_cm', {})
    out = {'time': t, 'mesh_bones': d.get('mesh_bones'), 'bones_off_reference_pose': d.get('bones_off_reference_pose'),
           'track_bones_missing_on_mesh': d.get('track_bones_missing_on_mesh'), 'component_space_cm': cs}
    if all(k in cs for k in ('hand_l', 'middle_01_l', 'hand_r', 'middle_01_r')):
        palm_l = mul(add(cs['hand_l'], cs['middle_01_l']), 0.5)
        palm_r = mul(add(cs['hand_r'], cs['middle_01_r']), 0.5)
        out['palm_l_mannequin_cm'] = rnd(palm_l, 2)
        out['palm_r_mannequin_cm'] = rnd(palm_r, 2)
        out['palm_l_minus_palm_r_mannequin_cm'] = rnd(sub(palm_l, palm_r), 2)
        out['hand_l_to_hand_r_cm'] = round(length(sub(cs['hand_l'], cs['hand_r'])), 2)
        out['palm_l_to_palm_r_cm'] = round(length(sub(palm_l, palm_r)), 2)
        out['finger_dir_mannequin'] = rnd(norm(sub(cs['middle_01_l'], cs['hand_l'])))
    return out


def poses():
    da = load(DA_PATH)
    parts = list(da.get_editor_property('body_parts') or [])
    meshes = [pt.get_editor_property('mesh') for pt in parts]
    meshes = [m for m in meshes if m]
    mesh = next((m for m in meshes if 'Vexa' in m.get_name()), meshes[0] if meshes else None)
    if not mesh:
        raise RuntimeError('DA_HoverPilot.body_parts carries no mesh')
    rifle = da.get_editor_property('rifle_aim')
    pistol = da.get_editor_property('pistol_aim')
    P = R['poses']
    P['vexa_mesh'] = str(mesh.get_path_name())
    P['rifle_aim'] = str(rifle.get_path_name()) if rifle else None
    P['pistol_aim'] = str(pistol.get_path_name()) if pistol else None
    if not rifle or not pistol:
        raise RuntimeError('DA_HoverPilot RifleAim/PistolAim unbound: %s / %s' % (P['rifle_aim'], P['pistol_aim']))
    for key, seq in (('rifle', rifle), ('pistol', pistol)):
        P[key] = {'t0': eval_pose(seq, mesh, 0.0), 't1': eval_pose(seq, mesh, 1.0)}
        a, b = P[key]['t0'].get('palm_l_minus_palm_r_mannequin_cm'), P[key]['t1'].get('palm_l_minus_palm_r_mannequin_cm')
        P[key]['palm_offset_drift_t0_t1_cm'] = round(length(sub(a, b)), 2) if a and b else None
    assertion('poses: both stance poses evaluate on Vexa with the hand bones present',
              all(P[k]['t0'].get('palm_l_minus_palm_r_mannequin_cm') for k in ('rifle', 'pistol')),
              {k: P[k]['t0'].get('palm_l_minus_palm_r_mannequin_cm') for k in ('rifle', 'pistol')})
    assertion('poses: pistol hand_l-hand_r ~10 cm, rifle ~33 cm (2026-10-30 facts)',
              abs(P['pistol']['t0']['hand_l_to_hand_r_cm'] - 10.2) < 2 and abs(P['rifle']['t0']['hand_l_to_hand_r_cm'] - 33.1) < 3,
              {'pistol': P['pistol']['t0']['hand_l_to_hand_r_cm'], 'rifle': P['rifle']['t0']['hand_l_to_hand_r_cm']},
              'pistol 10.2, rifle 33.1')


# ------------------------------------------------------------------------------------------------ PIE
def world():
    return u.HoverAuthoring.get_playtest_world()


def gun(p):
    return p.get_editor_property('world_gun_skel')


def mesh_loc(p, name):
    try:
        if not p.mesh.does_socket_exist(name):
            return None
        return v3(p.mesh.get_socket_location(name))
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
        if not g.does_socket_exist(name):
            return None
        return v3(g.get_socket_location(name))
    except Exception:
        return None


def press(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


def phase(name, t):
    S['phase'] = name
    S['pt'] = t
    log('phase', name, 't=%.3f' % t)


def rig_name(p):
    r = p.get_gun_rig()
    return r.get_name() if r else None


def sample(p, t, stance):
    """One tick: everything in gun space (WorldGunSkel component rotation; positions relative to the component
    origin, which is grip_r; scale-free)."""
    g = gun(p)
    gt = g.get_world_transform()
    gq = q4(gt.rotation)
    go = v3(gt.translation)
    gqi = q_inv(gq)
    to_gun = lambda w: q_rotate(gqi, sub(w, go))           # world point -> gun space (cm)
    dir_gun = lambda d: q_rotate(gqi, d)                    # world direction -> gun space
    hand_l, mid_l = mesh_loc(p, 'hand_l'), mesh_loc(p, 'middle_01_l')
    hand_r, mid_r = mesh_loc(p, 'hand_r'), mesh_loc(p, 'middle_01_r')
    th1, idx1, pky1 = mesh_loc(p, 'thumb_01_l'), mesh_loc(p, 'index_01_l'), mesh_loc(p, 'pinky_01_l')
    hq = mesh_quat(p, 'hand_l')
    palm_l = mul(add(hand_l, mid_l), 0.5)
    palm_r = mul(add(hand_r, mid_r), 0.5)
    mq = q4(p.mesh.get_world_transform().rotation)
    mqi = q_inv(mq)
    rig = p.get_gun_rig()
    pose = p.get_stance_aim_pose()
    out = {'t': round(t, 3), 'stance': stance, 'rig': rig.get_name() if rig else None,
           'rig_stance': str(rig.get_editor_property('stance')) if rig else None,
           'stance_pose': pose.get_name() if pose else None, 'aiming': bool(p.is_aiming()),
           'gun_component_scale': rnd(v3(gt.scale3d)),
           'gun_points_gun_cm': {n: rnd(to_gun(gun_world(p, n)), 2) for n in GUN_POINTS if gun_world(p, n)},
           'hand_l_gun_cm': rnd(to_gun(hand_l), 2), 'middle_01_l_gun_cm': rnd(to_gun(mid_l), 2),
           'palm_l_gun_cm': rnd(to_gun(palm_l), 2), 'palm_r_gun_cm': rnd(to_gun(palm_r), 2),
           'hand_r_gun_cm': rnd(to_gun(hand_r), 2),
           'finger_dir_gun': rnd(norm(dir_gun(sub(mid_l, hand_l)))),
           # Metacarpal directions from the wrist: the thumb base is the thumb side of the palm even when the
           # thumb itself wraps the gun (thumb_01 -> thumb_02 points out of the palm plane in a grip).
           'thumb_dir_gun': rnd(norm(dir_gun(sub(th1, hand_l)))) if th1 else None,
           'index_dir_gun': rnd(norm(dir_gun(sub(idx1, hand_l)))) if idx1 else None,
           'pinky_dir_gun': rnd(norm(dir_gun(sub(pky1, hand_l)))) if pky1 else None,
           'hand_l_axes_gun': {ax: rnd(dir_gun(q_rotate(hq, e))) for ax, e in
                               (('X', [1, 0, 0]), ('Y', [0, 1, 0]), ('Z', [0, 0, 1]))},
           'hand_l_world_quat': rnd(hq, 4),
           'hand_l_in_gun_quat': rnd(q_mul(gqi, hq), 4),
           # Live mannequin component -> gun mapping: gun axes expressed in mannequin component space.
           'gun_axes_in_mannequin': {ax: rnd(q_rotate(mqi, q_rotate(gq, e))) for ax, e in
                                     (('X', [1, 0, 0]), ('Y', [0, 1, 0]), ('Z', [0, 0, 1]))},
           'mannequin_to_gun_quat': rnd(q_mul(gqi, mq), 4),
           'control_rotation': [round(x, 2) for x in (lambda r: (r.roll, r.pitch, r.yaw))(S['pc'].get_control_rotation())],
           'palm_l_to_target_cm': round(length(sub(palm_l, gun_world(p, 'hand_l_target'))), 2) if gun_world(p, 'hand_l_target') else None,
           'palm_l_to_grip_l_cm': round(length(sub(palm_l, gun_world(p, 'grip_l'))), 2) if gun_world(p, 'grip_l') else None,
           'palm_r_to_grip_r_cm': round(length(sub(palm_r, gun_world(p, 'grip_r'))), 2) if gun_world(p, 'grip_r') else None,
           'hand_l_to_hand_r_cm': round(length(sub(hand_l, hand_r)), 2)}
    return out


def mean_dir(rows, key, sub_key=None):
    acc = [0.0, 0.0, 0.0]
    for r in rows:
        v = r[key][sub_key] if sub_key else r[key]
        acc = add(acc, v)
    return norm(acc)


def analyse(stance, rows):
    """Average the settled window, pick the palm normal, derive the convention sentence."""
    last = rows[-1]
    F = mean_dir(rows, 'finger_dir_gun')
    axes = [mean_dir(rows, 'hand_l_axes_gun', ax) for ax in 'XYZ']
    stability = max(angle_deg(r['finger_dir_gun'], F) for r in rows)
    axis_stability = max(angle_deg(r['hand_l_axes_gun'][ax], axes[i]) for r in rows for i, ax in enumerate('XYZ'))
    palm = last['palm_l_gun_cm']
    pts = last['gun_points_gun_cm']
    if stance == 'rifle':
        ref_x = (pts.get('hand_l_target') or pts.get('grip_l') or [22, 0, -3])[0]
        ref_z = (pts.get('muzzle') or [45, 0, 4])[2]
        ref = [ref_x, 0.0, ref_z]
        ref_name = 'barrel axis above the support hand: gun (hand_l_target.x, 0, muzzle.z)'
    else:
        # The live left palm is IK-forced onto grip_l (2.5, 0, -3.7), straight under the right palm, so the
        # live direction says nothing about which way the pose author faced the palm. Use the NATIVE pose: the
        # right palm as seen from the native left palm (mannequin offset rotated by the live mannequin->gun quat).
        d_m = R['poses']['pistol']['t0']['palm_l_minus_palm_r_mannequin_cm']
        native_l_minus_r = q_rotate(last['mannequin_to_gun_quat'], d_m)
        palm = rnd(native_l_minus_r, 2)      # native left palm, gun space, grip_r (= right palm) at the origin
        ref = [0.0, 0.0, 0.0]
        ref_name = 'the right palm (grip_r) as seen from the NATIVE pose left palm (no IK)'
    toward = perp(sub(ref, palm), F)
    label, d, axis_vec = pick_axis(axes, toward)
    normal = norm(perp(axis_vec, F))
    # Geometric cross-checks, left hand in UE's frame (X fwd, Y right, Z up, componentwise cross product). A
    # left hand held forward palm UP has its thumb LATERAL = to the LEFT (-Y): anatomical position has the palms
    # forward and thumbs outward, and flexing the shoulder 90 deg turns that palm up without rolling it. So with
    # F = +X, T = -Y, N = +Z: N = cross(T, F) (not F x T), and the palm plane gives N = cross(index, pinky)
    # (index on the thumb side -Y, pinky +Y: (1,-e,0) x (1,e,0) = (0,0,2e)).
    T = mean_dir(rows, 'thumb_dir_gun') if all(r.get('thumb_dir_gun') for r in rows) else None
    geo = norm(perp(cross(T, F), F)) if T else None
    geo_label, geo_d, _ = pick_axis(axes, geo) if geo else (None, None, None)
    I = mean_dir(rows, 'index_dir_gun') if all(r.get('index_dir_gun') for r in rows) else None
    K = mean_dir(rows, 'pinky_dir_gun') if all(r.get('pinky_dir_gun') for r in rows) else None
    plane = norm(perp(cross(I, K), F)) if I and K else None
    plane_label, plane_d, _ = pick_axis(axes, plane) if plane else (None, None, None)
    # Which hand axis is the finger direction, which is the thumb side (T = F x N for a left hand).
    f_label, f_dot, _ = pick_axis(axes, F)
    thumb_side = norm(cross(F, normal))
    t_label, t_dot, _ = pick_axis(axes, thumb_side)
    across = norm(sub(T, K)) if T and K else None   # measured thumb base minus pinky base: the thumb side
    across_label, across_d, _ = pick_axis(axes, across) if across else (None, None, None)
    convention = ('hand_l local %s along the fingers (dot %.2f), local %s out of the palm (dot %.2f against '
                  'the toward-gun rule), local %s toward the thumb side (dot %.2f; measured thumb-minus-pinky '
                  'base direction picks %s, dot %.2f)' %
                  (f_label, f_dot, label, d, t_label, t_dot, across_label, across_d or 0.0))
    out = {'ticks_in_window': len(rows), 'window_s': [rows[0]['t'], rows[-1]['t']],
           'finger_dir_gun': rnd(F), 'finger_dir_label': describe_axis(F),
           'finger_dir_stability_deg': round(stability, 2),
           'hand_l_axes_gun': {ax: rnd(axes[i]) for i, ax in enumerate('XYZ')},
           'hand_l_axes_stability_deg': round(axis_stability, 2),
           'palm_normal_rule': {'reference': ref_name, 'reference_gun_cm': rnd(ref, 2), 'palm_l_gun_cm': palm,
                                'toward_perp_to_fingers_gun': rnd(norm(toward)) if length(toward) > 1e-6 else None,
                                'toward_length_cm': round(length(toward), 2),
                                'picked_axis': label, 'picked_dot': round(d, 3)},
           'palm_normal_gun': rnd(normal), 'palm_normal_label': describe_axis(normal),
           'thumb_cross_check': {'thumb_base_dir_gun': rnd(T) if T else None, 'cross_T_F_perp_gun': rnd(geo) if geo else None,
                                 'nearest_hand_axis': geo_label, 'dot': round(geo_d, 3) if geo_d is not None else None,
                                 'agrees_with_rule': geo_label == label,
                                 'angle_between_rule_and_cross_deg': round(angle_deg(normal, geo), 1) if geo else None},
           'palm_plane_check': {'index_base_dir_gun': rnd(I) if I else None, 'pinky_base_dir_gun': rnd(K) if K else None,
                                'cross_index_pinky_perp_gun': rnd(plane) if plane else None,
                                'nearest_hand_axis': plane_label, 'dot': round(plane_d, 3) if plane_d is not None else None,
                                'agrees_with_rule': plane_label == label,
                                'angle_between_rule_and_plane_deg': round(angle_deg(normal, plane), 1) if plane else None},
           'thumb_side_gun': rnd(thumb_side), 'thumb_side_axis': t_label,
           'hand_axis_convention': convention,
           'live': {k: last[k] for k in ('palm_l_gun_cm', 'palm_r_gun_cm', 'hand_l_gun_cm', 'hand_r_gun_cm',
                                        'gun_points_gun_cm', 'palm_l_to_target_cm', 'palm_l_to_grip_l_cm',
                                        'palm_r_to_grip_r_cm', 'hand_l_to_hand_r_cm', 'gun_axes_in_mannequin',
                                        'mannequin_to_gun_quat', 'control_rotation', 'gun_component_scale',
                                        'rig', 'rig_stance', 'stance_pose', 'aiming')},
           'palm_l_minus_palm_r_live_ik_gun_cm': rnd(sub(last['palm_l_gun_cm'], last['palm_r_gun_cm']), 2)}
    assertion('%s: finger direction stable over the settled window (< 2 deg)' % stance, stability < 2.0, round(stability, 2), '< 2 deg')
    assertion('%s: palm-normal rule, thumb cross-check and palm-plane check pick the same hand axis' % stance,
              geo_label == label and plane_label == label, {'rule': label, 'thumb_cross': geo_label, 'palm_plane': plane_label})
    other = R['result'].get('rifle' if stance == 'pistol' else 'pistol')
    if other:
        assertion('both stances agree on hand_l\'s palm axis (the bone\'s local frame is pose-independent)',
                  other['palm_normal_rule']['picked_axis'] == label,
                  {'rifle': (other if stance == 'pistol' else out)['palm_normal_rule']['picked_axis'],
                   'pistol': (out if stance == 'pistol' else other)['palm_normal_rule']['picked_axis']})
    return out


def native_offsets():
    """(2) native palm offsets from the poses, mapped into gun space two ways: nominal (mannequin +Y = gun +X,
    mannequin -X = gun +Y, +Z = +Z) and the live PIE mannequin->gun rotation of that stance."""
    out = {}
    for stance in ('rifle', 'pistol'):
        pose = R['poses'][stance]['t0']
        d_m = pose['palm_l_minus_palm_r_mannequin_cm']
        nominal = [d_m[1], -d_m[0], d_m[2]]
        live_q = R['result'][stance]['live']['mannequin_to_gun_quat']  # rotates mannequin-space vectors into gun space
        live = q_rotate(live_q, d_m)
        gun_fwd_in_m = R['result'][stance]['live']['gun_axes_in_mannequin']['X']
        out[stance] = {'palm_l_minus_palm_r_mannequin_cm': d_m,
                       'nominal_mapping': 'gun(fwd,right,up) = mannequin(+Y, -X, +Z)',
                       'native_palm_offset_gun_cm_nominal': rnd(nominal, 2),
                       'native_palm_offset_gun_cm_live_mapping': rnd(live, 2),
                       'live_gun_forward_in_mannequin': gun_fwd_in_m,
                       'live_vs_nominal_forward_angle_deg': round(angle_deg(gun_fwd_in_m, [0, 1, 0]), 1),
                       'live_vs_nominal_offset_angle_deg': round(angle_deg(nominal, live), 1) if length(live) > 1e-6 else None,
                       'offset_length_cm': round(length(d_m), 2),
                       'ik_forced_palm_l_minus_palm_r_gun_cm': R['result'][stance]['palm_l_minus_palm_r_live_ik_gun_cm'],
                       'finger_dir_native_gun_nominal': rnd([pose['finger_dir_mannequin'][1], -pose['finger_dir_mannequin'][0],
                                                             pose['finger_dir_mannequin'][2]])}
    pf = out['pistol']['live_vs_nominal_forward_angle_deg']
    assertion('pistol: live gun forward in mannequin space is near +Y (the nominal mapping; aim pitch allowed)',
              pf is not None and pf < 25, pf, '< 25 deg (pitch only)')
    # B4 suggestion: round to 0.5 cm, clamp to the envelope (not more than 6 cm behind grip_r, not above it).
    n = out['pistol']['native_palm_offset_gun_cm_nominal']
    sug = [max(-6.0, round(n[0] * 2) / 2), round(n[1] * 2) / 2, min(0.0, round(n[2] * 2) / 2)]
    out['pistol']['suggested_grip_l_gun_cm_rounded_clamped'] = sug
    out['pistol']['current_em08_grip_l_gun_cm'] = R['result']['pistol']['live']['gun_points_gun_cm'].get('grip_l')
    return out


def run_phase(w, p, t, el):
    ph = S['phase']
    if ph == 'boot':
        if rig_name(p) == 'DA_GunRig_M4A1' and el >= 2.5:
            press('RightMouseButton', True)
            phase('rifle_aim', t)
        elif el > 20:
            raise RuntimeError('boot: rig never became DA_GunRig_M4A1 (rig=%s)' % rig_name(p))
    elif ph == 'rifle_aim':
        if el >= SETTLE_S:
            S['samples']['rifle'].append(sample(p, t, 'rifle'))
        if el >= SETTLE_S + WINDOW_S:
            R['pie']['rifle_samples'] = S['samples']['rifle']
            R['result']['rifle'] = analyse('rifle', S['samples']['rifle'])
            assertion('PIE: rifle rig holds MF_Rifle_Idle_ADS while aiming',
                      S['samples']['rifle'][-1]['stance_pose'] == 'MF_Rifle_Idle_ADS' and S['samples']['rifle'][-1]['aiming'],
                      {k: S['samples']['rifle'][-1][k] for k in ('rig', 'stance_pose', 'aiming')})
            p.apply_gun_rig(S['rig'])
            phase('pistol_aim', t)
    elif ph == 'pistol_aim':
        if el >= SETTLE_S:
            S['samples']['pistol'].append(sample(p, t, 'pistol'))
        if el >= SETTLE_S + WINDOW_S:
            R['pie']['pistol_samples'] = S['samples']['pistol']
            R['result']['pistol'] = analyse('pistol', S['samples']['pistol'])
            last = S['samples']['pistol'][-1]
            assertion('PIE: EM_08 rig holds MF_Pistol_Idle_ADS while aiming',
                      last['rig'] == 'DA_GunRig_EM08' and last['stance_pose'] == 'MF_Pistol_Idle_ADS' and last['aiming'],
                      {k: last[k] for k in ('rig', 'rig_stance', 'stance_pose', 'aiming')})
            R['result']['native_offsets'] = native_offsets()
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
        return
    lines = Path(path).read_text(errors='replace').splitlines()
    marks = [i for i, l in enumerate(lines) if 'HAND_AXES pie start' in l]
    pie = marks[-1] if marks else 0
    bad = [l.strip()[:300] for l in lines[pie:] if re.search(r'Error|ensure|Ensure condition', l) and
           re.search(r'Anim|Skeleton|Retarget|HOVER_GUN|Sequence|Bone', l) and 'HAND_AXES' not in l]
    L['anim_error_lines'] = bad[:20]
    assertion('PIE log: no anim/skeleton error or ensure lines', not bad, bad[:5])


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
    for st in ('rifle', 'pistol'):
        res = R['result'].get(st)
        if res:
            log(st, 'finger', res['finger_dir_gun'], 'palm_normal', res['palm_normal_gun'], 'axes', json.dumps(res['hand_l_axes_gun']))
            log(st, res['hand_axis_convention'])
    no = R['result'].get('native_offsets')
    if no:
        for st in ('rifle', 'pistol'):
            log(st, 'native palm offset gun cm nominal', no[st]['native_palm_offset_gun_cm_nominal'],
                'live-mapped', no[st]['native_palm_offset_gun_cm_live_mapping'])
    for e in R['errors']:
        print('HAND_AXES error', e[:600], flush=True)


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
        print('HAND_AXES_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


def main():
    try:
        poses()
    except Exception:
        R['errors'].append('poses: ' + traceback.format_exc())
    save()
    if R['errors']:
        log('RESULT ok=False (no PIE) errors=%d receipt=%s' % (len(R['errors']), RECEIPT))
        for e in R['errors']:
            print('HAND_AXES error', e[:600], flush=True)
        u.SystemLibrary.quit_editor()
        return
    # EditorAssetLibrary refuses to load during PIE: fetch the revolver rig now. Its Stance is Pistol on disk
    # (AuthorGunRigs.py); force it in memory only if an older asset is found, nothing is saved here.
    S['rig'] = load(RIG_EM08)
    if S['rig'].get_editor_property('stance') != u.HoverGunStance.PISTOL:
        S['rig'].set_editor_property('stance', u.HoverGunStance.PISTOL)
        R['notes'].append('DA_GunRig_EM08.Stance was not Pistol on disk; forced in memory for this run')
    R['pie']['em08_stance'] = str(S['rig'].get_editor_property('stance'))
    log('pie start')
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        R['errors'].append('load_level %s failed' % MAP)
        save()
        u.SystemLibrary.quit_editor()
        return
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick)


main()
