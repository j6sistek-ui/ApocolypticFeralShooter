"""AuthorPowerUpLive.py - build the live power-up displays and stand them in NYC Exploration (nullrhi, re-runnable).

The owner judges the power-up looks LIVE (Docs/POWERUP_CATALOG.md "DECIDED", Docs/POWERUP_BUILD.md): this script builds
real in-engine assets only. All motion is C++ (AHoverPowerUpDisplay, Source/HoverFlight/HoverPowerUpDisplay.*),
Niagara and material time; nothing here animates anything.

Makes (nothing outside these folders is edited; engine templates are duplicated, never changed):
  /Game/HoverPrototype/Effects/PowerUps/Live/
      M_PU_LiveSpark   additive Niagara sprite: white-hot core cooling to orange over the particle's life
      M_PU_LiveSmoke   translucent Niagara sprite: a small dark smoke puff (only with POP_PUFF, off since the fix round)
      M_PU_LiveMote    additive Niagara sprite: a soft mote in the item colour (MI_PU_LiveMote_<Item>)
      NS_PU_Live_SparkA / SparkB / SparkSingle / PopSparks   copies of the engine DirectionalBurst template
                       (6 / 7 / 1 / 3 velocity-stretched sparks under gravity, cone along the component's +Z)
      NS_PU_Live_PopPuff       slow DirectionalBurst copy on M_PU_LiveSmoke: the pop smoke puff (only with POP_PUFF)
      NS_PU_Live_Motes_<Item>  copy of RadialBurst (its OmnidirectionalBurst only): motes drifting up
  /Game/HoverPrototype/PowerUps/Live/<Item>/
      MI_PU_Live_<Item>_Skin (M_PU_ItemFX2), _Shell_<Name> (M_PU_Shell), _Neon<Slot> (M_PU_PropSimple),
      MI_PU_Live_Nuke_Pop<Part> (M_PU_GlowAdditive), DA_PU_Live_<Item> (UHoverPowerUpLook: every tunable)
  /Game/HoverPrototype/PowerUps/Styles/Shared/Props/NeonAmmo/SM_PU_NeonAmmo  (from SourceAssets/PowerUps/StyleProps,
      made by Scripts/Blender/MakePowerUpLiveProps.py)
  L_NYC_Explore: three AHoverPowerUpDisplay actors (NUKE, MEDKIT, MAX AMMO), tag AFS_PowerUpTrial, folder
      AFS_PowerUps, in a row 1.5 m apart about 3.5 m ahead of the player start and left of the sight line to the perk
      machines (tag AFS_PerkMachineTrial, never touched), on flat ground (traces), clear of small props (bounds) and in
      sight from the start at eye height. Only the persistent level is saved; the save is verified by a reload.

Every tunable is a named value below (LOOKS: one dict per item, keys = UHoverPowerUpLook properties; NIAGARA: module
inputs per system; MATERIAL params per instance). Change, re-run, open the map: the displays pick it up.
Receipt: D:/AFS_Comparisons/PowerUps_20261031/Live/author_receipt.json (incl. the Niagara tuning reports)
Fix round 2026-10-31 (independent check): no echo shell on the Nuke (it read as a floating ghost lid), echo on
Medkit / Max Ammo capped at 1.15x and half as bright; Nuke trefoil / seams a little brighter, key light 2.5 -> 4 cd
(tick + beat flash capped in C++); Max Ammo amber shifted to orange (1, .42, .03) so it does not read yellow-green
over the grass; the pop's smoke puff is OFF (POP_PUFF = False): it rendered but could not be made to read in front
of the black casing in 3 tries; bigger Niagara pools (C++). Before placing, the old Nuke's item is
hidden and the map saved through PreSave: the reload must show it (the hidden-phase save bug, fixed in C++).
2026-11-03 (owner: "it's a nuke ... should be twice as big as it was, and a little bit more sparky on the idle
phase"): Nuke item_scale 2, events every 1.6-2.6 s (was 2.4-3.6, first 1.2 s), both bursts at 50 %, dribble every 0.8 s;
sparks / pops start on casing points measured on the mesh (casing_points()), glint / pops / spark sprites x1.5, label
152 cm; the C++ display scales the key light offset / radius (and its intensity, linearly) with item_scale.
Usage: UnrealEditor-Cmd.exe AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput
       -DisablePlugins=NwiroIntegrationKit -ExecutePythonScript=M:/UnrealProjects/AFS/Scripts/AuthorPowerUpLive.py
Env: PU_LIVE_PLACE=0 builds the assets only (no map change).
"""
import json
import math
import os
import time
import traceback

import unreal as u

ROOT = '/Game/HoverPrototype/PowerUps'
LIVE = ROOT + '/Live'
FX = '/Game/HoverPrototype/Effects/PowerUps/Live'
MATS = ROOT + '/Styles/Shared/Materials'
PROPS = ROOT + '/Styles/Shared/Props'
PROP_SRC = 'M:/UnrealProjects/AFS/SourceAssets/PowerUps/StyleProps'
MAP = '/Game/HoverPrototype/Maps/L_NYC_Explore'
TAG = 'AFS_PowerUpTrial'
PERK_TAG = 'AFS_PerkMachineTrial'
FOLDER = 'AFS_PowerUps'
OUT = 'D:/AFS_Comparisons/PowerUps_20261031/Live'
PLACE = os.environ.get('PU_LIVE_PLACE', '1') != '0'
TEMPLATES = '/Niagara/DefaultAssets/Templates/Systems'

# placement (cm): row depth ahead of the player start, spacing, and how far left of the start line the row's right
# end may be (the perk machines stand ~10 m ahead, right of the line; their sight lines must stay clear)
AHEAD = 350.0
APART = 150.0
ROW_RIGHT_END = 0.0            # lateral offset (cm, + = right of the start's view line) of the rightmost item
FOOT, FLAT = 25.0, 6.0         # flat-ground footprint half-size and tolerance (a dropped pickup is ~40 cm wide)
CLEAR, CLUTTER_MAX = 10.0, 400.0
ROW_LEVEL = 4.0                # all three on the same ground level (the street), not one on a flat-topped rubble pile
# ground debris meshes have collision (the flatness traces see them), so they are not 'clutter' for the bounds check
GROUND_PREFIXES = ('SM_Ground', 'SM_Ivy', 'SM_Leaves', 'SM_Poster', 'Decal')
# 2026-10-31 survey: a 22 cm rubble pile (SM_Ground_4) lies 3.0-4.5 m ahead between the start line and the left
# barrel, so the search walks the depth down from 3.5 m until the row clears it
ORDER = ['Nuke', 'Medkit', 'MaxAmmo']           # left to right as seen from the start
LABELS = {'Nuke': 'NUKE', 'Medkit': 'MEDKIT', 'MaxAmmo': 'MAX AMMO'}
SEEDS = {'Nuke': 17, 'Medkit': 29, 'MaxAmmo': 41}
# label above the item (cm from the ground): the Nuke's (no neon) sits ~30 cm over its top, 30 + 45 x item_scale
# (2026-11-03: 118 -> 152 for the doubled Nuke, whose top is at 120 cm); the others over their neon icons
LABEL_HEIGHT = {'Nuke': 152.0, 'Medkit': 172.0, 'MaxAmmo': 172.0}

