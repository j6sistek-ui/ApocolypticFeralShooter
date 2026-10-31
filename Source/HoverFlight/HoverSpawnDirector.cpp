#include "HoverSpawnDirector.h"
#include "HoverNYCSurvival.h"
#include "HoverPilot.h"
#include "HoverTestController.h"
#include "AIController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavigationSystem.h"
#include "Zombies/ZE_ZombieAIController.h"
#include "Components/SceneComponent.h"
#include "NavAreas/NavArea_Null.h"
#include "NavModifierComponent.h"

UWorld *UHoverSpawnDirector::GetWorld() const
{
    return Mode ? Mode->GetWorld() : nullptr;
}

float UHoverSpawnDirector::Now() const
{
    const UWorld *World = GetWorld();
    return World ? World->GetTimeSeconds() : 0.f;
}

void UHoverSpawnDirector::Init(AHoverNYCSurvivalGameMode *InMode, UHoverNYCEncounterSettings *InSettings)
{
    Mode = InMode;
    Settings = InSettings;
    Spawners.Reset();
    if (!GetWorld())
        return;
    TArray<AZE_ZombieSpawnPoint *> All, Tagged;
    for (TActorIterator<AZE_ZombieSpawnPoint> It(GetWorld()); It; ++It)
    {
        All.Add(*It);
        if (It->ActorHasTag(TEXT("AFS_NYCSpawn")))
            Tagged.Add(*It);
    }
    const TArray<AZE_ZombieSpawnPoint *> &Pool = Tagged.Num() ? Tagged : All;
    for (AZE_ZombieSpawnPoint *Point : Pool)
    {
        FHoverSpawnerState State;
        State.Point = Point;
        for (const FName &Tag : Point->SpawnTags)
            if (const FString Name = Tag.ToString(); Name.StartsWith(TEXT("Zone.")))
            {
                State.Zone = FName(*Name.Mid(5));
                break;
            }
        // AuthorNYCSurvival.py writes the bare zone id as the first spawn tag ("Plaza", then extras
        // such as "Boss"). No zone list exists yet, so that first tag is the zone when no "Zone." tag does.
        if (State.Zone.IsNone() && Point->SpawnTags.Num())
            State.Zone = Point->SpawnTags[0];
        Spawners.Add(State);
    }
    // Level-placed points default to enabled. Every point stays off until the director chooses
    // one, so the vendor's uniform pick always lands on that one point.
    for (AZE_ZombieSpawnPoint *Point : All)
        Point->bIsEnabled = false;
    RateJitter = Settings ? FMath::FRandRange(Settings->RateJitterMin, Settings->RateJitterMax) : 1.f;
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_DIRECTOR spawners=%d tagged=%d total=%d"), Spawners.Num(), Tagged.Num(),
           All.Num());
}

void UHoverSpawnDirector::BeginRound(int32 InRound, EHoverRoundKind InKind, int32 InQuota)
{
    Round = InRound;
    Kind = InKind;
    Quota = InQuota;
    for (FHoverSpawnerState &State : Spawners)
        State.UsesThisRound = 0;
    Credit = 0.f;
    StallStart = -1.f;
    bRelaxCone = false;
    bStallWarned = false;
    bBossArmed = false;
    PackRemaining = 0;
    Chosen = nullptr;
    EnableOnly(nullptr);
    NextScore = 0.f;
    bHasPackBearing = false;
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_ROUND round=%d kind=%s quota=%d interval=%.2f"), Round,
           *UEnum::GetValueAsString(Kind), Quota, GetSpawnInterval());
}

void UHoverSpawnDirector::EndRound()
{
    // AFS 2026-10-31 (kid swarm): how many entrances fed the round that is ending (once per round).
    if (Round > 0 && Round != SpreadLoggedRound)
    {
        SpreadLoggedRound = Round;
        int32 Used = 0;
        FString Uses;
        for (const FHoverSpawnerState &State : Spawners)
            if (State.UsesThisRound > 0)
            {
                ++Used;
                Uses += FString::Printf(TEXT("%s:%d,"), *GetNameSafe(State.Point.Get()), State.UsesThisRound);
            }
        UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_SPREAD round=%d kind=%s spawners=%d uses=%s"), Round,
               *UEnum::GetValueAsString(Kind), Used, Uses.IsEmpty() ? TEXT("none") : *Uses);
    }
    Chosen = nullptr;
    Credit = 0.f;
    StallStart = -1.f;
    bRelaxCone = false;
    bStallWarned = false;
    bBossArmed = false;
    PackRemaining = 0;
    EnableOnly(nullptr);
}

