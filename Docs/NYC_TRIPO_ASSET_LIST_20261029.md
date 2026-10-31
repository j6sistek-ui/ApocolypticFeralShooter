# NYC Survival: assets to generate in Tripo (2026-10-29)

Companion to `NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md`. Every item below is something the design currently covers with a placeholder (a re-skinned ZESP `BP_Buy_01`, a vendor kiosk, a generator mesh) or lists as a content gap in Section 10. Guns are now covered by `SourceAssets/EM_Apocalyptic_Guns/EM_Apocalyptic_Guns-Vol 23.rar` and are not in this list.

## EM Apocalyptic Guns Vol 23: what is in it (checked 2026-10-29)

Archive moved to `M:\UnrealProjects\AFS\SourceAssets\EM_Apocalyptic_Guns\` (gitignored). It is a bundle of five inner RARs: Blender (one .blend, 450 MB), FBX (30 files, 34 MB), OBJ, HighPoly (1.2 GB) and PBR_Texture (1.6 GB). A rendered contact sheet of all 30 is beside it: `EM_Apocalyptic_Guns_contact_sheet.png`.

**Usable, with limits.**

- 30 guns, each one FBX (binary 7.7) holding **one merged static mesh with one material**. No rig, no separate magazine, bolt, slide or trigger, no sockets. So they work exactly like the current Ballista (a static mesh on `AHoverCyberRifle`): the fire feel comes from camera shake, recoil, tracer and muzzle flash, and reloads are character-side only. If you ever want a moving magazine, the parts have to be split in Blender first (the .blend is also merged, one object per gun).
- 25k-60k triangles each. Fine for a held weapon and wall-buy display; I will build LODs on import for the pickup and kiosk copies.
- Textures per gun at 2K and 4K: BaseColor, Normal, Roughness, Metallic, Emissive, Height. Same packing job as the Golem (R/M into one mask, Height unused). **Correction 2026-10-29 (survey):** 16 of the 30 Emissive maps are blank, so the Pack-a-Punch glow is a material setting, not a free channel.
- **Correction 2026-10-29 (survey, `SourceAssets/EM_Apocalyptic_Guns/em_guns_survey.json`):** the FBX headers are centimetres at 1.0 (Maya, Y-up); import at 1.0, not 2.54 (EM_13 = 120 cm, EM_21 = 34 cm at 1.0). Sizes are inconsistent across the pack (EM_02 155 cm; EM_17/18/19/20/22 only 55-76 cm) and the rig plan gives a per-gun scale factor. Rotation: EM_17 and EM_18 are turned 90 deg with hidden node scales (0.53 / 0.64), EM_26 is turned 180 deg with node scale 36.5, EM_04 stands upright; EM_09 is not rotated. Muzzle points -X for EM_13-22 and 25, +X for the rest. No gun has a loose magazine island (all one welded shell); magazines are UV islands joined at the seam, so a UV-island pick cuts them out on 10 of 13 box-mag guns. Full plan: `Docs/EM_GUNS_RIG_PLAN_20261029.md`.
- Blender file names the material of EM_11 `lambert9` (Maya export); harmless, renamed on import.

**Suggested slots for the design's armory** (my read of the contact sheet; swap freely):

| Design slot | Pick | Alternates |
|---|---|---|
| Sidearm (wall buy 500) | EM_08 snub revolver | EM_28 big revolver, EM_03 compact pistol |
| M16 slot: full-auto rifle (wall buy 1,250) | EM_11 suppressed carbine | EM_19 or EM_24 AK-pattern, EM_15 AK with scope |
| Heavy Ballista stand-in if we go bullets instead of bolts | EM_14 suppressed Dragunov-style | EM_27 scoped FAL-style, EM_20 scoped bolt-action |
| Shotgun (new wall buy, if wanted) | EM_25 heavy pump | EM_17 drum lever-shotgun, EM_06 improvised |
| SMG (new wall buy, if wanted) | EM_21 MP5-style | EM_09 compact SMG |
| Sniper (new, Stage 2) | EM_13 bolt-action | EM_18 with bipod, EM_10 improvised long |
| Flavour / improvised tier (R1 starter look) | EM_04, EM_07, EM_16 pipe guns | EM_26, EM_29 contraptions |
| Wonder-weapon flavour (was cut for lack of an asset) | EM_12 or EM_30 canister rifle | EM_26 |

The crossbow Ballista stays the signature weapon per the design; these fill the wall buys and the armory kiosk, and give the "gun armory" its wall of options.

## Modular M4A1 (showcase weapon for the advanced mechanics, checked 2026-10-29)

Moved from Downloads to `M:\UnrealProjects\AFS\SourceAssets\M4A1_Modular\` (gitignored): `UnrealFiles-5-0.zip` (unpacked beside it as `UnrealFiles\M4A1\`), `Lowpoly.fbx`, `Highpoly.fbx`, `Textures.zip`, `Freebie.zip`, plus a part render `M4A1_parts_render.png` and the part list `M4A1_parts_lowpoly.json`.

**What it is.** One AR-15 build split into 20 separately importable static meshes: upper and lower receiver, bolt carrier, charging handle, 20-inch barrel, gas block, flash hider, silencer, front rail, small rail, offset rail mount, vertical grip, pistol grip, buffer tube, stock, PMAG D60 drum magazine, prism scope, reflex sight, flashlight, laser. Every part has its own material instance under one `MAIN` master and its own BaseColor, Normal, Roughness and Metallic set (4K on the receivers, rail and scope; 2K on the rest). The Unreal assets were saved from 4.26 despite the "5-0" name; 5.8 opens and resaves them. There are no sockets, no rig and no animation in any file, and the low-poly FBX is the same 23 part groups (about 50k triangles total, 8.5k of it the rail).

**What it unlocks for the proof of concept.** Because the movers are separate meshes, the whole "advanced" feature list from Section 5 can run on the existing static-mesh weapon path (`AHoverCyberRifle`) with child mesh components, no skeleton needed yet:

- Bolt carrier and charging handle cycle on every shot (offset driven from `FireShot`), the first visible recoil mechanism on any gun in the project.
- Magazine detaches and drops as a physics prop on reload, a fresh one slides in; the drum reads as the "extended mag" PaP perk.
- Shell ejection and muzzle flash get real socket positions (ejection port on the upper receiver, muzzle at the flash hider or silencer).
- Attachment swaps as the armory / PaP visuals: silencer on or off, reflex vs prism scope, flashlight and laser as the tactical equipment toggles, and the Freebie zip's second receiver texture set as a PaP camo.

The rigged, animated version (bones per part, fire and reload clips) is the later Blender pass you mentioned; the component build above is enough to prove the mechanics and is what M0 will use. Sockets get added in the editor on the receiver and barrel meshes during import.

Priority: **P1** = Stage 1 needs it to look right, **P2** = Stage 2 feature, **P3** = nice to have. Within a tier, top to bottom is the order I would spend generations in.

## Export settings that make import painless

- FBX, Y-up is fine (the importer converts), 1 unit = 1 m in Tripo, so set the import scale to 100 or scale in Tripo to real-world size before export. Real-world heights are given per item.
- PBR textures: BaseColor, Normal, and a packed ORM (or separate Roughness and Metallic; I pack them). Source 4K like the Lakeside zombies, runtime cap 2048. Project convention: RM green = roughness, blue = metallic.
- One material slot per prop (two at most, e.g. body + emissive panel). Tripo names materials `tripo_mat_<guid>`; I rename on import.
- Pivot at the base centre for anything that stands on the ground, at the hinge edge for doors.
- Target tri counts are in each row. Tripo's quad or low-poly remesh at those counts is enough; Nanite is off for skeletal meshes, on for props.
- For characters: use Tripo's auto-rig (biped, A- or T-pose). I retarget to the ZESP `SK_Mannequin` the same way as the other 11 owner zombies (`ConfigureVariantSkeleton`), so proportions should stay roughly human. The Kid shows that extreme proportions still work, but a hunch or crawl pose should be left to animation, not baked into the mesh.

## P1: stations and props the loop needs

| # | Asset | Replaces / fills | Size | Tris | Notes |
|---|---|---|---|---|---|
| 1 | **Perk vending machine** (one body, six texture variants) | ZESP `BP_Buy_01` for Quick Revive, Juggernog, Speed Cola, Deadshot, Double Tap, Stamin-Up. **Correction 2026-10-29:** `BP_Buy_01` has no vending-machine model; its only mesh is Unreal's editor placeholder sphere, so there is nothing to re-skin and a model is required before any Painter work. **In-house base chosen 2026-10-29:** `SM_VendingMachine01` from the owner's licensed CyberPunk bar set, copied from SpaceSurvival into `Content/CyberPunkBarAssetSet01/` (mesh, `M_VendingMachine01`, 4K BaseColor/Normal/ORM/Emissive; 11 files, 163 MB, together with the second body `SM_BarVendingMAchine01`). One material and one UV layout, so the six perk variants are a Painter job: export the mesh to FBX from the editor (blocked while another editor automation run is active), open in Painter, author six BaseColor + Emissive variants, export to `SourceAssets/SubstanceExports/PerkMachines/`. A Tripo machine can still replace it later. | 190 h x 90 w x 80 d cm | 10-15k | Generate the body once, then use Tripo retexture for six colourways with a blank front panel I can put the perk logo and emissive on. Post-apoc: rust, bullet dents, one cracked glass front. |
| 2 | **Pack-a-Punch station** | `BP_Buy_01` on an `SM_AmmoBox_01a` base (Underpass, needs Power) | 200 h x 150 w x 120 d cm | 15-20k | Industrial press / forge with an open weapon cradle on top and heavy cables. Needs an emissive strip or coils so "powered" vs "unpowered" reads via material. |
| 3 | **Armor station** (vest rack) | No mesh assigned yet; two zones (vest II North Avenue, vest III Garage Block) | 180 h x 120 w x 60 d cm | 8-12k | Military locker or rack with plate carriers hanging and a stack of ceramic plates on a shelf. |
| 4 | **Shelter medic cabinet** | Shelter station (Self-Revive, Stim, Noisemaker); no mesh assigned | 170 h x 100 w x 50 d cm | 8-12k | Wall-mounted or free-standing first-aid cabinet, doors open, syringes and kits visible. |
| 5 | **Zone door A: chained chain-link gate** | Doors 1-2 (currently vendor `SM_MilitaryBase_WiredFence_Gate_Double` + lock) | 300 h x 400 w cm | 6-10k | Single mesh including chains and padlock so it can vanish or swing in one piece. Pivot on the hinge side. |
| 6 | **Zone door B: rubble and rebar pile** | Doors 3-4 (currently `SM_MetalBarrier01` x2) | 250 h x 450 w x 200 d cm | 10-15k | Collapsed concrete, rebar, a crushed car hood. Purchased = sinks into the ground. Needs a flat back face so it seals a doorway. |
| 7 | **Zone door C: boarded plywood wall with warning spray** | Doors 5-6 (currently `SM_Kiosk_Door` on `BP_Base_02`) | 280 h x 350 w x 20 d cm | 4-6k | Plywood sheets over a steel frame, "KEEP OUT" spray, a few planks already missing. |
| 8 | **Manhole with lifted lid** | Underpass ground-emerge spawners (no spawn-point dressing exists) | 90 cm diameter, lid 10 cm | 3-5k | Open ring in the asphalt plus the lid lying beside it. Rim slightly raised so the crawl-out reads. Also usable as the Kid crawler's horde entrance. |
| 9 | **Subway stair grate / sidewalk vent** | Second emerge type for horde rounds | 120 x 80 cm | 2-4k | Steel grate bent upward from below. |
| 10 | **Stim auto-injector** (pickup and hand prop) | Stim item has no mesh | 15 cm | 1-2k | Chunky military auto-injector with a glowing cartridge; also the HUD icon source. |
| 11 | **Self-Revive kit** | Self-Revive item has no mesh | 20 cm | 1-2k | Syringe clipped to a small pouch, red cross. |
| 12 | **Armor plate** (pickup) | Plates have no mesh (sold at kiosk/armor station) | 30 x 25 x 2 cm | <1k | Ceramic plate, one chipped corner. |
| 13 | **Frag grenade** | Current placeholder is `SM_Bomb`, which does not read as a frag | 10 cm | 1-2k | Standard pineapple or M67 body. |
| 14 | **Ammo cache crate** | Ammo caches reuse `SM_AmmoBox`; optional but a distinct NYC look helps | 60 h x 90 w x 50 d cm | 4-6k | Military crate with lid propped open, bolt bundles and mags visible (we fire bolts). |

## P2: Stage 2 features

| # | Asset | Fills | Size | Tris | Notes |
|---|---|---|---|---|---|
| 15 | **Power breaker panel with big lever** | Power switch currently just the generator mesh; a lever gives the interact a focal point | 150 h x 60 w x 30 d cm | 4-6k | Mounted beside `SM_Generator01`; lever down/up pose as two meshes or one with a separate lever part. |
| 16 | **Saw-barrel fire trap** | Uptown Barricade `AHoverZoneTrap` (750 points) | 120 h x 100 w x 100 d cm | 6-10k | Oil drum on its side with a spinning blade disc and burner nozzles. Blade as a separate part so it can rotate. |
| 17 | **Riot armor set for armored zombies** (helmet, chest plate, two shoulder plates, two shin guards) | Content gap: breakable plates on Pirate (light, R9) and BogZombie (heavy, R17) | Human scale | 2-3k each | Six separate meshes, each with the pivot where it attaches (head, spine_03, upperarms, calves). They get socketed to the existing skeletons and detached on break, so no rig needed. |
| 18 | **Mangler-style ranged special** (zombie with an arm cannon, biped) | Content gap: ranged special; needs projectile code, so Stage 2 | 200 cm | 25-30k | Keep the free arm and legs human so the ZESP retarget holds; the cannon arm can be oversized. Needs Tripo auto-rig. |
| 19 | **Noisemaker** | Currently `SM_WalkieTalkie`; fine as is, optional re-skin | 15 cm | 1-2k | Skip unless you want it to read as a lure (flashing beacon). |

## P3: extra roster and dressing

| # | Asset | Fills | Size | Tris | Notes |
|---|---|---|---|---|---|
| 20 | **12th standard zombie body** (NYC civilian: office worker, construction, hospital gown) | Content gap: more walker skin variety for R1+ | 180 cm | 20-25k | Only if you want more than the four Standards. Rigged in Tripo, same retarget path. |
| 21 | **Hellhound / mutated dog** | Content gap: animal horde unit. **Hold.** No quadruped animation set exists in any pack, so a model alone does nothing. The Kid crawler fills this role. | 90 cm | 15-20k | Generate only if you also have a source for quadruped run/attack clips. |
| 22 | **Perk bottle** (one mesh, six labels) | Pickup drop and HUD icon for perks | 25 cm | 1-2k | Cheap, and the machines dispensing a bottle is the BO tell. |
| 23 | **Power-up drop icons** (Max Ammo, Insta-Kill, Double Points, Nuke, Max Health) | ZESP already has power-up visuals; optional NYC re-skin only | 40 cm | 1-2k each | Lowest priority; vendor ones work. |
| 24 | **Exfil phone booth** | `SM_PhoneBooth` exists; skip | | | Listed so it is not generated by mistake. |

## NVIDIA SimReady assets as a second source (checked 2026-10-29)

`huggingface.co/datasets/nvidia/simready-assets`: 2,673 props, USD format, each in its own folder with PBR textures (albedo / normal / ORM PNGs, tiled material sets, plus MDL files Unreal ignores), CC-BY 4.0 (credit NVIDIA in the game credits), 489 GB in total but downloadable per folder. The catalogue is industrial, warehouse, automotive, hospital and food: no weapons, no apocalyptic dressing, no characters. Unreal 5.8 imports USD through the USD Importer plugin and converts to static meshes; materials get rebuilt from the PNGs. The full folder index is saved in the session scratchpad (`simready_dirs.txt`).

Folders that cover list items directly, with real download sizes:

| List item | SimReady folder | Size | Note |
|---|---|---|---|
| 1 Perk machine base | `machine_vending_snacksDrinks_a01` | 880 MB | A real snack-and-drinks vending machine; six perk variants would be Painter texture work on top. `machine_coffee_vending_a01` (353 MB) is a second body. `digitalSystem_infoKiosk_vertical_a01` (67 MB) suits an armory terminal. |
| 4 Medic cabinet | `safety_firstAidCabinet_wallMounted_a01` | 292 MB | Wall first-aid cabinet, exactly the Shelter station. `construction_firstAidPoint_trolley_a01` (865 MB) is a mobile alternative. |
| 11 Self-Revive kit | `safety_firstAidKit_pouch_tactical_a01`, `safety_firstAidKit_box_plastic_a01` | ~350 MB | Pickup meshes. |
| 15 Power breaker | `electrical_power_shutoff_a01` (1.1 GB), `warehouse_EF_electricPanel_a01` (155 MB), `safety_mobileShutoff_a01` (74 MB) | | The mobile shut-off is the cheapest lever-style switch. |
| 5 Zone door A | `barrier_fence_metal_a02` / `a03` (23 MB each), `barrier_gate_safety_a02` (30 MB), `barrier_wall_plastic_orange_a03` (47 MB) | | Fence panels and a safety gate; chains and padlock would still come from Tripo or Blender. |
| 16 Trap barrel | `drum_steel_a01` / `a02` (22 MB) | | Steel drum body for the saw trap; blade and burners still needed. |
| 14 Ammo cache | `crate_plywood_b01-b06`, `crate_green_a01`, `storage_locker_double_bench_b01`, `facilityFurniture_lockerUnit_multiDoor_a01` | small | Plywood crates and lockers; the armor station could be a locker unit. |
| Set dressing | `cabinet_drum_flammable_a02`, `ibcTank_steel_stainless_a01`, `scaffold_rolling_steel_a01`, `ladder_*`, `pallet_*`, `bin_waste_*`, `fireProtection_extinguisher_*`, `sign_warning_a04` | 20-50 MB each | NYC street and garage clutter. |

Not in SimReady: Pack-a-Punch forge, zone doors B and C (rubble, boarded wall), manhole, subway grate, stim injector, armor plate, frag, riot armor, any zombie. Those stay on the Tripo list. Realistic pull for the loop: vending machine + first-aid cabinet + mobile shut-off + two fence barriers + steel drum, about 1.4 GB.

## Perk names (owner decision 2026-10-29: no Call of Duty names)

The design doc still uses the Black Ops working names; these replace them everywhere from now on. Colours are the machine tint and the trim/label accent used by the Painter build.

| Effect (design doc slot) | Old working name | **Name** | Tint / accent |
|---|---|---|---|
| Self-revive, faster revive | Quick Revive | **Second Wind** | teal / ice blue |
| Max health | Juggernog | **Ironhide** | red / hot red |
| Reload and swap speed | Speed Cola | **Fast Lane** | green / lime |
| Aim assist, headshot damage | Deadshot | **Bullseye** | gunmetal / gold |
| Fire rate | Double Tap | **Hair Trigger** | orange / amber |
| Sprint | Stamin-Up | **Marathon** | yellow / violet |

## Perk station: owner direction (2026-10-29, later)

- **The Tripo station is the perk machine.** Six copies, each with a different **metallic tint** (body) and matching accent on the trim lines, **no names or labels** on the mesh. A perk indicator (icon, hologram or HUD prompt) comes later; the screen with the purple symbols will be custom-made later.
- **Interaction:** the player interacts with the station and the perk pickup **pops out onto the octagonal pad** at its base (the lit ring in front of the lower hatch) for the player to pick up. No vending or drink-delivery animation.
- The drink-machine build with the six names stays as a spare and as the pipeline proof.
- **Painter work parked (owner, 2026-10-29 evening):** the Tripo station is used **as-is** (purple trim, Tripo textures) as the placeholder for all six perk machines; the owner will retexture later. The station tint build script exists but its exports were never produced (the Painter remote-script hang is understood: never sleep-wait on Painter's main thread for async project creation; split create and build into two calls).

## Kid check (owner question, 2026-10-29)

Verified against `D:\AFS_Comparisons\ZombieSpecials_20261024\Prepared\Kid\SK_Kid.fbx` (the import source recorded in `SK_Kid.uasset`) and the project:

- **Bind pose is upright**, not a crawl: head 0.73, pelvis 0.40, feet 0.05 on the vertical axis, all on one vertical line; `rest.png` shows a standing A-pose and `run.png` an upright run. No shape keys, no embedded animation.
- **No Kid-specific clips exist.** `DA_Kid` plays the vendor `Zombie_001` montages and `BS_Zombie_WalkRun`; the Kid folder holds only mesh, skeleton, physics asset, materials, textures and the data asset. The crawler needs the ZAP belly-crawl clips plus a Feral lunge as the design says.
- **CLS (Custom Locomotion System, motion matching) is not applied to the Kid.** `BPC_LocomotionSystem` is referenced only by Vexa's blueprints (`BP_CLS_Vexa`, `BP_Vexa_CLS_Parkour`, `ABP_CLS_Actions`, `CHT_VexaRifle`); nothing in `Content/CLS` references the Kid or any zombie. The Kid's proportions work because `SK_Kid_Skeleton` lists the ZESP `SK_Mannequin` as a compatible skeleton (19 matching UE4-mannequin bone names), so the Zombie Engine animation blueprint drives it directly.
- **Possible simplification from CLS:** its "invisible driver / visual passenger" pattern (`CLS/Example/SetupYourHeroExample/VisualOverride/ABP_Passenger_Retarget` with a runtime IK Retargeter node) could drive the Kid, Giant Kid and Horror from one driver skeleton at runtime instead of batch-retargeting Feral and ZAP clips per body. Cost is a per-frame retarget per zombie, so it suits the one-at-a-time bosses (Giant Kid) better than the 24-strong horde crawlers; worth a test on the Giant Kid before committing to the `IK_Kid` / `RT_Feral_Kid` offline route.

Tints: Second Wind steel blue, Ironhide oxblood, Fast Lane verdigris, Bullseye brass, Hair Trigger copper, Marathon violet chrome. Exports: `SourceAssets/SubstanceExports/PerkStation/<Perk>/` (Unreal packed set, DirectX normal), project `SourceAssets/SubstanceProjects/PerkStation_Tripo.spp`, mesh `SourceAssets/PerkMachine/TripoStation_prep/PerkStation.fbx` (21,070 tris, one material `M_PerkStation`).

## Perk machine production (2026-10-29)

Three vending-machine bases are now in hand, plus the Tripo station:

- **Fab "Drink vending machine"** (`D:\FABDOWNLOADS\VaultCache\FabLibrary\Drink_vending_machine-6677109f`, FBX + 4K PBR, 1,531 tris, hand-painted grunge, DirectX normal, a blank sign plate on top). **This is the Painter base for the six perk machines.** The automated Painter build lives in the session scratchpad (`perk/prep_perk.py`, `labels.py`, `painter_build.py`, `render_variants.py`) and produces: `SourceAssets/PerkMachine/DrinkVending_prep/` (split AO/rough/metal, trim mask from the emissive, sign-plate mask, six UV-space label plates rendered rotated 180° into the sign island at UV [0.712, 0.085, 0.953, 0.187]), the Painter project `SourceAssets/SubstanceProjects/PerkMachine_DrinkVending.spp` (base layer + one group per perk), and `SourceAssets/SubstanceExports/PerkMachines/<Perk>/` with the Unreal packed set (BaseColor, Normal, OcclusionRoughnessMetallic, Emissive) per perk. Stack per perk: hue-preserving Color tint + Overlay lift on the body, perk-colour emissive on the trim lines, dark sign plate, label in BaseColor + Emissive, edge wear and dirt generators.
- **Fab "Fare Gates & Vending" (Retro Style Games, NYC Subway Realm vol. 4, free)**: one FBX with turnstile, turnstile door/entrances/rails, ticket vending, snack vending, water vending, charging station, help point, information stand, lightbox; each has its own BaseColor/Normal/MetallicRoughness/Occlusion/Emissive set. Uses: turnstiles and rails = zone-door bases (doors 1-2), ticket vending = armory kiosk, snack and water vending = extra perk bodies or set dressing, help point = Shelter station alternate, lightbox = zone signage.
- **SpaceSurvival CyberPunk bar set** `SM_VendingMachine01` / `SM_BarVendingMAchine01`, copied into `Content/CyberPunkBarAssetSet01/` (sci-fi look; kept as alternates).
- **Tripo perk station** (`SourceAssets/Tripo/PerkStation_20261029/PerkStation_tripo_21k.glb`, 21,070 tris, 4K base + packed metallic-roughness + normal; a 10,736-tri twin is beside it). Rusted sci-fi console with a screen showing health, run and shield icons and purple trim; reads as a station on its own. Use the 21k with Nanite; the 10k facets on the bevels. Unlike the drink machine it needs no label plate, so it suits the Pack-a-Punch or armor station rather than the six perk machines.

## Pack capabilities verified on disk (2026-10-29 night)

- **Blood**: NOT in ZESP. `Content/Rocket/NS1_Blood/NS_NS1_BloodShot` (Niagara hit spray) + `Rocket/Masters/Materials/MM_BloodPuddle` + `MI_NS1_Blood*` / `T_NS1_Blood*` textures. Already spawned on zombie hits by `HoverCyberCity.cpp:544` and `HoverZombie.cpp:55`. No wall decals or dismember spurts: a gore pack is optional polish.
- **ZESP (Zombie Engine Studio, RGCL V1)**: `NS_GunFire` muzzle, `NS_Explosion`, `BP_M16_FireShake`, bullet-hole decal (`M_Decal_Base`, `T_Impact_001`, per-weapon `DecalMaterial`/`DecalSize`), per-surface `ImpactEffectsMap` + `DefaultImpactEffects` on `UZE_WeaponDefinition` (plug NS1 blood in for flesh), player ragdoll, zombie death montage/ragdoll, perception AI, wave scaling, gold + wall buys, grid inventory, RGCL runtime tuning panels. No blood, gore or dismemberment. Requires the MotionTrajectory engine plugin.
- **Etherion "Zombie"**: 205 sound assets (ZombieV2 93, Monster 23, Entity 19, Zombie 16, Player 13, Gun 13, Whoosh 11, Hits 7, Footsteps 6), `SK_Zombie` with the ~45 `Morph_*` targets (face/jaw/teeth/ears/arms/body types) + `BP_Zombie_CharacterRandomizer`, materials A/Blue/Brown/Green/Ice/Lava/Skin Black/White each with a `_Fade` death-fade variant, `AnimBP_Zombie`, `BT_Zombie`, `BB_Zombie`, `BP_Zombie_AiController_Base`, `BP_ZombieSpawner`, 28 animation assets. Textures 8K: cap to 2K on import.
- **ZombieMale_AAB**: dismemberment body + motion-matching basics only.
- **Sci-Fi Weapons VFX AIO**: energy/laser/lightning systems, four `NS_Simple_Impact`, ground impacts, impact materials, blood textures only (no blood systems). Not a realistic ballistic set.

**Buy list (revised):** 1) realistic firearm SFX pack (top gap); 2) optional gore pack (wall splatter, dismember spurts); 3) optional crawler attack/death clips. Blood, muzzle, bullet holes, explosions, zombie vocals and all animation needs are covered by owned packs.

## Not needed from Tripo

- **StoneGolem**: model and 25 clips exist, textures are yours; no sword, no shield.
- **Kid and Giant Kid**: same mesh at two scales; the gap is animation, not geometry.
- **Guns**: covered by the EM Apocalyptic Guns pack. Pack-a-Punch tiers are material swaps (emissive camo), not new meshes.
- **Barricade windows**: cut from the design (Section 7).
- **Mystery Box and Wonder Weapon**: cut (no asset, no design).
- **Gore caps, blood decals, muzzle and impact VFX, HUD icons**: not mesh work; I take these from Vefects, Sci_Fi_Weapons_VFX_AIO and the Easy_Shockwaves set already in the project.

## Prompts you can paste

1. Perk machine: "Post-apocalyptic vending machine, 1990s American soda machine shape, rusted steel, bullet dents, cracked glass front, blank flat front panel, heavy base, game prop, PBR"
2. Pack-a-Punch: "Industrial weapon upgrade machine, heavy forge press with an open gun cradle on top, thick cables, copper coils, glowing strip, rusted post-apocalyptic, game prop, PBR"
3. Armor station: "Military locker rack with hanging plate carrier vests and a stack of ceramic armor plates on a shelf, olive drab, worn, post-apocalyptic, game prop"
4. Medic cabinet: "Wall first-aid cabinet with doors open, red cross, syringes and medical kits inside, dirty, post-apocalyptic New York, game prop"
5. Door A: "Chain-link double gate wrapped in chains with a padlock, steel frame, rust, post-apocalyptic, single piece, game prop"
6. Door B: "Pile of collapsed concrete rubble with exposed rebar and a crushed car hood, flat back, blocks a street, post-apocalyptic New York, game prop"
7. Door C: "Plywood barricade wall over a steel frame with missing planks and red KEEP OUT spray paint, post-apocalyptic, game prop"
8. Manhole: "Open New York street manhole with cast iron lid lying beside it, raised rim, asphalt ring, game prop"
9. Stair grate: "Steel sidewalk subway grate bent upward from below, rusted, game prop"
10. Stim: "Military auto-injector syringe with glowing green cartridge, chunky, hand-held, game prop"
11. Self-Revive: "Small medical pouch with a large syringe clipped to it, red cross, game item"
12. Plate: "Ceramic body armor plate, rectangular with cut top corners, one chipped corner, game item"
13. Frag: "M67 fragmentation grenade, olive drab, game item"
14. Ammo crate: "Open military ammo crate with crossbow bolts and magazines inside, olive drab, stencilled, game prop"
15. Breaker: "Industrial electrical breaker panel with a large red lever, warning stickers, rusted, game prop"
16. Trap: "Oil drum on its side with a circular saw blade mounted on top and gas burner nozzles, improvised trap, rusted, game prop"
17. Riot set: "Police riot helmet with visor, game prop" / "Riot chest plate, black polymer, scuffed" / "Riot shoulder guard" / "Riot shin guard"
18. Mangler: "Mutated zombie soldier with a heavy arm cannon fused to the right arm, human legs and left arm, torn uniform, A-pose, game character"
