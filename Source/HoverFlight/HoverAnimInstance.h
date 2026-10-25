#pragma once
#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "HoverAnimInstance.generated.h"

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
