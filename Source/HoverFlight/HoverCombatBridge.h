#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Weapons/ZE_WeaponBase.h"
#include "Weapons/ZE_MeleeWeapon.h"
#include "HoverMeleeProfile.h"
#include "HoverCombatBridge.generated.h"

class AHoverPilot;
class UZE_InventoryComponent;
class UZE_SurvivalComponent;
class UZE_WeaponComponent;
class UZE_InteractionTraceComponent;
class UZE_WeaponDefinition;
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
    // AFS 2026-10-31 (spear item): per-weapon strike data (HoverMeleeProfile.h). The katana keeps
    // FHoverMeleeProfile::Katana(), the 2026-10-31 swept slash exactly; the NYC Survival spear gets LoadSpear().
    void SetProfile(const FHoverMeleeProfile &InProfile);
    const FHoverMeleeProfile &GetProfile() const
    {
        return Profile;
    }
    // The melee input (R3 tap / V): the next light strike, or a buffered one inside the chain window.
    void PressLight();
    // Trigger level (R2 / LMB) for a profile with a heavy: a tap is a light press on release, a hold past
    // ChargeThreshold winds the heavy and the release throws it.
    void SetAttackHeld(bool Held);
    // Quickbar switched away: stop the strike, the charge and the stance loop.
    void OnHolstered();
    bool IsHeldBy(const AHoverPilot *Pilot) const;
    UFUNCTION(BlueprintPure) bool IsCharging() const
    {
        return bCharging;
    }
    UFUNCTION(BlueprintPure) float GetChargeAlpha() const;
    UFUNCTION(BlueprintPure) int32 GetNextComboIndex() const
    {
        return ComboIndex;
    }
    UFUNCTION(BlueprintPure) FName GetActiveStrikeName() const
    {
        return ActiveStrike.Name;
    }
    UFUNCTION(BlueprintPure) FName GetLastStrikeName() const
    {
        return LastStrikeName;
    }
    UFUNCTION(BlueprintPure) int32 GetLastStrikeHits() const
    {
        return LastStrikeHits;
    }
    UFUNCTION(BlueprintPure) float GetLastTipReach() const
    {
        return LastTipReach;
    }
    UFUNCTION(BlueprintPure) int32 GetStrikesFinished() const
    {
        return StrikesFinished;
    }
    UFUNCTION(BlueprintPure) bool IsStancePlaying() const;
    // World position of the mesh's head end (its long bounds axis), for the reach receipts.
    UFUNCTION(BlueprintPure) FVector GetTipLocation() const;

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
    // AFS 2026-10-31 (spear item): strike, combo, charge, stance and two-hand grip state.
    FHoverMeleeProfile Profile = FHoverMeleeProfile::Katana();
    FHoverMeleeStrike ActiveStrike;
    float ActiveDamageScale = 1.f, StrikeStart = 0.f, ChainAtTime = 0.f, ComboExpiresAt = 0.f, ChargeStart = 0.f;
    float MaxTipReach = 0.f, LastTipReach = 0.f, TwoHandWeight = 0.f;
    int8 TipLeftLive = -1; // AFS 2026-10-31: which palm the head is on (-1 = the profile's choice), see UpdateTwoHandGrip
    int32 ComboIndex = 0, StrikeHits = 0, LastStrikeHits = 0, StrikesFinished = 0;
    FName LastStrikeName;
    bool bBufferedLight = false, bAttackHeld = false, bHoldIsCharge = false, bCharging = false;
    bool bChargeClipPlaying = false, bStrikeOpen = false, bStanceActive = false;
    FTimerHandle ChainTimer, ChargeTimer, ChargeFreezeTimer, ChargeAutoTimer, StrikeEndTimer;
    FTransform CarryRelative, TwoHandRelative;
    TWeakObjectPtr<USkeletalMeshComponent> GripBody;
    TWeakObjectPtr<class UAnimMontage> StanceMontage;
    FDelegateHandle GripPoseHandle;
    bool PresentStrike(bool bPlayClip = true);
    void ClearSweeps();
    void ScheduleSweep(int32 Index, float Delay);
    void SweepAt(int32 Index);
    void StrikeActor(const FHitResult &Hit);
    bool CanStrike() const;
    void StartStrike(const FHoverMeleeStrike &Strike, float Scale, int32 ComboStep);
    void StartLight();
    void OnChainPoint();
    void FinishStrike();
    void BeginCharge();
    void FreezeCharge();
    void ReleaseHeavy();
    void ResetStrikeState();
    void UpdateStance(AHoverPilot *Pilot);
    void StopStance(AHoverPilot *Pilot);
    void ConfigureTwoHandGrip(AHoverPilot *Pilot);
    void UpdateTwoHandGrip();
    void ReleaseTwoHandGrip();
    bool GetShaft(FVector &Butt, FVector &Axis, float &Length) const;
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
    // AFS 2026-10-31 (spear item): NYC Survival only. The spear is a second pilot-owned
    // AHoverMeleeWeapon, like the katana. DA_NYC_Spear sits on the quickbar (CycleWeapon and the number keys reach
    // it) with no WeaponActorClass, so selecting it holsters the gun; while it is selected the melee input and the
    // trigger drive the spear.
    UFUNCTION(BlueprintPure) bool IsSpearSelected() const
    {
        return bSpearSelected;
    }
    UFUNCTION(BlueprintPure) AHoverMeleeWeapon *GetActiveMelee() const;
    // Quickbar slot holding DA_NYC_Spear, 0 when none.
    UFUNCTION(BlueprintPure) int32 FindSpearSlot() const;
    // Adds DA_NYC_Spear to the inventory at Slot when it is not there yet (proof scripts, later pickups).
    UFUNCTION(BlueprintCallable) bool GiveSpear(int32 Slot = 4);
    void SetSpearTrigger(bool Held);
    FString GetSpearHudText() const;
    void SuspendForRide();
    UFUNCTION(BlueprintPure) AZE_WeaponBase *GetWeapon() const;
    UFUNCTION(BlueprintPure) bool IsReloading() const;
    UFUNCTION(BlueprintPure) FString GetPrompt() const;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_InventoryComponent> Inventory;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_SurvivalComponent> Survival;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_WeaponComponent> Weapons;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UZE_InteractionTraceComponent> Interaction;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AHoverMeleeWeapon> MeleeWeapon;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AHoverMeleeWeapon> SpearWeapon;
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
    UPROPERTY() TObjectPtr<UZE_WeaponDefinition> SpearDefinition;
    bool bSpearSelected = false;
    void UpdateSpearSelection();
};
