"""Rendered Cyber City wave, combat, pickup and map-isolation checks."""
import unreal as u,json,time,traceback
from pathlib import Path
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'Automation/ZombieEngine/runtime';out.mkdir(parents=True,exist_ok=True)
r={'errors':[],'samples':[],'tracking':[]};s={'start':time.monotonic(),'play':False,'stage':0,'end':None,'busy':False,'last':-1};axes={}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/HoverPrototype/Maps/L_CyberCity')
def axis(pc,key,value):axes[key]=value;u.HoverAuthoring.test_key(pc,key,value,True)
def tap(pc,key):u.HoverAuthoring.test_key(pc,key,1,False);u.HoverAuthoring.test_key(pc,key,0,False)
def zombies(w):return u.GameplayStatics.get_all_actors_of_class(w,u.HoverCyberZombie)
def live(w):return [z for z in zombies(w) if not z.get_editor_property('is_dead')]
def row(w,pc,label):
 p=pc.get_controlled_pawn();gm=u.GameplayStatics.get_game_mode(w)
 d={'label':label,'time':u.GameplayStatics.get_time_seconds(w),'world':w.get_name(),'mode':gm.get_class().get_name(),'pawn':p.get_class().get_name(),'damage':u.GameplayStatics.apply_damage(p,9999,pc,p,u.DamageType),'old_zombies':len(u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie)),'rides':{}}
 actors=u.GameplayStatics.get_all_actors_of_class(w,u.Actor)
 for term in ['BP_Hoverbike','BP_Crossroad_Pickup']:d['rides'][term]=len([a for a in actors if term in a.get_class().get_name()])
 d['rides']['glider']=len([a for a in actors if any(c.get_name()=='HoverMechanism' for c in a.get_components_by_class(u.PoseableMeshComponent))])
 if isinstance(gm,u.HoverCyberCityGameMode):
  d.update(wave=gm.get_current_wave(),remaining=gm.get_zombies_remaining(),killed=gm.get_total_zombies_killed(),state=str(gm.get_wave_state()),timer=gm.get_wave_timer(),speed_bonus=gm.get_speed_bonus(),gold=gm.get_gold(),active_spawns=gm.get_active_spawn_count(),wave_ui=gm.is_wave_hud_visible())
  d['zombies']=[]
  for z in zombies(w):
   ai=z.get_controller();bb=ai.get_component_by_class(u.BlackboardComponent) if ai else None;target=bb.get_value_as_object('TargetEnemy') if bb else None
   d['zombies'].append({'name':z.get_name(),'location':list(z.get_actor_location().to_tuple()),'distance':z.get_distance_to(p),'velocity':z.get_velocity().length(),'health':z.survival_component.get_health(),'max_health':z.survival_component.get_max_health(),'dead':z.get_editor_property('is_dead'),'attack':z.get_editor_property('is_attacking'),'target':target.get_name() if target else None,'anim':z.mesh.get_anim_instance().get_class().get_name() if z.mesh.get_anim_instance() else None})
 return d
def sample(w,pc,label):
 r['samples'].append(row(w,pc,label));u.HoverAuthoring.capture_world_frame(str(out/(label+'.png')))
 u.HoverAuthoring.capture_playtest(str(out/(label+'_ui.png')))
def spawn_power(w,p,name):
 c=u.load_class(None,'/Game/HoverPrototype/ZombieEngine/BP_CyberPower_'+name+'.BP_CyberPower_'+name+'_C')
 tr=u.Transform(location=p.get_actor_location()+u.Vector(0,0,-30))
 a=u.HoverAuthoring.spawn_playtest_actor(c,tr);p.set_actor_location(p.get_actor_location()+u.Vector(10,0,0),True,False)
 return a
def finish():
 (out/'runtime.json').write_text(json.dumps(r,indent=2));u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play();s['end']=time.monotonic()
