#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "UObject/ObjectSaveContext.h"
#include "HoverBloodTube.generated.h"

class UMaterialInterface;
class UNiagaraComponent;
class UNiagaraSystem;
class UPointLightComponent;
class UStaticMesh;
class UStaticMeshComponent;

// AFS 2026-11-01: the blood inside the Headhunter perk machine's glass tube (Scripts/ImportHeadhunter.py places it,
// attached to the machine body, at the machine pivot, so its local frame is the machine meshes' frame in cm, front +Y).
// Purely visual. It animates in the editor viewport without Play (it ticks in editor viewports) and in game.
//   PoolMesh        SM_Headhunter_BloodPool on M_HH_BloodPool: the pool on the owner's red disc; the material ripples it.
//   GlassBloodMesh  SM_Headhunter_GlassBlood on M_HH_GlassBlood: smears, crawling runs and the headshot spatter.
//   Drops           a few SM_Headhunter_BloodDrop meshes this actor moves: a bead swells at a source (skull jaw, the
//                   rod's painted drip, the cap lip), lets go and falls under gravity into the pool; where it lands a
//                   ripple ring starts in the pool material and a small splash crown (Niagara) fires.
//   Headshot        every HeadshotInterval s: a fast spurt (Niagara) from the back of the skull to the back wall of the
//                   glass, a fresh splat there (glass material, it then runs down and fades), droplets falling off the
//                   glass (Niagara), the pool jolts (slosh + ring), the glow light kicks, and the skull bleeds faster.
// The materials read this actor's state through custom primitive data (transient, never saved):
//   pool  [0] HitAge s  [1] HitAngle rad  [2..4] ripple A age, x, y  [5..7] ripple B age, x, y   (x, y: cm from axis)
//   glass [0] HitAge s  [1] HitAngle rad  [2] HitZ cm  [3] HitSeed 0..1
UCLASS()
class HOVERFLIGHT_API AHoverBloodTube : public AActor
{
    GENERATED_BODY()

public:
    AHoverBloodTube();

    // ---------------------------------------------------------------- assets (applied to the components on construction)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UStaticMesh> PoolMeshAsset;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UMaterialInterface> PoolMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UStaticMesh> GlassBloodMeshAsset;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UMaterialInterface> GlassBloodMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UStaticMesh> DropMeshAsset;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UMaterialInterface> DropMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UNiagaraSystem> SplashSystem;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UNiagaraSystem> SpurtSystem;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Assets") TObjectPtr<UNiagaraSystem> GlassSplashSystem;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") FLinearColor GlowColor = FLinearColor(1.f, .05f, .025f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float GlowRadius = 45.f;
    // A soft neutral fill under the cap at the front of the tube: lights the skull's face and the back of the tube a
    // pale grey like the concept, so dark blood reads against it (the red glow alone turned the whole tube red).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") FVector FillOffset = FVector(0.f, 22.f, 146.f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float FillIntensity = 1.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float FillRadius = 70.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") FLinearColor FillColor = FLinearColor(1.f, .93f, .85f);

    // ---------------------------------------------------------------- tube geometry (local cm, the machine's frame)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tube") FVector2D TubeCentre = FVector2D(0.23f, -0.88f);
    // Radius where the glass blood sits (the hit spatter and the glass-splash droplets start here).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tube") float GlassRadius = 33.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tube") float PoolSurfaceZ = 117.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tube") float PoolRadius = 32.9f;

    // ---------------------------------------------------------------- drips
    // Where beads form (local cm). Index 0 = skull jaw (also the one the headshot speeds up).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") TArray<FVector> DropSources;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") TArray<float> DropSourceWeights;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float DropIntervalMin = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float DropIntervalMax = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float DropGrowSeconds = .9f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float DropScale = 1.3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float Gravity = 980.f;
    // After a headshot the skull bleeds: this many quick jaw drops, BleedGap s apart.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") int32 BleedDrops = 3;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Drips") float BleedGap = .55f;

    // ---------------------------------------------------------------- headshot
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotIntervalMin = 12.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotIntervalMax = 20.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float FirstHeadshotDelay = 5.f;
    // Where the spurt comes from (behind the skull, local cm) and where the splat lands: the back wall (local -Y)
    // within +-HeadshotArcDeg, between HeadshotZMin and HeadshotZMax.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") FVector SkullExit = FVector(0.f, 12.f, 133.f);
    // Off the back centre by HeadshotArcMinDeg..HeadshotArcDeg either side, so the splat is not hidden behind the skull.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotArcMinDeg = 22.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotArcDeg = 58.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotZMin = 124.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Headshot") float HeadshotZMax = 142.f;

    // ---------------------------------------------------------------- light
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float GlowIntensity = .3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float GlowFlicker = .12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float HitLightBoost = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float HitLightSeconds = .35f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Tube") bool bAnimateInEditor = true;

    // Fire a headshot / a drop now (stills harness, or to look at one in the editor). Source -1 = random by weight.
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Tube") void TriggerHeadshot();
    UFUNCTION(BlueprintCallable, Category = "Tube") void TriggerDrop(int32 Source = -1);
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Tube") void TriggerDropNow() { TriggerDrop(-1); }
    // JSON: clock, next events, drops in flight (state, local position), last hit.
    UFUNCTION(BlueprintCallable, Category = "Tube") FString DescribeState() const;

    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override { return bAnimateInEditor; }
    virtual void BeginPlay() override;
    virtual void OnConstruction(const FTransform &Transform) override;
    virtual void PreSave(FObjectPreSaveContext SaveContext) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<USceneComponent> Root;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UStaticMeshComponent> PoolMesh;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UStaticMeshComponent> GlassBloodMesh;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TArray<TObjectPtr<UStaticMeshComponent>> Drops;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UPointLightComponent> GlowLight;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UPointLightComponent> FillLight;
    // Niagara: splash crowns where drops land (pool of 3), the headshot spurt, droplets falling off the glass.
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TArray<TObjectPtr<UNiagaraComponent>> SplashFx;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UNiagaraComponent> SpurtFx;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components") TObjectPtr<UNiagaraComponent> GlassSplashFx;

private:
    static constexpr int32 NumDrops = 3;
    enum class EDrop : uint8 { Idle, Grow, Fall };
    struct FDrop
    {
        EDrop State = EDrop::Idle;
        FVector Start = FVector::ZeroVector;
        float T = 0.f;
        float Grow = .9f;
    };
    FDrop DropState[NumDrops];
    float Clock = 0.f;
    float NextDrop = 1.f;
    float NextHeadshot = 5.f;
    float HitTime = -100.f;
    float HitAngle = -UE_HALF_PI;
    float HitZ = 133.f;
    float HitSeed = 0.f;
    float RippleTime[2] = {-100.f, -100.f};
    FVector2D RippleXY[2];
    int32 NextRipple = 0;
    int32 NextSplash = 0;
    int32 BleedLeft = 0;
    float NextBleed = 0.f;
    FRandomStream Rng;
    bool bStarted = false;

    void Restart();
    void ApplyAssets();
    int32 PickSource();
    void Land(FDrop &D, const FVector &Local);
    void PushState();
    void ParkDrops();
};
