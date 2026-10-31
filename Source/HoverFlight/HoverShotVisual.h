#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HoverShotVisual.generated.h"

struct FHoverGunFeelTier;

UCLASS()
class AHoverShotVisual : public AActor
{
    GENERATED_BODY()
  public:
    AHoverShotVisual();
    // Legacy presentation; equal to Launch(Start, End, FHoverGunFeelTier::Legacy()).
    void Launch(const FVector &Start, const FVector &End);
    void Launch(const FVector &Start, const FVector &End, const FHoverGunFeelTier &Tier);
    virtual void Tick(float DT) override;

  private:
    UPROPERTY() TObjectPtr<class UStaticMeshComponent> Bullet;
    UPROPERTY() TObjectPtr<class UNiagaraComponent> Trail;
    FVector Origin, Direction;
    float Travel = 0, Distance = 0, Age = 0, Duration = 0;
    float Length = 55, Width = .014f;
    bool bArrived = false;
};
