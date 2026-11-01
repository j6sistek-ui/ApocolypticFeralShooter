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
    // Owned wave assets under /Game/HoverPrototype/ZombieEngine/ or /Game/HoverPrototype/NYC/. The
    // defaults are the Cyber City kit; DA_NYCWaves passes 270 / 2.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConfigureCityStartingGear(class UZE_WaveGameModeSettings *Settings, int32 AmmoQuantity = 120,
                                          int32 GrenadeCount = 0, bool bWithSidearm = false);
    // UHoverPilotAssets::GunRigs entry for a weapon definition (owned /Game/HoverPrototype/ assets only).
    // The key is normalized (UHoverGunRig::NormalizeWeaponKey) unless bExactKey; a null Rig stores a None
    // value, which pins that definition to the static Ballista. Returns the stored key, None on failure.
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static FName BindGunRig(class UHoverPilotAssets *Assets, FName WeaponKey, class UHoverGunRig *Rig,
                            bool bExactKey = false);
    // Removes the key (exact as given); the definition then falls back to the default rig.
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static bool UnbindGunRig(class UHoverPilotAssets *Assets, FName WeaponKey);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool IntegrateParkourBlueprint(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool RepairParkourTransitions(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool BuildRideBlend(class UBlendSpace *Blend, const TArray<class UAnimSequence *> &Clips,
                               const TArray<FVector> &Coordinates);
    // PIE in a new window of the given size (1280x720 by default; capture scripts pass 1920x1080).
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void StartPlaytest(int32 Width = 1280, int32 Height = 720);
    // -RenderOffscreen runs on FNullApplication, whose virtual work area is 1280x720 and clamps every new
    // window (a 1920x1080 PIE request came out 1274x682). Widen it before StartPlaytest; returns the area.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString ConfigureOffscreenDisplay(int32 Width = 1936, int32 Height = 1160);
    // Client size of the PIE window (the Slate title bar sits inside it); returns the new client size.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FIntPoint ResizePlaytestWindow(int32 Width, int32 Height);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FIntPoint GetPlaytestViewportSize();
    // AFS 2026-10-31: switch every level editor viewport client to realtime (or back) so the editor world ticks with
    // LEVELTICK_ViewportsOnly (actors that ShouldTickIfViewportsOnly animate without Play). Returns one line per client.
    // bKeepTickingInBackground also turns off "Use Less CPU when in Background" for this session (not saved).
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString SetLevelViewportsRealtime(bool bRealtime, bool bKeepTickingInBackground = false);
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
    static bool AddCityNavigation(UWorld *World, FVector Center, FVector Size, bool bDynamicModifiersOnly = false);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribePartitionNavigation(UWorld *World, bool EnableLakesideStreaming = false);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FVector> FindCompleteCityPath(UWorld *World, FVector Start, FVector End);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString ConfigureCityNavMesh(UWorld *World, float TileSizeUU, float CellSize, float AgentMaxStepHeight,
                                        int32 TilePoolSize);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static AActor *AddSurvivalActor(UWorld *World, TSubclassOf<AActor> ActorClass, FTransform Transform,
                                    const FString &Label, const TArray<FName> &Tags);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static AActor *AddZoneVolume(UWorld *World, FName ZoneId, int32 Order, FVector Center, FVector Size);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeStreamingLevels(UWorld *World);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SaveSurvivalMap(UWorld *World);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString ConfigurePrototypeEffect(UNiagaraSystem *Effect, float SpriteScale, bool LocalSpace);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 ConfigureGliderJet(UNiagaraSystem *Effect);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 ConfigureSurfaceImpact(UNiagaraSystem *Effect, class UMaterialInterface *DustMaterial);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeNiagaraEffect(UNiagaraSystem *Effect);
    // JSON for Scripts/InventoryMuzzleFlashes.py: a UNiagaraSystem's exposed user parameters (name, type, value
    // for float/int/bool/color/vec2/vec3/enum) and per-emitter loop / lifetime / colour / size constants read from
    // the rapid-iteration stores (module inputs, read-only here), or a legacy UParticleSystem's emitters
    // (duration, loops, lifetime range, module classes); either way an estimated duration in seconds
    // ("duration_s", -1 for a looping system). Empty for anything else.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString DescribeFlashAsset(UObject *Asset);
    // Sets an exposed USER parameter default on a /Game/HoverPrototype/Effects/ Niagara system (a duplicate
    // the inventory made, never a vendor asset) and marks it dirty; false when the parameter is missing or
    // its type does not match. Emitter internals are not touched.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SetNiagaraUserColor(UNiagaraSystem *Effect, FName Parameter, FLinearColor Value);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SetNiagaraUserFloat(UNiagaraSystem *Effect, FName Parameter, float Value);
    // AFS 2026-10-31 (live power-up displays, Scripts/AuthorPowerUpLive.py): tunes a Niagara copy under
    // /Game/HoverPrototype/Effects/PowerUps/Live/ (an engine template duplicate; refuses anything else). Disables every
    // emitter except KeepEmitter (empty = keep all), gives its sprite renderers SpriteMaterial (when set) and velocity
    // alignment (optional), and writes module inputs in the rapid-iteration stores of the particle and system scripts:
    // each Values key is a name suffix ("InitializeParticle.Lifetime Min", "SpawnBurst_Instantaneous.Spawn Count"),
    // each value "x" / "x,y" / "x,y,z" / "r,g,b,a" / "true". Returns a report: SET lines, MISSING keys, and the
    // kept emitter's system-script inputs (SYS lines) so new keys can be found.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString ConfigurePowerUpLiveEffect(UNiagaraSystem *Effect, const FString &KeepEmitter,
                                              class UMaterialInterface *SpriteMaterial, bool bVelocityAligned,
                                              const TMap<FString, FString> &Values);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void PrepareReviewEffects(const TArray<UNiagaraSystem *> &Effects);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectReviewEffects();
    // AFS 2026-10-31: the active Niagara components of the play world whose asset name contains AssetContains, with
    // their particle counts and (CPU sims) every particle attribute of the first particle (size, colour, age...).
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectActiveEffects(const FString &AssetContains);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void CapturePlaytest(const FString &Filename);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void CaptureWorldFrame(const FString &Filename);
    // Raw (parent-space, editor source data) transform of Sequence's track for Bone at each time in seconds, for
    // clip verification scripts; empty when the sequence, skeleton or bone is missing. Translation is in the
    // parent bone's space, so under a root bone that carries the FBX x100 scale it reads in metres. A bone the
    // sequence has no track for (Interchange drops flat 2-key tracks) samples as the skeleton's reference pose,
    // which is what the runtime plays for it; ClipHasBoneTrack tells the two apart.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FTransform> SampleClipBone(class UAnimSequence *Sequence, FName Bone, const TArray<float> &Times);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ClipHasBoneTrack(class UAnimSequence *Sequence, FName Bone);
    // Does Sequence play on Mesh? JSON: both skeleton paths, USkeleton::IsCompatibleForEditor each way, the
    // sequence's track bones the mesh skeleton lacks, and a pose sampled at Time through the same path the
    // runtime players use (UAnimSequence::GetAnimationPose with the mesh's bone container, so a different
    // skeleton goes through the engine's name remapping): how many bones left the reference pose and the
    // component-space locations of the named bones. For the stance poses: MF_Rifle_Idle_ADS is the known-good
    // reference (Flight SK_Mannequin on Vexa), the pistol duplicate must read the same way.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeSequenceOnMesh(class UAnimSequence *Sequence, USkeletalMesh *Mesh, float Time,
                                          const TArray<FName> &Bones);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectCharacterMesh(USkeletalMesh *Mesh);
    // Render-data vertices of one LOD in the mesh's bind (component) space, cm, and each vertex's heaviest-weighted
    // bone name, index-aligned; empty when the mesh has no render data. Scripts/MeasureGripSeat.py reads the grip
    // geometry under grip_r with these (a rig's root bone carries the FBX x100, so the positions are already cm).
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FVector> SkeletalMeshVertexPositions(USkeletalMesh *Mesh, int32 LOD = 0);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static TArray<FName> SkeletalMeshVertexBones(USkeletalMesh *Mesh, int32 LOD = 0);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConfigureCreatureLODs(USkeletalMesh *Mesh);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static FString InspectTexture(class UTexture2D *Texture);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static int32 RemapAppearanceAsset(UObject *Asset, const TArray<UObject *> &Sources,
                                      const TArray<UObject *> &Copies);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool ConvertAppearanceTextures(const TArray<class UTexture2D *> &Textures,
                                          const TArray<class UMaterial *> &Materials);
    // Design A1: turns a plain duplicate of a fire clip into a local-space additive whose base is its own frame
    // RefFrame (AAT_LocalSpaceBase / ABPT_AnimFrame), so the additive is exactly the authored recoil motion. Marks
    // the package dirty (the caller saves) and returns JSON with the read-back settings and IsValidAdditive().
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static FString MakeFrameAdditive(class UAnimSequence *Sequence, int32 RefFrame = 0);
    UFUNCTION(BlueprintCallable, Category = "Hover|Authoring")
    static bool IsValidAdditive(class UAnimSequence *Sequence);
    // Design C2: mean luminance (0-255, Rec.709 weights on the stored 8-bit values) and the fraction of pixels with
    // every channel above 245, over the central CentralFraction of a saved frame (CaptureWorldFrame PNG). JSON:
    // {"ok", "width", "height", "mean_luma", "saturated_fraction", "pixels"}. CPU only (image decode, no GPU).
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString MeasureFrameLuminance(const FString &Filename, float CentralFraction = .6f);
    // Design B2 synthetic test: drive the pilot's left-hand rotation delta (gun space, X fwd / Y right / Z up) and
    // finger curl in place of the rig bone's; bEnabled false restores the live read. Editor PIE only.
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SetSupportHandOverride(class AHoverPilot *Pilot, bool bEnabled, FRotator GunSpaceDelta,
                                       float Curl = 1.f);

    // NYC zombie diversity (Scripts/AuthorZombieDiversity.py). Editor-only bodies; each returns whether the asset
    // now reads as requested. Only owned /Game/HoverPrototype/ assets are changed, never pack originals.
    //
    // Adds Source to Target.CompatibleSkeletons so a pack clip plays on the roster body by bone name, and sets the
    // same translation retargeting as ConfigureVariantSkeleton (Skeleton for every bone, Animation on the root,
    // AnimationScaled on pelvis). Leaves the package clean when both already hold. True when Source is listed after.
    UFUNCTION(BlueprintCallable, Category = "AFS|Authoring")
    static bool MakeSkeletonCompatible(class USkeleton *Target, class USkeleton *Source);
    // Rebuilds a BlendSpace1D on one axis "Speed" 0..MaxSpeed: Clips[i] at Speeds[i] cm/s, rate scale 1 (the caller
    // may change RateScale on the sample copies afterwards). The blend space takes the first clip's skeleton; every
    // other clip must use it or a compatible one. False on any rejected sample.
    UFUNCTION(BlueprintCallable, Category = "AFS|Authoring")
    static bool BuildSpeedBlend1D(class UBlendSpace *Blend, const TArray<class UAnimSequence *> &Clips,
                                  const TArray<float> &Speeds, float MaxSpeed);
    // Renames the first slot track of an owned montage (UpperBody for attacks, DefaultSlot for full-body reactions,
    // roars and deaths; ABP_ZombieMaster has only those two). The montage skeleton's slot groups are not touched.
    UFUNCTION(BlueprintCallable, Category = "AFS|Authoring")
    static bool SetMontageSlot(class UAnimMontage *Montage, FName Slot);
};
