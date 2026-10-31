"""MeasureGripSeat.py - where the right fist really sits on each gun's pistol grip (CPU, -nullrhi).

Why (owner 2026-10-31 00:10, red circles on GunProof_20261030/prev_2355_righthand/stills/M4A1_c_burst1_t2.png): the
right hand is a closed fist at the BOTTOM OF THE RECEIVER with the pistol grip hanging EMPTY below it. Every rig's
grip_r (= the gun origin) is the pistol-grip TOP centre (RigM4A1.py: "origin at pistol-grip top centre (grip_r)"; the
EM rigs follow), and AHoverPilot::UpdateGunTransform seats grip_r at the right PALM CENTRE (midpoint hand_r /
middle_01_r), so the palm lands on the grip top and the fist straddles the receiver. The gun's rotation is the aim ray
(x the hand's recoil kick), independent of the fist's rake, so the grip axis does not run through the fingers either.

This measures, per rig, the two UHoverGunRig fields that fix it (GripSeatOffset, GripRotationOffset), from geometry:
  1. GRIP (editor, each SK_* mesh through HoverAuthoring.skeletal_mesh_vertex_positions / _bones): the 'body' bone's
     vertices below grip_r, in 1 cm z slabs. The BACKSTRAP is tracked downward from the first clean slab (min x of
     the verts within a window that follows the previous slab's backstrap: a rake of up to 50 deg moves it 1.2 cm per
     slab), the FRONT STRAP upward from the grip bottom until it merges with the trigger guard (a jump of more than
     1.5 cm forward between slabs), the grip bottom is the lowest slab still holding verts. The axis G (unit, down the
     grip) is the PCA line through the mid-points (back + front) / 2 of the slabs where both straps are clean; the
     top is that line at the first slab's height, the seat axis point A is min(4.5 cm, half the grip length) down the
     axis (the SMG's grip is 6 cm tall). The grip's depth / width come from the seat slab's straps and y extent. A
     cylinder fit was tried first and failed on three of four guns: the trigger guard sits inside any radius that
     also reaches the backstrap.
  2. FIST (PIE of L_NYC_Survival, fixed step, M4A1 rig aimed = Rifle stance, then DA_GunRig_EM08 applied in place =
     Pistol stance, each settled >= 1.5 s): in the held gun's frame (WorldGunSkel component rotation, positions
     relative to the right palm centre P, scale-free) the right hand's finger direction F (hand_r -> middle_01_r),
     the BAR AXIS B = the knuckle lines index -> pinky (the *_01 MCP line and the *_02 line, averaged, pointing down:
     a fist closes around a bar that runs thumb side -> pinky side across the palm; cross(N, F) from the thumb
     metacarpal was tried first and came out 50 deg off because the thumb base points up out of the palm plane), the
     palm normal N = hand_r's local +Y made perpendicular to B (the bone frame is pose-independent; hand_axes.json
     found hand_l's palm on -Y and the right hand mirrors it; the finger-plane normal cross(pinky, index) agrees
     within 6 deg, the thumb one only within 47: the thumb metacarpal leaves the palm plane in a fist), and the fist's TUNNEL centre Tc = mean of the five points that ring
     the grip: the palm surface (P + 1 cm N), the *_01 knuckle mean, the *_02 joint mean, the *_03 joint mean and
     thumb_01 (the web closes the ring at the back): where the bar the fingers close on actually is. Alternatives
     (ring without the thumb; palm-surface + thumb-web contact) are reported for the tuning pass. hand_r's local
     axes are reported in gun space and as a convention sentence.
  3. ROTATION: Q = basis(fist) * basis(grip)^-1 in gun space turns the grip frame (G down the grip, its back
     direction -Gf) onto the fist frame (B, the direction from Tc to the palm surface = the backstrap side): applied
     as gun = aim-ray x Q (post-multiplied, gun space) the grip axis runs down through the fist. Reported as UE
     FRotator (pitch, yaw, roll; FQuat::Rotator formula, round-tripped through unreal.Rotator.quaternion()), clamped
     to 25 deg, plus the barrel deviation (angle Q*X vs X). THAT DEVIATION IS AN AIM ERROR: FireShot fires along
     the gun component's forward, so a barrel 5 deg off the camera ray lands 87 cm low at 10 m; the hand is fixed
     by the pose, so the grip/fist alignment can only be bought with it (roll about X is free but a near-vertical
     grip gains nothing from roll). The chosen value keeps the swing (the X-moving part of Q, swing-twist split)
     at SWING_LIMIT_DEG = 3 deg (half the verify's 6 deg budget) and keeps the twist; the full alignment the pose
     would want (about 18 deg of pitch on the AR grip) is reported for the Prove/tuning pass to dial.
  4. SEAT: S = A - Q^-1 * Tc: with the palm centre on S and the gun turned by Q about it, the grip's axis point A
     lands on the fist's tunnel centre. The task's literal seat (A itself, the palm centre ON the axis) is reported
     beside it; it would put the grip inside the palm bones, 2-3 cm too far back.
Both stances are measured against the CURRENT rig values (GripSeatOffset / GripRotationOffset as the DA holds them,
zero before AuthorGunRigs.py writes these numbers); a non-zero rotation is folded out so the frame is the aim-ray frame.

Receipt: D:/AFS_Comparisons/GripSeat_20261031/measure.json (numbers, vertex counts, per-slab table), log beside it.
Run (editor Python, CPU):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/MeasureGripSeat.py" -nullrhi -unattended -nosplash
      -stdout -FullStdOutLogOutput -abslog="D:/AFS_Comparisons/GripSeat_20261031/measure.log"
"""
import json
import math
import re
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/GripSeat_20261031')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'measure.json'
RIGS = '/Game/HoverPrototype/Weapons/Rigs'
RIG_EM08 = RIGS + '/DA_GunRig_EM08'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
GUNS = {
    # mesh, rig DA, stance, grip bone, slab search window in x (gun cm, excludes the stock / buffer tube behind and
    # the magazine well ahead), first slab (z top, below the receiver junction) and the backstrap start window.
    'M4A1': {'mesh': '/Game/HoverPrototype/Weapons/M4A1/SK_M4A1', 'rig': RIGS + '/DA_GunRig_M4A1', 'stance': 'rifle',
             'bone': 'body', 'x_window': (-14.0, 10.0), 'z_top': -1.0, 'back_start': (-6.0, 2.0), 'y_half': 4.0,
             'json': 'M:/UnrealProjects/AFS/SourceAssets/M4A1_Modular/Rigged/m4a1_rig.json'},
    'EM11': {'mesh': '/Game/HoverPrototype/Weapons/EM/EM_11/SK_EM11', 'rig': RIGS + '/DA_GunRig_EM11', 'stance': 'rifle',
             'bone': 'body', 'x_window': (-14.0, 9.0), 'z_top': -1.0, 'back_start': (-7.0, 2.0), 'y_half': 4.0,
             'json': 'M:/UnrealProjects/AFS/SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_11/em11_rig.json'},
    'EM21': {'mesh': '/Game/HoverPrototype/Weapons/EM/EM_21/SK_EM21', 'rig': RIGS + '/DA_GunRig_EM21', 'stance': 'rifle',
             'bone': 'body', 'x_window': (-12.0, 7.0), 'z_top': -1.0, 'back_start': (-6.0, 2.0), 'y_half': 4.0,
             'json': 'M:/UnrealProjects/AFS/SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_21/em21_rig.json'},
    'EM08': {'mesh': '/Game/HoverPrototype/Weapons/EM/EM_08/SK_EM08', 'rig': RIGS + '/DA_GunRig_EM08', 'stance': 'pistol',
             'bone': 'body', 'x_window': (-14.0, 4.0), 'z_top': -1.0, 'back_start': (-9.0, 2.0), 'y_half': 4.0,
             'json': 'M:/UnrealProjects/AFS/SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_08/em08_rig.json'},
}
SEAT_DEPTH_CM = 4.5
ROT_CLAMP_DEG = 25.0
SWING_BUDGET_DEG = 6.0      # verify: muzzle within 6 deg of the aim ray at rest
SWING_LIMIT_DEG = 3.0       # the chosen swing: an aim error the owner plays with (52 cm at 10 m), half the budget
PALM_SURFACE_CM = 1.0       # palm surface from the metacarpal mid-line toward the palm normal
HAND_BONES = ['hand_r', 'middle_01_r', 'middle_02_r', 'middle_03_r', 'index_01_r', 'index_02_r', 'index_03_r',
              'ring_01_r', 'ring_02_r', 'ring_03_r', 'pinky_01_r', 'pinky_02_r', 'pinky_03_r', 'thumb_01_r',
              'thumb_02_r', 'thumb_03_r', 'hand_l', 'middle_01_l']
