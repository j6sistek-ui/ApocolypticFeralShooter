"""ProveParkourLifeEngine.py - in-game receipt: does the parkour template (BP_Vexa_CLS_Parkour) still wall run, wall
jump and clear the start barrier while the Life Engine solver drives? Life Engine ON, then OFF (`LifeEngine 0/1`).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveParkourLifeEngine.py
      -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720
      "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.EffectsQuality 1, sg.PostProcessQuality 1"

PIE L_NYC_Survival at 1280x720 (owner GPU budget), test input isolated, fixed 1/30 s step, zombies destroyed as they
spawn. Setup finds (1) a vault candidate near the start: a StaticMeshActor whose mesh / name says jersey / barrier
(40-160 cm tall), else a low obstacle found by knee/head-height traces, and (2) a long wall: a vertical face hit by a
120 cm-high ray whose plane holds over +-4 m and from 60 to 250 cm, with a clear running lane beside it (wall on her
LEFT first, so the right-shoulder camera arm does not pin against it and hide her). No wall -> a 12 x 4 m test wall is
spawned in the unsaved Play world beside the start (recorded as spawned). Per mode three runs:
  vault  : sprint (stick click + W) at the barrier, SpaceBar 140 cm before it, hold W 2.5 s
  wall   : sprint along the wall 70 cm off it, SpaceBar after 0.7 s, SpaceBar again (wall jump) after 0.35 s of wall run
  angle  : sprint at the wall 30 deg, SpaceBar 140 cm off its plane, same wall jump
Per tick it records height, speed, the character-movement mode, IsFalling / IsMovingOnGround as the template sees them,
the template's IsWallRunning / WallJumpLock / HasJumped and GravityScale, Life Engine active + solver ground flag, the
body and CLS-driver montages, whether her mesh is hidden from the owner view; stills from a side camera actor mid-vault,
mid-wall-run and mid-wall-jump (one tick after the camera moves). The log is harvested for HOVER_PARKOUR_YIELD / RESUME /
LAUNCH / WALLRUN (Verbose, enabled here) and LIFE_ENGINE lines.

Receipt D:/AFS_Comparisons/ParkourLifeEngine_20261031/proof.json (PROOF_OUT overrides). Changes only the unsaved Play
world. Run it once BEFORE the patch too: the 'on' pass then records the bug (no wall run with the solver on).
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
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/ParkourLifeEngine_20261031')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 900
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'passes': {}, 'log': {}, 'stills': [], 'summary': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'ticks': 0, 'run': None, 'cam': None, 'zombies_removed': 0, 'hold': set(),
     'snap': None, 'getters': {}, 'mode': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'
UP = u.Vector(0, 0, 1)


def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def V(x, y, z):
    return u.Vector(float(x), float(y), float(z))


def dot2(a, b):
    return a.x * b.x + a.y * b.y


def norm2(v):
    n = math.hypot(v.x, v.y) or 1.0
    return V(v.x / n, v.y / n, 0)


def yaw_of(d):
    return math.degrees(math.atan2(d.y, d.x))


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


def release_all():
    for k in list(S['hold']):
        key(k, False)


def clear_zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls:
        return
    for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
        z.destroy_actor()
        S['zombies_removed'] += 1


# --------------------------------------------------------------------------------------------------------- traces
def _hit_fields(hit):
    """(impact_point, impact_normal, actor, distance) from a HitResult, across the Python wrappers' shapes."""
    if hit is None:
        return None
    if isinstance(hit, tuple):
        hit = next((h for h in hit if isinstance(h, u.HitResult)), None)
        if hit is None:
            return None
    try:
        t = hit.to_tuple()
    except Exception:  # noqa: BLE001
        t = u.GameplayStatics.break_hit_result(hit)
    if not t or not t[0]:
        return None
    return t[5], t[7], t[9], t[3]


def trace(a, b):
    try:
        hit = u.SystemLibrary.line_trace_single(world(), a, b, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [pawn()],
                                                u.DrawDebugTrace.NONE, True)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('line_trace_single: %s' % str(e)[:160])
        return None
    return _hit_fields(hit)


def ground_z(p, above=200, below=400):
    h = trace(p + V(0, 0, above), p - V(0, 0, below))
    return h[0].z if h else None


