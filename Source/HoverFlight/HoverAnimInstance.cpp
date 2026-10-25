#include "HoverAnimInstance.h"
#include "HoverSecondaryMotion.h"
#include "HoverPilot.h"
#include "Animation/AnimInstanceProxy.h"
#include "Animation/AnimNode_SequencePlayer.h"
#include "AnimNodes/AnimNode_Slot.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "Animation/AnimSequence.h"
#include "AnimNodes/AnimNode_TwoWayBlend.h"
#include "AnimNodes/AnimNode_ApplyAdditive.h"
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

// Solve from this evaluation's right hand, avoiding a frame of weapon/hand lag.
struct FHoverSupportHandNode final : FAnimNode_TwoBoneIK
{
    FBoneReference GripHand, GripPalm, Palm, Shoulder;
    bool bGripAtPalm = false;
    FVector GripOffset = FVector::ZeroVector;
    FQuat GunRotation = FQuat::Identity;
    FHoverSupportHandNode()
    {
        IKBone.BoneName = TEXT("hand_l");
        GripHand.BoneName = TEXT("hand_r");
        GripPalm.BoneName = TEXT("middle_01_r");
        Palm.BoneName = TEXT("middle_01_l");
        Shoulder.BoneName = TEXT("upperarm_l");
        EffectorLocationSpace = JointTargetLocationSpace = BCS_ComponentSpace;
        bAllowStretching = false;
        bMaintainEffectorRelRot = false;
        bTakeRotationFromEffectorSpace = false;
    }
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext &Context) override
    {
        FAnimNode_TwoBoneIK::CacheBones_AnyThread(Context);
        const auto &Bones = Context.AnimInstanceProxy->GetRequiredBones();
        GripHand.Initialize(Bones);
        GripPalm.Initialize(Bones);
        Palm.Initialize(Bones);
        Shoulder.Initialize(Bones);
    }
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        const auto &Bones = Output.Pose.GetPose().GetBoneContainer();
        if (!GripHand.IsValidToEvaluate(Bones) || !Palm.IsValidToEvaluate(Bones) || !Shoulder.IsValidToEvaluate(Bones))
            return;
        const FVector Hand = Output.Pose.GetComponentSpaceTransform(IKBone.GetCompactPoseIndex(Bones)).GetLocation();
        const FVector PalmOffset =
            (Output.Pose.GetComponentSpaceTransform(Palm.GetCompactPoseIndex(Bones)).GetLocation() - Hand) * .5f;
        FVector Grip = Output.Pose.GetComponentSpaceTransform(GripHand.GetCompactPoseIndex(Bones)).GetLocation();
        if (bGripAtPalm && GripPalm.IsValidToEvaluate(Bones))
            Grip = FMath::Lerp(
                Grip, Output.Pose.GetComponentSpaceTransform(GripPalm.GetCompactPoseIndex(Bones)).GetLocation(), .5f);
        EffectorLocation = Grip + GunRotation.RotateVector(GripOffset) - PalmOffset;
        JointTargetLocation =
            Output.Pose.GetComponentSpaceTransform(Shoulder.GetCompactPoseIndex(Bones)).GetLocation() +
            FVector(30, 0, -35);
        FAnimNode_TwoBoneIK::EvaluateSkeletalControl_AnyThread(Output, Transforms);
    }
};

// Intersect the two-bone bend circle with a support plane. Preserve limb lengths
// and choose the side nearest the authored bend; unreachable contacts stay at
// the closest possible height instead of stretching a limb to the floor.
static FVector GroundBendTarget(const FVector &Start, const FVector &Joint, const FVector &End, const FVector &Target,
                                float Height)
{
    const float A = FVector::Distance(Start, Joint), B = FVector::Distance(Joint, End);
    const FVector Axis = (Target - Start).GetSafeNormal();
    const float D = FMath::Clamp(float(FVector::Distance(Start, Target)), .1f, (A + B) * .999f);
    const float Along = (A * A - B * B + D * D) / (2 * D);
    const float Radius = FMath::Sqrt(FMath::Max(0.f, A * A - Along * Along));
    const FVector Center = Start + Axis * Along;
    const FVector Up = (FVector::UpVector - Axis * Axis.Z).GetSafeNormal();
    if (Radius < .01f || Up.Z < .01f)
        return Joint;
    const float Z = FMath::Clamp(float((Height - Center.Z) / (Radius * Up.Z)), -1.f, 1.f);
    FVector Side = FVector::CrossProduct(Axis, Up);
    if (FVector::DotProduct(Joint - Center, Side) < 0)
        Side *= -1;
    return Center + Radius * (Up * Z + Side * FMath::Sqrt(1.f - Z * Z));
}

