"""ImportM4A1Painter.py - bring the owner's Substance Painter retexture of the M4A1 into Unreal (nullrhi).

Source: M:/UnrealProjects/AFS/SourceAssets/SubstanceExports/M4A1/Lowpoly_<PainterSet>_{BaseColor,Roughness,Metallic,Normal,Height}.png
(exported 2026-10-30 from the owner's GUN.spp through the Painter MCP, preset "PBR Metallic Roughness", 2048, PNG 8-bit).

Target: the vendor material instances under /Game/HoverPrototype/Weapons/M4A1/Vendor/Materials/<Slot> (parent MAIN) keep their
parameter names "Base Color", "Roughness", "Metal", "Normal"; this script imports the Painter maps as new textures under
/Game/HoverPrototype/Weapons/M4A1/Painter/T_<Slot>_<Map> and points each instance at them. The vendor textures stay on disk
untouched, so the swap is reversible (--revert puts the vendor textures back from the import receipt of 2026-10-29).

Painter texture sets carry the kit's part names with different numeric suffixes than the Blender rig's part_to_slot
(m4a1_rig.json); the mapping below was resolved by base name on 2026-10-30. Sets whose BaseColor export is a flat fill
(unpainted in Painter: Glas, Red1, JP gas block) are skipped so the vendor detail stays. Glass and RedDot are plain
Materials, not instances, and are never touched.

Usage:
  UnrealEditor-Cmd.exe AFS.uproject -ExecutePythonScript="Scripts/ImportM4A1Painter.py [--flip-green] [--revert] [--dry]" -nullrhi ...
  --flip-green  the Painter project exported OpenGL (Y+) normals: flip the green channel on import (UE wants DirectX, Y-).
Receipt: D:/AFS_Comparisons/M4A1_20261030_painter/import_receipt.json
"""
import json
import os
import sys
import time

import unreal as u

ARGS = sys.argv[1:]
FLIP_GREEN = '--flip-green' in ARGS
REVERT = '--revert' in ARGS
DRY = '--dry' in ARGS

SRC = 'M:/UnrealProjects/AFS/SourceAssets/SubstanceExports/M4A1'
DEST = '/Game/HoverPrototype/Weapons/M4A1/Painter'
MATS = '/Game/HoverPrototype/Weapons/M4A1/Vendor/Materials'
OUT_DIR = 'D:/AFS_Comparisons/M4A1_20261030_painter'
RECEIPT = OUT_DIR + '/import_receipt.json'
VENDOR_RECEIPT = 'D:/AFS_Comparisons/M4A1_20261029/import_receipt.json'

# Painter texture set -> UE material slot / instance name.
SET_TO_SLOT = {
    'AR_15_RAPTOR_LT_CHARGING_HANDLE_5_57': 'ChargingHandle',
    'Barrel_20_inch_for_AR_17': 'Barrel',
    'Bolt_Carrier2': 'BoltCarrier',
    'Colt_M4_Carbine_Lower_Receiver1': 'Receiver_Lower',
    'EMG_SAI_QD_Rail3': 'FrontRail',
    'EOTech_ATPIAL_AN_PEQ_16': 'Laser',
    'FAB_Defense_GL_SHOCK_AR15_M16_Shock_Absorbing_Butt_Stock1': 'Buttstock',
    'JP_Enterprises_Ar_15_M16_Adjustable_Gas_Blocks_A2_Style_Gas_Block1': 'GasBlock',
    'Magpul_Industries_M_lok_Alum_Rail1': 'SmallRail',
    'Magpul_PMAG_D_60__AR_M5': 'Magazine',
    'MAGPUL_PTS_AAC_Blackout_51T_Flash_Hider5': 'Muzzel',
    'NcSTAR_MPR45_45_Degree_Offset_Rail_Mount2': 'OffsetRail',
    'Primary_Arms_SLx_3_Compact_3x32_Gen_II_Prism_Scope3': 'Optic',
    'PTS_Fortis_SHIFT__Vertical_Grip1': 'FrontGrip',
    'SDN_6_Fast_attach_7_62mm_silencer1': 'Silencer',
    'Strike_SI_AR_Advanced_Receiver_Extension2': 'BufferTube',
    'Tactical_Dynamics_CNC_Aluminum_Skeletonized_Pistol_Grip_for_AR16': 'PistolGrip',
    'Vltor_MUR_MODULAR_UPPER_RECEIVER1': 'Receiver_Upper',
    'Zenit_BelOMO_PK_07': 'Reflex',
    'Zenitco_Klesch_2IKS3': 'Flashlight',
    # 'Glas' -> Glass and 'Red1' -> RedDot are plain Materials (no instance parameters) and flat exports: skipped.
}
# Painter map suffix -> (MI parameter name, sRGB, compression)
MAPS = [
    ('BaseColor', 'Base Color', True, u.TextureCompressionSettings.TC_DEFAULT),
    ('Roughness', 'Roughness', False, u.TextureCompressionSettings.TC_DEFAULT),
    ('Metallic', 'Metal', False, u.TextureCompressionSettings.TC_DEFAULT),
    ('Normal', 'Normal', False, u.TextureCompressionSettings.TC_NORMALMAP),
]
FLAT_BYTES = 60000  # a 2K PNG below this is a uniform fill: the set was not painted

