#include "HoverNYCZombie.h"
#include "HoverPilot.h"
#include "Animation/AnimMontage.h"
#include "BehaviorTree/BehaviorTreeComponent.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "Animation/AnimInstance.h"
#include "Engine/DamageEvents.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Navigation/CrowdFollowingComponent.h"
#include "Navigation/PathFollowingComponent.h"
#include "NavMesh/RecastNavMesh.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "TimerManager.h"
#include "Zombies/ZE_ZombieSettings.h"

const FName AHoverNYCZombieAI::Key_AttackSlotLocation(TEXT("AttackSlotLocation"));

namespace
{
// Role Boss (StoneGolem, Giant Kid). The Alpha Brute elite keeps Role Brute and is never a boss.
bool IsBossDefinition(const UHoverCyberZombieDefinition *Definition)
{
    return Definition && Definition->Role == EHoverZombieRole::Boss;
}

float CollisionHalfHeight(const AActor *Actor)
{
    if (const auto *Capsule = Actor ? Cast<UCapsuleComponent>(Actor->GetRootComponent()) : nullptr)
        return Capsule->GetScaledCapsuleHalfHeight();
    return Actor ? Actor->GetSimpleCollisionHalfHeight() : 0.f;
}
} // namespace

// ---------------------------------------------------------------------------------------------
// UHoverNYCNavigationSystem

void UHoverNYCNavigationSystem::PostInitProperties()
{
    Super::PostInitProperties();
    // One agent for every role (a single navmesh keeps the heavies inside crowd steering), sized
    // for the tallest Stage 1 unit. The step height is an override, so the resolution params keep
    // their own value where none is set.
    FNavDataConfig Agent;
    if (SupportedAgents.Num())
        Agent = SupportedAgents[0];
    else
    {
        Agent.Name = TEXT("Default");
        Agent.SetNavDataClass(ARecastNavMesh::StaticClass());
    }
    Agent.AgentRadius = 55.f;
    Agent.AgentHeight = 320.f;
    Agent.AgentStepHeight = 50.f;
    SupportedAgents.Reset();
    SupportedAgents.Add(Agent);
    CrowdManagerClass = UHoverNYCCrowdManager::StaticClass();
}

// ---------------------------------------------------------------------------------------------
// AHoverNYCZombie

AHoverNYCZombie::AHoverNYCZombie()
{
    AIControllerClass = AHoverNYCZombieAI::StaticClass();
    // BP_CyberZombie supplied the vendor AnimClass. The native class must too: without an anim
    // instance the mesh sits in its reference pose, PlayAnimMontage returns 0 and the vendor
    // PerformAttack never swings, so the AttackHit notify (and all damage) never happens.
    static ConstructorHelpers::FClassFinder<UAnimInstance> ZombieAnim(
        TEXT("/Game/ZESP/ZE/Animations/Zombies/Zombie_001/ABP_ZombieMaster"));
    if (ZombieAnim.Succeeded() && !GetMesh()->AnimClass)
        GetMesh()->SetAnimInstanceClass(ZombieAnim.Class);
}

const FHoverNYCJitter &AHoverNYCZombie::GetJitter() const
{
    if (!Jitter.bRolled)
    {
        // Bosses keep the same centre with half the spread.
        const float Spread = IsBoss() ? .5f : 1.f;
        const auto Roll = [Spread](float Low, float High) {
            const float Middle = (Low + High) * .5f;
            return FMath::FRandRange(Middle - (Middle - Low) * Spread, Middle + (High - Middle) * Spread);
        };
        Jitter.Speed = Roll(.92f, 1.08f);
        Jitter.Accel = Roll(.8f, 1.25f);
        Jitter.Yaw = Roll(.8f, 1.2f);
        Jitter.Cooldown = FMath::FRandRange(0.f, .4f * Spread);
        Jitter.Separation = Roll(.7f, 1.3f);
        Jitter.LateralBias = (FMath::RandBool() ? 1.f : -1.f) * FMath::FRandRange(80.f, 80.f + 120.f * Spread);
        Jitter.Acceptance = Roll(.75f, 1.25f);
        Jitter.bRolled = true;
    }
    return Jitter;
}

