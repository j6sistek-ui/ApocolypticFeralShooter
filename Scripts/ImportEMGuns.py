"""ImportEMGuns.py - bring the three rigged EM Apocalyptic test guns (EM_11 carbine, EM_21 SMG, EM_08 revolver)
into the project. Modelled on ImportM4A1.py (helpers copied, not imported).

Creates / updates (idempotent, read-back verified, receipt-driven), per gun EM_NN (tag EMNN):
  /Game/HoverPrototype/Weapons/EM/EM_NN/SK_EMNN (+ SK_EMNN_Skeleton)     Interchange skeletal mesh import
  /Game/HoverPrototype/Weapons/EM/EM_NN/Anims/A_EMNN_{Idle,Fire,DryFire,Reload,Chamber}
  /Game/HoverPrototype/Weapons/EM/EM_NN/Textures/T_EMNN_{BaseColor,Normal,Roughness,Metallic}
  /Game/HoverPrototype/Weapons/EM/EM_NN/MI_EMNN                          child of the shared master below
  /Game/HoverPrototype/Weapons/EM/M_EMGun                                 BaseColor/Normal/Roughness/Metallic params
Nothing is bound to DA_HoverPilot (the M4A1 stays bound there; per-weapon binding is built in C++ separately).

Sources: SourceAssets/EM_Apocalyptic_Guns/Rigged/EM_NN/ (SK_EMNN.fbx, A_EMNN_<Clip>.fbx, emNN_rig.json). When a
Rigged/EM_NN/ue_export/ folder exists (EM_11: Scripts/Blender/ReexportEM11ForUE.py, which renames the armature
object to 'Armature' and puts the mesh in every clip file) the FBX files are taken from there instead. A preflight
checks every FBX for the 'Armature' top node and, for clip files, the mesh payload, and fails loudly otherwise.
Textures: SourceAssets/EM_Apocalyptic_Guns/Textures_2K/EM_NN/EM_NN_Apocalyptic_Guns_<Kind>.png (2048^2):
sRGB only on BaseColor, Normal as normal map, Roughness/Metallic linear grayscale, MaxTextureSize 2048, no VT.

Receipt: D:/AFS_Comparisons/EMGuns_20261029/import_receipt.json

Run (headless, CPU only; never concurrently with another AFS editor instance):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/ImportEMGuns.py" -nullrhi -unattended -nosplash -stdout
Flags (inside the quoted value, after the script path):
  --dry-run     print the plan + preflight only (works outside Unreal too)
  --reimport    re-import meshes, clips and textures even when they exist
  --gun=EM_11   limit to one gun (repeatable)
"""
import json
import math
import sys
import time
import traceback
from pathlib import Path

try:
    import unreal as u
except ImportError:
    u = None

ARGS = sys.argv[1:]
DRY_RUN = '--dry-run' in ARGS
REIMPORT = '--reimport' in ARGS
ONLY = [a.split('=', 1)[1] for a in ARGS if a.startswith('--gun=')]

OUT = Path('D:/AFS_Comparisons/EMGuns_20261029')
RECEIPT = OUT / 'import_receipt.json'
PROJECT = Path('M:/UnrealProjects/AFS')
PACK = PROJECT / 'SourceAssets/EM_Apocalyptic_Guns'
RIGGED = PACK / 'Rigged'
TEX_SRC = PACK / 'Textures_2K'

EM = '/Game/HoverPrototype/Weapons/EM'
MASTER_NAME = 'M_EMGun'
MASTER_PATH = EM + '/' + MASTER_NAME
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'  # read-only here: checked to be unchanged

CLIPS = ['Idle', 'Fire', 'DryFire', 'Reload', 'Chamber']
KINDS = ['BaseColor', 'Normal', 'Roughness', 'Metallic']
PARAMS = sorted(KINDS)
TEXTURE_MAX = 2048
POS_TOL_CM = 0.4
ANG_TOL_DEG = 1.0
SOCKETS = ['muzzle', 'ejection_port', 'sight', 'grip_r', 'grip_l', 'mag_well']

# Per-gun data. Expected clip seconds come from the rig json; motion checks from the rig notes / verification.
# check: (clip, bone, frame, expect_cm (component space, None = don't care) or None, expect_local_deg or None)
GUNS = {
    'EM_11': {
        'tag': 'EM11', 'json': 'em11_rig.json', 'kind': 'carbine', 'key_bone': 'magazine',
        'checks': [
            ('Fire', 'bolt_carrier', 2, (-9.0, 0, 0), None),
            ('Fire', 'bolt_carrier', 7, (0, 0, 0), None),
            ('Reload', 'magazine', 0, (0, 0, 0), 0.0),
            ('Reload', 'magazine', 20, (0, 0, 0), 25.0),
            # 2026-10-30 hand-target choreography: rocked out and pulled by the hand to f30, free-fall to -60 cm
            # by f45 (hidden by bone scale f45-f61), pops in at the left hand at f62 and is carried (tilted 25 deg,
            # so the cup offset is rotated) to the well; f72 is the carry pose read back from the export.
            ('Reload', 'magazine', 45, (None, None, -60.0), None),
            ('Reload', 'magazine', 72, (-14.989, -10.153, -32.59), None),
            ('Reload', 'magazine', 100, (0, 0, 0), None),
            ('Reload', 'bolt_carrier', 122, (-9.0, 0, 0), None),
            ('Reload', 'magazine', 144, (0, 0, 0), 0.0),
            ('Chamber', 'bolt_carrier', 30, (-9.0, 0, 0), None),
            ('Chamber', 'bolt_carrier', 66, (0, 0, 0), None),
        ],
        'sweeps': {'Idle': ['magazine', 'bolt_carrier'], 'Fire': ['bolt_carrier', 'trigger'],
                   'DryFire': ['trigger', 'bolt_carrier'], 'Reload': ['magazine', 'bolt_carrier'],
                   'Chamber': ['bolt_carrier']},
        'sweep_expect': [('Fire', 'trigger', 'deg', 8.0), ('DryFire', 'trigger', 'deg', 8.0),
                         ('Fire', 'bolt_carrier', 'cm', 9.0), ('Chamber', 'bolt_carrier', 'cm', 9.0)],
    },
    'EM_21': {
        'tag': 'EM21', 'json': 'em21_rig.json', 'kind': 'smg', 'key_bone': 'magazine',
        'checks': [
            ('Reload', 'magazine', 0, (0, 0, 0), 0.0),
            ('Reload', 'charging_handle', 18, (-8.0, None, None), None),
            # 2026-10-30: the empty mag drops -56 cm by f57 and is hidden (scale 0.001) f57-f74; pops in at the hand f75.
            ('Reload', 'magazine', 72, (0, 0, -56.0), None),
            ('Reload', 'magazine', 144, (0, 0, 0), 0.0),
            ('Chamber', 'charging_handle', 24, (-8.0, 0, 0), None),
            ('Chamber', 'charging_handle', 66, (0, 0, 0), None),
        ],
        'sweeps': {'Idle': ['magazine', 'charging_handle'], 'Fire': ['trigger', 'charging_handle'],
                   'DryFire': ['trigger'], 'Reload': ['magazine', 'charging_handle'],
                   'Chamber': ['charging_handle']},
        'sweep_expect': [('Fire', 'trigger', 'deg', 8.0), ('DryFire', 'trigger', 'deg', 8.0),
                         ('Reload', 'magazine', 'cm', 56.0), ('Reload', 'charging_handle', 'cm', 8.0),
                         ('Chamber', 'charging_handle', 'cm', 8.0)],
    },
    'EM_08': {
        'tag': 'EM08', 'json': 'em08_rig.json', 'kind': 'revolver', 'key_bone': 'cylinder',
        'checks': [
            ('Fire', 'hammer', 2, None, 30.0),
            ('Fire', 'cylinder', 2, None, 60.0),
            ('Fire', 'trigger', 2, None, 10.0),
            ('DryFire', 'hammer', 4, None, 30.0),
            ('DryFire', 'cylinder', 4, None, 60.0),
            ('Reload', 'cylinder', 0, (0, 0, 0), 0.0),
            ('Reload', 'crane', 22, None, 90.0),
            ('Reload', 'cylinder', 72, (0, -3.42, -1.98), None),
            ('Reload', 'mag_well', 72, (0, -3.42, -1.98), None),
            ('Reload', 'cylinder', 144, (0, 0, 0), None),
            ('Chamber', 'hammer', 12, None, 30.0),
            ('Chamber', 'cylinder', 12, None, 60.0),
            ('Chamber', 'hammer', 40, None, 0.0),
        ],
        'sweeps': {'Idle': ['cylinder', 'hammer'], 'Fire': ['hammer', 'cylinder', 'trigger'],
                   'DryFire': ['hammer', 'cylinder', 'trigger'], 'Reload': ['cylinder', 'crane', 'ejector_rod', 'mag_well'],
                   'Chamber': ['hammer', 'cylinder', 'trigger']},
        'sweep_expect': [('Reload', 'ejector_rod', 'cm', None)],
    },
}

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'reimport': REIMPORT, 'errors': [], 'warnings': [], 'notes': [],
          'created': [], 'saved': [], 'preflight': {}, 'master': {}, 'guns': {}, 'python_names': {},
          'readback_mismatches': [], 'texture_max': TEXTURE_MAX, 'da_untouched': None,
          'claim': 'Editor asset import/authoring only (-nullrhi); no gameplay run, no rendered evidence'}
