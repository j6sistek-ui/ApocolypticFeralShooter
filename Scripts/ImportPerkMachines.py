"""ImportPerkMachines.py - bring the Lifeblood and Bioreactor perk machines into Unreal and stand them in NYC Exploration.

Sources: SourceAssets/PerkMachines/<Machine>/Clean/SM_<Machine>_<Part>.glb (Scripts/Blender/AssembleLifeblood.py and
AssembleBioreactor.py: every part keeps the machine's pivot at the bottom centre, so all parts snap at 0,0,0) and the
glow masks T_<Machine>_<Part>_Emissive.png beside them.

Content (all under /Game/HoverPrototype/PerkMachines/, nothing outside it is edited):
  Shared/M_PerkMachine   opaque, the part's own maps (BaseColor, Normal, glTF metal-roughness) plus glow: BaseColor x
                         (EmissiveMask x MaskGlow + saturation glow x AutoGlow), pulsing (PulseHz, PulseAmount,
                         HeartbeatShape 0 = sine, 1 = lub-dub)
  Shared/M_PerkGlass     translucent surface-lit glass, fresnel opacity (the Bioreactor tube)
  Shared/M_PerkLiquid    translucent unlit glowing liquid with slow rising noise (Niagara bubbles go inside later)
  Shared/M_PerkMetal     plain metal; SpinTurnsPerSec spins the mesh about a vertical axis through AxisLocal (cm,
                         mesh space) with World Position Offset, so the Bioreactor shaft turns in the editor viewport
                         and in game without any actor logic
  <Machine>/SM_<Machine>_<Part>, MI_<Machine>_<Part>, T_* (imported textures in <Machine>/Imported/<Part>/)
Placement: L_NYC_Explore (a test pad; machines are evaluation props there, no gameplay), both machines side by side
about 7 m in front of the player start, facing it, each on a flat 1.2 m footprint of ground (9 line traces; the first
try stood the Lifeblood on a parked car) in clear sight from the start at eye height and clear of small props on the spot and in the last 3 m of the view line (bounds check: barrels, cones),
as StaticMeshActors in the outliner folder
AFS_PerkMachines, labels "AFS Perk Trial <Machine> <Part>", tag AFS_PerkMachineTrial, parts attached to the body.
Re-runnable: re-imports, rebuilds the masters, replaces the tagged actors. PERK_PLACE=0 skips the map.
Receipt: D:/AFS_Comparisons/PerkMachines_20261031/Unreal/import_receipt.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput
       -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ImportPerkMachines.py
"""
import json
import math
import os
import time
import traceback

import unreal as u

SRC = 'M:/UnrealProjects/AFS/SourceAssets/PerkMachines'
DEST = '/Game/HoverPrototype/PerkMachines'
MATS = DEST + '/Shared'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Explore'
OUT = 'D:/AFS_Comparisons/PerkMachines_20261031/Unreal'
TAG = 'AFS_PerkMachineTrial'
FOLDER = 'AFS_PerkMachines'
PLACE = os.environ.get('PERK_PLACE', '1') != '0'
AHEAD, APART = 700.0, 190.0          # cm in front of the player start, each machine this far left / right of the line
FOOT, FLAT = 60.0, 12.0              # footprint half-size (cm) that must be flat ground (cars and kerbs fail)
CLEAR, CLUTTER_MAX = 30.0, 400.0     # no prop smaller than CLUTTER_MAX (cm half-extent) within FOOT + CLEAR

