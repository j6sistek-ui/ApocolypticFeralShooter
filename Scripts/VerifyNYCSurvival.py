"""CPU-only round/spawn regression; no rendered-quality claim.

Runs five waves of L_NYC_Survival in PIE (NullRHI is fine: no frame capture) and
records where zombies come from, whether they arrive, stalls and stragglers.
Vexa is held above half health with ZE_SurvivalComponent.set_health, so
player-damage behaviour is NOT tested by this run. Zone-pool conformance is
informational until the Section 8.2 adapter hooks land. Afterwards the zombie-free
L_NYC_Explore is checked statically (loaded read-only, never saved).
"""
import json
import math
import statistics
import time
import traceback
from pathlib import Path
import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
EXPLORE = '/Game/HoverPrototype/Maps/L_NYC_Explore'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d')) / 'spawns'
OUT.mkdir(parents=True, exist_ok=True)
ROUNDS = 5
TIMEOUT = 1500
BAND_NYC = (800, 6000)  # provisional, Section 8.3
BAND_CYBER = (1400, 10000)  # HoverCyberCity.cpp spawn band
MODES = ('HoverNYCSurvivalGameMode', 'BP_NYCSurvival_C')
NAV_SYSTEM = 'HoverNYCNavigationSystem'
EXPECT = {'spawners': 25, 'zones': 7, 'starts': 1, 'recast': 1}
PROBES = ['Plaza', 'SouthAve', 'NorthAve', 'Uptown', 'Plaza']
EDGES = [
    ('Plaza', 'SouthAve'),
    ('Plaza', 'NorthAve'),
    ('SouthAve', 'Underpass'),
    ('NorthAve', 'Shelter'),
    ('NorthAve', 'Uptown'),
    ('NorthAve', 'Garage'),
]
NEIGHBOURS = {}
for _a, _b in EDGES:
    NEIGHBOURS.setdefault(_a, set()).add(_b)
    NEIGHBOURS.setdefault(_b, set()).add(_a)
ARRIVE_DIST = 400
MAX_AGE = 45
STRAGGLER_OUTSIDE_S = 20
STRAGGLER_FAR = 6000
STRAGGLER_FAR_S = 20
STRAGGLER_SLOW_SPEED = 10
STRAGGLER_SLOW_S = 10
STALL_STAGES = (4, 8, 12)
KILL_DAMAGE = 99999

REPORT = {'errors': [], 'checks': {}, 'setup': {}, 'spawners': [], 'zones': [], 'rounds': [], 'spawns': [],
          'stragglers': [], 'stalls': [], 'kills': [], 'heals': 0, 'notes': [],
          'claim': 'CPU-only; no rendered-quality claim; player-damage behaviour not tested (health held)'}
STATE = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'setup': False, 'pc': None,
         'probed': 0, 'active': None, 'zombies': {}, 'stall_start': None, 'static_done': False}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
assert LEVEL.load_level(MAP)


def save():
    (OUT / 'runtime.json').write_text(json.dumps(REPORT, indent=2, default=str))


