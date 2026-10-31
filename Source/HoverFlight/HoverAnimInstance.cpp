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
#include "Animation/AnimationPoseData.h"
#include "AnimationRuntime.h"

// Design A1 additive with the right fingers held (2026-10-30 23:30, "her hand is not on the grip"): the CLS fire
// clip retargeted onto Vexa splays the right fingers while it kicks hand_r, and the gun, seated at the palm, is
// left with an open hand beside its grip. Here the base (the stance aim pose) is evaluated once, every bone UNDER
// hand_r keeps its aim-pose local transform through the additive, and hand_r itself keeps the kick: that is what
// the gun now follows (AHoverPilot::UpdateGunTransform). No cached pose and no second evaluation of the shared aim
// player: this node owns both links like the engine node it extends and only re-does its Evaluate.
struct FHoverStanceFireNode final : FAnimNode_ApplyAdditive
{
    FBoneReference Hand;
    TArray<FCompactPoseBoneIndex> Held;
    // Evidence for the headless verify: the largest finger-local rotation the additive would have applied this
    // evaluation before the hold put the aim pose back (0 while the additive is off). Written on the anim thread,
    // read in PostUpdate; a frame of lag or a torn read is harmless for a peak.
    float LastSplayDeg = 0.f;
    FHoverStanceFireNode()
    {
        Hand.BoneName = TEXT("hand_r");
    }
    virtual void CacheBones_AnyThread(const FAnimationCacheBonesContext &Context) override
    {
        FAnimNode_ApplyAdditive::CacheBones_AnyThread(Context);
        const FBoneContainer &Bones = Context.AnimInstanceProxy->GetRequiredBones();
        Hand.Initialize(Bones);
        Held.Reset();
        if (!Hand.IsValidToEvaluate(Bones))
            return;
        const FCompactPoseBoneIndex HandIndex = Hand.GetCompactPoseIndex(Bones);
        // Every descendant (thumb/index/middle/ring/pinky *_01/_02/_03_r and Vexa's *_metacarpal_r), parent-first
        // since compact indices are parent-first; the hand itself is not held.
        for (int32 I = 0; I < Bones.GetCompactPoseNumBones(); ++I)
        {
            const FCompactPoseBoneIndex Index(I);
            for (FCompactPoseBoneIndex Parent = Bones.GetParentBoneIndex(Index); Parent.IsValid();
                 Parent = Bones.GetParentBoneIndex(Parent))
                if (Parent == HandIndex)
                {
                    Held.Add(Index);
                    break;
                }
        }
    }
    virtual void Evaluate_AnyThread(FPoseContext &Output) override
    {
        if (!FAnimWeight::IsRelevant(ActualAlpha) || !IsLODEnabled(Output.AnimInstanceProxy) || Held.IsEmpty())
        {
            LastSplayDeg = 0.f;
            FAnimNode_ApplyAdditive::Evaluate_AnyThread(Output);
            return;
        }
        FPoseContext AdditiveContext(Output, true);
        Base.Evaluate(Output);
        TArray<FTransform, TInlineAllocator<32>> Grip;
        for (const FCompactPoseBoneIndex &Index : Held)
            Grip.Add(Output.Pose[Index]);
        Additive.Evaluate(AdditiveContext);
        FAnimationPoseData BasePose(Output);
        const FAnimationPoseData AdditivePose(AdditiveContext);
        FAnimationRuntime::AccumulateAdditivePose(BasePose, AdditivePose, ActualAlpha, AAT_LocalSpaceBase);
        Output.Pose.NormalizeRotations();
        float Splay = 0.f;
        for (int32 I = 0; I < Held.Num(); ++I)
        {
            Splay = FMath::Max(Splay, float(Output.Pose[Held[I]].GetRotation().AngularDistance(Grip[I].GetRotation())));
            Output.Pose[Held[I]] = Grip[I];
        }
        LastSplayDeg = FMath::RadiansToDegrees(Splay);
    }
};

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
// Design B2 (2026-10-30): the rig's hand_l_target also carries a gun-space rotation delta (HandRotation) and a finger
// curl (Curl). The PALM, not the wrist, lands on the target after the turn; after the IK the hand's component-space
// rotation becomes D * (input rotation) with D = GunRotation * HandRotation * GunRotation^-1, and the 15 finger
// bones get local rotation Ref * Pow(Ref^-1 * Aim, Curl): 1 = the aim pose's fingers, 0 = the open reference pose,
// 1.6 = a tighter extrapolated grip. Everything blends with the node's Alpha like the IK itself.
struct FHoverSupportHandNode final : FAnimNode_TwoBoneIK
{
    FBoneReference GripHand, GripPalm, Palm, Shoulder;
    FBoneReference Fingers[15];
    bool bGripAtPalm = false;
    FVector GripOffset = FVector::ZeroVector;
    FQuat GunRotation = FQuat::Identity;
    FQuat HandRotation = FQuat::Identity;
    float Curl = 1.f;
    // The gun rides the right hand's kick: with a cached rest the gun frame used for the target and the turn is
    // (hand_r now) * rest^-1 (clamped like the gun placement) over GunRotation, read from THIS evaluation's hand_r.
    FQuat GripHandRest = FQuat::Identity;
    bool bGripHandRest = false;
    static const TCHAR *FingerName(int32 I)
    {
        static const TCHAR *Names[15] = {TEXT("thumb_01_l"),  TEXT("thumb_02_l"),  TEXT("thumb_03_l"),
                                         TEXT("index_01_l"),  TEXT("index_02_l"),  TEXT("index_03_l"),
                                         TEXT("middle_01_l"), TEXT("middle_02_l"), TEXT("middle_03_l"),
                                         TEXT("ring_01_l"),   TEXT("ring_02_l"),   TEXT("ring_03_l"),
                                         TEXT("pinky_01_l"),  TEXT("pinky_02_l"),  TEXT("pinky_03_l")};
        return Names[I];
    }
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
        for (int32 I = 0; I < 15; ++I)
        {
            Fingers[I].BoneName = FingerName(I);
            Fingers[I].Initialize(Bones);
        }
    }
    // Ref * Pow(Ref^-1 * Aim, Curl) through axis-angle scaling: an exact slerp inside [0, 1] and a clean
    // extrapolation past 1 (the delta's angle grows, its axis stays), with the shortest arc always taken.
    static FQuat CurlRotation(const FQuat &Ref, const FQuat &Aim, float Alpha)
    {
        FQuat Delta = (Ref.Inverse() * Aim).GetNormalized();
        if (Delta.W < 0)
            Delta = -Delta;
        FVector Axis;
        float Angle;
        Delta.ToAxisAndAngle(Axis, Angle);
        if (Angle < KINDA_SMALL_NUMBER || !Axis.Normalize())
            return Ref;
        return (Ref * FQuat(Axis, Angle * Alpha)).GetNormalized();
    }
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext &Output,
                                                   TArray<FBoneTransform> &Transforms) override
    {
        const auto &Bones = Output.Pose.GetPose().GetBoneContainer();
        if (!GripHand.IsValidToEvaluate(Bones) || !Palm.IsValidToEvaluate(Bones) || !Shoulder.IsValidToEvaluate(Bones))
            return;
        const FCompactPoseBoneIndex HandIndex = IKBone.GetCompactPoseIndex(Bones);
        const FTransform HandInput = Output.Pose.GetComponentSpaceTransform(HandIndex);
        const FVector Hand = HandInput.GetLocation();
        const FVector PalmOffset =
            (Output.Pose.GetComponentSpaceTransform(Palm.GetCompactPoseIndex(Bones)).GetLocation() - Hand) * .5f;
        const FTransform GripHandNow = Output.Pose.GetComponentSpaceTransform(GripHand.GetCompactPoseIndex(Bones));
        FVector Grip = GripHandNow.GetLocation();
        if (bGripAtPalm && GripPalm.IsValidToEvaluate(Bones))
            Grip = FMath::Lerp(
                Grip, Output.Pose.GetComponentSpaceTransform(GripPalm.GetCompactPoseIndex(Bones)).GetLocation(), .5f);
        // The same kick AHoverPilot::UpdateGunTransform gives the gun, from the same pose (this evaluation's hand_r,
        // which the pilot reads once it is finalized), so the support target sits where the kicked gun will be.
        const FQuat GunRot =
            bGripHandRest
                ? (HoverClampRotation(GripHandNow.GetRotation() * GripHandRest.Inverse(), 25.f) * GunRotation)
                      .GetNormalized()
                : GunRotation;
        // The hand turns about its wrist by D; the palm (half a hand along the fingers) then sits at
        // wrist + D(PalmOffset), so the wrist effector backs off by the TURNED offset to put the palm on target.
        const FQuat D = (GunRot * HandRotation * GunRot.Inverse()).GetNormalized();
        const bool bTurn = !D.Equals(FQuat::Identity, 1e-4f);
        const bool bCurl = !FMath::IsNearlyEqual(Curl, 1.f, 1e-3f);
        EffectorLocation = Grip + GunRot.RotateVector(GripOffset) - D.RotateVector(PalmOffset);
        // The fingers' input (aim pose) local rotations, read before the IK touches the pose; the reference pose
        // from the bone container. Parent-first order is the array order (each _02 follows its _01).
        FTransform FingerLocal[15];
        bool bFinger[15] = {};
        if (bCurl)
            for (int32 I = 0; I < 15; ++I)
            {
                if (!Fingers[I].IsValidToEvaluate(Bones))
                    continue;
                const FCompactPoseBoneIndex Index = Fingers[I].GetCompactPoseIndex(Bones);
                const FCompactPoseBoneIndex Parent = Bones.GetParentBoneIndex(Index);
                if (!Parent.IsValid())
                    continue;
                FTransform Local = Output.Pose.GetComponentSpaceTransform(Index).GetRelativeTransform(
                    Output.Pose.GetComponentSpaceTransform(Parent));
                Local.SetRotation(CurlRotation(Bones.GetRefPoseTransform(Index).GetRotation(), Local.GetRotation(),
                                               FMath::Clamp(Curl, 0.f, 1.6f)));
                FingerLocal[I] = Local;
                bFinger[I] = true;
            }
        // Elbow pole. Component space here is the mannequin's: +Y forward, +X her left. At the support grip
        // the pole sits out-left of and below the shoulder, as before. A reload clip's hand_l_target takes
        // the hand down to the belt (40-50 cm under the shoulder); the pole then follows it lower, further
        // left and a little back, so the elbow hangs under and outside the hand instead of flipping forward
        // through the receiver. A 15 cm dead band keeps the aim pose's own small hand height changes inert.
        const FVector ShoulderLocation =
            Output.Pose.GetComponentSpaceTransform(Shoulder.GetCompactPoseIndex(Bones)).GetLocation();
        const float Drop = FMath::Clamp(float(ShoulderLocation.Z - EffectorLocation.Z) - 15.f, 0.f, 60.f);
        JointTargetLocation = ShoulderLocation + FVector(30 + Drop * .25f, -Drop * .35f, -35 - Drop * .5f);
        FAnimNode_TwoBoneIK::EvaluateSkeletalControl_AnyThread(Output, Transforms);
        if (!bTurn && !bCurl)
            return;
        // The IK leaves the hand's input rotation (bTakeRotationFromEffectorSpace and bMaintainEffectorRelRot are
        // both off); its entry is the hand's. Children are set from this turned hand below, so they follow.
        FBoneTransform *HandEntry = Transforms.FindByPredicate(
            [&](const FBoneTransform &T) { return T.BoneIndex.GetInt() == HandIndex.GetInt(); });
        if (!HandEntry)
            return;
        if (bTurn)
            HandEntry->Transform.SetRotation((D * HandEntry->Transform.GetRotation()).GetNormalized());
        if (!bCurl)
            return;
        // Component-space finger transforms from the new hand, appended in parent-before-child order (the array
        // order), then the whole list sorted by bone index as LocalBlendCSBoneTransforms requires.
        // Vexa's hands are UE5-style: index/middle/ring/pinky_01_l hang off a *_metacarpal_l bone, not off hand_l
        // (only the thumb does). Output.Pose is still the INPUT pose here, so a parent that is not in Solved must be
        // re-rooted on the moved hand through its own input local transform, or the finger lands where the aim pose
        // left the metacarpal and the palm (midpoint hand_l / middle_01_l) lags the wrist by half its travel
        // (verify run 2026-10-30 21:14: 20 cm off the target mid-reload). Every re-rooted ancestor is appended too.
        TArray<TPair<int32, FTransform>, TInlineAllocator<24>> Solved;
        Solved.Emplace(HandIndex.GetInt(), HandEntry->Transform);
        auto FindSolved = [&](const FCompactPoseBoneIndex &Index) -> const TPair<int32, FTransform> * {
            return Solved.FindByPredicate([&](const TPair<int32, FTransform> &P) { return P.Key == Index.GetInt(); });
        };
        // The new component-space transform of any bone under the hand: input local chain on the solved parent.
        auto NewCS = [&](const FCompactPoseBoneIndex &Index, auto &Self) -> FTransform {
            if (const TPair<int32, FTransform> *Known = FindSolved(Index))
                return Known->Value;
            const FCompactPoseBoneIndex Parent = Bones.GetParentBoneIndex(Index);
            if (!Parent.IsValid() || Index.IsRootBone())
                return Output.Pose.GetComponentSpaceTransform(Index);
            const FTransform Local = Output.Pose.GetComponentSpaceTransform(Index).GetRelativeTransform(
                Output.Pose.GetComponentSpaceTransform(Parent));
            const FTransform CS = Local * Self(Parent, Self);
            Solved.Emplace(Index.GetInt(), CS);
            Transforms.Add(FBoneTransform(Index, CS));
            return CS;
        };
        for (int32 I = 0; I < 15; ++I)
        {
            if (!bFinger[I])
                continue;
            const FCompactPoseBoneIndex Index = Fingers[I].GetCompactPoseIndex(Bones);
            const FCompactPoseBoneIndex Parent = Bones.GetParentBoneIndex(Index);
            const FTransform CS = FingerLocal[I] * NewCS(Parent, NewCS);
            Solved.Emplace(Index.GetInt(), CS);
            Transforms.Add(FBoneTransform(Index, CS));
        }
        Transforms.Sort(
            [](const FBoneTransform &A, const FBoneTransform &B) { return A.BoneIndex.GetInt() < B.BoneIndex.GetInt(); });
    }
};

