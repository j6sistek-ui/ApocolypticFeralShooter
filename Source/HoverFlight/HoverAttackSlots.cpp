#include "HoverAttackSlots.h"
#include "HoverNYCZombie.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "NavigationSystem.h"
#include "UObject/UnrealType.h"

namespace
{
TWeakObjectPtr<AHoverNYCZombie> SlotKey(const AHoverNYCZombie *Zombie)
{
    return TWeakObjectPtr<AHoverNYCZombie>(const_cast<AHoverNYCZombie *>(Zombie));
}

float BearingOf(const FVector &From, const FVector &To)
{
    const FVector Delta = To - From;
    return FMath::RadiansToDegrees(FMath::Atan2(Delta.Y, Delta.X));
}

float AngleGap(float A, float B)
{
    return FMath::Abs(FMath::FindDeltaAngleDegrees(A, B));
}

FVector BearingDirection(float Degrees)
{
    const float Radians = FMath::DegreesToRadians(Degrees);
    return FVector(FMath::Cos(Radians), FMath::Sin(Radians), 0);
}

float CapsuleRadiusOf(const APawn *Pawn)
{
    if (const auto *Capsule = Pawn ? Cast<UCapsuleComponent>(Pawn->GetRootComponent()) : nullptr)
        return Capsule->GetScaledCapsuleRadius();
    return Pawn ? Pawn->GetSimpleCollisionRadius() : 0.f;
}

float CapsuleHalfHeightOf(const APawn *Pawn)
{
    if (const auto *Capsule = Pawn ? Cast<UCapsuleComponent>(Pawn->GetRootComponent()) : nullptr)
        return Capsule->GetScaledCapsuleHalfHeight();
    return Pawn ? Pawn->GetSimpleCollisionHalfHeight() : 0.f;
}
} // namespace

UHoverAttackSlotSubsystem *UHoverAttackSlotSubsystem::Get(const UObject *WorldContext)
{
    const UWorld *World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UHoverAttackSlotSubsystem>() : nullptr;
}

bool UHoverAttackSlotSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UHoverAttackSlotSubsystem::Deinitialize()
{
    Rings.Reset();
    Tokens.Reset();
    BossTokens.Reset();
    Corpses.Reset();
    Super::Deinitialize();
}

bool UHoverAttackSlotSubsystem::IsZombieUsable(const AHoverNYCZombie *Zombie)
{
    return IsValid(Zombie) && !Zombie->IsKilled();
}

void UHoverAttackSlotSubsystem::Prune()
{
    for (auto It = Rings.CreateIterator(); It; ++It)
    {
        if (!It->Key.IsValid())
        {
            It.RemoveCurrent();
            continue;
        }
        FRing &Ring = It->Value;
        for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Inner)
            if (!IsZombieUsable(Slot.Get()))
                Slot.Reset();
        for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Queue)
            if (!IsZombieUsable(Slot.Get()))
                Slot.Reset();
        for (auto Roam = Ring.Roaming.CreateIterator(); Roam; ++Roam)
            if (!IsZombieUsable(Roam->Key.Get()))
                Roam.RemoveCurrent();
    }
    for (auto It = Tokens.CreateIterator(); It; ++It)
        if (!IsZombieUsable(It->Get()))
            It.RemoveCurrent();
    for (auto It = BossTokens.CreateIterator(); It; ++It)
        if (!IsZombieUsable(It->Get()))
            It.RemoveCurrent();
}

int32 UHoverAttackSlotSubsystem::CountHeavyInner(const FRing &Ring) const
{
    int32 Count = 0;
    for (const TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Inner)
        if (const AHoverNYCZombie *Zombie = Slot.Get(); IsZombieUsable(Zombie) && Zombie->IsHeavySlot())
            ++Count;
    return Count;
}

void UHoverAttackSlotSubsystem::RemoveFromRing(FRing &Ring, const AHoverNYCZombie *Zombie)
{
    for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Inner)
        if (Slot.Get() == Zombie)
            Slot.Reset();
    for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Queue)
        if (Slot.Get() == Zombie)
            Slot.Reset();
    Ring.Roaming.Remove(SlotKey(Zombie));
}

