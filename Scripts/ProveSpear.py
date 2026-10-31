"""ProveSpear.py - in-game receipt for Vexa's spear on L_NYC_Survival (AFS 2026-10-31, spear item).

Needs apply_spear.py built and Scripts/AuthorSpear.py run. Rendered (stills), one capture at a time, GPU budget 1280x720:
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveSpear.py
      -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720
      "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.TextureQuality 1, sg.EffectsQuality 1"

PIE at 1280x720, test input isolated, fixed 1/30 s step, LogTemp Verbose. Steps:
 1. Give: the spear must already be on the quickbar from DA_NYCWaves (FindSpearSlot); if not, GiveSpear(4) and the
    receipt says so.
 2. Cycle: Y-equivalent G taps (CycleWeapon) until IsSpearSelected (the number key 4 only as a recorded fallback).
    Checks the melee flag, the stance loop, the gun and katana hidden; still "stance".
 3. Targets: the first live NYC zombies are unpossessed and pinned every tick at fixed spots in front of Vexa along her
    control yaw: on the line at 120 / 200 / 265 / 340 cm, at 150 cm +-28 deg (swing arc) and 150 cm at 70 deg (outside
    every arc). Extra zombies are removed as they spawn, so nothing else can reach her.
 4. Light combo: V at 0 / 0.30 / 0.80 s (jab, buffered thrust, buffered swing). Stills mid-jab and mid-swing.
 5. Heavy: LMB held 1.1 s (wind-up still) and released (strike still).
 6. LMB tap: a light strike on release. 7. G tap: the gun comes back.
Per strike: name, hits (C++ counter), the head's reach (C++ GetLastTipReach and a per-tick Python sample), the slots
struck (HOVER_SPEAR_HIT actor names), whether a clip played (HOVER_SPEAR_STRIKE begin played=1) and the driver
montages seen. Receipt D:/AFS_Comparisons/OtherItems_20261031/spear/proof/proof.json. Changes only the Play world.
"""
import json
import math
import os
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/OtherItems_20261031/spear/proof')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
TIMEOUT = 600
ZOMBIE_WAIT = 120.0
# (label, distance cm, yaw offset deg): + yaw is to her right.
SLOTS = [('F120', 120, 0), ('F200', 200, 0), ('L28_150', 150, -28), ('R28_150', 150, 28), ('F265', 265, 0),
         ('F340', 340, 0), ('R70_150', 150, 70)]
ZCLASS = getattr(u, 'ZE_ZombieCharacter', None) or getattr(u, 'HoverNYCZombie', None)
R = {'ok': False, 'errors': [], 'api_errors': [], 'setup': {}, 'cycle': [], 'held': {}, 'strikes': [], 'samples': {},
     'targets': {}, 'heavy': {}, 'tap': {}, 'holster': {}, 'log': {}, 'stills': [], 'checks': {}}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 'done': False, 'queue': [],
     'next': None, 'last_step_t': None, 'cam': None, 'hold': set(), 'targets': {}, 'removed': 0, 'arranged': False,
     'yaw': 0.0, 'origin': None, 'caps': [], 'seen_strike': None, 'strike_t0': None, 'finished': 0, 'montages': {},
     'tip_max': {}, 'shot_names': set(), 'wait_t0': None, 'frozen': set()}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'


def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)]


def call(obj, name, *args, default=None):
    try:
        return getattr(obj, name)(*args)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s.%s: %s' % (type(obj).__name__, name, str(e)[:160]))
        return default


def drop_ai(ctrl):
    """Unpossess a zombie's AI (5.8 Python names it un_possess; fixed 2026-10-31 after the first run let the
    zombies reach and kill her during setup), else destroy the controller."""
    for name in ('un_possess', 'unpossess'):
        fn = getattr(ctrl, name, None)
        if fn:
            try:
                fn()
                return True
            except Exception as e:  # noqa: BLE001
                R['api_errors'].append('%s.%s: %s' % (type(ctrl).__name__, name, str(e)[:160]))
    try:
        ctrl.destroy_actor()
        return True
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('drop_ai destroy: %s' % str(e)[:160])
        return False


