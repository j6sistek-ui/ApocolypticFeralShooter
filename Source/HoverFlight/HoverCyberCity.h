#pragma once
#include "CoreMinimal.h"
#include "Survival/ZE_ZombieWaveGameMode.h"
#include "Zombies/ZE_ZombieAIController.h"
#include "Zombies/ZE_ZombieCharacter.h"
#include "Pickups/ZE_PowerUpPickup.h"
#include "Interaction/ZE_PickupBase.h"
#include "UI/ZE_WaveHUDWidget.h"
#include "World/ZE_ZombieSpawnPoint.h"
#include "HoverCyberVariants.h"
#include "HoverTestLevelPolicy.h"
#include "HoverPickupFeedback.h"
#include "NavigationSystem.h"
#include "HoverCyberCity.generated.h"

// Lakeside's large creatures need full-height routes around its raised porches.
// A world-specific navigation class keeps other test maps' agent profiles intact.
UCLASS()
class HOVERFLIGHT_API UHoverLakesideNavigationSystem : public UNavigationSystemV1
{
    GENERATED_BODY()
  public:
    virtual void PostInitProperties() override;
};

USTRUCT(BlueprintType)
struct FHoverZombieTuning
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Health = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Speed = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Count = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float SpawnInterval = 1.f;
};

class AHoverCyberZombie;

// Cyber City uses the vendor wave state machine and assets, with the AFS player.
// The level policy keeps its defaults here (all rides, the saved invincibility, first person).
UCLASS()
class HOVERFLIGHT_API AHoverCyberCityGameMode : public AZE_ZombieWaveGameMode, public IHoverTestLevelPolicy
{
    GENERATED_BODY()
  public:
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void StartWave() override;
    UPROPERTY(BlueprintReadOnly) FHoverZombieTuning Tuning;
    UFUNCTION(BlueprintCallable) void ApplyTuning(FHoverZombieTuning Value);
    void RecordSpawn(const FVector &Position);
    // Called once by every AHoverCyberZombie at the end of BeginPlay (inside the vendor
    // FinishSpawningActor, with ZombieData assigned). The base records the spawn position.
    virtual void OnZombieSpawned(AHoverCyberZombie &Zombie);
    // Moves a live zombie to a fresh spawner instead of destroying it. The base has no
    // director and returns false, so the caller keeps the engine default.
    virtual bool RelocateZombie(AHoverCyberZombie &Zombie)
    {
        return false;
    }
    // True when a subclass places and paces spawns itself (NYC Survival). Cyber City and
    // Lakeside keep the original per-frame spawn gate.
    bool UsesExternalSpawnDirector() const
    {
        return bExternalSpawnDirector;
    }
    // Round scaling consumed by the zombie AI and AHoverPilot::TakeDamage. The base returns
    // the wave asset's multipliers, exactly as before.
    UFUNCTION(BlueprintPure) virtual float GetRoundHealthScale(int32 Wave) const;
    UFUNCTION(BlueprintPure) virtual float GetRoundDamageScale(int32 Wave) const;
    UFUNCTION(BlueprintPure) int32 GetActiveSpawnCount() const
    {
        return ActiveSpawnCount;
    }
    UFUNCTION(BlueprintPure) bool IsWaveHUDVisible() const;
    UFUNCTION(BlueprintPure) float GetSpeedBonus() const;
    UFUNCTION(BlueprintPure) bool HasInstaKill() const;
    UFUNCTION(BlueprintPure) int32 GetGold() const;
    void AddGold(int32 Amount);
    void ActivatePowerUp(EZE_PowerUpType Type, float Duration);
    UFUNCTION(BlueprintPure) virtual FString GetEncounterLabel() const;
    UFUNCTION(BlueprintPure) UHoverCyberEncounterSettings *GetEncounterSettings() const
    {
        return Encounters;
    }

  protected:
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                  const TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual float GetEffectiveSpawnRate() const override;

    int32 ActiveSpawnCount = 0;
    UPROPERTY() TObjectPtr<UHoverCyberEncounterSettings> Encounters;
    TMap<TWeakObjectPtr<AActor>, float> SpawnLastUsed;
    FVector LastSpawnPosition = FVector::ZeroVector;
    TMap<TWeakObjectPtr<AActor>, bool> ReachableSpawns;
    FVector LastNavigationTarget = FVector::ZeroVector;
    float NextReachabilityCheck = 0;
    // When true, Tick skips the per-frame spawn gate and always runs the vendor tick.
    bool bExternalSpawnDirector = false;
    bool CanReachPlayer(AActor *Spawn, APawn *Player);

  public:
    // Uncached complete-path test from a spawn point or zombie to a target location.
    // Public so the NYC spawn director can share the base's navigation query.
    bool CanReachPoint(AActor *From, const FVector &Target, const FVector &TargetExtent,
                       const UObject *Querier = nullptr, FNavPathSharedPtr *OutPath = nullptr) const;

  private:
    float SpeedBonusUntil = 0;
    float InstaKillUntil = 0;
    int32 Gold = 500;
    UPROPERTY() TObjectPtr<class UUserWidget> WaveDisplay;
    bool bLakeside = false;
};

