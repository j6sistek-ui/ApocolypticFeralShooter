#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "HoverTestLevelPolicy.h"
#include "HoverGunRig.h"
#include "HoverPilot.generated.h"

class UHLRawMovementComponent;

class UAnimSequence;
class UCameraComponent;
class UPoseableMeshComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UBoxComponent;
class UNiagaraComponent;
class UNiagaraSystem;
class UFXSystemAsset;
class AZE_WeaponBase;
class UZE_WeaponDefinition;
class UHoverGunFeel;
class UForceFeedbackEffect;
class UPointLightComponent;
struct FHoverGunFeelTier;
struct FHoverRumbleCurve;

USTRUCT(BlueprintType)
struct FHoverBodyPart
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere) FName Name;
    UPROPERTY(EditAnywhere) TObjectPtr<USkeletalMesh> Mesh;
    UPROPERTY(EditAnywhere) TArray<TObjectPtr<UMaterialInterface>> Materials;
    UPROPERTY(EditAnywhere) TMap<FName, float> Morphs;
    UPROPERTY(EditAnywhere) TObjectPtr<class UPhysicsAsset> PhysicsOverride;
};

UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverPilotAssets : public UDataAsset
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere) TArray<FHoverBodyPart> BodyParts;
    UPROPERTY(EditAnywhere) TObjectPtr<USkeletalMesh> Glider;
    UPROPERTY(EditAnywhere) TObjectPtr<UStaticMesh> Gun;
    UPROPERTY(EditAnywhere, Category = "Weapon") TObjectPtr<UStaticMesh> GunOptic;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideIdle;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideMove;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideLeft;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideRight;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideDown;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideReverse;
    UPROPERTY(EditAnywhere) TObjectPtr<class UBlendSpace> RideBlend;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<class UBlendSpace> RideAimBlend;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideClimbPose;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideDivePose;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideStart;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideStop;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideLeftStart;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideLeftEnd;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideRightStart;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideRightEnd;
    UPROPERTY(EditAnywhere, Category = "Glider animation") TObjectPtr<UAnimSequence> RideRecoil;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> AimStart;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> AimEnd;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Fire;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RifleAim;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideGunPose;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Walk;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Stand;
    UPROPERTY(EditAnywhere) TObjectPtr<class UBlendSpace> Locomotion;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> TurnLeft;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> TurnRight;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> JumpPose;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> FallPose;
    UPROPERTY(EditAnywhere, Category = "Appearance") bool bBalancedTestLighting = true;
    UPROPERTY(EditAnywhere, Category = "Appearance") float TestExposureBias = .25f;
    UPROPERTY(EditAnywhere, Category = "Appearance") float TestBloomIntensity = .2f;
    UPROPERTY(EditAnywhere) TObjectPtr<UNiagaraSystem> BoosterEffect;
    UPROPERTY(EditAnywhere) TObjectPtr<UFXSystemAsset> ShockwaveEffect;
    UPROPERTY(EditAnywhere) TObjectPtr<UFXSystemAsset> MuzzleEffect;
    UPROPERTY(EditAnywhere, Category = "Weapon") FVector GunMuzzle = FVector(0, 46, 2);
    UPROPERTY(EditAnywhere, Category = "Weapon") FVector GunForward = FVector::RightVector;
    UPROPERTY(EditAnywhere, Category = "Weapon") FVector GunGrip = FVector(0, -20, -3);
    UPROPERTY(EditAnywhere, Category = "Weapon") FVector GunSupportGrip = FVector(-22, 0, -8);
    UPROPERTY(EditAnywhere, Category = "Weapon") FVector GunSight = FVector(0, 0, 12);
    UPROPERTY(EditAnywhere, Category = "Weapon", meta = (ClampMin = "0", ClampMax = "10"))
    float GunRecoilPitch = 2.6f;
    UPROPERTY(EditAnywhere, Category = "Weapon", meta = (ClampMin = "0", ClampMax = "10"))
    float GunRecoilDistance = 3.f;
    UPROPERTY(EditAnywhere, Category = "Weapon", meta = (ClampMin = "1", ClampMax = "60"))
    float GunRecoilRecovery = 22.f;
    UPROPERTY(EditAnywhere, Category = "Weapon") TObjectPtr<UFXSystemAsset> SurfaceImpact;
    UPROPERTY(EditAnywhere, Category = "Weapon") TObjectPtr<class USoundBase> ShotSound;
    // Opt-in gun feel tiers; null uses UHoverGunFeel::BuiltIn().
    UPROPERTY(EditAnywhere, Category = "Weapon") TObjectPtr<UHoverGunFeel> GunFeel;
    // Default rigged rifle (SK_M4A1): the rig for any definition GunRigs has no key for. While RiggedGun
    // is set the pilot shows the skeletal pair (ViewGunSkel/WorldGunSkel) with these mechanical clips
    // and hides the static Gun/GunOptic; empty keeps the Ballista path unchanged. Clips: Idle loops
    // between actions, Fire cycles the bolt per round, DryFire is the empty-magazine click, Reload starts
    // bolt locked back, and Chamber racks the charging handle once on equip. Fire/Reload are rate-scaled to the
    // weapon's cadence/ReloadDuration so the body clips and the magazine agree in time.
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<USkeletalMesh> RiggedGun;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> GunIdle;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> GunFire;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> GunDryFire;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> GunReload;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> GunChamber;
    // Upper-body aim pose for a rig whose Stance is Pistol (both hands on the grip): MF_Pistol_Idle_ADS,
    // duplicated beside MF_Rifle_Idle_ADS so it plays on Vexa's skeleton the same way. Null keeps RifleAim.
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> PistolAim;
    // Design A1 (2026-10-30): the stance fire reactions as frame-0-based local-space ADDITIVES (MA_Rifle_Fire_Add /
    // MA_Pistol_Fire_Add, duplicates of the CLS MM_*_Fire clips made by Scripts/BindFireAdditives.py). With a rigged
    // gun in third person the body no longer plays the feel tier's TPFireAction montage on the CLS driver (that path
    // dropped the aim layer and the support IK, leaving the left hand ahead of the muzzle); the proxy restarts this
    // additive over the stance aim pose on every shot instead, before the support IK, so both hands ride the recoil
    // with the gun. Null: no body reaction for that stance. *RecoilScale scales the additive's weight.
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> RifleFireAdd;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TObjectPtr<UAnimSequence> PistolFireAdd;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged", meta = (ClampMin = "0", ClampMax = "3"))
    float RifleRecoilScale = 1.f;
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged", meta = (ClampMin = "0", ClampMax = "3"))
    float PistolRecoilScale = 1.f;
    // Socket (or bone) names on RiggedGun. With bRiggedGunSocketsDriveOffsets their component-space
    // transforms replace GunMuzzle/GunGrip/GunSupportGrip/GunSight at BeginPlay and GunForward
    // becomes +X, so hand placement, support-grip IK and muzzle effects need no hand tuning; the
    // DA vectors above stay the fallback for any socket that is missing.
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") FName GunMuzzleSocket = TEXT("muzzle");
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") FName GunEjectSocket = TEXT("ejection_port");
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") FName GunSightSocket = TEXT("sight");
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") FName GunGripSocket = TEXT("grip_r");
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") FName GunSupportSocket = TEXT("grip_l");
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") bool bRiggedGunSocketsDriveOffsets = true;
    // Per-weapon rigs, keyed by weapon-definition asset name (UHoverGunRig::NormalizeWeaponKey: a trailing
    // _<digits> is dropped, so DA_NYC_M16_3 finds DA_NYC_M16). An exact name wins over the normalized one.
    // A key whose value is None pins that definition to the static Ballista; a definition with no key
    // uses the loose RiggedGun fields above, or the Ballista when RiggedGun is empty.
    UPROPERTY(EditAnywhere, Category = "Weapon|Rigged") TMap<FName, TObjectPtr<UHoverGunRig>> GunRigs;
    // True when GunRigs has a key for the name (exact, then normalized); OutRig may then be null.
    bool FindGunRig(FName DefinitionName, const UHoverGunRig *&OutRig) const;
    // NYC Section 2 Â§4 over-the-shoulder camera. Read only while the level policy forces third
    // person (NYC Survival); the 430 cm review camera stays everywhere else.
    UPROPERTY(EditAnywhere, Category = "Survival camera", meta = (ClampMin = "50"))
    float SurvivalArmLength = 300.f;
    UPROPERTY(EditAnywhere, Category = "Survival camera", meta = (ClampMin = "50"))
    float SurvivalAimArmLength = 210.f;
    UPROPERTY(EditAnywhere, Category = "Survival camera") FVector SurvivalSocketOffset = FVector(0, 58, 42);
    UPROPERTY(EditAnywhere, Category = "Survival camera", meta = (ClampMin = "40", ClampMax = "120"))
    float SurvivalHipFOV = 88.f;
    UPROPERTY(EditAnywhere, Category = "Survival camera", meta = (ClampMin = "30", ClampMax = "120"))
    float SurvivalAimFOV = 68.f;
    // Survival fill light (visual pass 2026-10-31, owner: "maybe the lighting on the player just a bit"): a soft,
    // shadowless point light on lighting channel 1 that only Vexa and her held guns receive. Offset is capsule
    // space (behind / right / up: the over-the-shoulder camera's side). Intensity 0 starts it off and
    // `HoverFillLight 1 <cd>` turns it on in play. The NYC sun is 5 lux under a low exposure range, so a few
    // candelas already read.
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light", meta = (ClampMin = "0", ClampMax = "100"))
    float SurvivalFillLightIntensity = 2.5f;
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light", meta = (ClampMin = "50", ClampMax = "1000"))
    float SurvivalFillLightRadius = 400.f;
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light", meta = (ClampMin = "0", ClampMax = "100"))
    float SurvivalFillLightSourceRadius = 40.f;
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light", meta = (ClampMin = "0", ClampMax = "1"))
    float SurvivalFillLightSpecular = .35f;
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light")
    FVector SurvivalFillLightOffset = FVector(-140, 90, 75);
    UPROPERTY(EditAnywhere, Category = "Survival camera|Fill light")
    FLinearColor SurvivalFillLightColor = FLinearColor(1.f, .93f, .85f);
    // Third-person self-occlusion: when spring-arm collision pins the review camera within this
    // distance of the capsule centre (zombies pushing Vexa into a wall or the parked truck), her
    // body and held rifle are hidden from her own view (shadow kept) until the camera backs off past
    // this distance + 15 cm. Normal arms sit ~220-310 cm out. Applies to every review camera.
    UPROPERTY(EditAnywhere, Category = "Survival camera", meta = (ClampMin = "0", ClampMax = "300"))
    float SurvivalMeshHideDistance = 95.f;
};

