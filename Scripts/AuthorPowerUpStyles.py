"""AuthorPowerUpStyles.py - build the power-up style exploration assets and the showcase level (nullrhi).

Reads the 14 looks from Scripts/PowerUpStyleRecipes.py and makes, under /Game/HoverPrototype/PowerUps/Styles/:
  Shared/Textures   T_PU_* masks from SourceAssets/PowerUps/StyleTextures (Scripts/MakePowerUpStyleTextures.py)
  Shared/Props      SM_PU_* street props from SourceAssets/PowerUps/StyleProps (Scripts/Blender/MakePowerUpStyleProps.py)
  Shared/Materials  masters M_PU_ItemFX, M_PU_GlowAdditive, M_PU_HoloLoFi, M_PU_PropSimple, M_PU_HeatHaze
                    (MaterialEditingLibrary graphs, rebuilt in place on every run so instances keep their parent)
  S<NN>_<Key>/      per look: MI_S<NN>_<Medkit|Nuke>_<Element>[_<Slot>] and NS_S<NN>_<Item>_<Element> (duplicates of
                    pack Niagara systems with their user parameters set; pack originals are never edited)
and the level /Game/HoverPrototype/Maps/L_PowerUpShowcase (new_level_from_template; asphalt street, dusk sun, fog,
manual exposure, GameModeBase so PIE has no HUD; backdrop wreck, barrier, barrels).
Nothing here is wired to gameplay.
Receipt: D:/AFS_Comparisons/PowerUps_20261031/Styles/author_receipt.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput -ExecutePythonScript=<this>
Env: PU_SKIP_IMPORT=1 skips the texture/prop imports, PU_SKIP_LEVEL=1 skips the level, PU_LOOKS=1,4 limits the looks.
"""
import glob
import json
import math
import os
import sys
import time
import traceback

import unreal as u

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'M:/UnrealProjects/AFS/Scripts')
sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import importlib  # noqa: E402

import PowerUpStyleRecipes as REC  # noqa: E402

importlib.reload(REC)

