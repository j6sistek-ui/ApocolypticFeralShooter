"""RecordPowerUpGifs.py - record short seamless motion loops of the round-2 power-up looks (GPU, -RenderOffscreen, PIE).

A copy of Scripts/PreviewPowerUpStyles2.py (same boot, fixed-step PIE, spawn, lighting and animate(t) code, same
L_PowerUpShowcase pair: medkit left, nuke right) that, instead of stills, records LOOP_S seconds of each look from the
round-2 2.5 m close camera at FPS frames per second of GAME time:
  * HoverAuthoring.set_playtest_fixed_step(True) fixes the world step at 1/30 s, so every PIE tick advances game time by
    exactly 1/30 s however long a capture takes; a frame is kept every 30/FPS ticks -> evenly spaced frames.
  * ReadPixels (capture_world_frame) returns the frame drawn this engine tick, i.e. the state animate() set on the
    PREVIOUS callback: the frame captured in callback N is stamped with the animate time of callback N-1.
  * Loop seams: the heartbeat is 1.25 Hz and LOOP_S = 2.4 s holds exactly 3 beats. Other periodic motion (bob, orbit
    turns and heights, the 'pulse' and 'fire' light flickers, material PulseHz on the dynamic instances) is snapped to
    a whole number of cycles per loop when that changes its speed by at most SNAP_MAX; anything that would change
    more keeps its designed speed and is listed in the receipt (it jumps at the loop point). Continuous spin cannot loop
    in 2.4 s and is kept as designed (listed too).
Env: GIF_LOOKS=23,20,16,17,18,15,5,13,21,6 (record order)  GIF_FPS=15  GIF_LOOP=2.4  GIF_WARM=15  GIF_SETTLE=3.0
     PU2_EV (exposure bias override)
Out: D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs/frames/S<NN>_<Key>/f000.png ... + gifs/frames/record.json
GIF assembly is separate (system Python + PIL): Scripts/AssemblePowerUpGifs.py.
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
import PowerUpStyleRecipes2 as REC2  # noqa: E402

importlib.reload(REC)
importlib.reload(REC2)

ROUND = 'gif'
OUT = Path('D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs/frames')
STILLS = OUT
STILLS.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
ORDER = [int(x) for x in os.environ.get('GIF_LOOKS', '23,20,16,17,18,15,5,13,21,6').split(',') if x.strip()]
EV = float(os.environ.get('PU2_EV', 'nan'))
WARM = float(os.environ.get('GIF_WARM', '15'))
FPS = int(os.environ.get('GIF_FPS', '15'))
LOOP_S = float(os.environ.get('GIF_LOOP', '2.4'))
SETTLE = float(os.environ.get('GIF_SETTLE', '3.0'))
NFRAMES = int(round(LOOP_S * FPS))
TICK = 1.0 / 30.0          # HoverAuthoring.SetPlaytestFixedStep: FApp::SetFixedDeltaTime(1/30)
EVERY = int(round(30 / FPS))
SNAP_MAX = 0.35
_BY_N = {lk['n']: lk for lk in REC2.all_looks(False)}
LOOKS = [_BY_N[n] for n in ORDER if n in _BY_N]
ITEM_TURN = 22.0
BEAT_HZ = 1.25
NUKE_AMP = 0.12
PULSE_PHASES = (('rest', 0.85), ('peak', 0.25), ('after', 0.38))
R = {'ok': True, 'errors': [], 'frames': [], 'looks': {}, 'lights': [], 'round': ROUND,
     'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'fps': FPS, 'loop_s': LOOP_S, 'nframes': NFRAMES,
     'order': ORDER, 'snapped': {}, 'unlooped': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None, 'queue': [],
     'next': None, 'last_step_t': None, 'done': False, 't_first': None, 'live': [], 'freeze': False, 'phase': None,
     'rec': None, 'prev_t': None, 'look': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(REC.LEVEL), 'load_level failed'
F, RT = REC.view_basis()
FACE_YAW = REC.VIEW_YAW + 90.0
KW = u.AttachmentRule.KEEP_WORLD
PR = random.Random(1234)   # harness particles
BR = random.Random()       # bolts (reseeded per jump)


def log(*a):
    print('PU_GIF', *a, flush=True)


def world():
    return u.HoverAuthoring.get_playtest_world()


def V(t):
    return u.Vector(t[0], t[1], t[2])


def lc(c, k=1.0):
    return u.LinearColor(c[0] * k, c[1] * k, c[2] * k, 1.0)


def material(path):
    m = u.load_asset(path)
    if not m:
        R['errors'].append('missing material ' + path)
    return m


def spawn_sma(mesh, loc, rot, scale, shadow=True):
    a = u.HoverAuthoring.spawn_playtest_actor(u.StaticMeshActor, u.Transform(location=V(loc), rotation=rot, scale=V(scale)))
    c = a.static_mesh_component
    c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_static_mesh(mesh)
    a.set_actor_scale3d(V(scale))
    c.set_editor_property('cast_shadow', shadow)
    return a


def apply_slots(actor, slots, look, key, el_name):
    comp = actor.static_mesh_component
    mids = []
    names = [str(n) for n in comp.get_material_slot_names()]
    for slot, spec in slots.items():
        path = spec[1] if spec[0] == 'asset' else REC2.mi_path(look, key, el_name, slot)
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


def track(actor, base_loc, base_rot, base_scale, spin=0.0, bob=None, pulse=False, mids=None, kind='mesh', **kw):
    rec = {'actor': actor, 'loc': base_loc, 'rot': base_rot, 'scale': base_scale, 'spin': spin, 'bob': bob,
           'pulse': pulse, 'mids': mids or [], 'kind': kind, 'phase': random.random() * 6.28}
    rec.update(kw)
    S['live'].append(rec)
    return rec


def billboard_rot():
    return u.MathLibrary.compose_rotators(u.Rotator(roll=0, pitch=-90, yaw=0), u.Rotator(roll=0, pitch=0, yaw=REC.VIEW_YAW + 180))


def set_niagara_vars(c, el, item):
    for pk, pv in el.get('floats', {}).items():
        c.set_variable_float(pk, float(pv))
    for pk, pv in el.get('colors', {}).items():
        c.set_variable_linear_color(pk, lc(REC.resolve(pv, item)))
    for pk, pv in el.get('vectors', {}).items():
        c.set_variable_vec3(pk, V(pv))


def spawn_look(look, offset=(0.0, 0.0)):
    ox, oy = offset
    base = (F[0] * ox + RT[0] * oy, F[1] * ox + RT[1] * oy)

    def W(local, anchor_y):
        p = REC.view_to_world(local, anchor_y)
        return (p[0] + base[0], p[1] + base[1], p[2])

    for key in REC.ITEM_ORDER:
        item = REC.ITEMS[key]
        ay = item['y']
        spec = look['item']
        beats = bool(item['pulse'] or spec.get('pulse'))
        mesh = u.load_asset(item['mesh'])
        hover = spec.get('hover', 0)
        loc = W((0, 0, hover), ay)
        rot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW + ITEM_TURN)
        ia = spawn_sma(mesh, loc, rot, (1, 1, 1))
        mids = []
        if spec.get('material'):
            m = material(REC2.mi_path(look, key, 'Item'))
            if m:
                ia.static_mesh_component.set_material(0, m)
                mids.append(ia.static_mesh_component.create_dynamic_material_instance(0, m))
        track(ia, loc, rot, 1.0, spec.get('spin', 0), spec.get('bob'), beats, mids, 'item',
              double=spec.get('double_beat', False), jitter=spec.get('jitter', 0.0))
        orbiters = {}
        for el in look['elements']:
            k = el['kind']
            if k == 'shell':
                sa = spawn_sma(mesh, loc, rot, (1, 1, 1), shadow=False)
                m = material(REC2.mi_path(look, key, el['name']))
                smids = []
                if m:
                    sa.static_mesh_component.set_material(0, m)
                    smids.append(sa.static_mesh_component.create_dynamic_material_instance(0, m))
                sa.attach_to_actor(ia, '', KW, KW, KW, False)
                track(sa, loc, rot, 1.0, pulse=beats, mids=smids, kind='shell', echo=el.get('echo', False))
            elif k == 'mesh':
                m_ = u.load_asset(REC.resolve(el['mesh'], item))
                if not m_:
                    R['errors'].append('missing mesh %s' % el['mesh'])
                    continue
                mloc = W(el.get('loc', (0, 0, 0)), ay)
                bb = el.get('billboard')
                if bb is True:
                    mrot = billboard_rot()
                elif bb == 'yaw':
                    mrot = u.Rotator(roll=0, pitch=0, yaw=FACE_YAW)
                else:
                    r = el.get('rot', (0, 0, 0))
                    mrot = u.Rotator(roll=r[0], pitch=r[1], yaw=r[2] + REC.VIEW_YAW)
                shadow = el.get('shadow', el['name'] not in ('Shaft', 'Motes', 'Halo', 'Sign'))
                a = spawn_sma(m_, mloc, mrot, el.get('scale', (1, 1, 1)), shadow)
                mids_ = apply_slots(a, el['slots'], look, key, el['name'])
                track(a, mloc, mrot, el.get('scale', (1, 1, 1)), el.get('spin', 0), el.get('bob'), False, mids_, 'prop')
            elif k == 'light':
                lloc = W(el['loc'], ay)
                spot = el['type'] == 'spot'
                cls = u.SpotLight if spot else u.PointLight
                r = el.get('rot') or (0, 0, 0)
                lrot = u.Rotator(roll=r[0], pitch=r[1], yaw=r[2])
                a = u.HoverAuthoring.spawn_playtest_actor(cls, u.Transform(location=V(lloc), rotation=lrot))
                c = a.get_component_by_class(u.SpotLightComponent if spot else u.PointLightComponent)
                c.set_mobility(u.ComponentMobility.MOVABLE)
                a.set_actor_rotation(lrot, False)
                c.set_editor_property('intensity_units', u.LightUnits.CANDELAS)
                c.set_intensity(el['intensity'])
                c.set_attenuation_radius(el['radius'])
                c.set_light_color(lc(REC.resolve(el['color'], item)), True)
                c.set_cast_shadows(bool(el.get('shadows', False)))
                if el.get('volumetric') is not None:
                    c.set_volumetric_scattering_intensity(float(el['volumetric']))
                if spot and el.get('cone'):
                    c.set_inner_cone_angle(el['cone'][0])
                    c.set_outer_cone_angle(el['cone'][1])
                if spot and len(R['lights']) < 6:
                    fwd = a.get_actor_forward_vector()
                    R['lights'].append({'look': look['n'], 'item': key, 'rot': str(a.get_actor_rotation()),
                                        'forward': [round(fwd.x, 3), round(fwd.y, 3), round(fwd.z, 3)],
                                        'units': str(c.get_editor_property('intensity_units')),
                                        'intensity': c.get_editor_property('intensity')})
                track(a, lloc, lrot, 1.0, kind='light', comp=c, base_i=el['intensity'], flicker=el.get('flicker'),
                      pulse=beats or el.get('pulse', False))
            elif k == 'niagara':
                nloc = W(el['loc'], ay)
                sysa = u.load_asset(REC2.ns_path(look, key, el['name'])) or u.load_asset(el['system'])
                a = u.HoverAuthoring.spawn_playtest_actor(u.NiagaraActor, u.Transform(location=V(nloc)))
                c = a.niagara_component
                c.set_asset(sysa)
                set_niagara_vars(c, el, item)
                c.activate(True)
                if el.get('scale'):
                    a.set_actor_scale3d(V((el['scale'],) * 3))
                if el.get('attach'):
                    a.attach_to_actor(ia, '', KW, KW, KW, False)
                orb = el.get('orbit')
                rec = track(a, nloc, None, 1.0, kind='fx', orbit=orb, center=W((0, 0, 0), ay), hover=hover, comp=c,
                            retrigger=el.get('retrigger'), last=-99.0)
                orbiters[el['name']] = rec
            elif k in ('pfx', 'bolts'):
                sm = u.load_asset(REC.ENG_SPHERE)
                m = material(REC2.mi_path(look, key, el['name']))
                n = el.get('count', 20) if k == 'pfx' else el.get('count', 3) * el.get('segments', 4)
                parts = []
                for i in range(n):
                    a = spawn_sma(sm, W((0, 0, -500), ay), u.Rotator(), (0.001, 0.001, 0.001), shadow=False)
                    if m:
                        a.static_mesh_component.set_material(0, m)
                    parts.append({'a': a, 'age': 99.0, 'life': 0.0, 'p': (0, 0, -500), 'v': (0, 0, 0),
                                  'stagger': PR.random() + 0.01})
                track(None, W((0, 0, 0), ay), None, 1.0, kind=k, spec=el, parts=parts, center=W((0, 0, 0), ay),
                      hover=hover, item=ia, last_t=None, beats=beats)
            elif k == 'heads':
                pm = u.load_asset(REC.ENG_PLANE)
                m = material(REC2.mi_path(look, key, el['name']))
                for nm in el['of']:
                    host = orbiters.get(nm)
                    if not host:
                        continue
                    s = el.get('size', 0.1)
                    a = spawn_sma(pm, host['loc'], billboard_rot(), (s, s, s), shadow=False)
                    if m:
                        a.static_mesh_component.set_material(0, m)
                    host.setdefault('heads', []).append(a)


def snap(f, what):
    """A frequency (Hz, may be negative) snapped to a whole number of cycles per loop, if that is a small change."""
    if not f:
        return f
    k = max(1, round(abs(f) * LOOP_S))
    g = math.copysign(k / LOOP_S, f)
    look = S['look'] or '?'
    if abs(g - f) / abs(f) <= SNAP_MAX:
        if abs(g - f) > 1e-6:
            R['snapped'].setdefault(look, []).append('%s %.3f->%.3f Hz' % (what, f, g))
        return g
    R['unlooped'].setdefault(look, []).append('%s %.3f Hz kept (%.2f cycles per loop)' % (what, f, abs(f) * LOOP_S))
    return f


def make_loopable():
    """Snap the periodic motion of the spawned look to the loop length (see the module doc)."""
    look = S['look']
    for rec in S['live']:
        kind = rec['kind']
        if rec.get('bob'):
            a, hz = rec['bob']
            rec['bob'] = (a, snap(hz, '%s bob' % kind))
        if rec.get('spin') and kind in ('item', 'prop'):
            what = 'item' if kind == 'item' else 'prop/motes'
            R['unlooped'].setdefault(look, []).append(
                '%s spin %.0f deg/s kept (turns %.0f deg per loop, jumps back at the loop point)'
                % (what, rec['spin'], rec['spin'] * LOOP_S))
        if kind == 'fx' and rec.get('orbit'):
            rad, z0, za, turns, zhz, ph = rec['orbit']
            rec['orbit'] = (rad, z0, za, snap(turns, 'orbit turns'), snap(zhz, 'orbit height'), ph)
        if kind == 'light' and rec.get('flicker') in ('pulse', 'fire'):
            R['snapped'].setdefault(look, []).append('light %s flicker snapped to the loop' % rec['flicker'])
        for m in rec.get('mids', []):
            try:
                hz = m.get_scalar_parameter_value('PulseHz')
            except Exception:  # noqa: BLE001
                hz = 0.0
            if hz:
                m.set_scalar_parameter_value('PulseHz', snap(hz, '%s material PulseHz' % kind))


FIRE_W = (2 * math.pi * max(1, round(9 / (2 * math.pi) * LOOP_S)) / LOOP_S,
          2 * math.pi * max(1, round(4.1 / (2 * math.pi) * LOOP_S)) / LOOP_S)
PULSE_HZ = max(1, round(0.45 * LOOP_S)) / LOOP_S


def clear_look():
    for rec in S['live']:
        try:
            for h in rec.get('heads', []):
                h.destroy_actor()
            for q in rec.get('parts', []):
                q['a'].destroy_actor()
            if rec['actor']:
                rec['actor'].destroy_actor()
        except Exception:  # noqa: BLE001
            pass
    S['live'] = []


# ----------------------------------------------------------------------------------------------------------------
# idle motion

def beat_shape(ph):
    """ph = phase within one beat cycle (0..1); the main thump peaks at 0.25."""
    return max(0.0, math.sin(2 * math.pi * ph)) ** 6


def heartbeat(t, double=False):
    ph = (BEAT_HZ * t) % 1.0
    if S['phase'] is not None:
        ph = S['phase']
    elif S['freeze']:
        return 0.0, 1.0
    hb = beat_shape(ph)
    if double:
        hb = min(1.2, hb + 0.6 * beat_shape((ph - 0.25) % 1.0))
    echo = (ph - 0.25) % 1.0   # 0 at the thump, grows until the next one
    return hb, echo


def flicker(kind, t, rec):
    if S['freeze'] and S['phase'] is None and kind in ('buzz', 'arc', 'geiger'):
        pass
    if kind == 'strobe':
        return 1.0 if (t % 0.9) < 0.1 else 0.0
    if kind == 'geiger':
        random.seed(int(t * 11) + int(rec['phase'] * 100))
        return 0.55 + 0.45 * random.random()
    if kind == 'fire':
        return 0.8 + 0.2 * math.sin(t * FIRE_W[0] + rec['phase']) * math.sin(t * FIRE_W[1])
    if kind == 'pulse':
        return 0.6 + 0.4 * (0.5 + 0.5 * math.sin(2 * math.pi * PULSE_HZ * t))
    if kind == 'buzz':
        random.seed(int(t * 30) + 7)
        return 0.3 if random.random() < 0.08 else 1.0
    if kind == 'arc':
        random.seed(int(t * 20) + 3)
        return 1.5 if random.random() < 0.3 else 0.6
    return 1.0


def orbit_pos(rec, t):
    rad, z0, za, turns, zhz, ph = rec['orbit']
    a = 2 * math.pi * (turns * t + ph)
    z = z0 + za * math.sin(2 * math.pi * (zhz * t + ph)) + rec['hover']
    c = rec['center']
    # the orbit plane is the view frame: x toward the camera, y right
    lx, ly = rad * math.cos(a), rad * math.sin(a)
    return (c[0] - F[0] * lx + RT[0] * ly, c[1] - F[1] * lx + RT[1] * ly, z)


def _place(a, p, v, length, width):
    """A stretched glowing sphere at p along v (a spark streak / ember / bolt segment)."""
    if width <= 0.001:
        a.set_actor_scale3d(V((0.001, 0.001, 0.001)))
        return
    sp = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if sp > 1e-3:
        rot = u.MathLibrary.find_look_at_rotation(V(p), V((p[0] + v[0], p[1] + v[1], p[2] + v[2])))
    else:
        rot = u.Rotator()
    a.set_actor_location_and_rotation(V(p), rot, False, True)
    a.set_actor_scale3d(V((max(length, width) / 100.0, width / 100.0, width / 100.0)))


def animate_pfx(rec, t):
    """Harness particles (stand-ins for a Niagara sprite emitter): spawn on the item's surface, fly, fade."""
    el = rec['spec']
    dt = 0.0 if rec['last_t'] is None else min(0.05, max(0.0, t - rec['last_t']))
    rec['last_t'] = t
    loc = rec['item'].get_actor_location()
    gate = 1.0
    if el.get('gate') == 'beat':
        gate, _ = heartbeat(t, True)
    sp0, sp1 = el.get('speed', (60, 120))
    l0, l1 = el.get('life', (0.5, 1.0))
    rad = el.get('radius', 13.0)
    z0, z1 = el.get('z', (5, 40))
    up = el.get('up', 0.3)
    g = el.get('gravity', 0.0)
    drag = el.get('drag', 0.0)
    w0 = el.get('width', 1.2)
    streak = el.get('streak', 0.03)
    maxlen = el.get('maxlen', 12.0)
    wob = el.get('wobble', 0.0)
    for q in rec['parts']:
        q['age'] += dt
        if q['age'] >= q['life']:
            if q['stagger'] > 0:      # spread the first wave over one lifetime
                q['age'] = -q['stagger'] * l1
                q['stagger'] = 0.0
                q['life'] = 0.0
                _place(q['a'], q['p'], q['v'], 0, 0)
                continue
            if el.get('gate') == 'beat' and gate < 0.35:
                _place(q['a'], q['p'], q['v'], 0, 0)
                continue
            th = PR.random() * 2 * math.pi
            r = rad * (0.85 + 0.3 * PR.random())
            z = z0 + (z1 - z0) * PR.random()
            q['p'] = (loc.x + r * math.cos(th), loc.y + r * math.sin(th), loc.z + z)
            spd = sp0 + (sp1 - sp0) * PR.random()
            d = (math.cos(th), math.sin(th), up + 0.5 * (PR.random() - 0.5))
            n = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            q['v'] = (d[0] / n * spd, d[1] / n * spd, d[2] / n * spd)
            q['age'] = 0.0
            q['life'] = l0 + (l1 - l0) * PR.random()
        if q['age'] < 0:
            _place(q['a'], q['p'], q['v'], 0, 0)
            continue
        vx, vy, vz = q['v']
        vz += g * dt
        k = max(0.0, 1.0 - drag * dt)
        vx, vy, vz = vx * k, vy * k, vz * k
        if wob:
            vx += (PR.random() - 0.5) * wob * dt
            vy += (PR.random() - 0.5) * wob * dt
        q['v'] = (vx, vy, vz)
        q['p'] = (q['p'][0] + vx * dt, q['p'][1] + vy * dt, q['p'][2] + vz * dt)
        f = q['age'] / max(q['life'], 1e-3)
        w = w0 * (1.0 - f) ** 0.6
        if el.get('twinkle'):
            w *= 0.6 + 0.6 * PR.random()
        sp = math.sqrt(vx * vx + vy * vy + vz * vz)
        _place(q['a'], q['p'], q['v'], min(maxlen, w + sp * streak), w)


