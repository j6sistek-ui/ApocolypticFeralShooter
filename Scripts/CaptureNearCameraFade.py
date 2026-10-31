"""Photograph the near-camera dither fade (Scripts/AddZombieCameraFade.py) from the player's own survival camera.

In a Play world on L_NYC_Survival with the game mode tick disabled (no rounds, no spawns), every live zombie is
removed and a SkeletalMeshActor carrying the Kid LOD mesh (the body DA_Kid puts on the zombie, scaled exactly as
AHoverCyberZombie::BeginPlay scales it: Height / bounds height) is spawned 20 cm in front of the player's
third-person camera. The camera is the pawn's active camera as the camera manager reports it
(pc.player_camera_manager.get_camera_location()/get_camera_rotation()); the survival OTS arm is
SurvivalArmLength 300, SurvivalSocketOffset (0, 58, 42), SurvivalHipFOV 88 with camera lag (HoverPilot.h:101-106,
applied at HoverPilot.cpp:347-357). The body is then moved so its bounds centre sits on the view ray at
0, 40, 80 and 150 cm from the camera, and one viewport frame is captured per distance after the temporal
dither has had time to resolve. Collision is disabled on the actor, like the zombie mesh/capsule ignoring
ECC_Camera, so the spring arm never pulls in.

Expected with FadeOffset 15 / FadeLength 70: PixelDepth <= 15 cm fully dithered out, >= 85 cm fully visible.
PixelDepth is per pixel, so the near surface of the body fades before its centre does.

Changes only the unsaved Play world; saves nothing. Hashes the Kid mesh, DA_Kid, M_Kid_0 and the map before/after.
Output: D:/AFS_Comparisons/NYCSurvival_<YYYYMMDD>/near_camera_fade/ (fade_000cm.png ... and capture.json)

Run with a real renderer (NullRHI gives black frames), never concurrently with another editor run:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/CaptureNearCameraFade.py" -RenderOffscreen -unattended -nosplash
"""
import hashlib
import json
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d')) / 'near_camera_fade'
OUT.mkdir(parents=True, exist_ok=True)
MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
VAR = '/Game/HoverPrototype/ZombieEngine/Variants/Kid/'
KID_MESH = VAR + 'Optimized/SK_Kid_LODs'
KID_DA = VAR + 'DA_Kid'
KID_M0 = VAR + 'M_Kid_0'
SPAWN_FORWARD = 20.0
DISTANCES = [0, 40, 80, 150]
SETTLE = 0.8          # seconds of play time per shot so TSR/TAA resolves the dither
FADE_OFFSET, FADE_LENGTH = 15.0, 70.0
CONTENT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
WATCH = [KID_MESH, KID_DA, KID_M0, MAP]

r = {'errors': [], 'shots': [], 'hashes': {}, 'distances': DISTANCES, 'spawn_forward': SPAWN_FORWARD}
s = {'start': time.monotonic(), 'play': False, 'stage': 0, 'busy': False, 'end': None, 'queue': [], 'mark': 0, 'pending': None}


def file_of(package):
    base = str(CONTENT / package[len('/Game/'):])
    return Path(base + '.umap') if Path(base + '.umap').is_file() else Path(base + '.uasset')


def sha(package):
    f = file_of(package)
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None


def vec(v):
    return [round(x, 2) for x in v.to_tuple()]


def along(origin, fwd, d):
    return u.Vector(origin.x + fwd.x * d, origin.y + fwd.y * d, origin.z + fwd.z * d)


for p in WATCH:
    r['hashes'][p] = {'file': str(file_of(p)), 'before': sha(p)}
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing: run AuthorNYCSurvival.py first'
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP)


def finish():
    for p in WATCH:
        h = r['hashes'][p]
        h['after'] = sha(p)
        h['changed'] = h['before'] != h['after']
        if h['changed']:
            r['errors'].append('content file changed during a read-only capture: ' + p)
    r['ok'] = not r['errors'] and len(r['shots']) == len(DISTANCES)
    (OUT / 'capture.json').write_text(json.dumps(r, indent=2, default=str), encoding='utf-8')
    u.log_warning('CaptureNearCameraFade: ok=%s shots=%d/%d material=%s arm=%s errors=%d out=%s' % (
        r['ok'], len(r['shots']), len(DISTANCES), r.get('slot0_material'), r.get('arm'), len(r['errors']), OUT))
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    s['end'] = time.monotonic()


def clear_zombies(w):
    n = 0
    for z in u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie):
        z.destroy_actor(); n += 1
    return n


