"""ProveZombieDiversity.py - rendered in-game receipt for the NYC Survival zombie diversity pass (2026-10-31).

  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" "M:/UnrealProjects/AFS/AFS.uproject"
      -unattended -stdout -FullStdOutLogOutput -RenderOffscreen -nosplash -ResX=1280 -ResY=720
      "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.GlobalIlluminationQuality 1, sg.ReflectionQuality 1, sg.PostProcessQuality 1, sg.EffectsQuality 1"
      "-LogCmds=LogTemp Verbose" -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ProveZombieDiversity.py

Answers the owner's playtest complaints ("all sound the same, walk backwards, no attack motion, common look",
"I saw 2-3 maybe?"). PIE on L_NYC_Survival at 1280x720, test input isolated (Vexa stands still at the survival
start), fixed 1/30 s step. The mode forces mortal, so Vexa's ZE survival pool is refilled every sample. Rounds 1-3
run; the intermission after rounds 1 and 2 is skipped through the vendor StartWave UFUNCTION. Because a still Vexa
kills nothing, the script culls the oldest zombies (alive >= 14 s, never mid-swing) with a traced head shot
(GameplayStatics.apply_point_damage on the head body, PC as instigator), and lands a 1-damage traced body shot every
3.5 s; that drives round progression and exercises the Hit/Headshot/Death blood and Pain/Death vocals.

Every 0.25 s of game time, for up to 150 s, every live AHoverNYCZombie is sampled: definition, mesh, skin material on
the definition's SkinMaterialSlot, location, velocity, forward, 2D distance to Vexa, montage playing, AttackSwings.
For a zombie moving faster than 80 cm/s the angle between its forward and its horizontal velocity is binned:
> 100 deg = backwards (the moonwalk), 60-100 deg = sideways. A swing (AttackSwings increase) counts as "with attack
montage" when a montage whose name contains "attack" is seen on that zombie within 1.6 s of the increase.

Stills (move the camera, wait 3 world ticks, capture: ReadPixels returns the previous frame): a group still every
12 s from behind-and-above Vexa, 6-10 m from the centroid of the 4-8 nearest zombies; 3 side close-ups of a zombie
mid-swing within 300 cm; 2 front close-ups of a sight roar. The view target returns to Vexa after each capture.

After PIE the -abslog (else Saved/Logs/AFS.log) is harvested for HOVER_ZOMBIE_VARIANT / VOICE / STEP / BLOOD /
ROAR / FACING_FIX. Receipt D:/AFS_Comparisons/ZombieDiversity_20261031/proof.json; prints PROVE_ZOMBIES_DONE
<summary json> and quits. Changes only the unsaved Play world.
"""
import json
import math
import os
import random
import re
import time
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path(os.environ.get('PROOF_OUT') or 'D:/AFS_Comparisons/ZombieDiversity_20261031')
OUT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT = 1280, 720
SAMPLE = 0.25            # game seconds between samples
WINDOW = 150.0           # game seconds of sampling
TIMEOUT = 2400           # wall seconds
MOVING = 80.0            # cm/s, horizontal speed above which facing is judged
BACKWARDS_DEG, SIDEWAYS_DEG = 100.0, 60.0
SWING_WINDOW = 1.6       # game seconds after an AttackSwings increase to see the attack montage
GROUP_FIRST, GROUP_EVERY = 8.0, 12.0
SWING_SHOTS, ROAR_SHOTS = 3, 2
CLOSE_RANGE = 300.0
LAST_SKIPPED_WAVE = 2    # skip the intermission after rounds 1 and 2 so round 3 starts promptly
CULL_EVERY, CULL_AGE, CULL_FORCE_AGE = 2.0, 14.0, 25.0
BODY_SHOT_EVERY = 3.5
RAND = random.Random(20261031)
# Review 2026-10-31: the player advances on zombies parked on the inner / queue ring (the case where facing the
# target while the slot steering retreats would moonwalk). From ADVANCE_FIRST, every ADVANCE_EVERY s, when at least
# one zombie ADVANCE_MIN_RING..ADVANCE_PICK cm out is nearly still, Vexa is moved toward the parked centroid at
# ADVANCE_SPEED for ADVANCE_TIME s (stopping ADVANCE_STOP cm from a zombie straight ahead); zombies within ADVANCE_RADIUS are judged until
# ADVANCE_MEASURE s after the start.
ADVANCE_FIRST, ADVANCE_EVERY = 30.0, 16.0
ADVANCE_PICK, ADVANCE_SPEED, ADVANCE_TIME, ADVANCE_STOP = 420.0, 170.0, 2.5, 90.0
ADVANCE_MIN_RING = 180.0   # parked zombies this far out (queue ring / outer inner ring) set the direction
ADVANCE_RADIUS, ADVANCE_MEASURE = 450.0, 4.5

R = {'ok': False, 'errors': [], 'api_errors': [], 'notes': [], 'setup': {}, 'rounds': [], 'round_skips': [],
     'kills': [], 'body_shots': [], 'refills': 0, 'player_hp_min': None, 'zombies': {}, 'definitions': {},
     'backwards_examples': [], 'samples': [], 'stills': [], 'log': {}, 'summary': {},
     'claim': 'Rendered PIE at 1280x720, fixed 1/30 s step, Vexa held alive and still; zombies culled by '
              'script head shots so rounds progress. Facing angle is forward vs horizontal velocity.'}
S = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'done': False, 'pc': None,
     't_first': None, 't0': None, 'next_sample': 0.0, 'cam': None, 'shot': None, 'last_t': None, 'ticks': 0,
     'logcmd': False, 'wave_key': None, 'state_since': None, 'next_group': None, 'next_cull': None,
     'next_body': None, 'swing_shots': 0, 'roar_shots': 0, 'last_close_t': -99.0, 'close_defs': [],
     'roar_seen': set(), 'pending_swings': {}, 'moving': 0, 'backwards': 0, 'sideways': 0,
     'moving_free': 0, 'backwards_free': 0, 'swings': 0, 'swings_attack': 0, 'attack_montage_samples': 0,
     'max_alive': 0, 'max_wave': 0, 'sample_n': 0}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.EditorAssetLibrary.does_asset_exist(MAP), 'L_NYC_Survival missing'
assert LEVEL.load_level(MAP), 'load_level failed'
ZCLASS = getattr(u, 'HoverNYCZombie', None) or getattr(u, 'HoverCyberZombie')


# ---------------------------------------------------------------- helpers
def save():
    (OUT / 'proof.json').write_text(json.dumps(R, indent=1, default=str))


def world():
    return u.HoverAuthoring.get_playtest_world()


def pawn():
    return S['pc'].get_controlled_pawn() if S['pc'] else None


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)] if v is not None else None


