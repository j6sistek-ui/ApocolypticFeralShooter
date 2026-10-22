#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "HoverAuthoring.generated.h"

UCLASS()
class HOVERFLIGHT_API UHoverAuthoring : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
  public:
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static FString DescribeBlueprint(UBlueprint *Blueprint);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void StartPlaytest();
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static UWorld *GetPlaytestWorld();
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor")
    static void TestKey(APlayerController *Controller, FName Key, float Value, bool bAnalog = false);
    UFUNCTION(BlueprintCallable, Category = "Hover|Editor") static void CapturePlaytest(const FString &Filename);
};
