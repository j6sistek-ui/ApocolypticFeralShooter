#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Actor.h"
#include "UObject/ObjectSaveContext.h"
#include "HoverPowerUpDisplay.generated.h"

class UMaterialInstanceDynamic;
class UMaterialInterface;
class UNiagaraComponent;
class UNiagaraSystem;
class UPointLightComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UTextRenderComponent;

// AFS 2026-10-31: the live power-up look (owner decisions in Docs/POWERUP_CATALOG.md "DECIDED", parameters in
// Docs/POWERUP_BUILD.md). AHoverPowerUpDisplay is purely visual: no pickup, no overlap, no gameplay effect. It animates
// in the editor viewport without Play (it ticks in editor viewports) and in game, so a look is judged live and the
// approved asset is the shipping one. The real pickup class attaches it later (bLoopForEvaluation = false).
// Every tunable is a field of UHoverPowerUpLook (one data asset per item, written by Scripts/AuthorPowerUpLive.py).

// What happens in the last WarningSeconds of the life.
UENUM(BlueprintType)
enum class EHoverPowerUpWarning : uint8
{
    None,
    Heartbeat,        // lub-dub swell, glow flash, echo shell
    HeartbeatAndArcs, // the heartbeat plus the arc crawl, both easing in and speeding up together (the Nuke)
};

// How the display drives one additive shell (a copy of the item mesh on M_PU_Shell, inflated by the material).
UENUM(BlueprintType)
enum class EHoverPowerUpShellRole : uint8
{
    Aura,          // always on (toxic aura layers, the blood mist); follows the life fade and the heartbeat flash
    ArcCrawl,      // off until the warning; ArcIntensity / ArcRate written by the arc crawl
    HeartbeatEcho, // off until the warning; grows (to EchoMaxScale) and fades on every heartbeat (not on the Nuke)
};

USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverPowerUpShell
{
    GENERATED_BODY()
    // A material instance of M_PU_Shell (its Inflate, Intensity, noise and pulse are set in the instance).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shell") TObjectPtr<UMaterialInterface> Material;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shell") EHoverPowerUpShellRole Role = EHoverPowerUpShellRole::Aura;
};

UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverPowerUpLook : public UPrimaryDataAsset
{
    GENERATED_BODY()
public:
    // ---------------------------------------------------------------- item
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") TObjectPtr<UStaticMesh> ItemMesh;
    // A material instance of M_PU_ItemFX2 (the item's own maps plus seam / emblem / rim / arcs). The display writes
    // GlowBoost, EmblemGlow / EmblemColor, SeamGlow / SeamColor, ArcIntensity / ArcRate / ArcPatch at run time.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") TObjectPtr<UMaterialInterface> ItemMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") FLinearColor ItemColor = FLinearColor(1.f, .42f, .08f);
    // Item base above the actor's ground point (cm): dropped pickups float 25-40 cm up.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") float HoverCm = 30.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") float SpinDegPerSec = 40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") float BobCm = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") float BobHz = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Item") float ItemScale = 1.f;

    // ---------------------------------------------------------------- life
    // A dropped power-up lives 30 s (vendor AZE_PowerUpPickup InitialLifeSpan).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Life") float LifeSeconds = 30.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Life") float SpawnInSeconds = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Life") float FadeOutSeconds = .5f;
    // Evaluation loop only: hidden this long after the fade, then the life starts again.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Life") float RespawnDelaySeconds = 2.f;

    // ---------------------------------------------------------------- key light (in front of / around the item)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") FLinearColor KeyLightColor = FLinearColor(1.f, .7f, .45f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float KeyLightIntensity = 3.f; // candela
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float KeyLightRadius = 220.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") FVector KeyLightOffset = FVector(0, 0, 34);
    // Slow breathing of the key light (Hz, fraction).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float KeyLightPulseHz = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Light") float KeyLightPulseAmount = 0.f;

    // ---------------------------------------------------------------- aura shells (toxic aura, blood mist, arc / echo)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Shells") TArray<FHoverPowerUpShell> Shells;

    // ---------------------------------------------------------------- drifting motes (Niagara)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motes") TObjectPtr<UNiagaraSystem> MoteSystem;
    // One mote burst is re-fired this often (each burst lives longer, so the motes overlap into a steady drift).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motes") float MoteBurstInterval = 1.1f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Motes") FVector MoteOffset = FVector(0, 0, 18);

    // ---------------------------------------------------------------- Geiger stutter ticks (Nuke N4)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") bool bGeigerTicks = false;
    // Mean gap between tick groups (s), clamped to [Min, Max].
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickMeanInterval = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickMinInterval = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickMaxInterval = 3.5f;
    // Chance a tick group is a triple (three ticks TickTripleGap apart) instead of a single.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickTripleChance = .3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickTripleGap = .09f;
    // Flash decay time constant (s).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickFlashSeconds = .07f;
    // Added to the emblem (trefoil) and seam glow at the flash peak; colours pushed toward TickWhiteHot.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickEmblemGlow = 9.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickSeamGlow = 7.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") FLinearColor TickWhiteHot = FLinearColor(1.f, .92f, .78f);
    // Casing shudder amplitude (cm) at the flash peak.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickShudderCm = 2.4f;
    // The shudder picks a new random offset this many times a second and glides between them (frame-rate independent).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickShudderHz = 30.f;
    // Cap on the effective trefoil / seam glow ((base + tick flash) x heartbeat glow flash): a tick landing on a beat
    // must not stack to white and wash the trefoil out. 0 = no cap.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float FlashEmblemGlowMax = 8.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float FlashSeamGlowMax = 7.f;
    // Star glint at a seam point: size (cm), intensity, key light kick.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float GlintSizeCm = 9.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float GlintIntensity = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Geiger") float TickLightKick = 2.5f;

    // ---------------------------------------------------------------- the event schedule (Nuke N1 sparks / N2 pops)
    // Seconds between scheduled events, alternating spark burst / pop when both are on.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Events") float EventIntervalMin = 2.4f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Events") float EventIntervalMax = 3.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Events") float FirstEventSeconds = 1.6f;
    // Casing points the sparks and pops come from (cm, item mesh space). Empty: seam rings and the cap from bounds.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Events") TArray<FVector> CasingPoints;
    // Seam heights as fractions of the item height, used when CasingPoints is empty (the cap is always added).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Events") TArray<float> SeamHeightFractions;

    // N1 spark bursts: SparkBurstA (6 sparks) and SparkBurstB (7) fired alone or together (6, 7 or 13 sparks).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") bool bSparkBursts = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") TObjectPtr<UNiagaraSystem> SparkBurstA;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") TObjectPtr<UNiagaraSystem> SparkBurstB;
    // Chance both fire (13 sparks); otherwise A or B evenly.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") float SparkBothChance = .35f;
    // Single-spark dribble between events (mean gap, s; 0 = off).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") TObjectPtr<UNiagaraSystem> SparkSingle;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") float DribbleMeanInterval = 1.3f;
    // Key light kick on a burst.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sparks") float SparkLightKick = 3.f;

    // N2 micro-detonation pops on the casing.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") bool bPops = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") TObjectPtr<UMaterialInterface> PopCoreMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") TObjectPtr<UMaterialInterface> PopGlowMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") TObjectPtr<UMaterialInterface> PopRayMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopCoreCm = 7.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopGlowCm = 30.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopRayLengthCm = 26.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopRayWidthCm = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") int32 PopRaysMin = 4;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") int32 PopRaysMax = 6;
    // Envelope time constants (s): core flash, blast glow, rays.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopCoreSeconds = .06f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopGlowSeconds = .18f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopRaySeconds = .09f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopLightIntensity = 40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopLightRadius = 260.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") FLinearColor PopLightColor = FLinearColor(1.f, .75f, .45f);
    // 3 sparks (once, or twice for 6) and, when PopSmoke is set, a small dark smoke puff (unset since 2026-10-31:
    // it could not be made to read against the black Nuke casing; Scripts/AuthorPowerUpLive.py POP_PUFF).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") TObjectPtr<UNiagaraSystem> PopSparks;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") TObjectPtr<UNiagaraSystem> PopSmoke;
    // The puff starts this far out from the casing (cm) so the sprites are not half inside the item.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopSmokeOffsetCm = 6.f;
    // Tiny casing jolt (cm, away from the pop) and its decay (s).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopJoltCm = 1.2f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pops") float PopJoltSeconds = .12f;

    // ---------------------------------------------------------------- floating neon icon (look 13)
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") TObjectPtr<UStaticMesh> NeonMesh;
    // Slots of the neon mesh: Lit, Dead (the dying tube), Frame (dark bracket).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") TObjectPtr<UMaterialInterface> NeonLitMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") TObjectPtr<UMaterialInterface> NeonDeadMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") TObjectPtr<UMaterialInterface> NeonFrameMaterial;
    // Above the item base (cm).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonHeightCm = 92.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonScale = 1.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonBobCm = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonBobHz = .5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonLitIntensity = 12.f;
    // The lit tube's buzz: random level changes per second and depth.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonBuzzRate = 14.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonBuzzAmount = .12f;
    // The dead tube: faint most of the time, stutter bursts every Min..Max s lasting BurstMin..BurstMax s.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonDeadOnIntensity = 8.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonDeadOffIntensity = .25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonStutterGapMin = .7f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonStutterGapMax = 2.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonStutterBurstMin = .15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonStutterBurstMax = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonStutterHz = 18.f;
    // Point light in a deeper version of the item colour, no shadows; follows the buzz and the dead tube.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") FLinearColor NeonLightColor = FLinearColor(1.f, .02f, .02f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonLightIntensity = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") float NeonLightRadius = 340.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Neon") FVector NeonLightOffset = FVector(0, 0, -12);

    // ---------------------------------------------------------------- end-of-life warning
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") EHoverPowerUpWarning Warning = EHoverPowerUpWarning::Heartbeat;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float WarningSeconds = 5.f;
    // The warning amplitude eases in from zero over this long (smoothstep).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float WarningEaseInSeconds = 1.5f;
    // Beat rate at the start and at the end of the warning; BeatAccelPower shapes the ramp (1 = linear).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatHzStart = 1.25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatHzEnd = 1.55f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatAccelPower = 1.f;
    // Lub-dub: swell (fraction of the item size), dub strength relative to the lub, glow flash (GlowBoost added).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatSwell = .12f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatDubStrength = .6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatGlowFlash = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float BeatLightKick = 4.f;
    // Echo shell (a HeartbeatEcho shell, if the look has one): grows from 1 to EchoMaxScale over EchoSeconds and
    // fades. Kept small: a big echo reads as a floating ghost of the item.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float EchoMaxScale = 1.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float EchoSeconds = .45f;
    // Arc crawl (HeartbeatAndArcs): skin and shell arc intensity at full amplitude, arc layout rate start / end
    // (jumps per second), coverage start / end, and light-stutter discharges per second start / end.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcSkinIntensity = 22.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcShellIntensity = 14.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcRateStart = 5.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcRateEnd = 22.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcPatchStart = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float ArcPatchEnd = .62f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float DischargeRateStart = 2.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float DischargeRateEnd = 14.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float DischargeLightKick = 9.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") FLinearColor DischargeLightColor = FLinearColor(1.f, .85f, .6f);
    // Chance a discharge also spits one spark (SparkSingle).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Warning") float DischargeSparkChance = .2f;
};

