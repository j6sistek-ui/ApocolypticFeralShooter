#pragma once
#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HoverMovementComponent.generated.h"

UCLASS()
class HOVERFLIGHT_API UHoverMovementComponent : public UCharacterMovementComponent
{
    GENERATED_BODY()
  public:
    virtual void CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration) override;
};
