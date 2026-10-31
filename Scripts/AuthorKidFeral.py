"""Author the NYC Kid as a feral: Feral Zombie locomotion, pounce/swipe attacks, hit reacts, deaths and a
Reanimate rise, plus DA_NYC_Kid (a duplicate of DA_Kid carrying them), then quit the editor.

Owner decision (2026-10-29): the Kid is a feral. Numbers: Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md
Section 10 "Kid horde crawler spec" and "Feral-clip usage table" (capsule 23/23, AttackRange 130,
AttackSphereRadius 45, AttackCooldown .85) and the Kid tier speeds (walk 300, run 650, max 820).
Capsule: the base AHoverCyberZombie sizes it CapsuleRadius x Height*.5 (HoverCyberCity.cpp:494, 23 x 55);
CapsuleHalfHeight 23 is then applied by AHoverNYCZombie::BeginPlay (HoverNYCZombie.cpp:133-146), so the
23/23 crawler capsule holds for the NYC wave class only, not if DA_NYC_Kid is spawned as a plain Cyber zombie.

Creates or updates, under /Game/HoverPrototype/NYC/Zombies/ (and saves only these):
  BS_NYC_Kid_Feral          BlendSpace1D on speed: Idle_01 @ 0, Walk @ 300, Run @ 650; axis 0..820, GridNum 2
  AM_NYC_Kid_Pounce         LeapForward_Short    attack, ZE_ZombieAnimNotify_AttackHit
  AM_NYC_Kid_Swipe_L / _R   Attack_LeftSwipe / Attack_RightSwipe   attack, hit notify
  AM_NYC_Kid_Hit_01..04     HitReact_01..04
  AM_NYC_Kid_Death_01 / 02  Death_01 / Death_02  (auto blend-out off: the vendor ragdolls at length-0.1 s)
  AM_NYC_Kid_Rise           Reanimate (spawn-in rise; SpecialMontages['Rise'], data only today)
  DA_NYC_Kid                duplicate of Variants/Kid/DA_Kid with the assets above and the design numbers

Skeletons. The montages and the blendspace are authored on the Feral clips' own skeleton
(/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton) and play on SK_Kid_Skeleton through the
compatible-skeleton registration that ReviewKidFeral.py already saved (verified here, never repeated).
That is the same path DA_Kid uses today for the vendor Zombie_001 assets (authored on ZESP SK_Mannequin).
UAnimMontageFactory is given only SourceAnimation: in the engine factory the target skeleton must equal the
source clip's skeleton, and HoverAuthoring.BuildRideBlend sets the blendspace skeleton from its first clip.

Slots (ABP_ZombieMaster has a full-body DefaultSlot and an UpperBody slot layered from spine_01): attacks use
the slot of the vendor AM_Attack_01, hit reacts the slot of AM_Hit, deaths and the rise the slot of AM_Death;
each is read from the vendor montage at run time (decoded on disk: UpperBody / DefaultSlot / DefaultSlot).

Idempotent: existing owned assets are checked and updated in place, never deleted; an existing asset of the
wrong class or on the wrong clip stops the run. Every value is read back before anything is saved; on any
error nothing is saved. Referenced assets (DA_Kid, the skeletons, the Feral clips, the vendor Zombie_001
assets, the Cyber data) are hashed before/after and must not change.
Receipt: D:/AFS_Comparisons/NYCSurvival_<YYYYMMDD>/kid_feral_receipt.json.

Run (never concurrently with another editor run):
  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
      "M:/UnrealProjects/AFS/AFS.uproject"
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorKidFeral.py" -nullrhi -unattended -nosplash
Afterwards re-run Scripts/AuthorNYCData.py: its Kid slot prefers /Game/HoverPrototype/NYC/Zombies/DA_NYC_Kid.
Flags (inside the quoted -ExecutePythonScript value, after the script path):
  --dry-run   print the plan; nothing is loaded, created or saved
"""
import hashlib
import json
import re
import sys
import time
import traceback
from pathlib import Path

try:
    import unreal as u
except ImportError:  # --dry-run also works outside the editor
    u = None

PKG = '/Game/HoverPrototype/NYC/Zombies'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
RECEIPT = OUT / 'kid_feral_receipt.json'
DRY_RUN = '--dry-run' in sys.argv[1:]

KID_DIR = '/Game/HoverPrototype/ZombieEngine/Variants/Kid'
DA_KID = KID_DIR + '/DA_Kid'
KID_SKEL = KID_DIR + '/SK_Kid_Skeleton'
KID_MESH = KID_DIR + '/Optimized/SK_Kid_LODs'
FERAL_SKEL = '/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton'
FERAL = '/Game/FeralZombie/Animations/'
VENDOR = '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/'
VENDOR_ATTACK, VENDOR_HIT, VENDOR_DEATH = VENDOR + 'AM_Attack_01', VENDOR + 'AM_Hit', VENDOR + 'AM_Death'
VENDOR_BS = VENDOR + 'BS_Zombie_WalkRun'
# Slot names decoded from the vendor packages' name tables; used only if the run-time read fails.
DECODED_SLOTS = {VENDOR_ATTACK: 'UpperBody', VENDOR_HIT: 'DefaultSlot', VENDOR_DEATH: 'DefaultSlot'}

