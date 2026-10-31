"""ImportM4A1.py - bring the rigged M4A1 (Blender export) into the project and bind it to Vexa.

Creates / updates (idempotent, read-back verified, receipt-driven):
  /Game/HoverPrototype/Weapons/M4A1/Vendor/{Materials,Textures,Meshes}   vendor UE 4.26 assets (moved in-editor)
  /Game/HoverPrototype/Weapons/M4A1/SK_M4A1 (+ SK_M4A1_Skeleton)         Interchange skeletal mesh import
  /Game/HoverPrototype/Weapons/M4A1/Anims/A_M4A1_{Idle,IdleEmpty,Fire,FireLast,DryFire,Reload,ReloadTactical,Chamber}
                                                                          (v2 clip set, m4a1_rig.json 'clips_v2')
  /Game/HoverPrototype/DA_HoverPilot                                      Weapon|Rigged fields bound

Vendor assets: the .uasset files in SourceAssets/M4A1_Modular/UnrealFiles/M4A1 carry /Game/M4A1/... package
references, so they must first sit at Content/M4A1 (plain file copy, done by the caller before launching the
editor or by this script + registry rescan), then the folder is renamed in-editor to .../M4A1/Vendor so the
material instance -> texture references are fixed up. Leftover redirectors under /Game/M4A1 are deleted.

Textures: every vendor map keeps its source (4K) and gets MaxTextureSize 2048 when the source is larger;
maps already <= 2048 are left alone and listed in the receipt (never upscaled, never capped below 2K).

Mesh: Interchange (project default) with an override InterchangeGenericAssetsPipeline: skeletal only, no
materials/textures/physics asset/morph targets, normals and tangents from the file. Slots keep the FBX
material names (= vendor MI names) and get the vendor MI assigned by name. Clips are imported with
'import only animations' onto SK_M4A1_Skeleton. Sockets: the FBX brings none (the code resolves sockets OR
bones by name, see ResolveGunSocket in HoverPilot.cpp); USkeletalMeshSocket entries are attempted from Python
and the outcome is reported.

Receipt: D:/AFS_Comparisons/M4A1_20261029/import_receipt.json

Run (never concurrently with another editor instance):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/ImportM4A1.py" -nullrhi -unattended -nosplash
Flags (inside the quoted value, after the script path):
  --dry-run     print the plan only (works outside Unreal too)
  --reimport    re-import SK_M4A1 and the clips even when they exist
"""
import json
import os
import re
import shutil
import sys
import time
import traceback
import zipfile
from pathlib import Path

try:
    import unreal as u
except ImportError:
    u = None

ARGS = sys.argv[1:]
DRY_RUN = '--dry-run' in ARGS
REIMPORT = '--reimport' in ARGS

OUT = Path('D:/AFS_Comparisons/M4A1_20261029')
RECEIPT = OUT / 'import_receipt.json'
PROJECT = Path('M:/UnrealProjects/AFS')
CONTENT = PROJECT / 'Content'
SRC_VENDOR = PROJECT / 'SourceAssets/M4A1_Modular/UnrealFiles/M4A1'
TEXTURES_ZIP = PROJECT / 'SourceAssets/M4A1_Modular/Textures.zip'
RIGGED = PROJECT / 'SourceAssets/M4A1_Modular/Rigged'

STAGE = '/Game/M4A1'  # where the vendor package references point; staging only
M4A1 = '/Game/HoverPrototype/Weapons/M4A1'
VENDOR = M4A1 + '/Vendor'
ANIMS = M4A1 + '/Anims'
FALLBACK = M4A1 + '/Fallback'
MESH_PATH = M4A1 + '/SK_M4A1'
SKEL_PATH = M4A1 + '/SK_M4A1_Skeleton'
DA_PATH = '/Game/HoverPrototype/DA_HoverPilot'
VENDOR_SUBDIRS = ('Materials', 'Textures', 'Meshes')

# v2 clip set (SourceAssets/M4A1_Modular/Rigged/m4a1_rig.json 'clips_v2'): IdleEmpty, FireLast and
# ReloadTactical are new; the five v1 names were re-exported. Only the first six go on DA_HoverPilot's loose
# Weapon|Rigged fields (DA_FIELDS); the three empty-state clips are bound on DA_GunRig_M4A1 (AuthorGunRigs.py).
CLIPS = ['Idle', 'IdleEmpty', 'Fire', 'FireLast', 'DryFire', 'Reload', 'ReloadTactical', 'Chamber']
EXPECT_KEYS = {'Idle': 2, 'IdleEmpty': 2, 'Fire': 8, 'FireLast': 8, 'DryFire': 10, 'Reload': 145,
               'ReloadTactical': 145, 'Chamber': 67}  # keys at 60 fps
EXPECT_LENGTH = {'Idle': (0.0, 0.05), 'IdleEmpty': (0.0, 0.05), 'Fire': (0.10, 0.14), 'FireLast': (0.10, 0.14),
                 'DryFire': (0.13, 0.17), 'Reload': (2.35, 2.45), 'ReloadTactical': (2.35, 2.45),
                 'Chamber': (1.05, 1.15)}
# clip -> [(bone, frame, expected component-space delta cm (None = don't care))]; UE space X fwd, Y right, Z up.
# clips_v2 + v3 hand target (2026-10-30): the left hand pulls the mag 12 cm (f12-f27), it free-falls from the
# release point, parks at -70 cm from f43 (hidden by bone scale f41-f55) and the fresh mag pops in at the hand
# at f56 (belt target (6, -14, -42) minus the cup offset = (-8.109, -9.536, -40.233) from the rest head).
_MAG_V2 = [('magazine', 27, (0, 0, -12.0)), ('magazine', 48, (None, None, -70.0)),
           ('magazine', 66, (-8.109, -9.536, -40.233)), ('magazine', 102, (0, 0, 0))]
