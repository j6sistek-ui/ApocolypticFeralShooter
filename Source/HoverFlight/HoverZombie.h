#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "HoverZombie.generated.h"
class UAnimSequence;
class UNiagaraSystem;
class AHoverZombieRange;

UCLASS()
class HOVERFLIGHT_API AHoverZombie : public ACharacter
{
    GENERATED_BODY()
  public:
    AHoverZombie();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual float TakeDamage(float Damage, const FDamageEvent &Event, AController *EventInstigator,
                             AActor *Causer) override;
    UFUNCTION(BlueprintPure) bool IsDead() const
    {
        return bDead;
    }
    UFUNCTION(BlueprintPure) float GetHealth() const
    {
        return Health;
    }
    UPROPERTY() TObjectPtr<AHoverZombieRange> Range;

  private:
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> Trousers;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> Shirt;
    UPROPERTY() TObjectPtr<UAnimSequence> Walk;
    UPROPERTY() TObjectPtr<UAnimSequence> Idle;
    UPROPERTY() TObjectPtr<UNiagaraSystem> Blood;
    FVector Home, WanderDirection;
    float Health = 100.f, WanderTime = 0;
    bool bDead = false, bWalking = false;
};

UCLASS()
class HOVERFLIGHT_API AHoverZombieRange : public AActor
{
    GENERATED_BODY()
  public:
    AHoverZombieRange();
    virtual void Tick(float DeltaSeconds) override;
    UFUNCTION(BlueprintPure) int32 GetKills() const
    {
        return Kills;
    }
    UFUNCTION(BlueprintPure) int32 GetAliveCount() const;
    UFUNCTION(BlueprintPure) int32 GetBloodHits() const
    {
        return BloodHits;
    }
    void RegisterKill()
    {
        ++Kills;
    }
    void RegisterBloodHit()
    {
        ++BloodHits;
    }

  private:
    UPROPERTY() TArray<TObjectPtr<AHoverZombie>> Zombies;
    FRandomStream Random;
    FVector Origin;
    float SpawnTime = 0;
    int32 Kills = 0, BloodHits = 0, SpawnIndex = 0;
    bool bInitialized = false;
    bool SpawnZombie();
};
