"""PowerUpStyleRecipes.py - the 14 power-up "street" looks as data (2026-10-31 style exploration).

Shared by Scripts/AuthorPowerUpStyles.py (makes the material instances / Niagara duplicates under
/Game/HoverPrototype/PowerUps/Styles/S<NN>_<Key>/) and Scripts/PreviewPowerUpStyles.py (spawns each look in
L_PowerUpShowcase and photographs it). Nothing here touches Unreal.

Coordinates of an element are in the VIEW frame of its item: x = toward the camera, y = screen right, z = up, cm,
origin = the item's ground point (the cleaned models have their pivot at bottom centre). The preview script turns
them into world space for whatever camera direction it uses, so the art direction stays "flare in front-left".
Colour tokens: '$c' = the item's power-up colour, '$c2' = its pale highlight, ('$c', k) = colour * k,
('mix', a, b, t) = lerp of two colour specs. Masters (Styles/Shared/Materials):
  M_PU_ItemFX       opaque lit, the item's own maps + rim / self-glow / veins / pulse / geiger flicker
  M_PU_GlowAdditive additive unlit: pools, halos, beams, decals, markers (radial, vertical fade, facing, noise, scanlines)
  M_PU_HoloLoFi     additive unlit hologram of the item: pixelated texture, scanlines, dropout bands, grain, WPO jitter
  M_PU_PropSimple   opaque lit prop paint with an emissive part that can flicker / pulse
  M_PU_HeatHaze     translucent refraction shell (heat shimmer)
  MM_Hologram       (copied from SpaceSurvival /Game/CyberpunkHolograms) for look 10, the scout's recipe D made dirty
"""

ROOT = '/Game/HoverPrototype/PowerUps'
STYLES = ROOT + '/Styles'
SHARED = STYLES + '/Shared'
PROPS = SHARED + '/Props'
TEX = SHARED + '/Textures'
MATS = SHARED + '/Materials'
LEVEL = '/Game/HoverPrototype/Maps/L_PowerUpShowcase'

ITEMS = {
    'Medkit': {
        'pu': 'PU_06_Medkit',
        'mesh': ROOT + '/Meshes/PU_06_Medkit/SM_PU_06_Medkit',
        'tex': ROOT + '/Meshes/PU_06_Medkit/PU_06_Medkit/Textures/T_PU_06_Medkit_',
        'c': (1.0, 0.045, 0.035), 'c2': (1.0, 0.42, 0.36), 'icon': 'Cross', 'y': -58.0, 'pulse': False,
    },
    'Nuke': {
        'pu': 'PU_17_Nuke',
        'mesh': ROOT + '/Meshes/PU_17_Nuke/SM_PU_17_Nuke',
        'tex': ROOT + '/Meshes/PU_17_Nuke/PU_17_Nuke/Textures/T_PU_17_Nuke_',
        'c': (1.0, 0.42, 0.08), 'c2': (1.0, 0.86, 0.66), 'icon': 'Trefoil', 'y': 58.0, 'pulse': True,
    },
}
ITEM_ORDER = ['Medkit', 'Nuke']

ENG_PLANE = '/Engine/BasicShapes/Plane'      # 100 x 100 cm, +Z normal, UV 0-1
ENG_SPHERE = '/Engine/BasicShapes/Sphere'    # 100 cm, centred
RUST = '/Game/PostApocalypticCity/Materials/MaterialInstance/MI_Rusted_MetalWallParts'
GRIMY = '/Game/PostApocalypticCity/Materials/MaterialInstance/MI_Generator01_2'
SMOKE = '/Game/PostApocalypticCity/Particles/NS_Smoke_01'
BLOODPOOL = '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_BloodPool'
AURA = '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_Aura_1'


def prop(name):
    return '%s/%s/SM_PU_%s' % (PROPS, name, name)


def glow(**p):
    return ('GlowAdditive', p)


def propmat(**p):
    return ('PropSimple', p)