MOTION_CHECKS = {
    'Fire': [('bolt_carrier', 2, (-9.0, 0, 0)), ('bolt_carrier', 7, (0, 0, 0)), ('charging_handle', 2, (0, 0, 0))],
    'IdleEmpty': [('bolt_carrier', 0, (-8.2, 0, 0)), ('bolt_carrier', 1, (-8.2, 0, 0)), ('magazine', 0, (0, 0, 0))],
    'FireLast': [('bolt_carrier', 2, (-9.0, 0, 0)), ('bolt_carrier', 4, (-8.2, 0, 0)),
                 ('bolt_carrier', 7, (-8.2, 0, 0))],
    'Reload': [('bolt_carrier', 0, (-8.2, 0, 0)), ('bolt_carrier', 115, (-8.2, 0, 0)), ('bolt_carrier', 117, (0, 0, 0))]
              + _MAG_V2,
    'ReloadTactical': [('bolt_carrier', f, (0, 0, 0)) for f in (0, 27, 48, 66, 102, 115, 117, 144)] + _MAG_V2,
    'Chamber': [('charging_handle', 29, (-9.0, 0, 0)), ('charging_handle', 35, (-9.0, 0, 0)),
                ('charging_handle', 37, (0, 0, 0)), ('bolt_carrier', 29, (-9.0, 0, 0)),
                ('bolt_carrier', 35, (-9.0, 0, 0)), ('bolt_carrier', 37, (0, 0, 0))],
}
SOCKETS = ['muzzle', 'ejection_port', 'sight', 'grip_r', 'grip_l', 'mag_well']
EXPECT_BONES = ['root', 'body', 'bolt_carrier', 'charging_handle', 'magazine', 'trigger', 'selector',
                'mag_release', 'bolt_catch', 'muzzle', 'ejection_port', 'sight', 'grip_r', 'grip_l', 'mag_well']
SLOTS = ['Barrel', 'BoltCarrier', 'BufferTube', 'Buttstock', 'ChargingHandle', 'Flashlight', 'FrontGrip',
         'FrontRail', 'GasBlock', 'Glass', 'Laser', 'Magazine', 'Muzzel', 'OffsetRail', 'Optic', 'PistolGrip',
         'Receiver_Lower', 'Receiver_Upper', 'RedDot', 'Reflex', 'Silencer', 'SmallRail']
TEXTURE_MAX = 2048
# Slot -> TGA name stem inside Textures.zip (fallback master/MI build only when a vendor MI is broken).
ZIP_STEMS = {
    'Barrel': 'Barrel 20 inch', 'BoltCarrier': 'Bolt_Carrier',
    'BufferTube': 'Strike Industries - Advanced Receiver Extension', 'Buttstock': 'FAB Defense GL-SHOCK',
    'ChargingHandle': 'RADIAN WEAPONS AR-15 RAPTOR CHARGING HANDLE', 'Flashlight': 'ZenitCo Klesch 2PS',
    'FrontGrip': 'PTS Fortis Shift Vertical Grip', 'FrontRail': 'EMG SAI QD Rail',
    'GasBlock': 'J P ENTERPRISES GAS BLOCK', 'Laser': 'ATPIAL Aiming Laser', 'Magazine': 'Magpul PMAG D60',
    'Muzzel': 'BLACKOUT 51T FLASH HIDER', 'OffsetRail': 'NcSTAR_MPR',
    'Optic': 'Primary Arms SLx 3 Compact 3x32 Gen II Prism Scope', 'PistolGrip': 'TACTICAL DYNAMICS SKELETON GRIP',
    'Receiver_Lower': 'Lower Receiver', 'Receiver_Upper': 'Vltor_MUR', 'Reflex': 'Zenit BelOMO PK 06',
    'SmallRail': 'Magpul M-lok', 'Silencer': 'AAC 7.62-SDN-6 Silencer',
}
DA_FIELDS = {  # cpp name -> value key resolved at bind time
    'RiggedGun': 'mesh', 'GunIdle': 'Idle', 'GunFire': 'Fire', 'GunDryFire': 'DryFire', 'GunReload': 'Reload',
    'GunChamber': 'Chamber', 'GunMuzzleSocket': 'muzzle', 'GunEjectSocket': 'ejection_port',
    'GunSightSocket': 'sight', 'GunGripSocket': 'grip_r', 'GunSupportSocket': 'grip_l',
    'bRiggedGunSocketsDriveOffsets': True,
}

REPORT = {'ok': False, 'dry_run': DRY_RUN, 'reimport': REIMPORT, 'errors': [], 'warnings': [], 'notes': [],
          'created': [], 'saved': [], 'vendor': {}, 'textures': {}, 'materials': {}, 'mesh': {}, 'sockets': {},
          'clips': {}, 'da': {}, 'python_names': {}, 'readback_mismatches': [], 'texture_max': TEXTURE_MAX,
          'claim': 'Editor asset import/authoring only; no gameplay run, no rendered evidence'}
EA = AT = ML = AL = None
TOUCHED = []  # assets to save at the end


def log(*a):
    line = 'M4A1_IMPORT ' + ' '.join(str(x) for x in a)
    print(line, flush=True)
    if u:
        u.log(line)


def warn(msg):
    REPORT['warnings'].append(msg)
    log('warning', msg)


def write_receipt():
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(REPORT, indent=2, default=str))
    except Exception:
        print('M4A1_IMPORT receipt failed', traceback.format_exc(), flush=True)


# ---------------------------------------------------------------------------------------------
# Helpers (copied from AuthorNYCBosses.py; Foo -> foo, bFoo -> foo).

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
    key = scope + '.' + cpp
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


def touch(asset, created=False):
    if asset is not None and all(pathish(a) != pathish(asset) for a in TOUCHED):
        TOUCHED.append(asset)
    if created:
        REPORT['created'].append(pathish(asset))


def vec(v):
    return [round(v.x, 3), round(v.y, 3), round(v.z, 3)]