OUT_DIR = 'D:/AFS_Comparisons/PowerUps_20261031/Styles'
TEX_SRC = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleTextures'
PROP_SRC = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps'
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
R = {'ok': True, 'errors': [], 'warnings': [], 'textures': {}, 'props': {}, 'masters': {}, 'looks': {}, 'level': {},
     'niagara_described': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
ONLY = [int(x) for x in os.environ.get('PU_LOOKS', '').split(',') if x.strip()]


def log(*a):
    print('PU_AUTHOR', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def warn(m):
    R['warnings'].append(m)
    log('WARN', m)


# ----------------------------------------------------------------------------------------------------------------
# imports

def import_file(src, dest):
    task = u.AssetImportTask()
    task.filename = src
    task.destination_path = dest
    task.automated = True
    task.replace_existing = True
    task.save = True
    AT.import_asset_tasks([task])
    return [p.split('.')[0] for p in (task.imported_object_paths or [])]


def import_textures():
    for png in sorted(glob.glob(TEX_SRC + '/T_PU_*.png')):
        name = os.path.splitext(os.path.basename(png))[0]
        paths = import_file(png, REC.TEX)
        t = u.load_asset('%s/%s' % (REC.TEX, name))
        if not t:
            err('texture import failed ' + png)
            continue
        t.set_editor_property('srgb', False)
        t.set_editor_property('compression_settings', u.TextureCompressionSettings.TC_DEFAULT)
        EAL.save_loaded_asset(t)
        R['textures'][name] = t.get_path_name()


def import_props():
    for glb in sorted(glob.glob(PROP_SRC + '/SM_PU_*.glb')):
        name = os.path.splitext(os.path.basename(glb))[0][len('SM_PU_'):]
        folder = '%s/%s' % (REC.PROPS, name)
        import_file(glb, folder)
        meshes = [p.split('.')[0] for p in EAL.list_assets(folder, True, False) if isinstance(u.load_asset(p), u.StaticMesh)]
        if not meshes:
            err('prop import failed ' + glb)
            continue
        target = '%s/SM_PU_%s' % (folder, name)
        if meshes[0] != target:
            if EAL.does_asset_exist(target):
                EAL.delete_asset(target)
            EAL.rename_asset(meshes[0], target)
        sm = u.load_asset(target)
        box = sm.get_bounding_box()
        R['props'][name] = {'path': target, 'slots': [str(m.material_slot_name) for m in sm.static_materials],
                            'min': [round(box.min.x, 1), round(box.min.y, 1), round(box.min.z, 1)],
                            'max': [round(box.max.x, 1), round(box.max.y, 1), round(box.max.z, 1)]}
        EAL.save_loaded_asset(sm)


# ----------------------------------------------------------------------------------------------------------------
# material graph helper

class MB:
    def __init__(self, path, blend, shading, two_sided=False):
        folder, name = path.rsplit('/', 1)
        m = u.load_asset(path)
        if not m:
            m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
        else:
            MEL.delete_all_material_expressions(m)
        self.m = m
        self.path = path
        m.set_editor_property('blend_mode', blend)
        m.set_editor_property('shading_model', shading)
        m.set_editor_property('two_sided', two_sided)
        self.x = -1600
        self.y = 0
        self.fails = []

    def node(self, cls, **props):
        self.y += 60
        if self.y > 1800:
            self.y, self.x = 0, self.x + 260
        e = MEL.create_material_expression(self.m, cls, self.x, self.y)
        for k, v in props.items():
            e.set_editor_property(k, v)
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
        if isinstance(v, (int, float)):
            return self.node(u.MaterialExpressionConstant, r=float(v))
        return v

    # parameters
    def scalar(self, name, default, group='PU'):
        return self.node(u.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(default), group=group)

    def vector(self, name, rgb, group='PU'):
        return self.node(u.MaterialExpressionVectorParameter, parameter_name=name,
                         default_value=u.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)

    def tex(self, name, texture, uv=None, group='PU'):
        e = self.node(u.MaterialExpressionTextureSampleParameter2D, parameter_name=name, group=group)
        e.set_editor_property('texture', texture)
        e.set_editor_property('sampler_type', sampler_for(texture))
        if uv is not None:
            self.link(uv, e, 'UVs')
        return e

    # math
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

    def div(self, a, b):
        return self.bin(u.MaterialExpressionDivide, a, b)

    def maxi(self, a, b):
        return self.bin(u.MaterialExpressionMax, a, b)

    def dot(self, a, b):
        return self.bin(u.MaterialExpressionDotProduct, a, b)

    def dist(self, a, b):
        return self.bin(u.MaterialExpressionDistance, a, b)

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

    def absf(self, a):
        return self.one(u.MaterialExpressionAbs, a)

    def frac(self, a):
        return self.one(u.MaterialExpressionFrac, a)

    def floor(self, a):
        return self.one(u.MaterialExpressionFloor, a)

    def sine(self, a):
        return self.one(u.MaterialExpressionSine, a, period=1.0)

    def mask(self, a, r=False, g=False, b=False, al=False):
        return self.one(u.MaterialExpressionComponentMask, a, r=r, g=g, b=b, a=al)

    def c2(self, x, y):
        return self.node(u.MaterialExpressionConstant2Vector, r=float(x), g=float(y))

    def c3(self, x, y, z):
        return self.node(u.MaterialExpressionConstant3Vector, constant=u.LinearColor(x, y, z, 1))

    def time(self):
        return self.node(u.MaterialExpressionTime)

    def uv(self):
        return self.node(u.MaterialExpressionTextureCoordinate)

    def hash(self, x):
        # frac(sin(x * 12.9898) * 43758.5453), the usual shader hash (Sine has period 1, fine for a hash)
        return self.frac(self.mul(self.sine(self.mul(x, 12.9898)), 43758.5453))

    def facing(self, vertex_normal=False):
        n = self.node(u.MaterialExpressionVertexNormalWS if vertex_normal else u.MaterialExpressionPixelNormalWS)
        c = self.node(u.MaterialExpressionCameraVectorWS)
        return self.absf(self.dot(n, c))

    def flicker_and_pulse(self):
        t = self.time()
        rate = self.scalar('FlickerRate', 0.0, 'Animation')
        amt = self.scalar('FlickerAmount', 0.0, 'Animation')
        h = self.hash(self.floor(self.mul(t, rate)))
        flick = self.lerp(1.0, h, amt)
        hz = self.scalar('PulseHz', 0.0, 'Animation')
        pamt = self.scalar('PulseAmount', 0.0, 'Animation')
        p = self.add(0.5, self.mul(0.5, self.sine(self.mul(t, hz))))
        pulse = self.lerp(1.0, p, pamt)
        boost = self.scalar('GlowBoost', 1.0, 'Animation')
        return self.mul(self.mul(flick, pulse), boost)

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
        info = {'path': self.path, 'expressions': MEL.get_num_material_expressions(self.m), 'link_failures': self.fails,
                'scalars': [str(x) for x in MEL.get_scalar_parameter_names(self.m)],
                'vectors': [str(x) for x in MEL.get_vector_parameter_names(self.m)],
                'textures': [str(x) for x in MEL.get_texture_parameter_names(self.m)]}
        if self.fails:
            err('%s link failures: %s' % (self.path, self.fails))
        R['masters'][self.path.rsplit('/', 1)[1]] = info
        return self.m


def sampler_for(t):
    cs = t.get_editor_property('compression_settings')
    srgb = t.get_editor_property('srgb')
    T = u.TextureCompressionSettings
    S = u.MaterialSamplerType
    if cs == T.TC_NORMALMAP:
        return S.SAMPLERTYPE_NORMAL
    if cs == T.TC_MASKS:
        return S.SAMPLERTYPE_MASKS
    if cs in (T.TC_GRAYSCALE, getattr(T, 'TC_ALPHA', None)):
        return S.SAMPLERTYPE_GRAYSCALE if srgb else S.SAMPLERTYPE_LINEAR_GRAYSCALE
    return S.SAMPLERTYPE_COLOR if srgb else S.SAMPLERTYPE_LINEAR_COLOR


def T(name):
    t = u.load_asset('%s/%s' % (REC.TEX, name))
    if not t:
        raise RuntimeError('missing texture ' + name)
    return t


BM = u.BlendMode
SM = u.MaterialShadingModel
MP = u.MaterialProperty


def build_item_fx():
    it = REC.ITEMS['Medkit']
    b = MB(REC.MATS + '/M_PU_ItemFX', BM.BLEND_OPAQUE, SM.MSM_DEFAULT_LIT)
    uv = b.uv()
    base = b.tex('BaseColorTex', u.load_asset(it['tex'] + 'BaseColor'), uv, 'Maps')
    nrm = b.tex('NormalTex', u.load_asset(it['tex'] + 'Normal'), uv, 'Maps')
    orm = b.tex('ORMTex', u.load_asset(it['tex'] + 'ORM'), uv, 'Maps')
    rgb = (base, 'RGB')
    lum = b.dot(rgb, b.c3(0.3, 0.59, 0.11))
    col = b.mul(b.mul(b.lerp(rgb, lum, b.scalar('Desaturate', 0.0, 'Look')), b.scalar('Darken', 1.0, 'Look')),
                b.vector('Tint', (1, 1, 1), 'Look'))
    b.out(col, MP.MP_BASE_COLOR)
    b.out((nrm, 'RGB'), MP.MP_NORMAL)
    b.out((orm, 'G'), MP.MP_ROUGHNESS)
    b.out((orm, 'B'), MP.MP_METALLIC)
    fr = b.node(u.MaterialExpressionFresnel)
    b.link(b.scalar('RimExponent', 3.0, 'Rim'), fr, 'ExponentIn')
    b.link(b.val(0.04), fr, 'BaseReflectFractionIn')
    rim = b.mul(b.mul(fr, b.vector('RimColor', (1, 0.1, 0.1), 'Rim')), b.scalar('RimIntensity', 0.0, 'Rim'))
    selfg = b.mul(b.mul(rgb, b.vector('SelfGlowColor', (1, 1, 1), 'SelfGlow')), b.scalar('SelfGlowAmount', 0.0, 'SelfGlow'))
    t = b.time()
    nuv = b.add(b.mul(uv, b.scalar('VeinScale', 3.0, 'Veins')), b.mul(t, b.scalar('VeinPan', 0.0, 'Veins')))
    n = b.tex('VeinNoise', T('T_PU_Noise'), nuv, 'Veins')
    vein = b.sat(b.sub(1.0, b.div(b.absf(b.sub((n, 'R'), 0.5)), b.scalar('VeinWidth', 0.04, 'Veins'))))
    veins = b.mul(b.mul(vein, b.vector('VeinColor', (1, 0.3, 0.3), 'Veins')), b.scalar('VeinIntensity', 0.0, 'Veins'))
    em = b.mul(b.add(b.add(rim, selfg), veins), b.flicker_and_pulse())
    b.out(em, MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_glow_additive():
    b = MB(REC.MATS + '/M_PU_GlowAdditive', BM.BLEND_ADDITIVE, SM.MSM_UNLIT, two_sided=True)
    uv = b.uv()
    t = b.time()
    m = b.tex('MaskTex', T('T_PU_White'), b.mul(uv, b.scalar('MaskTiling', 1.0, 'Mask')), 'Mask')
    mask = b.dot((m, 'RGB'), b.vector('MaskChannels', (1, 0, 0), 'Mask'))
    r = b.mul(b.dist(uv, b.c2(0.5, 0.5)), 2.0)
    radial = b.power(b.sat(b.sub(1.0, r)), b.scalar('RadialPower', 2.0, 'Shape'))
    mask = b.mul(mask, b.lerp(1.0, radial, b.scalar('RadialAmount', 0.0, 'Shape')))
    v = b.mask(uv, g=True)
    vg = b.power(b.maxi(b.sub(1.0, v), 0.0001), b.scalar('VPower', 1.0, 'Shape'))
    mask = b.mul(mask, b.lerp(1.0, vg, b.scalar('VAmount', 0.0, 'Shape')))
    fac = b.power(b.maxi(b.facing(), 0.0001), b.scalar('FacingPower', 1.0, 'Shape'))
    mask = b.mul(mask, b.lerp(1.0, fac, b.scalar('FacingAmount', 0.0, 'Shape')))
    pan = b.append(b.scalar('NoisePanU', 0.0, 'Noise'), b.scalar('NoisePanV', 0.0, 'Noise'))
    nuv = b.add(b.mul(uv, b.scalar('NoiseTiling', 1.0, 'Noise')), b.mul(t, pan))
    n = b.tex('NoiseTex', T('T_PU_Noise'), nuv, 'Noise')
    mask = b.mul(mask, b.lerp(1.0, b.mul((n, 'R'), b.scalar('NoiseGain', 1.6, 'Noise')), b.scalar('NoiseAmount', 0.0, 'Noise')))
    wz = b.mask(b.node(u.MaterialExpressionWorldPosition), b=True)
    s = b.add(0.5, b.mul(0.5, b.sine(b.add(b.div(wz, b.scalar('ScanSpacing', 2.0, 'Scan')), b.mul(t, b.scalar('ScanSpeed', 0.5, 'Scan'))))))
    s = b.power(b.maxi(s, 0.0001), b.scalar('ScanSharp', 1.0, 'Scan'))
    mask = b.mul(mask, b.lerp(1.0, s, b.scalar('ScanAmount', 0.0, 'Scan')))
    df = b.node(u.MaterialExpressionDepthFade)
    b.link(b.val(1.0), df, ['Opacity', 'InOpacity'])
    b.link(b.maxi(b.scalar('FadeDistance', 10.0, 'Shape'), 0.01), df, 'FadeDistance')
    col = b.mul(b.vector('Color', (1, 0.2, 0.1)), b.scalar('Intensity', 1.0))
    em = b.mul(b.mul(b.mul(col, mask), b.flicker_and_pulse()), df)
    b.out(em, MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_holo_lofi():
    it = REC.ITEMS['Medkit']
    b = MB(REC.MATS + '/M_PU_HoloLoFi', BM.BLEND_ADDITIVE, SM.MSM_UNLIT)
    uv = b.uv()
    t = b.time()
    res = b.scalar('LowRes', 48.0, 'Holo')
    uvq = b.div(b.floor(b.mul(uv, res)), res)
    base = b.tex('BaseTex', u.load_asset(it['tex'] + 'BaseColor'), uvq, 'Holo')
    lum = b.dot((base, 'RGB'), b.c3(0.3, 0.59, 0.11))
    edge = b.power(b.maxi(b.sub(1.0, b.facing()), 0.0001), b.scalar('EdgePower', 2.5, 'Holo'))
    val = b.add(b.add(b.mul(lum, b.scalar('BaseAmount', 1.0, 'Holo')), b.mul(edge, b.scalar('EdgeAmount', 1.0, 'Holo'))),
                b.scalar('Floor', 0.05, 'Holo'))
    wz = b.sub(b.mask(b.node(u.MaterialExpressionWorldPosition), b=True), b.mask(b.node(u.MaterialExpressionObjectPositionWS), b=True))
    scan = b.add(0.5, b.mul(0.5, b.sine(b.add(b.div(wz, b.scalar('ScanSpacing', 1.2, 'Scan')), b.mul(t, b.scalar('ScanSpeed', 0.8, 'Scan'))))))
    scan = b.power(b.maxi(scan, 0.0001), b.scalar('ScanSharp', 2.0, 'Scan'))
    scan = b.lerp(1.0, scan, b.scalar('ScanAmount', 0.6, 'Scan'))
    band = b.frac(b.sub(b.div(wz, b.scalar('BandSpacing', 16.0, 'Bands')), b.mul(t, b.scalar('BandSpeed', 0.35, 'Bands'))))
    drop = b.sat(b.mul(b.sub(band, b.scalar('BandWidth', 0.16, 'Bands')), 30.0))
    drop = b.lerp(1.0, drop, b.scalar('BandAmount', 0.8, 'Bands'))
    sp = b.node(u.MaterialExpressionScreenPosition)
    jit = b.mul(b.hash(b.floor(b.mul(t, 24.0))), b.c2(0.37, 0.61))
    guv = b.add(b.mul(b.mul((sp, 'ViewportUV'), b.c2(16.0, 9.0)), b.scalar('GrainTiling', 4.0, 'Grain')), jit)
    g = b.tex('GrainTex', T('T_PU_Noise'), guv, 'Grain')
    grain = b.lerp(1.0, b.mul((g, 'R'), 1.7), b.scalar('GrainAmount', 0.5, 'Grain'))
    col = b.mul(b.vector('Color', (1, 0.2, 0.1)), b.scalar('Intensity', 1.5))
    em = b.mul(b.mul(b.mul(b.mul(b.mul(col, val), scan), drop), grain), b.flicker_and_pulse())
    b.out(em, MP.MP_EMISSIVE_COLOR)
    # glitch jitter: now and then a slice of the hologram slides sideways
    jr = b.floor(b.mul(t, b.scalar('JitterRate', 6.0, 'Glitch')))
    h1 = b.hash(jr)
    h2 = b.hash(b.add(jr, 17.31))
    on = b.sat(b.mul(b.sub(h2, 0.62), 12.0))
    sl = b.sat(b.mul(b.sine(b.add(b.div(wz, b.scalar('JitterBand', 8.0, 'Glitch')), h1)), 3.0))
    off = b.mul(b.mul(b.mul(b.sub(h1, 0.5), b.mul(2.0, b.scalar('JitterAmount', 2.0, 'Glitch'))), on), sl)
    b.out(b.append(off, b.c2(0.0, 0.0)), MP.MP_WORLD_POSITION_OFFSET)
    return b.finish()


def build_prop_simple():
    b = MB(REC.MATS + '/M_PU_PropSimple', BM.BLEND_OPAQUE, SM.MSM_DEFAULT_LIT)
    uv = b.uv()
    n = b.tex('GrimeTex', T('T_PU_Noise'), b.mul(uv, b.scalar('GrimeTiling', 3.0, 'Paint')), 'Paint')
    grime = b.lerp(1.0, b.mul((n, 'R'), 1.2), b.scalar('GrimeAmount', 0.0, 'Paint'))
    b.out(b.mul(b.vector('Color', (0.3, 0.3, 0.3), 'Paint'), grime), MP.MP_BASE_COLOR)
    b.out(b.scalar('Roughness', 0.6, 'Paint'), MP.MP_ROUGHNESS)
    b.out(b.scalar('Metallic', 0.0, 'Paint'), MP.MP_METALLIC)
    em = b.mul(b.mul(b.vector('EmissiveColor', (0, 0, 0), 'Glow'), b.scalar('EmissiveIntensity', 0.0, 'Glow')), b.flicker_and_pulse())
    b.out(em, MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_heat_haze():
    b = MB(REC.MATS + '/M_PU_HeatHaze', BM.BLEND_TRANSLUCENT, SM.MSM_DEFAULT_LIT)
    try:
        b.m.set_editor_property('refraction_method', u.RefractionMode.RM_PIXEL_NORMAL_OFFSET)
    except Exception as e:  # noqa: BLE001
        warn('refraction_method: %s' % e)
    uv = b.uv()
    t = b.time()
    nuv = b.add(b.mul(uv, b.scalar('Tiling', 1.5, 'Haze')), b.mul(t, b.append(0.0, b.mul(-1.0, b.scalar('Speed', 0.3, 'Haze')))))
    nt = u.load_asset('/Game/Vefects/Easy_Shockwaves_VFX/Shared/Textures/T_VFX_Easy_Shockwaves_Noise_01_Normal')
    nn = b.tex('HazeNormal', nt, nuv, 'Haze')
    fade = b.power(b.maxi(b.facing(vertex_normal=True), 0.0001), 1.5)
    amt = b.mul(b.scalar('Strength', 0.5, 'Haze'), fade)
    b.out(b.lerp(b.c3(0, 0, 1), (nn, 'RGB'), amt), MP.MP_NORMAL)
    b.out(b.scalar('Opacity', 0.02, 'Haze'), MP.MP_OPACITY)
    b.out(b.mul(b.scalar('Refraction', 1.0, 'Haze'), fade), MP.MP_REFRACTION)
    return b.finish()


# ----------------------------------------------------------------------------------------------------------------
# per-look instances

PARENTS = {}


def tex_token(v, item):
    if not isinstance(v, str):
        return v
    if v == '$basetex':
        return item['tex'] + 'BaseColor'
    if v.startswith('/'):
        return v
    return '%s/T_PU_%s' % (REC.TEX, v)


def make_mi(path, parent, params, item):
    folder, name = path.rsplit('/', 1)
    mi = u.load_asset(path)
    if not mi:
        mi = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    else:
        MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, parent)
    params = dict(params)
    switches = params.pop('_switches', {})
    textures = dict(params.pop('_textures', {}))
    fails = []
    for k, v in params.items():
        v = REC.resolve(v, item)
        if k in ('MaskTex', 'BaseTex', 'BaseColorTex'):
            textures[k] = v
            continue
        if isinstance(v, (tuple, list)):
            c = list(v) + [1.0] * (4 - len(v))
            MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(c[0], c[1], c[2], c[3]))
        else:
            MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in textures.items():
        tp = tex_token(REC.resolve(v, item), item)
        t = u.load_asset(tp)
        if not t:
            fails.append('texture %s=%s missing' % (k, tp))
            continue
        MEL.set_material_instance_texture_parameter_value(mi, k, t)
    for k, v in switches.items():
        try:
            MEL.set_material_instance_static_switch_parameter_value(mi, k, bool(v))
        except Exception as e:  # noqa: BLE001
            fails.append('switch %s: %s' % (k, e))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    # read back a couple of values (the setters return False in 5.8 even when they work)
    rb = {}
    for k, v in list(params.items())[:3]:
        if not isinstance(REC.resolve(v, item), (tuple, list)):
            rb[k] = round(MEL.get_material_instance_scalar_parameter_value(mi, k), 3)
    if fails:
        warn('%s: %s' % (path, fails))
    return {'path': path, 'readback': rb, 'fails': fails}


def item_textures(item):
    return {'BaseColorTex': item['tex'] + 'BaseColor', 'NormalTex': item['tex'] + 'Normal', 'ORMTex': item['tex'] + 'ORM'}


def build_mat(spec, path, item):
    kind, params = spec
    if kind == 'asset':
        return {'path': params, 'vendor': True}
    params = dict(params)
    if kind == 'ItemFX':
        params.setdefault('_textures', {}).update(item_textures(item))
    if kind == 'HoloLoFi':
        params['BaseTex'] = '$basetex'
    return make_mi(path, PARENTS[kind], params, item)


def duplicate_niagara(src, dst, el, item):
    # reuse an earlier duplicate (deleting a loaded Niagara system can fail); only the user defaults change
    a = u.load_asset(dst) if EAL.does_asset_exist(dst) else EAL.duplicate_asset(src, dst)
    if not a:
        err('niagara duplicate failed %s -> %s' % (src, dst))
        return None
    res = {'path': dst, 'source': src, 'set': {}}
    for k, v in el.get('floats', {}).items():
        res['set'][k] = u.HoverAuthoring.set_niagara_user_float(a, k, float(v))
    for k, v in el.get('colors', {}).items():
        c = REC.resolve(v, item)
        res['set'][k] = u.HoverAuthoring.set_niagara_user_color(a, k, u.LinearColor(c[0], c[1], c[2], 1.0))
    EAL.save_loaded_asset(a)
    bad = [k for k, ok in res['set'].items() if not ok]
    if bad:
        warn('%s: user parameters not set %s' % (dst, bad))
    return res


def build_looks():
    for look in REC.LOOKS:
        if ONLY and look['n'] not in ONLY:
            continue
        folder = REC.look_folder(look)
        EAL.make_directory(folder)
        # Niagara duplicates belong under Effects/PowerUps (see REC.ns_path); clear strays from earlier runs
        for p in EAL.list_assets(folder, False, False):
            if isinstance(u.load_asset(p), u.NiagaraSystem):
                EAL.delete_asset(p.split('.')[0])
        L = R['looks'][look['key']] = {'n': look['n'], 'folder': folder, 'items': {}}
        for key in REC.ITEM_ORDER:
            item = REC.ITEMS[key]
            I = L['items'][key] = {'elements': []}
            if look['item'].get('material'):
                I['item_material'] = build_mat(look['item']['material'], REC.mi_path(look, key, 'Item'), item)
            for el in look['elements']:
                e = {'kind': el['kind'], 'name': el.get('name', el['kind'])}
                if el['kind'] == 'mesh':
                    e['slots'] = {}
                    for slot, spec in el['slots'].items():
                        e['slots'][REC.slot_key(slot)] = build_mat(spec, REC.mi_path(look, key, el['name'], slot), item)
                elif el['kind'] == 'itemcopy':
                    e['material'] = build_mat(el['material'], REC.mi_path(look, key, el['name']), item)
                elif el['kind'] == 'niagara':
                    e['system'] = duplicate_niagara(el['system'], REC.ns_path(look, key, el['name']), el, item)
                I['elements'].append(e)
        log('look', look['n'], look['key'], 'ok')


# ----------------------------------------------------------------------------------------------------------------
# showcase level

ACTOR = None


def V(t):
    return u.Vector(t[0], t[1], t[2])


def spawn_mesh(path, loc, yaw=0.0, scale=(1, 1, 1), pitch=0.0, roll=0.0, label=None):
    mesh = u.load_asset(path)
    if not mesh:
        warn('backdrop mesh missing ' + path)
        return None
    a = ACTOR.spawn_actor_from_object(mesh, V(loc), u.Rotator(roll=roll, pitch=pitch, yaw=yaw))
    a.set_actor_scale3d(V(scale))
    a.set_editor_property('tags', [u.Name('PUShowcase')])
    if label:
        a.set_actor_label(label)
    return a


def world_at(fwd, right, z=0.0):
    f, r = REC.view_basis()
    return (f[0] * fwd + r[0] * right, f[1] * fwd + r[1] * right, z)


def build_level():
    global ACTOR
    LES = u.get_editor_subsystem(u.LevelEditorSubsystem)
    ACTOR = u.get_editor_subsystem(u.EditorActorSubsystem)
    if EAL.does_asset_exist(REC.LEVEL):
        ok = LES.load_level(REC.LEVEL)
        R['level']['mode'] = 'reloaded %s' % ok
        for a in ACTOR.get_all_level_actors():
            if u.Name('PUShowcase') in list(a.tags):
                ACTOR.destroy_actor(a)
    else:
        ok = LES.new_level_from_template(REC.LEVEL, '/Engine/Maps/Templates/Template_Default')
        R['level']['mode'] = 'new_level_from_template %s' % ok
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    actors = ACTOR.get_all_level_actors()
    R['level']['template_actors'] = sorted('%s:%s' % (a.get_class().get_name(), a.get_actor_label()) for a in actors)
    vy = REC.VIEW_YAW
    for a in actors:
        cls = a.get_class().get_name()
        if cls == 'StaticMeshActor' and u.Name('PUShowcase') not in list(a.tags):
            ACTOR.destroy_actor(a)  # template floor
        elif cls == 'VolumetricCloud':
            ACTOR.destroy_actor(a)
        elif cls == 'DirectionalLight':
            c = a.get_component_by_class(u.DirectionalLightComponent)
            # dusk sun sitting on the skyline behind the scene (hidden by the buildings, it colours the sky)
            a.set_actor_rotation(u.Rotator(roll=0, pitch=-2.0, yaw=vy + 165.0), False)
            c.set_editor_property('intensity', 2.5)
            c.set_editor_property('light_color', u.Color(r=255, g=185, b=150, a=255))
            c.set_editor_property('cast_shadows', False)
            try:
                c.set_editor_property('atmosphere_sun_disk_color_scale', u.LinearColor(0, 0, 0, 1))
            except Exception as e:  # noqa: BLE001
                warn('sun disk: %s' % e)
            c.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
        elif cls == 'SkyLight':
            c = a.get_component_by_class(u.SkyLightComponent)
            c.set_editor_property('intensity', 1.2)
            c.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
            try:
                c.set_editor_property('real_time_capture', True)
                c.set_editor_property('lower_hemisphere_is_black', True)
            except Exception as e:  # noqa: BLE001
                warn('skylight: %s' % e)
        elif cls == 'ExponentialHeightFog':
            c = a.get_component_by_class(u.ExponentialHeightFogComponent)
            for k, v in (('fog_density', 0.045), ('fog_height_falloff', 0.35), ('start_distance', 250.0),
                         ('fog_inscattering_luminance', u.LinearColor(0.05, 0.045, 0.045, 1)),
                         ('directional_inscattering_exponent', 6.0),
                         ('directional_inscattering_luminance', u.LinearColor(0.12, 0.08, 0.06, 1)),
                         ('enable_volumetric_fog', True)):
                try:
                    c.set_editor_property(k, v)
                except Exception as e:  # noqa: BLE001
                    warn('fog %s: %s' % (k, e))
        elif cls == 'PlayerStart':
            a.set_actor_location(V(world_at(-3500, 0, 120)), False, False)
    # post process: manual exposure, no motion blur
    ppv = ACTOR.spawn_actor_from_class(u.PostProcessVolume, u.Vector(0, 0, 0))
    ppv.set_editor_property('tags', [u.Name('PUShowcase')])
    ppv.set_actor_label('PU_PostProcess')
    ppv.set_editor_property('unbound', True)
    s = ppv.get_editor_property('settings')
    for k, v in (('auto_exposure_method', u.AutoExposureMethod.AEM_MANUAL), ('auto_exposure_bias', -1.0),
                 ('auto_exposure_apply_physical_camera_exposure', False), ('motion_blur_amount', 0.0),
                 ('bloom_intensity', 0.9), ('vignette_intensity', 0.45)):
        try:
            s.set_editor_property('override_' + k, True)
            s.set_editor_property(k, v)
        except Exception as e:  # noqa: BLE001
            warn('ppv %s: %s' % (k, e))
    ppv.set_editor_property('settings', s)
    # ground: tile the pack's asphalt road pieces, else one plane with the asphalt material
    asphalt = u.load_asset('/Game/PostApocalypticCity/Meshes/Roads/SM_Asphalt01')
    tiled = 0
    if asphalt:
        bb = asphalt.get_bounding_box()
        sx, sy = bb.max.x - bb.min.x, bb.max.y - bb.min.y
        R['level']['asphalt_tile'] = [round(sx), round(sy), round(bb.min.z, 1), round(bb.max.z, 1)]
        if sx >= 200 and sy >= 200:
            nx, ny = min(int(4200 / sx) + 1, 24), min(int(4200 / sy) + 1, 24)
            for i in range(nx):
                for j in range(ny):
                    x = -1400 + i * sx - (bb.min.x)
                    y = -2100 + j * sy - (bb.min.y)
                    a = spawn_mesh('/Game/PostApocalypticCity/Meshes/Roads/SM_Asphalt01', (x, y, -bb.max.z), 0)
                    tiled += 1 if a else 0
    if not tiled:
        a = spawn_mesh('/Engine/BasicShapes/Plane', (0, 0, 0), 0, (60, 60, 1), label='PU_Ground')
        mi = u.load_asset('/Game/PostApocalypticCity/Materials/MaterialInstance/MI_Asphalt')
        if a and mi:
            a.static_mesh_component.set_material(0, mi)
    R['level']['ground_tiles'] = tiled
    # backdrop (view frame: fwd = away from the camera behind the items, right = screen right)
    P = '/Game/PostApocalypticCity/Meshes/'
    spawn_mesh(P + 'SM_Sedan03', world_at(560, 160), vy + 62, label='PU_Wreck')
    spawn_mesh(P + 'SM_MilitaryBase_Concrete_Barrier_Lrg_a', world_at(360, -300), vy + 100)
    spawn_mesh(P + 'SM_MilitaryBase_Concrete_Barrier_Lrg_b', world_at(420, -150), vy + 80)
    spawn_mesh(P + 'SM_Barrel01', world_at(300, 10), vy + 20)
    spawn_mesh(P + 'SM_Barrel02', world_at(330, 70), vy + 50, pitch=0, roll=90)
    spawn_mesh(P + 'SM_MERGED_Tires01', world_at(260, 290), vy)
    spawn_mesh(P + 'SM_TrafficCone01', world_at(170, -230), vy + 30, roll=88)
    spawn_mesh(P + 'SM_GarbageBag01', world_at(380, 300), vy)
    spawn_mesh(P + 'SM_GarbageBag02', world_at(410, 360), vy + 40)
    for k, (fw, rt) in enumerate(((140, -190), (120, 240), (230, -60))):
        spawn_mesh(P + 'SM_Ground_0%d' % (2 + k % 4), world_at(fw, rt, 0), vy + k * 70)
    # more street junk so the 10 m shot reads as a wrecked street, not a plain
    spawn_mesh(P + 'SM_Sedan03', world_at(60, -560), vy - 75, label='PU_Wreck3')
    spawn_mesh(P + 'SM_MilitaryBase_Concrete_Barrier_Med_a', world_at(120, 520), vy + 15)
    spawn_mesh(P + 'SM_MERGED_Tires02', world_at(-260, 430), vy)
    spawn_mesh(P + 'SM_Barrel01', world_at(-320, -420), vy)
    spawn_mesh(P + 'SM_Barrel03', world_at(-280, -360), vy, roll=90)
    spawn_mesh(P + 'SM_GarbageBag03', world_at(-200, 560), vy)
    spawn_mesh(P + 'SM_TrafficCone02', world_at(-450, 200), vy)
    spawn_mesh(P + 'SM_MilitaryBase_Concrete_Barrier_Lrg_a', world_at(900, -40), vy + 92)
    spawn_mesh(P + 'SM_MilitaryBase_Concrete_Barrier_Lrg_b', world_at(980, 380), vy + 70)
    spawn_mesh(P + 'Suv_Vehicles/SM_SUV01' if u.load_asset(P + 'Suv_Vehicles/SM_SUV01') else P + 'SM_SUV01',
               world_at(820, -520), vy - 20, label='PU_Wreck2')
    # skyline: stacked building pieces far down the street. Off (empty): the pack's building prefabs have far-off
    # pivots and walled the camera in on the 2026-10-31 r2 render; fog and the dusk sky carry the background instead.
    SKYLINE = ()
    B = P + 'Buildings/Prefabs/'
    for k, (fw, rt, mids) in enumerate(SKYLINE):
        kind = '01' if k % 2 == 0 else '03'
        parts = [B + 'SM_Building%s_Bottom' % kind] + [B + ('SM_Building01_Middle_A' if kind == '01' else 'SM_Building03_Middle')] * mids +                 ([B + 'SM_Building01_Roof'] if kind == '01' else [])
        z = 0.0
        for part in parts:
            mesh = u.load_asset(part)
            if not mesh:
                warn('building part missing ' + part)
                break
            bb = mesh.get_bounding_box()
            loc = world_at(fw, rt, z - bb.min.z)
            spawn_mesh(part, loc, vy + 180)
            z += bb.max.z - bb.min.z
        R['level'].setdefault('skyline_heights', []).append(round(z))
    # moonlight key from the camera side: the items keep a readable silhouette even with no glow on them
    moon = ACTOR.spawn_actor_from_class(u.DirectionalLight, u.Vector(0, 0, 500))
    moon.set_editor_property('tags', [u.Name('PUShowcase')])
    moon.set_actor_label('PU_Moon')
    moon.set_actor_rotation(u.Rotator(roll=0, pitch=-38.0, yaw=vy + 35.0), False)
    mc = moon.get_component_by_class(u.DirectionalLightComponent)
    mc.set_editor_property('mobility', u.ComponentMobility.MOVABLE)
    mc.set_editor_property('intensity', 2.2)
    mc.set_editor_property('light_color', u.Color(r=150, g=178, b=255, a=255))
    for k, v in (('atmosphere_sun_light', False), ('forward_shading_priority', -1)):
        try:
            mc.set_editor_property(k, v)
        except Exception as e:  # noqa: BLE001
            warn('moon %s: %s' % (k, e))
    # a fire barrel far back for warmth
    fb = spawn_mesh(P + 'SM_Barrel03', world_at(1300, 620), vy, label='PU_FireBarrel')
    fire = u.load_asset('/Game/PostApocalypticCity/Particles/NS_Fire_01')
    if fb and fire:
        loc = world_at(1300, 620, 75)
        na = ACTOR.spawn_actor_from_class(u.NiagaraActor, V(loc))
        na.niagara_component.set_asset(fire)
        na.set_actor_scale3d(u.Vector(0.5, 0.5, 0.5))
        na.set_editor_property('tags', [u.Name('PUShowcase')])
        pl = ACTOR.spawn_actor_from_class(u.PointLight, V(world_at(1300, 620, 110)))
        pl.set_editor_property('tags', [u.Name('PUShowcase')])
        pc = pl.get_component_by_class(u.PointLightComponent)
        pc.set_editor_property('intensity_units', u.LightUnits.CANDELAS)
        pc.set_editor_property('intensity', 30.0)
        pc.set_editor_property('attenuation_radius', 1500.0)
        pc.set_editor_property('light_color', u.Color(r=255, g=140, b=60, a=255))
    ws = world.get_world_settings()
    try:
        ws.set_editor_property('default_game_mode', u.GameModeBase.static_class())
    except Exception as e:  # noqa: BLE001
        warn('game mode override: %s' % e)
    R['level']['saved'] = LES.save_current_level()


def describe_extra():
    for p in ['/Game/Zombie/Demo/Effects/NS_Sparks', '/Game/A_Surface_Footstep/Niagara_FX/ParticleSystems/PSN_Sparks_Surface',
              '/Game/Blood_VFX_Pack/Particles/Parts/P_E_Sparks_01']:
        a = u.load_asset(p)
        if a:
            try:
                d = json.loads(u.HoverAuthoring.describe_flash_asset(a))
                R['niagara_described'][p] = {'duration_s': d.get('duration_s'),
                                             'user': [(q['name'], q.get('value')) for q in d.get('user_parameters', [])]}
            except Exception as e:  # noqa: BLE001
                R['niagara_described'][p] = str(e)


def main():
    if os.environ.get('PU_SKIP_IMPORT') != '1':
        import_textures()
        import_props()
    PARENTS['ItemFX'] = build_item_fx()
    PARENTS['GlowAdditive'] = build_glow_additive()
    PARENTS['HoloLoFi'] = build_holo_lofi()
    PARENTS['PropSimple'] = build_prop_simple()
    PARENTS['HeatHaze'] = build_heat_haze()
    PARENTS['Hologram'] = u.load_asset('/Game/CyberpunkHolograms/Materials/MM_Hologram')
    if not PARENTS['Hologram']:
        err('MM_Hologram missing (copy from SpaceSurvival first)')
    build_looks()
    describe_extra()
    if os.environ.get('PU_SKIP_LEVEL') != '1':
        build_level()


try:
    main()
except Exception as e:  # noqa: BLE001
    err('exception %s\n%s' % (e, traceback.format_exc()))
finally:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_DIR + '/author_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s errors=%d warnings=%d looks=%d' % (R['ok'], len(R['errors']), len(R['warnings']), len(R['looks'])))
    u.SystemLibrary.quit_editor()
