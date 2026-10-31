"""PowerUpStyleRecipes2.py - round 2 of the power-up look exploration (2026-10-31), as data.

Owner's ruling on round 1: a power-up is the item that spawns. Nothing is added to the scene: no props, no ground
features (pools, rings, decals, graffiti, beacons, lamps, pads, tags). Every effect lives ON the item (its
material) or AROUND it (shells hugging its silhouette, particles, ribbons, a light, a glow, a light shaft from above);
the only floating object allowed is look 13's neon icon.
Kept and refined from round 1 (same numbers): 5 Radioactive, 6 Blood Relic, 7 Infected, 8 Dust Shaft, 13 Busted Neon.
New: 15-23 (23 = the owner's 5+6+13 combo).

Shared by Scripts/AuthorPowerUpStyles2.py (material instances under /Game/HoverPrototype/PowerUps/Styles/R2/S<NN>_<Key>/,
Niagara duplicates under /Game/HoverPrototype/Effects/PowerUps/R2/S<NN>_<Key>/) and Scripts/PreviewPowerUpStyles2.py.
Coordinates and colour tokens as in Scripts/PowerUpStyleRecipes.py (view frame: x toward the camera, y right, z up, cm,
origin = the item's ground point; '$c' power-up colour, '$c2' pale highlight, ('$c', k), ('mix', a, b, t)).

Masters (Styles/Shared/Materials):
  M_PU_ItemFX2  opaque lit item skin: its own maps + seam glow (from the normal map), emblem glow (the saturated
                cross / trefoil paint), 3D-noise veins and crawling arcs, swirl, rim, geiger flicker, pulse
  M_PU_Shell    additive unlit shell on a copy of the item, inflated along its normals: fresnel edge / core glow,
                3D-noise mist, arcs, height fade, wobble; the "aura" that hugs the item
  M_PU_GlowAdditive, M_PU_PropSimple, M_PU_HeatHaze  (round 1)
"""
import PowerUpStyleRecipes as REC

ITEMS = REC.ITEMS
ITEM_ORDER = REC.ITEM_ORDER
LEVEL = REC.LEVEL
VIEW_YAW = REC.VIEW_YAW
view_basis = REC.view_basis
view_to_world = REC.view_to_world
resolve = REC.resolve
slot_key = REC.slot_key
prop = REC.prop
ENG_PLANE = REC.ENG_PLANE
ENG_SPHERE = REC.ENG_SPHERE
MATS = REC.MATS

STYLES2 = REC.STYLES + '/R2'
EFFECTS2 = REC.EFFECTS + '/R2'

SICK = (0.50, 1.0, 0.06)        # radioactive yellow-green
BLOODDK = ('$c', 0.35)
WHITEHOT = (1.0, 0.92, 0.85)

TRAIL_BASIC = '/Game/ArrowTrail/FX/NS_ArrowTrail_Basic_02'
TRAIL_MAGIC = '/Game/ArrowTrail/FX/NS_ArrowTrail_Magic'
TRAIL_HOLY = '/Game/ArrowTrail/FX/NS_ArrowTrail_Holy'
SPARKS1 = '/Game/Blood_VFX_Pack/Particles/Parts/P_E_Sparks_01'
SPARKS2 = '/Game/Blood_VFX_Pack/Particles/Parts/P_E_Sparks_02'
AURA = '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_Aura_1'
SMOKY = '/Game/sA_BloodMagic_1/Fx/OptimizedEmissive/NS_SmokySphere'
LIGHTBALL = '/Game/Sci_Fi_Weapons_VFX_AIO/VFX/VFX_Ready/NS_Lighting_Ball'
ATOM = '/Game/Sci_Fi_Weapons_VFX_AIO/VFX/VFX_Ready/NS_Atom'

CENTER = 22.0   # the items are about 45 cm tall, pivot at the bottom


def glow(**p):
    return ('GlowAdditive', p)


def propmat(**p):
    return ('PropSimple', p)


