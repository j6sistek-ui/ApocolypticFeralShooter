"""Author L_NYC_Survival under NullRHI: map copy, navmesh, zones, spawners and start.

Editor-only authoring with no rendered-quality claim. Every layout row is a
placeholder until the survey freezes Scripts/nyc_survival_layout.json.

Flags (after the script path on -ExecutePythonScript):
  --nav-only            stop after the navmesh build, then save
  --dry-run             validate the table and print the plan; no asset is touched
  --layout <json>       override the embedded table with a frozen layout file
  --game-mode <class>   default /Script/HoverFlight.HoverNYCSurvivalGameMode

Never saves vendor sublevels: the only save is UHoverAuthoring::SaveSurvivalMap.
"""
import argparse
import json
import math
import sys
import time
import traceback
from pathlib import Path

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
SRC = '/Game/HoverPrototype/Maps/L_NYC_Explore'
MAP_NAME = 'L_NYC_Survival'
ACTOR_PREFIX = MAP + '.' + MAP_NAME + ':PersistentLevel.'
DEFAULT_GAME_MODE = '/Script/HoverFlight.HoverNYCSurvivalGameMode'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
SUBLEVELS = ('CityMeshes', 'SetDressing', 'Lighting_Main', 'Lighting_Main_Directional')

# Section 2.7: full dimensions, covering x -930..1470, y 2400..7800, z -440..760.
NAV_CENTER = (270, 5100, 160)
NAV_SIZE = (2400, 5400, 1200)
NAV_PARAMS = {'tile_size_uu': 1000, 'cell_size': 19, 'agent_max_step_height': 50, 'tile_pool_size': 1024}
PS_LOC = (271, 5241, 162)
PS_YAW = -90
TRUCK_START = (200, 5900)
TRUCK_CLEARANCE = 300
ZONE_Z = 160
ZONE_HEIGHT = 10000
SPAWN_Z = 160

# Section 8.1. The Garage->Plaza jump pad is one-way and is not an edge.
EDGES = [
    ('Plaza', 'SouthAve'),
    ('Plaza', 'NorthAve'),
    ('SouthAve', 'Underpass'),
    ('NorthAve', 'Shelter'),
    ('NorthAve', 'Uptown'),
    ('NorthAve', 'Garage'),
]
# Metadata only: doors are not authored in this slice.
DOORS = [
    {'id': 'D1', 'cost': 750, 'zones': ['Plaza', 'SouthAve']},
    {'id': 'D2', 'cost': 1000, 'zones': ['Plaza', 'NorthAve']},
    {'id': 'D3', 'cost': 1250, 'zones': ['NorthAve', 'Shelter']},
    {'id': 'D4', 'cost': 1500, 'zones': ['SouthAve', 'Underpass']},
    {'id': 'D5', 'cost': 1750, 'zones': ['NorthAve', 'Uptown']},
    {'id': 'D6', 'cost': 2000, 'zones': ['NorthAve', 'Garage']},
]
# (order, id, display, centre xy, size xy); z centre ZONE_Z, height ZONE_HEIGHT.
ZONES = [
    (0, 'Plaza', 'Checkpoint Plaza', (275, 5250), (350, 900)),
    (1, 'SouthAve', 'South Avenue', (275, 4200), (350, 1200)),
    (2, 'NorthAve', 'North Avenue', (275, 6150), (350, 900)),
    (3, 'Shelter', 'Survivor Shelter', (850, 6150), (500, 500)),
    (4, 'Underpass', 'Underpass', (275, 3300), (350, 600)),
    (5, 'Uptown', 'Uptown Barricade', (275, 6900), (350, 600)),
    (6, 'Garage', 'Garage Block', (-150, 5950), (500, 500)),
]
# (zone tag, x, y, yaw, extra spawn tags, zone the point stands in).
SPAWNERS = [
    ('Plaza', 140, 4840, 90, [], 'Plaza'),
    ('Plaza', 410, 4840, 90, [], 'Plaza'),
    ('Plaza', 140, 5660, -90, [], 'Plaza'),
    ('Plaza', 410, 5660, -90, [], 'Plaza'),
    ('SouthAve', 130, 4650, 90, [], 'SouthAve'),
    ('SouthAve', 420, 4350, 90, [], 'SouthAve'),
    ('SouthAve', 130, 4050, 90, [], 'SouthAve'),
    ('SouthAve', 420, 3850, 90, [], 'SouthAve'),
    ('Underpass', 160, 3680, -90, [], 'SouthAve'),
    ('Underpass', 400, 3680, -90, [], 'SouthAve'),
    ('Underpass', 270, 3350, 90, [], 'Underpass'),
    ('NorthAve', 130, 6200, -90, [], 'NorthAve'),
    ('NorthAve', 420, 6350, -90, [], 'NorthAve'),
    ('NorthAve', 130, 6560, -90, [], 'NorthAve'),
    ('NorthAve', 420, 6560, -90, [], 'NorthAve'),
    ('Shelter', 950, 6250, 180, [], 'Shelter'),
    ('Shelter', 440, 5980, 0, [], 'NorthAve'),
    ('Shelter', 440, 6180, 0, [], 'NorthAve'),
    ('Uptown', 130, 6750, -90, [], 'Uptown'),
    ('Uptown', 420, 6850, -90, [], 'Uptown'),
    ('Uptown', 150, 7120, -90, ['Boss'], 'Uptown'),
    ('Uptown', 400, 7120, -90, ['Boss'], 'Uptown'),
    ('Garage', -320, 5780, 0, [], 'Garage'),
    ('Garage', -320, 6120, 0, [], 'Garage'),
    ('Garage', -150, 6150, 0, [], 'Garage'),
]
EXPECTED_ZONES = 7
EXPECTED_SPAWNERS = 25
MIN_PER_ZONE = 3


