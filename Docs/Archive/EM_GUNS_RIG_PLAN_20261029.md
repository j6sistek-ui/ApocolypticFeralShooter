# EM Apocalyptic Guns Vol 23: rigging plan (2026-10-29)

How the 30 bought guns become rigged, animated weapons that follow the M4A1 convention, which of them the survival mode uses, and what the C++ needs so each weapon shows its own gun.

Survey data: `SourceAssets/EM_Apocalyptic_Guns/em_guns_survey.json`, made by `Scripts/Blender/SurveyEMGuns.py` (Blender 5.2, headless). Proof sheets in the same folder:

- `em_guns_uv_islands_sheet.png`: every gun with each UV island in its own colour.
- `em_guns_mag_autopick_sheet.png`: the magazine the script would cut, shown in red.
- `_survey_tiles/fileaxes_sheet.png`: every gun as it sits in its FBX file.

## 1. Survey headline

| Finding | Detail |
|---|---|
| **No gun has a loose magazine** | All 30 are one welded shell. 28 have exactly one mesh island; EM_09 and EM_10 add only 1-4 stray triangles. Every moving part has to be cut out. |
| **Magazines are separate UV islands** | The unwrap puts each part on its own UV islands, so the UV seams mark the part borders. For 10 of the 13 box-mag guns, plus the EM_26 tank, the auto-pick selects exactly the magazine (red sheet). EM_14, EM_24 and the EM_12 canister need a hand-drawn seed box. EM_03 has no visible magazine, only the floor plate under the grip. |
| **Scale is cm at 1.0, not inches at 2.54** | Every FBX header says UnitScaleFactor 1.0 (cm), Maya, Y-up. At 1.0, EM_13 (a bolt-action) is 120 cm and EM_21 (an MP5K) is 34 cm, both life-size. At x2.54, EM_13 would be 3 m. The EM_21 test agent measured the same independently. **Import every gun at scale 1.0.** |
| **The pack is not consistently scaled** | EM_02 is oversized (155 cm). EM_17, 18, 19, 20 and 22 are 55-76 cm but are full-size guns. Section 2 has a per-gun factor. |
| **Rotated files** | The rotated files are EM_17 and EM_18 (Z -90°, plus node scale 0.53 / 0.64) and EM_26 (Z 180°, node scale 36.5). EM_09 is not rotated; it is wide because of its bow limbs. EM_04 is tilted 9.5° and stands upright. Unreal applies these node transforms, so what matters is the muzzle side: **+X for 01-12, 23, 24 and 26-30; -X for 13-22 and 25.** |
| **EM_09 is a crossbow** | A repeating pistol crossbow with a box bolt magazine and 67 cm limbs. It is a natural Heavy Ballista visual. |
| **Emissive maps are mostly empty** | 16 of 30 Emissive PNGs are a blank 12 KB image. The rest hold small lens glints, so the Pack-a-Punch glow must be a material parameter. |
| Triangles | 24.5k (EM_13) to 60.7k (EM_09), median about 38k. Each gun has one material. |

Per gun (length / height / width in cm at scale 1.0; "UV isl" is the UV island count; the magazine split codes are explained in section 4):