// One scheduled moment of a life (for evaluation tools: the capture script aims stills at these).
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverPowerUpEvent
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly, Category = "Event") float Time = 0.f;
    // 0 = Geiger tick, 1 = spark burst, 2 = pop, 3 = dribble spark
    UPROPERTY(BlueprintReadOnly, Category = "Event") int32 Kind = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Event") int32 Count = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Event") FVector Point = FVector::ZeroVector;
    bool bFired = false;
};

UCLASS(Blueprintable)
class HOVERFLIGHT_API AHoverPowerUpDisplay : public AActor
{
    GENERATED_BODY()
public:
    AHoverPowerUpDisplay();

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") TObjectPtr<UHoverPowerUpLook> Look;
    // Evaluation: after the fade and RespawnDelaySeconds the life starts again. The real pickup sets it false.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") bool bLoopForEvaluation = true;
    // Animate in the editor viewport without Play (needs a realtime viewport).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") bool bAnimateInEditor = true;
    // Seed of the spark / pop / tick schedule (each loop adds the loop index).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") int32 Seed = 17;
    // Small floating evaluation label ("NUKE"), turned to the viewer on yaw. Off on the real pickup.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") bool bShowLabel = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") FText Label;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") float LabelHeightCm = 150.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Power-up Display") float LabelSizeCm = 9.f;

    // Seconds into the current life (0 at spawn; LifeSeconds = despawn starts).
    UFUNCTION(BlueprintPure, Category = "Power-up Display") float GetLifeTime() const { return LifeTime; }
    UFUNCTION(BlueprintPure, Category = "Power-up Display") int32 GetLoopIndex() const { return LoopIndex; }
    // 0..1 warning amplitude right now (eased in), and the current beat rate.
    UFUNCTION(BlueprintPure, Category = "Power-up Display") float GetWarningAmount() const { return WarnAmount; }
    UFUNCTION(BlueprintPure, Category = "Power-up Display") float GetBeatHz() const { return BeatHz; }
    UFUNCTION(BlueprintCallable, Category = "Power-up Display") TArray<FHoverPowerUpEvent> GetSchedule() const { return Schedule; }
    // Start the life again from zero (re-reads the look).
    UFUNCTION(BlueprintCallable, Category = "Power-up Display") void RestartLife();

