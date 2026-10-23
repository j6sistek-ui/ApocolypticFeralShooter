#pragma once
#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "HoverTestController.generated.h"
class AHoverPilot;
class UHoverGraphicsSettings;
class UHoverGraphicsMenu;

UCLASS()
class HOVERFLIGHT_API AHoverTestController : public APlayerController
{
    GENERATED_BODY()
  public:
#if WITH_EDITOR
    bool bTestInputOnly = false;
    bool bInjectingTestKey = false;
#endif
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual bool InputKey(const FInputKeyEventArgs &Params) override;
    virtual void PlayerTick(float DeltaSeconds) override;
    UFUNCTION(Exec) void HoverGraphics();
    UFUNCTION(BlueprintPure) bool IsGraphicsMenuOpen() const
    {
        return GraphicsMenu != nullptr;
    }
    UFUNCTION(BlueprintPure) UHoverGraphicsSettings *GetGraphicsSettings() const
    {
        return GraphicsSettings;
    }
    UFUNCTION(BlueprintPure) UHoverGraphicsMenu *GetGraphicsMenu() const
    {
        return GraphicsMenu;
    }
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
    UPROPERTY() TObjectPtr<UHoverGraphicsSettings> GraphicsSettings;
    UPROPERTY() TObjectPtr<UHoverGraphicsMenu> GraphicsMenu;
    void CloseGraphicsMenu(bool bApply);
    UPROPERTY() TObjectPtr<AHoverPilot> Pilot;
    UPROPERTY() TObjectPtr<APawn> Bike;
    UPROPERTY() TObjectPtr<APawn> Truck;
    UPROPERTY() TObjectPtr<class UInputMappingContext> BikeMappings;
    void UpdateBikeMappings();
    void SetBikeParked(bool bParked);
    bool bBikeParkingLock = false;
    bool bBikeLockX = false, bBikeLockY = false, bBikeLockYaw = false;
    uint8 BikeSavedDOF = 0;
    UPROPERTY() TObjectPtr<AActor> DressedDriver;
    float ExitHold = 0;
    bool bExitConsumed = true, bSpawnAttempted = false;
    void DressDriver();
    void ExitTruck();
};
