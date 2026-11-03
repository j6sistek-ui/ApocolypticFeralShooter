# AFS: backlog

Only open work: bugs, the ranked to-do list, and decisions waiting on the owner. Last update: 2026-11-03.

## How this list works (owner rules, 2026-10-31)

- This list is maintained above everything else. Every new idea, bug or piece of feedback lands here the same day,
  ranked, and is pushed.
- When the owner raises something that is not game-breaking, confirm its priority (where it slots).
- When the owner asks for it now, name the current top task and confirm the owner wants to pull it ahead first.
- Game-breaking bugs (crash, softlock, mode unplayable) go straight to the top.
- **Later** is a parking lot: it keeps ideas safe so work does not drift onto things that matter much later while
  Now has needs (owner, 2026-10-31).
- When an item is done it is **removed from here** and added to `DONE.md`. The owner's in-game check ticks it there
  or sends it back here. No done items stay in this file.

## Bugs

Severity: **G** game-breaking, **M** major (hurts play), **m** minor.

| Bug | Sev |
|---|---|
| Life Engine jumps are low and short: 110 cm peak, 0.6 s in the air, 4.1 m running jump vs Classic 248 cm, 0.9 s, 6.1 m (preset gravity 2032, jump 686) | M |
| Owner 2026-11-01: crouch / hold-B "penguin waddle" on the NYC maps. 2026-11-01 walking fix: the in-air pose on standing up is fixed and crouch speed is 300 to match the clips, but scripted tests show the same crouch on NYC Survival, Exploration and PostApo; the test pads start in first person (rifle stance, belly crawl) and NYC Survival in third person (hands-and-knees crawl). Hold B at rest = prone crawl, while moving = dive. Needs the owner's eyes on `walking_before_after.mp4` | m |
| Life Engine has almost no air steering: 41 cm sideways in a jump vs 236 cm on Classic (Source-style air control needs mouse air-strafing) | M |
| Lifeblood sign in Unreal: the repainted PERK MACHINE subtitle (texture confirmed in, 2026-11-01) renders with dark doubled edges under the game lighting, unlike Blender; suspect the normal-map relief or the glass material (normal flip is correct). Still `D:/AFS_Comparisons/PerkMachines_20261101/Lifeblood_text/unreal/stills/Lifeblood_sign.png` | m |
| Life Engine straight-wall run dropped from 0.33 s to 0.1 s after the 2026-11-01 tick-order fix (ProveParkourLifeEngine); Classic unchanged | m |
| Life Engine planted-foot slide is about 1.4x Classic (104 vs 77 cm/s); lead: the CLS bridge ticks after the pilot but not after the solver | m |
| Life Engine: running into a wall at an angle stops dead (no wall slide); template wall runs are very short | M |
| Owner 2026-11-01: the hand goes through the middle of the sword (katana) handle instead of gripping it | m |
| Spear hits land 1.7-3.4 m out while the visible head reaches about 1 m; the jab points about 40 degrees high | m |
| Ammo pickup glint lights the area like a lamp (and nearby zombies) | m |
| Kid swarm: only 2 attack tokens, about 3 in 20 kids hang back at 3 m | m |
| Some slow zombie walks are sped up and slide; EtherionB walks 23 degrees off its travel | m |
| Vendor swing and death timers ignore the per-zombie animation-rate roll (up to 9 % early or late) | m |
| Zombies sink into the ground in PostApo (`AHoverZombie`, recording 0:24) | m |
| Small-gun muzzle flash too hot within 20 cm (EM21, EM08) | m |
| Owner 2026-11-01: the muzzle flash blinds the scope when firing, and it is still the blue sci-fi flash, not the warm per-rig flash from 2026-10-31 (that override only covers the 4 rigged guns; which gun and map to confirm) | M |
| Owner 2026-11-01: no ambient sound (requested). The crowd ambience by alive count was wired 2026-10-29 for NYC Survival rounds only; no city/weather ambience is wired anywhere (the weather SFX loops pack is in the project) | M |
| First-person arms fill the view; owner 2026-11-01: the left arm still looks very wrong in first person (`HoverView` is Exec-only; needs an FP capture to tune offset and FOV) | m |
| Brute, Kid horde round and bosses not yet seen in a rendered run with the new roster | m |

## Priority to-do (ranked; owner confirmed the direction 2026-10-31)

Owner 2026-10-31: ideas get tabled when they come (logged, not designed); the priority is the Stage 1 core loop.
While the owner cannot playtest, in-between work chips away at the top items that do not need a playtest.