void UHoverSpawnDirector::SetBossSpawnArmed(bool bArmed)
{
    if (bArmed == bBossArmed)
        return;
    bBossArmed = bArmed;
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_BOSS round=%d armed=%d"), Round, bArmed ? 1 : 0);
    // Re-pick at once so the farthest entrance is enabled before the vendor's next spawn check.
    if (bArmed && Mode && Mode->GetWaveState() == EZE_WaveState::WaveInProgress)
        Rescore();
}

void UHoverSpawnDirector::SuppressSpawns(float Seconds)
{
    SuppressUntil = FMath::Max(SuppressUntil, Now() + Seconds);
}

float UHoverSpawnDirector::GetSpawnInterval() const
{
    if (!Settings)
        return 2.f;
    const bool bHorde = Kind == EHoverRoundKind::Horde;
    const float Base = bHorde ? Settings->HordeIntervalBase : Settings->SpawnIntervalBase;
    const float Floor = bHorde ? Settings->HordeIntervalFloor : Settings->SpawnIntervalFloor;
    return FMath::Max(Floor, Base * FMath::Pow(Settings->SpawnIntervalDecay, float(FMath::Max(0, Round - 1))));
}

float UHoverSpawnDirector::GetSpawnRate() const
{
    // CRITICAL: 0 only with a valid, enabled Chosen. Any 0 with no enabled point makes the vendor
    // spawn at an arbitrary PlayerStart (ZE cpp:413-420), which can be AFS_SurvivalStart.
    if (!Mode || !Settings || Mode->GetWaveState() != EZE_WaveState::WaveInProgress)
        return BIG_NUMBER;
    const AZE_ZombieSpawnPoint *Point = Chosen.Get();
    // An armed boss ignores the credit gate; the vendor MaxConcurrent gate still holds.
    if (!Point || !Point->bIsEnabled || (Credit < 1.f && !bBossArmed) || Now() < SuppressUntil)
        return BIG_NUMBER;
    if (Settings->ConcurrentSoftCap > 0 && Live.Num() >= Settings->ConcurrentSoftCap)
        return BIG_NUMBER;
    return 0.f;
}

FHoverSpawnTarget UHoverSpawnDirector::GetTarget()
{
    FHoverSpawnTarget Target;
    auto *PC = Mode ? UGameplayStatics::GetPlayerController(Mode, 0) : nullptr;
    APawn *Pawn = PC ? PC->GetPawn() : nullptr;
    if (!Pawn)
        return Target;
    Target.Pawn = Pawn;
    FRotator ViewRotation;
    PC->GetPlayerViewPoint(Target.Eye, ViewRotation);
    Target.View = ViewRotation.Vector();
    const auto *Pilot = Cast<AHoverPilot>(Pawn);
    if (Pilot && Pilot->IsOnFoot())
    {
        // On foot: the pawn when grounded, otherwise (vault, glide, fall) its last grounded spot.
        if (Pilot->GetCharacterMovement() && Pilot->GetCharacterMovement()->IsMovingOnGround())
        {
            LastGrounded = Pawn->GetNavAgentLocation();
            bHasGrounded = true;
        }
        Target.Location = bHasGrounded ? LastGrounded : Pawn->GetNavAgentLocation();
    }
    else
    {
        // Mounted, or possessing a ride: project 3 s ahead and search the navmesh more widely.
        Target.Location = Pawn->GetActorLocation() + Pawn->GetVelocity() * 3.f;
        Target.Extent = FVector(500, 500, 300);
        Target.bProjected = true;
    }
    Target.bValid = true;
    return Target;
}

bool UHoverSpawnDirector::IsOccluded(const FHoverSpawnTarget &Target, const FVector &Point, const AActor *Ignore) const
{
    UWorld *World = GetWorld();
    if (!World)
        return false;
    FCollisionObjectQueryParams Objects;
    Objects.AddObjectTypesToQuery(ECC_WorldStatic);
    Objects.AddObjectTypesToQuery(ECC_WorldDynamic);
    FCollisionQueryParams Query(SCENE_QUERY_STAT(HoverSpawnOcclusion), false);
    const AActor *Ignored[] = {Target.Pawn, Ignore, nullptr, nullptr};
    if (const auto *PC = Cast<AHoverTestController>(UGameplayStatics::GetPlayerController(Mode, 0)))
    {
        Ignored[2] = PC->GetTestBike();
        Ignored[3] = PC->GetTestTruck();
    }
    for (const AActor *Actor : Ignored)
        if (Actor)
            Query.AddIgnoredActor(Actor);
    return World->LineTraceTestByObjectType(Target.Eye, Point + FVector(0, 0, 60), Objects, Query) &&
           World->LineTraceTestByObjectType(Target.Eye, Point + FVector(0, 0, 170), Objects, Query);
}

