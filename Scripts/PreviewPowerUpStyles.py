"""PreviewPowerUpStyles.py - photograph the 14 power-up looks in L_PowerUpShowcase (GPU, -RenderOffscreen, PIE).

For each look (Scripts/PowerUpStyleRecipes.py) it spawns the medkit (left, red) and the nuke (right, orange-white) with
the look's props, lights and Niagara duplicates (made by Scripts/AuthorPowerUpStyles.py), runs the idle motion (spin,
bob, light flicker, beacon strobe, the nuke's ticking-bomb heartbeat), then captures a 3/4 shot at about 2.5 m and a
shot from 10 m. Looks listed in PU_PULSE_LOOKS also get three nuke pulse frames (rest / half / peak).
Boot / tick / capture pattern from Scripts/PreviewGrenades.py (camera actor + HoverAuthoring.capture_world_frame;
ReadPixels returns the previous frame, so every capture waits a few ticks after the camera moves).
Env: PU_LOOKS=1,2 (default all), PU_PULSE_LOOKS=4,14, PU_ROUND=r1 (output sub-folder), PU_EV=-1.0 (exposure bias),
PU_WARM=25 (seconds the warm-up overview holds so new shaders finish compiling).
Out: D:/AFS_Comparisons/PowerUps_20261031/Styles/stills/<round>/S<NN>_<Key>_{close,10m,pulse0..2}.png + preview.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -ExecutePythonScript=Scripts/PreviewPowerUpStyles.py -RenderOffscreen -nosplash ...
"""
import json
import math
import os
import random
import sys
import time
import traceback
from pathlib import Path

import unreal as u

sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import importlib  # noqa: E402

import PowerUpStyleRecipes as REC  # noqa: E402

importlib.reload(REC)

ROUND = os.environ.get('PU_ROUND', 'r1')
OUT = Path('D:/AFS_Comparisons/PowerUps_20261031/Styles')
STILLS = OUT / 'stills' / ROUND
STILLS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
ONLY = [int(x) for x in os.environ.get('PU_LOOKS', '').split(',') if x.strip()]
PULSE = [int(x) for x in os.environ.get('PU_PULSE_LOOKS', '').split(',') if x.strip()]
EV = float(os.environ.get('PU_EV', 'nan'))
WARM = float(os.environ.get('PU_WARM', '25'))
LOOKS = [lk for lk in REC.LOOKS if not ONLY or lk['n'] in ONLY]
ITEM_TURN = 22.0          # extra yaw so the items show a 3/4 face, not a flat front
NUKE_HZ = 1.25            # ticking-bomb heartbeat, rising to 3 Hz near detonation in game
NUKE_AMP = 0.12
R = {'ok': True, 'errors': [], 'frames': [], 'looks': {}, 'round': ROUND, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'live': [], 'freeze': False, 'pulse': None, 't': 0.0}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(REC.LEVEL), 'load_level failed'
F, RT = REC.view_basis()
# Front of the cleaned models is UE +Y (Blender -Y through glTF / Interchange); this yaw turns it to the camera.
FACE_YAW = REC.VIEW_YAW + 90.0


