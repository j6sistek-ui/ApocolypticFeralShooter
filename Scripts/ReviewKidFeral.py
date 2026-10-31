"""Preview the Kid zombie wearing the Feral clips: register the Feral UE4 skeleton as compatible with
SK_Kid_Skeleton (the same registration path the Cyber bodies use), then photograph the Kid mesh playing
Feral Run / Walk / Idle / pounce / Reanimate in a Play world.

Run via Unreal -ExecutePythonScript with -RenderOffscreen. Saves exactly one asset (SK_Kid_Skeleton) when the
registration is new; writes before/after hashes. Output: Saved/Automation/ZombieEngine/kid_feral/
"""
import unreal as u, json, time, traceback, hashlib
from pathlib import Path
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'Automation/ZombieEngine/kid_feral'
out.mkdir(parents=True, exist_ok=True)
content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
KID_MESH = '/Game/HoverPrototype/ZombieEngine/Variants/Kid/Optimized/SK_Kid_LODs'
KID_SKEL = '/Game/HoverPrototype/ZombieEngine/Variants/Kid/SK_Kid_Skeleton'
FERAL_SKEL = '/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton'
CLIPS = ['Run', 'Walk', 'Idle_01', 'LeapForward_Short', 'Attack_LeftSwipe', 'Reanimate', 'Death_01']
PHASES = [0.0, 0.33, 0.66]
r = {'errors': [], 'shots': [], 'registration': {}}
s = {'start': time.monotonic(), 'play': False, 'stage': 0, 'busy': False, 'end': None, 'queue': [], 'mark': 0}

# ---- registration (editor world, before PIE) ----
try:
    skel = u.load_asset(KID_SKEL); feral = u.load_asset(FERAL_SKEL)
    assert skel and feral, (skel, feral)
    f = content / (KID_SKEL[len('/Game/'):] + '.uasset')
    r['registration']['hash_before'] = hashlib.sha256(f.read_bytes()).hexdigest()
    compat = [str(x.get_path_name()) for x in (skel.get_editor_property('compatible_skeletons') or [])]
    r['registration']['compatible_before'] = compat
    if FERAL_SKEL + '.UE4_Mannequin_Skeleton' not in compat and not any('UE4_Mannequin_Skeleton' in c for c in compat):
        skel.add_compatible_skeleton(feral)
        u.EditorAssetLibrary.save_loaded_asset(skel, False)
        r['registration']['added'] = True
    else:
        r['registration']['added'] = False
    r['registration']['compatible_after'] = [str(x.get_path_name()) for x in (skel.get_editor_property('compatible_skeletons') or [])]
    r['registration']['hash_after'] = hashlib.sha256(f.read_bytes()).hexdigest()
except Exception:
    r['errors'].append(traceback.format_exc())
(out / 'review.json').write_text(json.dumps(r, indent=2, default=str))
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
        if time.monotonic() - s['start'] > 420: raise RuntimeError('kid feral review timeout')
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
            a = u.HoverAuthoring.spawn_playtest_actor(u.SkeletalMeshActor, u.Transform(location=spot, rotation=u.Rotator(pitch=0, yaw=180)))
            comp = a.skeletal_mesh_component; comp.set_skeletal_mesh_asset(u.load_asset(KID_MESH))
            comp.set_animation_mode(u.AnimationMode.ANIMATION_SINGLE_NODE)
            b = comp.get_local_bounds() if hasattr(comp, 'get_local_bounds') else None
            r['kid_bounds'] = str(b) if b else None
            s['comp'] = comp
            camloc = spot + u.Vector(200, -220, 110)
            rot = u.MathLibrary.find_look_at_rotation(camloc, spot + u.Vector(0, 0, 45))
            c = u.HoverAuthoring.spawn_playtest_actor(u.CameraActor, u.Transform(location=camloc, rotation=rot))
            c.camera_component.set_field_of_view(50); pc.set_view_target_with_blend(c, 0)
            for name in CLIPS:
                seq = u.load_asset('/Game/FeralZombie/Animations/' + name)
                if seq:
                    for ph in PHASES: s['queue'].append((name, seq, ph))
                else:
                    r['errors'].append('missing clip ' + name)
            s['mark'] = t; s['stage'] = 1
        elif s['stage'] == 1 and t - s['mark'] > 0.6:
            if s.get('pending'):
                name, ph = s['pending']; fn = out / f'kid_{name}_{int(ph * 100):02d}.png'
                u.HoverAuthoring.capture_world_frame(str(fn)); r['shots'].append(str(fn)); s['pending'] = None
            if not s['queue']: finish(); return
            name, seq, ph = s['queue'].pop(0)
            comp = s['comp']
            try:
                comp.set_animation(seq); comp.play(False); comp.set_play_rate(0.0)
                comp.set_position(ph * seq.get_editor_property('sequence_length'), False)
                s['pending'] = (name, ph)
            except Exception:
                r['errors'].append(f'{name}: ' + traceback.format_exc()); s['pending'] = None
            s['mark'] = t
    except Exception:
        r['errors'].append(traceback.format_exc()); finish()
    finally:
        s['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True); s['handle'] = u.register_slate_post_tick_callback(tick)
