"""PreviewGrenades.py - photograph the four horror grenades in L_NYC_Survival (GPU, -RenderOffscreen).

Spawns the four imported grenade meshes in a row in front of Vexa at hand size (0.25 of the Tripo import, ~12 cm),
fills the caged one (the owner's "Blood Bomb") with a blood-magic core from sA_BloodMagic_1, and captures a wide
shot plus one close-up per grenade and two core variants. Boot / tick / capture pattern copied from CaptureGuns.py.
Receipt: D:/AFS_Comparisons/Grenades_20261031/preview.json, stills beside it.
Usage: UnrealEditor-Cmd.exe AFS.uproject -ExecutePythonScript=Scripts/PreviewGrenades.py -RenderOffscreen -ResX=1280 -ResY=720 ...
"""
import json
import os
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path('D:/AFS_Comparisons/Grenades_20261031')
STILLS = OUT / 'stills'
STILLS.mkdir(parents=True, exist_ok=True)
_res = os.environ.get('CAPTURE_RES', '1280x720').lower().split('x')
WIDTH, HEIGHT = int(_res[0]), int(_res[1])
GRENADES = [
    ('/Game/HoverPrototype/Props/Grenades/Horror_01_Biohazard/SM_Horror_01_Biohazard', 'Biohazard'),
    ('/Game/HoverPrototype/Props/Grenades/Horror_02_Cage_BloodBomb/SM_Horror_02_Cage_BloodBomb', 'BloodBomb'),
    ('/Game/HoverPrototype/Props/Grenades/Horror_03_Teeth/SM_Horror_03_Teeth', 'Teeth'),
    ('/Game/HoverPrototype/Props/Grenades/Horror_04_Skull/SM_Horror_04_Skull', 'Skull'),
]
# OptimizedEmissive variants (the pack also ships AdvShaded ones): the owner's rule is "not if it costs a lot".
# 2026-10-31 03:30: both systems are authored at character scale and ignore the actor's 0.12 scale, so the first run
# filled every frame with red haze; GRENADE_CORES=0 captures the clean row, the core needs a grenade-scale variant.
CORES = [] if os.environ.get('GRENADE_CORES', '1') == '0' else [
    '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_SmokySphere', '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_Aura_1']
