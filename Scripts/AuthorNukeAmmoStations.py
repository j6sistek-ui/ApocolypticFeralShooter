"""AuthorNukeAmmoStations.py - places two or three NYC Survival ammo buy points near the start (NEEDS THE OWNER'S OK).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AuthorNukeAmmoStations.py [--apply] [--count 3] [--cost 250] [--remove]"
      -unattended -nosplash -NullRHI

Owner 2026-10-31: "no way to buy ammo". NYC Survival has no stations; Cyber City's three supply crates are vendor
AZE_WallBuyActor instances on SM_AmmoBox. This script reuses that actor through AHoverAmmoStation (an
AZE_WallBuyActor subclass in HoverPickupFeedback.h that refills whatever gun Vexa holds, for AmmoCost points).

Default is a dry run: it finds the spots and writes the report, and touches nothing. --apply spawns or moves the
stations (labels "AFS NYC Ammo Station NN", tag AFS_NYCAmmoStation) and saves the persistent map through
UHoverAuthoring.SaveSurvivalMap (which refuses while a vendor sublevel is dirty). --remove deletes them and saves.

Spot search: from the AFS_SurvivalStart player start, horizontal traces left and right at several offsets along the
street find a wall; the crate stands 45 cm off it on walkable floor (normal z > .8), with 180 cm of headroom, 300 cm
from every zombie spawner, 350 cm from the parked truck, 250-900 cm from the start, a nav path from the start, and
400 cm between crates. The crate faces the street. Report: D:/AFS_Comparisons/OtherItems_20261031/NukeAmmoReadability/stations.json
"""
import argparse
import json
import math
import sys
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path('D:/AFS_Comparisons/OtherItems_20261031/NukeAmmoReadability')
TAG = 'AFS_NYCAmmoStation'
LABEL = 'AFS NYC Ammo Station %02d'
PS_FALLBACK = (271, 5241, 162)
TRUCK = (200, 5900)
OFFSETS = [-300, 300, -500, 500, -700, 700, -150, 150]
REPORT = {'ok': False, 'errors': [], 'mode': None, 'start': None, 'candidates': [], 'chosen': [], 'actors': [],
          'saved': False}


def parse():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('--count', type=int, default=3)
    ap.add_argument('--cost', type=int, default=250)
    args, _ = ap.parse_known_args(sys.argv[1:])
    return args


ARGS = parse()


def trace(w, a, b):
    hit = u.SystemLibrary.line_trace_single(w, a, b, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                            u.DrawDebugTrace.NONE, True)
    if isinstance(hit, tuple):
        hit = next((x for x in hit if isinstance(x, u.HitResult)), None)
    if hit is None:
        return None
    tup = hit.to_tuple()
    # (blocking, initial_overlap, time, distance, location, impact_point, normal, impact_normal, ...)
    return {'blocking': bool(tup[0]), 'point': tup[5], 'normal': tup[7]} if tup[0] else None


def d2(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def find_start(w):
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart):
        if a.actor_has_tag('AFS_SurvivalStart'):
            return a.get_actor_location()
    return u.Vector(*PS_FALLBACK)


def candidates(w, start, spawners):
    rows = []
    for off in OFFSETS:
        for side in (1, -1):
            origin = u.Vector(start.x, start.y + off, start.z + 40)
            row = {'offset': off, 'side': side, 'reject': None}
            hit = trace(w, origin, origin + u.Vector(side * 700.0, 0, 0))
            if not hit or abs(hit['normal'].z) > .3:
                row['reject'] = 'no wall within 7 m'
                rows.append(row)
                continue
            n = hit['normal']
            pos = hit['point'] + u.Vector(n.x * 45.0, n.y * 45.0, 0)
            floor = trace(w, pos + u.Vector(0, 0, 100), pos - u.Vector(0, 0, 400))
            if not floor or floor['normal'].z < .8:
                row['reject'] = 'no walkable floor'
                rows.append(row)
                continue
            loc = floor['point']
            row['location'] = [round(loc.x), round(loc.y), round(loc.z)]
            row['yaw'] = round(math.degrees(math.atan2(n.y, n.x)), 1)
            xy = (loc.x, loc.y)
            if trace(w, loc + u.Vector(0, 0, 10), loc + u.Vector(0, 0, 190)):
                row['reject'] = 'no headroom'
            elif any(trace(w, loc + u.Vector(0, 0, 50), loc + u.Vector(dx, dy, 50))
                     for dx, dy in ((n.x * 60, n.y * 60), (-n.y * 50, n.x * 50), (n.y * 50, -n.x * 50))):
                row['reject'] = 'cramped (street side or flanks blocked within 50-60 cm)'
            elif min([d2(xy, s) for s in spawners] or [1e9]) < 300:
                row['reject'] = 'within 3 m of a zombie spawner'
            elif d2(xy, TRUCK) < 350:
                row['reject'] = 'truck clearance'
            elif not 250 <= d2(xy, (start.x, start.y)) <= 900:
                row['reject'] = 'not 2.5-9 m from the start'
            else:
                end = loc + u.Vector(n.x * 80.0, n.y * 80.0, 40)
                try:
                    path = u.HoverAuthoring.find_complete_city_path(w, start, end)
                    row['path_points'] = len(path)
                    if len(path) < 2:
                        row['reject'] = 'no nav path from the start'
                except Exception as e:  # noqa: BLE001
                    row['path_error'] = str(e)[:120]
            rows.append(row)
    return rows


