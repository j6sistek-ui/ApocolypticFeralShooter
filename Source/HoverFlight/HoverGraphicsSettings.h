#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "HoverGraphicsSettings.generated.h"

UENUM(BlueprintType)
enum class EHoverUpscaling : uint8
{
    Native,
    DLAA,
    Quality,
    Balanced,
    Performance,
    UltraPerformance
};

USTRUCT(BlueprintType)
struct FHoverGraphicsOptions
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite) EHoverUpscaling Upscaling = EHoverUpscaling::Native;
    // 0 = off, 1 = dynamic, 2..6 = total presented frames per rendered frame.
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 FrameGeneration = 0;
};

UCLASS()
class HOVERFLIGHT_API UHoverGraphicsSettings : public UObject
{
    GENERATED_BODY()
  public:
    void Initialize(UWorld *World);
    void RestoreRenderer();
    UFUNCTION(BlueprintCallable) bool Apply(FHoverGraphicsOptions Options, bool bSave = true);
    UFUNCTION(BlueprintPure) FHoverGraphicsOptions GetOptions() const
    {
        return Current;
    }
    UFUNCTION(BlueprintPure) TArray<EHoverUpscaling> GetUpscalingOptions() const;
    UFUNCTION(BlueprintPure) TArray<int32> GetFrameGenerationOptions() const;
    UFUNCTION(BlueprintPure) FString GetRuntimeStatus() const;
    UFUNCTION(BlueprintPure) bool IsFrameGenerationPreviewOnly() const;
    FString GetAvailabilityNote() const;
    static FString UpscalingName(EHoverUpscaling Mode);
    static FString FrameGenerationName(int32 Mode);

  private:
    UPROPERTY() TObjectPtr<UWorld> PlayWorld;
    FHoverGraphicsOptions Current;
    TMap<FString, float> RendererBeforePlay;
    bool bDLSSBeforePlay = false;
    uint8 FrameGenerationBeforePlay = 0, ReflexBeforePlay = 0;
    bool bInitialized = false;
};
