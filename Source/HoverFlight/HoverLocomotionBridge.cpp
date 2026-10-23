#include "HoverLocomotionBridge.h"
#include "HoverPilot.h"
#include "HoverAnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Animation/AnimBlueprint.h"
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
    Driver->SetAnimInstanceClass(AnimClass);
    SetObject(Locomotion, TEXT("MeshComponent"), Driver);
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
    Driver->SetWorldTransform(Pilot->GetMesh()->GetComponentTransform());
    SetByte(Locomotion, TEXT("CurrentGait"), Pilot->GetCharacterMovement()->MaxWalkSpeed > 600 ? 1 : 0);
    // CLS Stance means Unarmed/Pistol/Rifle, not standing/crouching.
    // Crouching is selected through State.Movement.Crouch below.
    SetByte(Locomotion, TEXT("CurrentStance"), 0);
    SetByte(Locomotion, TEXT("CurrentRotationMode"), Pilot->IsAiming() ? 1 : 0);
    if (auto *Package = Locomotion->FindFunction(TEXT("Package_AnimData")))
        Locomotion->ProcessEvent(Package, nullptr);
    // Parkour keeps a camera-relative capsule for its wall traces. CLS sees the
    // rendered body's orientation, otherwise the same yaw is applied twice.
    if (auto *Data = FindFProperty<FStructProperty>(Locomotion->GetClass(), TEXT("AnimData")))
    {
        void *Value = Data->ContainerPtrToValuePtr<void>(Locomotion);
        for (TFieldIterator<FStructProperty> It(Data->Struct); It; ++It)
            if (It->GetName().StartsWith(TEXT("ActorTransform_")))
            {
                auto *Transform = It->ContainerPtrToValuePtr<FTransform>(Value);
                Transform->SetRotation((Driver->GetComponentQuat() * FRotator(0, 90, 0).Quaternion()));
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
    const float Acceleration = DT > 0 ? (Velocity - PreviousVelocity).Size() / DT : 0;
    PreviousVelocity = Velocity;
    FilteredAcceleration = FMath::FInterpTo(FilteredAcceleration, Acceleration, DT, 5);
    const float Target = !bPhysicsEnabled              ? 0
                         : Pilot && Pilot->IsMounted() ? FMath::Clamp((FilteredAcceleration - 400.f) / 1400.f, 0.f, .7f)
                                                       : 1;
    PhysicsAlpha = FMath::FInterpTo(PhysicsAlpha, Target, DT, 5);
    for (TFieldIterator<FStructProperty> It(GetClass()); It; ++It)
        if (It->Struct == FAnimNode_SpringBone::StaticStruct())
            It->ContainerPtrToValuePtr<FAnimNode_SpringBone>(this)->Alpha = PhysicsAlpha;
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
