# AFS: asset kits the owner flagged

The owner circled these in their Fab library on 2026-10-31 as the kits that matter for AFS. This file maps each one to
where it lives and what it is for. "In AFS" means imported under `M:\UnrealProjects\AFS\Content`. "On disk" means
cached under `D:\FABDOWNLOADS\VaultCache` but not imported into AFS.

## In AFS already

| Kit | Folder | Use |
|---|---|---|
| ZESP Zombie Engine Studio | `ZESP` | zombie, wave, weapon framework |
| Zombie (Etherion) | `Zombie` | two morph-target zombie bodies, 9 skins, about 90 vocals, clips |
| Zombie Animation Pack: Standard | `ZombieAnimationPack` | 32 zombie clips: walks, attacks, bursts, crawls, impaled, damage |
| Feral Zombie Animations | `FeralZombie` | the Kid's all-fours set |
| Zombie Male AAB | `ZombieMale_AAB` | modular zombie body with separate limbs (dismemberment later) |
| NIAGARA Blood VFX Pack (Rimaye) | `Blood_VFX_Pack` | all blood: hit splashes, bursts, ground splashes, artery bleeds |
| Blood Magic Skill VFX | `sA_BloodMagic_1` | blood-magic boss, horde haze, Blood Bomb core |
| Sci-Fi Explosives SFX (Stormwave) | `SF_Explosives_SFX` | grenades, Nuke, Robot Mine |
| Weather Sound FX Loops (cplomedia) | `cplomedia_WeatherSFXLoops` | wind bed now; rain and thunder with the weather toggle |
| Niagara Footstep VFX (Sidearm) | `A_Surface_Footstep` | footstep puffs and physical materials |
| Robot Mine | `SilkTrap` | tactical seeker mine |
| Life Engine | `Plugins/HLMovementSystem` | Source-style movement in NYC Survival |
| Parkour Movement Pack | `ParkourMovementPack` | Vexa's template: vault, wall run, wall jump |
| Glider Animation, Scifi Hoverbike Glider | `Glider_Animation`, `ScifiHoverbike` | the board / glider |
| Flips and Tricks, Free Arrow Trail | `FlipsAndTricks`, `ArrowTrail` | trick clips; tracer candidate |
| Smart Sharpen, Armored Stone Golem, Post Apocalyptic Desert | `SmartSharpen`, `StoneGolem`, `JustBStudios` | post, boss, PostApo map |
| Easy Shockwaves VFX (Vefects) | `Vefects` | shockwaves (Nuke, Brute stomp) |

## Weather

The Dreamrise Multiplayer Dynamic Weather System V4 is already downloaded and set up as its own project,
`M:\MultiplayerDynamicWeather`. It is the source for the rain/snow menu toggle, queued after the big bugs: migrate its
`Content/MultiplayerDynamicWeatherSystem` folder into AFS. No other weather kit is needed.

## Animations

The owner's animation packs are imported in the SpaceSurvival project (`C:\Users\j6sis\SpaceSurvival`). Look there
first, or ask the owner for something specific, before importing an animation pack into AFS from the vault cache.
The zombie packs are already in AFS.

SpaceSurvival packs that suit zombies (checked 2026-10-31): `DrunkAnimations` (stumbling walks and idles for
shamblers), `RamsterZ_FreeAnims_Volume1`, `MCO_Mocap_Basics`, `FreeAnimsMixPack`, `SampleAnimationPack`,
`AbductionAnimPack` (grabs). Not in SpaceSurvival, only as FBX in the vault cache: Paragon Crunch (heavy punches,
directional hit reacts front/back/left/right, deaths) for the Brute and Brawler; "a lame man came running and hung
onto something" (a run-and-grab for a zombie grab attack); "Cutting the throat" (a katana finisher). Next zombie pass:
ask the owner before importing those.

Added by the owner 2026-10-31 for the zombie work:
- `Content/AbductionAnimPack` (UE5 Manny skeleton, same 61 core bones as the roster): AS_ShoulderGrabfromBehind,
  AS_GrabandPull, AS_BackGrabSilence, AS_ChokeTakedown, AS_Push, AS_KnockoutStrikeandDrop, AS_BodyHaul,
  AS_SearchVictim, AS_SilentApproach, AS_GunThreat. Use: zombie grab / tackle attacks; BodyHaul for a zombie dragging a
  corpse.
- `Content/SpearAnimationsV2` (401 assets): 1H/2H spear jabs, swings, thrusts, throw, high/low hit reacts, idle/walk/run
  per stance. Owner ruling 2026-10-31: a melee weapon for Vexa; its poses may be mildly adapted for her other melee
  weapons (katana and later ones) instead of inventing motion from scratch.
- Dead Bodies Sitting & Lying Poses (30 single-frame mocap poses, 21 lying, 9 sitting): the Fab "converted" GLB in the
  vault cache is unusable (one 0.8 s take, mangled bone names). The listing has an Unreal Engine format: add that to the
  project. Use: corpse set dressing and dormant "ambush" zombies that rise (Feral Reanimate) when Vexa comes close.

## On disk, not imported

| Kit | Size | Use, and which open issue |
|---|---|---|
| Doomsday Pickup Truck, drivable | 514 MB | answers "can't get in car" (open issue: cars) |
| Custom locomotion system, Motion Matching | 677 MB | player locomotion option; after the Life Engine verdict |

## Not downloaded (library only)

| Kit | Use |
|---|---|
| Sci-Fi Weapon Sniper Gun | weapon |
| AI Voice No-Code Plugin (ElevenLabs) | generated voice lines |
| Essential Footsteps SFX (Sound Kajiya) | more footstep sets |

## Ruled out by the owner

- Free Blood VFX (Vefects): agreed not to add. Do not download it. Rimaye's pack covers blood.
- Zombie Survival Bodycam Kit: does not fit this project.
- Any other weather kit: the Dreamrise system is the weather.
