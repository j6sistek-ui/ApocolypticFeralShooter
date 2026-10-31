#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "HoverAnimInstance.generated.h"

// A rotation shortened to at most MaxDeg about its own axis (the shortest arc). The hand kick's safety clamp, shared
// by the gun placement (AHoverPilot::UpdateGunTransform) and the support IK so both see the same turn.
inline FQuat HoverClampRotation(const FQuat &Rotation, float MaxDeg)
{
    FQuat Q = Rotation.GetNormalized();
    if (Q.W < 0)
        Q = -Q;
    FVector Axis;
    float Angle;
    Q.ToAxisAndAngle(Axis, Angle);
    const float Max = FMath::DegreesToRadians(MaxDeg);
    if (Angle <= Max || !Axis.Normalize())
        return Q;
    return FQuat(Axis, Max);
}

UCLASS(Transient)
class HOVERFLIGHT_API UHoverAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
  public:
    UPROPERTY() TObjectPtr<UAnimSequence> Sequence;
    UPROPERTY() TObjectPtr<UAnimSequence> RifleAim;
    UPROPERTY() TObjectPtr<UAnimSequence> RifleFire;
    int32 ShotSerial = 0;
    UPROPERTY() TObjectPtr<class UBlendSpace> Locomotion;
    UPROPERTY() TObjectPtr<class UBlendSpace> RideBlend;
    UPROPERTY() TObjectPtr<class UHoverPilotAssets> RideAssets;
    UPROPERTY(BlueprintReadOnly) FVector RideAimInput = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) float RidePitch = 0;
    UPROPERTY(BlueprintReadOnly) FName RideTransition;
    bool bRideThrust = false;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> MotionSource;
    bool bMotionMatching = false;
    UPROPERTY(BlueprintReadOnly) FVector RideInput = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) bool bRiding = false;
    UPROPERTY(BlueprintReadOnly) bool bMountedReload = false;
    FVector LocomotionInput = FVector::ZeroVector;
    bool bGroundLocomotion = false;
    float SequenceRate = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSecondaryMotion = true;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> SecondaryOffsets;
    UPROPERTY(BlueprintReadOnly) TArray<bool> SecondaryBonesEvaluated;
    bool bAiming = false;
    bool bProne = false;
    bool bSupportedProne = false;
    bool bGroundContacts = false;
    FPlane GroundPlane = FPlane(0, 0, 1, 0);
    // Left/right feet, right/left elbows, right/left hands in component space.
    FPlane ContactPlanes[6];
    bool bLoop = true;
    int32 RestartSerial = 0;
    float FootLock = 0;
    float RiderLean = 0;
    FVector LeftFoot = FVector::ZeroVector;
    FVector RightFoot = FVector::ZeroVector;
    FVector SupportGripOffset = FVector::ZeroVector;
    FQuat WeaponRotation = FQuat::Identity;
    // The held rig seats grip_r at the right palm centre (UHoverGunRig::bGripAtPalm), so the support IK must
    // anchor its offset there too, or the left palm lands half a hand short of grip_l.
    bool bGripAtPalm = false;
    // Design B1 (2026-10-30): the rig's hand_l_target ROTATION is a gun-space delta from its rest (identity)
    // meaning "turn the left hand this much from how the aim pose holds it"; its bone-LOCAL scale X is the finger
    // curl (1 = the aim pose's fingers, 0 = the open reference pose, up to 1.6 = tighter). Identity / 1 when not
    // rigged or the rig has no such bone, so nothing changes outside an authored reload beat.
    FQuat SupportHandRotation = FQuat::Identity;
    float SupportHandCurl = 1.f;
    // Design A2: a rigged gun is drawn at the right hand (aiming or GunRaisedTime). While true the support IK runs
    // at weight 1 whatever drops bAiming (hit reacts, parkour actions), so the left hand never leaves the gun.
    bool bRiggedGunUp = false;
    // Design A1: the stance fire reaction (UHoverPilotAssets::RifleFireAdd / PistolFireAdd), restarted on every
    // ShotSerial change as a local-space additive over the aim pose, before the layered blend and the support IK, so
    // both hands ride the recoil. Null outside a rigged third-person stance. StanceRecoilScale scales it.
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UAnimSequence> StanceFireAdd;
    float StanceRecoilScale = 1.f;
    // Gun-rides-the-hand (2026-10-30 23:30, "her hand is not on the grip"): hand_r's component-space rotation in the
    // settled stance aim pose, cached by AHoverPilot::UpdateGunTransform while the fire additive is quiet. The support
    // IK turns its gun frame by (hand_r now) * (rest)^-1, the same kick UpdateGunTransform gives the gun, so the left
    // hand's target rides the recoil with the gun instead of lagging it by a frame. Invalid = no kick.
    FQuat GripHandRestRotation = FQuat::Identity;
    bool bGripHandRestValid = false;
    // Read-out (verify): the largest right-finger local rotation the fire additive wanted on the last evaluation,
    // which FHoverStanceFireNode replaced with the aim pose's; 0 while no additive runs.
    UPROPERTY(BlueprintReadOnly) float StanceFireFingerSplayDeg = 0.f;

  protected:
    virtual FAnimInstanceProxy *CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy) override;
};

UCLASS(Transient)
class HOVERFLIGHT_API UHoverViewAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
  public:
    UPROPERTY() TObjectPtr<UAnimSequence> Idle;
    UPROPERTY() TObjectPtr<UAnimSequence> AimIdle;
    UPROPERTY() TObjectPtr<UAnimSequence> MeleeIdle;
    bool bMelee = false;
    float AimAlpha = 0;
    FVector SupportGripOffset = FVector::ZeroVector;
    FQuat WeaponRotation = FQuat::Identity;
    // Same convention as UHoverAnimInstance (design B1/B3), read from ViewGunSkel's hand_l_target.
    FQuat SupportHandRotation = FQuat::Identity;
    float SupportHandCurl = 1.f;

  protected:
    virtual FAnimInstanceProxy *CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy) override;
};

UCLASS(Transient)
class HOVERFLIGHT_API UHoverAccessoryAnimInstance : public UAnimInstance
{
    GENERATED_BODY()
  public:
    UPROPERTY(BlueprintReadOnly) FVector ChainAngles = FVector::ZeroVector;

  protected:
    virtual FAnimInstanceProxy *CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy) override;
};
