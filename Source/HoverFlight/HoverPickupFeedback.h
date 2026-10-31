#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "World/ZE_WallBuyActor.h"
#include "HoverGunFeel.h"
#include "HoverPickupFeedback.generated.h"

class AController;
class AHUD;
class APawn;
class AZE_WeaponBase;
class UForceFeedbackEffect;
class UMaterialInterface;
class UNiagaraSystem;
class USoundBase;
class UStaticMesh;

// AFS 2026-10-31 (owner playtest items 1 and 6): presentation for the Nuke power-up and the ammo pickups in NYC
// Survival. Every visible string is a data field so the owner can rename it (no Call of Duty wording).

// Nuke presentation, edited on BP_CyberPower_Nuke (AHoverCyberPowerUp::NukePresentation). Used only when the
// auth game mode is AHoverNYCSurvivalGameMode; Cyber City and Lakeside keep the vendor same-frame kill.
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverNukePresentation
{
    GENERATED_BODY()
    FHoverNukePresentation();

    // Banner: placeholder wording, the owner names the power-up.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Banner") FText BannerText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Banner") FText BannerSubtext;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Banner") FLinearColor BannerColor = FLinearColor(1.f, .82f, .32f);
    // Real (undilated) seconds the banner stays up, fade included.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Banner", meta = (ClampMin = "0.2")) float BannerSeconds = 2.2f;

    // One short white flash (single pulse, under a quarter second).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flash", meta = (ClampMin = "0", ClampMax = "1")) float FlashAlpha = .85f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Flash", meta = (ClampMin = "0", ClampMax = "0.25")) float FlashSeconds = .18f;

    // Big blast from SF_Explosives_SFX, played 2D so it is full volume wherever Vexa stands.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sound") TSoftObjectPtr<USoundBase> ExplosionSound;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sound") float ExplosionVolume = 1.2f;

    // Vefects ground ring plus its distortion ring, at the pickup.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") TSoftObjectPtr<UNiagaraSystem> Shockwave;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") TSoftObjectPtr<UNiagaraSystem> ShockwaveDistortion;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float ShockwaveScale = 1.f;

    // UHoverBlastShake scale and a code-built rumble (left large heavy, right small sharp).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feel") float ShakeScale = 1.6f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Feel") FHoverRumbleCurve Rumble;

    // Zombies alive at the pickup freeze, then die in distance order from the pickup across RippleSeconds
    // (real seconds; the nearest at once, the farthest at the end).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ripple", meta = (ClampMin = "0")) float RippleSeconds = .6f;
    // Anim and movement rate of a zombie waiting for the ripple (a held, stunned pose).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ripple", meta = (ClampMin = "0.01", ClampMax = "1")) float StunDilation = .2f;
    // The vendor damage number would read "999,999": destroyed for these kills.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ripple") bool bHideDamageNumbers = true;

    // Optional slow-motion beat: global dilation for SlowMotionSeconds real seconds, then 1.0 (never while the
    // game-over death cam owns the dilation).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Slow motion") bool bSlowMotion = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Slow motion", meta = (ClampMin = "0.05", ClampMax = "1")) float SlowMotionDilation = .3f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Slow motion", meta = (ClampMin = "0")) float SlowMotionSeconds = .35f;
};

// Ammo drop presentation, edited on BP_CyberAmmo (AHoverAmmoPickup::Presentation). NYC Survival only.
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverAmmoPresentation
{
    GENERATED_BODY()
    FHoverAmmoPresentation();

    // One of these at random on pickup (A_ItemPickup_001..004, already imported).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sound") TArray<TSoftObjectPtr<USoundBase>> PickupSounds;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Sound") float SoundVolume = 1.f;

    // Always-on overlay outline (the vendor shows its red outline only while the crosshair focuses the drop).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") TSoftObjectPtr<UMaterialInterface> Outline;
    // Multiplies the 35 cm box AHoverAmmoPickup::BeginPlay sizes it to.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual", meta = (ClampMin = "0.5", ClampMax = "3")) float ScaleMultiplier = 1.25f;
    // Hover above the floor (cm), bob amplitude (cm) and rate (Hz), spin (deg/s).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float BobLift = 16.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float BobHeight = 6.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float BobHz = .8f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float SpinDegrees = 90.f;
    // Pulsing point light (no shadows) so the drop reads at 10 m and in the dark street.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") FLinearColor GlintColor = FLinearColor(1.f, .78f, .3f);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float GlintCandela = 80.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float GlintRadius = 300.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Visual") float GlintHz = 1.2f;

    // Walk-over pickup (no X / F hold, which is also the reload button).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pickup") bool bAutoPickup = true;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Pickup") float AutoPickupRadius = 100.f;

    // "{0}" is the amount; "{1}" is the ammo name when the drop is not for the held gun.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "HUD") FText ToastFormat;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "HUD") FText OtherAmmoToastFormat;
};

// Per-world feedback state: the Nuke sequence (ripple, flash, banner, slow motion) and HUD toasts. Drawn by
// AHoverHUD::DrawHUD through DrawHUD / DrawReserveFlash. Ticks on its own undilated clock so the flash, banner and
// ripple keep their real-time lengths through the slow-motion beat; it does not tick while the game is paused.
UCLASS()
class HOVERFLIGHT_API UHoverPickupFeedback : public UTickableWorldSubsystem
{
    GENERATED_BODY()
  public:
    static UHoverPickupFeedback *Get(const UObject *WorldContext);
    static bool IsNYCSurvival(const UObject *WorldContext);

