"""ValidateGunClips.py - prove the imported gun clips carry what Blender authored (CPU, no pixels).

Samples every rigged gun's UAnimSequence tracks through HoverAuthoring.sample_clip_bone (raw editor data, parent
space; a bone with no track samples as the skeleton reference pose, which is what the runtime plays) and composes
them along each gun's bone chain into COMPONENT space (X forward, Y right, Z up, cm), so the checks read the same
frame the game reads sockets in, whatever the bones' local axes are. Then it checks the moving parts against the
numbers the Blender rig scripts recorded in their rig JSON files:
  M4A1  (m4a1_rig.json clips_v2): bolt_carrier stroke 9.0 cm / hold-open 8.2 cm, bolt_catch 10 deg, trigger 8 deg,
        magazine pulled 12 cm by the hand (f12-f27, -12 cm at 0.45 s) then free-fall, parked -70 cm from 0.72 s
        (hidden by scale), Chamber pull 9.0 cm at f29 and home at f37,
        ReloadTactical bolt home every frame.
  EM_08 (em08_rig.json): hammer 30 deg and cylinder 60 deg about X by Fire f2, trigger 10 deg, crane ~90 deg mid
        Reload, ejector_rod 2 cm, Chamber ends one chamber on. The SIGNED cylinder angle (UE's own data) is what
        UHoverGunRig.IndexDegrees must carry so AHoverPilot::FinalizeGunPose turns the bone the same way the clip
        does; the script rewrites DA_GunRig_EM08.IndexDegrees when the sign disagrees.
  EM_11: bolt_carrier 9 cm back in Fire and Chamber, magazine leaves and re-seats in Reload.
  EM_21: charging handle still in Fire (non-reciprocating SMG handle, only the trigger moves), 8 cm back in Chamber,
        magazine leaves and re-seats in Reload.
Reload-IK hand target (2026-10-30, design items 2, 3 and 8), per gun: the non-deforming bone 'hand_l_target'
(child of body; the left palm's IK target the Reload clips key) is present, equals grip_l at f0 and the last
frame (0.3 cm), sits at grip_l in Idle / Fire / DryFire / Chamber, and rides the fresh magazine through the
carry: the hand-minus-magazine offset at the mid-carry frame is within 2 cm of the one at the pop-in frame
(EM_08: within 2 cm of cylinder + (3, -2.5, -1) mid-swing). Magazine continuity: the dropped mag hides by bone
SCALE (~0 mid-hold, 1.0 at f0 and the end) and pops in at the hand; the hidden window is read from the clip.
Every clip's length is checked against the JSON seconds, every rig's rest orientation must be identity in
component space (the convention the sockets rely on: ejection_port X = gun right), and clips whose moving bones
have no track are listed (an Interchange import that dropped a track shows up as a flat curve).

Receipt: D:/AFS_Comparisons/GunRigs_20261029/clip_validation.json

Run (CPU; it only writes DA_GunRig_EM08 when the sign is wrong):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/ValidateGunClips.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GunRigs_20261029/validate_clips.log"
"""
import json
import math
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/GunRigs_20261029')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'clip_validation.json'
SRC = Path('M:/UnrealProjects/AFS/SourceAssets')
M4 = '/Game/HoverPrototype/Weapons/M4A1/Anims/A_M4A1_'
EM = '/Game/HoverPrototype/Weapons/EM/EM_%s/Anims/A_EM%s_'
RIG_EM08 = '/Game/HoverPrototype/Weapons/Rigs/DA_GunRig_EM08'
FPS = 60.0
CM_TOL = 0.35
DEG_TOL = 1.5
# Bone parents per gun (from the rig JSON files / rig scripts); the chain is composed root-first.
PARENTS = {
    'M4A1': {'body': 'root', 'grip_r': 'root', 'bolt_carrier': 'body', 'charging_handle': 'body', 'magazine': 'body',
             'trigger': 'body', 'bolt_catch': 'body', 'mag_release': 'body', 'selector': 'body', 'ejection_port': 'body',
             'muzzle': 'body', 'grip_l': 'body', 'hand_l_target': 'body'},
    'EM08': {'body': 'root', 'grip_r': 'root', 'crane': 'body', 'cylinder': 'crane', 'ejector_rod': 'cylinder',
             'mag_well': 'cylinder', 'hammer': 'body', 'trigger': 'body', 'ejection_port': 'body', 'muzzle': 'body', 'grip_l': 'body', 'hand_l_target': 'body'},
    'EM11': {'body': 'root', 'grip_r': 'root', 'magazine': 'body', 'bolt_carrier': 'body', 'trigger': 'body',
             'ejection_port': 'body', 'muzzle': 'body', 'grip_l': 'body', 'hand_l_target': 'body'},
    'EM21': {'body': 'root', 'grip_r': 'root', 'magazine': 'body', 'charging_handle': 'body', 'trigger': 'body',
             'ejection_port': 'body', 'muzzle': 'body', 'grip_l': 'body', 'hand_l_target': 'body'},
}

R = {'ok': False, 'checks': [], 'guns': {}, 'errors': [], 'notes': [], 'tracks': {}}


def f(n):
    return n / FPS