bool UHoverSpawnDirector::IsVisible(const FHoverSpawnTarget &Target, const FVector &Point, const AActor *Ignore) const
{
    const FVector Sight = Point + FVector(0, 0, 60);
    return FVector::DotProduct((Sight - Target.Eye).GetSafeNormal(), Target.View) > 0.f &&
           !IsOccluded(Target, Point, Ignore);
}

bool UHoverSpawnDirector::CanReachCached(AZE_ZombieSpawnPoint *Point, const FHoverSpawnTarget &Target)
{
    const float Time = Now();
    if (Time >= NextReachReset || FVector::DistSquared(Target.Location, ReachTarget) > FMath::Square(200.f))
    {
        Reachable.Reset();
        ReachTarget = Target.Location;
        NextReachReset = Time + 1.f;
    }
    if (const bool *Cached = Reachable.Find(Point))
        return *Cached;
    const bool bReachable = Mode->CanReachPoint(Point, Target.Location, Target.Extent, Target.Pawn);
    Reachable.Add(Point, bReachable);
    return bReachable;
}

FHoverSpawnerState *UHoverSpawnDirector::FindState(const AZE_ZombieSpawnPoint *Point)
{
    if (Point)
        for (FHoverSpawnerState &State : Spawners)
            if (State.Point.Get() == Point)
                return &State;
    return nullptr;
}

void UHoverSpawnDirector::EnableOnly(AZE_ZombieSpawnPoint *Point)
{
    for (FHoverSpawnerState &State : Spawners)
        if (AZE_ZombieSpawnPoint *Each = State.Point.Get())
            Each->bIsEnabled = Each == Point;
}

