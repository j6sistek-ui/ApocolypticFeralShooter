"""Assess recorded character movement, source defaults and bounded secondary motion."""
import json,math,statistics,sys
from pathlib import Path

source=Path(sys.argv[1]);run=json.loads(source.read_text())
samples={r['label']:r for r in run['samples']};curves=run['curves'];checks={};metrics={}
def check(name,value):checks[name]=bool(value)
def speed(row):return math.hypot(*row['velocity'][:2])
def rows(a,b):return [r for r in curves if a<=r['t']<=b]
def pose_span(group,bone,axis):
    values=[r['bones'][bone][axis] for r in group]
    return max(values)-min(values) if values else 0
check('review_finished',not run['errors'] and '15_LightingAfter' in samples)
check('analog_walk_and_full_jog',150<speed(samples['02_Walk'])<300 and abs(speed(samples['03_Jog'])-600)<5)
for label,direction in [('04_Backward',180),('05_StrafeLeft',-90),('06_StrafeRight',90)]:
    check(label+'_direction',abs(samples[label]['state'][0]-direction)<5 and speed(samples[label])>580)
for name,a,b in [('walk',6.6,8.8),('jog',9.8,11.8),('back',14.8,16.8),('left',17.8,19.8),('right',20.8,22.8)]:
    group=rows(a,b)
    span=max(pose_span(group,'foot_l',i) for i in (0,1))
    metrics[name+'_foot_cycle_cm']=span
    check(name+'_feet_animate',span>12)
for label,a,b,sign in [('07_TurnLeft',24.2,25.8,-1),('08_TurnRight',26.2,27.8,1)]:
    group=rows(a,b)
    lift=max(pose_span(group,f,2) for f in ['foot_l','foot_r'])
    metrics[label+'_step_lift_cm']=lift
    check(label+'_steps_in_place',samples[label]['state'][2]*sign>50 and speed(samples[label])<1 and lift>2)
check('stops_at_idle',speed(samples['13_Settled'])<1)
air=rows(31,32.5);baseline=samples['01_Idle']['location'][2]
metrics['jump_height_cm']=max(r['location'][2]-baseline for r in air)
check('jump_and_fall',metrics['jump_height_cm']>130 and samples['09_Jump']['falling'] and samples['10_Fall']['falling'])
metrics['aim_foot_height_delta_cm']=max(abs(samples['11_Aim']['bones'][f][2]-samples['01_Idle']['bones'][f][2]) for f in ['foot_l','foot_r'])
check('grounded_aim_keeps_feet',metrics['aim_foot_height_delta_cm']<1)
offsets=[math.sqrt(sum(v*v for v in bone)) for row in curves for bone in row['secondary']]
metrics['max_secondary_displacement_cm']=max(offsets)
metrics['settled_secondary_displacement_cm']=max(math.sqrt(sum(v*v for v in bone)) for bone in samples['13_Settled']['secondary'])
check('secondary_motion_active_and_bounded',.1<max(offsets)<=2.05)
check('secondary_motion_settles',metrics['settled_secondary_displacement_cm']<.15)
parts=run['defaults']['parts']
check('source_morphs_and_physics_restored',len(parts)==6 and all(p['morphs']==p['expected_morphs'] and p['physics']==p['expected_physics'] for p in parts))
check('contact_shadows_and_local_materials',all(p['contact_shadow'] and all('/Game/HoverPrototype/Appearance/' in m for m in p['materials']) for p in parts))
movement=run['defaults']['movement']
check('source_walk_jump_defaults',movement['max_walk_speed']==600 and movement['jump_z_velocity']==600 and movement['gravity_scale']==1)
check('runtime_lighting',all(abs(p['auto_exposure_bias']-.25)<.01 and p['film_grain_intensity']==0 and p['bloom_intensity']<.21 and p['lumen_final_gather_quality']>=5 for p in run['defaults']['postprocess']))
check('hardware_lumen_and_virtual_textures',all(run['defaults']['rendering'][n]==1 for n in ['r.Lumen.HardwareRayTracing','r.VirtualTextures']))

# Diagnostic only: planted-foot motion varies through retargeting and crossfades.
for name,a,b in [('walk',6.7,8.8),('jog',9.8,11.8),('back',14.8,16.8),('left',17.8,19.8),('right',20.8,22.8)]:
    group=rows(a,b);slips=[]
    for foot in ['foot_l','foot_r']:
        low=min(r['bones'][foot][2] for r in group)
        for x,y in zip(group,group[1:]):
            dt=y['t']-x['t'];p=x['bones'][foot];q=y['bones'][foot]
            if not 0<dt<.16 or max(p[2],q[2])>low+2 or abs(q[2]-p[2])/dt>35:continue
            def world(r):
                b=r['bones'][foot];angle=math.radians(r['yaw']-90)
                return (r['location'][0]+math.cos(angle)*b[0]-math.sin(angle)*b[1],r['location'][1]+math.sin(angle)*b[0]+math.cos(angle)*b[1])
            slips.append(math.dist(world(x),world(y))/dt)
    metrics[name+'_contact_slip_cm_s_median']=statistics.median(slips) if slips else None
    metrics[name+'_contact_pairs']=len(slips)
result={'passed':all(checks.values()),'checks':checks,'metrics':metrics,'limits':['Rendered editor test with injected controller input; owner controller feel and visual acceptance remain separate.','Foot-slip measurements are diagnostics, not a claim of cinematic foot locking.','No packaged, long-session or representative performance acceptance.']}
source.with_name('assessment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
sys.exit(0 if result['passed'] else 1)