SCALE = 0.25
SPACING = 22.0  # cm between grenades in the row
R = {'ok': True, 'errors': [], 'frames': [], 'setup': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'actors': [], 'core': None, 'core_index': 0, 'done': False, 't_first': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def log(*a):
    print('GRENADE_PREVIEW', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def find_core_asset(path):
    for p in (path, path + '.' + path.split('/')[-1]):
        a = u.load_asset(p)
        if a:
            return a
    # the pack may keep the systems in a subfolder; search by name
    name = path.split('/')[-1]
    for ad in u.AssetRegistryHelpers.get_asset_registry().get_assets_by_path('/Game/sA_BloodMagic_1', True):
        if str(ad.asset_name) == name:
            return ad.get_asset()
    return None


def spawn_row(p):
    base = p.get_actor_location()
    fwd = p.get_actor_forward_vector()
    right = p.get_actor_right_vector()
    centre = base + fwd * 120.0 + u.Vector(0, 0, 20.0)
    S['centre'] = centre
    for i, (path, label) in enumerate(GRENADES):
        mesh = u.load_asset(path)
        if not mesh:
            R['errors'].append('missing mesh ' + path)
            continue
        loc = centre + right * ((i - 1.5) * SPACING)
        # glTF Y-up: the grenades import lying along X; pitch 90 stands them up (confirmed in the 03:35 row capture).
        tr = u.Transform(location=loc, rotation=u.Rotator(90.0, p.get_actor_rotation().yaw + 180.0, 0), scale=u.Vector(SCALE, SCALE, SCALE))
        a = u.HoverAuthoring.spawn_playtest_actor(u.StaticMeshActor, tr)
        a.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
        a.static_mesh_component.set_static_mesh(mesh)
        a.set_actor_scale3d(u.Vector(SCALE, SCALE, SCALE))
        S['actors'].append((label, a, loc))
        log('spawned', label, [round(loc.x, 1), round(loc.y, 1), round(loc.z, 1)])
    R['setup']['row'] = [(l, [round(v.x, 1), round(v.y, 1), round(v.z, 1)]) for l, _, v in S['actors']]


def set_core(index):
    if S['core']:
        S['core'].destroy_actor()
        S['core'] = None
    if index >= len(CORES):
        return
    sysasset = find_core_asset(CORES[index])
    if not sysasset:
        R['errors'].append('core system not found: ' + CORES[index])
        return
    cage = next((a for l, a, _ in S['actors'] if l == 'BloodBomb'), None)
    if not cage:
        return
    loc = cage.get_actor_location() + u.Vector(0, 0, 2.0)
    na = u.HoverAuthoring.spawn_playtest_actor(u.NiagaraActor, u.Transform(location=loc, rotation=u.Rotator(), scale=u.Vector(0.12, 0.12, 0.12)))
    na.niagara_component.set_asset(sysasset)
    na.niagara_component.set_world_scale3d(u.Vector(0.12, 0.12, 0.12))
    na.niagara_component.activate(True)
    S['core'] = na
    R['setup'].setdefault('cores', []).append(CORES[index])
    log('core', CORES[index])


def look_at(loc, target, fov):
    rot = u.MathLibrary.find_look_at_rotation(loc, target)
    S['cam'].set_actor_location_and_rotation(loc, rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


def capture(name):
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    R['frames'].append(fn.name)
    log('frame', fn.name)


def step(delay, fn):
    S['queue'].append((delay, fn))


def plan(p):
    fwd = p.get_actor_forward_vector()
    right = p.get_actor_right_vector()
    c = S['centre']
    # wide: from Vexa's side of the row, slightly above
    step(0.5, lambda t: look_at(c - fwd * 70 + u.Vector(0, 0, 18), c, 55))
    step(0.4, lambda t: capture('grenades_row_wide'))
    for i, (label, a, loc) in enumerate(S['actors']):
        step(0.1, lambda t, loc=loc: look_at(loc - fwd * 28 + right * 6 + u.Vector(0, 0, 8), loc + u.Vector(0, 0, 2), 40))
        step(0.4, lambda t, label=label: capture('grenade_%s_close' % label))
    # second core variant on the blood bomb
    bb = next((loc for l, a, loc in S['actors'] if l == 'BloodBomb'), c)
    step(0.1, lambda t: set_core(1))
    step(0.1, lambda t: look_at(bb - fwd * 28 + right * 6 + u.Vector(0, 0, 8), bb + u.Vector(0, 0, 2), 40))
    step(0.6, lambda t: capture('grenade_BloodBomb_close_core2'))
    step(0.1, lambda t: look_at(c - fwd * 70 + u.Vector(0, 0, 18), c, 55))
    step(0.4, lambda t: capture('grenades_row_wide_core2'))
    step(0.2, lambda t: finish())


def finish():
    if S['end']:
        return
    (OUT / 'preview.json').write_text(json.dumps(R, indent=1, default=str))
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
                    (OUT / 'preview.json').write_text(json.dumps(R, indent=1, default=str))
                    log('DONE frames=%d errors=%d' % (len(R['frames']), len(R['errors'])))
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 480:
            raise RuntimeError('preview timeout')
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
        p = pc.get_controlled_pawn()
        # keep the scene quiet: remove zombies as they spawn (same as CaptureGuns)
        for z in u.GameplayStatics.get_all_actors_of_class(w, u.Character):
            if z != p and 'Zomb' in z.get_class().get_name():
                z.destroy_actor()
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            spawn_row(p)
            set_core(0)
            plan(p)
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
        log('ERROR', R['errors'][-1][-600:])
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