| Gun | Tris | L / H / W | UV isl | Muzzle | Class | Mag | Action | Mag split | Role |
|---|---|---|---|---|---|---|---|---|---|
| 01 | 32k | 119/38/9 | 293 | +X | lever-action shotgun | tube | lever + hammer | n/a; lever by UV box | **Roster: lever shotgun** |
| 02 | 26k | 155/34/11 | 153 | +X | battle rifle, M14-style | box | carrier + op-rod | A | kiosk; scale 0.75 |
| 03 | 42k | 29/16/6 | 492 | +X | pistol with suppressor and light | box in grip | slide | C | kiosk; alt sidearm |
| 04 | 26k | 20/21/4 | 247 | ? | improvised vertical tube device | none | ? | n/a | kiosk |
| 05 | 39k | 41/16/5 | 291 | +X | pipe pistol (AR lower) | none | hammer | n/a | kiosk |
| 06 | 31k | 50/17/9 | 252 | +X | improvised hand cannon | none | break | n/a | kiosk |
| 07 | 36k | 44/20/6 | 409 | +X | long-barrel revolver | cylinder | hammer | cylinder by UV box | kiosk |
| 08 | 43k | 30/17/5 | 331 | +X | heavy revolver, swing-out cylinder | cylinder | hammer + crane | cylinder by UV box | **Roster: sidearm** (test gun) |
| 09 | 61k | 48/35/67 | 883 | +X | repeating pistol crossbow | box (bolts) | string + cocking lever | A | **Roster: Heavy Ballista option** |
| 10 | 33k | 119/23/9 | 284 | +X | improvised long rifle | internal | bolt handle | n/a | kiosk |
| 11 | 37k | 99/50/11 | 282 | +X | suppressed AK carbine | box | carrier + charging handle | A | **Roster: rifle (M16 slot)** (test gun) |
| 12 | 45k | 97/37/13 | 523 | +X | canister rifle, tank on top | canister | none | A* | kiosk (wonder flavour) |
| 13 | 25k | 120/23/7 | 174 | -X | bolt-action, Mosin-style | internal | bolt handle | n/a; bolt by UV box | **Roster: sniper** |
| 14 | 33k | 119/25/11 | 282 | -X | DMR, SVD-style | box | carrier + charging handle | A* | kiosk |
| 15 | 40k | 119/41/9 | 349 | -X | AK, scope, bayonet | box | carrier + charging handle | A | kiosk |
| 16 | 48k | 36/14/4 | 506 | -X | triple-barrel hand shotgun | none | break | n/a | kiosk |
| 17 | 43k | 63/21/6 | 467 | -X | drum lever-shotgun | drum | lever + hammer | drum by UV box | kiosk; scale 1.6 |
| 18 | 40k | 76/16/6 | 387 | -X | bolt sniper with bipod | small box | bolt handle | A (verify) | kiosk; scale 1.55 |
| 19 | 38k | 56/22/4 | 360 | -X | AKM, folding stock | box | carrier + charging handle | A | kiosk; scale 1.6 |
| 20 | 26k | 65/15/6 | 214 | -X | scoped bolt-action | internal | bolt handle | n/a | kiosk; scale 1.7 |
| 21 | 47k | 34/21/5 | 542 | -X | SMG, MP5K-style | box | carrier + cocking lever | A | **Roster: SMG** (test gun) |
| 22 | 45k | 70/21/5 | 394 | -X | improvised AK, bayonet | box | carrier + charging handle | A | kiosk; scale 1.25 |
| 23 | 38k | 101/27/7 | 347 | +X | wrapped battle rifle | box | carrier + charging handle | A | kiosk |
| 24 | 27k | 97/25/7 | 238 | +X | SKS/M14-style, bayonet | box | carrier + op-rod | A* | kiosk |
| 25 | 37k | 45/17/7 | 417 | -X | heavy pump shotgun | tube | pump | n/a; pump by UV box | **Roster: shotgun** |
| 26 | 41k | 34/38/12 | 493 | +X | canister contraption | canister | none | A (tank) | kiosk (wonder flavour) |
| 27 | 44k | 82/30/8 | 457 | +X | FAL-style battle rifle | box | carrier + charging handle | A | **Roster: battle rifle / DMR** |
| 28 | 31k | 41/19/6 | 472 | +X | magnum revolver | cylinder | hammer + crane | cylinder by UV box | **Roster: magnum** |
| 29 | 29k | 66/30/15 | 263 | +X | grenade launcher | none (single) | break | n/a | kiosk |
| 30 | 41k | 39/23/5 | 423 | +X | revolver with knife bayonet | cylinder | hammer | cylinder by UV box | kiosk |

Totals: 13 box magazines, 2 canisters, 5 cylinders/drums, 2 tubes, 3 internal, 5 with no magazine.

## 2. Roster: 9 rigged guns, 21 kiosk-only