def log(*a):
    print('PU_PREVIEW', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def V(t):
    return u.Vector(t[0], t[1], t[2])


def lc(c, k=1.0):
    return u.LinearColor(c[0] * k, c[1] * k, c[2] * k, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# spawning one look

def spawn_sma(mesh, loc, rot, scale):
    a = u.HoverAuthoring.spawn_playtest_actor(u.StaticMeshActor, u.Transform(location=V(loc), rotation=rot, scale=V(scale)))
    c = a.static_mesh_component
    c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(mesh)
    a.set_actor_scale3d(V(scale))
    c.set_editor_property('cast_shadow', True)
    return a


def material(path):
    m = u.load_asset(path)
    if not m:
        R['errors'].append('missing material ' + path)
    return m


def apply_slots(actor, slots, look, key, el_name, item):
    comp = actor.static_mesh_component
    mids = []
    names = [str(n) for n in comp.get_material_slot_names()]
    for slot, spec in slots.items():
        path = spec[1] if spec[0] == 'asset' else REC.mi_path(look, key, el_name, slot)
        m = material(path)
        if not m:
            continue
        idx = slot if isinstance(slot, int) else (names.index(slot) if slot in names else -1)
        if idx < 0:
            R['errors'].append('%s: slot %s not on mesh (%s)' % (el_name, slot, names))
            continue
        comp.set_material(idx, m)
        if spec[0] != 'asset':
            mids.append(comp.create_dynamic_material_instance(idx, m))
    return mids


def rot_of(el, extra_yaw=0.0):
    r = el.get('rot', (0, 0, 0))
    return u.Rotator(roll=r[0], pitch=r[1], yaw=r[2] + REC.VIEW_YAW + extra_yaw)


def track(actor, base_loc, base_rot, base_scale, spin=0.0, bob=None, pulse=False, mids=None, kind='mesh', **kw):
    rec = {'actor': actor, 'loc': base_loc, 'rot': base_rot, 'scale': base_scale, 'spin': spin, 'bob': bob,
           'pulse': pulse, 'mids': mids or [], 'kind': kind, 'phase': random.random() * 6.28}
    rec.update(kw)
    S['live'].append(rec)
    return rec


def spawn_look(look, offset=(0.0, 0.0)):
    """offset = (fwd, right) cm in the view frame, used by the warm-up overview to spread looks out."""
    ox, oy = offset
    base = (F[0] * ox + RT[0] * oy, F[1] * ox + RT[1] * oy)

    def W(local, anchor_y):
        p = REC.view_to_world(local, anchor_y)
        return (p[0] + base[0], p[1] + base[1], p[2])

    for key in REC.ITEM_ORDER:
        item = REC.ITEMS[key]
        ay = item['y']
        spec = look['item']
        if not spec.get('hide'):
            mesh = u.load_asset(item['mesh'])
            hover = spec.get('hover', 0)
            loc = W((0, 0, hover), ay)
            rot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW + ITEM_TURN)
            a = spawn_sma(mesh, loc, rot, (1, 1, 1))
            mids = []
            if spec.get('material'):
                m = material(REC.mi_path(look, key, 'Item'))
                if m:
                    a.static_mesh_component.set_material(0, m)
                    mids.append(a.static_mesh_component.create_dynamic_material_instance(0, m))
            track(a, loc, rot, 1.0, spec.get('spin', 0), spec.get('bob'), item['pulse'], mids, 'item')
        for el in look['elements']:
            k = el['kind']
            if k == 'mesh':
                mesh = u.load_asset(REC.resolve(el['mesh'], item))
                if not mesh:
                    R['errors'].append('missing mesh %s' % el['mesh'])
                    continue
                loc = W(el.get('loc', (0, 0, 0)), ay)
                bb = el.get('billboard')
                if bb is True:      # a plane (+Z normal) turned to face the camera
                    rot = u.MathLibrary.compose_rotators(u.Rotator(roll=0, pitch=-90, yaw=0),
                                                         u.Rotator(roll=0, pitch=0, yaw=REC.VIEW_YAW + 180))
                elif bb == 'yaw':   # a sign whose front is +Y
                    rot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW)
                else:
                    rot = rot_of(el)
                a = spawn_sma(mesh, loc, rot, el.get('scale', (1, 1, 1)))
                if el['name'] in ('Pool', 'Paint', 'Shaft', 'Beam', 'Cone', 'Halo', 'Motes', 'Haze', 'Tag'):
                    a.static_mesh_component.set_editor_property('cast_shadow', False)
                mids = apply_slots(a, el['slots'], look, key, el['name'], item)
                track(a, loc, rot, el.get('scale', (1, 1, 1)), el.get('spin', 0), el.get('bob'), False, mids, 'prop',
                      strobe=el.get('strobe', False))
            elif k == 'itemcopy':
                mesh = u.load_asset(item['mesh'])
                loc = W(el['loc'], ay)
                rot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW + ITEM_TURN)
                s = el.get('scale', 1.0)
                a = spawn_sma(mesh, loc, rot, (s, s, s))
                a.static_mesh_component.set_editor_property('cast_shadow', False)
                m = material(REC.mi_path(look, key, el['name']))
                mids = []
                if m:
                    a.static_mesh_component.set_material(0, m)
                    mids.append(a.static_mesh_component.create_dynamic_material_instance(0, m))
                track(a, loc, rot, s, el.get('spin', 0), el.get('bob'), item['pulse'], mids, 'item')
            elif k == 'light':
                loc = W(el['loc'], ay)
                spot = el['type'] == 'spot'
                cls = u.SpotLight if spot else u.PointLight
                r = el.get('rot') or (0, 0, 0)
                rot = u.Rotator(roll=r[0], pitch=r[1], yaw=r[2])
                a = u.HoverAuthoring.spawn_playtest_actor(cls, u.Transform(location=V(loc), rotation=rot))
                c = a.get_component_by_class(u.SpotLightComponent if spot else u.PointLightComponent)
                c.set_mobility(u.ComponentMobility.MOVABLE)
                c.set_editor_property('intensity_units', u.LightUnits.CANDELAS)
                c.set_intensity(el['intensity'])
                c.set_attenuation_radius(el['radius'])
                c.set_light_color(lc(REC.resolve(el['color'], item)), True)
                c.set_cast_shadows(bool(el.get('shadows', True)))
                if spot and el.get('cone'):
                    c.set_inner_cone_angle(el['cone'][0])
                    c.set_outer_cone_angle(el['cone'][1])
                track(a, loc, rot, 1.0, kind='light', comp=c, base_i=el['intensity'], flicker=el.get('flicker'),
                      pulse=item['pulse'])
            elif k == 'niagara':
                loc = W(el['loc'], ay)
                sysa = u.load_asset(REC.ns_path(look, key, el['name'])) or u.load_asset(el['system'])
                a = u.HoverAuthoring.spawn_playtest_actor(u.NiagaraActor, u.Transform(location=V(loc)))
                c = a.niagara_component
                c.set_asset(sysa)
                for pk, pv in el.get('floats', {}).items():
                    c.set_variable_float(pk, float(pv))
                for pk, pv in el.get('colors', {}).items():
                    c.set_variable_linear_color(pk, lc(REC.resolve(pv, item)))
                for pk, pv in el.get('vectors', {}).items():
                    c.set_variable_vec3(pk, V(pv))
                c.activate(True)
                track(a, loc, None, 1.0, kind='fx')


