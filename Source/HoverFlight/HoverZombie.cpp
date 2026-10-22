#include "HoverZombie.h"
#include "Animation/AnimSequence.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

AHoverZombie::AHoverZombie()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(32, 92);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    GetMesh()->SetRelativeLocation(FVector(0, 0, -92));
    GetMesh()->SetRelativeRotation(FRotator(0, -90, 0));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    GetMesh()->SetCollisionResponseToAllChannels(ECR_Ignore);
    GetMesh()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    GetCharacterMovement()->bRunPhysicsWithNoController = true;
    GetCharacterMovement()->MaxWalkSpeed = 95.f;
    GetCharacterMovement()->bOrientRotationToMovement = true;
    GetCharacterMovement()->RotationRate = FRotator(0, 120, 0);
    Trousers = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Trousers"));
    Shirt = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Shirt"));
    Trousers->SetupAttachment(GetMesh());
    Shirt->SetupAttachment(GetMesh());
    Trousers->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Shirt->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AHoverZombie::BeginPlay()
{
    Super::BeginPlay();
    Home = GetActorLocation();
    GetMesh()->SetSkeletalMesh(LoadObject<USkeletalMesh>(
        nullptr, TEXT("/Game/ZombieMale_AAB/Meshes/SKM_ZombieM_Male_WholeBody.SKM_ZombieM_Male_WholeBody")));
    Trousers->SetSkeletalMesh(LoadObject<USkeletalMesh>(
        nullptr, TEXT("/Game/ZombieMale_AAB/Meshes/Clothes/SKM_ZombieM_Male_Trousers.SKM_ZombieM_Male_Trousers")));
    Shirt->SetSkeletalMesh(LoadObject<USkeletalMesh>(
        nullptr, TEXT("/Game/ZombieMale_AAB/Meshes/Clothes/SKM_ZombieM_Male_Shirt_Open.SKM_ZombieM_Male_Shirt_Open")));
    Trousers->SetLeaderPoseComponent(GetMesh());
    Shirt->SetLeaderPoseComponent(GetMesh());
    Shirt->SetVisibility(GetUniqueID() % 2 == 0);
    GetMesh()->SetDisablePostProcessBlueprint(true);
    GetMesh()->SetMorphTarget(TEXT("Angry"), .75f);
    const TCHAR Variant = TEXT('A') + GetUniqueID() % 3;
    Walk = LoadObject<UAnimSequence>(
        nullptr, *FString::Printf(TEXT("/Game/HoverPrototype/Zombies/anim_Walk_%c.anim_Walk_%c"), Variant, Variant));
    Idle = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Zombies/anim_Idle_A.anim_Idle_A"));
    Blood = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Rocket/NS1_Blood/NS_NS1_BloodShot.NS_NS1_BloodShot"));
    GetMesh()->PlayAnimation(Idle, true);
    SetCanBeDamaged(true);
}

void AHoverZombie::Tick(float DT)
{
    Super::Tick(DT);
    if (bDead)
        return;
    WanderTime -= DT;
    APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0);
    FVector Direction = FVector::ZeroVector;
    if (Player && FVector::Dist2D(Player->GetActorLocation(), GetActorLocation()) < 2400)
    {
        Direction = Player->GetActorLocation() - GetActorLocation();
        Direction.Z = 0;
        if (Direction.Size2D() < 180)
            Direction = FVector::ZeroVector;
    }
    else
    {
        if (WanderTime <= 0)
        {
            const float Angle = FMath::FRandRange(-PI, PI);
            WanderDirection = FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0);
            if (FVector::Dist2D(Home, GetActorLocation()) > 900)
                WanderDirection = (Home - GetActorLocation()).GetSafeNormal2D();
            WanderTime = FMath::FRandRange(3.f, 7.f);
        }
        Direction = WanderDirection;
    }
    Direction = Direction.GetSafeNormal2D();
    FHitResult Obstacle;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ZombieWander), false, this);
    if (!Direction.IsNearlyZero() &&
        GetWorld()->SweepSingleByChannel(Obstacle, GetActorLocation(), GetActorLocation() + Direction * 100,
                                         FQuat::Identity, ECC_WorldStatic, FCollisionShape::MakeSphere(34), Params))
    {
        Direction = FVector::CrossProduct(Obstacle.ImpactNormal, FVector::UpVector).GetSafeNormal2D();
        WanderTime = 0;
    }
    AddMovementInput(Direction, 1.f, true);
    const bool Moving = GetVelocity().Size2D() > 8;
    if (Moving != bWalking)
    {
        bWalking = Moving;
        GetMesh()->PlayAnimation(Moving ? Walk : Idle, true);
    }
}

