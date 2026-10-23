#include "HoverShotVisual.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"

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
}
void AHoverShotVisual::Launch(const FVector &Start, const FVector &End)
{
    Origin = Start;
    Direction = (End - Start).GetSafeNormal();
    Distance = FVector::Dist(Start, End);
    SetActorLocationAndRotation(Start, Direction.Rotation());
    Bullet->SetRelativeScale3D(FVector(.35f, .009f, .009f));
    SetLifeSpan(FMath::Min(Distance / 18000.f + .02f, 3.f));
}
void AHoverShotVisual::Tick(float DT)
{
    Super::Tick(DT);
    Travel += 18000.f * DT;
    if (Travel >= Distance)
    {
        Destroy();
        return;
    }
    SetActorLocation(Origin + Direction * Travel);
    Bullet->SetRelativeScale3D(FVector(FMath::Min(35.f, Distance - Travel) / 100.f, .009f, .009f));
}