# per part: which master and its parameters (scalars / vectors); masks name the glow texture
MACHINES = {
    'Lifeblood': {
        'side': -1, 'collide': 'Body', 'front_part': 'CoinPanel',
        'parts': {
            'Body': ('Machine', {'AutoGlow': 1.6, 'AutoGlowBias': 0.45, 'PulseHz': 1.1, 'PulseAmount': 0.35,
                                 'HeartbeatShape': 1.0, 'MetalScale': 0.35}),
            'CoinPanel': ('Machine', {'AutoGlow': 1.2, 'AutoGlowBias': 0.5, 'MetalScale': 0.5}),
            'Tagline': ('Machine', {'AutoGlow': 1.0, 'AutoGlowBias': 0.5, 'MetalScale': 0.5}),
            'Core': ('Machine', {'mask': 'T_Lifeblood_Core_Emissive', 'MaskGlow': 9.0, 'PulseHz': 1.1,
                                 'PulseAmount': 0.8, 'HeartbeatShape': 1.0}),
        }},
    'Bioreactor': {
        'side': 1, 'collide': 'Frame', 'front_part': 'Sign',
        'parts': {
            'Frame': ('Machine', {'mask': 'T_Bioreactor_Frame_Emissive', 'MaskGlow': 6.0, 'PulseHz': 0.4,
                                  'PulseAmount': 0.2}),
            'Head': ('Machine', {'mask': 'T_Bioreactor_Head_Emissive', 'MaskGlow': 7.0, 'PulseHz': 0.6,
                                 'PulseAmount': 0.25}),
            'Sign': ('Machine', {'mask': 'T_Bioreactor_Sign_Emissive', 'MaskGlow': 6.0, 'PulseHz': 0.4,
                                 'PulseAmount': 0.2}),
            'Hose': ('Machine', {}),
            'TubeGlass': ('Glass', {}),
            'TubeVolume': ('Liquid', {'LiquidOpacity': 0.22, 'LiquidGlow': 1.4, 'RiseSpeed': 14.0}),
            'Shaft': ('Metal', {'SpinTurnsPerSec': 0.35}),
            'TubeCollars': ('Metal', {}),
        }},
}
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
R = {'ok': True, 'errors': [], 'warnings': [], 'machines': {}, 'masters': {}, 'placed': [],
     'time': time.strftime('%Y-%m-%d %H:%M:%S')}


