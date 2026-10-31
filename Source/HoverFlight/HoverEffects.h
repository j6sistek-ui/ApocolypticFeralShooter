#pragma once
#include "CoreMinimal.h"
class UNiagaraSystem;
class UWorld;
class AActor;
struct FTimerHandle;
namespace HoverEffects
{
// Impact systems from demonstration packs must not keep emitting after a hit.
void BloodBurst(UWorld *World, UNiagaraSystem *System, const FVector &Point, const FVector &Direction);
// Slows only the victim (never global dilation, which would break the player's fire cadence).
// The world timer is not dilated by the actor's CustomTimeDilation, so the restore lands on time.
void HitStop(AActor *Victim, float Dilation, float Seconds, FTimerHandle &Handle);
} // namespace HoverEffects
