#include "HoverCyberCity.h"
#include "HoverPilot.h"
#include "HoverTestController.h"
#include "BehaviorTree/BlackboardComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
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

void AHoverCyberCityGameMode::InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);
    DefaultPawnClass =
        LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Hybrid/BP_Vexa_CLS_Parkour.BP_Vexa_CLS_Parkour_C"));
    PlayerControllerClass = AHoverTestController::StaticClass();
    HUDClass = AHoverHUD::StaticClass();
    WaveSettings = LoadObject<UZE_WaveGameModeSettings>(
        nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_CyberWaves.DA_CyberWaves"));
    if (WaveSettings)
        WaveSettings->WaveHUDClass = UHoverCyberWaveHUD::StaticClass();
    // Test settings pauses the complete session, including the wave countdown.
    PrimaryActorTick.bTickEvenWhenPaused = false;
}

AHoverCyberZombieAI::AHoverCyberZombieAI()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickInterval = .5f;
}

void AHoverCyberCityGameMode::Tick(float DT)
{
    ActiveSpawnCount = 0;
    auto *PC = UGameplayStatics::GetPlayerController(this, 0);
    APawn *Player = PC ? PC->GetPawn() : nullptr;
    if (Player)
    {
        Player->SetCanBeDamaged(false);
        if (!IsWaveHUDVisible() && WaveSettings && WaveSettings->WaveHUDClass)
        {
            TArray<UUserWidget *> Widgets;
            UWidgetBlueprintLibrary::GetAllWidgetsOfClass(this, Widgets, WaveSettings->WaveHUDClass, true);
            WaveDisplay = Widgets.Num() ? Widgets[0] : CreateWidget<UUserWidget>(PC, WaveSettings->WaveHUDClass);
            if (WaveDisplay && !WaveDisplay->IsInViewport())
                WaveDisplay->AddToViewport(10);
        }
        FVector Eye;
        FRotator View;
        PC->GetPlayerViewPoint(Eye, View);
        for (TActorIterator<AZE_ZombieSpawnPoint> It(GetWorld()); It; ++It)
        {
            const FVector Position = It->GetActorLocation();
            const float Distance = FVector::Dist2D(Position, Player->GetActorLocation());
            bool Safe = Distance >= 1400.f && Distance <= 10000.f;
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
            It->bIsEnabled = Safe;
            ActiveSpawnCount += Safe ? 1 : 0;
        }
    }
    // The vendor otherwise falls back to PlayerStart when all points are disabled.
    // Wait for a fair entrance instead of spawning beside Vexa or inside a vehicle.
    if (GetWaveState() != EZE_WaveState::WaveInProgress || ActiveSpawnCount > 0)
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
    if (GetPawn() && Player)
    {
        if (auto *Board = GetBlackboardComponent())
        {
            if (Board->GetValueAsObject(Key_TargetEnemy) != Player)
                SetTargetEnemy(Player);
            Board->SetValueAsVector(Key_LastKnownLocation, Player->GetActorLocation());
        }
    }
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
    if (auto *Body =
            LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/SK_CyberZombie.SK_CyberZombie")))
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
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    GetMesh()->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Blood = LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/Rocket/NS1_Blood/NS_NS1_BloodShot.NS_NS1_BloodShot"));
}

float AHoverCyberZombie::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController,
                                    AActor *Causer)
{
    const bool WasAlive = !bIsDead;
    auto *Mode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
    if (!bIsDead && Damage > 0)
    {
        FHitResult Hit;
        FVector Direction;
        Event.GetBestHitInfo(this, Causer, Hit, Direction);
        if (Cast<AHoverPilot>(Causer) && SurvivalComponent &&
            (Hit.BoneName.ToString().Contains(TEXT("head"), ESearchCase::IgnoreCase) || (Mode && Mode->HasInstaKill())))
            Damage = FMath::Max(Damage, SurvivalComponent->GetHealth());
        if (Blood)
            UNiagaraFunctionLibrary::SpawnSystemAtLocation(this, Blood, Hit.ImpactPoint, (-Direction).Rotation(),
                                                           FVector(.65f), true, true);
    }
    // Vendor health, hit montages, damage numbers, death, loot and wave callback.
    const float Result = Super::TakeDamage(Damage, Event, EventController, Causer);
    if (WasAlive && bIsDead && Mode && ZombieData)
        Mode->AddGold(FMath::RandRange(ZombieData->Stats.MinGoldReward, ZombieData->Stats.MaxGoldReward));
    return Result;
}

float AHoverCyberCityGameMode::GetSpeedBonus() const
{
    return GetWorld()->GetTimeSeconds() < SpeedBonusUntil ? 1.5f : 1.f;
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
    // Sandbox health and ammunition are unlimited; those pickups remain harmless.
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
    Position->SetSize(FVector2D(250, 164));
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
    WaveStateText = AddText(TEXT("WaveStateText"), 13, FLinearColor(.4f, .85f, 1.f));
    ZombiesRemainingText = AddText(TEXT("ZombiesRemainingText"), 16, FLinearColor::White);
    ZombiesKilledText = AddText(TEXT("ZombiesKilledText"), 14, FLinearColor(.7f, .8f, .85f));
    CountdownText = AddText(TEXT("CountdownText"), 18, FLinearColor(.4f, .85f, 1.f));
    WaveProgressBar = WidgetTree->ConstructWidget<UProgressBar>();
    WaveProgressBar->SetFillColorAndOpacity(FLinearColor(.15f, .7f, .9f));
    Column->AddChildToVerticalBox(WaveProgressBar);
    SetVisibility(ESlateVisibility::HitTestInvisible);
}
