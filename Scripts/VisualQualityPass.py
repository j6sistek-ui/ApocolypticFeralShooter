"""VisualQualityPass.py - near-camera texture caps for Vexa and her held guns (owner 2026-10-31: "can the gun and player
be in higher resolution?"). NullRHI, no PIE.

  UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput
      "-ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/VisualQualityPass.py [--dry] [--revert]"

What it does
  1. Collects the near-camera meshes: Vexa = every DA_HoverPilot.BodyParts mesh (+ the part's material overrides,
     which is what AHoverPilot::BeginPlay applies to the NYC pawn BP_Vexa_CLS_Parkour), the pawn Blueprint's own mesh
     (cross-check) and the first-person arms; guns = DA_HoverPilot RiggedGun / Gun / GunOptic, every GunRigs value's
     Mesh, the DA_GunRig_* assets, the SK_* meshes under Weapons/M4A1 and Weapons/EM, and the katana.
  2. Walks each material to the textures it actually uses: MaterialEditingLibrary.get_used_textures, the effective
     texture-parameter values of the instance chain, and the base material's / material functions' hard texture
     dependencies minus parameter defaults the instance overrides.
  3. Reports per texture: source size (UTexture::Source via HoverAuthoring.inspect_texture), MaxTextureSize, LODBias,
     LODGroup, compression, sRGB, VT, NeverStream, the effective top mip, the referencer count, and which near-camera
     meshes use it.
  4. Applies (unless --dry): MaxTextureSize 0 (= source) where the cap or LODBias hides source detail (4096 ceiling;
     anything bigger is capped at 4096 and flagged), LODBias 0, LODGroup Character / CharacterNormalMap /
     CharacterSpecular for Vexa and Weapon / WeaponNormalMap / WeaponSpecular for the guns. NeverStream is left alone
     (reported). Only /Game/ textures; each changed texture is saved.
  5. Receipt with a VRAM estimate before / after (fully-resident upper bound for streamed textures; VT textures listed
     apart because they draw from the fixed VT pool), the owner's 6 GB gaming budget check against the last measured
     capture peak, the 2026-10-31 probe's 17 "4K capped at 2K" textures reconciled against what is actually in use, and
     "source-limited" textures (already at their source size: only a higher-resolution export can help).
  --revert restores every texture listed in texture_pass_applied.json (the last apply run that changed something) to
  its recorded before-values.

Receipt D:/AFS_Comparisons/VisualPass_20261031/texture_pass.json (VQ_OUT overrides the folder).
"""
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

import unreal as u

OUT = Path(os.environ.get('VQ_OUT') or 'D:/AFS_Comparisons/VisualPass_20261031')
OUT.mkdir(parents=True, exist_ok=True)
RECEIPT = OUT / 'texture_pass.json'
# Written only by an apply run that changed something, never by a dry or no-op run: --revert reads it.
APPLIED = OUT / 'texture_pass_applied.json'
ARGS = ' '.join(sys.argv[1:])
DRY = '--dry' in ARGS
REVERT = '--revert' in ARGS
PILOT = '/Game/HoverPrototype/DA_HoverPilot'
PAWN_BP = '/Game/HoverPrototype/Hybrid/BP_Vexa_CLS_Parkour'
CHARACTER_EXTRA = ['/Game/HoverPrototype/Weapons/FirstPerson/SK_Vexa_FPSArms']
GUN_FOLDERS = ['/Game/HoverPrototype/Weapons/M4A1', '/Game/HoverPrototype/Weapons/EM']
GUN_RIGS = '/Game/HoverPrototype/Weapons/Rigs'
KATANA = '/Game/HoverPrototype/Weapons/Katana/SM_BloodiedKatana'
PROBE = Path('D:/AFS_Comparisons/Playtest_20261031/texture_probe.json')
CEILING = 4096
# Owner rule (RULES.md 2026-10-31): rendered work while the owner games stays under ~6 GB VRAM. The last measured
# rendered capture with the Painter M4A1 peaked at ~5.1 GB (GunProof_20261030, 720p, pool 1200).
BUDGET_MB = 6144
BASELINE_PEAK_MB = 5100

EA = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
REG = u.AssetRegistryHelpers.get_asset_registry()
DEP = u.AssetRegistryDependencyOptions(include_soft_package_references=False, include_hard_package_references=True,
                                       include_searchable_names=False, include_soft_management_references=False,
                                       include_hard_management_references=False)
