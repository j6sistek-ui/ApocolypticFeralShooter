#include "HoverPickupFeedback.h"
#include "HoverCyberCity.h"
#include "HoverNYCSurvival.h"
#include "HoverCombatBridge.h"
#include "HoverPilot.h"
#include "AIController.h"
#include "BrainComponent.h"
#include "Animation/AnimInstance.h"
#include "Components/PointLightComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/ForceFeedbackEffect.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/WorldSettings.h"
#include "Interaction/ZE_InteractableInterface.h"
#include "Inventory/ZE_AmmoDefinition.h"
#include "Inventory/ZE_InventoryComponent.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "UI/ZE_DamageNumberActor.h"
#include "UObject/ConstructorHelpers.h"
#include "Weapons/ZE_WeaponBase.h"

namespace
{
constexpr float PickupToastSeconds = 1.6f;
constexpr float PickupReserveFlashSeconds = 1.2f;
constexpr int32 PickupMaxToasts = 4;
const FLinearColor PickupAmmoColor(1.f, .86f, .35f);
const FLinearColor PickupPointsColor(.75f, 1.f, .75f);
const FLinearColor PickupDeniedColor(1.f, .35f, .3f);

USoundBase *PickPickupSound(const TArray<TSoftObjectPtr<USoundBase>> &Sounds)
{
    TArray<USoundBase *> Loaded;
    for (const auto &Sound : Sounds)
        if (USoundBase *Asset = Sound.LoadSynchronous())
            Loaded.Add(Asset);
    return Loaded.Num() ? Loaded[FMath::RandRange(0, Loaded.Num() - 1)] : nullptr;
}

AZE_WeaponBase *PickupHeldWeapon(APawn *Pawn)
{
    if (!Pawn)
        return nullptr;
    const UHoverCombatBridge *Combat = nullptr;
    if (const auto *Pilot = Cast<AHoverPilot>(Pawn))
        Combat = Pilot->Combat;
    if (!Combat)
        Combat = Pawn->FindComponentByClass<UHoverCombatBridge>();
    return Combat ? Combat->GetWeapon() : nullptr;
}
} // namespace

// ---------------------------------------------------------------------------------------------
// Data defaults (owner-editable on the Blueprints).

FHoverNukePresentation::FHoverNukePresentation()
{
    // Placeholder name, not a Call of Duty power-up name: the owner renames it on BP_CyberPower_Nuke.
    BannerText = NSLOCTEXT("HoverPickups", "NukeBanner", "STREET SWEEP");
    BannerSubtext = NSLOCTEXT("HoverPickups", "NukeSubtext", "every zombie down");
    ExplosionSound = TSoftObjectPtr<USoundBase>(
        FSoftObjectPath(TEXT("/Game/SF_Explosives_SFX/CUE/CUE_Sci-Fi_Deep_Explosion_1_Cue.CUE_Sci-Fi_Deep_Explosion_1_Cue")));
    Shockwave = TSoftObjectPtr<UNiagaraSystem>(FSoftObjectPath(
        TEXT("/Game/Vefects/Easy_Shockwaves_VFX/VFX/Shockwaves/Particles/VFX_Shockwave_01_White_Big_1s."
             "VFX_Shockwave_01_White_Big_1s")));
    ShockwaveDistortion = TSoftObjectPtr<UNiagaraSystem>(FSoftObjectPath(
        TEXT("/Game/Vefects/Easy_Shockwaves_VFX/VFX/Shockwaves_Distortion/Particles/VFX_Shockwave_Distortion_01_Big_1s."
             "VFX_Shockwave_Distortion_01_Big_1s")));
    Rumble.LeftLarge = {FVector2D(0.f, 1.f), FVector2D(.25f, .8f), FVector2D(.7f, 0.f)};
    Rumble.RightSmall = {FVector2D(0.f, .7f), FVector2D(.12f, .45f), FVector2D(.35f, 0.f)};
}

FHoverAmmoPresentation::FHoverAmmoPresentation()
{
    for (const TCHAR *Name : {TEXT("A_ItemPickup_001"), TEXT("A_ItemPickup_002"), TEXT("A_ItemPickup_003"),
                              TEXT("A_ItemPickup_004")})
        PickupSounds.Add(TSoftObjectPtr<USoundBase>(FSoftObjectPath(
            FString::Printf(TEXT("/Game/HoverPrototype/Audio/NYC/Gameplay/ItemPickup/%s.%s"), Name, Name))));
    Outline = TSoftObjectPtr<UMaterialInterface>(
        FSoftObjectPath(TEXT("/Game/ZESP/ZE/Material/Base/MI_ZE_Outline_Gold.MI_ZE_Outline_Gold")));
    ToastFormat = NSLOCTEXT("HoverPickups", "AmmoToast", "+{0} AMMO");
    OtherAmmoToastFormat = NSLOCTEXT("HoverPickups", "OtherAmmoToast", "+{0} {1}");
}