def list_assets(folder):
    return sorted(p.split('.')[0] for p in EA.list_assets(folder, recursive=True, include_folder=False))


# ---------------------------------------------------------------------------------------------
# 1. Vendor folder: plain copy at /Game/M4A1 -> in-editor move to .../M4A1/Vendor (reference fix-up).

def expected_vendor_names():
    out = {}
    for sub in VENDOR_SUBDIRS:
        out[sub] = sorted(p.stem for p in (SRC_VENDOR / sub).glob('*.uasset'))
    return out


def stage_vendor_files():
    """Plain file copy of the vendor folder to Content/M4A1 (where its package references resolve)."""
    copied = 0
    for sub in VENDOR_SUBDIRS:
        dst = CONTENT / 'M4A1' / sub
        dst.mkdir(parents=True, exist_ok=True)
        for src in (SRC_VENDOR / sub).glob('*.uasset'):
            if not (dst / src.name).is_file():
                shutil.copy2(str(src), str(dst / src.name))
                copied += 1
    return copied


def ensure_vendor():
    info = REPORT['vendor']
    want = expected_vendor_names()
    info['expected_counts'] = {k: len(v) for k, v in want.items()}

    def present(root):
        got = set(list_assets(root)) if EA.does_directory_exist(root) else set()
        missing = [root + '/' + sub + '/' + n for sub, names in want.items() for n in names
                   if root + '/' + sub + '/' + n not in got]
        return got, missing

    got, missing = present(VENDOR)
    if not missing:
        info['state'] = 'existing'
        info['assets'] = len(got)
        return
    info['missing_before'] = missing
    staged, stage_missing = present(STAGE)
    if stage_missing:
        copied = stage_vendor_files()
        info['staged_files_copied'] = copied
        reg = u.AssetRegistryHelpers.get_asset_registry()
        reg.scan_paths_synchronous([STAGE], True)
        staged, stage_missing = present(STAGE)
        assert not stage_missing, 'vendor staging incomplete at %s: %s' % (STAGE, stage_missing[:5])
    info['staged_assets'] = len(staged)
    # Make sure the (partial) destination does not block the move.
    if EA.does_directory_exist(VENDOR) and got:
        raise RuntimeError('%s exists with %d assets but is incomplete (%s); refusing to merge. Delete it and re-run.'
                           % (VENDOR, len(got), missing[:3]))
    t0 = time.time()
    ok = EA.rename_directory(STAGE, VENDOR)
    info['rename_ok'] = bool(ok)
    info['rename_seconds'] = round(time.time() - t0, 1)
    assert ok, 'rename_directory %s -> %s failed' % (STAGE, VENDOR)
    got, missing = present(VENDOR)
    assert not missing, 'after move, missing in %s: %s' % (VENDOR, missing[:5])
    info['assets'] = len(got)
    # Redirectors left at the old location: nothing references them (the whole set moved together).
    try:
        leftover = list_assets(STAGE) if EA.does_directory_exist(STAGE) else []
        info['redirectors_left'] = len(leftover)
        if EA.does_directory_exist(STAGE):
            info['stage_deleted'] = bool(EA.delete_directory(STAGE))
        stage_dir = CONTENT / 'M4A1'
        if stage_dir.is_dir():
            leftovers = [str(p) for p in stage_dir.rglob('*') if p.is_file()]
            if not leftovers:
                shutil.rmtree(str(stage_dir), ignore_errors=True)
            else:
                info['stage_files_left'] = leftovers[:10]
                warn('%s still holds %d files after the move (redirectors?)' % (stage_dir, len(leftovers)))
    except Exception:
        warn('stage cleanup: ' + traceback.format_exc(limit=1))
    info['state'] = 'moved'


# ---------------------------------------------------------------------------------------------
# 2. Textures: source size, MaxTextureSize cap (>= 2K, never lower).

def source_size(tex):
    try:
        text = u.HoverAuthoring.inspect_texture(tex)
        m = re.search(r'size=(\d+)x(\d+)', text)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return None


def cap_textures():
    folder = VENDOR + '/Textures'
    small = []
    for path in list_assets(folder):
        tex = EA.load_asset(path)
        if not isinstance(tex, u.Texture2D):
            continue
        name = path.rsplit('/', 1)[1]
        entry = {'size': [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()], 'source': source_size(tex),
                 'max_before': int(tex.get_editor_property('max_texture_size'))}
        src_max = max(entry['source']) if entry['source'] else max(entry['size'])
        entry['source_max'] = src_max
        changes = []
        if src_max > TEXTURE_MAX:
            put(tex, 'MaxTextureSize', TEXTURE_MAX, 'Texture2D[%s]' % name, changes)
        elif 0 < entry['max_before'] < min(src_max, TEXTURE_MAX):
            # A vendor cap below the source (and below 2K) would ship a smaller map than the source allows.
            put(tex, 'MaxTextureSize', 0, 'Texture2D[%s]' % name, changes)
        if src_max < TEXTURE_MAX:
            small.append('%s source %dx%d' % (name, entry['source'][0], entry['source'][1]) if entry['source']
                         else '%s %s' % (name, entry['size']))
        entry['max_after'] = int(tex.get_editor_property('max_texture_size'))
        entry['changes'] = changes
        for prop in ('srgb', 'compression_settings', 'lod_group'):
            try:
                entry[prop] = str(tex.get_editor_property(prop))
            except Exception:
                pass
        REPORT['textures'][name] = entry
        if changes:
            touch(tex)
    if small:
        REPORT['notes'].append('vendor maps below 2K (left as-is, not upscaled): ' + '; '.join(small))
    log('textures', len(REPORT['textures']), 'capped',
        sum(1 for t in REPORT['textures'].values() if t['changes']), 'below2K', len(small))


# ---------------------------------------------------------------------------------------------
# 3. Material instances: resolve, usage flag on the parents, fallback build when broken.