WHITEHOT = (1.0, 0.92, 0.85)
KEYW = (1.0, 0.9, 0.8)
BLOOD = (1.0, 0.05, 0.03)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def scale(a, k):
    return tuple(x * k for x in a)


ITEMS = {
    'Nuke': {'pu': 'PU_17_Nuke', 'c': (1.0, 0.42, 0.08), 'icon': None},
    'Medkit': {'pu': 'PU_06_Medkit', 'c': (1.0, 0.045, 0.035), 'cd': (1.0, 0.02, 0.02), 'icon': 'NeonCross'},
    # orange amber (was 1, .55, .05: read yellow-green over the grass); the neon icon is three cartridges (NeonAmmo,
    # the middle tip is the dead tube)
    'MaxAmmo': {'pu': 'PU_18_MaxAmmo', 'c': (1.0, 0.42, 0.03), 'cd': (1.0, 0.24, 0.01), 'icon': 'NeonAmmo'},
}
for _k, _it in ITEMS.items():
    _it['mesh'] = '%s/Meshes/%s/SM_%s' % (ROOT, _it['pu'], _it['pu'])
    _it['tex'] = '%s/Meshes/%s/%s/Textures/T_%s_' % (ROOT, _it['pu'], _it['pu'], _it['pu'])

# ---------------------------------------------------------------------------------------------------------------
# material instances (parameters of the round-2 masters, see Scripts/AuthorPowerUpStyles2.py)

NUKE_C = ITEMS['Nuke']['c']
SKINS = {
    # N4 trefoil / seams (the display flashes them white-hot on each tick), arcs off until the warning
    'Nuke': dict(Darken=0.92, Tint=(1.0, 0.97, 0.92), EmblemColor=(1.0, 0.62, 0.06), EmblemGlow=1.5,
                 SeamColor=mix(NUKE_C, WHITEHOT, 0.25), SeamGlow=1.5, RimColor=NUKE_C, RimIntensity=0.25,
                 RimExponent=4.0, ArcColor=mix(NUKE_C, WHITEHOT, 0.25), ArcIntensity=0.0, ArcScale=0.08,
                 ArcWidth=0.07, ArcRate=5.0, ArcPatch=0.35, GlowBoost=1.0),
    # Toxic aura skin + a touch of blood: slightly darker, red ember rim breathing at 0.9 Hz
    'Medkit': dict(Darken=0.85, Desaturate=0.15, Tint=(1.0, 0.88, 0.86), EmblemColor=ITEMS['Medkit']['c'],
                   EmblemGlow=1.6, SeamColor=ITEMS['Medkit']['c'], SeamGlow=0.0, RimColor=BLOOD, RimIntensity=1.3,
                   RimExponent=3.5, PulseHz=0.9, PulseAmount=0.4, GlowBoost=1.0),
    'MaxAmmo': dict(Darken=0.85, Desaturate=0.1, Tint=(1.0, 0.93, 0.88), EmblemColor=ITEMS['MaxAmmo']['c'],
                    EmblemGlow=1.2, SeamColor=ITEMS['MaxAmmo']['c'], SeamGlow=0.0, RimColor=BLOOD, RimIntensity=1.1,
                    RimExponent=3.5, PulseHz=0.9, PulseAmount=0.4, GlowBoost=1.0),
}


def aura_shells(c, k=1.0):
    """Look 21 (three hazes in the item colour, intensities x k) + look 6's thin red mist (the touch) + the
    heartbeat echo."""
    return [
        ('Haze1', 'Aura', dict(Inflate=2.0, Color=c, Intensity=0.7 * k, EdgeAmount=1.0, EdgePower=1.8, NoiseAmount=1.0,
                               NoiseScale=0.08, NoiseSpeed=7, NoiseGain=1.8, NoiseBias=-0.2, Wobble=1.5, PulseHz=0.45,
                               PulseAmount=0.3)),
        ('Haze2', 'Aura', dict(Inflate=6.0, Color=c, Intensity=0.4 * k, EdgeAmount=1.0, EdgePower=1.4, NoiseAmount=1.0,
                               NoiseScale=0.05, NoiseSpeed=5, NoiseGain=1.8, NoiseBias=-0.3, Wobble=3.0, PulseHz=0.45,
                               PulseAmount=0.3)),
        ('Haze3', 'Aura', dict(Inflate=11.0, Color=c, Intensity=0.18 * k, EdgeAmount=1.0, EdgePower=1.2, NoiseAmount=1.0,
                               NoiseScale=0.035, NoiseSpeed=4, NoiseGain=2.0, NoiseBias=-0.35, Wobble=4.0,
                               HeightAmount=1.0, HeightTop=55, HeightSoft=25)),
        ('BloodMist', 'Aura', dict(Inflate=1.5, Color=BLOOD, Intensity=0.45, EdgeAmount=1.0, EdgePower=2.2,
                                   NoiseAmount=1.0, NoiseScale=0.07, NoiseSpeed=9.0, NoiseGain=1.6, NoiseBias=-0.15,
                                   Wobble=1.5, PulseHz=0.9, PulseAmount=0.35)),
        # half as bright as first built (0.7) and grown only to echo_max_scale 1.15
        ('Echo', 'HeartbeatEcho', dict(Inflate=1.5, Color=c, Intensity=0.35, EdgeAmount=1.0, EdgePower=1.6)),
    ]


SHELLS = {
    'Nuke': [
        ('Arcs', 'ArcCrawl', dict(Inflate=3.0, Color=NUKE_C, Intensity=0.0, ArcColor=mix(NUKE_C, WHITEHOT, 0.35),
                                  ArcIntensity=0.0, ArcScale=0.05, ArcWidth=0.06, ArcRate=11, ArcPatch=0.45, ArcEdge=1.0)),
        # no heartbeat echo shell on the Nuke (owner: no fog or haze; it read as a floating orange ghost lid)
    ],
    'Medkit': aura_shells(ITEMS['Medkit']['c']),
    # amber reads far brighter than red at the same intensity: the recipe's haze values x 0.7
    'MaxAmmo': aura_shells(ITEMS['MaxAmmo']['c'], 0.7),
}


def neon_mats(cd):
    return {'Lit': dict(Color=scale(cd, 0.25), EmissiveColor=cd, EmissiveIntensity=12, FlickerRate=0, FlickerAmount=0,
                        Roughness=0.1),
            'Dead': dict(Color=(0.05, 0.05, 0.05), EmissiveColor=cd, EmissiveIntensity=0.25, FlickerRate=0,
                         FlickerAmount=0, Roughness=0.1),
            'Frame': dict(Color=(0.025, 0.025, 0.024), Roughness=0.55, Metallic=0.6, GrimeAmount=0.5)}


POP_MATS = {  # M_PU_GlowAdditive on camera-facing planes (the display scales and fades them)
    'PopCore': dict(Color=WHITEHOT, Intensity=14.0, RadialAmount=1.0, RadialPower=2.6, FadeDistance=0.0),
    'PopGlow': dict(Color=(1.0, 0.42, 0.08), Intensity=3.0, RadialAmount=1.0, RadialPower=2.0, FadeDistance=0.0),
    'PopRay': dict(Color=(1.0, 0.8, 0.5), Intensity=16.0, RadialAmount=1.0, RadialPower=1.4, FadeDistance=0.0),
}

