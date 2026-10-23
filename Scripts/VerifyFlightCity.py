"""Physical-path regression in an unsaved test world, not owner acceptance."""
import unreal as u,json,time,traceback,math
from pathlib import Path
out=Path(u.Paths.project_saved_dir())/'Automation/FlightCity/motion_final';out.mkdir(parents=True,exist_ok=True)
r={'samples':[],'curves':[],'errors':[]};s={'start':time.monotonic(),'play':False,'index':0,'end':None,'busy':False,'last':0,'frame':0};axes={}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')
w=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world();w.get_world_settings().set_editor_property('default_game_mode',u.HoverGameMode)
for cmd in ['t.MaxFPS 60','t.IdleWhenNotForeground 0','Slate.bAllowThrottling 0']:u.SystemLibrary.execute_console_command(w,cmd)
def axis(pc,n,v):axes[n]=v;u.HoverAuthoring.test_key(pc,n,v,True)
def key(pc,n,v):u.HoverAuthoring.test_key(pc,n,v,False)
def command(pc,c):u.SystemLibrary.execute_console_command(u.HoverAuthoring.get_playtest_world(),c,pc)
def board():
 for a in u.GameplayStatics.get_all_actors_of_class(u.HoverAuthoring.get_playtest_world(),u.Actor):
  if any(c.get_name()=='HoverMechanism' for c in a.get_components_by_class(u.PoseableMeshComponent)):return a
 raise RuntimeError('Missing board')
def reset(pc):
 p=pc.get_controlled_pawn();p.character_movement.stop_movement_immediately();p.set_actor_location(s['origin'],False,True);p.set_actor_rotation(u.Rotator(),True);pc.set_control_rotation(u.Rotator(pitch=-8))
def setup(pc):
 w=u.HoverAuthoring.get_playtest_world();p=pc.get_controlled_pawn()
 for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombieRange):a.set_actor_tick_enabled(False)
 for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie):a.destroy_actor()
 s['origin']=p.get_actor_location()+u.Vector(0,0,6000)
 f=u.HoverAuthoring.spawn_test_platform(s['origin']-u.Vector(0,0,150));f.set_actor_scale3d(u.Vector(1000,1000,1));s['floor']=s['origin'].z-100
 reset(pc);u.HoverAuthoring.set_playtest_fixed_step(True);command(pc,'HoverView');p.get_editor_property('review_arm').target_arm_length=290
def row(pc):
 p=pc.get_controlled_pawn();m=p.mesh;bp=m.get_post_process_instance();v=p.get_velocity();loc=p.get_actor_location()
 d={'t':u.GameplayStatics.get_time_seconds(u.HoverAuthoring.get_playtest_world()),'speed':math.hypot(v.x,v.y),'velocity':list(v.to_tuple()),'location':list(loc.to_tuple()),'yaw':p.get_actor_rotation().yaw,'height':p.capsule_component.get_unscaled_capsule_half_height(),'max_speed':p.character_movement.max_walk_speed,'mode':str(p.character_movement.movement_mode),'feet':[m.get_socket_location(b).z-s.get('floor',0) for b in ['foot_l','foot_r']],'mounted':p.is_mounted(),'bank':p.get_board_bank(),'pitch':p.get_board_pitch(),'match':u.ClsComparisonAuthoring.motion_matching_result(p)}
 if bp:
  bp.measure_rendered_offsets();d['spring_bones']=[str(x) for x in bp.get_editor_property('evaluated_bones')];d['spring_offsets']=[list(x.to_tuple()) for x in bp.get_editor_property('measured_offsets')];d['alpha']=bp.get_editor_property('physics_alpha')
 return d
def sample(pc,label):
 d=row(pc);d['label']=label;r['samples'].append(d);u.HoverAuthoring.capture_world_frame(str(out/(label+'.png')))
def mount_setup(pc):
 axis(pc,'Gamepad_LeftY',0);axis(pc,'Gamepad_LeftX',0);axis(pc,'Gamepad_RightX',0);key(pc,'Gamepad_LeftThumbstick',0);reset(pc)
 b=board();root=b.root_component;root.set_simulate_physics(False);b.set_actor_location(s['origin']+u.Vector(150,0,-73),False,True);b.set_actor_rotation(u.Rotator(yaw=-90),True);root.set_simulate_physics(True)
def hop(pc):r['hop_start']=pc.get_controlled_pawn().get_actor_location().z;key(pc,'Gamepad_FaceButton_Bottom',1)
def bank_start(pc,enhanced):
 p=pc.get_controlled_pawn();p.set_actor_location(s['origin']+u.Vector(0,0,3000),False,True);p.set_actor_rotation(u.Rotator(),True);p.character_movement.velocity=u.Vector(2160,0,0)
 axis(pc,'Gamepad_LeftY',0);axis(pc,'Gamepad_LeftX',1);axis(pc,'Gamepad_RightTriggerAxis',1);key(pc,'Gamepad_LeftShoulder',int(enhanced))
