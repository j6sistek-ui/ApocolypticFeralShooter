# AFS: scope

AFS is a UE 5.8 project (`M:\UnrealProjects\AFS`, module `HoverFlight`) built on the Zombie Engine Studio plugin
(ZESP) with purchased content. The product in focus is **NYC Survival**: a wave-based, third-person, mortal zombie mode
on `L_NYC_Survival`, benchmarked on Black Ops 7 Zombies, played with Vexa, a DualSense pad or mouse and keyboard.

The full design is `NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md` (numeric spine, rounds, AI, gunplay, economy, equipment,
zones, HUD, roster). The current order lives in `BACKLOG.md` (the old running log is `Archive/NYC_PRIORITIES_AND_ANIMATION_NEEDS_20261029.md`).

## The project and its maps (owner, 2026-10-31)

AFS began as a sandbox: the name comes from the Advanced Flight System plugin the owner meant to test (the one thing
never built in it). Cyber City, Lakeside, PostApo and NYC Exploration, with their zombies and mechanics, are test
pads. **NYC Survival is the first map being taken further and is the product.** The test pads may be used to stage
things for evaluation (NYC Exploration first: same city and lighting as NYC Survival, no zombies). No new secret
levels unless a GPU or performance concern needs one. Keep it simple, less work. Staging is welcome there, but do
not redesign the test pads to match NYC Survival: their zombies are experimental and cannot hurt the player (Vexa is
invincible there by default), and that must stay so; no survival rules, lethal damage or new mechanics carried over.

## Owner direction

"A realistic, high-quality zombie shooter that works and feels good, then the bells and whistles." Gameplay and feel
first; placeholders are fine; the owner supplies assets (Fab packs, Painter textures, Tripo models).

## Phase after the 2026-10-31 playtest

The owner's verdict on the first full run: underwhelming, "everything except the reloading felt bugged", even with the
packs installed. The next phase is therefore **feel and believability**, in this order:

1. **Zombie animation diversity.** Every zombie currently reads the same: same vocals, backwards walking at the
   player, no attack motion. Use the inventory already on disk (ZESP, Zombie Animation Pack, Feral, Etherion,
   Lakeside retargets, Paragon) so walkers, runners, kids, brutes and bosses each move, attack, react and die
   differently.
2. **Proper behaviour.** Crowd separation and attack slots that actually hold, kids that swarm instead of clumping at
   their spawn, chase and flank, no lockstep, no bodies in the floor or the sky.
3. **Motion.** Player locomotion that feels right (the Life Engine solver is in as an A/B in NYC survival), melee that
   lands, vehicles enterable or removed from the mode, the board as the escape tool.
4. **Audio.** Guns, melee, footsteps, zombie vocals per type, ambience and weather, power-up stingers. The purchased
   and free sets are imported; wiring them is the work.
5. **VFX / SFX.** Blood (Rimaye pack), muzzle flashes per rig, tracers, nuke and explosion presentation, surface
   footstep VFX, weather (Dreamrise system lives in `M:\MultiplayerDynamicWeather`, not yet integrated).

Then P4 rounds and scaling, then P5 economy, perks (original names: Second Wind, Ironhide, Fast Lane, Bullseye,
Hair Trigger, Marathon), stations, doors, power.

## Out of scope for now

- New character bodies for SpaceSurvival (closed 2026-10-31; the three fitted bodies are parked).
- Control rebinding (owner tests the current bindings first).
- Tripo or Painter asset production unless the owner asks.

## Where things are

| What | Where |
|---|---|
| Engine | `C:\Program Files\Epic Games\UE_5.8` |
| Project | `M:\UnrealProjects\AFS` (this repo: source, scripts, docs only) |
| Purchased / generated source assets | `M:\UnrealProjects\AFS\SourceAssets\` (not in git) |
| Fab vault | `D:\FABDOWNLOADS\VaultCache\FabLibrary\` |
| Proof outputs (stills, receipts, logs) | `D:\AFS_Comparisons\<Topic>_<date>\` |
| Owner's Painter exports | Desktop and `OneDrive\Documents\Adobe\Adobe Substance 3D Painter\export` |