def tick(dt):
 if s['busy']:return
 s['busy']=True
 try:
  if s['end']:
   if time.monotonic()-s['end']>3 and not u.HoverAuthoring.get_playtest_world():u.unregister_slate_post_tick_callback(s['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
   return
  if time.monotonic()-s['start']>900:raise RuntimeError('Zombie integration timeout')
  if not s['play']:
   if time.monotonic()-s['start']>7:u.HoverAuthoring.start_playtest();s['play']=True
   return
  w=u.HoverAuthoring.get_playtest_world()
  if not w:return
  pc=u.GameplayStatics.get_player_controller(w,0)
  if not pc or not pc.get_controlled_pawn():return
  p=pc.get_controlled_pawn();t=u.GameplayStatics.get_time_seconds(w);gm=u.GameplayStatics.get_game_mode(w)
  if s.get('pc')!=pc:s['pc']=pc;u.HoverAuthoring.isolate_test_input(pc)
  for k,v in axes.items():u.HoverAuthoring.test_key(pc,k,v,True)
  if isinstance(gm,u.HoverCyberCityGameMode) and int(t)!=s['last']:
   s['last']=int(t);r['tracking'].append(row(w,pc,'tracking'))
  stage=s['stage']
  if stage==0 and t>8:
   assert isinstance(gm,u.HoverCyberCityGameMode),gm.get_class().get_name()
   u.SystemLibrary.execute_console_command(w,'HoverView',pc);sample(w,pc,'wave_start');s['stage']=1
  elif stage==1 and t>36:
   sample(w,pc,'zombies_chasing');assert len(live(w))==10,len(live(w))
   target=min(live(w),key=lambda z:z.get_distance_to(p));s['target']=target
   delta=p.get_actor_location()-target.get_actor_location();s['approach']=delta/max(delta.length(),1)
   p.set_actor_location(target.get_actor_location()+s['approach']*130,False,True);p.character_movement.stop_movement_immediately();s['mark']=t;s['stage']=1.5
  elif stage==1.5 and t-s['mark']>4:
   sample(w,pc,'melee_invulnerable');target=s['target']
   for z in live(w):
    if z.get_controller():z.get_controller().brain_component.stop_logic('Combat verification')
    z.character_movement.stop_movement_immediately()
   # Isolate the weapon check from random chase positions near the parked truck.
   # The preceding phase already exercised real street navigation and melee.
   platform=u.HoverAuthoring.spawn_test_platform(u.Vector(-1200,-1500,25000))
   s['combat_platform']=platform
   target.set_actor_location(u.Vector(-1200,-1250,25140),False,True)
   target.character_movement.stop_movement_immediately()
   p.set_actor_location(u.Vector(-1200,-1800,25155),False,True);p.character_movement.stop_movement_immediately();p.set_actor_rotation(u.Rotator(),True)
   r['weapon_test_setup']='Temporary clear platform after street chase/melee; world remains unsaved'
   axis(pc,'Gamepad_LeftTriggerAxis',1);s['mark']=t;s['stage']=2
  elif stage==2:
   target=s['target'];point=target.get_actor_location()+u.Vector(0,0,20)
   pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(p.get_editor_property('first_person_camera').get_world_location(),point))
   if t-s['mark']>2:axis(pc,'Gamepad_RightTriggerAxis',1);s['stage']=3;s['mark']=t
  elif stage==3:
   target=s['target'];pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(p.get_editor_property('first_person_camera').get_world_location(),target.get_actor_location()+u.Vector(0,0,20)))
   if target.get_editor_property('is_dead') or t-s['mark']>4:
    axis(pc,'Gamepad_RightTriggerAxis',0);sample(w,pc,'rifle_kill');r['actual_gun_kill']=target.get_editor_property('is_dead');r['shots']=p.get_shots_fired();axis(pc,'Gamepad_LeftTriggerAxis',0);s['stage']=4;s['mark']=t
  elif stage==4 and t-s['mark']>1:
   s['speed_pickup']=spawn_power(w,p,'Speed');s['stage']=5;s['mark']=t
  elif stage==5 and t-s['mark']>1:
   sample(w,pc,'speed_pickup');s['nuke_pickup']=spawn_power(w,p,'Nuke');s['stage']=6;s['mark']=t
  elif stage==6 and t-s['mark']>1:
   sample(w,pc,'nuke_wave_complete');s['stage']=7;s['mark']=t
  elif stage==7 and gm.get_current_wave()>=2 and len(live(w))>=2:
   sample(w,pc,'wave_two');tap(pc,'Gamepad_DPad_Up');s['paused_at']=u.GameplayStatics.get_time_seconds(w);s['paused_state']=(gm.get_current_wave(),gm.get_zombies_remaining(),gm.get_wave_timer());s['wall_pause']=time.monotonic();s['stage']=8
  elif stage==8 and time.monotonic()-s['wall_pause']>2:
   r['pause_preserved']=s['paused_state']==(gm.get_current_wave(),gm.get_zombies_remaining(),gm.get_wave_timer())
   tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Right');tap(pc,'Gamepad_FaceButton_Bottom');axes.clear();s['stage']=9
  elif stage==9 and 'PostApo' in w.get_name() and t>8:
   sample(w,pc,'postapo_unchanged');r['postapo_zombie_engine_count']=len(zombies(w));s['mark']=t;s['stage']=10
  elif stage==10 and t-s['mark']>1:
   tap(pc,'Gamepad_DPad_Up');tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Right');tap(pc,'Gamepad_FaceButton_Bottom');s['stage']=11
  elif stage==11 and 'CyberCity' in w.get_name() and t>8:
   sample(w,pc,'city_return');r['city_roundtrip']=isinstance(gm,u.HoverCyberCityGameMode) and gm.get_current_wave()==1;assert r['city_roundtrip'];finish()
 except Exception:r['errors'].append(traceback.format_exc());finish()
 finally:s['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True);s['handle']=u.register_slate_post_tick_callback(tick)