struct FHoverProneArmNode final : FAnimNode_TwoBoneIK
{
    FBoneReference Shoulder, Elbow, RightHand, Palm;
    bool bLeft = false;
    float WeaponAlpha = 0;
    float FloorHeight = 0;
    FVector GripOffset = FVector::ZeroVector;
    FQuat GunRotation = FQuat::Identity;
    FHoverProneArmNode()
    {
        EffectorLocationSpace = JointTargetLocationSpace = BCS_ComponentSpace;
        bAllowStretching = bMaintainEffectorRelRot = bTakeRotationFromEffectorSpace = false;
        RightHand.BoneName = TEXT("hand_r");
        Palm.BoneName = TEXT("middle_01_l");
    }
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext &Context) override
    {
        FAnimNode_TwoBoneIK::CacheBones_AnyThread(Context);
        const auto &Bones = Context.AnimInstanceProxy->GetRequiredBones();
        Shoulder.Initialize(Bones);
        Elbow.Initialize(Bones);
        RightHand.Initialize(Bones);
        Palm.Initialize(Bones);
    }
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        const auto &Bones = Output.Pose.GetPose().GetBoneContainer();
        if (!Shoulder.IsValidToEvaluate(Bones) || !Elbow.IsValidToEvaluate(Bones) ||
            !RightHand.IsValidToEvaluate(Bones) || !Palm.IsValidToEvaluate(Bones))
            return;
        auto Position = [&](const FBoneReference &Bone) {
            return Output.Pose.GetComponentSpaceTransform(Bone.GetCompactPoseIndex(Bones)).GetLocation();
        };
        const FVector Start = Position(Shoulder), Joint = Position(Elbow), Hand = Position(IKBone);
        FVector WeaponTarget;
        if (bLeft)
            WeaponTarget = Position(RightHand) + GunRotation.RotateVector(GripOffset) - (Position(Palm) - Hand) * .5f;
        else
            WeaponTarget = FVector(-16, Start.Y + 8.f, FloorHeight + 18.f);
        EffectorLocation = FMath::Lerp(FVector(Hand.X, Hand.Y, FloorHeight + 7.f), WeaponTarget, WeaponAlpha);
        JointTargetLocation = GroundBendTarget(Start, Joint, Hand, EffectorLocation, FloorHeight + 5.f);
        FAnimNode_TwoBoneIK::EvaluateSkeletalControl_AnyThread(Output, Transforms);
    }
};

// Posture blends can sweep a foot below the floor even when both source poses
// have valid contact. Correct only penetration, using the evaluated knee plane.
struct FHoverPostureContactNode final : FAnimNode_TwoBoneIK
{
    FBoneReference Thigh, Calf, Ball;
    float FloorHeight = 0;
    float SupportAlpha = 0;
    FHoverPostureContactNode()
    {
        EffectorLocationSpace = JointTargetLocationSpace = BCS_ComponentSpace;
        bAllowStretching = false;
        bMaintainEffectorRelRot = true;
    }
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext &Context) override
    {
        FAnimNode_TwoBoneIK::CacheBones_AnyThread(Context);
        const auto &Bones = Context.AnimInstanceProxy->GetRequiredBones();
        Thigh.Initialize(Bones);
        Calf.Initialize(Bones);
        Ball.Initialize(Bones);
    }
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        const auto &Bones = Output.Pose.GetPose().GetBoneContainer();
        if (!Thigh.IsValidToEvaluate(Bones) || !Calf.IsValidToEvaluate(Bones) || !Ball.IsValidToEvaluate(Bones))
            return;
        const FVector Foot = Output.Pose.GetComponentSpaceTransform(IKBone.GetCompactPoseIndex(Bones)).GetLocation();
        const FVector Toe = Output.Pose.GetComponentSpaceTransform(Ball.GetCompactPoseIndex(Bones)).GetLocation();
        const float Lowest = float(FMath::Min(Foot.Z, Toe.Z));
        const float Lift =
            FMath::Lerp(FMath::Max(0.f, FloorHeight + 2.f - Lowest), FloorHeight + 4.f - Lowest, SupportAlpha);
        if (FMath::Abs(Lift) < .01f && SupportAlpha < .01f)
            return;
        const FVector Hip = Output.Pose.GetComponentSpaceTransform(Thigh.GetCompactPoseIndex(Bones)).GetLocation();
        const FVector Knee = Output.Pose.GetComponentSpaceTransform(Calf.GetCompactPoseIndex(Bones)).GetLocation();
        EffectorLocation = Foot + FVector(0, 0, Lift);
        JointTargetLocation = Knee + (Knee - (Hip + Foot) * .5f).GetSafeNormal() * 30.f;
        JointTargetLocation = FMath::Lerp(
            JointTargetLocation, GroundBendTarget(Hip, Knee, Foot, EffectorLocation, FloorHeight + 6.f), SupportAlpha);
        FAnimNode_TwoBoneIK::EvaluateSkeletalControl_AnyThread(Output, Transforms);
    }
};

