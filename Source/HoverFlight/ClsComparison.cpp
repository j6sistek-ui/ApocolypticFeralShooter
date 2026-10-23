#include "ClsComparison.h"
#include "HoverAnimInstance.h"
#include "HoverSecondaryMotion.h"
#include "HoverLocomotionBridge.h"
#include "Animation/AnimNodeSpaceConversions.h"
#include "BoneControllers/AnimNode_ModifyBone.h"
#include "Animation/AnimInstanceProxy.h"
#include "AnimNodes/AnimNode_RetargetPoseFromMesh.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerInput.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "InputModifiers.h"
#include "InputKeyEventArgs.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"
#include "PoseSearch/AnimNode_MotionMatching.h"
#include "PoseSearch/PoseSearchDatabase.h"
#if WITH_EDITOR
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#endif

struct FClsRetargetProxy final : FAnimInstanceProxy
{
    FAnimNode_RetargetPoseFromMesh Retarget;
    FAnimNode_ConvertLocalToComponentSpace Component;
    FAnimNode_ModifyBone Springs[4];
    FAnimNode_ConvertComponentToLocalSpace Root;
    FHoverSecondaryMotion Secondary;
    explicit FClsRetargetProxy(UAnimInstance *Instance) : FAnimInstanceProxy(Instance) {}
    virtual void Initialize(UAnimInstance *Instance) override
    {
        Retarget.RetargetFrom = ERetargetSourceMode::ParentSkeletalMeshComponent;
        Retarget.IKRetargeterAsset =
            LoadObject<UIKRetargeter>(nullptr, TEXT("/Game/HoverPrototype/CLSComparison/RTG_CLS_Vexa.RTG_CLS_Vexa"));
        Component.LocalPose.SetLinkNode(&Retarget);
        const FName Names[] = {TEXT("chest_l"), TEXT("chest_r"), TEXT("glute_l"), TEXT("glute_r")};
        for (int32 I = 0; I < 4; ++I)
        {
            Springs[I].ComponentPose.SetLinkNode(I == 0 ? static_cast<FAnimNode_Base *>(&Component) : &Springs[I - 1]);
            Springs[I].BoneToModify.BoneName = Names[I];
            Springs[I].TranslationMode = BMM_Additive;
            Springs[I].TranslationSpace = BCS_ComponentSpace;
        }
        Root.ComponentPose.SetLinkNode(&Springs[3]);
        FAnimInstanceProxy::Initialize(Instance);
    }
    virtual FAnimNode_Base *GetCustomRootNode() override
    {
        return &Root;
    }
    virtual void GetCustomNodes(TArray<FAnimNode_Base *> &Nodes) override
    {
        Nodes = {&Retarget, &Component, &Springs[0], &Springs[1], &Springs[2], &Springs[3], &Root};
    }
    virtual void PreUpdate(UAnimInstance *Instance, float DT) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DT);
        auto *Character = Cast<ACharacter>(Instance->TryGetPawnOwner());
        Secondary.Update(Instance->GetSkelMeshComponent(), Character, DT, false,
                         Character && Character->GetCharacterMovement()->IsMovingOnGround());
        for (int32 I = 0; I < 4; ++I)
            Springs[I].Translation = Secondary.Offsets[I];
    }
};
FAnimInstanceProxy *UClsRetargetAnim::CreateAnimInstanceProxy()
{
    return new FClsRetargetProxy(this);
}
void UClsRetargetAnim::DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy)
{
    delete Proxy;
}

