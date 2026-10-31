"""AuthorPowerUpStyles2.py - build the round-2 power-up look assets (nullrhi). Round-1 assets are not touched.

Reads Scripts/PowerUpStyleRecipes2.py and makes:
  Styles/Shared/Materials  M_PU_ItemFX2 (opaque item skin: seam / emblem / swirl / veins / arcs / rim / flicker / pulse)
                           M_PU_Shell   (additive shell on an inflated copy of the item: edge / core / mist / arcs / height)
                           (round-1 masters M_PU_GlowAdditive, M_PU_PropSimple, M_PU_HeatHaze are reused, not rebuilt)
  Styles/R2/S<NN>_<Key>/   MI_S<NN>_<Medkit|Nuke>_<Element>[_<Slot>]
  Effects/PowerUps/R2/S<NN>_<Key>/  NS_S<NN>_<Item>_<Element>: duplicates of pack Niagara systems with the user
                           parameters set (pack originals are never edited)
Receipt: D:/AFS_Comparisons/PowerUps_20261031/Styles/R2/author2_receipt.json (+ Niagara user parameter dumps)
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput -ExecutePythonScript=<this>
Env: PU2_LOOKS=5,6 limits the looks, PU2_BENCH=1 also builds the particle bench looks (91-99).
"""
import json
import os
import sys
import time
import traceback

import unreal as u

sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import importlib  # noqa: E402

import PowerUpStyleRecipes as REC  # noqa: E402
import PowerUpStyleRecipes2 as REC2  # noqa: E402

importlib.reload(REC)
importlib.reload(REC2)

OUT_DIR = 'D:/AFS_Comparisons/PowerUps_20261031/Styles/R2'
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
R = {'ok': True, 'errors': [], 'warnings': [], 'masters': {}, 'looks': {}, 'niagara': {}, 'probe': {},
     'time': time.strftime('%Y-%m-%d %H:%M:%S')}
ONLY = [int(x) for x in os.environ.get('PU2_LOOKS', '').split(',') if x.strip()]
BENCH = os.environ.get('PU2_BENCH') == '1'