bool UHoverAttackSlotSubsystem::ProjectSlotPoint(const FVector &Point, FVector &OutPoint) const
{
    auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld());
    if (!Navigation)
    {
        OutPoint = Point;
        return true;
    }
    FNavLocation Projected;
    if (!Navigation->ProjectPointToNavigation(Point, Projected, FVector(60, 60, 200)))
        return false;
    OutPoint = Projected.Location;
    return true;
}

bool UHoverAttackSlotSubsystem::SectorPoint(const FRing &Ring, float BearingDegrees, float Radius, float MinRadius,
                                            FVector &Out) const
{
    // Street-side sectors can fall inside a facade. Walk inward toward the target before
    // giving the sector up; the caller blocks it for 2 s when every step fails.
    const FVector Direction = BearingDirection(BearingDegrees);
    for (float Step = Radius; Step >= MinRadius - KINDA_SMALL_NUMBER; Step -= 30.f)
        if (ProjectSlotPoint(Ring.Anchor + Direction * Step, Out))
            return true;
    return false;
}

bool UHoverAttackSlotSubsystem::BuildRoamPoint(const FRing &Ring, const AHoverNYCZombie *Zombie, FRoamPoint &Out) const
{
    FVector Approach = (Zombie->GetActorLocation() - Ring.Anchor).GetSafeNormal2D();
    if (Approach.IsNearlyZero())
        Approach = FVector::ForwardVector;
    const FVector Side(-Approach.Y, Approach.X, 0);
    const float Bias = Zombie->GetJitter().LateralBias;
    for (const float Distance : {FMath::FRandRange(400.f, 600.f), 400.f})
    {
        FVector Point;
        if (ProjectSlotPoint(Ring.Anchor + Approach * Distance + Side * Bias, Point))
        {
            Out.Location = Point;
            Out.Distance = FVector::Dist2D(Ring.Anchor, Point);
            Out.RefreshAt = GetWorld()->GetTimeSeconds() + FMath::FRandRange(2.5f, 3.5f);
            return true;
        }
    }
    return false;
}

float UHoverAttackSlotSubsystem::GetVendorReach2D(const AHoverNYCZombie *Zombie, const APawn *Target)
{
    const float AttackRange = Zombie && Zombie->ZombieData ? Zombie->ZombieData->Stats.AttackRange : 150.f;
    // Both capsules standing on the same floor: their centres differ by the half-height gap.
    const float Rise = FMath::Abs(CapsuleHalfHeightOf(Target) - CapsuleHalfHeightOf(Zombie));
    return FMath::Sqrt(FMath::Max(0.f, FMath::Square(AttackRange) - FMath::Square(Rise)));
}

float UHoverAttackSlotSubsystem::GetInnerRadius(const AHoverNYCZombie *Zombie, const APawn *Target) const
{
    if (!Zombie)
        return 0.f;
    const float AttackRange = Zombie->ZombieData ? Zombie->ZombieData->Stats.AttackRange : 150.f;
    const float Contact = CapsuleRadiusOf(Target) + CapsuleRadiusOf(Zombie);
    float Radius = FMath::Max(AttackRange - 30.f, Contact + 15.f);
    // The unmodified vendor tree tests 3D centre distance <= AttackRange. Keep the slot (plus
    // its acceptance radius) inside that test, or nothing on the inner ring would ever swing.
    if (Zombie->IsUsingVendorTree())
        Radius = FMath::Max(Contact + 5.f, FMath::Min(Radius, GetVendorReach2D(Zombie, Target) - 25.f));
    return Radius;
}