def dist2d(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def in_band(d, band):
    return band[0] <= d <= band[1]


def wave_state(gm):
    """Normalise EZE_WaveState to e.g. 'WAVEINPROGRESS' regardless of the Python enum spelling."""
    state = gm.get_wave_state()
    name = getattr(state, 'name', None) or str(state)
    return name.split('.')[-1].replace('_', '').upper()


def health_of(actor):
    s = actor.get_component_by_class(u.ZE_SurvivalComponent)
    return s.get_health() if s else None


def zone_of(point):
    """Highest-order zone whose 2D box contains the point, or None."""
    best = None
    for z in REPORT['zones']:
        if abs(point.x - z['center'][0]) <= z['extent'][0] and abs(point.y - z['center'][1]) <= z['extent'][1]:
            if best is None or z['order'] > best['order']:
                best = z
    return best['id'] if best else None


def zone_tag(actor):
    order, ident = -1, None
    for tag in [str(t) for t in actor.tags]:
        if tag.startswith('AFS_ZoneOrder_'):
            order = int(tag[len('AFS_ZoneOrder_'):])
        elif tag != 'AFS_NYCZone':
            ident = tag
    return ident, order


def setup(w, pc):
    gm = u.GameplayStatics.get_game_mode(w)
    mode = gm.get_class().get_name()
    REPORT['setup']['mode'] = mode
    REPORT['setup']['world'] = w.get_name()
    if mode not in MODES or not isinstance(gm, u.HoverCyberCityGameMode):
        raise RuntimeError('Wrong game mode %s (want one of %s on HoverCyberCityGameMode)' % (mode, MODES))
    actors = u.GameplayStatics.get_all_actors_of_class(w, u.Actor)
    spawners = sorted([a for a in actors if a.actor_has_tag('AFS_NYCSpawn')], key=lambda a: a.get_name())
    zones = [a for a in actors if a.actor_has_tag('AFS_NYCZone')]
    starts = [a for a in actors if a.actor_has_tag('AFS_SurvivalStart')]
    recasts = u.GameplayStatics.get_all_actors_of_class(w, u.RecastNavMesh)
    counts = {'spawners': len(spawners), 'zones': len(zones), 'starts': len(starts), 'recast': len(recasts)}
    REPORT['setup']['counts'] = counts
    # Section 2 section 10: the per-map agent (55 x 320) and UHoverNYCCrowdManager come from the WorldSettings
    # navigation_system_config. A default system means the bake is the 190 cm agent and invalid for Brutes.
    nav_class = None
    try:
        nav = u.NavigationSystemV1.get_navigation_system(w)
        nav_class = nav.get_class().get_name() if nav else None
    except Exception:
        REPORT['notes'].append('Navigation system lookup failed: ' + traceback.format_exc())
    REPORT['setup']['nav_system'] = nav_class
    REPORT['checks']['nav_system_class'] = nav_class == NAV_SYSTEM
    if nav_class != NAV_SYSTEM:
        REPORT['errors'].append('Navigation system is %s, want %s (re-run AuthorNYCSurvival.py)' % (nav_class, NAV_SYSTEM))
    for key, want in EXPECT.items():
        ok = counts[key] == want
        REPORT['checks']['count_' + key] = ok
        if not ok:
            REPORT['errors'].append('Expected %d %s, found %d' % (want, key, counts[key]))
    for z in zones:
        origin, extent = z.get_actor_bounds(False)
        ident, order = zone_tag(z)
        REPORT['zones'].append({'id': ident, 'order': order, 'center': list(origin.to_tuple()),
                                'extent': list(extent.to_tuple())})
    p = pc.get_controlled_pawn()
    start = starts[0].get_actor_location() if starts else p.get_actor_location()
    STATE['start_loc'] = start
    STATE['spawner_actors'] = spawners
    for a in spawners:
        loc = a.get_actor_location()
        tags = [str(t) for t in a.get_editor_property('spawn_tags')]
        path = u.HoverAuthoring.find_complete_city_path(w, loc, start)
        length = sum((path[i + 1] - path[i]).length() for i in range(len(path) - 1))
        REPORT['spawners'].append({'name': a.get_name(), 'label': a.get_actor_label() if hasattr(a, 'get_actor_label')
                                   else a.get_name(), 'zone': tags[0] if tags else None, 'spawn_tags': tags,
                                   'enabled': a.get_editor_property('is_enabled'),
                                   'placeholder': a.actor_has_tag('AFS_NYCSpawn_Placeholder'),
                                   'location': list(loc.to_tuple()), 'path_valid': len(path) > 1,
                                   'path_length': length, 'dist2d_to_start': dist2d(loc, start), 'used': 0})
    REPORT['setup']['player'] = {'pawn': p.get_class().get_name(), 'location': list(p.get_actor_location().to_tuple()),
                                 'bike': pc.get_test_bike() is not None if hasattr(pc, 'get_test_bike') else None,
                                 'truck': pc.get_test_truck() is not None if hasattr(pc, 'get_test_truck') else None}
    # Recorded, not failed, until the controller slice lands (bike spawn, truck mount).
    if REPORT['setup']['player']['bike']:
        REPORT['notes'].append('Bike spawned in NYC Survival (controller slice pending)')
    REPORT['setup']['last_chosen_hook'] = hasattr(gm, 'get_last_chosen_spawner')
    save()


def keep_alive(p):
    s = p.get_component_by_class(u.ZE_SurvivalComponent)
    if not s:
        if not STATE.get('no_survival'):
            STATE['no_survival'] = True
            REPORT['notes'].append('Pawn has no ZE_SurvivalComponent; health not held')
        return
    if s.get_health() < 0.5 * s.get_max_health():
        s.set_health(s.get_max_health())
        REPORT['heals'] += 1


def probe(p, r):
    name = PROBES[r - 1]
    zone = next((z for z in REPORT['zones'] if z['id'] == name), None)
    if not zone:
        REPORT['notes'].append('Round %d probe zone %s missing; Vexa not moved' % (r, name))
        return None
    loc = u.Vector(zone['center'][0], zone['center'][1], p.get_actor_location().z + 20)
    p.set_actor_location(loc, False, True)
    p.character_movement.stop_movement_immediately()
    return name


def nearest_spawner(loc):
    best, best_d = None, None
    for i, a in enumerate(STATE['spawner_actors']):
        d = dist2d(a.get_actor_location(), loc)
        if best_d is None or d < best_d:
            best, best_d = i, d
    return best


def record_spawn(w, gm, pc, p, z, t):
    loc = z.get_actor_location()
    player = p.get_actor_location()
    d = dist2d(loc, player)
    index = None
    chosen = None
    if hasattr(gm, 'get_last_chosen_spawner'):
        chosen = gm.get_last_chosen_spawner()
        if chosen:
            names = [a.get_name() for a in STATE['spawner_actors']]
            index = names.index(chosen.get_name()) if chosen.get_name() in names else None
    method = 'hook' if index is not None else 'nearest'
    if index is None:
        index = nearest_spawner(loc)
    spawner = REPORT['spawners'][index] if index is not None else None
    if spawner:
        spawner['used'] += 1
    s_zone = spawner['zone'] if spawner else None
    p_zone = zone_of(player)
    in_pool = bool(s_zone and p_zone and (s_zone == p_zone or s_zone in NEIGHBOURS.get(p_zone, set())))
    active = STATE['active']
    row = {'round': active['round'] if active else None, 't': t, 'name': z.get_name(),
           'location': list(loc.to_tuple()), 'dist2d_to_player': d, 'in_band_nyc': in_band(d, BAND_NYC),
           'in_band_cyber': in_band(d, BAND_CYBER), 'spawner': spawner['name'] if spawner else None,
           'spawner_method': method, 'spawner_zone': s_zone, 'player_zone': p_zone, 'in_pool': in_pool}
    REPORT['spawns'].append(row)
    if active:
        active['spawns'].append(row)
    STATE['zombies'][z.get_name()] = {'actor': z, 'first': t, 'last_loc': loc, 'outside_since': None,
                                      'far_since': None, 'slow_since': None, 'dead': False}
    save()


def kill(pc, p, name, info, reason, t, extra=None):
    info['dead'] = True
    row = {'round': STATE['active']['round'] if STATE['active'] else None, 'name': name, 'reason': reason,
           't': t, 'age': t - info['first'], 'location': list(info['actor'].get_actor_location().to_tuple())}
    if extra:
        row.update(extra)
    REPORT['kills'].append(row)
    if STATE['active']:
        STATE['active']['kills'].append(row)
    u.GameplayStatics.apply_damage(info['actor'], KILL_DAMAGE, pc, p, u.DamageType)
    save()


def straggler(pc, p, name, info, reason, since, t):
    row = {'round': STATE['active']['round'] if STATE['active'] else None, 'name': name, 'reason': reason,
           'duration': t - since, 'location': list(info['actor'].get_actor_location().to_tuple())}
    REPORT['stragglers'].append(row)
    if STATE['active']:
        STATE['active']['stragglers'].append(row)
    kill(pc, p, name, info, 'straggler_' + reason, t)


def track_zombies(w, gm, pc, p, t):
    present = {z.get_name(): z for z in u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie)}
    for name, z in present.items():
        if name not in STATE['zombies']:
            record_spawn(w, gm, pc, p, z, t)
    alive = 0
    player = p.get_actor_location()
    for name, info in STATE['zombies'].items():
        if info['dead']:
            continue
        z = present.get(name)
        if z is None:
            info['dead'] = True
            continue
        hp = health_of(z)
        if hp is not None and hp <= 0:
            info['dead'] = True
            continue
        alive += 1
        loc = z.get_actor_location()
        d = dist2d(loc, player)
        age = t - info['first']
        if d < ARRIVE_DIST:
            kill(pc, p, name, info, 'arrived', t, {'time_to_arrive': age})
            continue
        if age > MAX_AGE:
            kill(pc, p, name, info, 'timeout', t)
            continue
        if REPORT['zones'] and zone_of(loc) is None:
            info['outside_since'] = info['outside_since'] if info['outside_since'] is not None else t
            if t - info['outside_since'] >= STRAGGLER_OUTSIDE_S:
                straggler(pc, p, name, info, 'outside_zones', info['outside_since'], t)
                continue
        else:
            info['outside_since'] = None
        if d > STRAGGLER_FAR:
            info['far_since'] = info['far_since'] if info['far_since'] is not None else t
            if t - info['far_since'] >= STRAGGLER_FAR_S:
                straggler(pc, p, name, info, 'far_from_player', info['far_since'], t)
                continue
        else:
            info['far_since'] = None
        if z.get_velocity().length() < STRAGGLER_SLOW_SPEED:
            info['slow_since'] = info['slow_since'] if info['slow_since'] is not None else t
            if t - info['slow_since'] >= STRAGGLER_SLOW_S:
                straggler(pc, p, name, info, 'stuck', info['slow_since'], t)
                continue
        else:
            info['slow_since'] = None
    return alive


