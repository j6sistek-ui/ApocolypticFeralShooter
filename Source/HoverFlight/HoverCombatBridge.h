#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Weapons/ZE_WeaponBase.h"
#include "Weapons/ZE_MeleeWeapon.h"
#include "HoverCombatBridge.generated.h"

class AHoverPilot;
class UZE_InventoryComponent;
class UZE_SurvivalComponent;
class UZE_WeaponComponent;
class UZE_InteractionTraceComponent;
class UUserWidget;

// Vendor ammo, reload timers, recoil and spread; AFS supplies the existing gun presentation.
UCLASS()
class HOVERFLIGHT_API AHoverCyberRifle : public AZE_WeaponBase
{
    GENERATED_BODY()
  public:
    virtual void Reload() override;
    virtual void OnEquipped_Implementation(APawn *NewOwnerPawn) override;
    virtual void OnUnequipped_Implementation(APawn *OldOwnerPawn) override;
    void CancelReload();
    void EjectShellAt(const FTransform &Transform);

  protected:
    virtual void PerformLineTrace() override;
    virtual void PlayFireAnimation() override;

  private:
    FGuid ItemId;
};

UCLASS()
class HOVERFLIGHT_API AHoverMeleeWeapon : public AZE_MeleeWeapon
{
    GENERATED_BODY()
  public:
    AHoverMeleeWeapon();
    virtual void Tick(float DT) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    UFUNCTION(BlueprintPure) bool IsSwinging() const;
    void CancelSwing();

  protected:
    virtual void PlayFireAnimation() override;
    virtual void PerformMeleeTrace() override;

  private:
    FTimerHandle ContactTimer;
    float SwingEnd = 0;
    bool bGripConfigured = false;
    void ConfigureGrip(AHoverPilot *Pilot);
};

// Added only in Cyber City; original vendor inventory, purchases and UI remain authoritative.
UCLASS()
class HOVERFLIGHT_API UHoverCombatBridge : public UActorComponent
{
    GENERATED_BODY()
  public:
    UHoverCombatBridge();
    virtual void BeginPlay() override;
    virtual void TickComponent(float DT, ELevelTick Type, FActorComponentTickFunction *Function) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void SetTrigger(bool Held);
    UFUNCTION(BlueprintCallable) void Reload();
    UFUNCTION(BlueprintCallable) void Melee();
    UFUNCTION(BlueprintCallable) void ToggleInventory();
    UFUNCTION(BlueprintCallable) void RefillAmmo();
    UFUNCTION(BlueprintCallable) void SelectQuickbar(int32 Slot = 0);
    void SuspendForRide();
    UFUNCTION(BlueprintPure) AZE_WeaponBase *GetWeapon() const;
    UFUNCTION(BlueprintPure) FString GetPrompt() const;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_InventoryComponent> Inventory;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_SurvivalComponent> Survival;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_WeaponComponent> Weapons;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_InteractionTraceComponent> Interaction;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AHoverMeleeWeapon> MeleeWeapon;
    TMap<FGuid, int32> SavedMagazines;
    UFUNCTION(BlueprintPure) bool IsInventoryOpen() const
    {
        return InventoryUI != nullptr;
    }

  private:
    UPROPERTY() TObjectPtr<UUserWidget> InventoryUI;
    TWeakObjectPtr<AActor> InteractionTarget;
    float InteractionHeld = 0;
    bool bInteracted = false, bTriggerHeld = false;
    TSharedPtr<class FAnalogCursor> InventoryCursor;
    void UpdateInventoryCursor();
};