const UHoverCyberZombieDefinition *AHoverNYCZombie::GetNYCDefinition() const
{
    return Cast<UHoverCyberZombieDefinition>(ZombieData);
}

bool AHoverNYCZombie::IsBoss() const
{
    return IsBossDefinition(GetNYCDefinition());
}

bool AHoverNYCZombie::IsHeavySlot() const
{
    const auto *Definition = GetNYCDefinition();
    return Definition &&
           (Definition->bHeavySlot || Definition->Role == EHoverZombieRole::Brute || IsBossDefinition(Definition));
}

bool AHoverNYCZombie::IsUsingVendorTree() const
{
    const auto *AI = Cast<AHoverNYCZombieAI>(GetController());
    return !AI || AI->IsUsingVendorTree();
}

bool AHoverNYCZombie::CanStartAttack() const
{
    const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
    return !bIsDead && !bIsAttacking && !bSwingPending && ZombieData && Now >= NextAttackTime && Now >= VendorResetAt;
}

void AHoverNYCZombie::BeginPlay()
{
    // The base sizes the capsule and mesh, sets the role yaw/acceleration and calls the mode's
    // OnZombieSpawned (speed tier) before this runs.
    Super::BeginPlay();
    auto *Movement = GetCharacterMovement();
    const auto *Definition = GetNYCDefinition();
    if (Definition && Definition->AppearanceMesh)
    {
        // Crawler groundwork. Idempotent: when the base adapter already honours
        // CapsuleHalfHeight the capsule matches and nothing changes here.
        if (Definition->CapsuleHalfHeight > 0)
        {
            UCapsuleComponent *Capsule = GetCapsuleComponent();
            const float Radius = Capsule->GetUnscaledCapsuleRadius();
            const float Current = Capsule->GetUnscaledCapsuleHalfHeight();
            const float Desired = FMath::Max(Definition->CapsuleHalfHeight, Radius);
            if (!FMath::IsNearlyEqual(Current, Desired, .5f))
            {
                Capsule->SetCapsuleSize(Radius, Desired);
                // The base placed the mesh bottom on the old capsule bottom; keep it there.
                FVector Offset = GetMesh()->GetRelativeLocation();
                Offset.Z += Current - Desired;
                GetMesh()->SetRelativeLocation(Offset);
                Movement->UpdateNavAgent(*Capsule);
            }
        }
        if (Definition->RotationYaw > 0)
            Movement->RotationRate.Yaw = Definition->RotationYaw;
        if (Definition->MaxAcceleration > 0)
            Movement->MaxAcceleration = Definition->MaxAcceleration;
    }
    const FHoverNYCJitter &Roll = GetJitter();
    Movement->RotationRate.Yaw *= Roll.Yaw;
    Movement->MaxAcceleration *= Roll.Accel;
    // Possession ran before this BeginPlay, so the crowd agent registered with the class-default
    // capsule. Re-apply the agent settings now that the capsule has its final size.
    if (auto *AI = Cast<AHoverNYCZombieAI>(GetController()))
        AI->ApplyCrowdSettings();
}

void AHoverNYCZombie::EndPlay(const EEndPlayReason::Type Reason)
{
    ReleaseCrowdClaims();
    Super::EndPlay(Reason);
}

void AHoverNYCZombie::ReleaseCrowdClaims()
{
    if (UWorld *World = GetWorld())
    {
        World->GetTimerManager().ClearTimer(AttackEndTimer);
        World->GetTimerManager().ClearTimer(DeferredSwingTimer);
    }
    if (bSwingPending)
    {
        bSwingPending = false;
        bIsAttacking = false;
        SetBlackboardAttacking(false);
    }
    if (auto *Slots = UHoverAttackSlotSubsystem::Get(this))
    {
        Slots->ReleaseSlot(this);
        Slots->ReleaseAttackToken(this);
    }
    SetCrowdSimulation(false);
}

void AHoverNYCZombie::SetCrowdSimulation(bool bAttacking) const
{
    const auto *AI = Cast<AAIController>(GetController());
    auto *Crowd = AI ? Cast<UCrowdFollowingComponent>(AI->GetPathFollowingComponent()) : nullptr;
    if (!Crowd)
        return;
    // A swinging zombie stays an obstacle for the others but stops steering itself.
    const ECrowdSimulationState State = Crowd->GetCrowdSimulationState();
    if (bAttacking && State == ECrowdSimulationState::Enabled)
        Crowd->SetCrowdSimulationState(ECrowdSimulationState::ObstacleOnly);
    else if (!bAttacking && State == ECrowdSimulationState::ObstacleOnly)
        Crowd->SetCrowdSimulationState(ECrowdSimulationState::Enabled);
}

