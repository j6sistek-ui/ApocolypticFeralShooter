"""ProveLifeEngineAudio.py - in-game receipt for the Life Engine wiring and the audio pass on L_NYC_Survival.

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveLifeEngineAudio.py
      -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720 "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, ..."

PIE at 1280x720, test input isolated, fixed 1/30 s step, zombies destroyed as they spawn. Two passes, Life Engine ON
(the NYC Survival default) then OFF (`LifeEngine 0`): hold W 2 s (displacement, speed, ground flag), release, one
SpaceBar tap (peak rise), one V tap (katana swing), stills of the walk from the chase camera. Then the log is
harvested: LIFE_ENGINE created/active/suspended lines, HOVER_FOOTSTEP (Verbose, enabled here) and
HOVER_MELEE_SWING_SOUND counts, HOVER_NYC_WEATHER_BED. Receipt D:/AFS_Comparisons/LifeEngine_20261031/proof.json.
Changes only the unsaved Play world.
"""
import json
import math
import os
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/LifeEngine_20261031')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 900
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'passes': {}, 'log': {}, 'stills': []}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'ticks': 0, 'trace': None, 'cam': None, 'zombies_removed': 0, 'hold': set()}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'


def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
        return True
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s: %s' % (cmd, e))
        return False


def tap(name):
    key(name, True)
    key(name, False)


def menu_tick():
    m = S.get('menu')
    if not m:
        return False
    if not m['shot'] and time.monotonic() - m['t'] > 0.6:
        # A paused offscreen viewport is not redrawn, so no still of the menu; the receipt records the result.
        m['shot'] = True
        m['t'] = time.monotonic()
    elif m['shot'] and time.monotonic() - m['t'] > 0.3:
        tap('Enter')
        R['menu_toggle'] = {'life_active_after': life_active(pawn())}
        S['menu'] = None
    return True


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def clear_zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls:
        return
    for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
        z.destroy_actor()
        S['zombies_removed'] += 1


def life_active(p):
    try:
        return bool(p.is_life_engine_active())
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('is_life_engine_active: %s' % e)
        return None