GUN_POINTS = ['grip_r', 'grip_l', 'hand_l_target', 'muzzle', 'mag_well', 'sight']
TIMEOUT = 300
SETTLE_S = 1.5
WINDOW_S = 0.5
EA = u.EditorAssetLibrary
R = {'ok': False, 'errors': [], 'notes': [], 'assertions': [], 'grips': {}, 'fists': {}, 'result': {}, 'pie': {},
     'claim': 'CPU only (-nullrhi): grip geometry from the SK_* render vertices in the editor; fist frames from a '
              'fixed-step PIE of L_NYC_Survival with the M4A1 rig (Rifle stance) then DA_GunRig_EM08 applied in '
              'place (Pistol stance); no pixels.'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'pt': None, 'phase': None,
     'last_t': None, 'done': False, 'handle': None, 'rig': None, 'samples': {'rifle': [], 'pistol': []},
     'rig_values': {}}


# ------------------------------------------------------------------------------------------------ small math
def log(*a):
    print('GRIP_SEAT', *a, flush=True)


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


def norm(a):
    n = length(a)
    return [a[i] / n for i in range(3)] if n > 1e-9 else [0.0, 0.0, 0.0]


def perp(v, axis):
    return sub(v, mul(axis, dot(v, axis)))


def rnd(a, n=3):
    return [round(x, n) for x in a] if a is not None else None


def angle_deg(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(norm(a), norm(b))))))


def mean(rows):
    acc = [0.0, 0.0, 0.0]
    for r in rows:
        acc = add(acc, r)
    return mul(acc, 1.0 / len(rows)) if rows else acc


def q_rotate(q, v):
    """FQuat::RotateVector."""
    qv = q[:3]
    t = mul(cross(qv, v), 2.0)
    return add(add(v, mul(t, q[3])), cross(qv, t))


def q_inv(q):
    return [-q[0], -q[1], -q[2], q[3]]


