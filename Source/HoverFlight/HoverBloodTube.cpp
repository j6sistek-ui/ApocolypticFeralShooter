#include "HoverBloodTube.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"

// AFS 2026-11-01: see HoverBloodTube.h. One clock (seconds since construction / BeginPlay) drives everything: the drop
// schedule, the headshot schedule, the light, and the ages written into the pool / glass materials each tick.

namespace
{
constexpr float DropRadiusCm = .4f; // SM_Headhunter_BloodDrop's round part (Scripts/Blender/ExportHeadhunter.py)

UStaticMeshComponent *MakeMesh(AActor *Owner, const TCHAR *Name, USceneComponent *Parent)
{
    auto *C = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
    C->SetupAttachment(Parent);
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->SetCanEverAffectNavigation(false);
    C->SetGenerateOverlapEvents(false);
    C->CastShadow = false;
    C->bReceivesDecals = false;
    return C;
}

float EaseOut(float X)
{
    X = FMath::Clamp(X, 0.f, 1.f);
    return 1.f - FMath::Square(1.f - X);
}
} // namespace

AHoverBloodTube::AHoverBloodTube()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);
    PoolMesh = MakeMesh(this, TEXT("Pool"), Root);
    PoolMesh->SetBoundsScale(1.25f); // the surface ripples / sloshes up to ~2 cm (world position offset)
    GlassBloodMesh = MakeMesh(this, TEXT("GlassBlood"), Root);
    for (int32 I = 0; I < NumDrops; ++I)
    {
        auto *D = MakeMesh(this, *FString::Printf(TEXT("Drop%d"), I), Root);
        D->SetVisibility(false);
        D->SetBoundsScale(4.f);
        Drops.Add(D);
    }
    GlowLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("GlowLight"));
    GlowLight->SetupAttachment(Root);
    GlowLight->SetMobility(EComponentMobility::Movable);
    GlowLight->SetCastShadows(false);
    GlowLight->SetIntensityUnits(ELightUnits::Candelas);
    GlowLight->SetIntensity(GlowIntensity);
    GlowLight->SetAttenuationRadius(GlowRadius);
    GlowLight->SetLightColor(GlowColor);
    GlowLight->SetSourceRadius(4.f);
    GlowLight->bAffectsWorld = true;
    FillLight = CreateDefaultSubobject<UPointLightComponent>(TEXT("FillLight"));
    FillLight->SetupAttachment(Root);
    FillLight->SetMobility(EComponentMobility::Movable);
    FillLight->SetCastShadows(false);
    FillLight->SetIntensityUnits(ELightUnits::Candelas);
    FillLight->SetSourceRadius(8.f);
    FillLight->SetSoftSourceRadius(10.f);
    auto MakeFx = [this](const TCHAR *Name) {
        auto *F = CreateDefaultSubobject<UNiagaraComponent>(Name);
        F->SetupAttachment(Root);
        F->SetAutoActivate(false);
        F->SetAutoDestroy(false);
        F->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        F->SetCanEverAffectNavigation(false);
        return F;
    };
    for (int32 I = 0; I < 3; ++I)
        SplashFx.Add(MakeFx(*FString::Printf(TEXT("SplashFx%d"), I)));
    SpurtFx = MakeFx(TEXT("SpurtFx"));
    GlassSplashFx = MakeFx(TEXT("GlassSplashFx"));
}

void AHoverBloodTube::ApplyAssets()
{
    if (PoolMeshAsset && PoolMesh->GetStaticMesh() != PoolMeshAsset)
        PoolMesh->SetStaticMesh(PoolMeshAsset);
    if (PoolMaterial)
        PoolMesh->SetMaterial(0, PoolMaterial);
    if (GlassBloodMeshAsset && GlassBloodMesh->GetStaticMesh() != GlassBloodMeshAsset)
        GlassBloodMesh->SetStaticMesh(GlassBloodMeshAsset);
    if (GlassBloodMaterial)
        GlassBloodMesh->SetMaterial(0, GlassBloodMaterial);
    for (auto &D : Drops)
    {
        if (DropMeshAsset && D->GetStaticMesh() != DropMeshAsset)
            D->SetStaticMesh(DropMeshAsset);
        if (DropMaterial)
            D->SetMaterial(0, DropMaterial);
    }
    for (auto &F : SplashFx)
        if (SplashSystem && F->GetAsset() != SplashSystem)
            F->SetAsset(SplashSystem);
    if (SpurtSystem && SpurtFx->GetAsset() != SpurtSystem)
        SpurtFx->SetAsset(SpurtSystem);
    if (GlassSplashSystem && GlassSplashFx->GetAsset() != GlassSplashSystem)
        GlassSplashFx->SetAsset(GlassSplashSystem);
    GlowLight->SetLightColor(GlowColor);
    GlowLight->SetAttenuationRadius(GlowRadius);
    GlowLight->SetRelativeLocation(FVector(TubeCentre.X, TubeCentre.Y, PoolSurfaceZ + 9.f));
    FillLight->SetRelativeLocation(FillOffset);
    FillLight->SetLightColor(FillColor);
    FillLight->SetIntensity(FillIntensity);
    FillLight->SetAttenuationRadius(FillRadius);
}