EA = AT = ML = AL = None
TOUCHED = []  # assets to save at the end
GUN = None    # current gun id for error attribution
ROOT_SCALES = {}  # gun -> root bone local scale when it is not 1 (judged against the M4A1 at the end)
M4A1_SKEL = '/Game/HoverPrototype/Weapons/M4A1/SK_M4A1_Skeleton'


def log(*a):
    line = 'EMGUNS_IMPORT ' + ' '.join(str(x) for x in a)
    print(line, flush=True)
    if u:
        u.log(line)


def warn(msg):
    REPORT['warnings'].append(('[%s] ' % GUN if GUN else '') + msg)
    log('warning', msg)


def error(msg):
    REPORT['errors'].append(('[%s] ' % GUN if GUN else '') + msg)
    log('error', msg)


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('EMGUNS_IMPORT receipt failed', traceback.format_exc(), flush=True)


# ---------------------------------------------------------------------------------------------
# Helpers (copied from ImportM4A1.py / AuthorNYCBosses.py; Foo -> foo, bFoo -> foo).

def pythonize(cpp):
    name = cpp[1:] if len(cpp) > 1 and cpp[0] == 'b' and cpp[1].isupper() else cpp
    out = name[0].lower()
    for i in range(1, len(name)):
        c, prev = name[i], name[i - 1]
        nxt = name[i + 1] if i + 1 < len(name) else ''
        if c.isupper() and (prev.islower() or prev.isdigit() or (prev.isupper() and nxt.islower())):
            out += '_'
        out += c.lower()
    return out


def candidates(cpp):
    base = pythonize(cpp)
    alt = ''.join(('_' + ch if ch.isdigit() and i and not base[i - 1].isdigit() and base[i - 1] != '_' else ch)
                  for i, ch in enumerate(base))
    return [base] if alt == base else [base, alt]


def resolve(holder, cpp, scope):
    key = scope.split('[')[0] + '.' + cpp
    if key in REPORT['python_names']:
        return REPORT['python_names'][key]
    for name in candidates(cpp):
        try:
            holder.get_editor_property(name)
            REPORT['python_names'][key] = name
            return name
        except Exception:
            continue
    raise AttributeError('%s: no Python property for %s (tried %s)' % (scope, cpp, candidates(cpp)))


def pathish(value):
    if value is None:
        return None
    text = value.get_path_name() if hasattr(value, 'get_path_name') else str(value)
    text = text.strip().strip("'\"")
    return text.split('.')[0] if text.startswith('/') else text


def norm(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return round(value, 4)
    if hasattr(value, 'get_path_name'):
        return pathish(value)
    if u and isinstance(value, u.Name):
        return str(value)
    if isinstance(value, (list, tuple)) or (u and isinstance(value, u.Array)):
        return [norm(v) for v in value]
    return str(value)


def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-3
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def put(holder, cpp, value, scope, changes):
    name = resolve(holder, cpp, scope)
    if same(norm(holder.get_editor_property(name)), norm(value)):
        return False
    holder.set_editor_property(name, value)
    changes.append(scope + '.' + cpp)
    return True


def check(holder, cpp, expected, scope):
    actual = norm(holder.get_editor_property(resolve(holder, cpp, scope)))
    if not same(actual, norm(expected)):
        REPORT['readback_mismatches'].append({'field': scope + '.' + cpp, 'expected': norm(expected),
                                              'actual': actual})
        return False
    return True


def load(path):
    assert EA.does_asset_exist(path), 'missing asset ' + path
    asset = EA.load_asset(path)
    assert asset, 'failed to load ' + path
    return asset


def ensure_class(path, cls):
    asset = load(path)
    assert isinstance(asset, cls), '%s exists but is %s, not %s; refusing to touch it' % (
        path, asset.get_class().get_name(), cls.__name__)
    return asset


def touch(asset, created=False):
    if asset is not None and all(pathish(a) != pathish(asset) for a in TOUCHED):
        TOUCHED.append(asset)
    if created:
        REPORT['created'].append(pathish(asset))


def vec(v):
    return [round(v.x, 3), round(v.y, 3), round(v.z, 3)]


def list_assets(folder):
    return sorted(p.split('.')[0] for p in EA.list_assets(folder, recursive=True, include_folder=False))


def png_size(path):
    with open(str(path), 'rb') as f:
        head = f.read(24)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')


def quat_angle_deg(a, b):
    d = abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)
    return math.degrees(2.0 * math.acos(min(1.0, d)))


# ---------------------------------------------------------------------------------------------
# Paths, rig json, preflight (no Unreal needed).

