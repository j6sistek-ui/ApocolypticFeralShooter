#include "HoverCyberCity.h"
#include "HoverNYCZombie.h"
#include "HoverEffects.h"
#include "HoverCombatBridge.h"
#include "HoverPilot.h"
#include "HoverTestController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/DamageEvents.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "Zombies/ZE_ZombieSettings.h"
#include "World/ZE_ZombieSpawnPoint.h"
#include "EngineUtils.h"
#include "Blueprint/UserWidget.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/Border.h"
#include "Components/VerticalBox.h"
#include "Components/TextBlock.h"
#include "Components/ProgressBar.h"
#include "Styling/CoreStyle.h"
#include "Engine/SkeletalMesh.h"
#include "Animation/AnimInstance.h"
#include "Perception/AIPerceptionComponent.h"
#include "Perception/AISense_Damage.h"
#include "Perception/AISenseConfig_Hearing.h"
#include "Perception/AISenseConfig_Sight.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Navigation/CrowdFollowingComponent.h"
#include "NavMesh/RecastNavMesh.h"

void UHoverLakesideNavigationSystem::PostInitProperties()
{
    Super::PostInitProperties();
    if (SupportedAgents.IsEmpty())
    {
        FNavDataConfig Agent;
        Agent.Name = TEXT("Default");
        Agent.SetNavDataClass(ARecastNavMesh::StaticClass());
        SupportedAgents.Add(Agent);
    }
    for (FNavDataConfig &Agent : SupportedAgents)
        Agent.AgentHeight = 210.f;
}

void AHoverAmmoPickup::BeginPlay()
{
    Super::BeginPlay();
    auto *Box = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/ZESP/ZE/Meshes/Tools/SM_AmmoBox.SM_AmmoBox"));
    if (!LootStaticMesh || !Box)
        return;
    LootStaticMesh->SetStaticMesh(Box);
    LootStaticMesh->EmptyOverrideMaterials();
    const float Width = FMath::Max(Box->GetBounds().BoxExtent.X, Box->GetBounds().BoxExtent.Y) * 2.f;
    LootStaticMesh->SetRelativeScale3D(FVector(35.f / FMath::Max(Width, 1.f)));
    LootStaticMesh->SetVisibility(true);
    FHitResult Floor;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(AmmoDropFloor), false, this);
    const FVector Origin = GetActorLocation();
    if (GetWorld()->LineTraceSingleByObjectType(Floor, Origin + FVector(0, 0, 100), Origin - FVector(0, 0, 2000),
                                                FCollisionObjectQueryParams(ECC_WorldStatic), Query) &&
        Floor.ImpactNormal.Z > .5f)
    {
        const float Bottom = LootStaticMesh->Bounds.Origin.Z - LootStaticMesh->Bounds.BoxExtent.Z;
        SetActorLocation(Origin + FVector(0, 0, Floor.ImpactPoint.Z + 2.f - Bottom), false, nullptr,
                         ETeleportType::TeleportPhysics);
    }
}

void AHoverCyberCityGameMode::InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);
    DefaultPawnClass =
        LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Hybrid/BP_Vexa_CLS_Parkour.BP_Vexa_CLS_Parkour_C"));
    PlayerControllerClass = AHoverTestController::StaticClass();
    HUDClass = AHoverHUD::StaticClass();
    WaveSettings = LoadObject<UZE_WaveGameModeSettings>(
        nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_CyberWaves.DA_CyberWaves"));
    Encounters = LoadObject<UHoverCyberEncounterSettings>(
        nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/Variants/DA_CyberEncounters.DA_CyberEncounters"));
    bLakeside = MapName.Contains(TEXT("L_Showcase")) || MapName.Contains(TEXT("L_Lakeside"));
    if (bLakeside)
    {
        WaveSettings = LoadObject<UZE_WaveGameModeSettings>(
            nullptr, TEXT("/Game/HoverPrototype/Lakeside/DA_LakesideWaves.DA_LakesideWaves"));
        Encounters = LoadObject<UHoverCyberEncounterSettings>(
            nullptr, TEXT("/Game/HoverPrototype/Lakeside/DA_LakesideEncounters.DA_LakesideEncounters"));
    }
    if (WaveSettings)
        WaveSettings->WaveHUDClass = UHoverCyberWaveHUD::StaticClass();
    // Test settings pauses the complete session, including the wave countdown.
    PrimaryActorTick.bTickEvenWhenPaused = false;
}

void AHoverCyberCityGameMode::ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types)
{
    Super::ConfigureWave(Wave, Count, Types);
    if (bLakeside && (!Encounters || Encounters->Standards.IsEmpty()))
    {
        Count = 0;
        Types.Reset();
        return;
    }
    if (!Encounters)
        return;
    if (Encounters->IsSwarmWave(Wave))
    {
        Count = FMath::Clamp(Encounters->SwarmCount, 1, 24);
        Types = {Encounters->Kid};
    }
    else if (Encounters->Standards.Num())
    {
        Types.Reset();
        for (const auto &Definition : Encounters->Standards)
            if (Definition)
                Types.Add(Definition);
    }
    Count = FMath::Clamp(FMath::RoundToInt(Count * Tuning.Count), 1, 200);
}

