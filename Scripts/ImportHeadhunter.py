"""ImportHeadhunter.py - the owner's Headhunter perk machine, its blood-filled tube, standing in NYC Exploration (2026-11-01).

Third machine of the perk row (Scripts/ImportPerkMachines.py did the Lifeblood and Bioreactor; this script imports its
helpers and leaves those two machines and their assets alone).

Sources
  SourceAssets/PerkMachines/Headhunter/Clean/SM_Headhunter_<Part>.glb   Scripts/Blender/ExportHeadhunter.py (shared pivot)
  SourceAssets/PerkMachines/Headhunter/Painter/Textures/Headhunter_Painter_M_Headhunter_<Set>_{BaseColor,Normal,
      OcclusionRoughnessMetallic}.png   the owner's Painter export (Unreal preset: DirectX normal, ORM = AO/rough/metal)
  SourceAssets/PerkMachines/Headhunter/Blood/T_HH_GlassBloodStatic.png, T_HH_Spatter.png
      Scripts/MakeHeadhunterBloodTextures.py

Content (/Game/HoverPrototype/PerkMachines/Headhunter/ unless noted)
  SM_Headhunter_<Part> (12 owner parts + BloodPool, GlassBlood, BloodDrop), Textures/T_Headhunter_<Set>_<Map>
  MI_Headhunter_<Set> of Shared/M_PerkMachine (MetalRoughTex = the ORM map: G roughness, B metal), the red panel button
      and the red light strip glow a little through AutoGlow; MI_Headhunter_Glass of Shared/M_PerkGlass
  Blood/M_HH_BloodPool      opaque wet blood: dark red, glossy (roughness ~0.04), deeper = darker on the side wall, a faint
                            inner glow; the surface moves by world position offset AND per-pixel normals from one height
                            function (HLSL custom node): slow ambient swell, ripple rings where drops land, a slosh + ring
                            when the headshot hits, slow dark bubbles swelling and popping. State from the actor's
                            custom primitive data (HitAge, HitAngle, two ripples).
  Blood/M_HH_GlassBlood     masked two-sided blood on the inside of the glass: the static smear / run / spatter map,
                            procedural live runs that crawl down over 9-21 s and fade / refill (two column layers, per-run
                            speed, length, width, start height), and the headshot splat (T_HH_Spatter) appearing at the
                            hit point, its thick parts running down at SpatterRunCmPerSec, fading after SpatterFadeStart s.
                            Thin blood is redder, thick darker; wet = glossy; bump normal from the thickness.
  Blood/M_HH_BloodDrop      the falling drops; Blood/M_HH_BloodSprite  Niagara droplet sprites (masked, lit, round)
  /Game/HoverPrototype/Effects/PerkMachines/NS_HH_DripSplash, NS_HH_Spurt, NS_HH_GlassSplash: engine DirectionalBurst
      copies tuned through UHoverAuthoring::ConfigurePowerUpLiveEffect (crown where a drop lands, the headshot spurt,
      droplets falling off the glass)
Placement: L_NYC_Explore, in the row with the Lifeblood and Bioreactor (same distance from the player start, next to
  them, facing the start), flat 1.2 m footprint / prop bounds / line of sight checks as ImportPerkMachines.py; StaticMesh
  actors "AFS Perk Trial Headhunter <Part>" + one AHoverBloodTube "AFS Perk Trial Headhunter TubeFX", tag
  AFS_PerkMachineTrial, folder AFS_PerkMachines, all attached to the body (box collision on the body only).
  Re-runnable: replaces only the Headhunter actors; the other machines' transforms are recorded before and after.
Receipt: D:/AFS_Comparisons/PerkMachines_20261101/Headhunter/import_receipt.json
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput
       -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ImportHeadhunter.py
       HH_PLACE=0 skips the map; HH_TEXTURES=force re-imports the Painter textures even when unchanged.
"""
import builtins
import json
import math
import os
import sys
import time
import traceback

import unreal as u

builtins.AFS_PERK_IMPORT_AS_LIBRARY = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else 'M:/UnrealProjects/AFS/Scripts')
sys.path.insert(0, 'M:/UnrealProjects/AFS/Scripts')
import ImportPerkMachines as P  # noqa: E402

SRC = 'M:/UnrealProjects/AFS/SourceAssets/PerkMachines/Headhunter'
PAINTER = SRC + '/Painter/Textures'
DEST = '/Game/HoverPrototype/PerkMachines/Headhunter'
BLOOD = DEST + '/Blood'
FX = '/Game/HoverPrototype/Effects/PerkMachines'
TEMPLATES = '/Niagara/DefaultAssets/Templates/Systems'
MAP = P.MAP
TAG, FOLDER = P.TAG, P.FOLDER
OUT = 'D:/AFS_Comparisons/PerkMachines_20261101/Headhunter'
PLACE = os.environ.get('HH_PLACE', '1') != '0'
FORCE_TEX = os.environ.get('HH_TEXTURES', '') == 'force'
LABEL = 'AFS Perk Trial Headhunter '
EAL, MEL, AT = P.EAL, P.MEL, P.AT
MP, BM, SMOD = P.MP, P.BM, P.SMOD

# part -> (kind, texture set, master parameters)
PARTS = {
    'Body': ('Machine', 'Body', {'AutoGlow': 0.9, 'AutoGlowBias': 0.55, 'PulseHz': 0.5, 'PulseAmount': 0.25}),
    'Sign': ('Machine', 'Sign', {}),
    'SelectPanel': ('Machine', 'SelectPanel', {'AutoGlow': 1.4, 'AutoGlowBias': 0.5, 'PulseHz': 0.8,
                                               'PulseAmount': 0.3}),
    'CrosshairSkull': ('Machine', 'CrosshairSkull', {}),
    'TubeRing': ('Machine', 'TubeRing', {}),
    'TubeCap': ('Machine', 'Tube', {}),
    'TubeBase': ('Machine', 'Tube', {}),
    'TubeBolts': ('Machine', 'Tube', {}),
    'TubeRod': ('Machine', 'Tube', {}),
    'Emblem': ('Machine', 'Emblem', {}),
    'EmblemBacking': ('Machine', 'EmblemBacking', {}),
    'TubeGlass': ('Glass', None, {'OpacityCenter': 0.035, 'OpacityEdge': 0.42, 'EdgeExponent': 3.0,
                                  'GlassRoughness': 0.04}),
}
HELPERS = ('BloodPool', 'GlassBlood', 'BloodDrop')
SETS = ('Body', 'CrosshairSkull', 'Emblem', 'EmblemBacking', 'SelectPanel', 'Sign', 'Tube', 'TubeRing')
MAPS = {'BaseColor': 'base', 'Normal': 'normal', 'OcclusionRoughnessMetallic': 'mr'}
R = {'ok': True, 'errors': [], 'warnings': [], 'parts': {}, 'textures': {}, 'materials': {}, 'masters': {},
     'niagara': {}, 'placed': {}, 'time': time.strftime('%Y-%m-%d %H:%M:%S')}