R = {'ok': False, 'mode': 'revert' if REVERT else ('dry' if DRY else 'apply'), 'errors': [], 'api_notes': [],
     'meshes': {}, 'textures': {}, 'changes': [], 'vram': {}, 'probe_reconciliation': [], 'source_limited': [],
     'flags': [], 'time': time.strftime('%Y-%m-%d %H:%M:%S')}


def save():
    RECEIPT.write_text(json.dumps(R, indent=1, default=str))


def pkg(obj):
    return obj.get_path_name().split('.')[0] if obj else None


def note(msg):
    if msg not in R['api_notes']:
        R['api_notes'].append(msg)


# ---------------------------------------------------------------------------------------------------- meshes
def mesh_materials(mesh):
    mats = []
    try:
        if isinstance(mesh, u.SkeletalMesh):
            for sm in mesh.get_editor_property('materials'):
                mats.append(sm.get_editor_property('material_interface'))
        elif isinstance(mesh, u.StaticMesh):
            for sm in mesh.get_editor_property('static_materials'):
                mats.append(sm.get_editor_property('material_interface'))
    except Exception as e:  # noqa: BLE001
        R['errors'].append('materials of %s: %s' % (pkg(mesh), e))
    return mats


def add_mesh(group, mesh, overrides=None, why=''):
    if not mesh:
        return
    key = pkg(mesh)
    entry = R['meshes'].setdefault(key, {'group': group, 'why': [], 'materials': []})
    if group == 'character':
        entry['group'] = 'character'  # a mesh used by both stays in the character set
    entry['why'].append(why)
    mats = mesh_materials(mesh)
    for i, m in enumerate(overrides or []):
        if m:
            if i < len(mats):
                mats[i] = m
            else:
                mats.append(m)
    for m in mats:
        if m and pkg(m) not in entry['materials']:
            entry['materials'].append(pkg(m))
    entry.setdefault('_objs', []).extend([m for m in mats if m])


def collect_meshes():
    da = u.load_asset(PILOT)
    assert da, 'DA_HoverPilot missing'
    for i, part in enumerate(da.get_editor_property('body_parts')):  # struct array: a copy, read-only here
        add_mesh('character', part.get_editor_property('mesh'), list(part.get_editor_property('materials')),
                 'DA_HoverPilot.BodyParts[%d] %s' % (i, part.get_editor_property('name')))
    for path in CHARACTER_EXTRA:
        add_mesh('character', u.load_asset(path), None, 'first-person arms')
    try:
        bp = u.load_asset(PAWN_BP)
        cdo = u.get_default_object(bp.generated_class())
        comp = cdo.get_editor_property('mesh')
        sk = None
        for prop in ('skeletal_mesh_asset', 'skeletal_mesh'):
            try:
                sk = comp.get_editor_property(prop)
                break
            except Exception:  # noqa: BLE001
                continue
        R['pawn_bp_mesh'] = pkg(sk)
        add_mesh('character', sk, None, 'BP_Vexa_CLS_Parkour CDO mesh (BeginPlay replaces it with BodyParts[0])')
    except Exception as e:  # noqa: BLE001
        note('pawn BP mesh: %s' % str(e)[:120])
    for prop, why in (('rigged_gun', 'DA_HoverPilot.RiggedGun'), ('gun', 'DA_HoverPilot.Gun'),
                      ('gun_optic', 'DA_HoverPilot.GunOptic')):
        try:
            add_mesh('weapon', da.get_editor_property(prop), None, why)
        except Exception as e:  # noqa: BLE001
            note('%s: %s' % (prop, str(e)[:100]))
    try:
        for k, rig in da.get_editor_property('gun_rigs').items():
            if rig:
                add_mesh('weapon', rig.get_editor_property('mesh'), None, 'DA_HoverPilot.GunRigs[%s]' % k)
    except Exception as e:  # noqa: BLE001
        note('gun_rigs: %s' % str(e)[:100])
    for a in REG.get_assets_by_path(GUN_RIGS, True):
        rig = a.get_asset()
        try:
            add_mesh('weapon', rig.get_editor_property('mesh'), None, str(a.asset_name))
        except Exception:  # noqa: BLE001
            pass
    for folder in GUN_FOLDERS:
        for a in REG.get_assets_by_path(folder, True):
            if str(a.asset_class_path.asset_name) == 'SkeletalMesh':
                add_mesh('weapon', a.get_asset(), None, 'gun folder ' + folder)
    add_mesh('weapon', u.load_asset(KATANA), None, 'katana (held melee)')


