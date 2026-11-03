# AFS: continuity

How a fresh chat or a new machine picks this project up without re-learning it.

## Read first

`CLAUDE.md` at the repo root has the working rules every chat follows; `AGENTS.md` points to it.

1. `Docs/SCOPE.md` (what we are building and the current phase)
2. `Docs/RULES.md` (owner rulings and operational rules)
3. `Docs/BACKLOG.md` (bugs, ranked to-do, owner decisions; maintained first) and `Docs/DONE.md` (finished work
   waiting on the owner's in-game review)
4. `Docs/LESSONS.md` (what already went wrong)
5. `Docs/POWERUP_CATALOG.md`, `Docs/POWERUP_BUILD.md` and `Docs/ASSET_KITS.md` (power-up designs and how the
   decided looks are built; which packs exist and where)
6. `Docs/PERKS.md` (the perk drafts and machines) and `Docs/WEATHER.md` (the weather system)
7. `Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md` (the design, by section)

## Build and run

```
powershell -NoProfile -ExecutionPolicy Bypass -File M:\UnrealProjects\AFS\Scripts\Build.ps1
```

Check `tasklist | findstr UnrealEditor` first: a build fails against an open editor.

Headless CPU script:

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" M:\UnrealProjects\AFS\AFS.uproject -unattended -nullrhi -stdout -FullStdOutLogOutput -ExecutePythonScript=M:\UnrealProjects\AFS\Scripts\<script>.py
```

Rendered proof (capped for a shared GPU):

```
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" M:\UnrealProjects\AFS\AFS.uproject -RenderOffscreen -unattended -nosplash -ResX=1280 -ResY=720 "-ExecCmds=r.Streaming.PoolSize 1200, sg.ShadowQuality 1, sg.GlobalIlluminationQuality 1, sg.ReflectionQuality 1, sg.PostProcessQuality 1, sg.EffectsQuality 1" -ExecutePythonScript=M:\UnrealProjects\AFS\Scripts\<script>.py
```

Play NYC Survival from the launcher or the editor: `/Game/HoverPrototype/Maps/L_NYC_Survival`.

## Scripts that matter

| Script | Purpose |
|---|---|
| `Scripts/Build.ps1` | compile HoverFlight and the plugins |
| `Scripts/AuthorNYCSurvival.py`, `VerifyNYCSurvival.py`, `CaptureNYCSurvival.py` | author the map, verify rounds (nullrhi), capture (GPU) |
| `Scripts/AuthorNYCData.py`, `AuthorNYCBosses.py`, `AuthorNYCAudio.py` | data assets, bosses, the owner's audio sets |
| `Scripts/ImportM4A1.py`, `ImportEMGuns.py`, `AuthorGunRigs.py`, `ValidateGunClips.py`, `CaptureGuns.py` | the rigged guns pipeline and its proof |
| `Scripts/ImportM4A1Painter.py` | the owner's Painter retexture onto the M4A1 |
| `Scripts/ImportGrenades.py`, `PreviewGrenades.py` | the horror and Fab grenades |
| `Scripts/ProveLifeEngineAudio.py` | play proof for the Life Engine toggle and the audio pass |
| `Scripts/FixNYCLights.py` | directional-light priority in the NYC map |
| `Scripts/Blender/*.py` | headless Blender rig, cut, split and audit tools |
| `Scripts/ProveWalking.py`, `MakeWalkingVideo.py` | walking / crouch proof (`WALK_MAP` survival, explore or postapo) and its video |
| `Scripts/ImportWeather.py`, `ProveWeather.py`, `MakeWeatherVideo.py` | weather placement in NYC Survival, its proof (stills, moving camera, cost) and video |
| `Scripts/ImportPerkMachines.py`, `ImportHeadhunter.py`, `CapturePerkMachines.py` | perk machines into NYC Exploration and their stills |
| `Scripts/Blender/AssembleLifeblood.py`, `AssembleBioreactor.py`, `ExportHeadhunter.py` | machine assembly from the owner's parts |
| `Scripts/AuthorPowerUpLive.py`, `CapturePowerUpLive.py` | the live power-up displays (Nuke, Medkit, Max Ammo) and their stills |

## State on 2026-11-03 (hand-off)

Everything below is committed and pushed (last code commit `58fa70c`); `Docs/DONE.md` lists what waits on the
owner's in-game check (items 1-17), `Docs/BACKLOG.md` the ranked open work.

Done 2026-11-01 to 11-03:
- **Walking (DONE 16, `0d87cdb`).** Under the Life Engine CLS was told "in the air" on every grounded frame (engine
  movement-mode numbers written into CLS's own enum) and its trajectory read a 0 top speed, so Vexa floated in the
  fall pose and skated. Fixed in `HoverLocomotionBridge.cpp` / `HoverMovementComponent.cpp`; the pilot / Life Engine
  tick cycle is one-way; NYC "Water" asphalt no longer plays puddle footsteps; crouch 300.
- **Weather (DONE 17, `4bd9148`, `7f0041c`).** The owner's Multiplayer Dynamic Weather pack copied into
  `Content/MultiplayerDynamicWeatherSystem`, driven by `AHoverWeather` in NYC Survival only; F6 row and `Weather`
  exec. The pack's own manager is not used (it would replace NYC's sun, sky and fog).
- **Perk machines.** Headhunter in NYC Exploration with the live blood tube (`AHoverBloodTube`, DONE 15, owner
  confirmed the look); Lifeblood's PERK MACHINE subtitle repainted at 4K (in Unreal; renders with dark doubled edges,
  see Bugs). Machines go in NYC Survival, never side by side (`PERKS.md`).
- **Nuke display** doubled and sparkier (DONE 14 note).
- **Open topics for the owner** are at the top of the backlog's "Waiting on the owner" list (2026-11-03).
- **Texture caps audited** (2026-11-01): headless stills used to show low mips; capture scripts now force full
  textures. Real 2K caps remain on the M4A1 (16 maps), zombie variants (38) and grenades (owner to decide on 4K).

- **Weather lens fix (`58fa70c`):** flakes and rain drops fade out within 1-3.5 m of the camera (no lens discs).

Machine notes: Unreal's local cache server holds about 999 saved sessions and can take ~10 minutes to start; runs
then wait on it (do not kill it). Two SpaceSurvival editors from other sessions sometimes run alongside; one Unreal
process at a time keeps the owner's PC usable.

## State on 2026-10-31 evening (hand-off)

Built green and proven headless (`Scripts/ProveLifeEngineAudio.py`, receipt
`D:/AFS_Comparisons/LifeEngine_20261031/proof.json`, ok true): Life Engine on by default in NYC Survival, switched in
the F6 / D-pad Up test-settings menu ("Movement: Life Engine / Classic", applied on A without a reload; the proof flips
it through the real menu); audio pass (footsteps, katana whoosh and cut, WW2 machine-gun pool, revolver crack, wind
bed); corpse launch cap; unwalkable zombie heads (character movement and solver); four-sweep katana; Y/G weapon cycle
with DA_NYC_Pistol in slot 2; fixed-distance survival camera; sprint 680. The owner has not yet played any of this.
Next by owner priority: the big bugs (zombie diversity / behaviour, kid clumping, Nuke presentation, ammo readout),
then the pause-menu weather toggle.

**Local-only changes (not in git, by the ignore rules):** `Config/DefaultGame.ini` SprintSpeed 680 and
`CrouchedSpeed=300` (2026-11-01), and the patches
to the purchased `Plugins/HLMovementSystem` solver (each marked `AFS 2026-10-31`): PollInput keeps fed inputs,
substepped tick, start-penetration rejection in the ground checks, the snap-down floor hit kept, pawns never floor or
step (`IsPawnHit`), step-up retries while input is held, slide on the sweep normal, `HL_GROUND` / `HL_BLOCK` Verbose
logs. Back up the plugin folder with the project.

## Where the proofs go

`D:\AFS_Comparisons\<Topic>_<date>\` with a JSON receipt per run (`capture.json`, `proof.json`, `*_report.json`).
Stills are 1280x720 or 1920x1080 PNG. Short labelled MP4s when the owner is away (walking, weather); compress a
copy under 30 MB to send to the phone.

## Conventions

- C++ lives in `Source/HoverFlight` (Allman braces, 4 spaces, clang-format in SpaceSurvival's toolchain). The
  ZESP plugin source under `Plugins/ZombieEngineStudio` is compiled by us and may be patched; every patch carries an
  `AFS <date>` comment saying why.
- Owned data assets live under `/Game/HoverPrototype/NYC/` and `/Game/HoverPrototype/Weapons/`; vendor assets are
  never edited in place, they are duplicated.
- Each feel change has a Verbose log line (`HOVER_*`) so a headless run can prove it without pixels.
- Dates in docs are the day the fact was established; a newer dated line supersedes an older one.

## Assistant memory

The assistant keeps a private memory index outside the repo (facts, rulings, gotchas). This repo's docs are the
shared, durable copy; anything decided in chat that matters later goes into `RULES.md`, `LESSONS.md` or
`BACKLOG.md` the same day.
