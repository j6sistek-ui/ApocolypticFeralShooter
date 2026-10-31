"""CaptureGuns.py - in-game proof of every rigged gun in Vexa's hands on L_NYC_Survival (GPU, real pixels).

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/CaptureGuns.py -RenderOffscreen -unattended -nosplash

Grows CaptureM4A1.py into a four-gun run. PIE at 1920x1080, test input isolated so Vexa stands at the survival
start, fixed 1/30 s step, zombies destroyed as they spawn so nothing hits her mid-reload. For each gun in order
M4A1 (her starting rifle, bound by DA_AFS_Ballista) then EM_11, EM_21 and EM_08 (swapped in with
AHoverPilot.apply_gun_rig on the held HoverCyberRifle, the same call OnEquipped makes) it captures stills:

  <gun>_a_rest           three-quarter from her right-front, nothing pressed
  <gun>_b_aim            RightMouseButton held
  <gun>_b_hands          close on both hands at the grips (hand_r->grip_r / hand_l->grip_l distances recorded)
  <gun>_b_grip_r / _l    (grip seat, 2026-10-31) the right fist on the pistol grip from the right-below and the
                         left-below (ahead of the grip), ~80 px per cm: the judge for GripSeatOffset / GripRotationOffset
  <gun>_c_hands_before / _c_hands_tK  (design C2) the hands camera on the FIRST press: ticks +1..+3 after it; the flash
                         luminance (mean luma, saturated fraction, central 60 %) and hand_l_to_target_cm /
                         palm_ahead_of_muzzle on these frames; summarise() reports flash_luma_ratio per gun and camera
  <gun>_c_before / _c_burstN_tK (box guns: 4 ticks after each trigger press, close on the ejection port)
  <gun>_c_shotK_tK / _c_afterK  (EM_08: three spaced shots, close on the cylinder, cylinder roll recorded)
  <gun>_d_hands_*        same reload, same marks three ticks later: second camera from Vexa's left-front at ~1.2 x gun
                         length (75 cm floor) on the centroid of both hands and the mag well, so the left hand's
                         path to the magazine and the still gun hand both read (hand_l_to_target_cm, hand_r_rot)
  <gun>_d_reload_*       UHoverCombatBridge.reload, frames at clip marks, camera following the mag well (or the
                         cylinder on the revolver) every tick
  then a VIDEO segment <gun>_gameplay: every tick to video/<gun>_gameplay/f_NNNN.png while a three-quarter
  camera follows the gun: aim, a burst (three taps on the revolver), reload. Stitched to MP4 afterwards by the
  caller (ffmpeg, 30 fps).

FLASH_GALLERY="/Game/path/NS_A,/Game/path/NS_B@1.0,..." (env) adds a flash gallery to every gun's c_ section: for each
candidate Niagara system, in order, AHoverPilot.set_muzzle_flash_override (the held rig's in-memory override, never
saved) and, with '@scale', the rig's MuzzleFlashScale in memory (no '@': the authored scale), 0.5 s settle, then ONE shot
under each of the hands, receiver (cylinder on EM_08), muzzle and wide (three-quarter, the game's view) cameras, frames
<gun>_g<index>_<assetname>_{hands,receiver,muzzle,wide}_{before,t1,t2}, RefillAmmo before each candidate so the revolver
never runs dry; the original override and scale are restored afterwards. summarise() writes the per-candidate luminance
metrics (same measure as design C2) under the 'gallery' key of capture.json. Without the env nothing about the run changes.
TRACER_TRIAL=/Game/ArrowTrail/FX/NS_ArrowTrail_Fire (env): on the M4A1 only, after the gallery, one shot under the chase
camera with the feel tier's tracer, then one with the rig's TracerOverride set in memory to this system (tier colour
through User.Color, TracerOverrideLifetime = TRACER_LIFETIME env, default 0.08 s): frames
M4A1_tracer_{tier,<name>}_{before,t1,t2,t3}; the rig fields are restored, nothing saved ('tracer_trial' in capture.json).
CAPTURE_OUT (env) moves the receipt / stills folder (default D:/AFS_Comparisons/GunProof_20261030).
CAPTURE_RES=1280x720 (env) runs the Play viewport at that size instead of 1920x1080 (the owner games on this GPU; the
luma ratios are resolution-independent, the stills just come smaller).

Then the M4A1 goes back on, plus the eye-level bonus view and the wide shots. Every still and video frame logs
numbers: hand-to-grip distances, moving-part component-space offsets from each gun's own rest pose, cylinder
roll vs AHoverPilot.gun_cylinder_angle / gun_cylinder_applied (the revolver snap-back check), ammo and clip.
Receipt: D:/AFS_Comparisons/GunProof_20261030/capture.json. Changes only the unsaved Play world.
"""
import json
import os
import math
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('CAPTURE_OUT') or 'D:/AFS_Comparisons/GunProof_20261030')
STILLS = OUT / 'stills'
VIDEO = OUT / 'video'
for d in (STILLS, VIDEO):
    d.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'capture.json'
RIGS = '/Game/HoverPrototype/Weapons/Rigs/'
_res = os.environ.get('CAPTURE_RES', '').lower().split('x')
WIDTH, HEIGHT = (int(_res[0]), int(_res[1])) if len(_res) == 2 and all(x.isdigit() for x in _res) else (1920, 1080)
TICK = 1.0 / 30.0  # HoverAuthoring.set_playtest_fixed_step
TIMEOUT = 2400
CONSOLE = ('r.MotionBlurQuality 0', 'r.DefaultFeature.MotionBlur 0', 'DisableAllScreenMessages')
VIEWPORT_TRIES = 4
# tag, rig asset, length cm, telemetry bones, reload marks (s of the 2.4 s clip), reload follow socket, action bone
GUNS = [
    ('M4A1', 'DA_GunRig_M4A1', 118.0, ['bolt_carrier', 'magazine', 'charging_handle', 'bolt_catch'],
     (0.3, 0.75, 1.5, 1.9, 2.3), 'mag_well', 'bolt_carrier'),
    ('EM11', 'DA_GunRig_EM11', 99.0, ['bolt_carrier', 'magazine'], (0.3, 0.75, 1.5, 1.9), 'mag_well',
     'bolt_carrier'),
    ('EM21', 'DA_GunRig_EM21', 34.0, ['charging_handle', 'magazine'], (0.3, 0.75, 1.5, 1.9), 'mag_well',
     'charging_handle'),
    ('EM08', 'DA_GunRig_EM08', 30.0, ['cylinder', 'crane', 'hammer', 'ejector_rod'], (0.3, 0.75, 1.2, 1.9, 2.3),
     'cylinder', 'cylinder'),
]

R = {'ok': False, 'errors': [], 'notes': [], 'setup': {}, 'frames': [], 'video': {}, 'cyl_trace': [], 'log': {},
     'summary': {}, 'api_errors': [], 'gallery': {}, 'tracer_trial': {}}


def gallery_entry(text):
    """'path' or 'path@scale': the candidate Niagara system and, optionally, the MuzzleFlashScale to shoot it at
    (None: the held rig's authored scale). NS_GunFire at the authored 3.0 / 1.5 is the rigs' default; a puff like
    NS_Simple_Core_Impact_1 wants ~1.0, so one gallery shows both at their own sizes."""
    path, _, scale = text.strip().partition('@')
    return {'path': path.strip(), 'scale': float(scale) if scale.strip() else None}


