#include "HoverAnimInstance.h"
#include "HoverSecondaryMotion.h"
#include "HoverPilot.h"
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
#include "AnimNodes/AnimNode_RetargetPoseFromMesh.h"

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
    FAnimNode_RetargetPoseFromMesh MotionPose;
    FAnimNode_TwoWayBlend MotionBlend;
    FAnimNode_BlendSpacePlayer_Standalone Ride;
    FAnimNode_TwoWayBlend RideBlend;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FHoverPelvisNode Pelvis;
    FAnimNode_TwoBoneIK Left, Right;
    FAnimNode_ModifyBone Springs[4];
    FHoverSecondaryMotion Secondary;
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
        MotionPose.RetargetFrom = ERetargetSourceMode::CustomSkeletalMeshComponent;
        MotionPose.IKRetargeterAsset =
            LoadObject<UIKRetargeter>(nullptr, TEXT("/Game/HoverPrototype/CLSComparison/RTG_CLS_Vexa.RTG_CLS_Vexa"));
        MotionBlend.A.SetLinkNode(&GroundBlend);
        MotionBlend.B.SetLinkNode(&MotionPose);
        RideBlend.A.SetLinkNode(&MotionBlend);
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
        Nodes.Add(&MotionPose);
        Nodes.Add(&MotionBlend);
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        UpperBody.bMeshSpaceRotationBlend = !State->bProne;
        MotionPose.SourceMeshComponent = State->MotionSource;
        MotionBlend.Alpha = FMath::FInterpConstantTo(
            MotionBlend.Alpha, State->bMotionMatching && State->MotionSource ? 1.f : 0.f, DT, 8.f);
        Desired = State->Sequence;
        Serial = State->RestartSerial;
        bLoop = State->bLoop;
        Secondary.Update(State->GetSkelMeshComponent(), State->TryGetPawnOwner(), DT, State->bRiding,
                         State->bGroundLocomotion);
        for (int32 I = 0; I < 4; ++I)
            Springs[I].Translation = Secondary.Offsets[I];
        for (auto &Spring : Springs)
            Spring.Alpha =
                State->bSecondaryMotion && !State->GetSkelMeshComponent()->GetPostProcessInstance() ? 1.f : 0.f;
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
        State->SecondaryBonesEvaluated.Reset();
        for (const auto &Spring : Springs)
            State->SecondaryBonesEvaluated.Add(Spring.BoneToModify.IsValidToEvaluate(GetRequiredBones()));
        for (const auto &Offset : Secondary.Offsets)
            State->SecondaryOffsets.Add(State->bSecondaryMotion &&
                                                !State->GetSkelMeshComponent()->GetPostProcessInstance()
                                            ? Offset
                                            : FVector::ZeroVector);
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
    FVector LastAnchor = FVector::ZeroVector, LastAnchorSpeed = FVector::ZeroVector;
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
            FVector Acceleration = bInitialized ? (Velocity - LastVelocity) / DT : FVector::ZeroVector;
            const FVector Anchor = Mesh->GetSocketTransform(TEXT("spine_03"), RTS_Component).GetLocation();
            const FVector AnchorSpeed = bInitialized ? (Anchor - LastAnchor) / DT : FVector::ZeroVector;
            if (bInitialized && Velocity.Size2D() > 60 &&
                (!Cast<AHoverPilot>(Owner) || !Cast<AHoverPilot>(Owner)->IsMounted()))
            {
                const FVector LocalAccel = ((AnchorSpeed - LastAnchorSpeed) / DT).GetClampedToMaxSize(800);
                Acceleration += Mesh->GetComponentTransform().TransformVectorNoScale(
                    FVector(LocalAccel.X * 3.5f, LocalAccel.Y * 3.5f + LocalAccel.Z * 1.2f, 0));
            }
            LastAnchor = Anchor;
            LastAnchorSpeed = AnchorSpeed;
            LastVelocity = Velocity;
            bInitialized = true;
            FilteredForce = FMath::VInterpTo(FilteredForce, Acceleration.GetClampedToMaxSize(2500), DT, 6.f);
            const FVector Force = Mesh->GetComponentTransform().InverseTransformVectorNoScale(FilteredForce);
            const FVector Target(FMath::Clamp(-FMath::RadiansToDegrees(FMath::Atan(Force.Y / 450.f)), -25.f, 48.f),
                                 FMath::Clamp(FMath::RadiansToDegrees(FMath::Atan(Force.X / 450.f)), -45.f, 45.f), 0);
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(DT * 120));
            const float Step = DT / Steps;
            for (int32 I = 0; I < Steps; ++I)
            {
                AngularVelocity += ((Target - Angles) * 49.f - AngularVelocity * 3.6f) * Step;
                Angles += AngularVelocity * Step;
                Angles.X = FMath::Clamp(Angles.X, -25.f, 48.f);
                Angles.Y = FMath::Clamp(Angles.Y, -45.f, 45.f);
            }
            Chain[0].Rotation = FRotator(Angles.Y, 0, Angles.X);
            Chain[1].Rotation = FRotator(Angles.Y * .6f, 0, Angles.X * .6f);
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
