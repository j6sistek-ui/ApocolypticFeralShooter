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
    UPROPERTY() TObjectPtr<class UBlendSpace> Locomotion;
    FVector LocomotionInput = FVector::ZeroVector;
    bool bGroundLocomotion = false;
    float SequenceRate = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSecondaryMotion = true;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> SecondaryOffsets;
    bool bAiming = false;
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
