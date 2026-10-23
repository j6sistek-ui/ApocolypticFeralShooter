"""Assess recorded motion behavior. Does not establish owner feel or packaged performance."""
import json
import math
import sys
from pathlib import Path

root = Path(sys.argv[1])
checks, metrics = {}, {}

def read(name):
    return json.loads((root / name / 'runtime.json').read_text())

def check(name, value):
    checks[name] = bool(value)

def speed(row):
    return math.hypot(*row['velocity'][:2])

def magnitude(vector):
    return math.sqrt(sum(v * v for v in vector))

def angle_delta(a, b):
    return (a - b + 180) % 360 - 180

def rows(run, a, b):
    return [r for r in run['curves'] if a <= r['t'] <= b]

def span(group, bone, axis):
    values = [r['bones'][bone][axis] for r in group]
    return max(values) - min(values)

c = read('Character')
cs = {r['label']: r for r in c['samples']}
check('character_finished', not c['errors'] and '15_LightingAfter' in cs)
check('parkour_character_active', all(r['parkour'] for r in c['curves']))
movement = c['defaults']['movement']
check('parkour_source_movement_defaults', movement == {
    'max_walk_speed': 3000., 'max_acceleration': 1000.,
    'braking_deceleration_walking': 2048., 'ground_friction': 8.,
    'jump_z_velocity': 1102.5, 'gravity_scale': 2.5})
check('analog_then_full_speed', 100 < speed(cs['02_Walk']) < speed(cs['03_Jog'])
      and 2900 < speed(cs['03_Jog']) <= 3001)
metrics['parkour_max_speed_cm_s'] = max(speed(r) for r in c['curves'])
for label, target in [('03_Jog', 0), ('04_Backward', 180),
                      ('05_StrafeLeft', -90), ('06_StrafeRight', 90)]:
    row = cs[label]
    travel = math.degrees(math.atan2(row['velocity'][1], row['velocity'][0]))
    check(label + '_travels_and_faces_direction', speed(row) > 500 and
          abs(angle_delta(travel, target)) < 5 and
          abs(angle_delta(row['body_yaw'], travel)) < 5)
check('aim_keeps_body_facing_camera', abs(angle_delta(cs['12_AimStrafe']['body_yaw'],
      cs['12_AimStrafe']['yaw'])) < 5 and speed(cs['12_AimStrafe']) > 100)
for name, a, b in [('forward', 7, 11), ('back', 14.8, 16.8),
                   ('left', 17.8, 19.8), ('right', 20.8, 22.8)]:
    group = rows(c, a, b)
    check(name + '_foot_cycles', max(span(group, 'foot_l', i) for i in (0, 1)) > 12)
metrics['jump_height_cm'] = max(r['location'][2] for r in rows(c, 31, 32.6)) - cs['01_Idle']['location'][2]
check('controller_jump_and_fall', metrics['jump_height_cm'] > 150 and
      cs['09_Jump']['falling'] and cs['10_Fall']['falling'])
metrics['walking_secondary_max_cm'] = max(magnitude(v) for r in rows(c, 6, 22) for v in r['secondary'])
metrics['settled_secondary_max_cm'] = max(magnitude(v) for v in cs['13_Settled']['secondary'])
check('walking_secondary_active_and_bounded', .25 < metrics['walking_secondary_max_cm'] <= 3.21)
check('secondary_settles', metrics['settled_secondary_max_cm'] < .15)
metrics['chain_max_degrees'] = max(abs(v) for r in cs.values() for v in r['chain'][:2])
check('chain_reacts_and_settles', metrics['chain_max_degrees'] > 5 and
      max(abs(v) for v in cs['13_Settled']['chain'][:2]) < 1)
parts = c['defaults']['parts']
check('fitted_five_part_defaults', len(parts) == 5 and all(
    p['morphs'] == p['expected_morphs'] and p['physics'] == p['expected_physics'] for p in parts))
check('local_materials_and_contact_shadows', all(p['contact_shadow'] and all(
    '/Game/HoverPrototype/Appearance/' in m for m in p['materials']) for p in parts))
check('balanced_runtime_lighting', all(abs(p['auto_exposure_bias'] - .25) < .01 and
    p['film_grain_intensity'] == 0 and p['bloom_intensity'] < .21 and
    p['lumen_final_gather_quality'] >= 5 for p in c['defaults']['postprocess']))

g = read('Glider')
gs = {r['label']: r for r in g['samples']}
check('glider_finished', not g['errors'] and g['events'][-1]['label'] == 'done')
metrics['grounded_aim_foot_delta_cm'] = max(abs(gs[label]['feet'][f][2] - gs['01_Grounded_Idle']['feet'][f][2])
    for label in ['02_Grounded_Aim', '03_Grounded_AimFire', '04_Hipfire'] for f in ['foot_l', 'foot_r'])
check('grounded_aim_feet_stable', metrics['grounded_aim_foot_delta_cm'] < 1)
check('hipfire_has_visible_gun_and_shots', gs['04_Hipfire']['gun_visible'] and
      gs['04_Hipfire']['shots'] > gs['03_Grounded_AimFire']['shots'])
check('controller_mount_and_high_exit_block', gs['05_Mounted']['mounted'] and
      gs['07_HighExitBlocked']['mounted'] and not gs['07_HighExitBlocked']['can_dismount'])
