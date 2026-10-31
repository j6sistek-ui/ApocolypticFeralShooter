# AFS: completed work and in-game review

The one stop for everything waiting on the owner's eyes in game. Each finished item lists how it was validated by the
AI (build, headless proof, receipts, stills) and whether the owner has confirmed it in game. When the owner plays,
mark it **Confirmed**, or **Rejected** with a note, and move any rejection back into `BACKLOG.md`.

Owner column: **Pending** (not seen in game yet), **Confirmed**, **Rejected** (see note).
Receipts and stills live under `D:\AFS_Comparisons\` (local, not in git).

## Review in game: NYC Survival (`/Game/HoverPrototype/Maps/L_NYC_Survival`)

| # | Done | Item | What to check in game | AI validation | Owner |
|---|---|---|---|---|---|
| 1 | 2026-10-31 `7114ae2` | Zombie variety: 11 types (Shambler, Lurcher, Runner, Brawler, Drifter, Bog, Horror, Pirate, Plant, Etherion A/B) with their own walks, attacks, hits, deaths, voices; random skins and morphs; size and speed variation | 8+ different-looking zombies in a group; nobody walks backwards or sideways; every swing shows an attack; voices differ by type, never a wall of sound; headshot burst and death splash; some roar when they first see you | `ProveZombieDiversity.py`: 11 types, 0 % backwards, toes 2-8 deg off travel, 14/14 swings on attack clips, 124 voice lines from 65 sounds, ok=true; stills checked | Pending |
| 2 | 2026-10-31 `21eb065` | Kid swarm: truck cut out of navigation, packs from several directions | kids no longer pile into or push the truck; they come from several sides and ring Vexa | `ProveKidSwarm.py`: 0 paths through the truck, truck stays put, 7 spawners, contact 85 % (3 kids hang back, 2 attack tokens) | Pending |
| 3 | 2026-10-31 `21eb065` | Nuke presentation | zombies die in a ripple outward, banner "STREET SWEEP" (placeholder), flash, explosion, shockwave ring, short slow motion, no 999,999 number | `ProveNukeAmmo.py`: ripple monotone over 0.6 s, all feedback lines, ok=true; stills checked | Pending |
| 4 | 2026-10-31 `21eb065` | Ammo pickup readability | pickups bob and glint, pickup sound, "+30 AMMO" toast, reserve flashes (known: glint lights the area too much) | same proof: reserve 270 -> 300, toast and sound logged | Pending |
| 5 | 2026-10-31 `21eb065` | Spear melee | Y cycles to the spear (slot 4); V combo jab, thrust, swing; hold to charge a heavy thrust; hits pass through a line of zombies; katana unchanged (known: hits land beyond the visible spear head, jab points high) | `ProveSpear.py`: combo and heavy hit at the measured reach, katana sweep unchanged, ok=true | Pending |
| 6 | 2026-10-31 `a492e17`, `21eb065` | Life Engine movement, switched in F6 menu row "Movement" | feel of walk, sprint, jump with Life Engine vs Classic; wall run and wall jump still work with Life Engine on; jump pose instead of a running stride (known: Life Engine jump is much lower, no wall slide) | `ProveLifeEngineAudio.py` ok; `ProveParkourLifeEngine.py`: wall run hand-off and resume in both modes, ok=true | Pending |
| 7 | 2026-10-31 `a492e17` | Fixed-distance survival camera, sprint 680 | camera stays at the same distance except aiming (in) and sprinting (a little out); sprint no longer too fast | headless proof only (no feel check possible) | Pending |
| 8 | 2026-10-31 `a492e17` | Audio pass | gunshots (machine-gun pool on the rifle, crack on the revolver), katana whoosh and cut, footsteps by surface, wind bed | `ProveLifeEngineAudio.py`: 31-36 footsteps, swing sounds and the wind bed logged | Pending |
| 9 | 2026-10-31 `a492e17` | Corpses stay down, zombie heads not walkable | dead zombies slump instead of flying; you can't bounce on heads | built; not separately proven in a rendered run | Pending |
| 10 | 2026-10-31 `a492e17` | Katana damage window | the swing hits across most of its arc, with a cut sound on contact | `HOVER_KATANA_SWEEP` logged in proofs | Pending |
| 11 | 2026-10-31 `a492e17` | Y/G tap cycles weapons; pistol in slot 2 | tap Y to go rifle -> pistol -> spear; hold Y still calls the glider | proof cycled 1 -> 2 -> 4 | Pending |
| 12 | 2026-10-31 `21eb065` | Fill light on Vexa, texture pass | Vexa slightly brighter, zombies beside her not; console `HoverFillLight 0` / `1` to compare | `ProveVisualPass.py`: torso +54 % at 2.5 cd, zombie unchanged | Pending |

## Confirmed by the owner

(nothing yet)

## Rejected by the owner

(nothing yet)
