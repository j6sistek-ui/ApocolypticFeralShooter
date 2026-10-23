"""Rendered on-foot motion and appearance review in an unsaved Play world."""
import json, time, traceback
from pathlib import Path
import unreal as u

out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'HoverPrototype/CharacterReview'
out.mkdir(parents=True,exist_ok=True)
report={'samples':[],'curves':[],'errors':[],'environment':[],'frames':[]}
(out/'runtime.json').write_text(json.dumps(report,indent=2))
state={'start':time.monotonic(),'requested':False,'index':0,'busy':False,'last':-1,'camera':None,'isolated':False,'frame_time':0,'frame':0}
axes={};buttons={}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
for actor in u.GameplayStatics.get_all_actors_of_class(world,u.Actor):
    for comp in actor.get_components_by_class(u.LightComponentBase):
        row={'actor':actor.get_name(),'type':comp.get_class().get_name()}
        for name in ['intensity','light_color','indirect_lighting_intensity','volumetric_scattering_intensity','cast_shadows']:
            try:row[name]=str(comp.get_editor_property(name))
            except Exception:pass
        report['environment'].append(row)
    if isinstance(actor,u.PostProcessVolume):
        st=actor.get_editor_property('settings');row={'actor':actor.get_name()}
        for name in ['auto_exposure_bias','auto_exposure_min_brightness','auto_exposure_max_brightness','auto_exposure_method','bloom_intensity','dynamic_global_illumination_method','reflection_method']:
            try:row[name]=str(st.get_editor_property(name))
            except Exception:pass
        report['environment'].append(row)
for cmd in ['r.ScreenPercentage 100','t.MaxFPS 60','t.IdleWhenNotForeground 0','Slate.bAllowThrottling 0']:
    u.SystemLibrary.execute_console_command(world,cmd)
def key(pc,name,value):
    buttons[name]=value;u.HoverAuthoring.test_key(pc,name,value,False)
def axis(pc,name,value):
    axes[name]=value;u.HoverAuthoring.test_key(pc,name,value,True)
def pose(pc):
    p=pc.get_controlled_pawn();m=p.mesh
    return {'t':u.GameplayStatics.get_time_seconds(u.HoverAuthoring.get_playtest_world()),'location':list(p.get_actor_location().to_tuple()),'velocity':list(p.get_velocity().to_tuple()),'state':list(p.get_locomotion_state().to_tuple()),'yaw':p.get_actor_rotation().yaw,'falling':p.character_movement.is_falling(),'secondary':[list(v.to_tuple()) for v in m.get_anim_instance().get_editor_property('secondary_offsets')],'bones':{b:list(m.get_socket_transform(b,u.RelativeTransformSpace.RTS_COMPONENT).translation.to_tuple()) for b in ['foot_l','foot_r','pelvis','chest_l','chest_r','glute_l','glute_r']}}
