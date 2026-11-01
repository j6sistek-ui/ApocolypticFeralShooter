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
#include "Animation/AnimMontage.h"
#include "Animation/BlendSpace1D.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimData/IAnimationDataModel.h"
#include "Animation/Skeleton.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AttributesRuntime.h"
#include "BoneContainer.h"
#include "BonePose.h"
#include "Misc/MemStack.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraScript.h"
#include "NiagaraScriptSource.h"
#include "NiagaraGraph.h"
#include "NiagaraSpriteRendererProperties.h"
#include "NiagaraComponent.h"
#include "NiagaraRendererProperties.h"
#include "NiagaraLightRendererProperties.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleEmitter.h"
#include "Particles/ParticleLODLevel.h"
#include "Particles/ParticleModuleRequired.h"
#include "Particles/Lifetime/ParticleModuleLifetime.h"
#include "Particles/Color/ParticleModuleColor.h"
#include "Distributions/DistributionFloat.h"
#include "Distributions/DistributionVector.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "NiagaraSystemInstanceController.h"
#include "NiagaraSystemInstance.h"
#include "NiagaraEmitterInstance.h"
#include "NiagaraDataSet.h"
#include "NiagaraDataInterfaceCurve.h"
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
#include "Framework/Application/SlateApplication.h"
#include "Null/NullApplication.h"
#include "Widgets/SWindow.h"
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
#include "Engine/TriggerVolume.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/WorldSettings.h"
#include "World/ZE_ZombieSpawnPoint.h"
#include "Engine/LevelStreaming.h"
#include "FileHelpers.h"
#include "LevelEditorViewport.h"
#endif

#if WITH_EDITOR
namespace
{
const TCHAR *NYCSurvivalMap = TEXT("/Game/HoverPrototype/Maps/L_NYC_Survival");

// Exact package match: refuses L_NYC_Explore, vendor maps and PIE copies (UEDPIE_ prefix).
bool IsOwnedSurvivalWorld(const UWorld *World)
{
    return World && !World->IsGameWorld() && World->GetOutermost()->GetName() == NYCSurvivalMap;
}
} // namespace
#endif

