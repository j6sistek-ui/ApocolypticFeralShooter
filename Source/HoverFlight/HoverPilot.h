#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "HoverPilot.generated.h"

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
    UPROPERTY() TObjectPtr<class UHoverLocomotionBridge> LocomotionBridge;
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
        bInvincible = Enabled;
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
    bool UsesAimFacing() const
    {
        return bMeleeEquipped || bAiming || GunRaisedTime > 0 || !bReview;
    }
    bool bInvincible = true;
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
    UPROPERTY(VisibleAnywhere) TObjectPtr<USkeletalMeshComponent> ViewArms;

  private:
    friend class AHoverCyberRifle;
    UPROPERTY() TObjectPtr<UHoverPilotAssets> Assets;
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
    FDelegateHandle WeaponPoseHandle;
    FDelegateHandle ViewPoseHandle;
    FTransform ViewReferenceHand;
    bool bViewReferenceReady = false;
    float CameraPostureHeight = 0;
    FVector MountFrom, MountTo, MountFeet[2];
    FRotator StartRotation;
    float ForwardInput = 0, SideInput = 0, BankInput = 0, TurnInput = 0, PitchInput = 0;
    float FlightPitch = 0, FlightPitchVelocity = 0, HopStartZ = 0, HopTilt = 0;
    float GroundDirection = 0, GroundYawRate = 0;
    float BodyYaw = 0;
    float HoldTime = 0, TransitionTime = 0, HopTime = 0, SlideTime = 0;
    float GroundSlideTime = 0, GroundSlideSpeed = 0;
    FVector PostureTravel = FVector::ForwardVector;
    bool bMovingAtPosturePress = false, bDiving = false;
    bool bGroundCrouchHeld = false, bCrouchedAtPress = false, bProne = false;
    float GroundCrouchHold = 0;
    float TargetAltitude = 0, FireCooldown = 0, AimExitTime = 0, StatusTime = 0;
    FVector FlightEffectAcceleration = FVector::ZeroVector;
    float JetDemands[8] = {};
    float LockAlpha = 0, LockVelocity = 0, BoardPitch = 0, BoardBank = 0;
    float PitchVelocity = 0, BankVelocity = 0, WingSweep = 0, WingVelocity = 0, RiderLean = 0, LeanVelocity = 0;
    float BoostCharge = 1, BoostRechargeDelay = 0, GunRaisedTime = 0;
    bool bBoostHeld = false, bBoostExhausted = false;
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
    bool bHoldConsumed = false, bWasJump = false, bWasView = false, bWasSlide = false;
    bool bWasReset = false, bHeightHolding = false;
    FString StatusMessage;
    int32 ShotsFired = 0;
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
    bool HasBoardNearby() const;
    bool FindDismountLocation(FVector &Location) const;
    void UpdateGunTransform();
    void FinalizeViewPose();
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
};

UCLASS()
class HOVERFLIGHT_API AHoverGameMode : public AGameModeBase
{
    GENERATED_BODY()
  public:
    AHoverGameMode();
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
    virtual void BeginPlay() override;
};
