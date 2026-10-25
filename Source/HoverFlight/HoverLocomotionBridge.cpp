#include "HoverLocomotionBridge.h"
#include "HoverPilot.h"
#include "HoverAnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Animation/AnimBlueprint.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimNode_LinkedInputPose.h"
#include "BoneControllers/AnimNode_SpringBone.h"
#include "UObject/UnrealType.h"
#if WITH_EDITOR
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_CallFunction.h"
#include "K2Node_DynamicCast.h"
#include "K2Node_Self.h"
#include "AnimGraphNode_Root.h"
#include "AnimGraphNode_LinkedInputPose.h"
#include "AnimGraphNode_LocalToComponentSpace.h"
#include "AnimGraphNode_ComponentToLocalSpace.h"
#include "AnimGraphNode_SpringBone.h"
#include "AnimGraphNode_Slot.h"
#include "AnimGraphNode_SaveCachedPose.h"
#include "AnimGraphNode_UseCachedPose.h"
#include "AnimGraphNode_LayeredBoneBlend.h"
#include "Kismet/KismetMathLibrary.h"
#endif

namespace
{
void SetObject(UObject *Object, const TCHAR *Name, UObject *Value)
{
    if (auto *P = FindFProperty<FObjectPropertyBase>(Object->GetClass(), Name))
        P->SetObjectPropertyValue_InContainer(Object, Value);
}
void SetByte(UObject *Object, const TCHAR *Name, uint8 Value)
{
    if (auto *P = FindFProperty<FByteProperty>(Object->GetClass(), Name))
        P->SetPropertyValue_InContainer(Object, Value);
}
} // namespace
UHoverLocomotionBridge::UHoverLocomotionBridge()
{
    PrimaryComponentTick.bCanEverTick = true;
}
void UHoverLocomotionBridge::BeginPlay()
{
    Super::BeginPlay();
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    if (!Pilot)
        return;
    auto *DataClass =
        LoadClass<UActorComponent>(nullptr, TEXT("/Game/HoverPrototype/Hybrid/BPC_CLS_PoseData.BPC_CLS_PoseData_C"));
    auto *AnimClass =
        LoadClass<UAnimInstance>(nullptr, TEXT("/Game/HoverPrototype/Hybrid/ABP_CLS_Actions.ABP_CLS_Actions_C"));
    if (!AnimClass)
        AnimClass =
            LoadClass<UAnimInstance>(nullptr, TEXT("/Game/CLS/Core/Animations/ABP_CLS_Character.ABP_CLS_Character_C"));
    auto *Mesh = LoadObject<USkeletalMesh>(
        nullptr, TEXT("/Game/CLS/Core/Characters/Mannequins/Meshes/SKM_Quinn_Simple.SKM_Quinn_Simple"));
    if (!DataClass || !AnimClass || !Mesh)
        return;
    Locomotion = NewObject<UActorComponent>(Pilot, DataClass, TEXT("CLS_PoseData"));
    SetObject(Locomotion, TEXT("OwningCharacter"), Pilot);
    SetObject(Locomotion, TEXT("MovementComponent"), Pilot->GetCharacterMovement());
    SetObject(Locomotion, TEXT("CapsuleComponent"), Pilot->GetCapsuleComponent());
    SetObject(Locomotion, TEXT("ActiveProfile"),
              LoadObject<UObject>(nullptr, TEXT("/Game/HoverPrototype/CLSComparison/Profile_Vexa.Profile_Vexa")));
    // Local data-only copy has its automatic BeginPlay/Tick disconnected, so it
    // cannot overwrite Parkour gravity, jump, wall-run, crouch or slide settings.
    Locomotion->RegisterComponent();
    Locomotion->SetComponentTickEnabled(false);
    Driver = NewObject<USkeletalMeshComponent>(Pilot, TEXT("CLS_AnimationDriver"));
    Driver->SetupAttachment(Pilot->GetRootComponent());
    Driver->SetSkeletalMesh(Mesh);
    Driver->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Driver->SetHiddenInGame(true);
    Driver->CastShadow = false;
    Driver->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Driver->RegisterComponent();
    Driver->AddTickPrerequisiteComponent(this);
    SetObject(Locomotion, TEXT("MeshComponent"), Driver);
    Driver->SetWorldTransform(Pilot->GetMesh()->GetComponentTransform());
    // CLS evaluates once when the animation instance is created. Supply real
    // movement limits first so its acceleration normalization never starts at 0/0.
    if (auto *Package = Locomotion->FindFunction(TEXT("Package_AnimData")))
        Locomotion->ProcessEvent(Package, nullptr);
    Driver->SetAnimInstanceClass(AnimClass);
    AddTickPrerequisiteActor(Pilot);
    AddTickPrerequisiteComponent(Pilot->GetCharacterMovement());
    Pilot->GetMesh()->AddTickPrerequisiteComponent(Driver);
    bReady = true;
}
void UHoverLocomotionBridge::TickComponent(float DT, ELevelTick Type, FActorComponentTickFunction *Function)
{
    Super::TickComponent(DT, Type, Function);
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    if (!bReady || !Pilot)
        return;
    auto *DriverAnim = Driver->GetAnimInstance();
    const int32 NewPosture = bEnabled && Pilot->IsOnFoot() ? (Pilot->IsProne()           ? 2
                                                              : Pilot->IsGroundSliding() ? 1
                                                                                         : 0)
                                                           : 0;
    if (DriverAnim && NewPosture != PostureMode)
    {
        if (Posture)
            DriverAnim->Montage_Stop(.3f, Posture);
        Posture = nullptr;
        PostureMode = NewPosture;
        if (NewPosture)
        {
            auto *Clip = LoadObject<UAnimSequence>(
                nullptr, NewPosture == 2 ? TEXT("/Game/HoverPrototype/Animations/QA_ProneCrawl.QA_ProneCrawl")
                                         : TEXT("/Game/HoverPrototype/Animations/QA_GroundSlide.QA_GroundSlide"));
            if (Clip)
                Posture = DriverAnim->PlaySlotAnimationAsDynamicMontage(
                    Clip, TEXT("DefaultSlot"), NewPosture == 2 ? .55f : .22f, .3f, 1.f, 100000);
        }
    }
    if (DriverAnim && Posture && NewPosture == 2)
        DriverAnim->Montage_SetPlayRate(Posture,
                                        !Pilot->IsDiving() && Pilot->GetVelocity().Size2D() > 5.f
                                            ? FMath::Clamp(float(Pilot->GetVelocity().Size2D()) / 80.f, .3f, 1.5f)
                                            : 0.f);
    if (auto *Lock = FindFProperty<FBoolProperty>(Pilot->GetClass(), TEXT("WallJumpLock")))
    {
        const bool Locked = Lock->GetPropertyValue_InContainer(Pilot);
        if (Locked && !bWasWallJumpLocked && Pilot->GetVelocity().Z > 0 && Pilot->IsOnFoot())
            PlayAction(
                LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Animations/QA_WallJump.QA_WallJump")),
                0.f, false);
        bWasWallJumpLocked = Locked;
    }
    Driver->SetWorldTransform(Pilot->GetMesh()->GetComponentTransform());
    SetByte(Locomotion, TEXT("CurrentGait"), Pilot->GetCharacterMovement()->MaxWalkSpeed > 600 ? 1 : 0);
    // CLS Stance means Unarmed/Pistol/Rifle, not standing/crouching.
    // Crouching is selected through State.Movement.Crouch below.
    SetByte(Locomotion, TEXT("CurrentStance"), 0);
    SetByte(Locomotion, TEXT("CurrentRotationMode"), Pilot->UsesAimFacing() ? 1 : 0);
    if (auto *Package = Locomotion->FindFunction(TEXT("Package_AnimData")))
        Locomotion->ProcessEvent(Package, nullptr);
    // Parkour keeps a camera-relative capsule for its wall traces. CLS sees the
    // rendered body's orientation, otherwise the same yaw is applied twice.
    if (auto *Data = FindFProperty<FStructProperty>(Locomotion->GetClass(), TEXT("AnimData")))
    {
        void *Value = Data->ContainerPtrToValuePtr<void>(Locomotion);
        const FQuat BodyRotation = Driver->GetComponentQuat() * FRotator(0, 90, 0).Quaternion();
        for (TFieldIterator<FStructProperty> It(Data->Struct); It; ++It)
        {
            if (It->GetName().StartsWith(TEXT("ActorTransform_")))
            {
                auto *Transform = It->ContainerPtrToValuePtr<FTransform>(Value);
                Transform->SetRotation(BodyRotation);
            }
            else if (It->GetName().StartsWith(TEXT("OrientationIntent_")) && !Pilot->UsesAimFacing())
            {
                // The vendor package uses control rotation. Our free third-person
                // body faces travel, so steering and torso must share that intent.
                auto *Intent = It->ContainerPtrToValuePtr<FRotator>(Value);
                *Intent =
                    Pilot->GetVelocity().Size2D() > 12.f ? Pilot->GetVelocity().Rotation() : BodyRotation.Rotator();
                Intent->Pitch = Intent->Roll = 0;
            }
        }
    }
    if (auto *Anim = Cast<UHoverAnimInstance>(Pilot->GetMesh()->GetAnimInstance()))
    {
        Anim->MotionSource = Driver;
        Anim->bMotionMatching = bEnabled && Pilot->IsOnFoot();
    }
}
UActorComponent *UHoverIntegrationAuthoring::GetCLSData(AActor *Owner)
{
    auto *Bridge = Owner ? Owner->FindComponentByClass<UHoverLocomotionBridge>() : nullptr;
    return Bridge ? Bridge->Locomotion.Get() : nullptr;
}
bool UHoverLocomotionBridge::PlayAction(UAnimSequence *Sequence, float Duration, bool UpperBody)
{
    if (!Driver || !Driver->GetAnimInstance() || !Sequence || !bEnabled)
        return false;
    const float Rate = Duration > 0 ? Sequence->GetPlayLength() / Duration : 1.f;
    // The purchased skeleton already has a separate AdditiveGroup. Its slot can
    // carry a normal sequence through our upper-body blend without cancelling
    // the DefaultSlot used for slide/prone. Original skeleton stays untouched.
    Action = Driver->GetAnimInstance()->PlaySlotAnimationAsDynamicMontage(
        Sequence, UpperBody ? TEXT("AdditiveHitReact") : TEXT("DefaultSlot"), .12f, .18f, Rate);
    return Action != nullptr;
}
void UHoverLocomotionBridge::CancelAction()
{
    if (Driver && Driver->GetAnimInstance() && Action)
        Driver->GetAnimInstance()->Montage_Stop(.15f, Action);
}
bool UHoverLocomotionBridge::IsActionPlaying() const
{
    return Driver && Driver->GetAnimInstance() && Action && Driver->GetAnimInstance()->Montage_IsPlaying(Action);
}
USkeletalMeshComponent *UHoverIntegrationAuthoring::GetCLSDriver(AActor *Owner)
{
    auto *Bridge = Owner ? Owner->FindComponentByClass<UHoverLocomotionBridge>() : nullptr;
    return Bridge ? Bridge->Driver.Get() : nullptr;
}
FGameplayTagContainer UHoverIntegrationAuthoring::GetCLSTags(AActor *Owner)
{
    FGameplayTagContainer Tags;
    const auto *Pilot = Cast<AHoverPilot>(Owner);
    if (Pilot && Pilot->IsOnFoot() && Pilot->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight() < 70)
        Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("State.Movement.Crouch")));
    return Tags;
}
void UHoverBodyPhysics::NativeUpdateAnimation(float DT)
{
    Super::NativeUpdateAnimation(DT);
    auto *Pilot = Cast<AHoverPilot>(TryGetPawnOwner());
    const FVector Velocity = Pilot ? Pilot->GetVelocity() : FVector::ZeroVector;
    const bool Airborne = Pilot && (Pilot->IsMounted() || Pilot->GetCharacterMovement()->IsFalling());
    AirborneBlend = FMath::FInterpTo(AirborneBlend, Airborne ? 1.f : 0.f, DT, 8.f);
    // Avoid continually switching flight springs off/on at the acceleration
    // threshold. Preserve the accepted grounded settings, damp flight impulses.
    const float Target = !bPhysicsEnabled ? 0.f : Airborne ? .45f : 1.f;
    PhysicsAlpha = FMath::FInterpTo(PhysicsAlpha, Target, DT, 5);
    for (TFieldIterator<FStructProperty> It(GetClass()); It; ++It)
        if (It->Struct == FAnimNode_SpringBone::StaticStruct())
        {
            auto *Spring = It->ContainerPtrToValuePtr<FAnimNode_SpringBone>(this);
            const bool Glute = Spring->SpringBone.BoneName.ToString().StartsWith(TEXT("glute"));
            Spring->Alpha = PhysicsAlpha;
            Spring->SpringStiffness = FMath::Lerp(Glute ? 160.f : 220.f, Glute ? 100.f : 140.f, AirborneBlend);
            Spring->SpringDamping = FMath::Lerp(Glute ? 10.f : 12.f, Glute ? 22.f : 25.f, AirborneBlend);
            Spring->MaxDisplacement = FMath::Lerp(Glute ? 6.5f : 3.5f, Glute ? 3.f : 2.f, AirborneBlend);
            // A long render frame during fast flight is ordinary travel, not a
            // teleport. Avoid resetting and restarting the spring every frame.
            Spring->ErrorResetThresh = FMath::Max(250., Velocity.Size() * DT * 2. + 50.);
        }
}
void UHoverBodyPhysics::NativePostEvaluateAnimation()
{
    Super::NativePostEvaluateAnimation();
}
void UHoverBodyPhysics::MeasureRenderedOffsets()
{
    // Call after the component finalizes its pose, not inside PostEvaluate
    // (which still exposes the preceding frame's component-space transforms).
    EvaluatedBones.Reset();
    MeasuredOffsets.Reset();
    MeasuredAlphas.Reset();
    auto *Input = GetLinkedInputPoseNode();
    if (!Input || !Input->bIsCachedInputPoseInitialized)
        return;
    const auto &Pose = Input->CachedInputPose;
    const auto &Bones = Pose.GetBoneContainer();
    for (TFieldIterator<FStructProperty> It(GetClass()); It; ++It)
    {
        if (It->Struct != FAnimNode_SpringBone::StaticStruct())
            continue;
        auto *Spring = It->ContainerPtrToValuePtr<FAnimNode_SpringBone>(this);
        if (!Spring->SpringBone.IsValidToEvaluate(Bones))
            continue;
        auto Index = Spring->SpringBone.GetCompactPoseIndex(Bones);
        FTransform InputTransform = Pose[Index];
        auto Parent = Bones.GetParentBoneIndex(Index);
        while (Parent.GetInt() != INDEX_NONE)
        {
            InputTransform = InputTransform * Pose[Parent];
            Parent = Bones.GetParentBoneIndex(Parent);
        }
        EvaluatedBones.Add(Spring->SpringBone.BoneName);
        MeasuredAlphas.Add(Spring->ActualAlpha);
        // Report the resulting rendered bone, not the spring's stale internal
        // location when its alpha is zero.
        MeasuredOffsets.Add(
            GetSkelMeshComponent()->GetSocketTransform(Spring->SpringBone.BoneName, RTS_Component).GetLocation() -
            InputTransform.GetLocation());
    }
}