# Kid tier and crawler spec.
WALK_SPEED, RUN_SPEED, MAX_SPEED = 300.0, 650.0, 820.0
DA_NAME = 'DA_NYC_Kid'
DA_FIELDS = [('Height', 110.0), ('CapsuleRadius', 23.0), ('CapsuleHalfHeight', 23.0), ('MaximumRunSpeed', MAX_SPEED)]
STAT_FIELDS = [('WalkSpeed', WALK_SPEED), ('RunSpeed', RUN_SPEED), ('AttackRange', 130.0),
               ('AttackSphereRadius', 45.0), ('AttackCooldown', .85)]
# Read and recorded, never written (they keep DA_Kid's values).
KEPT_FIELDS = ['Role', 'AppearanceMesh', 'AnimClassOverride', 'MaxAcceleration', 'KillPoints']
KEPT_STATS = ['MaxHealth', 'MeleeDamage', 'MinGoldReward', 'MaxGoldReward', 'CorpseLifespan']

BS_NAME = 'BS_NYC_Kid_Feral'
BS_AXIS = 'Speed'
BS_SAMPLES = [('Idle_01', 0.0), ('Walk', WALK_SPEED), ('Run', RUN_SPEED)]

# name, Feral clip, role, hit-notify time in seconds (None = no notify). The notify times are estimates
# from the ReviewKidFeral stills (pounce lands near 60% of 0.47 s; the swipe winds up at 33% and has
# finished by 66% of 1.67 s); confirm in the montage editor.
HIT_TRACK = 'ZEHit'
MONTAGES = [
    ('AM_NYC_Kid_Pounce', 'LeapForward_Short', 'attack', .28),
    ('AM_NYC_Kid_Swipe_L', 'Attack_LeftSwipe', 'attack', .80),
    ('AM_NYC_Kid_Swipe_R', 'Attack_RightSwipe', 'attack', .80),
    ('AM_NYC_Kid_Hit_01', 'HitReact_01', 'hit', None),
    ('AM_NYC_Kid_Hit_02', 'HitReact_02', 'hit', None),
    ('AM_NYC_Kid_Hit_03', 'HitReact_03', 'hit', None),
    ('AM_NYC_Kid_Hit_04', 'HitReact_04', 'hit', None),
    ('AM_NYC_Kid_Death_01', 'Death_01', 'death', None),
    ('AM_NYC_Kid_Death_02', 'Death_02', 'death', None),
    ('AM_NYC_Kid_Rise', 'Reanimate', 'rise', None),
]
SLOT_SOURCE = {'attack': VENDOR_ATTACK, 'hit': VENDOR_HIT, 'death': VENDOR_DEATH, 'rise': VENDOR_DEATH}
HOLD_DEATH_POSE = True  # bEnableAutoBlendOut off on deaths so the 0.47-0.63 s clips do not blend back first
SPECIAL_KEYS = {'Pounce': 'AM_NYC_Kid_Pounce', 'Rise': 'AM_NYC_Kid_Rise'}  # merged into SpecialMontages
DEATH_MONTAGE = 'AM_NYC_Kid_Death_01'  # the longer Feral death (0.63 s); Death_02 is authored for later use

UNTOUCHED = [DA_KID, KID_SKEL, KID_MESH, FERAL_SKEL, VENDOR_ATTACK, VENDOR + 'AM_Attack_02', VENDOR_HIT,
             VENDOR_DEATH, VENDOR_BS, '/Game/HoverPrototype/ZombieEngine/DA_CyberWaves',
             '/Game/HoverPrototype/ZombieEngine/Variants/DA_CyberEncounters']
UNTOUCHED += sorted({FERAL + clip for _, clip, _, _ in MONTAGES} | {FERAL + clip for clip, _ in BS_SAMPLES})

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'errors': [], 'warnings': [], 'assets': {}, 'saved': [],
          'hashes_before': {}, 'hashes_after': {}, 'untouched_hashes_before': {}, 'untouched_hashes_after': {},
          'registration': {}, 'slots': {}, 'vendor': {}, 'blendspace': {}, 'montages': {}, 'definition': {},
          'kept_from_da_kid': {}, 'stride_info': {}, 'python_names': {}, 'readback_mismatches': [],
          'capsule_half_height_applied_by': 'AHoverNYCZombie::BeginPlay (HoverNYCZombie.cpp:133-146), NYC wave '
                                            'class only; the base AHoverCyberZombie uses Height*.5',
          'claim': 'Editor asset authoring only; no gameplay run, no rendered evidence'}
EA = None


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('KID_FERAL receipt failed', traceback.format_exc(), flush=True)