// ---------------------------------------------------------------------------------------------
// Subsystem.

UHoverPickupFeedback *UHoverPickupFeedback::Get(const UObject *WorldContext)
{
    UWorld *World =
        GEngine && WorldContext ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
    return World ? World->GetSubsystem<UHoverPickupFeedback>() : nullptr;
}

UHoverPickupFeedback *UHoverPickupFeedback::GetFeedback(const UObject *WorldContextObject)
{
    return Get(WorldContextObject);
}

bool UHoverPickupFeedback::IsNYCSurvival(const UObject *WorldContext)
{
    UWorld *World =
        GEngine && WorldContext ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr;
    return World && World->GetAuthGameMode<AHoverNYCSurvivalGameMode>() != nullptr;
}

bool UHoverPickupFeedback::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UHoverPickupFeedback::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UHoverPickupFeedback, STATGROUP_Tickables);
}

FIntPoint UHoverPickupFeedback::GetPawnAmmo(APawn *Pawn)
{
    const AZE_WeaponBase *Weapon = PickupHeldWeapon(Pawn);
    return Weapon ? FIntPoint(Weapon->GetCurrentClipAmmo(), Weapon->GetReserveAmmo()) : FIntPoint(-1, -1);
}

float UHoverPickupFeedback::GetNukeAge() const
{
    return NukeStart < 0 ? -1.f : float(Clock - NukeStart);
}

float UHoverPickupFeedback::GetFlashAlpha() const
{
    const float Age = GetNukeAge();
    if (Age < 0 || Nuke.FlashSeconds <= 0 || Age >= Nuke.FlashSeconds)
        return 0.f;
    return Nuke.FlashAlpha * FMath::Square(1.f - Age / Nuke.FlashSeconds);
}

bool UHoverPickupFeedback::IsBannerVisible() const
{
    const float Age = GetNukeAge();
    return Age >= 0 && Age < Nuke.BannerSeconds;
}

float UHoverPickupFeedback::GetLastToastAge() const
{
    return LastToastStart < 0 ? -1.f : float(Clock - LastToastStart);
}

float UHoverPickupFeedback::GetReserveFlashAge() const
{
    return ReserveFlashStart < 0 ? -1.f : float(Clock - ReserveFlashStart);
}

void UHoverPickupFeedback::Toast(const FString &Text, FLinearColor Color)
{
    if (Text.IsEmpty())
        return;
    if (Toasts.Num() >= PickupMaxToasts)
        Toasts.RemoveAt(0);
    Toasts.Add({Text, Color, Clock});
    LastToastText = Text;
    LastToastStart = Clock;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_PICKUP_TOAST text=\"%s\" real=%.3f"), *Text, Clock);
}

void UHoverPickupFeedback::NotifyAmmo(const FString &Text)
{
    Toast(Text, PickupAmmoColor);
    ReserveFlashStart = Clock;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_TOAST text=\"%s\" reserve_flash=1"), *Text);
}

bool UHoverPickupFeedback::BeginNuke(AActor *Pickup, APawn *Picker, const TArray<AActor *> &Targets,
                                     const FHoverNukePresentation &Presentation)
{
    if (!Pickup || !Picker || !IsNYCSurvival(Pickup))
        return false;
    UHoverPickupFeedback *Self = Get(Pickup);
    if (!Self)
        return false;
    Self->StartNuke(Pickup->GetActorLocation(), Picker, Targets, Presentation);
    return true;
}