float AHoverZombie::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventInstigator, AActor *Causer)
{
    if (bDead || Damage <= 0)
        return 0;
    FHitResult Hit;
    FVector Direction = FVector::ForwardVector;
    Event.GetBestHitInfo(this, Causer, Hit, Direction);
    const bool Headshot = Hit.BoneName.ToString().Contains(TEXT("head"));
    const float Applied = Headshot ? 100.f : Damage;
    Health = FMath::Max(0.f, Health - Applied);
    if (Blood)
    {
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Blood, Hit.ImpactPoint, (-Direction).Rotation(),
                                                       FVector(.65f), true, true);
        if (Range)
            Range->RegisterBloodHit();
    }
    if (Health <= 0)
    {
        bDead = true;
        GetCharacterMovement()->StopMovementImmediately();
        GetCharacterMovement()->DisableMovement();
        GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        GetMesh()->SetCollisionProfileName(TEXT("Ragdoll"));
        GetMesh()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
        GetMesh()->SetAllBodiesSimulatePhysics(true);
        GetMesh()->SetSimulatePhysics(true);
        GetMesh()->WakeAllRigidBodies();
        GetMesh()->AddImpulseAtLocation(Direction * 6500.f, Hit.ImpactPoint, Hit.BoneName);
        SetLifeSpan(12.f);
        if (Range)
            Range->RegisterKill();
        UE_LOG(LogTemp, Display, TEXT("HOVER_ZOMBIE_KILLED headshot=%d"), Headshot);
    }
    return Applied;
}

AHoverZombieRange::AHoverZombieRange()
{
    PrimaryActorTick.bCanEverTick = true;
    Random.Initialize(7319);
}
int32 AHoverZombieRange::GetAliveCount() const
{
    int32 Count = 0;
    for (const AHoverZombie *Z : Zombies)
        if (IsValid(Z) && !Z->IsDead())
            ++Count;
    return Count;
}
bool AHoverZombieRange::SpawnZombie()
{
    for (int32 Attempt = 0; Attempt < 25; ++Attempt)
    {
        FVector Candidate;
        if (SpawnIndex < 3 && Attempt == 0)
            Candidate = Origin + FVector(1300 + SpawnIndex * 450, (SpawnIndex - 1) * 320, 0);
        else
        {
            const float Angle = Random.FRandRange(-PI, PI), Radius = Random.FRandRange(1200, 9000);
            Candidate = Origin + FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, 0);
        }
        FHitResult Floor;
        FCollisionQueryParams Params(SCENE_QUERY_STAT(ZombieSpawn));
        if (!GetWorld()->LineTraceSingleByChannel(Floor, Candidate + FVector(0, 0, 16000),
                                                  Candidate - FVector(0, 0, 9000), ECC_WorldStatic, Params) ||
            Floor.ImpactNormal.Z < .75f)
            continue;
        if (Floor.ImpactPoint.Z > Origin.Z + 1800)
            continue;
        Candidate = Floor.ImpactPoint + FVector(0, 0, 96);
        if (GetWorld()->OverlapBlockingTestByChannel(Candidate, FQuat::Identity, ECC_Pawn,
                                                     FCollisionShape::MakeCapsule(34, 94), Params))
            continue;
        const FRotator Facing(0, (Origin - Candidate).Rotation().Yaw, 0);
        auto *Z = GetWorld()->SpawnActor<AHoverZombie>(Candidate, Facing);
        if (Z)
        {
            Z->Range = this;
            Zombies.Add(Z);
            ++SpawnIndex;
            return true;
        }
    }
    return false;
}
void AHoverZombieRange::Tick(float DT)
{
    Super::Tick(DT);
    if (!bInitialized)
    {
        auto *Player = UGameplayStatics::GetPlayerPawn(this, 0);
        if (!Player)
            return;
        Origin = Player->GetActorLocation();
        bInitialized = true;
    }
    SpawnTime -= DT;
    if (SpawnTime <= 0)
    {
        SpawnTime = 2.5f;
        Zombies.RemoveAll([](const auto &Z) { return !IsValid(Z); });
        const int32 Missing = 20 - GetAliveCount();
        for (int32 I = 0; I < Missing; ++I)
            if (!SpawnZombie())
                break;
    }
}
