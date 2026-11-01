"""CapturePerkMachines.py - rendered stills of the perk machines standing in NYC Exploration (GPU, -RenderOffscreen, PIE).

Same harness as Scripts/PreviewPowerUpStyles2.py (boot, fixed-step PIE, camera actor, HoverAuthoring.capture_world_frame).
Finds the machines by the tag Scripts/ImportPerkMachines.py gives them (AFS_PerkMachineTrial) and shoots:
  spawn_view       from the player start at eye height, what the owner sees after spawning
  <machine>_34     each machine three-quarter, full height
  <machine>_close  the glowing part close (Lifeblood core, Bioreactor tube) at two moments 0.7 s apart
                   (_a/_b: the heartbeat pulse and the shaft spin should differ)
  Headhunter (2026-11-01, Scripts/ImportHeadhunter.py): Headhunter_34, Headhunter_tube_a/_b (1 s apart, natural
                   schedule), Headhunter_drop (waits for a drop in free fall), Headhunter_shot_0p06/_0p4/_3 (after
                   AHoverBloodTube.TriggerHeadshot: spurt, splash + fresh splat, splat running down). The harness only
                   triggers; all motion is the actor's own (C++ tick, materials, Niagara).
Env: PERK_CAPTURE_ONLY=Headhunter (only that machine's shots), PERK_CAPTURE_OUT=<dir> (default below).
Out: D:/AFS_Comparisons/PerkMachines_20261031/Unreal/stills/*.png + capture.json
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
TAG = 'AFS_PerkMachineTrial'
OUT = Path(os.environ.get('PERK_CAPTURE_OUT', 'D:/AFS_Comparisons/PerkMachines_20261031/Unreal'))
ONLY = os.environ.get('PERK_CAPTURE_ONLY', '')
STILLS = OUT / 'stills'
STILLS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
R = {'ok': True, 'errors': [], 'frames': [], 'machines': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'm': {}, 'tube': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def log(*a):
    print('PERK_CAPTURE', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def V(t):
    return u.Vector(t[0], t[1], t[2])


def cam_look(loc, target, fov):
    rot = u.MathLibrary.find_look_at_rotation(V(loc), V(target))
    S['cam'].set_actor_location_and_rotation(V(loc), rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


def machine_frame(name):
    """Origin, facing unit vector (towards the front) and right vector of a machine's body actor."""
    m = S['m'][name]
    loc, yaw = m['loc'], m['yaw'] + m['front_mesh_yaw']
    f = (math.cos(math.radians(yaw)), math.sin(math.radians(yaw)))
    return loc, f, (-f[1], f[0])


def view_machine(name, dist, height, aim_z, side_deg, fov):
    loc, f, rt = machine_frame(name)
    a = math.radians(side_deg)
    d = (f[0] * math.cos(a) + rt[0] * math.sin(a), f[1] * math.cos(a) + rt[1] * math.sin(a))
    cam_look((loc[0] + d[0] * dist, loc[1] + d[1] * dist, loc[2] + height), (loc[0], loc[1], loc[2] + aim_z), fov)


def capture(name):
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    R['frames'].append(str(fn))
    log('frame', fn.name)


def step(delay, fn):
    S['queue'].append((delay, fn))


def find_machines():
    for a in u.GameplayStatics.get_all_actors_with_tag(world(), TAG):
        label = a.get_actor_label() if hasattr(a, 'get_actor_label') else a.get_name()
        parts = label.split()
        if len(parts) >= 5 and parts[-1] in ('Body', 'Frame'):
            l, r = a.get_actor_location(), a.get_actor_rotation()
            S['m'][parts[-2]] = {'loc': (l.x, l.y, l.z), 'yaw': r.yaw, 'front_mesh_yaw': 90.0}
    tubes = u.GameplayStatics.get_all_actors_of_class(world(), u.HoverBloodTube) if hasattr(u, 'HoverBloodTube') else []
    S['tube'] = tubes[0] if tubes else None
    R['machines'] = S['m']
    log('machines', json.dumps(S['m']), 'tube', bool(S['tube']))


def tube_state():
    st = json.loads(S['tube'].describe_state()) if S['tube'] else {}
    try:
        st['niagara'] = u.HoverAuthoring.inspect_active_effects('NS_HH')[:600]
    except Exception as ex:  # noqa: BLE001
        st['niagara'] = str(ex)
    return st


