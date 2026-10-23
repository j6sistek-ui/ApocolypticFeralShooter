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

USTRUCT(BlueprintType)
struct FHoverBodyPart
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere) FName Name;
    UPROPERTY(EditAnywhere) TObjectPtr<USkeletalMesh> Mesh;
    UPROPERTY(EditAnywhere) TArray<TObjectPtr<UMaterialInterface>> Materials;
};

UCLASS(BlueprintType)
class HOVERFLIGHT_API UHoverPilotAssets : public UDataAsset
{
    GENERATED_BODY()
  public:
    UPROPERTY(EditAnywhere) TArray<FHoverBodyPart> BodyParts;
    UPROPERTY(EditAnywhere) TObjectPtr<USkeletalMesh> Glider;
    UPROPERTY(EditAnywhere) TObjectPtr<UStaticMesh> Gun;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideIdle;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideMove;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideLeft;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideRight;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RideDown;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> AimStart;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> AimEnd;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Fire;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> RifleAim;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Walk;
    UPROPERTY(EditAnywhere) TObjectPtr<UAnimSequence> Stand;
    UPROPERTY(EditAnywhere) TObjectPtr<UNiagaraSystem> BoosterEffect;
    UPROPERTY(EditAnywhere) TObjectPtr<UFXSystemAsset> ShockwaveEffect;
    UPROPERTY(EditAnywhere) TObjectPtr<UFXSystemAsset> MuzzleEffect;
};

UCLASS()
class HOVERFLIGHT_API AHoverPilot : public ACharacter
{
    GENERATED_BODY()
  public:
    AHoverPilot(const FObjectInitializer &ObjectInitializer);
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void Landed(const FHitResult &Hit) override;
    virtual void SetupPlayerInputComponent(UInputComponent *Input) override;
    UFUNCTION(Exec) void HoverMount();
    UFUNCTION(Exec) void HoverView();
    UFUNCTION(Exec) void HoverReset();
    UFUNCTION(Exec) void HoverStatus();
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
    UFUNCTION(BlueprintPure) float HoldProgress() const
    {
        return HoldTime / .65f;
    }
    UFUNCTION(BlueprintPure) FString GetPrompt() const;
    float GetSpeedMps() const
    {
        return GetVelocity().Size() / 100.f;
    }
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<USpringArmComponent> ReviewArm;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UCameraComponent> ReviewCamera;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> ViewGun;
    UPROPERTY(VisibleAnywhere) TObjectPtr<UStaticMeshComponent> WorldGun;

  private:
    UPROPERTY() TObjectPtr<UHoverPilotAssets> Assets;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> Parts;
    UPROPERTY() TObjectPtr<AActor> BoardActor;
    UPROPERTY() TObjectPtr<UPoseableMeshComponent> Board;
    UPROPERTY() TObjectPtr<UBoxComponent> BoardBody;
    UPROPERTY() TArray<TObjectPtr<UNiagaraComponent>> Boosters;
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentAnimation;
    TMap<FName, FTransform> BoardRest;
    FVector StartLocation, ParkedLocation;
    FVector MountFrom, MountTo, MountFeet[2];
    FRotator StartRotation;
    float ForwardInput = 0, SideInput = 0, BankInput = 0, TurnInput = 0;
    float HoldTime = 0, TransitionTime = 0, HopTime = 0, SlideTime = 0;
    float TargetAltitude = 0, FireCooldown = 0, AimExitTime = 0, StatusTime = 0;
    float LockAlpha = 0, LockVelocity = 0, BoardPitch = 0, BoardBank = 0;
    float PitchVelocity = 0, BankVelocity = 0, WingSweep = 0, WingVelocity = 0, RiderLean = 0, LeanVelocity = 0;
    float BoostCharge = 1, BoostRechargeDelay = 0, GunRaisedTime = 0;
    bool bBoostHeld = false, bBoostExhausted = false;
    bool bGliderGrounded = false;
    float PreviousFlightVerticalSpeed = 0;
    float BoosterSize = 1.f, BoosterSpawnRate = 100.f;
    float LastLandingPulse = -10.f;
    bool bSteppingOn = false;
    bool bMounted = false, bAiming = false, bReview = false, bBoost = false;
    bool bHoldConsumed = false, bWasJump = false, bWasView = false, bWasSlide = false;
    bool bWasReset = false, bHeightHolding = false;
    FString StatusMessage;
    int32 ShotsFired = 0;
    void UpdateInput(float DeltaSeconds);
    void UpdateFlight(float DeltaSeconds);
    void UpdateAppearance(float DeltaSeconds);
    void PlayPose(UAnimSequence *Animation, bool bLoop);
    void FireShot();
    void SetView();
    bool HasBoardNearby() const;
    bool FindDismountLocation(FVector &Location) const;
    void UpdateGunTransform();
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
    virtual void BeginPlay() override;
};