# Flash gallery candidates (see the docstring); empty = the run as it always was.
GALLERY = [gallery_entry(p) for p in os.environ.get('FLASH_GALLERY', '').split(',') if p.strip()]
# Tracer trial (see the docstring); empty = no trial.
TRACER = os.environ.get('TRACER_TRIAL', '').strip()
TRACER_LIFETIME = float(os.environ.get('TRACER_LIFETIME', '0.08'))
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None,
     'queue': [], 'next': None, 'rest': {}, 'done': False, 'ticks': 0, 'vp_tries': 0, 'vp_req': None,
     'follow': None, 'last_step_t': None, 'console': False, 'video': None, 'video_n': 0, 'trace_cyl': False,
     'gun': GUNS[0], 'zombies_removed': 0, 'framing': {}}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'
COMP = u.RelativeTransformSpace.RTS_COMPONENT


def save():
    RECEIPT.write_text(json.dumps(R, indent=1, default=str))


def vec(v):
    return [round(v.x, 2), round(v.y, 2), round(v.z, 2)] if v is not None else None


def prop(obj, *names):
    for n in names:
        try:
            return getattr(obj, n)
        except Exception:
            pass
        try:
            return obj.get_editor_property(n)
        except Exception:
            pass
    return None


def call(obj, name, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception:
        return None


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def gun_of(p):
    return prop(p, 'world_gun_skel')


def weapon_of(p):
    c = prop(p, 'combat')
    return call(c, 'get_weapon') if c else None


def reloading(p):
    c = prop(p, 'combat')
    try:
        return bool(c.is_reloading()) if c else None
    except Exception as e:
        R['api_errors'].append('combat.is_reloading: %s' % e)
        return None


def clip_name(p):
    try:
        inst = gun_of(p).get_anim_instance()
        a = inst.get_animation_asset() if inst else None
        return a.get_name() if a else None
    except Exception:
        return None


def viewport_size():
    try:
        v = u.HoverAuthoring.get_playtest_viewport_size()
        return [int(v.x), int(v.y)]
    except Exception as e:
        R['api_errors'].append('get_playtest_viewport_size: %s' % e)
        return None


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
        return True
    except Exception as e:
        R['api_errors'].append('%s: %s' % (cmd, e))
        return False


def stop_shakes():
    try:
        S['pc'].player_camera_manager.stop_all_camera_shakes(True)
    except Exception as e:
        R['api_errors'].append('stop_all_camera_shakes: %s' % e)


def gun_world(g, name):
    try:
        return g.get_socket_location(name)
    except Exception:
        return None


def gun_comp(g, name):
    try:
        return g.get_socket_transform(name, COMP).translation
    except Exception:
        return None


def gun_comp_rot(g, name):
    try:
        r = g.get_socket_transform(name, COMP).rotation.rotator()
        return [round(r.roll, 2), round(r.pitch, 2), round(r.yaw, 2)]
    except Exception:
        return None


def angle_deg(a, b):
    a = a.normal() if hasattr(a, 'normal') else a
    b = b.normal() if hasattr(b, 'normal') else b
    d = max(-1.0, min(1.0, a.x * b.x + a.y * b.y + a.z * b.z))
    return round(math.degrees(math.acos(d)), 1)


def dist(a, b):
    return round((a - b).length(), 2) if a is not None and b is not None else None


def clear_zombies(w):
    cls = getattr(u, 'ZE_ZombieCharacter', None)
    if not cls:
        return
    for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
        z.destroy_actor()
        S['zombies_removed'] += 1


def rig_name(p):
    r = call(p, 'get_gun_rig')
    return r.get_name() if r else None


def cylinder_state(p):
    g = gun_of(p)
    rot = gun_comp_rot(g, 'cylinder')
    return {'cyl_roll': rot[0] if rot else None, 'cyl_angle': prop(p, 'gun_cylinder_angle'),
            'cyl_applied': call(p, 'gun_cylinder_applied'), 'clip': clip_name(p)}


def sample(p, t, light=False):
    """Numbers behind each frame: grip alignment, moving parts vs rest, aim, visibility, ammo."""
    g = gun_of(p)
    m = p.mesh
    w = weapon_of(p)
    tag = S['gun'][0]
    row = {'t': round(t, 3), 'gun': tag, 'rig': rig_name(p), 'clip': clip_name(p), 'rigged': call(p, 'uses_rigged_gun'),
           'aiming': call(p, 'is_aiming')}
    if g:
        hand_r = m.get_socket_location('hand_r')
        hand_l = m.get_socket_location('hand_l')
        grip_r = gun_world(g, 'grip_r')
        grip_l = gun_world(g, 'grip_l')
        row.update({'gun_visible': call(g, 'is_visible'), 'gun_mesh': call(call(g, 'get_skeletal_mesh_asset'), 'get_name'),
                    'hand_r_to_grip_r_cm': dist(hand_r, grip_r), 'hand_l_to_grip_l_cm': dist(hand_l, grip_l)})
        # Reload IK: the left PALM centre (midpoint hand_l / middle_01_l, what the support IK places) against the
        # rig's hand_l_target socket (keyed through the Reload clips; None on a rig without it), and the gun hand's
        # world rotation so a reviewer can see it holds still through the reload.
        palm = (hand_l + m.get_socket_location('middle_01_l')) * 0.5
        target = gun_world(g, 'hand_l_target') if call(g, 'does_socket_exist', 'hand_l_target') else None
        hr = m.get_socket_rotation('hand_r')
        # Design A3 / C2: is the left palm ahead of the muzzle? Its position along the gun's forward axis from grip_r
        # against the muzzle socket's gun-space X minus 3 cm.
        mz = gun_comp(g, 'muzzle')
        fwd = g.get_forward_vector()
        along = None
        if grip_r is not None:
            d = palm - grip_r
            along = round(d.x * fwd.x + d.y * fwd.y + d.z * fwd.z, 2)
        row.update({'palm_along_gun_cm': along, 'muzzle_x_cm': round(mz.x, 2) if mz is not None else None,
                    'palm_ahead_of_muzzle': (along > mz.x - 3.0) if along is not None and mz is not None else None})
        row.update({'hand_l_to_target_cm': dist(palm, target), 'palm_l_to_grip_l_cm': dist(palm, grip_l),
                    'hand_r_rot': [round(hr.roll, 1), round(hr.pitch, 1), round(hr.yaw, 1)]})
        if not light:
            row['muzzle'] = vec(gun_world(g, 'muzzle'))
            fwd = g.get_forward_vector()
            row['gun_fwd_vs_control_deg'] = angle_deg(fwd, S['pc'].get_control_rotation().get_forward_vector())
            row['third_person'] = call(p, 'is_third_person_view')
        rest = S['rest'].get(tag) or {}
        for b in S['gun'][3]:
            cur = gun_comp(g, b)
            if cur is not None and b in rest:
                d = cur - rest[b]
                row[b + '_d'] = vec(d)
        if tag == 'EM08':
            row.update(cylinder_state(p))
    if w:
        row.update({'clip_ammo': prop(w, 'current_clip_ammo'), 'reserve_ammo': prop(w, 'reserve_ammo'),
                    'reloading': reloading(p)})
    return row


def rest_pose(p):
    g = gun_of(p)
    tag = S['gun'][0]
    S['rest'][tag] = {b: gun_comp(g, b) for b in S['gun'][3] if gun_comp(g, b) is not None}
    R['setup'].setdefault('rest_comp', {})[tag] = {k: vec(v) for k, v in S['rest'][tag].items()}
    R['setup'].setdefault('rig_on', {})[tag] = {'rig': rig_name(p), 'mesh': call(call(g, 'get_skeletal_mesh_asset'),
                                                                                  'get_name'),
                                                 'bones': list(call(g, 'get_all_socket_names') or [])[:24]}


def look_at(cam, loc, target, fov):
    rot = u.MathLibrary.find_look_at_rotation(loc, target)
    cam.set_actor_location_and_rotation(loc, rot, False, True)
    cam.camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(cam, 0)
    return {'cam_loc': vec(loc), 'cam_rot': [round(rot.pitch, 1), round(rot.yaw, 1), round(rot.roll, 1)], 'fov': fov}


def gun_centre(p):
    g = gun_of(p)
    a = gun_world(g, 'grip_r')
    b = gun_world(g, 'muzzle')
    if a is None or b is None:
        return p.get_actor_location() + u.Vector(0, 0, 40)
    return (a + b) * 0.5


def tq_distance():
    return max(85.0, min(190.0, S['gun'][2] * 1.55))


def cam_three_quarter(p, dist_cm=None, fov=50.0):
    f = p.get_actor_forward_vector()
    r = p.get_actor_right_vector()
    d = (f * 0.65 + r * 0.76)
    d = d / d.length()
    target = gun_centre(p)
    loc = target + d * (dist_cm or tq_distance()) + u.Vector(0, 0, 22)
    return look_at(S['cam'], loc, target, fov)


def cam_hands(p):
    """Close on both hands: from the right side, level with the grips."""
    g = gun_of(p)
    a = gun_world(g, 'grip_r')
    b = gun_world(g, 'grip_l') or a
    if a is None:
        return cam_three_quarter(p)
    target = (a + b) * 0.5
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    loc = target + gr * 62 + gf * 6 + u.Vector(0, 0, 10)
    return look_at(S['cam'], loc, target, 36.0)


def _cam_grip(p, fwd, right, down):
    """Grip seat (2026-10-31): the hands camera sits level with the grips, so a fist that wraps the grip hides it. Two
    low views on the grip's middle (grip_r is the grip TOP centre; the seat ~4 cm down) show what the fist covers:
    right-below reads the trigger finger, the fingers on the front strap and the grip bottom under the pinky;
    left-below the fingertips, the thumb over the back and the grip bottom. Both sit AHEAD of the grip: a rear-below
    spot lands inside the right forearm (right) or the torso / left arm (left) and the frame is skin (round 2 of the
    tuning run). ~45 cm off at 30 deg: about 80 px per cm at 1920."""
    g = gun_of(p)
    a = gun_world(g, 'grip_r')
    if a is None:
        return cam_hands(p)
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    gu = g.get_up_vector()
    target = a - gu * 4
    loc = a + gf * fwd + gr * right - gu * down
    return look_at(S['cam'], loc, target, 30.0)


def cam_grip_r(p):
    return _cam_grip(p, 8, 33, 30)


def cam_grip_l(p):
    return _cam_grip(p, 14, -30, 34)


def cam_receiver(p):
    """Close on the ejection-port side so the action is readable; scaled to the gun."""
    g = gun_of(p)
    target = gun_world(g, 'ejection_port') or gun_centre(p)
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    k = max(0.55, S['gun'][2] / 118.0)
    loc = target + gr * 58 * k + gf * 14 * k + u.Vector(0, 0, 14 * k)
    return look_at(S['cam'], loc, target + gf * 2, 32.0)


def cam_cylinder(p):
    """Revolver: on the cylinder from the right, slightly forward so the chambers and hammer both read."""
    g = gun_of(p)
    target = gun_world(g, 'cylinder') or gun_centre(p)
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    loc = target + gr * 34 + gf * 12 + u.Vector(0, 0, 9)
    return look_at(S['cam'], loc, target, 30.0)


def cam_muzzle(p):
    """Flash gallery: on the muzzle from the right-front so the sprite itself is in frame (the hands and receiver
    cameras look at the grips / ejection port: on a 30 cm SMG the muzzle sits at the frame edge and a 15 cm burst
    never shows, 2026-10-31 run). The gun body and the hands stay behind the muzzle for the whiteout read."""
    g = gun_of(p)
    target = gun_world(g, 'muzzle') or gun_centre(p)
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    loc = target + gr * 50 + gf * 22 + u.Vector(0, 0, 12)
    return look_at(S['cam'], loc, target - gf * 6, 40.0)


def cam_reload(p):
    """Follows the live mag well (or cylinder) so the drop and the fresh mag stay in frame."""
    g = gun_of(p)
    sock = S['gun'][5]
    well = gun_world(g, sock)
    if well is None:
        return cam_three_quarter(p)
    f = p.get_actor_forward_vector()
    r = p.get_actor_right_vector()
    d = (f * 0.72 + r * 0.69)
    d = d / d.length()
    k = max(0.5, S['gun'][2] / 118.0)
    target = well + u.Vector(0, 0, -14 * k)
    loc = well + d * 150 * k + u.Vector(0, 0, 18 * k)
    return {**look_at(S['cam'], loc, target, 50.0), 'follow_world': vec(well)}


def cam_reload_hands(p):
    """Second reload framing: from Vexa's left-front at ~1.2 x gun length (75 cm floor so the 30 cm revolver still
    frames two hands), on the centroid of both hands and the mag well, so the left hand's path down to the belt and
    back to the magazine, and the still right hand, both stay in frame."""
    g = gun_of(p)
    m = p.mesh
    well = gun_world(g, S['gun'][5]) or gun_centre(p)
    target = (m.get_socket_location('hand_r') + m.get_socket_location('hand_l') + well) / 3.0
    f = p.get_actor_forward_vector()
    r = p.get_actor_right_vector()
    d = (f * 0.72 - r * 0.69)  # her left-front
    d = d / d.length()
    loc = target + d * max(75.0, S['gun'][2] * 1.2) + u.Vector(0, 0, 12)
    return {**look_at(S['cam'], loc, target, 50.0), 'follow_world': vec(target), 'framing_name': 'cam_reload_hands'}


def cam_follow(p):
    return cam_three_quarter(p, fov=46.0)


def cam_eye(p):
    eye = prop(p, 'first_person_camera')
    if eye is None:
        return cam_three_quarter(p)
    loc = eye.get_world_location() + eye.get_forward_vector() * 6.0
    rot = eye.get_world_rotation()
    S['cam'].set_actor_location_and_rotation(loc, rot, False, True)
    fov = prop(eye, 'field_of_view') or 90.0
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)
    return {'cam_loc': vec(loc), 'cam_rot': [round(rot.pitch, 1), round(rot.yaw, 1), round(rot.roll, 1)], 'fov': fov}


