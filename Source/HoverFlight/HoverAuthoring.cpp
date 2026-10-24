#include "HoverAuthoring.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "HoverTestController.h"
#include "HoverPilot.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Inventory/ZE_AmmoDefinition.h"
#include "GameFramework/PlayerInput.h"
#include "Engine/Blueprint.h"
#include "UObject/UnrealType.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"
#include "UnrealClient.h"
#include "Misc/App.h"
#if WITH_EDITOR
#include "NiagaraSystem.h"
#include "Animation/BlendSpace.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraScript.h"
#include "NiagaraSpriteRendererProperties.h"
#include "NiagaraComponent.h"
#include "NiagaraSystemInstanceController.h"
#include "NiagaraSystemInstance.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraDataSet.h"
#include "UObject/UObjectIterator.h"
#include "AssetCompilingManager.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Editor.h"
#include "Engine/GameViewportClient.h"
#include "ImageUtils.h"
#include "ImageCore.h"
#include "Misc/FileHelper.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Texture2D.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Editor/EditorPerformanceSettings.h"
#include "Serialization/ArchiveReplaceObjectRef.h"
#include "VirtualTexturingEditorModule.h"
#include "Materials/Material.h"
#include "PlayInEditorDataTypes.h"
#include "Settings/LevelEditorPlaySettings.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "K2Node_Event.h"
#include "K2Node_InputKey.h"
#include "K2Node_InputAxisEvent.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_CallFunction.h"
#include "NavMesh/NavMeshBoundsVolume.h"
#include "NavMesh/RecastNavMesh.h"
#include "NavigationSystem.h"
#include "Builders/CubeBuilder.h"
#include "ActorFactories/ActorFactory.h"
#include "Components/BrushComponent.h"
#include "EdGraphSchema_K2.h"
#include "PhysicsAssetUtils.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "WorldPartition/WorldPartition.h"
#endif

