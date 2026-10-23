"""Controller entry, drive and exit regression with Vexa appearance inspection."""
import json,time,traceback,math
from pathlib import Path
import unreal as u

out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'HoverPrototype/MotionRevision/Vehicles'
out.mkdir(parents=True,exist_ok=True)
report={'samples':[],'events':[],'errors':[],'checks':{}}
state={'start':time.monotonic(),'requested':False,'isolated':False,'busy':False,'index':0}
axes={};buttons={}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
u.SystemLibrary.execute_console_command(world,'t.MaxFPS 60')

def axis(pc,name,value):
    axes[name]=value;u.HoverAuthoring.test_key(pc,name,value,True)
def key(pc,name,value):
    buttons[name]=value;u.HoverAuthoring.test_key(pc,name,value,False)
def setup(pc):
    w=u.HoverAuthoring.get_playtest_world()
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombieRange):a.set_actor_tick_enabled(False)
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie):a.destroy_actor()
    u.SystemLibrary.execute_console_command(w,'HoverView',pc)
def near(pc,truck=False):
    p=pc.get_controlled_pawn();assert isinstance(p,u.HoverPilot),'Vexa not controlled before entry'
    v=pc.get_test_truck() if truck else pc.get_test_bike();assert v
    p.set_actor_location(v.get_actor_location()+u.Vector(0,-270 if truck else -220,180 if truck else 130),False,True)
    p.character_movement.stop_movement_immediately()
def sample(pc,label):
    p=pc.get_controlled_pawn()
    row={'label':label,'class':p.get_class().get_name(),'location':list(p.get_actor_location().to_tuple()),'velocity':list(p.get_velocity().to_tuple()),'vexa':isinstance(p,u.HoverPilot)}
    if p==pc.get_test_bike():
        move=p.get_component_by_class(u.ChaosWheeledVehicleMovementComponent)
        row.update({'speed':move.get_forward_speed(),'gear':move.get_current_gear(),'throttle':move.get_throttle_input(),'brake':move.get_brake_input(),'camera_yaw':p.get_editor_property('SpringArm').get_editor_property('relative_rotation').yaw,'boost':p.get_editor_property('BoostActivated')})
        driver=p.get_editor_property('PlayerCharacterRef');data=u.load_asset('/Game/HoverPrototype/DA_HoverPilot')
        row['driver_parts']=[]
        for part in data.get_editor_property('body_parts'):
            c=next(c for c in driver.get_components_by_class(u.SkeletalMeshComponent) if c.get_editor_property('skeletal_mesh_asset')==part.get_editor_property('mesh'))
            row['driver_parts'].append({'name':str(part.get_editor_property('name')),'morphs_match':all(abs(c.get_morph_target(n)-v)<.0001 for n,v in part.get_editor_property('morphs').items()),'materials_match':all(c.get_material(i)==m for i,m in enumerate(part.get_editor_property('materials'))),'contact_shadow':c.get_editor_property('cast_contact_shadow')})
    report['samples'].append(row)
    u.HoverAuthoring.capture_world_frame(str(out/(label+'.png')))
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
def finish():
    samples={r['label']:r for r in report['samples']}
    if not report['errors']:
        for vehicle in ['bike','truck']:
            a=samples[vehicle+'_mounted'];b=samples[vehicle+'_driven'];c=samples[vehicle+'_exit']
            report['checks'][vehicle+'_entered']=not a['vexa']
            report['checks'][vehicle+'_moved']=math.dist(a['location'],b['location'])>200
            report['checks'][vehicle+'_controller_exit']=c['vexa']
        report['checks']['bike_vexa_defaults']=all(r['morphs_match'] and r['materials_match'] and r['contact_shadow'] for r in samples['bike_mounted']['driver_parts'])
    report['passed']=not report['errors'] and all(report['checks'].values()) and len(report['checks'])==7
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
    u.unregister_slate_post_tick_callback(state['handle'])
    u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play()
    state['ending'] = time.monotonic()
    def quit_after_play(dt):
        if u.HoverAuthoring.get_playtest_world() or time.monotonic() - state['ending'] < 3:
            return
        report['shutdown'] = 'Play ended before editor exit'
        (out/'runtime.json').write_text(json.dumps(report,indent=2))
        u.unregister_slate_post_tick_callback(state['exit_handle'])
        u.EditorPythonScripting.set_keep_python_script_alive(False)
        u.SystemLibrary.quit_editor()
    state['exit_handle'] = u.register_slate_post_tick_callback(quit_after_play)

