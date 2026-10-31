"""CPU-only zombie attack probe for L_NYC_Survival; no rendered-quality claim.

Answers "do NYC zombies swing, and does the damage reach Vexa?" Runs PIE on L_NYC_Survival
(NullRHI is fine: nothing is captured), isolates test input so Vexa stands still at the
survival start, and does NOT hold her health. Every 0.5 s of game time for 90 s it records:

  player : HP (pilot get_health / get_max_health and the ZE survival component), invincible,
           defeated, capsule size and its response to the Pawn channel
  zombie : 2D/3D distance, within the definition AttackRange (the vendor 3D centre test),
           montage playing (anim instance) and which, bIsAttacking, velocity, facing angle to
           Vexa, a geometric replica of the vendor OnAttackHitCheck sweep (would it reach her,
           and is another zombie capsule in the way first), blackboard CanAttack / IsAttacking /
           TargetEnemy, path-following status, and the crowd-ai counters
           (MontageFlinches, SuppressedFlinches, FlinchCancels, AttackSwings, TokenDenials;
           AI MoveToRewrites, SlotReissues)
  slots  : UHoverAttackSlotSubsystem tokens in use / peak / ring moves / peak heavy inner

After the window three staged tests run on the in-range zombie facing Vexa most squarely:
the vendor OnAttackHitCheck called directly, a raw ACharacter.PlayAnimMontage with the DA
montage, and PerformAttack through its UFUNCTION (traced for 3 s). Then one control hit is applied to Vexa with a live zombie as causer
(GameplayStatics.apply_damage), which separates "the hit check never lands" from "damage
does not get through AHoverPilot::TakeDamage". HOVER_* and vendor "ZE:" log lines are copied
from the -abslog file. Changes only the unsaved Play world.

Output: D:/AFS_Comparisons/NYCSurvival_<date>/attack_probe.json
"""
import json
import math
import re
import time
import traceback
from pathlib import Path
import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
OUT.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUT / 'attack_probe.json'
SAMPLE = 0.5
WINDOW = 90.0
TIMEOUT = 900
CONTROL_DAMAGE = 10.0
COUNTERS = ('montage_flinches', 'suppressed_flinches', 'flinch_cancels', 'attack_swings', 'token_denials')
AI_COUNTERS = ('move_to_rewrites', 'slot_reissues')

REPORT = {'errors': [], 'notes': [], 'setup': {}, 'samples': [], 'zombies': {}, 'player_hp': [],
          'control_hit': None, 'log': {}, 'summary': {},
          'claim': 'CPU-only PIE under NullRHI; health NOT held; facing/sweep values are a geometric '
                   'replica of ZE_ZombieCharacter::OnAttackHitCheck, not the physics query itself'}
STATE = {'start': time.monotonic(), 'play': False, 'busy': False, 'end': None, 'pc': None, 't0': None,
         'next': 0.0, 'done': False}
LEVEL = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert LEVEL.load_level(MAP), 'Loading %s failed' % MAP


def save():
    REPORT_PATH.write_text(json.dumps(REPORT, indent=1, default=str))


def prop(obj, *names):
    """First readable Python-exposed property among names, else None."""
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


def vec(v):
    return [round(v.x, 1), round(v.y, 1), round(v.z, 1)] if v is not None else None


def capsule_of(actor):
    c = call(actor, 'get_component_by_class', u.CapsuleComponent)
    if not c:
        return None, 0.0, 0.0
    return c, c.get_scaled_capsule_radius(), c.get_scaled_capsule_half_height()


def enum_name(v):
    n = getattr(v, 'name', None)
    return n if n else str(v).split('.')[-1].split(':')[0].strip('<> ')


def pawn_response(capsule):
    if not capsule:
        return None
    try:
        r = capsule.get_collision_response_to_channel(u.CollisionChannel.ECC_PAWN)
        return enum_name(r)
    except Exception:
        return 'unknown'


def point_seg_dist(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    den = sum(x * x for x in ab)
    t = 0.0 if den <= 1e-6 else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / den))
    q = [a[i] + ab[i] * t for i in range(3)]
    return math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3)))


