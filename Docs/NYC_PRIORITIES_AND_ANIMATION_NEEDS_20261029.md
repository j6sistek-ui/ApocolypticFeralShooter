# NYC Survival: reordered priorities and animation needs (2026-10-29)

Owner direction: "a realistic, high-quality zombie shooter that works and feels good, then the bells and whistles." Priority is map layout, spawns, zombie behaviour, and weapons plus animations for zombies, player and guns. Upgrade assets (perks, Pack-a-Punch, armor, stations) come later. This reorders Section 11 of `NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md`; the designs themselves are unchanged.

## 1. Build order (replaces the M0-M6 sequence)

| Phase | Scope | Design doc sections | Done when |
|---|---|---|---|
| **P1 Map, nav, spawns** | New owned map `L_NYC_Survival` on the vendor sublevels; navmesh and `AddCityNavigation` past its world gate; 25 spawners in door-less zone volumes (zones exist as spawn pools only, no doors yet); spawn director with the 14-100 m gate, visibility cone, stall guard, straggler re-queue, ground-emerge spawners in the Underpass | 2, 3, 8 (spawner pools only) | Rounds run on NYC for 30 rounds unattended with no deadlock, no visible pop-in, no straggler timeouts |
| **P2 Zombie behaviour** | Crowd separation and the attack-slot ring, speed tiers by round roll, flinch rules, chase retarget, horde rounds with the Kid crawler, Brute heavy rounds, dismemberment hooks, corpse lifespans | 4, 3.4 | 24 concurrent zombies surround without stacking, crawlers reach the player, no lockstep |
| **P3 Weapons and animation** | Gunplay feel (camera shake, recoil, rumble, hit marker, tracer, penetration, kill punctuation) on the Ballista and the modular M4A1 showcase; player third-person rifle set; zombie clip integration including crawl; weapon-side bolt, charging handle and magazine motion | 5, 10 | Shooting feels right on a pad and mouse at 60 fps with 24 zombies |
| **P4 Rounds and scaling** | Health curve, counts, intermission, boss rounds (StoneGolem, Giant Kid), heavy rounds | 1, 3 | R1-R30 pacing matches the spine tables |
| **P5 Economy and stations** | Points, perks, Pack-a-Punch, armor, doors, power, Shelter, HUD polish | 6, 7, 8 doors, 9 | Loop complete |

P1 and P2 can run on Opus; P3 gunplay tuning and the animation integration are the hard parts.

## 2. Zombie animation inventory (verified on disk 2026-10-29)

| Pack (skeleton) | Locomotion | Attacks | Reacts / deaths | Special |
|---|---|---|---|---|
| ZESP `Zombie_001` (Manny) | idle, walk, run, `BS_Zombie_WalkRun` | 2 attacks | hit, death | `ABP_ZombieMaster` drives every body |
| Zombie Animation Pack (UE4 + UE5 mannequin) | walk A-C, run A, idle A-B | attack A-D | taking damage A-F, impaled A-B | **belly crawl A-B**, laying idle A-B, **ground burst A-K (11)** |
| Feral Zombie (UE4 mannequin) | walk x2, run | swipe L/R, combo, strong x3, leap short/full | hit react x4, death x2 | reanimate, feasting x3, roar x2, sniff, look L/R, idle x3 |
| Etherion Zombie (Manny) | idle x4, walk, slow, sneak, **giant walk**, jog, run x2 | bash, slash, wide loops, kick | none | roar |
| Lakeside retargets (owner) | 182 clips: the vendor set and ZAP set already retargeted onto Horror, BogZombie and the other Lakeside bodies | | | `IK_Horror`, `IK_BogZombie` |
| Brute (owner) | | stomp, smash | | |
| ZombieMale_AAB | motion-matching idle/walk/run/jump | none | none | dismemberment body |

**Crawling: yes, two kinds.**

- **Fast all-fours crawl (Feral pack).** Correction 2026-10-29: the Feral Zombie Animations set (Excalibur Studios) is an all-fours feral; its store art shows every figure on hands and feet, and its clip lengths fit a scurry (Run 0.5 s, Walk 0.73 s). So Feral `Walk`/`Walk_02`/`Run`/`Idle_01-03` are the fast crawl locomotion the owner wants for the Kid, and the set already carries the moves a crawler state needs: `LeapForward_Short` (pounce = crawl attack), `Attack_LeftSwipe/RightSwipe` from the low stance, `HitReact_01-04`, `Death_01/02`, `Reanimate` (rise from the ground), `Feasting_01-03`. **Confirmed 2026-10-29 by an offscreen in-engine render** (`Scripts/ReviewFeralPoses.py`, 39 frames under `Saved/Automation/ZombieEngine/feral_poses/`): Run is a four-limbed bounding gallop, Idle a crouched ape stance, the short leap a full-body lunge, Walk a low hunched two-legged stalk, Reanimate a rise from prone. If confirmed, the Kid crawler is fully covered by Feral alone and keeps the vendor run as its upright gait. **Owner decision 2026-10-29: the Kid does not have to crawl; the feral look and feel is the idea.** The horde Kid is therefore a feral: Feral locomotion (all-fours scurry), pounce and swipe attacks, Feral hit reacts and deaths, Reanimate as its spawn-in. Section 10's "crawler" capsule and attack-height notes apply to this low all-fours stance, not to a belly crawl; the belly-crawl set stays for dismembered standard bodies and ground-emerge spawns only.
- **Belly crawl (Zombie Animation Pack: Standard, QuokkaVoid).** Two belly-crawl loops, two laying idles, ten ground-burst emergence clips and two impaled poses, on both mannequin skeletons. This is the legless/dismembered crawler for any standard body, and the Underpass ground-emerge spawns.