void UHoverPickupFeedback::StartNuke(const FVector &Origin, APawn *Picker, const TArray<AActor *> &Targets,
                                     const FHoverNukePresentation &Presentation)
{
    UWorld *World = GetWorld();
    // A second Nuke during a ripple finishes the first at once, then starts its own sequence.
    for (FRippleTarget &Target : Ripple)
        if (!Target.bDone)
            KillRippleTarget(Target);
    Ripple.Reset();
    NukeKillRows.Reset();
    NukeKillCount = 0;
    HiddenDamageNumbers = 0;

    Nuke = Presentation;
    NukeOrigin = Origin;
    NukeStart = Clock;
    NukeGameStart = World->GetTimeSeconds();
    NukeInstigator = Picker->GetController();
    NukeCauser = Picker;

    // Freeze the living crowd in a stunned pose until its ring arrives.
    float MaxDistance = 0.f;
    for (AActor *Actor : Targets)
    {
        auto *Zombie = Cast<AHoverCyberZombie>(Actor);
        if (!IsValid(Zombie) || Zombie->IsDead())
            continue;
        FRippleTarget Target;
        Target.Zombie = Zombie;
        Target.Distance = float(FVector::Dist2D(Zombie->GetActorLocation(), Origin));
        MaxDistance = FMath::Max(MaxDistance, Target.Distance);
        Ripple.Add(Target);
        if (auto *AI = Cast<AAIController>(Zombie->GetController()))
        {
            AI->StopMovement();
            if (AI->BrainComponent)
                AI->BrainComponent->PauseLogic(TEXT("HoverNuke"));
        }
        if (auto *Move = Zombie->GetCharacterMovement())
            Move->StopMovementImmediately();
        if (UAnimInstance *Anim = Zombie->GetMesh() ? Zombie->GetMesh()->GetAnimInstance() : nullptr)
            Anim->Montage_Stop(.1f);
        Zombie->CustomTimeDilation = FMath::Clamp(Nuke.StunDilation, .01f, 1.f);
    }
    for (FRippleTarget &Target : Ripple)
        Target.Delay = MaxDistance > 1.f ? Nuke.RippleSeconds * Target.Distance / MaxDistance : 0.f;
    NukeTargetCount = Ripple.Num();
    UE_LOG(LogTemp, Display, TEXT("HOVER_NUKE_BEGIN targets=%d maxdist=%.0f ripple=%.2f origin=%s real=%.3f game=%.3f"),
           NukeTargetCount, MaxDistance, Nuke.RippleSeconds, *Origin.ToCompactString(), Clock, NukeGameStart);

    if (USoundBase *Sound = Nuke.ExplosionSound.LoadSynchronous())
    {
        UGameplayStatics::PlaySound2D(World, Sound, Nuke.ExplosionVolume);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_SOUND sound=%s"), *GetNameSafe(Sound));
    }
    else
        UE_LOG(LogTemp, Warning, TEXT("HOVER_NUKE_SOUND missing %s"), *Nuke.ExplosionSound.ToString());
    int32 Effects = 0;
    for (const TSoftObjectPtr<UNiagaraSystem> &Effect : {Nuke.Shockwave, Nuke.ShockwaveDistortion})
        if (UNiagaraSystem *System = Effect.LoadSynchronous())
            Effects += UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Origin + FVector(0, 0, 5.f),
                                                                      FRotator::ZeroRotator,
                                                                      FVector(Nuke.ShockwaveScale), true, true,
                                                                      ENCPoolMethod::None, false) != nullptr;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_SHOCKWAVE spawned=%d system=%s"), Effects,
           *Nuke.Shockwave.ToSoftObjectPath().GetAssetName());

    if (auto *PC = Cast<APlayerController>(Picker->GetController()); PC && PC->IsLocalController())
    {
        if (Nuke.ShakeScale > 0)
            PC->ClientStartCameraShake(UHoverBlastShake::StaticClass(), Nuke.ShakeScale);
        UForceFeedbackEffect *Effect = Nuke.Rumble.Override.LoadSynchronous();
        if (!Effect)
        {
            if (!NukeRumble)
                NukeRumble = HoverHaptics::Build(this, Nuke.Rumble);
            Effect = NukeRumble;
        }
        if (Effect)
        {
            FForceFeedbackParameters Parameters;
            Parameters.Tag = TEXT("HoverNuke");
            Parameters.bIgnoreTimeDilation = true;
            PC->ClientPlayForceFeedback(Effect, Parameters);
        }
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_FEEL shake=%.2f rumble=%d"), Nuke.ShakeScale, Effect != nullptr);
    }

    const auto *Mode = World->GetAuthGameMode<AHoverNYCSurvivalGameMode>();
    if (Nuke.bSlowMotion && Nuke.SlowMotionSeconds > 0 && !(Mode && Mode->IsGameOver()))
    {
        UGameplayStatics::SetGlobalTimeDilation(World, Nuke.SlowMotionDilation);
        bSlowMotionActive = true;
        SlowMotionEnd = Clock + Nuke.SlowMotionSeconds;
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_SLOWMO dilation=%.2f seconds=%.2f"), Nuke.SlowMotionDilation,
               Nuke.SlowMotionSeconds);
    }
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_FLASH alpha=%.2f seconds=%.2f"), Nuke.FlashAlpha, Nuke.FlashSeconds);
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_BANNER text=\"%s\" seconds=%.2f"), *Nuke.BannerText.ToString(),
           Nuke.BannerSeconds);
}