void AHoverBloodTube::Restart()
{
    Rng.Initialize(int32(GetUniqueID() * 7919 + 20261101));
    Clock = 0.f;
    NextDrop = .6f;
    NextHeadshot = FirstHeadshotDelay;
    HitTime = RippleTime[0] = RippleTime[1] = -100.f;
    BleedLeft = 0;
    for (auto &D : DropState)
        D = FDrop();
    ParkDrops();
    bStarted = true;
    PushState();
}

void AHoverBloodTube::OnConstruction(const FTransform &Transform)
{
    Super::OnConstruction(Transform);
    ApplyAssets();
    if (!bStarted)
        Restart();
    PushState();
}

void AHoverBloodTube::BeginPlay()
{
    Super::BeginPlay();
    ApplyAssets();
    Restart();
}

void AHoverBloodTube::PreSave(FObjectPreSaveContext SaveContext)
{
    // never save a mid-animation state (a drop hanging in the air); custom primitive data is transient anyway
    ParkDrops();
    Super::PreSave(SaveContext);
}

void AHoverBloodTube::ParkDrops()
{
    for (int32 I = 0; I < NumDrops; ++I)
    {
        DropState[I].State = EDrop::Idle;
        if (Drops.IsValidIndex(I) && Drops[I])
            Drops[I]->SetVisibility(false);
    }
}

int32 AHoverBloodTube::PickSource()
{
    float Total = 0.f;
    for (int32 I = 0; I < DropSources.Num(); ++I)
        Total += DropSourceWeights.IsValidIndex(I) ? DropSourceWeights[I] : 1.f;
    float R = Rng.FRand() * Total;
    for (int32 I = 0; I < DropSources.Num(); ++I)
    {
        R -= DropSourceWeights.IsValidIndex(I) ? DropSourceWeights[I] : 1.f;
        if (R <= 0.f)
            return I;
    }
    return DropSources.Num() - 1;
}

void AHoverBloodTube::TriggerDrop(int32 Source)
{
    if (DropSources.Num() == 0)
        return;
    if (!DropSources.IsValidIndex(Source))
        Source = PickSource();
    // one bead per source at a time; take a free slot
    for (auto &D : DropState)
        if (D.State == EDrop::Grow && D.Start.Equals(DropSources[Source], .01f))
            return;
    for (int32 I = 0; I < NumDrops; ++I)
    {
        FDrop &D = DropState[I];
        if (D.State != EDrop::Idle)
            continue;
        D.State = EDrop::Grow;
        D.Start = DropSources[Source];
        D.T = 0.f;
        D.Grow = BleedLeft > 0 && Source == 0 ? DropGrowSeconds * .45f : DropGrowSeconds * Rng.FRandRange(.8f, 1.25f);
        Drops[I]->SetVisibility(true);
        return;
    }
}

void AHoverBloodTube::TriggerHeadshot()
{
    HitTime = Clock;
    const float Off = Rng.FRandRange(HeadshotArcMinDeg, FMath::Max(HeadshotArcMinDeg, HeadshotArcDeg));
    HitAngle = -UE_HALF_PI + FMath::DegreesToRadians(Rng.FRand() < .5f ? -Off : Off);
    HitZ = Rng.FRandRange(HeadshotZMin, HeadshotZMax);
    HitSeed = Rng.FRand();
    const FVector Hit(TubeCentre.X + GlassRadius * FMath::Cos(HitAngle), TubeCentre.Y + GlassRadius * FMath::Sin(HitAngle),
                      HitZ);
    const FVector Inward = FVector(-FMath::Cos(HitAngle), -FMath::Sin(HitAngle), 0.f);
    if (SpurtFx && SpurtFx->GetAsset())
    {
        const FVector Dir = (Hit - SkullExit).GetSafeNormal();
        SpurtFx->SetRelativeLocationAndRotation(SkullExit, FRotationMatrix::MakeFromZ(Dir).Rotator());
        SpurtFx->Activate(true);
    }
    if (GlassSplashFx && GlassSplashFx->GetAsset())
    {
        const FVector Dir = (Inward * .75f + FVector(0, 0, -.65f)).GetSafeNormal();
        GlassSplashFx->SetRelativeLocationAndRotation(Hit + Inward * 1.2f, FRotationMatrix::MakeFromZ(Dir).Rotator());
        GlassSplashFx->Activate(true);
    }
    BleedLeft = BleedDrops;
    NextBleed = Clock + .5f;
    PushState();
}

void AHoverBloodTube::Land(FDrop &D, const FVector &Local)
{
    D.State = EDrop::Idle;
    const FVector2D XY(Local.X - TubeCentre.X, Local.Y - TubeCentre.Y);
    RippleTime[NextRipple] = Clock;
    RippleXY[NextRipple] = XY;
    NextRipple = (NextRipple + 1) % 2;
    if (SplashFx.Num())
    {
        UNiagaraComponent *F = SplashFx[NextSplash];
        NextSplash = (NextSplash + 1) % SplashFx.Num();
        if (F && F->GetAsset())
        {
            F->SetRelativeLocationAndRotation(FVector(Local.X, Local.Y, PoolSurfaceZ + .3f), FRotator::ZeroRotator);
            F->Activate(true);
        }
    }
}