Both retarget to every body through the same compatible-skeleton registration the Cyber bodies already use.

- **Owner's custom Kid crawl (for the record, 2026-10-29).** `SourceAssets/Kid_CrawlAnimation_20261029/Kid_crawl_v1.glb` (in place) and `Kid_crawl_v2.glb` (root motion, 0.89 m travel): the old-texture Tripo Kid with two clips on the Kid's own 61-bone rig, "Crawl on hands and knees" (240 frames, 10 s loopable) and "Get down on hands and knees, then crawl forward" (216 frames, 9 s: a standing-to-crawl transition plus crawl). Frame renders beside the files confirm a real hands-and-knees crawl. Because the rig matches `SK_Kid`'s source skeleton bone for bone, the clips import straight onto `SK_Kid_Skeleton` without retargeting. Use: the "get down" clip is the knockdown-into-crawl transition the packs lack (for the Kid), and the loop is a slower alternative to the Feral scurry. Mesh and texture in these files are superseded; take only the animations.

**What is still missing** (only for the belly crawler; the Feral set covers the all-fours one):

1. Crawl attack (a low reach or bite from the belly pose).
2. Crawl death (the Feral deaths are 0.5-0.6 s standing drops).
3. Knockdown into crawl (legs blown off or kneecapped: standing to prone transition).
4. Crawl hit react and a crawl turn in place.

Options, in order of preference:

- **Buy a crawler set** if one exists on Fab for the UE mannequin (search "zombie crawler", "crawling zombie animations"); about four clips are needed, and a bought set is faster and better than hand-keying.
- **Author in Blender** from the ZAP crawl loop: a 20-frame reach, a prone death to ragdoll, and the knockdown as a short keyed fall into the laying idle. I can do this headless; quality is "serviceable", not mocap.
- **Ragdoll stand-ins**: crawl death as a physics blend straight from the crawl pose (no clip needed); knockdown as a ragdoll fall that settles into the laying idle, then the crawl loop takes over.

Plan: buy if available, otherwise author the attack and knockdown and ragdoll the death. The Kid uses the same crawl set at its scale and keeps the vendor run, so it is not crawl-only.

## 3. Player (Vexa, third person) animation sources

In the project already (ZESP player set, Manny): pistol and M16 locomotion blendspaces for third and first person, aim offsets, fire and reload and equip montages, unarmed crouch set with starts and stops, knife and grenade throw, and the motion-matching pose databases for crouch and M16 crouch. The CLS motion-matching system and the Parkour pack cover traversal.

In the Fab vault, not yet imported: **Pistol and Rifle Locomotion 1700** (858 FBX files, GASP-compatible: the full rifle and pistol locomotion set with starts, stops, pivots, turns, aim sweeps, crouch, sprint) and **Paragon animations retargeted to Manny** (923 FBX: melee, hit reacts, deaths, dodges). Together they close the gaps below.

Gaps to fill: rifle hit reacts (Paragon), downed state crawl and self-revive (Paragon crawl or the ZAP crawl on Manny), rifle melee bash (Paragon melee), sprint-to-aim and weapon-swap transitions (Rifle Locomotion pack), vault and mantle (Parkour pack, already in).

## 4. Guns

The modular M4A1 ships no animations. Weapon motion is component-driven in code: bolt carrier and charging handle offset on fire, magazine detach and re-attach on reload, muzzle and ejection sockets added on import. The player-side reload and equip use the ZESP M16 montages until the Rifle Locomotion pack is in. Muzzle flash, shells, tracers and impacts come from the Sci-Fi Weapons VFX pack, Vefects and the arrow trail already in the project. The 30 EM guns are single static meshes and follow the same path.

## 4b. First NYC run findings (2026-10-29 evening)

- `L_NYC_Survival` authored (25 spawners, 7 zones, nav bounds, survival start, NYC game mode as default). Five-round CPU verification: 53 spawns, all arrived except two round-one timeouts, median arrival 8-11 s, zero stalls, zero stragglers; exploration map still zombie-free. Counts came from the Cyber wave data because `DA_NYCWaves` / `DA_NYCEncounters` did not exist yet (`Scripts/AuthorNYCData.py` creates them).
- **Camera bug to fix in P3:** zombies ignore the camera probe (by design, so the arm never snaps in), so a zombie standing at the camera position fills the lens with its body. Fix = near-camera dither fade on zombie materials (distance-to-camera opacity mask in the zombie master materials, ~60 cm) plus a 10 cm near clip; optionally the spring arm pulls in only for world geometry as now.
- `BindNYCNav.py` binds the map's nav config to `UHoverNYCNavigationSystem` (the Python route is `load_class` on the module config class + `make_soft_class_path`); the director now accepts bare zone tags.
- Kid textures raised to a 2K runtime cap (`Scripts/SetKidTexture2K.py`, receipt under Saved/HoverPrototype/KidTexture2K).

