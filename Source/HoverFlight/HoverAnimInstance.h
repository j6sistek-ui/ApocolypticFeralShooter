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
    bool bAiming = false;
    bool bLoop = true;
    int32 RestartSerial = 0;
    float FootLock = 0;
    FVector LeftFoot = FVector::ZeroVector;
    FVector RightFoot = FVector::ZeroVector;

  protected:
    virtual FAnimInstanceProxy *CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy) override;
};