# -------------------------------------------------------------------------------------------------- materials
def package_class(p):
    assets = REG.get_assets_by_package_name(p)
    return str(assets[0].asset_class_path.asset_name) if assets else ''


def material_graph_textures(start):
    """Texture packages hard-referenced by a material / material function graph (not following meshes)."""
    out, seen, stack = set(), set(), [start]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        for d in REG.get_dependencies(p, DEP) or []:
            d = str(d)
            if not d.startswith('/Game/'):
                continue
            c = package_class(d)
            if c == 'Texture2D':
                out.add(d)
            elif c.startswith('Material') and c != 'MaterialParameterCollection':
                stack.append(d)
    return out


def textures_of(mat):
    found = {}

    def add(t, how):
        if t and isinstance(t, u.Texture2D):
            found.setdefault(pkg(t), set()).add(how)

    try:
        for t in MEL.get_used_textures(mat) or []:
            add(t, 'used_textures')
    except Exception as e:  # noqa: BLE001
        note('get_used_textures: %s' % str(e)[:100])
    effective = set()
    try:
        names = MEL.get_texture_parameter_names(mat) or []
    except Exception as e:  # noqa: BLE001
        names = []
        note('get_texture_parameter_names: %s' % str(e)[:100])
    for n in names:
        try:
            if isinstance(mat, u.MaterialInstance):
                v = MEL.get_material_instance_texture_parameter_value(mat, n)
            else:
                v = MEL.get_material_default_texture_parameter_value(mat, n)
            add(v, 'param:%s' % n)
            if v:
                effective.add(pkg(v))
        except Exception as e:  # noqa: BLE001
            note('texture param %s: %s' % (n, str(e)[:100]))
    try:
        base = mat.get_base_material()
    except Exception:  # noqa: BLE001
        base = mat
    defaults = set()
    if base:
        try:
            for n in MEL.get_texture_parameter_names(base) or []:
                v = MEL.get_material_default_texture_parameter_value(base, n)
                if v:
                    defaults.add(pkg(v))
        except Exception as e:  # noqa: BLE001
            note('base defaults: %s' % str(e)[:100])
        for tp in material_graph_textures(pkg(base)):
            if tp in defaults and tp not in effective:
                continue  # a parameter default this instance overrides
            t = u.load_asset(tp)
            add(t, 'base_graph')
    return found


# --------------------------------------------------------------------------------------------------- textures
BPP = {'TC_DEFAULT': 1.0, 'TC_NORMALMAP': 1.0, 'TC_MASKS': 1.0, 'TC_GRAYSCALE': 1.0, 'TC_DISPLACEMENTMAP': 1.0,
       'TC_VECTOR_DISPLACEMENTMAP': 4.0, 'TC_HDR': 8.0, 'TC_EDITOR_ICON': 4.0, 'TC_ALPHA': .5,
       'TC_DISTANCE_FIELD_FONT': 1.0, 'TC_HDR_COMPRESSED': 1.0, 'TC_BC7': 1.0, 'TC_HALF_FLOAT': 2.0,
       'TC_LQ': 2.0, 'TC_ENCODED_REFLECTION_CAPTURE': 1.0, 'TC_SINGLE_FLOAT': 4.0, 'TC_HDR_F32': 16.0}


def enum_name(v):
    return str(v).split('.')[-1].split(':')[0].strip('<> ')


def source_size(t):
    try:
        s = u.HoverAuthoring.inspect_texture(t)
        m = re.search(r'size=(\d+)x(\d+)', s or '')
        if m:
            return int(m.group(1)), int(m.group(2)), 'source'
    except Exception as e:  # noqa: BLE001
        note('inspect_texture: %s' % str(e)[:100])
    return t.blueprint_get_size_x(), t.blueprint_get_size_y(), 'platform'


def effective(w, h, cap, bias):
    big = max(w, h)
    f = 1.0
    if cap and big > cap:
        f = cap / float(big)
    f /= 2 ** max(0, bias)
    return max(1, int(w * f)), max(1, int(h * f))


def bytes_of(w, h, comp, no_alpha):
    bpp = BPP.get(comp, 1.0)
    if comp in ('TC_DEFAULT', 'TC_MASKS') and no_alpha:
        bpp = .5  # BC1
    return w * h * bpp * 4.0 / 3.0