def paths_for(gun):
    tag = GUNS[gun]['tag']
    root = EM + '/' + gun
    return {'root': root, 'mesh': root + '/SK_' + tag, 'skel': root + '/SK_' + tag + '_Skeleton',
            'anims': root + '/Anims', 'textures': root + '/Textures', 'mi': root + '/MI_' + tag,
            'clip': {c: root + '/Anims/A_%s_%s' % (tag, c) for c in CLIPS},
            'tex': {k: root + '/Textures/T_%s_%s' % (tag, k) for k in KINDS}}


def source_dir(gun):
    fixed = RIGGED / gun / 'ue_export'
    if (fixed / ('SK_%s.fbx' % GUNS[gun]['tag'])).is_file():
        return fixed
    return RIGGED / gun


def texture_files(gun):
    return {k: TEX_SRC / gun / ('%s_Apocalyptic_Guns_%s.png' % (gun, k)) for k in KINDS}


def rig_info(gun):
    """Normalise the three (differently shaped) rig json files."""
    d = json.loads((RIGGED / gun / GUNS[gun]['json']).read_text())
    bones = d['bones']
    if isinstance(bones, dict):          # EM_21
        names = list(bones)
        parents = {b: v.get('parent') for b, v in bones.items()}
        heads = {b: v.get('head_ue_cm') for b, v in bones.items()}
    elif bones and isinstance(bones[0], dict):  # EM_08
        names = [b['name'] for b in bones]
        parents = {b['name']: b.get('parent') for b in bones}
        heads = {b['name']: b.get('head_ue_cm') for b in bones}
    else:                                 # EM_11
        names = list(bones)
        parents = dict(d.get('bone_parents') or {})
        heads = dict(d.get('bone_heads_cm_ue') or {})
    if 'bounds_cm_blender' in d:
        bounds, frame = d['bounds_cm_blender'], 'blender'
    elif 'bounds' in d:
        bounds, frame = [d['bounds']['min_cm'], d['bounds']['max_cm']], 'json'
    else:
        bm = d['verification']['SK_%s.fbx' % GUNS[gun]['tag']]['bounds_m']
        bounds, frame = [[round(x * 100, 2) for x in bm[0]], [round(x * 100, 2) for x in bm[1]]], 'blender'
    length = d.get('length_cm') or (d.get('scale') or {}).get('length_cm')
    clips = {}
    for k, v in d['clips'].items():
        clips[k.rsplit('_', 1)[-1]] = v.get('seconds')
    return {'bones': names, 'parents': parents, 'heads_cm_ue': heads, 'bounds_cm': bounds, 'bounds_frame': frame,
            'length_cm': length, 'clip_seconds': clips}


def fbx_scan(path, gun):
    data = path.read_bytes()
    return {'bytes': len(data), 'has_armature_node': data.count(b'Armature') > 0,
            'has_gun_skeleton_name': data.count(('%s_Skeleton' % gun).encode()) > 0,
            'has_geometry': data.count(b'Geometry') > 0}


def preflight(gun):
    src = source_dir(gun)
    tag = GUNS[gun]['tag']
    out = {'source_dir': str(src), 'files': {}, 'textures': {}, 'ok': True}
    if src.name == 'ue_export':
        out['note'] = ('using the corrected re-export in ue_export/ (Scripts/Blender/ReexportEM11ForUE.py); the '
                       'original Rigged/%s files have the armature object named %s_Skeleton (-> extra x100 root '
                       'bone in UE) and armature-only clip files (Interchange needs the mesh)' % (gun, gun))
    problems = []
    for name in ['SK_%s.fbx' % tag] + ['A_%s_%s.fbx' % (tag, c) for c in CLIPS]:
        p = src / name
        if not p.is_file():
            problems.append('missing ' + str(p))
            continue
        scan = fbx_scan(p, gun)
        out['files'][name] = scan
        if not scan['has_armature_node'] or scan['has_gun_skeleton_name']:
            problems.append('%s: top armature node is not named "Armature" (would add an extra x100 root bone)' % name)
        if not scan['has_geometry']:
            problems.append('%s: no mesh payload (UE 5.8 Interchange needs mesh + armature in clip files)' % name)
    for k, p in texture_files(gun).items():
        out['textures'][k] = {'path': str(p), 'exists': p.is_file(), 'size': png_size(p) if p.is_file() else None}
    out['textures_complete'] = all(t['exists'] for t in out['textures'].values())
    try:
        out['rig'] = rig_info(gun)
    except Exception:
        problems.append('rig json unreadable: ' + traceback.format_exc(limit=1))
    out['problems'] = problems
    out['ok'] = not problems
    return out


# ---------------------------------------------------------------------------------------------
# Textures + material.

def source_size(tex):
    try:
        import re
        text = u.HoverAuthoring.inspect_texture(tex)
        m = re.search(r'size=(\d+)x(\d+)', text)
        if m:
            return [int(m.group(1)), int(m.group(2))]
    except Exception:
        pass
    return None