void AHoverNYCZombie::SetBlackboardAttacking(bool bAttacking) const
{
    if (auto *AI = Cast<AAIController>(GetController()))
        if (UBlackboardComponent *Board = AI->GetBlackboardComponent())
            Board->SetValueAsBool(AZE_ZombieAIController::Key_IsAttacking, bAttacking);
}

void AHoverNYCZombie::PerformAttack(AActor *Target)
{
    // The vendor task reports Succeeded whatever happens here; the token caps how many swing.
    if (!CanStartAttack())
        return;
    auto *Slots = UHoverAttackSlotSubsystem::Get(this);
    if (Slots && !Slots->TryAcquireAttackToken(this))
    {
        ++TokenDenials;
        return;
    }
    const float Delay = IsUsingVendorTree() ? GetJitter().Cooldown : 0.f;
    if (Delay <= .02f)
    {
        StartSwing(Target);
        return;
    }
    // The vendor BT Wait is a literal, so under BT_Zombie the cadence jitter can only shift the
    // swing start. Hold the attacking state meanwhile so the tree does not re-enter.
    bSwingPending = true;
    bIsAttacking = true;
    SetBlackboardAttacking(true);
    const TWeakObjectPtr<AActor> WeakTarget(Target);
    GetWorldTimerManager().SetTimer(
        DeferredSwingTimer,
        FTimerDelegate::CreateWeakLambda(this,
                                         [this, WeakTarget] {
                                             bSwingPending = false;
                                             bIsAttacking = false;
                                             if (bIsDead || !WeakTarget.IsValid())
                                             {
                                                 SetBlackboardAttacking(false);
                                                 if (auto *SlotSystem = UHoverAttackSlotSubsystem::Get(this))
                                                     SlotSystem->ReleaseAttackToken(this);
                                                 return;
                                             }
                                             StartSwing(WeakTarget.Get());
                                         }),
        Delay, false);
}

void AHoverNYCZombie::StartSwing(AActor *Target)
{
    auto *Slots = UHoverAttackSlotSubsystem::Get(this);
    // Zombies parked on the slot ring only face their move direction; square up to the target so
    // the vendor forward sweep (40-190 cm, radius 50) actually covers it.
    if (Target)
    {
        const FVector To = Target->GetActorLocation() - GetActorLocation();
        if (!To.IsNearlyZero())
            SetActorRotation(FRotator(0.f, To.Rotation().Yaw, 0.f));
    }
    Super::PerformAttack(Target);
    if (!bIsAttacking)
    {
        // Vendor early-out (no montage or a zero-length one): nothing is swinging.
        SetBlackboardAttacking(false);
        if (Slots)
            Slots->ReleaseAttackToken(this);
        return;
    }
    const float Now = GetWorld()->GetTimeSeconds();
    const UAnimMontage *Montage = GetCurrentMontage();
    // Same length the vendor reset timer uses (PlayAnimMontage's return at rate 1).
    const float Duration = Montage ? Montage->GetPlayLength() / FMath::Max(Montage->RateScale, .01f) : 1.f;
    ++AttackSwings;
    AttackStartTime = Now;
    VendorResetAt = Now + Duration;
    SetCrowdSimulation(true);
    GetWorldTimerManager().SetTimer(AttackEndTimer, FTimerDelegate::CreateWeakLambda(this, [this] { EndSwing(); }),
                                    FMath::Max(Duration, .05f), false);
}

void AHoverNYCZombie::EndSwing()
{
    if (auto *Slots = UHoverAttackSlotSubsystem::Get(this))
        Slots->ReleaseAttackToken(this);
    SetCrowdSimulation(false);
    const float Cooldown = ZombieData ? ZombieData->Stats.AttackCooldown : 1.5f;
    NextAttackTime = GetWorld()->GetTimeSeconds() + Cooldown + GetJitter().Cooldown;
}