# ---------------------------------------------------------------------------------------------
# Python name resolution and read-back (same rules as AuthorNYCData.py).

def pythonize(cpp):
    name = cpp[1:] if len(cpp) > 1 and cpp[0] == 'b' and cpp[1].isupper() else cpp
    out = name[0].lower()
    for i in range(1, len(name)):
        c, prev = name[i], name[i - 1]
        nxt = name[i + 1] if i + 1 < len(name) else ''
        if c.isupper() and (prev.islower() or prev.isdigit() or (prev.isupper() and nxt.islower())):
            out += '_'
        out += c.lower()
    return out


def candidates(cpp):
    base = pythonize(cpp)
    alt = ''.join(('_' + ch if ch.isdigit() and i and not base[i - 1].isdigit() and base[i - 1] != '_' else ch)
                  for i, ch in enumerate(base))
    return [base] if alt == base else [base, alt]


def resolve(holder, cpp, scope):
    key = scope + '.' + cpp
    if key in REPORT['python_names']:
        return REPORT['python_names'][key]
    for name in candidates(cpp):
        try:
            holder.get_editor_property(name)
            REPORT['python_names'][key] = name
            return name
        except Exception:
            continue
    raise AttributeError('%s: no Python property for %s (tried %s)' % (scope, cpp, candidates(cpp)))


def get(holder, cpp, scope):
    return holder.get_editor_property(resolve(holder, cpp, scope))


def put(holder, cpp, value, scope):
    holder.set_editor_property(resolve(holder, cpp, scope), value)


def norm(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, 'get_path_name'):
        return value.get_path_name()
    if isinstance(value, u.SoftObjectPath):  # soft pointers may come back as paths instead of objects
        try:
            return str(u.SystemLibrary.conv_soft_obj_path_to_string(value))
        except Exception:
            return value.export_text()
    if isinstance(value, (list, tuple)) or isinstance(value, u.Array):
        return [norm(v) for v in value]
    return str(value)


def same(actual, want):
    if isinstance(want, float) and isinstance(actual, (int, float)):
        return abs(actual - want) < 1e-3
    if isinstance(want, list) and isinstance(actual, list):
        return len(want) == len(actual) and all(same(a, w) for a, w in zip(actual, want))
    return actual == want


def expect(field, actual, want):
    a, w = norm(actual), norm(want)
    if not same(a, w):
        REPORT['readback_mismatches'].append({'field': field, 'expected': w, 'actual': a})
    return a


# ---------------------------------------------------------------------------------------------

def file_of(asset_path):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return content / (asset_path[len('/Game/'):] + '.uasset')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load(path, cls=None):
    asset = EA.load_asset(path) if EA.does_asset_exist(path) else None
    assert asset, 'missing asset ' + path
    if cls:
        assert isinstance(asset, cls), '%s is %s, not %s' % (path, asset.get_class().get_name(), cls.__name__)
    return asset


def existing(name, cls):
    """The owned asset if it already exists (checked class), else None."""
    path = PKG + '/' + name
    if not EA.does_asset_exist(path):
        return None
    asset = EA.load_asset(path)
    assert asset and isinstance(asset, cls), '%s exists but is %s, not %s; refusing to touch it' % (
        path, asset.get_class().get_name() if asset else None, cls.__name__)
    return asset


def verify_registration(feral_skel):
    skel = load(KID_SKEL, u.Skeleton)
    compat = [norm(x) for x in (skel.get_editor_property('compatible_skeletons') or [])]
    REPORT['registration'] = {'skeleton': KID_SKEL, 'compatible_skeletons': compat,
                              'feral_registered': feral_skel.get_path_name() in compat}
    assert REPORT['registration']['feral_registered'], (
        'UE4_Mannequin_Skeleton is not in SK_Kid_Skeleton.CompatibleSkeletons (%s); run ReviewKidFeral.py first. '
        'This script does not register skeletons.' % compat)


def vendor_slot(path):
    """Slot of a vendor montage (AnimationLibrary first, then slot_anim_tracks, then the decoded name)."""
    try:
        montage = load(path, u.AnimMontage)
        names = [str(n) for n in u.AnimationLibrary.get_montage_slot_names(montage)]
        if not names:
            names = [str(t.get_editor_property('slot_name')) for t in montage.get_editor_property('slot_anim_tracks')]
        if names:
            REPORT['vendor'][path.split('/')[-1] + '_slots'] = names
            return names[0], 'read'
    except Exception:
        REPORT['warnings'].append('vendor slot read failed for %s: %s' % (path, traceback.format_exc(limit=1)))
    return DECODED_SLOTS[path], 'decoded'