def item_fx(**p):
    return ('ItemFX2', p)


def shell(name, inflate, **p):
    """An additive shell on a copy of the item, inflated `inflate` cm along its normals; follows the item."""
    q = dict(Inflate=inflate)
    q.update(p)
    return {'kind': 'shell', 'name': name, 'material': ('Shell', q)}


def light(loc, intensity, radius=300.0, color='$c', flicker=None, shadows=False, kind='point', rot=None, cone=None,
          volumetric=None):
    return {'kind': 'light', 'type': kind, 'loc': loc, 'intensity': intensity, 'radius': radius, 'color': color,
            'flicker': flicker, 'shadows': shadows, 'rot': rot, 'cone': cone, 'volumetric': volumetric}


def trail(name, system, orbit, color='$c', emissive=6.0, size=0.6, lifetime=0.6, extra=None):
    """A ribbon (ArrowTrail) carried around the item on a path: orbit = radius, z0, z amplitude, turns/s, z Hz, phase."""
    floats = {'Emissive': emissive, 'Trail Size': size, 'Lifetime': lifetime}
    floats.update(extra or {})
    colors = {'Color': color}
    if 'Magic' in system:
        colors = {'ColorA': color, 'ColorB': '$c2'}
    return {'kind': 'niagara', 'name': name, 'system': system, 'loc': (0, 0, CENTER), 'orbit': orbit,
            'floats': floats, 'colors': colors}


def sparks(name, color, rate=15, size=1.0, velocity=1.0, boost=50, z=CENTER, system=SPARKS1):
    return {'kind': 'niagara', 'name': name, 'system': system, 'loc': (0, 0, z), 'attach': True,
            'floats': {'SparksSpawnRate': rate, 'SparksSize': size, 'SparksVelocity': velocity, 'SparksColorBoost': boost},
            'colors': {'SparksColor': color}}


def pfx(name, color, intensity, count, **kw):
    """Harness particles (stretched glowing spheres) spawned on the item's surface; stand-ins for a Niagara sprite
    emitter (speed cm/s, life s, width cm, streak = length per cm/s, gravity cm/s2, up = upward bias)."""
    d = {'kind': 'pfx', 'name': name, 'count': count,
         'material': glow(Color=color, Intensity=intensity, FacingAmount=1.0, FacingPower=1.6, FadeDistance=0)}
    d.update(kw)
    return d


def bolts(name, color, intensity, count=3, **kw):
    d = {'kind': 'bolts', 'name': name, 'count': count,
         'material': glow(Color=color, Intensity=intensity, FacingAmount=1.0, FacingPower=1.2, FadeDistance=0)}
    d.update(kw)
    return d


# '$cd' = a deeper, more saturated version of the type colour (neon tubes, so orange stays orange in the tonemapper)
ITEMS['Medkit'].setdefault('cd', (1.0, 0.02, 0.02))
ITEMS['Nuke'].setdefault('cd', (1.0, 0.24, 0.012))
_resolve_r1 = REC.resolve


def _resolve(v, item):
    if v == '$cd':
        return tuple(item['cd'])
    if isinstance(v, tuple) and v and v[0] == 'mix':
        return _resolve_r1(('mix', _resolve(v[1], item), _resolve(v[2], item), v[3]), item)
    if isinstance(v, tuple) and len(v) == 2 and v[0] == '$cd':
        return tuple(x * v[1] for x in item['cd'])
    return _resolve_r1(v, item)


if getattr(REC.resolve, '__name__', '') != '_resolve':
    REC.resolve = _resolve
resolve = _resolve

MOTES = prop('DustMotes')
DARK = propmat(Color=(0.025, 0.025, 0.024), Roughness=0.55, Metallic=0.6, GrimeAmount=0.5)
EMBER = (1.0, 0.33, 0.04)
FRONT = (24, 0, 34)
KEYW = (1.0, 0.9, 0.8)
KEY = ('mix', '$c', KEYW, 0.55)   # a warm key tinted with the type colour: keeps the real texture readable     # item lights sit in front of the item (toward the camera), not inside it: inside, they
                        # lit only the ground and left the item dark (round 1's dark items)

