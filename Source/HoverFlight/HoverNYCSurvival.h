#pragma once
#include "CoreMinimal.h"
#include "HoverCyberCity.h"
#include "HoverNYCSurvival.generated.h"

class UAudioComponent;
class UHoverSpawnDirector;
class USoundBase;
struct FZE_WaveConfig;

// NYC - Survival (menu index 4): third-person, mortal wave mode on L_NYC_Survival.
// Inherits IHoverTestLevelPolicy from the Cyber base; it must not list it again.
UCLASS()
class HOVERFLIGHT_API AHoverNYCSurvivalGameMode : public AHoverCyberCityGameMode
{
    GENERATED_BODY()
  public:
    AHoverNYCSurvivalGameMode();
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void StartWave() override;
    virtual AActor *ChoosePlayerStart_Implementation(AController *Player) override;
    virtual void OnZombieSpawned(AHoverCyberZombie &Zombie) override;
    virtual bool RelocateZombie(AHoverCyberZombie &Zombie) override;
    virtual FString GetEncounterLabel() const override;
    virtual float GetRoundHealthScale(int32 Wave) const override;
    virtual float GetRoundDamageScale(int32 Wave) const override;

    // IHoverTestLevelPolicy
    virtual bool SpawnsTestBike() const override
    {
        return false;
    }
    virtual bool SpawnsTestTruck() const override
    {
        return true;
    }
    // Stage 1: the truck is parked set dressing.
    virtual bool AllowsTruckMount() const override
    {
        return false;
    }
    virtual bool ForcesThirdPerson() const override
    {
        return true;
    }
    virtual bool ForcesMortal() const override
    {
        return true;
    }
    virtual float GetPlayerMaxHealth() const override
    {
        return 150.f;
    }
    virtual bool EnablesEnhancedGunFeel() const override
    {
        return true;
    }
    virtual bool AllowsSandboxReset() const override
    {
        return false;
    }
    virtual bool UsesSurvivalRules() const override
    {
        return true;
    }

    // Section 2 Â§5 game over: zombies stop, a 2 s slow-motion death cam, then the vendor death widget
    // and RestartLevel policy. Called by AHoverPilot::TakeDamage at 0 HP instead of the sandbox reset.
    void BeginGameOver();
    bool IsGameOver() const
    {
        return bGameOver;
    }

    // Python assertions only.
    UFUNCTION(BlueprintPure) bool IsSurvivalMode() const
    {
        return true;
    }
    UFUNCTION(BlueprintPure) int32 GetPendingBossCount() const
    {
        return PendingBosses.Num();
    }
    UFUNCTION(BlueprintPure) int32 GetBossesReleased() const
    {
        return BossesReleased;
    }
    UFUNCTION(BlueprintPure) bool IsBossAlive() const;
    UFUNCTION(BlueprintPure) EHoverRoundKind GetRoundKind(int32 Wave) const;
    UFUNCTION(BlueprintPure) int32 GetRoundQuota() const
    {
        return RoundQuota;
    }
    UFUNCTION(BlueprintPure) int32 GetSpawnedThisRound() const
    {
        return SpawnedThisRound;
    }
    UFUNCTION(BlueprintPure) UHoverNYCEncounterSettings *GetNYCSettings() const
    {
        return NYC;
    }
    UHoverSpawnDirector *GetSpawnDirector() const
    {
        return Director;
    }

  protected:
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                  const TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual float GetEffectiveSpawnRate() const override;
    UFUNCTION() void OnRoundStateChanged(int32 Wave, EZE_WaveState State, float Timer);
    UFUNCTION() void FinishDeathCam();

  private:
    static const FZE_WaveConfig *FindRow(const UZE_WaveGameModeSettings *Settings, int32 Wave);
    // Arms the director once kills reach BossTriggerFraction x quota; a second boss on a row with
    // SecondEntersAtFraction waits for the lead boss's health (06.4 boss release).
    void UpdateBossArming();
    UPROPERTY() TObjectPtr<UHoverSpawnDirector> Director;
    UPROPERTY() TObjectPtr<UHoverNYCEncounterSettings> NYC;
    // Spawn ordinal -> Brute/Kid definition for this round (keyed by our own ordinal,
    // because the vendor SpawnIndex is killed + alive and repeats after kills).
    UPROPERTY() TMap<int32, TObjectPtr<UZE_ZombieDataAsset>> ScheduledSpecials;
    int32 RoundQuota = 0;
    int32 SpawnedThisRound = 0;
    // Set by SelectZombieData, consumed by the zombie's OnZombieSpawned in the same vendor spawn.
    bool bVendorSpawnPending = false;
    // Boss round state (06.4). Pending entries are stored reversed so Pop() releases the listed
    // order; an additive entry (boss or boss add) costs no standard ordinal.
    UPROPERTY() TArray<TObjectPtr<UZE_ZombieDataAsset>> PendingBosses;
    // AFS 2026-10-31 (zombie diversity): standards come from a shuffled deck that persists across rounds,
    // so every roster type shows up before any repeats, whatever the round quota.
    UPROPERTY() TArray<TObjectPtr<UZE_ZombieDataAsset>> StandardDeck;
    UPROPERTY() TObjectPtr<UZE_ZombieDataAsset> LastStandardDrawn;
    UZE_ZombieDataAsset *DrawStandard(const TArray<UZE_ZombieDataAsset *> &Types);
    TWeakObjectPtr<AHoverCyberZombie> LeadBoss;
    int32 BossesReleased = 0;
    float SecondEntersAtFraction = 0.f;
    bool bAdditiveSpawnPending = false;
    bool bGameOver = false;
    FTimerHandle DeathCamTimer;
    // Crowd ambience (audio additions): one looping 2D bed from round start to game over or EndPlay.
    USoundBase *ChooseAmbience() const;
    void UpdateAmbience();
    // Fades the current bed out (it destroys itself afterwards), or stops it at once for 0.
    void StopAmbience(float FadeSeconds);
    UPROPERTY() TObjectPtr<UAudioComponent> Ambience;
    UPROPERTY() TObjectPtr<USoundBase> AmbienceSound;
    UPROPERTY() TObjectPtr<UAudioComponent> WeatherAmbience; // audio pass 2026-10-31
    float AmbienceCheckTimer = 0.f;
    bool bAmbienceActive = false;
};