#if WITH_EDITOR
template <class T> T *AddNode(UEdGraph *Graph)
{
    auto *Node = NewObject<T>(Graph);
    Graph->AddNode(Node, false, false);
    Node->CreateNewGuid();
    Node->PostPlacedNewNode();
    Node->AllocateDefaultPins();
    return Node;
}
bool Connect(UEdGraphNode *A, const TCHAR *Out, UEdGraphNode *B, const TCHAR *In)
{
    auto *P = A->FindPin(Out);
    auto *Q = B->FindPin(In);
    if (!P && FString(Out) == TEXT("Pose"))
        for (auto *Pin : A->Pins)
            if (Pin->Direction == EGPD_Output && Pin->PinName.ToString().Contains(TEXT("Pose")))
            {
                P = Pin;
                break;
            }
    const bool Ok = P && Q && A->GetGraph()->GetSchema()->TryCreateConnection(P, Q);
    if (!Ok)
        UE_LOG(LogTemp, Error, TEXT("HYBRID_CONNECT %s.%s -> %s.%s pins=%d,%d"), *A->GetName(), Out, *B->GetName(), In,
               P != nullptr, Q != nullptr);
    return Ok;
}
#endif
bool UHoverIntegrationAuthoring::BuildActionLayer(UAnimBlueprint *Blueprint)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Hybrid/")))
        return false;
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
    {
        if (Graph->GetFName() != TEXT("Update_Lean"))
            continue;
        const bool Guarded = Graph->Nodes.ContainsByPredicate(
            [](const UEdGraphNode *Node) { return Node->NodeComment == TEXT("AFS safe acceleration normalization"); });
        if (Guarded)
            continue;
        for (UEdGraphNode *Node : TArray<TObjectPtr<UEdGraphNode>>(Graph->Nodes))
        {
            if (Node->GetFName() != TEXT("K2Node_PromotableOperator_0"))
                continue;
            auto *Denominator = Node->FindPin(TEXT("B"));
            if (!Denominator || Denominator->LinkedTo.Num() != 1)
                return false;
            UEdGraphPin *Value = Denominator->LinkedTo[0];
            auto *Guard = NewObject<UK2Node_CallFunction>(Graph);
            Guard->SetFromFunction(UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("FMax")));
            Graph->AddNode(Guard, false, false);
            Guard->CreateNewGuid();
            Guard->PostPlacedNewNode();
            Guard->AllocateDefaultPins();
            Guard->NodeComment = TEXT("AFS safe acceleration normalization");
            Guard->FindPin(TEXT("B"))->DefaultValue = TEXT("1.0");
            Denominator->BreakAllPinLinks();
            if (!Graph->GetSchema()->TryCreateConnection(Value, Guard->FindPin(TEXT("A"))) ||
                !Graph->GetSchema()->TryCreateConnection(Guard->GetReturnValuePin(), Denominator))
                return false;
            break;
        }
    }
    for (auto *Graph : Graphs)
    {
        if (Graph->GetFName() != TEXT("AnimGraph"))
            continue;
        // Authored full-body postures already define their ground contacts.
        // Applying CLS root offset/standing foot placement AFTER a slide holds
        // it behind the capsule and pulls the body forward when the action ends.
        for (UEdGraphNode *Node : Graph->Nodes)
            if (auto *Slot = Cast<UAnimGraphNode_Slot>(Node); Slot && Slot->Node.SlotName == TEXT("DefaultSlot"))
            {
                Slot->Node.bAlwaysUpdateSourcePose = true;
                if (Slot->NodeComment == TEXT("AFS full body after locomotion correction"))
                    break;
                UEdGraphNode *History = nullptr;
                for (UEdGraphNode *Candidate : Graph->Nodes)
                    if (Candidate->GetClass()->GetName() == TEXT("AnimGraphNode_PoseSearchHistoryCollector"))
                        History = Candidate;
                auto *SlotInput = Slot->FindPin(TEXT("Source"));
                auto *SlotOutput = Slot->FindPin(TEXT("Pose"));
                auto *HistoryInput = History ? History->FindPin(TEXT("Source")) : nullptr;
                if (!SlotInput || !SlotOutput || !HistoryInput || SlotInput->LinkedTo.Num() != 1 ||
                    SlotOutput->LinkedTo.Num() != 1 || HistoryInput->LinkedTo.Num() != 1)
                    return false;
                auto *BeforeSlot = SlotInput->LinkedTo[0];
                auto *AfterSlot = SlotOutput->LinkedTo[0];
                auto *CorrectedPose = HistoryInput->LinkedTo[0];
                SlotInput->BreakAllPinLinks();
                SlotOutput->BreakAllPinLinks();
                HistoryInput->BreakAllPinLinks();
                if (!Graph->GetSchema()->TryCreateConnection(BeforeSlot, AfterSlot) ||
                    !Graph->GetSchema()->TryCreateConnection(CorrectedPose, SlotInput) ||
                    !Graph->GetSchema()->TryCreateConnection(SlotOutput, HistoryInput))
                    return false;
                Slot->NodeComment = TEXT("AFS full body after locomotion correction");
                break;
            }
        UAnimGraphNode_Root *Root = nullptr;
        for (UEdGraphNode *Node : Graph->Nodes)
        {
            if (Node->NodeComment == TEXT("AFS upper body actions"))
            {
                if (auto *Layer = Cast<UAnimGraphNode_LayeredBoneBlend>(Node))
                    Layer->Node.bMeshSpaceRotationBlend = false;
                FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
                FKismetEditorUtilities::CompileBlueprint(Blueprint);
                return true;
            }
            if (auto *Candidate = Cast<UAnimGraphNode_Root>(Node))
                Root = Candidate;
        }
        if (!Root || Root->FindPin(TEXT("Result"))->LinkedTo.Num() != 1)
            return false;
        auto *Input = Root->FindPin(TEXT("Result"));
        auto *Source = Input->LinkedTo[0];
        auto *Cache = AddNode<UAnimGraphNode_SaveCachedPose>(Graph);
        Cache->CacheName = TEXT("AFS locomotion and posture");
        auto *Base = AddNode<UAnimGraphNode_UseCachedPose>(Graph);
        auto *ActionBase = AddNode<UAnimGraphNode_UseCachedPose>(Graph);
        Base->SaveCachedPoseNode = Cache;
        ActionBase->SaveCachedPoseNode = Cache;
        auto *Slot = AddNode<UAnimGraphNode_Slot>(Graph);
        Slot->Node.SlotName = TEXT("AdditiveHitReact");
        auto *Layer = AddNode<UAnimGraphNode_LayeredBoneBlend>(Graph);
        Layer->Node.BlendPoses.Reset();
        Layer->Node.BlendWeights.Reset();
        Layer->Node.LayerSetup.Reset();
        Layer->Node.AddPose();
        FBranchFilter Filter;
        Filter.BoneName = TEXT("spine_01");
        Filter.BlendDepth = 3;
        Layer->Node.LayerSetup[0].BranchFilters.Add(Filter);
        Layer->Node.BlendWeights[0] = 1.f;
        Layer->Node.bMeshSpaceRotationBlend = false;
        Layer->NodeComment = TEXT("AFS upper body actions");
        Layer->ReconstructNode();
        Input->BreakLinkTo(Source);
        if (!Graph->GetSchema()->TryCreateConnection(Source, Cache->FindPin(TEXT("Pose"))) ||
            !Connect(Base, TEXT("Pose"), Layer, TEXT("BasePose")) ||
            !Connect(ActionBase, TEXT("Pose"), Slot, TEXT("Source")) ||
            !Connect(Slot, TEXT("Pose"), Layer, TEXT("BlendPoses_0")) ||
            !Connect(Layer, TEXT("Pose"), Root, TEXT("Result")))
            return false;
        int32 X = 0;
        for (auto *Node : TArray<UEdGraphNode *>{Cache, Base, ActionBase, Slot, Layer, Root})
        {
            Node->NodePosX = X;
            Node->NodePosY = 500;
            X += 250;
        }
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
        return Blueprint->Status != BS_Error;
    }