def mi_status(mi, name):
    row = {'path': pathish(mi), 'class': mi.get_class().get_name()}
    parent = mi.get_editor_property('parent') if isinstance(mi, u.MaterialInstance) else None
    row['parent'] = pathish(parent)
    row['textures'] = {}
    broken = []
    if parent is None and isinstance(mi, u.MaterialInstance):
        broken.append('no parent')
    if isinstance(mi, u.MaterialInstance):
        try:
            for pname in ML.get_texture_parameter_names(parent) if parent else []:
                tex = ML.get_material_instance_texture_parameter_value(mi, pname)
                if tex is None:
                    try:
                        tex = ML.get_material_default_texture_parameter_value(parent, pname)
                    except Exception:
                        tex = None
                row['textures'][str(pname)] = pathish(tex)
                if tex is None:
                    broken.append('texture parameter %s unresolved' % pname)
            for pv in (mi.get_editor_property('texture_parameter_values') or []):
                tex = pv.get_editor_property('parameter_value')
                pname = str(pv.get_editor_property('parameter_info').get_editor_property('name'))
                row['textures'].setdefault(pname, pathish(tex))
                if tex is None:
                    broken.append('override %s is null' % pname)
        except Exception:
            broken.append('parameter read failed: ' + traceback.format_exc(limit=1))
    row['broken'] = broken
    return row


def ensure_usage_flags(materials):
    for path in sorted(set(materials)):
        if not path:
            continue
        mat = EA.load_asset(path)
        if not isinstance(mat, u.Material):
            continue
        changes = []
        put(mat, 'bUsedWithSkeletalMesh', True, 'Material[%s]' % path.rsplit('/', 1)[1], changes)
        if changes:
            ML.recompile_material(mat)
            touch(mat)
        REPORT['materials'].setdefault('_parents', {})[path] = {
            'used_with_skeletal_mesh': bool(mat.get_editor_property('used_with_skeletal_mesh')),
            'changes': changes}


def check_materials():
    """Returns {slot: MaterialInterface} for every slot, building fallbacks for broken vendor MIs."""
    out = {}
    broken = {}
    parents = []
    for slot in SLOTS:
        path = VENDOR + '/Materials/' + slot
        if not EA.does_asset_exist(path):
            broken[slot] = 'missing vendor MI ' + path
            REPORT['materials'][slot] = {'broken': [broken[slot]]}
            continue
        mi = EA.load_asset(path)
        row = mi_status(mi, slot)
        REPORT['materials'][slot] = row
        if row['broken']:
            broken[slot] = row['broken']
            continue
        out[slot] = mi
        parents.append(row['parent'] if row['parent'] else pathish(mi))
    ensure_usage_flags(parents)
    if broken:
        warn('broken vendor material instances: %s' % broken)
        fb = build_fallback(sorted(broken))
        out.update(fb)
    return out