def q_mul(a, b):
    """UE FQuat a*b: rotate by b first, then a."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


def q_norm(q):
    n = math.sqrt(sum(x * x for x in q))
    return [x / n for x in q] if n > 1e-12 else [0.0, 0.0, 0.0, 1.0]


def q_angle_deg(q):
    return math.degrees(2.0 * math.acos(min(1.0, abs(q[3]))))


def q_axis_angle(axis, deg):
    a = norm(axis)
    h = math.radians(deg) * 0.5
    s = math.sin(h)
    return [a[0] * s, a[1] * s, a[2] * s, math.cos(h)]


def q_clamp(q, max_deg):
    """Same rotation axis, angle clamped (HoverClampRotation)."""
    q = q_norm(q)
    if q[3] < 0:
        q = [-x for x in q]
    ang = q_angle_deg(q)
    if ang <= max_deg or ang < 1e-6:
        return q
    return q_axis_angle(q[:3], max_deg)


def q_from_basis(x, y, z):
    """Quaternion whose rotation maps unit X/Y/Z onto the orthonormal columns x, y, z (UE FMatrix -> FQuat)."""
    m = [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]  # m[row][col]
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        qx = (m[2][1] - m[1][2]) / s
        qy = (m[0][2] - m[2][0]) / s
        qz = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        w = (m[2][1] - m[1][2]) / s
        qx = 0.25 * s
        qy = (m[0][1] + m[1][0]) / s
        qz = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        w = (m[0][2] - m[2][0]) / s
        qx = (m[0][1] + m[1][0]) / s
        qy = 0.25 * s
        qz = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        w = (m[1][0] - m[0][1]) / s
        qx = (m[0][2] + m[2][0]) / s
        qy = (m[1][2] + m[2][1]) / s
        qz = 0.25 * s
    return q_norm([qx, qy, qz, w])


def q_to_rotator(q):
    """FQuat::Rotator -> (pitch, yaw, roll) degrees."""
    X, Y, Z, W = q
    st = Z * X - W * Y
    yaw_y = 2.0 * (W * Z + X * Y)
    yaw_x = 1.0 - 2.0 * (Y * Y + Z * Z)
    yaw = math.degrees(math.atan2(yaw_y, yaw_x))
    if st < -0.4999995:
        pitch, roll = -90.0, norm_axis(-yaw - 2.0 * math.degrees(math.atan2(X, W)))
    elif st > 0.4999995:
        pitch, roll = 90.0, norm_axis(yaw - 2.0 * math.degrees(math.atan2(X, W)))
    else:
        pitch = math.degrees(math.asin(2.0 * st))
        roll = math.degrees(math.atan2(-2.0 * (W * X + Y * Z), 1.0 - 2.0 * (X * X + Z * Z)))
    return [pitch, yaw, roll]


def norm_axis(a):
    a = math.fmod(a, 360.0)
    if a > 180.0:
        a -= 360.0
    if a < -180.0:
        a += 360.0
    return a


def swing_twist_x(q):
    """q = swing * twist with twist about X: twist = normalised (x, 0, 0, w)."""
    q = q_norm(q)
    twist = q_norm([q[0], 0.0, 0.0, q[3]]) if abs(q[0]) + abs(q[3]) > 1e-9 else [0.0, 0.0, 0.0, 1.0]
    swing = q_mul(q, q_inv(twist))
    return swing, twist


def pca_dir(points):
    """Dominant direction of a point set (power iteration on the 3x3 covariance)."""
    c = mean(points)
    cov = [[0.0] * 3 for _ in range(3)]
    for p in points:
        d = sub(p, c)
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    v = [0.0, 0.0, -1.0]
    for _ in range(60):
        w = [sum(cov[i][j] * v[j] for j in range(3)) for i in range(3)]
        n = length(w)
        if n < 1e-12:
            break
        v = mul(w, 1.0 / n)
    return v, c


# ------------------------------------------------------------------------------------------------ grips
def grip_geometry(name, spec):
    """The 'body' vertices under grip_r in 1 cm z slabs: backstrap tracked down, front strap tracked up, axis through
    the clean mid-points, the seat axis point, frame and extents."""
    mesh = load(spec['mesh'])
    pos = u.HoverAuthoring.skeletal_mesh_vertex_positions(mesh, 0)
    bones = u.HoverAuthoring.skeletal_mesh_vertex_bones(mesh, 0)
    pts = [[float(p.x), float(p.y), float(p.z)] for p in pos]
    bone_names = [str(b) for b in bones]
    n_all = len(pts)
    if not n_all or len(bone_names) != n_all:
        raise RuntimeError('%s: no render vertices (%d / %d)' % (name, n_all, len(bone_names)))
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    counts = {}
    for b in bone_names:
        counts[b] = counts.get(b, 0) + 1
    body = [p for p, b in zip(pts, bone_names) if b == spec['bone']]
    x0, x1 = spec['x_window']
    yh = spec['y_half']
    cand = [p for p in body if p[2] < spec['z_top'] + 1.0 and abs(p[1]) <= yh and x0 <= p[0] <= x1]
    # Slabs: index k holds z in [z_top - k - 1, z_top - k).
    slabs = {}
    for p in cand:
        k = int(math.floor(spec['z_top'] - p[2]))
        if k >= 0:
            slabs.setdefault(k, []).append(p)
    if not slabs:
        raise RuntimeError('%s: no body vertices under z=%.1f' % (name, spec['z_top']))
    # Backstrap tracked downward.
    back = {}
    lo_b, hi_b = spec['back_start']
    prev = None
    for k in sorted(slabs):
        rows = slabs[k]
        if prev is None:
            xs = [p[0] for p in rows if lo_b <= p[0] <= hi_b]
        else:
            xs = [p[0] for p in rows if prev - 2.5 <= p[0] <= prev + 1.5]
        if len(xs) < 3:
            break
        back[k] = min(xs)
        prev = back[k]
    if len(back) < 4:
        raise RuntimeError('%s: backstrap tracked over only %d slabs' % (name, len(back)))
    # Grip bottom: the lowest slab with a tracked backstrap and >= 5 verts within 9 cm ahead of it.
    bottom_k = max(k for k in back if sum(1 for p in slabs[k] if back[k] - 0.5 <= p[0] <= back[k] + 9.0) >= 5)
    # Front strap tracked upward from the bottom: max x of the verts within 9 cm ahead of the backstrap; stops where
    # it jumps forward by more than 1.5 cm (the trigger guard / receiver junction).
    front = {}
    prev = None
    for k in range(bottom_k, -1, -1):
        if k not in back:
            break
        xs = [p[0] for p in slabs[k] if back[k] - 0.5 <= p[0] <= back[k] + 9.0]
        if len(xs) < 3:
            break
        f = max(xs)
        if prev is not None and f - prev > 1.5:
            break
        front[k] = f
        prev = f
    # Clean slabs: both straps known and the backstrap still raking back (a backstrap that moves forward again is
    # the rounded floor plate / knob of a short grip, the SMG's below 4 cm).
    clean = []
    for k in sorted(front):
        if k not in back:
            continue
        if k > 0 and (k - 1) in back and back[k] > back[k - 1] + 0.3:
            break
        clean.append(k)
    if len(clean) < 3:
        raise RuntimeError('%s: only %d clean slabs with both straps (back %s, front %s)' % (name, len(clean), back, front))
    mids = [[(back[k] + front[k]) * 0.5, 0.0, spec['z_top'] - k - 0.5] for k in clean]
    # y centre from the grip verts of those slabs.
    ys = []
    for k in clean:
        ys.extend(p[1] for p in slabs[k] if back[k] - 0.2 <= p[0] <= front[k] + 0.2)
    yc = sum(ys) / len(ys) if ys else 0.0
    for m in mids:
        m[1] = yc
    G, c = pca_dir(mids)
    if G[2] > 0:
        G = mul(G, -1.0)
    # Top: the axis at grip_r height (z = 0, the rig convention's grip top centre); the grip's length runs from there
    # to the bottom slab; A: min(4.5, grip_len / 2) cm down the axis (the SMG's grip is 6 cm tall).
    t = (0.0 - c[2]) / G[2] if abs(G[2]) > 1e-6 else 0.0
    top = add(c, mul(G, t))
    grip_len = (bottom_k + 1.0) - spec['z_top']
    seat_depth = min(SEAT_DEPTH_CM, grip_len * 0.5)
    A = add(top, mul(G, seat_depth))
    Gf = norm(perp([1.0, 0.0, 0.0], G))
    Gr = norm(cross(Gf, G))
    # Table and the seat slab's extents.
    table = []
    used = 0
    for k in sorted(back):
        rows = [p for p in slabs[k] if back[k] - 0.2 <= p[0] <= (front.get(k, back[k] + 9.0)) + 0.2]
        used += len(rows)
        table.append({'z_from': spec['z_top'] - k - 1, 'z_to': spec['z_top'] - k, 'back_x': round(back[k], 2),
                      'front_x': round(front[k], 2) if k in front else None, 'clean': k in clean,
                      'vertices': len(rows), 'y_min': round(min(p[1] for p in rows), 2) if rows else None,
                      'y_max': round(max(p[1] for p in rows), 2) if rows else None})
    seat_k = int(math.floor(spec['z_top'] - A[2]))
    seat_slab = next((r for r in table if int(math.floor(spec['z_top'] - r['z_to'])) == seat_k), None)
    if not seat_slab or seat_slab['front_x'] is None:
        seat_slab = next((r for r in table if r['clean']), table[0])
    depth = (seat_slab['front_x'] - seat_slab['back_x']) if seat_slab['front_x'] is not None else None
    width = (seat_slab['y_max'] - seat_slab['y_min']) if seat_slab['y_max'] is not None else None
    rake = angle_deg(G, [0.0, 0.0, -1.0])
    back_rake = math.degrees(math.atan2(back[clean[0]] - back[clean[-1]], clean[-1] - clean[0])) if clean[-1] > clean[0] else None
    out = {'mesh': spec['mesh'], 'grip_bone': spec['bone'], 'vertices_total': n_all, 'vertices_body_bone': len(body),
           'vertices_candidates': len(cand), 'vertices_grip_used': used, 'slabs_tracked': len(back),
           'slabs_clean_both_straps': clean, 'grip_length_cm': grip_len, 'seat_depth_cm': seat_depth,
           'bone_vertex_counts': counts, 'mesh_bounds_cm': [rnd(lo, 2), rnd(hi, 2)],
           'axis_down_G': rnd(G, 4), 'rake_from_vertical_deg': round(rake, 2), 'backstrap_rake_deg': round(back_rake, 2) if back_rake is not None else None,
           'rake_back': G[0] < 0, 'top_at_grip_r_height': rnd(top, 3), 'z_top_first_slab': spec['z_top'],
           'seat_axis_point_A': rnd(A, 3), 'grip_forward_Gf': rnd(Gf, 4), 'grip_right_Gr': rnd(Gr, 4),
           'grip_depth_at_seat_cm': round(depth, 2) if depth is not None else None,
           'grip_width_at_seat_cm': round(width, 2) if width is not None else None,
           'grip_y_centre_cm': round(yc, 2), 'seat_slab': seat_slab, 'slab_table': table,
           'method': 'backstrap tracked down / front strap tracked up per 1 cm z slab; PCA line through the clean mid-points'}
    try:
        j = json.loads(Path(spec['json']).read_text(errors='replace'))
        jb = j.get('bounds_cm')
        out['rig_json_bounds_cm'] = jb
        if jb:
            diff = max(abs(jb[0][i] - lo[i]) for i in range(3) if i != 1) + max(abs(jb[1][i] - hi[i]) for i in range(3) if i != 1)
            out['rig_json_bounds_xz_abs_diff_sum_cm'] = round(diff, 2)
            assertion('%s: render vertices are in the rig JSON frame (x/z bounds within 3 cm)' % name, diff < 3.0,
                      {'render': out['mesh_bounds_cm'], 'json': jb, 'diff': round(diff, 2)}, '< 3 cm')
        sockets = j.get('sockets_cm') or j.get('sockets_cm_ue') or j.get('sockets')
        out['rig_json_sockets'] = sockets if isinstance(sockets, dict) else None
    except Exception as e:
        out['rig_json_error'] = str(e)
    # The revolver's grip_r sits at the top-FRONT of its 7 cm deep grip, so its axis crosses z = 0 about 4 cm behind.
    assertion('%s: grip found under grip_r (>= 120 vertices, >= 3 clean slabs, top within 5 cm of grip_r, rakes back 5-50 deg, 5-13 cm long)'
              % name, used >= 120 and len(clean) >= 3 and length(top) < 5.0 and G[0] < 0 and 5.0 <= rake <= 50.0 and 5.0 <= grip_len <= 13.0,
              {'vertices': used, 'clean_slabs': len(clean), 'top': rnd(top, 2), 'rake_deg': round(rake, 1),
               'axis': rnd(G, 3), 'grip_length_cm': grip_len})
    assertion('%s: grip cross-section at the seat looks like a grip (depth 2-8 cm, width 1.5-5 cm)' % name,
              depth is not None and 2.0 <= depth <= 8.0 and width is not None and 1.5 <= width <= 5.0,
              {'depth_cm': out['grip_depth_at_seat_cm'], 'width_cm': out['grip_width_at_seat_cm']})
    log(name, 'grip axis', rnd(G, 3), 'rake', round(rake, 1), 'top', rnd(top, 2), 'A', rnd(A, 2), 'len', grip_len,
        'verts', used, 'depth/width', out['grip_depth_at_seat_cm'], out['grip_width_at_seat_cm'])
    return out


def grips():
    for name, spec in GUNS.items():
        try:
            R['grips'][name] = grip_geometry(name, spec)
        except Exception:
            R['errors'].append('%s grip: %s' % (name, traceback.format_exc()))
            log('ERROR', name, R['errors'][-1][-600:])
    # Current rig values (folded out of the fist frame below; zero before AuthorGunRigs.py writes these).
    for name, spec in GUNS.items():
        try:
            rig = load(spec['rig'])
            seat = rig.get_editor_property('grip_seat_offset')
            rot = rig.get_editor_property('grip_rotation_offset')
            S['rig_values'][name] = {'seat': v3(seat), 'rot_pyr': [float(rot.pitch), float(rot.yaw), float(rot.roll)],
                                     'rot_q': q4(rot.quaternion())}
        except Exception as e:
            S['rig_values'][name] = {'error': str(e)}
    R['rig_values_before'] = S['rig_values']


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
    """One tick, everything in the held gun's frame, relative to the right palm centre."""
    g = gun(p)
    gt = g.get_world_transform()
    gq = q4(gt.rotation)
    go = v3(gt.translation)
    gqi = q_inv(gq)
    locs = {b: mesh_loc(p, b) for b in HAND_BONES}
    missing = [b for b, v in locs.items() if v is None]
    if missing:
        raise RuntimeError('body mesh lacks hand bones: %s' % missing)
    P = mul(add(locs['hand_r'], locs['middle_01_r']), 0.5)
    to_gun_rel = lambda w: q_rotate(gqi, sub(w, P))     # world point -> gun space, palm-relative (cm)
    dir_gun = lambda d: q_rotate(gqi, d)
    hq = mesh_quat(p, 'hand_r')
    rig = p.get_gun_rig()
    pose = p.get_stance_aim_pose()
    rows = {b: rnd(to_gun_rel(v), 3) for b, v in locs.items()}
    return {'t': round(t, 3), 'stance': stance, 'rig': rig.get_name() if rig else None,
            'stance_pose': pose.get_name() if pose else None, 'aiming': bool(p.is_aiming()),
            'bones_gun_cm_from_palm': rows,
            'palm_r_gun_cm_from_origin': rnd(q_rotate(gqi, sub(P, go)), 3),
            'gun_points_gun_cm_from_palm': {n: rnd(to_gun_rel(gun_world(p, n)), 2) for n in GUN_POINTS if gun_world(p, n)},
            'finger_dir_gun': rnd(norm(dir_gun(sub(locs['middle_01_r'], locs['hand_r']))), 4),
            'thumb_base_dir_gun': rnd(norm(dir_gun(sub(locs['thumb_01_r'], locs['hand_r']))), 4),
            'index_base_dir_gun': rnd(norm(dir_gun(sub(locs['index_01_r'], locs['hand_r']))), 4),
            'pinky_base_dir_gun': rnd(norm(dir_gun(sub(locs['pinky_01_r'], locs['hand_r']))), 4),
            'hand_r_axes_gun': {ax: rnd(dir_gun(q_rotate(hq, e)), 4) for ax, e in
                                (('X', [1, 0, 0]), ('Y', [0, 1, 0]), ('Z', [0, 0, 1]))},
            'gun_axes_in_mannequin': {ax: rnd(q_rotate(q_inv(q4(p.mesh.get_world_transform().rotation)), q_rotate(gq, e)), 3)
                                      for ax, e in (('X', [1, 0, 0]), ('Y', [0, 1, 0]), ('Z', [0, 0, 1]))},
            'gun_forward_vs_aim_ray_deg': round(angle_deg(q_rotate(gq, [1, 0, 0]),
                                                           q_rotate(q4(p.get_editor_property('gun_aim_world_rotation')), [1, 0, 0])), 3),
            'control_rotation': [round(x, 2) for x in (lambda r: (r.pitch, r.yaw, r.roll))(S['pc'].get_control_rotation())]}


