#include "HoverShotVisual.h"
#include "HoverGunFeel.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"

AHoverShotVisual::AHoverShotVisual()
{
    PrimaryActorTick.bCanEverTick = true;
    Bullet = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Bullet"));
    SetRootComponent(Bullet);
    Bullet->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Bullet->CastShadow = false;
    Bullet->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    Bullet->SetMaterial(
        0, LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/HoverPrototype/Effects/M_BulletTracer.M_BulletTracer")));
    Trail = CreateDefaultSubobject<UNiagaraComponent>(TEXT("PurchasedBulletTrail"));
    Trail->SetupAttachment(Bullet);
    Trail->SetAbsolute(false, false, true);
    Trail->SetAutoActivate(false);
    Trail->SetAsset(
        LoadObject<UNiagaraSystem>(nullptr, TEXT("/Game/ArrowTrail/FX/NS_ArrowTrail_Basic_02.NS_ArrowTrail_Basic_02")));
}
void AHoverShotVisual::Launch(const FVector &Start, const FVector &End)
{
    Launch(Start, End, FHoverGunFeelTier::Legacy());
}
void AHoverShotVisual::Launch(const FVector &Start, const FVector &End, const FHoverGunFeelTier &Tier)
{
    Origin = Start;
    Direction = (End - Start).GetSafeNormal();
    Distance = FVector::Dist(Start, End);
    SetActorLocationAndRotation(Start, Direction.Rotation());
    if (Distance < Tier.MinTracerDistance)
    {
        // A point-blank streak reads as a flash artefact; the muzzle flash already covers it.
        Bullet->SetVisibility(false, false);
        Destroy();
        return;
    }
    if (!Tier.Tracer.IsNull())
        if (auto *System = Tier.Tracer.LoadSynchronous())
            Trail->SetAsset(System);
    Length = Tier.TracerLength;
    Width = Tier.TracerWidth;
    Bullet->SetRelativeScale3D(FVector(Length / 100.f, Width, Width));
    // A short visual travel floor lets a nearby shot render before its tail fades.
    // Hit resolution stays instantaneous and never depends on this presentation.
    Duration =
        FMath::Clamp(Distance / FMath::Max(1.f, Tier.TracerSpeed), Tier.TracerMinDuration, Tier.TracerMaxDuration);
    if (Tier.bTracerColor)
        Trail->SetVariableLinearColor(TEXT("User.Color"), Tier.TracerColor);
    if (Tier.bTracerColorAB)
    {
        Trail->SetVariableLinearColor(TEXT("User.ColorA"), Tier.TracerColor);
        Trail->SetVariableLinearColor(TEXT("User.ColorB"), Tier.TracerColorB);
    }
    Trail->SetVariableFloat(TEXT("User.Emissive"), Tier.TracerEmissive);
    Trail->SetVariableFloat(TEXT("User.Lifetime"), Tier.TracerLifetime);
    Trail->SetVariableFloat(TEXT("User.Trail Size"), Tier.TracerTrailSize);
    Trail->Activate(true);
    SetLifeSpan(Duration + FMath::Max(.25f, Tier.TracerLifetime + .1f));
}
void AHoverShotVisual::Tick(float DT)
{
    Super::Tick(DT);
    if (bArrived)
        return;
    Age += DT;
    Travel = Distance * FMath::Clamp(Age / Duration, 0.f, 1.f);
    SetActorLocation(Origin + Direction * Travel);
    if (Age >= Duration)
    {
        bArrived = true;
        Bullet->SetVisibility(false, false);
        Trail->Deactivate();
        return;
    }
    Bullet->SetRelativeScale3D(FVector(FMath::Min(Length, Distance - Travel) / 100.f, Width, Width));
}
