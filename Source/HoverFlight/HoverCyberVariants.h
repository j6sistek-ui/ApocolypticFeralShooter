#pragma once
#include "CoreMinimal.h"
#include "Zombies/ZE_ZombieSettings.h"
#include "Animation/AnimNotifies/AnimNotify.h"
#include "HoverCyberVariants.generated.h"

class USoundBase;
class UAnimInstance;
class UAnimMontage;
class UMaterialInterface;
class UNiagaraSystem;

// Boss (Stage 1) and Riot (Stage 2) follow Kid; UENUMs serialize by name, so existing assets load unchanged.
UENUM(BlueprintType)
enum class EHoverZombieRole : uint8
{
    Standard,
    Brute,
    Kid,
    Boss,
    Riot
};

UENUM(BlueprintType)
enum class EHoverSpecialKind : uint8
{
    None,
    StoneGolem,
    GiantKid
};

// Boss phase row (NYC Section 4 Â§3). Data only in this pass: nothing evaluates phases yet.
USTRUCT(BlueprintType)
struct FHoverBossPhase
{
    GENERATED_BODY()
    // Starts at or below this health fraction.
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") float HealthFraction = .5f;
    // 0 = permanent.
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") float Duration = 0.f;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") FName DetachPartComponent;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") FName WeakPointBone;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") float StaggerSeconds = 1.f;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") TSoftObjectPtr<UAnimMontage> StaggerMontage;
    // 0 = keep MaximumRunSpeed.
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") float SpeedOverride = 0.f;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") float CooldownScale = 1.f;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") bool bEnrage = false;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") bool bUnlockSpecial = false;
    UPROPERTY(EditAnywhere, Category = "AFS|Boss") FString Banner;
};

UENUM(BlueprintType)
enum class EHoverRoundKind : uint8
{
    Normal,
    BruteDebut,
    Heavy,
    Horde,
    Boss
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

    // crowd-ai additions (NYC Section 4). Every default reproduces today's behaviour: the base zombie keeps
    // Height * .5 and the role yaw/acceleration while these are 0, and only AHoverNYCZombie and
    // AHoverNYCZombieAI read the crowd and hit fields, so Cyber City and Lakeside assets are unaffected.
    // 0 = Height * .5. The engine keeps the half-height at least the radius (a Kid crawler is 23/23).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Appearance", meta = (ClampMin = "0"))
    float CapsuleHalfHeight = 0;
    // 0 = role default (Brute 220, otherwise 600).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Movement", meta = (ClampMin = "0"))
    float RotationYaw = 0;
    // 0 = role default (Kid 2600, otherwise 1400).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Movement", meta = (ClampMin = "0"))
    float MaxAcceleration = 0;
    // Queue ring distance from the target, outside the inner attack ring.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Crowd", meta = (ClampMin = "50"))
    float QueueRingRadius = 260;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Crowd", meta = (ClampMin = "0"))
    float SeparationWeight = 10;
    // Counts toward the two-heavy limit on the inner ring (Brute and Boss roles always do).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Crowd")
    bool bHeavySlot = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit")
    bool bFlinchOnHit = true;
    // A hit must deal at least this fraction of MaxHealth to play a hit-reaction montage.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit", meta = (ClampMin = "0", ClampMax = "1"))
    float FlinchDamageFraction = .10f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit", meta = (ClampMin = "0"))
    float FlinchMontageCooldown = .35f;
    // A swing can be flinch-cancelled only during its first WindupSeconds.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit", meta = (ClampMin = "0"))
    float WindupSeconds = .5f;
    // end crowd-ai additions