AZE_ZombieSpawnPoint *UHoverSpawnDirector::Pick(const FHoverSpawnTarget &Target, bool bRelax, bool bPackReuse,
                                                int32 &OutCandidates)
{
    OutCandidates = 0;
    if (!Target.bValid || !Settings || !Mode)
        return nullptr;
    const float Time = Now();
    const float Cooldown = FMath::Max(Settings->CooldownMin, 2.f * GetSpawnInterval());
    const int32 RoundCap = FMath::Max(1, FMath::CeilToInt(Quota / 3.f));
    TArray<const AActor *, TInlineAllocator<3>> Rides;
    Rides.Add(Target.Pawn);
    if (const auto *PC = Cast<AHoverTestController>(UGameplayStatics::GetPlayerController(Mode, 0)))
    {
        Rides.Add(PC->GetTestBike());
        Rides.Add(PC->GetTestTruck());
    }
    struct FCandidate
    {
        FHoverSpawnerState *State;
        float Weight;
        float Distance;
        bool bCapped;
        bool bRecent;
    };
    TArray<FCandidate, TInlineAllocator<32>> List;
    for (FHoverSpawnerState &State : Spawners)
    {
        AZE_ZombieSpawnPoint *Point = State.Point.Get();
        if (!Point || (bPackReuse && Point != Chosen.Get()))
            continue;
        const FVector Position = Point->GetActorLocation();
        // Distance band to the target; a projected (mounted) target never uses the far edge.
        const float Distance = FVector::Dist2D(Position, Target.Location);
        float Weight = 0.f;
        if (Distance >= Settings->BandInner && Distance <= Settings->BandOuter)
            Weight = 1.f;
        else if ((Distance >= Settings->NearMin && Distance < Settings->BandInner) ||
                 (!Target.bProjected && Distance > Settings->BandOuter && Distance <= Settings->FarMax))
            Weight = Settings->EdgeWeight;
        else
            continue;
        // Occupancy: the player and the rides; a zombie only while it is less than 1 s old.
        bool bOccupied = false;
        for (const AActor *Ride : Rides)
            if (Ride && FVector::Dist2D(Ride->GetActorLocation(), Position) < Settings->PlayerClearance)
                bOccupied = true;
        for (const auto &Weak : Live)
            if (const AHoverCyberZombie *Zombie = Weak.Get();
                !bOccupied && Zombie && Time - Zombie->SpawnTime < 1.f &&
                FVector::Dist2D(Zombie->GetActorLocation(), Position) < Settings->FreshZombieClearance)
                bOccupied = true;
        if (bOccupied)
            continue;
        if (!bPackReuse && Time - State.LastUsed < Cooldown)
            continue;
        // Off-screen: behind the view, or hidden by static geometry at both heights.
        const FVector Sight = Position + FVector(0, 0, 60);
        if (FVector::DotProduct((Sight - Target.Eye).GetSafeNormal(), Target.View) > 0.f)
        {
            if (!bRelax && !IsOccluded(Target, Position, Point))
                continue;
            Weight *= Settings->OccludedWeight;
        }
        // AFS 2026-10-31 (kid swarm): a new horde pack favours entrances away from the last pack's bearing
        // (x .35 on the same bearing up to x 1 opposite), so a swarm arrives from several sides when the gates
        // allow it.
        if (Kind == EHoverRoundKind::Horde && !bPackReuse && bHasPackBearing)
        {
            const FVector Delta = Position - Target.Location;
            const float Bearing = FMath::RadiansToDegrees(FMath::Atan2(Delta.Y, Delta.X));
            Weight *= .35f + .65f * FMath::Abs(FMath::FindDeltaAngleDegrees(Bearing, LastPackBearing)) / 180.f;
        }
        if (Weight <= 0.f)
            continue;
        // Reachability is always required (last, because it is the most expensive gate).
        if (!CanReachCached(Point, Target))
            continue;
        List.Add({&State, Weight, Distance, !bPackReuse && State.UsesThisRound >= RoundCap,
                  !bPackReuse && Recent.Contains(State.Point)});
    }
    OutCandidates = List.Num();
    // Boss release: the farthest reachable entrance, so the boss walks in rather than appearing.
    if (bBossArmed && !bPackReuse && List.Num())
    {
        const FCandidate *Farthest = &List[0];
        for (const FCandidate &Candidate : List)
            if (Candidate.Distance > Farthest->Distance)
                Farthest = &Candidate;
        return Farthest->State->Point.Get();
    }
    // The per-round cap and the distinct-recent rule only apply while other entrances exist.
    if (List.ContainsByPredicate([](const FCandidate &C) { return !C.bCapped; }))
        List.RemoveAll([](const FCandidate &C) { return C.bCapped; });
    if (List.Num() >= 3 && List.ContainsByPredicate([](const FCandidate &C) { return !C.bRecent; }))
        List.RemoveAll([](const FCandidate &C) { return C.bRecent; });
    if (List.IsEmpty())
        return nullptr;
    float Total = 0.f;
    for (const FCandidate &Candidate : List)
        Total += Candidate.Weight;
    float Roll = FMath::FRand() * Total;
    for (const FCandidate &Candidate : List)
    {
        Roll -= Candidate.Weight;
        if (Roll <= 0.f)
            return Candidate.State->Point.Get();
    }
    return List.Last().State->Point.Get();
}

void UHoverSpawnDirector::Rescore()
{
    const FHoverSpawnTarget Target = GetTarget();
    const float Time = Now();
    int32 Found = 0;
    AZE_ZombieSpawnPoint *Point = nullptr;
    // A horde pack keeps its entrance while distance, reach, occupancy and cone still pass.
    if (PackRemaining > 0 && Chosen.IsValid())
    {
        Point = Pick(Target, bRelaxCone, true, Found);
        if (!Point)
            PackRemaining = 0;
    }
    if (!Point)
        Point = Pick(Target, bRelaxCone, false, Found);
    Candidates = Found;
    if (!Point)
    {
        // Stall: credit does not accrue, and no point may stay enabled.
        if (StallStart < 0.f)
            StallStart = Time;
        Credit = 0.f;
        Chosen = nullptr;
        EnableOnly(nullptr);
        if (!bRelaxCone && Settings && Time - StallStart >= Settings->StallRelaxSeconds)
        {
            // Only the cone/visibility gate relaxes; distance, reach and occupancy stay enforced.
            bRelaxCone = true;
            UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_RELAX round=%d stalled=%.1f target=%s"), Round,
                   Time - StallStart, *Target.Location.ToString());
            Point = Pick(Target, true, false, Found);
            Candidates = Found;
        }
        if (!Point)
        {
            if (!bStallWarned && Settings && Time - StallStart >= Settings->StallWarnSeconds)
            {
                bStallWarned = true;
                UE_LOG(LogTemp, Warning, TEXT("HOVER_SPAWN_STALL round=%d stalled=%.1f player=%s spawners=%d"), Round,
                       Time - StallStart, Target.Pawn ? *Target.Pawn->GetActorLocation().ToString() : TEXT("none"),
                       Spawners.Num());
            }
            return;
        }
    }
    // A returning candidate starts from zero credit (set while stalled).
    StallStart = -1.f;
    bStallWarned = false;
    Chosen = Point;
    EnableOnly(Point);
}

