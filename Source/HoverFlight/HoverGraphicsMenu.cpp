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
    PageText = AddText(TEXT("TEST SETTINGS"), 30, FLinearColor::White);
    HelpText = AddText(TEXT(""), 16, FLinearColor(.7f, .76f, .84f));
    ModeText = AddText(TEXT(""), 23, FLinearColor::White);
    FramesText = AddText(TEXT(""), 23, FLinearColor::White);
    LevelText = AddText(TEXT(""), 23, FLinearColor::White);
    HealthText = AddText(TEXT(""), 23, FLinearColor::White);
    DetailText = AddText(TEXT("Invincible off: take damage. At zero health, reset at the start after 3 seconds."), 16,
                         FLinearColor(.7f, .76f, .84f));
    AddText(TEXT("NYC: explore with Vexa, hoverboard and truck, without zombies. Other levels keep their "
                 "vehicles and encounters. Lakeside uses its own five creatures."),
            16, FLinearColor(.7f, .76f, .84f));
    ImageHelpText = AddText(TEXT("DLAA keeps full resolution. DLSS Quality is a good starting point for more speed."),
                            16, FLinearColor(.7f, .76f, .84f));
    NoteText = AddText(TEXT(""), 16, FLinearColor(.9f, .78f, .5f));
    AddText(
        TEXT("L1 / R1 / Tab: settings page    D-pad / arrows: adjust\nA / Enter: apply and resume    B / F6: cancel"),
        17, FLinearColor(.7f, .85f, 1));
    SetVisibility(ESlateVisibility::HitTestInvisible);
}

void UHoverGraphicsMenu::Open(UHoverGraphicsSettings *InSettings)
{
    Settings = InSettings;
    Pending = Settings->GetOptions();
    const FString Map = UGameplayStatics::GetCurrentLevelName(this);
    PendingLevel = Map.Contains(TEXT("L_NYC_Explore"))                                    ? 3
                   : Map.Contains(TEXT("L_Showcase")) || Map.Contains(TEXT("L_Lakeside")) ? 2
                   : Map.Contains(TEXT("Cyber"))                                          ? 1
                                                                                          : 0;
    SelectedRow = 0;
    bZombiePage = false;
    if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        PendingZombies = Mode->Tuning;
    Refresh();
}

void UHoverGraphicsMenu::ChangePage()
{
    if (GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        bZombiePage = !bZombiePage;
    SelectedRow = 0;
    Refresh();
}

void UHoverGraphicsMenu::ApplyZombieSettings()
{
    if (auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        Mode->ApplyTuning(PendingZombies);
}

void UHoverGraphicsMenu::Navigate(int32 Direction)
{
    SelectedRow = (SelectedRow + Direction + 4) % 4;
    Refresh();
}

void UHoverGraphicsMenu::Adjust(int32 Direction)
{
    if (bZombiePage)
    {
        float *Values[] = {&PendingZombies.Health, &PendingZombies.Speed, &PendingZombies.Count,
                           &PendingZombies.SpawnInterval};
        *Values[SelectedRow] =
            FMath::Clamp(*Values[SelectedRow] + Direction * .25f, .25f, SelectedRow == 1 ? 2.f : 3.f);
    }
    else if (SelectedRow == 0)
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
        PendingLevel = (PendingLevel + Direction + 4) % 4;
    else
        Pending.bInvincible = !Pending.bInvincible;
    Refresh();
}

void UHoverGraphicsMenu::Refresh()
{
    PageText->SetText(FText::FromString(bZombiePage ? TEXT("ZOMBIE SETTINGS") : TEXT("TEST SETTINGS")));
    HelpText->SetText(FText::FromString(GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>()
                                            ? TEXT("L1 / R1 switches between test and zombie settings.")
                                            : TEXT("Zombie wave settings are available in Cyber City and Lakeside.")));
    if (bZombiePage)
    {
        UTextBlock *Labels[] = {ModeText, FramesText, LevelText, HealthText};
        const TCHAR *Names[] = {TEXT("Zombie health"), TEXT("Zombie speed"), TEXT("Wave size"), TEXT("Spawn interval")};
        const float Values[] = {PendingZombies.Health, PendingZombies.Speed, PendingZombies.Count,
                                PendingZombies.SpawnInterval};
        for (int32 I = 0; I < 4; ++I)
        {
            Labels[I]->SetText(FText::FromString(FString::Printf(
                TEXT("%s %s:  < %.2fx >"), SelectedRow == I ? TEXT(">") : TEXT("  "), Names[I], Values[I])));
            Labels[I]->SetColorAndOpacity(
                FSlateColor(SelectedRow == I ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
        }
        DetailText->SetText(FText::FromString(TEXT("Health/speed apply to living enemies. Wave size changes next "
                                                   "round. Higher spawn interval means slower spawning.")));
        ImageHelpText->SetText(FText::FromString(
            TEXT("Editor weapon/wave tools: Window > ZESP Control Panel during Play. Shift+F1 releases the mouse. "
                 "Vexa movement and camera settings use this sandbox's controls.")));
        NoteText->SetText(FText::FromString(
            TEXT("Session-only adjustments. Apply resumes play; Cancel discards changes. New levels start at 1x.")));
        return;
    }
    DetailText->SetText(
        FText::FromString(TEXT("Invincible off: take damage. At zero health, reset at the start after 3 seconds.")));
    ImageHelpText->SetText(
        FText::FromString(TEXT("DLAA keeps full resolution. DLSS Quality is a good starting point for more speed.")));
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
                                          PendingLevel == 3   ? TEXT("NYC - Exploration")
                                          : PendingLevel == 2 ? TEXT("Chinese Lakeside Town")
                                          : PendingLevel == 1 ? TEXT("Cyber City")
                                                              : TEXT("Post-apocalypse"))));
    LevelText->SetColorAndOpacity(FSlateColor(SelectedRow == 2 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
    NoteText->SetText(FText::FromString(Settings->GetAvailabilityNote()));
    HealthText->SetText(
        FText::FromString(FString::Printf(TEXT("%s Invincible:  < %s >"), SelectedRow == 3 ? TEXT(">") : TEXT("  "),
                                          Pending.bInvincible ? TEXT("On") : TEXT("Off"))));
    HealthText->SetColorAndOpacity(FSlateColor(SelectedRow == 3 ? FLinearColor(.3f, .8f, 1) : FLinearColor::White));
}