def describe(tp):
    t = u.load_asset(tp)
    w, h, src = source_size(t)
    info = {'source_w': w, 'source_h': h, 'size_from': src,
            'max_texture_size': t.get_editor_property('max_texture_size'), 'lod_bias': t.get_editor_property('lod_bias'),
            'lod_group': enum_name(t.get_editor_property('lod_group')),
            'compression': enum_name(t.get_editor_property('compression_settings')),
            'srgb': t.get_editor_property('srgb'), 'vt': t.get_editor_property('virtual_texture_streaming'),
            'never_stream': t.get_editor_property('never_stream')}
    try:
        info['no_alpha'] = t.get_editor_property('compression_no_alpha')
    except Exception:  # noqa: BLE001
        info['no_alpha'] = False
    info['referencers'] = len(REG.get_referencers(tp, DEP) or [])
    return t, info


def target_group(info, group):
    name = info['_name'].lower()
    comp = info['compression']
    if 'NORMALMAP' in comp:
        kind = 'normal'
    elif comp in ('TC_MASKS', 'TC_GRAYSCALE', 'TC_ALPHA') or (
            not info['srgb'] and re.search(r'rough|metal|_ao|orm|spec|mask|opacity|height', name)):
        kind = 'spec'
    else:
        kind = 'base'
    base = 'TEXTUREGROUP_CHARACTER' if group == 'character' else 'TEXTUREGROUP_WEAPON'
    return {'normal': base + '_NORMAL_MAP', 'spec': base + '_SPECULAR', 'base': base}[kind]


def plan_change(info, group):
    ch = {}
    w, h = info['source_w'], info['source_h']
    cap, bias = info['max_texture_size'], info['lod_bias']
    want_cap = 0 if max(w, h) <= CEILING else CEILING
    ew, eh = effective(w, h, cap, bias)
    tw, th = effective(w, h, want_cap, 0)
    if (ew, eh) != (tw, th) and max(tw, th) > max(ew, eh):
        ch['max_texture_size'] = (cap, want_cap)
        if bias:
            ch['lod_bias'] = (bias, 0)
    tg = target_group(info, group)
    if info['lod_group'] != tg:
        ch['lod_group'] = (info['lod_group'], tg)
    return ch, (ew, eh), (tw, th) if 'max_texture_size' in ch else (ew, eh)


def apply_change(t, ch):
    for prop, (_, new) in ch.items():
        if prop == 'lod_group':
            t.set_editor_property('lod_group', getattr(u.TextureGroup, new))
        else:
            t.set_editor_property(prop, new)


# ------------------------------------------------------------------------------------------------------- main
def run_revert():
    assert APPLIED.exists(), 'no applied receipt to revert: ' + str(APPLIED)
    old = json.loads(APPLIED.read_text())
    done = []
    for c in old.get('changes', []):
        t = u.load_asset(c['texture'])
        if not t:
            R['errors'].append('missing ' + c['texture'])
            continue
        back = {k: (v[1], v[0]) for k, v in c['change'].items()}
        apply_change(t, back)
        if not EA.save_loaded_asset(t, False):
            R['errors'].append('save failed ' + c['texture'])
        done.append(c['texture'])
    R['reverted'] = done
    R['ok'] = not R['errors']
    R.pop('changes')
    (OUT / 'texture_pass_revert.json').write_text(json.dumps(R, indent=1, default=str))
    print('VQ_REVERT_DONE n=%d errors=%d' % (len(done), len(R['errors'])), flush=True)