| Slot (design) | Gun | Definition key | Status |
|---|---|---|---|
| Sidearm, wall buy 500 (Stage 1) | EM_08 | `DA_NYC_Sidearm` (+`_2`) | test gun in progress; see open question 2 |
| M16 slot, full-auto rifle 1,250 (Stage 2) | EM_11 | `DA_NYC_M16` (+`_2.._4`) | test gun in progress |
| SMG (new wall buy) | EM_21 | `DA_NYC_SMG` (new) | test gun in progress |
| Shotgun (new) | EM_25 | `DA_NYC_Shotgun` (new) | first pump |
| Battle rifle / DMR (new) | EM_27 | `DA_NYC_DMR` (new) | pure box-mag case, reuses the EM_11 script |
| Sniper (Stage 2, new) | EM_13 | `DA_NYC_Sniper` (new) | first bolt-action |
| Lever shotgun (flavour, new) | EM_01 | `DA_NYC_Lever` (new) | first lever |
| Magnum (new, or the sidearm's PaP look) | EM_28 | `DA_NYC_Magnum` (new) | reuses the EM_08 revolver script |
| Heavy Ballista (Stage 2) | EM_09 | `DA_NYC_HeavyBallista` (+`_2.._4`) | only if you want it instead of `SM_CS1_Crossbow_03a` |

The Ballista keeps its own crossbow mesh. Pack-a-Punch tiers share the base gun's rig and change only the material. The other 21 guns become static meshes on the armory and kiosk walls: scale normalised, muzzle +X, LODs, no rig.

## 3. Universal rig convention (one page)

Follows `Scripts/Blender/RigM4A1.py` exactly; nothing here contradicts it.

| Item | Rule |
|---|---|
| Axes | Muzzle +X, up +Z. In Blender the gun's right side faces -Y; Unreal reads that as +Y. |
| Origin | The `root` bone head sits at the top of the pistol grip, on the centre line. This is also where the `grip_r` socket bone goes. |
| Scale | Centimetres in Unreal. Import at 1.0, then apply the per-gun factor from section 1 inside Blender before rigging, so the exported FBX is already life-size. |
| Skin | Rigid. One joined mesh, each vertex weighted 1.0 to a single bone, one material slot. |
| Export | The M4A1 `FBX_COMMON` call: `axis_forward='-Y', axis_up='Z'`, primary bone axis Y, no leaf bones. Export the mesh once, then one FBX per clip. |
| Skeleton | One USkeleton **per gun**. Do not share one: bone rest positions differ, so shared translation clips would move parts to the wrong place. The fixed names below keep the C++ and the Blender script generic. |
| Clips (60 fps) | `A_<Gun>_Idle` (2 frames), `_Fire` (frames 0-7, 0.12 s), `_DryFire` (0-9), `_Reload` (0-144, 2.4 s, rate-scaled to the weapon's ReloadDuration), `_Chamber` (0-66, 1.1 s). For hand-cycled guns (pump, lever, bolt-action), Fire is 0.6-0.9 s; `PlayGunFire(MaxSeconds)` already speeds it up to fit the fire interval. |
| Reload beats | Same as the M4A1: magazine (or opening part) leaves at 0.25-0.9 s, the fresh one seats at about 1.8 s, the action closes at 1.9-2.3 s. The body clip lines up with these beats. |
| Bone axes | Every bone points Blender **+Y with roll 0** (identity in Unreal component space: bone X forward, Y right, Z up); `ejection_port` alone points Blender +X so its Unreal X is the gun's right. EM_11 was authored along +X on 2026-10-29 and came into Unreal with a 90 deg yaw on `root`: positions were right, every socket's X pointed to the right and brass would have flown rearward. Fixed at source 2026-10-30; `Scripts/ValidateGunClips.py` now fails any rig whose rest orientation is not identity. |
| Frame rate | Set `scene.render.fps = 60` **after** `import_scene.fbx`: the importer resets the scene to the source file's 30 fps, and a 60 fps clip exported at 30 lands in Unreal at double length (EM_11 Fire 0.233 s instead of 0.117 s). |
| Re-import | A rig whose bone orientation or hierarchy changed must be deleted in Unreal first (`SK_<Gun>`, `SK_<Gun>_Skeleton`, the clips) and imported fresh: an in-place reimport keeps the Skeleton asset's old reference pose, so clips with tracks and the Idle clip (no tracks, plays the reference pose) disagree by the old rotation. |
| Revolver index | `IndexDegrees` is **signed** the way the clips turn the cylinder in Unreal's own data (EM_08: +60 about X in the FQuat(axis, angle) sense; `ValidateGunClips.py` measures it with the w >= 0 quaternion convention and rewrites the data asset when it disagrees). `AHoverPilot::FinalizeGunPose` adds `GunCylinderApplied` about the cylinder bone's X after every clip evaluation, so the one-chamber turn each Fire / DryFire / Chamber authors carries into Idle instead of snapping back; the EM_08 chambers are not 6-fold symmetric, so the snap was visible. |
| Hand target | Every rig carries a non-deforming `hand_l_target` bone (position = left PALM CENTRE; ROTATION = delta from the aim pose's hand frame, identity at f0/end; SCALE X = finger curl, 1.0 = aim pose, 0.6 open, 1.3 tight; see `Scripts/MeasureHandAxes.py` for the hand axes) (child of body, rest = `grip_l` head, +Y identity). Static clips leave it at grip_l; Reload keys the left PALM CENTRE through the choreography (grab the mag with a measured cup offset, pull, release, belt at about (6,-14,-42) cm from grip_r, fresh mag pops in at the hand, carry, seat, charging-handle beat) and returns to grip_l on the last frame. In game `FHoverSupportHandNode` IKs `hand_l` to the live socket, so the body needs no reload clip. Validate: == grip_l at f0 / end (0.3 cm), rides the magazine within 2 cm mid-carry. |
| Magazine continuity | The empty mag free-falls from the hand's release point, then its bone SCALE goes to 0.001 (hidden) about 55-60 cm below the well; the fresh mag pops in at the hand at the belt (scale 1.0) and never rises from below the hand. Scale track baked by the exporter (`bake_anim_use_all_bones`, `use_armature_deform_only=False`). |
| Stance | `UHoverGunRig::Stance` Rifle or Pistol picks the body aim pose (`RifleAim` / `PistolAim`); `bGripAtPalm` seats grip_r at the palm (midpoint hand_r / middle_01_r). Revolvers and pistols = Pistol. |
| Proof | `Scripts/ValidateGunClips.py` (CPU, 74 checks on 2026-10-30 evening: lengths, component-space strokes and angles vs the rig JSON numbers, rest orientation, missing tracks) and `Scripts/CaptureGuns.py` (GPU: stills and video of all four rigged guns in Vexa's hands, hands camera per reload mark, `hand_l_to_target_cm` / `hand_r_rot` telemetry) and `Scripts/AuthorGunRigs.py --verify-only` (35 headless PIE assertions incl. palm-to-target and gun-hand stillness). |

**Bone superset.** A gun contains only the bones it uses, but every bone's name comes from this list:

| Bone | Used by |
|---|---|
| `root`, `body`, `trigger` | every gun |
| `magazine` | box mags, canisters (the tank), crossbow bolt box |
| `bolt_carrier` | the part that recoils on each shot: AR/AK bolt carrier, pistol slide, bolt-action bolt body |
| `charging_handle` | the part the hand pulls: AR/AK handle, MP5 cocking lever, **bolt-action bolt handle**, crossbow cocking lever |
| `hammer` | revolvers, pistols, lever guns, break-actions |
| `crane`, `cylinder` (child of `crane`) | revolvers, EM_17 drum |
| `pump` | pump shotguns |
| `lever` | lever-actions |
| `breech` | break-actions (barrel hinge) |
| `string` | crossbows |
| `selector`, `mag_release`, `bolt_catch` | optional M4A1 extras |

Socket bones (children of `body`, not deforming): `muzzle`, `ejection_port` (+Y points out to the right), `sight`, `grip_r`, `grip_l`, `mag_well`.

**What each clip moves, by action type:**

| Type | Fire | Reload (2.4 s) | Chamber (1.1 s) | `ejection_port` |
|---|---|---|---|---|
| AR / AK / SMG / battle | `bolt_carrier` back and home, `trigger` | `magazine` drops 45 cm and a fresh one rises; carrier released | `charging_handle` + `bolt_carrier` racked | yes, one casing per shot |
| Pistol | `bolt_carrier` (the slide), `hammer` | `magazine` out and in, slide drops | slide racked | yes |
| Revolver | `hammer` cocks, `cylinder` turns 360/n degrees | `crane` swings out, `cylinder` nudged (ejector), swings back | `hammer` cocked | **none per shot** |
| Pump | `pump` back and forward (~0.6 s) | `pump` locked back, body tilt, `pump` home | `pump` cycled | after the pump stroke |
| Lever | `lever` down and up, `hammer` | `lever` open and close | `lever` cycled | after the lever stroke |
| Bolt-action | `charging_handle` lifts and slides back with `bolt_carrier`, then returns (~0.9 s) | bolt open, close (`magazine` too if there is one) | bolt cycled | after the bolt stroke |
| Break | `hammer` | `breech` opens about 35°, closes | `breech` snaps shut | none |
| Crossbow | `string` snaps forward | `magazine` swap, `string` re-drawn | `charging_handle` cocks the string | none |

Tube magazines reload in one 2.4 s clip, not shell by shell; the character's hands sell the loading. Per weapon type, the C++ needs only two fields on the rig asset (section 5): `bEjectsPerShot` and `EjectDelay`.

## 4. Cutting the moving parts out

Since no part is loose, every gun uses one cut routine; the code, `cut_part`, is in `Scripts/Blender/RigEM_21.py`. The cases differ only in how the faces are selected.

| Case | Guns | Selection | Blender sequence |
|---|---|---|---|
| (a) loose island | none in this pack | `bpy.ops.mesh.select_linked()` | separate; parent to the bone |
| (b) own UV islands, welded at the seam: **A** auto / **A\*** seed box | A: 02, 09, 11, 15, 18, 19, 21, 22, 23, 26, 27. A\*: 12, 14, 24, plus every cylinder, pump, lever and bolt handle | UV islands that lie at least 95 % inside the part's box (source cm, read off an ortho render) | bmesh: UV-island flood, faces inside the box → `bmesh.ops.split` along the border edges → border loops → `bmesh.ops.holes_fill` on **both** sides → `bmesh.ops.triangulate` on the caps → cap UVs scaled into a 0.0025-UV patch next to a neighbouring face (it samples the dark recess colour) → vertex group for the bone |
| (c) no clean seam or no part geometry | EM_03 magazine; any part whose UV island also covers the receiver | box | `bpy.ops.mesh.bisect(plane_co, plane_no, use_fill=True)` on the receiver at the well line, or a Boolean DIFFERENCE with a cube (EXACT solver) plus a Boolean INTERSECT on a copy for the part; then cap as in (b). For EM_03, duplicate the floor plate and extrude a box 9 cm up inside the grip. |

**Quality rule.** With the moving part hidden, render the gun from 2.5 m at the gameplay FOV, from below at 45° and from the right side. No background may show through the receiver; the cap reads as a dark recess, never as the gun's base colour or as a stretched texture. Then cut out the opening bounds plus 5 mm, so no slivers are left on the receiver.

## 5. Per-weapon binding (one evening of C++)

**Today.** `AHoverPilot` always draws `Assets->Gun` (`HoverPilot.cpp:243/253`); the skeletal path adds one `RiggedGun`. So the Sidearm shows the Ballista mesh, whatever the definition is.

**Change.** Add one small data asset per gun, plus a lookup table keyed the same way as `UHoverGunFeel::Find`, which uses `Definition->GetFName()`:

```cpp
UCLASS() class UHoverGunRig : public UDataAsset {   // HoverPilot.h
  UPROPERTY(EditAnywhere) TObjectPtr<USkeletalMesh> Mesh;
  UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Idle, Fire, DryFire, Reload, Chamber;
  UPROPERTY(EditAnywhere) FName Muzzle="muzzle", Eject="ejection_port", Sight="sight",
                                GripR="grip_r", GripL="grip_l", MagWell="mag_well";
  UPROPERTY(EditAnywhere) bool bEjectsPerShot = true;  // false: revolver, break, crossbow
  UPROPERTY(EditAnywhere) float EjectDelay = 0.f;      // pump / lever / bolt: eject on the stroke
};
// UHoverPilotAssets:
UPROPERTY(EditAnywhere, Category="Weapon|Rigged") TMap<FName, TObjectPtr<UHoverGunRig>> GunRigs;
```

| Piece | Behaviour |
|---|---|
| `FindGunRig(Definition)` | Looks for an exact name first, then the name with a trailing `_<digits>` removed (so `DA_NYC_M16_3` finds `DA_NYC_M16`). If neither exists it returns null, and the static Ballista path stays. |
| `AHoverPilot::ApplyGunRig(const UHoverGunRig*)` | Today's `SetupRiggedGun`, but with its inputs passed in: set `ViewGunSkel`/`WorldGunSkel` to the mesh, re-read the sockets into `GunMuzzle/Grip/SupportGrip/Sight`, then `PlayGunChamber()`. It does nothing when given the rig that is already applied. |
| Call site | `AHoverCyberRifle::OnEquipped_Implementation`, already in the code. Wall buys (`AHoverArmoryBuy`), pickups, quickbar cycling and the Pack-a-Punch DA swap all end in an equip, so they need no new code. |
| Stays in DA_HoverPilot | `Gun`/`GunOptic` (the Ballista fallback), the fallback vectors, `GunFeel`, the camera, and the existing `RiggedGun` fields (treated as the default rig until migration). |
| Not used | The vendor `ZE_WeaponDefinition::ThirdPersonSkeletalMesh` and `Weapon*Montage`. Using them would mean two sources of truth, and they are montages with no idle, dry-fire or chamber clips. The rig also stays out of the gun feel table, because `GetFeelTier` returns `Legacy()` while the feel gate is off, and the gun must not disappear when it is. |

**Keys to fill:**

| Key | Rig |
|---|---|
| `DA_NYC_Sidearm`, `DA_Weapon_Pistol_001` | EM_08 |
| `DA_NYC_M16`, `DA_Weapon_Rifle_001` | EM_11 |
| `DA_NYC_SMG` | EM_21 |
| `DA_NYC_Shotgun` | EM_25 |
| `DA_NYC_DMR` | EM_27 |
| `DA_NYC_Sniper` | EM_13 |

`HoverGunFeel` has plain `Shotgun` and `Sniper` rows waiting; rename them to the new DA names when those DAs exist.

## 6. Production order, time, QA

| Wave | Guns | Script work | Human time per gun |
|---|---|---|---|
| 0 (running now) | EM_11, EM_21, EM_08 | three archetype scripts: box mag, SMG lever, revolver | (in progress) |
| 1 | EM_27, then EM_09 | Turn `RigEM_21.py` into `RigEMGun.py --gun EM_NN`, with each gun's settings (landmarks, part boxes, scale) in `Scripts/Blender/em_gun_rigs.json` | 30-45 min |
| 2 | EM_25 pump, EM_13 bolt, EM_01 lever | one new clip template per action type | first gun 2-3 h, each repeat about 45 min |
| 3 | EM_28 | revolver template from EM_08 | about 45 min |
| Kiosk | the other 21 | one batch script: scale, rotate to +X, export static FBX | about 10 min for all |

| Batch-scripted | Needs a human look |
|---|---|
| Import, scale and turn to +X; UV-island survey and auto-pick; cut and cap; armature from the template; rigid skin; clips from the action template (travel scales with gun size); export; re-import asserts; proof renders | Landmarks per gun (grip_r, grip_l, sight, muzzle, trigger pivot, part boxes) picked from ortho renders, about 15 min; confirming the red auto-pick; the hole check; the final in-game frames |

**QA: every gun must pass:**

1. Re-import asserts: every bone and socket bone exists; length within 2 % of the target; clip frame counts 2/8/10/145/67; each clip moves only its intended bones; `root` sits at grip_r.
2. Proof renders from the right three-quarter and the top: rest; Fire peak; Reload at 0.75 s (part out); Chamber apex.
3. Hole check from section 4, with the part hidden: from below and from the right at 2.5 m.
4. In game (third person 300 cm and first person):
   - Both hands on grip_r/grip_l with no clipping.
   - Muzzle flash at the muzzle.
   - Casing leaves to the right (none for revolvers).
   - ADS sight line matches the crosshair.
   - Reload mid-frame shows the part out with no see-through.
   - PaP tier 3 shows the same mesh with the new material.

## 7. Risks and open questions for you

1. **Gun size.** Six guns in the pack are not life-size. Should I scale them to real lengths (my table), or size all of them to Vexa's hand by eye?
2. **Sidearm magazine.** The design gives the Sidearm a 12-round magazine, but EM_08 is a 6-shot revolver. Change it to 6 rounds, or use EM_03 (a pistol, but its magazine has to be modelled)?
3. **Caps.** Every cut leaves a flat dark cap. It is invisible at 2-3 m, but in first person, up close, the empty mag well looks like a flat dark plate. Is that acceptable?
4. **Body animations.** Vexa only has a rifle reload (`MM_Rifle_Reload`). Revolver, pump, bolt-action and lever reloads need matching body clips, or the gun moves while the hands do the rifle motion. These are not sourced yet.
5. **Tube guns reload in one go** (2.4 s), not shell by shell. Shell-by-shell is a gameplay change.
6. **EM_09 crossbow as the Heavy Ballista visual?** It suits the bolt-firing theme better than a gun.
7. **Pack-a-Punch glow** cannot come from the Emissive textures (mostly blank); it will be a material parameter.
8. **Textures.** Only the inner RARs are unpacked so far, into `SourceAssets/EM_Apocalyptic_Guns/_inner_rar/` (3.3 GB). The PNGs themselves still need extracting (1.6 GB) before any Unreal import.
9. **C++ dependency.** Everything in section 5 depends on the skeletal-gun path that is still landing (`SetupRiggedGun` is declared but not yet in `HoverPilot.cpp`).
