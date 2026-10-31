#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "HoverMeleeProfile.generated.h"

class UAnimSequence;

// AFS 2026-10-31 (spear item): one melee strike. The katana's single slash and the spear's jab / thrust / swing / heavy
// thrust are all rows of this struct, played by AHoverMeleeWeapon through the same sweep, hit-confirm, sound and
// hit-stop plumbing. Times are game seconds from the strike start when the clip plays over Duration.
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverMeleeStrike
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") FName Name;
    // Played on the CLS driver through UHoverLocomotionBridge::PlayAction (a dynamic montage on AdditiveHitReact, the
    // upper-body slot of ABP_CLS_Actions; DefaultSlot when bUpperBody is false), rate-scaled to Duration.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") TSoftObjectPtr<UAnimSequence> Clip;
    // First-person arms clip (katana only; NYC Survival forces the third-person view).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") TSoftObjectPtr<UAnimSequence> ViewClip;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float Duration = .8f;
    // One sphere sweep per entry; every zombie is struck once per strike.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") TArray<float> SweepTimes;
    // Sweep length from the chest along the camera yaw; 0 reads the definition's MeleeRange (the katana).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float Reach = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ReachPad = 30.f;
    // Sphere radius; 0 reads max(50, MeleeRadius x 2.5) from the definition (the katana).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float Radius = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float StartHeight = 15.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float StartForward = 0.f;
    // Yaw offsets (degrees, + = right) of the first and last sweep; the sweeps between are spread evenly. 0 / 0 is a
    // straight line along the spear (jab, thrust); a swing walks the line across a narrow arc.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ArcStartYaw = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ArcEndYaw = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float DamageScale = 1.f;
    // Victim-only hit-stop (HoverEffects::HitStop); 0 seconds = none (the katana, unchanged).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float HitStopSeconds = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float HitStopDilation = .05f;
    // Combo: a light press after ChainOpenSeconds is buffered and the next strike starts at ChainAtSeconds
    // (0 = at Duration). Both ignored by the katana.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ChainOpenSeconds = 0.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ChainAtSeconds = 0.f;
    // Heavy only: the clip fraction reached at full charge and held until the release.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float WindupFraction = .35f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bUpperBody = true;
};

USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverMeleeProfile
{
    GENERATED_BODY()
    // HOVER_<LogTag>_SWEEP / _HIT / _STRIKE log lines (KATANA keeps the 2026-10-31 HOVER_KATANA_SWEEP prefix).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") FString LogTag = TEXT("KATANA");
    // HUD label while held; a data field so the owner can rename it.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") FString HudName = TEXT("KATANA");
    // Light chain, in order; it wraps after the last strike or after ComboResetSeconds without a press.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") TArray<FHoverMeleeStrike> Light;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ComboResetSeconds = .6f;
    // Hold-to-charge heavy strike (spear thrust). The trigger held past ChargeThreshold winds it, the release throws
    // it with DamageScale = Lerp(HeavyMinScale, HeavyMaxScale, held / FullChargeSeconds).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bHasHeavy = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") FHoverMeleeStrike Heavy;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float ChargeThreshold = .22f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float FullChargeSeconds = .9f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float MaxChargeHoldSeconds = 3.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float HeavyMinScale = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float HeavyMaxScale = 3.f;
    // Upper-body loop while held and idle between strikes (the pack's 2H stance idle); none for the katana.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") TSoftObjectPtr<UAnimSequence> StanceLoop;
    // Spear grip: the mesh's long bounds axis passes through the rear hand at GripFromButt (fraction of the length
    // from the butt) and is aimed at the front hand every frame while a pack clip holds both hands on the shaft.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bTwoHandGrip = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bTipTowardLeftHand = true;
    // The head is at the bounds minimum of the long axis instead of the maximum.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bFlipMeshTip = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float GripFromButt = .3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float TwoHandMinSpacing = 12.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") float TwoHandMaxSpacing = 110.f;
    // Cancel a strike or charge when the weapon stops being held (board, knockdown, inventory). Off for the katana.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bCancelWhenInactive = false;
    // AFS 2026-10-31 (spear proof): each sweep passes through every zombie on its line (a zombie capsule blocks the
    // Pawn channel, so a plain multi-sweep stopped at the first one); level geometry still stops it. Off for the
    // katana, which keeps its first-blocker sweep exactly.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") bool bPierce = false;

    // The katana as shipped 2026-10-31: QA_Katana over 0.8 s, sweeps at 0.22 / 0.30 / 0.38 / 0.48 s, reach and radius
    // from DA_AFS_Melee, no hit-stop.
    static FHoverMeleeProfile Katana();
    // Built-in spear values, used when /Game/HoverPrototype/Spear/DA_SpearProfile is missing.
    static FHoverMeleeProfile SpearDefaults();
    // DA_SpearProfile (Scripts/AuthorSpear.py, measured from the pack clips) or SpearDefaults().
    static FHoverMeleeProfile LoadSpear();
};

// Data asset so the owner (and Scripts/AuthorSpear.py) can tune a melee weapon without a build.
UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverMeleeProfileAsset : public UDataAsset
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Melee") FHoverMeleeProfile Profile;
    // Python entry point: fill Profile with FHoverMeleeProfile::SpearDefaults() before the measured values go in.
    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Melee") void ResetToSpearDefaults();
};