    // Remaining Section 4 Â§3 fields. Every default reproduces today's behaviour (0 / false = the
    // existing code path); the readers are listed per field. Fields marked "data only" are not
    // consumed yet and are recorded as deferred in Docs/VALIDATION.txt.
    // Data only: speed inside 8 m (golem 240).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    float CloseWalkSpeed = 0.f;
    // Data only (Stage 2 armored).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed")
    bool bNeverSprints = false;
    // Data only (Stage 2).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Armor", meta = (ClampMin = "0"))
    float ArmorHP = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Armor", meta = (ClampMin = "0"))
    float ArmorExplosiveMultiplier = .5f;
    // Data only: gore routes.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit")
    bool bCanBeDismembered = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit")
    bool bCanCrawl = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Hit")
    bool bAlwaysCrawl = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    EHoverSpecialKind SpecialKind = EHoverSpecialKind::None;
    // Data only: phase evaluation is a later slice.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TArray<FHoverBossPhase> BossPhases;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TMap<FName, TSoftObjectPtr<UAnimMontage>> SpecialMontages;
    // Data only: Giant Kid .3 Rise threshold.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0", ClampMax = "1"))
    float SecondLifeFraction = 0.f;
    // Stomp gate (AHoverCyberZombie::StompImpact): the Brute role always stomps; any other role needs this.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    bool bUsesStomp = false;
    // > 0: StompImpact applies 30 x this inside StompRadius instead of the vendor sweep.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0"))
    float StompDamageMultiplier = 0.f;
    // Data only: special-timer cooldown (golem 4, Giant Kid 2.5).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0"))
    float StompCooldown = 0.f;
    // Minimum re-arm between two StompImpact calls (replaces the former 0.8 s literal).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0"))
    float StompInterval = .8f;
    // Applied with SetAnimInstanceClass right after the appearance mesh is set.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Anim")
    TSubclassOf<UAnimInstance> AnimClassOverride;
    // Data only: vocal routes.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TSoftObjectPtr<USoundBase> SlowTierVocal;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TSoftObjectPtr<USoundBase> FastTierVocal;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TSoftObjectPtr<USoundBase> SightRoar;
    // Kill reward (AHoverCyberZombie::OnKilledBy). 0 keeps the vendor MinGoldReward..MaxGoldReward roll, so
    // Cyber City and Lakeside are unchanged; NYC assets author 90 / 115 / 105.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Points", meta = (ClampMin = "0"))
    int32 KillPoints = 0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Points", meta = (ClampMin = "0"))
    int32 HeadshotKillPoints = 0;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Points", meta = (ClampMin = "0"))
    int32 MeleeKillPoints = 0;

    // audio additions. Defaults are set in HoverNYCSurvival.cpp (this header has no .cpp).
    UHoverCyberZombieDefinition();
    // Data only: looping feeding beds (Audio/NYC/Zombies/Feeding) for the no-target Feast idle, which no code
    // plays yet. The consumer is the no-target branch of AHoverNYCZombieAI::Tick (Section 4 SelectChaseTarget
    // null): pick one at random, SpawnSoundAttached it to the mesh while feasting, stop it when a target
    // returns or on death. Nothing reads this field, so Cyber City and Lakeside assets are unaffected.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TArray<TSoftObjectPtr<USoundBase>> FeedingSounds;
    // end audio additions

    // zombie-diversity additions (2026-10-31). Read only by AHoverNYCZombie, so Cyber City, Lakeside and
    // PostApo assets are unaffected. Empty arrays / null pointers keep the existing behaviour.
    // One entry is picked per zombie and applied to SkinMaterialSlot.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    TArray<TObjectPtr<UMaterialInterface>> SkinMaterials;
    // NAME_None = material slot 0.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    FName SkinMaterialSlot = NAME_None;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    bool bRandomizeMorphTargets = false;
    // Empty = every morph target on the mesh.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    TArray<FName> MorphTargetNames;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety", meta = (ClampMin = "0", ClampMax = "1"))
    float MorphTargetMax = .8f;
    // Uniform actor scale range rolled per zombie (bosses use half the spread). The default (1, 1) changes
    // nothing; AuthorZombieDiversity.py writes the ranges on the NYC roster definitions.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    FVector2D ScaleJitter = FVector2D(1.f, 1.f);
    // Multiplier on the mesh GlobalAnimRateScale rolled per zombie. Default (1, 1) = unchanged.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    FVector2D AnimRateJitter = FVector2D(1.f, 1.f);
    // AFS 2026-10-31 (review): the mesh yaw on the capsule that puts this body's animated toes on actor +X,
    // measured once per definition at authoring time (AuthorZombieDiversity.py samples the walk cycle retargeted
    // onto the body). Applied at BeginPlay only when bAlignMeshYaw is set, so unauthored definitions (bosses,
    // Cyber City, Lakeside) keep their mesh rotation.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety")
    bool bAlignMeshYaw = false;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Variety", meta = (EditCondition = "bAlignMeshYaw"))
    float MeshYawOffset = 0.f;