def log(*a):
    print('PERK_IMPORT', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


# ----------------------------------------------------------------------------------------------------------------
# material graph helper (the MB of Scripts/AuthorPowerUpStyles2.py, trimmed to what these masters use)

class MB:
    def __init__(self, path, blend, shading, two_sided=False):
        folder, name = path.rsplit('/', 1)
        m = u.load_asset(path)
        if not m:
            m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
        else:
            MEL.delete_all_material_expressions(m)
        self.m, self.path, self.fails = m, path, []
        m.set_editor_property('blend_mode', blend)
        m.set_editor_property('shading_model', shading)
        m.set_editor_property('two_sided', two_sided)
        self.x, self.y = -2000, 0

    def node(self, cls, **props):
        self.y += 60
        if self.y > 2000:
            self.y, self.x = 0, self.x + 260
        e = MEL.create_material_expression(self.m, cls, self.x, self.y)
        for k, v in props.items():
            try:
                e.set_editor_property(k, v)
            except Exception as ex:  # noqa: BLE001
                self.fails.append('prop %s.%s: %s' % (cls.__name__, k, ex))
        return e

    @staticmethod
    def _o(a):
        return a if isinstance(a, tuple) else (a, '')

    def link(self, a, b, inputs):
        a, out = self._o(a)
        for inp in (inputs if isinstance(inputs, (list, tuple)) else [inputs]):
            if MEL.connect_material_expressions(a, out, b, inp):
                return True
        self.fails.append('%s.%s -> %s.%s' % (a.get_class().get_name(), out, b.get_class().get_name(), inputs))
        return False

    def val(self, v):
        return self.node(u.MaterialExpressionConstant, r=float(v)) if isinstance(v, (int, float)) else v

    def scalar(self, name, default, group='Perk'):
        return self.node(u.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(default), group=group)

    def vector(self, name, rgb, group='Perk'):
        return self.node(u.MaterialExpressionVectorParameter, parameter_name=name,
                         default_value=u.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)

    def tex(self, name, texture, sampler, group='Maps'):
        e = self.node(u.MaterialExpressionTextureSampleParameter2D, parameter_name=name, group=group)
        e.set_editor_property('texture', texture)
        e.set_editor_property('sampler_type', sampler)
        return e

    def bin(self, cls, a, b):
        e = self.node(cls)
        self.link(self.val(a), e, 'A')
        self.link(self.val(b), e, 'B')
        return e

    def mul(self, a, b):
        return self.bin(u.MaterialExpressionMultiply, a, b)

    def add(self, a, b):
        return self.bin(u.MaterialExpressionAdd, a, b)

    def sub(self, a, b):
        return self.bin(u.MaterialExpressionSubtract, a, b)

    def maxi(self, a, b):
        return self.bin(u.MaterialExpressionMax, a, b)

    def mini(self, a, b):
        return self.bin(u.MaterialExpressionMin, a, b)

    def append(self, a, b):
        return self.bin(u.MaterialExpressionAppendVector, a, b)

    def lerp(self, a, b, t):
        e = self.node(u.MaterialExpressionLinearInterpolate)
        self.link(self.val(a), e, 'A')
        self.link(self.val(b), e, 'B')
        self.link(self.val(t), e, 'Alpha')
        return e

    def power(self, base, exp):
        e = self.node(u.MaterialExpressionPower)
        self.link(self.val(base), e, 'Base')
        self.link(self.val(exp), e, ['Exp', 'Exponent'])
        return e

    def one(self, cls, src, **props):
        e = self.node(cls, **props)
        self.link(self.val(src), e, '')
        return e

    def sat(self, a):
        return self.one(u.MaterialExpressionSaturate, a)

    def sine(self, a):
        return self.one(u.MaterialExpressionSine, a, period=1.0)

    def c3(self, x, y, z):
        return self.node(u.MaterialExpressionConstant3Vector, constant=u.LinearColor(x, y, z, 1))

    def time(self):
        return self.node(u.MaterialExpressionTime)

    def fresnel(self, exponent):
        f = self.node(u.MaterialExpressionFresnel)
        self.link(self.val(exponent), f, 'ExponentIn')
        self.link(self.val(0.04), f, 'BaseReflectFractionIn')
        return f

    def noise(self, pos, levels=2):
        e = self.node(u.MaterialExpressionNoise)
        nf = getattr(u.NoiseFunction, 'NOISEFUNCTION_SIMPLEX_TEX', None)
        for k, v in (('scale', 1.0), ('quality', 1), ('levels', levels), ('output_min', -1.0), ('output_max', 1.0),
                     ('noise_function', nf)):
            if v is not None:
                try:
                    e.set_editor_property(k, v)
                except Exception as ex:  # noqa: BLE001
                    self.fails.append('noise prop %s: %s' % (k, ex))
        self.link(pos, e, ['Position', ''])
        return e

    def out(self, a, prop):
        a, o = self._o(a)
        if not MEL.connect_material_property(a, o, prop):
            self.fails.append('property %s' % prop)

    def finish(self):
        try:
            MEL.layout_material_expressions(self.m)
        except Exception:  # noqa: BLE001
            pass
        MEL.recompile_material(self.m)
        EAL.save_loaded_asset(self.m)
        R['masters'][self.path.rsplit('/', 1)[1]] = {
            'expressions': MEL.get_num_material_expressions(self.m), 'link_failures': self.fails,
            'scalars': [str(x) for x in MEL.get_scalar_parameter_names(self.m)],
            'textures': [str(x) for x in MEL.get_texture_parameter_names(self.m)]}
        if self.fails:
            err('%s link failures: %s' % (self.path, self.fails))
        return self.m


BM, SMOD, MP = u.BlendMode, u.MaterialShadingModel, u.MaterialProperty
ST = u.MaterialSamplerType
TC = u.TextureCompressionSettings


def pulse_of(b):
    """1 at rest; PulseAmount blends in a sine or a lub-dub beat at PulseHz (HeartbeatShape 0..1)."""
    t = b.mul(b.time(), b.scalar('PulseHz', 0.0, 'Pulse'))
    sine = b.add(0.5, b.mul(0.5, b.sine(t)))
    lub = b.power(b.sat(b.sine(t)), 8.0)
    dub = b.mul(0.6, b.power(b.sat(b.sine(b.sub(t, 0.17))), 8.0))
    beat = b.add(0.35, b.add(lub, dub))
    shape = b.lerp(sine, beat, b.scalar('HeartbeatShape', 0.0, 'Pulse'))
    return b.lerp(1.0, shape, b.scalar('PulseAmount', 0.0, 'Pulse'))


def build_machine_master(defaults):
    b = MB(MATS + '/M_PerkMachine', BM.BLEND_OPAQUE, SMOD.MSM_DEFAULT_LIT)
    base = b.tex('BaseColorTex', defaults['base'], ST.SAMPLERTYPE_COLOR)
    nrm = b.tex('NormalTex', defaults['normal'], ST.SAMPLERTYPE_NORMAL)
    mr = b.tex('MetalRoughTex', defaults['mr'], ST.SAMPLERTYPE_MASKS)
    mask = b.tex('EmissiveMaskTex', defaults['mask'], ST.SAMPLERTYPE_MASKS)
    rgb = (base, 'RGB')
    b.out(b.mul(rgb, b.vector('Tint', (1, 1, 1), 'Look')), MP.MP_BASE_COLOR)
    b.out((nrm, 'RGB'), MP.MP_NORMAL)
    b.out(b.mul((mr, 'G'), b.scalar('RoughnessScale', 1.0, 'Look')), MP.MP_ROUGHNESS)   # glTF: G roughness
    b.out(b.mul((mr, 'B'), b.scalar('MetalScale', 1.0, 'Look')), MP.MP_METALLIC)         # glTF: B metal
    r, g, bl = (base, 'R'), (base, 'G'), (base, 'B')
    satv = b.sub(b.maxi(b.maxi(r, g), bl), b.mini(b.mini(r, g), bl))
    auto = b.sat(b.mul(b.sub(satv, b.scalar('AutoGlowBias', 0.45, 'Glow')), 4.0))
    glow = b.add(b.mul((mask, 'R'), b.scalar('MaskGlow', 0.0, 'Glow')), b.mul(auto, b.scalar('AutoGlow', 0.0, 'Glow')))
    em = b.mul(b.mul(b.mul(rgb, glow), b.vector('GlowTint', (1, 1, 1), 'Glow')), pulse_of(b))
    b.out(em, MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_glass_master():
    b = MB(MATS + '/M_PerkGlass', BM.BLEND_TRANSLUCENT, SMOD.MSM_DEFAULT_LIT)
    for k, v in (('translucency_lighting_mode', 'TLM_SURFACE'),):
        try:
            b.m.set_editor_property(k, getattr(u.TranslucencyLightingMode, v))
        except Exception as ex:  # noqa: BLE001
            R['warnings'].append('glass %s: %s' % (k, ex))
    b.out(b.vector('GlassTint', (0.72, 0.9, 1.0)), MP.MP_BASE_COLOR)
    b.out(b.val(0.0), MP.MP_METALLIC)
    b.out(b.scalar('GlassRoughness', 0.04), MP.MP_ROUGHNESS)
    b.out(b.val(1.0), MP.MP_SPECULAR)
    op = b.lerp(b.scalar('OpacityCenter', 0.07), b.scalar('OpacityEdge', 0.5), b.fresnel(b.scalar('EdgeExponent', 3.5)))
    b.out(op, MP.MP_OPACITY)
    return b.finish()


def build_liquid_master():
    b = MB(MATS + '/M_PerkLiquid', BM.BLEND_TRANSLUCENT, SMOD.MSM_UNLIT)
    wp = b.node(u.MaterialExpressionWorldPosition)
    rise = b.append(b.append(0.0, 0.0), b.mul(b.time(), b.mul(b.scalar('RiseSpeed', 6.0), -1.0)))
    n = b.noise(b.mul(b.add(wp, rise), b.scalar('NoiseScale', 0.035)), levels=2)
    mottle = b.add(b.scalar('Floor', 0.55), b.mul(n, b.scalar('Mottle', 0.35)))
    edge = b.add(1.0, b.mul(b.fresnel(2.5), b.scalar('EdgeBoost', 0.8)))
    em = b.mul(b.mul(b.mul(b.vector('LiquidColor', (0.0, 0.75, 1.0)), b.scalar('LiquidGlow', 3.0)), mottle), edge)
    b.out(em, MP.MP_EMISSIVE_COLOR)
    b.out(b.scalar('LiquidOpacity', 0.5), MP.MP_OPACITY)
    return b.finish()


def build_metal_master():
    b = MB(MATS + '/M_PerkMetal', BM.BLEND_OPAQUE, SMOD.MSM_DEFAULT_LIT)
    b.out(b.vector('MetalColor', (0.09, 0.095, 0.1)), MP.MP_BASE_COLOR)
    b.out(b.scalar('Metallic', 1.0), MP.MP_METALLIC)
    b.out(b.scalar('Roughness', 0.35), MP.MP_ROUGHNESS)
    # spin about a vertical axis through AxisLocal (mesh space, cm): world position offset, so it runs everywhere
    tv = b.node(u.MaterialExpressionTransform)
    for k, cls, v in (('transform_source_type', 'MaterialVectorCoordTransformSource', 'TRANSFORMSOURCE_LOCAL'),
                      ('transform_type', 'MaterialVectorCoordTransform', 'TRANSFORM_WORLD')):
        try:
            tv.set_editor_property(k, getattr(getattr(u, cls), v))
        except Exception as ex:  # noqa: BLE001
            b.fails.append('transform %s: %s' % (k, ex))
    b.link(b.vector('AxisLocal', (0, 0, 0), 'Spin'), tv, ['Input', ''])
    pivot = b.add(b.node(u.MaterialExpressionObjectPositionWS), tv)
    rot = b.node(u.MaterialExpressionRotateAboutAxis)
    b.link(b.c3(0, 0, 1), rot, 'NormalizedRotationAxis')
    b.link(b.mul(b.time(), b.scalar('SpinTurnsPerSec', 0.0, 'Spin')), rot, 'RotationAngle')
    b.link(pivot, rot, 'PivotPoint')
    b.link(b.node(u.MaterialExpressionWorldPosition), rot, 'Position')
    b.out(rot, MP.MP_WORLD_POSITION_OFFSET)
    return b.finish()


# ----------------------------------------------------------------------------------------------------------------
# import

def import_file(src, folder):
    task = u.AssetImportTask()
    task.filename = src
    task.destination_path = folder
    task.automated = True
    task.replace_existing = True
    task.save = True
    AT.import_asset_tasks([task])
    found = set(p.split('.')[0] for p in (task.imported_object_paths or []))
    found |= set(p.split('.')[0] for p in EAL.list_assets(folder, True, False))
    return sorted(found)


def fix_texture(t, role):
    want = {'base': (True, TC.TC_DEFAULT), 'normal': (False, TC.TC_NORMALMAP), 'mr': (False, TC.TC_MASKS),
            'mask': (False, TC.TC_MASKS)}[role]
    changed = False
    if t.get_editor_property('srgb') != want[0]:
        t.set_editor_property('srgb', want[0])
        changed = True
    if t.get_editor_property('compression_settings') != want[1]:
        t.set_editor_property('compression_settings', want[1])
        changed = True
    if t.get_editor_property('max_texture_size') != 2048:
        t.set_editor_property('max_texture_size', 2048)
        changed = True
    if changed:
        EAL.save_loaded_asset(t)


def role_of(param, tex_name):
    s = (param + ' ' + tex_name).lower()
    if 'normal' in s:
        return 'normal'
    if 'basecolor' in s or 'base_color' in s or 'diffuse' in s or 'albedo' in s:
        return 'base'
    if 'metal' in s or 'rough' in s or 'orm' in s or '_rm' in s:
        return 'mr'
    if 'emissive' in s or 'occlusion' in s:
        return None
    return None


def import_part(machine, part):
    src = '%s/%s/Clean/SM_%s_%s.glb' % (SRC, machine, machine, part)
    folder = '%s/%s/Imported/%s' % (DEST, machine, part)
    paths = import_file(src, folder)
    rec = {'source': src, 'objects': len(paths), 'textures': {}}
    mesh, maps = None, {}
    for p in paths:
        a = u.load_asset(p)
        if isinstance(a, u.StaticMesh) and mesh is None:
            mesh = p
        elif isinstance(a, u.MaterialInstanceConstant):
            for tv in a.get_editor_property('texture_parameter_values'):
                t = tv.get_editor_property('parameter_value')
                if t:
                    r = role_of(str(tv.get_editor_property('parameter_info').get_editor_property('name')), t.get_name())
                    if r and r not in maps:
                        maps[r] = t
    for p in paths:   # textures the material did not name (fallback by file name)
        a = u.load_asset(p)
        if isinstance(a, u.Texture2D) and a not in maps.values():
            r = role_of('', a.get_name())
            if r and r not in maps:
                maps[r] = a
    if mesh is None:
        err('no mesh imported from ' + src)
        return None, {}
    target = '%s/%s/SM_%s_%s' % (DEST, machine, machine, part)
    if mesh != target:
        if EAL.does_asset_exist(target):
            EAL.delete_asset(target)
        if not EAL.rename_asset(mesh, target):
            err('rename %s -> %s failed' % (mesh, target))
            target = mesh
    sm = u.load_asset(target)
    for r, t in maps.items():
        fix_texture(t, r)
        rec['textures'][r] = t.get_path_name()
    box = sm.get_bounding_box()
    rec.update({'mesh': target, 'tris': sm.get_num_triangles(0),
                'min': [round(box.min.x, 1), round(box.min.y, 1), round(box.min.z, 1)],
                'max': [round(box.max.x, 1), round(box.max.y, 1), round(box.max.z, 1)]})
    return sm, maps, rec


def import_mask(machine, name):
    src = '%s/%s/Clean/%s.png' % (SRC, machine, name)
    folder = '%s/%s/Masks' % (DEST, machine)
    for p in import_file(src, folder):
        a = u.load_asset(p)
        if isinstance(a, u.Texture2D) and a.get_name() == name:
            fix_texture(a, 'mask')
            return a
    err('mask %s not imported' % src)
    return None


def add_box_collision(sm):
    for lib in ('StaticMeshEditorSubsystem',):
        ss = u.get_editor_subsystem(getattr(u, lib))
        try:
            ss.remove_collisions(sm)
            ss.add_simple_collisions(sm, u.ScriptCollisionShapeType.BOX)
            EAL.save_loaded_asset(sm)
            return True
        except Exception as ex:  # noqa: BLE001
            R['warnings'].append('collision %s: %s' % (sm.get_name(), ex))
    try:
        u.EditorStaticMeshLibrary.add_simple_collisions(sm, u.ScriptCollisionShapeType.BOX)
        EAL.save_loaded_asset(sm)
        return True
    except Exception as ex:  # noqa: BLE001
        R['warnings'].append('collision (legacy) %s: %s' % (sm.get_name(), ex))
    return False


def make_mi(name, folder, parent, scalars=None, vectors=None, textures=None):
    path = '%s/%s' % (folder, name)
    mi = u.load_asset(path)
    if not mi:
        mi = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property('parent', parent)
    MEL.clear_all_material_instance_parameters(mi)
    for k, v in (scalars or {}).items():
        MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in (vectors or {}).items():
        MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(v[0], v[1], v[2], 1.0))
    for k, v in (textures or {}).items():
        MEL.set_material_instance_texture_parameter_value(mi, k, v)
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    return mi


# ----------------------------------------------------------------------------------------------------------------
# placement

def trace(w, a, b):
    hit = u.SystemLibrary.line_trace_single(w, a, b, u.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                            u.DrawDebugTrace.NONE, True)
    if isinstance(hit, tuple):
        hit = next((x for x in hit if isinstance(x, u.HitResult)), None)
    if hit is None:
        return None
    tup = hit.to_tuple()
    return tup[5] if tup[0] else None


def flat_ground(w, x, y, top, bottom):
    """Ground z if a FOOT x FOOT square around (x, y) is flat to within FLAT (not a car, kerb edge or crate)."""
    zs = []
    for dx in (-FOOT, 0.0, FOOT):
        for dy in (-FOOT, 0.0, FOOT):
            h = trace(w, u.Vector(x + dx, y + dy, top), u.Vector(x + dx, y + dy, bottom))
            if h is None:
                return None
            zs.append(h.z)
    return min(zs) if max(zs) - min(zs) <= FLAT else None


def clutter_boxes():
    """Bounds of the small props in the level (barrels, cones, crates: some have no visibility collision, so the
    traces miss them). Buildings, the landscape and foliage actors are far bigger than CLUTTER_MAX and are skipped."""
    out = []
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if a.actor_has_tag(TAG) or not isinstance(a, (u.StaticMeshActor, u.Actor)):
            continue
        try:
            o, e = a.get_actor_bounds(False)
        except Exception:  # noqa: BLE001
            continue
        if e.x <= 0 or e.y <= 0 or max(e.x, e.y) > CLUTTER_MAX:
            continue
        out.append((o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y, o.z - e.z, o.z + e.z, a.get_actor_label()))
    return out


def cluttered(boxes, x, y, z, r=FOOT + CLEAR):
    for x0, x1, y0, y1, z0, z1, label in boxes:
        if x1 > x - r and x0 < x + r and y1 > y - r and y0 < y + r and z1 > z + 20 and z0 < z + 220:
            return label
    return None


def find_spots(w, sl, fx, fy):
    """Both machines on flat ground, as close to AHEAD / APART as the street allows."""
    tried = []
    boxes = clutter_boxes()
    R['clutter_props_considered'] = len(boxes)
    for ahead in (AHEAD, 600.0, 800.0, 500.0, 900.0, 1000.0):
        for shift in (0.0, -150.0, 150.0, -300.0, 300.0, -450.0, 450.0):
            spots = []
            for side in (-APART, APART):
                lat = shift + side
                x, y = sl.x + fx * ahead - fy * lat, sl.y + fy * ahead + fx * lat
                z = flat_ground(w, x, y, sl.z + 400, sl.z - 1500)
                if z is not None and cluttered(boxes, x, y, z):
                    z = None
                if z is not None:   # nor a prop in the last 3 m of the view line from the start
                    d = math.hypot(sl.x - x, sl.y - y)
                    for k in (100.0, 160.0, 220.0, 280.0):
                        if k < d - 100 and cluttered(boxes, x + (sl.x - x) * k / d, y + (sl.y - y) * k / d, z, 35.0):
                            z = None
                            break
                if z is not None:   # seen from the start at eye height (nothing like a barrel in front of it)
                    for zz in (60.0, 110.0, 180.0):
                        tgt = u.Vector(x, y, z + zz)
                        h = trace(w, u.Vector(sl.x, sl.y, sl.z + 70), tgt)
                        if h is not None and math.hypot(math.hypot(h.x - x, h.y - y), h.z - tgt.z) > 70:
                            z = None
                            break
                spots.append((x, y, z))
            tried.append({'ahead': ahead, 'shift': shift, 'ok': all(s[2] is not None for s in spots)})
            if all(s[2] is not None for s in spots):
                R['spot_search'] = tried
                return spots
    R['spot_search'] = tried
    raise RuntimeError('no flat spot pair found near the player start')


def place(meshes, mats):
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert level.load_level(MAP), 'load_level failed'
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    ss = u.get_editor_subsystem(u.EditorActorSubsystem)
    for a in ss.get_all_level_actors():
        if a.actor_has_tag(TAG):
            ss.destroy_actor(a)
    starts = u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart)
    assert starts, 'no PlayerStart in ' + MAP
    ps = starts[0]
    sl, yaw = ps.get_actor_location(), ps.get_actor_rotation().yaw
    fx, fy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    R['player_start'] = {'location': [round(sl.x), round(sl.y), round(sl.z)], 'yaw': round(yaw, 1),
                         'name': ps.get_actor_label()}
    spots = dict(zip(('Lifeblood', 'Bioreactor'), find_spots(w, sl, fx, fy)))
    for machine, spec in MACHINES.items():
        body_name = spec['collide']
        body_sm = meshes[machine][body_name]
        fb, ff = body_sm.get_bounding_box(), meshes[machine][spec['front_part']].get_bounding_box()
        dx = (ff.min.x + ff.max.x) / 2 - (fb.min.x + fb.max.x) / 2
        dy = (ff.min.y + ff.max.y) / 2 - (fb.min.y + fb.max.y) / 2
        front_yaw = math.degrees(math.atan2(dy, dx))        # mesh-space direction the machine faces
        front_yaw = round(front_yaw / 90.0) * 90.0
        x, y, z = spots[machine]
        look = math.degrees(math.atan2(sl.y - y, sl.x - x))
        rot = u.Rotator(roll=0.0, pitch=0.0, yaw=look - front_yaw)
        loc = u.Vector(x, y, z)
        body = None
        for part, sm in meshes[machine].items():
            a = ss.spawn_actor_from_object(sm, loc, rot)
            a.set_actor_label('AFS Perk Trial %s %s' % (machine, part))
            a.tags = [u.Name(TAG)]
            a.set_folder_path(FOLDER)
            c = a.static_mesh_component
            c.set_material(0, mats[machine][part])
            kind = MACHINES[machine]['parts'][part][0]
            if kind in ('Glass', 'Liquid'):
                c.set_editor_property('translucency_sort_priority', 2 if kind == 'Glass' else 1)
                c.set_editor_property('cast_shadow', False)
            if part != body_name:
                c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
            if part == body_name:
                body = a
        for a in ss.get_all_level_actors():
            if a.actor_has_tag(TAG) and a is not body and a.get_actor_label().startswith('AFS Perk Trial %s ' % machine):
                a.attach_to_actor(body, u.Name(''), u.AttachmentRule.KEEP_WORLD, u.AttachmentRule.KEEP_WORLD,
                                  u.AttachmentRule.KEEP_WORLD, False)
        R['placed'].append({'machine': machine, 'location': [round(x), round(y), round(z)], 'yaw': round(look - front_yaw, 1),
                            'front_mesh_yaw': front_yaw})
    saved = level.save_current_level()
    R['map_saved'] = bool(saved)
    # verify from disk
    assert level.load_level(MAP), 'reload failed'
    n = sum(1 for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors() if a.actor_has_tag(TAG))
    R['actors_after_reload'] = n
    if n != sum(len(s['parts']) for s in MACHINES.values()):
        err('after reload %d tagged actors, expected %d' % (n, sum(len(s['parts']) for s in MACHINES.values())))


