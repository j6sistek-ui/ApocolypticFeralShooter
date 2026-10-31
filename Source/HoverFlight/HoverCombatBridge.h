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
struct FHoverGunFeelTier;

// Vendor ammo, reload timers, recoil and spread; AFS supplies the existing gun presentation.
UCLASS()
class HOVERFLIGHT_API AHoverCyberRifle : public AZE_WeaponBase
{
    GENERATED_BODY()
  public:
    AHoverCyberRifle();
    virtual void Tick(float DT) override;
    // P0-1 cadence cap (enhanced gun feel only): no shot inside 1 / GetEffectiveFireRate() of the
    // last one, whatever the tap rate; a semi press inside the interval is buffered.
    virtual void StartFire() override;
    virtual void Reload() override;
    virtual void OnEquipped_Implementation(APawn *NewOwnerPawn) override;
    virtual void OnUnequipped_Implementation(APawn *OldOwnerPawn) override;
    void CancelReload();
    void EjectShellAt(const FTransform &Transform);
    // Rigged guns: the vendor's shell spawn (definition mesh, scale, gravity, lifetime, ShellsPerShot) with
    // the rig's socket-local LocalDirection and Impulse (0: the definition's BulletShellImpulse).
    void EjectRigShellAt(const FTransform &Transform, const FVector &LocalDirection, float Impulse);
    // The opt-in gun feel tier for the held definition; Legacy() while the pilot's gate is off.
    const FHoverGunFeelTier &GetFeelTier() const;
    // CurrentSpread x Lerp(1, .35, aim alpha): the ADS multiplier (P0-1). Raw spread while the gate is off.
    float GetEffectiveSpreadDegrees() const;
    float GetEffectiveFireRate() const;
    // Double Tap 1.2 (economy slice). The vendor timer reads the shared DA, so the scale lives here.
    float FireRateScale = 1.f;

  protected:
    virtual void HandleFire() override;
    virtual void PerformLineTrace() override;
    virtual void PlayFireAnimation() override;

  private:
    FGuid ItemId;
    int32 TPFireCounter = 0;
    float LastFireMontageTime = -10;
    float LastShotTime = -10.f;
    FTimerHandle BufferedShot;
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
    // Katana sweep (owner 2026-10-31: "targeting feels like a small window"): one sweep per sample time, every pawn
    // damaged once per swing.
    TArray<FTimerHandle> SwingTimers;
    TArray<TWeakObjectPtr<AActor>> SwingHits;
    void SweepOnce();
    float SwingEnd = 0;
    bool bGripConfigured = false;
    bool bFirstPersonDetail = false;
    void SetFirstPersonDetail(bool Enabled);
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
    // Next quickbar slot that holds a weapon definition (guns and the katana item, not grenades or consumables).
    UFUNCTION(BlueprintCallable) void CycleWeapon();
    void SuspendForRide();
    UFUNCTION(BlueprintPure) AZE_WeaponBase *GetWeapon() const;
    UFUNCTION(BlueprintPure) bool IsReloading() const;
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
