#include "HoverAnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "AnimNodes/AnimNode_LayeredBoneBlend.h"
#include "BoneControllers/AnimNode_TwoBoneIK.h"
#include "BoneControllers/AnimNode_ModifyBone.h"

struct FHoverAnimProxy final : FAnimInstanceProxy
{
    FAnimNode_SequencePlayer_Standalone Players[2];
    FAnimNode_SequencePlayer_Standalone Rifle;
    FAnimNode_LayeredBoneBlend UpperBody;
    FAnimNode_TwoWayBlend Blend;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_ModifyBone Pelvis;
    FAnimNode_TwoBoneIK Left, Right;
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
        UpperBody.BasePose.SetLinkNode(&Blend);
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
        Root.ComponentPose.SetLinkNode(&Right);
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
        Nodes = {&Players[0], &Players[1], &Rifle, &Blend, &UpperBody, &ToComponent, &Pelvis, &Left, &Right, &Root};
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        Desired = State->Sequence;
        Serial = State->RestartSerial;
        bLoop = State->bLoop;
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