def cam_chase(p):
    loc = p.get_actor_location()
    f = p.get_actor_forward_vector()
    return look_at(S['cam'], loc - f * 650 + u.Vector(0, 0, 320), loc + u.Vector(0, 0, 60), 70.0)


def capture(name, t, extra=None):
    p = pawn()
    fn = STILLS / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    row = {'file': fn.name, **(extra or {}), **sample(p, t)}
    R['frames'].append(row)
    brief = {k: row.get(k) for k in ('t', 'gun', 'clip', 'hand_l_to_grip_l_cm', 'clip_ammo', 'cyl_roll', 'cyl_angle')}
    for b in S['gun'][3][:2]:
        brief[b] = row.get(b + '_d')
    print('GUN_CAPTURE', fn.name, json.dumps(brief), flush=True)
    return row


def video_frame(t):
    name = S['video']
    d = VIDEO / name
    d.mkdir(parents=True, exist_ok=True)
    fn = d / ('f_%04d.png' % S['video_n'])
    S['video_n'] += 1
    u.HoverAuthoring.capture_world_frame(str(fn))
    p = pawn()
    R['video'].setdefault(name, []).append({'file': fn.name, **sample(p, t, light=True)})


def start_video(name):
    S['video'] = name
    S['video_n'] = 0
    S['follow'] = cam_follow
    R['video'][name] = []