void UHoverSpawnDirector::Update(float DeltaSeconds)
{
    if (!Mode || !Settings)
        return;
    Live.RemoveAll([](const TWeakObjectPtr<AHoverCyberZombie> &Weak) { return !Weak.IsValid() || Weak->IsDead(); });
    UpdateTruckNavBlocker();
    if (Mode->GetWaveState() != EZE_WaveState::WaveInProgress)
        return;
    const float Time = Now();
    // Remaining-to-spawn = remaining-to-kill minus the living. With nothing left to spawn, no
    // point stays enabled and the stall timers stay quiet.
    const bool bSpawnsLeft = Mode->GetZombiesRemaining() - Live.Num() > 0;
    if (Time >= NextScore)
    {
        NextScore = Time + .25f;
        if (bSpawnsLeft)
            Rescore();
        else if (Chosen.IsValid() || StallStart >= 0.f)
        {
            Chosen = nullptr;
            StallStart = -1.f;
            EnableOnly(nullptr);
        }
    }
    // Pacing: Interval = SI(r) x Tuning x jitter; Pressure = Raise x Lower; credit is the only gate.
    const float Interval = FMath::Max(.05f, GetSpawnInterval() * Mode->Tuning.SpawnInterval * RateJitter);
    const APawn *Player = UGameplayStatics::GetPlayerPawn(Mode, 0);
    bool bAnyClose = false;
    int32 Crowd = 0;
    if (Player)
        for (const auto &Weak : Live)
            if (const AHoverCyberZombie *Zombie = Weak.Get())
            {
                const float Distance = FVector::Dist(Zombie->GetActorLocation(), Player->GetActorLocation());
                bAnyClose |= Distance <= Settings->IdleRadius;
                Crowd += Distance <= Settings->CrowdRadius ? 1 : 0;
            }
    const bool bQuotaLeft = Quota - Mode->GetZombiesKilledThisWave() - Live.Num() > 0;
    const float Raise = Live.Num() < Settings->CatchUpBelowAlive && bQuotaLeft ? Settings->CatchUpPressure
                        : Player && !bAnyClose                                 ? Settings->IdlePressure
                                                                               : 1.f;
    const float Lower = Crowd >= Settings->CrowdCount ? Settings->CrowdPressure : 1.f;
    LastPressure = Raise * Lower;
    LastInterval = Interval;
    if (StallStart < 0.f)
        Credit = FMath::Min(1.f, Credit + LastPressure * DeltaSeconds / Interval);
    if (Time >= NextSprintCheck)
    {
        NextSprintCheck = Time + 1.f;
        UpdateForcedSprinters();
    }
    if (Time >= NextStragglerPass)
    {
        NextStragglerPass = Time + 2.f;
        UpdateStragglers();
    }
}