def close_stall(t):
    since = STATE['stall_start']
    STATE['stall_start'] = None
    if since is None:
        return
    length = t - since
    if length < STALL_STAGES[0]:
        return
    stage = max(s for s in STALL_STAGES if length >= s)
    row = {'round': STATE['active']['round'] if STATE['active'] else None, 'start': since, 'length': length,
           'stage': stage}
    REPORT['stalls'].append(row)
    if STATE['active']:
        STATE['active']['stalls'].append(row)
    save()


def open_round(gm, t, probe_zone):
    r = len(REPORT['rounds']) + 1
    STATE['active'] = {'round': r, 'wave': gm.get_current_wave(), 'start': t, 'probe': probe_zone,
                       'zombies_at_start': gm.get_zombies_remaining(), 'spawns': [], 'kills': [],
                       'stragglers': [], 'stalls': []}
    REPORT['notes'].append('Round %d started at %.1f (wave %d)' % (r, t, STATE['active']['wave']))
    save()


def close_round(gm, t):
    close_stall(t)
    a = STATE['active']
    STATE['active'] = None
    dists = [s['dist2d_to_player'] for s in a['spawns']]
    n = len(a['spawns'])

    def rate(key):
        return sum(1 for s in a['spawns'] if s[key]) / n if n else None

    reasons = {}
    for k in a['kills']:
        reasons[k['reason']] = reasons.get(k['reason'], 0) + 1
    arrive = [k['time_to_arrive'] for k in a['kills'] if 'time_to_arrive' in k]
    REPORT['rounds'].append({
        'round': a['round'], 'wave': a['wave'], 'probe': a['probe'], 'zombies_at_start': a['zombies_at_start'],
        'spawned': n, 'time_to_clear': t - a['start'],
        'dist_min': min(dists) if dists else None, 'dist_median': statistics.median(dists) if dists else None,
        'dist_max': max(dists) if dists else None, 'band_nyc_rate': rate('in_band_nyc'),
        'band_cyber_rate': rate('in_band_cyber'), 'pool_rate_informational': rate('in_pool'),
        'kills_by_reason': reasons, 'median_time_to_arrive': statistics.median(arrive) if arrive else None,
        'stalls': a['stalls'], 'max_stall': max((s['length'] for s in a['stalls']), default=0),
        'stragglers': a['stragglers'], 'end_state': wave_state(gm), 'end_wave': gm.get_current_wave()})
    save()