def pool(scale, intensity, z=0.6, **extra):
    """An additive light pool on the asphalt (reads at distance even when the light itself is small)."""
    p = dict(Color='$c', Intensity=intensity, RadialAmount=1.0, RadialPower=2.4, NoiseAmount=0.45, NoiseTiling=1.6,
             FadeDistance=1.0)
    p.update(extra)
    return {'kind': 'mesh', 'name': 'Pool', 'mesh': ENG_PLANE, 'loc': (0, 0, z), 'scale': (scale, scale, 1),
            'slots': {0: glow(**p)}}


def light(loc, intensity, radius=400.0, color='$c', flicker=None, shadows=True, kind='point', rot=None, cone=None):
    return {'kind': 'light', 'type': kind, 'loc': loc, 'intensity': intensity, 'radius': radius, 'color': color,
            'flicker': flicker, 'shadows': shadows, 'rot': rot, 'cone': cone}


DARK = propmat(Color=(0.03, 0.03, 0.028), Roughness=0.55, Metallic=0.6, GrimeAmount=0.5)

LOOKS = [
    {'n': 1, 'key': 'RoadFlare', 'name': 'Road Flare',
     'look': 'A burning road flare dropped beside the item: flickering red-orange light pool, a wisp of smoke.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Flare', 'mesh': prop('FlareStick'), 'loc': (34, -14, 0), 'rot': (0, 0, 28), 'scale': (1.2, 1.2, 1.2),
          'slots': {'Body': propmat(Color=(0.32, 0.03, 0.02), Roughness=0.7, GrimeAmount=0.5),
                    'Cap': DARK,
                    'Tip': propmat(Color=(0.2, 0.05, 0.02), EmissiveColor=('mix', '$c', (1, 0.55, 0.3), 0.5), EmissiveIntensity=60,
                                   FlickerRate=17, FlickerAmount=0.45)}},
         light((46, -6, 20), 14, 520, ('mix', '$c', (1, 0.35, 0.12), 0.5), 'flare'),
         {'kind': 'niagara', 'name': 'Smoke', 'system': SMOKE, 'loc': (44, -6, 4),
          'floats': {'Alpha': 0.35, 'Lifetime': 2.6, 'Radius': 1.5, 'Size': 0.3, 'SpawnRate': 22, 'Drag': 0.6},
          'colors': {'ColorTint': ('mix', '$c', (0.6, 0.5, 0.5), 0.7)},
          'vectors': {'Velocity': (0, 0, 55), 'Wind': (18, 12, 0)}},
         dict(pool(2.4, 0.22), loc=(30, -8, 0.6)),
     ]},
    {'n': 2, 'key': 'Chemlight', 'name': 'Chemlight',
     'look': 'A snapped glowstick in the power-up colour lies at the item; soft coloured halo and a dim pool.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Stick', 'mesh': prop('Chemlight'), 'loc': (26, 12, 0), 'rot': (0, 0, -58), 'scale': (1.3, 1.3, 1.3),
          'slots': {'Tube': propmat(Color=('$c', 0.4), EmissiveColor='$c', EmissiveIntensity=28, Roughness=0.2),
                    'Cap': DARK}},
         {'kind': 'mesh', 'name': 'Halo', 'mesh': ENG_SPHERE, 'loc': (0, 0, 24), 'scale': (0.8, 0.8, 0.8),
          'slots': {0: glow(Color='$c', Intensity=0.06, FacingAmount=1.0, FacingPower=5.0, FadeDistance=25)}},
         pool(1.9, 0.28),
         light((28, 10, 8), 5, 320, '$c', None),
     ]},
    {'n': 3, 'key': 'SupplyBeacon', 'name': 'Supply Beacon',
     'look': 'A supply-drop strobe beacon flashes beside the item and a column of coloured signal smoke rises.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Beacon', 'mesh': prop('Beacon'), 'loc': (20, 30, 0), 'rot': (0, 0, 20), 'scale': (1.4, 1.4, 1.4),
          'slots': {'Body': propmat(Color=(0.06, 0.07, 0.05), Roughness=0.6, GrimeAmount=0.6),
                    'Lens': propmat(Color=(0.6, 0.6, 0.6), EmissiveColor=(1, 0.95, 0.9), EmissiveIntensity=120, Roughness=0.1)},
          'strobe': True},
         light((20, 30, 30), 5, 450, (1, 0.95, 0.9), 'strobe', shadows=True),
         {'kind': 'niagara', 'name': 'SignalSmoke', 'system': SMOKE, 'loc': (8, 20, 8),
          'floats': {'Alpha': 0.6, 'Lifetime': 7.0, 'Radius': 2, 'Size': 0.5, 'SpawnRate': 30, 'Drag': 0.2},
          'colors': {'ColorTint': ('$c', 4.0)},
          'vectors': {'Velocity': (0, 0, 60), 'Wind': (10, 5, 0)}},
         light((0, 10, 60), 4, 300, '$c', None, shadows=False),
     ]},
    {'n': 4, 'key': 'HoloProjector', 'name': 'Holo Projector',
     'look': 'A grimy projector puck on the ground throws a flickering, low-res, scanlined hologram of the item (scout recipe A, made dirty).',
     'item': {'hide': True},
     'elements': [
         {'kind': 'mesh', 'name': 'Puck', 'mesh': prop('ProjectorPuck'), 'loc': (0, 0, 0), 'rot': (0, 0, 30), 'scale': (1.1, 1.1, 1.1),
          'slots': {'Body': propmat(Color=(0.09, 0.09, 0.085), Roughness=0.65, Metallic=0.5, GrimeAmount=0.8),
                    'Trim': DARK,
                    'Lens': propmat(Color=(0.1, 0.1, 0.1), EmissiveColor='$c2', EmissiveIntensity=25, FlickerRate=11, FlickerAmount=0.3)}},
         {'kind': 'mesh', 'name': 'Cone', 'mesh': prop('ConeShaft'), 'loc': (0, 0, 7), 'scale': (0.75, 0.75, 0.30),
          'slots': {0: glow(Color='$c', Intensity=0.3, VAmount=1.0, VPower=1.3, FacingAmount=1.0, FacingPower=1.5,
                            ScanAmount=0.6, ScanSpacing=1.2, ScanSpeed=0.7, NoiseAmount=0.4, NoiseTiling=3, NoisePanV=-0.5,
                            FlickerRate=11, FlickerAmount=0.3, FadeDistance=4)}},
         {'kind': 'itemcopy', 'name': 'Holo', 'loc': (0, 0, 36), 'scale': 0.92, 'spin': 40, 'bob': (3, 0.7),
          'material': ('HoloLoFi', dict(Color=('mix', '$c', '$c2', 0.35), Intensity=1.6, BaseAmount=1.0, EdgeAmount=1.3, EdgePower=2.5,
                                        Floor=0.06, LowRes=40, ScanSpacing=1.1, ScanSpeed=0.9, ScanAmount=0.65, ScanSharp=2.0,
                                        BandSpacing=16, BandSpeed=0.35, BandWidth=0.16, BandAmount=0.85, GrainAmount=0.55,
                                        GrainTiling=4, FlickerRate=9, FlickerAmount=0.3, JitterAmount=2.0, JitterRate=6, JitterBand=8))},
         light((0, 0, 30), 3, 260, '$c', 'geiger', shadows=False),
     ]},
    {'n': 5, 'key': 'Radioactive', 'name': 'Radioactive',
     'look': 'The item glows from inside like hot salvage, flickers on a Geiger tick, shimmers with heat and sheds sparks of light.',
     'item': {'hover': 10, 'spin': 25, 'bob': (2, 0.6),
              'material': ('ItemFX', dict(Darken=0.75, SelfGlowColor='$c', SelfGlowAmount=0.9, RimColor='$c2', RimIntensity=3.5,
                                          RimExponent=2.5, FlickerRate=11, FlickerAmount=0.45))},
     'elements': [
         {'kind': 'mesh', 'name': 'Haze', 'mesh': ENG_SPHERE, 'loc': (0, 0, 48), 'scale': (0.8, 0.8, 0.9),
          'slots': {0: ('HeatHaze', dict(Strength=0.6, Tiling=1.5, Speed=0.35, Refraction=1.0))}},
         {'kind': 'mesh', 'name': 'Motes', 'mesh': prop('DustMotes'), 'loc': (0, 0, 0), 'scale': (0.7, 0.7, 0.6), 'spin': 12,
          'slots': {0: glow(Color='$c', Intensity=1.5, FlickerRate=11, FlickerAmount=0.45, FadeDistance=0)}},
         pool(1.9, 0.38, FlickerRate=11, FlickerAmount=0.45),
         light((0, 0, 25), 7, 380, '$c', 'geiger'),
     ]},
    {'n': 6, 'key': 'BloodRelic', 'name': 'Blood Relic',
     'look': 'The item darkened like a charred relic with an ember rim, a thin red mist and a blood pool under it (scout recipe B).',
     'item': {'hover': 8, 'spin': 15, 'bob': (3, 0.4),
              'material': ('ItemFX', dict(Darken=0.3, Desaturate=0.5, RimColor='$c', RimIntensity=2.5, RimExponent=3.5,
                                          PulseHz=0.9, PulseAmount=0.6))},
     'elements': [
         {'kind': 'niagara', 'name': 'Pool', 'system': BLOODPOOL, 'loc': (0, 0, 1),
          'floats': {'Size': 0.18, 'Duration': 600},
          'colors': {'Color_Min': ('$c', 0.45), 'Color_Max': ('$c', 0.02)}},
         {'kind': 'niagara', 'name': 'Aura', 'system': AURA, 'loc': (0, 0, 4),
          'floats': {'Size': 0.12, 'Duration': 600},
          'colors': {'Color_Min': ('$c', 0.45), 'Color_Max': ('$c', 0.02)}},
         light((0, 0, 22), 5, 300, '$c', 'fire'),
     ]},
    {'n': 7, 'key': 'Infected', 'name': 'Infected',
     'look': 'Bio-luminescent infection: glowing veins crawl over the darkened item and a blotchy organic glow breathes under it.',
     'item': {'hover': 0, 'spin': 0,
              'material': ('ItemFX', dict(Darken=0.5, Desaturate=0.35, VeinColor='$c2', VeinIntensity=9, VeinScale=3.0,
                                          VeinWidth=0.035, VeinPan=0.015, PulseHz=0.45, PulseAmount=0.75,
                                          RimColor='$c', RimIntensity=1.5, RimExponent=4))},
     'elements': [
         pool(1.5, 0.7, NoiseAmount=1.0, NoiseTiling=2.5, NoiseGain=2.2, PulseHz=0.45, PulseAmount=0.6),
         light((0, 0, 20), 4, 280, '$c', 'pulse'),
     ]},
    {'n': 8, 'key': 'DustShaft', 'name': 'Dust Shaft',
     'look': 'A soft shaft of dusk light falls on the item through the ruin; dust motes hang in the beam like found treasure.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Shaft', 'mesh': prop('ConeShaft'), 'loc': (0, 0, 330), 'rot': (180, 0, 0), 'scale': (0.9, 0.9, 3.3),
          'slots': {0: glow(Color=('mix', (1, 0.82, 0.6), '$c', 0.25), Intensity=0.09, VAmount=0.35, VPower=1.0,
                            FacingAmount=1.0, FacingPower=2.5, NoiseAmount=0.6, NoiseTiling=2, NoisePanV=0.04, FadeDistance=40)}},
         {'kind': 'mesh', 'name': 'Motes', 'mesh': prop('DustMotes'), 'loc': (0, 0, 0), 'scale': (0.8, 0.8, 2.0), 'spin': 4,
          'slots': {0: glow(Color=('mix', (1, 0.85, 0.65), '$c2', 0.3), Intensity=0.25, FadeDistance=0)}},
         # a spot from 3.4 m did not light the item in the r4 render (cause not found); a warm point light above does the job
         light((0, 0, 115), 30, 420, ('mix', (1, 0.8, 0.6), '$c2', 0.3), None),
     ]},
    {'n': 9, 'key': 'TaggedSalvage', 'name': 'Tagged Salvage',
     'look': 'The plain solid item with a scavenger hazard-diamond tag floating above it, like a spray stencil or a HUD ping.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Tag', 'mesh': ENG_PLANE, 'loc': (0, 0, 80), 'scale': (0.34, 0.34, 1), 'billboard': True, 'bob': (4, 0.8),
          'slots': {0: glow(Color='$c', Intensity=3.0, MaskTex='Hazard_$icon', MaskChannels=(1.0, 0.1, 0.0), FadeDistance=0,
                            PulseHz=0.8, PulseAmount=0.25)}},
     ]},
    {'n': 10, 'key': 'DirtyHoloShell', 'name': 'Dirty Holo Shell',
     'look': 'The real item sits on the ground; a dim, noisy hologram copy of it hovers just above with glitch bands (scout recipe D, made dirty).',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'itemcopy', 'name': 'Shell', 'loc': (0, 0, 52), 'scale': 0.95, 'spin': 30, 'bob': (3, 0.7),
          'material': ('Hologram', {'Base Color': '$c', 'Tint': ('$c', 0.5), 'ConstantColor': '$c', 'Emissive Intensity': 0.5,
                                    'Opacity_Int': 0.2, 'Edge Tint': '$c', 'Edge Int': 4.0, 'Edge Glow Int': 120.0,
                                    'Brigthnes': 1.0, 'Line1 Size': 450.0, 'Line1 Speed': 20.0, 'Line2 Size': 220.0, 'Line2 Speed': 12.0,
                                    'Animation Intensity': 0.35, 'Animation Weight': 0.3, 'Animation Lines': 3.0,
                                    'Refresh Line Amount': 2500.0, 'Refresh Line Speed': 0.5,
                                    '_switches': {'Hologram Animation': True, 'Animation1': True, 'Animation2': True,
                                                  'Refresh Line': True, 'Base Color Enable': False, 'BC Custom Texture': False,
                                                  'Edge Colors': True},
                                    '_textures': {'BaseColor': '$basetex'}})},
         light((0, 0, 40), 3, 260, '$c', 'geiger', shadows=False),
     ]},
    {'n': 11, 'key': 'ScrapRingPad', 'name': 'Scrap Ring Pad',
     'look': 'The store "glowing ring pad" rebuilt from rusted scrap plates with blinking hazard lamps; the item hovers and spins over it.',
     'item': {'hover': 30, 'spin': 45, 'bob': (5, 0.8)},
     'elements': [
         {'kind': 'mesh', 'name': 'Ring', 'mesh': prop('ScrapRing'), 'loc': (0, 0, 0), 'scale': (1.0, 1.0, 1.0),
          'slots': {'Metal': ('asset', RUST),
                    'Lights': propmat(Color=(0.2, 0.2, 0.2), EmissiveColor='$c', EmissiveIntensity=40, FlickerRate=2.5, FlickerAmount=0.8)}},
         pool(1.0, 0.15, z=1.0),
         light((0, 0, 25), 8, 320, '$c', None),
     ]},
    {'n': 12, 'key': 'GraffitiCircle', 'name': 'Graffiti Circle',
     'look': 'The store "magic circle" as a spray-painted ring and icon on the asphalt that glows like UV paint; the item hovers over it.',
     'item': {'hover': 18, 'spin': 45, 'bob': (4, 0.8)},
     'elements': [
         {'kind': 'mesh', 'name': 'Paint', 'mesh': ENG_PLANE, 'loc': (0, 0, 0.6), 'scale': (1.12, 1.12, 1), 'rot': (0, 0, 0),
          'slots': {0: glow(Color='$c', Intensity=0.6, MaskTex='SprayCircle_$icon', MaskChannels=(1.0, 0.0, 0.0), FadeDistance=1.0,
                            PulseHz=0.5, PulseAmount=0.2)}},
         light((0, 0, 10), 3, 260, '$c', None, shadows=False),
     ]},
    {'n': 13, 'key': 'BustedNeon', 'name': 'Busted Neon',
     'look': 'The store "glowing icon" as an old NYC storefront neon tube sign of the icon floating over the item, buzzing, one tube dead.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Sign', 'mesh': prop('Neon$icon'), 'loc': (0, 0, 92), 'scale': (1.0, 1.0, 1.0), 'billboard': 'yaw',
          'bob': (2, 0.5),
          'slots': {'Lit': propmat(Color=('$c2', 0.3), EmissiveColor=('mix', '$c', '$c2', 0.15), EmissiveIntensity=45,
                                   FlickerRate=14, FlickerAmount=0.12, Roughness=0.1),
                    'Dead': propmat(Color=(0.05, 0.05, 0.05), EmissiveColor='$c', EmissiveIntensity=0.15, Roughness=0.1),
                    'Frame': DARK}},
         light((0, 0, 85), 8, 380, '$c', 'buzz'),
     ]},
    {'n': 14, 'key': 'SearchlightPillar', 'name': 'Searchlight Pillar',
     'look': 'The store "light pillar" as a dusty emergency searchlight beside the item throwing a tinted beam straight up (scout recipe C pillar).',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Lamp', 'mesh': prop('SearchLight'), 'loc': (8, -36, 0), 'scale': (1.0, 1.0, 1.0),
          'slots': {'Body': propmat(Color=(0.12, 0.11, 0.09), Roughness=0.6, Metallic=0.4, GrimeAmount=0.7),
                    'Lens': propmat(Color=(0.8, 0.8, 0.8), EmissiveColor='$c2', EmissiveIntensity=60, Roughness=0.1)}},
         {'kind': 'mesh', 'name': 'Beam', 'mesh': prop('ConeShaft'), 'loc': (8, -36, 19), 'scale': (0.62, 0.62, 9.0),
          'slots': {0: glow(Color=('mix', '$c', '$c2', 0.25), Intensity=0.65, VAmount=1.0, VPower=0.7, FacingAmount=1.0,
                            FacingPower=1.3, NoiseAmount=0.5, NoiseTiling=3, NoisePanV=0.06, FadeDistance=20)}},
         light((14, -30, 30), 4, 300, '$c2', None),
     ]},
]