def clear_look():
    for rec in S['live']:
        try:
            rec['actor'].destroy_actor()
        except Exception:  # noqa: BLE001
            pass
    S['live'] = []


# ----------------------------------------------------------------------------------------------------------------
# idle motion

def heartbeat(t):
    return max(0.0, math.sin(2 * math.pi * NUKE_HZ * t)) ** 6


def flicker(kind, t, rec):
    if S['freeze']:
        return 1.0
    if kind == 'flare':
        return 0.7 + 0.3 * (0.5 + 0.25 * math.sin(t * 31 + rec['phase']) + 0.25 * math.sin(t * 17.3 + 2 * rec['phase']))
    if kind == 'strobe':
        return 1.0 if (t % 0.9) < 0.1 else 0.0
    if kind == 'geiger':
        random.seed(int(t * 11) + int(rec['phase'] * 100))
        return 0.55 + 0.45 * random.random()
    if kind == 'fire':
        return 0.8 + 0.2 * math.sin(t * 9 + rec['phase']) * math.sin(t * 4.1)
    if kind == 'pulse':
        return 0.6 + 0.4 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.45 * t))
    if kind == 'buzz':
        random.seed(int(t * 30) + 7)
        return 0.25 if random.random() < 0.08 else 1.0
    return 1.0


def animate(t):
    hb = S['pulse'] if S['pulse'] is not None else (0.0 if S['freeze'] else heartbeat(t))
    for rec in S['live']:
        a = rec['actor']
        if rec['kind'] == 'light':
            k = flicker(rec['flicker'], t, rec)
            if rec.get('pulse'):
                k *= 1.0 + 2.0 * hb
            rec['comp'].set_intensity(rec['base_i'] * k)
            continue
        if rec['kind'] == 'fx':
            continue
        loc = rec['loc']
        z = 0.0
        if rec['bob'] and not S['freeze']:
            z = rec['bob'][0] * math.sin(2 * math.pi * rec['bob'][1] * t + rec['phase'])
        yaw = rec['rot'].yaw + (0.0 if S['freeze'] else rec['spin'] * t)
        r = u.Rotator(roll=rec['rot'].roll, pitch=rec['rot'].pitch, yaw=yaw)
        a.set_actor_location_and_rotation(u.Vector(loc[0], loc[1], loc[2] + z), r, False, True)
        if rec['pulse']:
            s = rec['scale'] * (1.0 + NUKE_AMP * hb)
            a.set_actor_scale3d(u.Vector(s, s, s))
            for m in rec['mids']:
                m.set_scalar_parameter_value('GlowBoost', 1.0 + 2.0 * hb)
        if rec.get('strobe'):
            on = flicker('strobe', t, rec)
            for m in rec['mids']:
                m.set_scalar_parameter_value('GlowBoost', 0.03 + 0.97 * on)


