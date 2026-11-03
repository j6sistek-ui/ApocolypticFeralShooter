"""Measure native NYC Survival rounds 1–2 at the player start or a pinned intersection.

Run one unattended offscreen editor at a time. From the AFS root in PowerShell:

    $env:AFS_DIRECTION_SITE = 'intersection'  # or 'start'
    $env:AFS_DIRECTION_RUN = 'before-01'      # use a new label for each repetition
    $out = "D:/AFS_Comparisons/NYCDirectionalSpawns/$env:AFS_DIRECTION_RUN/$env:AFS_DIRECTION_SITE"
    New-Item -ItemType Directory -Force $out | Out-Null
    & 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' `
      "$PWD/AFS.uproject" -unattended -RenderOffscreen -nosplash -NoSound -NoP4 -FixedSeed `
      -ResX=960 -ResY=540 '-LogCmds=LogTemp Verbose' "-abslog=$out/ue.log" `
      '-ExecCmds=r.Streaming.PoolSize 1200,sg.ShadowQuality 1,sg.GlobalIlluminationQuality 1,sg.PostProcessQuality 1,sg.EffectsQuality 1' `
      "-ExecutePythonScript=$PWD/Scripts/ProveNYCDirectionalSpawns.py"

Defaults to start and a timestamped run. AFS_DIRECTION_OUT overrides the receipt directory
within D:/AFS_Comparisons. AFS_DIRECTION_PIN overrides the November 3 intersection with a
JSON file containing {"at": [x, y, z]} in Unreal centimeters. Use the same pin for paired runs.
The stationary pawn is healed and approaching zombies are killed by the probe. The receipt
measures approach distribution, not combat, moving-player bias, or relocation acceptance.
"""
import json
import math
import os
import re
import time
import traceback
from collections import Counter
from pathlib import Path

import unreal as u


ROOT = Path("D:/AFS_Comparisons").resolve()
SITE = os.environ.get("AFS_DIRECTION_SITE", "start")
RUN = os.environ.get("AFS_DIRECTION_RUN") or time.strftime("%Y%m%d-%H%M%S")
OUT = Path(os.environ.get("AFS_DIRECTION_OUT") or ROOT / "NYCDirectionalSpawns" / RUN / SITE).resolve()
INTERSECTION = (1250, 5650, 10)  # Saved position from the paired native-map survey.
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
GAME = u.GameplayStatics
AUTHOR = u.HoverAuthoring
DIRECTIONS = (("E", 1, 0), ("N", 0, 1), ("W", -1, 0), ("S", 0, -1))


def xyz(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)]


