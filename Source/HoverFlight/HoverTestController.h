#pragma once
#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "HoverTestController.generated.h"
class AHoverPilot;

UCLASS()
class HOVERFLIGHT_API AHoverTestController : public APlayerController
{
    GENERATED_BODY()
  public:
    virtual void PlayerTick(float DeltaSeconds) override;
    bool IsNearBike() const;
    bool IsNearTruck() const;
    bool TryEnterBike();
    UFUNCTION(BlueprintPure) APawn *GetTestBike() const
    {
        return Bike;
    }
    UFUNCTION(BlueprintPure) APawn *GetTestTruck() const
    {
        return Truck;
    }
    bool IsDrivingTruck() const
    {
        return Truck && GetPawn() == Truck;
    }

  private:
    UPROPERTY() TObjectPtr<AHoverPilot> Pilot;
    UPROPERTY() TObjectPtr<APawn> Bike;
    UPROPERTY() TObjectPtr<APawn> Truck;
    UPROPERTY() TObjectPtr<AActor> DressedDriver;
    float ExitHold = 0;
    bool bExitConsumed = true, bSpawnAttempted = false;
    void DressDriver();
    void ExitTruck();
};