R = {'ok': True, 'errors': [], 'warnings': [], 'args': ARGS, 'imported': {}, 'skipped': {}, 'assigned': {},
     'readback': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary


def log(*a):
    print('PAINTER_IMPORT', *a, flush=True)


def err(msg):
    R['ok'] = False
    R['errors'].append(msg)
    log('ERROR', msg)


def save_receipt():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(RECEIPT, 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)


def import_texture(png, name, srgb, compression, flip_green):
    task = u.AssetImportTask()
    task.filename = png
    task.destination_path = DEST
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.imported_object_paths or [])
    if not paths:
        err('import failed: %s' % png)
        return None
    tex = u.load_asset(paths[0])
    if not tex:
        err('imported but not loadable: %s' % paths[0])
        return None
    tex.set_editor_property('srgb', srgb)
    tex.set_editor_property('compression_settings', compression)
    if compression == u.TextureCompressionSettings.TC_NORMALMAP:
        tex.set_editor_property('flip_green_channel', bool(flip_green))
        tex.set_editor_property('lod_group', u.TextureGroup.TEXTUREGROUP_WORLD_NORMAL_MAP)
    else:
        tex.set_editor_property('lod_group', u.TextureGroup.TEXTUREGROUP_WEAPON)
    tex.set_editor_property('max_texture_size', 2048)
    EAL.save_loaded_asset(tex)
    return tex


def set_params(mi, mapping):
    """mapping: parameter name -> texture asset. Returns the read-back dict."""
    back = {}
    for param, tex in mapping.items():
        # UE 5.8 returns False here even when the value is applied (observed 2026-10-30: 76/76 'failed' yet the
        # fresh-load readback showed every parameter on the new texture), so the readback below is the truth.
        MEL.set_material_instance_texture_parameter_value(mi, param, tex)
        got = MEL.get_material_instance_texture_parameter_value(mi, param)
        back[param] = got.get_path_name() if got else None
        if not got or got.get_path_name() != tex.get_path_name():
            err('readback mismatch %s.%s: %s != %s' % (mi.get_name(), param, back[param], tex.get_path_name()))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return back


def main():
    if REVERT:
        vendor = json.load(open(VENDOR_RECEIPT, encoding='utf-8'))['materials']
        for slot, m in vendor.items():
            if m.get('class') != 'MaterialInstanceConstant':
                continue
            mi = u.load_asset(m['path'])
            mapping = {}
            for param, path in m['textures'].items():
                tex = u.load_asset(path)
                if tex:
                    mapping[param] = tex
            R['assigned'][slot] = set_params(mi, mapping) if not DRY else {k: v.get_path_name() for k, v in mapping.items()}
        log('reverted to the vendor textures')
        return
    for tset, slot in SET_TO_SLOT.items():
        base = '%s/Lowpoly_%s_BaseColor.png' % (SRC, tset)
        if not os.path.exists(base):
            err('missing export: ' + base)
            continue
        if os.path.getsize(base) < FLAT_BYTES:
            R['skipped'][slot] = 'flat BaseColor export (%d bytes): set not painted, vendor textures kept' % os.path.getsize(base)
            log('skip', slot, R['skipped'][slot])
            continue
        mi_path = '%s/%s' % (MATS, slot)
        mi = u.load_asset(mi_path)
        if not isinstance(mi, u.MaterialInstanceConstant):
            err('not a material instance: ' + mi_path)
            continue
        mapping = {}
        for suffix, param, srgb, comp in MAPS:
            png = '%s/Lowpoly_%s_%s.png' % (SRC, tset, suffix)
            if not os.path.exists(png):
                err('missing map: ' + png)
                continue
            name = 'T_%s_%s' % (slot, suffix)
            if DRY:
                R['imported'].setdefault(slot, {})[suffix] = '%s/%s (dry)' % (DEST, name)
                continue
            tex = import_texture(png, name, srgb, comp, FLIP_GREEN)
            if tex:
                mapping[param] = tex
                R['imported'].setdefault(slot, {})[suffix] = tex.get_path_name()
        if DRY or len(mapping) != len(MAPS):
            if not DRY:
                err('incomplete map set for %s: %s' % (slot, sorted(mapping)))
            continue
        R['assigned'][slot] = set_params(mi, mapping)
        log('assigned', slot, {k: v.get_name() for k, v in mapping.items()})
    # Read back the whole rifle's slots from a fresh load so the receipt reflects disk, not memory.
    for slot in SET_TO_SLOT.values():
        mi = u.load_asset('%s/%s' % (MATS, slot))
        if isinstance(mi, u.MaterialInstanceConstant):
            R['readback'][slot] = {p: (lambda t: t.get_path_name() if t else None)(MEL.get_material_instance_texture_parameter_value(mi, p))
                                   for _, p, _, _ in MAPS}


try:
    main()
except Exception as e:  # noqa: BLE001
    import traceback
    err('exception: %s\n%s' % (e, traceback.format_exc()))
finally:
    save_receipt()
    log('DONE ok=%s errors=%d imported=%d skipped=%d' % (R['ok'], len(R['errors']), len(R['imported']), len(R['skipped'])))
    u.SystemLibrary.quit_editor()