def capture(name):
    fn = OUT / (name + '.png')
    p = pawn()
    loc = p.get_actor_location()
    f = p.get_actor_forward_vector()
    cam = S['cam']
    cam_loc = loc - f * 420 + u.Vector(0, 0, 170)
    cam.set_actor_location_and_rotation(cam_loc, u.MathLibrary.find_look_at_rotation(cam_loc, loc + u.Vector(0, 0, 40)),
                                        False, False)
    S['pc'].set_view_target_with_blend(cam, 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    # ReadPixels returns the frame already rendered, so the snap waits one tick after the camera move.
    S['queue'].insert(0, (0.1, lambda t: snap(fn)))


def snap(fn):
    u.HoverAuthoring.capture_world_frame(str(fn))
    R['stills'].append(fn.name)


def begin_trace(name):
    S['trace'] = {'name': name, 'rows': [], 'start_loc': vec(pawn().get_actor_location()), 't0': None}


def end_trace():
    tr = S['trace']
    S['trace'] = None
    if not tr:
        return
    rows = tr['rows']
    p = pawn()
    tr['end_loc'] = vec(p.get_actor_location())
    d = [b - a for a, b in zip(tr['start_loc'], tr['end_loc'])]
    tr['displacement_cm'] = round((d[0] ** 2 + d[1] ** 2) ** .5, 1)
    tr['peak_speed'] = round(max([r['speed'] for r in rows] or [0]), 1)
    tr['peak_rise_cm'] = round(max([r['z'] for r in rows] or [tr['start_loc'][2]]) - tr['start_loc'][2], 1)
    tr['ticks'] = len(rows)
    tr['life_active_any'] = any(r['life'] for r in rows)
    tr['rows'] = rows[::5][:40]
    R['passes'].setdefault(tr['mode'] if 'mode' in tr else S['mode'], {})[tr['name']] = tr
    save()


def trace_tick(t):
    tr = S['trace']
    if not tr:
        return
    p = pawn()
    if tr['t0'] is None:
        tr['t0'] = t
    loc = p.get_actor_location()
    row = {'t': round(t - tr['t0'], 3), 'z': round(loc.z, 1), 'speed': round(math.hypot(p.get_velocity().x, p.get_velocity().y), 1),
           'life': life_active(p)}
    # Solver-side diagnostics (what the pilot fed it, its speed target, ground state, control rotation, view target).
    try:
        lm = p.get_editor_property('life_movement')
        if lm:
            row.update({'inF': round(lm.get_editor_property('input_forward'), 2),
                        'maxG': round(lm.get_editor_property('max_ground_speed'), 0),
                        'gnd': lm.get_editor_property('grounded'),
                        'gnz': round(lm.get_editor_property('ground_normal').z, 3)})
        cr = S['pc'].get_control_rotation()
        row['cr'] = (round(cr.pitch, 1), round(cr.yaw, 1))
        row['yaw'] = round(p.get_actor_rotation().yaw, 1)
        vt = S['pc'].get_view_target()
        row['vt'] = vt.get_name() if vt else None
    except Exception as e:  # noqa: BLE001
        row['diag_err'] = str(e)[:100]
    tr['rows'].append(row)


def plan():
    q = []

    def mode_pass(mode):
        def start(t):
            S['mode'] = mode
            # Both passes cover the same stretch of road.
            pawn().set_actor_location(u.Vector(*R['setup']['start']), False, True)
            if mode == 'off':
                # Owner 2026-10-31: the switch is a row in the F6 test-settings menu. The menu pauses the game, so
                # the rest of the sequence runs on a real-time timer in tick() (menu_tick).
                tap('F6')
                for _ in range(4):
                    tap('Down')
                tap('Right')
                S['menu'] = {'t': time.monotonic(), 'shot': False}
            else:
                console('LifeEngine 1')
            console('HoverStatus')

        q.append((1.0, start))
        q.append((0.5, lambda t: begin_trace('walk')))
        q.append((0.0, lambda t: key('W', True)))
        q.append((1.0, lambda t: capture('%s_walk_a' % mode)))
        q.append((1.0, lambda t: capture('%s_walk_b' % mode)))
        q.append((0.0, lambda t: key('W', False)))
        q.append((0.8, lambda t: end_trace()))
        q.append((0.2, lambda t: begin_trace('jump')))
        q.append((0.0, lambda t: key('SpaceBar', True)))
        q.append((0.15, lambda t: key('SpaceBar', False)))
        q.append((0.4, lambda t: capture('%s_jump' % mode)))
        q.append((1.2, lambda t: end_trace()))
        q.append((0.2, lambda t: begin_trace('sprint')))
        q.append((0.0, lambda t: (key('Gamepad_LeftThumbstick', True), key('W', True))))  # sprint is the stick click; LeftShift is only the board boost
        q.append((1.5, lambda t: capture('%s_sprint' % mode)))
        q.append((0.0, lambda t: (key('W', False), key('Gamepad_LeftThumbstick', False))))
        q.append((0.8, lambda t: end_trace()))
        q.append((0.2, lambda t: key('V', True)))
        q.append((0.1, lambda t: key('V', False)))
        q.append((0.4, lambda t: capture('%s_melee' % mode)))
        q.append((0.8, lambda t: console('HoverStatus')))

    mode_pass('on')
    mode_pass('off')
    q.append((0.5, lambda t: finish()))
    S['queue'] = q


def harvest_log():
    path = None
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        path = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        pass
    if not path:
        path = str(Path(u.Paths.project_log_dir()) / 'AFS.log')
    R['log']['path'] = path
    if not Path(path).exists():
        R['errors'].append('log not found: ' + path)
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    pick = lambda tag, n=12: [l[-160:] for l in lines if tag in l][-n:]  # noqa: E731
    R['log']['life_engine'] = pick('LIFE_ENGINE', 20)
    R['log']['hover_state'] = pick('HOVER_STATE', 6)
    R['log']['footsteps'] = len([l for l in lines if 'HOVER_FOOTSTEP' in l])
    R['log']['footstep_samples'] = pick('HOVER_FOOTSTEP', 6)
    R['log']['melee_swing_sounds'] = pick('HOVER_MELEE_SWING_SOUND', 4)
    R['log']['weather_bed'] = pick('HOVER_NYC_WEATHER_BED', 2)
    R['log']['hl_updated'] = len([l for l in lines if 'HLMovementSystem CPP UPDATED TEST' in l])
    R['log']['warnings_life'] = [l[-200:] for l in lines if ('Life' in l or 'HLRaw' in l) and ('Warning' in l or 'Error' in l)][-10:]


def summarise():
    on, off = R['passes'].get('on', {}), R['passes'].get('off', {})
    R['summary'] = {
        'life_on_walk_cm': on.get('walk', {}).get('displacement_cm'), 'life_on_walk_speed': on.get('walk', {}).get('peak_speed'),
        'life_on_jump_rise_cm': on.get('jump', {}).get('peak_rise_cm'), 'life_on_sprint_speed': on.get('sprint', {}).get('peak_speed'),
        'life_on_active': on.get('walk', {}).get('life_active_any'),
        'life_off_walk_cm': off.get('walk', {}).get('displacement_cm'), 'life_off_walk_speed': off.get('walk', {}).get('peak_speed'),
        'life_off_jump_rise_cm': off.get('jump', {}).get('peak_rise_cm'), 'life_off_sprint_speed': off.get('sprint', {}).get('peak_speed'),
        'life_off_active': off.get('walk', {}).get('life_active_any'),
        'footsteps_logged': R['log'].get('footsteps'), 'melee_swing_logged': len(R['log'].get('melee_swing_sounds', [])),
        'weather_bed': bool(R['log'].get('weather_bed')), 'zombies_removed': S['zombies_removed'],
    }
    s = R['summary']
    R['ok'] = bool(s['life_on_active']) and s['life_off_active'] is False and (s['life_on_walk_cm'] or 0) > 150 and \
        (s['life_off_walk_cm'] or 0) > 150 and (s['footsteps_logged'] or 0) > 0 and not R['errors']


def finish():
    if S['end']:
        return
    for k in list(S['hold']):
        key(k, False)
    save()
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
                    harvest_log()
                    summarise()
                    save()
                    print('PROVE_LIFE_DONE', json.dumps(R['summary'], default=str), flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('proof timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 7:
                try:
                    u.HoverAuthoring.configure_offscreen_display(WIDTH + 16, HEIGHT + 80)
                except Exception as e:  # noqa: BLE001
                    R['api_errors'].append('configure_offscreen_display: %s' % e)
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
        p = pc.get_controlled_pawn()
        clear_zombies(w)
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            R['setup'] = {'pawn': p.get_class().get_name(), 'life_active_at_start': life_active(p),
                          'third_person': p.is_third_person_view(), 'start': vec(p.get_actor_location())}
            plan()
            S['next'] = t
            return
        if menu_tick():
            return
        S['ticks'] += 1
        trace_tick(t)
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_LIFE_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