// Intersect the two-bone bend circle with a support plane. Preserve limb lengths
// and choose the side nearest the authored bend; unreachable contacts stay at
// the closest possible height instead of stretching a limb to the floor.
static float GroundHeight(const FPlane &Plane, const FVector &Point)
{
    return (Plane.W - Plane.X * Point.X - Plane.Y * Point.Y) / FMath::Max(Plane.Z, .1);
}
static FVector GroundBendTarget(const FVector &Start, const FVector &Joint, const FVector &End, const FVector &Target,
                                FPlane Plane, float Clearance)
{
    const float A = FVector::Distance(Start, Joint), B = FVector::Distance(Joint, End);
    const FVector Axis = (Target - Start).GetSafeNormal();
    const float D = FMath::Clamp(float(FVector::Distance(Start, Target)), .1f, (A + B) * .999f);
    const float Along = (A * A - B * B + D * D) / (2 * D);
    const float Radius = FMath::Sqrt(FMath::Max(0.f, A * A - Along * Along));
    const FVector Center = Start + Axis * Along;
    const FVector Normal(Plane.X, Plane.Y, Plane.Z);
    const FVector Up = (Normal - Axis * FVector::DotProduct(Axis, Normal)).GetSafeNormal();
    const float Projection = FVector::DotProduct(Up, Normal);
    if (Radius < .01f || Projection < .01f)
        return Joint;
    const float Z = FMath::Clamp(
        float((Plane.W + Clearance - FVector::DotProduct(Normal, Center)) / (Radius * Projection)), -1.f, 1.f);
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
    FPlane ElbowPlane = FPlane(0, 0, 1, 0), HandPlane = FPlane(0, 0, 1, 0);
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
        {
            WeaponTarget = FVector(-16, Start.Y + 8.f, 0);
            WeaponTarget.Z = GroundHeight(HandPlane, WeaponTarget) + 18.f;
        }
        EffectorLocation =
            FMath::Lerp(FVector(Hand.X, Hand.Y, GroundHeight(HandPlane, Hand) + 7.f), WeaponTarget, WeaponAlpha);
        JointTargetLocation = GroundBendTarget(Start, Joint, Hand, EffectorLocation, ElbowPlane, 5.f);
        FAnimNode_TwoBoneIK::EvaluateSkeletalControl_AnyThread(Output, Transforms);
    }
};