def build_fallback(slots):
    """Master + MIs from the TGA textures in Textures.zip for the given slots (only when a vendor MI is broken)."""
    out = {}
    stems = {s: ZIP_STEMS[s] for s in slots if s in ZIP_STEMS}
    if not stems:
        warn('no TGA source for broken slots %s (Glass/RedDot have no vendor textures)' % slots)
        return out
    extract = OUT / 'tga_extract'
    extract.mkdir(parents=True, exist_ok=True)
    norm_name = lambda s: re.sub(r'[^A-Za-z0-9]+', '', s).lower()
    with zipfile.ZipFile(str(TEXTURES_ZIP)) as z:
        members = {norm_name(m): m for m in z.namelist()}
        textures = {}
        for slot, stem in stems.items():
            textures[slot] = {}
            for kind in ('BaseColor', 'Normal', 'Metallic', 'Roughness'):
                key = norm_name('M4A1_' + stem + '_' + kind + '.tga')
                member = members.get(key)
                if not member:
                    warn('fallback %s: no %s TGA in Textures.zip' % (slot, kind))
                    continue
                target = extract / ('T_%s_%s.tga' % (slot, kind))
                if not target.is_file():
                    with z.open(member) as src, open(str(target), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                asset = FALLBACK + '/T_%s_%s' % (slot, kind)
                if not EA.does_asset_exist(asset):
                    task = u.AssetImportTask()
                    task.set_editor_property('filename', str(target))
                    task.set_editor_property('destination_path', FALLBACK)
                    task.set_editor_property('destination_name', 'T_%s_%s' % (slot, kind))
                    task.set_editor_property('automated', True)
                    task.set_editor_property('replace_existing', True)
                    task.set_editor_property('save', False)
                    AT.import_asset_tasks([task])
                tex = EA.load_asset(asset)
                if not isinstance(tex, u.Texture2D):
                    warn('fallback %s: import of %s failed' % (slot, target))
                    continue
                changes = []
                scope = 'Texture2D[fallback %s %s]' % (slot, kind)
                put(tex, 'SRGB', kind == 'BaseColor', scope, changes)
                put(tex, 'CompressionSettings', u.TextureCompressionSettings.TC_NORMALMAP if kind == 'Normal'
                    else (u.TextureCompressionSettings.TC_DEFAULT if kind == 'BaseColor'
                          else u.TextureCompressionSettings.TC_GRAYSCALE), scope, changes)
                put(tex, 'MaxTextureSize', TEXTURE_MAX, scope, changes)
                touch(tex, True)
                textures[slot][kind] = tex
    master_path = FALLBACK + '/M_M4A1_Fallback'
    if EA.does_asset_exist(master_path):
        master = load(master_path)
    else:
        master = AT.create_asset('M_M4A1_Fallback', FALLBACK, u.Material, u.MaterialFactoryNew())
        rows = [('BaseColor', u.MaterialSamplerType.SAMPLERTYPE_COLOR, -500, [('RGB', u.MaterialProperty.MP_BASE_COLOR)]),
                ('Normal', u.MaterialSamplerType.SAMPLERTYPE_NORMAL, -250, [('RGB', u.MaterialProperty.MP_NORMAL)]),
                ('Metallic', u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 0,
                 [('R', u.MaterialProperty.MP_METALLIC)]),
                ('Roughness', u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE, 250,
                 [('R', u.MaterialProperty.MP_ROUGHNESS)])]
        for param, sampler, y, outputs in rows:
            node = ML.create_material_expression(master, u.MaterialExpressionTextureSampleParameter2D, -420, y)
            node.set_editor_property('parameter_name', param)
            node.set_editor_property('sampler_type', sampler)
            for output, prop in outputs:
                ML.connect_material_property(node, output, prop)
        master.set_editor_property('used_with_skeletal_mesh', True)
        ML.recompile_material(master)
        touch(master, True)
    for slot in stems:
        mi_path = FALLBACK + '/MI_' + slot
        if EA.does_asset_exist(mi_path):
            mi = load(mi_path)
        else:
            mi = AT.create_asset('MI_' + slot, FALLBACK, u.MaterialInstanceConstant,
                                 u.MaterialInstanceConstantFactoryNew())
            ML.set_material_instance_parent(mi, master)
            touch(mi, True)
        for kind, tex in textures.get(slot, {}).items():
            if pathish(ML.get_material_instance_texture_parameter_value(mi, kind)) != pathish(tex):
                ML.set_material_instance_texture_parameter_value(mi, kind, tex)
                touch(mi)
        ML.update_material_instance(mi)
        out[slot] = mi
        REPORT['materials'][slot]['fallback'] = pathish(mi)
    return out


# ---------------------------------------------------------------------------------------------
# 4. Interchange imports.

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


def import_mesh(materials):
    info = REPORT['mesh']
    exists = EA.does_asset_exist(MESH_PATH)
    if not exists or REIMPORT:
        ok, new = interchange_import(RIGGED / 'SK_M4A1.fbx', M4A1, mesh_pipeline())
        info['imported'] = new
        assert EA.does_asset_exist(MESH_PATH), 'SK_M4A1 did not import (%s)' % new
        for p in new:
            REPORT['created'].append(p)
        extra = [p for p in new if p not in (MESH_PATH, SKEL_PATH)]
        if extra:
            warn('Interchange created extra assets beside the mesh: %s' % extra)
    info['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
    mesh = load(MESH_PATH)
    assert isinstance(mesh, u.SkeletalMesh), 'SK_M4A1 is a %s' % mesh.get_class().get_name()
    skel = mesh.get_editor_property('skeleton')
    assert skel, 'SK_M4A1 has no skeleton'
    info['skeleton'] = pathish(skel)
    if pathish(skel) != SKEL_PATH:
        warn('skeleton is %s, expected %s' % (pathish(skel), SKEL_PATH))
    if not exists or REIMPORT:
        touch(mesh, not exists)
        touch(skel, not exists)
    # Bounds.
    b = mesh.get_bounds()
    ext, org = b.box_extent, b.origin
    info['bounds_min_cm'] = vec(u.Vector(org.x - ext.x, org.y - ext.y, org.z - ext.z))
    info['bounds_max_cm'] = vec(u.Vector(org.x + ext.x, org.y + ext.y, org.z + ext.z))
    info['length_cm'] = round(ext.x * 2, 2)
    if not 110 < info['length_cm'] < 125:
        REPORT['errors'].append('SK_M4A1 length %.1f cm is not life size' % info['length_cm'])
    try:
        info['physics_asset'] = pathish(mesh.get_editor_property('physics_asset'))
    except Exception:
        info['physics_asset'] = 'n/a'
    try:
        info['lods'] = int(u.SkeletalMeshEditorSubsystem.get_lod_count(mesh))
    except Exception:
        info['lods'] = 'n/a'
    # Bones (reference pose, component space).
    pose = u.AnimPoseExtensions.get_reference_pose(skel)
    names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
    info['bones'] = names
    info['bone_count'] = len(names)
    missing = [b for b in EXPECT_BONES if b not in names]
    if missing or names[0] != 'root':
        REPORT['errors'].append('skeleton bones %s (missing %s)' % (names, missing))
    ref = {}
    for bn in names:
        t = u.AnimPoseExtensions.get_bone_pose(pose, bn, u.AnimPoseSpaces.WORLD)
        xa = t.rotation.rotate_vector(u.Vector(1, 0, 0))
        ref[bn] = {'loc_cm': vec(t.translation), 'x_axis': vec(xa)}
    info['ref_pose_component_space'] = ref
    # Material slots.
    rows = list(mesh.get_editor_property('materials'))
    slot_names = [str(m.get_editor_property('material_slot_name')) for m in rows]
    info['slots_before'] = [{'slot': s, 'material': pathish(m.get_editor_property('material_interface'))}
                            for s, m in zip(slot_names, rows)]
    if slot_names != SLOTS:
        warn('slot order/names differ from the rig JSON: %s' % slot_names)
    changed = False
    unmatched = []
    for s, m in zip(slot_names, rows):
        target = materials.get(s)
        if target is None:
            unmatched.append(s)
            continue
        if pathish(m.get_editor_property('material_interface')) != pathish(target):
            m.set_editor_property('material_interface', target)
            changed = True
    if changed:
        mesh.set_editor_property('materials', rows)
        touch(mesh)
    if unmatched:
        REPORT['errors'].append('no material for slots %s' % unmatched)
    rows = list(mesh.get_editor_property('materials'))
    info['slots'] = [{'slot': str(m.get_editor_property('material_slot_name')),
                      'material': pathish(m.get_editor_property('material_interface'))} for m in rows]
    for row in info['slots']:
        want = materials.get(row['slot'])
        if want is not None and row['material'] != pathish(want):
            REPORT['readback_mismatches'].append({'field': 'SK_M4A1.slot ' + row['slot'],
                                                  'expected': pathish(want), 'actual': row['material']})
    try:
        preview = AL.get_skeleton_preview_mesh(skel, False)
        if pathish(preview) != MESH_PATH:
            AL.set_skeleton_preview_mesh(skel, mesh, True)
            touch(skel)
    except Exception:
        warn('preview mesh not set: ' + traceback.format_exc(limit=1))
    return mesh, skel


def ensure_sockets(mesh, skel):
    """Mesh sockets named after the socket bones (identity local transform). Reports what was possible."""
    info = REPORT['sockets']
    try:
        existing = [str(mesh.get_socket_by_index(i).get_editor_property('socket_name'))
                    for i in range(mesh.num_sockets())]
    except Exception:
        existing = []
        info['list_error'] = traceback.format_exc(limit=1)
    info['before'] = existing
    missing = [s for s in SOCKETS if s not in existing]
    added = []
    if missing:
        try:
            rows = list(mesh.get_editor_property('sockets'))
            for name in missing:
                sock = u.new_object(u.SkeletalMeshSocket, outer=mesh)
                sock.set_editor_property('socket_name', name)
                sock.set_editor_property('bone_name', name)
                rows.append(sock)
                added.append(name)
            mesh.set_editor_property('sockets', rows)
            touch(mesh)
        except Exception:
            added = []
            info['add_error'] = traceback.format_exc(limit=1)
            REPORT['notes'].append('USkeletalMeshSocket entries could not be authored from Python (%s); the '
                                   'pilot resolves socket names as bones (ResolveGunSocket falls back to '
                                   'FindBoneIndex) and component attachment by bone name works the same way'
                                   % info['add_error'].strip().splitlines()[-1])
    try:
        after = [str(mesh.get_socket_by_index(i).get_editor_property('socket_name'))
                 for i in range(mesh.num_sockets())]
    except Exception:
        after = existing + added
    info['after'] = after
    info['added'] = added
    info['resolved_as'] = {s: ('socket' if s in after else 'bone') for s in SOCKETS}
    info['positions_cm'] = {s: REPORT['mesh']['ref_pose_component_space'].get(s, {}).get('loc_cm') for s in SOCKETS}
    bad = [s for s in SOCKETS if s not in REPORT['mesh']['bones']]
    if bad:
        REPORT['errors'].append('socket bones missing on the skeleton: %s' % bad)


def derive_idle_empty(seq, source, frame):
    """Key every bone of the track-less A_M4A1_IdleEmpty from A_M4A1_FireLast's last frame (local space).

    m4a1_rig.json clips_v2 defines FireLast's last frame as the IdleEmpty pose (bolt_carrier -8.2, bolt_catch
    10 deg, magazine seated, trigger released). Interchange drops the payload of every 2-key clip (the Baked
    Transforms ensure in InterchangeAnimSequenceFactory), so the pose is re-keyed here through the sequence's
    AnimationDataController on the frame count Interchange already gave the clip."""
    opts = u.AnimPoseEvaluationOptions()
    for prop, val in (('evaluation_type', u.AnimDataEvalType.RAW), ('retarget', False),
                      ('extract_root_motion', False)):
        try:
            opts.set_editor_property(prop, val)
        except Exception:
            pass
    pose = u.AnimPoseExtensions.get_anim_pose_at_frame(source, frame, opts)
    bones = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
    keys = AL.get_num_frames(seq) + 1
    ctrl = seq.get_editor_property('controller')
    ctrl.open_bracket('AFS: IdleEmpty from FireLast f%d' % frame, False)
    try:
        for bone in bones:
            t = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.LOCAL)
            ctrl.add_bone_curve(bone, False)
            ctrl.set_bone_track_keys(bone, [t.translation] * keys, [t.rotation] * keys, [t.scale3d] * keys, False)
    finally:
        ctrl.close_bracket(False)
    return {'source': pathish(source), 'source_frame': frame, 'bones': len(bones), 'keys': keys}


def import_clips(skel):
    out = {}
    # IdleEmpty last: when Interchange leaves it track-less it is re-keyed from FireLast (derive_idle_empty).
    for clip in [c for c in CLIPS if c != 'IdleEmpty'] + ['IdleEmpty']:
        name = 'A_M4A1_' + clip
        path = ANIMS + '/' + name
        entry = {'path': path}
        exists = EA.does_asset_exist(path)
        if not exists or REIMPORT:
            ok, new = interchange_import(RIGGED / (name + '.fbx'), ANIMS, anim_pipeline(skel))
            entry['imported'] = new
            for p in new:
                REPORT['created'].append(p)
            if not EA.does_asset_exist(path):
                REPORT['errors'].append('%s did not import (%s)' % (name, new))
                REPORT['clips'][clip] = entry
                continue
        entry['state'] = 'imported' if (not exists or REIMPORT) else 'existing'
        seq = load(path)
        if not isinstance(seq, u.AnimSequence):
            REPORT['errors'].append('%s is a %s' % (name, seq.get_class().get_name()))
            REPORT['clips'][clip] = entry
            continue
        if not exists or REIMPORT:
            touch(seq, not exists)
        entry['skeleton'] = pathish(seq.get_editor_property('skeleton'))
        if entry['skeleton'] != pathish(skel):
            REPORT['errors'].append('%s is on skeleton %s, not %s' % (name, entry['skeleton'], pathish(skel)))
        entry['length_s'] = round(AL.get_sequence_length(seq), 4)
        entry['num_frames'] = AL.get_num_frames(seq)
        try:
            entry['tracks'] = [str(n) for n in AL.get_animation_track_names(seq)]
        except Exception:
            entry['tracks'] = 'n/a'
        lo, hi = EXPECT_LENGTH[clip]
        entry['length_ok'] = lo <= entry['length_s'] <= hi
        # Interchange pads a 2-key clip by one key (Idle: 3 keys, 0.0333 s), so allow +-1 key.
        entry['keys'] = entry['num_frames'] + 1
        entry['expect_keys'] = EXPECT_KEYS[clip]
        entry['keys_ok'] = abs(entry['keys'] - EXPECT_KEYS[clip]) <= 1
        if not entry['keys_ok']:
            REPORT['errors'].append('%s has %d keys, expected %d' % (name, entry['keys'], EXPECT_KEYS[clip]))
        if not entry['length_ok']:
            REPORT['errors'].append('%s length %.4f s outside [%.3f, %.3f]' % (name, entry['length_s'], lo, hi))
        if clip == 'IdleEmpty' and not entry['tracks'] and 'FireLast' in out:
            # Unlike Idle it is NOT the rest pose: an empty sequence would idle with the bolt home.
            entry['derived'] = derive_idle_empty(seq, out['FireLast'], EXPECT_KEYS['FireLast'] - 1)
            touch(seq)
            entry['tracks'] = [str(n) for n in AL.get_animation_track_names(seq)]
            entry['length_s'] = round(AL.get_sequence_length(seq), 4)
            REPORT['notes'].append('A_M4A1_IdleEmpty imported with no bone tracks (the 2-key Interchange case that '
                                   'empties A_M4A1_Idle); re-keyed from A_M4A1_FireLast f7 (= IdleEmpty pose in '
                                   'clips_v2): %d bones x %d keys' % (entry['derived']['bones'],
                                                                     entry['derived']['keys']))
        elif clip == 'IdleEmpty' and not entry['tracks']:
            REPORT['errors'].append('A_M4A1_IdleEmpty has no bone tracks and FireLast is unavailable to re-key it')
        if clip not in ('Idle', 'IdleEmpty') and not entry['tracks']:
            REPORT['errors'].append('%s has no bone tracks' % name)
        if clip == 'Idle' and not entry['tracks']:
            REPORT['notes'].append('A_M4A1_Idle imported with no bone tracks (Interchange pads the 2-key clip and '
                                   'drops the payload: "unexpected number of Baked Transforms" ensure); an empty '
                                   'sequence evaluates to the reference pose, which is the rest pose Idle encodes '
                                   '(bolt home, magazine seated), so the looping idle is visually correct')
        entry['motion'] = motion_checks(seq, clip)
        for t in entry['motion']:
            if not t['ok']:
                REPORT['errors'].append('%s %s f%d delta %s expected %s' % (name, t['bone'], t['frame'],
                                                                           t['delta_cm'], t['expect_cm']))
        REPORT['clips'][clip] = entry
        out[clip] = seq
        log('clip', name, 'len', entry['length_s'], 'frames', entry['num_frames'], 'motion',
            all(t['ok'] for t in entry['motion']))
    return out


def motion_checks(seq, clip):
    tests = []
    opts = u.AnimPoseEvaluationOptions()
    for prop, val in (('evaluation_type', u.AnimDataEvalType.RAW), ('retarget', False),
                      ('extract_root_motion', False)):
        try:
            opts.set_editor_property(prop, val)
        except Exception:
            pass
    checks = MOTION_CHECKS.get(clip, [])
    if clip == 'DryFire':
        checks = [('trigger', 4, (None, None, None))]
    for bone, frame, expect in checks:
        try:
            pose = u.AnimPoseExtensions.get_anim_pose_at_frame(seq, frame, opts)
            cur = u.AnimPoseExtensions.get_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD)
            ref = u.AnimPoseExtensions.get_ref_bone_pose(pose, bone, u.AnimPoseSpaces.WORLD)
            d = [cur.translation.x - ref.translation.x, cur.translation.y - ref.translation.y,
                 cur.translation.z - ref.translation.z]
            rot = (cur.rotation.rotator().pitch - ref.rotation.rotator().pitch)
            ok = all(e is None or abs(d[i] - e) < 0.4 for i, e in enumerate(expect))
            if clip == 'DryFire':
                ok = abs(rot) > 2.0 or max(abs(x) for x in d) > 0.05  # trigger must move somehow
            tests.append({'bone': bone, 'frame': frame, 'delta_cm': [round(v, 3) for v in d],
                          'pitch_delta_deg': round(rot, 2), 'expect_cm': list(expect), 'ok': ok})
        except Exception:
            tests.append({'bone': bone, 'frame': frame, 'ok': False, 'error': traceback.format_exc(limit=1)})
    return tests