# ---------------------------------------------------------------------------------------------------------------
# Niagara: engine template copies, tuned module inputs (suffix -> value), see UHoverAuthoring::ConfigurePowerUpLiveEffect

SPARK = {
    'AddVelocityInCone.Cone Angle': '55', 'AddVelocityInCone.Cone Axis': '0,0,1',
    'RandomRangeFloat002.Minimum': '140', 'RandomRangeFloat002.Maximum': '330',
    'InitializeParticle.Lifetime Min': '0.45', 'InitializeParticle.Lifetime Max': '0.95',
    # x1.5 for the doubled Nuke (2026-11-03; was 0.25,0.8 / 0.4,1.2): at 2x the casing the sparks read as hairlines
    'InitializeParticle.Sprite Size Min': '0.38,1.2', 'InitializeParticle.Sprite Size Max': '0.6,1.8',
    'ScaleSpriteSizeBySpeed.Min Scale Factor': '1,1', 'ScaleSpriteSizeBySpeed.Max Scale Factor': '1,4',
    'ScaleSpriteSizeBySpeed.Velocity Threshold': '320', 'GravityForce.Gravity': '0,0,-750',
    'InitializeParticle.Color': '1,1,1,1', 'SpawnBurst_Instantaneous.Spawn Count': '6',
}
# The pop's smoke puff (N2 "small dark smoke puff") is OFF: fix round 2026-10-31 could not make it read. It rendered (a
# light grey column above the cap while every burst had 20 particles), but at its real 5 particles a dark or grey-brown
# puff vanished against the black casing it rises in front of (3 tries: see SPRITE_MATS LiveSmoke). True rebuilds
# NS_PU_Live_PopPuff / M_PU_LiveSmoke and gives the Nuke its puff again; False deletes both once unreferenced.
POP_PUFF = False
# Fix round 2026-10-31: until HoverAuthoring.ConfigurePowerUpLiveEffect also wrote the emitter spawn / update scripts,
# every burst here (sparks, pop sparks, puff, motes) spawned the templates' 20 particles, not these counts.
NIAGARA = {
    'SparkA': ('DirectionalBurst', 'DirectionalBurst', 'LiveSpark', True, dict(SPARK)),
    'SparkB': ('DirectionalBurst', 'DirectionalBurst', 'LiveSpark', True,
               dict(SPARK, **{'SpawnBurst_Instantaneous.Spawn Count': '7', 'AddVelocityInCone.Cone Angle': '65'})),
    'SparkSingle': ('DirectionalBurst', 'DirectionalBurst', 'LiveSpark', True,
                    dict(SPARK, **{'SpawnBurst_Instantaneous.Spawn Count': '1', 'RandomRangeFloat002.Minimum': '60',
                                   'RandomRangeFloat002.Maximum': '170', 'InitializeParticle.Lifetime Min': '0.5',
                                   'InitializeParticle.Lifetime Max': '1.1'})),
    'PopSparks': ('DirectionalBurst', 'DirectionalBurst', 'LiveSpark', True,
                  dict(SPARK, **{'SpawnBurst_Instantaneous.Spawn Count': '3', 'AddVelocityInCone.Cone Angle': '75',
                                 'RandomRangeFloat002.Minimum': '170', 'RandomRangeFloat002.Maximum': '360',
                                 'InitializeParticle.Lifetime Min': '0.3', 'InitializeParticle.Lifetime Max': '0.6'})),
    # (the first try, a SimpleExplosion copy, rendered nothing: the puff is a slow DirectionalBurst copy instead.
    # Fix round: it did render, but as 6-11 cm near-black soft dots at low opacity half inside the black casing, i.e.
    # invisible; now larger grey-brown sprites, started PopSmokeOffsetCm out from the casing, opacity in the material)
    'PopPuff': ('DirectionalBurst', 'DirectionalBurst', 'LiveSmoke', False, dict(SPARK, **{
        'SpawnBurst_Instantaneous.Spawn Count': '5', 'AddVelocityInCone.Cone Angle': '45',
        'RandomRangeFloat002.Minimum': '10', 'RandomRangeFloat002.Maximum': '30', 'GravityForce.Gravity': '0,0,22',
        'InitializeParticle.Lifetime Min': '0.9', 'InitializeParticle.Lifetime Max': '1.4',
        'InitializeParticle.Sprite Size Min': '13,13', 'InitializeParticle.Sprite Size Max': '21,21',
        'ScaleSpriteSizeBySpeed.Max Scale Factor': '1,1'})),
}
MOTES = {
    'SpawnBurst_Instantaneous.Spawn Count': '5', 'ShapeLocation.Sphere Radius': '20',
    'AddVelocity.Origin Offset': '0,0,-30', 'RandomRangeFloat.Minimum': '4', 'RandomRangeFloat.Maximum': '14',
    'GravityForce.Gravity': '0,0,10', 'Drag.Drag': '0.6', 'InitializeParticle.Lifetime Min': '2.4',
    'InitializeParticle.Lifetime Max': '3.6', 'InitializeParticle.Uniform Sprite Size Min': '0.6',
    'InitializeParticle.Uniform Sprite Size Max': '1.3', 'InitializeParticle.Color': '1,1,1,1',
}
SPRITE_MATS = {
    'LiveSpark': dict(HotColor=(1.0, 0.9, 0.7), HotIntensity=30.0, CoolColor=(1.0, 0.22, 0.02), CoolIntensity=12.0,
                      CoolPower=0.35, FadePower=1.2, MaskPower=1.3),
    # grey-brown, was (0.035, 0.03, 0.027), 0.85, 1.2 (invisible). Fix round: (0.11, 0.085, 0.065) read as a light grey
    # column (the template's 20 particles a burst, see NIAGARA); (0.075, 0.058, 0.044) at 5 particles vanished against
    # the black casing. It must stay lighter than the casing it rises in front of.
    'LiveSmoke': dict(SmokeColor=(0.13, 0.1, 0.075), Opacity=1.0, MaskPower=0.6, FadePower=1.5),
}

# ---------------------------------------------------------------------------------------------------------------
# the looks (UHoverPowerUpLook properties, python names). Materials / systems are filled in by build_looks().

COMMON = dict(hover_cm=30.0, bob_cm=2.0, bob_hz=0.5, item_scale=1.0, life_seconds=30.0, spawn_in_seconds=0.35,
              fade_out_seconds=0.5, respawn_delay_seconds=2.0, warning_seconds=5.0)
