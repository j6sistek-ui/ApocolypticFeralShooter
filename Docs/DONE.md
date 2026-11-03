# AFS: completed work, waiting on the owner's in-game check

Finished items move here from `BACKLOG.md`. Each one says what to look at in game and how the AI validated it. The
owner ticks the box when it checks out in game, or sends it back: it is then removed here and returns to
`BACKLOG.md` with the owner's note. Ticked items stay as one line under "Confirmed" so this file stays short.
Receipts and stills live under `D:\AFS_Comparisons\` (local, not in git).

## Waiting on the owner (NYC Survival)

- [ ] **1. Zombie variety** (2026-10-31, `7114ae2`). 11 types: Shambler, Lurcher, Runner, Brawler, Drifter, Bog,
  Horror, Pirate, Plant, Etherion A/B, each with its own walk, attacks, hits, deaths and voice; random skins, morphs,
  size and speed.
  *Check:* 8+ different-looking zombies in a group; nobody walks backwards or sideways; every swing shows an attack;
  voices differ by type without a wall of sound; headshot burst and death splash; some roar when they first see you.
  *AI:* `ProveZombieDiversity.py`: 11 types, 0 % backwards, toes 2-8 degrees off travel, 14/14 swings on attack clips,
  124 voice lines from 65 sounds; stills checked.
- [ ] **2. Kid swarm** (2026-10-31, `21eb065`). Truck cut out of navigation, packs from several directions.
  *Check:* kids no longer pile into or push the truck; they come from several sides and ring Vexa.
  *AI:* `ProveKidSwarm.py`: 0 paths through the truck, truck stays put, 7 spawners, contact 85 %.
- [ ] **3. Nuke presentation** (2026-10-31, `21eb065`).
  *Check:* zombies die in a ripple outward; banner (placeholder "STREET SWEEP"), flash, explosion, shockwave ring,
  short slow motion; no 999,999 number.
  *AI:* `ProveNukeAmmo.py`: ripple over 0.6 s in distance order, every feedback line logged; stills checked.
- [ ] **4. Ammo pickup readability** (2026-10-31, `21eb065`).
  *Check:* pickups bob and glint, pickup sound, "+30 AMMO" toast, the reserve flashes.
  *AI:* same proof: reserve 270 to 300, toast and sound logged.
- [ ] **5. Spear melee** (2026-10-31, `21eb065`).
  *Check:* tap Y to reach the spear (slot 4); V for jab, thrust, swing; hold to charge a heavy thrust; hits pass
  through a line of zombies; the katana feels unchanged.
  *AI:* `ProveSpear.py`: combo and heavy hit at the measured reach, katana sweep unchanged.
- [ ] **6. Life Engine movement** (2026-10-31, `a492e17`, `21eb065`). F6 menu row "Movement": Life Engine / Classic.
  *Check:* walk, sprint and jump feel in both modes; wall run and wall jump with the Life Engine on; a jump pose
  instead of a running stride.
  *AI:* `ProveLifeEngineAudio.py`; `ProveParkourLifeEngine.py`: wall-run hand-off and resume in both modes;
  `ProveLifeEngineCompare.py` (Life Engine vs Classic): same top speeds (500 walk, 680 sprint); reaches 90 % of
  speed in 0.3 s vs 0.5-0.67 s; 90-degree turn in 0.27 s keeping 285 cm/s vs 0.4 s dropping to 115; reverse in
  0.4 s vs 0.63; stops about the same (0.23-0.27 s vs 0.2 s, 3-5 cm longer); jump 110 cm / 0.6 s vs 248 cm / 0.9 s;
  running jump 4.1 m vs 6.1 m; air steering 41 cm vs 236 cm; holding jump while sprinting gives no speed gain
  in a straight line in either mode.
- [ ] **7. Fixed-distance camera, sprint 680** (2026-10-31, `a492e17`).
  *Check:* the camera keeps its distance except aiming (in) and sprinting (a little out); sprint no longer too fast.
  *AI:* built; feel cannot be judged headless.
- [ ] **8. Audio pass** (2026-10-31, `a492e17`).
  *Check:* machine-gun sound on the rifle, crack on the revolver, katana whoosh and cut, footsteps by surface, wind.
  *AI:* `ProveLifeEngineAudio.py`: footsteps, swing sounds and the wind bed logged.
- [ ] **9. Corpses stay down, heads not walkable** (2026-10-31, `a492e17`).
  *Check:* dead zombies slump instead of flying; no bouncing on heads.
  *AI:* built; not separately proven in a rendered run.
- [ ] **10. Katana damage window** (2026-10-31, `a492e17`).
  *Check:* the swing hits across most of its arc, with a cut sound on contact.
  *AI:* `HOVER_KATANA_SWEEP` logged in the proofs.
- [ ] **11. Weapon cycle, pistol in slot 2** (2026-10-31, `a492e17`).
  *Check:* tap Y: rifle, pistol, spear; holding Y still calls the glider.
  *AI:* proof cycled slot 1, 2, 4.
- [ ] **12. Fill light on Vexa, texture pass** (2026-10-31, `21eb065`).
  *Check:* Vexa a little brighter, zombies beside her not; console `HoverFillLight 0` / `1` to compare.
  *AI:* `ProveVisualPass.py`: torso +54 % at 2.5 cd, a zombie beside her unchanged.
- [ ] **14. Live power-ups in NYC Exploration** (2026-10-31; Nuke doubled and sparkier 2026-11-03, `7f0041c`). The decided looks on a live display actor: Nuke,
  Medkit, Max Ammo, about 3 m ahead of the player start (in the editor: Realtime on, editor focused; or press Play).
  *Check:*
  - The Nuke shakes and ticks throughout. Spark bursts and small pops alternate about every 3 s. In the last 5 s
    the heartbeat and arcs ease in and speed up.
  - Medkit and Max Ammo have the neon icon, the coloured aura and a touch of red, with a heartbeat in the last 5 s.
  - They loop every 32.5 s for evaluation.
  *AI:* independent check of the build and of the fix pass:
  - Build succeeded; the authoring script ran with ok=True.
  - No ghost lid on the Nuke.
  - Hidden-after-save bug fixed, and verified by a reload.
  - Animation runs in the editor without Play (life 0 to 6 s).
  - Stills in `D:/AFS_Comparisons/PowerUps_20261031/Live/stills_fix/`.
  - The decided smoke puff is off (it could not read on the black casing).
- [ ] **13. Perk machines in NYC Exploration** (2026-10-31). Lifeblood and Bioreactor as props (no buying yet),
  about 10 m ahead of the player start, facing it.
  *Check:* LIFEBLOOD reads on the front and both sides; the blood core and heart sign beat; the cabinet colour
  holds up in the street light; the Bioreactor screen and biohazard sign glow, the liquid moves, the stirring
  shaft turns behind the glass; you cannot walk through either machine.
  *AI:* `ImportPerkMachines.py` (12 parts, 4 materials compiled with no link failures, 12 actors after a map
  reload); `CapturePerkMachines.py` stills from the spawn point and close up, 0.7 s apart: the shaft and the beat
  move. Glass is a plain fresnel glass; no bubbles yet.
  *Owner 2026-11-01:* Bioreactor looks great; Lifeblood has an issue (details pending). Sent back.
- [ ] **16. Walking in NYC Survival** (2026-11-01, `0d87cdb`). Under the Life Engine Vexa now jogs like Classic, feet on
  the ground; the floating crouched (fall) pose is gone; footsteps on the NYC streets sound dry; crouch walks at 300.
  *Check:* walk and sprint in NYC Survival on Life Engine and Classic (F6); crouch and hold-B; footsteps on the street.
  *AI:* causes and numbers: CLS was told "in the air" on every grounded frame (116/116), its path prediction read a
  0 top speed (walk clip, skating), and the pilot and Life Engine ticked in a loop (3,567 warnings in your log, now 0).
  After: jog clip 110/115 frames (Classic 106/109), feet 0.4 cm off the ground, Classic unchanged, parkour proof
  passes. Video `D:/AFS_Comparisons/Walking_20261101/walking_before_after.mp4`. Open: the crouch "waddle" was not
  reproduced as map-specific (see Bugs), Life Engine wall runs got shorter (0.33 to 0.1 s).
- [ ] **17. Weather in NYC Survival** (2026-11-01/03, `4bd9148`, `7f0041c`). The owner's Multiplayer Dynamic Weather
  pack, driven by `AHoverWeather` (`Docs/WEATHER.md`). F6 menu row "Weather": Clear / Cloudy / Rain / Storm / Snow
  (6 s blend; Cancel keeps the current weather); exec `Weather Rain`, `Weather Snow 0` (instant). Clear is the default
  and looks as before.
  *Check:* each weather from the player view and while running; wet streets and snow cover; thunder flashes in Storm;
  blood still lands on zombies in rain/snow; the rain and wind sound.
  *AI:* two independent reviews. Pack copied intact (130 packages, source project untouched); no second sun; wet/snow
  layer fades out (no edge); snow holds while running (-18 %) and turning (-10 %); particle cap restored; blood decals
  on characters during rain and snow. Cost, player running, quiet machine: snow +1.2 ms game thread, rain/storm about
  +2-3.7 ms game thread, GPU under +0.5 ms. Video `D:/AFS_Comparisons/Weather_20261101/weather_nyc.mp4`.

## Confirmed by the owner

- [x] **15. Headhunter perk machine in NYC Exploration** (2026-11-01). Your Painter textures (Unreal export, full 4K)
  on the 12 parts, a glass tube with live blood: a deep pool on the red disc, runs and spatter on the inside of the
  glass, drops into the pool with splash rings, a "headshot" spatter every 12-20 s, slow bubbles, a red glow. Third
  machine, about 3.6 m right of the Bioreactor and 2 m forward of the row. Select `AFS Perk Trial Headhunter TubeFX`
  (folder `AFS_PerkMachines`); its Details panel fires a headshot or a drop on demand.
  *AI:* build succeeded; materials compile; Lifeblood/Bioreactor unchanged after save and reload; stills with full
  textures forced in `D:/AFS_Comparisons/PerkMachines_20261101/Headhunter/fix1/stills/`. Known open (fix round
  pending): the pool hides the painted TubeRing, drops are small, the splat lands before the spurt and a new
  headshot wipes the old splat, a pink tint on the skull crown from the added fill light, boxes may overlap.
  *Owner 2026-11-01:* "perks look great". Placement does not matter here: machines go in NYC Survival and are never
  side by side. Open tube fixes moved to the backlog (perks, item 1).