def animate_bolts(rec, t):
    """Jagged arcs: each bolt jumps between two points just off the item surface every 1/rate s."""
    el = rec['spec']
    rate = el.get('rate', 12.0)
    segs = el.get('segments', 4)
    rad = el.get('radius', 14.0)
    reach = el.get('reach', 6.0)
    w = el.get('width', 0.7)
    z0, z1 = el.get('z', (4, 42))
    loc = rec['item'].get_actor_location()
    parts = rec['parts']
    nb = len(parts) // segs
    for b in range(nb):
        slot = int(t * rate + b * 0.37)
        BR.seed(slot * 7919 + b * 104729 + int(rec['center'][1] * 10))
        on = BR.random() < el.get('duty', 0.75)
        th0 = BR.random() * 2 * math.pi
        th1 = th0 + (0.5 + BR.random() * 1.2) * (1 if BR.random() < 0.5 else -1)
        za = z0 + (z1 - z0) * BR.random()
        zb = max(z0, min(z1, za + (BR.random() - 0.5) * 30))
        pts = []
        for i in range(segs + 1):
            f = i / segs
            th = th0 + (th1 - th0) * f
            bulge = math.sin(math.pi * f) * reach * (0.5 + BR.random())
            r = rad + 1.0 + bulge
            z = za + (zb - za) * f + (BR.random() - 0.5) * 6 * math.sin(math.pi * f)
            pts.append((loc.x + r * math.cos(th), loc.y + r * math.sin(th), loc.z + z))
        for i in range(segs):
            a = parts[b * segs + i]['a']
            if not on:
                _place(a, pts[i], (1, 0, 0), 0, 0)
                continue
            p0, p1 = pts[i], pts[i + 1]
            mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2)
            v = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
            ln = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
            _place(a, mid, v, ln * 1.15, w)