def mean_dir(rows, key, sub_key=None):
    return norm(mean([(r[key][sub_key] if sub_key else r[key]) for r in rows]))


def pick_axis(axes, direction):
    best = None
    for i in range(3):
        for sign in (1, -1):
            a = mul(axes[i], sign)
            d = dot(a, norm(direction))
            if best is None or d > best[1]:
                best = (('+' if sign > 0 else '-') + 'XYZ'[i], round(d, 3), a)
    return best


def analyse_fist(stance, rows, q0):
    """Average the settled window: bar axis B (knuckle lines), palm normal N (hand_r +Y), finger direction F, the
    tunnel centre Tc (finger-ring mean), hand_r axis convention. q0 = the rig rotation the samples were taken under
    (folded out so the frame is the aim-ray gun frame)."""
    unfold = lambda v: q_rotate(q0, v)
    F = norm(unfold(mean_dir(rows, 'finger_dir_gun')))
    T = norm(unfold(mean_dir(rows, 'thumb_base_dir_gun')))
    I = norm(unfold(mean_dir(rows, 'index_base_dir_gun')))
    K = norm(unfold(mean_dir(rows, 'pinky_base_dir_gun')))
    axes = [norm(unfold(mean_dir(rows, 'hand_r_axes_gun', ax))) for ax in 'XYZ']
    stability = max(angle_deg(r['finger_dir_gun'], mean_dir(rows, 'finger_dir_gun')) for r in rows)
    pos = lambda b: norm_vec_mean(rows, b, unfold)
    j01 = {b: pos(b + '_01_r') for b in ('index', 'middle', 'ring', 'pinky')}
    j02 = {b: pos(b + '_02_r') for b in ('index', 'middle', 'ring', 'pinky')}
    j03 = {b: pos(b + '_03_r') for b in ('index', 'middle', 'ring', 'pinky')}
    thumb = {b: pos('thumb_%s_r' % b) for b in ('01', '02', '03')}
    # Bar axis: the knuckle lines index -> pinky, both rows, averaged, pointing down.
    line01 = norm(sub(j01['pinky'], j01['index']))
    line02 = norm(sub(j02['pinky'], j02['index']))
    B = norm(add(line01, line02))
    flipped = False
    if B[2] > 0:
        B = mul(B, -1.0)
        flipped = True
    # Palm normal: hand_r's local +Y (hand_axes.json: hand_l palm = -Y; the right hand mirrors), perpendicular to B.
    N = norm(perp(axes[1], B))
    N_thumb = norm(perp(cross(F, T), F))
    N_plane = norm(perp(cross(K, I), F))
    n_label, n_dot, _ = pick_axis(axes, N)
    f_label, f_dot, _ = pick_axis(axes, F)
    b_label, b_dot, _ = pick_axis(axes, B)
    B_cross = norm(cross(N, F))
    if B_cross[2] > 0:
        B_cross = mul(B_cross, -1.0)
    # Ring around the grip: palm surface, knuckle rows, thumb base. Tc = their mean.
    surface = mul(N, PALM_SURFACE_CM)
    m01, m02, m03 = mean(list(j01.values())), mean(list(j02.values())), mean(list(j03.values()))
    ring = [surface, m01, m02, m03, thumb['01']]
    Tc = mean(ring)
    Tc_no_thumb = mean([surface, m01, m02, m03])
    # Contact alternative: grip right face on the palm surface, back face 1 cm ahead of the thumb base, for a grip of
    # depth d / width w: Tc = surface + N * w/2 + F' * (thumb_01.F + 1 + d/2) (reported per gun in solve()).
    radius = length(perp(sub(Tc, surface), B))
    last = rows[-1]
    out = {'ticks_in_window': len(rows), 'window_s': [rows[0]['t'], rows[-1]['t']],
           'finger_dir_stability_deg': round(stability, 2),
           'finger_dir_F_gun': rnd(F, 4), 'thumb_base_dir_gun': rnd(T, 4), 'index_base_dir_gun': rnd(I, 4),
           'pinky_base_dir_gun': rnd(K, 4),
           'palm_normal_N_gun': rnd(N, 4), 'palm_normal_source': 'hand_r local +Y made perpendicular to B',
           'palm_normal_from_thumb_gun': rnd(N_thumb, 4), 'palm_normal_from_pinky_x_index_gun': rnd(N_plane, 4),
           'palm_normal_vs_thumb_deg': round(angle_deg(N, N_thumb), 2), 'palm_normal_vs_plane_deg': round(angle_deg(N, N_plane), 2),
           'bar_axis_B_gun_down': rnd(B, 4), 'bar_axis_source': 'mean of the index->pinky knuckle lines (_01 MCP row, _02 row)',
           'bar_axis_line01_gun': rnd(line01, 4), 'bar_axis_line02_gun': rnd(line02, 4),
           'bar_axis_from_cross_N_F_gun': rnd(B_cross, 4), 'bar_axis_vs_cross_deg': round(angle_deg(B, B_cross), 2),
           'bar_axis_flipped_to_point_down': flipped,
           'bar_rake_from_vertical_deg': round(angle_deg(B, [0.0, 0.0, -1.0]), 2),
           'hand_r_axes_gun': {ax: rnd(axes[i], 4) for i, ax in enumerate('XYZ')},
           'hand_r_axis_convention': 'hand_r local %s along the fingers (dot %.2f), local %s out of the palm (dot %.2f), '
                                     'local %s down the bar / toward the pinky side (dot %.2f)' %
                                     (f_label, f_dot, n_label, n_dot, b_label, b_dot),
           'joints_gun_cm_from_palm': {'hand_r': rnd(pos('hand_r'), 2),
                                       **{b + '_01_r': rnd(v, 2) for b, v in j01.items()},
                                       **{b + '_02_r': rnd(v, 2) for b, v in j02.items()},
                                       **{b + '_03_r': rnd(v, 2) for b, v in j03.items()},
                                       **{'thumb_%s_r' % b: rnd(v, 2) for b, v in thumb.items()}},
           'ring_points_gun_cm_from_palm': {'palm_surface': rnd(surface, 2), 'knuckles_01_mean': rnd(m01, 2),
                                            'joints_02_mean': rnd(m02, 2), 'joints_03_mean': rnd(m03, 2),
                                            'thumb_01': rnd(thumb['01'], 2)},
           'tunnel_centre_Tc_gun_cm_from_palm': rnd(Tc, 3), 'tunnel_centre_source': 'mean of the five ring points',
           'tunnel_centre_without_thumb_gun_cm': rnd(Tc_no_thumb, 3),
           'tunnel_radius_perp_B_cm': round(radius, 2),
           'tunnel_centre_along_N_cm': round(dot(Tc, N), 2), 'tunnel_centre_along_F_cm': round(dot(Tc, F), 2),
           'tunnel_centre_along_B_cm': round(dot(Tc, B), 2),
           'rig_rotation_folded_out_q': rnd(q0, 4),
           'live': {k: last[k] for k in ('rig', 'stance_pose', 'aiming', 'palm_r_gun_cm_from_origin',
                                         'gun_points_gun_cm_from_palm', 'gun_axes_in_mannequin',
                                         'gun_forward_vs_aim_ray_deg', 'control_rotation')}}
    assertion('%s: finger direction stable over the settled window (< 2 deg)' % stance, stability < 2.0, round(stability, 2), '< 2 deg')
    # The thumb cross-check is weak in a fist (the thumb metacarpal points up out of the palm plane: 45-47 deg here).
    assertion('%s: hand_r +Y palm normal agrees with the finger-plane normal (< 25 deg) and roughly with the thumb one (< 60 deg)' % stance,
              out['palm_normal_vs_plane_deg'] < 25.0 and out['palm_normal_vs_thumb_deg'] < 60.0,
              {'vs_plane_deg': out['palm_normal_vs_plane_deg'], 'vs_thumb_deg': out['palm_normal_vs_thumb_deg']})
    assertion('%s: the two knuckle lines agree on the bar axis (< 25 deg), no flip, rake 0-30 deg from vertical' % stance,
              angle_deg(line01, line02) < 25.0 and not flipped and out['bar_rake_from_vertical_deg'] <= 30.0,
              {'line01_vs_line02_deg': round(angle_deg(line01, line02), 2), 'flipped': flipped,
               'rake_deg': out['bar_rake_from_vertical_deg'], 'B': out['bar_axis_B_gun_down']})
    assertion('%s: the fist tunnel centre is 2-6 cm ahead of the palm centre along the fingers and 1-4 cm out of the palm' % stance,
              2.0 <= out['tunnel_centre_along_F_cm'] <= 6.0 and 1.0 <= out['tunnel_centre_along_N_cm'] <= 4.0,
              {'along_F_cm': out['tunnel_centre_along_F_cm'], 'along_N_cm': out['tunnel_centre_along_N_cm'], 'Tc': out['tunnel_centre_Tc_gun_cm_from_palm']})
    return out


