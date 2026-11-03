#include "HoverWeather.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Components/DecalComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Components/MeshComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetMaterialLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialParameterCollection.h"
#include "ParticleEmitterInstances.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "Sound/SoundBase.h"

namespace
{
const TCHAR *Pack = TEXT("/Game/MultiplayerDynamicWeatherSystem");

UParticleSystemComponent *MakePrecipitation(AActor *Owner, const TCHAR *Name, USceneComponent *Root)
{
    auto *FX = Owner->CreateDefaultSubobject<UParticleSystemComponent>(Name);
    FX->SetupAttachment(Root);
    FX->SetUsingAbsoluteLocation(true);
    FX->SetUsingAbsoluteRotation(true);
    FX->bAutoActivate = false;
    FX->SetCastShadow(false);
    return FX;
}

int32 LiveParticles(const UParticleSystemComponent *FX)
{
    int32 Count = 0;
    if (FX)
        for (const FParticleEmitterInstance *Emitter : FX->EmitterInstances)
            if (Emitter)
                Count += Emitter->ActiveParticles;
    return Count;
}
} // namespace

AHoverWeather::AHoverWeather()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostUpdateWork; // after the camera, so precipitation sits on this frame's view
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    RootComponent = Root;
    RainNear = MakePrecipitation(this, TEXT("RainNear"), Root);
    RainFar = MakePrecipitation(this, TEXT("RainFar"), Root);
    Snow = MakePrecipitation(this, TEXT("Snow"), Root);
    SnowFar = MakePrecipitation(this, TEXT("SnowFar"), Root);
    Surface = CreateDefaultSubobject<UDecalComponent>(TEXT("SurfaceDecal"));
    Surface->SetupAttachment(Root);
    Surface->SetUsingAbsoluteLocation(true);
    Surface->SetUsingAbsoluteRotation(true);
    Surface->SetWorldRotation(FRotator(-90, 0, 0)); // the decal projects along its X axis: straight down
    Surface->SortOrder = -10;                       // blood and impact decals draw over the weather layer
    Surface->SetVisibility(false);

    RainTemplate = TSoftObjectPtr<UParticleSystem>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Weather/P_Rain_AFS.P_Rain_AFS")));
    RainFarTemplate = TSoftObjectPtr<UParticleSystem>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Weather/P_Rain_AFS_Far.P_Rain_AFS_Far")));
    SnowTemplate = TSoftObjectPtr<UParticleSystem>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Weather/P_Snow_AFS.P_Snow_AFS")));
    SnowFarTemplate = TSoftObjectPtr<UParticleSystem>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Weather/P_Snow_AFS_Far.P_Snow_AFS_Far")));
    SplashTemplate = TSoftObjectPtr<UParticleSystem>(
        FSoftObjectPath(FString(Pack) + TEXT("/Particles/Rain/P_Rain_Ground.P_Rain_Ground")));
    ThunderClass = TSoftClassPtr<AActor>(FSoftObjectPath(FString(Pack) + TEXT("/Blueprints/BP_Thunder.BP_Thunder_C")));
    RainSound = TSoftObjectPtr<USoundBase>(FSoftObjectPath(FString(Pack) + TEXT("/Audio/Rain_Cue.Rain_Cue")));
    WindSound = TSoftObjectPtr<USoundBase>(
        FSoftObjectPath(FString(Pack) + TEXT("/Audio/Starter_Wind05_Cue.Starter_Wind05_Cue")));
    WeatherParameters = TSoftObjectPtr<UMaterialParameterCollection>(
        FSoftObjectPath(FString(Pack) + TEXT("/ParameterCollection/MPC_DynamicWeatherSystem.MPC_DynamicWeatherSystem")));
    SurfaceMaterial = TSoftObjectPtr<UMaterialInterface>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Weather/M_WeatherSurface.M_WeatherSurface")));

    // Multipliers on the level's own Clear lighting. Cloudy and Rain follow the pack's DT_Weather rows relative to
    // its Sunny row (Cloudy: sun 1.75/2.75, sky light 1.1/1.25, fog x2; Rainy: sun 0.1/2.75, sky 0.5/1.25, fog x5,
    // ground wetness 0.6, thunder every ~10 s), lifted where the pack's night-dark rain made the streets unplayable.
    // Snow is the pack's Winter season (its snow emitter) under an overcast Cloudy-like sky.
    Looks.Add(EHoverWeatherKind::Clear, FHoverWeatherLook());
    FHoverWeatherLook Cloudy;
    Cloudy.Sun = .64f;
    Cloudy.SkyLight = .88f;
    Cloudy.FogDensity = 2.f;
    Cloudy.FogColorBlend = .5f;
    Cloudy.Rayleigh = .5f;
    Cloudy.Mie = 3.f;
    Cloudy.MieHalo = .6f;
    Cloudy.SunShafts = .5f;
    Cloudy.Wind = 1.5f;
    Looks.Add(EHoverWeatherKind::Cloudy, Cloudy);
    FHoverWeatherLook Rain;
    Rain.Sun = .22f;
    Rain.SkyLight = .6f;
    Rain.FogDensity = 4.f;
    Rain.FogColorBlend = .85f;
    Rain.Rayleigh = .25f;
    Rain.Mie = 4.f;
    Rain.MieHalo = .3f;
    Rain.SunShafts = .1f;
    Rain.Wetness = 1.f;
    Rain.Wind = 3.f;
    Rain.RainVolume = 1.f;
    Rain.WindVolume = .35f;
    Rain.bRain = true;
    Looks.Add(EHoverWeatherKind::Rain, Rain);
    FHoverWeatherLook Storm = Rain;
    Storm.Sun = .14f;
    Storm.SkyLight = .5f;
    Storm.FogDensity = 5.f;
    Storm.FogColor = FLinearColor(.4f, .43f, .5f);
    Storm.MieHalo = .25f;
    Storm.SunShafts = .05f;
    Storm.WindVolume = .6f;
    Storm.bThunder = true;
    Looks.Add(EHoverWeatherKind::Storm, Storm);
    FHoverWeatherLook SnowLook;
    SnowLook.Sun = .55f;
    SnowLook.SkyLight = 1.f;
    SnowLook.FogDensity = 3.5f;
    SnowLook.FogColorBlend = .9f;
    SnowLook.FogColor = FLinearColor(.78f, .82f, .88f);
    SnowLook.Rayleigh = .4f;
    SnowLook.Mie = 4.f;
    SnowLook.MieHalo = .35f;
    SnowLook.SunShafts = .25f;
    SnowLook.SnowCover = 1.f;
    SnowLook.Wind = 2.f;
    SnowLook.WindVolume = .7f;
    SnowLook.bSnow = true;
    Looks.Add(EHoverWeatherKind::Snow, SnowLook);
}

