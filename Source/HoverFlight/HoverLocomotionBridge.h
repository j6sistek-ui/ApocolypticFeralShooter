#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Animation/AnimInstance.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "GameplayTagContainer.h"
#include "HoverLocomotionBridge.generated.h"

// CLS supplies poses while the existing Parkour pawn owns movement and special actions.
UCLASS()
class HOVERFLIGHT_API UHoverLocomotionBridge : public UActorComponent
{
    GENERATED_BODY()
  public:
    UHoverLocomotionBridge();
    virtual void BeginPlay() override;
    virtual void TickComponent(float DT, ELevelTick Type, FActorComponentTickFunction *Function) override;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<USkeletalMeshComponent> Driver;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<UActorComponent> Locomotion;
    UPROPERTY(BlueprintReadOnly) bool bReady = false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bEnabled = true;
    UPROPERTY(BlueprintReadOnly) bool bRifleStance = false;
    // LoopCount: the spear's stance loop passes a large count (AFS 2026-10-31 spear item); 1 everywhere else.
    UFUNCTION(BlueprintCallable)
    bool PlayAction(UAnimSequence *Sequence, float Duration = 0.f, bool UpperBody = true, int32 LoopCount = 1);
    UFUNCTION(BlueprintCallable) void CancelAction();
    // AFS 2026-10-31 (spear item): the heavy thrust holds its wind-up (rate 0) and resumes on release.
    UFUNCTION(BlueprintCallable) bool SetActionPlayRate(float Rate);
    UFUNCTION(BlueprintPure) class UAnimMontage *GetAction() const
    {
        return Action;
    }
    // Pure so the headless verify can assert no driver montage runs through a rigged burst (design A1).
    UFUNCTION(BlueprintPure) bool IsActionPlaying() const;

  private:
    UPROPERTY() TObjectPtr<class UAnimMontage> Action;
    UPROPERTY() TObjectPtr<class UAnimMontage> Posture;
    int32 PostureMode = 0;
    bool bWasWallJumpLocked = false;
    bool bHasRifleProfile = false;
    bool bWasCrouched = false;
};

// The Blueprint owns the actual Spring Controller graph. This class only gates
// its strength during quiet hovering and exposes measured runtime offsets.
UCLASS()
class HOVERFLIGHT_API UHoverBodyPhysics : public UAnimInstance
{
    GENERATED_BODY()
  public:
    virtual void NativeUpdateAnimation(float DT) override;
    virtual void NativePostEvaluateAnimation() override;
    UFUNCTION(BlueprintCallable) void MeasureRenderedOffsets();
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool bPhysicsEnabled = true;
    UPROPERTY(BlueprintReadOnly) float PhysicsAlpha = 1;
    UPROPERTY(BlueprintReadOnly) TArray<FName> EvaluatedBones;
    UPROPERTY(BlueprintReadOnly) TArray<FVector> MeasuredOffsets;
    UPROPERTY(BlueprintReadOnly) TArray<float> MeasuredAlphas;

  private:
    float AirborneBlend = 0;
};

UCLASS()
class HOVERFLIGHT_API UHoverIntegrationAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
  public:
    UFUNCTION(BlueprintCallable) static bool ConfigureHybrid(UBlueprint *Pilot, UBlueprint *DataComponent);
    UFUNCTION(BlueprintCallable) static bool BuildActionLayer(class UAnimBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable)
    static bool BuildBodyPhysics(class UAnimBlueprint *Blueprint, class UAnimBlueprint *Original);
    UFUNCTION(BlueprintCallable) static bool ConfigureMovementTags(UBlueprint *Blueprint);
    UFUNCTION(BlueprintPure) static FGameplayTagContainer GetCLSTags(AActor *Owner);
    UFUNCTION(BlueprintPure) static UActorComponent *GetCLSData(AActor *Owner);
    UFUNCTION(BlueprintPure) static USkeletalMeshComponent *GetCLSDriver(AActor *Owner);
    // AFS 2026-11-01 (Scripts/ProveWalking.py): one JSON row of the walk state for a per-frame receipt: character
    // movement mode / ground / crouch / acceleration, Life Engine active / grounded / hand-off flag, capsule and mesh
    // height, floor distance and surface under the capsule, physics volume, foot and pelvis heights over the floor,
    // and the CLS AnimData fields as packaged this frame. Read-only.
    UFUNCTION(BlueprintCallable) static FString DescribeWalkState(AActor *Owner);
};
