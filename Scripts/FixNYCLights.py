"""FixNYCLights.py - stop the on-screen "lights are competing to be the single one used for forward shading ...
ForwardShadingPriority" warning in L_NYC_Survival (every frame of the owner's 2026-10-31 recording).

  UnrealEditor-Cmd.exe <AFS.uproject> -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/FixNYCLights.py

Lists every directional light in the map (intensity, atmosphere-sun flag, current priority), keeps the atmosphere sun
(else the brightest) at ForwardShadingPriority 1 and sets every other directional light to 0, then saves the map.
NYC_LIGHTS_DRY=1 only reports. Receipt D:/AFS_Comparisons/NYCLights_20261031/lights.json.
"""
import json
import os

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
OUT = 'D:/AFS_Comparisons/NYCLights_20261031'
DRY = os.environ.get('NYC_LIGHTS_DRY') == '1'
os.makedirs(OUT, exist_ok=True)
les = u.get_editor_subsystem(u.LevelEditorSubsystem)
assert les.load_level(MAP), 'load failed'
eas = u.get_editor_subsystem(u.EditorActorSubsystem)
rows = []
for a in eas.get_all_level_actors():
    for c in a.get_components_by_class(u.DirectionalLightComponent):
        rows.append({'actor': a.get_actor_label(), 'comp': c.get_name(), 'intensity': c.get_editor_property('intensity'),
                     'sun': c.get_editor_property('atmosphere_sun_light'), 'sun_index': c.get_editor_property('atmosphere_sun_light_index'),
                     'priority': c.get_editor_property('forward_shading_priority'), 'visible': c.get_editor_property('visible'),
                     'affects_world': c.get_editor_property('affects_world'), '_c': c, '_a': a})
live = [r for r in rows if r['visible'] and r['affects_world']]
keep = next((r for r in live if r['sun']), None) or (max(live, key=lambda r: r['intensity']) if live else None)
changed = []
if keep and not DRY:
    for r in rows:
        want = 1 if r is keep else 0
        if r['priority'] != want:
            r['_c'].set_editor_property('forward_shading_priority', want)
            r['_a'].modify()
            changed.append((r['actor'], r['priority'], want))
    if changed:
        les.save_current_level()
report = {'lights': [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows],
          'kept': keep['actor'] if keep else None, 'changed': changed, 'dry': DRY}
json.dump(report, open(os.path.join(OUT, 'lights.json'), 'w'), indent=1, default=str)
print('NYC_LIGHTS_DONE', json.dumps(report, default=str), flush=True)
u.SystemLibrary.quit_editor()
