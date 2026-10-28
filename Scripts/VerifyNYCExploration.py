"""CPU-only map/spawn/vehicle regression; no rendered-quality or controller-feel claim."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

OUT = Path('D:/AFS_Comparisons/NYC_20261028')
REPORT = {'errors': [], 'samples': [], 'events': [], 'checks': {}}
STATE = {'start': time.monotonic(), 'play': False, 'busy': False, 'index': 0, 'end': None}
AXES = {}
BUTTONS = {}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level('/Game/HoverPrototype/Maps/L_NYC_Explore')


def key(pc, name, value):
    BUTTONS[name] = value
    u.HoverAuthoring.test_key(pc, name, value, False)


def axis(pc, name, value):
    AXES[name] = value
    u.HoverAuthoring.test_key(pc, name, value, True)


def tap(pc, name):
    key(pc, name, 1)
    key(pc, name, 0)


def sample(pc, label):
    w = u.HoverAuthoring.get_playtest_world()
    p = pc.get_controlled_pawn()
    actors = u.GameplayStatics.get_all_actors_of_class(w, u.Actor)
    boards = [a for a in actors if any(c.get_name() == 'HoverMechanism'
              for c in a.get_components_by_class(u.PoseableMeshComponent))]
    enemies = [a.get_class().get_name() for a in actors if
               isinstance(a, (u.HoverZombie, u.HoverZombieRange, u.ZE_ZombieCharacter))]
    row = {'label': label, 'time': u.GameplayStatics.get_time_seconds(w),
           'world': w.get_name(), 'mode': u.GameplayStatics.get_game_mode(w).get_class().get_name(),
           'pawn': p.get_class().get_name(), 'location': list(p.get_actor_location().to_tuple()),
           'velocity': list(p.get_velocity().to_tuple()),
           'board_pitch': p.get_board_pitch() if isinstance(p, u.HoverPilot) else None,
           'mounted': isinstance(p, u.HoverPilot) and p.is_mounted(),
           'foot': isinstance(p, u.HoverPilot) and p.is_on_foot(),
           'truck': pc.get_test_truck().get_class().get_name() if pc.get_test_truck() else None,
           'bike': pc.get_test_bike() is not None, 'boards': len(boards), 'enemies': enemies}
    REPORT['samples'].append(row)
    assert not enemies, row
    assert row['mode'] == 'HoverExplorationGameMode', row
    assert not row['bike'] and row['truck'] and row['boards'] == 1, row
    if label == 'start':
        STATE['pilot'] = p
        assert row['foot'] and row['pawn'] == 'BP_Vexa_CLS_Parkour_C', row
        REPORT['checks']['vexa_board_truck_no_enemies'] = True
    if label == 'board_mounted': assert row['mounted'], row
    if label == 'board_moving':
        old = next(s for s in REPORT['samples'] if s['label'] == 'board_mounted')
        assert row['mounted'] and math.dist(row['location'], old['location']) > 150, row
        assert row['location'][2] > old['location'][2] + 100, row
    if label in ('board_exit', 'truck_exit'): assert row['foot'], row
    if label == 'truck_mounted': assert p == pc.get_test_truck(), row
    if label == 'truck_moved':
        old = next(s for s in REPORT['samples'] if s['label'] == 'truck_mounted')
        assert p == pc.get_test_truck() and math.dist(row['location'], old['location']) > 200, row
    (OUT / 'runtime.json').write_text(json.dumps(REPORT, indent=2))


def near_truck(pc):
    p = pc.get_controlled_pawn()
    truck = pc.get_test_truck()
    assert isinstance(p, u.HoverPilot) and p.is_on_foot() and truck
    p.set_actor_location(truck.get_actor_location() - truck.get_actor_right_vector() * 260 + u.Vector(0, 0, 160), False, True)
    p.character_movement.stop_movement_immediately()


def menu_check(pc):
    tap(pc, 'Gamepad_DPad_Up')
    assert pc.is_graphics_menu_open()
    STATE['world'] = u.HoverAuthoring.get_playtest_world()
    tap(pc, 'Gamepad_FaceButton_Bottom')
    assert not pc.is_graphics_menu_open()


def finish():
    if STATE['end']: return
    if not REPORT['errors']:
        assert STATE.get('world') == u.HoverAuthoring.get_playtest_world(), 'Applying the current level reloaded it'
    REPORT['completed'] = not REPORT['errors'] and len(REPORT['samples']) == 8
    (OUT / 'runtime.json').write_text(json.dumps(REPORT, indent=2))
    print('NYC_RUNTIME', REPORT['completed'], REPORT['errors'], flush=True)
    LEVEL.editor_request_end_play()
    STATE['end'] = time.monotonic()


EVENTS = [
    (5, 'start', lambda c: sample(c, 'start')),
    (6, 'mount', lambda c: key(c, 'Gamepad_FaceButton_Left', 1)),
    (7, 'release_mount', lambda c: key(c, 'Gamepad_FaceButton_Left', 0)),
    (9, 'board_mounted', lambda c: sample(c, 'board_mounted')),
    (9.2, 'lift_off', lambda c: axis(c, 'Gamepad_LeftY', .65)),
    (10, 'hold_height', lambda c: axis(c, 'Gamepad_LeftY', 0)),
    (10, 'thrust', lambda c: axis(c, 'Gamepad_RightTriggerAxis', .4)),
    (12, 'board_moving', lambda c: (sample(c, 'board_moving'), axis(c, 'Gamepad_RightTriggerAxis', 0))),
    (16, 'descend', lambda c: (STATE.update(descending=True), axis(c, 'Gamepad_LeftY', -.5))),
    (20, 'board_exit', lambda c: key(c, 'Gamepad_FaceButton_Left', 1)),
    (21, 'release_exit', lambda c: key(c, 'Gamepad_FaceButton_Left', 0)),
    (23, 'board_exit_check', lambda c: sample(c, 'board_exit')),
    (24, 'near_truck', near_truck),
    (26, 'enter_truck', lambda c: key(c, 'Gamepad_FaceButton_Left', 1)),
    (27, 'release_truck', lambda c: key(c, 'Gamepad_FaceButton_Left', 0)),
    (29, 'truck_mounted', lambda c: sample(c, 'truck_mounted')),
    (30, 'drive', lambda c: axis(c, 'Gamepad_RightTriggerAxis', .7)),
    (33, 'truck_moved', lambda c: (sample(c, 'truck_moved'), axis(c, 'Gamepad_RightTriggerAxis', 0), axis(c, 'Gamepad_LeftTriggerAxis', 1))),
    (35, 'stop_braking', lambda c: axis(c, 'Gamepad_LeftTriggerAxis', 0)),
    (36, 'exit_truck', lambda c: key(c, 'Gamepad_FaceButton_Top', 1)),
    (37, 'release_exit_truck', lambda c: key(c, 'Gamepad_FaceButton_Top', 0)),
    (39, 'truck_exit', lambda c: sample(c, 'truck_exit')),
    (42, 'menu', menu_check),
    (60, 'no_enemies_after_minute', lambda c: (sample(c, 'minute'), finish())),
]


def tick(dt):
    if STATE['busy']: return
    STATE['busy'] = True
    try:
        if STATE['end']:
            if time.monotonic() - STATE['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                u.unregister_slate_post_tick_callback(STATE['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - STATE['start'] > 600: raise RuntimeError('NYC runtime timeout')
        if not STATE['play']:
            if time.monotonic() - STATE['start'] > 5:
                u.HoverAuthoring.start_playtest()
                STATE['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w: return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn(): return
        if not STATE.get('isolated'):
            u.HoverAuthoring.isolate_test_input(pc)
            STATE['isolated'] = True
        if STATE.get('descending') and pc.get_controlled_pawn().get_actor_location().z < 240:
            axis(pc, 'Gamepad_LeftY', 0)
            STATE['descending'] = False
        for n, v in AXES.items(): u.HoverAuthoring.test_key(pc, n, v, True)
        for n, v in BUTTONS.items(): u.HoverAuthoring.test_key(pc, n, v, False)
        t = u.GameplayStatics.get_time_seconds(w)
        while STATE['index'] < len(EVENTS) and t >= EVENTS[STATE['index']][0]:
            _, label, fn = EVENTS[STATE['index']]
            STATE['index'] += 1
            REPORT['events'].append({'label': label, 'time': t})
            fn(pc)
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
        finish()
    finally:
        STATE['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
STATE['handle'] = u.register_slate_post_tick_callback(tick)
