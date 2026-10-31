"""Photograph the rigged M4A1 (UHoverPilotAssets::RiggedGun) in Vexa's hands on L_NYC_Survival.

Run headless with real pixels (NullRHI gives black frames):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/CaptureM4A1.py -RenderOffscreen -unattended -nosplash

Starts PIE at 1920x1080 (HoverAuthoring.start_playtest(1920, 1080)), isolates test input so Vexa stands
still at the survival start, switches the engine to a fixed 1/30 s step so clip timing is deterministic,
and drives the weapon the way the player does (RightMouseButton = aim, LeftMouseButton = trigger,
UHoverCombatBridge.reload = X). A spawned CameraActor frames each shot:

  a_rest_true      third person, nothing pressed (the forced-third-person mode lowers/hides the rifle)
  a_hold           hip hold 0.7 s after one shot (GunRaisedTime keeps the rifle up for 3 s)
  b_aim            RightMouseButton held, same three-quarter framing from the right at ~180 cm
  c_burstN_tK      trigger pressed at tick N, frames on the next 4 ticks, close on the receiver
  d_reload_*       UHoverCombatBridge.reload at t0, frames at 0.3/0.75/1.5/1.9/2.3 s of a 2.4 s reload
                   (scaled to the weapon's ReloadTime), framed on the magazine well
  e_first_person   only if HoverView is honoured (survival forces third person); otherwise e_eye_view
                   is the spawned camera parked on Vexa's FirstPersonCamera transform as a bonus
  f_wide_*         chase camera, the player camera and the UI (capture_playtest) for context

Frames are 1920x1080: -RenderOffscreen runs on FNullApplication whose virtual work area is 1280x720, so
HoverAuthoring.configure_offscreen_display widens it before start_playtest and resize_playtest_window /
get_playtest_viewport_size correct the window until the viewport measures WIDTH x HEIGHT. Motion blur is
switched off (r.MotionBlurQuality 0, r.DefaultFeature.MotionBlur 0) and the fire camera shake is stopped
before each burst frame so the bolt is readable; the reload camera follows the live mag_well socket every
tick because the body's reload clip raises the rifle to chest height. One scheduled step runs per world
tick (the slate post-tick callback can fire more than once per frame).

Every frame also records numbers: hand_r->grip_r and hand_l->grip_l distances, bolt_carrier and
magazine component-space offsets from their rest pose, gun forward vs control rotation, visibility,
ammo/reload state and zombie count. Receipt: D:/AFS_Comparisons/M4A1_20261029/captures/capture.json.
Changes only the unsaved Play world.
"""
import json
import math
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path('D:/AFS_Comparisons/M4A1_20261029/captures')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'capture.json'
RIG_JSON = Path('M:/UnrealProjects/AFS/SourceAssets/M4A1_Modular/Rigged/m4a1_rig.json')
WIDTH, HEIGHT = 1920, 1080
TIMEOUT = 1500
RELOAD_MARKS = (0.3, 0.75, 1.5, 1.9, 2.3)  # seconds of the authored 2.4 s clip
CONSOLE = ('r.MotionBlurQuality 0', 'r.DefaultFeature.MotionBlur 0', 'DisableAllScreenMessages')
VIEWPORT_TRIES = 4
BURSTS = 3
BURST_TICKS = 4

R = {'ok': False, 'errors': [], 'notes': [], 'setup': {}, 'frames': [], 'log': {}, 'summary': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'cam': None,
     'queue': [], 'next': None, 'rest': {}, 'done': False, 'ticks': 0, 'vp_tries': 0, 'vp_req': None,
     'follow': None, 'last_step_t': None, 'console': False}
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
    """UHoverCombatBridge::IsReloading (BlueprintPure) mirrors AZE_WeaponBase::bIsReloading."""
    c = prop(p, 'combat')
    try:
        return bool(c.is_reloading()) if c else None
    except Exception as e:
        R.setdefault('api_errors', []).append('combat.is_reloading: %s' % e)
        return None


def viewport_size():
    try:
        v = u.HoverAuthoring.get_playtest_viewport_size()
        return [int(v.x), int(v.y)]
    except Exception as e:
        R.setdefault('api_errors', []).append('get_playtest_viewport_size: %s' % e)
        return None


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
        return True
    except Exception as e:
        R.setdefault('api_errors', []).append('%s: %s' % (cmd, e))
        return False


def stop_shakes():
    try:
        S['pc'].player_camera_manager.stop_all_camera_shakes(True)
    except Exception as e:
        R.setdefault('api_errors', []).append('stop_all_camera_shakes: %s' % e)


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