void UHoverPickupFeedback::KillRippleTarget(FRippleTarget &Target)
{
    Target.bDone = true;
    auto *Zombie = Cast<AHoverCyberZombie>(Target.Zombie.Get());
    if (!IsValid(Zombie) || Zombie->IsDead())
        return;
    UWorld *World = GetWorld();
    Zombie->CustomTimeDilation = 1.f;
    const FVector Where = Zombie->GetActorLocation();
    // Same damage, instigator and causer as the vendor loop, so kill points, loot and the wave count are unchanged.
    UGameplayStatics::ApplyDamage(Zombie, 999999.f, NukeInstigator.Get(), NukeCauser.Get(), UDamageType::StaticClass());
    int32 Hidden = 0;
    if (Nuke.bHideDamageNumbers)
        for (TActorIterator<AZE_DamageNumberActor> It(World); It; ++It)
            if (!It->IsActorBeingDestroyed() && FVector::Dist(It->GetActorLocation(), Where) < 350.f)
            {
                It->Destroy();
                ++Hidden;
            }
    HiddenDamageNumbers += Hidden;
    const bool bDead = Zombie->IsDead();
    if (!bDead)
        // Invincible or scripted survivor: hand the brain back.
        if (auto *AI = Cast<AAIController>(Zombie->GetController()); AI && AI->BrainComponent)
            AI->BrainComponent->ResumeLogic(TEXT("HoverNuke"));
    NukeKillCount += bDead;
    const float Real = float(Clock - NukeStart);
    const float Game = float(World->GetTimeSeconds() - NukeGameStart);
    NukeKillRows.Add(FVector(Target.Distance, Real, Game));
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_KILL zombie=%s dist=%.0f delay=%.3f real=%.3f game=%.3f dead=%d hidden=%d"),
           *Zombie->GetName(), Target.Distance, Target.Delay, Real, Game, bDead, Hidden);
}

void UHoverPickupFeedback::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    UWorld *World = GetWorld();
    if (!World)
        return;
    // Undilated frame time (the fixed step in a headless proof), capped against hitches.
    Clock += FMath::Clamp(double(World->DeltaRealTimeSeconds), 0., .1);

    if (NukeStart >= 0)
    {
        const double Age = Clock - NukeStart;
        bool bPending = false;
        for (FRippleTarget &Target : Ripple)
            if (!Target.bDone)
            {
                if (Age >= Target.Delay)
                    KillRippleTarget(Target);
                else
                    bPending = true;
            }
        if (!bPending && Ripple.Num())
        {
            UE_LOG(LogTemp, Display, TEXT("HOVER_NUKE_END kills=%d targets=%d hidden_numbers=%d real=%.3f"),
                   NukeKillCount, NukeTargetCount, HiddenDamageNumbers, Age);
            Ripple.Reset();
        }
    }
    if (bSlowMotionActive && Clock >= SlowMotionEnd)
    {
        bSlowMotionActive = false;
        const auto *Mode = World->GetAuthGameMode<AHoverNYCSurvivalGameMode>();
        const AWorldSettings *Settings = World->GetWorldSettings();
        // Leave the dilation alone if the death cam (or anything else) changed it meanwhile.
        if (!(Mode && Mode->IsGameOver()) && Settings &&
            FMath::IsNearlyEqual(Settings->TimeDilation, Nuke.SlowMotionDilation, .001f))
            UGameplayStatics::SetGlobalTimeDilation(World, 1.f);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_NUKE_SLOWMO_END real=%.3f dilation=%.2f"), Clock - NukeStart,
               Settings ? Settings->TimeDilation : -1.f);
    }
    Toasts.RemoveAll([this](const FToast &Entry) { return Clock - Entry.Start >= PickupToastSeconds; });
}

// ---------------------------------------------------------------------------------------------
// HUD (called from AHoverHUD::DrawHUD; immediate-mode canvas like the rest of that HUD).

static UCanvas *HudCanvas(const AHUD *HUD)
{
    const AHoverHUD *Hover = Cast<AHoverHUD>(HUD);
    return Hover ? Hover->GetHudCanvas() : nullptr;
}

void UHoverPickupFeedback::DrawHUD(AHUD *HUD)
{
    if (!HUD || !HudCanvas(HUD))
        return;
    if (const UHoverPickupFeedback *Self = Get(HUD))
    {
        Self->DrawNuke(HUD);
        Self->DrawToasts(HUD);
    }
}

