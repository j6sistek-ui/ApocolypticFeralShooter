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
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> MotionSource;
    bool bMotionMatching = false;
    FVector RideInput = FVector::ZeroVector;
    bool bRiding = false;
    FVector LocomotionInput = FVector::ZeroVector;
    bool bGroundLocomotion = false;
    float SequenceRate = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSecondaryMotion = true;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> SecondaryOffsets;
    UPROPERTY(BlueprintReadOnly) TArray<bool> SecondaryBonesEvaluated;
    bool bAiming = false;
    bool bProne = false;
    bool bLoop = true;
    int32 RestartSerial = 0;
    float FootLock = 0;
    float RiderLean = 0;
    FVector LeftFoot = FVector::ZeroVector;
    FVector RightFoot = FVector::ZeroVector;

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
