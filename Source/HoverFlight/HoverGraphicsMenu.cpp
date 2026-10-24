#include "HoverGraphicsMenu.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Kismet/GameplayStatics.h"

void UHoverGraphicsMenu::NativeOnInitialized()
{
    Super::NativeOnInitialized();
    auto *Root = WidgetTree->ConstructWidget<UCanvasPanel>();
    WidgetTree->RootWidget = Root;
    auto *Shade = WidgetTree->ConstructWidget<UBorder>();
    Shade->SetBrushColor(FLinearColor(0.01f, 0.015f, 0.025f, .8f));
    auto *ShadeSlot = Root->AddChildToCanvas(Shade);
    ShadeSlot->SetAnchors(FAnchors(0, 0, 1, 1));
    ShadeSlot->SetOffsets(FMargin(0));
    auto *Panel = WidgetTree->ConstructWidget<UBorder>();
    Panel->SetBrushColor(FLinearColor(.035f, .05f, .075f, 1));
    Panel->SetPadding(FMargin(32));
    auto *PanelSlot = Root->AddChildToCanvas(Panel);
    PanelSlot->SetAnchors(FAnchors(.5f, .5f));
    PanelSlot->SetAlignment(FVector2D(.5f, .5f));
    PanelSlot->SetAutoSize(true);
    auto *Size = WidgetTree->ConstructWidget<USizeBox>();
    Size->SetWidthOverride(660);
    Panel->SetContent(Size);
    auto *Rows = WidgetTree->ConstructWidget<UVerticalBox>();
    Size->SetContent(Rows);
    auto AddText = [this, Rows](const FString &Text, int32 FontSize, const FLinearColor &Color) {
        auto *Label = WidgetTree->ConstructWidget<UTextBlock>();
        Label->SetText(FText::FromString(Text));
        auto Font = Label->GetFont();
        Font.Size = FontSize;
        Label->SetFont(Font);
        Label->SetColorAndOpacity(FSlateColor(Color));
        Label->SetAutoWrapText(true);
        Rows->AddChildToVerticalBox(Label)->SetPadding(FMargin(0, 8));
        return Label;
    };
    AddText(TEXT("TEST SETTINGS"), 30, FLinearColor::White);
    AddText(TEXT("Game paused. Adjust graphics, health or the test environment."), 16, FLinearColor(.7f, .76f, .84f));
    ModeText = AddText(TEXT(""), 23, FLinearColor::White);
    FramesText = AddText(TEXT(""), 23, FLinearColor::White);
    LevelText = AddText(TEXT(""), 23, FLinearColor::White);
    HealthText = AddText(TEXT(""), 23, FLinearColor::White);
    AddText(TEXT("Invincible off: take damage. At zero health, reset at the start after 3 seconds."), 16,
            FLinearColor(.7f, .76f, .84f));
    AddText(TEXT("Changing level starts a fresh test with Vexa and all three vehicles. Lakeside uses its own five "
                 "creatures."),
            16, FLinearColor(.7f, .76f, .84f));
    AddText(TEXT("DLAA keeps full resolution. DLSS Quality is a good starting point for more speed."), 16,
            FLinearColor(.7f, .76f, .84f));
    NoteText = AddText(TEXT(""), 16, FLinearColor(.9f, .78f, .5f));
    AddText(TEXT("D-pad / arrows: choose and adjust\nA / Enter: apply and resume    B / F6: cancel"), 17,
            FLinearColor(.7f, .85f, 1));
    SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UHoverGraphicsMenu::Open(UHoverGraphicsSettings *InSettings)
{
    Settings = InSettings;
    Pending = Settings->GetOptions();
    const FString Map = UGameplayStatics::GetCurrentLevelName(this);
    PendingLevel = Map.Contains(TEXT("L_Showcase")) || Map.Contains(TEXT("L_Lakeside")) ? 2
                   : Map.Contains(TEXT("Cyber"))                                        ? 1
                                                                                        : 0;
    SelectedRow = 0;
    Refresh();
}

void UHoverGraphicsMenu::Navigate(int32 Direction)
{
    SelectedRow = (SelectedRow + Direction + 4) % 4;
    Refresh();
}

void UHoverGraphicsMenu::Adjust(int32 Direction)
{
    if (SelectedRow == 0)
    {
        const auto Options = Settings->GetUpscalingOptions();
        const int32 Index = FMath::Max(0, Options.Find(Pending.Upscaling));
        Pending.Upscaling = Options[(Index + Direction + Options.Num()) % Options.Num()];
    }
    else if (SelectedRow == 1)
    {
        const auto Options = Settings->GetFrameGenerationOptions();
        const int32 Index = FMath::Max(0, Options.Find(Pending.FrameGeneration));
        Pending.FrameGeneration = Options[(Index + Direction + Options.Num()) % Options.Num()];
    }
    else if (SelectedRow == 2)
        PendingLevel = (PendingLevel + Direction + 3) % 3;
    else
        Pending.bInvincible = !Pending.bInvincible;
    Refresh();
}

void UHoverGraphicsMenu::Refresh()
{
    ModeText->SetText(
        FText::FromString(FString::Printf(TEXT("%s Image:  < %s >"), SelectedRow == 0 ? TEXT(">") : TEXT("  "),
                                          *UHoverGraphicsSettings::UpscalingName(Pending.Upscaling))));
    FramesText->SetText(FText::FromString(
        FString::Printf(TEXT("%s Frame generation:  < %s >"), SelectedRow == 1 ? TEXT(">") : TEXT("  "),
                        *UHoverGraphicsSettings::FrameGenerationName(Pending.FrameGeneration))));
    ModeText->SetColorAndOpacity(FSlateColor(SelectedRow == 0 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
    FramesText->SetColorAndOpacity(FSlateColor(SelectedRow == 1 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
    LevelText->SetText(
        FText::FromString(FString::Printf(TEXT("%s Test level:  < %s >"), SelectedRow == 2 ? TEXT(">") : TEXT("  "),
                                          PendingLevel == 2   ? TEXT("Chinese Lakeside Town")
                                          : PendingLevel == 1 ? TEXT("Cyber City")
                                                              : TEXT("Post-apocalypse"))));
    LevelText->SetColorAndOpacity(FSlateColor(SelectedRow == 2 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
    NoteText->SetText(FText::FromString(Settings->GetAvailabilityNote()));
    HealthText->SetText(
        FText::FromString(FString::Printf(TEXT("%s Invincible:  < %s >"), SelectedRow == 3 ? TEXT(">") : TEXT("  "),
                                          Pending.bInvincible ? TEXT("On") : TEXT("Off"))));
    HealthText->SetColorAndOpacity(FSlateColor(SelectedRow == 3 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
}
