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
  drops expire around street level): rain near 7 m / far 26 m ahead of the camera, snow near 5 m / far 26 m.
  Assets are AFS-tuned copies of the pack's Cascade systems in `/Game/HoverPrototype/Weather/`: `P_Rain_AFS` /
  `P_Rain_AFS_Far` (2,200 drops/s each, longer streaks; far 1.25 s life), `P_Snow_AFS` (450 flakes/s over
  18 x 18 m) / `P_Snow_AFS_Far` (900/s over 32 x 32 m, 4.5-6 s life), 2.5-6 cm flakes. The pack's originals are
  the fallback. `fx.MaxCPUParticlesPerEmitter` is raised to 6000 on the first change (Cascade's default 1000 capped
  the first snow at exactly 1,000 flakes).
  Splashes: the pack's `P_Rain_Ground` on the near rain's collision events, at most 90/s within 30 m.
- **Wet streets / snow cover:** NYC's materials do not read the pack's MPC (wiring the pack's MF_ functions into
  every NYC master material is the expensive route, not taken). Instead `M_WeatherSurface` (deferred decal, built
  by `ImportWeather.py`) is projected straight down in a 90 x 90 x 30 m box around the camera: up-facing surfaces
  only (normal from screen derivatives), the pack's perlin noise for patches; `Wetness` = dark + glossy,
  `SnowCover` = white + rough. Characters and what they hold opt out of decals while it shows (a world-aligned
  layer would swim on them) and get their own setting back after.
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

- `Scripts/ImportWeather.py` (nullrhi): builds `M_WeatherSurface`, the tuned particle copies, places/re-wires the
  one actor in `L_NYC_Survival`, saves, reloads and checks the actor count (4,429 -> 4,430). Re-runnable.
- `Scripts/ProveWeather.py` (RenderOffscreen PIE): stills from Vexa's view, a raised street camera and a low
  close camera for Clear / Rain / Storm (with a thunder flash) / Snow / Cloudy / Clear again, through the real
  F6 key path (F6, Up, Right, Enter) and the exec; video frames; frame-time windows; `profilegpu`.
  `WEATHER_QUICK=1` stills only (~2 min); `WEATHER_BASELINE=1` the Clear stills without the actor.
- `Scripts/MakeWeatherVideo.py` (plain Python + Pillow + ffmpeg): `weather_nyc.mp4`, `weather_contact_sheet.png`,
  `clear_check.json` (pixel difference of Clear against the pre-weather baseline).

## Cost (offscreen PIE, 1280x720, this machine; rough)

Receipts: `D:\AFS_Comparisons\Weather_20261101\perf.json` (`ProveWeather.py` with `WEATHER_PERF=1`: Clear / Rain
/ Clear / Snow / Clear / Storm twice, 4 s windows, instant switches) and `logsinal_perf.log` (`profilegpu`).
The machine was busy with an unrelated SpaceSurvival cook writing ~38 MB/s to D:, so absolute times are inflated;
compare neighbouring windows (second pass, after the first pass settled):

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
CPU: Cascade traces every near drop and flake against the city each frame.

## Known limits and open choices

- No day/night cycle, seasons, sky sphere or volumetric clouds from the pack (they would replace NYC's sky).
  "Cloudy" is a lighting change with a greyer sky, not visible clouds.
- Only the near rain / snow volumes are traced: far away, drops and flakes also fall under awnings and bridges.
- The surface decal does not follow vertical surfaces (no wet walls / no snow on ledges' faces), and dead-leaf
  decals in NYC draw on top of the snow (they read as leaves on snow).
- The pack's own 60 s transitions and random weather cycling are not used; the menu choice stays until changed and
  is not saved: every load of NYC Survival starts Clear (`StartWeather` on "AFS Weather" changes that).
- Falling snow reads lightly from the raised street camera (2.5-6 cm flakes); the snow cover carries it there.
  Denser snow costs CPU in the traced volume.
- Rain is lit translucency: in Storm it is darker and less visible than in Rain.
- Weather is per level: only NYC Survival has the actor (test pads untouched). Single-player: `AHoverWeather` does
  not replicate (the pack's multiplayer events are not used).
