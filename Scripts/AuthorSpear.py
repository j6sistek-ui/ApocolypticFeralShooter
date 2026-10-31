"""AuthorSpear.py - Vexa's spear for NYC Survival from Content/SpearAnimationsV2 (AFS 2026-10-31, spear item).

Needs the C++ from D:/AFS_Comparisons/OtherItems_20261031/spear/apply_spear.py built first (UHoverMeleeProfileAsset).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorSpear.py"
  Flags (inside the quoted -ExecutePythonScript value, after the path):
      --dry-run        measure and report, save nothing
      --reset-profile  refill DA_SpearProfile from FHoverMeleeProfile::SpearDefaults() before the measured values
      --allow-compat   if the IK batch retarget is unavailable, fall back to playing the UE4 clips through a compatible
                       skeleton (this edits the CLS SK_Mannequin's CompatibleSkeletons list, a pack asset; off by default)

What it does (only owned /Game/HoverPrototype/ assets are created or saved; pack assets are read, never saved):
 1. The pack's body clips are on its own UE4 mannequin skeleton (/Game/SpearAnimationsV2/Mannequin/Character/Mesh/
    UE4_Mannequin_Skeleton, 247 assets); the CLS driver that Vexa's body retargets from (HoverLocomotionBridge.cpp,
    SKM_Quinn_Simple on the CLS UE5 SK_Mannequin) has spine_01-05 / neck_01-02, so the clips are IK-retargeted with
    the project's RTG_UE4Manny_UE5Manny (StoneGolem demo rigs) onto SKM_Quinn_Simple: first duplicated to
    /Game/HoverPrototype/Spear/Source (owned copies, so the batch output lands in an owned folder), then retargeted,
    then renamed to /Game/HoverPrototype/Spear/Anims/AS_Spear_<Key>. An existing AS_Spear_<Key> is kept (idempotent).
 2. Each retargeted clip is sampled on the driver mesh (AnimPose API): forward / lateral axes, the contact time (front
    palm furthest forward for jab / thrust / heavy, peak lateral hand speed for the swing), the swing direction, the
    heavy wind-up (front palm furthest back before contact), which hand leads, the 2H hand spacing, and the head's
    reach at contact. The heavy thrust is the candidate with the deepest lunge.
 3. SM_Spear_01 (the pack's static spear) is measured: long axis, length, which end is the head (SK_Spear's HandL /
    HandR grip bones when its bounds match, else the vertex spread at each end), the rear-hand grip fraction.
 4. /Game/HoverPrototype/NYC/Weapons/DA_NYC_Spear: a duplicate of DA_AFS_Melee (the katana definition) with no
    WeaponActorClass (selecting it holsters the gun; UHoverCombatBridge owns the spear actor), SM_Spear_01 as its mesh,
    display name "Spear".
 5. /Game/HoverPrototype/Spear/DA_SpearProfile (UHoverMeleeProfileAsset): SpearDefaults() plus the measured clips,
    sweep times, arc, reach, wind-up and grip.
 6. DA_NYCWaves StartingEquipment: DA_NYC_Spear on the first free quickbar slot of 4, 3, 5 that is not the Ballista's
    (1), the pistol's (2) or the grenades'.
Receipt: D:/AFS_Comparisons/OtherItems_20261031/spear/author_receipt.json. Never run beside another AFS editor.
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

import unreal as u

ARGS = sys.argv[1:]
DRY = '--dry-run' in ARGS
RESET_PROFILE = '--reset-profile' in ARGS
ALLOW_COMPAT = '--allow-compat' in ARGS
OUT = Path('D:/AFS_Comparisons/OtherItems_20261031/spear')
OUT.mkdir(parents=True, exist_ok=True)
L = u.EditorAssetLibrary

PACK = '/Game/SpearAnimationsV2'
PACK_CHAR = PACK + '/Animations/Character'
PACK_MESH = PACK + '/Mannequin/Character/Mesh/SK_Mannequin'
PACK_SKEL = PACK + '/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton'
SPEAR_SM = PACK + '/Mesh/SM_Spear_01'
SPEAR_SK = PACK + '/Mesh/SK_Spear'
SPEAR_SK_SKEL = PACK + '/Mesh/SK_Spear_Skeleton'
DRIVER_MESH = '/Game/CLS/Core/Characters/Mannequins/Meshes/SKM_Quinn_Simple'
DRIVER_SKEL = '/Game/CLS/Core/Characters/Mannequins/Meshes/SK_Mannequin'
RTG = '/Game/StoneGolem/Demo/Characters/Mannequin_UE4/Rigs/RTG_UE4Manny_UE5Manny'
SPEAR_DIR = '/Game/HoverPrototype/Spear'
SRC_DIR = SPEAR_DIR + '/Source'
ANIM_DIR = SPEAR_DIR + '/Anims'
PROFILE = SPEAR_DIR + '/DA_SpearProfile'
KATANA_DEF = '/Game/HoverPrototype/ZombieEngine/DA_AFS_Melee'
SPEAR_DEF_DIR = '/Game/HoverPrototype/NYC/Weapons'
SPEAR_DEF = SPEAR_DEF_DIR + '/DA_NYC_Spear'
WAVES = '/Game/HoverPrototype/NYC/DA_NYCWaves'

# One consistent stance (2H Pose01) for the light chain and the stance loop, so strikes chain without a stance change.
CLIPS = {
    'Jab': PACK_CHAR + '/2Hand/Pose01/A_2H_01_Jab_Mid',
    'Thrust': PACK_CHAR + '/2Hand/Pose01/A_2H_01_Thrust_Mid',
    'Swing': PACK_CHAR + '/2Hand/Pose01/A_2H_01_Swing_HorizontalMid',
    'Stance': PACK_CHAR + '/2Hand/Pose01/A_2H_Idle_01',
    'Heavy_P1High': PACK_CHAR + '/2Hand/Pose01/A_2H_01_Thrust_High',
    'Heavy_P3Mid': PACK_CHAR + '/2Hand/Pose03/A_2H_03_Thrust_Mid',
    'Heavy_P4Mid': PACK_CHAR + '/2Hand/Pose04/A_2H_04_Thrust_Mid',
}
HEAVY_KEYS = ['Heavy_P4Mid', 'Heavy_P3Mid', 'Heavy_P1High']  # FHoverMeleeProfile::SpearDefaults() uses P4Mid
# Strike seconds the clip is rate-scaled to (never slower than the pack's own timing).
TARGET_DURATION = {'Jab': .55, 'Thrust': .70, 'Swing': .85, 'Heavy': .95}
SWING_HALF_ARC = 30.0
R = {'ok': False, 'dry_run': DRY, 'errors': [], 'warnings': [], 'clips': {}, 'measure': {}, 'mesh': {}, 'profile': {},
     'definition': {}, 'waves': {}, 'saved': [], 'started': time.strftime('%Y-%m-%d %H:%M:%S')}


def save_receipt():
    (OUT / 'author_receipt.json').write_text(json.dumps(R, indent=1, default=str))


def path_of(obj):
    return obj.get_path_name().split('.')[0] if obj else None


def load(path):
    return L.load_asset(path) if L.does_asset_exist(path) else None


def out_path(key):
    return '%s/AS_Spear_%s' % (ANIM_DIR, key)


def ensure_dir(path):
    if not DRY and not L.does_directory_exist(path):
        L.make_directory(path)


# ---------------------------------------------------------------------------------------------------------------------
# 1. Retarget
# ---------------------------------------------------------------------------------------------------------------------
def retarget_clips():
    for key, src in CLIPS.items():
        assert L.does_asset_exist(src), 'pack clip missing: ' + src
    todo = [k for k in CLIPS if not L.does_asset_exist(out_path(k))]
    R['clips']['kept'] = [k for k in CLIPS if k not in todo]
    R['clips']['todo'] = todo
    if not todo or DRY:
        return 'kept' if not todo else 'dry-run'
    ensure_dir(SRC_DIR)
    ensure_dir(ANIM_DIR)
    copies = {}
    for key in todo:
        name = CLIPS[key].rsplit('/', 1)[1]
        dup = '%s/%s' % (SRC_DIR, name)
        if not L.does_asset_exist(dup):
            assert L.duplicate_asset(CLIPS[key], dup), 'duplicate failed: ' + CLIPS[key]
        copies[key] = dup
    rtg, src_mesh, tgt_mesh = load(RTG), load(PACK_MESH), load(DRIVER_MESH)
    op = getattr(u, 'IKRetargetBatchOperation', None)
    if not (rtg and src_mesh and tgt_mesh and op and hasattr(op, 'duplicate_and_retarget')):
        R['warnings'].append('IK batch retarget unavailable (rtg=%s src=%s tgt=%s op=%s)' % (
            bool(rtg), bool(src_mesh), bool(tgt_mesh), bool(op)))
        return compat_fallback(copies)
    datas = [L.find_asset_data(p) for p in copies.values()]
    result, last = None, None
    # 5.8 signature (checked 2026-10-31): (assets, source_mesh, target_mesh, rtg, search, replace, prefix, suffix,
    # target_path, use_source_path, include_referenced_assets, overwrite_existing_files). The 8-positional form
    # also binds there, but with target_path '' the output did not land next to the copies; name the folder.
    for call in (lambda: op.duplicate_and_retarget(datas, src_mesh, tgt_mesh, rtg, search='', replace='', prefix='',
                                                   suffix='_Vexa', target_path=SRC_DIR, use_source_path=False,
                                                   include_referenced_assets=False, overwrite_existing_files=True),
                 lambda: op.duplicate_and_retarget(datas, src_mesh, tgt_mesh, rtg, '', '', '', '_Vexa', False),
                 lambda: op.duplicate_and_retarget(datas, src_mesh, tgt_mesh, rtg, '', '', '', '_Vexa'),
                 lambda: op.duplicate_and_retarget(assets_to_retarget=datas, source_mesh=src_mesh,
                                                   target_mesh=tgt_mesh, ik_retarget_asset=rtg, suffix='_Vexa')):
        try:
            result = call()
            break
        except TypeError as e:
            last = e
    if result is None:
        R['warnings'].append('duplicate_and_retarget rejected every signature: %s' % last)
        return compat_fallback(copies)
    made = {}
    for key, dup in copies.items():
        retargeted = dup + '_Vexa'
        if not L.does_asset_exist(retargeted):
            R['errors'].append('retarget output missing: ' + retargeted)
            continue
        assert L.rename_asset(retargeted, out_path(key)), 'rename failed: ' + retargeted
        seq = load(out_path(key))
        made[key] = {'path': out_path(key), 'skeleton': path_of(seq.get_editor_property('skeleton'))}
        L.save_loaded_asset(seq, False)
        R['saved'].append(out_path(key))
    R['clips']['retargeted'] = made
    return 'retargeted'


def compat_fallback(copies):
    if not ALLOW_COMPAT:
        R['errors'].append('no retargeted clips: rerun after fixing the IK batch retarget, or pass --allow-compat')
        return 'failed'
    # Plays the UE4 clips by bone name on the driver; spine_04/05 and neck_02 stay at the reference pose.
    helper = getattr(u.HoverAuthoring, 'make_skeleton_compatible', None)
    tgt, src = load(DRIVER_SKEL), load(PACK_SKEL)
    if not helper or not tgt or not src or not helper(tgt, src):
        R['errors'].append('compat fallback failed (helper=%s)' % bool(helper))
        return 'failed'
    L.save_loaded_asset(tgt, False)
    R['saved'].append(DRIVER_SKEL + ' (CompatibleSkeletons += pack UE4 skeleton)')
    for key, dup in copies.items():
        if not L.does_asset_exist(out_path(key)):
            assert L.rename_asset(dup, out_path(key)), 'rename failed: ' + dup
            R['saved'].append(out_path(key))
    R['warnings'].append('COMPAT mode: UE4 clips play through CompatibleSkeletons, not retargeted; judge the spine')
    return 'compat'


# ---------------------------------------------------------------------------------------------------------------------
# 2. Clip measurement
# ---------------------------------------------------------------------------------------------------------------------
def v3(t):
    return (t.x, t.y, t.z)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a):
    return math.sqrt(dot(a, a))


def lerp(a, b, t):
    return add(a, mul(sub(b, a), t))


def sample(seq, mesh):
    opts = u.AnimPoseEvaluationOptions()
    opts.optional_skeletal_mesh = mesh
    length = seq.get_play_length()
    n = max(30, int(round(length * 60)))
    rows = []
    for i in range(n + 1):
        t = min(length * i / n, max(0.0, length - 1e-4))
        pose = u.AnimPoseExtensions.get_anim_pose_at_time(seq, t, opts)
        get = lambda b: v3(pose.get_bone_pose(b, u.AnimPoseSpaces.WORLD).translation)  # noqa: E731
        row = {'t': t, 'root': get('root')}
        for side in ('r', 'l'):
            hand, middle = get('hand_' + side), get('middle_01_' + side)
            row[side] = lerp(hand, middle, .6)  # palm
        rows.append(row)
    return length, rows


def pick_axes(rows_by_key):
    """Forward = the horizontal axis along which the jab / thrust palms travel furthest from frame 0."""
    best = None
    for axis in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)):
        reach = 0.0
        for key in ('Jab', 'Thrust'):
            rows = rows_by_key.get(key)
            if not rows:
                continue
            f0 = max(dot(rows[0]['r'], axis), dot(rows[0]['l'], axis))
            reach += max(max(dot(r['r'], axis), dot(r['l'], axis)) for r in rows) - f0
        if best is None or reach > best[1]:
            best = (axis, reach)
    return best


def right_axis(fwd):
    """Lateral axis pointing to the character's right, from the reference pose's hands."""
    lat = (fwd[1], -fwd[0], 0.0)
    try:
        skel = load(DRIVER_SKEL)
        ref = u.AnimPoseExtensions.get_reference_pose(skel)
        hr = v3(ref.get_bone_pose('hand_r', u.AnimPoseSpaces.WORLD).translation)
        hl = v3(ref.get_bone_pose('hand_l', u.AnimPoseSpaces.WORLD).translation)
        if dot(sub(hr, hl), lat) < 0:
            lat = mul(lat, -1)
        return lat, 'reference pose'
    except Exception as e:  # noqa: BLE001
        R['warnings'].append('reference pose unavailable (%s); lateral axis assumed' % e)
        return lat, 'assumed'


def measure_thrust(rows, fwd):
    fronts = [max(dot(r['r'], fwd), dot(r['l'], fwd)) - dot(r['root'], fwd) for r in rows]
    c = max(range(len(rows)), key=lambda i: fronts[i])
    w = min(range(0, max(1, c)), key=lambda i: fronts[i]) if c > 0 else 0
    lead_left = dot(rows[c]['l'], fwd) > dot(rows[c]['r'], fwd)
    return {'contact_index': c, 'windup_index': w, 'front_peak_cm': round(fronts[c], 1),
            'lunge_cm': round(fronts[c] - fronts[0], 1), 'pullback_cm': round(fronts[0] - fronts[w], 1),
            'lead_left': lead_left}


def measure_swing(rows, lat):
    mids = [dot(lerp(r['r'], r['l'], .5), lat) for r in rows]
    vel = [0.0] + [(mids[i] - mids[i - 1]) / max(1e-4, rows[i]['t'] - rows[i - 1]['t']) for i in range(1, len(rows))]
    c = max(range(len(rows)), key=lambda i: abs(vel[i]))
    return {'contact_index': c, 'lateral_speed_cm_s': round(vel[c], 1), 'moving_right': vel[c] > 0}


def spacing(rows):
    d = [norm(sub(r['r'], r['l'])) for r in rows]
    return round(sum(d) / len(d), 1), round(min(d), 1), round(max(d), 1)


def tip_reach(row, fwd, lead_left, length, grip):
    rear, front = (row['r'], row['l']) if lead_left else (row['l'], row['r'])
    d = sub(front, rear)
    n = norm(d)
    if n < 1:
        return None
    tip = add(rear, mul(d, length * (1 - grip) / n))
    return round(dot(sub(tip, row['root']), fwd), 1)


# ---------------------------------------------------------------------------------------------------------------------
# 3. Spear mesh
# ---------------------------------------------------------------------------------------------------------------------
def box_info(box):
    mn, mx = (box.min.x, box.min.y, box.min.z), (box.max.x, box.max.y, box.max.z)
    size = [mx[i] - mn[i] for i in range(3)]
    a = max(range(3), key=lambda i: size[i])
    return mn, mx, size, a


def measure_mesh():
    sm = load(SPEAR_SM)
    assert sm, 'SM_Spear_01 missing'
    mn, mx, size, a = box_info(sm.get_bounding_box())
    info = {'path': SPEAR_SM, 'bounds_min': mn, 'bounds_max': mx, 'size': [round(s, 1) for s in size], 'long_axis': 'XYZ'[a],
            'length_cm': round(size[a], 1), 'head_at': 'max', 'grip_from_butt': .3, 'head_source': 'default'}
    # a) SK_Spear grip bones, when the skeletal spear has the same bounds (the pack's rig holds HandL / HandR on it).
    try:
        sk = load(SPEAR_SK)
        bounds = sk.get_bounds() if sk else None
        ext = (bounds.box_extent.x, bounds.box_extent.y, bounds.box_extent.z) if bounds else None
        org = (bounds.origin.x, bounds.origin.y, bounds.origin.z) if bounds else None
        tol = .05 * size[a] + 1
        # Same size AND same placement, so the skeletal spear's grip bones can be read in the static mesh's space.
        same = bool(bounds) and all(abs(2 * ext[i] - size[i]) < tol and abs(org[i] - (mn[i] + mx[i]) * .5) < tol
                                    for i in range(3))
        info['sk_spear_bounds_match'] = bool(same)
        if same:
            ref = u.AnimPoseExtensions.get_reference_pose(load(SPEAR_SK_SKEL))
            hr = v3(ref.get_bone_pose('HandR', u.AnimPoseSpaces.WORLD).translation)
            hl = v3(ref.get_bone_pose('HandL', u.AnimPoseSpaces.WORLD).translation)
            mid = (hr[a] + hl[a]) * .5
            head_max = abs(mx[a] - mid) > abs(mid - mn[a])  # the head is the end further from the hands
            butt = mn[a] if head_max else mx[a]
            rear = hr if abs(hr[a] - butt) < abs(hl[a] - butt) else hl
            info.update({'head_at': 'max' if head_max else 'min', 'head_source': 'SK_Spear HandL/HandR',
                         'sk_hand_r': hr, 'sk_hand_l': hl, 'sk_rear_hand': 'HandR' if rear is hr else 'HandL',
                         'grip_from_butt': round(abs(rear[a] - butt) / size[a], 3),
                         'sk_hand_spacing_cm': round(abs(hr[a] - hl[a]), 1)})
            return info
    except Exception as e:  # noqa: BLE001
        R['warnings'].append('SK_Spear grip bones unreadable: %s' % e)
    # b) vertex spread at each end of the long axis: the head is wider than the shaft.
    try:
        desc = sm.get_static_mesh_description(0)
        count = desc.get_vertex_count()
        pts = [desc.get_vertex_position(u.VertexID(i)) for i in range(count)]
        pts = [(p.x, p.y, p.z) for p in pts]
        band = .15 * size[a]
        others = [i for i in range(3) if i != a]
        center = [(mn[i] + mx[i]) * .5 for i in range(3)]

        def spread(lo, hi):
            sel = [p for p in pts if lo <= p[a] <= hi]
            return max((math.hypot(p[others[0]] - center[others[0]], p[others[1]] - center[others[1]]) for p in sel),
                       default=0.0)
        s_min, s_max = spread(mn[a], mn[a] + band), spread(mx[a] - band, mx[a])
        info.update({'head_at': 'max' if s_max >= s_min else 'min', 'head_source': 'vertex spread',
                     'spread_min_end': round(s_min, 2), 'spread_max_end': round(s_max, 2), 'vertices': count})
    except Exception as e:  # noqa: BLE001
        R['warnings'].append('SM_Spear_01 vertices unreadable (%s); head assumed at the bounds maximum' % e)
    return info


# ---------------------------------------------------------------------------------------------------------------------
# 4-6. Assets
# ---------------------------------------------------------------------------------------------------------------------
def author_definition(mesh):
    if not L.does_asset_exist(SPEAR_DEF):
        if DRY:
            R['definition']['planned'] = 'duplicate %s -> %s' % (KATANA_DEF, SPEAR_DEF)
            return None
        ensure_dir(SPEAR_DEF_DIR)
        assert L.duplicate_asset(KATANA_DEF, SPEAR_DEF), 'duplicate DA_AFS_Melee failed'
        R['definition']['created'] = True
    d = load(SPEAR_DEF)
    d.set_editor_property('weapon_actor_class', None)
    d.set_editor_property('third_person_static_mesh', mesh)
    d.set_editor_property('first_person_static_mesh', mesh)
    for prop in ('third_person_skeletal_mesh', 'first_person_skeletal_mesh'):
        try:
            d.set_editor_property(prop, None)
        except Exception as e:  # noqa: BLE001
            R['warnings'].append('%s: %s' % (prop, e))
    d.set_editor_property('display_name', u.Text('Spear'))
    stats = d.get_editor_property('melee_stats')
    stats.set_editor_property('melee_range', 270.0)  # vendor fallback only; the profile's strikes set the sweeps
    stats.set_editor_property('melee_radius', 12.0)
    d.set_editor_property('melee_stats', stats)
    back = d.get_editor_property('melee_stats')
    R['definition'].update({
        'path': SPEAR_DEF, 'weapon_actor_class': str(d.get_editor_property('weapon_actor_class')),
        'mesh': path_of(d.get_editor_property('third_person_static_mesh')),
        'weapon_type': str(d.get_editor_property('weapon_type')),
        'melee_damage': back.get_editor_property('melee_damage'), 'melee_range': back.get_editor_property('melee_range')})
    if not DRY:
        L.save_loaded_asset(d, False)
        R['saved'].append(SPEAR_DEF)
    return d


def strike_set(s, values):
    for k, v in values.items():
        s.set_editor_property(k, v)


def author_profile(clips, m, mesh_info):
    if DRY:
        R['profile']['planned'] = m.get('plan')
        return
    asset = load(PROFILE)
    fresh = asset is None
    if fresh:
        factory = u.DataAssetFactory()
        factory.set_editor_property('data_asset_class', u.HoverMeleeProfileAsset)
        asset = u.AssetToolsHelpers.get_asset_tools().create_asset('DA_SpearProfile', SPEAR_DIR,
                                                                   u.HoverMeleeProfileAsset, factory)
        assert asset, 'DA_SpearProfile create failed'
    if fresh or RESET_PROFILE:
        asset.reset_to_spear_defaults()
    prof = asset.get_editor_property('profile')
    light = list(prof.get_editor_property('light'))
    names = [str(s.get_editor_property('name')) for s in light]
    plan = m['plan']
    for key in ('Jab', 'Thrust', 'Swing'):
        if key not in names or key not in plan:
            R['warnings'].append('profile row %s not updated' % key)
            continue
        s = light[names.index(key)]
        strike_set(s, plan[key])
        if clips.get(key):
            s.set_editor_property('clip', clips[key])
        light[names.index(key)] = s
    prof.set_editor_property('light', light)
    heavy = prof.get_editor_property('heavy')
    if 'Heavy' in plan:
        strike_set(heavy, plan['Heavy'])
    if clips.get('Heavy'):
        heavy.set_editor_property('clip', clips['Heavy'])
    prof.set_editor_property('heavy', heavy)
    if clips.get('Stance'):
        prof.set_editor_property('stance_loop', clips['Stance'])
    for k, v in plan.get('grip', {}).items():
        prof.set_editor_property(k, v)
    asset.set_editor_property('profile', prof)
    back = asset.get_editor_property('profile')
    R['profile'] = {
        'path': PROFILE, 'fresh': fresh, 'reset': RESET_PROFILE,
        'light': [{'name': str(s.get_editor_property('name')), 'clip': path_of(s.get_editor_property('clip')),
                   'duration': round(s.get_editor_property('duration'), 3),
                   'sweeps': [round(t, 3) for t in s.get_editor_property('sweep_times')],
                   'reach': s.get_editor_property('reach'), 'radius': s.get_editor_property('radius'),
                   'arc': (s.get_editor_property('arc_start_yaw'), s.get_editor_property('arc_end_yaw'))}
                  for s in back.get_editor_property('light')],
        'heavy': {'clip': path_of(back.get_editor_property('heavy').get_editor_property('clip')),
                  'windup': back.get_editor_property('heavy').get_editor_property('windup_fraction'),
                  'sweeps': list(back.get_editor_property('heavy').get_editor_property('sweep_times'))},
        'stance': path_of(back.get_editor_property('stance_loop')),
        'grip': {k: back.get_editor_property(k) for k in ('two_hand_grip', 'tip_toward_left_hand', 'flip_mesh_tip',
                                                          'grip_from_butt', 'two_hand_max_spacing')}}
    L.save_loaded_asset(asset, False)
    R['saved'].append(PROFILE)


def author_waves(spear_def):
    waves = load(WAVES)
    assert waves, 'DA_NYCWaves missing'
    gear = waves.get_editor_property('starting_equipment')
    weapons = list(gear.get_editor_property('starting_weapons'))
    rows = [(path_of(w.get_editor_property('weapon_definition')), w.get_editor_property('quickbar_slot'),
             w.get_editor_property('add_to_quickbar')) for w in weapons]
    grenade_slot = gear.get_editor_property('grenade_quickbar_slot') if (
        gear.get_editor_property('grenade_count') > 0 and gear.get_editor_property('add_grenades_to_quickbar')) else None
    R['waves'] = {'before': rows, 'grenade_slot': grenade_slot}
    present = [r for r in rows if r[0] == SPEAR_DEF]
    if present:
        R['waves']['spear_slot'] = present[0][1]
        R['waves']['note'] = 'already in StartingWeapons'
        return
    used = {r[1] for r in rows if r[2]} | ({grenade_slot} if grenade_slot else set())
    slot = next((s for s in (4, 3, 5) if s not in used), None)
    assert slot, 'no free quickbar slot among 4, 3, 5 (used %s)' % sorted(used)
    R['waves']['spear_slot'] = slot
    if DRY or not spear_def:
        return
    # The struct's fields are EditDefaultsOnly, so set_editor_property refuses them on an instance (first real
    # run 2026-10-31); the keyword constructor is accepted.
    cfg = u.ZE_StartingWeaponConfig(weapon_definition=spear_def, add_to_quickbar=True, quickbar_slot=slot)
    weapons.append(cfg)
    try:
        gear.set_editor_property('starting_weapons', weapons)  # struct arrays come back as copies: set them back
    except Exception as e:  # noqa: BLE001
        R['warnings'].append('starting_weapons set_editor_property refused (%s); used import_text' % str(e)[:120])
        text = gear.export_text()
        head, sep, tail = text.partition('StartingWeapons=(')
        assert sep, 'StartingWeapons not in exported text'
        entry = cfg.export_text()
        gear.import_text(head + sep + entry + ',' + tail if not tail.startswith(')') else head + sep + entry + tail)
    try:
        waves.set_editor_property('starting_equipment', gear)
    except Exception as e:  # noqa: BLE001
        R['warnings'].append('starting_equipment set_editor_property refused (%s); used set_editor_properties' % str(e)[:120])
        waves.set_editor_properties({'starting_equipment': gear})
    back = waves.get_editor_property('starting_equipment').get_editor_property('starting_weapons')
    R['waves']['after'] = [(path_of(w.get_editor_property('weapon_definition')), w.get_editor_property('quickbar_slot'))
                           for w in back]
    assert any(r[0] == SPEAR_DEF and r[1] == slot for r in R['waves']['after']), 'StartingWeapons read-back failed'
    L.save_loaded_asset(waves, False)
    R['saved'].append(WAVES)


# ---------------------------------------------------------------------------------------------------------------------
def build_plan(mode):
    mesh_info = measure_mesh()
    R['mesh'] = mesh_info
    driver = load(DRIVER_MESH)
    assert driver, 'CLS driver mesh missing: ' + DRIVER_MESH
    clips, rows_by_key, lengths = {}, {}, {}
    for key in CLIPS:
        seq = load(out_path(key))
        if not seq:
            continue
        clips[key] = seq
        lengths[key], rows_by_key[key] = sample(seq, driver)
        try:
            R['clips'].setdefault('on_driver', {})[key] = json.loads(u.HoverAuthoring.describe_sequence_on_mesh(
                seq, driver, lengths[key] * .5, ['hand_r', 'hand_l', 'spine_05', 'head']))
        except Exception as e:  # noqa: BLE001
            R['warnings'].append('describe_sequence_on_mesh %s: %s' % (key, e))
    if not rows_by_key:
        (R['warnings'] if DRY else R['errors']).append('no retargeted clips to measure (mode %s)' % mode)
        return clips, {'plan': {}}
    fwd, reach_sum = pick_axes(rows_by_key)
    lat, lat_src = right_axis(fwd)
    m = {'forward_axis': fwd, 'forward_reach_sum_cm': round(reach_sum, 1), 'right_axis': lat, 'right_axis_source': lat_src, 'lengths': lengths, 'clips': {}}
    length_cm = mesh_info['length_cm']
    grip = mesh_info.get('grip_from_butt', .3)
    plan = {}
    jab = measure_thrust(rows_by_key['Jab'], fwd) if 'Jab' in rows_by_key else None
    lead_left = jab['lead_left'] if jab else True
    stance = spacing(rows_by_key['Stance']) if 'Stance' in rows_by_key else None
    m['stance_spacing_mean_min_max'] = stance

    def timing(key, frac_contact, spread):
        dur = min(lengths[key], TARGET_DURATION['Heavy' if key.startswith('Heavy') else key])
        c = frac_contact * dur
        sweeps = sorted({round(min(max(c + o * dur, .05), dur - .03), 3) for o in spread})
        return dur, c, sweeps

    for key in ('Jab', 'Thrust'):
        if key not in rows_by_key:
            continue
        rows = rows_by_key[key]
        th = measure_thrust(rows, fwd)
        frac = rows[th['contact_index']]['t'] / lengths[key]
        dur, c, sweeps = timing(key, frac, (-.10, -.04, .02) if key == 'Jab' else (-.12, -.06, 0, .05))
        # Each thrust's own lead hand (fixed 2026-10-31: the jab leads left, the thrust right, so the jab's lead
        # laid the thrust's spear backwards and measured 22 cm).
        reach = tip_reach(rows[th['contact_index']], fwd, th['lead_left'], length_cm, grip)
        th.update({'contact_frac': round(frac, 3), 'tip_reach_cm': reach, 'duration': dur, 'rate': round(lengths[key] / dur, 2)})
        m['clips'][key] = th
        row = {'duration': dur, 'sweep_times': sweeps, 'chain_open_seconds': round(c * .6, 3),
               'chain_at_seconds': round(min(c + .25 * dur, .92 * dur), 3)}
        if reach and 150 <= reach <= 360:
            row['reach'] = float(round(reach))
        plan[key] = row
    if 'Swing' in rows_by_key:
        rows = rows_by_key['Swing']
        sw = measure_swing(rows, lat)
        frac = rows[sw['contact_index']]['t'] / lengths['Swing']
        dur, c, sweeps = timing('Swing', frac, (-.12, -.06, 0, .06, .12))
        start, end = (-SWING_HALF_ARC, SWING_HALF_ARC) if sw['moving_right'] else (SWING_HALF_ARC, -SWING_HALF_ARC)
        reach = tip_reach(rows[sw['contact_index']], fwd, lead_left, length_cm, grip)
        sw.update({'contact_frac': round(frac, 3), 'duration': dur, 'rate': round(lengths['Swing'] / dur, 2),
                   'arc': (start, end), 'tip_reach_cm': reach})
        m['clips']['Swing'] = sw
        row = {'duration': dur, 'sweep_times': sweeps, 'arc_start_yaw': start, 'arc_end_yaw': end,
               'chain_open_seconds': round(c * .6, 3), 'chain_at_seconds': round(min(c + .25 * dur, .92 * dur), 3)}
        if reach and 150 <= reach <= 330:
            row['reach'] = float(round(reach))
        plan['Swing'] = row
    heavy_rows = {k: measure_thrust(rows_by_key[k], fwd) for k in HEAVY_KEYS if k in rows_by_key}
    if heavy_rows:
        best = max(heavy_rows, key=lambda k: heavy_rows[k]['lunge_cm'])
        th = heavy_rows[best]
        rows = rows_by_key[best]
        frac = rows[th['contact_index']]['t'] / lengths[best]
        windup = min(max(rows[th['windup_index']]['t'] / lengths[best], .15), max(.15, frac - .12), .7)
        dur, c, sweeps = timing(best, frac, (-.08, -.03, .02, .07))
        sweeps = [t for t in sweeps if t / dur > windup + .02] or [round(c, 3)]
        reach = tip_reach(rows[th['contact_index']], fwd, th['lead_left'], length_cm, grip)
        m['clips']['Heavy'] = dict(th, key=best, contact_frac=round(frac, 3), windup_frac=round(windup, 3),
                                   duration=dur, tip_reach_cm=reach,
                                   candidates={k: v['lunge_cm'] for k, v in heavy_rows.items()})
        row = {'duration': dur, 'sweep_times': sweeps, 'windup_fraction': round(windup, 3)}
        # A charged heavy must not reach less than the light thrust (2026-10-31: with each clip's own lead hand the
        # heavy measured 159 cm against the thrust's 270 cm default); below that keep SpearDefaults' 300 cm.
        thrust_reach = plan.get('Thrust', {}).get('reach', 270.0)
        if reach and 150 <= reach <= 380 and reach >= thrust_reach:
            row['reach'] = float(round(reach))
        elif reach:
            R['warnings'].append('heavy measured reach %.0f cm < thrust %.0f cm: kept the default' % (reach, thrust_reach))
        plan['Heavy'] = row
        clips['Heavy'] = clips[best]
    plan['grip'] = {'tip_toward_left_hand': bool(lead_left), 'flip_mesh_tip': mesh_info['head_at'] == 'min',
                    'grip_from_butt': float(grip),
                    'two_hand_max_spacing': float(max(110.0, (stance[2] if stance else 0) * 1.4))}
    m['plan'] = plan
    R['measure'] = m
    return clips, m


def main():
    try:
        assert hasattr(u, 'HoverMeleeProfileAsset'), 'UHoverMeleeProfileAsset missing: apply_spear.py + Build.ps1 first'
        mode = retarget_clips()
        R['clips']['mode'] = mode
        clips, m = build_plan(mode)
        mesh = load(SPEAR_SM)
        spear_def = author_definition(mesh)
        author_profile(clips, m, R['mesh'])
        author_waves(spear_def)
        R['ok'] = not R['errors']
    except Exception:  # noqa: BLE001
        R['errors'].append(traceback.format_exc())
    R['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    save_receipt()
    print('AUTHOR_SPEAR_DONE', json.dumps({'ok': R['ok'], 'mode': R['clips'].get('mode'), 'saved': R['saved'],
                                           'errors': [e[-300:] for e in R['errors']]}, default=str), flush=True)


main()
u.SystemLibrary.quit_editor()