void UHoverSpawnDirector::OnSpawned(AHoverCyberZombie &Zombie, bool bVendorSpawn)
{
    Live.AddUnique(TWeakObjectPtr<AHoverCyberZombie>(&Zombie));
    Zombie.OnDeath.AddUniqueDynamic(this, &UHoverSpawnDirector::OnLiveZombieDeath);
    if (!bVendorSpawn || !Settings)
        return;
    const float Time = Now();
    AZE_ZombieSpawnPoint *Point = Chosen.Get();
    Credit = FMath::Max(0.f, Credit - 1.f);
    if (FHoverSpawnerState *State = FindState(Point))
    {
        State->LastUsed = Time;
        ++State->UsesThisRound;
    }
    if (Point)
    {
        const TWeakObjectPtr<AZE_ZombieSpawnPoint> Used(Point);
        Recent.Remove(Used);
        Recent.Insert(Used, 0);
        if (Recent.Num() > Settings->RecentCount)
            Recent.SetNum(Settings->RecentCount);
    }
    if (Kind == EHoverRoundKind::Horde)
    {
        // AFS 2026-10-31 (kid swarm): remember the bearing of each new pack's entrance (see Pick).
        if (PackRemaining <= 0 && Point)
            if (const APawn *PackTarget = UGameplayStatics::GetPlayerPawn(Mode, 0))
            {
                const FVector Delta = Point->GetActorLocation() - PackTarget->GetActorLocation();
                LastPackBearing = FMath::RadiansToDegrees(FMath::Atan2(Delta.Y, Delta.X));
                bHasPackBearing = true;
                UE_LOG(LogTemp, Verbose, TEXT("HOVER_SPAWN_HORDE_PACK round=%d spawner=%s bearing=%.0f"), Round,
                       *GetNameSafe(Point), LastPackBearing);
            }
        PackRemaining = PackRemaining > 0 ? PackRemaining - 1 : FMath::Max(0, Settings->HordePackSize - 1);
    }
    const bool bWasRelaxed = bRelaxCone;
    bRelaxCone = false;
    // Jitter: a reachable point near the entrance and +-60 degrees of yaw, so a door never
    // produces a conga line on one exact XY. The vendor spawn already succeeded either way.
    if (Settings->JitterRadius > 0.f)
        if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
        {
            FNavLocation Out;
            if (Navigation->GetRandomReachablePointInRadius(Zombie.GetActorLocation(), Settings->JitterRadius, Out))
                Zombie.SetActorLocation(
                    Out.Location + FVector(0, 0, Zombie.GetCapsuleComponent()->GetScaledCapsuleHalfHeight() + 50.f),
                    false, nullptr, ETeleportType::TeleportPhysics);
        }
    Zombie.AddActorWorldRotation(FRotator(0, FMath::FRandRange(-60.f, 60.f), 0));
    const APawn *Player = UGameplayStatics::GetPlayerPawn(Mode, 0);
    UE_LOG(LogTemp, Display,
           TEXT("HOVER_SPAWN time=%.2f round=%d spawner=%s distance=%.0f tier=%.0f interval=%.2f pressure=%.2f "
                "credit=%.2f candidates=%d relaxCone=%d zombie=%s role=%s"),
           Time, Round, *GetNameSafe(Point),
           Player ? FVector::Dist2D(Player->GetActorLocation(), Zombie.GetActorLocation()) : -1.f, Zombie.SpeedTier,
           LastInterval, LastPressure, Credit, Candidates, bWasRelaxed ? 1 : 0, *Zombie.GetName(),
           *UEnum::GetValueAsString(Zombie.GetRole()));
    RateJitter = FMath::FRandRange(Settings->RateJitterMin, Settings->RateJitterMax);
    // Re-pick at once, so the next spawn can use a different entrance in the same tick window.
    if (Mode && Mode->GetZombiesRemaining() - Live.Num() > 0)
        Rescore();
}

bool UHoverSpawnDirector::PrepareExtraSpawn()
{
    if (!Mode || !Settings || Credit < 1.f || Now() < SuppressUntil)
        return false;
    Rescore();
    return GetSpawnRate() == 0.f;
}

void UHoverSpawnDirector::OnLiveZombieDeath(AZE_ZombieCharacter *Zombie)
{
    Live.RemoveAll(
        [Zombie](const TWeakObjectPtr<AHoverCyberZombie> &Weak) { return !Weak.IsValid() || Weak.Get() == Zombie; });
    for (auto It = HiddenSince.CreateIterator(); It; ++It)
        if (!It->Key.IsValid() || It->Key.Get() == Zombie)
            It.RemoveCurrent();
}

bool UHoverSpawnDirector::RelocateZombie(AHoverCyberZombie &Zombie)
{
    if (!Mode || !Settings || Zombie.IsDead())
        return false;
    const FHoverSpawnTarget Target = GetTarget();
    int32 Found = 0;
    AZE_ZombieSpawnPoint *Point = Pick(Target, false, false, Found);
    if (!Point)
        return false;
    auto *AI = Cast<AAIController>(Zombie.GetController());
    if (AI)
        AI->StopMovement();
    if (auto *Movement = Zombie.GetCharacterMovement())
        Movement->StopMovementImmediately();
    Zombie.SetActorLocation(Point->GetActorLocation() + FVector(0, 0, 50), false, nullptr,
                            ETeleportType::TeleportPhysics);
    if (AI)
        if (auto *Board = AI->GetBlackboardComponent())
            Board->SetValueAsVector(AZE_ZombieAIController::Key_LastKnownLocation, Target.Location);
    // No relocation limit: health is kept and the zombie stays in the vendor ZombiesAlive.
    ++Zombie.RelocationCount;
    Zombie.UnreachableSince = -1.f;
    Zombie.SpawnerUsed = Point;
    HiddenSince.Remove(TWeakObjectPtr<AHoverCyberZombie>(&Zombie));
    if (FHoverSpawnerState *State = FindState(Point))
        State->LastUsed = Now();
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_RELOCATE time=%.2f round=%d zombie=%s spawner=%s relocations=%d"), Now(),
           Round, *Zombie.GetName(), *GetNameSafe(Point), Zombie.RelocationCount);
    return true;
}