    // Empty = the vendor DeathMontage.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Anim")
    TArray<TObjectPtr<UAnimMontage>> DeathMontageVariants;
    // Played once on first sight of the player (slot DefaultSlot or UpperBody of ABP_ZombieMaster).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Anim")
    TObjectPtr<UAnimMontage> SightRoarMontage;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Anim", meta = (ClampMin = "0", ClampMax = "1"))
    float SightRoarChance = .4f;

    // Per-zombie voice (UHoverZombieVoice budget). Any of these set also mutes the vendor
    // AttackSound / DeathSound so the two never double up.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> IdleVocals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> ChaseVocals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> AttackVocals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> PainVocals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> DeathVocals;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    TArray<TObjectPtr<USoundBase>> FootstepSounds;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    FVector2D VoicePitch = FVector2D(.95f, 1.05f);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice", meta = (ClampMin = "0"))
    float VoiceVolume = 1.f;
    // Seconds between idle / chase vocals (jittered per call).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice")
    FVector2D VocalInterval = FVector2D(3.f, 8.f);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice", meta = (ClampMin = "0"))
    float FootstepVolume = .6f;
    // Centimetres of travel per step, scaled by the zombie's actor scale.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Voice", meta = (ClampMin = "10"))
    float FootstepStride = 75.f;

    // Null keeps the shared NS_NS1_BloodShot hit path (and no death pool).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Blood")
    TObjectPtr<UNiagaraSystem> HitBlood;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Blood")
    TObjectPtr<UNiagaraSystem> HeadshotBlood;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Blood")
    TObjectPtr<UNiagaraSystem> DeathBlood;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Blood", meta = (ClampMin = "0"))
    float BloodScale = 1.f;

    // True when any voice array is authored.
    bool HasCustomVoice() const
    {
        return IdleVocals.Num() || ChaseVocals.Num() || AttackVocals.Num() || PainVocals.Num() || DeathVocals.Num();
    }
    // end zombie-diversity additions
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
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Swarm", meta = (ClampMin = "1", ClampMax = "80"))
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

// One boss round (NYC Section 3 06.4). Bosses enter in listed order; a Brute in the list is an
// additive boss add released with the boss. SecondEntersAtFraction > 0 holds the second boss
// until the first one's health drops to that fraction (or it dies).
USTRUCT(BlueprintType)
struct FHoverBossRound
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "1"))
    int32 Round = 13;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TArray<TObjectPtr<UHoverCyberZombieDefinition>> Bosses;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0", ClampMax = "1"))
    float SecondEntersAtFraction = 0.f;
};

