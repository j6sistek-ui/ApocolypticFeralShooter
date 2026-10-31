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

Lesson: the Python-driven motion (sparks, embers, bolts, heartbeat echo) is preview only. The shipping version is the
in-engine display actor (C++ `AHoverPowerUpDisplay`, being built 2026-10-31) with real Niagara or C++ particles,
placed in NYC Exploration so the owner can watch it live. When that lands this file gets its parameters.

## Parked for a later trial

The GIF variants (round 2 looks 5-23, Nuke N1-N6) are kept: frames and GIFs under
`D:/AFS_Comparisons/PowerUps_20261031/Styles/` (local), definitions in the scripts above.
