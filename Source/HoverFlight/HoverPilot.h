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
};

UCLASS()
class HOVERFLIGHT_API AHoverPilot : public ACharacter
{
    GENERATED_BODY()
  public:
    AHoverPilot();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
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
    float HoldProgress() const
    {
        return HoldTime / .65f;
    }
    FString GetPrompt() const;
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
    UPROPERTY() TObjectPtr<UAnimSequence> CurrentAnimation;
    TMap<FName, FTransform> BoardRest;
    FVector StartLocation, ParkedLocation;
    FVector MountFrom, MountTo, MountFeet[2];
    FRotator StartRotation;
    float ForwardInput = 0, SideInput = 0, UpInput = 0, TurnInput = 0;
    float HoldTime = 0, TransitionTime = 0, HopTime = 0, SlideTime = 0;
    float TargetAltitude = 0, FireCooldown = 0, AimExitTime = 0;
    float LockAlpha = 0, LockVelocity = 0, BoardPitch = 0, BoardBank = 0;
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