def sweep_contact(start, end, sphere, centre, radius, half):
    """Earliest sweep fraction t in [0,1] at which the vendor sphere touches the capsule, else None."""
    lo = [centre[0], centre[1], centre[2] - max(0.0, half - radius)]
    hi = [centre[0], centre[1], centre[2] + max(0.0, half - radius)]
    steps = 40
    for k in range(steps + 1):
        t = k / steps
        p = [start[i] + (end[i] - start[i]) * t for i in range(3)]
        if point_seg_dist(p, lo, hi) <= sphere + radius:
            return t
    return None


def stats_of(z):
    d = prop(z, 'zombie_data')
    s = prop(d, 'stats') if d else None
    row = {'definition': d.get_name() if d else None,
           'definition_class': d.get_class().get_name() if d else None}
    if s:
        for k in ('attack_range', 'attack_sphere_radius', 'melee_damage', 'attack_cooldown', 'run_speed'):
            row[k] = prop(s, k)
    if d:
        for k in ('queue_ring_radius', 'capsule_radius', 'capsule_half_height', 'windup_seconds',
                  'close_walk_speed', 'role'):
            v = prop(d, k)
            row[k] = str(v) if k == 'role' else v
        montages = prop(d, 'attack_montages')
        row['attack_montages'] = [str(m) for m in montages] if montages is not None else None
        row['behavior_tree'] = str(prop(d, 'behavior_tree'))
    return row


def blackboard(z):
    bb = None
    try:
        bb = u.AIBlueprintHelperLibrary.get_blackboard(z)
    except Exception:
        pass
    if not bb:
        ai = z.get_controller()
        bb = prop(ai, 'blackboard') if ai else None
    if not bb:
        return {}
    out = {}
    for key, fn in (('CanAttack', 'get_value_as_bool'), ('IsAttacking', 'get_value_as_bool'),
                    ('AttackCooldown', 'get_value_as_float')):
        out[key] = call(bb, fn, key)
    tgt = call(bb, 'get_value_as_object', 'TargetEnemy')
    out['TargetEnemy'] = tgt.get_name() if tgt else None
    loc = call(bb, 'get_value_as_vector', 'AttackSlotLocation')
    out['has_AttackSlotLocation_value'] = loc is not None and (abs(loc.x) + abs(loc.y)) > 0
    return out


def slot_subsystem(w):
    errs = []
    try:
        cls = u.HoverAttackSlotSubsystem
    except Exception:
        cls = None
        errs.append('HoverAttackSlotSubsystem not exposed to Python')
    if cls:
        pc = u.GameplayStatics.get_player_controller(w, 0)
        for ctx in (pc, w):
            try:
                ss = u.SubsystemBlueprintLibrary.get_world_subsystem(ctx, cls)
                if ss:
                    return ss
            except Exception as e:
                errs.append(repr(e)[:200])
    if errs and not STATE.get('slot_note'):
        STATE['slot_note'] = True
        REPORT['notes'].append('slot subsystem lookup: ' + '; '.join(errs))
    return None