UCLASS()
class HOVERFLIGHT_API AHoverPilot : public ACharacter
{
    GENERATED_BODY()
  public:
    AHoverPilot(const FObjectInitializer &ObjectInitializer);
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void Landed(const FHitResult &Hit) override;
    virtual void OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
    virtual void OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust) override;
    virtual float TakeDamage(float Damage, const FDamageEvent &Event, AController *EventInstigator,
                             AActor *Causer) override;
    virtual void SetupPlayerInputComponent(UInputComponent *Input) override;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly) bool bParkourMovement = false;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly) bool bCLSLocomotion = false;
    // BlueprintReadOnly so the headless verify can read IsActionPlaying through it (plain UPROPERTYs are invisible to
    // Python's get_editor_property).
    UPROPERTY(BlueprintReadOnly) TObjectPtr<class UHoverLocomotionBridge> LocomotionBridge;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<class UHoverCombatBridge> Combat;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<class AHoverMeleeWeapon> MeleeWeapon;
    UFUNCTION(BlueprintCallable) void Melee();
    UFUNCTION(BlueprintCallable) void ToggleMeleeWeapon();
    UFUNCTION(BlueprintPure) bool IsMeleeEquipped() const
    {
        return bMeleeEquipped;
    }
    UFUNCTION(BlueprintCallable) void SetInvincible(bool Enabled)
    {
        bInvincible = Enabled && !bMortalLocked;
    }
    UFUNCTION(BlueprintPure) bool IsInvincible() const
    {
        return bInvincible;
    }
    UFUNCTION(BlueprintPure) bool IsDefeated() const
    {
        return bDefeated;
    }
    UFUNCTION(BlueprintPure) float GetHealth() const;
    // The survival component's pool (100 everywhere, 150 in NYC Survival); 100 without the bridge.
    UFUNCTION(BlueprintPure) float GetMaxHealth() const;
    UFUNCTION(BlueprintCallable) bool ApplyStompKnockdown(FVector Origin);
    UFUNCTION(BlueprintPure) bool IsKnockedDown() const
    {
        return bKnockedDown;
    }
    void ShowStompPulse(const FVector &Location, const FVector &Normal, float Radius, bool Close);
    UFUNCTION(BlueprintPure) bool IsThirdPersonView() const
    {
        return bReview;
    }
    UFUNCTION(BlueprintPure) bool IsOnFoot() const
    {
        return !bMounted;
    }
    UFUNCTION(Exec) void HoverMount();
    bool PrepareForRide();
    UFUNCTION(Exec) void HoverView();
    UFUNCTION(Exec) void HoverReset();
    UFUNCTION(Exec) void HoverStatus();
    // Life Engine (HL Movement System, Source/Quake-style solver) trial, NYC Survival only (owner 2026-10-31):
    // created at BeginPlay under survival rules and ON by default there; `LifeEngine` in the console toggles it in
    // place (1 on, 0 off, no argument flips) so the two locomotions compare on the same spot. Never exists in the
    // other modes. While active the character movement sits in MOVE_None and mirrors the solver's velocity so the
    // animation, aim and camera code keep reading GetVelocity(); the board, parkour, knockdown and defeat suspend it.
    UFUNCTION(Exec) void LifeEngine(int32 Mode = -1);
    // NYC Survival fill light on Vexa (visual pass 2026-10-31): `HoverFillLight` flips it, `HoverFillLight 0` / `1`
    // sets it, a second argument sets the intensity in candelas (A/B without the F6 menu).
    UFUNCTION(Exec) void HoverFillLight(int32 Mode = -1, float Intensity = -1.f);
    // Audio pass 2026-10-31: the katana swing whoosh (AHoverMeleeWeapon::PlayFireAnimation calls it).
    void PlayMeleeSwingSound();
    UFUNCTION(BlueprintPure) bool IsLifeEngineActive() const
    {
        return bLifeEngineActive;
    }
    // The F6 test-settings menu row: present only where the solver exists (NYC Survival).
    bool HasLifeEngine() const
    {
        return LifeMovement != nullptr;
    }
    bool IsLifeEngineEnabled() const
    {
        return bLifeEngine;
    }
    // AFS 2026-11-01 (walking proof): the parkour hand-off flag, read by UHoverIntegrationAuthoring::DescribeWalkState.
    bool IsLifeEngineTemplateOverride() const
    {
        return bLifeEngineTemplateOverride;
    }
    UPROPERTY(BlueprintReadOnly, Category = "Life Engine") TObjectPtr<UHLRawMovementComponent> LifeMovement;
    UFUNCTION(BlueprintCallable) void SetParkourCrouch(bool Held);
    void CancelPostureInput();
    UFUNCTION(BlueprintPure) int32 GetShotsFired() const
    {
        return ShotsFired;
    }
    UFUNCTION(BlueprintPure) bool IsMounted() const
    {
        return bMounted;
    }
    UFUNCTION(BlueprintPure) bool IsAiming() const
    {
        return bAiming;
    }
    // Strafe rule: melee, aiming, a raised gun, first person, or (NYC Â§4) a reload in progress.
    bool UsesAimFacing() const;
    UFUNCTION(BlueprintPure) bool UsesSupportedProne() const
    {
        return bProne && !bDiving && (ProneLandingTime > 0 || UsesAimFacing() || GetVelocity().Size2D() < 15.f);
    }
    bool bInvincible = true;
    // Set by a level policy that forces mortality (NYC Survival); SetInvincible then stays off.
    bool bMortalLocked = false;
    // Section 5 survival rules (sprint-fire gate); set from the level policy at BeginPlay.
    bool bSurvivalRules = false;
    bool bForcedThirdPerson = false;
    bool bSandboxResetAllowed = true;
    bool bDefeated = false;
    float SandboxHealth = 100.f, DefeatedUntil = 0.f, RespawnGraceUntil = 0.f;
    TWeakObjectPtr<AController> DefeatedController;
    UFUNCTION(BlueprintPure) FVector GetMuzzlePosition() const;
    UFUNCTION(BlueprintPure) float GetBoostCharge() const
    {
        return BoostCharge;
    }
    UFUNCTION(BlueprintPure) float GetBoardPitch() const
    {
        return BoardPitch;
    }
    UFUNCTION(BlueprintPure) float GetBoardBank() const
    {
        return BoardBank;
    }
    UFUNCTION(BlueprintPure) float GetWingSweep() const
    {
        return WingSweep;
    }
    UFUNCTION(BlueprintPure) bool CanDismount() const;
    UFUNCTION(BlueprintPure) bool IsProne() const
    {
        return bProne;
    }
    UFUNCTION(BlueprintPure) bool IsGroundSliding() const
    {
        return GroundSlideTime > 0;
    }
    UFUNCTION(BlueprintPure) bool IsDiving() const
    {
        return bDiving;
    }
    UFUNCTION(BlueprintPure) FVector GetLocomotionState() const
    {
        return FVector(GroundDirection, GetVelocity().Size2D(), GroundYawRate);
    }
    UFUNCTION(BlueprintPure) float HoldProgress() const
    {
        return HoldTime / .65f;
    }
    UFUNCTION(BlueprintPure) FString GetPrompt() const;
    float GetSpeedMps() const
    {
        return GetVelocity().Size() / 100.f;
    }
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> FirstPersonCamera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> ReviewArm;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> ReviewCamera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> ViewGun;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WorldGun;
    // Rigged rifle pair (UHoverPilotAssets::RiggedGun); same attachment and visibility rules as the
    // static pair, which stays hidden while these carry a mesh. ActiveGunPrimitive picks per view.
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> ViewGunSkel;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> WorldGunSkel;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> ViewArms;
    UFUNCTION(BlueprintPure) bool UsesRiggedGun() const
    {
        return bRiggedGun;
    }
    // The rifle component the given view renders: the skeletal pair while rigged, else the static
    // Ballista pair. Placement, visibility, muzzle FX/light/sound, shell eject and GetMuzzlePosition
    // all go through this so both paths share one code path.
    UPrimitiveComponent *ActiveGunPrimitive(bool bReviewView) const;
    // Rigged-gun clip playback (single-node on both skeletal components); no-ops without RiggedGun.
    // MaxSeconds > 0 speeds the clip up to fit the fire interval so the bolt is home before the next round.
    // bLastRound (the shot that emptied the clip) plays the rig's FireLast and then loops IdleEmpty.
    UFUNCTION(BlueprintCallable) void PlayGunFire(float MaxSeconds = 0.f, bool bLastRound = false);
    UFUNCTION(BlueprintCallable) void PlayGunDryFire();
    // Rate-scaled so the 2.4 s clip fits the weapon's ReloadDuration, matching the body's MM_Rifle_Reload.
    // bTactical (rounds left at reload start) plays the rig's ReloadTactical, else the empty Reload.
    UFUNCTION(BlueprintCallable) void PlayGunReload(float Duration, bool bTactical = false);
    UFUNCTION(BlueprintCallable) void PlayGunChamber();
    // Stops the current clip (reload cancel) and returns to GunIdle.
    UFUNCTION(BlueprintCallable) void StopGunClip();
    // Swaps the held gun at runtime: a rig with a Mesh puts it and its clips on the skeletal pair and
    // re-derives the socket offsets; null (or no Mesh) returns to the static Ballista. Re-logs HOVER_GUN.
    // The rig already applied is a no-op. AHoverCyberRifle::OnEquipped calls it with FindGunRig.
    UFUNCTION(BlueprintCallable) void ApplyGunRig(const UHoverGunRig *Rig);
    UFUNCTION(BlueprintPure) const UHoverGunRig *GetGunRig() const
    {
        return GunRig;
    }
    // Gallery hook (Scripts/CaptureGuns.py FLASH_GALLERY): writes the held rig's MuzzleFlashOverride in memory so
    // the next shot spawns System (null = back to the weapon definition's flash). The rig asset is not marked dirty,
    // so nothing reaches disk; the caller restores the original. No-op while the static Ballista shows (no rig).
    UFUNCTION(BlueprintCallable) void SetMuzzleFlashOverride(UNiagaraSystem *System);
    // The rig for a held definition: Assets->GunRigs (exact, then normalized key), else the default rig
    // built from the loose RiggedGun fields, else null (static Ballista).
    const UHoverGunRig *FindGunRig(const UZE_WeaponDefinition *Definition) const;
    // The upper-body aim pose the body holds for the held gun: Assets->PistolAim for a Pistol-stance rig
    // when it is set, else Assets->RifleAim (the Ballista and every rifle rig).
    UFUNCTION(BlueprintPure) UAnimSequence *GetStanceAimPose() const;
    // Gun-space (X forward, origin grip_r) offset from the grip to where the left palm centre goes: the
    // rig's HandTargetSocket read live from Gun's current pose when rigged and present (the Reload clips
    // key it to the magazine), else the static support grip. Gun is the pair member the caller renders.
    FVector SupportGripOffset(const USkeletalMeshComponent *Gun) const;
    // Where the right palm centre sits in gun space (UHoverGunRig::GripSeatOffset from grip_r; the Ballista keeps its
    // grip) and the rig's extra gun-space rotation about that point (identity when not rigged). Every hand anchor
    // (both gun views, the left-hand IK base) uses these; gun-side points keep GunGrip.
    FVector GunSeatPoint() const
    {
        return bRiggedGun && GunRig ? GunGrip + GunRig->GripSeatOffset : GunGrip;
    }
    FQuat GunGripRotation() const
    {
        return bRiggedGun && GunRig ? GunRig->GripRotationOffset.Quaternion() : FQuat::Identity;
    }
    // Design B1: the left hand's orientation delta and finger curl the rig keys on the same hand_l_target bone:
    // OutRotation = the bone's gun-space (RTS_Component, scale stripped) rotation, a delta from its identity rest;
    // OutCurl = the bone's LOCAL scale X (GetBoneSpaceTransforms, never the component-space scale that carries the
    // root's x100). Identity / 1 when not rigged, no bone, or the pose is not evaluated yet.
    void SupportHandPose(const USkeletalMeshComponent *Gun, FQuat &OutRotation, float &OutCurl) const;
    // Design A1: the stance fire additive for the held rig (Assets->RifleFireAdd / PistolFireAdd), with its scale;
    // null when not rigged, mounted, or the asset is unbound or not a valid additive.
    UAnimSequence *GetStanceFireAdditive(float &OutScale) const;
    // The gun rides the right hand's kick (2026-10-30 23:30, "her hand is not on the grip"): the stance fire additive
    // turns hand_r, so UpdateGunTransform composes the rigged gun's world rotation as (hand_r now) * (hand_r at rest
    // in the settled aim pose)^-1, clamped to GunHandKickMaxDeg, applied over the aim-ray rotation. Read-outs for the
    // headless verify: the kick in the body mesh's component space, its angle, the world rotation the aim ray alone
    // gave this frame (the gun's world rotation is mesh * kick * mesh^-1 * this), and whether a rest is cached.
    UPROPERTY(BlueprintReadOnly) FQuat GunHandKick = FQuat::Identity;
    UPROPERTY(BlueprintReadOnly) float GunHandKickDeg = 0.f;
    UPROPERTY(BlueprintReadOnly) FQuat GunAimWorldRotation = FQuat::Identity;
    UPROPERTY(BlueprintReadOnly) bool bGunHandRestValid = false;
    static constexpr float GunHandKickMaxDeg = 25.f;
