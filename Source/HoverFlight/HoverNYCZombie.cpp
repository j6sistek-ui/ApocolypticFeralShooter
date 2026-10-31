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
#include "Animation/MorphTarget.h"
#include "Components/AudioComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"

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

// Diversity pass tuning (2026-10-31).
// AFS 2026-10-31 (review): square up to the target only inside attack range + 100 (left again past + 200), and
// only while swinging, roaring, nearly still, or moving roughly toward the target. The queue ring (260 cm) sits
// inside that radius and moves with the player, and the gait is a forward-only speed blend, so facing the target
// while the slot steering moves the zombie sideways or away would play the forward walk in reverse.
constexpr float FaceTargetEnter = 100.f;
constexpr float FaceTargetExit = 200.f;
constexpr float FaceStillSpeed = 40.f;      // cm/s; below this a zombie in range squares up (60 to stop)
constexpr float FaceStillSpeedHold = 60.f;
constexpr float FaceMoveCos = .5f;          // cos 60 deg: moving within 60 deg of the target direction
constexpr float FaceMoveCosHold = .2588f;   // cos 75 deg once already facing
constexpr float SightRoarRange = 2500.f;    // first sight of the player inside this rolls the roar
constexpr float FootstepRange = 2500.f;     // steps further than this from the player are skipped
constexpr float VocalAudibleRange = 3300.f; // inner 300 + falloff 3000 of the shared attenuation
constexpr float PainVocalInterval = 1.2f;

// Uniform roll in [Low, High] (order-insensitive), with the spread around the centre scaled.
float RollRange(const FVector2D &Range, float Spread)
{
    const float Low = FMath::Min(Range.X, Range.Y), High = FMath::Max(Range.X, Range.Y);
    const float Middle = (Low + High) * .5f;
    return FMath::FRandRange(Middle - (Middle - Low) * Spread, Middle + (High - Middle) * Spread);
}

template <typename T> T *PickRandom(const TArray<TObjectPtr<T>> &Items)
{
    TArray<T *, TInlineAllocator<16>> Valid;
    for (const TObjectPtr<T> &Item : Items)
        if (Item)
            Valid.Add(Item.Get());
    return Valid.Num() ? Valid[FMath::RandRange(0, Valid.Num() - 1)] : nullptr;
}

// One-shot blood: stops emitting after StopAfter and is removed after DestroyAfter even if the
// system loops (several Blood_VFX_Pack systems do).
void SpawnTimedBlood(UWorld *World, UNiagaraSystem *System, const FVector &Location, const FRotator &Rotation,
                     float Scale, float StopAfter, float DestroyAfter)
{
    if (!World || !System)
        return;
    UNiagaraComponent *Effect =
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Location, Rotation, FVector(FMath::Max(Scale, .01f)),
                                                       /*bAutoDestroy*/ true, /*bAutoActivate*/ true);
    if (!Effect)
        return;
    const TWeakObjectPtr<UNiagaraComponent> Weak(Effect);
    FTimerHandle StopHandle, CleanupHandle;
    World->GetTimerManager().SetTimer(
        StopHandle,
        [Weak]() {
            if (Weak.IsValid())
                Weak->Deactivate();
        },
        StopAfter, false);
    World->GetTimerManager().SetTimer(
        CleanupHandle,
        [Weak]() {
            if (Weak.IsValid())
                Weak->DestroyComponent();
        },
        DestroyAfter, false);
}

