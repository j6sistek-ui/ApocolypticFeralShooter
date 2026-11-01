"""ProveWalking.py - walking / crouch-walking receipt for Vexa (BP_Vexa_CLS_Parkour), per map and movement mode (2026-11-01).

Owner 2026-11-01: "the animation is totally broken for walking", "I'm hovering and floating in a crunched position",
B (crouch) gives a "penguin waddle" on both NYC maps (worse in NYC Survival, not on the desert map), wet footsteps on
dry NYC ground. This script measures it in PIE with scripted input and renders frames.

Re-run (one map per run; no AFS editor may be open; one rendered capture at a time):

  WALK_MAP=survival WALK_PHASE=before \
  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "M:/UnrealProjects/AFS/AFS.uproject" \
      -unattended -stdout -FullStdOutLogOutput -DisablePlugins=NwiroIntegrationKit -RenderOffscreen -nosplash \
      -ResX=1280 -ResY=720 "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.EffectsQuality 1" \
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveWalking.py > <log> 2>&1

  WALK_MAP   survival (L_NYC_Survival: Life Engine pass, then Classic) | explore (L_NYC_Explore, Classic) |
             postapo (the desert test pad /Game/JustBStudios/PostApo/Levels/PostApo, Classic)
  WALK_PHASE before | after (output subfolder)
  WALK_FRAMES 0 skips the rendered frames (logic only; -nullrhi then works too)
  WALK_TESTS  comma list to run a subset (walk,curve,kerb,jump,sprintjump,hops,crouch,crouchstrafe,slide,crawl,
             holdmove)
  WALK_VIEW  third (default: the test pads are toggled to the third-person view NYC Survival uses) | first
  WALK_TRAJ  1 (default, the review fix) | 0: hover.LifeEngineMoveLimits 0, the pre-fix MOVE_None max speed 0
  PROOF_OUT  output root (default D:/AFS_Comparisons/Walking_20261101)

Per mode: walk (W 4 s on the longest clear lane from the start), curve (W 3 s while the view yaws 30 deg/s), kerb
(walk up a 5-25 cm step found by floor traces near the start and back down, if any), jump (one Space press mid-walk), sprintjump (the same at a sprint),
crouch (tap B at rest = crouch, then W 3 s), slide (sprint, tap B while moving = slide, keep W), crawl (hold B 1 s at
rest = prone hands-and-knees, then W 2 s). Each test starts standing (a crouch left over is tapped off). Every tick logs
UHoverIntegrationAuthoring::DescribeWalkState: movement mode, Life Engine active / solver grounded / hand-off flag,
capsule half height, bIsCrouched, floor distance + surface (physical material, material) under the capsule, mesh
relative Z, pelvis / foot heights over the floor, velocity, the CharacterMovement acceleration, physics volume / water,
and the CLS AnimData fields after Package_AnimData. Frames: side camera at foot height and a 3/4 camera, 10 fps each,
for 3 s of the walk, the crouch-walk, the slide and the crawl.
2026-11-01 review additions: per-foot world position and height over the floor under that foot, and a foot-slide
metric per test (world XY speed of each ball while it is within 3 cm of the floor, against the capsule speed); hops
(repeated jumps with mid-air presses, the owner's hand-off pattern), melee (V while walking and mid-jump), crouchstrafe (crouched D / S) and holdmove (hold
B while walking = dive, then W), kerbsprint (sprint up over the kerb, turn, sprint back down off it), crouchaim (crouched + RMB aim, D then S);
the CLS motion matching database / clip / play rate per tick (motion_matching per test); foot_lock
(contact-phase foot speed, threshold-free; the receipt's main slide number); occlusion-aware cameras; PostApo foliage hidden in the capture only. The log is harvested for HOVER_PARKOUR_YIELD / RESUME, LIFE_ENGINE
switches and the tick-prerequisite cycle warnings.

Output D:/AFS_Comparisons/Walking_20261101/<phase>/<map>/receipt.json and frames/<mode>_<test>_<view>_NNN.png.
Changes only the unsaved Play world.
"""
import json
import math
import os
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAPS = {'survival': '/Game/HoverPrototype/Maps/L_NYC_Survival',
        'explore': '/Game/HoverPrototype/Maps/L_NYC_Explore',
        'postapo': '/Game/JustBStudios/PostApo/Levels/PostApo'}
KEY = os.environ.get('WALK_MAP', 'survival')
PHASE = os.environ.get('WALK_PHASE', 'before')
FRAMES = os.environ.get('WALK_FRAMES', '1') != '0'
TESTS = [t for t in os.environ.get(
    'WALK_TESTS', 'walk,curve,kerb,kerbsprint,jump,sprintjump,hops,crouch,crouchstrafe,crouchaim,slide,crawl,holdmove').split(',') if t]
