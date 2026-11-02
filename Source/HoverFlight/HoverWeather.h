#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "HoverWeather.generated.h"

class UAudioComponent;
class UDecalComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UMaterialParameterCollection;
class UParticleSystem;
class UParticleSystemComponent;
class UPhysicalMaterial;
class UPrimitiveComponent;
class USoundBase;

// AFS 2026-11-01 (owner: "put the weather in too ... I want to see how it works"; earlier "Menu toggle, rain/snow").
// The Dreamrise Multiplayer Dynamic Weather System (/Game/MultiplayerDynamicWeatherSystem, copied from
// M:/MultiplayerDynamicWeather) is an all-in-one sky manager: its BP_MultiplayerDynamicWeatherManager owns the sun
// rotation (day/night cycle), sun / sky light / fog intensities, a sky sphere and volumetric clouds, and tells pawns
// implementing BI_MultiplayerDynamicWeatherSystem to switch their own Cascade rain / snow emitters. Placed in NYC it
// would replace the map's sun, sky and fog with its own values, so AFS uses the pack's PARTS instead: P_Rain /
// P_Snow / P_Rain_Ground / BP_Thunder / rain + wind cues / MPC_DynamicWeatherSystem, driven by this actor, and the
// level's OWN sun, sky light, fog and atmosphere scaled by the pack's DT_Weather ratios (Rainy vs Sunny etc.).
// Clear restores the exact values captured at BeginPlay and touches nothing before the first change, so the map
// looks as it did. One instance per level; the F6 menu shows its row only when one exists (Find).
UENUM(BlueprintType)
enum class EHoverWeatherKind : uint8
{
    Clear,
    Cloudy,
    Rain,
    Storm,
    Snow,
    Count UMETA(Hidden)
};

// One weather state as multipliers on the level's own Clear values (1 = unchanged) plus the precipitation it runs.
USTRUCT(BlueprintType)
struct FHoverWeatherLook
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Sun = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float SkyLight = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float FogDensity = 1;
    // 0 keeps the level's fog colour, 1 uses FogColor.
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float FogColorBlend = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FLinearColor FogColor = FLinearColor(.5f, .53f, .58f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Rayleigh = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Mie = 1;
    // Multiplier on the atmosphere's Mie anisotropy: below 1 spreads the sun's forward-scatter halo into an even
    // overcast instead of a bright glare around the sun (first proof: the storm sky glowed at the sun).
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float MieHalo = 1;
    // Sun shafts (the pack's per-weather "Sun Shaft Bloom Scale" / "Light Shaft Occlusion Darkness"): multiplier on
    // the sun's shaft bloom and volumetric-fog scattering, and the shaft occlusion fades toward none as it drops.
    // Rounds 2-3: NYC's sun has light-shaft occlusion on; in the rain haze it drew hard rays at the sun.
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float SunShafts = 1;
    // Surface decal: 1 = full wet streets / full snow cover on up-facing surfaces.
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Wetness = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float SnowCover = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Wind = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float RainVolume = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float WindVolume = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bRain = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bSnow = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bThunder = false;
};

UCLASS()
class HOVERFLIGHT_API AHoverWeather : public AActor
{
    GENERATED_BODY()
  public:
    AHoverWeather();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Tick(float DeltaSeconds) override;

    // BlendSeconds < 0 uses TransitionSeconds; 0 switches at once.
    UFUNCTION(BlueprintCallable, Category = "AFS|Weather") void SetWeather(EHoverWeatherKind NewWeather, float BlendSeconds = -1);
    UFUNCTION(BlueprintPure, Category = "AFS|Weather") EHoverWeatherKind GetWeather() const
    {
        return TargetWeather;
    }
    UFUNCTION(BlueprintPure, Category = "AFS|Weather") float GetBlendAlpha() const
    {
        return BlendDuration > 0 ? FMath::Clamp(BlendTime / BlendDuration, 0.f, 1.f) : 1.f;
    }
    // One line for logs and proofs: weather, blend, applied multipliers, live particle counts.
    UFUNCTION(BlueprintCallable, Category = "AFS|Weather") FString DescribeState() const;
    UFUNCTION(BlueprintCallable, Category = "AFS|Weather") int32 GetLiveParticleCount() const;
    UFUNCTION(BlueprintPure, Category = "AFS|Weather", meta = (WorldContext = "WorldContext"))
    static AHoverWeather *FindWeather(const UObject *WorldContext);
    static const TCHAR *WeatherName(EHoverWeatherKind Weather);
    static bool ParseWeather(const FString &Text, EHoverWeatherKind &OutWeather);