void UHoverPickupFeedback::DrawNuke(AHUD *HUD) const
{
    const float Age = GetNukeAge();
    if (Age < 0)
        return;
    const float W = HudCanvas(HUD)->ClipX, H = HudCanvas(HUD)->ClipY;
    if (const float Flash = GetFlashAlpha(); Flash > 0)
        HUD->DrawRect(FLinearColor(1.f, 1.f, 1.f, Flash), 0, 0, W, H);
    if (Age >= Nuke.BannerSeconds)
        return;
    const float In = FMath::Clamp(Age / .12f, 0.f, 1.f);
    const float Out = FMath::Clamp((Nuke.BannerSeconds - Age) / .5f, 0.f, 1.f);
    const float Alpha = In * Out;
    const float Pop = 1.f + .3f * FMath::Clamp(1.f - Age / .2f, 0.f, 1.f);
    const float Res = FMath::Max(H / 1080.f, .5f);
    UFont *Large = GEngine ? GEngine->GetLargeFont() : nullptr;
    UFont *Medium = GEngine ? GEngine->GetMediumFont() : nullptr;
    const FString Text = Nuke.BannerText.ToString();
    const FString Sub = Nuke.BannerSubtext.ToString();
    const float Scale = 2.4f * Pop * Res, SubScale = 1.4f * Res;
    float TW = 0, TH = 0, SW = 0, SH = 0;
    HUD->GetTextSize(Text, TW, TH, Large, Scale);
    if (!Sub.IsEmpty())
        HUD->GetTextSize(Sub, SW, SH, Medium, SubScale);
    const float Y = H * .24f - TH * .5f;
    HUD->DrawRect(FLinearColor(0.f, 0.f, 0.f, .45f * Alpha), 0, Y - TH * .2f, W, TH * 1.3f + SH * 1.2f);
    FLinearColor Color = Nuke.BannerColor;
    Color.A = Alpha;
    HUD->DrawText(Text, FLinearColor(0.f, 0.f, 0.f, .8f * Alpha), (W - TW) * .5f + 3.f, Y + 3.f, Large, Scale);
    HUD->DrawText(Text, Color, (W - TW) * .5f, Y, Large, Scale);
    if (!Sub.IsEmpty())
        HUD->DrawText(Sub, FLinearColor(1.f, 1.f, 1.f, .9f * Alpha), (W - SW) * .5f, Y + TH * 1.05f, Medium, SubScale);
}

void UHoverPickupFeedback::DrawToasts(AHUD *HUD) const
{
    if (Toasts.IsEmpty())
        return;
    const float W = HudCanvas(HUD)->ClipX, H = HudCanvas(HUD)->ClipY;
    // Stacked just above the ammo counter (AHoverHUD draws it at ClipX - 285, ClipY - 185), newest lowest.
    for (int32 Index = 0; Index < Toasts.Num(); ++Index)
    {
        const FToast &Entry = Toasts[Index];
        const float Age = float(Clock - Entry.Start);
        const float Rise = 24.f * FMath::Clamp(Age / PickupToastSeconds, 0.f, 1.f);
        const float Y = H - 225.f - float(Toasts.Num() - 1 - Index) * 30.f - Rise;
        FLinearColor Color = Entry.Color;
        Color.A = FMath::Clamp((PickupToastSeconds - Age) / .5f, 0.f, 1.f);
        HUD->DrawText(Entry.Text, FLinearColor(0.f, 0.f, 0.f, .8f * Color.A), W - 283.f, Y + 2.f, nullptr, 1.4f);
        HUD->DrawText(Entry.Text, Color, W - 285.f, Y, nullptr, 1.4f);
    }
}

void UHoverPickupFeedback::DrawReserveFlash(AHUD *HUD, int32 Clip, int32 Reserve, bool bMelee, float X, float Y,
                                            float Scale)
{
    const UHoverPickupFeedback *Self = HUD && HudCanvas(HUD) ? Get(HUD) : nullptr;
    if (!Self || bMelee || Self->ReserveFlashStart < 0)
        return;
    const float Age = float(Self->Clock - Self->ReserveFlashStart);
    if (Age < 0 || Age >= PickupReserveFlashSeconds)
        return;
    // Overdraws the reserve digits of the "%d / %d" line in a pulsing gold, same font and scale.
    float PrefixWidth = 0, PrefixHeight = 0;
    HUD->GetTextSize(FString::Printf(TEXT("%d / "), Clip), PrefixWidth, PrefixHeight, nullptr, Scale);
    const float Pulse = .5f + .5f * FMath::Cos(Age * 2.f * PI * 3.f);
    FLinearColor Color = FMath::Lerp(FLinearColor::White, PickupAmmoColor, Pulse);
    Color.A = FMath::Clamp((PickupReserveFlashSeconds - Age) / .3f, 0.f, 1.f);
    HUD->DrawText(FString::FromInt(Reserve), Color, X + PrefixWidth, Y, nullptr, Scale);
}

