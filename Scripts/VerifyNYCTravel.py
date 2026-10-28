"""Verify menu travel to NYC and back, including the original encounter mode."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

OUT = Path('D:/AFS_Comparisons/NYC_20261028')
R = {'errors': [], 'samples': []}
S = {'start': time.monotonic(), 'stage': 0, 'busy': False, 'play': False, 'end': None}
LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LE.load_level('/Game/JustBStudios/PostApo/Levels/PostApo')


def tap(pc, name):
    u.HoverAuthoring.test_key(pc, name, 1, False)
    u.HoverAuthoring.test_key(pc, name, 0, False)


def sample(w, pc, label, nyc):
    mode = u.GameplayStatics.get_game_mode(w).get_class().get_name()
    ranges = len(u.GameplayStatics.get_all_actors_of_class(w, u.HoverZombieRange))
    zombies = len(u.GameplayStatics.get_all_actors_of_class(w, u.HoverZombie))
    row = {'label': label, 'world': w.get_name(), 'mode': mode, 'ranges': ranges,
           'zombies': zombies, 'bike': pc.get_test_bike() is not None,
           'truck': pc.get_test_truck() is not None,
           'pawn': pc.get_controlled_pawn().get_class().get_name()}
    R['samples'].append(row)
    assert row['pawn'] == 'BP_Vexa_CLS_Parkour_C' and row['truck'], row
    if nyc:
        assert mode == 'HoverExplorationGameMode' and not ranges and not zombies and not row['bike'], row
    else:
        assert mode == 'HoverGameMode' and ranges == 1 and zombies > 0 and row['bike'], row
    (OUT / 'travel.json').write_text(json.dumps(R, indent=2))


def change(pc, direction):
    tap(pc, 'Gamepad_DPad_Up')
    assert pc.is_graphics_menu_open()
    tap(pc, 'Gamepad_DPad_Down')
    tap(pc, 'Gamepad_DPad_Down')
    tap(pc, direction)
    tap(pc, 'Gamepad_FaceButton_Bottom')


def finish():
    if S['end']: return
    R['completed'] = not R['errors'] and len(R['samples']) == 3
    (OUT / 'travel.json').write_text(json.dumps(R, indent=2))
    print('NYC_TRAVEL', R['completed'], R['errors'], flush=True)
    LE.editor_request_end_play()
    S['end'] = time.monotonic()


def tick(dt):
    if S['busy']: return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > 600: raise RuntimeError('Travel timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 5:
                u.HoverAuthoring.start_playtest()
                S['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w: return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn(): return
        if S.get('pc') != pc:
            S['pc'] = pc
            u.HoverAuthoring.isolate_test_input(pc)
        t = u.GameplayStatics.get_time_seconds(w)
        if S['stage'] == 0 and t > 8:
            sample(w, pc, 'postapo_before', False)
            change(pc, 'Gamepad_DPad_Left')
            S['stage'] = 1
        elif S['stage'] == 1 and 'NYC' in w.get_name() and t > 12:
            sample(w, pc, 'nyc_from_menu', True)
            change(pc, 'Gamepad_DPad_Right')
            S['stage'] = 2
        elif S['stage'] == 2 and 'PostApo' in w.get_name() and t > 8:
            sample(w, pc, 'postapo_return', False)
            finish()
    except Exception:
        R['errors'].append(traceback.format_exc())
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