def sample(pc,label):
    row=pose(pc);row['label']=label;report['samples'].append(row)
    u.HoverAuthoring.capture_world_frame(str(out/(label+'.png')))
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
def setup(pc):
    w=u.HoverAuthoring.get_playtest_world();p=pc.get_controlled_pawn()
    u.HoverAuthoring.isolate_test_input(pc)
    for n in ['Gamepad_LeftX','Gamepad_LeftY','Gamepad_RightX','Gamepad_RightY','Gamepad_LeftTriggerAxis','Gamepad_RightTriggerAxis']:
        axis(pc,n,0)
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombieRange):a.set_actor_tick_enabled(False)
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie):a.destroy_actor()
    u.SystemLibrary.execute_console_command(w,'HoverView',pc)
    # Above the tallest nearby ruins, so sideways travel measures locomotion rather than wall sliding.
    state['origin']=p.get_actor_location()+u.Vector(0,0,6000)
    floor=u.HoverAuthoring.spawn_test_platform(state['origin']-u.Vector(0,0,150));floor.set_actor_scale3d(u.Vector(70,70,1))
    reset(pc)
    data=u.load_asset('/Game/HoverPrototype/DA_HoverPilot')
    report['defaults']={'parts':[],'movement':{},'rendering':{},'postprocess':[]}
    for name in ['max_walk_speed','max_acceleration','braking_deceleration_walking','ground_friction','jump_z_velocity','gravity_scale']:
        report['defaults']['movement'][name]=p.character_movement.get_editor_property(name)
    components=p.get_components_by_class(u.SkeletalMeshComponent)
    for part in data.get_editor_property('body_parts'):
        component=next(c for c in components if c.get_editor_property('skeletal_mesh_asset')==part.get_editor_property('mesh'))
        morphs=part.get_editor_property('morphs')
        report['defaults']['parts'].append({'name':str(part.get_editor_property('name')),
            'morphs':{str(n):component.get_morph_target(n) for n in morphs},
            'expected_morphs':{str(n):v for n,v in morphs.items()},
            'physics':str(component.get_editor_property('physics_asset_override')),
            'expected_physics':str(part.get_editor_property('physics_override')),
            'contact_shadow':component.get_editor_property('cast_contact_shadow'),
            'materials':[str(component.get_material(i)) for i in range(component.get_num_materials())]})
    for name in ['r.Lumen.HardwareRayTracing','r.VirtualTextures','r.ScreenPercentage']:
        report['defaults']['rendering'][name]=u.SystemLibrary.get_console_variable_float_value(name)
    for actor in u.GameplayStatics.get_all_actors_of_class(w,u.PostProcessVolume):
        st=actor.get_editor_property('settings')
        report['defaults']['postprocess'].append({n:st.get_editor_property(n) for n in ['auto_exposure_bias','bloom_intensity','film_grain_intensity','motion_blur_amount','lumen_final_gather_quality']})
    # Normal player camera stays active for movement validation.
def reset(pc):
    p=pc.get_controlled_pawn();p.set_actor_location(state['origin'],False,True)
    p.character_movement.stop_movement_immediately();pc.set_control_rotation(u.Rotator())
    p.set_actor_rotation(u.Rotator(),True)
def front(pc):
    p=pc.get_controlled_pawn();arm=p.get_editor_property('review_arm')
    arm.set_editor_property('use_pawn_control_rotation',False)
    arm.set_relative_rotation(u.Rotator(pitch=0,yaw=170,roll=0),False,True)
def lighting(pc,legacy):
    w=u.HoverAuthoring.get_playtest_world()
    for actor in u.GameplayStatics.get_all_actors_of_class(w,u.PostProcessVolume):
        st=actor.get_editor_property('settings')
        for n,v in {'auto_exposure_bias':1.35 if legacy else .25,'bloom_intensity':.675 if legacy else .2,'film_grain_intensity':.5 if legacy else 0.}.items():st.set_editor_property(n,v)
        actor.set_editor_property('settings',st)
    for actor in u.GameplayStatics.get_all_actors_of_class(w,u.DirectionalLight):
        c=actor.get_component_by_class(u.DirectionalLightComponent)
        c.set_indirect_lighting_intensity(3. if legacy else 1.)
        c.set_volumetric_scattering_intensity(8. if legacy else 1.)