def import_textures(gun, info):
    P = paths_for(gun)
    out = {}
    rows = {}
    for kind, src in texture_files(gun).items():
        path = P['tex'][kind]
        name = path.rsplit('/', 1)[1]
        entry = {'source': str(src), 'source_png_size': png_size(src)}
        exists = EA.does_asset_exist(path)
        if not exists or REIMPORT:
            task = u.AssetImportTask()
            task.set_editor_property('filename', str(src))
            task.set_editor_property('destination_path', P['textures'])
            task.set_editor_property('destination_name', name)
            task.set_editor_property('automated', True)
            task.set_editor_property('replace_existing', True)
            task.set_editor_property('save', False)
            AT.import_asset_tasks([task])
            imported = [str(p) for p in (task.get_editor_property('imported_object_paths') or [])]
            entry['imported'] = imported
            assert EA.does_asset_exist(path), 'texture import failed for %s -> %s (%s)' % (src, path, imported)
        tex = ensure_class(path, u.Texture2D)
        changes = []
        scope = 'Texture2D[%s]' % name
        put(tex, 'SRGB', kind == 'BaseColor', scope, changes)
        put(tex, 'CompressionSettings', {'BaseColor': u.TextureCompressionSettings.TC_DEFAULT,
                                         'Normal': u.TextureCompressionSettings.TC_NORMALMAP}.get(
            kind, u.TextureCompressionSettings.TC_GRAYSCALE), scope, changes)
        put(tex, 'LODGroup', u.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP if kind == 'Normal'
            else u.TextureGroup.TEXTUREGROUP_WORLD, scope, changes)
        put(tex, 'MaxTextureSize', TEXTURE_MAX, scope, changes)
        try:
            put(tex, 'VirtualTextureStreaming', False, scope, changes)
        except AttributeError:
            pass
        entry['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
        entry['changes'] = changes
        src_size = source_size(tex) or list(entry['source_png_size'] or [0, 0])
        mx = int(tex.get_editor_property('max_texture_size'))
        entry['source_size'] = src_size
        entry['max_texture_size'] = mx
        entry['effective'] = min(max(src_size), mx) if mx > 0 else max(src_size)
        for prop in ('srgb', 'compression_settings', 'lod_group', 'virtual_texture_streaming', 'flip_green_channel'):
            try:
                entry[prop] = str(tex.get_editor_property(prop))
            except Exception:
                pass
        if max(src_size) < TEXTURE_MAX:
            error('%s source %s is below 2K' % (name, src_size))
        if 0 < mx < TEXTURE_MAX:
            error('%s MaxTextureSize %d < %d' % (name, mx, TEXTURE_MAX))
        check(tex, 'SRGB', kind == 'BaseColor', scope)
        check(tex, 'MaxTextureSize', TEXTURE_MAX, scope)
        rows[name] = entry
        if not exists or REIMPORT or changes:
            touch(tex, not exists)
        out[kind] = tex
    info['textures'] = rows
    log('textures', gun, {k: v['effective'] for k, v in rows.items()})
    return out


def build_master(default_textures):
    info = REPORT['master']
    created = not EA.does_asset_exist(MASTER_PATH)
    mat = AT.create_asset(MASTER_NAME, EM, u.Material, u.MaterialFactoryNew()) if created \
        else ensure_class(MASTER_PATH, u.Material)
    assert mat, 'create_asset failed for ' + MASTER_PATH
    params = sorted(str(n) for n in ML.get_texture_parameter_names(mat))
    count = ML.get_num_material_expressions(mat)
    rebuilt = False
    if created or params != PARAMS or count != 4:
        ML.delete_all_material_expressions(mat)
        rows = [('BaseColor', u.MaterialSamplerType.SAMPLERTYPE_COLOR, -500, [('RGB', u.MaterialProperty.MP_BASE_COLOR)]),
                ('Normal', u.MaterialSamplerType.SAMPLERTYPE_NORMAL, -200, [('RGB', u.MaterialProperty.MP_NORMAL)]),
                ('Metallic', u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 100,
                 [('R', u.MaterialProperty.MP_METALLIC)]),
                ('Roughness', u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 400,
                 [('R', u.MaterialProperty.MP_ROUGHNESS)])]
        for param, sampler, y, outputs in rows:
            node = ML.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, -420, y)
            assert node, 'create_material_expression failed for ' + param
            node.set_editor_property('parameter_name', param)
            node.set_editor_property('texture', default_textures[param])
            node.set_editor_property('sampler_type', sampler)
            for output, prop in outputs:
                assert ML.connect_material_property(node, output, prop), 'connect %s.%s failed' % (param, output)
        rebuilt = True
    changes = []
    put(mat, 'bUsedWithSkeletalMesh', True, 'Material[%s]' % MASTER_NAME, changes)
    if rebuilt or changes:
        ML.recompile_material(mat)
        touch(mat, created)
    params = sorted(str(n) for n in ML.get_texture_parameter_names(mat))
    if params != PARAMS:
        REPORT['readback_mismatches'].append({'field': MASTER_NAME + '.texture_parameters', 'expected': PARAMS,
                                              'actual': params})
    check(mat, 'bUsedWithSkeletalMesh', True, 'Material[%s]' % MASTER_NAME)
    info.update({'path': MASTER_PATH, 'state': 'created' if created else ('rebuilt' if rebuilt else 'existing'),
                 'parameters': params, 'expressions': ML.get_num_material_expressions(mat), 'changes': changes,
                 'defaults': {p: pathish(ML.get_material_default_texture_parameter_value(mat, p)) for p in params}})
    return mat


def explicit_overrides(mi):
    return {str(r.get_editor_property('parameter_info').get_editor_property('name')):
            pathish(r.get_editor_property('parameter_value'))
            for r in (mi.get_editor_property('texture_parameter_values') or [])}


def set_texture_parameter(mi, param, tex, diags):
    """MaterialEditingLibrary setter first; on False (5.8) write TextureParameterValues directly."""
    diag = {'param': param, 'texture': pathish(tex)}
    diag['library_ok'] = bool(ML.set_material_instance_texture_parameter_value(mi, param, tex))
    if not diag['library_ok']:
        pinfo = u.MaterialParameterInfo()
        pinfo.set_editor_property('name', param)
        pinfo.set_editor_property('association', u.MaterialParameterAssociation.GLOBAL_PARAMETER)
        pinfo.set_editor_property('index', -1)
        value = u.TextureParameterValue()
        value.set_editor_property('parameter_info', pinfo)
        value.set_editor_property('parameter_value', tex)
        rows = [r for r in (mi.get_editor_property('texture_parameter_values') or [])
                if str(r.get_editor_property('parameter_info').get_editor_property('name')) != param]
        mi.set_editor_property('texture_parameter_values', rows + [value])
        diag['fallback'] = 'texture_parameter_values'
    diag['readback'] = pathish(ML.get_material_instance_texture_parameter_value(mi, param))
    diags.append(diag)
    assert diag['readback'] == pathish(tex), '%s.%s set failed: %s' % (pathish(mi), param, diag)


def build_instance(gun, master, textures, info):
    P = paths_for(gun)
    name = P['mi'].rsplit('/', 1)[1]
    created = not EA.does_asset_exist(P['mi'])
    mi = AT.create_asset(name, P['root'], u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew()) \
        if created else ensure_class(P['mi'], u.MaterialInstanceConstant)
    assert mi, 'create_asset failed for ' + P['mi']
    changed = False
    diags = []
    if pathish(mi.get_editor_property('parent')) != pathish(master):
        ML.set_material_instance_parent(mi, master)
        changed = True
    # Compare the EXPLICIT overrides, not the effective value: a parent default that happens to be this gun's map
    # (the master uses EM_11's maps as defaults) must still be written as an override on the MI.
    for kind, tex in textures.items():
        if explicit_overrides(mi).get(kind) != pathish(tex):
            set_texture_parameter(mi, kind, tex, diags)
            changed = True
    if changed:
        ML.update_material_instance(mi)
        touch(mi, created)
    readback = {}
    overrides = explicit_overrides(mi)
    for kind, tex in textures.items():
        got = pathish(ML.get_material_instance_texture_parameter_value(mi, kind))
        readback[kind] = got
        if got != pathish(tex) or overrides.get(kind) != pathish(tex):
            REPORT['readback_mismatches'].append({'field': '%s.%s' % (name, kind), 'expected': pathish(tex),
                                                  'actual': got, 'override': overrides.get(kind)})
    info['material_instance'] = {'path': P['mi'], 'state': 'created' if created else ('updated' if changed else 'existing'),
                                 'parent': pathish(mi.get_editor_property('parent')), 'textures': readback,
                                 'overrides': overrides, 'sets': diags}
    return mi


# ---------------------------------------------------------------------------------------------
# Interchange imports (pipelines copied from ImportM4A1.py).