const TCHAR *AHoverWeather::WeatherName(EHoverWeatherKind Weather)
{
    switch (Weather)
    {
    case EHoverWeatherKind::Cloudy:
        return TEXT("Cloudy");
    case EHoverWeatherKind::Rain:
        return TEXT("Rain");
    case EHoverWeatherKind::Storm:
        return TEXT("Storm");
    case EHoverWeatherKind::Snow:
        return TEXT("Snow");
    default:
        return TEXT("Clear");
    }
}

bool AHoverWeather::ParseWeather(const FString &Text, EHoverWeatherKind &OutWeather)
{
    const FString Key = Text.TrimStartAndEnd();
    for (int32 I = 0; I < int32(EHoverWeatherKind::Count); ++I)
        if (Key.Equals(WeatherName(EHoverWeatherKind(I)), ESearchCase::IgnoreCase) || Key == FString::FromInt(I))
        {
            OutWeather = EHoverWeatherKind(I);
            return true;
        }
    // The pack's own row names.
    if (Key.Equals(TEXT("Sunny"), ESearchCase::IgnoreCase) || Key.Equals(TEXT("Rainy"), ESearchCase::IgnoreCase))
    {
        OutWeather = Key.Equals(TEXT("Sunny"), ESearchCase::IgnoreCase) ? EHoverWeatherKind::Clear : EHoverWeatherKind::Rain;
        return true;
    }
    return false;
}

AHoverWeather *AHoverWeather::FindWeather(const UObject *WorldContext)
{
    if (UWorld *World = GEngine ? GEngine->GetWorldFromContextObject(WorldContext, EGetWorldErrorMode::ReturnNull) : nullptr)
        for (TActorIterator<AHoverWeather> It(World); It; ++It)
            return *It;
    return nullptr;
}