def check(gun, name, ok, measured, expected=None):
    R['checks'].append({'gun': gun, 'name': name, 'ok': bool(ok), 'measured': measured, 'expected': expected})
    print('CLIP_CHECK', 'PASS' if ok else 'FAIL', gun, name, json.dumps(measured, default=str)[:160], flush=True)


def load(path):
    a = u.load_asset(path)
    if a is None:
        raise RuntimeError('missing ' + path)
    return a


def sample_local(seq, bone, times):
    xs = u.HoverAuthoring.sample_clip_bone(seq, bone, [float(t) for t in times])
    key = '%s/%s' % (seq.get_name(), bone)
    if key not in R['tracks']:
        R['tracks'][key] = bool(u.HoverAuthoring.clip_has_bone_track(seq, bone))
    return list(xs) if xs else None


def chain(gun, bone):
    out = [bone]
    while PARENTS[gun].get(out[-1]):
        out.append(PARENTS[gun][out[-1]])
    if out[-1] != 'root':
        out.append('root')
    return list(reversed(out))  # root first


def compose(parent, local):
    """Component transform of a child: local in the parent's frame, scale included (root carries x100)."""
    ps = parent.scale3d
    lt = local.translation
    scaled = u.Vector(lt.x * ps.x, lt.y * ps.y, lt.z * ps.z)
    trans = parent.rotation.rotate_vector(scaled) + parent.translation
    rot = parent.rotation.multiply(local.rotation)
    rot.normalize()
    ls = local.scale3d
    return u.Transform(trans, rot.rotator(), u.Vector(ps.x * ls.x, ps.y * ls.y, ps.z * ls.z))


def comp(seq, gun, bone, times):
    """Component-space transforms (cm) of bone at each time: the whole chain sampled from this clip."""
    links = chain(gun, bone)
    samples = {b: sample_local(seq, b, times) for b in links}
    if any(samples[b] is None for b in links):
        return None
    out = []
    for i in range(len(times)):
        cur = samples[links[0]][i]
        for b in links[1:]:
            cur = compose(cur, samples[b][i])
        out.append(cur)
    return out


def dpos(seq, gun, bone, times, rest):
    """Component-space translation minus the rest clip's frame-0 translation, cm."""
    xs = comp(seq, gun, bone, times)
    if not xs:
        return None
    r = rest.translation
    return [[round(x.translation.x - r.x, 3), round(x.translation.y - r.y, 3), round(x.translation.z - r.z, 3)]
            for x in xs]


def quat_conj(q):
    return u.Quat(-q.x, -q.y, -q.z, q.w)


def axis_angle(q):
    q.normalize()
    if q.w < 0:  # double cover: q and -q are one rotation; keep w >= 0 so the angle is in [0, 180] and the sign
        q = u.Quat(-q.x, -q.y, -q.z, -q.w)  # comes from the axis alone (FQuat(X, +a) <=> x component > 0)
    ang = 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, q.w))))
    s = math.sin(math.radians(ang) / 2.0)
    if abs(s) < 1e-6:
        return 0.0, '-'
    axis = [q.x / s, q.y / s, q.z / s]
    dom = max(range(3), key=lambda i: abs(axis[i]))
    return round(ang * (1 if axis[dom] >= 0 else -1), 2), 'XYZ'[dom]


def drot(seq, gun, bone, times, rest):
    """Signed component-space rotation vs rest about the dominant axis: (degrees, 'X'|'Y'|'Z')."""
    xs = comp(seq, gun, bone, times)
    if not xs:
        return None
    out = []
    for x in xs:
        q = x.rotation.multiply(quat_conj(rest.rotation))  # pose * rest^-1: the delta applied in component space
        out.append(list(axis_angle(q)))
    return out


def rest_of(idle, gun, bone):
    xs = comp(idle, gun, bone, [0.0])
    return xs[0] if xs else None


def vlist(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def vdist(a, b):
    return round(math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2), 3)