# ----------------------------------------------------------------------------------------------------------------
# camera + plan

TARGET = (0.0, 0.0, 36.0)


def cam_at(dist, height, fov, target=TARGET):
    loc = (target[0] - F[0] * dist, target[1] - F[1] * dist, height)
    rot = u.MathLibrary.find_look_at_rotation(V(loc), V(target))
    S['cam'].set_actor_location_and_rotation(V(loc), rot, False, True)
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)


def capture(name):
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    R['frames'].append(str(fn))
    log('frame', fn.name)


def step(delay, fn):
    S['queue'].append((delay, fn))


def set_ev():
    if math.isnan(EV):
        return
    for p in u.GameplayStatics.get_all_actors_of_class(world(), u.PostProcessVolume):
        s = p.get_editor_property('settings')
        s.set_editor_property('override_auto_exposure_bias', True)
        s.set_editor_property('auto_exposure_bias', EV)
        p.set_editor_property('settings', s)
    R['ev'] = EV


def plan():
    step(0.1, lambda t: set_ev())
    # warm-up overview: every look at once, spread down the street, so their shaders compile before the real shots
    if WARM > 0:
        def warm(t):
            for i, lk in enumerate(LOOKS):
                spawn_look(lk, ((i // 2) * 320.0 + 200.0, (i % 2) * 300.0 - 150.0))
            cam_at(1100, 420, 75, (F[0] * 1300, F[1] * 1300, 0))
        step(0.1, warm)
        step(WARM, lambda t: capture('_warmup_overview'))
        step(0.2, lambda t: clear_look())
    for lk in LOOKS:
        tag = 'S%02d_%s' % (lk['n'], lk['key'])
        wait = 5.0 if lk['key'] in ('SupplyBeacon', 'RoadFlare') else 2.5
        step(0.3, lambda t, lk=lk: spawn_look(lk))
        step(wait, lambda t: S.update(freeze=True))
        step(0.1, lambda t: cam_at(250, 112, 62))
        step(0.3, lambda t, tag=tag: capture(tag + '_close'))
        step(0.1, lambda t: cam_at(1000, 175, 70))
        step(0.3, lambda t, tag=tag: capture(tag + '_10m'))
        if lk['n'] in PULSE:
            for i, ph in enumerate((0.0, 0.5, 1.0)):
                step(0.1, lambda t, ph=ph: (S.update(pulse=ph), cam_at(150, 75, 50, (RT[0] * 58, RT[1] * 58, 30))))
                step(0.3, lambda t, tag=tag, i=i: capture('%s_pulse%d' % (tag, i)))
            step(0.05, lambda t: S.update(pulse=None))
        step(0.05, lambda t, lk=lk: (S.update(freeze=False), R['looks'].setdefault(lk['key'], {'n': lk['n']})))
        step(0.1, lambda t: clear_look())
    step(0.3, lambda t: finish())


def finish():
    if S['end']:
        return
    (OUT / ('preview_%s.json' % ROUND)).write_text(json.dumps(R, indent=1, default=str))
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
                    (OUT / ('preview_%s.json' % ROUND)).write_text(json.dumps(R, indent=1, default=str))
                    log('DONE frames=%d errors=%d' % (len(R['frames']), len(R['errors'])))
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 1500:
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
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            S['cam'].camera_component.set_editor_property('constrain_aspect_ratio', False)
            cam_at(250, 112, 62)
            plan()
            S['next'] = t
            R['viewport'] = str(u.HoverAuthoring.get_playtest_viewport_size())
            return
        animate(t)
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
