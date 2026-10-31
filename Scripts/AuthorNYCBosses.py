"""Author the two Stage 1 NYC bosses so DA_NYCEncounters can bind them, then quit the editor.

  /Game/HoverPrototype/ZombieEngine/Variants/Golem/DA_StoneGolem    HoverCyberZombieDefinition
  /Game/HoverPrototype/ZombieEngine/Variants/Kid/DA_GiantKid        HoverCyberZombieDefinition

Values: Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md Section 10 (StoneGolem boss build spec, Golem
texture import table, Giant Kid spec) with the Section 1.7 errata applied on top (the errata govern
combat tuning and overwrite the v2 draft fields). After this run, re-run AuthorNYCData.py so
DA_NYCEncounters picks up the two pointers and activates the R13/R19/R27 boss rows.

Golem section (everything new lives under Variants/Golem; /Game/StoneGolem is source art and is
only read, duplicated from, and hashed before/after):
  1. Imports the six Oct 29 Substance PNGs to T_Golem_{Body,Armor}_{BaseColor,Normal,RM}
     (BaseColor sRGB/Default, Normal linear/Normalmap, ORM linear/Masks; max 2048, source 4096 kept).
  2. Builds the local master M_Golem (TextureSampleParameter2D BaseColor / Normal / ORM, ORM R -> AO,
     G -> Roughness, B -> Metallic) and MI_Golem_Body / MI_Golem_Armor.
  3. Duplicates SKEL_StoneGolem_Skeleton -> SKEL_Golem and SKM_StoneGolem -> Optimized/SK_Golem_LODs,
     points the copy at SKEL_Golem (UHoverAuthoring::SetCyberZombieSkeleton), assigns the two MIs to
     the slots M_StoneGolem_Body / M_StoneGolem_Armor (slot names are read back and reported), adds
     the ZESP SK_Mannequin and the vendor golem skeleton to SKEL_Golem.CompatibleSkeletons
     (add_compatible_skeleton on the duplicate, as ReviewKidFeral.py did; never on the vendor
     original), and generates 4 LODs + ConfigureCreatureLODs when the copy has fewer than 4.
  4. Montages from the vendor clips (attack3 Light_A, attack2 Light_B, attack5 Slam, gethit1 Hit,
     death1 Death, turn180 Intro) and the 1D BS_Golem_WalkRun (idle1 0, walkF walk, jogF run).
  5. DA_StoneGolem.
Kid section (Variants/Kid/GiantKid; reads SK_Kid_LODs and the Feral clips, never saves them):
  6. Montages from the Feral clips (registered on SK_Kid_Skeleton by ReviewKidFeral.py) and the 1D
     BS_GiantKid_WalkRun, then DA_GiantKid.

Hit timing: no clip on disk serializes a notify and poses are not decodable, so the
ZE_ZombieAnimNotify_AttackHit / HoverBruteStompNotify times below are length fractions that MUST be
checked in the viewport (receipt key 'notify_times'). Without a hit notify ZE deals no melee damage.

Idempotent: existing owned assets are updated in place (only differing values are written, existing
notify tracks are left alone, textures are not re-imported unless --reimport-textures). Each section
saves only its own assets, only if that section had no error and every read-back matched. Every
touched Content file is hashed before/after, and every read reference is hashed to prove it is
unchanged. Receipt: D:/AFS_Comparisons/NYCSurvival_<date>/bosses_receipt.json.

Run (never concurrently with another editor run):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorNYCBosses.py" -nullrhi -unattended -nosplash
Flags (inside the quoted -ExecutePythonScript value, after the script path):
  --dry-run            print the plan; nothing is loaded, created or saved (also works outside Unreal)
  --only=golem|kid     author one section only
  --reimport-textures  re-import the six PNGs over existing T_Golem_* assets
  --flip-green         set FlipGreenChannel on the two normal maps (OpenGL-preset export)
  --no-lods            skip LOD generation on SK_Golem_LODs
"""
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path

try:
    import unreal as u
except ImportError:  # --dry-run also works outside the editor
    u = None

ARGS = sys.argv[1:]
DRY_RUN = '--dry-run' in ARGS
REIMPORT = '--reimport-textures' in ARGS
FLIP_GREEN = '--flip-green' in ARGS
NO_LODS = '--no-lods' in ARGS
ONLY = next((a.split('=', 1)[1] for a in ARGS if a.startswith('--only=')), None)
SECTIONS = [s for s in ('golem', 'kid') if ONLY in (None, s)]

OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
RECEIPT = OUT / 'bosses_receipt.json'

VARIANTS = '/Game/HoverPrototype/ZombieEngine/Variants'
GOLEM = VARIANTS + '/Golem'
GOLEM_OPT = GOLEM + '/Optimized'
KID = VARIANTS + '/Kid'
GIANT = KID + '/GiantKid'

# Read-only sources (hashed before/after, never saved).
VENDOR_MESH = '/Game/StoneGolem/Mesh/SKM_StoneGolem'
VENDOR_SKEL = '/Game/StoneGolem/Mesh/SKEL_StoneGolem_Skeleton'
VENDOR_PHYS = '/Game/StoneGolem/Mesh/PHYS_StoneGolem'
VENDOR_CLIP = '/Game/StoneGolem/Animations/AS_StoneGolem_'
VENDOR_MASTERS = ['/Game/StoneGolem/Materials/M_StoneGolem_Body', '/Game/StoneGolem/Materials/M_StoneGolem_Armor']
ZESP_SKEL = '/Game/ZESP/Demo/Characters/Mannequins/Meshes/SK_Mannequin'
ZESP_ANIM = '/Game/ZESP/ZE/Animations/Zombies/Zombie_001/'
ZESP_REF = {'attack': ZESP_ANIM + 'AM_Attack_01', 'hit': ZESP_ANIM + 'AM_Hit', 'death': ZESP_ANIM + 'AM_Death',
            'blend': ZESP_ANIM + 'BS_Zombie_WalkRun'}
FERAL = '/Game/FeralZombie/Animations/'
FERAL_SKEL = '/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton'
KID_MESH = KID + '/Optimized/SK_Kid_LODs'
KID_SKEL = KID + '/SK_Kid_Skeleton'
KID_DA = KID + '/DA_Kid'
# BehaviorTree, damage widget/actor classes, perception and loot are copied from this definition.
TEMPLATE_DA = VARIANTS + '/Brute/DA_Brute'