    virtual void Tick(float DeltaSeconds) override;
    virtual bool ShouldTickIfViewportsOnly() const override { return bAnimateInEditor; }
    virtual void OnConstruction(const FTransform &Transform) override;
    virtual void BeginPlay() override;
    virtual void PreSave(FObjectPreSaveContext SaveContext) override;

protected:
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<USceneComponent> Root;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<USceneComponent> ItemPivot;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UStaticMeshComponent> ItemMesh;
    UPROPERTY(VisibleAnywhere, Category = "Components") TArray<TObjectPtr<UStaticMeshComponent>> ShellMeshes;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UPointLightComponent> KeyLight;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<USceneComponent> NeonPivot;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UStaticMeshComponent> NeonSign;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UPointLightComponent> NeonLight;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<USceneComponent> PopPivot;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UStaticMeshComponent> PopCore;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UStaticMeshComponent> PopGlow;
    UPROPERTY(VisibleAnywhere, Category = "Components") TArray<TObjectPtr<UStaticMeshComponent>> PopRays;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UPointLightComponent> PopLight;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<USceneComponent> GlintPivot;
    UPROPERTY(VisibleAnywhere, Category = "Components") TArray<TObjectPtr<UStaticMeshComponent>> GlintRays;
    // Niagara pools, by role: spark A, spark B, single spark, pop sparks, pop smoke, motes.
    UPROPERTY(VisibleAnywhere, Category = "Components") TArray<TObjectPtr<UNiagaraComponent>> FxPool;
    UPROPERTY(VisibleAnywhere, Category = "Components") TObjectPtr<UTextRenderComponent> LabelText;

private:
    enum EFx : uint8 { FxSparkA, FxSparkB, FxSingle, FxPopSparks, FxSmoke, FxMotes, FxRoleCount };
    // Pool size per role. A pool slot is re-fired (killing its live particles) after FxNum(role) uses, so a pool must
    // outlast the longest particle life at the highest fire rate.
    // (sizes in HoverPowerUpDisplay.cpp, FxPoolSizes)
    static int32 FxNum(int32 Role);
    static int32 FxFirst(int32 Role);
    static constexpr int32 MaxShells = 6;
    static constexpr int32 MaxRays = 6;

    void InitLook();
    // Per-component visibility of a visible, live display (shells by role, neon, pop / glint planes off) and the
    // pivots' rest scale. Never depends on transient state, so a saved or PIE-duplicated hidden phase cannot stick.
    void ResetVisibility();
    void BuildSchedule();
    void ApplyMaterials(bool bDynamic);
    bool bMaterialsNeedReapply = false;
    void FireFx(EFx FxRole, const FVector &WorldLoc, const FVector &WorldDir);
    void FireEvent(FHoverPowerUpEvent &Event);
    FVector RandomCasingPoint(FRandomStream &Rng, bool bAllowCap) const;
    FVector CasingNormal(const FVector &LocalPoint) const;
    bool GetViewLocation(FVector &Out) const;
    void UpdateAnimation(float Dt);
    void FaceCamera(USceneComponent *Plane, const FVector &CamLoc, float RollDeg, const FVector &Scale);
    float Hash(float X) const;

    UPROPERTY(Transient) TObjectPtr<UHoverPowerUpLook> InitedLook;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> ItemDMI;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> ShellDMIs;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> NeonLitDMI;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> NeonDeadDMI;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PopCoreDMI;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PopGlowDMI;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> PopRayDMI;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> GlintDMI;

    TArray<FHoverPowerUpEvent> Schedule;
    int32 FxNext[FxRoleCount] = {};
    FBox ItemBounds = FBox(ForceInit);
    float BaseEmblemGlow = 0.f, BaseSeamGlow = 0.f, BaseArcPatch = .5f;
    FLinearColor BaseEmblemColor = FLinearColor::White, BaseSeamColor = FLinearColor::White;

    float LifeTime = 0.f;
    float Clock = 0.f; // free-running, for buzz / bob
    int32 LoopIndex = 0;
    bool bHiddenPhase = false;
    float TickFlash = 0.f;
    float GlintFlash = 0.f;
    float GlintRoll = 0.f;
    FVector ShudderOffset = FVector::ZeroVector;
    FVector ShudderFrom = FVector::ZeroVector, ShudderTo = FVector::ZeroVector;
    float ShudderPhase = 0.f;
    float PopAge = 100.f;
    int32 PopRayCount = 0;
    float PopRayRolls[MaxRays] = {};
    float PopRayLens[MaxRays] = {};
    FVector JoltDir = FVector::ZeroVector;
    float LightKick = 0.f;
    float WarnAmount = 0.f;
    float BeatHz = 0.f;
    float BeatPhase = 0.f;
    float EchoAge = 100.f;
    float DischargeFlash = 0.f;
    float NeonStutterUntil = 0.f;
    float NeonNextStutter = 1.f;
    float NextMoteBurst = 0.f;
    FRandomStream LiveRng;
};