def angle_deg(a, b):
    a = a.normal() if hasattr(a, 'normal') else a
    b = b.normal() if hasattr(b, 'normal') else b
    d = max(-1.0, min(1.0, a.x * b.x + a.y * b.y + a.z * b.z))
    return round(math.degrees(math.acos(d)), 1)


def dist(a, b):
    return round((a - b).length(), 2) if a is not None and b is not None else None


def sample(p, t):
    """Numbers that back each frame: grip alignment, bolt/mag offsets, aim, visibility, ammo."""
    g = gun_of(p)
    m = p.mesh
    w = weapon_of(p)
    row = {'t': round(t, 3), 'rigged': call(p, 'uses_rigged_gun'), 'aiming': call(p, 'is_aiming'),
           'third_person': call(p, 'is_third_person_view'), 'pawn_loc': vec(p.get_actor_location())}
    if g:
        hand_r = m.get_socket_location('hand_r')
        hand_l = m.get_socket_location('hand_l')
        grip_r = gun_world(g, 'grip_r')
        grip_l = gun_world(g, 'grip_l')
        row.update({'gun_visible': call(g, 'is_visible'), 'gun_owner_no_see': prop(g, 'owner_no_see'),
                    'gun_mesh': call(call(g, 'get_skeletal_mesh_asset'), 'get_name'),
                    'hand_r_to_grip_r_cm': dist(hand_r, grip_r), 'hand_l_to_grip_l_cm': dist(hand_l, grip_l),
                    'muzzle': vec(gun_world(g, 'muzzle')), 'grip_l_world': vec(grip_l),
                    'hand_l_world': vec(hand_l)})
        fwd = g.get_forward_vector()
        ctrl = S['pc'].get_control_rotation().get_forward_vector()
        row['gun_fwd_vs_control_deg'] = angle_deg(fwd, ctrl)
        row['gun_fwd_vs_pawn_deg'] = angle_deg(fwd, p.get_actor_forward_vector())
        bolt = gun_comp(g, 'bolt_carrier')
        mag = gun_comp(g, 'magazine')
        handle = gun_comp(g, 'charging_handle')
        trig = g.get_socket_transform('trigger', COMP).rotation.rotator() if g else None
        if bolt is not None:
            row['bolt_carrier_comp'] = vec(bolt)
            row['magazine_comp'] = vec(mag)
            row['charging_handle_comp'] = vec(handle)
            row['trigger_pitch_deg'] = round(trig.pitch, 2) if trig else None
            rest = S['rest']
            if rest:
                row['bolt_dx_cm'] = round(bolt.x - rest['bolt'].x, 2)
                row['mag_dz_cm'] = round(mag.z - rest['mag'].z, 2)
                row['mag_dx_cm'] = round(mag.x - rest['mag'].x, 2)
                row['handle_dx_cm'] = round(handle.x - rest['handle'].x, 2)
        # Scale reference: shoulder to wrist plus hand; an M4 with can is about shoulder-to-fingertip.
        try:
            sh = m.get_socket_location('upperarm_r')
            row['vexa_shoulder_to_hand_cm'] = dist(sh, hand_r)
            row['vexa_hand_to_finger_cm'] = dist(hand_r, m.get_socket_location('middle_03_r'))
        except Exception:
            pass
    if w:
        row.update({'clip_ammo': prop(w, 'current_clip_ammo'), 'reserve_ammo': prop(w, 'reserve_ammo'),
                    'reloading': reloading(p), 'weapon_reloading': call(w, 'is_reloading'),
                    'firing': prop(w, 'is_firing', 'b_is_firing')})
    wd = world()
    if wd:
        try:
            row['zombies'] = len(u.GameplayStatics.get_all_actors_of_class(wd, u.HoverCyberZombie))
        except Exception:
            pass
    return row


def rest_pose(p):
    g = gun_of(p)
    S['rest'] = {'bolt': gun_comp(g, 'bolt_carrier'), 'mag': gun_comp(g, 'magazine'),
                 'handle': gun_comp(g, 'charging_handle')}
    R['setup']['rest_comp'] = {k: vec(v) for k, v in S['rest'].items()}


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


def cam_three_quarter(p, dist_cm=180.0, fov=50.0, drop=0.0):
    """Three-quarter view from Vexa's right-front; frames both hands and the whole rifle."""
    f = p.get_actor_forward_vector()
    r = p.get_actor_right_vector()
    d = (f * 0.65 + r * 0.76)
    d = d / d.length()
    target = gun_centre(p) + u.Vector(0, 0, -drop)
    loc = target + d * dist_cm + u.Vector(0, 0, 22)
    return look_at(S['cam'], loc, target, fov)