def sample(w, gm, pc, p, t):
    el = t - STATE['t0']
    pcap, pr, ph = capsule_of(p)
    pl = p.get_actor_location()
    surv = call(p, 'get_component_by_class', u.ZE_SurvivalComponent)
    player = {'hp': call(p, 'get_health'), 'max_hp': call(p, 'get_max_health'),
              'survival_hp': call(surv, 'get_health') if surv else None,
              'survival_max': call(surv, 'get_max_health') if surv else None,
              'invincible': call(p, 'is_invincible'), 'defeated': call(p, 'is_defeated'),
              'mounted': call(p, 'is_mounted'), 'loc': vec(pl)}
    wave = call(gm, 'get_current_wave')
    row = {'t': round(el, 2), 'wave': wave, 'wave_state': enum_name(call(gm, 'get_wave_state')),
           'zombies_remaining': call(gm, 'get_zombies_remaining'), 'player': player, 'zombies': []}
    REPORT['player_hp'].append([round(el, 2), player['hp']])
    ss = slot_subsystem(w)
    if ss:
        row['slots'] = {'tokens_in_use': call(ss, 'get_tokens_in_use'),
                        'peak_tokens': call(ss, 'get_peak_tokens_in_use'),
                        'ring_moves': call(ss, 'get_ring_moves'),
                        'peak_heavy_inner': call(ss, 'get_peak_heavy_inner'),
                        'live_corpses': call(ss, 'get_live_corpse_count')}
    zombies = list(u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie))
    caps = {}
    for z in zombies:
        c, r, h = capsule_of(z)
        zl = z.get_actor_location()
        caps[z.get_name()] = ([zl.x, zl.y, zl.z], r, h, pawn_response(c))
    for z in zombies:
        name = z.get_name()
        info = REPORT['zombies'].get(name)
        if info is None:
            c, r, h = capsule_of(z)
            info = {'class': z.get_class().get_name(), 'first_t': round(el, 2), 'stats': stats_of(z),
                    'capsule_radius': r, 'capsule_half_height': h, 'capsule_pawn_response': pawn_response(c),
                    'controller': None, 'montages_seen': [], 'max_counters': {}, 'samples_in_range': 0,
                    'samples_montage': 0, 'samples_facing_hit': 0, 'samples_blocked_by_zombie': 0,
                    'samples': 0, 'min_dist2d': None}
            REPORT['zombies'][name] = info
        st = info['stats']
        hp = None
        zs = prop(z, 'survival_component')
        if zs:
            hp = call(zs, 'get_health')
        if hp is not None and hp <= 0:
            continue
        zl = z.get_actor_location()
        d2 = math.hypot(zl.x - pl.x, zl.y - pl.y)
        d3 = math.sqrt(d2 * d2 + (zl.z - pl.z) ** 2)
        rng = st.get('attack_range') or 150.0
        sph = st.get('attack_sphere_radius') or 50.0
        fwd = z.get_actor_forward_vector()
        to = [pl.x - zl.x, pl.y - zl.y]
        n = math.hypot(*to) or 1.0
        cosang = max(-1.0, min(1.0, (fwd.x * to[0] + fwd.y * to[1]) / (n * (math.hypot(fwd.x, fwd.y) or 1.0))))
        facing = math.degrees(math.acos(cosang))
        start = [zl.x + fwd.x * 40, zl.y + fwd.y * 40, zl.z + fwd.z * 40]
        end = [start[i] + [fwd.x, fwd.y, fwd.z][i] * rng for i in range(3)]
        t_pilot = sweep_contact(start, end, sph, [pl.x, pl.y, pl.z], pr, ph)
        blocker = None
        if t_pilot is not None:
            for other, (oc, orad, oh, oresp) in caps.items():
                if other == name or oresp not in (None, 'ECR_BLOCK', 'unknown'):
                    continue
                to_ = sweep_contact(start, end, sph, oc, orad, oh)
                if to_ is not None and to_ < t_pilot:
                    blocker = other
                    break
        anim = call(z.mesh, 'get_anim_instance') if prop(z, 'mesh') else None
        playing = call(anim, 'is_any_montage_playing') if anim else None
        mont = call(z, 'get_current_montage')
        mname = mont.get_name() if mont else None
        if mname and mname not in info['montages_seen']:
            info['montages_seen'].append(mname)
        ai = z.get_controller()
        counters = {k: prop(z, k) for k in COUNTERS}
        if ai:
            info['controller'] = ai.get_class().get_name()
            for k in AI_COUNTERS:
                counters[k] = prop(ai, k)
            counters['move_status'] = enum_name(call(ai, 'get_move_status'))
        for k, v in counters.items():
            if isinstance(v, int):
                info['max_counters'][k] = max(info['max_counters'].get(k, 0), v)
        vel = z.get_velocity()
        zr = {'name': name, 'd2': round(d2, 1), 'd3': round(d3, 1), 'dz': round(zl.z - pl.z, 1),
              'in_vendor_range': d3 <= rng, 'montage_playing': playing, 'montage': mname,
              'is_attacking': prop(z, 'is_attacking', 'b_is_attacking'), 'speed': round(vel.length(), 1),
              'facing_deg': round(facing, 1), 'sweep_reaches_pilot': t_pilot is not None,
              'sweep_blocked_by': blocker, 'bb': blackboard(z), 'hp': hp}
        zr.update(counters)
        row['zombies'].append(zr)
        info['samples'] += 1
        info['samples_in_range'] += 1 if zr['in_vendor_range'] else 0
        info['samples_montage'] += 1 if playing else 0
        info['samples_facing_hit'] += 1 if (t_pilot is not None and blocker is None) else 0
        info['samples_blocked_by_zombie'] += 1 if blocker else 0
        info['min_dist2d'] = d2 if info['min_dist2d'] is None else min(info['min_dist2d'], d2)
    REPORT['samples'].append(row)