EXPORT = Path('C:/Users/j6sis/OneDrive/Documents/Adobe/Adobe Substance 3D Painter/export')
# (source png, asset name, kind) per the Golem texture import table.
TEXTURES = [
    ('stoneUntitled_M_StoneGolem_Body_BaseColor.png', 'T_Golem_Body_BaseColor', 'color'),
    ('stoneUntitled_M_StoneGolem_Body_Normal.png', 'T_Golem_Body_Normal', 'normal'),
    ('stoneUntitled_M_StoneGolem_Body_OcclusionRoughnessMetallic.png', 'T_Golem_Body_RM', 'masks'),
    ('stoneUntitled_M_StoneGolem_Armor_BaseColor.png', 'T_Golem_Armor_BaseColor', 'color'),
    ('stoneUntitled_M_StoneGolem_Armor_Normal.png', 'T_Golem_Armor_Normal', 'normal'),
    ('stoneUntitled_M_StoneGolem_Armor_OcclusionRoughnessMetallic.png', 'T_Golem_Armor_RM', 'masks'),
]
TEXTURE_MAX = 2048
SOURCE_SIZE = 4096
MASTER = 'M_Golem'
# MI name -> (slot name on SK_Golem_LODs, {parameter: texture asset name}).
INSTANCES = {
    'MI_Golem_Body': ('M_StoneGolem_Body', {'BaseColor': 'T_Golem_Body_BaseColor', 'Normal': 'T_Golem_Body_Normal',
                                            'ORM': 'T_Golem_Body_RM'}),
    'MI_Golem_Armor': ('M_StoneGolem_Armor', {'BaseColor': 'T_Golem_Armor_BaseColor', 'Normal': 'T_Golem_Armor_Normal',
                                              'ORM': 'T_Golem_Armor_RM'}),
}
GOLEM_SKEL_NAME = 'SKEL_Golem'
GOLEM_MESH_NAME = 'SK_Golem_LODs'
LOD_COUNT = 4

# Montage rows: (asset, source clip, role, [(track, fraction of length, notify)]).
# 'hit' = ZE_ZombieAnimNotify_AttackHit (ZE OnAttackHitCheck); 'stomp' = HoverBruteStompNotify on the
# AM_Brute_Stomp precedent track 'AFS_Contact' (StompImpact; with StompDamageMultiplier > 0 it applies the
# radial 30 x multiplier hit instead of the vendor sweep, so stomp montages carry no AttackHit).
GOLEM_MONTAGES = [
    ('AM_Golem_Attack_Light_A', 'attack3', 'attack', [('AFS_Hit', .45, 'hit')]),
    ('AM_Golem_Attack_Light_B', 'attack2', 'attack', [('AFS_Hit', .45, 'hit')]),
    ('AM_Golem_Slam', 'attack5', 'attack', [('AFS_Contact', .55, 'stomp')]),
    ('AM_Golem_Hit', 'gethit1', 'hit', []),
    ('AM_Golem_Death', 'death1', 'death', []),
    ('AM_Golem_Intro', 'turn180', 'special', []),
]
KID_MONTAGES = [
    ('AM_GiantKid_Charge', 'LeapForward_Full', 'special', []),
    ('AM_GiantKid_Strong_01', 'StrongAttack_01', 'attack', [('AFS_Hit', .5, 'hit')]),
    ('AM_GiantKid_Strong_02', 'StrongAttack_02', 'attack', [('AFS_Hit', .5, 'hit')]),
    ('AM_GiantKid_Strong_03', 'StrongAttack_03', 'attack', [('AFS_Contact', .55, 'stomp')]),
    ('AM_GiantKid_Rise', 'Reanimate', 'special', []),
    ('AM_GiantKid_Hit_01', 'HitReact_01', 'hit', []),
    ('AM_GiantKid_Hit_02', 'HitReact_02', 'hit', []),
    ('AM_GiantKid_Hit_03', 'HitReact_03', 'hit', []),
    ('AM_GiantKid_Hit_04', 'HitReact_04', 'hit', []),
    ('AM_GiantKid_Death', 'Death_01', 'death', []),
]
# 1D blendspaces on speed (cm/s): (asset, axis max, [(clip, speed, rate scale)]).
GOLEM_BLEND = ('BS_Golem_WalkRun', 420.0, [('idle1', 0.0, 1.0), ('walkF', 240.0, 1.0), ('jogF', 420.0, 1.0)])
KID_BLEND = ('BS_GiantKid_WalkRun', 650.0, [('Idle_01', 0.0, 1.0), ('Walk', 200.0, 1.0), ('Run', 300.0, 1.0),
                                            ('Run', 650.0, 1.6)])

# Definitions. Errata 1.7 over the Section 10 spec. Stats fields live on the ZE_ZombieStats struct.
GOLEM_STATS = {'MaxHealth': 1500.0, 'WalkSpeed': 240.0, 'RunSpeed': 420.0, 'MeleeDamage': 75.0,
               'AttackRange': 240.0, 'AttackCooldown': 3.0, 'AttackSphereRadius': 90.0,
               'MinGoldReward': 500, 'MaxGoldReward': 500}
GOLEM_FIELDS = {'Height': 320.0, 'CapsuleRadius': 70.0, 'MaximumRunSpeed': 420.0, 'StompRadius': 600.0,
                'CloseWalkSpeed': 240.0, 'bUsesStomp': True, 'StompDamageMultiplier': 2.5,
                'StompCooldown': 4.0, 'StompInterval': 4.0, 'KillPoints': 500}
KID_STATS = {'MaxHealth': 1200.0, 'WalkSpeed': 200.0, 'RunSpeed': 300.0, 'MeleeDamage': 90.0,
             'AttackRange': 260.0, 'AttackCooldown': 2.5, 'AttackSphereRadius': 90.0,
             'MinGoldReward': 500, 'MaxGoldReward': 500}
KID_FIELDS = {'Height': 320.0, 'CapsuleRadius': 60.0, 'MaximumRunSpeed': 650.0, 'StompRadius': 500.0,
              'bUsesStomp': True, 'StompDamageMultiplier': 2.0, 'StompCooldown': 2.5, 'StompInterval': 2.5,
              'SecondLifeFraction': .30, 'KillPoints': 500}
# Data only today (nothing evaluates phases): E3 "enraged 650 below 50%".
KID_PHASES = [{'HealthFraction': .5, 'SpeedOverride': 650.0, 'bEnrage': True}]
GOLEM_SPECIALS = {'Slam': 'AM_Golem_Slam', 'Intro': 'AM_Golem_Intro'}
KID_SPECIALS = {'Charge': 'AM_GiantKid_Charge', 'Rise': 'AM_GiantKid_Rise'}
TEMPLATE_COPY = ['BehaviorTree', 'DamageWidgetClass', 'DamageActorClass']

# Design items deliberately left at their defaults (reported).
LEFT_DEFAULT = [
    'AggroSound/AttackSound/DeathSound, SightRoar, Slow/FastTierVocal: Etherion cues (SC_Entity_Roar, S_Entity_Hit_A-C, '
    'S_Entity_Death / S_Entity_Slash_A, SC_Entity_Death) need owner licence sign-off; the audit keeps silence',
    'AnimClassOverride: None (BP_NYCZombie keeps ABP_ZombieMaster; works through the CompatibleSkeletons registration)',
    'CapsuleHalfHeight 0 (= Height * .5), RotationYaw 0 / MaxAcceleration 0 (Boss role default 220 yaw, 1400 accel)',
    'HeadBoneName: template value (ZE default "Head"; FName compare is case-insensitive, golem/kid bone is "head")',
    'Golem BossPhases: none (E1 withdraws the armor-break phases and the x3 weak point)',
    'Golem 2.1 s knockdown / Giant Kid 2.1 s knockdown: AHoverPilot::ApplyStompKnockdown, no DA field',
    'Giant Kid guaranteed Max Ammo, Insta-Kill two kills, lethal-hit clamp at the 30% crossing: code rules, no DA field',
    'FlinchDamageFraction/FlinchMontageCooldown/WindupSeconds, QueueRingRadius, SeparationWeight: class defaults',
    'Golem PHYS: SK_Golem_LODs keeps the vendor PHYS_StoneGolem reference (identical bone names); no PA_Golem copy',
    'SK_Golem (non-LOD runtime copy) and the 25-clip duplicate-and-retarget onto SKEL_Golem: not done; montages and '
    'the blendspace reference the vendor clips through SKEL_Golem.CompatibleSkeletons',
    'ConfigureVariantSkeleton (translation retargeting modes) not run on SKEL_Golem: registration only, as ReviewKidFeral',
    'Giant Kid Etherion Walk_Giant/Roar, Feasting_01-03, LeapForward_Short pounce: not registered on SK_Kid_Skeleton '
    '(Etherion) or not named in this slice',
]

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'sections': {}, 'errors': [], 'warnings': [], 'created': [],
          'modified': [], 'saved': [], 'hashes_before': {}, 'hashes_after': {}, 'untouched_hashes_before': {},
          'untouched_hashes_after': {}, 'untouched_changed': [], 'python_names': {}, 'readback_mismatches': [],
          'notify_times': {}, 'slots': {}, 'skeleton': {}, 'textures': {}, 'lods': {}, 'blendspaces': {},
          'montage_slots': {}, 'left_default': LEFT_DEFAULT,
          'claim': 'Editor asset authoring only; no gameplay run, no rendered evidence'}