def resolve(v, item):
    """Turn colour tokens into numbers for one item."""
    if isinstance(v, str):
        if v == '$c':
            return tuple(item['c'])
        if v == '$c2':
            return tuple(item['c2'])
        return v.replace('$icon', item['icon'])
    if isinstance(v, tuple) and v and v[0] == 'mix':
        a, b, t = resolve(v[1], item), resolve(v[2], item), v[3]
        return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str):
        c = resolve(v[0], item)
        return tuple(x * v[1] for x in c)
    if isinstance(v, dict):
        return {k: resolve(x, item) for k, x in v.items()}
    return v


def look_folder(look):
    return '%s/S%02d_%s' % (STYLES, look['n'], look['key'])


def slot_key(slot):
    return 'Mat' if isinstance(slot, int) else str(slot)


def mi_path(look, item_key, elem_name, slot=None):
    """Naming convention shared by the authoring and preview scripts."""
    tail = elem_name if slot is None else '%s_%s' % (elem_name, slot_key(slot))
    name = 'MI_S%02d_%s_%s' % (look['n'], item_key, tail)
    return '%s/%s' % (look_folder(look), name)


EFFECTS = '/Game/HoverPrototype/Effects/PowerUps'


def ns_path(look, item_key, elem_name):
    # Niagara duplicates live under /Game/HoverPrototype/Effects/PowerUps/S<NN>_<Key>/: UHoverAuthoring::SetNiagaraUser*
    # only edits systems below /Game/HoverPrototype/Effects/ (a guard against touching vendor assets).
    return '%s/S%02d_%s/NS_S%02d_%s_%s' % (EFFECTS, look['n'], look['key'], look['n'], item_key, elem_name)


# Showcase framing: the camera looks along VIEW_YAW (deg); "toward the camera" is the opposite direction.
VIEW_YAW = 25.0


def view_basis():
    import math
    a = math.radians(VIEW_YAW)
    f = (math.cos(a), math.sin(a), 0.0)
    r = (-math.sin(a), math.cos(a), 0.0)
    return f, r


def view_to_world(local, anchor_y=0.0):
    """local (x toward camera, y right, z up) around an anchor anchor_y cm to the right of the showcase centre."""
    f, r = view_basis()
    x, y, z = local
    return (-f[0] * x + r[0] * (y + anchor_y), -f[1] * x + r[1] * (y + anchor_y), z)