void AHoverNYCZombie::CancelSwing()
{
    const bool bWasSwinging = !bSwingPending && bIsAttacking;
    GetWorldTimerManager().ClearTimer(DeferredSwingTimer);
    GetWorldTimerManager().ClearTimer(AttackEndTimer);
    bSwingPending = false;
    bIsAttacking = false;
    SetBlackboardAttacking(false);
    if (auto *Slots = UHoverAttackSlotSubsystem::Get(this))
        Slots->ReleaseAttackToken(this);
    SetCrowdSimulation(false);
    // Stop the swing so its hit notify cannot land; the vendor hit reaction plays next. The
    // vendor reset timer still runs, so VendorResetAt keeps the next swing from starting early.
    if (bWasSwinging)
        StopAnimMontage();
    ++FlinchCancels;
}

float AHoverNYCZombie::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController, AActor *Causer)
{
    const bool bWasAlive = !bIsDead;
    // Flinch rule without editing the vendor (§9 zero-edit route): LastHitTime = Now - 1 forces
    // the vendor hit reaction (its 0.8 s gate passes), LastHitTime = Now suppresses it, and a
    // swing still inside its wind-up is cleared before the vendor checks !bIsAttacking.
    if (bWasAlive && Damage > 0 && SurvivalComponent && ZombieData)
    {
        const float Now = GetWorld()->GetTimeSeconds();
        const auto *Definition = GetNYCDefinition();
        const bool bHasReactions = !ZombieData->HitReactionMontages.IsEmpty();
        const float MaxHealth = FMath::Max(1.f, SurvivalComponent->GetMaxHealth());
        const float Windup = Definition ? Definition->WindupSeconds : .5f;
        const bool bInWindup = bSwingPending || (bIsAttacking && Now - AttackStartTime <= Windup);
        const bool bEligible = bHasReactions && Damage < SurvivalComponent->GetHealth() &&
                               (!Definition || Definition->bFlinchOnHit) &&
                               Damage >= (Definition ? Definition->FlinchDamageFraction : .1f) * MaxHealth &&
                               Now - LastMontageFlinch >= (Definition ? Definition->FlinchMontageCooldown : .35f) &&
                               (!bIsAttacking || bInWindup);
        if (bEligible)
        {
            if (bIsAttacking)
                CancelSwing();
            LastHitTime = Now - 1.f;
            LastMontageFlinch = Now;
            ++MontageFlinches;
        }
        else
        {
            LastHitTime = Now;
            SuppressedFlinches += bHasReactions ? 1 : 0;
        }
    }
    // Cyber adapter: insta-kill, blood, vendor health/death/loot, retarget and gold.
    const float Result = Super::TakeDamage(Damage, Event, EventController, Causer);
    // The vendor Die() ran synchronously inside Super and has already set the corpse lifespan.
    if (bWasAlive && bIsDead)
        HandleKilled();
    return Result;
}

void AHoverNYCZombie::HandleKilled()
{
    ReleaseCrowdClaims();
    if (auto *Slots = UHoverAttackSlotSubsystem::Get(this))
        Slots->RegisterCorpse(this);
}

// ---------------------------------------------------------------------------------------------
// AHoverNYCZombieAI

AHoverNYCZombieAI::AHoverNYCZombieAI() {}

void AHoverNYCZombieAI::OnPossess(APawn *InPawn)
{
    // Cyber: crowd follower swap before the tree starts; vendor: perception and BT_Zombie.
    Super::OnPossess(InPawn);
    const UBlackboardComponent *Board = GetBlackboardComponent();
    bVendorTree = !Board || Board->GetKeyID(Key_AttackSlotLocation) == FBlackboard::InvalidKey;
    // Spread the 0.5 s retarget tick so a swarm does not re-path in the same frame.
    SetActorTickInterval(.5f * FMath::FRandRange(.85f, 1.15f));
    CurrentClaim = FHoverSlotClaim();
    bHasIssuedSlot = false;
    bFarApproachActive = false;
    ApplyCrowdSettings();
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_NYC_AI possess=%s tree=%s"), *GetNameSafe(InPawn),
           bVendorTree ? TEXT("vendor") : TEXT("owned"));
}

