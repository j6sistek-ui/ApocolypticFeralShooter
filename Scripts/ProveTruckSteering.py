"""Crossroad pickup on a flat unsaved PostApo test platform. Run with UnrealEditor-Cmd,
-RenderOffscreen -FixedSeed -ExecutePythonScript=<this file>. Set AFS_STEER_OUT to a
fresh folder per build; repeat the same gamepad trials before and after. Speed is controlled
using gas/brake only, steering goes through the game's normal left-stick binding. The receipt
separates completion from passing the tuned handling targets. The 85 km/h full-stick trial
checks absolute stability; the November 3 stock run measured only partial stick at that speed.
"""
import json
import math
import os
from pathlib import Path
import statistics
import time
import traceback
import unreal as u


OUT = Path(os.environ.get("AFS_STEER_OUT") or
           f"D:/AFS_Comparisons/TruckSteering/{time.strftime('%Y%m%d-%H%M%S')}").resolve()
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
A, G = u.HoverAuthoring, u.GameplayStatics
TRIALS = [(20, 1.0), (45, .65), (45, -.65), (45, 1.0), (85, .35), (85, -.35), (85, 1.0)]
PAD = u.Vector(0, 0, 20000)
START = PAD + u.Vector(0, 0, 180)
R = {"map": "PostApo", "errors": [], "trials": [], "completed": False}
S = {"stage": "load", "wall": time.monotonic(), "trial": 0, "busy": False}


def save():
    tmp = OUT / "receipt.tmp"
    tmp.write_text(json.dumps(R, indent=1), encoding="utf-8")
    tmp.replace(OUT / "receipt.json")


