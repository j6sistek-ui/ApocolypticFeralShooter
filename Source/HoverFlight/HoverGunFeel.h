#pragma once
#include "CoreMinimal.h"
#include "Camera/CameraShakeBase.h"
#include "Engine/DataAsset.h"
#include "HoverGunFeel.generated.h"

class UAnimSequence;
class UForceFeedbackEffect;
class UNiagaraSystem;
class USoundBase;
class UZE_WeaponDefinition;

// (time, value) keys per motor. Built into a UForceFeedbackEffect at runtime, so no .uasset is required.
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverRumbleCurve
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, Category = "Rumble") TArray<FVector2D> LeftLarge;
    UPROPERTY(EditAnywhere, Category = "Rumble") TArray<FVector2D> LeftSmall;
    UPROPERTY(EditAnywhere, Category = "Rumble") TArray<FVector2D> RightLarge;
    UPROPERTY(EditAnywhere, Category = "Rumble") TArray<FVector2D> RightSmall;
    // An authored effect replaces the key lists when set.
    UPROPERTY(EditAnywhere, Category = "Rumble") TSoftObjectPtr<UForceFeedbackEffect> Override;
    bool IsEmpty() const
    {
        return LeftLarge.IsEmpty() && LeftSmall.IsEmpty() && RightLarge.IsEmpty() && RightSmall.IsEmpty() &&
               Override.IsNull();
    }
};

// Presentation for one weapon definition. Defaults are the enhanced (section 5) Ballista values;
// Legacy() reproduces the presentation that shipped before the opt-in gun feel.
USTRUCT(BlueprintType)
struct HOVERFLIGHT_API FHoverGunFeelTier
{
    GENERATED_BODY()
    FHoverGunFeelTier();

    // --- Tier and pierce ---
    UPROPERTY(EditAnywhere, Category = "Tier") int32 PaP = 0;
    UPROPERTY(EditAnywhere, Category = "Tier", meta = (ClampMin = "0", ClampMax = "8")) int32 Pierce = 0;
    UPROPERTY(EditAnywhere, Category = "Tier", meta = (ClampMin = "0", ClampMax = "1")) float PierceScale = .6f;

    // --- Tracer ---
    // Null keeps the tracer actor's default trail (NS_ArrowTrail_Basic_02).
    UPROPERTY(EditAnywhere, Category = "Tracer") TSoftObjectPtr<UNiagaraSystem> Tracer;
    UPROPERTY(EditAnywhere, Category = "Tracer") bool bTracerColor = true;
    // Magic-style systems expose User.ColorA/User.ColorB instead of User.Color.
    UPROPERTY(EditAnywhere, Category = "Tracer") bool bTracerColorAB = false;
    UPROPERTY(EditAnywhere, Category = "Tracer") FLinearColor TracerColor = FLinearColor(1.f, .65f, .25f);
    UPROPERTY(EditAnywhere, Category = "Tracer") FLinearColor TracerColorB = FLinearColor(1.f, .65f, .25f);
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerLength = 90.f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerWidth = .03f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerSpeed = 40000.f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerMinDuration = .12f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerMaxDuration = .22f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerLifetime = .14f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerTrailSize = 3.f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float TracerEmissive = 8.f;
    UPROPERTY(EditAnywhere, Category = "Tracer") float MinTracerDistance = 250.f;

    // --- Camera shake ---
    // Null uses the definition's FireCameraShake, then BP_M16_FireShake, then UHoverFireShake.
    UPROPERTY(EditAnywhere, Category = "Shake") TSubclassOf<UCameraShakeBase> FireShake;
    UPROPERTY(EditAnywhere, Category = "Shake") float ShakeScale = 1.f;

    // --- View recoil (degrees per shot; recovery in degrees per second) ---
    UPROPERTY(EditAnywhere, Category = "Recoil") bool bOverrideRecoil = false;
    UPROPERTY(EditAnywhere, Category = "Recoil") FVector2D RecoilKick = FVector2D(.35f, .15f);
    UPROPERTY(EditAnywhere, Category = "Recoil") float RecoilRecovery = 10.f;
    UPROPERTY(EditAnywhere, Category = "Recoil") float RecoilAutoRecoverFraction = .6f;
    UPROPERTY(EditAnywhere, Category = "Recoil") float RecoilDebtCap = 6.f;
    UPROPERTY(EditAnywhere, Category = "Recoil") float AimRecoilScale = .7f;
    UPROPERTY(EditAnywhere, Category = "Recoil") float RecoilJitter = .15f;