// ---------------------------------------------------------------------------------------------
// AHoverAmmoPickup (declared in HoverCyberCity.h; its floor-snapping BeginPlay stays in HoverCyberCity.cpp).

AHoverAmmoPickup::AHoverAmmoPickup(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer)
{
    // The vendor interactable never ticks; the first tick turns this off again outside NYC Survival.
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
}

void AHoverAmmoPickup::SetupPresentation()
{
    bPresentationActive = true;
    const FHoverAmmoPresentation &P = Presentation;
    if (LootStaticMesh)
    {
        LootStaticMesh->SetRelativeScale3D(LootStaticMesh->GetRelativeScale3D() * P.ScaleMultiplier);
        MeshBase = LootStaticMesh->GetRelativeLocation();
        MeshBaseRotation = LootStaticMesh->GetRelativeRotation();
        if (UMaterialInterface *Outline = P.Outline.LoadSynchronous())
        {
            // Outline always on; the focus highlight uses the same material.
            OverlayMaterialOverride = Outline;
            bDisableOverlayByDefault = false;
            LootStaticMesh->SetOverlayMaterial(Outline);
        }
    }
    Glint = NewObject<UPointLightComponent>(this, TEXT("AmmoGlint"));
    Glint->SetupAttachment(GetRootComponent());
    Glint->SetRelativeLocation(FVector(0, 0, P.BobLift + 30.f));
    Glint->SetIntensityUnits(ELightUnits::Candelas);
    Glint->SetIntensity(P.GlintCandela);
    Glint->SetLightColor(P.GlintColor);
    Glint->SetAttenuationRadius(P.GlintRadius);
    Glint->SetSourceRadius(4.f);
    Glint->SetCastShadows(false);
    Glint->RegisterComponent();
    AddInstanceComponent(Glint);
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_PRESENT pickup=%s outline=%s glint=1 item=%s qty=%d"), *GetName(),
           *GetNameSafe(LootStaticMesh ? LootStaticMesh->GetOverlayMaterial() : nullptr), *GetNameSafe(ItemDefinition),
           PickupQuantity);
}

void AHoverAmmoPickup::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bPresentationChecked)
    {
        bPresentationChecked = true;
        if (!UHoverPickupFeedback::IsNYCSurvival(this))
        {
            SetActorTickEnabled(false);
            return;
        }
        SetupPresentation();
    }
    if (!bPresentationActive || bPickedUp)
        return;
    const FHoverAmmoPresentation &P = Presentation;
    PresentAge += DeltaSeconds;
    if (LootStaticMesh && !LootStaticMesh->IsSimulatingPhysics())
    {
        LootStaticMesh->SetRelativeLocation(
            MeshBase + FVector(0, 0, P.BobLift + P.BobHeight * FMath::Sin(PresentAge * 2.f * PI * P.BobHz)));
        LootStaticMesh->SetRelativeRotation(MeshBaseRotation + FRotator(0, PresentAge * P.SpinDegrees, 0));
        // The vendor focus-end path restores the overlay cached at BeginPlay (none); keep the outline on.
        if (OverlayMaterialOverride && LootStaticMesh->GetOverlayMaterial() != OverlayMaterialOverride)
            LootStaticMesh->SetOverlayMaterial(OverlayMaterialOverride);
    }
    if (Glint)
        Glint->SetIntensity(P.GlintCandela * (.35f + .65f * FMath::Square(FMath::Sin(PresentAge * PI * P.GlintHz))));
    if (!P.bAutoPickup)
        return;
    APawn *Pawn = UGameplayStatics::GetPlayerPawn(this, 0);
    if (!Cast<AHoverPilot>(Pawn))
        return;
    const FVector Delta = Pawn->GetActorLocation() - GetActorLocation();
    if (Delta.Size2D() < P.AutoPickupRadius && FMath::Abs(Delta.Z) < 160.f &&
        IZE_InteractableInterface::Execute_CanInteract(this, Pawn))
    {
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_AUTOPICKUP pickup=%s dist=%.0f"), *GetName(), Delta.Size2D());
        IZE_InteractableInterface::Execute_Interact(this, Pawn);
    }
}