void AHoverCyberCityGameMode::ApplyTuning(FHoverZombieTuning Value)
{
    Tuning.Health = FMath::Clamp(Value.Health, .25f, 3.f);
    Tuning.Speed = FMath::Clamp(Value.Speed, .25f, 2.f);
    Tuning.Count = FMath::Clamp(Value.Count, .25f, 3.f);
    Tuning.SpawnInterval = FMath::Clamp(Value.SpawnInterval, .25f, 3.f);
}

void AHoverCyberCityGameMode::RecordSpawn(const FVector &Position)
{
    LastSpawnPosition = Position;
    AActor *Closest = nullptr;
    float Distance = 500.f;
    for (TActorIterator<AZE_ZombieSpawnPoint> It(GetWorld()); It; ++It)
    {
        const float D = FVector::Dist2D(Position, It->GetActorLocation());
        if (D < Distance)
        {
            Closest = *It;
            Distance = D;
        }
    }
    if (Closest)
        SpawnLastUsed.Add(Closest, GetWorld()->GetTimeSeconds());
}

bool AHoverCyberCityGameMode::CanReachPlayer(AActor *Spawn, APawn *Player)
{
    const FVector Target = Player->GetNavAgentLocation();
    const float Now = GetWorld()->GetTimeSeconds();
    if (Now >= NextReachabilityCheck || FVector::DistSquared(Target, LastNavigationTarget) > FMath::Square(200.f))
    {
        ReachableSpawns.Reset();
        LastNavigationTarget = Target;
        NextReachabilityCheck = Now + 1.f;
    }
    if (const bool *Cached = ReachableSpawns.Find(Spawn))
        return *Cached;
    const bool Reachable = CanReachPoint(Spawn, Target, FVector(100, 100, 120), Player);
    ReachableSpawns.Add(Spawn, Reachable);
    return Reachable;
}

bool AHoverCyberCityGameMode::CanReachPoint(AActor *From, const FVector &Target, const FVector &TargetExtent,
                                            const UObject *Querier) const
{
    bool Reachable = false;
    if (!From)
        return Reachable;
    if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(GetWorld()))
        if (auto *Data = Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
        {
            FNavLocation Start, End;
            if (Navigation->ProjectPointToNavigation(From->GetActorLocation(), Start, FVector(120, 120, 200)) &&
                Navigation->ProjectPointToNavigation(Target, End, TargetExtent))
            {
                FPathFindingQuery Query(Querier ? Querier : From, *Data, Start.Location, End.Location);
                Query.SetAllowPartialPaths(false);
                Reachable = Navigation->TestPathSync(Query);
            }
        }
    return Reachable;
}

void AHoverCyberCityGameMode::OnZombieSpawned(AHoverCyberZombie &Zombie)
{
    RecordSpawn(Zombie.GetActorLocation());
}

float AHoverCyberCityGameMode::GetRoundHealthScale(int32 Wave) const
{
    float Health = 1, Damage = 1, Speed = 1;
    if (WaveSettings)
        WaveSettings->GetDifficultyMultipliers(Wave, Health, Damage, Speed);
    return Health;
}

float AHoverCyberCityGameMode::GetRoundDamageScale(int32 Wave) const
{
    float Health = 1, Damage = 1, Speed = 1;
    if (WaveSettings)
        WaveSettings->GetDifficultyMultipliers(Wave, Health, Damage, Speed);
    return Damage;
}

UZE_ZombieDataAsset *AHoverCyberCityGameMode::SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                               const TArray<UZE_ZombieDataAsset *> &Types)
{
    if (Encounters)
    {
        if (Encounters->IsSwarmWave(Wave))
            return Encounters->Kid;
        // Exactly one tank; the remaining spawn slots keep the ordinary horde.
        if (Encounters->IsBruteWave(Wave) && SpawnIndex == 0)
            return Encounters->Brute;
        if (Types.Num())
            return Types[SpawnIndex % Types.Num()];
    }
    return Super::SelectZombieData(Wave, SpawnIndex, Types);
}

float AHoverCyberCityGameMode::GetEffectiveSpawnRate() const
{
    const float Interval = Encounters && Encounters->IsSwarmWave(GetCurrentWave())
                               ? FMath::Max(.1f, Encounters->SwarmSpawnInterval)
                               : Super::GetEffectiveSpawnRate();
    return Interval * Tuning.SpawnInterval;
}

void AHoverCyberCityGameMode::StartWave()
{
    // A separate, empty roster must never fall back to the Cyber City enemies.
    if (bLakeside && (!Encounters || Encounters->Standards.IsEmpty()))
        return;
    Super::StartWave();
}

