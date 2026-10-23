"""Rendered PIE integration test. Only changes the unsaved play world.

Back up GameUserSettings.ini before launching; restore it after the process exits.
The Apply-button check intentionally exercises real preference persistence.
"""
import json
import time
import traceback
from pathlib import Path
import unreal as u

out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'HoverPrototype' / 'GraphicsReview'
out.mkdir(parents=True, exist_ok=True)
report = {'checks': [], 'errors': [], 'samples': []}
state = {'start': time.monotonic(), 'play': None, 'busy': False, 'index': 0}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')

def check(label, result):
    report['checks'].append({'label': label, 'passed': bool(result)})
    assert result, label

def key(pc, name, value=1, analog=False):
    u.HoverAuthoring.test_key(pc, name, value, analog)
    if not analog:
        u.HoverAuthoring.test_key(pc, name, 0, False)

def options(mode, fg=0):
    o = u.HoverGraphicsOptions()
    o.upscaling = mode
    o.frame_generation = fg
    return o

def sample(pc, label):
    g = pc.get_graphics_settings()
    report['samples'].append({'label': label, 'status': g.get_runtime_status(),
                              'mode': str(g.get_options().upscaling),
                              'fg': g.get_options().frame_generation})
    u.HoverAuthoring.capture_playtest(str(out / (label + '.png')))

def mode(pc, value, percent):
    g = pc.get_graphics_settings()
    check('Apply ' + str(value), g.apply(options(value), False))
    check('DLSS switch ' + str(value), u.DLSSLibrary.is_dlss_enabled() == (value != u.HoverUpscaling.NATIVE))
    check('Render scale ' + str(value), abs(u.SystemLibrary.get_console_variable_float_value('r.ScreenPercentage') - percent) < .1)

def open_menu(pc):
    state['pilot'] = pc.get_controlled_pawn()
    state['position'] = state['pilot'].get_actor_location()
    state['shots'] = state['pilot'].get_shots_fired()
    state['rotation'] = pc.get_control_rotation()
    key(pc, 'Gamepad_DPad_Up')
    check('Controller opens menu', pc.is_graphics_menu_open())
    check('Menu pauses game', u.GameplayStatics.is_game_paused(pc))
    key(pc, 'Gamepad_LeftY', 1, True)
    key(pc, 'Gamepad_RightX', 1, True)
    key(pc, 'Gamepad_RightTriggerAxis', 1, True)

def menu_input(pc):
    p = pc.get_controlled_pawn()
    check('Paused movement blocked', (p.get_actor_location() - state['position']).length() < .1)
    check('Paused firing blocked', p.get_shots_fired() == state['shots'])
    check('Paused look blocked', abs(pc.get_control_rotation().yaw - state['rotation'].yaw) < .1)
    key(pc, 'Gamepad_DPad_Right')
    sample(pc, '04_Menu_DLAA')

def apply_menu(pc):
    key(pc, 'Gamepad_FaceButton_Bottom')
    check('Controller Apply closes menu', not pc.is_graphics_menu_open())
    check('Apply resumes game', not u.GameplayStatics.is_game_paused(pc))
    check('Controller selected DLAA', pc.get_graphics_settings().get_options().upscaling == u.HoverUpscaling.DLAA)

def cancel_menu(pc):
    key(pc, 'F6')
    check('Keyboard opens menu', pc.is_graphics_menu_open())
    key(pc, 'Gamepad_DPad_Right')
    key(pc, 'Gamepad_FaceButton_Right')
    check('Controller cancel preserves DLAA', pc.get_graphics_settings().get_options().upscaling == u.HoverUpscaling.DLAA)
    check('Cancel unpauses', not u.GameplayStatics.is_game_paused(pc))
    key(pc, 'Gamepad_LeftY', 0, True)
    key(pc, 'Gamepad_RightX', 0, True)
    key(pc, 'Gamepad_RightTriggerAxis', 0, True)

def vehicle_menu(pc, truck):
    vehicle = pc.get_test_truck() if truck else pc.get_test_bike()
    check('Vehicle exists', vehicle is not None)
    pc.possess(vehicle)
    key(pc, 'Gamepad_DPad_Up')
    check(('Truck' if truck else 'Bike') + ' menu', pc.is_graphics_menu_open())
    state['vehicle'] = vehicle
    state['vehicle_pos'] = vehicle.get_actor_location()
    key(pc, 'Gamepad_RightTriggerAxis', 1, True)
    sample(pc, '06_Truck_Menu' if truck else '08_Bike_Menu')

def vehicle_close(pc):
    check('Paused vehicle stays put', (state['vehicle'].get_actor_location() - state['vehicle_pos']).length() < .1)
    key(pc, 'Gamepad_FaceButton_Right')
    check('Menu keeps vehicle possession', pc.get_controlled_pawn() == state['vehicle'])
    key(pc, 'Gamepad_RightTriggerAxis', 0, True)
    pc.possess(state['pilot'])

def fg_preview(pc):
    g = pc.get_graphics_settings()
    report['supported_fg'] = list(g.get_frame_generation_options())
    report['supported_upscaling'] = [str(x) for x in g.get_upscaling_options()]
    check('PIE identified', g.is_frame_generation_preview_only())
    if 2 in g.get_frame_generation_options():
        check('FG preference accepted', g.apply(options(u.HoverUpscaling.QUALITY, 2), False))
        check('FG disabled in PIE', u.StreamlineLibraryDLSSG.get_dlssg_mode() == u.StreamlineDLSSGMode.OFF)
    sample(pc, '10_FG_Editor_Guard')

def finish():
    (out / 'runtime.json').write_text(json.dumps(report, indent=2))
    u.unregister_slate_post_tick_callback(state['handle'])
    u.EditorPythonScripting.set_keep_python_script_alive(False)
    u.SystemLibrary.quit_editor()

events = [
    (3, lambda c: mode(c, u.HoverUpscaling.DLAA, 100)),
    (6, lambda c: sample(c, '01_DLAA')),
    (7, lambda c: mode(c, u.HoverUpscaling.QUALITY, 66.6667)),
    (10, lambda c: sample(c, '02_DLSS_Quality')),
    (11, lambda c: mode(c, u.HoverUpscaling.NATIVE, 100)),
    (14, lambda c: sample(c, '03_Native_TSR')),
    (15, open_menu), (17, menu_input), (19, apply_menu),
    (21, cancel_menu), (22, lambda c: sample(c, '05_Resumed_DLAA')),
    (23, lambda c: vehicle_menu(c, True)), (25, vehicle_close),
    (27, lambda c: vehicle_menu(c, False)), (29, vehicle_close),
    (31, fg_preview), (33, lambda c: finish())
]

def tick(dt):
    if state['busy']:
        return
    state['busy'] = True
    try:
        if time.monotonic() - state['start'] > 480:
            raise RuntimeError('Graphics regression timeout')
        if not state.get('requested'):
            if time.monotonic() - state['start'] > 8:
                u.HoverAuthoring.start_playtest()
                state['requested'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_graphics_settings():
            return
        if state['play'] is None:
            state['play'] = time.monotonic()
        elapsed = time.monotonic() - state['play']
        if state['index'] < len(events) and elapsed >= events[state['index']][0]:
            _, fn = events[state['index']]
            state['index'] += 1
            fn(pc)
    except Exception:
        report['errors'].append(traceback.format_exc())
        print('GRAPHICS_TEST_ERROR', report['errors'][-1])
        finish()
    finally:
        state['busy'] = False

u.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle'] = u.register_slate_post_tick_callback(tick)
