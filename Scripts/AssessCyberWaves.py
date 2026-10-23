"""Assess recorded integration outcomes; accepts the ZombieEngine report folder."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1]);r=json.loads((root/'runtime/runtime.json').read_text());v=json.loads((root/'vehicles/runtime.json').read_text());p=json.loads((root/'spawns/review.json').read_text())
rows={x['label']:x for x in r['samples']};first=rows['zombies_chasing'];second=rows['wave_two'];old=rows['postapo_unchanged']
checks={
 'wave_script_clean':not r['errors'],'vehicle_script_clean':not v['errors'],'spawn_review_clean':not p['errors'],
 'main_city_roundtrip':r.get('city_roundtrip',False),
 'cyber_player_preserved':'Vexa_CLS_Parkour' in first['pawn'],'wave_one_ten':first['wave']==1 and len(first['zombies'])==10,
 'zombies_pursue_player':all(z['target'] for z in first['zombies']),
 'melee_animation_active':any(z['attack'] for z in rows['melee_invulnerable']['zombies']),
 'actual_rifle_kill':r['actual_gun_kill'] and r['shots']==3,
 'speed_pickup':rows['speed_pickup']['speed_bonus']==1.5,'speed_expires':second['speed_bonus']==1,
 'nuke_completes_wave':rows['nuke_wave_complete']['remaining']==0 and rows['nuke_wave_complete']['killed']==10,
 'wave_two_grows':second['wave']==2 and second['remaining']==12,
 'wave_health_scales':any(z['max_health']==110 and z['health']==110 for z in second['zombies']),
 'wave_pause_preserved':r['pause_preserved'],'gold_reward':rows['rifle_kill']['gold']>first['gold'],
 'all_samples_invulnerable':all(x['damage']==0 for x in r['samples']+v['samples']),
 'three_rides_both_maps':all(all(n==1 for n in x['rides'].values()) for x in r['samples']),
 'postapo_isolated':old['mode']=='HoverGameMode' and old['old_zombies']==20 and r['postapo_zombie_engine_count']==0,
 'city_uses_waves_only':first['old_zombies']==0 and first['mode']=='BP_CyberWaves_C',
 'vehicle_hud_survives':all(x['wave_hud'] for x in v['samples']),
 'vehicle_target_switching':all(x['targets'] and all(x['targets']) for x in v['samples']),
 'vehicle_entry_exit':[x['label'] for x in v['samples']]==['foot','bike','after_bike','truck','after_truck'],
 'spawn_distance_observed':len(v['spawns'])==10 and min(x['distance_to_player'] for x in v['spawns'])>=1400,
 'eight_connected_entrances':len(p['points'])==8 and all(x['path_valid'] and not x['path_partial'] for x in p['points'])}
result={'passed':all(checks.values()),'checks':checks,'scope':'Rendered editor integration with injected input; physical feel, package, performance and long sessions remain unverified.'}
(root/'assessment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));sys.exit(0 if result['passed'] else 1)
