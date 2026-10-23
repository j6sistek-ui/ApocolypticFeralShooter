#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "HoverGraphicsSettings.h"
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
    FHoverGraphicsOptions Pending;
    int32 SelectedRow = 0;
    int32 PendingLevel = 0;
    void Refresh();
};