def setup(w, pc, p):
    gm = u.GameplayStatics.get_game_mode(w)
    pcap, pr, ph = capsule_of(p)
    REPORT['setup'] = {'mode': gm.get_class().get_name() if gm else None, 'world': w.get_name(),
                       'pawn': p.get_class().get_name(), 'pawn_capsule_radius': pr, 'pawn_capsule_half_height': ph,
                       'pawn_capsule_pawn_response': pawn_response(pcap), 'start': vec(p.get_actor_location()),
                       'invincible': call(p, 'is_invincible'), 'max_hp': call(p, 'get_max_health'),
                       'slot_subsystem': bool(slot_subsystem(w)),
                       'damage_scale_w1': call(gm, 'get_round_damage_scale', 1),
                       'damage_scale_w0': call(gm, 'get_round_damage_scale', 0)}
    save()


def control_hit(w, p):
    zombies = [z for z in u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie)]
    if not zombies:
        REPORT['control_hit'] = {'skipped': 'no zombie alive'}
        return
    z = zombies[0]
    before = call(p, 'get_health')
    applied = u.GameplayStatics.apply_damage(p, CONTROL_DAMAGE, z.get_controller(), z, u.DamageType)
    REPORT['control_hit'] = {'causer': z.get_name(), 'damage': CONTROL_DAMAGE, 'applied_return': applied,
                             'hp_before': before, 'hp_after': call(p, 'get_health')}


def log_path():
    try:
        cmd = u.SystemLibrary.get_command_line()
    except Exception:
        return None
    m = re.search(r'-abslog="?([^"\s]+)', cmd)
    return m.group(1) if m else None


def harvest_log():
    path = log_path()
    REPORT['log']['path'] = path
    if not path or not Path(path).exists():
        REPORT['notes'].append('abslog not found; HOVER_* lines not harvested')
        return
    lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    hover = [l for l in lines if 'HOVER_' in l and 'HOVER_PERF' not in l]
    ze = [l for l in lines if 'LogZombieEngineStudio' in l]
    REPORT['log']['hover_lines'] = hover[-400:]
    REPORT['log']['vendor_lines'] = ze[-200:]
    REPORT['log']['vendor_attack_hits'] = sum(1 for l in ze if 'Attack Hit' in l)
    REPORT['log']['vendor_no_montage_warnings'] = sum(1 for l in ze if 'no cached attack montages' in l)


def summarise():
    zs = REPORT['zombies'].values()
    hp = [h for _, h in REPORT['player_hp'] if h is not None]
    s = REPORT['summary']
    s['zombies_seen'] = len(REPORT['zombies'])
    s['hp_start'] = hp[0] if hp else None
    s['hp_min'] = min(hp) if hp else None
    s['hp_end'] = hp[-1] if hp else None
    s['damage_taken_in_window'] = (hp[0] - min(hp)) if hp else None
    for k in COUNTERS + AI_COUNTERS:
        s['total_' + k] = sum(z['max_counters'].get(k, 0) for z in zs)
    s['zombie_samples'] = sum(z['samples'] for z in zs)
    s['samples_in_vendor_range'] = sum(z['samples_in_range'] for z in zs)
    s['samples_montage_playing'] = sum(z['samples_montage'] for z in zs)
    s['samples_sweep_would_hit'] = sum(z['samples_facing_hit'] for z in zs)
    s['samples_sweep_blocked_by_zombie'] = sum(z['samples_blocked_by_zombie'] for z in zs)
    s['montages_seen'] = sorted({m for z in zs for m in z['montages_seen']})
    s['vendor_attack_hits_logged'] = REPORT['log'].get('vendor_attack_hits')
    slots = [r['slots'] for r in REPORT['samples'] if r.get('slots')]
    if slots:
        s['peak_tokens'] = max(x['peak_tokens'] or 0 for x in slots)
        s['ring_moves'] = slots[-1]['ring_moves']