    UPROPERTY(EditAnywhere, Category = "Weather") EHoverWeatherKind StartWeather = EHoverWeatherKind::Clear;
    UPROPERTY(EditAnywhere, Category = "Weather") float TransitionSeconds = 6;
    UPROPERTY(EditAnywhere, Category = "Weather") TMap<EHoverWeatherKind, FHoverWeatherLook> Looks;
    // The level's own lighting. Empty = found at BeginPlay (atmosphere sun or brightest directional light, first sky
    // light / height fog / sky atmosphere). Every other directional light follows the sun multiplier too.
    UPROPERTY(EditAnywhere, Category = "Weather|Level") TObjectPtr<AActor> SunLight;
    UPROPERTY(EditAnywhere, Category = "Weather|Level") TObjectPtr<AActor> SkyLight;
    UPROPERTY(EditAnywhere, Category = "Weather|Level") TObjectPtr<AActor> HeightFog;
    UPROPERTY(EditAnywhere, Category = "Weather|Level") TObjectPtr<AActor> Atmosphere;
    // Precipitation follows the view: centred this far ahead of the camera (flat), near and far rain volumes.
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float RainNearAhead = 700;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float RainFarAhead = 2600;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float SnowAhead = 500;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float SnowFarAhead = 2600;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") int32 MaxParticlesPerEmitter = 6000;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float MaxSplashesPerSecond = 90;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") float SplashRange = 3000;
    UPROPERTY(EditAnywhere, Category = "Weather|Precipitation") FVector2D ThunderInterval = FVector2D(6, 14);
    // Half extents of the surface decal box (X = vertical projection depth).
    UPROPERTY(EditAnywhere, Category = "Weather|Surface") FVector SurfaceDecalSize = FVector(1500, 4500, 4500);

    // AFS-tuned copies of the pack's P_Rain (Scripts/ImportWeather.py: denser, wider streaks; the far one without
    // collision). Empty or missing = the pack's own P_Rain.
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UParticleSystem> RainTemplate;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UParticleSystem> RainFarTemplate;
    // AFS-tuned copies of the pack's P_Snow (smaller flakes; near traced, far untraced); missing = the pack's own.
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UParticleSystem> SnowTemplate;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UParticleSystem> SnowFarTemplate;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UParticleSystem> SplashTemplate;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftClassPtr<AActor> ThunderClass;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<USoundBase> RainSound;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<USoundBase> WindSound;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UMaterialParameterCollection> WeatherParameters;
    UPROPERTY(EditAnywhere, Category = "Weather|Assets") TSoftObjectPtr<UMaterialInterface> SurfaceMaterial;

  private:
    UPROPERTY(VisibleAnywhere) TObjectPtr<USceneComponent> Root;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UParticleSystemComponent> RainNear;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UParticleSystemComponent> RainFar;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UParticleSystemComponent> Snow;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UParticleSystemComponent> SnowFar;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UDecalComponent> Surface;
    UPROPERTY() TObjectPtr<UAudioComponent> RainAudio;
    UPROPERTY() TObjectPtr<UAudioComponent> WindAudio;
    UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> SurfaceMID;
    UPROPERTY() TObjectPtr<UParticleSystem> Splash;
    UPROPERTY() TObjectPtr<UMaterialParameterCollection> MPC;
    UPROPERTY() TArray<TObjectPtr<class UDirectionalLightComponent>> Suns;
    UPROPERTY() TObjectPtr<class USkyLightComponent> Sky;
    UPROPERTY() TObjectPtr<class UExponentialHeightFogComponent> Fog;
    UPROPERTY() TObjectPtr<class USkyAtmosphereComponent> Air;
    TArray<float> BaseSun, BaseShaftBloom, BaseSunScattering, BaseShaftOcclusion;
    float BaseSky = 1, BaseFog = 0, BaseRayleigh = 1, BaseMie = 1, BaseMieAnisotropy = .8f;
    int32 SplashCount = 0;
    FLinearColor BaseFogColor = FLinearColor::White;
    bool bCaptured = false;

    EHoverWeatherKind TargetWeather = EHoverWeatherKind::Clear;
    FHoverWeatherLook From, To, Current;
    float BlendTime = 0, BlendDuration = 0;
    bool bApplying = false;
    float SplashBudget = 0, NextThunder = 0, Flash = 0, DecalSweep = 0, RecaptureTimer = -1;
    TArray<TWeakObjectPtr<UPrimitiveComponent>> DecalExcluded;

    void CaptureLevelLighting();
    void Advance(float DeltaSeconds);
    void ApplyLook(const FHoverWeatherLook &Look, float FlashBoost);
    void UpdatePrecipitation(const FHoverWeatherLook &Look);
    void FollowView();
    void UpdateCharacterDecals(bool bSurfaceActive);
    void SpawnThunder();
    UFUNCTION() void HandleRainCollide(FName EventName, float EmitterTime, int32 ParticleTime, FVector Location,
                                       FVector Velocity, FVector Direction, FVector Normal, FName BoneName,
                                       UPhysicalMaterial *PhysMat);
    static FHoverWeatherLook BlendLooks(const FHoverWeatherLook &A, const FHoverWeatherLook &B, float Alpha);
};