bool IsHeavyRole(const UHoverCyberZombieDefinition *Definition)
{
    return Definition && (Definition->Role == EHoverZombieRole::Brute || Definition->Role == EHoverZombieRole::Boss);
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
    // Owner 2026-10-31 "zombies walk backwards": the pawn followed the controller yaw (focus on the
    // player) while crowd/slot steering moved it elsewhere. The body now faces its movement, and
    // Tick squares it up to the target itself when close, swinging or roaring.
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->bUseControllerDesiredRotation = false;
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
    return !bIsDead && !bIsAttacking && !bSwingPending && !bRoaring && ZombieData && Now >= NextAttackTime &&
           Now >= VendorResetAt;
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

    // Facing fix (see the constructor). Re-applied here in case a Blueprint subclass or the
    // spawn path restored the ACharacter defaults.
    bUseControllerRotationYaw = false;
    Movement->bOrientRotationToMovement = true;
    Movement->bUseControllerDesiredRotation = false;
    static TWeakObjectPtr<UWorld> FacingLoggedWorld;
    if (FacingLoggedWorld.Get() != GetWorld())
    {
        FacingLoggedWorld = GetWorld();
        UE_LOG(LogTemp, Display,
               TEXT("HOVER_ZOMBIE_FACING_FIX zombie=%s bUseControllerRotationYaw=%d bOrientRotationToMovement=%d "
                    "bUseControllerDesiredRotation=%d face_target_within=attack_range+%.0f/+%.0f "
                    "face_when=swing|roar|speed<%.0f|heading<60deg rotation_yaw=%.0f"),
               *GetName(), bUseControllerRotationYaw ? 1 : 0, Movement->bOrientRotationToMovement ? 1 : 0,
               Movement->bUseControllerDesiredRotation ? 1 : 0, FaceTargetEnter, FaceTargetExit, FaceStillSpeed,
               Movement->RotationRate.Yaw);
    }

    // Per-zombie variation (scale, anim rate, skin, morphs) before the crowd agent is sized.
    AlignMeshFacing();
    ApplyVariation();
    const float Now = GetWorld()->GetTimeSeconds();
    if (Definition)
        NextVocalTime = Now + FMath::FRandRange(.5f, FMath::Max(.5f, Definition->VocalInterval.GetMax()));
    NextSightCheck = Now + FMath::FRandRange(0.f, .3f);

    // Possession ran before this BeginPlay, so the crowd agent registered with the class-default
    // capsule. Re-apply the agent settings now that the capsule has its final size.
    if (auto *AI = Cast<AHoverNYCZombieAI>(GetController()))
        AI->ApplyCrowdSettings();
}

void AHoverNYCZombie::AlignMeshFacing()
{
    // AFS 2026-10-31 (review): the native AHoverNYCZombie never set a mesh yaw (the Cyber BP child did), and the
    // roster bodies face different axes once the compatible-skeleton clips play (Standard bodies 180 deg, the
    // UE4-mannequin bodies 90 deg). The yaw is measured once per definition at authoring time from the walk cycle
    // retargeted onto the body (AuthorZombieDiversity.py) and only applied here: no runtime pose sampling, no
    // per-session cache and no snap after spawn. Definitions without bAlignMeshYaw (bosses, other maps) are untouched.
    const auto *Definition = GetNYCDefinition();
    USkeletalMeshComponent *Body = GetMesh();
    if (!Definition || !Definition->bAlignMeshYaw || !Body)
    {
        MeshFacingYaw = Body ? Body->GetRelativeRotation().Yaw : 0.f;
        return;
    }
    FRotator Rotation = Body->GetRelativeRotation();
    const float Previous = Rotation.Yaw;
    Rotation.Yaw = FRotator::NormalizeAxis(Definition->MeshYawOffset);
    Body->SetRelativeRotation(Rotation);
    MeshFacingYaw = Rotation.Yaw;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_MESH_YAW %s mesh=%s applied=%.1f previous=%.1f"),
           *GetNameSafe(Definition), *GetNameSafe(Body->GetSkeletalMeshAsset()), Rotation.Yaw, Previous);
}