void AClsComparisonCharacter::BeginPlay()
{
    Super::BeginPlay();
    SetCanBeDamaged(false);
    for (auto *Component : GetComponents())
        if (UFunction *Apply = Component->FindFunction(TEXT("ApplyProfileSettings")))
            Component->ProcessEvent(Apply, nullptr);
    auto *Assets = LoadObject<UHoverPilotAssets>(nullptr, TEXT("/Game/HoverPrototype/DA_HoverPilot.DA_HoverPilot"));
    if (!Assets || Assets->BodyParts.IsEmpty())
        return;
    GetMesh()->SetHiddenInGame(true, false);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    for (int32 I = 0; I < Assets->BodyParts.Num(); ++I)
    {
        const auto &Part = Assets->BodyParts[I];
        // CharacterMesh0 is already the mannequin driver. Never reuse its name:
        // NewObject with that name can replace it and make retargeting self-referential.
        auto *PartMesh = NewObject<USkeletalMeshComponent>(this, FName(TEXT("Vexa_") + Part.Name.ToString()));
        PartMesh->SetupAttachment(I == 0 ? GetMesh() : Vexa.Get());
        PartMesh->SetSkeletalMesh(Part.Mesh);
        PartMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        PartMesh->bCastContactShadow = true;
        PartMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        if (Part.PhysicsOverride)
            PartMesh->SetPhysicsAsset(Part.PhysicsOverride);
        for (int32 M = 0; M < Part.Materials.Num(); ++M)
            PartMesh->SetMaterial(M, Part.Materials[M]);
        for (const auto &Morph : Part.Morphs)
            PartMesh->SetMorphTarget(Morph.Key, Morph.Value);
        PartMesh->RegisterComponent();
        if (I == 0)
        {
            Vexa = PartMesh;
            PartMesh->AddTickPrerequisiteComponent(GetMesh());
            PartMesh->SetAnimInstanceClass(UClsRetargetAnim::StaticClass());
        }
        else if (PartMesh->GetBoneIndex(TEXT("afs_chain_01")) != INDEX_NONE)
        {
            PartMesh->AddTickPrerequisiteComponent(Vexa);
            PartMesh->SetAnimInstanceClass(UHoverAccessoryAnimInstance::StaticClass());
        }
        else
            PartMesh->SetLeaderPoseComponent(Vexa);
        Parts.Add(PartMesh);
    }
    // Match the current third-person AFS framing, without changing the vendor movement graph.
    TArray<USpringArmComponent *> Arms;
    GetComponents(Arms);
    for (auto *Arm : Arms)
    {
        Arm->TargetArmLength = 430;
        Arm->SocketOffset = FVector(0, 40, 15);
        Arm->bUsePawnControlRotation = true;
    }
    UE_LOG(LogTemp, Display, TEXT("CLS_COMPARISON_READY Vexa parts=%d"), Parts.Num());
}

