# AFS: backlog

The one list of everything the game needs: bugs, the ranked to-do list, and decisions waiting on the owner. Updated
the same day an idea, piece of feedback or result comes in, and pushed. Last update: 2026-10-31.

## How this list is used (owner rule, 2026-10-31)

- This list is maintained above everything else. Every new idea, bug or piece of feedback lands here, ranked.
- When the owner raises something that is not game-breaking, confirm its priority (where it slots in the ranking).
- When the owner asks for it to be done now, name the current top task and confirm the owner wants to pull the new
  item ahead of it before starting.
- Game-breaking bugs (crash, softlock, can't play the mode) go straight to the top.
- Keep the repo simple: design, issues, needs and context come first.
- Finished work moves to `DONE.md` with its validation and an owner column (Pending / Confirmed / Rejected); a
  rejection comes back here.

## Bugs

Severity: **G** game-breaking, **M** major (hurts play), **m** minor. "Fixed" = built and proven headless, waiting
for the owner's playtest.

| Bug | Sev | Status |
|---|---|---|
| Life Engine jump peaks at 111 cm vs 251 cm on classic movement | M | open |
| Life Engine: running into a wall at an angle stops dead (no wall slide); template wall runs are very short | M | open |
| Spear hits at 1.7-3.4 m while the visible head reaches about 1 m; jab points about 40 degrees high | m | open |
| Ammo pickup glint light floods the area like a lamp (and lights zombies) | m | open |
| Kid swarm: only 2 attack tokens, about 3 in 20 kids hang back at 3 m | m | open (design call) |
| Some slow zombie walks are sped up and slide; EtherionB walks 23 degrees off travel | m | open |
| Vendor swing and death timers ignore the per-zombie animation-rate roll (up to 9 % early/late) | m | open |
| Zombies sink into the ground in PostApo | m | open |
| Small-gun muzzle flash too hot within 20 cm (EM21, EM08) | m | open |
| First-person arms fill the view | m | open |
| Brute, Kid horde round and bosses not yet seen in a rendered run with the new roster | m | unverified |
| Zombies all look/sound/move the same; moonwalking zombies | M | fixed |
| Kids pile into the truck at their spawn | M | fixed (contact 85 %) |
| Corpses launch into the sky; zombie heads are trampolines | M | fixed |
| Nuke kills everything with no presentation / 999,999 number | M | fixed |
| Ammo pickup unreadable | m | fixed |
| Melee damage window too small, no hit read | M | fixed |
| No audio (guns, melee, footsteps) | M | fixed |
| Survival camera distance drifts | m | fixed |
| Light warning on every frame | m | fixed |

## Priority to-do (ranked)

**Now**
1. Owner playtest of the 2026-10-31 builds: zombie variety and behaviour, kid swarm, Nuke and ammo, spear, Life
   Engine with parkour, fill light. Their feedback re-ranks everything below.
2. Life Engine movement feel: jump height, wall slide, wall runs (the owner's stated focus: "the Life Engine drives").
3. Zombie follow-ups: rendered check of Brute, Kid horde and bosses; foot slide; grab and tackle attacks from
   `AbductionAnimPack`.
4. Melee feel: katana judged in play; spear reach and jab angle.
5. Power-ups: the 15 owner models as holograms and the new effects per `POWERUP_CATALOG.md` (unlimited ammo,
   invincibility, slow time, perfect vision, Curse, boss totem, sprint), Max Ammo as the common drop.

**Next**
6. Ammo economy: buy points (staged, waiting on the owner's OK), glint toned down.
7. Weather: Dreamrise (`M:\MultiplayerDynamicWeather`) migrated, rain/snow toggle in the menu (owner: after the big
   bugs).
8. ZESP in-game settings menu in the pause menu (needs the owner to say what it should expose).
9. Vehicles: the Doomsday pickup drivable (owner adds the pack to the project), gas can idea.
10. Dead-body poses: corpse dressing and dormant ambush zombies (owner adds the Unreal Engine format of the pack).
11. Visuals: rifle at 4K (owner re-exports GUN.spp at 4096), first-person arms, small-gun flash.

**Later**
- Tacticals: Silk spider drone / Robot Mine, toxic gas bomb, Blood Bomb, Fab grenades after painting.
- Bosses and specials: blood-magic boss, blood haze in hordes, boss totem ally, zombies throwing spears at an
  unreachable player.
- Stations and economy: perks (Second Wind, Ironhide, Fast Lane, Bullseye, Hair Trigger, Marathon), wall buys,
  mystery crate, armour box, health station.
- Movement extras: a vault (needs a pack clip), motion matching locomotion option.
- Controls and HUD naming (PlayStation glyphs), tracer trial, EM_11 right-side camera, revolver cup.

## Waiting on the owner

- Ammo buy points: place 2-3 in NYC (reusing Cyber City's supply crate)? Price?
- Kid swarm: truck to the Garage? a closer horde-only spawn band? more horde attack tokens?
- Nuke banner text (placeholder "STREET SWEEP"); keep the slow-motion beat?
- Vault: wanted? which pack clip?
- Spear: generous reach or match the visible head? damage numbers? slot 4 or a pickup later?
- Fill light: 2.5 cd "just a bit", or lower?
- Rifle 4K: re-export GUN.spp at 4096 from Painter.
- Doomsday pickup and Dead Bodies poses: add the Unreal Engine format to the project.

## Details

One entry per issue, written so it can be pasted into a GitHub issue as is. Status is the state on the date shown.

### From the owner's 2026-10-31 playtest

#### Zombies all look, sound and move the same
Labels: zombies, animation, audio. Priority: P1. Status: built and proven headless 2026-10-31, waiting for the owner's
playtest. Proof (`Scripts/ProveZombieDiversity.py`, `D:/AFS_Comparisons/ZombieDiversity_20261031/proof.json`): 11
standard types seen in rounds 1-4 (Shambler, Lurcher, Runner, Brawler, Drifter, Bog, Horror, Pirate, Plant, Etherion
A/B), 15 body+skin looks, 0% backwards, toes within 2-8 deg of travel (EtherionB 23), every swing on an attack
montage (13 distinct), 124 vocal lines from 65 sounds under a 6-voice budget, footsteps, headshot and death blood,
sight roars. The real moonwalk was the mesh, not the actor: the Standard bodies' toes pointed 178 deg from travel;
each definition now carries an authored MeshYawOffset. Open: Brute, Kid horde and bosses not yet seen rendered; some
foot sliding on slow walks scaled up; vendor swing/death timers ignore the per-zombie anim-rate roll; body-hit blood
uses the old NS_NS1_BloodShot (P_BigSplash_Hit drew a flat red disc).
Root causes found 2026-10-31: the four standards and the Brute share one blend space, two attacks, one hit and one
death; every vocal field is empty; the NYC zombie had bUseControllerRotationYaw on with orient-to-movement, so it
faced the player while crowd steering moved it (the moonwalk); Etherion montages use a "FullBody" slot the vendor ABP
lacks. Every roster skeleton shares the 61 core mannequin bones with all four zombie packs, so pack clips play through
compatible skeletons without retargeting. Owner 2026-10-31: "at least 5-10 usable zombies for diversity in the
group. I saw 2-3". Plan: 10+ NYC standard definitions (four standards, four Lakeside bodies, two Etherion bodies with
random skins and morphs, optionally the ZombieMale body) each with its own gait, attacks, hits, deaths and voice
palette; per-zombie scale, anim-rate, skin and morph variation; budgeted voices and footsteps; Blood_VFX_Pack hits,
headshots and death splashes; sight roars; facing fix. Scripts: `InventoryZombieAssets.py`, `ProbeZombieRigs.py`,
`AuthorZombieDiversity.py`, `ProveZombieDiversity.py`; receipts in `D:/AFS_Comparisons/ZombieDiversity_20261031/`.
Same vocals on every type, walking backwards at the player, no visible attack motion, generic look. Needs per-type
locomotion, attack, hit-react and death sets from the packs on disk, per-type vocals (ZombieV2, Entity, Monster sets
exist), and turn-in-place or strafing so they do not back into her.

#### Kid swarm clumps at its spawn
Labels: zombies, AI. Priority: P1.
Status 2026-10-31: fixed and proven in part (`Scripts/ProveKidSwarm.py`). Root cause: the parked pickup at
AFS_TruckStart is spawned after the navmesh exists, so kids pathed into it and shoved it about 5.5 m onto Vexa; every
horde spawner left by the 1400 cm minimum sits behind it. Now the truck is cut out of the navmesh at runtime (0 paths
through it, truck stays put), horde packs spread by bearing (7 spawners), stalled zombies get detours. Still: only 2
horde attack tokens, so 3 of 20 kids hold the queue ring at about 3 m (contact 85 %). Owner calls: truck to the Garage?
a closer horde-only spawn band? more horde tokens?
Frames 5m06s and 8m40s: the kids hoard in one spot by the truck until she walks up. Check the feral kid's sight and
aggro range, the attack-slot ring for Kid role, and whether the swarm round spawns all kids at one spawner.

#### Melee feel and damage window
Labels: combat, feel. Priority: P1. Status: built 2026-10-31 (swept arc, whoosh, cut sound), awaiting the owner's feel check.
Vendor single sphere trace at 0.3 s replaced by four sweeps across 0.22-0.48 s, wide radius, each zombie once per
swing. Still to judge in play; consider a hit-stop on contact and a lunge.

#### Nuke kills everything with no presentation
Labels: feel, power-ups. Priority: P1.
Status 2026-10-31: built and proven (`Scripts/ProveNukeAmmo.py`): ripple kills outward over about 0.6 s, banner
(placeholder text "STREET SWEEP"), flash, explosion, shockwave ring, shake, rumble, 0.35 s slow motion, no damage
numbers. Owner design (POWERUP_CATALOG.md) later: ticking pickup animation, bosses take heavy damage instead of dying.
The Nuke power-up applies 999,999 to every zombie with a generic pickup sound. Needs a banner, a screen flash, an
explosion sound from `SF_Explosives_SFX`, and a short slow-motion beat. (Corpse launch fixed separately.)

#### Corpses launch into the sky
Labels: zombies, physics. Priority: P1. Status: built 2026-10-31 in the vendor plugin, not yet seen in play.
Dead-body impulse scaled with damage; no-montage deaths got an 18 m/s kick. Capped to a shove and a slump.

#### Zombie heads are trampolines
Labels: physics. Priority: P1. Status: built 2026-10-31, not yet seen in play.
Capsule marked unwalkable in `AHoverCyberZombie::BeginPlay` (character movement path). The Life Engine solver sweeps on
ECC_Pawn and would stand on a zombie regardless, so it now refuses pawns as floor, slide surface and step target
(`IsPawnHit` in the plugin). The owner suspects the parkour pack's mantle too; if the bounce persists with the solver
on, that is the next place to look.

#### Zombies sink into the ground (PostApo)
Labels: zombies, physics. Priority: P2.
Recording 0:24 (PostApo, `AHoverZombie`): a live zombie bent over with its legs under the sand and a dead one
half-buried beside it. That level uses the older `AHoverZombie` range spawner, not the NYC class: check the mesh
offset against the capsule on that class, and the ragdoll death (capsule collision off, "Ragdoll" profile) against the
landscape. Not seen in the NYC footage.

#### No ammo purchase, clip pickup unreadable
Labels: economy, HUD. Priority: P2.
Status 2026-10-31: pickup readability built and proven: bob/spin, glint, pickup sound, "+N AMMO" toast, reserve
flash. Flaw: the glint light acts like a lamp (lights the barrier and grass, and nearby zombies); tone down. Ammo buy
points (reusing the Cyber City supply crate, `Scripts/AuthorNukeAmmoStations.py`) are staged but NOT placed: owner OK
pending.
Picking old clips refills but nothing shows it. Needs an ammo pickup toast and the wall-buy or MaxAmmo loop.

#### No tactical items, no other weapons in the mode
Labels: equipment, weapons. Priority: P2. Status: partly coded 2026-10-31.
Owner: "Y to switch weapons, have the pistol on hand". Done in code: a tap of Y / G cycles to the next weapon on the
quickbar (hold still mounts the board); the starting kit gets the owned `DA_NYC_Pistol` (EM_08 revolver rig on the
HoverCyberRifle actor) in slot 2 with pistol ammo (`Scripts/AddStartingPistol.py`). Still missing: a way to buy or
find the other EM rigs and the tactical items (Robot Mine, horror grenades), and the frag throw's presentation.
**There are no perks, wall buys or stations in NYC Survival yet**: the mode logs them as deferred at InitGame; only
Cyber City has its three supply crates. Ammo comes from drops and the MaxAmmo power-up.

#### Idea: zombies throw spears at an unreachable player
Labels: zombies, AI, idea. Priority: P3. Owner 2026-10-31: "maybe zombies can throw spears later on, or if you're too
high / glitch / hoverboard". An anti-camping answer: when no nav path reaches Vexa for a few seconds (rooftop, glitch
spot, hovering on the board), a nearby zombie throws a spear with `SpearAnimationsV2` A_1H_Throw. Later, not now.

#### Cannot enter cars
Labels: vehicles. Priority: P3.
The board mounts and lands; the cars do not. Decide: enterable or removed from the mode.

#### ZESP in-game settings menu missing from the pause menu
Labels: UI. Priority: P3.
Clarify what the owner wants exposed (wave settings, difficulty, graphics) and whether the vendor widget exists.

#### Engine light warning on every frame
Labels: level. Priority: P2. Status: fixed 2026-10-31 (`Scripts/FixNYCLights.py` ran: DirectionalLight4 priority 1, AtmosphericDirectionalLight2 0).
Two directional lights compete for forward shading priority in `L_NYC_Survival`.

#### Survival camera distance drifts with speed
Labels: camera. Priority: P2. Status: built 2026-10-31, not yet seen in play.
Owner: "the camera needs to stay at a fixed distance almost, except zooming or maybe sprinting". The spring arm's
positional lag (up to 60 cm) is off; the arm is 300 at rest, 210 aiming, 340 sprinting, interpolated at 6/s.

#### Spear melee weapon
Labels: weapons, melee. Priority: P2. Status 2026-10-31: built and proven (`Scripts/AuthorSpear.py`,
`Scripts/ProveSpear.py`): quickbar slot 4 through the Y/G cycle, Jab -> Thrust -> Swing combo, charged heavy thrust,
piercing sweeps, shared strike path (katana values unchanged). Gaps: the visible spear head reaches about 0.9-1.2 m
while the sweeps hit at 1.7-3.4 m; upper body only (the pack's lunge is lost); the jab points about 40 degrees high.

#### Visual pass: fill light and texture groups
Labels: visuals. Priority: P3. Status 2026-10-31: a 2.5 cd fill light on lighting channel 1 lights only Vexa (torso
+54 %, a zombie beside her unchanged; console `HoverFillLight 0|1 [cd]`); `Scripts/VisualQualityPass.py` set 126
texture groups/caps (revertable with --revert). The rifle stays 2K until GUN.spp is re-exported at 4096.

#### First-person arms fill the view
Labels: camera. Priority: P3.
`HoverView` is Exec-only; needs BlueprintCallable and an FP capture to tune the arm offset and FOV.

#### Ammo pickup reads as a mystery red thing on the ground
Labels: economy, HUD. Priority: P2.
Recording 5:37-5:42: out of ammo, she chases a small red object on the ground, touches it, "RELOADING" appears. No
toast, no icon, no sound. Same fix as the ammo readout issue: pickup toast, a glint or outline, the item-pickup sound
that is already imported (`A_ItemPickup_001-004`).

#### Visual quality pass: gun and player resolution, light on the player
Labels: visuals. Priority: P2. Owner 2026-10-31: "can the gun and player be in higher resolution? maybe the lighting
on the player just a bit. Any way to enhance visual quality (it's not that bad, I just want to see how far I can
take it)". Steps: audit the texture size caps on Vexa's skin MIs, the M4A1 Painter set and the EM rigs (runtime was
capped at 1K-2K by the saved graphics setting and per-texture MaxTextureSize), raise the streaming pool for the
near-camera set, check LOD bias on the gun and the view arms, Nanite or tessellation where it is cheap; a character
fill or rim light on its own lighting channel attached to the pilot (low intensity, no shadows); a measured before
and after at the owner's settings. Keep the 6 GB VRAM budget while the owner games.

### Carried over (before the playtest)

#### Small-gun muzzle flash still hot within 20 cm (EM21, EM08)
Labels: vfx. Priority: P3. Status: source radius built, not re-captured.

#### Life Engine x parkour template
Labels: motion. Priority: P2. Status 2026-10-31: the template had no way to see Vexa airborne under the solver
(CharacterMovement in MOVE_None reports neither falling nor grounded), so wall runs, wall jumps and jump poses never
fired. UHoverMovementComponent now reports the solver's ground state; the solver yields on the template's
`IsWallRunning?` flag and resumes on landing (`Scripts/ProveParkourLifeEngine.py`). Weak spots: the template's wall
runs are very short in both modes; a 30 degree run at a wall stops dead under the solver (it does not slide along
walls); the solver's jump peaks at 111 cm against 251 cm with classic movement. There is no vault anywhere in the
pack or AFS.

#### Life Engine locomotion A/B in NYC survival
Labels: motion. Priority: P2. Status: built and proven 2026-10-31, on by default in NYC Survival; switch it in the F6
menu ("Movement" row; `LifeEngine 0/1` also works as a console command). Headless proof `Scripts/ProveLifeEngineAudio.py` walks, jumps, sprints and swings with
the solver on then off (receipt `D:/AFS_Comparisons/LifeEngine_20261031/proof.json`). Fixed along the way: the parkour
pawn was excluded outright (now the template only takes over mid-move); long frames are substepped; a start-penetrating
ground sweep took a wall as the floor (line-trace fallback); the snap-down left a zero floor normal; the slide used the
face normal, so the corner of the start barrier stripped her to 15 cm/s for 0.7 s (now the sweep normal: one glancing
contact, back to 500 in 0.3 s); step-up covers any non-walkable face and retries while input is held. Switch: F6 /
D-pad Up menu, row "Movement". Owner 2026-10-31: the solver drives, the parkour animations and wall run / jump stay
(not yet checked in play with the solver on: whether the template still triggers vaults and wall runs).

#### Audio pass
Labels: audio. Priority: P1. Status: built 2026-10-31, not yet heard by the owner. WW2 machine-gun pools, sniper crack on the revolver,
katana whoosh and cut, code-driven footsteps on the walk and run sets, wind bed under the crowd ambience.

#### Blood Bomb core, Fab grenade import after painting, blood haze in hordes, blood-magic boss, Robot Mine
Labels: equipment, vfx. Priority: P3. Waiting on the owner for the Blood Bomb and the painted grenades.

#### Dreamrise weather integration with a menu toggle (rain / snow)
Labels: vfx, level, UI. Priority: P3. Owner 2026-10-31: "Menu toggle, rain/snow. But do that after the big bugs."
The system lives in its own project (`M:\MultiplayerDynamicWeather`); migrate the manager into AFS, place it in
`L_NYC_Survival`, expose a pause-menu toggle (off / rain / snow) and tie the rain to the wind bed. After the P1 list.

#### Controls and HUD naming (PlayStation glyphs, NYC vs PostApo differences)
Labels: UI. Priority: P3. After the owner's binding test.

#### Tracer trial, EM_11 right-side camera, revolver cup reads as barrel
Labels: vfx, animation. Priority: P4.
