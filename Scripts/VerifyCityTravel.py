import unreal as u,json,time,traceback
from pathlib import Path
out=Path(u.Paths.project_saved_dir())/'Automation/FlightCity/city_runtime';out.mkdir(parents=True,exist_ok=True)
r={'errors':[],'samples':[]};s={'start':time.monotonic(),'play':False,'stage':0,'end':None,'busy':False,'pc':None}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')
def key(pc,n,v):u.HoverAuthoring.test_key(pc,n,v,False)
def tap(pc,n):key(pc,n,1);key(pc,n,0)
def sample(pc,name):
 w=u.HoverAuthoring.get_playtest_world();p=pc.get_controlled_pawn();actors=u.GameplayStatics.get_all_actors_of_class(w,u.Actor)
 d={'label':name,'world':w.get_name(),'pawn':p.get_class().get_name(),'location':list(p.get_actor_location().to_tuple()),'velocity':list(p.get_velocity().to_tuple()),'damage':u.GameplayStatics.apply_damage(p,9999,pc,p,u.DamageType),'rides':{},'zombies':len(u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie))}
 for term in ['BP_Hoverbike','BP_Crossroad_Pickup']:
  d['rides'][term]=[{'class':a.get_class().get_name(),'location':list(a.get_actor_location().to_tuple())} for a in actors if term in a.get_class().get_name()]
 d['rides']['glider']=len([a for a in actors if any(c.get_name()=='HoverMechanism' for c in a.get_components_by_class(u.PoseableMeshComponent))])
 r['samples'].append(d);u.HoverAuthoring.capture_world_frame(str(out/(name+'.png')))
def menu(pc):
 tap(pc,'Gamepad_DPad_Up');tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Down');tap(pc,'Gamepad_DPad_Right')
def finish():
 (out/'runtime.json').write_text(json.dumps(r,indent=2));u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play();s['end']=time.monotonic()
def tick(dt):
 if s['busy']:return
 s['busy']=True
 try:
  if s['end']:
   if time.monotonic()-s['end']>3 and not u.HoverAuthoring.get_playtest_world():u.unregister_slate_post_tick_callback(s['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
   return
  if time.monotonic()-s['start']>900:raise RuntimeError('City travel timeout')
  if not s['play']:
   if time.monotonic()-s['start']>7:u.HoverAuthoring.start_playtest();s['play']=True
   return
  w=u.HoverAuthoring.get_playtest_world()
  if not w:return
  pc=u.GameplayStatics.get_player_controller(w,0)
  if not pc or not pc.get_controlled_pawn():return
  if s['pc']!=pc:s['pc']=pc;u.HoverAuthoring.isolate_test_input(pc)
  t=u.GameplayStatics.get_time_seconds(w);stage=s['stage'];city='Cyber' in w.get_name()
  if stage==0 and t>6:
   u.SystemLibrary.execute_console_command(w,'HoverView',pc);sample(pc,'postapo_initial');menu(pc);s['menu_time']=time.monotonic();s['stage']=1
  elif stage==1 and time.monotonic()-s['menu_time']>1:
   u.HoverAuthoring.capture_world_frame(str(out/'select_city.png'));tap(pc,'Gamepad_FaceButton_Bottom');s['stage']=2
  elif stage==2 and city and t>14:
   u.SystemLibrary.execute_console_command(w,'HoverView',pc);pc.set_control_rotation(u.Rotator(pitch=-8,yaw=0));sample(pc,'city_street');s['stage']=3
  elif stage==3 and city and t>18:
   pc.set_control_rotation(u.Rotator(pitch=-8,yaw=180));sample(pc,'city_reverse');s['stage']=4
  elif stage==4 and city and t>21:
   menu(pc);s['menu_time']=time.monotonic();s['stage']=5
  elif stage==5 and time.monotonic()-s['menu_time']>1:
   u.HoverAuthoring.capture_world_frame(str(out/'select_postapo.png'));tap(pc,'Gamepad_FaceButton_Bottom');s['stage']=6
  elif stage==6 and not city and t>8:sample(pc,'postapo_return');finish()
 except Exception:r['errors'].append(traceback.format_exc());finish()
 finally:s['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True);s['handle']=u.register_slate_post_tick_callback(tick)