# ------------------------------------------------------------------------------------------ hand target (items 2/3/8)
def validate_hand_target(gun, clips, carry=None, seat=102, cup=None, cup_bone='magazine', scale_clips=('Reload',)):
    """hand_l_target: the left palm's IK target the gun's Reload clips key (AHoverPilot::SupportGripOffset reads it
    live). Rest = grip_l, so outside a reload the IK target is the support grip; through the reload it cups the
    magazine and carries the fresh one in, so the hands meet the real magazine by construction.
    Box mags (cup None): the carry window is read from the clip, pop-in = first frame after the magazine's hidden
    (scale < 0.5) hold, else `carry`; the hand-minus-mag offset at mid-carry must match the pop-in one (2 cm).
    Revolver (cup set): hand_l_target within 2 cm of cup_bone + cup at the mid-swing frame `seat`.
    scale_clips: clips whose magazine must hide by scale (~0 mid-hold, 1.0 at f0 and the end)."""
    reload = clips['Reload']
    nr = int(round(reload.get_play_length() * FPS))
    G = R['guns'][gun]
    H = G['hand_target'] = {'frames': nr}
    ht = comp(reload, gun, 'hand_l_target', [f(0), f(nr)])
    gl = comp(reload, gun, 'grip_l', [f(0), f(nr)])
    H['present'] = ht is not None
    H['track_in_reload'] = R['tracks'].get('%s/hand_l_target' % reload.get_name())
    check(gun, 'hand_l_target bone present (Reload clip skeleton)', ht is not None,
          {'present': ht is not None, 'keyed': H['track_in_reload']})
    if ht is None or gl is None:
        return
    ends = [vdist(ht[i].translation, gl[i].translation) for i in range(2)]
    H['to_grip_l_f0_end_cm'] = ends
    H['grip_l_comp_cm'] = vlist(gl[0].translation)
    check(gun, 'hand_l_target == grip_l at f0 and the last frame (0.3 cm)', all(e <= 0.3 for e in ends), ends,
          '<= 0.3 cm')
    rest_err = {}
    for name in ('Idle', 'Fire', 'DryFire', 'Chamber'):
        a = comp(clips[name], gun, 'hand_l_target', [f(0)])
        b = comp(clips[name], gun, 'grip_l', [f(0)])
        rest_err[name] = vdist(a[0].translation, b[0].translation) if a and b else None
    H['rest_clips_to_grip_l_cm'] = rest_err
    check(gun, 'hand_l_target sits at grip_l in Idle / Fire / DryFire / Chamber', all(
        e is not None and e <= 0.3 for e in rest_err.values()), rest_err, '<= 0.3 cm each')
    frames = list(range(0, nr + 1))
    if cup is None:
        sc = sample_local(reload, cup_bone, [f(i) for i in frames])
        scales = [round(s.scale3d.x, 3) for s in sc] if sc else None
        hidden = [i for i, s in enumerate(scales) if s < 0.5] if scales else []
        pop = (hidden[-1] + 1) if hidden else carry
        H['magazine_hidden_frames'] = [hidden[0], hidden[-1]] if hidden else None
        H['carry_pop_in_frame'] = pop
        if pop is None or pop >= seat:
            check(gun, 'hand_l_target rides the magazine through the carry', False,
                  {'pop_in': pop, 'seat': seat, 'hidden': H['magazine_hidden_frames']}, 'a carry window')
        else:
            mid = (pop + seat) // 2
            hs = comp(reload, gun, 'hand_l_target', [f(pop), f(mid), f(seat)])
            ms = comp(reload, gun, cup_bone, [f(pop), f(mid), f(seat)])
            offs = [hs[i].translation - ms[i].translation for i in range(3)] if hs and ms else None
            drift = [vdist(offs[0], offs[i]) for i in range(1, 3)] if offs else None
            H['carry'] = {'pop_in': pop, 'mid': mid, 'seat': seat,
                          'hand_minus_mag_cm': [vlist(o) for o in offs] if offs else None, 'drift_mid_seat_cm': drift}
            check(gun, 'hand_l_target rides the magazine through the carry (offset drift <= 2 cm at mid-carry)',
                  drift is not None and drift[0] <= 2.0, H['carry'], '<= 2 cm')
    else:
        hs = comp(reload, gun, 'hand_l_target', [f(seat)])
        cs = comp(reload, gun, cup_bone, [f(seat)])
        if hs and cs:
            want = cs[0].translation + u.Vector(*cup)
            err = vdist(hs[0].translation, want)
            H['cup'] = {'frame': seat, 'cylinder_cm': vlist(cs[0].translation), 'want_cm': vlist(want),
                        'hand_target_cm': vlist(hs[0].translation), 'err_cm': err}
        else:
            err = None
            H['cup'] = {'frame': seat, 'missing': cup_bone}
        check(gun, 'hand_l_target within 2 cm of %s + %s mid-swing (f%d)' % (cup_bone, list(cup), seat),
              err is not None and err <= 2.0, H['cup'], '<= 2 cm')
    for name in scale_clips:
        clip = clips.get(name)
        if not clip:
            continue
        n = int(round(clip.get_play_length() * FPS))
        sc = sample_local(clip, cup_bone, [f(i) for i in range(0, n + 1)])
        scales = [round(s.scale3d.x, 3) for s in sc] if sc else None
        hidden = [i for i, s in enumerate(scales) if s < 0.5] if scales else []
        row = {'min': min(scales) if scales else None, 'f0': scales[0] if scales else None,
               'end': scales[-1] if scales else None, 'hidden_frames': [hidden[0], hidden[-1]] if hidden else None}
        H['magazine_scale_' + name] = row
        check(gun, '%s magazine hides by scale (~0 mid-hold, 1.0 at f0 and the end)' % name,
              scales is not None and row['min'] <= 0.01 and abs(row['f0'] - 1.0) <= 0.01 and
              abs(row['end'] - 1.0) <= 0.01, row, 'min <= 0.01, 1.0 at both ends')


# ------------------------------------------------------------------------------------------ hand orientation (B7)
def axis_angle_full(q):
    """(deg, unit axis) of a u.Quat, w folded >= 0 so the angle is in [0, 180]."""
    q.normalize()
    if q.w < 0:
        q = u.Quat(-q.x, -q.y, -q.z, -q.w)
    ang = 2.0 * math.degrees(math.acos(max(-1.0, min(1.0, q.w))))
    s = math.sin(math.radians(ang) / 2.0)
    axis = [q.x / s, q.y / s, q.z / s] if abs(s) > 1e-6 else [0.0, 0.0, 0.0]
    return round(ang, 2), [round(a, 3) for a in axis]