FHoverSlotClaim UHoverAttackSlotSubsystem::ClaimSlot(AHoverNYCZombie *Zombie, APawn *Target)
{
    FHoverSlotClaim Claim;
    if (!IsZombieUsable(Zombie) || !IsValid(Target))
        return Claim;
    Prune();
    for (auto &Pair : Rings)
        if (Pair.Key.Get() != Target)
            RemoveFromRing(Pair.Value, Zombie);

    FRing &Ring = Rings.FindOrAdd(TWeakObjectPtr<APawn>(Target));
    const FVector TargetLocation = Target->GetActorLocation();
    if (!Ring.bAnchored || FVector::Dist2D(Ring.Anchor, TargetLocation) > AnchorTolerance)
    {
        RingMoves += Ring.bAnchored ? 1 : 0;
        Ring.Anchor = TargetLocation;
        Ring.bAnchored = true;
    }
    const float Now = GetWorld()->GetTimeSeconds();
    const float Bearing = BearingOf(Ring.Anchor, Zombie->GetActorLocation());
    const float InnerRadius = GetInnerRadius(Zombie, Target);
    const auto *Definition = Zombie->GetNYCDefinition();
    const float QueueRadius = FMath::Max(Definition ? Definition->QueueRingRadius : 260.f, InnerRadius + 60.f);
    const float InnerStep = 360.f / InnerSectors;
    const float QueueStep = 360.f / QueueSectors;
    const auto Fill = [&Claim, &Ring](const FVector &Location, EHoverSlotKind Kind, int32 Sector) {
        Claim.Location = Location;
        Claim.Kind = Kind;
        Claim.Sector = Sector;
        Claim.StopRadius = FVector::Dist2D(Ring.Anchor, Location);
    };

    int32 OwnInner = INDEX_NONE, OwnQueue = INDEX_NONE;
    for (int32 Index = 0; Index < InnerSectors; ++Index)
        if (Ring.Inner[Index].Get() == Zombie)
            OwnInner = Index;
    for (int32 Index = 0; Index < QueueSectors; ++Index)
        if (Ring.Queue[Index].Get() == Zombie)
            OwnQueue = Index;

    // 1. Sticky inner sector.
    FVector Point;
    if (OwnInner != INDEX_NONE)
    {
        if (SectorPoint(Ring, OwnInner * InnerStep, InnerRadius, InnerRadius - 30.f, Point))
        {
            Fill(Point, EHoverSlotKind::Inner, OwnInner);
            return Claim;
        }
        Ring.InnerBlockedUntil[OwnInner] = Now + 2.f;
        Ring.Inner[OwnInner].Reset();
    }

    // 2. Free inner sector nearest the approach bearing (also promotes queue claimants).
    if (!Zombie->IsHeavySlot() || CountHeavyInner(Ring) < MaxHeavyInner)
    {
        TArray<int32, TInlineAllocator<InnerSectors>> Order;
        for (int32 Index = 0; Index < InnerSectors; ++Index)
            if (!Ring.Inner[Index].IsValid() && Now >= Ring.InnerBlockedUntil[Index])
                Order.Add(Index);
        Order.Sort([Bearing, InnerStep](int32 A, int32 B) {
            return AngleGap(A * InnerStep, Bearing) < AngleGap(B * InnerStep, Bearing);
        });
        for (const int32 Index : Order)
        {
            if (!SectorPoint(Ring, Index * InnerStep, InnerRadius, InnerRadius - 30.f, Point))
            {
                Ring.InnerBlockedUntil[Index] = Now + 2.f;
                continue;
            }
            RemoveFromRing(Ring, Zombie);
            Ring.Inner[Index] = SlotKey(Zombie);
            PeakHeavyInner = FMath::Max(PeakHeavyInner, CountHeavyInner(Ring));
            Fill(Point, EHoverSlotKind::Inner, Index);
            return Claim;
        }
    }

    // 3. Sticky queue sector, then 4. the nearest free one. Queue points never walk inside
    // the inner ring, so a queued zombie cannot pass the attack-range test without a sector.
    const float QueueFloor = InnerRadius + 30.f;
    if (OwnQueue != INDEX_NONE)
    {
        if (SectorPoint(Ring, OwnQueue * QueueStep, QueueRadius, QueueFloor, Point))
        {
            Fill(Point, EHoverSlotKind::Queue, OwnQueue);
            return Claim;
        }
        Ring.QueueBlockedUntil[OwnQueue] = Now + 2.f;
        Ring.Queue[OwnQueue].Reset();
    }
    {
        TArray<int32, TInlineAllocator<QueueSectors>> Order;
        for (int32 Index = 0; Index < QueueSectors; ++Index)
            if (!Ring.Queue[Index].IsValid() && Now >= Ring.QueueBlockedUntil[Index])
                Order.Add(Index);
        Order.Sort([Bearing, QueueStep](int32 A, int32 B) {
            return AngleGap(A * QueueStep, Bearing) < AngleGap(B * QueueStep, Bearing);
        });
        for (const int32 Index : Order)
        {
            if (!SectorPoint(Ring, Index * QueueStep, QueueRadius, QueueFloor, Point))
            {
                Ring.QueueBlockedUntil[Index] = Now + 2.f;
                continue;
            }
            RemoveFromRing(Ring, Zombie);
            Ring.Queue[Index] = SlotKey(Zombie);
            Fill(Point, EHoverSlotKind::Queue, Index);
            return Claim;
        }
    }

    // 5. Beyond the 20 sectors: a roaming point 400-600 cm out on the LateralBias side,
    // refreshed every 2.5-3.5 s, so the overflow keeps circling instead of idling.
    for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Inner)
        if (Slot.Get() == Zombie)
            Slot.Reset();
    for (TWeakObjectPtr<AHoverNYCZombie> &Slot : Ring.Queue)
        if (Slot.Get() == Zombie)
            Slot.Reset();
    FRoamPoint *Roam = Ring.Roaming.Find(SlotKey(Zombie));
    if (!Roam || Now >= Roam->RefreshAt)
    {
        FRoamPoint Fresh;
        if (BuildRoamPoint(Ring, Zombie, Fresh))
            Roam = &Ring.Roaming.Add(SlotKey(Zombie), Fresh);
    }
    if (Roam)
    {
        Claim.Location = Roam->Location;
        Claim.Kind = EHoverSlotKind::Roam;
        Claim.Sector = INDEX_NONE;
        Claim.StopRadius = Roam->Distance;
    }
    return Claim;
}

