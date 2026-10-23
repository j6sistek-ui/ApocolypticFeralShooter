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
    UFUNCTION(BlueprintCallable)
    static bool BuildBodyPhysics(class UAnimBlueprint *Blueprint, class UAnimBlueprint *Original);
    UFUNCTION(BlueprintCallable) static bool ConfigureMovementTags(UBlueprint *Blueprint);
    UFUNCTION(BlueprintPure) static FGameplayTagContainer GetCLSTags(AActor *Owner);
    UFUNCTION(BlueprintPure) static UActorComponent *GetCLSData(AActor *Owner);
    UFUNCTION(BlueprintPure) static USkeletalMeshComponent *GetCLSDriver(AActor *Owner);
};