FString AHoverCyberCityGameMode::GetEncounterLabel() const
{
    if (bLakeside)
        return !Encounters || Encounters->Standards.IsEmpty() ? TEXT("LAKESIDE - new zombie roster pending")
                                                              : TEXT("LAKESIDE HORDE");
    if (Encounters && Encounters->IsSwarmWave(GetCurrentWave()))
        return TEXT("KID SWARM - stay moving");
    if (Encounters && Encounters->IsBruteWave(GetCurrentWave()))
        return TEXT("HEAVY TANK - brute round");
    return TEXT("CITY HORDE");
}

AHoverCyberZombieAI::AHoverCyberZombieAI()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = .5f;
    HearingConfig->DetectionByAffiliation.bDetectNeutrals = true;
    HearingConfig->DetectionByAffiliation.bDetectEnemies = true;
    HearingConfig->DetectionByAffiliation.bDetectFriendlies = true;
    GetPerceptionComponent()->ConfigureSense(*HearingConfig);
}

void AHoverCyberZombieAI::OnPossess(APawn *InPawn)
{
    // Use UE's navmesh-aware crowd steering, retaining the purchased behavior tree.
    // Install before the tree starts so requests bind to the correct follower.
    if (!Cast<UCrowdFollowingComponent>(GetPathFollowingComponent()))
    {
        auto *Old = GetPathFollowingComponent();
        auto *Crowd = NewObject<UCrowdFollowingComponent>(this, TEXT("AFSCrowdFollowing"));
        Crowd->RegisterComponent();
        SetPathFollowingComponent(Crowd);
        if (Old)
            Old->DestroyComponent();
        Crowd->SetCrowdSeparation(true);
        Crowd->SetCrowdSeparationWeight(3.f);
        Crowd->SetCrowdCollisionQueryRange(500.f);
        Crowd->SetCrowdAvoidanceQuality(ECrowdAvoidanceQuality::High);
        Crowd->SetCrowdAnticipateTurns(true);
    }
    Super::OnPossess(InPawn);
    // Bind on the live instance: a copied Blueprint can retain the parent's
    // serialized unfiltered delegate despite a native constructor replacement.
    GetPerceptionComponent()->OnTargetPerceptionUpdated.RemoveAll(this);
    GetPerceptionComponent()->OnTargetPerceptionUpdated.AddDynamic(this, &AHoverCyberZombieAI::OnPlayerDetected);
}

void AHoverCyberCityGameMode::Tick(float DT)
{
    ActiveSpawnCount = 0;
    auto *PC = UGameplayStatics::GetPlayerController(this, 0);
    APawn *Player = PC ? PC->GetPawn() : nullptr;
    if (Player)
    {
        // Vexa handles reactions and honors the pause-menu invulnerability setting.
        Player->SetCanBeDamaged(Cast<AHoverPilot>(Player) != nullptr);
        if (!IsWaveHUDVisible() && WaveSettings && WaveSettings->WaveHUDClass)
        {
            TArray<UUserWidget *> Widgets;
            UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, WaveSettings->WaveHUDClass, true);
            WaveDisplay = Widgets.Num() ? Widgets[0] : CreateWidget<UUserWidget>(PC, WaveSettings->WaveHUDClass);
            if (WaveDisplay && !WaveDisplay->IsInViewport())
                WaveDisplay->AddToViewport(10);
        }
    }
    // NYC Survival's director owns placement and pacing; this per-frame gate is Cyber/Lakeside only.
    if (Player && !bExternalSpawnDirector)
    {
        FVector Eye;
        FRotator View;
        PC->GetPlayerViewPoint(Eye, View);
        AZE_ZombieSpawnPoint *Chosen = nullptr;
        float BestScore = -1.f;
        for (TActorIterator<AZE_ZombieSpawnPoint> It(GetWorld()); It; ++It)
        {
            const FVector Position = It->GetActorLocation();
            const float Distance = FVector::Dist2D(Position, Player->GetActorLocation());
            bool Safe = Distance >= 1400.f && Distance <= 10000.f;
            // Do not spend a wave slot on a disconnected porch/island. Refresh
            // paths at most once a second; airborne/vehicle targeting is unchanged.
            if (const auto *Pilot = Cast<AHoverPilot>(Player);
                Safe && Pilot && Pilot->IsOnFoot() && Pilot->GetCharacterMovement()->IsMovingOnGround())
                Safe = CanReachPlayer(*It, Player);
            FCollisionQueryParams Query;
            Query.AddIgnoredActor(Player);
            Query.AddIgnoredActor(*It);
            const FVector SightPoint = Position + FVector(0, 0, 60);
            // A visible street entrance cannot produce a zombie in front of the player.
            if (Safe && FVector::DotProduct((SightPoint - Eye).GetSafeNormal(), View.Vector()) > .2f)
                Safe = GetWorld()->LineTraceTestByChannel(Eye, SightPoint, ECC_Visibility, Query);
            if (Safe)
                for (TActorIterator<APawn> Pawn(GetWorld()); Pawn; ++Pawn)
                    if (FVector::Dist2D(Pawn->GetActorLocation(), Position) < 300.f)
                    {
                        Safe = false;
                        break;
                    }
            It->bIsEnabled = false;
            ActiveSpawnCount += Safe ? 1 : 0;
            if (Safe)
            {
                const float *Last = SpawnLastUsed.Find(*It);
                const float Age = Last ? FMath::Min(60.f, GetWorld()->GetTimeSeconds() - *Last) : 60.f;
                const float Score = Age + FMath::Min(20.f, FVector::Dist2D(Position, LastSpawnPosition) / 300.f);
                if (Score > BestScore)
                {
                    Chosen = *It;
                    BestScore = Score;
                }
            }
        }
        if (Chosen)
            Chosen->bIsEnabled = true;
    }
    // The vendor otherwise falls back to PlayerStart when all points are disabled.
    // Wait for a fair entrance instead of spawning beside Vexa or inside a vehicle.
    // An external director instead keeps the vendor rate at BIG_NUMBER until a hidden entrance is enabled.
    if (bExternalSpawnDirector || GetWaveState() != EZE_WaveState::WaveInProgress || ActiveSpawnCount > 0)
        Super::Tick(DT);
}