def prop(obj, *names):
    if obj is None:
        return None
    for n in names:
        try:
            return obj.get_editor_property(n)
        except Exception:  # noqa: BLE001
            pass
        try:
            return getattr(obj, n)
        except Exception:  # noqa: BLE001
            pass
    return None


def call(obj, name, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception:  # noqa: BLE001
        return None


def api_err(what, e):
    msg = '%s: %s' % (what, str(e)[:200])
    if msg not in R['api_errors'] and len(R['api_errors']) < 60:
        R['api_errors'].append(msg)


def enum_key(v):
    n = getattr(v, 'name', None) or str(v).split('.')[-1].split(':')[0]
    return n.strip('<> ').replace('_', '').lower()


def console(cmd):
    try:
        u.SystemLibrary.execute_console_command(world(), cmd)
        return True
    except Exception as e:  # noqa: BLE001
        api_err(cmd, e)
        return False


def obj_name(o):
    try:
        return o.get_name() if o else None
    except Exception:  # noqa: BLE001
        return None


def is_attack(m):
    return bool(m) and 'attack' in m.lower()


# ---------------------------------------------------------------- zombie reads
def zombie_alive(z):
    if prop(z, 'is_dead', 'b_is_dead'):
        return False
    sc = prop(z, 'survival_component')
    hp = call(sc, 'get_health') if sc else None
    return hp is None or hp > 0


def definition_of(z):
    return prop(z, 'zombie_data')


def skin_of(z, d):
    mesh = prop(z, 'mesh')
    if not mesh:
        return None, None
    sk = call(mesh, 'get_skeletal_mesh_asset') or prop(mesh, 'skeletal_mesh_asset', 'skeletal_mesh')
    idx = 0
    slot = prop(d, 'skin_material_slot') if d else None
    if slot is not None and str(slot) not in ('None', ''):
        i = call(mesh, 'get_material_index', slot)
        if isinstance(i, int) and i >= 0:
            idx = i
    mat = call(mesh, 'get_material', idx)
    return obj_name(sk), obj_name(mat)


def first_sight(z, d, t):
    mesh = prop(z, 'mesh')
    mesh_name, skin = skin_of(z, d)
    info = {'class': z.get_class().get_name(), 'definition': obj_name(d), 'first_t': round(t - S['t0'], 2),
            'last_t': None, 'mesh': mesh_name, 'skin': skin,
            'actor_scale': round(z.get_actor_scale3d().x, 3),
            'mesh_scale': round(mesh.get_editor_property('relative_scale3d').x, 3) if mesh else None,
            'anim_rate': prop(mesh, 'global_anim_rate_scale'), 'montages': [], 'swings': 0, 'samples': 0,
            'moving': 0, 'backwards': 0, 'min_d2': None, 'killed_by_script': None, 'dead_seen': False}
    return info


def definition_row(d):
    n = obj_name(d)
    row = R['definitions'].get(n)
    if row is None:
        roar = prop(d, 'sight_roar_montage')
        row = {'class': d.get_class().get_name() if d else None, 'zombies': 0, 'skins': [], 'meshes': [],
               'montages': [], 'moving': 0, 'backwards': 0, 'sideways': 0, 'swings': 0, 'swings_attack': 0,
               'sight_roar_montage': obj_name(roar),
               'skin_materials': [obj_name(m) for m in (prop(d, 'skin_materials') or [])],
               'attack_montages': [obj_name(m) if hasattr(m, 'get_name') else str(m)
                                   for m in (prop(d, 'attack_montages') or [])],
               'death_variants': [obj_name(m) for m in (prop(d, 'death_montage_variants') or [])],
               'voice_sets': {k: len(prop(d, k) or []) for k in ('idle_vocals', 'chase_vocals', 'attack_vocals',
                                                                   'pain_vocals', 'death_vocals', 'footstep_sounds')},
               'blood': {k: obj_name(prop(d, k)) for k in ('hit_blood', 'headshot_blood', 'death_blood')}}
        R['definitions'][n] = row
    return row


def add_unique(lst, v, cap=40):
    if v and v not in lst and len(lst) < cap:
        lst.append(v)


# ---------------------------------------------------------------- Vexa
def keep_vexa_alive(p):
    surv = None
    combat = prop(p, 'combat')
    if combat:
        surv = prop(combat, 'survival')
    if not surv:
        surv = call(p, 'get_component_by_class', u.ZE_SurvivalComponent)
    if not surv:
        api_err('keep_vexa_alive', 'no survival component')
        return None
    hp, mx = call(surv, 'get_health'), call(surv, 'get_max_health')
    if hp is not None:
        R['player_hp_min'] = hp if R['player_hp_min'] is None else min(R['player_hp_min'], hp)
    if hp is not None and mx and hp < mx:
        try:
            surv.set_health(mx)
            R['refills'] += 1
        except Exception as e:  # noqa: BLE001
            api_err('set_health', e)
    return hp


# ---------------------------------------------------------------- shooting (cull + blood/pain coverage)
def hit_info(hit):
    """(blocking, actor, bone, location) of a HitResult; break_hit_result first, properties as the fallback."""
    try:
        # UE 5.8 Python has no GameplayStatics.break_hit_result; HitResult.to_tuple() is the same layout
        # (blocking, initial_overlap, time, distance, location, impact_point, normal, impact_normal, phys_mat,
        # hit_actor, hit_component, hit_bone_name, bone_name, ...).
        tup = hit.to_tuple()
        actor = tup[9] if len(tup) > 9 and isinstance(tup[9], u.Actor) else None
        if actor is None:
            actor = next((x for x in tup if isinstance(x, u.Actor)), None)
        bone = str(tup[12]) if len(tup) > 12 else None
        return bool(tup[0]), actor, bone, tup[4]
    except Exception as e:  # noqa: BLE001
        api_err('hit_to_tuple', e)
    b = prop(hit, 'bone_name')
    bone = str(b) if b is not None else None
    return bool(prop(hit, 'blocking_hit')), prop(hit, 'hit_actor', 'actor'), bone, prop(hit, 'location', 'impact_point')


def trace(start, end, ignore, complex_=False):
    hit = u.SystemLibrary.line_trace_single(world(), start, end, u.TraceTypeQuery.TRACE_TYPE_QUERY1, complex_, ignore,
                                            u.DrawDebugTrace.NONE, True)
    if isinstance(hit, tuple):
        hit = next((x for x in hit if isinstance(x, u.HitResult)), None)
    return hit


def shoot(z, bone, damage):
    w, p, pc = world(), pawn(), S['pc']
    mesh = prop(z, 'mesh')
    target = call(mesh, 'get_socket_location', bone) if mesh else None
    if target is None:
        target = z.get_actor_location()
    src = p.get_actor_location() + u.Vector(0, 0, 60)
    d = target - src
    n = d.length() or 1.0
    dirv = u.Vector(d.x / n, d.y / n, d.z / n)
    start, end = target - dirv * 90.0, target + dirv * 40.0
    try:
        # Simple collision (physics asset bodies), as ZE_WeaponBase's ECC_Visibility trace; complex traces
        # do not hit skeletal meshes.
        hit = trace(start, end, [p], False)
        blocking, actor, hbone, _ = hit_info(hit) if hit else (False, None, None, None)
        if blocking and actor == z:
            u.GameplayStatics.apply_point_damage(z, damage, dirv, hit, pc, p, u.DamageType)
            return 'point:%s' % hbone
    except Exception as e:  # noqa: BLE001
        api_err('point_damage', e)
    u.GameplayStatics.apply_damage(z, damage, pc, p, u.DamageType)
    return 'radial_fallback'


def cull_and_shoot(w, gm, live, t):
    el = t - S['t0']
    if S['next_cull'] is None:
        S['next_cull'] = t + 10.0
        S['next_body'] = t + 6.0
    if t >= S['next_cull']:
        S['next_cull'] = t + CULL_EVERY
        quota, spawned = call(gm, 'get_round_quota'), call(gm, 'get_spawned_this_round')
        all_out = bool(quota) and spawned is not None and spawned >= quota
        cands = []
        for z, info, mname, d2 in live:
            age = el - info['first_t']
            if age >= CULL_AGE and not is_attack(mname) and z != (S['shot'] or {}).get('subject'):
                cands.append((age, z, info, d2))
        cands.sort(key=lambda c: -c[0])
        if cands:
            age, z, info, d2 = cands[0]
            if len(live) >= 5 or age >= CULL_FORCE_AGE or all_out:
                sc = prop(z, 'survival_component')
                hp = call(sc, 'get_health') or 100.0
                how = shoot(z, 'head', hp + 250.0)
                info['killed_by_script'] = round(el, 2)
                R['kills'].append({'t': round(el, 2), 'zombie': z.get_name(), 'definition': info['definition'],
                                   'age': round(age, 1), 'how': how, 'alive': len(live), 'quota': quota,
                                   'spawned': spawned})
                # Integration 2026-10-31: two blood close-ups (headshot burst + ground splash) 3 ticks after a
                # traced kill, from a clear bearing 260 cm off the head.
                if how.startswith('point') and not S['shot'] and S.get('blood_shots', 0) < 2:
                    zl, pl = z.get_actor_location(), pawn().get_actor_location()
                    base = math.atan2(pl.y - zl.y, pl.x - zl.x) + math.pi / 2
                    cands = [u.Vector(zl.x + math.cos(base + o) * 260, zl.y + math.sin(base + o) * 260, zl.z + 60)
                             for o in (0.0, math.pi, 0.6, -0.6, math.pi + 0.6, math.pi - 0.6)]
                    cam, _ = clear_pose(cands, [(zl + u.Vector(0, 0, 40), z)], [pawn()])
                    begin_shot('blood', 'blood_%d_%s' % (S.get('blood_shots', 0), info['definition']), cam,
                               zl + u.Vector(0, 0, 20), {'t': round(el, 2), 'definition': info['definition'],
                                                         'how': how, 'zombie': z.get_name()})
                    S['blood_shots'] = S.get('blood_shots', 0) + 1
    if t >= S['next_body']:
        S['next_body'] = t + BODY_SHOT_EVERY
        pool = [(z, info) for z, info, mname, d2 in live if d2 > CLOSE_RANGE + 50 and not is_attack(mname)]
        if pool:
            z, info = RAND.choice(pool)
            how = shoot(z, 'spine_03', 1.0)
            R['body_shots'].append({'t': round(el, 2), 'zombie': z.get_name(), 'definition': info['definition'],
                                    'how': how})


# ---------------------------------------------------------------- rounds
def manage_rounds(gm, t):
    wave, state = call(gm, 'get_current_wave'), call(gm, 'get_wave_state')
    sk = enum_key(state) if state is not None else None
    key = (wave, sk)
    if key != S['wave_key']:
        S['wave_key'] = key
        S['state_since'] = t
        R['rounds'].append({'t': round(t - S['t0'], 2), 'wave': wave, 'state': sk,
                            'quota': call(gm, 'get_round_quota'),
                            'kind': str(call(gm, 'get_round_kind', wave or 0))})
        if sk == 'gameover':
            R['errors'].append('game over at t=%.1f' % (t - S['t0']))
    S['max_wave'] = max(S['max_wave'], wave or 0)
    since = t - (S['state_since'] or t)
    skip = (sk == 'wavecompleted' and (wave or 0) <= LAST_SKIPPED_WAVE and since >= 3.0) or \
           (sk == 'waitingtostart' and since >= 10.0)
    if skip and not any(s['wave'] == wave and s['state'] == sk for s in R['round_skips']):
        try:
            gm.start_wave()
            R['round_skips'].append({'t': round(t - S['t0'], 2), 'wave': wave, 'state': sk})
        except Exception as e:  # noqa: BLE001
            api_err('start_wave', e)
    return wave, sk


# ---------------------------------------------------------------- stills
def unoccluded(target, cam, ignore):
    """Pull the camera in front of any wall between it and the target."""
    try:
        hit = trace(target, cam, ignore)
        blocking, _, _, loc = hit_info(hit) if hit else (False, None, None, None)
        if blocking:
            if loc is not None:
                d = target - loc
                n = d.length() or 1.0
                return loc + u.Vector(d.x / n, d.y / n, d.z / n) * 40.0
    except Exception as e:  # noqa: BLE001
        api_err('occlusion_trace', e)
    return cam


def clear_pose(cands, targets, ignore):
    """(camera, all_clear): the first candidate with an unblocked line to every target point, else the one
    seeing the most. Review 2026-10-31: callers only run unoccluded() when all_clear is False, because the
    pull-in after a clear pose dragged the camera into the parked truck."""
    best = None
    for cand in cands:
        seen = 0
        for pt, actor_ok in targets:
            hit = trace(cand, pt, ignore)
            blocking, actor, _, _ = hit_info(hit) if hit else (False, None, None, None)
            if not blocking or (actor_ok is not None and actor == actor_ok):
                seen += 1
        if seen == len(targets):
            return cand, True
        if best is None or seen > best[0]:
            best = (seen, cand)
    return best[1], False


def begin_shot(kind, name, cam_loc, look_at, meta, subject=None):
    rot = u.MathLibrary.find_look_at_rotation(cam_loc, look_at)
    S['cam'].set_actor_location_and_rotation(cam_loc, rot, False, False)
    S['pc'].set_view_target_with_blend(S['cam'], 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)
    S['shot'] = {'kind': kind, 'file': OUT / (name + '.png'), 'loc': cam_loc, 'rot': rot, 'ticks': 0,
                 'meta': meta, 'subject': subject}


def shot_tick():
    sh = S['shot']
    if not sh:
        return
    S['cam'].set_actor_location_and_rotation(sh['loc'], sh['rot'], False, False)
    sh['ticks'] += 1
    # ReadPixels returns the frame already rendered: capture after the camera pose has been drawn.
    if sh['ticks'] >= 3:
        try:
            u.HoverAuthoring.capture_world_frame(str(sh['file']))
            meta = dict(sh['meta'], kind=sh['kind'], file=sh['file'].name, cam=vec(sh['loc']))
            R['stills'].append(meta)
        except Exception as e:  # noqa: BLE001
            R['errors'].append('capture %s: %s' % (sh['file'].name, e))
        S['shot'] = None
        p = pawn()
        if p:
            S['pc'].set_view_target_with_blend(p, 0.0, u.ViewTargetBlendFunction.VT_BLEND_LINEAR, 0.0, False)


def try_group_still(live, t):
    p = pawn()
    if not live:
        S['next_group'] = t + 2.0
        return
    pl = p.get_actor_location()
    near = sorted(live, key=lambda r: r[3])[:8]
    cx = sum(z.get_actor_location().x for z, _, _, _ in near) / len(near)
    cy = sum(z.get_actor_location().y for z, _, _, _ in near) / len(near)
    cz = sum(z.get_actor_location().z for z, _, _, _ in near) / len(near)
    c = u.Vector(cx, cy, cz)
    dx, dy = pl.x - cx, pl.y - cy
    dist = math.hypot(dx, dy)
    if dist < 1.0:
        f = p.get_actor_forward_vector()
        dx, dy, dist = -f.x, -f.y, 1.0
    ux, uy = dx / dist, dy / dist
    # Integration 2026-10-31: the single behind-Vexa pose was often walled off by the parked truck. Try 12
    # bearings around the group (Vexa's side first) at 6.5 m and 2.2 m up, and keep the pose that sees the
    # most framed zombies' chests without a blocking hit (Vexa and the zombies themselves ignored).
    ignore = [p]
    base = math.atan2(uy, ux)
    best = None
    for k in range(12):
        a = base + (k // 2 + (k % 2)) * (math.pi / 6.0) * (1 if k % 2 else -1)
        cand = u.Vector(cx + math.cos(a) * 650.0, cy + math.sin(a) * 650.0, cz + 220.0)
        seen = 0
        for z, _, _, _ in near:
            chest = z.get_actor_location() + u.Vector(0, 0, 40)
            hit = trace(cand, chest, ignore)
            blocking, actor, _, _ = hit_info(hit) if hit else (False, None, None, None)
            if not blocking or actor == z:
                seen += 1
        if best is None or seen > best[0]:
            best = (seen, cand)
        if seen == len(near):
            break
    cam = best[1] if best[0] == len(near) else unoccluded(c + u.Vector(0, 0, 100), best[1],
                                                          [z for z, _, _, _ in near] + [p])
    n = len(R['stills'])
    begin_shot('group', 'group_%02d_t%03d' % (n, int(t - S['t0'])), cam, c + u.Vector(0, 0, 40),
               {'t': round(t - S['t0'], 2), 'alive': len(live), 'framed': len(near),
                'group_distance_cm': round(math.hypot(cam.x - cx, cam.y - cy), 0), 'clear_lines': best[0],
                'framed_definitions': sorted({i['definition'] for _, i, _, _ in near if i['definition']}),
                'framed_skins': sorted({i['skin'] for _, i, _, _ in near if i['skin']})})
    S['next_group'] = t + GROUP_EVERY


def try_close_ups(live, t):
    p = pawn()
    pl = p.get_actor_location()
    el = t - S['t0']
    if el - S['last_close_t'] < 2.5:
        return False
    if S['roar_shots'] < ROAR_SHOTS:
        for z, info, mname, d2 in live:
            row = R['definitions'].get(info['definition'], {})
            roar = row.get('sight_roar_montage')
            if mname and ('roar' in mname.lower() or (roar and mname == roar)) and z.get_name() not in S['roar_seen']:
                S['roar_seen'].add(z.get_name())
                zl, f = z.get_actor_location(), z.get_actor_forward_vector()
                fa = math.atan2(f.y, f.x)
                cands = [u.Vector(zl.x + math.cos(fa + o) * 320, zl.y + math.sin(fa + o) * 320, zl.z + 40)
                         for o in (0.0, 0.5, -0.5, 1.0, -1.0)]
                cam, clear = clear_pose(cands, [(zl + u.Vector(0, 0, 50), z)], [p])
                if not clear:
                    cam = unoccluded(zl + u.Vector(0, 0, 50), cam, [z, p])
                begin_shot('roar', 'roar_%d_%s' % (S['roar_shots'], info['definition']), cam, zl + u.Vector(0, 0, 50),
                           {'t': round(el, 2), 'definition': info['definition'], 'montage': mname,
                            'skin': info['skin'], 'zombie': z.get_name()}, z)
                S['roar_shots'] += 1
                S['last_close_t'] = el
                return True
    if S['swing_shots'] < SWING_SHOTS:
        cands = [(z, info, mname, d2) for z, info, mname, d2 in live if is_attack(mname) and d2 <= CLOSE_RANGE]
        # Prefer a definition not yet close-upped.
        cands.sort(key=lambda r: (r[1]['definition'] in S['close_defs'], r[3]))
        if cands:
            z, info, mname, d2 = cands[0]
            zl = z.get_actor_location()
            mx, my, mz = (zl.x + pl.x) / 2, (zl.y + pl.y) / 2, (zl.z + pl.z) / 2
            dx, dy = zl.x - pl.x, zl.y - pl.y
            n = math.hypot(dx, dy) or 1.0
            px, py = -dy / n, dx / n
            m = u.Vector(mx, my, mz)
            la = math.atan2(py, px)
            cands = [u.Vector(mx + math.cos(la + o) * 290, my + math.sin(la + o) * 290, mz + 40)
                     for o in (0.0, math.pi, 0.5, -0.5, math.pi + 0.5, math.pi - 0.5)]
            cam, clear = clear_pose(cands, [(zl + u.Vector(0, 0, 40), z), (pl + u.Vector(0, 0, 40), p)], [])
            if not clear:
                cam = unoccluded(m + u.Vector(0, 0, 20), cam, [z, p])
            begin_shot('swing', 'swing_%d_%s' % (S['swing_shots'], info['definition']), cam, m + u.Vector(0, 0, 10),
                       {'t': round(el, 2), 'definition': info['definition'], 'montage': mname,
                        'distance_cm': round(d2, 0), 'skin': info['skin'], 'zombie': z.get_name()}, z)
            S['swing_shots'] += 1
            S['close_defs'].append(info['definition'])
            S['last_close_t'] = el
            return True
    return False


# ---------------------------------------------------------------- player advance (review 2026-10-31)
def advance_tick(p, t):
    el = t - S['t0']
    adv = S.get('adv')
    if adv:
        if t <= adv['move_until']:
            pl = p.get_actor_location()
            near = 9e9
            for z, _ in S.get('last_live', []):
                try:
                    if zombie_alive(z):
                        zl = z.get_actor_location()
                        dd = math.hypot(zl.x - pl.x, zl.y - pl.y)
                        # Only a zombie straight ahead (within 30 deg of the advance) stops Vexa; the inner-ring
                        # zombies beside her must not cancel the advance.
                        ahead = dd > 1.0 and ((zl.x - pl.x) * adv['dir'][0] + (zl.y - pl.y) * adv['dir'][1]) / dd > 0.866
                        if ahead:
                            near = min(near, dd)
                except Exception:  # noqa: BLE001  (destroyed since the last sample)
                    pass
            if near > ADVANCE_STOP:
                step = ADVANCE_SPEED * max(0.0, min(0.1, t - adv['last_t']))
                try:
                    # No sweep: the first run's swept moves were blocked and Vexa barely moved. The stop distance
                    # keeps her out of the zombies; the character movement depenetrates any small overlap.
                    p.set_actor_location(pl + u.Vector(adv['dir'][0] * step, adv['dir'][1] * step, 0.0), False, True)
                except Exception as e:  # noqa: BLE001
                    api_err('advance_move', e)
                after = p.get_actor_location()
                adv['row']['moved_cm'] = round(adv['row']['moved_cm'] + math.hypot(after.x - pl.x, after.y - pl.y), 1)
        adv['last_t'] = t
        if t > adv['measure_until']:
            end = p.get_actor_location()
            adv['row']['to'] = vec(end)
            adv['row']['net_cm'] = round(math.hypot(end.x - adv['row']['from'][0], end.y - adv['row']['from'][1]), 1)
            S['adv'] = None
        return
    if el < S.get('next_adv', ADVANCE_FIRST) or S['shot']:
        return
    pl = p.get_actor_location()
    parked = []
    for z, d2 in S.get('last_live', []):
        try:
            if not zombie_alive(z) or d2 > ADVANCE_PICK or d2 < ADVANCE_MIN_RING:
                continue
            v = z.get_velocity()
            if math.hypot(v.x, v.y) < 60.0:
                parked.append((z, z.get_actor_location()))
        except Exception:  # noqa: BLE001
            continue
    if not parked:
        return
    cx = sum(zl.x for _, zl in parked) / len(parked)
    cy = sum(zl.y for _, zl in parked) / len(parked)
    dx, dy = cx - pl.x, cy - pl.y
    n = math.hypot(dx, dy)
    if n < 1.0:
        return
    row = {'t': round(el, 2), 'parked': len(parked), 'from': vec(pl), 'moved_cm': 0.0, 'zombie_samples': 0,
           'moving': 0, 'backwards': 0, 'sideways': 0, 'moving_away': 0, 'visual_n': 0, 'visual_backwards': 0,
           'visual_sideways': 0, 'visual_angles': []}
    R.setdefault('advances', []).append(row)
    S['adv'] = {'dir': (dx / n, dy / n), 'move_until': t + ADVANCE_TIME, 'measure_until': t + ADVANCE_MEASURE,
                'last_t': t, 'row': row}
    S['next_adv'] = el + ADVANCE_EVERY


# ---------------------------------------------------------------- sampling
def finalize_swings(name, force=False, t=None):
    keep = []
    for pend in S['pending_swings'].get(name, []):
        if force or t is None or t > pend['until']:
            S['swings'] += pend['n']
            S['swings_attack'] += pend['n'] if pend['seen'] else 0
            row = R['definitions'].get(pend['definition'])
            if row:
                row['swings'] += pend['n']
                row['swings_attack'] += pend['n'] if pend['seen'] else 0
        else:
            keep.append(pend)
    S['pending_swings'][name] = keep


def body_check(z, info, drow, fwd, zl, mname, sp):
    mesh = prop(z, 'mesh')
    if not mesh:
        return None
    try:
        pts = {b: mesh.get_socket_location(b) for b in ('foot_l', 'ball_l', 'foot_r', 'ball_r')}
        vx = (pts['ball_l'].x - pts['foot_l'].x) + (pts['ball_r'].x - pts['foot_r'].x)
        vy = (pts['ball_l'].y - pts['foot_l'].y) + (pts['ball_r'].y - pts['foot_r'].y)
        vn, fn = math.hypot(vx, vy), math.hypot(fwd.x, fwd.y)
        cap = z.get_component_by_class(u.CapsuleComponent)
        half = cap.get_scaled_capsule_half_height() if cap else 0.0
        gap = min(pts['foot_l'].z, pts['foot_r'].z) - (zl.z - half)
    except Exception as e:  # noqa: BLE001
        api_err('body_check', e)
        return None
    vis = drow.setdefault('visual', {'n': 0, 'backwards': 0, 'sideways': 0, 'angles': [], 'gaps': []})
    # Facing is judged while walking/running only: idle and attack stances turn the feet on purpose.
    if vn > 1.0 and fn > 0.1 and not mname and sp > MOVING:
        c = max(-1.0, min(1.0, (vx * fwd.x + vy * fwd.y) / (vn * fn)))
        a = math.degrees(math.acos(c))
        vis['n'] += 1
        S['visual_n'] = S.get('visual_n', 0) + 1
        if a > BACKWARDS_DEG:
            vis['backwards'] += 1
            S['visual_backwards'] = S.get('visual_backwards', 0) + 1
        elif a >= SIDEWAYS_DEG:
            vis['sideways'] += 1
            S['visual_sideways'] = S.get('visual_sideways', 0) + 1
        if len(vis['angles']) < 400:
            vis['angles'].append(round(a, 0))
    else:
        a = None
    if len(vis['gaps']) < 400:
        vis['gaps'].append(round(gap, 1))
    return a


def sample(w, gm, p, t):
    el = t - S['t0']
    S['sample_n'] += 1
    keep_vexa_alive(p)
    wave, state = manage_rounds(gm, t)
    pl = p.get_actor_location()
    live = []
    rows = []
    present = set()
    for z in u.GameplayStatics.get_all_actors_of_class(w, ZCLASS):
        name = z.get_name()
        present.add(name)
        d = definition_of(z)
        info = R['zombies'].get(name)
        if info is None:
            info = first_sight(z, d, t)
            R['zombies'][name] = info
            drow = definition_row(d)
            drow['zombies'] += 1
            add_unique(drow['meshes'], info['mesh'])
            add_unique(drow['skins'], info['skin'])
        elif info['samples'] == 4:
            # Runtime variety may be applied a frame after spawn: re-read the skin once.
            _, skin = skin_of(z, d)
            if skin and skin != info['skin']:
                info['skin'] = skin
                add_unique(R['definitions'][info['definition']]['skins'], skin)
        drow = R['definitions'][info['definition']]
        info['last_t'] = round(el, 2)
        mont = call(z, 'get_current_montage')
        mname = obj_name(mont)
        if mname:
            add_unique(info['montages'], mname, 20)
            add_unique(drow['montages'], mname, 60)
        alive = zombie_alive(z)
        if not alive:
            info['dead_seen'] = True
            finalize_swings(name, force=True)
            continue
        info['samples'] += 1
        zl, vel, fwd = z.get_actor_location(), z.get_velocity(), z.get_actor_forward_vector()
        d2 = math.hypot(zl.x - pl.x, zl.y - pl.y)
        info['min_d2'] = round(d2, 1) if info['min_d2'] is None else round(min(info['min_d2'], d2), 1)
        sp = math.hypot(vel.x, vel.y)
        ang = None
        if sp > MOVING:
            fn = math.hypot(fwd.x, fwd.y) or 1.0
            c = max(-1.0, min(1.0, (fwd.x * vel.x + fwd.y * vel.y) / (fn * sp)))
            ang = math.degrees(math.acos(c))
            S['moving'] += 1
            info['moving'] += 1
            drow['moving'] += 1
            if not mname:
                S['moving_free'] += 1
            if ang > BACKWARDS_DEG:
                S['backwards'] += 1
                info['backwards'] += 1
                drow['backwards'] += 1
                if not mname:
                    S['backwards_free'] += 1
                if len(R['backwards_examples']) < 25:
                    R['backwards_examples'].append({'t': round(el, 2), 'zombie': name, 'definition': info['definition'],
                                                    'angle': round(ang, 1), 'speed': round(sp, 1), 'montage': mname,
                                                    'd2': round(d2, 1), 'yaw': round(z.get_actor_rotation().yaw, 1),
                                                    'vel': vec(vel)})
            elif ang >= SIDEWAYS_DEG:
                S['sideways'] += 1
                drow['sideways'] += 1
        # Integration 2026-10-31: the actor-forward test above cannot see a mesh that is turned on its capsule.
        # Visual facing = the horizontal foot->ball direction of both feet (toes point where the body faces);
        # grounding = lowest foot bone above the capsule bottom (negative = sunk, large = floating).
        adv = S.get('adv')
        in_adv = bool(adv) and t <= adv['measure_until'] and d2 <= ADVANCE_RADIUS
        vis_ang = None
        if info['samples'] % 2 == 1 or in_adv:
            vis_ang = body_check(z, info, drow, fwd, zl, mname, sp)
        if in_adv:
            A = adv['row']
            A['zombie_samples'] += 1
            if sp > MOVING and ang is not None:
                A['moving'] += 1
                A['backwards'] += 1 if ang > BACKWARDS_DEG else 0
                A['sideways'] += 1 if SIDEWAYS_DEG <= ang <= BACKWARDS_DEG else 0
                # Moving away from Vexa while her advance pushes the ring back is the case under test.
                away = ((zl.x - pl.x) * vel.x + (zl.y - pl.y) * vel.y) / ((d2 or 1.0) * sp)
                A['moving_away'] += 1 if away > 0.3 else 0
            if vis_ang is not None:
                A['visual_n'] += 1
                A['visual_backwards'] += 1 if vis_ang > BACKWARDS_DEG else 0
                A['visual_sideways'] += 1 if SIDEWAYS_DEG <= vis_ang <= BACKWARDS_DEG else 0
                if len(A['visual_angles']) < 200:
                    A['visual_angles'].append(round(vis_ang, 0))
        if is_attack(mname):
            S['attack_montage_samples'] += 1
        swings = prop(z, 'attack_swings')
        if isinstance(swings, int):
            last = info.get('_last_swings', 0)
            if swings > last:
                S['pending_swings'].setdefault(name, []).append(
                    {'until': t + SWING_WINDOW, 'n': swings - last, 'seen': is_attack(mname),
                     'definition': info['definition']})
                info['swings'] += swings - last
            info['_last_swings'] = swings
            for pend in S['pending_swings'].get(name, []):
                if is_attack(mname):
                    pend['seen'] = True
            finalize_swings(name, t=t)
        live.append((z, info, mname, d2))
        rows.append({'z': name, 'def': info['definition'], 'loc': vec(zl), 'spd': round(sp, 0),
                     'fwd': [round(fwd.x, 2), round(fwd.y, 2)], 'ang': round(ang, 0) if ang is not None else None,
                     'd2': round(d2, 0), 'mont': mname, 'swings': swings})
    for name in list(S['pending_swings']):
        if name not in present:
            finalize_swings(name, force=True)
    S['max_alive'] = max(S['max_alive'], len(live))
    S['last_live'] = [(z, d2) for z, _, _, d2 in live]
    if S['sample_n'] % 4 == 1:   # 1 Hz rows in the receipt
        R['samples'].append({'t': round(el, 2), 'wave': wave, 'state': state, 'alive': len(live),
                             'vexa': vec(pl), 'zombies': rows})
    if S['sample_n'] % 40 == 0:
        save()
    return live


# ---------------------------------------------------------------- log harvest + summary
def harvest_log():
    path = None
    try:
        m = re.search(r'-abslog="?([^"\s]+)', u.SystemLibrary.get_command_line())
        path = m.group(1) if m else None
    except Exception:  # noqa: BLE001
        pass
    if not path:
        path = str(Path(u.Paths.project_log_dir()) / 'AFS.log')
    L = R['log']
    L['path'] = path
    if not Path(path).exists():
        R['errors'].append('log not found: ' + path)
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    variants, voices, steps, blood, roars = [], [], {}, {}, []
    rv = re.compile(r'HOVER_ZOMBIE_VARIANT (\S+) scale=([-\d.]+) rate=([-\d.]+) skin=(\S+) morphs=(\d+)')
    rvo = re.compile(r'HOVER_ZOMBIE_VOICE (\w+) (\S+) (\S+) active=(\d+)')
    rb = re.compile(r'HOVER_ZOMBIE_BLOOD (\w+) (\S+)')
    rr = re.compile(r'HOVER_ZOMBIE_ROAR (\S+)')
    rs = re.compile(r'HOVER_ZOMBIE_STEP (\S+)')
    log_errors = []
    for l in lines:
        if 'HOVER_ZOMBIE_' in l:
            m = rv.search(l)
            if m:
                variants.append({'definition': m.group(1), 'scale': float(m.group(2)), 'rate': float(m.group(3)),
                                 'skin': m.group(4), 'morphs': int(m.group(5))})
                continue
            m = rvo.search(l)
            if m:
                voices.append((m.group(1), m.group(2), m.group(3), int(m.group(4))))
                continue
            m = rs.search(l)
            if m:
                steps[m.group(1)] = steps.get(m.group(1), 0) + 1
                continue
            m = rb.search(l)
            if m:
                blood.setdefault(m.group(1), {}).setdefault(m.group(2), 0)
                blood[m.group(1)][m.group(2)] += 1
                continue
            m = rr.search(l)
            if m:
                roars.append(m.group(1))
                continue
        if ('Error:' in l or ': Error' in l) and 'LogPython' not in l and \
                any(k in l for k in ('Zombie', 'ZOMBIE', 'Montage', 'ZE_', 'Niagara', 'Skeleton', 'Sound', 'Anim')):
            log_errors.append(l[-240:])
    L['variants'] = variants[:200]
    L['voice_lines'] = len(voices)
    L['voice_by_kind'] = {}
    L['voice_sounds_by_kind'] = {}
    L['voice_by_definition'] = {}
    for kind, snd, dn, act in voices:
        L['voice_by_kind'][kind] = L['voice_by_kind'].get(kind, 0) + 1
        L['voice_sounds_by_kind'].setdefault(kind, set()).add(snd)
        L['voice_by_definition'][dn] = L['voice_by_definition'].get(dn, 0) + 1
    L['voice_sounds_by_kind'] = {k: sorted(v) for k, v in L['voice_sounds_by_kind'].items()}
    L['max_active_voices'] = max([v[3] for v in voices] or [0])
    L['voice_samples'] = [' '.join(map(str, v)) for v in voices[:12]]
    L['steps_by_definition'] = steps
    L['footsteps'] = sum(steps.values())
    L['blood'] = blood
    L['roars'] = roars
    L['facing_fix'] = [l[-220:] for l in lines if 'HOVER_ZOMBIE_FACING_FIX' in l][:3]
    yaw = {}
    for l in lines:
        m = re.search(r'HOVER_ZOMBIE_MESH_YAW (\S+) mesh=\S+ applied=([-\d.]+)', l)
        if m:
            yaw.setdefault(m.group(1), set()).add(float(m.group(2)))
    L['mesh_yaw_by_definition'] = {k: sorted(v) for k, v in yaw.items()}
    L['mesh_yaw_live_lines'] = len([l for l in lines if 'HOVER_ZOMBIE_MESH_YAW_LIVE' in l])
    L['roar_cuts'] = len([l for l in lines if 'HOVER_ZOMBIE_ROAR_CUT' in l])
    L['spawn_leaks'] = len([l for l in lines if 'HOVER_SPAWN_LEAK' in l])
    L['vendor_no_montage_warnings'] = len([l for l in lines if 'no cached attack montages' in l])
    L['log_errors'] = log_errors[:30]
    L['log_error_count'] = len(log_errors)


def med(xs):
    xs = sorted(x for x in (xs or []) if x is not None)
    return xs[len(xs) // 2] if xs else None


def summarise():
    L = R['log']
    for name in list(S['pending_swings']):
        finalize_swings(name, force=True)
    defs = sorted(d for d in R['definitions'] if d)
    sampled_skins = {z['skin'] for z in R['zombies'].values() if z['skin']}
    logged_skins = {v['skin'] for v in L.get('variants', []) if v['skin'] not in ('None', '')}
    skins = sorted(sampled_skins | logged_skins)
    looks = sorted({'%s|%s' % (z['mesh'], z['skin']) for z in R['zombies'].values()})
    mv = S['moving']
    blood = L.get('blood', {})
    errors = R['errors'] + ['log: ' + e for e in L.get('log_errors', [])]
    s = {
        'distinct_definitions_seen': len(defs), 'definitions_seen': defs,
        'zombies_by_definition': {d: R['definitions'][d]['zombies'] for d in defs},
        'definitions_logged': sorted({v['definition'] for v in L.get('variants', [])}),
        'distinct_skins_seen': len(skins), 'skins_seen': skins, 'distinct_mesh_skin_looks': len(looks),
        'zombies_seen': len(R['zombies']), 'max_alive': S['max_alive'], 'max_wave': S['max_wave'],
        'moving_samples': mv,
        'backwards_fraction': round(S['backwards'] / mv, 4) if mv else None,
        'sideways_fraction': round(S['sideways'] / mv, 4) if mv else None,
        'backwards_fraction_no_montage': round(S['backwards_free'] / S['moving_free'], 4) if S['moving_free'] else None,
        'attack_swings': S['swings'], 'swings_with_attack_montage': S['swings_attack'],
        'attack_montage_samples': S['attack_montage_samples'],
        'attack_montages_seen': sorted({m for d in defs for m in R['definitions'][d]['montages'] if is_attack(m)}),
        'all_montages_seen': sorted({m for d in defs for m in R['definitions'][d]['montages']}),
        'voice_lines': L.get('voice_lines', 0), 'voice_by_kind': L.get('voice_by_kind', {}),
        'distinct_voice_sounds': len({s for v in L.get('voice_sounds_by_kind', {}).values() for s in v}),
        'max_active_voices': L.get('max_active_voices', 0),
        'footsteps': L.get('footsteps', 0),
        'blood_by_kind': {k: sum(v.values()) for k, v in blood.items()},
        'roars': len(L.get('roars', [])), 'roar_stills': S['roar_shots'],
        'variants_logged': len(L.get('variants', [])),
        'variant_scale_range': [min([v['scale'] for v in L.get('variants', [])] or [0]),
                                max([v['scale'] for v in L.get('variants', [])] or [0])],
        'variant_rate_range': [min([v['rate'] for v in L.get('variants', [])] or [0]),
                               max([v['rate'] for v in L.get('variants', [])] or [0])],
        'facing_fix_logged': bool(L.get('facing_fix')),
        'script_kills': len(R['kills']), 'body_shots': len(R['body_shots']), 'vexa_refills': R['refills'],
        'vexa_hp_min': R['player_hp_min'], 'round_skips': len(R['round_skips']),
        'mesh_visual_samples': S.get('visual_n', 0),
        'mesh_visual_backwards_fraction': round(S.get('visual_backwards', 0) / S['visual_n'], 4) if S.get('visual_n') else None,
        'mesh_visual_sideways_fraction': round(S.get('visual_sideways', 0) / S['visual_n'], 4) if S.get('visual_n') else None,
        'mesh_visual_by_definition': {d: {'n': R['definitions'][d].get('visual', {}).get('n', 0),
                                          'backwards': R['definitions'][d].get('visual', {}).get('backwards', 0),
                                          'median_deg': med(R['definitions'][d].get('visual', {}).get('angles')),
                                          'foot_gap_cm_median': med(R['definitions'][d].get('visual', {}).get('gaps')),
                                          'foot_gap_cm_min': min(R['definitions'][d].get('visual', {}).get('gaps') or [None], key=lambda x: x if x is not None else 0)}
                                      for d in defs},
        'errors': len(errors), 'api_errors': len(R['api_errors']),
        'stills': [x['file'] for x in R['stills']],
        'mesh_yaw_by_definition': L.get('mesh_yaw_by_definition', {}),
        'mesh_yaw_live_lines': L.get('mesh_yaw_live_lines', 0), 'roar_cuts': L.get('roar_cuts', 0),
    }
    adv = R.get('advances', [])
    am = sum(a['moving'] for a in adv)
    av = sum(a['visual_n'] for a in adv)
    s['advance'] = {'runs': len(adv), 'moved_cm': [a['moved_cm'] for a in adv],
                    'zombie_samples': sum(a['zombie_samples'] for a in adv), 'moving_samples': am,
                    'moving_away_samples': sum(a['moving_away'] for a in adv),
                    'backwards_fraction': round(sum(a['backwards'] for a in adv) / am, 4) if am else None,
                    'sideways_fraction': round(sum(a['sideways'] for a in adv) / am, 4) if am else None,
                    'visual_samples': av,
                    'visual_backwards_fraction': round(sum(a['visual_backwards'] for a in adv) / av, 4) if av else None,
                    'visual_sideways_fraction': round(sum(a['visual_sideways'] for a in adv) / av, 4) if av else None,
                    'visual_median_deg': med([x for a in adv for x in a['visual_angles']])}
    R['summary'] = s
    R['errors_all'] = errors
    R['ok'] = s['distinct_definitions_seen'] >= 8 and s['backwards_fraction'] is not None and \
        s['backwards_fraction'] < 0.03 and s['swings_with_attack_montage'] > 0 and s['voice_lines'] > 0 and not errors         and s['mesh_visual_backwards_fraction'] is not None and s['mesh_visual_backwards_fraction'] < 0.05         and all((v['median_deg'] or 0) < 45 for v in s['mesh_visual_by_definition'].values())
    # Review 2026-10-31: the advance case must have run and must not moonwalk either.
    A = s['advance']
    s['ok_advance'] = A['runs'] > 0 and (A['backwards_fraction'] or 0) < 0.05 and \
        (A['visual_backwards_fraction'] or 0) < 0.05
    R['ok'] = R['ok'] and s['ok_advance']
    s['ok'] = R['ok']


# ---------------------------------------------------------------- driver
def finish():
    if S['end']:
        return
    save()
    LEVEL.editor_request_end_play()
    S['end'] = time.monotonic()


def setup(w, pc, p, t):
    for cmd in ('Log LogTemp Verbose', 'r.MotionBlurQuality 0', 'DisableAllScreenMessages'):
        console(cmd)
    u.HoverAuthoring.isolate_test_input(pc)
    u.HoverAuthoring.set_playtest_fixed_step(True)
    S['cam'] = u.HoverAuthoring.spawn_playtest_actor(
        u.CameraActor, u.Transform(location=p.get_actor_location() + u.Vector(0, 0, 500), rotation=u.Rotator()))
    gm = u.GameplayStatics.get_game_mode(w)
    R['setup'] = {'mode': gm.get_class().get_name() if gm else None, 'pawn': p.get_class().get_name(),
                  'start': vec(p.get_actor_location()), 'zombie_class': ZCLASS.__name__,
                  'max_hp': call(p, 'get_max_health'), 'nyc_settings': obj_name(call(gm, 'get_nyc_settings'))}
    nyc = call(gm, 'get_nyc_settings')
    if nyc:
        R['setup']['roster'] = {'standards': [obj_name(x) for x in (prop(nyc, 'standards') or [])],
                                'brute': obj_name(prop(nyc, 'brute')), 'kid': obj_name(prop(nyc, 'kid'))}
    S['t0'] = t
    S['next_sample'] = t
    S['next_group'] = t + GROUP_FIRST
    save()


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
                    print('PROVE_ZOMBIES_DONE', json.dumps(R['summary'], default=str), flush=True)
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
                    api_err('configure_offscreen_display', e)
                u.HoverAuthoring.start_playtest(WIDTH, HEIGHT + 32)
                S['play'] = True
            return
        w = world()
        if not w:
            return
        if not S['logcmd']:
            S['logcmd'] = True
            console('Log LogTemp Verbose')   # as early as possible so spawn-time Verbose lines are kept
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        p = pc.get_controlled_pawn()
        t = u.GameplayStatics.get_time_seconds(w)
        if S['pc'] is None:
            S['pc'] = pc
            S['t_first'] = t
            u.HoverAuthoring.isolate_test_input(pc)
            return
        if S['t0'] is None:
            keep_vexa_alive(p)
            if t - S['t_first'] >= 3.0:
                setup(w, pc, p, t)
            return
        if t == S['last_t']:
            return               # one pass per world tick
        S['last_t'] = t
        S['ticks'] += 1
        shot_tick()
        advance_tick(p, t)
        if t >= S['next_sample'] - 1e-4:
            S['next_sample'] = t + SAMPLE
            gm = u.GameplayStatics.get_game_mode(w)
            live = sample(w, gm, p, t)
            if not S['shot']:
                if not try_close_ups(live, t) and t >= S['next_group']:
                    try_group_still(live, t)
            cull_and_shoot(w, gm, live, t)
        el = t - S['t0']
        if el >= WINDOW or (S['max_wave'] > 3 and el >= 90.0):
            if S['shot']:
                return           # let a pending still land first
            R['notes'].append('window closed at t=%.1f wave=%d' % (el, S['max_wave']))
            finish()
    except Exception:
        R['errors'].append(traceback.format_exc())
        print('PROVE_ZOMBIES_ERROR', R['errors'][-1], flush=True)
        finish()
    finally:
        S['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
S['handle'] = u.register_slate_post_tick_callback(tick)
