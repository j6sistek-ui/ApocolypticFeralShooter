#include "HoverAnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "AnimNodes/AnimNode_BlendSpacePlayer.h"
#include "AnimNodes/AnimNode_LayeredBoneBlend.h"
#include "AnimNodes/AnimNode_CopyPoseFromMesh.h"
#include "BoneControllers/AnimNode_TwoBoneIK.h"
#include "BoneControllers/AnimNode_ModifyBone.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Pawn.h"

// Keep the current pose within both legs' reach before solving foot IK.
// A fixed pelvis offset alone cannot cover the pack's taller dive/aim poses.
struct FHoverPelvisNode final : FAnimNode_ModifyBone
{
    FBoneReference Legs[2][3];
    FVector Targets[2];
    FHoverPelvisNode()
    {
        const TCHAR *Names[2][3] = {{TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l")},
                                    {TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r")}};
        for (int32 Side = 0; Side < 2; ++Side)
            for (int32 Joint = 0; Joint < 3; ++Joint)
                Legs[Side][Joint].BoneName = Names[Side][Joint];
    }
    virtual void InitializeBoneReferences(const FBoneContainer &Bones) override
    {
        BoneToModify.Initialize(Bones);
        for (auto &Leg : Legs)
            for (auto &Bone : Leg)
                Bone.Initialize(Bones);
    }
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        FAnimNode_ModifyBone::EvaluateSkeletalControl_AnyThread(Output, Transforms);
        if (Transforms.IsEmpty())
            return;
        const auto &Bones = Output.Pose.GetPose().GetBoneContainer();
        const FTransform Before = Output.Pose.GetComponentSpaceTransform(BoneToModify.GetCompactPoseIndex(Bones));
        FTransform &After = Transforms[0].Transform;
        float Drop = 0;
        for (int32 Side = 0; Side < 2; ++Side)
        {
            if (!Legs[Side][0].IsValidToEvaluate(Bones) || !Legs[Side][1].IsValidToEvaluate(Bones) ||
                !Legs[Side][2].IsValidToEvaluate(Bones))
                continue;
            FVector Points[3];
            for (int32 Joint = 0; Joint < 3; ++Joint)
                Points[Joint] =
                    Output.Pose.GetComponentSpaceTransform(Legs[Side][Joint].GetCompactPoseIndex(Bones)).GetLocation();
            const float Reach =
                (FVector::Distance(Points[0], Points[1]) + FVector::Distance(Points[1], Points[2])) * .985f;
            const FVector Hip = After.TransformPosition(Before.InverseTransformPosition(Points[0]));
            const FVector Delta = Hip - Targets[Side];
            const float VerticalReach = FMath::Sqrt(FMath::Max(0.f, Reach * Reach - float(Delta.SizeSquared2D())));
            Drop = FMath::Max(Drop, float(Delta.Z) - VerticalReach);
        }
        After.AddToTranslation(FVector(0, 0, -FMath::Clamp(Drop, 0.f, 20.f)));
    }
};

struct FHoverAnimProxy final : FAnimInstanceProxy
{
    FAnimNode_SequencePlayer_Standalone Players[2];
    FAnimNode_SequencePlayer_Standalone Rifle;
    FAnimNode_LayeredBoneBlend UpperBody;
    FAnimNode_TwoWayBlend Blend;
    FAnimNode_BlendSpacePlayer_Standalone Locomotion;
    FAnimNode_TwoWayBlend GroundBlend;
    FAnimNode_BlendSpacePlayer_Standalone Ride;
    FAnimNode_TwoWayBlend RideBlend;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FHoverPelvisNode Pelvis;
    FAnimNode_TwoBoneIK Left, Right;
    FAnimNode_ModifyBone Springs[4];
    FVector Secondary[4], SecondaryVelocity[4];
    FVector PreviousVelocity = FVector::ZeroVector, FilteredAcceleration = FVector::ZeroVector;
    float PreviousFootHeight[2] = {}, PreviousFootVelocity[2] = {}, FootCooldown[2] = {};
    bool bMotionInitialized = false;
    FAnimNode_ConvertComponentToLocalSpace Root;
    UAnimSequence *Desired = nullptr;
    UAnimSequence *Last = nullptr;
    int32 Serial = 0, LastSerial = -1, Active = 0;
    UAnimSequence *DesiredRifle = nullptr, *LastRifle = nullptr;
    int32 ShotSerial = 0, LastShotSerial = 0;
    float RecoilTime = 0;
    bool bRifleLoop = true;
    bool bRifleRecoil = false;
    bool bLoop = true;
    explicit FHoverAnimProxy(UAnimInstance *Instance) : FAnimInstanceProxy(Instance) {}

    virtual void Initialize(UAnimInstance *Instance) override
    {
        Blend.A.SetLinkNode(&Players[0]);
        Blend.B.SetLinkNode(&Players[1]);
        GroundBlend.A.SetLinkNode(&Blend);
        GroundBlend.B.SetLinkNode(&Locomotion);
        RideBlend.A.SetLinkNode(&GroundBlend);
        RideBlend.B.SetLinkNode(&Ride);
        UpperBody.BasePose.SetLinkNode(&RideBlend);
        UpperBody.BlendPoses.Reset();
        UpperBody.BlendWeights.Reset();
        UpperBody.LayerSetup.Reset();
        UpperBody.AddPose();
        UpperBody.BlendPoses[0].SetLinkNode(&Rifle);
        FBranchFilter Filter;
        Filter.BoneName = TEXT("spine_01");
        Filter.BlendDepth = 3;
        UpperBody.LayerSetup[0].BranchFilters.Add(Filter);
        UpperBody.bMeshSpaceRotationBlend = true;
        UpperBody.InvalidatePerBoneBlendWeights();
        UpperBody.BlendWeights[0] = 0;
        ToComponent.LocalPose.SetLinkNode(&UpperBody);
        Pelvis.ComponentPose.SetLinkNode(&ToComponent);
        Pelvis.BoneToModify.BoneName = TEXT("pelvis");
        Pelvis.TranslationMode = BMM_Additive;
        Pelvis.TranslationSpace = BCS_ComponentSpace;
        Pelvis.Translation = FVector(0, 0, -39.f);
        Pelvis.RotationMode = BMM_Additive;
        Pelvis.RotationSpace = BCS_ComponentSpace;
        Left.ComponentPose.SetLinkNode(&Pelvis);
        Right.ComponentPose.SetLinkNode(&Left);
        const FName SpringNames[] = {TEXT("chest_l"), TEXT("chest_r"), TEXT("glute_l"), TEXT("glute_r")};
        for (int32 I = 0; I < 4; ++I)
        {
            auto &Spring = Springs[I];
            Spring.ComponentPose.SetLinkNode(I == 0 ? static_cast<FAnimNode_Base *>(&Right) : &Springs[I - 1]);
            Spring.BoneToModify.BoneName = SpringNames[I];
            Spring.TranslationMode = BMM_Additive;
            Spring.TranslationSpace = BCS_ComponentSpace;
            Secondary[I] = SecondaryVelocity[I] = FVector::ZeroVector;
        }
        Root.ComponentPose.SetLinkNode(&Springs[3]);
        Left.IKBone.BoneName = TEXT("foot_l");
        Right.IKBone.BoneName = TEXT("foot_r");
        for (auto *IK : {&Left, &Right})
        {
            IK->EffectorLocationSpace = BCS_ComponentSpace;
            IK->JointTargetLocationSpace = BCS_ComponentSpace;
            IK->bAllowStretching = false;
            IK->bMaintainEffectorRelRot = false;
            IK->bTakeRotationFromEffectorSpace = false;
            IK->Alpha = 0;
        }
        Left.JointTargetLocation = FVector(25, 100, 50);
        Right.JointTargetLocation = FVector(-25, 100, 50);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base *GetCustomRootNode() override
    {
        return &Root;
    }
    virtual void GetCustomNodes(TArray<FAnimNode_Base *> &Nodes) override
    {
        Nodes = {&Players[0],  &Players[1], &Rifle, &Blend, &Locomotion, &GroundBlend, &UpperBody,
                 &ToComponent, &Pelvis,     &Left,  &Right, &Root,       &Ride,        &RideBlend};
        for (auto &Spring : Springs)
            Nodes.Add(&Spring);
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        Desired = State->Sequence;
        Serial = State->RestartSerial;
        bLoop = State->bLoop;
        // Feed a slow damped response with locomotion impacts and filtered
        // acceleration. Raw hover correction/breathing no longer excites it.
        if (auto *Pawn = State->TryGetPawnOwner(); Pawn && DT > 0)
        {
            auto *Mesh = State->GetSkelMeshComponent();
            const FVector Velocity = Pawn->GetVelocity();
            FVector Acceleration = bMotionInitialized ? (Velocity - PreviousVelocity) / DT : FVector::ZeroVector;
            PreviousVelocity = Velocity;
            FilteredAcceleration =
                FMath::VInterpTo(FilteredAcceleration, Acceleration.GetClampedToMaxSize(3500), DT, 5.f);
            FVector Force = FilteredAcceleration;
            const float Deadband = State->bRiding ? 400.f : 120.f;
            Force = Force.GetSafeNormal() * FMath::Max(0.f, float(Force.Size()) - Deadband);
            const FVector Local = Mesh->GetComponentTransform().InverseTransformVectorNoScale(Force);
            for (int32 Foot = 0; Foot < 2; ++Foot)
            {
                const float Height =
                    Mesh->GetSocketTransform(Foot == 0 ? TEXT("foot_l") : TEXT("foot_r"), RTS_Component)
                        .GetLocation()
                        .Z;
                const float FootSpeed = (Height - PreviousFootHeight[Foot]) / DT;
                FootCooldown[Foot] = FMath::Max(0.f, FootCooldown[Foot] - DT);
                if (bMotionInitialized && !State->bRiding && State->bGroundLocomotion && Velocity.Size2D() > 60 &&
                    Height < 20 && PreviousFootVelocity[Foot] < -4 && FootSpeed >= -1 && FootCooldown[Foot] <= 0)
                {
                    for (int32 I = 0; I < 4; ++I)
                        SecondaryVelocity[I].Z -= (I < 2 ? 12.f : 24.f) * (I % 2 == Foot ? 1.f : .72f);
                    FootCooldown[Foot] = .20f;
                }
                PreviousFootHeight[Foot] = Height;
                PreviousFootVelocity[Foot] = FootSpeed;
            }
            bMotionInitialized = true;
            for (int32 I = 0; I < 4; ++I)
            {
                const float Limit = I < 2 ? 2.f : 3.2f;
                const FVector Target =
                    FVector(-Local.X * .00035f, 0, -Local.Z * .0008f + Local.Y * .0005f).GetClampedToMaxSize(Limit);
                const int32 Steps = FMath::Max(1, FMath::CeilToInt(DT * 120.f));
                const float Step = DT / Steps;
                for (int32 J = 0; J < Steps; ++J)
                {
                    constexpr float Omega = 11.3f; // 1.8 Hz, deliberately below the former rapid vibration.
                    SecondaryVelocity[I] +=
                        ((Target - Secondary[I]) * Omega * Omega - SecondaryVelocity[I] * (2.f * .42f * Omega)) * Step;
                    Secondary[I] += SecondaryVelocity[I] * Step;
                    Secondary[I] = Secondary[I].GetClampedToMaxSize(Limit);
                }
                Springs[I].Translation = Secondary[I];
            }
        }
        for (auto &Spring : Springs)
            Spring.Alpha = State->bSecondaryMotion ? 1.f : 0.f;
        Ride.SetBlendSpace(State->RideBlend);
        Ride.SetPosition(State->RideInput);
        Ride.SetLoop(true);
        RideBlend.Alpha =
            FMath::FInterpConstantTo(RideBlend.Alpha, State->bRiding && State->RideBlend ? 1.f : 0.f, DT, 5.f);
        Locomotion.SetBlendSpace(State->Locomotion);
        Locomotion.SetPosition(State->LocomotionInput);
        Locomotion.SetLoop(true);
        Locomotion.SetPlayRate(FMath::Max(1.f, float(State->LocomotionInput.Y) / 600.f));
        GroundBlend.Alpha = FMath::FInterpConstantTo(
            GroundBlend.Alpha, State->bGroundLocomotion && State->Locomotion ? 1.f : 0.f, DT, 7.f);
        for (auto &Player : Players)
            Player.SetPlayRate(State->SequenceRate);
        RecoilTime = FMath::Max(0.f, RecoilTime - DT);
        ShotSerial = State->ShotSerial;
        if (State->bRiding && State->RifleFire && ShotSerial != LastShotSerial)
            RecoilTime = .16f;
        DesiredRifle = RecoilTime > 0 ? State->RifleFire.Get() : State->RifleAim.Get();
        bRifleRecoil = RecoilTime > 0;
        bRifleLoop = !State->bRiding;
        UpperBody.BlendWeights[0] =
            FMath::FInterpTo(UpperBody.BlendWeights[0], State->bAiming && State->RifleAim ? 1.f : 0.f, DT, 10.f);
        Left.Alpha = Right.Alpha = State->FootLock;
        Pelvis.Alpha = State->FootLock;
        Pelvis.Translation = FVector(-State->RideInput.X * 6.f, 0, -39.f);
        Pelvis.Targets[0] = State->LeftFoot;
        Pelvis.Targets[1] = State->RightFoot;
        Pelvis.Rotation = FQuat(FVector::ForwardVector, FMath::DegreesToRadians(-State->RiderLean)).Rotator();
        Left.EffectorLocation = State->LeftFoot;
        Right.EffectorLocation = State->RightFoot;
    }
    virtual void PostUpdate(UAnimInstance *Instance) const override
    {
        FAnimInstanceProxy::PostUpdate(Instance);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        State->SecondaryOffsets.Reset();
        for (const auto &Offset : Secondary)
            State->SecondaryOffsets.Add(State->bSecondaryMotion ? Offset : FVector::ZeroVector);
    }
    virtual void UpdateAnimationNode(const FAnimationUpdateContext &Context) override
    {
        const float DT = Context.GetDeltaTime();
        if (DesiredRifle && (DesiredRifle != LastRifle || ShotSerial != LastShotSerial))
        {
            Rifle.SetSequence(DesiredRifle);
            Rifle.SetLoopAnimation(bRifleLoop);
            Rifle.Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            Rifle.SetAccumulatedTime(!bRifleLoop && !bRifleRecoil ? DesiredRifle->GetPlayLength() : 0);
            LastRifle = DesiredRifle;
        }
        LastShotSerial = ShotSerial;
        if (Desired && (Desired != Last || Serial != LastSerial))
        {
            Active = 1 - Active;
            Players[Active].SetSequence(Desired);
            Players[Active].SetLoopAnimation(bLoop);
            Players[Active].SetAccumulatedTime(0);
            Players[Active].Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            Last = Desired;
            LastSerial = Serial;
        }
        Blend.Alpha = FMath::FInterpConstantTo(Blend.Alpha, float(Active), DT, 6.f);
        FAnimInstanceProxy::UpdateAnimationNode(Context);
    }
};

FAnimInstanceProxy *UHoverAnimInstance::CreateAnimInstanceProxy()
{
    return new FHoverAnimProxy(this);
}
void UHoverAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy)
{
    delete Proxy;
}

struct FHoverAccessoryProxy final : FAnimInstanceProxy
{
    FAnimNode_CopyPoseFromMesh Copy;
    FAnimNode_ConvertLocalToComponentSpace Component;
    FAnimNode_ModifyBone Chain[2];
    FAnimNode_ConvertComponentToLocalSpace Root;
    FVector Angles = FVector::ZeroVector, AngularVelocity = FVector::ZeroVector;
    FVector LastVelocity = FVector::ZeroVector, FilteredForce = FVector::ZeroVector;
    bool bInitialized = false;
    explicit FHoverAccessoryProxy(UAnimInstance *Instance) : FAnimInstanceProxy(Instance) {}
    virtual void Initialize(UAnimInstance *Instance) override
    {
        Copy.bUseAttachedParent = true;
        Copy.bCopyCurves = false; // The fitted body already contains Vexa's saved shape.
        Component.LocalPose.SetLinkNode(&Copy);
        for (int32 I = 0; I < 2; ++I)
        {
            Chain[I].ComponentPose.SetLinkNode(I == 0 ? static_cast<FAnimNode_Base *>(&Component) : &Chain[0]);
            Chain[I].BoneToModify.BoneName = I == 0 ? TEXT("afs_chain_01") : TEXT("afs_chain_02");
            Chain[I].RotationMode = BMM_Additive;
            Chain[I].RotationSpace = BCS_ComponentSpace;
        }
        Root.ComponentPose.SetLinkNode(&Chain[1]);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base *GetCustomRootNode() override
    {
        return &Root;
    }
    virtual void GetCustomNodes(TArray<FAnimNode_Base *> &Nodes) override
    {
        Nodes = {&Copy, &Component, &Chain[0], &Chain[1], &Root};
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *Mesh = Instance->GetSkelMeshComponent();
        if (auto *Owner = Mesh->GetOwner(); Owner && DT > 0)
        {
            const FVector Velocity = Owner->GetVelocity();
            const FVector Acceleration = bInitialized ? (Velocity - LastVelocity) / DT : FVector::ZeroVector;
            LastVelocity = Velocity;
            bInitialized = true;
            FilteredForce = FMath::VInterpTo(FilteredForce, Acceleration.GetClampedToMaxSize(2500), DT, 6.f);
            const FVector Force = Mesh->GetComponentTransform().InverseTransformVectorNoScale(FilteredForce);
            const FVector Target(FMath::Clamp(-FMath::RadiansToDegrees(FMath::Atan(Force.Y / 980.f)), -12.f, 18.f),
                                 FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(Force.X / 980.f)), -18.f, 18.f), 0);
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(DT * 120));
            const float Step = DT / Steps;
            for (int32 I = 0; I < Steps; ++I)
            {
                AngularVelocity += ((Target - Angles) * 49.f - AngularVelocity * 6.3f) * Step;
                Angles += AngularVelocity * Step;
                Angles.X = FMath::Clamp(Angles.X, -12.f, 18.f);
                Angles.Y = FMath::Clamp(Angles.Y, -18.f, 18.f);
            }
            Chain[0].Rotation = FRotator(Angles.Y, 0, Angles.X);
            Chain[1].Rotation = FRotator(Angles.Y * .3f, 0, Angles.X * .3f);
        }
    }
    virtual void PostUpdate(UAnimInstance *Instance) const override
    {
        FAnimInstanceProxy::PostUpdate(Instance);
        CastChecked<UHoverAccessoryAnimInstance>(Instance)->ChainAngles = Angles;
    }
};
FAnimInstanceProxy *UHoverAccessoryAnimInstance::CreateAnimInstanceProxy()
{
    return new FHoverAccessoryProxy(this);
}
void UHoverAccessoryAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy)
{
    delete Proxy;
}