# Camera view of the run: 'third' (default) toggles the test pads (first person by default) to the third-person view
# the owner sees in NYC Survival; 'first' keeps the pad default. The view decides CLS Stance and the crawl clip:
# first person always aims (UsesAimFacing is true without bReview), so it runs the rifle stance and the supported
# belly crawl, while third person runs free facing, the unarmed stance and the owner's hands-and-knees crawl.
VIEW = os.environ.get('WALK_VIEW', 'third')
# hover.LifeEngineMoveLimits for the run: 1 = the 2026-11-01 review fix (walking limits under the solver), 0 = before.
TRAJ = os.environ.get('WALK_TRAJ', '1')
MAP = MAPS[KEY]
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/Walking_20261101') / PHASE / KEY
(OUT / 'frames').mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 1200
CROUCH = 'Gamepad_FaceButton_Right'  # B: AHoverTestController routes it to SetParkourCrouch on foot
SPRINT = 'Gamepad_LeftThumbstick'
AIM = 'RightMouseButton'
R = {'ok': False, 'map': MAP, 'phase': PHASE, 'errors': [], 'api_errors': [], 'setup': {}, 'tests': {}, 'log': {},
     'summary': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'mode': None, 'test': None, 'hold': set(), 'origin': None, 'yaw': None,
     'cams': None, 'shoot': None, 'cycle': 0, 'yaw_rate': 0.0, 'removed': 0}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'load_level failed'


def V(x, y, z):
    return u.Vector(float(x), float(y), float(z))


def save():
    (OUT / 'receipt.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s: %s' % (cmd, e))


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def release_all():
    for k in list(S['hold']):
        key(k, False)
    S['yaw_rate'] = 0.0


def clear_zombies(w):
    for name in ('ZE_ZombieCharacter', 'HoverZombie', 'HoverNYCZombie'):
        cls = getattr(u, name, None)
        if cls:
            for z in u.GameplayStatics.get_all_actors_of_class(w, cls):
                z.destroy_actor()
                S['removed'] += 1


# ------------------------------------------------------------------------------------------------------ traces
def _hit(hit):
    if hit is None:
        return None
    if isinstance(hit, tuple):
        hit = next((h for h in hit if isinstance(h, u.HitResult)), None)
        if hit is None:
            return None
    try:
        t = hit.to_tuple()
    except Exception:  # noqa: BLE001
        t = u.GameplayStatics.break_hit_result(hit)
    if not t or not t[0]:
        return None
    return t[5], t[7], t[9], t[3]  # point, normal, actor, distance


def trace(a, b):
    try:
        return _hit(u.SystemLibrary.line_trace_single(world(), a, b, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False,
                                                      [pawn()], u.DrawDebugTrace.NONE, True))
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('trace: %s' % str(e)[:160])
        return None


def ground_z(p, above=150, below=400):
    h = trace(p + V(0, 0, above), p - V(0, 0, below))
    return h[0].z if h else None


