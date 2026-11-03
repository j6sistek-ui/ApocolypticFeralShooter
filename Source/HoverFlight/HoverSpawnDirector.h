#pragma once
#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "HoverCyberVariants.h"
#include "World/ZE_ZombieSpawnPoint.h"
#include "HoverSpawnDirector.generated.h"

class AHoverNYCSurvivalGameMode;
class AHoverCyberZombie;
class AZE_ZombieCharacter;
class APawn;

USTRUCT()
struct FHoverSpawnerState
{
    GENERATED_BODY()
    TWeakObjectPtr<AZE_ZombieSpawnPoint> Point;
    // From a "Zone.<Name>" spawn tag, else the first spawn tag (the bare zone id the author script writes).
    // Zone pools are a later slice; every spawner is in-zone now.
    FName Zone;
    float LastUsed = -1000.f;
    int32 UsesThisRound = 0;
};

// The player target the gates measure against (plain struct, not reflected).
struct FHoverSpawnTarget
{
    APawn *Pawn = nullptr;
    // On foot: the pawn, or its last grounded spot while airborne. Mounted: Loc + Vel * 3.
    FVector Location = FVector::ZeroVector;
    FVector Extent = FVector(120, 120, 200);
    FVector Eye = FVector::ZeroVector;
    FVector View = FVector::ForwardVector;
    bool bProjected = false;
    bool bValid = false;
};

// NYC Survival spawn placement and pacing. The vendor SpawnZombie/GetRandomSpawnPoint are
// private, so the director steers them: exactly one spawn point has bIsEnabled, and the
// mode's GetEffectiveSpawnRate returns GetSpawnRate() (0 = spawn now, BIG_NUMBER = hold).
UCLASS()
class HOVERFLIGHT_API UHoverSpawnDirector : public UObject
{
    GENERATED_BODY()
  public:
    virtual UWorld *GetWorld() const override;
    void Init(AHoverNYCSurvivalGameMode *InMode, UHoverNYCEncounterSettings *InSettings);
    void BeginRound(int32 InRound, EHoverRoundKind InKind, int32 InQuota);
    void EndRound();
    // Credit every call, scoring every 0.25 s, forced sprinters every 1 s, stragglers every 2 s.
    void Update(float DeltaSeconds);
    // bVendorSpawn is false for zombies that did not come from the vendor wave spawn
    // (level-placed actors): they are tracked as live but cost no credit or spawner use.
    void OnSpawned(AHoverCyberZombie &Zombie, bool bVendorSpawn);
    float GetSpawnRate() const;
    AZE_ZombieSpawnPoint *GetChosen() const
    {
        return Chosen.Get();
    }
    int32 GetCandidateCount() const
    {
        return Candidates;
    }
    int32 GetLiveCount() const
    {
        return Live.Num();
    }
    bool RelocateZombie(AHoverCyberZombie &Zombie);
    void SuppressSpawns(float Seconds);
    // Boss release (06.4): while armed, GetSpawnRate ignores credit and Pick takes the farthest
    // reachable entrance, so the boss appears on the vendor's next free slot. The mode decides when.
    void SetBossSpawnArmed(bool bArmed);
    bool IsBossSpawnArmed() const
    {
        return bBossArmed;
    }
    // Optional extra spawn inside one mode tick (MaxSpawnsPerTick > 1): re-picks and enables
    // a different spawner. True only when a spawn may happen right now.
    bool PrepareExtraSpawn();

