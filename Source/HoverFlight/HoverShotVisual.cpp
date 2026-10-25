#include "HoverShotVisual.h"
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
    Origin = Start;
    Direction = (End - Start).GetSafeNormal();
    Distance = FVector::Dist(Start, End);
    SetActorLocationAndRotation(Start, Direction.Rotation());
    Bullet->SetRelativeScale3D(FVector(.55f, .014f, .014f));
    // A short visual travel floor lets a nearby shot render before its tail fades.
    // Hit resolution stays instantaneous and never depends on this presentation.
    Duration = FMath::Clamp(Distance / 90000.f, .06f, .09f);
    Trail->SetVariableLinearColor(TEXT("User.Color"), FLinearColor(1.f, .65f, .25f));
    Trail->SetVariableFloat(TEXT("User.Emissive"), 2.f);
    Trail->SetVariableFloat(TEXT("User.Lifetime"), .06f);
    Trail->SetVariableFloat(TEXT("User.Trail Size"), 1.4f);
    Trail->Activate(true);
    SetLifeSpan(Duration + .25f);
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
    Bullet->SetRelativeScale3D(FVector(FMath::Min(55.f, Distance - Travel) / 100.f, .014f, .014f));
}
