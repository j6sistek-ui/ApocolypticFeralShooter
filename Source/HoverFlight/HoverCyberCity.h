#pragma once
#include "CoreMinimal.h"
#include "Survival/ZE_ZombieWaveGameMode.h"
#include "Zombies/ZE_ZombieAIController.h"
#include "Zombies/ZE_ZombieCharacter.h"
#include "Pickups/ZE_PowerUpPickup.h"
#include "UI/ZE_WaveHUDWidget.h"
#include "HoverCyberVariants.h"
#include "HoverCyberCity.generated.h"

// Cyber City uses the vendor wave state machine and assets, with the AFS player.
UCLASS()
class HOVERFLIGHT_API AHoverCyberCityGameMode : public AZE_ZombieWaveGameMode
{
    GENERATED_BODY()
  public:
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void StartWave() override;
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
    UFUNCTION(BlueprintPure) FString GetEncounterLabel() const;
    UFUNCTION(BlueprintPure) UHoverCyberEncounterSettings *GetEncounterSettings() const
    {
        return Encounters;
    }

  protected:
    virtual void ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual UZE_ZombieDataAsset *SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                  const TArray<UZE_ZombieDataAsset *> &Types) override;
    virtual float GetEffectiveSpawnRate() const override;

  private:
    float SpeedBonusUntil = 0;
    float InstaKillUntil = 0;
    int32 Gold = 500;
    int32 ActiveSpawnCount = 0;
    UPROPERTY() TObjectPtr<class UUserWidget> WaveDisplay;
    UPROPERTY() TObjectPtr<UHoverCyberEncounterSettings> Encounters;
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
    UFUNCTION(BlueprintCallable) bool StompImpact();
    UPROPERTY(BlueprintReadOnly) int32 StompCount = 0;
    UPROPERTY(BlueprintReadOnly) int32 StompKnockdowns = 0;
    virtual void BeginPlay() override;
    virtual float TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController,
                             AActor *Causer) override;

  protected:
    virtual void InitializeZombieStats() override;

  private:
    UPROPERTY() TObjectPtr<class UNiagaraSystem> Blood;
    UPROPERTY() TObjectPtr<class USkeletalMeshComponent> Trousers;
    UPROPERTY() TObjectPtr<class USkeletalMeshComponent> Shirt;
    float LastStompTime = -10;
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
  protected:
    virtual void OnOverlapBegin(UPrimitiveComponent *OverlappedComp, AActor *OtherActor, UPrimitiveComponent *OtherComp,
                                int32 OtherBodyIndex, bool bFromSweep, const FHitResult &SweepResult) override;
};