#endif
    return false;
}
bool UHoverIntegrationAuthoring::ConfigureMovementTags(UBlueprint *Blueprint)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Hybrid/")))
        return false;
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
    {
        if (Graph->GetFName() != TEXT("Get_Locomotion_Tags"))
            continue;
        for (UEdGraphNode *Node : Graph->Nodes)
            if (auto *Result = Cast<UK2Node_FunctionResult>(Node))
            {
                if (Result->FindPin(TEXT("Tags"))->LinkedTo.Num())
                    return true;
                auto *Call = NewObject<UK2Node_CallFunction>(Graph);
                Call->SetFromFunction(StaticClass()->FindFunctionByName(TEXT("GetCLSTags")));
                Graph->AddNode(Call, false, false);
                Call->CreateNewGuid();
                Call->PostPlacedNewNode();
                Call->AllocateDefaultPins();
                auto *Self = AddNode<UK2Node_Self>(Graph);
                if (!Connect(Self, TEXT("self"), Call, TEXT("Owner")) ||
                    !Connect(Call, TEXT("ReturnValue"), Result, TEXT("Tags")))
                    return false;
                Self->NodePosX = -400;
                Call->NodePosX = -200;
                Result->NodePosX = 100;
                FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
                FKismetEditorUtilities::CompileBlueprint(Blueprint);
                return Blueprint->Status != BS_Error;
            }
    }
