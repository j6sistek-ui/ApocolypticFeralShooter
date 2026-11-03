# NYC Zombie Survival: wave-based third-person mode design

Project: AFS (`M:\UnrealProjects\AFS`, Unreal Engine 5.8, HoverFlight module + Zombie Engine Studio plugin)
Date: 2026-10-29
Status: design, implementation-ready; no code or content has been changed by this document
Benchmark: Call of Duty Black Ops 7 Zombies (BO6 and Cold War data used where BO7 numbers are unpublished; every such proxy is flagged in the review trail)

## 0. Summary

This document specifies a complete round-based zombie survival mode for the post-apocalyptic New York level. It is built on the systems that already run in Cyber City (the Zombie Engine wave game mode, inventory, wall buys, power-ups and the AFS adapter classes) and adds what is missing: a new game mode and owned map, navigation, a spawn director, crowd and attack-slot AI, round scaling with a health cap, horde and heavy rounds, two mid-level bosses, a points economy, an armory with Pack-a-Punch tiers, vest and plate armor, tactical equipment, a downed state, power-ups, a door-gated zone graph with a power objective, and a HUD that communicates all of it.

It also carries the fixes for the three problems the owner reported in the existing zombie maps. Each was traced to code and confirmed by independent skeptic agents before the design was written:

| Complaint | Verified cause | Design response |
|---|---|---|
| Gun shooting feels bad, weak VFX and haptics | `AHoverCyberRifle::PlayFireAnimation` is a no-op, so the authored camera shake and fire montages never play; vendor recoil integrates to about 0.03 degrees per shot; rumble is 18% on the small motors for 60 ms; no hit marker or hit sound; all five Ballista tiers are semi-automatic because `bAutomatic` is unset; tracer is 60 to 90 ms and hair-thin; zombie flinch is one full-body montage per 0.8 s and never during an attack | Section 5: camera shake, real recoil, automatic fire at 8 shots/s, force-feedback assets on the large motors, hit and kill markers, per-shot damage numbers, physics flinch, longer brighter tracer, muzzle light, flesh impact audio and decals, bounded penetration, kill punctuation |
| Zombies spawn randomly and stall then burst | The adapter enables exactly one spawner per frame from a forward-cone visibility test that zombie bodies block; the vendor tick is skipped when no entrance qualifies and the spawn timer is not advanced, so a cleared entrance fires instantly; no straggler relocation; the wave cannot end until every zombie is dead, including ones chasing a vehicle | Section 3: a spawn director with zone pools, distance-band weighting, pawn-ignoring occlusion test, per-spawner cooldowns, spread across at least three recent spawners, a pacing budget, interval and position jitter, straggler relocation with honest wave accounting |
| Zombies bunch up | Every zombie runs `MoveTo(TargetEnemy)` with a 5 cm acceptance radius toward the identical player point and stops only at 150 cm; no attack slots or attacker limit; attack cadence is a fixed wait; no per-instance speed jitter; DetourCrowd is hot-swapped at possess time on an unconfigured crowd manager | Section 4: an attack-slot ring with attacker tokens, a configured crowd manager with per-role separation, per-instance speed, acceleration and cooldown jitter, speed tiers rolled at spawn, obstacle-only crowd state while attacking |

## 0.1 Headline decisions

- The mode is a **new game mode and a new owned map** (`AHoverNYCSurvivalGameMode`, `L_NYC_Survival`, level menu entry 4 "NYC - Survival"). The existing "NYC - Exploration" entry stays zombie-free as `AGENTS.md` requires; the owner must amend the listed lines before implementation starts.
- **Third person is forced** on spawn in this mode; the sandbox default is first person.
- **Invincibility is forced off** and the player health model moves to 150 HP with regen, a downed state and self-revive, matching the benchmark.
- **Rounds are continuous** with a 10 s gap, a stepped health curve capped at 25,000, the classic count curve with a 24-alive cap, speed tiers rolled per zombie at spawn, horde rounds every 5 from round 5, a Brute debut at round 8, heavy rounds on even rounds from 12, and scripted boss rounds at 13, 19 and 27.
- **Pack-a-Punch is a definition swap** across the existing Ballista tiers (5,000 / 15,000 / 30,000 for x2 / x4 / x8), the economy is kill-only Essence (90 / 115 crit / 105 melee / 250 special / 500 boss), vests are 1 / 2 / 3 plates at 0 / 4,000 / 10,000, and six perks cost 2,500 plus 500 per perk owned.
- **Six door-gated zones** open from the spawn plaza along the known street corridor, with the power objective in the Survivor Shelter and Pack-a-Punch in the Underpass.
- Delivery is **two-staged**: Stage 1 ships the whole loop with Standard, Kid, Brute and the two bosses; Stage 2 adds the Riot armored zombie, the second rifle, exfil, extra power-ups and traps.

## 0.2 Owner decisions recorded during the design pass

These were given after the numeric spine was fixed and override anything contrary in later sections; the roster section (Section 10) is the reconciled source.

- All eleven owner-made zombie meshes (Standard01-04, Brute, Kid, Horror, BogZombie, Mythical, Plant, Pirate) may be used in NYC. The Lakeside isolation rule applies only to Cyber City and PostApo.
- The **StoneGolem stays as a mid-level boss as is**, with no hammer and no shield, using its own 25 clips. Its skin is the owner's new Substance Painter export (`stoneUntitled_M_StoneGolem_Body/Armor` BaseColor, Normal, packed OcclusionRoughnessMetallic). The older export set is an optional alternate; the unnamed third set has an unconfirmed target mesh.
- The **Kid is the horde-round unit** and must crawl fast and attack. The same Kid mesh scaled large is a **second boss-style enemy with unique animations**.
- The Feral zombie animation pack (already imported as `Content/FeralZombie`) supplies leap, strong attack, feasting and reanimate clips for specials and boss moves.
- Content gaps may be filled from the Fab library cache (`D:\FABDOWNLOADS\VaultCache`) and the SpaceSurvival project (`C:\Users\j6sis\SpaceSurvival`); Section 10 lists candidates.

## 0.3 How to read this document

Section 1 is the numeric spine: every other section references its tables and does not restate different numbers. Sections 2 to 9 and Section 11 are the system specifications and the implementation plan, each written against the real code (file and line citations) and each reviewed by two skeptic agents, one checking feasibility against the codebase and one checking coherence with the spine and the benchmark. Section 10 is the roster and content mapping, verified against the asset name tables on disk. The appendix (`NYC_ZOMBIE_SURVIVAL_DESIGN_20261029_REVIEW_TRAIL.md`) records the spine judging, verification verdicts and per-section changelogs. Open questions for the owner are collected at the end.

Conventions: prices and points are Essence; distances are centimetres unless stated; "round" and "wave" are the same thing (the plugin calls them waves); "owned" means authored under `/Game/HoverPrototype` and never a vendor asset.

## 1. Numeric spine (authoritative tables)

**Angle:** FEEL-FIRST SPINE, SHIP-FAST DELIVERY, BO7 RULES. Structure = Candidate 3 (highest aggregate judge score 83 vs 80 vs 77): every round band ends at about 8 body / 4 head shots with the Ballista at the PaP tier the economy affords and each PaP purchase snaps TTK back to about 4/2; readable speed tiers (walkers only R1, no walkers from R9, all sprinters R18); horde round every 5 from R5 (Kids, Max Ammo on clear); Brute debut R8 then heavy rounds on even non-horde rounds from R12; three scripted mid-level boss set pieces (R13, R19, R27). Delivery = Candidate 2: the R1-30 curve is UZE_WaveGameModeSettings bUseCustomWaves rows (BaseZombieCount, HealthMultiplier = H(r)/100, DamageMultiplier band, SpeedMultiplier 1.0, CustomIntermissionTime 10) that the adapter already consumes; Pack-a-Punch = DA swap DA_AFS_Ballista -> _2 -> _3 -> _4 in the same quickbar slot; Alpha Brute = pure data duplicate of DA_Brute as the guaranteed-shippable boss; horde/heavy cadence through UHoverCyberEncounterSettings fields; perks as unique item definitions sold by AZE_WallBuyActor subclasses; no new EZE_PowerUpType values in Stage 1. Rules = Candidate 1 / BO7 benchmark: 150-HP player, 30/50/75 hit bands, kill-only 90/115/105/250/500 points, vests 1/2/3 plates at 0/4,000/10,000, six perks at 2,500 + 500n, PaP 5k/15k/30k = x2/x4/x8, BO3-lineage power-up threshold, per-spawn speed roll, full owner-amendment checklist. Two-stage cut: Stage 1 ships the loop (Standard/Kid/Brute/Alpha Brute, 6 perks, vests, PaP, doors, downed/game-over, power switch); Stage 2 adds Riot armored, Warden (StoneGolem), Heavy Ballista/M16, exfil booth, Double Points/Bonus Points, traps.

WHY THIS SHAPE: judges split one vote each; by aggregate Candidate 3 (Feel-first) wins 83-80-77 and is the only candidate whose ledger subtracted ammo and reproduced line by line, so its TTK-derived structure is the winner. Judge 2's feasibility case for Candidate 2 is adopted wholesale as the delivery mechanism, and Candidate 1 supplies the benchmark rules. WHAT CHANGED VS THE WINNER (every item recomputed by me, see income_check): (1) Fire rate: Candidate 3 assumed 600 RPM from an unverified ctor default; the spine prescribes the authored value FireRate 8 / bAutomatic true on all Ballista DAs, so TTK seconds = shots x 0.125 (band exit 8 body = 1.0 s, 4 head = 0.5 s) instead of shots/10. (2) Health curve R26-30 lowered from +400 to +300 per round (R30 3,500 not 4,000) and R31+ restated as +800 (R31-40, R40 = 11,500) then +1,000 (R41+); the 25,000 cap binds at R54 (R53 24,500, R54 25,500 clamped) - the winner's 'R55' claim was wrong (it bound at R49). The flattening is forced by the ammo ledger: with +400 and a 300-round reserve, PaP II ammo at R21-29 costs 6-9 refills a round and PaP III is never affordable by R30 (simulated); with +300, reserve 270/360/450/540 by PaP tier and guaranteed Brute/boss Max Ammo drops, PaP III lands R23-24 and the R30 surplus is ~40,000. (3) Count R30 = 105 (integer math 24 + 9*r*r/100; the winner's 104 was a double-precision floor artifact). (4) Kids pay 90 (BO flat award) not 60; bosses pay 500 (BO elite) not 1,000; the lost income is covered by the Brute Max Ammo rule. (5) Hit damage bands are the benchmark 30 (R1-10) / 50 (R11-30) / 75 (R31+) via CustomWaves DamageMultiplier 1.0 / 1.667 / 2.5 on DA MeleeDamage 30; the winner's invented 65 step at R21-30 is dropped. (6) Riot armored simplified to one ablative pool (body 1.5x + armor 0.5x = 2.0x effective, 150 pts, no per-bone pools), share 15% R9-16 / 20% R17+, max 6 alive, zero on horde and boss rounds, and moved to Stage 2; the income model now applies the zero-on-boss-rounds rule consistently (R13 = 4,351, R19 = 6,030, R27 = 9,789). (7) Warden 15x (not 18x) so the R27 double-boss set piece is 126 PaP III headshots (about 16 s of fire) instead of 150+; Alpha Brute 12x as the shippable fallback for every boss round. (8) Katana hit table corrected: 50 + 12.5(r-1) (cap 400) vs H(r) is exactly 2 hits R1-10, 3 hits R11-15, 4 hits R16-20, 6 at R25, 9 at R30; Kids one-swing through R12 only. (9) Juggernog hits-to-down corrected: 250/30 = 9 hits at R1-10 (not 7), 5 at R11-30, 4 at R31+. (10) Plates: one 50-HP plate at 50% routing adds 50 HP of absorption = +1-2 hits at R1-10, +1 at R11-30 (Candidate 1's +3 was wrong). (11) Brute R8 figure: 1,650 HP = 48 body / 24 head PaP 0 shots = 3.0 s of headshots (the winner mislabeled the PaP 0 figure as PaP I). (12) HealthScale is frozen per actor at spawn (judges' graft) so bosses and stragglers do not re-scale across the round boundary; the per-tick rewrite in AHoverCyberZombieAI::Tick reads the actor's frozen scale. (13) Economy ledger re-simulated three ways (35% headshot-kill mix = 98.75/kill, 25% = 96.25, all-body 90) with ammo purchased at refill-to-full prices whenever the pool runs dry and only GUARANTEED Max Ammo drops counted (horde clear, boss death, first Brute of each heavy round): lowest balance 132 (expected) / 98 (25%) / 10 (all-body, R2 if Door 2 is bought at R2; wait to R3 and it is 1,180). (14) Vehicles: hoverbike is not spawned in L_NYC_Survival at all (owner rule), Doomsday truck is parked and unmountable in Stage 1 (exfil set piece in Stage 2), hoverboard allowed but earns no points and does not block damage. BASELINE EDITS THE AUTHORING PASS MUST MAKE: Standard DA MaxHealth stays 100 (NYC copies DA_NYC_Standard01-04 of the Cyber definitions, Role Standard, MeleeDamage 30); Kid 45 HP / MeleeDamage 15; Brute 600 HP / MeleeDamage 60 (was 75, band now scales it); DA_NYCWaves: AutoHealth/Speed/Damage/CountScalePerWave 1.0, bUseCustomWaves true with 30 rows + ConfigureWave formula fallback for R31+, TimeBetweenWaves 10, FirstWaveDelay 5, MaxConcurrentZombies 24, SpawnInterval 2.0; DA_AFS_Ballista.._4: 35/70/140/280 body, HeadshotMultiplier 2.0 all tiers, bAutomatic true, FireRate 8, Mag 30, Reserve 270/360/450/540, SpreadRecovery while held; Vexa: SetMaxHealth 150 at InitGame, bInvincible forced false, HUD '/100' label reads MaxHealth; kill reward: fixed 90/115/105/250/500 via the AHoverCyberZombie::TakeDamage override (bone/causer check before Super) instead of RandRange(MinGold,MaxGold).

### 1.1 Player

| Base health | Regen delay (s) | Regen rate (HP/s) |
|---|---|---|
| 150 | 6 | 40 |

Armor tiers:

| Tier | Plates | Plate HP | Reduction % | Price |
|---|---|---|---|---|
| 1 | 1 | 50 | 50 | 0 |
| 2 | 2 | 50 | 50 | 4000 |
| 3 | 3 | 50 | 50 | 10000 |

Zombie hit damage by round band:

- R1-10 (CustomWaves DamageMultiplier 1.0): Standard 30, Kid 15, Riot 45, Brute 60 swing / 60 stomp + 2.1 s knockdown, Alpha Brute 90, Warden hammer 75 + knockdown; 150-HP Vexa downs in 5 standard hits, 9 with Juggernog (250)
- R11-30 (DamageMultiplier 1.667): Standard 50, Kid 25, Riot 75, Brute 100, Alpha 150, Warden 125; 3 hits unarmored, 5 with Juggernog
- R31+ (DamageMultiplier 2.5): Standard 75, Kid 38, Riot 113, Brute 150, Alpha 225, Warden 188; 2 hits unarmored, 4 with Juggernog
- Plate rule: while any plate HP remains, 50% of each hit goes to the plate pool and 50% to health (FZE_ArmorStats DamageReduction formula lifted from ZE_HealthTrigger.cpp into AHoverPilot::TakeDamage); plates are 50 HP each, so one plate absorbs 50 HP total = +1-2 hits at R1-10 (30 dmg: 15 per hit to the plate, breaks on the 4th hit), +1 hit at R11-30; vest tier = max plates; plates 50 points each at any armor station; Max Health power-up also refills plates (Max Armor stand-in)
- Knockdown: Brute/Alpha stomp and Warden hammer apply the existing 2.1 s ApplyStompKnockdown (1.4 s with Stamin-Up) on top of damage; knockdown ignores plates only for the stun, the damage is still plate-routed
- Readability: directional damage indicator on every hit, plate-crack sound when a plate breaks, regen countdown drawn on the HUD at <= 40 HP; zombie hits never scale with the sandbox 15 x 1.05^(w-1) formula (AutoDamageScalePerWave = 1.0)
- Vehicles: hoverbike is not spawned in L_NYC_Survival; Doomsday truck parked and unmountable in Stage 1; hoverboard usable but awards no points and does not block damage (the SetCanBeDamaged gate is bypassed for the board in this mode)

Downed rules: Solo only. Survival mode forces bInvincible = false and MaxHealth 150 at InitGame; sandbox HoverReset teleport-and-heal and the 3 s reset + 2 s grace path are disabled in this mode. Regen: 6 s after last damage (3 s with Quick Revive), 40 HP/s to max. At 0 HP Vexa enters a 3.0 s downed pose (QA_StompRecovery-style CLS action, no input; zombies ignore her for the pose + 2.0 s grace via the AI-tick retarget filter since direct chase bypasses perception). If a Self-Revive is held it is consumed: stand at 50% MaxHealth, 0 plates, lose the most recently bought perk (BO6 rule simplified), round continues and spawning never pauses. One Self-Revive is free at match start; more cost 1,500 at the Shelter station, max 3 held (4 with Quick Revive). With no Self-Revive the match ends: 2 s slow-motion death cam, vendor WBP_ZE_DeathRespawn summary (round reached, kills, points earned, zones opened, PaP tier), then RestartLevel to R1; the vendor GameOver path is bound only to AZE_PlayerCharacter so AHoverNYCSurvivalGameMode invokes the widget manually. No bleed-out bar, no co-op revive.

### 1.2 Rounds

- Health formula: H(1) = 100 (DA_NYC_Standard MaxHealth unchanged); H(r) = H(r-1) + inc(r) with inc = +25 for R2-10, +45 R11-15, +90 R16-20, +200 R21-25, +300 R26-30, +800 R31-40, +1,000 R41+; clamp at 25,000 (R40 = 11,500, R53 = 24,500, cap binds at R54). Delivered as CustomWaves[r].HealthMultiplier = H(r)/100 for R1-30 (AutoHealthScalePerWave 1.0) with the same formula coded in AHoverNYCSurvivalGameMode::ConfigureWave as the R31+ fallback (CustomWaves beyond the last row is unverified vendor behaviour). Specials are multiples of H(r) through their own DA MaxHealth (Kid 45 = 0.45x, Brute 600 = 6x, Alpha 1,200 = 12x, Warden 1,500 = 15x, Riot 150 body + 50 armor pool = 2.0x) so one multiplier scales the whole roster. HealthScale is frozen per actor at spawn so bosses and stragglers do not re-scale at a round boundary. Shape check: Cold War proportions (150 base, +60 to R12, +100 to R17, +300 to R22) scaled to the 100-HP base and the 35-dmg rifle so that H(10) = 325 (PaP I 5 body / 3 head), H(15) = 550 (PaP I 8/4), H(20) = 1,000 (PaP II 8/4), H(25) = 2,000 (PaP III 8/4), H(30) = 3,500 (PaP III 13/7, the stretch band where Deadshot and Double Tap earn their price).
- Health cap: 25000
- Count formula: Standard quota N(r): R1-9 classic solo lookup 6, 8, 13, 18, 24, 27, 28, 28, 29; R10+ N(r) = 24 + (9*r*r)/100 in INTEGER arithmetic (R20 60, R30 105, R40 168, R50 249); never FMath::FloorToInt(0.09*r*r), which yields 104 at R30 in double precision. Horde rounds (r mod 5 == 0) replace the quota with K(r) = 10 + 2r Kids (R5 20, R10 30, R15 40, R20 50, R25 60, R30 70). Brutes and Riots REPLACE standards inside N(r); bosses are ADDITIVE on top of N(r) (one extra unit on R13 and R19, two on R27) and the income check uses exactly this reading. From R21, 10% of the standard quota on normal rounds is Kids (BO7 Ravager bleed-in). Authored as CustomWaves[r].BaseZombieCount = N(r) with AutoCountScalePerWave 1.0, the existing Tuning.Count multiplier and Clamp(1, 200) kept; ConfigureWave applies the horde/heavy/boss substitutions.
- Max concurrent: 24
- Spawn interval: SI(r) = 2.0 x 0.95^(r-1) s, floor 0.5 s (R1 2.00, R5 1.63, R10 1.26, R15 0.98, R20 0.75, R25 0.58, R30 0.50), computed in the existing GetEffectiveSpawnRate override (vendor SpawnInterval 2.0 is the R1 base, Tuning.SpawnInterval still multiplies). Horde rounds: 0.65 x 0.95^(r-1), floor 0.35, spawned in packs of 4 from one rotating entrance. Catch-up: while ZombiesAlive < 8 and quota remains, spawn 2 per interval. Pressure relief: while a boss is alive the interval doubles. Stall guard: if no entrance passes the gates for 4 s, relax only the forward-cone visibility gate (distance 14-100 m and reachability gates stay) so the vendor Tick is never skipped longer than 4 s. Stragglers relocate to an eligible entrance at full wave-scaled health. The same actor keeps its place in the wave (see the Stage 1 straggler rules). After a Nuke the next spawn is delayed 3 s. Boss spawns bypass the interval (see boss_round_rule). MaxConcurrent 24 throttle kept.
- Intermission: 10 s
- Speed tiers: SpeedMultiplier = 1.0 on every CustomWaves row (AutoSpeedScalePerWave 1.0; the live 1.02^wave creep and the identical per-tick MaxWalkSpeed rewrite are removed). At spawn each Standard rolls: speed = 4 x r (R1 forced speed = 1); k = rand[speed, speed + 35]; k <= 35 Walker 180 cm/s, k <= 70 Runner 400, else Sprinter 600 (MaximumRunSpeed cap 620). Result: R1 100% walkers, R5 ~44% walkers, R9 last walkers (~3% sprinters), R13 ~47% sprinters, R18+ 100% sprinters. Stored as a per-instance SpeedTier float on AHoverCyberZombie at BeginPlay and applied in AHoverCyberZombieAI::Tick. After R3 the last 3 zombies alive of a round are forced to Sprinter; every 10 s one Walker/Runner farther than 25 m from the player is promoted one tier (straggler rule). Kid always 700 (cap 820). Riot never above Runner (Walk 160 / Runner 320). Brute 260 (enraged 420 for 8 s below 30% HP), Alpha Brute 300 (enraged 650 below 50%), Warden Walk 240 / Jog 420 / charge 700 for 1.5 s. Each tier has its own blend-space clip and vocal cue (ZombieV2 ChasingSlow for walkers, Chasing for sprinters) so the tier is readable at 30 m. Per-instance attack-cadence jitter 0-0.4 s and zig-zag path deviation come from the crowding slice.
- Horde rounds: Rounds 5, 10, 15, 20, 25, 30 and every 5 after (SwarmFirstWave 5 / SwarmInterval 5 on UHoverCyberEncounterSettings, swarm count clamp raised from 24 to 80): the round is K(r) = 10 + 2r Kids only (20/30/40/50/60/70 at R5-30), health 0.45 x H(r), always Sprint 700, half band damage at 0.85 s cadence, 90 points each, packs of 4 at 0.65 x 0.95^(r-1) s (floor 0.35) from a single rotating entrance, concurrent cap 24, no Riot/Brute/boss, HUD banner KID SWARM - stay moving. The last Kid's death always drops a Max Ammo at the player's feet (BO6/BO7 special-round rule); plates are not restored. From R21 Kids also make up 10% of the standard quota on normal rounds. Priority on a shared round number: horde beats heavy beats boss (none collide in the R1-30 table).
- Heavy rounds: R8 is the Brute debut: exactly one Brute spawned at 50% of the quota (BruteDebutWave field, HUD banner HEAVY TANK). Heavy rounds are every even round from R12 that is not a horde round: 12, 14, 16, 18, 22, 24, 26, 28, then 32, 34... (BruteFirstWave 12 / BruteInterval 2 with the ClampMin 11 in HoverCyberVariants.h lowered to 8 and horde priority on 20/30). Brute count B(r) = min(4, 1 + floor((r - 8) / 6)): R12-13 1, R14-19 2, R20-25 3, R26+ 4 (BO6 Mangler cap), spawned at 25/50/75/90% of the quota so they never arrive together; each Brute replaces one standard. Brute drops are guaranteed and alternate per heavy round: the first Brute killed drops Max Ammo, the second Max Health (full heal + plates refilled = Max Armor stand-in), third Max Ammo, fourth Max Health - heavy rounds are the ammo-and-armor economy rounds and the income check depends on this rule. Riot armored (Stage 2) are not round-gated: 15% of standards R9-16, 20% from R17, max 6 alive, zero on horde and boss rounds. Heavy rounds play the strength-step stinger (SC_Zombie_Roar) at start.
- Boss rounds: Three scripted set pieces to R30, then alternating every 6: R13 Warden, R19 Alpha Brute, R27 Warden + Alpha Brute (Alpha enters when the Warden reaches 50% HP), R33 Warden + 2 Brutes, R39 2 Alpha Brutes, R45 both... Bosses are ADDITIVE to N(r). The boss spawns when 40% of the round quota is dead, from the entrance farthest from the player, bypassing the spawn interval, with a 1.2 s roar stinger, screen shake and HUD banner; the standard spawn interval doubles while the boss lives; Riot share is zero and no extra Brutes (boss rounds are never heavy rounds); the boss counts as 1 toward MaxConcurrent. Boss HP = multiple x H(r): Warden 15x (R13 6,900 = 50 PaP I headshots = 6.25 s, 33 on the exposed weak point = 4.1 s; R27 39,000 = 70 PaP III headshots = 8.75 s, 47 weak point = 5.9 s), Alpha Brute 12x (R19 10,920 = 39 PaP II headshots = 4.9 s; R27 31,200 = 56 PaP III headshots = 7.0 s). The boss must die to end the round (existing ZombiesAlive == 0 rule); on death: guaranteed Max Ammo, 500 points, 3 s slow-motion kill cam; the R27 pair = 1,000 points and two Max Ammos. Stage 1 ships Alpha Brute on every boss round (R13 Alpha 12 x 460 = 5,520 HP = 40 PaP I headshots); Warden replaces it on R13/R27 in Stage 2 if the owner accepts the StoneGolem re-skin. No final boss; the mode is endless.

Round table (standard zombie health, zombie count):

| Round | Std health | Count |
|---|---|---|
| 1 | 100 | 6 |
| 2 | 125 | 8 |
| 3 | 150 | 13 |
| 4 | 175 | 18 |
| 5 | 200 | 24 |
| 6 | 225 | 27 |
| 7 | 250 | 28 |
| 8 | 275 | 28 |
| 9 | 300 | 29 |
| 10 | 325 | 33 |
| 11 | 370 | 34 |
| 12 | 415 | 36 |
| 13 | 460 | 39 |
| 14 | 505 | 41 |
| 15 | 550 | 44 |
| 16 | 640 | 47 |
| 17 | 730 | 50 |
| 18 | 820 | 53 |
| 19 | 910 | 56 |
| 20 | 1000 | 60 |
| 21 | 1200 | 63 |
| 22 | 1400 | 67 |
| 23 | 1600 | 71 |
| 24 | 1800 | 75 |
| 25 | 2000 | 80 |
| 26 | 2300 | 84 |
| 27 | 2600 | 89 |
| 28 | 2900 | 94 |
| 29 | 3200 | 99 |
| 30 | 3500 | 105 |

Special schedule:

- R1-4: Standard only (6/8/13/18), walkers dominant, teaching rounds; R1 all walkers
- R5: HORDE 20 Kids, Max Ammo on clear
- R6-7: Standard 27/28, ~40% walkers
- R8: Brute debut (1 Brute at 50% quota, 1,650 HP, 48 PaP 0 body / 24 head), PaP I economy point
- R9: Riot armored enter at 15% of standards (Stage 2); last walkers; PaP I in hand
- R10: HORDE 30 Kids, Max Ammo
- R11-12: R11 normal 34; R12 first heavy round (1 Brute at 50%)
- R13: BOSS Warden (Stage 1: Alpha Brute) + 39 standards, no Riot; R14 heavy (2 Brutes)
- R15: HORDE 40 Kids, Max Ammo; PaP II economy point (end R15)
- R16: heavy (2 Brutes); R17 normal, Riot share 20%; R18 heavy (2 Brutes), all standards are sprinters
- R19: BOSS Alpha Brute (10,920 HP) + 56 standards; R20: HORDE 50 Kids, Max Ammo
- R21: Kids bleed into normal rounds at 10%; R22 heavy (3 Brutes); R23 normal; PaP III economy point (end R23-24)
- R24: heavy (3 Brutes); R25: HORDE 60 Kids, Max Ammo; R26 heavy (4 Brutes)
- R27: BOSS Warden + Alpha Brute (Alpha at 50% Warden HP), 89 standards, two Max Ammos; R28 heavy (4 Brutes); R29 normal
- R30: HORDE 70 Kids, Max Ammo; R31+: damage band 75, health +800/round, heavy every even non-horde round with 4 Brutes, boss every 6 from R33, +1,000/round from R41, 25,000 cap at R54

### 1.3 Enemies

| Name | Role | Asset | Health x base | Speed | Damage | First round | Cadence | Points | Signature |
|---|---|---|---|---|---|---|---|---|---|
| Street Zombie - Walker / Runner tiers | standard | DA_NYC_Standard01-04 (duplicates of HoverPrototype/ZombieEngine/Variants/Standard01-04 UHoverCyberZombieDefinition, SK_Standard0x 180 cm, retargeted ZESP Zombie_001 clips AS_Walking / BS_Zombie_WalkRun / AM_Attack_01-02 / AM_Hit / AM_Death, NS_NS1_BloodShot); MaxHealth 100, MeleeDamage 30, AttackRange 150; audio ZombieV2 ChasingSlow / Idle / Pain | 1 | Walker 180 or Runner 400 cm/s by the per-spawn roll (100% walkers R1, 44% R5, 0% from R9; runners dominant R9-13) | band x1.0: 30 / 50 / 75; AttackCooldown 1.5 s + 0-0.4 s per-instance jitter; 0.5 s wind-up telegraph (arm raise) before the swing | 1 | every round, fills N(r) minus Brutes/Riots/Kid bleed-in; round-robin across the four looks; share shrinks as the roll promotes to Sprinter | 90 | Upper-body flinch on any hit >= 10% MaxHealth, allowed every 0.35 s and while attacking (cancels the swing; requires relaxing the 0.8 s / !bIsAttacking rule in the patched ZE_ZombieCharacter.cpp); headshot kill = head gib + 115 points; katana kill 105 (2 swings R1-10, 3 swings R11-15); TTK at band end 8 body / 4 head = 1.0 s / 0.5 s at FireRate 8 |
| Street Zombie - Sprinter tier | standard-fast | same DA_NYC_Standard01-04 definitions, Run clip AS_Run / BS_Zombie_WalkRun at 600; vocal ZombieV2 Chasing + Roar on first sight | 1 | 600 cm/s (cap 620); share = clamp((4r - 35)/36): ~3% R9, ~47% R13, 100% from R18; last 3 zombies alive after R3 forced to this tier | band x1.0 (30 / 50 / 75), same cooldown; 0.3 s lunge when within 250 cm (telegraph: roar + arms forward) | 3 | every round by the roll; the straggler-promotion rule feeds this tier | 90 | Vexa sprint 900 beats 600 so a runner line can be broken, but a 1.5 s reload = 9 m of closure; a sprinter that loses its path for 20 s is re-queued to spawn ahead of the player (straggler re-queue), never idles |
| Kid Swarmer (horde unit) | horde | DA_NYC_Kid (duplicate of Variants/Kid: SK_Kid 110 cm, Role Kid, MaxAcceleration 2600, MaxHealth 45, MeleeDamage 15); vocal ZombieV2 Hiss / Speech | 0.45 | always Sprint 700 cm/s (MaximumRunSpeed 820) | band x0.5: 15 / 25 / 38 at 0.85 s cadence | 5 | horde rounds 5, 10, 15, 20, 25, 30 as the whole round (K(r) = 10 + 2r); from R21 also 10% of the standard quota on normal rounds | 90 | Dies to one katana swing through R12 (R13: 207 HP vs 200) and to 1-3 Ballista shots through R15 at the expected tier, so hordes are a tempo change not a wall; no flinch (hits only kill), stagger on grenade; the last Kid of a horde round drops the guaranteed Max Ammo |
| Riot (armored heavy) - Stage 2 | armored | DA_NYC_Riot: SK_Standard02/04 mesh with ZESP SKM armor helmet + chest (Content/ZESP/ZE/SkeletonMesh/Armor) attached to head/spine sockets (socket compatibility on the retargeted skeleton must be verified), ZESP Black outline MI; Jog clip only; vocal ZombieV2 Inhale/Exhale; new EHoverZombieRole::Riot | 2 | Walker 160 / Runner 320, never sprints (BO7 armored rule) | band x1.5: 45 / 75 / 113, 1.8 s cooldown; shoulder shove 300 cm knockback (no knockdown) within 200 cm | 9 | 15% of standards R9-16, 20% from R17, max 6 alive, zero on horde and boss rounds | 150 | Single ablative armor pool = 0.5 x H(r) on top of 1.5 x H(r) body (2.0x effective): the AHoverCyberZombie::TakeDamage override routes damage to the pool BEFORE Super so headshot multipliers and flinch are suppressed while the pool > 0; when it breaks the helmet/chest meshes hide with a clang + 0.6 s stagger and headshots open; explosives x0.5 vs the pool; shots at expected tier: R9 9 PaP I, R17 11 PaP II, R25 15 PaP III |
| Brute (heavy-round tank) | heavy | DA_NYC_Brute (duplicate of DA_Brute: SK_Brute 250 cm, AM_Brute_Smash, AM_Brute_Stomp with UHoverBruteStompNotify, RotationRate 220, MaxHealth 600, MeleeDamage lowered 75 -> 60 so the band scales it) | 6 | 260 cm/s (cap 380); enraged 420 for 8 s below 30% HP | swing band x2.0: 60 / 100 / 150, 3.5 s cooldown; stomp band x2.0 in 400 cm + 2.1 s knockdown (existing ApplyStompKnockdown), 0.8 s minimum stomp interval | 8 | R8 single debut at 50% quota; heavy rounds 12, 14, 16, 18, 22, 24, 26, 28 with B(r) = min(4, 1 + floor((r - 8)/6)); never on horde or boss rounds | 250 | Stomp telegraph: ground-crack decal + Vefects shockwave ring drawn at 0.6 s of the 2.367 s stomp clip so the 400 cm radius is visible before impact; shots at expected tier: R8 48 body / 24 head PaP 0 (3.0 s of headshots), R12 36/18 PaP I (2.25 s), R16 28/14 PaP II, R22 60/30 PaP II (3.75 s), R28 63/32 PaP III (4.0 s) - a 1-2 magazine commitment while sprinters close; guaranteed drop alternating Max Ammo / Max Health per heavy round |
| Alpha Brute (mid-level boss A, Stage 1 shippable) | boss | DA_NYC_AlphaBrute = data duplicate of DA_Brute: same SK_Brute / AM_Brute_Stomp / AM_Brute_Smash (played 0.9x), Height 300, CapsuleRadius 48, M_Brute darkened + emissive red eyes (MI_Brute_Alpha), MaxHealth 1,200, MeleeDamage 90, StompRadius 500, roar SC_Entity_Roar, blood NS_NS1_BloodShot x2; no new mesh or clips | 12 | 300 cm/s; enraged at 50% HP: 650 cm/s sprint (Vexa must sprint) with 2-stomp chains | swing band x3.0: 90 / 150 / 225; stomp band x2.0 + knockdown radius 500 cm, 2.5 s cooldown | 19 | R19, R27 (enters at 50% Warden HP), then R39, R51...; in Stage 1 also R13 and every boss round in place of the Warden | 500 | Tempo flip: first half is the known Brute at bigger scale (stomp ring telegraph), second half is a sprinter that cannot be out-walked, announced by a roar and a 1 s red screen pulse; headshot x2 stays (no armor): R19 10,920 HP = 39 PaP II headshots (4.9 s) per phase; R27 31,200 = 56 PaP III headshots (7.0 s); spawn interval doubles during the fight; guaranteed Max Ammo + kill cam on death |
| Warden (mid-level boss B, Stage 2 stretch) | boss | DA_NYC_Warden: Content/StoneGolem SKM_StoneGolem + Parts SKMs (Helmet / Pauldron / ChestArmor / Greaves) + SM_StoneGolem_Hammer, skin MI_StoneGolem_Body_Skin2 with a rebar/rubble tint so it reads as animated rubble in NYC; own skeleton SKEL_StoneGolem with ABP wrappers for attack1-5, gethit1-3, death1-3, jogF/walkF, turn180; new EHoverZombieRole::Warden, Height 320, CapsuleRadius 70, nav agent radius 70; VFX_Shockwave_02_White_Big_1s; roar SC_Monster_Roar; MaxHealth 1,500, MeleeDamage 75 | 15 | Walk 240 / Jog 420; charge 700 for 1.5 s after a 1.2 s roar telegraph (turn180 clip); never sprints | hammer slam band x2.5: 75 / 125 / 188 in 600 cm + 2.1 s knockdown, 4 s cooldown; charge contact band x2.0 + 500 cm launch | 13 | R13, R27 (with Alpha Brute), then R33, R45...; Stage 1 substitutes Alpha Brute | 500 | Three armor-break phases at 75 / 50 / 25% HP: a Part SKM (Helmet, then Pauldron + ChestArmor, then Greaves) detaches with a 1.0 s gethit stagger and exposes a glowing weak point (x3 damage, replaces the head-bone multiplier) for the rest of the fight; R13 6,900 HP = 99 PaP I body / 50 head (6.25 s) / 33 weak point (4.1 s), R27 39,000 = 70 PaP III head (8.75 s) / 47 weak point (5.9 s); kite-and-punish fight; death1-3 with 3 s corpse; guaranteed Max Ammo + kill cam |

### 1.4 Weapons

TTK targets: Ballista: 35 body / 70 head base, FireRate 8 automatic (authored: bAutomatic true + FireRate 8 on DA_AFS_Ballista.._4; seconds = shots x 0.125), headshot x2 all tiers (x3 with Deadshot), mag 30, reserve 270 / 360 / 450 / 540 by PaP tier. Expected path: PaP 0 R1-8, PaP I from R9, PaP II from R16, PaP III from R24-25. Body / head shots (seconds): PaP 0: R1 3/2 (0.4/0.25), R5 6/3 (0.75/0.4), R8 8/4 (1.0/0.5) -> buy PaP I end R8. PaP I (70/140): R9 5/3, R10 5/3, R13 7/4, R15 8/4 (1.0/0.5), R16 10/5 -> PaP II end R15-16. PaP II (140/280): R16 5/3, R18 6/3, R20 8/4 (1.0/0.5), R23 12/6, R24 13/7 -> PaP III end R23-24. PaP III (280/560): R24 7/4, R25 8/4, R26 9/5, R28 11/6, R30 13/7 (1.6/0.9 s; Double Tap 9.6 shots/s and Deadshot x3 head bring R30 back to 1.3 s / 0.6 s). Beyond R30 TTK grows to the 25,000 cap (PaP III 90 body / 45 head = 11 s / 5.6 s at R54) - endurance rounds by design. Design band: 3-5 body on a fresh tier, 8 at band end, never above 13 before R31. Bosses 40-70 headshots (5-9 s plus reloads) with weak-point windows halving that; Brutes 14-32 headshots. Katana 50 + 12.5(r-1) capped 400: 2 swings R1-10, 3 R11-15, 4 R16-20, 6 at R25, 9 at R30; Kids 1 swing through R12. Frag 1.5 x H(r) at <= 250 cm.

Damage ladder:

- Ballista PaP 0 (DA_AFS_Ballista): 35 body / 70 head, FireRate 8 auto, mag 30, reserve 270, reload 1.5 s, BaseSpread 0.5 + 0.35/shot max 3.0, SpreadRecovery 12/s that also runs while the trigger is held, recoil 0.35 pitch / 0.15 yaw per shot (replaces the 0.03 deg integrated recoil), fire montage + BP_M16_FireShake camera shake actually played (PlayFireAnimation no longer a no-op), gunshot volume 1.0, 120 ms tracer, muzzle light; kills R1 3 body / 2 head, R5 6/3, R8 8/4
- Ballista PaP I (DA_AFS_Ballista_2, x2): 70 / 140, reserve 360, tracer NS_ArrowTrail_Fire; R10 5/3, R15 8/4, R16 10/5; ammo refill 750
- Ballista PaP II (DA_AFS_Ballista_3, x4): 140 / 280, reserve 450, reload 1.3 s, penetration 1 body at 60% damage, tracer NS_ArrowTrail_Ice; R16 5/3, R20 8/4, R24 13/7; refill 1,500
- Ballista PaP III (DA_AFS_Ballista_4, x8): 280 / 560, reserve 540, reload 1.2 s, penetration 2 bodies, tracer NS_ArrowTrail_Holy + NS_Lightning_Damage_Land_Small on headshot kills; R25 8/4, R30 13/7; refill 3,000
- Full body grid: PaP 0 35 | I 70 | II 140 | III 280 (head x2: 70 / 140 / 280 / 560; Deadshot x3: 105 / 210 / 420 / 840)
- Sidearm (ZESP DA_Weapon_Pistol_001 + SM_Pistol via AHoverCyberRifle, wall buy 500): 25 / 50, semi-auto 6 shots/s, mag 12, reserve 96; PaP I only (x3 = 75 / 150, DA_Weapon_Pistol_PaP); the downed/backup weapon
- M16 (ZESP DA_Weapon_Rifle_001 + SM_M16, wall buy 1,250, Stage 2): 30 / 60 full-auto at FireRate 10 (the vendor cannot express 3-round burst), mag 30, reserve 240; PaP via DA_Weapon_Rifle_002-004 re-stat to x2/x4/x8
- Heavy Ballista (DA_AFS_Ballista_5 re-authored, SM_CS1_Crossbow_03a mesh, armory 3,000, Stage 2): 90 / 225 (x2.5), semi 4 shots/s, mag 12, reserve 72, reload 2.2 s, penetration 3; PaP tiers need DA_AFS_HeavyBallista_2..4 (x2/x4/x8); R30 PaP III 5 body / 2 head
- Katana (DA_AFS_Melee, free, R3 hold): 50 + 12.5 x (r - 1) damage capped 400, 1.1 swings/s, 160 cm; 105 points per kill; hit stagger on anything below Brute; useless vs Riot armor pool
- Frag grenade (DA_Grenade_Frag, AZE_GrenadeWeapon, ExplosionDamage scaled in a subclass): 1.5 x H(r) at <= 250 cm falling to 10% at 500 cm, fuse 3 s, carry 2 (4 with Stamin-Up), 250 per 2; x0.5 vs Riot pool; never kills a Brute above 25% HP
- Headshot rule: Stats.HeadBoneName must match the variant skeletons (bone 'head', case-insensitive check); the kill-point bone check happens in AHoverCyberZombie::TakeDamage before Super consumes the FPointDamageEvent

Pack-a-Punch tiers:

| Tier | Price | Damage x | Extra |
|---|---|---|---|
| 1 | 5000 | 2 | Swap quickbar item to DA_AFS_Ballista_2 in the same slot (remove instance, AddItemDefinition, AssignInstanceToQuickbar, copy clip ratio, identical AmmoTypeId so the reserve pool is shared), free full refill (BO rule), reserve 360, fire tracer, Vefects shockwave burst at the station; refill price 750; affordable end R8 on all three income models |
| 2 | 15000 | 4 | DA_AFS_Ballista_3, reserve 450, reload 1.3 s, penetration 1, ice tracer, free refill; refill price 1,500; affordable end R15 (R16 all-body) |
| 3 | 30000 | 8 | DA_AFS_Ballista_4, reserve 540, reload 1.2 s, penetration 2, holy tracer + muzzle light, free refill; refill price 3,000; station then shows MAXED; affordable end R23 (R24 at 25% / all-body); PaP total 50,000 |

Armory:

- Starting kit: Ballista PaP 0 in quickbar 1 with 30 + 270, katana, 2 frags, tier 1 vest with 1 plate, 1 Self-Revive, 500 points
- Checkpoint Plaza kiosk (BP_Kiosk, AZE_WallBuyActor subclass AHoverArmoryStation): Sidearm 500, Ballista re-buy 1,750 (PaP 0), ammo refill-to-full, plates 50
- South Avenue: M16 wall buy 1,250 (Stage 2); North Avenue: Frag wall buy 250 per 2, armor station vest II 4,000
- Survivor Shelter station: Self-Revive 1,500 (max 3 held), Stim 500, Noisemaker 500 (Stage 2), Power switch (free, 25 s defend objective)
- Underpass: Pack-a-Punch station (ZESP BP_Buy_01 re-skinned, requires Power): 5,000 / 15,000 / 30,000 on Ballista, Heavy Ballista, M16, Sidearm (tier I only)
- Uptown Barricade armory: Heavy Ballista 3,000 (Stage 2); saw-barrel trap 750 (Stage 2)
- Garage Block: armor station vest III 10,000, plates 50
- Perk vending (one per zone, ZESP BP_Buy_01 re-skinned, perks are bUnique UZE_ItemDefinition items read from inventory by the bridge): 2,500 + 500 x perks owned
- No Mystery Box / no Wonder Weapon (no asset); the unused SM_CS1_Crossbow_0Xa_Nanite meshes are visual variants per PaP tier if desired

Ammo prices:

- Ballista refill-to-full at any wall buy / ammo cache, price computed from the owned PaP tier by AHoverArmoryStation::ExecutePurchase (not the vendor MagazineSize x 2 AmmoCost): 250 (PaP 0, 270 rounds) / 750 (PaP I, 360) / 1,500 (PaP II, 450) / 3,000 (PaP III, 540) - the BO7 250/1,000/2,500/5,000 ladder compressed for a single-currency solo economy; cost per standard kill at band end = 7.4 / 16.7 / 26.7 / 72 points, always below the 90-point award
- Sidearm refill 100 (PaP 0) / 250 (PaP I); M16 refill 250 / 750 / 1,500 / 3,000; Heavy Ballista same ladder
- Frag 250 per 2; Armor plate 50 each; Stim 500
- Max Ammo power-up: every quickbar weapon to full reserve + grenades (plates excluded so Max Health keeps its armor role); GUARANTEED at the end of every horde round, on every boss death, and from the first (and third) Brute killed on each heavy round
- PaP purchase refills ammo for free (BO rule)

### 1.5 Economy

| Kill | Crit kill | Melee kill | Special | Boss | Starting |
|---|---|---|---|---|---|
| 90 | 115 | 105 | 250 | 500 | 500 |

Door prices:

- Door 1 South Avenue 750 (R1-2)
- Door 2 North Avenue 1,000 (R2-3)
- Door 3 Survivor Shelter 1,250 (R6; holds the Power objective)
- Door 4 Underpass 1,500 (R6; Pack-a-Punch, needs Power -> minimum spend before PaP I = doors 1+2+3+4 = 4,500)
- Door 5 Uptown Barricade 1,750 (R9-10)
- Door 6 Garage Block 2,000 (R11-12; vest III, exfil truck in Stage 2)
- Total 8,250 for all six doors (BO6 Liberty Falls PaP route 7,500; BO7 Ashes 500-1,750); every door removes an owned BP_T_Wall/WiredFence_Gate dressing actor with the PostApocalypticCity SW_Door sound, enables the zone's spawners and plays the zone-name banner
- Trap (Stage 2): Uptown saw-barrel fire trap 750 per 20 s activation, 45 s cooldown, needs Power, kills anything below Brute, half damage to bosses
- Exfil booth (Stage 2, Garage SM_PhoneBooth, R11 then every 5): free; kill the HVT Alpha Brute (1.5x) within 2:00 or game over; success ends the match with a scored exfil screen

Perks:

- Pricing: cost = 2,500 + 500 x (perks already owned): 2,500 / 3,000 / 3,500 / 4,000 / 4,500 / 5,000 = 22,500 for all six; one fixed vending spot per perk, no Wunderfizz; most recent perk is lost on each Self-Revive
- Juggernog (North Avenue): MaxHealth 150 -> 250 (Survival->SetMaxHealth)
- Quick Revive (South Avenue): regen delay 6 s -> 3 s, +1 Self-Revive capacity
- Speed Cola (Survivor Shelter): reload and plate insert 30% faster
- Deadshot (Underpass): headshot multiplier x2 -> x3 on all tiers, aim snap to head bone
- Double Tap (Uptown Barricade): fire rate +20% (Ballista 8 -> 9.6 shots/s, Heavy Ballista 4 -> 4.8)
- Stamin-Up (Garage Block): sprint 900 -> 1,050, walk 500 -> 560, grenade carry 2 -> 4, knockdown recovery 2.1 s -> 1.4 s

Equipment prices:

- Frag x2: 250 (max 4 held with Stamin-Up)
- Armor plate: 50; Armor vest tier 2: 4,000; tier 3: 10,000 (14,000 total)
- Self-Revive: 1,500 (max 3 held, 4 with Quick Revive, 1 free at start)
- Stim (DA_Medkit consumable, instant +75 HP, overheal to +100 for 20 s): 500, carry 2
- Noisemaker (Stage 2, SM_WalkieTalkie prop, Monkey-bomb role: every zombie within 30 m paths to it for 10 s, then 1.0 x H(r) in 300 cm): 500, carry 1
- Sidearm 500; M16 1,250 (Stage 2); Heavy Ballista 3,000 (Stage 2); Ballista re-buy 1,750
- Trap activation 750 (Stage 2); Pack-a-Punch 5,000 / 15,000 / 30,000

Power-ups:

- Drop rule (BO3 lineage, in the mode not the DA LootTable): score threshold starts at 2,000 points earned and multiplies by 1.14 after each drop; 3% pure random roll per kill; max 4 drops per round; never in the first 10 kills of a round; 15 s solid + 11 s blink = 26 s lifetime; spawns at the death spot via AHoverCyberPowerUp
- Max Ammo (existing): all weapons full reserve + grenades; guaranteed on horde clear, boss death, first/third Brute of a heavy round
- Insta-Kill (existing, Duration 15 -> 30 s in BP_CyberPower_InstaKill): Standard/Kid/Riot die to any hit, Brutes take x4, bosses x2 (handled in the AHoverCyberZombie::TakeDamage override)
- Nuke (existing): kills every Standard/Kid/Riot alive, +400 points, next spawn delayed 3 s, Brutes/bosses take 25% of max
- Max Health (existing enum, adapter branch added): full heal + plates refilled to the owned tier (Max Armor stand-in); guaranteed from the second/fourth Brute of a heavy round
- Speed Boost (existing, 15 s x1.5): kept, sells the parkour
- Danger: removed from every loot table
- Stage 2 (new EZE_PowerUpType values in the patched plugin enum): Double Points 30 s (all awards x2), Bonus Points +500; not ported: Carpenter, Fire Sale, Random Perk

Income check: Model: standard kill 98.75 expected (65% body 90 / 35% headshot 115), conservative 96.25 (25% headshot) and all-body 90 also run; Kids 90, Riot 150, Brute 250, boss 500; no Double Points / Bonus Points / Nuke income; count table with horde K(r), Brutes/Riots replacing standards, bosses additive, Riot zero on boss rounds, 10% Kid bleed-in from R21; start 500. Ammo: shots per kill = ceil(HP / body damage) at the owned tier (headshot savings offset misses), refill-to-full bought whenever the pool runs dry at 250/750/1,500/3,000, only GUARANTEED Max Ammo drops counted (horde clear, boss death, first/third Brute per heavy round), PaP purchase refills free. CUMULATIVE EARNED incl. start - expected: R5 6,744 | R10 20,860 | R15 41,046 | R20 68,378 | R25 104,480 | R30 151,664; conservative: 6,631 | 20,480 | 40,339 | 67,232 | 102,860 | 149,351; all-body: 6,350 | 19,530 | 38,570 | 64,370 | 98,810 | 143,570. Per-round income samples (expected): R1 592, R5 1,800, R8 2,916, R9 3,069, R12 3,962, R13 (boss) 4,351, R15 3,600 (40 Kids), R19 (boss) 6,030, R22 7,684, R27 (double boss) 9,789, R29 10,714, R30 6,300. SPEND PATH (expected income, running balance after the round's purchases): R1 Door 1 750 -> 342 | R2 Door 2 1,000 -> 132 (buy at R3 instead for a 1,180 buffer) | R5 Vest II 4,000 -> 994 | R6 Door 3 1,250 + Door 4 1,500 -> 910 | R7 ammo 250 | R8 PaP I 5,000 -> 1,341 | R9 Juggernog 2,500 + Door 5 1,750 -> 160 | R11 Quick Revive 3,000 + Door 6 2,000 -> 1,474 | R15 PaP II 15,000 -> 3,046 | R16 Speed Cola 3,500 -> 4,849 | R17 Vest III 10,000 -> 299 | R18 Deadshot 4,000 -> 2,348 | R21 ammo 1,500 | R23 ammo 3,000 + PaP III 30,000 -> 564 | R24 Double Tap 4,500 -> 4,580 | R25 Stamin-Up 5,000 -> 4,980 | R29 ammo 6,000 | R30 ammo 3,000 -> 43,164 end balance. Cumulative spend 108,500 (ammo 13,750 of it) vs 151,664 earned = 72% utilisation; the ~40,000 surplus funds the Stage 2 Heavy Ballista + PaP I/II, Self-Revives, Stims, plates and traps. Conservative (25%): identical milestones except Deadshot R18, PaP III + Double Tap R24, Stamin-Up R25, end 39,351, lowest 98 at R2. All-body (90): PaP I R8, Juggernog R9, PaP II R15, Vest III R18, Deadshot R19, PaP III R24, Double Tap R25, Stamin-Up R26, end 33,570, lowest 10 at R2 (1,180 if Door 2 waits to R3). Ammo sanity: cost per standard kill at band end is 7.4 (PaP 0 R8) / 16.7 (PaP I R15) / 26.7 (PaP II R24) / 72 (PaP III R30) points against the 90 award, so shooting is never net-negative through R30; late rounds need 1-2 refills (R26-28 covered by heavy-round Brute Max Ammos, R29 2 refills = 6,000 vs 10,714 income). Milestones vs benchmark: PaP I R8 (BO7 solo R8-10), 50,000 total PaP by R23-24 (BO7 ~R25-30), all six perks by R25-26, every purchase lands at least one round before the health step that needs it (PaP I before the R11 +45 band, PaP II before the R16 +90 band, PaP III before the R26 +300 band). Without the Brute Max Ammo rule PaP III slips to R27-28 and R26-30 becomes break-even; without flattening R26-30 (+400 as in the winner) PaP III is unaffordable by R30 - both were simulated.

### 1.6 Zones

| Order | Zone | Door price | Contents | Spawners |
|---|---|---|---|---|
| 0 | Checkpoint Plaza (spawn) | 0 | Owned PlayerStart in L_NYC_Survival at (271, 5241, 162) yaw -90 (same spot as the vendor start, vendor actor untouched); street corridor y 4,800-5,700 at x 100-450; kiosk shop: Sidearm 500, Ballista re-buy 1,750, ammo refill, plates 50; sandbag cover along the curb; exits: south gate (Door 1) and north gate (Door 2) built from owned BP_T_Wall_Double_a_BarbedWire pairs; graph 0-1, 0-2; spawn pool = this zone + opened neighbours (one hop), rebuilt every 1 s from zone-tagged AZE_ZombieSpawnPoint actors | 4 |
| 1 | South Avenue | 750 | Corridor y 3,600-4,800; Quick Revive vending; M16 wall buy 1,250 (Stage 2); two building-entrance alcoves as training loops; link to Underpass (Door 4) at its south end; graph 1-4 | 4 |
| 2 | North Avenue | 1000 | Corridor y 5,700-6,600 including the truck lane; Juggernog vending; armor station vest II 4,000 / plates 50; Frag wall buy; parked PA_SUV cover; links to Survivor Shelter (Door 3) east, Uptown Barricade (Door 5) north, Garage Block (Door 6) west; graph 2-3, 2-5, 2-6 | 4 |
| 3 | Survivor Shelter | 1250 | BP_SurvivorShelter block east of North Avenue (x 600-1,100, y 5,900-6,400 pending the level pass); Power objective: BP_LightTower generator, hold F to start a 25 s defend window (spawn interval x0.5 while active), then the switch lights the city and enables PaP, the trap and the Garage jump pad; Speed Cola vending; Shelter station: Self-Revive 1,500, Stim 500, Noisemaker 500 (Stage 2); single entrance = the panic room | 3 |
| 4 | Underpass | 1500 | SM_Underpass set at the south end y 3,000-3,600; Pack-a-Punch station (ZESP BP_Buy_01 re-skinned on an SM_AmmoBox base, Vefects shockwave on purchase), requires Power; Deadshot vending; ammo cache; spawners are ground emergers (ZombieAnimationPack Burst clips, retarget needed) so the PaP room is a crawl-out ambush | 3 |
| 5 | Uptown Barricade | 1750 | North end y 6,600-7,200 (truck turnaround, military checkpoint meshes); Double Tap vending; ammo cache; Heavy Ballista armory 3,000 and saw-barrel fire trap 750 at the choke between the two BP_T_Wall_Corner_BarbedWire corners (Stage 2); longest open training loop around the SM_MilitaryBase_Concrete_Barrier island; boss spawn entrance (farthest from spawn) | 4 |
| 6 | Garage Block | 2000 | West side block (x -400..100, y 5,600-6,100 pending the level pass, BP_Base_02 dressing); armor station vest III 10,000 / plates 50; Stamin-Up vending; jump pad back to Checkpoint Plaza (after Power); Doomsday truck parked as set dressing (Stage 1) and exfil set piece with SM_PhoneBooth HVT call (Stage 2); dead-end late-game camp with a single approach; graph 6-0 one-way via the jump pad | 3 |

Spine risks:

- MAP AND NAV: NYC has no navmesh, no AZE_ZombieSpawnPoint, no zone/door actors; all 25 spawners, 6 doors, 7 zone volumes, stations, an owned PlayerStart and a NavMeshBoundsVolume must be authored into the NEW owned map L_NYC_Survival (same four vendor sublevels, vendor SetDressing untouched) and AddCityNavigation extended past its world-name gate; zone extents beyond the x 100-450 / y 3,000-7,200 corridor are placeholders until a path test (ReviewCyberSpawns pattern) runs; every zone must keep >= 3 entrances 14-100 m from any reachable player position or rounds deadlock even with the stall guard.
- OWNER AMENDMENTS (must be in the design doc): AGENTS.md L26-28 add 'NYC - Survival (index 4, L_NYC_Survival, AHoverNYCSurvivalGameMode subclass of AHoverCyberCityGameMode) is the only NYC entry that may spawn zombies/waves; it never spawns the bike; the index-3 NYC - Exploration rules are unchanged'; README.md level table (index 4) and the ?game= option; Docs/CONTROLS.txt economy rows (points 90/115/105/250/500, plates, perks, PaP, doors, ammo ladder, reserve 270) and keys; HoverTestController level table index 4 + HoverGraphicsMenu '% 4' -> '% 5'; .gitignore Docs whitelist for Docs/NYC_SURVIVAL_<date>.txt; PAL_AFS_Runtime cook roots for /Game/HoverPrototype/NYC; VerifyNYCExploration.py unchanged, new VerifyNYCSurvival.py asserting the R1-30 health/count/damage rows and that index 3 still has zero zombies.
- HEALTH DELIVERY: the adapter tick calls WaveSettings->GetDifficultyMultipliers(CurrentWave) on the DA, so R1-30 are CustomWaves rows (30 FZE_WaveConfig entries to author and dump) and R31+ needs the ConfigureWave formula fallback plus a one-line redirect in AHoverCyberZombieAI::Tick; CustomWaves beyond the last row is unverified vendor behaviour and AutoHealthScale 1.0 would otherwise collapse health to 100 at R31. The per-tick MaxHealth rewrite must read a per-actor HealthScale frozen at spawn, and FHoverZombieTuning.Health (runtime menu .25-3x) still multiplies on top - document in VALIDATION.
- BINARY DA VALUES ARE PRESCRIBED, NOT READ: FireRate 8, bAutomatic, reserve 270/360/450/540, HeadshotMultiplier 2.0, MeleeDamage 30/15/60, Brute 75 -> 60 are authoring targets for DAs that could not be dumped; the authoring pass must set and dump them (UnrealEditor-Cmd Python) with D:/AFS_Comparisons evidence; if the Ballista DA carries a different FireRate every TTK row in seconds shifts proportionally (shot counts do not).
- AMMO ECONOMY RESTS ON THREE RULES: reserve growing with PaP tier, refill-to-full pricing computed from the owned tier (AHoverArmoryStation override, not the vendor MagazineSize x 2 path), and GUARANTEED Max Ammo from horde clears, boss deaths and the first/third Brute per heavy round; the simulation shows PaP III slipping to R27-28 without the Brute rule and never arriving with the winner's +400 R26-30 band; random 3% drops were not counted, so real play is slightly richer.
- SPEED ROLL AND CROWDING: the per-spawn tier needs the per-tick MaxWalkSpeed rewrite replaced by a per-instance value; the readable mixed-line horde still depends on the crowding slice (attack slots/tokens, 120-180 cm acceptance radius, zig-zag deviation, cadence jitter) landing in the same pass, otherwise BT MoveTo(TargetEnemy, 5 cm) still converges every zombie on one point.
- FLINCH WHILE ATTACKING contradicts the hardcoded 0.8 s / !bIsAttacking rule in ZE_ZombieCharacter.cpp (already patched file): one more plugin edit, or the flinch must be driven from the AHoverCyberZombie override via PlayAction on the locomotion bridge.
- STONEGOLEM WARDEN is a fantasy asset with its own skeleton (ABP/montage wrappers, 320 cm capsule, nav agent 70, Underpass ceiling clearance) and may fail the owner's post-apocalyptic bar; it is Stage 2 and the spine ships with Alpha Brute on every boss round, so no Stage 1 number depends on it.
- RIOT ARMORED (Stage 2) needs ZESP armor SKMs attached to the retargeted Standard skeleton (socket compatibility unverified) and the pre-Super damage interception in AHoverCyberZombie::TakeDamage; if it is cut, remove its 15/20% share from the income model (income drops ~1,500 by R30, still positive).
- NEW CODE SURFACE (Stage 1, estimated 600-900 lines in HoverFlight plus thin AZE_WallBuyActor / AZE_InteractableBase subclasses): plates/mitigation in AHoverPilot::TakeDamage, regen, downed/self-revive/game-over (vendor GameOver binds only AZE_PlayerCharacter), perks-as-items, doors, PaP DA swap with clip copy (SavedMagazines keyed by InstanceId), tier-scaled ammo pricing, kill-point hook, speed roll, stall guard / catch-up / straggler re-queue, Brute/boss guaranteed drops, power switch; none of it should touch the 14 patched plugin files except the flinch rule and the Stage 2 enum values.
- INVINCIBILITY is persisted ON in GameUserSettings; the survival mode must force it off at InitGame and hide the pause-menu toggle, or the entire damage/armor/downed design is inert.
- PERFORMANCE: 24 concurrent zombies, 70-Kid hordes at 0.35 s and a 300 cm boss on the procedural-building city are unbenchmarked (NullRHI-only NYC pass, VSM warnings, 12-14 GB VRAM contention); if frame time forces MaxConcurrent 16, keep the count table and lower spawn-interval floors instead (round length grows ~30%); if hordes collapse, cap K(r) at 48.
- VEHICLES: not spawning the bike and parking the truck removes the infinite safe zone in Stage 1; the hoverboard 'no points, damage not blocked' rule needs the SetCanBeDamaged gate bypassed for the board only; the Stage 2 exfil truck set piece must not reintroduce a stall.
- BO7 PROXIES remain proxies (critic.json): the 150-HP player, 30/50/75 hit bands, 2,000 x 1.14 drop threshold, vest III 10,000, special/boss 250/500 and the health-curve shape are Cold War/BO6/BO3-lineage or single-source values; the spine tunes to the AFS feel targets first and shape-checks against them, so if BO7 publishes tables only the CustomWaves rows and prices change.
- ROUND LENGTH: R30 = 105 standards at 13 body shots with 24 concurrent and a 0.5 s floor is a 4-5 minute round; past R30 rounds are endurance by design (health +800/+1,000 per round, 25,000 cap at R54) and should be presented as such in CONTROLS/README.

### 1.7 Spine errata after owner decisions

These errata apply the 2026-10-29 owner decisions and lead decisions D1-D15, superseding only what is listed. `roster_mapping_v2.md` governs assets and clips; these errata govern combat tuning. When the DAs are authored, these v2 draft fields are overwritten:

- `DA_StoneGolem`
  - MaxHealth 1,500; MeleeDamage 90 -> 75.
  - Walk/Run 160/300 -> 240/420. MaximumRunSpeed 380 must be raised so it does not clamp 420.
  - StompRadius 500 -> 600; slam cooldown 4 s; gold -> 500 points.
  - Role `Boss`, SpecialKind `StoneGolem`.
- `DA_GiantKid`
  - MaxHealth 1,200; MeleeDamage 60 -> 90.
  - Run 420 -> 300, enraged 650. MaximumRunSpeed 520 must be raised so it does not clamp 650.
  - StompRadius 450 -> 500; cooldown 2.4 -> 2.5 s; gold -> 500 points.
  - Role `Boss`, SpecialKind `GiantKid`.

**E1. Warden becomes StoneGolem, Stage 1, unarmed.**
- "Warden" is deleted as a name everywhere, including "new EHoverZombieRole::Warden".
  - `EHoverZombieRole` gains only `Boss` and `Riot` (Stage 2).
  - SpecialKind is {None, StoneGolem, GiantKid}.
- The v2 build replaces the spine asset line (Parts SKMs, hammer, `MI_StoneGolem_Body_Skin2`, `SC_Monster_Roar`, nav agent 70):
  - `DA_StoneGolem` in `Variants/Golem` with single-mesh `SK_Golem_LODs`, `MI_Golem_Body/Armor` and `SC_Entity_Roar`.
  - Empty sockets; `BP_StoneGolem` is not spawned.
- Stats: 15x H(r) via the frozen round scale, Walk 240 / Jog 420, 500 points.
  - The `attack5` slam uses the x2.5 band (75/125/188) in 600 cm, with a 2.1 s knockdown and a 4 s cooldown.
  - At R13 the slam does 30 x 2.5 x 1.667 = 125.
- Withdrawn from Stage 1:
  - The 700 charge and its launch. `turn180` is only the intro.
  - The armor-break phases and the x3 weak point. The spine's R13 "33 weak point (4.1 s)" and R27 "47 weak point (5.9 s)" are void; the full-HP fight takes roughly twice those times.
- Tuning risk: base HP may drop to 1,000 (10x) after playtest (not decided).

**E2. Alpha Brute is not a boss.** It becomes an optional Stage 2 heavy-round elite.
- Role `Brute`, 1,200 HP, bands 90/150/225.
- Speed 300, enraged 650 below 50%.
- 250 points.
- Off by default.

**E3. Giant Kid is boss B.**
- `DA_GiantKid` in `Variants/Kid`: `SK_Kid_LODs` at Height 320.
- 12x H(r): R19 is 10,920 HP (39 PaP II headshots), R27 is 31,200 HP (56 PaP III).
- It inherits the whole Alpha boss row:
  - Bands 90/150/225.
  - Speed 300, enraged 650 below 50%.
  - x2.0 stomp in 500 cm, with a 2.1 s knockdown and a 2.5 s cooldown.
  - 500 points and a guaranteed Max Ammo.
- Second life: when HP first crosses 30%, a 2.8 s invulnerable Rise (`Reanimate`) plays with no HP added.
  - Only on that crossing is the lethal hit clamped to 1 HP.
  - Insta-Kill needs two kills; OnKilledBy and points fire on the final death only.

**E4. Boss schedule.**
- R13: StoneGolem (6,900 HP) with 39 standards.
- R19: Giant Kid with 56 standards.
- R27: both (Kid at 50% golem HP), 89 standards, 1,000 points, two Max Ammos.
- Then 33 + 6k: R33 golem + 2 Brutes, R39 two Giant Kids. Text 02 must say "R13/R19/R27, then 33 + 6k".
- The spine priority "horde beats heavy beats boss" stands. R45, R75 and R105 are horde rounds, so those bosses shift to R46, R76 and R106. Texts 02 and 03 must drop their boss-beats-horde reading.
- Open (owner): the shifted rounds are even, which also makes them heavy rounds.
- The R33 Brutes are additive. This clarifies "Brutes replace standards" for boss rounds only.
- Boss data (pointers, `BossRounds[]`, `FindBossRound`) lives on `UHoverNYCEncounterSettings`.
- Brute cadence: BruteDebutWave 8, BruteFirstWave 12, BruteInterval 2.

**E5. Kid crawler and horde.**
- The crawler is `DA_NYC_Kid`, a duplicate of `Variants/Kid` with `BS_Kid_Crawl`. Cyber `DA_Kid` is untouched.
- Banner text: "KID SWARM - stay moving".
- `SwarmInterval` 5 is `DA_NYCEncounters` data. The class default stays 10.
- `SwarmCount` ClampMax 24 -> 80 is a code edit in `HoverCyberVariants.h`.

**E6. Speed roll.** Spine slip "R9 last walkers": R8 is the last round with walkers (11%). R9 has 0% walkers and 2.8% sprinters.

**E7. One frozen health scale.**
- `OnZombieSpawned` sets `AHoverCyberZombie::HealthScale = GetRoundHealthScale(Round)`; `AHoverNYCZombie` and the AI tick read it.
- `FrozenHealthScale` and `HealthScaleFactor` are deleted.
- `DA_NYCWaves.ZombieClass` is `BP_NYCZombie` (parent `AHoverNYCZombie : AHoverCyberZombie`).

**E8. Stragglers (spine deviation).**
- Stage 1 only relocates stragglers to the director's pick, using text 02's thresholds; text 03 references 02. Nothing is destroyed or patched.
- Re-queue and the `NotifyZombieRemoved` patch move to Stage 2 as optional work.

**E9. Owner meshes.** All eleven are allowed.
- In Stage 1, Horror, BogZombie, Mythical, Plant and Pirate are Standard skins only, with the same stats, round-robin with Standard01-04.
- Their special roles move to Stage 2: armored 150 points, specials 250. The 110/130/120/300 values are removed.

**E10. Stage 2 list.**
- Removed: Warden.
- Added: the Alpha elite, the Lakeside roles and re-queue.
- Everything else in the list stays.

## 2. Mode framework, level entry, third-person camera, navigation

This section defines the container that every other slice plugs into: the new game mode, the new owned map, the fifth menu entry, the camera, health and invincibility policy Vexa adopts in that map, and the navigation that the spawn, crowding and zone slices assume exists. The `NYC - Exploration` entry does not change. `L_NYC_Explore`, `AHoverExplorationGameMode` and `VerifyNYCExploration.py` stay untouched.

### 1. Class map

| Item | Decision | Why (code evidence) |
|---|---|---|
| Game mode class | `AHoverNYCSurvivalGameMode : AHoverCyberCityGameMode`, in new files `Source/HoverFlight/HoverNYCSurvival.h/.cpp` | Vexa only gets `UHoverCombatBridge` (inventory, quickbar, ammo, gold, survival) when the auth mode casts to `AHoverCyberCityGameMode` (`HoverPilot.cpp:283-287`). Wave `DamageMultiplier` is applied in `AHoverPilot::TakeDamage` under the same cast (`:1652-1659`), and the Zombie Settings page is gated the same way (`HoverGraphicsMenu.cpp:83-84`). Deriving inherits all three. |
| Launch option | native `game=/Script/HoverFlight.HoverNYCSurvivalGameMode`, with no Blueprint child | `AHoverCyberCityGameMode::InitGame` already hard-loads the pawn, PC, HUD and DAs (`HoverCyberCity.cpp:78-101`). `BP_CyberWaves_C` (`HoverTestController.cpp:117-118`) is historical. |
| Map | `/Game/HoverPrototype/Maps/L_NYC_Survival`: a copy of `L_NYC_Explore` with the same streaming sublevels. Its WorldSettings set DefaultGameMode = `AHoverNYCSurvivalGameMode` | The game-over restart reopens the map with no `?game=` option. That applies both to the vendor `RestartWaveSession` (`ZE_ZombieWaveGameMode.cpp:207-~260`, `OpenLevel` near :245) and to the subclass path (section 5). Opening the map in the editor and pressing Play also passes no option. The WorldSettings override must therefore name the survival mode. Binary evidence that `L_NYC_Explore` carries its own override: one `HoverExplorationGameMode` string in `Content/HoverPrototype/Maps/L_NYC_Explore.umap`, found by a string scan that also shows 3 `LevelStreamingAlwaysLoaded` and 104 `LevelStreamingDynamic` names. `VerifyNYCExploration.py:52` confirms it at runtime. |
| Data | `/Game/HoverPrototype/NYC/DA_NYCWaves` (`UZE_WaveGameModeSettings`), `DA_NYCEncounters` (`UHoverCyberEncounterSettings`), `DA_NYC_Standard01-04`, `DA_NYC_Kid`, `DA_NYC_Brute`, `DA_NYC_AlphaBrute` | Same per-map swap as Lakeside in `InitGame` (`HoverCyberCity.cpp:89-96`). The numbers are the spine's. This section only fixes paths and the loader. |
| Menu index | `4`, label `NYC - Survival` | Index 3 stays `NYC - Exploration` (owner rule). |
| Player | Vexa (`BP_Vexa_CLS_Parkour_C`, from `AHoverCyberCityGameMode::InitGame:80-81`): third person, mortal, MaxHealth 150, no bike, truck parked and unmountable | Spine `player` block. |

**Required changes to existing AFS classes.** The section 2 header must not rely on anything that is not listed here.

1. **`HoverCyberCity.h:67-81`.** Move these members from `private:` to `protected:`: `Encounters`, `ActiveSpawnCount`, `SpawnLastUsed`, `LastSpawnPosition`, `ReachableSpawns`, `NextReachabilityCheck` and `CanReachPlayer`.
2. **Split the per-point test in `AHoverCyberCityGameMode::Tick` (`HoverCyberCity.cpp:283-325`) into two virtual hooks:**
   - `virtual bool IsSpawnCandidate(AZE_ZombieSpawnPoint *Point) const { return true; }` is the zone pool hook (zone slice).
   - `virtual bool IsSpawnPointSafe(AZE_ZombieSpawnPoint *Point, APawn *Player, const FVector &Eye, const FRotator &View, bool bRelaxVisibility)` holds today's band, reachability, cone/visibility and 300 cm pawn tests unchanged. When `bRelaxVisibility` is true it skips only the cone/visibility test.
   - The base passes `ShouldRelaxVisibilityGate()`, which returns false by default. The NYC subclass returns true after 4 s with `ActiveSpawnCount == 0` (stall guard, spawn slice).

   A plain `Tick` override cannot do this, because it only runs before or after the monolithic loop.
3. **Add `IHoverTestLevelPolicy` (section 3)** to `AHoverGameMode` (`HoverPilot.h:309-321`) and `AHoverCyberCityGameMode` (`HoverCyberCity.h:35`).
4. **`UHoverCombatBridge::BeginPlay` (`HoverCombatBridge.cpp:269-281`)** applies only `StartingWeapons` and `StartingAmmo` × `Gear.AmmoQuantity`. That is why `AmmoQuantity 270` in `DA_NYCWaves` reaches Vexa without the vendor `ApplyStartingEquipment`, which only runs for `AZE_PlayerCharacter` (`ZE_ZombieWaveGameMode.cpp:49-57`). `GrenadeCount` and `GrenadeQuickbarSlot` are ignored today, so add `AddItemDefinition(<frag definition>, Gear.GrenadeCount, Id)` plus `AssignInstanceToQuickbar(Id, Gear.GrenadeQuickbarSlot)`. This is a container obligation; the equipment slice supplies the frag definition.

**Vendor constraint the spawn and zone slices inherit.** `AZE_ZombieWaveGameMode::GetRandomSpawnPoint` is private (`ZE_ZombieWaveGameMode.h:151`). It picks uniformly among `bIsEnabled` spawn points and falls back to any `APlayerStart` when none is enabled (`.cpp:393-420`). Zone pools and LRU choice can therefore only work by toggling `bIsEnabled` inside the adapter loop, as `HoverCyberCity.cpp:309, 323-324` does today. `AZE_ZombieSpawnPoint::SpawnTags` is read nowhere in the adapter, so the zone test belongs in `IsSpawnCandidate`. The guard that skips `Super::Tick` when `ActiveSpawnCount == 0` (`:328-329`) must stay; otherwise `AFS_SurvivalStart` becomes a spawn point.

### 2. `AHoverNYCSurvivalGameMode` skeleton

```cpp
// HoverNYCSurvival.h
#pragma once
#include "HoverCyberCity.h"
#include "HoverNYCSurvival.generated.h"

UCLASS()
class HOVERFLIGHT_API AHoverNYCSurvivalGameMode : public AHoverCyberCityGameMode // policy interface comes from the base
{
    GENERATED_BODY()

  public:
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual AActor *ChoosePlayerStart_Implementation(AController *Player) override; // AFS_SurvivalStart first
    virtual void RestartPlayer(AController *NewPlayer) override;                   // third person + mortal + 150 HP
    // IHoverTestLevelPolicy (declared in the base)
    virtual bool SpawnsTestBike() const override { return false; }
    virtual bool SpawnsTestTruck() const override { return true; }
    virtual bool AllowsTruckMount() const override { return false; } // Stage 1: parked set dressing
    virtual bool ForcesThirdPerson() const override { return true; }
    virtual bool ForcesMortal() const override { return true; }
    virtual float GetPlayerMaxHealth() const override { return 150.f; }
    UFUNCTION(BlueprintPure) bool IsSurvivalMode() const { return true; } // Python assertions only

  protected:
    // Hooks filled by the rounds/spawn/zone slices (protected in the base, HoverCyberCity.h:61-65)
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                  const TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual float GetEffectiveSpawnRate() const override;
    virtual bool IsSpawnCandidate(AZE_ZombieSpawnPoint *Point) const override; // zone pool
    virtual bool ShouldRelaxVisibilityGate() const override;                  // 4 s stall guard
    void BeginGameOver();                                                       // section 5, downed slice

  private:
    static constexpr const TCHAR *WavesPath = TEXT("/Game/HoverPrototype/NYC/DA_NYCWaves.DA_NYCWaves");
    static constexpr const TCHAR *EncountersPath = TEXT("/Game/HoverPrototype/NYC/DA_NYCEncounters.DA_NYCEncounters");
};
```

```cpp
// HoverNYCSurvival.cpp (framework part only)
#include "HoverNYCSurvival.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"

void AHoverNYCSurvivalGameMode::InitGame(const FString &MapName, const FString &Options, FString &Error)
{
    Super::InitGame(MapName, Options, Error); // vendor InitGame, then Cyber pawn/PC/HUD/DAs
    if (auto *Waves = LoadObject<UZE_WaveGameModeSettings>(nullptr, WavesPath))
        WaveSettings = Waves;
    if (auto *Enc = LoadObject<UHoverCyberEncounterSettings>(nullptr, EncountersPath))
        Encounters = Enc; // protected after change 1
    if (WaveSettings)
        WaveSettings->WaveHUDClass = UHoverCyberWaveHUD::StaticClass(); // in memory only, never saved
    UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_SURVIVAL waves=%s encounters=%s"), *GetNameSafe(WaveSettings),
           *GetNameSafe(Encounters));
}

AActor *AHoverNYCSurvivalGameMode::ChoosePlayerStart_Implementation(AController *Player)
{
    for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
        if (It->ActorHasTag(TEXT("AFS_SurvivalStart")))
            return *It;
    return Super::ChoosePlayerStart_Implementation(Player); // vendor SetDressing start is the fallback
}
```

**Load order.** `Super::InitGame` runs `AZE_ZombieWaveGameMode::InitGame` and then the Cyber loader (`HoverCyberCity.cpp:85-88`). The vendor reads `WaveSettings` only in `PostLogin`, `StartPlay` and `Tick` (`ZE_ZombieWaveGameMode.cpp:35-47`, `:466+`), so replacing the DAs in `InitGame` means no Cyber data reaches `StartWave`.

**WaveHUDClass.** `AHoverCyberCityGameMode::InitGame:97-98` already writes `DA_CyberWaves->WaveHUDClass` in memory on every launch, which is harmless existing behaviour. NYC follows the same in-memory-only rule. Vendor `PostLogin` creates the HUD from `WaveHUDClass`, and the adapter `Tick` re-creates it lazily (`:273-279`). This assignment is therefore the single place where the HUD slice substitutes its banner-capable subclass (`KID SWARM`, `HEAVY TANK`, boss).

**Branch selection.** `bLakeside` stays false because the map name contains neither `L_Showcase` nor `L_Lakeside` (`:89`), and the subclass overrides the Cyber branch.

### 3. Test-level policy interface (bike gate generalisation)

`AHoverTestController::PlayerTick` spawns the bike when `!GetAuthGameMode<AHoverGameMode>() || Mode->bSpawnBike` (`HoverTestController.cpp:572-576`). No ZES-derived mode is an `AHoverGameMode`, so the bike would always appear in NYC Survival. The interface below replaces that cast:

```cpp
// HoverTestLevelPolicy.h
#pragma once
#include "UObject/Interface.h"
#include "HoverTestLevelPolicy.generated.h"

UINTERFACE(MinimalAPI)
class UHoverTestLevelPolicy : public UInterface
{
    GENERATED_BODY()
};

class IHoverTestLevelPolicy
{
    GENERATED_BODY()

  public:
    virtual bool SpawnsTestBike() const { return true; }
    virtual bool SpawnsTestTruck() const { return true; }
    virtual bool AllowsTruckMount() const { return true; }
    virtual bool ForcesThirdPerson() const { return false; }
    virtual bool ForcesMortal() const { return false; }
    virtual float GetPlayerMaxHealth() const { return 100.f; }
    static const IHoverTestLevelPolicy *Get(const UWorld *World); // Cast<IHoverTestLevelPolicy>(AuthGameMode)
};
```

| Class | Implements | `SpawnsTestBike` | Notes |
|---|---|---|---|
| `AHoverGameMode` (`HoverPilot.h:309-321`) | `public AGameModeBase, public IHoverTestLevelPolicy` | override returns `bSpawnBike` | PostApo unchanged |
| `AHoverExplorationGameMode` | inherited | `bSpawnBike=false` (`HoverPilot.cpp:1961-1965`) | unchanged |
| `AHoverCyberCityGameMode` (`HoverCyberCity.h:35`) | `public AZE_ZombieWaveGameMode, public IHoverTestLevelPolicy` | default `true` | Cyber/Lakeside keep all three rides |
| `AHoverNYCSurvivalGameMode` | inherited only; no second base (a duplicate base would make the cast ambiguous) | `false` | owner rule |

**Bike and truck spawning.** `PlayerTick` becomes `const auto *Policy = IHoverTestLevelPolicy::Get(GetWorld()); UClass *Class = (!Policy || Policy->SpawnsTestBike()) ? LoadClass<APawn>(...BP_Hoverbike_C) : nullptr;`, and the truck spawn block is wrapped in `(!Policy || Policy->SpawnsTestTruck())`.

**Truck entry.** On foot, `AHoverPilot::HoverMount` (`HoverPilot.cpp:422-430`) calls `AHoverTestController::TryEnterBike` (`HoverTestController.cpp:326-333`), which computes `bTruck` from `IsNearTruck` (`:312-317`). Truck entry is gated inside `IsNearTruck()` itself: it returns false when `Policy && !Policy->AllowsTruckMount()`. That one check also stops `TryEnterBike` and the on-foot prompt. The X-hold exit at `:622-640` only runs while already driving and stays untouched. The truck remains set dressing at `AFS_TruckStart` (`(200, 5900, 120.54)` yaw +90, `Docs/NYC_EXPLORATION_20261028.txt:26-27`).

**Truck prompt.** `AHoverPilot::GetPrompt` (`HoverPilot.cpp:1803-1805`) gets a branch before the `IsNearTruck` test: when the policy forbids mounting and the pilot is within the same 420 cm / 220 cm proximity, it prints `TRUCK - locked (exfil in Stage 2)`. The in-vehicle bar at `:1838-1846` is unreachable in Stage 1.

### 4. Third-person default and OTS camera

Vexa already has a complete review camera:

- `ReviewArm` (spring arm, `TargetArmLength 430`, `SocketOffset (0,40,15)`, pawn control rotation) and `ReviewCamera` (`HoverPilot.cpp:103-110`).
- It is toggled by the private `bReview` (`HoverPilot.h:274`) through `HoverView()` (`HoverPilot.cpp:516-520`) and `SetView()` (`:522-538`), bound to F5 / Gamepad_Special_Right (`:735-737`). It is read through `IsThirdPersonView()` (`HoverPilot.h:136-139`).
- FOV is 90 hip / 72 aim (`:1071`). The damage trace starts from the active camera (`:1312-1314`), and `FireShot` keeps the world gun raised for 3 s after a shot (`:1392`).

The survival mode only changes the default view and the arm numbers.

| Change | Where | Value |
|---|---|---|
| Default view | `AHoverPilot::BeginPlay` after the preference read (`:137`): `if (Policy && Policy->ForcesThirdPerson()) bReview = true;` before `SetView()` | member access; no accessor |
| F5 lock | `HoverView()`: early return with `StatusMessage = "Survival is third person"` when forced | keeps `IsThirdPersonView()` consumers (`HoverCombatBridge.cpp:156-169` TP/FP mesh switch) on one path |
| Arm length | new `UHoverPilotAssets` fields on `DA_HoverPilot` (`HoverPilot.h:32-89`): `SurvivalArmLength 300`, `SurvivalAimArmLength 210`, `SurvivalSocketOffset (0, 58, 42)`, `SurvivalAimFOV 68`, `SurvivalHipFOV 88` | applied in `UpdateAppearance` next to the FOV interpolation (`:1069-1071`): `ReviewArm->TargetArmLength = FInterpTo(..., bAiming ? AimArm : Arm, DT, 10)` |
| Camera lag | `bEnableCameraLag = true; CameraLagSpeed = 14; CameraLagMaxDistance = 60` in `BeginPlay` when forced | readable sprint-and-turn at 900 cm/s; `bDoCollisionTest` stays true (probe 12) because zombie capsules ignore `ECC_Camera` (`HoverCyberCity.cpp:484-485`) and so does the mesh (`:490`). The mesh still blocks `ECC_Visibility` (`:487`) for the hitscan. |
| Pitch limits | unchanged `-75..75` (`HoverPilot.cpp:295-296`) | |
| Posture | unchanged `UpdateCameraPosture` (`:546-562`) | |

**Strafe rule.** `UsesAimFacing()` (`HoverPilot.h:163-166`) is `bMeleeEquipped || bAiming || GunRaisedTime > 0 || !bReview`. It drives `BodyYaw` (`HoverPilot.cpp:902`) and the CLS rotation mode (`HoverLocomotionBridge.cpp:171-178`). In third person Vexa faces her direction of travel with the gun lowered, and strafes while aiming, swinging, or for 3 s after a shot. That rule is kept.

**Addition: reload counts as aiming.** Add `|| (Combat && Combat->IsReloading())`. The new `UHoverCombatBridge::IsReloading()` returns `GetWeapon() && GetWeapon()->IsReloading()`, using the vendor `AZE_WeaponBase::IsReloading()` (`ZE_WeaponBase.h:113`) that `AHoverCyberRifle` inherits. `GunRaisedTime` is untouched. If the inline body cannot see the complete bridge type, move `UsesAimFacing` into `HoverPilot.cpp`.

**Unchanged.** `bUseControllerRotationYaw = bParkourMovement && !bMounted` (`:1750`). The OTS offset interacts with the breech-to-muzzle trace (`:1312-1320`), which the combat-feel slice validates.

### 5. Invincibility, health and game over

| Fact | Evidence |
|---|---|
| `bInvincible` defaults true, read from `[AFS.Graphics] Invincible` at BeginPlay | `HoverPilot.h:171`, `HoverPilot.cpp:137` |
| The menu saves the preference and calls `SetInvincible` on every pilot | `HoverGraphicsSettings.cpp:181-187` |
| `TakeDamage` returns 0 while invincible | `HoverPilot.cpp:1649` |
| Health lives in `SandboxHealth` (100, `HoverPilot.h:173`) and `Combat->Survival`; `GetHealth` prefers Survival, `TakeDamage` writes both | `HoverPilot.cpp:1629-1632, 1663-1665` |
| `UZE_SurvivalComponent::MaxHealth` defaults to 100; the bridge never reads `ZE_PlayerSettings.MaxHP=150` | `ZE_SurvivalComponent.h:93`, `HoverCombatBridge.cpp:246-258`, `DefaultGame.ini:15` |
| HUD prints `HP %.0f/100` | `HoverPilot.cpp:1823-1826` |

Decisions:

1. **Mortal lock; the saved preference is untouched.** `BeginPlay` sets `bMortalLocked = Policy && Policy->ForcesMortal(); if (bMortalLocked) bInvincible = false;`, and `SetInvincible(bool E)` becomes `bInvincible = E && !bMortalLocked;`.
   - The menu still saves the preference, and PostApo, Cyber and Lakeside honour it as before.
   - `UHoverGraphicsMenu::Adjust` row 3 (`HoverGraphicsMenu.cpp:125-126`) becomes a no-op, and `Refresh` (`:206-209`) prints `Invincible:  Off (survival)`. Both test `IHoverTestLevelPolicy::Get(GetWorld())->ForcesMortal()`, so the pilot and the menu use the same mechanism.
2. **The survival component is authoritative, at 150 HP.** After `Survival->RegisterComponent()` (`HoverCombatBridge.cpp:254-255`) the bridge runs `const float Max = Policy ? Policy->GetPlayerMaxHealth() : 100.f; Survival->SetMaxHealth(Max); Survival->SetHealth(Max); Pilot->SandboxHealth = Max;`.
   - A new `AHoverPilot::GetMaxHealth()` returns the component's value, and the HUD prints `HP %.0f/%.0f`.
   - `HoverReset` (`:566-608`) uses `GetMaxHealth()` instead of the literal 100.
   - When `ForcesMortal()` is true, the downed slice bypasses the reset/`DefeatedUntil` path (`HoverPilot.cpp:624-632, 1668-1669`).
   - Juggernog later calls `Survival->SetMaxHealth(250)`.
3. **Game-over entry point.** The vendor `HandleGameOver`, `RestartWaveSession` and `OnPlayerHealthChanged` are declared `private:` (`ZE_ZombieWaveGameMode.h:118`, `:163-171`; `protected:` only resumes at `:181`). The subclass cannot call or bind them from C++. The decision is to re-implement game over in `BeginGameOver()`:
   - call `StopAllZombies()` (protected, `:189`);
   - run the spine's 2 s slow-motion death cam, with the subclass owning global time dilation (the vendor sets 0.001, which would freeze the death cam);
   - create `WaveSettings->DeathWidgetClass` for the local PC;
   - `UGameplayStatics::OpenLevel` with `RestartLevelName`.

   If a later pass needs the vendor's exact restart behaviour, the reflective call `if (UFunction *F = FindFunction(TEXT("RestartWaveSession"))) ProcessEvent(F, nullptr);` is allowed. Both functions are `UFUNCTION(BlueprintCallable)`, and AFS already uses `ProcessEvent` (`HoverTestController.cpp:530, 679`). No 15th plugin patch is made.
4. **Vehicles.**
   - `AHoverCyberCityGameMode::Tick` keeps `SetCanBeDamaged(Cast<AHoverPilot>(Player) != nullptr)` (`HoverCyberCity.cpp:271`). A mounted Vexa is still the `AHoverPilot` pawn, so the board already does not block damage, and no gate bypass is needed.
   - The spine's "board earns no points" rule is assigned to the economy slice: the kill-reward override in `AHoverCyberZombie::TakeDamage` awards 0 when the instigating pilot `IsMounted()`.
   - In Stage 1 no vehicle is ever the possessed pawn.

### 6. Owned map `L_NYC_Survival` and PlayerStart

Editor/Python steps (NullRHI, `-ExecutePythonScript`, evidence written to `D:/AFS_Comparisons/NYCSurvival_<date>/Before+After`):

| Step | Action |
|---|---|
| 1 | Try `EditorAssetLibrary.duplicate_asset('/Game/HoverPrototype/Maps/L_NYC_Explore', '/Game/HoverPrototype/Maps/L_NYC_Survival')`. World duplication through the asset library is unverified on UE 5.8 here, so the fallback is `LevelEditorSubsystem.load_level(L_NYC_Explore)` then `EditorLoadingAndSavingUtils.save_map(world, '/Game/HoverPrototype/Maps/L_NYC_Survival')`. VALIDATION records which call produced the asset. Then verify that the streaming sublevels (CityMeshes, SetDressing, Lighting_Main, Lighting_Main_Directional; `Docs/NYC_EXPLORATION_20261028.txt:23-25`) are still AlwaysLoaded. Vendor sublevels are never saved. |
| 2 | WorldSettings: `DefaultGameMode = AHoverNYCSurvivalGameMode`; `world_settings.set_editor_property('navigation_system_config', unreal.NavigationSystemModuleConfig(navigation_system_class=unreal.HoverNYCNavigationSystem))` (`AWorldSettings::NavigationSystemConfig`, `WorldSettings.h:544`). The Lakeside binding is not visible in Source, Config or Scripts and presumably lives in the L_Showcase asset, so the NYC binding is authored explicitly and asserted. |
| 3 | Add `APlayerStart` at `(271, 5241, 162)` yaw `-90`, tag `AFS_SurvivalStart`, label `AFS Survival Start`. This is the vendor start's spot; the vendor actor stays untouched. Vexa's `StartLocation`/`StartRotation` and the parked board come from it (`HoverPilot.cpp:138-139, 229`). |
| 4 | Keep `AFS_TruckStart`; do not add `AFS_BikeStart`. |
| 5 | Add `NavMeshBoundsVolume` + `RecastNavMesh` (section 7), 25 `AZE_ZombieSpawnPoint` tagged `AFS_NYCSpawn` with `SpawnTags = {ZoneName}`, and door/zone actors (zone slice). |
| 6 | `PAL_AFS_Runtime` (`/Game/HoverPrototype/Cook`, scanned by `DefaultGame.ini:40`): add roots for `L_NYC_Survival`, `DA_NYCWaves`, `DA_NYCEncounters` and the seven `DA_NYC_*` definitions; dump the label before and after. |

`DA_NYCWaves` framework fields:

- **Zombie class and types.** `ZombieClass = /Game/HoverPrototype/ZombieEngine/BP_CyberZombie.BP_CyberZombie_C` (AHoverCyberZombie-derived) is mandatory. `SpawnZombie` aborts with "ZombieClass is NOT set" otherwise (`ZE_ZombieWaveGameMode.cpp:502-508, 684-688`). `DA_CyberWaves` carries it, and a fresh DA would not. Also set `DefaultZombieTypes` to the four `DA_NYC_Standard` definitions, plus per-row `ZombieTypes` where the rounds slice needs them.
- **Timing and scaling.** `FirstWaveDelay 5`, `TimeBetweenWaves 10`, `SpawnInterval 2.0`, `MaxConcurrentZombies 24`, `Auto*ScalePerWave 1.0`, `bUseCustomWaves true` with 30 rows, `MaxWaves 0`, `bDirectChaseMode true`.
- **Restart.** `RespawnPolicy RestartLevel`, `RestartLevelName /Game/HoverPrototype/Maps/L_NYC_Survival` (`ZE_WaveGameModeSettings.h:281-289`), `DeathWidgetClass WBP_ZE_DeathRespawn`, which `BeginGameOver` creates.
- **Starting kit.** `StartingEquipment`: Ballista in slot 1, `DA_AMMO_M16` with `AmmoQuantity 270`, `StartingGold 500`, `GrenadeCount 2` (effective only after change 4).
- **Authoring helper.** `UHoverAuthoring::ConfigureCityStartingGear` rejects paths outside `/Game/HoverPrototype/ZombieEngine/` (`HoverAuthoring.cpp:79`) and hard-codes `AmmoQuantity 120` and `GrenadeCount 0` (`:94, :96`). It gains `AmmoQuantity` and `GrenadeCount` parameters and also accepts `/Game/HoverPrototype/NYC/`.

### 7. Navigation

`L_NYC_Explore` is a classic persistent level with streaming sublevels, not a World Partition map, and it has no navmesh. Spawn gating needs complete paths (`CanReachPlayer`, `HoverCyberCity.cpp:155-182`), and crowd following needs a navmesh.

| Topic | Decision |
|---|---|
| Authoring API | Widen `UHoverAuthoring::AddCityNavigation` (`HoverAuthoring.cpp:199-200`) to also accept `Name.StartsWith("L_NYC_Survival")`. `L_NYC_Explore` stays refused. |
| Volume | One `NavMeshBoundsVolume` tagged `AFS_CityNavigation`, centre `(270, 5100, 160)`, size `(2400, 5400, 1200)`: x -400..1100 zone placeholders, y 2400-7800, z -440..760. |
| Runtime generation | `DynamicModifiersOnly` (new `bDynamicModifiersOnly` parameter, instead of the `Dynamic` forced at `:240-243`). Tiles are baked into the map. Each door carries a `UNavModifierComponent` (`NavArea_Null`), so opening a door rebuilds only its tiles. |
| Agent | `UHoverNYCNavigationSystem : UNavigationSystemV1` (pattern `HoverCyberCity.cpp:40-52`). `PostInitProperties` writes one supported agent sized for the tallest Stage 1 unit: `Agent.AgentRadius = 48.f; Agent.AgentHeight = 300.f; Agent.AgentStepHeight = 50.f;` (`FNavDataConfig` has `AgentStepHeight`, not `AgentMaxStepHeight`). Brute (250) and Alpha Brute (300 / r 48) never get a path the 190 cm agent would allow but their capsule cannot pass. The street is open-air, so the low-clearance tiles lost are negligible. Standards and Kids query the same agent; `AHoverCyberZombie::BeginPlay` syncs capsules to it (`:453-454`). The Stage 1 StoneGolem boss (r 70, h 320) adds a second agent. VALIDATION records the tile count against a 40 x 190 comparison bake. |
| Tile budget | `TileSizeUU 1000`, `bFixedTilePoolSize true`, `TilePoolSize 1024` (direct properties). Cell size and step height are set through the resolution params, because `CellSize`/`AgentMaxStepHeight` are deprecated config-only: `Nav->SetCellSize(ENavigationDataResolution::Default, 19.f)` and `SetAgentMaxStepHeight(ENavigationDataResolution::Default, 50.f)` (Python: `nav_mesh_resolution_params`). The volume is 3 x 6 tiles per layer, far below the pool (packaged tile mismatch: `Docs/ASSET_AUDIT_REPAIRS_20261025.txt:125-127`). |
| Acceptance | `Scripts/ReviewNYCSpawns.py` (copy of `ReviewCyberSpawns.py`, tag `AFS_NYCSpawn`, `find_complete_city_path`, one PNG per spawner). Pass criteria: (a) each of the 25 spawners has a complete path to `AFS_SurvivalStart` and to its zone centre; (b) from every zone centre, at least 3 spawners in that zone or one hop away lie 14-100 m away with complete paths, which is the spine's deadlock rule. A failing spawner is disabled, never relied on. |

Risk: generation needs the procedural-building collision (`MaximumLoopIterationCount=10000000`, `DefaultEngine.ini:78-80`). The first bake runs under NullRHI and its tile count and time go into VALIDATION.

### 8. Level menu index 4

| File:line | Current | Change |
|---|---|---|
| `HoverTestController.cpp:106-109` | 4-entry map table | `Level == 4 ? TEXT("/Game/HoverPrototype/Maps/L_NYC_Survival")` first |
| `HoverTestController.cpp:115-119` | `?game=` chain | `Level == 4 ? TEXT("game=/Script/HoverFlight.HoverNYCSurvivalGameMode") :` before `Level == 3` |
| `HoverTestController.cpp:79-83`, `HoverGraphicsMenu.cpp:69-73` | substring index detection | `L_NYC_Survival -> 4` before `L_NYC_Explore -> 3` |
| `HoverGraphicsMenu.cpp:123` | `+ 4) % 4` | `+ 5) % 5` (row count at `:97` stays 4) |
| `HoverGraphicsMenu.cpp:169-174` | four labels | `PendingLevel == 4 ? TEXT("NYC - Survival")` |
| `HoverGraphicsMenu.cpp:53-55` | "NYC: explore ... without zombies..." | "NYC - Exploration has no zombies. NYC - Survival is the third-person wave mode with no bike. Other levels keep their vehicles and encounters. Lakeside uses its own five creatures." |
| `HoverGraphicsMenu.cpp:132-134` | "available in Cyber City and Lakeside." | "...Cyber City, Lakeside and NYC - Survival." |
| `HoverGraphicsMenu.cpp:125-126, 206-209` | Invincible row | no-op / `Off (survival)` via `ForcesMortal()` |

**Wrap-around in `VerifyNYCTravel.py`.**

- Today stage 0 taps Left once (`:81`, 0 -> 3). Stage 1 matches `'NYC' in w.get_name()` (`:83`) and taps Right once (`:85`, 3 -> 0).
- With five entries those taps land on 4 and then 0 -> 4. The `'NYC'` match also accepts `L_NYC_Survival`, and stage 2 would time out waiting for PostApo.
- New sequence: PostApo -> Left x2 -> `L_NYC_Explore` (sample `nyc_from_menu`) -> Right x1 -> `L_NYC_Survival` (sample `nyc_survival_from_menu`: mode, no bike, navmesh present) -> Right x1 -> PostApo (`postapo_return`).
- `change()` gains a tap count, and the stages match `L_NYC_Explore` / `L_NYC_Survival` instead of `NYC`.

### 9. Owner amendment checklist (exact lines)

| File | Line(s) | Text |
|---|---|---|
| `AGENTS.md` | after L28 | "NYC - Survival (menu index 4, HoverPrototype/Maps/L_NYC_Survival, AHoverNYCSurvivalGameMode derived from AHoverCyberCityGameMode) is the only NYC entry that may spawn zombies and waves. It never spawns the bike; the Doomsday truck is parked and unmountable. The index-3 NYC - Exploration rules above are unchanged. Both maps stream the same vendor sublevels; author only in the owned maps." |
| `README.md` | L167-173 | L167-170 list gains `NYC - Survival (/Game/HoverPrototype/Maps/L_NYC_Survival)`; L171 becomes "NYC - Exploration uses Vexa, the hoverboard and Doomsday truck, with no zombies or wave systems. NYC - Survival is a third-person wave mode (rounds, points, Pack-a-Punch, perks, doors) with no bike and a parked truck; past round 30 rounds are endurance by design."; L172 becomes "The other levels retain their existing vehicles and encounters." |
| `Docs/CONTROLS.txt` | L5 | "...in Cyber City, Lakeside or NYC - Survival." |
| `Docs/CONTROLS.txt` | L10-11 | "Test level: Post-apocalypse, Cyber City, Chinese Lakeside Town, NYC - Exploration or NYC - Survival. NYC - Exploration has no zombies; NYC - Survival has waves, no bike and a parked truck." |
| `Docs/CONTROLS.txt` | L13-14 | append "NYC - Survival forces Invincible Off and third person; F5 is locked there." |
| `Docs/CONTROLS.txt` | L63 | append "(not in NYC - Survival)" |
| `Docs/CONTROLS.txt` | new block after L82 | NYC SURVIVAL ECONOMY: points 90/115/105/250/500, plates 50, perks 2,500 + 500n, PaP 5,000/15,000/30,000, doors 750-2,000, ammo 250/750/1,500/3,000, reserve 270 |
| `.gitignore` | after L31 | `!Docs/NYC_SURVIVAL_<date>.txt` |
| `Scripts/VerifyNYCTravel.py` | L81, L83, L85 | Left x2; stage match `L_NYC_Explore`; Right x1 to the new survival stage, then Right x1 to PostApo |
| `Docs/NYC_EXPLORATION_20261028.txt` | L5 | "left twice on that row selects NYC - Exploration; right from there selects NYC - Survival" |

### 10. Verification scripts

| Script | Asserts |
|---|---|
| `Scripts/VerifyNYCExploration.py` | Unchanged (spine). Rerun as the regression: mode, zero enemies, no bike, the truck mountable there. |
| `Scripts/VerifyNYCSurvival.py` (new, `load_level` with no `?game=`, `VerifyCyberWaves.py` sampling pattern) | **Mode and nav:** mode `HoverNYCSurvivalGameMode` (proves the WorldSettings override for direct Play); `w.get_navigation_system().get_class().get_name() == 'HoverNYCNavigationSystem'`. **Player:** pawn `BP_Vexa_CLS_Parkour_C`; `is_third_person_view()` true at t=5 and after an F5 tap; `is_invincible()` false while GameUserSettings says On; survival max health 150. **Vehicles:** `get_test_bike() is None`; truck present, and a hold-X next to it leaves Vexa possessed. **Map and waves:** exactly one `RecastNavMesh`; at least 25 actors tagged `AFS_NYCSpawn`; `wave_settings.zombie_class` set; wave 1 `get_zombies_remaining() == 6`, wave 2 `== 8`; zombie `max_health` 100 then 125; `custom_waves` rows 1-30 match the spine tables and the 1.0/1.667 bands. **Exploration static check:** an editor `load_level` of `L_NYC_Explore` shows no `RecastNavMesh`, no spawn points and no zombies. Output: `D:/AFS_Comparisons/NYCSurvival_<date>/runtime.json`. |
| `Scripts/AssessNYCSurvival.py` | scores that JSON (pattern `AssessCyberWaves.py`) |
| `Scripts/ReviewNYCSpawns.py` | section 7 acceptance criteria |
| `Scripts/VerifyNYCTravel.py` | amended stages (section 8) |
| `Scripts/VerifyGraphics.py`, `Scripts/VerifyCyberWaves.py` | Rerun after the `SetInvincible` change. No script references invincibility today, so `VerifyCyberWaves.py` gains one assertion that `is_invincible()` equals the saved preference in Cyber City. |

All runs are offscreen and never concurrent. Build with `Scripts/Build.ps1` and run clang-format. `Docs/NYC_SURVIVAL_<date>.txt` uses the plain-text style with a VALIDATION section recording:

- the map-creation call used;
- the nav bake tile count and time for 48 x 300 versus 40 x 190;
- the spawner acceptance table;
- the 30-row DA dump with `ZombieClass`;
- the exploration regression.

### 11. Obligations to other slices

| Slice | Depends on this container | Owns |
|---|---|---|
| Rounds | `ConfigureWave`/`SelectZombieData`/`GetEffectiveSpawnRate` overrides; `DA_NYCWaves` rows | 30 CustomWaves rows, R31+ formula, per-actor HealthScale freeze (edit `AHoverCyberZombieAI::Tick`, `HoverCyberCity.cpp:385-394`, not this subclass) |
| Spawn | change 1 (protected state), change 2 (`IsSpawnPointSafe`, `ShouldRelaxVisibilityGate`), `Super::Tick` skip guard | stall guard, catch-up, boss interval, straggler re-queue |
| Zones | `IsSpawnCandidate`, `SpawnTags`, door `UNavModifierComponent` | zone graph, doors, `bIsEnabled` integration inside the adapter loop |
| Downed | `ForcesMortal`, `GetMaxHealth`, `BeginGameOver` skeleton | reset-path bypass, self-revive, time dilation, death widget contents |
| Economy | the board rule (section 5), change 4 grenades, `AmmoQuantity` parameter | kill reward hook, tier-scaled ammo pricing |
| HUD | in-memory `WaveHUDClass` assignment in `InitGame` | banner widget subclass |
| Combat feel | OTS arm numbers (section 4) | trace origin vs OTS offset (`HoverPilot.cpp:1312-1320`), TP/FP mesh switch (`HoverCombatBridge.cpp:156-169`) |

## 3. Rounds, scaling and the spawn director

This section turns the numeric spine into code paths that exist today. Three verified facts drive it. (1) The vendor `AZE_ZombieWaveGameMode` exposes `virtual ConfigureWave / SelectZombieData / GetEffectiveSpawnRate / StartWave` (local patch, `ZE_ZombieWaveGameMode.h:51,184-187,197`), but `SpawnZombie`, `GetRandomSpawnPoint` and `GetEffectiveMaxConcurrentZombies` are non-virtual, and every counter (`ZombiesToSpawn`, `ZombiesAlive`, `LastSpawnTime`) is private with no getter for `ZombiesAlive` (`.h:118-129,146,151,198`). (2) `GetZombieCountForWave` and `GetDifficultyMultipliers` are plain members of `UZE_WaveGameModeSettings` (`ZE_WaveGameModeSettings.h:305-309`). Vendor `StartWave` calls them (`ZE_ZombieWaveGameMode.cpp:467-471`), and so do the adapter AI tick (`HoverCyberCity.cpp:372-374`) and `AHoverPilot::TakeDamage` (`HoverPilot.cpp:1653-1660`). (3) The only post-spawn hook AFS owns is `AHoverCyberZombie::BeginPlay -> Mode->RecordSpawn(...)` (`HoverCyberCity.cpp:497-498`). It runs inside `FinishSpawningActor` (`ZE_ZombieWaveGameMode.cpp:539`), before the vendor's 0.1 s `ApplyDifficultyToZombie` timer (`:570-610`).

Where the logic goes:
- Round logic goes in `ConfigureWave` / `SelectZombieData`.
- Per-actor scaling goes in the spawn hook.
- Spawn placement and pacing go in a director. The director drives the vendor loop through `bIsEnabled` and the return value of `GetEffectiveSpawnRate`.

### 06.1 Class map

| Item | File (Source/HoverFlight unless noted) | Role |
|---|---|---|
| `AHoverNYCSurvivalGameMode : AHoverCyberCityGameMode` | `HoverNYCSurvival.h/.cpp` (new) | Reassigns `WaveSettings`/`Encounters` after `Super::InitGame`, owns the schedule, the R31+ formula, `UHoverSpawnDirector`, `TickInterval 0.1` |
| `UHoverNYCEncounterSettings : UHoverCyberEncounterSettings` | `HoverCyberVariants.h` | Schedule table and tier constants (06.4) |
| `UHoverSpawnDirector : UObject` | `HoverSpawnDirector.h/.cpp` (new) | Spawner pools, gates, credit pacing, packs, jitter, stragglers, vehicle projection (06.6) |
| `AHoverCyberCityGameMode` edits | `HoverCyberCity.h:44,55,67-80`, `.cpp:155-182,263-330` | `RecordSpawn` becomes `virtual OnZombieSpawned(AHoverCyberZombie&)`; `GetEncounterLabel` becomes `virtual` (`.h:55`, otherwise the HUD call at `.cpp:694-695` stays bound to the base class); `Encounters`, `CanReachPlayer` move to `protected`; new overload `CanReachPoint(AActor*, const FVector&, const FVector& Extent)` that `CanReachPlayer` forwards to, with its own cache keyed by (spawn, target cell); new protected `bExternalSpawnDirector`: when true, Tick skips exactly `.cpp:283-324` (Chosen/BestScore through `Chosen->bIsEnabled = true`) and the `ActiveSpawnCount > 0` guard at `:328`, and still runs `:265-279` (`SetCanBeDamaged`, WaveHUD) |
| `AHoverCyberZombie` edits | `HoverCyberCity.h:97-122` | Per-instance `HealthScale` (0 = use DA lookup), `SpeedTier`, `RelocationCount`, `SpawnTime`, `SpawnerUsed` |
| `AHoverNYCZombie : AHoverCyberZombie` (`BP_NYCZombie`) | roster section (03) | `DA_NYCWaves.ZombieClass`; slots, phases and the Giant Kid second life. It READS `HealthScale` written by `OnZombieSpawned` and keeps no health scale of its own (no `FrozenHealthScale`, no `HealthScaleFactor`) |
| `AHoverCyberZombieAI::Tick` edits | `HoverCyberCity.cpp:343-351,371-394` | Retarget gated on `!bTargetDropped`; frozen per-actor scale (06.3, 06.6) |
| Vendor patch (Stage 2 optional, declared deviation) | `Plugins/.../Survival/ZE_ZombieWaveGameMode.h/.cpp` (already among the 14 patched files) | `protected: void NotifyZombieRemoved(AZE_ZombieCharacter*, bool bRequeue)`; needed only for Stage 2 destroy-and-requeue (06.6). Stage 1 does not apply it |
| `EHoverZombieRole` | `HoverCyberVariants.h:7-13` | add `Boss` (StoneGolem, Giant Kid) and `Riot` (Stage 2) only; no other value is added. `DA_StoneGolem` and `DA_GiantKid` set `Role = Boss` plus a `SpecialKind` enum {None, StoneGolem, GiantKid}. The optional Alpha Brute elite (Stage 2) keeps `Brute`. `Boss` must pass the Brute gates at `HoverCyberCity.cpp:463` (yaw 220) and `:509` (`StompImpact`) |

**Stage 1 straggler rule: relocation only, no plugin patch.** Stragglers are teleported to the director's `Pick()`, never destroyed, with no limit on `RelocationCount` (06.6). They always count toward `ZombiesAlive`, so the round-end test (`ZE_ZombieWaveGameMode.cpp:629-634`) needs no change and Stage 1 touches no plugin file for stragglers. The spine's straggler re-queue therefore moves to Stage 2; the errata records this deviation.

**Stage 2 optional deviation the owner must accept.** The spine limits plugin edits to the flinch rule and the Stage 2 enum values. Destroy-and-requeue needs a third edit, `NotifyZombieRemoved`, because the counters are private and `OnDeath` fires only from `Die()` (`ZE_ZombieCharacter.cpp:272-277`). Without it, a removed zombie keeps `ZombiesAlive` above 0 and the round never ends (`:629-634`). If adopted, the patch gets a new row in the native-patch matrix of `Docs/NYC_SURVIVAL_<date>.txt`, in the same format as `Docs/ZOMBIE_SPECIALS_20261024.txt:94-99`, with Before/After SHA256 receipts under `D:/AFS_Comparisons/NYCSurvival_<date>`. It is never committed (AGENTS.md:4-5). If the owner refuses, Stage 1 relocation simply stays the rule.

`HoverFlight.Build.cs` already links `AIModule` and `NavigationSystem`, so no module change is needed.

### 06.2 Round state machine

The vendor state machine is kept as is: `WaitingToStart --FirstWaveDelay--> WaveInProgress --last death--> WaveCompleted --intermission--> WaveInProgress` (`ZE_ZombieWaveGameMode.cpp:436-459,612-658`). `SetWaveState` only broadcasts `OnWaveStateChanged` (`.cpp:660-663`) and nothing pauses the player, so with a 10 s intermission the rounds run continuously, as in BO7.

| Timer / event | Source | NYC value |
|---|---|---|
| First round delay | `DA_NYCWaves.FirstWaveDelay` (`ZE_WaveGameModeSettings.h:153`) | 5 s |
| Intermission | `CustomWaves[r].CustomIntermissionTime` (`.h:134`, `.cpp:101-114`); `TimeBetweenWaves` for R31+ | 10 s |
| Round end | `CheckWaveStatus` needs `ZombiesToSpawn<=0 && ZombiesAlive<=0` (`.cpp:629-634`) | unchanged; bosses must die |
| Round start stinger | `OnRoundStateChanged` bound to `OnWaveStateChanged` in `BeginPlay`; on `WaveInProgress` plays `RoundStartSound` (heavy: `SC_Zombie_Roar`); the banner comes from `virtual FString GetEncounterLabel() const override` (HEAVY TANK / KID SWARM - stay moving / BOSS: STONE GOLEM / BOSS: GIANT KID / NYC SURVIVAL - ROUND n) | 1.2 s |
| Max concurrent | `DA_NYCWaves.MaxConcurrentZombies` (`.h:172`), non-virtual getter (`.h:198`) | 24 (a boss counts as 1) |
| Nuke / boss pacing | director `SuppressUntil`, `IsBossAlive()` | +3 s; spawn rate x0.5 |

`InitGame`: call `Super::InitGame`, then reassign the protected `WaveSettings` (`ZE_ZombieWaveGameMode.h:94`) to `/Game/HoverPrototype/NYC/DA_NYCWaves` and `Encounters` to `/Game/HoverPrototype/NYC/DA_NYCEncounters`. This is needed because the parent hard-loads DA_CyberWaves/DA_CyberEncounters (`HoverCyberCity.cpp:85-88`). Then set `WaveSettings->WaveHUDClass = UHoverCyberWaveHUD::StaticClass()` again, keeping the Cyber wave HUD, and set `bExternalSpawnDirector = true`.

The constructor sets `PrimaryActorTick.TickInterval = 0.1f`, because the inherited 0.5 s (`ZE_ZombieWaveGameMode.cpp:30`) would quantise the 0.35 s horde floor up to 0.5 s.

### 06.3 Health, count, damage and speed delivery

The DA getters cannot be overridden, so the curve is delivered in two parts.

1. **R1-30 are data.** `DA_NYCWaves.bUseCustomWaves=true` with 30 `FZE_WaveConfig` rows (`ZE_WaveGameModeSettings.h:94-135`).
2. **R31+ and every substitution are code.** `ConfigureWave` (called at `ZE_ZombieWaveGameMode.cpp:494`, after the DA lookup) rewrites `Count`. `GetRoundHealthScale/GetRoundDamageScale(Round)` return the matching row, otherwise the formula. The AI tick and `AHoverPilot::TakeDamage` are redirected to these getters when the mode is `AHoverNYCSurvivalGameMode`.

**Verified collapse at R31.** The vendor matches `CustomWaves` by `WaveNumber` and falls back to `Auto^(W-1)` for any wave without a row (`ZE_WaveGameModeSettings.cpp:7-28,59-62`). With every Auto value at 1.0, R31 would drop to 100 HP and a count of 24, so the formula getter is mandatory.

| `DA_NYCWaves` field | Value |
|---|---|
| `FirstWaveDelay / TimeBetweenWaves / SpawnInterval / MaxConcurrentZombies` | 5 / 10 / 2.0 / 24 |
| `BaseZombieCount`, `Auto{Health,Damage,Speed,Count}ScalePerWave` | 24, all 1.0 |
| `bUseCustomWaves`, `CustomWaves[30]` | row r: `WaveNumber=r`, `BaseZombieCount=N(r)`, `HealthMultiplier=H(r)/100`, `DamageMultiplier` 1.0 (R1-10) / 1.667 (R11-30), `SpeedMultiplier=1.0`, `CustomIntermissionTime=10`, `ZombieTypes` empty |
| `DefaultZombieTypes` | `DA_NYC_Standard01..04`: deliberate duplicates of `/Game/HoverPrototype/ZombieEngine/Variants/Standard01-04` under `/Game/HoverPrototype/NYC/Zombies/`, so NYC tuning (MeleeDamage 30, Brute 75 -> 60) does not change Cyber City. In Stage 1 the Lakeside meshes Horror, BogZombie, Mythical, Plant and Pirate are added as further Standard SKINS only: same Standard stats and points, round-robin with Standard01-04 (assets in the roster section). `NYC->Standards` lists the same entries. Their special roles (armored Pirate/BogZombie, Feral Horror, Spore Plant, Elite Mythical) are Stage 2, paid on the spine ladder only (armored 150, specials 250) |
| `ZombieClass` | `BP_NYCZombie` (native parent `AHoverNYCZombie : AHoverCyberZombie`, roster section), `bDirectChaseMode=true` |
| `StartingEquipment` | section 04 |

```cpp
// HoverNYCSurvival.h (excerpt)
UCLASS() class HOVERFLIGHT_API AHoverNYCSurvivalGameMode : public AHoverCyberCityGameMode {
    GENERATED_BODY()
  public:
    AHoverNYCSurvivalGameMode();                              // TickInterval 0.1
    virtual void InitGame(const FString &Map, const FString &Options, FString &Error) override;
    virtual void Tick(float DT) override;                     // Director->Update(DT); Super::Tick(DT) ALWAYS
    virtual void StartWave() override;                        // Super::StartWave(); then Director->BeginRound(...)
    virtual void OnZombieSpawned(AHoverCyberZombie &Z) override;
    virtual FString GetEncounterLabel() const override;
    UFUNCTION(BlueprintPure) float GetRoundHealthScale(int32 Round) const;
    UFUNCTION(BlueprintPure) float GetRoundDamageScale(int32 Round) const;   // 1 / 1.667 / 2.5
    UFUNCTION(BlueprintPure) int32 GetStandardQuota(int32 Round) const;
    UFUNCTION(BlueprintPure) EHoverRoundKind GetRoundKind(int32 Round) const;
    UFUNCTION(BlueprintPure) int32 GetRoundQuota() const { return RoundQuota; }
    UFUNCTION(BlueprintPure) bool IsBossAlive() const { return Boss.IsValid(); }
  protected:
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 Idx, const TArray<UZE_ZombieDataAsset *> &T) override;
    virtual float GetEffectiveSpawnRate() const override { return Director->GetSpawnRate(); }
    UFUNCTION() void OnRoundStateChanged(int32 Wave, EZE_WaveState State, float Timer);
  private:
    struct FRequeued { TObjectPtr<UZE_ZombieDataAsset> Type; float Fraction; };
    UPROPERTY() TObjectPtr<UHoverSpawnDirector> Director;
    UPROPERTY() TObjectPtr<UHoverNYCEncounterSettings> NYC;
    int32 RoundQuota = 0, SpawnedThisRound = 0;
    TMap<int32, TObjectPtr<UZE_ZombieDataAsset>> ScheduledSpecials;           // ordinal -> Brute/Kid (AlphaBrute, Riot: Stage 2)
    TArray<TObjectPtr<UHoverCyberZombieDefinition>> PendingBosses;            // same element type as FHoverBossRound
    TArray<FRequeued> Requeued;                                               // Stage 2 re-queue only; always empty in Stage 1
    TOptional<float> PendingFraction;                                         // Stage 2: applied in OnZombieSpawned
    TWeakObjectPtr<AHoverCyberZombie> Boss;
};

static const FZE_WaveConfig *FindRow(const UZE_WaveGameModeSettings *WS, int32 R) {   // vendor match rule
    if (WS && WS->bUseCustomWaves)
        for (int32 i = 0; i < WS->CustomWaves.Num(); ++i)
            if ((WS->CustomWaves[i].WaveNumber > 0 ? WS->CustomWaves[i].WaveNumber : i + 1) == R) return &WS->CustomWaves[i];
    return nullptr;
}
float AHoverNYCSurvivalGameMode::GetRoundHealthScale(int32 R) const {
    if (const auto *Row = FindRow(GetWaveSettings(), R)) return Row->HealthMultiplier;
    int32 H = 3500;                                            // H(30)
    for (int32 r = 31; r <= R; ++r) H += r <= 40 ? 800 : 1000;
    return FMath::Min(H, 25000) / 100.f;                       // cap binds at R54
}
int32 AHoverNYCSurvivalGameMode::GetStandardQuota(int32 R) const {
    static const int32 Solo[] = {6, 8, 13, 18, 24, 27, 28, 28, 29};
    return R <= 9 ? Solo[R - 1] : 24 + (9 * R * R) / 100;     // integer: R30 = 105
}
```

**One frozen health scale.** `AHoverNYCSurvivalGameMode::OnZombieSpawned` writes `AHoverCyberZombie::HealthScale = GetRoundHealthScale(Round)` once per actor (06.5). That field is the only health-scale mechanism: `AHoverNYCZombie` and the AI tick read it, and no second frozen copy or per-DA factor exists.

`AHoverCyberZombieAI::Tick` (`HoverCyberCity.cpp:371-394`): if `Zombie->HealthScale > 0`, use it in place of the `GetDifficultyMultipliers` result. Cyber City and Lakeside leave it at 0, so their behaviour is unchanged. If `Zombie->SpeedTier > 0`, `MaxWalkSpeed = TargetEnemy ? SpeedTier : Stats.WalkSpeed`, with no `SpeedScale`. The `MaximumRunSpeed` clamp and `Tuning.Speed/Health` still apply.

Ordering: the vendor 0.1 s timer multiplies MaxHealth once by the row value, and the next adapter tick (0.5 s or less) rewrites it to `Stats.MaxHealth x HealthScale x Tuning.Health` with the health fraction preserved (`:385-394`). VALIDATION therefore samples health at t+1 s and asserts that this rewrite ran for frozen-scale actors.

### 06.4 Round kinds and the special schedule

`UHoverNYCEncounterSettings` extends `UHoverCyberEncounterSettings` (`HoverCyberVariants.h:44-76`) and is the single home of the boss plumbing and the special schedule; the roster section references it and adds no second schedule. The NYC mode never reads `IsBruteWave`, `IsSwarmWave` or `SwarmCount`: its `ConfigureWave`, `SelectZombieData`, `GetEffectiveSpawnRate` and `GetEncounterLabel` all replace the parent's. The shared clamp at `:55` (BruteFirstWave ClampMin 11) stays unchanged. Two horde edits are kept apart:
- `SwarmInterval 5` is a data value in `DA_NYCEncounters`; the class default `SwarmInterval = 10` (`:62`) stays.
- `SwarmCount` `ClampMax` 24 -> 80 (`:63`) is a code edit to the UPROPERTY meta in `HoverCyberVariants.h`, per the spine's horde rule. It changes no authored value.

Cyber City and Lakeside are unaffected.

Both bosses are Stage 1, with `Role = Boss` and `SpecialKind` StoneGolem / GiantKid. The StoneGolem ships as is: one mesh, unarmed (no hammer or shield, `weapon_l/r` sockets empty), so Stage 1 has no charge, no armor-break phases and no weak-point windows. The Giant Kid is the Kid mesh at Height 320. Boss health uses the frozen scale only: StoneGolem MaxHealth 1,500 (15x H(r)), Giant Kid 1,200 (12x), no extra factor, so R13 is 6,900, R19 10,920 and R27 39,000 + 31,200 = 70,200. Melee bands, speeds, slam/stomp, the Giant Kid's 30% Rise, the asset paths, clips and retarget routes all come from the roster section (boss build spec, Giant Kid spec) and are not restated here.

| Field (`DA_NYCEncounters`) | Value | Use |
|---|---|---|
| `StoneGolem`, `GiantKid` | `/Game/HoverPrototype/ZombieEngine/Variants/Golem/DA_StoneGolem`, `/Game/HoverPrototype/ZombieEngine/Variants/Kid/DA_GiantKid` (Stage 1, both `Role = Boss`) | boss rosters; `IsBossDefinition(D)` = `D == StoneGolem \|\| D == GiantKid` |
| `AlphaBrute`, `bAlphaBruteElite` | `DA_NYC_AlphaBrute` (Stage 2 heavy-round elite, Role `Brute`: MaxHealth 1,200, bands 90/150/225, speed 300 / enraged 650 below 50% HP, 250 points), false | optional heavy-round elite, never a boss |
| `Riot` | Stage 2 | armored roster |
| `Kid` (inherited) | `DA_NYC_Kid`: NYC duplicate of `Variants/Kid` with `BS_Kid_Crawl`, AttackRange 130, AttackSphereRadius 45 (roster crawler spec). Cyber City `DA_Kid` is untouched, so the Cyber swarm keeps walking | horde crawler and the R21+ bleed-in |
| `SwarmFirstWave / SwarmInterval` (base) | 5 / 5 (data value; class default stays 10) | horde rounds 5, 10, 15, ... (Kid crawler only) |
| `HordeBase / HordePerRound / HordePackSize / HordeIntervalBase / HordeIntervalFloor / HordeCountCap` | 10 / 2 / 4 / 0.65 / 0.35 / 0 (0 = off; 48 is the performance fallback) | `K(r)=10+2r` |
| `SpawnIntervalBase / SpawnIntervalFloor / SpawnIntervalDecay` | 2.0 / 0.5 / 0.95 | `SI(r)`; the floors are the performance-fallback knobs |
| `BruteDebutWave`, `BruteFirstWave / BruteInterval` (base) | 8, 12 / 2 | heavy = even, >= 12, not horde |
| `BruteCountCap / BruteCountDivisor / BrutePlacement[]` | 4 / 6 / {0.25,0.5,0.75,0.9} | `B(r)=min(4,1+(r-8)/6)` |
| `KidBleedFromRound` | 21 | `N(r)/10` Kids |
| `BossRounds[]` `FHoverBossRound{Round, TArray<TObjectPtr<UHoverCyberZombieDefinition>> Bosses, SecondEntersAtFraction}` | {13,[StoneGolem]}, {19,[GiantKid]}, {27,[StoneGolem,GiantKid],0.5}, all Stage 1; R33+ generated by `FindBossRound` | additive; listed order = entry order |
| `BossTriggerFraction` | 0.40 | release point |
| `RiotShareEarly / RiotShareLate / RiotFromRound / RiotLateRound / RiotMaxAlive` | 0.15 / 0.20 / 9 / 17 / 6 | Stage 2 |
| `WalkerSpeed / RunnerSpeed / SprinterSpeed / RollPerRound / RollWindow` | 180 / 400 / 600 / 4 / 35 | 06.5 |
| `ForcedSprintersAtEnd / StragglerPromoteSeconds / StragglerPromoteRange` | 3 / 10 / 2500 | 06.5 |
| `RoundStartSound / HeavyRoundSound / BossRoar / EmergeMontage` | ZombieV2 clip, `SC_Zombie_Roar`, `SC_Entity_Roar`, none (animation section) | stingers |

**Boss schedule:** R13/R19/R27, then 33 + 6k (33, 39, 45, 51, ...). Collision priority is the spine's: horde beats heavy beats boss. The nominal boss rounds are all odd, so they never meet heavy rounds (even). They do meet horde rounds whenever 33 + 6k is a multiple of 5 (R45, R75, R105: every 30 rounds from R45, since 45 = 9 x 5). There the horde keeps the round and the boss round shifts one round later (R46, R76, R106); the hordes stay on every multiple of 5. No collision exists in R1-30.

`GetRoundKind` tests, in order: `Horde`, then `FindBossRound` (which already resolves the shift), then `BruteDebut` (R8) / `Heavy`, then `Normal`. This matches the spine order on every nominal round. The only even boss rounds are the shifted ones, which would also qualify as heavy; the lead decision makes them boss rounds, so they get no heavy Brutes (a boss round is never a heavy round). This is an owner check (06.8).

**R31+ boss composition is generated** in `FindBossRound`: every 6 rounds from R33, in a three-step cycle (R33 StoneGolem + 2 Brutes, R39 2 Giant Kids, R45 StoneGolem + Giant Kid played at R46, then R51 repeats R33). The cycle step is taken from the nominal round, so a shift never changes the composition. Multi-boss rows reuse the R27 rule: the second boss enters at 50% of the first one's health. Extra Brutes ride in the `Bosses` array as boss adds released with the boss, so a boss round is still never a heavy round. These R33 Brutes are ADDITIVE to the quota; this clarifies the spine's 'Brutes replace standards inside N(r)' rule for boss rounds only (errata).

```cpp
bool UHoverNYCEncounterSettings::IsHordeRound(int32 R) const {
    return R >= SwarmFirstWave && (R - SwarmFirstWave) % SwarmInterval == 0;     // 5, 10, 15, ...
}
const FHoverBossRound *UHoverNYCEncounterSettings::FindBossRound(int32 R) const {
    for (const FHoverBossRound &B : BossRounds) if (B.Round == R) return &B;   // R13/R19/R27 authored rows
    auto OnCycle = [](int32 N) { return N >= 33 && (N - 33) % 6 == 0; };       // 33 + 6k
    int32 Nominal = INDEX_NONE;
    if (OnCycle(R) && !IsHordeRound(R)) Nominal = R;                           // R33, R39, R51, R57, ...
    else if (OnCycle(R - 1) && IsHordeRound(R - 1)) Nominal = R - 1;           // horde wins: R45 -> R46, R75 -> R76
    if (Nominal == INDEX_NONE) return nullptr;
    Generated = FHoverBossRound{R, {}, 0.f};                                   // UPROPERTY(Transient) mutable scratch row
    switch (((Nominal - 33) / 6) % 3) {
    case 0:  Generated.Bosses = {StoneGolem, Brute, Brute}; break;            // R33, R51, ...: adds come with the golem
    case 1:  Generated.Bosses = {GiantKid, GiantKid}; Generated.SecondEntersAtFraction = .5f; break;   // R39, R57, ...
    default: Generated.Bosses = {StoneGolem, GiantKid}; Generated.SecondEntersAtFraction = .5f;        // nominal R45 (played R46), R63, ...
    }
    return &Generated;
}
```

**Alpha Brute elite (optional, Stage 2).** When `bAlphaBruteElite` is set and `AlphaBrute` is valid, the last scheduled Brute of a `Heavy` round spawns `AlphaBrute` instead. It keeps Role `Brute` and counts as a Brute for quota, placement, forced-sprint exclusion and the `StompImpact` gate. It never sets `Boss`, never plays the boss intro and never appears in `BossRounds`. Its stats are the table row above (1,200 HP, bands 90/150/225, 300 / enraged 650 below 50%, 250 points on the special ladder); the enrage hookup belongs to section 05.

```cpp
void AHoverNYCSurvivalGameMode::ConfigureWave(int32 R, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) {
    AZE_ZombieWaveGameMode::ConfigureWave(R, Count, Types);    // skip the Cyber parent (swarm clamp, IsBruteWave)
    ScheduledSpecials.Reset(); PendingBosses.Reset(); Requeued.Reset(); SpawnedThisRound = 0;
    const EHoverRoundKind Kind = GetRoundKind(R);
    Types.Reset();
    if (Kind == EHoverRoundKind::Horde) {
        Count = NYC->HordeBase + NYC->HordePerRound * R;
        if (NYC->HordeCountCap > 0) Count = FMath::Min(Count, NYC->HordeCountCap);
        Count = FMath::Clamp(FMath::RoundToInt(Count * Tuning.Count), 1, 200);
        Types.Add(NYC->Kid);
    } else {
        Count = FMath::Clamp(FMath::RoundToInt(GetStandardQuota(R) * Tuning.Count), 1, 200);   // scale FIRST
        for (auto &D : NYC->Standards) if (D) Types.Add(D);
        const int32 Brutes = Kind == EHoverRoundKind::BruteDebut ? 1
                           : Kind == EHoverRoundKind::Heavy ? FMath::Min(NYC->BruteCountCap, 1 + (R - 8) / NYC->BruteCountDivisor) : 0;
        int32 LastBruteSlot = INDEX_NONE;
        for (int32 i = 0; i < Brutes; ++i)
            ScheduledSpecials.Add(LastBruteSlot = FMath::RoundToInt(Count * (Brutes == 1 ? .5f : NYC->BrutePlacement[i])), NYC->Brute);
        if (Kind == EHoverRoundKind::Heavy && NYC->bAlphaBruteElite && NYC->AlphaBrute && LastBruteSlot != INDEX_NONE)
            ScheduledSpecials.Add(LastBruteSlot, NYC->AlphaBrute);       // TMap::Add replaces: Stage 2 optional elite, not a boss
        if (R >= NYC->KidBleedFromRound)
            for (int32 k = 1, Kids = Count / 10; k <= Kids; ++k) {       // integer: R21 6 ... R29 9
                int32 Slot = k * 10 - 5;
                while (ScheduledSpecials.Contains(Slot)) ++Slot;         // never drop a Kid on a Brute slot
                ScheduledSpecials.Add(Slot, NYC->Kid);                   // DA_NYC_Kid
            }
        if (const FHoverBossRound *B = NYC->FindBossRound(R)) {
            for (int32 i = B->Bosses.Num() - 1; i >= 0; --i)              // reversed: Pop() returns Bosses[0] first
                if (B->Bosses[i]) PendingBosses.Add(B->Bosses[i]);       // R27: golem before Giant Kid
            Count += PendingBosses.Num();                                 // ADDITIVE, never scaled
        }
    }
    RoundQuota = Count;
}
UZE_ZombieDataAsset *AHoverNYCSurvivalGameMode::SelectZombieData(int32, int32, const TArray<UZE_ZombieDataAsset *> &T) {
    // Vendor index (killed + alive, .cpp:536) shifts with kills; use our own ordinal.
    if (Director->IsBossSpawnArmed() && PendingBosses.Num()) return PendingBosses.Pop();
    if (Requeued.Num()) { const FRequeued Q = Requeued.Pop(); PendingFraction = Q.Fraction; return Q.Type; }   // Stage 2
    if (auto *S = ScheduledSpecials.Find(SpawnedThisRound)) return *S;
    return T.Num() ? T[SpawnedThisRound % T.Num()] : nullptr;
}
void AHoverNYCSurvivalGameMode::StartWave() {
    Super::StartWave();                      // vendor builds quota + schedule via ConfigureWave (.cpp:494)
    Director->BeginRound(GetCurrentWave(), GetRoundKind(GetCurrentWave()), RoundQuota);
}
```

Kid bleed-in per round (the same crawler `DA_NYC_Kid`): R21 6, R22 6, R23 7, R24 7, R25 horde, R26 8, R27 8, R28 9, R29 9.

**Boss release.** When `GetZombiesKilledThisWave() >= BossTriggerFraction x RoundQuota`, the director arms the boss spawn. While armed, `GetSpawnRate()` returns 0, ignoring credit, and `Pick` forces the farthest reachable candidate. The vendor `ZombiesAlive < MaxConcurrent` gate (`.cpp:448-451`) still holds, so the boss appears on the next free slot: 0-2 s at a saturated cap. Because `SelectZombieData` pops the boss first, no standard zombie can take that slot.

The director stays armed while the next pending entry is an add (R33 Brutes come out back to back after the golem). It disarms when the next pending entry is a second boss on a row with `SecondEntersAtFraction > 0`. That boss re-arms when the first boss's health drops below the fraction (R27: the Giant Kid at 50% golem HP), or at once if the first boss dies before reaching it. The roar, camera shake and banner fire from `OnZombieSpawned` when the boss actually exists, not when it is armed. The Giant Kid's spawn-in is its `AM_GiantKid_Rise` (roster Giant Kid spec), played through the same `PlayBossIntro`. Its second life is not a respawn: the first time its HP crosses 30%, a 2.8 s invulnerable Rise plays with no HP added (same pool, roster section). `Boss` stays valid through it, so the second-entry fraction does not re-fire and boss pacing stays on; points and `OnKilledBy` come from the final death only. Drops and kill cams belong to sections 05/08.

### 06.5 Speed tier at spawn

```cpp
void AHoverNYCSurvivalGameMode::OnZombieSpawned(AHoverCyberZombie &Z) {
    const int32 R = GetCurrentWave();
    const bool bReplacement = PendingFraction.IsSet();
    Z.HealthScale = GetRoundHealthScale(R);                    // THE frozen health scale; AHoverNYCZombie + AI tick read it
    Z.SpawnTime = GetWorld()->GetTimeSeconds();
    if (Z.GetRole() == EHoverZombieRole::Standard) {
        const int32 Speed = R == 1 ? 0 : NYC->RollPerRound * R;  // R1: K in [0,35] -> 100% walkers
        const int32 K = FMath::RandRange(Speed, Speed + NYC->RollWindow);   // inclusive
        Z.SpeedTier = K <= 35 ? NYC->WalkerSpeed : K <= 70 ? NYC->RunnerSpeed : NYC->SprinterSpeed;
    } else if (Z.GetRole() == EHoverZombieRole::Kid) Z.SpeedTier = 700.f;   // DA_NYC_Kid crawler; BS_Kid_Crawl PlayRate speed/150, clamp 1-4
    else Z.SpeedTier = 0.f;                                    // Brute/Boss (AlphaBrute, Riot: Stage 2): DA speeds (roster section)
    if (bReplacement) { Z.PendingHealthFraction = PendingFraction.GetValue(); PendingFraction.Reset(); }   // Stage 2 only
    if (NYC->IsBossDefinition(Z.ZombieData)) {                 // both are Role Boss; the Alpha Brute elite stays Role Brute
        if (!Boss.IsValid()) Boss = &Z;                        // the first boss drives the second-entry fraction
        PlayBossIntro(Z);                                      // roar, shake, banner (golem or Giant Kid label)
    }
    Director->OnSpawned(Z);                                    // jitter, stamp, credit -= 1, log line
    if (!bReplacement) ++SpawnedThisRound;                     // re-queued units do not consume an ordinal
}
```

The AI tick applies `PendingHealthFraction` (Stage 2 re-queue) on its first rewrite. Resulting mix: R1 100% walkers, R5 about 44% walkers, R8 the last round with walkers (11%), R9 0% walkers and 2.8% sprinters (k in [36,71]), R13 about 47% sprinters, R18+ all sprinters. The spine's speed rule says 'R9 last walkers'; that slip is corrected in the errata.

The speed roll and the spawn jitter (06.6) live in this spawn hook and the director; the roster section references them and does not repeat them.

Rules on the director's 1 s tick:
- **Forced sprinters:** after R3, when `GetZombiesRemaining() <= 3` (nothing left to spawn and at most three alive), the remaining Standards are set to `SprinterSpeed`. Brutes and bosses are excluded.
- **Straggler promotion:** every 10 s, one Walker or Runner farther than 25 m from the player moves up one tier.

`MaximumRunSpeed` still caps speeds (Standard 620, Kid 820).

### 06.6 UHoverSpawnDirector

The director replaces the per-frame loop at `HoverCyberCity.cpp:283-324`. `SpawnZombie` and `GetRandomSpawnPoint` are non-virtual, so it still steers the vendor through `bIsEnabled` (`ZE_ZombieSpawnPoint.h:38`, read at `.cpp:393-411`). Level-placed points default to `bIsEnabled = true`, and the base loop's `:309` clear is skipped. So in `Init`, in `BeginRound` and on every re-choice the director runs `for (auto &S : Spawners) if (S.Point.IsValid()) S.Point->bIsEnabled = (S.Point == Chosen);`. The vendor's `RandRange` then always lands on a one-element list.

```cpp
USTRUCT() struct FHoverSpawnerState {
    GENERATED_BODY()
    TWeakObjectPtr<AZE_ZombieSpawnPoint> Point; FName Zone; bool bEmerger = false;   // SpawnTags "Zone.<Name>", "Emerger" (tag name open, 06.8)
    float LastUsed = -1000.f; int32 UsesThisRound = 0;
};
UCLASS() class HOVERFLIGHT_API UHoverSpawnDirector : public UObject {
    GENERATED_BODY()
  public:
    void Init(AHoverNYCSurvivalGameMode *Mode, UHoverNYCEncounterSettings *Settings);
    void BeginRound(int32 Round, EHoverRoundKind Kind, int32 Quota);
    void Update(float DT);            // credit every tick, scoring 0.25 s, pool 1 s, stragglers 2 s, promotions 10 s
    void OnSpawned(AHoverCyberZombie &Z);
    float GetSpawnRate() const;       // 0 = spawn this tick, BIG_NUMBER = hold
    bool  IsBossSpawnArmed() const { return bBossArmed; }
    void  SuppressSpawns(float Seconds) { SuppressUntil = Now() + Seconds; }
    void  RebuildPool();              // called by the zone subsystem on door open (section 07)
  private:
    AZE_ZombieSpawnPoint *Pick(const FVector &Target, APawn *Player, bool bOnFoot, bool bBoss);
    bool  IsOccluded(const FVector &Eye, const FVector &P) const;   // LineTraceTestByObjectType(AllStaticObjects), +60/+170
    void  RelocateStragglers();
    UPROPERTY() TArray<FHoverSpawnerState> Spawners;
    TArray<TWeakObjectPtr<AHoverCyberZombie>> Live;   // own alive set: vendor ZombiesAlive has no getter
    TSet<FName> ActiveZones;
    TArray<TWeakObjectPtr<AZE_ZombieSpawnPoint>> Recent;  // last 3 picks
    TWeakObjectPtr<AZE_ZombieSpawnPoint> Chosen;
    float Credit = 0.f, StallStart = -1.f, SuppressUntil = 0.f, RateJitter = 1.f, LastInterval = 0.f, LastPressure = 1.f;
    int32 PackRemaining = 0, Candidates = 0; bool bBossArmed = false, bRelaxCone = false;
};
```

**Candidate pipeline.** Runs every 0.25 s while `WaveInProgress`. `T` is the player target:
- On foot and grounded: the pawn location.
- On foot but airborne (vault, glide, fall): the last grounded location, stamped by `AHoverPilot` on every grounded tick. Reachability is still required.
- Mounted or on the board: the projected point `Loc + Vel x 3`.

| Gate / weight | Rule | Replaces |
|---|---|---|
| Zone pool | `Zone` in `ActiveZones` (player zone + one OPEN hop, section 07) | none |
| Distance band | 2000-6000 cm weight 1.0; 1400-2000 and 6000-10000 weight 0.3; else excluded; vehicles limited to 6000 of `T` | hard 14-100 m (`:289`) |
| Reachability | `CanReachPoint(P, T, Extent)`: on foot (120,120,200), projected (500,500,300) | skipped unless grounded on foot (`:292-294`) |
| Off-screen | behind the view (`dot <= 0`) weight 1.0; otherwise must be occluded by static geometry at +60 and +170 cm, weight 0.8; visible excluded unless `bRelaxCone` | `ECC_Visibility` trace blocked by zombie meshes (`:301`) |
| Occupancy | player or vehicle within 300 cm excluded; a zombie within 150 cm excluded only if it spawned less than 1 s ago | any pawn 300 cm (`:303-308`) |
| Cooldown | `Now - LastUsed < max(4, 2 x SI(r))` | 60 s age score (`:313-315`) |
| Per-round cap | `UsesThisRound >= ceil(Quota/3)` excluded while others exist | none |
| Distinct recent | with >= 3 candidates, `Recent` excluded | none |
| Pick | weighted random; boss = farthest reachable | best score |

**Horde packs:** while `PackRemaining > 0`, the director re-uses `Chosen` without the Cooldown, Per-round cap and Distinct-recent gates. Distance, reachability, occupancy and cone still apply, and if they fail the pack ends early. `PackRemaining` drops by one per spawn. At 0, the full pipeline picks the next entrance and sets `PackRemaining = HordePackSize`.

**Pacing (credit is the only gate).** Each tick:

```
Interval = SI(r) x Tuning.SpawnInterval x RateJitter
SI(r)    = 2.0 x 0.95^(r-1), floor 0.5   (horde: 0.65 x 0.95^(r-1), floor 0.35)
Pressure = Raise x Lower
           Raise = 2.0 if catch-up (Live < 8 and quota remains), else 1.5 if no zombie within 2500 cm, else 1.0
           Lower = 0.5 if >= 4 zombies within 800 cm or a boss is alive, else 1.0 (no stacking)
Credit   = min(1, Credit + Pressure x DT / Interval)
```

- `GetSpawnRate()` returns 0 when the boss spawn is armed. It also returns 0 when `Chosen` is valid, `Credit >= 1` and `Now >= SuppressUntil`. In every other case it returns `BIG_NUMBER`.
- With a rate of 0, the vendor test `Now - LastSpawnTime >= Rate` (`.cpp:453`) is always true, so the vendor's `LastSpawnTime = 0` initialisation (`.h:129`) and stale stamp no longer matter.
- `OnSpawned` subtracts 1 from `Credit` and keeps the remainder, so the average rate is exact. Individual gaps are quantised to the 0.1 s tick. `OnSpawned` also re-rolls `RateJitter` in [0.85, 1.15] and stores `LastInterval` / `LastPressure` for the log.
- The cap at 1 means credit never banks, which rules out back-to-back bursts.
- Nuke: `SuppressSpawns(3)`.

Catch-up is active at every round start, so the expected R1-3 cadence is about 1.0 / 0.95 / 0.90 s. R1 runs at catch-up cadence for its whole 6-zombie quota. Players will notice this, so it is stated here for the owner up front.

**BO7 deviation:** BO7 floors the interval at 0.1 s and clamps the round at 60 in the calculation. AFS floors at 0.5 s (0.35 s on hordes) because MaxConcurrent 24 already binds from about R20 on the unbenchmarked NYC city. The floor binds at R28, which makes the round-60 clamp irrelevant.

**Stall guard.**
- When no candidate exists: set `StallStart` and `Credit = 0`; credit does not accrue while stalled.
- At 4 s: `bRelaxCone = true` and a `HOVER_SPAWN_RELAX` log line. Distance, reachability and occupancy stay enforced.
- At 12 s: a `HOVER_SPAWN_STALL` warning with the player location, for the level pass.
- When a candidate returns, credit accrues from 0, so the first spawn lands at `StallClearedAt + Interval / Pressure`. `bRelaxCone` clears after the next spawn.

`Super::Tick` always runs, because the base-class guard is skipped via `bExternalSpawnDirector`.

**Spawn jitter** (in `OnSpawned`, normal spawners only; 250 cm radius (tuning placeholder)):

```cpp
if (auto *Nav = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld())) {
    FNavLocation Out;
    if (Nav->GetRandomReachablePointInRadius(Z.GetActorLocation(), 250.f, Out))
        Z.SetActorLocation(Out.Location + FVector(0, 0, 50), false, nullptr, ETeleportType::TeleportPhysics);
}
Z.AddActorWorldRotation(FRotator(0, FMath::FRandRange(-60.f, 60.f), 0));
```

The vendor spawns with `AdjustIfPossibleButAlwaysSpawn` (`.cpp:525-539`), so the nudge never fails a spawn.

**Emerger spawners** (`bEmerger`, Underpass) skip the jitter. The roster section and v2 propose the tag name `Ground` for the same points; one name is to be chosen (06.8), the behaviour is the same. They play `NYC->EmergeMontage` through the locomotion bridge `PlayAction` with a 1.2 s no-move window. If the animation section has not delivered the retargeted Burst clip yet, the montage is null and the point behaves as a normal spawner.

**Incoming directions (2026-11-03).** After the placement gates, classify each complete nav path by where it first enters an 8 m circle around the target. `DirectionalSpawnBias` defaults to 0.85: on those picks, favor the eligible side least recently served by the last four successful entrances or pack starts. Points sharing one corridor share that side. Actual horizontal player velocity gives approaching from ahead up to 1.4 times the weight; standing still or turning the camera adds no forward weight. Boss releases keep their farthest eligible entrance and an intact horde pack keeps its source. A single eligible lane can still spawn. `AFS_GroundEntry` marks a fixed floor site for the full-body rise before pursuit.

**Stragglers** (2 s pass). This is the single statement of the straggler policy; the roster section references it.

Stage 1 is relocation only: no destroy, no plugin patch. A zombie is relocated when any of these holds:
- farther than 12000 cm, older than 8 s and not visible;
- no complete path for 20 s;
- more than 6000 cm away and not visible for 20 s.

Relocation is `StopMovement`, a teleport to `Pick()` + 50 Z, `Key_LastKnownLocation = T`, and `RelocationCount++`. `RelocationCount` has no limit in Stage 1; the same actor stays in `ZombiesAlive`. On a successful return it heals to its own wave-scaled maximum HP, including bosses (owner ruling, 2026-11-03). A failed entrance search leaves health unchanged.

**Stage 2 (optional, declared deviation, 06.1):** destroy-and-requeue, the spine's original rule. The two 20 s triggers and `RelocationCount >= 3` then re-queue instead of relocating:
1. Push `{Z.ZombieData, Health/MaxHealth}` to `Requeued`.
2. Call `NotifyZombieRemoved(&Z, true)`.
3. Call `Z.Destroy()`.

A boss is never re-queued; it is always relocated.

```cpp
// Stage 2 only. ZE_ZombieWaveGameMode.h (protected, beside ConfigureWave) - declared deviation, 06.1
void NotifyZombieRemoved(AZE_ZombieCharacter *Zombie, bool bRequeue);
// ZE_ZombieWaveGameMode.cpp
void AZE_ZombieWaveGameMode::NotifyZombieRemoved(AZE_ZombieCharacter *Zombie, bool bRequeue) {
  if (Zombie) Zombie->OnDeath.RemoveDynamic(this, &AZE_ZombieWaveGameMode::OnZombieDeath);
  ZombiesAlive = FMath::Max(0, ZombiesAlive - 1);
  if (bRequeue) ZombiesToSpawn++; else ZombiesRemaining = FMath::Max(0, ZombiesRemaining - 1);
  OnZombieCountChanged.Broadcast(ZombiesRemaining, ZombiesKilledThisWave);
  CheckWaveStatus();
}
```

**Unreachable targets.** `AHoverCyberZombieAI` gets `UnreachableSince` and `bTargetDropped`. The timer runs while `GetPathFollowingComponent()->HasPartialPath()` is true, or while the director's `CanReachPoint` fails for a mounted or airborne target. After 6 s:
- `bTargetDropped = true`;
- `ClearValue(Key_TargetEnemy)`, `Key_ZombieState = 0`, roar.

The retarget block at `HoverCyberCity.cpp:343-351` becomes `if (GetPawn() && Player && bDirectChaseMode && !bTargetDropped)`. That covers both the `SetTargetEnemy` call, which also resets `Key_ZombieState` to 1 (`ZE_ZombieAIController.cpp:130-135`), and the `Key_LastKnownLocation` write at `:349`. Without the gate, the 0.5 s tick would restore the target. The flag clears when the path test succeeds again, or when the player is on foot and grounded with a full path. At 20 s the straggler rule relocates the zombie (Stage 1; re-queue in Stage 2).

The vendor 1 s `UpdateDirectChaseTarget` (`ZE_ZombieAIController.cpp:154-167`) cannot interfere, because `FindNearestPlayer` casts to `AZE_PlayerCharacter` (`:169-190`, cast at `:185`). The player section's downed-pose ignore filter uses the same predicate (`ShouldChase(Player)`).

In `L_NYC_Survival` the vehicle path covers only the hoverboard: the bike is absent and the truck is parked.

### 06.7 Complaint-to-mechanism

| Owner complaint | Cause (skeptic status) | Fix |
|---|---|---|
| Nothing, then a burst | CONFIRMED: vendor Tick skipped while no entrance qualifies, stale `LastSpawnTime` (`HoverCyberCity.cpp:328-329`, `ZE_ZombieWaveGameMode.cpp:451-456`) | always `Super::Tick`; credit-only pacing with no banking; credit reset at stall; 4 s cone relax |
| Spawns pop in / look arbitrary | CONFIRMED: zombie meshes block the `ECC_Visibility` occlusion trace (`:301`, `:486-487`), so entrances behind a crowd count as hidden; fixed 2.0-2.5 s cadence at one exact XY. UNVERIFIED: the "pool flips every frame" claim was refuted (safe pool 6-8 of 8; the evidence predates the 2026-10-25 LRU/reachability code) | static-only occlusion at two heights, zone pool, 20-60 m band, distinct last-3, jitter. Not credited until the re-capture in 06.8 step 4 |
| Same door repeats / conga line | CONFIRMED: one exact XY, no jitter | cooldown, per-round cap, 250 cm reachable jitter (tuning placeholder), +-60 yaw, interval jitter |
| Zombies walk into walls / never arrive | CONFIRMED: reachability skipped when not grounded; no straggler rule; wave needs `ZombiesAlive==0` | projected/last-grounded reachability, 6 s target drop, relocation (incl. the 20 s triggers); re-queue is Stage 2 |
| Bunching at the player | single goal, 5 cm acceptance (crowding slice) | out of scope; `SpeedTier` mix hands off |

### 06.8 Interfaces, authoring and VALIDATION

**Interfaces with other sections:**
- **Section 07:** supplies `ActiveZones` (player zone + one open hop), the `Zone.<Name>` tags, the door-open call to `RebuildPool()`, and the farthest-entrance query. Spawner counts per zone (4/4/4/3/3/4/3 = 25) must match its zone list, with at least 3 entrances per zone.
- **Section 05:** drops, kill cams, enrage speeds (including the optional Stage 2 Alpha Brute elite), the Riot pool (Stage 2) and the StoneGolem/Giant Kid RunSpeed values hang off `OnZombieSpawned`, `IsBossAlive()` and `GetRoundKind()`.
- **Player section:** owns `:271 SetCanBeDamaged`, which stays in the kept part of Tick, plus the board-damage rule and the downed filter.
- **Crowding slice:** replaces the `:349` raw location with a slot goal.
- **Sequencing:** the edits from 06.6, the crowding slice and the player section all touch `AHoverCyberZombieAI::Tick` and are applied in one pass by a single owner, in this order: target gate, then slot goal, then speed/health.
- **Section 08:** owns the banners, stingers and `HOVER_SPAWN_STALL` surfacing. `UHoverCyberWaveHUD` EncounterText (13 pt in a 270x190 box) needs a width check for the longer labels.
- **Sections 04/09:** `StartingEquipment`, `StartingGold 500`, and the HoverAuthoring Python mirror of the `UHoverNYCEncounterSettings` fields.

**Owner amendments.** The full list is in the design doc checklist, and this section depends on it:
- AGENTS.md:26-28: add the NYC - Survival sentence.
- README.md:167-173: add the fifth level row and the `?game=` option.
- Docs/CONTROLS.txt:10-11: update the test level list.
- HoverTestController.cpp:106-119: `Level == 4` -> `/Game/HoverPrototype/Maps/L_NYC_Survival?game=/Script/HoverFlight.HoverNYCSurvivalGameMode`.
- HoverGraphicsMenu.cpp:97,123: `% 4` -> `% 5`.
- `.gitignore`: add `Docs/NYC_SURVIVAL_<date>.txt` to the Docs whitelist.
- PAL_AFS_Runtime: add `/Game/HoverPrototype/NYC` to the cook roots.
- Native-patch matrix: Stage 2 only, if destroy-and-requeue is adopted: add the `NotifyZombieRemoved` row.
- Schedule check: confirm that R45/R75/R105 stay horde rounds with the boss shifted to R46/R76/R106 (no heavy Brutes on the shifted round), and that R39 uses the 50% second-entry rule.
- Spawner tag: choose `Emerger` or `Ground` for the Underpass emerge points.

**Authoring steps:**
1. Place at least 25 `AZE_ZombieSpawnPoint` actors in the new owned map `/Game/HoverPrototype/Maps/L_NYC_Survival`, which references the same four vendor sublevels. Give each one `SpawnTags = {"Zone.<Name>"}` and the tag `AFS_NYCSpawn`; Underpass points also get `"Emerger"`.
2. Extend the `UHoverAuthoring::AddCityNavigation` world gate (`HoverAuthoring.cpp:197-200`) with `L_NYC_Survival`, call it with the corridor bounds plus the zone extents, and build.
3. Author `DA_NYCWaves`, `DA_NYCEncounters` and `DA_NYC_*` through UnrealEditor-Cmd Python (`AssessCyberWaves.py` pattern), dumping every row to `D:/AFS_Comparisons/NYCSurvival_<date>/Evidence/waves.json`.
4. Re-capture first: run the current build of L_CyberCity with `ReviewCyberSpawns.py` to establish a placement baseline. Without it, the pool changes are not credited with fixing "random" spawns. Then run `Scripts/ReviewNYCSpawns.py`: `find_complete_city_path` from every spawner to the start and to each zone centre; fail if any zone has fewer than 3 entrances 14-100 m from its centre.
5. Run `Scripts/VerifyNYCSurvival.py` offscreen, never concurrently with another run:
   - Assert `CustomWaves[r]` = {N(r), H(r)/100, damage band}, plus FirstWaveDelay 5, TimeBetweenWaves 10 and MaxConcurrent 24, with `Tuning.Count/Health/Speed/SpawnInterval` all at 1.0.
   - Play R1-R6 and log one `HOVER_SPAWN` line per spawn: `{time, spawner, zone, distance, tier, interval, pressure, credit, candidates, relaxCone}`.
   - Assert each gap equals the logged `interval/pressure` within +-5% or one 0.1 s tick, whichever is larger.
   - Assert R1-3 cadence of about 1.0/0.95/0.90 s under catch-up, and pressure 1.0 in a controlled window (player stationary, 8-23 alive).
   - Assert that the first spawn after an injected initial stall lands at `StallClearedAt + interval/pressure`.
   - Assert at least 3 distinct spawners per round, no spawn closer than 14 m, and no in-cone spawn unless a `HOVER_SPAWN_RELAX` line precedes it.
   - Assert that health at t+1 s equals `Stats.MaxHealth x HealthScale` and that the AI-tick rewrite ran; for bosses this gives R13 6,900, R19 10,920 and R27 39,000 + 31,200.
   - Assert R31 = 3,500 + 800 HP through the getter, and that the spawn-phase duration equals the sum of the logged intervals.
   - Assert `GetRoundKind` for R1-60: hordes on every multiple of 5 (R45 included); bosses on 13/19/27/33/39/46/51/57 (R46 = shifted R45, StoneGolem + Giant Kid, no heavy Brutes); the R27 golem enters before the Giant Kid; with `bAlphaBruteElite` off, no `DA_NYC_AlphaBrute` spawns.
   - Assert that no straggler is destroyed in Stage 1 (relocations only, `ZombiesAlive` never decremented outside a death).
   - Separately assert that index 3 `L_NYC_Explore` still has zero zombies; `VerifyNYCExploration.py` stays unchanged.

**The VALIDATION section of `Docs/NYC_SURVIVAL_<date>.txt` must state:**
- DA values are prescribed until they are dumped.
- R31+ is formula-only. The vendor fallback to `Auto^(W-1) = 1.0` is verified at `ZE_WaveGameModeSettings.cpp:7-28,59-62`, so the getter is mandatory.
- `Tuning.*` were 1.0 during validation.
- Crowd separation and attack slots are not covered by this pass.
- Expected round length: R30 (105 standards at 13 body shots, 24 concurrent, 0.5 s floor) is 4-5 minutes. Past R30, rounds are endurance rounds by design.
- Performance at 24 concurrent and 70-Kid hordes was tested on NullRHI only. If frame time is a problem: MaxConcurrent 16 with lower `SpawnIntervalFloor`/`HordeIntervalFloor` (round length about +30%), and `HordeCountCap 48` if hordes collapse.
- It is unverified whether the hoverboard path sets `bMounted`. The last-grounded rule covers it either way.

## 4. Zombie roster, behaviour and crowd AI

This section covers behaviour, stats, AI, phases and C++ hooks. Asset paths, clip names, skeleton families, retarget routes and texture imports are in **Section 10 (roster asset mapping)** and are not repeated here. The round schedule, the spawn director, the frozen health scale, the speed roll, spawn jitter and the straggler policy are in **Section 3 (rounds and spawn director)** and are referenced, not restated. Internal references use §n. Values that neither the spine nor the lead decisions fix are this section's and are marked "(tuning placeholder)" where they were changed or are boss/elite specific.

### 1. Ownership and code placement

Everything here lives in `M:/UnrealProjects/AFS/Source/HoverFlight` as subclasses of the AFS adapter. Stage 1 does not touch the 14 patched plugin files (the `NotifyZombieRemoved` patch is a Stage 2 option, Section 3). The mode is `AHoverNYCSurvivalGameMode : AHoverCyberCityGameMode` (a new file owned by the rounds slice). It has to derive from the Cyber adapter, not from `AZE_ZombieWaveGameMode`. The reason: `AHoverCyberZombieAI::Tick` (HoverCyberCity.cpp:372, 382), `RecordSpawn` in `AHoverCyberZombie::BeginPlay` (:497; it becomes `OnZombieSpawned` in Section 3), the zombie insta-kill and gold paths (:565, :588) and the damage scaling in `AHoverPilot::TakeDamage` (HoverPilot.cpp:1652-1659) all call `GetAuthGameMode<AHoverCyberCityGameMode>()`, and every one of them would silently do nothing under the other base. `IsHordeRound()` and `IsBossRound()` are added on the NYC mode. `GetWaveSettings()` is already public const (ZE_ZombieWaveGameMode.h:85-88).

Existing hooks:
- `AHoverCyberZombie` (HoverCyberCity.h:97-122).
- `AHoverCyberZombieAI` (:84-94). Its tick interval is 0.5 s, set at HoverCyberCity.cpp:231.
- `UHoverCyberZombieDefinition` (HoverCyberVariants.h:17-33) and `UHoverBruteStompNotify` (:36-42, calls `StompImpact`, HoverCyberCity.cpp:542-547).
- The vendor `UZE_BTService_CheckAttackRange::TickNode` and `UZE_BTTask_ZombieAttack::ExecuteTask` are protected virtual, and `TargetKey`/`CanAttackKey` are protected UPROPERTYs.
- `AZE_ZombieCharacter::PerformAttack` is public virtual (ZE_ZombieCharacter.h:57); it picks a random entry of `CachedAttackMontages` (ZE_ZombieCharacter.cpp:378).
- `UZE_ZombieAnimNotify_AttackHit` (ZE_ZombieAnimNotify_AttackHit.h:18, exported, `Notify` virtual) calls `OnAttackHitCheck`. Some source clips do serialize notifies: Etherion `Anim_Zombie_Walk_Giant` carries `AnimNotify_MovingZombieFootstep` and `Anim_Zombie_Attack` carries `AnimNotify_PlaySound` (Section 10). None of the golem, Feral, ZAP or Etherion clips carries an attack-hit notify, so every new montage gets `UZE_ZombieAnimNotify_AttackHit` placed by hand.

| File | Contents |
|---|---|
| `HoverNYCZombie.h/.cpp` (new) | `AHoverNYCZombie : AHoverCyberZombie` (including the boss ability timers, §10), `AHoverNYCZombieAI : AHoverCyberZombieAI`, `UHoverAttackSlotSubsystem`, `UHoverBTTask_MoveToSlot`, `UHoverBTService_AttackSlot`, `UHoverBTTask_ZombieAttack`, `UHoverStompTelegraphNotify`, `UHoverWindupNotifyState`, `UHoverFistImpactNotify : UZE_ZombieAnimNotify_AttackHit`, `UHoverNYCNavigationSystem`, `UHoverNYCCrowdManager`, `UHoverNukeDamageType` |
| `HoverCyberVariants.h` (edit) | enums, `FHoverBossPhase`, definition fields, and the `SwarmCount` ClampMax meta 24 -> 80 (§3). No boss schedule here: it lives on Section 3's `UHoverNYCEncounterSettings` |
| `HoverCyberCity.h/.cpp` (edit) | virtual hooks and the capsule half-height override (§5); `Blood`/`LastStompTime` moved to protected; stomp gate and radial damage (§10); the Nuke `ApplyDamage` (:641) uses `UHoverNukeDamageType` |
| `HoverPilot.cpp` (edit, player slice) | hit scaling reads the attacker's frozen damage scale (§5) |
| `HoverAuthoring.cpp` (edit, level slice) | `AddCityNavigation` gate (:200) also accepts `L_NYC_Survival` |
| `Content/HoverPrototype/NYC/AI/BB_NYCZombie`, `BT_NYCZombie`, `ABP_NYCZombie` | owned duplicates of ZESP `BB_Zombie`/`BT_Zombie`/`ABP_ZombieMaster` (§7, §2) |
| NYC definitions and montages | `DA_NYC_<Name>` under `NYC/Zombies/` (the crawler is `DA_NYC_Kid`), plus Section 10's `DA_StoneGolem` (Variants/Golem) and `DA_GiantKid` (Variants/Kid); `AM_NYC_Attack_01/02` carry a wind-up |

`Config/DefaultEngine.ini` is **not** edited (§8). `BP_NYCZombie` (parent `AHoverNYCZombie : AHoverCyberZombie`, AnimClass `ABP_NYCZombie`, overridden per definition by `AnimClassOverride`) and `BP_NYCZombieAI` mirror `BP_CyberZombie`/`BP_CyberZombieAI`. `DA_NYCWaves.ZombieClass` is set to `BP_NYCZombie`; the slot, phase and Rise code below depends on that class.

**Cross-slice dependencies**

| Slice | What this section needs from it |
|---|---|
| Rounds (Section 3) | `ConfigureWave` R31+ fallback, `IsHordeRound()`, `IsBossRound()`, K(r), `HealthScale` and `SpeedTier` stamped per actor in `OnZombieSpawned`, `GetRoundDamageScale`, the boss schedule on `UHoverNYCEncounterSettings` (`BossRounds[]`, `FindBossRound`, boss spawn at 40% quota, Giant Kid entry at 50% golem HP, R33 additive Brute adds, the R45 -> R46 shift), the optional Alpha Brute swap, and a jump-to-wave exec `NYCStartAtWave N` for validation |
| Player | `AHoverPilot::IsDowned()` and its grace window, the frozen-damage read at HoverPilot.cpp:1652-1659, plate routing, the on-foot (32/97, HoverPilot.cpp:85) and mounted (90/142, :463) capsule sizes used by the attack test (§7) |
| Economy | `Mode->AwardKill(Zombie, EHoverKillKind)`, `Mode->OnSpecialKilled(Zombie)` (Brute drop alternation, boss Max Ammo, kill cam), the flat Nuke +400 |
| Spawn (Section 3 director) | zone-tagged spawners, the `Emerger` spawn tag (Section 10 calls the same tag the proposed `Ground` tag), the director's spawn jitter, straggler relocation and stall guard |
| Level | `L_NYC_Survival` World Settings NavigationSystemClass, NavMeshBoundsVolume, the Underpass nav area |
| Weapons | traces on `ECC_Visibility` (the zombie mesh blocks it and the capsule ignores it, per `AHoverCyberZombie::BeginPlay`, HoverCyberCity.cpp:484-490), so `Hit.BoneName` is valid; an explosive damage type for the Stage 2 armor pools; penetration calls `TakeDamage` once per body |

### 2. Roster

The Cyber standards, Brute and Kid play the ZESP `Zombie_001` montages directly. This works because `UHoverAuthoring::ConfigureVariantSkeleton` (HoverAuthoring.cpp:136-158) lists the ZESP `SK_Mannequin` as compatible and the owner rigs carry its 61 UE4-named bones. The NYC definitions **reuse the existing Variants meshes**. All eleven owner meshes are in play (Standard01-04, Brute, Kid, Horror, BogZombie, Mythical, Plant, Pirate), plus the StoneGolem runtime copy. In Stage 1 the five Lakeside meshes are extra Standard skins only. Extra clip families (ZAP-UE4, Feral, Etherion) are added by further `ConfigureVariantSkeleton` registrations or, where proportions fail, by the Lakeside IK route; Section 10 lists which skeleton gets which registration and the fallback RTs. Rules for this slice:
- Registration is additive: no Cyber DA references a new clip. It does edit Cyber-shared skeletons, so `VerifyCyberWaves.py` is re-run and its evidence kept.
- Before anything depends on it, play back one Burst clip on `SK_Standard04`, `anim_Belly_Crawling_A` and `LeapForward_Short` on `SK_Kid`, `StrongAttack_01` on `SK_Kid` at Height 320, and `walkF`/`attack3` on the golem copy (Section 10's five-clip viewport pass).
- Lakeside DAs and their `Retargeted/` clips are not edited; NYC uses duplicate DAs of the Lakeside bodies.
- `ABP_NYCZombie` is an owned duplicate of `ABP_ZombieMaster` (TargetSkeleton `SK_Mannequin`, so it runs on every registered rig). It keeps the vendor slot (read its name in the editor; Section 10 notes it is not decodable offline), adds an `UpperBody` slot layered from `spine_01`, a `Crawl` state driven by `bCrawling`, and the crawl play rate `speed / 150` clamped 1-4. A child ABP cannot add states, hence the duplicate.

| Enemy | Role / Stage | Definition | Behaviour clips (names per Section 10) | Vocal (Etherion `/Game/Zombie/Sound/`, owner sign-off) |
|---|---|---|---|---|
| Street Zombie (tier by roll) | `Standard`, S1, R1+ | `DA_NYC_Standard01-04` | 01/02: `BS_Zombie_WalkRun`, `AM_NYC_Attack_01/02`, `AM_Hit`, `AM_Death`. 03 (sprinter-weighted from R9): + Feral `Run`, `Attack_Left/RightSwipe`. 04: + ZAP `anim_Burst_*` on `Emerger` spawns. Leg-hit crawler: ZAP `Belly_Crawling_A/B` | `SC_ZombieV2_ChasingSlow` (walker) / `SC_ZombieV2_Chasing`, `SC_ZombieV2_AttackHiss`, `SC_ZombieV2_Death`, `SC_Zombie_Roar` on first sight |
| Lakeside skins (Horror, BogZombie, Mythical, Plant, Pirate) | `Standard`, S1, R1+ | `DA_NYC_Horror/BogZombie/Mythical/Plant/Pirate` (duplicates of the Lakeside bodies), round-robin with `DA_NYC_Standard01-04` in Section 3's default roster | Lakeside set per Section 10; Standard stat block, speed roll, points 90/115/105; no special behaviour | as Street Zombie |
| Kid crawler | `Kid`, S1, horde unit R5 and every 5 | `DA_NYC_Kid` (NYC duplicate of `Variants/Kid` with `BS_Kid_Crawl` and Section 10's crawler values; Cyber `DA_Kid` is untouched) | `BS_Kid_Crawl` (Laying_Idle_A / Belly_Crawling_A / _B), `AM_Kid_Lunge` (Feral `LeapForward_Short`), `AM_Kid_Attack_B` (ZAP `anim_Attack_D`, `UpperBody` slot), hits ZAP `Taking_Damage_A/B`, `AM_Kid_Burst_*` on `Emerger` spawns | `SC_Zombie_Chasing` (+0.15 pitch), `SC_ZombieV2_AttackHiss`, `SC_Zombie_Death`, `SC_Zombie_Footstep` at half rate as scrape |
| Brute | `Brute`, S1, R8 | `DA_NYC_Brute` | `AM_Brute_Stomp` (2.367 s, landing 1.2 s), `AM_Brute_Smash` (1.433 s, hit 0.8 s) per Docs/ZOMBIE_SPECIALS_20261024.txt:27-29, + Feral `StrongAttack_02` | `SC_Entity_Roar`, `S_Entity_Slash_A` |
| Alpha Brute (optional elite) | `Brute`, S2 heavy rounds only, never a boss | `DA_NYC_AlphaBrute` (data duplicate of `DA_Brute`), `MI_Brute_Alpha` | Brute montages at 0.9x, enraged below 50% HP | `SC_Entity_Roar` |
| **StoneGolem** (boss A) | `Boss` + `StoneGolem`, S1, R13 | `DA_StoneGolem` | Own clips, unarmed, sockets empty: `AM_Golem_Attack_Light_A/B` (`attack3`/`attack2`), `AM_Golem_Attack_Heavy_A` (`attack1`, only if open-handed), `AM_Golem_Slam` (`attack5`), `AM_Golem_Hit_1-3`, `AM_Golem_Death_1-3`, `AM_Golem_Intro`, `dodge`, `BS_Golem_WalkRun` | `SC_Entity_Roar` + `S_Entity_Roar_Loop`, `S_Entity_Hit_A-C` (fist impacts), `S_Entity_Death`, `S_Monster_Ambience_Long_A-C` stinger |
| **Giant Kid** (boss B, placeholder name) | `Boss` + `GiantKid`, S1, R19 | `DA_GiantKid` (same Kid mesh at Height 320) | `BS_GiantKid_WalkRun` (Etherion `Walk_Giant`, Feral `Run` at 0.7), `AM_GiantKid_Charge`/`_Pounce`/`_Strong_01-03`/`_Rise`, `Feasting_01-03`, Etherion `Roar`, Feral `HitReact_01-04` | `SC_Entity_Roar`, `S_Entity_Slash_A`, `SC_Entity_Death`, `S_Entity_DistantRoar_A-J` stinger, Etherion footstep notify |
| Light armored | `Standard`, S2, R9+ | `DA_NYC_Pirate` (S2 special build) | Lakeside Retargeted + Variety, never sprints | `SC_Monster_Ambience`, `SC_Monster_Roar`, `S_Monster_Hit_A-C` on pool break |
| Heavy armored | `Standard`, S2, R17+ | `DA_NYC_BogZombie` (S2 special build) | Lakeside set, optional Etherion `Walk_Giant`/`Roar` | as light armored, `SC_Monster_Death` |
| Feral special | `Standard` + `Feral`, S2, R11+ | `DA_NYC_Horror` (S2 special build) | Feral full set: leap, swipes, `Feasting`, `Reanimate`, `HitReact_01-04` | `SC_ZombieV2_AttackHiss` + `SC_Zombie_Hiss`; `S_Zombie_Roar_Loop` on reanimate |
| Spore special | `Standard` + `Spore`, S2, R12+ | `DA_NYC_Plant` (S2 special build) | Lakeside + ZAP `anim_Burst_*`, `Laying_Idle_A/B` (emerge) | `SC_Zombie_Inhale` (telegraph), `S_Zombie_Exhale_1-10` |
| Elite | `Standard` + `Elite`, S2, R16+, cap 1 | `DA_NYC_Mythical` (S2 special build) | Lakeside + Feral `StrongAttack_01-03`, `LeapForward_Full`, `Idle_Roar_01/02` | `SC_Entity_Roar`, `S_Entity_Slash_A`, `SC_Entity_Death` |
| Riot | `Riot`, S2 | `DA_NYC_Riot` | Pirate/BogZombie or `SK_Standard02/04` body plus ZESP `Armor/SKM_Armor_001` via `SetLeaderPoseComponent` (skinned to `SK_Mannequin`, follows by bone name). Visible breakable plates are a Section 10 content gap; a helmet needs an owner-approved pack | `SC_Zombie_Inhale` |

The Alpha Brute's stage label is the one in the lead decisions (optional heavy-round elite, Stage 2); its DA can be authored early because it is a data duplicate, but it is off by default (`bAlphaBruteElite` false, Section 3).

The golem uses its own skeleton copy with the ZESP `SK_Mannequin` registered on it (Section 10's preferred route keeps `/Game/StoneGolem/` source art untouched), so `ABP_NYCZombie` drives it like the owner rigs. If the golem-skeleton blend space does not evaluate inside the Mannequin-targeted ABP, the fallback is `AnimClassOverride = ABP_NYC_Golem` on the golem skeleton with the same `Slot`/`UpperBody` names. The vendor `ABP_StoneGolem` and `BP_StoneGolem` are never used (no attack wiring, and it attaches the excluded hammer/shield). Gore props are `ZombieMale_AAB/Meshes/BodyParts/SKM_ZombieM_Male_BP_{Head_01,ForeArm_L/R,Hand_L/R,Leg_L1/R1,Foot_L/R}` with their `PA_*` physics assets, used as a pool of detached gibs (§9).

### 3. Definition fields and enums (HoverCyberVariants.h)

Append `Boss` (Stage 1) and `Riot` (Stage 2) after `Kid` in `EHoverZombieRole` (HoverCyberVariants.h:7-13); these are the only new roles, and the name "Warden" is not used anywhere. UENUMs serialize by name, so existing DAs load unchanged. Speed is a per-instance tier (Section 3), not a role. The Alpha Brute keeps `Role = Brute` (stomp gate, yaw, drop alternation, Insta-Kill rule); both bosses use `Role = Boss` and differ by `SpecialKind`.

```cpp
class USoundBase;
class UAnimInstance;
class UAnimMontage;

UENUM(BlueprintType) enum class EHoverSpecialKind : uint8 { None, StoneGolem, GiantKid };   // Stage 2 appends Feral, Spore, Elite

USTRUCT(BlueprintType) struct FHoverBossPhase
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere) float HealthFraction = .5f;   // starts at or below
    UPROPERTY(EditAnywhere) float Duration = 0.f;         // 0 = permanent (Alpha enrage); Brute enrage uses 8
    UPROPERTY(EditAnywhere) FName DetachPartComponent;    // Stage 2 golem armor break only; empty in S1
    UPROPERTY(EditAnywhere) FName WeakPointBone;          // Stage 2 only (x3, replaces the head multiplier); empty in S1
    UPROPERTY(EditAnywhere) float StaggerSeconds = 1.f;
    UPROPERTY(EditAnywhere) TSoftObjectPtr<UAnimMontage> StaggerMontage;
    UPROPERTY(EditAnywhere) float SpeedOverride = 0.f;    // bypasses MaximumRunSpeed
    UPROPERTY(EditAnywhere) float CooldownScale = 1.f;    // multiplies AttackCooldown
    UPROPERTY(EditAnywhere) bool bEnrage = false;         // stomp/slam chains of 2
    UPROPERTY(EditAnywhere) bool bUnlockSpecial = false;  // golem dodge
    UPROPERTY(EditAnywhere) FString Banner;
};

// UHoverCyberZombieDefinition, after StompRadius: one UPROPERTY per member (UHT rule)
// The speed-tier roll and its 180/400/600 values live on Section 3's encounter settings, not here.
UPROPERTY(EditAnywhere, Category = "AFS|Appearance") float CapsuleHalfHeight = 0.f; // 0 = Height * .5
UPROPERTY(EditAnywhere, Category = "AFS|Movement") float RotationYaw = 0.f;         // 0 = role default (:463)
UPROPERTY(EditAnywhere, Category = "AFS|Movement") float MaxAcceleration = 0.f;     // 0 = role default (:464)
UPROPERTY(EditAnywhere, Category = "AFS|Speed") float CloseWalkSpeed = 0.f;  // golem 240 (Stats.WalkSpeed) inside 8 m
UPROPERTY(EditAnywhere, Category = "AFS|Speed") bool bNeverSprints = false;  // Stage 2 armored
UPROPERTY(EditAnywhere, Category = "AFS|Armor") float ArmorHP = 0.f;         // Stage 2
UPROPERTY(EditAnywhere, Category = "AFS|Armor") float ArmorExplosiveMultiplier = .5f;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") bool bFlinchOnHit = true;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") float FlinchDamageFraction = .10f;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") float FlinchMontageCooldown = .35f;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") float WindupSeconds = .5f;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") bool bCanBeDismembered = false;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") bool bCanCrawl = false;
UPROPERTY(EditAnywhere, Category = "AFS|Hit") bool bAlwaysCrawl = false;     // Kid horde unit
UPROPERTY(EditAnywhere, Category = "AFS|Crowd") float QueueRingRadius = 260.f;
UPROPERTY(EditAnywhere, Category = "AFS|Crowd") float SeparationWeight = 10.f;
UPROPERTY(EditAnywhere, Category = "AFS|Crowd") bool bHeavySlot = false;     // capped inner claims
UPROPERTY(EditAnywhere, Category = "AFS|Boss") EHoverSpecialKind SpecialKind = EHoverSpecialKind::None;
UPROPERTY(EditAnywhere, Category = "AFS|Boss") TArray<FHoverBossPhase> BossPhases;
UPROPERTY(EditAnywhere, Category = "AFS|Boss") TMap<FName, TSoftObjectPtr<UAnimMontage>> SpecialMontages; // Slam, Charge (Giant Kid only), Pounce, Rise, Intro, Dodge, Roar, Feast
UPROPERTY(EditAnywhere, Category = "AFS|Boss") float SecondLifeFraction = 0.f;  // Giant Kid .3: Rise threshold, no HP added
UPROPERTY(EditAnywhere, Category = "AFS|Boss") bool bUsesStomp = false;
UPROPERTY(EditAnywhere, Category = "AFS|Boss") float StompDamageMultiplier = 0.f; // 0 = vendor sweep
UPROPERTY(EditAnywhere, Category = "AFS|Boss") float StompCooldown = 0.f;         // golem 4, Giant Kid/Alpha 2.5
UPROPERTY(EditAnywhere, Category = "AFS|Boss") float StompInterval = .8f;         // minimum re-arm
UPROPERTY(EditAnywhere, Category = "AFS|Anim") TSubclassOf<UAnimInstance> AnimClassOverride;
UPROPERTY(EditAnywhere, Category = "AFS|Audio") TSoftObjectPtr<USoundBase> SlowTierVocal;
UPROPERTY(EditAnywhere, Category = "AFS|Audio") TSoftObjectPtr<USoundBase> FastTierVocal;
UPROPERTY(EditAnywhere, Category = "AFS|Audio") TSoftObjectPtr<USoundBase> SightRoar;
UPROPERTY(EditAnywhere, Category = "AFS|Points") int32 KillPoints = 90;
UPROPERTY(EditAnywhere, Category = "AFS|Points") int32 HeadshotKillPoints = 115;
UPROPERTY(EditAnywhere, Category = "AFS|Points") int32 MeleeKillPoints = 105;
```

There is no boss health factor: bosses take Section 3's frozen `HealthScale` like every other zombie (§4, §5).

**Encounter settings.** The boss and heavy schedule lives on Section 3's `UHoverNYCEncounterSettings` (the `StoneGolem`/`GiantKid`/`AlphaBrute` pointers, `BossRounds[]`, `FindBossRound`, `BruteDebutWave 8`, `BruteFirstWave 12`, `BruteInterval 2`). This section adds no second schedule and does not edit `IsBruteWave`, `IsSwarmWave` or the `BruteFirstWave` ClampMin on the shared `UHoverCyberEncounterSettings`. What this section relies on:
- Schedule: R13 StoneGolem, R19 Giant Kid, R27 both (the Giant Kid enters at 50% golem HP), then 33 + 6k (R33 golem + 2 Brutes as additive boss adds, R39 two Giant Kids, then both, repeating). The priority is the spine's: horde beats heavy, heavy beats boss. When 33 + 6k is a multiple of 5 (R45, R75...), the boss round moves one round later (R46, R76). Section 3 owns this.
- Horde: `SwarmInterval 5` is a `DA_NYCEncounters` data value. The class default stays 10, so `DA_CyberEncounters` (serialized 12/2/5/10) is unchanged.
- The one encounter code edit is in HoverCyberVariants.h: the `SwarmCount` ClampMax meta (:63) goes from 24 to 80. NYC computes K(r) in `ConfigureWave`, and the performance fallback cap is 48.
- Section 10's `BruteFirstWave 16` was written for the superseded R20/30/40 boss schedule and is not used.

### 4. Stat blocks (vendor `FZE_ZombieStats` plus AFS fields)

DA values for the Kid crawler and Brute are Section 10's decoded values. Boss and Alpha health, damage, speeds, stomp values and points are the spine's and the lead decisions'. Any boss or elite cell not set by them is this section's (tuning placeholder), as marked in the row label. In Stage 1 the five Lakeside skins use the Standard column unchanged.

| Field | Standard (and S1 Lakeside skins) | Kid crawler | Brute | Alpha Brute (elite, S2) | StoneGolem (boss) | Giant Kid (boss) |
|---|---|---|---|---|---|---|
| MaxHealth (x base) | 100 (1x) | 45 (0.45x) | 600 (6x) | 1,200 (12x) | 1,500 (15x) | 1,200 (12x), one Rise at 30% with no HP added |
| MeleeDamage (band applied in `AHoverPilot::TakeDamage` from the attacker's **frozen** scale) | 30 | 15 | 60 (`DA_Brute` serializes 75) | 90 (90/150/225) | 75 (75/125/188) | 90 (90/150/225) |
| AttackRange / SphereRadius (boss/Alpha: tuning placeholder) | 150 / 50 | 130 / 45 (from 100 / 32) | 210 / 50 | 230 / 60 | 240 / 90 | 260 / 90 |
| AttackCooldown (+0-0.4 s jitter; golem: tuning placeholder) | 1.5 | 0.85 | 3.5 | 2.5 | 3.0 (x0.75 at P3) | 2.5 |
| Speed cm/s (Section 3 `SpeedTier`, else DA `RunSpeed`) | roll 180/400/600 | 700 | 260 | 300 | `RunSpeed` 420 (Jog), `WalkSpeed` 240 within 8 m | 300 |
| MaximumRunSpeed (tier cap; boss: tuning placeholder) | 620 | 820 | 380 | 380 | 420 (raised from 380 so Jog is not clamped) | 520 |
| Phase speed (`SpeedOverride`, bypasses cap) | - | - | 420 for 8 s at <= 30% | 650 at <= 50%, permanent | none (no charge in S1) | 650 at <= 50% |
| Height / CapsuleRadius / CapsuleHalfHeight | 180 / 34 / - | 110 / 23 / **23** | 250 / 55 / - | 300 / 48 / - | 320 / 70 / - | 320 / 60 / - |
| RotationYaw / MaxAcceleration (boss/Alpha: tuning placeholder) | 600 / 1400 | 600 / 2600 | 220 / 1400 | 220 / 1600 | 180 / 1200 | 260 / 1800 |
| StompRadius / StompDamageMultiplier / StompCooldown (all with the 2.1 s knockdown) | - | - | 400 / 2.0 / 0.8 s minimum interval | 500 / 2.0 / 2.5 s | 600 / 2.5 (slam) / 4 s | 500 / 2.0 (`Strong_03`) / 2.5 s |
| QueueRingRadius / bHeavySlot / SeparationWeight (boss/Alpha: tuning placeholder) | 260 / no / 10 | 220 / no / 6 | 320 / yes / 20 | 360 / yes / 20 | 400 / yes / 25 | 380 / yes / 22 |
| Points kill / head / melee | 90 / 115 / 105 | 90 / 90 / 90 | 250 | 250 (special ladder) | 500 | 500 (final death only) |
| Flinch / dismember / crawl | yes / yes / leg-hit | no / no / always | stagger only | stagger only | phase stagger / no / no | phase stagger / head gib on final kill / no |

**Stage 2 only: Lakeside specials and Riot** (not built in Stage 1; points follow the spine ladder, armored 150 and specials 250; every other value is a tuning placeholder)

| Field | Light armored (Pirate) | Heavy armored (BogZombie) | Feral (Horror) | Spore (Plant) | Elite (Mythical) | Riot |
|---|---|---|---|---|---|---|
| MaxHealth + ArmorHP | 100 + 60 | 150 + 120 | 120 | 90 | 450 | 150 + 50 |
| MeleeDamage / AttackRange / Sphere | 30 / 150 / 50 | 45 / 160 / 55 | 30 / 150 / 50 | 20 (burst 30) / 150 / 50 | 60 / 210 / 55 | 45 / 150 / 50 |
| AttackCooldown | 1.6 | 2.0 | 1.2 | 1.8 (burst 6 s) | 2.6 | 1.8 |
| Speed / cap | roll, `bNeverSprints`, 450 | roll clamped 160/320, 340 | 600, 650 | 180, 200 | 300, 380 (charge 650 for 1.2 s) | roll clamped 160/320, 340 |
| Height / CapsuleRadius | 185 / 34 | 195 / 40 | 185 / 34 | 180 / 36 | 230 / 45 | 180 / 36 |
| Queue / heavy / separation | 260 / no / 12 | 280 / no / 14 | 260 / no / 10 | 260 / no / 10 | 320 / yes / 18 | 260 / no / 14 |
| Points | 150 | 150 | 250 | 250 | 250 | 150 |
| Flinch / dismember / crawl | headshots only while pool > 0 / yes / yes | same / yes / no | yes / yes / no (reanimates) | yes / no / no | stagger only / no / no | suppressed while plate > 0 |

Notes on the stat tables:
- `DA_Kid` (AttackRange 100, AttackSphereRadius 32, MaxHealth 45, RunSpeed 650, MaximumRunSpeed 820) and `DA_Brute` (AttackRange 210, MeleeDamage 75, MaximumRunSpeed 380) are decoded in Section 10, so the old "dump before copy" precondition is now a check, not a blocker. The crawler values go onto the NYC duplicate `DA_NYC_Kid`; the Cyber City `DA_Kid` is untouched and the Cyber swarm keeps walking.
- **Boss health and TTK.** R13 golem 6,900 HP, R19 Giant Kid 10,920 HP, R27 39,000 + 31,200 = 70,200 HP, which is 70 + 56 PaP III headshots at 560. The Stage 1 golem is one unarmed mesh, so the spine's weak-point figures (R13 "33 weak point (4.1 s)", R27 "47 weak point (5.9 s)") do not apply. At full HP the golem fight takes roughly twice those times (spine errata 1.7). This is a tuning risk. Lowering golem base HP to 1,000 (10x) after playtest is an option, not a decision.
- The Alpha capsule radius of 48 is the spine value. Scaling the 250/55 Brute to 300 cm implies about 66, so the mesh will overhang the capsule. The mesh ignores `ECC_Pawn` (HoverCyberCity.cpp:489), so the overhang only affects how it looks; this stays with the owner.
- The golem's 320 cm is a ~1.7x upscale of the vendor pawn (Section 10; bounds unmeasured). The capsule follows `Height`, so a different measured height only changes the mesh scale.
- `MinGoldReward`/`MaxGoldReward` stay at 0, and kill points go through `OnKilledBy` (§5).
- `HeadBoneName "Head"` matches bone `head` on every rig, the golem included, because FName comparison is case-insensitive.

### 5. Hooks and spawn-time instance setup

**Hooks added to the Cyber classes.** The Cyber defaults reproduce today's behaviour exactly.

- `AHoverCyberZombieAI::GetWaveScales(float&, float&, float&) const` wraps :371-374.
- `ApplyPursuitSpeed(AHoverCyberZombie*, UBlackboardComponent*, float)` wraps :377-384.
- `APawn* SelectChaseTarget(APawn* Player) const` is used at :342-350, at the clear at :369, in the post-Super retarget in `AHoverCyberZombie::TakeDamage`, and in `OnPlayerDetected`. When it returns `nullptr`, the caller does `ClearValue(Key_TargetEnemy)`.
- `AHoverCyberZombie::ModifyIncomingDamage(float&, const FDamageEvent&, AController*, AActor*, const FHitResult&)` wraps the insta-kill line, so no NYC rule has to fight the base one-shot.
- `OnKilledBy(AController*, AActor*)` wraps `AddGold(RandRange)` at :587-588.
- `virtual float GetStompInterval() const` replaces the literal 0.8 at :510.
- `Blood` and `LastStompTime` move to `protected:`.
- **Capsule half-height** (Section 10's crawler spec): at :450 the capsule becomes `(CapsuleRadius, HalfHeight)` with `HalfHeight = CapsuleHalfHeight > 0 ? CapsuleHalfHeight : Height * .5f`, and the mesh offset at :458-459 becomes `-HalfHeight - (Bounds.Origin.Z - Bounds.BoxExtent.Z) * Scale`. The mesh still scales from `Height`, so the kid is a 110 cm body in a 46 cm sphere-capsule.
- Yaw and acceleration at :463-464 read `RotationYaw`/`MaxAcceleration` when non-zero; the role defaults accept `Boss` like `Brute` (220).
- `AnimClassOverride`, when set, is applied with `GetMesh()->SetAnimInstanceClass()` right after `SetSkeletalMesh` (:455).

**Spawn-time setup.** Section 3's `OnZombieSpawned` runs inside the base `BeginPlay` and owns three things that this section only reads:
- the frozen `AHoverCyberZombie::HealthScale = GetRoundHealthScale(Round)`;
- the speed roll into `SpeedTier`;
- the director's spawn jitter (reachable point within 250 cm plus ±60° yaw; `Emerger` points skip it).

The AI tick reads `HealthScale`, and so does `AHoverNYCZombie`. There is no second copy and no health factor.

**AHoverNYCZombie::BeginPlay** (after `Super::BeginPlay`)

1. **Boss facing**: a boss re-faces the player after the director's yaw so its intro plays toward the player (§10).
2. **Frozen damage scale**: `FrozenDamageScale = Mode->GetRoundDamageScale(spawn round)`, exposed through `GetFrozenDamageScale()`. The player slice changes HoverPilot.cpp:1652-1659 to `DamageScale = Cast<AHoverNYCZombie>(Causer) ? Z->GetFrozenDamageScale() : live wave`, so a zombie spawned in R10 still hits for 30 in R11. `AHoverNYCZombieAI::GetWaveScales` returns `HealthScale` and the frozen damage scale. The order of the vendor 0.1 s `ApplyDifficultyToZombie` one-shot against the adapter rewrite is covered in Section 3. `Tuning.Health` still multiplies on top.
3. **Speed** (the roll itself is Section 3's: R1 forced Walker, then `speed = 4r` with a 35-wide window. Results: R5 44% walkers, R8 11% and the last round with walkers, R9 0% walkers and 2.8% sprinters, R13 47% sprinters, R18 100%):
   - `ApplyPursuitSpeed` sets `MaxWalkSpeed = (PhaseSpeed > 0 ? PhaseSpeed : min(BaseSpeed * SpeedJitter, MaximumRunSpeed)) * Tuning.Speed`. `BaseSpeed` is `SpeedTier` when > 0; otherwise it is `CloseWalkSpeed` inside 8 m when that is set (the golem walks into melee at 240), and otherwise the DA `RunSpeed`.
   - `bNeverSprints` (Stage 2 armored) clamps a Sprinter `SpeedTier` to Runner.
   - The tier also selects the looping vocal (attenuated to 30 m) and the blend-space input.
   - Speeds above a blend space's last sample need a duplicated top sample with `RateScale`, or the feet slide. Cases: golem `jogF` at 420 with 1.4; Giant Kid Feral `Run` at 520 with 0.7 (Section 10); the Giant Kid's and the Alpha's 650 enrage with a `RateScale` set in the viewport pass (tuning placeholder).
4. **Jitter** (per instance, this section): `SpeedJitter 0.92-1.08`, MaxAcceleration x0.8-1.25, RotationRate.Yaw x0.8-1.2, `CooldownJitter 0-0.4 s`, SeparationWeight x0.7-1.3, `LateralBias +-80-200 cm`. Rotation and acceleration come from the DA and replace the role-hardcoded values the base sets. Bosses take half the jitter range.
5. **Crawl state**: `bAlwaysCrawl` sets `bCrawling` on the ABP at spawn. A Kid on an `Emerger` spawn plays `AM_Kid_Burst_*` first, with a 0.3 s blend into the crawl idle if the burst ends standing (Section 10).
6. **Crowd refresh**: after the base capsule resize (:450-454), call `UpdateCrowdAgentParams()` (CrowdFollowingComponent.h:71). NavAgentProps stay capsule-derived (`SetUpdateNavAgentWithOwnersCollisions(true)` at :453). With a single NYC nav agent (§8), every capsule selects the same navmesh.

The Lakeside 46-degree floor tweak (:490-491) is gated on `UHoverLakesideNavigationSystem`, so NYC keeps the 44.76-degree default, which is fine for streets.

### 6. Targeting, approach, promotion, stragglers

Direct chase stays on (`bDirectChaseMode` true, ZE_WaveGameModeSettings.h:236). The vendor `FindNearestPlayer` only accepts `AZE_PlayerCharacter` (ZE_ZombieAIController.cpp:185), so the real retarget is `SelectChaseTarget`.

The NYC version always returns the `AHoverPilot`, found via `TActorIterator`, so a hoverboard rider stays targeted and damageable. The bike is not spawned and the truck cannot be mounted. It returns `nullptr` while `IsDowned()` or the grace window is active. That is a hard dependency on the player slice; until it lands, the hook returns the pilot. The stomp knockdown (`IsKnockedDown()`, HoverPilot.h:131) deliberately does not grant grace, because it is the punishment. Perception is kept only for `SightRoar` and `UAISense_Damage`.

| Condition | Blackboard write |
|---|---|
| > 800 cm, no `LineOfSightTo` | `AttackSlotLocation` = reachable point within 500 cm of the player, offset by `LateralBias` perpendicular to the approach vector, refreshed every 3 s (zig-zag) |
| <= 800 cm or LOS | `AttackSlotLocation` = `ClaimSlot` (§7) |
| `SelectChaseTarget` null | clear `TargetEnemy`, release slot and token, hold at the queue radius. The Giant Kid (and the Stage 2 Feral) plays `Feast` in place instead of idling |
| Sprinter, <= 250 cm, in an inner sector | the AI tick takes a token, then one `LaunchCharacter(Forward * 400)` lunge (0.3 s, roar). The token is kept through the next swing and released at swing end, on a miss, or after 1.5 s. Kid crawlers never lunge this way; their lunge is the attack montage itself (§7) |

**Promotion and forced sprinters** are Section 3's director rules: every 10 s one Walker or Runner farther than 25 m moves up a tier, and after R3 the last three Standards are forced to Sprinter. This section adds only the exclusions for states it owns. Leg-hit crawlers and Kid crawlers are never promoted or forced, and neither are Brutes, fixed-speed roles or bosses.

**Stragglers**: the policy, thresholds and boss handling are Section 3's. Stage 1 uses relocation only: a teleport to the director's `Pick()`, with no destroy and no plugin patch. Destroy-and-requeue through the `NotifyZombieRemoved` plugin patch is a Stage 2 option and carries its deviation note in Section 3. On a relocation, this section releases the slot and token and clears `AttackEndTimer`. Health is untouched. The 0.4 s hide and the `SC_Zombie_Hiss` cue are presentation only (tuning placeholder).

### 7. Attack sectors and tokens

```cpp
UCLASS() class UHoverAttackSlotSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
  public:
    FVector ClaimSlot(AHoverNYCZombie *Z, APawn *Target);   // sticky; bearing of approach at claim time
    void ReleaseSlot(AHoverNYCZombie *Z);                   // death, retarget, relocation, grace
    bool TryAcquireAttackToken(AHoverNYCZombie *Z);         // 3, or 2 while IsHordeRound(); Boss role: own token
    void ReleaseAttackToken(AHoverNYCZombie *Z);
    bool IsInInnerRing(const AHoverNYCZombie *Z) const;
  private:
    static constexpr int32 InnerSectors = 8, QueueSectors = 12, MaxHeavyInner = 2;
    TWeakObjectPtr<AHoverNYCZombie> Inner[InnerSectors], Queue[QueueSectors];
    TSet<TWeakObjectPtr<AHoverNYCZombie>> Tokens;
    FVector Anchor;                                          // player loc, rewritten only after > 60 cm move
    float InnerRadius(const AHoverNYCZombie *Z) const;       // horizontal: max(AttackRange-30, PlayerR+CapsuleR+15), PlayerR live
};
```

How the sectors work:
- **Bearing sectors are world-fixed and shared across roles.** There is one claimant per sector, and each claimant stands at its own radius. Exclusivity removes the same-bearing radial overlap (a Brute at 180 behind a Standard at 120).
- Clearance checks (on-foot pilot, radius 32):

  | Pair | Spacing (cm) | Needed (cm) |
  |---|---|---|
  | Standards at 120, 45° sectors | 92 | 68 |
  | Kid crawlers at 100 | 77 | 46 |
  | Brute at 180, Standard at 120 | 127 | 89 |
  | Two Brutes at 180 | 138 | 110 |
  | Golem at 210, Brute at 180 | 150 | 125 |
  | Giant Kid at 230, golem | 168 | 130 |

  So every role takes exactly one sector.
- Heavies (Brute, Alpha, both bosses; Stage 2 Mythical) hold at most 2 inner sectors at once. At R33 (golem + 2 Brutes) and from R26 with 4 Brutes, the others wait on the queue ring.
- Each boss carries its own token outside the 3 (2 on horde rounds, banner "KID SWARM - stay moving", Section 3), so a boss swing never starves the adds and the adds never lock a boss out.
- The queue ring has 12 sectors at `QueueRingRadius` (Standard 260 gives a 135 cm spacing).
- Zombies beyond the 20 sectors (up to 24 concurrent) take a roaming point 400-600 cm out on their `LateralBias` side, refreshed every 3 s. They never idle. On horde rounds most Kids are in this band.
- Sector positions follow only the player's translation, with the anchor updated after more than 60 cm of movement (equal to `ObservedBlackboardValueTolerance`). Turning or aiming in place therefore never re-paths the ring.
- A queue zombie is promoted to the free inner sector nearest its bearing.

**Crawl-height in-range test.** The vendor service tests 3D centre-to-centre distance (ZE_BTService_CheckAttackRange.cpp: `FVector::Dist <= AttackRange`, +30 hysteresis). A crawler's centre is 23 cm up, against the pilot's 97 cm on foot (`InitCapsuleSize(32, 97)`, HoverPilot.cpp:85) and 142 cm mounted (`SetCapsuleSize(90, 142)`, :463). Mounted, the Kid's ring radius is max(100, 90+23+15) = 128, so the 3D distance is about 175 and the vendor test could never pass.

`UHoverBTService_AttackSlot::TickNode` therefore replaces the vendor test for every role with a cylinder test: `Dist2D <= InnerRadius(Z) + 30` (+30 hysteresis once in range) and `|dz| <= TargetHalfHeight + SelfHalfHeight`. For upright roles dz is under 65 cm, so the result matches the vendor test.

The vendor sweep (`OnAttackHitCheck`, ZE_ZombieCharacter.cpp:428-447) starts 40 cm forward of the actor, runs along `AttackRange` with radius `AttackSphereRadius`, and uses `ECC_Pawn`. For a crawler it starts at the centre height of 23 cm. With radius 45 it spans -22 to 68 cm, which overlaps the bottom of the pilot capsule both on foot and on the board. That is why Section 10 sets 130 / 45.

| Asset | Change |
|---|---|
| `BB_NYCZombie` | `TargetEnemy`, `LastKnownLocation`, `CanAttack`, `AttackCooldown`, `IsAttacking` exist. **`ZombieState` is absent from BB_Zombie**, so the vendor `SetValueAsEnum` at ZE_ZombieAIController.cpp:133 fails silently today. Add an Enum key `ZombieState` and a Vector key `AttackSlotLocation` |
| `BT_NYCZombie` | Blackboard set to `BB_NYCZombie`; `MoveTo(TargetEnemy)` replaced by `UHoverBTTask_MoveToSlot` on `AttackSlotLocation`; the service replaced by `UHoverBTService_AttackSlot`; the attack task replaced by `UHoverBTTask_ZombieAttack`; `BTTask_Wait.WaitTime` (an `FValueOrBBKey_Float`) bound to key `AttackCooldown`, which is a literal today; decorators unchanged. **Precondition**: dump BT_Zombie's node graph |
| `DA_NYC_*`, `DA_StoneGolem`, `DA_GiantKid` | `BehaviorTree` set to `BT_NYCZombie`; standard attack montages set to `AM_NYC_Attack_01/02`; every new montage carries a hand-placed `UZE_ZombieAnimNotify_AttackHit` (or `UHoverFistImpactNotify`) at its contact frame |

```cpp
UHoverBTTask_MoveToSlot::UHoverBTTask_MoveToSlot(const FObjectInitializer &OI) : Super(OI)
{   // bObserveBlackboardValue is UPROPERTY() only (BTTask_MoveTo.h:88-89)
    bObserveBlackboardValue = true;
    AcceptableRadius = 40.f;
    ObservedBlackboardValueTolerance = 60.f;
    bProjectGoalLocation = true;
    bReachTestIncludesAgentRadius = false;
    NodeName = "AFS: Move To Slot";
}
EBTNodeResult::Type UHoverBTTask_ZombieAttack::ExecuteTask(UBehaviorTreeComponent &C, uint8 *M)
{
    auto *Z = Cast<AHoverNYCZombie>(C.GetAIOwner()->GetPawn());
    if (Z && !Z->NeedsContactPose() && Subsystem->TryAcquireAttackToken(Z))
        return Super::ExecuteTask(C, M);
    // Latent failure: independent of the BT layout, no per-frame token spin.
    reinterpret_cast<FRetryMemory *>(M)->Remaining = FMath::FRandRange(.25f, .4f);
    return EBTNodeResult::InProgress;                 // TickTask -> FinishLatentTask(Failed)
}
```

`GetInstanceMemorySize()` returns `sizeof(FRetryMemory)`, `bNotifyTick` is true, and `AbortTask` returns Aborted. Today `ExecuteTask` returns Succeeded even when `PerformAttack` early-outs (ZE_BTTask_ZombieAttack.cpp:38-40 vs ZE_ZombieCharacter.cpp:351-352), which is the lockstep bug.

```cpp
void AHoverNYCZombie::PerformAttack(AActor *Target)
{
    AttackStartTime = GetWorld()->GetTimeSeconds();
    if (UAnimMontage *Special = PickReadySpecial(Target))   // slam, stomp, charge, pounce, dodge (§10); null otherwise
        PlaySpecial(Special);                               // sets bIsAttacking like the vendor path
    else
        Super::PerformAttack(Target);                       // random AttackMontages entry (cpp:378)
    if (!bIsAttacking) { Subsystem->ReleaseAttackToken(this); return; }
    SetCrowdState(ECrowdSimulationState::ObstacleOnly);   // CrowdFollowingComponent.h:33,84
    const float Duration = GetCurrentMontage() ? GetCurrentMontage()->GetPlayLength() : 1.f;
    GetWorldTimerManager().SetTimer(AttackEndTimer, FTimerDelegate::CreateWeakLambda(this, [this] {
        Subsystem->ReleaseAttackToken(this); SetCrowdState(ECrowdSimulationState::Enabled); }), Duration, false);
}   // ClearTimer(AttackEndTimer) on flinch-cancel, death, Rise and relocation
```

**Wind-up telegraph**: `AM_NYC_Attack_01/02` carry a `UHoverWindupNotifyState` over the first 0.5 s (arm raise, a grunt from the Pain set, and the flinch-cancel window). The vendor hit notify has to fire at 0.5 s or later. That is still to confirm; if it fires earlier, the DA plays the montage at 0.8x. The Kid's `AM_Kid_Lunge` is only 0.47 s, so its wind-up is 0.25 s of hiss with the hit notify at the landing frame. Kids do not flinch, so no cancel window is needed.

**Cooldown jitter**: after `Super::Tick`, write `Key_AttackCooldown = Stats.AttackCooldown * PhaseCooldownScale + CooldownJitter`, which overrides :396 in the same frame.

### 8. Crowd configuration

**Swap placement**: the possess-time hot-swap stays in `OnPossess` before `Super::OnPossess` (HoverCyberCity.cpp:238-256), which runs before `RunBehaviorTree` (ZE_ZombieAIController.cpp:83-85). It is the only verified placement, because the engine's Private AIController/Pawn sources are not shipped.
- Moving it to `PostInitializeComponents` is an experiment, gated on `ReviewNYCCrowd.py` showing the agents registered.
- The constructor route (an `FObjectInitializer` overload on the vendor controller; the pattern is at AIModule/Classes/DetourCrowdAIController.h:18) is Stage 2 cleanup.
- `bUseRVOAvoidance` is already false by default; validation asserts it.

**Per-agent settings** are applied in `AHoverNYCZombieAI::OnPossess` after Super, overriding the Cyber 3 / 500 / High at :250-254:
- Separation on, with the weight from the DA plus jitter.
- `CollisionQueryRange 3R+150`: Standard 252, Kid 219, Brute 315, Alpha 294, StoneGolem 360, Giant Kid 330; Stage 2 Mythical 285.
- Avoidance quality Medium, range multiplier 1.5, path optimization range 1000.
- No slowdown at goal; obstacle avoidance on; anticipate turns on.

**Crowd manager**: there is no `DefaultEngine.ini` section. A global section would change Cyber and Lakeside, which breaks Lakeside isolation.
- The engine defaults (`MaxAgents 50`, `MaxAgentRadius 100`, to confirm by a CDO dump) already cover 24 zombies plus two bosses with radii up to 70 cm.
- The only tuning wanted is `bResolveCollisions` and `SeparationDirClamp 0.3`. It goes through `UHoverNYCCrowdManager : UCrowdManager` (the config properties are protected, CrowdManager.h:279-331), which `UHoverNYCNavigationSystem` assigns as `CrowdManagerClass` (NavigationSystem.h:319). Because it is set per map, the other maps are unchanged.
- `UCrowdManager` is `MinimalAPI` (:178), so Build.ps1 confirms whether the subclass links. If it does not link, the defaults ship.
- On horde rounds the 48-Kid fallback cap stays under `MaxAgents 50`. Above it, Kids beyond the agent limit fall back to plain path following, which is acceptable for the roaming band.

**Navmesh decision: a single navmesh.** `UCrowdManager` simulates on one `MyNavData` (CrowdManager.h:282), so a separate Large-agent mesh would drop heavies out of crowd steering. `UHoverNYCNavigationSystem::PostInitProperties` (the Lakeside pattern, HoverCyberCity.cpp:40-52) registers one agent with `AgentRadius 55`, `AgentHeight 320`. Every role is a crowd agent on that mesh, and there are no NavAgentProps writes. Section 10's "accept the 210 cm agent" note describes the Cyber/Lakeside agent (:51) and is the fallback only if `UHoverNYCNavigationSystem` is dropped. The trade-offs:
- Standards lose gaps under 110 cm, which is acceptable on streets.
- The golem's 70 cm and the Giant Kid's 60 cm radii rely on their capsules for the extra clearance.
- `ReviewNYCCrowd.py` verifies that Brutes and both bosses path through all 6 doors.

**Level handoff**: set `L_NYC_Survival` World Settings `NavigationSystemConfig.NavigationSystemClass = UHoverNYCNavigationSystem` (the same mechanism as L_Showcase), and extend HoverAuthoring.cpp:200 with `|| World->GetName().Contains(TEXT("L_NYC_Survival"))`.

### 9. Hit reactions and gore

The vendor plays a full-body `AM_Hit` (the DA's `HitReactionMontages`) at most once per 0.8 s, and only when `!bIsAttacking && !bIsDead` (ZE_ZombieCharacter.cpp:243-251). The headshot multiplier applies only for an `AZE_WeaponBase` causer (:143-156). `LastHitTime` is protected (ZE_ZombieCharacter.h:97): setting it to `Now` suppresses the vendor flinch and `Now - 1` forces it. The work happens in `ModifyIncomingDamage`, which runs before the vendor Super and records `LastHitBone` and the causer. Hit montages per enemy:
- Kid crawlers use ZAP `Taking_Damage_A/B` (0.67 s).
- The Giant Kid uses Feral `HitReact_01-04` (0.4 s).
- The golem uses `AM_Golem_Hit_1-3` only as phase staggers.

| Trigger | Reaction |
|---|---|
| any hit | flesh-impact cue `SC_Hit`, at most one per 0.1 s per zombie, with a pitched-up variant for headshots (the golem plays `S_Entity_Hit_A-C`, a stone cue, instead); a blood decal traced 8 m behind the impact along the shot (max 24 live, 20 s fade; NS1_Blood decal material if present, else an owned `M_NYC_BloodDecal`, to confirm; none for the golem); the existing BloodBurst (HoverCyberCity.cpp:567-568), replaced by `VFX_Shockwave_01_White_Small_1s` dust on the golem |
| `Damage >= 10% MaxHealth`, `bFlinchOnHit` | physics flinch, limited to `spine_02/03`, `neck_01`, `head`, `upperarm_l/r`, `thigh_l/r` (skipping None, pelvis and root): `SetAllBodiesBelowSimulatePhysics`, blend 0.35, `AddImpulse(Dir * 200, Bone, bVelChange = true)`, restored after 0.18 s; pain vocal at most every 0.6 s |
| same, and 0.35 s since the last montage flinch | force `AM_Hit` when not attacking. While attacking, only inside `WindupSeconds` (Standard 0.5, smash 0.8, stomp 1.2): play `AM_Hit`, clear `bIsAttacking` and `Key_IsAttacking`, release the token, `ClearTimer(AttackEndTimer)` |
| headshot kill, `bCanBeDismembered` | gib: `HideBoneByName(head)`, a head gib from the pool, a second BloodBurst (`Blood` is now protected). Living zombies never lose their head. The Giant Kid gibs only on its final death; the golem never gibs (its physics asset ragdolls the death pose) |
| leg hit for >= 25% MaxHealth, HP remains, `bCanCrawl`, fewer than 4 leg-hit crawlers | crawler: hide the thigh, leg gib, half-height 45, `SpeedTier 120`, `AttackRange 110`, `bCrawling` on `ABP_NYCZombie` (the same ZAP belly-crawl clips the Kid uses). Kid crawlers do not count toward the 4 |
| **Giant Kid Rise** (`SecondLifeFraction .3`) | when HP first crosses 30% MaxHealth, `Rise` (`Reanimate`, 2.8 s) plays and all damage is ignored for 2.8 s. No HP is added; the Rise uses the same pool. If the crossing hit would be lethal, `ModifyIncomingDamage` clamps it to leave 1 HP, and only on that first crossing. Slot, token and `AttackEndTimer` are released |
| armor pool > 0 (Stage 2: Pirate, BogZombie, Riot) | body damage goes to the pool (explosives x0.5); flinch only on headshots. Riot also suppresses the head multiplier and, when the plate breaks, hides `SKM_Armor_001`, plays a clang and a 0.6 s stagger. Pirate/BogZombie play `S_Monster_Hit_A-C` on pool break |
| Insta-Kill (`ModifyIncomingDamage`) | Standard (including the Lakeside skins)/Kid (S2: Lakeside specials, Riot): `Damage = max(Damage, Health)`; Brute and Alpha Brute x4 (the Alpha is a Brute; S2 Mythical x4); StoneGolem/Giant Kid x2. The Giant Kid's first lethal hit is still clamped and the Rise still triggers, so it has to be killed twice |
| `UHoverNukeDamageType` | Standard/Lakeside skins/Kid (S2: Lakeside specials, Riot) die with no per-kill award (the economy pays a flat 400); Brute/Alpha/bosses (S2 Mythical) take `0.25 * MaxHealth` |
| kill (`OnKilledBy`) | release slot and token; `Mode->AwardKill(this, Kind)` with Kind = head 115 / `AHoverMeleeWeapon` causer 105 / else `KillPoints`; `Mode->OnSpecialKilled(this)`, where the economy keeps the per-round Brute counter (1st/3rd Max Ammo, 2nd/4th Max Health; the Alpha counts as a Brute) and handles the boss Max Ammo and kill cam. For the Giant Kid this fires on the final death only: the 30% Rise is a threshold trigger, not a death, and awards nothing |

At the stretch bands, body shots fall under the 10% gate: R24 PaP II 140/1,800 = 7.8%, and R30 PaP III 280/3,500 = 8%. Those hits get the cue, decal and BloodBurst only. Headshots stay above the gate through R30 (15.5% and 16%).

The vendor death is kept (`AM_Death`, ragdoll, 15 s corpse). Kids start with Feral `Death_01/02` and then ragdoll; the golem plays `AM_Golem_Death_1-3` and then ragdolls. The gib pool holds at most 12 gibs with an 8 s lifespan and no pawn collision.

### 10. Boss and special mechanics

**Stomp gate**: at :509 the gate becomes `GetRole() != Brute && !(Def && Def->bUsesStomp)`. Cyber `DA_Brute` needs no edit. Brute, Alpha, StoneGolem and Giant Kid set `bUsesStomp`. Their slam/stomp montages carry `UHoverBruteStompNotify` at the landing frame, so `StompImpact` runs the existing floor trace, LOS test, `ShowStompPulse` and `ApplyStompKnockdown` (HoverCyberCity.cpp:507-539; 2.1 s knockdown).

**Stomp damage**: when `StompDamageMultiplier > 0`, `StompImpact` skips `OnAttackHitCheck` (:521) and instead applies `ApplyDamage(Pilot, 30 * StompDamageMultiplier)` inside `StompRadius`, using the existing LOS test. The pilot then applies the frozen band. Base values are 60 for Brute, Alpha and Giant Kid and 75 for the golem's slam. With the band, the R13 golem slam is 30 x 2.5 x 1.667 = 125 (R11-30 band). The Cyber default of 0 keeps the vendor sweep.

**Stomp timing**:
- `StompCooldown` is a special timer: golem 4 s, Giant Kid and Alpha 2.5 s.
- `GetStompInterval()` returns the DA's `StompInterval` as the minimum re-arm.
- `UHoverStompTelegraphNotify` fires 0.6 s before the landing and draws a ground-crack decal plus `VFX_Shockwave_02_White_Big_1s` scaled to the radius.
- On `AM_Brute_Stomp` the landing comes at 1.2 s. On `AM_Golem_Slam` and `AM_GiantKid_Strong_03` the landing frame is set in the viewport pass, because neither source clip carries a hit or stomp notify.
- `ApplyStompKnockdown` (HoverPilot.cpp:1706-1739) only knocks down an on-foot pilot; a mounted rider takes the damage only.

**Fists**: `UHoverFistImpactNotify` calls the vendor hit check (`Super::Notify`) and spawns `VFX_Shockwave_01_White_Small_1s` and an `S_Entity_Hit` cue at a configurable bone (`hand_r`/`hand_l`). The golem's 90 cm `AttackSphereRadius` makes the bare arm read as the hitbox; `weapon_lSocket`/`weapon_rSocket` stay empty.

**Phases**: phase evaluation runs in `TakeDamage` after Super, and `Duration` expiry clears `PhaseSpeed`. Specials are timer states in `AHoverNYCZombie` (`PickReadySpecial`, §7). Each has its own cooldown and is chosen before the random vendor montage.
- `DA_NYC_Brute` has one phase `{0.3, Duration 8, SpeedOverride 420}`.
- `DA_NYC_AlphaBrute` has one permanent phase `{0.5, bEnrage, SpeedOverride 650}`. From 50% HP it sprints at 650, and every stomp queues a second one (a 2-stomp chain).
- The Alpha spawns only when Section 3 swaps it in for the last Brute of a heavy round (`bAlphaBruteElite`, off by default).

| Boss | Phases | Telegraph | Adds / arena |
|---|---|---|---|
| **StoneGolem** (S1; R13, R27, R33, then per Section 3, e.g. R46) | Intro: `AM_Golem_Intro` (`turn180` or `idle1`, at speed 0) plus roar; `turn180` is used only for the intro. P1 (100-66%): `Light_A`/`Light_B` fists (plus `Heavy_A` only if the viewport pass keeps it); `Slam` on a 4 s cooldown when the player is inside 600 cm (2.1 s knockdown on foot). P2 at 0.66 (`bUnlockSpecial`, stagger 1.8 s on `AM_Golem_Hit_2`): `dodge` sidestep (1.23 s) when hit from more than 8 m, 8 s cooldown (tuning placeholder). P3 at 0.33 (`bEnrage`, `CooldownScale .75`, `SC_Entity_Roar`, 1 s red HUD pulse): every slam chains a second one (tuning placeholder). **Stage 1 has no charge, no armor break-off and no weak-point window** (single unarmed mesh). The armor part meshes plus `DetachPartComponent`/`WeakPointBone` are the Stage 2 route | slam: ring 0.6 s before landing, 600 cm; fists: `UHoverWindupNotifyState` over each clip's lift (attack3 is the shortest at 1.73 s) | R27 and later two-boss rounds: the Giant Kid enters at golem <= 50% (Section 3). R33: two Brutes as additive boss adds. Its AI uses a `UNavigationQueryFilter` that excludes `UHoverNavArea_Underpass`. If the player stays in the Underpass more than 5 s, the emergers spawn a 4-pack every 5 s and the golem roars at the entrance, so the room is never boss-proof |
| **Giant Kid** (S1; R19, R27, R39 x2, then per Section 3) | Intro: `AM_GiantKid_Rise` (`Reanimate`, 2.8 s) at the spawn point, then Etherion `Roar` (3.8 s) as the round telegraph. P1: `Strong_01/02` in melee. `Strong_03` stomp (x2.0 in 500 cm, 2.1 s knockdown) on a 2.5 s cooldown. `Pounce` (`LeapForward_Short`) at 2-4 m, token-gated. `Charge` (`LeapForward_Full`, 1.2 s) when the player is 8-18 m away in LOS, 10 s cooldown: `LaunchCharacter(Forward * 900 + Up * 250)` at take-off, then a contact sweep at capsule + 60 on landing dealing `30 * 2.0`, no knockdown (pounce and charge values are tuning placeholders). P2 at 0.5 (`bEnrage`, SpeedOverride 650): every stomp chains a second one, and the charge cooldown drops to 6 s (tuning placeholder). **Rise (second life)**: at the first 30% crossing, a 2.8 s invulnerable `Rise` with no HP added (§9). No-target idle: `Feast` | charge: 0.4 s crouch in the clip plus `S_Entity_DistantRoar` stinger; stomp ring 0.6 s before landing | R39: two Giant Kids, both heavy-slot claimants, so no other heavy takes an inner sector. It uses the same Underpass filter and emerger rule as the golem |

**Stage 2 specials** (the Lakeside meshes' special builds; in Stage 1 these meshes are plain Standard skins)

| Special | Mechanic |
|---|---|
| Feral (Horror) | token-gated `LeapForward_Short` pounce at <= 300 cm instead of the sprinter lunge; on the first body-shot death (not a headshot) it plays `Reanimate` and returns at 25% HP, once; `Feast` when there is no target |
| Spore (Plant) | spawns on `Emerger` points (Burst / `Laying_Idle`); every 6 s, when the player is within 250 cm, a 0.6 s `SC_Zombie_Inhale` telegraph then an `Easy_Shockwaves` ring dealing `30 * 1.0` with the stomp LOS test and no knockdown; the same burst on death |
| Elite (Mythical) | `LeapForward_Full` charge (650 for 1.2 s) at 8-15 m, 12 s cooldown, preceded by `Idle_Roar_01`; `StrongAttack_01-03` as its attack set; active cap 1 (rounds slice) |

### 11. Barricade windows

**Not in Stage 1 or 2.** NYC streets have no interiors on the navmesh, and the vendor sweep (ZE_ZombieCharacter.cpp:435-448) cannot reach through boards. Adding them later would cost an `AHoverBarricade` (6 planks, 10 points per plank), a tear branch in the BT, and a behind-window spawner: about 350 lines, with no new animation.

### 12. VALIDATION

- **Preconditions**:
  - Dump BT_Zombie's node graph and read `ABP_ZombieMaster`'s slot name before duplicating it.
  - `ReviewNYCCrowd.py` asserts that `BB_NYCZombie` has `ZombieState` and `AttackSlotLocation`.
  - Dump the `UCrowdManager` CDO via UnrealEditor-Cmd Python, and cross-check the `DA_Kid`/`DA_Brute` Stats against Section 10's decoded values.
  - Confirm the `SK_Kid`/`SK_Brute`/`SK_Standard01` slot materials resolve to `M_<Name>_0` (Section 10 open issue); otherwise the crawler, the Giant Kid and the Brute render with the default material.
  - Play back the clips listed in §2 on their target meshes, including the golem five-clip pass, and record which golem attacks are kept.
- **Build**:
  - Run clang-format on `HoverNYCZombie.h/.cpp`, `HoverCyberVariants.h`, `HoverCyberCity.h/.cpp` and `HoverPilot.cpp`.
  - Run `Scripts/Build.ps1`. The UHT pass over `HoverCyberVariants.h` must pass (new enums, `TMap` of soft montages, the `SwarmCount` ClampMax 80 meta).
  - Record whether `UHoverNYCCrowdManager` links.
- **`ReviewNYCCrowd.py`**: offscreen, never concurrent. Covers R1, R5, R8, R13, R19, R21, R26, R27, R30, R45 and R46 via `NYCStartAtWave N`. It logs and checks:
  - Tokens never above 3 (2 on horde rounds), with each boss holding at most its own token.
  - Heavies holding no more than 2 inner sectors.
  - Capsule-overlap pairs in under 3% of samples.
  - Zero re-paths while the test pawn turns 90° in place.
  - The SpeedTier histogram (rolled in Section 3): R1 100% Walker, R5 about 44%, R8 about 11% Walker, R9 0% Walker and about 2.8% Sprinter, R13 about 47% Sprinter, R18 100%.
  - Montage flinches at most 2.86/s per zombie.
  - Zero relocations on the main corridor, and no straggler destroyed in Stage 1 (relocation only).
  - Brutes and both bosses reaching all 6 doors.
  - Kid crawlers: capsule half-height 23, the mesh bottom on the capsule bottom, `CanAttack` set and hits landing against both the on-foot and the mounted pilot, crawl play rate between 1 and 4.
  - Stomp damage of 60 at R8, and a golem slam of 125 at R13 (30 x 2.5 x 1.667, R11-30 band).
  - Insta-Kill on a Brute and on an Alpha Brute giving x4, not a one-shot. On the Giant Kid, Insta-Kill clamps the first lethal hit to 1 HP and triggers the Rise.
  - An R10 zombie still hitting for 30 in R11.
  - `bUseRVOAvoidance` false.
  - Boss phase timestamps and HP. The golem fight has no charge, detach or weak-point event. The R27 Giant Kid enters at golem <= 50%. The Giant Kid Rise fires once, at the first 30% crossing, with HP unchanged across the 2.8 s and no damage taken during it. Points and `OnSpecialKilled` fire only at the final death. R45 runs as a horde round and the boss round runs at R46.
- **`VerifyNYCSurvival.py`** asserts the DA rows above, including:
  - MaximumRunSpeed, with the golem at 420;
  - StompRadius/StompDamageMultiplier/StompCooldown (golem 600/2.5/4, Giant Kid and Alpha 500/2.0/2.5);
  - `CapsuleHalfHeight` 23 and `KillPoints` 90 for the Kid;
  - golem MaxHealth 1,500, MeleeDamage 75, Walk/Run 240/420;
  - Giant Kid MaxHealth 1,200, MeleeDamage 90, `SecondLifeFraction` .3;
  - Alpha 1,200 HP, 250 points, Role `Brute`;
  - no health factor field on any definition;
  - golem `BossPhases` without `DetachPartComponent`/`WeakPointBone` and no `Charge` entry;
  - empty golem weapon sockets;
  - index 3 still spawning zero zombies.

  The boss and horde schedule (R13/R19/R27, then 33 + 6k, with R45 moved to R46) is asserted in Section 3's VALIDATION. `VerifyNYCExploration.py` is unchanged.
- **Regression**: re-run `VerifyCyberWaves.py` (shared skeletons and their new registrations, hooks, stomp gate, the unchanged Cyber `DA_Kid`, `DA_CyberEncounters` 12/2/5/10) and the Lakeside verification (shared classes, untouched Lakeside DAs). Evidence goes to `D:/AFS_Comparisons/NYCSurvival_<date>/`, including frame times at 24 concurrent zombies, in the 70-Kid horde and at R27 with both bosses.

### 13. Owner amendments for this slice

| File | Line to add |
|---|---|
| AGENTS.md (after L26-28) | "NYC - Survival zombies use owned AI assets under /Game/HoverPrototype/NYC/AI and definitions under /Game/HoverPrototype/NYC/Zombies (crawler DA_NYC_Kid; bosses: Variants/Golem/DA_StoneGolem, Variants/Kid/DA_GiantKid); ZESP Zombie_001 BT/BB/ABP and Cyber/Lakeside definitions, including Cyber DA_Kid, are not edited." |
| AGENTS.md | "Owner skeletons list the ZESP SK_Mannequin and, for NYC, the ZAP-UE4 / Feral / Etherion skeletons named in the roster mapping as compatible (additive; VerifyCyberWaves.py evidence). /Game/StoneGolem is source art. NYC crowd and nav settings are per-map (UHoverNYCNavigationSystem); DefaultEngine.ini has no CrowdManager section." |
| README.md level table | roster: Street Zombie (walker/runner/sprinter; Standard01-04 plus the five Lakeside skins), Kid crawler (horde every 5 from R5), Brute, optional Alpha Brute elite; bosses StoneGolem (R13) and Giant Kid (R19), both at R27, then every 6 from R33; Stage 2 Riot, light/heavy armored, Feral, Spore, Mythical elite |
| Docs/CONTROLS.txt | "Zombies surround on 8 sectors, at most 3 swing at once"; "Headshot kills gib; leg hits can create crawlers"; "Stomp and slam rings appear 0.6 s before impact"; "The Giant Kid gets back up once" |
| Docs/NYC_SURVIVAL_<date>.txt | this section's tables and VALIDATION results, plain text |

**Open for the owner**:
- Golem base HP 1,000 (10x) after playtest. This is the Stage 1 TTK tuning risk in §4 and is not decided.
- The Alpha capsule overhang.
- Which golem attack clips survive the viewport pass.
- One name for the emerger spawn tag: `Emerger` in Section 3, proposed `Ground` in Section 10.
- Etherion cue licensing (Section 10).

## 5. Gunplay, weapon VFX, haptics and hit feedback overhaul

### Scope and priorities

This section turns the verified gunplay diagnosis into an implementation spec for `L_NYC_Survival`. The primary tuning target is the **third-person 430 cm review camera**, because the camera section makes it the default view in `AHoverNYCSurvivalGameMode`. First person and mounted-glider fire are secondary targets, and both are validated. The feel targets are owned by AFS. BO7 publishes no gunplay tables, so the only BO conventions borrowed are the readable ones: a diagonal hit marker, a distinct headshot or kill confirm, a PaP tracer identity per tier, and no firing while sprinting.

The C++ presentation changes (shake, recoil model, haptics, hit marker, tracer, light, sound, penetration loop) live in the shared AFS layer, so Cyber City, Lakeside and the PostApo no-bridge path also get the improved feel. The owner authorised that. **Balance values are NYC-only:** they are authored on new duplicates under `/Game/HoverPrototype/NYC/Weapons/`. The existing `DA_AFS_Ballista.._5` receive presentation fields only (see the owner amendments). This section touches no vendor plugin file. The flinch rule belongs to the crowding/AI section. Spine numbers are referenced here and never changed.

| Pri | Item | Why it is in that tier |
|---|---|---|
| P0 | Auto-fire with FireRate 8 and a cadence cap, rifle tick ctor, camera shake, real recoil, held bloom with ADS, haptics, hit marker and hit sounds, damage numbers, gunshot 1.0 with tail, tracer and the per-tier tracer table, muzzle light, penetration, auto-reload, sprint-fire gate, third-person fire reaction | Without these the spine's TTK tables do not exist, and shooting still reads as "super bad" |
| P1 | Flesh sound and wall splatter, kill punctuation, shell eject fix, reload feel, melee lunge, incoming-damage feedback, frag and katana presentation, intensity sliders | Makes damage legible. Depends on the P0 hooks |
| P2 | FP arms fire montage, mechanical and distant sound layers, crosshair polish, Heavy Ballista family, Stage 2 marker hooks | Cosmetic or Stage 2 |

This section does not fix spawning or bunching; those belong to the spawn and crowding sections. Its only contribution to bunching is readability: penetration rewards lined-up zombies, and blood shows which body in a cluster was hit.

### Root causes being fixed (verified)

| # | Fact in code | Consequence |
|---|---|---|
| 1 | `AHoverCyberRifle::PlayFireAnimation` (`HoverCombatBridge.cpp:78-82`) only stamps `LastFireAnimTime`. The vendor `SpawnMuzzleFlash/PlayFireSound/TriggerFireCameraShake` path never runs | `BP_M16_FireShake` is never played |
| 2 | `UpdateCombatState` (`ZE_WeaponBase.cpp:1504-1537`) integrates `CurrentRecoil * DeltaSeconds` (:1525) and skips spread recovery while `bIsFiring` (:1532). In addition, the vendor ctor ticks only `#if WITH_EDITOR` (:35-40) | **The felt causes in editor and `-game` runs** are the ~0.03 deg recoil and spread that never recovers while the trigger is held. The missing tick only matters in a packaged build (correctness fix) |
| 3 | `HoverPilot.cpp:1513` `PlayDynamicForceFeedback(.18f, .06f, ...)`, small motors only, no hit or kill rumble | Haptics are barely felt |
| 4 | `AHoverHUD::DrawHUD` (`HoverPilot.cpp:1855-1861`) draws a static white cross. When aiming it draws a red 3x3 dot | No hit confirmation |
| 5 | `SetTrigger` is rising-edge (`HoverCombatBridge.cpp:289-300`). `StartFire` arms the repeat timer only when `bAutomatic` (`ZE_WeaponBase.cpp:610-646`), and every tier leaves it false. No cadence cap exists for re-presses | One shot per press, and the tap rate is unbounded |
| 6 | `HoverShotVisual.cpp:31-38`: scale (.55,.014,.014), duration .06-.09 s, and `User.Color` is forced orange. :57 rewrites the scale every Tick. The muzzle flash dies at .09 s and has no light. The gunshot plays at .60 volume (:1511) | A hair-thin 60 ms tracer, a dim flash and a quiet gun |
| 7 | `HoverPilot.cpp:1484` skips impact FX for zombies. Zombie hits get only `HoverEffects::BloodBurst` | Zombie hits are silent |
| 8 | A single trace (`:1469`), and `ProcessHit` takes no damage parameter (`ZE_WeaponBase.cpp:1265-1289`) | No penetration |
| 9 | Death plays `AM_Death` and then a timed ragdoll (`ZE_ZombieCharacter.cpp:301-332`) | No kill punctuation |
| 10 | Damage numbers accumulate over a sliding 0.8 s window (`ZE_ZombieCharacter.cpp:166-180`) | Per-shot numbers merge into one |

The headshot check compares `FName`s (case-insensitive) at `ZE_ZombieCharacter.cpp:145`, and it requires `DamageCauser` to be an `AZE_WeaponBase` (:148). Every rifle damage call therefore passes `SourceWeapon` as the causer.

### Per-tier data asset values

The AFS-owned duplicates live in `/Game/HoverPrototype/NYC/Weapons/` and are made with `duplicate_asset`; the vendor ZESP DAs are never edited. **Naming change for the spine owner:** the PaP chain becomes `DA_NYC_Ballista → _2 → _3 → _4`, replacing `DA_AFS_Ballista.._4`. The spine's numbers are unchanged. The Ballista family uses a new `DA_AMMO_NYC_Ballista` with a unique `AmmoTypeId`. It is shared across the four tiers only, so the Stage 2 M16 (`DA_AMMO_M16`) can never refill the Ballista pool. The economy and armory section must match this. Values marked * are this section's proposal.

| Field | DA_NYC_Ballista (PaP 0) | _2 (PaP I) | _3 (PaP II) | _4 (PaP III) | DA_NYC_HeavyBallista (Stage 2, PaP 0) |
|---|---|---|---|---|---|
| CombatStats.Damage | 35 | 70 | 140 | 280 | 90 (_2.._4 = 180/360/720) |
| HeadshotMultiplier | 2.0 | 2.0 | 2.0 | 2.0 | 2.5 |
| Range* | 15000 | 15000 | 15000 | 15000 | 15000 |
| BaseSpread / SpreadPerShot / MaxSpread / SpreadRecovery | 0.5 / 0.35 / 3.0 / 12 | same | same | same | 0.3 / 0.6 / 2.0 / 10 |
| RecoilKick (pitch, yaw) / RecoilRecovery (deg/s, read by AFS) | 0.35 / 0.15 / 10 | same | same | same | 1.2 / 0.3 / 8 |
| ReloadTime | 1.5 | 1.5 | 1.3 | 1.2 | 2.2 |
| FireRate / automatic | 8 / true | 8 / true | 8 / true | 8 / true | 4 / false (capped by AFS) |
| MagazineSize / MaxReserveAmmo | 30 / 270 | 30 / 360 | 30 / 450 | 30 / 540 | 12 / 72 |
| FireCameraShake | UHoverFireShake | same | same | same | same |
| `muzzle_flash_fx.scale` (not `muzzle_flash_scale`, which FireShot does not read) | 1.0 | 1.1 | 1.2 | 1.3 | 1.4 |
| FireSound | `A_Cyberpunk_Rifle1_004` | same | same | same | same, pitch .85 |
| BulletShellImpulse / BulletShellDirection* | 320 / (1, 0, .25), lateral local X because the barrel is +Y; confirm the sign in capture | same | same | same | same |

The Sidearm family is `DA_NYC_Sidearm` and `_2`, duplicated from `DA_Weapon_Pistol_001` and keeping `SW_Shot`. The Stage 2 M16 family is `DA_NYC_M16` and `_2.._4`, duplicated from `DA_Weapon_Rifle_001-004`. The zombie DAs `DA_NYC_*` come from the roster section; this section only requires `Stats.DamageAccumulationWindow = 0.1` on them (see P0-5).

AFS tier table. `FHoverRifleTier` is defined at global scope in `HoverCombatBridge.h`, and the TMap lives in the cpp. Pierce falloff\* compounds at 0.6 per body (100 / 60 / 36 %). The spine fixes only PaP II's 60 %, and the spine's ammo ledger counts no penetration multi-kills, so it stays conservative.

| Key | PaP | Pierce | Tracer | Color override | Shake | Pitch |
|---|---|---|---|---|---|---|
| `DA_NYC_Ballista` | 0 | 0 | `NS_ArrowTrail_Basic_02` | User.Color (1,.65,.25) | 1.00 | 1.00 |
| `DA_NYC_Ballista_2` | I | 0 | `NS_ArrowTrail_Fire` | none | 1.05 | .97 |
| `DA_NYC_Ballista_3` | II | 1 | `NS_ArrowTrail_Ice` | none | 1.10 | .94 |
| `DA_NYC_Ballista_4` | III | 2* | `NS_ArrowTrail_Holy`, plus `NS_Lightning_Damage_Land_Small` on headshot kills | none | 1.20 | .90 |
| `DA_NYC_HeavyBallista` _1.._4 | 0-III | 3* | `NS_ArrowTrail_Magic` | User.ColorA/ColorB | 1.60 | .85 |
| `DA_NYC_Sidearm` / `_2` | 0 / I | 0 | `NS_ArrowTrail_Basic_02` | (.9,.9,1) | .70 | 1.10 |
| `DA_NYC_M16` _1.._4 | 0-III | 0 / 0 / 1 / 2 | Basic_02 / Fire / Ice / Holy | as Ballista | .90 | 1.0 (SW_Shot) |
| `DA_AFS_Ballista` .. `_5` (Cyber/Lakeside) | n/a | 0 | Basic_02 / Fire / Ice / Holy / Magic | as above | 1.0-1.6 | 1.0-.85 |

### TTK targets (spine convention: seconds = shots x 0.125)

The spine's convention is kept on purpose. The first automatic shot actually fires at t = 0, so true TTK is (shots − 1) x 0.125. For example, R30 body is 1.5 s, not 1.6 s.

| Round | H(r) | Tier | Body / head shots | Body / head seconds | Mag reloads (body) |
|---|---|---|---|---|---|
| R1 | 100 | PaP 0 | 3 / 2 | 0.38 / 0.25 | 0 |
| R5 | 200 | PaP 0 | 6 / 3 | 0.75 / 0.38 | 0 |
| R8 | 275 | PaP 0, then buy I | 8 / 4 | 1.0 / 0.5 | 0 |
| R10 / R15 | 325 / 550 | PaP I | 5/3, 8/4 | 0.63/0.38, 1.0/0.5 | 0 |
| R16 / R20 | 640 / 1,000 | PaP II | 5/3, 8/4 | 0.63/0.38, 1.0/0.5 | 0 |
| R25 / R30 | 2,000 / 3,500 | PaP III | 8/4, 13/7 | 1.0/0.5, 1.63/0.88 | 0 |
| Brute R8 | 1,650 | PaP 0 | 48 / 24 | 6.0 / 3.0 | 1 |
| Brute R12 | 2,490 | PaP I | 36 / 18 | 4.5 / 2.25 | 1 |
| Alpha Brute R13 (Stage 1 boss) | 5,520 | PaP I | 79 / 40 | 9.9 / 5.0 | 2 (1 on heads) |
| Alpha Brute R19 | 10,920 | PaP II | 78 / 39 | 9.75 / 4.9 | 2 (1 on heads) |
| Alpha Brute R27 | 31,200 | PaP III | 112 / 56 | 14.0 / 7.0 | 3 (1 on heads) |

Every presentation value keys off the definition pointer the rifle currently holds. The PaP DA swap belongs to the economy section, and it changes the feel immediately.

### P0-1 Rifle: tick, cadence cap, bloom, ADS (HoverCombatBridge.h/.cpp)

```cpp
// HoverCombatBridge.h, global scope above AHoverCyberRifle
struct FHoverRifleTier
{
    int32 PaP = 0, Pierce = 0; float PierceScale = .6f; const TCHAR *Tracer = nullptr;
    bool bColor = false; FLinearColor Color = FLinearColor(1.f, .65f, .25f); float ShakeScale = 1.f, Pitch = 1.f;
};
// AHoverCyberRifle additions
public:
    AHoverCyberRifle();                                   // PrimaryActorTick.bCanEverTick = true
    virtual void Tick(float DT) override;
    virtual void StartFire() override;
    float GetEffectiveSpreadDegrees() const;              // CurrentSpread * Lerp(1, .35, Pilot->WeaponAimAlpha)
    float GetEffectiveFireRate() const { return (WeaponDefinition ? WeaponDefinition->FireRate : 8.f) * FireRateScale; }
    float FireRateScale = 1.f;                            // Double Tap 1.2, written by the economy section
    const FHoverRifleTier &GetTier() const;
    static const FHoverRifleTier &DefaultTier();
protected:
    virtual void HandleFire() override;
private:
    float LastShotTime = -10.f; FTimerHandle BufferedShot;

// HoverCombatBridge.cpp
void AHoverCyberRifle::Tick(float DT)
{
    CurrentRecoil = TargetRecoil = FRotator::ZeroRotator;   // BEFORE Super: HandleFire's kick must not leak one tick
    Super::Tick(DT);                                       // vendor release recovery: FInterpTo at SpreadRecovery 12
    if (bIsFiring && WeaponDefinition)                     // held bloom: linear SpreadRecovery / 6 = 2.0 deg/s
        CurrentSpread = FMath::FInterpConstantTo(CurrentSpread, WeaponDefinition->CombatStats.BaseSpread, DT,
                                                 WeaponDefinition->CombatStats.SpreadRecovery / 6.f);
}
void AHoverCyberRifle::StartFire()
{
    if (bIsFiring || bIsReloading || !WeaponDefinition) return;
    if (WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0) { Reload(); return; }
    const float Interval = 1.f / FMath::Max(.1f, GetEffectiveFireRate());
    const float Wait = LastShotTime + Interval - GetWorld()->GetTimeSeconds();
    auto &Timers = GetWorldTimerManager();
    bIsFiring = true;
    if (WeaponDefinition->bAutomatic)
    {
        if (Wait <= 0.f) HandleFire();
        Timers.SetTimer(FireTimerHandle, this, &AHoverCyberRifle::HandleFire, Interval, true, FMath::Max(Wait, Interval));
    }
    else if (Wait <= 0.f) HandleFire();
    else Timers.SetTimer(BufferedShot, this, &AHoverCyberRifle::HandleFire, Wait, false);  // buffered semi press
}
void AHoverCyberRifle::HandleFire()
{
    if (!WeaponDefinition->bUsesAmmo || CurrentClipAmmo > 0) LastShotTime = GetWorld()->GetTimeSeconds();
    Super::HandleFire();                                   // ammo, PerformLineTrace, spread +0.35, StopFire at 0
}
const FHoverRifleTier &AHoverCyberRifle::GetTier() const
{
    const FName Key = WeaponDefinition ? WeaponDefinition->GetFName() : NAME_None;
    if (const auto *Found = RifleTiers().Find(Key)) return *Found;
    static TSet<FName> Warned;
    if (!Warned.Contains(Key)) { Warned.Add(Key); UE_LOG(LogTemp, Warning, TEXT("HOVER_RIFLE_TIER missing %s"), *Key.ToString()); }
    return DefaultTier();
}
```

`PerformLineTrace` passes `GetEffectiveSpreadDegrees()` to `FireShot`. The cadence cap also closes the "tap faster than 8/s" hole on automatic weapons, and it enforces the Sidearm's 6/s and the Heavy's 4/s. Double Tap goes through `FireRateScale` because the vendor timer reads the shared DA.

**Bloom (deviation flagged):** applied literally, the spine's "SpreadRecovery 12/s also while held" erases bloom. Exponential recovery at 12 settles at about 0.58 deg, and linear recovery at 12 deg/s returns to base between every shot. This section keeps 12 as the release-recovery DA value and recovers at 2.0 deg/s linear while held, which gives +0.1 deg net per shot. Spread used on shot n is 0.5 + 0.1(n−1): shot 1 = 0.5, shot 10 = 1.4, and MaxSpread 3.0 is reached at shot 26. Release recovery brings it to about 0.6 at +0.25 s and 0.5 at +0.5 s. ADS multiplies by 0.35.

**Auto-reload** (`UHoverCombatBridge::TickComponent`): `if (bTriggerHeld && Weapon && Weapon->GetCurrentClipAmmo() == 0 && !Weapon->IsReloading() && Weapon->GetReserveAmmo() > 0) Weapon->Reload();`. The vendor `StopFire`s at 0 ammo, and rising-edge `SetTrigger` would otherwise wait for a release.

**Keep `SetView()` in FireShot (:1395).** It never touches control rotation. Its job is to make `WorldGun` visible after `GunRaisedTime = 3` (`HoverPilot.cpp:532`), which is how the gun appears during third-person hip-fire. **Leave `FireCooldown = .18f`.** The bridge never reads it, and lowering it would speed up PostApo.

**Sprint-fire gate** (survival rules only, via `bSurvivalRules` set by `AHoverNYCSurvivalGameMode`): promote the local `Sprint` at `HoverPilot.cpp:686` to a member, and `CanFire &= !(bSurvivalRules && (bSprinting || Now - SprintEndTime < .15f))`.

### P0-2 Camera shake (new `HoverFireShake.h/.cpp`)

Add `"EngineCameras"` to `PublicDependencyModuleNames` in `HoverFlight.Build.cs`. The plugin is EnabledByDefault, and `UPerlinNoiseCameraShakePattern` lives there, not in Engine.

```cpp
#include "Shakes/PerlinNoiseCameraShakePattern.h"
UHoverFireShake::UHoverFireShake(const FObjectInitializer &Init) : Super(Init)
{
    bSingleInstance = false;                                  // 8/s stack, 1-2 overlap at .12 s
    auto *P = CreateDefaultSubobject<UPerlinNoiseCameraShakePattern>(TEXT("Root"));
    P->Duration = .12f; P->BlendInTime = .02f; P->BlendOutTime = .08f;
    P->Pitch.Amplitude = .7f; P->Pitch.Frequency = 28.f; P->Yaw.Amplitude = .25f; P->Yaw.Frequency = 22.f;
    P->Roll.Amplitude = .15f; P->Roll.Frequency = 18.f; P->FOV.Amplitude = .6f; P->FOV.Frequency = 20.f;
    P->X.Amplitude = 1.2f; P->X.Frequency = 24.f;
    SetRootShakePattern(P);
}
```

The same file defines `UHoverHurtShake` (pitch 1.2, roll 1.5, 0.2 s) and `UHoverBlastShake` (pitch 2.0, FOV 2.0, 0.45 s). The trigger lives in FireShot:

`PC->ClientStartCameraShake(Shake, Tier.ShakeScale * ViewScale * ShakeSetting)`

`ViewScale` is 1.0 in third person, 0.6 when aiming and 0.8 in first person. `Shake` is `Definition->FireCameraShake`, falling back to `Assets->FireShake` (PostApo). `BP_M16_FireShake` is left untouched. Shake is applied to the view only: it changes the camera-manager POV, never the aim traces.

### P0-3 Real recoil (AHoverPilot, no vendor patch)

```cpp
// HoverPilot.h private: float RecoilPitchDebt = 0.f, LastRecoilTime = -10.f; void ApplyViewRecoil(float Pitch, float Yaw);
void AHoverPilot::ApplyViewRecoil(float PitchKick, float YawKick)
{
    auto *PC = Cast<APlayerController>(GetController());
    if (!PC) return;
    FRotator View = PC->GetControlRotation();               // direct write, never AddControllerPitchInput (legacy -2.5 scale)
    View.Pitch = FMath::Clamp(FRotator::NormalizeAxis(View.Pitch) + PitchKick, -75.f, 75.f);
    View.Yaw += YawKick;
    PC->SetControlRotation(View);
    RecoilPitchDebt = FMath::Min(RecoilPitchDebt + PitchKick * .6f, 6.f);   // 60 % auto-recovers
    LastRecoilTime = GetWorld()->GetTimeSeconds();
}
// Tick, next to HoverMotion::Spring at :1775
const auto *Weapon = Combat ? Combat->GetWeapon() : nullptr;
const UZE_WeaponDefinition *Definition = Weapon ? Weapon->GetWeaponDefinition() : nullptr;
const float Quiet = FMath::Max(.2f, 1.5f / FMath::Max(1.f, Definition ? Definition->FireRate : 8.f));
if (RecoilPitchDebt > 0 && !(Weapon && Weapon->IsFiring()) && GetWorld()->GetTimeSeconds() - LastRecoilTime > Quiet)
{
    const float Step = FMath::Min(RecoilPitchDebt, (Definition ? Definition->CombatStats.RecoilRecovery : 10.f) * DT);
    if (auto *PC = Cast<APlayerController>(GetController()))
    { FRotator V = PC->GetControlRotation(); V.Pitch = FRotator::NormalizeAxis(V.Pitch) - Step; PC->SetControlRotation(V); }
    RecoilPitchDebt -= Step;
}
```

Per shot, `PitchKick = Kick.X * FRandRange(.85, 1.15) * (bAiming ? .7 : 1) * RecoilSetting` and `YawKick = FRandRange(-Kick.Y, Kick.Y)`. PostApo falls back to a kick of (0.35, 0.15). Over a full 30-round magazine the view climbs about 10.5 deg gross while firing (7.4 deg in ADS). The debt cap of 6 is reached around shot 29 and recovers in 0.6 s after release, leaving about 4.5 deg net that the player manages. Recovery is gated on the trigger state, so it does not change with Double Tap. `gun_recoil_distance = 4.0` is set on the `DA_HoverPilot` asset (the header default is not what runs). Recoil changes the control rotation, so the review arm inherits it.

### P0-4 Haptics (built in C++)

`HoverHaptics::Build(UObject *Outer)` creates each `UForceFeedbackEffect` with `NewObject` at `AHoverPilot::BeginPlay` and fills `ChannelDetails[i].Curve.GetRichCurve()->AddKey(t, v)`. An optional `DA_HoverPilot` slot overrides each effect. Kill and hit feedback set `bIgnoreTimeDilation = true` so they survive the boss slow-motion kill cam. Intensity uses `PC->ForceFeedbackScale` (from the rumble slider).

| Effect | Channels: curve (t, v) | Use |
|---|---|---|
| FF_RifleFire | LL (0,.45)(.04,.3)(.07,0); RS (0,.9)(.04,0) | every shot, Tag "Fire" |
| FF_HitConfirm | RS/LS (0,.35)(.04,0) | body hit |
| FF_Headshot | RS (0,.6)(.05,0); RL (0,.3)(.06,0) | headshot |
| FF_Kill / FF_KillHeadshot | LL+RL (0,.7)(.06,.5)(.14,0) / same x1.3 clamped to 1 | kill |
| FF_Reload | LS (0,.25)(.03,0) | mag out, mag in |
| FF_MeleeSwing | LL (0,.5)(.08,0) | katana contact |
| FF_PlayerHit | LL (0,.5)(.1,0) | zombie hit on Vexa |
| FF_Stomp | LL+RL (0,.9)(.35,0) | Brute or Alpha stomp knockdown |
| FF_PlateBreak | RS (0,.8)(.05,0) | plate breaks |
| FF_Downed | LL (0,.6)(1.0,0) | downed |
| FF_Explosion | all (0,1)(.1,.6)(.4,0), scaled by distance | frag |

Each shot calls `ClientPlayForceFeedback(FireFX, P)`. The fallback is `PlayDynamicForceFeedback(.55f, .07f, true, true, false, true)`.

### P0-5 Hit confirmation and damage numbers

```cpp
// HoverPilot.h public
void NotifyHitConfirmed(bool Headshot, bool Kill, const AActor *Causer);
void AHoverPilot::NotifyHitConfirmed(bool Headshot, bool Kill, const AActor *Causer)
{
    if (!Assets) return;                                     // BeginPlay may have returned early (:141-146)
    const float Now = GetWorld()->GetTimeSeconds();
    if (Kill && Now - LastKillStingTime < .08f) Kill = false; // multi-kill = one sting
    if (Kill) LastKillStingTime = Now;
    LastHitMarkTime = Now; bLastHitHeadshot = Headshot; bLastHitKill = Kill;
    const bool Melee = Cast<AHoverMeleeWeapon>(Causer) != nullptr;
    if (USoundBase *Cue = Kill ? Assets->KillSting : Headshot ? Assets->HeadshotSound : Assets->HitConfirmSound)
        UGameplayStatics::PlaySound2D(this, Cue, Kill ? 1.f : .8f);
    if (auto *PC = Cast<APlayerController>(GetController()))
    {
        FForceFeedbackParameters P; P.Tag = TEXT("Hit"); P.bIgnoreTimeDilation = true;
        UForceFeedbackEffect *FX = Kill ? (Headshot ? Haptics.KillHeadshot : Haptics.Kill)
                                 : Melee ? Haptics.Melee : Headshot ? Haptics.Headshot : Haptics.Hit;
        if (FX) PC->ClientPlayForceFeedback(FX, P);
    }
}
```

The hook goes in `AHoverCyberZombie::TakeDamage`. Hoist `FHitResult Hit; FVector Direction;` above :554 and call `Event.GetBestHitInfo` outside the `if`. Then, after `Super` (:571):

```cpp
const bool Headshot = ZombieData && Hit.BoneName == ZombieData->Stats.HeadBoneName;
if (WasAlive && Damage > 0 && Cast<AZE_WeaponBase>(Causer))            // no corpses, no Nuke (weapon-less causer)
    if (auto *Pilot = EventController ? Cast<AHoverPilot>(EventController->GetPawn()) : nullptr)
        Pilot->NotifyHitConfirmed(Headshot, bIsDead, Causer);
```

The kill-point override (90/115/105/250/500) and the Insta-Kill Brute x4 / boss x2 rule share this block (economy section). Deadshot x3 must pre-scale `Damage` before `Super`, because :148 reads the shared DA multiplier. Add a public `bool IsDead() const { return bIsDead; }` to `AHoverCyberZombie`; the vendor `bIsDead` is protected. `AHoverZombie::IsDead()` already exists (`HoverZombie.h:19`). The PostApo mirror in `AHoverZombie::TakeDamage` (:106-124) needs `#include "HoverPilot.h"`.

HUD (after `HoverPilot.cpp:1861`): the cross gap is `G = 4 + Rifle->GetEffectiveSpreadDegrees() * 6` px, keeping the aiming red dot. The marker is four diagonal 2 px segments from `G+2` to `G+10` px for 0.12 s, with `alpha = 1 − Age/.12`: white for body, red (1,.15,.1) for headshots, and yellow (1,.85,.2) at 1.5x size for kills. Reserved Stage 2 colours: a grey "clang" marker on the Riot armor pool (no headshot marker while the pool is above 0) and cyan (.3,.9,1) reserved for a future boss weak point (none in Stage 1).

Damage numbers stay on the vendor accumulator, with `DamageAccumulationWindow 0.1` on the NYC zombie DAs. The window slides, and the 0.125 s shot interval is longer than it, so every shot gets its own number while same-frame pierce hits merge. That caps widgets at about one per zombie per shot. If the perf capture shows more than 40 live `AZE_DamageNumberActor`, raise the window to 0.3.

### P0-6 Shot presentation (tracer, muzzle light, sound, TPS reaction)

`AHoverShotVisual::Launch(Start, End, const FHoverRifleTier &Tier)` sets the following:
- `Bullet` scale (.9,.03,.03); the Tick at :57 becomes `FVector(FMath::Min(90.f, Distance - Travel) / 100.f, .03f, .03f)`.
- `Duration = Clamp(Distance / 40000, .12, .22)`.
- `User.Emissive 8`, `User.Trail Size 3`, `User.Lifetime .14`.
- `Trail->SetAsset(LoadObject(Tier.Tracer))`, replacing the asset hardcoded at :22-23.
- `User.Color` only when `Tier.bColor`, and `ColorA/ColorB` for Magic.
- No tracer for travel under 250 cm.

The single caller (`HoverPilot.cpp:1473`) moves after the hit loop.

The muzzle light is one persistent `UPointLightComponent MuzzleLight`, created at BeginPlay with 0 intensity, no shadows, a 320 cm radius and colour (.75,.85,1). Each shot re-attaches it to the active gun at `Assets->GunMuzzle`, sets 600 cd (tune 300-800 from captures), and restores 0 after 0.06 s via `FTimerDelegate::CreateWeakLambda(this, ...)`. The flash sprite timer goes from 0.09 s to 0.10 s.

The sound (replacing :1509-1511) is `SpawnSoundAttached(ShotSound, ActiveGun, NAME_None, Assets->GunMuzzle, KeepRelativeOffset, false, 1.0f, Tier.Pitch * FRandRange(.97, 1.03))`, plus `A_Cyberpunk_Rifle1_Tail` at 0.5 volume every third shot. Shells keep `EjectShellAt(FTransform(Gun->GetComponentQuat(), Breech))`; their direction comes from the DA `BulletShellDirection`.

**Third-person fire reaction (on foot):** on the first shot of a burst and then every fourth shot (every 0.5 s), unless reloading, call `LocomotionBridge->PlayAction(MM_Rifle_Fire /* /Game/CLS/Example/SetupYourHeroExample/Anims/Rifle */, 0.f, true)`, an upper-body clip. Today only mounted aiming plays `Assets->Fire` (:1514-1518). The existing gun-model spring stays.

### P0-7 Bounded penetration (replaces FireShot :1466-1505)

```cpp
const auto *Rifle = Cast<AHoverCyberRifle>(SourceWeapon);   // next to Definition at :1408
const FHoverRifleTier &Tier = Rifle ? Rifle->GetTier() : AHoverCyberRifle::DefaultTier();
FVector End = Target;
if (!ProjectileLaunched)
{
    int32 PiercesLeft = Tier.Pierce; float Scale = 1.f; FVector Start = Muzzle;
    for (int32 Guard = 0; Guard < Tier.Pierce + 8; ++Guard)
    {
        if (Guard > 0 || !Hit.bBlockingHit)                   // iteration 0 reuses the breech hit (:1433)
            Hit = TraceWeaponRay(GetWorld(), Start, Target + ShotDirection * 3.f, Params);
        if (!Hit.bBlockingHit) break;
        End = Hit.ImpactPoint;
        AActor *Victim = Hit.GetActor();
        const auto *Cyber = Cast<AHoverCyberZombie>(Victim); const auto *Simple = Cast<AHoverZombie>(Victim);
        const auto *OtherZE = Cyber ? nullptr : Cast<AZE_ZombieCharacter>(Victim);
        if (Cyber || Simple || OtherZE)
        {
            const auto *Surv = OtherZE ? OtherZE->FindComponentByClass<UZE_SurvivalComponent>() : nullptr;
            const bool WasCorpse = Cyber ? Cyber->IsDead() : Simple ? Simple->IsDead() : (Surv && Surv->GetHealth() <= 0);
            Params.AddIgnoredActor(Victim); Start = Hit.ImpactPoint + ShotDirection * 5.f;
            if (WasCorpse) continue;                          // sampled BEFORE damage: free, no pierce consumed
            UGameplayStatics::ApplyPointDamage(Victim, Damage * Scale, ShotDirection, Hit, GetController(), DamageSource, nullptr);
            SpawnFleshFeedback(Hit, ShotDirection);           // P1-1
            if (PiercesLeft-- <= 0) break;
            Scale *= Tier.PierceScale; continue;
        }
        if (Victim) UGameplayStatics::ApplyPointDamage(Victim, Damage * Scale, ShotDirection, Hit, GetController(), DamageSource, nullptr);
        SpawnSurfaceImpact(Hit);                              // existing :1484-1505 block moved verbatim into a helper
        break;
    }
}
```

Non-zombie actors (vehicles, destructibles) still take damage. `DamageSource` stays the weapon, so headshots still apply. HoverPilot.cpp gains `#include "Player/ZE_SurvivalComponent.h"` (the path follows the plugin layout).

### P1 items

- **Flesh feedback** (`SpawnFleshFeedback`):
  - `SC_Hit` at 0.9 volume, pitch 0.9-1.1.
  - `NS_NS1_BloodShot` on the body. No skinned-mesh decals: they do not follow deformation.
  - Wall trace 150 cm behind the victim. On a non-pawn hit, `SpawnDecalAtLocation(M_BloodDecal, FVector(25), ..., 10 s)` through a 32-slot ring buffer that destroys the oldest.
  - `BloodBurst` gains `bool Headshot` (scale 1.0, stop at 0.3 s).
  - `M_BloodDecal` (Deferred Decal, DBuffer) is built from `T_Blood_2` and `T_Blood_2_Mask`.
- **Kill punctuation** (`AHoverCyberZombie`, post-Super, `WasAlive && bIsDead`, skipped for bosses because the boss kill cam supersedes it):
  - Add `FTimerHandle HitStopTimer;` (private).
  - Set `CustomTimeDilation = .15f`, then `SetTimer(HitStopTimer, FTimerDelegate::CreateWeakLambda(this, [this]{ CustomTimeDilation = 1.f; }), .07f, false)`.
  - On a headshot kill: `StopAnimMontage()`, `HideBoneByName(Hit.BoneName, PBO_None)`, and a gib burst at `GetSocketLocation(GetMesh()->GetParentBone(Hit.BoneName))`. Verify the head and parent bone names in the authoring dump.
  - Then ragdoll with `AddImpulseAtLocation(Direction * 4500, Hit.ImpactPoint, Hit.BoneName)`. The vendor ragdoll lambda re-applies the profile, which is idempotent.
  - Flinch at ≥ 10 % MaxHealth every 0.35 s, including while attacking, belongs to the crowding/AI section.
- **Reload:** timers at 35 % and 80 % of `ReloadDuration` play `FF_Reload` and dip the gun 2 deg. Speed Cola scales `ReloadDuration` (economy section).
- **Melee lunge** (`AHoverMeleeWeapon::PlayFireAnimation`): a 40 cm sphere sweep over 240 cm. If a zombie is found at D > 110 cm, override velocity for 0.12 s toward `Target − 90 cm` with `Speed = (D − 90) / .12`, capped at 1,400 cm/s, then restore the movement mode. Contact timing is unchanged. A katana kill adds `FF_Kill`, a 0.05 s victim hit-stop and a slash `BloodBurst`. Points stay at 105.
- **Incoming damage** (in `AHoverPilot::TakeDamage`, which the player section owns):
  - Every hit: `UHoverHurtShake` at scale Clamp(Damage/30, .6, 1.6) and `FF_PlayerHit`.
  - Stomp knockdown: hurt shake x2 and `FF_Stomp`.
  - Plate break: `FF_PlateBreak`, with the player section's crack sound.
  - Downed: `FF_Downed`.
  - The directional indicator and regen HUD stay with the player section.
- **Frag:** `UGameplayStatics::PlayWorldCameraShake(UHoverBlastShake, inner 300, outer 1500)` and `FF_Explosion` scaled by 1 − d/1500.
- **Intensity sliders** (HoverGraphicsMenu, persisted in GameUserSettings): Camera shake 0-100 %, View recoil 50-100 %, Rumble 0-100 % (via `ForceFeedbackScale`). They feed `ShakeSetting`, `RecoilSetting` and the rumble scale.

### P2 items

- **FP arms fire:** use `AM_FPS_Fire_AIM_M16_Montage` (DefaultSlot) when aiming, and `PlaySlotAnimationAsDynamicMontage(AS_FPS_Fire_M16, "DefaultSlot", .02, .06)` for hip fire. The arms already play ZESP M16 FPS idles (`HoverAnimInstance.cpp:690-693`). `AS_FPS_Fire_M16_Montage` uses an UpperBody slot this graph lacks.
- **Sound layers:** a bolt clack at 0.35 volume and a distant layer.
- **Heavy Ballista family:** Stage 2.

### Cross-section dependencies

| Section | Needs from or gives to this section |
|---|---|
| Economy | PaP swap to the `DA_NYC_Ballista` names; `DA_AMMO_NYC_Ballista`; Double Tap via `FireRateScale`; Deadshot pre-scale before `Super`; Speed Cola `ReloadDuration`; kill points and Insta-Kill in the same post-Super block |
| Crowding/AI | The flinch rule (plugin patch 15, recorded in `Docs/QUALITY_20261023.txt`) |
| Camera/player | Third-person default; `bSurvivalRules`; plates and downed fire the haptics above |
| Boss | 3 s slow-motion kill cam (hit-stop is skipped for bosses) |
| Roster | `DA_NYC_*` zombie DAs carry `DamageAccumulationWindow 0.1` |

### Asset checklist

| Create | Path | Notes |
|---|---|---|
| DA_NYC_Ballista.._4, DA_NYC_Sidearm/_2, DA_AMMO_NYC_Ballista (Stage 2: DA_NYC_M16.._4, DA_NYC_HeavyBallista.._4) | `/Game/HoverPrototype/NYC/Weapons/` | Duplicates; ZESP and `DA_AFS_*` stay untouched except for presentation fields |
| M_BloodDecal (+ MI) | `/Game/HoverPrototype/Effects/` | Decal domain |
| S_HitConfirm, S_Headshot, S_KillSting, S_BoltClack, S_ImpactConcrete | `/Game/HoverPrototype/Audio/` | Imports. `KillSting` may reuse `S_Entity_Hit_B` at 0.7 volume in the meantime |
| UHoverFireShake / HurtShake / BlastShake, HoverHaptics | C++ | EngineCameras dependency |
| Reuse | `A_Cyberpunk_Rifle1_004/_Tail`, `SW_Shot`, `NS_ArrowTrail_*`, `NS_Lightning_Damage_Land_Small`, `NS_NS1_BloodShot`, `SC_Hit`, `MM_Rifle_Fire`, `T_Blood_2` | Add `/Game/ArrowTrail`, `/Game/Zombie/Sound` and `/Game/Sci_Fi_Weapons_VFX_AIO` to the `PAL_AFS_Runtime` cook roots |

### Authoring and validation steps

1. Run `UnrealEditor-Cmd.exe M:/UnrealProjects/AFS/AFS.uproject -run=pythonscript -script=M:/UnrealProjects/AFS/Scripts/AuthorBallistaTiers.py`. The script:
   - duplicates the tiers;
   - copies `combat_stats`, sets the table fields and calls `set_editor_property('combat_stats', stats)`;
   - sets `fire_rate`, `automatic` (bool properties drop the b prefix in UE Python), `magazine_size`, `max_reserve_ammo`, `bullet_shell_impulse`, `bullet_shell_direction`, `muzzle_flash_fx`, and `fire_camera_shake = unreal.load_class(None, '/Script/HoverFlight.HoverFireShake')`;
   - sets `gun_recoil_distance` on `DA_HoverPilot`, and `damage_accumulation_window` on the NYC zombie DAs once they exist;
   - writes before and after values to `D:/AFS_Comparisons/Gunplay_<date>/*_before.json` and `_after.json`.
2. Build with `Scripts/Build.ps1`, then run `clang-format` on the touched sources.
3. Offscreen runs, never concurrent, with `-LogCmds="LogTemp Verbose"`:
   - Hold the trigger for 1.1 s: expect 1 `HOVER_SHOT` before the fix (rising-edge semi) and 9 after.
   - Spread: about 0.5 / 1.4 / 3.0 at shots 1 / 10 / 30, and about 0.6 / 0.5 at +0.25 s / +0.5 s after release.
   - Pitch over a 10-shot burst: +3.5 deg gross, settling to +1.4 within 0.5 s.
   - Pierce: one PaP II shot through two zombies logs two `HOVER_ZOMBIE_HIT` lines. **Negative test:** one PaP 0 shot that kills the first of two zombies logs exactly one.
   - Tapping at 20 Hz still yields at most 8 shots/s.
   - Releasing on an empty magazine with the trigger held auto-reloads.
   - In a packaged-equivalent run with the rifle ticking, the control pitch stays within the AFS -75..75 clamp and does not move during knockdown. The vendor `UpdateCombatState` writes the control rotation every tick and should write a zero delta.
   - Perf capture: frame time, live damage-number actors and Niagara tracer cost at 8/s per tier.
4. Rendered captures (AGENTS.md) of the gun, muzzle light, shell direction, tracer and recoil in third-person hip and ADS, first person, and mounted glider.
5. Regressions: `Scripts/VerifyNYCExploration.py` (FireShot runs at index 3), `Scripts/VerifyCyberWaves.py` (presentation fields on the shared DAs) and a PostApo shot check, all sequential.
6. Record everything in `Docs/GUNPLAY_<date>.txt` under a `VALIDATION` section, with the comparison folder.

**Owner amendments:**
- `Docs/CONTROLS.txt` NYC row: "Ballista 35/70/140/280 body, x2 head, 8 rounds/s auto, mag 30, reserve 270/360/450/540, PaP II/III pierce 1/2, no fire while sprinting; shake/recoil/rumble sliders".
- `CONTROLS.txt:70` and `README.md:18, 155-159`: Cyber City and Lakeside crate tiers keep their damage and semi-auto, and gain shake, recoil, rumble, hit markers and tier tracers. Whether to also give them auto-fire is an owner call; if so, rerun `VerifyCyberWaves.py`.
- PostApo feel changes (shake, recoil, rumble, marker; cooldown unchanged).
- `.gitignore` Docs whitelist for `Docs/GUNPLAY_<date>.txt`.
- `QUALITY_20261023.txt` patch count, if the flinch patch lands.

### Risks

- Recoil changes the control rotation and the review arm inherits it. Shake is view-only.
- A tier lookup miss falls back to PaP 0 feel and logs `HOVER_RIFLE_TIER missing` once.
- 8/s multi-emitter arrow trails and a moving point light are unmeasured on NYC's procedural city. Fall back to Basic_02 with a colour if the GPU cost exceeds 0.5 ms.
- `MM_Rifle_Fire` through `PlayAction` may fight Parkour vaults. Suppress it while a Parkour action is active.
- The native shake class in a DA requires the module to load before the asset. A Blueprint child is the fallback.
- The DA renaming must be accepted by the spine owner, or the PaP chain stays on `DA_AFS_*` and the Cyber/Lakeside balance amendment becomes mandatory.

## 6. Points economy, armory, Pack-a-Punch and armor upgrades

All new classes live in `M:/UnrealProjects/AFS/Source/HoverFlight/` (new pair `HoverNYCEconomy.h/.cpp`, plus edits to `HoverCyberCity.*`, `HoverCombatBridge.*`, `HoverPilot.*`, `HoverGraphicsSettings.cpp`, `HoverGraphicsMenu.cpp`). No vendor file is touched. `AHoverNYCSurvivalGameMode` derives from `AHoverCyberCityGameMode`, so Vexa receives `UHoverCombatBridge` (gate at `HoverPilot.cpp:282`), and `GetGold`/`AddGold` (`HoverCyberCity.cpp:596-612`), the wave `DamageScale` in `AHoverPilot::TakeDamage` (`HoverPilot.cpp:1652-1660`) and the HUD gold line (`HoverPilot.cpp:1826-1831`) keep working. "Points" means the existing float `UZE_SurvivalComponent::CurrentGold` (`ZE_SurvivalComponent.h:117`). No new field stores currency, and every balance change goes through the NYC mode's `AddPoints` / `TryPay`.

**Shared assets stay untouched.** `DA_AFS_Ballista.._5` are shared with Cyber City (the street crates sell tiers for 500/1250/2500, `Docs/CONTROLS.txt:69-71`) and with the Lakeside starting gear. Their decoded current values are: Damage 35/45.5/56/66.5/78.75, Mag 30/35/40/45/60, Headshot 2.0/2.2/2.5/2.8/3.5, FireRate 8/9/default/11.5/13, and MaxReserveAmmo 0 on every tier. NYC therefore owns its own copies under `Content/HoverPrototype/NYC/` (section 6). The spine's "DA_AFS_Ballista -> _2 -> _3 -> _4" swap is delivered as `DA_NYC_Ballista_0 -> _1 -> _2 -> _3`, using the same mechanism and the same numbers.

### 1. Points (Essence)

**Hook.** `AHoverCyberZombie::TakeDamage` pays `Mode->AddGold(RandRange(MinGoldReward, MaxGoldReward))` when the zombie goes from alive to dead (`HoverCyberCity.cpp:587-588`). The hit bone is read with `Event.GetBestHitInfo` inside the `if (!bIsDead && Damage > 0)` block (`:554-561`). `AddGold` is non-virtual (`HoverCyberCity.h:53`), so a wrapper on the derived class would never be reached from that call. The fix is to replace line 588 with one virtual hook on the Cyber mode:

```cpp
// HoverCyberCity.h  (AHoverCyberCityGameMode)
virtual void OnZombieKilled(AHoverCyberZombie *Zombie, const FHitResult &Hit, AActor *Causer);
// base body keeps today's behaviour, so VerifyCyberWaves.py is untouched:
//   AddGold(FMath::RandRange(Zombie->ZombieData->Stats.MinGoldReward, ...MaxGoldReward));

// HoverCyberCity.cpp: hoist `FHitResult Hit; FVector Direction;` above the if-block at :554
if (WasAlive && bIsDead && Mode && ZombieData) Mode->OnZombieKilled(this, Hit, Causer);

// HoverNYCEconomy.cpp (AHoverNYCSurvivalGameMode)
void AHoverNYCSurvivalGameMode::OnZombieKilled(AHoverCyberZombie *Z, const FHitResult &Hit, AActor *Causer)
{
    if (bNukeResolving) return;                                   // Nuke pays only its flat +400
    AddPoints(KillReward(Z, Hit, Causer), EHoverPointsReason::Kill);
    NoteKillForDrops(Z);                                          // power-up threshold, guaranteed drops
}
int32 AHoverNYCSurvivalGameMode::KillReward(const AHoverCyberZombie *Z, const FHitResult &Hit, AActor *Causer) const
{
    const bool bMelee = Cast<AZE_MeleeWeapon>(Causer) != nullptr;
    const bool bGun   = !bMelee && Cast<AZE_WeaponBase>(Causer) != nullptr;
    const bool bCrit  = bGun && Hit.BoneName == Z->ZombieData->Stats.HeadBoneName;  // FName == ignores case
    int32 Base = bMelee ? 105 : (bCrit ? 115 : 90);               // Standard, Kid
    switch (Z->GetRole()) {
      case EHoverZombieRole::Brute: Base = 250; break;
      // enemy slice adds: case Riot: 150 (Stage 2); case Boss: 500 (StoneGolem, Giant Kid); Alpha Brute elite stays Role Brute at 250
      default: break;
    }
    return FMath::RoundToInt(Base * PointsMultiplier());           // 1.0; 2.0 under Double Points (Stage 2)
}
```

`ZombieData` is public (`ZE_ZombieCharacter.h:35-40`) and `GetRole()` is const (`HoverCyberCity.h:102`), so this compiles as written with Standard/Brute/Kid. The `Riot`/`Boss` cases land with the enemy slice's enum extension (`HoverCyberVariants.h:7-13` has only three values today). Every NYC enemy, bosses included, must derive from `AHoverCyberZombie` so that it reaches this hook.

`AddPoints(int32, EHoverPointsReason)` calls `AddGold`, then increments `PointsEarnedTotal` and `PointsEarnedThisRound` (the spine's power-up threshold reads points earned, not the balance), then pushes a HUD popup. `TryPay` is the only spend path.

| Award | Value | Condition |
|---|---|---|
| Standard / Kid kill | 90 | death, any causer (grenade kills use `ApplyRadialDamageWithFalloff` with the projectile as causer, `ZE_Projectile_Grenade.cpp:308-311`, which is not an `AZE_WeaponBase`, so they pay 90) |
| Critical kill | 115 | non-melee `AZE_WeaponBase` causer, `Hit.BoneName == HeadBoneName` |
| Melee kill | 105 | `AZE_MeleeWeapon` causer (Vexa's `AHoverMeleeWeapon`); `DA_NYC_Melee` HeadshotMultiplier 1.0 so the spine's 2-swing table holds |
| Riot (Stage 2) / Brute / boss | 150 / 250 / 500 | role; the R27 pair pays 1,000 |
| Nuke | +400 flat | `AHoverCyberPowerUp` Nuke branch (`HoverCyberCity.cpp:636-642`). The NYC mode sets `bNukeResolving = true` around the loop, so the up to 24 nuked zombies pay 0 instead of 24 x 90 = 2,160. The Brute/boss "25% of max" exemption is applied by the enemy slice before `Super` |
| Double Points (Stage 2) | x2 | `PointsMultiplier()` while `DoublePointsUntil > now` |
| Starting points | 500 | `DA_NYCWaves.StartingEquipment.StartingGold`, read at `HoverCombatBridge.cpp:258` |

The vendor `HandleRewardsAndLoot` casts to `AZE_PlayerCharacter` (`ZE_ZombieCharacter.cpp:493-513`), so it never pays Vexa and there is no double award. `MinGoldReward = MaxGoldReward = 0` on every `DA_NYC_*` zombie DA, so the field is visibly inert.

**HUD popups.** `AHoverHUD::DrawHUD` draws canvas text (`HoverPilot.cpp:1817-1831`). The mode keeps `TArray<FHoverPointsPopup{int32 Amount; FString Tag; float Time;}>` (max 8). Each popup is drawn to the right of the counter, rising 36 px and fading over 0.9 s: `+90`, `+115 HEADSHOT`, `+105 MELEE`, `+250`, `+500 BOSS`, `+400 NUKE`, `-5,000 PACK-A-PUNCH`, `NOT ENOUGH POINTS`. The vendor `ShowBuyFeedback` requires `AZE_PlayerController` (`ZE_WallBuyActor.cpp:63-70`), so every station toasts through this buffer instead. The label `Gold:` becomes `Points:` in the NYC mode only (`HoverPilot.cpp:1828`).

### 2. Station base class and the armory

`AZE_WallBuyActor::ExecutePurchase` is public and non-virtual (`ZE_WallBuyActor.h:33`), and `PlayerHasWeapon` is private (`:81`). Its ammo path grants `MagazineSize*2` rounds with no cap (`.cpp:82-84`). It also calls `AssignInstanceToQuickbar(Id, -1)` (`.cpp:92`); `NormalizeSlotIndex(-1)` returns -2, which `MoveOrSwapInventoryToQuickbar` rejects (`ZE_InventoryComponent.cpp:361-364, 564-571`), so vendor wall buys leave the gun in the grid. NYC stations therefore never call `ExecutePurchase`.

`UZE_InteractionTraceComponent::TryInteract` calls `Execute_Interact` only after `Execute_CanInteract` returns true (`ZE_InteractionTraceComponent.cpp:303-307`). The base `CanInteract` is `WeaponDefinition != nullptr` (`ZE_WallBuyActor.cpp:33-36`), which would make the PaP station and the ammo caches dead. The bridge builds the prompt as `"Hold X / F: " + GetFocusedInteractText()` (`HoverCombatBridge.cpp:427-432`) with a 0.5 s hold, and the pawn gate is `MaxInteractDistance` 250 cm (TraceDistance is 800 cm), so placement must respect 250 cm.

```cpp
UCLASS(Abstract) class HOVERFLIGHT_API AHoverStationBase : public AZE_WallBuyActor {
  GENERATED_BODY()
public:   // matches the base's public overrides (ZE_WallBuyActor.h:37-46)
  virtual bool CanInteract_Implementation(APawn *P) const override;   // true when visible and zone unlocked; never checks balance
  virtual float GetHoldDuration_Implementation(APawn *) const override { return 0.5f; }
protected:
  UPROPERTY(EditAnywhere, Category="AFS|Station") bool bRequiresPower = false;
  UPROPERTY(EditAnywhere, Category="AFS|Station") FName ZoneId;        // zone slice: hidden until the door opens
  AHoverNYCSurvivalGameMode *Mode() const;
  UHoverCombatBridge *Bridge(APawn *P) const;                             // Cast<AHoverPilot>(P)->Combat
  bool TryPay(APawn *P, int32 Price, const TCHAR *Tag);                   // balance check + AddPoints(-Price), else "NOT ENOUGH POINTS"
  static bool FindOwned(UZE_InventoryComponent *Inv, const UZE_ItemDefinition *Def,
                        FZE_InventoryItemInstance &Out, int32 &QuickbarSlot);  // GetAllItems + GetQuickbarItem(1..5)
  static bool HasFreeGridCell(const UZE_InventoryComponent *Inv);         // scans GetAllItems for an invalid InstanceId (FindFirstEmptySlot is private)
  static int32 FirstFreeQuickbarSlot(const UZE_InventoryComponent *Inv);  // scans GetQuickbarItem(1..5); 0 if none
};
```

All affordability, MAXED, power and space checks happen inside `Interact_Implementation`, and the prompt reports them. `GetInteractText` returns only the action text (`Buy Sidearm (500)`), because the bridge adds the key prefix.

`AHoverArmoryBuy : AHoverStationBase` sells one weapon family and refills it at the price of the tier the player owns:

| Field | Type | Notes |
|---|---|---|
| `Family` | `TArray<TObjectPtr<UZE_WeaponDefinition>>` | tier order, e.g. `DA_NYC_Ballista_0.._3` |
| `WeaponPrice` | int32 | Sidearm 500, Ballista re-buy 1,750, M16 1,250 (S2), Heavy Ballista 3,000 (S2) |
| `RefillPrices` | `TArray<int32>` | Ballista 250/750/1,500/3,000; Sidearm 100/250; M16 and Heavy Ballista the same ladder |
| `bAmmoCache` | bool | refills the active weapon of any registered family; `Family` empty |

How `Interact` works:
- **Owned at tier i.** `Missing = Family[i]->MaxReserveAmmo - Inv->GetTotalAmmoByTypeId(Family[i]->AmmoTypeId)`. The reserve is backed by the inventory (`ZE_WeaponBase.cpp:581-607`), and NYC weapon ItemIds never equal their AmmoTypeId, so the `-1` self-count in `GetReserveAmmo` (`:600-605`) does not apply. If `Missing > 0`, the station checks the price, calls `AddItemDefinition(AmmoDefinition, Missing, Id)`, and charges only if that succeeds. The clip is untouched (BO rule).
- **Not owned.** The station checks the price and a free grid cell, calls `AddItemDefinition(Family[0], 1, Id)`, then `AssignInstanceToQuickbar(Id, FirstFreeQuickbarSlot)`, and charges last. If all five slots are full, the prompt becomes `Swap <active> for Sidearm (500)`, and the new gun swaps with the active slot.

The weight gate stays on. MaxWeight is 80 (`ZE_InventorySettings.h:172`, no ini override), ammo uses the ctor value 0.01 (`ZE_AmmoDefinition.cpp:22`) and weapons weigh 3.0. 540 + 96 rounds plus four guns comes to about 18, so no weight change is needed.

**Max Ammo.** `UHoverCombatBridge::RefillAmmo` only tops up the active weapon (`HoverCombatBridge.cpp:328-343`). Because every shared Ballista DA has MaxReserveAmmo 0, it adds no reserve today. The new `RefillAllAmmo()` does this:
1. It iterates `GetAllItems` plus quickbar 1..5 and collects the weapon definitions that have a non-null `AmmoDefinition`. This skips `DA_Grenade_Frag`, which is a `UZE_WeaponDefinition` with `AmmoTypeId 'grenade'` and no AmmoDefinition.
2. It tops each distinct `AmmoTypeId` pool up to `MaxReserveAmmo`.
3. It tops frags separately with `GetTotalQuantityByItemId('Bomb_001')` against the carry cap (2, or 4 with Stamin-Up).
4. It calls `Weapon->RefillAmmo(false)` on the active weapon.

Plates are excluded. In NYC, the `AHoverCyberPowerUp` MaxAmmo branch (`HoverCyberCity.cpp:645-648`) calls it.

**Starting kit (data).** `DA_NYCWaves.StartingEquipment` sets `DA_NYC_Ballista_0` in slot 1, `StartingAmmo [DA_NYC_AMMO_Ballista]`, `AmmoQuantity 270`, `GrenadeItem DA_Grenade_Frag`, `GrenadeCount 2`, `bAddGrenadesToQuickbar false` and `StartingGold 500` (`ZE_WaveGameModeSettings.h:48-86`). The bridge adds starting ammo only inside `if (Waves && !StartingWeapons.IsEmpty())` (`HoverCombatBridge.cpp:269`), and a sibling block there adds `GrenadeItem x GrenadeCount`.

The new `UHoverAuthoring::ConfigureNYCStartingGear` copies `ConfigureCityStartingGear` (`HoverAuthoring.cpp:76-105`), but its path gate is `/Game/HoverPrototype/NYC/` instead of `/ZombieEngine/` (`:79`), and it uses AmmoQuantity 270 and GrenadeCount 2. The Cyber function stays unchanged.

The katana is spawned for every mode (`HoverPilot.cpp:276-286`) and is never sold.

**Frag throw is unverified.** No AFS source throws grenades. A vendor `AZE_GrenadeWeapon` equipped on Vexa would be hidden every tick (`HoverCombatBridge.cpp:445-448`), and it has never been tested on a non-`AZE_PlayerCharacter`. Stage 1 therefore adds `UHoverCombatBridge::ThrowFrag()`: it removes one `Bomb_001`, spawns the DA's projectile class from Vexa's hand socket, and plays a CLS upper-body throw. It is bound to Q-hold only if Q is free on foot; otherwise it uses a key the gameplay slice assigns. If the adapter slips, set GrenadeCount 0 and hide the frag wall buy.

**Deviations from BO7.**
- No Mystery Box. Its pool would be three guns, a 950 roll competes with the PaP path in a ledger already at 72% utilisation, there is no Wonder Weapon asset, and the corridor map has room for only one box spot.
- No rarity track. It needs Salvage, a second currency with no pickup actor. It would also stack to 32x with PaP and invalidate every TTK row. `Rarity` is set on the NYC Ballista copies only, for the tooltip colour.
- Ammo ladder 250/750/1,500/3,000 instead of 250/1,000/2,500/5,000, and vests sold for points instead of Salvage. This collapses BO7's two currencies into one, and it keeps the ammo cost per standard kill (7.4/16.7/26.7/72) below the 90-point award at every band end.

### 3. Pack-a-Punch station

`AHoverPackAPunchStation : AHoverStationBase` uses `bRequiresPower = true` and `TArray<FHoverPaPFamily{ Tiers; Prices; }>`:
- Ballista: `[DA_NYC_Ballista_0.._3]`, prices `[5000, 15000, 30000]`.
- Sidearm: `[DA_NYC_Pistol, DA_NYC_Pistol_PaP]`, price `[5000]`.
- M16 and Heavy Ballista arrive in Stage 2.

An upgrade is a definition swap in the same quickbar slot, because `FZE_InventoryItemInstance` holds only `InstanceId/Definition/Quantity/GridX/GridY` (`ZE_InventoryTypes.h:80-105`). The sequence adds before it removes, and charges last:

```cpp
void AHoverPackAPunchStation::Interact_Implementation(APawn *P) {
  auto *B = Bridge(P); if (!B) return;
  if (!Mode()->IsPowerOn()) { Mode()->Toast(TEXT("NEEDS POWER")); return; }    // zone slice owns IsPowerOn
  UZE_InventoryComponent *Inv = B->Inventory;
  const int32 Slot = Inv->GetActiveQuickbarSlot();
  FZE_InventoryItemInstance Cur; if (!Inv->GetQuickbarItem(Slot, Cur)) return;
  int32 Fam, Tier; if (!Locate(Cur.Definition, Fam, Tier)) return;           // katana, frag: prompt says Cannot upgrade
  if (Tier + 1 >= Families[Fam].Tiers.Num()) return;                         // prompt says MAXED
  const int32 Price = Families[Fam].Prices[Tier];
  if (B->Survival->GetGold() < Price) { Mode()->Toast(TEXT("NOT ENOUGH POINTS")); return; }
  if (!HasFreeGridCell(Inv)) { Mode()->Toast(TEXT("INVENTORY FULL")); return; }
  FGuid NewId;
  if (!Inv->AddItemDefinition(Families[Fam].Tiers[Tier + 1], 1, NewId)) return;   // nothing charged yet
  Inv->AssignInstanceToQuickbar(NewId, Slot);      // swaps old into the vacated grid cell, one broadcast (:633-684)
  Inv->RemoveItemByInstanceId(Cur.InstanceId, 1);  // from the grid; broadcasts OnQuickbarChanged (:528-537)
  B->SavedMagazines.Remove(Cur.InstanceId);        // after the swap, OnUnequipped has already re-saved it (:73-74)
  TryPay(P, Price, TEXT("PACK-A-PUNCH"));          // affordability pre-checked
  B->RefillAllAmmo();                              // BO: PaP refills for free
  Mode()->OnPackAPunched(Fam, Tier + 1, GetActorLocation());
}
```

If the swap is not completed (`GetQuickbarItem(Slot)` does not return `NewId`), the station removes `NewId` and does not charge. That means a full grid never costs the player points or the gun.

What the swap does to ammo: `HandleQuickbarSlotChanged` sees `CurrentWeaponDef != WeaponDef` (`ZE_WeaponComponent.cpp:66-74, 103-112`). `EquipWeaponWithDefinition` (`:118-160`) then synchronously unequips the old gun, spawns a new `AHoverCyberRifle` and calls `SetWeaponDefinition`. Its `bDefinitionChanged` branch sets `CurrentClipAmmo = MagazineSize` (`ZE_WeaponBase.cpp:142-145`). `OnEquipped` finds no saved magazine under the new unique ItemId (`HoverCombatBridge.cpp:56-69`), so the new tier arrives with a full 30-round magazine. All four NYC tiers share `AmmoTypeId Ammo_NYC_Ballista`, so the reserve survives the swap, and `RefillAllAmmo` tops it up to 270/360/450/540. The re-spawn plays the equip montage once, which doubles as the PaP pull-out.

| Tier | Definition | Price | Reserve | Visible change |
|---|---|---|---|---|
| 0 | `DA_NYC_Ballista_0` | - | 270 | default tracer |
| I | `DA_NYC_Ballista_1` | 5,000 | 360 | `NS_ArrowTrail_Fire` tracer, Vefects shockwave at the station |
| II | `DA_NYC_Ballista_2` | 15,000 | 450 | `NS_ArrowTrail_Ice`, reload 1.3 s |
| III | `DA_NYC_Ballista_3` | 30,000 | 540 | `NS_ArrowTrail_Holy` + muzzle light, `MAXED` |

**Presentation.** `FireShot` always spawns the hard-coded `AHoverShotVisual` (`HoverPilot.cpp:1472-1473`), so editing the DAs does not change the tracer. The new `AHoverPilot::SetBallistaTier(int32)` stores a `UNiagaraSystem*` that `AHoverShotVisual::Launch` uses, plus a muzzle-light flag, and applies the tint MID (`MI_NYC_Ballista_PaP1..3`, emissive 0.3/0.6/1.0) to both `ViewGun` and `WorldGun` (`HoverPilot.h:221-222`; `bReview` selects between them at `HoverPilot.cpp:1400`). It is called from `OnPackAPunched` and from every `OnEquipped`, and it is coordinated with the gunplay slice's tracer pass. Prompts: `Pack-a-Punch Ballista -> Tier II (15,000)`, `Pack-a-Punch: needs POWER`, `Ballista MAXED`, `Cannot upgrade Katana`.

### 4. Armor, regeneration and mortality

Vendor armor is not used. `UZE_ArmorDefinition` provides visual slots whose mesh swap lives on `AZE_PlayerCharacter` (`ZE_PlayerCharacter.cpp:1034-1081`), and nothing on Vexa's damage path reads it. The mitigation formula `max(0, Dmg - Defense) * (1 - DamageReduction/100)` (`ZE_HealthTrigger.cpp:316-324`) is lifted into `AHoverPilot::TakeDamage` with `Defense 0`, `DamageReduction 50`, and the reduced half drawn from a plate pool held on the bridge:

```cpp
USTRUCT() struct FHoverArmorState {
  GENERATED_BODY()
  int32 VestTier = 1;          // max slotted plates 1/2/3
  float PlatePool = 50.f;      // 0..50*VestTier
  int32 SparePlates = 0;       // max 3
  float InsertProgress = -1.f; // <0 idle
  float MaxPool() const { return 50.f * VestTier; }
};
```

**Mortality hooks (InitGame cannot do this).** At InitGame no pawn exists yet. `UZE_SurvivalComponent` is created in `UHoverCombatBridge::BeginPlay` (`HoverCombatBridge.cpp:252-255`). `AHoverPilot::BeginPlay` re-reads `Invincible` from GConfig (`HoverPilot.cpp:137`), and `UHoverGraphicsSettings` re-applies it to every pilot (`HoverGraphicsSettings.cpp:186-187`). The fix adds virtuals on the Cyber mode:
- `GetPlayerMaxHealth()` returns 100 (NYC: 150).
- `ForcesMortality()` returns false (NYC: true).
- `HandlePilotDefeated(AHoverPilot*)` returns false (NYC: true).

They are used in four places:
- **`InitGame`** only loads `DA_NYCWaves`, after `Super::InitGame` loads the Cyber DAs (`HoverCyberCity.cpp:85-88`).
- **Bridge `BeginPlay`**, after Survival exists: `Survival->SetMaxHealth(M); Survival->SetHealth(M); Pilot->SandboxHealth = M`. `SetMaxHealth` only clamps downward (`ZE_SurvivalComponent.cpp:58-62`), which is why `SetHealth` follows.
- **`AHoverPilot::BeginPlay`** after line 137, and the `HoverGraphicsSettings.cpp:186-187` loop: `if (ForcesMortality()) bInvincible = false`. `HoverGraphicsMenu` disables the Invincible row (`Pending.bInvincible`, `HoverGraphicsMenu.cpp:125`) in this mode.
- **`HoverReset`** uses `Survival->GetMaxHealth()` instead of the `100.f` literals (`HoverPilot.cpp:578-580`), so other modes keep 100.

**Game over.** No game over exists today. At 0 HP, `TakeDamage` sets `bDefeated` and `DefeatedUntil = +3 s` (`HoverPilot.cpp:1666-1669`), then Tick calls `HoverReset` (`:630-631`), which teleports Vexa and keeps inventory and points. In NYC, the `SandboxHealth <= 0` branch calls `HandlePilotDefeated`, which returns true and skips the reset. The downed slice then runs the 3 s downed pose, then either a self-revive or the death cam, the manual `WBP_ZE_DeathRespawn`, and `RestartGame()`. `RestartGame()` reloads `L_NYC_Survival`, and the bridge is rebuilt in `BeginPlay`.

**Damage order in `AHoverPilot::TakeDamage`** (`HoverPilot.cpp:1634-1669`):
1. The existing `bDefeated`/grace early-out.
2. The hit react.
3. `bInvincible` (always false in NYC).
4. The wave `DamageScale` for `AHoverCyberZombie` causers, which is the 1.0/1.667/2.5 band.
5. New plate absorption: `if (Combat && Combat->Armor.PlatePool > 0) { Absorb = min(Damage*0.5f, PlatePool); PlatePool -= Absorb; Damage -= Absorb; if (PlatePool <= 0) PlateCrack(); }`.
6. Cancel `InsertProgress`, and set `Combat->LastDamageTime = now`.
7. `Super::TakeDamage`, then `SandboxHealth`, then `Survival->SetHealth`.

Check: a 30-damage hit sends 15 to the plate and 15 to health, so the plate breaks on the 4th hit, giving +1-2 hits at R1-10. `ApplyStompKnockdown` (`HoverPilot.cpp:1706-1740`) stuns independently of plates.

**Regeneration (new; nothing exists today).** `UHoverCombatBridge::TickComponent` runs it only when `ForcesMortality()`, while not downed and not dead:
- When `now - LastDamageTime >= RegenDelay()` (6 s, or 3 s with Quick Revive), health rises at 40 HP/s up to `GetMaxHealth()`.
- `SandboxHealth` is synced every tick.
- At or below 40 HP, the HUD draws the countdown.

**Plate insertion.**
- Bindings: hold `G` or hold `Gamepad_Special_Left` (the View button). Neither key, nor `H`, has an `EKeys` reference in `Source/HoverFlight` as of 2026-10-29. D-pad Right stays the CLS compare toggle (`HoverTestController.cpp:212`, `ClsComparison.cpp:165`).
- Duration: 1.2 s, or 0.84 s with Speed Cola, drawn as a ring.
- Availability: only when `SparePlates > 0 && PlatePool < MaxPool()`.
- Cancelled by damage, sprint, fire, mounting the board, or being downed.
- On completion: `SparePlates -= 1` and `PlatePool = min(PlatePool + 50, MaxPool())`.

| Purchase | Actor / field | Price | Rule |
|---|---|---|---|
| Vest II | `AHoverArmorStation.VestTierSold = 2` (North Avenue) | 4,000 | requires tier 1; pool cap 100 |
| Vest III | `AHoverArmorStation.VestTierSold = 3` (Garage Block) | 10,000 | requires tier 2; a tier-1 player is offered Vest II first |
| Plate | any armor station or kiosk, `PlatePrice 50` | 50 | fills `PlatePool` first; when full, adds a spare (max 3) |
| Max Health power-up | new NYC-only branch in `AHoverCyberPowerUp::OnOverlapBegin` (today only Nuke/Danger/MaxAmmo, `HoverCyberCity.cpp:636-648`) | - | `SetHealth(GetMaxHealth())`, SandboxHealth sync, `PlatePool = MaxPool()`; spares untouched |
| Self-revive | downed slice | - | `PlatePool = 0`; spares and tier kept |

HUD: `VestTier` segments under the HP text, spare count `x2`, a 0.3 s white flash plus `SC_ArmorCrack` when a plate breaks, and `G / View: INSERT PLATE` while an insert is possible. The HP label reads `Survival->GetMaxHealth()` instead of `/100` (`HoverPilot.cpp:1823-1825`).

### 5. Perks and Shelter items

**The bridge is the source of truth:** `TArray<FName> PerkPurchaseOrder` plus a `uint8 PerkMask`, keyed on the six perk ids and not on Category. There are no perk items in the grid, so the player cannot discard a paid perk and the perks consume none of the 30 cells. Perk icons are drawn by `AHoverHUD` under the armor bar. `AHoverPerkVendor : AHoverStationBase` has a `PerkId` field and prices at `2500 + 500 * PerkPurchaseOrder.Num()`. Vending actors are `BP_NYC_Perk_<Name>` children that use the mesh from `ZESP/ZE/Actors/Shop/BP_Buy_01`, whose parent is `ZE_WallBuyActor`.

| Perk | Zone | Effect, where it lands |
|---|---|---|
| Juggernog | North Avenue | `SetMaxHealth(250); SetHealth(250); SandboxHealth = 250`; on loss `SetMaxHealth(150)` clamps |
| Quick Revive | South Avenue | `RegenDelay()` 6 -> 3 s; `GetSelfReviveCap()` 3 -> 4 |
| Speed Cola | Survivor Shelter | inside `AHoverCyberRifle::Reload`, after `Super::Reload` and before the montage block (`HoverCombatBridge.cpp:92-108`): `ReloadDuration *= 0.7f; SetTimer(ReloadTimerHandle, this, &AHoverCyberRifle::FinishReload, ReloadDuration, false)`, so montage rate and timer agree; plate insert 0.84 s |
| Deadshot | Underpass | `AHoverCyberZombie::TakeDamage` before `Super`: head bone + non-melee gun + perk -> `Damage *= 1.5` (2.0 x 1.5 = 3.0); aim snap deferred |
| Double Tap | Uptown Barricade | `AHoverCyberRifle::StartFire` override: `Super::StartFire()`; if `bIsFiring && bAutomatic` then `SetTimer(FireTimerHandle, this, &AHoverCyberRifle::HandleFire, 1.f/(FireRate*1.2f), true)` |
| Stamin-Up | Garage Block | speed 900 -> 1,050 / 500 -> 560, frag cap 2 -> 4, `KnockdownDuration()` 2.1 -> 1.4 replacing the literals at `HoverPilot.cpp:1730-1733` |

`FireTimerHandle`, `ReloadTimerHandle`, `ReloadDuration`, `HandleFire` and `FinishReload` are protected members of `AZE_WeaponBase` (`ZE_WeaponBase.h:227-248`). Member pointers must name the derived class (`&AHoverCyberRifle::...`).

Self-revive pops the last `PerkPurchaseOrder` entry and reverts its effect. Prompts: `Buy Juggernog (2,500)`, `Juggernog OWNED`.

**Shelter items** are counters on the bridge, not grid items:
- `SelfRevives`: starts at 1, max `GetSelfReviveCap()`, 1,500 each. The station refuses at the cap with the prompt `Self-Revive FULL (3/3)`.
- `Stims`: carry 2, 500 each.

The stim does not go through `UseConsumableFromQuickbarSlot`. That path heals via reflected `CurrentHP/Health` properties that Vexa lacks (`ZE_InventoryComponent.cpp:1638-1703`), yet still consumes the item (`:1799-1803`). Instead, `H` or a tap of `Gamepad_Special_Left` (under 0.25 s; holding it is the plate insert) calls `Bridge->UseStim()`, which does `Stims -= 1; Survival->ApplyHealthDelta(75); SandboxHealth = Survival->GetHealth()`. The 20 s overheal is deferred.

### 6. Data assets, actors, persistence

The asset ids below were decoded from the .uasset files and are verified:
- All five shared Ballista DAs use `AmmoTypeId Ammo_16` with `DA_AMMO_M16` (ItemId `Ammo_16`).
- `DA_AMMO_M16` has MaxStack 100.
- `DA_Weapon_Pistol_001` uses `Ammo_Pistol`, which equals `DA_AMMO_Pistol`'s ItemId, and saves `bAutomatic false`.
- Ballista `bAutomatic` is not serialized, so it already takes the ctor value true.
- `DA_Weapon_Rifle_001` also uses `Ammo_16`.
- `DA_AFS_Ballista`, `Pistol_001` and `Rifle_001` all have ItemId `01`.

Every NYC copy therefore gets a unique ItemId.

| New asset (under `Content/HoverPrototype/NYC/`) | Base | Key fields |
|---|---|---|
| `DA_NYCWaves` | `UZE_WaveGameModeSettings` | starting kit above; 30 `CustomWaves` rows (rounds slice) |
| `DA_NYC_Ballista_0.._3` | copies of `DA_AFS_Ballista` | ItemId `NYC_Ballista_0..3`, 35/70/140/280, Headshot 2.0, `bAutomatic true`, FireRate 8, Mag 30, MaxReserveAmmo 270/360/450/540, reload 1.5/1.5/1.3/1.2, `AmmoTypeId Ammo_NYC_Ballista`, `WeaponActorClass AHoverCyberRifle`, Rarity Common..Epic |
| `DA_NYC_AMMO_Ballista` | copy of `DA_AMMO_M16` | ItemId `Ammo_NYC_Ballista`, MaxStack 600 (one grid cell), Weight 0.01; keeps the Stage 2 M16 (`Ammo_16`) on its own pool |
| `DA_NYC_Pistol`, `DA_NYC_Pistol_PaP` | copies of `DA_Weapon_Pistol_001` | ItemIds `NYC_Pistol_0/1`, 25/50 and 75/150, semi-auto, mag 12, reserve 96, `Ammo_Pistol`, `AHoverCyberRifle` |
| `DA_NYC_Melee` | copy of `DA_AFS_Melee` | HeadshotMultiplier 1.0 |
| `MI_NYC_Ballista_PaP1..3`, `SC_ArmorCrack` | material instances, SoundCue | tint per tier; plate-break sound |

Grid budget: 4 weapons, 2 ammo stacks, 1 frag stack and 1 free cell for the PaP swap, out of 30.

| Actor class | Parent | Placed instances (zone slice places them) |
|---|---|---|
| `AHoverNYCSurvivalGameMode` | `AHoverCyberCityGameMode` | `InitGame` loads `DA_NYCWaves`; overrides `OnZombieKilled`, `GetPlayerMaxHealth`, `ForcesMortality`, `HandlePilotDefeated` |
| `AHoverStationBase` | `AZE_WallBuyActor` | abstract |
| `AHoverArmoryBuy` | `AHoverStationBase` | Kiosk (Sidearm, Ballista re-buy, ammo, plates), Underpass/Uptown caches, North Avenue frag x2 250; S2 M16, Heavy Ballista |
| `AHoverPackAPunchStation` | `AHoverStationBase` | Underpass x1 |
| `AHoverArmorStation` | `AHoverStationBase` | North Avenue (II), Garage Block (III) |
| `AHoverPerkVendor` | `AHoverStationBase` | six |
| `AHoverShelterStation` | `AHoverStationBase` | Self-Revive 1,500, Stim 500 |
| `AHoverNYCPowerUp` (Stage 2) | `AHoverCyberPowerUp` | `EHoverPowerUpExtra { None, DoublePoints, BonusPoints }`, because `EZE_PowerUpType` (`ZE_PowerUpPickup.h:12-19`) is vendor |

| State | Across rounds | On self-revive | On game over (`RestartGame`, new) |
|---|---|---|---|
| Points, PaP tier, weapons, ammo | kept | kept | reset (map reload) |
| Vest tier, spare plates | kept | kept | tier 1, 0 spares |
| Slotted plates | kept | 0 | 50 |
| Perks | kept | lose most recent | none |
| Self-Revives, Stims | kept | -1 Self-Revive | 1 / 0 |
| Doors, power | kept | kept | closed / off |

### 7. Income and spend path check

The spine ledger includes the Stage 2 Riot share (R9 income 3,069 = 4 Riots x 150 + 25 x 98.75), so it is the **Stage 2 ledger**. Stage 1 has no Riots: each one becomes a 98.75 standard (-51.25 gross). The table below uses the spine's Riot counts (15% R9-16, 20% from R17, rounded; zero on horde and boss rounds). It ignores the ammo that Stage 1 saves by not shooting 2x-HP Riots, so it is a conservative lower bound.

| Round | Stage 2 (spine, expected) | Stage 1 (no Riot) |
|---|---|---|
| R2 | Door 2 -> 132 | identical (no Riot before R9) |
| R8 | PaP I -> 1,341 | 1,341 |
| R9 | Juggernog + Door 5 -> 160 | Juggernog only -> 1,705 (both together would leave -45) |
| R10 | - | Door 5 -> 2,655 (30 Kids = 2,700) |
| R11 | QR + Door 6 -> 1,474 | 1,013 |
| R15 | PaP II -> 3,046 | 2,021 |
| R16 | Speed Cola -> 4,849 | 3,465 |
| R17 | Vest III -> 299 | no purchase -> 8,402 (Vest III would leave -1,598) |
| R18 | Deadshot -> 2,348 | Vest III -> 3,938 |
| R19 | - | Deadshot -> 5,968 |
| R23 | ammo 3,000 + PaP III -> 564 | ammo 3,000 only -> 26,360 |
| R24 | Double Tap -> 4,580 | PaP III -> 4,210 |
| R25 | Stamin-Up -> 4,980 | Double Tap -> 5,110 |
| R26 | - | Stamin-Up -> ~9,200 |
| R30 | 43,164 | about 35,800 (gross -7,331); about 38,500 once the saved Riot ammo (~2,700) is credited |

Stage 1 hits the spine's conservative milestones: PaP III and the last perks arrive one round later, the lowest balance is still R2 (132), and every purchase still lands before the health step that needs it. PaP III arrives at R24, before the R26 +300 band.

The ledger holds because of three mechanisms:
1. Refill-to-full is priced by the owned tier. The vendor's 60-rounds-for-250 path would cost 1,125 per 270-round refill.
2. A PaP purchase refills ammo for free.
3. The guaranteed Max Ammo drops call `RefillAllAmmo`.

The Nuke pays a flat 400 (the ledger counts none), so the per-kill exploit is closed. Plates, Self-Revives and Stims are funded from the surplus. At R2 (132), no plate purchase is needed because the starting plate is full.

### 8. Dependencies, owner amendments and validation

**Cross-slice dependencies.**
- **Enemy slice:** adds `EHoverZombieRole::Boss` (Stage 1) and `Riot` (Stage 2); the Alpha Brute elite keeps `Brute`. It also implements Insta-Kill as Brute x4 / boss x2. Today `HoverCyberCity.cpp:564-566` uses `Damage = max(Damage, Health)` for every zombie, bosses included. It applies the Nuke 25%-of-max exemption before `Super`.
- **Rounds slice:** authors the 30 CustomWaves rows with DamageMultiplier 1.0/1.667/2.5.
- **Zone slice:** provides `IsPowerOn()`, ZoneId gating and door removal.
- **Downed slice:** owns the pose, the self-revive (`PlatePool = 0`, pop last perk) and the death-cam-to-`RestartGame` flow behind `HandlePilotDefeated`.
- **Gunplay slice:** shares the `AHoverShotVisual` tier tracer.

**Owner amendments.**
- `Docs/CONTROLS.txt` lines 69-71 (Cyber crates) stay **unchanged**. A new `NYC - SURVIVAL ECONOMY` block is added with:
  - points 90/115/105/250/500, Nuke +400, start 500;
  - plates 50, vests 4,000/10,000, perks 2,500 + 500n, PaP 5,000/15,000/30,000;
  - refills 250/750/1,500/3,000, reserve 270;
  - `G / View (hold): insert plate`, `H / View (tap): Stim`;
  - the Invincible setting is disabled in this mode.
- `AGENTS.md` lines 26-28 gain the spine's NYC - Survival sentence plus "NYC Survival uses NYC-owned weapon DAs; DA_AFS_Ballista.._5 stay Cyber/Lakeside assets."
- `README.md` notes the Invincible row is disabled in NYC Survival.
- If the owner also wants the gunplay re-tune in Cyber, that is a separate, explicit DA change.

**VALIDATION** (offscreen, `VerifyNYCSurvival.py`, evidence at `D:/AFS_Comparisons/NYCEconomy_<date>`):
- (a) Kill one Standard each by body, head and katana: +90 / +115 / +105.
- (b) Nuke with 10 Standards alive: balance changes by exactly +400.
- (c) PaP I with 5,000: slot 1 holds `DA_NYC_Ballista_1`, clip 30 (checked after the synchronous re-equip), reserve 360, balance -5,000.
- (d) PaP with a full 30-cell grid: balance unchanged, Ballista kept.
- (e) Owned PaP I with reserve 0: refill costs 750, reserve becomes 360.
- (f) Max Ammo: every gun (quickbar and grid) at max reserve, frags at cap, plates untouched.
- (g) A 30-damage hit with `PlatePool 50`: health -15, pool 35; repeat after toggling Invincible in the settings menu: still -15.
- (h) Two perks cost 2,500 then 3,000; Juggernog sets health 250/250.
- (i) Spawn health is 150/150; regen starts 6 s after a hit at 40 HP/s.
- (j) 0 HP with no Self-Revive reaches `RestartGame` and not `HoverReset`; in Cyber, `HoverReset` restores `GetMaxHealth()` (100).
- (k) Stim gives +75 and consumes 1.
- (l) `VerifyCyberWaves.py` and `VerifyNYCExploration.py` stay green, and the hashes of the shared `DA_AFS_Ballista.._5` .uasset files are unchanged.

## 7. Tactical equipment, player survival, downed state and power-ups

This section covers Vexa's survival loop in `L_NYC_Survival`. It runs under a new game mode, `AHoverNYCSurvivalGameMode : AHoverCyberCityGameMode`, at index 4. The index-3 exploration entry is not touched. All numbers come from the spine. Values this section adds are marked **[addition, owner approval]**, and none of them is in the income model. Nothing here edits the 14 patched plugin files. The Stage 2 power-up enum has an AFS-only route.

### Ground truth (code wins)

| Fact | Where |
|---|---|
| `bInvincible` defaults true and is re-read from `[AFS.Graphics] Invincible` in BeginPlay. Applying any graphics setting loops `SetInvincible(Current.bInvincible)` over all pilots. | `HoverPilot.cpp:136-137`, `HoverGraphicsSettings.cpp:186-187` |
| `TakeDamage` checks the gates in this order: bDefeated/grace gate (:1636), hit react (gated by IsOnFoot and !IsActionPlaying, :1637-1648), invincible, wave `DamageScale` for `AHoverCyberZombie` causers via the non-virtual `GetDifficultyMultipliers` (:1653-1660), `Super`, `SetHealth`, then the sandbox `bDefeated` block (:1665+) | `HoverPilot.cpp:1634-1697` |
| `GetDifficultyMultipliers` returns CustomWaves values only on an exact WaveNumber match. Otherwise it returns `AutoDamageScalePerWave^(w-1)`. `ConfigureWave` cannot change it. | `ZE_WaveGameModeSettings.cpp:31-63` |
| `HoverReset` sets health to a literal 100. Home (and R when !Combat) calls it at any time. | `HoverPilot.cpp:578-580, 739` |
| `bKnockedDown`, `bReview`, `bAiming`, `bSuppressFireUntilRelease` and `ImpactPulse` are private. There is no `SetThirdPerson`. Input gates check only `bDefeated`/`bKnockedDown`. | `HoverPilot.h:225-294`, `HoverPilot.cpp:624-649`, `HoverTestController.cpp:128-140` |
| `SetWaveState` (153), `HandleGameOver` (167) and `RestartWaveSession` (171) are **private** (`private:` runs from 118 to `protected:` 181). Only `StopAllZombies` (189) can be called by a subclass. The vendor restart is `OpenLevel(name)` with no options. | `ZE_ZombieWaveGameMode.h:118-189`, `.cpp:207-235` |
| `bSpawnBike` lives on `AHoverGameMode`. Cyber-derived modes always get the bike (`!Mode \|\| Mode->bSpawnBike`). The truck spawns in every mode. | `HoverPilot.h:320`, `HoverTestController.cpp:573-575, 595-619` |
| The grenade weapon casts to `AZE_PlayerCharacter`. Its spawn is private and camera-anchored (+50 cm, about 3.8 m behind Vexa on the 430 cm arm). `StartFire/StopFire/GetCurrentClipAmmo` are protected virtual. | `ZE_GrenadeWeapon.cpp:109-208`, `.h:43-46` |
| `Explode` uses InnerRadius 0, 3D distance to the actor centre, a cover trace on `ECC_Visibility`, and skips the instigator only if `bDamageInstigator` is false and an Instigator is set | `ZE_Projectile_Grenade.cpp:148-330` |
| The `AZE_PowerUpPickup` ctor sets `bCanEverTick = false`. The AFS Nuke applies 999999 damage to every zombie. MaxHealth is unhandled. `RefillAmmo` fills only the equipped weapon. | `ZE_PowerUpPickup.cpp:20`, `HoverCyberCity.cpp:619-654`, `HoverCombatBridge.cpp:328-343` |
| The AI direct chase re-runs `SetTargetEnemy(Player)` and writes LastKnownLocation every 0.5 s. `TakeDamage` and `OnPlayerDetected` also retarget. `Key_CanAttack` is rewritten by `BTService_CheckAttackRange` on every tick. | `HoverCyberCity.cpp:343-350, 413-419, 575-586`, `ZE_BTService_CheckAttackRange.cpp:42,57` |
| `UseConsumable` applies `HealthRestore` itself through reflected HP properties, clamped to max. Selecting a consumable slot unequips the weapon. | `ZE_InventoryComponent.cpp:1771-1832`, `ZE_WeaponComponent.cpp:96-101` |
| Rumble is `PlayDynamicForceFeedback(.18, .06)` on the small motors only, plus `ImpactPulse` | `HoverPilot.cpp:1513, 1533-1548` |

### 1. Equipment roster and quickbar

| Item | Stage | DA (`/Game/HoverPrototype/NYC/Equipment/`) | Effect, H(r) = round health | Fuse / radius | Price, carry |
|---|---|---|---|---|---|
| Frag | 1 | `DA_NYC_Frag` (`UHoverThrowableDefinition`, copied from `DA_Grenade_Frag`, `SM_Bomb`, `NS_Explosion`) | Base 1.5 x H(r). Vendor curve `1 - 0.9(d/500)^5`: about 97 % at 2.5 m, 70 % at 4 m, 10 % at 5 m. Lethal to same-round Standards out to about 4.1 m. Riot pool x0.5. Brute/boss x1.0 with no HP floor: one frag removes a quarter of a Brute, so it never kills one above 25 %. | 3.0 s, radius 500 | 250 per 2, carry 2 (4 with Stamin-Up) |
| Molotov **[addition]** | 2 | `DA_NYC_Molotov` (contact, `NS_Fire_01`) | `AHoverBurnZone` deals 0.3 x H(r)/s for 6 s in 300 cm, with burn speed modifier x0.8. Brute x0.5, boss x0.25. | contact | 500 per 2 |
| Stun flare **[addition]** | 2 | `DA_NYC_Stun` (`NS_Lightning_Damage_Land_Small`) | 400 cm: Standard/Kid/Riot 4 s, Brute 2 s, boss 1 s. Self-blind 1.5 s if Vexa faces it. | 1.5 s | 300 per 2 |
| Noisemaker | 2 | `DA_NYC_Noisemaker` (`SM_WalkieTalkie`) | Zombies within 30 m target it for 10 s, then 1.0 x H(r) in 300 cm. Bosses are immune. | 10 s | 500, carry 1 |

**Quickbar.** Slot 1 is the Ballista. Slot 2 is the secondary (Sidearm, M16 or Heavy Ballista, one at a time; the weapons section owns slot contention). Slot 3 is the Stim, slot 4 is tactical (Stage 2) and slot 5 is the Frag (`GrenadeQuickbarSlot 5`). In survival, D-pad Left cycling (`UHoverCombatBridge::SelectQuickbar(0)`, `:348-360`) is restricted to slots 1-2. Keys 3/4/5 never equip: they use the item (see Stim) or quick-throw. A new `UHoverCombatBridge::GrantStartingGrenades()` reads `StartingEquipment.GrenadeItem/Count/Slot` (`DA_NYC_Frag`, 2, slot 5). That covers the gap at `HoverCombatBridge.cpp:268-282`. Frag purchases that rebuild an emptied stack must re-assign the new instance to slot 5 (shops section).

**Quick-throw.** On foot, `G`, `5` or `Gamepad_RightShoulder` call `Combat->QuickThrow()`. It remembers the active slot, equips slot 5, aims while held and throws on release, then re-selects the previous slot. Clip state survives the swap through `SavedMagazines` (keyed by instance FGuid). The bridge hides `ViewGun/WorldGun` while the active weapon is not an `AHoverCyberRifle` (via `SetView/UpdateGunTransform`), so the rifle mesh does not float during the throw. If Vexa is downed while aiming or cooking, the throw is cancelled and the frag is not consumed, because consumption happens only on commit.

**Throw implementation (AFS-owned).** `AHoverGrenadeWeapon : AZE_GrenadeWeapon`:
- `Tick` calls `AZE_WeaponBase::Tick(DT)` directly, not `Super`. It mirrors `CurrentClipAmmo` from the bridge inventory and draws its own `PredictProjectilePath` arc from the hand. It never sets the inherited `bIsThrowing`, so a `ZE_AnimNotify_ThrowGrenade` cannot reach the vendor camera spawn.
- `CommitHoverThrow` spawns at `GetMesh()->GetSocketLocation("hand_r")`, not `GetMuzzlePosition()`, which is the rifle muzzle. Velocity is the camera-trace aim direction x 1500 + 200 Z. It sets `SpawnParams.Owner = SpawnParams.Instigator = Pilot`, adds the pilot to the projectile's ignore-move actors, calls `InitGrenade(BombStats)` and then `RemoveItemByTypeId(ItemId, 1)`.
- `PlayFireAnimation` calls `LocomotionBridge->PlayAction(As_Grenade_Throw_Anim, .9f, true)`. That is a ZESP-skeleton clip, so a retarget check is required.

`AHoverThrowable : AZE_Projectile_Grenade` overrides `Tick`. One frame before the fuse ends it writes `GrenadeStats.ExplosionDamage = Multiplier x Mode->GetRoundHealth()`. For Fire/Stun/Decoy it spawns the effect actor and sets `bExploded = true` instead of calling `Explode`. Frag damage arrives at `AHoverCyberZombie::TakeDamage` as a plain `FDamageEvent` with `Causer` = the `AHoverThrowable`. In that override, order matters: role-aware Insta-Kill comes first (Standard/Kid/Riot lethal, Brute x4, boss x2), then the throwable's per-role multiplier, then `Super`. The existing Insta-Kill line (`HoverCyberCity.cpp:566-568`) must not kill Brutes from a frag.

### 2. Player survival model

| Parameter | Value | Mechanism |
|---|---|---|
| MaxHealth | 150 (Juggernog 250) | `ConfigurePilot()` runs on the survival mode's first Tick with a valid `Pilot->Combat`, which is after the pawn's BeginPlay re-reads the ini. It calls `Survival->SetMaxHealth(150)`, `SetHealth(150)`, `Pilot->bForceVulnerable = true` (honoured by `SetInvincible`, so the graphics-apply loop cannot re-enable invincibility) and `Pilot->SetThirdPersonView(true)`. |
| Regen | 6 s after the last damage (3 s with Quick Revive), 40 HP/s up to **BaseMaxHealth** | `UHoverSurvivalState::TickComponent` |
| Zombie hit | R1-10: Standard 30, Kid 15, Riot 45, Brute 60 (swing and stomp) + knockdown, Giant Kid 90, StoneGolem 75 + knockdown. R11-30: 50 / 25 / 75 / 100 / 150 / 125. R31+: 75 / 37.5 / 112.5 / 150 / 225 / 187.5 (float damage, shown rounded) | DA `MeleeDamage` x `Mode->GetPlayerDamageScale(Wave)`, a new AFS virtual. The base returns the `GetDifficultyMultipliers` DamageScale (Cyber/Lakeside unchanged). The survival override returns 1.0 / 1.667 / 2.5 by band for every round, including R31+. It replaces the call at `HoverPilot.cpp:1655-1659`. `MeleeDamage` 30/15/45/60/90/75 is authored explicitly on `DA_NYC_*`. The live standards use the vendor default 15. |
| Hits to down, 0 plates | 5 / 3 / 2. With Juggernog: 9 / 5 / 4. | 150 or 250 divided by the band damage |
| Plates | 50 HP each, 50 % of each hit routed to the pool while any remains | `RoutePlates` (armor section owns the pool) runs between band scaling and `Super` |

**Survival-mode order in `AHoverPilot::TakeDamage`:**
1. `bDefeated || IsDowned() ||` grace gate.
2. Skip the early hit react when `SurvivalState` exists.
3. Invincible (forced false).
4. `GetPlayerDamageScale`.
5. Record `Scaled`.
6. `RoutePlates`.
7. `Super`.
8. `SetHealth`.
9. `NotifyDamage(Causer, Scaled, Applied)`, which handles the reaction, regen timer, arrow and haptics.
10. If health is 0, `HandleZeroHealth()` and return before the sandbox block.

The edit replaces `HoverPilot.cpp:1653-1664` and changes `:1636-1637`. Header edits are listed in §7.

**Hit reactions [threshold revised].** A light hit is a scaled pre-plate hit below 34 % of BaseMaxHealth (below 51 at 150 HP, below 85 with Juggernog). It uses the existing `MM_HitReact_Front_Lgt_01`/`Back_Med_01`, 0.65 s cooldown, on foot only. A heavy hit is at least 34 %, or any Brute, Giant Kid or StoneGolem swing. It plays `MM_HitReact_Front_Hvy_01` and calls the public `ApplyStagger(0.4f)`: MaxWalkSpeed x0.5, `bSuppressFireUntilRelease`, no aim. R11 Standards (50) therefore never stagger, and the "900 beats 600" escape holds. The stomp and the hammer call `ApplyKnockdown(Origin, Duration)`, which is `ApplyStompKnockdown` with a parameter: 2.1 s, or 1.4 s with Stamin-Up. Damage is still plate-routed.

**Readability.** A directional arc in `AHoverHUD::DrawHUD` (0.6 s fade). A plate-crack sound. A regen countdown at 40 HP or less. `HP %.0f/%.0f` reading BaseMaxHealth, plus `+N` for overheal.

**Haptics and camera (owner complaint).** A new public `AHoverPilot::PlayHaptic(float Amp, float Dur, bool bLarge)` wraps `PlayDynamicForceFeedback` with large motors enabled.

| Event | Rumble | Camera |
|---|---|---|
| Light hit | 0.25 / 0.08 s, small motor on the hit side | `Cam_Shake_Slight` x0.4 |
| Heavy hit / stomp | 0.6 / 0.25 s, large motor | x1.0 |
| Plate break | two 0.35 / 0.05 s pulses | none |
| Downed | 0.8 / 0.5 s decaying | death-cam shake |
| Frag detonation | 0.7 x (1 - d/1500), large | `Cam_Shake_Slight` within 8 m |
| Power-up pickup | 0.15 / 0.04 s tick | none |

**Stamina.** No drain in Stage 1, matching BO7 unlimited sprint and the spine's 900-vs-600 math. Line 686 becomes `Sprint = Down(Gamepad_LeftThumbstick) || (!bMounted && Down(LeftShift))`. The drain values stay dormant (drain 10/s, regen 20/s after 1.0 s) as an owner option.

**Melee lunge [addition].** `Melee()` steps in toward an `AHoverCyberZombie` that is 160-320 cm away inside a 30° cone: `LaunchCharacter(dir x 450)`, stopping 90 cm short, so the 0.30 s delayed trace lands. Katana damage and the 105-point reward follow the weapons and economy sections.

**Sandbox paths off.** In survival, the Home/R reset is gated by `Mode->AllowsSandboxReset()` (returns false). `HoverReset` uses `Survival->GetMaxHealth()` instead of the literal 100. The pause-menu Invincible row is hidden (`HoverGraphicsMenu.cpp:125,178`), and its detail text (`:51,158`) becomes mode-aware. `AHoverCyberCityGameMode::Tick`'s `SetCanBeDamaged(Cast<AHoverPilot>(Player))` stays: the pilot remains the possessed pawn while she rides the board.

### 3. Downed state machine

```
ALIVE --(health 0)--> DOWNED 3.0 s (fall 0.9 s; with a Self-Revive the get-up QA_StompRecovery 2.1 s fills the rest)
  DOWNED --(Self-Revive held)--> ALIVE + 2.0 s grace     (untargetable 3.0 + 2.0 = 5.0 s, spine)
  DOWNED --(none held)---------> DEATH_CAM 2.0 s real (dilation 0.25) --> GAME_OVER --> AFS restart at R1
```

| State | Entry | Rules | Exit |
|---|---|---|---|
| DOWNED | `HandleZeroHealth()` calls the public `Pilot->EnterDowned(3.f)`. If Vexa is mounted it first calls `ForceDismount`. EnterDowned performs the `ApplyStompKnockdown` cancel sequence (trigger, reload, swing, inventory, aim, slide, prone), sets the private `bDowned`, plays **`MM_Death_Back_01`** (CLS SK_Mannequin) and holds the pose at 0.9 s. `IsIncapacitated()` (bDefeated, bKnockedDown or bDowned) replaces `IsKnockedDown()` in the UpdateInput early-out, `InputKey` swallowing, Melee, ToggleMeleeWeapon, PrepareForRide and the melee hold. `UpdateCameraPosture` lowers the camera by 65 cm while bDowned. | `TakeDamage` returns 0. The AI uses `Desired = nullptr` (see §7). Each zombie holds a ring point 10-15 m from Vexa (angle from instance index plus jitter), so the horde does not converge on a spawn entrance. Spawning never pauses. HUD shows "DOWN". | At 0.9 s, if a Self-Revive is held, enter the get-up. Otherwise go to the death cam at 3.0 s. |
| Get-up (in DOWNED) | Order: `PerkState->LoseMostRecent()` **first**, then `RemoveItemByTypeId(SelfReviveItemId, 1)`, then `SetHealth(0.5 x the new BaseMaxHealth)`, plates 0, then `PlayAction(QA_StompRecovery, 2.1f, false)`. Self-Revives held above a reduced cap are kept, but the Shelter refuses to sell more. | untargetable | At 3.0 s, `ExitDowned()` sets `RespawnGraceUntil = now + 2`. Zombies re-acquire with a staggered 0-1 s delay. |
| DEATH_CAM | `SetGlobalTimeDilation(0.25)`, review camera, death clip continues. The timer is a 0.5 s game-time timer, which is 2.0 s real at 0.25. | input ignored | `Mode->TriggerGameOver()` |
| GAME_OVER | AFS-owned. Sets `bGameOver`, so `AHoverCyberCityGameMode::Tick` stops calling `Super::Tick` and the spawn gating returns early. Calls the protected `StopAllZombies()`. Creates `WaveSettings->DeathWidgetClass` (`WBP_ZE_DeathRespawn`) at Z 100 and `UHoverSurvivalSummaryWidget` (C++, like `UHoverCyberWaveHUD`) at Z 101 showing round, kills, points earned, zones opened and PaP tier. Sets UI-only input and dilation 0.001. The restart button (name verified in the authoring dump; `BTN_Restart` is unverified) binds to the AFS `OnRestartClicked`, which resets dilation and calls `OpenLevel(L_NYC_Survival, "game=/Script/HoverFlight.HoverNYCSurvivalGameMode")`. | none | R1 |

Self-Revive is the `DA_NYC_SelfRevive` item (Tool, stackable, MaxStack 4). The Shelter enforces 3, or 4 with Quick Revive. One is free at start, and more cost 1,500. Solo only: there is no bleed-out bar and no co-op revive.

**BO6/BO7 deviation.** BO solo has a last stand: a sidearm while downed and a player-activated self-revive. The spine's no-input 3.0 s pose was chosen because the Self-Revive is automatic, the downed weapon path would need the bridge to fire while incapacitated, and the CLS crawl clip is unverified (`QA_OwnerCrawlLoop` references the ZombieAnimationPack `SKEL_Mannequin`, so its skeleton must be checked first). A Stage 2 last stand fits the same states; that is the owner's call. **BO7 Field Upgrades** (kill-charged abilities) are not ported: there are no assets, and a second charge resource would muddy the single-currency solo economy. Stage 2 tacticals take that role.

### 4. Stim and Self-Revive

| Item | DA | Use | Rule |
|---|---|---|---|
| Stim | `DA_NYC_Stim` (`UHoverStimDefinition : UZE_ConsumableDefinition`: `StimHeal 75`, `OverhealCap 100`, `OverhealDecay 20`, **`HealthRestore 0`**) | `H`, `3` or hold `Gamepad_FaceButton_Top` call `SurvivalState->UseStim()`. Selecting slot 3 never equips. | Heals +75 up to BaseMaxHealth. The excess goes to a separate `Overheal` float (cap 100) that decays to 0 over 20 s. The component cap is raised only while Overheal > 0. Regen, Max Health, Self-Revive and the HUD all read BaseMaxHealth. Decrement uses `RemoveItemByTypeId(Def->GetEffectiveItemId(), 1)`, which broadcasts `OnInventoryChanged`. Price 500, carry 2. Not usable while downed or mounted. Cancels a reload. 0.9 s upper-body `PlayAction`. |
| Self-Revive | `DA_NYC_SelfRevive` | automatic in DOWNED | See §3 |

### 5. Vehicle rules

| Vehicle | Rule | Mechanism |
|---|---|---|
| Hoverbike | not spawned | `UPROPERTY bSpawnBike = true, bAllowTruckRide = true` added to `AHoverCyberCityGameMode`. The survival ctor sets both false. A helper `ShouldSpawnBike(const AGameModeBase*)` checks either mode class at `HoverTestController.cpp:573-575`. `AHoverExplorationGameMode` is unchanged. |
| Doomsday truck | parked and unmountable (Stage 1) | It still spawns at `:595`. `IsNearTruck()/TryEnterBike` (`:312-340`) return false when `!bAllowTruckRide`. `PrepareForRide` is untouched, because the hoverboard needs it. |
| Hoverboard | Allowed. **No points** while mounted (the kill hook checks `IsOnFoot()`). Damage is not blocked. A scaled hit of at least 34 % BaseMaxHealth, any stomp, or being downed calls the public `ForceDismount(Away)`. ForceDismount uses the HoverReset board-detach lines (`:592-611`) without the teleport, plus a downward trace to the floor, bypassing `FindDismountLocation`. `StompImpact` gains a mounted branch before the `IsOnFoot` gate and the feet-Z test. **[addition]** A zombie within 150 cm applies a 35 % thrust penalty. | The board is the owner's identity feature. Zero points and damage-through remove the safe zone. |

### 6. Power-ups

| Power-up | Effect in NYC | Guaranteed sources |
|---|---|---|
| Max Ammo | `RefillAllAmmo()` (below) | horde clear (at the player's feet), boss death, Brutes 1 and 3 of each heavy round |
| Insta-Kill | 30 s on `BP_NYCPower_InstaKill` only. Cyber's BP is unchanged, which deviates from the spine's wording to protect Cyber City. Role-aware in the zombie override. | random |
| Nuke | The existing loop is edited. Standard/Kid/Riot take lethal damage, Brute/boss take 0.25 x MaxHealth, all through `UHoverNukeDamageType`, which the kill hook pays 0 for. Then `AddGold(400)` once and `DelayNextSpawn(3)`. | random |
| Max Health | A new branch: full heal to BaseMaxHealth plus plates refilled to the tier | Brutes 2 and 4 of each heavy round |
| Speed Boost | 15 s x1.5, unchanged | random |
| Danger | removed | none |
| Double Points / Bonus Points | Stage 2, through AFS `EHoverBonusPowerUp` on the pickup with `PowerUpType None` | random |

**Drop rule (mode-side).** `LootDropChance 0` is set on all `DA_NYC_*`. A drop triggers when points earned reach a threshold that starts at 2,000 and is multiplied by 1.14 after each drop, or on a 3 % roll per kill. There are at most 4 random drops per round, and none in the first 10 kills. **Spine clarification:** guaranteed drops do not count toward the cap. The type comes from a shuffled bag of the five types drawn without replacement and refilled when empty (BO lineage, no invented weights). Drops spawn at the death spot from `OnZombieKilled`.

**Lifetime.** `AHoverNYCPowerUp : AHoverCyberPowerUp` sets `InitialLifeSpan = 26` in its ctor. A 0.25 s timer set in BeginPlay starts blinking at 15 s, because the vendor ctor disables Tick.

**Max Ammo semantics.** For quickbar slots 1-5:
- Each `UZE_WeaponDefinition` with `bUsesAmmo` tops its `AmmoTypeId` pool to `MaxReserveAmmo` (270/360/450/540). Ballista tiers share one pool, so there is one add per pool.
- Non-equipped weapons get `SavedMagazines[Guid] = MagazineSize`. The equipped weapon gets `RefillAmmo(false)`.
- **Only the Frag** is refilled to its carry cap (spine: "grenades"). Tacticals, Stims, plates and Self-Revives are excluded.
- Ammo and grenade DAs need `Weight 0`, or the `MaxWeight 80` gate drops the add.

### 7. C++ skeleton

There are new files `HoverSurvivalState.h/.cpp`, `HoverEquipment.h/.cpp` and `HoverNYCSurvival.h/.cpp`, plus edits to `HoverPilot.h/.cpp`, `HoverCyberCity.h/.cpp`, `HoverCombatBridge.cpp`, `HoverTestController.cpp`, `HoverGraphicsSettings.cpp` and `HoverGraphicsMenu.cpp`.

```cpp
// HoverNYCSurvival.h (members this section needs; zones/rounds sections add theirs)
UCLASS()
class HOVERFLIGHT_API AHoverNYCSurvivalGameMode : public AHoverCyberCityGameMode
{
    GENERATED_BODY()
  public:
    AHoverNYCSurvivalGameMode(); // bSpawnBike = bAllowTruckRide = false
    virtual void InitGame(const FString &Map, const FString &Options, FString &Error) override; // Super, then load DA_NYCWaves + Encounters (base hard-codes DA_CyberWaves)
    virtual void Tick(float DT) override;                    // ConfigurePilot once; DelayNextSpawn by skipping Super::Tick
    virtual float GetPlayerDamageScale(int32 Wave) const override; // 1.0 / 1.667 / 2.5
    float GetRoundHealth() const;           // H(r) x Tuning.Health
    FVector GetRetreatPoint(const AActor *Zombie) const;    // ring 10-15 m around Vexa
    AActor *GetActiveDecoy() const { return Decoy.Get(); }
    void DelayNextSpawn(float Seconds);
    void OnZombieKilled(AHoverCyberZombie *Z, AActor *Causer, bool bHead, const UDamageType *Type);
    void TriggerGameOver();
    bool AllowsSandboxReset() const { return false; }
  private:
    void ConfigurePilot(AHoverPilot *Pilot);
    UFUNCTION() void OnRestartClicked();
    TWeakObjectPtr<AActor> Decoy;
    float SpawnBlockedUntil = 0, PowerUpThreshold = 2000;
    int32 RandomDropsThisRound = 0, KillsThisRound = 0;
};
// HoverCyberCity.h additions: virtual float GetPlayerDamageScale(int32) const; bool bGameOver = false;
// UPROPERTY(EditDefaultsOnly) bool bSpawnBike = true, bAllowTruckRide = true;
// AHoverCyberZombie: float StunnedUntil = 0, SpeedModifier = 1.f;

// HoverPilot.h public additions
UPROPERTY() TObjectPtr<UHoverSurvivalState> SurvivalState;
bool bForceVulnerable = false;               // SetInvincible(true) ignored when set
void SetThirdPersonView(bool b) { bReview = b; SetView(); }
void EnterDowned(float Duration); void ExitDowned(); bool IsDowned() const { return bDowned; }
bool IsIncapacitated() const { return bDefeated || bKnockedDown || bDowned; }
void ApplyStagger(float Seconds);
bool ApplyKnockdown(const FVector &Origin, float Duration);
void ForceDismount(const FVector &Away);
void PlayHaptic(float Amp, float Dur, bool bLarge);
// private: bool bDowned = false;

// HoverSurvivalState.h
UENUM() enum class EHoverDownedState : uint8 { Alive, Downed, DeathCam, GameOver };
UCLASS()
class HOVERFLIGHT_API UHoverSurvivalState : public UActorComponent
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere) float RegenDelay = 6.f, RegenRate = 40.f, DownedDuration = 3.f,
        FallHold = .9f, ReviveGrace = 2.f, KnockdownDuration = 2.1f;
    UPROPERTY(EditAnywhere) FName SelfReviveItemId = TEXT("NYC_SelfRevive");
    float BaseMaxHealth = 150.f, Overheal = 0.f;
    float RoutePlates(float Damage);
    void NotifyDamage(AActor *Causer, float Scaled, float Applied); // reaction, regen, arrow, haptics
    bool HandleZeroHealth();
    bool IsDowned() const { return State != EHoverDownedState::Alive; }
    void UseStim();
    virtual void TickComponent(float DT, ELevelTick, FActorComponentTickFunction *) override;
  private:
    void BeginGetUp(); void EnterDeathCam();
    EHoverDownedState State = EHoverDownedState::Alive;
    float StateUntil = 0, LastDamageTime = -100;
};

// HoverEquipment.h
UENUM() enum class EHoverThrowableEffect : uint8 { Frag, Fire, Stun, Decoy };
UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverThrowableDefinition : public UZE_WeaponDefinition
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditDefaultsOnly) EHoverThrowableEffect Effect = EHoverThrowableEffect::Frag;
    UPROPERTY(EditDefaultsOnly) float DamageMultiplierOfRoundHealth = 1.5f;
    UPROPERTY(EditDefaultsOnly) float BruteMultiplier = 1.f, BossMultiplier = 1.f, RiotPoolMultiplier = .5f; // Molotov .5/.25
    UPROPERTY(EditDefaultsOnly) float EffectRadius = 300.f, EffectDuration = 6.f, BurnPerSecondOfRoundHealth = .3f;
    UPROPERTY(EditDefaultsOnly) float StunStandard = 4.f, StunBrute = 2.f, StunBoss = 1.f;
    UPROPERTY(EditDefaultsOnly) int32 CarryCap = 2, PricePerPair = 250;
};
UCLASS()
class HOVERFLIGHT_API AHoverGrenadeWeapon : public AZE_GrenadeWeapon
{
    GENERATED_BODY()
  protected:
    virtual void StartFire() override; virtual void StopFire() override;
    virtual int32 GetCurrentClipAmmo() const override;
  public:
    virtual void Tick(float DT) override;      // AZE_WeaponBase::Tick, own arc from hand_r
    virtual void PlayFireAnimation() override;
    void CancelThrow();                        // downed mid-aim: nothing consumed
  private:
    void CommitHoverThrow();                   // Owner = Instigator = Pilot, hand_r spawn
};
UCLASS()
class HOVERFLIGHT_API AHoverThrowable : public AZE_Projectile_Grenade
{
    GENERATED_BODY()
  public:
    UPROPERTY() TObjectPtr<const UHoverThrowableDefinition> Definition;
    virtual void Tick(float DT) override;
};
```

```cpp
// HoverCyberCity.cpp, AHoverCyberZombieAI::Tick: REPLACE the direct-chase block 343-350
auto *Pilot = Cast<AHoverPilot>(Player);
const auto *Survival = GetWorld()->GetAuthGameMode<AHoverNYCSurvivalGameMode>();
AActor *Desired = Player;
if (Pilot && (Pilot->IsDowned() || GetWorld()->GetTimeSeconds() < Pilot->GetGraceUntil()) && Survival)
    Desired = nullptr;
else if (AActor *D = Survival ? Survival->GetActiveDecoy() : nullptr;
         D && FVector::Dist(D->GetActorLocation(), GetPawn()->GetActorLocation()) < 3000.f)
    Desired = D;
if (auto *Board = GetBlackboardComponent())
{
    if (!Desired) { Board->ClearValue(Key_TargetEnemy);
                    Board->SetValueAsVector(Key_LastKnownLocation, Survival->GetRetreatPoint(GetPawn())); }
    else { if (Board->GetValueAsObject(Key_TargetEnemy) != Desired) SetTargetEnemy(Desired);
           Board->SetValueAsVector(Key_LastKnownLocation, Desired->GetActorLocation()); }
}
// Same Desired rule in AHoverCyberZombie::TakeDamage (575-586) and OnPlayerDetected (413-419).
// END of Tick, after the speed-tier write (372-382 replaced by the per-instance tier):
Move->MaxWalkSpeed = TierSpeed * Zombie->SpeedModifier;        // burn x0.8
const bool Stunned = Zombie->StunnedUntil > GetWorld()->GetTimeSeconds();
if (Stunned && !bLogicPaused) { GetBrainComponent()->PauseLogic(TEXT("Stun")); StopMovement(); bLogicPaused = true; }
else if (!Stunned && bLogicPaused) { GetBrainComponent()->ResumeLogic(TEXT("Stun")); bLogicPaused = false; }
```

**Kill hook.** The vendor binds `OnDeath` privately (`ZE_ZombieWaveGameMode.cpp:552`). AFS reuses the existing `WasAlive && bIsDead` branch in `AHoverCyberZombie::TakeDamage` (`HoverCyberCity.cpp:587-588`) and calls `Mode->OnZombieKilled` there. The bone/causer check runs before `Super` consumes the point event.

### 8. Editor steps

1. Create `DA_NYC_Frag` by copying `DA_Grenade_Frag`, then set:
   - `WeaponActorClass AHoverGrenadeWeapon`, `ProjectileClass AHoverThrowable`, `NS_Explosion`
   - `DamageableObjectTypes [Pawn]`, **`bDamageInstigator false`**, **`bUseCoverDamageReduction false`** (zombie meshes block Visibility and would shield each other at 0.3)
   - Radius 500, exponent 5, min 0.1, fuse 3
   - **`BruteMultiplier 1.0`, `BossMultiplier 1.0`**
   - `Weight 0`, MaxStack 4

   Stage 2: Molotov (0.5/0.25), Stun, Noisemaker.
2. Create `DA_NYC_Stim` (`HealthRestore 0`, `StimHeal 75`) and `DA_NYC_SelfRevive` (MaxStack 4, Weight 0).
3. On `DA_NYCWaves`, set Grenade `DA_NYC_Frag`/2/slot 5 and `DeathWidgetClass WBP_ZE_DeathRespawn`. Restart is AFS-owned. Also set the `L_NYC_Survival` World Settings GameMode Override to the survival mode as a second guard. Add index 4 to the travel mapping at `HoverTestController.cpp:116-119`.
4. Create the `BP_NYCPower_*` children of `AHoverNYCPowerUp` (InstaKill 30, Speed 15). Set `LootDropChance 0` on every `DA_NYC_*` zombie DA and author MeleeDamage 30/15/45/60/90/75 on them.
5. Dump the IMC mappings of `BP_Vexa_CLS_Parkour` and assert that G, H, 3/5, `Gamepad_FaceButton_Top`, `Gamepad_RightShoulder` and LeftShift are unbound on foot. `HoverTestController::InputKey` consumes the new keys before `Super`. Also dump the death widget's button names.
6. Dump all DAs to `D:/AFS_Comparisons/NYCSurvival_<date>/` and record them in `Docs/NYC_SURVIVAL_<date>.txt`.

### 9. Cross-section dependencies

- **Armor:** `RoutePlates`, the plate pool, plate refill on Max Health, and the starting 1-plate vest.
- **Perks:** Juggernog sets BaseMaxHealth 250. Quick Revive sets regen 3 s and Self-Revive cap 4. Stamin-Up sets knockdown 1.4 s, frag carry 4 and sprint 1,050. `PerkState->LoseMostRecent()` is called on Self-Revive.
- **Economy:** 0 points when mounted or for Nuke kills. The points-earned counter feeds the drop threshold. `OnZombieKilled` is the single hook.
- **Rounds/adapter:** `GetRoundHealth` uses the per-actor frozen HealthScale times `Tuning.Health`. Also `DelayNextSpawn`, `bGameOver` and `GetPlayerDamageScale`.
- **AI/crowding:** BT behaviour when TargetEnemy is cleared (MoveTo LastKnownLocation, then hold), speed-tier write order, `StunnedUntil`/`SpeedModifier`.
- **Weapons:** `SavedMagazines` keyed by FGuid, slot-2 contention, Ballista re-buy slot.
- **Shops:** re-assign frag instances to slot 5. The Shelter enforces the Self-Revive cap.
- **Heavy/boss:** guaranteed-drop spawn location.

### 10. Owner amendments added by this section

- `Docs/CONTROLS.txt`:
  - Survival rows for G/5/R1 quick-throw, H/3/Y stim, Shift sprint on foot, the downed/self-revive flow, the hoverboard rule ("no points, takes damage, knocked off by heavy hits"), the power-up list and the 26 s lifetime.
  - L11 "Other levels retain all three vehicles" excludes NYC - Survival.
  - L13 Invincible gains "(forced Off in NYC - Survival)".
- `AGENTS.md` L26-28 and `README.md` per the spine. Add "Vexa may be downed and the match restarts from R1 in NYC - Survival only".
- `HoverGraphicsMenu.cpp`: the `% 4` to `% 5` change (:123), `PendingLevel` (:70) and the mode-aware Invincible text (:51,158), unless the level section owns them.
- `.gitignore` whitelist for `Docs/NYC_SURVIVAL_<date>.txt`.
- `VerifyNYCSurvival.py` asserts MaxHealth 150, bInvincible false, frag slot 5 count 2, the survival mode on restart, and zero zombies at index 3.

### VALIDATION

- **Offscreen runs:** `Scripts/Build.ps1`, then `UnrealEditor-Cmd ... -game -NullRHI`, never concurrent. Expected log lines:
  - `HOVER_SURVIVAL downed=1`
  - `HOVER_SURVIVAL revive consumed left=0`
  - `HOVER_SURVIVAL gameover round=N`
  - `HOVER_THROW spawned at hand dist<60cm`
  - `HOVER_POWERUP MaxAmmo pools=[...]`
- **Damage asserts:**
  - With 0 plates, Vexa takes exactly 5 Standard hits at R1, 3 at R11 and 2 at R31.
  - With 1 plate, 7 hits at R1 and 4 at R11.
  - With Juggernog, 9 / 5 / 4.
  - R31 damage scale is 2.5 even though no CustomWaves row exists.
- **Frag asserts:**
  - A R5 Standard (200 HP) at 2 m takes about 297 damage and dies.
  - A centre-hit frag leaves a R8 Brute (1,650) at 1,237.5 (75 %).
  - A frag at Vexa's feet deals 0 to her.
  - Two Standards in line both take uncovered damage.
- **Regen asserts:** regen starts 6.0 s after the last hit. From 1 HP it fills in 3.725 s. After a Self-Revive it goes 75 to 150 in 1.875 s. It never fills Overheal.
- **Downed asserts:**
  - No zombie has Vexa as `TargetEnemy` during DOWNED + grace (5.0 s).
  - Home, fire and mount input are ignored while downed.
  - A downed rider is dismounted first.
- **Power-up asserts:**
  - Nuke leaves Brutes and bosses alive at 75 % and pays exactly +400.
  - Max Ammo refills a non-equipped Ballista tier through the shared AmmoTypeId and does not refill tacticals.
- **Mode asserts:**
  - Applying a graphics setting in survival leaves bInvincible false.
  - Game over and restart log `AHoverNYCSurvivalGameMode` and R1, not HoverGameMode.
  - No bike exists. The truck refuses entry.
  - The hoverboard still mounts.
- **Evidence:** before/after DA dumps go to `D:/AFS_Comparisons/NYCSurvival_<date>/`. `FHoverZombieTuning.Health` must be 1.0 for the asserts.

## 8. NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout

### Scope and ground truth

The survival map is a new owned persistent level, `/Game/HoverPrototype/Maps/L_NYC_Survival`. It is a duplicate of `L_NYC_Explore.umap` and streams the same four vendor sublevels as always-loaded: `CityMeshes`, `SetDressing`, `Lighting_Main` and `Lighting_Main_Directional`. Vendor actors are left untouched. Everything in this section is an owned actor placed in that level.

What is known about the footprint:
- The roadway is a north-south corridor at x ~100-450, running from y ~3,000 to ~7,200, so about 42 m long.
- The vendor PlayerStart is at (271, 5241, 162), yaw -90.
- The owned `AFS_TruckStart` marker is at (200, 5900, 120.54), which is inside North Avenue.
- Vendor `SetDressing` holds 59 `BP_T_Wall_Double_a_BarbedWire`, 8 corner barricades, 6 `BP_Kiosk`, 1 `BP_SurvivorShelter` and 9 BlockingVolumes.
- There is no navmesh, no `AZE_ZombieSpawnPoint`, and no door or zone actor.

**The survey (section 9) is a hard prerequisite.** Every extent, spawner count and NYC band value below is provisional until the survey freezes `Scripts/nyc_survival_layout.json`.

| Fact | Where |
|---|---|
| `AZE_ZombieSpawnPoint` has only `bIsEnabled` (default true) and `TArray<FName> SpawnTags`. No code reads `SpawnTags`. | `Plugins/.../Public/World/ZE_ZombieSpawnPoint.h:38,42` |
| The vendor picks with `RandRange` among enabled points and falls back to `APlayerStart`. `GetRandomSpawnPoint` and `SpawnZombie` are private and non-virtual. | `ZE_ZombieWaveGameMode.cpp:393-423`, `.h:146,151` |
| The adapter `Tick` runs these gates in order: band `Dist2D >= 1400 && <= 10000` (`:289`), then nav reach on foot only (`:292-294`), then cone LOS (`:300-301`), then 300 cm pawn clearance (`:302-308`). It always writes `bIsEnabled = false` (`:309`), uses the LRU score (`:313-315`), enables exactly one point (`:322-323`), and skips `Super::Tick` while `ActiveSpawnCount == 0` (`:328-329`). | `HoverCyberCity.cpp:263-330` |
| `CanReachPlayer` uses `TestPathSync` with no partial paths and a 1 s / 200 cm cache. It is private. So are `ActiveSpawnCount`, `SpawnLastUsed`, `Encounters` and `bLakeside`. | `HoverCyberCity.cpp:155-182`, `.h:67-80` |
| `InitGame` always loads `DA_CyberWaves` and `DA_CyberEncounters`. `ZombieClass` exists only in the `BP_CyberWaves` Blueprint defaults. | `HoverCyberCity.cpp:85-98` |
| `GetEncounterLabel` is a non-virtual `BlueprintPure`. `GetEffectiveSpawnRate` returns an interval in seconds and is protected virtual. | `HoverCyberCity.h:55,65`; `.cpp:200-226` |
| Interaction: the trace focuses any actor that implements the interface (`:192`). `CanInteract` is checked only in `TryInteract` (`:303`). The prompt is `"Hold X / F: " + text`. | `ZE_InteractionTraceComponent.cpp:192,303`; `HoverCombatBridge.cpp:427-431` |
| `AZE_InteractableBase` is Abstract and Blueprintable and implements only GetInteractText, CanInteract, Interact and OnFocusStart/End. RequiresHold and GetHoldDuration fall back to the UHT defaults. | `ZE_InteractableBase.h:26-84`; `ZE_InteractableInterface.h:27-61` |
| `AZE_WallBuyActor::ExecutePurchase` is non-virtual and `PlayerHasWeapon` is private. The overridable virtuals are `CanInteract_`, `Interact_` (which calls ExecutePurchase), `GetInteractText_`, `RequiresHold_` and `GetHoldDuration_`. | `ZE_WallBuyActor.h:33,37-46,81`; `.cpp:38-40` |
| `TraceWeaponRay` uses ECC_Visibility and skips only `AZE_PickupBase` and `AZE_PowerUpPickup`. The board floor and contact traces also use ECC_Visibility. | `HoverPilot.cpp:63-75,1017-1018,1137-1156` |
| The bike spawns when `!GetAuthGameMode<AHoverGameMode>() \|\| bSpawnBike`. The zombie mode is not an `AHoverGameMode`, so the bike spawns there. The truck spawns every time and stays mountable. | `HoverTestController.cpp:572-605`; `HoverPilot.cpp:1804-1807` |
| `AddCityNavigation` is gated to `CyberCity`/`L_Showcase` (`:200`). It passes `Size` to `UCubeBuilder` as full dimensions and forces `RuntimeGeneration = Dynamic`. | `HoverAuthoring.cpp:197-243` |

### 1. Zone graph

There are seven zones, six doors, 3-4 spawners per zone (25 in total) and one jump pad. Graph edges: 0-1, 0-2, 1-4, 2-3, 2-5, 2-6. The jump pad 6->0 is one-way and works only after Power. It is not a door, so it never adds Plaza to the Garage pool or the Garage to the Plaza pool.

The active pool is the player's zone plus every neighbour one hop away through an opened door (BO3 zone-manager rule). It is rebuilt every 1 s. A spawner's tag names the zone it serves, not where it stands, so spawners may sit outside their zone volume.

| Order | ZoneId | Name | Door (price, from) | Extent (cm, provisional) | Contents | Spawners |
|---|---|---|---|---|---|---|
| 0 | `Plaza` | Checkpoint Plaza (spawn) | - | x 100-450, y 4,800-5,700 | vendor PlayerStart; `AHoverArmoryStation` on a `BP_Kiosk` copy (Sidearm 500, Ballista re-buy 1,750, ammo refill, plates 50); sandbags (`SM_Sandbags_Straight_01/02`) | 4 |
| 1 | `SouthAve` | South Avenue | D1 750, from Plaza | x 100-450, y 3,600-4,800 | Quick Revive; M16 wall buy 1,250 (S2); two `BPC_A_Entrance` alcoves; hosts the 2 Underpass entrance-side spawners beyond D4 | 4 |
| 2 | `NorthAve` | North Avenue | D2 1,000, from Plaza | x 100-450, y 5,700-6,600 | Juggernog; armor station vest II 4,000 / plates 50; Frag 250; truck lane with the pickup parked at `AFS_TruckStart` (200, 5900), unmountable; `BP_SUV0x` cover; doors 3 (east), 5 (north), 6 (west); hosts the 2 Shelter entrance-side spawners beyond D3 | 4 |
| 3 | `Shelter` | Survivor Shelter | D3 1,250, from NorthAve | x 600-1,100, y 5,900-6,400 | Power (`AHoverPowerSwitch`); Speed Cola; Shelter station (Self-Revive 1,500, Stim 500, Noisemaker 500 S2) | 3 (1 inside, 2 outside D3) |
| 4 | `Underpass` | Underpass | D4 1,500, from SouthAve | x 100-450, y 3,000-3,600 | `AHoverPackAPunchStation` (needs Power); Deadshot; ammo cache | 3 (1 inside, 2 outside D4) |
| 5 | `Uptown` | Uptown Barricade | D5 1,750, from NorthAve | x 100-450, y 6,600-7,200 | Double Tap; ammo cache; Heavy Ballista 3,000 + trap 750 (S2); barrier-island loop; two spawners tagged `Boss` | 4 |
| 6 | `Garage` | Garage Block | D6 2,000, from NorthAve | x -400-100, y 5,700-6,200 | vest III 10,000 / plates 50; Stamin-Up; `AHoverJumpPad`; `SM_PhoneBooth` exfil dressing (S2) | 3 |

The door total is 8,250. The minimum spend before PaP I is D1+D2+D3+D4 = 4,500.

The Garage box is moved 100 cm north of the spine placeholder (y 5,600 -> 5,700) so that it no longer shares a door-less seam with Plaza. In Stage 1 the pickup stays parked in the NorthAve truck lane. Moving the `AFS_TruckStart` copy into the Garage is part of the Stage 2 exfil work.

```
            y 7200  +-----------------------------+
                    |  [5] UPTOWN   S S  Sb Sb    |   Sb = 'Boss'-tagged spawner
            y 6600  +---------==D5 1750==---------+
  x -400..100       |  [2] NORTH AVENUE  S S      |      x 600..1100
  +-----------+     |   truck lane (parked) S3 S3 |==D3=+-------------+
  | [6] GARAGE|=D6==|   Jugg  VestII  Frag  S S   | 1250| [3] SHELTER |
  |  VestIII  | 2000|                             |     |  POWER  S3  |
  |  jumppad->Plaza |                             |     +-------------+
  +-----------+     +---------==D2 1000==---------+
            y 5700  |  [0] CHECKPOINT PLAZA S S S S|  PlayerStart (271,5241) facing -y
            y 4800  +---------==D1  750==---------+
                    |  [1] SOUTH AVENUE  S S S S  |
                    |               S4 S4         |   S3/S4 = Shelter/Underpass-tagged, outside their room
            y 3600  +---------==D4 1500==---------+
                    |  [4] UNDERPASS  S4  PaP     |
            y 3000  +-----------------------------+
```

### 2. Hooks on the owned adapter (`HoverCyberCity.h/.cpp`)

Every hook defaults to today's behaviour, so Cyber and Lakeside are unchanged. The edits below are the only changes to `AHoverCyberCityGameMode`.

```cpp
public:
    UFUNCTION(BlueprintPure) virtual FString GetEncounterLabel() const;      // was non-virtual
    UFUNCTION(BlueprintPure) virtual bool AllowsBike() const { return true; }   // controller :574
    UFUNCTION(BlueprintPure) virtual bool AllowsTruckEntry() const { return true; } // IsNearTruck gate
    UFUNCTION(BlueprintPure) AZE_ZombieSpawnPoint *GetLastChosenSpawner() const { return LastChosen.Get(); }
protected:
    virtual FVector2D GetSpawnBand() const { return FVector2D(1400.f, 10000.f); }  // used at :289
    virtual bool IsSpawnerEligible(const AZE_ZombieSpawnPoint *Point) const { return true; }
    virtual bool RelaxVisibilityGate() const { return false; }                 // skips :300-301
    virtual bool RelaxPawnClearance() const { return false; }                  // skips :302-308
    virtual float ScoreSpawner(const AZE_ZombieSpawnPoint *Point, float Distance, float LruScore) const
    { return LruScore; }                                                       // used at :313-315
    void SetEncounterSettings(UHoverCyberEncounterSettings *Value) { Encounters = Value; }
    TWeakObjectPtr<AZE_ZombieSpawnPoint> LastChosen;                           // set at :322
```

The hook calls go into the loop as `bool Safe = IsSpawnerEligible(*It) && Distance >= Band.X && Distance <= Band.Y;`. The loop has no early `continue`, so `It->bIsEnabled = false` (`:309`) still runs for every point, and an ineligible point can never stay enabled for the vendor `RandRange`.

`HoverTestController.cpp:574` becomes `(!Mode || Mode->bSpawnBike) && (!Cyber || Cyber->AllowsBike())`, where Cyber is `GetAuthGameMode<AHoverCyberCityGameMode>()`. `IsNearTruck()` returns false when `!Cyber->AllowsTruckEntry()`.

### 3. `AHoverNYCSurvivalGameMode` and `BP_NYCSurvival`

The new files are `HoverNYCSurvival.h/.cpp`. The class is `AHoverNYCSurvivalGameMode : AHoverCyberCityGameMode`.

**`InitGame`.** It calls Super first. It then overwrites `WaveSettings` with `/Game/HoverPrototype/NYC/DA_NYCWaves`, and calls `SetEncounterSettings` with `/Game/HoverPrototype/NYC/DA_NYCEncounters`, which holds the Cyber-derived `DA_NYC_Standard01-04`, `DA_NYC_Kid`, `DA_NYC_Brute` and the new asset `DA_NYC_AlphaBrute`. It re-applies `WaveHUDClass` as at `:97-98`.

Two rosters are excluded. The Lakeside roster is isolated by owner rule. The Cyber DAs are duplicated, never referenced directly.

**`BP_NYCSurvival`.** This is a Blueprint child at `/Game/HoverPrototype/ZombieEngine/BP_NYCSurvival`. It copies the `BP_CyberWaves` defaults, most importantly `ZombieClass`. Its `_C` path is used both as the WorldSettings GameMode Override and in `?game=`.

**Overrides:**

- `AllowsBike()` returns false, and `AllowsTruckEntry()` returns false.
- `GetSpawnBand()` returns provisional `{800, 6000}`. The final value is set by the survey and recorded in VALIDATION as an intentional difference from the Cyber/Lakeside band `{1400, 10000}`.
- `IsSpawnerEligible(P)` returns `P->SpawnTags.Num() && Pool.Contains(P->SpawnTags[0])`.
- `GetEncounterLabel()` returns `DisplayName` for 3 s after a zone change. After that it returns `Super`.
- `GetEffectiveSpawnRate()` returns `Super` x 0.5 while the generator hold is active. A lower interval means spawning is twice as fast. It returns x2.0 while a boss lives (spine).
- There is no owned PlayerStart. The vendor start in the always-loaded `SetDressing` is the only one, as it is in `L_NYC_Explore` today. The skip guard at `:328-329` is never removed, so the vendor PlayerStart fallback for zombies can never run.

**Stall guard.** The 4 s stage is the spine's rule. The 8 s and 12 s stages are deliberate extensions, because on a 42 m corridor the cone-only guard cannot recover.

| Time with `ActiveSpawnCount == 0` while quota remains | Stage |
|---|---|
| 4 s | `RelaxVisibilityGate()` returns true. Band and reach gates are kept. |
| 8 s | `Pool` widens to every opened zone, and the band minimum drops to 600 cm. |
| 12 s | `RelaxPawnClearance()` returns true, and `ScoreSpawner` returns `Distance`, so the farthest reachable opened spawner wins. |
| Still zero after 12 s (only possible when nav is broken) | Log `AFS_SpawnStall` once per round and keep waiting. The automation asserts that this never fires. |

**Pack lock and boss entrance.** Both go through `ScoreSpawner`. This layer owns the spawner choice; the rounds slice owns the timing.

- While `PackRemaining > 0`, the pack anchor spawner returns `FLT_MAX`, so it stays `Chosen` for a horde pack of 4. Catch-up (2 per interval) is delivered by halving the interval in `GetEffectiveSpawnRate`, because the vendor spawns one zombie per timer tick.
- While the rounds slice reports `IsBossSpawnPending()` (from the 40% kill threshold until the boss has spawned), the pool is every opened zone, the cone is relaxed, and `ScoreSpawner` returns `Distance + (HasTag Boss ? 1e5 : 0)`. With Door 5 open, the boss therefore enters from Uptown. Otherwise it enters from the farthest opened spawner.
- The boss still spawns through vendor `SpawnZombie`, so `ZombiesAlive` stays correct.

**Straggler.** A zombie whose 2D position has been outside every pool zone for 20 s, or more than 60 m from the player for 20 s (spine), is handed to the rounds slice's re-queue (the active implementation relocates the living actor and restores full health on success). On this map the zone test is the one that matters, because 60 m rarely occurs on a 42 m corridor.

### 4. `AHoverZoneVolume` and player-zone tracking

The class lives in `HoverNYCZones.h`. Extents are numeric `EditAnywhere` properties applied in `OnConstruction`, so Python can author them.

```cpp
UCLASS()
class HOVERFLIGHT_API AHoverZoneVolume : public AActor
{
    GENERATED_BODY()
  public:
    AHoverZoneVolume(); // Box: ECC_Pawn Overlap only, CanEverAffectNavigation false
    virtual void OnConstruction(const FTransform &T) override; // Box->SetBoxExtent(Extent)
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") FName ZoneId;
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") int32 Order = 0;
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") FText DisplayName;
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") TArray<FName> Neighbours;
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") FVector Extent = FVector(175, 450, 5000); // tall: covers the board
    UPROPERTY(EditAnywhere, Category = "AFS|Zone") TArray<FVector> ProbePoints; // >= 3 nav floor points
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> Box;
};
```

The mode binds `OnComponentBeginOverlap` and `OnComponentEndOverlap` on every Box.

- The handler ignores any actor that is not `UGameplayStatics::GetPlayerPawn(this, 0)`. Zombies are pawns too.
- On either event, `CurrentZone` is the highest-`Order` opened zone whose box contains the pawn's 2D location. If no opened box contains it, `CurrentZone` keeps its last value.
- `CurrentZone` never resolves to an unopened zone, whether the pawn is gliding, vaulting or airborne. A pool can therefore never include spawners behind a closed door.
- The tall boxes plus the door board-blocks (section 5) are the door-gating rule for the hoverboard. The spine keeps the board usable, so disabling it is not the chosen fix.

### 5. `AHoverZoneDoor`

The class lives in `HoverNYCZones.h`. It derives from the owned `AHoverInteractable : AZE_InteractableBase`. That base tags its `Trigger` component `AFS_InteractTrigger` and starts it 30 cm above the floor so that board floor traces never read it as ground. `TraceWeaponRay` gains `|| Hit.GetComponent()->ComponentHasTag("AFS_InteractTrigger")` in its ignore filter, so no interact trigger is bullet cover.

```cpp
UCLASS()
class HOVERFLIGHT_API AHoverZoneDoor : public AHoverInteractable
{
    GENERATED_BODY()
  public:
    AHoverZoneDoor();
    virtual void OnConstruction(const FTransform &T) override; // sizes Trigger/NavBox/BoardBlock from GapExtent
    UPROPERTY(EditAnywhere, Category = "AFS|Door") FName ZoneA;
    UPROPERTY(EditAnywhere, Category = "AFS|Door") FName ZoneB;
    UPROPERTY(EditAnywhere, Category = "AFS|Door") int32 Price = 750;
    UPROPERTY(EditAnywhere, Category = "AFS|Door") float HoldSeconds = 1.0f;
    UPROPERTY(EditAnywhere, Category = "AFS|Door") FVector GapExtent = FVector(60, 200, 150);
    UPROPERTY(EditAnywhere, Category = "AFS|Door") float BlockHeight = 2500.f; // cornice, from survey
    UPROPERTY(EditAnywhere, Category = "AFS|Door") TArray<TObjectPtr<AActor>> Blockers; // owned copies
    UPROPERTY(EditAnywhere, Category = "AFS|Door") TObjectPtr<USoundBase> OpenSound;  // PostApocalypticCity SW_Door2
    UPROPERTY(EditAnywhere, Category = "AFS|Door") TObjectPtr<USoundBase> DenySound;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> NavBox;     // NoCollision, CanEverAffectNavigation
    UPROPERTY(VisibleAnywhere) TObjectPtr<UNavModifierComponent> NavBlock; // UNavArea_Null, FailsafeExtent = GapExtent
    UPROPERTY(VisibleAnywhere) TObjectPtr<UBoxComponent> BoardBlock; // blocks ECC_Pawn only, floor->BlockHeight
    UPROPERTY(BlueprintReadOnly) bool bOpen = false;
    virtual bool CanInteract_Implementation(APawn *P) const override { return !bOpen; }
    virtual void Interact_Implementation(APawn *P) override;  // gold check -> Open or deny
    virtual FText GetInteractText_Implementation(APawn *P) const override;
    virtual bool RequiresHold_Implementation(APawn *) const override { return true; }
    virtual float GetHoldDuration_Implementation(APawn *) const override { return HoldSeconds; }
    UFUNCTION(BlueprintCallable, Category = "AFS|Door") void Open(APawn *Payer);
};
```

**Prompt and payment.** The prompt always shows the price. When the player is short, it reads "Open South Avenue (750) - need 250 more". `Interact` with too little gold plays `DenySound` and does not open the door. Otherwise it calls `Open`. This works without ZE HUD feedback, which is tied to `AZE_PlayerController`.

**`Open()` sequence:**

1. `Survival->ApplyGoldDelta(-Price)`, the same path as `ZE_WallBuyActor.cpp:107`.
2. `Trigger` and `BoardBlock` are set to NoCollision, and the text becomes empty. The sphere trace then loses focus, so no empty "Hold X / F:" prompt is left behind.
3. For each blocker: hide it, disable its collision, call `SetCanEverAffectNavigation(false)` on its components, then call `UNavigationSystemV1::UpdateActorAndComponentsInNavOctree(*Blocker)`.
4. `NavBlock->SetAreaClass(UNavArea_Default)` and `NavBox->SetCanEverAffectNavigation(false)`. Dirtying under Dynamic generation is not verified, because the engine cpp is not shipped. The Door-isolation check in section 11 plus a nav tile dump before and after open are the proof. The fallback is a `UShapeComponent` dynamic obstacle.
5. Sound, plus `UNiagaraFunctionLibrary::SpawnSystemAtLocation(/Game/Vefects/Easy_Shockwaves_VFX/VFX/Shockwaves/Particles/VFX_Shockwave_01_White_1s)`.
6. `Mode->NotifyDoorOpened(ZoneA, ZoneB)`, a `BlueprintCallable` that marks the edge open, rebuilds the pool and fires the banner.

**Blockers.** These are owned copies that plug the gap. Vendor walls are untouched.

| Door | Blocker copies |
|---|---|
| D1, D2 | `BP_T_Wall_Double_a_BarbedWire` pair |
| D3 | `SM_MilitaryBase_WiredFence_Gate_Double` + `_Gate_Lock` |
| D4 | `SM_MetalBarrier01` x2 + `SM_Barrier02` |
| D5 | `BP_T_Wall_Corner_BarbedWire` + `_Gate_L/R` |
| D6 | `SM_Kiosk_Door` on `BP_Base_02` |

Where the board can clear a roofline, a second `BoardBlock` cap is authored over the gap.

**Build and reset.** `NavigationSystem` and `Niagara` are already HoverFlight modules. Verify that the `NavModifierComponent.h` include compiles.

Doors are one-shot within a match. Game over calls `RestartLevel`, which reloads the world, so doors, power and pools return to their authored state. Nothing is persisted. A Self-Revive keeps doors and power.

### 6. Power objective (`AHoverPowerSwitch : AHoverInteractable`, Shelter)

The generator is `SM_Generator01` with two owned `BP_LightTower_off` copies, which swap to `_On` with `SC_OnOff` when power comes on.

**Hold.** Hold F for 1.0 s to start a 25 s window. The hold can only start while `WaveInProgress` and with at least 6 of the quota still to spawn. During the hold:
- the banner reads "HOLD THE GENERATOR 25";
- the spawn interval is x0.5 (twice as fast);
- the pool is {Shelter, NorthAve}, and Shelter-tagged spawners stand outside D3 so zombies pour in through the only door.

**Failure.** The window resets and can be retried next round (BO7) if:
- Vexa is more than 600 cm from the generator for 5 s cumulative, or
- Vexa goes down, or
- the round ends mid-hold.

**Success.** `bPowerOn = true` and `OnPowerChanged` fires. PaP, the trap and the jump pad all check `bPowerOn` in `CanInteract`.

### 7. Pack-a-Punch placement and unlock

`AHoverPackAPunchStation : AHoverInteractable` sits at the Underpass dead end (x ~270, y ~3,100). Its visual is the static mesh of `BP_Buy_01` on an `SM_AmmoBox_01a` base. The live `BP_Buy_01` Blueprint is not used, because it is a working WallBuy. On purchase it spawns `VFX_Shockwave_02_White_Big_1s` through Niagara.

`CanInteract` is `bPowerOn && held weapon has a next tier`. The prompt reads "Pack-a-Punch (5,000)", "(15,000)", "(30,000)" or "MAXED". The DA swap belongs to the weapons slice.

This slice guarantees three things:
- the Underpass is reachable only via D1 then D4;
- PaP is the only station that needs Power;
- the room is an ambush, with one inside spawner and two Underpass-tagged spawners in SouthAve beyond D4. Stage 2 adds emergers (second tag `Emerger`, `anim_Burst_A-I, K`, 10 clips, `ZombieAnimationPack/Animations/Mannequin_UE5`, retarget needed).

### 8. Stations per zone

`AHoverInteractable` is the owned base for every station except the armory. The visual mesh is always an owned prop.

| Zone | Station | Items |
|---|---|---|
| Plaza | `AHoverArmoryStation : AZE_WallBuyActor` on a `BP_Kiosk` copy | Sidearm 500. Ballista re-buy 1,750. It overrides the virtual `Interact_/CanInteract_/GetInteractText_Implementation`: if the pawn already owns the weapon (owned check reimplemented through the inventory component, because `PlayerHasWeapon` is private), it runs the tier-priced refill 250/750/1,500/3,000 in owned code; otherwise it calls `Super` for the vendor first buy. Plates 50. |
| SouthAve | `AHoverPerkStation` Quick Revive; `AZE_WallBuyActor` M16 (S2) | 2,500 + 500n; 1,250 |
| NorthAve | `AHoverPerkStation` Juggernog; `AHoverArmorStation` vest II; `AZE_WallBuyActor` Frag | 4,000; 250 per 2 |
| Shelter | `AHoverPowerSwitch`; `AHoverPerkStation` Speed Cola; `AHoverShelterStation` | Self-Revive 1,500, Stim 500, Noisemaker 500 (S2) |
| Underpass | `AHoverPackAPunchStation`; `AHoverPerkStation` Deadshot; ammo cache (`AHoverArmoryStation` with no weapon) | 5k/15k/30k |
| Uptown | `AHoverPerkStation` Double Tap; ammo cache; Heavy Ballista + `AHoverZoneTrap` (S2) | 3,000; 750 |
| Garage | `AHoverArmorStation` vest III; `AHoverPerkStation` Stamin-Up; `AHoverJumpPad`; exfil booth (S2) | 10,000 |

`AHoverPerkStation` computes the 2,500 + 500n price itself and grants the `bUnique` perk item from the economy slice. One machine per perk, no Wunderfizz.

### 9. Survey, then authoring

**Steps:**

1. **Back up.** Copy `HoverCyberCity.h/.cpp`, `HoverTestController.cpp`, `HoverGraphicsMenu.cpp`, `HoverAuthoring.cpp` and `HoverPilot.cpp` to `D:/AFS_Comparisons/NYCSurvival_<date>/Before` with a SHA256 manifest before any edit.
2. **Code edits.** Apply the section 2 hooks. Then:
   - Widen `HoverAuthoring.cpp:200` to accept `L_NYC_Survival`.
   - In `HoverTestController.cpp:81-84`, add `CurrentMap.Contains("L_NYC_Survival") ? 4` as the first branch.
   - In `:106-119`, add an explicit `Level == 4` map branch and the option `game=/Game/HoverPrototype/ZombieEngine/BP_NYCSurvival.BP_NYCSurvival_C`. Without it, index 4 would fall into the `BP_CyberWaves` branch.
   - Gate the bike at `:574`.
   - In `HoverGraphicsMenu.cpp`, add a `L_NYC_Survival ? 4` branch at `:70-73` and change only `:123` to `% 5`. `:97` wraps the four menu rows and is left alone. Add the label `PendingLevel == 4 ? "NYC - Survival"` at `:171-174` and amend the text at `:53-55` and `:132-134`.
   - Add the new files `HoverNYCZones.h/.cpp` and `HoverNYCSurvival.h/.cpp`. Run clang-format, then `Scripts/Build.ps1`.
3. **Editor.** Duplicate `L_NYC_Explore` as `L_NYC_Survival`, keep the four sublevels, set the GameMode Override to `BP_NYCSurvival_C`, and create `BP_NYCSurvival`.
4. **Nav only.** Run `Scripts/AuthorNYCSurvival.py --nav-only` (UnrealEditor-Cmd, NullRHI allowed) with `add_city_navigation(world, Vector(270, 5100, 150), Vector(2400, 5200, 1200))`. Size is full dimensions, so the bounds are x -930..1,470, y 2,500..7,700, z -450..750. Re-derive them once the survey finds side streets.
5. **Survey.** Run `Scripts/SurveyNYCSurvival.py` as a PIE playtest with a real RHI and `-RenderOffscreen`, never concurrently with another run. `capture_world_frame` needs a live viewport. It uses a top-down `CameraActor` from `spawn_playtest_actor` at (270, 5100, 9000) pitch -89 and `find_complete_city_path` probes. Before the survey, read the real `CapsuleRadius`/`Height` of `DA_NYC_Brute` and the new `DA_NYC_AlphaBrute` through `describe_object_properties`.
6. **Author.** Run `AuthorNYCSurvival.py` (NullRHI). It spawns everything from the frozen JSON with `spawn_actor_from_class`, sets `Extent`, `GapExtent`, `BlockHeight`, `spawn_tags=[ZoneId(, Boss|Emerger)]` and `tags=['AFS_NYCSpawn']`, dumps `describe_object_properties` to `layout_dump.json`, then saves.
7. **Cook.** Add `L_NYC_Survival`, `BP_NYCSurvival`, `DA_NYCWaves`, `DA_NYCEncounters` and every `DA_NYC_*` as explicit assets of `PAL_AFS_Runtime` (`/Game/HoverPrototype/Cook`, `DefaultGame.ini:41`).

**Survey outputs** (written into the JSON):
- facade-to-facade width per 1 m along y for each segment;
- every side-street and alcove entrance (centre, width, depth, reachable yes/no);
- Shelter interior and doorway width;
- Underpass ceiling height;
- door-gap rectangles and cornice height;
- nav islands.

**Freeze rule.** The JSON is frozen only when all of these hold:
- every zone is served by 3 or more spawners, and each spawner passes the NYC band from at least 50% of the probe points of every zone whose pool it serves;
- Brute routes are at least 150 cm wide;
- the Underpass ceiling is at least the Alpha height + 20 cm, or no boss spawner is placed there;
- every probe in every door state on the spend path reaches `ActiveSpawnCount > 0` within 8 s.

If the band minimum cannot meet 800, drop it to 600 and rely on cone LOS and closed-door occlusion. Record that in VALIDATION.

### 10. Loops, chokes, traps, fast travel, exfil

| Zone | Shape | Intent |
|---|---|---|
| Plaza | 3.5 m roadway (survey measures facade width), two gates | teach: walkers funnel from both gates |
| SouthAve | corridor + two alcoves | first loop |
| NorthAve | widest, truck + SUVs | hub loop, hardest to hold |
| Shelter | room, one door | Power hold choke |
| Underpass | columns, dead end | PaP ambush, leave fast |
| Uptown | barrier island | boss arena loop, trap at the choke |
| Garage | single approach | late camp, jump pad exit |

Zone pools do not fix bunching. In Cyber the pool was already 6-8 of 8 points, and clumping comes from arrivals converging on one point. A 3.5 m corridor makes that worse. Readable lines depend on the crowding slice: attack slots, a 120-180 cm acceptance radius, zig-zag deviation and cadence jitter.

**Trap (S2).** `AHoverZoneTrap` costs 750, needs Power, runs 20 s on / 45 s cooldown and uses `NS_Fire_01`. It is lethal to Standard, Kid and Riot. Brutes take 10% MaxHealth/s and bosses take 5%/s (half of the Brute rate). An optional electric variant uses `/Game/Sci_Fi_Weapons_VFX_AIO/VFX/NS_Lightning_Damage_Land_Small`.

**Jump pad.** `AHoverJumpPad` goes Garage -> Plaza with a 0.3 s fade and `SetActorLocation`, after Power. It is free, which deliberately departs from the BO7 price of about 500: it is a single solo route back to spawn.

**Exfil.** Cut from Stage 1.

### 11. Automation

**`Scripts/ReviewNYCSpawns.py`.** PIE with `-RenderOffscreen`. Unlike `ReviewCyberSpawns.py:23`, it keeps the game-mode tick enabled and reads `get_active_spawn_count()` and `get_last_chosen_spawner()`. `Survival` is reached through `pawn.get_component_by_class(unreal.ZE_SurvivalComponent).set_gold(99999)`. `AssessNYCSpawns.py` checks:

| Check | Pass condition |
|---|---|
| Coverage | every zone is served by 3 or more spawners (25 total) |
| Reachability (all doors open) | every served spawner has a complete path; Dist2D is inside the NYC band; path length is at most 2.5 x Dist2D |
| Door isolation (all doors closed) | no complete path from Plaza probes into another zone; after `door.open(pawn)` a path exists across that door and the spawn count is > 0 within 2 s |
| Board isolation | Vexa on the board cannot cross any closed door's BoardBlock; `CurrentZone` never becomes an unopened zone |
| Pool rule | in NorthAve with D3/D5/D6 closed, the chosen spawners are only `NorthAve` or `Plaza` |
| Stall guard | at every probe, in every reachable door state, facing the pool: spawn count > 0 within 8 s; `AFS_SpawnStall` never logged |
| Boss entrance | D5 open, player in Plaza, boss pending: `GetLastChosenSpawner()` is tagged `Boss` in Uptown |
| Vehicles | no `BP_Hoverbike` actor; `IsNearTruck()` false beside the pickup |

**`VerifyNYCSurvival.py`** asserts:
- the mode class is `BP_NYCSurvival`;
- the 30 `DA_NYCWaves` rows match the spine health, count and damage tables;
- 7 zones, 6 doors and 25 tagged spawners exist;
- `HoverLoadLevel(4)` produces the right map and option, and `CurrentLevel` detects 4.

**`VerifyNYCExploration.py`** stays unchanged and green: index 3 still maps to `L_NYC_Explore` with `HoverExplorationGameMode`, has zero spawners, zones, doors and zombies, and still spawns its bike.

Evidence goes to `D:/AFS_Comparisons/NYCSurvival_<date>/spawns/`. `Docs/NYC_SURVIVAL_<date>.txt` is plain text with VALIDATION (recording the NYC band against Cyber's) and ROLLBACK/EVIDENCE sections.

### Cross-section dependencies

| Slice | What this layer needs from it |
|---|---|
| Rounds | `IsBossSpawnPending()`, `PackRemaining`, the straggler re-queue API, Max Ammo drop sites |
| Economy | perk items, `StartingGold` 500 via `Survival->SetGold` at InitGame |
| Weapons | the PaP DA swap |
| Player | the downed state, which resets the power window |
| Crowding | bunching (attack slots, acceptance radius, path deviation, cadence jitter) |
| Controller | the bike and truck policy (section 2) |

### Owner amendments this layer needs

- **`AGENTS.md`**
  - L26-28: add a new entry: NYC - Survival, index 4, `L_NYC_Survival`, `BP_NYCSurvival` / `AHoverNYCSurvivalGameMode`. It is the only NYC entry that may spawn zombies or waves, and it never spawns the bike; the pickup is unmountable. The index-3 rules are unchanged.
  - L28: authoring permission for `HoverPrototype/Maps/L_NYC_Survival` and `/Game/HoverPrototype/NYC`.
- **`README.md`**
  - L167-173: level table entry for index 4 and its `?game=` option.
  - L172: "The other three levels" becomes "four".
- **`Docs/CONTROLS.txt`**
  - L5: Zombie Settings are also available in NYC - Survival.
  - L10-11: the economy and door rows.
- **`HoverGraphicsMenu.cpp`**: `:53-55`, `:132-134`, `:171-174`, `:123`.
- **`HoverTestController.cpp`**: `:81-84`, `:106-119`, `:574`.
- **`HoverAuthoring.cpp:200`**: the world gate.
- **`.gitignore`**: add `Docs/NYC_SURVIVAL_<date>.txt` to the Docs whitelist (L31).
- **`PAL_AFS_Runtime`**: the map, `BP_NYCSurvival` and the NYC DAs as explicit assets.
- **Scripts**: new `VerifyNYCSurvival.py`; `VerifyNYCExploration.py` unchanged.

## 9. HUD, UI and audio feedback

### 9.1 Surface decision: canvas for sub-second feedback, code-built UMG for the persistent panel

Today the AFS HUD has two surfaces. The first is `AHoverHUD::DrawHUD` (`Source/HoverFlight/HoverPilot.cpp:1817-1898`), a single non-decomposed immediate-mode function. It draws the help line; `HP %.0f/100` plus Kills/Gold at :1824-1832, drawn whenever the auth mode casts to `AHoverCyberCityGameMode`; the crosshair :1854-1861; the prompt box :1862-1874; the mount hold bar :1875-1876; the boost bar :1877-1882; and ammo text :1886-1897. The second is `UHoverCyberWaveHUD`, a code-built `UZE_WaveHUDWidget`. Its `NativeOnInitialized` (`HoverCyberCity.cpp:656-688`) builds a local, unnamed `UVerticalBox` inside a `UBorder` fixed at `SetSize(270,190)`, and `EncounterText` is private (`HoverCyberCity.h:131`). It is installed through `WaveSettings->WaveHUDClass` (`HoverCyberCity.cpp:98`). The vendor `AZE_ZombieWaveGameMode::PostLogin` (`ZE_ZombieWaveGameMode.cpp:35-45`) already creates it at ZOrder 0. The AFS tick (`:272-278`) finds that instance and does not re-add it, so ZOrder 10 is not guaranteed. Every vendor HUD widget assumes the vendor pawn or controller: `ZE_PlayerHUDWidget.cpp:437-447` and `ZE_WallBuyActor.cpp:64-68, 98-103`.

| Surface | Decision | Reason |
|---|---|---|
| `AHoverHUD` refactor (AFS code) | Split `DrawHUD` into protected virtuals `DrawStatusLine`, `DrawCrosshair`, `DrawPromptBox`, `DrawHoldBar`, `DrawBoost`, `DrawAmmo`. `DrawHUD` calls them in the current order, so the other modes keep identical output. | Without the split, calling `Super` from a subclass redraws the "/100" line, the old crosshair, the mount bar and the canvas ammo, which duplicates the panel. Skipping `Super` would lose the help, prompt and BOOST bars. |
| `AHoverSurvivalHUD : AHoverHUD` (new) | Overrides `DrawStatusLine` (suppressed) and `DrawAmmo` (suppressed; the panel owns ammo). Replaces `DrawCrosshair` and `DrawHoldBar`. Keeps `DrawPromptBox` and `DrawBoost`. Adds hit/kill markers, damage arcs, the regen ring, the downed overlay and the death frame. | These are 0.1-3 s overlays tied to the frame of a hit. Set as `HUDClass` in the survival constructor. |
| `UHoverSurvivalPanel : UHoverCyberWaveHUD` (new) | Code-built UMG, no WBP asset. It does not append rows to the parent column. It adds four separate anchored containers to `Cast<UCanvasPanel>(WidgetTree->RootWidget)` (check the cast; log an error and fall back to a plain canvas): top-left, top-centre, bottom-left and bottom-right. The parent 270x190 round/remaining block stays top-right, and Cyber City is unchanged. | The parent column is unreachable and 190 px cannot fit about 12 rows. Survival loads its own `DA_NYCWaves` and sets `WaveHUDClass` after `Super::InitGame`, so `DA_CyberWaves` is never mutated. ZOrder 0 from PostLogin is accepted. |
| Vendor `WBP_UZE_PlayerHUDWidget`, `WBP_WaveHUD`, `WBP_InteractPrompt`, `WBP_ZE_DeathRespawn` | Not used | Pawn/controller casts; `WBP_ZE_DeathRespawn` is mouse-driven (`ZE_DeathRespawnWidgetBase.h:84-96`). |
| Vendor `WBP_DamageNumber` | Kept | `ZE_ZombieCharacter.cpp:162-163` needs **both** `DamageWidgetClass` and `DamageActorClass` on every `DA_NYC_*`. Also set `Stats.bAccumulateDamage=false` (`ZE_ZombieSettings.h:92`) so each shot prints. |

**Scale rule:** every pixel constant in 9.3/9.4 is a 1080p value multiplied by `S = Canvas->ClipY / 1080`. The panel uses the same factor through a `UScaleBox` on each container.

**Camera:** survival defaults to the third-person review camera (430 cm spring arm). F5/Menu toggles to first person. This depends on the player/camera slice. The fire trace already uses the active camera (`HoverPilot.cpp:1312`), so screen centre is correct. When the aim trace's first hit is Vexa's own capsule within 150 cm, the crosshair dims to 35% alpha. Damage-arc yaw uses `PlayerCameraManager->GetCameraRotation().Yaw`, not `BodyYaw`.

### 9.2 Feedback plumbing: one component, three producers

`UHoverFeedbackComponent` is created in `AHoverPilot::BeginPlay` beside the bridge creation (`HoverPilot.cpp:283-287`), only under `Cast<AHoverNYCSurvivalGameMode>`. The other modes never get it.

It has three producers:

1. **`AHoverCyberZombie::TakeDamage`.**
   - Compute `bHeadshot = Hit.BoneName.IsEqual(ZombieData->Stats.HeadBoneName, ENameCase::IgnoreCase)` from the existing pre-Super `GetBestHitInfo` (`HoverCyberCity.cpp:557-562`).
   - After `Super`, call `HitConfirmed(bHeadshot, WasAlive && bIsDead)` for any accepted damage (Result > 0), gated on `Cast<AHoverPilot>(EventController->GetPawn())`.
   - Call `PointsAwarded(fixed amount, kind)`. The `Mode->AddGold(FMath::RandRange(...))` line at :588-589 is **replaced**, not supplemented.
   - Damage of type `UHoverNukeDamageType` (new, used by the Nuke path at `:637-641`) suppresses markers and per-kill points. The mode awards +400 once.
   - The flesh-hit cue plays beside `BloodBurst` (`:567-568`).
2. **`AHoverPilot::TakeDamage`.** The causer direction is computed on its own, before the `bInvincible` return (`:1649`), and `DamageTaken` is called on every accepted hit. `TowardImpact` at :1641-1643 sits inside the 0.65 s throttled hit-react block and cannot be reused.
3. **Stations and doors** report purchase success or denial (9.5).

Round, boss and power-up state is read from AFS getters. The vendor never broadcasts `GameOver`/`Won` for Vexa, so the AFS-side `OnSurvivalEvent` delegate on the mode carries game over, boss spawn, boss death, horde clear and power state.

```cpp
// Source/HoverFlight/HoverSurvivalHUD.h (new) - sketch, must pass UHT
UENUM() enum class EHoverPointsKind : uint8 { Body, Headshot, Melee, Special, Boss, PowerUp };
USTRUCT() struct FHoverPointsPopup {
    GENERATED_BODY()
    int32 Amount = 0; EHoverPointsKind Kind = EHoverPointsKind::Body; float Time = 0; };  // Kind = colour only
USTRUCT() struct FHoverDamageMark { GENERATED_BODY() float RelativeYaw = 0; float Time = 0; bool bPlate = false; };

UCLASS() class HOVERFLIGHT_API UHoverFeedbackComponent : public UActorComponent {
    GENERATED_BODY() public:
    virtual void BeginPlay() override;   // resolves cue table (9.7) by object path; missing = silent + one log line
    void HitConfirmed(bool bHeadshot, bool bKill);
    void PointsAwarded(int32 Amount, EHoverPointsKind Kind);
    void DamageTaken(const FVector &From, bool bPlateHit, bool bPlateBroke);
    void Purchase(bool bOk, const FText &Label);
    void Banner(const FText &Big, const FText &Small, float Seconds, FName Cue);
    void PlayCue(FName Cue, float Volume = 1, float Pitch = 1);
    void PlayRumble(FName Effect);       // runtime-built curves, 9.9
    UPROPERTY() TMap<FName, TObjectPtr<USoundBase>> Cues;
    UPROPERTY() TMap<FName, TObjectPtr<UForceFeedbackEffect>> Rumble;   // NewObject at BeginPlay, no Content
    UPROPERTY() TObjectPtr<UTexture2D> PlaceholderIcon;                  // T_Icon_001..017
    float LastHitTime = -10, LastKillTime = -10; bool bLastHeadshot = false;
    TArray<FHoverPointsPopup> Popups; TArray<FHoverDamageMark> Marks;
    FText BannerBig, BannerSmall; float BannerUntil = 0;
};

UCLASS() class HOVERFLIGHT_API AHoverSurvivalHUD : public AHoverHUD {
    GENERATED_BODY() protected:
    virtual void DrawStatusLine() override {}  virtual void DrawAmmo() override {}
    virtual void DrawCrosshair() override;     virtual void DrawHoldBar() override;
    virtual void DrawHUD() override;           // Super + overlays (9.4)
};

UCLASS() class HOVERFLIGHT_API UHoverSurvivalPanel : public UHoverCyberWaveHUD {
    GENERATED_BODY() protected:
    virtual void NativeOnInitialized() override;   // Super, then add 4 anchored containers to the root canvas
    virtual void NativeTick(const FGeometry &G, float DT) override;
    UPROPERTY() TObjectPtr<UTextBlock> PointsText;  UPROPERTY() TObjectPtr<UTextBlock> ZoneText;
    UPROPERTY() TObjectPtr<UTextBlock> AmmoText;    UPROPERTY() TObjectPtr<UTextBlock> TierText;
    UPROPERTY() TObjectPtr<UTextBlock> EquipText;   UPROPERTY() TObjectPtr<UTextBlock> PowerUpText;
    UPROPERTY() TObjectPtr<UTextBlock> CentreTimerText; UPROPERTY() TObjectPtr<UTextBlock> DebugText;
    UPROPERTY() TObjectPtr<UProgressBar> HealthBar; UPROPERTY() TObjectPtr<UProgressBar> CentreBar;
    UPROPERTY() TArray<TObjectPtr<UProgressBar>> PlateBars;
    UPROPERTY() TObjectPtr<UHorizontalBox> Quickbar; UPROPERTY() TObjectPtr<UHorizontalBox> PerkRow;
    UPROPERTY() TObjectPtr<UVerticalBox> PopupColumn;
};
```

**Required AFS-side edits:**
- On `AHoverCyberCityGameMode` (`HoverCyberCity.h`, AFS code): add a public `float GetPowerUpRemaining(EZE_PowerUpType) const`. `SpeedBonusUntil` and `InstaKillUntil` are private at :67-68. Also make `GetEncounterLabel` `virtual` (:55), so the survival override reaches the parent `NativeTick` while Cyber City and Lakeside strings stay unchanged.
- On `AHoverNYCSurvivalGameMode`: `GetRoundKind()`, `GetActiveBoss()` (health through the public `AZE_ZombieCharacter::SurvivalComponent`, `ZE_ZombieCharacter.h:46`), `GetLiveBossCount()`, `GetPowerDefendRemaining()`, `GetZoneName()`, `GetPaPTier()`, `IsSurvivalOver()`, and `UFUNCTION(BlueprintPure) FString GetHUDSnapshot()`.
- On the bridge: `UFUNCTION(BlueprintPure) float GetInteractionProgress()`.
- On `AHoverCyberRifle`: `float GetSpreadFraction() const`.

### 9.3 Persistent panel rows (`UHoverSurvivalPanel`)

| Row | Source of truth | Rule |
|---|---|---|
| Round (parent block, top-right) | `GetCurrentWave()` | 34 pt "ROUND 13". It scales from 1.6x to 1.0x over 0.6 s when a round starts. Tint is red on boss rounds, orange on horde rounds and steel on heavy rounds. |
| Encounter line | virtual `GetEncounterLabel()` override | "KID SWARM - stay moving", "HEAVY TANK x2" (B(r)), "BOSS - ALPHA BRUTE" / "WARDEN" (Stage 2), and "ENDLESS - health +800/round" from R31. |
| Remaining / intermission | `GetZombiesRemaining()` + `GetLiveBossCount()` | Bosses are spawned outside the vendor `SpawnZombie`, which privately binds `OnZombieDeath` (`ZE_ZombieWaveGameMode.cpp:552`), so the vendor counters never see them. AFS tracks each boss through the public `OnDeath` delegate (`ZE_ZombieCharacter.h:51`), and round clear also waits for that count. The intermission shows "NEXT ROUND 10". All stations stay usable and the game never pauses (spine: no shop pause). |
| Points (bottom-left) | `GetGold()` (`HoverCyberCity.cpp:596-602`) | 28 pt with a thousands separator. Flashes white for 0.15 s on change and shakes red for 0.2 s on a denied purchase. Greyed while mounted (the board earns nothing). |
| Points popups | `PointsAwarded` | Prints the Amount it is passed; Kind only selects the colour. "+90" white, "+115" yellow, "+105" cyan (katana), "+150" orange (Riot, Stage 2), "+250" orange (Brute), "+500" red (boss), "+400" green (Nuke, `PowerUp`). Popups rise 24 px over 0.9 s, up to 6 stacked. |
| Health | `AHoverPilot::GetHealth()` (`SandboxHealth`, `HoverPilot.h:173`) / new `AHoverPilot::GetMaxHealth()` | Health lives in `SandboxHealth` and is mirrored one way into `Combat->Survival` (`HoverPilot.cpp:1663-1666`). Every new writer goes through one `AHoverPilot::SetSurvivalHealth(float)` that clamps to MaxHealth and mirrors: regen, Stim, Max Health, Juggernog, Self-Revive at 50%, InitGame 150. The bar is 220x12: green above 60%, amber 30-60%, red below 30%. While regen is pending, the edge pulses blue. Juggernog lengthens the bar to the 250 scale with a tick at 150. |
| Plates | `AHoverPilot::GetPlateState()` (player slice) | 1-3 white segments of 50 HP that drain fractionally. A break flashes the segment red and plays `PlateCrack`. An empty vest shows hollow outlines. |
| Ammo (bottom-right) | `Cast<AHoverCyberRifle>(Combat->GetWeapon())` clip / reserve | "17 / 270" at 34 pt. Amber at 10 or fewer in the clip, red at 0 with "EMPTY - tap X / R". When a station is focused, it reads "EMPTY - R / step away to reload": tap-X reload is suppressed while an interactable is focused (`HoverPilot.cpp:698-708`). "RELOADING" is kept. |
| Tier | `GetPaPTier()` | "BALLISTA" / "BALLISTA I/II/III", then MAXED after III. `DA_AFS_Ballista_5` is not in the Stage 1 PaP chain (Stage 2 re-authors it as Heavy Ballista). |
| Quickbar | `GetQuickbarItem/GetActiveQuickbarSlot/GetQuickbarSize` (`ZE_InventoryComponent.h:247-265`) | Five 48 px slots. `GetActiveQuickbarSlot` is 1-based, so subtract 1 for `GetQuickbarItem` (verify the base once in VALIDATION). Icons come from `UZE_ItemDefinition::Icon`. Use the `T_Icon_001..017` generics in `Content/ZESP/ZE/Texture/IconItem` as placeholders for Ballista tiers, plates, frag and stim before authoring new textures. Each PaP DA keeps its own icon through the swap. |
| Perks (bottom-left, above points) | inventory perk items (economy slice) | Up to six 32 px icons in purchase order (tinted placeholders until owner art). The newest is outlined, because it is the one lost on Self-Revive. On loss it shakes and fades over 1 s. |
| Equipment | pilot inventory | "FRAG 2  PLATES 1/1  STIM 0/2  REVIVE 1". |
| Power-up chips | `GetPowerUpRemaining` | "INSTA-KILL 23" / "SPEED 9", blinking under 5 s. Max Ammo, Max Health and Nuke show a 1.5 s centre banner instead. |
| Centre-top bar (shared slot) | `GetActiveBoss()` / `GetPowerDefendRemaining()` | **Boss:** 520x14 bar with the name and ticks at 75/50/25% (Alpha enrage at 50%). **Power defend:** "DEFEND THE GENERATOR 25" in orange, blinking under 5 s, with a `PowerDefend` stinger at start. The boss bar wins if both are active. The rule for leaving the zone is deferred to the zones slice. |
| Zone (bottom-right, under ammo) | `GetZoneName()` | Small caps, 2 s slide-in when a door opens. |
| QA line (test menu only) | mode debug counters | "spawner Z3/E2 \| stall-guard 0 \| requeued 1". This makes the spawn and straggler fixes visible to the owner. Hidden by default. |
| Hoverboard | `Pilot->IsMounted()` | BOOST bar kept. Damage arcs and plate drain still draw while mounted, because the board does not block damage (SetCanBeDamaged bypass, player slice). |

### 9.4 Canvas overlays (`AHoverSurvivalHUD`)

| Overlay | Trigger | Draw rule |
|---|---|---|
| Crosshair + spread | every frame | 3 px dot when aiming, 5 px cross otherwise. A 4-tick ring with radius `18 + 10 x GetSpreadFraction()` px, where `GetSpreadFraction() = MaxSpread > 0 ? CurrentSpread / MaxSpread : 0` reads the protected `CurrentSpread` (`ZE_WeaponBase.h:275`) and `GetWeaponDefinition()->CombatStats.MaxSpread`. The ring is dimmed when the aim is self-blocked (9.1). |
| Hit marker | `HitConfirmed(false,false)` | Four diagonal 6-12 px lines, 2 px wide, white, fading over 0.12 s. Plays `HitTick`. |
| Headshot marker | `HitConfirmed(true,false)` | Same marker in red. `HeadshotTick` at pitch 1.3. |
| Kill marker | `HitConfirmed(*,true)` | Ticks expand to 10-18 px, yellow, 0.25 s, with `KillSting`. A headshot kill fades red to yellow. |
| Damage direction | `DamageTaken` | Red 48 px arc on a 90 px ring at `RelativeYaw = camera yaw - yaw to causer`, fading over 0.8 s. Plate hits draw white. Up to 4 marks. |
| Regen countdown | health <= 40 and last damage under 6 s (3 s with Quick Revive) | 24 px ring that fills clockwise. It disappears when regen (40 HP/s) starts. |
| Hold progress | `GetInteractionProgress()` | 140x5 bar under the crosshair, value `InteractionHeld / GetHoldDuration` (bridge private block `HoverCombatBridge.h:89-92`, tick `.cpp:457-476`). The mount bar is kept only while mounted (`HoldProgress()`, 0.65 s). |
| Prompt line | `Pilot->GetPrompt()` (`HoverPilot.cpp:1793-1815`, bridge prefix `:427-432`) | The price is drawn red when `GetGold() < Price`. Reading it requires `Combat->Interaction->GetFocusedActor()` plus a `Cast` to `IHoverPricedInteractable`. Shows "Hold X" when `AHoverTestController::bLastInputGamepad` is set (from `Params.Key.IsGamepadKey()` at the top of `InputKey`), otherwise "Hold F". |
| Downed | pilot downed flag (player slice) | Red vignette at 0.35 alpha, "DOWNED" at 48 pt with a 3.0 s countdown, then "SELF-REVIVE x1" or "NO SELF-REVIVE" in red. `DownedSting` plays once. |
| Death frame | `IsSurvivalOver()` | 2 s of slow motion with 12% black bars and "ROUND 19" at 40 pt, then the game-over widget (9.6). |

### 9.5 Prompts, purchase feedback, denied buzz

Only `AZE_WallBuyActor` overrides `RequiresHold`/`GetHoldDuration` (`ZE_WallBuyActor.cpp:157-178`). The interface defaults are false/0 (`ZE_InteractableInterface.generated.h:23-24`), which would make the bridge fire a base-derived station after 0.05 s (`HoverCombatBridge.cpp:469-471`). Its `CanInteract` also fails without a WeaponDefinition (`:33-36`). So:

- **Doors, perks, PaP, power, armor, Self-Revive and Shelter stations** derive from `AZE_InteractableBase`. They override `RequiresHold_Implementation` (true), `GetHoldDuration_Implementation` (1.0 s, or the per-station value), `CanInteract`, `Interact` and `GetInteractText`.
- **Real weapon and item buys** subclass `AZE_WallBuyActor`. `ExecutePurchase` is non-virtual and returns void, so the AFS override wraps `Interact_Implementation`. It compares gold before and after `Super` to decide `Purchase(true/false)` and computes tier-scaled ammo prices itself.

```cpp
UINTERFACE(MinimalAPI) class UHoverPricedInteractable : public UInterface { GENERATED_BODY() };
class HOVERFLIGHT_API IHoverPricedInteractable { GENERATED_BODY() public:
    virtual int32 GetPrice(APawn *Pawn) const = 0;          // 0 = free (power switch)
    virtual FText GetDeniedReason(APawn *Pawn) const = 0;   // "NEEDS POWER", "MAXED", "NOT ENOUGH POINTS"
};
```

Prompt strings: `Door - South Avenue (750)`, `Pack-a-Punch I (5,000)`, `Juggernog (2,500)`, `Armor plate (50)`, `Vest II (4,000)`, `Self-Revive (1,500)`, `Refill ammo (750)`, `Power - hold to start (25 s defend)`.

- **Success:** centre text "PURCHASED - PACK-A-PUNCH I" in green for 1.2 s, `PurchaseOk`, and a points flash.
- **Denied:** the prompt shakes 4 px for 0.3 s, the points row shakes red, `PurchaseDenied` plays and `Hit` rumble fires.

The vendor `ShowBuyFeedback` path is dead for Vexa and is not patched.

### 9.6 Downed, game over, restart

The vendor flow is unusable: `OnPlayerHealthChanged`/`HandleGameOver` are private (`ZE_ZombieWaveGameMode.h:163, :167`) and bound only for `AZE_PlayerCharacter` (`.cpp:49-66`). `SetWaveState` is private (`:153`), so the vendor state stays `WaveInProgress`.

`AHoverNYCSurvivalGameMode::HandleSurvivalGameOver()` runs these steps in order:

1. Sets `bSurvivalOver` and broadcasts `OnSurvivalEvent(GameOver)`.
2. Calls `StopAllZombies()` (protected, `:189`).
3. While the flag is set, the overridden `Tick` skips `Super::Tick`. That skips both the vendor wave/spawn tick (`:436-458`) and the AFS spawn gating, so no new zombies arrive.
4. Applies `SetGlobalTimeDilation(0.2)`. The vendor uses 0.001 at `ZE_ZombieWaveGameMode.cpp:159` and resets to 1.0 at :232/:252. The 2 s is measured with `GetRealTimeSeconds()`, because a dilated timer would last 10 s.
5. Resets dilation to 1.0 and creates `UHoverGameOverWidget` (code-built). Title "VEXA FELL - ROUND 19". Rows: Kills, Points earned, Zones opened 4/7, PaP tier II, Perks 4/6, Rounds survived. Hints: `A / Enter: restart from round 1`, `B / Esc: test settings`.

**Input:** `AHoverTestController::InputKey` gets a game-over branch at the very top, before the knocked-down/defeated swallow at `HoverTestController.cpp:130-136`, gated on `IsSurvivalOver()`. Otherwise A/Enter/B/Esc never arrive.

**Defeat timeout:** in survival, `AHoverPilot::UpdateInput` must not call `HoverReset` at `HoverPilot.cpp:624-632`. That timeout teleports Vexa and heals her to 100 (`:577-579`). The `TakeDamage` defeat block (:1666-1693) is gated as well. The mode owns the downed and game-over flow (player slice).

**Restart:** uses the same travel string as `HoverLoadLevel`. `BP_CyberWaves` class defaults (`HoverTestController.cpp:118`) cannot be read from source, so the authoring pass dumps them with HoverAuthoring. If they hold anything beyond the native defaults, author a local `BP_NYCSurvival` child and travel with its `_C` path. Otherwise use `/Script/HoverFlight.HoverNYCSurvivalGameMode`. Record the choice in VALIDATION.

### 9.7 Banners and cue families

Each event has its own clip family, so meanings never share a clip. Cues are resolved from full object paths at component BeginPlay. A missing cue is silent.

| Event | Banner (centre, 1.5 s unless noted) | Cue (`/Game/...` object path) |
|---|---|---|
| Round start | "ROUND r" | `PostApocalypticCity/Sounds/SC_OnOff` + `Vefects/.../SFX_Vefects_Shockwave_02_500ms_Cue` at 0.5 volume |
| Strength step (R11, 16, 21, 26, 31, 41) | "THEY HIT HARDER" / "THEY ARE TOUGHER" | `Zombie/Sound/ZombieV2/SC_Zombie_CrowdAmbience` swell, 1.2 s |
| Horde round | "KID SWARM - stay moving", 2 s | `Zombie/Sound/ZombieV2/Hiss/SC_Zombie_Hiss` x3 |
| Heavy round / R8 debut | "HEAVY TANK" + count | `Zombie/Sound/Monster/SC_Monster_Roar` (the Brute's voice) |
| Boss spawn | "ALPHA BRUTE" at 48 pt for 2.5 s, plus a shake from `LoadClass<UCameraShakeBase>(nullptr, TEXT("/Game/ZESP/ZE/FX/CameraShake/BP_M16_FireShake.BP_M16_FireShake_C"))` at scale 3.0 | `Entity/SC_Entity_Roar` + `Monster/SC_Monster_Roar` layered at pitch 0.7 |
| Power defend start | "DEFEND THE GENERATOR" | `Zombie/Sound/ZombieV2/Hiss/SC_Zombie_Hiss` |
| Alpha enrage at 50% | 1 s red pulse | `SC_Entity_Roar` at pitch 0.8 |
| Boss death | "BOSS DOWN +500", 2 s; 3 s kill cam at dilation 0.3 (real-time timed) | `KillSting` + `SC_Entity_Death` |
| Max Ammo (any source) | "MAX AMMO" | `PowerUpPickup` |
| Power-up pickup | "INSTA-KILL 30 s" / "NUKE +400" / "MAX HEALTH" | `AHoverCyberPowerUp` already plays `PickupSound` (`HoverCyberCity.cpp:649-650`); only the banner is added |
| Round clear | "ROUND r CLEAR - next in 10" | none |
| Door opened | zone slide-in | `PostApocalypticCity/Sounds/SW_Door1-3` at the door |
| Power on | "POWER RESTORED - Pack-a-Punch online", 2.5 s | `SC_OnOff` + `SC_EngineSound01` |

UI chimes are placeholders: `HitTick` and `PurchaseOk` use `Zombie/Sound/Hits/S_Entity_Hit_A` at pitch 1.6 and 0.35 volume, `PurchaseDenied` is two `SC_OnOff` taps at pitch 0.6, and `PlateCrack` is `S_Monster_Hit_B` at pitch 1.4. These are UI and impact cues, not creature vocals. The flesh hit on zombies is `Hits/S_Monster_Hit_A-C` beside BloodBurst.

### 9.8 Zombie vocals by role (owner decision, default off)

`Docs/ASSET_AUDIT_REPAIRS_20261025.txt:63-64` records an owner decision: no suitable creature vocals were found in the audited libraries, and silence is not to be filled with unrelated effects. This table therefore ships behind `bZombieVocals = false` (a `UHoverCyberEncounterSettings` field) and only turns on after the owner amends that line.

When it is on, AFS plays every vocal itself, picked by role and runtime speed tier through `PlaySoundAtLocation(..., Pitch)`:
- `DA_NYC_*` `AttackSound`/`DeathSound` are left null so the vendor (`ZE_ZombieCharacter.cpp:293-295, :386-389`) never double-plays.
- Aggro plays once from `AHoverCyberZombieAI::OnPlayerDetected` (`HoverCyberCity.cpp:413-419`).
- The chase loop is a `UAudioComponent` chosen when the tier is rolled (rounds slice).
- The crowd bed is `SC_Zombie_CrowdAmbience` in 2D at `clamp(alive/16)`.

| Role | Aggro | Chase loop | Attack | Pain on flinch | Death |
|---|---|---|---|---|---|
| Walker | `Idle/SC_Zombie_Idle` | `SC_ZombieV2_ChasingSlow` | `Attack/SC_ZombieV2_AttackHiss` | `Pain/SC_Zombie_Pain` | `SC_ZombieV2_Death` |
| Runner | `Speech/SC_Zombie_Speech` | `SC_ZombieV2_Chasing` 0.8 | `Attack/SC_Zombie_Attack` | `SC_Zombie_Pain` | `SC_ZombieV2_Death` |
| Sprinter | `Roar/SC_Zombie_Roar` | `SC_ZombieV2_Chasing` | `SC_Zombie_Attack` pitch 1.1 | `SC_Zombie_Pain` | `SC_ZombieV2_Death` |
| Kid | `Hiss/SC_Zombie_Hiss` | `SC_Zombie_Speech` pitch 1.3 | `SC_ZombieV2_AttackHiss` pitch 1.3 | none | `SC_ZombieV2_Death` pitch 1.4 |
| Riot (S2) | `Inhale/SC_Zombie_Inhale` | `ChasingSlow` pitch 0.9 | `SC_Zombie_Attack` pitch 0.9 | none while pool > 0 | `SC_ZombieV2_Death` |
| Brute | `Monster/SC_Monster_Roar` | `SC_Monster_Ambience` | `SC_Monster_Roar` on stomp | `S_Monster_Hit_A-C` | `SC_Monster_Death` |
| Alpha Brute | `Entity/SC_Entity_Roar` | `SC_Entity_Ambience` | `SC_Entity_Roar` | `S_Entity_Hit_A-C` | `SC_Entity_Death` |
| StoneGolem (S1) | `SC_Entity_Roar` pitch 0.7 | `SC_Monster_Ambience` 0.7 | `SC_Monster_Roar` 0.7 | `S_Monster_Hit_*` | `SC_Monster_Death` |

Paths are relative to `/Game/Zombie/Sound/` (`ZombieV2/...`, `Monster/...`, `Entity/...`, `Hits/...`). "Pain on flinch" depends on the crowding slice relaxing the 0.8 s / `!bIsAttacking` rule.

### 9.9 Haptics

The new path runs only when `UHoverFeedbackComponent` exists, which means survival only. PostApo, Cyber City, Lakeside and NYC Exploration keep `PlayDynamicForceFeedback(.18f,.06f,...)` (`HoverPilot.cpp:1512-1513`) and the 0.45 s `ImpactPulse` throttle (`:1542-1548`). The effects are `UForceFeedbackEffect` objects built at runtime with `NewObject` and curve keys, played with `PC->ClientPlayForceFeedback`. No Content asset is needed.

| Effect | Motors | When |
|---|---|---|
| `Fire` | left large 0.45 x 0.07 s, right small 0.9 x 0.04 s | every shot (combat slice call site) |
| `Hit` | right small 0.35 x 0.04 s, 1.5x on headshot | hit confirmed, denied purchase |
| `Kill` | left large 0.7 ramping down over 0.14 s | kill |
| `DamageTaken` | both large 0.5 x 0.12 s | zombie hit on Vexa |
| `PlateBreak` | both small 1.0 x 0.08 s, then large 0.3 | plate break |
| `Knockdown` | both large 1.0 x 0.4 s | stomp or hammer (existing `ShowStompPulse` 0.5, `:1703`) |

### 9.10 Pause / test menu changes

**Index detection.** It exists twice: `HoverTestController.cpp:81-84` and `HoverGraphicsMenu.cpp:69-73`, which seeds `PendingLevel`. Both must return 4 for `L_NYC_Survival`. Otherwise the map falls through to 0 (PostApo) and Apply reloads the wrong level. Move this into one shared `HoverLevels::IndexForMap()` helper.

**Menu and travel edits:**
- `Adjust` level modulus `% 4` to `% 5` (`HoverGraphicsMenu.cpp:123`). `Navigate` (:97) is the row count and stays 4.
- Add index 4 "NYC - Survival" to the label ternary (:171-174) and to `HoverLoadLevel` (`HoverTestController.cpp:106-119`).
- The static NYC line (:53-55) becomes "NYC - Exploration: no zombies. NYC - Survival: rounds, points, doors, Pack-a-Punch".
- The DetailText "reset at the start after 3 seconds" (`:51`, `:157-158`) gets a survival variant: "Survival: down = Self-Revive or game over".

**Invincibility.** The game mode cannot fix this alone: `bInvincible` is read in `AHoverPilot::BeginPlay` (`HoverPilot.cpp:137`) after InitGame, and `UHoverGraphicsSettings::Apply` re-applies the saved value at `HoverGraphicsSettings.cpp:186-187`. So `BeginPlay` (after :137), `SetInvincible` and `IsInvincible` force false when the auth mode is `AHoverNYCSurvivalGameMode`. The Invincible row (`:124-125`, `:177-180`) draws greyed "Off (survival)" and Adjust ignores it. Survival never writes the persisted `[AFS.Graphics] Invincible`.

**Zombie Settings page.** It stays available; `Tuning.*` still multiplies the spine rows (VALIDATION). `SetPause` remains the only pause.

### 9.11 Controller + keyboard mapping

Bindings are raw `EKeys` checks in `AHoverTestController::InputKey`, `AHoverPilot::UpdateInput` and the bridge tick. G, H, Q, Y and L1 are proposed, but they are not confirmed free on foot until the authoring pass lists the Parkour/CLS IMC bindings with HoverAuthoring.

| Action | Gamepad | Keyboard | Status / conflict |
|---|---|---|---|
| Fire / aim / reload / jump | R2 / L2 / tap X / A | LMB / RMB / R / Space | unchanged |
| Run / slide-crouch | L3 (`HoverPilot.cpp:686`) / B | none in code / Ctrl (`:731`); Shift per CONTROLS via Parkour | documented as is |
| Katana | tap R3 / hold R3 0.45 s | V | unchanged (`HoverTestController.cpp:152-174`) |
| Interact | hold X (1.0 s) | hold F | mount hold and tap-X reload are suppressed while focused (`HoverPilot.cpp:698-708`) |
| Quickbar / inventory | D-pad Left / D-pad Down | 1-5, R / Tab | unchanged (`:188-210`) |
| Test settings | D-pad Up | F6 | unchanged (`:222-226`) |
| Frag (new) | L1 tap, on foot | G | L1 is bank only while mounted |
| Plate insert (new) | D-pad Right hold 0.3 s, on foot | Q, on foot | Q is bank while mounted (`:664`, read every frame), so this is gated on `IsOnFoot()`. Other D-pad Right consumers must early-out in survival: CLS compare (`HoverTestController.cpp:212-221`), `ClsComparison.cpp:165` and the test menu (`:255`). Compare moves to F7 only, and the hint at `HoverPilot.cpp:1850-1853` changes. |
| Stim (new) | Y tap, on foot | H | Y is "exit truck" only while driving |
| Self-Revive | automatic | automatic | spine |
| Game over | A / B | Enter / Esc | top-of-`InputKey` branch (9.6) |
| Camera | Menu | F5 | third-person default in survival (9.1) |

### 9.12 Validation and owner amendments

**VALIDATION** (offscreen, never concurrent). `Scripts/VerifyNYCSurvival.py` opens `L_NYC_Survival`, drives `HoverAuthoring.test_key`, and reads `is_wave_hud_visible` plus `get_hud_snapshot()` JSON. It asserts:
- The round label and the points after one scripted kill (+90 body, +115 head).
- After one scripted 30-damage hit: plate HP 35/50 and health 135/150.
- After four hits: plate pool 50 -> 35 -> 20 -> 5 -> 0 and the PlateCrack flag set, health 80/150. This assumes the 4th hit's 10 overflow spills to health, consistent with the spine's "one plate absorbs 50 HP total"; the player slice confirms.
- `perks_owned`; banners on R5 and R8; the centre bar visible on R13.
- A Nuke kill emits no per-kill popup and a single +400.
- Remaining includes the live boss.
- The game-over widget appears after a forced down with 0 Self-Revives, and A restarts.
- The pilot stays invincible-false after `UHoverGraphicsSettings::Apply` with the saved value On.
- The active-slot base used for `GetQuickbarItem`.
- Which travel form (native vs `BP_NYCSurvival_C`) was chosen.
- That cues and icons resolve. Local-only Content is checked by an existence check, and absence is allowed and logged.

`VerifyNYCExploration.py` is unchanged; a new assertion checks that index 3 shows the original `AHoverHUD` status line and no `UHoverSurvivalPanel`. Evidence goes to `D:/AFS_Comparisons/NYCSurvival_<date>/`. `CapturePlaytest` screenshots are labelled as rendered evidence, separate from NullRHI runs.

**Owner must amend:**
- `AGENTS.md:26-28`: index-4 survival entry may spawn waves, never the bike; index 3 unchanged.
- `AGENTS.md:20-22`: the ZES inventory clause also covers Survival.
- `README.md:167-173`: level table and the `?game=` option.
- `Docs/CONTROLS.txt`: a new "NYC SURVIVAL" block (points 90/115/105/150/250/500, plates, perks, PaP 5k/15k/30k, doors 750-2,000, reserve 270/360/450/540, L1/G frag, D-pad Right/Q plate, Y/H stim, F7-only compare, A restart, reload while facing a station).
- `Docs/CONTROLS.txt`: the "Invincible: On by default" paragraph (forced off in Survival) and the TEST SETTINGS level line.
- `Docs/ASSET_AUDIT_REPAIRS_20261025.txt:63-64`, if zombie vocals are wanted.
- `.gitignore`: `!Docs/NYC_SURVIVAL_<date>.txt`.
- `PAL_AFS_Runtime` roots: `/Game/Zombie/Sound`, `/Game/PostApocalypticCity/Sounds`, `/Game/ZESP/ZE/Texture/IconItem`, `/Game/HoverPrototype/NYC`.

### 9.13 Benchmark deviations, coverage, risks

**BO7 deviations (deliberate):**
- A persistent "remaining" counter, because the vendor panel has one and it is the owner's QA signal for spawns.
- Plates drain fractionally (BO plates are whole) because the spine routes 50% per hit.
- Per-shot damage numbers (BO default is off), kept because the vendor numbers are free.
- An explicit regen ring, kept for readability.

**Owner-complaint coverage.** This section fixes missing hit markers, hit sounds, kill punctuation and haptics. It does not fix random spawning or bunching (spawn and crowding slices), but it exposes them through the remaining counter and the QA line.

**Risks:**
- The `AHoverHUD` virtual split touches every mode. VALIDATION must show identical canvas output in indices 0-3.
- The root-canvas cast in `UHoverCyberWaveHUD` is assumed from the code-built tree and must be checked.
- The 1.0 s station hold and the 0.65 s mount hold share X, which is safe only while board and station are never focused together.
- With vocals off by default, the mode stays quiet on creature audio until the owner decides.
- Vendor death-flow updates never reach survival, by design.

## 10. Roster asset mapping and content gaps

### What was verified on disk (2026-10-29, revised after owner decisions)

Every skeleton, data asset and clip below was inspected by parsing the package name table (`C:/Users/j6sis/AppData/Local/Temp/claude/M--AFS-Relocation-Backup-20261025-Saved-From-C/c549ba76-f9d4-4652-b871-26d23d5e3882/scratchpad/tools/uasset_names.py`), not by guessing from folder names. Numeric values come from serialized property tags (`SequenceLength`/`NumberOfFrames`/frame-rate `Numerator` for clips). Name tables show which names a package serializes; they do not show poses, body counts or channel wiring, and the text says so wherever that limit applies.

**Owner rigs.** All eleven owner skeletons (`SK_Standard01-04_Skeleton`, `SK_Brute_Skeleton`, `SK_Kid_Skeleton`, `SK_Horror/BogZombie/Mythical/Plant/Pirate_Skeleton` under `M:/UnrealProjects/AFS/Content/HoverPrototype/ZombieEngine/Variants/`) carry exactly 61 UE4-Mannequin-named bones (no `ik_*`, no `spine_04/05`, no `neck_02`, no correctives) and list `/Game/ZESP/Demo/Characters/Mannequins/Meshes/SK_Mannequin` in `CompatibleSkeletons`. That vendor `SK_Mannequin` is a USkeleton, UE5-Manny-named (100 names, correctives, `ik_*`). The vendor clips (`/Game/ZESP/ZE/Animations/Zombies/Zombie_001/AS_*`, `AM_Attack_01/02`, `AM_Death`, `AM_Hit`, `BS_Zombie_WalkRun`) and `ABP_ZombieMaster` (same folder, TargetSkeleton = that `SK_Mannequin`) therefore play on the Cyber six through compatible-skeleton registration. Two name families exist and the owner rigs are the common subset of both: the UE4 family (Feral `/Game/FeralZombie/Demo/Mannequin/Mesh/UE4_Mannequin_Skeleton`, ZAP-UE4 `/Game/ZombieAnimationPack/Demo/EpicContent/Mannequin_UE4/Mesh/SKEL_UE4_Mannequin`, both 61 + 7 `ik_*` = 68; SpaceSurvival `Heavy_space_trooper`, `Robot_scout_R_21`) and the UE5-Manny family (ZESP skeleton, ZAP-UE5 `Demo/EpicContent/Mannequin_UE5/Meshes/SKEL_Mannequin`, Etherion `/Game/Zombie/Meshes/SKEL_Zombie`, `SKEL_CyberZombie`, AAB `SK_Mannequin_SNP`, `SKEL_StoneGolem_Skeleton`). The Lakeside five were IK-retargeted (`Lakeside/RetargetSource/IK_ZombieSource`, `IK_VarietySource` -> `<Name>/Retargeted/IK_<Name>` + `RT_<Name>`, `<Name>/Variety/RT_Variety_<Name>`; all ten assets present) for proportions, not bone names.

`UHoverAuthoring::ConfigureVariantSkeleton` (`Source/HoverFlight/HoverAuthoring.cpp:136-158`) is the registration call. Gate: the mesh path must start with `/Game/HoverPrototype/ZombieEngine/Variants/` (the animation skeleton's path is not checked). It then modifies the mesh's own skeleton: `UpdateReferencePoseFromMesh(Mesh)`, `AddCompatibleSkeleton(AnimationSkeleton)`, then sets bone-translation retargeting to **Skeleton on every bone** (`SetBoneTranslationRetargetingMode(0, Skeleton, true)` is recursive), **Animation on `root` only** (second call, non-recursive) and **AnimationScaled on `pelvis`** (returns false if no `pelvis`). So registered clips keep the target mesh's bone lengths (Skeleton mode), carry root motion/translation from the clip, and scale the pelvis height. `CreateVariantPhysics` (`:170`, same gate; writes `PA_` + mesh name minus its first three characters beside the mesh, reusing an existing one) and `ConfigureCreatureLODs` (`:1016`; gate: `Variants/` + `/Optimized/` in the path + at least 4 LODs; ratios 1/.55/.25/.12, screen sizes 1/.45/.20/.08; comment: "Only isolated runtime candidates may be reduced; never touch source art") are the other gated helpers. `ConvertAppearanceTextures`/`RemapAppearanceAsset` (`:1137`, `:1113`) are gated to `/Game/HoverPrototype/Appearance/` and do not apply to zombie textures. `BuildRideBlend` (`:299`) is gated to `/Game/HoverPrototype/`, takes any `UBlendSpace` plus clips and `FVector` sample coordinates, sets the blend's skeleton from clip 0 and rebuilds the samples; it was written for the 2D ride blend.

**Data assets.** Every DA's `AppearanceMesh` is the `Optimized/SK_<Name>_LODs` copy. `DA_Standard01-04`, `DA_Brute`, `DA_Kid` reference the vendor `Zombie_001` montages and blendspace directly (`DA_Kid` name table: `AttackMontages`, `HitReactionMontages`, `DeathMontage`, `MovementBlendSpace` -> `BS_Zombie_WalkRun`, `BT_Zombie`); `DA_Brute` adds `Variants/Brute/AM_Brute_Stomp/Smash`; the Lakeside DAs reference `Retargeted/<Name>_AM_*` plus `Variety/AM_Attack_B/D`, `AM_Taking_Damage_B/D/F`. Serialized values: `DA_Brute` Height 250, CapsuleRadius 55, MaxHealth 600, WalkSpeed 140, RunSpeed 260, MaximumRunSpeed 380, MeleeDamage 75, AttackRange 210, AttackCooldown 3.5, gold 400-500, Role Brute; `DA_Kid` Height 110, CapsuleRadius 23, MaxHealth 45, WalkSpeed 240, RunSpeed 650, MaximumRunSpeed 820, AttackRange 100, AttackSphereRadius 32, AttackCooldown .85, gold 70-90, Role Kid (MeleeDamage not serialized = default 15); `DA_Horror` 185, `DA_Pirate` 185, `DA_Mythical` 205; the rest keep defaults (Height 180, CapsuleRadius 34, MaximumRunSpeed 850). `UHoverCyberZombieDefinition` (`HoverCyberVariants.h`) adds `AppearanceMesh`, `Role`, `Height` (min 50), `CapsuleRadius` (min 10), `MaximumRunSpeed`, `StompRadius` 400 (min 100) on top of `UZE_ZombieDataAsset`. ZE defaults (`Plugins/ZombieEngineStudio/.../ZE_ZombieSettings.h`): MaxHealth 100, `CorpseLifespan` 15, WalkSpeed 150, RunSpeed 450, `HeadBoneName "Head"` (FName compare is case-insensitive), MeleeDamage 15, AttackRange 150, AttackCooldown 1.5, AttackSphereRadius 50, gold 10-50; `AggroSound`/`AttackSound`/`DeathSound` are soft pointers no DA serializes. `AHoverCyberZombie::BeginPlay` (`HoverCyberCity.cpp:441-465`) scales the mesh by `Height / (bounds.BoxExtent.Z*2)`, sets the capsule to `(CapsuleRadius, Height*.5)`, offsets the mesh so its bounds bottom sits on the capsule bottom, calls `EmptyOverrideMaterials()` (so the mesh's own slot materials apply), sets yaw rate 220 for Brute else 600 (`:463`) and MaxAcceleration 2600 for Kid else 1400 (`:464`); `StompImpact` (`:507-509`) is gated to Role Brute; the nav agent height is fixed at 210 cm (`:51`); `AHoverCyberZombieAI::OnPossess` (`:238-256`) installs `UCrowdFollowingComponent` with separation weight 3, query range 500, avoidance High, anticipate turns. ZE has no attack-slot ring: `ZE_BTService_CheckAttackRange` sets CanAttack when `FVector::Dist` (3D, actor centre to actor centre) <= `AttackRange` (+30 hysteresis once in range), and `OnAttackHitCheck` (`ZE_ZombieCharacter.cpp:428-447`) sphere-sweeps from actor location + 40 cm forward along `AttackRange` with radius `AttackSphereRadius` on ECC_Pawn. `UHoverCyberEncounterSettings`: `BruteFirstWave 12`, `BruteInterval 2` (>= 11), `SwarmFirstWave 5`, `SwarmInterval 10`, `SwarmCount 8` (1-24), `SwarmSpawnInterval .65`; `IsSwarmWave` = `Wave >= SwarmFirstWave && (Wave - SwarmFirstWave) % SwarmInterval == 0`; `IsBruteWave` excludes swarm waves and puts exactly one Brute at SpawnIndex 0 (`SelectZombieData`, `:186-197`); swarm waves spawn `SwarmCount` Kids only. `EHoverZombieRole` is `Standard/Brute/Kid`; there is no boss schedule and no spawn-point tag logic in code.

**StoneGolem (`M:/UnrealProjects/AFS/Content/StoneGolem`).** `Mesh/SKM_StoneGolem` serializes two material names, `Materials/M_StoneGolem_Body` and `M_StoneGolem_Armor` (also as the original FBX material names), and nine FBX geometry names (`Body_geo`, `Armor_{Belt,Bracers,ChestArmor,Greaves,HandArmor,Helmet,Pauldron,ThighArmor}_geo`), so the two slots are `M_StoneGolem_Body` and `M_StoneGolem_Armor`; `Mesh/Parts/SKM_StoneGolem_Body` binds `MI_StoneGolem_Body_Skin1`, the eight `SKM_StoneGolem_Armor_*` parts bind `MI_StoneGolem_Armor_Skin1`; all on `SKEL_StoneGolem_Skeleton`. Each master samples seven textures (`T_StoneGolem_<Part>_{Albedo_Skin1,Emission(_Skin1),Metallic,Normal,Occlusion,Roughness,Specular}`) through plain `TextureSample` nodes except two `TextureSampleParameter2D`s named `Albedo Texture` and `Emissive Texture` (plus a scalar `Emissive` and a Multiply); the 12 `MI_*_Skin1-4` override only those. `SKEL_StoneGolem_Skeleton`: 91 bones, Manny-named without correctives (`spine_01-05`, `neck_01/02`, `*_twist_01/02`, metacarpals, `ik_foot_root/l/r`, `ik_hand_root/gun/l/r`, `interaction`, `center_of_mass`) plus `weapon_l`/`weapon_r` bones and the sockets `weapon_lSocket`/`weapon_rSocket`. `PHYS_StoneGolem` name table carries 22 bone names (pelvis, spine_02/03/04/05, neck_01/02, head, clavicle/upperarm/lowerarm/hand/thigh/calf/foot L/R) and named primitives (`spine_02_capsule`, `clavicle_r_capsule`, `head_capsule`, `neck_01_capsule`, `neck_02_capsule`, `hand_l/r_box`, `foot_l/r_box`); the exact body count is not decodable from the name table. Clips (all 30 fps, decoded `SequenceLength`/`NumberOfFrames`): idle1 10.0 s/300 f, walkF 1.13/34, jogF 0.77/23, turn180 2.33/70, dodge 1.23/37, gethit1 1.0/30, gethit2 1.8/54, gethit3 1.8/54, death1 3.5/105, death2 2.0/60, death3 2.53/76, attack1 2.97/89, attack2 2.50/75, attack3 1.73/52, attack4 2.93/88, attack5 4.40/132 (idle2-4, walk/jog B/L/R not decoded). No clip serializes an `AnimNotifyEvent` (only empty `AnimNotifyTracks`). Every clip carries `FBX.<bone>.lockInfluenceWeights` for all 91 bones (and `filmboxTypeID`, `blendParent1`), i.e. Maya FBX custom attributes imported for every bone; they say nothing about how the weapon bones were animated. attack4, attack5 and dodge additionally serialize `RawCurveTracks`/`FloatCurves` (`AnimationCurveData`), i.e. real float curves whose names are not in the table. `Blueprint/BP_StoneGolem` is the vendor demo pawn: `CapsuleHalfHeight 90`, `CapsuleRadius 35`, `AgentRadius 42`, `AgentHeight 192` (so the vendor sizes the golem as a ~180-190 cm character at scale 1), two StaticMeshComponents (`SM_StoneGolem_Hammer`, `SM_StoneGolem_Shield`) with `weapon_lSocket`/`weapon_rSocket` as attach names (which socket takes which mesh is not decodable), Enhanced Input `IA_Jump/Look/Move`, anim class `Demo/ABP_StoneGolem`. `ABP_StoneGolem` is a third-person-template graph on `SKEL_StoneGolem_Skeleton`: `Demo/BS_MM_WalkRun` (built from `Demo/MM_Walk_Fwd`, `MM_Run_Fwd`, `MM_Walk_InPlace` copies on the golem skeleton), `MM_Idle/Jump/Fall_Loop/Land`, `CR_Mannequin_BasicFootIK`, one `DefaultSlot`; none of the 25 `AS_StoneGolem_*` clips are referenced by it. Mesh bounds are in bulk data and were not measured.

**Substance export (`C:/Users/j6sis/OneDrive/Documents/Adobe/Adobe Substance 3D Painter/export`).** 24 PNGs, all 4096x4096, 8-bit, PNG colour type 2 (RGB): primary `stoneUntitled_M_StoneGolem_{Body,Armor}_{BaseColor,Normal,OcclusionRoughnessMetallic}` (Oct 29 07:18; 8.9/17.4/9.2 MB body, 8.9/20.0/12.0 MB armor); secondary `M_StoneGolem_{Body,Armor,Weapon}_{BaseColor,Normal,Roughness,Metallic,Displacement}` (Oct 25 08:15; `Body_Metallic` and `Armor_Metallic` are 49,073 bytes each, i.e. flat; `Weapon_Metallic` 3.1 MB is not flat); third `0e26c14a-11c1-4c0f-893b-06a2de061c8f (1)_Material_{BaseColor,Normal,OcclusionRoughnessMetallic}` (Oct 25 09:08, 20.7/33.1/21.0 MB).

**Kid (`Variants/Kid`).** Files: `SK_Kid`, `SK_Kid_Skeleton` (`CompatibleSkeletons` -> ZESP `SK_Mannequin`), `SK_Kid_PhysicsAsset`, `PA_Kid`, `Optimized/SK_Kid_LODs`, `M_Kid_0`, `Material_001`, `T_Kid_0_BaseColor/Normal/RM`, `DA_Kid`. **Open issue:** `SK_Kid` and `SK_Kid_LODs` serialize one slot, `Material_001`, bound to `/Game/HoverPrototype/ZombieEngine/Variants/Kid/M_Kid`, and no `M_Kid.uasset` exists on disk (nor in the relocation backup). The material that exists is `M_Kid_0` (asset registry object `M_Kid_0.M_Kid_0`; three `TextureSample`s: `T_Kid_0_BaseColor`, `T_Kid_0_Normal`, `T_Kid_0_RM` with `SAMPLERTYPE_Masks`; material inputs BaseColor/Normal/Roughness/Metallic/AmbientOcclusion are in its table, channel wiring is not decodable); `Material_001` is the Interchange FBX Phong instance (`FBXLegacyPhongSurfaceMaterial`, `DiffuseColorMap`/`NormalMap` = `T_Kid_0_BaseColor/Normal`, no RM). The same pattern holds for Brute (`SK_Brute` slot `Material_002` -> missing `M_Brute`; `M_Brute_0` exists) and Standard01 (slot `Material_003` -> missing `M_Standard01`; `M_Standard01_0` exists). Either the editor holds unsaved reassignments or these slots resolve to the engine default material at runtime; verify in the editor and, if needed, assign `M_<Name>_0` and resave `SK_<Name>` + `Optimized/SK_<Name>_LODs`. The Lakeside convention (`Docs/ZOMBIE_SPECIALS_20261024.txt:87-88`): BaseColor/Normal/RM, source PNGs stay 4K, runtime max 2048, RM green = roughness, blue = metallic.

**Clip sources (lengths decoded).** ZAP-UE4 (`/Game/ZombieAnimationPack/Animations/Mannequin_UE4/`, on `SKEL_UE4_Mannequin`, 30 fps; a UE5 twin exists under `Mannequin_UE5/`): `anim_Belly_Crawling_A` 3.0 s, `_B` 6.0, `anim_Laying_Idle_A/B` 6.0 each, `anim_Burst_A` 1.0, `anim_Burst_B-I,K` 3.0 each (10 clips, no J), `anim_Attack_A` 3.33, `_B` 3.0, `_C` 3.9, `_D` 2.0, `anim_Run_A` 2.67, `anim_Idle_A` 3.97, `_B` 2.0, `anim_Impaled_A/B` 6.0, `anim_Taking_Damage_A/B/C` 0.67, `_D/E` 1.33, `_F` 1.0, `anim_Walk_A-C` 3.97; no `bEnableRootMotion` serialized (default off, in place) and no notify events. Feral (29 clips on `UE4_Mannequin_Skeleton`, no notify events): `LeapForward_Full` 1.2 s, `LeapForward_Short` 0.47, `StrongAttack_01` 1.5, `_02` 1.87, `_03` 2.13, `Reanimate` 2.8, `Feasting_01/02/03` 2.73 each, `Run` 0.5, `Walk` 0.73, `Walk_02` 0.7, `Attack_LeftSwipe` 1.67, `Attack_RightSwipe` 1.67, `Attack_Combo` 2.4, `HitReact_01-04` 0.4 each, `Death_01` 0.63, `Death_02` 0.47, `Idle_01` 3.33, `Idle_Roar_01` 1.67, `_02` 2.6, `Idle_Sniffing` 1.53. Etherion (`/Game/Zombie/Animations`, on `SKEL_Zombie`): `Anim_Zombie_Walk_Giant` 2.53 s at 60 fps (carries `AnimNotify_MovingZombieFootstep`, a Blueprint notify at `/Game/Zombie/Sound/Footsteps/`), `Anim_Zombie_Roar` 3.8 s at 60 fps, `Anim_Zombie_Attack` 2.4 s at 30 fps (`AnimNotify_PlaySound` -> `Sound/Whoosh/SC_Whoosh`). Other rigs, SpaceSurvival and the Fab vault are as recorded in v1 (AAB 25 part SKMs on `SK_Mannequin_SNP`; `SK_CyberZombie` on `SKEL_CyberZombie` with `ABP_ZombieMale_AAB_PostProcess`; Etherion 18 sequences + 10 montages, no death clip; `Easy_Shockwaves_VFX` (`VFX_Shockwave_01_White_1s/_Big_1s/_Small_1s` present) and `Sci_Fi_Weapons_VFX_AIO` imported; `FeralZoma90ca3c7aa32V2` vault = the imported 29 clips; Paragon/Pistol-Rifle FBX not imported; Etherion listing `is_ai_forbidden=1`). `NS_NS1_BloodShot` is at `Content/Rocket/NS1_Blood/`.

### Owner decisions applied (2026-10-29)

1. StoneGolem stays as the mid-level boss, as is, unarmed: `SM_StoneGolem_Hammer/Shield` excluded, `weapon_l/r` sockets left empty. No replacement is coming; the boss-slot interface is replaced by the build spec below.
2. The Oct 29 `stoneUntitled_*` Body/Armor set is the primary texture set; the Oct 25 set is optional; the GUID set has no confirmed target.
3. The Kid is the horde unit and crawls fast.
4. The same Kid mesh, scaled to 300-340 cm, is a second boss-style enemy, "Giant Kid" (placeholder name), with its own clips.
5. Horde rounds every 5 from R5: `SwarmInterval` 10 -> 5 (swarm waves 5, 10, 15, 20, ...). `IsBruteWave` skips swarm waves, so with `BruteFirstWave` 16 / interval 2 the brute lands on 16, 18, 22, 24, 26, 28, 32 ... and boss rounds 20/30/40 coincide with horde rounds (open question below).

### Mapping table

Speed tier (walker/runner/sprinter) is a per-spawn roll on `RunSpeed`/`MaximumRunSpeed`, so the four Standards are skins for all tiers. "Registration" = `ConfigureVariantSkeleton` adding the source skeleton to the owner skeleton's `CompatibleSkeletons` (the array takes several), the mechanism that already plays the vendor Manny clips on the Cyber six; it is unexercised with Feral/ZAP/Etherion sets, so each such row needs a visual check.

| Mesh (DA mesh) | NYC role | Clip source | Retarget needed | Height / capsule | Notes |
|---|---|---|---|---|---|
| SK_Standard01 (`Optimized/SK_Standard01_LODs`) | Walker/runner skin A (R1+) | ZE `Zombie_001` direct | None (live) | 180 / 34 | Also the "last zombie forced sprint" body; slot `Material_003` -> missing `M_Standard01` (see Kid open issue) |
| SK_Standard02 | Walker/runner skin B | Same | None | 180 / 34 | |
| SK_Standard03 | Sprinter skin (weighted from R9) | ZE + Feral `Run`, `Attack_Left/RightSwipe` | Registration of Feral `UE4_Mannequin_Skeleton` | 180 / 34 | |
| SK_Standard04 | Sprinter / ground-emerge skin | ZE + ZAP-UE4 `anim_Burst_A-I,K` | Registration of `SKEL_UE4_Mannequin` | 180 / 34 | Emergence only on spawn points carrying a proposed `Ground` tag (no such tag exists in code yet) |
| SK_Kid (`Optimized/SK_Kid_LODs`), `DA_Kid` | **Horde crawler** (R5, every 5; `SwarmInterval` 5, `SwarmCount` 8, `.65 s`) | ZAP-UE4 `anim_Belly_Crawling_A/B`, `anim_Laying_Idle_A/B`, `anim_Burst_A-I,K`; attacks from Feral `LeapForward_Short` + ZAP `anim_Attack_D` (see crawler spec) | Registration of `SKEL_UE4_Mannequin` and Feral `UE4_Mannequin_Skeleton` on `SK_Kid_Skeleton` | 110 (mesh scale) / 23, capsule half-height 23 via new override | 45 HP, 650-820 cm/s, .85 s cooldown already authored; AttackRange 100 -> 130, AttackSphereRadius 32 -> 45; fix the `M_Kid` slot binding first |
| SK_Kid (`Optimized/SK_Kid_LODs`), **new `DA_GiantKid`** | **Giant Kid** boss-style B (R16+ alternating with Brute/Mythical, active cap 1) | Feral `LeapForward_Full/Short`, `StrongAttack_01-03`, `Reanimate`, `Feasting_01-03`; Etherion `Walk_Giant`, `Roar` | Registration (Feral: UE4 family; Etherion: Manny family, drops `spine_04/05`, `neck_02`, `twist_02` tracks); IK route `IK_FeralSource` -> new `IK_Kid` -> `RT_Feral_Kid` if proportions fail | 320 / 60 | Same mesh/textures as the crawler; see Giant Kid spec |
| SK_Pirate | Light armored (R9+, never sprints) | Lakeside Retargeted + Variety | None; cap `MaximumRunSpeed` ~450 | 185 / 34 | Armor = extra HP pool, no plates yet (gap) |
| SK_BogZombie | Heavy armored (R17+) | Lakeside + optional Etherion `Walk_Giant`/`Roar` | Registration of `SKEL_Zombie` or new `IK_EtherionSource` -> `IK_BogZombie` | 180 -> 195 / 40 | 21,967 tris |
| SK_Horror | Feral special (R11+, leap, feast, reanimate) | Feral full set via new `RT_Feral_Horror` (`IK_FeralSource` -> `IK_Horror`) | One new IK source + one RT (or registration) | 185 / 34 | |
| SK_Plant | Spore special (R12+, emerge, AoE burst) | Lakeside + ZAP `anim_Burst_*`, `anim_Laying_Idle_A/B` through `IK_VarietySource` -> `IK_Plant` | Batch-retarget 12 clips | 180 / 36 (proposal) | AoE = `Easy_Shockwaves` ring + `StompRadius` |
| SK_Mythical | Elite A (R16, every 3-5, cap 1) | Lakeside + Feral `StrongAttack_01-03`, `LeapForward_Full`, `Idle_Roar_01/02` via `RT_Feral_Mythical` | One new RT reusing `IK_Mythical` | 205 -> 230 / 45 | 26,182 tris |
| SK_Brute | Heavy / elite (R16 alt, cap 1-2) | Own `AM_Brute_Stomp/Smash` + ZE + Feral `StrongAttack_02` | Registration | 250 / 55 | 600 HP, `UHoverBruteStompNotify` in `AM_Brute_Stomp`; `BruteFirstWave` 12 -> 16; slot `Material_002` -> missing `M_Brute` (see Kid open issue) |
| **StoneGolem** (new `Variants/Golem/Optimized/SK_Golem_LODs`), **new `DA_StoneGolem`** | **Boss** (R20/30/40 HVT) | Own 25 clips on the golem skeleton, unarmed | Register ZESP `SK_Mannequin` on the golem skeleton so `ABP_ZombieMaster` runs (see caution in the build spec) | 320 / 70 (bounds unmeasured; the vendor pawn is sized as ~180-190 cm, so 320 is a ~1.7x upscale) | New `EHoverZombieRole::Boss`; nav agent stays 210 cm (brute precedent) |

### StoneGolem boss build spec (unarmed, as is)

**Runtime copy and path gates.** Keep `/Game/StoneGolem/` as source art (`ConfigureCreatureLODs`: "Only isolated runtime candidates may be reduced; never touch source art"). Duplicate `SKM_StoneGolem` to `/Game/HoverPrototype/ZombieEngine/Variants/Golem/SK_Golem` and `Optimized/SK_Golem_LODs` (4 LODs, then `ConfigureCreatureLODs`). **Caution on the skeleton:** `ConfigureVariantSkeleton(SK_Golem_LODs, ZESP SK_Mannequin)` passes the gate (mesh path only) but edits the mesh's *skeleton* asset: it re-reads the reference pose from the LOD copy, appends `SK_Mannequin` to `CompatibleSkeletons`, and switches every bone to Skeleton translation retargeting (root Animation, pelvis AnimationScaled). If the copy still points at `/Game/StoneGolem/Mesh/SKEL_StoneGolem_Skeleton`, that edits source art and changes how the golem's own 25 clips evaluate bone translations (from the skeleton's reference pose instead of the clip; for same-rig clips this is normally invisible, but attack4/attack5/dodge carry float curves and must be viewport-checked). Preferred: duplicate the skeleton to `Variants/Golem/SKEL_Golem`, assign it to `SK_Golem`/`SK_Golem_LODs`, and duplicate-and-retarget the 25 clips (and `PHYS_StoneGolem` as `PA_Golem`) onto it (identical hierarchy, lossless); then run `ConfigureVariantSkeleton` on the copy. The registration lets `BP_CyberZombie`'s `ABP_ZombieMaster` (TargetSkeleton = `SK_Mannequin`) run on the golem exactly as on the eleven owner rigs; `CreateVariantPhysics` is optional (it would write `PA_Golem_LODs` for the LOD mesh name). Do not spawn `BP_StoneGolem`; its ABP has no attack wiring and it attaches the excluded hammer/shield.

**Clips and montages (all on the golem skeleton; the montage slot must match the slot node in `ABP_ZombieMaster`, which was not decoded).** The name tables cannot show poses, and the per-bone `lockInfluenceWeights` entries are generic FBX attributes, so nothing on disk says which clips are hammer swings, shield moves or unarmed; the choice below is by length only and must be confirmed in a five-clip viewport pass:

| Clip | Length | Proposed slot | Unarmed read |
|---|---|---|---|
| `attack3` | 1.73 s / 52 f | `AM_Golem_Attack_Light_A` | Shortest; a jab/backhand reads as a fist strike without change |
| `attack2` | 2.50 s / 75 f | `AM_Golem_Attack_Light_B` | Medium swing; sell as a forearm sweep (hit notify at the arm's lowest frame) |
| `attack1` | 2.97 s / 89 f | `AM_Golem_Attack_Heavy_A` | Long arc; keep only if the wrist stays open-handed, otherwise cut |
| `attack5` | 4.40 s / 132 f (float curves) | `AM_Golem_Slam` | Longest; if the viewport shows a two-handed overhead, sell it as a double-fist ground pound: `UHoverBruteStompNotify` at the landing frame + `Easy_Shockwaves` ring scaled to `StompRadius` |
| `attack4` | 2.93 s / 88 f (float curves) | Reserve | Keep only if it reads as a shoulder barge or arm sweep; drop if it is a shield move |

Selling the fists: large `AttackSphereRadius` (90) so the arm volume registers; impact VFX (`VFX_Shockwave_01_White_Small_1s`) spawned at `hand_r`/`hand_l` on the hit-check notify; `weapon_lSocket`/`weapon_rSocket` stay empty; no mesh edits. Other montages: `AM_Golem_Hit_1-3` from `gethit1` (1.0 s), `gethit2` (1.8 s), `gethit3` (1.8 s); `AM_Golem_Death_1-3` from `death1` (3.5 s), `death2` (2.0 s), `death3` (2.53 s); `AM_Golem_Intro` from `idle1` first 3 s or `turn180` (2.33 s, spawn telegraph); `BS_Golem_WalkRun` 1D on speed from `idle1` (0), `walkF` (1.13 s, walk speed), `jogF` (0.77 s, run speed); `dodge` (1.23 s, float curves) is a bonus sidestep on ranged hits. Build the blendspace by hand (`BuildRideBlend` could populate the samples for any blend under `/Game/HoverPrototype/`, but it was written for the 2D ride blend).

**`DA_StoneGolem`** (`UHoverCyberZombieDefinition`, `/Game/HoverPrototype/ZombieEngine/Variants/Golem/DA_StoneGolem`): `AppearanceMesh` = `Optimized/SK_Golem_LODs`, `Role` = new `EHoverZombieRole::Boss`, Height 320, CapsuleRadius 70, MaxHealth 2400 (4x brute; Cold War proxies 6.66x-13x base), WalkSpeed 160, RunSpeed 300, MaximumRunSpeed 380, MeleeDamage 90, AttackRange 240, AttackSphereRadius 90, AttackCooldown 3.0, `StompRadius` 500 (existing DA field), gold 900-1200, `HeadBoneName` default `"Head"` resolves to the golem's `head`. Code: `HoverCyberCity.cpp:463` yaw rate and `:509` stomp gate must accept Boss as they do Brute; the 210 cm nav agent is accepted (brute precedent); boss spawn on 20/30/40 needs a `BossFirstWave`/`BossInterval` pair in `UHoverCyberEncounterSettings` plus a `SelectZombieData` branch (code; `ConfigureWave` currently knows only swarm and standard rosters).

**Materials.** See the texture import table; the runtime copy's two slots (`M_StoneGolem_Body`, `M_StoneGolem_Armor`) take `MI_Golem_Body` and `MI_Golem_Armor`. The part SKMs are not needed for the single-mesh boss; if break-off armor is wanted later, the eight armor parts are already skinned to the same skeleton and bind `MI_StoneGolem_Armor_Skin1`, so they would take `MI_Golem_Armor` on the same slot.

### Golem texture import table

Target folder `/Game/HoverPrototype/ZombieEngine/Variants/Golem/` (inside the HoverAuthoring `Variants/` gate; no authoring helper touches textures, so this is a plain editor import). Lakeside naming `T_<Name>_BaseColor/Normal/RM`; source 4K kept, Maximum Texture Size 2048, Texture Group Character. Painter's ORM export packs R = occlusion, G = roughness, B = metallic (per its channel naming; confirm on import), which matches the RM convention (green roughness, blue metallic) with red as spare AO. The existing masters expose only `Albedo Texture`/`Emissive Texture`, so Normal and RM cannot be bound through an instance of `M_StoneGolem_Body/Armor`; create one local master `M_Golem` in the target folder modeled on `M_Kid_0` (BaseColor sRGB, Normal, RM Masks sampler with G -> Roughness, B -> Metallic, R -> AO; `M_Kid_0`'s own channel wiring is not decodable and must be read in the editor) and two instances.

| Source PNG (export folder) | Asset path | Settings | Binds to |
|---|---|---|---|
| `stoneUntitled_M_StoneGolem_Body_BaseColor.png` | `Variants/Golem/T_Golem_Body_BaseColor` | sRGB, max 2048 | `MI_Golem_Body` BaseColor -> slot `M_StoneGolem_Body` on `SK_Golem_LODs` (and `Parts/SKM_StoneGolem_Body`) |
| `stoneUntitled_M_StoneGolem_Body_Normal.png` | `Variants/Golem/T_Golem_Body_Normal` | Normalmap, linear; check green orientation (Painter's Unreal preset exports DirectX; a generic PBR preset exports OpenGL and needs Flip Green) | `MI_Golem_Body` Normal |
| `stoneUntitled_M_StoneGolem_Body_OcclusionRoughnessMetallic.png` | `Variants/Golem/T_Golem_Body_RM` | Masks, sRGB off | `MI_Golem_Body` RM |
| `stoneUntitled_M_StoneGolem_Armor_BaseColor.png` | `Variants/Golem/T_Golem_Armor_BaseColor` | sRGB, max 2048 | `MI_Golem_Armor` -> slot `M_StoneGolem_Armor` on `SK_Golem_LODs` (and the eight `SKM_StoneGolem_Armor_*` parts) |
| `stoneUntitled_M_StoneGolem_Armor_Normal.png` | `Variants/Golem/T_Golem_Armor_Normal` | Normalmap, same orientation check | `MI_Golem_Armor` Normal |
| `stoneUntitled_M_StoneGolem_Armor_OcclusionRoughnessMetallic.png` | `Variants/Golem/T_Golem_Armor_RM` | Masks | `MI_Golem_Armor` RM |
| `M_StoneGolem_Body_BaseColor/Normal.png` (Oct 25, optional) | `Variants/Golem/Alt/T_Golem_Body_BaseColor_v0`, `_Normal_v0` | As above | `MI_Golem_Body_v0` fallback skin only if the Oct 29 set is rejected |
| `M_StoneGolem_Body_Roughness.png` + `_Metallic.png` (flat, 49 KB) | Pack into `Alt/T_Golem_Body_RM_v0` (G/B; R from vendor `T_StoneGolem_Body_Occlusion`) | Masks | Same fallback |
| `M_StoneGolem_Armor_*` (Oct 25) | Same pattern under `Alt/` | | Same fallback |
| `M_StoneGolem_*_Displacement.png`, `M_StoneGolem_Weapon_*.png` | Not imported | | Displacement unused (no tessellation path); weapons excluded |
| `0e26c14a-...(1)_Material_{BaseColor,Normal,OcclusionRoughnessMetallic}.png` | Hold at source | | Target mesh unconfirmed; the GUID naming matches Tripo material names in Lakeside (`Horror/tripo_mat_485b43f2-...`, `Pirate/tripo_mat_2285bdde-...`), so it may be a re-texture of a Tripo-generated body, not the golem; the Kid's FBX material is a Phong `Material_001`, not a Tripo name |

The vendor `T_StoneGolem_*` set and `MI_*_Skin1-4` stay in `/Game/StoneGolem/` untouched as fallbacks.

### Kid horde crawler spec

**Prerequisite.** Confirm in the editor that `SK_Kid`/`SK_Kid_LODs` slot `Material_001` resolves to `M_Kid_0` (on disk it references a missing `M_Kid`); otherwise the crawler and the Giant Kid render with the default material.

**Locomotion.** `BS_Kid_Crawl` (1D on speed, on `SK_Kid_Skeleton` after `ConfigureVariantSkeleton(SK_Kid_LODs, SKEL_UE4_Mannequin)`): `anim_Laying_Idle_A` (6.0 s) at 0, `anim_Belly_Crawling_A` (3.0 s) at 240 (walk), `anim_Belly_Crawling_B` (6.0 s) at 650-820. The ZAP crawls are in place (no root-motion flag) and authored at crawl pace, so at 650-820 cm/s drive the sample PlayRate from speed (speed/150, clamped 1-4) in `ABP_ZombieMaster` or a child ABP; otherwise the kid slides. `DA_Kid.MovementBlendSpace` takes `BS_Kid_Crawl` in place of `BS_Zombie_WalkRun`; the `MaxAcceleration` 2600 Kid branch stays. Registration keeps the kid's bone lengths (Skeleton retargeting on all bones) and scales the pelvis height, so the adult crawl pose should sit on the kid's shorter limbs without the hands floating; verify.

**Emergence.** `anim_Burst_A` (1.0 s) and `anim_Burst_B-I,K` (3.0 s each) as `AM_Kid_Burst_*` on spawn points carrying the proposed `Ground` tag (no tag logic exists in code yet). Whether a burst ends standing or prone is not decodable from disk: if standing, blend 0.3 s into the crawl idle or prefer `anim_Burst_A` for the horde's pace.

**Capsule.** `BeginPlay` derives both the mesh scale and the capsule half-height from `Height`, so a shorter capsule needs a new `float CapsuleHalfHeight = 0` (0 = `Height*.5`) in `UHoverCyberZombieDefinition`; for the crawler set 23 (= radius, a 46 cm tall sphere-capsule) and change the mesh offset to `-HalfHeight - (Bounds.Origin.Z - Bounds.BoxExtent.Z) * Scale`. The mesh still scales to a 110 cm standing kid; the crawl pose is then roughly 35-45 cm tall and the capsule covers it.

**Attacks at crawl height.** ZE has no slot ring; spacing comes from the crowd separation (weight 3, query range 500) and the 23 cm radius, which packs eight kids around the rider. The in-range test is 3D centre-to-centre: with the crawler centre about 23 cm up and the rider's capsule centre around 90 cm, a 100 cm `AttackRange` leaves only about 70 cm of horizontal reach, so set AttackRange 130 (horizontal about 110) and AttackSphereRadius 45 so the low sweep (actor centre + 40 cm forward) still overlaps the rider's capsule bottom. Clips: `AM_Kid_Lunge` from Feral `LeapForward_Short` (0.47 s; a low pounce that reads as a bite from the crawl, hit notify at landing) and `AM_Kid_Attack_B` from ZAP `anim_Attack_D` (2.0 s, trimmed to the swipe, upper-body slot blended over the crawl pose); hit reacts ZAP `anim_Taking_Damage_A/B` (0.67 s); deaths: Feral `Death_01`/`Death_02` are only 0.63 s/0.47 s, so use them as the drop-to-ground start followed by ragdoll (`PHYS`/`PA_Kid`) and `CorpseLifespan` 15 s, or keep the vendor `AM_Death` (already registered). No pack ships a true belly-crawl attack (gap below).

### Giant Kid spec (placeholder name)

**`DA_GiantKid`** (`/Game/HoverPrototype/ZombieEngine/Variants/Kid/DA_GiantKid`): `AppearanceMesh` = `Kid/Optimized/SK_Kid_LODs` (same LODs and `T_Kid_0_*` textures; at 2.9x the crawler's scale the 2048 runtime textures will read soft up close, acceptable for a placeholder), `Role` Boss (Brute until Boss exists, for the 220 yaw rate and stomp gate), Height 320, CapsuleRadius 60, MaxHealth 1500, WalkSpeed 200, RunSpeed 420, MaximumRunSpeed 520, MeleeDamage 60, AttackRange 260, AttackSphereRadius 90, AttackCooldown 2.4, `StompRadius` 450, gold 450-600. `BeginPlay` sets the mesh scale to `Height / (bounds.Z*2)`, so the giant is 320/110 = 2.9x the crawler's scale with no extra code.

**Unique clips.** `BS_GiantKid_WalkRun`: Etherion `Anim_Zombie_Walk_Giant` (2.53 s, 60 fps) at 0-200, Feral `Run` (0.5 s) at 520 with PlayRate 0.7 to sell mass; `AM_GiantKid_Charge` from `LeapForward_Full` (1.2 s, gap-closer telegraph) and `AM_GiantKid_Pounce` from `LeapForward_Short` (0.47 s); `AM_GiantKid_Strong_01-03` from `StrongAttack_01-03` (1.5/1.87/2.13 s), stomp notify on 03; `AM_GiantKid_Rise` from `Reanimate` (2.8 s) as the spawn-in and a one-time second life at 30% HP; `Feasting_01-03` (2.73 s each) as the no-target idle; `Anim_Zombie_Roar` (3.8 s) as the round-start telegraph; hit reacts Feral `HitReact_01-04` are 0.4 s each (short; fine for a boss that barely flinches). `Walk_Giant` carries `AnimNotify_MovingZombieFootstep` (Etherion Blueprint footstep notify) which fires once the clip plays on the kid.

**Retarget route.** Feral clips are UE4-family (owner bones + `ik_*`): one `ConfigureVariantSkeleton` call registers `UE4_Mannequin_Skeleton` on `SK_Kid_Skeleton` (`CompatibleSkeletons` already holds the ZESP skeleton and takes more). Etherion is Manny-family: registration drops `spine_04/05`, `neck_02` and `twist_02` tracks, so `Walk_Giant` loses some upper-back bend. Registration keeps the kid's bone lengths (Skeleton translation retargeting on every bone) and scales only the pelvis height (AnimationScaled), so adult-authored clips keep child proportions and feet may slide or hands may miss the ground in `Feasting`; if that fails the viewport check, follow the Lakeside precedent: new `IK_FeralSource` on `UE4_Mannequin_Skeleton` (shared with `RT_Feral_Horror/Mythical`), new `IK_Kid` chain rig, `RT_Feral_Kid`, baked clips under `Kid/Retargeted/GiantKid_*`. The crawler and the giant share the skeleton and mesh; only the DA and clip sets differ.

### Feral-clip usage table

| Feral clip | Used by | Slot |
|---|---|---|
| `Run` (0.5 s), `Walk` (0.73), `Walk_02` (0.7) | Horror, Standard03, Giant Kid | Sprinter/feral blendspace |
| `LeapForward_Short` (0.47 s) | Kid crawler, Giant Kid, Horror | Lunge/pounce montage, hit notify at landing |
| `LeapForward_Full` (1.2 s) | Giant Kid, Mythical, Horror | Charge telegraph |
| `Attack_LeftSwipe` (1.67), `Attack_RightSwipe` (1.67), `Attack_Combo` (2.4) | Horror, Standard03 | `AttackMontages[]` |
| `StrongAttack_01-03` (1.5/1.87/2.13) | Giant Kid, Brute, Mythical | Heavy attacks |
| `HitReact_01-04` (0.4 each) | Horror, Giant Kid | `HitReactionMontages[]` |
| `Death_01` (0.63), `Death_02` (0.47) | Horror, Kid crawler, Standard03 | `DeathMontage` start only; too short alone, pair with ragdoll |
| `Reanimate` (2.8 s) | Giant Kid, Horror | Spawn-in rise / second life |
| `Feasting_01-03` (2.73 each) | Giant Kid, Horror | No-target idle (`CorpseLifespan` 15 s) |
| `Idle_Roar_01/02` (1.67/2.6), `Idle_Sniffing` (1.53), `Idle_LookLeft/Right`, `Idle_01-03` | Mythical, Horror | Search / telegraph |

### Dismemberment plan

Unchanged from v1: AAB parts fit only the `SK_CyberZombie` fallback body (same 98-name family, leader-pose); tier 1 on all owner meshes = head-hide on headshot (`HideBoneByName('head')` + `NS_NS1_BloodShot` + neck cap decal) and leg-hide crawler conversion using the same ZAP `anim_Belly_Crawling_A/B` now built for the Kid (so the crawler blendspace serves both); tier 2 = `SK_CyberZombie` as a twelfth skin with `SKM_ZombieM_Male_BP_*` swaps; a per-bone hit path belongs in `AHoverCyberZombie`, not the licensed plugin. The golem gets no dismemberment; its `PHYS_StoneGolem` bodies ragdoll the death pose.

### Sound assignment table (Etherion pack, `Content/Zombie/Sound`)

All cue and wave names below exist on disk (`SC_*` cues; `S_Entity_Slash_A`, `S_Entity_Hit_A-C`, `S_Entity_DistantRoar_A-J`, `S_Entity_Roar_Loop`, `S_Entity_Death`, `S_Monster_Hit_A-C`, `S_Monster_Ambience_Long_A-C`, `S_Zombie_Roar_Loop`, `SC_Zombie_Footstep`).

| Role | AggroSound | AttackSound | DeathSound | Extra |
|---|---|---|---|---|
| Standard walker/runner/sprinter | `SC_ZombieV2_Chasing` (walk: `SC_ZombieV2_ChasingSlow`) | `SC_ZombieV2_AttackHiss` | `SC_ZombieV2_Death` | `SC_ZombieV2_Ambience`, `SC_Zombie_CrowdAmbience` |
| Kid crawler | `SC_Zombie_Chasing` (+0.15 pitch copy) | `SC_ZombieV2_AttackHiss` | `SC_Zombie_Death` | Crawl scrape: none in library; `SC_Zombie_Footstep` at half rate |
| Giant Kid | `SC_Entity_Roar` | `S_Entity_Slash_A` | `SC_Entity_Death` | `S_Entity_DistantRoar_A-J` spawn stinger; Etherion footstep notify from `Walk_Giant` |
| Light/heavy armored | `SC_Monster_Ambience` | `SC_Monster_Roar` | `SC_Monster_Death` | `S_Monster_Hit_A-C` on armor break |
| Feral / Spore specials | `SC_ZombieV2_AttackHiss` + `SC_Zombie_Hiss` | `SC_Zombie_Inhale` / `S_Zombie_Exhale_1-10` | `SC_ZombieV2_Death` | Reanimate: `S_Zombie_Roar_Loop` |
| Brute / Mythical | `SC_Entity_Roar` | `S_Entity_Slash_A` | `SC_Entity_Death` | |
| StoneGolem boss | `SC_Entity_Roar` + `S_Entity_Roar_Loop` | `S_Entity_Hit_A-C` (fist impacts) | `S_Entity_Death` | `S_Monster_Ambience_Long_A-C` round stinger |

Licence caveat unchanged: the Etherion listing is `is_ai_forbidden=1` with no tier recorded; usable in the licensed project, not redistributable; the audit kept silence deliberately, so this needs owner sign-off.

### Content gaps table

| Gap | Best Fab-library / SpaceSurvival candidate | In-project fallback |
|---|---|---|
| Breakable armor plates for light/heavy armored | SpaceSurvival `Heavy_space_trooper` (UE4 family); `SciFITrooper_Man_03` modular parts (own skeleton) | HP layer + metallic RM swap on Pirate/BogZombie |
| Crawler attack clips (true belly-crawl strike) | None in ZAP (only `Belly_Crawling_A/B`, `Impaled_A/B`), none in Feral, Etherion or the vault | Feral `LeapForward_Short` lunge + ZAP `anim_Attack_D` upper-body over the crawl pose; or a hand-keyed 20-frame reach on `anim_Belly_Crawling_A` |
| Crawler death clip | None (Feral `Death_01/02` are 0.63/0.47 s) | Short drop + ragdoll, or vendor `AM_Death` |
| Unique Giant Kid clips (child-proportioned giant moves) | Feral `LeapForward_Full/Short`, `StrongAttack_01-03`, `Reanimate`, `Feasting_01-03` (UE4 family); Etherion `Walk_Giant`, `Roar` (Manny family); Paragon `CrunchManny` FBX (not imported) for more brawler swings | Registration on `SK_Kid_Skeleton`, else `IK_FeralSource` -> `IK_Kid` -> `RT_Feral_Kid` |
| Golem unarmed attack clips | None; which of the five vendor attacks are weapon swings is unknown until viewed | Keep `attack3/2/5` as fist/forearm/slam if they pass the viewport check, cut clips that read as shield or hammer arcs |
| Golem Normal/RM binding | Code-free: new local master `M_Golem` (the vendor masters expose only Albedo/Emissive parameters) | Vendor `MI_*_Skin1-4` on the old 7-map masters |
| Owner mesh material bindings (`M_Kid`, `M_Brute`, `M_Standard01` missing on disk; `M_<Name>_0` present) | Editor check, not content | Reassign `M_<Name>_0` and resave the mesh + LOD copy |
| Ground-emerge / spawn VFX | SpaceSurvival `PyroVFX`, `RPGEnvironmentVFX`, `NiagaraExamples` | `Easy_Shockwaves_VFX` dust ring + `NS_NS1_BloodShot` |
| Boss slam / stomp telegraph VFX | `Sci_Fi_Weapons_VFX_AIO` impacts | `Easy_Shockwaves` ring scaled to `StompRadius` |
| Ranged special (Mangler-like) | `Scifi_gun` + weapon VFX; needs projectile code | Skip; Plant spore burst is the only AoE special |
| Animal/hellhound horde unit | None | Kid crawler |
| Heavy locomotion (giant walk, roar) | Etherion `Walk_Giant`, `Roar` | Lakeside walk at `MaximumRunSpeed` 300 |
| Creature vocals beyond Etherion; crawl scrape loop | None in library | Etherion cues or silence per audit rule |
| Nav agent for > 210 cm bodies; Boss role; capsule override; boss wave schedule; `Ground` spawn tag | Code, not content | Accept 210 cm agent; Brute role until `Boss` exists |
| 12th standard body with full dismemberment | `ZombieMale_AAB` | `SK_CyberZombie` fallback body |

## 11. Implementation plan, milestones and verification

The mode ships in seven milestones. M0 and M2 land on Cyber City first because `Scripts/VerifyCyberWaves.py` can test them today and they answer the owner's three complaints (gun feel, spawn stalls, bunching) before any NYC content exists. M1 creates the new entry (`AHoverNYCSurvivalGameMode`, `L_NYC_Survival`, level index 4), so the index-3 exploration entry and `Scripts/VerifyNYCExploration.py` (L51-53 assert zero enemies and `HoverExplorationGameMode`) stay untouched. M3-M6 fill in the loop in the order the economy needs it. Every milestone ends with a build via `Scripts/Build.ps1`, clang-format, an offscreen verify run and a dated backup under `D:/AFS_Comparisons/NYCSurvival_<date>/`. Inputs owned by other sections: Zones (extents, spawners behind doors, door prices), Economy (price constants), Enemies (`DA_NYC_*` stats), Combat (penetration, gib, tracers), HUD (plates, regen countdown, banners, damage indicator).

### Milestone table

| M | Deliverable | Owned files touched | Patched plugin files touched | New assets | Effort | Depends on |
|---|---|---|---|---|---|---|
| M0 Gunplay feel (Cyber City) | Fire shake + montage play, real recoil, hit marker/sound on every hit, rumble with counters, tracer/muzzle light, simulated flinch impulse, head gib, penetration, kill punctuation, Ballista DA retune | `HoverCombatBridge.cpp` (PlayFireAnimation L78-82), `HoverPilot.cpp` (FireShot L1389-1516, DrawHUD L1817+), `HoverPilot.h` (UHoverPilotAssets L33, counters), `HoverShotVisual.cpp` L31-40, `HoverCyberCity.cpp` (TakeDamage L549-590) | `ZE_WeaponBase.h` L278-281 (`PrevRecoil`), `ZE_WeaponBase.cpp` L1521-1527, L1532-1536 | `FF_RifleFire`, `FF_HitConfirm`, `FF_Kill` in `/Game/HoverPrototype/Weapons/`; DA_AFS_Ballista.._4 re-authored | 3.5 days | none |
| M1 Mode framework | `AHoverNYCSurvivalGameMode`, `L_NYC_Survival`, index 4, navmesh, third-person default with aim convergence, survival profile, no bike, truck unmountable, sandbox reset off | new `HoverNYCSurvival.h/.cpp`; `HoverCyberCity.h` (virtual hooks, protected members); `HoverTestController.cpp` L81-84, L106-119, L326-340, L572-576; `HoverGraphicsMenu.cpp` L70, L97 (conditional), L123, L124-125, L171, L177-180; `HoverGraphicsSettings.cpp` L186-187; `HoverAuthoring.cpp` L79, L200; `HoverPilot.cpp` L137, L283-285, L624-631, L739-741, L1400-1406, L1825 | none | `/Game/HoverPrototype/NYC/BP_NYCSurvival`, `DA_NYCWaves`, `DA_NYCEncounters`, `Maps/L_NYC_Survival`, NavMeshBoundsVolume, owned blockers | 4 days | none |
| M2 Spawn director + crowd AI (Cyber City first) | `UHoverSpawnDirector`, `UHoverAttackSlotSubsystem`, owned BT/BB, stall guard, catch-up, straggler relocation, jitter, zig-zag | `HoverCyberCity.h/.cpp` (Tick L263-330 -> `ChooseSpawner`; AI Tick L337-411; OnPossess L238-261); new `HoverSpawnDirector.h/.cpp`, `HoverAttackSlots.h/.cpp`, `HoverBTTasks.h/.cpp` | optional: `ZE_ZombieWaveGameMode.h` L118-129 `private:` -> `protected:` (only for a true re-queue) | `/Game/HoverPrototype/ZombieEngine/AI/BT_AFSZombie`, `BB_AFSZombie` | 5.5 days | M1 for NYC; runs on Cyber City alone |
| M3 Rounds, roster, bosses | CustomWaves R1-30, ConfigureWave R31+ (health, count, damage band), frozen per-actor scale, speed roll, cadence, Alpha Brute, forced boss spawn | `HoverNYCSurvival.cpp`; `HoverCyberCity.cpp` L216 (`GetEncounterLabel` virtual), AI Tick L370-395, `InitializeZombieStats` L421-429; `HoverPilot.cpp` L1652-1659 | `ZE_ZombieCharacter.cpp` L245-249 (flinch while attacking, 0.35 s), or none if driven from the override | `DA_NYC_Standard01-04`, `DA_NYC_Kid`, `DA_NYC_Brute`, `DA_NYC_AlphaBrute`, `MI_Brute_Alpha` in `/Game/HoverPrototype/ZombieEngine/Variants/NYC/` | 4.5 days | M1, M2 |
| M4 Economy, armory, PaP, armor, perks | kill points by causer/role, `AHoverArmoryStation`, `AHoverPackAPunchStation`, perk effects, vests/plates, NYC starting gear | `HoverCyberCity.cpp` TakeDamage L559-588; new `HoverStations.h/.cpp`, `HoverNYCEconomy.h`; `HoverPilot.cpp` L1652-1665; `HoverCombatBridge.cpp` RefillAmmo L328-343; `HoverAuthoring.cpp` L79 | none | `DA_Perk_Juggernog..StaminUp`, `DA_Vest_1..3`, `DA_NYCEconomy`, `BP_NYC_Armory`, `BP_NYC_PaP`, `BP_NYC_Perk_*` | 5 days | M1, M3 |
| M5 Equipment, downed, power-ups | frag/stim/self-revive, regen, downed with AI ignore, vendor game over, drop rule, all guaranteed drops, Insta-Kill/Nuke rework, hoverboard rule | `HoverPilot.h/.cpp`; `HoverCyberCity.cpp` AI Tick L343-349, TakeDamage L564-566, AHoverCyberPowerUp L627-654; `HoverNYCSurvival.cpp` | none in Stage 1 (`ZE_PowerUpPickup.h` enum in Stage 2) | `BP_NYCPower_MaxHealth`, `DA_SelfRevive`, `DA_Stim`, `DA_Grenade_Frag_NYC` | 4 days | M4 |
| M6 Zones, doors, power, placement, HUD | `UHoverZoneGraph`, `AHoverZoneDoor`, power switch + 25 s defend, 25 spawners/6 doors/7 zone volumes, nav coverage, HUD | new `HoverZones.h/.cpp`; `HoverCyberCity.cpp` UHoverCyberWaveHUD L656-696; `HoverNYCSurvival.cpp` | none | `BP_NYC_Door`, `BP_NYC_ZoneVolume`, `BP_NYC_PowerSwitch`, placed actors | 5 days | M2, M4 |

Stage 1 is about 31.5 engineer-days plus owner review (2.5 more than before, for the owned BT, penetration, aim convergence and the survival-profile hooks). `economy_floor` can only pass after M6, because PaP needs Power. Stage 2 (Riot, Alpha Brute elite, Lakeside special roles, Heavy Ballista/M16, exfil, Double/Bonus Points, traps) starts only after M6 acceptance.

### Patched-plugin ledger

The plugin copy carries exactly 14 patched files (`D:/AFS_Comparisons/AuditRepairs_20261025/after_manifest.json`, `licensed_patch_files`): `ZE_AnimNotify_AttachEquippedWeapon.cpp/.h`, `ZE_ArmorPickup.cpp`, `ZE_ZombieWaveGameMode.cpp/.h`, `ZE_InventoryWidgetBase.cpp`, `ZE_MeleeWeapon.cpp/.h`, `ZE_WeaponBase.cpp/.h`, `ZE_WallBuyActor.cpp`, `ZE_ZombieCharacter.cpp`, `ZE_WeaponDefinition.h`, `SZE_ControlPanel.cpp`. Stage 1 edits four of them again and adds no file: `ZE_WeaponBase.h/.cpp` (M0), `ZE_ZombieCharacter.cpp` (M3) and optionally `ZE_ZombieWaveGameMode.h` (M2). Stage 2 adds `ZE_PowerUpPickup.h` (two enum values). Every edit gets an original/after SHA256 entry, in the same form as `licensed_patch_files`.

**Deviation from the spine.** The NEW CODE SURFACE risk allows only the flinch rule and the Stage 2 enum. `ZE_WeaponBase` is added because recoil integration and spread recovery sit inline in the vendor weapon Tick, and an `AHoverCyberRifle` Tick that skipped Super would lose the vendor fire, reload and ammo logic. The owner must accept this deviation.

**Counters.** `ZombiesToSpawn`, `ZombiesAlive`, `LastSpawnTime` and the difficulty multipliers are private (`ZE_ZombieWaveGameMode.h` L118-142). So are `SpawnZombie`, `GetRandomSpawnPoint`, `SetWaveState` and `ApplyDifficultyToZombie` (L146-156). The director counts live `AHoverCyberZombie` actors every 0.5 s and derives unspawned = `GetZombiesRemaining()` - live. It keeps the existing enable-one-spawner mechanism (`HoverCyberCity.cpp` L309-324, consumed at `ZE_ZombieWaveGameMode.cpp` L393-411). Stragglers relocate to a fresh entrance. The actor and round accounting survive; its health resets to its own maximum on successful re-entry.

### M0: gunplay feel (Cyber City, testable today)

| Fix | Mechanism | Verified anchor |
|---|---|---|
| Fire shake + montage | `AHoverCyberRifle::PlayFireAnimation` calls `TriggerFireCameraShake()` (as vendor L900/L936 does, with no rate limit at 8 shots/s) and plays the first-person montage via `ViewArms` as `Reload()` does (`HoverCombatBridge.cpp` L95-99); it increments `AHoverPilot::FireShakeCount` | `HoverCombatBridge.cpp` L78-82 is a no-op |
| Recoil | new `PrevRecoil` member; apply `CurrentRecoil - PrevRecoil` per frame instead of `CurrentRecoil * DeltaSeconds`; kick 0.35 pitch / 0.15 yaw | `ZE_WeaponBase.h` L278-281, `.cpp` L1521-1527 |
| Spread recovery while held | `FInterpTo` branch always runs, at half rate while `bIsFiring` | `ZE_WeaponBase.cpp` L1532-1536 |
| Rumble | `ClientPlayForceFeedback(Assets->FireFeedback)` replaces `PlayDynamicForceFeedback(.18f,.06f,...)`; hit/kill effects come from `NotifyHitConfirmed`; `RumbleRequestCount` counts requests, because playback is a no-op under NullRHI with no pad | `HoverPilot.cpp` L1512-1513 |
| Hit marker + sound | `AHoverPilot::NotifyHitConfirmed(bHead, bKill)` is called after `Super::TakeDamage` (`HoverCyberCity.cpp` L571) for every `Damage > 0` from an `AHoverPilot` instigator, with the head taken from the `GetBestHitInfo` bone (L559-561) and `bKill = WasAlive && bIsDead`; it bumps `HitMarkCount`; `DrawHUD` draws four diagonals for 0.12 s (white, red kill, yellow head) | `HoverPilot.cpp` L1817 |
| Flinch impulse, flesh sound, decal | `SetAllBodiesBelowSimulatePhysics(Bone, true, false)`, then blend weight .35 + `AddImpulseAtLocation`, restored (simulate false, weight 0) after 0.18 s with a per-bone cooldown; `SpawnDecalAttached`; volume 1.0. Prerequisite: each referenced mesh has a physics asset (`CreateVariantPhysics`, `HoverAuthoring.cpp` L173) | `HoverCyberCity.cpp` L484-495, L567-568; `HoverPilot.cpp` L1510 |
| Head gib | on a headshot kill, `HideBoneByName(head)` + `NS1_Blood` | `HoverCyberCity.cpp` L587 |
| Penetration | multi-hit trace sorted by distance: 100% to the first body, then 60% to the next 1 (PaP II) or 2 (PaP III); the count lives in a HoverFlight table keyed by DA path (`ZE_WeaponDefinition.h` has no such field) | `HoverPilot.cpp` L1400-1430 |
| Tracer / muzzle light | `Clamp(Distance/40000, .12, .22)`, 250 cm minimum, per-tier Fire/Ice/Holy; transient `UPointLightComponent` (4000 cd, 60 ms) spawned in FireShot next to the muzzle flash | `HoverShotVisual.cpp` L34, L37; `HoverPilot.cpp` L1412-1430 |
| Kill punctuation | `CustomTimeDilation .15f` for 70 ms; ragdoll impulse on headshot kills | `HoverCyberCity.cpp` L587 |
| DA retune | Python `set_editor_property` directly on `DA_AFS_Ballista.._4`, with a path assert. Top level: `bAutomatic true`, `FireRate 8`, `MagazineSize 30`, `MaxReserveAmmo 270/360/450/540`, reload 1.5/1.5/1.3/1.2. Nested `combat_stats` (`FZE_WeaponCombatStats`, L912): damage 35/70/140/280, `HeadshotMultiplier 2.0`, spread 0.5/0.35/3.0/recovery 12. `_5` is unchanged until Stage 2 | `ZE_WeaponDefinition.h` L85-122, L912, L993-1021 |

No AFS authoring function edits weapon combat fields, so `Scripts/RetuneBallista.py` is new and dumps before/after values to `Evidence/ballista_tiers.json`. The Ballista DAs are shared with Cyber City and Lakeside (both load `BP_CyberWaves`), so their gunplay changes too and `VerifyCyberWaves.py`/`AssessCyberWaves.py` are re-baselined. If the owner wants those modes left unchanged, M0 authors `DA_NYC_Ballista_1..4` copies instead.

### M1: mode framework

```cpp
// Source/HoverFlight/HoverNYCSurvival.h
UCLASS()
class HOVERFLIGHT_API AHoverNYCSurvivalGameMode : public AHoverCyberCityGameMode
{
    GENERATED_BODY()
  public:
    AHoverNYCSurvivalGameMode();   // PrimaryActorTick.TickInterval = .1f (vendor .5 caps spawns at 2/s)
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldSpawnBike() const override { return false; }
    virtual bool AllowTruckMount() const override { return false; }
    virtual float GetZombieDamageScale(int32 Round, const AActor *Causer) const override; // 1.0 / 1.667 / 2.5
    virtual FString GetEncounterLabel() const override;
    UFUNCTION(BlueprintPure) float GetRoundHealth(int32 Round) const;   // table R1-30, +800/+1000, cap 25000
    UFUNCTION(BlueprintPure) int32 GetRoundQuota(int32 Round) const;    // r <= 9 lookup, else 24 + (9*r*r)/100
    int32 GetHordeCount(int32 Round) const;                             // 10 + 2r, clamp 80 (binds from R35)
    bool IsHordeRound(int32 Round) const;                               // r >= 5 && r % 5 == 0
    bool IsHeavyRound(int32 Round) const;                               // r == 8 || (r >= 12 && even && !horde && !boss)
    bool IsBossRound(int32 Round) const;                                // 13, 19, 27, then every 6
    void ApplySurvivalProfile(class AHoverPilot *Pilot);                // called from AHoverPilot::BeginPlay
    UPROPERTY() TObjectPtr<class UHoverSpawnDirector> Director;         // M2
    UPROPERTY() TObjectPtr<class UHoverZoneGraph> Zones;                // M6
    UPROPERTY() int32 PointsEarnedThisRound = 0;                        // M5
    UPROPERTY() int32 DropsThisRound = 0;                               // M5
  protected:
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                  const TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual float GetEffectiveSpawnRate() const override;
    UPROPERTY() TObjectPtr<class UHoverNYCEncounterSettings> NYCEncounters;
};
```

`AHoverCyberCityGameMode` gains four virtuals. `ShouldSpawnBike()` and `AllowTruckMount()` return true. `GetZombieDamageScale()` returns the DA multiplier, so Cyber City and Lakeside behave as today. `GetEncounterLabel()` becomes virtual. `Encounters`, `bLakeside`, `ActiveSpawnCount` and `WaveDisplay` move from private (`HoverCyberCity.h` L73) to protected. `InitGame` calls Super (which loads `DA_CyberWaves`, `HoverCyberCity.cpp` L85-88), then swaps in `/Game/HoverPrototype/NYC/DA_NYCWaves` and `DA_NYCEncounters`. It then re-runs the `WaveHUDClass = UHoverCyberWaveHUD` assignment from L97-98, because the vendor PostLogin HUD reads it. `DA_NYCWaves` authors `DeathWidgetClass = WBP_ZE_DeathRespawn`, `RespawnPolicy = RestartLevel` and `RestartLevelName = /Game/HoverPrototype/Maps/L_NYC_Survival`.

**Survival profile timing.** InitGame runs before the pawn exists. `AHoverPilot::BeginPlay` reads the persisted Invincible value at L137 and creates `Combat` only at L283-285, so `ApplySurvivalProfile` is called right after L285. It sets `bInvincible = false`, `Combat->Survival->SetMaxHealth(150)` and `SandboxHealth = 150` (L1663-1665 already mirror SandboxHealth into Survival), calls `HoverView()` once so `bReview` starts true, and swaps the 430 cm `ReviewArm` (L105) for a 300 cm right-shoulder profile. `HoverGraphicsSettings.cpp` L186-187 skips `SetInvincible` under survival, because every menu Apply (`HoverTestController.cpp` L88) re-pushes the persisted value. The Invincible row is hidden under survival: the L97 row modulus becomes 3, and L124-125 and L177-180 are skipped. The defeat auto-reset (`HoverPilot.cpp` L624-631) and the Home/R reset (L739-741) are bypassed under survival, and the fall-out-of-world reset (L1790) teleports Vexa back without healing her.

**Aim convergence.** With `bReview` set, FireShot fires along the `WorldGun` barrel (L1400-1406). Under survival it traces the camera ray to an aim point and fires from the muzzle toward it. If the muzzle path is blocked within 150 cm, the shot uses the camera hit, so shots near cover stop hitting the wall in front of Vexa.

**Vehicles and hoverboard.** At `HoverTestController.cpp` L572-576, the `GetAuthGameMode<AHoverGameMode>()` cast is null for vendor-derived modes, which is why Cyber City has a bike today. The condition gains `&& (!Cyber || Cyber->ShouldSpawnBike())`. The truck still spawns (L595-610), but `TryEnterBike` (L326-340) refuses it when `!AllowTruckMount()`. The hoverboard rule (board damage gate bypassed, 0 kill points while boarded) is placed in `AHoverPilot::TakeDamage` near L1636 and in the kill-point hook.

**Level entry.** The edits are:
- `HoverTestController.cpp` L81-84: add `Contains("L_NYC_Survival") ? 4`. Without it the survival map reads as 0 and every Apply reloads it.
- L106-109 and L116: add the map path and `game=/Game/HoverPrototype/NYC/BP_NYCSurvival.BP_NYCSurvival_C`.
- `HoverGraphicsMenu.cpp` L70: add a Survival branch (the names are disjoint, so the order does not matter).
- L123: change the level wrap `% 4` to `% 5`.
- L171: add the `NYC - Survival` label.

**Editor steps.**
1. Duplicate `L_NYC_Explore` and keep the four vendor sublevels always loaded.
2. Set GameMode Override to `BP_NYCSurvival`.
3. Keep the vendor PlayerStart (271, 5241, 162, yaw -90) and add no second one. The stall gate (`HoverCyberCity.cpp` L328-329) keeps the vendor fallback at `ZE_ZombieWaveGameMode.cpp` L413-420 unreachable.
4. Make the persistent level current, because `AddCityNavigation` creates its volume in `GetCurrentLevel()` (L209).
5. Extend the L200 gate with `L_NYC_Survival`.
6. Use bounds Center (350, 5100, 200) and Size (3200, 5200, 900), so the Garage (x -400) and Shelter (x 1,100) side zones are covered.
7. Set `ARecastNavMesh` `TileSizeUU 1000` / `TilePoolSize 4096` in the same script, because `AddCityNavigation` does not, and keep a packaged log free of nav-tile warnings as evidence.

**Cook.** `PAL_AFS_Runtime` uses ExplicitAssets, so every natively loaded asset is listed explicitly and the root count is updated: `BP_NYCSurvival`, `DA_NYCWaves`, `DA_NYCEncounters`, `DA_NYCEconomy`, each `DA_NYC_*`, `MI_Brute_Alpha`, `FF_*`, `BT_AFSZombie`/`BB_AFSZombie`, the perk/vest DAs and `L_NYC_Survival`. Alternatively, a second label goes in `/Game/HoverPrototype/Cook/`, which `DefaultGame.ini` L41 already scans.

### M2: spawn director and crowd AI

The inline gate (`HoverCyberCity.cpp` L283-324) becomes `virtual AZE_ZombieSpawnPoint *ChooseSpawner(...)`, shared by Cyber City and NYC.

```cpp
struct FHoverSpawnerState   // namespace scope, not reflected
{
    TWeakObjectPtr<AZE_ZombieSpawnPoint> Point;
    FName Zone;
    float LastUsed = -60.f;
    int32 Uses = 0;
};

UCLASS()
class HOVERFLIGHT_API UHoverSpawnDirector : public UActorComponent
{
    GENERATED_BODY()
  public:
    AZE_ZombieSpawnPoint *Pick(APawn *Player, const FVector &Eye, const FRotator &View);
    AZE_ZombieSpawnPoint *ForceFarthest(APawn *Player);   // boss spawn: enable only this, reset interval
    void NoteSpawn(AZE_ZombieSpawnPoint *Point, const FVector &Where);
    void UpdateLive(APawn *Player);   // 0.5 s: live count, last-3 sprint, 10 s promotion, stragglers
    TArray<FHoverSpawnerState> Spawners;
    TSet<FName> OpenZones;            // M6 writes; empty = every spawner eligible
    float LastPickTime = 0.f;         // stall guard: after 4 s relax only the forward cone
    int32 PacksRemaining = 0;         // horde rounds: packs of 4 from one rotating entrance
    int32 LiveCount = 0;
};
```

`Pick` keeps the 1,400-10,000 cm band and the reachability cache (L155-182). It checks visibility with `LineTraceTestByObjectType(ECC_WorldStatic)` at ground +60 and +170, so zombie bodies no longer block the test. It applies 300 cm occupancy, ignoring zombies younger than 1 s, and scores candidates by age + distance from the last spawn + a penalty for repeats within 5 spawns. The stall guard keeps `Super::Tick` running (L328-329) and relaxes only the cone. `GetEffectiveSpawnRate` returns 2.0 x 0.95^(r-1) (floor 0.5), or 0.65 x 0.95^(r-1) (floor 0.35) on horde rounds. Three modifiers apply on top: 2 spawns per interval while `LiveCount < 8`, a doubled interval while a boss lives, and a 3 s delay after a Nuke. The 0.1 s mode tick is required, because the vendor spawns at most one zombie per tick.

```cpp
UCLASS()
class HOVERFLIGHT_API UHoverAttackSlotSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
  public:
    FVector ClaimSlot(AHoverCyberZombie *Zombie, const APawn *Target);  // 8 at 120 cm + 8 at 260 cm, yaw-relative
    void ReleaseSlot(AHoverCyberZombie *Zombie);
    bool TryAcquireAttackToken(AHoverCyberZombie *Zombie);              // 3 simultaneous (5 on horde rounds)
    void ReleaseAttackToken(AHoverCyberZombie *Zombie);
};
```

**Owned behaviour tree.** The vendor `BT_Zombie` does `MoveTo(TargetEnemy)` with a 5 cm acceptance radius and paces attacks with a literal `BTTask_Wait`. It never reads `Key_LastKnownLocation` or `Key_AttackCooldown`, so writing those keys does nothing. M2 authors `BT_AFSZombie`/`BB_AFSZombie` (keys `AttackSlotLocation` and `AttackCadence`), used only by the AFS/NYC definitions. `/Game/ZESP` `BT_Zombie` is never edited. `HoverBTTasks` adds two tasks:
- `UHoverBTTask_MoveToSlot : UBTTask_MoveTo`: the constructor sets `bObserveBlackboardValue = true` and `AcceptableRadius = 40`.
- `UHoverBTTask_ZombieAttack`: wraps `ZE_BTTask_ZombieAttack`, calling `TryAcquireAttackToken` before Super and releasing the token on finish or abort.

A blackboard-keyed Wait reads `AttackCadence` (cooldown + 0-0.4 s per-instance jitter). `AHoverCyberZombieAI::Tick` (L347-349) writes `ClaimSlot()` into the slot key, offset laterally ±150 cm every 1.5 s beyond 8 m (zig-zag). `OnPossess` (L250-254) raises separation from 3 to 10 (20 for a Brute) with a 0.7-1.3 per-instance multiplier, and raises the query range from 500 to 800 (the diagnosis recommends 700-900). `AHoverCyberZombie::BeginPlay` (L463-464) scales yaw rate and acceleration by 0.8-1.2. The AI class is shared with Lakeside, so M2 also runs a Lakeside wave verify.

### M3-M6 anchors

| Item | Where | Note |
|---|---|---|
| Health R1-30 | `DA_NYCWaves.CustomWaves[r]`: `BaseZombieCount N(r)`, `HealthMultiplier H(r)/100`, `DamageMultiplier 1.0/1.667`, `SpeedMultiplier 1.0`, intermission 10; `Auto*ScalePerWave 1.0`, `bUseCustomWaves true` | `ZE_WaveGameModeSettings.cpp` L43-56 |
| R31+ fallback | with no row, L12-28/L43-60 return 1.0 for health/damage/speed and `BaseZombieCount` for count (code-verified). `ConfigureWave` sets `Count = GetRoundQuota(r)` (or `GetHordeCount`), the frozen scale supplies health, and `GetZombieDamageScale` gives 2.5 | spine's "unverified" wording is outdated |
| Damage band | `AHoverPilot::TakeDamage` L1652-1659 uses `Mode->GetZombieDamageScale(Round, Causer)`: 1.0 for R1-10, 1.667 for R11-30, 2.5 for R31+, applied to every role's DA `MeleeDamage` | Cyber City keeps the DA path |
| Frozen scale | `AHoverCyberZombie::InitializeZombieStats` (L421-429, which runs inside vendor BeginPlay at `ZE_ZombieCharacter.cpp` L62) stores `FrozenHealthScale = GetRoundHealth(wave)/100` and rolls `SpeedTier`, without multiplying. The AI Tick rewrite (L370-395) stays authoritative: `Stats.MaxHealth * FrozenHealthScale * Tuning.Health` and `SpeedTier * Tuning.Speed`. That rewrite overrides the vendor 0.1 s `ApplyDifficultyToZombie` timer (`ZE_ZombieWaveGameMode.cpp` L570-609), which would otherwise give (H/100)^2 | `frozen_health` check |
| Speed roll | `Tier = (r == 1) ? Walker : roll(rand[4r, 4r+35])`, 180/400/600 capped by `MaximumRunSpeed`; `UpdateLive` forces the last 3 alive to sprint after R3 and promotes one Walker/Runner beyond 25 m every 10 s | Kid 700, Brute 260, Alpha 300 |
| Cadence | `UHoverNYCEncounterSettings` adds `BruteDebutWave 8`, `BossRounds {13,19,27}`, `BossInterval 6`, `AlphaBrute` and `KidBleedInFromRound 21`. NYC `ConfigureWave`/`SelectZombieData` skip Super's swarm/brute branches and use the mode's predicates, so the literal 11 (`HoverCyberVariants.h` L72) and clamp 24 (`HoverCyberCity.cpp` L116) never apply. Brutes spawn at 25/50/75/90% of the quota | Cyber City unchanged |
| Boss spawn | `ConfigureWave` adds 1 (R13, R19) or 2 (R27), and one of the 24 slots is reserved. At 40% dead, `ForceFarthest()` enables only the farthest entrance and resets the interval, giving roar, shake and banner. At R27 the second boss is gated on the first's HP <= 50% | `boss_spawn_latency` |
| Kill points | `AHoverCyberZombie::TakeDamage` resolves the bone and causer before Super (L559-566) and pays at L587-588 instead of `RandRange` | Role from `UHoverCyberZombieDefinition::Role` (Alpha = `DA_NYC_AlphaBrute`): 90/115 head, Kid 90, Brute 250, boss 500; an `AHoverMeleeWeapon` causer pays 105; a Nuke kill (L641) pays 0 and the Nuke pays +400 flat; 0 while on the board |
| Stations, prices | `AHoverArmoryStation : AZE_WallBuyActor` overrides `Interact_/GetInteractText_Implementation` (`ZE_WallBuyActor.h` L37-45) with tier refill prices 250/750/1,500/3,000. `AHoverPackAPunchStation` swaps `_2/_3/_4` via `AddItemDefinition` + `AssignInstanceToQuickbar` (`HoverCombatBridge.cpp` L274-275), copies `SavedMagazines` (`.h` L83), refills for free and needs Power. Constants live in `DA_NYCEconomy` (PaP 5k/15k/30k, perks 2,500 + 500n, vests 4,000/10,000, plates 50, doors 750-2,000, self-revive 1,500) | perks are `bUnique` items (`ZE_ItemDefinition.h` L114) |
| Perk effects | Jugg: `Survival->SetMaxHealth(250)` in the bridge on acquire. Quick Revive: `RegenDelay` 3 s, +1 revive cap. Speed Cola: rifle-instance reload/plate scale 0.7. Deadshot: x3 head at runtime in zombie TakeDamage. Double Tap: rifle-instance fire interval / 1.2. Stamin-Up: sprint 1,050, walk 560, 4 grenades, knockdown 1.4 s | shared weapon DAs never mutated |
| Starting gear | `ConfigureCityStartingGear` gate (`HoverAuthoring.cpp` L79) extended to `/Game/HoverPrototype/NYC/`; `DA_NYCWaves` gets `AmmoQuantity 270`, `GrenadeCount 2`, `StartingGold 500`, dumped to Evidence | Cyber City keeps 120/0 |
| Plates | after the band multiply (L1652-1659) and before the SandboxHealth write (L1663), 50% of each hit goes to `PlatePool` (`ZE_HealthTrigger.cpp` L318-324 formula) | vest tier = max plates |
| Regen, downed | Regen: 6 s (3 s with QR) delay, then 40 HP/s. At 0 HP: a 3 s `PlayAction` pose (`HoverLocomotionBridge.h` L23), during which `AHoverCyberZombieAI::Tick` L343-349 skips `SetTargetEnemy` (pose + 2 s grace). With a Self-Revive (1 free, max 3, 4 with QR): stand at 50% MaxHealth with 0 plates and lose the newest perk. Without one: 2 s slow-motion, then `ProcessEvent(FindFunction("OnPlayerHealthChanged"), {0, Max})`, which sets GameOver, stops the zombies and binds the widget buttons in `HandleGameOver` (`ZE_ZombieWaveGameMode.cpp` L68-136) | never bound to the delegate, which would fire before the self-revive check |
| Power-ups | `AHoverCyberPowerUp::OnOverlapBegin` (L627-654): new `MaxHealth` branch (heal + plates to the vest tier); Nuke deals 25% max to Brutes/bosses; Insta-Kill (L564-566) kills Standard/Kid, x4 on Brutes, x2 on bosses, 30 s. Drop rule in the mode: 2,000 x 1.14, 3%, max 4 per round, none in the first 10 kills, 15 s + 11 s blink | guaranteed: Max Ammo at the feet on the last horde Kid and on boss death; Brute drops alternate Ammo/Health; `Danger` removed |
| Zones/doors | `UHoverZoneGraph` feeds `Director->OpenZones`. `AHoverZoneDoor : AZE_InteractableBase` removes only OWNED blockers in `L_NYC_Survival`'s persistent level and plays `SW_Door`. Vendor barbed wire is hidden at runtime only, never saved, with dynamic nav. Spawners carry `SpawnTags {pool zone}` (`ZE_ZombieSpawnPoint.h` L41-42) + `AFS_NYCSpawn` and sit behind closed doors/barricades, 14 m or more from the zone's test points; the Plaza pool uses South/North street segments beyond Doors 1-2 | `ReviewNYCSpawns.py` gates wave runs; Power defend 25 s at interval x0.5 |

Content folders:
- Definitions: `/Game/HoverPrototype/ZombieEngine/Variants/NYC/` (inside the gates at `HoverAuthoring.cpp` L140/L173).
- Mode assets: `/Game/HoverPrototype/NYC/`.
- BT: `/Game/HoverPrototype/ZombieEngine/AI/`.
- Effects: `/Game/HoverPrototype/Effects/`.
- Maps: `/Game/HoverPrototype/Maps/`.

Vendor folders are only referenced, never edited.

### Performance mitigations

| Risk | Mitigation | Check |
|---|---|---|
| 24 concurrent + 70-Kid hordes | 20 m URO budget (`HoverCyberCity.cpp` L357-363), AI `TickInterval .5` (L231), crowd quality High inside 30 m; `ConfigureCreatureLODs` on the meshes' `/Optimized/` copies under `Variants/` (the L1020-1022 gate needs that path and 4+ LODs), created if missing; cap K(r) at 48 if median > 33 ms | `frame_ms_p50/p95` per round |
| Nav tile / crowd warnings | fixed tile pool, dynamic generation (L234-238), one bounds volume, one agent profile (radius 45, height 210) | log scan |
| VRAM 12-14 GB held elsewhere | NullRHI logic runs; `-RenderOffscreen` only for evidence, never concurrent (AGENTS.md L37) | RESULTS.json run labels |
| MaxConcurrent forced to 16 | keep the count table, lower the interval floors | documented in CONTROLS |

### Verification

`Scripts/VerifyNYCSurvival.py` copies the patterns of `VerifyCyberWaves.py` (slate post-tick, `start_playtest`, `isolate_test_input`, `test_key`, 1 Hz rows) and `VerifyNYCExploration.py` (event table, `OUT` under `D:/AFS_Comparisons`). It runs in two passes:
- R1-R10 at `Tuning.Count 1.0`, with an auto-aim kill loop and a scripted spend path.
- An accelerated pass to R32 at `Tuning.Count .25`, with `Tuning.Health 1.0` asserted. The table checks read the ConfigureWave/CustomWaves output before Tuning.

`WITH_EDITOR` test hooks `Test_SetPaPTier`, `Test_SpawnStandard` and `Test_SetRound` force states that an aim loop cannot reach. Each row records:
- `round, quota, live, zombies[{role, tier, health, max_health, speed, distance, slot, attacking}]`
- `spawn_events[{spawner, zone, distance, pack, boss}]`, `relocations`, `nearest_neighbour_cm`
- `ttk_samples, shots, hits, hit_marks, fire_shakes, rumble_requests, aim_samples`
- `points, spend_log, plates, hp, downed_events, drops`
- `frame_ms`

`AssessNYCSurvival.py` adds `spawns/review.json` from `ReviewNYCSpawns.py`, a `ReviewCyberSpawns.py` clone using tag `AFS_NYCSpawn` and `find_complete_city_path`.

| Check | Threshold | Complaint |
|---|---|---|
| `no_spawn_gap` | gap <= 6 s while quota remains and live < 24 | stall then burst |
| `spawner_spread` | non-horde: every 5 consecutive spawns use >= 3 spawners, max share <= 40%; horde: consecutive packs differ, every 3 packs use >= 3 entrances; boss spawns excluded | bunched spawns |
| `all_entrances_connected` | each zone pool keeps >= 3 spawners with a complete path 14-100 m from the zone's test points; runs before any wave test | deadlock |
| `contact_spacing` | median nearest-neighbour >= 90 cm within 300 cm of the player; attackers <= 3 (5 on horde rounds) | bunching |
| `no_stragglers` | no zombie > 60 m or pathless for > 25 s; each relocation logged with before/after distance | wave cannot end |
| `health_table`, `count_table` | R1-30 equal the spine arrays (100..3500, 6..105); R31 4,300 HP, count 110 | rounds |
| `frozen_health` | `max_health == H(r) x Tuning.Health` at 1 s and 5 s after spawn and across a round boundary | double scaling |
| `damage_band` | measured hits 30 (R1-10), 50 (R11-30), 75 (R31-32); Brute 60/100/150 | rounds |
| `speed_tiers` | R1 100% walkers (exact), R9 0% walkers, R18 100% sprinters (tolerance 1); last 3 alive sprint after R3 | readability |
| `ttk_band` | standards at R8 PaP 0 (8/4), R14 PaP I (8/4), R19 PaP II (7/4), R24 PaP III (7/4), ±1 shot, tier forced by hook | gun feel |
| `fire_feedback` | `hit_marks == hits`, `rumble_requests >= shots`, `fire_shakes == shots` | gun feel |
| `aim_convergence` | third-person impact within 30 cm of the camera aim point at 5-40 m; no self-occlusion within 150 cm | gun feel |
| `boss_spawn_latency` | boss <= 5 s after the 40% trigger; R27 second boss only after the first is at <= 50% HP | bosses |
| `guaranteed_drops` | Max Ammo on every horde clear and boss death; Brute drops alternate Ammo/Health | economy |
| `downed_flow` | 3 s pose, no zombie targets Vexa for 5 s; self-revive gives 75 HP, 0 plates, newest perk lost; without one, vendor GameOver is entered and the buttons respond; `bInvincible` stays false after a menu Apply | downed |
| `economy_floor` | at the 25% headshot mix the spend path reaches PaP I by end R8, PaP II by end R16, PaP III by end R24 (needs M6 Power) | economy |
| `exploration_untouched` | `VerifyNYCExploration.py` passes; the index-3 sample shows zero enemies | owner rule |
| `no_bike`, `truck_parked` | `get_test_bike() is None`; truck present, and `TryEnterBike` returns false beside it | vehicles |

Rendered owner checklist (not automated): third-person clearance at the barricades, fire shake and muzzle light at night, flinch, gib and ragdoll, horde readability at 30 m, stomp telegraph, door removal and banner, downed pose and death summary, HUD plates and regen.

Evidence goes to `D:/AFS_Comparisons/NYCSurvival_<date>/{Before,After,Evidence,Reproduce}`:
- `before_manifest.json`/`after_manifest.json` (`{utc, baseline, files:{path:sha256}}`).
- `licensed_patch_files`.
- `RESULTS.json` with per-report SHA256.
- `Reproduce/*.cmd` lines.

Failed runs stay labelled in `Evidence/` and are never counted.

**Docs and owner amendments.** Add `Docs/NYC_SURVIVAL_<date>.txt` with sections SCOPE, ROUNDS, COMBAT, ECONOMY, ZONES, VALIDATION and ROLLBACK, pairing each claim with what is not verified, and whitelist it in `.gitignore` after L31. The owner must amend:
- AGENTS.md L26-28: index 4 `NYC - Survival` is the only NYC entry that spawns zombies or waves, and it never spawns the bike; index 3 is unchanged.
- README.md L167-173 and the `?game=` option.
- `Docs/CONTROLS.txt`: economy rows, reserve 270, the R31+ endurance note.
- The index-4 lines in HoverTestController and HoverGraphicsMenu.
- The `PAL_AFS_Runtime` explicit assets.
- `Scripts/VerifyNYCTravel.py`: its DPad-Left wrap now lands on index 4, so it must press Left twice and assert `L_NYC_Explore` + `HoverExplorationGameMode`, plus gain a separate survival leg.
- `VerifyNYCSurvival.py`, added beside the unchanged `VerifyNYCExploration.py`.
- The `ZE_WeaponBase` deviation.

### Rollback

Each milestone reverts independently from its `Before/` folder:
1. Restore the listed owned files and plugin files by manifest hash.
2. Rebuild with `Scripts/Build.ps1`.
3. Delete `/Game/HoverPrototype/NYC/`, `Variants/NYC/`, the AFS BT/BB and `Maps/L_NYC_Survival`. Vendor sublevels, vendor barricades and `L_NYC_Explore` are untouched.
4. Restore `PAL_AFS_Runtime` and `GameUserSettings.ini`.
5. Remove the `.gitignore` line and the Docs file.

M0 and M2 revert Cyber City on their own, and the Ballista tiers return to their dumped pre-edit values. Restore selected files only and never overwrite later owner work wholesale, as `OWNER_BUGS_20261025` L106 requires.

## Open questions for the owner

- (Mode framework, level entry, third-person camera, navigation) Lock F5 in NYC - Survival (third person only) or keep the FPS toggle available as a review aid? The design locks it so aim, strafe and HUD are authored for one camera.
- (Mode framework, level entry, third-person camera, navigation) Should the Doomsday truck be absent entirely in Stage 1 instead of parked-and-unmountable? Parked keeps the Stage 2 exfil set piece in place but is one more owned actor that can block a spawner path.
- (Mode framework, level entry, third-person camera, navigation) Map location: /Game/HoverPrototype/Maps/L_NYC_Survival (next to L_NYC_Explore) versus a new /Game/HoverPrototype/NYC folder holding map and data assets together; the design splits map (Maps) and data (NYC).
- (Mode framework, level entry, third-person camera, navigation) Confirm the AGENTS.md amendment wording before any code lands: the current L26-28 rule binds NYC to HoverExplorationGameMode and no zombies, so the survival entry is blocked until the owner adds the index-4 clause.
- (Mode framework, level entry, third-person camera, navigation) Accept DynamicModifiersOnly navmesh (door actors as nav modifiers, baked tiles saved in the owned map) or require fully Dynamic generation like Cyber City? Dynamic costs runtime rebuilds across the whole 2400 x 5400 volume on every door opening.
- (Mode framework, level entry, third-person camera, navigation) Single nav agent (radius 40, height 190) for Stage 1 means Brutes (radius 48) may clip corners in alleys; accept, or pay for a second agent profile now?
- (Mode framework, level entry, third-person camera, navigation) Is the exploration menu travel script allowed to change (two left taps) now that a fifth level exists, or should NYC - Survival be inserted so that the wrap order keeps NYC - Exploration adjacent to Post-apocalypse (would renumber indices and touch the same table)?
- (Rounds, scaling and the spawn director) Should the spawn director also replace the Cyber City / Lakeside per-frame loop in the same pass (owner said those maps' spawning is bad), or stay NYC-only until validated? The design defaults to NYC-only with an opt-in flag.
- (Rounds, scaling and the spawn director) Is the one-function vendor patch NotifyZombieRemoved in ZE_ZombieWaveGameMode.h/.cpp acceptable (the pair is already among the 14 patched files)? Without it, re-queued stragglers cannot keep wave counts honest.
- (Rounds, scaling and the spawn director) May the vendor game-mode tick run at 0.1 s in NYC (needed for the 0.35 s horde floor) given the extra scoring cost, or should hordes accept 0.5 s quantisation?
- (Rounds, scaling and the spawn director) Zone membership is encoded in AZE_ZombieSpawnPoint.SpawnTags as 'Zone.<Name>'; confirm this is preferred over a separate zone volume lookup from section 07.
- (Rounds, scaling and the spawn director) BO7 proxies: the 20-60 m preferred band and the 4 s / 12 s stall thresholds are tuning guesses, not benchmark values; confirm they may be tuned during the level pass without a doc amendment.
- (Zombie roster, behaviour and crowd AI) Is a 15th patched plugin file acceptable in Stage 2 for the ObjectInitializer-based crowd component (AZE_ZombieAIController ctor signature), or should the hardened hot-swap remain permanent?
- (Zombie roster, behaviour and crowd AI) Are generic ZombieMale_AAB body parts acceptable as detached gibs on the Standard0x skins (grey zombie flesh, not skin-matched), or should gore stop at HideBoneByName + blood?
- (Zombie roster, behaviour and crowd AI) May Etherion ZombieV2/Monster/Entity sound cues be assigned to non-Etherion meshes under the pack licence (ASSET_AUDIT_REPAIRS notes no vocal set was established)?
- (Zombie roster, behaviour and crowd AI) The [/Script/AIModule.CrowdManager] ini section is project-wide and will change Cyber City and Lakeside crowd behaviour; is that acceptable, or should those maps be re-verified and the section be considered a shared improvement?
- (Zombie roster, behaviour and crowd AI) Leg-loss crawlers reuse AM_Attack_01 while prone in Stage 1; is that visual acceptable until a crawl attack is authored?
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) Hitscan Range is not in the numeric spine; this section proposes 15000 cm on all tiers. Confirm, or state the value the Ballista DAs currently carry.
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) The Etherion pack sounds (/Game/Zombie/Sound/SC_Hit, S_Entity_Hit_*) are proposed as the flesh-impact and interim kill-sting cues; ASSET_AUDIT_REPAIRS notes no vocal set was ever established from this pack. Is reuse under its licence acceptable, or should flesh/hit-confirm/kill sounds be imported fresh?
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) Should the survival mode's third-person review camera receive the full fire camera shake and recoil, or a 0.8x scale? The spine says third-person, and the same control rotation drives both cameras.
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) Is a native UHoverFireShake class acceptable as the FireCameraShake value on the five DAs, or do you prefer a Blueprint child (BP_HoverFireShake) so artists can tune it without a rebuild?
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) PaP-tier tracers reference /Game/ArrowTrail and /Game/Sci_Fi_Weapons_VFX_AIO directly rather than copies under HoverPrototype/Effects (HoverAuthoring effect helpers only accept that path). Confirm the cook roots (PAL_AFS_Runtime) may include those pack folders, or that copies should be made.
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) Headshot kills are proposed to skip the AM_Death montage (instant ragdoll + head hide + impulse). Confirm this is acceptable for the Cyber/Lakeside rosters too, since the hook is shared.
- (Gunplay, weapon VFX, haptics and hit feedback overhaul) Hit-confirm, headshot, kill-sting, bolt-clack and concrete-impact sounds must be imported (none exist). Who supplies them, and should they go under /Game/HoverPrototype/Audio?
- (Points economy, armory, Pack-a-Punch and armor upgrades) Perks as inventory items (spine) vs a plain bitmask on the bridge: items show in WBP_Inventory but can be dragged out of the grid (DiscardBehavior Destroy makes the loss permanent); accept that, or prefer the bitmask with no inventory presence?
- (Points economy, armory, Pack-a-Punch and armor upgrades) Where does the visible Ballista mesh live on Vexa (component name in HoverPilot/BP_Vexa_CLS_Parkour) so the per-tier PaP tint can be a material parameter on it?
- (Points economy, armory, Pack-a-Punch and armor upgrades) Is lowering UZE_InventorySettings::MaxWeight to 0 (disables the weight gate project-wide, Cyber City included) acceptable if DA_AMMO_M16 carries non-zero Weight, or should the ammo DA be duplicated with Weight 0 for NYC?
- (Points economy, armory, Pack-a-Punch and armor upgrades) Plate insert key: G / D-pad Right is free on the current CONTROLS map as far as the docs show; confirm it does not collide with a CLS/Parkour binding.
- (Points economy, armory, Pack-a-Punch and armor upgrades) Should the R27 double-boss pay 1,000 as two separate 500 awards (two popups) or one combined popup?
- (Points economy, armory, Pack-a-Punch and armor upgrades) Confirm DA_AFS_Ballista_5 may be re-authored as the Stage 2 Heavy Ballista base (it is currently documented as a Ballista tier and sold at a Cyber City crate).
- (Tactical equipment, player survival, downed state and power-ups) Molotov, Stun flare and Noisemaker (Stage 2) add prices and effects that are not in the spine's income model (frag 250, stim 500, noisemaker 500 are); confirm the molotov 500 / stun 300 prices and the 0.3 x H(r)/s burn and 4 s stun figures, or cut them.
- (Tactical equipment, player survival, downed state and power-ups) Downed state: the spine fixes a 3.0 s pose with no crawl and no bleed-out; the task brief floated a crawl/sidearm/30-45 s last stand, which the existing QA_OwnerCrawlLoop and QA_StompKnockdown clips could support in Stage 2. Keep the spine, or schedule the last stand?
- (Tactical equipment, player survival, downed state and power-ups) Stamina: ship unlimited sprint (BO7 parity, spine math) with only the Shift binding added, or enable the dormant UZE_SurvivalComponent drain (10/s, regen 20/s, 15 minimum) now?
- (Tactical equipment, player survival, downed state and power-ups) Stage 2 power-up enum: AFS-side EHoverBonusPowerUp on AHoverCyberPowerUp (no plugin touch, recommended) or the 15th plugin patch adding DoublePoints/BonusPoints to EZE_PowerUpType as the spine wrote it?
- (Tactical equipment, player survival, downed state and power-ups) Hoverboard in survival: accept 'allowed, no points, takes damage, slowed by adjacent zombies, knocked off on a >= 50 hit or stomp', or disable the board entirely in L_NYC_Survival?
- (Tactical equipment, player survival, downed state and power-ups) Gamepad bindings for quick-throw (R1 on foot) and stim (hold Y) are proposals; the D-pad is fully used (Up menu, Down inventory, Left quickbar cycle, Right CLS toggle). Confirm, or free D-pad Right in survival mode for the stim.
- (Tactical equipment, player survival, downed state and power-ups) The ZESP throw clip As_Grenade_Throw_Anim is on the ZESP skeleton; if the CLS driver retarget rejects it, the fallback is the existing QA_Melee swing as the throw pose. Acceptable?
- (Tactical equipment, player survival, downed state and power-ups) WBP_ZE_DeathRespawn is a binary vendor widget: the design reuses its buttons and draws the round/kills/points summary with AHoverHUD over it. Prefer a new owned WBP_NYC_GameOver instead?
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Zone extents for Shelter (x 600-1,100) and Garage (x -400..100) assume side streets or building shells exist east and west of the main corridor at those y ranges; if the survey finds only facade geometry, both become alcoves off North Avenue and the 7-zone graph collapses to 5 corridor zones plus two rooms - is that acceptable?
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) May the survey/authoring pass add a NavMeshBoundsVolume covering the whole x -500..1,100 / y 2,800..7,400 block (nav build cost and tile count on the procedural buildings are unbenchmarked), or should navigation be limited to the main corridor plus the two side rooms?
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Jump pad Garage -> Plaza is specified as free after Power (BO7 charges ~500); should it cost points, and should it also work in reverse?
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Exfil is cut from Stage 1 and the phone booth is placed as dressing; confirm the cut, or require the booth + HVT flow in Stage 1 at the cost of the truck set piece
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Doors use owned copies of vendor barricade/gate meshes placed next to the untouched SetDressing walls; if a vendor wall already sits exactly in a required gap, the only options are to route the door around it or to hide that one vendor actor at runtime (SetActorHiddenInGame on a vendor-sublevel actor, no asset edit) - is runtime hiding of a vendor-placed actor acceptable under the preserve-vendor-content rule?
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Adding IsSpawnerEligible()/RelaxVisibilityGate() virtuals to AHoverCyberCityGameMode touches the shared Cyber/Lakeside adapter (default behaviour unchanged); confirm that owned-class edit is preferred over duplicating the Tick loop in the NYC subclass
- (NYC zone graph, doors, power, Pack-a-Punch placement and spawner layout) Stage 2 Underpass ground emergers need the ZombieAnimationPack Burst clips retargeted to the Standard01-04 skeleton; should the Underpass spawners be authored with the second 'Emerger' tag now so no re-placement is needed later?
- (HUD, UI and audio feedback) Is the Etherion Content/Zombie/Sound bank acceptable as the vocal set for the Cyber-derived NYC roster, Brute and Alpha Brute (ASSET_AUDIT_REPAIRS:63-64 noted no creature vocal set was established), or should a separate zombie VO pack be supplied?
- (HUD, UI and audio feedback) No owned UI sound set (hit tick, purchase chime, denied buzz, round stinger) exists; the design uses pitched hit/switch cues as placeholders. Will the owner supply a UI SFX pack, or accept the placeholders?
- (HUD, UI and audio feedback) Rebinding D-pad Right from the CLS/original-locomotion compare toggle to armor-plate insert (keyboard F7 keeps the compare) applies only in the survival mode; is that acceptable, or should the plate use a different button?
- (HUD, UI and audio feedback) Should the game-over screen offer only 'restart from round 1' (spine) or also 'return to test settings' (B/Esc), given level travel discards the session?
- (HUD, UI and audio feedback) HUD scaling: both surfaces use fixed pixel font sizes; is 1080p/1440p the acceptance resolution, or does the owner need a DPI-scale pass for 4K/ultrawide in this stage?
- (HUD, UI and audio feedback) Should world-space damage numbers (vendor WBP_DamageNumber) stay on in survival alongside the new hit/kill markers and point popups, or be disabled to reduce clutter at 24 concurrent zombies?
- (Implementation plan, milestones and verification) Straggler rule resolved for Stage 1 (owner, 2026-11-03): relocate the same actor, restore full health on success and keep its round accounting.
- (Implementation plan, milestones and verification) May M0's recoil and spread-recovery fixes be made in the already-patched ZE_WeaponBase.cpp (two small edits, hashes recorded), or should recoil be reimplemented AFS-side in AHoverPilot::FireShot and the vendor recoil zeroed in the DAs?
- (Implementation plan, milestones and verification) Third-person survival camera: is a 300 cm right-shoulder profile acceptable as the mode default (review camera today is a 430 cm centred spring arm), given the owner must approve it rendered?
- (Implementation plan, milestones and verification) Flinch while attacking: edit the 0.8 s / !bIsAttacking rule in the patched ZE_ZombieCharacter.cpp, or drive flinch purely from AHoverCyberZombie::TakeDamage via the locomotion bridge and leave the vendor rule alone?
- (Implementation plan, milestones and verification) Level entry: is a Blueprint child BP_NYCSurvival (mirroring BP_CyberWaves) acceptable as the World Settings override and ?game= target, or should the C++ class be used directly in the ?game= string?
- (Implementation plan, milestones and verification) Doors remove owned BP_T_Wall_Double_a_BarbedWire pairs placed in L_NYC_Survival; confirm the vendor SetDressing copies stay untouched and the survival map gets its own duplicates for the six gates.
- (Implementation plan, milestones and verification) Evidence runs: the full R1-30 acceptance run needs roughly 25-35 minutes of accelerated offscreen play; confirm this can be scheduled without the other game occupying VRAM, or accept NullRHI-only for the table checks and a shorter rendered R1-10 pass.
- (Implementation plan, milestones and verification) If frame time forces MaxConcurrentZombies 16 on the NYC city, confirm the agreed fallback (keep count table, lower spawn-interval floors, ~30% longer rounds) rather than cutting the count table.
- (Implementation plan, milestones and verification) Stage 2 power-up enum additions (Double Points, Bonus Points) add ZE_PowerUpPickup.h as a 15th patched plugin file; confirm that is acceptable before Stage 2 is scheduled.
- (Roster asset mapping) Which mesh do the GUID-named maps '0e26c14a-11c1-4c0f-893b-06a2de061c8f (1)_Material_{BaseColor,Normal,OcclusionRoughnessMetallic}.png' belong to? The GUID naming matches Tripo material names seen in Lakeside (Horror/tripo_mat_<guid>), so they may be a Kid or Lakeside body re-texture rather than the golem; they are held at source until confirmed.
- (Roster asset mapping) Which Substance Painter export preset produced the Oct 29 set (Unreal/DirectX normals vs generic OpenGL)? This decides whether the Normal maps need Flip Green on import.
- (Roster asset mapping) Boss rounds 20/30/40 now coincide with horde rounds (every 5 from R5). Should the boss round be a 'horde + boss' round, move to 18/28/38, or should the boss spawner suppress the swarm on its round?
- (Roster asset mapping) Confirm in the viewport which of attack1-5 read acceptably unarmed; the proposal (keep attack3, attack2, attack5; attack1/attack4 conditional) is based on clip lengths and curve data only, since poses cannot be decoded from the name tables.
- (Roster asset mapping) Golem Height 320 / CapsuleRadius 70 and Giant Kid Height 320 / CapsuleRadius 60 are proposals; the golem mesh bounds were not measured (BP_StoneGolem's demo capsule is 90/35), and the DA Height overrides the native scale either way.
- (Roster asset mapping) Giant Kid HP 1500, golem HP 2400 and the gold ranges are placeholders pending the NYC round tuning; Role 'Boss' needs the EHoverZombieRole enum extended (code).
- (Roster asset mapping) Should the Kid crawler keep the standing anim_Burst emergence (which ends upright) or spawn directly in the crawl idle (anim_Laying_Idle_A/B)?
- (Roster asset mapping) Etherion cue usage still needs sign-off given the is_ai_forbidden=1 listing flag and the audit's deliberate silence.