## 4c. Kid on Feral clips (2026-10-29, done)

`Scripts/ReviewKidFeral.py` registered the Feral `UE4_Mannequin_Skeleton` as a compatible skeleton on `SK_Kid_Skeleton` (saved; the only asset touched, hashes in `Saved/Automation/ZombieEngine/kid_feral/review.json`) and rendered the Kid mesh on Feral Run / Walk / Idle / pounce / swipe / Reanimate / Death: all 21 frames play cleanly on the Kid with no retarget. Next: point `DA_Kid` (or a NYC copy) at the Feral clips for its montages and blendspace, set the horde role, and the Kid feral is in the game. The second verification run already produced a 20-strong horde round at round five using the Kid definition.

## 4d. Phase two results (2026-10-29, late)

- **Near-camera fade** applied to the six NYC zombie materials (`Scripts/AddZombieCameraFade.py`: CameraDepthFade -> DitherTemporalAA -> OpacityMask, Masked blend, scalar params NYC_FadeLength 70 / NYC_FadeOffset 15). Every mesh slot was confirmed to resolve to `M_<Name>_0`, so the Section 10 "missing M_<Name>" worry is closed. Cyber City bodies share these materials and fade too. Rendered proof pending (`Scripts/CaptureNearCameraFade.py`).
- **Kid feral** (`Scripts/AuthorKidFeral.py`): `/Game/HoverPrototype/NYC/Zombies/DA_NYC_Kid` + `BS_NYC_Kid_Feral` (Idle_01 0 / Walk 300 / Run 650) + montages Pounce, Swipe_L/R (UpperBody slot), Hit_01-04, Death_01/02, Rise (DefaultSlot). Bound as the horde Kid.
- **Bosses** (`Scripts/AuthorNYCBosses.py`): `Variants/Golem/` holds the six imported Substance textures (2K cap), `M_Golem` master, `MI_Golem_Body/Armor`, `SKEL_Golem` (compatible with ZESP SK_Mannequin), `Optimized/SK_Golem_LODs` (4 LODs, 31.8k/17.5k/7.9k/3.8k tris), `AM_Golem_Attack_Light_A/B`, `AM_Golem_Slam`, `AM_Golem_Hit`, `AM_Golem_Death`, `AM_Golem_Intro`, `BS_Golem_WalkRun`, `DA_StoneGolem` (errata values). `Variants/Kid/DA_GiantKid` + `AM_GiantKid_*` from the Feral clips. Boss attack montages are on DefaultSlot (full body) on purpose. Bound: rounds 13 / 19 / 27.
- **Audio**: 127 SoundWaves under `/Game/HoverPrototype/Audio/NYC/` (cyberpunk rifle x2, pistol x2, shotgun, sniper; WW2 machine gun + tails, WW2 rifle; crowd loops x7; feeding loops x6; footsteps 5 sets; vehicles 2 sets; hit metal-wound, katana cut/sharpen, first aid, item pickup). Wired in code: per-tier random fire pools (WW2 machine gun on the M16 tiers, cyberpunk rifles on the Ballista, pistol on the sidearm), tail pools, hit-confirm pool with headshot/kill pitch, crowd ambience by alive-count band with the aggressive loop on horde rounds. Not yet wired: footsteps, vehicles, feeding (data only), katana, first aid, pickup. 5.8 gotcha: `set_material_instance_texture_parameter_value` returns False; write `texture_parameter_values` directly.
- **UE 5.8 Python gotchas collected**: no NavigationSystemModuleConfig type (use load_class), no make_soft_class_path (assign SoftClassPath / class), `ConfigureCreatureLODs` exports as `configure_creature_lo_ds`, export text omits struct-default members (parse with defaults), montage/blendspace factories work with target_skeleton + source_animation.

## 4e. Phase two proof runs (2026-10-29, night)

- Verification run 3 (with DA_NYC_Kid, bosses bound): rounds 6/8/13/18/20 all complete, horde round arrival 4.2 s median (feral speed), zero stalls, nav check green.
- **Near-camera fade proven**: `near_camera_fade/fade_000cm.png` (invisible at the lens), `fade_040cm.png` (dithered ghost), `fade_150cm.png` (solid). Player-camera frames in `captures/round_*_player.png` show zombies at arm's length with no lens fill.
- **Bug found and fixed**: with Vexa standing still, six round-one zombies surrounded her in a raised-arms pose and never hurt her. `Scripts/ProbeNYCAttack.py` proved the cause: the native `AHoverNYCZombie` class (substituted for the blueprint zombie at InitGame) had no AnimClass, so the mesh sat in its reference pose, montages returned zero length and the vendor attack never fired its hit notify. Fix in `HoverNYCZombie.cpp`: the constructor now assigns the vendor `ABP_ZombieMaster` when no AnimClass is set, and `StartSwing` yaws the zombie to its target before the vendor forward sweep. Re-probe: montages play, 10 hits, HP 150 -> 0 in 38 s, 3 token denials. Every round frame captured before this fix shows reference-pose zombies.
- Post-fix rendered capture (`captures/round_0*_chase.png`): zombies animated and attacking by the truck, HP 150 -> 120 -> 60, game over at ~36 s with the vendor death widget ("You Are Died" is vendor text; our own downed/game-over screen is a Section 9 item).
- **New camera issue**: when zombies pin Vexa against the parked truck the spring arm collapses and the camera sits inside her own mesh (`round_05_player.png`). Fix in progress: hide the player's own body from her camera (owner-no-see, shadows kept) when the review camera is within ~95 cm, with hysteresis.
- Camera-collapse fix done: `AHoverPilot` hides its own body parts and world gun from the owner's view inside 95 cm (show again past 110 cm, hidden shadow kept); `HOVER_CAM_HIDE` log line; applies to every third-person camera. Proven in `captures/round_05_player.png`.
- Owner request: Smart Sharpen post-process placed in `L_NYC_Survival` (`Scripts/AddSmartSharpen.py`: `BP_SmartSharpen` unbound, priority 10, intensity 1.5 default, label "AFS Smart Sharpen", tag `AFS_SmartSharpen`).
- Minor: the PostApo "Walk to the glider | Home: reset test" prompt leaks into the survival HUD.

