"""ProveWeather.py - rendered proof of the weather in L_NYC_Survival (GPU, -RenderOffscreen, PIE). Re-runnable.

  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" M:/UnrealProjects/AFS/AFS.uproject
      -unattended -RenderOffscreen -nosplash -ResX=1280 -ResY=720 -stdout -FullStdOutLogOutput
      -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveWeather.py
  then: python M:/UnrealProjects/AFS/Scripts/MakeWeatherVideo.py <root> [<video/sheet out>]

Same harness as Scripts/CapturePerkMachines.py / ProveWalking.py (PIE at a fixed 1/30 s step, camera actor,
HoverAuthoring.capture_world_frame, which returns the PREVIOUS frame, so every shot is taken >= 0.2 s after its view
was set). r.Streaming.FullyLoadUsedTextures 1 before shooting (Docs/LESSONS.md). Zombies keep spawning and walking
(they are part of the proof); any that reaches 7 m of Vexa is removed so she is never attacked during the shots.

Sequence: Clear (untouched map) -> F6 menu row to Rain (real key path: F6, Up = last row = Weather, Right x2,
Enter) recorded through the blend -> rain stills -> a blood decal on Vexa and on a zombie in the rain (fix round 1,
finding D: other decals must still land on characters while the wet layer shows) -> moving camera in the rain
(Vexa runs with scripted W + L3, then the camera sweeps 360 deg, then both; drops in view counted every frame) ->
Storm (exec "Weather Storm", waits for a BP_Thunder strike) -> menu to Snow (Right x1) recorded through the blend ->
snow stills + blood on Vexa in the snow -> moving camera in the snow -> Cloudy (exec) -> Clear (exec "Weather Clear
0") and a menu open + cancel. fx.MaxCPUParticlesPerEmitter is read before, during and after (finding C).
Video frames are taken at 15 fps of game time (every second step); a capture costs 0.5-3 s of wall time
(viewport read-back + PNG), so the whole run takes ~25-40 min.
Views: 'player' = Vexa's own third-person camera, 'street' = a raised camera down the avenue, 'close' = low at
Vexa's feet (wet ground / snow cover), 'blood' = 1.5 m in front of a character's chest.

WEATHER_PERF=1: cost only, with the player MOVING (Vexa runs a circle: W + L3 held, camera yaw 40 deg/s, reset to the
same start every window): Clear / Rain / Clear / Snow / Clear / Storm, twice; 4 s settle + 4 s window each; per
window mean / p95 real frame, game thread, render thread, RHI thread and GPU frame ("stat unit" numbers through
HoverAuthoring.get_thread_times_ms) and live particles, one profilegpu per window into the log -> perf.json.
WEATHER_MOVE=1: only the moving-camera tests (rain, snow) with stills, no video -> move.json. With WEATHER_LEGACY=1
the actor is set back to the pre-fix placement (snow 5 m / far 26 m ahead, no velocity lead) to measure the old behaviour (the
particle assets are whatever ImportWeather.py last built).
WEATHER_SET='{"max_splashes_per_second": 0}': AHoverWeather properties set at the start (A/B cost tests).
WEATHER_QUICK=1: the stills without video frames.
WEATHER_BASELINE=1: before ImportWeather.py placed the actor (or for a reference run): shoots only the Clear stills
(clear_player / clear_street at the same moments) into <out>/baseline/.
Out: <root>/{stills,frames,baseline}/ + prove.json / perf.json / move.json; root D:/AFS_Comparisons/Weather_20261101
(WEATHER_OUT overrides it; the fix round 1 receipts are in its fix1/ subfolder).
"""
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
ROOT = Path(os.environ.get('WEATHER_OUT', 'D:/AFS_Comparisons/Weather_20261101'))
BASELINE = os.environ.get('WEATHER_BASELINE') == '1'
QUICK = os.environ.get('WEATHER_QUICK') == '1'   # stills only: no video frames
PERF = os.environ.get('WEATHER_PERF') == '1'     # cost only: alternating Clear / Rain / Snow windows, player moving
MOVE = os.environ.get('WEATHER_MOVE') == '1'     # moving-camera tests only
LEGACY = os.environ.get('WEATHER_LEGACY') == '1'  # pre-fix placement of the volumes (for the before numbers)
STILLS = ROOT / ('baseline' if BASELINE else 'stills')
FRAMES = ROOT / 'frames'
for d in (STILLS, FRAMES):
    d.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
