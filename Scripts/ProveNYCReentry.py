"""Check that one injured, stranded NYC zombie returns at full health and resumes chasing.

With no AFS editor open, use the rendered invocation from Docs/CONTINUITY.md with
-FixedSeed and -ExecutePythonScript=<project>/Scripts/ProveNYCReentry.py. Only the
unsaved PIE world is changed. Read ok and failed_checks in the timestamped JSON receipt.
"""
import json
import math
import time
import traceback
from pathlib import Path

import unreal as u


LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
AUTHOR = u.HoverAuthoring
GAME = u.GameplayStatics
OUT = Path("D:/AFS_Comparisons/NYCReentry") / time.strftime("%Y%m%d-%H%M%S")
OUT.mkdir(parents=True, exist_ok=False)
receipt = {"ok": False, "failed_checks": []}
state = {"started": time.monotonic(), "play": False, "busy": False}


def distance(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def wave_state(mode, actors):
    return {"wave": mode.get_current_wave(), "quota": mode.get_round_quota(),
            "remaining": mode.get_zombies_remaining(), "wave_kills": mode.get_zombies_killed_this_wave(),
            "total_kills": mode.get_total_zombies_killed(), "living": sorted(z.get_path_name() for z in actors)}


def strand(world, player, mode, actors, now):
    victim = min(actors, key=lambda z: z.get_name())
    # Real map floor surveyed north of the survival start, behind the held player's view.
    xy = u.Vector(293, 21279, player.get_actor_location().z)
    hit = u.SystemLibrary.line_trace_single_for_objects(
        world, xy + u.Vector(0, 0, 1300), xy - u.Vector(0, 0, 600),
        [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1, u.ObjectTypeQuery.OBJECT_TYPE_QUERY2],
        False, [player, victim], u.DrawDebugTrace.NONE, True)
    if not hit or not hit.to_tuple()[0]:
        raise RuntimeError("No supporting floor at the surveyed stranding point")
    floor = hit.to_tuple()[5]
    health = victim.get_component_by_class(u.ZE_SurvivalComponent)
    health.set_health(0.73 * health.get_max_health())
    receipt.update(actor=victim.get_path_name(), injured_hp=health.get_health(), max_hp=health.get_max_health(),
                   before=wave_state(mode, actors), stranded_at_s=now)
    state.update(victim=victim, health=health, initial_relocations=victim.get_editor_property("relocation_count"))
    victim.set_actor_location(floor + u.Vector(0, 0, victim.capsule_component.get_scaled_capsule_half_height() + 5),
                              False, True)
    receipt["stranded_cm"] = distance(victim.get_actor_location(), player.get_actor_location())
    if receipt["stranded_cm"] <= 12000 or not 0 < receipt["injured_hp"] < receipt["max_hp"]:
        raise RuntimeError("The controlled injury or distance precondition was not satisfied")


def finish():
    (OUT / "reentry.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
    print(f"PROVE_NYC_REENTRY ok={receipt['ok']} receipt={OUT / 'reentry.json'}", flush=True)
    state["ending"] = time.monotonic()
    LEVEL.editor_request_end_play()


def tick(_delta):
    if state["busy"]:
        return
    state["busy"] = True
    try:
        if "ending" in state:
            if time.monotonic() - state["ending"] > 2 and not AUTHOR.get_playtest_world():
                u.unregister_slate_post_tick_callback(state["handle"])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        elapsed = time.monotonic() - state["started"]
        if elapsed > 600:
            raise RuntimeError("Timed out waiting for a full first wave, native re-entry, or a live pawn")
        if not state["play"]:
            if elapsed > 3:
                AUTHOR.configure_offscreen_display(976, 640)
                AUTHOR.start_playtest(960, 572)
                state["play"] = True
            return
        world = AUTHOR.get_playtest_world()
        pc = GAME.get_player_controller(world, 0) if world else None
        player = pc.get_controlled_pawn() if pc else None
        if not player:
            return
        if "player_health" not in state:
            AUTHOR.isolate_test_input(pc)
            AUTHOR.set_playtest_fixed_step(True)
            pc.set_control_rotation(u.Rotator(roll=0, pitch=0, yaw=-90))
            state["player_health"] = player.get_component_by_class(u.ZE_SurvivalComponent)
        pool = state["player_health"]
        if pool.get_health() < pool.get_max_health():
            pool.set_health(pool.get_max_health())
        now = GAME.get_time_seconds(world)
        if now < state.get("next_sample", 25):
            return
        state["next_sample"] = now + 0.1
        mode = GAME.get_game_mode(world)
        actors = [z for z in GAME.get_all_actors_of_class(world, u.HoverNYCZombie)
                  if z.get_component_by_class(u.ZE_SurvivalComponent).get_health() > 0]
        if "victim" not in state:
            if mode.get_current_wave() == 1 and actors and len(actors) == mode.get_round_quota():
                strand(world, player, mode, actors, now)
            return
        victim = state["victim"]
        if victim not in actors:
            raise RuntimeError("The original wave actor died or was replaced")
        if victim.get_editor_property("relocation_count") <= state["initial_relocations"]:
            return
        remaining_cm = distance(victim.get_actor_location(), player.get_actor_location())
        if "reentry_at_s" not in receipt:
            health = state["health"]
            receipt.update(reentry_at_s=now, reentry_hp=health.get_health(), reentry_max_hp=health.get_max_health(),
                           after=wave_state(mode, actors), reentry_cm=remaining_cm, closest_cm=remaining_cm)
        receipt["closest_cm"] = min(receipt["closest_cm"], remaining_cm)
        if now - receipt["reentry_at_s"] >= 15:
            checks = {"restored_to_own_max": abs(receipt["reentry_hp"] - receipt["max_hp"]) < 0.01,
                      "max_health_unchanged": abs(receipt["reentry_max_hp"] - receipt["max_hp"]) < 0.01,
                      "same_actors_and_counters": receipt["before"] == receipt["after"],
                      "returned_closer": receipt["reentry_cm"] < receipt["stranded_cm"],
                      "continued_pursuit": receipt["reentry_cm"] - receipt["closest_cm"] > 100}
            receipt["failed_checks"] = [key for key, passed in checks.items() if not passed]
            receipt["ok"] = not receipt["failed_checks"]
            finish()
    except Exception:
        receipt["failed_checks"].append(traceback.format_exc())
        finish()
    finally:
        state["busy"] = False


assert LEVEL.load_level("/Game/HoverPrototype/Maps/L_NYC_Survival")
u.EditorPythonScripting.set_keep_python_script_alive(True)
state["handle"] = u.register_slate_post_tick_callback(tick)