void AHoverWeather::BeginPlay()
{
    Super::BeginPlay();
    Splash = SplashTemplate.LoadSynchronous();
    MPC = WeatherParameters.LoadSynchronous();
    UParticleSystem *PackRain = LoadObject<UParticleSystem>(nullptr, *(FString(Pack) + TEXT("/Particles/Rain/P_Rain.P_Rain")));
    UParticleSystem *NearFX = RainTemplate.LoadSynchronous();
    UParticleSystem *FarFX = RainFarTemplate.LoadSynchronous();
    for (auto [FX, Template] : {TPair<UParticleSystemComponent *, UParticleSystem *>(RainNear, NearFX ? NearFX : PackRain),
                                TPair<UParticleSystemComponent *, UParticleSystem *>(RainFar, FarFX ? FarFX : PackRain)})
        if (Template)
        {
            FX->SetTemplate(Template);
            FX->DeactivateSystem();
        }
    UParticleSystem *PackSnow = LoadObject<UParticleSystem>(nullptr, *(FString(Pack) + TEXT("/Particles/Snow/P_Snow.P_Snow")));
    UParticleSystem *SnowNearFX = SnowTemplate.LoadSynchronous();
    UParticleSystem *SnowFarFX = SnowFarTemplate.LoadSynchronous();
    // Without the AFS copies the pack's single P_Snow runs near and the far volume stays empty.
    for (auto [FX, Template] : {TPair<UParticleSystemComponent *, UParticleSystem *>(Snow, SnowNearFX ? SnowNearFX : PackSnow),
                                TPair<UParticleSystemComponent *, UParticleSystem *>(SnowFar, SnowFarFX)})
        if (Template)
        {
            FX->SetTemplate(Template);
            FX->DeactivateSystem();
        }
    // The pack's pawns spawn a P_Rain_Ground splash where each drop's collision event lands; only the near volume
    // does that here, under a per-second budget.
    RainNear->OnParticleCollide.AddDynamic(this, &AHoverWeather::HandleRainCollide);
    if (UMaterialInterface *Material = SurfaceMaterial.LoadSynchronous())
    {
        Surface->SetDecalMaterial(Material);
        Surface->DecalSize = SurfaceDecalSize;
        SurfaceMID = Surface->CreateDynamicMaterialInstance();
        // Radial fade (fix round 1): the layer thins out with horizontal distance from the camera and is gone
        // before the box ends, so no square edge slides with the view.
        SurfaceMID->SetScalarParameterValue(TEXT("FadeStart"), SurfaceFadeStart);
        SurfaceMID->SetScalarParameterValue(
            TEXT("FadeEnd"), FMath::Min(SurfaceFadeEnd, FMath::Min(SurfaceDecalSize.Y, SurfaceDecalSize.Z) - 100.f));
    }
    Current = To = From = Looks.FindRef(EHoverWeatherKind::Clear);
    if (StartWeather != EHoverWeatherKind::Clear)
        SetWeather(StartWeather, 0);
}

void AHoverWeather::EndPlay(const EEndPlayReason::Type Reason)
{
    UpdateCharacterMask(false);
    RestoreParticleCap();
    for (UAudioComponent *Audio : {RainAudio.Get(), WindAudio.Get()})
        if (IsValid(Audio))
            Audio->Stop();
    Super::EndPlay(Reason);
}