def bearing(x, y):
    degrees = math.degrees(math.atan2(y, x)) % 360
    return {"deg": round(degrees, 2), "sector": DIRECTIONS[int((degrees + 45) // 90) % 4][0]}


def inward_crossing(a, b):
    """Paired-probe convention: an outside sample followed by an inside/on-circle sample."""
    if not math.hypot(*a) > 800 >= math.hypot(*b):
        return None
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    dot = a[0] * dx + a[1] * dy
    discriminant = dot * dot - length_sq * (a[0] ** 2 + a[1] ** 2 - 800 ** 2)
    t = max(0, min(1, (-dot - math.sqrt(max(0, discriminant))) / length_sq))
    return bearing(a[0] + t * dx, a[1] + t * dy)


def project(world, point):
    result = u.NavigationSystemV1.project_point_to_navigation(world, point, None, None, u.Vector(80, 80, 500))
    if isinstance(result, tuple):
        if False in result:
            return None
        result = next((v for v in result if isinstance(v, u.Vector)), None)
    if result is not None and max(abs(result.x), abs(result.y), abs(result.z)) < 1e7:
        return result
    return None


def route_entry(world, start, center):
    path = list(AUTHOR.find_complete_city_path(world, start, center))
    for a, b in zip(path, path[1:]):
        crossing = inward_crossing((a.x - center.x, a.y - center.y), (b.x - center.x, b.y - center.y))
        if crossing:
            return crossing["sector"]
    return None


def survey(world, center, pawn, targets):
    arms = []
    for side, dx, dy in DIRECTIONS:
        far = project(world, center + u.Vector(dx * 1000, dy * 1000, 0))
        if far is not None:
            path = list(AUTHOR.find_complete_city_path(world, center, far))
            if len(path) > 1 and sum((b - a).length() for a, b in zip(path, path[1:])) < 1325:
                arms.append(side)
    routes = Counter()
    for loc in targets.values():
        if 1400 <= math.hypot(loc[0] - center.x, loc[1] - center.y) <= 10000:
            side = route_entry(world, u.Vector(*loc), center)
            if side:
                routes[side] += 1
    selected = {"at": xyz(center), "clear_10m_arms": arms, "potential_preferred_source_paths_at_8m": dict(routes)}

    # Feasibility only. None of these candidate points become spawners in the proof.
    scout = []
    objects = [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1, u.ObjectTypeQuery.OBJECT_TYPE_QUERY2]
    for radius in (1600, 2300, 3000, 4000):
        for degrees in range(0, 360, 15):
            angle = math.radians(degrees)
            point = project(world, center + u.Vector(radius * math.cos(angle), radius * math.sin(angle), 0))
            if point is None:
                continue
            dx, dy = point.x - center.x, point.y - center.y
            if math.hypot(dx, dy) < 1400:
                continue
            side = route_entry(world, point, center)
            if side:
                row = {"at": xyz(point), "meters": round(math.hypot(dx, dy) / 100, 1),
                       "source_arm": bearing(dx, dy)["sector"], "path_entry_arm": side}
                try:
                    row["both_height_rays_blocked"] = all(
                        u.SystemLibrary.line_trace_single_for_objects(
                            world, center + u.Vector(0, 0, 160), point + u.Vector(0, 0, h),
                            objects, False, [pawn], u.DrawDebugTrace.NONE, True) is not None for h in (60, 170))
                except Exception as error:
                    row["trace_error"] = str(error)[:160]
                scout.append(row)
    return selected, scout


def sequence(sectors, possible):
    counts = Counter(sectors)
    longest = streak = 0
    previous = None
    for side in sectors:
        streak = streak + 1 if side == previous else 1
        longest = max(longest, streak)
        previous = side
    gaps = {}
    for side in sorted(possible):
        indices = [-1] + [i for i, s in enumerate(sectors) if s == side] + [len(sectors)]
        gaps[side] = max(b - a - 1 for a, b in zip(indices, indices[1:]))
    return {"ordered_sectors": sectors, "total": len(sectors), "counts": dict(counts),
            "largest_share": round(max(counts.values()) / len(sectors), 3) if sectors else None,
            "longest_same_arm_streak": longest, "largest_gap_other_arrivals_by_arm": gaps}


def summarize(receipt, lines):
    """Join the first native spawn per actor with the independent position samples."""
    actors, events = receipt["actors"], []
    seen = set()
    for line in lines:
        if "HOVER_SPAWN time=" not in line:
            continue
        event = dict(re.findall(r"([A-Za-z_]\w*)=(\S+)", line.split("HOVER_SPAWN ", 1)[1]))
        name = event.get("zombie")
        if not name or name in seen or event.get("round") not in ("1", "2"):
            continue
        seen.add(name)
        point = receipt["targets"].get(event.get("spawner"))
        if point and receipt["center_cm"]:
            center = receipt["center_cm"]
            side = bearing(point[0] - center[0], point[1] - center[1])
            event.update(source_sector=side["sector"], source_bearing=side["deg"])
        if name in actors:
            event["observed"] = actors[name]
        events.append(event)  # Includes eligibleMask, approachSide, travelXY and forwardWeight when emitted.

    possible = receipt.get("selected", {}).get("potential_preferred_source_paths_at_8m", {})
    def metrics(records, rows, quota):
        crossings = sorted((round(a["born_s"] + a["cross"]["seconds"], 2), name, a["cross"]["sector"])
                           for name, a in records if a.get("cross"))
        return {"expected_quota": quota, "seen": len(records), "actual_logged_spawns": len(rows),
                "joined": sum("observed" in e for e in rows), "first_crossings": len(crossings),
                "crossing_fraction": len(crossings) / len(records) if records else None,
                "first_sample_sector": dict(Counter(a["first"]["sector"] for _, a in records)),
                "born_inside_8m": sum(a["first_d"] <= 800 for _, a in records),
                "reached_3m": sum("contact" in a for _, a in records),
                "timed_out": sum(a.get("end") == "60s timeout" for _, a in records),
                "runtime_candidate_spawner_counts": [int(e["candidates"]) for e in rows if "candidates" in e],
                "source_sequence": sequence([e["source_sector"] for e in rows if "source_sector" in e], possible),
                "arrival_sequence": sequence([c[2] for c in crossings], possible)}

    rounds = {}
    for wave, info in receipt["waves"].items():
        observed = [(n, a) for n, a in actors.items() if a["round"] == int(wave)]
        rows = [e for e in events if e["round"] == str(wave)]
        rounds[wave] = {**info, "metrics": metrics(observed, rows, info["quota"])}
    return {"site": receipt["site"], "complete": receipt["completed"], "errors": receipt["errors"],
            "center": receipt["center_cm"], "rounds": rounds, "stills": receipt["stills"],
            "pooled": metrics(list(actors.items()), events, sum(w["quota"] for w in receipt["waves"].values())),
            "all_spawn_events": events}


class DirectionProbe:
    def __init__(self):
        if SITE not in ("start", "intersection") or ROOT not in OUT.parents:
            raise ValueError("Choose start or intersection and a new receipt folder below D:/AFS_Comparisons")
        OUT.mkdir(parents=True, exist_ok=True)
        if (OUT / "proof.json").exists():
            raise FileExistsError(f"Receipt already exists in {OUT}. Choose a new run.")
        self.receipt = {"site": SITE, "completed": False, "errors": [], "targets": {}, "actors": {},
                        "stills": [], "waves": {}, "center_cm": [],
                        "method": "Native rounds 1–2. Fixed 1/30 s, sampled every 0.1 s. First inward 8 m "
                                  "crossing. Removed 2 s after reaching 3 m or after 60 s alive. Pawn held and healed."}
        match = re.search(r'-abslog=(?:"([^"]+)"|([^\s"]+))', u.SystemLibrary.get_command_line(), re.I)
        self.log = Path(match.group(1) or match.group(2)) if match else Path(u.Paths.project_log_dir()) / "AFS.log"
        self.log_start = self.log.stat().st_size if self.log.is_file() else 0
        self.start_time = time.monotonic()
        self.busy = self.playing = self.ready = False
        self.end_time = self.pending_shot = None
        self.next_sample, self.last_save = -1.0, -5.0
        self.previous, self.shot_waves = {}, set()

    def save(self):
        for wave, row in self.receipt["waves"].items():
            records = [a for a in self.receipt["actors"].values() if a["round"] == wave]
            row.update(seen=len(records), first_sector=dict(Counter(a["first"]["sector"] for a in records)),
                       entry_8m=dict(Counter(a["cross"]["sector"] for a in records if "cross" in a)),
                       born_inside_8m=sum(a["first_d"] <= 800 for a in records),
                       arrived_3m=sum("contact" in a for a in records),
                       timed_out=sum(a.get("end") == "60s timeout" for a in records))
        temp = OUT / "proof.tmp"
        temp.write_text(json.dumps(self.receipt, indent=1), encoding="utf-8")
        temp.replace(OUT / "proof.json")

    def setup(self, world, pawn, controller):
        AUTHOR.isolate_test_input(controller)
        AUTHOR.set_playtest_fixed_step(True)
        r = self.receipt
        r["targets"] = {a.get_name(): xyz(a.get_actor_location())
                        for a in GAME.get_all_actors_with_tag(world, "AFS_NYCSpawn")}
        location = pawn.get_actor_location()
        r["start_cm"] = xyz(location)
        if SITE == "intersection":
            pin = os.environ.get("AFS_DIRECTION_PIN")
            values = json.loads(Path(pin).read_text(encoding="utf-8-sig"))["at"] if pin else INTERSECTION
            location = u.Vector(*values)
        center = project(world, location)
        if center is None:
            raise RuntimeError(f"Cannot project {SITE} onto the navigation mesh")
        if SITE == "intersection":
            half = pawn.capsule_component.get_scaled_capsule_half_height()
            pawn.set_actor_location(center + u.Vector(0, 0, half + 3), False, True)
            pawn.character_movement.stop_movement_immediately()
        r["selected"], r["unplaced_nav_scout"] = survey(world, center, pawn, r["targets"])
        self.center = pawn.get_actor_location()
        r["center_cm"] = xyz(self.center)
        r["facing_deg"] = round(controller.get_control_rotation().yaw, 2)
        self.health = pawn.get_component_by_class(u.ZE_SurvivalComponent)
        transform = u.Transform(location=self.center + u.Vector(0, 0, 1500), rotation=u.Rotator())
        self.camera = AUTHOR.spawn_playtest_actor(u.CameraActor, transform)
        self.ready = True
        self.save()

    def sample(self, world, pawn, controller, wave, now):
        center = pawn.get_actor_location()
        if math.hypot(center.x - self.center.x, center.y - self.center.y) > 35:
            raise RuntimeError("Held pawn displaced more than 35 cm")
        for zombie in GAME.get_all_actors_of_class(world, u.HoverNYCZombie):
            health = zombie.get_component_by_class(u.ZE_SurvivalComponent)
            if health and health.get_health() <= 0:
                continue
            name, at = zombie.get_name(), zombie.get_actor_location()
            rel = (at.x - center.x, at.y - center.y)
            distance = math.hypot(*rel)
            actors = self.receipt["actors"]
            if name not in actors:
                actors[name] = {"round": wave, "born_s": round(now, 2), "first": bearing(*rel),
                                "first_xyz": xyz(at), "first_d": round(distance, 1)}
            actor = actors[name]
            prev = self.previous.get(name)
            if prev and "cross" not in actor:
                entry = inward_crossing((prev[0] - center.x, prev[1] - center.y), rel)
                if entry:
                    actor["cross"] = {**entry, "seconds": round(now - actor["born_s"], 2)}
            self.previous[name] = (at.x, at.y)
            if distance <= 300 and "contact" not in actor:
                actor["contact"] = round(now, 2)
            if "end" not in actor and (now - actor.get("contact", now) > 2 or now - actor["born_s"] >= 60):
                actor["end"] = "arrival" if "contact" in actor else "60s timeout"
                GAME.apply_damage(zombie, 99999, controller, pawn, u.DamageType)
        if wave not in self.shot_waves and any(a.get("cross") for a in self.receipt["actors"].values()
                                               if a["round"] == wave):
            self.shot_waves.add(wave)
            eye = center + u.Vector(100, -100, 1450)
            self.camera.set_actor_location_and_rotation(eye, u.MathLibrary.find_look_at_rotation(eye, center), False, False)
            controller.set_view_target_with_blend(self.camera, 0.0)
            self.pending_shot = [wave, 3]

    def finish(self):
        self.end_time = time.monotonic()
        self.save()
        LEVEL.editor_request_end_play()

    def step(self):
        elapsed = time.monotonic() - self.start_time
        world = AUTHOR.get_playtest_world()
        if self.end_time is not None:
            if time.monotonic() - self.end_time > 2 and not world:
                lines = []
                if self.log.is_file():
                    with self.log.open("rb") as log:
                        log.seek(self.log_start)
                        lines = log.read().decode("utf-8", errors="replace").splitlines()
                result = summarize(self.receipt, lines)
                (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
                u.unregister_slate_post_tick_callback(self.handle)
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if elapsed > 1350:
            raise RuntimeError("Wall time limit")
        if not self.playing:
            if elapsed > 3:
                AUTHOR.configure_offscreen_display(976, 640)
                AUTHOR.start_playtest(960, 572)
                self.playing = True
            return
        if not world:
            return
        now = GAME.get_time_seconds(world)
        controller = GAME.get_player_controller(world, 0)
        pawn = controller.get_controlled_pawn() if controller else None
        if not pawn:
            return
        if not self.ready:
            if now > 1.5:
                self.setup(world, pawn, controller)
            return
        if self.pending_shot:
            self.pending_shot[1] -= 1
            if self.pending_shot[1] == 0:
                name = f"round_{self.pending_shot[0]}.png"
                AUTHOR.capture_world_frame(str(OUT / name))
                self.receipt["stills"].append(name)
                controller.set_view_target_with_blend(pawn, 0.0)
                self.pending_shot = None
        if self.health and self.health.get_health() < self.health.get_max_health():
            self.health.set_health(self.health.get_max_health())
        if now < self.next_sample:
            return
        self.next_sample = now + .09
        mode = GAME.get_game_mode(world)
        wave = mode.get_current_wave()
        if wave > 2:
            self.receipt["completed"] = True
            self.finish()
            return
        if now > 290:
            raise RuntimeError("Game-time limit; examine the spawn director log")
        if wave > 0:
            self.receipt["waves"].setdefault(wave, {"kind": str(mode.get_round_kind(wave)),
                                                    "quota": mode.get_round_quota()})
            self.sample(world, pawn, controller, wave, now)
            if now - self.last_save > 6:
                self.save()
                self.last_save = now

    def tick(self, _delta):
        if self.busy:
            return
        self.busy = True
        try:
            self.step()
        except Exception:
            self.receipt["errors"].append(traceback.format_exc())
            if self.end_time is None:
                self.finish()
            else:
                self.save()
                u.unregister_slate_post_tick_callback(self.handle)
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
        finally:
            self.busy = False


probe = DirectionProbe()
if not LEVEL.load_level("/Game/HoverPrototype/Maps/L_NYC_Survival"):
    raise RuntimeError("Cannot load NYC Survival")
u.EditorPythonScripting.set_keep_python_script_alive(True)
probe.handle = u.register_slate_post_tick_callback(probe.tick)