    // --- Sound and rumble ---
    UPROPERTY(EditAnywhere, Category = "Sound") float SoundVolume = 1.f;
    UPROPERTY(EditAnywhere, Category = "Sound") float SoundPitch = 1.f;
    UPROPERTY(EditAnywhere, Category = "Sound") float SoundPitchJitter = .03f;
    // One entry per shot, never the same one twice running; empty plays the definition's FireSound.
    UPROPERTY(EditAnywhere, Category = "Sound") TArray<TSoftObjectPtr<USoundBase>> FireSoundPool;
    UPROPERTY(EditAnywhere, Category = "Sound") TSoftObjectPtr<USoundBase> TailSound;
    // Picked like FireSoundPool; empty plays TailSound.
    UPROPERTY(EditAnywhere, Category = "Sound") TArray<TSoftObjectPtr<USoundBase>> TailSoundPool;
    UPROPERTY(EditAnywhere, Category = "Sound", meta = (ClampMin = "1")) int32 TailEveryN = 3;
    UPROPERTY(EditAnywhere, Category = "Rumble") FHoverRumbleCurve FireRumble;

    // --- Muzzle flash and light ---
    // 300 cd (600 until 2026-10-30: every rigged shot lit the whole character); a held rig scales it further
    // through UHoverGunRig::MuzzleLightScale. Legacy() keeps 0 (no light).
    UPROPERTY(EditAnywhere, Category = "Muzzle") float MuzzleLightIntensity = 300.f;
    UPROPERTY(EditAnywhere, Category = "Muzzle") float MuzzleLightRadius = 320.f;
    // Warm (1, .7, .4) since 2026-10-31; was the Ballista's blue-white (.75, .85, 1) ("comic book blue", owner
    // 2026-10-30 23:40), so even a non-rigged gun no longer lights the character blue. A held rig can replace it
    // outright (UHoverGunRig::MuzzleLightColorOverride). Legacy() has no light, so its colour is moot.
    UPROPERTY(EditAnywhere, Category = "Muzzle") FLinearColor MuzzleLightColor = FLinearColor(1.f, .70f, .40f);
    UPROPERTY(EditAnywhere, Category = "Muzzle") float MuzzleLightSeconds = .06f;
    UPROPERTY(EditAnywhere, Category = "Muzzle") float MuzzleFlashSeconds = .10f;

    // --- Third-person fire reaction ---
    UPROPERTY(EditAnywhere, Category = "Animation") TSoftObjectPtr<UAnimSequence> TPFireAction;
    UPROPERTY(EditAnywhere, Category = "Animation", meta = (ClampMin = "1")) int32 TPFireEveryN = 4;

    // --- Kill punctuation ---
    UPROPERTY(EditAnywhere, Category = "Kill") float KillTimeDilation = .15f;
    UPROPERTY(EditAnywhere, Category = "Kill") float KillHitStopSeconds = .07f;
    UPROPERTY(EditAnywhere, Category = "Kill") bool bKillFlash = true;

    // The pre-gun-feel presentation: .55/.014 tracer at D/90000 clamped .06-.09, Emissive 2,
    // Lifetime .06, Trail Size 1.4, orange colour, volume .60 with +-4% pitch, .09 s flash,
    // no light, no pierce, no view recoil, no shake and no hit-stop.
    static const FHoverGunFeelTier &Legacy();

    // Random FireSoundPool entry other than InOutLast, which is updated; null when the pool is empty.
    USoundBase *PickFireSound(int32 &InOutLast) const;
    // TailSoundPool entry picked the same way, else TailSound.
    USoundBase *PickTailSound(int32 &InOutLast) const;
};

UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverGunFeel : public UPrimaryDataAsset
{
    GENERATED_BODY()
  public:
    UHoverGunFeel();
    UPROPERTY(EditAnywhere, Category = "Tiers") FHoverGunFeelTier Default;
    // Keyed by weapon-definition asset name, for example DA_NYC_Ballista_3.
    UPROPERTY(EditAnywhere, Category = "Tiers") TMap<FName, FHoverGunFeelTier> Tiers;

    UPROPERTY(EditAnywhere, Category = "Hit feedback") TSoftObjectPtr<USoundBase> HitConfirmSound;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") TSoftObjectPtr<USoundBase> HeadshotSound;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") TSoftObjectPtr<USoundBase> KillSound;
    // Impact layer under the cues above: one entry per confirmed hit, never the same one twice running,
    // played 2D at HitConfirmPoolVolume with the headshot and kill pitch shifts. Empty adds nothing.
    UPROPERTY(EditAnywhere, Category = "Hit feedback") TArray<TSoftObjectPtr<USoundBase>> HitConfirmSoundPool;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float HitConfirmPoolVolume = .6f;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float HeadshotPoolPitch = 1.15f;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float KillPoolPitch = .9f;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FHoverRumbleCurve HitRumble;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FHoverRumbleCurve HeadshotRumble;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FHoverRumbleCurve KillRumble;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FHoverRumbleCurve KillHeadshotRumble;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float HitMarkerSeconds = .12f;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FLinearColor BodyMarkerColor = FLinearColor::White;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FLinearColor HeadMarkerColor = FLinearColor(1.f, .15f, .1f);
    UPROPERTY(EditAnywhere, Category = "Hit feedback") FLinearColor KillMarkerColor = FLinearColor(1.f, .85f, .2f);
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float KillMarkerScale = 1.5f;
    UPROPERTY(EditAnywhere, Category = "Hit feedback") float KillStingMinInterval = .08f;

    UPROPERTY(EditAnywhere, Category = "Shake") float ThirdPersonShakeScale = 1.f;
    UPROPERTY(EditAnywhere, Category = "Shake") float AimingShakeScale = .6f;
    UPROPERTY(EditAnywhere, Category = "Shake") float FirstPersonShakeScale = .8f;

    // --- Melee (audio pass 2026-10-31: "no melee sounds") ---
    // A whoosh on every katana swing start (Etherion S_Whoosh_1..10) and the owner's Bladecutting set on a
    // confirmed katana hit, both picked without back-to-back repeats.
    UPROPERTY(EditAnywhere, Category = "Melee") TArray<TSoftObjectPtr<USoundBase>> MeleeSwingSoundPool;
    UPROPERTY(EditAnywhere, Category = "Melee") float MeleeSwingVolume = .8f;
    UPROPERTY(EditAnywhere, Category = "Melee") TArray<TSoftObjectPtr<USoundBase>> MeleeHitSoundPool;
    UPROPERTY(EditAnywhere, Category = "Melee") float MeleeHitVolume = 1.f;

    // --- Footsteps ("no footsteps") ---
    // The owner's WW2 walk / run sets (Audio/NYC/Player/Footsteps). AHoverPilot::UpdateFootsteps plants a step
    // when a ball bone drops back under FootstepPlantHeight after rising past FootstepLiftHeight (cm above the
    // capsule bottom), or by cadence when the clip never lifts that far. Run pools above FootstepRunSpeed cm/s.
    // The recordings peak near -25 dBFS, hence the volume above 1.
    UPROPERTY(EditAnywhere, Category = "Footsteps") TArray<TSoftObjectPtr<USoundBase>> FootstepWalkConcrete;
    UPROPERTY(EditAnywhere, Category = "Footsteps") TArray<TSoftObjectPtr<USoundBase>> FootstepWalkDirt;
    UPROPERTY(EditAnywhere, Category = "Footsteps") TArray<TSoftObjectPtr<USoundBase>> FootstepWalkPuddle;
    UPROPERTY(EditAnywhere, Category = "Footsteps") TArray<TSoftObjectPtr<USoundBase>> FootstepRunConcrete;
    UPROPERTY(EditAnywhere, Category = "Footsteps") TArray<TSoftObjectPtr<USoundBase>> FootstepRunPuddle;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepVolume = 1.7f;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepRunSpeed = 520.f;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepLiftHeight = 11.f;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepPlantHeight = 6.f;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepWalkStride = 72.f;
    UPROPERTY(EditAnywhere, Category = "Footsteps") float FootstepRunStride = 115.f;

    // Falls back to Default, logging HOVER_RIFLE_TIER missing <name> once per key.
    const FHoverGunFeelTier &Find(const UZE_WeaponDefinition *Definition) const;
    // Random HitConfirmSoundPool entry other than InOutLast, which is updated; null when the pool is empty.
    USoundBase *PickHitConfirmSound(int32 &InOutLast) const;
    USoundBase *PickMeleeSwingSound(int32 &InOutLast) const;
    USoundBase *PickMeleeHitSound(int32 &InOutLast) const;
    // Surface 0 concrete, 1 dirt, 2 puddle; a run on dirt falls back to run concrete (no such recording).
    USoundBase *PickFootstep(bool bRun, int32 Surface, int32 &InOutLast) const;

    // Transient, rooted section-5 table, used until a DA_HoverGunFeel asset is authored.
    static const UHoverGunFeel *BuiltIn();

  private:
    mutable TSet<FName> ReportedMissing;
};