def animate(t):
    for rec in S['live']:
        a = rec['actor']
        kind = rec['kind']
        if kind == 'light':
            k = flicker(rec['flicker'], t, rec)
            if rec.get('pulse'):
                hb, _ = heartbeat(t)
                k *= 1.0 + 2.0 * hb
            rec['comp'].set_intensity(rec['base_i'] * k)
            continue
        if kind == 'fx':
            if rec.get('retrigger') and t - rec['last'] >= rec['retrigger']:
                rec['last'] = t
                rec['comp'].reset_system()
            if rec.get('orbit'):
                p = orbit_pos(rec, t)
                a.set_actor_location(V(p), False, True)
                for h in rec.get('heads', []):
                    h.set_actor_location(V(p), False, True)
            continue
        if kind == 'pfx':
            animate_pfx(rec, t)
            continue
        if kind == 'bolts':
            animate_bolts(rec, t)
            continue
        if kind == 'shell':
            if rec['pulse'] or rec.get('echo'):
                hb, echo = heartbeat(t, True)
                if rec.get('echo'):
                    s = 1.0 + 0.55 * echo
                    a.set_actor_relative_scale3d(V((s, s, s)))
                    for m in rec['mids']:
                        m.set_scalar_parameter_value('GlowBoost', (1.0 - echo) ** 2.5)
                else:
                    for m in rec['mids']:
                        m.set_scalar_parameter_value('GlowBoost', 1.0 + 1.5 * hb)
            continue
        loc = rec['loc']
        z = 0.0
        if rec['bob'] and not S['freeze']:
            z = rec['bob'][0] * math.sin(2 * math.pi * rec['bob'][1] * t + rec['phase'])
        yaw = rec['rot'].yaw + (0.0 if S['freeze'] else rec['spin'] * t)
        r = u.Rotator(roll=rec['rot'].roll, pitch=rec['rot'].pitch, yaw=yaw)
        dx = dy = 0.0
        hb = 0.0
        if rec['pulse']:
            hb, _ = heartbeat(t, rec.get('double', False))
            if rec.get('jitter'):
                random.seed(int(t * 40))
                dx = (random.random() - 0.5) * 2 * rec['jitter'] * hb
                dy = (random.random() - 0.5) * 2 * rec['jitter'] * hb
        a.set_actor_location_and_rotation(u.Vector(loc[0] + dx, loc[1] + dy, loc[2] + z), r, False, True)
        if rec['pulse']:
            s = rec['scale'] * (1.0 + NUKE_AMP * hb)
            a.set_actor_scale3d(u.Vector(s, s, s))
            for m in rec['mids']:
                m.set_scalar_parameter_value('GlowBoost', 1.0 + 2.0 * hb)


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