def lane(origin, yaw, length=2400):
    """Clear distance along yaw from origin: no hit at knee / chest height and no floor change over 30 cm."""
    d = V(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
    g0 = ground_z(origin)
    if g0 is None:
        return 0
    best = length
    for hgt in (45, 120):
        h = trace(V(origin.x, origin.y, g0 + hgt), V(origin.x, origin.y, g0 + hgt) + d * length)
        if h:
            best = min(best, h[3] - 60)
    for s in range(100, int(best), 100):
        g = ground_z(origin + d * s)
        if g is None or abs(g - g0) > 30:
            return s - 100
    return max(0, best)


def find_kerb(origin):
    """Nearest 5-25 cm step up within 9 m: a ray of floor samples whose height jumps once and stays up."""
    g0 = ground_z(origin)
    if g0 is None:
        return None
    best = None
    for k in range(24):
        yaw = k * 15.0
        d = V(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0)
        prev = g0
        for s in range(50, 900, 10):
            g = ground_z(origin + d * s)
            if g is None:
                break
            step = g - prev
            if abs(g - g0) > 30 and not 5 <= step <= 25:
                break
            if 5 <= step <= 25 and (best is None or s < best['dist']):
                # Must stay up for the next 1.5 m, and the approach must be clear at knee height.
                after = [ground_z(origin + d * (s + q)) for q in (30, 80, 150)]
                if all(a is not None and abs(a - g) < 6 for a in after) and \
                        not trace(V(origin.x, origin.y, g0 + 45), V(origin.x, origin.y, g0 + 45) + d * (s + 200)):
                    best = {'yaw': yaw, 'dist': s, 'height': round(step, 1), 'floor_z': round(g0, 1)}
                break
            prev = g
    return best


# ------------------------------------------------------------------------------------------------------ sampling
def state(p):
    try:
        return json.loads(u.HoverIntegrationAuthoring.describe_walk_state(p))
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('describe_walk_state: %s' % str(e)[:160])
        return {}


def sample(t):
    tr = S['test']
    if not tr:
        return
    row = state(pawn())
    row['t'] = round(t - tr['t0'], 3)
    tr['rows'].append(row)


# ------------------------------------------------------------------------------------------------------ cameras
def cams_follow():
    """Side camera at foot height (perpendicular to travel) and a 3/4 camera ahead of her, both tracking.

    2026-11-01 review fix: each camera is placed on the first candidate (either side, 380 / 300 / 230 cm out) with a
    clear line of sight to her pelvis and feet, at least 25 cm over the ground under the camera itself (the PostApo
    side frames were behind bushes and below the terrain edge); the side kept last time is preferred while clear."""
    p = pawn()
    loc = p.get_actor_location()
    v = p.get_velocity()
    if math.hypot(v.x, v.y) > 50:
        f = V(v.x, v.y, 0)
    else:
        yaw = math.radians(S['pc'].get_control_rotation().yaw)
        f = V(math.cos(yaw), math.sin(yaw), 0)
    n = math.hypot(f.x, f.y) or 1
    f = V(f.x / n, f.y / n, 0)
    right = V(-f.y, f.x, 0)
    g = ground_z(loc, above=20, below=300)
    floor = g if g is not None else loc.z - 97
    targets = (V(loc.x, loc.y, floor + 90), V(loc.x, loc.y, floor + 15))

    def place(name, offset, up, at):
        prefer = S.setdefault('cam_side', {}).get(name, 1)
        best = None
        for sign in (prefer, -prefer):
            for k in (1.0, 0.79, 0.6):
                c = V(loc.x, loc.y, 0) + offset(sign, k)
                cg = ground_z(V(c.x, c.y, floor + 200), above=0, below=600)
                c = V(c.x, c.y, max(floor + up, (cg if cg is not None else floor) + 25))
                if best is None:
                    best = c
                if not any(trace(c, t) for t in targets):
                    S['cam_side'][name] = sign
                    return c, at
        return best, at

    side = place('side', lambda sg, k: right * (380 * k * sg), 35, V(loc.x, loc.y, floor + 55))
    q34 = place('q34', lambda sg, k: (f * 330 + right * (330 * sg)) * k, 150, V(loc.x, loc.y, floor + 80))
    return {'side': side, 'q34': q34}


def view(name):
    cam = S['cams'][name]
    loc, at = cams_follow()[name]
    cam.set_actor_location_and_rotation(loc, u.MathLibrary.find_look_at_rotation(loc, at), False, False)
    S['pc'].set_view_target_with_blend(cam, 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


def shoot_tick():
    """10 fps per view at the fixed 1/30 s step: set side, capture side + set 3/4, capture 3/4."""
    sh = S['shoot']
    if not sh:
        return
    c = S['cycle'] % 3
    S['cycle'] += 1
    if c == 0:
        view('side')
    elif c == 1:
        u.HoverAuthoring.capture_world_frame(str(OUT / 'frames' / ('%s_side_%03d.png' % (sh, S['frame']))))
        view('q34')
    else:
        u.HoverAuthoring.capture_world_frame(str(OUT / 'frames' / ('%s_q34_%03d.png' % (sh, S['frame']))))
        S['frame'] += 1


def shoot(on):
    def f(t):
        if not FRAMES:
            return
        if on:
            S['shoot'] = '%s_%s' % (S['mode'], S['test']['name'])
            S['cycle'] = 0
            S['frame'] = 0
        else:
            S['shoot'] = None
            S['pc'].set_view_target_with_blend(pawn(), 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    return f


# ------------------------------------------------------------------------------------------------------ plan
def reset_to(yaw_key):
    def f(t):
        release_all()
        p = pawn()
        o = S['origin']
        yaw = R['setup'][yaw_key] if isinstance(yaw_key, str) else S['yaw']
        p.set_actor_location_and_rotation(V(*o), u.Rotator(roll=0, pitch=0, yaw=yaw), False, True)
        S['pc'].set_control_rotation(u.Rotator(roll=0.0, pitch=-10.0, yaw=yaw))
        try:
            p.get_movement_component().stop_movement_immediately()
            lm = p.get_editor_property('life_movement')
            if lm:
                lm.set_hl_velocity(V(0, 0, 0))
        except Exception as e:  # noqa: BLE001
            R['api_errors'].append('reset: %s' % str(e)[:120])
    return f


def stand(t):
    """Tap B off any crouch / prone left over from the previous test (a short press uncrouches)."""
    if state(pawn()).get('crouched'):
        key(CROUCH, True)
        S['stand_release'] = t + 0.15


def begin(name):
    def f(t):
        S['test'] = {'name': name, 't0': t, 'rows': [], 'marks': {}}
    return f


def mark(label):
    def f(t):
        if S['test']:
            S['test']['marks'][label] = round(t - S['test']['t0'], 3)
    return f


def end(t):
    tr = S['test']
    S['test'] = None
    if tr:
        R['tests'].setdefault(S['mode'], {})[tr['name']] = analyse(tr)
        save()


def press(*names):
    return lambda t: [key(n, True) for n in names]


def lift(*names):
    return lambda t: [key(n, False) for n in names]


def yaw_rate(r):
    def f(t):
        S['yaw_rate'] = r
    return f


def plan(modes):
    q = []
    idle = (lambda t: None)

    def test(name, yaw_key, steps):
        q.append((0.3, stand))
        q.append((0.6, reset_to(yaw_key)))
        q.append((1.0, begin(name)))
        q.extend(steps)
        q.append((0.0, end))

    for mode in modes:
        def start(t, mode=mode):
            S['mode'] = mode
            if KEY == 'survival':
                console('LifeEngine %d' % (1 if mode == 'life' else 0))
        q.append((0.5, start))
        if 'walk' in TESTS:
            test('walk', 'walk_yaw', [(0.0, press('W')), (1.0, shoot(True)), (3.0, shoot(False)),
                                      (0.0, mark('release')), (0.0, lift('W')), (1.0, idle)])
        if 'curve' in TESTS:
            test('curve', 'walk_yaw', [(0.0, press('W')), (0.6, yaw_rate(30.0)), (3.0, yaw_rate(0.0)),
                                       (0.0, lift('W')), (0.8, idle)])
        if 'kerb' in TESTS and R['setup'].get('kerb'):
            up = (R['setup']['kerb']['dist'] + 250) / 500.0
            test('kerb', 'kerb_yaw', [(0.0, press('W')), (0.0, mark('walk')), (up, lift('W')), (0.0, press('S')),
                                      (up + 0.3, lift('S')), (0.8, idle)])
        if 'kerbsprint' in TESTS and R['setup'].get('kerb'):
            # Sprint up over the kerb and on, turn round, sprint back down off it (solver ground flag on step-downs).
            def turn(t):
                r = S['pc'].get_control_rotation()
                S['pc'].set_control_rotation(u.Rotator(roll=0.0, pitch=r.pitch, yaw=r.yaw + 180.0))
            test('kerbsprint', 'kerb_yaw', [(0.0, press(SPRINT, 'W')), (1.6, lift('W')), (0.3, turn),
                                            (0.2, press('W')), (2.0, lift('W', SPRINT)), (0.8, idle)])
        if 'jump' in TESTS:
            test('jump', 'walk_yaw', [(0.0, press('W')), (1.0, press('SpaceBar')), (0.1, lift('SpaceBar')),
                                      (1.6, lift('W')), (0.8, idle)])
        if 'sprintjump' in TESTS:
            test('sprintjump', 'walk_yaw', [(0.0, press(SPRINT, 'W')), (1.2, press('SpaceBar')),
                                            (0.1, lift('SpaceBar')), (1.5, lift('W', SPRINT)), (0.8, idle)])
        if 'hops' in TESTS:
            # The owner's NYC log: each "suspended (parkour template)" came ~0.5 s after a landing pulse and ended
            # on the next landing, i.e. mid-air during repeated jumps. Repeated jumps with a second press mid-air
            # (0.35 s after take-off) and a press just before landing (0.75 s), four times each.
            steps = [(0.0, press('W')), (0.8, idle)]
            for k in range(4):
                steps += [(0.0, mark('hop%d' % k)), (0.0, press('SpaceBar')), (0.1, lift('SpaceBar')),
                          (0.25, press('SpaceBar')), (0.1, lift('SpaceBar')), (0.3, press('SpaceBar')),
                          (0.1, lift('SpaceBar')), (0.5, idle)]
            steps += [(0.0, lift('W')), (0.8, idle)]
            test('hops', 'walk_yaw', steps)
        if 'melee' in TESTS:
            # Melee (V) while walking, twice, and once mid-jump: QA_Melee carries root motion, a hand-off reason.
            test('melee', 'walk_yaw', [(0.0, press('W')), (0.8, press('V')), (0.1, lift('V')), (1.2, press('V')),
                                       (0.1, lift('V')), (1.2, press('SpaceBar')), (0.1, lift('SpaceBar')),
                                       (0.2, press('V')), (0.1, lift('V')), (1.5, lift('W')), (0.8, idle)])
        if 'crouch' in TESTS:
            test('crouch', 'walk_yaw', [(0.0, press(CROUCH)), (0.15, lift(CROUCH)), (0.8, mark('walk')),
                                        (0.0, press('W')), (0.3, shoot(True)), (3.0, shoot(False)), (0.0, lift('W')),
                                        (0.8, idle)])
        if 'crouchstrafe' in TESTS:
            # Crouched, move right (D) then back (S): the CLS crouch database has a single forward clip.
            test('crouchstrafe', 'walk_yaw', [(0.0, press(CROUCH)), (0.15, lift(CROUCH)), (0.8, mark('walk')),
                                              (0.0, press('D')), (0.3, shoot(True)), (2.0, shoot(False)),
                                              (0.0, lift('D')), (0.0, press('S')), (2.0, lift('S')), (0.8, idle)])
        if 'crouchaim' in TESTS:
            # Crouched and aiming (RMB): she faces the aim, so moving right / back must use sideways / backward
            # crouch clips (the owner aims a lot in NYC Survival).
            test('crouchaim', 'walk_yaw', [(0.0, press(CROUCH)), (0.15, lift(CROUCH)), (0.3, press(AIM)),
                                           (0.5, mark('walk')), (0.0, press('D')), (0.3, shoot(True)),
                                           (2.0, shoot(False)), (0.0, lift('D')), (0.0, press('S')), (2.0, lift('S')),
                                           (0.0, lift(AIM)), (0.8, idle)])
        if 'slide' in TESTS:
            test('slide', 'walk_yaw', [(0.0, press(SPRINT, 'W')), (1.2, mark('tap')), (0.0, press(CROUCH)),
                                       (0.15, lift(CROUCH)), (0.0, lift(SPRINT)), (0.0, shoot(True)),
                                       (2.5, shoot(False)), (0.0, lift('W')), (0.8, idle)])
        if 'crawl' in TESTS:
            test('crawl', 'walk_yaw', [(0.0, press(CROUCH)), (1.0, mark('walk')), (0.0, press('W')),
                                       (0.3, shoot(True)), (2.0, shoot(False)), (0.0, lift('W', CROUCH)),
                                       (0.8, idle)])
        if 'holdmove' in TESTS:
            # Hold B while walking (the owner's "holding B"): moving hold = dive to the belly, then crawl on with W.
            test('holdmove', 'walk_yaw', [(0.0, press('W')), (1.2, mark('hold')), (0.0, press(CROUCH)),
                                          (0.0, shoot(True)), (1.2, mark('walk')), (2.0, shoot(False)),
                                          (0.0, lift('W', CROUCH)), (0.8, idle)])
    q.append((0.5, lambda t: finish()))
    S['queue'] = q


# ------------------------------------------------------------------------------------------------------ analysis
def analyse(tr):
    rows = tr['rows']
    out = {'marks': tr['marks'], 'samples': len(rows)}
    if not rows:
        return out
    t_walk = tr['marks'].get('walk', 0.0)
    moving = [r for r in rows if r['t'] >= t_walk + 0.6 and r.get('vel') and math.hypot(*r['vel'][:2]) > 50]
    out['moving_samples'] = len(moving)

    def stat(key, rs=None, f=None):
        vals = [f(r) if f else r.get(key) for r in (rs if rs is not None else moving)]
        vals = [v for v in vals if isinstance(v, (int, float))]
        if not vals:
            return None
        return {'min': round(min(vals), 2), 'max': round(max(vals), 2), 'mean': round(sum(vals) / len(vals), 2)}

    speed = lambda r: math.hypot(*r['vel'][:2])  # noqa: E731
    acc = lambda r: math.hypot(*r['cmc_accel'][:2]) if r.get('cmc_accel') else None  # noqa: E731
    out['speed'] = stat(None, f=speed)
    out['cmc_accel'] = stat(None, f=acc)
    out['cmc_accel_zero_frac'] = round(sum(1 for r in moving if (acc(r) or 0) < 1) / max(1, len(moving)), 3)
    for k in ('floor_dist', 'half_height', 'mesh_rel_z', 'pelvis_z', 'ball_l_z', 'ball_r_z', 'foot_l_z', 'foot_r_z'):
        out[k] = stat(k)
    grounded = [r for r in moving if r.get('on_ground')]
    out['grounded_frac'] = round(len(grounded) / max(1, len(moving)), 3)
    out['falling_frames'] = sum(1 for r in moving if r.get('falling'))
    out['float_frames_over_3cm'] = sum(1 for r in grounded if abs(r.get('floor_dist', 0) or 0) > 3)
    out['min_foot_over_floor'] = stat(None, f=lambda r: min(r.get('ball_l_z', 99), r.get('ball_r_z', 99)))
    out['crouched_frac'] = round(sum(1 for r in moving if r.get('crouched')) / max(1, len(moving)), 3)
    out['modes'] = sorted({r.get('mode') for r in rows})
    out['life_active_frac'] = round(sum(1 for r in moving if r.get('life_active')) / max(1, len(moving)), 3)
    flips = 0
    for a, b in zip(rows, rows[1:]):
        if a.get('life_active') != b.get('life_active'):
            flips += 1
    out['life_switches'] = flips
    out['override_frames'] = sum(1 for r in rows if r.get('template_override'))
    out['solver_air_frames'] = sum(1 for r in rows if r.get('life_active') and r.get('solver_grounded') is False)
    out['water'] = sorted({str(r.get('water_volume')) for r in rows})
    out['volumes'] = sorted({r.get('volume', '') for r in rows})
    out['swimming_frames'] = sum(1 for r in rows if r.get('swimming'))
    out['floor_surfaces'] = sorted({'%s | %s | %s' % (r.get('floor_physmat'), r.get('floor_material'),
                                                      r.get('floor_actor')) for r in rows})[:12]
    # CLS AnimData as packaged: value sets over the moving frames.
    anim_keys = set()
    for r in moving:
        anim_keys |= set((r.get('anim') or {}).keys())
    out['anim_fields'] = {}
    for k in sorted(anim_keys):
        vals = [(r.get('anim') or {}).get(k) for r in moving]
        if k in ('InputAcceleration', 'Velocity'):
            mags = []
            for v in vals:
                m = re.findall(r'[-\d.]+', v or '')
                if len(m) >= 2:
                    mags.append(math.hypot(float(m[0]), float(m[1])))
            out['anim_fields'][k] = {'mag_min': round(min(mags), 1) if mags else None,
                                     'mag_max': round(max(mags), 1) if mags else None,
                                     'zero_frac': round(sum(1 for m in mags if m < 1) / max(1, len(mags)), 3)}
        elif k in ('ActorTransform', 'OrientationIntent'):
            continue
        else:
            counts = {}
            for v in vals:
                counts[v] = counts.get(v, 0) + 1
            out['anim_fields'][k] = counts
    # Gait / state flips over the moving window: a stop/start loop shows as many flips.
    for k in ('MovementState', 'Gait', 'MovementMode', 'Stance'):
        seq = [(r.get('anim') or {}).get(k) for r in moving]
        out.setdefault('anim_flips', {})[k] = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    out['foot_slide'] = foot_slide(moving)
    out['foot_lock'] = foot_lock(rows, t_walk + 0.6)
    # What CLS motion matching played over the moving window: database / clip counts and the mean wanted play rate.
    mm = {}
    for r in moving:
        for m in r.get('mm') or []:
            k = '%s / %s' % (m.get('db'), m.get('anim'))
            e = mm.setdefault(k, {'n': 0, 'rate': 0.0})
            e['n'] += 1
            e['rate'] += m.get('rate') or 0
    out['motion_matching'] = {k: {'n': v['n'], 'rate': round(v['rate'] / v['n'], 2)}
                              for k, v in sorted(mm.items(), key=lambda kv: -kv[1]['n'])}
    out['rows'] = [{k: r.get(k) for k in ('t', 'mode', 'on_ground', 'falling', 'life_active', 'solver_grounded',
                                          'template_override', 'crouched', 'wants_crouch', 'half_height',
                                          'mesh_rel_z', 'floor_dist', 'pelvis_z', 'ball_l_z', 'ball_r_z', 'vel',
                                          'cmc_accel', 'sliding', 'prone', 'root_motion', 'montage', 'cls_montage',
                                          'rifle_stance', 'crouch_tag', 'water_volume', 'swimming', 'floor_physmat',
                                          'floor_material', 'gravity_scale', 'ball_l_own', 'ball_r_own', 'ball_l_w',
                                          'ball_r_w', 'max_speed', 'max_braking', 'aim_facing', 'mm')} |
                   {'anim': {k: v for k, v in (r.get('anim') or {}).items()
                             if k not in ('ActorTransform', 'OrientationIntent')}} for r in rows]
    return out


def foot_lock(rows, t0):
    """Foot lock (2026-11-01 review): per ball, from t0 on while she moves, the world XY speed per tick. contact_speed
    = mean speed over the 30% of ticks where that ball is lowest (its contact phase, threshold-free); stance_frac =
    share of ticks under 60 cm/s (the foot standing still on the ground); lift_max = highest the ball rises."""
    out = {}
    rows = [r for r in rows if r.get('vel') and math.hypot(*r['vel'][:2]) > 50 and (r.get('t') or 0) >= t0]
    body = [math.hypot(*r['vel'][:2]) for r in rows]
    out['body_speed'] = round(sum(body) / len(body), 1) if body else None
    both = []
    for b in ('ball_l', 'ball_r'):
        sp = []
        for a, c in zip(rows, rows[1:]):
            dt = c['t'] - a['t']
            h = c.get(b + '_own', c.get(b + '_z'))
            if dt <= 0 or h is None or not a.get(b + '_w') or not c.get(b + '_w'):
                continue
            sp.append((h, math.hypot(c[b + '_w'][0] - a[b + '_w'][0], c[b + '_w'][1] - a[b + '_w'][1]) / dt))
        if not sp:
            continue
        low = sorted(sp)[:max(1, int(len(sp) * 0.3))]
        out[b] = {'contact_speed': round(sum(s[1] for s in low) / len(low), 1),
                  'stance_frac': round(sum(1 for s in sp if s[1] < 60) / len(sp), 3),
                  'lift_max': round(max(s[0] for s in sp), 1), 'ticks': len(sp)}
        both.append(out[b]['contact_speed'])
    out['contact_speed'] = round(sum(both) / len(both), 1) if both else None
    return out


def foot_slide(rows, planted_cm=3.0):
    """Horizontal skate of planted feet (2026-11-01 review): per ball, the world XY speed between consecutive ticks
    while the ball is within planted_cm of the floor directly under it, against the capsule speed. A clean walk
    keeps planted feet near 0 cm/s; a foot that stays down while the body travels skates at the body speed."""
    out = {}
    body = [math.hypot(*r['vel'][:2]) for r in rows if r.get('vel')]
    out['body_speed'] = round(sum(body) / len(body), 1) if body else None
    for b in ('ball_l', 'ball_r'):
        speeds, plants, run, lifts = [], [], 0, []
        for a, c in zip(rows, rows[1:]):
            ha = a.get(b + '_own', a.get(b + '_z'))
            hc = c.get(b + '_own', c.get(b + '_z'))
            dt = (c.get('t') or 0) - (a.get('t') or 0)
            if ha is None or hc is None or dt <= 0 or not a.get(b + '_w') or not c.get(b + '_w'):
                continue
            if ha < planted_cm and hc < planted_cm:
                speeds.append(math.hypot(c[b + '_w'][0] - a[b + '_w'][0], c[b + '_w'][1] - a[b + '_w'][1]) / dt)
                run += dt
            elif run:
                plants.append(run)
                run = 0
            lifts.append(hc)
        if run:
            plants.append(run)
        speeds.sort()
        q = lambda f: round(speeds[min(len(speeds) - 1, int(f * len(speeds)))], 1) if speeds else None  # noqa
        out[b] = {'planted_pairs': len(speeds), 'slide_mean': round(sum(speeds) / len(speeds), 1) if speeds else None,
                  'slide_p50': q(0.5), 'slide_p90': q(0.9), 'plants': len(plants),
                  'plant_mean_s': round(sum(plants) / len(plants), 3) if plants else None,
                  'plant_max_s': round(max(plants), 3) if plants else None,
                  'lift_max': round(max(lifts), 1) if lifts else None}
    sl = [out[b]['slide_mean'] for b in ('ball_l', 'ball_r') if out[b]['slide_mean'] is not None]
    out['slide_mean'] = round(sum(sl) / len(sl), 1) if sl else None
    out['slide_ratio'] = round(out['slide_mean'] / out['body_speed'], 3) if sl and out['body_speed'] else None
    return out


def harvest_log():
    path = None
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        path = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        pass
    if not path:
        path = str(Path(u.Paths.project_log_dir()) / 'AFS.log')
    R['log']['path'] = path
    if not Path(path).exists():
        R['errors'].append('log not found: ' + path)
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    pick = lambda tag, n=30: [l[-220:] for l in lines if tag in l][-n:]  # noqa: E731
    for tag in ('HOVER_PARKOUR_YIELD', 'HOVER_PARKOUR_RESUME', 'HOVER_PARKOUR_LAUNCH', 'LIFE_ENGINE',
                'HOVER_FOOTSTEP'):
        R['log'][tag] = {'count': len([l for l in lines if tag in l]), 'samples': pick(tag, 20)}
    R['log']['tick_cycle_component'] = len([l for l in lines if 'would form a cycle' in l and
                                            'LifeEngine[TickComponent], could not use' in l])
    R['log']['tick_cycle_actor'] = len([l for l in lines if 'would form a cycle' in l and
                                        '[TickActor], could not use' in l and 'LifeEngine' in l])
    R['log']['tick_cycle_any'] = len([l for l in lines if 'would form a cycle' in l])
    R['log']['tick_cycle_samples'] = pick('would form a cycle', 4)


def summarise():
    s = {}
    for mode, tests in R['tests'].items():
        for name, a in tests.items():
            s['%s.%s' % (mode, name)] = {k: a.get(k) for k in (
                'speed', 'cmc_accel_zero_frac', 'floor_dist', 'float_frames_over_3cm', 'falling_frames',
                'grounded_frac', 'half_height', 'mesh_rel_z', 'pelvis_z', 'min_foot_over_floor', 'crouched_frac',
                'life_active_frac', 'life_switches', 'solver_air_frames', 'anim_flips', 'swimming_frames', 'water',
                'foot_slide', 'foot_lock', 'motion_matching')}
            af = a.get('anim_fields', {})
            s['%s.%s' % (mode, name)]['anim'] = {k: af.get(k) for k in (
                'InputAcceleration', 'Gait', 'MovementState', 'MovementMode', 'Stance', 'RotationMode',
                'CurrentMaxAcceleration',
                'CurrentMaxDeceleration')}
    s['log'] = {k: (v['count'] if isinstance(v, dict) else v) for k, v in R['log'].items()
                if k not in ('path', 'tick_cycle_samples')}
    R['summary'] = s
    R['ok'] = bool(R['tests']) and not R['errors']


def finish():
    if S['end']:
        return
    release_all()
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def setup(p):
    loc = p.get_actor_location()
    S['origin'] = (loc.x, loc.y, loc.z + 2.0)
    S['yaw'] = S['pc'].get_control_rotation().yaw
    o = V(*S['origin'])
    lanes = sorted(((lane(o, S['yaw'] + k * 22.5), (S['yaw'] + k * 22.5) % 360) for k in range(16)), reverse=True)
    R['setup'].update({'pawn': p.get_class().get_name(), 'start': [round(v, 1) for v in S['origin']],
                       'start_yaw': round(S['yaw'], 1), 'walk_yaw': lanes[0][1], 'walk_lane_cm': lanes[0][0],
                       'lanes': lanes[:5], 'game_mode': u.GameplayStatics.get_game_mode(world()).get_class().get_name(),
                       'life_engine': bool(p.get_editor_property('life_movement')),
                       'state_at_start': state(p)})
    k = find_kerb(o)
    R['setup']['kerb'] = k
    if k:
        R['setup']['kerb_yaw'] = k['yaw']


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
                    print('PROVE_WALKING_DONE', json.dumps(R['summary'], default=str)[:4000], flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('walking proof timeout')
        if not S['play']:
            if time.monotonic() - S['start'] > 7:
                try:
                    u.HoverAuthoring.configure_offscreen_display(WIDTH + 16, HEIGHT + 80)
                except Exception as e:  # noqa: BLE001
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
        if S['origin'] is None:
            if t - S['t_first'] < 3.0:
                return
            if S.get('setup_at') is None:
                console('hover.LifeEngineMoveLimits %s' % TRAJ)
                if KEY != 'survival' and VIEW == 'third' and state(p).get('aim_facing'):
                    console('HoverView')
                if FRAMES:
                    # Render-only, this capture: bushes / grass hid her feet from the foot-height side camera
                    # (PostApo in the review; NYC street planters in round 2). The traces cannot see foliage.
                    for cmd in ('ShowFlag.InstancedFoliage 0', 'ShowFlag.InstancedGrass 0', 'ShowFlag.Foliage 0'):
                        console(cmd)
                S['setup_at'] = t
                return
            if t - S['setup_at'] < 0.5:
                return
            for cmd in ('Log LogTemp Verbose', 'DisableAllScreenMessages', 'r.MotionBlurQuality 0',
                        'r.Streaming.FullyLoadUsedTextures 1'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            if FRAMES:
                S['cams'] = {n: u.HoverAuthoring.spawn_playtest_actor(
                    u.CameraActor, u.Transform(location=V(0, 0, 500), rotation=u.Rotator())) for n in ('side', 'q34')}
                for c in S['cams'].values():
                    try:
                        c.camera_component.set_editor_property('field_of_view', 60.0)
                        c.camera_component.set_editor_property('constrain_aspect_ratio', False)
                    except Exception as e:  # noqa: BLE001
                        R['api_errors'].append('camera: %s' % str(e)[:120])
            setup(p)
            R['setup']['view'] = VIEW if KEY != 'survival' else 'third (survival default)'
            R['setup']['move_limits_cvar'] = TRAJ
            save()
            plan(['life', 'classic'] if KEY == 'survival' and R['setup']['life_engine'] else ['classic'])
            S['next'] = t
            return
        if S['yaw_rate']:
            r = pc.get_control_rotation()
            pc.set_control_rotation(u.Rotator(roll=0.0, pitch=r.pitch, yaw=r.yaw + S['yaw_rate'] / 30.0))
        if S.get('stand_release') and t >= S['stand_release']:
            key(CROUCH, False)
            S['stand_release'] = None
        sample(t)
        shoot_tick()
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_WALKING_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