## 5. Kid texture (resolved)

The in-game Kid already uses the owner's Painter export: `T_Kid_0_BaseColor/Normal/RM` were re-imported on 2026-10-25 09:37 from `D:\AFS_Comparisons\KidTextureUpdate_20261025\Source\` (the same files as the `0e26c14a-...(1)_Material_*` export, hash-identical, pixel-identical per `final_manifest.json`), and `M_Kid_0` was updated with them. The earlier open question about that GUID set is closed: it is the Kid. The 1K/2K/4K Cyber City sheet was rendered after the import. The saved graphics setting caps the Kid at 1K; 2K costs 8 MB more and is the better default for a horde unit seen up close.


## Glider in NYC Survival (owner decision 2026-10-29 late)

The glider **stays** in L_NYC_Survival. It is the one map with vertical depth, and the owner sees it as a future feature: a quick escape or a way to travel the map, probably limited (about 15 seconds of flight, or fuel bought like ammo), outdoors only, useless indoors. Nothing is disabled and the survival exception is unchanged.

What changed now: the get-on / get-off control moved off the reload button in survival only. Hold **Y** (gamepad) or **G** (keyboard) next to the glider to step on, hold the same to get off; **X** is reload only there (any press length). Every other level keeps hold-X mount and tap-X reload. Prompts updated ("Hold Y / G: glider (quick escape)"). Code: `HoverPilot.cpp` UpdateInput hold block and `GetPrompt`.

Still to design when the feature is picked up: flight timer or fuel economy, indoor lockout, whether zombies can grab a low glider, and a spawn/park position that is not under the first horde.


## Rigged guns (2026-10-29 night to 2026-10-30, GPU-proven)

