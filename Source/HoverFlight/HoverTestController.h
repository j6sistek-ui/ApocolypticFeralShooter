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
    TSet<FName> TestHeldKeys;
#endif
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual bool InputKey(const FInputKeyEventArgs &Params) override;
    virtual void PlayerTick(float DeltaSeconds) override;
    UFUNCTION(Exec) void HoverGraphics();
    UFUNCTION(Exec) void HoverLoadLevel(int32 Level);
    // AFS 2026-11-01: "Weather Rain" / "Weather Snow 0" / "Weather" (report). Same path as the F6 weather row.
    UFUNCTION(Exec) void Weather(const FString &Mode);
    // Test level menu: 0 PostApo, 1 Cyber City, 2 Lakeside, 3 NYC Exploration, 4 NYC Survival.
    static constexpr int32 TestLevelCount = 5;
    static int32 GetTestLevelIndex(const FString &MapName);
    static const TCHAR *GetTestLevelLabel(int32 Level);
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
    TWeakObjectPtr<AHoverPilot> MeleeInputPilot;
    float MeleeHoldTime = 0;
    bool bMeleeHoldConsumed = false;
    void DressDriver();
    void ExitTruck();
};