def quat_between_deg(a, b):
    d = min(1.0, abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w))
    return math.degrees(2.0 * math.acos(d))


def validate_hand_pose(gun, clips, beats):
    """Design B7: hand_l_target's ROTATION (a gun-space delta: the rig bones rest at identity in component space, so
    the composed component rotation is the delta) and bone-LOCAL scale X (the finger curl) per clip: identity at f0
    and the last frame (< 2 deg), finite and < 150 deg between consecutive sampled frames (every 6th frame plus the
    end), scale X 1.0 (+-0.02) at both ends and within [0.4, 1.6] on every sampled frame. The rotation (axis-angle)
    and curl at each beat frame of the listed clips are logged for the reviewer. Unkeyed clips read identity / 1.0."""
    H = R['guns'][gun].setdefault('hand_pose', {})
    end_worst, step_worst, scale_end_worst, scale_lo, scale_hi, finite = 0.0, 0.0, 0.0, 9.0, -9.0, True
    for name, seq in clips.items():
        n = int(round(seq.get_play_length() * FPS))
        frames = list(range(0, n + 1, 6))
        if frames[-1] != n:
            frames.append(n)
        times = [f(i) for i in frames]
        xs = comp(seq, gun, 'hand_l_target', times)
        loc = sample_local(seq, 'hand_l_target', times)
        if xs is None or loc is None:
            H[name] = {'missing': True}
            continue
        angs = [axis_angle_full(x.rotation) for x in xs]
        steps = [round(quat_between_deg(xs[i].rotation, xs[i + 1].rotation), 2) for i in range(len(xs) - 1)]
        scales = [round(s.scale3d.x, 4) for s in loc]
        vals = [a[0] for a in angs] + steps + scales
        if not all(math.isfinite(v) for v in vals):
            finite = False
        row = {'frames': n, 'rot_f0_deg': angs[0][0], 'rot_end_deg': angs[-1][0], 'rot_max_deg': max(a[0] for a in angs),
               'rot_step_max_deg': max(steps) if steps else 0.0, 'scale_f0': scales[0], 'scale_end': scales[-1],
               'scale_min': min(scales), 'scale_max': max(scales)}
        end_worst = max(end_worst, angs[0][0], angs[-1][0])
        step_worst = max(step_worst, row['rot_step_max_deg'])
        scale_end_worst = max(scale_end_worst, abs(scales[0] - 1.0), abs(scales[-1] - 1.0))
        scale_lo, scale_hi = min(scale_lo, row['scale_min']), max(scale_hi, row['scale_max'])
        if name in beats:
            bt = [f(i) for i in beats[name]]
            bx = comp(seq, gun, 'hand_l_target', bt)
            bl = sample_local(seq, 'hand_l_target', bt)
            row['beats'] = []
            for i, fr in enumerate(beats[name]):
                ang, axis = axis_angle_full(bx[i].rotation)
                b = {'frame': fr, 'rot_deg': ang, 'axis_gun': axis, 'curl': round(bl[i].scale3d.x, 3),
                     'pos_gun_cm': vlist(bx[i].translation)}
                row['beats'].append(b)
                print('CLIP_HAND', gun, name, 'f%d' % fr, 'rot %.1f deg about %s curl %.2f at %s' % (
                    ang, axis, b['curl'], b['pos_gun_cm']), flush=True)
        H[name] = row
    check(gun, 'hand_l_target rotation identity at f0 and the last frame of every clip (< 2 deg)', end_worst < 2.0,
          {'worst_deg': round(end_worst, 2)}, '< 2 deg')
    check(gun, 'hand_l_target rotation finite and < 150 deg between consecutive sampled frames (every 6th)',
          finite and step_worst < 150.0, {'finite': finite, 'worst_step_deg': round(step_worst, 2)}, '< 150 deg')
    check(gun, 'hand_l_target scale X (curl) 1.0 +-0.02 at f0 and the end of every clip', scale_end_worst <= 0.02,
          {'worst_err': round(scale_end_worst, 4)}, '+-0.02')
    check(gun, 'hand_l_target scale X (curl) within [0.4, 1.6] on every sampled frame',
          0.4 <= scale_lo and scale_hi <= 1.6, {'min': scale_lo, 'max': scale_hi}, '[0.4, 1.6]')


def near(a, b, tol):
    return a is not None and b is not None and abs(a - b) <= tol


def clip_length_checks(gun, clips, expected):
    for name, seq in clips.items():
        want = expected.get(name)
        got = round(seq.get_play_length(), 4)
        check(gun, 'length %s' % name, want is None or near(got, want, 0.02), got, want)


def orientation_check(gun, idle, bones):
    """Rest orientation of every rig bone must be identity in component space; ejection_port yawed +90 (X = right)."""
    worst = 0.0
    rows = {}
    for b in bones:
        rest = rest_of(idle, gun, b)
        if rest is None:
            continue
        rot = rest.rotation.rotator()
        rows[b] = [round(rot.roll, 2), round(rot.pitch, 2), round(rot.yaw, 2)]
        if b == 'ejection_port':
            err = max(abs(rot.roll), abs(rot.pitch), abs(abs(rot.yaw) - 90))
        else:
            err = max(abs(rot.roll), abs(rot.pitch), abs(rot.yaw))
        worst = max(worst, err)
    R['guns'][gun]['rest_rotation_comp_deg'] = rows
    check(gun, 'rest orientation identity in component space (ejection_port yaw 90)', worst < 1.0,
          {'worst_deg': round(worst, 2), 'rows': rows})
    return worst < 1.0


