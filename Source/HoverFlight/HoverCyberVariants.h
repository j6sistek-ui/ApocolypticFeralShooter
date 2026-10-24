#pragma once
#include "CoreMinimal.h"
#include "Zombies/ZE_ZombieSettings.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "HoverCyberVariants.generated.h"

UENUM(BlueprintType)
enum class EHoverZombieRole : uint8
{
    Standard,
    Brute,
    Kid
};

// Local definitions retain the purchased combat, loot and animation settings.
UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverCyberZombieDefinition : public UZE_ZombieDataAsset
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Appearance")
    TObjectPtr<class USkeletalMesh> AppearanceMesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Appearance")
    EHoverZombieRole Role = EHoverZombieRole::Standard;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Appearance", meta = (ClampMin = "50"))
    float Height = 180;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Appearance", meta = (ClampMin = "10"))
    float CapsuleRadius = 34;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Movement", meta = (ClampMin = "1"))
    float MaximumRunSpeed = 850;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stomp", meta = (ClampMin = "100"))
    float StompRadius = 400;
};

UCLASS()
class HOVERFLIGHT_API UHoverBruteStompNotify : public UAnimNotify
{
    GENERATED_BODY()
  public:
    virtual void Notify(USkeletalMeshComponent *MeshComp, UAnimSequenceBase *Animation,
                        const FAnimNotifyEventReference &EventReference) override;
};

UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverCyberEncounterSettings : public UDataAsset
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Enemies")
    TArray<TObjectPtr<UHoverCyberZombieDefinition>> Standards;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Enemies")
    TObjectPtr<UHoverCyberZombieDefinition> Brute;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Enemies")
    TObjectPtr<UHoverCyberZombieDefinition> Kid;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "11"))
    int32 BruteFirstWave = 12;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "1"))
    int32 BruteInterval = 2;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Swarm", meta = (ClampMin = "1"))
    int32 SwarmFirstWave = 5;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Swarm", meta = (ClampMin = "1"))
    int32 SwarmInterval = 10;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Swarm", meta = (ClampMin = "1", ClampMax = "24"))
    int32 SwarmCount = 8;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Swarm", meta = (ClampMin = "0.1"))
    float SwarmSpawnInterval = .65f;
    UFUNCTION(BlueprintPure) bool IsSwarmWave(int32 Wave) const
    {
        return Kid && SwarmInterval > 0 && Wave >= SwarmFirstWave && (Wave - SwarmFirstWave) % SwarmInterval == 0;
    }
    UFUNCTION(BlueprintPure) bool IsBruteWave(int32 Wave) const
    {
        return Brute && !IsSwarmWave(Wave) && BruteInterval > 0 && Wave >= FMath::Max(11, BruteFirstWave) &&
               (Wave - BruteFirstWave) % BruteInterval == 0;
    }
};