**Done and verified headless (no pixels yet):**
- M4A1 modular kit rigged (`Scripts/Blender/RigM4A1.py`, 15 bones, X forward, origin at the right-hand grip, 118 cm) with eight clips: Idle, IdleEmpty, Fire, FireLast (locks the bolt), DryFire, Reload (empty, free-fall drop, hand-arc fresh mag, bolt release at 1.95 s), ReloadTactical, Chamber. Imported to `/Game/HoverPrototype/Weapons/M4A1/` at 2K with the vendor materials (`Scripts/ImportM4A1.py`). First GPU proof showed it life-size in Vexa's hands with sharp textures; the bolt and reload still need a proper in-game capture.
- Skeletal gun path in `HoverPilot` + per-weapon binding `HoverGunRig` (data asset per gun, `DA_HoverPilot.gun_rigs` keyed by weapon definition, applied on equip; brass direction and socket fallbacks live on the rig; socket scale stripped because every rig's root bone carries x100 from the FBX).
- Three EM test guns cut, rigged, clipped and imported (`Scripts/Blender/RigEM_11.py`, `RigEM_21.py`, `RigEM_08.py`, `Scripts/ImportEMGuns.py`): EM_11 carbine (box mag, AK rock), EM_21 SMG (box mag, HK slap), EM_08 revolver (cylinder swing-out, hammer, ejector, 60 deg index). Rig assets `DA_GunRig_{M4A1,EM11,EM21,EM08}` under `/Game/HoverPrototype/Weapons/Rigs/`, bound: DA_AFS_Ballista -> M4A1, DA_Weapon_Pistol -> EM08, DA_Weapon_Rifle -> EM11, DA_Weapon_Rifle_002 -> EM21 (`Scripts/AuthorGunRigs.py`).
- Headless playtest (`AuthorGunRigs.py --verify-only`, receipt `D:\AFS_Comparisons\GunRigs_20261029uthor_receipt.json`): bolt cycles per shot, last round locks the bolt, empty reload vs tactical reload picked by ammo, swap to the revolver and back, cylinder indexes 120 deg over two shots, casings fall during the revolver reload not per shot. 36/36.
- All-guns plan: `Docs/EM_GUNS_RIG_PLAN_20261029.md` (survey, roster of 9, cut methods, production order). Showcase videos: `D:\AFS_Comparisons\Showcase_20261029\` (per gun + `Guns_showcase_all.mp4`).

**Done 2026-10-30 (GPU proof and validation):**
- Revolver cylinder carries over: `AHoverPilot::FinalizeGunPose` (OnBoneTransformsFinalized on both gun components) turns `CylinderBone` and its children by the accumulated `GunCylinderApplied` about the bone's X after every clip evaluation, so Fire's one-chamber turn stays in Idle. In-game trace (`D:\AFS_Comparisons\GunProof_20261030\capture.json`, `cyl_trace`): three shots, three -60 deg roll steps, all inside Fire, no step at any Fire-to-Idle handover, Idle roll equal to the accumulated angle on 58/58 ticks.
- `Scripts/ValidateGunClips.py` (CPU, 54/54): every imported clip's length and component-space strokes / angles match the Blender rig JSON numbers, rest orientation is identity on all four rigs, no moving bone lacks a track. It found EM_11 imported from the pre-fix export (flat bolt track), then the 60 fps clips exported at 30 fps, then the +X bone convention (90 deg root yaw: sockets' X pointed right, brass would have flown rearward); all three fixed at source (`RigEM_11.py`), assets deleted and re-imported fresh (an in-place reimport keeps the stale Skeleton reference pose).
- `Scripts/CaptureGuns.py` (GPU, `-RenderOffscreen`): 77 stills and four gameplay clips (`D:\AFS_Comparisons\GunProof_20261030\`, `Guns_ingame_reel.mp4` / `_720p.mp4`): M4A1 bolt -9 cm two ticks after the press with brass in the air, mag -70 parked at 0.75 s and seated at 1.9 s; EM_11 bolt -9 cm, mag -33 cm at 0.75 s; EM_21 mag -16 cm at 0.75 s, handle still in Fire (non-reciprocating); EM_08 cylinder 3.4 cm out to the left on the crane mid-reload. Hands: `hand_l` within 4.4 cm of `grip_l` on every gun while aiming, `hand_r` on `grip_r` by construction.
- Headless gameplay verify (`AuthorGunRigs.py --verify-only`) still green after the C++ change.

**Done 2026-10-30 evening (hand-tracked reloads, still gun hand, pistol stance) - owner's reel complaints: "firing a small pistol like a shotgun, floating hands", "reloads dramatically miss any magazine, big phantom motion", "hand holding the gun spins around the gun", "magazine appeared from the ground and floats into the gun, arm smashes through the gun":**
- Root causes: `AHoverCyberRifle::Reload()` played the stock `MM_Rifle_Reload` through the CLS driver (generic hands, aim pose and support IK gated off), the gun took its rotation from the aim ray while `hand_r` swung with the body clip (hand spinning around the gun), one rifle ADS pose for every rig (revolver shouldered), and one magazine bone parked at -70 cm then keyed back up (mag rising from the ground).
- Fix: rigged guns no longer play a body reload. The aim pose is held through the reload (`PlayGunReload` extends `GunRaisedTime`), the right hand stays on the grip (gun seated at the palm: `UHoverGunRig::bGripAtPalm`, grip_r at the midpoint of `hand_r` / `middle_01_r`), and the left hand is driven by two-bone IK to a non-deforming `hand_l_target` bone keyed inside each gun's Reload clip (`UHoverGunRig::HandTargetSocket`, live socket read in `UpdateAppearance`; the elbow joint target drops and swings out as the hand goes to the belt). Stance per rig: `EHoverGunStance {Rifle, Pistol}` picks `UHoverPilotAssets::RifleAim` or the new `PistolAim` (`/Game/HoverPrototype/Animations/MF_Pistol_Idle_ADS`, a copy of the CLS pistol ADS; `Scripts/BindPistolAim.py`); EM_08 is Pistol.
- Rig choreography (Blender, `RigM4A1.py` v3, `RigEM_11.py`, `RigEM_21.py`, `RigEM_08.py`): M4A1 and EM_11 pull the mag off with the hand (12 cm), release, it free-falls, the hand goes to the belt, the fresh mag POPS IN at the hand (magazine bone scale 0.001 while hidden, 1.0 at pop-in) and rides the hand into the well, M4A1 then hits the bolt catch (empty reload only); EM_21 drops the mag by itself, the hand touches the release, fetches at the belt, seats, HK slap on the ring handle; EM_08 cups the swung-out cylinder, speedloader beat at the belt, the crane closes late (f128-138) so the loader meets an open cylinder. Hand target == grip_l at f0 / last frame of every clip, so the IK blends back to the support grip for free.
- Proof: `ValidateGunClips.py` 74/74 (hand target present, at grip_l in all static clips, rides the magazine within 2 cm mid-carry, magazine scale hidden window f41-55 / f45-61 / f57-74); `AuthorGunRigs.py --verify-only` 35/35 (left palm within 0.01 cm of the hand target at 0.75 / 1.5 / 1.9 s, `hand_r` turns < 1 deg through the M4A1 reload, < 2.5 deg on the revolver); GPU capture `D:\AFS_Comparisons\GunProof_20261030\` (95 stills, 4 gameplay MP4s, reel; `M4A1_magchange_strip.png`; previous runs in `prev_1705/`, `prev_2214/`). CaptureGuns: hands camera now reads the back buffer 3 ticks late on purpose (a camera moved in the same tick is not in the pixels), `or 99` falsy-zero bug in the ok check fixed.
- Visible residuals (next pass): finger curl is still the aim pose's, so the left hand cups beside the magazine / cylinder instead of closing on it (needs a finger pose blend during reload, not an offset); on the EM_21 HK slap and the EM_11 rack the drooping fingers sink 1-2 cm into the receiver top (tunables `HAND_HK_M` z in `RigEM_21.py`, `HAND_KNOB_PAD` in `RigEM_11.py`); the M4A1 capture exercised ReloadTactical (26/30), so the bolt-catch beat is covered by the headless verify only; `Tier.TPFireAction` still plays a body fire reaction through the CLS driver on every third-person shot and drops aim while it plays (suspect if the "shotgun" feel persists).

**Done 2026-10-30 night (hands ride the gun through recoil, hand orientation + finger curl from the rig, per-gun flash scale):** owner, after the hand-tracked reload pass: "m4a1 looks great. the hands on the other ones still off, especially after recoil, the one hand stays in front of the gun and gets flashed over, but the hand grip of the non dominant hand goes through gun too.. she sure lights up a lot, might be overkill, at least for the smaller guns"; "for a hand gun both hands can be on grip and both follow the recoil instead of one. then the sub machine gun during recoil just needs to follow the same path of the gun. not eliminating the animation"; "only during the non reloading portion the hands position relative to the gun should stay in place".
- Cause of the hand ahead of the muzzle: every 4th shot played the stock `MM_Rifle_Fire` through the CLS driver; while it played `bAiming` dropped, the aim layer and the support IK went to zero and the left hand followed the retargeted rifle clip (handguard distance = ahead of a 30 cm SMG). Fix: rigged guns no longer route `TPFireAction` through the driver; the stance fire clips (`MA_Rifle_Fire_Add` / `MA_Pistol_Fire_Add`, copies of the CLS clips as local-space additives on their own first frame, `Scripts/BindFireAdditives.py`, `UHoverPilotAssets::RifleFireAdd/PistolFireAdd`) play as an additive over the aim pose, restarted per shot, and the support IK runs after at weight 1 whenever a rigged gun is up (`bRiggedGunUp`), so both hands ride the recoil. Headless: 5-shot M4A1 burst and 3 revolver shots, left palm within 1.9 cm of its target on every tick, never ahead of the muzzle, upper-body kick 6.2 deg (rifle) / 2.5 deg (pistol).
- Hand orientation + finger curl: `hand_l_target` now carries a ROTATION delta (from the aim pose's hand frame, measured by `Scripts/MeasureHandAxes.py`: hand_l +X along the fingers, -Y out of the palm, -Z thumb side) and a SCALE X curl channel (1.0 = aim-pose fingers, 0.6 open, 1.3 tighter) keyed per beat in all four rigs; `FHoverSupportHandNode` applies the rotation after the IK and rebuilds the finger chain (`Ref * Pow(Ref^-1 * Aim, Curl)`, including the Vexa metacarpals). Revolver `grip_l` moved to the pistol pose's native left-palm offset (2.0, -8.5, -3.0) so the left hand wraps the right hand instead of being pulled 8.6 cm into the frame.
- Flash: `UHoverGunRig::MuzzleFlashScale / MuzzleLightScale`, tier light 600 -> 300 cd; after the reviewer's tune the rigs sit at M4A1 0.6/0.1, EM11 0.4/0.06, EM21 0.3/0.04, EM08 0.35/0.05. M4A1 and EM11 now read as lit, not washed out; **EM21 and EM08 still white the torso on the shot tick** because the Ballista Niagara sprite (`NS_BallistaMuzzle`, about 1.5 m glow) dominates, not the point light. Next: a per-rig Niagara override (`NS_RifleMuzzle_Compact` exists) or a Niagara light-renderer scale, not a smaller number.
- Proof: `ValidateGunClips.py` 90/90, `AuthorGunRigs.py --verify-only` 48/48, GPU capture 112 stills + 4 MP4s + reel (`D:\AFS_Comparisons\GunProof_20261030\`, previous runs in `prev_1836/`, `prev_2152_flash_v1/`). CaptureGuns.py adds `c_hands_tK` post-shot hands frames and flash luminance metrics.
- Also 2026-10-30: `AHoverPilot::HoverView()` early return removed (F5 / Menu toggles to first person in survival again, per the design); engine debug hotkeys F1-F5 and Shift cancelled in `Config/DefaultInput.ini` (F5 was also `viewmode shadercomplexity`: the owner's red/green screen).

**Done 2026-10-30 late (M4A1 retexture):** the owner repainted the M4A1 in Substance Painter (GUN.spp); pulled through the Painter MCP with the "PBR Metallic Roughness" preset at 2K and bound to the vendor instances by `Scripts/ImportM4A1Painter.py` (19 painted parts; gas block, glass and red dot unpainted so the vendor maps stay; `--revert` restores). Proven in game with a single-gun 720p capture (`CAPTURE_GUNS=M4A1`).

**Done 2026-10-30 23:50 (right hand through recoil):** the fire additive opened the right hand off the pistol grip while the gun kept the aim-ray rotation. Now the rigged gun rotation rides the right hand's kick (`GunHandKick`, cached aim-pose rest, 25 deg clamp) and `FHoverStanceFireNode` holds the right finger chain at the aim pose through the additive; verify 59/59; capped M4A1 capture shows the fist closed on every burst frame. Owner also asked for a warm red/orange flash instead of the blue starburst (or a small explosion): flash gallery pass queued.

**Owner additions 2026-10-31 (packs + designs):** Fab packs installed into Content/ (Blood_VFX_Pack 111 Niagara effects, sA_BloodMagic_1, SF_Explosives_SFX, cplomedia_WeatherSFXLoops, A_Surface_Footstep, SilkTrap = Robot Mine). Dreamrise Multiplayer Dynamic Weather System v4 lives as its own project at `M:\MultiplayerDynamicWeather` (blueprint-only; copy its Content subfolder in, place BP_MultiplayerDynamicWeatherManager, wire MF_WeatherWind / season blends into the NYC master materials for wet and snow). The Life Engine (movement) is blocked by the launcher version check (use "Show all projects" or copy the plugin). **Robot Mine power-up (owner):** "a tactical power up, throw on ground and finds the nearest zombie and explodes AOE" - throw, Anim_Assembly on landing, seek the nearest zombie (Jump/Attack anims), AOE explosion (ZE NS_Explosion + SF_Explosives_SFX), COD tactical-slot semantics (LB / L1). **Blood Magic boss (owner):** `sA_BloodMagic_1` is for a boss-type zombie with higher HP and heavy-damage special attacks (telegraphed blood-magic casts, AOE), a second boss archetype next to the StoneGolem. Also: the same effects low to the ground in small patches inside hordes as a creepy blood-fog ambience (spawn under dense groups, short-lived, budgeted).

**Done 2026-10-31 02:30 (grip seat):** the right fist now wraps the pistol grip on all four guns (`GripSeatOffset` / `GripRotationOffset` per rig, measured by `Scripts/MeasureGripSeat.py`; verify 63/63; sheet `D:\AFS_Comparisons\GripSeat_20261031\grip_sheet.png`). Pose-limited residuals: the AR grip rakes 31 deg against the aim pose's 10 deg fist (grip bottom ~2 cm below the pinky), the revolver trigger finger rests under the guard, the SMG grip is shorter than the hand. Next: per-rig right-hand rotation delta + trigger-finger pose.

**Done 2026-10-31 03:15:** muzzle flash warm per rig (`MuzzleFlashOverride` = ZE `NS_GunFire`, warm light, light scale .03/.02/.01/.01, radius 150 cm, 20 cm source radius, absolute scale when overridden); sheet `D:\AFS_Comparisons\Flash_20261031\flash_two_options.png` (M4A1 good; SMG/revolver still hot within 20 cm before the source-radius build). The Life Engine (HL Movement System) extracted from a temporary UE 5.7 install into `Plugins/HLMovementSystem`, compiled for 5.8, 5.7 removed. Four horror grenades (split from the owner's Tripo file) imported under `/Game/HoverPrototype/Props/Grenades/` (~48 cm tall, scale 0.25 in use); the caged one is the **Blood Bomb** (fill with a blood-magic core).

**Side quest 2026-10-31 (SpaceSurvival body for Vexa's routine, not AFS):** the owner's Female Basemesh V10 was given the Base Female Body pack's eyes, fitted with SpaceSurvival's 98-bone Vexa skeleton (joints by surface correspondence, weights transferred, every routine track binds) and the owner's hair/teeth/tongue; deliverables in `D:\Female Basemesh V10 (1)\Rigged\` (`SK_V10_VexaRig_Final_Hair.fbx`, README_import.md). Two more bodies were fitted to the same skeleton (done 2026-10-31): `D:\Bodies_VexaRig\AAA\SK_Jess_VexaRig.fbx` (Jess 8.2, untextured, 26 correctives) and `D:\Bodies_VexaRig\CC\SK_CC_VexaRig.fbx` (Character Creator talking body, 121 face morphs, jaw-driven mouth, 110 textures beside it), each with its own README_import.md. All three were placed in SpaceSurvival's `L_BodyTrials` (copy of the Vexa chamber) and the owner looked in game 2026-10-31. Ruling: the deformation problems are the routine's retargeting/contact, not the mesh topology; no further character bodies for the routine. Body quest closed. Scripts under `Scripts/Blender/` (TopologyAudit.py, TransferSkinToV10.py, BakeSkinToV10.py, WireV10PainterTextures.py) are reusable for AFS characters.

**Open:**
0. **Small-gun flash:** EM_21 / EM_08 still white the character on the shot tick (Ballista Niagara sprite); per-rig Niagara override (`NS_RifleMuzzle_Compact`) or light-renderer scale. **First person:** the owner reports the FP arms fill the view; `HoverView` is Exec-only so `CaptureGuns.py` cannot toggle FP (make it BlueprintCallable, capture an FP still, then fix arm placement / FOV). **Controls:** owner wants NYC to feel like the PostApo / COD layout; NYC differs only in hold-Triangle glider, Square-release reload and the sprint-fire block, and the HUD mixes Xbox face names with PlayStation shoulder names (DualSense via Steam) - owner is testing before any change. EM_11 knob pinch needs a right-side camera to verify; the EM_08 cylinder cup reads as cupping the barrel from the capture cameras.
1. **Product gap:** the vendor definitions (DA_Weapon_Pistol_001, DA_Weapon_Rifle_00x) spawn vendor weapon actors, not `HoverCyberRifle`, so the EM bindings only work once owned definitions exist (DA_NYC_Sidearm 6 rounds for the revolver, DA_NYC_M16, DA_NYC_SMG) with `HoverCyberRifle` as the actor class. That is the wall-buy / economy slice.
2. GPU proof: in-game capture of the M4A1 bolt and mag drop with a proper camera, hand placement check (review said raw grip sockets may put the wrist inside the receiver), the three EM guns in hand, and a gameplay video.
3. Cut-cap texturing on the EM guns (white caps on the revolver, orange well on the carbine, beige scar on the SMG).
4. Dropped magazine as a physics prop (the empty mag now hides by bone scale once it has fallen clear); hand-carried fresh mag, cylinder carry-over and per-stance aim poses are done; body reload clips are no longer needed for rigged guns (hand target IK), pump / bolt / lever guns get theirs the same way.
5. Convention v2 for the next guns: export at unit scale 0.01 so the root bone is 1.0; armature object named `Armature`; clips carry the mesh; bones point Blender +Y roll 0 (ejection_port +X); set the scene fps after the FBX import; run `ValidateGunClips.py` after every import (see `Docs/EM_GUNS_RIG_PLAN_20261029.md` section 3).

## Owner playtest 2026-10-31 (NYC Survival, verbatim list, video review to follow)

1. **Ammo economy unreadable.** No way to buy ammo; picking old clips off the ground refills but nothing indicates it. (owner: not a big deal for now)
2. **Zombies all the same.** Same sounds, walk backwards at her, no real attack motion, "very common look".
3. **No tactical items, no other weapons** reachable in the mode.
4. **Can't get in a car**; the hover board mounts and lands fine.
5. **Kid zombies bunch up** and hoard in one spot; she had to approach them.
6. **Random attack did 999,999 damage and every zombie died** at once.
7. Reload animation looks good; movement "still ok".
8. **Zombies flying up and sinking into the ground.**
9. **Menu lacks the ZESP in-game settings menu.**
10. **Melee feel "sucks"**: the damage window feels tiny and there is no read on when a hit lands.

11. **Zombie heads are trampolines**: she can jump onto a zombie and bounce on its capsule.

Frames from the owner's recording (Downloads, `Screen Recording 2026-10-31 084123 - frame at *.jpg`): 7m0s the melee
swing (50) lands as the Nuke fires (999,999 on every zombie); 7m2s every zombie is a ragdoll on the ground; 7m3s all the
ragdolls shoot into the sky at once. 5m26s a lone ragdoll already airborne after a normal kill. 5m6s / 8m40s the kid
swarm clumps at its spawn by the truck until she walks up. 0m0s the first-person arm fills the frame. Every frame also
shows the engine's on-screen directional-light warning ("lights are competing to be the single one used for forward
shading ... ForwardShadingPriority") in the top-left: two directional lights in L_NYC_Survival.

Root causes found 2026-10-31 (code read, patches written, build pending):
- **6 + 8 (999,999 and flying corpses):** the Nuke power-up (`AHoverCyberPowerUp::OnOverlapBegin`) applies 999,999 to every
  zombie, alive or dead. The vendor `AZE_ZombieCharacter::TakeDamage` gives an already-dead ragdoll an impulse of
  damage x 100, so the nuke (and a few rifle rounds into a corpse) launched bodies skyward; and a death with no death
  montage got the vendor's deliberate "fly away" impulse (1,800 up / 1,500 back as a velocity change). Patched: corpse
  impulse only for point hits, capped (min(damage, 60) x 60); the no-clip death now slumps (220 back, 60 down). The nuke
  still has no banner, sound or flash: presentation to do.
- **11 (trampoline):** zombie capsules were walkable; `AHoverCyberZombie::BeginPlay` now sets the capsule
  WalkableSlopeOverride to Unwalkable, so Vexa slides off instead of standing on heads.
- **10 (melee):** vendor `PerformMeleeTrace` is one 20 cm sphere trace along the camera from eye height, fired once
  0.3 s into the 0.8 s swing. Not yet changed; plan: several samples across 0.2-0.55 s, wider radius, multi-hit, plus
  the new whoosh / cut sounds.
- **Light warning on every frame:** two directional lights compete in L_NYC_Survival (ForwardShadingPriority). Not yet
  changed.

Full-video pass (contact sheets under `D:\AFS_Comparisons\Playtest_20261031\`): 1:06-1:36 is the owner in the editor viewport, not play (owner clarified); 5:37-5:42 the ammo pickup is an unmarked red object on the ground;
7:30-8:00 the board flight works; 8:55 death to the kid swarm. Zombies sinking into the ground was not caught at the
5 s sampling; needs the owner's timestamp.

Status at logging time: Life Engine wiring and the audio pass (guns louder on the WW2 set, katana whoosh + cut,
code-driven footsteps, wind bed) are written and waiting on a build; nothing from this list is started. The owner is
reviewing a recording and will add to the list.