void AHoverNYCZombieAI::OnUnPossess()
{
    auto *Zombie = Cast<AHoverNYCZombie>(GetPawn());
    Super::OnUnPossess();
    if (Zombie)
        Zombie->ReleaseCrowdClaims();
    CurrentClaim = FHoverSlotClaim();
    ChaseTarget.Reset();
    bHasIssuedSlot = false;
    // The vendor Die() unpossesses but never destroys its controller, which would keep ticking
    // with perception for the rest of the session.
    SetLifeSpan(.1f);
}

void AHoverNYCZombieAI::ApplyCrowdSettings()
{
    auto *Crowd = Cast<UCrowdFollowingComponent>(GetPathFollowingComponent());
    auto *Zombie = Cast<AHoverNYCZombie>(GetPawn());
    if (!Crowd || !Zombie)
        return;
    const auto *Definition = Zombie->GetNYCDefinition();
    const float Radius =
        Definition ? Definition->CapsuleRadius : Zombie->GetCapsuleComponent()->GetScaledCapsuleRadius();
    const float Weight = (Definition ? Definition->SeparationWeight : 10.f) * Zombie->GetJitter().Separation;
    // Overrides the Cyber 3 / 500 / High set when the follower was created.
    Crowd->SetCrowdSeparation(true, false);
    Crowd->SetCrowdSeparationWeight(Weight, false);
    Crowd->SetCrowdCollisionQueryRange(3.f * Radius + 150.f, false);
    Crowd->SetCrowdAvoidanceQuality(ECrowdAvoidanceQuality::Medium, false);
    Crowd->SetCrowdAvoidanceRangeMultiplier(1.5f, false);
    Crowd->SetCrowdPathOptimizationRange(1000.f, false);
    Crowd->SetCrowdSlowdownAtGoal(false, false);
    Crowd->SetCrowdObstacleAvoidance(true, false);
    Crowd->SetCrowdAnticipateTurns(true, false);
    Crowd->UpdateCrowdAgentParams();
    // Detour crowd steering and RVO must not both drive the same agent.
    if (auto *Movement = Zombie->GetCharacterMovement(); Movement && Movement->bUseRVOAvoidance)
    {
        UE_LOG(LogTemp, Warning, TEXT("HOVER_NYC_AI rvo_enabled=%s (disabled)"), *Zombie->GetName());
        Movement->SetAvoidanceEnabled(false);
    }
}

APawn *AHoverNYCZombieAI::FindChaseTarget() const
{
    // Hoverboard riders stay the pilot pawn, so they stay targeted and damageable. The downed
    // grace window (player slice) will return nullptr here.
    APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (Cast<AHoverPilot>(Player))
        return Player;
    for (TActorIterator<AHoverPilot> It(GetWorld()); It; ++It)
        return *It;
    return Player;
}

float AHoverNYCZombieAI::GetAcceptanceRadius(const FHoverSlotClaim &Claim) const
{
    const auto *Zombie = Cast<AHoverNYCZombie>(GetPawn());
    const float Jitter = Zombie ? Zombie->GetJitter().Acceptance : 1.f;
    switch (Claim.Kind)
    {
    case EHoverSlotKind::Inner: {
        float Radius = 40.f * Jitter;
        // Under the vendor tree the stop point (slot + acceptance) must pass its 3D range test.
        if (bVendorTree && Zombie && ChaseTarget.IsValid())
            Radius = FMath::Clamp(UHoverAttackSlotSubsystem::GetVendorReach2D(Zombie, ChaseTarget.Get()) - 10.f -
                                      Claim.StopRadius,
                                  10.f, Radius);
        return Radius;
    }
    case EHoverSlotKind::Queue:
        return 60.f;
    case EHoverSlotKind::Roam:
        return 120.f;
    default:
        return 40.f;
    }
}

