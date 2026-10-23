#include "HoverAuthoring.h"
#include "Engine/DirectionalLight.h"
#include "EngineUtils.h"
#include "HoverTestController.h"
#include "HoverPilot.h"
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
#endif

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

bool UHoverAuthoring::AddCityNavigation(UWorld *World, FVector Center, FVector Size)
{
#if WITH_EDITOR
    if (!World || !World->GetName().Contains(TEXT("CyberCity")))
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
    Bounds->SetActorLabel(TEXT("AFS Cyber City Navigation"));
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

TArray<FVector> UHoverAuthoring::FindCompleteCityPath(UWorld *World, FVector Start, FVector End)
{
    TArray<FVector> Points;
#if WITH_EDITOR
    if (auto *Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(World))
        if (auto *Data = Navigation->GetDefaultNavDataInstance())
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
