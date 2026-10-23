#pragma once
#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Pawn.h"

// Shared by both locomotion candidates. Excitation comes from evaluated body
// motion and foot contacts, with a separate deadband for hover corrections.
struct FHoverSecondaryMotion
{
    FVector Offsets[4] = {}, Speeds[4] = {};
    FVector LastVelocity = FVector::ZeroVector, FilteredAcceleration = FVector::ZeroVector;
    FVector LastPelvis = FVector::ZeroVector, LastPelvisSpeed = FVector::ZeroVector;
    FVector PelvisAcceleration = FVector::ZeroVector;
    float FootHeight[2] = {}, FootSpeed[2] = {}, Cooldown[2] = {};
    bool Initialized = false;

    void Update(USkeletalMeshComponent *Mesh, APawn *Pawn, float DT, bool Riding, bool Walking)
    {
        if (!Mesh || !Pawn || DT <= 0)
            return;
        const FVector Velocity = Pawn->GetVelocity();
        const FVector Pelvis = Mesh->GetSocketTransform(TEXT("pelvis"), RTS_Component).GetLocation();
        const FVector PelvisSpeed = Initialized ? (Pelvis - LastPelvis) / DT : FVector::ZeroVector;
        const FVector BodyAcceleration = Initialized ? (PelvisSpeed - LastPelvisSpeed) / DT : FVector::ZeroVector;
        PelvisAcceleration = FMath::VInterpTo(PelvisAcceleration, BodyAcceleration.GetClampedToMaxSize(900), DT, 8.f);
        const FVector Acceleration = Initialized ? (Velocity - LastVelocity) / DT : FVector::ZeroVector;
        LastVelocity = Velocity;
        LastPelvis = Pelvis;
        LastPelvisSpeed = PelvisSpeed;
        FilteredAcceleration = FMath::VInterpTo(FilteredAcceleration, Acceleration.GetClampedToMaxSize(3500), DT, 5.f);
        FVector Force = FilteredAcceleration;
        Force = Force.GetSafeNormal() * FMath::Max(0.f, float(Force.Size()) - (Riding ? 400.f : 120.f));
        const FVector Local = Mesh->GetComponentTransform().InverseTransformVectorNoScale(Force);
        const bool MovingOnFoot = !Riding && Walking && Velocity.Size2D() > 60.f;
        for (int32 Foot = 0; Foot < 2; ++Foot)
        {
            const float Height =
                Mesh->GetSocketTransform(Foot == 0 ? TEXT("foot_l") : TEXT("foot_r"), RTS_Component).GetLocation().Z;
            const float Speed = (Height - FootHeight[Foot]) / DT;
            Cooldown[Foot] = FMath::Max(0.f, Cooldown[Foot] - DT);
            if (Initialized && MovingOnFoot && Height < 22 && FootSpeed[Foot] < -4 && Speed >= -1 &&
                Cooldown[Foot] <= 0)
            {
                for (int32 I = 0; I < 4; ++I)
                    Speeds[I].Z -= (I < 2 ? 12.f : 68.f) * (I % 2 == Foot ? 1.f : .70f);
                Cooldown[Foot] = .20f;
            }
            FootHeight[Foot] = Height;
            FootSpeed[Foot] = Speed;
        }
        Initialized = true;
        for (int32 I = 0; I < 4; ++I)
        {
            const bool Glute = I >= 2;
            const float Limit = Glute ? 6.5f : 2.f;
            FVector Target(-Local.X * .00035f, 0, -Local.Z * .0008f + Local.Y * .0005f);
            if (MovingOnFoot && Glute)
                Target += FVector(-PelvisAcceleration.X * .006f, 0, -PelvisAcceleration.Z * .010f);
            Target = Target.GetClampedToMaxSize(Limit);
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(DT * 120.f));
            const float Step = DT / Steps;
            for (int32 J = 0; J < Steps; ++J)
            {
                const float Omega = Glute ? 10.f : 11.3f;
                Speeds[I] += ((Target - Offsets[I]) * Omega * Omega - Speeds[I] * (2.f * .45f * Omega)) * Step;
                Offsets[I] = (Offsets[I] + Speeds[I] * Step).GetClampedToMaxSize(Limit);
            }
        }
    }
};