# ---------------------------------------------------------------------------------------------
# 5. DA binding.

def bind_da(mesh, clips):
    da = load(DA_PATH)
    scope = 'HoverPilotAssets'
    info = REPORT['da']
    info['class'] = da.get_class().get_name()
    values = {}
    for cpp, key in DA_FIELDS.items():
        if key == 'mesh':
            values[cpp] = mesh
        elif key in clips:
            values[cpp] = clips[key]
        elif isinstance(key, bool):
            values[cpp] = key
        else:
            values[cpp] = u.Name(key)
    changes = []
    for cpp, value in values.items():
        put(da, cpp, value, scope, changes)
    info['changes'] = changes
    info['gun_kept'] = pathish(da.get_editor_property(resolve(da, 'Gun', scope)))
    for cpp in ('GunMuzzle', 'GunForward', 'GunGrip', 'GunSupportGrip', 'GunSight'):
        try:
            info['fallback_' + cpp] = vec(da.get_editor_property(resolve(da, cpp, scope)))
        except Exception:
            info['fallback_' + cpp] = 'n/a'
    if changes:
        touch(da)
    readback = {}
    ok = True
    for cpp, value in values.items():
        name = resolve(da, cpp, scope)
        got = norm(da.get_editor_property(name))
        readback[cpp] = got
        if not check(da, cpp, value, scope):
            ok = False
    info['readback'] = readback
    info['bound'] = ok
    return ok


