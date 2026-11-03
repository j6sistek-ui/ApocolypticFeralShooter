# AFS: how the power-up looks are built (so they can be changed later)

The design and the owner's decisions are in `POWERUP_CATALOG.md`. This file says where the logic lives and how to
re-run it. All scripts are in this repo; meshes, textures, materials and maps are in the owner's local Content.

## Decided (2026-10-31)

| Item | Look | Last 5 s before despawn |
|---|---|---|
| Every power-up except the Nuke | Busted Neon (look 13) + Toxic Aura (look 21) + a touch of Blood Relic (look 6) | Heartbeat pulse (look 20) |
| Nuke | N4 shake throughout; N1 sparks alternating with N2 pops over its 30 s life | Heartbeat and arc crawl (look 16) ease in together and speed up |

A dropped power-up lives 30 s (`AZE_PowerUpPickup::InitialLifeSpan`, vendor default).

### The ingredients, by look (parameters in `Scripts/PowerUpStyleRecipes2.py`, entries `'n': 6, 13, 16, 20, 21`)

- **13 Busted Neon:** a storefront neon tube of the item's icon (cross, trefoil) floating about 92 cm above the item,
  facing the camera on yaw, bobbing 2 cm at 0.5 Hz; neon material with a lit tube and one dead tube stuttering; a
  point light in a deeper version of the item colour with a buzz flicker, no shadows.
- **21 Toxic Aura:** three additive shells of the item inflated 2, 6 and 11 cm (`M_PU_Shell`), the item colour,
  intensities 0.7 / 0.4 / 0.18, 3D-noise mist boiling upward, wobble, a 0.45 Hz pulse; the outer shell fades with
  height; drifting motes; a key light pulsing.
- **6 Blood Relic (the "touch"):** the item skin (`M_PU_ItemFX2`) darkened slightly with a red ember rim breathing at
  about 0.9 Hz, and a thin red mist shell 1.5 cm out (a second at 5 cm, weaker); fire-flicker light.
- **20 Heartbeat:** a lub-dub at 1.25 Hz: the item swells about 12 %, the emblem/seam/rim glow flashes, an echo
  shell grows from 1.0 to 1.55 and fades, streaks on the beat.
- **16 Arc Crawl:** crawling electric filaments in the item skin (3D noise, jumping about 14 times a second), arcs
  biased to the silhouette on a shell, jagged bolts and sparks, the light stuttering with each discharge.
- **Nuke N1 / N2 / N4** (`Scripts/RecordNukeSignatures.py`, `look_N1`, `pop` + `look_N2`, `look_N4`): N1 = irregular
  spark bursts from the seams and cap (6-13 sparks, cooling white to orange under gravity) plus single-spark dribble;
  N2 = micro-detonation pops on the casing (a white-hot core, a soft blast glow, a 4-6 ray star, dark smoke puffs, 3-6
  sparks, a small casing jolt); N4 = Geiger-like stutter ticks (single and triple) flashing the trefoil and seams
  white-hot with a star glint and a casing shudder of about 2.4 cm. In those GIFs the pace is compressed into a
  2.4 s loop; the real version spreads them over 30 s.

Shared masters (local Content, `/Game/HoverPrototype/PowerUps/Styles/Shared/Materials`): `M_PU_ItemFX2` (the item's
own maps plus seam glow, emblem glow, veins, arcs, swirl, rim, Geiger flicker, pulse) and `M_PU_Shell` (an additive
shell hugging the item: fresnel edge, noise mist, arcs, height fade, wobble). Look recipes use colour tokens: `$c` the
item colour, `$c2` a pale highlight.

## Pipeline scripts

| Script | What it does | Run with |
|---|---|---|
| `Scripts/Blender/RenderPropSheet.py` | renders a folder of GLBs to judge new models | Blender `-b --python ... -- <glb folder> <out>` |
| `Scripts/Blender/CleanPowerUps.py` | cleans the owner's Tripo models: strays, pivot, facing, size (45 / 60 cm), textures; list `MODELS` | Blender `-b --python ...` |
| `Scripts/ImportPowerUps.py` | imports cleaned models into `/Game/HoverPrototype/PowerUps/Meshes/` | UnrealEditor-Cmd, nullrhi |
| `Scripts/PowerUpStyleRecipes.py`, `PowerUpStyleRecipes2.py` | every look as data (round 1 and round 2) | imported by the others |
| `Scripts/AuthorPowerUpStyles.py`, `AuthorPowerUpStyles2.py`, `MakePowerUpStyleTextures.py` | build the materials, instances and Niagara copies for the looks | UnrealEditor-Cmd |
| `Scripts/PreviewPowerUpStyles2.py`, `RecordPowerUpGifs.py`, `AssemblePowerUpGifs.py`, `RecordNukeSignatures.py` | the showcase renders and GIFs (motion driven from Python: preview only) | UnrealEditor-Cmd, RenderOffscreen |

| `Scripts/AuthorPowerUpLive.py` | **the shipping look**: builds the live materials, Niagara copies and `DA_PU_Live_<Item>` settings, places the displays in NYC Exploration (every tunable is a named value at the top) | UnrealEditor-Cmd, nullrhi |
| `Scripts/CapturePowerUpLive.py` | stills of the live displays (`PU_LIVE_PLAN=fix` for the short set) | UnrealEditor-Cmd, RenderOffscreen |
| `Scripts/Blender/MakePowerUpLiveProps.py` | the neon cartridge icon mesh for Max Ammo | Blender `-b --python ...` |

Lesson: the Python-driven motion (sparks, embers, bolts, heartbeat echo) of the GIF rounds was preview only. The
shipping version is the live display actor below.

## The shipping version: live display actor (built 2026-10-31)