void UHoverAttackSlotSubsystem::ReleaseSlot(AHoverNYCZombie *Zombie)
{
    for (auto &Pair : Rings)
        RemoveFromRing(Pair.Value, Zombie);
}

bool UHoverAttackSlotSubsystem::TryAcquireAttackToken(AHoverNYCZombie *Zombie)
{
    if (!IsZombieUsable(Zombie))
        return false;
    Prune();
    // A boss carries its own token outside the pool: its swings never starve the adds, and
    // the adds never lock it out.
    if (Zombie->IsBoss())
    {
        BossTokens.Add(SlotKey(Zombie));
        return true;
    }
    if (Tokens.Contains(SlotKey(Zombie)))
        return true;
    if (Tokens.Num() >= GetTokenLimit())
        return false;
    Tokens.Add(SlotKey(Zombie));
    PeakTokens = FMath::Max(PeakTokens, Tokens.Num());
    return true;
}

void UHoverAttackSlotSubsystem::ReleaseAttackToken(AHoverNYCZombie *Zombie)
{
    Tokens.Remove(SlotKey(Zombie));
    BossTokens.Remove(SlotKey(Zombie));
}

bool UHoverAttackSlotSubsystem::HasAttackToken(const AHoverNYCZombie *Zombie) const
{
    return Tokens.Contains(SlotKey(Zombie)) || BossTokens.Contains(SlotKey(Zombie));
}

bool UHoverAttackSlotSubsystem::IsInInnerRing(const AHoverNYCZombie *Zombie) const
{
    for (const auto &Pair : Rings)
        for (const TWeakObjectPtr<AHoverNYCZombie> &Slot : Pair.Value.Inner)
            if (Slot.Get() == Zombie)
                return true;
    return false;
}

void UHoverAttackSlotSubsystem::SetTokenBudget(int32 Normal, int32 Horde)
{
    NormalTokens = FMath::Max(1, Normal);
    HordeTokens = FMath::Max(1, Horde);
}