void AHoverWeather::CaptureLevelLighting()
{
    if (bCaptured)
        return;
    bCaptured = true;
    UWorld *World = GetWorld();
    // The sun: the explicit actor, else the atmosphere sun, else the brightest. Every other directional light is
    // scaled by the same factor so a fill light does not stay at full strength under a storm.
    UDirectionalLightComponent *Main = SunLight ? SunLight->FindComponentByClass<UDirectionalLightComponent>() : nullptr;
    TArray<UDirectionalLightComponent *> All;
    for (TActorIterator<AActor> It(World); It; ++It)
        for (UActorComponent *Component : It->GetComponents())
            if (auto *Light = Cast<UDirectionalLightComponent>(Component); Light && Light->IsVisible())
                All.Add(Light);
    if (!Main)
        for (auto *Light : All)
            if (Light->IsUsedAsAtmosphereSunLight() && (!Main || Light->Intensity > Main->Intensity))
                Main = Light;
    if (!Main)
        for (auto *Light : All)
            if (!Main || Light->Intensity > Main->Intensity)
                Main = Light;
    if (Main)
    {
        All.Remove(Main);
        All.Insert(Main, 0);
    }
    for (auto *Light : All)
    {
        Suns.Add(Light);
        BaseSun.Add(Light->Intensity);
        BaseShaftBloom.Add(Light->BloomScale);
        BaseSunScattering.Add(Light->VolumetricScatteringIntensity);
        BaseShaftOcclusion.Add(Light->OcclusionMaskDarkness);
    }
    auto FindFirst = [World](AActor *Explicit, UClass *ComponentClass) -> UActorComponent * {
        if (Explicit)
            if (UActorComponent *Found = Explicit->FindComponentByClass(ComponentClass))
                return Found;
        for (TActorIterator<AActor> It(World); It; ++It)
            if (UActorComponent *Found = It->FindComponentByClass(ComponentClass))
                return Found;
        return nullptr;
    };
    Sky = Cast<USkyLightComponent>(FindFirst(SkyLight, USkyLightComponent::StaticClass()));
    Fog = Cast<UExponentialHeightFogComponent>(FindFirst(HeightFog, UExponentialHeightFogComponent::StaticClass()));
    Air = Cast<USkyAtmosphereComponent>(FindFirst(Atmosphere, USkyAtmosphereComponent::StaticClass()));
    if (Sky)
        BaseSky = Sky->Intensity;
    if (Fog)
    {
        BaseFog = Fog->FogDensity;
        BaseFogColor = Fog->FogInscatteringLuminance;
    }
    if (Air)
    {
        BaseRayleigh = Air->RayleighScatteringScale;
        BaseMie = Air->MieScatteringScale;
        BaseMieAnisotropy = Air->MieAnisotropy;
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_WEATHER captured sun %s (%d directional, %.2f) sky %s %.2f fog %s %.4f air %s"),
           Main ? *Main->GetOwner()->GetActorNameOrLabel() : TEXT("none"), Suns.Num(), BaseSun.Num() ? BaseSun[0] : 0.f,
           Sky ? *Sky->GetOwner()->GetActorNameOrLabel() : TEXT("none"), BaseSky,
           Fog ? *Fog->GetOwner()->GetActorNameOrLabel() : TEXT("none"), BaseFog,
           Air ? *Air->GetOwner()->GetActorNameOrLabel() : TEXT("none"));
}

void AHoverWeather::SetWeather(EHoverWeatherKind NewWeather, float BlendSeconds)
{
    if (NewWeather >= EHoverWeatherKind::Count)
        return;
    CaptureLevelLighting();
    From = Current;
    To = Looks.FindRef(NewWeather);
    TargetWeather = NewWeather;
    BlendDuration = BlendSeconds < 0 ? TransitionSeconds : BlendSeconds;
    BlendTime = 0;
    bApplying = true;
    RecaptureTimer = 0;
    if (To.bThunder)
        NextThunder = FMath::FRandRange(1.5f, 3.f);
    UpdatePrecipitation(To);
    UE_LOG(LogTemp, Display, TEXT("HOVER_WEATHER set %s blend %.1fs"), WeatherName(NewWeather), BlendDuration);
    if (BlendDuration <= 0)
        Advance(0);
}

FHoverWeatherLook AHoverWeather::BlendLooks(const FHoverWeatherLook &A, const FHoverWeatherLook &B, float Alpha)
{
    FHoverWeatherLook Out = B;
    Out.Sun = FMath::Lerp(A.Sun, B.Sun, Alpha);
    Out.SkyLight = FMath::Lerp(A.SkyLight, B.SkyLight, Alpha);
    Out.FogDensity = FMath::Lerp(A.FogDensity, B.FogDensity, Alpha);
    // Colour and its weight blend as a pre-multiplied pair so Clear (weight 0) never inherits a stale colour.
    const FLinearColor ColA = A.FogColor * A.FogColorBlend, ColB = B.FogColor * B.FogColorBlend;
    Out.FogColorBlend = FMath::Lerp(A.FogColorBlend, B.FogColorBlend, Alpha);
    Out.FogColor = Out.FogColorBlend > KINDA_SMALL_NUMBER ? FMath::Lerp(ColA, ColB, Alpha) / Out.FogColorBlend : B.FogColor;
    Out.Rayleigh = FMath::Lerp(A.Rayleigh, B.Rayleigh, Alpha);
    Out.Mie = FMath::Lerp(A.Mie, B.Mie, Alpha);
    Out.MieHalo = FMath::Lerp(A.MieHalo, B.MieHalo, Alpha);
    Out.SunShafts = FMath::Lerp(A.SunShafts, B.SunShafts, Alpha);
    Out.Wetness = FMath::Lerp(A.Wetness, B.Wetness, Alpha);
    Out.SnowCover = FMath::Lerp(A.SnowCover, B.SnowCover, Alpha);
    Out.Wind = FMath::Lerp(A.Wind, B.Wind, Alpha);
    Out.RainVolume = FMath::Lerp(A.RainVolume, B.RainVolume, Alpha);
    Out.WindVolume = FMath::Lerp(A.WindVolume, B.WindVolume, Alpha);
    return Out;
}