def record_vendor():
    try:
        attack = load(VENDOR_ATTACK, u.AnimMontage)
        events = u.AnimationLibrary.get_animation_notify_events(attack)
        times = [round(u.AnimationLibrary.get_anim_notify_event_trigger_time(e), 3) for e in events]
        REPORT['vendor']['AM_Attack_01'] = {'length': attack.get_play_length(), 'notify_times': times}
    except Exception:
        REPORT['warnings'].append('vendor AM_Attack_01 notify read failed: ' + traceback.format_exc(limit=1))
    try:
        bs = load(VENDOR_BS)
        params = bs.get_editor_property('blend_parameters')
        p0 = params[0]
        REPORT['vendor']['BS_Zombie_WalkRun'] = {
            'class': bs.get_class().get_name(), 'axis_name': str(p0.get_editor_property('display_name')),
            'min': p0.get_editor_property('min'), 'max': p0.get_editor_property('max'),
            'samples': [(norm(s.get_editor_property('animation')), s.get_editor_property('sample_value').x)
                        for s in bs.get_editor_property('sample_data')]}
    except Exception:
        REPORT['warnings'].append('vendor BS_Zombie_WalkRun read failed: ' + traceback.format_exc(limit=1))


# ---------------------------------------------------------------------------------------------
# Montages

def ensure_montage(name, clip, kid_mesh):
    montage = existing(name, u.AnimMontage)
    state = 'updated_in_place'
    if montage is None:
        factory = u.AnimMontageFactory()
        # SourceAnimation only: the factory requires TargetSkeleton to be unset or equal to the clip's skeleton.
        factory.set_editor_property('source_animation', clip)
        montage = u.AssetToolsHelpers.get_asset_tools().create_asset(name, PKG, u.AnimMontage, factory)
        assert montage and isinstance(montage, u.AnimMontage), 'create_asset failed for ' + name
        state = 'created'
    first = montage.get_first_anim_reference()
    assert first and first.get_path_name() == clip.get_path_name(), (
        '%s plays %s, not %s; refusing to rewrite it' % (name, norm(first), clip.get_path_name()))
    try:
        montage.set_preview_skeletal_mesh(kid_mesh)
    except Exception:
        REPORT['warnings'].append('%s: preview mesh not set: %s' % (name, traceback.format_exc(limit=1)))
    return montage, state


def set_slot(montage, slot, scope):
    tracks = list(get(montage, 'SlotAnimTracks', 'AnimMontage'))
    assert len(tracks) == 1, '%s has %d slot tracks; expected 1' % (scope, len(tracks))
    track = tracks[0]
    if str(track.get_editor_property('slot_name')) != slot:
        track.set_editor_property('slot_name', slot)
        put(montage, 'SlotAnimTracks', [track], 'AnimMontage')


def set_hit_notify(montage, seconds, length, scope):
    lib = u.AnimationLibrary
    if lib.is_valid_anim_notify_track_name(montage, HIT_TRACK):
        lib.remove_animation_notify_events_by_track(montage, HIT_TRACK)
    else:
        lib.add_animation_notify_track(montage, HIT_TRACK, u.LinearColor(1, .2, .2, 1))
    at = min(seconds, max(length - .02, 0.0))
    notify = lib.add_animation_notify_event(montage, HIT_TRACK, at, u.ZE_ZombieAnimNotify_AttackHit.static_class())
    assert notify, '%s: AddAnimationNotifyEvent returned None' % scope
    return at


def read_montage(montage, clip, slot, hit_at, hold, scope):
    names = [str(n) for n in u.AnimationLibrary.get_montage_slot_names(montage)]
    expect(scope + '.slots', names, [slot])
    expect(scope + '.first_anim', montage.get_first_anim_reference(), clip)
    expect(scope + '.length', round(montage.get_play_length(), 3), round(clip.get_play_length(), 3))
    expect(scope + '.skeleton', montage.get_editor_property('skeleton'), clip.get_editor_property('skeleton'))
    hits = []
    if lib_track_exists(montage):
        for e in u.AnimationLibrary.get_animation_notify_events_for_track(montage, HIT_TRACK):
            n = e.get_editor_property('notify')
            hits.append({'class': n.get_class().get_name() if n else None,
                         'time': round(u.AnimationLibrary.get_anim_notify_event_trigger_time(e), 3)})
    if hit_at is None:
        expect(scope + '.hit_notifies', len(hits), 0)
    else:
        expect(scope + '.hit_notifies', [(h['class'], h['time']) for h in hits],
               [('ZE_ZombieAnimNotify_AttackHit', round(hit_at, 3))])
    blend_out = get(montage, 'bEnableAutoBlendOut', 'AnimMontage')
    expect(scope + '.auto_blend_out', bool(blend_out), not hold)
    return {'slot': names, 'length': montage.get_play_length(), 'clip': clip.get_path_name(),
            'skeleton': norm(montage.get_editor_property('skeleton')), 'hit_notifies': hits,
            'auto_blend_out': bool(blend_out)}


def lib_track_exists(montage):
    return u.AnimationLibrary.is_valid_anim_notify_track_name(montage, HIT_TRACK)