bool AHoverCyberCityGameMode::IsWaveHUDVisible() const
{
    return WaveDisplay && WaveDisplay->IsInViewport();
}

void AHoverCyberZombieAI::Tick(float DT)
{
    Super::Tick(DT);
    // The supplied direct-chase lookup requires its own player class. Target the
    // possessed AFS pawn, including vehicles, while retaining its behavior tree.
    APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0);
    if (GetPawn() && Player && bDirectChaseMode)
    {
        if (auto *Board = GetBlackboardComponent())
        {
            if (Board->GetValueAsObject(Key_TargetEnemy) != Player)
                SetTargetEnemy(Player);
            Board->SetValueAsVector(Key_LastKnownLocation, Player->GetActorLocation());
        }
    }
    auto *Zombie = Cast<AHoverCyberZombie>(GetPawn());
    if (Zombie && Player)
    {
        // Preserve exact contact poses nearby. Distant enemies can use Unreal's
        // visibility/update-rate budget without throttling AI or attack timers.
        const bool NeedsFullPose =
            Zombie->NeedsContactPose() ||
            FVector::DistSquared(Zombie->GetActorLocation(), Player->GetActorLocation()) < FMath::Square(2000.f);
        Zombie->GetMesh()->bEnableUpdateRateOptimizations = !NeedsFullPose;
        Zombie->GetMesh()->VisibilityBasedAnimTickOption =
            NeedsFullPose ? EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones
                          : EVisibilityBasedAnimTickOption::AlwaysTickPose;
    }
    auto *Board = GetBlackboardComponent();
    if (Zombie && Zombie->ZombieData && Board)
    {
        if (!bDirectChaseMode && Board->GetValueAsObject(Key_TargetEnemy) != Player)
            Board->ClearValue(Key_TargetEnemy);
        const auto &Stats = Zombie->ZombieData->Stats;
        float HealthScale = 1, DamageScale = 1, SpeedScale = 1;
        if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>(); Mode && Mode->GetWaveSettings())
            Mode->GetWaveSettings()->GetDifficultyMultipliers(Mode->GetCurrentWave(), HealthScale, DamageScale,
                                                              SpeedScale);
        // A spawn-frozen per-actor scale wins; otherwise the mode's round lookup, which the
        // base class answers with the same wave-asset value as above.
        if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
            HealthScale =
                Zombie->HealthScale > 0 ? Zombie->HealthScale : Mode->GetRoundHealthScale(Mode->GetCurrentWave());
        // The supplied character initialized only WalkSpeed. Use its own RunSpeed
        // for pursuit so the existing walk/run blend space can reach its run pose.
        const bool Pursuing = Board->GetValueAsObject(Key_TargetEnemy) != nullptr;
        Zombie->GetCharacterMovement()->MaxWalkSpeed = (Pursuing ? Stats.RunSpeed : Stats.WalkSpeed) * SpeedScale;
        // A rolled speed tier (NYC Survival) replaces the run speed and ignores the wave speed scale.
        if (Zombie->SpeedTier > 0)
            Zombie->GetCharacterMovement()->MaxWalkSpeed = Pursuing ? Zombie->SpeedTier : Stats.WalkSpeed;
        if (const auto *Definition = Cast<UHoverCyberZombieDefinition>(Zombie->ZombieData))
            Zombie->GetCharacterMovement()->MaxWalkSpeed =
                FMath::Min(Zombie->GetCharacterMovement()->MaxWalkSpeed, Definition->MaximumRunSpeed);
        if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        {
            Zombie->GetCharacterMovement()->MaxWalkSpeed *= Mode->Tuning.Speed;
            if (auto *Health = Zombie->SurvivalComponent; Health && Health->GetHealth() > 0)
            {
                const float Maximum = Stats.MaxHealth * HealthScale * Mode->Tuning.Health;
                if (!FMath::IsNearlyEqual(Health->GetMaxHealth(), Maximum))
                {
                    const float Fraction = Health->GetHealth() / FMath::Max(1.f, Health->GetMaxHealth());
                    Health->SetMaxHealth(Maximum);
                    Health->SetHealth(Maximum * Fraction);
                }
            }
        }
        Board->SetValueAsFloat(Key_AttackCooldown, Stats.AttackCooldown);
        if (SightConfig->SightRadius != Stats.SightRadius || SightConfig->LoseSightRadius != Stats.LoseSightRadius ||
            SightConfig->PeripheralVisionAngleDegrees != Stats.ViewAngle)
        {
            SightConfig->SightRadius = Stats.SightRadius;
            SightConfig->LoseSightRadius = Stats.LoseSightRadius;
            SightConfig->PeripheralVisionAngleDegrees = Stats.ViewAngle;
            GetPerceptionComponent()->ConfigureSense(*SightConfig);
        }
        if (HearingConfig->HearingRange != Stats.HearingRange)
        {
            HearingConfig->HearingRange = Stats.HearingRange;
            GetPerceptionComponent()->ConfigureSense(*HearingConfig);
        }
    }
}