void AHoverNYCZombie::ApplyVariation()
{
    const auto *Definition = GetNYCDefinition();
    if (!Definition)
        return;
    USkeletalMeshComponent *Body = GetMesh();
    UCapsuleComponent *Capsule = GetCapsuleComponent();
    // Bosses keep half the spread so their nav/slot sizing stays close to the authored capsule.
    const float Spread = IsBoss() ? .5f : 1.f;

    // Uniform actor scale. The mesh offset and scale are relative to the capsule, so they scale
    // with it; the actor moves by the half-height change so the capsule bottom stays put.
    const float Scale = RollRange(Definition->ScaleJitter, Spread);
    if (Scale > .01f && !FMath::IsNearlyEqual(Scale, 1.f, .001f))
    {
        const float OldHalf = Capsule->GetScaledCapsuleHalfHeight();
        SetActorScale3D(GetActorScale3D() * Scale);
        const float NewHalf = Capsule->GetScaledCapsuleHalfHeight();
        AddActorWorldOffset(FVector(0.f, 0.f, NewHalf - OldHalf));
        GetCharacterMovement()->UpdateNavAgent(*Capsule);
    }
    VariantScale = GetActorScale3D().Z;

    // Gait and swing tempo (a multiplier, so a rate set elsewhere is kept; (1, 1) changes nothing).
    const float Rate = FMath::Max(.1f, RollRange(Definition->AnimRateJitter, Spread));
    if (!FMath::IsNearlyEqual(Rate, 1.f, .001f))
        Body->GlobalAnimRateScale *= Rate;
    VariantAnimRate = Body->GlobalAnimRateScale;

    // Skin.
    FString SkinName = TEXT("none");
    if (UMaterialInterface *Skin = PickRandom(Definition->SkinMaterials))
    {
        const int32 Slot =
            Definition->SkinMaterialSlot.IsNone() ? 0 : Body->GetMaterialIndex(Definition->SkinMaterialSlot);
        if (Slot == INDEX_NONE || Slot >= Body->GetNumMaterials())
        {
            UE_LOG(LogTemp, Warning, TEXT("HOVER_ZOMBIE_VARIANT_SKIN_SLOT_MISSING %s slot=%s mesh=%s"),
                   *GetNameSafe(Definition), *Definition->SkinMaterialSlot.ToString(),
                   *GetNameSafe(Body->GetSkeletalMeshAsset()));
        }
        else
        {
            Body->SetMaterial(Slot, Skin);
            SkinName = Skin->GetName();
        }
    }

    // Morphs.
    int32 Morphs = 0;
    if (Definition->bRandomizeMorphTargets)
    {
        TArray<FName> Names = Definition->MorphTargetNames;
        if (Names.IsEmpty())
            if (const USkeletalMesh *Asset = Body->GetSkeletalMeshAsset())
                for (const TObjectPtr<UMorphTarget> &Morph : Asset->GetMorphTargets())
                    if (Morph)
                        Names.Add(Morph->GetFName());
        for (const FName &Name : Names)
        {
            Body->SetMorphTarget(Name, FMath::FRandRange(0.f, FMath::Max(0.f, Definition->MorphTargetMax)), false);
            ++Morphs;
        }
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_ZOMBIE_VARIANT %s scale=%.3f rate=%.3f skin=%s morphs=%d"),
           *GetNameSafe(Definition), VariantScale, VariantAnimRate, *SkinName, Morphs);
}

APawn *AHoverNYCZombie::GetChaseTarget() const
{
    const auto *AI = Cast<AHoverNYCZombieAI>(GetController());
    return AI ? AI->GetChaseTarget() : nullptr;
}

void AHoverNYCZombie::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (bIsDead || !ZombieData || DeltaSeconds <= 0.f)
        return;
    const float Now = GetWorld()->GetTimeSeconds();
    APawn *Target = GetChaseTarget();
    // AFS 2026-10-31 (review): a hit reaction (DefaultSlot) or any other montage can cut the sight roar short.
    // End the roar with its montage, so the zombie does not stand still, unable to swing, for the rest of the timer.
    if (bRoaring)
    {
        const auto *Definition = GetNYCDefinition();
        const UAnimInstance *Anim = GetMesh() ? GetMesh()->GetAnimInstance() : nullptr;
        const UAnimMontage *Montage = Definition ? Definition->SightRoarMontage.Get() : nullptr;
        if (!Anim || !Montage || Anim->Montage_GetIsStopped(Montage))
        {
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_ROAR_CUT %s by=montage_stopped"), *GetNameSafe(Definition));
            EndRoar();
        }
    }
    UpdateFacing(Target, DeltaSeconds);
    UpdateSightRoar(Target, Now);
    UpdateVocals(Target, Now);
    UpdateFootsteps(DeltaSeconds);
    if (bRoaring)
        GetCharacterMovement()->MaxWalkSpeed = 0.f;
}