def base_pipeline():
    pipe = u.InterchangeGenericAssetsPipeline()
    pipe.set_editor_property('use_source_name_for_asset', True)
    mat = pipe.get_editor_property('material_pipeline')
    mat.set_editor_property('import_materials', False)
    try:
        mat.get_editor_property('texture_pipeline').set_editor_property('import_textures', False)
    except Exception:
        warn('texture_pipeline.import_textures not settable: ' + traceback.format_exc(limit=1))
    mesh = pipe.get_editor_property('mesh_pipeline')
    mesh.set_editor_property('import_static_meshes', False)
    return pipe


def set_prop(holder, name, value, label):
    try:
        holder.set_editor_property(name, value)
    except Exception:
        warn('%s.%s not settable: %s' % (label, name, traceback.format_exc(limit=1)))


def mesh_pipeline():
    pipe = base_pipeline()
    common = pipe.get_editor_property('common_meshes_properties')
    set_prop(common, 'force_all_mesh_as_type', u.InterchangeForceMeshType.IFMT_SKELETAL_MESH, 'common_meshes')
    set_prop(common, 'recompute_normals', False, 'common_meshes')
    set_prop(common, 'recompute_tangents', False, 'common_meshes')
    set_prop(common, 'import_sockets', True, 'common_meshes')
    set_prop(common, 'bake_meshes', True, 'common_meshes')
    skel = pipe.get_editor_property('common_skeletal_meshes_and_animations_properties')
    set_prop(skel, 'import_only_animations', False, 'common_skeletal')
    set_prop(skel, 'use_t0_as_ref_pose', False, 'common_skeletal')
    mesh = pipe.get_editor_property('mesh_pipeline')
    set_prop(mesh, 'import_skeletal_meshes', True, 'mesh_pipeline')
    set_prop(mesh, 'import_morph_targets', False, 'mesh_pipeline')
    set_prop(mesh, 'create_physics_asset', False, 'mesh_pipeline')
    set_prop(mesh, 'skeletal_mesh_import_content_type', u.InterchangeSkeletalMeshContentType.ALL, 'mesh_pipeline')
    anim = pipe.get_editor_property('animation_pipeline')
    set_prop(anim, 'import_animations', False, 'animation_pipeline')
    return pipe


def anim_pipeline(skel):
    pipe = base_pipeline()
    common = pipe.get_editor_property('common_skeletal_meshes_and_animations_properties')
    common.set_editor_property('skeleton', skel)
    common.set_editor_property('import_only_animations', True)
    anim = pipe.get_editor_property('animation_pipeline')
    anim.set_editor_property('import_animations', True)
    anim.set_editor_property('import_bone_tracks', True)
    pipe.get_editor_property('mesh_pipeline').set_editor_property('import_skeletal_meshes', False)
    return pipe


def interchange_import(filename, dest, pipe):
    im = u.InterchangeManager.get_interchange_manager_scripted()
    sd = u.InterchangeManager.create_source_data(str(filename))
    params = u.ImportAssetParameters()
    params.set_editor_property('is_automated', True)
    params.set_editor_property('override_pipelines', [u.SoftObjectPath(pipe.get_path_name())])
    before = set(list_assets(dest)) if EA.does_directory_exist(dest) else set()
    ok = im.import_asset(dest, sd, params)
    try:
        im.wait_until_all_tasks_done(False)
    except Exception:
        pass
    after = set(list_assets(dest)) if EA.does_directory_exist(dest) else set()
    new = sorted(after - before)
    log('interchange', Path(str(filename)).name, '->', dest, 'ok', ok, 'new', [p.rsplit('/', 1)[1] for p in new])
    return bool(ok), new


def bone_parents(mesh, names):
    """Parent names from the reference skeleton (SkeletonModifier, read-only use). None when unavailable."""
    try:
        mod = u.SkeletonModifier()
        mod.set_skeletal_mesh(mesh)
        out = {}
        for b in names:
            p = str(mod.get_parent_name(b))
            out[b] = None if p in ('None', '') else p
        return out, 'SkeletonModifier'
    except Exception:
        return None, 'unavailable: ' + traceback.format_exc(limit=1).strip().splitlines()[-1]


def compare_bounds(got_min, got_max, want, frame):
    """Returns (max abs diff cm, y_mirrored) comparing as-is and with Y mirrored."""
    def diff(wmin, wmax):
        return max(abs(a - b) for a, b in zip(got_min + got_max, wmin + wmax))
    wmin, wmax = list(want[0]), list(want[1])
    direct = diff(wmin, wmax)
    mmin = [wmin[0], -wmax[1], wmin[2]]
    mmax = [wmax[0], -wmin[1], wmax[2]]
    mirrored = diff(mmin, mmax)
    return (round(mirrored, 3), True) if mirrored < direct else (round(direct, 3), False)


