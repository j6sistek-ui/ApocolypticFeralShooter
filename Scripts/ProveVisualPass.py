"""ProveVisualPass.py - stills for the visual pass: Vexa from the survival camera with the fill light off / on / strong,
the aimed over-the-shoulder view, and close-ups of the held guns, at 1920x1080.

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveVisualPass.py
      -RenderOffscreen -unattended -nosplash -ResX=1920 -ResY=1080
      "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.EffectsQuality 1, sg.TextureQuality 3"

GPU budget (RULES.md): 1080p is above the usual 720p capture size; run it only when the owner is not gaming, or check the
`vram_mb` column the receipt records from nvidia-smi at every still (the run aborts a still series above VRAM_LIMIT_MB,
default 6000). sg.TextureQuality 3 keeps texture mips at full detail so the texture pass is visible.

PIE L_NYC_Survival, test input isolated, fixed 1/30 s step, zombies destroyed (one zombie's mesh lighting channels are
recorded first: the fill must not reach channel-0-only meshes). Sequence:
  1. Vexa still at the start, survival camera (the pawn's own view target, nothing overridden), 4 s for streaming.
  2. `HoverFillLight 0` -> vexa_fill_off, `HoverFillLight 1 <data intensity>` -> vexa_fill_on,
     `HoverFillLight 1 <2x>` -> vexa_fill_strong, back to the data intensity.
  3. Aim (right mouse held) -> vexa_aim_fill_on / vexa_aim_fill_off.
  4. Gun close-up from a camera actor 45 cm off the held gun's right side, fill on and off; then quickbar slot 2 and the
     same close-ups if it holds a different gun mesh.
Every still: HoverAuthoring.measure_frame_luminance (central 35 %) and VRAM used. Receipt also lists the fill light's
settings and lighting channels, the channels of every skeletal / static mesh on the pilot, the survival camera position
in capsule space and the log lines HOVER_FILL_LIGHT. Receipt D:/AFS_Comparisons/VisualPass_20261031/proof.json
(PROOF_OUT overrides). Changes only the unsaved Play world.
"""
import json
import math
import os
import re
import subprocess
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/VisualPass_20261031')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1920, 1080
VRAM_LIMIT_MB = int(os.environ.get('VRAM_LIMIT_MB') or 6000)
TIMEOUT = 900
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'stills': [], 'fill': {}, 'channels': {}, 'log': {},
     'summary': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'cam': None, 'zombies_removed': 0, 'hold': set(), 'snap': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'