def author_montages(feral_skel, kid_mesh):
    slots = {}
    for kind, source in SLOT_SOURCE.items():
        slots[kind], how = vendor_slot(source)
        REPORT['slots'][kind] = {'slot': slots[kind], 'from': source.split('/')[-1], 'how': how}
    made = {}
    for name, clip_name, kind, hit_at in MONTAGES:
        clip = load(FERAL + clip_name, u.AnimSequence)
        assert norm(clip.get_editor_property('skeleton')) == feral_skel.get_path_name(), (
            '%s is not on %s' % (clip_name, FERAL_SKEL))
        montage, state = ensure_montage(name, clip, kid_mesh)
        set_slot(montage, slots[kind], name)
        if hit_at is not None:
            hit_at = set_hit_notify(montage, hit_at, clip.get_play_length(), name)
        elif lib_track_exists(montage):
            u.AnimationLibrary.remove_animation_notify_track(montage, HIT_TRACK)
        hold = HOLD_DEATH_POSE and kind == 'death'
        put(montage, 'bEnableAutoBlendOut', not hold, 'AnimMontage')
        REPORT['assets'][name] = {'path': montage.get_path_name(), 'class': 'AnimMontage', 'state': state}
        made[name] = (montage, clip, slots[kind], hit_at, hold)
    for name, (montage, clip, slot, hit_at, hold) in made.items():
        REPORT['montages'][name] = read_montage(montage, clip, slot, hit_at, hold, name)
    return {name: v[0] for name, v in made.items()}


# ---------------------------------------------------------------------------------------------
# Blendspace: BuildRideBlend adds, validates and triangulates the samples (it needs coordinates inside its
# -1..1 axes, so the speeds go in normalised to the final 0..MAX_SPEED range, and it sets GridNum 2). The
# validated FBlendSample structs are then read back as copies (they keep the transient bIsValid and the editor
# fields), only their SampleValue is changed to the absolute speed, and they are written back between two axis
# writes, as RefineCharacterAssets.py does for RateScale. No FBlendSample is constructed in Python and GridNum
# stays 2, because no Python-reachable ResampleData is proven. The serialized triangulation (BlendSpaceData) is
# in normalised 0..1 space (BlendSpace.h FBlendSpaceSegment), so it is the same for -1..1 with normalised
# samples and for 0..820 with absolute ones; it is read back through DescribeObjectProperties and checked.

BS_GRID = 2  # = HoverAuthoring.BuildRideBlend (HoverAuthoring.cpp:511)


def make_axis(template, name, lo, hi, grid, scope):
    p = template
    put(p, 'DisplayName', name, scope)
    put(p, 'Min', float(lo), scope)
    put(p, 'Max', float(hi), scope)
    put(p, 'GridNum', int(grid), scope)
    put(p, 'bSnapToGrid', False, scope)
    put(p, 'bWrapInput', False, scope)
    return p


def write_axes(bs):
    params = bs.get_editor_property('blend_parameters')
    p0 = make_axis(params[0], BS_AXIS, 0, MAX_SPEED, BS_GRID, 'BlendParameter')
    p1 = make_axis(params[1], 'None', 0, 100, BS_GRID, 'BlendParameter')
    try:
        params[0] = p0
        params[1] = p1
        bs.set_editor_property('blend_parameters', params)
    except Exception:
        rest = [params[i] for i in range(2, len(params))]
        bs.set_editor_property('blend_parameters', [p0, p1] + rest)


def sample_values(bs):
    return [(norm(s.get_editor_property('animation')), round(s.get_editor_property('sample_value').x, 3))
            for s in bs.get_editor_property('sample_data')]


def check_triangulation(bs, got):
    """Record the serialized blendspace data and check the 1D segments against the sample speeds."""
    dump = dict(u.HoverAuthoring.describe_object_properties(bs))
    keep = ('SampleData', 'GridSamples', 'BlendSpaceData', 'BlendParameters')
    REPORT['blendspace']['dump'] = {k: str(dump.get(k)) for k in keep}
    text = str(dump.get('BlendSpaceData', ''))
    segments = []
    # ExportText omits members equal to the struct default (BlendSpace.h FBlendSpaceSegment:
    # SampleIndices = {INDEX_NONE, INDEX_NONE}, Vertices = {0.f, 0.f}), so the segment that starts at speed 0
    # exports without Vertices[0]. Fill omitted entries with those defaults instead of dropping the segment;
    # an omitted index stays -1 and fails the range check below.
    for chunk in re.findall(r'\(([^()]*SampleIndices[^()]*)\)', text):
        idx = {'0': '-1', '1': '-1'}
        idx.update(re.findall(r'SampleIndices\W{0,2}(\d)\W{0,2}=\s*(-?\d+)', chunk))
        ver = {'0': '0', '1': '0'}
        ver.update(re.findall(r'Vertices\W{0,2}(\d)\W{0,2}=\s*(-?[0-9.]+(?:[eE][-+]?\d+)?)', chunk))
        if set(idx) == {'0', '1'} and set(ver) == {'0', '1'}:
            segments.append([(int(idx[k]), round(float(ver[k]), 3)) for k in ('0', '1')])
    REPORT['blendspace']['segments'] = segments
    REPORT['blendspace']['grid_samples_entries'] = len(re.findall(r'Indices', str(dump.get('GridSamples', ''))))
    want_norm = [round(speed / MAX_SPEED, 3) for _, speed in got]  # 0 / .366 / .793
    REPORT['blendspace']['expected_normalised_vertices'] = want_norm
    expect(BS_NAME + '.BlendSpaceData.segment_count', len(segments), len(got) - 1)
    bad = [seg for seg in segments for i, v in seg
           if not (0 <= i < len(got)) or abs(v - want_norm[i]) > 2e-3]
    expect(BS_NAME + '.BlendSpaceData.segment_vertices', bad, [])
    expect(BS_NAME + '.BlendSpaceData.vertices', sorted({v for seg in segments for _, v in seg}), want_norm)


