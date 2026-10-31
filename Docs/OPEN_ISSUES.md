# AFS: open issues

One entry per issue, written so it can be pasted into a GitHub issue as is (title, labels, body). Status is the
state in the working copy on the date shown; "coded" means written but not yet built or proven in play.

## From the owner's 2026-10-31 playtest

### Zombies all look, sound and move the same
Labels: zombies, animation, audio. Priority: P1.
Same vocals on every type, walking backwards at the player, no visible attack motion, generic look. Needs per-type
locomotion, attack, hit-react and death sets from the packs on disk, per-type vocals (ZombieV2, Entity, Monster sets
exist), and turn-in-place or strafing so they do not back into her.

### Kid swarm clumps at its spawn
Labels: zombies, AI. Priority: P1.
Frames 5m06s and 8m40s: the kids hoard in one spot by the truck until she walks up. Check the feral kid's sight and
aggro range, the attack-slot ring for Kid role, and whether the swarm round spawns all kids at one spawner.

### Melee feel and damage window
Labels: combat, feel. Priority: P1. Status: built 2026-10-31 (swept arc, whoosh, cut sound), awaiting the owner's feel check.
Vendor single sphere trace at 0.3 s replaced by four sweeps across 0.22-0.48 s, wide radius, each zombie once per
swing. Still to judge in play; consider a hit-stop on contact and a lunge.

### Nuke kills everything with no presentation
Labels: feel, power-ups. Priority: P1.
The Nuke power-up applies 999,999 to every zombie with a generic pickup sound. Needs a banner, a screen flash, an
explosion sound from `SF_Explosives_SFX`, and a short slow-motion beat. (Corpse launch fixed separately.)

### Corpses launch into the sky
Labels: zombies, physics. Priority: P1. Status: built 2026-10-31 in the vendor plugin, not yet seen in play.
Dead-body impulse scaled with damage; no-montage deaths got an 18 m/s kick. Capped to a shove and a slump.

### Zombie heads are trampolines
Labels: physics. Priority: P1. Status: built 2026-10-31, not yet seen in play.
Capsule marked unwalkable in `AHoverCyberZombie::BeginPlay`.

### Zombies sink into the ground (PostApo)
Labels: zombies, physics. Priority: P2.
Recording 0:24 (PostApo, `AHoverZombie`): a live zombie bent over with its legs under the sand and a dead one
half-buried beside it. That level uses the older `AHoverZombie` range spawner, not the NYC class: check the mesh
offset against the capsule on that class, and the ragdoll death (capsule collision off, "Ragdoll" profile) against the
landscape. Not seen in the NYC footage.

### No ammo purchase, clip pickup unreadable
Labels: economy, HUD. Priority: P2.
Picking old clips refills but nothing shows it. Needs an ammo pickup toast and the wall-buy or MaxAmmo loop.

### No tactical items, no other weapons in the mode
Labels: equipment, weapons. Priority: P2. Status: partly coded 2026-10-31.
Owner: "Y to switch weapons, have the pistol on hand". Done in code: a tap of Y / G cycles to the next weapon on the
quickbar (hold still mounts the board); the starting kit gets the owned `DA_NYC_Pistol` (EM_08 revolver rig on the
HoverCyberRifle actor) in slot 2 with pistol ammo (`Scripts/AddStartingPistol.py`). Still missing: a way to buy or
find the other EM rigs and the tactical items (Robot Mine, horror grenades), and the frag throw's presentation.
**There are no perks, wall buys or stations in NYC Survival yet**: the mode logs them as deferred at InitGame; only
Cyber City has its three supply crates. Ammo comes from drops and the MaxAmmo power-up.

### Cannot enter cars
Labels: vehicles. Priority: P3.
The board mounts and lands; the cars do not. Decide: enterable or removed from the mode.

### ZESP in-game settings menu missing from the pause menu
Labels: UI. Priority: P3.
Clarify what the owner wants exposed (wave settings, difficulty, graphics) and whether the vendor widget exists.

### Engine light warning on every frame
Labels: level. Priority: P2. Status: fixed 2026-10-31 (`Scripts/FixNYCLights.py` ran: DirectionalLight4 priority 1, AtmosphericDirectionalLight2 0).
Two directional lights compete for forward shading priority in `L_NYC_Survival`.

### First-person arms fill the view
Labels: camera. Priority: P3.
`HoverView` is Exec-only; needs BlueprintCallable and an FP capture to tune the arm offset and FOV.

### Ammo pickup reads as a mystery red thing on the ground
Labels: economy, HUD. Priority: P2.
Recording 5:37-5:42: out of ammo, she chases a small red object on the ground, touches it, "RELOADING" appears. No
toast, no icon, no sound. Same fix as the ammo readout issue: pickup toast, a glint or outline, the item-pickup sound
that is already imported (`A_ItemPickup_001-004`).

### Visual quality pass: gun and player resolution, light on the player
Labels: visuals. Priority: P2. Owner 2026-10-31: "can the gun and player be in higher resolution? maybe the lighting
on the player just a bit. Any way to enhance visual quality (it's not that bad, I just want to see how far I can
take it)". Steps: audit the texture size caps on Vexa's skin MIs, the M4A1 Painter set and the EM rigs (runtime was
capped at 1K-2K by the saved graphics setting and per-texture MaxTextureSize), raise the streaming pool for the
near-camera set, check LOD bias on the gun and the view arms, Nanite or tessellation where it is cheap; a character
fill or rim light on its own lighting channel attached to the pilot (low intensity, no shadows); a measured before
and after at the owner's settings. Keep the 6 GB VRAM budget while the owner games.

## Carried over (before the playtest)

### Small-gun muzzle flash still hot within 20 cm (EM21, EM08)
Labels: vfx. Priority: P3. Status: source radius built, not re-captured.

### Life Engine locomotion A/B in NYC survival
Labels: motion. Priority: P2. Status: built 2026-10-31, on by default in NYC Survival; toggle with `LifeEngine 0/1` in the console. Headless proof `Scripts/ProveLifeEngineAudio.py` walks, jumps, sprints and swings with the solver on then off.

### Audio pass
Labels: audio. Priority: P1. Status: built 2026-10-31, not yet heard by the owner. WW2 machine-gun pools, sniper crack on the revolver,
katana whoosh and cut, code-driven footsteps on the walk and run sets, wind bed under the crowd ambience.

### Blood Bomb core, Fab grenade import after painting, blood haze in hordes, blood-magic boss, Robot Mine
Labels: equipment, vfx. Priority: P3. Waiting on the owner for the Blood Bomb and the painted grenades.

### Dreamrise weather integration
Labels: vfx, level. Priority: P4. The system lives in its own project; migrate the manager and tie it to the wind bed.

### Controls and HUD naming (PlayStation glyphs, NYC vs PostApo differences)
Labels: UI. Priority: P3. After the owner's binding test.

### Tracer trial, EM_11 right-side camera, revolver cup reads as barrel
Labels: vfx, animation. Priority: P4.