def pick_zombie(w, p):
    """Live zombie inside the vendor range with the smallest facing error to Vexa."""
    pl = p.get_actor_location()
    best, best_a = None, None
    for z in u.GameplayStatics.get_all_actors_of_class(w, u.HoverCyberZombie):
        zl = z.get_actor_location()
        d3 = (zl - pl).length()
        st = REPORT['zombies'].get(z.get_name(), {}).get('stats', {})
        if d3 > (st.get('attack_range') or 150.0):
            continue
        f = z.get_actor_forward_vector()
        to = u.Vector(pl.x - zl.x, pl.y - zl.y, 0)
        n = to.length() or 1.0
        a = math.degrees(math.acos(max(-1.0, min(1.0, (f.x * to.x + f.y * to.y) / n))))
        if best_a is None or a < best_a:
            best, best_a = z, a
    return best, best_a


def zstate(z):
    anim = call(z.mesh, 'get_anim_instance')
    m = call(z, 'get_current_montage')
    return {'is_attacking': prop(z, 'is_attacking', 'b_is_attacking'),
            'montage_playing': call(anim, 'is_any_montage_playing') if anim else None,
            'montage': m.get_name() if m else None,
            **{k: prop(z, k) for k in ('attack_swings', 'token_denials')}}


def staged(w, p, el):
    """Direct stage tests after the window: hit check, raw montage play, then PerformAttack."""
    T = STATE.setdefault('stage_tests', {'step': 0, 'at': el})
    R = REPORT.setdefault('stage_tests', {})
    z = STATE.get('stage_zombie')
    if T['step'] == 0:
        z, ang = pick_zombie(w, p)
        if not z:
            R['skipped'] = 'no zombie inside AttackRange'
            return True
        STATE['stage_zombie'] = z
        mesh = z.mesh
        anim = call(mesh, 'get_anim_instance')
        sk = call(mesh, 'get_skeletal_mesh_asset') or prop(mesh, 'skeletal_mesh_asset', 'skeletal_mesh')
        data = prop(z, 'zombie_data')
        mons = [m for m in (prop(data, 'attack_montages') or [])]
        loaded = []
        for m in mons:
            try:
                obj = m.load_synchronous() if hasattr(m, 'load_synchronous') else m
            except Exception:
                obj = None
            if not obj:
                try:
                    obj = u.load_asset(str(m.get_path_name()) if hasattr(m, 'get_path_name') else str(m))
                except Exception:
                    obj = None
            loaded.append(obj)
        STATE['stage_montages'] = [m for m in loaded if m]
        R['zombie'] = z.get_name()
        R['facing_deg'] = round(ang, 1)
        R['anim_instance'] = anim.get_class().get_name() if anim else None
        R['anim_class'] = str(prop(mesh, 'anim_class'))
        R['animation_mode'] = enum_name(prop(mesh, 'animation_mode'))
        R['definition_anim_class_override'] = str(prop(prop(z, 'zombie_data'), 'anim_class_override'))
        R['mesh'] = sk.get_name() if sk else None
        R['mesh_skeleton'] = str(prop(sk, 'skeleton')) if sk else None
        R['montages'] = [{'name': m.get_name(), 'skeleton': str(call(m, 'get_editor_property', 'skeleton') or prop(m, 'skeleton')),
                          'play_length': call(m, 'get_play_length'), 'rate_scale': prop(m, 'rate_scale'),
                          'slots': str(prop(m, 'slot_anim_tracks'))[:300]} for m in STATE['stage_montages']]
        # 1. Vendor hit check called directly (no montage needed).
        hp0 = call(p, 'get_health')
        ok = True
        try:
            z.on_attack_hit_check()
        except Exception:
            ok = traceback.format_exc()
        R['hit_check'] = {'called': ok, 'hp_before': hp0, 'hp_after': call(p, 'get_health')}
        T['step'], T['at'] = 1, el
        return False
    if not z or not u.SystemLibrary.is_valid(z):
        R['aborted'] = 'stage zombie gone'
        return True
    if T['step'] == 1 and el - T['at'] >= 0.3:
        # 2. Raw ACharacter.PlayAnimMontage with the DA montage.
        res = []
        for m in STATE.get('stage_montages', [])[:1]:
            try:
                d = z.play_anim_montage(m, 1.0, 'None')
            except Exception:
                d = traceback.format_exc()
            res.append({'montage': m.get_name(), 'returned': d, 'after': zstate(z)})
        R['play_anim_montage'] = res
        T['step'], T['at'] = 2, el
        return False
    if T['step'] == 2 and el - T['at'] >= 0.3:
        R['play_anim_montage_after_0_3s'] = zstate(z)
        try:
            z.stop_anim_montage(None)
        except Exception:
            pass
        T['step'], T['at'] = 3, el
        return False
    if T['step'] == 3 and el - T['at'] >= 2.5:
        # 3. PerformAttack through the UFUNCTION (dispatches to AHoverNYCZombie::PerformAttack).
        R['perform_attack_before'] = zstate(z)
        R['perform_attack_hp_before'] = call(p, 'get_health')
        try:
            z.perform_attack(p)
            R['perform_attack_called'] = True
        except Exception:
            R['perform_attack_called'] = traceback.format_exc()
        R['perform_attack_trace'] = [[0.0, zstate(z)]]
        T['step'], T['at'] = 4, el
        return False
    if T['step'] == 4:
        if el - T['at'] >= 0.1 * len(R['perform_attack_trace']):
            R['perform_attack_trace'].append([round(el - T['at'], 2), zstate(z)])
        if el - T['at'] >= 3.0:
            R['perform_attack_hp_after'] = call(p, 'get_health')
            return True
    return False