  private:
    FHoverSpawnTarget GetTarget();
    float GetSpawnInterval() const;
    // Full gate pipeline. bPackReuse tests only Chosen without cooldown/cap/recent gates.
    AZE_ZombieSpawnPoint *Pick(const FHoverSpawnTarget &Target, bool bRelax, bool bPackReuse, int32 &OutCandidates,
                               bool bBalanceApproaches = true);
    void Rescore();
    void EnableOnly(AZE_ZombieSpawnPoint *Point);
    FHoverSpawnerState *FindState(const AZE_ZombieSpawnPoint *Point);
    // Static geometry only (WorldStatic/WorldDynamic object types) at +60 and +170 cm, so a
    // crowd of zombie meshes (Pawn) never counts as cover.
    bool IsOccluded(const FHoverSpawnTarget &Target, const FVector &Point, const AActor *Ignore) const;
    bool IsVisible(const FHoverSpawnTarget &Target, const FVector &Point, const AActor *Ignore) const;
    // World-cardinal incoming side, or INDEX_NONE if no complete route exists.
    int32 GetApproachSideCached(AZE_ZombieSpawnPoint *Point, const FHoverSpawnTarget &Target);
    void UpdateStragglers();
    void UpdateForcedSprinters();
    // AFS 2026-10-31 (kid swarm): cuts the parked NYC pickup out of the navmesh (null-area nav modifier).
    void UpdateTruckNavBlocker();
    UFUNCTION() void OnLiveZombieDeath(AZE_ZombieCharacter *Zombie);
    float Now() const;

    UPROPERTY() TObjectPtr<AHoverNYCSurvivalGameMode> Mode;
    UPROPERTY() TObjectPtr<UHoverNYCEncounterSettings> Settings;
    UPROPERTY() TArray<FHoverSpawnerState> Spawners;
    // Own alive set: the vendor ZombiesAlive counter has no getter.
    TArray<TWeakObjectPtr<AHoverCyberZombie>> Live;
    TMap<TWeakObjectPtr<AHoverCyberZombie>, float> HiddenSince;
    TArray<TWeakObjectPtr<AZE_ZombieSpawnPoint>> Recent;
    TWeakObjectPtr<AZE_ZombieSpawnPoint> Chosen;
    // Evidence from the winning round-spawn pick, before any later relocation or rescore.
    int32 ChosenApproachSide = INDEX_NONE;
    uint8 ChosenEligibleSides = 0; // bits 0..3 = E, N, W, S
    FVector2D ChosenTravelVelocity = FVector2D::ZeroVector;
    float ChosenForwardWeight = 1.f;
    TMap<TWeakObjectPtr<AZE_ZombieSpawnPoint>, int32> ApproachSides;
    // Entries are successful births or pack starts, oldest first. Reclassify their routes as the target moves.
    TArray<TWeakObjectPtr<AZE_ZombieSpawnPoint>, TInlineAllocator<4>> ServedApproaches;
    FVector ReachTarget = FVector::ZeroVector;
    FVector LastGrounded = FVector::ZeroVector;
    bool bHasGrounded = false;
    int32 Round = 0, Quota = 0, PackRemaining = 0, Candidates = 0;
    EHoverRoundKind Kind = EHoverRoundKind::Normal;
    float Credit = 0.f, StallStart = -1.f, SuppressUntil = 0.f, RateJitter = 1.f;
    float LastInterval = 0.f, LastPressure = 1.f;
    float NextScore = 0.f, NextReachReset = 0.f, NextSprintCheck = 0.f, NextStragglerPass = 0.f;
    bool bRelaxCone = false, bStallWarned = false;
    bool bBossArmed = false;
    // Round-robin cursor for UpdateStragglers; each pass handles Live.Num() / StragglerPasses zombies.
    int32 StragglerCursor = 0;
    static constexpr int32 StragglerPasses = 4;
    // AFS 2026-10-31 (kid swarm): the nav modifier actor over the parked pickup, its extent and timers.
    TWeakObjectPtr<AActor> TruckBlocker;
    FVector TruckBlockerExtent = FVector::ZeroVector;
    float NextTruckCheck = 0.f;
    float TruckSeenAt = -1.f;
    // Horde spread: bearing (target to entrance) of the last horde pack, so Pick favours another side next.
    float LastPackBearing = 0.f;
    bool bHasPackBearing = false;
    int32 SpreadLoggedRound = 0;
};