void AHoverNYCZombie::UpdateFacing(APawn *Target, float DeltaSeconds)
{
    UCharacterMovementComponent *Movement = GetCharacterMovement();
    FVector To = Target ? Target->GetActorLocation() - GetActorLocation() : FVector::ZeroVector;
    To.Z = 0.f;
    const float Distance = To.Size();
    const float AttackRange = ZombieData->Stats.AttackRange;
    // Range hysteresis, so a zombie hovering at the edge does not flip modes every frame.
    if (!Target || Distance > AttackRange + FaceTargetExit)
        bInFaceRange = false;
    else if (Distance <= AttackRange + FaceTargetEnter)
        bInFaceRange = true;
    bool bFace = false;
    if (Target && Distance > KINDA_SMALL_NUMBER)
    {
        if (bIsAttacking || bRoaring)
            bFace = true;
        else if (bInFaceRange)
        {
            // Square up only when that does not make the body slide sideways or backwards on the forward walk.
            FVector Velocity = GetVelocity();
            Velocity.Z = 0.f;
            const float Speed = Velocity.Size();
            if (Speed < (bFacingTarget ? FaceStillSpeedHold : FaceStillSpeed))
                bFace = true;
            else
                bFace = FVector::DotProduct(Velocity / Speed, To / Distance) >=
                        (bFacingTarget ? FaceMoveCosHold : FaceMoveCos);
        }
    }
    bFacingTarget = bFace;
    // Otherwise face the movement direction (slot shuffles, retreats to a queue point that moved).
    Movement->bOrientRotationToMovement = !bFace;
    if (!bFace)
        return;
    const float Rate = Movement->RotationRate.Yaw > 0.f ? Movement->RotationRate.Yaw : 360.f;
    const FRotator Current = GetActorRotation();
    const float Yaw = FMath::FixedTurn(Current.Yaw, To.Rotation().Yaw, Rate * DeltaSeconds);
    SetActorRotation(FRotator(0.f, Yaw, 0.f));
    ++FacingFrames;
}

bool AHoverNYCZombie::PlayVoiceSound(EHoverZombieVoiceKind Kind, USoundBase *Sound)
{
    const auto *Definition = GetNYCDefinition();
    auto *Voice = UHoverZombieVoice::Get(this);
    if (!Definition || !Voice || !Sound)
        return false;
    USkeletalMeshComponent *Body = GetMesh();
    const FName Head = ZombieData->Stats.HeadBoneName;
    const FName Socket = !Head.IsNone() && Body->DoesSocketExist(Head) ? Head : NAME_None;
    const float Pitch = FMath::Max(.1f, RollRange(Definition->VoicePitch, 1.f));
    if (!Voice->PlayVocal(this, Kind, Sound, Body, Socket, Definition->VoiceVolume, Pitch, GetNameSafe(Definition)))
        return false;
    ++VocalsStarted;
    return true;
}

bool AHoverNYCZombie::PlayVoice(EHoverZombieVoiceKind Kind, const TArray<TObjectPtr<USoundBase>> &Sounds)
{
    USoundBase *Sound = PickRandom(Sounds);
    return Sound && PlayVoiceSound(Kind, Sound);
}

