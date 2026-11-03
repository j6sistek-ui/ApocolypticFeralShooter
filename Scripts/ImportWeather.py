"""ImportWeather.py - put the Dreamrise weather into L_NYC_Survival (CPU, -nullrhi). Re-runnable.

Owner 2026-11-01: "put the weather in too ... ahead of anything else, because I want to see how it works"
(earlier: "Menu toggle, rain/snow"). Needs the pack copied first (Docs/WEATHER.md, "Redo the copy"):
/Game/MultiplayerDynamicWeatherSystem = M:/MultiplayerDynamicWeather/Content/MultiplayerDynamicWeatherSystem.

  "C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe" M:/UnrealProjects/AFS/AFS.uproject
      -unattended -nullrhi -nosplash -stdout -FullStdOutLogOutput -DisablePlugins=NwiroIntegrationKit
      -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/ImportWeather.py

What it does (and nothing else):
  1. (Re)builds /Game/HoverPrototype/Weather/M_WeatherSurface, the deferred-decal material AHoverWeather projects
     straight down around the camera: up-facing surfaces only (normal from screen derivatives of the world
     position), the pack's T_Perlin_Noise_M for patches. Scalar parameters Wetness (dark, glossy: wet streets) and
     SnowCover (white, rough: snow cover). Opacity 0 when both are 0, and the decal is hidden then anyway.
     Fix round 1: a radial fade with horizontal distance from the camera (FadeStart / FadeEnd, no square edge) and
     no layer where custom depth equals scene depth (characters, drawn into custom depth by AHoverWeather).
  2. Places ONE AHoverWeather actor labelled "AFS Weather" in L_NYC_Survival (moves/re-wires it if it exists),
     StartWeather Clear, driving the map's OWN sun (the atmosphere-sun directional light), sky light, height fog
     and sky atmosphere (NYC keeps them in the Lighting_Main sublevel, so they are found at runtime; the receipt
     names them). It adds no light, sky or fog actor. Saves the map.
  2b. Tuned copies of the pack's Cascade particles in the same folder: P_Rain_AFS (1800 drops/s from 12 m above the
     camera, longer streaks, collision kept), P_Rain_AFS_Far (same from 20 m, never traced, 1.25 s life), P_Snow_AFS
     (400 flakes/s over 18 x 18 m, 2.5-11 m above the camera, 2.5-6 cm flakes, traced) and P_Snow_AFS_Far (850/s
     over 32 x 32 m, 1.5-12 m up, never traced, 2.5-3.5 s life). The pack's assets stay as shipped.
  2c. Fix round 2: M_WeatherFlake, a copy of the pack's M_RadialGradient (the rain and snow sprite material) whose
     opacity fades out with the particle's distance from the camera (0 inside 1 m, full from 2 m), so flakes and drops
     passing the lens no longer draw as big soft discs; the snow copies use it, the rain copies its instance
     MI_WeatherRainDrop (fades 1.5 m -> 3.5 m: the streaks are long).
  3. Reloads the map and checks: actor count = before + (0 or 1), exactly one AHoverWeather, its references, and
     the material each particle copy draws with.
Receipt: D:/AFS_Comparisons/Weather_20261101/import_receipt.json (WEATHER_OUT overrides the folder). WEATHER_DRY=1
reports without saving.
"""
import json
import os
import traceback
from pathlib import Path

import unreal as u

MAP = '/Game/HoverPrototype/Maps/L_NYC_Survival'
FOLDER = '/Game/HoverPrototype/Weather'
MAT = FOLDER + '/M_WeatherSurface'
NOISE = '/Game/MultiplayerDynamicWeatherSystem/Textures/T_Perlin_Noise_M'
LABEL = 'AFS Weather'
OUT = Path(os.environ.get('WEATHER_OUT', 'D:/AFS_Comparisons/Weather_20261101'))
OUT.mkdir(parents=True, exist_ok=True)
DRY = os.environ.get('WEATHER_DRY') == '1'
R = {'ok': False, 'errors': [], 'material': {}, 'placement': {}, 'verify': {}, 'dry': DRY}
EA = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary


def log(*a):
    print('IMPORT_WEATHER', *a, flush=True)