def step_rounds(w, gm, pc, p, t):
    state = wave_state(gm)
    if state == 'GAMEOVER':
        raise RuntimeError('Game over during round %d despite the health hold' % (len(REPORT['rounds']) + 1))
    r = len(REPORT['rounds']) + 1
    if STATE['active'] is None:
        if state in ('WAITINGTOSTART', 'WAVECOMPLETED') and STATE['probed'] < r:
            STATE['probe_zone'] = probe(p, r)
            STATE['probed'] = r
        if state == 'WAVEINPROGRESS':
            open_round(gm, t, STATE.get('probe_zone') if STATE['probed'] == r else None)
    if STATE['active'] is None:
        return
    alive = track_zombies(w, gm, pc, p, t)
    a = STATE['active']
    if gm.get_current_wave() != a['wave'] or state in ('WAVECOMPLETED', 'WON'):
        close_round(gm, t)
        return
    stalled = state == 'WAVEINPROGRESS' and alive < gm.get_zombies_remaining() and gm.get_active_spawn_count() == 0
    if stalled and STATE['stall_start'] is None:
        STATE['stall_start'] = t
    elif not stalled and STATE['stall_start'] is not None:
        close_stall(t)


def finish():
    if STATE['end']:
        return
    t = None
    w = u.HoverAuthoring.get_playtest_world()
    if w:
        t = u.GameplayStatics.get_time_seconds(w)
        if STATE['active'] and STATE['stall_start'] is not None:
            close_stall(t)
    REPORT['spawner_usage'] = {s['name']: s['used'] for s in REPORT['spawners']}
    REPORT['never_used'] = [s['name'] for s in REPORT['spawners'] if not s['used']]
    REPORT['unreachable'] = [s['name'] for s in REPORT['spawners'] if not s['path_valid']]
    REPORT['stalls_over_12s'] = sum(1 for s in REPORT['stalls'] if s['length'] >= 12)
    REPORT['completed'] = (not REPORT['errors'] and len(REPORT['rounds']) == ROUNDS and
                           REPORT['stalls_over_12s'] == 0)
    save()
    print('NYC_SURVIVAL', REPORT['completed'], REPORT['errors'], flush=True)
    LEVEL.editor_request_end_play()
    STATE['end'] = time.monotonic()