namespace HoverHaptics
{
// One channel per non-empty key list; Duration is set explicitly to the last key time.
UForceFeedbackEffect *Build(UObject *Outer, const FHoverRumbleCurve &Curve);
} // namespace HoverHaptics

// Short additive noise for each shot. Kept in-module so no EngineCameras dependency is needed.
UCLASS()
class HOVERFLIGHT_API UHoverShakePattern : public UCameraShakePattern
{
    GENERATED_BODY()
  public:
    UHoverShakePattern(const FObjectInitializer &ObjectInitializer);
    UPROPERTY(EditAnywhere, Category = "Shake") float Duration = .12f;
    UPROPERTY(EditAnywhere, Category = "Shake") float BlendInTime = .02f;
    UPROPERTY(EditAnywhere, Category = "Shake") float BlendOutTime = .08f;
    // Amplitude (X) and frequency in Hz (Y) per axis; location in cm, rotation and FOV in degrees.
    UPROPERTY(EditAnywhere, Category = "Shake") FVector2D Pitch = FVector2D(.7f, 28.f);
    UPROPERTY(EditAnywhere, Category = "Shake") FVector2D Yaw = FVector2D(.25f, 22.f);
    UPROPERTY(EditAnywhere, Category = "Shake") FVector2D Roll = FVector2D(.15f, 18.f);
    UPROPERTY(EditAnywhere, Category = "Shake") FVector2D FOV = FVector2D(.6f, 20.f);
    UPROPERTY(EditAnywhere, Category = "Shake") FVector2D X = FVector2D(1.2f, 24.f);

  private:
    float Age = 0;
    float Seeds[5] = {};
    virtual void GetShakePatternInfoImpl(FCameraShakeInfo &OutInfo) const override;
    virtual void StartShakePatternImpl(const FCameraShakePatternStartParams &Params) override;
    virtual void UpdateShakePatternImpl(const FCameraShakePatternUpdateParams &Params,
                                        FCameraShakePatternUpdateResult &OutResult) override;
    virtual bool IsFinishedImpl() const override;
};

UCLASS()
class HOVERFLIGHT_API UHoverFireShake : public UCameraShakeBase
{
    GENERATED_BODY()
  public:
    UHoverFireShake(const FObjectInitializer &ObjectInitializer);
};

// P1, not wired yet: incoming zombie hit.
UCLASS()
class HOVERFLIGHT_API UHoverHurtShake : public UCameraShakeBase
{
    GENERATED_BODY()
  public:
    UHoverHurtShake(const FObjectInitializer &ObjectInitializer);
};

// P1, not wired yet: nearby explosion.
UCLASS()
class HOVERFLIGHT_API UHoverBlastShake : public UCameraShakeBase
{
    GENERATED_BODY()
  public:
    UHoverBlastShake(const FObjectInitializer &ObjectInitializer);
};
