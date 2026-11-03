# Weather (Dreamrise Multiplayer Dynamic Weather System in NYC Survival)

Owner 2026-11-01: "put the weather in too ... ahead of anything else, because I want to see how it works"
(earlier: "Menu toggle, rain/snow"). Built 2026-11-01; proof and video in `D:\AFS_Comparisons\Weather_20261101\`.

## What it is

The Fab pack **Multiplayer Dynamic Weather System** (Dreamrise, V4), kept as its own project at
`M:\MultiplayerDynamicWeather` (UE 5.8, blueprint-only; only plugin Bridge, which no pack asset references). That
project is the read-only source. Its content lives in AFS at the same path, `/Game/MultiplayerDynamicWeatherSystem`:
130 packages, 120 MB (126,329,124 bytes): 7 Blueprints, 2 widgets, 1 data table, 8 structs, 3 enums, 1 material
parameter collection, 15 materials + 5 instances + 10 functions, 5 Cascade particle systems (no Niagara), 6 sound
waves + 6 cues + 2 attenuations, 34 textures, 4 static meshes, a UE4 mannequin with 7 anims and its anim blueprint,
6 curves, the showcase map `Map/L_Showcase` and 2 landscape layer infos.
Dependencies outside the folder: engine content and engine modules only (`/Engine/EngineSky/BP_Sky_Sphere`, sky and
volumetric-cloud noise textures, engine material functions, basic shapes; `/Script/` Engine, UMG, Landscape,
Foliage, NavigationSystem, PhysicsCore, AnimGraph, ClothingSystemRuntimeNv...). No plugin content, nothing else
from the source project. All 129 non-map packages load in AFS with no errors; no redirectors. No readme or licence
file ships with the pack (Fab standard licence).

### Redo the copy

The target folder must not exist first (if it does, it is the migrated pack: do not copy over it).

    cp -r /m/MultiplayerDynamicWeather/Content/MultiplayerDynamicWeatherSystem /m/UnrealProjects/AFS/Content/

Same path, so every internal reference stays valid; no fix-up needed. Then run `Scripts/ImportWeather.py`
(below). Never open-and-save the source project.

## How the pack works

- **`Blueprints/BP_MultiplayerDynamicWeatherManager`** is the whole system, one actor per level. It owns:
  - a day/night clock (`Current Time`, `Day Length` / `Night Length` minutes, `Animate Day/Night Cycle`) that
    ROTATES the sun it is given (`Sun light`, `Sun Inclination`, `Sun Rotation`) and recolours it from curves;
  - weathers from **`DT_Weather`** (rows Sunny 37.5 %, Cloudy 37.5 %, Rainy 25 %; each with Duration 60 s,
    Transition Speed 60 s, Rain Phase, Ground Wetness, Thunder? + interval, and per season fog density / colours,
    sun intensity, shaft bloom, shaft occlusion darkness, sky light day/night, cloud density, wind). With
    `Enable Weather Changes` it picks a random row every Duration and blends over Transition Speed;
  - seasons (`E_Seasons` Spring..Winter, `Enable Season Changes`: transition mode, day/month mode or off);
  - it WRITES the sun / sky light / height fog / sky sphere (`BP_Sky_Sphere_Modulated`, engine sky sphere) /
    volumetric clouds (`M_VolumetricClouds`) it is given, and `ParameterCollection/MPC_DynamicWeatherSystem`
    (Rain phase, Ground Wetness, Wind Intensity, Season) that the pack's own materials read (wet landscape, wind
    on foliage, season blend);
  - events (server reliable / multicast: Change Weather, Toggle Change Weather(row, speed), Toggle Season,
    Toggle Thunder, Set Time) and it calls **`BI_MultiplayerDynamicWeatherSystem`** (On Rain, On Weather Changed,
    On Season Changed) on every actor that implements it (Get All Actors With Interface).
- **Precipitation is not in the manager.** The receiving pawn (`Character/ThirdPersonBP/ThirdPersonCharacter`)
  carries Cascade `Rain` (P_Rain) and `Snow` (P_Snow) components and a rain audio component: On Rain turns its
  rain emitter on and fades `Rain_Cue` in; On Season Changed(Winter) turns snow on. Each rain drop's collision
  event spawns a `P_Rain_Ground` splash. Snow is therefore the Winter season, not a weather row.
- `BP_Thunder`: spawned by the manager on a ground point ~25,000 cm away in Rainy weather: bolt sprite
  (P_Thunder), point-light flash, ThunderHit / Thunder cues. `BP_Fire`: campfire prop.
- `Widget/W_Screen` + `W_MDWS_Time`: the showcase HUD (clock, date, weather name).
- `L_Showcase` sets up: the manager wired to its own directional light, sky light, height fog, VolumetricCloud and
  sky sphere; 10 s days / 2 s nights, seasons 60 s, weather changes on; the mannequin game mode; E = time x10.

## What AFS uses, and why not the manager

Placed in NYC, the manager would take over NYC's sun (rotation, colour, intensity 2.75 for Sunny vs NYC's 5),
sky light and fog, and wants its own sky sphere and clouds: the map would not look like today when Clear, and a
second sky would fight NYC's SkyAtmosphere. So AFS drives the pack's **parts** from its own actor and leaves the
map's lighting to the map:

**`AHoverWeather`** (`Source/HoverFlight/HoverWeather.h/.cpp`), one per level, placed in `L_NYC_Survival` as
"AFS Weather" (persistent level, no light/sky/fog actor added). Weathers (`EHoverWeatherKind`):

| Weather | Lighting (multipliers on NYC's own values) | Precipitation, surface, sound |
|---|---|---|
| Clear (default) | none: the captured values, exactly | none |
| Cloudy | pack Cloudy/Sunny ratios: sun 0.64, sky light 0.88, fog x2 | wind 1.5 (MPC) |
| Rain | pack Rainy/Sunny, lifted to stay playable: sun 0.22, sky 0.6, fog x4, grey fog colour, flat overcast sky | rain near + far, splashes, wet streets, rain loop + wind |
| Storm | Rain darker (sun 0.14, fog x5) | + BP_Thunder strikes every 6-14 s with a sky flash |
| Snow | pack Winter under an overcast sky: sun 0.55, fog x3.5 white | snowfall, snow cover, wind loop |

- **Lighting:** on the FIRST weather change it captures NYC's sun (the atmosphere-sun directional light,
  `DirectionalLight4`; the second directional light follows the same factor), `SkyLight2`, `ExponentialHeightFog`
  and `SkyAtmosphere2` (all in the PostApocalypticCity `Lighting_Main` sublevels, so found at runtime, not
  referenced from the map). It scales sun intensity, shaft bloom, sun volumetric scattering and fades the sun's
  light-shaft occlusion (which drew hard rays in the haze), sky light, fog density + colour, atmosphere Rayleigh /
  Mie / Mie anisotropy. Clear writes back the exact captured values; before the first change nothing is touched.
  A captured-scene sky light is recaptured once a second during a blend and at its end.
- **Blend:** 6 s by default (`TransitionSeconds`; the pack's own is 60 s), smooth-stepped. Rain / snow start with
  the blend; when they stop, drops already falling finish and whatever is left is removed at the end of the blend.
- **Precipitation** follows the view (camera manager), each kind in a near volume that is traced against the city
  (no rain or snow under the roof Vexa stands under, rain splash events) and a far volume that is not (cheap; its
  drops expire around street level): rain near 7 m / far 26 m ahead of the camera, snow near 2 m / far 10 m.
  All four also lead the VIEW TARGET's smoothed horizontal velocity (Vexa running or gliding; a still camera actor
  gets none): rain by 0.6 s, snow by 1.5 s, at most 15 m (`RainLeadSeconds`, `SnowLeadSeconds`, `MaxLead`), so a
  running player meets air that already holds drops / flakes at eye level.
  Assets are AFS-tuned copies of the pack's Cascade systems in `/Game/HoverPrototype/Weather/`: `P_Rain_AFS`
  (1,800 drops/s from 12 m above the camera) / `P_Rain_AFS_Far` (2,200/s from 20 m, 1.25 s life), longer streaks;
  `P_Snow_AFS` (400 flakes/s over 18 x 18 m, spawned 2.5-11 m above the camera) / `P_Snow_AFS_Far` (850/s over
  32 x 32 m, spawned 1.5-12 m above the camera, 2.5-3.5 s life), 2.5-6 cm flakes. Spawning across the height (not
  at one fixed height) is what keeps the air full where a volume has just moved to. The pack's originals are the
  fallback.
  **Lens fade (fix round 2, 2026-11-03):** with the near snow 2 m ahead and spawned through the full height, flakes
  passed right in front of the lens and drew as big soft white discs, up to ~100 px (review: `fix1/frames/
  v05_to_snow_player_0059.png`, `_0060.png`); rain drops did the same as wide soft pillars. The copies no longer use
  the pack's sprite material `M_RadialGradient` (lit translucent, opacity = particle alpha x radial gradient) but
  `M_WeatherFlake`, a copy of it whose opacity also fades with the PARTICLE's distance from the camera (its centre,
  so a flake fades as a whole; scalar parameters `NearFadeStart` / `NearFadeEnd`): snow 0 inside 1 m, full from 2 m;
  rain through the instance `MI_WeatherRainDrop`, 0 inside 1.5 m, full from 3.5 m (its 60-90 cm streaks were still
  20-25 px wide soft pillars with the snow's 1-2 m). No spawn change and no C++ change: the spheres it empties are a
  tiny part of the volumes (snow flakes in view within 15 m / 7 m standing 391 / 75 vs fix round 1's 426 / 68, run
  to run noise; live flakes ~1,000 + 2,590 as before). The pack's `M_RadialGradient` stays as shipped (its own P_Rain
  / P_Snow still use it). Receipts `D:/AFS_Comparisons/Weather_20261101/fix2/`: `lens_before_after.png` (the
  reviewer's two frames, a rain street frame and the snow / rain player stills, fix1 | fix2),
  `lens_before_after_moving.png`, `lensdisc_fix1.json` / `lensdisc_fix2.json` (still-camera segments: pixels 20
  levels brighter than the median of the +-3 neighbouring frames, blobs >= ~20 px across: snow blend v05 32 frames
  with one, max ~108 px -> 16, max 48 px (a corner streak left from the storm, no disc); snow street 19, max 56 ->
  8, max 32; rain streaks are long, so their numbers are streak lengths: frames with a >= 40 px blob v03 30 -> 6,
  v04 23 -> 9), `pass1/` (the first pass, rain at 1-2 m), `import_receipt.json`, `verify_flake_fresh.json` (a fresh
  editor process: the snow copies draw with `M_WeatherFlake`, the rain copies with `MI_WeatherRainDrop`),
  `import_files_written.txt` (the map and the seven `/Game/HoverPrototype/Weather/` assets, nothing else).
  `fx.MaxCPUParticlesPerEmitter` (a global, 1000 by default, which capped the first snow at exactly
  1,000 flakes) is raised to 6000 only while rain or snow runs and put back to its old value at the end of the
  blend to a dry weather and in EndPlay (log `HOVER_WEATHER particle cap ...`; `DescribeState` prints `cap=`).
  Splashes: the pack's `P_Rain_Ground` on the near rain's collision events, at most 40/s within 18 m (was 90/s
  within 30 m: ~1 ms of game thread on its own, see Cost).
- **Wet streets / snow cover:** NYC's materials do not read the pack's MPC (wiring the pack's MF_ functions into
  every NYC master material is the expensive route, not taken). Instead `M_WeatherSurface` (deferred decal, built
  by `ImportWeather.py`) is projected straight down in a 300 x 300 x 60 m box around the camera: up-facing surfaces
  only (normal from screen derivatives), the pack's perlin noise for patches; `Wetness` = dark + glossy,
  `SnowCover` = white + rough. It fades with horizontal distance from the camera, full to 90 m and gone at 145 m
  (`SurfaceFadeStart` / `SurfaceFadeEnd` -> material `FadeStart` / `FadeEnd`), so no edge slides with the view
  (the first build's 90 m box ended in a hard square edge ~45 m out).
  Characters (and what is attached to them) must not get the world-aligned layer (it would swim on them), but
  must keep blood / impact decals: while the layer shows, their meshes draw into custom depth
  (`SetRenderCustomDepth`, only on meshes that were not already doing so, restored when the layer goes) and
  `M_WeatherSurface` drops every pixel whose custom depth equals the scene depth (the visible surface is a
  character). A character behind a wall does not mask the wall. Needs `r.CustomDepth` 1 and custom depth rendered
  before the DBuffer decals (`r.CustomDepth.Order` 2, the default with `r.DBuffer` 1; both checked in the proof).
  Other decals (`SortOrder` above the layer's -10) land on characters as normal.
- **Sound:** the pack's `Rain_Cue` and `Starter_Wind05_Cue` loops (2D, volume follows the blend), thunder from
  `BP_Thunder`. The NYC wind bed from the 2026-10-31 audio pass keeps playing under them.
- **MPC:** Rain phase / Ground Wetness / Wind Intensity / Season are set too (pack materials only).

## Changing the weather

- **F6 / D-pad Up test-settings menu:** row "Weather: < Clear / Cloudy / Rain / Storm / Snow >", the last row,
  shown only when the level has an `AHoverWeather`; it opens on the current weather and applies on Apply
  (A / Enter), blending over 6 s once play resumes; Cancel discards it.
- **Exec (tests):** `Weather Rain` (blend 6 s), `Weather Snow 0` (instant), `Weather Storm 3`, `Weather` (report).
  Logs `HOVER_WEATHER ...`.
- **Code / Blueprint:** `AHoverWeather::FindWeather(this)->SetWeather(EHoverWeatherKind::Rain, Seconds)`;
  `GetWeather`, `DescribeState`, `GetLiveParticleCount`. `StartWeather` on the placed actor (Clear) sets the
  weather at BeginPlay; per-weather values are the editable `Looks` map.

## Scripts

- `Scripts/ImportWeather.py` (nullrhi): builds `M_WeatherSurface`, `M_WeatherFlake` + `MI_WeatherRainDrop` (the
  near-camera fade), the tuned particle copies, places/re-wires the one actor in `L_NYC_Survival`, saves, reloads
  and checks the actor count (4,429 -> 4,430; re-runs keep 4,430) and each copy's material. Re-runnable.
- `Scripts/ProveWeather.py` (RenderOffscreen PIE): stills from Vexa's view, a raised street camera and a low
  close camera for Clear / Rain / Storm (with a thunder flash) / Snow / Cloudy / Clear again, through the real
  F6 key path (F6, Up, Right, Enter) and the exec; a blood decal (`MI_BloodDecal`) on Vexa and on a zombie in rain
  and snow; the moving-camera test in rain and snow (Vexa still / running with scripted W + L3 / camera turning
  90 deg/s / running a circle, drops and flakes within 15 m and 7 m inside a 40 deg cone counted every frame);
  `fx.MaxCPUParticlesPerEmitter` read before, during and after; video frames. `WEATHER_QUICK=1` stills only;
  `WEATHER_BASELINE=1` the Clear stills without the actor; `WEATHER_MOVE=1` only the moving test (`move.json`,
  with `WEATHER_LEGACY=1` the pre-fix placement); `WEATHER_PERF=1` the cost windows with the player moving
  (`perf.json`); `WEATHER_OUT` the output folder.
- `Scripts/MakeWeatherVideo.py <root> [<out>]` (plain Python + Pillow + ffmpeg): `weather_nyc.mp4` (with the
  moving-camera segments), `weather_contact_sheet.png` (plus a moving row and a blood-decal row), `clear_check.json`
  (pixel difference of Clear against the pre-weather baseline).

## Cost (offscreen PIE, 1280x720, this machine; rough)

**Fix round 1 (2026-11-03), player moving.** Receipts in `D:/AFS_Comparisons/Weather_20261101/fix1/`:
`perf/perf.json` (`ProveWeather.py` with `WEATHER_PERF=1`: Vexa runs a circle with scripted W + L3 and the camera
turning 40 deg/s, from the same start every window; Clear / Rain / Clear / Snow / Clear / Storm twice, instant
switches, 4 s settle + 4 s window; `stat unit` game thread and GPU through `HoverAuthoring.GetThreadTimesMs`, one
`profilegpu` per window in `logs\perf.log`). No other Unreal, cook or game process was running for that run (a
Codex agent session was open; a 140 GB robocopy M: -> D: and a Call of Duty session it ran had ended; earlier
runs that overlapped them are kept as `perf_*` for the record). Window-to-window noise is about +-1 ms on the game
thread, so the deltas are against the neighbouring Clear windows and read as rough:

| Weather | Live particles (near traced + far) | Game thread vs Clear | GPU (stat unit) vs Clear |
|---|---|---|---|
| Clear | 0 | 13.4-15.1 ms (mean 14.3) | 9.94-10.02 ms |
| Rain | ~1,120 + 2,820 drops, splashes <= 40/s | +3.7 (after the first window) / +2.0 ms | +0.46 ms |
| Storm | same + a strike every 6-14 s | +2.1 / +3.1 ms | +0.47 ms |
| Snow | ~1,000 + 2,550 flakes | +1.3 / +1.2 ms | ~0 |

The real frame (22-29 ms mean in every window, Clear included) is the offscreen harness and editor, not the
weather. Render / RHI thread times read 0 through `GetThreadTimesMs` (not filled in this mode).
What changed to get there (same harness, before): snow was +2.2 to +3.7 ms (1,100 traced + 3,950 far flakes; the far
ones spawned at eye level spent most of their life under the street) -> far 1,300 -> 850/s spawned 1.5-12 m up,
near 450 -> 400/s. Rain was ~+2.5 ms; an in-run A/B (`WEATHER_PERF_SEQ='Clear,Rain,Clear,Rain/nosplash,...'`,
`perf_splash_ab\`) put the 90/s splashes at ~1 ms on their own (rain +2.5 with, +1.45 without) -> 40/s within 18 m,
and the traced drops 2,200 -> 1,800/s.

**First build (2026-11-01), camera still.** `D:\AFS_Comparisons\Weather_20261101\perf.json` and
`logs/final_perf.log`; the machine was busy with an unrelated SpaceSurvival cook writing ~38 MB/s to D:, so
absolute times are inflated:

| Weather | Live particles (near traced + far) | Real frame, mean | GPU frame (one profilegpu) |
|---|---|---|---|
| Clear | 0 | 61.2 / 60.9 / 61.1 ms | 59.2 / 60.4 / 59.7 ms |
| Rain | ~2,150 + 2,820 drops, splashes <= 90/s | 64.7 ms (+3.6) | 62.7 ms (+2.5) |
| Storm | same + a strike every 6-14 s | 64.7 ms (+3.6) | 64.1 ms (+4) |
| Snow | ~2,090 + 4,740 flakes | 60.7 ms (+0) | 61.7 ms (+1.5) |

On an unloaded machine (first proof, the pack's own 500 drops/s x 2): real frame 17.0 -> 20.3 ms, GPU 8.5 -> 9.2 ms.
Before the snow was split, 6,000 all-traced flakes cost ~3x the rain in the same run (59.6 vs 22.1 ms): Cascade's
per-particle collision traces are the expensive part, hence one traced volume near the camera only.

Clear costs nothing (no particles, decal hidden, nothing ticks but a pointer check). Most of the rain/snow cost is
CPU: Cascade traces every near drop and flake against the city each frame, and the rain's splashes.

## Known limits and open choices

- No day/night cycle, seasons, sky sphere or volumetric clouds from the pack (they would replace NYC's sky).
  "Cloudy" is a lighting change with a greyer sky, not visible clouds.
- Only the near rain / snow volumes are traced: far away, drops and flakes also fall under awnings and bridges.
- The surface decal does not follow vertical surfaces (no wet walls / no snow on ledges' faces), and dead-leaf
  decals in NYC draw on top of the snow (they read as leaves on snow).
- The pack's own 60 s transitions and random weather cycling are not used; the menu choice stays until changed and
  is not saved: every load of NYC Survival starts Clear (`StartWeather` on "AFS Weather" changes that).
- Falling snow reads lightly from the raised street camera and even from Vexa's view (2.5-6 cm flakes); the snow
  cover carries it. Denser snow costs CPU in the traced volume.
- Moving camera (fix round 1, `fix1\prove.json` "move", flakes / drops within 15 m inside a 40 deg cone, mean):
  snow standing 426 / running 349 (-18 %) / turning 90 deg/s 384 (-10 %) / running a circle 252 (-41 %); before the
  fix (`fix1\legacy_move\move.json`) 425 / 303 (-29 %) / 303 (-29 %) / 96 (-77 %). Rain 170 / 219 / 157 / 136
  (before 221 / 345 / 195 / 174: fewer traced drops after the cost pass, same ratios). The circle runs along the
  building by the spawn, where much of the view is wall and fence, so part of its drop is the place, not the lead.
- Rain is lit translucency: in Storm it is darker and less visible than in Rain.
- Weather is per level: only NYC Survival has the actor (test pads untouched). Single-player: `AHoverWeather` does
  not replicate (the pack's multiplayer events are not used).