void AHoverNYCZombie::UpdateVocals(APawn *Target, float Now)
{
    const auto *Definition = GetNYCDefinition();
    if (!Definition || Now < NextVocalTime)
        return;
    const float Low = FMath::Max(.5f, Definition->VocalInterval.GetMin());
    NextVocalTime = Now + FMath::FRandRange(Low, FMath::Max(Low, Definition->VocalInterval.GetMax()));
    // Swings and roars voice themselves; inaudible zombies do not spend the budget.
    if (bIsAttacking || bRoaring)
        return;
    const auto *Voice = UHoverZombieVoice::Get(this);
    if (!Voice || FVector::Dist(GetActorLocation(), Voice->GetListenerLocation()) > VocalAudibleRange)
        return;
    const bool bChasing = Target && GetVelocity().Size2D() > 30.f;
    const auto &Primary = bChasing ? Definition->ChaseVocals : Definition->IdleVocals;
    const auto &Fallback = bChasing ? Definition->IdleVocals : Definition->ChaseVocals;
    const EHoverZombieVoiceKind Kind = bChasing ? EHoverZombieVoiceKind::Chase : EHoverZombieVoiceKind::Idle;
    // An empty list borrows the other one, so a definition with only chase vocals still murmurs.
    PlayVoice(Kind, Primary.IsEmpty() ? Fallback : Primary);
}

void AHoverNYCZombie::UpdateFootsteps(float DeltaSeconds)
{
    const auto *Definition = GetNYCDefinition();
    UCharacterMovementComponent *Movement = GetCharacterMovement();
    if (!Definition || Definition->FootstepSounds.IsEmpty() || !Movement->IsMovingOnGround())
        return;
    StepDistance += GetVelocity().Size2D() * DeltaSeconds;
    const float Stride = FMath::Max(10.f, Definition->FootstepStride * GetActorScale3D().Z);
    if (StepDistance < Stride)
        return;
    StepDistance = FMath::Fmod(StepDistance, Stride);
    const APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0);
    auto *Voice = UHoverZombieVoice::Get(this);
    if (!Player || !Voice || FVector::Dist(Player->GetActorLocation(), GetActorLocation()) > FootstepRange)
        return;
    USoundBase *Sound = PickRandom(Definition->FootstepSounds);
    if (!Sound || !Voice->TryConsumeFootstep())
        return;
    const bool bHeavy = IsHeavyRole(Definition);
    const float Volume = Definition->FootstepVolume * (bHeavy ? 1.6f : 1.f);
    const float Pitch = FMath::FRandRange(.94f, 1.06f) * (bHeavy ? .8f : 1.f);
    const FVector Feet = GetActorLocation() - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    UGameplayStatics::PlaySoundAtLocation(this, Sound, Feet, FRotator::ZeroRotator, Volume, Pitch, 0.f,
                                          Voice->GetFootstepAttenuation());
    ++FootstepsPlayed;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_STEP %s"), *GetNameSafe(Definition));
}

void AHoverNYCZombie::UpdateSightRoar(APawn *Target, float Now)
{
    if (bSightRollDone || bRoaring || !Target || Now < NextSightCheck)
        return;
    NextSightCheck = Now + .3f;
    const auto *Definition = GetNYCDefinition();
    if (!Definition || !Definition->SightRoarMontage)
    {
        bSightRollDone = true;
        return;
    }
    if (FVector::Dist(Target->GetActorLocation(), GetActorLocation()) > SightRoarRange)
        return;
    const auto *AI = Cast<AAIController>(GetController());
    if (!AI || !AI->LineOfSightTo(Target))
        return;
    // One roll per zombie, on the first acquisition with line of sight.
    bSightRollDone = true;
    if (bIsAttacking || bSwingPending || FMath::FRand() >= Definition->SightRoarChance)
        return;
    auto *Voice = UHoverZombieVoice::Get(this);
    if (!Voice || !Voice->TryStartRoar())
        return;
    StartRoar(Target);
}

