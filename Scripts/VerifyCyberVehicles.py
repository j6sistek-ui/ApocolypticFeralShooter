"""Cyber-only vehicle targeting, spawn safety, and Slate HUD review."""
import unreal as u,json,time,traceback
from pathlib import Path
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'Automation/ZombieEngine/vehicles';out.mkdir(parents=True,exist_ok=True)
r={'errors':[],'samples':[],'spawns':[]};s={'start':time.monotonic(),'play':False,'busy':False,'index':0,'end':None,'seen':set()};buttons={}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/HoverPrototype/Maps/L_CyberCity')
def key(pc,k,v):buttons[k]=v;u.HoverAuthoring.test_key(pc,k,v,False)
def near(pc,truck=False):
 p=pc.get_controlled_pawn();assert isinstance(p,u.HoverPilot)
 v=pc.get_test_truck() if truck else pc.get_test_bike()
 p.set_actor_location(v.get_actor_location()+u.Vector(0,-270 if truck else -220,180 if truck else 130),False,True)
 p.character_movement.stop_movement_immediately()
def sample(pc,label,expected):
 w=u.HoverAuthoring.get_playtest_world();p=pc.get_controlled_pawn();gm=u.GameplayStatics.get_game_mode(w)
 targets=[]
 for z in u.GameplayStatics.get_all_actors_of_class(w,u.HoverCyberZombie):
  if z.get_editor_property('is_dead'):continue
  ai=z.get_controller();bb=ai.get_component_by_class(u.BlackboardComponent) if ai else None
  targets.append(bb.get_value_as_object('TargetEnemy')==p if bb else False)
 row={'label':label,'pawn':p.get_class().get_name(),'wave_hud':gm.is_wave_hud_visible(),'damage':u.GameplayStatics.apply_damage(p,9999,pc,p,u.DamageType),'targets':targets,'wave':gm.get_current_wave(),'active_points':gm.get_active_spawn_count()}
 r['samples'].append(row)
 assert expected in row['pawn'],row
 assert row['wave_hud'] and row['damage']==0 and all(targets),row
 u.HoverAuthoring.capture_playtest(str(out/(label+'_ui.png')))
 u.HoverAuthoring.capture_world_frame(str(out/(label+'.png')))
def finish():
 (out/'runtime.json').write_text(json.dumps(r,indent=2));u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play();s['end']=time.monotonic()
events=[(8,'foot',lambda c:sample(c,'foot','Vexa')),(9,'near_bike',near),
 (10,'enter_bike',lambda c:key(c,'Gamepad_FaceButton_Left',1)),(11,'release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (14,'bike',lambda c:sample(c,'bike','Hoverbike')),(16,'exit_bike',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (17,'release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),(20,'after_bike',lambda c:sample(c,'after_bike','Vexa')),
 (22,'near_truck',lambda c:near(c,True)),(23,'enter_truck',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (24,'release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),(27,'truck',lambda c:sample(c,'truck','Crossroad')),
 (29,'exit_truck',lambda c:key(c,'Gamepad_FaceButton_Top',1)),(30,'release',lambda c:key(c,'Gamepad_FaceButton_Top',0)),
 (33,'after_truck',lambda c:sample(c,'after_truck','Vexa')),(35,'finish',lambda c:finish())]
def tick(dt):
 if s['busy']:return
 s['busy']=True
 try:
  if s['end']:
   if time.monotonic()-s['end']>3 and not u.HoverAuthoring.get_playtest_world():u.unregister_slate_post_tick_callback(s['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
   return
  if time.monotonic()-s['start']>400:raise RuntimeError('Vehicle test timeout')
  if not s['play']:
   if time.monotonic()-s['start']>7:u.HoverAuthoring.start_playtest();s['play']=True
   return
  w=u.HoverAuthoring.get_playtest_world()
  if not w:return
  pc=u.GameplayStatics.get_player_controller(w,0)
  if not pc or not pc.get_controlled_pawn():return
  if not s.get('isolated'):u.HoverAuthoring.isolate_test_input(pc);s['isolated']=True
  for k,v in buttons.items():u.HoverAuthoring.test_key(pc,k,v,False)
  t=u.GameplayStatics.get_time_seconds(w);p=pc.get_controlled_pawn()
  for z in u.GameplayStatics.get_all_actors_of_class(w,u.HoverCyberZombie):
   if z.get_name() not in s['seen']:
    s['seen'].add(z.get_name());delta=z.get_actor_location()-p.get_actor_location();d=(delta.x**2+delta.y**2)**.5
    r['spawns'].append({'time':t,'name':z.get_name(),'distance_to_player':d,'location':list(z.get_actor_location().to_tuple())})
    assert d>=1375,'Spawn appeared beside player'
  while s['index']<len(events) and t>=events[s['index']][0]:
   _,label,fn=events[s['index']];s['index']+=1;fn(pc)
 except Exception:r['errors'].append(traceback.format_exc());finish()
 finally:s['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True);s['handle']=u.register_slate_post_tick_callback(tick)