def author_blendspace(feral_skel, kid_mesh):
    clips = [load(FERAL + name, u.AnimSequence) for name, _ in BS_SAMPLES]
    bs = existing(BS_NAME, u.BlendSpace1D)
    state = 'updated_in_place'
    if bs is None:
        factory = u.BlendSpaceFactory1D()
        factory.set_editor_property('target_skeleton', feral_skel)
        factory.set_editor_property('preview_skeletal_mesh', kid_mesh)
        bs = u.AssetToolsHelpers.get_asset_tools().create_asset(BS_NAME, PKG, u.BlendSpace1D, factory)
        assert bs and isinstance(bs, u.BlendSpace1D), 'create_asset failed for ' + BS_NAME
        state = 'created'
    normalised = [u.Vector(2.0 * speed / MAX_SPEED - 1.0, 0.0, 0.0) for _, speed in BS_SAMPLES]
    assert u.HoverAuthoring.build_ride_blend(bs, clips, normalised), 'BuildRideBlend refused ' + BS_NAME
    # Copies of the samples BuildRideBlend just validated; only sample_value changes on them.
    samples = list(bs.get_editor_property('sample_data'))
    REPORT['blendspace']['after_build_ride_blend'] = sample_values(bs)
    assert len(samples) == len(clips), '%s has %d samples after BuildRideBlend; expected %d' % (
        BS_NAME, len(samples), len(clips))
    for s, clip in zip(samples, clips):
        anim = s.get_editor_property('animation')
        assert anim and anim.get_path_name() == clip.get_path_name(), (
            '%s sample order: %s, expected %s' % (BS_NAME, norm(anim), clip.get_path_name()))
    write_axes(bs)
    REPORT['blendspace']['after_axis_write'] = sample_values(bs)  # shows whether the engine remapped
    for s, (_, speed) in zip(samples, BS_SAMPLES):
        s.set_editor_property('sample_value', u.Vector(speed, 0.0, 0.0))
    bs.set_editor_property('sample_data', samples)
    write_axes(bs)
    try:
        bs.set_preview_skeletal_mesh(kid_mesh)
    except Exception:
        REPORT['warnings'].append('BS preview mesh not set: ' + traceback.format_exc(limit=1))
    REPORT['assets'][BS_NAME] = {'path': bs.get_path_name(), 'class': 'BlendSpace1D', 'state': state}

    p0 = bs.get_editor_property('blend_parameters')[0]
    got = sample_values(bs)
    expect(BS_NAME + '.samples', [list(x) for x in got],
           [[c.get_path_name(), speed] for c, (_, speed) in zip(clips, BS_SAMPLES)])
    expect(BS_NAME + '.axis', [str(p0.get_editor_property('display_name')), p0.get_editor_property('min'),
                               p0.get_editor_property('max'), p0.get_editor_property('grid_num')],
           [BS_AXIS, 0.0, MAX_SPEED, BS_GRID])
    expect(BS_NAME + '.skeleton', bs.get_editor_property('skeleton'), feral_skel)
    check_triangulation(bs, got)
    REPORT['blendspace'].update({'samples': got, 'axis': [BS_AXIS, 0.0, MAX_SPEED], 'grid_num': BS_GRID,
                                 'skeleton': norm(bs.get_editor_property('skeleton'))})
    return bs