void AHoverBloodTube::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bStarted)
        Restart();
    const float Dt = FMath::Clamp(DeltaSeconds, 0.f, .1f);
    Clock += Dt;

    if (Clock >= NextHeadshot)
    {
        TriggerHeadshot();
        NextHeadshot = Clock + Rng.FRandRange(HeadshotIntervalMin, FMath::Max(HeadshotIntervalMin, HeadshotIntervalMax));
    }
    if (BleedLeft > 0 && Clock >= NextBleed)
    {
        TriggerDrop(0);
        --BleedLeft;
        NextBleed = Clock + BleedGap;
    }
    if (Clock >= NextDrop)
    {
        TriggerDrop(-1);
        NextDrop = Clock + Rng.FRandRange(DropIntervalMin, FMath::Max(DropIntervalMin, DropIntervalMax));
    }

    for (int32 I = 0; I < NumDrops; ++I)
    {
        FDrop &D = DropState[I];
        UStaticMeshComponent *C = Drops[I];
        if (D.State == EDrop::Idle || !C)
            continue;
        D.T += Dt;
        if (D.State == EDrop::Grow)
        {
            // the bead swells and sags under the source, then lets go
            const float K = EaseOut(D.T / D.Grow);
            const float S = DropScale * (.25f + .75f * K);
            const float Sag = 1.f + .35f * K;
            C->SetRelativeScale3D(FVector(S, S, S * Sag));
            C->SetRelativeLocation(D.Start - FVector(0, 0, DropRadiusCm * S * Sag));
            if (D.T >= D.Grow)
            {
                D.State = EDrop::Fall;
                D.T = 0.f;
            }
            continue;
        }
        const float V = Gravity * D.T;
        const float Z = D.Start.Z - DropRadiusCm * DropScale * 1.35f - .5f * Gravity * D.T * D.T;
        const float Stretch = 1.f + FMath::Clamp(V / 260.f, 0.f, 1.4f);
        const float S = DropScale;
        C->SetRelativeScale3D(FVector(S / FMath::Sqrt(Stretch), S / FMath::Sqrt(Stretch), S * Stretch));
        const FVector Local(D.Start.X, D.Start.Y, Z);
        C->SetRelativeLocation(Local);
        if (Z <= PoolSurfaceZ + .2f)
        {
            C->SetVisibility(false);
            Land(D, Local);
        }
    }

    if (GlowLight)
    {
        const float Flick = 1.f + GlowFlicker * (.6f * FMath::Sin(Clock * 1.7f) + .4f * FMath::Sin(Clock * 4.3f + 1.f));
        const float Age = Clock - HitTime;
        const float Kick = Age >= 0.f ? HitLightBoost * FMath::Exp(-Age / FMath::Max(HitLightSeconds, .01f)) : 0.f;
        GlowLight->SetIntensity(GlowIntensity * Flick + Kick * GlowIntensity);
    }
    PushState();
}

void AHoverBloodTube::PushState()
{
    if (PoolMesh)
    {
        PoolMesh->SetCustomPrimitiveDataVector4(0, FVector4(Clock - HitTime, HitAngle, Clock - RippleTime[0], RippleXY[0].X));
        PoolMesh->SetCustomPrimitiveDataVector4(4, FVector4(RippleXY[0].Y, Clock - RippleTime[1], RippleXY[1].X,
                                                            RippleXY[1].Y));
    }
    if (GlassBloodMesh)
        GlassBloodMesh->SetCustomPrimitiveDataVector4(0, FVector4(Clock - HitTime, HitAngle, HitZ, HitSeed));
}

FString AHoverBloodTube::DescribeState() const
{
    FString Out = FString::Printf(TEXT("{\"clock\":%.3f,\"next_drop\":%.3f,\"next_headshot\":%.3f,\"hit_age\":%.3f,"
                                       "\"hit_angle_deg\":%.1f,\"hit_z\":%.1f,\"ripple_ages\":[%.3f,%.3f],\"drops\":["),
                                  Clock, NextDrop, NextHeadshot, Clock - HitTime, FMath::RadiansToDegrees(HitAngle), HitZ,
                                  Clock - RippleTime[0], Clock - RippleTime[1]);
    for (int32 I = 0; I < NumDrops; ++I)
    {
        const FDrop &D = DropState[I];
        const FVector L = Drops.IsValidIndex(I) && Drops[I] ? Drops[I]->GetRelativeLocation() : FVector::ZeroVector;
        Out += FString::Printf(TEXT("%s{\"state\":%d,\"t\":%.3f,\"local\":[%.1f,%.1f,%.1f]}"), I ? TEXT(",") : TEXT(""),
                               int32(D.State), D.T, L.X, L.Y, L.Z);
    }
    return Out + TEXT("]}");
}