C++ `AHoverPowerUpDisplay` (`Source/HoverFlight/HoverPowerUpDisplay.*`). It is purely visual, so the real pickup can
attach it later; that pickup must set `bLoopForEvaluation = false`. It handles:
- spin, bob and casing shudder (new target 30 times a second)
- the Geiger ticks, pops and spark schedule
- the neon icon with its buzz and dead-tube stutter
- the aura shells
- the last-5-second warning: the heartbeat, plus the arc crawl on the Nuke

The settings live in `/Game/HoverPrototype/PowerUps/Live/<Item>/DA_PU_Live_<Item>`, written by
`AuthorPowerUpLive.py`. Timing, light and warning values are read every frame; mesh, material, shell and Niagara
changes need a map reload or a re-run of the script.

**Built from:**
- **Niagara:** the sparks, single sparks, pop sparks and motes, all copies of the engine DirectionalBurst and
  RadialBurst templates. `UHoverAuthoring::ConfigurePowerUpLiveEffect` writes their emitter scripts so the authored
  counts hold (before that fix every burst spawned 20).
- **Camera-facing planes:** the pop core, glow, rays and glint.
- **Material time:** the shells, blood rim and arcs.

**Live in NYC Exploration:** outliner folder `AFS_PowerUps`, tag `AFS_PowerUpTrial`. The three displays stand in a
row 1.5 m apart, about 3 m ahead of the player start: NUKE, MEDKIT, MAX AMMO. In the editor, turn on Realtime
(Ctrl+R) and keep the editor focused, or press Play.

**All items:**
- Hover 30 cm, bob 2 cm at 0.5 Hz.
- Life 30 s, pop-in 0.35 s, fade 0.5 s, then (evaluation only) hidden 2 s and loop.
- Warning: the last 5 s.
- Heartbeat swell 12 %, dub at 0.6 of the lub.

**Nuke:**
- Twice the size (item_scale 2, 2026-11-03, owner: "should be twice as big"): 90 cm tall from 30 cm up, label at
  152 cm. The display scales the key light offset and radius with item_scale and its intensity linearly (4 cd reads as
  8 cd). Pop, glint and spark sizes are world cm and went up 1.5x, not 2x.
- Spin 30°/s, key light 4 cd, emblem and seam glow 1.5. No echo shell: it read as a floating ghost lid.
- Geiger ticks every 1.6 s on average (0.35-3.5 s apart); 30 % are triples, 0.09 s apart. Each tick flashes 0.07 s
  (trefoil +9, seams +7, capped at 8 / 7 when it lands on a heartbeat flash), shudders 2.4 cm and adds a 13 cm glint.
- One event every 1.6-2.6 s from 1.2 s, alternating spark burst and pop (was 2.4-3.6 s from 1.6 s; 2026-11-03,
  "a little bit more sparky on the idle phase").
- Sparks and pops start on 84 casing points measured on the mesh (`casing_points()`: the seam rings at 20 / 50 / 80 %
  height cut from the mesh, plus 12 on the lid), picked on the side the viewer sees (within 75°).
- Spark bursts: 6 or 7, with a 13 at 50 % (was 35 %). A single spark about every 0.8 s (was 1.3 s). Cone 55-65°,
  speed 140-330, life 0.45-0.95 s, sprites 0.38-0.6 x 1.2-1.8 cm.
- Pops: core 5 cm, glow 27 cm, 4-6 rays (18 x 1 cm), light 12 cd, 3 or 6 sparks, jolt 1.2 cm. The decided
  dark smoke puff is **off** (`POP_PUFF = False`): it rendered but could not be made to read against the black
  casing.
- Warning: heartbeat and arc crawl share one 3 s ease-in. The beat speeds up from 1.0 to 2.4 Hz (power 1.4), with a
  glow flash of 1.8.
- Arc crawl: intensity 10 on the skin and 7 on the shell. Its rate rises from 5 to 22 and its coverage from 0.30 to
  0.50. The light stutters 2 to 14 times a second.

**Medkit and Max Ammo:**
- Spin 25°/s, key light 3 cd pulsing at 0.45 Hz.
- Neon icon 92 cm up. The lit tube is 12 with a 14 Hz buzz at 0.12. The dead tube is 0.25 off / 8 on, stuttering in
  bursts of 0.15-0.6 s every 0.7-2.6 s. Neon light 5 cd, radius 340 cm.
- Aura shells at 2 / 6 / 11 cm, intensity 0.7 / 0.4 / 0.18. Max Ammo's haze is 0.7x.
- Blood touch: a red mist shell 1.5 cm out at 0.45, and a red rim of 1.3 (Max Ammo 1.1) breathing at 0.9 Hz.
- Motes: 5 every 1.1 s.
- Heartbeat speeds up from 1.25 to 1.55 Hz, with a 1.5 s ease-in and a glow flash of 1.6. Echo shell up to 1.15x at
  0.35.

**Item colours:**
- Medkit: red (1, .045, .035), neon cross.
- Max Ammo: orange amber (1, .42, .03), neon of three cartridges (the middle tip is the dead tube).

**Open (owner's eye):**
- No smoke puff on the pops.
- Max Ammo's haze is still a little yellow on one edge.
- The Nuke reads small from the start: doubled 2026-11-03 (stills `D:/AFS_Comparisons/PowerUps_20261031/Live/
  stills_nuke2x/`), owner to judge live.
- Each tick that lands on a heartbeat is capped, so it shows less.

## Parked for a later trial

The GIF variants (round 2 looks 5-23, Nuke N1-N6) are kept: frames and GIFs under
`D:/AFS_Comparisons/PowerUps_20261031/Styles/` (local), definitions in the scripts above.