events=[(3,'setup',setup),(4,'near_bike',near),
 (6,'bike_enter',lambda c:key(c,'Gamepad_FaceButton_Left',1)),(7,'bike_enter_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (9,'bike_mounted',lambda c:sample(c,'bike_mounted')),
 (10,'bike_drive',lambda c:axis(c,'Gamepad_RightTriggerAxis',1)),(12,'bike_driven',lambda c:(axis(c,'Gamepad_RightTriggerAxis',0),sample(c,'bike_driven'))),
 (13,'brake',lambda c:axis(c,'Gamepad_LeftTriggerAxis',1)),(14,'braking',lambda c:sample(c,'bike_braking')),
 (17,'reverse',lambda c:sample(c,'bike_reverse')),(18,'release',lambda c:axis(c,'Gamepad_LeftTriggerAxis',0)),
 (19,'look',lambda c:axis(c,'Gamepad_RightX',.5)),(20,'look_sample',lambda c:sample(c,'bike_look_right')),(21,'look_release',lambda c:axis(c,'Gamepad_RightX',0)),
 (22,'boost',lambda c:(key(c,'Gamepad_FaceButton_Right',1),axis(c,'Gamepad_RightTriggerAxis',1))),
 (24,'boost_sample',lambda c:sample(c,'bike_boost')),(25,'boost_stop',lambda c:(key(c,'Gamepad_FaceButton_Right',0),axis(c,'Gamepad_RightTriggerAxis',0))),
 (26,'stop',lambda c:axis(c,'Gamepad_LeftTriggerAxis',1)),(28,'stop_release',lambda c:axis(c,'Gamepad_LeftTriggerAxis',0)),
 (29,'bike_exit',lambda c:key(c,'Gamepad_FaceButton_Left',1)),(30,'bike_exit_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (32,'bike_returned',lambda c:sample(c,'bike_exit')),(33,'near_truck',lambda c:near(c,True)),
 (35,'truck_enter',lambda c:key(c,'Gamepad_FaceButton_Left',1)),(36,'truck_enter_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (38,'truck_mounted',lambda c:sample(c,'truck_mounted')),
 (39,'truck_drive',lambda c:axis(c,'Gamepad_RightTriggerAxis',1)),(42,'truck_driven',lambda c:(axis(c,'Gamepad_RightTriggerAxis',0),sample(c,'truck_driven'))),
 (42.1,'brake',lambda c:axis(c,'Gamepad_LeftTriggerAxis',1)),(43.5,'brake_release',lambda c:axis(c,'Gamepad_LeftTriggerAxis',0)),
 (44,'truck_exit',lambda c:key(c,'Gamepad_FaceButton_Top',1)),(45,'truck_exit_release',lambda c:key(c,'Gamepad_FaceButton_Top',0)),
 (47,'truck_returned',lambda c:sample(c,'truck_exit')),(48,'done',lambda c:finish())]

def tick(dt):
    if state['busy']:return
    state['busy']=True
    try:
        if time.monotonic()-state['start']>600:raise RuntimeError('Vehicle test timeout')
        if not state['requested']:
            if time.monotonic()-state['start']>10:u.HoverAuthoring.start_playtest();state['requested']=True
            return
        w=u.HoverAuthoring.get_playtest_world()
        if not w:return
        pc=u.GameplayStatics.get_player_controller(w,0)
        if not pc or not pc.get_controlled_pawn():return
        if not state['isolated']:
            u.HoverAuthoring.isolate_test_input(pc);state['isolated']=True
            for n in ['Gamepad_LeftX','Gamepad_LeftY','Gamepad_RightX','Gamepad_RightY','Gamepad_LeftTriggerAxis','Gamepad_RightTriggerAxis']:axis(pc,n,0)
        for n,v in axes.items():u.HoverAuthoring.test_key(pc,n,v,True)
        for n,v in buttons.items():u.HoverAuthoring.test_key(pc,n,v,False)
        t=u.GameplayStatics.get_time_seconds(w)
        while state['index']<len(events) and t>=events[state['index']][0]:
            _,label,fn=events[state['index']];state['index']+=1;report['events'].append({'label':label,'t':t});fn(pc)
    except Exception:report['errors'].append(traceback.format_exc());print(report['errors'][-1]);finish()
    finally:state['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle']=u.register_slate_post_tick_callback(tick)
