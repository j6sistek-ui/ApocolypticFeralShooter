"""InventoryZombieAssets.py - what the NYC zombies use today and what the packs on disk offer (2026-10-31, owner:
"Zombie animation and audio diversity, effects, and behavior").

  UnrealEditor-Cmd.exe <AFS.uproject> -unattended -nullrhi -stdout -FullStdOutLogOutput
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/InventoryZombieAssets.py

Read-only. Writes D:/AFS_Comparisons/ZombieDiversity_20261031/inventory.json:
  roster      every definition DA_NYCEncounters spawns (standards, brute, kid, bosses) with mesh, skeleton,
              anim class, blend space, montages, sounds, role and size
  skeletons   every USkeleton with the anim sequences / montages / blend spaces that target it (names only,
              from the asset registry, nothing loaded) grouped by package folder
  sounds      SoundWave / SoundCue counts and names under the zombie and audio folders
  niagara     Niagara systems under the blood / gore / zombie folders
"""
import json
import os
import re
import traceback
from collections import defaultdict

import unreal as u

OUT = 'D:/AFS_Comparisons/ZombieDiversity_20261031/inventory.json'
R = {'errors': [], 'roster': {}, 'skeletons': {}, 'sounds': {}, 'niagara': {}, 'meshes': {}}
AR = u.AssetRegistryHelpers.get_asset_registry()
L = u.EditorAssetLibrary


def props_of(obj):
    doc = type(obj).__doc__ or ''
    return re.findall(r'``(\w+)`` \(', doc)


def short(v):
    if v is None:
        return None
    if isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, u.Name):
        return str(v)
    if isinstance(v, (list, tuple)) or type(v).__name__ == 'Array':
        return [short(x) for x in v]
    if hasattr(v, 'get_path_name'):
        return v.get_path_name()
    if type(v).__name__ in ('SoftObjectPath',):
        return str(v)
    try:
        return str(v)
    except Exception:  # noqa: BLE001
        return repr(v)


def describe_def(d):
    out = {'path': d.get_path_name(), 'class': d.get_class().get_name()}
    for p in props_of(d):
        if p in ('damage_widget_class', 'damage_actor_class', 'loot_table'):
            continue
        try:
            out[p] = short(d.get_editor_property(p))
        except Exception as e:  # noqa: BLE001
            out[p] = 'ERR %s' % e
    mesh = d.get_editor_property('appearance_mesh') if 'appearance_mesh' in out else None
    if mesh:
        sk = mesh.get_editor_property('skeleton')
        out['mesh_skeleton'] = sk.get_path_name() if sk else None
        bounds = mesh.get_bounds()
        out['mesh_bounds_cm'] = [round(bounds.box_extent.x * 2), round(bounds.box_extent.y * 2),
                                 round(bounds.box_extent.z * 2)]
        try:
            out['mesh_morph_targets'] = len(mesh.get_editor_property('morph_targets'))
        except Exception:  # noqa: BLE001
            pass
    return out


try:
    enc = L.load_asset('/Game/HoverPrototype/NYC/DA_NYCEncounters')
    assert enc, 'DA_NYCEncounters missing'
    R['encounter_fields'] = props_of(enc)
    for field in ('standards', 'brute', 'kid', 'bosses'):
        v = enc.get_editor_property(field)
        items = list(v) if isinstance(v, (list, tuple)) or type(v).__name__ == 'Array' else [v]
        R['roster'][field] = [describe_def(d) for d in items if d]
    for f in R['encounter_fields']:
        if f in ('standards', 'brute', 'kid', 'bosses'):
            continue
        try:
            val = enc.get_editor_property(f)
            if hasattr(val, 'get_path_name') or (isinstance(val, (list, tuple)) or type(val).__name__ == 'Array'):
                R.setdefault('encounter_refs', {})[f] = short(val)
        except Exception:  # noqa: BLE001
            pass
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

# Every definition asset of the NYC / Cyber / Lakeside variant classes, so unused types are visible too.
try:
    for cls in ('HoverCyberZombieDefinition',):
        flt = u.ARFilter(class_paths=[u.TopLevelAssetPath('/Script/HoverFlight', cls)], recursive_classes=True)
        R['all_definitions'] = sorted(str(a.package_name) for a in AR.get_assets(flt))
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

# Animation assets by target skeleton (registry tag 'Skeleton'), grouped by folder.
try:
    by_skel = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for cls in ('AnimSequence', 'AnimMontage', 'BlendSpace', 'BlendSpace1D', 'AnimBlueprint'):
        flt = u.ARFilter(class_paths=[u.TopLevelAssetPath('/Script/Engine', cls)])
        for a in AR.get_assets(flt):
            pkg = str(a.package_name)
            if pkg.startswith('/Game/Developers') or not pkg.startswith('/Game/'):
                continue
            tag = a.get_tag_value('Skeleton') or a.get_tag_value('TargetSkeleton') or ''
            m = re.search(r"'([^']+)'", str(tag))
            skel = (m.group(1) if m else str(tag)).split('.')[0] or 'unknown'
            folder = pkg.rsplit('/', 1)[0]
            by_skel[skel][folder][cls].append(pkg.rsplit('/', 1)[1])
    for skel, folders in by_skel.items():
        R['skeletons'][skel] = {f: {c: sorted(n) for c, n in cl.items()} for f, cl in folders.items()}
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

# Skeletal meshes and their skeletons (zombie-looking folders only).
try:
    flt = u.ARFilter(class_paths=[u.TopLevelAssetPath('/Script/Engine', 'SkeletalMesh')])
    for a in AR.get_assets(flt):
        pkg = str(a.package_name)
        if not re.search(r'(?i)zomb|feral|variant|mutant|ghoul|horror|creature|monster|golem|kid|brute', pkg):
            continue
        tag = a.get_tag_value('Skeleton') or ''
        m = re.search(r"'([^']+)'", str(tag))
        R['meshes'][pkg] = (m.group(1) if m else str(tag)).split('.')[0]
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

# Sounds and Niagara by folder.
try:
    for cls, key, mod in (('SoundWave', 'sounds', '/Script/Engine'), ('SoundCue', 'sounds', '/Script/Engine'),
                          ('MetaSoundSource', 'sounds', '/Script/MetasoundEngine'),
                          ('NiagaraSystem', 'niagara', '/Script/Niagara')):
        flt = u.ARFilter(class_paths=[u.TopLevelAssetPath(mod, cls)])
        for a in AR.get_assets(flt):
            pkg = str(a.package_name)
            if not pkg.startswith('/Game/'):
                continue
            if key == 'sounds' and not re.search(r'(?i)zomb|monster|creature|growl|groan|scream|gore|blood|feral|'
                                                 r'horror|entity|flesh|bite|footstep|/Audio/', pkg):
                continue
            if key == 'niagara' and not re.search(r'(?i)blood|gore|zomb|magic|flesh|splat|spray|decal|impact', pkg):
                continue
            folder = pkg.rsplit('/', 1)[0]
            R[key].setdefault(folder, {}).setdefault(cls, []).append(pkg.rsplit('/', 1)[1])
    for key in ('sounds', 'niagara'):
        for folder in R[key]:
            for cls in R[key][folder]:
                R[key][folder][cls].sort()
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(R, open(OUT, 'w'), indent=1, default=str)
print('ZOMBIE_INVENTORY_DONE roster=%s skeletons=%d sound_folders=%d niagara_folders=%d errors=%d' % (
    {k: len(v) for k, v in R['roster'].items()}, len(R['skeletons']), len(R['sounds']), len(R['niagara']),
    len(R['errors'])), flush=True)
u.SystemLibrary.quit_editor()