void AHoverNYCZombieAI::UpdateDestination(AHoverNYCZombie *Zombie, APawn *Target)
{
    auto *Slots = UHoverAttackSlotSubsystem::Get(this);
    const float Now = GetWorld()->GetTimeSeconds();
    const FVector Self = Zombie->GetActorLocation();
    const FVector Goal = Target->GetActorLocation();
    const float Distance = FVector::Dist2D(Self, Goal);
    if (Distance > 800.f && !LineOfSightTo(Target))
    {
        // Out of sight and far: zig-zag toward a reachable point near the target instead of
        // holding a sector, so the ring stays free for the zombies that can use it.
        if (Slots)
            Slots->ReleaseSlot(Zombie);
        const bool bStale = !bFarApproachActive || Now >= NextApproachRefresh ||
                            FVector::Dist2D(Goal, ApproachTargetAt) > 300.f ||
                            FVector::Dist2D(Self, ApproachPoint) < 150.f;
        if (bStale)
        {
            FVector Approach = (Self - Goal).GetSafeNormal2D();
            if (Approach.IsNearlyZero())
                Approach = FVector::ForwardVector;
            const FVector Side(-Approach.Y, Approach.X, 0);
            ApproachSide = -ApproachSide;
            const FVector Desired = Goal + Approach * FMath::Min(Distance * .5f, 400.f) +
                                    Side * Zombie->GetJitter().LateralBias * ApproachSide;
            FVector Point = Goal;
            if (Slots && !Slots->ProjectSlotPoint(Desired, Point) && !Slots->ProjectSlotPoint(Goal, Point))
                Point = Goal;
            ApproachPoint = Point;
            ApproachTargetAt = Goal;
            NextApproachRefresh = Now + FMath::FRandRange(2.5f, 3.5f);
            bFarApproachActive = true;
        }
        CurrentClaim.Location = ApproachPoint;
        CurrentClaim.Kind = EHoverSlotKind::Roam;
        CurrentClaim.Sector = INDEX_NONE;
        CurrentClaim.StopRadius = FVector::Dist2D(Goal, ApproachPoint);
        return;
    }
    bFarApproachActive = false;
    CurrentClaim = Slots ? Slots->ClaimSlot(Zombie, Target) : FHoverSlotClaim();
}

void AHoverNYCZombieAI::Tick(float DeltaSeconds)
{
    // Cyber: retarget to the player pawn, LOD, speed/health rewrite, perception radii.
    Super::Tick(DeltaSeconds);
    auto *Zombie = Cast<AHoverNYCZombie>(GetPawn());
    auto *Board = GetBlackboardComponent();
    if (!Zombie || Zombie->IsKilled() || !Board || !Zombie->ZombieData)
        return;

    // 1. Target.
    APawn *Target = FindChaseTarget();
    if (!Target)
    {
        Board->ClearValue(Key_TargetEnemy);
        ChaseTarget.Reset();
        CurrentClaim = FHoverSlotClaim();
        Zombie->ReleaseCrowdClaims();
        return;
    }
    if (bDirectChaseMode && Board->GetValueAsObject(Key_TargetEnemy) != Target)
        SetTargetEnemy(Target);
    ChaseTarget = Target;

    // 2-3. Destination: far approach or a ring claim, mirrored into the owned-BT key.
    UpdateDestination(Zombie, Target);
    if (CurrentClaim.IsValid() && Board->GetKeyID(Key_AttackSlotLocation) != FBlackboard::InvalidKey)
        Board->SetValueAsVector(Key_AttackSlotLocation, CurrentClaim.Location);

    // 4. Under the vendor tree the move goal is fixed when MoveTo is issued. When the claim has
    // moved further than the observer tolerance, abort so the tree re-runs MoveTo, which the
    // override below rewrites to the new slot.
    if (bVendorTree && bHasIssuedSlot && CurrentClaim.IsValid() && !Zombie->IsSwingActive())
        if (UPathFollowingComponent *Path = GetPathFollowingComponent();
            Path && Path->GetStatus() == EPathFollowingStatus::Moving &&
            FVector::Dist(CurrentClaim.Location, LastIssuedSlot) > UHoverAttackSlotSubsystem::AnchorTolerance)
        {
            bHasIssuedSlot = false;
            ++SlotReissues;
            Path->AbortMove(*this, FPathFollowingResultFlags::ForcedScript);
        }

    // 5. Cadence key for BT_NYCZombie's Wait (overrides the base write in the same frame).
    const auto &Stats = Zombie->ZombieData->Stats;
    Board->SetValueAsFloat(Key_AttackCooldown, Stats.AttackCooldown + Zombie->GetJitter().Cooldown);

    // Pursuit speed: the spawn-rolled tier (or the DA run speed) with per-instance jitter,
    // clamped to the definition maximum. NYC ignores the wave speed scale; Tuning.Speed stays.
    const bool bPursuing = Board->GetValueAsObject(Key_TargetEnemy) != nullptr;
    float Speed = bPursuing ? (Zombie->SpeedTier > 0 ? Zombie->SpeedTier : Stats.RunSpeed) : Stats.WalkSpeed;
    Speed *= Zombie->GetJitter().Speed;
    if (const auto *Definition = Zombie->GetNYCDefinition())
        Speed = FMath::Min(Speed, Definition->MaximumRunSpeed);
    if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        Speed *= Mode->Tuning.Speed;
    Zombie->GetCharacterMovement()->MaxWalkSpeed = Speed;
}

