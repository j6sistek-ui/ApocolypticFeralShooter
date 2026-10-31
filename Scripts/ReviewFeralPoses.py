"""Photograph the Feral Zombie clips on the pack's own UE4 mannequin to confirm the all-fours stance.

Run via Unreal -ExecutePythonScript with -RenderOffscreen. Changes only the unsaved Play world.
Output: Saved/Automation/ZombieEngine/feral_poses/<clip>_<phase>.png + review.json
"""
import unreal as u, json, time, traceback
from pathlib import Path
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'Automation/ZombieEngine/feral_poses'
out.mkdir(parents=True, exist_ok=True)
CLIPS = ['Run', 'Walk', 'Walk_02', 'Idle_01', 'Idle_Roar_01', 'LeapForward_Short', 'LeapForward_Full', 'Attack_LeftSwipe', 'StrongAttack_01', 'Reanimate', 'Death_01', 'Feasting_01', 'HitReact_01']
PHASES = [0.0, 0.33, 0.66]
MESH = '/Game/FeralZombie/Demo/Mannequin/Mesh/SK_Mannequin'
r = {'errors': [], 'shots': [], 'clips': {}}
s = {'start': time.monotonic(), 'play': False, 'stage': 0, 'busy': False, 'end': None, 'queue': [], 'mark': 0}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/HoverPrototype/Maps/L_CyberCity')


def finish():
    (out / 'review.json').write_text(json.dumps(r, indent=2, default=str))
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play(); s['end'] = time.monotonic()


def tick(dt):
    if s['busy']: return
    s['busy'] = True
    try:
        if s['end']:
            if time.monotonic() - s['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                u.unregister_slate_post_tick_callback(s['handle']); u.EditorPythonScripting.set_keep_python_script_alive(False); u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - s['start'] > 420: raise RuntimeError('Feral pose review timeout')
        if not s['play']:
            if time.monotonic() - s['start'] > 7: u.HoverAuthoring.start_playtest(); s['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w: return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn(): return
        gm = u.GameplayStatics.get_game_mode(w)
        if gm: gm.set_actor_tick_enabled(False)
        t = u.GameplayStatics.get_time_seconds(w)
        if s['stage'] == 0 and t > 8:
            u.HoverAuthoring.isolate_test_input(pc); p = pc.get_controlled_pawn(); base = p.get_actor_location()
            spot = base + u.Vector(0, 400, 0)
            tr = u.Transform(location=spot, rotation=u.Rotator(pitch=0, yaw=180))
            a = u.HoverAuthoring.spawn_playtest_actor(u.SkeletalMeshActor, tr)
            comp = a.skeletal_mesh_component
            mesh = u.load_asset(MESH); comp.set_skeletal_mesh_asset(mesh)
            comp.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
            s['actor'] = a; s['comp'] = comp
            camloc = spot + u.Vector(350, -350, 160)
            rot = u.MathLibrary.find_look_at_rotation(camloc, spot + u.Vector(0, 0, 60))
            c = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=camloc, rotation=rot))
            c.camera_component.set_field_of_view(55); pc.set_view_target_with_blend(c, 0); s['camera'] = c
            for name in CLIPS:
                seq = u.load_asset('/Game/FeralZombie/Animations/' + name)
                if seq:
                    r['clips'][name] = {'seconds': round(seq.get_editor_property('sequence_length'), 3)}
                    for ph in PHASES: s['queue'].append((name, seq, ph))
                else:
                    r['errors'].append('missing clip ' + name)
            s['mark'] = t; s['stage'] = 1
        elif s['stage'] == 1 and t - s['mark'] > 0.6:
            if s.get('pending'):
                name, ph = s['pending']; fn = out / f'{name}_{int(ph * 100):02d}.png'
                u.HoverAuthoring.capture_world_frame(str(fn)); r['shots'].append(str(fn)); s['pending'] = None
            if not s['queue']: finish(); return
            name, seq, ph = s['queue'].pop(0)
            comp = s['comp']; comp.set_animation(seq); comp.play(False); comp.set_play_rate(0.0)
            comp.set_position(ph * seq.get_editor_property('sequence_length'), False)
            s['pending'] = (name, ph); s['mark'] = t
    except Exception:
        r['errors'].append(traceback.format_exc()); finish()
    finally:
        s['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True); s['handle'] = u.register_slate_post_tick_callback(tick)