**Now**
0. Power-ups, time-boxed: the live displays are built (`DONE.md` #14), waiting on the owner's look in the
   editor. Open for the owner's eye: the Nuke pops have no smoke puff (it could not read on the black casing), Max
   Ammo's haze is a little yellow on one edge, and the Nuke reads small from the start (fixed 2026-11-03: twice the size, sparks every ~0.9 s, `DONE.md` #14;
   from 3.5 m the sparks still read faint, the owner's call whether to make them bigger or brighter). Then the shared look goes to
   the other power-ups, and the display gets attached to the real pickup (`bLoopForEvaluation = false`).
1. **Phase 1 core loop: perks** (`PERKS.md`; the owner is drafting the ideas). Design the perk mechanics and the machines, then build them: the six perks (owner
   drafts so far: Necrosiphon (health), Life Blood (revive), Headhunter (ammo efficiency), Survivalist (speed,
   melee, carry), Bioreactor (passive damage); one more to decide) with effects, prices (design: 2,500 + 500 per perk
   owned), limits, HUD icons, the machine (Lifeblood and Bioreactor machines stand in NYC Exploration since 2026-10-31,
   `DONE.md` #13; the other four await the owner's Tripo parts), placement in NYC, and how buying works. Then the rest of the loop: doors and zones, the power objective, wall buys, vests, the
   upgrade machine (Pack-a-Punch equivalent, original name), the downed state (comes first for Life Blood: crawl
   and shoot while down; solo without the perk ends the run), the HUD.
   Headhunter tube fix round (owner liked the look 2026-11-01): show the painted red TubeRing (pool wall inside it),
   bigger drops falling mostly from the cap, the headshot splat landing with the spurt and old splats fading instead
   of vanishing, less pink on the skull crown. Machines go in NYC Survival, spread out, never side by side.
1b. **Muzzle flash, ambient sound** (owner placed it right after perks, 2026-11-01): the warm flash on every gun
   the player holds (no scope whiteout), and city/weather ambience plus a check that the crowd ambience plays in rounds (the 2026-10-31 audio pass
   lists wind, which the owner did not hear).
2. Owner playtest of everything in `DONE.md` (whenever the owner can); the results re-rank this list.
3. Life Engine movement feel: measured 2026-10-31 (`Scripts/ProveLifeEngineCompare.py`); waiting on the owner's
   test to choose jump height and air control, then wall slide and wall runs.
4. Zombie follow-ups: rendered check of the Brute, Kid horde and bosses; foot slide; grab and tackle attacks from
   `AbductionAnimPack`.
5. Melee feel: spear reach and jab angle; katana feel after the owner's check.

**Next**
6. Power-up effects: the new effects from `POWERUP_CATALOG.md` (unlimited ammo, invincibility, slow time, perfect
   vision, Curse, boss totem, sprint, health) after the core loop (Max Ammo model arrived: #18).
7. Ammo economy: buy points (staged in `Scripts/AuthorNukeAmmoStations.py`, waiting on the owner), glint toned down;
   folds into the wall-buy work in item 1 if that comes first.
8. Weather follow-ups (`DONE.md` #17): owner's call on rain cost and snowflake look; saved menu choice; day/night,
   seasons and clouds from the pack (not used); wet walls.
9. ZESP in-game settings menu in the pause menu: the owner says what it should expose.
10. Vehicles: drivable Doomsday pickup (owner adds the pack to the project); gas can if rides need fuel.
11. Dead-body poses: corpse dressing and dormant ambush zombies that rise (owner adds the Unreal Engine format).
12. Visuals: rifle at 4K (the 4096 source is in; the import still caps it at 2048, see the 2026-11-01 texture audit), first-person arms (left arm), small-gun flash.

**Later (tabled ideas, not designed)**
- Tacticals: Silk spider drone with modes (mini-nuke hunter, electrical defence field, healing pulse waves for nearby
  players; trap-pod pickup grants a charge, also in the shop); toxic gas bomb; Blood Bomb; the painted Fab grenades;
  the other EM gun rigs as finds or buys.
- Bosses and specials: blood-magic boss (vortex telegraph, blood projectiles), thin blood haze in hordes (only if
  cheap), boss totem ally, zombies throwing spears at a player they cannot reach.
- Power-up idea bank (owner's reference boards): Corpse Magnet, Boom Box, Ghost Snack / Zombie Buddy, Caffeine
  Overdrive, Be-Gone Cloud, Frostbite Shake, Lucky Scav Box, Hemo Burst, Static Surprise, Banshee's Whistle, Good
  Boy companion; in `POWERUP_CATALOG.md` with the model each could repurpose.
- Stations beyond Stage 1: mystery crate, armour box, health station.
- Movement extras: a vault (needs a pack clip), motion matching locomotion option, the Advanced Flight System plugin
  (the project's namesake, never tested; owner's Fab library).
- Controls and HUD naming (PlayStation glyphs), tracer trial (Free Arrow Trail), EM_11 right-side camera, revolver
  cup reading as a barrel.

## Waiting on the owner

- (2026-11-03) Rain cost: about +2-3.7 ms on the game thread while running; accept, or thin the rain further?
- (2026-11-03) Snow and Nuke sparks read faint at play distance: bigger / brighter flakes and sparks?
- (2026-11-01) Crouch "penguin waddle": still there after the walking fix? (`walking_before_after.mp4`)
- (2026-11-01) Sword grip (hand through the katana handle): rank it (asked: with melee feel #5?).
- (2026-11-01) Muzzle-flash scope whiteout: which gun and map?
- (2026-11-01) Raise the M4A1 (16) and zombie (38) textures from 2K to 4K, with the texture pool at about 3 GB?
- (2026-11-03) Clear Unreal's local cache of ~999 saved sessions (slow starts)?
- Ammo buy points: place 2-3 in NYC (Cyber City's supply crate)? Price?
- Kid swarm: truck to the Garage? a closer horde-only spawn band? more horde attack tokens?
- Nuke banner text (placeholder "STREET SWEEP"); keep the slow-motion beat? Later per the power-up design: ticking
  pickup, bosses take heavy damage instead of dying.
- Vault: wanted? which pack clip?
- Spear: generous reach or match the visible head? damage numbers? slot 4 or a pickup?
- Fill light: 2.5 cd "just a bit", or lower?
- Rifle 4K: re-export GUN.spp at 4096 from Painter.
- Doomsday pickup and Dead Bodies poses: add their Unreal Engine format to the project.
- Cars: enterable, or removed from the mode?
