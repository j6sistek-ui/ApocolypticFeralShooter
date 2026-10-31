"""ProveLifeEngineCompare.py - measured movement feel, Life Engine vs Classic, on L_NYC_Survival (2026-10-31).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveLifeEngineCompare.py
      -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720 "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, ..."

Owner 2026-10-31: "compare and tell me the impact it has, movement speed and feel; then I'll test it later."
PIE, isolated test input, fixed 1/30 s step, zombies removed as they spawn. Each test starts from the same spot facing
the same way, Vexa at rest. Two passes: Life Engine ON (`LifeEngine 1`), then OFF (Classic, `LifeEngine 0`).
Tests: walk start/stop, sprint start/stop, reverse (W then S), 90-degree turn (W then D), standing jump, running jump,
air control (running jump, then D only in the air), held jump while sprinting (bunny hop), crouch-walk speed.
Every tick is sampled (position, velocity, grounded) and each test is reduced to a few numbers. Receipt
D:/AFS_Comparisons/LifeEngineCompare_20261031/compare.json (summary + per-test traces). Changes only the Play world.
"""
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/LifeEngineCompare_20261031')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 900
SPRINT = 'Gamepad_LeftThumbstick'
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'tests': {}, 'summary': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'mode': None, 'test': None, 'rows': [], 'hold': set(), 'spam': None,
     'origin': None, 'yaw': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def save():
    (OUT / 'compare.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s: %s' % (cmd, e))


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def release_all():
    for k in list(S['hold']):
        key(k, False)
    S['spam'] = None


def grounded(p):
    try:
        return bool(p.get_editor_property('character_movement').is_moving_on_ground())
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('grounded: %s' % e)
        return None


def life_active(p):
    try:
        return bool(p.is_life_engine_active())
    except Exception:  # noqa: BLE001
        return None


def clear_zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if cls:
        for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
            z.destroy_actor()


# ---------------------------------------------------------------- test plan

def reset(t):
    """Back to the start spot, facing the start direction, at rest."""
    release_all()
    p = pawn()
    p.set_actor_location(u.Vector(*S['origin']), False, True)
    S['pc'].set_control_rotation(u.Rotator(roll=0.0, pitch=0.0, yaw=S['yaw']))


def begin(name):
    def f(t):
        S['test'] = {'name': name, 't0': t, 'rows': [], 'marks': {}}
    return f


def mark(label):
    def f(t):
        if S['test']:
            S['test']['marks'][label] = round(t - S['test']['t0'], 3)
    return f


def end(t):
    tr = S['test']
    S['test'] = None
    if tr:
        R['tests'].setdefault(S['mode'], {})[tr['name']] = analyse(tr)
        save()


def press(*names):
    return lambda t: [key(n, True) for n in names]


def lift(*names):
    return lambda t: [key(n, False) for n in names]


def spam_jump(on):
    def f(t):
        S['spam'] = 'SpaceBar' if on else None
        if not on:
            key('SpaceBar', False)
    return f


def plan():
    q = []

    def test(name, steps):
        q.append((0.6, reset))
        q.append((1.0, begin(name)))
        q.extend(steps)
        q.append((0.0, end))

    def mode_pass(mode):
        def start(t):
            S['mode'] = mode
            console('LifeEngine %d' % (1 if mode == 'life' else 0))
        q.append((0.5, start))
        test('walk', [(0.0, press('W')), (2.0, mark('release')), (0.0, lift('W')), (1.5, lambda t: None)])
        test('sprint', [(0.0, press(SPRINT, 'W')), (2.0, mark('release')), (0.0, lift('W', SPRINT)),
                        (1.5, lambda t: None)])
        test('reverse', [(0.0, press('W')), (1.5, mark('switch')), (0.0, lift('W')), (0.0, press('S')),
                         (1.2, lift('S')), (1.0, lambda t: None)])
        test('turn90', [(0.0, press('W')), (1.5, mark('switch')), (0.0, lift('W')), (0.0, press('D')),
                        (1.2, lift('D')), (1.0, lambda t: None)])
        test('jump_stand', [(0.0, mark('press')), (0.0, press('SpaceBar')), (0.1, lift('SpaceBar')),
                            (1.6, lambda t: None)])
        test('jump_run', [(0.0, press(SPRINT, 'W')), (1.2, mark('press')), (0.0, press('SpaceBar')),
                          (0.1, lift('SpaceBar')), (1.4, lift('W', SPRINT)), (1.2, lambda t: None)])
        test('air_control', [(0.0, press(SPRINT, 'W')), (1.2, mark('press')), (0.0, press('SpaceBar')),
                             (0.1, lift('SpaceBar', 'W', SPRINT)), (0.0, press('D')), (1.2, lift('D')),
                             (1.2, lambda t: None)])
        test('bhop', [(0.0, press(SPRINT, 'W')), (0.6, mark('hold')), (0.0, press('SpaceBar')),
                      (0.0, spam_jump(True)), (3.0, spam_jump(False)), (0.0, lift('W', SPRINT, 'SpaceBar')),
                      (1.5, lambda t: None)])
        test('crouch_walk', [(0.0, press('LeftControl')), (0.4, press('W')), (2.0, lift('W', 'LeftControl')),
                             (1.2, lambda t: None)])

    mode_pass('life')
    mode_pass('classic')
    q.append((0.5, lambda t: finish()))
    S['queue'] = q