def stand_at(p):
    """Location for the capsule (half height 97) standing on the ground under p, or None."""
    g = ground_z(p)
    return V(p.x, p.y, g + 99) if g is not None else None


# --------------------------------------------------------------------------------------------------- obstacles
def find_barrier(origin):
    g0 = ground_z(origin) or (origin.z - 97)
    best = None
    for a in u.GameplayStatics.get_all_actors_of_class(world(), u.StaticMeshActor):
        try:
            comp = a.static_mesh_component
            mesh = comp.static_mesh if comp else None
            name = '%s %s' % (mesh.get_name() if mesh else '', a.get_name())
            if not re.search(r'jersey|barrier|barricade', name, re.I):
                continue
            d = math.hypot(a.get_actor_location().x - origin.x, a.get_actor_location().y - origin.y)
            if d > 2500:
                continue
            o, e = a.get_actor_bounds(False)
            h = e.z * 2
            if not 40 <= h <= 160 or min(e.x, e.y) > 120:
                continue
            if best is None or d < best['dist']:
                axis = V(1, 0, 0) if e.x < e.y else V(0, 1, 0)  # cross the barrier along its thin axis
                if dot2(V(origin.x - o.x, origin.y - o.y, 0), axis) > 0:
                    axis = V(-axis.x, -axis.y, 0)  # approach from the start's side
                best = {'source': 'actor', 'actor': a.get_name(), 'mesh': name.split(' ')[0], 'dist': round(d, 0),
                        'center': o, 'half_thick': min(e.x, e.y), 'height': round(h, 1), 'axis': axis,
                        'top_z': o.z + e.z}
        except Exception as ex:  # noqa: BLE001
            R['api_errors'].append('barrier scan %s: %s' % (a.get_name(), str(ex)[:120]))
    if best:
        return best
    # Fallback: a low obstacle (knee-height hit, head height clear for 150 cm beyond it).
    for yaw in range(0, 360, 15):
        d = V(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
        knee = trace(V(origin.x, origin.y, g0 + 45), V(origin.x, origin.y, g0 + 45) + d * 1500)
        if not knee:
            continue
        dist = knee[3]
        head = trace(V(origin.x, origin.y, g0 + 175), V(origin.x, origin.y, g0 + 175) + d * (dist + 150))
        if head and head[3] < dist + 150:
            continue
        top = trace(knee[0] + d * 20 + V(0, 0, 200), knee[0] + d * 20 - V(0, 0, 100))
        h = (top[0].z - g0) if top else None
        if h and 40 <= h <= 150 and (best is None or dist < best['dist']):
            best = {'source': 'trace', 'dist': round(dist, 0), 'center': knee[0] + d * 20, 'half_thick': 20.0,
                    'height': round(h, 1), 'axis': d, 'top_z': top[0].z}
    return best


def lane_clear(start, t, length=900):
    for h in (50, 150):
        a = start + V(0, 0, h - 99)
        if trace(a, a + t * length):
            return False
    for s in (0, length * .5, length):
        if ground_z(start + t * s) is None:
            return False
    return True


def find_wall(origin):
    g0 = ground_z(origin) or (origin.z - 97)
    cands = []
    for yaw in range(0, 360, 10):
        d = V(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
        a = V(origin.x, origin.y, g0 + 120)
        hit = trace(a, a + d * 3000)
        if not hit or abs(hit[1].z) > .2:
            continue
        p, n = hit[0], norm2(hit[1])
        t = V(n.y, -n.x, 0)  # wall on her LEFT when she runs along +t
        good = True
        for s in (-400, -200, 200, 400):
            for h in (60, 250):
                q = V(p.x, p.y, g0 + h) + t * s + n * 80
                hh = trace(q, q - n * 200)
                if not hh or abs(hh[3] - 80) > 25 or dot2(norm2(hh[1]), n) < .9:
                    good = False
                    break
            if not good:
                break
        if good:
            cands.append({'dist': hit[3], 'point': p, 'normal': n, 'yaw': yaw})
    cands.sort(key=lambda c: c['dist'])
    for c in cands:
        p, n = c['point'], c['normal']
        for side, t in (('left', V(n.y, -n.x, 0)), ('right', V(-n.y, n.x, 0))):
            start = stand_at(p + n * 70 - t * 600)
            if start and lane_clear(start, t):
                c.update({'source': 'level', 'tangent': t, 'wall_side': side, 'lane_start': start})
                return c
    return None


def spawn_wall(origin, forward):
    right = V(-forward.y, forward.x, 0)
    g0 = ground_z(origin) or (origin.z - 97)
    center = V(origin.x, origin.y, g0 + 200) + right * 350 + forward * 300
    tr = u.Transform(location=center, rotation=u.Rotator(roll=0, pitch=0, yaw=yaw_of(forward)), scale=V(12, .4, 4))
    a = u.HoverAuthoring.spawn_playtest_actor(u.StaticMeshActor, tr)
    comp = a.static_mesh_component
    comp.set_mobility(u.ComponentMobility.MOVABLE)
    comp.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube.Cube'))
    comp.set_collision_profile_name('BlockAll')
    a.set_actor_scale3d(V(12, .4, 4))
    n = V(-right.x, -right.y, 0)  # face toward the start
    p = V(center.x, center.y, g0 + 120) + n * 20
    t = V(n.y, -n.x, 0)
    return {'source': 'spawned', 'actor': a.get_name(), 'point': p, 'normal': n, 'tangent': t, 'wall_side': 'left',
            'lane_start': stand_at(p + n * 70 - t * 600) or V(p.x, p.y, g0 + 99) + n * 70 - t * 600, 'dist': 350}


# ------------------------------------------------------------------------------------------------------- state
def bp_var(p, names):
    """Read a template Blueprint variable; the working accessor is cached per first name."""
    k = names[0]
    g = S['getters'].get(k)
    if g is None:
        for nm in names:
            try:
                p.get_editor_property(nm)
                S['getters'][k] = g = ('prop', nm)
                break
            except Exception:  # noqa: BLE001
                continue
        else:
            S['getters'][k] = g = ('desc', names)
    if g[0] == 'prop':
        try:
            return p.get_editor_property(g[1])
        except Exception:  # noqa: BLE001
            return None
    tick = S['ticks']
    if S.get('desc_tick') != tick:
        try:
            S['desc'] = dict(u.HoverAuthoring.describe_object_properties(p))
        except Exception as e:  # noqa: BLE001
            S['desc'] = {}
            R['api_errors'].append('describe_object_properties: %s' % str(e)[:100])
        S['desc_tick'] = tick
    for nm in g[1]:
        if nm in S['desc']:
            v = S['desc'][nm]
            return {'True': True, 'False': False}.get(v, v)
    return None


def body_mesh(p):
    try:
        return p.get_editor_property('mesh')
    except Exception:  # noqa: BLE001
        return p.get_component_by_class(u.SkeletalMeshComponent)


def montage_name(mesh):
    try:
        ai = mesh.get_anim_instance() if mesh else None
        m = ai.get_current_active_montage() if ai else None
        return m.get_name() if m else None
    except Exception:  # noqa: BLE001
        return None


def snapshot(p):
    cmc = p.get_movement_component()
    loc, vel = p.get_actor_location(), p.get_velocity()
    row = {'z': round(loc.z, 1), 'x': round(loc.x, 1), 'y': round(loc.y, 1),
           'speed': round(math.hypot(vel.x, vel.y), 1), 'vz': round(vel.z, 1)}
    try:
        row['mode'] = str(cmc.get_editor_property('movement_mode')).split('.')[-1].split(':')[0]
        row['falling'] = cmc.is_falling()
        row['ground'] = cmc.is_moving_on_ground()
        row['grav'] = round(cmc.get_editor_property('gravity_scale'), 2)
        row['crouch'] = bool(p.get_editor_property('is_crouched'))
    except Exception as e:  # noqa: BLE001
        row['cmc_err'] = str(e)[:80]
    try:
        row['life'] = bool(p.is_life_engine_active())
        lm = p.get_editor_property('life_movement')
        row['solver_gnd'] = lm.get_editor_property('grounded') if lm else None
    except Exception as e:  # noqa: BLE001
        row['life_err'] = str(e)[:80]
    row['wallrun'] = bp_var(p, ['IsWallRunning', 'is_wall_running', 'Is Wall Running'])
    row['wjlock'] = bp_var(p, ['WallJumpLock', 'wall_jump_lock', 'Wall Jump Lock'])
    row['jumped'] = bp_var(p, ['HasJumped', 'has_jumped', 'Has Jumped'])
    mesh = body_mesh(p)
    row['montage'] = montage_name(mesh)
    try:
        row['cls_montage'] = montage_name(u.HoverIntegrationAuthoring.get_cls_driver(p))
    except Exception:  # noqa: BLE001
        row['cls_montage'] = None
    try:
        row['hidden'] = bool(mesh.get_editor_property('owner_no_see'))
    except Exception:  # noqa: BLE001
        pass
    return row


# ------------------------------------------------------------------------------------------------------- stills
def side_capture(name, side_dir):
    p = pawn()
    loc = p.get_actor_location()
    cam_loc = loc + side_dir * 520 + V(0, 0, 90)
    S['cam'].set_actor_location_and_rotation(
        cam_loc, u.MathLibrary.find_look_at_rotation(cam_loc, loc + V(0, 0, 20)), False, False)
    S['pc'].set_view_target_with_blend(S['cam'], 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    # ReadPixels returns the frame already rendered: snap one tick after the camera move.
    S['snap'] = {'file': OUT / (name + '.png'), 'ticks': 1}


def snap_tick():
    sn = S['snap']
    if not sn:
        return
    if sn['ticks'] > 0:
        sn['ticks'] -= 1
        return
    u.HoverAuthoring.capture_world_frame(str(sn['file']))
    R['stills'].append(sn['file'].name)
    S['snap'] = None
    # Back to the survival camera between stills.
    S['pc'].set_view_target_with_blend(pawn(), 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


# --------------------------------------------------------------------------------------------------------- runs
def place(loc, yaw):
    p = pawn()
    p.set_actor_location_and_rotation(loc, u.Rotator(roll=0, pitch=0, yaw=yaw), False, True)
    S['pc'].set_control_rotation(u.Rotator(roll=0, pitch=-8, yaw=yaw))
    try:
        p.get_movement_component().stop_movement_immediately()
        lm = p.get_editor_property('life_movement')
        if lm:
            lm.set_hl_velocity(V(0, 0, 0))
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('place: %s' % str(e)[:100])


def start_run(kind):
    mode = S['mode']
    setup = R['setup']
    run = {'kind': kind, 'mode': mode, 'rows': [], 't0': None, 'jump_t': None, 'jump2_t': None, 'wall_t': None,
           'stills': {}, 'note': None}
    if kind == 'vault':
        b = setup.get('_barrier')
        if not b:
            run['note'] = 'no vault candidate'
            S['staged_run'] = None
            R['passes'].setdefault(mode, {})[kind] = run
            return
        start = stand_at(b['center'] - b['axis'] * (b['half_thick'] + 650))
        if start is None:
            run['note'] = 'no ground at the vault approach'
            S['staged_run'] = None
            R['passes'].setdefault(mode, {})[kind] = run
            return
        place(start, yaw_of(b['axis']))
        run.update({'axis': b['axis'], 'face': b['center'] - b['axis'] * b['half_thick'], 'side': V(-b['axis'].y, b['axis'].x, 0)})
    else:
        w = setup['_wall']
        n, t = w['normal'], w['tangent']
        if kind == 'wall':
            start, d = w['lane_start'], t
        else:
            d = norm2(t * math.cos(math.radians(30)) - n * math.sin(math.radians(30)))
            start = stand_at(w['point'] + n * 330 - t * 350) or w['lane_start']
        place(start, yaw_of(d))
        run.update({'n': n, 't': t, 'p': w['point'], 'side': n})  # side camera on the open side of the wall
    run['start_loc'] = vec(pawn().get_actor_location())
    # The ('run', None) queue marker starts it after the settle delay.
    S['staged_run'] = run


def run_tick(t):
    run = S['run']
    if not run:
        return
    p = pawn()
    if run['t0'] is None:
        run['t0'] = t
        key('W', True)
        key('Gamepad_LeftThumbstick', True)
    el = t - run['t0']
    row = snapshot(p)
    row['t'] = round(el, 3)
    run['rows'].append(row)
    loc = p.get_actor_location()
    # Jump triggers.
    if run['jump_t'] is None:
        go = False
        if run['kind'] == 'vault':
            go = dot2(run['face'] - loc, run['axis']) < 140
        elif run['kind'] == 'wall':
            go = el >= .7
        else:
            go = dot2(loc - run['p'], run['n']) < 140
        if go or el > 2.5:
            key('SpaceBar', True)
            run['jump_t'] = el
    elif 'SpaceBar' in S['hold'] and el - (run['jump2_t'] or run['jump_t']) > .15:
        key('SpaceBar', False)
    # Wall run detection, wall jump, stills.
    if row.get('wallrun') and run['wall_t'] is None:
        run['wall_t'] = el
    if run['kind'] != 'vault':
        if run['wall_t'] is not None and run['jump2_t'] is None and el - run['wall_t'] >= .35:
            key('SpaceBar', True)
            run['jump2_t'] = el
        if run['wall_t'] is not None and 'mid_wallrun' not in run['stills'] and el - run['wall_t'] >= .2:
            run['stills']['mid_wallrun'] = '%s_%s_mid_wallrun' % (run['mode'], run['kind'])
            side_capture(run['stills']['mid_wallrun'], run['side'])
        if run['jump2_t'] is not None and 'mid_walljump' not in run['stills'] and el - run['jump2_t'] >= .2:
            run['stills']['mid_walljump'] = '%s_%s_mid_walljump' % (run['mode'], run['kind'])
            side_capture(run['stills']['mid_walljump'], run['side'])
        if run['jump_t'] is not None and run['wall_t'] is None and 'airborne' not in run['stills'] and \
                el - run['jump_t'] >= .45:
            run['stills']['airborne'] = '%s_%s_airborne_no_wallrun' % (run['mode'], run['kind'])
            side_capture(run['stills']['airborne'], run['side'])
    elif run['jump_t'] is not None and 'mid_vault' not in run['stills'] and el - run['jump_t'] >= .25:
        run['stills']['mid_vault'] = '%s_vault_mid' % run['mode']
        side_capture(run['stills']['mid_vault'], run['side'])
    limit = 3.4 if run['kind'] == 'vault' else 3.6
    if el >= limit:
        end_run()


def end_run():
    run = S['run']
    S['run'] = None
    S['rearm'] = True
    release_all()
    rows = run['rows']
    z0 = run['start_loc'][2]
    run['peak_rise_cm'] = round(max([r['z'] for r in rows] or [z0]) - z0, 1)
    run['peak_speed'] = round(max([r['speed'] for r in rows] or [0]), 1)
    run['life_at_start'] = rows[0].get('life') if rows else None
    run['life_at_end'] = rows[-1].get('life') if rows else None
    run['modes_seen'] = []
    for r in rows:
        if not run['modes_seen'] or run['modes_seen'][-1] != r.get('mode'):
            run['modes_seen'].append(r.get('mode'))
    run['wallrun_ticks'] = sum(1 for r in rows if r.get('wallrun'))
    run['wallrun_s'] = round(run['wallrun_ticks'] / 30.0, 2)
    run['walljump_lock_seen'] = any(r.get('wjlock') for r in rows)
    run['falling_reported'] = any(r.get('falling') for r in rows)
    run['montages'] = sorted({r['montage'] for r in rows if r.get('montage')} |
                             {'cls:' + r['cls_montage'] for r in rows if r.get('cls_montage')})
    run['hidden_ticks'] = sum(1 for r in rows if r.get('hidden'))
    if run['kind'] == 'vault' and rows:
        last = rows[-1]
        endp = V(last['x'], last['y'], last['z'])
        run['cleared'] = dot2(endp - run['face'], run['axis']) > R['setup']['barrier']['half_thick'] * 2 + 30
    for k in ('axis', 'face', 'side', 'n', 't', 'p'):
        if k in run:
            run[k] = vec(run[k])
    run['height_profile'] = [(r['t'], r['z']) for r in rows[::3]]
    run['rows'] = rows[::2][:120]
    R['passes'].setdefault(run['mode'], {})[run['kind']] = run
    save()


def plan():
    q = []

    def mode_pass(mode):
        def start(t):
            S['mode'] = mode
            console('LifeEngine %d' % (1 if mode == 'on' else 0))
            console('HoverStatus')

        q.append((0.5, start))
        for kind in ('vault', 'wall', 'angle'):
            q.append((0.8, lambda t, k=kind: start_run(k)))
            q.append((0.6, lambda t: None))  # settle; run_tick starts the input on the next tick
            q.append(('run', None))
        q.append((0.5, lambda t: console('HoverStatus')))

    mode_pass('on')
    mode_pass('off')
    q.append((0.5, lambda t: finish()))
    S['queue'] = q


# ------------------------------------------------------------------------------------------------------ harvest
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
    pick = lambda tag, n=30: [l[-200:] for l in lines if tag in l][-n:]  # noqa: E731
    for tag in ('HOVER_PARKOUR_YIELD', 'HOVER_PARKOUR_RESUME', 'HOVER_PARKOUR_LAUNCH', 'HOVER_PARKOUR_WALLRUN'):
        R['log'][tag] = {'count': len([l for l in lines if tag in l]), 'samples': pick(tag, 12)}
    R['log']['life_engine'] = pick('LIFE_ENGINE', 30)
    R['log']['hover_state'] = pick('HOVER_STATE', 6)
    R['log']['patch_present'] = any('HOVER_PARKOUR_' in l for l in lines)


def summarise():
    s = {}
    for mode in ('on', 'off'):
        ps = R['passes'].get(mode, {})
        for kind in ('vault', 'wall', 'angle'):
            r = ps.get(kind, {})
            s['%s_%s' % (mode, kind)] = {k: r.get(k) for k in (
                'note', 'peak_rise_cm', 'peak_speed', 'cleared', 'wallrun_s', 'walljump_lock_seen', 'modes_seen',
                'life_at_start', 'life_at_end', 'falling_reported', 'hidden_ticks')}
        s['%s_wallrun_any' % mode] = any((ps.get(k) or {}).get('wallrun_ticks') for k in ('wall', 'angle'))
    s['yields'] = R['log'].get('HOVER_PARKOUR_YIELD', {}).get('count')
    s['resumes'] = R['log'].get('HOVER_PARKOUR_RESUME', {}).get('count')
    s['launch_handoffs'] = R['log'].get('HOVER_PARKOUR_LAUNCH', {}).get('count')
    s['zombies_removed'] = S['zombies_removed']
    s['wall_source'] = R['setup'].get('wall', {}).get('source')
    s['barrier_source'] = (R['setup'].get('barrier') or {}).get('source')
    R['summary'] = s
    on_runs = [R['passes'].get('on', {}).get(k, {}) for k in ('wall', 'angle')]
    # Success: with the solver on the template wall runs (as it does with it off), the solver was driving when each
    # run began, and it is driving again after landing (resumed).
    R['ok'] = bool(s['on_wallrun_any']) and bool(s['off_wallrun_any']) and \
        all(r.get('life_at_start') for r in on_runs if r) and any(r.get('life_at_end') for r in on_runs if r) and \
        (s['yields'] or 0) > 0 and (s['resumes'] or 0) > 0 and not R['errors']


def finish():
    if S['end']:
        return
    release_all()
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def setup_world(p):
    origin = p.get_actor_location()
    fwd = norm2(p.get_actor_forward_vector())
    b = find_barrier(origin)
    w = find_wall(origin)
    if not w:
        w = spawn_wall(origin, fwd)
    R['setup'].update({'pawn': p.get_class().get_name(), 'start': vec(origin), 'life_active_at_start': p.is_life_engine_active(),
                       'barrier': {k: (vec(v) if isinstance(v, u.Vector) else v) for k, v in b.items()} if b else None,
                       'wall': {k: (vec(v) if isinstance(v, u.Vector) else v) for k, v in w.items()}})
    R['setup']['_barrier'] = b
    R['setup']['_wall'] = w


def tick(dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                if not S['done']:
                    S['done'] = True
                    R['setup'].pop('_barrier', None)
                    R['setup'].pop('_wall', None)
                    harvest_log()
                    summarise()
                    save()
                    print('PROVE_PARKOUR_DONE', json.dumps(R['summary'], default=str), flush=True)
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
            setup_world(p)
            save()
            plan()
            S['next'] = t
            return
        S['ticks'] += 1
        snap_tick()
        if S['run']:
            run_tick(t)
            return
        if S.get('rearm'):
            # A run just ended: the next step waits its own delay from now.
            S['rearm'] = False
            S['next'] = t + (S['queue'][0][0] if S['queue'] and S['queue'][0][0] != 'run' else 0)
            return
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            if delay == 'run':
                S['run'] = S.pop('staged_run', None)
            else:
                fn(t)
            if S['queue']:
                nd = S['queue'][0][0]
                S['next'] = t + (0 if nd == 'run' else nd)
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_PARKOUR_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