def stop_video():
    name = S['video']
    S['video'] = None
    S['follow'] = None
    if name:
        print('GUN_VIDEO', name, len(R['video'].get(name, [])), 'frames', flush=True)


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


def apply_rig(tag):
    spec = next(g for g in GUNS if g[0] == tag)
    rig = u.load_asset(RIGS + spec[1])
    p = pawn()
    before = rig_name(p)
    p.apply_gun_rig(rig)
    S['gun'] = spec
    R['setup'].setdefault('swaps', []).append({'to': tag, 'from_rig': before, 'rig': rig_name(p),
                                               'mesh': call(call(gun_of(p), 'get_skeletal_mesh_asset'), 'get_name')})
    print('GUN_SWAP', tag, before, '->', rig_name(p), flush=True)


def flash_override_path(p):
    """Asset path of the held rig's in-memory MuzzleFlashOverride, None when unset / no rig."""
    rig = call(p, 'get_gun_rig')
    ov = prop(rig, 'muzzle_flash_override') if rig else None
    return ov.get_path_name().split('.')[0] if ov else None


def gallery_begin(tag):
    p = pawn()
    rig = call(p, 'get_gun_rig')
    S['gallery_orig'] = prop(rig, 'muzzle_flash_override') if rig else None
    S['gallery_scale_orig'] = prop(rig, 'muzzle_flash_scale') if rig else None
    R['gallery'][tag] = []
    # FLASH_LIGHT_SCALE (env): the held rig's MuzzleLightScale for the gallery shots only, in memory (the asset is
    # never saved; the c_ reference shots before the gallery keep the authored value, so one run shows both). The
    # 2026-10-31 gallery proved the point light, not the sprite, makes the whiteout: every candidate measured the
    # same ratio, and the small sprites vanished inside the blown-out muzzle.
    if os.environ.get('FLASH_LIGHT_SCALE') and rig:
        try:
            S['gallery_light_orig'] = prop(rig, 'muzzle_light_scale')
            rig.set_editor_property('muzzle_light_scale', float(os.environ['FLASH_LIGHT_SCALE']))
            R['setup'].setdefault('gallery_light_scale', {})[tag] = {
                'original': S['gallery_light_orig'], 'gallery': prop(rig, 'muzzle_light_scale')}
        except Exception as e:
            R['api_errors'].append('gallery light scale: %s' % e)
    print('GUN_GALLERY', tag, 'begin, original override', flash_override_path(p), 'light',
          R['setup'].get('gallery_light_scale', {}).get(tag), flush=True)


def load_system(path):
    """A Niagara system by path. EditorAssetLibrary refuses every call while PIE runs ("The Editor is currently in a
    play mode", 2026-10-31 run: all six candidates reported missing), so it goes through unreal.load_asset /
    load_object, which carry no play-mode guard; a path that really does not exist still yields None."""
    name = path.rsplit('/', 1)[-1]
    for loader in (lambda: u.load_asset(path), lambda: u.load_object(None, path + '.' + name)):
        try:
            system = loader()
        except Exception as e:
            R['api_errors'].append('load %s: %s' % (path, str(e)[:160]))
            continue
        if system is not None:
            return system
    return None


def gallery_pick(tag, idx, entry):
    """Points the held rig at candidate idx (in memory), sets its '@scale' MuzzleFlashScale (or the authored one back)
    and refills the clip so the shots always fire."""
    p = pawn()
    path = entry['path']
    name = path.rsplit('/', 1)[-1]
    system = load_system(path)
    row = {'index': idx, 'asset': path, 'name': name, 'loaded': system is not None, 'frames': []}
    if system is None:
        R['notes'].append('%s gallery %d: %s missing; the definition flash fired instead' % (tag, idx, path))
    try:
        p.set_muzzle_flash_override(system)
    except Exception as e:
        R['api_errors'].append('set_muzzle_flash_override %s: %s' % (path, e))
    row['applied'] = flash_override_path(p)
    rig = call(p, 'get_gun_rig')
    if rig is not None and S.get('gallery_scale_orig') is not None:
        try:
            rig.set_editor_property('muzzle_flash_scale',
                                    entry['scale'] if entry['scale'] is not None else S['gallery_scale_orig'])
        except Exception as e:
            R['api_errors'].append('gallery flash scale %s: %s' % (path, e))
    row['flash_scale'] = prop(rig, 'muzzle_flash_scale') if rig else None
    row['light_scale'] = prop(rig, 'muzzle_light_scale') if rig else None
    w = weapon_of(p)
    try:
        w.refill_ammo(True)
        row['clip_ammo'] = prop(w, 'current_clip_ammo')
    except Exception as e:
        R['api_errors'].append('refill_ammo: %s' % e)
    R['gallery'][tag].append(row)
    print('GUN_GALLERY', tag, idx, row['name'], 'applied', row['applied'], flush=True)


def gallery_end(tag):
    p = pawn()
    try:
        p.set_muzzle_flash_override(S.get('gallery_orig'))
    except Exception as e:
        R['api_errors'].append('set_muzzle_flash_override restore: %s' % e)
    if S.get('gallery_light_orig') is not None:
        try:
            call(p, 'get_gun_rig').set_editor_property('muzzle_light_scale', S['gallery_light_orig'])
        except Exception as e:
            R['api_errors'].append('gallery light scale restore: %s' % e)
    if S.get('gallery_scale_orig') is not None:
        try:
            call(p, 'get_gun_rig').set_editor_property('muzzle_flash_scale', S['gallery_scale_orig'])
        except Exception as e:
            R['api_errors'].append('gallery flash scale restore: %s' % e)
    R['setup'].setdefault('gallery_restored', {})[tag] = flash_override_path(p)
    print('GUN_GALLERY', tag, 'restored', R['setup']['gallery_restored'][tag], flush=True)


TRACER_FIELDS = ('tracer_override', 'tracer_override_tier_color', 'tracer_override_lifetime')


def pathish(v):
    return v.get_path_name().split('.')[0] if hasattr(v, 'get_path_name') else v


def tracer_begin(tag):
    p = pawn()
    rig = call(p, 'get_gun_rig')
    S['tracer_orig'] = {k: prop(rig, k) for k in TRACER_FIELDS} if rig else None
    try:
        weapon_of(p).refill_ammo(True)
    except Exception as e:
        R['api_errors'].append('refill_ammo: %s' % e)
    R['tracer_trial'][tag] = {'original': {k: pathish(v) for k, v in (S['tracer_orig'] or {}).items()}}
    print('GUN_TRACER', tag, 'begin', R['tracer_trial'][tag]['original'], flush=True)


def tracer_pick(tag, path):
    """The rig's TracerOverride in memory: the trial system, tier colour, TRACER_LIFETIME; the rig is never saved."""
    p = pawn()
    rig = call(p, 'get_gun_rig')
    system = load_system(path)
    row = {'asset': path, 'loaded': system is not None, 'lifetime': TRACER_LIFETIME}
    if system is None:
        R['notes'].append('%s tracer trial: %s missing; the tier tracer fired instead' % (tag, path))
    if rig is not None:
        try:
            rig.set_editor_property('tracer_override', system)
            rig.set_editor_property('tracer_override_tier_color', True)
            rig.set_editor_property('tracer_override_lifetime', TRACER_LIFETIME)
        except Exception as e:
            R['api_errors'].append('tracer override %s: %s' % (path, e))
        row['applied'] = pathish(prop(rig, 'tracer_override'))
    try:
        weapon_of(p).refill_ammo(True)
    except Exception as e:
        R['api_errors'].append('refill_ammo: %s' % e)
    R['tracer_trial'][tag]['override'] = row
    print('GUN_TRACER', tag, 'override', row, flush=True)