def main():
    collect_meshes()
    users = {}
    for mp, entry in R['meshes'].items():
        for m in entry.pop('_objs', []):
            for tp, how in textures_of(m).items():
                rec = users.setdefault(tp, {'meshes': set(), 'groups': set(), 'evidence': set(), 'materials': set()})
                rec['meshes'].add(mp)
                rec['groups'].add(entry['group'])
                rec['evidence'] |= how
                rec['materials'].add(pkg(m))
    vram = {'nonvt_before_mb': 0.0, 'nonvt_after_mb': 0.0, 'vt_before_mb': 0.0, 'vt_after_mb': 0.0}
    for tp in sorted(users):
        rec = users[tp]
        group = 'character' if 'character' in rec['groups'] else 'weapon'
        t, info = describe(tp)
        info['_name'] = tp.split('/')[-1]
        info.update({'group': group, 'meshes': sorted(rec['meshes']), 'materials': sorted(rec['materials']),
                     'evidence': sorted(rec['evidence'])})
        if not tp.startswith('/Game/') or max(info['source_w'], info['source_h']) <= 64:
            info['skipped'] = 'engine or placeholder texture'
            ch, before, after = {}, effective(info['source_w'], info['source_h'], info['max_texture_size'],
                                              info['lod_bias']), None
        else:
            ch, before, after = plan_change(info, group)
        after = after or before
        info['effective_before'] = '%dx%d' % before
        info['effective_after'] = '%dx%d' % after
        b0 = bytes_of(before[0], before[1], info['compression'], info['no_alpha']) / 2 ** 20
        b1 = bytes_of(after[0], after[1], info['compression'], info['no_alpha']) / 2 ** 20
        info['mb_before'], info['mb_after'] = round(b0, 2), round(b1, 2)
        k = 'vt' if info['vt'] else 'nonvt'
        vram[k + '_before_mb'] += b0
        vram[k + '_after_mb'] += b1
        if max(info['source_w'], info['source_h']) > CEILING:
            R['flags'].append('%s source %dx%d > %d: capped at %d' % (tp, info['source_w'], info['source_h'],
                                                                      CEILING, CEILING))
        if max(after) <= 2048 and max(info['source_w'], info['source_h']) <= 2048 and group == 'weapon':
            R['source_limited'].append(tp)
        if info['referencers'] > 3:
            info['shared_note'] = 'referenced by %d packages; the change applies everywhere it is used' % info['referencers']
        info.pop('_name')
        R['textures'][tp] = info
        if ch:
            R['changes'].append({'texture': tp, 'group': group, 'change': ch})
            if not DRY:
                apply_change(t, ch)
                if not EA.save_loaded_asset(t, False):
                    R['errors'].append('save failed ' + tp)
    vram = {k: round(v, 1) for k, v in vram.items()}
    vram['nonvt_delta_mb'] = round(vram['nonvt_after_mb'] - vram['nonvt_before_mb'], 1)
    vram['vt_delta_mb'] = round(vram['vt_after_mb'] - vram['vt_before_mb'], 1)
    vram['note'] = ('Upper bound: every streamed texture fully resident at its top mip, conservative block sizes '
                    '(BC7/BC5/G8 = 1 B/texel, BC1 = 0.5 when CompressionNoAlpha). Streaming keeps less resident and the '
                    'pool (r.Streaming.PoolSize 1200 in captures) caps it; VT textures draw from the fixed VT physical '
                    'pool, so their delta is disk / tile churn, not resident VRAM.')
    vram['budget_mb'] = BUDGET_MB
    vram['baseline_peak_mb'] = BASELINE_PEAK_MB
    vram['projected_peak_mb'] = round(BASELINE_PEAK_MB + max(0.0, vram['nonvt_delta_mb']), 1)
    vram['within_budget'] = vram['projected_peak_mb'] <= BUDGET_MB
    if not vram['within_budget']:
        R['flags'].append('projected peak %.0f MB exceeds the %d MB gaming budget' % (vram['projected_peak_mb'], BUDGET_MB))
    R['vram'] = vram
    if PROBE.exists():
        probe = json.loads(PROBE.read_text())
        for row in probe.get('rows', []):
            if row.get('w', 0) >= 4096 and row.get('max') not in (0, None):
                tp = row['path']
                R['probe_reconciliation'].append({'texture': tp, 'probe_cap': row['max'], 'in_use': tp in R['textures'],
                                                  'changed': any(c['texture'] == tp for c in R['changes'])})
    R['counts'] = {'meshes': len(R['meshes']), 'textures': len(R['textures']), 'changes': len(R['changes']),
                   'source_limited': len(R['source_limited'])}
    R['ok'] = not R['errors']
    save()
    if R['changes'] and not DRY:
        if APPLIED.exists():
            APPLIED.rename(OUT / ('texture_pass_applied_%s.json' % time.strftime('%Y%m%d_%H%M%S')))
        APPLIED.write_text(json.dumps(R, indent=1, default=str))
    print('VQ_DONE mode=%s %s vram=%s flags=%d' % (R['mode'], json.dumps(R['counts']), json.dumps(
        {k: vram[k] for k in ('nonvt_delta_mb', 'vt_delta_mb', 'projected_peak_mb', 'within_budget')}),
        len(R['flags'])), flush=True)


try:
    if REVERT:
        run_revert()
    else:
        main()
except Exception:  # noqa: BLE001
    R['errors'].append(traceback.format_exc())
    save()
    print('VQ_ERROR', R['errors'][-1], flush=True)
finally:
    u.SystemLibrary.quit_editor()