THUNDER = '/Game/MultiplayerDynamicWeatherSystem/Blueprints/BP_Thunder.BP_Thunder_C'
BLOOD = '/Game/Blood_VFX_Pack/Materials/MI_BloodDecal'
SPRINT = 'Gamepad_LeftThumbstick'   # hold L3 = run (HUD: "Hold L3 run")
CAP = 'fx.MaxCPUParticlesPerEmitter'
# Raised street camera: the avenue runs along Y through the plaza at x ~275 (zones Plaza 5250, SouthAve 4200).
STREET_EYE, STREET_AT = (520.0, 6650.0, 700.0), (230.0, 4300.0, 120.0)
OUT_JSON = 'baseline.json' if BASELINE else 'perf.json' if PERF else 'move.json' if MOVE else 'prove.json'
R = {'ok': True, 'errors': [], 'frames': {}, 'capture_s': {}, 'stills': [], 'states': [], 'perf': {}, 'menu': [], 'thunder': [],
     'move': {}, 'blood': [], 'cap': [], 'removed_zombies': 0, 'baseline': BASELINE, 'legacy': LEGACY,
     'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'rec': None, 'rec_n': 0, 'rec_skip': 0,
     'perf': None, 'last_real': None, 'wx': None, 'view': 'player', 'watch_thunder': None, 'hold': set(),
     'yaw_rate': 0.0, 'msample': None, 'spawn': None, 'focus': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def log(*a):
    print('PROVE_WEATHER', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def V(t):
    return u.Vector(t[0], t[1], t[2])


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd, S['pc'])
    except Exception as e:  # noqa: BLE001
        R['errors'].append('%s: %s' % (cmd, e))


def cap(tag):
    try:
        v = u.SystemLibrary.get_console_variable_int_value(CAP)
    except Exception as e:  # noqa: BLE001
        v = 'n/a: %s' % e
    R['cap'].append({'tag': tag, CAP: v})
    log('cap', tag, v)


def key(name):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0, False)
    u.HoverAuthoring.test_key(S['pc'], name, 0.0, False)


