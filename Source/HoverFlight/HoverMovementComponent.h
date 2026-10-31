#pragma once
#include "CoreMinimal.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HoverMovementComponent.generated.h"

UCLASS()
class HOVERFLIGHT_API UHoverMovementComponent : public UCharacterMovementComponent
{
    GENERATED_BODY()
  public:
    virtual void CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration) override;
    // AFS 2026-10-31 (Life Engine x parkour): while the pilot's Life Engine solver moves the capsule this
    // component sits in MOVE_None, where the engine reports neither IsMovingOnGround nor IsFalling, drops every
    // Launch and never starts a jump. The parkour template (BP_Vexa_CLS_Parkour) gates its wall run on IsFalling
    // and launches its wall jump through LaunchCharacter, so with the solver on it never saw her airborne.
    // AHoverPilot::UpdateLifeEngine reports the solver state here every tick (the solver exists only in NYC
    // Survival; the default state leaves the engine behaviour untouched everywhere else).
    void SetExternalSolverState(bool bActive, bool bGrounded);
    bool IsExternalSolverDriving() const
    {
        return bExternalSolverActive && MovementMode == MOVE_None;
    }
    // Under the solver (MOVE_None only): the solver's ground flag, for the template, CLS and the pilot's gates.
    virtual bool IsMovingOnGround() const override;
    virtual bool IsFalling() const override;
    // The solver owns the plain jump; a template Jump() must not also start a character-movement jump.
    virtual bool CanAttemptJump() const override;
    // A launch (the template's wall jump or coyote jump, the pilot's dive or stomp shove) hands the capsule
    // back: falling mode first so the engine accepts it, and UpdateLifeEngine then suspends the solver.
    virtual void Launch(FVector const &LaunchVel) override;

  private:
    bool bExternalSolverActive = false;
    bool bExternalSolverGrounded = true;
};
