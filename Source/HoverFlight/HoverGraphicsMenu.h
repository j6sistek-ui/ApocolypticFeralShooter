#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HoverGraphicsSettings.h"
#include "HoverCyberCity.h"
#include "HoverGraphicsMenu.generated.h"
class UTextBlock;

UCLASS()
class HOVERFLIGHT_API UHoverGraphicsMenu : public UUserWidget
{
    GENERATED_BODY()
  public:
    void Open(UHoverGraphicsSettings *InSettings);
    void Navigate(int32 Direction);
    void Adjust(int32 Direction);
    void ChangePage();
    void ApplyZombieSettings();
    FHoverGraphicsOptions GetSelection() const
    {
        return Pending;
    }
    int32 GetSelectedRow() const
    {
        return SelectedRow;
    }
    int32 GetSelectedLevel() const
    {
        return PendingLevel;
    }

  protected:
    virtual void NativeOnInitialized() override;

  private:
    UPROPERTY() TObjectPtr<UHoverGraphicsSettings> Settings;
    UPROPERTY() TObjectPtr<UTextBlock> ModeText;
    UPROPERTY() TObjectPtr<UTextBlock> FramesText;
    UPROPERTY() TObjectPtr<UTextBlock> NoteText;
    UPROPERTY() TObjectPtr<UTextBlock> LevelText;
    UPROPERTY() TObjectPtr<UTextBlock> HealthText;
    UPROPERTY() TObjectPtr<UTextBlock> PageText;
    UPROPERTY() TObjectPtr<UTextBlock> HelpText;
    UPROPERTY() TObjectPtr<UTextBlock> DetailText;
    UPROPERTY() TObjectPtr<UTextBlock> ImageHelpText;
    FHoverZombieTuning PendingZombies;
    bool bZombiePage = false;
    FHoverGraphicsOptions Pending;
    int32 SelectedRow = 0;
    int32 PendingLevel = 0;
    void Refresh();
};
