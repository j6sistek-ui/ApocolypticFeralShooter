"""Add a near-camera dither fade to the six NYC zombie body materials.

Why: zombie capsules and meshes ignore ECC_Camera on purpose (HoverCyberCity.cpp, AHoverCyberZombie::BeginPlay),
so the survival OTS spring arm never pulls in for them and a zombie standing at the third-person camera fills
the lens. This pass makes the body dissolve as it nears the lens instead:

    ScalarParameter NYC_FadeLength (70) --+
    ScalarParameter NYC_FadeOffset (15) --+--> CameraDepthFade --(x existing OpacityMask, if any)-->
        DitherTemporalAA (Desc 'NYC_NearCameraFade') --> OpacityMask
    BlendMode Opaque -> Masked, OpacityMaskClipValue 0.333, shading model and every other input untouched.

Which materials: for DA_Standard01..04, DA_Brute and DA_Kid under /Game/HoverPrototype/ZombieEngine/Variants/,
the AppearanceMesh (the mesh AHoverCyberZombie::BeginPlay puts on the body; it then calls EmptyOverrideMaterials,
so the mesh's own slot materials are what renders) is read slot by slot, and every slot material is resolved the
way the renderer will see it. Design doc Section 10 notes the SK_<Name> slots serialize a reference to a missing
M_<Name> while M_<Name>_0 exists, so M_<Name>_0 is always processed as well. The receipt records, per body, which
material each slot resolves to and whether it is M_<Name>_0.

Ownership rules:
  - a plain UMaterial is edited only when it lives under /Game/HoverPrototype/ (owner-made);
  - a MaterialInstance is walked to its base UMaterial; the base is edited only when it is under
    /Game/HoverPrototype/ (never a vendor or engine master); every skipped instance is reported;
  - an empty slot (renders with the engine default surface material) is reported, never "fixed": reassigning
    slots would mean resaving the meshes, which this script does not own.

Idempotent: a material that already holds an expression whose Desc is 'NYC_NearCameraFade' is left alone.
A material is saved only after its read-back checks pass and RecompileMaterial reports no error; nothing else
is saved. Meshes and DAs are hashed before/after to prove they are untouched.
Receipt: D:/AFS_Comparisons/NYCSurvival_<YYYYMMDD>/camera_fade_receipt.json

Run (never concurrently with another editor run):
  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject
      -ExecutePythonScript="M:/UnrealProjects/AFS/Scripts/AddZombieCameraFade.py" -nullrhi -unattended -nosplash
Flags (inside the quoted -ExecutePythonScript value, after the script path):
  --dry-run   resolve and report every material; create no node and save nothing
"""
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path

import unreal as u

DRY_RUN = '--dry-run' in sys.argv[1:]
OUT = Path('D:/AFS_Comparisons/NYCSurvival_' + time.strftime('%Y%m%d'))
RECEIPT = OUT / 'camera_fade_receipt.json'
VARIANTS = '/Game/HoverPrototype/ZombieEngine/Variants/'
BODIES = ['Standard01', 'Standard02', 'Standard03', 'Standard04', 'Brute', 'Kid']
OWNED = '/Game/HoverPrototype/'
TAG = 'NYC_NearCameraFade'
FADE_LENGTH = 70.0
FADE_OFFSET = 15.0
CLIP = 0.333
# Both are engine material functions (Engine/Content/Functions), not native expression classes in 5.8.
CAMERA_DEPTH_FADE = '/Engine/Functions/Engine_MaterialFunctions01/Opacity/CameraDepthFade'
DITHER_TEMPORAL_AA = '/Engine/Functions/Engine_MaterialFunctions02/Utility/DitherTemporalAA'
# Input pin names as serialized in the two function assets.
PIN_FADE_LENGTH = 'Fade Length'
PIN_FADE_OFFSET = 'Fade Offset'
PIN_ALPHA = 'Alpha Threshold'

