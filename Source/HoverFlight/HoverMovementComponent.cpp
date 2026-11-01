#include "HoverMovementComponent.h"
#include "HAL/IConsoleManager.h"

// AFS 2026-11-01 (walking, review fix): A/B switch for the proof (Scripts/ProveWalking.py WALK_TRAJ=0 measures the
// pre-fix behaviour). 1 = report the walking / falling limits under the Life Engine solver (the fix), 0 = engine
// MOVE_None values (max speed 0).
static TAutoConsoleVariable<int32> CVarHoverSolverLimits(
    TEXT("hover.LifeEngineMoveLimits"), 1,
    TEXT("1: under the Life Engine solver the character movement reports walking/falling max speed and braking "
         "(CLS motion-matching trajectory); 0: engine MOVE_None values (0)."));

void UHoverMovementComponent::CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration)
{
    // HoverPilot integrates thrust, coasting and braking. Keep swept flying collision
    // movement, but do not apply a second fluid-friction/braking pass to its velocity.
    if (MovementMode != MOVE_Flying)
        Super::CalcVelocity(DeltaTime, Friction, bFluid, BrakingDeceleration);
}

// AFS 2026-10-31 (Life Engine x parkour): see the header. Only MOVE_None under an active solver is affected.
void UHoverMovementComponent::SetExternalSolverState(bool bActive, bool bGrounded)
{
    bExternalSolverActive = bActive;
    bExternalSolverGrounded = bGrounded;
}

bool UHoverMovementComponent::IsMovingOnGround() const
{
    return IsExternalSolverDriving() ? bExternalSolverGrounded : Super::IsMovingOnGround();
}

bool UHoverMovementComponent::IsFalling() const
{
    return IsExternalSolverDriving() ? !bExternalSolverGrounded : Super::IsFalling();
}

bool UHoverMovementComponent::CanAttemptJump() const
{
    return !IsExternalSolverDriving() && Super::CanAttemptJump();
}

void UHoverMovementComponent::Launch(FVector const &LaunchVel)
{
    if (IsExternalSolverDriving())
    {
        UE_LOG(LogTemp, Display, TEXT("HOVER_PARKOUR_LAUNCH handoff grounded=%d velocity=%s launch=%s"),
               bExternalSolverGrounded, *Velocity.ToString(), *LaunchVel.ToString());
        SetMovementMode(MOVE_Falling);
    }
    Super::Launch(LaunchVel);
}

// AFS 2026-11-01 (walking, review fix): see the header. Only MOVE_None under an active solver is affected.
float UHoverMovementComponent::GetMaxSpeed() const
{
    if (!IsExternalSolverDriving() || !CVarHoverSolverLimits.GetValueOnAnyThread())
        return Super::GetMaxSpeed();
    return bExternalSolverGrounded && IsCrouching() ? MaxWalkSpeedCrouched : MaxWalkSpeed;
}

float UHoverMovementComponent::GetMinAnalogSpeed() const
{
    return IsExternalSolverDriving() && CVarHoverSolverLimits.GetValueOnAnyThread() ? MinAnalogWalkSpeed
                                                                                    : Super::GetMinAnalogSpeed();
}

float UHoverMovementComponent::GetMaxBrakingDeceleration() const
{
    if (!IsExternalSolverDriving() || !CVarHoverSolverLimits.GetValueOnAnyThread())
        return Super::GetMaxBrakingDeceleration();
    return bExternalSolverGrounded ? BrakingDecelerationWalking : BrakingDecelerationFalling;
}