# ---------------------------------------------------------------------------------------------------- M4A1
def validate_m4a1():
    gun = 'M4A1'
    meta = json.loads((SRC / 'M4A1_Modular/Rigged/m4a1_rig.json').read_text())['clips_v2']['clips']
    names = ['Idle', 'IdleEmpty', 'Fire', 'FireLast', 'DryFire', 'Reload', 'ReloadTactical', 'Chamber']
    clips = {n: load(M4 + n) for n in names}
    clip_length_checks(gun, clips, {n: meta[n]['seconds'] for n in names})
    idle = clips['Idle']
    G = R['guns'][gun] = {}
    orientation_check(gun, idle, ['root', 'body', 'bolt_carrier', 'magazine', 'ejection_port', 'muzzle'])
    rest = {b: rest_of(idle, gun, b) for b in ('bolt_carrier', 'charging_handle', 'magazine', 'trigger', 'bolt_catch')}
    G['rest_comp_cm'] = {b: [round(v, 2) for v in (rest[b].translation.x, rest[b].translation.y, rest[b].translation.z)]
                         for b in rest if rest[b]}
    bolt = dpos(clips['Fire'], gun, 'bolt_carrier', [f(0), f(1), f(2), f(6), f(7)], rest['bolt_carrier'])
    G['fire_bolt_dx'] = [b[0] for b in bolt] if bolt else None
    check(gun, 'Fire bolt_carrier -4.5/-9.0/home', bolt and near(bolt[1][0], -4.5, CM_TOL) and
          near(bolt[2][0], -9.0, CM_TOL) and near(bolt[4][0], 0.0, CM_TOL), G['fire_bolt_dx'], [0, -4.5, -9, -0.3, 0])
    trig = drot(clips['Fire'], gun, 'trigger', [f(2), f(7)], rest['trigger'])
    G['fire_trigger_deg'] = trig
    check(gun, 'Fire trigger 8 deg about Y then home', trig and near(abs(trig[0][0]), 8.0, DEG_TOL) and
          trig[0][1] == 'Y' and near(abs(trig[1][0]), 0.0, DEG_TOL), trig, [8, 0])
    bl = dpos(clips['FireLast'], gun, 'bolt_carrier', [f(2), f(7)], rest['bolt_carrier'])
    catch = drot(clips['FireLast'], gun, 'bolt_catch', [f(0), f(7)], rest['bolt_catch'])
    G['firelast_bolt_dx'] = [b[0] for b in bl] if bl else None
    G['firelast_catch_deg'] = catch
    check(gun, 'FireLast bolt -9.0 then holds -8.2', bl and near(bl[0][0], -9.0, CM_TOL) and
          near(bl[1][0], -8.2, CM_TOL), G['firelast_bolt_dx'], [-9.0, -8.2])
    check(gun, 'FireLast bolt_catch 0 -> 10 deg', catch and near(abs(catch[0][0]), 0, DEG_TOL) and
          near(abs(catch[1][0]), 10, DEG_TOL), catch, [0, 10])
    ie = dpos(clips['IdleEmpty'], gun, 'bolt_carrier', [f(0)], rest['bolt_carrier'])
    iec = drot(clips['IdleEmpty'], gun, 'bolt_catch', [f(0)], rest['bolt_catch'])
    G['idleempty'] = {'bolt_dx': ie[0][0] if ie else None, 'catch_deg': iec[0] if iec else None}
    check(gun, 'IdleEmpty bolt -8.2 / catch 10 (re-keyed 2-key clip survives import)',
          ie and near(ie[0][0], -8.2, CM_TOL) and iec and near(abs(iec[0][0]), 10, DEG_TOL), G['idleempty'])
    dt = drot(clips['DryFire'], gun, 'trigger', [f(0), f(2), f(9)], rest['trigger'])
    db = dpos(clips['DryFire'], gun, 'bolt_carrier', [f(2)], rest['bolt_carrier'])
    G['dryfire'] = {'trigger_deg': dt, 'bolt_dx_f2': db[0][0] if db else None}
    check(gun, 'DryFire trigger 0/8/0, bolt still', dt and near(abs(dt[1][0]), 8, DEG_TOL) and
          near(abs(dt[2][0]), 0, DEG_TOL) and db and near(db[0][0], 0, CM_TOL), G['dryfire'])
    # v3 (2026-10-30): the left hand pulls the mag 12 cm (f12-f27), it free-falls from the release point and is
    # parked at -70 cm from 0.7167 s (hidden by bone scale f41-f55), the fresh mag pops in at the hand at f56.
    mag = dpos(clips['Reload'], gun, 'magazine', [0.0, 0.45, 0.75, 1.9, 2.4], rest['magazine'])
    rb = dpos(clips['Reload'], gun, 'bolt_carrier', [0.0, 1.5, 2.3, 2.4], rest['bolt_carrier'])
    G['reload'] = {'mag_dz': [m[2] for m in mag] if mag else None, 'bolt_dx': [b[0] for b in rb] if rb else None}
    check(gun, 'Reload mag 0 / -12 @0.45 (pulled by the hand) / -70 parked @0.75 / seated 1.9 / seated end', mag and
          near(mag[0][2], 0, CM_TOL) and near(mag[1][2], -12, 1.0) and near(mag[2][2], -70, 1.0) and
          near(mag[3][2], 0, 0.6) and near(mag[4][2], 0, CM_TOL), G['reload']['mag_dz'], [0, -12, -70, 0, 0])
    check(gun, 'Reload bolt locked -8.2 at start, home by 2.3 s', rb and near(rb[0][0], -8.2, CM_TOL) and
          near(rb[1][0], -8.2, CM_TOL) and near(rb[2][0], 0, CM_TOL) and near(rb[3][0], 0, CM_TOL),
          G['reload']['bolt_dx'], [-8.2, -8.2, 0, 0])
    tm = dpos(clips['ReloadTactical'], gun, 'magazine', [0.45, 2.4], rest['magazine'])
    tb = dpos(clips['ReloadTactical'], gun, 'bolt_carrier', [f(i) for i in range(0, 145, 12)], rest['bolt_carrier'])
    G['reload_tactical'] = {'mag_dz_0.45': tm[0][2] if tm else None,
                            'bolt_dx_max_abs': round(max(abs(b[0]) for b in tb), 3) if tb else None}
    check(gun, 'ReloadTactical mag -12 @0.45 (pulled by the hand), bolt home every frame', tm and near(tm[0][2], -12, 1.0) and
          near(tm[1][2], 0, CM_TOL) and tb and max(abs(b[0]) for b in tb) < CM_TOL, G['reload_tactical'])
    cb = dpos(clips['Chamber'], gun, 'bolt_carrier', [f(0), f(29), f(37), f(66)], rest['bolt_carrier'])
    ch = dpos(clips['Chamber'], gun, 'charging_handle', [f(0), f(29), f(37), f(66)], rest['charging_handle'])
    G['chamber'] = {'bolt_dx': [b[0] for b in cb] if cb else None, 'handle_dx': [b[0] for b in ch] if ch else None}
    check(gun, 'Chamber bolt+handle 0 / -9 @f29 / 0 @f37 / 0 end', cb and ch and
          near(cb[1][0], -9, CM_TOL) and near(ch[1][0], -9, CM_TOL) and near(cb[2][0], 0, CM_TOL) and
          near(ch[2][0], 0, CM_TOL) and near(cb[3][0], 0, CM_TOL), G['chamber'], [0, -9, 0, 0])
    # Design: fresh mag pops in at the hand at the belt (~f56) and seats at f102; both reloads hide the empty by scale.
    validate_hand_target(gun, clips, carry=56, seat=102, scale_clips=('Reload', 'ReloadTactical'))
    # Beat frames of the v3 hand path (RigM4A1.py): grip_l, grab, release, belt, belt hold, carry x3, seat, bolt catch, end.
    validate_hand_pose(gun, clips, {'Reload': [0, 12, 27, 56, 66, 80, 92, 97, 102, 110, 118, 144],
                                    'ReloadTactical': [0, 12, 27, 56, 66, 80, 92, 97, 102, 144]})


