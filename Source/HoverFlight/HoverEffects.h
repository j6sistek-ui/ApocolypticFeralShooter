#pragma once
#include "CoreMinimal.h"
class UNiagaraSystem;
class UWorld;
namespace HoverEffects
{
// Impact systems from demonstration packs must not keep emitting after a hit.
void BloodBurst(UWorld *World, UNiagaraSystem *System, const FVector &Point, const FVector &Direction);
} // namespace HoverEffects