def stride_info(kid_mesh):
    """Informational: foot-plant speed of Walk/Run on the Kid at runtime scale (rate 1). Never applied."""
    try:
        extent = kid_mesh.get_bounds().box_extent.z
        scale = 110.0 / (2.0 * extent) if extent > 0 else 1.0
        options = u.AnimPoseEvaluationOptions()
        options.optional_skeletal_mesh = kid_mesh
        options.should_retarget = True
        info = {'mesh_half_height': extent, 'runtime_scale': scale}
        for name, speed in BS_SAMPLES[1:]:
            seq = load(FERAL + name, u.AnimSequence)
            length = seq.get_play_length()
            n = max(30, round(length * 60))
            dt = length / n
            rows = {b: [] for b in ('foot_l', 'foot_r')}
            for i in range(n + 1):
                pose = u.AnimPoseExtensions.get_anim_pose_at_time(seq, min(i * dt, length - .0001), options)
                root = pose.get_bone_pose('root', u.AnimPoseSpaces.WORLD).translation
                for b in rows:
                    rows[b].append(pose.get_bone_pose(b, u.AnimPoseSpaces.WORLD).translation - root)
            speeds = []
            for pts in rows.values():
                low = min(v.z for v in pts)
                for a, b in zip(pts, pts[1:]):
                    if max(a.z, b.z) > low + 2 or abs(b.z - a.z) / dt > 30:
                        continue
                    planar = ((b.x - a.x) ** 2 + (b.y - a.y) ** 2) ** .5 / dt
                    if planar > 30:
                        speeds.append(planar)
            speeds.sort()
            mesh_speed = speeds[len(speeds) // 2] if len(speeds) >= 3 else None
            world = mesh_speed * scale if mesh_speed else None
            info[name] = {'sample_speed': speed, 'planted_frames': len(speeds), 'mesh_space_cm_s': mesh_speed,
                          'world_cm_s_at_rate_1': world,
                          'suggested_rate_scale': round(speed / world, 3) if world else None}
        REPORT['stride_info'] = info
    except Exception:
        REPORT['stride_info'] = {'error': traceback.format_exc(limit=2)}


# ---------------------------------------------------------------------------------------------
# Definition

def author_definition(bs, montages):
    dest = PKG + '/' + DA_NAME
    da = existing(DA_NAME, u.HoverCyberZombieDefinition)
    state = 'updated_in_place'
    if da is None:
        da = EA.duplicate_asset(DA_KID, dest)
        assert da and isinstance(da, u.HoverCyberZombieDefinition), 'duplicate_asset failed for ' + dest
        state = 'duplicated_from_DA_Kid'
    REPORT['assets'][DA_NAME] = {'path': da.get_path_name(), 'class': da.get_class().get_name(), 'state': state}
    scope = 'HoverCyberZombieDefinition'
    for cpp in KEPT_FIELDS:
        try:
            REPORT['kept_from_da_kid'][cpp] = norm(get(da, cpp, scope))
        except Exception:
            REPORT['kept_from_da_kid'][cpp] = 'n/a'
    role = str(get(da, 'Role', scope)).upper()
    assert 'KID' in role, '%s Role is %s, expected Kid' % (dest, role)

    for cpp, value in DA_FIELDS:
        put(da, cpp, value, scope)
    stats = get(da, 'Stats', scope)
    for cpp in KEPT_STATS:
        REPORT['kept_from_da_kid']['Stats.' + cpp] = norm(get(stats, cpp, 'ZE_ZombieStats'))
    for cpp, value in STAT_FIELDS:
        put(stats, cpp, value, 'ZE_ZombieStats')
    put(da, 'Stats', stats, scope)

    attacks = [montages[n] for n, _, kind, _ in MONTAGES if kind == 'attack']
    hits = [montages[n] for n, _, kind, _ in MONTAGES if kind == 'hit']
    put(da, 'MovementBlendSpace', bs, scope)
    put(da, 'AttackMontages', attacks, scope)
    put(da, 'HitReactionMontages', hits, scope)
    put(da, 'DeathMontage', montages[DEATH_MONTAGE], scope)
    special = {}
    try:
        for k, v in get(da, 'SpecialMontages', scope).items():
            special[str(k)] = v
    except Exception:
        pass
    REPORT['definition']['special_montages_before'] = {k: norm(v) for k, v in special.items()}
    for key, name in SPECIAL_KEYS.items():
        special[key] = montages[name]
    try:
        put(da, 'SpecialMontages', special, scope)
    except Exception:
        typed = u.Map(u.Name, u.AnimMontage)
        for k, v in special.items():
            typed[u.Name(k)] = v
        put(da, 'SpecialMontages', typed, scope)

    # Read-back.
    for cpp, value in DA_FIELDS:
        REPORT['definition'][cpp] = expect(DA_NAME + '.' + cpp, get(da, cpp, scope), value)
    stats = get(da, 'Stats', scope)
    for cpp, value in STAT_FIELDS:
        REPORT['definition']['Stats.' + cpp] = expect(DA_NAME + '.Stats.' + cpp, get(stats, cpp, 'ZE_ZombieStats'),
                                                      value)
    REPORT['definition']['MovementBlendSpace'] = expect(DA_NAME + '.MovementBlendSpace',
                                                        get(da, 'MovementBlendSpace', scope), bs)
    REPORT['definition']['AttackMontages'] = expect(DA_NAME + '.AttackMontages', list(get(da, 'AttackMontages', scope)),
                                                    attacks)
    REPORT['definition']['HitReactionMontages'] = expect(DA_NAME + '.HitReactionMontages',
                                                         list(get(da, 'HitReactionMontages', scope)), hits)
    REPORT['definition']['DeathMontage'] = expect(DA_NAME + '.DeathMontage', get(da, 'DeathMontage', scope),
                                                  montages[DEATH_MONTAGE])
    got = {str(k): norm(v) for k, v in get(da, 'SpecialMontages', scope).items()}
    for key, name in SPECIAL_KEYS.items():
        expect(DA_NAME + '.SpecialMontages[%s]' % key, got.get(key), montages[name])
    REPORT['definition']['SpecialMontages'] = got
    expect(DA_NAME + '.Role', 'KID' in str(get(da, 'Role', scope)).upper(), True)
    return da


# ---------------------------------------------------------------------------------------------

def main():
    global EA
    EA = u.EditorAssetLibrary
    owned = [PKG + '/' + n for n, _, _, _ in MONTAGES] + [PKG + '/' + BS_NAME, PKG + '/' + DA_NAME]
    REPORT['hashes_before'] = {p: sha(file_of(p)) for p in owned}
    REPORT['untouched_hashes_before'] = {p: sha(file_of(p)) for p in UNTOUCHED}
    missing = [p for p, h in REPORT['untouched_hashes_before'].items() if h is None]
    assert not missing, 'Referenced assets missing on disk: %s' % missing

    feral_skel = load(FERAL_SKEL, u.Skeleton)
    kid_mesh = load(KID_MESH, u.SkeletalMesh)
    verify_registration(feral_skel)
    record_vendor()
    if not EA.does_directory_exist(PKG):
        EA.make_directory(PKG)

    montages = author_montages(feral_skel, kid_mesh)
    bs = author_blendspace(feral_skel, kid_mesh)
    da = author_definition(bs, montages)
    stride_info(kid_mesh)
    assert not REPORT['readback_mismatches'], 'Read-back mismatches; nothing saved: %s' % REPORT[
        'readback_mismatches']

    for asset in list(montages.values()) + [bs, da]:
        assert EA.save_loaded_asset(asset, False), 'save_loaded_asset failed for ' + asset.get_path_name()
        REPORT['saved'].append(asset.get_path_name())
    REPORT['hashes_after'] = {p: sha(file_of(p)) for p in owned}
    absent = [p for p, h in REPORT['hashes_after'].items() if not h]
    assert not absent, 'Saved files missing on disk: %s' % absent
    REPORT['untouched_hashes_after'] = {p: sha(file_of(p)) for p in UNTOUCHED}
    changed = [p for p, h in REPORT['untouched_hashes_before'].items() if REPORT['untouched_hashes_after'][p] != h]
    assert not changed, 'Referenced assets changed on disk: %s' % changed
    REPORT['references_unchanged'] = True
    try:
        REPORT['dump'] = dict(u.HoverAuthoring.describe_object_properties(da))
    except Exception:
        REPORT['warnings'].append('describe_object_properties failed: ' + traceback.format_exc(limit=1))


def summary():
    states = {}
    for a in REPORT['assets'].values():
        states[a['state']] = states.get(a['state'], 0) + 1
    slots = ','.join('%s=%s(%s)' % (k, v['slot'], v['how']) for k, v in REPORT['slots'].items())
    return ('KID_FERAL ok=%s assets=%d %s saved=%d slots=%s feralRegistered=%s mismatches=%d warnings=%d errors=%d '
            'receipt=%s' % (REPORT['ok'], len(REPORT['assets']), json.dumps(states), len(REPORT['saved']), slots,
                            REPORT['registration'].get('feral_registered'), len(REPORT['readback_mismatches']),
                            len(REPORT['warnings']), len(REPORT['errors']), RECEIPT))


def dry_run():
    plan = {'package': PKG, 'definition': {'from': DA_KID, 'to': PKG + '/' + DA_NAME, 'fields': DA_FIELDS,
                                           'stats': STAT_FIELDS, 'special': SPECIAL_KEYS,
                                           'death': DEATH_MONTAGE},
            'blendspace': {'name': BS_NAME, 'axis': [BS_AXIS, 0, MAX_SPEED], 'samples': BS_SAMPLES},
            'montages': MONTAGES, 'slot_source': SLOT_SOURCE, 'decoded_slots': DECODED_SLOTS,
            'hold_death_pose': HOLD_DEATH_POSE, 'untouched': UNTOUCHED, 'receipt': str(RECEIPT)}
    print('KID_FERAL_PLAN', json.dumps(plan, default=str), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    try:
        assert u, 'AuthorKidFeral must run inside the Unreal Editor (use --dry-run elsewhere)'
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and len(REPORT['saved']) == len(MONTAGES) + 2
        write_receipt()
        line = summary()
        print(line, flush=True)
        for e in REPORT['errors']:
            print('KID_FERAL error', e, flush=True)
        if u:
            u.log_warning(line)
            for w in REPORT['warnings']:
                u.log_warning('KID_FERAL warning ' + w)
            for e in REPORT['errors']:
                u.log_error('KID_FERAL error ' + e)
            u.SystemLibrary.quit_editor()


if DRY_RUN:
    dry_run()
else:
    run()