void AHoverNYCZombie::StartRoar(APawn *Target)
{
    const auto *Definition = GetNYCDefinition();
    UAnimMontage *Montage = Definition ? Definition->SightRoarMontage.Get() : nullptr;
    const float Duration = Montage ? PlayAnimMontage(Montage) : 0.f;
    if (Duration <= 0.f)
    {
        UE_LOG(LogTemp, Warning, TEXT("HOVER_ZOMBIE_ROAR_FAILED %s montage=%s (no matching slot?)"),
               *GetNameSafe(Definition), *GetNameSafe(Montage));
        return;
    }
    bRoaring = true;
    ++Roars;
    UCharacterMovementComponent *Movement = GetCharacterMovement();
    PreRoarSpeed = Movement->MaxWalkSpeed;
    Movement->StopMovementImmediately();
    Movement->MaxWalkSpeed = 0.f;
    SetCrowdSimulation(true);
    // Dedicated sight roar if authored, otherwise a chase vocal.
    USoundBase *Sound = Definition->SightRoar.IsNull() ? nullptr : Definition->SightRoar.LoadSynchronous();
    if (!Sound)
        Sound = PickRandom(Definition->ChaseVocals);
    PlayVoiceSound(EHoverZombieVoiceKind::Roar, Sound);
    UE_LOG(LogTemp, Display, TEXT("HOVER_ZOMBIE_ROAR %s montage=%s duration=%.2f target=%s"), *GetNameSafe(Definition),
           *GetNameSafe(Montage), Duration, *GetNameSafe(Target));
    // PlayAnimMontage's length ignores the mesh GlobalAnimRateScale.
    const float RealDuration = Duration / FMath::Max(GetMesh()->GlobalAnimRateScale, .1f);
    GetWorldTimerManager().SetTimer(RoarEndTimer, FTimerDelegate::CreateWeakLambda(this, [this] { EndRoar(); }),
                                    FMath::Max(RealDuration, .05f), false);
}

void AHoverNYCZombie::EndRoar()
{
    if (!bRoaring)
        return;
    bRoaring = false;
    GetWorldTimerManager().ClearTimer(RoarEndTimer);
    if (bIsDead)
        return;
    SetCrowdSimulation(false);
    // The AI tick rewrites the speed every ~0.5 s; restore it now so the zombie does not idle.
    GetCharacterMovement()->MaxWalkSpeed = PreRoarSpeed;
}

UAnimMontage *AHoverNYCZombie::SelectDeathMontage()
{
    if (const auto *Definition = GetNYCDefinition())
        if (UAnimMontage *Variant = PickRandom(Definition->DeathMontageVariants))
        {
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_DEATH_VARIANT %s %s"), *GetNameSafe(Definition),
                   *Variant->GetName());
            return Variant;
        }
    return Super::SelectDeathMontage();
}

bool AHoverNYCZombie::ShouldPlayDataAssetSounds() const
{
    const auto *Definition = GetNYCDefinition();
    return !(Definition && Definition->HasCustomVoice());
}

bool AHoverNYCZombie::SpawnDefinitionHitBlood(const FHitResult &Hit, const FVector &ShotDirection)
{
    const auto *Definition = GetNYCDefinition();
    if (!Definition || (!Definition->HitBlood && !Definition->HeadshotBlood))
        return false;
    const FName Bone = Hit.BoneName;
    const bool bHead = !Bone.IsNone() && (Bone == ZombieData->Stats.HeadBoneName ||
                                          Bone.ToString().Contains(TEXT("head"), ESearchCase::IgnoreCase));
    const bool bUseHead = bHead && Definition->HeadshotBlood;
    UNiagaraSystem *System = bUseHead ? Definition->HeadshotBlood.Get() : Definition->HitBlood.Get();
    if (!System)
        return false;
    const FVector Back = ShotDirection.IsNearlyZero() ? GetActorForwardVector() : -ShotDirection.GetSafeNormal();
    SpawnTimedBlood(GetWorld(), System, Hit.ImpactPoint, Back.Rotation(), Definition->BloodScale, 1.f, 5.f);
    ++BloodSpawns;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_BLOOD %s %s"), bUseHead ? TEXT("Headshot") : TEXT("Hit"),
           *System->GetName());
    return true;
}

