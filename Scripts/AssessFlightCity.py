import json,math
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'Saved/Automation/FlightCity';m=json.loads((root/'motion_final/runtime.json').read_text());city=json.loads((root/'city_runtime/runtime.json').read_text());samples={s['label']:s for s in m['samples']};checks={}
def check(name,value):checks[name]=bool(value)
check('motion_script_errors',not m['errors']);check('city_roundtrip_errors',not city['errors'])
for label,speed in [('walk',500),('run_straight',900),('run_diagonal',900),('run_camera_turn',900),('crouch',400),('stand_after_crouch',900),('thrust',2160)]:check(label+'_speed',abs(samples[label]['speed']-speed)<2)
check('slide_preserves_running_momentum',600<samples['crouch_transition']['speed']<900)
check('crouch_grounded',samples['crouch']['height']==60 and 'WALKING' in samples['crouch']['mode'])
check('stand_restored',samples['stand_after_crouch']['height']==100)
check('ground_jump_falling','FALLING' in samples['ground_jump']['mode'])
hop=[v for v in m['curves'] if 36<v['t']<38];check('ollie_peak',295<max(v['location'][2] for v in hop)-m['hop_start']<301)
check('ollie_settle',abs(samples['hop_settle']['location'][2]-m['hop_start']-166)<1)
check('climb_speed',abs(samples['climb']['velocity'][2]-1800)<5);check('dive_speed',abs(samples['dive']['velocity'][2]+2400)<5)
normal=samples['bank_normal'];enhanced=samples['bank_enhanced'];check('enhanced_bank_angle',abs(enhanced['bank'])>abs(normal['bank'])*1.8)
check('enhanced_turn',enhanced['yaw']%360>(normal['yaw']%360)*1.6)
check('quiet_flight_settles',samples['quiet_flight']['speed']<1)
for s in city['samples']:
 check(s['label']+'_invulnerable',s['damage']==0);check(s['label']+'_three_rides',s['rides']['glider']==1 and len(s['rides']['BP_Hoverbike'])==len(s['rides']['BP_Crossroad_Pickup'])==1)
 if 'city' in s['label']:
  check(s['label']+'_bike_on_street',400<s['rides']['BP_Hoverbike'][0]['location'][2]<550)
check('both_maps_and_return',[s['world'] for s in city['samples']]==['PostApo','L_CyberCity','L_CyberCity','PostApo'])
r={'checks':checks,'passed':sum(checks.values()),'total':len(checks),'failures':[k for k,v in checks.items() if not v]};(root/'assessment.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2));assert not r['failures']