LOOKS = {
    # AFS 2026-11-01 owner: the Nuke read much smaller than the medkit and ammo; twice as big, a bit more sparky idling
    'Nuke': dict(COMMON, item_scale=2.0, spin_deg_per_sec=30.0, item_color=NUKE_C,
                 key_light_color=(1.0, 0.72, 0.42), key_light_intensity=4.0, key_light_radius=220.0,
                 key_light_offset=(26, 0, 30),
                 # N4 Geiger stutter ticks throughout
                 geiger_ticks=True, tick_mean_interval=1.6, tick_min_interval=0.35, tick_max_interval=3.5,
                 tick_triple_chance=0.3, tick_triple_gap=0.09, tick_flash_seconds=0.07, tick_emblem_glow=9.0,
                 tick_seam_glow=7.0, tick_white_hot=WHITEHOT, tick_shudder_cm=2.4, tick_shudder_hz=30.0,
                 # 2026-11-03 doubled Nuke: the glint and pop sizes are world cm (C++), x1.5 so they still read on
                 # the 2x casing without turning into fireworks (were 9 / 3.5 / 18 / 12 / 0.7)
                 flash_emblem_glow_max=8.0, flash_seam_glow_max=7.0, glint_size_cm=13.0,
                 glint_intensity=1.0, tick_light_kick=2.5,
                 # N1 sparks alternating with N2 pops, calm pace over the 30 s
                 event_interval_min=1.6, event_interval_max=2.6, first_event_seconds=1.2,
                 # the seam rings; casing_points (mesh space) are measured on the mesh from these by casing_points()
                 seam_height_fractions=[0.2, 0.5, 0.8],
                 spark_bursts=True, spark_both_chance=0.5, dribble_mean_interval=0.8, spark_light_kick=3.0,
                 pops=True, pop_core_cm=5.0, pop_glow_cm=27.0, pop_ray_length_cm=18.0, pop_ray_width_cm=1.0,
                 pop_rays_min=4, pop_rays_max=6, pop_core_seconds=0.05, pop_glow_seconds=0.16, pop_ray_seconds=0.06,
                 pop_light_intensity=12.0, pop_light_radius=220.0, pop_light_color=(1.0, 0.75, 0.45),
                 pop_jolt_cm=1.2, pop_jolt_seconds=0.12, pop_smoke_offset_cm=6.0,
                 # last 5 s: heartbeat + arc crawl ease in together and speed up toward despawn
                 warning='HEARTBEAT_AND_ARCS', warning_ease_in_seconds=3.0, beat_hz_start=1.0, beat_hz_end=2.4,
                 beat_accel_power=1.4, beat_swell=0.12, beat_dub_strength=0.6, beat_glow_flash=1.8,
                 beat_light_kick=4.0,
                 arc_skin_intensity=10.0, arc_shell_intensity=7.0, arc_rate_start=5.0, arc_rate_end=22.0,
                 arc_patch_start=0.3, arc_patch_end=0.5, discharge_rate_start=2.0, discharge_rate_end=14.0,
                 discharge_light_kick=9.0, discharge_light_color=(1.0, 0.85, 0.6), discharge_spark_chance=0.2),
}
for _k in ('Medkit', 'MaxAmmo'):
    c, cd = ITEMS[_k]['c'], ITEMS[_k]['cd']
    LOOKS[_k] = dict(COMMON, spin_deg_per_sec=25.0, item_color=c,
                     key_light_color=mix(c, KEYW, 0.55), key_light_intensity=3.0, key_light_radius=220.0,
                     key_light_offset=(26, 0, 30), key_light_pulse_hz=0.45, key_light_pulse_amount=0.25,
                     mote_burst_interval=1.1, mote_offset=(0, 0, 18),
                     # look 13 Busted Neon
                     neon_height_cm=92.0, neon_scale=1.0, neon_bob_cm=2.0, neon_bob_hz=0.5, neon_lit_intensity=12.0,
                     neon_buzz_rate=14.0, neon_buzz_amount=0.12, neon_dead_on_intensity=8.0,
                     neon_dead_off_intensity=0.25, neon_stutter_gap_min=0.7, neon_stutter_gap_max=2.6,
                     neon_stutter_burst_min=0.15, neon_stutter_burst_max=0.6, neon_stutter_hz=18.0,
                     neon_light_color=cd, neon_light_intensity=5.0, neon_light_radius=340.0,
                     neon_light_offset=(0, 6, -12),
                     # last 5 s: heartbeat (look 20), beats slightly faster toward the end
                     warning='HEARTBEAT', warning_ease_in_seconds=1.5, beat_hz_start=1.25, beat_hz_end=1.55,
                     beat_accel_power=1.0, beat_swell=0.12, beat_dub_strength=0.6, beat_glow_flash=1.6,
                     beat_light_kick=4.0, echo_max_scale=1.15, echo_seconds=0.38)

EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
R = {'ok': True, 'errors': [], 'warnings': [], 'materials': {}, 'niagara': {}, 'looks': {}, 'placed': [],
     'time': time.strftime('%Y-%m-%d %H:%M:%S')}


def log(*a):
    print('PU_LIVE', *a, flush=True)


def err(m):
    R['ok'] = False
    R['errors'].append(m)
    log('ERROR', m)


def warn(m):
    R['warnings'].append(m)
    log('WARN', m)


# ---------------------------------------------------------------------------------------------------------------
# small material graph helper (same idea as AuthorPowerUpStyles2.MB)

BM = u.BlendMode
SM = u.MaterialShadingModel
MP = u.MaterialProperty


