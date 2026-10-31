#include "HoverMovementComponent.h"

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
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_PARKOUR_LAUNCH handoff grounded=%d velocity=%s launch=%s"),
               bExternalSolverGrounded, *Velocity.ToString(), *LaunchVel.ToString());
        SetMovementMode(MOVE_Falling);
    }
    Super::Launch(LaunchVel);
}