# the round-2 item skins share one recipe each so the combo (23) reuses them
RADIO_SKIN = dict(Darken=1.0, Tint=(0.95, 1.0, 0.88), SeamColor=SICK, SeamGlow=3.5, EmblemColor='$c', EmblemGlow=2.2,
                  SwirlAmount=0.5, SwirlScale=0.06, SwirlSpeed=6.0, FlickerRate=11, FlickerAmount=0.5)
BLOOD_SKIN = dict(Darken=0.85, Desaturate=0.2, Tint=(1.0, 0.86, 0.84), EmblemColor='$c', EmblemGlow=2.2,
                  RimColor='$c', RimIntensity=1.6, RimExponent=3.5, PulseHz=0.9, PulseAmount=0.45)
BLOOD_MIST = dict(Color='$c', Intensity=0.9, EdgeAmount=1.0, EdgePower=2.2, NoiseAmount=1.0, NoiseScale=0.07,
                  NoiseSpeed=9.0, NoiseGain=1.6, NoiseBias=-0.15, Wobble=1.5, PulseHz=0.9, PulseAmount=0.35)
NEON = {'Lit': propmat(Color=('$cd', 0.25), EmissiveColor='$cd', EmissiveIntensity=12, FlickerRate=14, FlickerAmount=0.1,
                       Roughness=0.1),
        'Dead': propmat(Color=(0.05, 0.05, 0.05), EmissiveColor='$cd', EmissiveIntensity=7, FlickerRate=7, FlickerAmount=0.95,
                        Roughness=0.1),
        'Frame': DARK}

