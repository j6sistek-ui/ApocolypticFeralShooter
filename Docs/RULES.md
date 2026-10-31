# AFS: working rules

Rules the owner set, plus operational rules that cost real time when broken. Each has a date so a later reader can
tell which is newer.

## Owner rulings

- **The backlog comes first.** `Docs/BACKLOG.md` is maintained above all else: every idea, bug and piece of feedback
  is added and ranked the same day and pushed. When the owner raises something that is not game-breaking, confirm its
  priority. When the owner asks for it now, name the current top task and confirm the owner wants to pull it ahead.
  Keep the repo simple: design, issues, needs and context. Finished work is removed from the backlog and goes
  to `Docs/DONE.md` with the AI validation; the owner's in-game check ticks it there or sends it back to the backlog.
  No stale done items in the backlog. (2026-10-31)
- **Effect explorations go in a trial map.** Build options as placed actors in a trial map the owner can open and see
  live (motion running in-engine, not only from a preview script), and also send a few shots or GIFs for when the owner
  is away. Only fall back to script-driven renders when building it in the map is much harder. (2026-10-31)
- **Feel first.** Gameplay and feel before bells and whistles; placeholders are fine. (2026-10-29)
- **No Call of Duty names.** Perks use the original six names (Second Wind, Ironhide, Fast Lane, Bullseye, Hair
  Trigger, Marathon). (2026-10-29)
- **Judge in game.** The owner judges animation and feel by playing, not from side-by-side videos. Send stills and a
  launcher, keep the claims to what the receipts show. (2026-10-31)
- **The Life Engine drives, the parkour template decorates.** In NYC Survival the Source-style solver owns ground
  movement; the parkour template keeps its animations and capabilities (wall run, wall jump, vault) and only takes the
  capsule while it is mid-move. (2026-10-31)
- **Fixed camera distance.** The survival camera stays at its arm length; only the aim zoom and a sprint stretch change
  it. No positional lag. (2026-10-31)
- **Spear pack is Vexa's melee.** `SpearAnimationsV2` becomes a spear melee weapon; its poses may be mildly adapted for
  other melee weapons rather than authoring motion from scratch. (2026-10-31)
- **Sprint was too fast.** 900 cm/s came from our DefaultGame.ini, not the parkour pack; it is 680 now. Walk stays 500
  until the owner says otherwise. (2026-10-31)
- **Do not change control bindings** until the owner has tested the current ones. (2026-10-30)
- **GPU budget while the owner games:** keep rendered captures under about 6 GB VRAM (1280x720, scalability 1,
  streaming pool 1200). CPU (NullRHI) work is unrestricted. (2026-10-31)
- **The Robot Mine (SilkTrap)** is a thrown tactical: lands, seeks the nearest zombie, explodes AOE. **Blood Magic**
  is for a boss-type zombie and cheap ground haze in hordes. **Arrow Trail** doubles as the bullet tracer. (2026-10-31)
- **Blood Bomb** (the empty horror grenade) waits for the owner before its core is built. (2026-10-31)
- **Weather:** Dreamrise Multiplayer Dynamic Weather System is the chosen system (own project on M), not the free one.
- **This chat is AFS.** SpaceSurvival work goes to its own chat. (2026-10-31)

## Operational rules

- **Never build while an editor is open.** `UnrealEditor.exe` locks `UnrealEditor-HoverFlight.dll`; check `tasklist`
  first. Compiles and NullRHI scripts may run beside a SpaceSurvival editor, never beside an AFS one.
- **Only one rendered capture at a time** (AGENTS.md). NullRHI authoring may run in parallel.
- **Never commit Content** through git; purchased content and local configuration stay private (the ignore list is
  source, scripts and docs only). Commit only when the owner asks.
- **Headless Blender 5.2: never `read_factory_settings` or `--factory-startup`.** It wipes the extension wheels
  (PIL, cv2, imageio, trimesh...). Use `read_homefile(use_empty=True)`; `RestoreBlenderWheels.py` repairs the damage.
- **Headless Unreal:** `UnrealEditor-Cmd.exe <project> -unattended -nullrhi -stdout -FullStdOutLogOutput
  -ExecutePythonScript=<abs path>` for CPU work; `-RenderOffscreen` plus the capped scalability flags for pixels.
  A Python exception does not fail the process: grep the log for `LogPython: Error`.
- **Python edits to data assets:** `get_editor_property` only sees Edit/BlueprintVisible UPROPERTYs; material and
  mesh arrays of structs come back as copies (write them back by index); `set_material_instance_texture_parameter_value`
  returns False in 5.8 even when it worked, so read back.
- **Every import gets a validator run** (`Scripts/ValidateGunClips.py` for guns) and every feel change gets a
  rendered proof with a JSON receipt under `D:\AFS_Comparisons\`.
- **Controller problems are Steam first.** The DualSense reaches Unreal only through Steam Input; grep `AFS.log` for
  `RegisterDevice` before touching input code.
- **Docs record decisions with dates.** When the owner reverses something, the newer line wins and says so.