def cam_receiver(p):
    """Close on the ejection-port side of the receiver so the bolt carrier is readable."""
    g = gun_of(p)
    target = gun_world(g, 'ejection_port')
    gf = g.get_forward_vector()
    gr = g.get_right_vector()
    loc = target + gr * 58 + gf * 14 + u.Vector(0, 0, 14)
    return look_at(S['cam'], loc, target + gf * 2, 32.0)


def cam_magwell(p):
    """~150 cm off Vexa's right-front, slightly above the rifle, aimed at the live mag well so the well
    and the ~45 cm drop below it stay in frame while the body's reload clip raises the rifle."""
    g = gun_of(p)
    well = gun_world(g, 'mag_well')
    if well is None:
        return cam_three_quarter(p)
    f = p.get_actor_forward_vector()
    r = p.get_actor_right_vector()
    d = (f * 0.72 + r * 0.69)
    d = d / d.length()
    target = well + u.Vector(0, 0, -14)
    loc = well + d * 150 + u.Vector(0, 0, 18)
    return {**look_at(S['cam'], loc, target, 50.0), 'mag_well_world': vec(well)}


def cam_eye(p):
    """Bonus: the spawned camera on Vexa's FirstPersonCamera transform (survival refuses HoverView)."""
    eye = prop(p, 'first_person_camera')
    if eye is None:
        return cam_three_quarter(p)
    loc = eye.get_world_location() + eye.get_forward_vector() * 6.0
    rot = eye.get_world_rotation()
    S['cam'].set_actor_location_and_rotation(loc, rot, False, True)
    fov = prop(eye, 'field_of_view') or 90.0
    S['cam'].camera_component.set_field_of_view(fov)
    S['pc'].set_view_target_with_blend(S['cam'], 0)
    return {'cam_loc': vec(loc), 'cam_rot': [round(rot.pitch, 1), round(rot.yaw, 1), round(rot.roll, 1)],
            'fov': fov}


def cam_chase(p):
    loc = p.get_actor_location()
    f = p.get_actor_forward_vector()
    camloc = loc - f * 650 + u.Vector(0, 0, 320)
    return look_at(S['cam'], camloc, loc + u.Vector(0, 0, 60), 70.0)


def capture(name, t, extra=None):
    p = pawn()
    fn = OUT / (name + '.png')
    u.HoverAuthoring.capture_world_frame(str(fn))
    row = {'file': fn.name, **(extra or {}), **sample(p, t)}
    R['frames'].append(row)
    print('M4A1_CAPTURE', fn.name, json.dumps({k: row.get(k) for k in ('t', 'gun_visible', 'bolt_dx_cm', 'mag_dz_cm',
                                                                       'hand_l_to_grip_l_cm', 'clip_ammo')}),
          flush=True)
    return row


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)