void AHoverCyberZombieAI::OnPlayerDetected(AActor *Actor, FAIStimulus Stimulus)
{
    // Retain the pack's perception/BT path; parked vehicles and the unpossessed
    // rider are not enemies after a mount or vehicle switch.
    if (Actor == UGameplayStatics::GetPlayerPawn(this, 0) && GetBlackboardComponent())
        OnTargetDetected(Actor, Stimulus);
}

void AHoverCyberZombie::InitializeZombieStats()
{
    Super::InitializeZombieStats();
    if (ZombieData && SurvivalComponent)
    {
        SurvivalComponent->SetMaxHealth(ZombieData->Stats.MaxHealth);
        SurvivalComponent->SetHealth(ZombieData->Stats.MaxHealth);
    }
}

AHoverCyberZombie::AHoverCyberZombie()
{
    Trousers = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CyberTrousers"));
    Shirt = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("CyberShirt"));
    Trousers->SetupAttachment(GetMesh());
    Shirt->SetupAttachment(GetMesh());
    Trousers->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Shirt->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AHoverCyberZombie::BeginPlay()
{
    Super::BeginPlay();
    // Owner 2026-10-31: "I can jump on top of zombies' heads and bounce like a trampoline". The capsule top is
    // walkable by default, so a character landing on it stands there; marking the capsule unwalkable makes the
    // movement component treat any contact as a wall and slide off. Pathing and hits are unaffected.
    GetCapsuleComponent()->SetWalkableSlopeOverride(FWalkableSlopeOverride(WalkableSlope_Unwalkable, 0.f));
    auto *Definition = Cast<UHoverCyberZombieDefinition>(ZombieData);
    if (Definition && Definition->AppearanceMesh)
    {
        auto *Body = Definition->AppearanceMesh.Get();
        const FBoxSphereBounds Bounds = Body->GetBounds();
        const float Scale = Definition->Height / FMath::Max(1.f, Bounds.BoxExtent.Z * 2.f);
        GetCapsuleComponent()->SetCapsuleSize(Definition->CapsuleRadius, Definition->Height * .5f);
        // Spawned variants resize after the movement component registered.
        // Keep path queries and crowd avoidance consistent with the live capsule.
        GetCharacterMovement()->SetUpdateNavAgentWithOwnersCollisions(true);
        GetCharacterMovement()->UpdateNavAgent(*GetCapsuleComponent());
        GetMesh()->SetSkeletalMesh(Body);
        if (Definition->AnimClassOverride)
            GetMesh()->SetAnimInstanceClass(Definition->AnimClassOverride);
        GetMesh()->EmptyOverrideMaterials();
        GetMesh()->SetRelativeScale3D(FVector(Scale));
        GetMesh()->SetRelativeLocation(
            FVector(0, 0, -Definition->Height * .5f - (Bounds.Origin.Z - Bounds.BoxExtent.Z) * Scale));
        GetMesh()->SetDisablePostProcessBlueprint(true);
        Trousers->SetVisibility(false);
        Shirt->SetVisibility(false);
        // Role defaults; the Boss role turns like a Brute. AHoverNYCZombie applies the DA overrides on top.
        GetCharacterMovement()->RotationRate.Yaw =
            Definition->Role == EHoverZombieRole::Brute || Definition->Role == EHoverZombieRole::Boss ? 220.f : 600.f;
        GetCharacterMovement()->MaxAcceleration = Definition->Role == EHoverZombieRole::Kid ? 2600.f : 1400.f;
    }
    else
    {
        if (auto *Body = LoadObject<USkeletalMesh>(
                nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/SK_CyberZombie.SK_CyberZombie")))
        {
            GetMesh()->SetSkeletalMesh(Body);
            GetMesh()->EmptyOverrideMaterials();
            GetMesh()->SetMorphTarget(TEXT("Angry"), .75f);
            GetMesh()->SetDisablePostProcessBlueprint(true);
        }
        Trousers->SetSkeletalMesh(LoadObject<USkeletalMesh>(
            nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/SK_CyberTrousers.SK_CyberTrousers")));
        Shirt->SetSkeletalMesh(
            LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/SK_CyberShirt.SK_CyberShirt")));
        Trousers->SetLeaderPoseComponent(GetMesh());
        Shirt->SetLeaderPoseComponent(GetMesh());
        Shirt->SetVisibility(GetUniqueID() % 2 == 0);
    }
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    GetMesh()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    // The capsule handles pawn separation; animated limbs must not shove the rider.
    GetMesh()->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
    GetMesh()->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
    // Lakeside's dock boards have 45-degree collision bevels. Recast accepts
    // their short steps, but the default 44.76-degree movement slope blocks them.
    if (Cast<UHoverLakesideNavigationSystem>(GetWorld()->GetNavigationSystem()))
        GetCharacterMovement()->SetWalkableFloorAngle(46.f);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Blood = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Rocket/NS1_Blood/NS_NS1_BloodShot.NS_NS1_BloodShot"));
    if (auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        Mode->OnZombieSpawned(*this);
}

void AHoverCyberZombie::FellOutOfWorld(const UDamageType &DamageType)
{
    // A director-run round needs every spawned zombie to die by damage, so a fall below
    // KillZ relocates instead. Without a director (or a spawner) the engine default runs.
    auto *Mode = GetWorld() ? GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>() : nullptr;
    if (!bIsDead && Mode && Mode->UsesExternalSpawnDirector() && Mode->RelocateZombie(*this))
        return;
    Super::FellOutOfWorld(DamageType);
}

void AHoverCyberZombie::EndPlay(const EEndPlayReason::Type Reason)
{
    // Leak guard: a living zombie destroyed by anything but Die() would keep the vendor
    // ZombiesAlive above zero and the round could never end. Route it through OnDeath.
    auto *Mode = GetWorld() ? GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>() : nullptr;
    if (Reason == EEndPlayReason::Destroyed && !bIsDead && Mode && Mode->UsesExternalSpawnDirector())
    {
        bIsDead = true;
        UE_LOG(LogTemp, Warning, TEXT("HOVER_SPAWN_LEAK zombie=%s location=%s relocations=%d"), *GetName(),
               *GetActorLocation().ToString(), RelocationCount);
        OnDeath.Broadcast(this);
    }
    Super::EndPlay(Reason);
}

EHoverZombieRole AHoverCyberZombie::GetRole() const
{
    const auto *Definition = Cast<UHoverCyberZombieDefinition>(ZombieData);
    return Definition ? Definition->Role : EHoverZombieRole::Standard;
}

float AHoverCyberZombie::GetStompInterval() const
{
    const auto *Definition = Cast<UHoverCyberZombieDefinition>(ZombieData);
    return Definition ? Definition->StompInterval : .8f;
}

bool AHoverCyberZombie::StompImpact()
{
    // The Brute role always stomps (Cyber DA_Brute needs no edit); any other role needs bUsesStomp.
    const auto *Definition = Cast<UHoverCyberZombieDefinition>(ZombieData);
    const bool bStomper = GetRole() == EHoverZombieRole::Brute || (Definition && Definition->bUsesStomp);
    if (!bStomper || bIsDead || !bIsAttacking || GetWorld()->GetTimeSeconds() - LastStompTime < GetStompInterval())
        return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(BruteLanding), false, this);
    FVector Feet = GetActorLocation() - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    FHitResult Floor;
    if (!GetWorld()->LineTraceSingleByChannel(Floor, Feet + FVector(0, 0, 70), Feet - FVector(0, 0, 150),
                                              ECC_Visibility, Query) ||
        Floor.ImpactNormal.Z < .5f)
        return false;
    LastStompTime = GetWorld()->GetTimeSeconds();
    ++StompCount;
    // 0 keeps the purchased damage trace (Vexa honors the Invincible toggle); a multiplier applies
    // a radial 30 x multiplier hit inside StompRadius instead, with the same LOS test below.
    const float StompDamage = Definition ? 30.f * Definition->StompDamageMultiplier : 0.f;
    if (StompDamage <= 0.f)
        OnAttackHitCheck();
    const float Radius = Definition ? Definition->StompRadius : 400.f;
    for (TActorIterator<AHoverPilot> It(GetWorld()); It; ++It)
    {
        AHoverPilot *Pilot = *It;
        const FVector Target = Pilot->GetActorLocation();
        const FVector PlayerFeet = Target - FVector(0, 0, Pilot->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
        const bool Close = FVector::Dist2D(PlayerFeet, Floor.ImpactPoint) <= Radius &&
                           FMath::Abs(PlayerFeet.Z - Floor.ImpactPoint.Z) < 150.f;
        Query.AddIgnoredActor(Pilot);
        const bool Blocked =
            GetWorld()->LineTraceTestByChannel(Floor.ImpactPoint + FVector(0, 0, 65), Target, ECC_Visibility, Query);
        Pilot->ShowStompPulse(Floor.ImpactPoint, Floor.ImpactNormal, Radius, Close && !Blocked);
        if (Close && !Blocked && StompDamage > 0.f)
            UGameplayStatics::ApplyDamage(Pilot, StompDamage, GetController(), this, nullptr);
        if (Close && !Blocked && Pilot->GetController() && Pilot->ApplyStompKnockdown(Floor.ImpactPoint))
            ++StompKnockdowns;
        break;
    }
    return true;
}

void UHoverBruteStompNotify::Notify(USkeletalMeshComponent *MeshComp, UAnimSequenceBase *Animation,
                                    const FAnimNotifyEventReference &EventReference)
{
    if (auto *Zombie = MeshComp ? Cast<AHoverCyberZombie>(MeshComp->GetOwner()) : nullptr)
        Zombie->StompImpact();
}

float AHoverCyberZombie::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController,
                                    AActor *Causer)
{
    const bool WasAlive = !bIsDead;
    auto *Mode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
    FHitResult Hit;
    FVector Direction;
    Event.GetBestHitInfo(this, Causer, Hit, Direction);
    if (!bIsDead && Damage > 0)
    {
        if (EventController && EventController->GetPawn())
            UAISense_Damage::ReportDamageEvent(this, this, EventController->GetPawn(), Damage,
                                               EventController->GetPawn()->GetActorLocation(), GetActorLocation());
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_HIT causer=%s bone=%s damage=%.1f point=%s"), *GetNameSafe(Causer),
               *Hit.BoneName.ToString(), Damage, *Hit.ImpactPoint.ToString());
        ModifyIncomingDamage(Damage, Event, EventController, Causer, Hit);
        if (Event.IsOfType(FPointDamageEvent::ClassID) && Hit.bBlockingHit && Hit.GetActor() == this)
        {
            // NYC zombies whose definition authors HitBlood / HeadshotBlood spawn their own; every
            // other zombie (and an NYC definition without them) keeps NS_NS1_BloodShot.
            auto *NYCZombie = Cast<AHoverNYCZombie>(this);
            if (!(NYCZombie && NYCZombie->SpawnDefinitionHitBlood(Hit, Direction)) && Blood)
                HoverEffects::BloodBurst(GetWorld(), Blood, Hit.ImpactPoint, Direction);
        }
    }
    // Vendor health, hit montages, damage numbers, death, loot and wave callback.
    const float Result = Super::TakeDamage(Damage, Event, EventController, Causer);
    // Vendor damage retaliation can select an unoccupied collision-causing
    // vehicle independently of perception. Keep the same player-only rule here.
    if (!bIsDead)
        if (auto *AI = Cast<AHoverCyberZombieAI>(GetController()))
            if (auto *Blackboard = AI->GetBlackboardComponent())
            {
                APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0);
                if (Blackboard->GetValueAsObject(AZE_ZombieAIController::Key_TargetEnemy) != Player)
                {
                    if (AI->bDirectChaseMode && Player)
                        AI->SetTargetEnemy(Player);
                    else
                        Blackboard->ClearValue(AZE_ZombieAIController::Key_TargetEnemy);
                }
            }
    if (WasAlive && bIsDead && Mode && ZombieData)
        OnKilledBy(EventController, Causer, Hit);
    return Result;
}

void AHoverCyberZombie::ModifyIncomingDamage(float &Damage, const FDamageEvent &Event, AController *EventController,
                                             AActor *Causer, const FHitResult &Hit)
{
    // Insta-Kill: the pilot's hits one-shot the zombie.
    const auto *Mode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
    if (EventController && Cast<AHoverPilot>(EventController->GetPawn()) && SurvivalComponent && Mode &&
        Mode->HasInstaKill())
        Damage = FMath::Max(Damage, SurvivalComponent->GetHealth());
}

void AHoverCyberZombie::OnKilledBy(AController *EventController, AActor *Causer, const FHitResult &Hit)
{
    auto *Mode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
    if (!Mode || !ZombieData)
        return;
    // Authored KillPoints (NYC 90 / 115 / 105) replace the vendor roll; 0 keeps it for Cyber and Lakeside.
    const auto *Definition = Cast<UHoverCyberZombieDefinition>(ZombieData);
    int32 Points = FMath::RandRange(ZombieData->Stats.MinGoldReward, ZombieData->Stats.MaxGoldReward);
    if (Definition && Definition->KillPoints > 0)
    {
        const bool bHeadshot = Hit.BoneName.ToString().Contains(TEXT("head"), ESearchCase::IgnoreCase);
        const bool bMelee = Cast<AHoverMeleeWeapon>(Causer) != nullptr;
        Points = bMelee && Definition->MeleeKillPoints > 0         ? Definition->MeleeKillPoints
                 : bHeadshot && Definition->HeadshotKillPoints > 0 ? Definition->HeadshotKillPoints
                                                                   : Definition->KillPoints;
    }
    Mode->AddGold(Points);
}

float AHoverCyberCityGameMode::GetSpeedBonus() const
{
    return GetWorld()->GetTimeSeconds() < SpeedBonusUntil ? 1.5f : 1.f;
}
int32 AHoverCyberCityGameMode::GetGold() const
{
    for (TActorIterator<AHoverPilot> It(GetWorld()); It; ++It)
        if (It->Combat && It->Combat->Survival)
            return FMath::RoundToInt(It->Combat->Survival->GetGold());
    return Gold;
}
void AHoverCyberCityGameMode::AddGold(int32 Amount)
{
    for (TActorIterator<AHoverPilot> It(GetWorld()); It; ++It)
        if (It->Combat && It->Combat->Survival)
        {
            It->Combat->Survival->ApplyGoldDelta(Amount);
            return;
        }
    Gold += Amount;
}

bool AHoverCyberCityGameMode::HasInstaKill() const
{
    return GetWorld()->GetTimeSeconds() < InstaKillUntil;
}

void AHoverCyberCityGameMode::ActivatePowerUp(EZE_PowerUpType Type, float Duration)
{
    if (Type == EZE_PowerUpType::SpeedBoost)
        SpeedBonusUntil = GetWorld()->GetTimeSeconds() + Duration;
    if (Type == EZE_PowerUpType::InstaKill)
        InstaKillUntil = GetWorld()->GetTimeSeconds() + Duration;
}

void AHoverCyberPowerUp::OnOverlapBegin(UPrimitiveComponent *OverlappedComp, AActor *OtherActor,
                                        UPrimitiveComponent *OtherComp, int32 OtherBodyIndex, bool bFromSweep,
                                        const FHitResult &SweepResult)
{
    auto *Pawn = Cast<APawn>(OtherActor);
    auto *Mode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
    if (!Pawn || !Pawn->IsPlayerControlled() || !Mode || IsActorBeingDestroyed())
        return;
    Mode->ActivatePowerUp(PowerUpType, Duration);
    if (PowerUpType == EZE_PowerUpType::Nuke)
    {
        TArray<AActor *> Targets;
        UGameplayStatics::GetAllActorsOfClass(this, AHoverCyberZombie::StaticClass(), Targets);
        for (auto *Target : Targets)
            UGameplayStatics::ApplyDamage(Target, 999999.f, Pawn->GetController(), Pawn, UDamageType::StaticClass());
    }
    else if (PowerUpType == EZE_PowerUpType::Danger)
        UGameplayStatics::ApplyDamage(Pawn, DangerDamage, GetInstigatorController(), this, UDamageType::StaticClass());
    else if (PowerUpType == EZE_PowerUpType::MaxAmmo)
        for (TActorIterator<AHoverPilot> It(GetWorld()); It; ++It)
            if (It->Combat)
                It->Combat->RefillAmmo();
    if (PickupSound)
        UGameplayStatics::PlaySoundAtLocation(this, PickupSound, GetActorLocation());
    if (PickupFX)
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, PickupFX, GetActorLocation());
    Destroy();
}

void UHoverCyberWaveHUD::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    auto *Root = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("WaveRoot"));
    WidgetTree->RootWidget = Root;
    auto *Background = WidgetTree->ConstructWidget<UBorder>();
    Background->SetBrushColor(FLinearColor(.015f, .025f, .035f, .8f));
    Background->SetPadding(FMargin(14));
    auto *Position = Root->AddChildToCanvas(Background);
    Position->SetAnchors(FAnchors(1, 0));
    Position->SetAlignment(FVector2D(1, 0));
    Position->SetPosition(FVector2D(-24, 24));
    Position->SetSize(FVector2D(270, 190));
    auto *Column = WidgetTree->ConstructWidget<UVerticalBox>();
    Background->SetContent(Column);
    auto AddText = [this, Column](FName Name, int32 Size, FLinearColor Color) {
        auto *Text = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), Name);
        Text->SetFont(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"), Size));
        Text->SetColorAndOpacity(FSlateColor(Color));
        Column->AddChildToVerticalBox(Text);
        return Text;
    };
    WaveNumberText = AddText(TEXT("WaveNumberText"), 22, FLinearColor::White);
    EncounterText = AddText(TEXT("EncounterText"), 13, FLinearColor(1.f, .65f, .25f));
    WaveStateText = AddText(TEXT("WaveStateText"), 13, FLinearColor(.4f, .85f, 1.f));
    ZombiesRemainingText = AddText(TEXT("ZombiesRemainingText"), 16, FLinearColor::White);
    ZombiesKilledText = AddText(TEXT("ZombiesKilledText"), 14, FLinearColor(.7f, .8f, .85f));
    CountdownText = AddText(TEXT("CountdownText"), 18, FLinearColor(.4f, .85f, 1.f));
    WaveProgressBar = WidgetTree->ConstructWidget<UProgressBar>();
    WaveProgressBar->SetFillColorAndOpacity(FLinearColor(.15f, .7f, .9f));
    Column->AddChildToVerticalBox(WaveProgressBar);
    SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UHoverCyberWaveHUD::NativeTick(const FGeometry &Geometry, float DeltaTime)
{
    Super::NativeTick(Geometry, DeltaTime);
    if (EncounterText)
        if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
            EncounterText->SetText(FText::FromString(Mode->GetEncounterLabel()));
}