EA = AT = ML = AL = None


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('NYC_BOSSES receipt failed', traceback.format_exc(), flush=True)


# ---------------------------------------------------------------------------------------------
# Python name resolution (same rules as AuthorNYCData.py: Foo -> foo, bFoo -> foo).

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


def pathish(value):
    """Object/soft pointer/path -> '/Game/...' package path (object name suffix dropped)."""
    if value is None:
        return None
    text = value.get_path_name() if hasattr(value, 'get_path_name') else str(value)
    text = text.strip().strip("'\"")
    return text.split('.')[0] if text.startswith('/') else text


def soft_text(value):
    """unreal.SoftObjectPath -> '/Pkg/Asset.Asset' text (an unloaded TSoftObjectPtr comes back as one)."""
    try:
        return value.export_text()
    except Exception:
        return str(u.SystemLibrary.break_soft_object_path(value))


def norm(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, 'get_path_name'):
        return pathish(value)
    if u and isinstance(value, u.SoftObjectPath):
        return pathish(soft_text(value)) or None
    if isinstance(value, dict) or (u and isinstance(value, u.Map)):
        return sorted((str(k), norm(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)) or (u and isinstance(value, (u.Array, getattr(u, 'FixedArray', ())))):
        return [norm(v) for v in value]
    if u and isinstance(value, u.Name):
        return str(value)
    return str(value)


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-3
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, tuple) and isinstance(b, tuple):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def put(holder, cpp, value, scope, changes):
    """Write only when the normalized value differs; returns True when written."""
    name = resolve(holder, cpp, scope)
    if same(norm(holder.get_editor_property(name)), norm(value)):
        return False
    holder.set_editor_property(name, value)
    changes.append(scope + '.' + cpp)
    return True


def check(holder, cpp, expected, scope):
    actual = norm(holder.get_editor_property(resolve(holder, cpp, scope)))
    if not same(actual, norm(expected)):
        REPORT['readback_mismatches'].append({'field': scope + '.' + cpp, 'expected': norm(expected),
                                              'actual': actual})


def enum_value(enum_cls_name, member):
    cls = getattr(u, enum_cls_name)
    return getattr(cls, member)


# ---------------------------------------------------------------------------------------------
# Files and hashes.

