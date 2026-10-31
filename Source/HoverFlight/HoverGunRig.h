#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "HoverGunRig.generated.h"

class UAnimSequence;
class USkeletalMesh;
class UNiagaraSystem;

// Body stance a rig is held in: which third-person upper-body aim pose the pilot feeds the body
// (UHoverPilotAssets::RifleAim or PistolAim). A pistol's grip_l sits under the right hand, so both hands
// wrap one grip; a rifle's sits out on the handguard.
UENUM(BlueprintType)
enum class EHoverGunStance : uint8
{
    Rifle,
    Pistol
};

// One rigged gun (Docs/EM_GUNS_RIG_PLAN_20261029.md section 5): the skeletal mesh, its mechanical clips
// and the socket names the pilot reads. UHoverPilotAssets::GunRigs picks one per weapon definition;
// AHoverPilot::ApplyGunRig swaps it in on every equip. Socket and bone names follow the universal rig
// convention (section 3: X forward, Z up, origin at grip_r); any that a gun lacks keeps the Fallback*
// offset below and logs once per swap. Nothing here is read from the Ballista DA, which is Y-forward.
UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverGunRig : public UDataAsset
{
    GENERATED_BODY()
  public:
    // Null or empty Mesh means no rig: the pilot shows the static Ballista.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Rig") TObjectPtr<USkeletalMesh> Mesh;
    // Rifle: the body holds Assets->RifleAim (MF_Rifle_Idle_ADS); Pistol: Assets->PistolAim when set, else
    // RifleAim. EM_08 is the only pistol today.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Rig") EHoverGunStance Stance = EHoverGunStance::Rifle;
    // Idle loops between actions; Fire cycles the action once per round (sped up to fit the fire
    // interval); DryFire is the empty click; Reload (the empty reload) starts bolt locked back and is
    // rate-scaled to the weapon's ReloadDuration; Chamber plays once per equip. A missing clip is skipped
    // (Idle missing stops the pose).
    // TODO(design doc): the dropped magazine should become a physics prop; today it is only the clip's
    // magazine bone.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> Idle;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> Fire;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> DryFire;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> Reload;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> Chamber;
    // Empty-magazine state, each optional: FireLast is the round that empties the clip and ends bolt locked
    // back (null: Fire), IdleEmpty loops locked back until the reload (null: Idle), ReloadTactical is the
    // reload with rounds left, bolt home and no release (null: Reload).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> FireLast;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> IdleEmpty;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Clips") TObjectPtr<UAnimSequence> ReloadTactical;
    // Socket (or bone) names on Mesh. With bSocketsDriveOffsets their reference-pose transforms set the
    // pilot's muzzle, grip, support-grip and sight offsets; GunForward is +X for every rig either way. The
    // muzzle and ejection sockets are also read live from the component on every use, so a socket that
    // rides a moving part (a revolver's cylinder) is where the clip has put it.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName MuzzleSocket = TEXT("muzzle");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName EjectSocket = TEXT("ejection_port");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName SightSocket = TEXT("sight");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName GripSocket = TEXT("grip_r");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName SupportSocket = TEXT("grip_l");
    // Magazine well; on a revolver it rides the cylinder. Camera framing and brass only: the hands follow
    // HandTargetSocket, not this.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName MagWellSocket = TEXT("mag_well");
    // Left-hand PALM-CENTRE target bone the gun's own Reload clips key (child of body, rest at grip_l). The
    // body keeps its aim pose through a reload and only the left hand moves, by IK, to this bone read live
    // from the gun component every frame (AHoverPilot::SupportGripOffset), so the hand meets the real
    // magazine by construction. At rest it equals grip_l, so outside a reload nothing changes; a rig
    // without the bone keeps the static SupportSocket offset.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FName HandTargetSocket = TEXT("hand_l_target");
    // Seat grip_r at the right palm centre (midpoint of hand_r and middle_01_r) instead of the wrist, the
    // same rule FHoverSupportHandNode::bGripAtPalm uses for the left hand. GripSocket stays the gun-side point.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") bool bGripAtPalm = true;
    // Right-hand SEAT (owner 2026-10-31 00:10 on the M4A1 burst still: a closed fist at the bottom of the receiver,
    // the pistol grip hanging empty below it). Every rig's grip_r is the pistol-grip TOP centre, but a fist closes
    // around the grip's middle, so seating grip_r at the palm centre put the palm on the grip top and the knuckles
    // over the receiver. GripSeatOffset is where the right PALM CENTRE (midpoint hand_r / middle_01_r) sits
    // relative to grip_r, in gun space (cm, X forward, Y right, Z up): the seat point replaces grip_r wherever the
    // hand is anchored (AHoverPilot::UpdateGunTransform both views, SupportGripOffset for the left-hand IK base,
    // AuthorGunRigs.py's palm assertion); the gun-side points (muzzle, breech trace start, brass) keep grip_r.
    // Scripts/MeasureGripSeat.py measures it from the grip geometry under grip_r and the stance pose's fist (the
    // fist's tunnel centre sits 2-3 cm in front of the palm centre, so the seat is NOT on the grip axis itself).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FVector GripSeatOffset = FVector::ZeroVector;
    // Extra gun-space rotation between the aim-ray/kick rotation and the gun, applied about the seat point, so the
    // grip's axis runs through the fist (the pose's fist rakes differently from each gun's grip). Keep it small
    // (MeasureGripSeat.py clamps at 25 deg): its pitch/yaw part turns the barrel off the aim ray by that much (the
    // verify holds the muzzle within 6 deg of the aim ray at rest), its roll about X costs nothing. The bullet trace
    // is unaffected: FireShot keeps firing along the gun component's own forward from its breech, so the round
    // leaves along the drawn barrel exactly as before; only the drawn barrel vs the camera ray changes, by this.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FRotator GripRotationOffset = FRotator::ZeroRotator;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") bool bSocketsDriveOffsets = true;
    // Rig-frame (cm, X forward, origin at grip_r) offsets for a missing socket, or for all four when
    // bSocketsDriveOffsets is off. Rifle-sized defaults.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FVector FallbackMuzzle = FVector(45, 0, 4);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FVector FallbackGrip = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FVector FallbackSupportGrip = FVector(22, 0, -3);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Sockets") FVector FallbackSight = FVector(5, 0, 9);
    // Brass. bEjectsPerShot with EjectDelay 0: one casing at the ejection socket per round (AR, pistol).
    // bEjectsPerShot with EjectDelay > 0: per round, EjectDelay seconds into the Fire clip (pump, lever,
    // bolt stroke). bEjectsPerShot false with EjectDelay > 0: the spent rounds fall together EjectDelay
    // seconds into the Reload clip (revolver, about .37 s for EM_08). False with 0: never (break, crossbow).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Eject") bool bEjectsPerShot = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Eject", meta = (ClampMin = "0"))
    float EjectDelay = 0.f;
    // Casing throw in the ejection socket's frame (its X is the gun's right, Y rearward), replacing the
    // weapon definition's BulletShellDirection, whose (0, 1, .2) default throws brass back into the camera.
    // EjectImpulse is cm/s (velocity change, +-15 % jitter); 0 keeps the definition's BulletShellImpulse.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Eject") FVector EjectDirection = FVector(1, 0, .25f);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Eject", meta = (ClampMin = "0"))
    float EjectImpulse = 0.f;
    // Revolver index. When CylinderBone is set, AHoverPilot::GunCylinderAngle advances by IndexDegrees on
    // every Fire, DryFire and Chamber (each EM_08 clip turns the cylinder one chamber on). The angle is
    // tracked but not yet applied to the bone: see GunCylinderAngle.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cylinder") FName CylinderBone = NAME_None;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Cylinder") float IndexDegrees = 0.f;
    // Per-gun flash (design C1, 2026-10-30: "she sure lights up a lot, might be overkill, at least for the
    // smaller guns"). MuzzleFlashScale multiplies the weapon definition's Niagara flash scale, MuzzleLightScale
    // the feel tier's MuzzleLightIntensity, both in AHoverPilot::FireShot while this rig is held. Socket, offset,
    // Niagara asset and MuzzleLightSeconds are untouched; the static Ballista path never reads these.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle", meta = (ClampMin = "0", ClampMax = "4"))
    float MuzzleFlashScale = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle", meta = (ClampMin = "0", ClampMax = "4"))
    float MuzzleLightScale = 1.f;
    // Warm, pickable flash (owner 2026-10-30 23:40 on the rusty M4A1: "Maybe gun flash is more red/orange, instead
    // of comic book blue"). MuzzleFlashOverride replaces the weapon definition's MuzzleFlashFX Niagara system
    // (the Ballista's blue NS_BallistaMuzzle) while this rig is held; null keeps the definition's. The capture
    // gallery (Scripts/CaptureGuns.py FLASH_GALLERY) writes it in memory through AHoverPilot::SetMuzzleFlashOverride
    // and restores it; only AuthorGunRigs.py puts one on disk. bOverrideMuzzleLightColor swaps the feel tier's
    // MuzzleLightColor for MuzzleLightColorOverride (orange by default, so the light agrees with a warm sprite).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle") TObjectPtr<UNiagaraSystem> MuzzleFlashOverride;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle") bool bOverrideMuzzleLightColor = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle")
    FLinearColor MuzzleLightColorOverride = FLinearColor(1.f, .62f, .30f);
    // Light reach in cm; 0 keeps the feel tier's MuzzleLightRadius (320). The 2026-10-31 flash gallery proved the
    // whiteout is the point light under the night exposure, not the sprite (every candidate sprite lit the hands
    // the same), so the rigs pull the light in to ~150 cm: the muzzle and hands still catch it, the torso and the
    // street behind her do not.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Muzzle", meta = (ClampMin = "0", ClampMax = "1000"))
    float MuzzleLightRadiusOverride = 0.f;
    // Tracer trial (owner 2026-10-31: the Free Arrow Trail "can also be a bullet tracer"). TracerOverride replaces the
    // feel tier's Tracer Niagara system on AHoverShotVisual while this rig is held (null: the tier's); the trail then
    // takes the tier's TracerColor through User.Color when bTracerOverrideTierColor (the ArrowTrail family exposes
    // it), and TracerOverrideLifetime (s, 0 = the tier's) shortens the ribbon for a bullet. Nothing else about the
    // shot visual changes. CaptureGuns.py TRACER_TRIAL writes these in memory only.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tracer") TObjectPtr<UNiagaraSystem> TracerOverride;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tracer") bool bTracerOverrideTierColor = true;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Tracer", meta = (ClampMin = "0", ClampMax = "2"))
    float TracerOverrideLifetime = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Rig", meta = (MultiLine = true)) FString Description;

    // GunRigs key for a weapon-definition name: a trailing _<digits> is dropped, so Pack-a-Punch tiers
    // (DA_NYC_M16_3) and numbered vendor rows (DA_Weapon_Rifle_001) share DA_NYC_M16 / DA_Weapon_Rifle.
    UFUNCTION(BlueprintPure, Category = "Hover|Weapon") static FName NormalizeWeaponKey(FName DefinitionName);
};