def norm_vec_mean(rows, bone, unfold):
    return unfold(mean([r['bones_gun_cm_from_palm'][bone] for r in rows]))


# ------------------------------------------------------------------------------------------------ result
def solve(name, grip, fist):
    """Q (grip frame -> fist frame, gun space), swing-limited, and the seat S = A - Q^-1 Tc, with alternatives."""
    G, Gf = grip['axis_down_G'], grip['grip_forward_Gf']
    Gr = norm(cross(Gf, G))
    N, B, F = fist['palm_normal_N_gun'], fist['bar_axis_B_gun_down'], fist['finger_dir_F_gun']
    Tc = fist['tunnel_centre_Tc_gun_cm_from_palm']
    surface = fist['ring_points_gun_cm_from_palm']['palm_surface']
    # The fist's "back" direction: from the tunnel centre to the palm surface point, perpendicular to B (the palm
    # heel / thumb web side is where the backstrap goes). Grip back = -Gf.
    fist_back = norm(perp(sub(surface, Tc), B))
    fist_fwd = mul(fist_back, -1.0)
    fist_right = norm(cross(fist_fwd, B))
    q_grip = q_from_basis(Gf, Gr, mul(G, -1.0))
    q_fist = q_from_basis(fist_fwd, fist_right, mul(B, -1.0))
    Q_full = q_norm(q_mul(q_fist, q_inv(q_grip)))
    if Q_full[3] < 0:
        Q_full = [-x for x in Q_full]
    err_axis = angle_deg(q_rotate(Q_full, G), B)
    err_fwd = angle_deg(q_rotate(Q_full, Gf), fist_fwd)
    Q_axis_only = find_between(G, B)
    variants = {}
    for label, Q in (('full', Q_full), ('axis_only', Q_axis_only)):
        variants[label] = describe_rotation(q_clamp(Q, ROT_CLAMP_DEG), grip, fist, clamped_from=q_angle_deg(Q))
    Qc = q_clamp(Q_full, ROT_CLAMP_DEG)
    swing, twist = swing_twist_x(Qc)
    Ql = q_norm(q_mul(q_clamp(swing, SWING_LIMIT_DEG), twist))
    variants['limited'] = describe_rotation(Ql, grip, fist, clamped_from=q_angle_deg(Qc))
    chosen_label = 'limited' if variants['full']['barrel_vs_aim_ray_deg'] > SWING_LIMIT_DEG + 1e-6 else 'full'
    chosen = variants[chosen_label]
    Qsel = chosen['quat']
    A = grip['seat_axis_point_A']
    S_seat = sub(A, q_rotate(q_inv(Qsel), Tc))
    landed = q_rotate(Qsel, sub(A, S_seat))
    # Alternatives for the tuning pass (same Q): ring without the thumb; contact rule (right face on the palm surface,
    # back face 1 cm ahead of the thumb base) for this grip's measured depth / width.
    d = grip['grip_depth_at_seat_cm'] or 4.0
    w = grip['grip_width_at_seat_cm'] or 3.0
    Fp = norm(perp(F, B))
    thumb01 = fist['joints_gun_cm_from_palm']['thumb_01_r']
    Tc_contact = add(add(surface, mul(N, w * 0.5)), mul(Fp, dot(thumb01, Fp) + 1.0 + d * 0.5 - dot(surface, Fp)))
    alt = {'ring_without_thumb': rnd(sub(A, q_rotate(q_inv(Qsel), fist['tunnel_centre_without_thumb_gun_cm'])), 2),
           'contact_palm_and_thumb_web': rnd(sub(A, q_rotate(q_inv(Qsel), Tc_contact)), 2),
           'literal_axis_point_A': A}
    out = {'grip_axis_G': G, 'grip_forward_Gf': Gf, 'fist_bar_B': B, 'fist_palm_normal_N': N,
           'fist_back_dir': rnd(fist_back, 4),
           'misalignment_before_deg': {'grip_axis_vs_fist_bar': round(angle_deg(G, B), 2),
                                       'grip_back_vs_fist_back': round(angle_deg(mul(Gf, -1.0), fist_back), 2)},
           'Q_full_unclamped_deg': round(q_angle_deg(Q_full), 2), 'Q_full_unclamped_pitch_yaw_roll': rnd(q_to_rotator(Q_full), 2),
           'Q_full_maps_G_to_B_err_deg': round(err_axis, 3), 'Q_full_maps_Gf_to_fist_fwd_err_deg': round(err_fwd, 3),
           'variants': variants, 'chosen_variant': chosen_label, 'swing_limit_deg': SWING_LIMIT_DEG,
           'rot_deg_pitch_yaw_roll': chosen['rotator_pitch_yaw_roll'], 'rot_quat': rnd(Qsel, 5),
           'seat_axis_point_A_cm': A, 'tunnel_centre_Tc_cm_from_palm': Tc,
           'seat_cm': rnd(S_seat, 2), 'seat_cm_exact': rnd(S_seat, 4),
           'seat_alternatives_cm': alt, 'seat_vs_literal_axis_point_cm': rnd(sub(S_seat, A), 2),
           'check_axis_point_lands_on_tunnel_err_cm': round(length(sub(landed, Tc)), 4),
           'residual_after_chosen_deg': {'grip_axis_vs_fist_bar': round(angle_deg(q_rotate(Qsel, G), B), 2),
                                         'grip_back_vs_fist_back': round(angle_deg(q_rotate(Qsel, mul(Gf, -1.0)), fist_back), 2)},
           'where_things_land_gun_cm': {
               'palm_centre': rnd(S_seat, 2),
               'hand_r_wrist': rnd(add(S_seat, q_rotate(q_inv(Qsel), fist['joints_gun_cm_from_palm']['hand_r'])), 2),
               'knuckles_01_mean': rnd(add(S_seat, q_rotate(q_inv(Qsel), fist['ring_points_gun_cm_from_palm']['knuckles_01_mean'])), 2),
               'joints_02_mean': rnd(add(S_seat, q_rotate(q_inv(Qsel), fist['ring_points_gun_cm_from_palm']['joints_02_mean'])), 2),
               'thumb_01': rnd(add(S_seat, q_rotate(q_inv(Qsel), thumb01)), 2),
               'grip_back_x_at_seat': grip['seat_slab']['back_x'], 'grip_front_x_at_seat': grip['seat_slab']['front_x']}}
    assertion('%s: Q maps the grip frame onto the fist frame (construction check < 0.5 deg)' % name,
              err_axis < 0.5 and err_fwd < 0.5, {'axis_err': round(err_axis, 3), 'fwd_err': round(err_fwd, 3)})
    assertion('%s: chosen rotation within 25 deg and barrel deviation within the 6 deg verify budget' % name,
              chosen['angle_deg'] <= ROT_CLAMP_DEG + 1e-3 and chosen['barrel_vs_aim_ray_deg'] <= SWING_BUDGET_DEG,
              {'angle_deg': chosen['angle_deg'], 'barrel_vs_aim_ray_deg': chosen['barrel_vs_aim_ray_deg'], 'variant': chosen_label})
    assertion('%s: seat is below grip_r and within the grip envelope (z in [-9, -1], |y| < 4, x in [-12, 4])' % name,
              -9.0 <= S_seat[2] <= -1.0 and abs(S_seat[1]) < 4.0 and -12.0 <= S_seat[0] <= 4.0, rnd(S_seat, 2))
    assertion('%s: rotator round-trips through unreal.Rotator.quaternion() (< 0.05 deg)' % name,
              chosen['rotator_roundtrip_err_deg'] is not None and chosen['rotator_roundtrip_err_deg'] < 0.05,
              chosen['rotator_roundtrip_err_deg'])
    log(name, 'seat', rnd(S_seat, 2), 'rot(p,y,r)', chosen['rotator_pitch_yaw_roll'], 'variant', chosen_label,
        'barrel dev', chosen['barrel_vs_aim_ray_deg'], 'angle', chosen['angle_deg'], 'full wanted', out['Q_full_unclamped_pitch_yaw_roll'])
    return out