metrics['coast_speed_m_s'] = speed(gs['09_Coast']) / 100
check('release_coasts_then_stops', 300 < speed(gs['09_Coast']) < speed(gs['08_Forward']) and speed(gs['10_Stopped']) < 5)
check('brake_before_reversing', gs['12_Braking']['velocity'][0] < 0 and
      speed(gs['12_Braking']) < speed(gs['09_Coast']))
check('opposite_wing_reactions', gs['08_Forward']['wing'] > 5 and gs['11_Reverse']['wing'] < -5)
check('forward_reverse_board_pitch', gs['08_Forward']['pitch'] < -3 and gs['11_Reverse']['pitch'] > 3)
check('right_stick_climb_and_dive', gs['13_Climb']['velocity'][2] > 300 and gs['13_Climb']['pitch'] > 5 and
      gs['14_Dive']['velocity'][2] < -300 and gs['14_Dive']['pitch'] < -5)
check('shoulders_bank_then_level', gs['15_BankLeft']['bank'] < -20 and gs['16_BankRight']['bank'] > 20 and abs(gs['17_BankLevel']['bank']) < 1)
for name, a, b, sign in [('left', 40.5, 41.8, -1), ('right', 42.5, 43.8, 1)]:
    group = rows(g, a, b)
    metrics[name + '_bank_yaw_change_degrees'] = angle_delta(group[-1]['yaw'], group[0]['yaw'])
    check(name + '_bank_bends_travel', metrics[name + '_bank_yaw_change_degrees'] * sign > 3)
metrics['boost_speed_m_s'] = speed(gs['18_Boost']) / 100
check('boost_stronger_drains_recharges', speed(gs['18_Boost']) > speed(gs['08_Forward']) * 2 and
      .1 < gs['18_Boost']['boost'] < .9 and gs['19_BoostEmpty']['boost'] < .05 and gs['22_BoardLanded']['boost'] > .9)
check('safe_exit_succeeds', gs['20_LowReady']['can_dismount'] and not gs['21_Released']['mounted'])
# Compare with the last mounted pose: by the post-release sample the board may
# already have fallen during the controller hold/sample interval.
metrics['released_board_drop_cm'] = gs['20_LowReady']['board_location'][2] - gs['22_BoardLanded']['board_location'][2]
check('released_board_falls_and_settles', gs['22_BoardLanded']['board_physics'] and
      metrics['released_board_drop_cm'] > 20 and magnitude(gs['22_BoardLanded']['board_velocity']) < 5)
check('remount_and_touchdown', gs['24_Remounted']['mounted'] and gs['26_LandingSettled']['mounted'] and gs['26_LandingSettled']['can_dismount'])
check('boosters_follow_travel', all(c['active'] for c in gs['18_Boost']['boosters']) and not any(c['active'] for c in gs['22_BoardLanded']['boosters']))
errors = [math.dist(r['feet'][f], [r['pads'][p][i] + 8.5 * r['board_up'][i] for i in range(3)])
    for r in g['samples'] if r['mounted'] for f, p in [('foot_l', 'foot_contact_L'), ('foot_r', 'foot_contact_R')]]
metrics['max_ankle_target_error_cm'] = max(errors)
check('feet_follow_pads', max(errors) < 3)
metrics['steady_hover_secondary_cm'] = max(magnitude(v) for r in rows(g, 20, 22) for v in r['secondary'])
check('steady_hover_ignores_tiny_motion', metrics['steady_hover_secondary_cm'] < .1)
metrics['steady_dive_pelvis_range_cm'] = span(rows(g, 36, 36.8), 'pelvis', 2)
check('dive_does_not_cycle_crouch', metrics['steady_dive_pelvis_range_cm'] < 3)
check('inflight_gun_shoots', gs['19a_RideGun']['gun_visible'] and gs['19a_RideGun']['shots'] > gs['04_Hipfire']['shots'])
check('left_right_rider_shift', math.dist(gs['15_BankLeft']['bones']['spine_03'], gs['16_BankRight']['bones']['spine_03']) > 5)

v = read('Vehicles')
vs = {r['label']: r for r in v['samples']}
check('vehicles_finished', not v['errors'] and v['events'][-1]['label'] == 'done')
for name, result in v['checks'].items():
    check(name, result)
check('bike_RT_drives_forward', vs['bike_driven']['speed'] > 300)
check('bike_LT_brakes_then_reverses', abs(vs['bike_braking']['speed']) < abs(vs['bike_driven']['speed']) and vs['bike_reverse']['speed'] < -300)
check('bike_right_stick_direction', angle_delta(vs['bike_look_right']['camera_yaw'], vs['bike_reverse']['camera_yaw']) > 5)
check('bike_B_boost', vs['bike_boost']['boost'] and vs['bike_boost']['speed'] > vs['bike_driven']['speed'])

result = {'passed': all(checks.values()), 'checks': checks, 'metrics': metrics,
          'limits': ['Injected controller input; physical controller feel and owner visual acceptance remain open.',
                     'Wall-run/coyote-time graphs retained; those maneuvers are not established by this flat-platform test.',
                     'No packaged build, representative performance or long-session acceptance.']}
(root / 'assessment.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
sys.exit(0 if result['passed'] else 1)
