#pragma once
#include "CoreMinimal.h"
#include "HoverPilot.h"
#include "HoverTestController.h"
#include "Animation/AnimInstance.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ClsComparison.generated.h"

UCLASS()
class HOVERFLIGHT_API UClsRetargetAnim : public UAnimInstance
{
    GENERATED_BODY()
  protected:
    virtual FAnimInstanceProxy *CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy *Proxy) override;
};

// Native base for a local duplicate of the supplied CLS character Blueprint.
// Its movement component, motion matching graph and input events remain vendor code.
UCLASS()
class HOVERFLIGHT_API AClsComparisonCharacter : public ACharacter
{
    GENERATED_BODY()
  public:
    virtual void BeginPlay() override;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<USkeletalMeshComponent> Vexa;
    UPROPERTY() TArray<TObjectPtr<USkeletalMeshComponent>> Parts;
};

UCLASS()
class HOVERFLIGHT_API AClsComparisonController : public AHoverTestController
{
    GENERATED_BODY()
  public:
    virtual void PlayerTick(float DT) override;
    virtual bool InputKey(const FInputKeyEventArgs &Params) override;
    UFUNCTION(Exec, BlueprintCallable) void CompareLocomotion();
    UFUNCTION(BlueprintPure) bool IsCLSMode() const;

  private:
    UPROPERTY() TObjectPtr<AHoverPilot> Before;
    UPROPERTY() TObjectPtr<AClsComparisonCharacter> After;
    UPROPERTY() TObjectPtr<class UInputMappingContext> ComparisonMappings;
    void SetCLSMappings(bool Enabled);
};

UCLASS()
class HOVERFLIGHT_API AClsComparisonHUD : public AHoverHUD
{
    GENERATED_BODY()
  public:
    virtual void DrawHUD() override;
};

UCLASS()
class HOVERFLIGHT_API AClsComparisonGameMode : public AHoverGameMode
{
    GENERATED_BODY()
  public:
    AClsComparisonGameMode();
    virtual void InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage) override;
};

UCLASS()
class HOVERFLIGHT_API UClsComparisonAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
  public:
    UFUNCTION(BlueprintCallable) static bool ConfigureCharacter(UBlueprint *Blueprint, UObject *Profile);
    UFUNCTION(BlueprintCallable) static FString MotionMatchingResult(ACharacter *Character);
    UFUNCTION(BlueprintCallable) static bool BuildMappings(class UInputMappingContext *Mappings);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool SetLocalAnimationProperty(UObject *Asset, FName PropertyName, const FString &Value);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static bool BuildLocalPoseDatabase(class UPoseSearchDatabase *Database, const TArray<class UAnimSequence *> &Clips);
};
