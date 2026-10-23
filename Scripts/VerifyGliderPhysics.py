"""Rendered editor regression; changes only the unsaved play world. Run via -ExecutePythonScript."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / 'HoverPrototype' / 'PhysicsReview'
out.mkdir(parents=True, exist_ok=True)
report = {'samples': [], 'events': [], 'errors': [], 'curves': []}
(out/'runtime.json').write_text(json.dumps(report,indent=2))
state = {'start': time.monotonic(), 'requested': False, 'index': 0, 'busy': False, 'last_sample': -1}
axes = {}
buttons = {}
u.get_editor_subsystem(u.LevelEditorSubsystem).load_level('/Game/JustBStudios/PostApo/Levels/PostApo')
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
u.SystemLibrary.execute_console_command(world, 'r.ScreenPercentage 100')
u.SystemLibrary.execute_console_command(world, 't.MaxFPS 60')

def key(pc, name, value):
    buttons[name] = value
    u.HoverAuthoring.test_key(pc, name, value, False)

def axis(pc, name, value):
    axes[name] = value
    u.HoverAuthoring.test_key(pc, name, value, True)

def command(pc, value):
    u.SystemLibrary.execute_console_command(u.HoverAuthoring.get_playtest_world(), value, pc)

def board():
    w = u.HoverAuthoring.get_playtest_world()
    for a in u.GameplayStatics.get_all_actors_of_class(w, u.Actor):
        for c in a.get_components_by_class(u.PoseableMeshComponent):
            if c.get_name() == 'HoverMechanism':
                return a, c
    raise RuntimeError('Glider not found')

def sample(pc, label, capture=False):
    p = pc.get_controlled_pawn()
    a, mesh = board()
    row = {'label':label, 'time':u.GameplayStatics.get_time_seconds(u.HoverAuthoring.get_playtest_world()),
           'location':list(p.get_actor_location().to_tuple()), 'velocity':list(p.get_velocity().to_tuple()),
           'mounted':p.is_mounted(), 'can_dismount':p.can_dismount(), 'pitch':p.get_board_pitch(),
           'control_pitch':pc.get_control_rotation().pitch,
           'hold':p.hold_progress(),'prompt':p.get_prompt(),
           'bank':p.get_board_bank(), 'wing':p.get_wing_sweep(), 'boost':p.get_boost_charge(),
           'board_location':list(a.get_actor_location().to_tuple()),
           'board_up':list(mesh.get_up_vector().to_tuple()),
           'board_velocity':list(a.get_editor_property('root_component').get_physics_linear_velocity().to_tuple()),
           'board_physics':a.get_editor_property('root_component').is_simulating_physics(),
           'gun_visible':p.get_editor_property('world_gun').is_visible(), 'shots':p.get_shots_fired(),
           'feet':{b:list(p.mesh.get_socket_location(b).to_tuple()) for b in ['foot_l','foot_r']},
           'pads':{b:list(mesh.get_bone_location_by_name(b,u.BoneSpaces.WORLD_SPACE).to_tuple()) for b in ['foot_contact_L','foot_contact_R']},
           'boosters':[{'active':c.is_active(),'scale':list(c.get_editor_property('relative_scale3d').to_tuple())} for c in a.get_components_by_class(u.NiagaraComponent)]}
    report['samples'].append(row)
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
    if capture:
        u.HoverAuthoring.capture_playtest(str(out/(label+'.png')))

def pitch(pc, angle):
    r=pc.get_control_rotation(); r.pitch=angle; pc.set_control_rotation(r)

def high(pc):
    p=pc.get_controlled_pawn()
    p.set_actor_location(p.get_actor_location()+u.Vector(0,0,6000),False,True)
    p.character_movement.velocity=u.Vector()
    key(pc,'Gamepad_FaceButton_Bottom',1)

def mounted(pc):
    sample(pc,'05_Mounted',True)
    assert pc.get_controlled_pawn().is_mounted(), 'Controller hold did not mount; inspect hold sample before continuing physics tests'

def clear_mount_area(pc):
    # Wandering targets can correctly block the mount sweep. Isolate the flight
    # regression from random AI positions in this unsaved test world only.
    w=u.HoverAuthoring.get_playtest_world()
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombieRange):
        a.set_actor_tick_enabled(False)
    for a in u.GameplayStatics.get_all_actors_of_class(w,u.HoverZombie):
        a.destroy_actor()

def low(pc):
    # A temporary landing pad makes the low/high edge cases repeatable; never saved.
    p=pc.get_controlled_pawn(); a,mesh=board()
    floor=u.HoverAuthoring.spawn_test_platform(p.get_actor_location()-u.Vector(0,0,240))
    assert floor
    p.character_movement.stop_movement_immediately()
    pitch(pc,0)

def finish():
    (out/'runtime.json').write_text(json.dumps(report,indent=2))
    u.unregister_slate_post_tick_callback(state['handle'])
    u.EditorPythonScripting.set_keep_python_script_alive(False)
    u.SystemLibrary.quit_editor()

events=[
 (3,'third_person',lambda c:command(c,'HoverView')),
 (4,'idle',lambda c:sample(c,'01_Grounded_Idle',True)),
 (5,'aim',lambda c:axis(c,'Gamepad_LeftTriggerAxis',1)),
 (6,'aim_sample',lambda c:sample(c,'02_Grounded_Aim',True)),
 (7,'aim_fire',lambda c:axis(c,'Gamepad_RightTriggerAxis',1)),
 (7.3,'aim_fire_stop',lambda c:axis(c,'Gamepad_RightTriggerAxis',0)),
 (8,'aim_fire_sample',lambda c:sample(c,'03_Grounded_AimFire',True)),
 (9,'aim_release',lambda c:axis(c,'Gamepad_LeftTriggerAxis',0)),
 (10,'hipfire',lambda c:axis(c,'Gamepad_RightTriggerAxis',1)),
 (10.05,'muzzle_sample',lambda c:sample(c,'04a_MuzzlePulse',True)),
 (10.5,'hipfire_stop',lambda c:axis(c,'Gamepad_RightTriggerAxis',0)),
 (11,'hipfire_sample',lambda c:sample(c,'04_Hipfire',True)),
 (12,'clear_mount_area',clear_mount_area),
 (13,'mount',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (13.4,'mount_hold',lambda c:sample(c,'04b_MountHold')),
 (14,'mount_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (16,'mounted',mounted),
 (17,'high',high),(17.2,'hop_release',lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),
 (19,'high_sample',lambda c:sample(c,'06_High')),
 (20,'unsafe_exit',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (21,'unsafe_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (22,'blocked_sample',lambda c:sample(c,'07_HighExitBlocked')),
 (23,'forward',lambda c:axis(c,'Gamepad_LeftY',1)),
 (24.5,'forward_sample',lambda c:sample(c,'08_Forward',True)),
 (25,'coast',lambda c:axis(c,'Gamepad_LeftY',0)),
 (25.25,'coast_sample',lambda c:sample(c,'09_Coast')),
 (28,'stopped_sample',lambda c:sample(c,'10_Stopped')),
 (29,'reverse',lambda c:axis(c,'Gamepad_LeftY',-1)),
 (30.5,'reverse_sample',lambda c:sample(c,'11_Reverse',True)),
 (31,'forward_brake',lambda c:axis(c,'Gamepad_LeftY',1)),
 (31.25,'brake_sample',lambda c:sample(c,'12_Braking')),
 (33,'climb',lambda c:axis(c,'Gamepad_RightY',-1)),
 (33.34,'climb_stick_release',lambda c:axis(c,'Gamepad_RightY',0)),
 (34,'climb_sample',lambda c:sample(c,'13_Climb',True)),
 (35,'dive',lambda c:axis(c,'Gamepad_RightY',1)),
 (35.67,'dive_stick_release',lambda c:axis(c,'Gamepad_RightY',0)),
 (36,'dive_sample',lambda c:sample(c,'14_Dive',True)),
 (37,'level',lambda c:(pitch(c,0),axis(c,'Gamepad_LeftY',0))),
 (40,'left_bank',lambda c:key(c,'Gamepad_LeftShoulder',1)),
 (41,'left_sample',lambda c:sample(c,'15_BankLeft',True)),
 (42,'right_bank',lambda c:(key(c,'Gamepad_LeftShoulder',0),key(c,'Gamepad_RightShoulder',1))),
 (43,'right_sample',lambda c:sample(c,'16_BankRight',True)),
 (44,'bank_release',lambda c:key(c,'Gamepad_RightShoulder',0)),
 (45,'bank_level',lambda c:sample(c,'17_BankLevel')),
 (46,'boost',lambda c:(axis(c,'Gamepad_LeftY',1),key(c,'Gamepad_LeftThumbstick',1))),
 (48,'boost_sample',lambda c:sample(c,'18_Boost',True)),
 (51,'empty_sample',lambda c:sample(c,'19_BoostEmpty')),
 (51.1,'boost_release',lambda c:(axis(c,'Gamepad_LeftY',0),key(c,'Gamepad_LeftThumbstick',0))),
 (56,'low',low),(57,'low_sample',lambda c:sample(c,'20_LowReady')),
 (58,'safe_exit',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (58.7,'exit_sample',lambda c:sample(c,'21_Released')),
 (59,'safe_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (61,'fallen_sample',lambda c:sample(c,'22_BoardLanded',True)),
 (62,'jump',lambda c:key(c,'Gamepad_FaceButton_Bottom',1)),
 (62.2,'jump_release',lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),
 (62.9,'jump_land',lambda c:sample(c,'23_JumpLanding',True)),
 (64,'remount',lambda c:key(c,'Gamepad_FaceButton_Left',1)),
 (65,'remount_release',lambda c:key(c,'Gamepad_FaceButton_Left',0)),
 (66,'remounted',lambda c:sample(c,'24_Remounted',True)),
 (67,'landing_hop',lambda c:key(c,'Gamepad_FaceButton_Bottom',1)),
 (67.2,'landing_hop_release',lambda c:key(c,'Gamepad_FaceButton_Bottom',0)),
 (68,'landing_dive',lambda c:(pitch(c,-60),axis(c,'Gamepad_LeftY',.5))),
 (68.9,'landing_level',lambda c:(pitch(c,0),axis(c,'Gamepad_LeftY',0))),
 (69,'touchdown',lambda c:sample(c,'25_MountedLanding',True)),
 (70,'settled',lambda c:sample(c,'26_LandingSettled')),
 (71,'done',lambda c:finish())]

def tick(dt):
    if state['busy']:return
    state['busy']=True
    try:
        if time.monotonic()-state['start']>900:raise RuntimeError('Timeout')
        if not state['requested']:
            if time.monotonic()-state['start']>10:
                u.HoverAuthoring.start_playtest();state['requested']=True
            return
        w=u.HoverAuthoring.get_playtest_world()
        if not w:return
        pc=u.GameplayStatics.get_player_controller(w,0)
        if not pc or not isinstance(pc.get_controlled_pawn(),u.HoverPilot):return
        for name,value in axes.items():u.HoverAuthoring.test_key(pc,name,value,True)
        for name,value in buttons.items():u.HoverAuthoring.test_key(pc,name,value,False)
        t=u.GameplayStatics.get_time_seconds(w)
        if t-state['last_sample']>.1:
            p=pc.get_controlled_pawn()
            report['curves'].append({'t':t,'velocity':list(p.get_velocity().to_tuple()),'pitch':p.get_board_pitch(),'bank':p.get_board_bank(),'wing':p.get_wing_sweep(),'charge':p.get_boost_charge()})
            state['last_sample']=t
        while state['index']<len(events) and t>=events[state['index']][0]:
            _,label,fn=events[state['index']];state['index']+=1
            report['events'].append({'label':label,'time':t});fn(pc)
    except Exception:
        report['errors'].append(traceback.format_exc());print('GLIDER_TEST_ERROR',report['errors'][-1]);finish()
    finally:state['busy']=False

u.EditorPythonScripting.set_keep_python_script_alive(True)
state['handle']=u.register_slate_post_tick_callback(tick)
