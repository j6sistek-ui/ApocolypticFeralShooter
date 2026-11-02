"""ProveWeather.py - rendered proof of the weather in L_NYC_Survival (GPU, -RenderOffscreen, PIE). Re-runnable.

  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" M:/UnrealProjects/AFS/AFS.uproject
      -unattended -RenderOffscreen -nosplash -ResX=1280 -ResY=720 -stdout -FullStdOutLogOutput
      -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveWeather.py
  then: python M:/UnrealProjects/AFS/Scripts/MakeWeatherVideo.py   (video, contact sheet, Clear-vs-baseline diff)

Same harness as Scripts/CapturePerkMachines.py / ProveWalking.py (PIE at a fixed 1/30 s step, camera actor,
HoverAuthoring.capture_world_frame, which returns the PREVIOUS frame, so every shot is taken >= 0.2 s after its view
was set). r.Streaming.FullyLoadUsedTextures 1 before shooting (Docs/LESSONS.md). Zombies keep spawning and walking
(they are part of the proof); any that reaches 7 m of Vexa is removed so she is never attacked during the shots.

Sequence: Clear (untouched map) -> F6 menu row to Rain (real key path: F6, Up = last row = Weather, Right x2,
Enter) recorded through the blend -> Storm (exec "Weather Storm", waits for a BP_Thunder strike) -> menu to Snow
(Right x1) recorded through the blend -> Cloudy (exec) -> Clear (exec "Weather Clear 0") and a menu open + cancel.
Video frames are taken at 15 fps of game time (every second step); a capture costs 0.5-3 s of wall time
(viewport read-back + PNG), so the whole run takes ~25-40 min.
Views: 'player' = Vexa's own third-person camera from the spawn, 'street' = a raised camera down the avenue,
'close' = low at Vexa's feet (wet ground / snow cover). Cost: per weather, 90 frames without captures: mean real
frame time, live weather particles; 'profilegpu' once per weather into the log.

WEATHER_PERF=1: cost only (Clear / Rain / Clear / Snow / Clear / Storm, twice; mean / p95 real frame time and
live particles per 4 s window, profilegpu per window) into perf.json.
WEATHER_QUICK=1: the same stills without video frames or perf windows (~5 min, for look iterations).
WEATHER_BASELINE=1: before ImportWeather.py placed the actor (or for a reference run): shoots only the Clear stills
(clear_player / clear_street at the same moments) into <out>/baseline/.
Out: D:/AFS_Comparisons/Weather_20261101/{stills,frames,baseline}/ + prove.json (WEATHER_OUT overrides the root).
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
QUICK = os.environ.get('WEATHER_QUICK') == '1'   # stills only: no video frames, no perf windows (look iterations)
PERF = os.environ.get('WEATHER_PERF') == '1'     # cost only: alternating Clear / Rain / Snow windows, no stills
STILLS = ROOT / ('baseline' if BASELINE else 'stills')
FRAMES = ROOT / 'frames'
for d in (STILLS, FRAMES):
    d.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
THUNDER = '/Game/MultiplayerDynamicWeatherSystem/Blueprints/BP_Thunder.BP_Thunder_C'
# Raised street camera: the avenue runs along Y through the plaza at x ~275 (zones Plaza 5250, SouthAve 4200).
STREET_EYE, STREET_AT = (520.0, 6650.0, 700.0), (230.0, 4300.0, 120.0)
R = {'ok': True, 'errors': [], 'frames': {}, 'capture_s': {}, 'stills': [], 'states': [], 'perf': {}, 'menu': [], 'thunder': [],
     'removed_zombies': 0, 'baseline': BASELINE, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'rec': None, 'rec_n': 0, 'rec_skip': 0,
     'perf': None, 'last_real': None, 'wx': None, 'view': 'player', 'watch_thunder': None}
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


def key(name):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0, False)
    u.HoverAuthoring.test_key(S['pc'], name, 0.0, False)


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


def view(name):
    S['view'] = name
    p = pawn()
    if name == 'player':
        S['pc'].set_view_target_with_blend(p, 0)
        return
    if name == 'street':
        eye, at, fov = STREET_EYE, STREET_AT, 70
    else:  # close: low, beside Vexa, looking past her feet along the ground
        l = p.get_actor_location()
        f = p.get_actor_forward_vector()
        eye = (l.x - f.x * 260 + f.y * 140, l.y - f.y * 260 - f.x * 140, l.z - 30)
        at = (l.x + f.x * 300, l.y + f.y * 300, l.z - 95)
        fov = 70
    rot = u.MathLibrary.find_look_at_rotation(V(eye), V(at))
    S['cam'].set_actor_location_and_rotation(V(eye), rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


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


def perf(name):
    if QUICK:
        return
    step(0.05, lambda t: view('player'))
    step(0.3, lambda t: S.update(perf={'name': name, 'dts': [], 'particles': []}))
    step(3.0, lambda t: end_perf())
    step(0.05, lambda t: console('profilegpu'))
    step(0.3, lambda t: log('profilegpu', name))


def end_perf():
    p = S['perf']
    S['perf'] = None
    if not p or not p['dts']:
        return
    d = sorted(p['dts'])
    R['perf'][p['name']] = {'frames': len(d), 'mean_ms': round(1000 * sum(d) / len(d), 2),
                            'p95_ms': round(1000 * d[int(len(d) * .95) - 1], 2),
                            'particles_max': max(p['particles']) if p['particles'] else 0,
                            'particles_mean': round(sum(p['particles']) / len(p['particles'])) if p['particles'] else 0}
    log('perf', p['name'], json.dumps(R['perf'][p['name']]))


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


def plan_perf():
    """A/B/A windows from Vexa's view so drift (other work on the machine) shows up: each weather twice,
    Clear between, instant switches, 2 s settle, 4 s window, one profilegpu per window (log 'Frame Time')."""
    step(2.0, lambda t: view('player'))
    n = 0
    for rnd in (1, 2):
        for w in ('Clear', 'Rain', 'Clear', 'Snow', 'Clear', 'Storm'):
            n += 1
            name = '%02d_%s' % (n, w)
            step(0.05, lambda t, w=w: console('Weather %s 0' % w))
            step(2.0, lambda t, n=name: S.update(perf={'name': n, 'dts': [], 'particles': []}))
            step(4.0, lambda t: end_perf())
            step(0.05, lambda t: console('profilegpu'))
            step(0.3, lambda t, n=name: log('profilegpu', n))
    step(0.2, lambda t: finish())


def plan():
    if PERF:
        plan_perf()
        return
    step(0.05, lambda t: state('start'))
    shot('player', 'clear_player', 2.0)
    if BASELINE:
        shot('street', 'clear_street', 0.8)
        step(0.2, lambda t: finish())
        return
    rec('v01_clear_player', 2.5, 'player')
    shot('street', 'clear_street', 0.8)
    rec('v02_clear_street', 2.5, 'street')
    perf('Clear')
    menu_to(2, 'menu Clear->Rain')
    step(0.05, lambda t: state('rain set'))
    rec('v03_to_rain_player', 7.0, 'player')
    step(0.05, lambda t: state('rain blended'))
    shot('player', 'rain_player', 0.4)
    shot('street', 'rain_street', 0.8)
    rec('v04_rain_street', 4.0, 'street')
    shot('close', 'rain_close', 0.8)
    perf('Rain')
    step(0.05, lambda t: console('Weather Storm 3'))
    step(3.5, lambda t: state('storm blended'))
    shot('player', 'storm_player', 0.4)
    step(0.05, lambda t: view('street'))
    watch_thunder('storm_flash', 14.0)
    shot('street', 'storm_street', 0.4)
    perf('Storm')
    menu_to(1, 'menu Storm->Snow')
    step(0.05, lambda t: state('snow set'))
    rec('v05_to_snow_player', 7.5, 'player')
    step(0.05, lambda t: state('snow blended'))
    shot('player', 'snow_player', 0.4)
    shot('street', 'snow_street', 0.8)
    rec('v06_snow_street', 4.0, 'street')
    shot('close', 'snow_close', 0.8)
    perf('Snow')
    step(0.05, lambda t: console('Weather Cloudy 0'))
    shot('player', 'cloudy_player', 1.5)
    shot('street', 'cloudy_street', 0.8)
    step(0.05, lambda t: console('Weather Clear 0'))
    step(0.05, lambda t: state('clear again'))
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
    for name in ('HoverCyberZombie', 'HoverNYCZombie', 'HoverZombie', 'ZE_ZombieCharacter'):
        cls = getattr(u, name, None)
        if not cls:
            continue
        for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
            if (z.get_actor_location() - pl).length() < 700:
                z.destroy_actor()
                R['removed_zombies'] += 1


def per_frame(w, t):
    now = time.monotonic()
    if S['perf'] is not None and S['last_real'] is not None:
        S['perf']['dts'].append(now - S['last_real'])
        if S['wx']:
            S['perf']['particles'].append(S['wx'].get_live_particle_count())
    S['last_real'] = now
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


def finish():
    if S['end']:
        return
    S['rec'] = None
    (ROOT / ('baseline.json' if BASELINE else 'perf.json' if PERF else 'prove.json')).write_text(
        json.dumps(R, indent=1, default=str))
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
                    (ROOT / ('baseline.json' if BASELINE else 'perf.json' if PERF else 'prove.json')).write_text(
                        json.dumps(R, indent=1, default=str))
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
            for cmd in ('r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 6000', 'r.ScreenPercentage 100',
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
            R['game_mode'] = u.GameplayStatics.get_game_mode(w).get_class().get_name()
            R['pawn'] = pc.get_controlled_pawn().get_class().get_name()
            plan()
            S['next'] = t
            return
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