def tracer_end(tag):
    p = pawn()
    rig = call(p, 'get_gun_rig')
    if rig is not None and S.get('tracer_orig'):
        for k, v in S['tracer_orig'].items():
            try:
                rig.set_editor_property(k, v)
            except Exception as e:
                R['api_errors'].append('tracer restore %s: %s' % (k, e))
    R['tracer_trial'][tag]['restored'] = {k: pathish(prop(rig, k)) for k in TRACER_FIELDS} if rig else None
    print('GUN_TRACER', tag, 'restored', R['tracer_trial'][tag]['restored'], flush=True)


def start_reload(t, label):
    p = pawn()
    w = weapon_of(p)
    before = {'clip_ammo': prop(w, 'current_clip_ammo'), 'reserve_ammo': prop(w, 'reserve_ammo')}
    p.combat.reload()
    S['reload_t0'] = t
    started = reloading(p)
    R['setup'].setdefault('reloads', []).append({'label': label, 't0': round(t, 3), 'started': started, **before,
                                                 'reload_time_s': S.get('reload_time')})
    if not started:
        R['notes'].append('%s: combat.reload() did not start (clip full or no reserve?) %s' % (label, before))


# ---- schedule -------------------------------------------------------------------------------------
def plan():
    q = []

    def step(delay, fn):
        q.append((delay, fn))

    def frame(framing):
        def fn(t):
            S['framing'] = framing(pawn())
        return fn

    def cap(name, delay, state=None):
        def fn(t):
            capture(name, t, {**S.get('framing', {}), 'state': state} if state else S.get('framing', {}))
        step(delay, fn)

    scale = lambda m: m * (S.get('reload_time') or 2.4) / 2.4

    def gun_plan(spec):
        tag = spec[0]
        marks = spec[4]
        if tag != 'M4A1':
            step(0.3, lambda t, tag=tag: apply_rig(tag))
            step(1.2, lambda t: None)  # settle: ApplyGunRig idles the new mesh, offsets re-resolve
        step(0.0, lambda t: rest_pose(pawn()))
        step(0.0, frame(cam_three_quarter))
        cap(f'{tag}_a_rest', 0.2, 'nothing pressed')
        step(0.0, lambda t: key('RightMouseButton', True))
        step(0.9, frame(cam_three_quarter))
        cap(f'{tag}_b_aim', 0.1, 'aim held 1.0 s')
        step(0.0, frame(cam_hands))
        cap(f'{tag}_b_hands', 0.15, 'hands on the grips')
        # Grip seat (2026-10-31): the right fist on the pistol grip from below, where the fist cannot hide the grip
        # (the judge for GripSeatOffset / GripRotationOffset tuning: grip inside the closed hand, nothing poking out).
        step(0.0, frame(cam_grip_r))
        cap(f'{tag}_b_grip_r', 0.1, 'grip from the right-below: trigger finger, front strap, grip bottom')
        step(0.0, frame(cam_grip_l))
        cap(f'{tag}_b_grip_l', 0.1, 'grip from the left-below: fingertips, thumb over the back, grip bottom')
        # Design C2: the FIRST press of this gun, under the hands camera (re-framed two ticks ahead: CaptureWorldFrame
        # reads the last PRESENTED frame, so the camera set on tick A is in the pixels read on tick A+2). One
        # before frame, then ticks +1..+3 after the press: summarise() measures the flash luminance on these and
        # records hand_l_to_target_cm / palm_ahead_of_muzzle for A3 (the left hand must be on the gun, never lit
        # as a silhouette ahead of the flash). The receiver / cylinder bursts below follow as before.
        step(0.0, frame(cam_hands))
        step(0.0, lambda t: None)
        cap(f'{tag}_c_hands_before', 0.0, 'hands camera, aim, before the first press')
        step(0.0, lambda t: (key('LeftMouseButton', True), S.__setitem__('shot_t', t)))
        for k in range(1, 4):
            step(0.0, lambda t, k=k: (stop_shakes(), capture(
                f'{tag}_c_hands_t{k}', t, {**S['framing'], 'state': f'hands camera, tick +{k} after the first press',
                                           'since_press_s': round(t - S['shot_t'], 3)})))
        step(0.0, lambda t: key('LeftMouseButton', False))
        step(0.6, lambda t: None)
        if tag == 'EM08':
            step(0.0, lambda t: S.__setitem__('trace_cyl', True))
            step(0.0, frame(cam_cylinder))
            cap(f'{tag}_c_before', 0.15, 'aim, cylinder at rest')
            for k in range(1, 4):
                step(0.0, lambda t: key('LeftMouseButton', True))
                step(0.0, lambda t, k=k: (key('LeftMouseButton', False), stop_shakes(),
                                          capture(f'{tag}_c_shot{k}_t1', t, {**S['framing'], 'state': 'tick +1'})))
                step(0.0, lambda t, k=k: (stop_shakes(), capture(f'{tag}_c_shot{k}_t2', t,
                                                                 {**S['framing'], 'state': 'tick +2'})))
                step(0.0, lambda t, k=k: (stop_shakes(), capture(f'{tag}_c_shot{k}_t3', t,
                                                                 {**S['framing'], 'state': 'tick +3'})))
                cap(f'{tag}_c_after{k}', 0.55, f'0.55 s after shot {k}: Idle, cylinder must hold {k} chambers on')
            step(0.0, lambda t: S.__setitem__('trace_cyl', False))
        else:
            step(0.0, frame(cam_receiver))
            cap(f'{tag}_c_before', 0.15, 'aim, action home')
            for b in range(1, 3):
                step(0.0, lambda t: (key('LeftMouseButton', True), S.__setitem__('shot_t', t)))
                for k in range(1, 5):
                    step(0.0, lambda t, b=b, k=k: (stop_shakes(), capture(
                        f'{tag}_c_burst{b}_t{k}', t, {**S['framing'], 'state': f'tick +{k} after trigger press',
                                                       'since_press_s': round(t - S['shot_t'], 3)})))
                step(0.0, lambda t: key('LeftMouseButton', False))
                step(0.6, lambda t: None)
        if GALLERY:
            # Flash gallery: each candidate Niagara system in turn, one shot per camera. A camera moved on tick A is
            # in the pixels read on tick A + 2 (the back-buffer rule above): frame, one idle tick, before frame, press.
            step(0.0, lambda t, tag=tag: gallery_begin(tag))
            close_cam = cam_cylinder if tag == 'EM08' else cam_receiver

            def gallery_capture(name, t, idx, state):
                row = capture(name, t, {**S.get('framing', {}), 'state': state, 'gallery_index': idx,
                                        'since_press_s': round(t - S['shot_t'], 3) if 'shot_t' in S else None})
                R['gallery'][tag][-1]['frames'].append(row['file'])

            def gallery_shot(idx, name, cam, label):
                stem = f'{tag}_g{idx}_{name}_{label}'
                step(0.0, frame(cam))
                step(0.0, lambda t: None)
                step(0.0, lambda t, stem=stem, idx=idx: (stop_shakes(), gallery_capture(
                    f'{stem}_before', t, idx, 'gallery, before the shot')))
                step(0.0, lambda t: (key('LeftMouseButton', True), S.__setitem__('shot_t', t)))
                for k in (1, 2):
                    step(0.0, lambda t, stem=stem, idx=idx, k=k: (stop_shakes(), gallery_capture(
                        f'{stem}_t{k}', t, idx, f'gallery, tick +{k} after the press')))
                step(0.0, lambda t: key('LeftMouseButton', False))
                step(0.6, lambda t: None)

            for idx, entry in enumerate(GALLERY):
                name = entry['path'].rsplit('/', 1)[-1]
                step(0.0, lambda t, idx=idx, entry=entry, tag=tag: gallery_pick(tag, idx, entry))
                step(0.5, lambda t: None)
                gallery_shot(idx, name, cam_hands, 'hands')
                gallery_shot(idx, name, close_cam, 'receiver')
                gallery_shot(idx, name, cam_muzzle, 'muzzle')
                # The game's own view: the three-quarter camera, the flash on the whole character.
                gallery_shot(idx, name, cam_three_quarter, 'wide')
            step(0.0, lambda t, tag=tag: gallery_end(tag))
            step(0.5, lambda t: None)
        if TRACER and tag == 'M4A1':
            # Tracer trial: the chase camera (behind and above, looking down the aim) sees the streak leave the
            # muzzle; the tier's own tracer first, then the rig's TracerOverride, same camera, same ticks.
            def tracer_shot(label):
                stem = f'{tag}_tracer_{label}'
                step(0.0, frame(cam_chase))
                step(0.0, lambda t: None)
                step(0.0, lambda t, stem=stem: (stop_shakes(), capture(
                    f'{stem}_before', t, {**S.get('framing', {}), 'state': 'tracer trial, before the shot'})))
                step(0.0, lambda t: (key('LeftMouseButton', True), S.__setitem__('shot_t', t)))
                for k in (1, 2, 3):
                    step(0.0, lambda t, stem=stem, k=k: (stop_shakes(), capture(
                        f'{stem}_t{k}', t, {**S.get('framing', {}), 'state': f'tracer trial, tick +{k} after the press',
                                           'since_press_s': round(t - S['shot_t'], 3)})))
                step(0.0, lambda t: key('LeftMouseButton', False))
                step(0.6, lambda t: None)

            step(0.0, lambda t, tag=tag: tracer_begin(tag))
            tracer_shot('tier')
            step(0.0, lambda t, tag=tag: tracer_pick(tag, TRACER))
            step(0.5, lambda t: None)
            tracer_shot(TRACER.rsplit('/', 1)[-1])
            step(0.0, lambda t, tag=tag: tracer_end(tag))
            step(0.5, lambda t: None)
        step(0.0, lambda t: key('RightMouseButton', False))
        # reload stills, camera following the well / cylinder every tick
        step(0.4, lambda t: S.__setitem__('follow', cam_reload))
        step(0.1, lambda t, tag=tag: start_reload(t, tag + ' stills'))
        last = 0.0
        for mark in marks:
            # Two framings per mark: the well camera on the mark tick, the hands camera three ticks later (the row
            # notes it). CaptureWorldFrame reads the back buffer, i.e. the last PRESENTED frame, so a camera moved
            # in the capture tick is not in the pixels: the hands camera is switched on one tick, rendered the
            # next, and read on the third. Those three ticks come off the next delay so the later marks keep
            # their beat.
            step(max(0.0, scale(mark) - scale(last) - (3 * TICK if last else 0.0)), lambda t, mark=mark, tag=tag: capture(
                f'{tag}_d_reload_{str(mark).replace(".", "_")}s', t,
                {**S.get('framing', {}), 'state': f'reload clip {mark} s of 2.4',
                 'since_reload_s': round(t - S['reload_t0'], 3)}))
            step(0.0, lambda t: S.__setitem__('follow', cam_reload_hands))
            step(0.0, lambda t: None)  # one tick with the hands camera rendered

            def hands(t, mark=mark, tag=tag):
                capture(f'{tag}_d_hands_{str(mark).replace(".", "_")}s', t,
                        {**S.get('framing', {}), 'state': f'reload clip {mark} s of 2.4 + 3 ticks, hands camera',
                         'since_reload_s': round(t - S['reload_t0'], 3)})
                S['follow'] = cam_reload
            step(0.0, hands)
            last = mark
        cap(f'{tag}_d_reload_done', max(0.0, scale(2.4) - scale(last) - 3 * TICK) + 0.4, 'after reload')
        step(0.0, lambda t: S.__setitem__('follow', None))
        # video: aim, burst (taps on the revolver), reload, settle
        step(0.3, lambda t, tag=tag: start_video(f'{tag}_gameplay'))
        step(0.5, lambda t: key('RightMouseButton', True))
        if tag == 'EM08':
            for k in range(3):
                step(0.55 if k == 0 else 0.5, lambda t: key('LeftMouseButton', True))
                step(0.0, lambda t: key('LeftMouseButton', False))
        else:
            step(0.6, lambda t: key('LeftMouseButton', True))
            step(0.75, lambda t: key('LeftMouseButton', False))
        step(0.7, lambda t, tag=tag: start_reload(t, tag + ' video'))
        step(scale(2.4) + 0.5, lambda t: key('RightMouseButton', False))
        step(0.5, lambda t: stop_video())

    for spec in GUNS:

        # CAPTURE_GUNS=M4A1,EM08 (env) limits the run to those tags: a texture or flash check does not need all four.

        if os.environ.get('CAPTURE_GUNS') and spec[0] not in os.environ['CAPTURE_GUNS'].split(','):

            continue
        gun_plan(spec)
    # back to her rifle, then the bonus views
    step(0.3, lambda t: apply_rig('M4A1'))
    step(1.0, lambda t: rest_pose(pawn()))

    def first_person(t):
        p = pawn()
        try:
            p.hover_view()
        except Exception as e:
            R['api_errors'].append('hover_view: %s' % e)
        S['pc'].set_view_target_with_blend(p, 0)
        S['fp'] = not call(p, 'is_third_person_view')
        R['setup']['hover_view'] = {'first_person': S['fp'], 'prompt': call(p, 'get_prompt')}
    step(0.0, first_person)

    def fp_capture(t):
        p = pawn()
        if S.get('fp'):
            capture('M4A1_e_first_person', t, {'state': 'first person (player camera)'})
            return
        R['notes'].append('first person skipped: survival forces third person (status "%s"); e_eye_view is the '
                          'spawned camera on FirstPersonCamera instead' % call(p, 'get_prompt'))
        S['framing'] = cam_eye(p)
    step(0.3, fp_capture)
    step(0.3, lambda t: None if S.get('fp') else capture('M4A1_e_eye_view', t, {**S.get('framing', {}),
                                                                                'state': 'eye-level bonus view'}))
    step(0.0, frame(cam_chase))
    cap('M4A1_f_wide_chase', 0.3, 'chase camera')
    step(0.0, lambda t: S['pc'].set_view_target_with_blend(pawn(), 0))
    step(0.3, lambda t: (capture('M4A1_f_wide_player', t, {'state': 'player camera'}),
                         u.HoverAuthoring.capture_playtest(str(STILLS / 'M4A1_f_wide_ui.png'))))
    step(0.5, lambda t: finish())
    S['queue'] = q