# ---------------------------------------------------------------------------------------------
# 6. Texture gate for the bound materials.

def texture_gate(materials):
    bound = set()
    for slot, mi in materials.items():
        row = REPORT['materials'].get(slot, {})
        for tex in (row.get('textures') or {}).values():
            if tex:
                bound.add(tex)
    results = {}
    small = []
    for path in sorted(bound):
        tex = EA.load_asset(path)
        if not isinstance(tex, u.Texture2D):
            continue
        src = source_size(tex) or (tex.blueprint_get_size_x(), tex.blueprint_get_size_y())
        mx = int(tex.get_editor_property('max_texture_size'))
        effective = min(max(src), mx) if mx > 0 else max(src)
        results[path] = {'source': list(src), 'max_texture_size': mx, 'effective': effective}
        if mx not in (0,) and mx < TEXTURE_MAX:
            REPORT['errors'].append('%s MaxTextureSize %d < %d' % (path, mx, TEXTURE_MAX))
        if max(src) < TEXTURE_MAX:
            small.append('%s %dx%d' % (path.rsplit('/', 1)[1], src[0], src[1]))
    REPORT['texture_gate'] = {'bound_textures': len(results), 'below_2k_sources': small, 'details': results}
    if small:
        REPORT['notes'].append('bound textures whose SOURCE is below 2K (vendor shipped them that way; not upscaled): '
                               + '; '.join(small))
    REPORT['texture_max'] = TEXTURE_MAX
    log('texture gate bound', len(results), 'below2K', len(small))


