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
  *AI:* `ProveLifeEngineAudio.py`; `ProveParkourLifeEngine.py`: wall-run hand-off and resume in both modes.
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

## Confirmed by the owner

(none yet)