class MB:
    def __init__(self, path, blend, shading):
        folder, name = path.rsplit('/', 1)
        EAL.make_directory(folder)
        m = u.load_asset(path)
        if not m:
            m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
        else:
            MEL.delete_all_material_expressions(m)
        self.m, self.path, self.fails, self.y = m, path, [], 0
        m.set_editor_property('blend_mode', blend)
        m.set_editor_property('shading_model', shading)
        m.set_editor_property('used_with_niagara_sprites', True)

    def node(self, cls, **props):
        self.y += 60
        e = MEL.create_material_expression(self.m, cls, -1200 + 260 * (self.y // 1800), self.y % 1800)
        for k, v in props.items():
            e.set_editor_property(k, v)
        return e

    def link(self, a, b, inp):
        a, o = a if isinstance(a, tuple) else (a, '')
        for i in (inp if isinstance(inp, (list, tuple)) else [inp]):
            if MEL.connect_material_expressions(a, o, b, i):
                return
        self.fails.append('%s -> %s' % (o, inp))

    def val(self, v):
        return self.node(u.MaterialExpressionConstant, r=float(v)) if isinstance(v, (int, float)) else v

    def bin(self, cls, a, b):
        e = self.node(cls)
        self.link(self.val(a), e, 'A')
        self.link(self.val(b), e, 'B')
        return e

    def mul(self, a, b):
        return self.bin(u.MaterialExpressionMultiply, a, b)

    def sub(self, a, b):
        return self.bin(u.MaterialExpressionSubtract, a, b)

    def lerp(self, a, b, t):
        e = self.node(u.MaterialExpressionLinearInterpolate)
        self.link(self.val(a), e, 'A')
        self.link(self.val(b), e, 'B')
        self.link(self.val(t), e, 'Alpha')
        return e

    def power(self, a, p):
        e = self.node(u.MaterialExpressionPower)
        self.link(self.val(a), e, 'Base')
        self.link(self.val(p), e, ['Exp', 'Exponent'])
        return e

    def sat(self, a):
        e = self.node(u.MaterialExpressionSaturate)
        self.link(self.val(a), e, '')
        return e

    def scalar(self, n, d):
        return self.node(u.MaterialExpressionScalarParameter, parameter_name=n, default_value=float(d), group='Live')

    def vector(self, n, c):
        return self.node(u.MaterialExpressionVectorParameter, parameter_name=n,
                         default_value=u.LinearColor(c[0], c[1], c[2], 1.0), group='Live')

    def radial(self, power):
        uv = self.node(u.MaterialExpressionTextureCoordinate)
        d = self.node(u.MaterialExpressionDistance)
        self.link(uv, d, 'A')
        self.link(self.node(u.MaterialExpressionConstant2Vector, r=0.5, g=0.5), d, 'B')
        return self.power(self.sat(self.sub(1.0, self.mul(d, 2.0))), power)

    def rgb(self, a):
        e = self.node(u.MaterialExpressionComponentMask, r=True, g=True, b=True, a=False)
        self.link(a, e, '')
        return e

    def out(self, a, prop):
        a, o = a if isinstance(a, tuple) else (a, '')
        if not MEL.connect_material_property(a, o, prop):
            self.fails.append('property %s' % prop)

    def finish(self):
        MEL.recompile_material(self.m)
        EAL.save_loaded_asset(self.m)
        R['materials'][self.path] = {'fails': self.fails,
                                     'scalars': [str(x) for x in MEL.get_scalar_parameter_names(self.m)]}
        if self.fails:
            err('%s: %s' % (self.path, self.fails))
        return self.m


def build_sprite_materials():
    out = {}
    # sparks: white-hot when born, cooling to orange; fading; a soft core stretched along the velocity
    b = MB(FX + '/M_PU_LiveSpark', BM.BLEND_ADDITIVE, SM.MSM_UNLIT)
    p = SPRITE_MATS['LiveSpark']
    age = b.node(u.MaterialExpressionParticleRelativeTime)
    pc = b.node(u.MaterialExpressionParticleColor)
    hot = b.mul(b.vector('HotColor', p['HotColor']), b.scalar('HotIntensity', p['HotIntensity']))
    cool = b.mul(b.vector('CoolColor', p['CoolColor']), b.scalar('CoolIntensity', p['CoolIntensity']))
    col = b.lerp(hot, cool, b.power(b.sat(age), b.scalar('CoolPower', p['CoolPower'])))
    fade = b.power(b.sat(b.sub(1.0, age)), b.scalar('FadePower', p['FadePower']))
    em = b.mul(b.mul(b.mul(col, fade), b.radial(b.scalar('MaskPower', p['MaskPower']))), b.mul(b.rgb(pc), (pc, 'A')))
    b.out(em, MP.MP_EMISSIVE_COLOR)
    out['LiveSpark'] = b.finish()
    # smoke: a dark soft puff that thins out as it ages (only with POP_PUFF)
    if POP_PUFF:
        b = MB(FX + '/M_PU_LiveSmoke', BM.BLEND_TRANSLUCENT, SM.MSM_UNLIT)
        p = SPRITE_MATS['LiveSmoke']
        age = b.node(u.MaterialExpressionParticleRelativeTime)
        b.out(b.vector('SmokeColor', p['SmokeColor']), MP.MP_EMISSIVE_COLOR)
        rise = b.sat(b.mul(age, 8.0))
        # the opacity envelope is all here (not the template's particle alpha curve)
        op = b.mul(b.mul(b.radial(b.scalar('MaskPower', p['MaskPower'])), b.scalar('Opacity', p['Opacity'])),
                   b.mul(rise, b.power(b.sat(b.sub(1.0, age)), b.scalar('FadePower', p['FadePower']))))
        b.out(op, MP.MP_OPACITY)
        out['LiveSmoke'] = b.finish()
    # motes: soft dots in the item colour, fading in and out over the life
    b = MB(FX + '/M_PU_LiveMote', BM.BLEND_ADDITIVE, SM.MSM_UNLIT)
    age = b.node(u.MaterialExpressionParticleRelativeTime)
    sine = b.node(u.MaterialExpressionSine, period=2.0)
    b.link(age, sine, '')
    em = b.mul(b.mul(b.mul(b.vector('Color', (1, 0.5, 0.1)), b.scalar('Intensity', 4.0)), b.radial(2.0)), b.sat(sine))
    b.out(em, MP.MP_EMISSIVE_COLOR)
    out['LiveMote'] = b.finish()
    return out


def make_mi(path, parent, params):
    folder, name = path.rsplit('/', 1)
    EAL.make_directory(folder)
    mi = u.load_asset(path)
    if not mi:
        mi = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    else:
        MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, parent)
    names_s = set(str(x) for x in MEL.get_scalar_parameter_names(parent))
    names_v = set(str(x) for x in MEL.get_vector_parameter_names(parent))
    names_t = set(str(x) for x in MEL.get_texture_parameter_names(parent))
    missing = []
    for k, v in params.items():
        if isinstance(v, u.Texture):
            if k not in names_t:
                missing.append(k)
            MEL.set_material_instance_texture_parameter_value(mi, k, v)
        elif isinstance(v, (tuple, list)):
            if k not in names_v:
                missing.append(k)
            c = list(v) + [1.0] * (4 - len(v))
            MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(c[0], c[1], c[2], c[3]))
        else:
            if k not in names_s:
                missing.append(k)
            MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))   # returns False on success
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi)
    if missing:
        err('%s: parent %s has no %s' % (path, parent.get_name(), missing))
    rb = {k: round(MEL.get_material_instance_scalar_parameter_value(mi, k), 3)
          for k, v in list(params.items())[:3] if isinstance(v, (int, float))}
    R['materials'][path] = {'parent': parent.get_name(), 'readback': rb}
    return mi


# ---------------------------------------------------------------------------------------------------------------
# imports

def import_neon_props():
    for name in ('NeonAmmo',):
        target = '%s/%s/SM_PU_%s' % (PROPS, name, name)
        src = '%s/SM_PU_%s.glb' % (PROP_SRC, name)
        if EAL.does_asset_exist(target):
            continue
        if not os.path.exists(src):
            err('missing %s (run Scripts/Blender/MakePowerUpLiveProps.py)' % src)
            continue
        task = u.AssetImportTask()
        task.filename = src
        task.destination_path = '%s/%s' % (PROPS, name)
        task.automated = True
        task.replace_existing = True
        task.save = True
        AT.import_asset_tasks([task])
        meshes = [p.split('.')[0] for p in EAL.list_assets('%s/%s' % (PROPS, name), True, False)
                  if isinstance(u.load_asset(p), u.StaticMesh)]
        if not meshes:
            err('neon prop import failed ' + src)
            continue
        if meshes[0] != target:
            EAL.rename_asset(meshes[0], target)
        EAL.save_loaded_asset(u.load_asset(target))
    for name in ('NeonCross', 'NeonAmmo'):
        sm = u.load_asset('%s/%s/SM_PU_%s' % (PROPS, name, name))
        if sm:
            bb = sm.get_bounding_box()
            R.setdefault('neon', {})[name] = {'slots': [str(m.material_slot_name) for m in sm.static_materials],
                                              'min': [round(bb.min.x, 1), round(bb.min.y, 1), round(bb.min.z, 1)],
                                              'max': [round(bb.max.x, 1), round(bb.max.y, 1), round(bb.max.z, 1)]}