// Posture blends can sweep a foot below the floor even when both source poses
// have valid contact. Correct only penetration, using the evaluated knee plane.
struct FHoverPostureContactNode final : FAnimNode_TwoBoneIK
{
    FBoneReference Thigh, Calf, Ball;
    FPlane FloorPlane = FPlane(0, 0, 1, 0);
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
        const float Lowest =
            float(FMath::Min(Foot.Z - GroundHeight(FloorPlane, Foot), Toe.Z - GroundHeight(FloorPlane, Toe)));
        const float Lift = FMath::Lerp(FMath::Max(0.f, 2.f - Lowest), 4.f - Lowest, SupportAlpha);
        if (FMath::Abs(Lift) < .01f && SupportAlpha < .01f)
            return;
        const FVector Hip = Output.Pose.GetComponentSpaceTransform(Thigh.GetCompactPoseIndex(Bones)).GetLocation();
        const FVector Knee = Output.Pose.GetComponentSpaceTransform(Calf.GetCompactPoseIndex(Bones)).GetLocation();
        EffectorLocation = Foot + FVector(0, 0, Lift);
        JointTargetLocation = Knee + (Knee - (Hip + Foot) * .5f).GetSafeNormal() * 30.f;
        JointTargetLocation = FMath::Lerp(
            JointTargetLocation, GroundBendTarget(Hip, Knee, Foot, EffectorLocation, FloorPlane, 6.f), SupportAlpha);
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
    // Design A1: the on-foot stance fire reaction, a local-space additive over the stance aim pose (Rifle), on the
    // aim path before the layered blend and the support IK; restarted from 0 on every shot, full weight while it
    // runs, faded over its last 0.1 s, scaled by the DA's *RecoilScale.
    FAnimNode_SequencePlayer_Standalone StanceFire;
    FHoverStanceFireNode StanceAdditive;
    UAnimSequence *DesiredStanceFire = nullptr, *LastStanceFire = nullptr;
    float StanceRecoilTime = 0, StanceRecoilScale = 1;
    UAnimSequence *DesiredAction = nullptr, *DesiredAimAction = nullptr;
    float ActionTime = 0, ActionDuration = 0, AimTime = 0, AimDuration = 0;
    int32 ActionSerial = 0, EvaluatedActionSerial = 0, AimSerial = 0, EvaluatedAimSerial = 0;
    int32 RideTurn = 0;
    bool bWasRiding = false, bWasThrust = false, bWasAiming = false;
    FAnimNode_ConvertLocalToComponentSpace ToComponent;
    FAnimNode_ModifyBone ProneGround, ProneNeck, ProneHead;
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
        StanceAdditive.Base.SetLinkNode(&Rifle);
        StanceAdditive.Additive.SetLinkNode(&StanceFire);
        StanceAdditive.Alpha = 0;
        StanceFire.SetLoopAnimation(false);
        WeaponPose.A.SetLinkNode(&StanceAdditive);
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
        ProneGround.ComponentPose.SetLinkNode(&ToComponent);
        ProneGround.BoneToModify.BoneName = TEXT("root");
        ProneGround.RotationMode = ProneGround.TranslationMode = BMM_Additive;
        ProneGround.RotationSpace = ProneGround.TranslationSpace = BCS_ComponentSpace;
        ProneGround.Alpha = 0;
        ProneNeck.ComponentPose.SetLinkNode(&ProneGround);
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
        Nodes.Add(&ProneGround);
        Nodes.Add(&ProneNeck);
        Nodes.Add(&ProneHead);
        Nodes.Add(&ProneArms[0]);
        Nodes.Add(&ProneArms[1]);
        Nodes.Append({&RideAction, &Climb, &Dive, &AimAction, &GunShot, &RideActionBlend, &ClimbBlend, &DiveBlend,
                      &AimActionBlend, &WeaponPose, &GliderAim, &ShotAdditive, &StanceFire, &StanceAdditive});
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *State = CastChecked<UHoverAnimInstance>(Instance);
        UpperBody.bMeshSpaceRotationBlend = !State->bProne;
        ProneGround.Alpha =
            FMath::FInterpTo(ProneGround.Alpha, State->bSupportedProne && State->bGroundContacts ? 1.f : 0.f, DT, 10.f);
        if (State->bGroundContacts)
        {
            const FVector Normal(State->GroundPlane.X, State->GroundPlane.Y, State->GroundPlane.Z);
            const FQuat Align = FQuat::FindBetweenNormals(FVector::UpVector, Normal);
            const FVector Pivot(0, 0, GroundHeight(State->GroundPlane, FVector::ZeroVector));
            ProneGround.Rotation = Align.Rotator();
            ProneGround.Translation = Pivot - Align.RotateVector(Pivot);
        }
        for (int32 I = 0; I < 2; ++I)
        {
            auto &Contact = GroundContacts[I];
            Contact.Alpha = State->bGroundContacts && !State->bRiding ? 1.f : 0.f;
            Contact.FloorPlane = State->ContactPlanes[I];
            Contact.SupportAlpha = FMath::FInterpTo(Contact.SupportAlpha, State->bSupportedProne ? 1.f : 0.f, DT, 10.f);
        }
        for (int32 I = 0; I < 2; ++I)
        {
            auto &Arm = ProneArms[I];
            Arm.Alpha =
                FMath::FInterpTo(Arm.Alpha, State->bSupportedProne && State->bGroundContacts ? 1.f : 0.f, DT, 10.f);
            Arm.WeaponAlpha = FMath::FInterpTo(Arm.WeaponAlpha, State->bAiming ? 1.f : 0.f, DT, 10.f);
            Arm.ElbowPlane = State->ContactPlanes[2 + I];
            Arm.HandPlane = State->ContactPlanes[4 + I];
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
        // Design A1: the stance additive clock. Its player is (re)started in UpdateAnimationNode on the same serial
        // change; a clip that goes away (rig swap, mount) just lets the alpha run out.
        StanceRecoilTime = FMath::Max(0.f, StanceRecoilTime - DT);
        DesiredStanceFire = State->StanceFireAdd.Get();
        StanceRecoilScale = State->StanceRecoilScale;
        if (DesiredStanceFire && ShotSerial != LastShotSerial)
            StanceRecoilTime = DesiredStanceFire->GetPlayLength();
        StanceAdditive.Alpha = DesiredStanceFire && DesiredStanceFire == LastStanceFire && StanceRecoilTime > 0
                                   ? FMath::Clamp(StanceRecoilTime / .1f, 0.f, 1.f) * StanceRecoilScale
                                   : 0.f;
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
        // Design A2: with a rigged gun drawn the left hand is locked to it at weight 1 on every tick, through fire
        // additives, hit reacts and anything else that lowers the aim layer; only a reload (its clip's
        // hand_l_target) or the mounted reload pose takes it off.
        SupportHand.Alpha =
            FMath::Max(UpperBody.BlendWeights[0], State->bRiggedGunUp ? 1.f : 0.f) * (1.f - ReloadBlend.Alpha);
        SupportHand.GripOffset = State->SupportGripOffset;
        SupportHand.GunRotation = State->WeaponRotation;
        // Same anchor as AHoverPilot::UpdateGunTransform: the palm midpoint for a rig that seats there.
        SupportHand.bGripAtPalm = State->bGripAtPalm;
        // Design B1/B2: the rig bone's rotation delta (gun space) and finger curl.
        SupportHand.HandRotation = State->SupportHandRotation;
        SupportHand.Curl = State->SupportHandCurl;
        // The gun rides hand_r's kick: the pilot's cached rest lets the IK target ride it too, without a frame of lag.
        SupportHand.GripHandRest = State->GripHandRestRotation;
        SupportHand.bGripHandRest = State->bGripHandRestValid;
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
        State->StanceFireFingerSplayDeg = StanceAdditive.LastSplayDeg;
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
        // Design A1: the stance additive restarts from frame 0 (its own base frame, so it starts at zero delta) on
        // every shot; a changed clip is bound here so the alpha only opens once the player holds it.
        if (DesiredStanceFire && (ShotSerial != LastShotSerial || DesiredStanceFire != LastStanceFire))
        {
            StanceFire.SetSequence(DesiredStanceFire);
            StanceFire.SetLoopAnimation(false);
            StanceFire.Initialize_AnyThread(FAnimationInitializeContext(this, Context.SharedContext));
            StanceFire.SetAccumulatedTime(0);
            LastStanceFire = DesiredStanceFire;
        }
        else if (!DesiredStanceFire)
            LastStanceFire = nullptr;
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
        Support.HandRotation = State->SupportHandRotation;
        Support.Curl = State->SupportHandCurl;
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
