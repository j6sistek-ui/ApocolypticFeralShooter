# AFS: continuity

How a fresh chat or a new machine picks this project up without re-learning it.

## Read first

`CLAUDE.md` at the repo root has the working rules every chat follows; `AGENTS.md` points to it.

1. `Docs/SCOPE.md` (what we are building and the current phase)
2. `Docs/RULES.md` (owner rulings and operational rules)
3. `Docs/BACKLOG.md` (bugs, ranked to-do, owner decisions; maintained first) and `Docs/DONE.md` (finished work
   waiting on the owner's in-game review)
4. `Docs/LESSONS.md` (what already went wrong)
5. `Docs/POWERUP_CATALOG.md` and `Docs/ASSET_KITS.md` (power-up designs; which packs exist and where)
6. `Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md` (the design, by section)

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

## State on 2026-10-31 evening (hand-off)

Built green and proven headless (`Scripts/ProveLifeEngineAudio.py`, receipt
`D:/AFS_Comparisons/LifeEngine_20261031/proof.json`, ok true): Life Engine on by default in NYC Survival, switched in
the F6 / D-pad Up test-settings menu ("Movement: Life Engine / Classic", applied on A without a reload; the proof flips
it through the real menu); audio pass (footsteps, katana whoosh and cut, WW2 machine-gun pool, revolver crack, wind
bed); corpse launch cap; unwalkable zombie heads (character movement and solver); four-sweep katana; Y/G weapon cycle
with DA_NYC_Pistol in slot 2; fixed-distance survival camera; sprint 680. The owner has not yet played any of this.
Next by owner priority: the big bugs (zombie diversity / behaviour, kid clumping, Nuke presentation, ammo readout),
then the pause-menu weather toggle.

**Local-only changes (not in git, by the ignore rules):** `Config/DefaultGame.ini` SprintSpeed 680, and the patches
to the purchased `Plugins/HLMovementSystem` solver (each marked `AFS 2026-10-31`): PollInput keeps fed inputs,
substepped tick, start-penetration rejection in the ground checks, the snap-down floor hit kept, pawns never floor or
step (`IsPawnHit`), step-up retries while input is held, slide on the sweep normal, `HL_GROUND` / `HL_BLOCK` Verbose
logs. Back up the plugin folder with the project.

## Where the proofs go

`D:\AFS_Comparisons\<Topic>_<date>\` with a JSON receipt per run (`capture.json`, `proof.json`, `*_report.json`).
Stills are 1280x720 or 1920x1080 PNG; the owner looks at stills, not videos.

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