def build_niagara(sprite_mats):
    out = {}
    jobs = dict(NIAGARA)
    if not POP_PUFF:
        jobs.pop('PopPuff')
    for k in ('Medkit', 'MaxAmmo'):
        jobs['Motes_' + k] = ('RadialBurst', 'OmnidirectionalBurst', 'Mote_' + k, False, dict(MOTES))
    mote_parent = sprite_mats['LiveMote']
    for name, (template, keep, mat_key, velocity, values) in jobs.items():
        dst = '%s/NS_PU_Live_%s' % (FX, name)
        # first run: a copy of the engine template; later runs re-apply every value to that copy (idempotent)
        ns = u.load_asset(dst) if EAL.does_asset_exist(dst) else EAL.duplicate_asset('%s/%s' % (TEMPLATES, template), dst)
        if not ns:
            err('duplicate failed ' + dst)
            continue
        if mat_key.startswith('Mote_'):
            item = mat_key[len('Mote_'):]
            mat = make_mi('%s/MI_PU_LiveMote_%s' % (FX, item), mote_parent,
                          dict(Color=ITEMS[item]['c'], Intensity=4.0))
        else:
            mat = sprite_mats[mat_key]
        rep = u.HoverAuthoring.configure_power_up_live_effect(ns, keep, mat, velocity, values)
        EAL.save_loaded_asset(ns)
        lines = rep.splitlines()
        R['niagara'][name] = {'path': dst, 'template': template, 'set': [x for x in lines if x.startswith('SET')],
                              'missing': [x for x in lines if x.startswith('MISSING')],
                              'sys': [x for x in lines if x.startswith('SYS')][:80],
                              'other': [x for x in lines if not x.startswith(('SET', 'MISSING', 'SYS'))]}
        if R['niagara'][name]['missing']:
            warn('%s: %s' % (name, R['niagara'][name]['missing']))
        out[name] = ns
    return out


def mesh_triangles(mesh):
    """LOD0 render vertices (mesh space) and triangle index triples (ProceduralMeshComponent's library, an engine
    default plugin)."""
    vs, tris = [], []
    for sec in range(mesh.get_num_sections(0)):
        res = u.ProceduralMeshLibrary.get_section_from_static_mesh(mesh, 0, sec)
        verts, idx = res[0], res[1]
        base = len(vs)
        vs += [(p.x, p.y, p.z) for p in verts]
        tris += [(base + idx[i], base + idx[i + 1], base + idx[i + 2]) for i in range(0, len(idx) - 2, 3)]
    return vs, tris


def slice_points(vs, tris, zh):
    """Where the mesh surface crosses the plane z = zh: the end points of every triangle's cut segment (plus the segment
    midpoint), so a low-poly casing gives its true outline, not the nearest vertices."""
    out = []
    for t in tris:
        ps = [vs[i] for i in t]
        cut = []
        for a, b in ((ps[0], ps[1]), (ps[1], ps[2]), (ps[2], ps[0])):
            if (a[2] - zh) * (b[2] - zh) < 0:
                f = (zh - a[2]) / (b[2] - a[2])
                cut.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
        if len(cut) == 2:
            out += [cut[0], cut[1], ((cut[0][0] + cut[1][0]) / 2, (cut[0][1] + cut[1][1]) / 2)]
    return out


def casing_points(key, mesh, fractions, bins=24, inset=0.97, caps=12):
    """AFS 2026-11-03 (doubled Nuke): the sparks and pops start on the casing itself. The bounds rings (C++ fallback:
    radius 0.92 x the smaller half-width) sat ~3 cm inside the 31.7 x 27.1 cm egg on its wide side and outside it near
    the rounded top and bottom, and item_scale 2 doubles that. Here each seam ring is the mesh cut at that height: the
    outermost surface point per 15 deg bin (x inset), plus `caps` points on the lid (C++ gives z > top - 1 an up
    normal). Returns [] (C++ falls back to the bounds rings) if the mesh cannot be read."""
    try:
        vs, tris = mesh_triangles(mesh)
    except Exception as e:  # noqa: BLE001
        warn('%s casing points: mesh unreadable (%s); bounds rings used' % (key, e))
        return []
    bb = mesh.get_bounding_box()
    mn, mx = bb.min, bb.max
    if len(tris) < 50:
        warn('%s casing points: only %d triangles; bounds rings used' % (key, len(tris)))
        return []
    vz0, vz1 = min(v[2] for v in vs), max(v[2] for v in vs)
    if abs((vz1 - vz0) - (mx.z - mn.z)) > 0.02 * (mx.z - mn.z):
        warn('%s casing points: render height %.1f != bounds %.1f; bounds rings used' % (key, vz1 - vz0, mx.z - mn.z))
        return []
    cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2

    def outline(xy, nbins):
        best = {}
        for x, y in xy:
            a = math.atan2(y - cy, x - cx)
            r = math.hypot(x - cx, y - cy)
            k = int((a + math.pi) / (2 * math.pi) * nbins) % nbins
            if r > best.get(k, (0, 0))[0]:
                best[k] = (r, a)
        return best

    pts, rings = [], {}
    for h in fractions:
        zh = mn.z + (mx.z - mn.z) * h
        best = outline(slice_points(vs, tris, zh), bins)
        for k, (r, a) in sorted(best.items()):
            pts.append((cx + r * inset * math.cos(a), cy + r * inset * math.sin(a), zh))
        rr = [r for r, _ in best.values()]
        rings[str(h)] = {'z': round(zh, 1), 'bins': len(best), 'r_min': round(min(rr), 1) if rr else None,
                         'r_max': round(max(rr), 1) if rr else None}
    ztop = mx.z - 0.5
    cap = outline(slice_points(vs, tris, mx.z - 1.0), caps)
    for k, (r, a) in sorted(cap.items()):
        pts.append((cx + r * 0.6 * math.cos(a), cy + r * 0.6 * math.sin(a), ztop))
    R.setdefault('casing_points', {})[key] = {
        'triangles': len(tris), 'points': len(pts), 'cap_points': len(cap),
        'cap_r_max': round(max([r for r, _ in cap.values()] or [0]), 1), 'rings': rings,
        'bounds_half_width': [round((mx.x - mn.x) / 2, 1), round((mx.y - mn.y) / 2, 1)],
        'old_ring_radius': round(min(mx.x - mn.x, mx.y - mn.y) / 2 * 0.92, 1)}
    log('casing points', key, R['casing_points'][key])
    return [u.Vector(*p) for p in pts]