# ---------------------------------------------------------------------------------------------------- EM_08
def validate_em08():
    gun = 'EM08'
    meta = json.loads((SRC / 'EM_Apocalyptic_Guns/Rigged/EM_08/em08_rig.json').read_text())['clips']
    names = ['Idle', 'Fire', 'DryFire', 'Reload', 'Chamber']
    clips = {n: load(EM % ('08', '08') + n) for n in names}
    clip_length_checks(gun, clips, {n: meta['A_EM08_' + n]['seconds'] for n in names})
    idle = clips['Idle']
    G = R['guns'][gun] = {}
    orientation_check(gun, idle, ['root', 'body', 'crane', 'cylinder', 'hammer', 'ejection_port', 'muzzle'])
    rest = {b: rest_of(idle, gun, b) for b in ('cylinder', 'crane', 'hammer', 'trigger', 'ejector_rod')}
    cyl = drot(clips['Fire'], gun, 'cylinder', [f(0), f(2), f(7)], rest['cylinder'])
    ham = drot(clips['Fire'], gun, 'hammer', [f(2), f(7)], rest['hammer'])
    trg = drot(clips['Fire'], gun, 'trigger', [f(2), f(7)], rest['trigger'])
    G['fire'] = {'cylinder_deg_signed': cyl, 'hammer_deg': ham, 'trigger_deg': trg}
    check(gun, 'Fire cylinder 60 deg about X by f2 and stays', cyl and cyl[1][1] == 'X' and
          near(abs(cyl[1][0]), 60, DEG_TOL) and near(abs(cyl[2][0]), 60, DEG_TOL), cyl, '+-60 about X')
    check(gun, 'Fire hammer 30 deg at f2, down at f7', ham and near(abs(ham[0][0]), 30, DEG_TOL) and
          near(abs(ham[1][0]), 0, DEG_TOL), ham, [30, 0])
    check(gun, 'Fire trigger 10 deg', trg and near(abs(trg[0][0]), 10, DEG_TOL), trg, 10)
    dcyl = drot(clips['DryFire'], gun, 'cylinder', [f(12)], rest['cylinder'])
    ccyl = drot(clips['Chamber'], gun, 'cylinder', [f(48)], rest['cylinder'])
    G['dryfire_cylinder_end'] = dcyl
    G['chamber_cylinder_end'] = ccyl
    check(gun, 'DryFire and Chamber end one chamber on (60 deg)', dcyl and ccyl and
          near(abs(dcyl[0][0]), 60, DEG_TOL) and near(abs(ccyl[0][0]), 60, DEG_TOL), [dcyl, ccyl])
    signs = [c[0] for c in (cyl[1:] + dcyl + ccyl) if c and abs(c[0]) > 1] if cyl and dcyl and ccyl else []
    same_sign = bool(signs) and all((s > 0) == (signs[0] > 0) for s in signs)
    check(gun, 'every indexing clip turns the cylinder the same way', same_sign, signs)
    signed_index = round(signs[0], 1) if same_sign else None
    G['index_degrees_signed'] = signed_index
    frames = list(range(0, 145, 2))
    cr = drot(clips['Reload'], gun, 'crane', [f(i) for i in frames], rest['crane']) or []
    er = dpos(clips['Reload'], gun, 'ejector_rod', [f(i) for i in frames], rest['ejector_rod']) or []
    cy = dpos(clips['Reload'], gun, 'cylinder', [f(i) for i in frames], rest['cylinder']) or []
    cmax = max((abs(c[0]) for c in cr), default=None)
    emin = min((e[0] for e in er), default=None)
    ymin = min((c[1] for c in cy), default=None)
    G['reload'] = {'crane_max_deg': cmax, 'crane_axis': cr[len(cr) // 2][1] if cr else None,
                   'ejector_min_dx_cm': emin, 'crane_end_deg': cr[-1][0] if cr else None,
                   'cylinder_min_dy_cm': ymin}
    check(gun, 'Reload crane ~90 deg about X and back (eased swing overshoots a few deg)', cmax is not None and
          near(cmax, 90, 5.0) and near(abs(cr[-1][0]), 0, DEG_TOL) and G['reload']['crane_axis'] == 'X', G['reload'])
    check(gun, 'Reload swings the cylinder out to the left (>= 2.5 cm)', ymin is not None and ymin <= -2.5, ymin)
    check(gun, 'Reload ejector_rod strokes 2 cm rearward', emin is not None and near(emin, -2.0, CM_TOL), emin, -2.0)
    rig = load(RIG_EM08)
    cur = rig.get_editor_property('index_degrees')
    G['da_index_degrees_before'] = cur
    if signed_index is not None and (cur > 0) != (signed_index > 0):
        rig.set_editor_property('index_degrees', float(signed_index))
        saved = u.EditorAssetLibrary.save_loaded_asset(rig, False)
        G['da_index_degrees_after'] = rig.get_editor_property('index_degrees')
        R['notes'].append('DA_GunRig_EM08.IndexDegrees %s -> %s (clip sign), saved=%s' % (cur, signed_index, saved))
    else:
        G['da_index_degrees_after'] = cur
    check(gun, 'DA_GunRig_EM08.IndexDegrees matches the clip sign', signed_index is not None and
          (G['da_index_degrees_after'] > 0) == (signed_index > 0) and near(abs(G['da_index_degrees_after']), 60, .1),
          {'da': G['da_index_degrees_after'], 'clip': signed_index})
    # Design: f15-f90 the hand cups the swung-out cylinder at cylinder + (3, -2.5, -1); checked mid-swing (f50).
    validate_hand_target(gun, clips, seat=50, cup=(3.0, -2.5, -1.0), cup_bone='cylinder', scale_clips=())
    # Beats (RigEM_08.py): grab, cup start, mid-swing, cup end, belt, speedloader, closing x2, end.
    validate_hand_pose(gun, clips, {'Reload': [0, 15, 18, 50, 90, 115, 125, 130, 140, 144]})


# ---------------------------------------------------------------------------------------------------- EM_11 / 21
def validate_box_gun(gun, n, action_bone, fire_travel_cm, chamber_travel_cm, mag_bone='magazine', beats=None):
    meta_path = SRC / ('EM_Apocalyptic_Guns/Rigged/EM_%s/em%s_rig.json' % (n, n))
    meta = json.loads(meta_path.read_text())['clips']
    names = ['Idle', 'Fire', 'DryFire', 'Reload', 'Chamber']
    clips = {m: load(EM % (n, n) + m) for m in names}
    exp = {}
    for m in names:
        e = meta.get(m) or meta.get('A_EM%s_%s' % (n, m)) or {}
        exp[m] = e.get('seconds')
    clip_length_checks(gun, clips, exp)
    idle = clips['Idle']
    G = R['guns'][gun] = {}
    orientation_check(gun, idle, ['root', 'body', action_bone, mag_bone, 'ejection_port', 'muzzle'])
    rest = {b: rest_of(idle, gun, b) for b in (action_bone, mag_bone, 'trigger')}
    nf = int(round(clips['Fire'].get_play_length() * FPS)) + 1
    fb = dpos(clips['Fire'], gun, action_bone, [f(i) for i in range(nf)], rest[action_bone]) or []
    fmin = min((b[0] for b in fb), default=None)
    ft = drot(clips['Fire'], gun, 'trigger', [f(2)], rest['trigger'])
    G['fire'] = {'%s_min_dx' % action_bone: fmin, 'end_dx': fb[-1][0] if fb else None, 'frames': nf,
                 'trigger_deg_f2': ft}
    if fire_travel_cm:
        ok = fmin is not None and near(fmin, -fire_travel_cm, 0.6) and near(fb[-1][0], 0, CM_TOL)
        check(gun, 'Fire %s travels back %.0f cm and returns' % (action_bone, fire_travel_cm), ok, G['fire'],
              -fire_travel_cm)
    else:
        ok = fmin is not None and abs(fmin) < CM_TOL and ft and abs(ft[0][0]) > 2.0
        check(gun, 'Fire leaves the %s still (non-reciprocating) and pulls the trigger' % action_bone, ok, G['fire'],
              'handle 0, trigger ~8')
    nr = int(round(clips['Reload'].get_play_length() * FPS)) + 1
    mg = dpos(clips['Reload'], gun, mag_bone, [f(i) for i in range(0, nr, 2)], rest[mag_bone]) or []
    far = max((math.sqrt(m[0] ** 2 + m[1] ** 2 + m[2] ** 2) for m in mg), default=None)
    low = min((m[2] for m in mg), default=None)
    G['reload'] = {'mag_max_offset_cm': round(far, 2) if far else None, 'mag_min_dz_cm': low,
                   'mag_end_cm': [round(v, 2) for v in mg[-1]] if mg else None, 'frames': nr}
    check(gun, 'Reload magazine leaves (> 5 cm, drops) and re-seats', far is not None and far > 5.0 and low is not None
          and low < -5.0 and mg and all(abs(v) < CM_TOL for v in mg[-1]), G['reload'])
    nc = int(round(clips['Chamber'].get_play_length() * FPS)) + 1
    cb = dpos(clips['Chamber'], gun, action_bone, [f(i) for i in range(nc)], rest[action_bone]) or []
    cmin = min((b[0] for b in cb), default=None)
    G['chamber'] = {'%s_min_dx' % action_bone: cmin, 'end_dx': cb[-1][0] if cb else None}
    check(gun, 'Chamber %s pulls back %.0f cm and returns' % (action_bone, chamber_travel_cm), cmin is not None and
          near(cmin, -chamber_travel_cm, 0.6) and near(cb[-1][0], 0, CM_TOL), G['chamber'], -chamber_travel_cm)
    dt = drot(clips['DryFire'], gun, 'trigger', [f(2), f(3)], rest['trigger'])
    G['dryfire_trigger_deg'] = dt
    check(gun, 'DryFire moves the trigger about Y', dt and max(abs(d[0]) for d in dt) > 2.0 and
          all(d[1] in ('Y', '-') for d in dt), dt)
    # Design: EM_11 / EM_21 fresh mag in hand from ~f75, seated f102; the dropped mag hides by scale meanwhile.
    validate_hand_target(gun, clips, carry=75, seat=102, cup_bone=mag_bone)
    validate_hand_pose(gun, clips, {'Reload': beats} if beats else {})


# Beat frames of the hand paths (RigEM_11.py / RigEM_21.py) for the B7 log.
BEATS_EM11 = [0, 8, 10, 20, 30, 56, 62, 104, 106, 108, 110, 126, 138, 141, 144]
BEATS_EM21 = [0, 10, 20, 25, 57, 75, 102, 108, 116, 120, 134, 144]


def main():
    for name, fn in (('M4A1', validate_m4a1), ('EM08', validate_em08),
                     ('EM11', lambda: validate_box_gun('EM11', '11', 'bolt_carrier', 9.0, 9.0, beats=BEATS_EM11)),
                     ('EM21', lambda: validate_box_gun('EM21', '21', 'charging_handle', 0.0, 8.0, beats=BEATS_EM21))):
        try:
            fn()
        except Exception:
            R['errors'].append(name + ': ' + traceback.format_exc())
    R['missing_tracks'] = sorted(k for k, v in R['tracks'].items() if not v)
    passed = sum(1 for c in R['checks'] if c['ok'])
    R['summary'] = {'passed': passed, 'total': len(R['checks']),
                    'failed': [c['gun'] + ': ' + c['name'] for c in R['checks'] if not c['ok']]}
    R['ok'] = passed == len(R['checks']) and not R['errors']
    RECEIPT.write_text(json.dumps(R, indent=1, default=str))
    print('CLIP_VALIDATION_DONE', json.dumps(R['summary']), 'errors=%d' % len(R['errors']), flush=True)
    print('CLIP_MISSING_TRACKS', json.dumps([m for m in R['missing_tracks'] if 'Idle' not in m]),
          'idle_without_tracks=%d' % len([m for m in R['missing_tracks'] if 'Idle' in m]), flush=True)
    for e in R['errors']:
        print(e, flush=True)


main()
u.SystemLibrary.quit_editor()