#endif
    return false;
}
bool UHoverIntegrationAuthoring::ConfigureHybrid(UBlueprint *Pilot, UBlueprint *DataComponent)
{
#if WITH_EDITOR
    if (!Pilot || !DataComponent || !Pilot->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Hybrid/")) ||
        !DataComponent->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Hybrid/")))
        return false;
    TArray<UEdGraph *> Graphs;
    DataComponent->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
        for (UEdGraphNode *Node : Graph->Nodes)
            if (auto *Event = Cast<UK2Node_Event>(Node))
                if (auto *Pin = Event->FindPin(UEdGraphSchema_K2::PN_Then))
                    Pin->BreakAllPinLinks();
    auto *EventGraph = FBlueprintEditorUtils::FindEventGraph(DataComponent);
    if (!EventGraph)
        return false;
    for (const TCHAR *Name : {TEXT("ReceiveBeginPlay"), TEXT("ReceiveTick")})
    {
        auto *Event = NewObject<UK2Node_Event>(EventGraph);
        Event->EventReference.SetExternalMember(Name, UActorComponent::StaticClass());
        Event->bOverrideFunction = true;
        EventGraph->AddNode(Event, false, false);
        Event->CreateNewGuid();
        Event->PostPlacedNewNode();
        Event->AllocateDefaultPins();
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(DataComponent);
    FKismetEditorUtilities::CompileBlueprint(DataComponent);
    auto *Interface = LoadClass<UInterface>(
        nullptr, TEXT("/Game/CLS/Core/Interfaces/BPI_LocomotionProvider.BPI_LocomotionProvider_C"));
    if (!Interface)
        return false;
    if (!Pilot->GeneratedClass->ImplementsInterface(Interface))
        if (!FBlueprintEditorUtils::ImplementNewInterface(Pilot, FTopLevelAssetPath(Interface)))
            return false;
    Graphs.Reset();
    Pilot->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
    {
        const bool Data = Graph->GetFName() == TEXT("Get_Locomotion_Component");
        const bool DriverGraph = Graph->GetFName() == TEXT("Get_DriverMesh");
        if (!Data && !DriverGraph)
            continue;
        UK2Node_FunctionResult *Result = nullptr;
        for (UEdGraphNode *Node : Graph->Nodes)
            if (auto *R = Cast<UK2Node_FunctionResult>(Node))
                Result = R;
        if (!Result)
            return false;
        auto *Call = NewObject<UK2Node_CallFunction>(Graph);
        Call->SetFromFunction(StaticClass()->FindFunctionByName(Data ? TEXT("GetCLSData") : TEXT("GetCLSDriver")));
        Graph->AddNode(Call, false, false);
        Call->CreateNewGuid();
        Call->PostPlacedNewNode();
        Call->AllocateDefaultPins();
        // Owner is the pilot itself; the schema supplies self through an explicit node.
        auto *Self = NewObject<UK2Node_Self>(Graph);
        Graph->AddNode(Self, false, false);
        Self->CreateNewGuid();
        Self->AllocateDefaultPins();
        if (!Connect(Self, TEXT("self"), Call, TEXT("Owner")))
            return false;
        if (Data)
        {
            auto *Cast = NewObject<UK2Node_DynamicCast>(Graph);
            Cast->TargetType = DataComponent->GeneratedClass;
            Cast->SetPurity(true);
            Graph->AddNode(Cast, false, false);
            Cast->CreateNewGuid();
            Cast->AllocateDefaultPins();
            if (!Graph->GetSchema()->TryCreateConnection(Call->GetReturnValuePin(), Cast->GetCastSourcePin()) ||
                !Graph->GetSchema()->TryCreateConnection(Cast->GetCastResultPin(),
                                                         Result->FindPin(TEXT("LocomotionComponent"))))
                return false;
        }
        else if (!Connect(Call, TEXT("ReturnValue"), Result, TEXT("DriverMesh")))
            return false;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Pilot);
    FKismetEditorUtilities::CompileBlueprint(Pilot);
    return Pilot->Status != BS_Error && DataComponent->Status != BS_Error;
#else
    return false;
#endif
}
bool UHoverIntegrationAuthoring::BuildBodyPhysics(UAnimBlueprint *Blueprint, UAnimBlueprint *Original)
{
#if WITH_EDITOR
    if (!Blueprint || !Original || !Blueprint->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")))
        return false;
    UEdGraph *Graph = nullptr;
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (auto *Candidate : Graphs)
        if (Candidate->GetFName() == TEXT("AnimGraph"))
            Graph = Candidate;
    if (!Graph)
        return false;
    UAnimGraphNode_Root *Root = nullptr;
    for (UEdGraphNode *Node : Graph->Nodes)
        if (auto *R = Cast<UAnimGraphNode_Root>(Node))
            Root = R;
    if (!Root)
        return false;
    if (Graph->Nodes.Num() != 1)
    {
        // A normal slow rendered frame can move a running character over50cm.
        // Keep the teleport reset above that while retaining bounded springs.
        for (UEdGraphNode *Node : Graph->Nodes)
            if (auto *Spring = Cast<UAnimGraphNode_SpringBone>(Node))
                Spring->Node.ErrorResetThresh = 250;
        // Existing local graph: arrange it for editing without replacing nodes.
        UEdGraphNode *Current = Root;
        int32 X = 1680;
        TSet<UEdGraphNode *> Seen;
        while (Current && !Seen.Contains(Current))
        {
            Seen.Add(Current);
            Current->NodePosX = X;
            Current->NodePosY = 0;
            X -= 240;
            UEdGraphNode *Previous = nullptr;
            for (auto *Pin : Current->Pins)
                if (Pin->Direction == EGPD_Input && Pin->PinType.PinCategory == TEXT("struct") && Pin->LinkedTo.Num())
                    Previous = Pin->LinkedTo[0]->GetOwningNode();
            Current = Previous;
        }
        FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
        FKismetEditorUtilities::CompileBlueprint(Blueprint);
        return Seen.Num() == 8;
    }
    auto *Input = AddNode<UAnimGraphNode_LinkedInputPose>(Graph);
    auto *Component = AddNode<UAnimGraphNode_LocalToComponentSpace>(Graph);
    auto *Local = AddNode<UAnimGraphNode_ComponentToLocalSpace>(Graph);
    if (!Connect(Input, TEXT("Pose"), Component, TEXT("LocalPose")))
        return false;
    UEdGraphNode *Previous = Component;
    auto *Defaults = Original->GeneratedClass->GetDefaultObject();
    for (const TCHAR *Bone : {TEXT("chest_l"), TEXT("chest_r"), TEXT("glute_l"), TEXT("glute_r")})
    {
        auto *Spring = AddNode<UAnimGraphNode_SpringBone>(Graph);
        bool Found = false;
        for (TFieldIterator<FStructProperty> It(Defaults->GetClass()); It; ++It)
            if (It->Struct == FAnimNode_SpringBone::StaticStruct())
            {
                const auto *Source = It->ContainerPtrToValuePtr<FAnimNode_SpringBone>(Defaults);
                if (Source->SpringBone.BoneName == Bone)
                {
                    Spring->Node = *Source;
                    Found = true;
                    break;
                }
            }
        if (!Found)
            return false;
        Spring->Node.ComponentPose = FComponentSpacePoseLink();
        Spring->Node.SpringStiffness = FString(Bone).StartsWith(TEXT("glute")) ? 160 : 220;
        Spring->Node.bLimitDisplacement = true;
        Spring->Node.MaxDisplacement = FString(Bone).StartsWith(TEXT("glute")) ? 6.5 : 3.5;
        Spring->Node.ErrorResetThresh = 250;
        if (!Connect(Previous, TEXT("Pose"), Spring, TEXT("ComponentPose")))
            return false;
        Previous = Spring;
    }
    if (!Connect(Previous, TEXT("Pose"), Local, TEXT("ComponentPose")) ||
        !Connect(Local, TEXT("Pose"), Root, TEXT("Result")))
        return false;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    return Blueprint->Status != BS_Error;
#else
    return false;
#endif
}