def setup(p):
    w = weapon_of(p)
    wd = call(w, 'get_weapon_definition') if w else None
    stats = prop(wd, 'combat_stats') if wd else None
    S['reload_time'] = prop(stats, 'reload_time') if stats else None
    if not S['reload_time'] or S['reload_time'] <= 0:
        S['reload_time'] = 1.5
    g = gun_of(p)
    R['setup'].update({'pawn': p.get_class().get_name(), 'rigged': call(p, 'uses_rigged_gun'), 'rig': rig_name(p),
                       'gun_mesh': call(call(g, 'get_skeletal_mesh_asset'), 'get_name') if g else None,
                       'weapon': w.get_class().get_name() if w else None,
                       'definition': wd.get_name() if wd else None, 'reload_time': S['reload_time'],
                       'magazine': call(w, 'get_magazine_size') if w else None,
                       'clip_ammo': prop(w, 'current_clip_ammo') if w else None,
                       'reserve_ammo': prop(w, 'reserve_ammo') if w else None,
                       'third_person': call(p, 'is_third_person_view')})
    save()


def harvest_log():
    path = None
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        path = m.group(1) if m else None
    except Exception:
        pass
    if not path:
        path = str(Path(u.Paths.project_log_dir()) / 'AFS.log')
    R['log']['path'] = path
    if not Path(path).exists():
        R['notes'].append('log not found: ' + path)
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    R['log']['hover_gun'] = [l for l in lines if 'HOVER_GUN' in l and 'HOVER_GUNFEEL' not in l][-24:]
    R['log']['gun_warnings'] = [l for l in lines if ('M4A1' in l or 'EM08' in l or 'EM11' in l or 'EM21' in l)
                                and ('Warning' in l or 'Error' in l)][-40:]