UCLASS()
class HOVERFLIGHT_API AHoverCyberZombieAI : public AZE_ZombieAIController
{
    GENERATED_BODY()
  public:
    AHoverCyberZombieAI();
    virtual void OnPossess(APawn *InPawn) override;
    virtual void Tick(float DeltaSeconds) override;

  private:
    UFUNCTION() void OnPlayerDetected(AActor *Actor, FAIStimulus Stimulus);
};

UCLASS()
class HOVERFLIGHT_API AHoverCyberZombie : public AZE_ZombieCharacter
{
    GENERATED_BODY()
  public:
    AHoverCyberZombie();
    UFUNCTION(BlueprintPure) EHoverZombieRole GetRole() const;
    bool NeedsContactPose() const
    {
        return bIsAttacking || bIsDead;
    }
    UFUNCTION(BlueprintCallable) bool StompImpact();
    bool CanOccupyCapsuleAt(const FVector &Center) const;
    UPROPERTY(BlueprintReadOnly) int32 StompCount = 0;
    UPROPERTY(BlueprintReadOnly) int32 StompKnockdowns = 0;
    // Spawn-time state written by the game mode's OnZombieSpawned. HealthScale 0 means
    // "use the mode's round lookup" and SpeedTier 0 means "use the data asset speeds",
    // which is what Cyber City and Lakeside zombies keep.
    UPROPERTY(BlueprintReadOnly) float HealthScale = 0.f;
    UPROPERTY(BlueprintReadOnly) float SpeedTier = 0.f;
    UPROPERTY(BlueprintReadOnly) int32 RelocationCount = 0;
    UPROPERTY(BlueprintReadOnly) float SpawnTime = 0.f;
    TWeakObjectPtr<AZE_ZombieSpawnPoint> SpawnerUsed;
    float UnreachableSince = -1.f;
    bool IsDead() const
    {
        return bIsDead;
    }
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void FellOutOfWorld(const UDamageType &DamageType) override;
    virtual float TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController,
                             AActor *Causer) override;

    // NYC Section 4 Â§5 hooks. The base bodies reproduce the previous behaviour exactly: the DA
    // StompInterval (default .8 s), the Insta-Kill one-shot, and the vendor gold roll unless the
    // definition authors KillPoints.
    virtual float GetStompInterval() const;
    virtual void ModifyIncomingDamage(float &Damage, const FDamageEvent &Event, AController *EventController,
                                      AActor *Causer, const FHitResult &Hit);
    virtual void OnKilledBy(AController *EventController, AActor *Causer, const FHitResult &Hit);

  protected:
    virtual void InitializeZombieStats() override;
    UPROPERTY() TObjectPtr<class UNiagaraSystem> Blood;
    float LastStompTime = -10;

  private:
    UPROPERTY() TObjectPtr<class USkeletalMeshComponent> Trousers;
    UPROPERTY() TObjectPtr<class USkeletalMeshComponent> Shirt;
};

UCLASS()
class HOVERFLIGHT_API UHoverCyberWaveHUD : public UZE_WaveHUDWidget
{
    GENERATED_BODY()
  protected:
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry &Geometry, float DeltaTime) override;

  private:
    UPROPERTY() TObjectPtr<class UTextBlock> EncounterText;
};

UCLASS()
class HOVERFLIGHT_API AHoverCyberPowerUp : public AZE_PowerUpPickup
{
    GENERATED_BODY()
  public:
    // AFS 2026-10-31 (owner playtest item 1): NYC Survival presentation of the Nuke (banner, flash, blast,
    // shockwave, shake, rumble, distance ripple, optional slow motion). Owner-editable on BP_CyberPower_Nuke.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Presentation") FHoverNukePresentation NukePresentation;

  protected:
    virtual void OnOverlapBegin(UPrimitiveComponent *OverlappedComp, AActor *OtherActor, UPrimitiveComponent *OtherComp,
                                int32 OtherBodyIndex, bool bFromSweep, const FHitResult &SweepResult) override;
};

// Keep vendor inventory/interaction behavior, with a readable grounded ammo drop.
UCLASS()
class HOVERFLIGHT_API AHoverAmmoPickup : public AZE_PickupBase
{
    GENERATED_BODY()
  public:
    // AFS 2026-10-31 (owner playtest item 6): readable ammo drop in NYC Survival (outline, glint, bob and spin,
    // walk-over pickup, pickup sound, "+N AMMO" toast). Members defined in HoverPickupFeedback.cpp.
    AHoverAmmoPickup(const FObjectInitializer &ObjectInitializer = FObjectInitializer::Get());
    virtual void Tick(float DeltaSeconds) override;
    virtual void Interact_Implementation(APawn *InteractingPawn) override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Presentation") FHoverAmmoPresentation Presentation;

  private:
    void SetupPresentation();
    UPROPERTY() TObjectPtr<class UPointLightComponent> Glint;
    FVector MeshBase = FVector::ZeroVector;
    FRotator MeshBaseRotation = FRotator::ZeroRotator;
    float PresentAge = 0.f;
    bool bPresentationChecked = false;
    bool bPresentationActive = false;
    bool bPickedUp = false;

  protected:
    virtual void BeginPlay() override;
};