def log(*a):
    print('PU_AUTHOR2', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def warn(m):
    R['warnings'].append(m)
    log('WARN', m)


# ----------------------------------------------------------------------------------------------------------------
# material graph helper (same as AuthorPowerUpStyles.MB, plus 3D noise and local position)

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
        self.x = -2000
        self.y = 0
        self.fails = []

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
        if isinstance(v, (int, float)):
            return self.node(u.MaterialExpressionConstant, r=float(v))
        return v

    def scalar(self, name, default, group='PU'):
        return self.node(u.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(default), group=group)

    def vector(self, name, rgb, group='PU'):
        return self.node(u.MaterialExpressionVectorParameter, parameter_name=name,
                         default_value=u.LinearColor(rgb[0], rgb[1], rgb[2], 1.0), group=group)

    def tex(self, name, texture, uv=None, group='PU', sampler=None):
        e = self.node(u.MaterialExpressionTextureSampleParameter2D, parameter_name=name, group=group)
        e.set_editor_property('texture', texture)
        e.set_editor_property('sampler_type', sampler or sampler_for(texture))
        if uv is not None:
            self.link(uv, e, 'UVs')
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

    def div(self, a, b):
        return self.bin(u.MaterialExpressionDivide, a, b)

    def maxi(self, a, b):
        return self.bin(u.MaterialExpressionMax, a, b)

    def mini(self, a, b):
        return self.bin(u.MaterialExpressionMin, a, b)

    def dot(self, a, b):
        return self.bin(u.MaterialExpressionDotProduct, a, b)

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

    def c3(self, x, y, z):
        return self.node(u.MaterialExpressionConstant3Vector, constant=u.LinearColor(x, y, z, 1))

    def time(self):
        return self.node(u.MaterialExpressionTime)

    def uv(self):
        return self.node(u.MaterialExpressionTextureCoordinate)

    def hash(self, x):
        return self.frac(self.mul(self.sine(self.mul(x, 12.9898)), 43758.5453))

    def local_pos(self):
        cls = getattr(u, 'MaterialExpressionLocalPosition', None)
        if cls is not None:
            R['probe']['local_position'] = 'MaterialExpressionLocalPosition'
            return self.node(cls)
        R['probe']['local_position'] = 'TransformPosition'
        e = self.node(u.MaterialExpressionTransformPosition)
        for k, v in (('transform_source_type', 'TRANSFORMPOSSOURCE_WORLD'), ('transform_type', 'TRANSFORMPOSSOURCE_LOCAL')):
            e.set_editor_property(k, getattr(u.MaterialPositionTransformSource, v))
        self.link(self.node(u.MaterialExpressionWorldPosition), e, ['Input', ''])
        return e

    def noise(self, pos, levels=2, func='SIMPLEX_TEX'):
        e = self.node(u.MaterialExpressionNoise)
        nf = getattr(u.NoiseFunction, 'NOISEFUNCTION_' + func, None) or getattr(u.NoiseFunction, func, None)
        props = {'scale': 1.0, 'quality': 1, 'turbulence': False, 'levels': levels, 'output_min': -1.0, 'output_max': 1.0,
                 'level_scale': 2.0}
        if nf is not None:
            props['noise_function'] = nf
        else:
            self.fails.append('noise function %s missing' % func)
        for k, v in props.items():
            try:
                e.set_editor_property(k, v)
            except Exception as ex:  # noqa: BLE001
                self.fails.append('noise prop %s: %s' % (k, ex))
        self.link(pos, e, ['Position', ''])
        return e

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

    def ridge(self, n, width):
        return self.sat(self.sub(1.0, self.div(self.absf(n), width)))

    def arcs(self, pos, group='Arcs'):
        """Thin bright filaments that jump to a new layout ArcRate times a second, on a patchy part of the surface."""
        t = self.time()
        j = self.hash(self.floor(self.mul(t, self.scalar('ArcRate', 12.0, group))))
        sc = self.scalar('ArcScale', 0.08, group)
        pa = self.add(self.mul(pos, sc), self.mul(j, self.c3(137.0, 91.0, 53.0)))
        a = self.ridge(self.noise(pa, levels=3), self.scalar('ArcWidth', 0.05, group))
        a = self.mul(a, a)
        pp = self.add(self.mul(pos, self.mul(sc, 0.45)), self.mul(j, self.c3(41.0, 77.0, 19.0)))
        patch = self.sat(self.mul(self.add(self.noise(pp, levels=1), self.sub(self.scalar('ArcPatch', 0.5, group), 0.5)), 4.0))
        return self.mul(self.mul(self.mul(a, patch), self.vector('ArcColor', (1, 0.9, 0.9), group)),
                        self.scalar('ArcIntensity', 0.0, group))

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


BM = u.BlendMode
SM = u.MaterialShadingModel
MP = u.MaterialProperty


def build_item_fx2():
    it = REC.ITEMS['Medkit']
    b = MB(REC.MATS + '/M_PU_ItemFX2', BM.BLEND_OPAQUE, SM.MSM_DEFAULT_LIT)
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
    b.out(b.mul((orm, 'G'), b.scalar('RoughnessScale', 1.0, 'Look')), MP.MP_ROUGHNESS)
    b.out(b.mul((orm, 'B'), b.scalar('MetalScale', 1.0, 'Look')), MP.MP_METALLIC)
    # masks: seams from the normal map (grooves tilt the normal), emblem = the strongly saturated paint
    seam = b.sat(b.mul(b.sub(b.sub(1.0, (nrm, 'B')), b.scalar('SeamBias', 0.08, 'Masks')), b.scalar('SeamGain', 6.0, 'Masks')))
    r, g, bl = (base, 'R'), (base, 'G'), (base, 'B')
    satv = b.sub(b.maxi(b.maxi(r, g), bl), b.mini(b.mini(r, g), bl))
    emblem = b.sat(b.mul(b.sub(satv, b.scalar('EmblemBias', 0.4, 'Masks')), b.scalar('EmblemGain', 4.0, 'Masks')))
    pos = b.local_pos()
    t = b.time()
    # swirl: slow 3D noise rising through the item, modulates the inner glow
    sw_pos = b.add(b.mul(pos, b.scalar('SwirlScale', 0.07, 'Inner')),
                   b.mul(b.append(b.append(0.0, 0.0), b.mul(t, -1.0)), b.mul(b.scalar('SwirlSpeed', 6.0, 'Inner'), 0.05)))
    swirl = b.sat(b.add(0.5, b.mul(b.noise(sw_pos, levels=2), 0.9)))
    swirl = b.lerp(1.0, b.mul(swirl, 1.6), b.scalar('SwirlAmount', 0.0, 'Inner'))
    inner = b.add(b.add(b.mul(b.mul(seam, b.vector('SeamColor', (1, 0.2, 0.1), 'Inner')), b.scalar('SeamGlow', 0.0, 'Inner')),
                        b.mul(b.mul(emblem, b.vector('EmblemColor', (1, 0.1, 0.1), 'Inner')), b.scalar('EmblemGlow', 0.0, 'Inner'))),
                  b.mul(b.vector('InnerColor', (1, 0.2, 0.1), 'Inner'), b.scalar('InnerGlow', 0.0, 'Inner')))
    inner = b.mul(inner, swirl)
    # veins: ridged 3D noise crawling upward, patchy, kept off the emblem
    vs = b.scalar('VeinScale', 0.1, 'Veins')
    v_pos = b.add(b.mul(pos, vs), b.mul(b.append(b.append(0.0, 0.0), b.mul(t, -1.0)), b.mul(b.scalar('VeinPan', 0.0, 'Veins'), 0.05)))
    vein = b.ridge(b.noise(v_pos, levels=3), b.scalar('VeinWidth', 0.05, 'Veins'))
    vpatch = b.sat(b.add(b.mul(b.noise(b.mul(pos, b.mul(vs, 0.35)), levels=1), 2.0), 0.6))
    vein = b.mul(b.mul(vein, b.lerp(1.0, vpatch, b.scalar('VeinPatch', 0.0, 'Veins'))),
                 b.sub(1.0, b.mul(emblem, b.scalar('VeinEmblemCut', 0.0, 'Veins'))))
    veins = b.mul(b.mul(vein, b.vector('VeinColor', (1, 0.2, 0.1), 'Veins')), b.scalar('VeinIntensity', 0.0, 'Veins'))
    arcs = b.arcs(pos)
    fr = b.node(u.MaterialExpressionFresnel)
    b.link(b.scalar('RimExponent', 3.0, 'Rim'), fr, 'ExponentIn')
    b.link(b.val(0.04), fr, 'BaseReflectFractionIn')
    rim = b.mul(b.mul(fr, b.vector('RimColor', (1, 0.1, 0.1), 'Rim')), b.scalar('RimIntensity', 0.0, 'Rim'))
    em = b.mul(b.add(b.add(b.add(rim, inner), veins), arcs), b.flicker_and_pulse())
    b.out(em, MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_shell():
    b = MB(REC.MATS + '/M_PU_Shell', BM.BLEND_ADDITIVE, SM.MSM_UNLIT)
    pos = b.local_pos()
    t = b.time()
    up = b.append(b.append(0.0, 0.0), b.mul(t, -1.0))
    n_pos = b.add(b.mul(pos, b.scalar('NoiseScale', 0.06, 'Mist')), b.mul(up, b.mul(b.scalar('NoiseSpeed', 5.0, 'Mist'), 0.05)))
    n = b.noise(n_pos, levels=2)
    mist = b.sat(b.add(b.add(0.5, b.mul(n, b.mul(b.scalar('NoiseGain', 1.5, 'Mist'), 0.5))), b.scalar('NoiseBias', 0.0, 'Mist')))
    mist = b.lerp(1.0, mist, b.scalar('NoiseAmount', 0.0, 'Mist'))
    f = b.facing(vertex_normal=True)
    edge = b.mul(b.power(b.maxi(b.sub(1.0, f), 0.0001), b.scalar('EdgePower', 2.0, 'Shape')), b.scalar('EdgeAmount', 1.0, 'Shape'))
    core = b.mul(b.power(b.maxi(f, 0.0001), b.scalar('CorePower', 2.0, 'Shape')), b.scalar('CoreAmount', 0.0, 'Shape'))
    hz = b.mask(pos, b=True)
    hfade = b.sat(b.div(b.sub(b.scalar('HeightTop', 30.0, 'Shape'), hz), b.maxi(b.scalar('HeightSoft', 15.0, 'Shape'), 0.1)))
    hm = b.lerp(1.0, hfade, b.scalar('HeightAmount', 0.0, 'Shape'))
    glowc = b.mul(b.mul(b.mul(b.vector('Color', (1, 0.1, 0.1)), b.scalar('Intensity', 1.0)), b.add(edge, core)), mist)
    arcs = b.arcs(pos)
    arcs = b.mul(arcs, b.lerp(1.0, b.mul(b.power(b.maxi(b.sub(1.0, f), 0.0001), 1.2), 2.0), b.scalar('ArcEdge', 0.0, 'Arcs')))
    em = b.mul(b.mul(b.add(glowc, arcs), hm), b.flicker_and_pulse())
    b.out(em, MP.MP_EMISSIVE_COLOR)
    # inflate along the vertex normal, with a slow wobble so the shell breathes
    w_pos = b.add(b.mul(pos, 0.035), b.mul(up, 0.4))
    disp = b.add(b.scalar('Inflate', 2.0, 'Shape'), b.mul(b.noise(w_pos, levels=1), b.scalar('Wobble', 0.0, 'Shape')))
    b.out(b.mul(b.node(u.MaterialExpressionVertexNormalWS), disp), MP.MP_WORLD_POSITION_OFFSET)
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
    EAL.make_directory(folder)
    mi = u.load_asset(path)
    if not mi:
        mi = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    else:
        MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, parent)
    params = dict(params)
    textures = dict(params.pop('_textures', {}))
    fails = []
    names_s = set(str(x) for x in MEL.get_scalar_parameter_names(parent))
    names_v = set(str(x) for x in MEL.get_vector_parameter_names(parent))
    for k, v in params.items():
        v = REC.resolve(v, item)
        if k in ('MaskTex', 'BaseTex', 'BaseColorTex'):
            textures[k] = v
            continue
        if isinstance(v, (tuple, list)):
            if k not in names_v:
                fails.append('no vector param %s' % k)
            c = list(v) + [1.0] * (4 - len(v))
            MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(c[0], c[1], c[2], c[3]))
        else:
            if k not in names_s:
                fails.append('no scalar param %s' % k)
            MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in textures.items():
        tp = tex_token(REC.resolve(v, item), item)
        t = u.load_asset(tp)
        if not t:
            fails.append('texture %s=%s missing' % (k, tp))
            continue
        MEL.set_material_instance_texture_parameter_value(mi, k, t)
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    rb = {}
    for k, v in list(params.items())[:4]:
        if not isinstance(REC.resolve(v, item), (tuple, list)) and k not in textures:
            rb[k] = round(MEL.get_material_instance_scalar_parameter_value(mi, k), 3)
    if fails:
        err('%s: %s' % (path, fails))
    return {'path': path, 'readback': rb, 'fails': fails}