# ---------------------------------------------------------------- analysis

def analyse(tr):
    rows = tr['rows']
    out = {'marks': tr['marks'], 'samples': len(rows)}
    if not rows:
        return out
    sp = [r['speed'] for r in rows]
    out['peak_speed'] = round(max(sp), 1)
    name = tr['name']
    z0 = rows[0]['z']

    def first(pred, after=0.0):
        for r in rows:
            if r['t'] >= after and pred(r):
                return r
        return None

    if name in ('walk', 'sprint', 'crouch_walk'):
        rel = tr['marks'].get('release', rows[-1]['t'])
        steady = [r['speed'] for r in rows if rel - 0.6 <= r['t'] < rel] or [out['peak_speed']]
        vmax = sum(steady) / len(steady)
        out['steady_speed'] = round(vmax, 1)
        r90 = first(lambda r: r['speed'] >= 0.9 * vmax)
        out['t_to_90pct'] = round(r90['t'], 3) if r90 else None
        r25 = first(lambda r: r['t'] >= 0.25)
        out['speed_at_0_25s'] = r25['speed'] if r25 else None
        if 'release' in tr['marks']:
            at = first(lambda r: r['t'] >= rel)
            stop = first(lambda r: r['speed'] < 20, after=rel)
            if at and stop:
                out['stop_time'] = round(stop['t'] - rel, 3)
                out['stop_distance_cm'] = round(math.dist(at['xy'], stop['xy']), 1)
    if name == 'reverse':
        sw = tr['marks']['switch']
        at = first(lambda r: r['t'] >= sw)
        fwd = at['vxy'] if at else (0, 0)
        n = math.hypot(*fwd) or 1
        f = (fwd[0] / n, fwd[1] / n)
        along = [(r['t'], r['vxy'][0] * f[0] + r['vxy'][1] * f[1]) for r in rows if r['t'] >= sw]
        zero = next((t for t, a in along if a <= 0), None)
        back = next((t for t, a in along if a <= -0.9 * (at['speed'] if at else 500)), None)
        out['t_to_zero'] = round(zero - sw, 3) if zero else None
        out['t_to_90pct_back'] = round(back - sw, 3) if back else None
    if name == 'turn90':
        sw = tr['marks']['switch']
        at = first(lambda r: r['t'] >= sw)
        h0 = math.atan2(at['vxy'][1], at['vxy'][0]) if at else 0
        turned = next((r['t'] for r in rows if r['t'] >= sw and r['speed'] > 50 and
                       abs((math.degrees(math.atan2(r['vxy'][1], r['vxy'][0]) - h0) + 180) % 360 - 180) >= 80),
                      None)
        out['t_to_80deg'] = round(turned - sw, 3) if turned else None
        dip = min((r['speed'] for r in rows if sw <= r['t'] <= sw + 0.6), default=None)
        out['min_speed_during_turn'] = dip
    if name.startswith('jump') or name in ('air_control', 'bhop'):
        pr = tr['marks'].get('press', tr['marks'].get('hold', 0.0))
        air = [r for r in rows if r['t'] >= pr and r['grounded'] is False]
        out['peak_rise_cm'] = round(max(r['z'] for r in rows) - z0, 1)
        if air and name != 'bhop':
            t_off = air[0]['t']
            land = first(lambda r: r['grounded'], after=t_off)
            out['air_time'] = round((land['t'] if land else rows[-1]['t']) - t_off, 3)
            before = first(lambda r: r['t'] >= pr)
            out['speed_at_takeoff'] = before['speed'] if before else None
            if land:
                out['speed_at_landing'] = land['speed']
                out['air_distance_cm'] = round(math.dist(air[0]['xy'], land['xy']), 1)
                if name == 'air_control':
                    # Sideways travel in the air (perpendicular to the take-off direction).
                    v = before['vxy'] if before else (0, -1)
                    n = math.hypot(*v) or 1
                    side = (-v[1] / n, v[0] / n)
                    d = (land['xy'][0] - air[0]['xy'][0], land['xy'][1] - air[0]['xy'][1])
                    out['air_sideways_cm'] = round(abs(d[0] * side[0] + d[1] * side[1]), 1)
        if name == 'bhop':
            hop = [r for r in rows if r['t'] >= pr]
            out['bhop_peak_speed'] = round(max((r['speed'] for r in hop), default=0), 1)
            out['bhop_final_speed'] = hop[-1]['speed'] if hop else None
            out['hops'] = sum(1 for a, b in zip(hop, hop[1:]) if a['grounded'] and b['grounded'] is False)
    out['trace'] = [{k: r[k] for k in ('t', 'speed', 'z', 'grounded')} for r in rows[::3]]
    return out