def finish():
    if STATE['end']:
        return
    try:
        w = u.HoverAuthoring.get_playtest_world()
        if w and STATE['pc']:
            p = STATE['pc'].get_controlled_pawn()
            if p:
                control_hit(w, p)
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    save()
    LEVEL.editor_request_end_play()
    STATE['end'] = time.monotonic()


def tick(dt):
    if STATE['busy']:
        return
    STATE['busy'] = True
    try:
        if STATE['end']:
            if time.monotonic() - STATE['end'] > 3 and not u.HoverAuthoring.get_playtest_world():
                if not STATE['done']:
                    STATE['done'] = True
                    harvest_log()
                    summarise()
                    save()
                    print('NYC_ATTACK_PROBE', json.dumps(REPORT['summary'], default=str), flush=True)
                u.unregister_slate_post_tick_callback(STATE['handle'])
                u.EditorPythonScripting.set_keep_python_script_alive(False)
                u.SystemLibrary.quit_editor()
            return
        if time.monotonic() - STATE['start'] > TIMEOUT:
            raise RuntimeError('attack probe timeout')
        if not STATE['play']:
            if time.monotonic() - STATE['start'] > 5:
                u.HoverAuthoring.start_playtest()
                STATE['play'] = True
            return
        w = u.HoverAuthoring.get_playtest_world()
        if not w:
            return
        pc = u.GameplayStatics.get_player_controller(w, 0)
        if not pc or not pc.get_controlled_pawn():
            return
        if STATE['pc'] != pc:
            STATE['pc'] = pc
            u.HoverAuthoring.isolate_test_input(pc)
        p = pc.get_controlled_pawn()
        t = u.GameplayStatics.get_time_seconds(w)
        if STATE['t0'] is None:
            STATE['t0'] = t
            STATE['next'] = t
            setup(w, pc, p)
        if t >= STATE['next']:
            STATE['next'] = t + SAMPLE
            sample(w, u.GameplayStatics.get_game_mode(w), pc, p, t)
            if len(REPORT['samples']) % 20 == 0:
                save()
        if t - STATE['t0'] >= WINDOW and staged(w, p, t - STATE['t0']):
            finish()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
        finish()
    finally:
        STATE['busy'] = False


u.EditorPythonScripting.set_keep_python_script_alive(True)
STATE['handle'] = u.register_slate_post_tick_callback(tick)