EA = u.EditorAssetLibrary
ML = u.MaterialEditingLibrary
CONTENT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
R = {'dry_run': DRY_RUN, 'bodies': {}, 'materials': {}, 'skipped': [], 'hashes': {}, 'errors': [],
     'settings': {'fade_length': FADE_LENGTH, 'fade_offset': FADE_OFFSET, 'clip': CLIP, 'tag': TAG}}


def pkg(obj_or_path):
    p = obj_or_path if isinstance(obj_or_path, str) else obj_or_path.get_path_name()
    return p.split('.')[0]


def file_of(package):
    if not package.startswith('/Game/'):
        return None
    base = str(CONTENT / package[len('/Game/'):])
    for ext in ('.uasset', '.umap'):
        if Path(base + ext).is_file():
            return Path(base + ext)
    return Path(base + '.uasset')


def sha(package):
    f = file_of(package)
    return hashlib.sha256(f.read_bytes()).hexdigest() if f and f.is_file() else None


def hash_before(package):
    R['hashes'].setdefault(package, {'file': str(file_of(package)), 'before': sha(package), 'after': None})


def has_tag(mat):
    return any(str(e.get_editor_property('desc')) == TAG for e in ML.get_material_expressions(mat))


def base_of(mi):
    """Walk MaterialInstance parents to the UMaterial; returns (base or None, chain of paths)."""
    chain, cur = [], mi
    for _ in range(16):
        chain.append(cur.get_path_name())
        if isinstance(cur, u.Material):
            return cur, chain
        if not isinstance(cur, u.MaterialInstance):
            return None, chain
        cur = cur.get_editor_property('parent')
        if cur is None:
            chain.append(None)
            return None, chain
    return None, chain


def connect(src, src_out, dst, dst_in):
    if not ML.connect_material_expressions(src, src_out, dst, dst_in):
        raise RuntimeError('connect %s.%r -> %s.%r failed; inputs on target: %s' % (
            src.get_name(), src_out, dst.get_name(), dst_in, list(ML.get_material_expression_input_names(dst))))


def function_call(mat, path, x, y):
    fn = u.load_asset(path)
    assert fn, 'missing engine material function ' + path
    node = ML.create_material_expression(mat, u.MaterialExpressionMaterialFunctionCall, x, y)
    assert node and node.set_material_function(fn), 'set_material_function failed for ' + path
    return node