events=[(3,setup),(5,lambda c:sample(c,'idle')),(6,lambda c:axis(c,'Gamepad_LeftY',1)),(8,lambda c:sample(c,'walk')),
 (9,lambda c:key(c,'Gamepad_LeftThumbstick',1)),(11,lambda c:sample(c,'run_straight')),
 (12,lambda c:(axis(c,'Gamepad_LeftY',.707107),axis(c,'Gamepad_LeftX',.707107))),(14,lambda c:sample(c,'run_diagonal')),
 (15,lambda c:(axis(c,'Gamepad_LeftY',1),axis(c,'Gamepad_LeftX',0),axis(c,'Gamepad_RightX',.6))),(18,lambda c:sample(c,'run_camera_turn')),
 (19,lambda c:(axis(c,'Gamepad_RightX',0),key(c,'Gamepad_FaceButton_Right',1))),(19.2,lambda c:sample(c,'crouch_transition')),(20,lambda c:sample(c,'crouch')),
 (21,lambda c:key(c,'Gamepad_FaceButton_Right',0)),(22,lambda c:sample(c,'stand_after_crouch')),
 (23,lambda c:key(c,'Gamepad_FaceButton_Bottom',1)),(23.1,lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),(23.4,lambda c:sample(c,'ground_jump')),
 (26,mount_setup),(28,lambda c:key(c,'Gamepad_FaceButton_Left',1)),(29,lambda c:key(c,'Gamepad_FaceButton_Left',0)),(31,lambda c:sample(c,'mounted')),
 (32,lambda c:axis(c,'Gamepad_RightTriggerAxis',1)),(35,lambda c:sample(c,'thrust')),(36,hop),(36.1,lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),(36.43,lambda c:sample(c,'hop_peak')),(38,lambda c:sample(c,'hop_settle')),
 (39,lambda c:axis(c,'Gamepad_LeftY',1)),(41,lambda c:sample(c,'climb')),(42,lambda c:axis(c,'Gamepad_LeftY',-1)),(44,lambda c:sample(c,'dive')),
 (45,lambda c:axis(c,'Gamepad_LeftY',0)),(47,lambda c:sample(c,'hold')),(48,lambda c:bank_start(c,False)),(51,lambda c:sample(c,'bank_normal')),
 (52,lambda c:bank_start(c,True)),(55,lambda c:sample(c,'bank_enhanced')),(56,lambda c:(axis(c,'Gamepad_LeftX',0),axis(c,'Gamepad_RightTriggerAxis',0),key(c,'Gamepad_LeftShoulder',0))),
 (60,lambda c:sample(c,'quiet_flight')),(61,lambda c:finish())]
def finish():
 u.HoverAuthoring.set_playtest_fixed_step(False);(out/'runtime.json').write_text(json.dumps(r,indent=2));u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play();s['end']=time.monotonic()
def tick(dt):
 if s['busy']:return
 s['busy']=True
 try:
  if s['end']:
   if time.monotonic()-s['end']>3 and not u.HoverAuthoring.get_playtest_world():u.unregister_slate_post_tick_callback(s['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
   return
  if time.monotonic()-s['start']>600:raise RuntimeError('Motion timeout')
  if not s['play']:
   if time.monotonic()-s['start']>7:u.HoverAuthoring.start_playtest();s['play']=True
   return
  w=u.HoverAuthoring.get_playtest_world()
  if not w:return
  pc=u.GameplayStatics.get_player_controller(w,0)
  if not pc or not pc.get_controlled_pawn():return
  if not s.get('isolated'):u.HoverAuthoring.isolate_test_input(pc);s['isolated']=True
  for n,v in axes.items():u.HoverAuthoring.test_key(pc,n,v,True)
  t=u.GameplayStatics.get_time_seconds(w)
  if s['index']<len(events) and t>=events[s['index']][0]:events[s['index']][1](pc);s['index']+=1
  if s['index'] and t-s['last']>.016 and not s['end']:s['last']=t;r['curves'].append(row(pc))
  if not s['end'] and any(lo<t<hi for lo,hi in [(7,8),(10,11),(19,22),(23,24.5),(34,35),(36,38),(40,41),(43,44),(57,60)]):
   u.HoverAuthoring.capture_world_frame(str(out/('%04d.png'%s['frame'])));s['frame']+=1
 except Exception:r['errors'].append(traceback.format_exc());finish()
 finally:s['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True);s['handle']=u.register_slate_post_tick_callback(tick)
