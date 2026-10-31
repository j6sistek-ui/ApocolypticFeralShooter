"""Author the two data assets AHoverNYCSurvivalGameMode loads, then quit the editor.

  /Game/HoverPrototype/NYC/DA_NYCWaves       ZE_WaveGameModeSettings (vendor UPrimaryDataAsset)
  /Game/HoverPrototype/NYC/DA_NYCEncounters  HoverNYCEncounterSettings (HoverCyberVariants.h)

Paths and classes are the ones HoverNYCSurvival.cpp:17-18 / :96-97 load. Values come from
Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md: Section 1.2 round table (H(r), N(r)), Section 3
06.2-06.4 (DA_NYCWaves / DA_NYCEncounters tables), Section 6 framework fields, errata E1-E7.

Idempotent: an existing asset of the right class is updated in place, never deleted. Every
value is read back before anything is saved; on any mismatch nothing is saved. Only the two
NYC assets are saved; every referenced definition is hashed before/after to prove it is
untouched. Receipt: D:/AFS_Comparisons/NYCSurvival_<date>/data_receipt.json.

Run (never concurrently with another editor run):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorNYCData.py" -nullrhi -unattended
Flags (inside the quoted -ExecutePythonScript value, after the script path):
  --dry-run   print the planned rows and values; no asset is loaded, created or saved
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

PKG = '/Game/HoverPrototype/NYC'
WAVES_NAME = 'DA_NYCWaves'
ENCOUNTERS_NAME = 'DA_NYCEncounters'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
RECEIPT = OUT / 'data_receipt.json'
DRY_RUN = '--dry-run' in sys.argv[1:]

VARIANTS = '/Game/HoverPrototype/ZombieEngine/Variants'
NYC_ZOMBIES = PKG + '/Zombies'
# Each roster slot lists candidates in preference order: the NYC duplicate the design asks for
# (Section 3 06.3, E5) when it has been authored, otherwise the existing Cyber definition.
ROSTER = {
    'Standard01': [NYC_ZOMBIES + '/DA_NYC_Standard01', VARIANTS + '/Standard01/DA_Standard01'],
    'Standard02': [NYC_ZOMBIES + '/DA_NYC_Standard02', VARIANTS + '/Standard02/DA_Standard02'],
    'Standard03': [NYC_ZOMBIES + '/DA_NYC_Standard03', VARIANTS + '/Standard03/DA_Standard03'],
    'Standard04': [NYC_ZOMBIES + '/DA_NYC_Standard04', VARIANTS + '/Standard04/DA_Standard04'],
    'Brute': [NYC_ZOMBIES + '/DA_NYC_Brute', VARIANTS + '/Brute/DA_Brute'],
    'Kid': [NYC_ZOMBIES + '/DA_NYC_Kid', VARIANTS + '/Kid/DA_Kid'],
    # Bosses (E1/E3/E4): left None until authored; FindBossRound then yields no boss round.
    'StoneGolem': [VARIANTS + '/Golem/DA_StoneGolem'],
    'GiantKid': [VARIANTS + '/Kid/DA_GiantKid'],
    # Stage 2 heavy-round elite (E2): referenced only if it exists, and bAlphaBruteElite stays off.
    'AlphaBrute': [NYC_ZOMBIES + '/DA_NYC_AlphaBrute'],
}
STANDARD_SLOTS = ('Standard01', 'Standard02', 'Standard03', 'Standard04')
ZOMBIE_CLASS_BPS = [PKG + '/BP_NYCZombie', NYC_ZOMBIES + '/BP_NYCZombie']  # E7; native fallback
DEATH_WIDGET = '/Game/ZESP/ZE/UI/Main/WBP_ZE_DeathRespawn'
GRENADE_ITEM = '/Game/ZESP/ZE/Data/Weapons/DA_Grenade_Frag'
RESTART_LEVEL = '/Game/HoverPrototype/Maps/L_NYC_Survival'
# Read-only references hashed before/after (they must never change).
UNTOUCHED = ['/Game/HoverPrototype/ZombieEngine/DA_CyberWaves', VARIANTS + '/DA_CyberEncounters']

# ---------------------------------------------------------------------------------------------
# Section 1.2 round table (authoritative) and the formulas it must equal.
TABLE_HEALTH = [100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 370, 415, 460, 505, 550,
                640, 730, 820, 910, 1000, 1200, 1400, 1600, 1800, 2000, 2300, 2600, 2900, 3200, 3500]
TABLE_COUNT = [6, 8, 13, 18, 24, 27, 28, 28, 29, 33, 34, 36, 39, 41, 44,
               47, 50, 53, 56, 60, 63, 67, 71, 75, 80, 84, 89, 94, 99, 105]
INTERMISSION = 10.0
DAMAGE_BAND = ((10, 1.0), (30, 1.667))  # R1-10 30 dmg, R11-30 50 dmg on MeleeDamage 30


def health_formula(r):
    h = 100
    for n in range(2, r + 1):
        h += 25 if n <= 10 else 45 if n <= 15 else 90 if n <= 20 else 200 if n <= 25 else 300
    return min(h, 25000)


def count_formula(r):
    solo = [6, 8, 13, 18, 24, 27, 28, 28, 29]
    return solo[r - 1] if r <= 9 else 24 + (9 * r * r) // 100  # integer: R30 = 105


def damage_band(r):
    return next(m for last, m in DAMAGE_BAND if r <= last)


def build_rows():
    rows = []
    for r in range(1, 31):
        assert TABLE_HEALTH[r - 1] == health_formula(r), 'H(%d) table %d != formula %d' % (
            r, TABLE_HEALTH[r - 1], health_formula(r))
        assert TABLE_COUNT[r - 1] == count_formula(r), 'N(%d) table %d != formula %d' % (
            r, TABLE_COUNT[r - 1], count_formula(r))
        rows.append({'WaveNumber': r, 'BaseZombieCount': TABLE_COUNT[r - 1],
                     'HealthMultiplier': TABLE_HEALTH[r - 1] / 100.0, 'DamageMultiplier': damage_band(r),
                     'SpeedMultiplier': 1.0, 'WaveCompletionBonus': 0, 'CustomIntermissionTime': INTERMISSION})
    return rows


ROWS = build_rows()

# DA_NYCWaves scalar fields (Section 3 06.2/06.3 table, Section 6 framework fields).
WAVE_FIELDS = [
    ('FirstWaveDelay', 5.0), ('TimeBetweenWaves', 10.0), ('SpawnInterval', 2.0),
    ('MaxConcurrentZombies', 24), ('BaseZombieCount', 24),
    ('AutoHealthScalePerWave', 1.0), ('AutoDamageScalePerWave', 1.0),
    ('AutoSpeedScalePerWave', 1.0), ('AutoCountScalePerWave', 1.0),
    ('bUseCustomWaves', True), ('bDirectChaseMode', True), ('bTargetNearestPlayer', True),
    ('MaxWaves', 0), ('bEndOnAllPlayersDead', True),
    ('bShowWaveNumber', True), ('bShowZombiesRemaining', True), ('bShowCountdown', True),
    ('bShowDebugLogs', False),
]
# Starting kit (Section 6): ConfigureCityStartingGear(Settings, AmmoQuantity, GrenadeCount).
START_AMMO, START_GRENADES = 270, 2

# DA_NYCEncounters scalar fields (Section 3 06.4 table, Section 1.2 spine, E4/E5, header defaults
# where the design names the rule but not a new number). Object fields are filled at runtime.
ENCOUNTER_FIELDS = [
    # Inherited UHoverCyberEncounterSettings schedule.
    ('BruteFirstWave', 12), ('BruteInterval', 2),
    ('SwarmFirstWave', 5), ('SwarmInterval', 5),
    ('SwarmCount', 8),              # not read by the NYC mode (HordeBase/HordePerRound drive hordes)
    ('SwarmSpawnInterval', .65),    # not read by the NYC mode; mirrors HordeIntervalBase
    # Boss schedule.
    ('bAlphaBruteElite', False), ('BossTriggerFraction', .4),
    ('BossCycleFromRound', 33), ('BossCycleInterval', 6),
    # Pacing SI(r) = max(Floor, Base * Decay^(r-1)) and the credit pressures (06.6).
    ('SpawnIntervalBase', 2.0), ('SpawnIntervalFloor', .5), ('SpawnIntervalDecay', .95),
    ('HordeIntervalBase', .65), ('HordeIntervalFloor', .35),
    ('CatchUpBelowAlive', 8), ('CatchUpPressure', 2.0), ('IdlePressure', 1.5), ('IdleRadius', 2500.0),
    ('CrowdPressure', .5), ('CrowdCount', 4), ('CrowdRadius', 800.0),
    ('RateJitterMin', .85), ('RateJitterMax', 1.15),
    ('StallRelaxSeconds', 4.0), ('StallWarnSeconds', 12.0),
    ('MaxSpawnsPerTick', 1), ('ConcurrentSoftCap', 0),
    # Placement band and gates (06.6).
    ('NearMin', 1400.0), ('BandInner', 2000.0), ('BandOuter', 6000.0), ('FarMax', 10000.0),
    ('EdgeWeight', .3), ('OccludedWeight', .8), ('CooldownMin', 4.0), ('RecentCount', 3),
    ('PlayerClearance', 300.0), ('FreshZombieClearance', 150.0), ('JitterRadius', 250.0),
    # Stragglers, Stage 1 relocation (06.6, E8).
    ('FarDistance', 12000.0), ('FarMinAge', 8.0), ('NoPathSeconds', 20.0),
    ('HiddenDistance', 6000.0), ('HiddenSeconds', 20.0),
    # Endurance R31+ (Section 1.2: H(30) 3,500, +800 to R40, +1,000 after, cap 25,000; count 24 + 9r^2/100).
    ('EnduranceFromRound', 31), ('EnduranceBaseHP', 3500), ('HealthStepTo40', 800),
    ('HealthStepUntilRound', 40), ('HealthStep', 1000), ('HealthCapHP', 25000),
    ('CountBase', 24), ('CountQuadPercent', 9), ('DamageScaleLate', 2.5),
    # Horde K(r) = 10 + 2r, packs of 4.
    ('HordeBase', 10), ('HordePerRound', 2), ('HordePackSize', 4), ('HordeCountCap', 0),
    # Heavy rounds B(r) = min(4, 1 + (r - 8) / 6); R8 debut at 50%.
    ('BruteDebutWave', 8), ('BruteCountCap', 4), ('BruteCountDivisor', 6),
    ('BrutePlacement', [.25, .5, .75, .9]), ('LoneBrutePlacement', .5),
    ('KidBleedFromRound', 21),
    # Speed roll (06.5, E6).
    ('RollPerRound', 4), ('RollWindow', 35), ('WalkerMaxRoll', 35), ('RunnerMaxRoll', 70),
    ('WalkerSpeed', 180.0), ('RunnerSpeed', 400.0), ('SprinterSpeed', 600.0), ('KidSpeedTier', 700.0),
    ('ForcedSprintAfterRound', 3), ('ForcedSprintersAtEnd', 3),
]
# (Round, boss slots, SecondEntersAtFraction): E4 R13 golem, R19 Giant Kid, R27 both at .5.
BOSS_ROWS = [(13, ['StoneGolem'], 0.0), (19, ['GiantKid'], 0.0), (27, ['StoneGolem', 'GiantKid'], .5)]

# Design items with no field on either asset (reported, not authored).
UNMAPPED = [
    'Riot fields (RiotShareEarly/Late .15/.20, RiotFromRound 9, RiotLateRound 17, RiotMaxAlive 6): Stage 2, no UPROPERTY',
    'StragglerPromoteSeconds 10 / StragglerPromoteRange 2500 (straggler tier promotion): no UPROPERTY',
    'RoundStartSound / HeavyRoundSound (SC_Zombie_Roar) / BossRoar (SC_Entity_Roar) / EmergeMontage: no UPROPERTY',
    'Boss pressure "interval doubles while a boss lives": covered only by CrowdPressure .5 (Lower term), no own field',
    'Nuke next-spawn delay 3 s, guaranteed Max Ammo/Max Health drops, horde-clear Max Ammo: code/power-up rules, no field',
    'Kid half-band damage and 0.85 s cadence, Brute/boss MaxHealth multiples (6x/12x/15x): live on the zombie DAs',
    'DA_NYC_Standard01-04 / DA_NYC_Kid / DA_NYC_Brute duplicates (MeleeDamage 30/15/60): not authored here; used automatically once they exist',
    'Lakeside skins (Horror, BogZombie, Mythical, Plant, Pirate) as Standard round-robin skins (E9): not added to Standards',
    'SwarmCount ClampMax 24 -> 80: a code edit, not data (the NYC mode does not read SwarmCount)',
    'StartingEquipment DA_NYC_Ballista_0 / DA_NYC_AMMO_Ballista (design 2147): do not exist; the helper uses DA_AFS_Ballista + DA_AMMO_M16',
    'FHoverZombieTuning Count/Health/Speed/SpawnInterval = 1.0: runtime menu state, not on these assets',
]

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'errors': [], 'warnings': [], 'assets': {}, 'references': {},
          'hashes_before': {}, 'hashes_after': {}, 'untouched_hashes_before': {}, 'untouched_hashes_after': {},
          'python_names': {}, 'waves_fields': {}, 'waves_rows': ROWS, 'encounter_fields': {},
          'boss_rounds': [], 'readback_mismatches': [], 'unmapped_design_items': UNMAPPED, 'saved': [],
          'claim': 'Editor data authoring only; no gameplay run, no rendered evidence'}


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('NYC_DATA receipt failed', traceback.format_exc(), flush=True)


# ---------------------------------------------------------------------------------------------
# Python name resolution (UPROPERTY Foo -> foo, bFoo -> foo, EnduranceBaseHP -> endurance_base_hp).

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
    key = scope.split('[')[0] + '.' + cpp
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


def set_field(holder, cpp, value, scope):
    name = resolve(holder, cpp, scope)
    try:
        holder.set_editor_property(name, value)
        return name
    except Exception as first:
        try:
            setattr(holder, name, value)
            return name
        except Exception:
            raise RuntimeError('%s.%s (%s) could not be set: %s' % (scope, cpp, name, first))


def make_struct(cls, fields, scope):
    """Build a struct; per-field set, with a keyword-constructor fallback for protected fields."""
    s = cls()
    failed = {}
    for cpp, value in fields.items():
        try:
            set_field(s, cpp, value, scope)
        except Exception as exc:
            failed[cpp] = str(exc)
    if failed:
        try:
            s = cls(**{resolve(cls(), cpp, scope): value for cpp, value in fields.items()})
        except Exception:
            raise RuntimeError('%s fields could not be set: %s' % (scope, failed))
    return s


def norm(value):
    """Comparable form: objects/classes by path, names/enums by text, sequences element-wise."""
    if value is None:
        return None
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, 'get_path_name'):
        return value.get_path_name()
    if isinstance(value, (list, tuple)) or (u and isinstance(value, u.Array)):
        return [norm(v) for v in value]
    return str(value)


def check(holder, cpp, expected, scope):
    actual = norm(holder.get_editor_property(resolve(holder, cpp, scope)))
    want = norm(expected)
    if isinstance(want, float) and isinstance(actual, (int, float)):
        same = abs(actual - want) < 1e-3
    elif isinstance(want, list) and isinstance(actual, list) and len(want) == len(actual):
        same = all((abs(a - w) < 1e-3) if isinstance(w, float) else a == w for a, w in zip(actual, want))
    else:
        same = actual == want
    if not same:
        REPORT['readback_mismatches'].append({'field': scope + '.' + cpp, 'expected': want, 'actual': actual})
    return actual


# ---------------------------------------------------------------------------------------------

def file_of(asset_path):
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    return content / (asset_path[len('/Game/'):] + '.uasset')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def load_first(slot):
    for path in ROSTER[slot]:
        if EA.does_asset_exist(path):
            asset = EA.load_asset(path)
            if asset:
                REPORT['references'][slot] = {'path': asset.get_path_name(), 'class': asset.get_class().get_name()}
                return asset
    REPORT['references'][slot] = None
    return None


def ensure_asset(name, cls):
    path = PKG + '/' + name
    if EA.does_asset_exist(path):
        asset = EA.load_asset(path)
        assert asset and isinstance(asset, cls), '%s exists but is %s, not %s; refusing to touch it' % (
            path, asset.get_class().get_name() if asset else None, cls.__name__)
        state = 'updated_in_place'
    else:
        factory = u.DataAssetFactory()
        factory.set_editor_property('data_asset_class', cls.static_class())
        asset = u.AssetToolsHelpers.get_asset_tools().create_asset(name, PKG, cls.static_class(), factory)
        assert asset and isinstance(asset, cls), 'create_asset failed for %s' % path
        state = 'created'
    REPORT['assets'][name] = {'path': asset.get_path_name(), 'class': asset.get_class().get_name(), 'state': state}
    return asset


def author_waves(waves, standards):
    scope = 'ZE_WaveGameModeSettings'
    for cpp, value in WAVE_FIELDS:
        set_field(waves, cpp, value, scope)
        REPORT['waves_fields'][cpp] = value
    set_field(waves, 'DefaultZombieTypes', standards, scope)
    REPORT['waves_fields']['DefaultZombieTypes'] = norm(standards)

    zombie_class = None
    for bp in ZOMBIE_CLASS_BPS:
        if EA.does_asset_exist(bp):
            zombie_class = EA.load_blueprint_class(bp)
            break
    if not zombie_class:
        zombie_class = u.HoverNYCZombie.static_class()
        REPORT['warnings'].append('BP_NYCZombie not found; ZombieClass = native AHoverNYCZombie (the mode would '
                                  'substitute it at InitGame anyway)')
    set_field(waves, 'ZombieClass', zombie_class, scope)
    REPORT['waves_fields']['ZombieClass'] = norm(zombie_class)

    set_field(waves, 'RespawnPolicy', u.ZE_PlayerRespawnPolicy.RESTART_LEVEL, scope)
    set_field(waves, 'RestartLevelName', RESTART_LEVEL, scope)
    REPORT['waves_fields']['RespawnPolicy'] = 'RestartLevel'
    REPORT['waves_fields']['RestartLevelName'] = RESTART_LEVEL
    if EA.does_asset_exist(DEATH_WIDGET):
        widget = EA.load_blueprint_class(DEATH_WIDGET)
        set_field(waves, 'DeathWidgetClass', widget, scope)
        REPORT['waves_fields']['DeathWidgetClass'] = norm(widget)
    else:
        REPORT['warnings'].append('WBP_ZE_DeathRespawn missing; DeathWidgetClass left unchanged')
    # WaveHUDClass is assigned in memory by InitGame (UHoverCyberWaveHUD) and is never authored.

    rows = []
    for row in ROWS:
        fields = dict(row)
        fields['ZombieTypes'] = standards
        rows.append(make_struct(u.ZE_WaveConfig, fields, 'ZE_WaveConfig'))
    set_field(waves, 'CustomWaves', rows, scope)

    # Starting kit: Ballista slot 1, DA_AMMO_M16 x 270, 500 points, 2 grenades (owned-path helper).
    if u.HoverAuthoring.configure_city_starting_gear(waves, START_AMMO, START_GRENADES):
        REPORT['waves_fields']['StartingEquipment'] = {'helper': 'ConfigureCityStartingGear',
                                                       'AmmoQuantity': START_AMMO, 'GrenadeCount': START_GRENADES,
                                                       'StartingGold': 500}
    else:
        REPORT['warnings'].append('ConfigureCityStartingGear refused (DA_AFS_Ballista or DA_AMMO_M16 missing); '
                                  'StartingEquipment weapon/ammo not set')
    if EA.does_asset_exist(GRENADE_ITEM):
        frag = EA.load_asset(GRENADE_ITEM)
        gear = waves.get_editor_property(resolve(waves, 'StartingEquipment', scope))
        try:
            set_field(gear, 'GrenadeItem', frag, 'ZE_StartingEquipment')
            set_field(waves, 'StartingEquipment', gear, scope)
            REPORT['waves_fields']['StartingEquipment.GrenadeItem'] = norm(frag)
        except Exception:
            REPORT['warnings'].append('GrenadeItem not set: ' + traceback.format_exc(limit=1))


def verify_waves(waves, standards):
    scope = 'ZE_WaveGameModeSettings'
    for cpp, value in WAVE_FIELDS:
        check(waves, cpp, value, scope)
    check(waves, 'DefaultZombieTypes', standards, scope)
    check(waves, 'ZombieClass', REPORT['waves_fields']['ZombieClass'], scope)
    check(waves, 'RespawnPolicy', u.ZE_PlayerRespawnPolicy.RESTART_LEVEL, scope)
    check(waves, 'RestartLevelName', RESTART_LEVEL, scope)
    rows = waves.get_editor_property(resolve(waves, 'CustomWaves', scope))
    if len(rows) != len(ROWS):
        REPORT['readback_mismatches'].append({'field': 'CustomWaves', 'expected': len(ROWS), 'actual': len(rows)})
        return
    for got, row in zip(rows, ROWS):
        for cpp, value in row.items():
            check(got, cpp, value, 'ZE_WaveConfig[%d]' % row['WaveNumber'])
        check(got, 'ZombieTypes', standards, 'ZE_WaveConfig[%d]' % row['WaveNumber'])


def author_encounters(enc, refs, standards):
    scope = 'HoverNYCEncounterSettings'
    expected = {}
    cyber_standards = [d for d in standards if isinstance(d, u.HoverCyberZombieDefinition)]
    if len(cyber_standards) != len(standards):
        REPORT['warnings'].append('Standards: skipped definitions that are not HoverCyberZombieDefinition')
    expected['Standards'] = cyber_standards
    for slot in ('Brute', 'Kid', 'StoneGolem', 'GiantKid', 'AlphaBrute'):
        expected[slot] = refs[slot]
    for cpp, value in ENCOUNTER_FIELDS:
        expected[cpp] = value
    for cpp, value in expected.items():
        set_field(enc, cpp, value, scope)
        REPORT['encounter_fields'][cpp] = norm(value)

    boss_rows = []
    for rnd, slots, fraction in BOSS_ROWS:
        bosses = [refs[s] for s in slots if refs[s]]
        missing = [s for s in slots if not refs[s]]
        boss_rows.append(make_struct(u.HoverBossRound, {'Round': rnd, 'Bosses': bosses,
                                                         'SecondEntersAtFraction': fraction}, 'HoverBossRound'))
        REPORT['boss_rounds'].append({'Round': rnd, 'Bosses': norm(bosses), 'SecondEntersAtFraction': fraction,
                                      'missing': missing, 'active': bool(bosses)})
    set_field(enc, 'BossRounds', boss_rows, scope)
    return expected


def verify_encounters(enc, expected):
    scope = 'HoverNYCEncounterSettings'
    for cpp, value in expected.items():
        check(enc, cpp, value, scope)
    rows = enc.get_editor_property(resolve(enc, 'BossRounds', scope))
    if len(rows) != len(REPORT['boss_rounds']):
        REPORT['readback_mismatches'].append({'field': 'BossRounds', 'expected': len(REPORT['boss_rounds']),
                                              'actual': len(rows)})
        return
    for got, want in zip(rows, REPORT['boss_rounds']):
        for cpp in ('Round', 'Bosses', 'SecondEntersAtFraction'):
            check(got, cpp, want[cpp], 'HoverBossRound[%d]' % want['Round'])


def main():
    global EA
    EA = u.EditorAssetLibrary
    targets = {n: file_of(PKG + '/' + n) for n in (WAVES_NAME, ENCOUNTERS_NAME)}
    REPORT['hashes_before'] = {str(p): sha(p) for p in targets.values()}

    refs = {slot: load_first(slot) for slot in ROSTER}
    untouched = sorted(set(UNTOUCHED + [r['path'].split('.')[0] for r in REPORT['references'].values() if r]))
    REPORT['untouched_hashes_before'] = {str(file_of(p)): sha(file_of(p)) for p in untouched}

    standards = [refs[s] for s in STANDARD_SLOTS if refs[s]]
    assert standards, 'No Standard definition exists under %s; nothing authored' % VARIANTS
    for slot in ('Brute', 'Kid'):
        if not refs[slot]:
            REPORT['warnings'].append('%s definition missing; its rounds are disabled' % slot)
    for slot in ('StoneGolem', 'GiantKid'):
        if not refs[slot]:
            REPORT['warnings'].append('%s does not exist yet (%s); pointer left None, so its boss rounds play as '
                                      'Normal rounds until it is authored and this script is re-run'
                                      % (slot, ROSTER[slot][0]))
    roles = {}
    for slot, d in refs.items():
        if d:
            try:
                roles[slot] = str(d.get_editor_property('role'))
            except Exception:
                roles[slot] = 'n/a'
    REPORT['reference_roles'] = roles

    waves = ensure_asset(WAVES_NAME, u.ZE_WaveGameModeSettings)
    enc = ensure_asset(ENCOUNTERS_NAME, u.HoverNYCEncounterSettings)
    author_waves(waves, standards)
    expected = author_encounters(enc, refs, standards)
    verify_waves(waves, standards)
    verify_encounters(enc, expected)
    assert not REPORT['readback_mismatches'], 'Read-back mismatches; nothing saved: %s' % REPORT[
        'readback_mismatches']

    for asset in (waves, enc):
        assert EA.save_loaded_asset(asset, False), 'save_loaded_asset failed for ' + asset.get_path_name()
        REPORT['saved'].append(asset.get_path_name())
    REPORT['hashes_after'] = {str(p): sha(p) for p in targets.values()}
    for path, digest in REPORT['hashes_after'].items():
        assert digest, 'Saved file missing on disk: ' + path
    REPORT['untouched_hashes_after'] = {str(file_of(p)): sha(file_of(p)) for p in untouched}
    changed = [p for p, h in REPORT['untouched_hashes_before'].items() if REPORT['untouched_hashes_after'][p] != h]
    assert not changed, 'Referenced assets changed on disk: %s' % changed
    REPORT['references_unchanged'] = True
    try:
        REPORT['dump'] = {n: dict(u.HoverAuthoring.describe_object_properties(a))
                          for n, a in ((WAVES_NAME, waves), (ENCOUNTERS_NAME, enc))}
    except Exception:
        REPORT['warnings'].append('describe_object_properties dump failed: ' + traceback.format_exc(limit=1))


def summary():
    refs = REPORT['references']
    name = lambda slot: refs.get(slot)['path'].split('.')[-1] if refs.get(slot) else 'None'
    return ('NYC_DATA ok=%s waves=%s encounters=%s rows=%d standards=%s brute=%s kid=%s stoneGolem=%s giantKid=%s '
            'alphaBrute=%s bossRounds=%s mismatches=%d warnings=%d errors=%d receipt=%s' % (
                REPORT['ok'], REPORT['assets'].get(WAVES_NAME, {}).get('state'),
                REPORT['assets'].get(ENCOUNTERS_NAME, {}).get('state'), len(ROWS),
                ','.join(name(s) for s in STANDARD_SLOTS), name('Brute'), name('Kid'), name('StoneGolem'),
                name('GiantKid'), name('AlphaBrute'),
                ','.join('%d:%s' % (b['Round'], 'on' if b['active'] else 'off') for b in REPORT['boss_rounds']),
                len(REPORT['readback_mismatches']), len(REPORT['warnings']), len(REPORT['errors']), RECEIPT))


def dry_run():
    plan = {'package': PKG, 'assets': [WAVES_NAME, ENCOUNTERS_NAME], 'roster_candidates': ROSTER,
            'wave_fields': WAVE_FIELDS, 'rows': ROWS, 'encounter_fields': ENCOUNTER_FIELDS, 'boss_rows': BOSS_ROWS,
            'python_names': {cpp: candidates(cpp) for cpp, _ in WAVE_FIELDS + ENCOUNTER_FIELDS}}
    print('NYC_DATA_PLAN', json.dumps(plan, default=str), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    try:
        assert u, 'AuthorNYCData must run inside the Unreal Editor (use --dry-run elsewhere)'
        main()
    except Exception:
        # Nothing is saved after an error before the save step; the new assets stay unsaved in memory.
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and len(REPORT['saved']) == 2
        write_receipt()
        line = summary()
        print(line, flush=True)
        for w in REPORT['warnings']:
            print('NYC_DATA warning', w, flush=True)
        for e in REPORT['errors']:
            print('NYC_DATA error', e, flush=True)
        if u:
            u.log_warning(line)
            for w in REPORT['warnings']:
                u.log_warning('NYC_DATA warning ' + w)
            for e in REPORT['errors']:
                u.log_error('NYC_DATA error ' + e)
            u.SystemLibrary.quit_editor()


EA = None
if DRY_RUN:
    dry_run()
else:
    run()