def import_mesh(gun, mi, rig, info):
    P = paths_for(gun)
    tag = GUNS[gun]['tag']
    src = source_dir(gun) / ('SK_%s.fbx' % tag)
    m = info.setdefault('mesh', {})
    m['source'] = str(src)
    exists = EA.does_asset_exist(P['mesh'])
    if not exists or REIMPORT:
        ok, new = interchange_import(src, P['root'], mesh_pipeline())
        m['imported'] = new
        assert EA.does_asset_exist(P['mesh']), '%s did not import (%s)' % (P['mesh'], new)
        REPORT['created'].extend(new)
        extra = [p for p in new if p not in (P['mesh'], P['skel'])]
        if extra:
            warn('Interchange created extra assets beside the mesh: %s' % extra)
    m['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
    mesh = ensure_class(P['mesh'], u.SkeletalMesh)
    skel = mesh.get_editor_property('skeleton')
    assert skel, '%s has no skeleton' % P['mesh']
    m['skeleton'] = pathish(skel)
    if pathish(skel) != P['skel']:
        error('skeleton is %s, expected %s' % (pathish(skel), P['skel']))
    if not exists or REIMPORT:
        touch(mesh, not exists)
        touch(skel, not exists)
    # Bounds.
    b = mesh.get_bounds()
    ext, org = b.box_extent, b.origin
    bmin = vec(u.Vector(org.x - ext.x, org.y - ext.y, org.z - ext.z))
    bmax = vec(u.Vector(org.x + ext.x, org.y + ext.y, org.z + ext.z))
    m['bounds_min_cm'], m['bounds_max_cm'] = bmin, bmax
    m['length_cm'] = round(ext.x * 2, 2)
    m['size_cm'] = [round(ext.x * 2, 2), round(ext.y * 2, 2), round(ext.z * 2, 2)]
    m['rig_length_cm'] = rig['length_cm']
    if rig['length_cm'] and abs(m['length_cm'] - rig['length_cm']) > 1.0:
        error('length %.2f cm != rig json %.2f cm' % (m['length_cm'], rig['length_cm']))
    bdiff, mirrored = compare_bounds(bmin, bmax, rig['bounds_cm'], rig['bounds_frame'])
    m['bounds_vs_rig_json'] = {'rig': rig['bounds_cm'], 'rig_frame': rig['bounds_frame'], 'max_abs_diff_cm': bdiff,
                               'y_mirrored': mirrored}
    if bdiff > 0.5:
        error('bounds differ from rig json by %.2f cm (got %s %s, rig %s)' % (bdiff, bmin, bmax, rig['bounds_cm']))
    for prop in ('physics_asset',):
        try:
            m[prop] = pathish(mesh.get_editor_property(prop))
        except Exception:
            m[prop] = 'n/a'
    try:
        m['lods'] = int(u.SkeletalMeshEditorSubsystem.get_lod_count(mesh))
    except Exception:
        m['lods'] = 'n/a'
    # Bones.
    pose = u.AnimPoseExtensions.get_reference_pose(skel)
    names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
    m['bones'] = names
    m['bone_count'] = len(names)
    m['rig_bones'] = rig['bones']
    m['rig_bone_count'] = len(rig['bones'])
    if 'Armature' in names or names[0] != 'root' or any(n.endswith('_Skeleton') for n in names):
        root_scale = None
        try:
            root_scale = vec(u.AnimPoseExtensions.get_bone_pose(pose, names[0], u.AnimPoseSpaces.LOCAL).scale3d)
        except Exception:
            pass
        error('!!! EXPORT CONVENTION BROKEN: skeleton root is "%s" (local scale %s), bones %s. Expected "root" first '
              'with no extra Armature/x100 root.' % (names[0], root_scale, names))
    missing = [x for x in rig['bones'] if x not in names]
    extra = [x for x in names if x not in rig['bones']]
    m['missing_vs_rig'] = missing
    m['extra_vs_rig'] = extra
    if missing or extra:
        error('bones differ from rig json: missing %s extra %s' % (missing, extra))
    scales = {}
    ref = {}
    head_err = {}
    for bn in names:
        t = u.AnimPoseExtensions.get_bone_pose(pose, bn, u.AnimPoseSpaces.WORLD)
        lt = u.AnimPoseExtensions.get_bone_pose(pose, bn, u.AnimPoseSpaces.LOCAL)
        ref[bn] = {'loc_cm': vec(t.translation), 'x_axis': vec(t.rotation.rotate_vector(u.Vector(1, 0, 0)))}
        sc = vec(lt.scale3d)
        if any(abs(s - 1.0) > 1e-3 for s in sc):
            scales[bn] = sc
        want = rig['heads_cm_ue'].get(bn)
        if want:
            head_err[bn] = round(max(abs(a - b) for a, b in zip(ref[bn]['loc_cm'], want)), 3)
    m['ref_pose_component_space'] = ref
    m['non_unit_local_scales'] = scales
    m['component_scale'] = {bn: vec(u.AnimPoseExtensions.get_bone_pose(pose, bn, u.AnimPoseSpaces.WORLD).scale3d)
                            for bn in ('root', 'body', 'muzzle', 'ejection_port') if bn in names}
    other = {k: v for k, v in scales.items() if k != 'root'}
    if other:
        error('bones other than root with non-unit local scale: %s' % other)
    if 'root' in scales:
        ROOT_SCALES[gun] = scales['root']
    m['bone_head_err_cm_vs_rig'] = head_err
    worst = max(head_err.values()) if head_err else None
    m['bone_head_err_cm_max'] = worst
    if worst is not None and worst > 0.05:
        bad = {k: v for k, v in head_err.items() if v > 0.05}
        error('bone heads differ from rig json head_ue_cm by > 0.05 cm: %s' % bad)
    parents, how = bone_parents(mesh, names)
    m['parents_source'] = how
    if parents is not None:
        m['parents'] = parents
        diff = {b: {'ue': parents.get(b), 'rig': rig['parents'].get(b)} for b in names
                if b in rig['parents'] and parents.get(b) != rig['parents'].get(b)}
        m['parent_mismatches'] = diff
        if diff:
            error('bone parents differ from rig json: %s' % diff)
    else:
        m['parents'] = None
        REPORT['notes'].append('[%s] bone parents not readable from Python (%s); hierarchy is checked by motion '
                               '(see clip checks)' % (gun, how))
    m['socket_bones'] = {s: ref.get(s, {}).get('loc_cm') for s in SOCKETS}
    missing_sockets = [s for s in SOCKETS if s not in names]
    if missing_sockets:
        error('socket bones missing: %s' % missing_sockets)
    # Material slots: one slot -> MI_EMNN.
    rows = list(mesh.get_editor_property('materials'))
    m['slots_before'] = [{'slot': str(r.get_editor_property('material_slot_name')),
                          'material': pathish(r.get_editor_property('material_interface'))} for r in rows]
    if len(rows) != 1:
        error('expected ONE material slot, got %d: %s' % (len(rows), m['slots_before']))
    changed = False
    for r in rows:
        if pathish(r.get_editor_property('material_interface')) != pathish(mi):
            r.set_editor_property('material_interface', mi)
            changed = True
    if changed:
        mesh.set_editor_property('materials', rows)
        touch(mesh)
    rows = list(mesh.get_editor_property('materials'))
    m['slots'] = [{'slot': str(r.get_editor_property('material_slot_name')),
                   'material': pathish(r.get_editor_property('material_interface'))} for r in rows]
    for r in m['slots']:
        if r['material'] != pathish(mi):
            REPORT['readback_mismatches'].append({'field': '%s.slot %s' % (P['mesh'], r['slot']),
                                                  'expected': pathish(mi), 'actual': r['material']})
    try:
        preview = AL.get_skeleton_preview_mesh(skel, False)
        if pathish(preview) != P['mesh']:
            AL.set_skeleton_preview_mesh(skel, mesh, True)
            touch(skel)
        m['skeleton_preview_mesh'] = pathish(AL.get_skeleton_preview_mesh(skel, False))
    except Exception:
        warn('preview mesh not set: ' + traceback.format_exc(limit=1))
    return mesh, skel


def eval_opts():
    opts = u.AnimPoseEvaluationOptions()
    for prop, val in (('evaluation_type', u.AnimDataEvalType.RAW), ('retarget', False),
                      ('extract_root_motion', False)):
        try:
            opts.set_editor_property(prop, val)
        except Exception:
            pass
    return opts


def bone_delta(pose, bone):
    cur = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD)
    ref = u.AnimPoseExtensions.get_ref_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD)
    lcur = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.LOCAL)
    lref = u.AnimPoseExtensions.get_ref_bone_pose(pose, bone, u.AnimPoseSpaces.LOCAL)
    d = [cur.translation.x - ref.translation.x, cur.translation.y - ref.translation.y,
         cur.translation.z - ref.translation.z]
    rc, rr = cur.rotation.rotator(), ref.rotation.rotator()
    return {'delta_cm': [round(v, 3) for v in d],
            'dist_cm': round(math.sqrt(sum(v * v for v in d)), 3),
            'world_deg': round(quat_angle_deg(cur.rotation, ref.rotation), 2),
            'local_deg': round(quat_angle_deg(lcur.rotation, lref.rotation), 2),
            'rotator_delta_deg': {'roll': round(rc.roll - rr.roll, 2), 'pitch': round(rc.pitch - rr.pitch, 2),
                                  'yaw': round(rc.yaw - rr.yaw, 2)}}


