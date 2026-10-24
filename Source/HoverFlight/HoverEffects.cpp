#include "HoverEffects.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"

void HoverEffects::BloodBurst(UWorld *World, UNiagaraSystem *System, const FVector &Point, const FVector &Direction)
{
    if (!World || !System)
        return;
    auto *Effect = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Point, (-Direction).Rotation(),
                                                                  FVector(.65f), true, true);
    if (!Effect)
        return;
    TWeakObjectPtr<UNiagaraComponent> WeakEffect(Effect);
    FTimerHandle StopHandle, CleanupHandle;
    World->GetTimerManager().SetTimer(
        StopHandle,
        [WeakEffect]() {
            if (WeakEffect.IsValid())
                WeakEffect->Deactivate();
        },
        .15f, false);
    World->GetTimerManager().SetTimer(
        CleanupHandle,
        [WeakEffect]() {
            if (WeakEffect.IsValid())
                WeakEffect->DestroyComponent();
        },
        2.f, false);
}
