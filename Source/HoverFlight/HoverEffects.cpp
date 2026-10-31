#include "HoverEffects.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
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

void HoverEffects::HitStop(AActor *Victim, float Dilation, float Seconds, FTimerHandle &Handle)
{
    UWorld *World = Victim ? Victim->GetWorld() : nullptr;
    if (!World || Seconds <= 0)
        return;
    Victim->CustomTimeDilation = FMath::Clamp(Dilation, .01f, 1.f);
    World->GetTimerManager().SetTimer(
        Handle, FTimerDelegate::CreateWeakLambda(Victim, [Victim]() { Victim->CustomTimeDilation = 1.f; }), Seconds,
        false);
}