FPathFollowingRequestResult AHoverNYCZombieAI::MoveTo(const FAIMoveRequest &MoveRequest, FNavPathSharedPtr *OutPath)
{
    auto *Zombie = Cast<AHoverNYCZombie>(GetPawn());
    APawn *Target = ChaseTarget.IsValid() ? ChaseTarget.Get() : FindChaseTarget();
    // Only the vendor tree's MoveTo(TargetEnemy) is rewritten; every other request (and every
    // request under BT_NYCZombie, which already moves to AttackSlotLocation) passes through.
    if (!bVendorTree || !Zombie || Zombie->IsKilled() || !Target || !MoveRequest.IsMoveToActorRequest() ||
        MoveRequest.GetGoalActor() != Target)
        return Super::MoveTo(MoveRequest, OutPath);
    ChaseTarget = Target;
    if (!CurrentClaim.IsValid())
        UpdateDestination(Zombie, Target);
    if (!CurrentClaim.IsValid())
        return Super::MoveTo(MoveRequest, OutPath);

    // A fresh location request: FAIMoveRequest's goal setters only apply to an uninitialised
    // request, so the actor request's options are copied across instead.
    FAIMoveRequest Slot(CurrentClaim.Location);
    Slot.SetNavigationFilter(MoveRequest.GetNavigationFilter())
        .SetUsePathfinding(MoveRequest.IsUsingPathfinding())
        .SetAllowPartialPath(MoveRequest.IsUsingPartialPaths())
        .SetRequireNavigableEndLocation(MoveRequest.IsNavigableEndLocationRequired())
        .SetApplyCostLimitFromHeuristic(MoveRequest.IsApplyingCostLimitFromHeuristic(),
                                        MoveRequest.GetCostLimitFactor(), MoveRequest.GetMinimumCostLimit())
        .SetCanStrafe(MoveRequest.CanStrafe())
        .SetUserData(MoveRequest.GetUserData())
        .SetUserFlags(MoveRequest.GetUserFlags())
        .SetStartFromPreviousPath(MoveRequest.ShouldStartFromPreviousPath())
        .SetProjectGoalLocation(true)
        .SetReachTestIncludesAgentRadius(false)
        .SetReachTestIncludesGoalRadius(false)
        .SetAcceptanceRadius(GetAcceptanceRadius(CurrentClaim));
    LastIssuedSlot = CurrentClaim.Location;
    bHasIssuedSlot = true;
    ++MoveToRewrites;
    return Super::MoveTo(Slot, OutPath);
}

// ---------------------------------------------------------------------------------------------
// Owned-BT nodes

UHoverBTTask_MoveToSlot::UHoverBTTask_MoveToSlot(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer)
{
    NodeName = TEXT("AFS: Move To Slot");
    // bObserveBlackboardValue is UPROPERTY() only (BTTask_MoveTo.h:88-89).
    bObserveBlackboardValue = true;
    AcceptableRadius = FValueOrBBKey_Float(40.f);
    ObservedBlackboardValueTolerance = FValueOrBBKey_Float(UHoverAttackSlotSubsystem::AnchorTolerance);
    bProjectGoalLocation = FValueOrBBKey_Bool(true);
    bReachTestIncludesAgentRadius = FValueOrBBKey_Bool(false);
    BlackboardKey.SelectedKeyName = AHoverNYCZombieAI::Key_AttackSlotLocation;
}

UHoverBTService_AttackSlot::UHoverBTService_AttackSlot()
{
    NodeName = TEXT("AFS: Check Attack Slot");
}

