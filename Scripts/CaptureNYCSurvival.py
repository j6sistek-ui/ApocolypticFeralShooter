"""Photograph L_NYC_Survival through its first five rounds: a chase camera behind Vexa plus her own view, every 15 s.

Run via Unreal -ExecutePythonScript with -RenderOffscreen (NullRHI gives black frames).
Changes only the unsaved Play world. Output: D:/AFS_Comparisons/NYCSurvival_<date>/captures/
"""
import unreal as u, json, time, traceback
from pathlib import Path
out = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d')) / 'captures'
out.mkdir(parents=True, exist_ok=True)
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
INTERVAL = 6.0
DURATION = 100.0
r = {'errors': [], 'shots': []}
s = {'start': time.monotonic(), 'play': False, 'stage': 0, 'busy': False, 'end': None, 'next': 0.0, 'n': 0, 'toggle': 0}
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing: run AuthorNYCSurvival.py first'
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP)


def finish():
    (out / 'capture.json').write_text(json.dumps(r, indent=2, default=str))
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play(); s['end'] = time.monotonic()


def place_chase(pc, cam):
    p = pc.get_controlled_pawn()
    if not p: return
    loc = p.get_actor_location(); fwd = p.get_actor_forward_vector()
    camloc = loc - fwd * 650 + u.Vector(0, 0, 320)
    cam.set_actor_location_and_rotation(camloc, u.MathLibrary.find_look_at_rotation(camloc, loc + u.Vector(0, 0, 60)), False, True)


def tick(dt):
    if s['busy']: return
    s['busy'] = True
    try:
        if s['end']:
            if time.monotonic() - s['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                u.unregister_slate_post_tick_callback(s['handle']); u.EditorPythonScripting.set_keep_python_script_alive(False); u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - s['start'] > 1200: raise RuntimeError('capture timeout')
        if not s['play']:
            if time.monotonic() - s['start'] > 7: u.HoverAuthoring.start_playtest(); s['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w: return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            if s['stage'] == 1 and s['n'] > 2: r['note'] = 'pawn gone (game over); finishing'; finish()
            return
        t = u.GameplayStatics.get_time_seconds(w)
        if s['stage'] == 0 and t > 4:
            u.HoverAuthoring.isolate_test_input(pc)
            c = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            c.camera_component.set_field_of_view(70); s['camera'] = c; s['t0'] = t; s['next'] = t; s['stage'] = 1
        elif s['stage'] == 1:
            el = t - s['t0']
            if el >= s['next'] - s['t0']:
                n = s['n']; zombies = len(u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie))
                gm = u.GameplayStatics.get_game_mode(w); wave = gm.get_current_wave() if gm and hasattr(gm, 'get_current_wave') else None
                # chase view
                place_chase(pc, s['camera']); pc.set_view_target_with_blend(s['camera'], 0)
                s['pending'] = ('chase', n, el, zombies, wave); s['next'] = t + INTERVAL; s['n'] += 1
            if s.get('pending') and t - (s['next'] - INTERVAL) > 0.4:
                kind, n, el, zombies, wave = s['pending']
                if kind == 'chase':
                    fn = out / f'round_{n:02d}_chase.png'; u.HoverAuthoring.capture_world_frame(str(fn))
                    r['shots'].append({'file': fn.name, 't': round(el, 1), 'zombies': zombies, 'wave': wave})
                    pc.set_view_target_with_blend(pc.get_controlled_pawn(), 0); s['pending'] = ('player', n, el, zombies, wave); s['swap'] = t
                elif kind == 'player' and t - s.get('swap', t) > 0.4:
                    fn = out / f'round_{n:02d}_player.png'; u.HoverAuthoring.capture_world_frame(str(fn)); u.HoverAuthoring.capture_playtest(str(out / f'round_{n:02d}_ui.png'))
                    s['pending'] = None
            if el > DURATION and not s.get('pending'): finish()
    except Exception:
        r['errors'].append(traceback.format_exc()); finish()
    finally:
        s['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True); s['handle'] = u.register_slate_post_tick_callback(tick)