def pos_ok(d, expect):
    return all(e is None or abs(d[i] - e) < POS_TOL_CM for i, e in enumerate(expect))


def motion_report(gun, clip, seq, nf):
    cfg = GUNS[gun]
    opts = eval_opts()
    tests = []
    for c, bone, frame, expect, deg in cfg['checks']:
        if c != clip:
            continue
        row = {'bone': bone, 'frame': frame, 'expect_cm': list(expect) if expect else None, 'expect_local_deg': deg}
        try:
            pose = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, min(frame, nf), opts)
            row.update(bone_delta(pose, bone))
            ok = True
            if expect is not None:
                ok = pos_ok(row['delta_cm'], expect)
                if not ok and expect[1] not in (None, 0):
                    mirrored = (expect[0], -expect[1], expect[2])
                    if pos_ok(row['delta_cm'], mirrored):
                        ok = True
                        row['y_mirrored_vs_rig_json'] = True
            if deg is not None and abs(row['local_deg'] - deg) > ANG_TOL_DEG:
                ok = False
            row['ok'] = ok
        except Exception:
            row.update({'ok': False, 'error': traceback.format_exc(limit=1)})
        tests.append(row)
    # Sweep: frame 0, mid-clip and the per-bone maximum over every frame.
    sweep = {}
    bones = cfg['sweeps'].get(clip, [])
    if bones:
        mid = nf // 2
        maxes = {b: {'max_dist_cm': 0.0, 'max_dist_frame': 0, 'max_local_deg': 0.0, 'max_local_deg_frame': 0}
                 for b in bones}
        samples = {}
        for f in range(0, nf + 1):
            try:
                pose = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, f, opts)
            except Exception:
                break
            for b in bones:
                r = bone_delta(pose, b)
                mx = maxes[b]
                if r['dist_cm'] > mx['max_dist_cm']:
                    mx['max_dist_cm'], mx['max_dist_frame'] = r['dist_cm'], f
                if r['local_deg'] > mx['max_local_deg']:
                    mx['max_local_deg'], mx['max_local_deg_frame'] = r['local_deg'], f
                if f in (0, mid):
                    samples.setdefault(b, {})['f%d' % f] = r
        for b in bones:
            sweep[b] = dict(maxes[b], frame0=samples.get(b, {}).get('f0'),
                            mid=dict(frame=mid, **(samples.get(b, {}).get('f%d' % mid) or {})))
        for c, b, kind, val in cfg['sweep_expect']:
            if c != clip or b not in sweep:
                continue
            got = sweep[b]['max_local_deg'] if kind == 'deg' else sweep[b]['max_dist_cm']
            ok = val is None and got > 0.05 or (val is not None and abs(got - val) < (ANG_TOL_DEG if kind == 'deg'
                                                                                        else POS_TOL_CM))
            tests.append({'sweep': b, 'kind': 'max_' + kind, 'expect': val, 'got': got, 'ok': bool(ok)})
    return tests, sweep


