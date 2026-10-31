"""ProveNukeAmmo.py - in-game receipt for owner playtest 2026-10-31 items 1 (Nuke presentation) and 6 (ammo pickups).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveNukeAmmo.py
      -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720 "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1"

Needs the HoverPickupFeedback patch built (D:/AFS_Comparisons/OtherItems_20261031/NukeAmmoReadability/apply_*.py).
PIE on L_NYC_Survival at 1280x720, test input isolated, fixed 1/30 s step, Vexa's ZE health refilled every tick.

  1. Waits for the director to put zombies on the street (4 alive, or whatever is alive after 45 s).
  2. Spawns BP_CyberPower_Nuke 1.6 m in front of Vexa and walks her onto it (teleport fallback after 2.5 s).
     Stills: two frames right after the pickup (white flash), one at 0.6 s real (banner).
     Records, per zombie alive at the pickup, its distance to the pickup and the real / game time it died
     (Python observation), plus the subsystem's own kill rows, the global time dilation over time, the flash alpha
     and banner state at each still.
  3. Spawns BP_CyberAmmo 3 m ahead (its BeginPlay floor-snaps), stills from 10 m and 3 m (readability), then walks
     Vexa onto it: the walk-over pickup, the toast, the reserve before / after. Stills of the toast.
  4. Optional: if the AHoverAmmoStation class is compiled, spawns one in front of her, aims at it, holds F and
     records the purchase (not part of ok: placement waits for the owner).
  5. Harvests HOVER_NUKE_* / HOVER_AMMO_* / HOVER_PICKUP_TOAST lines from the log.

Receipt: D:/AFS_Comparisons/OtherItems_20261031/NukeAmmoReadability/proof/proof.json (PROOF_OUT overrides).
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
NUKE_BP = '/Game/HoverPrototype/ZombieEngine/BP_CyberPower_Nuke.BP_CyberPower_Nuke_C'
AMMO_BP = '/Game/HoverPrototype/ZombieEngine/BP_CyberAmmo.BP_CyberAmmo_C'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/OtherItems_20261031/NukeAmmoReadability/proof')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 900
MIN_ZOMBIES = 4
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'nuke': {}, 'ammo': {}, 'station': {}, 'log': {},
     'stills': [], 'refills': 0}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'cam': None,
     'hold': set(), 'step': 0, 'step_t0': None, 'pending': [], 'tick': 0}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'


# ---------------------------------------------------------------- helpers
def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def api_err(what, e):
    msg = '%s: %s' % (what, str(e)[:200])
    if msg not in R['api_errors'] and len(R['api_errors']) < 60:
        R['api_errors'].append(msg)


def prop(obj, *names):
    if obj is None:
        return None
    for n in names:
        try:
            return obj.get_editor_property(n)
        except Exception:  # noqa: BLE001
            pass
    return None


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
    except Exception as e:  # noqa: BLE001
        api_err(cmd, e)


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def feedback():
    try:
        return u.HoverPickupFeedback.get_feedback(world())
    except Exception as e:  # noqa: BLE001
        api_err('get_feedback', e)
        return None


def fb(name, *args):
    f = feedback()
    try:
        return getattr(f, name)(*args) if f else None
    except Exception as e:  # noqa: BLE001
        api_err(name, e)
        return None


def ammo(p):
    try:
        pt = u.HoverPickupFeedback.get_pawn_ammo(p)
        return [pt.x, pt.y]
    except Exception as e:  # noqa: BLE001
        api_err('get_pawn_ammo', e)
        return None


def survival(p):
    c = prop(p, 'combat')
    return prop(c, 'survival') if c else None


def keep_vexa_alive(p):
    s = survival(p)
    if not s:
        return
    try:
        hp, mx = s.get_health(), s.get_max_health()
        if hp < mx:
            s.set_health(mx)
            R['refills'] += 1
    except Exception as e:  # noqa: BLE001
        api_err('keep_vexa_alive', e)


def zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    return list(u.GameplayStatics.get_all_actors_of_class(w, cls)) if cls else []


def alive(z):
    try:
        return z is not None and not z.is_actor_being_destroyed() and not z.get_editor_property('is_dead')
    except Exception:  # noqa: BLE001
        return False


def dist2d(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def load_cls(path):
    try:
        return u.load_class(None, path)
    except Exception as e:  # noqa: BLE001
        api_err('load_class ' + path, e)
        return None


def spawn(cls, loc, yaw=0.0):
    return u.HoverAuthoring.spawn_playtest_actor(cls, u.Transform(location=loc, rotation=u.Rotator(yaw=yaw)))


def snap_later(name, ticks=1, extra=None):
    """ReadPixels returns the frame already rendered, so a still is read `ticks` ticks after it is requested."""
    S['pending'].append([ticks, name, extra])


def snap_now(name, extra):
    fn = OUT / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    row = {'file': fn.name, 'nuke_age': fb('get_nuke_age'), 'flash_alpha': fb('get_flash_alpha'),
           'banner_visible': fb('is_banner_visible'), 'last_toast': fb('get_last_toast'),
           'toast_age': fb('get_last_toast_age'), 'reserve_flash_age': fb('get_reserve_flash_age')}
    if extra:
        row.update(extra)
    R['stills'].append(row)


def pending_tick():
    keep = []
    for item in S['pending']:
        item[0] -= 1
        if item[0] <= 0:
            snap_now(item[1], item[2])
        else:
            keep.append(item)
    S['pending'] = keep


def view_from(cam_loc, look_at):
    cam = S['cam']
    cam.set_actor_location_and_rotation(cam_loc, u.MathLibrary.find_look_at_rotation(cam_loc, look_at), False, False)
    S['pc'].set_view_target_with_blend(cam, 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


def view_pawn():
    S['pc'].set_view_target_with_blend(pawn(), 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


def dilation(w):
    try:
        return round(u.GameplayStatics.get_global_time_dilation(w), 3)
    except Exception as e:  # noqa: BLE001
        api_err('get_global_time_dilation', e)
        return None


# ---------------------------------------------------------------- steps (each returns True when done)
def step_wait_zombies(t, age):
    w, p = world(), pawn()
    live = [z for z in zombies(w) if alive(z)]
    near = min([dist2d(z.get_actor_location(), p.get_actor_location()) for z in live] or [1e9])
    R['nuke']['wait'] = {'alive': len(live), 'nearest_cm': round(near), 'waited_s': round(age, 1)}
    if (len(live) >= MIN_ZOMBIES and near < 1800) or (age > 45 and live):
        return True
    if age > 90:
        raise RuntimeError('no zombies alive after 90 s')
    return False


def step_spawn_nuke(t, age):
    w, p = world(), pawn()
    cls = load_cls(NUKE_BP)
    assert cls, 'BP_CyberPower_Nuke class missing'
    loc = p.get_actor_location() + p.get_actor_forward_vector() * 160.0
    nuke = spawn(cls, loc)
    assert nuke, 'Nuke spawn failed'
    S['nuke_actor'] = nuke
    S['nuke_loc'] = nuke.get_actor_location()
    tracked = []
    for z in zombies(w):
        if alive(z):
            tracked.append({'actor': z, 'name': z.get_name(), 'dist_cm': round(dist2d(z.get_actor_location(), loc)),
                            'died_real': None, 'died_game': None})
    S['tracked'] = tracked
    R['nuke']['spawned_at'] = vec(loc)
    R['nuke']['alive_at_spawn'] = len(tracked)
    R['nuke']['banner_field'] = str(prop(nuke, 'nuke_presentation').get_editor_property('banner_text')) \
        if prop(nuke, 'nuke_presentation') else None
    key('W', True)
    return True


def step_walk_onto_nuke(t, age):
    nuke_age = fb('get_nuke_age')
    if nuke_age is not None and nuke_age >= 0:
        key('W', False)
        S['t_pick_game'] = t
        R['nuke']['picked'] = True
        R['nuke']['teleported'] = S.get('nuke_teleported', False)
        R['nuke']['targets'] = fb('get_nuke_target_count')
        R['nuke']['dilation_rows'] = []
        w = world()
        # Stunned check: zombie speed right after the pickup.
        R['nuke']['speeds_after_pick'] = [round(math.hypot(z['actor'].get_velocity().x, z['actor'].get_velocity().y))
                                          for z in S['tracked'] if alive(z['actor'])][:12]
        R['nuke']['dilation_at_pick'] = dilation(w)
        snap_later('nuke_flash_a', 1)
        snap_later('nuke_flash_b', 2)
        return True
    if age > 2.5 and not S.get('nuke_teleported'):
        key('W', False)
        S['nuke_teleported'] = True
        pawn().set_actor_location(S['nuke_loc'] + u.Vector(0, 0, 60), False, True)
    if age > 4.0:
        raise RuntimeError('Nuke was not picked up (walk and teleport)')
    return False


def step_ripple(t, age):
    w = world()
    nuke_age = fb('get_nuke_age') or 0.0
    R['nuke']['dilation_rows'].append([round(nuke_age, 3), dilation(w)])
    for z in S['tracked']:
        if z['died_real'] is None and not alive(z['actor']):
            z['died_real'] = round(nuke_age, 3)
            z['died_game'] = round(t - S['t_pick_game'], 3)
    if nuke_age >= 0.6 and not S.get('banner_shot'):
        S['banner_shot'] = True
        snap_later('nuke_banner', 1)
    if nuke_age >= 1.6 and not S.get('banner_late_shot'):
        S['banner_late_shot'] = True
        snap_later('nuke_banner_late', 1)
    return nuke_age >= 2.6


def finish_nuke():
    rows = [{k: v for k, v in z.items() if k != 'actor'} for z in S['tracked']]
    R['nuke']['observed'] = rows
    try:
        R['nuke']['kill_rows_cpp'] = [[round(v.x), round(v.y, 3), round(v.z, 3)] for v in
                                      (fb('get_nuke_kill_rows') or [])]
    except Exception as e:  # noqa: BLE001
        api_err('kill_rows', e)
    R['nuke']['kills_cpp'] = fb('get_nuke_kill_count')
    R['nuke']['hidden_damage_numbers'] = fb('get_hidden_damage_numbers')
    R['nuke']['banner_text'] = fb('get_banner_text')
    died = [r for r in rows if r['died_real'] is not None]
    R['nuke']['died_observed'] = len(died)
    R['nuke']['ripple_span_real_s'] = round(max(r['died_real'] for r in died) - min(r['died_real'] for r in died), 3) \
        if len(died) > 1 else 0.0
    R['nuke']['dist_time_spearman'] = spearman([r['dist_cm'] for r in died], [r['died_real'] for r in died])
    cpp = R['nuke'].get('kill_rows_cpp') or []
    R['nuke']['dist_time_spearman_cpp'] = spearman([r[0] for r in cpp], [r[1] for r in cpp])
    dl = [d for _, d in R['nuke'].get('dilation_rows', []) if d is not None]
    R['nuke']['dilation_min'] = min(dl) if dl else None
    R['nuke']['dilation_final'] = dl[-1] if dl else None
    save()


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (sx * sy), 3) if sx and sy else None


def step_spawn_ammo(t, age):
    if age < 1.0:
        return False
    finish_nuke()
    p = pawn()
    cls = load_cls(AMMO_BP)
    assert cls, 'BP_CyberAmmo class missing'
    loc = p.get_actor_location() + p.get_actor_forward_vector() * 300.0
    pick = spawn(cls, loc, p.get_actor_rotation().yaw)
    assert pick, 'ammo pickup spawn failed'
    S['ammo_actor'] = pick
    R['ammo']['spawned_at'] = vec(pick.get_actor_location())
    R['ammo']['before'] = ammo(p)
    R['ammo']['toast_before'] = fb('get_last_toast')
    S['toast_age_before'] = fb('get_last_toast_age')
    return True


def step_ammo_stills(t, age):
    pick, p = S['ammo_actor'], pawn()
    if age < 0.5:
        return False
    loc = pick.get_actor_location()
    right = p.get_actor_right_vector()
    if not S.get('ammo_far'):
        S['ammo_far'] = True
        view_from(loc - right * 1000.0 + u.Vector(0, 0, 170), loc)
        snap_later('ammo_10m', 2, {'distance_cm': 1000})
        R['ammo']['mesh_z_samples'] = []
        return False
    if not S.get('ammo_near') and age > 0.8:
        S['ammo_near'] = True
        view_from(loc - right * 300.0 + u.Vector(0, 0, 120), loc)
        snap_later('ammo_3m', 2, {'distance_cm': 300})
        return False
    try:
        mesh = prop(pick, 'loot_static_mesh')
        if mesh:
            R['ammo']['mesh_z_samples'].append(round(mesh.get_world_location().z, 1))
    except Exception as e:  # noqa: BLE001
        api_err('mesh_z', e)
    if age > 1.4 and not S['pending']:
        z = R['ammo']['mesh_z_samples']
        R['ammo']['bob_range_cm'] = round(max(z) - min(z), 1) if z else None
        view_pawn()
        key('W', True)
        return True
    return False


def step_walk_onto_ammo(t, age):
    toast_age = fb('get_last_toast_age')
    toast = fb('get_last_toast') or ''
    # A toast raised during this step (its real age is below the step's game age plus a frame).
    fresh = toast_age is not None and 0 <= toast_age <= age + 0.05
    if fresh and 'AMMO' in toast.upper():
        key('W', False)
        p = pawn()
        R['ammo']['after'] = ammo(p)
        R['ammo']['toast'] = toast
        R['ammo']['picked_after_s'] = round(age, 2)
        R['ammo']['teleported'] = S.get('ammo_teleported', False)
        try:
            R['ammo']['pickup_gone'] = S['ammo_actor'].is_actor_being_destroyed()
        except Exception:  # noqa: BLE001
            R['ammo']['pickup_gone'] = True
        snap_later('ammo_toast', 1)
        snap_later('ammo_toast_b', 12)
        return True
    if age > 3.0 and not S.get('ammo_teleported'):
        key('W', False)
        S['ammo_teleported'] = True
        try:
            pawn().set_actor_location(S['ammo_actor'].get_actor_location() + u.Vector(0, 0, 95), False, True)
        except Exception as e:  # noqa: BLE001
            api_err('ammo teleport', e)
    if age > 5.0:
        R['errors'].append('ammo pickup: no toast after walk + teleport')
        key('W', False)
        return True
    return False


def step_station(t, age):
    cls = getattr(u, 'HoverAmmoStation', None)
    if cls is None:
        R['station']['skipped'] = 'HoverAmmoStation class not compiled'
        return True
    p = pawn()
    st = S.get('station')
    if st is None:
        loc = p.get_actor_location() + p.get_actor_forward_vector() * 170.0 - u.Vector(0, 0, 90)
        st = spawn(cls, loc, p.get_actor_rotation().yaw + 180.0)
        S['station'] = st
        if not st:
            R['station']['error'] = 'spawn failed'
            return True
        s = survival(p)
        try:
            if s and s.get_gold() < 1000:
                s.apply_gold_delta(1000.0)
        except Exception as e:  # noqa: BLE001
            api_err('gold', e)
        R['station']['gold_before'] = s.get_gold() if s else None
        R['station']['ammo_before'] = ammo(p)
        R['station']['cost'] = st.get_ammo_cost() if hasattr(st, 'get_ammo_cost') else None
        try:
            look = u.MathLibrary.find_look_at_rotation(p.get_actor_location() + u.Vector(0, 0, 60), st.get_actor_location())
            S['pc'].set_control_rotation(look)
        except Exception as e:  # noqa: BLE001
            api_err('aim at station', e)
        return False
    if age > 0.4 and not S.get('station_hold'):
        S['station_hold'] = True
        c = prop(p, 'combat')
        R['station']['prompt'] = c.get_prompt() if c else None
        key('F', True)
        return False
    if age > 2.6:
        key('F', False)
        s = survival(p)
        R['station']['gold_after'] = s.get_gold() if s else None
        R['station']['ammo_after'] = ammo(p)
        R['station']['toast'] = fb('get_last_toast')
        return True
    return False


STEPS = [('wait_zombies', step_wait_zombies), ('spawn_nuke', step_spawn_nuke), ('walk_onto_nuke', step_walk_onto_nuke),
         ('ripple', step_ripple), ('spawn_ammo', step_spawn_ammo), ('ammo_stills', step_ammo_stills),
         ('walk_onto_ammo', step_walk_onto_ammo), ('station', step_station)]


# ---------------------------------------------------------------- log + verdict
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
    pick = lambda tag, n=12: [l[-220:] for l in lines if tag in l][-n:]  # noqa: E731
    for tag in ('HOVER_NUKE_BEGIN', 'HOVER_NUKE_SOUND', 'HOVER_NUKE_SHOCKWAVE', 'HOVER_NUKE_FEEL', 'HOVER_NUKE_SLOWMO',
                'HOVER_NUKE_SLOWMO_END', 'HOVER_NUKE_FLASH', 'HOVER_NUKE_BANNER', 'HOVER_NUKE_END',
                'HOVER_AMMO_PRESENT', 'HOVER_AMMO_AUTOPICKUP', 'HOVER_AMMO_PICKUP', 'HOVER_AMMO_PICKUP_SOUND',
                'HOVER_AMMO_TOAST', 'HOVER_PICKUP_TOAST', 'HOVER_AMMO_STATION', 'HOVER_AMMO_STATION_BUY'):
        R['log'][tag] = pick(tag + ' ', 6)
    R['log']['HOVER_NUKE_KILL'] = pick('HOVER_NUKE_KILL ', 40)
    R['log']['nuke_kill_lines'] = len([l for l in lines if 'HOVER_NUKE_KILL ' in l])


def summarise():
    n, a, lg = R['nuke'], R['ammo'], R['log']
    has = lambda tag: bool(lg.get(tag))  # noqa: E731
    targets = n.get('targets') or 0
    s = {
        'nuke_picked': bool(n.get('picked')), 'nuke_targets': targets, 'nuke_kills_cpp': n.get('kills_cpp'),
        'nuke_died_observed': n.get('died_observed'), 'ripple_span_real_s': n.get('ripple_span_real_s'),
        'dist_time_spearman': n.get('dist_time_spearman'), 'dist_time_spearman_cpp': n.get('dist_time_spearman_cpp'),
        'hidden_damage_numbers': n.get('hidden_damage_numbers'), 'banner_text': n.get('banner_text'),
        'dilation_min': n.get('dilation_min'), 'dilation_final': n.get('dilation_final'),
        'flash_still_alpha': max([r.get('flash_alpha') or 0 for r in R['stills'] if r['file'].startswith('nuke_flash')]
                                 or [0]),
        'banner_still_visible': any(r.get('banner_visible') for r in R['stills'] if r['file'] == 'nuke_banner.png'),
        'nuke_logs': {t: has(t) for t in ('HOVER_NUKE_BEGIN', 'HOVER_NUKE_SOUND', 'HOVER_NUKE_SHOCKWAVE',
                                          'HOVER_NUKE_FEEL', 'HOVER_NUKE_FLASH', 'HOVER_NUKE_BANNER', 'HOVER_NUKE_END')},
        'ammo_before': a.get('before'), 'ammo_after': a.get('after'), 'ammo_toast': a.get('toast'),
        'ammo_bob_range_cm': a.get('bob_range_cm'), 'ammo_teleported': a.get('teleported'),
        'ammo_logs': {t: has(t) for t in ('HOVER_AMMO_PRESENT', 'HOVER_AMMO_AUTOPICKUP', 'HOVER_AMMO_PICKUP',
                                          'HOVER_AMMO_PICKUP_SOUND', 'HOVER_AMMO_TOAST')},
        'station': {k: R['station'].get(k) for k in ('skipped', 'prompt', 'gold_before', 'gold_after', 'ammo_before',
                                                    'ammo_after', 'toast')},
    }
    R['summary'] = s
    reserve_up = bool(s['ammo_before'] and s['ammo_after'] and s['ammo_after'][1] > s['ammo_before'][1])
    # Fixed 2026-10-31: the ripple is a wave from the pickup (delay = RippleSeconds * dist / maxDist), so the
    # first-to-last span depends on how spread the targets are, not only on RippleSeconds. With every zombie
    # 13-18 m away the old 0.3 s span floor failed a correct ripple. Check each kill against the wave instead.
    cpp_rows = n.get('kill_rows_cpp') or []
    max_d = max([r[0] for r in cpp_rows] or [0])
    wave_err = max([abs(r[1] - .6 * r[0] / max_d) for r in cpp_rows] or [9]) if max_d else 9
    s['ripple_wave_max_error_s'] = round(wave_err, 3)
    s['ripple_last_kill_real_s'] = max([r[1] for r in cpp_rows] or [0])
    # Kills land on 1/30 s frames, so zombies a few cm apart tie and Spearman drops on ties: require the kill
    # times to be non-decreasing with distance instead (plus the per-kill wave error above).
    by_dist = sorted(cpp_rows, key=lambda r: r[0])
    s['ripple_monotone'] = all(b[1] >= a[1] - 1e-6 for a, b in zip(by_dist, by_dist[1:]))
    ripple_ok = targets < 3 or (s['ripple_monotone'] and wave_err <= .1 and .45 <= s['ripple_last_kill_real_s'] <= .9)
    R['checks'] = {
        'nuke_picked': s['nuke_picked'],
        'all_targets_died': targets > 0 and (s['nuke_kills_cpp'] or 0) >= targets,
        'ripple_outward': ripple_ok,
        'slowmo_and_restore': s['dilation_min'] is not None and s['dilation_min'] <= .31 and s['dilation_final'] == 1.0,
        'flash_seen': s['flash_still_alpha'] > .2,
        'banner_seen': s['banner_still_visible'],
        'nuke_logs': all(s['nuke_logs'].values()),
        'ammo_walkover': not s['ammo_teleported'] and s['ammo_logs']['HOVER_AMMO_AUTOPICKUP'],
        'ammo_logs': all(s['ammo_logs'].values()),
        'ammo_reserve_up': reserve_up,
        'ammo_toast_text': bool(s['ammo_toast'] and re.match(r'^\+\d+ ', s['ammo_toast'])),
    }
    R['ok'] = all(R['checks'].values()) and not R['errors']


def finish():
    if S['end']:
        return
    for k in list(S['hold']):
        key(k, False)
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


# ---------------------------------------------------------------- driver (slate post-tick, game time)
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
                    print('PROVE_NUKE_AMMO_DONE', R['ok'], json.dumps(R.get('checks'), default=str), flush=True)
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
                    api_err('configure_offscreen_display', e)
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
        keep_vexa_alive(p)
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            R['setup'] = {'pawn': p.get_class().get_name(), 'start': vec(p.get_actor_location()),
                          'mode': u.GameplayStatics.get_game_mode(w).get_class().get_name(),
                          'feedback': feedback() is not None,
                          'station_class': getattr(u, 'HoverAmmoStation', None) is not None,
                          'ammo_at_start': ammo(p)}
            if not R['setup']['feedback']:
                raise RuntimeError('UHoverPickupFeedback missing: build the NukeAmmoReadability patch first')
            save()
            return
        S['tick'] += 1
        pending_tick()
        if S['step'] >= len(STEPS):
            if not S['pending']:
                finish()
            return
        name, fn = STEPS[S['step']]
        if S['step_t0'] is None:
            S['step_t0'] = t
        if fn(t, t - S['step_t0']):
            R.setdefault('steps', []).append([name, round(t, 2)])
            S['step'] += 1
            S['step_t0'] = None
            save()
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_NUKE_AMMO_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