def sample(t):
    tr = S['test']
    if not tr:
        return
    p = pawn()
    loc, vel = p.get_actor_location(), p.get_velocity()
    tr['rows'].append({'t': round(t - tr['t0'], 3), 'xy': (round(loc.x, 1), round(loc.y, 1)),
                       'z': round(loc.z, 1), 'vxy': (round(vel.x, 1), round(vel.y, 1)),
                       'speed': round(math.hypot(vel.x, vel.y), 1), 'grounded': grounded(p),
                       'life': life_active(p)})


def summarise():
    keys = [('walk', 'steady_speed'), ('walk', 't_to_90pct'), ('walk', 'speed_at_0_25s'), ('walk', 'stop_time'),
            ('walk', 'stop_distance_cm'), ('sprint', 'steady_speed'), ('sprint', 't_to_90pct'),
            ('sprint', 'stop_time'), ('sprint', 'stop_distance_cm'), ('reverse', 't_to_zero'),
            ('reverse', 't_to_90pct_back'), ('turn90', 't_to_80deg'), ('turn90', 'min_speed_during_turn'),
            ('jump_stand', 'peak_rise_cm'), ('jump_stand', 'air_time'), ('jump_run', 'peak_rise_cm'),
            ('jump_run', 'air_time'), ('jump_run', 'air_distance_cm'), ('jump_run', 'speed_at_landing'),
            ('air_control', 'air_sideways_cm'), ('bhop', 'bhop_peak_speed'), ('bhop', 'hops'),
            ('crouch_walk', 'steady_speed')]
    table = {}
    for test, k in keys:
        table['%s.%s' % (test, k)] = {m: R['tests'].get(m, {}).get(test, {}).get(k) for m in ('life', 'classic')}
    R['summary'] = table
    R['life_was_active'] = any(r for r in [R['tests'].get('life', {}).get('walk', {}).get('samples')])
    R['ok'] = bool(R['tests'].get('life')) and bool(R['tests'].get('classic')) and not R['errors']


def finish():
    if S['end']:
        return
    release_all()
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
                    summarise()
                    save()
                    print('PROVE_COMPARE_DONE', json.dumps(R['summary'], default=str), flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('compare timeout')
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
        if S['origin'] is None:
            if t - S['t_first'] < 3.0:
                return
            for cmd in ('Log LogTemp Verbose', 'DisableAllScreenMessages'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            loc = p.get_actor_location()
            S['origin'] = (loc.x, loc.y, loc.z + 2.0)
            S['yaw'] = pc.get_control_rotation().yaw
            R['setup'] = {'pawn': p.get_class().get_name(), 'start': [round(v, 1) for v in S['origin']],
                          'yaw': round(S['yaw'], 1), 'life_active_at_start': life_active(p)}
            plan()
            S['next'] = t
            return
        if S['spam']:
            key(S['spam'], S['spam'] not in S['hold'])
        sample(t)
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_COMPARE_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