def start_rec(lk):
    d = OUT / ('S%02d_%s' % (lk['n'], lk['key']))
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob('f*.png'):
        old.unlink()
    S['rec'] = {'dir': d, 'look': lk, 'start': None, 'n': 0, 'times': []}
    log('record', lk['n'], lk['key'])


def rec_tick(t):
    """Called once per new game time t, BEFORE animate(t): the frame on screen now shows animate(S['prev_t'])."""
    rc = S['rec']
    if rc is None or rc['n'] >= NFRAMES:
        return
    shown = S['prev_t']
    if rc['start'] is None:
        rc['start'] = t          # animate(t) below is frame 0; it shows up next callback
        return
    if shown is None:
        return
    i = int(round((shown - rc['start']) / TICK))
    if i < 0 or i % EVERY:
        return
    fn = rc['dir'] / ('f%03d.png' % rc['n'])
    u.HoverAuthoring.capture_world_frame(str(fn))
    rc['times'].append(round(shown - rc['start'], 4))
    rc['n'] += 1
    if rc['n'] >= NFRAMES:
        lk = rc['look']
        R['looks'][lk['key']] = {'n': lk['n'], 'name': lk['name'], 'frames': rc['n'], 'dir': str(rc['dir']),
                                 'game_t0': round(rc['start'], 4), 'times': rc['times']}
        log('recorded', lk['key'], rc['n'], 'frames, last t', rc['times'][-1])