bool UHoverAuthoring::ConfigureCityStartingGear(UZE_WaveGameModeSettings *Settings)
{
#if WITH_EDITOR
    if (!Settings || !Settings->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/")))
        return false;
    auto *Weapon = LoadObject<UZE_WeaponDefinition>(
        nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_AFS_Ballista.DA_AFS_Ballista"));
    auto *Ammo = LoadObject<UZE_AmmoDefinition>(nullptr, TEXT("/Game/ZESP/ZE/Data/Ammo/DA_AMMO_M16.DA_AMMO_M16"));
    if (!Weapon || !Ammo)
        return false;
    Settings->Modify();
    auto &Gear = Settings->StartingEquipment;
    FZE_StartingWeaponConfig Slot;
    Slot.WeaponDefinition = Weapon;
    Slot.bAddToQuickbar = true;
    Slot.QuickbarSlot = 1;
    Gear.StartingWeapons = {Slot};
    Gear.StartingAmmo = {Ammo};
    Gear.AmmoQuantity = 120;
    Gear.StartingGold = 500;
    Gear.GrenadeCount = 0;
    Settings->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

AActor *UHoverAuthoring::SpawnPlaytestActor(TSubclassOf<AActor> ActorClass, FTransform Transform)
{
#if WITH_EDITOR
    if (auto *World = GetPlaytestWorld(); World && ActorClass)
    {
        FActorSpawnParameters Params;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        return World->SpawnActor<AActor>(ActorClass, Transform, Params);
    }
#endif
    return nullptr;
}

bool UHoverAuthoring::SetCyberZombieSkeleton(USkeletalMesh *Mesh, USkeleton *Skeleton)
{
#if WITH_EDITOR
    if (!Mesh || !Skeleton || !Mesh->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/")) ||
        !Skeleton->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/")))
        return false;
    for (int32 Bone = 0; Bone < Mesh->GetRefSkeleton().GetNum(); ++Bone)
        if (Skeleton->GetReferenceSkeleton().FindBoneIndex(Mesh->GetRefSkeleton().GetBoneName(Bone)) == INDEX_NONE)
            return false;
    Mesh->Modify();
    Mesh->SetSkeleton(Skeleton);
    Mesh->PostEditChange();
    Mesh->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

bool UHoverAuthoring::ConfigureVariantSkeleton(USkeletalMesh *Mesh, USkeleton *AnimationSkeleton)
{
#if WITH_EDITOR
    if (!Mesh || !AnimationSkeleton ||
        !Mesh->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/Variants/")))
        return false;
    USkeleton *Skeleton = Mesh->GetSkeleton();
    if (!Skeleton)
        return false;
    Skeleton->Modify();
    Skeleton->UpdateReferencePoseFromMesh(Mesh);
    Skeleton->AddCompatibleSkeleton(AnimationSkeleton);
    Skeleton->SetBoneTranslationRetargetingMode(0, EBoneTranslationRetargetingMode::Skeleton, true);
    Skeleton->SetBoneTranslationRetargetingMode(0, EBoneTranslationRetargetingMode::Animation);
    const int32 Pelvis = Skeleton->GetReferenceSkeleton().FindBoneIndex(TEXT("pelvis"));
    if (Pelvis == INDEX_NONE)
        return false;
    Skeleton->SetBoneTranslationRetargetingMode(Pelvis, EBoneTranslationRetargetingMode::AnimationScaled);
    Skeleton->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

UObject *UHoverAuthoring::GetLocalAnimationController(UAnimSequence *Sequence)
{
#if WITH_EDITOR
    if (Sequence && Sequence->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")))
        return Cast<UObject>(&Sequence->GetController());
#endif
    return nullptr;
}

UPhysicsAsset *UHoverAuthoring::CreateVariantPhysics(USkeletalMesh *Mesh)
{
#if WITH_EDITOR
    if (!Mesh || !Mesh->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/Variants/")))
        return nullptr;
    const FString Name = TEXT("PA_") + Mesh->GetName().RightChop(3);
    const FString Path = FPackageName::GetLongPackagePath(Mesh->GetOutermost()->GetName()) / Name;
    if (auto *Existing = LoadObject<UPhysicsAsset>(nullptr, *(Path + TEXT(".") + Name)))
        return Existing;
    auto *Asset = NewObject<UPhysicsAsset>(CreatePackage(*Path), *Name, RF_Public | RF_Standalone);
    FPhysAssetCreateParams Params;
    Params.MinBoneSize = 3.f;
    FText Error;
    if (!FPhysicsAssetUtils::CreateFromSkeletalMesh(Asset, Mesh, Params, Error, true, false))
    {
        UE_LOG(LogTemp, Error, TEXT("Variant collision: %s"), *Error.ToString());
        return nullptr;
    }
    FAssetRegistryModule::AssetCreated(Asset);
    Asset->MarkPackageDirty();
    Mesh->MarkPackageDirty();
    return Asset;
#else
    return nullptr;
#endif
}

bool UHoverAuthoring::AddCityNavigation(UWorld *World, FVector Center, FVector Size)
{
#if WITH_EDITOR
    if (!World || !(World->GetName().Contains(TEXT("CyberCity")) || World->GetName() == TEXT("L_Showcase")))
        return false;
    ANavMeshBoundsVolume *Bounds = nullptr;
    for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
        if (It->ActorHasTag(TEXT("AFS_CityNavigation")))
            Bounds = *It;
    if (!Bounds)
        if (auto *Factory = GEditor->FindActorFactoryForActorClass(ANavMeshBoundsVolume::StaticClass()))
            Bounds =
                Cast<ANavMeshBoundsVolume>(Factory->CreateActor(nullptr, World->GetCurrentLevel(), FTransform(Center)));
    if (!Bounds)
        return false;
    Bounds->Tags.AddUnique(TEXT("AFS_CityNavigation"));
    Bounds->SetActorLabel(TEXT("AFS Horde Navigation"));
    auto *Builder = NewObject<UCubeBuilder>();
    Builder->X = Size.X;
    Builder->Y = Size.Y;
    Builder->Z = Size.Z;
    if (!Builder->Build(World, Bounds))
        return false;
    Bounds->GetBrushComponent()->BuildSimpleBrushCollision();
    Bounds->GetBrushComponent()->UpdateBounds();
    Bounds->PostEditMove(true);
    Bounds->SetActorLocation(Center);
    if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World))
    {
        // A navigation system created after a partitioned map loads can retain
        // its async-load lock. Finish loading before this explicit authoring build.
        FlushAsyncLoading();
        Navigation->RemoveNavigationBuildLock(ENavigationBuildLock::AsyncLoadLock,
                                              UNavigationSystemV1::ELockRemovalRebuildAction::NoRebuild);
        Navigation->OnNavigationBoundsUpdated(Bounds);
        Navigation->GetDefaultNavDataInstance(FNavigationSystem::Create);
        Navigation->Build();
    }
    for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
        if (auto *Property = FindFProperty<FEnumProperty>(It->GetClass(), TEXT("RuntimeGeneration")))
            Property->GetUnderlyingProperty()->SetIntPropertyValue(Property->ContainerPtrToValuePtr<void>(*It),
                                                                   static_cast<int64>(ERuntimeGenerationType::Dynamic));
    return true;
#else
    return false;
#endif
}

FString UHoverAuthoring::DescribePartitionNavigation(UWorld *World, bool EnableLakesideStreaming)
{
#if WITH_EDITOR
    if (World)
        if (auto *Partition = World->GetWorldPartition())
        {
            const bool WasStreaming = Partition->IsStreamingEnabled();
            FString NavigationState;
            if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World))
                NavigationState = FString::Printf(TEXT(" MainNavData=%s BuildLocked=%d"),
                                                  *GetNameSafe(Navigation->GetDefaultNavDataInstance()),
                                                  Navigation->IsNavigationBuildingLocked());
            for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
                NavigationState +=
                    FString::Printf(TEXT(" Recast=%s ActiveTiles=%d"), *It->GetName(), It->GetNumActiveTiles());
            if (EnableLakesideStreaming && !WasStreaming && !World->IsGameWorld() &&
                World->GetOutermost()->GetName() == TEXT("/Game/Chinese_Lakeside_Town/Levels/L_Showcase"))
            {
                Partition->Modify();
                Partition->SetEnableStreaming(true);
                World->MarkPackageDirty();
            }
            return FString::Printf(TEXT("StreamingBefore=%d Streaming=%d EditorBounds=%s RuntimeBounds=%s%s"),
                                   WasStreaming, Partition->IsStreamingEnabled(),
                                   *Partition->GetEditorWorldBounds().ToString(),
                                   *Partition->GetRuntimeWorldBounds().ToString(), *NavigationState);
        }
#endif
    return TEXT("No partition");
}

TArray<FVector> UHoverAuthoring::FindCompleteCityPath(UWorld *World, FVector Start, FVector End)
{
    TArray<FVector> Points;
#if WITH_EDITOR
    if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World))
        if (auto *Data = Navigation->GetDefaultNavDataInstance(FNavigationSystem::DontCreate))
        {
            FNavLocation From, To;
            if (Navigation->ProjectPointToNavigation(Start, From, FVector(400, 400, 600)) &&
                Navigation->ProjectPointToNavigation(End, To, FVector(400, 400, 600)))
            {
                FPathFindingQuery Query(nullptr, *Data, From.Location, To.Location);
                Query.SetAllowPartialPaths(false);
                auto Result = Navigation->FindPathSync(Query);
                if (Result.IsSuccessful() && Result.Path.IsValid() && !Result.Path->IsPartial())
                    for (const auto &Point : Result.Path->GetPathPoints())
                        Points.Add(Point.Location);
            }
        }
#endif
    return Points;
}

bool UHoverAuthoring::BuildRideBlend(UBlendSpace *Blend, const TArray<UAnimSequence *> &Clips,
                                     const TArray<FVector> &Coordinates)
{
#if WITH_EDITOR
    if (!Blend || !Blend->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")) || Clips.Num() != Coordinates.Num())
        return false;
    Blend->Modify();
    if (Clips.IsEmpty() || !Clips[0])
        return false;
    Blend->SetSkeleton(Clips[0]->GetSkeleton());
    while (Blend->GetNumberOfBlendSamples())
        Blend->DeleteSample(Blend->GetNumberOfBlendSamples() - 1);
    auto *Property = FindFProperty<FStructProperty>(Blend->GetClass(), TEXT("BlendParameters"));
    if (!Property)
        return false;
    for (int32 I = 0; I < 2; ++I)
    {
        auto *Parameter = Property->ContainerPtrToValuePtr<FBlendParameter>(Blend, I);
        Parameter->DisplayName = I == 0 ? TEXT("Turn") : TEXT("Forward / reverse");
        Parameter->Min = -1;
        Parameter->Max = 1;
        Parameter->GridNum = 2;
        Parameter->bSnapToGrid = false;
    }
    for (int32 I = 0; I < Clips.Num(); ++I)
        if (!Clips[I] || Blend->AddSample(Clips[I], Coordinates[I]) == INDEX_NONE)
            return false;
    Blend->TargetWeightInterpolationSpeedPerSec = 5;
    Blend->ValidateSampleData();
    Blend->ResampleData();
    Blend->PostEditChange();
    Blend->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

bool UHoverAuthoring::IntegrateParkourBlueprint(UBlueprint *Blueprint)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Parkour/")))
        return false;
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
    {
        const auto OriginalNodes = Graph->Nodes;
        for (UEdGraphNode *Node : OriginalNodes)
        {
            auto *Event = Cast<UK2Node_Event>(Node);
            const bool GateEvent = Event && Event->EventReference.GetMemberName() != TEXT("ReceiveBeginPlay");
            if (!GateEvent && !Node->IsA<UK2Node_InputKey>() && !Node->IsA<UK2Node_InputAxisEvent>())
                continue;
            for (auto *Pin : Node->Pins)
            {
                if (Pin->Direction != EGPD_Output || Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec ||
                    Pin->LinkedTo.IsEmpty())
                    continue;
                FGraphNodeCreator<UK2Node_CallFunction> CallCreator(*Graph);
                auto *Call = CallCreator.CreateNode();
                Call->SetFromFunction(
                    AHoverPilot::StaticClass()->FindFunctionByName(GET_FUNCTION_NAME_CHECKED(AHoverPilot, IsOnFoot)));
                CallCreator.Finalize();
                FGraphNodeCreator<UK2Node_IfThenElse> BranchCreator(*Graph);
                auto *Branch = BranchCreator.CreateNode();
                BranchCreator.Finalize();
                const auto Links = Pin->LinkedTo;
                Pin->BreakAllPinLinks();
                Pin->MakeLinkTo(Branch->GetExecPin());
                Call->GetReturnValuePin()->MakeLinkTo(Branch->GetConditionPin());
                for (auto *Link : Links)
                    Branch->GetThenPin()->MakeLinkTo(Link);
                Branch->NodePosX = Node->NodePosX + 220;
                Branch->NodePosY = Node->NodePosY;
                Call->NodePosX = Branch->NodePosX;
                Call->NodePosY = Branch->NodePosY + 160;
            }
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    return Blueprint->Status != BS_Error;
#else
    return false;
#endif
}

bool UHoverAuthoring::RepairParkourTransitions(UBlueprint *Blueprint)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")))
        return false;
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (auto *Graph : Graphs)
    {
        const auto Nodes = Graph->Nodes;
        for (UEdGraphNode *Node : Nodes)
        {
            if (auto *Debug = Node->FindPin(TEXT("DrawDebugType")))
            {
                Debug->BreakAllPinLinks();
                Debug->DefaultValue = TEXT("None");
            }
            auto *Key = Cast<UK2Node_InputKey>(Node);
            if (!Key || Key->InputKey != EKeys::LeftShift)
                continue;
            for (const TCHAR *Event : {TEXT("Pressed"), TEXT("Released")})
            {
                auto *Pin = Key->FindPin(Event);
                if (!Pin)
                    continue;
                Pin->BreakAllPinLinks();
                FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);
                auto *Call = Creator.CreateNode();
                Call->SetFromFunction(AHoverPilot::StaticClass()->FindFunctionByName(
                    GET_FUNCTION_NAME_CHECKED(AHoverPilot, SetParkourCrouch)));
                Creator.Finalize();
                Call->FindPin(TEXT("Held"))->DefaultValue =
                    FString(Event) == TEXT("Pressed") ? TEXT("true") : TEXT("false");
                Pin->MakeLinkTo(Call->GetExecPin());
            }
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    return Blueprint->Status != BS_Error;
#else
    return false;
#endif
}

FString UHoverAuthoring::DescribeBlueprint(UBlueprint *Blueprint)
{
    FString Result;
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GeneratedClass)
        return TEXT("No generated class");
    UObject *Defaults = Blueprint->GeneratedClass->GetDefaultObject();
    for (TFieldIterator<FProperty> It(Blueprint->GeneratedClass); It; ++It)
    {
        if (!It->GetOwnerClass()->ClassGeneratedBy)
            continue;
        FString Value;
        It->ExportText_InContainer(0, Value, Defaults, Defaults, Defaults, PPF_None);
        Result += FString::Printf(TEXT("PROPERTY %s %s = %s\n"), *It->GetCPPType(), *It->GetName(), *Value.Left(500));
    }
    for (TFieldIterator<UFunction> It(Blueprint->GeneratedClass); It; ++It)
    {
        if (!It->GetOwnerClass()->ClassGeneratedBy)
            continue;
        Result += FString::Printf(TEXT("FUNCTION %s("), *It->GetName());
        for (TFieldIterator<FProperty> Param(*It); Param && (Param->PropertyFlags & CPF_Parm); ++Param)
            Result += Param->GetCPPType() + TEXT(" ") + Param->GetName() + TEXT(", ");
        Result += TEXT(")\n");
    }
    TArray<UEdGraph *> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    for (const auto *Graph : Graphs)
    {
        Result += TEXT("GRAPH ") + Graph->GetName() + TEXT("\n");
        for (const UEdGraphNode *Node : Graph->Nodes)
        {
            Result += TEXT("NODE ") + Node->GetName() + TEXT(" ") +
                      Node->GetNodeTitle(ENodeTitleType::FullTitle).ToString() + TEXT("\n");
            for (const auto *Pin : Node->Pins)
            {
                Result += TEXT("  ") + Pin->PinName.ToString() + TEXT("=") + Pin->DefaultValue;
                if (Pin->DefaultObject)
                    Result += TEXT(" [") + Pin->DefaultObject->GetPathName() + TEXT("]");
                for (const auto *Link : Pin->LinkedTo)
                    Result += TEXT(" -> ") + Link->GetOwningNode()->GetName() + TEXT(".") + Link->PinName.ToString();
                Result += TEXT("\n");
            }
        }
    }
#endif
    return Result;
}

void UHoverAuthoring::StartPlaytest()
{
#if WITH_EDITOR
    if (!GEditor || GEditor->PlayWorld)
        return;
    GetMutableDefault<UEditorPerformanceSettings>()->bThrottleCPUWhenNotForeground = false;
    FRequestPlaySessionParams Params;
    auto *Settings = GetMutableDefault<ULevelEditorPlaySettings>();
    Settings->NewWindowWidth = 1280;
    Settings->NewWindowHeight = 720;
    Params.EditorPlaySettings = Settings;
    Params.bAllowOnlineSubsystem = false;
    GEditor->RequestPlaySession(Params);
#endif
}

UWorld *UHoverAuthoring::GetPlaytestWorld()
{
#if WITH_EDITOR
    return GEditor ? GEditor->PlayWorld : nullptr;
#else
    return nullptr;
#endif
}

void UHoverAuthoring::TestKey(APlayerController *Controller, FName Key, float Value, bool bAnalog)
{
#if WITH_EDITOR
    // A held physical button emits one press edge. Replaying Pressed each frame
    // restarts Blueprint slide timelines and can compound capsule scaling.
    auto *TestController = Cast<AHoverTestController>(Controller);
    if (TestController && !bAnalog)
    {
        // Consumed menu/crouch buttons never enter PlayerInput's held-key map.
        // Track injected edges independently so their release is still delivered.
        if (TestController->TestHeldKeys.Contains(Key) == (Value > 0))
            return;
        if (Value > 0)
            TestController->TestHeldKeys.Add(Key);
        else
            TestController->TestHeldKeys.Remove(Key);
    }
    if (TestController)
        TestController->bInjectingTestKey = true;
    if (Controller)
        Controller->InputKey(FInputKeyEventArgs(nullptr, FInputDeviceId::CreateFromInternalId(0), FKey(Key),
                                                bAnalog ? IE_Axis : (Value > 0 ? IE_Pressed : IE_Released), Value,
                                                false, FPlatformTime::Cycles64()));
    if (TestController)
        TestController->bInjectingTestKey = false;
#endif
}

void UHoverAuthoring::IsolateTestInput(APlayerController *Controller)
{
#if WITH_EDITOR
    if (auto *PC = Cast<AHoverTestController>(Controller))
    {
        PC->bTestInputOnly = true;
        PC->TestHeldKeys.Reset();
        if (PC->PlayerInput)
            PC->PlayerInput->FlushPressedKeys();
    }
#endif
}

void UHoverAuthoring::SetPlaytestFixedStep(bool bEnabled)
{
#if WITH_EDITOR
    FApp::SetFixedDeltaTime(1.0 / 30.0);
    FApp::SetUseFixedTimeStep(bEnabled);
#endif
}

AActor *UHoverAuthoring::SpawnTestPlatform(FVector Location)
{
#if WITH_EDITOR
    if (UWorld *World = GetPlaytestWorld())
    {
        AStaticMeshActor *Platform = World->SpawnActor<AStaticMeshActor>(Location, FRotator::ZeroRotator);
        Platform->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
        Platform->GetStaticMeshComponent()->SetStaticMesh(
            LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
        Platform->SetActorScale3D(FVector(14, 14, 1));
        Platform->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
        return Platform;
    }
#endif
    return nullptr;
}

TArray<FVector> UHoverAuthoring::FindLightingReviewLocations(UWorld *World, FVector Origin)
{
    TArray<FVector> Result;
#if WITH_EDITOR
    if (!World)
        return Result;
    TActorIterator<ADirectionalLight> Sun(World);
    if (!Sun)
        return Result;
    const FVector ToSun = -Sun->GetActorForwardVector();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(LightingReview));
    if (auto *PC = World->GetFirstPlayerController())
        Params.AddIgnoredActor(PC->GetPawn());
    FVector Locations[2];
    bool Found[2] = {false, false};
    for (float Distance : {0.f, 350.f, 700.f, 1100.f, 1600.f, 2400.f, 3200.f})
        for (int32 I = 0; I < 16; ++I)
        {
            const FVector Point =
                Origin + FVector(FMath::Cos(I * PI / 8) * Distance, FMath::Sin(I * PI / 8) * Distance, 0);
            FHitResult Floor, Shade;
            if (!World->LineTraceSingleByChannel(Floor, Point + FVector(0, 0, 300), Point - FVector(0, 0, 2500),
                                                 ECC_Visibility, Params) ||
                Floor.ImpactNormal.Z < .8f)
                continue;
            const FVector Location = Floor.ImpactPoint + FVector(0, 0, 105);
            if (World->OverlapBlockingTestByChannel(Location, FQuat::Identity, ECC_Pawn,
                                                    FCollisionShape::MakeCapsule(35, 100), Params))
                continue;
            const FVector Start = Location + FVector(0, 0, 50);
            const int32 Index =
                World->LineTraceSingleByChannel(Shade, Start, Start + ToSun * 10000, ECC_Visibility, Params) ? 1 : 0;
            if (!Found[Index])
            {
                Locations[Index] = Location;
                Found[Index] = true;
            }
            if (Found[0] && Found[1])
                return {Locations[0], Locations[1]};
        }
#endif
    return Result;
}

FString UHoverAuthoring::DescribeNiagaraEffect(UNiagaraSystem *Effect)
{
    FString Report;
#if WITH_EDITOR
    if (!Effect)
        return Report;
    auto DescribeStore = [&Report](const FNiagaraParameterStore &Store) {
        TArray<FNiagaraVariable> Variables;
        Store.GetParameters(Variables);
        for (const auto &Variable : Variables)
        {
            Report += Variable.GetName().ToString() + TEXT(" ") + Variable.GetType().GetName();
            if (Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
                Report += FString::Printf(TEXT(" = %.4f"), Store.GetParameterValue<float>(Variable));
            else if (Variable.GetType() == FNiagaraTypeDefinition::GetColorDef())
                Report += TEXT(" = ") + Store.GetParameterValue<FLinearColor>(Variable).ToString();
            else if (Variable.GetType() == FNiagaraTypeDefinition::GetIntDef())
                Report += FString::Printf(TEXT(" = %d"), Store.GetParameterValue<int32>(Variable));
            else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec3Def())
                Report += TEXT(" = ") + Store.GetParameterValue<FVector3f>(Variable).ToString();
            Report += TEXT("\n");
        }
    };
    DescribeStore(Effect->GetExposedParameters());
    for (auto &Handle : Effect->GetEmitterHandles())
        if (auto *Data = Handle.GetEmitterData())
        {
            Report += TEXT("EMITTER ") + Handle.GetName().ToString() + TEXT("\n");
            TArray<UNiagaraScript *> Scripts;
            Data->GetScripts(Scripts);
            for (auto *Script : Scripts)
                DescribeStore(Script->RapidIterationParameters);
        }
#endif
    return Report;
}

FString UHoverAuthoring::ConfigurePrototypeEffect(UNiagaraSystem *Effect, float SpriteScale, bool LocalSpace)
{
    FString Report;
#if WITH_EDITOR
    // Restrict authoring to our duplicates; vendor systems must remain unchanged.
    if (!Effect || !Effect->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/")))
        return TEXT("Refused: only local prototype effect copies may be edited");
    Effect->Modify();
    TArray<FNiagaraVariable> Exposed;
    Effect->GetExposedParameters().GetParameters(Exposed);
    for (const auto &Variable : Exposed)
        Report += TEXT("USER ") + Variable.GetName().ToString() + TEXT(" ") + Variable.GetType().GetName() + TEXT("\n");
    for (auto &Handle : Effect->GetEmitterHandles())
    {
        auto *Data = Handle.GetEmitterData();
        if (!Data)
            continue;
        Data->bLocalSpace = LocalSpace;
        TArray<UNiagaraScript *> Scripts;
        Data->GetScripts(Scripts);
        for (auto *Script : Scripts)
        {
            auto &Store = Script->RapidIterationParameters;
            TArray<FNiagaraVariable> Variables;
            Store.GetParameters(Variables);
            for (const auto &Variable : Variables)
            {
                const FString Name = Variable.GetName().ToString();
                // Muzzle sprites must stay on the measured barrel tip. The purchased
                // source's camera offset moves them a metre toward the viewer.
                if (Effect->GetName().StartsWith(TEXT("NS_BallistaMuzzle")) &&
                    Name.EndsWith(TEXT("CameraOffset.Camera Offset Amount")) &&
                    Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
                {
                    Script->Modify();
                    const float Old = Store.GetParameterValue<float>(Variable);
                    Store.SetParameterValue(0.f, Variable);
                    Report += FString::Printf(TEXT("%s %.3f -> 0.000\n"), *Name, Old);
                }
                if (!Name.Contains(TEXT("InitializeParticle.")) || !Name.Contains(TEXT("Sprite Size")))
                    continue;
                Script->Modify();
                if (Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
                {
                    const float Old = Store.GetParameterValue<float>(Variable);
                    Store.SetParameterValue(Old * SpriteScale, Variable);
                    Report += FString::Printf(TEXT("%s %.3f -> %.3f\n"), *Name, Old, Old * SpriteScale);
                }
                else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec2Def())
                {
                    const FVector2f Old = Store.GetParameterValue<FVector2f>(Variable);
                    Store.SetParameterValue(Old * SpriteScale, Variable);
                    Report += FString::Printf(TEXT("%s %.3f,%.3f -> %.3f,%.3f\n"), *Name, Old.X, Old.Y,
                                              Old.X * SpriteScale, Old.Y * SpriteScale);
                }
            }
        }
    }
    Effect->RequestCompile(true);
    Effect->WaitForCompilationComplete();
    Effect->MarkPackageDirty();
#endif
    return Report;
}

int32 UHoverAuthoring::ConfigureSurfaceImpact(UNiagaraSystem *Effect, UMaterialInterface *DustMaterial)
{
    int32 Changed = 0;
#if WITH_EDITOR
    if (!Effect || !Effect->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/")) || !DustMaterial ||
        !DustMaterial->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/")))
        return 0;
    Effect->Modify();
    for (auto &Handle : Effect->GetEmitterHandles())
    {
        auto *Data = Handle.GetEmitterData();
        if (!Data || Handle.GetName() != TEXT("Dust"))
            continue;
        // The vehicle source spreads slowly over five seconds. A bullet needs a
        // compact, short burst directed out of the actual contact surface.
        Data->bLocalSpace = true;
        for (auto *Renderer : Data->GetRenderers())
            if (auto *Sprite = Cast<UNiagaraSpriteRendererProperties>(Renderer))
            {
                Sprite->Modify();
                Sprite->Material = DustMaterial;
                ++Changed;
            }
        TArray<UNiagaraScript *> Scripts;
        Data->GetScripts(Scripts);
        for (auto *Script : Scripts)
        {
            Script->Modify();
            auto &Store = Script->RapidIterationParameters;
            TArray<FNiagaraVariable> Variables;
            Store.GetParameters(Variables);
            for (const auto &Variable : Variables)
            {
                const FString Name = Variable.GetName().ToString();
                if (Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
                {
                    TOptional<float> Value;
                    if (Name.EndsWith(TEXT("RandomRangeFloat001.Minimum")))
                        Value = .45f;
                    else if (Name.EndsWith(TEXT("RandomRangeFloat001.Maximum")))
                        Value = .75f;
                    else if (Name.EndsWith(TEXT("RandomRangeFloat.Minimum")))
                        Value = .3f;
                    else if (Name.EndsWith(TEXT("RandomRangeFloat.Maximum")))
                        Value = .7f;
                    else if (Name.EndsWith(TEXT("ShapeLocation.Sphere Radius")))
                        Value = 6.f;
                    if (Value.IsSet())
                    {
                        Store.SetParameterValue(Value.GetValue(), Variable);
                        ++Changed;
                    }
                }
                else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec2Def() &&
                         (Name.EndsWith(TEXT("ScaleSpriteSizeBySpeed.Min Scale Factor")) ||
                          Name.EndsWith(TEXT("ScaleSpriteSizeBySpeed.Max Scale Factor"))))
                {
                    Store.SetParameterValue(FVector2f(1, 1), Variable);
                    ++Changed;
                }
                else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec3Def())
                {
                    if (Name.EndsWith(TEXT("RandomRangeVector001.Minimum")))
                    {
                        Store.SetParameterValue(FVector3f(-65, -65, 80), Variable);
                        ++Changed;
                    }
                    else if (Name.EndsWith(TEXT("RandomRangeVector001.Maximum")))
                    {
                        Store.SetParameterValue(FVector3f(65, 65, 160), Variable);
                        ++Changed;
                    }
                }
            }
        }
    }
    Effect->RequestCompile(true);
    Effect->WaitForCompilationComplete();
    Effect->MarkPackageDirty();
#endif
    return Changed;
}

void UHoverAuthoring::CapturePlaytest(const FString &Filename)
{
#if WITH_EDITOR
    FScreenshotRequest::RequestScreenshot(Filename, true, false);
#endif
}

bool UHoverAuthoring::PreserveMeshUserData(USkeletalMesh *Source, USkeletalMesh *Target)
{
#if WITH_EDITOR
    if (!Source || !Target || !Target->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Appearance/")))
        return false;
    if (const auto *Data = Source->GetAssetUserDataArray())
        for (auto *Entry : *Data)
            Target->AddAssetUserData(DuplicateObject(Entry, Target));
    Target->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

TMap<FString, FString> UHoverAuthoring::DescribeObjectProperties(UObject *Object)
{
    TMap<FString, FString> Result;
#if WITH_EDITOR
    if (Object)
        for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
            if (!It->HasAnyPropertyFlags(CPF_Transient))
            {
                FString Value;
                It->ExportText_InContainer(0, Value, Object, Object, Object, PPF_None);
                Result.Add(It->GetName(), Value);
            }
#endif
    return Result;
}

FString UHoverAuthoring::InspectCharacterMesh(USkeletalMesh *Mesh)
{
    FString Result;
#if WITH_EDITOR
    if (Mesh && Mesh->GetResourceForRendering() && Mesh->GetResourceForRendering()->LODRenderData.Num())
    {
        const auto &LOD = Mesh->GetResourceForRendering()->LODRenderData[0];
        const auto &Vertices = LOD.StaticVertexBuffers.StaticMeshVertexBuffer;
        const auto &Weights = LOD.SkinWeightVertexBuffer;
        for (const auto &Section : LOD.RenderSections)
        {
            FVector2f Min(FLT_MAX, FLT_MAX), Max(-FLT_MAX, -FLT_MAX);
            TMap<FName, int32> Counts;
            for (uint32 V = Section.BaseVertexIndex; V < Section.BaseVertexIndex + Section.NumVertices; ++V)
            {
                const FVector2f UV = Vertices.GetVertexUV(V, 0);
                Min.X = FMath::Min(Min.X, UV.X);
                Min.Y = FMath::Min(Min.Y, UV.Y);
                Max.X = FMath::Max(Max.X, UV.X);
                Max.Y = FMath::Max(Max.Y, UV.Y);
                for (uint32 I = 0; I < Weights.GetMaxBoneInfluences(); ++I)
                    if (Weights.GetBoneWeight(V, I) > 0)
                    {
                        const FName Bone =
                            Mesh->GetRefSkeleton().GetBoneName(Section.BoneMap[Weights.GetBoneIndex(V, I)]);
                        if (Bone.ToString().StartsWith(TEXT("chest_")) || Bone.ToString().StartsWith(TEXT("glute_")))
                            Counts.FindOrAdd(Bone)++;
                    }
            }
            Result += FString::Printf(TEXT("material=%d vertices=%u UV0=(%.4f,%.4f)-(%.4f,%.4f)\n"),
                                      Section.MaterialIndex, Section.NumVertices, Min.X, Min.Y, Max.X, Max.Y);
            for (const auto &Pair : Counts)
                Result += FString::Printf(TEXT("weighted %s vertices=%d\n"), *Pair.Key.ToString(), Pair.Value);
        }
    }
#endif
    return Result;
}

FString UHoverAuthoring::InspectTexture(UTexture2D *Texture)
{
    FString Result;
#if WITH_EDITOR
    if (Texture)
        for (int32 I = 0; I < Texture->Source.GetNumBlocks(); ++I)
        {
            FTextureSourceBlock Block;
            Texture->Source.GetBlock(I, Block);
            Result += FString::Printf(TEXT("block=%d tile=%d,%d size=%dx%d\n"), I, Block.BlockX, Block.BlockY,
                                      Block.SizeX, Block.SizeY);
        }
#endif
    return Result;
}

int32 UHoverAuthoring::RemapAppearanceAsset(UObject *Asset, const TArray<UObject *> &Sources,
                                            const TArray<UObject *> &Copies)
{
#if WITH_EDITOR
    if (!Asset || !Asset->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Appearance/")) ||
        Sources.Num() != Copies.Num())
        return -1;
    TMap<UObject *, UObject *> Map;
    for (int32 I = 0; I < Sources.Num(); ++I)
    {
        if (!Copies[I] || !Copies[I]->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Appearance/")))
            return -1;
        Map.Add(Sources[I], Copies[I]);
    }
    Asset->Modify();
    FArchiveReplaceObjectRef<UObject> Archive(
        Asset, Map, EArchiveReplaceObjectFlags::IgnoreOuterRef | EArchiveReplaceObjectFlags::IgnoreArchetypeRef);
    Asset->MarkPackageDirty();
    return Archive.GetCount();
#else
    return -1;
#endif
}

bool UHoverAuthoring::ConvertAppearanceTextures(const TArray<UTexture2D *> &Textures,
                                                const TArray<UMaterial *> &Materials)
{
#if WITH_EDITOR
    for (const UObject *Object : Textures)
        if (!Object || !Object->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Appearance/")))
            return false;
    for (const UObject *Object : Materials)
        if (!Object || !Object->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Appearance/")))
            return false;
    FModuleManager::LoadModuleChecked<IVirtualTexturingEditorModule>(TEXT("VirtualTexturingEditor"))
        .ConvertVirtualTextures(Textures, false, &Materials);
    return true;
#else
    return false;
#endif
}

void UHoverAuthoring::PrepareReviewEffects(const TArray<UNiagaraSystem *> &Effects)
{
#if WITH_EDITOR
    // Short-lived effects must be compiled before a rendered review begins.
    // Otherwise the first shot can expire while its shaders are still compiling.
    for (UNiagaraSystem *Effect : Effects)
        if (Effect)
            Effect->WaitForCompilationComplete(true, false);
    FAssetCompilingManager::Get().FinishAllCompilation();
#endif
}

FString UHoverAuthoring::InspectReviewEffects()
{
    FString Report;
#if WITH_EDITOR
    UWorld *World = GetPlaytestWorld();
    if (!World)
        return TEXT("No play world");
    if (auto *Viewport = World->GetGameViewport())
        Report = FString::Printf(TEXT("Particles=%d Niagara=%d Translucency=%d\n"), Viewport->EngineShowFlags.Particles,
                                 Viewport->EngineShowFlags.Niagara, Viewport->EngineShowFlags.Translucency);
    for (TObjectIterator<UNiagaraComponent> It; It; ++It)
        if (It->GetWorld() == World)
        {
            auto Controller = It->GetSystemInstanceController();
            Report +=
                FString::Printf(TEXT("%s active=%d rendering=%d state=%d age=%.3f position=%s bounds=%s\n"),
                                *GetNameSafe(It->GetAsset()), It->IsActive(), It->GetRenderingEnabled(),
                                int32(It->GetExecutionState()), Controller.IsValid() ? Controller->GetAge() : -1.f,
                                *It->GetComponentLocation().ToString(), *It->Bounds.GetBox().ToString());
            if (Controller.IsValid())
                if (auto *Instance = Controller->GetSystemInstance_Unsafe())
                {
                    Instance->WaitForConcurrentTickAndFinalize();
                    for (const auto &Emitter : Instance->GetEmitters())
                    {
                        Report += FString::Printf(TEXT("  %s particles=%d\n"),
                                                  *Emitter->GetEmitterHandle().GetName().ToString(),
                                                  Emitter->GetNumParticles());
                        if (Emitter->GetEmitterHandle().GetName() == TEXT("Dust"))
                            if (const auto *Buffer = Emitter->GetParticleData().GetCurrentData();
                                Buffer && Buffer->GetNumInstances() > 0)
                            {
                                FNiagaraDataVariableIterator Values(Buffer);
                                Values.Get();
                                for (const auto &Value : Values.GetVariables())
                                    Report += TEXT("    ") + Value.ToString() + TEXT("\n");
                            }
                    }
                }
        }
#endif
    return Report;
}

void UHoverAuthoring::CaptureWorldFrame(const FString &Filename)
{
#if WITH_EDITOR
    if (UWorld *World = GetPlaytestWorld())
        if (UGameViewportClient *Client = World->GetGameViewport(); Client && Client->Viewport)
        {
            TArray<FColor> Pixels;
            if (Client->Viewport->ReadPixels(Pixels))
            {
                // Backbuffer alpha is not scene opacity; export an opaque review image.
                for (FColor &Pixel : Pixels)
                    Pixel.A = 255;
                const FIntPoint Size = Client->Viewport->GetSizeXY();
                TArray64<uint8> PNG;
                const FImageView Image(Pixels.GetData(), Size.X, Size.Y);
                if (FImageUtils::CompressImage(PNG, TEXT("png"), Image))
                    FFileHelper::SaveArrayToFile(PNG, *Filename);
            }
        }
#endif
}