def item_textures(item):
    return {'BaseColorTex': item['tex'] + 'BaseColor', 'NormalTex': item['tex'] + 'Normal', 'ORMTex': item['tex'] + 'ORM'}


def build_mat(spec, path, item):
    kind, params = spec
    if kind == 'asset':
        return {'path': params, 'vendor': True}
    params = dict(params)
    if kind == 'ItemFX2':
        params.setdefault('_textures', {}).update(item_textures(item))
    return make_mi(path, PARENTS[kind], params, item)


def duplicate_niagara(src, dst, el, item):
    folder = dst.rsplit('/', 1)[0]
    EAL.make_directory(folder)
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


def describe(src):
    if src in R['niagara']:
        return
    a = u.load_asset(src)
    if not a:
        R['niagara'][src] = 'MISSING'
        warn('niagara missing ' + src)
        return
    try:
        d = json.loads(u.HoverAuthoring.describe_flash_asset(a))
        R['niagara'][src] = {'duration_s': d.get('duration_s'),
                             'user': [(q['name'], q.get('value')) for q in d.get('user_parameters', [])],
                             'emitters': [(e.get('name'), e.get('sim_target'), e.get('local_space'),
                                           [r.get('class') for r in e.get('renderers', [])]) for e in d.get('emitters', [])]}
    except Exception as e:  # noqa: BLE001
        R['niagara'][src] = 'describe failed: %s' % e