void AHoverWeather::ApplyLook(const FHoverWeatherLook &Look, float FlashBoost)
{
    // Multiplier 1 / weight 0 reproduce the captured values exactly, so a finished Clear is the original map.
    const float Lightning = 1.f + 5.f * FlashBoost;
    for (int32 I = 0; I < Suns.Num(); ++I)
        if (Suns[I])
        {
            Suns[I]->SetIntensity(BaseSun[I] * Look.Sun * (I == 0 ? Lightning : 1.f));
            Suns[I]->SetBloomScale(BaseShaftBloom[I] * Look.SunShafts);
            Suns[I]->SetVolumetricScatteringIntensity(BaseSunScattering[I] * Look.SunShafts);
            Suns[I]->SetOcclusionMaskDarkness(FMath::Lerp(1.f, BaseShaftOcclusion[I], Look.SunShafts));
        }
    if (Sky)
        Sky->SetIntensity(BaseSky * Look.SkyLight * (1.f + 2.f * FlashBoost));
    if (Fog)
    {
        Fog->SetFogDensity(BaseFog * Look.FogDensity);
        Fog->SetFogInscatteringColor(FMath::Lerp(BaseFogColor, Look.FogColor, Look.FogColorBlend));
    }
    if (Air)
    {
        Air->SetRayleighScatteringScale(BaseRayleigh * Look.Rayleigh);
        Air->SetMieScatteringScale(BaseMie * Look.Mie);
        Air->SetMieAnisotropy(BaseMieAnisotropy * Look.MieHalo);
    }
    // The pack's own materials read these (MF_WeatherWind, wet landscape); NYC's do not, but the values stay true.
    if (MPC)
    {
        UKismetMaterialLibrary::SetScalarParameterValue(this, MPC, TEXT("Rain phase"), Look.Wetness);
        UKismetMaterialLibrary::SetScalarParameterValue(this, MPC, TEXT("Ground Wetness"), Look.Wetness * .6f);
        UKismetMaterialLibrary::SetScalarParameterValue(this, MPC, TEXT("Wind Intensity"), Look.Wind);
        UKismetMaterialLibrary::SetScalarParameterValue(this, MPC, TEXT("Season"), Look.SnowCover * 3.f);
    }
    const bool bSurface = SurfaceMID && (Look.Wetness > .001f || Look.SnowCover > .001f);
    Surface->SetVisibility(bSurface);
    if (SurfaceMID)
    {
        SurfaceMID->SetScalarParameterValue(TEXT("Wetness"), Look.Wetness);
        SurfaceMID->SetScalarParameterValue(TEXT("SnowCover"), Look.SnowCover);
    }
    auto Loop = [this](TObjectPtr<UAudioComponent> &Audio, const TSoftObjectPtr<USoundBase> &Sound, float Volume) {
        if (Volume <= .001f)
        {
            if (IsValid(Audio) && Audio->IsPlaying())
                Audio->Stop();
            return;
        }
        if (!IsValid(Audio))
            if (USoundBase *Loaded = Sound.LoadSynchronous())
                Audio = UGameplayStatics::CreateSound2D(this, Loaded, 1.f, 1.f, 0.f, nullptr, false, false);
        if (!IsValid(Audio))
            return;
        Audio->SetVolumeMultiplier(Volume);
        if (!Audio->IsPlaying())
            Audio->Play();
    };
    Loop(RainAudio, RainSound, Look.RainVolume);
    Loop(WindAudio, WindSound, Look.WindVolume);
}