void UHoverSpawnDirector::UpdateForcedSprinters()
{
    // After the opening rounds, the last few Standards of a round run so it cannot trickle out.
    if (Round <= Settings->ForcedSprintAfterRound || Mode->GetZombiesRemaining() > Settings->ForcedSprintersAtEnd)
        return;
    for (const auto &Weak : Live)
        if (AHoverCyberZombie *Zombie = Weak.Get();
            Zombie && !Zombie->IsDead() && Zombie->GetRole() == EHoverZombieRole::Standard)
            Zombie->SpeedTier = FMath::Max(Zombie->SpeedTier, Settings->SprinterSpeed);
}

void UHoverSpawnDirector::UpdateTruckNavBlocker()
{
    // AFS 2026-10-31 (kid swarm, owner playtest item 5): "kid zombies bunch / hoard in one spot" by the truck.
    // AHoverTestController spawns the parked pickup at runtime at AFS_TruckStart (200, 5900), in the North
    // Avenue lane between the Uptown entrances and the survival start, but L_NYC_Survival's navmesh is
    // DynamicModifiersOnly and was built without it. Paths, and Detour crowd steering (which only sees navmesh
    // walls), ran straight through the truck: zombies from Uptown piled against its bumper and crawled along
    // it at 5-50 cm/s (ZombieDiversity_20261031/proof.json). A null-area nav modifier over the settled truck
    // cuts it out of the navmesh, so paths go round either side of it.
    UWorld *World = GetWorld();
    const float Time = Now();
    if (!World || !Mode || Time < NextTruckCheck)
        return;
    NextTruckCheck = Time + 2.f;
    const auto *PC = Cast<AHoverTestController>(UGameplayStatics::GetPlayerController(Mode, 0));
    APawn *Truck = PC ? PC->GetTestTruck() : nullptr;
    AActor *Blocker = TruckBlocker.Get();
    if (!IsValid(Truck) || PC->GetPawn() == Truck)
    {
        if (Blocker)
        {
            Blocker->Destroy();
            UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_TRUCK_NAV action=removed truck=%s"), *GetNameSafe(Truck));
        }
        TruckBlocker.Reset();
        TruckSeenAt = -1.f;
        return;
    }
    if (TruckSeenAt < 0.f)
        TruckSeenAt = Time;
    // Spawned 120 cm above the road, it drops onto its wheels first (placed anyway after 6 s of suspension jitter).
    const float Seen = Time - TruckSeenAt;
    if (Seen < 1.5f || (Seen < 6.f && Truck->GetVelocity().SizeSquared() > FMath::Square(10.f)))
        return;
    FVector Origin, Extent;
    Truck->GetActorBounds(true, Origin, Extent);
    // Collision bounds of the vehicle body, clamped so a stray component can never close a whole street.
    Extent.X = FMath::Clamp<double>(Extent.X, 60.0, 400.0) + 10.0;
    Extent.Y = FMath::Clamp<double>(Extent.Y, 60.0, 400.0) + 10.0;
    Extent.Z = FMath::Clamp<double>(Extent.Z, 60.0, 250.0);
    if (Blocker && FVector::Dist2D(Blocker->GetActorLocation(), Origin) < 40.f &&
        (TruckBlockerExtent - Extent).GetAbsMax() < 25.f)
        return;
    const TCHAR *Action = Blocker ? TEXT("moved") : TEXT("placed");
    if (Blocker)
        Blocker->Destroy();
    TruckBlocker.Reset();
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    Params.ObjectFlags |= RF_Transient;
    AActor *Actor = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(Origin), Params);
    if (!Actor)
        return;
    // No primitive component on purpose: the modifier then uses FailsafeExtent around the actor location, an
    // axis-aligned box (the root is never rotated), instead of guessing from the vehicle's physics bodies.
    auto *Root = NewObject<USceneComponent>(Actor, TEXT("AFSTruckNavRoot"));
    Actor->SetRootComponent(Root);
    Root->SetWorldLocationAndRotation(Origin, FQuat::Identity);
    Root->RegisterComponent();
    auto *Modifier = NewObject<UNavModifierComponent>(Actor, TEXT("AFSTruckNavModifier"));
    Modifier->AreaClass = UNavArea_Null::StaticClass();
    Modifier->FailsafeExtent = Extent;
    Modifier->bIncludeAgentHeight = true;
    Modifier->RegisterComponent();
    Actor->Tags.Add(TEXT("AFS_TruckNavBlocker"));
    TruckBlocker = Actor;
    TruckBlockerExtent = Extent;
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPAWN_TRUCK_NAV action=%s truck=%s center=%s extent=%s area=%s"), Action,
           *Truck->GetName(), *Origin.ToCompactString(), *Extent.ToCompactString(),
           *GetNameSafe(Modifier->AreaClass.Get()));
}

