"""Bind L_NYC_Survival's WorldSettings navigation_system_config to UHoverNYCNavigationSystem.

Run under the editor (NullRHI is fine) with -ExecutePythonScript. Steps:
  1. load L_NYC_Survival, point the instanced NavigationSystemModuleConfig at
     /Script/HoverFlight.HoverNYCNavigationSystem and read the class back;
  2. save through UHoverAuthoring::SaveSurvivalMap, then reload the map so the editor world
     recreates its navigation system from the new config (the 55 x 320 agent);
  3. rebuild the navmesh with the same calls as AuthorNYCSurvival.py build_navigation, check
     the live navigation system class, save again and write nav_receipt.json; quit the editor.

Flags (after the script path):
  --layout <json>   take nav_center / nav_size from a frozen layout file (as AuthorNYCSurvival.py)

Why the route: NavigationSystemModuleConfig is a UCLASS with no BlueprintType and no
Blueprint-visible members, so the Python plugin does not generate unreal.NavigationSystemModuleConfig.
AWorldSettings::NavigationSystemConfig is EditAnywhere + BlueprintReadOnly + Instanced, and a default
map already owns one config instance, so its NavigationSystemClass (FSoftClassPath, EditAnywhere) is
set in place through get/set_editor_property with the C++ property name. A missing config is created
with unreal.new_object(unreal.load_class(...)) instead of the absent Python type.

AuthorNYCSurvival.py cannot be imported for its helpers: it runs main() at import time and quits.
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
MAP_NAME = 'L_NYC_Survival'
RELOAD_VIA = '/Engine/Maps/Entry'
NAV_SYSTEM_PATH = '/Script/HoverFlight.HoverNYCNavigationSystem'
NAV_SYSTEM_NAME = 'HoverNYCNavigationSystem'
NAV_CONFIG_PATH = '/Script/NavigationSystem.NavigationSystemModuleConfig'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
SUBLEVELS = ('CityMeshes', 'SetDressing', 'Lighting_Main', 'Lighting_Main_Directional')
# Same values as AuthorNYCSurvival.py (Section 2.7).
NAV_CENTER = (270, 5100, 160)
NAV_SIZE = (2400, 5400, 1200)
NAV_PARAMS = {'tile_size_uu': 1000, 'cell_size': 19, 'agent_max_step_height': 50, 'tile_pool_size': 1024}
AGENT_WANT = {'radius': 55.0, 'height': 320.0}

parser = argparse.ArgumentParser(prog='BindNYCNav.py', add_help=False)
parser.add_argument('--layout', default=None)
ARGS, UNKNOWN = parser.parse_known_args(sys.argv[1:])

RECEIPT = {'map': MAP, 'want_nav_system': NAV_SYSTEM_PATH, 'errors': [], 'warnings': [], 'unknown_args': UNKNOWN,
           'bind': {}, 'live_nav_system': {}, 'nav': {}, 'saved_bind': False, 'saved_final': False,
           'time': time.strftime('%Y-%m-%d %H:%M:%S'),
           'claim': 'NullRHI authoring only; navigation config binding and navmesh rebake'}

LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
EA = u.EditorAssetLibrary


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


def nav_box():
    center, size = NAV_CENTER, NAV_SIZE
    if ARGS.layout:
        frozen = json.loads(Path(ARGS.layout).read_text())
        center, size = frozen.get('nav_center', center), frozen.get('nav_size', size)
    return vec(center), vec(size)


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
    """Point settings.navigation_system_config at UHoverNYCNavigationSystem; return the read-back path."""
    nav_cls = u.load_class(None, NAV_SYSTEM_PATH)
    assert nav_cls, '%s is not loaded (HoverFlight module not built?)' % NAV_SYSTEM_PATH
    cfg_cls = u.load_class(None, NAV_CONFIG_PATH)
    assert cfg_cls, '%s is not loaded' % NAV_CONFIG_PATH
    cfg = settings.get_editor_property('navigation_system_config')
    info['config_class_before'] = cfg.get_class().get_path_name() if cfg else None
    if cfg is None or not u.MathLibrary.class_is_child_of(cfg.get_class(), cfg_cls):
        # unreal.NavigationSystemModuleConfig does not exist; new_object takes the unreal.Class instead.
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


def live_nav_class(world):
    nav = u.NavigationSystemV1.get_navigation_system(world)
    return nav.get_class().get_name() if nav else None


def dirty_packages():
    names = []
    for getter in ('get_dirty_map_packages', 'get_dirty_content_packages'):
        fn = getattr(u.EditorLoadingAndSavingUtils, getter, None)
        if fn:
            names += [p.get_name() for p in fn()]
    return names


def load_map():
    assert LEVEL.load_level(MAP), 'Loading %s failed' % MAP
    world = EDITOR.get_editor_world()
    assert world and world.get_path_name().startswith(MAP + '.'), world.get_path_name() if world else None
    assert LEVEL.set_current_level_by_name(MAP_NAME), 'set_current_level_by_name failed'
    check_streaming(world)
    return world


def check_streaming(world):
    lines = [line for line in u.HoverAuthoring.describe_streaming_levels(world).splitlines() if line.strip()]
    for name in SUBLEVELS:
        row = next((line for line in lines if line.split(' ')[0].endswith('/' + name)), None)
        assert row, 'Missing streaming sublevel %s' % name
        assert 'class=LevelStreamingAlwaysLoaded' in row, row
        assert 'loaded=1' in row and 'dirty=0' in row, row


def recast_agent(recast):
    agent = {'name': recast.get_name()}
    for key, names in (('radius', ('agent_radius', 'AgentRadius')), ('height', ('agent_height', 'AgentHeight'))):
        try:
            agent[key] = float(get_prop(recast, names)[0])
        except Exception:
            agent[key] = None
    return agent


def build_navigation(world):
    """Same sequence as AuthorNYCSurvival.py build_navigation."""
    center, size = nav_box()
    assert u.HoverAuthoring.add_city_navigation(world, center, size, True), 'First navigation build refused'
    configured = u.HoverAuthoring.configure_city_nav_mesh(
        world, NAV_PARAMS['tile_size_uu'], NAV_PARAMS['cell_size'], NAV_PARAMS['agent_max_step_height'],
        NAV_PARAMS['tile_pool_size'])
    RECEIPT['nav']['configure'] = configured
    assert configured.startswith('Recast='), configured
    started = time.monotonic()
    assert u.HoverAuthoring.add_city_navigation(world, center, size, True), 'Navigation rebuild refused'
    RECEIPT['nav']['rebuild_seconds'] = time.monotonic() - started
    recasts = u.GameplayStatics.get_all_actors_of_class(world, u.RecastNavMesh)
    RECEIPT['nav']['recasts'] = [recast_agent(r) for r in recasts]
    assert len(recasts) == 1, 'Expected exactly one RecastNavMesh, got %d' % len(recasts)
    RECEIPT['nav']['describe'] = u.HoverAuthoring.describe_partition_navigation(world, False)
    RECEIPT['nav']['params'] = NAV_PARAMS
    agent = RECEIPT['nav']['recasts'][0]
    if agent['radius'] is None or agent['height'] is None:
        RECEIPT['warnings'].append('Could not read the RecastNavMesh agent size: %s' % agent)
    else:
        ok = abs(agent['radius'] - AGENT_WANT['radius']) < 0.5 and abs(agent['height'] - AGENT_WANT['height']) < 0.5
        RECEIPT['nav']['agent_ok'] = ok
        assert ok, 'RecastNavMesh agent %s, want %s' % (agent, AGENT_WANT)


def main():
    assert EA.does_asset_exist(MAP), '%s does not exist; run AuthorNYCSurvival.py first' % MAP
    world = load_map()
    RECEIPT['live_nav_system']['on_load'] = live_nav_class(world)
    bind_nyc_nav_config(world.get_world_settings(), RECEIPT['bind'])
    if RECEIPT['live_nav_system']['on_load'] != NAV_SYSTEM_NAME:
        # The editor world built its navigation system from the old config at load: save the binding,
        # then reload so the world recreates the system (and its agent) from the new config.
        assert u.HoverAuthoring.save_survival_map(world), 'save_survival_map refused the binding save'
        RECEIPT['saved_bind'] = True
        dirty = dirty_packages()
        assert not dirty, 'Refusing to reload with dirty packages: %s' % dirty
        if EA.does_asset_exist(RELOAD_VIA):
            assert LEVEL.load_level(RELOAD_VIA), 'Loading %s failed' % RELOAD_VIA
        world = load_map()
        RECEIPT['bind']['navigation_system_class_after_reload'] = soft_class_text(
            get_prop(world.get_world_settings().get_editor_property('navigation_system_config'),
                     ('navigation_system_class', 'NavigationSystemClass'))[0])
    RECEIPT['live_nav_system']['before_rebuild'] = live_nav_class(world)
    assert RECEIPT['live_nav_system']['before_rebuild'] == NAV_SYSTEM_NAME, \
        'Live navigation system is %s after reload, want %s' % (RECEIPT['live_nav_system']['before_rebuild'],
                                                                NAV_SYSTEM_NAME)
    build_navigation(world)
    RECEIPT['live_nav_system']['after_rebuild'] = live_nav_class(world)
    check_streaming(world)
    assert u.HoverAuthoring.save_survival_map(world), 'save_survival_map refused or failed'
    RECEIPT['saved_final'] = True


def run():
    try:
        main()
    except Exception:
        RECEIPT['errors'].append(traceback.format_exc())
    finally:
        RECEIPT['ok'] = not RECEIPT['errors'] and RECEIPT['saved_final']
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / 'nav_receipt.json').write_text(json.dumps(RECEIPT, indent=2, default=str))
        except Exception:
            print('NYC_NAV_BIND receipt failed', traceback.format_exc(), flush=True)
        print('NYC_NAV_BIND', RECEIPT['ok'], RECEIPT['errors'], flush=True)
        u.SystemLibrary.quit_editor()


run()