def hold(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def release_all():
    for k in list(S['hold']):
        hold(k, False)
    S['yaw_rate'] = 0.0


def reset_vexa(t=None):
    """Back to the spawn transform, standing, camera behind her (moving tests start from the same place)."""
    release_all()
    p = pawn()
    loc, yaw = S['spawn']
    p.set_actor_location_and_rotation(loc, u.Rotator(roll=0, pitch=0, yaw=yaw), False, True)
    S['pc'].set_control_rotation(u.Rotator(roll=0.0, pitch=-10.0, yaw=yaw))
    try:
        p.get_movement_component().stop_movement_immediately()
        lm = p.get_editor_property('life_movement')
        if lm:
            lm.set_hl_velocity(V((0, 0, 0)))
    except Exception as e:  # noqa: BLE001
        R['errors'].append('reset: %s' % str(e)[:160])


def state(tag):
    wx = S['wx']
    row = {'tag': tag, 't': round(u.GameplayStatics.get_time_seconds(world()), 2)}
    if wx:
        row['state'] = wx.describe_state()
        row['weather'] = str(wx.get_weather())
        row['particles'] = wx.get_live_particle_count()
    R['states'].append(row)
    log('state', json.dumps(row))
    return row


def look(eye, at, fov=70):
    rot = u.MathLibrary.find_look_at_rotation(V(eye), V(at))
    S['cam'].set_actor_location_and_rotation(V(eye), rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


def view(name):
    S['view'] = name
    p = pawn()
    if name == 'player':
        S['pc'].set_view_target_with_blend(p, 0)
        return
    if name == 'street':
        look(STREET_EYE, STREET_AT)
    elif name == 'blood':  # 1.5 m in front of the focus character's chest
        a = S['focus'] or p
        l = a.get_actor_location()
        f = a.get_actor_forward_vector()
        chest = (l.x, l.y, l.z + 35)
        look((chest[0] + f.x * 150 + f.y * 25, chest[1] + f.y * 150 - f.x * 25, chest[2] + 20), chest, 55)
    else:  # close: low, beside Vexa, looking past her feet along the ground
        l = p.get_actor_location()
        f = p.get_actor_forward_vector()
        look((l.x - f.x * 260 + f.y * 140, l.y - f.y * 260 - f.x * 140, l.z - 30),
             (l.x + f.x * 300, l.y + f.y * 300, l.z - 95))


def capture(name):
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    R['stills'].append(fn.name)
    log('still', fn.name)


def step(delay, fn):
    S['queue'].append((delay, fn))


def shot(view_name, name, settle=0.6):
    step(0.05, lambda t: view(view_name))
    step(settle, lambda t: capture(name))


def rec(name, seconds, view_name):
    step(0.05, lambda t: view(view_name))
    if QUICK:
        step(min(seconds, 6.5), lambda t: None)   # keep the blends' game time, skip the frames
        return
    step(0.2, lambda t: S.update(rec=name, rec_n=0, rec_skip=1))
    step(seconds, lambda t: S.update(rec=None))


def end_perf():
    p = S['perf']
    S['perf'] = None
    if not p or not p['dts']:
        return

    def stats(xs):
        d = sorted(xs)
        return round(sum(d) / len(d), 2), round(d[max(0, int(len(d) * .95) - 1)], 2)

    row = {'frames': len(p['dts'])}
    row['frame_mean_ms'], row['frame_p95_ms'] = stats([1000 * x for x in p['dts']])
    for i, k in enumerate(('game', 'render', 'rhi', 'gpu')):
        row[k + '_mean_ms'], row[k + '_p95_ms'] = stats([tt[i] for tt in p['tt']] or [0])
    row['particles_max'] = max(p['particles']) if p['particles'] else 0
    row['particles_mean'] = round(sum(p['particles']) / len(p['particles'])) if p['particles'] else 0
    row['speed_mean'] = round(sum(p['speed']) / len(p['speed'])) if p['speed'] else 0
    R['perf'][p['name']] = row
    log('perf', p['name'], json.dumps(row))


def menu_to(steps_right, tag):
    """The F6 row path in one game-time instant (the menu pauses the game): F6, Up (row 0 -> last row, Weather),
    Right x N, Enter. Records the weather before / after and whether the menu closed."""
    def f(t):
        before = str(S['wx'].get_weather())
        key('F6')
        opened = S['pc'].is_graphics_menu_open()
        key('Up')
        for _ in range(steps_right):
            key('Right')
        key('Enter')
        row = {'tag': tag, 'before': before, 'opened': opened, 'closed': not S['pc'].is_graphics_menu_open(),
               'after': str(S['wx'].get_weather()), 'paused_after': u.GameplayStatics.is_game_paused(S['pc'])}
        R['menu'].append(row)
        log('menu', json.dumps(row))
    step(0.05, f)


def menu_cancel(tag):
    def f(t):
        before = str(S['wx'].get_weather())
        key('F6')
        opened = S['pc'].is_graphics_menu_open()
        key('Up')
        key('Right')
        key('F6')  # cancel: the pending change must be discarded
        row = {'tag': tag, 'before': before, 'opened': opened, 'closed': not S['pc'].is_graphics_menu_open(),
               'after': str(S['wx'].get_weather())}
        R['menu'].append(row)
        log('menu', json.dumps(row))
    step(0.05, f)


def watch_thunder(name, seconds):
    def start(t):
        S['watch_thunder'] = {'name': name, 'until': t + seconds, 'shots': 0}
    step(0.05, start)
    step(seconds + 0.1, lambda t: S.update(watch_thunder=None))


ZOMBIES = ('HoverCyberZombie', 'HoverNYCZombie', 'HoverZombie', 'ZE_ZombieCharacter')


def zombies(w):
    out = []
    for name in ZOMBIES:
        cls = getattr(u, name, None)
        if cls:
            out += list(u.GameplayStatics.get_all_actors_of_class(w, cls))
    return out


def blood_on(tag, who):
    """A blood decal (Blood_VFX_Pack MI_BloodDecal, the same kind of deferred decal as impact / blood decals)
    attached to a character's chest, projected from the front; 'zombie' takes the nearest zombie 9-35 m away and
    freezes it (custom time dilation 0) for the shot. Finding D: it must show while the wet / snow layer is on."""
    def f(t):
        w = world()
        p = pawn()
        a = p
        if who == 'zombie':
            pl = p.get_actor_location()
            best = None
            for z in zombies(w):
                dist = (z.get_actor_location() - pl).length()
                if 900 < dist < 3500 and (best is None or dist < best[0]):
                    best = (dist, z)
            if not best:
                R['blood'].append({'tag': tag, 'error': 'no zombie 9-35 m away'})
                S['focus'] = None
                return
            a = best[1]
            a.set_editor_property('custom_time_dilation', 0.0)
            S['frozen'] = a
        S['focus'] = a
        mat = u.load_asset(BLOOD)
        l = a.get_actor_location()
        fwd = a.get_actor_forward_vector()
        chest = u.Vector(l.x + fwd.x * 10, l.y + fwd.y * 10, l.z + 35)
        rot = u.MathLibrary.make_rot_from_x(u.Vector(-fwd.x, -fwd.y, 0))   # projects along +X: into the chest
        mesh = a.get_editor_property('mesh')
        dc = u.GameplayStatics.spawn_decal_attached(mat, u.Vector(30, 22, 22), mesh, 'None', chest, rot,
                                                    u.AttachLocation.KEEP_WORLD_POSITION, 0.0)
        row = {'tag': tag, 'actor': a.get_class().get_name(), 'decal': bool(dc), 'material': BLOOD,
               'mesh_receives_decals': bool(mesh.get_editor_property('receives_decals')),
               'mesh_custom_depth': bool(mesh.get_editor_property('render_custom_depth')),
               'weather': str(S['wx'].get_weather())}
        R['blood'].append(row)
        log('blood', json.dumps(row))
    step(0.05, f)


def unfreeze(t):
    z = S.pop('frozen', None)
    if z:
        try:
            z.destroy_actor()
        except Exception:  # noqa: BLE001
            pass
    S['focus'] = None


MOVE_PHASES = (  # name, seconds, held keys, camera yaw rate (deg/s)
    ('still', 3.0, (), 0.0),
    ('run', 4.0, ('W', SPRINT), 0.0),
    ('turn', 4.0, (), 90.0),
    ('runturn', 4.0, ('W', SPRINT), 45.0),
)


def move_test(kind, record):
    """Vexa's own camera. Weather set at once, 8 s to settle, then the phases above; every frame counts the drops /
    flakes within 15 m and 7 m of the camera inside a 40 deg half-angle cone (what is in front of the player), the
    camera's speed and the lead the volumes use. Stills mid-run and mid-turn; video frames for 'record' phases."""
    step(0.05, reset_vexa)
    step(0.05, lambda t: view('player'))
    step(0.05, lambda t: console('Weather %s 0' % kind))
    step(8.0, lambda t: state('move %s settled' % kind))
    for name, secs, keys, yaw in MOVE_PHASES:
        def start(t, name=name, keys=keys, yaw=yaw):
            release_all()
            for k in keys:
                hold(k, True)
            S['yaw_rate'] = yaw
            S['msample'] = {'name': '%s_%s' % (kind.lower(), name), 'rows': []}
            if record and name in record and not QUICK:
                S.update(rec=record[name], rec_n=0, rec_skip=1)
        step(0.05, start)
        if name != 'still':
            step(secs / 2, lambda t, n='move_%s_%s' % (kind.lower(), name): capture(n))
        else:
            step(secs / 2, lambda t: None)
        step(secs / 2, lambda t: end_move())
    step(0.05, lambda t: release_all())
    step(0.05, reset_vexa)
    step(0.5, lambda t: state('move %s done' % kind))


def end_move():
    m = S['msample']
    S['msample'] = None
    S['rec'] = None
    if not m or not m['rows']:
        return
    rows = m['rows']

    def col(i):
        return [r[i] for r in rows]

    def summary(xs):
        d = sorted(xs)
        return {'mean': round(sum(d) / len(d), 1), 'min': d[0], 'p10': d[int(len(d) * .1)], 'max': d[-1]}
    R['move'][m['name']] = {'frames': len(rows), 'in_view_15m': summary(col(0)), 'in_view_7m': summary(col(1)),
                            'camera_speed': summary(col(2)), 'lead_speed': summary(col(3)),
                            'live_total': summary(col(4))}
    log('move', m['name'], json.dumps(R['move'][m['name']]))


def plan_perf():
    """A/B/A windows with the player MOVING (Vexa runs a circle: W + L3, camera yaw 40 deg/s, from the same start
    every window) so drift (other work on the machine) shows up: each weather twice, Clear between, instant
    switches, 4 s settle, 4 s window, one profilegpu per window (log 'Frame Time')."""
    step(2.0, lambda t: view('player'))
    n = 0
    # WEATHER_PERF_SEQ: a custom window list for one round (repeated twice), e.g. 'Clear,Rain,Clear,Rain/nosplash';
    # '/nosplash' runs that window with AHoverWeather.max_splashes_per_second 0 (in-run splash A/B).
    seq = [x.strip() for x in os.environ.get('WEATHER_PERF_SEQ', 'Clear,Rain,Clear,Snow,Clear,Storm').split(',')]
    for rnd in (1, 2):
        for item in seq:
            w, _, opt = item.partition('/')
            n += 1
            name = '%02d_%s' % (n, item.replace('/', '_'))
            step(0.05, reset_vexa)

            def splashes(t, opt=opt):
                if 'splash0' not in S:
                    S['splash0'] = S['wx'].get_editor_property('max_splashes_per_second')
                S['wx'].set_editor_property('max_splashes_per_second', 0.0 if opt == 'nosplash' else S['splash0'])
            step(0.05, splashes)
            step(0.05, lambda t, w=w: console('Weather %s 0' % w))

            def go(t):
                hold('W', True)
                hold(SPRINT, True)
                S['yaw_rate'] = 40.0
            step(0.05, go)
            step(4.0, lambda t, n=name: S.update(perf={'name': n, 'dts': [], 'tt': [], 'particles': [], 'speed': []}))
            step(4.0, lambda t: end_perf())
            step(0.05, lambda t: release_all())
            step(0.05, lambda t: console('profilegpu'))
            step(0.3, lambda t, n=name: log('profilegpu', n))
    step(0.05, reset_vexa)
    step(0.2, lambda t: finish())


def plan_move():
    step(0.05, lambda t: cap('start (before any weather)'))
    move_test('Rain', None)
    move_test('Snow', None)
    step(0.05, lambda t: console('Weather Clear 0'))
    step(0.5, lambda t: cap('after Clear'))
    step(0.2, lambda t: finish())


def plan():
    if PERF:
        plan_perf()
        return
    if MOVE:
        plan_move()
        return
    step(0.05, lambda t: state('start'))
    step(0.05, lambda t: cap('start (before any weather)'))
    shot('player', 'clear_player', 2.0)
    if BASELINE:
        shot('street', 'clear_street', 0.8)
        step(0.2, lambda t: finish())
        return
    rec('v01_clear_player', 2.0, 'player')
    shot('street', 'clear_street', 0.8)
    rec('v02_clear_street', 2.0, 'street')
    menu_to(2, 'menu Clear->Rain')
    step(0.05, lambda t: state('rain set'))
    step(0.05, lambda t: cap('rain set'))
    rec('v03_to_rain_player', 6.5, 'player')
    step(0.05, lambda t: state('rain blended'))
    shot('player', 'rain_player', 0.4)
    shot('street', 'rain_street', 0.8)
    rec('v04_rain_street', 4.0, 'street')
    shot('close', 'rain_close', 0.8)
    blood_on('rain vexa', 'vexa')
    shot('blood', 'rain_blood_vexa', 0.6)
    blood_on('rain zombie', 'zombie')
    step(0.05, lambda t: state('rain blood'))
    shot('blood', 'rain_blood_zombie', 0.6)
    step(0.05, unfreeze)
    move_test('Rain', {'run': 'v08_rain_run_player'})
    step(0.05, lambda t: console('Weather Storm 3'))
    step(3.5, lambda t: state('storm blended'))
    shot('player', 'storm_player', 0.4)
    step(0.05, lambda t: view('street'))
    watch_thunder('storm_flash', 14.0)
    shot('street', 'storm_street', 0.4)
    menu_to(1, 'menu Storm->Snow')
    step(0.05, lambda t: state('snow set'))
    rec('v05_to_snow_player', 6.5, 'player')
    step(0.05, lambda t: state('snow blended'))
    shot('player', 'snow_player', 0.4)
    shot('street', 'snow_street', 0.8)
    rec('v06_snow_street', 4.0, 'street')
    shot('close', 'snow_close', 0.8)
    blood_on('snow vexa', 'vexa')
    shot('blood', 'snow_blood_vexa', 0.6)
    blood_on('snow zombie', 'zombie')
    shot('blood', 'snow_blood_zombie', 0.6)
    step(0.05, unfreeze)
    move_test('Snow', {'run': 'v09_snow_run_player', 'turn': 'v10_snow_turn_player'})
    step(0.05, lambda t: console('Weather Cloudy 0'))
    shot('player', 'cloudy_player', 1.5)
    shot('street', 'cloudy_street', 0.8)
    step(0.05, lambda t: cap('cloudy (dry, after snow)'))
    step(0.05, lambda t: console('Weather Clear 0'))
    step(0.05, lambda t: state('clear again'))
    step(0.05, lambda t: cap('clear again'))
    shot('player', 'clear_after_player', 2.0)
    shot('street', 'clear_after_street', 0.8)
    rec('v07_clear_after_street', 2.0, 'street')
    menu_cancel('menu open + cancel')
    step(0.3, lambda t: state('end'))
    step(0.2, lambda t: finish())


def keep_zombies_off(w):
    p = pawn()
    if not p:
        return
    pl = p.get_actor_location()
    for z in zombies(w):
        if z != S.get('frozen') and (z.get_actor_location() - pl).length() < 700:
            z.destroy_actor()
            R['removed_zombies'] += 1


def per_frame(w, t):
    now = time.monotonic()
    p = pawn()
    if S['perf'] is not None and S['last_real'] is not None:
        S['perf']['dts'].append(now - S['last_real'])
        tt = u.HoverAuthoring.get_thread_times_ms()
        S['perf']['tt'].append((tt.x, tt.y, tt.z, tt.w))
        if S['wx']:
            S['perf']['particles'].append(S['wx'].get_live_particle_count())
        S['perf']['speed'].append(p.get_velocity().length() if p else 0)
    S['last_real'] = now
    if S['msample'] is not None and S['wx']:
        wx = S['wx']
        S['msample']['rows'].append((wx.count_particles_in_view(1500, 40), wx.count_particles_in_view(700, 40),
                                     round(p.get_velocity().length()) if p else 0,
                                     round(wx.get_view_velocity().length()), wx.get_live_particle_count()))
    if S['rec']:
        # 15 fps of game time (every second 1/30 s step); MakeWeatherVideo.py doubles them to 30 fps.
        S['rec_tick'] = 1 - S.get('rec_tick', 0)
        if S['rec_skip'] > 0:
            S['rec_skip'] -= 1
        elif S['rec_tick']:
            fn = FRAMES / ('%s_%04d.png' % (S['rec'], S['rec_n']))
            c0 = time.monotonic()
            u.HoverAuthoring.capture_world_frame(str(fn))
            R['capture_s'].setdefault(S['rec'], []).append(round(time.monotonic() - c0, 3))
            R['frames'][S['rec']] = S['rec_n'] + 1
            S['rec_n'] += 1
        S['last_real'] = None  # captured frames do not count for perf
    wt = S['watch_thunder']
    if wt:
        cls = u.load_class(None, THUNDER)
        bolts = u.GameplayStatics.get_all_actors_of_class(w, cls) if cls else []
        if bolts and wt['shots'] < 4:
            # The strike's flash lasts ~0.35 s: capture two frames of it per strike, at most four in total.
            capture('%s_%d' % (wt['name'], wt['shots']))
            wt['shots'] += 1
            if not R['thunder'] or R['thunder'][-1]['t'] < t - 1.0:
                R['thunder'].append({'t': round(t, 2), 'at': str(bolts[0].get_actor_location())})


def write():
    (ROOT / OUT_JSON).write_text(json.dumps(R, indent=1, default=str))


def finish():
    if S['end']:
        return
    S['rec'] = None
    release_all()
    write()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def tick(dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                if not S['done']:
                    S['done'] = True
                    cap('after PIE ended (EndPlay)')
                    write()
                    log('DONE stills=%d errors=%d' % (len(R['stills']), len(R['errors'])))
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 5400:
            raise RuntimeError('weather proof timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 7:
                try:
                    u.HoverAuthoring.configure_offscreen_display(WIDTH + 16, HEIGHT + 80)
                except Exception as e:  # noqa: BLE001
                    R['errors'].append('configure_offscreen_display: %s' % e)
                u.HoverAuthoring.start_playtest(WIDTH, HEIGHT + 32)
                S['play'] = True
            return
        w = world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        t = u.GameplayStatics.get_time_seconds(w)
        if S['pc'] is None:
            S['pc'] = pc
            S['t_first'] = t
            return
        keep_zombies_off(w)
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            for cmd in ('r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 2500', 'r.ScreenPercentage 100',
                        'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
                console(cmd)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=V((0, 0, 500)),
                                                                                       rotation=u.Rotator()))
            S['cam'].camera_component.set_editor_property('constrain_aspect_ratio', False)
            found = u.GameplayStatics.get_all_actors_of_class(w, u.HoverWeather)
            S['wx'] = found[0] if found else None
            R['weather_actor'] = S['wx'].get_actor_label() if S['wx'] and hasattr(S['wx'], 'get_actor_label') else (
                S['wx'].get_name() if S['wx'] else None)
            if not S['wx'] and not BASELINE:
                raise RuntimeError('no AHoverWeather in L_NYC_Survival: run Scripts/ImportWeather.py first')
            p = pc.get_controlled_pawn()
            S['spawn'] = (p.get_actor_location(), pc.get_control_rotation().yaw)
            R['spawn'] = {'location': str(S['spawn'][0]), 'yaw': round(S['spawn'][1], 1)}
            if S['wx']:
                if LEGACY:  # the placement before fix round 1
                    for k, v in (('snow_ahead', 500.0), ('snow_far_ahead', 2600.0), ('rain_lead_seconds', 0.0),
                                 ('snow_lead_seconds', 0.0)):
                        S['wx'].set_editor_property(k, v)
                for k, v in json.loads(os.environ.get('WEATHER_SET') or '{}').items():  # A/B tests, e.g. splashes off
                    S['wx'].set_editor_property(k, v)
                    R.setdefault('set', {})[k] = v
                R['placement'] = {k: S['wx'].get_editor_property(k) for k in (
                    'rain_near_ahead', 'rain_far_ahead', 'snow_ahead', 'snow_far_ahead', 'rain_lead_seconds',
                    'snow_lead_seconds', 'max_lead', 'surface_fade_start', 'surface_fade_end')}
                R['placement']['surface_decal_size'] = str(S['wx'].get_editor_property('surface_decal_size'))
            for cv in ('r.CustomDepth', 'r.CustomDepth.Order', 'r.DBuffer'):
                try:
                    R.setdefault('cvars', {})[cv] = u.SystemLibrary.get_console_variable_int_value(cv)
                except Exception as e:  # noqa: BLE001
                    R.setdefault('cvars', {})[cv] = 'n/a: %s' % e
            R['game_mode'] = u.GameplayStatics.get_game_mode(w).get_class().get_name()
            R['pawn'] = p.get_class().get_name()
            plan()
            S['next'] = t
            return
        if S['yaw_rate']:
            r = pc.get_control_rotation()
            pc.set_control_rotation(u.Rotator(roll=0.0, pitch=r.pitch, yaw=r.yaw + S['yaw_rate'] / 30.0))
        per_frame(w, t)
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:  # noqa: BLE001
        R['errors'].append(traceback.format_exc())
        R['ok'] = False
        log('ERROR', R['errors'][-1][-1200:])
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