def plan():
    step(0.1, lambda t: find_machines())
    ps = u.GameplayStatics.get_all_actors_of_class(world(), u.PlayerStart)
    p = ps[0].get_actor_location() if ps else u.Vector(271, 5241, 162)

    def spawn_view(t):
        mids = [S['m'][k]['loc'] for k in S['m']]
        cx = sum(m[0] for m in mids) / len(mids)
        cy = sum(m[1] for m in mids) / len(mids)
        cz = sum(m[2] for m in mids) / len(mids)
        cam_look((p.x, p.y, p.z + 70), (cx, cy, cz + 110), 80)
    step(1.0, spawn_view)
    step(2.0, lambda t: capture('spawn_view'))
    for name, aim, dist in (('Lifeblood', 92.0, 170.0), ('Bioreactor', 112.0, 240.0)):
        if ONLY and name != ONLY:
            continue
        step(0.1, lambda t, n=name: view_machine(n, 360, 150, 110, 32, 55))
        step(1.0, lambda t, n=name: capture(n + '_34'))
        step(0.1, lambda t, n=name, a=aim, d=dist: view_machine(n, d, a + 25, a, 12, 50))
        step(1.0, lambda t, n=name: capture(n + '_close_a'))
        step(0.7, lambda t, n=name: capture(n + '_close_b'))
        if name == 'Lifeblood':   # 2026-11-01: the repainted PERK MACHINE subtitle, straight on
            step(0.1, lambda t, n=name: view_machine(n, 95, 135, 133, 0, 40))
            step(1.0, lambda t, n=name: capture(n + '_sign'))
    if not ONLY or ONLY == 'Headhunter':
        plan_headhunter()
    step(0.3, lambda t: finish())


def plan_headhunter():
    def has():
        return 'Headhunter' in S['m'] and S['tube'] is not None

    def shot(n):
        if has():
            capture(n)
            R.setdefault('tube_states', {})[n] = tube_state()
    step(0.1, lambda t: has() and view_machine('Headhunter', 360, 150, 110, 32, 55))
    step(1.0, lambda t: shot('Headhunter_34'))
    step(0.1, lambda t: has() and view_machine('Headhunter', 125, 132, 128, 8, 42))
    step(1.0, lambda t: shot('Headhunter_tube_a'))
    step(1.0, lambda t: shot('Headhunter_tube_b'))
    # a drop from the cap lip (front-left, the longest fall) and one from the jaw; shoot when one is in free fall
    step(0.1, lambda t: has() and (S['tube'].trigger_drop(2), S['tube'].trigger_drop(0)))
    step(0.1, lambda t: wait_fall('Headhunter_drop'))
    step(0.2, lambda t: has() and S['tube'].trigger_headshot())
    step(0.06, lambda t: shot('Headhunter_shot_0p06'))
    step(0.34, lambda t: shot('Headhunter_shot_0p4'))
    step(2.6, lambda t: shot('Headhunter_shot_3'))
    step(0.1, lambda t: has() and view_machine('Headhunter', 230, 140, 125, 30, 45))
    step(0.5, lambda t: shot('Headhunter_tube_side'))
    step(0.1, lambda t: has() and view_machine('Headhunter', 110, 185, 185, 0, 45))
    step(1.0, lambda t: shot('Headhunter_sign'))
    step(0.1, lambda t: has() and view_machine('Headhunter', 110, 95, 85, 0, 45))
    step(1.0, lambda t: shot('Headhunter_panel'))


def wait_fall(name, tries=[0]):
    """Re-queues itself each step until a drop is in free fall well above the pool (then captures), at most ~3 s."""
    st = tube_state()
    falling = [d for d in st.get('drops', []) if d['state'] == 2 and d['t'] >= 0.05 and d['local'][2] > 126]
    tries[0] += 1
    if falling or tries[0] > 90:
        capture(name)
        R.setdefault('tube_states', {})[name] = st
        return
    S['queue'].insert(0, (0.033, lambda t: wait_fall(name)))


def finish():
    if S['end']:
        return
    (OUT / 'capture.json').write_text(json.dumps(R, indent=1, default=str))
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
                    (OUT / 'capture.json').write_text(json.dumps(R, indent=1, default=str))
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
            if t - S['t_first'] < 3.0:
                return
            u.HoverAuthoring.set_playtest_fixed_step(True)
            for cmd in ('r.Streaming.FullyLoadUsedTextures 1', 'r.Streaming.PoolSize 6000', 'r.ScreenPercentage 100'):
                u.SystemLibrary.execute_console_command(w, cmd)   # stills right after load showed low texture mips
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500),
                                                                                       rotation=u.Rotator()))
            S['cam'].camera_component.set_editor_property('constrain_aspect_ratio', False)
            plan()
            S['next'] = t
            return
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:  # noqa: BLE001
        R['errors'].append(traceback.format_exc())
        R['ok'] = False
        log('ERROR', R['errors'][-1][-800:])
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