bool UHoverAuthoring::ConfigureCityStartingGear(UZE_WaveGameModeSettings *Settings, int32 AmmoQuantity,
                                                int32 GrenadeCount, bool bWithSidearm)
{
#if WITH_EDITOR
    // Owned wave assets only: Cyber City (120 / 0 defaults) and NYC Survival (270 / 2 by argument).
    if (!Settings || !(Settings->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/")) ||
                       Settings->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/NYC/"))))
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
    // Owner 2026-10-31: "have the pistol on hand". The owned DA_NYC_Pistol (HoverCyberRifle actor, EM_08 revolver
    // rig) goes to quickbar slot 2 with its ammo; the vendor pistol is the fallback when the owned one is absent.
    if (bWithSidearm)
    {
        auto *Pistol = LoadObject<UZE_WeaponDefinition>(
            nullptr, TEXT("/Game/HoverPrototype/NYC/Weapons/DA_NYC_Pistol.DA_NYC_Pistol"));
        if (!Pistol)
            Pistol = LoadObject<UZE_WeaponDefinition>(
                nullptr, TEXT("/Game/ZESP/ZE/Data/Weapons/DA_Weapon_Pistol_001.DA_Weapon_Pistol_001"));
        auto *PistolAmmo =
            LoadObject<UZE_AmmoDefinition>(nullptr, TEXT("/Game/ZESP/ZE/Data/Ammo/DA_AMMO_Pistol.DA_AMMO_Pistol"));
        if (Pistol)
        {
            FZE_StartingWeaponConfig Side;
            Side.WeaponDefinition = Pistol;
            Side.bAddToQuickbar = true;
            Side.QuickbarSlot = 2;
            Gear.StartingWeapons.Add(Side);
            if (Gear.GrenadeQuickbarSlot == 2)
                Gear.GrenadeQuickbarSlot = 3;
        }
        if (PistolAmmo)
            Gear.StartingAmmo.Add(PistolAmmo);
    }
    Gear.AmmoQuantity = FMath::Max(0, AmmoQuantity);
    Gear.StartingGold = 500;
    // The frag definition itself (GrenadeItem) is the equipment slice's; only the count is set here.
    Gear.GrenadeCount = FMath::Max(0, GrenadeCount);
    Settings->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

FName UHoverAuthoring::BindGunRig(UHoverPilotAssets *Assets, FName WeaponKey, UHoverGunRig *Rig, bool bExactKey)
{
#if WITH_EDITOR
    if (!Assets || WeaponKey.IsNone() || !Assets->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")) ||
        (Rig && !Rig->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/"))))
        return NAME_None;
    const FName Key = bExactKey ? WeaponKey : UHoverGunRig::NormalizeWeaponKey(WeaponKey);
    Assets->Modify();
    Assets->GunRigs.Add(Key, Rig);
    Assets->MarkPackageDirty();
    return Key;
#else
    return NAME_None;
#endif
}

bool UHoverAuthoring::UnbindGunRig(UHoverPilotAssets *Assets, FName WeaponKey)
{
#if WITH_EDITOR
    if (!Assets || !Assets->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")) ||
        !Assets->GunRigs.Contains(WeaponKey))
        return false;
    Assets->Modify();
    Assets->GunRigs.Remove(WeaponKey);
    Assets->MarkPackageDirty();
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

bool UHoverAuthoring::AddCityNavigation(UWorld *World, FVector Center, FVector Size, bool bDynamicModifiersOnly)
{
#if WITH_EDITOR
    if (!World || !(World->GetName().Contains(TEXT("CyberCity")) || World->GetName() == TEXT("L_Showcase") ||
                    IsOwnedSurvivalWorld(World)))
        return false;
    ANavMeshBoundsVolume *Bounds = nullptr;
    for (TActorIterator<ANavMeshBoundsVolume> It(World); It; ++It)
        if (It->ActorHasTag(TEXT("AFS_CityNavigation")))
            Bounds = *It;
    if (!Bounds)
        if (auto *Factory = GEditor->FindActorFactoryForActorClass(ANavMeshBoundsVolume::StaticClass()))
            // NYC Survival keeps its bounds in the persistent level, never in a vendor streaming sublevel.
            Bounds = Cast<ANavMeshBoundsVolume>(Factory->CreateActor(
                nullptr, IsOwnedSurvivalWorld(World) ? World->PersistentLevel.Get() : World->GetCurrentLevel(),
                FTransform(Center)));
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
            Property->GetUnderlyingProperty()->SetIntPropertyValue(
                Property->ContainerPtrToValuePtr<void>(*It),
                static_cast<int64>(bDynamicModifiersOnly ? ERuntimeGenerationType::DynamicModifiersOnly
                                                         : ERuntimeGenerationType::Dynamic));
    return true;
#else
    return false;
#endif
}

FString UHoverAuthoring::ConfigureCityNavMesh(UWorld *World, float TileSizeUU, float CellSize, float AgentMaxStepHeight,
                                              int32 TilePoolSize)
{
#if WITH_EDITOR
    if (!IsOwnedSurvivalWorld(World))
        return TEXT("Refused");
    FString Report;
    for (TActorIterator<ARecastNavMesh> It(World); It; ++It)
    {
        It->Modify();
        It->TileSizeUU = TileSizeUU;
        It->bFixedTilePoolSize = true;
        It->TilePoolSize = TilePoolSize;
        // Python cannot reliably write the fixed-size NavMeshResolutionParams array.
        It->SetCellSize(ENavigationDataResolution::Default, CellSize);
        It->SetAgentMaxStepHeight(ENavigationDataResolution::Default, AgentMaxStepHeight);
        It->MarkPackageDirty();
        Report += FString::Printf(TEXT("%sRecast=%s TileSizeUU=%.1f Cell=%.1f Step=%.1f Pool=%d ActiveTiles=%d"),
                                  Report.IsEmpty() ? TEXT("") : TEXT("\n"), *It->GetName(), It->TileSizeUU, CellSize,
                                  AgentMaxStepHeight, It->TilePoolSize, It->GetNumActiveTiles());
    }
    return Report.IsEmpty() ? TEXT("No RecastNavMesh") : Report;
#else
    return TEXT("");
#endif
}

AActor *UHoverAuthoring::AddSurvivalActor(UWorld *World, TSubclassOf<AActor> ActorClass, FTransform Transform,
                                          const FString &Label, const TArray<FName> &Tags)
{
#if WITH_EDITOR
    // Allow-list: spawn points and player starts only, so this never becomes a general spawner.
    if (!IsOwnedSurvivalWorld(World) || !ActorClass || Label.IsEmpty() ||
        !(ActorClass->IsChildOf(AZE_ZombieSpawnPoint::StaticClass()) ||
          ActorClass->IsChildOf(APlayerStart::StaticClass())))
        return nullptr;
    ULevel *Level = World->PersistentLevel;
    AActor *Actor = nullptr;
    for (AActor *Existing : Level->Actors)
        if (Existing && Existing->IsA(ActorClass) && Existing->GetActorLabel() == Label)
        {
            Actor = Existing;
            break;
        }
    if (Actor)
    {
        Actor->Modify();
        Actor->SetActorTransform(Transform);
    }
    else
    {
        FActorSpawnParameters Params;
        Params.OverrideLevel = Level;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        Actor = World->SpawnActor<AActor>(ActorClass, Transform, Params);
        if (!Actor)
            return nullptr;
    }
    Actor->SetActorLabel(Label);
    for (const FName &Tag : Tags)
        Actor->Tags.AddUnique(Tag);
    Actor->PostEditChange();
    Actor->MarkPackageDirty();
    return Actor;
#else
    return nullptr;
#endif
}

AActor *UHoverAuthoring::AddZoneVolume(UWorld *World, FName ZoneId, int32 Order, FVector Center, FVector Size)
{
#if WITH_EDITOR
    if (!IsOwnedSurvivalWorld(World) || ZoneId.IsNone())
        return nullptr;
    ATriggerVolume *Volume = nullptr;
    for (AActor *Existing : World->PersistentLevel->Actors)
        if (auto *Trigger = Cast<ATriggerVolume>(Existing))
            if (Trigger->ActorHasTag(TEXT("AFS_NYCZone")) && Trigger->ActorHasTag(ZoneId))
            {
                Volume = Trigger;
                break;
            }
    if (!Volume)
        if (auto *Factory = GEditor->FindActorFactoryForActorClass(ATriggerVolume::StaticClass()))
            Volume = Cast<ATriggerVolume>(Factory->CreateActor(nullptr, World->PersistentLevel, FTransform(Center)));
    if (!Volume)
        return nullptr;
    Volume->Modify();
    // Overlap-only zone marker: the tall box must never carve the navmesh.
    Volume->GetBrushComponent()->SetCanEverAffectNavigation(false);
    Volume->GetBrushComponent()->SetCollisionProfileName(TEXT("Trigger"));
    auto *Builder = NewObject<UCubeBuilder>();
    Builder->X = Size.X;
    Builder->Y = Size.Y;
    Builder->Z = Size.Z;
    if (!Builder->Build(World, Volume))
        return nullptr;
    Volume->GetBrushComponent()->BuildSimpleBrushCollision();
    Volume->GetBrushComponent()->UpdateBounds();
    Volume->PostEditMove(true);
    Volume->SetActorLocation(Center);
    Volume->Tags.AddUnique(TEXT("AFS_NYCZone"));
    Volume->Tags.AddUnique(ZoneId);
    Volume->Tags.AddUnique(FName(*FString::Printf(TEXT("AFS_ZoneOrder_%d"), Order)));
    Volume->SetActorLabel(FString::Printf(TEXT("AFS Zone %s"), *ZoneId.ToString()));
    Volume->MarkPackageDirty();
    return Volume;
#else
    return nullptr;
#endif
}

FString UHoverAuthoring::DescribeStreamingLevels(UWorld *World)
{
#if WITH_EDITOR
    if (!World)
        return TEXT("No world");
    TArray<FString> Lines;
    for (ULevelStreaming *Streaming : World->GetStreamingLevels())
    {
        if (!Streaming)
            continue;
        const ULevel *Loaded = Streaming->GetLoadedLevel();
        Lines.Add(FString::Printf(TEXT("%s class=%s loaded=%d dirty=%d"), *Streaming->GetWorldAssetPackageName(),
                                  *Streaming->GetClass()->GetName(), Loaded != nullptr,
                                  Loaded && Loaded->GetOutermost()->IsDirty()));
    }
    const AWorldSettings *Settings = World->GetWorldSettings();
    Lines.Add(FString::Printf(TEXT("PersistentActors=%d DefaultGameMode=%s"),
                              World->PersistentLevel ? World->PersistentLevel->Actors.Num() : 0,
                              Settings && Settings->DefaultGameMode ? *Settings->DefaultGameMode->GetPathName()
                                                                    : TEXT("None")));
    return FString::Join(Lines, TEXT("\n"));
#else
    return TEXT("");
#endif
}

bool UHoverAuthoring::SaveSurvivalMap(UWorld *World)
{
#if WITH_EDITOR
    if (!IsOwnedSurvivalWorld(World))
        return false;
    // Vendor sublevels are never saved: refuse while any loaded sublevel package is dirty.
    bool bVendorDirty = false;
    for (ULevelStreaming *Streaming : World->GetStreamingLevels())
        if (const ULevel *Loaded = Streaming ? Streaming->GetLoadedLevel() : nullptr)
            if (Loaded->GetOutermost()->IsDirty())
            {
                UE_LOG(LogTemp, Error, TEXT("NYC Survival save refused: dirty sublevel %s"),
                       *Loaded->GetOutermost()->GetName());
                bVendorDirty = true;
            }
    if (bVendorDirty)
        return false;
    return FEditorFileUtils::SaveLevel(World->PersistentLevel);
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
        Parameter->DisplayName = Blend->GetName().Contains(TEXT("Aim"))
                                     ? (I == 0 ? TEXT("Aim yaw") : TEXT("Aim pitch"))
                                     : (I == 0 ? TEXT("Turn") : TEXT("Forward / reverse"));
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

void UHoverAuthoring::StartPlaytest(int32 Width, int32 Height)
{
#if WITH_EDITOR
    if (!GEditor || GEditor->PlayWorld)
        return;
    GetMutableDefault<UEditorPerformanceSettings>()->bThrottleCPUWhenNotForeground = false;
    FRequestPlaySessionParams Params;
    auto *Settings = GetMutableDefault<ULevelEditorPlaySettings>();
    Settings->NewWindowWidth = FMath::Max(Width, 320);
    Settings->NewWindowHeight = FMath::Max(Height, 240);
    Params.EditorPlaySettings = Settings;
    Params.bAllowOnlineSubsystem = false;
    GEditor->RequestPlaySession(Params);
#endif
}
FString UHoverAuthoring::ConfigureOffscreenDisplay(int32 Width, int32 Height)
{
#if WITH_EDITOR
    if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().IsRenderingOffScreen())
        return TEXT("not rendering offscreen");
    const TSharedPtr<GenericApplication> App = FSlateApplication::Get().GetPlatformApplication();
    if (!App)
        return TEXT("no platform application");
    FPlatformRect Area;
    Area.Left = 0;
    Area.Top = 0;
    Area.Right = FMath::Max(Width, 320);
    Area.Bottom = FMath::Max(Height, 240);
    // Offscreen rendering always installs FNullApplication (ApplicationCore), the only platform app with a
    // settable virtual work area.
    static_cast<FNullApplication *>(App.Get())->SetWorkArea(Area);
    const FPlatformRect Now = App->GetWorkArea(Area);
    return FString::Printf(TEXT("work area %d x %d"), Now.Right - Now.Left, Now.Bottom - Now.Top);
#else
    return TEXT("editor only");
#endif
}
FString UHoverAuthoring::SetLevelViewportsRealtime(bool bRealtime, bool bKeepTickingInBackground)
{
#if WITH_EDITOR
    if (!GEditor)
        return TEXT("no editor");
    FString Report = FString::Printf(TEXT("level viewport clients %d\n"), GEditor->GetLevelViewportClients().Num());
    if (bKeepTickingInBackground)
    {
        // this session only (not saved to the ini): an unfocused editor otherwise re-pushes its 'Background Process'
        // realtime override every frame
        auto *Perf = GetMutableDefault<UEditorPerformanceSettings>();
        Report += FString::Printf(TEXT("throttle when not foreground was %d, now 0\n"), int32(Perf->bThrottleCPUWhenNotForeground));
        Perf->bThrottleCPUWhenNotForeground = false;
    }
    for (FLevelEditorViewportClient *Client : GEditor->GetLevelViewportClients())
    {
        if (!Client)
            continue;
        const FString Before = FString::Printf(TEXT("realtime=%d override='%s'"), int32(Client->IsRealtime()),
                                               *Client->GetRealtimeOverrideMessage().ToString());
        Client->SetRealtime(bRealtime);
        // an override (unattended / remote session / performance) wins over SetRealtime: push ours on top of it
        static const FText OverrideName = FText::FromString(TEXT("AFS SetLevelViewportsRealtime"));
        Client->RemoveRealtimeOverride(OverrideName, false);
        if (Client->IsRealtime() != bRealtime)
            Client->AddRealtimeOverride(bRealtime, OverrideName);
        Report += FString::Printf(TEXT("client perspective=%d before(%s) now realtime=%d visible=%d world=%s\n"),
                                  int32(Client->IsPerspective()), *Before, int32(Client->IsRealtime()),
                                  int32(Client->IsVisible()), Client->GetWorld() ? *Client->GetWorld()->GetName() : TEXT("none"));
    }
    return Report;
#else
    return TEXT("editor only");
#endif
}
FIntPoint UHoverAuthoring::GetPlaytestViewportSize()
{
#if WITH_EDITOR
    if (UWorld *World = GetPlaytestWorld())
        if (UGameViewportClient *Client = World->GetGameViewport(); Client && Client->Viewport)
            return Client->Viewport->GetSizeXY();
#endif
    return FIntPoint::ZeroValue;
}
FIntPoint UHoverAuthoring::ResizePlaytestWindow(int32 Width, int32 Height)
{
#if WITH_EDITOR
    if (UWorld *World = GetPlaytestWorld())
        if (UGameViewportClient *Client = World->GetGameViewport())
            if (TSharedPtr<SWindow> Window = Client->GetWindow())
            {
                Window->Resize(FVector2D(FMath::Max(Width, 320), FMath::Max(Height, 240)));
                const FVector2D Size = Window->GetClientSizeInScreen();
                return FIntPoint(FMath::RoundToInt(Size.X), FMath::RoundToInt(Size.Y));
            }
#endif
    return FIntPoint::ZeroValue;
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

namespace
{
#if WITH_EDITOR
// A Niagara parameter as JSON: name, type and the value when the type is one we can read. Enums read as their
// int32 payload plus the enum's display name so Loop Behavior (Infinite / Once / Multiple) is legible.
TSharedPtr<FJsonObject> FlashParameterJson(const FNiagaraParameterStore &Store, const FNiagaraVariable &Variable)
{
    auto Row = MakeShared<FJsonObject>();
    const FNiagaraTypeDefinition &Type = Variable.GetType();
    Row->SetStringField(TEXT("name"), Variable.GetName().ToString());
    Row->SetStringField(TEXT("type"), Type.GetName());
    if (Store.IndexOf(Variable) == INDEX_NONE)
        return Row;
    if (Type == FNiagaraTypeDefinition::GetFloatDef())
        Row->SetNumberField(TEXT("value"), Store.GetParameterValue<float>(Variable));
    else if (Type == FNiagaraTypeDefinition::GetIntDef())
        Row->SetNumberField(TEXT("value"), Store.GetParameterValue<int32>(Variable));
    else if (Type == FNiagaraTypeDefinition::GetBoolDef())
        Row->SetBoolField(TEXT("value"), Store.GetParameterValue<FNiagaraBool>(Variable).GetValue());
    else if (Type == FNiagaraTypeDefinition::GetColorDef())
    {
        const FLinearColor C = Store.GetParameterValue<FLinearColor>(Variable);
        TArray<TSharedPtr<FJsonValue>> V;
        for (float F : {C.R, C.G, C.B, C.A})
            V.Add(MakeShared<FJsonValueNumber>(F));
        Row->SetArrayField(TEXT("value"), V);
    }
    else if (Type == FNiagaraTypeDefinition::GetVec2Def())
    {
        const FVector2f P = Store.GetParameterValue<FVector2f>(Variable);
        Row->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(P.X), MakeShared<FJsonValueNumber>(P.Y)});
    }
    else if (Type == FNiagaraTypeDefinition::GetVec3Def())
    {
        const FVector3f P = Store.GetParameterValue<FVector3f>(Variable);
        Row->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(P.X), MakeShared<FJsonValueNumber>(P.Y),
                                           MakeShared<FJsonValueNumber>(P.Z)});
    }
    else if (Type.IsEnum() && Variable.GetSizeInBytes() == sizeof(int32))
    {
        const int32 I = Store.GetParameterValue<int32>(Variable);
        Row->SetNumberField(TEXT("value"), I);
        if (const UEnum *Enum = Type.GetEnum())
            Row->SetStringField(TEXT("enum"), Enum->GetDisplayNameTextByValue(I).ToString());
    }
    return Row;
}

// Module-input constants worth an inventory row: loop timing, lifetime, colour, size / scale. Everything else
// (velocity, drag, camera offset, ...) stays out so the JSON reads.
bool FlashConstantIsInteresting(const FString &Name)
{
    const FString Flat = Name.Replace(TEXT(" "), TEXT("")).ToLower();
    for (const TCHAR *Key : {TEXT("loop"), TEXT("lifetime"), TEXT("color"), TEXT("colour"), TEXT("tint"), TEXT("size"),
                             TEXT("scale"), TEXT("spawncount"), TEXT("duration"), TEXT("intensity"), TEXT("radius")})
        if (Flat.Contains(Key))
            return true;
    return false;
}
#endif
} // namespace

FString UHoverAuthoring::DescribeFlashAsset(UObject *Asset)
{
    FString Out;
#if WITH_EDITOR
    auto Root = MakeShared<FJsonObject>();
    if (!Asset)
        return Out;
    Root->SetStringField(TEXT("path"), Asset->GetPathName());
    Root->SetStringField(TEXT("class"), Asset->GetClass()->GetName());
    double Duration = 0.0; // -1 once any emitter loops forever; the longest finite emitter otherwise.
    bool bDurationKnown = false;
    if (auto *Effect = Cast<UNiagaraSystem>(Asset))
    {
        TArray<TSharedPtr<FJsonValue>> Users;
        TArray<FNiagaraVariable> Exposed;
        Effect->GetExposedParameters().GetParameters(Exposed);
        for (const auto &Variable : Exposed)
            Users.Add(MakeShared<FJsonValueObject>(FlashParameterJson(Effect->GetExposedParameters(), Variable)));
        Root->SetArrayField(TEXT("user_parameters"), Users);
        TArray<TSharedPtr<FJsonValue>> Emitters;
        for (auto &Handle : Effect->GetEmitterHandles())
        {
            auto Row = MakeShared<FJsonObject>();
            Row->SetStringField(TEXT("name"), Handle.GetName().ToString());
            Row->SetBoolField(TEXT("enabled"), Handle.GetIsEnabled());
            auto *Data = Handle.GetEmitterData();
            if (!Data)
            {
                Emitters.Add(MakeShared<FJsonValueObject>(Row));
                continue;
            }
            Row->SetBoolField(TEXT("local_space"), Data->bLocalSpace);
            Row->SetStringField(TEXT("sim_target"), Data->SimTarget == ENiagaraSimTarget::GPUComputeSim ? TEXT("GPU") : TEXT("CPU"));
            TArray<TSharedPtr<FJsonValue>> Renderers;
            for (auto *Renderer : Data->GetRenderers())
            {
                if (!Renderer)
                    continue;
                auto R = MakeShared<FJsonObject>();
                R->SetStringField(TEXT("class"), Renderer->GetClass()->GetName());
                R->SetBoolField(TEXT("enabled"), Renderer->GetIsEnabled());
                // A light renderer is the part that "whites the character out": its radius and colour add matter.
                if (auto *Light = Cast<UNiagaraLightRendererProperties>(Renderer))
                {
                    R->SetNumberField(TEXT("radius_scale"), Light->RadiusScale);
                    R->SetBoolField(TEXT("inverse_squared"), Light->bUseInverseSquaredFalloff);
                    R->SetArrayField(TEXT("color_add"), {MakeShared<FJsonValueNumber>(Light->ColorAdd.X),
                                                         MakeShared<FJsonValueNumber>(Light->ColorAdd.Y),
                                                         MakeShared<FJsonValueNumber>(Light->ColorAdd.Z)});
                }
                Renderers.Add(MakeShared<FJsonValueObject>(R));
            }
            Row->SetArrayField(TEXT("renderers"), Renderers);
            // Module inputs the stack stores as rapid-iteration constants (editor data). Loop Behavior is read when
            // it is a constant; as a static switch it is compiled in and absent, which the row then says.
            TArray<TSharedPtr<FJsonValue>> Constants;
            TArray<UNiagaraScript *> Scripts;
            Data->GetScripts(Scripts);
            double LoopDuration = 0, LoopDelay = 0, LifetimeMax = 0;
            int32 LoopBehavior = -1, LoopCount = 1;
            bool bLoopDurationKnown = false;
            for (auto *Script : Scripts)
            {
                if (!Script)
                    continue;
                TArray<FNiagaraVariable> Variables;
                Script->RapidIterationParameters.GetParameters(Variables);
                for (const auto &Variable : Variables)
                {
                    const FString Name = Variable.GetName().ToString();
                    if (!FlashConstantIsInteresting(Name))
                        continue;
                    auto C = FlashParameterJson(Script->RapidIterationParameters, Variable);
                    Constants.Add(MakeShared<FJsonValueObject>(C));
                    const FString Flat = Name.Replace(TEXT(" "), TEXT("")).ToLower();
                    double Number = 0;
                    const bool bNumber = C->TryGetNumberField(TEXT("value"), Number);
                    if (Flat.Contains(TEXT("emitterstate")) && bNumber)
                    {
                        if (Flat.EndsWith(TEXT("loopduration")))
                        {
                            LoopDuration = FMath::Max(LoopDuration, Number);
                            bLoopDurationKnown = true;
                        }
                        else if (Flat.EndsWith(TEXT("loopdelay")))
                            LoopDelay = FMath::Max(LoopDelay, Number);
                        else if (Flat.EndsWith(TEXT("loopcount")))
                            LoopCount = FMath::Max(1, int32(Number));
                        else if (Flat.EndsWith(TEXT("loopbehavior")))
                            LoopBehavior = int32(Number);
                    }
                    else if (Flat.Contains(TEXT("lifetime")) && bNumber)
                        LifetimeMax = FMath::Max(LifetimeMax, Number);
                }
            }
            Row->SetArrayField(TEXT("constants"), Constants);
            // ENiagaraLoopBehavior: Infinite 0, Once 1, Multiple 2. Unknown behaviour with a known duration is
            // treated as Once (the shipped muzzle flashes all burst once).
            double EmitterDuration = -1;
            if (LoopBehavior == 0)
                EmitterDuration = -1;
            else if (bLoopDurationKnown)
                EmitterDuration = LoopDelay + LoopDuration * (LoopBehavior == 2 ? LoopCount : 1) + LifetimeMax;
            Row->SetNumberField(TEXT("loop_behavior"), LoopBehavior);
            Row->SetNumberField(TEXT("loop_duration_s"), LoopDuration);
            Row->SetNumberField(TEXT("loop_count"), LoopCount);
            Row->SetNumberField(TEXT("lifetime_max_s"), LifetimeMax);
            Row->SetNumberField(TEXT("duration_s"), EmitterDuration);
            Row->SetBoolField(TEXT("duration_known"), LoopBehavior == 0 || bLoopDurationKnown);
            if (Handle.GetIsEnabled())
            {
                if (EmitterDuration < 0 && (LoopBehavior == 0 || !bLoopDurationKnown))
                {
                    if (LoopBehavior == 0)
                        Duration = -1;
                }
                else if (Duration >= 0)
                    Duration = FMath::Max(Duration, EmitterDuration);
                bDurationKnown = bDurationKnown || LoopBehavior == 0 || bLoopDurationKnown;
            }
            Emitters.Add(MakeShared<FJsonValueObject>(Row));
        }
        Root->SetArrayField(TEXT("emitters"), Emitters);
    }
    else if (auto *Cascade = Cast<UParticleSystem>(Asset))
    {
        TArray<TSharedPtr<FJsonValue>> Emitters;
        for (UParticleEmitter *Emitter : Cascade->Emitters)
        {
            if (!Emitter)
                continue;
            auto Row = MakeShared<FJsonObject>();
            Row->SetStringField(TEXT("name"), Emitter->EmitterName.ToString());
            UParticleLODLevel *Lod = Emitter->LODLevels.Num() ? Emitter->LODLevels[0].Get() : nullptr;
            if (!Lod)
            {
                Emitters.Add(MakeShared<FJsonValueObject>(Row));
                continue;
            }
            Row->SetBoolField(TEXT("enabled"), Lod->bEnabled);
            double EmitterDuration = -1;
            float LifetimeMax = 0;
            TArray<TSharedPtr<FJsonValue>> Modules;
            for (UParticleModule *Module : Lod->Modules)
            {
                if (!Module)
                    continue;
                auto M = MakeShared<FJsonObject>();
                M->SetStringField(TEXT("class"), Module->GetClass()->GetName());
                if (auto *Lifetime = Cast<UParticleModuleLifetime>(Module))
                {
                    float Min = 0, Max = 0;
                    Lifetime->Lifetime.GetOutRange(Min, Max);
                    M->SetNumberField(TEXT("lifetime_min_s"), Min);
                    M->SetNumberField(TEXT("lifetime_max_s"), Max);
                    LifetimeMax = FMath::Max(LifetimeMax, Max);
                }
                if (auto *Color = Cast<UParticleModuleColor>(Module))
                {
                    float Min = 0, Max = 0;
                    Color->StartColor.GetOutRange(Min, Max);
                    M->SetNumberField(TEXT("start_color_min"), Min);
                    M->SetNumberField(TEXT("start_color_max"), Max);
                }
                Modules.Add(MakeShared<FJsonValueObject>(M));
            }
            if (UParticleModuleRequired *Required = Lod->RequiredModule)
            {
                Row->SetNumberField(TEXT("emitter_duration_s"), Required->EmitterDuration);
                Row->SetNumberField(TEXT("emitter_loops"), Required->EmitterLoops);
                EmitterDuration = Required->EmitterLoops == 0
                                      ? -1
                                      : Required->EmitterDuration * Required->EmitterLoops + LifetimeMax;
            }
            Row->SetNumberField(TEXT("lifetime_max_s"), LifetimeMax);
            Row->SetNumberField(TEXT("duration_s"), EmitterDuration);
            Row->SetArrayField(TEXT("modules"), Modules);
            if (Lod->bEnabled)
            {
                if (EmitterDuration < 0)
                    Duration = -1;
                else if (Duration >= 0)
                    Duration = FMath::Max(Duration, EmitterDuration);
                bDurationKnown = true;
            }
            Emitters.Add(MakeShared<FJsonValueObject>(Row));
        }
        Root->SetArrayField(TEXT("emitters"), Emitters);
    }
    else
        return Out;
    Root->SetNumberField(TEXT("duration_s"), bDurationKnown ? Duration : -2); // -2: no emitter said.
    Root->SetBoolField(TEXT("duration_known"), bDurationKnown);
    auto Writer = TJsonWriterFactory<>::Create(&Out);
    FJsonSerializer::Serialize(Root, Writer);
#endif
    return Out;
}

namespace
{
#if WITH_EDITOR
// Finds the exposed user parameter named Parameter (with or without the "User." prefix) of the given type on a
// prototype-folder system; null when the system is a vendor asset or the parameter is missing / another type.
const FNiagaraVariable *FindUserParameter(UNiagaraSystem *Effect, FName Parameter, const FNiagaraTypeDefinition &Type,
                                          TArray<FNiagaraVariable> &Storage)
{
    if (!Effect || !Effect->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/")))
        return nullptr;
    Effect->GetExposedParameters().GetParameters(Storage);
    const FString Wanted = Parameter.ToString();
    for (const auto &Variable : Storage)
    {
        const FString Name = Variable.GetName().ToString();
        if ((Name == Wanted || Name == TEXT("User.") + Wanted) && Variable.GetType() == Type)
            return &Variable;
    }
    return nullptr;
}
#endif
} // namespace

bool UHoverAuthoring::SetNiagaraUserColor(UNiagaraSystem *Effect, FName Parameter, FLinearColor Value)
{
#if WITH_EDITOR
    TArray<FNiagaraVariable> Storage;
    if (const auto *Variable = FindUserParameter(Effect, Parameter, FNiagaraTypeDefinition::GetColorDef(), Storage))
    {
        Effect->Modify();
        Effect->GetExposedParameters().SetParameterValue(Value, *Variable);
        Effect->MarkPackageDirty();
        return true;
    }
#endif
    return false;
}

bool UHoverAuthoring::SetNiagaraUserFloat(UNiagaraSystem *Effect, FName Parameter, float Value)
{
#if WITH_EDITOR
    TArray<FNiagaraVariable> Storage;
    if (const auto *Variable = FindUserParameter(Effect, Parameter, FNiagaraTypeDefinition::GetFloatDef(), Storage))
    {
        Effect->Modify();
        Effect->GetExposedParameters().SetParameterValue(Value, *Variable);
        Effect->MarkPackageDirty();
        return true;
    }
#endif
    return false;
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
            Report += TEXT("EMITTER ") + Handle.GetName().ToString() +
                      FString::Printf(TEXT(" enabled=%d local=%d sim=%d\n"), int32(Handle.GetIsEnabled()),
                                      int32(Data->bLocalSpace), int32(Data->SimTarget));
            for (auto *Renderer : Data->GetRenderers())
                if (auto *Sprite = Cast<UNiagaraSpriteRendererProperties>(Renderer))
                    Report += FString::Printf(TEXT("SPRITE enabled=%d material=%s alignment=%d facing=%d sort=%d priority=%d\n"),
                                              int32(Sprite->GetIsEnabled()), Sprite->Material ? *Sprite->Material->GetPathName() : TEXT("none"),
                                              int32(Sprite->Alignment), int32(Sprite->FacingMode), int32(Sprite->SortMode),
                                              Sprite->SortOrderHint);
                else if (Renderer)
                    Report += TEXT("RENDERER ") + Renderer->GetClass()->GetName() + TEXT("\n");
            TArray<UNiagaraScript *> Scripts;
            Data->GetScripts(Scripts);
            TSet<UNiagaraGraph *> Seen;
            for (auto *Script : Scripts)
            {
                DescribeStore(Script->RapidIterationParameters);
                if (Effect->GetName().StartsWith(TEXT("NS_GliderJet")) || Effect->GetName().StartsWith(TEXT("NS_PU_Live_Pop")))
                    if (auto *Source = Cast<UNiagaraScriptSource>(Script->GetLatestSource());
                        Source && Source->NodeGraph && !Seen.Contains(Source->NodeGraph))
                    {
                        Seen.Add(Source->NodeGraph);
                        for (UEdGraphNode *Node : Source->NodeGraph->Nodes)
                        {
                            Report += TEXT("NODE ") + Node->GetName() + TEXT(" ") +
                                      Node->GetNodeTitle(ENodeTitleType::ListView).ToString() +
                                      FString::Printf(TEXT(" enabled=%d\n"), int32(Node->GetDesiredEnabledState()));
                            for (const auto *Pin : Node->Pins)
                            {
                                Report += TEXT("  PIN ") + Pin->PinName.ToString() + TEXT(" = ") + Pin->DefaultValue;
                                for (const auto *Link : Pin->LinkedTo)
                                    Report += TEXT(" -> ") + Link->GetOwningNode()->GetName() + TEXT(".") +
                                              Link->PinName.ToString();
                                Report += TEXT("\n");
                            }
                        }
                    }
            }
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

int32 UHoverAuthoring::ConfigureGliderJet(UNiagaraSystem *Effect)
{
    int32 Changed = 0;
#if WITH_EDITOR
    if (!Effect || !Effect->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/NS_GliderJet")))
        return 0;
    Effect->Modify();
    Effect->GetExposedParameters().SetParameterValue(
        26.f, FNiagaraVariable(FNiagaraTypeDefinition::GetFloatDef(), TEXT("User.ThrustSize")));
    Effect->GetExposedParameters().SetParameterValue(
        260.f, FNiagaraVariable(FNiagaraTypeDefinition::GetFloatDef(), TEXT("User.ThurstSpawningRate")));
    Effect->GetExposedParameters().SetParameterValue(
        FLinearColor(.8f, .9f, 1.f, 1.f),
        FNiagaraVariable(FNiagaraTypeDefinition::GetColorDef(), TEXT("User.ThrustColor")));
    Effect->SetFixedBounds(FBox(FVector(-850, -100, -100), FVector(100, 100, 100)));
    for (auto &Handle : Effect->GetEmitterHandles())
    {
        // Ten nozzles do not need ten overlapping heat-distortion volumes.
        if (Handle.GetName() == TEXT("Heat") || Handle.GetName() == TEXT("Sparks") || Handle.GetName() == TEXT("Trail"))
        {
            Handle.SetIsEnabled(false, *Effect, false);
            continue;
        }
        auto *Data = Handle.GetEmitterData();
        if (!Data)
            continue;
        Data->bLocalSpace = true;
        for (auto *Renderer : Data->GetRenderers())
            if (auto *Sprite = Cast<UNiagaraSpriteRendererProperties>(Renderer))
            {
                if (auto *Material = LoadObject<UMaterialInterface>(
                        nullptr, TEXT("/Game/HoverPrototype/Effects/M_GliderJet_Core.M_GliderJet_Core")))
                    Sprite->Material = Material;
                Sprite->Alignment = ENiagaraSpriteAlignment::VelocityAligned;
                Sprite->FacingMode = ENiagaraSpriteFacingMode::FaceCamera;
                ++Changed;
            }
        if (Effect->GetName().EndsWith(TEXT("DebugCPU")))
            Data->SimTarget = ENiagaraSimTarget::CPUSim;
        TArray<UNiagaraScript *> Scripts;
        Data->GetScripts(Scripts);
        for (auto *Script : Scripts)
        {
            Script->Modify();
            if (auto *Source = Cast<UNiagaraScriptSource>(Script->GetLatestSource());
                Source && Source->NodeGraph && Source->GetOutermost() == Effect->GetOutermost())
            {
                auto *Graph = Source->NodeGraph.Get();
                for (UEdGraphNode *Node : Graph->Nodes)
                {
                    const FString Title = Node->GetNodeTitle(ENodeTitleType::ListView).ToString();
                    if (auto *Property = FindFProperty<FObjectPropertyBase>(Node->GetClass(), TEXT("DataInterface")))
                        if (auto *Curve =
                                Cast<UNiagaraDataInterfaceCurve>(Property->GetObjectPropertyValue_InContainer(Node));
                            Curve && Curve->GetOutermost() == Effect->GetOutermost())
                        {
                            const bool Size = Title.StartsWith(TEXT("ScaleSpriteSize."));
                            const bool Alpha = Title.StartsWith(TEXT("FloatFromCurve002."));
                            if (Size || Alpha)
                            {
                                Curve->Modify();
                                Curve->Curve.Reset();
                                Curve->Curve.AddKey(0.f, 1.f);
                                Curve->Curve.AddKey(.2f, 1.f);
                                Curve->Curve.AddKey(.65f, Size ? .4f : .6f);
                                Curve->Curve.AddKey(1.f, Size ? .05f : 0.f);
                                Curve->UpdateLUT();
                                static_cast<UEdGraph *>(Graph)->NotifyGraphChanged();
                                ++Changed;
                            }
                        }
                    if (Node->GetNodeTitle(ENodeTitleType::ListView).ToString() == TEXT("Solve Forces and Velocity") &&
                        Node->GetDesiredEnabledState() != ENodeEnabledState::Enabled)
                    {
                        Node->Modify();
                        Node->SetEnabledState(ENodeEnabledState::Enabled);
                        static_cast<UEdGraph *>(Graph)->NotifyGraphChanged();
                        ++Changed;
                    }
                    for (UEdGraphPin *Pin : Node->Pins)
                        if (Pin->PinName == TEXT("Write to Presolve Properties") && Pin->DefaultValue != TEXT("false"))
                        {
                            // The source defers integration into presolve fields. Our
                            // self-contained nozzle must write its actual position.
                            Graph->Modify();
                            Node->Modify();
                            Pin->DefaultValue = TEXT("false");
                            Node->PinDefaultValueChanged(Pin);
                            static_cast<UEdGraph *>(Graph)->NotifyGraphChanged();
                            ++Changed;
                        }
                }
            }
            auto &Store = Script->RapidIterationParameters;
            TArray<FNiagaraVariable> Variables;
            Store.GetParameters(Variables);
            for (const auto &Variable : Variables)
            {
                const FString Name = Variable.GetName().ToString();
                if (Variable.GetType() == FNiagaraTypeDefinition::GetFloatDef())
                {
                    TOptional<float> Value;
                    if (Name.EndsWith(TEXT("AddVelocity.Cone Angle")))
                        Value = .8f;
                    else if (Name.EndsWith(TEXT("RandomRangeFloat.Minimum")))
                        Value = 900.f;
                    else if (Name.EndsWith(TEXT("RandomRangeFloat.Maximum")))
                        Value = 1000.f;
                    else if (Name.EndsWith(TEXT("InitializeParticle.Lifetime Min")))
                        Value = .25f;
                    else if (Name.EndsWith(TEXT("InitializeParticle.Lifetime Max")))
                        Value = .33f;
                    else if (Name.EndsWith(TEXT("InitializeParticle.Lifetime")))
                        Value = .29f;
                    else if (Name.EndsWith(TEXT("InitializeParticle.Uniform Sprite Size Min")))
                        Value = .9f;
                    else if (Name.EndsWith(TEXT("InitializeParticle.Uniform Sprite Size Max")))
                        Value = 1.1f;
                    else if (Name.Contains(TEXT("InitializeParticle.Sprite Rotation Angle")))
                        Value = 0.f;
                    else if (Name.EndsWith(TEXT("CurlNoiseForce.Noise Strength")))
                        Value = 0.f;
                    else if (Name.EndsWith(TEXT("ShapeLocation.Sphere Radius")))
                        Value = 1.5f;
                    if (Value.IsSet())
                    {
                        Store.SetParameterValue(Value.GetValue(), Variable);
                        ++Changed;
                    }
                }
                else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec3Def() &&
                         Name.EndsWith(TEXT("AddVelocity.Velocity")))
                {
                    Store.SetParameterValue(FVector3f(-550, 0, 0), Variable);
                    ++Changed;
                }
                else if (Variable.GetType() == FNiagaraTypeDefinition::GetVec3Def() &&
                         Name.EndsWith(TEXT("ShapeLocation.Box Size")))
                {
                    Store.SetParameterValue(FVector3f(2, 1, 1), Variable);
                    ++Changed;
                }
            }
            Script->InvalidateCompileResults(TEXT("Local directional jet tuning"));
        }
    }
    Effect->RequestCompile(true);
    Effect->WaitForCompilationComplete();
    Effect->MarkPackageDirty();
#endif
    return Changed;
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

FString UHoverAuthoring::ConfigurePowerUpLiveEffect(UNiagaraSystem *Effect, const FString &KeepEmitter,
                                                   UMaterialInterface *SpriteMaterial, bool bVelocityAligned,
                                                   const TMap<FString, FString> &Values)
{
    FString Report;
#if WITH_EDITOR
    // AFS 2026-10-31: only our template copies for the live power-up displays.
    if (!Effect || !Effect->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/Effects/PowerUps/Live/")))
        return TEXT("Refused: only /Game/HoverPrototype/Effects/PowerUps/Live/ copies may be edited");
    Effect->Modify();
    TSet<FString> Used;
    auto Apply = [&](UNiagaraScript *Script, const FString &Where, const FString &OnlyEmitter, bool bListSys) {
        if (!Script)
            return;
        Script->Modify();
        auto &Store = Script->RapidIterationParameters;
        TArray<FNiagaraVariable> Vars;
        Store.GetParameters(Vars);
        bool bChanged = false;
        for (const auto &V : Vars)
        {
            const FString Name = V.GetName().ToString();
            if (!OnlyEmitter.IsEmpty() && !Name.Contains(TEXT(".") + OnlyEmitter + TEXT(".")))
                continue;
            if (bListSys)
                Report += FString::Printf(TEXT("SYS %s %s\n"), *Name, *V.GetType().GetName());
            for (const auto &KV : Values)
            {
                if (!Name.EndsWith(KV.Key))
                    continue;
                const FNiagaraTypeDefinition &T = V.GetType();
                TArray<FString> P;
                KV.Value.ParseIntoArray(P, TEXT(","));
                if (P.Num() == 0)
                    continue;
                auto F = [&P](int32 I) { return P.IsValidIndex(I) ? FCString::Atof(*P[I].TrimStartAndEnd()) : 0.f; };
                bool bOk = true;
                if (T == FNiagaraTypeDefinition::GetFloatDef())
                    Store.SetParameterValue(F(0), V);
                else if (T == FNiagaraTypeDefinition::GetIntDef())
                    Store.SetParameterValue(int32(FCString::Atoi(*P[0].TrimStartAndEnd())), V);
                else if (T == FNiagaraTypeDefinition::GetBoolDef())
                {
                    FNiagaraBool B;
                    B.SetValue(P[0].TrimStartAndEnd().ToBool());
                    Store.SetParameterValue(B, V);
                }
                else if (T == FNiagaraTypeDefinition::GetVec2Def())
                    Store.SetParameterValue(FVector2f(F(0), F(1)), V);
                else if (T == FNiagaraTypeDefinition::GetVec3Def())
                    Store.SetParameterValue(FVector3f(F(0), F(1), F(2)), V);
                else if (T == FNiagaraTypeDefinition::GetVec4Def())
                    Store.SetParameterValue(FVector4f(F(0), F(1), F(2), F(3)), V);
                else if (T == FNiagaraTypeDefinition::GetColorDef())
                    Store.SetParameterValue(FLinearColor(F(0), F(1), F(2), P.Num() > 3 ? F(3) : 1.f), V);
                else
                    bOk = false;
                if (bOk)
                {
                    Used.Add(KV.Key);
                    bChanged = true;
                    Report += FString::Printf(TEXT("SET %s %s = %s\n"), *Where, *Name, *KV.Value);
                }
                else
                    Report += FString::Printf(TEXT("TYPE %s %s %s\n"), *Where, *Name, *T.GetName());
            }
        }
        if (bChanged)
            Script->InvalidateCompileResults(TEXT("AFS power-up live tuning"));
    };
    for (auto &Handle : Effect->GetEmitterHandles())
    {
        const FString EName = Handle.GetName().ToString();
        if (!KeepEmitter.IsEmpty() && EName != KeepEmitter)
        {
            Handle.SetIsEnabled(false, *Effect, false);
            Report += TEXT("DISABLED ") + EName + TEXT("\n");
            continue;
        }
        auto *Data = Handle.GetEmitterData();
        if (!Data)
            continue;
        Data->bLocalSpace = false;
        for (auto *Renderer : Data->GetRenderers())
            if (auto *Sprite = Cast<UNiagaraSpriteRendererProperties>(Renderer))
            {
                Sprite->Modify();
                if (SpriteMaterial)
                    Sprite->Material = SpriteMaterial;
                if (bVelocityAligned)
                {
                    Sprite->Alignment = ENiagaraSpriteAlignment::VelocityAligned;
                    Sprite->FacingMode = ENiagaraSpriteFacingMode::FaceCamera;
                }
                Report += TEXT("SPRITE ") + EName + TEXT("\n");
            }
        TArray<UNiagaraScript *> Scripts;
        // bCompilableOnly = false: include the emitter spawn / update scripts. Their rapid-iteration values (the
        // Spawn Burst count, emitter state) are copied over the system scripts' copies when the system compiles, so
        // setting only the system copy left every burst at the template's 20 particles (fix round 2026-10-31).
        Data->GetScripts(Scripts, false);
        for (auto *Script : Scripts)
            Apply(Script, EName, FString(), false);
    }
    Apply(Effect->GetSystemSpawnScript(), TEXT("SystemSpawn"), KeepEmitter, true);
    Apply(Effect->GetSystemUpdateScript(), TEXT("SystemUpdate"), KeepEmitter, true);
    for (const auto &KV : Values)
        if (!Used.Contains(KV.Key))
            Report += TEXT("MISSING ") + KV.Key + TEXT("\n");
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

bool UHoverAuthoring::ConfigureCreatureLODs(USkeletalMesh *Mesh)
{
#if WITH_EDITOR
    // Only isolated runtime candidates may be reduced; never touch source art.
    if (!Mesh || !Mesh->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/ZombieEngine/Variants/")) ||
        !Mesh->GetPathName().Contains(TEXT("/Optimized/")) || Mesh->GetLODNum() < 4)
        return false;
    Mesh->Modify();
    const float Ratios[] = {1.f, .55f, .25f, .12f};
    const float Screens[] = {1.f, .45f, .20f, .08f};
    for (int32 I = 1; I < 4; ++I)
    {
        auto *Info = Mesh->GetLODInfo(I);
        Info->ScreenSize.Default = Screens[I];
        Info->LODHysteresis = .03f;
        auto &Reduction = Info->ReductionSettings;
        Reduction.TerminationCriterion = SMTC_NumOfTriangles;
        Reduction.NumOfTrianglesPercentage = Ratios[I];
        Reduction.NumOfVertPercentage = Ratios[I];
        Reduction.BaseLOD = 0;
        Reduction.MaxBonesPerVertex = 8;
        Reduction.bEnforceBoneBoundaries = true;
        Reduction.bMergeCoincidentVertBones = true;
        Reduction.bRecalcNormals = false;
        Reduction.bRemapMorphTargets = true;
    }
    Mesh->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

FString UHoverAuthoring::InspectCharacterMesh(USkeletalMesh *Mesh)
{
    FString Result;
#if WITH_EDITOR
    if (Mesh && Mesh->GetResourceForRendering() && Mesh->GetResourceForRendering()->LODRenderData.Num())
    {
        int32 Index = 0;
        for (const auto &Level : Mesh->GetResourceForRendering()->LODRenderData)
        {
            uint32 Triangles = 0;
            for (const auto &Section : Level.RenderSections)
                Triangles += Section.NumTriangles;
            Result +=
                FString::Printf(TEXT("LOD=%d triangles=%u vertices=%u\n"), Index++, Triangles, Level.GetNumVertices());
        }
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

TArray<FVector> UHoverAuthoring::SkeletalMeshVertexPositions(USkeletalMesh *Mesh, int32 LOD)
{
    TArray<FVector> Out;
    const FSkeletalMeshRenderData *Render = Mesh ? Mesh->GetResourceForRendering() : nullptr;
    if (!Render || !Render->LODRenderData.IsValidIndex(LOD))
        return Out;
    const auto &Positions = Render->LODRenderData[LOD].StaticVertexBuffers.PositionVertexBuffer;
    Out.Reserve(Positions.GetNumVertices());
    for (uint32 V = 0; V < Positions.GetNumVertices(); ++V)
        Out.Add(FVector(Positions.VertexPosition(V)));
    return Out;
}

TArray<FName> UHoverAuthoring::SkeletalMeshVertexBones(USkeletalMesh *Mesh, int32 LOD)
{
    TArray<FName> Out;
    const FSkeletalMeshRenderData *Render = Mesh ? Mesh->GetResourceForRendering() : nullptr;
    if (!Render || !Render->LODRenderData.IsValidIndex(LOD))
        return Out;
    const auto &Level = Render->LODRenderData[LOD];
    const auto &Weights = Level.SkinWeightVertexBuffer;
    Out.Init(NAME_None, Level.GetNumVertices());
    for (const auto &Section : Level.RenderSections)
        for (uint32 V = Section.BaseVertexIndex; V < Section.BaseVertexIndex + Section.NumVertices; ++V)
        {
            uint16 Best = 0;
            int32 BestBone = INDEX_NONE;
            for (uint32 I = 0; I < Weights.GetMaxBoneInfluences(); ++I)
                if (Weights.GetBoneWeight(V, I) > Best)
                {
                    Best = Weights.GetBoneWeight(V, I);
                    BestBone = Weights.GetBoneIndex(V, I);
                }
            if (BestBone != INDEX_NONE && Section.BoneMap.IsValidIndex(BestBone) && Out.IsValidIndex(V))
                Out[V] = Mesh->GetRefSkeleton().GetBoneName(Section.BoneMap[BestBone]);
        }
    return Out;
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
                        if (Emitter->GetSimTarget() == ENiagaraSimTarget::CPUSim &&
                            (Emitter->GetEmitterHandle().GetName() == TEXT("Dust") ||
                             Emitter->GetEmitterHandle().GetName() == TEXT("Thrust") ||
                             Emitter->GetEmitterHandle().GetName() == TEXT("Trail")))
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

FString UHoverAuthoring::InspectActiveEffects(const FString &AssetContains)
{
    FString Report;
#if WITH_EDITOR
    UWorld *World = GetPlaytestWorld();
    if (!World)
        return TEXT("No play world");
    for (TObjectIterator<UNiagaraComponent> It; It; ++It)
    {
        if (It->GetWorld() != World || !It->IsActive() || !GetNameSafe(It->GetAsset()).Contains(AssetContains))
            continue;
        auto Controller = It->GetSystemInstanceController();
        Report += FString::Printf(TEXT("%s %s age=%.3f position=%s bounds=%s visible=%d\n"), *It->GetName(),
                                  *GetNameSafe(It->GetAsset()), Controller.IsValid() ? Controller->GetAge() : -1.f,
                                  *It->GetComponentLocation().ToString(), *It->Bounds.GetBox().ToString(),
                                  int32(It->IsVisible()));
        if (!Controller.IsValid())
            continue;
        if (auto *Instance = Controller->GetSystemInstance_Unsafe())
        {
            Instance->WaitForConcurrentTickAndFinalize();
            for (const auto &Emitter : Instance->GetEmitters())
            {
                Report += FString::Printf(TEXT("  %s particles=%d\n"), *Emitter->GetEmitterHandle().GetName().ToString(),
                                          Emitter->GetNumParticles());
                if (Emitter->GetSimTarget() == ENiagaraSimTarget::CPUSim)
                    if (const auto *Buffer = Emitter->GetParticleData().GetCurrentData(); Buffer && Buffer->GetNumInstances() > 0)
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

TArray<FTransform> UHoverAuthoring::SampleClipBone(UAnimSequence *Sequence, FName Bone, const TArray<float> &Times)
{
    TArray<FTransform> Out;
    if (!Sequence || !Sequence->GetSkeleton())
        return Out;
    const FReferenceSkeleton &Ref = Sequence->GetSkeleton()->GetReferenceSkeleton();
    const int32 Index = Ref.FindBoneIndex(Bone);
    if (Index == INDEX_NONE)
        return Out;
    if (!ClipHasBoneTrack(Sequence, Bone))
    {
        for (int32 I = 0; I < Times.Num(); ++I)
            Out.Add(Ref.GetRefBonePose()[Index]);
        return Out;
    }
    for (const float Time : Times)
    {
        FTransform Atom;
        Sequence->GetBoneTransform(Atom, FSkeletonPoseBoneIndex(Index), FAnimExtractContext(static_cast<double>(Time)),
                                   true);
        Out.Add(Atom);
    }
    return Out;
}

bool UHoverAuthoring::ClipHasBoneTrack(UAnimSequence *Sequence, FName Bone)
{
#if WITH_EDITOR
    if (!Sequence || !Sequence->GetDataModel())
        return false;
    return Sequence->GetDataModel()->IsValidBoneTrackName(Bone);
#else
    return false;
#endif
}

FString UHoverAuthoring::DescribeSequenceOnMesh(UAnimSequence *Sequence, USkeletalMesh *Mesh, float Time,
                                                const TArray<FName> &Bones)
{
    if (!Sequence || !Mesh || !Mesh->GetSkeleton() || !Sequence->GetSkeleton())
        return TEXT("{\"error\": \"null sequence, mesh or skeleton\"}");
    USkeleton *MeshSkeleton = Mesh->GetSkeleton();
    USkeleton *SequenceSkeleton = Sequence->GetSkeleton();
    const FReferenceSkeleton &Ref = Mesh->GetRefSkeleton();
    // Track bones the mesh skeleton has no bone for: the engine's name remapping drops them silently.
    TArray<FString> Missing;
    int32 Tracks = 0;
#if WITH_EDITOR
    if (Sequence->GetDataModel())
    {
        TArray<FName> Names;
        Sequence->GetDataModel()->GetBoneTrackNames(Names);
        Tracks = Names.Num();
        for (const FName &Name : Names)
            if (Ref.FindBoneIndex(Name) == INDEX_NONE)
                Missing.Add(FString::Printf(TEXT("\"%s\""), *Name.ToString()));
    }
#endif
    // Sample through the runtime path: every mesh bone required, the mesh's own skeleton as the target, so a
    // sequence on another skeleton goes through FSkeletonRemapping exactly as FAnimNode_SequencePlayer does.
    // FCompactPose and FBlendedCurve allocate from the anim mem stack, which asserts without a mark in scope
    // (the anim graph provides one per evaluation; this is a plain editor call).
    FMemMark Mark(FMemStack::Get());
    TArray<FBoneIndexType> Required;
    for (int32 Index = 0; Index < Ref.GetNum(); ++Index)
        Required.Add(static_cast<FBoneIndexType>(Index));
    FBoneContainer Container;
    Container.InitializeTo(Required, UE::Anim::FCurveFilterSettings(), *Mesh);
    FCompactPose Pose;
    Pose.SetBoneContainer(&Container);
    FBlendedCurve Curve;
    Curve.InitFrom(Container);
    UE::Anim::FStackAttributeContainer Attributes;
    FAnimationPoseData PoseData(Pose, Curve, Attributes);
    Sequence->GetAnimationPose(PoseData, FAnimExtractContext(static_cast<double>(Time)));
    int32 Moved = 0;
    TArray<FTransform> ComponentSpace;
    ComponentSpace.SetNum(Pose.GetNumBones());
    for (int32 Index = 0; Index < Pose.GetNumBones(); ++Index)
    {
        const FCompactPoseBoneIndex Bone(Index);
        const FTransform &Local = Pose[Bone];
        const FTransform &RefLocal = Container.GetRefPoseTransform(Bone);
        if (!Local.GetLocation().Equals(RefLocal.GetLocation(), .05f) ||
            !Local.GetRotation().Equals(RefLocal.GetRotation(), .001f))
            ++Moved;
        const FCompactPoseBoneIndex Parent = Container.GetParentBoneIndex(Bone);
        ComponentSpace[Index] = Parent.IsValid() ? Local * ComponentSpace[Parent.GetInt()] : Local;
    }
    TArray<FString> Locations;
    for (const FName &Name : Bones)
    {
        const int32 Index = Ref.FindBoneIndex(Name);
        if (Index == INDEX_NONE || !ComponentSpace.IsValidIndex(Index))
            continue;
        const FVector L = ComponentSpace[Index].GetLocation();
        Locations.Add(FString::Printf(TEXT("\"%s\": [%.2f, %.2f, %.2f]"), *Name.ToString(), L.X, L.Y, L.Z));
    }
    // The editor's asset-picker rule (CompatibleSkeletons list) each way; the runtime players do not use it.
    return FString::Printf(
        TEXT("{\"sequence\": \"%s\", \"sequence_skeleton\": \"%s\", \"mesh\": \"%s\", \"mesh_skeleton\": \"%s\", "
             "\"same_skeleton\": %s, \"mesh_skeleton_accepts_sequence_skeleton\": %s, "
             "\"sequence_skeleton_accepts_mesh_skeleton\": %s, \"track_bones\": %d, "
             "\"track_bones_missing_on_mesh\": [%s], \"mesh_bones\": %d, \"bones_off_reference_pose\": %d, "
             "\"time\": %.3f, \"component_space_cm\": {%s}}"),
        *Sequence->GetPathName(), *SequenceSkeleton->GetPathName(), *Mesh->GetPathName(),
        *MeshSkeleton->GetPathName(), MeshSkeleton == SequenceSkeleton ? TEXT("true") : TEXT("false"),
        MeshSkeleton->IsCompatibleForEditor(SequenceSkeleton) ? TEXT("true") : TEXT("false"),
        SequenceSkeleton->IsCompatibleForEditor(MeshSkeleton) ? TEXT("true") : TEXT("false"), Tracks,
        *FString::Join(Missing, TEXT(", ")), Pose.GetNumBones(), Moved, Time, *FString::Join(Locations, TEXT(", ")));
}

FString UHoverAuthoring::MakeFrameAdditive(UAnimSequence *Sequence, int32 RefFrame)
{
    if (!Sequence)
        return TEXT("{\"ok\": false, \"error\": \"null sequence\"}");
#if WITH_EDITOR
    Sequence->Modify();
    Sequence->AdditiveAnimType = AAT_LocalSpaceBase;
    Sequence->RefPoseType = ABPT_AnimFrame;
    Sequence->RefFrameIndex = FMath::Max(0, RefFrame);
    // ABPT_AnimFrame reads the base frame from RefPoseSeq and IsValidAdditive() demands one; the clip itself is the
    // base (the CLS MM_*_Fire sources are built the same way, self-referenced at their rest frame).
    Sequence->RefPoseSeq = Sequence;
    // Same path the details panel takes: PostEditChangeProperty on the additive settings invalidates the
    // compressed data and rebuilds it (baked additive) before the asset is saved.
    for (const TCHAR *Name : {TEXT("AdditiveAnimType"), TEXT("RefPoseType"), TEXT("RefFrameIndex"), TEXT("RefPoseSeq")})
        if (FProperty *Property = UAnimSequence::StaticClass()->FindPropertyByName(Name))
        {
            FPropertyChangedEvent Event(Property, EPropertyChangeType::ValueSet);
            Sequence->PostEditChangeProperty(Event);
        }
    Sequence->MarkPackageDirty();
#endif
    return FString::Printf(TEXT("{\"ok\": %s, \"additive_anim_type\": %d, \"ref_pose_type\": %d, \"ref_frame_index\": %d, "
                                "\"is_valid_additive\": %s, \"length_s\": %.4f, \"frames\": %d}"),
                           Sequence->IsValidAdditive() ? TEXT("true") : TEXT("false"), int32(Sequence->AdditiveAnimType),
                           int32(Sequence->RefPoseType), Sequence->RefFrameIndex,
                           Sequence->IsValidAdditive() ? TEXT("true") : TEXT("false"), Sequence->GetPlayLength(),
                           Sequence->GetNumberOfSampledKeys());
}

bool UHoverAuthoring::IsValidAdditive(UAnimSequence *Sequence)
{
    return Sequence && Sequence->IsValidAdditive();
}

FString UHoverAuthoring::MeasureFrameLuminance(const FString &Filename, float CentralFraction)
{
    FImage Image;
    if (!FImageUtils::LoadImage(*Filename, Image) || Image.GetWidth() <= 0 || Image.GetHeight() <= 0)
        return FString::Printf(TEXT("{\"ok\": false, \"error\": \"load failed\", \"file\": \"%s\"}"), *Filename);
    // The capture is written from the back buffer as 8-bit BGRA; measure on those stored values (the viewer sees
    // them), not linear light, so a saturated pixel is one the screen shows as white.
    FImage Pixels;
    Image.CopyTo(Pixels, ERawImageFormat::BGRA8, EGammaSpace::sRGB);
    const int32 W = Pixels.GetWidth(), H = Pixels.GetHeight();
    const float Frac = FMath::Clamp(CentralFraction, .05f, 1.f);
    const int32 X0 = FMath::RoundToInt(W * (1 - Frac) * .5f), X1 = W - X0;
    const int32 Y0 = FMath::RoundToInt(H * (1 - Frac) * .5f), Y1 = H - Y0;
    const TArrayView64<FColor> Colors = Pixels.AsBGRA8();
    double Sum = 0;
    int64 Count = 0, Saturated = 0;
    for (int32 Y = Y0; Y < Y1; ++Y)
        for (int32 X = X0; X < X1; ++X)
        {
            const FColor &C = Colors[int64(Y) * W + X];
            Sum += .2126 * C.R + .7152 * C.G + .0722 * C.B;
            Saturated += (C.R > 245 && C.G > 245 && C.B > 245) ? 1 : 0;
            ++Count;
        }
    return FString::Printf(TEXT("{\"ok\": true, \"width\": %d, \"height\": %d, \"central_fraction\": %.2f, "
                                "\"mean_luma\": %.3f, \"saturated_fraction\": %.5f, \"pixels\": %lld}"),
                           W, H, Frac, Count ? Sum / Count : 0.0, Count ? double(Saturated) / Count : 0.0, Count);
}

bool UHoverAuthoring::SetSupportHandOverride(AHoverPilot *Pilot, bool bEnabled, FRotator GunSpaceDelta, float Curl)
{
#if WITH_EDITOR
    if (!Pilot)
        return false;
    Pilot->bSupportHandOverride = bEnabled;
    Pilot->SupportHandOverrideRotation = GunSpaceDelta.Quaternion();
    Pilot->SupportHandOverrideCurl = FMath::Clamp(Curl, 0.f, 1.6f);
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

// ---------------------------------------------------------------------------------------------
// NYC zombie diversity helpers (Scripts/AuthorZombieDiversity.py, 2026-10-31).

bool UHoverAuthoring::MakeSkeletonCompatible(USkeleton *Target, USkeleton *Source)
{
#if WITH_EDITOR
    // Only owned skeletons are edited; the pack skeletons stay as shipped (the script duplicates a pack body
    // and its skeleton first when it needs one).
    if (!Target || !Source || Target == Source || !Target->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")))
        return false;
    const FReferenceSkeleton &Reference = Target->GetReferenceSkeleton();
    if (Reference.GetNum() == 0)
        return false;
    const FSoftObjectPath SourcePath(Source);
    auto IsListed = [&]() {
        for (const TSoftObjectPtr<USkeleton> &Listed : Target->GetCompatibleSkeletons())
            if (Listed.ToSoftObjectPath() == SourcePath)
                return true;
        return false;
    };
    const int32 Pelvis = Reference.FindBoneIndex(TEXT("pelvis"));
    auto Wanted = [Pelvis](int32 Bone) {
        return Bone == 0        ? EBoneTranslationRetargetingMode::Animation
               : Bone == Pelvis ? EBoneTranslationRetargetingMode::AnimationScaled
                                : EBoneTranslationRetargetingMode::Skeleton;
    };
    bool bModesHold = true;
    for (int32 Bone = 0; Bone < Reference.GetNum() && bModesHold; ++Bone)
        bModesHold = Target->GetBoneTranslationRetargetingMode(Bone) == Wanted(Bone);
    if (IsListed() && bModesHold)
        return true;
    Target->Modify();
    if (!IsListed())
        Target->AddCompatibleSkeleton(Source);
    if (!bModesHold)
    {
        Target->SetBoneTranslationRetargetingMode(0, EBoneTranslationRetargetingMode::Skeleton, true);
        Target->SetBoneTranslationRetargetingMode(0, EBoneTranslationRetargetingMode::Animation);
        if (Pelvis != INDEX_NONE)
            Target->SetBoneTranslationRetargetingMode(Pelvis, EBoneTranslationRetargetingMode::AnimationScaled);
    }
    Target->MarkPackageDirty();
    return IsListed();
#else
    return false;
#endif
}

bool UHoverAuthoring::BuildSpeedBlend1D(UBlendSpace *Blend, const TArray<UAnimSequence *> &Clips,
                                        const TArray<float> &Speeds, float MaxSpeed)
{
#if WITH_EDITOR
    if (!Blend || !Blend->IsA<UBlendSpace1D>() || !Blend->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")) ||
        Clips.IsEmpty() || Clips.Num() != Speeds.Num() || MaxSpeed <= 0.f)
        return false;
    for (int32 I = 0; I < Clips.Num(); ++I)
        if (!Clips[I] || !Clips[I]->GetSkeleton() || Speeds[I] < 0.f || Speeds[I] > MaxSpeed)
            return false;
    auto *Property = FindFProperty<FStructProperty>(Blend->GetClass(), TEXT("BlendParameters"));
    if (!Property)
        return false;
    Blend->Modify();
    Blend->SetSkeleton(Clips[0]->GetSkeleton());
    while (Blend->GetNumberOfBlendSamples())
        Blend->DeleteSample(Blend->GetNumberOfBlendSamples() - 1);
    // Axis first: AddSample rejects values outside the axis range.
    auto *Speed = Property->ContainerPtrToValuePtr<FBlendParameter>(Blend, 0);
    Speed->DisplayName = TEXT("Speed");
    Speed->Min = 0.f;
    Speed->Max = MaxSpeed;
    Speed->GridNum = 4;
    Speed->bSnapToGrid = false;
    Speed->bWrapInput = false;
    for (int32 I = 0; I < Clips.Num(); ++I)
        if (Blend->AddSample(Clips[I], FVector(Speeds[I], 0.f, 0.f)) == INDEX_NONE)
        {
            UE_LOG(LogTemp, Warning, TEXT("HOVER_AUTHOR BuildSpeedBlend1D %s rejected %s at %.1f"), *Blend->GetName(),
                   *Clips[I]->GetPathName(), Speeds[I]);
            return false;
        }
    Blend->TargetWeightInterpolationSpeedPerSec = 5.f;
    Blend->ValidateSampleData();
    Blend->ResampleData();
    Blend->PostEditChange();
    Blend->MarkPackageDirty();
    return Blend->GetNumberOfBlendSamples() == Clips.Num();
#else
    return false;
#endif
}

bool UHoverAuthoring::SetMontageSlot(UAnimMontage *Montage, FName Slot)
{
#if WITH_EDITOR
    if (!Montage || Slot.IsNone() || !Montage->GetPathName().StartsWith(TEXT("/Game/HoverPrototype/")) ||
        Montage->SlotAnimTracks.IsEmpty())
        return false;
    if (Montage->SlotAnimTracks[0].SlotName == Slot)
        return true;
    Montage->Modify();
    Montage->SlotAnimTracks[0].SlotName = Slot;
    Montage->PostEditChange();
    Montage->MarkPackageDirty();
    return Montage->SlotAnimTracks[0].SlotName == Slot;
#else
    return false;
#endif
}