void UHoverBTService_AttackSlot::TickNode(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory, float DeltaSeconds)
{
    // Skip the vendor 3D test; this replaces it.
    UBTService::TickNode(OwnerComp, NodeMemory, DeltaSeconds);
    AAIController *Controller = OwnerComp.GetAIOwner();
    UBlackboardComponent *Board = OwnerComp.GetBlackboardComponent();
    if (!Controller || !Board)
        return;
    auto *Zombie = Cast<AHoverNYCZombie>(Controller->GetPawn());
    const auto *Target = Cast<AActor>(Board->GetValueAsObject(TargetKey.SelectedKeyName));
    if (!Zombie || !Zombie->ZombieData || !Target)
    {
        Board->SetValueAsBool(CanAttackKey.SelectedKeyName, false);
        return;
    }
    const auto *TargetPawn = Cast<APawn>(Target);
    const auto *Slots = UHoverAttackSlotSubsystem::Get(Zombie);
    const float Inner =
        Slots && TargetPawn ? Slots->GetInnerRadius(Zombie, TargetPawn) : Zombie->ZombieData->Stats.AttackRange - 30.f;
    const bool bWasInRange = Board->GetValueAsBool(CanAttackKey.SelectedKeyName);
    const float Reach = Inner + 30.f + (bWasInRange ? 30.f : 0.f);
    const FVector Self = Zombie->GetActorLocation();
    const FVector Goal = Target->GetActorLocation();
    const float Stack = CollisionHalfHeight(Zombie) + CollisionHalfHeight(Target);
    Board->SetValueAsBool(CanAttackKey.SelectedKeyName,
                          FVector::Dist2D(Self, Goal) <= Reach && FMath::Abs(Self.Z - Goal.Z) <= Stack);
}

UHoverBTTask_ZombieAttack::UHoverBTTask_ZombieAttack()
{
    NodeName = TEXT("AFS: Zombie Attack (token)");
    bNotifyTick = true;
}

EBTNodeResult::Type UHoverBTTask_ZombieAttack::ExecuteTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory)
{
    const AAIController *Controller = OwnerComp.GetAIOwner();
    auto *Zombie = Controller ? Cast<AHoverNYCZombie>(Controller->GetPawn()) : nullptr;
    if (!Zombie)
        return Super::ExecuteTask(OwnerComp, NodeMemory);
    auto *Slots = UHoverAttackSlotSubsystem::Get(Zombie);
    if (Zombie->CanStartAttack() && (!Slots || Slots->TryAcquireAttackToken(Zombie)))
    {
        const EBTNodeResult::Type Result = Super::ExecuteTask(OwnerComp, NodeMemory);
        if (Result != EBTNodeResult::Succeeded || Zombie->IsSwingActive())
            return Result;
        // PerformAttack started nothing; do not keep a token without a swing.
        if (Slots)
            Slots->ReleaseAttackToken(Zombie);
    }
    // Latent failure, independent of the tree layout and without a per-frame token spin.
    CastInstanceNodeMemory<FRetryMemory>(NodeMemory)->Remaining = FMath::FRandRange(.25f, .4f);
    return EBTNodeResult::InProgress;
}

void UHoverBTTask_ZombieAttack::TickTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory, float DeltaSeconds)
{
    FRetryMemory *Memory = CastInstanceNodeMemory<FRetryMemory>(NodeMemory);
    Memory->Remaining -= DeltaSeconds;
    if (Memory->Remaining <= 0.f)
        FinishLatentTask(OwnerComp, EBTNodeResult::Failed);
}

EBTNodeResult::Type UHoverBTTask_ZombieAttack::AbortTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory)
{
    return EBTNodeResult::Aborted;
}

uint16 UHoverBTTask_ZombieAttack::GetInstanceMemorySize() const
{
    return sizeof(FRetryMemory);
}

void UHoverBTTask_ZombieAttack::InitializeMemory(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory,
                                                 EBTMemoryInit::Type InitType) const
{
    InitializeNodeMemory<FRetryMemory>(NodeMemory, InitType);
}

void UHoverBTTask_ZombieAttack::CleanupMemory(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory,
                                              EBTMemoryClear::Type CleanupType) const
{
    CleanupNodeMemory<FRetryMemory>(NodeMemory, CleanupType);
}