def build_looks(niagara):
    parents = {k: u.load_asset('%s/M_PU_%s' % (MATS, k)) for k in ('ItemFX2', 'Shell', 'PropSimple', 'GlowAdditive')}
    for k, v in parents.items():
        if not v:
            raise RuntimeError('master M_PU_%s missing (run Scripts/AuthorPowerUpStyles2.py)' % k)
    looks = {}
    for key, spec in LOOKS.items():
        item = ITEMS[key]
        folder = '%s/%s' % (LIVE, key)
        EAL.make_directory(folder)
        mesh = u.load_asset(item['mesh'])
        if not mesh:
            err('mesh missing ' + item['mesh'])
            continue
        tex = {s + 'Tex': u.load_asset(item['tex'] + {'BaseColor': 'BaseColor', 'Normal': 'Normal', 'ORM': 'ORM'}[s])
               for s in ('BaseColor', 'Normal', 'ORM')}
        if not all(tex.values()):
            err('%s textures missing under %s*' % (key, item['tex']))
        skin = make_mi('%s/MI_PU_Live_%s_Skin' % (folder, key), parents['ItemFX2'], dict(SKINS[key], **tex))
        shells = []
        for name, role, params in SHELLS[key]:
            mi = make_mi('%s/MI_PU_Live_%s_Shell_%s' % (folder, key, name), parents['Shell'], params)
            s = u.HoverPowerUpShell()
            s.set_editor_property('material', mi)
            s.set_editor_property('role', getattr(u.HoverPowerUpShellRole, {'Aura': 'AURA', 'ArcCrawl': 'ARC_CRAWL',
                                                                           'HeartbeatEcho': 'HEARTBEAT_ECHO'}[role]))
            shells.append(s)
        da_path = '%s/DA_PU_Live_%s' % (folder, key)
        da = u.load_asset(da_path)
        if not da:
            f = u.DataAssetFactory()
            f.set_editor_property('data_asset_class', u.HoverPowerUpLook)
            da = AT.create_asset('DA_PU_Live_%s' % key, folder, u.HoverPowerUpLook, f)
        props = dict(spec)
        props.update(item_mesh=mesh, item_material=skin, shells=shells)
        if key == 'Nuke':
            props['casing_points'] = casing_points(key, mesh, spec.get('seam_height_fractions') or [0.2, 0.5, 0.8])
            props.update(spark_burst_a=niagara.get('SparkA'), spark_burst_b=niagara.get('SparkB'),
                         spark_single=niagara.get('SparkSingle'), pop_sparks=niagara.get('PopSparks'),
                         pop_smoke=niagara.get('PopPuff'))
            for part, params in POP_MATS.items():
                props['%s_material' % {'PopCore': 'pop_core', 'PopGlow': 'pop_glow', 'PopRay': 'pop_ray'}[part]] = \
                    make_mi('%s/MI_PU_Live_Nuke_%s' % (folder, part), parents['GlowAdditive'], params)
        else:
            nm = neon_mats(item['cd'])
            props.update(neon_mesh=u.load_asset('%s/%s/SM_PU_%s' % (PROPS, item['icon'], item['icon'])),
                         neon_lit_material=make_mi('%s/MI_PU_Live_%s_NeonLit' % (folder, key), parents['PropSimple'], nm['Lit']),
                         neon_dead_material=make_mi('%s/MI_PU_Live_%s_NeonDead' % (folder, key), parents['PropSimple'], nm['Dead']),
                         neon_frame_material=make_mi('%s/MI_PU_Live_%s_NeonFrame' % (folder, key), parents['PropSimple'], nm['Frame']),
                         mote_system=niagara.get('Motes_' + key))
            if not props['neon_mesh']:
                err('%s neon mesh %s missing' % (key, item['icon']))
        rec = {}
        for k, v in props.items():
            if k == 'warning':
                v = getattr(u.HoverPowerUpWarning, v)
            elif k.endswith('_color') and isinstance(v, tuple):
                v = u.LinearColor(v[0], v[1], v[2], 1.0)
            elif k.endswith('_offset') and isinstance(v, tuple):
                v = u.Vector(*v)
            try:
                da.set_editor_property(k, v)
            except Exception as e:  # noqa: BLE001
                err('%s.%s: %s' % (da_path, k, e))
            if k == 'casing_points':
                v = '%d points' % len(v)
            rec[k] = v.get_path_name() if hasattr(v, 'get_path_name') else (str(v) if not isinstance(v, (int, float, list)) else v)
        EAL.save_loaded_asset(da)
        R['looks'][key] = {'asset': da_path, 'props': {k: (x if isinstance(x, (int, float)) else str(x)) for k, x in rec.items()}}
        looks[key] = da
        log('look', key, 'ok')
    return looks


# ---------------------------------------------------------------------------------------------------------------
# placement (traces + prop bounds, as Scripts/ImportPerkMachines.py)

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
    zs = []
    for dx in (-FOOT, 0.0, FOOT):
        for dy in (-FOOT, 0.0, FOOT):
            h = trace(w, u.Vector(x + dx, y + dy, top), u.Vector(x + dx, y + dy, bottom))
            if h is None:
                return None
            zs.append(h.z)
    return min(zs) if max(zs) - min(zs) <= FLAT else None


def clutter_boxes():
    out = []
    for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors():
        if a.actor_has_tag(TAG) or a.get_actor_label().startswith(GROUND_PREFIXES):
            continue
        if not isinstance(a, (u.StaticMeshActor, u.SkeletalMeshActor)) and not a.actor_has_tag(PERK_TAG):
            continue    # props only (not the player start, cameras, decals, volumes)
        try:
            o, e = a.get_actor_bounds(False)
        except Exception:  # noqa: BLE001
            continue
        if e.x <= 0 or e.y <= 0:
            continue
        perk = a.actor_has_tag(PERK_TAG)
        if max(e.x, e.y) > CLUTTER_MAX and not perk:
            continue
        out.append((o.x - e.x, o.x + e.x, o.y - e.y, o.y + e.y, o.z - e.z, o.z + e.z, a.get_actor_label(), perk))
    return out


def cluttered(boxes, x, y, z, r):
    for x0, x1, y0, y1, z0, z1, label, perk in boxes:
        rr = r + (120.0 if perk else 0.0)        # keep well away from the perk machines
        if x1 > x - rr and x0 < x + rr and y1 > y - rr and y0 < y + rr and z1 > z + 5 and z0 < z + 220:
            return label
    return None


def find_row(w, sl, fx, fy):
    boxes = clutter_boxes()
    R['clutter_props_considered'] = len(boxes)
    tried = []
    for ahead in (AHEAD, 330.0, 310.0, 300.0, 290.0, 280.0, 270.0, 260.0):
        for right_end in (ROW_RIGHT_END, -10.0, 10.0, 20.0, -20.0, 30.0):
            spots, why = [], None
            for i in range(len(ORDER)):
                lat = right_end - (len(ORDER) - 1 - i) * APART
                x, y = sl.x + fx * ahead - fy * lat, sl.y + fy * ahead + fx * lat
                z = flat_ground(w, x, y, sl.z + 300, sl.z - 600)
                if z is None:
                    why = 'not flat at %d' % i
                    break
                c = cluttered(boxes, x, y, z, FOOT + CLEAR)
                if c:
                    why = 'clutter %s at %d' % (c, i)
                    break
                d = math.hypot(sl.x - x, sl.y - y)
                for k in (60.0, 120.0, 180.0, 240.0):
                    c = cluttered(boxes, x + (sl.x - x) * k / d, y + (sl.y - y) * k / d, z, 20.0) if k < d - 60 else None
                    if c:
                        why = 'prop %s in the view line at %d' % (c, i)
                        break
                if why:
                    break
                for zz in (45.0, 90.0, 130.0):     # item, label and neon height, from the start at eye height
                    tgt = u.Vector(x, y, z + zz)
                    h = trace(w, u.Vector(sl.x, sl.y, sl.z + 70), tgt)
                    if h is not None and math.hypot(math.hypot(h.x - x, h.y - y), h.z - tgt.z) > 40:
                        why = 'hidden at %d (%d cm)' % (i, zz)
                        break
                if why:
                    break
                spots.append((x, y, z))
            if why is None and max(p[2] for p in spots) - min(p[2] for p in spots) > ROW_LEVEL:
                why = 'not one ground level %s (a debris pile?)' % [round(p[2], 1) for p in spots]
            tried.append({'ahead': ahead, 'right_end': right_end, 'why': why})
            if why is None:
                R['spot_search'] = tried
                return spots
    R['spot_search'] = tried
    raise RuntimeError('no flat clear row found ahead of the player start')