struct FHoverAnimProxy final : FAnimInstanceProxy
{
    FAnimNode_SequencePlayer_Standalone Players[2];
    FAnimNode_SequencePlayer_Standalone Rifle;
    FAnimNode_LayeredBoneBlend UpperBody;
    FAnimNode_LayeredBoneBlend ProneHands;
    FAnimNode_TwoWayBlend Blend;
    FAnimNode_BlendSpacePlayer_Standalone Locomotion;
    FAnimNode_TwoWayBlend GroundBlend;
    FAnimNode_RetargetPoseFromMesh MotionPose;
    FAnimNode_RetargetPoseFromMesh ReloadPose;
    FAnimNode_TwoWayBlend ReloadBlend;
    FAnimNode_TwoWayBlend MotionBlend;
    FAnimNode_BlendSpacePlayer_Standalone Ride;
    FAnimNode_TwoWayBlend RideBlend;
    FAnimNode_SequencePlayer_Standalone RideAction, Climb, Dive, AimAction, GunShot;
    FAnimNode_TwoWayBlend RideActionBlend, ClimbBlend, DiveBlend, AimActionBlend, WeaponPose;
    FAnimNode_BlendSpacePlayer_Standalone GliderAim;
    FAnimNode_ApplyAdditive ShotAdditive;
    UAnimSequence *DesiredAction = nullptr, *DesiredAimAction = nullptr;
    float ActionTime = 0, ActionDuration = 0, AimTime = 0, AimDuration = 0;
    int32 ActionSerial = 0, EvaluatedActionSerial = 0, AimSerial = 0, EvaluatedAimSerial = 0;
    int32 RideTurn = 0;
    bool bWasRiding = false, bWasThrust = false, bWasAiming = false;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_ModifyBone ProneNeck, ProneHead;
    FHoverPelvisNode Pelvis;
    FAnimNode_TwoBoneIK Left, Right;
    FHoverPostureContactNode GroundContacts[2];
    FHoverProneArmNode ProneArms[2];
    FHoverSupportHandNode SupportHand;
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
        RideActionBlend.A.SetLinkNode(&Ride);
        RideActionBlend.B.SetLinkNode(&RideAction);
        ClimbBlend.A.SetLinkNode(&RideActionBlend);
        ClimbBlend.B.SetLinkNode(&Climb);
        DiveBlend.A.SetLinkNode(&ClimbBlend);
        DiveBlend.B.SetLinkNode(&Dive);
        RideBlend.B.SetLinkNode(&DiveBlend);
        AimActionBlend.A.SetLinkNode(&GliderAim);
        AimActionBlend.B.SetLinkNode(&AimAction);
        ShotAdditive.Base.SetLinkNode(&AimActionBlend);
        ShotAdditive.Additive.SetLinkNode(&GunShot);
        WeaponPose.A.SetLinkNode(&Rifle);
        WeaponPose.B.SetLinkNode(&ShotAdditive);
        ReloadPose.RetargetFrom = ERetargetSourceMode::CustomSkeletalMeshComponent;
        ReloadPose.IKRetargeterAsset = MotionPose.IKRetargeterAsset;
        ReloadBlend.A.SetLinkNode(&WeaponPose);
        ReloadBlend.B.SetLinkNode(&ReloadPose);
        UpperBody.BasePose.SetLinkNode(&RideBlend);
        UpperBody.BlendPoses.Reset();
        UpperBody.BlendWeights.Reset();
        UpperBody.LayerSetup.Reset();
        UpperBody.AddPose();
        UpperBody.BlendPoses[0].SetLinkNode(&ReloadBlend);
        FBranchFilter Filter;
        Filter.BoneName = TEXT("spine_01");
        Filter.BlendDepth = 3;
        UpperBody.LayerSetup[0].BranchFilters.Add(Filter);
        UpperBody.bMeshSpaceRotationBlend = true;
        UpperBody.InvalidatePerBoneBlendWeights();
        UpperBody.BlendWeights[0] = 0;
        ProneHands.BasePose.SetLinkNode(&UpperBody);
        ProneHands.AddPose();
        ProneHands.BlendPoses[0].SetLinkNode(&Rifle);
        for (const FName Hand : {FName(TEXT("hand_l")), FName(TEXT("hand_r"))})
        {
            FBranchFilter HandFilter;
            HandFilter.BoneName = Hand;
            HandFilter.BlendDepth = 1;
            ProneHands.LayerSetup[0].BranchFilters.Add(HandFilter);
        }
        ProneHands.bMeshSpaceRotationBlend = true;
        ProneHands.InvalidatePerBoneBlendWeights();
        ProneHands.BlendWeights[0] = 0;
        ToComponent.LocalPose.SetLinkNode(&ProneHands);
        ProneNeck.ComponentPose.SetLinkNode(&ToComponent);
        ProneHead.ComponentPose.SetLinkNode(&ProneNeck);
        ProneNeck.BoneToModify.BoneName = TEXT("neck_01");
        ProneHead.BoneToModify.BoneName = TEXT("head");
        for (auto *Look : {&ProneNeck, &ProneHead})
        {
            Look->RotationMode = BMM_Additive;
            Look->RotationSpace = BCS_ComponentSpace;
            Look->Alpha = 0;
        }
        // The purchased belly crawl looks at the floor. Lift her gaze along the
        // ground while the arms support the torso and keep the rifle beside it.
        ProneNeck.Rotation = FQuat(FVector::ForwardVector, FMath::DegreesToRadians(50.f)).Rotator();
        ProneHead.Rotation = FQuat(FVector::ForwardVector, FMath::DegreesToRadians(25.f)).Rotator();
        Pelvis.ComponentPose.SetLinkNode(&ProneHead);
        Pelvis.BoneToModify.BoneName = TEXT("pelvis");
        Pelvis.TranslationMode = BMM_Additive;
        Pelvis.TranslationSpace = BCS_ComponentSpace;
        Pelvis.Translation = FVector(0, 0, -39.f);
        Pelvis.RotationMode = BMM_Additive;
        Pelvis.RotationSpace = BCS_ComponentSpace;
        Left.ComponentPose.SetLinkNode(&Pelvis);
        Right.ComponentPose.SetLinkNode(&Left);
        GroundContacts[0].ComponentPose.SetLinkNode(&Right);
        GroundContacts[1].ComponentPose.SetLinkNode(&GroundContacts[0]);
        for (int32 I = 0; I < 2; ++I)
        {
            const TCHAR *Side = I == 0 ? TEXT("l") : TEXT("r");
            GroundContacts[I].IKBone.BoneName = FName(*FString::Printf(TEXT("foot_%s"), Side));
            GroundContacts[I].Thigh.BoneName = FName(*FString::Printf(TEXT("thigh_%s"), Side));
            GroundContacts[I].Calf.BoneName = FName(*FString::Printf(TEXT("calf_%s"), Side));
            GroundContacts[I].Ball.BoneName = FName(*FString::Printf(TEXT("ball_%s"), Side));
        }
        ProneArms[0].ComponentPose.SetLinkNode(&GroundContacts[1]);
        ProneArms[1].ComponentPose.SetLinkNode(&ProneArms[0]);
        for (int32 I = 0; I < 2; ++I)
        {
            const TCHAR *Side = I == 0 ? TEXT("r") : TEXT("l");
            ProneArms[I].bLeft = I == 1;
            ProneArms[I].IKBone.BoneName = FName(*FString::Printf(TEXT("hand_%s"), Side));
            ProneArms[I].Shoulder.BoneName = FName(*FString::Printf(TEXT("upperarm_%s"), Side));
            ProneArms[I].Elbow.BoneName = FName(*FString::Printf(TEXT("lowerarm_%s"), Side));
        }
        SupportHand.ComponentPose.SetLinkNode(&ProneArms[1]);
        const FName SpringNames[] = {TEXT("chest_l"), TEXT("chest_r"), TEXT("glute_l"), TEXT("glute_r")};
        for (int32 I = 0; I < 4; ++I)
        {
            auto &Spring = Springs[I];
            Spring.ComponentPose.SetLinkNode(I == 0 ? static_cast<FAnimNode_Base *>(&SupportHand) : &Springs[I - 1]);
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
        Nodes.Add(&ReloadPose);
        Nodes.Add(&ReloadBlend);
        Nodes.Add(&MotionBlend);
        Nodes.Add(&SupportHand);
        Nodes.Add(&GroundContacts[0]);
        Nodes.Add(&GroundContacts[1]);
        Nodes.Add(&ProneHands);
        Nodes.Add(&ProneNeck);
        Nodes.Add(&ProneHead);
        Nodes.Add(&ProneArms[0]);
        Nodes.Add(&ProneArms[1]);
        Nodes.Append({&RideAction, &Climb, &Dive, &AimAction, &GunShot, &RideActionBlend, &ClimbBlend, &DiveBlend,
                      &AimActionBlend, &WeaponPose, &GliderAim, &ShotAdditive});
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        UpperBody.bMeshSpaceRotationBlend = !State->bProne;
        for (auto &Contact : GroundContacts)
        {
            Contact.Alpha = State->bGroundContacts && !State->bRiding ? 1.f : 0.f;
            Contact.FloorHeight = State->GroundContactHeight;
            Contact.SupportAlpha = FMath::FInterpTo(Contact.SupportAlpha, State->bSupportedProne ? 1.f : 0.f, DT, 10.f);
        }
        for (auto &Arm : ProneArms)
        {
            Arm.Alpha =
                FMath::FInterpTo(Arm.Alpha, State->bSupportedProne && State->bGroundContacts ? 1.f : 0.f, DT, 10.f);
            Arm.WeaponAlpha = FMath::FInterpTo(Arm.WeaponAlpha, State->bAiming ? 1.f : 0.f, DT, 10.f);
            Arm.FloorHeight = State->GroundContactHeight;
            Arm.GripOffset = State->SupportGripOffset;
            Arm.GunRotation = State->WeaponRotation;
        }
        ProneHands.BlendWeights[0] = FMath::FInterpTo(ProneHands.BlendWeights[0],
                                                      State->bSupportedProne && State->bAiming ? 1.f : 0.f, DT, 10.f);
        ProneNeck.Alpha = ProneHead.Alpha =
            FMath::FInterpTo(ProneNeck.Alpha, State->bSupportedProne ? 1.f : 0.f, DT, 10.f);
        MotionPose.SourceMeshComponent = State->MotionSource;
        ReloadPose.SourceMeshComponent = State->MotionSource;
        ReloadBlend.Alpha =
            FMath::FInterpTo(ReloadBlend.Alpha, State->bMountedReload && State->MotionSource ? 1.f : 0.f, DT, 12.f);
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
        ActionTime += DT;
        AimTime += DT;
        RecoilTime = FMath::Max(0.f, RecoilTime - DT);
        ShotSerial = State->ShotSerial;
        if (State->bRiding && State->RifleFire && ShotSerial != LastShotSerial)
            RecoilTime = State->RifleFire->GetPlayLength();
        if (const auto *Assets = State->RideAssets.Get())
        {
            Climb.SetSequence(Assets->RideClimbPose);
            Dive.SetSequence(Assets->RideDivePose);
            Climb.SetPlayRate(0);
            Dive.SetPlayRate(0);
            ClimbBlend.Alpha = FMath::FInterpTo(
                ClimbBlend.Alpha,
                State->bRiding && Assets->RideClimbPose ? FMath::Max(0.f, State->RidePitch) * .72f : 0.f, DT, 6.f);
            DiveBlend.Alpha = FMath::FInterpTo(
                DiveBlend.Alpha,
                State->bRiding && Assets->RideDivePose ? FMath::Max(0.f, -State->RidePitch) * .72f : 0.f, DT, 6.f);
            int32 Turn = RideTurn;
            if (State->RideInput.X < -.35f)
                Turn = -1;
            else if (State->RideInput.X > .35f)
                Turn = 1;
            else if (FMath::Abs(State->RideInput.X) < .15f)
                Turn = 0;
            UAnimSequence *Next = nullptr;
            if (State->bRiding && bWasRiding)
            {
                if (Turn != RideTurn)
                    Next = Turn < 0       ? Assets->RideLeftStart.Get()
                           : Turn > 0     ? Assets->RideRightStart.Get()
                           : RideTurn < 0 ? Assets->RideLeftEnd.Get()
                                          : Assets->RideRightEnd.Get();
                else if (State->bRideThrust != bWasThrust && Turn == 0)
                    Next = State->bRideThrust ? Assets->RideStart.Get() : Assets->RideStop.Get();
            }
            if (Next)
            {
                DesiredAction = Next;
                ActionTime = 0;
                ActionDuration = Next->GetPlayLength();
                ++ActionSerial;
            }
            RideTurn = Turn;
            bWasThrust = State->bRideThrust;
            bWasRiding = State->bRiding;
            const float ActionWeight = State->bRiding && DesiredAction
                                           ? FMath::Min(FMath::Clamp(ActionTime / .12f, 0.f, 1.f),
                                                        FMath::Clamp((ActionDuration - ActionTime) / .16f, 0.f, 1.f))
                                           : 0.f;
            RideActionBlend.Alpha = ActionWeight;
            State->RideTransition = ActionWeight > 0 ? DesiredAction->GetFName() : NAME_None;
            GliderAim.SetBlendSpace(Assets->RideAimBlend);
            GliderAim.SetPosition(State->RideAimInput);
            GliderAim.SetLoop(true);
            WeaponPose.Alpha = State->bRiding && Assets->RideAimBlend ? 1.f : 0.f;
            if (State->bRiding && State->bAiming != bWasAiming)
            {
                DesiredAimAction = State->bAiming ? Assets->AimStart.Get() : Assets->AimEnd.Get();
                AimTime = 0;
                AimDuration = DesiredAimAction ? DesiredAimAction->GetPlayLength() : 0;
                ++AimSerial;
            }
            bWasAiming = State->bAiming;
            AimActionBlend.Alpha =
                State->bRiding && DesiredAimAction ? FMath::Clamp((AimDuration - AimTime) / .14f, 0.f, 1.f) : 0.f;
            GunShot.SetSequence(Assets->RideRecoil);
            GunShot.SetLoopAnimation(false);
            ShotAdditive.Alpha = State->bRiding && Assets->RideRecoil && RecoilTime > 0
                                     ? FMath::Clamp(RecoilTime / .08f, 0.f, 1.f)
                                     : 0.f;
        }
        Locomotion.SetBlendSpace(State->Locomotion);
        Locomotion.SetPosition(State->LocomotionInput);
        Locomotion.SetLoop(true);
        Locomotion.SetPlayRate(FMath::Max(1.f, float(State->LocomotionInput.Y) / 600.f));
        GroundBlend.Alpha = FMath::FInterpConstantTo(
            GroundBlend.Alpha, State->bGroundLocomotion && State->Locomotion ? 1.f : 0.f, DT, 7.f);
        for (auto &Player : Players)
            Player.SetPlayRate(State->SequenceRate);
        DesiredRifle = State->RifleAim.Get();
        bRifleRecoil = false;
        bRifleLoop = !State->bRiding;
        // Rifle gait clips carry the weapon low. ADS remains a separate owned
        // upper-body pose over their matching lower-body motion.
        UpperBody.BlendWeights[0] = FMath::FInterpTo(UpperBody.BlendWeights[0],
                                                     ((State->bAiming && !State->bProne) || State->bMountedReload ||
                                                      (State->bRiding && AimTime < AimDuration)) &&
                                                             State->RifleAim
                                                         ? 1.f
                                                         : 0.f,
                                                     DT, 10.f);
        Left.Alpha = Right.Alpha = State->FootLock;
        SupportHand.Alpha = UpperBody.BlendWeights[0] * (1.f - ReloadBlend.Alpha);
        SupportHand.GripOffset = State->SupportGripOffset;
        SupportHand.GunRotation = State->WeaponRotation;
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
        if (ActionSerial != EvaluatedActionSerial && DesiredAction)
        {
            RideAction.SetSequence(DesiredAction);
            RideAction.SetLoopAnimation(false);
            RideAction.Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            RideAction.SetAccumulatedTime(0);
            EvaluatedActionSerial = ActionSerial;
        }
        if (AimSerial != EvaluatedAimSerial && DesiredAimAction)
        {
            AimAction.SetSequence(DesiredAimAction);
            AimAction.SetLoopAnimation(false);
            AimAction.Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            AimAction.SetAccumulatedTime(0);
            EvaluatedAimSerial = AimSerial;
        }
        if (ShotSerial != LastShotSerial)
        {
            GunShot.Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            GunShot.SetAccumulatedTime(0);
        }
        if (DesiredRifle && DesiredRifle != LastRifle)
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

// Purchased FPS poses and reload montage; ammo/timing stay with the native weapon.
struct FHoverViewProxy final : FAnimInstanceProxy
{
    FAnimNode_SequencePlayer_Standalone Idle, Aim, Melee;
    FAnimNode_TwoWayBlend AimBlend, MeleeBlend;
    FAnimNode_Slot Reload;
    FAnimNode_ConvertLocalToComponentSpace Component;
    FHoverSupportHandNode Support;
    FAnimNode_ConvertComponentToLocalSpace Root;
    explicit FHoverViewProxy(UAnimInstance *Instance) : FAnimInstanceProxy(Instance) {}
    virtual void Initialize(UAnimInstance *Instance) override
    {
        auto *State = CastChecked<UHoverViewAnimInstance>(Instance);
        State->Idle =
            LoadObject<UAnimSequence>(nullptr, TEXT("/Game/ZESP/ZE/Animations/M16/AS_FPS_Idle_M16.AS_FPS_Idle_M16"));
        State->AimIdle = LoadObject<UAnimSequence>(
            nullptr, TEXT("/Game/ZESP/ZE/Animations/M16/AS_FPS_Idle_Aim_M16.AS_FPS_Idle_Aim_M16"));
        State->MeleeIdle =
            LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Animations/QA_KatanaIdle.QA_KatanaIdle"));
        Idle.SetSequence(State->Idle);
        Aim.SetSequence(State->AimIdle);
        Idle.SetLoopAnimation(true);
        Aim.SetLoopAnimation(true);
        Melee.SetSequence(State->MeleeIdle);
        Melee.SetLoopAnimation(true);
        AimBlend.A.SetLinkNode(&Idle);
        AimBlend.B.SetLinkNode(&Aim);
        MeleeBlend.A.SetLinkNode(&AimBlend);
        MeleeBlend.B.SetLinkNode(&Melee);
        Reload.Source.SetLinkNode(&MeleeBlend);
        Reload.SlotName = TEXT("DefaultSlot");
        Reload.bAlwaysUpdateSourcePose = true;
        Component.LocalPose.SetLinkNode(&Reload);
        Support.ComponentPose.SetLinkNode(&Component);
        Support.bGripAtPalm = true;
        Root.ComponentPose.SetLinkNode(&Support);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base *GetCustomRootNode() override
    {
        return &Root;
    }
    virtual void GetCustomNodes(TArray<FAnimNode_Base *> &Nodes) override
    {
        Nodes = {&Idle, &Aim, &Melee, &AimBlend, &MeleeBlend, &Reload, &Component, &Support, &Root};
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverViewAnimInstance>(Instance);
        AimBlend.Alpha = State->AimAlpha;
        MeleeBlend.Alpha = State->bMelee ? 1.f : 0.f;
        Support.GripOffset = State->SupportGripOffset;
        Support.GunRotation = State->WeaponRotation;
        // Let the authored reload hand leave the foregrip.
        Support.Alpha =
            State->bMelee ? 0.f : FMath::FInterpTo(Support.Alpha, State->IsAnyMontagePlaying() ? 0.f : 1.f, DT, 16.f);
    }
};

FAnimInstanceProxy *UHoverViewAnimInstance::CreateAnimInstanceProxy()
{
    return new FHoverViewProxy(this);
}
void UHoverViewAnimInstance::DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy)
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
            const auto *Vehicle = Owner->GetAttachParentActor();
            const FVector Velocity = Vehicle ? Vehicle->GetVelocity() : Owner->GetVelocity();
            FVector Acceleration = bInitialized ? (Velocity - LastVelocity) / DT : FVector::ZeroVector;
            const FVector Anchor = Mesh->GetSocketTransform(TEXT("spine_03"), RTS_Component).GetLocation();
            const FVector AnchorSpeed = bInitialized ? (Anchor - LastAnchor) / DT : FVector::ZeroVector;
            if (bInitialized && !Vehicle && Velocity.Size2D() > 60 &&
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