def place(pc, d):
    """Move the Kid so its bounds centre sits on the camera's view ray, d cm out; face the camera."""
    cam = pc.player_camera_manager.get_camera_location()
    rot = pc.player_camera_manager.get_camera_rotation()
    fwd = u.MathLibrary.get_forward_vector(rot)
    target = along(cam, fwd, d)
    a = s['actor']
    a.set_actor_location_and_rotation(target, u.Rotator(pitch=0, yaw=rot.yaw + 180, roll=0), False, True)
    origin, _ = a.get_actor_bounds(False)
    delta = u.Vector(target.x - origin.x, target.y - origin.y, target.z - origin.z)
    a.set_actor_location(u.Vector(target.x + delta.x, target.y + delta.y, target.z + delta.z), False, True)
    origin, extent = a.get_actor_bounds(False)
    centre = (origin - cam).length()
    return {'distance': d, 'camera': vec(cam), 'camera_rotation': [round(rot.pitch, 2), round(rot.yaw, 2), round(rot.roll, 2)],
            'body_centre': vec(origin), 'body_extent': vec(extent), 'centre_to_camera': round(centre, 2),
            'expected_fade_at_centre': round(min(1.0, max(0.0, (centre - FADE_OFFSET) / FADE_LENGTH)), 3)}


def tick(dt):
    if s['busy']: return
    s['busy'] = True
    try:
        if s['end']:
            if time.monotonic() - s['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                u.unregister_slate_post_tick_callback(s['handle']); u.EditorPythonScripting.set_keep_python_script_alive(False); u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - s['start'] > 300: raise RuntimeError('near camera fade capture timeout')
        if not s['play']:
            if time.monotonic() - s['start'] > 7: u.HoverAuthoring.start_playtest(); s['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w: return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn() or not pc.player_camera_manager: return
        gm = u.GameplayStatics.get_game_mode(w)
        if gm: gm.set_actor_tick_enabled(False)
        t = u.GameplayStatics.get_time_seconds(w)
        if s['stage'] == 0 and t > 8:
            u.HoverAuthoring.isolate_test_input(pc); p = pc.get_controlled_pawn()
            r['game_mode'] = gm.get_class().get_name() if gm else None
            r['zombies_removed'] = clear_zombies(w)
            r['pawn'] = {'class': p.get_class().get_name(), 'location': vec(p.get_actor_location())}
            arms = p.get_components_by_class(u.SpringArmComponent)
            cams = p.get_components_by_class(u.CameraComponent)
            r['arm'] = [{'name': a.get_name(), 'length': a.get_editor_property('target_arm_length'),
                         'socket_offset': vec(a.get_editor_property('socket_offset'))} for a in arms]
            r['cameras'] = [{'name': c.get_name(), 'active': c.is_active(), 'fov': c.get_editor_property('field_of_view')} for c in cams]
            r['view_target'] = pc.get_view_target().get_name() if pc.get_view_target() else None
            mesh = u.load_asset(KID_MESH); da = u.load_asset(KID_DA)
            assert mesh, 'missing ' + KID_MESH
            height = float(da.get_editor_property('height')) if da else 0.0
            b = mesh.get_bounds()
            scale = height / max(1.0, b.box_extent.z * 2.0) if height > 0 else 1.0
            r['kid'] = {'mesh': mesh.get_path_name(), 'da_mesh': da.get_editor_property('appearance_mesh').get_path_name() if da and da.get_editor_property('appearance_mesh') else None,
                        'height': height, 'bounds_extent': vec(b.box_extent), 'scale': round(scale, 4)}
            cam = pc.player_camera_manager.get_camera_location()
            fwd = u.MathLibrary.get_forward_vector(pc.player_camera_manager.get_camera_rotation())
            a = u.HoverAuthoring.spawn_playtest_actor(u.SkeletalMeshActor, u.Transform(location=along(cam, fwd, SPAWN_FORWARD)))
            comp = a.skeletal_mesh_component
            comp.set_skeletal_mesh_asset(mesh)  # a fresh actor has no override materials: slot materials render
            comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            a.set_actor_scale3d(u.Vector(scale, scale, scale))
            s['actor'] = a
            m0 = comp.get_material(0)
            r['slot0_material'] = m0.get_path_name() if m0 else None
            r['spawn'] = {'camera': vec(cam), 'location': vec(a.get_actor_location())}
            s['queue'] = list(DISTANCES); s['mark'] = t; s['stage'] = 1
        elif s['stage'] == 1 and t - s['mark'] > SETTLE:
            if s['pending']:
                shot = s['pending']; fn = OUT / ('fade_%03dcm.png' % shot['distance'])
                u.HoverAuthoring.capture_world_frame(str(fn)); shot['file'] = str(fn); r['shots'].append(shot); s['pending'] = None
            if not s['queue']: finish(); return
            clear_zombies(w)
            s['pending'] = place(pc, s['queue'].pop(0)); s['mark'] = t
    except Exception:
        r['errors'].append(traceback.format_exc()); finish()
    finally:
        s['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True); s['handle'] = u.register_slate_post_tick_callback(tick)