def parse_args(argv):
    parser = argparse.ArgumentParser(prog='AuthorNYCSurvival.py', add_help=False)
    parser.add_argument('--nav-only', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--layout', default=None)
    parser.add_argument('--game-mode', default=DEFAULT_GAME_MODE)
    args, unknown = parser.parse_known_args(argv)
    return args, unknown


def build_table(layout_path):
    """Return the layout table; a frozen JSON file replaces the embedded rows key by key."""
    table = {
        'source': 'embedded',
        'nav_center': list(NAV_CENTER), 'nav_size': list(NAV_SIZE),
        'player_start': {'location': list(PS_LOC), 'yaw': PS_YAW, 'placeholder': True},
        'edges': [list(e) for e in EDGES], 'doors': DOORS,
        'zones': [{'order': o, 'id': i, 'display': d, 'center': [c[0], c[1], ZONE_Z],
                   'size': [s[0], s[1], ZONE_HEIGHT], 'placeholder': True}
                  for o, i, d, c, s in ZONES],
        'spawners': [],
    }
    counts = {}
    for zone, x, y, yaw, extra, stands in SPAWNERS:
        counts[zone] = counts.get(zone, 0) + 1
        table['spawners'].append({'zone': zone, 'location': [x, y, SPAWN_Z], 'yaw': yaw, 'extra_tags': list(extra),
                                  'stands': stands, 'label': 'AFS NYC Spawn %s %02d' % (zone, counts[zone]),
                                  'placeholder': True})
    if layout_path:
        frozen = json.loads(Path(layout_path).read_text())
        for key in ('nav_center', 'nav_size', 'player_start', 'edges', 'doors', 'zones', 'spawners'):
            if key in frozen:
                table[key] = frozen[key]
        table['source'] = str(layout_path)
    return table


def inside_2d(point, zone):
    cx, cy = zone['center'][0], zone['center'][1]
    hx, hy = zone['size'][0] / 2.0, zone['size'][1] / 2.0
    return abs(point[0] - cx) <= hx and abs(point[1] - cy) <= hy


def validate_table(table):
    """Return (errors, warnings). Errors block authoring; warnings go to the dump."""
    errors, warnings = [], []
    zones = {z['id']: z for z in table['zones']}
    if len(table['zones']) != EXPECTED_ZONES or len(zones) != EXPECTED_ZONES:
        errors.append('expected %d unique zones, got %d' % (EXPECTED_ZONES, len(table['zones'])))
    orders = sorted(z['order'] for z in table['zones'])
    if orders != list(range(len(table['zones']))):
        errors.append('zone orders are not 0..n-1: %s' % orders)
    adjacency = {z: set() for z in zones}
    for edge in table['edges']:
        a, b = edge
        if a not in zones or b not in zones or a == b:
            errors.append('bad edge %s' % (edge,))
            continue
        adjacency[a].add(b)
        adjacency[b].add(a)
    for a, near in adjacency.items():
        for b in near:
            if a not in adjacency.get(b, set()):
                errors.append('asymmetric edge %s-%s' % (a, b))
    if len(table['spawners']) != EXPECTED_SPAWNERS:
        errors.append('expected %d spawners, got %d' % (EXPECTED_SPAWNERS, len(table['spawners'])))
    labels = [s['label'] for s in table['spawners']]
    if len(set(labels)) != len(labels):
        errors.append('duplicate spawner labels')
    served = {z: 0 for z in zones}
    nav_c, nav_s = table['nav_center'], table['nav_size']
    nav_box = {'center': nav_c, 'size': nav_s}
    for s in table['spawners']:
        zone, stands, loc = s['zone'], s.get('stands', s['zone']), s['location']
        if zone not in zones:
            errors.append('%s: unknown zone %s' % (s['label'], zone))
            continue
        served[zone] += 1
        if stands not in zones:
            errors.append('%s: unknown standing zone %s' % (s['label'], stands))
        elif stands != zone and stands not in adjacency[zone]:
            errors.append('%s: stands in %s, not %s or a neighbour' % (s['label'], stands, zone))
        elif not inside_2d(loc, zones[stands]):
            errors.append('%s: %s is outside zone %s' % (s['label'], loc, stands))
        if not inside_2d(loc, nav_box) or abs(loc[2] - nav_c[2]) > nav_s[2] / 2.0:
            errors.append('%s: outside nav bounds' % s['label'])
        truck = math.dist(loc[:2], TRUCK_START)
        if truck < TRUCK_CLEARANCE:
            warnings.append('%s: %.0f cm from AFS_TruckStart' % (s['label'], truck))
    for zone, count in served.items():
        if count < MIN_PER_ZONE:
            errors.append('zone %s served by %d spawners (< %d)' % (zone, count, MIN_PER_ZONE))
    ps = table['player_start']['location']
    if not inside_2d(ps, nav_box):
        errors.append('player start outside nav bounds')
    return errors, warnings


ARGS, UNKNOWN = parse_args(sys.argv[1:])
TABLE = build_table(ARGS.layout)
TABLE_ERRORS, TABLE_WARNINGS = validate_table(TABLE)
REPORT = {'errors': [], 'warnings': list(TABLE_WARNINGS), 'flags': vars(ARGS), 'unknown_args': UNKNOWN,
          'map': MAP, 'source_map': SRC, 'creation': None, 'streaming': [], 'game_mode': None,
          'nav_agent': None, 'nav': {}, 'actors': {}, 'table': TABLE, 'saved': False,
          'claim': 'NullRHI authoring only; no rendered-quality claim; every row is a placeholder'}


def write_dump():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'layout_dump.json').write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('NYC_AUTHOR dump failed', traceback.format_exc(), flush=True)


