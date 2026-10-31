"""Place one unbound BP_SmartSharpen (Fab 'Smart Sharpen' post-process actor) in L_NYC_Survival.

Run via Unreal -ExecutePythonScript with -nullrhi. Idempotent: reuses an existing actor tagged
AFS_SmartSharpen. Saves only the survival map through UHoverAuthoring::SaveSurvivalMap.
Receipt: D:/AFS_Comparisons/NYCSurvival_<date>/sharpen_receipt.json
"""
import json, time, traceback, hashlib
from pathlib import Path
import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
BP = '/Game/SmartSharpen/Blueprint/BP_SmartSharpen'
TAG = 'AFS_SmartSharpen'
WANT = {'unbound': True, 'priority': 10.0}  # intensity/strength stay at the pack's defaults
out = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d')); out.mkdir(parents=True, exist_ok=True)
content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
map_file = content / (MAP[len('/Game/'):] + '.umap')
r = {'map': MAP, 'errors': [], 'set': {}, 'read': {}, 'hash_before': hashlib.sha256(map_file.read_bytes()).hexdigest()}
try:
    LE = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert LE.load_level(MAP), 'load failed'
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    cls = u.load_class(None, BP + '.BP_SmartSharpen_C')
    assert cls, 'BP_SmartSharpen_C not loaded'
    existing = [a for a in u.GameplayStatics.get_all_actors_of_class(world, cls) if a.actor_has_tag(TAG)]
    if existing:
        actor = existing[0]; r['reused'] = actor.get_path_name()
    else:
        # add_survival_actor only accepts spawn points and player starts; use the editor actor subsystem
        actor = u.get_editor_subsystem(u.EditorActorSubsystem).spawn_actor_from_class(cls, u.Vector(270, 5100, 300), u.Rotator())
        assert actor, 'spawn_actor_from_class returned None'
        actor.set_actor_label('AFS Smart Sharpen'); actor.tags = [u.Name(TAG)]
        r['created'] = actor.get_path_name()
    # property names: the BP exposes 'Unbound?', 'Priority', 'Blend Radius', 'Intensity', 'Strength', 'Strength Far'
    names = {'unbound': ['Unbound?', 'unbound', 'Unbound'], 'priority': ['Priority', 'priority']}
    for key, val in WANT.items():
        done = None
        for n in names[key]:
            try:
                actor.set_editor_property(n, val); done = n; break
            except Exception as e:
                last = str(e)
        r['set'][key] = done or ('FAILED: ' + last)
        if done:
            try: r['read'][key] = actor.get_editor_property(done)
            except Exception as e: r['read'][key] = 'read failed: ' + str(e)
    for n in ('Intensity', 'Strength', 'Strength Far', 'Blend Radius'):
        try: r['read'][n] = actor.get_editor_property(n)
        except Exception: pass
    assert u.HoverAuthoring.save_survival_map(world), 'save_survival_map refused'
    r['saved'] = True
except Exception:
    r['errors'].append(traceback.format_exc())
r['hash_after'] = hashlib.sha256(map_file.read_bytes()).hexdigest()
(out / 'sharpen_receipt.json').write_text(json.dumps(r, indent=1, default=str), encoding='utf-8')
u.log_warning('SMART_SHARPEN ' + json.dumps({k: r.get(k) for k in ('created', 'reused', 'set', 'read', 'saved')}, default=str) + (' ERRORS' if r['errors'] else ''))
u.SystemLibrary.quit_editor()