bool AClsComparisonController::IsCLSMode() const
{
    return Cast<AClsComparisonCharacter>(GetPawn()) != nullptr;
}
void AClsComparisonController::PlayerTick(float DT)
{
    // The legacy vehicle controller recognizes a vendor exit pawn by its class.
    // A comparison pawn is intentional and must not be replaced by that exit handler.
    if (IsCLSMode())
        APlayerController::PlayerTick(DT);
    else
        Super::PlayerTick(DT);
}
bool AClsComparisonController::InputKey(const FInputKeyEventArgs &Params)
{
#if WITH_EDITOR
    if (bTestInputOnly && !bInjectingTestKey)
        return false;
#endif
    if (!IsGraphicsMenuOpen() && Params.Event == IE_Pressed &&
        (Params.Key == EKeys::F7 || Params.Key == EKeys::Gamepad_DPad_Right))
    {
        CompareLocomotion();
        return true;
    }
    return Super::InputKey(Params);
}
void AClsComparisonController::SetCLSMappings(bool Enabled)
{
    auto *Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer());
    if (!Subsystem)
        return;
    if (!ComparisonMappings)
        ComparisonMappings = LoadObject<UInputMappingContext>(
            nullptr, TEXT("/Game/HoverPrototype/CLSComparison/IMC_CLSComparison.IMC_CLSComparison"));
    if (!ComparisonMappings)
        return;
    if (Enabled)
        Subsystem->AddMappingContext(ComparisonMappings, 50);
    else
        Subsystem->RemoveMappingContext(ComparisonMappings);
}
void AClsComparisonController::CompareLocomotion()
{
    auto *Current = Cast<ACharacter>(GetPawn());
    if (!Current || Current->GetCharacterMovement()->IsFalling() || IsGraphicsMenuOpen())
        return;
    const bool ToCLS = !IsCLSMode();
    if (ToCLS)
    {
        Before = Cast<AHoverPilot>(Current);
        if (!Before || Before->IsMounted())
            return;
    }
    const FVector FootLocation =
        Current->GetActorLocation() - FVector(0, 0, Current->GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    FRotator View = GetControlRotation();
    if (ToCLS && !After)
    {
        UClass *Class = LoadClass<AClsComparisonCharacter>(
            nullptr, TEXT("/Game/HoverPrototype/CLSComparison/BP_CLS_Vexa.BP_CLS_Vexa_C"));
        if (!Class)
            return;
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        After = GetWorld()->SpawnActor<AClsComparisonCharacter>(Class, Current->GetActorLocation(),
                                                                Current->GetActorRotation(), Params);
        if (!After)
            return;
    }
    ACharacter *Next = ToCLS ? static_cast<ACharacter *>(After.Get()) : Before.Get();
    if (!Next)
        return;
    Current->GetCharacterMovement()->StopMovementImmediately();
    Current->SetActorHiddenInGame(true);
    Current->SetActorEnableCollision(false);
    Current->SetActorTickEnabled(false);
    Current->GetCharacterMovement()->SetComponentTickEnabled(false);
    for (auto *Component : Current->GetComponents())
        Component->SetComponentTickEnabled(false);
    Next->SetActorLocationAndRotation(FootLocation +
                                          FVector(0, 0, Next->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()),
                                      FRotator(0, View.Yaw, 0), false, nullptr, ETeleportType::TeleportPhysics);
    Next->SetActorHiddenInGame(false);
    Next->SetActorEnableCollision(true);
    Next->SetActorTickEnabled(true);
    for (auto *Component : Next->GetComponents())
        Component->SetComponentTickEnabled(true);
    Next->GetCharacterMovement()->StopMovementImmediately();
    Next->GetCharacterMovement()->SetMovementMode(MOVE_Walking);
    Possess(Next);
    SetControlRotation(View);
    SetCLSMappings(ToCLS);
    if (PlayerInput)
        PlayerInput->FlushPressedKeys();
    UE_LOG(LogTemp, Display, TEXT("CLS_COMPARISON mode=%s"), ToCLS ? TEXT("CLS_MM") : TEXT("PARKOUR"));
}
void AClsComparisonHUD::DrawHUD()
{
    auto *PC = Cast<AClsComparisonController>(GetOwningPlayerController());
    if (!PC || !PC->IsCLSMode())
        Super::DrawHUD();
    if (!PC || !Canvas)
        return;
    DrawRect(FLinearColor(0, 0, 0, .8f), 20, 16, 650, 78);
    DrawText(PC->IsCLSMode() ? TEXT("B: CLS_MM / Vexa live retarget") : TEXT("A: Current Parkour / Vexa"),
             FLinearColor::White, 32, 24, nullptr, 1.25f);
    DrawText(TEXT("D-pad RIGHT / F7: switch while grounded. Locomotion comparison only."), FLinearColor::White, 32, 53,
             nullptr, 1.f);
}
AClsComparisonGameMode::AClsComparisonGameMode()
{
    PlayerControllerClass = AClsComparisonController::StaticClass();
    HUDClass = AClsComparisonHUD::StaticClass();
}

bool UClsComparisonAuthoring::ConfigureCharacter(UBlueprint *Blueprint, UObject *Profile)
{
#if WITH_EDITOR
    if (!Blueprint || !Profile || !Blueprint->SimpleConstructionScript)
        return false;
    bool Found = false;
    for (auto *Node : Blueprint->SimpleConstructionScript->GetAllNodes())
    {
        auto *Component = Node->ComponentTemplate.Get();
        if (auto *P = FindFProperty<FObjectProperty>(Component->GetClass(), TEXT("ActiveProfile")))
        {
            P->SetObjectPropertyValue_InContainer(Component, Profile);
            Found = true;
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    return Found && Blueprint->Status != BS_Error;
#else
    return false;
#endif
}
void AClsComparisonGameMode::InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);
    DefaultPawnClass =
        LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Parkour/BP_AFS_ParkourPilot.BP_AFS_ParkourPilot_C"));
}
FString UClsComparisonAuthoring::MotionMatchingResult(ACharacter *Character)
{
    if (!Character)
        return TEXT("no_animation");
    auto *Driver = UHoverIntegrationAuthoring::GetCLSDriver(Character);
    auto *Anim = (Driver ? Driver : Character->GetMesh())->GetAnimInstance();
    if (!Anim)
        return TEXT("no_animation");
    for (TFieldIterator<FStructProperty> It(Anim->GetClass()); It; ++It)
    {
        if (It->Struct == FAnimNode_MotionMatching::StaticStruct())
        {
            const auto *Node = It->ContainerPtrToValuePtr<FAnimNode_MotionMatching>(Anim);
            const auto &Result = Node->GetMotionMatchingState().SearchResult;
            return FString::Printf(TEXT("%s|%s|%.4f|%.4f"), *GetPathNameSafe(Result.SelectedAnim),
                                   *GetPathNameSafe(Result.SelectedDatabase), Result.SelectedTime, Result.SearchCost);
        }
    }
    return TEXT("no_motion_matching_node");
}

bool UClsComparisonAuthoring::BuildMappings(UInputMappingContext *Mappings)
{
    if (!Mappings)
        return false;
    Mappings->UnmapAll();
    auto Action = [](const TCHAR *Name) {
        return LoadObject<UInputAction>(nullptr,
                                        *FString::Printf(TEXT("/Game/CLS/Example/Input/Actions/%s.%s"), Name, Name));
    };
    auto *Move = Action(TEXT("IA_Move"));
    auto *Look = Action(TEXT("IA_Look"));
    if (!Move || !Look)
        return false;
    Mappings->MapKey(Move, EKeys::Gamepad_Left2D);
    for (const FKey Key : {EKeys::W, EKeys::S, EKeys::A, EKeys::D})
    {
        auto &Map = Mappings->MapKey(Move, Key);
        if (Key == EKeys::S || Key == EKeys::A)
            Map.Modifiers.Add(NewObject<UInputModifierNegate>(Mappings));
        if (Key == EKeys::W || Key == EKeys::S)
        {
            auto *Swizzle = NewObject<UInputModifierSwizzleAxis>(Mappings);
            Swizzle->Order = EInputAxisSwizzle::YXZ;
            Map.Modifiers.Add(Swizzle);
        }
    }
    auto &LookMap = Mappings->MapKey(Look, EKeys::Gamepad_Right2D);
    auto *LookScale = NewObject<UInputModifierScalar>(Mappings);
    LookScale->Scalar = FVector(48, -36, 1);
    LookMap.Modifiers.Add(LookScale);
    LookMap.Modifiers.Add(NewObject<UInputModifierScaleByDeltaTime>(Mappings));
    Mappings->MapKey(Action(TEXT("IA_MouseLook")), EKeys::Mouse2D);
    for (const FKey Key : {EKeys::SpaceBar, EKeys::Gamepad_FaceButton_Bottom})
        Mappings->MapKey(Action(TEXT("IA_Jump")), Key);
    for (const FKey Key : {EKeys::LeftShift, EKeys::Gamepad_LeftThumbstick})
        Mappings->MapKey(Action(TEXT("IA_Sprint")), Key);
    for (const FKey Key : {EKeys::LeftControl, EKeys::Gamepad_FaceButton_Right})
        Mappings->MapKey(Action(TEXT("AI_Crouch")), Key);
    return true;
}
