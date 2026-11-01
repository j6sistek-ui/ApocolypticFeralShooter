"""CapturePowerUpLive.py - a handful of PIE stills of the live power-up displays in NYC Exploration (sanity check only).

The owner judges the displays live in the editor ("no need for a video"): this takes stills, never a video or a frame
sequence. Same harness as Scripts/CapturePerkMachines.py (boot, fixed-step PIE, camera actor,
HoverAuthoring.capture_world_frame, which returns the previous frame). The three AHoverPowerUpDisplay actors (tag
AFS_PowerUpTrial, placed by Scripts/AuthorPowerUpLive.py) start their 30 s life together at BeginPlay; shots are timed
on the Nuke's life clock (GetLifeTime) and its schedule (GetSchedule: the spark bursts and pops):
  row_05 / row_15 / row_27 / row_29_5   the row from about 3.5 m (toward the player start), eye height
  <item>_close                          each item close at about 6 s
  nuke_burst_a/_b, nuke_pop_a/_b        the Nuke close just after a scheduled spark burst and a pop
  nuke_27_7, medkit_28_2, nuke_28_9     the warning (heartbeat, arc crawl) easing in
The player's pawn is hidden in PIE (it stands at the start, in the row view). Nothing is saved.
Env PU_LIVE_PLAN=fix (fix round 2026-10-31) takes the shorter check set instead, into stills_fix/ (or PU_LIVE_STILLS):
  row_05_start                          the row at 5 s from the player start itself (eye height)
  nuke_pop_a / _0_3 / _0_6              the Nuke close at a pop (+0.04 s flash, then +0.3 s and +0.6 s)
  maxammo_close                         the new orange amber
  nuke_27_5, medkit_28_2, nuke_28_9     the last 3 s (heartbeat, arc crawl; no echo ghost on the Nuke)
  and records, at the first PIE frame, whether every display's item and neon are visible (the hidden-phase bug), and
  the particle counts of one spark burst (and of the pop's smoke puff, if the look has one) in capture.json 'puff'.
Out: D:/AFS_Comparisons/PowerUps_20261031/Live/stills/*.png + capture.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -RenderOffscreen -nosplash -ResX=1280 -ResY=720 -stdout
       -FullStdOutLogOutput -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=<this>
"""
import json
import math
import os
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Explore'
TAG = 'AFS_PowerUpTrial'
OUT = Path('D:/AFS_Comparisons/PowerUps_20261031/Live')
PLAN = os.environ.get('PU_LIVE_PLAN', 'full')
STILLS = OUT / os.environ.get('PU_LIVE_STILLS', 'stills_fix' if PLAN == 'fix' else 'stills')
STILLS.mkdir(parents=True, exist_ok=True)
CAPTURE_JSON = STILLS / 'capture.json' if PLAN == 'fix' else OUT / 'capture.json'
WIDTH, HEIGHT = 1280, 720
ROW_DIST, EYE = 350.0, 165.0
R = {'ok': True, 'errors': [], 'frames': [], 'displays': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'plan': None,
     't_first': None, 'd': {}, 'nuke': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def log(*a):
    print('PU_LIVE_CAPTURE', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def V(t):
    return u.Vector(t[0], t[1], t[2])


def cam_look(loc, target, fov):
    rot = u.MathLibrary.find_look_at_rotation(V(loc), V(target))
    S['cam'].set_actor_location_and_rotation(V(loc), rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


def toward_start(p):
    dx, dy = S['start_loc'][0] - p[0], S['start_loc'][1] - p[1]
    d = math.hypot(dx, dy) or 1.0
    return dx / d, dy / d


def view_row():
    ps = [S['d'][k]['loc'] for k in S['d']]
    c = (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps), sum(p[2] for p in ps) / len(ps))
    f = toward_start(c)
    cam_look((c[0] + f[0] * ROW_DIST, c[1] + f[1] * ROW_DIST, c[2] + EYE), (c[0], c[1], c[2] + 70), 70)


def view_start():
    """From the player start itself at eye height, looking at the row (what the owner sees on Play)."""
    ps = [S['d'][k]['loc'] for k in S['d']]
    c = (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps), sum(p[2] for p in ps) / len(ps))
    st = S['start_loc']
    cam_look((st[0], st[1], c[2] + EYE), (c[0], c[1], c[2] + 60), 80)


def view_item(key, dist, height, aim, fov):
    p = S['d'][key]['loc']
    f = toward_start(p)
    side = (-f[1], f[0])
    a = math.radians(-14)      # a little off-axis
    d = (f[0] * math.cos(a) + side[0] * math.sin(a), f[1] * math.cos(a) + side[1] * math.sin(a))
    cam_look((p[0] + d[0] * dist, p[1] + d[1] * dist, p[2] + height), (p[0], p[1], p[2] + aim), fov)


def capture(name):
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    life = S['nuke'].get_life_time()
    R['frames'].append({'file': str(fn), 'life': round(life, 3), 'loop': S['nuke'].get_loop_index(),
                        'warning': round(S['nuke'].get_warning_amount(), 3), 'beat_hz': round(S['nuke'].get_beat_hz(), 3)})
    log('frame', fn.name, 'life %.2f' % life)


def fx_state(tag):
    """Which of the Nuke's Niagara pool components are active (evaluation note in capture.json)."""
    out = []
    for c in S['nuke'].get_components_by_class(u.NiagaraComponent):
        a = c.get_asset()
        out.append((c.get_name(), a.get_name() if a else None, bool(c.is_active())))
    R.setdefault('fx_state', {})[tag] = out
    log('fx', tag, [x for x in out if x[2]])


def puff_dump(tag, what='PopPuff'):
    """Active Niagara effects of one kind right now: counts (and, CPU sims, the first particle's attributes)."""
    rep = u.HoverAuthoring.inspect_active_effects(what)
    R.setdefault('puff', {})['%s %s' % (what, tag)] = rep.splitlines()
    log('fxdump', what, tag, [x.strip() for x in rep.splitlines() if 'particles=' in x or 'age=' in x])


def find_displays():
    for a in u.GameplayStatics.get_all_actors_with_tag(world(), TAG):
        key = a.get_actor_label().split()[-1] if hasattr(a, 'get_actor_label') else a.get_name()
        l = a.get_actor_location()
        S['d'][key] = {'loc': (l.x, l.y, l.z), 'actor': a}
    S['nuke'] = S['d']['Nuke']['actor']
    R['displays'] = {k: v['loc'] for k, v in S['d'].items()}
    vis = {}
    for k, v in S['d'].items():
        comps = {c.get_name(): c for c in v['actor'].get_components_by_class(u.SceneComponent)}
        vis[k] = {n: bool(comps[n].is_visible()) for n in ('ItemMesh', 'NeonSign') if n in comps}
        vis[k]['life'] = round(v['actor'].get_life_time(), 2)
    R['visible_at_start'] = vis
    sched = [(round(e.time, 3), e.kind, e.count) for e in S['nuke'].get_schedule()]
    R['nuke_schedule'] = sched
    log('displays', R['displays'])


def build_plan_fix():
    sched = R['nuke_schedule']
    pop = next(t for t, k, c in sched if k == 2 and t > 7.0)
    burst = next(t for t, k, c in sched if k == 1 and t > 7.0)
    P = [(burst + .03, lambda: puff_dump('+0.03', 'Spark')), (burst + .2, lambda: puff_dump('+0.2', 'Spark')),
         (burst + .5, lambda: puff_dump('+0.5', 'Spark')),
         (pop + .02, lambda: puff_dump('+0.02')), (pop + .12, lambda: puff_dump('+0.12', 'PopSparks')),(4.6, view_start), (5.0, lambda: capture('row_05_start')),
         (5.4, lambda: view_item('MaxAmmo', 290, 120, 88, 50)), (5.8, lambda: capture('maxammo_close')),
         (pop - .4, lambda: view_item('Nuke', 140, 85, 50, 50)), (pop + .04, lambda: capture('nuke_pop_a')),
         (pop + .3, lambda: capture('nuke_pop_0_3')), (pop + .6, lambda: capture('nuke_pop_0_6')),
         (pop + .65, lambda: fx_state('pop+0.65')),
         (27.1, lambda: view_item('Nuke', 140, 85, 50, 50)), (27.5, lambda: capture('nuke_27_5')),
         (27.8, lambda: view_item('Medkit', 290, 120, 88, 50)), (28.2, lambda: capture('medkit_28_2')),
         (28.5, lambda: view_item('Nuke', 140, 85, 50, 50)), (28.9, lambda: capture('nuke_28_9')),
         (29.2, finish)]
    R['plan_times'] = {'pop': pop, 'burst': burst}
    return sorted(P, key=lambda x: x[0])


def build_plan():
    if PLAN == 'fix':
        return build_plan_fix()
    sched = R['nuke_schedule']
    burst = next(t for t, k, c in sched if k == 1 and t > 7.6)
    pop = next(t for t, k, c in sched if k == 2 and t > burst + 1.2)
    P = [(4.6, view_row), (5.0, lambda: capture('row_05')),
         (5.2, lambda: view_item('Medkit', 290, 120, 88, 50)), (5.6, lambda: capture('medkit_close')),
         (5.8, lambda: view_item('MaxAmmo', 290, 120, 88, 50)), (6.2, lambda: capture('maxammo_close')),
         (6.4, lambda: view_item('Nuke', 140, 85, 50, 50)), (6.8, lambda: capture('nuke_close')),
         (burst - .4, lambda: view_item('Nuke', 140, 85, 50, 50)), (burst + .07, lambda: capture('nuke_burst_a')),
         (burst + .3, lambda: capture('nuke_burst_b')),
         (pop - .4, lambda: view_item('Nuke', 140, 85, 50, 50)), (pop + .04, lambda: capture('nuke_pop_a')),
         (pop + .2, lambda: capture('nuke_pop_b')), (pop + .25, lambda: fx_state('pop+0.25')),
         (14.6, view_row), (15.0, lambda: capture('row_15')),
         (26.6, view_row), (27.0, lambda: capture('row_27')),
         (27.3, lambda: view_item('Nuke', 140, 85, 50, 50)), (27.7, lambda: capture('nuke_27_7')),
         (27.8, lambda: view_item('Medkit', 290, 120, 88, 50)), (28.2, lambda: capture('medkit_28_2')),
         (28.5, lambda: view_item('Nuke', 140, 85, 50, 50)), (28.9, lambda: capture('nuke_28_9')),
         (29.1, view_row), (29.5, lambda: capture('row_29_5')), (29.7, finish)]
    R['plan_times'] = {'burst': burst, 'pop': pop}
    return sorted(P, key=lambda x: x[0])


def finish():
    if S['end']:
        return
    CAPTURE_JSON.write_text(json.dumps(R, indent=1, default=str))
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def tick(dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                CAPTURE_JSON.write_text(json.dumps(R, indent=1, default=str))
                log('DONE frames=%d errors=%d' % (len(R['frames']), len(R['errors'])))
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 900:
            raise RuntimeError('capture timeout')
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
        if not pc:
            return
        t = u.GameplayStatics.get_time_seconds(w)
        if S['pc'] is None:
            S['pc'] = pc
            S['t_first'] = t
            return
        if S['cam'] is None:
            if t - S['t_first'] < 2.0:
                return
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500),
                                                                                       rotation=u.Rotator()))
            S['cam'].camera_component.set_editor_property('constrain_aspect_ratio', False)
            ps = u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart)
            p = ps[0].get_actor_location() if ps else u.Vector(271, 5241, 162)
            S['start_loc'] = (p.x, p.y, p.z)
            pawn = pc.get_controlled_pawn()
            if pawn:
                pawn.set_actor_hidden_in_game(True)
            find_displays()
            S['plan'] = build_plan()
            log('plan', R['plan_times'], 'life now %.2f' % S['nuke'].get_life_time())
            return
        life = S['nuke'].get_life_time()
        if S['nuke'].get_loop_index() > 0:
            raise RuntimeError('missed the first life (life clock wrapped)')
        while S['plan'] and life >= S['plan'][0][0]:
            _, fn = S['plan'].pop(0)
            fn()
            break        # one action per frame (camera moves need a frame before a capture)
    except Exception:  # noqa: BLE001
        R['errors'].append(traceback.format_exc())
        R['ok'] = False
        log('ERROR', R['errors'][-1][-800:])
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
