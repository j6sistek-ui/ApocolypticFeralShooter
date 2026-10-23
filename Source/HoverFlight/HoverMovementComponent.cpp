#include "HoverMovementComponent.h"

void UHoverMovementComponent::CalcVelocity(float DeltaTime, float Friction, bool bFluid, float BrakingDeceleration)
{
    // HoverPilot integrates thrust, coasting and braking. Keep swept flying collision
    // movement, but do not apply a second fluid-friction/braking pass to its velocity.
    if (MovementMode != MOVE_Flying)
        Super::CalcVelocity(DeltaTime, Friction, bFluid, BrakingDeceleration);
}