try:
    import unreal as u
except ImportError:  # the dry run also works outside the editor
    u = None


def dry_run():
    plan = {'map': MAP, 'nav_center': TABLE['nav_center'], 'nav_size': TABLE['nav_size'],
            'nav_params': NAV_PARAMS, 'game_mode': ARGS.game_mode, 'zones': len(TABLE['zones']),
            'spawners': len(TABLE['spawners']), 'errors': TABLE_ERRORS, 'warnings': TABLE_WARNINGS}
    print('NYC_AUTHOR_PLAN', json.dumps(plan), flush=True)
    print('NYC_AUTHOR', not TABLE_ERRORS, TABLE_ERRORS, flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


def editor_world():
    world = EDITOR.get_editor_world()
    assert world, 'No editor world'
    return world


def dirty_packages():
    names = []
    for getter in ('get_dirty_map_packages', 'get_dirty_content_packages'):
        fn = getattr(u.EditorLoadingAndSavingUtils, getter, None)
        if fn:
            names += [p.get_name() for p in fn()]
    return names


def ensure_map():
    """Create MAP from L_NYC_Explore once; never overwrite an existing MAP."""
    if EA.does_asset_exist(MAP):
        REPORT['creation'] = 'existing'
        return
    copy = EA.duplicate_asset(SRC, MAP)
    if copy is not None:
        # LoadMap needs the package on disk, so the pure copy is written before any edit.
        assert EA.save_asset(MAP, False), 'Saving the duplicated map failed'
        REPORT['creation'] = 'duplicate_asset'
        return
    assert LEVEL.load_level(SRC), 'Loading %s failed' % SRC
    dirty = dirty_packages()
    assert not dirty, 'Refusing save_map with dirty packages: %s' % dirty
    assert not EA.does_asset_exist(MAP), 'MAP appeared during fallback'
    assert u.EditorLoadingAndSavingUtils.save_map(editor_world(), MAP), 'save_map fallback failed'
    REPORT['creation'] = 'load_level+save_map'


def check_streaming(world):
    text = u.HoverAuthoring.describe_streaming_levels(world)
    lines = [line for line in text.splitlines() if line.strip()]
    REPORT['streaming'] = lines
    for name in SUBLEVELS:
        row = next((line for line in lines if line.split(' ')[0].endswith('/' + name)), None)
        assert row, 'Missing streaming sublevel %s' % name
        assert 'class=LevelStreamingAlwaysLoaded' in row, row
        assert 'loaded=1' in row and 'dirty=0' in row, row


NAV_SYSTEM_PATH = '/Script/HoverFlight.HoverNYCNavigationSystem'
NAV_SYSTEM_NAME = 'HoverNYCNavigationSystem'
NAV_CONFIG_PATH = '/Script/NavigationSystem.NavigationSystemModuleConfig'


def soft_class_text(value):
    if value is None:
        return None
    try:
        return u.SystemLibrary.break_soft_class_path(value)
    except Exception:
        pass
    try:
        return value.export_text()
    except Exception:
        return str(value)


def get_prop(obj, names):
    """get_editor_property by Python name, then by C++ name (needed on classes Python does not wrap)."""
    last = None
    for name in names:
        try:
            return obj.get_editor_property(name), name
        except Exception as exc:
            last = exc
    raise last


def set_prop(obj, names, value):
    last = None
    for name in names:
        try:
            obj.set_editor_property(name, value)
            return name
        except Exception as exc:
            last = exc
    raise last


def soft_class_values(path):
    """Candidate values for an FSoftClassPath property; 5.8 Python has no make_soft_class_path."""
    vals = []
    for ctor in (lambda: u.SoftClassPath(path), lambda: u.SoftClassPath(asset_path_name=path), lambda: u.load_class(None, path)):
        try:
            v = ctor()
            if v is not None:
                vals.append(v)
        except Exception:
            pass
    return vals


def set_prop_any(obj, names, values):
    last = None
    for value in values:
        try:
            return set_prop(obj, names, value)
        except Exception as exc:
            last = exc
    raise last


def bind_nyc_nav_config(settings, info):
    """Point settings.navigation_system_config at UHoverNYCNavigationSystem (same route as BindNYCNav.py).

    unreal.NavigationSystemModuleConfig is not generated (no BlueprintType, no Blueprint-visible members),
    so the map's existing config instance is edited by C++ property name, and a missing one is created
    from unreal.load_class instead of the absent Python type.
    """
    nav_cls = u.load_class(None, NAV_SYSTEM_PATH)
    assert nav_cls, '%s is not loaded (HoverFlight module not built?)' % NAV_SYSTEM_PATH
    cfg_cls = u.load_class(None, NAV_CONFIG_PATH)
    assert cfg_cls, '%s is not loaded' % NAV_CONFIG_PATH
    cfg = settings.get_editor_property('navigation_system_config')
    info['config_class_before'] = cfg.get_class().get_path_name() if cfg else None
    if cfg is None or not u.MathLibrary.class_is_child_of(cfg.get_class(), cfg_cls):
        cfg = u.new_object(cfg_cls, settings)
        settings.set_editor_property('navigation_system_config', cfg)
        info['config_created'] = True
    else:
        info['config_created'] = False
    names = ('navigation_system_class', 'NavigationSystemClass')
    before, _ = get_prop(cfg, names)
    info['navigation_system_class_before'] = soft_class_text(before)
    if info['navigation_system_class_before'] != NAV_SYSTEM_PATH:
        try:
            settings.modify()
            cfg.modify()
        except Exception:
            info.setdefault('notes', []).append('modify() unavailable: ' + traceback.format_exc())
        info['set_property_name'] = set_prop_any(cfg, names, soft_class_values(NAV_SYSTEM_PATH))
    after_cfg = settings.get_editor_property('navigation_system_config')
    after, read_name = get_prop(after_cfg, names)
    info['config_class_after'] = after_cfg.get_class().get_path_name() if after_cfg else None
    info['navigation_system_class_after'] = soft_class_text(after)
    info['read_property_name'] = read_name
    assert info['navigation_system_class_after'] == NAV_SYSTEM_PATH, \
        'navigation_system_class read back as %s' % info['navigation_system_class_after']
    return info['navigation_system_class_after']


def set_game_mode(world):
    cls = u.load_class(None, ARGS.game_mode)
    assert cls, 'Game mode class %s is missing; nothing saved' % ARGS.game_mode
    settings = world.get_world_settings()
    settings.set_editor_property('default_game_mode', cls)
    current = settings.get_editor_property('default_game_mode')
    assert current and current.get_path_name() == cls.get_path_name(), 'GameMode override did not stick'
    REPORT['game_mode'] = cls.get_path_name()
    try:
        cdo = u.get_default_object(cls)
        REPORT['game_mode_is_cyber_adapter'] = isinstance(cdo, u.HoverCyberCityGameMode)
    except Exception:
        REPORT['warnings'].append('Could not inspect the game-mode CDO: ' + traceback.format_exc())
    if u.load_class(None, NAV_SYSTEM_PATH):
        try:
            REPORT['nav_bind'] = {}
            bind_nyc_nav_config(settings, REPORT['nav_bind'])
            live = u.NavigationSystemV1.get_navigation_system(world)
            live = live.get_class().get_name() if live else None
            REPORT['nav_bind']['live_nav_system'] = live
            if live == NAV_SYSTEM_NAME:
                REPORT['nav_agent'] = NAV_SYSTEM_NAME
            else:
                # The editor world made its navigation system at load, before this binding: this run's
                # bake uses the old agent. The saved map is bound; BindNYCNav.py reloads and rebakes.
                REPORT['nav_agent'] = 'BOUND_PENDING_RELOAD'
                REPORT['warnings'].append('navigation_system_config bound but live system is %s; '
                                          'run Scripts/BindNYCNav.py to reload and rebake' % live)
        except Exception:
            REPORT['warnings'].append('navigation_system_config failed: ' + traceback.format_exc())
            REPORT['nav_agent'] = 'DEFAULT_PLACEHOLDER'
    else:
        # The 55 x 320 agent class has not landed: this bake is invalid for Brutes and must be redone.
        REPORT['nav_agent'] = 'DEFAULT_PLACEHOLDER'


def build_navigation(world):
    center, size = vec(TABLE['nav_center']), vec(TABLE['nav_size'])
    assert u.HoverAuthoring.add_city_navigation(world, center, size, True), 'First navigation build refused'
    configured = u.HoverAuthoring.configure_city_nav_mesh(
        world, NAV_PARAMS['tile_size_uu'], NAV_PARAMS['cell_size'], NAV_PARAMS['agent_max_step_height'],
        NAV_PARAMS['tile_pool_size'])
    REPORT['nav']['configure'] = configured
    assert configured.startswith('Recast='), configured
    started = time.monotonic()
    assert u.HoverAuthoring.add_city_navigation(world, center, size, True), 'Navigation rebuild refused'
    REPORT['nav']['rebuild_seconds'] = time.monotonic() - started
    recasts = u.GameplayStatics.get_all_actors_of_class(world, u.RecastNavMesh)
    REPORT['nav']['recast_count'] = len(recasts)
    assert len(recasts) == 1, 'Expected exactly one RecastNavMesh, got %d' % len(recasts)
    REPORT['nav']['describe'] = u.HoverAuthoring.describe_partition_navigation(world, False)
    REPORT['nav']['params'] = NAV_PARAMS


def check_owned(actor, label):
    assert actor, '%s was not authored' % label
    path = actor.get_path_name()
    assert path.startswith(ACTOR_PREFIX), '%s landed outside the persistent level: %s' % (label, path)
    REPORT['actors'][label] = {'path': path, 'properties': dict(u.HoverAuthoring.describe_object_properties(actor))}


def author_player_start(world):
    ps = TABLE['player_start']
    transform = u.Transform(location=vec(ps['location']), rotation=u.Rotator(yaw=float(ps['yaw'])))
    actor = u.HoverAuthoring.add_survival_actor(world, u.PlayerStart, transform, 'AFS Survival Start',
                                                ['AFS_SurvivalStart'])
    check_owned(actor, 'AFS Survival Start')


def author_zones(world):
    for zone in TABLE['zones']:
        actor = u.HoverAuthoring.add_zone_volume(world, zone['id'], int(zone['order']), vec(zone['center']),
                                                 vec(zone['size']))
        check_owned(actor, 'AFS Zone ' + zone['id'])


def author_spawners(world):
    for row in TABLE['spawners']:
        tags = ['AFS_NYCSpawn'] + (['AFS_NYCSpawn_Placeholder'] if row.get('placeholder', True) else [])
        transform = u.Transform(location=vec(row['location']), rotation=u.Rotator(yaw=float(row['yaw'])))
        actor = u.HoverAuthoring.add_survival_actor(world, u.ZE_ZombieSpawnPoint, transform, row['label'], tags)
        assert actor, '%s was not authored' % row['label']
        actor.set_editor_property('spawn_tags', [row['zone']] + list(row.get('extra_tags', [])))
        actor.set_editor_property('is_enabled', True)
        written = [str(t) for t in actor.get_editor_property('spawn_tags')]
        assert written[:1] == [row['zone']], '%s spawn_tags=%s' % (row['label'], written)
        check_owned(actor, row['label'])


def main():
    global LEVEL, EDITOR, EA
    assert u, 'AuthorNYCSurvival must run inside the Unreal Editor (use --dry-run elsewhere)'
    LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
    EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    EA = u.EditorAssetLibrary
    assert not TABLE_ERRORS, 'Layout table invalid: %s' % TABLE_ERRORS
    ensure_map()
    assert LEVEL.load_level(MAP), 'Loading %s failed' % MAP
    world = editor_world()
    assert world.get_path_name().startswith(MAP + '.'), world.get_path_name()
    assert LEVEL.set_current_level_by_name(MAP_NAME), 'set_current_level_by_name failed'
    check_streaming(world)
    set_game_mode(world)
    build_navigation(world)
    if not ARGS.nav_only:
        author_player_start(world)
        author_zones(world)
        author_spawners(world)
    check_streaming(world)
    assert u.HoverAuthoring.save_survival_map(world), 'save_survival_map refused or failed'
    REPORT['saved'] = True


def run():
    try:
        main()
    except Exception:
        # Nothing is saved after an error: save_survival_map is the last step of main().
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and REPORT['saved']
        write_dump()
        print('NYC_AUTHOR', REPORT['ok'], REPORT['errors'], flush=True)
        if u:
            u.SystemLibrary.quit_editor()


LEVEL = EDITOR = EA = None
if ARGS.dry_run:
    dry_run()
else:
    run()