void AHoverAmmoPickup::Interact_Implementation(APawn *InteractingPawn)
{
    // The walk-over and the vendor X / F hold can both reach this on one frame.
    if (bPickedUp)
        return;
    const FIntPoint Before = UHoverPickupFeedback::GetPawnAmmo(InteractingPawn);
    UZE_ItemDefinition *Item = ItemDefinition;
    const int32 Quantity = FMath::Max(1, PickupQuantity);
    Super::Interact_Implementation(InteractingPawn);
    const FIntPoint After = UHoverPickupFeedback::GetPawnAmmo(InteractingPawn);
    const bool bTaken = IsActorBeingDestroyed() || After.Y > Before.Y;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_PICKUP pickup=%s taken=%d item=%s qty=%d reserve=%d->%d"), *GetName(),
           bTaken, *GetNameSafe(Item), Quantity, Before.Y, After.Y);
    if (!bTaken)
        return;
    // Latch only when the vendor consumed the drop; a partial take leaves it live for the next interact.
    bPickedUp = IsActorBeingDestroyed();
    if (!bPresentationActive)
        return; // Cyber City and Lakeside: vendor behaviour only.
    if (USoundBase *Sound = PickPickupSound(Presentation.PickupSounds))
    {
        UGameplayStatics::PlaySoundAtLocation(this, Sound, GetActorLocation(), Presentation.SoundVolume);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_PICKUP_SOUND sound=%s"), *GetNameSafe(Sound));
    }
    const int32 Gained = After.Y - Before.Y;
    const FText Text = Gained > 0 ? FText::Format(Presentation.ToastFormat, FText::AsNumber(Gained))
                                  : FText::Format(Presentation.OtherAmmoToastFormat, FText::AsNumber(Quantity),
                                                  Item ? Item->DisplayName : FText::GetEmpty());
    if (UHoverPickupFeedback *Feedback = UHoverPickupFeedback::Get(this))
    {
        if (Gained > 0)
            Feedback->NotifyAmmo(Text.ToString().ToUpper());
        else
            Feedback->Toast(Text.ToString().ToUpper(), PickupAmmoColor);
    }
    // A drop the vendor keeps (bDestroyOnPickup off) stays live and keeps its glint.
    if (Glint && bPickedUp)
        Glint->SetVisibility(false);
}

// ---------------------------------------------------------------------------------------------
// AHoverAmmoStation.

AHoverAmmoStation::AHoverAmmoStation()
{
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Crate(TEXT("/Game/ZESP/ZE/Meshes/Tools/SM_AmmoBox.SM_AmmoBox"));
    if (Crate.Succeeded() && MeshComponent)
        MeshComponent->SetStaticMesh(Crate.Object);
    bRequiresHold = true;
    AmmoCost = 250;
    PurchaseSound = TSoftObjectPtr<USoundBase>(FSoftObjectPath(
        TEXT("/Game/HoverPrototype/Audio/NYC/Gameplay/ItemPickup/A_ItemPickup_002.A_ItemPickup_002")));
    Outline = TSoftObjectPtr<UMaterialInterface>(
        FSoftObjectPath(TEXT("/Game/ZESP/ZE/Material/Base/MI_ZE_Outline_Gold.MI_ZE_Outline_Gold")));
    PromptFormat = NSLOCTEXT("HoverPickups", "StationPrompt", "Buy Ammo: {0} +{1} ({2} Points)");
    FullText = NSLOCTEXT("HoverPickups", "StationFull", "Ammo full");
    NoGunText = NSLOCTEXT("HoverPickups", "StationNoGun", "Ammo crate (hold a gun)");
    NoPointsText = NSLOCTEXT("HoverPickups", "StationNoPoints", "NOT ENOUGH POINTS");
}

void AHoverAmmoStation::OnConstruction(const FTransform &Transform)
{
    Super::OnConstruction(Transform);
    if (const UStaticMesh *Mesh = MeshComponent ? MeshComponent->GetStaticMesh() : nullptr)
    {
        const FVector Extent = Mesh->GetBounds().BoxExtent;
        const float Width = FMath::Max(Extent.X, Extent.Y) * 2.f;
        MeshComponent->SetRelativeScale3D(FVector(CrateWidth / FMath::Max(Width, 1.f)));
    }
}