def keep_vexa_alive(p):
    # Same refill as ProveNukeAmmo: a stray hit during setup must not end the round (game over dilates time).
    try:
        c = p.get_editor_property('combat')
        s = c.get_editor_property('survival') if c else None
        if s and s.get_health() < s.get_max_health():
            s.set_health(s.get_max_health())
            R['refills'] = R.get('refills', 0) + 1
    except Exception as e:  # noqa: BLE001
        if 'keep_alive' not in str(R['api_errors']):
            R['api_errors'].append('keep_alive: %s' % str(e)[:160])


def prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s.%s: %s' % (type(obj).__name__, name, str(e)[:160]))
        return default


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('%s: %s' % (cmd, e))


def key(name, down):
    u.HoverAuthoring.test_key(S['pc'], name, 1.0 if down else 0.0, False)
    (S['hold'].add if down else S['hold'].discard)(name)


def combat():
    return prop(pawn(), 'combat')


def spear():
    c = combat()
    return prop(c, 'spear_weapon') if c else None


def forward():
    y = math.radians(S['yaw'])
    return u.Vector(math.cos(y), math.sin(y), 0.0)


def along(dist, yaw_off):
    y = math.radians(S['yaw'] + yaw_off)
    o = S['origin']
    return u.Vector(o.x + math.cos(y) * dist, o.y + math.sin(y) * dist, o.z)


# ---------------------------------------------------------------------------------------------------------------------
# Stills: move the camera actor, snap on the next tick (ReadPixels returns the frame already rendered).
# ---------------------------------------------------------------------------------------------------------------------
def schedule_still(name, at):
    if name not in S['shot_names']:
        S['shot_names'].add(name)
        S['caps'].append({'name': name, 't': at, 'moved': None})