def place(looks):
    level = u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert level.load_level(MAP), 'load_level failed'
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    ss = u.get_editor_subsystem(u.EditorActorSubsystem)
    # hidden-phase save check: hide an existing display's item and neon as the respawn window does, save (PreSave
    # must restore the visible rest pose), reload, look; then the displays are replaced as usual
    old = [a for a in ss.get_all_level_actors() if a.actor_has_tag(TAG)]
    if old:
        def pivots(a):
            return {c.get_name(): c for c in a.get_components_by_class(u.SceneComponent)}
        probe = old[0]
        label = probe.get_actor_label()
        for n in ('ItemPivot', 'NeonPivot'):
            if n in pivots(probe):
                pivots(probe)[n].set_visibility(False, True)
        R['hidden_save_check'] = {'actor': label, 'hidden_before_save': not pivots(probe)['ItemMesh'].is_visible(),
                                  'saved': bool(level.save_current_level())}
        assert level.load_level(MAP), 'reload failed'
        back = next((a for a in ss.get_all_level_actors() if a.get_actor_label() == label), None)
        vis = bool(back and pivots(back)['ItemMesh'].is_visible())
        R['hidden_save_check']['item_visible_after_reload'] = vis
        if not vis:
            err('hidden-phase save check: %s item still hidden after save + reload' % label)
        w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()   # the reload made a new world
    for a in ss.get_all_level_actors():
        if a.actor_has_tag(TAG):
            ss.destroy_actor(a)
    perks_before = sorted((a.get_actor_label(), round(a.get_actor_location().x, 1), round(a.get_actor_location().y, 1))
                          for a in ss.get_all_level_actors() if a.actor_has_tag(PERK_TAG))
    starts = u.GameplayStatics.get_all_actors_of_class(w, u.PlayerStart)
    assert starts, 'no PlayerStart'
    sl, yaw = starts[0].get_actor_location(), starts[0].get_actor_rotation().yaw
    fx, fy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    R['player_start'] = {'location': [round(sl.x), round(sl.y), round(sl.z)], 'yaw': round(yaw, 1)}
    spots = find_row(w, sl, fx, fy)
    for key, (x, y, z) in zip(ORDER, spots):
        face = math.degrees(math.atan2(sl.y - y, sl.x - x))    # actor +X toward the start (the key light side)
        a = ss.spawn_actor_from_class(u.HoverPowerUpDisplay, u.Vector(x, y, z), u.Rotator(roll=0, pitch=0, yaw=face))
        a.set_actor_label('AFS PowerUp Trial %s' % key)
        a.tags = [u.Name(TAG)]
        a.set_folder_path(FOLDER)
        a.set_editor_property('look', looks[key])
        a.set_editor_property('loop_for_evaluation', True)
        a.set_editor_property('animate_in_editor', True)
        a.set_editor_property('seed', SEEDS[key])
        a.set_editor_property('show_label', True)
        a.set_editor_property('label', u.Text(LABELS[key]) if hasattr(u, 'Text') else LABELS[key])
        a.set_editor_property('label_height_cm', LABEL_HEIGHT[key])
        a.set_editor_property('label_size_cm', 9.0)
        try:
            a.rerun_construction_scripts()
        except Exception:  # noqa: BLE001
            pass
        R['placed'].append({'item': key, 'location': [round(x), round(y), round(z)], 'yaw': round(face, 1)})
    saved = level.save_current_level()
    R['map_saved'] = bool(saved)
    assert level.load_level(MAP), 'reload failed'
    after = [a for a in ss.get_all_level_actors() if a.actor_has_tag(TAG)]
    R['after_reload'] = [{'label': a.get_actor_label(), 'look': a.get_editor_property('look').get_path_name()
                          if a.get_editor_property('look') else None,
                          'loc': [round(a.get_actor_location().x), round(a.get_actor_location().y),
                                  round(a.get_actor_location().z)]} for a in after]
    perks_after = sorted((a.get_actor_label(), round(a.get_actor_location().x, 1), round(a.get_actor_location().y, 1))
                         for a in ss.get_all_level_actors() if a.actor_has_tag(PERK_TAG))
    R['perk_machines_unchanged'] = perks_before == perks_after
    R['perk_machines'] = perks_after
    if len(after) != len(ORDER) or not all(x['look'] for x in R['after_reload']):
        err('after reload: %s' % R['after_reload'])
    if perks_before != perks_after:
        err('perk machines changed!')


def main():
    import_neon_props()
    sprite_mats = build_sprite_materials()
    niagara = build_niagara(sprite_mats)
    looks = build_looks(niagara)
    old = FX + '/NS_PU_Live_PopSmoke'      # replaced by NS_PU_Live_PopPuff (2026-10-31), no longer referenced
    if EAL.does_asset_exist(old):
        R['deleted_old'] = EAL.delete_asset(old)
    EAL.save_directory(LIVE, only_if_is_dirty=True, recursive=True)
    EAL.save_directory(FX, only_if_is_dirty=True, recursive=True)
    if PLACE:
        place(looks)
    # the Nuke has no echo shell any more (fix round 2026-10-31): drop its instance once nothing references it (the
    # displays placed before this round carried it on a shell component, so this runs after they are replaced)
    gone = [LIVE + '/Nuke/MI_PU_Live_Nuke_Shell_Echo']
    if not POP_PUFF:       # the puff is off: its system first (it references the material), then the material
        gone += [FX + '/NS_PU_Live_PopPuff', FX + '/M_PU_LiveSmoke']
    u.SystemLibrary.collect_garbage()     # the replaced displays' pool components still held the puff system
    for old in gone:
        if EAL.does_asset_exist(old):
            refs = [str(x) for x in EAL.find_package_referencers_for_asset(old, False) if str(x) not in gone]
            R.setdefault('removed', {})[old] = {'referencers': refs}
            if not refs:
                R['removed'][old]['deleted'] = EAL.delete_asset(old)
                f = u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()) + old[len('/Game/'):] + '.uasset'
                R['removed'][old]['file_left'] = os.path.exists(f)
                if os.path.exists(f):
                    warn('%s: deleted in the editor but %s is still on disk' % (old, f))


try:
    main()
except Exception as e:  # noqa: BLE001
    err('%s\n%s' % (e, traceback.format_exc()))
finally:
    os.makedirs(OUT, exist_ok=True)
    with open(OUT + '/author_receipt.json', 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    log('DONE ok=%s errors=%d warnings=%d placed=%d' % (R['ok'], len(R['errors']), len(R['warnings']), len(R['placed'])))
    u.SystemLibrary.quit_editor()
