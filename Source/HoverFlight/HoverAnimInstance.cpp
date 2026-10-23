#include "HoverAnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "AnimNodes/AnimNode_BlendSpacePlayer.h"
#include "AnimNodes/AnimNode_LayeredBoneBlend.h"
#include "BoneControllers/AnimNode_TwoBoneIK.h"
#include "BoneControllers/AnimNode_ModifyBone.h"
#include "BoneControllers/AnimNode_SpringBone.h"

struct FHoverSpringBone : FAnimNode_SpringBone
{
    FVector Displacement = FVector::ZeroVector;
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        FAnimNode_SpringBone::EvaluateSkeletalControl_AnyThread(Output, Transforms);
        Displacement = Transforms.IsEmpty()
                           ? FVector::ZeroVector
                           : Transforms[0].Transform.GetLocation() -
                                 Output.Pose.GetComponentSpaceTransform(Transforms[0].BoneIndex).GetLocation();
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
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_ModifyBone Pelvis;
    FAnimNode_TwoBoneIK Left, Right;
    FHoverSpringBone Springs[4];
    FAnimNode_ConvertComponentToLocalSpace Root;
    UAnimSequence *Desired = nullptr;
    UAnimSequence *Last = nullptr;
    int32 Serial = 0, LastSerial = -1, Active = 0;
    bool bLoop = true;
    explicit FHoverAnimProxy(UAnimInstance *Instance) : FAnimInstanceProxy(Instance) {}

    virtual void Initialize(UAnimInstance *Instance) override
    {
        Blend.A.SetLinkNode(&Players[0]);
        Blend.B.SetLinkNode(&Players[1]);
        GroundBlend.A.SetLinkNode(&Blend);
        GroundBlend.B.SetLinkNode(&Locomotion);
        UpperBody.BasePose.SetLinkNode(&GroundBlend);
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
        Pelvis.Translation = FVector(0, 0, -32.f);
        Pelvis.RotationMode = BMM_Additive;
        Pelvis.RotationSpace = BCS_ComponentSpace;
        Left.ComponentPose.SetLinkNode(&Pelvis);
        Right.ComponentPose.SetLinkNode(&Left);
        const FName SpringNames[] = {TEXT("chest_l"), TEXT("chest_r"), TEXT("glute_l"), TEXT("glute_r")};
        for (int32 I = 0; I < 4; ++I)
        {
            auto &Spring = Springs[I];
            Spring.ComponentPose.SetLinkNode(I == 0 ? static_cast<FAnimNode_Base *>(&Right) : &Springs[I - 1]);
            Spring.SpringBone.BoneName = SpringNames[I];
            // Restore the source Xandra springs with a restrained stretch limit.
            Spring.SpringStiffness = 500;
            Spring.SpringDamping = I < 2 ? 12 : 10;
            Spring.bTranslateX = Spring.bTranslateY = false;
            Spring.bTranslateZ = true;
            Spring.bRotateX = Spring.bRotateY = Spring.bRotateZ = false;
            Spring.bLimitDisplacement = true;
            Spring.MaxDisplacement = 2.f;
            Spring.ErrorResetThresh = 256.f;
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
        Nodes = {&Players[0], &Players[1],  &Rifle,  &Blend, &Locomotion, &GroundBlend,
                 &UpperBody,  &ToComponent, &Pelvis, &Left,  &Right,      &Root};
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
        for (auto &Spring : Springs)
            Spring.Alpha = State->bSecondaryMotion ? 1.f : 0.f;
        Locomotion.SetBlendSpace(State->Locomotion);
        Locomotion.SetPosition(State->LocomotionInput);
        Locomotion.SetLoop(true);
        GroundBlend.Alpha = FMath::FInterpConstantTo(
            GroundBlend.Alpha, State->bGroundLocomotion && State->Locomotion ? 1.f : 0.f, DT, 7.f);
        for (auto &Player : Players)
            Player.SetPlayRate(State->SequenceRate);
        Rifle.SetSequence(State->RifleAim);
        Rifle.SetLoopAnimation(true);
        UpperBody.BlendWeights[0] =
            FMath::FInterpTo(UpperBody.BlendWeights[0], State->bAiming && State->RifleAim ? 1.f : 0.f, DT, 10.f);
        Left.Alpha = Right.Alpha = State->FootLock;
        Pelvis.Alpha = State->FootLock;
        Pelvis.Rotation = FQuat(FVector::ForwardVector, FMath::DegreesToRadians(-State->RiderLean)).Rotator();
        Left.EffectorLocation = State->LeftFoot;
        Right.EffectorLocation = State->RightFoot;
    }
    virtual void PostUpdate(UAnimInstance *Instance) const override
    {
        FAnimInstanceProxy::PostUpdate(Instance);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        State->SecondaryOffsets.Reset();
        for (const auto &Spring : Springs)
            State->SecondaryOffsets.Add(State->bSecondaryMotion ? Spring.Displacement : FVector::ZeroVector);
    }
    virtual void UpdateAnimationNode(const FAnimationUpdateContext &Context) override
    {
        const float DT = Context.GetDeltaTime();
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
