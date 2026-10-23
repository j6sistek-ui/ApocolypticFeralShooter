#pragma once
#include "CoreMinimal.h"

namespace HoverMotion
{
// A bank bends the existing velocity, rather than replacing it with a new heading.
// Positive UE roll is right bank. At low speed the turn authority fades away.
inline float BankYawRate(float BankDegrees, float ForwardSpeed)
{
    const float Speed = FMath::Abs(ForwardSpeed);
    return FMath::RadiansToDegrees(980.f * FMath::Tan(FMath::DegreesToRadians(BankDegrees)) /
                                   FMath::Max(Speed, 700.f)) *
           FMath::Clamp(Speed / 700.f, 0.f, 1.f) * FMath::Sign(ForwardSpeed);
}
inline FVector ApplyBank(FVector Velocity, float BankDegrees, float DeltaSeconds)
{
    const float Yaw = BankYawRate(BankDegrees, Velocity.Size2D());
    return Velocity.RotateAngleAxis(Yaw * DeltaSeconds, FVector::UpVector);
}
// Exact critically damped response for a constant target during this time step.
inline void Spring(float &Value, float &Velocity, float Target, float DeltaSeconds, float Frequency = 9.f)
{
    const float Offset = Value - Target;
    const float Impulse = Velocity + Frequency * Offset;
    const float Decay = FMath::Exp(-Frequency * DeltaSeconds);
    Value = Target + (Offset + Impulse * DeltaSeconds) * Decay;
    Velocity = (Velocity - Frequency * Impulse * DeltaSeconds) * Decay;
}

inline FVector HorizontalVelocity(FVector Velocity, FVector Input, float TopSpeed, float DeltaSeconds, bool Boost)
{
    Velocity.Z = Input.Z = 0;
    Input = Input.GetClampedToMaxSize(1.f);
    const bool HasThrust = !Input.IsNearlyZero(.01f);
    const bool Braking = HasThrust && FVector::DotProduct(Velocity, Input) < -10.f;
    // Release coasts; opposing thrust brakes before building speed in reverse.
    const float Acceleration = !HasThrust ? 900.f : Braking ? 3000.f : Boost ? 3200.f : 1800.f;
    return FMath::VInterpConstantTo(Velocity, Input * TopSpeed, DeltaSeconds, Acceleration);
}
} // namespace HoverMotion