def summarise():
    fr = {Path(f['file']).stem: f for f in R['frames']}
    s = R['summary']
    s['frames'] = len(R['frames'])
    s['video_frames'] = {k: len(v) for k, v in R['video'].items()}
    s['zombies_removed'] = S['zombies_removed']
    per = s['guns'] = {}
    for spec in GUNS:
        tag = spec[0]
        act = spec[6]
        g = per[tag] = {}
        aim = fr.get(f'{tag}_b_aim', {})
        g['hand_r_to_grip_r_aim_cm'] = aim.get('hand_r_to_grip_r_cm')
        g['hand_l_to_grip_l_aim_cm'] = aim.get('hand_l_to_grip_l_cm')
        g['gun_visible_aim'] = aim.get('gun_visible')
        g['mesh'] = aim.get('gun_mesh')
        burst = [f for f in R['frames'] if f['file'].startswith(f'{tag}_c_') and f.get(act + '_d')]
        if tag == 'EM08':
            trace = [c for c in R['cyl_trace']]
            idle = [c for c in trace if c['clip'] == 'A_EM08_Idle' and c['cyl_roll'] is not None]
            # Idle ticks: the bone's roll must equal the accumulated angle (same sign convention), never rest.
            err = [round(min(abs(((c['cyl_roll'] - c['cyl_angle']) + 180) % 360 - 180),
                             abs(((c['cyl_roll'] + c['cyl_angle']) + 180) % 360 - 180)), 2) for c in idle]
            # No snap-back: every roll step over the trace goes the same way (the clip's way). A snap would be a
            # step of one chamber in the opposite direction when Idle takes over from Fire.
            steps = []
            for a, b in zip(trace, trace[1:]):
                if a['cyl_roll'] is None or b['cyl_roll'] is None:
                    continue
                d = ((b['cyl_roll'] - a['cyl_roll']) + 180) % 360 - 180
                if abs(d) > 0.5:
                    steps.append(round(d, 1))
            g['cylinder_idle_ticks'] = len(idle)
            g['cylinder_idle_roll_vs_angle_max_err_deg'] = max(err) if err else None
            g['cylinder_roll_steps_deg'] = steps
            g['cylinder_sign_matches'] = bool(steps) and all((s > 0) == (steps[0] > 0) for s in steps)
            g['cylinder_rolls_after_shots'] = [(f['file'], f.get('cyl_roll'), f.get('cyl_angle')) for f in R['frames']
                                               if f['file'].startswith('EM08_c_after')]
            g['cylinder_trace_len'] = len(trace)
        else:
            g['action_back_frames'] = [(f['file'], f[act + '_d'][0]) for f in burst if f[act + '_d'][0] < -2.0]
        mags = {m: fr.get(f'{tag}_d_reload_{m}', {}).get('magazine_d') for m in ('0_75s', '1_5s', '1_9s')}
        g['magazine_dz_at_marks'] = {k: (v[2] if v else None) for k, v in mags.items()}
        # Reload IK: palm -> hand_l_target and the gun hand's rotation at every mark (both framings).
        hand_rows = {Path(f['file']).stem: f for f in R['frames'] if f['file'].startswith(f'{tag}_d_')}
        g['hand_l_to_target_at_marks'] = {k: v.get('hand_l_to_target_cm') for k, v in hand_rows.items()}
        g['hand_r_rot_at_marks'] = {k: v.get('hand_r_rot') for k, v in hand_rows.items()}
        rots = [v['hand_r_rot'] for v in hand_rows.values() if v.get('hand_r_rot')]
        g['hand_r_rot_span_deg'] = [round(max(r[i] for r in rots) - min(r[i] for r in rots), 1) for i in range(3)] \
            if rots else None
        if tag == 'EM08':
            g['crane_d_at_marks'] = {m: fr.get(f'{tag}_d_reload_{m}', {}).get('crane_d') for m in ('0_75s', '1_2s')}
            g['cylinder_dy_at_0_75'] = (fr.get(f'{tag}_d_reload_0_75s', {}).get('cylinder_d') or [None] * 3)[1]
        # Design C2: flash luminance. mean_luma / saturated_fraction (central 60 % of the frame, decoded from the
        # saved PNG by HoverAuthoring.measure_frame_luminance) on the before frame and the shot frames of each
        # camera: the hands camera (c_hands_before vs c_hands_t1..t3) and the receiver / cylinder camera (c_before
        # vs the first two ticks of each burst / shot). flash_luma_ratio = max shot luma / before luma. Targets:
        # ratio <= 1.8 and saturated <= 4 % on EM_21 / EM_08 / EM_11, ratio <= 2.4 and saturated <= 8 % on the M4A1.
        g['flash'] = flash_summary(tag, fr)
        g['flash_luma_ratio'] = g['flash']['hands_cam']['flash_luma_ratio']
        g['saturated_fraction'] = g['flash']['hands_cam']['saturated_fraction']
        # A3 on the hands-camera shot frames: the left palm on hand_l_target, never ahead of the muzzle.
        hf = [fr.get(f'{tag}_c_hands_t{k}') for k in (1, 2, 3)]
        hf = [f for f in hf if f]
        g['hands_frames'] = {
            'hand_l_to_target_cm': [f.get('hand_l_to_target_cm') for f in hf],
            'palm_ahead_of_muzzle': [f.get('palm_ahead_of_muzzle') for f in hf],
            'hand_l_to_target_max_cm': max((f['hand_l_to_target_cm'] for f in hf
                                            if f.get('hand_l_to_target_cm') is not None), default=None),
            'palm_ahead_any': any(f.get('palm_ahead_of_muzzle') for f in hf)}
    if GALLERY:
        s['gallery'] = gallery_summary(fr)
    if TRACER:
        s['tracer_trial'] = R['tracer_trial']
    s['hover_gun_lines'] = R['log'].get('hover_gun', [])[-6:]
    s['reloads'] = R['setup'].get('reloads')
    m4 = per['M4A1']
    em8 = per['EM08']
    # `x or default` treats a perfect 0.0 (mag seated, cylinder error 0) as missing; test for None instead.
    num = lambda v, default: default if v is None else v
    s['flash_ok'] = all(per[sp[0]]['flash'][cam]['within_target'] for sp in GUNS for cam in ('hands_cam', 'receiver_cam'))
    s['hands_frames_ok'] = all(per[sp[0]]['hands_frames']['hand_l_to_target_max_cm'] is not None and
                               per[sp[0]]['hands_frames']['hand_l_to_target_max_cm'] <= 4.0 and
                               not per[sp[0]]['hands_frames']['palm_ahead_any'] for sp in GUNS)
    R['ok'] = bool(m4.get('action_back_frames')) and num(m4['magazine_dz_at_marks'].get('0_75s'), 0) < -10 and \
        abs(num(m4['magazine_dz_at_marks'].get('1_9s'), 99)) < 1.5 and bool(m4.get('gun_visible_aim')) and \
        bool(em8.get('cylinder_sign_matches')) and num(em8.get('cylinder_idle_roll_vs_angle_max_err_deg'), 99) < 3 \
        and s['flash_ok'] and s['hands_frames_ok']