LOOKS = [
    # ---------------------------------------------------------------- kept and refined
    {'n': 5, 'key': 'Radioactive', 'name': 'Radioactive', 'r1': True,
     'look': 'Hot irradiated salvage: the real texture, a sickly yellow-green glow leaking from the seams, the emblem lit '
             'in the type colour, a Geiger-tick flicker and drifting specks. No ground ring.',
     'item': {'hover': 10, 'spin': 25, 'bob': (2, 0.6), 'material': item_fx(**RADIO_SKIN)},
     'elements': [
         shell('Glow', 1.2, Color=SICK, Intensity=0.2, EdgeAmount=1.0, EdgePower=3.5, NoiseAmount=0.8, NoiseScale=0.09,
               NoiseSpeed=12, FlickerRate=11, FlickerAmount=0.5),
         {'kind': 'mesh', 'name': 'Motes', 'mesh': MOTES, 'loc': (0, 0, 4), 'scale': (0.55, 0.55, 0.55), 'spin': 14,
          'slots': {0: glow(Color=('mix', SICK, '$c', 0.35), Intensity=1.6, FlickerRate=11, FlickerAmount=0.5, FadeDistance=0)}},
         light(FRONT, 1.8, 220, ('mix', SICK, KEYW, 0.5), 'geiger'),
     ]},
    {'n': 6, 'key': 'BloodRelic', 'name': 'Blood Relic', 'r1': True,
     'look': 'A cursed relic: the item stays readable (cross lit), a red ember rim breathes and a thin red mist clings '
             'to its silhouette. No splats, no pool.',
     'item': {'hover': 8, 'spin': 15, 'bob': (3, 0.4), 'material': item_fx(**BLOOD_SKIN)},
     'elements': [
         shell('Mist', 1.5, **BLOOD_MIST),
         shell('MistOuter', 5.0, **dict(BLOOD_MIST, Intensity=0.25, NoiseScale=0.05, EdgePower=1.6, Wobble=3.0)),
         light(FRONT, 3, 220, KEY, 'fire'),
     ]},
    {'n': 7, 'key': 'Infected', 'name': 'Infected', 'r1': True,
     'look': 'Infection under the skin: veins in the type colour crawl over the item and breathe slowly; the emblem '
             'stays clear and readable.',
     'item': {'hover': 0, 'spin': 0,
              'material': item_fx(Darken=0.85, Desaturate=0.2, VeinColor='$c', VeinIntensity=12.0, VeinScale=0.08,
                                  VeinWidth=0.06, VeinPan=1.2, VeinEmblemCut=1.0, VeinPatch=0.85, EmblemColor='$c',
                                  EmblemGlow=0.6, RimColor='$c', RimIntensity=0.4, RimExponent=4,
                                  PulseHz=0.35, PulseAmount=0.75)},
     'elements': [
         light(FRONT, 2.2, 220, KEY, 'pulse'),
     ]},
    {'n': 8, 'key': 'DustShaft', 'name': 'Dust Shaft', 'r1': True,
     'look': 'A tight tinted shaft of light from above falls on the item through the dust; coloured motes hang in it.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         light((0, 0, 340), 200, 520, ('mix', (1, 0.8, 0.6), '$c', 0.6), None, shadows=True, kind='spot',
               rot=(0, -90, 0), cone=(5, 9), volumetric=8.0),
         {'kind': 'mesh', 'name': 'Shaft', 'mesh': prop('ConeShaft'), 'loc': (0, 0, 330), 'rot': (180, 0, 0),
          'scale': (0.45, 0.45, 3.3),
          'slots': {0: glow(Color=('mix', (1, 0.8, 0.6), '$c', 0.6), Intensity=0.25, VAmount=0.8, VPower=0.6,
                            FacingAmount=1.0, FacingPower=2.0, NoiseAmount=0.6, NoiseTiling=2, NoisePanV=0.04, FadeDistance=40)}},
         {'kind': 'mesh', 'name': 'Motes', 'mesh': MOTES, 'loc': (0, 0, 8), 'scale': (0.38, 0.38, 0.9), 'spin': 4,
          'slots': {0: glow(Color=('mix', '$c', '$c2', 0.3), Intensity=1.0, FadeDistance=0)}},
     ]},
    {'n': 13, 'key': 'BustedNeon', 'name': 'Busted Neon', 'r1': True,
     'look': 'An old storefront neon of the icon hangs over the item in the type colour, buzzing; one tube is dying '
             'and stutters. Thin dark bracket only; the sign casts no shadow.',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         {'kind': 'mesh', 'name': 'Sign', 'mesh': prop('Neon$icon'), 'loc': (0, 0, 92), 'scale': (1.0, 1.0, 1.0),
          'billboard': 'yaw', 'bob': (2, 0.5), 'shadow': False, 'slots': NEON},
         light((0, 6, 80), 5, 340, '$cd', 'buzz', shadows=False),
     ]},
    # ---------------------------------------------------------------- new
    {'n': 15, 'key': 'EnergySwirl', 'name': 'Energy Swirl',
     'look': 'Three glowing tendrils spiral up and down around the item in the type colour (the toxic-bottle board); '
             'the item keeps its real texture with a hot rim.',
     'item': {'hover': 6, 'spin': 0, 'material': item_fx(EmblemColor='$c', EmblemGlow=1.2, RimColor='$c', RimIntensity=0.8,
                                                         RimExponent=3.5)},
     'elements': [
         trail('Swirl1', TRAIL_BASIC, (21, 30, 24, 0.7, 0.45, 0.0), emissive=16, size=2.4, lifetime=1.0, extra={'Length': 3.0}),
         trail('Swirl2', TRAIL_BASIC, (25, 30, 26, 0.7, 0.45, 0.333), emissive=16, size=2.4, lifetime=1.0, extra={'Length': 3.0}),
         trail('Swirl3', TRAIL_BASIC, (18, 30, 22, 0.7, 0.45, 0.667), emissive=16, size=2.4, lifetime=1.0, extra={'Length': 3.0}),
         light(FRONT, 3, 220, KEY, 'pulse'),
     ]},
    {'n': 16, 'key': 'ArcCrawl', 'name': 'Arc Crawl',
     'look': 'Electric arcs crawl over the item, jump off its edges and spit sparks; the light stutters with every '
             'discharge (the Static Surprise board).',
     'item': {'hover': 0, 'spin': 0,
              'material': item_fx(Darken=0.9, ArcColor=('mix', '$c', WHITEHOT, 0.35), ArcIntensity=22.0, ArcScale=0.08,
                                  ArcWidth=0.07, ArcRate=14, ArcPatch=0.55, EmblemColor='$c', EmblemGlow=0.6)},
     'elements': [
         shell('Arcs', 3.0, Color='$c', Intensity=0.0, ArcColor=('mix', '$c', WHITEHOT, 0.5), ArcIntensity=14.0,
               ArcScale=0.05, ArcWidth=0.06, ArcRate=11, ArcPatch=0.45, ArcEdge=1.0),
         bolts('Bolts', ('mix', '$c', WHITEHOT, 0.4), 40, count=3, segments=5, rate=13, width=0.6, reach=7, radius=14),
         pfx('Sparks', ('mix', '$c', WHITEHOT, 0.5), 30, 14, speed=(120, 260), up=0.8, gravity=-500, life=(0.25, 0.5),
             width=0.7, streak=0.025, radius=14),
         light(FRONT, 4, 240, ('mix', '$c', WHITEHOT, 0.3), 'arc'),
     ]},
    {'n': 17, 'key': 'SoulWisps', 'name': 'Soul Wisps',
     'look': 'Four pale ghost wisps tinted with the type colour circle the item at different heights, trailing faint '
             'tails; the item has a cold ghostly rim (fits the Necrosiphon perk\'s souls).',
     'item': {'hover': 6, 'spin': 0, 'material': item_fx(RimColor=('mix', '$c2', (0.8, 0.9, 1.0), 0.4), RimIntensity=1.0,
                                                         RimExponent=3.0, EmblemColor='$c', EmblemGlow=0.8)},
     'elements': [
         trail('Wisp1', TRAIL_BASIC, (30, 40, 10, 0.32, 0.7, 0.0), color=('mix', '$c2', '$c', 0.55), emissive=25, size=2.0,
               lifetime=1.2, extra={'Length': 3.0}),
         trail('Wisp2', TRAIL_BASIC, (36, 20, 8, -0.27, 0.55, 0.25), color=('mix', '$c2', '$c', 0.55), emissive=25, size=2.0,
               lifetime=1.2, extra={'Length': 3.0}),
         trail('Wisp3', TRAIL_BASIC, (26, 58, 9, 0.38, 0.8, 0.5), color=('mix', '$c2', '$c', 0.55), emissive=25, size=2.0,
               lifetime=1.2, extra={'Length': 3.0}),
         trail('Wisp4', TRAIL_BASIC, (40, 32, 12, -0.22, 0.6, 0.75), color=('mix', '$c2', '$c', 0.55), emissive=25, size=2.0,
               lifetime=1.2, extra={'Length': 3.0}),
         {'kind': 'heads', 'name': 'Heads', 'of': ['Wisp1', 'Wisp2', 'Wisp3', 'Wisp4'], 'size': 0.14,
          'material': glow(Color=('mix', '$c2', '$c', 0.5), Intensity=9.0, RadialAmount=1.0, RadialPower=3.0, FadeDistance=0)},
         light(FRONT, 2.5, 240, ('mix', '$c2', (0.7, 0.85, 1.0), 0.3), 'pulse'),
     ]},
    {'n': 18, 'key': 'EmberCorona', 'name': 'Ember Corona',
     'look': 'The item runs hot: seams glow like a stove, embers drift up off it and sparks spit out, under a '
             'fire-flicker light (the Rusty Revitalizer board).',
     'item': {'hover': 0, 'spin': 0,
              'material': item_fx(Darken=0.8, Tint=(1.0, 0.9, 0.85), SeamColor=('mix', '$c', EMBER, 0.5),
                                  SeamGlow=6.0, EmblemColor='$c', EmblemGlow=1.2, SwirlAmount=0.6, SwirlScale=0.08,
                                  SwirlSpeed=10, RimColor=('mix', '$c', EMBER, 0.5), RimIntensity=0.9,
                                  RimExponent=3.0, FlickerRate=9, FlickerAmount=0.25)},
     'elements': [
         pfx('Embers', ('mix', '$c', EMBER, 0.5), 40, 40, speed=(20, 50), up=2.0, gravity=40, drag=0.5, life=(1.0, 2.0),
             width=1.5, streak=0.01, wobble=300, twinkle=True, radius=12),
         pfx('Spit', ('mix', '$c', (1.0, 0.6, 0.2), 0.4), 35, 12, speed=(150, 300), up=0.8, gravity=-600, life=(0.3, 0.6),
             width=0.6, streak=0.03, radius=13),
         light(FRONT, 3.5, 240, ('mix', ('mix', '$c', EMBER, 0.5), KEYW, 0.35), 'fire'),
     ]},
    {'n': 19, 'key': 'InnerGlow', 'name': 'Inner Glow Vessel',
     'look': 'The item is a vessel of light: its shell darkens and a swirling glow shines out through every seam and the '
             'emblem, as if something alive is inside (the Zombie Buddy Vial board).',
     'item': {'hover': 6, 'spin': 0,
              'material': item_fx(Darken=0.45, SeamColor='$c', SeamGlow=20.0, EmblemColor='$cd', EmblemGlow=2.5,
                                  SwirlAmount=1.0, SwirlScale=0.07, SwirlSpeed=8.0, InnerGlow=0.0,
                                  InnerColor='$c', PulseHz=0.5, PulseAmount=0.3)},
     'elements': [
         shell('Inner', 0.6, Color='$c', Intensity=0.06, EdgeAmount=0.0, CoreAmount=1.0, CorePower=2.0, NoiseAmount=1.0,
               NoiseScale=0.08, NoiseSpeed=8, NoiseGain=2.5, NoiseBias=-0.6, PulseHz=0.5, PulseAmount=0.3),
         light((0, 0, 22), 2.0, 200, '$c', 'pulse'),
         light(FRONT, 0.6, 200, KEY, None),
     ]},
    {'n': 20, 'key': 'Heartbeat', 'name': 'Heartbeat Pulse',
     'look': 'The item thumps like a heart (lub-dub): it swells, flashes, jitters and throws an echo of its own '
             'silhouette outward with each beat, plus streaks (Caffeine Overdrive).',
     'item': {'hover': 4, 'spin': 0, 'pulse': True, 'double_beat': True, 'jitter': 0.8,
              'material': item_fx(EmblemColor='$c', EmblemGlow=1.5, SeamColor='$c', SeamGlow=2.0, RimColor='$c',
                                  RimIntensity=1.0, RimExponent=3.0)},
     'elements': [
         dict(shell('Echo', 1.5, Color='$c', Intensity=1.0, EdgeAmount=1.0, EdgePower=1.6), echo=True),
         pfx('Streaks', ('mix', '$c', WHITEHOT, 0.3), 30, 24, gate='beat', speed=(300, 500), up=0.2, life=(0.12, 0.25),
             width=0.8, streak=0.04, maxlen=18, radius=14),
         dict(light(FRONT, 3, 240, KEY, None), pulse=True),
     ]},
    {'n': 21, 'key': 'ToxicAura', 'name': 'Toxic Aura',
     'look': 'A thick coloured haze clings to the item in layers and boils slowly upward, with motes drifting through '
             'it (the sludge boards, cleaned of ground goo).',
     'item': {'hover': 0, 'spin': 0, 'material': item_fx(EmblemColor='$c', EmblemGlow=0.8, RimColor='$c', RimIntensity=0.5)},
     'elements': [
         shell('Haze1', 2.0, Color='$c', Intensity=0.7, EdgeAmount=1.0, EdgePower=1.8, NoiseAmount=1.0, NoiseScale=0.08,
               NoiseSpeed=7, NoiseGain=1.8, NoiseBias=-0.2, Wobble=1.5, PulseHz=0.45, PulseAmount=0.3),
         shell('Haze2', 6.0, Color='$c', Intensity=0.4, EdgeAmount=1.0, EdgePower=1.4, NoiseAmount=1.0, NoiseScale=0.05,
               NoiseSpeed=5, NoiseGain=1.8, NoiseBias=-0.3, Wobble=3.0, PulseHz=0.45, PulseAmount=0.3),
         shell('Haze3', 11.0, Color='$c', Intensity=0.18, EdgeAmount=1.0, EdgePower=1.2, NoiseAmount=1.0, NoiseScale=0.035,
               NoiseSpeed=4, NoiseGain=2.0, NoiseBias=-0.35, Wobble=4.0, HeightAmount=1.0, HeightTop=55, HeightSoft=25),
         {'kind': 'mesh', 'name': 'Motes', 'mesh': MOTES, 'loc': (0, 0, 2), 'scale': (0.45, 0.45, 0.5), 'spin': 9,
          'slots': {0: glow(Color='$c', Intensity=1.2, FadeDistance=0, PulseHz=0.45, PulseAmount=0.3)}},
         light(FRONT, 3, 220, KEY, 'pulse'),
     ]},
    {'n': 22, 'key': 'RarityMist', 'name': 'Rarity Mist',
     'look': 'The quietest option: a low, slow coloured mist hugs the lower half of the item and a soft light in the '
             'type colour; nothing else (a baseline).',
     'item': {'hover': 0, 'spin': 0},
     'elements': [
         shell('Mist', 4.0, Color='$c', Intensity=0.45, EdgeAmount=1.0, EdgePower=1.5, NoiseAmount=0.8, NoiseScale=0.04,
               NoiseSpeed=2.5, NoiseGain=1.6, NoiseBias=-0.1, Wobble=2.0, HeightAmount=1.0, HeightTop=22, HeightSoft=16),
         light(FRONT, 2.5, 200, KEY, None),
     ]},
    {'n': 23, 'key': 'ComboRadBloodNeon', 'name': 'Combo 5+6+13', 'priority': True,
     'look': 'The owner\'s combo: Radioactive seams and Geiger flicker on the item, the Blood Relic\'s thin mist hugging '
             'it, and the Busted Neon icon over it. Three separate colours: sick green seams, deep type-colour mist, '
             'bright type-colour neon.',
     'item': {'hover': 8, 'spin': 15, 'bob': (2, 0.5),
              'material': item_fx(**dict(RADIO_SKIN, SeamGlow=4.0, EmblemGlow=2.2, RimColor='$c', RimIntensity=0.7,
                                         RimExponent=3.5))},
     'elements': [
         shell('Mist', 1.5, **dict(BLOOD_MIST, Color=('$c', 0.8), Intensity=0.95)),
         {'kind': 'mesh', 'name': 'Motes', 'mesh': MOTES, 'loc': (0, 0, 4), 'scale': (0.5, 0.5, 0.5), 'spin': 14,
          'slots': {0: glow(Color=SICK, Intensity=1.2, FlickerRate=11, FlickerAmount=0.5, FadeDistance=0)}},
         {'kind': 'mesh', 'name': 'Sign', 'mesh': prop('Neon$icon'), 'loc': (0, 0, 96), 'scale': (0.9, 0.9, 0.9),
          'billboard': 'yaw', 'bob': (2, 0.5), 'shadow': False, 'slots': NEON},
         light((0, 6, 84), 4, 300, '$cd', 'buzz'),
         light(FRONT, 0.6, 160, SICK, 'geiger'),
         light((24, 0, 40), 1.5, 200, KEY, None),
     ]},
]