DA = u.load_asset('/Game/HoverPrototype/DA_HoverPilot')


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


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def vram_mb():
    try:
        out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=5).stdout
        return int(out.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None


def channels(prim):
    try:
        lc = prim.get_editor_property('lighting_channels')
        return [bool(lc.get_editor_property('channel0')), bool(lc.get_editor_property('channel1')),
                bool(lc.get_editor_property('channel2'))]
    except Exception as e:  # noqa: BLE001
        return 'err: %s' % str(e)[:60]


def fill_light(p):
    for c in p.get_components_by_class(u.PointLightComponent):
        if c.get_name() == 'SurvivalFillLight':
            return c
    return None


def data_intensity():
    try:
        return float(DA.get_editor_property('survival_fill_light_intensity'))
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('survival_fill_light_intensity: %s (patch not built?)' % str(e)[:80])
        return 2.5


def record_zombie_channels(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls or 'zombie' in R['channels']:
        return
    zs = u.GameplayStatics.get_all_actors_of_class(w, cls)
    if zs:
        meshes = zs[0].get_components_by_class(u.SkeletalMeshComponent)
        R['channels']['zombie'] = {'actor': zs[0].get_name(), 'meshes': {m.get_name(): channels(m) for m in meshes}}


def clear_zombies(w):
    record_zombie_channels(w)
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls:
        return
    for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
        z.destroy_actor()
        S['zombies_removed'] += 1


# ------------------------------------------------------------------------------------------------------- stills
def snap_pawn_view(name):
    S['pc'].set_view_target_with_blend(pawn(), 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    S['snap'] = {'file': OUT / (name + '.png'), 'ticks': 2, 'meta': {'view': 'survival camera'}}


def snap_gun(name):
    p = pawn()
    comp = None
    for prop in ('world_gun_skel', 'world_gun'):
        try:
            c = p.get_editor_property(prop)
            mesh = c.get_editor_property('skeletal_mesh_asset' if prop.endswith('skel') else 'static_mesh')
            if c and mesh and c.is_visible():
                comp = (c, mesh)
                break
        except Exception as e:  # noqa: BLE001
            R['api_errors'].append('%s: %s' % (prop, str(e)[:80]))
    if not comp:
        R['api_errors'].append('no visible held gun for %s' % name)
        return None
    c, mesh = comp
    fwd, right, up = c.get_forward_vector(), c.get_right_vector(), c.get_up_vector()
    center = c.get_world_location() + fwd * 18
    cam_loc = center + right * 45 + up * 8 - fwd * 6
    S['cam'].set_actor_location_and_rotation(cam_loc, u.MathLibrary.find_look_at_rotation(cam_loc, center), False, False)
    try:
        S['cam'].get_editor_property('camera_component').set_field_of_view(40.0)
    except Exception:  # noqa: BLE001
        pass
    S['pc'].set_view_target_with_blend(S['cam'], 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    S['snap'] = {'file': OUT / ('%s_%s.png' % (name, mesh.get_name())), 'ticks': 2,
                 'meta': {'view': 'gun close-up', 'gun_mesh': mesh.get_path_name()}}
    return mesh.get_name()


def snap_tick():
    sn = S['snap']
    if not sn:
        return False
    if sn['ticks'] > 0:
        sn['ticks'] -= 1
        return True
    used = vram_mb()
    if used is not None and used > VRAM_LIMIT_MB:
        R['errors'].append('VRAM %d MB above %d MB: still %s skipped' % (used, VRAM_LIMIT_MB, sn['file'].name))
        S['snap'] = None
        return True
    u.HoverAuthoring.capture_world_frame(str(sn['file']))
    row = dict(sn['meta'])
    row.update({'file': sn['file'].name, 'vram_mb': used})
    try:
        row['luminance'] = u.HoverAuthoring.measure_frame_luminance(str(sn['file']), .35)
    except Exception as e:  # noqa: BLE001
        row['luminance'] = 'err: %s' % str(e)[:80]
    lt = fill_light(pawn())
    row['fill'] = {'visible': lt.is_visible(), 'intensity': lt.get_editor_property('intensity')} if lt else None
    R['stills'].append(row)
    S['snap'] = None
    save()
    return True


# ------------------------------------------------------------------------------------------------------- plan
def fill(mode, intensity=None):
    console('HoverFillLight %d%s' % (mode, '' if intensity is None else ' %.2f' % intensity))


def record_setup(p):
    lt = fill_light(p)
    if lt:
        R['fill'] = {'intensity': lt.get_editor_property('intensity'),
                     'units': str(lt.get_editor_property('intensity_units')),
                     'radius': lt.get_editor_property('attenuation_radius'),
                     'source_radius': lt.get_editor_property('source_radius'),
                     'color': str(lt.get_editor_property('light_color')),
                     'cast_shadows': lt.get_editor_property('cast_shadows'),
                     'indirect': lt.get_editor_property('indirect_lighting_intensity'),
                     'channels': channels(lt), 'relative_location': vec(lt.get_editor_property('relative_location'))}
    else:
        R['errors'].append('SurvivalFillLight component not found (patch not applied / built?)')
    R['channels']['pilot'] = {c.get_name(): channels(c) for c in
                              list(p.get_components_by_class(u.SkeletalMeshComponent)) +
                              list(p.get_components_by_class(u.StaticMeshComponent))}
    try:
        cam = p.get_editor_property('review_camera')
        loc = cam.get_world_location()
        R['setup']['survival_camera_capsule_space'] = vec(
            u.MathLibrary.inverse_transform_location(p.get_actor_transform(), loc))
        R['setup']['survival_camera_fov'] = cam.get_editor_property('field_of_view')
        if lt:
            R['setup']['fill_to_camera_cm'] = round((lt.get_world_location() - loc).length(), 1)
            R['setup']['fill_to_chest_cm'] = round(
                (lt.get_world_location() - (p.get_actor_location() + u.Vector(0, 0, 40))).length(), 1)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('review_camera: %s' % str(e)[:100])
    try:
        R['setup']['viewport'] = str(u.HoverAuthoring.get_playtest_viewport_size())
    except Exception:  # noqa: BLE001
        pass


def plan():
    base = data_intensity()
    R['setup']['data_intensity'] = base
    q = [
        (4.0, lambda t: fill(0)),
        (0.6, lambda t: snap_pawn_view('vexa_fill_off')),
        (0.4, lambda t: fill(1, base)),
        (0.6, lambda t: snap_pawn_view('vexa_fill_on')),
        (0.4, lambda t: fill(1, base * 2)),
        (0.6, lambda t: snap_pawn_view('vexa_fill_strong')),
        (0.4, lambda t: fill(1, base)),
        (0.2, lambda t: key('RightMouseButton', True)),
        (1.2, lambda t: snap_pawn_view('vexa_aim_fill_on')),
        (0.4, lambda t: fill(0)),
        (0.6, lambda t: snap_pawn_view('vexa_aim_fill_off')),
        (0.4, lambda t: fill(1, base)),
        (0.6, lambda t: S.__setitem__('gun1', snap_gun('gun_closeup_fill_on'))),
        (0.4, lambda t: fill(0)),
        (0.6, lambda t: snap_gun('gun_closeup_fill_off')),
        (0.4, lambda t: (fill(1, base), key('RightMouseButton', False))),
        (0.3, lambda t: (key('Two', True), key('Two', False))),
        (1.5, lambda t: key('RightMouseButton', True)),
        (1.2, lambda t: second_gun()),
        (0.6, lambda t: key('RightMouseButton', False)),
        (0.3, lambda t: (key('One', True), key('One', False))),
        (1.0, lambda t: finish()),
    ]
    S['queue'] = q


def second_gun():
    p = pawn()
    try:
        mesh = p.get_editor_property('world_gun_skel').get_editor_property('skeletal_mesh_asset')
        name = mesh.get_name() if mesh else None
    except Exception:  # noqa: BLE001
        name = None
    R['setup']['slot2_gun'] = name
    if name and name != S.get('gun1'):
        snap_gun('gun_closeup_slot2_fill_on')
    else:
        R['setup']['slot2_note'] = 'slot 2 holds the same mesh or none; no second close-up'


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
    if Path(path).exists():
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
        R['log']['fill'] = [l[-200:] for l in lines if 'HOVER_FILL_LIGHT' in l][-12:]
        R['log']['texture_warnings'] = [l[-200:] for l in lines if 'LogTexture' in l and 'Warning' in l][-10:]


def lum_value(s):
    # HoverAuthoring.measure_frame_luminance returns JSON: {"ok", "width", "height", "central_fraction", "mean_luma", ...}
    try:
        return float(json.loads(s)['mean_luma'])
    except Exception:  # noqa: BLE001
        return None


def summarise():
    by = {r['file'].split('.')[0]: r for r in R['stills']}
    off, on, strong = (lum_value(by.get(k, {}).get('luminance')) for k in ('vexa_fill_off', 'vexa_fill_on', 'vexa_fill_strong'))
    R['summary'] = {'stills': len(R['stills']), 'lum_off': off, 'lum_on': on, 'lum_strong': strong,
                    'lum_gain_on_pct': round(100 * (on - off) / off, 1) if off and on else None,
                    'vram_peak_mb': max([r['vram_mb'] for r in R['stills'] if r.get('vram_mb')] or [0]) or None,
                    'fill_channels': R['fill'].get('channels'), 'zombies_removed': S['zombies_removed']}
    zombie = R['channels'].get('zombie', {}).get('meshes', {})
    R['summary']['zombie_on_fill_channel'] = any(isinstance(c, list) and c[1] for c in zombie.values()) if zombie else None
    R['ok'] = bool(R['fill']) and R['fill'].get('channels') == [False, True, False] and len(R['stills']) >= 6 and \
        not R['summary']['zombie_on_fill_channel'] and not R['errors']


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
                    print('PROVE_VISUAL_DONE', json.dumps(R['summary'], default=str), flush=True)
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
            for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages',
                        'r.Streaming.FullyLoadUsedTextures 1'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            R['setup'].update({'pawn': p.get_class().get_name(), 'start': vec(p.get_actor_location()),
                               'vram_at_start_mb': vram_mb()})
            record_setup(p)
            save()
            plan()
            S['next'] = t + S['queue'][0][0]
            return
        if snap_tick():
            return
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            _, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_VISUAL_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