#if WITH_EDITOR
    // Headless proof hook (design B2 synthetic test): while enabled, UpdateAppearance feeds these instead of the
    // rig bone's rotation / curl. Set through UHoverAuthoring::SetSupportHandOverride; never read in a cooked game.
    bool bSupportHandOverride = false;
    FQuat SupportHandOverrideRotation = FQuat::Identity;
    float SupportHandOverrideCurl = 1.f;
#endif
    // Revolver cylinder index in degrees [0, 360): advanced by the rig's IndexDegrees per Fire, DryFire and
    // Chamber when its CylinderBone is set, reset by every rig swap. FinalizeGunPose turns CylinderBone (and
    // its children) by GunCylinderApplied about the bone's X after every clip evaluation, so the one-chamber
    // turn each indexing clip authors (EM_08's chambers are not 6-fold symmetric) carries over into Idle
    // instead of snapping back to rest.
    UPROPERTY(BlueprintReadOnly) float GunCylinderAngle = 0.f;
    // The additive the bone gets right now: GunCylinderAngle, minus IndexDegrees while Fire, DryFire or
    // Chamber is still turning the cylinder itself (the clip ends at +IndexDegrees, then Idle resumes).
    UFUNCTION(BlueprintPure) float GunCylinderApplied() const;

    // Section 5 gun feel. Off by default; [AFS.Gunplay] EnhancedFeel=True, -AFSGunFeel or the NYC mode enable it.
    UPROPERTY(BlueprintReadOnly) bool bEnhancedGunFeel = false;
    const UHoverGunFeel *GetGunFeel() const;
    void NotifyHitConfirmed(bool Headshot, bool Kill, const AActor *Causer);
    float GetHitMarkerAge() const;
    bool WasLastHitHeadshot() const
    {
        return bLastHitHeadshot;
    }
    bool WasLastHitKill() const
    {
        return bLastHitKill;
    }
    float GetKillFlashAge() const;
    // Automated evidence: rumble and shake are no-ops under NullRHI without a pad.
    UPROPERTY(BlueprintReadOnly) int32 FireShakeCount = 0;
    UPROPERTY(BlueprintReadOnly) int32 RumbleRequestCount = 0;
    UPROPERTY(BlueprintReadOnly) int32 HitMarkCount = 0;
    UPROPERTY(BlueprintReadOnly) int32 KillStingCount = 0;
    // Self-occlusion probe: hide/show transitions of the camera-too-close body hide (HOVER_CAM_HIDE).
    UPROPERTY(BlueprintReadOnly) int32 CameraBodyHideCount = 0;
    UPROPERTY(BlueprintReadOnly) bool bCameraHidesBody = false;

  private:
    friend class AHoverCyberRifle;
    UPROPERTY() TObjectPtr<UHoverPilotAssets> Assets;
    // Gun-space offsets the placement, IK and muzzle code read. Copied from the DA at BeginPlay and,
    // for a rigged gun with bRiggedGunSocketsDriveOffsets, overwritten from its socket transforms.
    FVector GunMuzzle = FVector(0, 46, 2);
    FVector GunForward = FVector::RightVector;
    FVector GunGrip = FVector(0, -20, -3);
    FVector GunSupportGrip = FVector(-22, 0, -8);
    FVector GunSight = FVector(0, 0, 12);
    bool bRiggedGun = false;
    // The rig on the skeletal pair; null while the static Ballista shows. DefaultGunRig is the transient
    // copy of the DA's loose RiggedGun fields (null without RiggedGun).
    UPROPERTY() TObjectPtr<const UHoverGunRig> GunRig;
    UPROPERTY() TObjectPtr<UHoverGunRig> DefaultGunRig;
    bool bStaticGunReady = false;
    // Bolt locked back (last round fired, or equipped empty): PlayGunIdle loops the rig's IdleEmpty.
    bool bGunEmpty = false;
    float GunClipRate = 1.f, GunClipStartTime = 0.f;
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentGunClip;
    FTimerHandle GunClipTimer;
    FTimerHandle GunReloadEjectTimer;
    // The Ballista meshes and optic, built once on first use; a rigged start never builds them.
    void SetupStaticGun();
    // Ejection transform read live: the rig's eject socket when rigged and present, else the Ballista's
    // breech (its grip offset) as before.
    FTransform GunEjectTransform() const;
    // Per-round brass per the rig's bEjectsPerShot/EjectDelay; the static Ballista ejects at once.
    void EjectShellForShot(class AHoverCyberRifle *Rifle);
    // One casing now at GunEjectTransform, thrown along the rig's EjectDirection (vendor direction for the Ballista).
    void EjectGunShell(class AHoverCyberRifle *Rifle) const;
    // Muzzle light onto the active gun's muzzle socket (or GunMuzzle offset) at world scale 1.
    void AttachMuzzleLight();
    void SetGunEmpty(bool bEmpty);
    void ScheduleGunEject(class AHoverCyberRifle *Rifle, float Delay, int32 Count, FTimerHandle *Handle = nullptr);
    // Revolver empties (bEjectsPerShot false, EjectDelay > 0): Spent casings EjectDelay into the Reload
    // clip, rate-scaled to Duration like PlayGunReload. Cleared by StopGunClip and every rig swap.
    void ScheduleReloadEject(class AHoverCyberRifle *Rifle, float Duration, int32 Spent);
    void AdvanceGunCylinder();
    // Single-node playback on both skeletal gun components; DurationOrZero > 0 sets the rate so the
    // clip fits that time. One-shot clips hand back to PlayGunIdle when they end.
    void PlayGunClip(UAnimSequence *Clip, float DurationOrZero, bool bLoop = false);
    void PlayGunIdle();
    // Muzzle attach point for flash, light and sound: the rig's muzzle socket when rigged, else GunMuzzle.
    FName MuzzleAttachSocket() const;
    FVector MuzzleAttachOffset() const;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> Parts;
    UPROPERTY() TObjectPtr<AActor> BoardActor;
    UPROPERTY() TObjectPtr<UPoseableMeshComponent> Board;
    UPROPERTY() TObjectPtr<UBoxComponent> BoardBody;
    UPROPERTY() TArray<TObjectPtr<UNiagaraComponent>> Boosters;
    UPROPERTY() TArray<TObjectPtr<UNiagaraComponent>> DirectionalBoosters;
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentAnimation;
    TMap<FName, FTransform> BoardRest;
    FVector StartLocation, ParkedLocation;
    float WeaponAimAlpha = 0;
    float GunRecoil = 0, GunRecoilVelocity = 0;
    float RecoilPitchDebt = 0, RecoilTrackedPitch = 0, LastRecoilTime = -10;
    float LastHitMarkTime = -10, LastKillStingTime = -10, KillFlashTime = -10;
    bool bLastHitHeadshot = false, bLastHitKill = false;
    float ShakeSetting = 1, RecoilSetting = 1;
    UPROPERTY() TObjectPtr<UPointLightComponent> MuzzleLight;
    FTimerHandle MuzzleLightTimer;
    // Keeps code-built force-feedback effects referenced for the session.
    UPROPERTY() TMap<FName, TObjectPtr<UForceFeedbackEffect>> RumbleCache;
    void ApplyViewRecoil(float PitchKick, float YawKick);
    void UpdateViewRecoil(float DeltaSeconds);
    void PlayFireShake(const FHoverGunFeelTier &Tier, const UZE_WeaponDefinition *Definition);
    bool PlayRumble(FName Key, const FHoverRumbleCurve &Curve, bool bIgnoreTimeDilation, FName Tag = TEXT("Fire"));
    void SpawnSurfaceImpact(const FHitResult &Hit, AZE_WeaponBase *SourceWeapon,
                            const UZE_WeaponDefinition *Definition);
    void EnsureMuzzleLight();
    const FHoverGunFeelTier &GetActiveFeelTier() const;
    FDelegateHandle WeaponPoseHandle;
    FDelegateHandle ViewPoseHandle;
    FTransform ViewReferenceHand;
    bool bViewReferenceReady = false;
    // hand_r's component-space rotation in the settled stance aim pose (see GunHandKick). Re-read on every quiet
    // frame (aim layer up for AimLayerUpTime > .5 s, no shot within the additive's length, no reload), frozen the
    // moment a shot lands so only the additive's deviation reaches the gun, dropped when the aim layer goes down
    // or the stance pose changes. The aim loop's own slow sway therefore never accumulates into the gun.
    FQuat GunHandRestRotation = FQuat::Identity;
    UPROPERTY() TObjectPtr<UAnimSequence> GunHandRestStance;
    float AimLayerUpTime = 0.f, LastShotWorldTime = -10.f;
    int32 GunHandShotSerial = 0;
    float CameraPostureHeight = 0;
    FVector MountFrom, MountTo, MountFeet[2];
    FRotator StartRotation;
    float ForwardInput = 0, SideInput = 0, BankInput = 0, TurnInput = 0, PitchInput = 0;
    bool bLifeEngine = false, bLifeEngineActive = false;
    // The parkour template (BP_Vexa_CLS_Parkour) owns vaults, wall runs and slides through the character movement;
    // while it drives a mode change or a root-motion montage the solver steps aside and resumes on the ground.
    bool bLifeEngineTemplateOverride = false;
    // AFS 2026-10-31 (Life Engine x parkour): edge detector for the template's wall-run flag (HOVER_PARKOUR_WALLRUN)
    // and the GravityScale it had when the solver last took over (a change means its wall run began).
    bool bTemplateWallRunWas = false;
    float TemplateWallRunGroundTime = 0.f; // AFS 2026-10-31: stuck-flag guard, see UpdateLifeEngine
    float LifeEngineGravityScale = 1.f;
    // Visual pass 2026-10-31: the survival fill light (SetupFillLight from BeginPlay, NYC Survival only).
    UPROPERTY() TObjectPtr<UPointLightComponent> FillLight;
    bool bFillLightOn = false;
    void SetupFillLight();
    void UpdateLifeEngine(float DT);
    UFUNCTION() void OnLifeEngineLanded();
    float FlightPitch = 0, FlightPitchVelocity = 0, HopStartZ = 0, HopTilt = 0;
    float GroundDirection = 0, GroundYawRate = 0;
    float BodyYaw = 0;
    float HoldTime = 0, TransitionTime = 0, HopTime = 0, SlideTime = 0;
    float GroundSlideTime = 0, GroundSlideSpeed = 0;
    FVector PostureTravel = FVector::ForwardVector;
    bool bMovingAtPosturePress = false, bDiving = false;
    bool bGroundCrouchHeld = false, bCrouchedAtPress = false, bProne = false;
    float GroundCrouchHold = 0;
    float GroundContactTime = 0;
    float ProneLandingTime = 0;
    float TargetAltitude = 0, FireCooldown = 0, AimExitTime = 0, StatusTime = 0;
    FVector FlightEffectAcceleration = FVector::ZeroVector;
    float JetDemands[8] = {};
    float LockAlpha = 0, LockVelocity = 0, BoardPitch = 0, BoardBank = 0;
    float PitchVelocity = 0, BankVelocity = 0, WingSweep = 0, WingVelocity = 0, RiderLean = 0, LeanVelocity = 0;
    float BoostCharge = 1, BoostRechargeDelay = 0, GunRaisedTime = 0;
    bool bBoostHeld = false, bBoostExhausted = false;
    bool bSprinting = false;
    float SprintEndTime = -10.f;
    bool bGliderGrounded = false;
    float PreviousFlightVerticalSpeed = 0;
    float BoosterSize = 1.f, BoosterSpawnRate = 100.f;
    float LastLandingPulse = -10.f;
    float LastHitReaction = -10.f;
    bool bKnockedDown = false;
    float KnockdownUntil = 0, KnockdownGraceUntil = 0;
    TWeakObjectPtr<AController> KnockdownController;
    bool bSteppingOn = false;
    bool bMounted = false, bAiming = false, bReview = false, bBoost = false;
    bool bMeleeEquipped = false, bSuppressFireUntilRelease = false;
    bool bSpearHeld = false; // AFS 2026-10-31 (spear item): the NYC spear slot is selected and she is on foot.
    bool bHoldConsumed = false, bWasJump = false, bWasView = false, bWasSlide = false;
    bool bWasReloadKey = false; // NYC Survival: X is reload only, the glider rides on Y / G
    bool bWasReset = false, bHeightHolding = false;
    FString StatusMessage;
    int32 ShotsFired = 0;
    // Pool cursors for PickFireSound, PickTailSound and PickHitConfirmSound: no entry repeats back to back.
    int32 LastFireSoundIndex = INDEX_NONE, LastTailSoundIndex = INDEX_NONE, LastHitSoundIndex = INDEX_NONE;
    int32 LastMeleeSwingSoundIndex = INDEX_NONE, LastMeleeHitSoundIndex = INDEX_NONE, LastFootstepSoundIndex = INDEX_NONE;
    // Footsteps (audio pass 2026-10-31): per-foot lift state and plant times, plus the cadence fallback clock.
    bool bFootWasUp[2] = {false, false};
    float LastFootstepTime[2] = {-10.f, -10.f}, LastAnyFootstepTime = -10.f;
    void UpdateFootsteps(float DeltaSeconds);
    void PlayFootstep(const FVector &At, float Speed);
    UPROPERTY() TObjectPtr<class UMaterialInstanceDynamic> ParkourSpeedlines;
    void UpdateInput(float DeltaSeconds);
    void UpdateGroundPosture(float DeltaSeconds);
    void UpdateFlight(float DeltaSeconds);
    void UpdateAppearance(float DeltaSeconds);
    void PlayPose(UAnimSequence *Animation, bool bLoop);
    void FireShot(float Damage = 35.f, float Spread = 0.f, float Range = 50000.f,
                  AZE_WeaponBase *SourceWeapon = nullptr);
    void SetView();
    void UpdateCameraPosture(float DeltaSeconds);
    void UpdateCameraBodyHide();
    void ApplyCameraBodyHide(bool bHide);
    float LastCameraHideLog = -10.f;
    bool HasBoardNearby() const;
    bool FindDismountLocation(FVector &Location) const;
    void UpdateGunTransform();
    void FinalizeViewPose();
    // OnBoneTransformsFinalized on each rigged gun component: applies GunCylinderApplied to CylinderBone.
    void FinalizeGunPose(USkeletalMeshComponent *Gun);
    FDelegateHandle GunPoseHandles[2];
    void ImpactPulse(const FVector &Location, const FVector &Normal, float Scale, float Rumble, float Duration,
                     UFXSystemAsset *Template = nullptr);
    UFUNCTION()
    void BoardHit(UPrimitiveComponent *HitComponent, AActor *OtherActor, UPrimitiveComponent *OtherComponent,
                  FVector NormalImpulse, const FHitResult &Hit);
};

UCLASS()
class HOVERFLIGHT_API AHoverHUD : public AHUD
{
    GENERATED_BODY()
  public:
    virtual void DrawHUD() override;
    // AFS 2026-10-31: AHUD::Canvas is protected in 5.8; UHoverPickupFeedback draws through this.
    UCanvas *GetHudCanvas() const
    {
        return Canvas;
    }
};

UCLASS()
class HOVERFLIGHT_API AHoverGameMode : public AGameModeBase, public IHoverTestLevelPolicy
{
    GENERATED_BODY()
  public:
    AHoverGameMode();
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void BeginPlay() override;
    virtual bool SpawnsTestBike() const override
    {
        return bSpawnBike;
    }
    UPROPERTY(EditDefaultsOnly, Category = "Test Level")
    bool bSpawnRangeZombies = true;
    UPROPERTY(EditDefaultsOnly, Category = "Test Level")
    bool bSpawnBike = true;
};

// Shares the current playable character and vehicles, without any combat encounters.
UCLASS()
class HOVERFLIGHT_API AHoverExplorationGameMode : public AHoverGameMode
{
    GENERATED_BODY()
  public:
    AHoverExplorationGameMode();
};