def choose(rows):
    good = [r for r in rows if not r['reject']]
    good.sort(key=lambda r: abs(r['offset']))
    chosen = []
    for r in good:
        xy = r['location'][:2]
        if all(d2(xy, c['location'][:2]) >= 400 for c in chosen):
            chosen.append(r)
        if len(chosen) >= ARGS.count:
            break
    return chosen


def existing(w):
    cls = getattr(u, 'HoverAmmoStation', None)
    return [a for a in u.GameplayStatics.get_all_actors_of_class(w, cls) if a.actor_has_tag(TAG)] if cls else []


def main():
    REPORT['mode'] = 'remove' if ARGS.remove else ('apply' if ARGS.apply else 'dry-run')
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert level.load_level(MAP), 'load_level failed'
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    cls = getattr(u, 'HoverAmmoStation', None)
    REPORT['class_compiled'] = cls is not None
    actors_ss = u.get_editor_subsystem(u.EditorActorSubsystem)
    if ARGS.remove:
        for a in existing(w):
            REPORT['actors'].append({'removed': a.get_actor_label()})
            actors_ss.destroy_actor(a)
        REPORT['saved'] = bool(u.HoverAuthoring.save_survival_map(w))
        return
    start = find_start(w)
    REPORT['start'] = [round(start.x), round(start.y), round(start.z)]
    spawners = [(s.get_actor_location().x, s.get_actor_location().y)
                for s in u.GameplayStatics.get_all_actors_of_class(w, u.ZE_ZombieSpawnPoint)]
    REPORT['spawners'] = len(spawners)
    rows = candidates(w, start, spawners)
    REPORT['candidates'] = rows
    chosen = choose(rows)
    REPORT['chosen'] = chosen
    if len(chosen) < 2:
        REPORT['errors'].append('only %d spot(s) passed; place by hand or widen OFFSETS' % len(chosen))
    if not ARGS.apply:
        return
    assert cls is not None, 'HoverAmmoStation is not compiled: apply the NukeAmmoReadability patch and build first'
    have = {a.get_actor_label(): a for a in existing(w)}
    for i, row in enumerate(chosen, start=1):
        label = LABEL % i
        loc = u.Vector(*row['location'])
        rot = u.Rotator(yaw=row['yaw'])
        a = have.pop(label, None)
        if a is None:
            a = actors_ss.spawn_actor_from_class(cls, loc, rot)
            assert a, 'spawn failed for ' + label
            a.set_actor_label(label)
        else:
            a.set_actor_location_and_rotation(loc, rot, False, True)
        tags = list(a.tags)
        if TAG not in [str(t) for t in tags]:
            a.tags = tags + [u.Name(TAG)]
        a.set_editor_property('ammo_cost', ARGS.cost)
        REPORT['actors'].append({'label': label, 'location': row['location'], 'yaw': row['yaw'],
                                 'cost': a.get_editor_property('ammo_cost'), 'level': a.get_level().get_name()
                                 if hasattr(a, 'get_level') else None})
    for label, a in have.items():
        REPORT['actors'].append({'removed_extra': label})
        actors_ss.destroy_actor(a)
    REPORT['saved'] = bool(u.HoverAuthoring.save_survival_map(w))
    if not REPORT['saved']:
        REPORT['errors'].append('save_survival_map refused or failed')


def run():
    try:
        main()
    except Exception:  # noqa: BLE001
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and (REPORT['saved'] or REPORT['mode'] == 'dry-run')
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'stations.json').write_text(json.dumps(REPORT, indent=1, default=str))
        print('NUKE_AMMO_STATIONS', REPORT['mode'], REPORT['ok'], len(REPORT['chosen']), REPORT['errors'], flush=True)
        u.SystemLibrary.quit_editor()


run()