def prop(obj, name, fallback=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return fallback


def axes(controller, steer=0.0, gas=0.0, brake=0.0):
    for key, value in (("Gamepad_LeftX", steer), ("Gamepad_RightTriggerAxis", gas),
                       ("Gamepad_LeftTriggerAxis", brake)):
        A.test_key(controller, key, float(value), True)


def inspect(move):
    rate = move.get_editor_property("steering_input_rate")
    setup = move.get_editor_property("steering_setup")
    speed_curve = setup.get_editor_property("steering_curve")
    wheels = list(move.get_editor_property("wheels"))
    return {"rise_rate": prop(rate, "rise_rate"), "fall_rate": prop(rate, "fall_rate"),
            "input_function": str(prop(rate, "input_curve_function")),
            "steering_type": str(prop(setup, "steering_type")),
            "speed_curve_mph": {str(mph): round(u.MathLibrary.get_runtime_float_curve_value(speed_curve, mph), 4)
                                for mph in (0, 20, 35, 50, 60, 120)},
            "wheels": [{"class": w.get_class().get_name(), "steers": prop(w, "affected_by_steering"),
                        "axle": str(w.get_axle_type()), "angle": prop(w, "max_steer_angle"),
                        "friction": prop(w, "friction_force_multiplier")} for w in wheels]}


def sample(truck, move, phase, seconds, stick):
    velocity, forward, right = truck.get_velocity(), truck.get_actor_forward_vector(), truck.get_actor_right_vector()
    wheels = move.get_editor_property("wheels")
    vx = velocity.x * forward.x + velocity.y * forward.y
    vy = velocity.x * right.x + velocity.y * right.y
    rot, pos = truck.get_actor_rotation(), truck.get_actor_location()
    return {"s": round(seconds, 4), "phase": phase, "stick": stick, "x": round(pos.x, 2), "y": round(pos.y, 2),
            "yaw": round(rot.yaw, 3), "roll": round(rot.roll, 3), "kph": round(math.hypot(vx, vy) * .036, 2),
            "slip_deg": round(math.degrees(math.atan2(vy, vx)), 2), "raw_steer": round(move.get_steering_input(), 3),
            "tire_deg": [round(w.get_steer_angle(), 3) for w in wheels],
            "grounded": sum(not w.is_in_air() for w in wheels)}


def summarize(rows, target):
    turn = [r for r in rows if r["phase"] == "turn"]
    settled = [r for r in turn if r["s"] >= .7]
    distance = yaw = 0.0
    for a, b in zip(settled, settled[1:]):
        distance += math.hypot(a["x"] - b["x"], a["y"] - b["y"]) / 100
        yaw += (b["yaw"] - a["yaw"] + 180) % 360 - 180
    speeds = [r["kph"] for r in turn]
    wheel_delay = next((r["s"] for r in turn if max(map(abs, r["tire_deg"])) >= 1.0), None)
    raw_delay = next((r["s"] for r in turn if abs(r["raw_steer"]) >= .1), None)
    recovery = [r for r in rows if r["phase"] == "release"]
    yaw_at = {}
    for seconds in (.5, 1., 2.):
        row = next((r for r in turn if r["s"] >= seconds), turn[-1])
        yaw_at[str(seconds)] = round((row["yaw"] - turn[0]["yaw"] + 180) % 360 - 180, 2)
    return {"entry_kph": speeds[0], "mean_turn_kph": round(statistics.mean(speeds), 2),
            "turn_speed_range_kph": [min(speeds), max(speeds)],
            "within_10pct_speed": all(abs(s - target) <= target * .1 for s in speeds),
            "latency_raw_s": raw_delay, "latency_wheel_1deg_s": wheel_delay,
            "peak_raw_stick": max(abs(r["raw_steer"]) for r in turn),
            "peak_wheel_deg": max(max(map(abs, r["tire_deg"])) for r in turn),
            "yaw_at_s": yaw_at,
            "steady_path_m": round(distance, 3), "steady_yaw_deg": round(yaw, 3),
            "radius_m": round(distance / abs(math.radians(yaw)), 3) if abs(yaw) > 1 else None,
            "peak_roll_deg": max(abs(r["roll"]) for r in turn + recovery),
            "peak_slip_deg": max(abs(r["slip_deg"]) for r in turn + recovery),
            "min_grounded": min(r["grounded"] for r in turn + recovery),
            "release_final_slip_deg": recovery[-1]["slip_deg"]}


def regression_checks(trials):
    # Flat-pad handling targets. Stock vs tuned evidence was collected with identical physical controls.
    by_input = {(t["target_kph"], t["stick"]): t["metrics"] for t in trials}
    city = [by_input[45, stick] for stick in (.65, -.65)]
    highway = [by_input[85, stick] for stick in (.35, -.35)]
    hard = by_input[45, 1.]
    emergency = by_input[85, 1.]
    return {
        "45kph_partial_radius_at_most_24m": all(m["within_10pct_speed"] and
                                                m["radius_m"] is not None and m["radius_m"] <= 24 for m in city),
        "45kph_partial_wheel_response_within_0.11s": all(m["latency_wheel_1deg_s"] is not None and
                                                         m["latency_wheel_1deg_s"] <= .11 for m in city),
        "45kph_full_at_least_9.5deg_in_first_half_second": hard["within_10pct_speed"] and
                                                          abs(hard["yaw_at_s"]["0.5"]) >= 9.5,
        "85kph_partial_grounded_and_settles": all(m["within_10pct_speed"] and m["min_grounded"] == 4 and
                                                  m["peak_roll_deg"] <= 6 and abs(m["release_final_slip_deg"]) <= 2
                                                  for m in highway),
        "85kph_full_emergency_absolute_stability": emergency["within_10pct_speed"] and
                                                   emergency["min_grounded"] >= 3 and emergency["peak_roll_deg"] <= 8 and
                                                   abs(emergency["release_final_slip_deg"]) <= 3,
    }


def reset_trial(truck, controller, now):
    axes(controller)
    truck.set_actor_location_and_rotation(START, u.Rotator(), False, True)
    mesh = truck.get_component_by_class(u.SkeletalMeshComponent)
    mesh.set_physics_linear_velocity(u.Vector())
    mesh.set_physics_angular_velocity_in_degrees(u.Vector())
    S.update(stage="settle", since=now, speed_hold=0., integral=0., prev_t=now)


def finish():
    save()
    LEVEL.editor_request_end_play()
    S.update(stage="end", since=time.monotonic())


def run():
    world = A.get_playtest_world()
    if S["stage"] == "end":
        if not world and time.monotonic() - S["since"] > 2:
            u.unregister_slate_post_tick_callback(S["handle"])
            u.EditorPythonScripting.set_keep_python_script_alive(False)
            u.SystemLibrary.quit_editor()
        return
    if time.monotonic() - S["wall"] > 650:
        raise RuntimeError("Wall-time limit")
    if S["stage"] == "load":
        if time.monotonic() - S["wall"] > 3:
            A.start_playtest(960, 540)
            S["stage"] = "enter"
        return
    if not world:
        return
    pc = G.get_player_controller(world, 0)
    if not pc or not pc.get_controlled_pawn():
        return
    now, pawn, truck = G.get_time_seconds(world), pc.get_controlled_pawn(), pc.get_test_truck()
    if not truck or now < 3:
        return
    if S["stage"] == "enter":
        A.isolate_test_input(pc)
        A.set_playtest_fixed_step(True)
        platform = A.spawn_test_platform(PAD)
        platform.set_actor_scale3d(u.Vector(1200, 1200, 1))
        pawn.set_actor_location(truck.get_actor_location() + u.Vector(0, -270, 180), False, True)
        pawn.character_movement.stop_movement_immediately()
        A.test_key(pc, "Gamepad_FaceButton_Left", 1.0, False)
        S.update(stage="mount", since=now)
        return
    if S["stage"] == "mount":
        if now - S["since"] < 1:
            return
        A.test_key(pc, "Gamepad_FaceButton_Left", 0.0, False)
        if pawn != truck:
            raise RuntimeError("Could not mount the Crossroad pickup through its normal entry action")
        S["move"] = truck.get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
        R.update(truck=truck.get_class().get_name(), setup=inspect(S["move"]))
        reset_trial(truck, pc, now)
        return
    if pawn != truck:
        raise RuntimeError("Lost possession of the pickup")
    move = S["move"]
    target, stick = TRIALS[S["trial"]]
    dt = now - S["prev_t"]
    if dt <= .0001:
        return
    S["prev_t"] = now
    elapsed = now - S["since"]
    if S["stage"] == "settle":
        axes(pc)
        if elapsed > 1.5 and all(not w.is_in_air() for w in move.get_editor_property("wheels")):
            S.update(stage="speed", since=now)
        elif elapsed > 8:
            raise RuntimeError("Truck did not settle on the test platform")
        return
    current = math.hypot(truck.get_velocity().x, truck.get_velocity().y) * .036
    error = target - current
    S["integral"] = max(-1., min(1., S["integral"] + .08 * error * dt))
    effort = S["integral"] + .18 * error
    gas, brake = min(1., max(0., effort)), min(1., max(0., -effort))
    if S["stage"] == "speed":
        axes(pc, 0, gas, brake)
        S["speed_hold"] = S["speed_hold"] + dt if abs(error) < max(1., target * .035) else 0.
        if S["speed_hold"] >= .35:
            S["stage"], S["since"] = "turn", now
            R["trials"].append({"target_kph": target, "stick": stick, "rows": []})
            axes(pc, stick, gas, brake)
            R["trials"][-1]["rows"].append(sample(truck, move, "turn", 0., stick))
        elif elapsed > 20:
            raise RuntimeError(f"Could not reach {target} kph at stable entry speed; measured {current:.1f}")
        return
    phase = S["stage"]
    active_stick = stick if phase == "turn" else 0.
    axes(pc, active_stick, gas, brake)
    trial = R["trials"][-1]
    trial["rows"].append(sample(truck, move, phase, elapsed, active_stick))
    if phase == "turn" and elapsed >= 2.0:
        axes(pc, 0., gas, brake)
        S.update(stage="release", since=now)
        if S["trial"] == 1:
            A.capture_world_frame(str(OUT / "45kph_partial_turn.png"))
    elif phase == "release" and elapsed >= 1.0:
        trial["metrics"] = summarize(trial["rows"], target)
        save()
        S["trial"] += 1
        if S["trial"] == len(TRIALS):
            R["completed"] = True
            R["checks"] = regression_checks(R["trials"])
            R["passed"] = all(R["checks"].values())
            if not R["passed"]:
                R["errors"].append("Failed handling targets: " + ", ".join(k for k, ok in R["checks"].items() if not ok))
            axes(pc)
            finish()
        else:
            reset_trial(truck, pc, now)


def tick(_dt):
    if S["busy"]:
        return
    S["busy"] = True
    try:
        run()
    except Exception:
        R["errors"].append(traceback.format_exc())
        finish()
    finally:
        S["busy"] = False


OUT.mkdir(parents=True, exist_ok=True)
if (OUT / "receipt.json").exists():
    raise FileExistsError(f"Choose a fresh output directory; {OUT}/receipt.json exists")
assert LEVEL.load_level("/Game/JustBStudios/PostApo/Levels/PostApo")
u.EditorPythonScripting.set_keep_python_script_alive(True)
S["handle"] = u.register_slate_post_tick_callback(tick)