void AHoverWeather::RaiseParticleCap()
{
    // Cascade caps every CPU emitter at fx.MaxCPUParticlesPerEmitter (1000 by default): the first proof's snow sat at
    // exactly 1000 flakes and the denser rain could never pass it. Raised (never lowered) only while rain or snow
    // runs; RestoreParticleCap puts the old value back (review finding C: it used to stay raised for the session).
    IConsoleVariable *Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("fx.MaxCPUParticlesPerEmitter"));
    if (!Cap || SavedParticleCap >= 0 || Cap->GetInt() >= MaxParticlesPerEmitter)
        return;
    SavedParticleCap = Cap->GetInt();
    Cap->Set(MaxParticlesPerEmitter, ECVF_SetByCode);
    UE_LOG(LogTemp, Display, TEXT("HOVER_WEATHER particle cap %d -> %d"), SavedParticleCap, Cap->GetInt());
}

void AHoverWeather::RestoreParticleCap()
{
    if (SavedParticleCap < 0)
        return;
    if (IConsoleVariable *Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("fx.MaxCPUParticlesPerEmitter")))
    {
        Cap->Set(SavedParticleCap, ECVF_SetByCode);
        UE_LOG(LogTemp, Display, TEXT("HOVER_WEATHER particle cap restored %d"), Cap->GetInt());
    }
    SavedParticleCap = -1;
}

void AHoverWeather::UpdatePrecipitation(const FHoverWeatherLook &Look)
{
    if (Look.bRain || Look.bSnow)
        RaiseParticleCap();
    // Starting precipitation begins with the blend; stopping lets the drops already in the air finish falling.
    auto Switch = [](UParticleSystemComponent *FX, bool bOn, const TCHAR *Emitter) {
        if (!FX || !FX->Template)
            return;
        if (bOn && !FX->IsActive())
        {
            FX->ActivateSystem(true);
            FX->SetEmitterEnable(Emitter, true);
        }
        else if (!bOn && FX->IsActive())
            FX->DeactivateSystem();
    };
    FollowView();
    Switch(RainNear, Look.bRain, TEXT("Rain"));
    Switch(RainFar, Look.bRain, TEXT("Rain"));
    Switch(Snow, Look.bSnow, TEXT("Snow"));
    Switch(SnowFar, Look.bSnow, TEXT("Snow"));
}

void AHoverWeather::TrackView(float DeltaSeconds)
{
    const APlayerController *PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !PC->PlayerCameraManager || DeltaSeconds <= 0)
        return;
    // The VIEW TARGET's velocity (Vexa running, gliding, a vehicle), not the camera's: a third-person camera
    // swinging around her at 90 deg/s moves ~4.5 m/s sideways, and leading by that pushed the near snow box out of
    // the view during a turn (fix round 1 moving-camera proof: flakes in view -45 % while turning on the spot).
    // A camera actor (street / test views) is still and gets no lead; above 40 m/s (a teleport) the lead resets.
    const AActor *Target = PC->PlayerCameraManager->GetViewTarget();
    FVector Velocity = Target ? Target->GetVelocity() : FVector::ZeroVector;
    Velocity.Z = 0;
    if (Velocity.SizeSquared() > FMath::Square(4000.f))
        ViewVelocity = FVector::ZeroVector;
    else
        ViewVelocity = FMath::Lerp(ViewVelocity, Velocity, FMath::Clamp(DeltaSeconds * 4.f, 0.f, 1.f));
}

void AHoverWeather::FollowView()
{
    const APlayerController *PC = GetWorld()->GetFirstPlayerController();
    if (!PC || !PC->PlayerCameraManager)
        return;
    const FVector Eye = PC->PlayerCameraManager->GetCameraLocation();
    FVector Ahead = PC->PlayerCameraManager->GetCameraRotation().Vector();
    Ahead.Z = 0;
    Ahead = Ahead.GetSafeNormal();
    // World-space drops and flakes stay where they spawned; the volumes move ahead of a moving camera so the air it
    // runs into is already full (fix round 1, finding B).
    const FVector RainLead = (ViewVelocity * RainLeadSeconds).GetClampedToMaxSize(MaxLead);
    const FVector SnowLead = (ViewVelocity * SnowLeadSeconds).GetClampedToMaxSize(MaxLead);
    RainNear->SetWorldLocation(Eye + Ahead * RainNearAhead + RainLead);
    RainFar->SetWorldLocation(Eye + Ahead * RainFarAhead + RainLead);
    Snow->SetWorldLocation(Eye + Ahead * SnowAhead + SnowLead);
    SnowFar->SetWorldLocation(Eye + Ahead * SnowFarAhead + SnowLead);
    Surface->SetWorldLocation(Eye);
}