# ---- schedule -------------------------------------------------------------------------------------
# Each step: (delay_after_previous_seconds, fn(t)). A 0 delay means "the very next tick".
def plan():
    q = []

    def step(delay, fn):
        q.append((delay, fn))

    def cap(name, delay, framing=None, extra=None):
        def fn(t):
            meta = framing(pawn()) if framing else {}
            capture(name, t, {**meta, **(extra or {})})
        step(delay, fn)

    def frame(framing):
        def fn(t):
            S['framing'] = framing(pawn())
        return fn

    # (a1) true rest: forced third person, nothing pressed.
    step(0.0, lambda t: rest_pose(pawn()))
    step(0.0, frame(cam_three_quarter))
    step(0.2, lambda t: capture('a_rest_true', t, S.get('framing')))
    # (b) aim held.
    step(0.0, lambda t: key('RightMouseButton', True))
    step(0.9, frame(cam_three_quarter))
    step(0.1, lambda t: capture('b_aim', t, {**S.get('framing', {}), 'state': 'aim held 1.0 s'}))
    step(0.0, lambda t: key('RightMouseButton', False))
    # (a2) hip hold: one tap keeps the rifle raised (GunRaisedTime 3 s) without the ADS camera/pose.
    step(0.4, lambda t: key('LeftMouseButton', True))
    step(0.0, lambda t: key('LeftMouseButton', False))
    step(0.7, frame(cam_three_quarter))
    step(0.1, lambda t: capture('a_hold', t, {**S.get('framing', {}), 'state': 'hip hold 0.8 s after one shot'}))
    # (c) bursts: aim, close on the receiver, tap, frames on the next ticks.
    step(0.0, lambda t: key('RightMouseButton', True))
    step(0.6, frame(cam_receiver))
    step(0.15, lambda t: capture('c_receiver_before', t, {**S.get('framing', {}), 'state': 'aim, bolt home'}))
    for b in range(1, BURSTS + 1):
        step(0.0, lambda t, b=b: (key('LeftMouseButton', True), S.__setitem__('shot_t', t)))
        for k in range(1, BURST_TICKS + 1):
            step(0.0, lambda t, b=b, k=k: (stop_shakes(), capture(
                f'c_burst{b}_t{k}', t, {**S.get('framing', {}), 'state': f'tick +{k} after trigger press',
                                        'since_press_s': round(t - S['shot_t'], 3)})))
        step(0.0, lambda t: key('LeftMouseButton', False))
        step(0.6, lambda t: None)
    step(0.0, lambda t: key('RightMouseButton', False))
    # (d) reload: the camera follows the mag well every tick from here until d_reload_done.
    step(0.4, lambda t: S.__setitem__('follow', cam_magwell))

    def start_reload(t):
        p = pawn()
        w = weapon_of(p)
        before = {'clip_ammo': prop(w, 'current_clip_ammo'), 'reserve_ammo': prop(w, 'reserve_ammo')}
        p.combat.reload()
        S['reload_t0'] = t
        started = reloading(p)
        R['setup']['reload'] = {'t0': round(t, 3), 'started': started, **before,
                                'reload_time_s': S.get('reload_time')}
        if not started:
            R['notes'].append('combat.reload() did not start a reload (clip full or no reserve?)')
    step(0.1, start_reload)
    scale = lambda m: m * (S.get('reload_time') or 2.4) / 2.4
    last = 0.0
    for mark in RELOAD_MARKS:
        delay = scale(mark) - scale(last)
        step(delay, lambda t, mark=mark: capture(f'd_reload_{str(mark).replace(".", "_")}s', t,
                                                 {**S.get('framing', {}), 'state': f'reload clip {mark} s of 2.4',
                                                  'since_reload_s': round(t - S['reload_t0'], 3)}))
        last = mark
    step(scale(2.4) - scale(last) + 0.4, lambda t: capture('d_reload_done', t, {**S.get('framing', {}),
                                                                             'state': 'after reload'}))
    step(0.0, lambda t: S.__setitem__('follow', None))
    # (e) first person attempt: AHoverPilot::HoverView is an Exec UFUNCTION (survival's level policy
    # refuses it and leaves a status message); the player camera is the view target for the check.

    def first_person(t):
        p = pawn()
        try:
            p.hover_view()
        except Exception as e:
            R.setdefault('api_errors', []).append('hover_view: %s' % e)
        S['pc'].set_view_target_with_blend(p, 0)
        S['fp'] = not call(p, 'is_third_person_view')
        R['setup']['hover_view'] = {'first_person': S['fp'], 'prompt': call(p, 'get_prompt')}
    step(0.0, first_person)

    def fp_capture(t):
        p = pawn()
        if S.get('fp'):
            capture('e_first_person', t, {'state': 'first person (player camera)'})
            return
        R['notes'].append('first person skipped: survival forces third person (HoverView refused, '
                          'status "%s"); e_eye_view is the spawned camera on FirstPersonCamera instead'
                          % call(p, 'get_prompt'))
        S['framing'] = cam_eye(p)
    step(0.3, fp_capture)
    step(0.3, lambda t: None if S.get('fp') else capture('e_eye_view', t, {**S.get('framing', {}),
                                                                           'state': 'eye-level bonus view'}))
    # (f) wide shots.
    step(0.0, frame(cam_chase))
    step(0.3, lambda t: capture('f_wide_chase', t, {**S.get('framing', {}), 'state': 'chase camera'}))
    step(0.0, lambda t: S['pc'].set_view_target_with_blend(pawn(), 0))
    step(0.3, lambda t: (capture('f_wide_player', t, {'state': 'player camera'}),
                         u.HoverAuthoring.capture_playtest(str(OUT / 'f_wide_ui.png'))))
    step(0.5, lambda t: finish())
    S['queue'] = q