def caps_tick(t):
    for c in list(S['caps']):
        if c['moved'] is None and t >= c['t'] - 1e-4:
            p = pawn()
            loc = p.get_actor_location()
            f = forward()
            right = u.Vector(-f.y, f.x, 0.0)
            cam_loc = loc + right * 380.0 + f * 140.0 + u.Vector(0, 0, 110)
            look = loc + f * 150.0 + u.Vector(0, 0, 25)
            S['cam'].set_actor_location_and_rotation(cam_loc, u.MathLibrary.find_look_at_rotation(cam_loc, look),
                                                     False, False)
            S['pc'].set_view_target_with_blend(S['cam'], 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
            c['moved'] = t
            c['strike'] = str(call(spear(), 'get_active_strike_name', default='')) if spear() else None
            c['charge'] = call(spear(), 'get_charge_alpha', default=None) if spear() else None
        elif c['moved'] is not None and t > c['moved']:
            fn = OUT / (c['name'] + '.png')
            u.HoverAuthoring.capture_world_frame(str(fn))
            R['stills'].append({'file': fn.name, 'strike': c.get('strike'), 'charge': c.get('charge'),
                                'game_t': round(t, 3)})
            S['caps'].remove(c)


# ---------------------------------------------------------------------------------------------------------------------
# Zombie targets
# ---------------------------------------------------------------------------------------------------------------------
def live_zombies(w):
    out = []
    for z in u.GameplayStatics.get_all_actors_of_class(w, ZCLASS) if ZCLASS else []:
        if not prop(z, 'is_dead', False):
            out.append(z)
    return out


def half_height(actor):
    cap = actor.get_component_by_class(u.CapsuleComponent)
    return cap.get_scaled_capsule_half_height() if cap else 90.0


def targets_tick(w):
    if not S['arranged']:
        return
    p = pawn()
    p_half = half_height(p)
    zs = live_zombies(w)
    names = {z.get_name(): z for z in zs}
    # Drop dead or destroyed targets; refill free slots from new zombies; remove the rest.
    for label in list(S['targets']):
        if S['targets'][label] not in names:
            R['targets'].setdefault('lost', []).append(label)
            del S['targets'][label]
    free = [s for s in SLOTS if s[0] not in S['targets']]
    for z in zs:
        if z.get_name() in S['targets'].values():
            continue
        if free and S.get('refill', True):
            label = free.pop(0)[0]
            S['targets'][label] = z.get_name()
            R['targets'].setdefault('assigned', []).append((label, z.get_name()))
            ctrl = z.get_controller()
            if ctrl:
                drop_ai(ctrl)
        else:
            z.destroy_actor()
            S['removed'] += 1
    for label, dist, yaw in SLOTS:
        z = names.get(S['targets'].get(label))
        if not z:
            continue
        spot = along(dist, yaw)
        spot.z = S['origin'].z - p_half + half_height(z)
        face = u.MathLibrary.find_look_at_rotation(spot, S['origin'])
        z.set_actor_location_and_rotation(spot, u.Rotator(roll=0, pitch=0, yaw=face.yaw), False, True)
        mc = z.get_movement_component()
        if mc:
            call(mc, 'stop_movement_immediately')


def arrange(t):
    p = pawn()
    S['origin'] = p.get_actor_location()
    S['yaw'] = S['pc'].get_control_rotation().yaw
    S['pc'].set_control_rotation(u.Rotator(roll=0, pitch=0, yaw=S['yaw']))
    S['arranged'] = True
    R['targets']['origin'] = vec(S['origin'])
    R['targets']['yaw'] = round(S['yaw'], 1)


def wait_for_zombies(t):
    """Holds the queue until enough zombies exist (the director spawns them over the first seconds)."""
    w = world()
    n = len(live_zombies(w))
    if S['wait_t0'] is None:
        S['wait_t0'] = t
    if n >= len(SLOTS) or (n >= 3 and t - S['wait_t0'] > 30.0) or t - S['wait_t0'] > ZOMBIE_WAIT:
        R['targets']['live_when_arranged'] = n
        R['targets']['waited_s'] = round(t - S['wait_t0'], 1)
        arrange(t)
        return
    S['queue'].insert(0, (0.5, wait_for_zombies))


# ---------------------------------------------------------------------------------------------------------------------
# Spear state watcher (every tick)
# ---------------------------------------------------------------------------------------------------------------------
def watch_tick(t):
    sp = spear()
    p = pawn()
    if not sp or not p:
        return
    name = str(call(sp, 'get_active_strike_name', default=''))
    swinging = bool(call(sp, 'is_swinging', default=False))
    charging = bool(call(sp, 'is_charging', default=False))
    label = ('charge' if charging else name) if (swinging or charging) else None
    if label != S['seen_strike']:
        S['seen_strike'] = label
        S['strike_t0'] = t
        if label == 'Jab':
            schedule_still('mid_jab', t + .17)
        elif label == 'Swing':
            schedule_still('mid_swing', t + .30)
        elif label == 'charge':
            schedule_still('heavy_windup', t + .85)
        elif label == 'Heavy':
            schedule_still('mid_heavy', t + .12)
    if label and S['origin'] is not None:
        tip = call(sp, 'get_tip_location')
        if tip:
            loc, f = p.get_actor_location(), forward()
            d = (tip.x - loc.x) * f.x + (tip.y - loc.y) * f.y
            S['tip_max'][label] = round(max(S['tip_max'].get(label, -1e9), d), 1)
        bridge = prop(p, 'locomotion_bridge')
        action = call(bridge, 'get_action') if bridge else None
        if action and call(bridge, 'is_action_playing', default=False):
            S['montages'].setdefault(label, set()).add(action.get_name())
    done = call(sp, 'get_strikes_finished', default=0) or 0
    if done > S['finished']:
        S['finished'] = done
        last = str(call(sp, 'get_last_strike_name', default=''))
        R['strikes'].append({'n': done, 'name': last, 'hits': call(sp, 'get_last_strike_hits'),
                             'tip_reach_cpp': round(call(sp, 'get_last_tip_reach', default=0) or 0, 1),
                             'tip_reach_py': S['tip_max'].get(last), 'game_t': round(t, 3),
                             'montages': sorted(S['montages'].get(last, set()) | (
                                 S['montages'].get('charge', set()) if last == 'Heavy' else set()))})
        S['tip_max'].pop(last, None)
        S['montages'].pop(last, None)
        if last == 'Heavy':
            S['montages'].pop('charge', None)
        save()


# ---------------------------------------------------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------------------------------------------------
def tap(name, hold=0.12):
    return [(0.0, lambda t: key(name, True)), (hold, lambda t: key(name, False))]


def cycle_try(left):
    def step(t):
        c = combat()
        sel = bool(call(c, 'is_spear_selected', default=False))
        inv = prop(c, 'inventory')
        R['cycle'].append({'t': round(t, 2), 'selected': sel,
                           'active_slot': call(inv, 'get_active_quickbar_slot') if inv else None})
        if sel or left < 0:
            return
        if left > 0:
            S['queue'][0:0] = tap('G', .15) + [(0.5, cycle_try(left - 1))]
        else:
            # Four G taps never reached it: the number key, recorded as a failed cycle check.
            R['cycle'].append({'fallback': 'number key 4'})
            S['queue'][0:0] = tap('Four', .1) + [(0.5, cycle_try(-1))]
    return step


def record_held(t):
    p, c, sp = pawn(), combat(), spear()
    katana = prop(p, 'melee_weapon')
    R['held'] = {'spear_selected': call(c, 'is_spear_selected'), 'melee_flag': call(p, 'is_melee_equipped'),
                 'stance_playing': call(sp, 'is_stance_playing') if sp else None,
                 'spear_hidden': prop(sp, 'hidden') if sp else None,
                 'katana_hidden': prop(katana, 'hidden') if katana else None,
                 'gun_actor': str(call(c, 'get_weapon')), 'hud': call(c, 'get_spear_hud_text'),
                 'spear_slot': call(c, 'find_spear_slot')}
    schedule_still('stance', t + .05)
    save()


def record_holster(t):
    c = combat()
    R['holster'] = {'spear_selected': call(c, 'is_spear_selected'), 'gun_actor': str(call(c, 'get_weapon')),
                    'melee_flag': call(pawn(), 'is_melee_equipped')}


def plan():
    q = [(1.0, cycle_try(4)), (1.5, record_held), (0.2, wait_for_zombies), (1.0, lambda t: None)]
    # Light combo on the melee input (V): jab, a press inside the jab's chain window, one inside the thrust's.
    q += tap('V', .08) + [(0.22, lambda t: key('V', True)), (0.08, lambda t: key('V', False)),
                          (0.42, lambda t: key('V', True)), (0.08, lambda t: key('V', False)), (1.8, lambda t: None)]
    # Heavy: hold the trigger past the threshold and through the full charge, then release.
    q += [(0.0, lambda t: key('LeftMouseButton', True)), (1.1, lambda t: key('LeftMouseButton', False)),
          (1.6, lambda t: None)]
    # A trigger tap is a light strike on release.
    q += [(0.0, lambda t: key('LeftMouseButton', True)), (0.08, lambda t: key('LeftMouseButton', False)),
          (1.2, lambda t: None)]
    q += tap('G', .15) + [(0.8, record_holster)]
    # Katana regression (added 2026-10-31): hold-R3 equivalent (ToggleMeleeWeapon), one V slash, back to the gun.
    # The katana's sweep must keep the shipped geometry: range = DA_AFS_Melee MeleeRange, radius = max(50, 2.5 x
    # MeleeRadius), sweeps at 0.22 / 0.30 / 0.38 / 0.48 s, first blocker per sweep (no pierce).
    q += [(0.3, katana_on)] + tap('V', .08) + [(1.3, katana_done), (0.5, lambda t: finish())]
    S['queue'] = q


def katana_on(t):
    p = pawn()
    call(p, 'toggle_melee_weapon')
    R['katana'] = {'equipped': call(p, 'is_melee_equipped'), 't_on': round(t, 2),
                   'live_targets': sorted(S['targets'].keys())}
    try:
        d = u.load_asset('/Game/HoverPrototype/ZombieEngine/DA_AFS_Melee.DA_AFS_Melee')
        ms = d.get_editor_property('melee_stats')
        rng, rad = ms.get_editor_property('melee_range'), ms.get_editor_property('melee_radius')
        R['katana']['expected'] = {'range': round(rng), 'radius': round(max(50.0, rad * 2.5))}
    except Exception as e:  # noqa: BLE001
        R['api_errors'].append('katana expected: %s' % str(e)[:160])


def katana_done(t):
    p = pawn()
    R['katana']['equipped_after_swing'] = call(p, 'is_melee_equipped')
    call(p, 'toggle_melee_weapon')
    R['katana']['equipped_end'] = call(p, 'is_melee_equipped')


# ---------------------------------------------------------------------------------------------------------------------
def harvest_log():
    path = None
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        path = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        pass
    path = path or str(Path(u.Paths.project_log_dir()) / 'AFS.log')
    R['log']['path'] = path
    if not Path(path).exists():
        R['errors'].append('log not found: ' + path)
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    pick = lambda tag, n=40: [l[l.find(tag):][:220] for l in lines if tag in l][-n:]  # noqa: E731
    for tag in ('HOVER_SPEAR_PROFILE', 'HOVER_SPEAR_READY', 'HOVER_SPEAR_GIVEN', 'HOVER_SPEAR_SELECTED',
                'HOVER_SPEAR_GRIP', 'HOVER_SPEAR_STANCE', 'HOVER_SPEAR_STRIKE', 'HOVER_SPEAR_SWEEP', 'HOVER_SPEAR_HIT',
                'HOVER_SPEAR_CHARGE', 'HOVER_SPEAR_HEAVY', 'HOVER_SPEAR_BUFFER', 'HOVER_CYCLE_WEAPON',
                'HOVER_MELEE_SWING_SOUND', 'HOVER_KATANA_SWEEP', 'HOVER_KATANA_HIT'):
        R['log'][tag] = pick(tag)
    R['log']['warnings'] = [l[-220:] for l in lines if ('Spear' in l or 'AS_Spear' in l) and
                            ('Warning' in l or 'Error' in l)][-12:]
    # Which slots each strike struck, from the HIT lines (actor names map to slot labels).
    slot_of = {v: k for k, v in R['targets'].get('assigned', [])}
    per = {}
    for l in R['log']['HOVER_SPEAR_HIT']:
        m = re.search(r'strike=(\w+) actor=(\S+) dist=(\d+)', l)
        if m:
            per.setdefault(m.group(1), []).append((slot_of.get(m.group(2), m.group(2)), int(m.group(3))))
    R['samples']['hits_by_strike'] = per
    R['samples']['clip_played'] = [bool(re.search(r'played=1', l)) for l in R['log']['HOVER_SPEAR_STRIKE']
                                   if ' begin ' in l]


def summarise():
    k = R.setdefault('katana', {})
    sweeps = R['log'].get('HOVER_KATANA_SWEEP') or []
    geo = set()
    struck = 0
    for l in sweeps:
        m = re.search(r'struck=(\d+) radius=(\d+) range=(\d+)', l)
        if m:
            struck += int(m.group(1))
            geo.add((int(m.group(3)), int(m.group(2))))
    k['sweep_lines'] = len(sweeps)
    k['struck_total'] = struck
    k['geometry_seen'] = sorted(geo)
    exp = k.get('expected')
    k['same_as_before'] = bool(exp and struck > 0 and geo == {(exp['range'], exp['radius'])})
    names = [s['name'] for s in R['strikes']]
    hits = {s['name']: s['hits'] for s in R['strikes']}
    per = R['samples'].get('hits_by_strike', {})
    R['checks'] = {
        'spear_selected_by_cycle': any(c.get('selected') for c in R['cycle']) and
                                   not any('fallback' in c for c in R['cycle']),
        'melee_flag_while_held': R['held'].get('melee_flag') is True,
        'katana_hidden_while_spear': R['held'].get('katana_hidden') is True,
        'gun_holstered_while_spear': R['held'].get('gun_actor') in ('None', None),
        'combo_order': names[:3] == ['Jab', 'Thrust', 'Swing'],
        'heavy_thrown': 'Heavy' in names and bool(R['log'].get('HOVER_SPEAR_HEAVY')),
        'tap_light_after_heavy': len(names) >= 5 and names[4] == 'Jab',
        'clips_played': bool(R['samples'].get('clip_played')) and all(R['samples']['clip_played']),
        'strikes_with_hits': sum(1 for s in R['strikes'] if (s['hits'] or 0) > 0),
        'gun_back_after_holster': R['holster'].get('spear_selected') is False,
        'stills': len(R['stills']),
        'farthest_hit_cm': {k: max(d for _, d in v) for k, v in per.items() if v},
        'hits_per_strike': hits,
    }
    c = R['checks']
    c['katana_same_as_before'] = R['katana'].get('same_as_before')
    R['ok'] = (c['spear_selected_by_cycle'] and c['melee_flag_while_held'] and c['combo_order'] and c['heavy_thrown']
               and c['clips_played'] and c['strikes_with_hits'] >= 2 and c['stills'] >= 3 and not R['errors']
               and bool(c['katana_same_as_before']))


def finish():
    if S['end']:
        return
    for k in list(S['hold']):
        key(k, False)
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
                    print('PROVE_SPEAR_DONE', json.dumps({'ok': R['ok'], 'checks': R['checks']}, default=str),
                          flush=True)
                u.unregister_slate_post_tick_callback(S['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - S['start'] > TIMEOUT:
            raise RuntimeError('proof timeout')
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
        keep_vexa_alive(p)
        if S['cam'] is None:
            if t - S['t_first'] < 3.0:
                return
            for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
                console(cmd)
            u.HoverAuthoring.isolate_test_input(pc)
            u.HoverAuthoring.set_playtest_fixed_step(True)
            S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
                u.CameraActor, u.Transform(location=u.Vector(0, 0, 500), rotation=u.Rotator()))
            c = combat()
            sp = spear()
            R['setup'] = {'pawn': p.get_class().get_name(), 'third_person': call(p, 'is_third_person_view'),
                          'combat': bool(c), 'spear_actor': sp.get_name() if sp else None,
                          'spear_slot': call(c, 'find_spear_slot') if c else None, 'start': vec(p.get_actor_location())}
            if not sp:
                raise RuntimeError('no spear actor: DA_NYC_Spear missing (run AuthorSpear.py) or not NYC rules')
            if not R['setup']['spear_slot']:
                R['setup']['given'] = call(c, 'give_spear', 4)
                R['setup']['spear_slot'] = call(c, 'find_spear_slot')
            plan()
            S['next'] = t
            return
        if not S['arranged']:
            # Until the targets are pinned, every zombie loses its AI where it spawned, so none can reach her.
            for z in live_zombies(w):
                if z.get_name() not in S['frozen']:
                    ctrl = z.get_controller()
                    if ctrl and drop_ai(ctrl):
                        S['frozen'].add(z.get_name())
        targets_tick(w)
        watch_tick(t)
        caps_tick(t)
        if S['queue'] and t >= S['next'] - 1e-4 and t != S['last_step_t']:
            S['last_step_t'] = t
            delay, fn = S['queue'].pop(0)
            fn(t)
            if S['queue']:
                S['next'] = t + S['queue'][0][0]
        R['targets']['removed'] = S['removed']
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_SPEAR_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