def build_looks():
    for look in REC2.all_looks(BENCH):
        if ONLY and look['n'] not in ONLY:
            continue
        folder = REC2.look_folder(look)
        EAL.make_directory(folder)
        L = R['looks'][look['key']] = {'n': look['n'], 'folder': folder, 'items': {}}
        for key in REC.ITEM_ORDER:
            item = REC.ITEMS[key]
            I = L['items'][key] = {'elements': []}
            if look['item'].get('material'):
                I['item_material'] = build_mat(look['item']['material'], REC2.mi_path(look, key, 'Item'), item)
            for el in look['elements']:
                e = {'kind': el['kind'], 'name': el.get('name', el['kind'])}
                if el['kind'] == 'mesh':
                    e['slots'] = {}
                    for slot, spec in el['slots'].items():
                        e['slots'][REC.slot_key(slot)] = build_mat(spec, REC2.mi_path(look, key, el['name'], slot), item)
                elif el['kind'] in ('shell', 'heads', 'pfx', 'bolts'):
                    e['material'] = build_mat(el['material'], REC2.mi_path(look, key, el['name']), item)
                elif el['kind'] == 'niagara':
                    describe(el['system'])
                    e['system'] = duplicate_niagara(el['system'], REC2.ns_path(look, key, el['name']), el, item)
                I['elements'].append(e)
        log('look', look['n'], look['key'], 'ok')


def main():
    PARENTS['ItemFX2'] = build_item_fx2()
    PARENTS['Shell'] = build_shell()
    for k in ('GlowAdditive', 'PropSimple', 'HeatHaze'):
        PARENTS[k] = u.load_asset('%s/M_PU_%s' % (REC.MATS, k))
        if not PARENTS[k]:
            err('round-1 master M_PU_%s missing' % k)
    R['probe']['noise_functions'] = [x for x in dir(u.NoiseFunction) if x.isupper()]
    build_looks()


try:
    main()
except Exception as e:  # noqa: BLE001
    err('exception %s\n%s' % (e, traceback.format_exc()))
finally:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_DIR + '/author2_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s errors=%d warnings=%d looks=%d' % (R['ok'], len(R['errors']), len(R['warnings']), len(R['looks'])))
    u.SystemLibrary.quit_editor()