def build_material():
    if EA.does_asset_exist(MAT):
        EA.delete_asset(MAT)
    mat = u.AssetToolsHelpers.get_asset_tools().create_asset('M_WeatherSurface', FOLDER, u.Material,
                                                             u.MaterialFactoryNew())
    mat.set_editor_property('material_domain', u.MaterialDomain.MD_DEFERRED_DECAL)
    mat.set_editor_property('blend_mode', u.BlendMode.BLEND_TRANSLUCENT)

    def ex(cls, x, y, **props):
        e = MEL.create_material_expression(mat, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def link(a, b, pin='', out=''):
        assert MEL.connect_material_expressions(a, out, b, pin), 'link failed %s -> %s.%s' % (a, b, pin)

    # Up-facing mask: geometric normal from the derivatives of the world position (decals have no GBuffer normal).
    wp = ex(u.MaterialExpressionWorldPosition, -1700, 0)
    dx = ex(u.MaterialExpressionDDX, -1500, -80)
    dy = ex(u.MaterialExpressionDDY, -1500, 80)
    link(wp, dx)
    link(wp, dy)
    cross = ex(u.MaterialExpressionCrossProduct, -1300, 0)
    # cross(ddx, ddy) points up on a floor seen from above (screen x = right, y = down); the first build had the
    # operands swapped, so only ceilings and undersides got wet / snowed (proof 2026-11-01 round 1).
    link(dx, cross, 'A')
    link(dy, cross, 'B')
    norm = ex(u.MaterialExpressionNormalize, -1150, 0)
    link(cross, norm)
    nz = ex(u.MaterialExpressionComponentMask, -1000, 0, r=False, g=False, b=True, a=False)
    link(norm, nz)
    up = ex(u.MaterialExpressionSmoothStep, -850, 0, const_min=0.6, const_max=0.9)
    link(nz, up, 'Value')
    # Patches: the pack's perlin noise in world XY (9 m tiles).
    xy = ex(u.MaterialExpressionComponentMask, -1500, 300, r=True, g=True, b=False, a=False)
    link(wp, xy)
    scale = ex(u.MaterialExpressionMultiply, -1300, 300, const_b=1.0 / 900.0)
    link(xy, scale, 'A')
    tex = u.load_asset(NOISE)
    smp = ex(u.MaterialExpressionTextureSample, -1100, 300)
    smp.set_editor_property('texture', tex)
    comp = tex.get_editor_property('compression_settings')
    stype = {u.TextureCompressionSettings.TC_MASKS: u.MaterialSamplerType.SAMPLERTYPE_MASKS,
             u.TextureCompressionSettings.TC_GRAYSCALE: u.MaterialSamplerType.SAMPLERTYPE_GRAYSCALE,
             u.TextureCompressionSettings.TC_ALPHA: u.MaterialSamplerType.SAMPLERTYPE_ALPHA}.get(comp)
    if stype is None:
        stype = (u.MaterialSamplerType.SAMPLERTYPE_COLOR if tex.get_editor_property('srgb')
                 else u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    smp.set_editor_property('sampler_type', stype)
    link(scale, smp, 'UVs')
    R['material']['noise'] = {'compression': str(comp), 'sampler': str(stype)}
    wet = ex(u.MaterialExpressionScalarParameter, -850, 500, parameter_name='Wetness', default_value=0.0)
    snow = ex(u.MaterialExpressionScalarParameter, -850, 650, parameter_name='SnowCover', default_value=0.0)
    # Wet: puddle-ish variation 55..95 % over the noise. Snow: drifts where the noise is high, filling in with cover.
    wvar = ex(u.MaterialExpressionLinearInterpolate, -650, 300, const_a=0.55, const_b=0.95)
    link(smp, wvar, 'Alpha', 'R')
    wm = ex(u.MaterialExpressionMultiply, -450, 350)
    link(wvar, wm, 'A')
    link(wet, wm, 'B')
    sbias = ex(u.MaterialExpressionAdd, -650, 600)
    link(smp, sbias, 'A', 'R')
    sc = ex(u.MaterialExpressionMultiply, -800, 760, const_b=0.5)
    link(snow, sc, 'A')
    link(sc, sbias, 'B')
    sstep = ex(u.MaterialExpressionSmoothStep, -450, 600, const_min=0.35, const_max=0.75)
    link(sbias, sstep, 'Value')
    sm = ex(u.MaterialExpressionMultiply, -300, 650)
    link(sstep, sm, 'A')
    link(snow, sm, 'B')
    mx = ex(u.MaterialExpressionMax, -150, 450)
    link(wm, mx, 'A')
    link(sm, mx, 'B')
    cover = ex(u.MaterialExpressionMultiply, 0, 300)
    link(mx, cover, 'A')
    link(up, cover, 'B')
    # Fix round 1 (review finding A): the 45 m box ended in a hard square edge that slid with the camera. The box is
    # now 150 m and the layer fades with horizontal distance from the camera (AHoverWeather sits the decal on the
    # camera): full to FadeStart, gone at FadeEnd (set by AHoverWeather from SurfaceFadeStart / SurfaceFadeEnd).
    cam = ex(u.MaterialExpressionCameraPositionWS, -1700, 1000)
    camxy = ex(u.MaterialExpressionComponentMask, -1500, 1000, r=True, g=True, b=False, a=False)
    link(cam, camxy)
    dist = ex(u.MaterialExpressionDistance, -1300, 1000)
    link(xy, dist, 'A')
    link(camxy, dist, 'B')
    fs = ex(u.MaterialExpressionScalarParameter, -1300, 1150, parameter_name='FadeStart', default_value=9000.0)
    fe = ex(u.MaterialExpressionScalarParameter, -1300, 1250, parameter_name='FadeEnd', default_value=14500.0)
    fstep = ex(u.MaterialExpressionSmoothStep, -1100, 1050)
    link(fs, fstep, 'Min')
    link(fe, fstep, 'Max')
    link(dist, fstep, 'Value')
    fade = ex(u.MaterialExpressionOneMinus, -950, 1050)
    link(fstep, fade)
    # Fix round 1 (finding D): characters no longer opt out of all decals; AHoverWeather draws them into custom
    # depth while the layer shows, and the layer skips pixels whose custom depth equals the scene depth (the visible
    # surface IS a character). A character behind a wall leaves the wall alone (custom depth farther than the wall).
    # |difference| rather than a sign test, so an empty / unbound custom depth (far or near) never masks the world.
    cd = ex(u.MaterialExpressionSceneTexture, -1700, 1400, scene_texture_id=u.SceneTextureId.PPI_CUSTOM_DEPTH)
    cdr = ex(u.MaterialExpressionComponentMask, -1500, 1400, r=True, g=False, b=False, a=False)
    link(cd, cdr, '', 'Color')
    pd = ex(u.MaterialExpressionPixelDepth, -1500, 1500)
    dd = ex(u.MaterialExpressionSubtract, -1300, 1400)
    link(cdr, dd, 'A')
    link(pd, dd, 'B')
    ad = ex(u.MaterialExpressionAbs, -1150, 1400)
    link(dd, ad)
    keep = ex(u.MaterialExpressionSmoothStep, -1000, 1400, const_min=4.0, const_max=16.0)
    link(ad, keep, 'Value')
    fk = ex(u.MaterialExpressionMultiply, -800, 1200)
    link(fade, fk, 'A')
    link(keep, fk, 'B')
    op = ex(u.MaterialExpressionMultiply, 150, 300)
    link(cover, op, 'A')
    link(fk, op, 'B')
    snow01 = ex(u.MaterialExpressionSaturate, -450, 800)
    link(snow, snow01)
    col = ex(u.MaterialExpressionLinearInterpolate, 0, -100)
    wcol = ex(u.MaterialExpressionConstant3Vector, -250, -200, constant=u.LinearColor(0.025, 0.025, 0.028, 1))
    scol = ex(u.MaterialExpressionConstant3Vector, -250, -50, constant=u.LinearColor(0.80, 0.82, 0.86, 1))
    link(wcol, col, 'A')
    link(scol, col, 'B')
    link(snow01, col, 'Alpha')
    rough = ex(u.MaterialExpressionLinearInterpolate, 0, 100, const_a=0.06, const_b=0.65)
    link(snow01, rough, 'Alpha')
    MEL.connect_material_property(col, '', u.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(rough, '', u.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(op, '', u.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(mat)
    EA.save_asset(MAT, only_if_is_dirty=False)
    try:
        R['material']['compile_errors'] = u.HoverAuthoring.material_compile_errors(mat)
    except Exception as e:  # noqa: BLE001
        R['material']['compile_errors'] = 'n/a: %s' % e
    R['material']['path'] = MAT
    R['material']['expressions'] = MEL.get_num_material_expressions(mat)
    log('material', json.dumps(R['material']))


# AFS-tuned copies of the pack's Cascade rain (the pack's own assets stay untouched). First proof 2026-11-01: 500
# drops/s in a 20 x 20 m column read as a few stray streaks from the third-person camera. Sub-object path ->
# {property: value}; vectors as tuples.
RAIN_SRC = '/Game/MultiplayerDynamicWeatherSystem/Particles/Rain/P_Rain'
RAIN_TUNE = {
    'ParticleModuleSpawn_0.RequiredDistributionSpawnRate': {'constant': 2200.0},
    'ParticleModuleSize_0.DistributionStartSize': {'min': (3.0, 60.0, 0.0), 'max': (5.5, 90.0, 0.0)},
}
# Round 2: the pack's snow (500/s over 40 x 40 m, 3-12.5 cm flakes) was thin from the street and its near flakes
# showed as big soft discs; denser over 30 x 30 m and smaller flakes (collision kept: no snow under roofs).
SNOW_SRC = '/Game/MultiplayerDynamicWeatherSystem/Particles/Snow/P_Snow'
# Full run: 6,000 traced flakes cost ~3x the rain, so the snow is split like the rain: a traced near volume (no snow
# under roofs where Vexa stands) and an untraced far one whose flakes simply expire around street level.
# Fix round 1 (review finding B, moving camera): the flakes all started 15 m above the camera and fall 2.5-5 m/s, so
# air the camera moved or turned into stayed empty at eye level for 3-6 s. The near (traced) flakes now start 2.5-11 m
# above the camera (above the awnings Vexa stands under; same flakes per metre of height, fewer above the view, so
# fewer traces) and the far ones anywhere from eye level to 12 m up with a 2.5-3.5 s life, so a region the far
# volume moves into fills within ~3 s at every height. AHoverWeather also leads both by the view target's velocity.
# Cost pass (finding F, 2026-11-03): with the far box moved to 10 m ahead it overlaps the near one, and the far flakes
# spawned at eye level spent most of their 3 s below the street; snow cost +2.2..3.7 ms game thread vs ~1.5 for rain.
# Near 450 -> 400/s, far 1300 -> 850/s spawned 1.5-12 m above the camera (not from eye level): ~30 % fewer live flakes.
SNOW_TUNE = {
    'ParticleModuleSpawn_0.RequiredDistributionSpawnRate': {'constant': 400.0},
    'ParticleModuleSize_0.DistributionStartSize': {'min': (2.5, 2.5, 0.0), 'max': (6.0, 6.0, 0.0)},
    'ParticleModuleLocation_0.DistributionStartLocation': {'min': (-900.0, -900.0, 250.0),
                                                           'max': (900.0, 900.0, 1100.0)},
}
SNOW_FAR_TUNE = dict(SNOW_TUNE, **{
    'ParticleModuleSpawn_0.RequiredDistributionSpawnRate': {'constant': 850.0},
    'ParticleModuleLocation_0.DistributionStartLocation': {'min': (-1600.0, -1600.0, 150.0),
                                                           'max': (1600.0, 1600.0, 1200.0)},
    'ParticleModuleCollision_0.DistributionDelayAmount': {'constant': 100.0},
    'ParticleModuleLifetime_0.DistributionLifetime': {'min': 2.5, 'max': 3.5},
})
VARIANTS = {
    # Near the camera: keeps collision (roofs, underpass, splash events). Fix round 1: drops start 12 m above the
    # camera instead of 20 m (they reach eye level in ~0.5 s after a turn; ~35 % fewer traced drops alive). Cost pass
    # (finding F): rain + storm measured ~2.0 ms game thread over Clear with the player running, so the traced drops
    # go 2200 -> 1800/s (the far, untraced curtain stays at 2200).
    'P_Rain_AFS': (RAIN_SRC, dict(RAIN_TUNE, **{
        'ParticleModuleSpawn_0.RequiredDistributionSpawnRate': {'constant': 1800.0},
        'ParticleModuleLocation_0.DistributionStartLocation': {'min': (-1000.0, -1000.0, 1200.0),
                                                               'max': (1000.0, 1000.0, 1200.0)},
    })),
    'P_Rain_AFS_Far': (RAIN_SRC, dict(RAIN_TUNE, **{   # 26 m ahead: no traces, dies just below street level
        # Cascade modules are not exposed to Python (bEnabled, MaxCollisionDistance), their distributions are: a
        # collision delay longer than the emitter's 1 s loop means the far drops are never traced.
        'ParticleModuleCollision_0.DistributionDelayAmount': {'constant': 100.0},
        'ParticleModuleLifetime_0.DistributionLifetime': {'min': 1.25, 'max': 1.25},
    })),
    'P_Snow_AFS': (SNOW_SRC, SNOW_TUNE),          # near: traced
    'P_Snow_AFS_Far': (SNOW_SRC, SNOW_FAR_TUNE),  # 10 m ahead (fix round 1): never traced, 2.5-3.5 s life
}


# Fix round 2 (2026-11-03 review, fix1 frames v05_to_snow_player_0059/0060): with the near snow 2 m ahead and spawned
# through the whole volume height, flakes pass right in front of the lens and draw as big soft white discs (up to
# ~100 px: a 6 cm flake 40 cm from the camera). Rain drops share the pack's material. M_WeatherFlake is a copy of the
# pack's M_RadialGradient (lit translucent, opacity = particle alpha x radial gradient) whose opacity also fades with
# the PARTICLE's distance from the camera (its centre, so a flake fades as a whole): 0 inside NearFadeStart (1 m),
# full from NearFadeEnd (2 m, half at 1.5 m). The sphere it empties is ~0.03 % of the near snow volume, so the
# density gained in fix round 1 stays. The pack's M_RadialGradient stays as shipped.
# Rain drops are 60-90 cm streaks: at 1-2 m they still drew as 20-25 px wide soft pillars (fix2 first pass), so the
# rain copies use MI_WeatherRainDrop, an instance of the same material fading 1.5 m -> 3.5 m (half at 2.5 m; ~4 % of
# the near rain column).
FLAKE_SRC = '/Game/MultiplayerDynamicWeatherSystem/Materials/M_RadialGradient'
FLAKE = FOLDER + '/M_WeatherFlake'
FLAKE_FADE = (100.0, 200.0)
RAIN_MI = FOLDER + '/MI_WeatherRainDrop'
RAIN_FADE = (150.0, 350.0)


def build_flake_material():
    if EA.does_asset_exist(FLAKE):
        EA.delete_asset(FLAKE)
    mat = EA.duplicate_asset(FLAKE_SRC, FLAKE)
    assert mat, 'duplicate failed ' + FLAKE
    prop = u.MaterialProperty.MP_OPACITY
    src = MEL.get_material_property_input_node(mat, prop)
    src_out = MEL.get_material_property_input_node_output_name(mat, prop)
    assert src, 'M_RadialGradient has no opacity input'

    def ex(cls, x, y, **props):
        e = MEL.create_material_expression(mat, cls, x, y)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    pos = ex(u.MaterialExpressionParticlePositionWS, -900, 600)
    cam = ex(u.MaterialExpressionCameraPositionWS, -900, 720)
    dist = ex(u.MaterialExpressionDistance, -700, 640)
    assert MEL.connect_material_expressions(pos, '', dist, 'A') and MEL.connect_material_expressions(cam, '', dist, 'B')
    near0 = ex(u.MaterialExpressionScalarParameter, -700, 780, parameter_name='NearFadeStart',
               default_value=FLAKE_FADE[0])
    near1 = ex(u.MaterialExpressionScalarParameter, -700, 880, parameter_name='NearFadeEnd',
               default_value=FLAKE_FADE[1])
    fade = ex(u.MaterialExpressionSmoothStep, -500, 700)
    assert (MEL.connect_material_expressions(near0, '', fade, 'Min') and
            MEL.connect_material_expressions(near1, '', fade, 'Max') and
            MEL.connect_material_expressions(dist, '', fade, 'Value'))
    mul = ex(u.MaterialExpressionMultiply, -250, 500)
    assert MEL.connect_material_expressions(src, src_out, mul, 'A') and MEL.connect_material_expressions(fade, '', mul, 'B')
    assert MEL.connect_material_property(mul, '', prop)
    MEL.recompile_material(mat)
    EA.save_asset(FLAKE, only_if_is_dirty=False)
    row = {'path': FLAKE, 'from': FLAKE_SRC, 'near_fade_cm': FLAKE_FADE, 'expressions': MEL.get_num_material_expressions(mat),
           'opacity_input': MEL.get_material_property_input_node(mat, prop).get_name(),
           'blend_mode': str(mat.get_editor_property('blend_mode')),
           'used_with_particle_sprites': mat.get_editor_property('used_with_particle_sprites')}
    try:
        row['compile_errors'] = u.HoverAuthoring.material_compile_errors(mat)
    except Exception as e:  # noqa: BLE001
        row['compile_errors'] = 'n/a: %s' % e
    R['material']['flake'] = row
    log('flake', json.dumps(row, default=str))
    return mat


def build_rain_instance(parent):
    if EA.does_asset_exist(RAIN_MI):
        EA.delete_asset(RAIN_MI)
    mi = u.AssetToolsHelpers.get_asset_tools().create_asset('MI_WeatherRainDrop', FOLDER, u.MaterialInstanceConstant,
                                                            u.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(mi, parent)
    MEL.set_material_instance_scalar_parameter_value(mi, 'NearFadeStart', RAIN_FADE[0])
    MEL.set_material_instance_scalar_parameter_value(mi, 'NearFadeEnd', RAIN_FADE[1])
    MEL.update_material_instance(mi)
    EA.save_asset(RAIN_MI, only_if_is_dirty=False)
    row = {'path': RAIN_MI, 'parent': mi.get_editor_property('parent').get_path_name(),
           'near_fade_cm': [MEL.get_material_instance_scalar_parameter_value(mi, n) for n in ('NearFadeStart',
                                                                                              'NearFadeEnd')]}
    assert row['near_fade_cm'] == list(RAIN_FADE), row
    R['material']['rain_drop'] = row
    log('rain_drop', json.dumps(row))
    return mi


def tuned_copies():
    out = {}
    # The copies reference M_WeatherFlake / MI_WeatherRainDrop: remove them before the materials are rebuilt.
    for name in VARIANTS:
        if EA.does_asset_exist(FOLDER + '/' + name):
            EA.delete_asset(FOLDER + '/' + name)
    if EA.does_asset_exist(RAIN_MI):
        EA.delete_asset(RAIN_MI)
    flake = build_flake_material()
    drop = build_rain_instance(flake)
    for name, (src, tune) in VARIANTS.items():
        dst = FOLDER + '/' + name
        ps = EA.duplicate_asset(src, dst)
        assert ps, 'duplicate failed ' + dst
        row = {}
        for sub, props in tune.items():
            obj = u.find_object(None, '%s.%s:%s' % (dst, name, sub))
            if not obj:
                row[sub] = 'MISSING'
                continue
            for k, v in props.items():
                if isinstance(v, tuple):
                    v = u.Vector(*v)
                obj.set_editor_property(k, v)
            row[sub] = {k: str(obj.get_editor_property(k)) for k in props}
        req = u.find_object(None, '%s.%s:ParticleModuleRequired_0' % (dst, name))
        assert req, 'no required module in ' + dst
        want = drop if name.startswith('P_Rain') else flake
        req.set_editor_property('material', want)
        row['ParticleModuleRequired_0.Material'] = req.get_editor_property('material').get_path_name()
        assert row['ParticleModuleRequired_0.Material'] == want.get_path_name(), row['ParticleModuleRequired_0.Material']
        ps.modify()
        EA.save_asset(dst, only_if_is_dirty=False)
        out[name] = row
    R['material']['rain_variants'] = out
    log('variants', json.dumps(out))


def lighting(actors):
    found = {'sun': None, 'sky': None, 'fog': None, 'air': None}
    best = -1.0
    for a in actors:
        for c in a.get_components_by_class(u.DirectionalLightComponent):
            score = c.get_editor_property('intensity') + (1000 if c.get_editor_property('atmosphere_sun_light') else 0)
            if c.get_editor_property('visible') and score > best:
                best, found['sun'] = score, a
        if found['sky'] is None and a.get_components_by_class(u.SkyLightComponent):
            found['sky'] = a
        if found['fog'] is None and a.get_components_by_class(u.ExponentialHeightFogComponent):
            found['fog'] = a
        if found['air'] is None and a.get_components_by_class(u.SkyAtmosphereComponent):
            found['air'] = a
    return found


def weathers(actors):
    return [a for a in actors if a.get_class().get_name() == 'HoverWeather']


try:
    if not DRY:
        build_material()
        tuned_copies()
    les = u.get_editor_subsystem(u.LevelEditorSubsystem)
    eas = u.get_editor_subsystem(u.EditorActorSubsystem)
    assert les.load_level(MAP), 'load failed'
    actors = eas.get_all_level_actors()
    before = len(actors)
    have = weathers(actors)
    lights = lighting(actors)
    R['placement']['before_actors'] = before
    R['placement']['existing'] = [a.get_actor_label() for a in have]
    R['placement']['level_lighting'] = {k: (v.get_actor_label() if v else None) for k, v in lights.items()}
    R['placement']['directional_lights'] = [a.get_actor_label() for a in actors
                                            if a.get_components_by_class(u.DirectionalLightComponent)]
    if len(have) > 1:
        raise RuntimeError('more than one AHoverWeather in the map: %s' % R['placement']['existing'])
    starts = [a for a in actors if a.get_class().get_name() == 'PlayerStart']
    at = starts[0].get_actor_location() + u.Vector(0, 0, 400) if starts else u.Vector(0, 0, 600)
    if not DRY:
        w = have[0] if have else eas.spawn_actor_from_class(u.HoverWeather, at, u.Rotator())
        w.set_actor_label(LABEL)
        w.set_actor_location(at, False, False)
        w.set_editor_property('start_weather', u.HoverWeatherKind.CLEAR)
        # NYC's sun / sky light / fog / atmosphere live in the PostApocalypticCity Lighting_Main sublevel; a map
        # cannot hold references into another map ("Illegal reference to private object"), so the references stay
        # empty and AHoverWeather finds the same actors at runtime (first weather change). Only a map whose lighting
        # sits in its own persistent level gets explicit references.
        persistent = u.EditorLevelLibrary.get_editor_world().get_name() if hasattr(u, 'EditorLevelLibrary') else ''
        for prop, k in (('sun_light', 'sun'), ('sky_light', 'sky'), ('height_fog', 'fog'), ('atmosphere', 'air')):
            a = lights[k]
            same = a is not None and a.get_outer().get_outer().get_name() == persistent
            w.set_editor_property(prop, a if same else None)
            R['placement'].setdefault('wired', {})[prop] = (a.get_actor_label() + (' (explicit)' if same else
                                                            ' (runtime lookup: ' + a.get_outer().get_outer().get_name()
                                                            + ')')) if a else None
        w.modify()
        assert les.save_current_level(), 'save failed'
        R['placement']['placed'] = 'moved existing' if have else 'spawned'
        # Reload-verify from disk.
        assert les.load_level('/Game/HoverPrototype/Maps/L_NYC_Explore') and les.load_level(MAP), 'reload failed'
        actors = eas.get_all_level_actors()
        ws = weathers(actors)
        R['verify'] = {'after_actors': len(actors), 'expected': before + (0 if have else 1), 'weather_actors': len(ws)}
        if ws:
            w = ws[0]
            R['verify'].update({k: (w.get_editor_property(k).get_actor_label() if w.get_editor_property(k) else None)
                                for k in ('sun_light', 'sky_light', 'height_fog', 'atmosphere')})
            R['verify']['start_weather'] = str(w.get_editor_property('start_weather'))
            R['verify']['label'] = w.get_actor_label()
        # Fix round 2: the particle copies draw with M_WeatherFlake / MI_WeatherRainDrop, the pack's
        # M_RadialGradient is left to the pack's own P_Rain / P_Snow.
        # (The registry's referencer list for the brand-new material comes back empty in the same session, so each
        # copy's required module is read back; a fresh editor process lists the copies as its users.)
        R['verify']['flake_users'] = {}
        for n in VARIANTS:
            req = u.find_object(None, '%s/%s.%s:ParticleModuleRequired_0' % (FOLDER, n, n))
            R['verify']['flake_users'][n] = req.get_editor_property('material').get_path_name() if req else None
        R['verify']['radial_gradient_users'] = sorted(str(x) for x in EA.find_package_referencers_for_asset(FLAKE_SRC,
                                                                                                          False))
        flake_ok = (all(v == (RAIN_MI + '.MI_WeatherRainDrop' if n.startswith('P_Rain') else FLAKE + '.M_WeatherFlake')
                        for n, v in R['verify']['flake_users'].items()) and
                    not any(x.startswith(FOLDER) for x in R['verify']['radial_gradient_users']))
        R['ok'] = len(actors) == R['verify']['expected'] and len(ws) == 1 and flake_ok
    else:
        R['ok'] = True
except Exception:
    R['errors'].append(traceback.format_exc())
    log('ERROR', R['errors'][-1])
(OUT / 'import_receipt.json').write_text(json.dumps(R, indent=1, default=str), encoding='utf-8')
log('DONE ok=%s' % R['ok'], json.dumps(R['verify'], default=str))