def setup(p):
    w = weapon_of(p)
    wd = call(w, 'get_weapon_definition') if w else None
    stats = prop(wd, 'combat_stats') if wd else None
    S['reload_time'] = prop(stats, 'reload_time') if stats else None
    if not S['reload_time'] or S['reload_time'] <= 0:
        S['reload_time'] = 1.5  # vendor fallback in AZE_WeaponBase::Reload
    g = gun_of(p)
    R['setup'] = {'pawn': p.get_class().get_name(), 'rigged': call(p, 'uses_rigged_gun'),
                  'gun_mesh': call(call(g, 'get_skeletal_mesh_asset'), 'get_name') if g else None,
                  'gun_anim_mode': str(prop(g, 'animation_mode')) if g else None,
                  'weapon': w.get_class().get_name() if w else None, 'definition': wd.get_name() if wd else None,
                  'automatic': prop(wd, 'automatic', 'b_automatic') if wd else None,
                  'fire_rate': prop(stats, 'fire_rate') if stats else None, 'reload_time': S['reload_time'],
                  'magazine': call(w, 'get_magazine_size') if w else None,
                  'clip_ammo': prop(w, 'current_clip_ammo') if w else None,
                  'invincible': call(p, 'is_invincible'), 'third_person': call(p, 'is_third_person_view'),
                  'viewport': None}
    try:
        vs = u.WidgetLayoutLibrary.get_viewport_size(world())
        R['setup']['viewport'] = [vs.x, vs.y]
    except Exception:
        pass
    if RIG_JSON.exists():
        try:
            R['setup']['rig_sockets_cm'] = json.loads(RIG_JSON.read_text())['sockets_cm']
        except Exception:
            pass
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
    R['log']['hover_gun'] = [l for l in lines if 'HOVER_GUN' in l and 'HOVER_GUNFEEL' not in l][-20:]
    R['log']['m4a1_warnings'] = [l for l in lines if 'M4A1' in l and ('Warning' in l or 'Error' in l)][-40:]
    R['log']['hover_ready'] = [l for l in lines if 'HOVER_READY' in l][-3:]


def summarise():
    fr = {Path(f['file']).stem: f for f in R['frames']}
    bolt = [f for f in R['frames'] if f['file'].startswith('c_burst') and (f.get('bolt_dx_cm') or 0) < -2.0]
    s = R['summary']
    s['frames'] = len(R['frames'])
    s['bolt_back_frames'] = [(f['file'], f['bolt_dx_cm']) for f in bolt]
    s['mag_out_0_75'] = fr.get('d_reload_0_75s', {}).get('mag_dz_cm')
    s['mag_seated_1_9'] = fr.get('d_reload_1_9s', {}).get('mag_dz_cm')
    s['hand_l_to_grip_l_aim_cm'] = fr.get('b_aim', {}).get('hand_l_to_grip_l_cm')
    s['hand_r_to_grip_r_aim_cm'] = fr.get('b_aim', {}).get('hand_r_to_grip_r_cm')
    s['gun_visible_aim'] = fr.get('b_aim', {}).get('gun_visible')
    s['gun_visible_hold'] = fr.get('a_hold', {}).get('gun_visible')
    s['gun_fwd_vs_control_aim_deg'] = fr.get('b_aim', {}).get('gun_fwd_vs_control_deg')
    s['hover_gun_line'] = R['log'].get('hover_gun', [])[-1:] or None
    s['viewport'] = R['setup'].get('viewport_final')
    s['reload_started'] = R['setup'].get('reload', {}).get('started')
    R['ok'] = bool(bolt) and s['mag_out_0_75'] is not None and s['mag_out_0_75'] < -10 and \
        s['mag_seated_1_9'] is not None and abs(s['mag_seated_1_9']) < 1.5 and bool(s['gun_visible_aim'])


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
                    print('M4A1_CAPTURE_DONE', json.dumps(R['summary'], default=str), flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('capture timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 7:
                try:
                    R['setup']['offscreen_display'] = u.HoverAuthoring.configure_offscreen_display(
                        WIDTH + 16, HEIGHT + 80)
                except Exception as e:
                    R.setdefault('api_errors', []).append('configure_offscreen_display: %s' % e)
                u.HoverAuthoring.start_playtest(WIDTH, HEIGHT + 32)  # 32 px Slate title bar inside the client
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
        if not S['console']:
            S['console'] = True
            R['setup']['console'] = {c: console(c) for c in CONSOLE}
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return  # let the equip/chamber clip, HUD and the first zombies settle
            cur = viewport_size()
            if cur and cur != [WIDTH, HEIGHT] and S['vp_tries'] < VIEWPORT_TRIES:
                # Window.Resize takes the client size (title bar included): grow by the measured shortfall.
                S['vp_tries'] += 1
                req = S['vp_req'] or [WIDTH, HEIGHT]
                req = [req[0] + (WIDTH - cur[0]), req[1] + (HEIGHT - cur[1])]
                S['vp_req'] = req
                got = u.HoverAuthoring.resize_playtest_window(req[0], req[1])
                R['setup'].setdefault('viewport_resizes', []).append(
                    {'measured': cur, 'requested': req, 'client': [int(got.x), int(got.y)]})
                return  # measure again next tick
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
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('M4A1_CAPTURE_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
