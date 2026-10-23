import unreal as u,json,time,traceback
from pathlib import Path
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/'Automation/ZombieEngine/spawns';out.mkdir(parents=True,exist_ok=True)
r={'errors':[],'points':[]};s={'start':time.monotonic(),'play':False,'stage':0,'busy':False,'end':None}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/HoverPrototype/Maps/L_CyberCity')
def finish():
 (out/'review.json').write_text(json.dumps(r,indent=2));u.get_editor_subsystem(u.LevelEditorSubsystem).editor_request_end_play();s['end']=time.monotonic()
def tick(dt):
 if s['busy']:return
 s['busy']=True
 try:
  if s['end']:
   if time.monotonic()-s['end']>3 and not u.HoverAuthoring.get_playtest_world():u.unregister_slate_post_tick_callback(s['handle']);u.EditorPythonScripting.set_keep_python_script_alive(False);u.SystemLibrary.quit_editor()
   return
  if time.monotonic()-s['start']>400:raise RuntimeError('Spawn review timeout')
  if not s['play']:
   if time.monotonic()-s['start']>7:u.HoverAuthoring.start_playtest();s['play']=True
   return
  w=u.HoverAuthoring.get_playtest_world()
  if not w:return
  pc=u.GameplayStatics.get_player_controller(w,0)
  if not pc or not pc.get_controlled_pawn():return
  u.GameplayStatics.get_game_mode(w).set_actor_tick_enabled(False)
  t=u.GameplayStatics.get_time_seconds(w)
  if s['stage']==0 and t>8:
   u.HoverAuthoring.isolate_test_input(pc);p=pc.get_controlled_pawn();s['player']=p.get_actor_location()
   points=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.Actor) if a.actor_has_tag('AFS_CyberSpawn')]
   s['points']=sorted(points,key=lambda a:a.get_name());s['index']=-1
   tr=u.Transform(location=u.Vector(0,-7000,10000),rotation=u.Rotator(pitch=-55,yaw=90))
   c=u.HoverAuthoring.spawn_playtest_actor(u.CameraActor,tr)
   c.camera_component.set_field_of_view(75);pc.set_view_target_with_blend(c,0);s['camera']=c;s['mark']=t;s['stage']=1
  elif s['stage']==1 and t-s['mark']>2:
   i=s['index'];u.HoverAuthoring.capture_world_frame(str(out/('overview.png' if i<0 else 'spawn_%02d.png'%i)))
   s['index']+=1
   if s['index']>=len(s['points']):finish();return
   a=s['points'][s['index']];loc=a.get_actor_location();p=pc.get_controlled_pawn()
   path=u.HoverAuthoring.find_complete_city_path(w,loc,s['player'])
   r['points'].append({'name':a.get_name(),'location':list(loc.to_tuple()),'distance_to_start':(loc-s['player']).length(),'path_valid':len(path)>1,'path_partial':False if path else True,'path':[list(v.to_tuple()) for v in path]})
   camloc=loc+u.Vector(0,0,130);rot=u.MathLibrary.find_look_at_rotation(camloc,s['player']+u.Vector(0,0,50))
   s['camera'].set_actor_location_and_rotation(camloc,rot,False,True);s['mark']=t
 except Exception:r['errors'].append(traceback.format_exc());finish()
 finally:s['busy']=False
u.EditorPythonScripting.set_keep_python_script_alive(True);s['handle']=u.register_slate_post_tick_callback(tick)