P.R = R   # the shared helpers log into this receipt


def log(*a):
    print('HH_IMPORT', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def warn(m):
    R['warnings'].append(m)
    log('WARN', m)


# ---------------------------------------------------------------------------------------------------------------- textures

def import_texture(src, folder, name, role):
    path = '%s/%s' % (folder, name)
    stamp_file = OUT + '/texture_stamps.json'
    stamps = json.load(open(stamp_file)) if os.path.exists(stamp_file) else {}
    key = src
    mt = '%.0f' % os.path.getmtime(src)
    if not FORCE_TEX and EAL.does_asset_exist(path) and stamps.get(key) == mt:
        t = u.load_asset(path)
        P.fix_texture(t, role, 0)   # 0 = the Painter export's full 4K (the 2048 cap blurred the sign)
        return t, False
    task = u.AssetImportTask()
    task.filename = src
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    AT.import_asset_tasks([task])
    t = u.load_asset(path)
    if not t:
        err('texture import failed %s' % src)
        return None, True
    if role == 'normal':
        try:
            t.set_editor_property('flip_green_channel', False)   # Painter Unreal preset = DirectX, as Unreal wants
        except Exception as ex:  # noqa: BLE001
            warn('flip_green %s: %s' % (name, ex))
    P.fix_texture(t, role, 0)   # 0 = the Painter export's full 4K (the 2048 cap blurred the sign)
    EAL.save_loaded_asset(t)
    stamps[key] = mt
    os.makedirs(OUT, exist_ok=True)
    json.dump(stamps, open(stamp_file, 'w'), indent=1)
    return t, True


def import_painter_textures():
    tex = {}
    for s in SETS:
        tex[s] = {}
        for suffix, role in MAPS.items():
            src = '%s/Headhunter_Painter_M_Headhunter_%s_%s.png' % (PAINTER, s, suffix)
            if not os.path.exists(src):
                err('missing Painter map ' + src)
                continue
            short = {'base': 'BaseColor', 'normal': 'Normal', 'mr': 'ORM'}[role]
            t, fresh = import_texture(src, DEST + '/Textures', 'T_Headhunter_%s_%s' % (s, short), role)
            if t:
                tex[s][role] = t
                R['textures']['%s_%s' % (s, short)] = {'asset': t.get_path_name(), 'source': src,
                                                       'source_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                                                                     time.localtime(os.path.getmtime(src))),
                                                       'reimported': fresh, 'srgb': t.get_editor_property('srgb'),
                                                       'compression': str(t.get_editor_property('compression_settings'))}
    return tex


# ---------------------------------------------------------------------------------------------------------------- blood materials

def custom(b, code, out_type, inputs, desc):
    e = b.node(u.MaterialExpressionCustom)
    e.set_editor_property('code', code)
    e.set_editor_property('description', desc)
    e.set_editor_property('output_type', getattr(u.CustomMaterialOutputType, out_type))
    ins = []
    for n, _ in inputs:
        ci = u.CustomInput()
        ci.set_editor_property('input_name', n)
        ins.append(ci)
    e.set_editor_property('inputs', ins)
    for n, src in inputs:
        b.link(b.val(src) if isinstance(src, (int, float)) else src, e, n)
    return e


def cpd(b, name, idx, default):
    return b.node(u.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(default), group='State',
                  use_custom_primitive_data=True, primitive_data_index=idx)


def vec4(b, a, bb, c, d):
    return b.append(b.append(a, bb), b.append(c, d))


def local_pos(b):
    wp = b.node(u.MaterialExpressionWorldPosition,
                world_position_shader_offset=u.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    lp = b.node(u.MaterialExpressionTransformPosition,
                transform_source_type=u.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD,
                transform_type=u.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
    b.link(wp, lp, ['Input', ''])
    return lp


def tube_rel(b, lp):
    """Local position relative to the tube axis in x, y (z stays the machine's local height, cm)."""
    c = b.append(b.append(b.scalar('CentreX', 0.23, 'Tube'), b.scalar('CentreY', -0.88, 'Tube')), 0.0)
    return b.sub(lp, c)


POOL_FN = r"""
struct HHPool {
  float H(float2 p, float t, float4 A, float4 B, float4 K, float4 K2) {
    // A = (HitAge, HitAngle, RippleA age, RippleA x)  B = (RippleA y, RippleB age, RippleB x, RippleB y)
    // K = (Radius, AmbientAmp, RippleAmp, BubbleAmp)  K2 = (SloshAmp, RippleSpeed, BubbleCell, -)
    float h = 0;
    h += sin(dot(p, float2(0.41, 0.17)) + t * 1.3) * 0.05;
    h += sin(dot(p, float2(-0.23, 0.37)) + t * 1.05 + 1.3) * 0.05;
    h += sin(dot(p, float2(0.67, -0.52)) - t * 1.9 + 2.1) * 0.025;
    h += sin(dot(p, float2(-0.9, -0.31)) + t * 2.3 + 0.4) * 0.018;
    h *= K.y;
    float rings = 0;
    for (int i = 0; i < 2; i++) {
      float age = (i == 0) ? A.z : B.y;
      float2 c = (i == 0) ? float2(A.w, B.x) : B.zw;
      float d = length(p - c);
      float x = d - age * K2.y;
      float env = exp(-age * 1.4) * exp(-x * x / (2.0 + age * 14.0)) * saturate(age * 20.0);
      rings += sin(x * 1.6) * env;
    }
    h += rings * K.z;
    float ha = max(A.x, 0.0);
    float2 dir = float2(cos(A.y), sin(A.y));
    float s = dot(p, dir) / K.x;
    float sl = s * exp(-ha * 0.9) * sin(ha * 6.5);
    float xx = (K.x - dot(p, dir)) - ha * 22.0;
    sl += 0.45 * sin(xx * 0.9) * exp(-xx * xx / 30.0) * exp(-ha * 1.2);
    h += sl * K2.x;
    float cs = K2.z;
    float2 g = p / cs;
    float2 cell = floor(g);
    float2 f = (g - cell) * cs;
    float r1 = frac(sin(dot(cell, float2(127.1, 311.7))) * 43758.5453);
    float r2 = frac(sin(dot(cell, float2(269.5, 183.3))) * 43758.5453);
    float r3 = frac(sin(dot(cell, float2(419.2, 371.9))) * 43758.5453);
    float ph = frac(t / (5.0 + r1 * 7.0) + r2);
    float k = ph / 0.3;
    float2 bc = float2(0.25 + 0.5 * r2, 0.25 + 0.5 * r3) * cs;
    float d2 = length(f - bc);
    float rb = (0.25 + 0.75 * saturate(k)) * (0.35 + 0.6 * r3);
    float bub = 0;
    if (r1 > 0.4 && k < 1.0) {
      if (k < 0.9) bub = sqrt(saturate(1.0 - d2 * d2 / (rb * rb))) * rb * 0.6;
      else { float x2 = d2 - (k - 0.9) * 25.0; bub = sin(x2 * 5.0) * exp(-x2 * x2 * 4.0) * 0.06; }
    }
    h += bub * K.w;
    return h;
  }
};
HHPool hp;
"""


def compiled(m):
    try:
        e = u.HoverAuthoring.material_compile_errors(m)
    except Exception as ex:  # noqa: BLE001
        e = 'check failed: %s' % ex
    R.setdefault('compile', {})[m.get_name()] = e or 'ok'
    if e:
        err('%s does not compile: %s' % (m.get_name(), e[:600]))
    return m


def build_pool_master():
    b = P.MB(BLOOD + '/M_HH_BloodPool', BM.BLEND_OPAQUE, SMOD.MSM_DEFAULT_LIT)
    b.m.set_editor_property('tangent_space_normal', False)
    lp = local_pos(b)
    rel = tube_rel(b, lp)
    t = b.time()
    hit_age = cpd(b, 'HitAge', 0, 100)
    A = vec4(b, hit_age, cpd(b, 'HitAngle', 1, -1.5708), cpd(b, 'RippleAAge', 2, 100), cpd(b, 'RippleAX', 3, 0))
    Bv = vec4(b, cpd(b, 'RippleAY', 4, 0), cpd(b, 'RippleBAge', 5, 100), cpd(b, 'RippleBX', 6, 0), cpd(b, 'RippleBY', 7, 0))
    K = vec4(b, b.scalar('Radius', 33.0, 'Surface'), b.scalar('AmbientAmp', 1.0, 'Surface'),
             b.scalar('RippleAmp', 0.35, 'Surface'), b.scalar('BubbleAmp', 1.0, 'Surface'))
    K2 = vec4(b, b.scalar('SloshAmp', 1.0, 'Surface'), b.scalar('RippleSpeed', 16.0, 'Surface'),
              b.scalar('BubbleCell', 6.0, 'Surface'), 0.0)
    ins = [('P', rel), ('T', t), ('A', A), ('B', Bv), ('K', K), ('K2', K2)]
    height = custom(b, POOL_FN + 'return hp.H(P.xy, T, A, B, K, K2);', 'CMOT_FLOAT1', ins, 'PoolHeight')
    nrm = custom(b, POOL_FN + """
float e = 0.12;
float hx = hp.H(P.xy + float2(e, 0), T, A, B, K, K2) - hp.H(P.xy - float2(e, 0), T, A, B, K, K2);
float hy = hp.H(P.xy + float2(0, e), T, A, B, K, K2) - hp.H(P.xy - float2(0, e), T, A, B, K, K2);
return normalize(float3(-hx / (2 * e), -hy / (2 * e), 1.0));""", 'CMOT_FLOAT3', ins, 'PoolNormal')
    # world position offset: only the surface (the top disc and the wall's top ring) moves
    top_z = b.scalar('PoolTopZ', 117.0, 'Tube')
    floor_z = b.scalar('PoolFloorZ', 98.3, 'Tube')
    lz = b.one(u.MaterialExpressionComponentMask, rel, r=False, g=False, b=True, a=False)
    wmask = b.sat(b.mul(b.sub(lz, b.sub(top_z, 1.2)), 1.25))
    b.out(b.append(b.append(0.0, 0.0), b.mul(height, wmask)), MP.MP_WORLD_POSITION_OFFSET)
    vn = b.node(u.MaterialExpressionVertexNormalWS)
    top = b.sat(b.mul(b.sub(b.one(u.MaterialExpressionComponentMask, vn, r=False, g=False, b=True, a=False), 0.5), 4.0))
    tv = b.node(u.MaterialExpressionTransform)
    tv.set_editor_property('transform_source_type', u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL)
    tv.set_editor_property('transform_type', u.MaterialVectorCoordTransform.TRANSFORM_WORLD)
    b.link(nrm, tv, ['Input', ''])
    b.out(b.lerp(vn, tv, top), MP.MP_NORMAL)
    depth = b.sat(b.bin(u.MaterialExpressionDivide, b.sub(top_z, lz), b.sub(top_z, floor_z)))
    side = b.lerp(b.vector('SideTopColor', (0.1, 0.004, 0.003), 'Look'), b.vector('SideDeepColor', (0.02, 0.0008, 0.0006), 'Look'),
                  b.power(depth, 0.6))
    rim = b.fresnel(b.scalar('RimExponent', 3.0, 'Look'))
    side = b.mul(side, b.lerp(1.0, 0.45, rim))
    b.out(b.lerp(side, b.vector('TopColor', (0.07, 0.0025, 0.002), 'Look'), top), MP.MP_BASE_COLOR)
    b.out(b.lerp(b.scalar('SideRoughness', 0.1, 'Look'), b.scalar('TopRoughness', 0.035, 'Look'), top), MP.MP_ROUGHNESS)
    b.out(b.scalar('Specular', 0.6, 'Look'), MP.MP_SPECULAR)
    b.out(b.val(0.0), MP.MP_METALLIC)
    hit_flash = b.mul(b.scalar('HitGlow', 1.5, 'Glow'),
                      b.one(u.MaterialExpressionExponential, b.mul(b.maxi(hit_age, 0.0), -3.0)))
    # side: light scattered through the blood near the surface (deep = dark); top: a faint glow under the gloss
    clots = b.noise(b.mul(b.add(rel, b.append(b.append(0.0, 0.0), b.mul(b.time(), 0.4))), 0.16), levels=3)
    mottle = b.add(0.55, b.mul(clots, 0.45))
    side_glow = b.mul(b.mul(b.mul(b.vector('SideTopColor2', (0.1, 0.0025, 0.002), 'Glow'), b.scalar('SideGlow', 0.3, 'Glow')),
                            b.power(b.sub(1.0, depth), 3.0)), mottle)
    top_glow = b.mul(b.vector('GlowColor', (1.0, 0.03, 0.012), 'Glow'), b.scalar('InnerGlow', 0.03, 'Glow'))
    glow = b.mul(b.lerp(side_glow, top_glow, top), b.add(1.0, hit_flash))
    b.out(glow, MP.MP_EMISSIVE_COLOR)
    return b.finish()


GLASS_FN = r"""
float R = K.x;
float ang = atan2(P.y, P.x);
float z = P.z;
float live = 0;
for (int L = 0; L < 2; L++) {
  float N = (L == 0) ? 41.0 : 29.0;
  float cw = 6.2831853 * R / N;
  float u = (ang + 3.14159265) / 6.2831853 * N + L * 0.37;
  float ci = floor(u);
  float fx = (frac(u) - 0.5) * cw;
  float h1 = frac(sin(ci * 12.9898 + L * 78.233) * 43758.5453);
  float h2 = frac(sin(ci * 39.3468 + L * 11.135) * 24634.6345);
  float h3 = frac(sin(ci * 73.156 + L * 52.235) * 35458.5453);
  if (h1 < K.w) {
    float period = 9.0 + h2 * 12.0;
    float ph = frac(T / period + h3);
    float zTop = (h2 < 0.15) ? K2.y - 0.8 : lerp(K2.x + 3.0, K2.y - 8.0, pow(h3, 1.7));
    float len = zTop - K2.x;
    float speed = (0.7 + h1 / max(K.w, 0.01) * 2.3) * K.z;
    float travel = min(ph * period * speed, len);
    float head = zTop - travel;
    float w = 0.08 + 0.2 * h3;
    float dx = fx - (h2 - 0.5) * cw * 0.5 - sin(z * 0.45 + h2 * 20.0) * 0.2;
    float above = z - head;
    float tw = w * lerp(1.0, 0.4, saturate(above / max(travel, 0.01)));
    float m = (above > 0.0 && z < zTop) ? saturate(1.0 - abs(dx) / tw) * 1.4 : 0.0;
    float2 bd = float2(dx, (z - head) * 0.8);
    m = max(m, saturate(1.0 - length(bd) / (w * 1.6)) * 1.6);
    m *= (1.0 - smoothstep(0.78, 1.0, ph)) * saturate(ph * period * 2.0);
    live = max(live, m);
  }
}
float spat = 0;
float ha = A.x;
if (ha >= 0.0 && ha < K2.w + 7.0) {
  float da = ang - A.y;
  da = da - 6.2831853 * floor((da + 3.14159265) / 6.2831853);
  float sx = da * R;
  float sz = z - A.z;
  float size = K.y * lerp(0.6, 1.0, saturate(ha / 0.07));
  float ca = cos(A.w * 6.2831853);
  float sa = sin(A.w * 6.2831853);
  float run = min(ha * K2.z, 16.0);
  float base = 0;
  float drip = 0;
  for (int k = 0; k <= 8; k++) {
    float off = run * k / 8.0;
    float2 q = float2(sx, -(sz + off)) / size;
    q = float2(q.x * ca - q.y * sa, q.x * sa + q.y * ca) + 0.5;
    float inside = step(0.0, q.x) * step(q.x, 1.0) * step(0.0, q.y) * step(q.y, 1.0);
    float v = Texture2DSampleLevel(Spat, SpatSampler, q, 0).r * inside;
    if (k == 0) base = v; else drip = max(drip, saturate((v - 0.5) * 2.0) * (1.0 - k / 11.0));
  }
  float streams = saturate(1.0 - abs(frac(sx / 1.1 + A.w * 7.0) - 0.5) * 3.2);
  float fade = 1.0 - smoothstep(K2.w, K2.w + 6.0, ha);
  spat = max(base, drip * streams * 1.3) * fade;
}
float sub = smoothstep(K2.x - 0.6, K2.x + 0.5, z);   // under the pool surface the glass blood is the pool itself
float th = max(St.x * StaticAmount * sub, max(live * sub, spat));
float fresh = max(saturate(live) * 0.3, saturate(spat) * saturate(1.0 - ha / 5.0));
return float4(th, fresh, St.y, spat);
"""

BUMP_FN = r"""
float2 dux = ddx(UV);
float2 duy = ddy(UV);
float hx = ddx(Th);
float hy = ddy(Th);
float det = dux.x * duy.y - dux.y * duy.x;
det = abs(det) < 1e-12 ? 1e-12 : det;
float2 g = float2(hx * duy.y - hy * dux.y, -hx * duy.x + hy * dux.x) / det;
g = g / float2(210.0, 43.7);
return normalize(float3(-g.x * Strength, g.y * Strength, 1.0));
"""


def build_glass_blood_master(static_tex, spat_tex):
    b = P.MB(BLOOD + '/M_HH_GlassBlood', BM.BLEND_MASKED, SMOD.MSM_DEFAULT_LIT, two_sided=True)
    b.m.set_editor_property('opacity_mask_clip_value', 0.35)
    lp = local_pos(b)
    rel = tube_rel(b, lp)
    uv = b.node(u.MaterialExpressionTextureCoordinate)
    st = b.tex('StaticBloodTex', static_tex, u.MaterialSamplerType.SAMPLERTYPE_MASKS, 'Blood')
    b.link(uv, st, 'UVs')
    spat = b.node(u.MaterialExpressionTextureObjectParameter, parameter_name='SpatterTex', group='Blood')
    spat.set_editor_property('texture', spat_tex)
    try:
        spat.set_editor_property('sampler_type', u.MaterialSamplerType.SAMPLERTYPE_MASKS)
    except Exception as ex:  # noqa: BLE001
        b.fails.append('spat sampler %s' % ex)
    A = vec4(b, cpd(b, 'HitAge', 0, 100), cpd(b, 'HitAngle', 1, -1.5708), cpd(b, 'HitZ', 2, 133), cpd(b, 'HitSeed', 3, 0))
    K = vec4(b, b.scalar('Radius', 33.1, 'Tube'), b.scalar('SpatterSizeCm', 30.0, 'Blood'),
             b.scalar('RunSpeed', 1.0, 'Blood'), b.scalar('LiveRunDensity', 0.3, 'Blood'))
    K2 = vec4(b, b.scalar('PoolTopZ', 117.0, 'Tube'), b.scalar('GlassTopZ', 152.0, 'Tube'),
              b.scalar('SpatterRunCmPerSec', 1.6, 'Blood'), b.scalar('SpatterFadeStart', 7.0, 'Blood'))
    g = custom(b, GLASS_FN, 'CMOT_FLOAT4',
               [('P', rel), ('T', b.time()), ('A', A), ('K', K), ('K2', K2), ('St', b.append((st, 'R'), (st, 'G'))),
                ('StaticAmount', b.scalar('StaticAmount', 1.0, 'Blood')), ('Spat', spat)], 'GlassBlood')
    thick = b.one(u.MaterialExpressionComponentMask, g, r=True, g=False, b=False, a=False)
    fresh = b.one(u.MaterialExpressionComponentMask, g, r=False, g=True, b=False, a=False)
    age = b.one(u.MaterialExpressionComponentMask, g, r=False, g=False, b=True, a=False)
    nrm = custom(b, BUMP_FN, 'CMOT_FLOAT3', [('Th', thick), ('UV', uv), ('Strength', b.scalar('BumpStrength', 0.25, 'Look'))],
                 'GlassBloodBump')
    b.out(nrm, MP.MP_NORMAL)
    k = b.sat(b.mul(b.sub(thick, 0.35), 1.8))
    col = b.lerp(b.vector('ThinColor', (0.22, 0.008, 0.006), 'Look'), b.vector('ThickColor', (0.085, 0.0035, 0.003), 'Look'), k)
    col = b.lerp(col, b.vector('FreshColor', (0.26, 0.009, 0.007), 'Look'), b.mul(fresh, 0.6))
    col = b.mul(col, b.lerp(1.0, b.scalar('OldDarken', 0.55, 'Look'), b.mul(age, b.sub(1.0, b.sat(fresh)))))
    b.out(col, MP.MP_BASE_COLOR)
    wet = b.maxi(b.sat(fresh), b.sub(1.0, b.mul(age, 0.7)))
    b.out(b.lerp(b.scalar('DryRoughness', 0.3, 'Look'), b.scalar('WetRoughness', 0.06, 'Look'), wet), MP.MP_ROUGHNESS)
    b.out(b.scalar('Specular', 0.55, 'Look'), MP.MP_SPECULAR)
    b.out(thick, MP.MP_OPACITY_MASK)
    b.out(b.mul(b.mul(col, b.scalar('TransmitGlow', 0.12, 'Glow')), b.sub(1.0, k)), MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_drop_master():
    b = P.MB(BLOOD + '/M_HH_BloodDrop', BM.BLEND_OPAQUE, SMOD.MSM_DEFAULT_LIT)
    b.out(b.vector('DropColor', (0.11, 0.004, 0.003), 'Look'), MP.MP_BASE_COLOR)
    b.out(b.scalar('Roughness', 0.04, 'Look'), MP.MP_ROUGHNESS)
    b.out(b.scalar('Specular', 0.6, 'Look'), MP.MP_SPECULAR)
    b.out(b.mul(b.vector('GlowColor', (1.0, 0.03, 0.012), 'Glow'), b.scalar('Glow', 0.02, 'Glow')), MP.MP_EMISSIVE_COLOR)
    return b.finish()


def build_sprite_master():
    b = P.MB(BLOOD + '/M_HH_BloodSprite', BM.BLEND_MASKED, SMOD.MSM_DEFAULT_LIT)
    for k in ('used_with_niagara_sprites', 'used_with_particle_sprites'):
        try:
            b.m.set_editor_property(k, True)
        except Exception as ex:  # noqa: BLE001
            b.fails.append('%s %s' % (k, ex))
    b.m.set_editor_property('opacity_mask_clip_value', 0.5)
    uv = b.node(u.MaterialExpressionTextureCoordinate)
    pc = b.node(u.MaterialExpressionParticleColor)
    sph = custom(b, """
float2 q = UV * 2.0 - 1.0;
float r2 = dot(q, q);
return float4(q.x, -q.y, sqrt(saturate(1.0 - r2)), saturate((1.0 - r2) * 6.0));""", 'CMOT_FLOAT4', [('UV', uv)], 'Droplet')
    b.out(b.one(u.MaterialExpressionComponentMask, sph, r=True, g=True, b=True, a=False), MP.MP_NORMAL)
    b.out(b.mul(b.one(u.MaterialExpressionComponentMask, sph, r=False, g=False, b=False, a=True), (pc, 'A')),
          MP.MP_OPACITY_MASK)
    # a fixed blood colour (the burst template's colour modules would otherwise tint the droplets white)
    b.out(b.vector('SpriteColor', (0.1, 0.0035, 0.003), 'Look'), MP.MP_BASE_COLOR)
    b.out(b.scalar('Roughness', 0.06, 'Look'), MP.MP_ROUGHNESS)
    b.out(b.scalar('Specular', 0.6, 'Look'), MP.MP_SPECULAR)
    return b.finish()


# ---------------------------------------------------------------------------------------------------------------- niagara

BLOOD_RGBA = '0.16,0.005,0.004,1'
NIAGARA = {
    # crown where a drop lands: a short ring of droplets thrown up and falling back
    'DripSplash': {
        'SpawnBurst_Instantaneous.Spawn Count': '11', 'AddVelocityInCone.Cone Angle': '40',
        'AddVelocityInCone.Cone Axis': '0,0,1', 'RandomRangeFloat002.Minimum': '45',
        'RandomRangeFloat002.Maximum': '105', 'InitializeParticle.Lifetime Min': '0.18',
        'InitializeParticle.Lifetime Max': '0.34', 'InitializeParticle.Sprite Size Min': '0.3,0.5',
        'InitializeParticle.Sprite Size Max': '0.5,0.9', 'ScaleSpriteSizeBySpeed.Min Scale Factor': '1,1',
        'ScaleSpriteSizeBySpeed.Max Scale Factor': '1,2.2', 'ScaleSpriteSizeBySpeed.Velocity Threshold': '150',
        'GravityForce.Gravity': '0,0,-980', 'InitializeParticle.Color': BLOOD_RGBA},
    # the headshot spurt: a fast narrow jet from the back of the skull to the back wall of the glass
    'Spurt': {
        'SpawnBurst_Instantaneous.Spawn Count': '28', 'AddVelocityInCone.Cone Angle': '10',
        'AddVelocityInCone.Cone Axis': '0,0,1', 'RandomRangeFloat002.Minimum': '250',
        'RandomRangeFloat002.Maximum': '330', 'InitializeParticle.Lifetime Min': '0.11',
        'InitializeParticle.Lifetime Max': '0.16', 'InitializeParticle.Sprite Size Min': '0.3,0.7',
        'InitializeParticle.Sprite Size Max': '0.6,1.3', 'ScaleSpriteSizeBySpeed.Min Scale Factor': '1,1',
        'ScaleSpriteSizeBySpeed.Max Scale Factor': '1,5', 'ScaleSpriteSizeBySpeed.Velocity Threshold': '300',
        'GravityForce.Gravity': '0,0,-300', 'InitializeParticle.Color': BLOOD_RGBA},
    # droplets bouncing off the glass at the hit and falling to the pool
    'GlassSplash': {
        'SpawnBurst_Instantaneous.Spawn Count': '30', 'AddVelocityInCone.Cone Angle': '55',
        'AddVelocityInCone.Cone Axis': '0,0,1', 'RandomRangeFloat002.Minimum': '25',
        'RandomRangeFloat002.Maximum': '95', 'InitializeParticle.Lifetime Min': '0.25',
        'InitializeParticle.Lifetime Max': '0.55', 'InitializeParticle.Sprite Size Min': '0.2,0.35',
        'InitializeParticle.Sprite Size Max': '0.5,0.8', 'ScaleSpriteSizeBySpeed.Min Scale Factor': '1,1',
        'ScaleSpriteSizeBySpeed.Max Scale Factor': '1,2.2', 'ScaleSpriteSizeBySpeed.Velocity Threshold': '150',
        'GravityForce.Gravity': '0,0,-980', 'InitializeParticle.Color': BLOOD_RGBA},
}


def build_niagara(sprite_mat):
    out = {}
    for name, values in NIAGARA.items():
        dst = '%s/NS_HH_%s' % (FX, name)
        ns = u.load_asset(dst) if EAL.does_asset_exist(dst) else EAL.duplicate_asset(TEMPLATES + '/DirectionalBurst', dst)
        if not ns:
            err('duplicate failed ' + dst)
            continue
        rep = u.HoverAuthoring.configure_power_up_live_effect(ns, 'DirectionalBurst', sprite_mat, True, values)
        EAL.save_loaded_asset(ns)
        lines = rep.splitlines()
        R['niagara'][name] = {'path': dst, 'set': len([x for x in lines if x.startswith('SET')]),
                              'missing': [x for x in lines if x.startswith('MISSING')],
                              'other': [x for x in lines if not x.startswith(('SET', 'MISSING', 'SYS'))]}
        if R['niagara'][name]['missing'] or rep.startswith('Refused'):
            err('niagara %s: %s' % (name, rep[:300] if rep.startswith('Refused') else R['niagara'][name]['missing']))
        out[name] = ns
    return out


# ---------------------------------------------------------------------------------------------------------------- import

def no_nanite(sm):
    try:
        ns = sm.get_editor_property('nanite_settings')
        if ns.get_editor_property('enabled'):
            ns.set_editor_property('enabled', False)
            sm.set_editor_property('nanite_settings', ns)
            EAL.save_loaded_asset(sm)
            return 'disabled'
        return 'off'
    except Exception as ex:  # noqa: BLE001
        return 'n/a %s' % ex


def import_meshes():
    meshes = {}
    for part in list(PARTS) + list(HELPERS):
        res = P.import_part('Headhunter', part)
        if res[0] is None:
            continue
        sm, _maps, rec = res
        meshes[part] = sm
        if part in ('TubeGlass',) + HELPERS:
            rec['nanite'] = no_nanite(sm)
        rec['tris_after'] = sm.get_num_triangles(0)
        rec['lods'] = sm.get_num_lods()
        try:
            rec['nanite_on'] = sm.get_editor_property('nanite_settings').get_editor_property('enabled')
        except Exception:  # noqa: BLE001
            pass
        R['parts'][part] = rec
        log(part, json.dumps({k: rec.get(k) for k in ('tris', 'min', 'max')}))
    if 'Body' in meshes:
        R['parts']['Body']['box_collision'] = P.add_box_collision(meshes['Body'])
    return meshes


def build_part_materials(tex):
    m_machine = u.load_asset(P.MATS + '/M_PerkMachine')
    m_glass = u.load_asset(P.MATS + '/M_PerkGlass')
    if not m_machine or not m_glass:
        raise RuntimeError('shared masters missing: run Scripts/ImportPerkMachines.py first')
    mats, done = {}, {}
    for part, (kind, tset, params) in PARTS.items():
        if kind == 'Glass':
            mi = P.make_mi('MI_Headhunter_Glass', DEST, m_glass, params,
                           {'GlassTint': (0.86, 0.9, 0.92)})
        else:
            if tset not in done:
                textures = {}
                for role, pname in (('base', 'BaseColorTex'), ('normal', 'NormalTex'), ('mr', 'MetalRoughTex')):
                    if role in tex.get(tset, {}):
                        textures[pname] = tex[tset][role]
                    else:
                        err('%s has no %s map' % (tset, role))
                scal = {k: v for k, v in params.items() if isinstance(v, (int, float))}
                vec = {'GlowTint': (1.0, 0.25, 0.2)} if scal.get('AutoGlow') else {}
                done[tset] = P.make_mi('MI_Headhunter_%s' % tset, DEST, m_machine, scal, vec, textures)
            mi = done[tset]
        mats[part] = mi
        R['materials'][part] = mi.get_path_name()
    return mats


# ---------------------------------------------------------------------------------------------------------------- placement

def machine_bodies():
    out = {}
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if not a.actor_has_tag(TAG):
            continue
        lab = a.get_actor_label()
        for m in ('Lifeblood', 'Bioreactor', 'Headhunter'):
            if lab.startswith('AFS Perk Trial %s ' % m):
                l, r = a.get_actor_location(), a.get_actor_rotation()
                out.setdefault(m, []).append((lab, [round(l.x, 2), round(l.y, 2), round(l.z, 2)], round(r.yaw, 2)))
    for v in out.values():
        v.sort()
    return out


def ground(w, x, y, top, bottom):
    """(lowest z, spread) of the 9-trace footprint, or (None, None) when a trace misses."""
    zs = []
    for dx in (-P.FOOT, 0.0, P.FOOT):
        for dy in (-P.FOOT, 0.0, P.FOOT):
            h = P.trace(w, u.Vector(x + dx, y + dy, top), u.Vector(x + dx, y + dy, bottom))
            if h is None:
                return None, None
            zs.append(h.z)
    return min(zs), max(zs) - min(zs)


def find_spot(w, sl, others):
    # decals are not props (their bounds are boxes of projected paint)
    boxes = [b for b in P.clutter_boxes() if 'decal' not in b[6].lower()]
    R['clutter_props_considered'] = len(boxes)
    xs = [o[0] for o in others]
    ys = [o[1] for o in others]
    row_y = sum(ys) / len(ys)
    step = abs(xs[1] - xs[0]) if len(xs) > 1 else 380.0
    cands = []   # beside either end of the row, nearest the row's own spacing and line first
    toward = 1.0 if sl.y > row_y else -1.0
    for gap in range(200, 801, 50):
        for dy in (0.0, 60.0, -60.0, 120.0, -120.0, 200.0, -200.0, 300.0):
            cost = abs(gap - step) + 1.5 * abs(dy) + (40 if dy * toward < 0 else 0)
            cands.append((cost, min(xs) - gap, row_y + dy * toward))
            cands.append((cost + 1, max(xs) + gap, row_y + dy * toward))
    cands = [(x, y) for _, x, y in sorted(cands)]
    tried = []
    for x, y in cands:
        why = None
        if min(math.hypot(x - ox, y - oy) for ox, oy in others) < 200:
            why = 'too close to another machine'
        z, spread = (None, None) if why else ground(w, x, y, sl.z + 400, sl.z - 1500)
        if not why and (z is None or spread > P.FLAT):
            why = 'not flat (%s cm)' % (round(spread, 1) if spread is not None else 'miss')
            z = None
        if not why and P.cluttered(boxes, x, y, z):
            why = 'prop on the spot: %s' % P.cluttered(boxes, x, y, z)
        if not why:
            d = math.hypot(sl.x - x, sl.y - y)
            for k in (100.0, 160.0, 220.0, 280.0):
                if k < d - 100 and P.cluttered(boxes, x + (sl.x - x) * k / d, y + (sl.y - y) * k / d, z, 35.0):
                    why = 'prop in the view line'
                    break
        if not why:
            for zz in (60.0, 110.0, 180.0):
                tgt = u.Vector(x, y, z + zz)
                h = P.trace(w, u.Vector(sl.x, sl.y, sl.z + 70), tgt)
                if h is not None and math.hypot(math.hypot(h.x - x, h.y - y), h.z - tgt.z) > 70:
                    why = 'line of sight blocked at %d cm' % zz
                    break
        tried.append({'x': round(x), 'y': round(y), 'ok': why is None, 'why': why})
        if why is None:
            R['spot_search'] = tried[-25:]
            R['spot_tries'] = len(tried)
            return x, y, z
    R['spot_search'] = tried[:60]
    raise RuntimeError('no spot for the Headhunter next to the row')


def place(meshes, mats, blood):
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert level.load_level(MAP), 'load_level failed'
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    ss = u.get_editor_subsystem(u.EditorActorSubsystem)
    before = machine_bodies()
    R['others_before'] = {k: v for k, v in before.items() if k != 'Headhunter'}
    n_actors_before = len(ss.get_all_level_actors())
    removed = 0
    for a in ss.get_all_level_actors():
        if a.actor_has_tag(TAG) and a.get_actor_label().startswith(LABEL):
            ss.destroy_actor(a)
            removed += 1
    R['removed_old_headhunter_actors'] = removed
    starts = u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart)
    assert starts, 'no PlayerStart'
    sl = starts[0].get_actor_location()
    others = []
    for m in ('Lifeblood', 'Bioreactor'):
        body = [e for e in before.get(m, []) if e[0].endswith((' Body', ' Frame'))]
        if body:
            others.append((body[0][1][0], body[0][1][1]))
    if len(others) < 2:
        raise RuntimeError('Lifeblood / Bioreactor not found in the map: %s' % before.keys())
    x, y, z = find_spot(w, sl, others)
    fb, ff = meshes['Body'].get_bounding_box(), meshes['SelectPanel'].get_bounding_box()
    front_yaw = round(math.degrees(math.atan2((ff.min.y + ff.max.y) / 2 - (fb.min.y + fb.max.y) / 2,
                                              (ff.min.x + ff.max.x) / 2 - (fb.min.x + fb.max.x) / 2)) / 90.0) * 90.0
    look = math.degrees(math.atan2(sl.y - y, sl.x - x))
    rot = u.Rotator(roll=0.0, pitch=0.0, yaw=look - front_yaw)
    loc = u.Vector(x, y, z)
    body, spawned = None, []
    for part, sm in meshes.items():
        if part in HELPERS:
            continue
        a = ss.spawn_actor_from_object(sm, loc, rot)
        a.set_actor_label(LABEL + part)
        a.tags = [u.Name(TAG)]
        a.set_folder_path(FOLDER)
        c = a.static_mesh_component
        c.set_material(0, mats[part])
        if part == 'TubeGlass':
            c.set_editor_property('translucency_sort_priority', 2)
            c.set_editor_property('cast_shadow', False)
        if part == 'Body':
            body = a
        else:
            c.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        spawned.append(a)
    fxa = ss.spawn_actor_from_class(u.HoverBloodTube, loc, rot)
    fxa.set_actor_label(LABEL + 'TubeFX')
    fxa.tags = [u.Name(TAG)]
    fxa.set_folder_path(FOLDER)
    configure_tube(fxa, meshes, blood)
    spawned.append(fxa)
    for a in spawned:
        if a is not body:
            a.attach_to_actor(body, u.Name(''), u.AttachmentRule.KEEP_WORLD, u.AttachmentRule.KEEP_WORLD,
                              u.AttachmentRule.KEEP_WORLD, False)
    R['placed'] = {'location': [round(x, 1), round(y, 1), round(z, 1)], 'yaw': round(look - front_yaw, 2),
                   'front_mesh_yaw': front_yaw, 'player_start': [round(sl.x), round(sl.y), round(sl.z)],
                   'distance_from_start_cm': round(math.hypot(sl.x - x, sl.y - y)), 'actors': len(spawned)}
    R['map_saved'] = bool(level.save_current_level())
    assert level.load_level(MAP), 'reload failed'
    after = machine_bodies()
    R['headhunter_after_reload'] = len(after.get('Headhunter', []))
    R['others_after'] = {k: v for k, v in after.items() if k != 'Headhunter'}
    R['others_unchanged'] = R['others_after'] == R['others_before']
    R['level_actor_count'] = {'before': n_actors_before,
                              'after': len(u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())}
    if R['headhunter_after_reload'] != len(PARTS) + 1:
        err('after reload %d Headhunter actors, expected %d' % (R['headhunter_after_reload'], len(PARTS) + 1))
    if not R['others_unchanged']:
        err('Lifeblood / Bioreactor actors changed')
    tube = [a for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
            if a.get_actor_label() == LABEL + 'TubeFX']
    if tube:
        t = tube[0]
        R['tube_after_reload'] = {
            'class': t.get_class().get_name(), 'parent': t.get_attach_parent_actor().get_actor_label()
            if t.get_attach_parent_actor() else None,
            'pool_mesh': str(t.pool_mesh.static_mesh.get_path_name()) if t.pool_mesh.static_mesh else None,
            'glass_mesh': str(t.glass_blood_mesh.static_mesh.get_path_name()) if t.glass_blood_mesh.static_mesh else None,
            'splash': str(t.get_editor_property('splash_system').get_path_name()) if t.get_editor_property('splash_system') else None,
            'drop_sources': len(t.get_editor_property('drop_sources'))}
    else:
        err('TubeFX actor missing after reload')


def configure_tube(t, meshes, blood):
    m = R['measure']
    cx, cy = m['ue_tube_centre_cm']
    jaw = m['crosshair_skull']['jaw_tip_ue_cm']
    rod = m['rod']['drip_tip_ue_cm']
    pool_top = m['pool']['top_ue_cm']
    cap_z = m['cap_underside']['z_m'] * 100 - 0.2
    srcs = [u.Vector(jaw[0], jaw[1], jaw[2] - 0.1), u.Vector(rod[0], rod[1], rod[2] - 0.1)]
    for deg in (62.0, 118.0, 200.0, -18.0):      # the cap's inner lip, front-left / front-right / sides (local +Y = front)
        srcs.append(u.Vector(cx + 27.5 * math.cos(math.radians(deg)), cy + 27.5 * math.sin(math.radians(deg)), cap_z))
    sk = m['crosshair_skull']['skull_only_bounds_m']
    exit_ = u.Vector(m['crosshair_skull']['skull_centre_ue_cm'][0], -sk[1][1] * 100 - 0.5,
                     m['crosshair_skull']['skull_centre_ue_cm'][2])
    props = {
        'pool_mesh_asset': meshes['BloodPool'], 'pool_material': blood['pool'],
        'glass_blood_mesh_asset': meshes['GlassBlood'], 'glass_blood_material': blood['glass'],
        'drop_mesh_asset': meshes['BloodDrop'], 'drop_material': blood['drop'],
        'splash_system': blood['ns']['DripSplash'], 'spurt_system': blood['ns']['Spurt'],
        'glass_splash_system': blood['ns']['GlassSplash'],
        'tube_centre': u.Vector2D(cx, cy), 'glass_radius': m['glass_blood_shell']['radius_ue_cm'][0],
        'pool_surface_z': pool_top, 'pool_radius': m['pool']['radius_m'][0] * 100,
        'drop_sources': srcs, 'drop_source_weights': [0.4, 0.22, 0.1, 0.1, 0.09, 0.09],
        'skull_exit': exit_, 'headshot_z_min': 128.0, 'headshot_z_max': 142.0, 'headshot_arc_min_deg': 30.0,
        'glow_intensity': 0.15, 'glow_radius': 35.0, 'hit_light_boost': 6.0,
        'fill_offset': u.Vector(cx, cy + 28.0, cap_z - 3.5), 'fill_intensity': 0.5, 'fill_radius': 70.0,
    }
    for k, v in props.items():
        try:
            t.set_editor_property(k, v)
        except Exception as ex:  # noqa: BLE001
            err('tube property %s: %s' % (k, ex))
    # (set_editor_property runs PostEditChangeProperty, which reruns OnConstruction and applies the assets)
    R['tube'] = {k: (v.get_path_name() if hasattr(v, 'get_path_name') else
                     [[round(s.x, 2), round(s.y, 2), round(s.z, 2)] for s in v] if k == 'drop_sources' else str(v))
                 for k, v in props.items()}


def main():
    clean = json.load(open(SRC + '/Clean/headhunter_clean.json', encoding='utf-8'))
    R['measure'] = clean['measure']
    meshes = import_meshes()
    tex = import_painter_textures()
    mats = build_part_materials(tex)
    static_t, _ = import_texture(SRC + '/Blood/T_HH_GlassBloodStatic.png', BLOOD, 'T_HH_GlassBloodStatic', 'mr')
    spat_t, _ = import_texture(SRC + '/Blood/T_HH_Spatter.png', BLOOD, 'T_HH_Spatter', 'mr')
    for t in (static_t, spat_t):
        t.set_editor_property('max_texture_size', 0)
        t.set_editor_property('address_x', u.TextureAddress.TA_WRAP)
        t.set_editor_property('address_y', u.TextureAddress.TA_CLAMP)
        EAL.save_loaded_asset(t)
    m = R['measure']
    pool = compiled(build_pool_master())
    glass = compiled(build_glass_blood_master(static_t, spat_t))
    drop = compiled(build_drop_master())
    sprite = compiled(build_sprite_master())
    cx, cy = m['ue_tube_centre_cm']
    tube_params = {'CentreX': cx, 'CentreY': cy, 'PoolTopZ': m['pool']['top_ue_cm']}
    mi_pool = P.make_mi('MI_HH_BloodPool', BLOOD, pool, dict(tube_params, PoolFloorZ=m['pool']['floor_z_m'] * 100,
                                                              Radius=m['pool']['radius_m'][0] * 100))
    mi_glass = P.make_mi('MI_HH_GlassBlood', BLOOD, glass, dict(tube_params, Radius=m['glass_blood_shell']['radius_ue_cm'][0],
                                                                GlassTopZ=m['glass_blood_shell']['z_m'][1] * 100))
    mi_drop = P.make_mi('MI_HH_BloodDrop', BLOOD, drop, {})
    ns = build_niagara(sprite)
    blood = {'pool': mi_pool, 'glass': mi_glass, 'drop': mi_drop, 'ns': ns}
    R['blood_materials'] = {k: v.get_path_name() for k, v in blood.items() if k != 'ns'}
    EAL.save_directory(DEST, only_if_is_dirty=True, recursive=True)
    EAL.save_directory(FX, only_if_is_dirty=True, recursive=True)
    if PLACE:
        place(meshes, mats, blood)


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