void AHoverAmmoStation::BeginPlay()
{
    Super::BeginPlay();
    if (UMaterialInterface *Material = Outline.LoadSynchronous())
    {
        OverlayMaterialOverride = Material;
        bDisableOverlayByDefault = false;
        if (MeshComponent)
            MeshComponent->SetOverlayMaterial(Material);
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_AMMO_STATION ready=%s cost=%d at=%s"), *GetName(), AmmoCost,
           *GetActorLocation().ToCompactString());
}

int32 AHoverAmmoStation::MissingRounds(APawn *Pawn, AZE_WeaponBase **OutWeapon) const
{
    AZE_WeaponBase *Weapon = PickupHeldWeapon(Pawn);
    if (OutWeapon)
        *OutWeapon = Weapon;
    const UZE_WeaponDefinition *Definition = Weapon ? Weapon->GetWeaponDefinition() : nullptr;
    if (!Definition || !Definition->bUsesAmmo || Definition->AmmoDefinition.IsNull())
        return -1;
    return FMath::Max(0, Definition->MaxReserveAmmo - Weapon->GetReserveAmmo());
}

bool AHoverAmmoStation::CanInteract_Implementation(APawn *InteractingPawn) const
{
    // Weapon-agnostic: the vendor base requires its own WeaponDefinition.
    return MissingRounds(InteractingPawn) >= 0;
}

FText AHoverAmmoStation::GetInteractText_Implementation(APawn *InteractingPawn) const
{
    AZE_WeaponBase *Weapon = nullptr;
    const int32 Missing = MissingRounds(InteractingPawn, &Weapon);
    if (Missing < 0)
        return NoGunText;
    if (Missing == 0)
        return FullText;
    const UZE_WeaponDefinition *Definition = Weapon->GetWeaponDefinition();
    return FText::Format(PromptFormat, Definition ? Definition->DisplayName : FText::GetEmpty(),
                         FText::AsNumber(Missing), FText::AsNumber(AmmoCost));
}

void AHoverAmmoStation::Interact_Implementation(APawn *InteractingPawn)
{
    AZE_WeaponBase *Weapon = nullptr;
    const int32 Missing = MissingRounds(InteractingPawn, &Weapon);
    UHoverPickupFeedback *Feedback = UHoverPickupFeedback::Get(this);
    auto *Survival = InteractingPawn ? InteractingPawn->FindComponentByClass<UZE_SurvivalComponent>() : nullptr;
    auto *Inventory = InteractingPawn ? InteractingPawn->FindComponentByClass<UZE_InventoryComponent>() : nullptr;
    const float Gold = Survival ? Survival->GetGold() : 0.f;
    if (Missing <= 0 || !Survival || !Inventory)
    {
        if (Feedback && Missing == 0)
            Feedback->Toast(FullText.ToString().ToUpper(), PickupPointsColor);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_STATION_BUY result=refused missing=%d gold=%.0f"), Missing, Gold);
        return;
    }
    if (Gold < AmmoCost)
    {
        if (Feedback)
            Feedback->Toast(NoPointsText.ToString(), PickupDeniedColor);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_STATION_BUY result=no_points missing=%d gold=%.0f cost=%d"), Missing,
               Gold, AmmoCost);
        return;
    }
    const UZE_WeaponDefinition *Definition = Weapon->GetWeaponDefinition();
    UZE_AmmoDefinition *Ammo = Definition ? Definition->AmmoDefinition.LoadSynchronous() : nullptr;
    const int32 Before = Weapon->GetReserveAmmo();
    FGuid Id;
    if (!Ammo || !Inventory->AddItemDefinition(Ammo, Missing, Id))
    {
        UE_LOG(LogTemp, Warning, TEXT("HOVER_AMMO_STATION_BUY result=add_failed ammo=%s"), *GetNameSafe(Ammo));
        return;
    }
    Survival->ApplyGoldDelta(-float(AmmoCost));
    LastPurchaseTime = GetWorld()->GetTimeSeconds();
    if (USoundBase *Sound = PurchaseSound.LoadSynchronous())
        UGameplayStatics::PlaySoundAtLocation(this, Sound, GetActorLocation());
    const int32 After = Weapon->GetReserveAmmo();
    if (Feedback)
    {
        Feedback->Toast(FString::Printf(TEXT("-%d POINTS"), AmmoCost), PickupPointsColor);
        Feedback->NotifyAmmo(FString::Printf(TEXT("+%d AMMO"), After - Before));
    }
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_AMMO_STATION_BUY result=bought rounds=%d reserve=%d->%d cost=%d gold=%.0f->%.0f"),
           Missing, Before, After, AmmoCost, Gold, Survival->GetGold());
}
