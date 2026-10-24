#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HoverShotVisual.generated.h"

UCLASS()
class AHoverShotVisual : public AActor
{
    GENERATED_BODY()
  public:
    AHoverShotVisual();
    void Launch(const FVector &Start, const FVector &End);
    virtual void Tick(float DT) override;

  private:
    UPROPERTY() TObjectPtr<class UStaticMeshComponent> Bullet;
    UPROPERTY() TObjectPtr<class UNiagaraComponent> Trail;
    FVector Origin, Direction;
    float Travel = 0, Distance = 0, Age = 0, Duration = 0;
    bool bArrived = false;
};
