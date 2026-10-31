"""ProveKidSwarm.py - in-game receipt for the kid swarm clump (owner playtest 2026-10-31 item 5: "kid zombies bunch /
hoard in one spot" by the truck, recording 5:06 and 8:40).

  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "M:/UnrealProjects/AFS/AFS.uproject"
      -unattended -stdout -FullStdOutLogOutput -RenderOffscreen -nosplash -ResX=1280 -ResY=720
      "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.GlobalIlluminationQuality 1, sg.ReflectionQuality 1, sg.PostProcessQuality 1, sg.EffectsQuality 1"
      "-LogCmds=LogTemp Verbose" -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveKidSwarm.py

Set PROOF_OUT to keep a baseline apart (e.g. PROOF_OUT=D:/AFS_Comparisons/OtherItems_20261031/kid_swarm/baseline before
apply_kid_swarm.py is built, .../after once it is). Default: D:/AFS_Comparisons/OtherItems_20261031/kid_swarm/proof.

PIE on L_NYC_Survival at 1280x720, test input isolated (Vexa stands still at the survival start, facing south), fixed
1/30 s step. Three game seconds in, the first horde round (the Kid-only swarm, GetRoundKind == Horde) is forced by
calling the vendor StartWave UFUNCTION until GetCurrentWave reaches it; no zombie exists yet, so no earlier round
spawns anything. Vexa's ZE survival pool is refilled every tick (the mode forces mortal). Nothing is shot.

Every 0.25 s of game time, for 60 s, every live Kid is sampled (location, horizontal speed, 2D distance to Vexa,
current montage). Receipt fields:
  spawners_used / spawner_uses   HOVER_SPAWN log lines of the forced round (spawner object name, label added), with
                                 the nearest tagged spawner to each kid's first sample as a fallback
  kids.<name>.contact_s          seconds from first sample to the first sample within CONTACT_CM (300) of Vexa;
                                 inner_s the same for INNER_CM (150); None = never
  max_far_cluster                largest single-link group (links <= 150 cm) of kids farther than 600 cm from Vexa
                                 and at least 3 s old (a pack spawns together, so the newborn are left out)
  parked_fraction                kids that, farther than 600 cm from Vexa and with no montage playing, stayed within
                                 75 cm of one spot for more than 3 s; target < 0.10
  truck                          the parked pickup's bounds, the AFS_TruckNavBlocker actor (the patch), a nav
                                 projection at the truck centre and nav paths from the band spawners to Vexa, each
                                 tested against the truck footprint
  slots                          UHoverAttackSlotSubsystem stall / detour / reroute counters (after the patch)
  stills                         lane_t10 and lane_t25 (behind and above Vexa, looking up North Avenue at the truck
                                 lane), surround_t45 (close, round Vexa); each captured two ticks after the camera move
After PIE the -abslog (else Saved/Logs/AFS.log) is harvested for HOVER_SPAWN / _TRUCK_NAV / _SPREAD / _STALL /
_RELAX / _RELOCATE, HOVER_SLOT_STALL / _DETOUR / _DETOUR_FAILED and HOVER_APPROACH_REROUTE. Prints
PROVE_KID_SWARM_DONE <summary json> and quits. Changes only the unsaved Play world.
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
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/OtherItems_20261031/kid_swarm/proof')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
SAMPLE = 0.25          # game seconds between samples
WINDOW = 60.0          # game seconds sampled after the forced round starts
TIMEOUT = 1500         # wall seconds
CONTACT_CM, INNER_CM = 300.0, 150.0
FAR_CM = 600.0         # "away from Vexa"
PARK_S, PARK_MOVE_CM = 3.0, 75.0
LINK_CM, YOUNG_S = 150.0, 3.0
STILLS = [(10.0, 'lane'), (25.0, 'lane'), (45.0, 'surround')]
TARGETS = {'parked_fraction_max': 0.10, 'spawners_used_min': 3, 'contact_fraction_min': 0.9, 'kids_min': 8}

R = {'ok': False, 'errors': [], 'api_errors': [], 'notes': [], 'setup': {}, 'force': [], 'kids': {}, 'spawners': {},
     'truck': {}, 'slots': {}, 'stills': [], 'clusters': [], 'log': {}, 'summary': {}, 'refills': 0,
     'player_hp_min': None, 'claim': 'Rendered PIE at 1280x720, fixed 1/30 s step, Vexa held alive and still at the '
                                     'survival start; the first horde round forced through the vendor StartWave.'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'done': False, 'pc': None, 't_first': None,
     't0': None, 'next_sample': 0.0, 'cam': None, 'shot': None, 'stills_left': list(STILLS), 'probes': 0,
     'log_mark': None, 'target_round': None}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'
ZCLASS = getattr(u, 'HoverNYCZombie', None) or getattr(u, 'HoverCyberZombie')


# ---------------------------------------------------------------- helpers
def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)] if v is not None else None


def prop(obj, *names):
    if obj is None:
        return None
    for n in names:
        try:
            return obj.get_editor_property(n)
        except Exception:  # noqa: BLE001
            pass
        try:
            return getattr(obj, n)
        except Exception:  # noqa: BLE001
            pass
    return None


def call(obj, name, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception:  # noqa: BLE001
        return None


def api_err(what, e):
    msg = '%s: %s' % (what, str(e)[:200])
    if msg not in R['api_errors'] and len(R['api_errors']) < 60:
        R['api_errors'].append(msg)


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
    except Exception as e:  # noqa: BLE001
        api_err(cmd, e)


def d2(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def label(actor):
    try:
        return actor.get_actor_label()
    except Exception:  # noqa: BLE001
        return actor.get_name()


def log_path():
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return str(Path(u.Paths.project_log_dir()) / 'AFS.log')


def log_lines():
    p = Path(log_path())
    return p.read_text(encoding='utf-8', errors='replace').splitlines() if p.exists() else []


# ---------------------------------------------------------------- Vexa
def keep_vexa_alive(p):
    surv = None
    combat = prop(p, 'combat')
    if combat:
        surv = prop(combat, 'survival')
    if not surv:
        surv = call(p, 'get_component_by_class', u.ZE_SurvivalComponent)
    if not surv:
        api_err('keep_vexa_alive', 'no survival component')
        return
    hp, mx = call(surv, 'get_health'), call(surv, 'get_max_health')
    if hp is not None:
        R['player_hp_min'] = hp if R['player_hp_min'] is None else min(R['player_hp_min'], hp)
    if hp is not None and mx and hp < mx:
        try:
            surv.set_health(mx)
            R['refills'] += 1
        except Exception as e:  # noqa: BLE001
            api_err('set_health', e)


# ---------------------------------------------------------------- round forcing
def kind_name(gm, wave):
    return str(call(gm, 'get_round_kind', wave)).upper()


def force_horde(w, gm, t):
    target = next((n for n in range(1, 41) if 'HORDE' in kind_name(gm, n)), None)
    if target is None:
        raise RuntimeError('no horde round in 1..40 (DA_NYCEncounters Kid unset?)')
    S['target_round'] = target
    for z in u.GameplayStatics.get_all_actors_of_class(w, ZCLASS):
        z.destroy_actor()
        R['notes'].append('destroyed pre-round zombie %s' % z.get_name())
    S['log_mark'] = len(log_lines())
    guard = 0
    while (call(gm, 'get_current_wave') or 0) < target and guard < 50:
        guard += 1
        gm.start_wave()
        wave = call(gm, 'get_current_wave')
        R['force'].append({'wave': wave, 'kind': kind_name(gm, wave or 0), 'quota': call(gm, 'get_round_quota'),
                           'state': str(call(gm, 'get_wave_state'))})
    R['setup']['forced_round'] = target
    R['setup']['forced_kind'] = kind_name(gm, target)
    R['setup']['forced_quota'] = call(gm, 'get_round_quota')
    settings = call(gm, 'get_nyc_settings')
    R['setup']['nyc'] = {k: prop(settings, k) for k in ('horde_base', 'horde_per_round', 'horde_pack_size',
                                                        'near_min', 'band_inner', 'band_outer', 'kid_speed_tier',
                                                        'horde_interval_base', 'cooldown_min', 'recent_count')}
    S['t0'] = t
    S['next_sample'] = t


# ---------------------------------------------------------------- truck and nav
def nav_project(w, point, extent):
    try:
        res = u.NavigationSystemV1.k2_project_point_to_navigation(w, point, None, None, extent)
    except Exception as e:  # noqa: BLE001
        api_err('k2_project_point_to_navigation', e)
        return None
    if isinstance(res, tuple):
        ok = next((x for x in res if isinstance(x, bool)), True)
        v = next((x for x in res if isinstance(x, u.Vector)), None)
        return v if ok else None
    return res if isinstance(res, u.Vector) else None


def seg_hits_box(a, b, lo, hi):
    """2D segment a-b against the axis-aligned box lo..hi (Liang-Barsky)."""
    t0, t1 = 0.0, 1.0
    dx, dy = b[0] - a[0], b[1] - a[1]
    for p, q in ((-dx, a[0] - lo[0]), (dx, hi[0] - a[0]), (-dy, a[1] - lo[1]), (dy, hi[1] - a[1])):
        if abs(p) < 1e-9:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def truck_probe(w, tag):
    pc, p = S['pc'], pawn()
    truck = call(pc, 'get_test_truck')
    row = {'tag': tag, 't': round(u.GameplayStatics.get_time_seconds(w) - (S['t0'] or 0), 2)}
    if truck:
        try:
            origin, extent = truck.get_actor_bounds(True)
        except Exception as e:  # noqa: BLE001
            api_err('truck bounds', e)
            origin, extent = truck.get_actor_location(), u.Vector(260, 110, 100)
        row.update({'truck': truck.get_name(), 'center': vec(origin), 'extent': vec(extent),
                    'yaw': round(truck.get_actor_rotation().yaw, 1)})
        lo, hi = (origin.x - extent.x, origin.y - extent.y), (origin.x + extent.x, origin.y + extent.y)
        hit = nav_project(w, u.Vector(origin.x, origin.y, origin.z), u.Vector(15, 15, 400))
        row['nav_at_truck_center'] = vec(hit)  # None once the null-area modifier has cut the hole
        blockers = u.GameplayStatics.get_all_actors_with_tag(w, 'AFS_TruckNavBlocker')
        row['blockers'] = [{'name': b.get_name(), 'at': vec(b.get_actor_location())} for b in blockers]
        paths = []
        vl = p.get_actor_location()
        for name, info in sorted(R['spawners'].items()):
            if not info.get('band'):
                continue
            start = u.Vector(*info['at'])
            try:
                path = u.NavigationSystemV1.find_path_to_location_synchronously(w, start, vl)
                pts = list(prop(path, 'path_points') or [])
                partial = call(path, 'is_partial')
                length = call(path, 'get_path_length')
            except Exception as e:  # noqa: BLE001
                api_err('find_path', e)
                continue
            through = any(seg_hits_box((a.x, a.y), (b.x, b.y), lo, hi) for a, b in zip(pts, pts[1:]))
            paths.append({'spawner': name, 'label': info['label'], 'points': len(pts), 'partial': partial,
                          'length': round(length, 0) if isinstance(length, (int, float)) else length,
                          'through_truck': through})
        row['paths'] = paths
        row['paths_through_truck'] = sum(1 for x in paths if x['through_truck'])
    else:
        row['truck'] = None
    R['truck'].setdefault('probes', []).append(row)
    save()


def read_slots(w):
    try:
        sub = u.SubsystemBlueprintLibrary.get_world_subsystem(w, u.HoverAttackSlotSubsystem)
    except Exception as e:  # noqa: BLE001
        api_err('slot subsystem', e)
        return
    for k in ('get_stall_count', 'get_detour_count', 'get_approach_reroute_count', 'get_tokens_in_use',
              'get_peak_tokens_in_use', 'get_ring_moves'):
        v = call(sub, k)
        R['slots'][k] = v if v is not None else 'n/a (pre-patch build?)'


# ---------------------------------------------------------------- sampling
def is_kid(z):
    return 'KID' in str(call(z, 'get_role')).upper()


def alive(z):
    sc = prop(z, 'survival_component')
    hp = call(sc, 'get_health') if sc else None
    return hp is None or hp > 0


def nearest_spawner(loc):
    best = None
    for name, info in R['spawners'].items():
        d = math.hypot(info['at'][0] - loc.x, info['at'][1] - loc.y)
        if best is None or d < best[1]:
            best = (name, d)
    return best


def sample(w, t):
    p = pawn()
    vl = p.get_actor_location()
    el = round(t - S['t0'], 2)
    kids = []
    for z in u.GameplayStatics.get_all_actors_of_class(w, ZCLASS):
        if not is_kid(z) or not alive(z):
            continue
        loc, vel = z.get_actor_location(), z.get_velocity()
        mont = call(z, 'get_current_montage')
        name = z.get_name()
        k = R['kids'].get(name)
        if k is None:
            near = nearest_spawner(loc)
            k = R['kids'][name] = {'first_t': el, 'first_at': vec(loc), 'nearest_spawner': near[0] if near else None,
                                   'nearest_spawner_cm': round(near[1], 0) if near else None, 'contact_s': None,
                                   'inner_s': None, 'first_move_s': None, 'min_d2': None, 'track': []}
        dist = d2(loc, vl)
        speed = math.hypot(vel.x, vel.y)
        k['track'].append((el, round(loc.x, 1), round(loc.y, 1), round(dist, 0), round(speed, 0),
                           mont.get_name() if mont else None))
        k['min_d2'] = round(dist if k['min_d2'] is None else min(k['min_d2'], dist), 0)
        if k['first_move_s'] is None and speed > 100:
            k['first_move_s'] = round(el - k['first_t'], 2)
        if k['contact_s'] is None and dist <= CONTACT_CM:
            k['contact_s'] = round(el - k['first_t'], 2)
        if k['inner_s'] is None and dist <= INNER_CM:
            k['inner_s'] = round(el - k['first_t'], 2)
        kids.append((name, loc, dist, el - k['first_t']))
    # Single-link clusters among the far, not-newborn kids.
    far = [(n, l) for n, l, dist, age in kids if dist > FAR_CM and age >= YOUNG_S]
    seen, best = set(), []
    for i, (n, l) in enumerate(far):
        if n in seen:
            continue
        group, stack = [], [i]
        seen.add(n)
        while stack:
            j = stack.pop()
            group.append(far[j])
            for k2, (m, lm) in enumerate(far):
                if m not in seen and d2(far[j][1], lm) <= LINK_CM:
                    seen.add(m)
                    stack.append(k2)
        if len(group) > len(best):
            best = group
    if best and len(best) >= 2:
        cx = sum(l.x for _, l in best) / len(best)
        cy = sum(l.y for _, l in best) / len(best)
        R['clusters'].append({'t': el, 'size': len(best), 'center': [round(cx), round(cy)],
                              'distance_to_vexa': round(math.hypot(cx - vl.x, cy - vl.y))})
    return kids


def parked_seconds(track):
    """Longest run with every sample farther than FAR_CM, no montage, and within PARK_MOVE_CM of the run start."""
    best, where = 0.0, None
    n = len(track)
    for i in range(n):
        t_i, x_i, y_i, d_i, _, m_i = track[i]
        if d_i <= FAR_CM or m_i:
            continue
        j = i
        while j + 1 < n:
            t_j, x_j, y_j, d_j, _, m_j = track[j + 1]
            if d_j <= FAR_CM or m_j or math.hypot(x_j - x_i, y_j - y_i) > PARK_MOVE_CM:
                break
            j += 1
        if track[j][0] - t_i > best:
            best, where = track[j][0] - t_i, [x_i, y_i, t_i]
    return round(best, 2), where


# ---------------------------------------------------------------- stills
def begin_still(kind, el):
    p = pawn()
    vl = p.get_actor_location()
    if kind == 'lane':
        # Behind (south of) and above Vexa, looking up North Avenue past the truck toward Uptown.
        truck = call(S['pc'], 'get_test_truck')
        look = truck.get_actor_location() if truck else vl + u.Vector(0, 700, 0)
        cam = u.Vector(vl.x + 220, vl.y - 520, vl.z + 640)
    else:
        look = vl + u.Vector(0, 0, 40)
        cam = u.Vector(vl.x - 420, vl.y - 380, vl.z + 360)
    rot = u.MathLibrary.find_look_at_rotation(cam, look)
    S['cam'].set_actor_location_and_rotation(cam, rot, False, False)
    S['pc'].set_view_target_with_blend(S['cam'], 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    S['shot'] = {'file': OUT / ('%s_t%02d.png' % (kind, int(el))), 'loc': cam, 'rot': rot, 'ticks': 0, 'kind': kind,
                 't': round(el, 2)}


def shot_tick():
    sh = S['shot']
    if not sh:
        return
    S['cam'].set_actor_location_and_rotation(sh['loc'], sh['rot'], False, False)
    sh['ticks'] += 1
    # ReadPixels returns the frame already rendered: capture after the moved camera has been drawn.
    if sh['ticks'] < 2:
        return
    try:
        u.HoverAuthoring.capture_world_frame(str(sh['file']))
        R['stills'].append({'file': sh['file'].name, 'kind': sh['kind'], 't': sh['t'], 'cam': vec(sh['loc'])})
    except Exception as e:  # noqa: BLE001
        R['errors'].append('capture %s: %s' % (sh['file'].name, e))
    S['shot'] = None
    S['pc'].set_view_target_with_blend(pawn(), 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


# ---------------------------------------------------------------- log + summary
SPAWN_RE = re.compile(r'HOVER_SPAWN time=([\d.]+) round=(\d+) spawner=(\S+) distance=(\S+) .*?candidates=(\d+) '
                      r'relaxCone=(\d)(?: zombie=(\S+) role=(\S+))?')


def harvest_log():
    lines = log_lines()
    R['log']['path'] = log_path()
    mark = S['log_mark'] or 0
    if len(lines) < mark:
        mark = 0  # rotated
    tail = lines[mark:]
    target = S['target_round']
    spawns = []
    for line in tail:
        m = SPAWN_RE.search(line)
        if m and int(m.group(2)) == target:
            spawns.append({'t': float(m.group(1)), 'spawner': m.group(3), 'distance': m.group(4),
                           'candidates': int(m.group(5)), 'relax': int(m.group(6)), 'zombie': m.group(7),
                           'role': m.group(8)})
    R['log']['spawns'] = spawns
    pick = lambda tag, n=12: [l[-220:] for l in tail if tag in l][-n:]  # noqa: E731
    count = lambda tag: sum(1 for l in tail if tag in l)  # noqa: E731
    for tag in ('HOVER_SPAWN_TRUCK_NAV', 'HOVER_SPAWN_SPREAD', 'HOVER_SPAWN_STALL', 'HOVER_SPAWN_RELAX',
                'HOVER_SPAWN_RELOCATE', 'HOVER_SPAWN_HORDE_PACK', 'HOVER_NYC_CROWD'):
        R['log'][tag] = {'count': count(tag), 'lines': pick(tag, 8)}
    # The truck blocker may be placed before the forced round (it runs from the first director tick).
    R['log']['HOVER_SPAWN_TRUCK_NAV_session'] = [l[-220:] for l in lines if 'HOVER_SPAWN_TRUCK_NAV' in l][-4:]
    for tag in ('HOVER_SLOT_STALL', 'HOVER_SLOT_DETOUR ', 'HOVER_SLOT_DETOUR_FAILED', 'HOVER_APPROACH_REROUTE',
                'HOVER_ZOMBIE_ROAR '):
        R['log'][tag.strip()] = {'count': count(tag), 'lines': pick(tag, 6)}


def median(values):
    values = sorted(values)
    return values[len(values) // 2] if values else None


def summarise():
    kids = R['kids']
    by_log = {}
    for s in R['log'].get('spawns', []):
        by_log[s['spawner']] = by_log.get(s['spawner'], 0) + 1
    by_near = {}
    for k in kids.values():
        if k['nearest_spawner']:
            by_near[k['nearest_spawner']] = by_near.get(k['nearest_spawner'], 0) + 1
    uses = by_log or by_near
    parked = {}
    for name, k in kids.items():
        secs, where = parked_seconds(k['track'])
        k['parked_s'], k['parked_at'] = secs, where
        if secs > PARK_S:
            parked[name] = {'seconds': secs, 'at': where}
        k['samples'] = len(k['track'])
        k['track'] = k['track'][::4][:60]  # thinned for the receipt
    n = len(kids)
    contact = [k['contact_s'] for k in kids.values() if k['contact_s'] is not None]
    clusters = sorted(R['clusters'], key=lambda c: -c['size'])
    probes = R['truck'].get('probes', [])
    last = probes[-1] if probes else {}
    R['summary'] = {
        'forced_round': S['target_round'], 'forced_kind': R['setup'].get('forced_kind'),
        'kids_seen': n,
        'spawners_used': len(uses), 'spawner_uses': {('%s (%s)' % (k, R['spawners'].get(k, {}).get('label', '?'))): v
                                                     for k, v in sorted(uses.items())},
        'spawner_source': 'log' if by_log else 'nearest-spawner fallback',
        'time_to_first_contact_s': {name: k['contact_s'] for name, k in sorted(kids.items())},
        'contact_fraction': round(len(contact) / n, 3) if n else None,
        'contact_median_s': median(contact),
        'contact_max_s': max(contact) if contact else None,
        'first_move_median_s': median([k['first_move_s'] for k in kids.values() if k['first_move_s'] is not None]),
        'max_far_cluster': clusters[0]['size'] if clusters else (1 if n else 0),
        'max_far_cluster_at': clusters[0] if clusters else None,
        'parked_fraction': round(len(parked) / n, 3) if n else None,
        'parked_kids': parked,
        'truck_blocker_present': bool(last.get('blockers')),
        'nav_at_truck_center': last.get('nav_at_truck_center'),
        'paths_through_truck': last.get('paths_through_truck'),
        'slot_counters': R['slots'],
        'stall_log_count': R['log'].get('HOVER_SLOT_STALL', {}).get('count'),
        'detour_log_count': R['log'].get('HOVER_SLOT_DETOUR', {}).get('count'),
        'player_hp_min': R['player_hp_min'], 'refills': R['refills'],
        'targets': TARGETS,
    }
    s = R['summary']
    R['ok'] = (not R['errors'] and n >= TARGETS['kids_min'] and s['spawners_used'] >= TARGETS['spawners_used_min']
               and s['parked_fraction'] is not None and s['parked_fraction'] < TARGETS['parked_fraction_max']
               and (s['contact_fraction'] or 0) >= TARGETS['contact_fraction_min'])


def finish():
    if S['end']:
        return
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


# ---------------------------------------------------------------- driver
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
                    print('PROVE_KID_SWARM_DONE', json.dumps({k: v for k, v in R['summary'].items()
                                                              if k not in ('time_to_first_contact_s', 'parked_kids')},
                                                             default=str), flush=True)
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
        p = pc.get_controlled_pawn()
        if S['pc'] is None:
            S['pc'] = pc
            S['t_first'] = t
            return
        keep_vexa_alive(p)
        gm = u.GameplayStatics.get_game_mode(w)
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            vl = p.get_actor_location()
            for sp in u.GameplayStatics.get_all_actors_with_tag(w, 'AFS_NYCSpawn'):
                loc = sp.get_actor_location()
                dist = d2(loc, vl)
                R['spawners'][sp.get_name()] = {'label': label(sp), 'at': vec(loc), 'distance_to_vexa': round(dist),
                                                'band': 1400 <= dist <= 10000}
            R['setup'].update({'pawn': p.get_class().get_name(), 'game_mode': gm.get_class().get_name(),
                               'vexa': vec(vl), 'vexa_yaw': round(p.get_actor_rotation().yaw, 1),
                               'wave_before': call(gm, 'get_current_wave'), 'state_before': str(call(gm, 'get_wave_state')),
                               'spawners': len(R['spawners']),
                               'band_spawners': sorted(v['label'] for v in R['spawners'].values() if v['band'])})
            truck_probe(w, 'before_round')
            force_horde(w, gm, t)
            save()
            return
        if S['shot']:
            shot_tick()
            return
        el = t - S['t0']
        if el >= WINDOW:
            truck_probe(w, 'end')
            read_slots(w)
            finish()
            return
        if S['probes'] == 0 and el >= 2.0:
            S['probes'] = 1
            truck_probe(w, 'round_t2')
        if t >= S['next_sample'] - 1e-4:
            S['next_sample'] = t + SAMPLE
            sample(w, t)
        if S['stills_left'] and el >= S['stills_left'][0][0]:
            _, kind = S['stills_left'].pop(0)
            begin_still(kind, el)
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_KID_SWARM_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