# A test bench of particle ingredients (PU2_BENCH=1): each one beside the two items, photographed close up.
BENCH = [
    {'n': 91, 'key': 'B_TrailBasic', 'name': 'Trail Basic_02', 'item': {},
     'elements': [trail('T', TRAIL_BASIC, (22, 30, 14, 0.6, 0.45, 0.0), emissive=20, size=3.0, lifetime=1.0,
                        extra={'Length': 3.0})]},
    {'n': 92, 'key': 'B_TrailMagic', 'name': 'Trail Magic', 'item': {},
     'elements': [trail('T', TRAIL_MAGIC, (22, 30, 14, 0.6, 0.45, 0.0), emissive=3, size=2.0, lifetime=1.0,
                        extra={'Length': 3.0})]},
    {'n': 93, 'key': 'B_TrailMagic2', 'name': 'Trail Magic_2', 'item': {},
     'elements': [trail('T', '/Game/ArrowTrail/FX/NS_ArrowTrail_Magic_2', (22, 30, 14, 0.6, 0.45, 0.0), emissive=3, size=2.0,
                        lifetime=1.0, extra={'Length': 3.0})]},
    {'n': 94, 'key': 'B_Sparks1', 'name': 'Sparks 01 retrigger', 'item': {},
     'elements': [dict(sparks('S', '$c', rate=20, size=0.7, velocity=0.7), retrigger=0.5)]},
    {'n': 95, 'key': 'B_ZSparks', 'name': 'Zombie sparks', 'item': {},
     'elements': [{'kind': 'niagara', 'name': 'S', 'system': '/Game/Zombie/Demo/Effects/NS_Sparks', 'loc': (0, 0, CENTER),
                   'retrigger': 0.6}]},
    {'n': 96, 'key': 'B_SurfSparks', 'name': 'Surface sparks', 'item': {},
     'elements': [{'kind': 'niagara', 'name': 'S', 'system': '/Game/A_Surface_Footstep/Niagara_FX/ParticleSystems/PSN_Sparks_Surface',
                   'loc': (0, 0, CENTER), 'retrigger': 0.6}]},
    {'n': 97, 'key': 'B_TrailFire', 'name': 'Trail Fire', 'item': {},
     'elements': [trail('T', '/Game/ArrowTrail/FX/NS_ArrowTrail_Fire', (22, 30, 14, 0.6, 0.45, 0.0), emissive=3, size=2.0,
                        lifetime=1.0, extra={'Length': 3.0})]},
    {'n': 98, 'key': 'B_Fire', 'name': 'Fire 0.15', 'item': {},
     'elements': [{'kind': 'niagara', 'name': 'S', 'system': '/Game/PostApocalypticCity/Particles/NS_Fire_01', 'loc': (0, 0, 40),
                   'scale': 0.15}]},
    {'n': 99, 'key': 'B_Smoky', 'name': 'Smoky 0.12', 'item': {},
     'elements': [{'kind': 'niagara', 'name': 'A', 'system': SMOKY, 'loc': (0, 0, CENTER),
                   'floats': {'Scale': 0.12, 'Duration': 600}, 'colors': {'Color_Min': ('$c', 0.5), 'Color_Max': ('$c', 0.03)}}]},
]


def look_folder(look):
    return '%s/S%02d_%s' % (STYLES2, look['n'], look['key'])


def mi_path(look, item_key, elem_name, slot=None):
    tail = elem_name if slot is None else '%s_%s' % (elem_name, slot_key(slot))
    return '%s/MI_S%02d_%s_%s' % (look_folder(look), look['n'], item_key, tail)


def ns_path(look, item_key, elem_name):
    return '%s/S%02d_%s/NS_S%02d_%s_%s' % (EFFECTS2, look['n'], look['key'], look['n'], item_key, elem_name)


def all_looks(bench=False):
    return LOOKS + (BENCH if bench else [])