void AHoverWeather::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    Advance(DeltaSeconds);
}

void AHoverWeather::Advance(float DeltaSeconds)
{
    if (!bCaptured)
        return; // nothing has changed the weather yet: the level is exactly as authored
    TrackView(DeltaSeconds);
    FollowView();
    SplashBudget = FMath::Min(SplashBudget + DeltaSeconds * MaxSplashesPerSecond, MaxSplashesPerSecond * .25f);
    if (Current.bThunder || To.bThunder)
        if ((NextThunder -= DeltaSeconds) <= 0 && To.bThunder)
        {
            SpawnThunder();
            NextThunder = FMath::FRandRange(ThunderInterval.X, ThunderInterval.Y);
        }
    const bool bFlashing = Flash > 0;
    Flash = FMath::Max(0.f, Flash - DeltaSeconds / .35f);
    if (bApplying)
    {
        BlendTime += DeltaSeconds;
        const float Alpha = GetBlendAlpha();
        Current = BlendLooks(From, To, FMath::SmoothStep(0.f, 1.f, Alpha));
        ApplyLook(Current, Flash);
        if (Alpha >= 1)
        {
            Current = To;
            ApplyLook(Current, Flash);
            bApplying = false;
            RecaptureTimer = 0;
            // Flakes live 10-15 s: once the blend is over, what is still in the air goes too (round 2: snow kept
            // falling through Cloudy and Clear).
            for (auto [FX, bOn] : {TPair<UParticleSystemComponent *, bool>(RainNear, To.bRain),
                                   TPair<UParticleSystemComponent *, bool>(RainFar, To.bRain),
                                   TPair<UParticleSystemComponent *, bool>(Snow, To.bSnow),
                                   TPair<UParticleSystemComponent *, bool>(SnowFar, To.bSnow)})
                if (!bOn && FX)
                    FX->KillParticlesForced();
            if (!To.bRain && !To.bSnow)
                RestoreParticleCap();
        }
    }
    else if (bFlashing)
        ApplyLook(Current, Flash);
    // A captured-scene sky light keeps the old sky until recaptured: once a second during a blend and at its end.
    if (Sky && !Sky->bRealTimeCapture && RecaptureTimer >= 0 && (RecaptureTimer -= DeltaSeconds) <= 0)
    {
        Sky->RecaptureSky();
        RecaptureTimer = bApplying ? 1.f : -1.f;
    }
    if ((DecalSweep -= DeltaSeconds) <= 0)
    {
        DecalSweep = .5f;
        UpdateCharacterMask(Surface->IsVisible());
    }
}

void AHoverWeather::UpdateCharacterMask(bool bSurfaceActive)
{
    // The surface decal is world-aligned; on moving characters (and what they hold) it would swim. Fix round 1
    // (finding D): they used to opt out of ALL decals while it showed, so blood / impact decals could not land on
    // Vexa or the zombies in rain or snow. Now their meshes draw into custom depth instead, and M_WeatherSurface
    // drops every pixel whose custom depth equals the scene depth (the visible surface is a character); other decals
    // are untouched. A character hidden behind a wall does not mask the wall (its custom depth is farther).
    if (!bSurfaceActive)
    {
        for (const auto &Weak : CustomDepthAdded)
            if (UPrimitiveComponent *Primitive = Weak.Get())
                Primitive->SetRenderCustomDepth(false);
        CustomDepthAdded.Reset();
        return;
    }
    for (TActorIterator<ACharacter> It(GetWorld()); It; ++It)
    {
        TArray<AActor *> Attached;
        It->GetAttachedActors(Attached, true, true);
        Attached.Add(*It);
        for (AActor *Actor : Attached)
            for (UActorComponent *Component : Actor->GetComponents())
                if (auto *Mesh = Cast<UMeshComponent>(Component); Mesh && Mesh->bReceivesDecals && !Mesh->bRenderCustomDepth)
                {
                    Mesh->SetRenderCustomDepth(true);
                    CustomDepthAdded.Add(Mesh);
                }
    }
}

