# AFS: backlog

Only open work: bugs, the ranked to-do list, and decisions waiting on the owner. Last update: 2026-10-31.

## How this list works (owner rules, 2026-10-31)

- This list is maintained above everything else. Every new idea, bug or piece of feedback lands here the same day,
  ranked, and is pushed.
- When the owner raises something that is not game-breaking, confirm its priority (where it slots).
- When the owner asks for it now, name the current top task and confirm the owner wants to pull it ahead first.
- Game-breaking bugs (crash, softlock, mode unplayable) go straight to the top.
- When an item is done it is **removed from here** and added to `DONE.md`. The owner's in-game check ticks it there
  or sends it back here. No done items stay in this file.

## Bugs

Severity: **G** game-breaking, **M** major (hurts play), **m** minor.

| Bug | Sev |
|---|---|
| Life Engine jumps are low and short: 110 cm peak, 0.6 s in the air, 4.1 m running jump vs Classic 248 cm, 0.9 s, 6.1 m (preset gravity 2032, jump 686) | M |
| Life Engine has almost no air steering: 41 cm sideways in a jump vs 236 cm on Classic (Source-style air control needs mouse air-strafing) | M |
| Life Engine: running into a wall at an angle stops dead (no wall slide); template wall runs are very short | M |
| Spear hits land 1.7-3.4 m out while the visible head reaches about 1 m; the jab points about 40 degrees high | m |
| Ammo pickup glint lights the area like a lamp (and nearby zombies) | m |
| Kid swarm: only 2 attack tokens, about 3 in 20 kids hang back at 3 m | m |
| Some slow zombie walks are sped up and slide; EtherionB walks 23 degrees off its travel | m |
| Vendor swing and death timers ignore the per-zombie animation-rate roll (up to 9 % early or late) | m |
| Zombies sink into the ground in PostApo (`AHoverZombie`, recording 0:24) | m |
| Small-gun muzzle flash too hot within 20 cm (EM21, EM08) | m |
| First-person arms fill the view (`HoverView` is Exec-only; needs an FP capture to tune offset and FOV) | m |
| Brute, Kid horde round and bosses not yet seen in a rendered run with the new roster | m |

## Priority to-do (ranked, proposed; owner to confirm)

**Now**
0. In progress (owner pulled ahead 2026-10-31, "work on the 15 until I get back"): power-up models cleaned and
   imported, plus effect style options (hologram, blood magic, Niagara) for the owner to pick from.
1. Owner playtest of everything in `DONE.md`; the results re-rank this list.
2. Life Engine movement feel: measured 2026-10-31 (`Scripts/ProveLifeEngineCompare.py`); waiting on the owner's test
   to choose jump height and air control (options: match Classic, or a middle ground), then wall slide and wall runs.
3. Zombie follow-ups: rendered check of the Brute, Kid horde and bosses; foot slide; grab and tackle attacks from
   `AbductionAnimPack` (shoulder grab, grab and pull, choke, push, knockout).
4. Melee feel: spear reach and jab angle; katana feel after the owner's check.
5. Power-ups: the owner's 15 models as holograms with their effects (`POWERUP_CATALOG.md`): unlimited ammo (rare),
   Max Ammo (common, needs a model), invincibility, slow time, perfect vision, Curse, boss totem, sprint, health.

**Next**
6. Ammo economy: buy points (staged in `Scripts/AuthorNukeAmmoStations.py`, waiting on the owner), glint toned down.
7. Weather: migrate Dreamrise from `M:\MultiplayerDynamicWeather`, rain/snow toggle in the menu (owner: after the big
   bugs).
8. ZESP in-game settings menu in the pause menu: the owner says what it should expose.
9. Vehicles: drivable Doomsday pickup (owner adds the pack to the project); gas can if rides need fuel.
10. Dead-body poses: corpse dressing and dormant ambush zombies that rise (owner adds the Unreal Engine format).
11. Visuals: rifle at 4K (owner re-exports GUN.spp at 4096), first-person arms, small-gun flash.

**Later**
- Tacticals: Silk spider drone with modes (tabled by the owner): mini-nuke hunter, electrical defence field, healing
  pulse waves for nearby players; trap-pod pickup grants a charge, also in the shop; toxic gas bomb, Blood Bomb,
  the painted Fab grenades, the other EM gun rigs as finds or buys.
- Bosses and specials: blood-magic boss (vortex telegraph, blood projectiles), thin blood haze in hordes (only if
  cheap), boss totem ally, zombies throwing spears at a player they cannot reach (rooftop, glitch spot, board).
- Power-up idea bank (owner's reference boards, 2026-10-31): Corpse Magnet, Boom Box, Ghost Snack / Zombie Buddy,
  Caffeine Overdrive, Be-Gone Cloud, Frostbite Shake, Lucky Scav Box, Hemo Burst, Static Surprise, Banshee's Whistle,
  Good Boy companion and more; listed in `POWERUP_CATALOG.md` with which owner model each could repurpose.
- Stations and economy: perks (Second Wind, Ironhide, Fast Lane, Bullseye, Hair Trigger, Marathon), wall buys,
  mystery crate, armour box, health station.
- Movement extras: a vault (needs a pack clip), motion matching locomotion option.
- Controls and HUD naming (PlayStation glyphs), tracer trial (Free Arrow Trail), EM_11 right-side camera, revolver
  cup reading as a barrel.

## Waiting on the owner

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