def import_clips(gun, skel, rig, info):
    P = paths_for(gun)
    tag = GUNS[gun]['tag']
    out = {}
    clips = info.setdefault('clips', {})
    for clip in CLIPS:
        name = 'A_%s_%s' % (tag, clip)
        path = P['clip'][clip]
        src = source_dir(gun) / (name + '.fbx')
        entry = {'path': path, 'source': str(src)}
        exists = EA.does_asset_exist(path)
        if not exists or REIMPORT:
            ok, new = interchange_import(src, P['anims'], anim_pipeline(skel))
            entry['imported'] = new
            REPORT['created'].extend(new)
            unexpected = [p for p in new if p != path]
            if unexpected:
                warn('%s import created extra assets %s' % (name, unexpected))
            if not EA.does_asset_exist(path):
                error('%s did not import (%s)' % (name, new))
                clips[clip] = entry
                continue
        entry['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
        seq = load(path)
        if not isinstance(seq, u.AnimSequence):
            error('%s is a %s' % (name, seq.get_class().get_name()))
            clips[clip] = entry
            continue
        if not exists or REIMPORT:
            touch(seq, not exists)
        entry['skeleton'] = pathish(seq.get_editor_property('skeleton'))
        if entry['skeleton'] != pathish(skel):
            error('%s is on skeleton %s, not %s' % (name, entry['skeleton'], pathish(skel)))
        entry['length_s'] = round(AL.get_sequence_length(seq), 4)
        nf = AL.get_num_frames(seq)
        entry['num_frames'] = nf
        try:
            entry['tracks'] = [str(n) for n in AL.get_animation_track_names(seq)]
        except Exception:
            entry['tracks'] = 'n/a'
        want = rig['clip_seconds'].get(clip)
        entry['rig_seconds'] = want
        lo, hi = (0.0, 0.05) if clip == 'Idle' else ((want - 0.02, want + 0.02) if want else (0, 99))
        entry['length_ok'] = lo <= entry['length_s'] <= hi
        if not entry['length_ok']:
            error('%s length %.4f s outside [%.3f, %.3f] (rig json %s s)' % (name, entry['length_s'], lo, hi, want))
        if clip != 'Idle' and not entry['tracks']:
            error('%s has no bone tracks' % name)
        if clip == 'Idle' and not entry['tracks']:
            REPORT['notes'].append('[%s] %s imported with no bone tracks (same as A_M4A1_Idle: Interchange drops '
                                   'the 2-key payload); an empty sequence evaluates to the reference pose = rest, '
                                   'which is what Idle encodes' % (gun, name))
        tests, sweep = motion_report(gun, clip, seq, nf)
        entry['motion'] = tests
        entry['sweep'] = sweep
        for t in tests:
            if not t['ok']:
                error('%s motion check failed: %s' % (name, {k: t.get(k) for k in (
                    'bone', 'sweep', 'frame', 'delta_cm', 'local_deg', 'expect_cm', 'expect_local_deg', 'expect',
                    'got', 'error') if k in t}))
        clips[clip] = entry
        out[clip] = seq
        log('clip', name, 'len', entry['length_s'], 'frames', nf, 'motion', all(t['ok'] for t in tests))
    return out


# ---------------------------------------------------------------------------------------------

def da_fingerprint():
    if not EA.does_asset_exist(DA_PATH):
        return None
    da = EA.load_asset(DA_PATH)
    out = {}
    for cpp in ('RiggedGun', 'GunIdle', 'GunFire', 'GunReload', 'GunChamber'):
        try:
            out[cpp] = pathish(da.get_editor_property(resolve(da, cpp, 'HoverPilotAssets')))
        except Exception:
            out[cpp] = 'n/a'
    return out


def m4a1_reference():
    """Read-only: the working M4A1 skeleton's root scale, for comparison with the EM guns."""
    if not EA.does_asset_exist(M4A1_SKEL):
        return None
    pose = u.AnimPoseExtensions.get_reference_pose(EA.load_asset(M4A1_SKEL))
    names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
    root = names[0]
    return {'skeleton': M4A1_SKEL, 'root': root, 'bone_count': len(names),
            'root_local_scale': vec(u.AnimPoseExtensions.get_bone_pose(pose, root, u.AnimPoseSpaces.LOCAL).scale3d),
            'muzzle_component_scale': vec(u.AnimPoseExtensions.get_bone_pose(pose, 'muzzle', u.AnimPoseSpaces.WORLD)
                                          .scale3d) if 'muzzle' in names else None}


def judge_root_scale():
    ref = m4a1_reference()
    REPORT['reference_m4a1'] = ref
    if not ROOT_SCALES:
        return
    same_as_m4a1 = bool(ref) and all(same(v, ref['root_local_scale']) for v in ROOT_SCALES.values())
    REPORT['root_scale_convention'] = {
        'guns': ROOT_SCALES, 'm4a1_root_local_scale': ref and ref['root_local_scale'], 'same_as_m4a1': same_as_m4a1,
        'meaning': 'no extra bone was inserted (the "Armature" Null is dropped), but its x100 node scale is folded '
                   'into the root bone: root local scale 100, child local translations in metres, component-space '
                   'positions correct in cm, and every bone/socket has COMPONENT-SPACE SCALE 100. Use '
                   'GetSocketLocation/rotation only, or strip scale (SnapToTargetNotIncludingScale / '
                   'GetSocketTransform(...).SetScale3D(1)) before attaching or spawning at a gun bone.'}
    msg = ('!!! ROOT BONE LOCAL SCALE x100 on %s (%s the M4A1, whose root local scale is %s). No extra "Armature" '
           'bone exists; see root_scale_convention in the receipt.' % (
               sorted(ROOT_SCALES), 'same as' if same_as_m4a1 else 'DIFFERENT from', ref and ref['root_local_scale']))
    if same_as_m4a1:
        warn(msg)
    else:
        error(msg)


def save_all():
    saved = []
    for asset in TOUCHED:
        path = pathish(asset)
        try:
            if EA.save_loaded_asset(asset, False):
                saved.append(path)
            else:
                error('save failed for ' + path)
        except Exception:
            error('save raised for %s: %s' % (path, traceback.format_exc(limit=1)))
    REPORT['saved'] = saved
    log('saved', len(saved))


def selected_guns():
    return [g for g in GUNS if not ONLY or g in ONLY]


def main():
    global EA, AT, ML, AL, GUN
    EA = u.EditorAssetLibrary
    AT = u.AssetToolsHelpers.get_asset_tools()
    ML = u.MaterialEditingLibrary
    AL = u.AnimationLibrary
    da_before = da_fingerprint()
    guns = selected_guns()
    pre = {}
    for gun in guns:
        pre[gun] = preflight(gun)
        REPORT['preflight'][gun] = {k: v for k, v in pre[gun].items() if k != 'rig'}
        if not pre[gun]['ok']:
            GUN = gun
            error('preflight failed: %s' % pre[gun]['problems'])
            GUN = None
    # Textures for every gun first (the master needs defaults), then the master, then per gun MI/mesh/clips.
    textures = {}
    for gun in guns:
        GUN = gun
        info = REPORT['guns'].setdefault(gun, {'paths': paths_for(gun)})
        if not pre[gun]['textures_complete']:
            error('Textures_2K/%s incomplete: %s' % (gun, pre[gun]['textures']))
            continue
        try:
            textures[gun] = import_textures(gun, info)
        except Exception:
            error('textures: ' + traceback.format_exc())
    GUN = None
    assert textures, 'no gun has textures; cannot build the master'
    first = textures.get('EM_11') or next(iter(textures.values()))
    master = build_master(first)
    for gun in guns:
        GUN = gun
        info = REPORT['guns'][gun]
        if not pre[gun]['ok']:
            info['skipped'] = 'preflight failed'
            continue
        try:
            mi = build_instance(gun, master, textures[gun], info) if gun in textures else None
            mesh, skel = import_mesh(gun, mi, pre[gun]['rig'], info)
            clips = import_clips(gun, skel, pre[gun]['rig'], info)
            missing = [c for c in CLIPS if c not in clips]
            if missing:
                error('clips missing: %s' % missing)
        except Exception:
            error(traceback.format_exc())
    GUN = None
    if REPORT['readback_mismatches']:
        error('read-back mismatches: %s' % REPORT['readback_mismatches'])
    save_all()
    judge_root_scale()
    da_after = da_fingerprint()
    REPORT['da_untouched'] = {'before': da_before, 'after': da_after, 'same': da_before == da_after}
    if da_before != da_after:
        error('DA_HoverPilot changed: %s -> %s' % (da_before, da_after))
    assets = [MASTER_PATH]
    for gun in guns:
        P = paths_for(gun)
        assets += [P['mesh'], P['skel'], P['mi']] + list(P['clip'].values()) + list(P['tex'].values())
    REPORT['assets'] = sorted(assets)
    REPORT['assets_exist'] = {a: bool(EA.does_asset_exist(a)) for a in assets}
    missing = [a for a, e in REPORT['assets_exist'].items() if not e]
    if missing:
        error('assets missing at the end: %s' % missing)
    REPORT['created'] = sorted(set(REPORT['created']))


def summary():
    per = {}
    for gun, g in REPORT['guns'].items():
        m = g.get('mesh', {})
        per[gun] = {'bones': m.get('bone_count'), 'len_cm': m.get('length_cm'),
                    'clips': {c: v.get('length_s') for c, v in g.get('clips', {}).items()},
                    'motion_ok': all(t.get('ok') for v in g.get('clips', {}).values() for t in v.get('motion', []))}
    return ('EMGUNS_IMPORT ok=%s guns=%s master=%s created=%d saved=%d warnings=%d errors=%d receipt=%s' % (
        REPORT['ok'], json.dumps(per), REPORT['master'].get('state'), len(REPORT['created']), len(REPORT['saved']),
        len(REPORT['warnings']), len(REPORT['errors']), RECEIPT))


def dry_run():
    plan = {'guns': {}, 'master': MASTER_PATH}
    for gun in selected_guns():
        pf = preflight(gun)
        plan['guns'][gun] = {'paths': paths_for(gun), 'preflight': pf}
    print('EMGUNS_IMPORT_PLAN', json.dumps(plan, default=str, indent=1), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    t0 = time.time()
    try:
        assert u, 'ImportEMGuns must run inside the Unreal Editor (use --dry-run elsewhere)'
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['seconds'] = round(time.time() - t0, 1)
        REPORT['ok'] = not REPORT['errors']
        write_receipt()
        line = summary()
        print(line, flush=True)
        for w in REPORT['warnings']:
            print('EMGUNS_IMPORT warning', w, flush=True)
        for e in REPORT['errors']:
            print('EMGUNS_IMPORT error', e, flush=True)
        if u:
            u.log_warning(line)
            for e in REPORT['errors']:
                u.log_error('EMGUNS_IMPORT error ' + e)
            u.SystemLibrary.quit_editor()


if DRY_RUN:
    dry_run()
else:
    run()