# ---------------------------------------------------------------------------------------------

def save_all():
    saved = []
    for asset in TOUCHED:
        path = pathish(asset)
        try:
            if EA.save_loaded_asset(asset, False):
                saved.append(path)
            else:
                REPORT['errors'].append('save failed for ' + path)
        except Exception:
            REPORT['errors'].append('save raised for %s: %s' % (path, traceback.format_exc(limit=1)))
    REPORT['saved'] = saved
    log('saved', len(saved))


def main():
    global EA, AT, ML, AL
    EA = u.EditorAssetLibrary
    AT = u.AssetToolsHelpers.get_asset_tools()
    ML = u.MaterialEditingLibrary
    AL = u.AnimationLibrary
    for p in [RIGGED / 'SK_M4A1.fbx'] + [RIGGED / ('A_M4A1_%s.fbx' % c) for c in CLIPS]:
        assert p.is_file(), 'missing rig export ' + str(p)
    assert EA.does_asset_exist(DA_PATH), 'missing ' + DA_PATH
    ensure_vendor()
    cap_textures()
    materials = check_materials()
    mesh, skel = import_mesh(materials)
    ensure_sockets(mesh, skel)
    clips = import_clips(skel)
    missing_clips = [c for c in CLIPS if c not in clips]
    if missing_clips:
        raise RuntimeError('clips missing: %s' % missing_clips)
    REPORT['da_bound'] = bind_da(mesh, clips)
    texture_gate(materials)
    if REPORT['readback_mismatches']:
        REPORT['errors'].append('read-back mismatches: %s' % REPORT['readback_mismatches'])
    save_all()
    REPORT['assets'] = sorted(set([MESH_PATH, SKEL_PATH] + [ANIMS + '/A_M4A1_' + c for c in CLIPS] +
                                  [VENDOR + '/' + s for s in VENDOR_SUBDIRS] + [DA_PATH]))
    REPORT['created'] = sorted(set(REPORT['created']))


def summary():
    return ('M4A1_IMPORT ok=%s vendor=%s textures=%d capped=%d mesh=%s bones=%s slots=%d clips=%s sockets=%s '
            'da_bound=%s saved=%d warnings=%d errors=%d receipt=%s' % (
                REPORT['ok'], REPORT['vendor'].get('state'), len(REPORT['textures']),
                sum(1 for t in REPORT['textures'].values() if t.get('changes')), REPORT['mesh'].get('state'),
                REPORT['mesh'].get('bone_count'), len(REPORT['mesh'].get('slots', [])),
                {c: v.get('length_s') for c, v in REPORT['clips'].items()}, REPORT['sockets'].get('resolved_as'),
                REPORT.get('da_bound'), len(REPORT['saved']), len(REPORT['warnings']), len(REPORT['errors']),
                RECEIPT))


def dry_run():
    plan = {'vendor_src': str(SRC_VENDOR), 'vendor_expected': expected_vendor_names(), 'stage': STAGE,
            'vendor_dest': VENDOR, 'mesh': MESH_PATH, 'skeleton': SKEL_PATH,
            'clips': [ANIMS + '/A_M4A1_' + c for c in CLIPS], 'da': DA_PATH,
            'da_fields': {cpp: candidates(cpp) for cpp in DA_FIELDS}, 'slots': SLOTS, 'sockets': SOCKETS,
            'rigged_present': {p.name: p.is_file() for p in [RIGGED / 'SK_M4A1.fbx'] +
                               [RIGGED / ('A_M4A1_%s.fbx' % c) for c in CLIPS]},
            'textures_zip': TEXTURES_ZIP.is_file()}
    print('M4A1_IMPORT_PLAN', json.dumps(plan, default=str, indent=1), flush=True)
    if u:
        u.SystemLibrary.quit_editor()


def run():
    try:
        assert u, 'ImportM4A1 must run inside the Unreal Editor (use --dry-run elsewhere)'
        main()
    except Exception:
        REPORT['errors'].append(traceback.format_exc())
    finally:
        REPORT['ok'] = not REPORT['errors'] and bool(REPORT.get('da_bound'))
        write_receipt()
        line = summary()
        print(line, flush=True)
        for w in REPORT['warnings']:
            print('M4A1_IMPORT warning', w, flush=True)
        for e in REPORT['errors']:
            print('M4A1_IMPORT error', e, flush=True)
        if u:
            u.log_warning(line)
            for e in REPORT['errors']:
                u.log_error('M4A1_IMPORT error ' + e)
            u.SystemLibrary.quit_editor()


if DRY_RUN:
    dry_run()
else:
    run()
