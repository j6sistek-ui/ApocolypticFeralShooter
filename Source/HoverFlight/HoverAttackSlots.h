#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Navigation/CrowdManager.h"
#include "HoverAttackSlots.generated.h"

class AHoverNYCZombie;

UENUM(BlueprintType)
enum class EHoverSlotKind : uint8
{
    None,
    Inner,
    Queue,
    Roam
};

// One destination handed to a zombie by the attack-slot ring.
USTRUCT(BlueprintType)
struct FHoverSlotClaim
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FVector Location = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) EHoverSlotKind Kind = EHoverSlotKind::None;
    UPROPERTY(BlueprintReadOnly) int32 Sector = INDEX_NONE;
    // Horizontal distance from the ring anchor to Location.
    UPROPERTY(BlueprintReadOnly) float StopRadius = 0;
    bool IsValid() const
    {
        return Kind != EHoverSlotKind::None;
    }
};

// NYC Survival attack sectors and tokens (design Section 4 §7). The subsystem exists in every
// game world but is inert: only AHoverNYCZombie and AHoverNYCZombieAI call it, so Cyber City,
// Lakeside, PostApo and NYC Exploration never claim a slot or a token.
UCLASS()
class HOVERFLIGHT_API UHoverAttackSlotSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
  public:
    static constexpr int32 InnerSectors = 8;
    static constexpr int32 QueueSectors = 12;
    static constexpr int32 MaxHeavyInner = 2;
    // Matches UHoverBTTask_MoveToSlot's ObservedBlackboardValueTolerance: a target turning or
    // aiming in place never moves the ring.
    static constexpr float AnchorTolerance = 60.f;
    // AFS 2026-10-31 (kid swarm): progress watchdog. A zombie farther than StallMinDistance from its target
    // that has travelled less than StallMoveCm in StallSeconds (not swinging or roaring) is stalled and gets a
    // lateral detour for up to DetourSeconds.
    static constexpr float StallSeconds = 2.f;
    static constexpr float StallMoveCm = 60.f;
    static constexpr float StallMinDistance = 600.f;
    static constexpr float DetourSeconds = 2.f;

    static UHoverAttackSlotSubsystem *Get(const UObject *WorldContext);

    virtual void Deinitialize() override;

    // Sticky: keeps the zombie's sector while it stays valid, otherwise the free inner sector
    // nearest its approach bearing, then the nearest queue sector, then a roaming point. A queue
    // claimant is promoted to a free inner sector on every call.
    FHoverSlotClaim ClaimSlot(AHoverNYCZombie *Zombie, APawn *Target);
    void ReleaseSlot(AHoverNYCZombie *Zombie);
    bool TryAcquireAttackToken(AHoverNYCZombie *Zombie);
    void ReleaseAttackToken(AHoverNYCZombie *Zombie);
    bool HasAttackToken(const AHoverNYCZombie *Zombie) const;
    bool IsInInnerRing(const AHoverNYCZombie *Zombie) const;
    // Inner ring radius for this zombie against this target: max(AttackRange - 30, TargetR +
    // SelfR + 15) with the target capsule read live (pilot 32 on foot, 90 mounted). Under the
    // vendor BT the radius is also kept inside the vendor's 3D centre-distance test.
    float GetInnerRadius(const AHoverNYCZombie *Zombie, const APawn *Target) const;
    // Largest horizontal stop distance that still passes the vendor 3D range test.
    static float GetVendorReach2D(const AHoverNYCZombie *Zombie, const APawn *Target);

    // Mode configuration. The NYC game mode pushes these; the defaults are the design values
    // (3 tokens, 2 on horde rounds, corpse budget off).
    void SetTokenBudget(int32 Normal, int32 Horde);
    void SetHordeRound(bool bHorde);
    void SetMaxLiveCorpses(int32 Count);
    int32 GetTokenLimit() const;
    // Corpse budget: when more than MaxLiveCorpses NYC corpses are alive, the oldest is set to
    // expire in 1 s. 0 keeps the vendor CorpseLifespan only.
    void RegisterCorpse(AActor *Corpse);

    // Validation counters (read by the offscreen review script).
    UFUNCTION(BlueprintPure) int32 GetTokensInUse() const;
    UFUNCTION(BlueprintPure) int32 GetPeakTokensInUse() const
    {
        return PeakTokens;
    }
    int32 GetHeavyInnerCount(const APawn *Target) const;
    UFUNCTION(BlueprintPure) int32 GetPeakHeavyInner() const
    {
        return PeakHeavyInner;
    }
    UFUNCTION(BlueprintPure) int32 GetRingMoves() const
    {
        return RingMoves;
    }
    UFUNCTION(BlueprintPure) int32 GetLiveCorpseCount() const;

    // Per-world crowd tuning without a DefaultEngine.ini section: sets bResolveCollisions and
    // SeparationDirClamp .3 on this world's live crowd manager through reflection (the config
    // properties are protected). Call once from AHoverNYCSurvivalGameMode::StartPlay. A
    // UHoverNYCCrowdManager already carries the values and is left untouched.
    static void ApplyNYCCrowdTuning(UWorld *World);

    // Nav projection used by every slot point (extent 60, 60, 200).
    bool ProjectSlotPoint(const FVector &Point, FVector &OutPoint) const;

    // AFS 2026-10-31 (kid swarm): samples the zombie's travel; true once each time it becomes stalled (see
    // StallSeconds). Called by ClaimSlot and by the far-approach branch of AHoverNYCZombieAI::UpdateDestination.
    bool UpdateProgress(AHoverNYCZombie *Zombie, const APawn *Target);
    // Far-approach point: a live detour for a stalled zombie, else Desired when it is on the navmesh and
    // connected to the target, else the nearest of a fan of bearings round the target, else the target's own
    // nav point. False (OutPoint unset) only when none of them projects.
    bool ResolveApproachPoint(AHoverNYCZombie *Zombie, const APawn *Target, const FVector &Desired,
                              FVector &OutPoint);
    UFUNCTION(BlueprintPure) int32 GetStallCount() const
    {
        return Stalls;
    }
    UFUNCTION(BlueprintPure) int32 GetDetourCount() const
    {
        return Detours;
    }
    UFUNCTION(BlueprintPure) int32 GetApproachRerouteCount() const
    {
        return ApproachReroutes;
    }

  protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

  private:
    struct FRoamPoint
    {
        FVector Location = FVector::ZeroVector;
        float RefreshAt = 0;
        float Distance = 0;
    };
    struct FRing
    {
        FVector Anchor = FVector::ZeroVector;
        bool bAnchored = false;
        TWeakObjectPtr<AHoverNYCZombie> Inner[InnerSectors];
        TWeakObjectPtr<AHoverNYCZombie> Queue[QueueSectors];
        float InnerBlockedUntil[InnerSectors] = {};
        float QueueBlockedUntil[QueueSectors] = {};
        TMap<TWeakObjectPtr<AHoverNYCZombie>, FRoamPoint> Roaming;
    };
    TMap<TWeakObjectPtr<APawn>, FRing> Rings;
    TSet<TWeakObjectPtr<AHoverNYCZombie>> Tokens;
    TSet<TWeakObjectPtr<AHoverNYCZombie>> BossTokens;
    TArray<TWeakObjectPtr<AActor>> Corpses;
    int32 NormalTokens = 3;
    int32 HordeTokens = 2;
    bool bHordeRound = false;
    int32 MaxLiveCorpses = 0;
    int32 PeakTokens = 0;
    int32 PeakHeavyInner = 0;
    int32 RingMoves = 0;
    // AFS 2026-10-31 (kid swarm): per-zombie progress window and detour (UpdateProgress / GetDetour).
    struct FProgress
    {
        FVector Origin = FVector::ZeroVector;
        float WindowStart = -1.f;
        bool bStalled = false;
        FVector Detour = FVector::ZeroVector;
        float DetourUntil = 0.f;
        float DetourSide = 0.f;
    };
    TMap<TWeakObjectPtr<AHoverNYCZombie>, FProgress> Progress;
    int32 Stalls = 0;
    int32 Detours = 0;
    int32 ApproachReroutes = 0;

    void Prune();
    static bool IsZombieUsable(const AHoverNYCZombie *Zombie);
    int32 CountHeavyInner(const FRing &Ring) const;
    void RemoveFromRing(FRing &Ring, const AHoverNYCZombie *Zombie);
    bool SectorPoint(const FRing &Ring, float BearingDegrees, float Radius, float MinRadius, FVector &Out) const;
    bool BuildRoamPoint(const FRing &Ring, const AHoverNYCZombie *Zombie, FRoamPoint &Out) const;
    bool IsReachable(const FVector &From, const FVector &To, const UObject *Querier) const;
    bool BuildDetour(const AHoverNYCZombie *Zombie, const APawn *Target, FProgress &State);
    bool GetDetour(AHoverNYCZombie *Zombie, const APawn *Target, FVector &OutPoint);
};

// Optional per-map crowd manager for UHoverNYCNavigationSystem::CrowdManagerClass. Unused until a
// NYC navigation system assigns it; ApplyNYCCrowdTuning is the per-world fallback.
UCLASS()
class HOVERFLIGHT_API UHoverNYCCrowdManager : public UCrowdManager
{
    GENERATED_BODY()
  public:
    virtual void PostInitProperties() override;
};