def file_of(asset_path, ext='.uasset'):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return content / (asset_path[len('/Game/'):] + ext)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def png_size(path):
    with open(str(path), 'rb') as f:
        head = f.read(24)
    assert head[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG: %s' % path
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def owned_paths(section):
    if section == 'golem':
        paths = [GOLEM + '/' + name for _, name, _ in TEXTURES]
        paths += [GOLEM + '/' + MASTER] + [GOLEM + '/' + n for n in INSTANCES]
        paths += [GOLEM + '/' + GOLEM_SKEL_NAME, GOLEM_OPT + '/' + GOLEM_MESH_NAME]
        paths += [GOLEM + '/' + row[0] for row in GOLEM_MONTAGES] + [GOLEM + '/' + GOLEM_BLEND[0]]
        paths += [GOLEM + '/DA_StoneGolem']
    else:
        paths = [GIANT + '/' + row[0] for row in KID_MONTAGES] + [GIANT + '/' + KID_BLEND[0], KID + '/DA_GiantKid']
    return paths


def read_paths(section):
    if section == 'golem':
        paths = [VENDOR_MESH, VENDOR_SKEL, VENDOR_PHYS, ZESP_SKEL, TEMPLATE_DA] + VENDOR_MASTERS
        paths += sorted(set(VENDOR_CLIP + row[1] for row in GOLEM_MONTAGES) |
                        set(VENDOR_CLIP + c for c, _, _ in GOLEM_BLEND[2]))
    else:
        paths = [KID_MESH, KID_SKEL, KID_DA, FERAL_SKEL, TEMPLATE_DA]
        paths += sorted(set(FERAL + row[1] for row in KID_MONTAGES) | set(FERAL + c for c, _, _ in KID_BLEND[2]))
    return paths + sorted(ZESP_REF.values())


# ---------------------------------------------------------------------------------------------
# Asset helpers.

def load(path):
    assert EA.does_asset_exist(path), 'missing asset ' + path
    asset = EA.load_asset(path)
    assert asset, 'failed to load ' + path
    return asset


def track(section, asset, created):
    path = pathish(asset)
    (REPORT['created'] if created else REPORT['modified']).append(path)
    SECTION_ASSETS[section].append(asset)


def create_new(name, pkg, cls, factory):
    asset = AT.create_asset(name, pkg, cls, factory)
    assert asset and isinstance(asset, cls), 'create_asset failed for %s/%s' % (pkg, name)
    return asset


def ensure_existing_class(path, cls):
    asset = load(path)
    assert isinstance(asset, cls), '%s exists but is %s, not %s; refusing to touch it' % (
        path, asset.get_class().get_name(), cls.__name__)
    return asset


def skeleton_of(asset):
    for attempt in (lambda: asset.get_editor_property('skeleton'), lambda: asset.skeleton,
                    lambda: asset.get_skeleton()):
        try:
            value = attempt()
            if value:
                return value
        except Exception:
            continue
    return None


def compatible_paths(skel):
    return [pathish(x) for x in (skel.get_editor_property('compatible_skeletons') or [])]


# ---------------------------------------------------------------------------------------------
# Golem: textures, material, mesh/skeleton.

def import_textures(section):
    textures = {}
    for png, name, kind in TEXTURES:
        src = EXPORT / png
        path = GOLEM + '/' + name
        entry = {'source': str(src)}
        assert src.is_file(), 'missing Substance export ' + str(src)
        entry['source_sha256'] = sha(src)
        entry['source_size'] = png_size(src)
        if entry['source_size'] != (SOURCE_SIZE, SOURCE_SIZE):
            REPORT['warnings'].append('%s is %s, expected %d^2' % (png, entry['source_size'], SOURCE_SIZE))
        exists = EA.does_asset_exist(path)
        if not exists or REIMPORT:
            task = u.AssetImportTask()
            task.set_editor_property('filename', str(src))
            task.set_editor_property('destination_path', GOLEM)
            task.set_editor_property('destination_name', name)
            task.set_editor_property('automated', True)
            task.set_editor_property('replace_existing', True)
            task.set_editor_property('save', False)
            AT.import_asset_tasks([task])
            imported = [str(p) for p in (task.get_editor_property('imported_object_paths') or [])]
            entry['imported'] = imported
            assert any(p.split('.')[0] == path for p in imported), 'import failed for %s -> %s (%s)' % (
                png, path, imported)
        tex = ensure_existing_class(path, u.Texture2D)
        changes = []
        scope = 'Texture2D[%s]' % name
        put(tex, 'SRGB', kind == 'color', scope, changes)
        put(tex, 'CompressionSettings', {'color': u.TextureCompressionSettings.TC_DEFAULT,
                                         'normal': u.TextureCompressionSettings.TC_NORMALMAP,
                                         'masks': u.TextureCompressionSettings.TC_MASKS}[kind], scope, changes)
        put(tex, 'LODGroup', {'color': u.TextureGroup.TEXTUREGROUP_CHARACTER,
                              'normal': u.TextureGroup.TEXTUREGROUP_CHARACTER_NORMAL_MAP,
                              'masks': u.TextureGroup.TEXTUREGROUP_CHARACTER_SPECULAR}[kind], scope, changes)
        put(tex, 'MaxTextureSize', TEXTURE_MAX, scope, changes)
        if kind == 'normal':
            put(tex, 'bFlipGreenChannel', FLIP_GREEN, scope, changes)
        entry['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
        entry['changes'] = changes
        try:
            entry['inspect'] = u.HoverAuthoring.inspect_texture(tex)
        except Exception:
            entry['inspect'] = 'n/a'
        REPORT['textures'][name] = entry
        if not exists or REIMPORT or changes:
            track(section, tex, not exists)
        textures[name] = tex
    return textures


def build_master(section, textures):
    path = GOLEM + '/' + MASTER
    created = not EA.does_asset_exist(path)
    mat = create_new(MASTER, GOLEM, u.Material, u.MaterialFactoryNew()) if created else ensure_existing_class(
        path, u.Material)
    params = sorted(str(n) for n in ML.get_texture_parameter_names(mat))
    count = ML.get_num_material_expressions(mat)
    rebuilt = False
    if created or params != ['BaseColor', 'Normal', 'ORM'] or count != 3:
        ML.delete_all_material_expressions(mat)
        rows = [('BaseColor', 'T_Golem_Body_BaseColor', u.MaterialSamplerType.SAMPLERTYPE_COLOR, -500,
                 [('RGB', u.MaterialProperty.MP_BASE_COLOR)]),
                ('Normal', 'T_Golem_Body_Normal', u.MaterialSamplerType.SAMPLERTYPE_NORMAL, -150,
                 [('RGB', u.MaterialProperty.MP_NORMAL)]),
                ('ORM', 'T_Golem_Body_RM', u.MaterialSamplerType.SAMPLERTYPE_MASKS, 200,
                 [('R', u.MaterialProperty.MP_AMBIENT_OCCLUSION), ('G', u.MaterialProperty.MP_ROUGHNESS),
                  ('B', u.MaterialProperty.MP_METALLIC)])]
        for param, tex, sampler, y, outputs in rows:
            node = ML.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, -420, y)
            assert node, 'create_material_expression failed for ' + param
            node.set_editor_property('parameter_name', param)
            node.set_editor_property('texture', textures[tex])
            node.set_editor_property('sampler_type', sampler)
            for output, prop in outputs:
                assert ML.connect_material_property(node, output, prop), 'connect %s.%s failed' % (param, output)
        rebuilt = True
    changes = []
    put(mat, 'bUsedWithSkeletalMesh', True, 'Material[M_Golem]', changes)
    if rebuilt or changes:
        ML.recompile_material(mat)
        track(section, mat, created)
    params = sorted(str(n) for n in ML.get_texture_parameter_names(mat))
    if params != ['BaseColor', 'Normal', 'ORM']:
        REPORT['readback_mismatches'].append({'field': 'M_Golem.texture_parameters', 'expected':
                                              ['BaseColor', 'Normal', 'ORM'], 'actual': params})
    REPORT['sections'][section]['master'] = {'state': 'created' if created else ('rebuilt' if rebuilt else 'existing'),
                                             'parameters': params, 'changes': changes,
                                             'expressions': ML.get_num_material_expressions(mat)}
    return mat


def texture_diag(tex):
    out = {}
    for prop in ('virtual_texture_streaming', 'srgb', 'compression_settings', 'lod_group'):
        try:
            out[prop] = str(tex.get_editor_property(prop))
        except Exception as exc:
            out[prop] = 'n/a (%s)' % exc
    return out


def set_texture_parameter(section, mi, name, param, tex):
    """MaterialEditingLibrary setter first; on False fall back to writing TextureParameterValues directly."""
    parent = mi.get_editor_property('parent')
    diag = {'param': param, 'texture': pathish(tex), 'texture_props': texture_diag(tex), 'parent': pathish(parent),
            'parent_params': sorted(str(n) for n in ML.get_texture_parameter_names(parent))}
    diag['library_ok'] = bool(ML.set_material_instance_texture_parameter_value(mi, param, tex))
    if not diag['library_ok']:
        info = u.MaterialParameterInfo()
        info.set_editor_property('name', param)
        info.set_editor_property('association', u.MaterialParameterAssociation.GLOBAL_PARAMETER)
        info.set_editor_property('index', -1)
        value = u.TextureParameterValue()
        value.set_editor_property('parameter_info', info)
        value.set_editor_property('parameter_value', tex)
        rows = [r for r in (mi.get_editor_property('texture_parameter_values') or [])
                if str(r.get_editor_property('parameter_info').get_editor_property('name')) != param]
        mi.set_editor_property('texture_parameter_values', rows + [value])
        diag['fallback'] = 'texture_parameter_values'
    diag['readback'] = pathish(ML.get_material_instance_texture_parameter_value(mi, param))
    REPORT['sections'][section].setdefault('instance_sets', {}).setdefault(name, []).append(diag)
    assert diag['readback'] == pathish(tex), '%s.%s set failed: %s' % (name, param, diag)


def build_instances(section, master, textures):
    out = {}
    for name, (_, params) in INSTANCES.items():
        path = GOLEM + '/' + name
        created = not EA.does_asset_exist(path)
        mi = create_new(name, GOLEM, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew()) \
            if created else ensure_existing_class(path, u.MaterialInstanceConstant)
        changed = False
        if pathish(mi.get_editor_property('parent')) != pathish(master):
            ML.set_material_instance_parent(mi, master)
            changed = True
        for param, tex in params.items():
            current = ML.get_material_instance_texture_parameter_value(mi, param)
            if pathish(current) != pathish(textures[tex]):
                set_texture_parameter(section, mi, name, param, textures[tex])
                changed = True
        if changed:
            ML.update_material_instance(mi)
            track(section, mi, created)
        for param, tex in params.items():
            got = pathish(ML.get_material_instance_texture_parameter_value(mi, param))
            if got != pathish(textures[tex]):
                REPORT['readback_mismatches'].append({'field': name + '.' + param, 'expected': pathish(textures[tex]),
                                                      'actual': got})
        out[name] = mi
    return out


def slot_rows(mesh):
    rows = []
    for m in mesh.get_editor_property('materials'):
        row = {'slot': str(m.get_editor_property('material_slot_name')),
               'material': pathish(m.get_editor_property('material_interface'))}
        try:
            row['imported_slot'] = str(m.get_editor_property('imported_material_slot_name'))
        except Exception:
            row['imported_slot'] = None
        rows.append(row)
    return rows


def lods_configured(mesh):
    """True when ConfigureCreatureLODs' LOD1 screen size (.45) is on the mesh (screen size, else triangle ratio)."""
    try:
        info = mesh.get_editor_property('lod_info')[1]
        size = float(info.get_editor_property('screen_size').get_editor_property('default'))
        return {'ok': abs(size - .45) < 1e-3, 'lod1_screen_size': size}
    except Exception:
        pass
    try:
        tris = [int(line.split('triangles=')[1].split()[0]) for line in
                u.HoverAuthoring.inspect_character_mesh(mesh).splitlines() if line.startswith('LOD=')]
        ratio = tris[1] / float(tris[0])
        return {'ok': ratio > .4, 'lod1_triangle_ratio': round(ratio, 3)}
    except Exception:
        return {'ok': False, 'error': traceback.format_exc(limit=1)}


def build_mesh(section, instances):
    vendor_skel = load(VENDOR_SKEL)
    zesp_skel = load(ZESP_SKEL)
    skel_path = GOLEM + '/' + GOLEM_SKEL_NAME
    mesh_path = GOLEM_OPT + '/' + GOLEM_MESH_NAME
    info = REPORT['skeleton']

    skel_created = not EA.does_asset_exist(skel_path)
    if skel_created:
        skel = EA.duplicate_asset(VENDOR_SKEL, skel_path)
        assert skel and isinstance(skel, u.Skeleton), 'duplicate_asset failed for ' + skel_path
    else:
        skel = ensure_existing_class(skel_path, u.Skeleton)
    skel_changed = skel_created

    mesh_created = not EA.does_asset_exist(mesh_path)
    if mesh_created:
        mesh = EA.duplicate_asset(VENDOR_MESH, mesh_path)
        assert mesh and isinstance(mesh, u.SkeletalMesh), 'duplicate_asset failed for ' + mesh_path
    else:
        mesh = ensure_existing_class(mesh_path, u.SkeletalMesh)
    mesh_changed = mesh_created
    REPORT['slots']['before'] = slot_rows(mesh)

    info['mesh_skeleton_before'] = pathish(skeleton_of(mesh))
    if info['mesh_skeleton_before'] != skel_path:
        assert u.HoverAuthoring.set_cyber_zombie_skeleton(mesh, skel), \
            'SetCyberZombieSkeleton refused %s -> %s (path gate or missing bone)' % (mesh_path, skel_path)
        mesh_changed = True
    info['mesh_skeleton_after'] = pathish(skeleton_of(mesh))
    assert info['mesh_skeleton_after'] == skel_path, 'mesh skeleton is %s' % info['mesh_skeleton_after']

    info['compatible_before'] = compatible_paths(skel)
    for other in (zesp_skel, vendor_skel):
        if pathish(other) not in compatible_paths(skel):
            skel.add_compatible_skeleton(other)
            skel_changed = True
    info['compatible_after'] = compatible_paths(skel)
    for want in (ZESP_SKEL, VENDOR_SKEL):
        if want not in info['compatible_after']:
            REPORT['readback_mismatches'].append({'field': 'SKEL_Golem.CompatibleSkeletons', 'expected': want,
                                                  'actual': info['compatible_after']})
    try:
        preview = AL.get_skeleton_preview_mesh(skel, False)
        if pathish(preview) != mesh_path:
            AL.set_skeleton_preview_mesh(skel, mesh, True)
            skel_changed = True
    except Exception:
        REPORT['warnings'].append('SKEL_Golem preview mesh not set: ' + traceback.format_exc(limit=1))

    # Material slots.
    wanted = {slot: instances[name] for name, (slot, _) in INSTANCES.items()}
    materials = list(mesh.get_editor_property('materials'))
    found = set()
    slots_changed = False
    for m in materials:
        names = {str(m.get_editor_property('material_slot_name'))}
        try:
            names.add(str(m.get_editor_property('imported_material_slot_name')))
        except Exception:
            pass
        hit = next((s for s in wanted if s in names), None)
        if hit:
            found.add(hit)
            if pathish(m.get_editor_property('material_interface')) != pathish(wanted[hit]):
                m.set_editor_property('material_interface', wanted[hit])
                slots_changed = True
    missing = sorted(set(wanted) - found)
    if missing:
        raise RuntimeError('SK_Golem_LODs has no slot named %s; slots are %s' % (missing, REPORT['slots']['before']))
    if slots_changed:
        mesh.set_editor_property('materials', materials)
        mesh_changed = True
    REPORT['slots']['after'] = slot_rows(mesh)
    for row in REPORT['slots']['after']:
        target = wanted.get(row['slot']) or wanted.get(row['imported_slot'])
        if target and row['material'] != pathish(target):
            REPORT['readback_mismatches'].append({'field': 'SK_Golem_LODs.slot ' + row['slot'],
                                                  'expected': pathish(target), 'actual': row['material']})

    # LODs (ConfigureCreatureLODs needs at least 4 and an /Optimized/ path).
    lods = REPORT['lods']
    try:
        lods['before'] = int(u.SkeletalMeshEditorSubsystem.get_lod_count(mesh))
    except Exception:
        lods['before'] = None
        REPORT['warnings'].append('get_lod_count unavailable; LOD step skipped: ' + traceback.format_exc(limit=1))
    lods['action'] = 'skipped (--no-lods)' if NO_LODS else 'none needed'
    need_generate = lods['before'] is not None and lods['before'] < LOD_COUNT
    if lods['before'] is not None and not need_generate:
        lods['configured_before'] = lods_configured(mesh)
    need_configure = need_generate or (lods['before'] is not None and not lods.get('configured_before', {}).get('ok'))
    if not NO_LODS and need_configure:
        try:
            if need_generate:
                lods['regenerate_1'] = u.SkeletalMeshEditorSubsystem.regenerate_lod(mesh, LOD_COUNT, False, False)
                mesh_changed = True
            # UE exposes ConfigureCreatureLODs as configure_creature_lo_ds; match it by letters, not spelling.
            configure = next((getattr(u.HoverAuthoring, n) for n in dir(u.HoverAuthoring)
                              if n.replace('_', '') == 'configurecreaturelods'), None)
            assert configure, 'HoverAuthoring.ConfigureCreatureLODs is not exposed to Python'
            lods['configure'] = configure(mesh)
            if lods['configure']:
                lods['regenerate_2'] = u.SkeletalMeshEditorSubsystem.regenerate_lod(mesh, 0, False, False)
                mesh_changed = True
            lods['action'] = 'generated' if need_generate else 'configured'
            lods['configured_after'] = lods_configured(mesh)
        except Exception:
            lods['action'] = 'failed'
            REPORT['warnings'].append('LOD generation/configuration failed (%s LODs before): %s' % (
                lods['before'], traceback.format_exc(limit=2)))
    try:
        lods['after'] = u.SkeletalMeshEditorSubsystem.get_lod_count(mesh)
        lods['inspect'] = u.HoverAuthoring.inspect_character_mesh(mesh)
    except Exception:
        lods['after'] = 'n/a'
    try:
        REPORT['sections'][section]['physics_asset'] = pathish(mesh.get_editor_property('physics_asset'))
    except Exception:
        REPORT['sections'][section]['physics_asset'] = 'n/a'

    if skel_changed:
        track(section, skel, skel_created)
    if mesh_changed:
        track(section, mesh, mesh_created)
    return skel, mesh


# ---------------------------------------------------------------------------------------------
# Montages and blendspaces (shared).

def vendor_reference():
    ref = {}
    for key in ('attack', 'hit', 'death'):
        m = load(ZESP_REF[key])
        row = {'slots': [str(s) for s in AL.get_montage_slot_names(m)], 'length': m.get_play_length()}
        try:
            row['auto_blend_out'] = bool(m.get_editor_property('enable_auto_blend_out'))
        except Exception:
            row['auto_blend_out'] = None
        try:
            events = AL.get_animation_notify_events(m)
            row['notify_fractions'] = [round(AL.get_anim_notify_event_trigger_time(e) / max(.001, row['length']), 3)
                                       for e in events]
        except Exception:
            row['notify_fractions'] = 'n/a'
        ref[key] = row
    return ref


def describe_event(event, track_name, kind, length):
    row = {'track': track_name, 'kind': kind}
    try:
        t = AL.get_anim_notify_event_trigger_time(event)
        row.update({'time': round(t, 3), 'fraction': round(t / max(.001, length), 3)})
    except Exception:
        row.update({'time': None, 'fraction': None})
    try:
        notify = event.get_editor_property('notify')
        row['class'] = notify.get_class().get_name() if notify else None
    except Exception:
        row['class'] = None
    return row


def notify_class(kind):
    return (u.ZE_ZombieAnimNotify_AttackHit if kind == 'hit' else u.HoverBruteStompNotify).static_class()


def ensure_montage(section, pkg, name, seq, role, notifies, ref):
    path = pkg + '/' + name
    created = not EA.does_asset_exist(path)
    if created:
        factory = u.AnimMontageFactory()
        factory.set_editor_property('target_skeleton', skeleton_of(seq))
        factory.set_editor_property('source_animation', seq)
        montage = create_new(name, pkg, u.AnimMontage, factory)
    else:
        montage = ensure_existing_class(path, u.AnimMontage)
    changed = created
    # The existing montage must still wrap the expected clip.
    try:
        tracks = montage.get_editor_property('slot_anim_tracks')
        segment = tracks[0].get_editor_property('anim_track').get_editor_property('anim_segments')[0]
        source = pathish(segment.get_editor_property('anim_reference'))
        if source != pathish(seq):
            REPORT['readback_mismatches'].append({'field': name + '.source', 'expected': pathish(seq),
                                                  'actual': source})
    except Exception:
        REPORT['warnings'].append('%s: source clip not readable from Python (unverified)' % name)
    slots = [str(s) for s in AL.get_montage_slot_names(montage)]
    REPORT['montage_slots'][name] = slots
    want_slots = ref['attack']['slots']
    if slots != want_slots:
        REPORT['warnings'].append('%s slots %s differ from vendor AM_Attack_01 %s (ABP_ZombieMaster slot); '
                                  'left as created' % (name, slots, want_slots))
    if role == 'death' and ref['death'].get('auto_blend_out') is not None:
        try:
            cur = bool(montage.get_editor_property('enable_auto_blend_out'))
            if cur != ref['death']['auto_blend_out']:
                montage.set_editor_property('enable_auto_blend_out', ref['death']['auto_blend_out'])
                changed = True
        except Exception:
            REPORT['warnings'].append('%s: enable_auto_blend_out not writable' % name)
    length = montage.get_play_length()
    times = []
    for track_name, fraction, kind in notifies:
        if not AL.is_valid_anim_notify_track_name(montage, track_name):
            AL.add_animation_notify_track(montage, track_name, u.LinearColor(1, .3, .1, 1))
            changed = True
        events = AL.get_animation_notify_events_for_track(montage, track_name)
        if not events:
            notify = AL.add_animation_notify_event(montage, track_name, length * fraction, notify_class(kind))
            assert notify, '%s: add_animation_notify_event failed on %s' % (name, track_name)
            changed = True
            events = AL.get_animation_notify_events_for_track(montage, track_name)
        for e in events:
            times.append(describe_event(e, track_name, kind, length))
        if not any(t['class'] and t['class'] == notify_class(kind).get_name() for t in times
                   if t['track'] == track_name):
            REPORT['readback_mismatches'].append({'field': name + '.' + track_name, 'expected':
                                                  notify_class(kind).get_name(), 'actual': times})
    REPORT['notify_times'][name] = {'length': round(length, 3), 'source': pathish(seq), 'events': times}
    if changed:
        track(section, montage, created)
    return montage


def ensure_blend(section, pkg, name, skeleton, axis_max, samples, ref_blend):
    path = pkg + '/' + name
    created = not EA.does_asset_exist(path)
    if created:
        factory = u.BlendSpaceFactory1D()
        factory.set_editor_property('target_skeleton', skeleton)
        blend = create_new(name, pkg, u.BlendSpace1D, factory)
    else:
        blend = ensure_existing_class(path, u.BlendSpace1D)
    changed = created
    info = {'state': 'created' if created else 'existing'}
    params = blend.get_editor_property('blend_parameters')  # FBlendParameter[3] (FixedArray)
    ref_params = ref_blend.get_editor_property('blend_parameters')
    axis = params[0]
    info['vendor_axis'] = {k: norm(ref_params[0].get_editor_property(k)) for k in ('display_name', 'min', 'max',
                                                                                     'grid_num')}
    want = {'display_name': str(ref_params[0].get_editor_property('display_name')) or 'Speed', 'min': 0.0,
            'max': axis_max, 'grid_num': int(ref_params[0].get_editor_property('grid_num')), 'snap_to_grid': False}
    if any(not same(norm(axis.get_editor_property(k)), norm(v)) for k, v in want.items()):
        for k, v in want.items():
            axis.set_editor_property(k, v)
        params[0] = axis
        try:
            blend.set_editor_property('blend_parameters', params)
            info['axis_write'] = 'fixed_array'
        except Exception:
            blend.set_editor_property('blend_parameters', [params[i] for i in range(len(params))])
            info['axis_write'] = 'list'
        changed = True
    want_samples = [(pathish(seq), speed, rate) for seq, speed, rate in samples]
    have = [(pathish(s.get_editor_property('animation')), round(s.get_editor_property('sample_value').x, 3),
             round(s.get_editor_property('rate_scale'), 3)) for s in blend.get_editor_property('sample_data')]
    if not same([list(x) for x in have], [list(x) for x in want_samples]):
        rows = []
        for seq, speed, rate in samples:
            s = u.BlendSample()
            s.set_editor_property('animation', seq)
            s.set_editor_property('sample_value', u.Vector(speed, 0, 0))
            s.set_editor_property('rate_scale', rate)
            rows.append(s)
        blend.set_editor_property('sample_data', rows)
        changed = True
    got_axis = blend.get_editor_property('blend_parameters')[0]
    info['axis'] = {k: norm(got_axis.get_editor_property(k)) for k in want}
    info['samples'] = [(pathish(s.get_editor_property('animation')), round(s.get_editor_property('sample_value').x, 3),
                        round(s.get_editor_property('rate_scale'), 3)) for s in blend.get_editor_property('sample_data')]
    if not same([list(x) for x in info['samples']], [list(x) for x in want_samples]):
        REPORT['readback_mismatches'].append({'field': name + '.SampleData', 'expected': want_samples,
                                              'actual': info['samples']})
    if not same(info['axis']['max'], axis_max):
        REPORT['readback_mismatches'].append({'field': name + '.BlendParameters[0].Max', 'expected': axis_max,
                                              'actual': info['axis']['max']})
    REPORT['blendspaces'][name] = info
    if changed:
        track(section, blend, created)
    return blend


# ---------------------------------------------------------------------------------------------
# Definitions.

def ensure_definition(section, pkg, name):
    path = pkg + '/' + name
    if EA.does_asset_exist(path):
        return ensure_existing_class(path, u.HoverCyberZombieDefinition), False
    factory = u.DataAssetFactory()
    factory.set_editor_property('data_asset_class', u.HoverCyberZombieDefinition.static_class())
    return create_new(name, pkg, u.HoverCyberZombieDefinition, factory), True


def author_definition(section, pkg, name, mesh, role, kind, stats_values, fields, montages, blend, specials, phases):
    da, created = ensure_definition(section, pkg, name)
    template = load(TEMPLATE_DA)
    scope = 'HoverCyberZombieDefinition[%s]' % name
    changes = []
    expected = {}
    # Template-only fields first (behaviour tree, damage numbers).
    for cpp in TEMPLATE_COPY:
        value = template.get_editor_property(resolve(template, cpp, 'HoverCyberZombieDefinition[template]'))
        if value is None:
            REPORT['warnings'].append('%s.%s is None on the template; left default' % (name, cpp))
            continue
        if u and isinstance(value, u.SoftObjectPath):  # unloaded soft pointer: write/compare the loaded object
            soft = pathish(soft_text(value))
            value = EA.load_asset(soft) if soft else None
            if value is None:
                REPORT['warnings'].append('%s.%s soft path %r on the template did not load; left default'
                                          % (name, cpp, soft))
                continue
        put(da, cpp, value, scope, changes)
        expected[cpp] = value
    # Stats: start from the template's struct (perception, loot, debug flags), then the boss values.
    stats_scope = 'ZE_ZombieStats[%s]' % name
    stats = da.get_editor_property(resolve(da, 'Stats', scope)) if not created else \
        template.get_editor_property(resolve(template, 'Stats', 'HoverCyberZombieDefinition[template]'))
    stats_changes = []
    if created:
        stats_changes.append('Stats<-template')
    for cpp, value in stats_values.items():
        put(stats, cpp, value, stats_scope, stats_changes)
    stats_written = bool(stats_changes)
    if stats_written:
        da.set_editor_property(resolve(da, 'Stats', scope), stats)
        changes.extend(stats_changes)
    attacks = [montages[r[0]] for r in montages['_rows'] if r[2] == 'attack']
    hits = [montages[r[0]] for r in montages['_rows'] if r[2] == 'hit']
    death = next(montages[r[0]] for r in montages['_rows'] if r[2] == 'death')
    special_map = {key: montages[asset] for key, asset in specials.items()}
    values = dict(fields)
    values.update({'AppearanceMesh': mesh, 'Role': role, 'SpecialKind': kind, 'MovementBlendSpace': blend,
                   'AttackMontages': attacks, 'HitReactionMontages': hits, 'DeathMontage': death,
                   'SpecialMontages': special_map})
    for cpp, value in values.items():
        put(da, cpp, value, scope, changes)
        expected[cpp] = value
    # Boss phases (struct array): compare per field, rewrite when anything differs.
    phase_scope = 'HoverBossPhase'
    current = list(da.get_editor_property(resolve(da, 'BossPhases', scope)))
    current_norm = [{cpp: norm(p.get_editor_property(resolve(p, cpp, phase_scope))) for cpp in row}
                    for p, row in zip(current, phases)]
    if len(current) != len(phases) or not all(same(norm(v), c[k]) for row, c in zip(phases, current_norm)
                                              for k, v in row.items()):
        rows = []
        for row in phases:
            p = u.HoverBossPhase()
            for cpp, value in row.items():
                p.set_editor_property(resolve(p, cpp, phase_scope), value)
            rows.append(p)
        da.set_editor_property(resolve(da, 'BossPhases', scope), rows)
        changes.append(scope + '.BossPhases')
    # Read-back.
    for cpp, value in expected.items():
        check(da, cpp, value, scope)
    got_stats = da.get_editor_property(resolve(da, 'Stats', scope))
    for cpp, value in stats_values.items():
        check(got_stats, cpp, value, stats_scope)
    got_phases = list(da.get_editor_property(resolve(da, 'BossPhases', scope)))
    if len(got_phases) != len(phases):
        REPORT['readback_mismatches'].append({'field': scope + '.BossPhases', 'expected': len(phases),
                                              'actual': len(got_phases)})
    else:
        for p, row in zip(got_phases, phases):
            for cpp, value in row.items():
                check(p, cpp, value, phase_scope)
    REPORT['sections'][section]['definition'] = {
        'path': pathish(da), 'state': 'created' if created else 'updated_in_place', 'changes': changes,
        'values': {k: norm(v) for k, v in values.items()}, 'stats': stats_values, 'boss_phases': phases,
        'template_copied': {k: norm(v) for k, v in expected.items() if k in TEMPLATE_COPY}}
    if created or changes:
        track(section, da, created)
    try:
        REPORT['sections'][section]['definition']['dump'] = dict(u.HoverAuthoring.describe_object_properties(da))
    except Exception:
        pass
    return da


# ---------------------------------------------------------------------------------------------
# Sections.

def golem_section(section, ref):
    textures = import_textures(section)
    master = build_master(section, textures)
    instances = build_instances(section, master, textures)
    skel, mesh = build_mesh(section, instances)
    montages = {'_rows': GOLEM_MONTAGES}
    for name, clip, role, notifies in GOLEM_MONTAGES:
        seq = ensure_existing_class(VENDOR_CLIP + clip, u.AnimSequence)
        montages[name] = ensure_montage(section, GOLEM, name, seq, role, notifies, ref)
    blend_name, axis_max, rows = GOLEM_BLEND
    samples = [(ensure_existing_class(VENDOR_CLIP + c, u.AnimSequence), s, r) for c, s, r in rows]
    blend = ensure_blend(section, GOLEM, blend_name, skeleton_of(samples[0][0]), axis_max, samples,
                         load(ZESP_REF['blend']))
    author_definition(section, GOLEM, 'DA_StoneGolem', mesh, enum_value('HoverZombieRole', 'BOSS'),
                      enum_value('HoverSpecialKind', 'STONE_GOLEM'), GOLEM_STATS, GOLEM_FIELDS, montages, blend,
                      GOLEM_SPECIALS, [])


def kid_section(section, ref):
    mesh = ensure_existing_class(KID_MESH, u.SkeletalMesh)
    kid_skel = ensure_existing_class(KID_SKEL, u.Skeleton)
    compat = compatible_paths(kid_skel)
    REPORT['sections'][section]['kid_skeleton_compatible'] = compat
    REPORT['sections'][section]['kid_mesh_skeleton'] = pathish(skeleton_of(mesh))
    if FERAL_SKEL not in compat:
        REPORT['warnings'].append('SK_Kid_Skeleton does not list %s as compatible (ReviewKidFeral.py registration '
                                  'missing); the Giant Kid clips will not play until it is registered' % FERAL_SKEL)
    montages = {'_rows': KID_MONTAGES}
    for name, clip, role, notifies in KID_MONTAGES:
        seq = ensure_existing_class(FERAL + clip, u.AnimSequence)
        montages[name] = ensure_montage(section, GIANT, name, seq, role, notifies, ref)
    blend_name, axis_max, rows = KID_BLEND
    samples = [(ensure_existing_class(FERAL + c, u.AnimSequence), s, r) for c, s, r in rows]
    blend = ensure_blend(section, GIANT, blend_name, skeleton_of(samples[0][0]), axis_max, samples,
                         load(ZESP_REF['blend']))
    author_definition(section, KID, 'DA_GiantKid', mesh, enum_value('HoverZombieRole', 'BOSS'),
                      enum_value('HoverSpecialKind', 'GIANT_KID'), KID_STATS, KID_FIELDS, montages, blend,
                      KID_SPECIALS, KID_PHASES)


SECTION_ASSETS = {'golem': [], 'kid': []}


def main():
    global EA, AT, ML, AL
    EA = u.EditorAssetLibrary
    AT = u.AssetToolsHelpers.get_asset_tools()
    ML = u.MaterialEditingLibrary
    AL = u.AnimationLibrary
    owned = {s: owned_paths(s) for s in SECTIONS}
    reads = sorted(set(p for s in SECTIONS for p in read_paths(s)))
    REPORT['hashes_before'] = {p: sha(file_of(p)) for s in SECTIONS for p in owned[s]}
    REPORT['untouched_hashes_before'] = {p: sha(file_of(p)) for p in reads}
    missing = [p for p, h in REPORT['untouched_hashes_before'].items() if h is None]
    assert not missing, 'read-only sources missing on disk: %s' % missing
    ref = vendor_reference()
    REPORT['vendor_reference'] = ref

    for section in SECTIONS:
        REPORT['sections'][section] = {'ok': False, 'errors': []}
        mismatches_before = len(REPORT['readback_mismatches'])
        try:
            (golem_section if section == 'golem' else kid_section)(section, ref)
        except Exception:
            REPORT['sections'][section]['errors'].append(traceback.format_exc())
        mism = REPORT['readback_mismatches'][mismatches_before:]
        if mism:
            REPORT['sections'][section]['errors'].append('read-back mismatches: %s' % mism)
        if REPORT['sections'][section]['errors']:
            REPORT['errors'].extend('%s: %s' % (section, e) for e in REPORT['sections'][section]['errors'])
            REPORT['sections'][section]['saved'] = []
            continue
        saved = []
        seen = set()
        for asset in SECTION_ASSETS[section]:
            path = pathish(asset)
            if path in seen:
                continue
            seen.add(path)
            assert path in owned[section], 'refusing to save non-owned asset ' + path
            if EA.save_loaded_asset(asset, False):  # False = write even if not dirty
                saved.append(path)
            else:
                REPORT['errors'].append('%s: save_loaded_asset failed for %s' % (section, path))
        REPORT['sections'][section]['saved'] = saved
        REPORT['saved'].extend(saved)
        REPORT['sections'][section]['ok'] = not any(e.startswith(section + ':') for e in REPORT['errors'])

    REPORT['hashes_after'] = {p: sha(file_of(p)) for s in SECTIONS for p in owned[s]}
    REPORT['untouched_hashes_after'] = {p: sha(file_of(p)) for p in reads}
    REPORT['untouched_changed'] = [p for p, h in REPORT['untouched_hashes_before'].items()
                                   if REPORT['untouched_hashes_after'][p] != h]
    if REPORT['untouched_changed']:
        REPORT['errors'].append('read-only sources changed on disk: %s' % REPORT['untouched_changed'])
    REPORT['changed_files'] = [p for p in REPORT['hashes_after']
                               if REPORT['hashes_after'][p] != REPORT['hashes_before'].get(p)]
    REPORT['created'] = sorted(set(REPORT['created']))
    REPORT['modified'] = sorted(set(REPORT['modified']) - set(REPORT['created']))


def summary():
    sec = REPORT['sections']
    return ('NYC_BOSSES ok=%s golem=%s kid=%s saved=%d changed_files=%d created=%d modified=%d slots=%s lods=%s '
            'mismatches=%d warnings=%d errors=%d untouched_changed=%d receipt=%s' % (
                REPORT['ok'], sec.get('golem', {}).get('ok', 'skipped'), sec.get('kid', {}).get('ok', 'skipped'),
                len(REPORT['saved']), len(REPORT.get('changed_files', [])), len(REPORT['created']),
                len(REPORT['modified']), [r['slot'] for r in REPORT['slots'].get('after', [])],
                '%s->%s' % (REPORT['lods'].get('before'), REPORT['lods'].get('after')),
                len(REPORT['readback_mismatches']), len(REPORT['warnings']), len(REPORT['errors']),
                len(REPORT['untouched_changed']), RECEIPT))


def dry_run():
    plan = {'sections': SECTIONS, 'owned_assets': {s: owned_paths(s) for s in SECTIONS},
            'read_only': {s: read_paths(s) for s in SECTIONS},
            'textures': [(str(EXPORT / p), GOLEM + '/' + n, k) for p, n, k in TEXTURES],
            'golem': {'stats': GOLEM_STATS, 'fields': GOLEM_FIELDS, 'montages': GOLEM_MONTAGES, 'blend': GOLEM_BLEND,
                      'specials': GOLEM_SPECIALS},
            'kid': {'stats': KID_STATS, 'fields': KID_FIELDS, 'phases': KID_PHASES, 'montages': KID_MONTAGES,
                    'blend': KID_BLEND, 'specials': KID_SPECIALS},
            'flags': {'reimport': REIMPORT, 'flip_green': FLIP_GREEN, 'no_lods': NO_LODS},
            'python_names': {cpp: candidates(cpp) for cpp in list(GOLEM_STATS) + list(GOLEM_FIELDS) +
                             list(KID_FIELDS) + TEMPLATE_COPY},
            'pngs_present': {p: (EXPORT / p).is_file() for p, _, _ in TEXTURES},
            'left_default': LEFT_DEFAULT}
    print('NYC_BOSSES_PLAN', json.dumps(plan, default=str, indent=1), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    try:
        assert u, 'AuthorNYCBosses must run inside the Unreal Editor (use --dry-run elsewhere)'
        assert SECTIONS, 'unknown --only value %r (golem|kid)' % ONLY
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and all(REPORT['sections'].get(s, {}).get('ok') for s in SECTIONS)
        write_receipt()
        line = summary()
        print(line, flush=True)
        for w in REPORT['warnings']:
            print('NYC_BOSSES warning', w, flush=True)
        for e in REPORT['errors']:
            print('NYC_BOSSES error', e, flush=True)
        if u:
            u.log_warning(line)
            for w in REPORT['warnings']:
                u.log_warning('NYC_BOSSES warning ' + w)
            for e in REPORT['errors']:
                u.log_error('NYC_BOSSES error ' + e)
            u.SystemLibrary.quit_editor()


if DRY_RUN:
    dry_run()
else:
    run()
