#include "HoverAuthoring.h"
#include "HoverTestController.h"
#include "GameFramework/PlayerInput.h"
#include "Engine/Blueprint.h"
#include "UObject/UnrealType.h"
#include "GameFramework/PlayerController.h"
#include "InputKeyEventArgs.h"
#include "UnrealClient.h"
#if WITH_EDITOR
#include "NiagaraSystem.h"
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
#endif

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
    auto *TestController = Cast<AHoverTestController>(Controller);
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
        if (PC->PlayerInput)
            PC->PlayerInput->FlushPressedKeys();
    }
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