void UHoverAttackSlotSubsystem::SetHordeRound(bool bHorde)
{
    bHordeRound = bHorde;
}

void UHoverAttackSlotSubsystem::SetMaxLiveCorpses(int32 Count)
{
    MaxLiveCorpses = FMath::Max(0, Count);
}

int32 UHoverAttackSlotSubsystem::GetTokenLimit() const
{
    return bHordeRound ? HordeTokens : NormalTokens;
}

int32 UHoverAttackSlotSubsystem::GetTokensInUse() const
{
    int32 Count = 0;
    for (const TWeakObjectPtr<AHoverNYCZombie> &Token : Tokens)
        Count += IsZombieUsable(Token.Get()) ? 1 : 0;
    return Count;
}

int32 UHoverAttackSlotSubsystem::GetHeavyInnerCount(const APawn *Target) const
{
    for (const auto &Pair : Rings)
        if (Pair.Key.Get() == Target)
            return CountHeavyInner(Pair.Value);
    return 0;
}

void UHoverAttackSlotSubsystem::RegisterCorpse(AActor *Corpse)
{
    Corpses.RemoveAll([](const TWeakObjectPtr<AActor> &Entry) { return !Entry.IsValid(); });
    if (!IsValid(Corpse))
        return;
    Corpses.AddUnique(Corpse);
    // The vendor Die() has already set the 15 s CorpseLifespan; only the overflow shortens it.
    while (MaxLiveCorpses > 0 && Corpses.Num() > MaxLiveCorpses)
    {
        if (AActor *Oldest = Corpses[0].Get())
            Oldest->SetLifeSpan(1.f);
        Corpses.RemoveAt(0);
    }
}

int32 UHoverAttackSlotSubsystem::GetLiveCorpseCount() const
{
    int32 Count = 0;
    for (const TWeakObjectPtr<AActor> &Entry : Corpses)
        Count += Entry.IsValid() ? 1 : 0;
    return Count;
}

void UHoverAttackSlotSubsystem::ApplyNYCCrowdTuning(UWorld *World)
{
    UCrowdManager *Crowd = World ? UCrowdManager::GetCurrent(World) : nullptr;
    if (!Crowd)
    {
        UE_LOG(LogTemp, Warning, TEXT("HOVER_NYC_CROWD manager=none"));
        return;
    }
    if (Crowd->IsA<UHoverNYCCrowdManager>())
    {
        UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_CROWD manager=%s source=class"), *Crowd->GetClass()->GetName());
        return;
    }
    // The config properties are protected and UCrowdManager is MinimalAPI, so write this world's
    // live instance through reflection. The engine CDO (and every other map) is untouched.
    bool bClamp = false, bResolve = false;
    if (auto *Property = FindFProperty<FFloatProperty>(UCrowdManager::StaticClass(), TEXT("SeparationDirClamp")))
    {
        Property->SetPropertyValue_InContainer(Crowd, .3f);
        bClamp = true;
    }
    if (auto *Property = FindFProperty<FBoolProperty>(UCrowdManager::StaticClass(), TEXT("bResolveCollisions")))
    {
        Property->SetPropertyValue_InContainer(Crowd, true);
        bResolve = true;
    }
    // Re-push an existing avoidance entry so the crowd refreshes its parameters where the
    // engine re-reads them there. Whether SeparationDirClamp is re-read live is unverified.
    FCrowdAvoidanceConfig Config;
    const bool bRefreshed = Crowd->GetAvoidanceConfig(0, Config) && Crowd->SetAvoidanceConfig(0, Config);
    UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_CROWD manager=%s source=reflection clamp=%d resolve=%d refreshed=%d"),
           *Crowd->GetClass()->GetName(), bClamp ? 1 : 0, bResolve ? 1 : 0, bRefreshed ? 1 : 0);
}

void UHoverNYCCrowdManager::PostInitProperties()
{
    Super::PostInitProperties();
    // After the config load, so a [/Script/AIModule.CrowdManager] section cannot override it.
    SeparationDirClamp = .3f;
    bResolveCollisions = true;
}