void AHoverWeather::HandleRainCollide(FName EventName, float EmitterTime, int32 ParticleTime, FVector Location,
                                      FVector Velocity, FVector Direction, FVector Normal, FName BoneName,
                                      UPhysicalMaterial *PhysMat)
{
    if (!Splash || SplashBudget < 1)
        return;
    const APlayerController *PC = GetWorld()->GetFirstPlayerController();
    if (PC && PC->PlayerCameraManager &&
        FVector::DistSquared(PC->PlayerCameraManager->GetCameraLocation(), Location) > FMath::Square(SplashRange))
        return;
    SplashBudget -= 1;
    ++SplashCount;
    UGameplayStatics::SpawnEmitterAtLocation(this, Splash, Location, FRotator::ZeroRotator, FVector(1),
                                             true, EPSCPoolMethod::AutoRelease);
}

void AHoverWeather::SpawnThunder()
{
    UClass *Class = ThunderClass.LoadSynchronous();
    const APlayerController *PC = GetWorld()->GetFirstPlayerController();
    if (!Class || !PC || !PC->PlayerCameraManager)
        return;
    // Like the pack's manager: a random point far from the player, traced down to the ground; BP_Thunder draws the
    // bolt, flashes its light and plays ThunderHit / Thunder. The sky flash here makes it read in the streets.
    const FVector Eye = PC->PlayerCameraManager->GetCameraLocation();
    const FVector Dir = FRotator(0, FMath::FRandRange(0.f, 360.f), 0).Vector();
    FVector Strike = Eye + Dir * FMath::FRandRange(6000.f, 16000.f);
    FHitResult Hit;
    if (GetWorld()->LineTraceSingleByChannel(Hit, Strike + FVector(0, 0, 30000), Strike - FVector(0, 0, 30000),
                                             ECC_Visibility))
        Strike = Hit.ImpactPoint;
    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    GetWorld()->SpawnActor<AActor>(Class, FTransform(Strike), Params);
    Flash = 1;
    UE_LOG(LogTemp, Display, TEXT("HOVER_WEATHER thunder at %s"), *Strike.ToCompactString());
}

int32 AHoverWeather::CountParticlesInView(float Range, float HalfAngleDeg) const
{
    const APlayerController *PC = GetWorld() ? GetWorld()->GetFirstPlayerController() : nullptr;
    if (!PC || !PC->PlayerCameraManager)
        return 0;
    const FVector Eye = PC->PlayerCameraManager->GetCameraLocation();
    const FVector Axis = PC->PlayerCameraManager->GetCameraRotation().Vector();
    const double CosHalf = FMath::Cos(FMath::DegreesToRadians(HalfAngleDeg)), RangeSq = double(Range) * Range;
    int32 Count = 0;
    for (UParticleSystemComponent *FX : {RainNear.Get(), RainFar.Get(), Snow.Get(), SnowFar.Get()})
        if (FX)
            for (FParticleEmitterInstance *Emitter : FX->EmitterInstances)
                if (Emitter && !Emitter->UseLocalSpace())
                    for (int32 I = 0; I < Emitter->ActiveParticles; ++I)
                        if (const FBaseParticle *Particle = Emitter->GetParticle(I))
                        {
                            const FVector Offset = Particle->Location - Eye;
                            const double DistSq = Offset.SizeSquared();
                            if (DistSq <= RangeSq && DistSq > 1 && FVector::DotProduct(Offset, Axis) >= CosHalf * FMath::Sqrt(DistSq))
                                ++Count;
                        }
    return Count;
}

int32 AHoverWeather::GetLiveParticleCount() const
{
    return LiveParticles(RainNear) + LiveParticles(RainFar) + LiveParticles(Snow) + LiveParticles(SnowFar);
}

FString AHoverWeather::DescribeState() const
{
    const IConsoleVariable *Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("fx.MaxCPUParticlesPerEmitter"));
    return FString::Printf(TEXT("weather=%s blend=%.2f sun=%.2f sky=%.2f fog=%.2f wet=%.2f snow=%.2f rainVol=%.2f "
                                "windVol=%.2f particles rain=%d+%d snow=%d+%d decal=%d suns=%d splashes=%d masked=%d cap=%d "
                                "lead=%.0f"),
                           WeatherName(TargetWeather), GetBlendAlpha(), Current.Sun, Current.SkyLight, Current.FogDensity,
                           Current.Wetness, Current.SnowCover, Current.RainVolume, Current.WindVolume,
                           LiveParticles(RainNear), LiveParticles(RainFar), LiveParticles(Snow), LiveParticles(SnowFar),
                           Surface && Surface->IsVisible() ? 1 : 0, Suns.Num(), SplashCount, CustomDepthAdded.Num(),
                           Cap ? Cap->GetInt() : -1, ViewVelocity.Size());
}