void AHoverNYCZombie::SpawnDeathBlood()
{
    const auto *Definition = GetNYCDefinition();
    if (!Definition || !Definition->DeathBlood)
        return;
    const USkeletalMeshComponent *Body = GetMesh();
    static const FName Pelvis(TEXT("pelvis"));
    const FVector From = Body->GetBoneIndex(Pelvis) != INDEX_NONE ? Body->GetBoneLocation(Pelvis) : GetActorLocation();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(HoverZombieDeathBlood), false, this);
    FHitResult Floor;
    FVector Point = From - FVector(0.f, 0.f, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    FVector Normal = FVector::UpVector;
    if (GetWorld()->LineTraceSingleByChannel(Floor, From + FVector(0.f, 0.f, 50.f), From - FVector(0.f, 0.f, 400.f),
                                             ECC_Visibility, Query))
    {
        Point = Floor.ImpactPoint;
        Normal = Floor.ImpactNormal;
    }
    SpawnTimedBlood(GetWorld(), Definition->DeathBlood, Point, FRotationMatrix::MakeFromZ(Normal).Rotator(),
                    Definition->BloodScale, 3.f, 20.f);
    ++BloodSpawns;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_BLOOD Death %s"), *Definition->DeathBlood->GetName());
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
    if (bRoaring)
    {
        bRoaring = false;
        if (UWorld *World = GetWorld())
            World->GetTimerManager().ClearTimer(RoarEndTimer);
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
    if (const auto *Definition = GetNYCDefinition())
        PlayVoice(EHoverZombieVoiceKind::Attack, Definition->AttackVocals);
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
            // The vendor hit reaction replaces the roar montage: end the roar state with it (review 2026-10-31).
            if (bRoaring)
            {
                UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_ROAR_CUT %s by=flinch"), *GetNameSafe(Definition));
                EndRoar();
            }
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
    else if (bWasAlive && Damage > 0.f)
        if (const auto *Definition = GetNYCDefinition(); Definition && Definition->PainVocals.Num())
        {
            const float Now = GetWorld()->GetTimeSeconds();
            if (Now - LastPainVocal >= PainVocalInterval)
            {
                LastPainVocal = Now;
                PlayVoice(EHoverZombieVoiceKind::Pain, Definition->PainVocals);
            }
        }
    return Result;
}

void AHoverNYCZombie::HandleKilled()
{
    // The vendor Die() already chose the clip through SelectDeathMontage and muted its own
    // DeathSound when this definition has a voice set.
    if (const auto *Definition = GetNYCDefinition())
        PlayVoice(EHoverZombieVoiceKind::Death, Definition->DeathVocals);
    SpawnDeathBlood();
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
    // The definition radius follows the per-zombie scale roll (AHoverNYCZombie::ApplyVariation).
    const float Radius = Definition ? Definition->CapsuleRadius * Zombie->GetActorScale3D().X
                                    : Zombie->GetCapsuleComponent()->GetScaledCapsuleRadius();
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
        // AFS 2026-10-31 (kid swarm): a stalled zombie (UHoverAttackSlotSubsystem::UpdateProgress) re-plans now.
        const bool bStale = (Slots && Slots->UpdateProgress(Zombie, Target)) || !bFarApproachActive ||
                            Now >= NextApproachRefresh ||
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
            // AFS 2026-10-31 (kid swarm): on the navmesh and connected to the target, or a stalled zombie's detour.
            if (Slots && !Slots->ResolveApproachPoint(Zombie, Target, Desired, Point))
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
    // A sight roar holds the zombie in place until its montage ends.
    Zombie->GetCharacterMovement()->MaxWalkSpeed = Zombie->IsRoaring() ? 0.f : Speed;
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
