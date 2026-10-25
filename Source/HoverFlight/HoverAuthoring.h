#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "HoverAuthoring.generated.h"
class UNiagaraSystem;

UCLASS()
class HOVERFLIGHT_API UHoverAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
  public:
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeBlueprint(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TMap<FString, FString> DescribeObjectProperties(UObject *Object);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool PreserveMeshUserData(USkeletalMesh *Source, USkeletalMesh *Target);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SetCyberZombieSkeleton(USkeletalMesh *Mesh, class USkeleton *Skeleton);
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static bool ConfigureVariantSkeleton(USkeletalMesh *Mesh, class USkeleton *AnimationSkeleton);
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static class UPhysicsAsset *CreateVariantPhysics(USkeletalMesh *Mesh);
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static UObject *GetLocalAnimationController(class UAnimSequence *Sequence);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConfigureCityStartingGear(class UZE_WaveGameModeSettings *Settings);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool IntegrateParkourBlueprint(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool RepairParkourTransitions(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool BuildRideBlend(class UBlendSpace *Blend, const TArray<class UAnimSequence *> &Clips,
                               const TArray<FVector> &Coordinates);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void StartPlaytest();
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static UWorld *GetPlaytestWorld();
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void TestKey(APlayerController *Controller, FName Key, float Value, bool bAnalog = false);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void IsolateTestInput(APlayerController *Controller);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void SetPlaytestFixedStep(bool bEnabled);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static AActor *SpawnTestPlatform(FVector Location);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static AActor *SpawnPlaytestActor(TSubclassOf<AActor> ActorClass, FTransform Transform);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FVector> FindLightingReviewLocations(UWorld *World, FVector Origin);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool AddCityNavigation(UWorld *World, FVector Center, FVector Size);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribePartitionNavigation(UWorld *World, bool EnableLakesideStreaming = false);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FVector> FindCompleteCityPath(UWorld *World, FVector Start, FVector End);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString ConfigurePrototypeEffect(UNiagaraSystem *Effect, float SpriteScale, bool LocalSpace);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 ConfigureGliderJet(UNiagaraSystem *Effect);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 ConfigureSurfaceImpact(UNiagaraSystem *Effect, class UMaterialInterface *DustMaterial);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeNiagaraEffect(UNiagaraSystem *Effect);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void PrepareReviewEffects(const TArray<UNiagaraSystem *> &Effects);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectReviewEffects();
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void CapturePlaytest(const FString &Filename);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void CaptureWorldFrame(const FString &Filename);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectCharacterMesh(USkeletalMesh *Mesh);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConfigureCreatureLODs(USkeletalMesh *Mesh);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectTexture(class UTexture2D *Texture);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 RemapAppearanceAsset(UObject *Asset, const TArray<UObject *> &Sources,
                                      const TArray<UObject *> &Copies);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConvertAppearanceTextures(const TArray<class UTexture2D *> &Textures,
                                          const TArray<class UMaterial *> &Materials);
};