def find_between(a, b):
    """FQuat::FindBetweenNormals."""
    a, b = norm(a), norm(b)
    w = 1.0 + dot(a, b)
    if w < 1e-6:
        # Opposite: any perpendicular axis.
        axis = norm(cross(a, [0, 0, 1])) if abs(a[2]) < 0.9 else norm(cross(a, [1, 0, 0]))
        return q_axis_angle(axis, 180.0)
    c = cross(a, b)
    return q_norm([c[0], c[1], c[2], w])


def describe_rotation(Q, grip, fist, clamped_from=None):
    Q = q_norm(Q)
    if Q[3] < 0:
        Q = [-x for x in Q]
    pyr = q_to_rotator(Q)
    # Round trip through the engine: unreal.Rotator(roll, pitch, yaw).quaternion() must give Q back.
    try:
        eq = q4(u.Rotator(roll=pyr[2], pitch=pyr[0], yaw=pyr[1]).quaternion())
        rt = q_angle_deg(q_mul(eq, q_inv(Q)))
    except Exception as e:
        rt = None
        R['notes'].append('rotator round trip failed: %s' % e)
    swing, twist = swing_twist_x(Q)
    return {'quat': rnd(Q, 6), 'angle_deg': round(q_angle_deg(Q), 2),
            'clamped_from_deg': round(clamped_from, 2) if clamped_from is not None else None,
            'rotator_pitch_yaw_roll': rnd(pyr, 2), 'rotator_roundtrip_err_deg': round(rt, 4) if rt is not None else None,
            'barrel_vs_aim_ray_deg': round(angle_deg(q_rotate(Q, [1, 0, 0]), [1, 0, 0]), 2),
            'swing_deg': round(q_angle_deg(swing), 2), 'twist_about_x_deg': round(q_angle_deg(twist), 2),
            'grip_axis_after_vs_fist_bar_deg': round(angle_deg(q_rotate(Q, grip['axis_down_G']), fist['bar_axis_B_gun_down']), 2),
            'grip_axis_after_vs_vertical_deg': round(angle_deg(q_rotate(Q, grip['axis_down_G']), [0.0, 0.0, -1.0]), 2)}