def main():
    meshes, maps_all, masks = {}, {}, {}
    for machine, spec in MACHINES.items():
        meshes[machine], maps_all[machine] = {}, {}
        R['machines'][machine] = {}
        for part, (kind, params) in spec['parts'].items():
            res = import_part(machine, part)
            if res[0] is None:
                continue
            sm, maps, rec = res
            meshes[machine][part], maps_all[machine][part] = sm, maps
            R['machines'][machine][part] = rec
            if part == spec['collide']:
                rec['box_collision'] = add_box_collision(sm)
            if params.get('mask'):
                masks[params['mask']] = import_mask(machine, params['mask'])
            log(machine, part, json.dumps({k: rec.get(k) for k in ('tris', 'min', 'max')}))
    lb = maps_all['Lifeblood']['Body']
    core_mask = masks.get('T_Lifeblood_Core_Emissive')
    missing = [r for r in ('base', 'normal', 'mr') if r not in lb]
    if missing or core_mask is None:
        raise RuntimeError('Lifeblood body maps missing %s (found %s)' % (missing, list(lb)))
    m_machine = build_machine_master({'base': lb['base'], 'normal': lb['normal'], 'mr': lb['mr'], 'mask': core_mask})
    masters = {'Machine': m_machine, 'Glass': build_glass_master(), 'Liquid': build_liquid_master(),
               'Metal': build_metal_master()}
    # the Bioreactor shaft axis in mesh space: the collars are rings round it (symmetric bounds)
    cb = meshes['Bioreactor']['TubeCollars'].get_bounding_box()
    axis = ((cb.min.x + cb.max.x) / 2, (cb.min.y + cb.max.y) / 2, 0.0)
    R['shaft_axis_local_cm'] = [round(v, 2) for v in axis]
    mats = {}
    for machine, spec in MACHINES.items():
        mats[machine] = {}
        for part, (kind, params) in spec['parts'].items():
            if part not in meshes[machine]:
                continue
            folder = '%s/%s' % (DEST, machine)
            scalars = {k: v for k, v in params.items() if isinstance(v, (int, float))}
            vectors, textures = {}, {}
            if kind == 'Machine':
                maps = maps_all[machine][part]
                for role, pname in (('base', 'BaseColorTex'), ('normal', 'NormalTex'), ('mr', 'MetalRoughTex')):
                    if role in maps:
                        textures[pname] = maps[role]
                    else:
                        R['warnings'].append('%s %s has no %s map (master default used)' % (machine, part, role))
                if params.get('mask') and masks.get(params['mask']):
                    textures['EmissiveMaskTex'] = masks[params['mask']]
                if machine == 'Lifeblood':
                    vectors['GlowTint'] = (1.0, 0.35, 0.3)
            if kind == 'Metal':
                vectors['AxisLocal'] = axis
            mi = make_mi('MI_%s_%s' % (machine, part), folder, masters[kind], scalars, vectors, textures)
            mats[machine][part] = mi
            R['machines'][machine][part]['material'] = mi.get_path_name()
    EAL.save_directory(DEST, only_if_is_dirty=True, recursive=True)
    if PLACE:
        place(meshes, mats)


try:
    main()
except Exception:  # noqa: BLE001
    err(traceback.format_exc())
finally:
    os.makedirs(OUT, exist_ok=True)
    with open(OUT + '/import_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s errors=%d warnings=%d' % (R['ok'], len(R['errors']), len(R['warnings'])))
    u.SystemLibrary.quit_editor()