def static_exploration_check():
    """L_NYC_Explore must stay zombie-free: no navmesh, spawners or zones. Read-only, never saved."""
    try:
        assert LEVEL.load_level(EXPLORE), 'Loading %s failed' % EXPLORE
        world = EDITOR.get_editor_world()
        actors = u.GameplayStatics.get_all_actors_of_class(world, u.Actor)
        row = {'recast': len(u.GameplayStatics.get_all_actors_of_class(world, u.RecastNavMesh)),
               'spawners': sum(1 for a in actors if a.actor_has_tag('AFS_NYCSpawn')),
               'zones': sum(1 for a in actors if a.actor_has_tag('AFS_NYCZone'))}
        REPORT['exploration_static'] = row
        assert row == {'recast': 0, 'spawners': 0, 'zones': 0}, row
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    REPORT['completed'] = REPORT.get('completed', False) and not REPORT['errors']
    save()
    print('NYC_SURVIVAL_FINAL', REPORT['completed'], REPORT['errors'], flush=True)


def tick(dt):
    if STATE['busy']:
        return
    STATE['busy'] = True
    try:
        if STATE['end']:
            if time.monotonic() - STATE['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                if not STATE['static_done']:
                    STATE['static_done'] = True
                    static_exploration_check()
                u.unregister_slate_post_tick_callback(STATE['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - STATE['start'] > TIMEOUT:
            raise RuntimeError('NYC survival timeout after %d rounds' % len(REPORT['rounds']))
        if not STATE['play']:
            if time.monotonic() - STATE['start'] > 5:
                u.HoverAuthoring.start_playtest()
                STATE['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        if STATE['pc'] != pc:
            STATE['pc'] = pc
            u.HoverAuthoring.isolate_test_input(pc)
        p = pc.get_controlled_pawn()
        t = u.GameplayStatics.get_time_seconds(w)
        if not STATE['setup']:
            STATE['setup'] = True
            setup(w, pc)
        # The game-mode tick stays enabled: the waves have to run.
        gm = u.GameplayStatics.get_game_mode(w)
        keep_alive(p)
        step_rounds(w, gm, pc, p, t)
        if len(REPORT['rounds']) >= ROUNDS:
            finish()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
        finish()
    finally:
        STATE['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
STATE['handle'] = u.register_slate_post_tick_callback(tick)