def results():
    seats = {}
    for name, spec in GUNS.items():
        grip = R['grips'].get(name)
        fist = R['fists'].get(spec['stance'])
        if not grip or not fist:
            R['errors'].append('%s: missing grip (%s) or fist (%s)' % (name, bool(grip), bool(fist)))
            continue
        try:
            res = solve(name, grip, fist)
            R['result'][name] = res
            seats[name] = {'seat_cm': res['seat_cm'], 'rot_deg': res['rot_deg_pitch_yaw_roll'],
                           'vertices_used': grip['vertices_grip_used'], 'stance': spec['stance'],
                           'variant': res['chosen_variant'],
                           'barrel_vs_aim_ray_deg': res['variants'][res['chosen_variant']]['barrel_vs_aim_ray_deg'],
                           'full_alignment_wanted_pitch_yaw_roll': res['Q_full_unclamped_pitch_yaw_roll'],
                           'seat_alternatives_cm': res['seat_alternatives_cm']}
        except Exception:
            R['errors'].append('%s solve: %s' % (name, traceback.format_exc()))
    R['seats'] = seats
    R['rig_spec_lines'] = {n: "'GripSeatOffset': (%s, %s, %s), 'GripRotationOffset': (%s, %s, %s)," % tuple(
        s['seat_cm'] + s['rot_deg']) for n, s in seats.items()}


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
            rows = S['samples']['rifle']
            R['pie']['rifle_samples'] = rows
            R['fists']['rifle'] = analyse_fist('rifle', rows, S['rig_values'].get('M4A1', {}).get('rot_q', [0, 0, 0, 1]))
            assertion('PIE: rifle rig holds MF_Rifle_Idle_ADS while aiming',
                      rows[-1]['stance_pose'] == 'MF_Rifle_Idle_ADS' and rows[-1]['aiming'],
                      {k: rows[-1][k] for k in ('rig', 'stance_pose', 'aiming')})
            p.apply_gun_rig(S['rig'])
            phase('pistol_aim', t)
    elif ph == 'pistol_aim':
        if el >= SETTLE_S:
            S['samples']['pistol'].append(sample(p, t, 'pistol'))
        if el >= SETTLE_S + WINDOW_S:
            rows = S['samples']['pistol']
            R['pie']['pistol_samples'] = rows
            R['fists']['pistol'] = analyse_fist('pistol', rows, S['rig_values'].get('EM08', {}).get('rot_q', [0, 0, 0, 1]))
            assertion('PIE: EM_08 rig holds MF_Pistol_Idle_ADS while aiming',
                      rows[-1]['rig'] == 'DA_GunRig_EM08' and rows[-1]['stance_pose'] == 'MF_Pistol_Idle_ADS' and rows[-1]['aiming'],
                      {k: rows[-1][k] for k in ('rig', 'stance_pose', 'aiming')})
            press('RightMouseButton', False)
            results()
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
    marks = [i for i, l in enumerate(lines) if 'GRIP_SEAT pie start' in l]
    pie = marks[-1] if marks else 0
    bad = [l.strip()[:300] for l in lines[pie:] if re.search(r'Error|ensure|Ensure condition', l) and
           re.search(r'Anim|Skeleton|Retarget|HOVER_GUN|Sequence|Bone', l) and 'GRIP_SEAT' not in l]
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
    for st, f in R['fists'].items():
        log(st, f['hand_r_axis_convention'])
        log(st, 'F', f['finger_dir_F_gun'], 'N', f['palm_normal_N_gun'], 'B', f['bar_axis_B_gun_down'], 'Tc', f['tunnel_centre_Tc_gun_cm_from_palm'], 'ring', f['ring_points_gun_cm_from_palm'])
    for n, s in (R.get('seats') or {}).items():
        log(n, 'SEAT', s['seat_cm'], 'ROT(p,y,r)', s['rot_deg'], 'variant', s['variant'], 'verts', s['vertices_used'])
    for e in R['errors']:
        print('GRIP_SEAT error', e[:600], flush=True)


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
        print('GRIP_SEAT_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


def main():
    try:
        grips()
    except Exception:
        R['errors'].append('grips: ' + traceback.format_exc())
    save()
    if R['errors'] or not all(a['ok'] for a in R['assertions']):
        log('grip stage had errors/failures (continuing to PIE so the fist frame is still measured)')
    try:
        S['rig'] = load(RIG_EM08)
    except Exception:
        R['errors'].append('rig: ' + traceback.format_exc())
        save()
        u.SystemLibrary.quit_editor()
        return
    log('pie start')
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        R['errors'].append('load_level %s failed' % MAP)
        save()
        u.SystemLibrary.quit_editor()
        return
    u.EditorPythonScripting.set_keep_python_script_alive(True)
    S['handle'] = u.register_slate_post_tick_callback(tick)


main()