    // AHoverCyberPowerUp::OnOverlapBegin: true when the NYC sequence took the targets (the caller then skips its
    // same-frame 999,999 loop); false outside NYC Survival.
    static bool BeginNuke(AActor *Pickup, APawn *Picker, const TArray<AActor *> &Targets,
                          const FHoverNukePresentation &Presentation);

    void Toast(const FString &Text, FLinearColor Color);
    // Toast plus the held weapon's reserve flashing on the ammo counter.
    void NotifyAmmo(const FString &Text);

    // HUD hooks (no-ops while nothing is active).
    static void DrawHUD(AHUD *HUD);
    static void DrawReserveFlash(AHUD *HUD, int32 Clip, int32 Reserve, bool bMelee, float X, float Y, float Scale);

    // (clip, reserve) of the pawn's held weapon; (-1, -1) without one. Python proof and the pickups.
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") static FIntPoint GetPawnAmmo(APawn *Pawn);
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups", meta = (WorldContext = "WorldContextObject"))
    static UHoverPickupFeedback *GetFeedback(const UObject *WorldContextObject);

    // Python assertions (Scripts/ProveNukeAmmo.py). Ages are real seconds, -1 when it never happened.
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") float GetNukeAge() const;
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") int32 GetNukeTargetCount() const
    {
        return NukeTargetCount;
    }
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") int32 GetNukeKillCount() const
    {
        return NukeKillCount;
    }
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") int32 GetHiddenDamageNumbers() const
    {
        return HiddenDamageNumbers;
    }
    // One row per ripple kill: X distance from the pickup (cm), Y real seconds after the pickup, Z game seconds.
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") TArray<FVector> GetNukeKillRows() const
    {
        return NukeKillRows;
    }
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") float GetFlashAlpha() const;
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") bool IsBannerVisible() const;
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") FString GetBannerText() const
    {
        return Nuke.BannerText.ToString();
    }
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") FString GetLastToast() const
    {
        return LastToastText;
    }
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") float GetLastToastAge() const;
    UFUNCTION(BlueprintPure, Category = "Hover|Pickups") float GetReserveFlashAge() const;

    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;

  protected:
    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

  private:
    struct FRippleTarget
    {
        TWeakObjectPtr<AActor> Zombie;
        float Distance = 0.f;
        float Delay = 0.f;
        bool bDone = false;
    };
    struct FToast
    {
        FString Text;
        FLinearColor Color;
        double Start = 0.;
    };
    void StartNuke(const FVector &Origin, APawn *Picker, const TArray<AActor *> &Targets,
                   const FHoverNukePresentation &Presentation);
    void KillRippleTarget(FRippleTarget &Target);
    void DrawNuke(AHUD *HUD) const;
    void DrawToasts(AHUD *HUD) const;

    // Undilated, unpaused seconds since the subsystem started.
    double Clock = 0.;
    FHoverNukePresentation Nuke;
    FVector NukeOrigin = FVector::ZeroVector;
    double NukeStart = -1.;
    double NukeGameStart = 0.;
    TArray<FRippleTarget> Ripple;
    TWeakObjectPtr<AController> NukeInstigator;
    TWeakObjectPtr<APawn> NukeCauser;
    int32 NukeTargetCount = 0;
    int32 NukeKillCount = 0;
    int32 HiddenDamageNumbers = 0;
    TArray<FVector> NukeKillRows;
    bool bSlowMotionActive = false;
    double SlowMotionEnd = 0.;
    UPROPERTY() TObjectPtr<UForceFeedbackEffect> NukeRumble;

    TArray<FToast> Toasts;
    FString LastToastText;
    double LastToastStart = -1.;
    double ReserveFlashStart = -1.;
};

// Weapon-agnostic ammo buy point built on the vendor wall-buy actor that Cyber City uses for its three supply
// crates: Hold X / F tops up the held gun's reserve to MaxReserveAmmo for AmmoCost points. Placed in L_NYC_Survival
// only by Scripts/AuthorNukeAmmoStations.py, which needs the owner's OK (not placed by default).
UCLASS()
class HOVERFLIGHT_API AHoverAmmoStation : public AZE_WallBuyActor
{
    GENERATED_BODY()
  public:
    AHoverAmmoStation();
    virtual void OnConstruction(const FTransform &Transform) override;
    virtual bool CanInteract_Implementation(APawn *InteractingPawn) const override;
    virtual void Interact_Implementation(APawn *InteractingPawn) override;
    virtual FText GetInteractText_Implementation(APawn *InteractingPawn) const override;

    // Width the crate mesh is scaled to (cm).
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") float CrateWidth = 70.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") TSoftObjectPtr<USoundBase> PurchaseSound;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") TSoftObjectPtr<UMaterialInterface> Outline;
    // Prompt and toasts; "{0}" weapon name, "{1}" rounds, "{2}" cost.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") FText PromptFormat;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") FText FullText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") FText NoGunText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ammo Station") FText NoPointsText;
    UFUNCTION(BlueprintPure, Category = "Ammo Station") int32 GetAmmoCost() const
    {
        return AmmoCost;
    }

  protected:
    virtual void BeginPlay() override;

  private:
    // Rounds the held gun is missing below MaxReserveAmmo; -1 when the pawn holds no ammo-using gun.
    int32 MissingRounds(APawn *Pawn, AZE_WeaponBase **OutWeapon = nullptr) const;
};