void UHoverSpawnDirector::UpdateStragglers()
{
    const FHoverSpawnTarget Target = GetTarget();
    if (!Target.bValid || Live.IsEmpty())
        return;
    const float Time = Now();
    // Round-robin: a quarter of the live set per 2 s pass, so a 24-zombie round costs at most six
    // path tests and twelve traces in one mode tick instead of 24 and 48. Each zombie is still
    // revisited every 8 s, well inside the 20 s NoPath / Hidden windows.
    const int32 Slice = FMath::Max(1, FMath::DivideAndRoundUp(Live.Num(), StragglerPasses));
    // The sight traces only matter past the nearer of the two distance gates.
    const float SightDistance = FMath::Min(Settings->FarDistance, Settings->HiddenDistance);
    TArray<AHoverCyberZombie *, TInlineAllocator<8>> Stragglers;
    for (int32 Step = 0; Step < Slice; ++Step)
    {
        if (StragglerCursor >= Live.Num())
            StragglerCursor = 0;
        AHoverCyberZombie *Zombie = Live[StragglerCursor++].Get();
        if (!Zombie || Zombie->IsDead())
            continue;
        const FVector Feet =
            Zombie->GetActorLocation() - FVector(0, 0, Zombie->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
        const float Distance = FVector::Dist2D(Feet, Target.Pawn->GetActorLocation());
        const bool bVisible = Distance > SightDistance && IsVisible(Target, Feet, Zombie);
        // (a) far, old enough and out of sight.
        bool bRelocate =
            Distance > Settings->FarDistance && Time - Zombie->SpawnTime > Settings->FarMinAge && !bVisible;
        // (b) no complete path for NoPathSeconds. A zombie already moving on a complete path is
        // reachable; only idle or path-less ones pay for the synchronous navmesh query.
        bool bNoPath = false, bMovingOnPath = false;
        if (const auto *AI = Cast<AAIController>(Zombie->GetController()))
            if (const auto *Path = AI->GetPathFollowingComponent())
            {
                bNoPath = Path->HasPartialPath();
                bMovingOnPath = !bNoPath && Path->HasValidPath() && Path->GetStatus() == EPathFollowingStatus::Moving;
            }
        if (!bNoPath && !bMovingOnPath)
            bNoPath = !Mode->CanReachPoint(Zombie, Target.Location, Target.Extent, Zombie);
        if (!bNoPath)
            Zombie->UnreachableSince = -1.f;
        else if (Zombie->UnreachableSince < 0.f)
            Zombie->UnreachableSince = Time;
        else if (Time - Zombie->UnreachableSince >= Settings->NoPathSeconds)
            bRelocate = true;
        // (c) beyond HiddenDistance and out of sight for HiddenSeconds.
        if (Distance > Settings->HiddenDistance && !bVisible)
        {
            const float Since = HiddenSince.FindOrAdd(TWeakObjectPtr<AHoverCyberZombie>(Zombie), Time);
            bRelocate |= Time - Since >= Settings->HiddenSeconds;
        }
        else
            HiddenSince.Remove(TWeakObjectPtr<AHoverCyberZombie>(Zombie));
        if (bRelocate)
            Stragglers.Add(Zombie);
    }
    for (AHoverCyberZombie *Zombie : Stragglers)
        RelocateZombie(*Zombie);
}
