# AFS: continuity

How a fresh chat or a new machine picks this project up without re-learning it.

## Read first

1. `Docs/SCOPE.md` (what we are building and the current phase)
2. `Docs/RULES.md` (owner rulings and operational rules)
3. `Docs/OPEN_ISSUES.md` (what is open, with status)
4. `Docs/LESSONS.md` (what already went wrong)
5. `Docs/NYC_PRIORITIES_AND_ANIMATION_NEEDS_20261029.md` (the running log with Done blocks and the playtest list)
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
`OPEN_ISSUES.md` the same day.