def scalar(mat, name, value, x, y):
    node = ML.create_material_expression(mat, u.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property('parameter_name', name)
    node.set_editor_property('default_value', value)
    return node


def apply_fade(mat):
    """Builds the fade graph on one owned UMaterial. Returns a dict describing what happened."""
    info = {'blend_before': str(mat.get_editor_property('blend_mode')),
            'clip_before': float(mat.get_editor_property('opacity_mask_clip_value')),
            'shading_model': str(mat.get_editor_property('shading_model')),
            'expressions_before': ML.get_num_material_expressions(mat)}
    if has_tag(mat):
        info['action'] = 'already'
        return info
    blend = mat.get_editor_property('blend_mode')
    if blend not in (u.BlendMode.BLEND_OPAQUE, u.BlendMode.BLEND_MASKED):
        info['action'] = 'skipped: blend mode %s is not Opaque/Masked' % blend
        return info
    prev = ML.get_material_property_input_node(mat, u.MaterialProperty.MP_OPACITY_MASK)
    prev_out = ML.get_material_property_input_node_output_name(mat, u.MaterialProperty.MP_OPACITY_MASK) if prev else ''
    info['opacity_mask_before'] = prev.get_path_name() if prev else None
    if DRY_RUN:
        info['action'] = 'would apply'
        return info
    length = scalar(mat, 'NYC_FadeLength', FADE_LENGTH, -1100, 900)
    offset = scalar(mat, 'NYC_FadeOffset', FADE_OFFSET, -1100, 1000)
    fade = function_call(mat, CAMERA_DEPTH_FADE, -800, 920)
    connect(length, '', fade, PIN_FADE_LENGTH)
    connect(offset, '', fade, PIN_FADE_OFFSET)
    src = fade
    if prev:
        # keep any existing cut-out (none expected on these imports) and fade on top of it
        mul = ML.create_material_expression(mat, u.MaterialExpressionMultiply, -550, 920)
        connect(prev, prev_out, mul, 'A')
        connect(fade, '', mul, 'B')
        src = mul
    dither = function_call(mat, DITHER_TEMPORAL_AA, -350, 920)
    dither.set_editor_property('desc', TAG)
    connect(src, '', dither, PIN_ALPHA)
    # ConnectMaterialProperty documents no empty-name fallback (only ConnectMaterialExpressions does), so try the
    # DitherTemporalAA output's serialized name 'Result' first and the empty name second.
    for out_name in ('Result', ''):
        if ML.connect_material_property(dither, out_name, u.MaterialProperty.MP_OPACITY_MASK):
            info['opacity_mask_output_name'] = out_name
            break
    else:
        raise RuntimeError('connect_material_property OpacityMask failed on %s (tried Result and empty name)' % mat.get_path_name())
    mat.set_editor_property('blend_mode', u.BlendMode.BLEND_MASKED)
    mat.set_editor_property('opacity_mask_clip_value', CLIP)
    # bUsedWithSkeletalMesh is deprecated in 5.8: go through the usage accessors
    if not ML.has_material_usage(mat, u.MaterialUsage.MATUSAGE_SKELETAL_MESH):
        ML.set_base_material_usage(mat, u.MaterialUsage.MATUSAGE_SKELETAL_MESH, True)
        info['set_skeletal_mesh_usage'] = True
    errors = ML.recompile_material(mat)
    info['compile_errors'] = [str(e) for e in (errors or [])]
    # read back before saving
    assert mat.get_editor_property('blend_mode') == u.BlendMode.BLEND_MASKED, 'blend mode did not stick'
    assert abs(float(mat.get_editor_property('opacity_mask_clip_value')) - CLIP) < 1e-4, 'clip value did not stick'
    assert ML.get_material_property_input_node(mat, u.MaterialProperty.MP_OPACITY_MASK) == dither, 'OpacityMask not wired'
    assert has_tag(mat), 'tag node missing after build'
    assert str(mat.get_editor_property('shading_model')) == info['shading_model'], 'shading model changed'
    if info['compile_errors']:
        info['action'] = 'not saved: compile errors'
        return info
    assert EA.save_loaded_asset(mat, False), 'save failed for ' + mat.get_path_name()
    info['action'] = 'applied'
    info['expressions_after'] = ML.get_num_material_expressions(mat)
    info['dither_inputs'] = list(ML.get_material_expression_input_names(dither))
    info['fade_inputs'] = list(ML.get_material_expression_input_names(fade))
    return info


def collect():
    """Returns {base material path: {'material': UMaterial, 'sources': [...]}} for owned bases."""
    targets = {}

    def consider(body, label, mi):
        entry = {'source': label, 'material': mi.get_path_name() if mi else None}
        if mi is None:
            entry['resolves_to'] = 'engine default surface material (empty slot)'
            R['skipped'].append({'body': body, 'source': label, 'reason': 'empty slot: renders with the engine default material'})
            return entry
        base, chain = base_of(mi)
        entry['chain'] = chain
        if base is None:
            entry['resolves_to'] = None
            R['skipped'].append({'body': body, 'source': label, 'material': mi.get_path_name(), 'reason': 'no UMaterial base', 'chain': chain})
            return entry
        entry['base'] = base.get_path_name()
        if not base.get_path_name().startswith(OWNED):
            R['skipped'].append({'body': body, 'source': label, 'material': mi.get_path_name(), 'base': base.get_path_name(),
                                 'reason': 'base material is not under ' + OWNED + ' (vendor/engine master)'})
            return entry
        t = targets.setdefault(base.get_path_name(), {'material': base, 'sources': []})
        t['sources'].append('%s:%s' % (body, label))
        return entry

    for name in BODIES:
        b = {'da': VARIANTS + name + '/DA_' + name}
        R['bodies'][name] = b
        try:
            for p in (b['da'], VARIANTS + name + '/Optimized/SK_' + name + '_LODs', VARIANTS + name + '/SK_' + name):
                if EA.does_asset_exist(p):
                    hash_before(p)
            da = u.load_asset(b['da'])
            assert da, 'missing ' + b['da']
            b['da_class'] = da.get_class().get_name()
            mesh = da.get_editor_property('appearance_mesh')
            b['mesh'] = mesh.get_path_name() if mesh else None
            b['mesh_is_lod_copy'] = bool(mesh) and pkg(mesh) == VARIANTS + name + '/Optimized/SK_' + name + '_LODs'
            expected_0 = VARIANTS + name + '/M_' + name + '_0'
            b['slots'] = []
            if mesh:
                for i, slot in enumerate(mesh.get_editor_property('materials')):
                    mi = slot.get_editor_property('material_interface')
                    e = consider(name, 'slot%d:%s' % (i, slot.get_editor_property('material_slot_name')), mi)
                    e['is_M_0'] = bool(mi) and pkg(mi) == expected_0
                    b['slots'].append(e)
            else:
                R['errors'].append(name + ': DA has no AppearanceMesh')
            m0 = u.load_asset(expected_0) if EA.does_asset_exist(expected_0) else None
            b['M_0'] = consider(name, 'M_%s_0' % name, m0) if m0 else {'material': expected_0, 'exists': False}
            b['runtime_uses_M_0'] = any(s.get('is_M_0') for s in b['slots'])
            u.log('AddZombieCameraFade %s: mesh=%s slots=%s runtime_uses_M_%s_0=%s' % (
                name, b['mesh'], [(s['source'], s['material']) for s in b['slots']], name, b['runtime_uses_M_0']))
        except Exception:
            R['errors'].append('%s: %s' % (name, traceback.format_exc()))
    return targets


def main():
    targets = collect()
    for path, t in sorted(targets.items()):
        hash_before(pkg(path))
        try:
            info = apply_fade(t['material'])
        except Exception:
            info = {'action': 'error', 'error': traceback.format_exc()}
            R['errors'].append(path + ': ' + info['error'])
        info['sources'] = t['sources']
        R['materials'][path] = info


try:
    main()
except Exception:
    R['errors'].append(traceback.format_exc())
finally:
    for p, h in R['hashes'].items():
        h['after'] = sha(p)
        h['changed'] = h['before'] != h['after']
    saved = sorted(pkg(p) for p, i in R['materials'].items() if i.get('action') == 'applied')
    unexpected = sorted(p for p, h in R['hashes'].items() if h['changed'] and p not in saved)
    if unexpected:
        R['errors'].append('files changed that this script does not own: %s' % unexpected)
    R['saved'] = saved
    R['ok'] = not R['errors']
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(R, indent=2, default=str), encoding='utf-8')
    except Exception:
        u.log_error('AddZombieCameraFade: receipt write failed\n' + traceback.format_exc())
    acts = [i.get('action', '') for i in R['materials'].values()]
    u.log_warning('AddZombieCameraFade: ok=%s dry=%s applied=%d already=%d other=%d skipped=%d errors=%d m0_bound=%s receipt=%s' % (
        R['ok'], DRY_RUN, acts.count('applied'), acts.count('already'),
        len(acts) - acts.count('applied') - acts.count('already'), len(R['skipped']), len(R['errors']),
        {n: b.get('runtime_uses_M_0') for n, b in R['bodies'].items()}, RECEIPT))
    u.SystemLibrary.quit_editor()