def finish():
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
    u.unregister_slate_post_tick_callback(state['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
events=[(3,'setup',setup),(5,'idle',lambda c:sample(c,'01_Idle')),
(6,'walk',lambda c:axis(c,'Gamepad_LeftY',.58)),(8,'walk_sample',lambda c:sample(c,'02_Walk')),
(9,'jog',lambda c:axis(c,'Gamepad_LeftY',1)),(11,'jog_sample',lambda c:sample(c,'03_Jog')),
(12,'stop',lambda c:axis(c,'Gamepad_LeftY',0)),(13,'reset',reset),
(14,'back',lambda c:axis(c,'Gamepad_LeftY',-1)),(16,'back_sample',lambda c:sample(c,'04_Backward')),
(17,'left',lambda c:(reset(c),axis(c,'Gamepad_LeftY',0),axis(c,'Gamepad_LeftX',-1))),
(19,'left_sample',lambda c:sample(c,'05_StrafeLeft')),
(20,'right',lambda c:(reset(c),axis(c,'Gamepad_LeftX',1))),
(22,'right_sample',lambda c:sample(c,'06_StrafeRight')),
(23,'stop',lambda c:axis(c,'Gamepad_LeftX',0)),(24,'turn_left',lambda c:axis(c,'Gamepad_RightX',-1)),
(24.5,'turn_left_sample',lambda c:sample(c,'07_TurnLeft')),
(26,'turn_right',lambda c:axis(c,'Gamepad_RightX',1)),
(27,'turn_right_sample',lambda c:sample(c,'08_TurnRight')),
(28,'stop_turn',lambda c:axis(c,'Gamepad_RightX',0)),(30,'reset',reset),
(31,'jump',lambda c:key(c,'Gamepad_FaceButton_Bottom',1)),(31.3,'jump_sample',lambda c:sample(c,'09_Jump')),
(31.4,'release_jump',lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),(31.7,'fall_sample',lambda c:sample(c,'10_Fall')),
(33,'aim',lambda c:axis(c,'Gamepad_LeftTriggerAxis',1)),(34,'aim_sample',lambda c:sample(c,'11_Aim')),
(35,'aim_walk',lambda c:axis(c,'Gamepad_LeftX',.6)),(36,'aim_walk_sample',lambda c:sample(c,'12_AimStrafe')),
(37,'stop',lambda c:(axis(c,'Gamepad_LeftX',0),axis(c,'Gamepad_LeftTriggerAxis',0))),
(38,'front',front),(40,'settled',lambda c:sample(c,'13_Settled')),
(41,'legacy_lighting',lambda c:lighting(c,True)),(44,'legacy_sample',lambda c:sample(c,'14_LightingBefore')),
(45,'balanced_lighting',lambda c:lighting(c,False)),(48,'balanced_sample',lambda c:sample(c,'15_LightingAfter')),
(49,'finish',lambda c:finish())]
def tick(dt):
    if state['busy']:return
    state['busy']=True
    try:
        if time.monotonic()-state['start']>900:raise RuntimeError('Character review timed out')
        if not state['requested']:
            if time.monotonic()-state['start']>10:u.HoverAuthoring.start_playtest();state['requested']=True
            return
        w=u.HoverAuthoring.get_playtest_world()
        if not w:return
        pc=u.GameplayStatics.get_player_controller(w,0)
        if not pc or not isinstance(pc.get_controlled_pawn(),u.HoverPilot):return
        if not state['isolated']:
            u.HoverAuthoring.isolate_test_input(pc);state['isolated']=True
            for n in ['Gamepad_LeftX','Gamepad_LeftY','Gamepad_RightX','Gamepad_RightY','Gamepad_LeftTriggerAxis','Gamepad_RightTriggerAxis']:axis(pc,n,0)
        for n,v in axes.items():u.HoverAuthoring.test_key(pc,n,v,True)
        for n,v in buttons.items():u.HoverAuthoring.test_key(pc,n,v,False)
        t=u.GameplayStatics.get_time_seconds(w)
        if t-state['last']>.05:report['curves'].append(pose(pc));state['last']=t
        if any(a<=t<=b for a,b in [(6,11),(14,22),(24,28),(31,34)]) and t-state['frame_time']>=.125:
            frames=out/'frames';frames.mkdir(exist_ok=True)
            u.HoverAuthoring.capture_world_frame(str(frames/('%04d.png'%state['frame'])))
            report['frames'].append({'file':'frames/%04d.png'%state['frame'],'t':t})
            state['frame']+=1;state['frame_time']=t
        while state['index']<len(events) and t>=events[state['index']][0]:
            _,label,fn=events[state['index']];state['index']+=1;fn(pc)
    except Exception:
        report['errors'].append(traceback.format_exc());print(report['errors'][-1]);finish()
    finally:state['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle']=u.register_slate_post_tick_callback(tick)