// NYC Survival data home. Every pacing, placement and endurance number is data; the
// R1-30 curves live in the DA_NYCWaves CustomWaves rows. Cyber City and Lakeside never read it.
UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverNYCEncounterSettings : public UHoverCyberEncounterSettings
{
    GENERATED_BODY()
  public:
    // Boss rosters (Stage 1, both Role Boss). Null pointers disable the rows that name them.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TObjectPtr<UHoverCyberZombieDefinition> StoneGolem;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TObjectPtr<UHoverCyberZombieDefinition> GiantKid;
    // Optional Stage 2 heavy-round elite (Role Brute, never a boss); off by default.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute")
    TObjectPtr<UHoverCyberZombieDefinition> AlphaBrute;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute")
    bool bAlphaBruteElite = false;
    // Authored rows (R13 golem, R19 Giant Kid, R27 both at .5). Rounds on the 33 + 6k cycle are generated.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss")
    TArray<FHoverBossRound> BossRounds;
    // Kills this round, as a fraction of the quota, that release the first boss.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "0", ClampMax = "1"))
    float BossTriggerFraction = .4f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "1"))
    int32 BossCycleFromRound = 33;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Boss", meta = (ClampMin = "1"))
    int32 BossCycleInterval = 6;
    // The authored row for Round, or the generated 33 + 6k row (a horde round shifts it one later).
    // The returned pointer is valid until the next call.
    const FHoverBossRound *FindBossRound(int32 Round) const;
    UFUNCTION(BlueprintPure) bool IsBossRound(int32 Round) const
    {
        return FindBossRound(Round) != nullptr;
    }
    UFUNCTION(BlueprintPure) bool IsBossDefinition(const UZE_ZombieDataAsset *Definition) const;

    // Pacing: SI(r) = max(Floor, Base * Decay^(r-1)); credit pressure raises or lowers the rate.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.05"))
    float SpawnIntervalBase = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.05"))
    float SpawnIntervalFloor = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1", ClampMax = "1"))
    float SpawnIntervalDecay = .95f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.05"))
    float HordeIntervalBase = .65f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.05"))
    float HordeIntervalFloor = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    int32 CatchUpBelowAlive = 8;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1"))
    float CatchUpPressure = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1"))
    float IdlePressure = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    float IdleRadius = 2500.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1"))
    float CrowdPressure = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "1"))
    int32 CrowdCount = 4;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    float CrowdRadius = 800.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1"))
    float RateJitterMin = .85f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0.1"))
    float RateJitterMax = 1.15f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    float StallRelaxSeconds = 4.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    float StallWarnSeconds = 12.f;
    // 1 = the vendor's single spawn per tick. Higher values re-enter the vendor tick (off by default).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "1", ClampMax = "4"))
    int32 MaxSpawnsPerTick = 1;
    // 0 = use DA MaxConcurrentZombies only. Performance fallback, for example 16.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Pacing", meta = (ClampMin = "0"))
    int32 ConcurrentSoftCap = 0;

    // Placement: 2D distance band to the player target, off-screen and occupancy rules.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float NearMin = 1400.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float BandInner = 2000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float BandOuter = 6000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float FarMax = 10000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0", ClampMax = "1"))
    float EdgeWeight = .3f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0", ClampMax = "1"))
    float OccludedWeight = .8f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float CooldownMin = 4.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    int32 RecentCount = 3;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float PlayerClearance = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float FreshZombieClearance = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Placement", meta = (ClampMin = "0"))
    float JitterRadius = 250.f;

    // Stragglers are relocated to a fresh spawner, never destroyed (Stage 1).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stragglers", meta = (ClampMin = "0"))
    float FarDistance = 12000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stragglers", meta = (ClampMin = "0"))
    float FarMinAge = 8.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stragglers", meta = (ClampMin = "0"))
    float NoPathSeconds = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stragglers", meta = (ClampMin = "0"))
    float HiddenDistance = 6000.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Stragglers", meta = (ClampMin = "0"))
    float HiddenSeconds = 20.f;

    // Endurance: rounds without a DA_NYCWaves row (R31+ by design).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "1"))
    int32 EnduranceFromRound = 31;
    // H(30), in HP: the last authored row's health that the endurance steps add to.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "1"))
    int32 EnduranceBaseHP = 3500;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "0"))
    int32 HealthStepTo40 = 800;
    // Last round that adds HealthStepTo40; later rounds add HealthStep.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "1"))
    int32 HealthStepUntilRound = 40;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "0"))
    int32 HealthStep = 1000;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "1"))
    int32 HealthCapHP = 25000;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "1"))
    int32 CountBase = 24;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "0"))
    int32 CountQuadPercent = 9;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Endurance", meta = (ClampMin = "0"))
    float DamageScaleLate = 2.5f;

    // Horde rounds use the inherited SwarmFirstWave/SwarmInterval schedule and the Kid only.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Horde", meta = (ClampMin = "1"))
    int32 HordeBase = 10;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Horde", meta = (ClampMin = "0"))
    int32 HordePerRound = 2;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Horde", meta = (ClampMin = "1"))
    int32 HordePackSize = 4;
    // 0 = off. 48 is the performance fallback.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Horde", meta = (ClampMin = "0"))
    int32 HordeCountCap = 0;

    // Heavy rounds use the inherited BruteFirstWave/BruteInterval schedule.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "1"))
    int32 BruteDebutWave = 8;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "1"))
    int32 BruteCountCap = 4;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "1"))
    int32 BruteCountDivisor = 6;
    // Spawn-order fractions of the round quota for each heavy-round Brute.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute")
    TArray<float> BrutePlacement = {.25f, .5f, .75f, .9f};
    // Spawn-order fraction for a round with exactly one Brute (the R8 debut).
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Brute", meta = (ClampMin = "0", ClampMax = "1"))
    float LoneBrutePlacement = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Kid", meta = (ClampMin = "1"))
    int32 KidBleedFromRound = 21;

    // Standard speed roll: K in [RollPerRound * r, + RollWindow]; R1 rolls from 0.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 RollPerRound = 4;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 RollWindow = 35;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 WalkerMaxRoll = 35;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 RunnerMaxRoll = 70;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "1"))
    float WalkerSpeed = 180.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "1"))
    float RunnerSpeed = 400.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "1"))
    float SprinterSpeed = 600.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    float KidSpeedTier = 700.f;
    // After this round, the last few Standards alive in a round become sprinters.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 ForcedSprintAfterRound = 3;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Speed", meta = (ClampMin = "0"))
    int32 ForcedSprintersAtEnd = 3;

    // audio additions. Crowd ambience, one looping 2D bed played by AHoverNYCSurvivalGameMode from round
    // start to game over and re-picked every AmbienceCheckSeconds with an AmbienceFadeSeconds cross-fade.
    // Horde rounds play HordeAmbience; other rounds index RoundAmbience by the live zombie count: 0 below
    // AmbienceMidBandAlive, 1 below AmbienceLargeBandAlive, else 2 (a shorter list repeats its last entry).
    // Null or empty entries are silence. Defaults are set in HoverNYCSurvival.cpp.
    UHoverNYCEncounterSettings();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TSoftObjectPtr<USoundBase> HordeAmbience;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TArray<TSoftObjectPtr<USoundBase>> RoundAmbience;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0"))
    int32 AmbienceMidBandAlive = 8;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0"))
    int32 AmbienceLargeBandAlive = 17;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0"))
    float AmbienceVolume = 1.f;
    // Audio pass 2026-10-31 ("game's quiet"): one looping weather bed (cplomedia wind loop) under the crowd bed
    // from the first round to EndPlay. Null is silence.
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio")
    TSoftObjectPtr<USoundBase> WeatherBed;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0"))
    float WeatherBedVolume = .45f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0"))
    float AmbienceFadeSeconds = 1.5f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "AFS|Audio", meta = (ClampMin = "0.1"))
    float AmbienceCheckSeconds = 2.f;
    // end audio additions

    UFUNCTION(BlueprintPure) bool IsHordeRound(int32 Round) const
    {
        return SwarmInterval > 0 && Round >= SwarmFirstWave && (Round - SwarmFirstWave) % SwarmInterval == 0;
    }

  private:
    // Scratch row for the generated cycle. Its definitions are also held by the UPROPERTY pointers above.
    mutable FHoverBossRound Generated;
};
