"""CapturePerkMachines.py - rendered stills of the perk machines standing in NYC Exploration (GPU, -RenderOffscreen, PIE).

Same harness as Scripts/PreviewPowerUpStyles2.py (boot, fixed-step PIE, camera actor, HoverAuthoring.capture_world_frame).
Finds the machines by the tag Scripts/ImportPerkMachines.py gives them (AFS_PerkMachineTrial) and shoots:
  spawn_view       from the player start at eye height, what the owner sees after spawning
  <machine>_34     each machine three-quarter, full height
  <machine>_close  the glowing part close (Lifeblood core, Bioreactor tube) at two moments 0.7 s apart
                   (_a/_b: the heartbeat pulse and the shaft spin should differ)
Out: D:/AFS_Comparisons/PerkMachines_20261031/Unreal/stills/*.png + capture.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -RenderOffscreen -nosplash -ResX=1280 -ResY=720 -stdout
       -FullStdOutLogOutput -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=<this>
"""
import json
import math
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Explore'
TAG = 'AFS_PerkMachineTrial'
OUT = Path('D:/AFS_Comparisons/PerkMachines_20261031/Unreal')
STILLS = OUT / 'stills'
STILLS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
R = {'ok': True, 'errors': [], 'frames': [], 'machines': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'm': {}}
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
    R['machines'] = S['m']
    log('machines', json.dumps(S['m']))


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
        step(0.1, lambda t, n=name: view_machine(n, 360, 150, 110, 32, 55))
        step(1.0, lambda t, n=name: capture(n + '_34'))
        step(0.1, lambda t, n=name, a=aim, d=dist: view_machine(n, d, a + 25, a, 12, 50))
        step(1.0, lambda t, n=name: capture(n + '_close_a'))
        step(0.7, lambda t, n=name: capture(n + '_close_b'))
    step(0.3, lambda t: finish())


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