def spawn_for_rec(lk):
    S['look'] = lk['key']
    spawn_look(lk)
    make_loopable()


def plan():
    step(0.1, lambda t: set_ev())
    if WARM > 0:
        def warm(t):
            for i, lk in enumerate(LOOKS):
                spawn_look(lk, ((i // 2) * 320.0 + 200.0, (i % 2) * 300.0 - 150.0))
            cam_at(1100, 420, 75, (F[0] * 1300, F[1] * 1300, 0))
        step(0.1, warm)
        step(WARM, lambda t: capture('_warmup_overview'))
        step(0.2, lambda t: clear_look())
    for lk in LOOKS:
        step(0.3, lambda t, lk=lk: spawn_for_rec(lk))
        step(0.1, lambda t: cam_at(250, 112, 62))
        step(SETTLE, lambda t, lk=lk: start_rec(lk))
        step(LOOP_S + 0.4, lambda t: S.update(rec=None))
        step(0.1, lambda t: clear_look())
    step(0.3, lambda t: finish())


def finish():
    if S['end']:
        return
    (OUT / 'record.json').write_text(json.dumps(R, indent=1, default=str))
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
                    (OUT / 'record.json').write_text(json.dumps(R, indent=1, default=str))
                    log('DONE looks=%d errors=%d' % (len(R['looks']), len(R['errors'])))
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 2400:
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
        if t != S['prev_t']:
            rec_tick(t)
            animate(t)
            S['prev_t'] = t
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
