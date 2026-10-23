"""Check recorded play behavior, not a substitute for controller-feel review."""
import json
import math
import sys
from pathlib import Path

source = Path(sys.argv[1])
run = json.loads(source.read_text())
samples = {row['label']: row for row in run['samples']}
checks = {}
metrics = {}

def check(name, passed):
    checks[name] = bool(passed)

def speed(row):
    return math.hypot(*row['velocity'][:2])

check('script_finished', not run['errors'] and run['events'][-1]['label'] == 'done')
idle = samples['01_Grounded_Idle']
metrics['grounded_aim_foot_delta_cm'] = max(
    abs(samples[label]['feet'][foot][2] - idle['feet'][foot][2])
    for label in ['02_Grounded_Aim', '03_Grounded_AimFire', '04_Hipfire']
    for foot in ['foot_l', 'foot_r'])
check('grounded_aim_keeps_feet', metrics['grounded_aim_foot_delta_cm'] < 1.)
check('hipfire_has_gun_and_shots', samples['04_Hipfire']['gun_visible'] and
      samples['04_Hipfire']['shots'] > samples['03_Grounded_AimFire']['shots'])
check('controller_hold_mounts', samples['05_Mounted']['mounted'])
check('high_exit_blocked', samples['07_HighExitBlocked']['mounted'] and
      not samples['07_HighExitBlocked']['can_dismount'])
metrics['speed_after_release_mps'] = speed(samples['09_Coast']) / 100
check('release_coasts_then_stops', 300 < speed(samples['09_Coast']) < speed(samples['08_Forward']) and
      speed(samples['10_Stopped']) < 5.)
check('opposite_input_brakes_before_reverse', samples['12_Braking']['velocity'][0] < 0 and
      speed(samples['12_Braking']) < speed(samples['09_Coast']))
check('wing_reactions_opposite', samples['08_Forward']['wing'] > 5 and samples['11_Reverse']['wing'] < -5)
check('right_stick_climbs_and_dives', samples['13_Climb']['velocity'][2] > 300 and
      samples['13_Climb']['pitch'] > 10 and samples['14_Dive']['velocity'][2] < -300 and
      samples['14_Dive']['pitch'] < -10)
check('shoulders_bank_and_release_levels', samples['15_BankLeft']['bank'] < -20 and
      samples['16_BankRight']['bank'] > 20 and abs(samples['17_BankLevel']['bank']) < 1)
metrics['boost_speed_mps'] = speed(samples['18_Boost']) / 100
check('boost_stronger_and_drains', speed(samples['18_Boost']) > speed(samples['08_Forward']) * 2 and
      .1 < samples['18_Boost']['boost'] < .9 and samples['19_BoostEmpty']['boost'] < .05)
check('boost_recharges', samples['22_BoardLanded']['boost'] > .9)
check('safe_exit_succeeds', samples['20_LowReady']['can_dismount'] and not samples['21_Released']['mounted'])
metrics['released_board_drop_cm'] = samples['21_Released']['board_location'][2] - samples['22_BoardLanded']['board_location'][2]
check('released_board_falls_and_settles', samples['22_BoardLanded']['board_physics'] and
      metrics['released_board_drop_cm'] > 20 and
      math.sqrt(sum(v*v for v in samples['22_BoardLanded']['board_velocity'])) < 5)
check('settled_board_can_remount', samples['24_Remounted']['mounted'])
check('mounted_touchdown_stays_mounted', samples['26_LandingSettled']['mounted'] and
      samples['26_LandingSettled']['can_dismount'])
check('boosters_active_in_travel', all(c['active'] for c in samples['18_Boost']['boosters']) and
      not any(c['active'] for c in samples['22_BoardLanded']['boosters']))
errors = []
for row in run['samples']:
    if not row['mounted']:
        continue
    for foot, pad in [('foot_l', 'foot_contact_L'), ('foot_r', 'foot_contact_R')]:
        target = [row['pads'][pad][i] + 8.5 * row['board_up'][i] for i in range(3)]
        errors.append(math.dist(row['feet'][foot], target))
metrics['max_sampled_ankle_target_error_cm'] = max(errors)
check('feet_follow_pads', metrics['max_sampled_ankle_target_error_cm'] < 3.)
result = {'checks': checks, 'metrics': metrics, 'passed': all(checks.values()),
          'limits': ['Injected input; physical controller feel and haptics require owner play.',
                     'No packaged build, performance or long-session acceptance.']}
source.with_name('assessment.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
sys.exit(0 if result['passed'] else 1)