def measure_luma(row):
    """Adds mean_luma / saturated_fraction (central 60 %) to a frame row from its PNG; None when it cannot be read."""
    if row is None:
        return None
    if 'mean_luma' not in row:
        try:
            m = json.loads(u.HoverAuthoring.measure_frame_luminance(str(STILLS / row['file']), 0.6))
            if m.get('ok'):
                row['mean_luma'] = round(m['mean_luma'], 3)
                row['saturated_fraction'] = round(m['saturated_fraction'], 5)
            else:
                R['api_errors'].append('measure_frame_luminance %s: %s' % (row['file'], m))
        except Exception as e:
            R['api_errors'].append('measure_frame_luminance %s: %s' % (row.get('file'), e))
    return row if row.get('mean_luma') is not None else None


def gallery_summary(fr):
    """Per gun and candidate: the C2 luminance measure (before vs the two shot ticks) under each camera, written
    into R['gallery'] (capture.json 'gallery') and returned for the summary."""
    out = {}
    for tag, rows in R['gallery'].items():
        ratio_max, sat_max = (2.4, 0.08) if tag == 'M4A1' else (1.8, 0.04)
        out[tag] = []
        for row in rows:
            stem = '%s_g%d_%s' % (tag, row['index'], row['name'])
            for cam in ('hands', 'receiver', 'muzzle', 'wide'):
                before = measure_luma(fr.get(f'{stem}_{cam}_before'))
                shots = [measure_luma(fr.get(f'{stem}_{cam}_t{k}')) for k in (1, 2)]
                shots = [x for x in shots if x]
                d = row[cam + '_cam'] = {
                    'before_luma': before['mean_luma'] if before else None,
                    'before_saturated': before['saturated_fraction'] if before else None,
                    'shot_frames': {x['file']: {'luma': x['mean_luma'], 'saturated': x['saturated_fraction']}
                                    for x in shots}}
                d['flash_luma_ratio'] = (round(max(x['mean_luma'] for x in shots) / max(1e-3, before['mean_luma']), 3)
                                         if before and shots else None)
                d['saturated_fraction'] = round(max(x['saturated_fraction'] for x in shots), 5) if shots else None
                d['within_target'] = (d['flash_luma_ratio'] is not None and d['flash_luma_ratio'] <= ratio_max and
                                      d['saturated_fraction'] is not None and d['saturated_fraction'] <= sat_max)
            brief = {k: row.get(k) for k in ('index', 'name', 'asset', 'applied', 'clip_ammo', 'flash_scale',
                                              'light_scale')}
            for cam in ('hands_cam', 'receiver_cam', 'muzzle_cam', 'wide_cam'):
                brief[cam] = {k: row[cam][k] for k in ('flash_luma_ratio', 'saturated_fraction', 'within_target')}
            out[tag].append(brief)
    return out


def flash_summary(tag, fr):
    ratio_max, sat_max = (2.4, 0.08) if tag == 'M4A1' else (1.8, 0.04)
    shot_names = ([f'{tag}_c_shot{b}_t{k}' for b in (1, 2, 3) for k in (1, 2)] if tag == 'EM08' else
                  [f'{tag}_c_burst{b}_t{k}' for b in (1, 2) for k in (1, 2)])
    out = {'targets': {'flash_luma_ratio_max': ratio_max, 'saturated_fraction_max': sat_max}}
    for cam, before_name, names in (('hands_cam', f'{tag}_c_hands_before', [f'{tag}_c_hands_t{k}' for k in (1, 2, 3)]),
                                    ('receiver_cam', f'{tag}_c_before', shot_names)):
        before = measure_luma(fr.get(before_name))
        shots = [measure_luma(fr.get(n)) for n in names]
        shots = [s for s in shots if s]
        d = out[cam] = {'before_frame': before_name, 'before_luma': before['mean_luma'] if before else None,
                        'before_saturated': before['saturated_fraction'] if before else None,
                        'shot_frames': {s['file']: {'luma': s['mean_luma'], 'saturated': s['saturated_fraction']}
                                        for s in shots}}
        d['flash_luma_ratio'] = (round(max(s['mean_luma'] for s in shots) / max(1e-3, before['mean_luma']), 3)
                                 if before and shots else None)
        d['saturated_fraction'] = round(max(s['saturated_fraction'] for s in shots), 5) if shots else None
        d['within_target'] = (d['flash_luma_ratio'] is not None and d['flash_luma_ratio'] <= ratio_max and
                              d['saturated_fraction'] is not None and d['saturated_fraction'] <= sat_max)
    return out


def finish():
    if S['end']:
        return
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def tick(dt):
    if S['busy']:
        return
    S['busy'] = True
    try:
        if S['end']:
            if time.monotonic() - S['end'] > 3 and not world():
                if not S['done']:
                    S['done'] = True
                    harvest_log()
                    summarise()
                    save()
                    print('GUN_CAPTURE_DONE', json.dumps(R['summary'], default=str)[:1500], flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('capture timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 7:
                try:
                    R['setup']['offscreen_display'] = u.HoverAuthoring.configure_offscreen_display(WIDTH + 16, HEIGHT + 80)
                except Exception as e:
                    R['api_errors'].append('configure_offscreen_display: %s' % e)
                u.HoverAuthoring.start_playtest(WIDTH, HEIGHT + 32)
                S['play'] = True
            return
        w = world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        t = u.GameplayStatics.get_time_seconds(w)
        if S['pc'] is None:
            S['pc'] = pc
            S['t_first'] = t
            return
        p = pc.get_controlled_pawn()
        clear_zombies(w)
        if not S['console']:
            S['console'] = True
            R['setup']['console'] = {c: console(c) for c in CONSOLE}
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            cur = viewport_size()
            if cur and cur != [WIDTH, HEIGHT] and S['vp_tries'] < VIEWPORT_TRIES:
                S['vp_tries'] += 1
                req = S['vp_req'] or [WIDTH, HEIGHT]
                req = [req[0] + (WIDTH - cur[0]), req[1] + (HEIGHT - cur[1])]
                S['vp_req'] = req
                got = u.HoverAuthoring.resize_playtest_window(req[0], req[1])
                R['setup'].setdefault('viewport_resizes', []).append(
                    {'measured': cur, 'requested': req, 'client': [int(got.x), int(got.y)]})
                return
            R['setup']['viewport_final'] = cur
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            setup(p)
            plan()
            S['next'] = t
            return
        S['ticks'] += 1
        if S['follow']:
            S['framing'] = S['follow'](p)
        if S['trace_cyl']:
            R['cyl_trace'].append({'t': round(t, 3), **cylinder_state(p)})
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
        if S['video']:
            video_frame(t)
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('GUN_CAPTURE_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
