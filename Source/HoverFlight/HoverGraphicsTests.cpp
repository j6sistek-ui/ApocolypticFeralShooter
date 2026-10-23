#include "HoverGraphicsSettings.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "HoverTestController.h"
#include "DLSSLibrary.h"
#include "StreamlineLibraryDLSSG.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/App.h"
#include "UnrealClient.h"

// Run in an actual -game window: an offscreen editor Play session cannot prove generated presentation.
class FHoverGraphicsRuntimeProbe : public IAutomationLatentCommand
{
  public:
    explicit FHoverGraphicsRuntimeProbe(FAutomationTestBase *InTest) : Test(InTest) {}
    virtual bool Update() override
    {
        const double Now = FPlatformTime::Seconds();
        if (!Settings.IsValid())
        {
            if (!Start)
                Start = Now;
            for (const auto &Context : GEngine->GetWorldContexts())
                if (Context.WorldType == EWorldType::Game && Context.World())
                    if (auto *PC = Cast<AHoverTestController>(Context.World()->GetFirstPlayerController()))
                    {
                        Settings = PC->GetGraphicsSettings();
                        if (Settings.IsValid())
                        {
                            Original = Settings->GetOptions();
                            Modes = Settings->GetFrameGenerationOptions();
                            int32 SavedMode = 0, SavedFG = 0;
                            if (GConfig->GetInt(TEXT("AFS.Graphics"), TEXT("Upscaling"), SavedMode,
                                                GGameUserSettingsIni))
                            {
                                GConfig->GetInt(TEXT("AFS.Graphics"), TEXT("FrameGeneration"), SavedFG,
                                                GGameUserSettingsIni);
                                Test->TestEqual(TEXT("Saved image mode loaded on fresh process"),
                                                int32(Original.Upscaling), SavedMode);
                                Test->TestEqual(TEXT("Saved FG loaded on fresh process"), Original.FrameGeneration,
                                                SavedFG);
                                Test->AddInfo(FString::Printf(TEXT("SAVED_PREFERENCES upscaling=%d fg=%d | %s"),
                                                              SavedMode, SavedFG, *Settings->GetRuntimeStatus()));
                            }
                            Start = Now;
                            break;
                        }
                    }
            if (!Settings.IsValid())
            {
                if (Now - Start > 120)
                {
                    Test->AddError(TEXT("No AFS game world available; launch PostApo with -game."));
                    return true;
                }
                return false;
            }
        }
        if (Now - Start < 5)
            return false;
        Start = Now;
        auto *G = Settings.Get();
        if (Step > 0)
        {
            float FPS = 0;
            int32 Presented = 0;
            UStreamlineLibraryDLSSG::GetDLSSGFrameTiming(FPS, Presented);
            Test->AddInfo(FString::Printf(TEXT("FG request=%d | %s"), CurrentMode, *G->GetRuntimeStatus()));
            if (CurrentMode >= 2 && FApp::HasFocus())
                Test->TestTrue(FString::Printf(TEXT("FG %dX produces additional presented frames"), CurrentMode),
                               Presented > 1);
            else if (CurrentMode >= 2)
                Test->AddWarning(TEXT("Game window is backgrounded: NVIDIA suspends FG. This sample cannot validate "
                                      "generated presentation."));
        }
        if (Step < Modes.Num())
        {
            CurrentMode = Modes[Step++];
            FHoverGraphicsOptions Choice;
            Choice.Upscaling = EHoverUpscaling::Quality;
            Choice.FrameGeneration = CurrentMode;
            Test->TestTrue(TEXT("Supported graphics selection accepted"), G->Apply(Choice, false));
            Test->TestTrue(TEXT("DLSS actually enabled"), UDLSSLibrary::IsDLSSEnabled());
            Test->TestFalse(TEXT("Standalone bypasses PIE guard"), G->IsFrameGenerationPreviewOnly());
            FScreenshotRequest::RequestScreenshot(FString::Printf(TEXT("Graphics_FG_%d"), CurrentMode), true, false);
            return false;
        }
        FHoverGraphicsOptions Invalid;
        Invalid.Upscaling = EHoverUpscaling(255);
        Invalid.FrameGeneration = 99;
        Test->TestFalse(TEXT("Invalid stored settings rejected"), G->Apply(Invalid, false));
        Test->TestFalse(TEXT("Invalid settings fall back to native"), UDLSSLibrary::IsDLSSEnabled());
        Test->TestTrue(TEXT("Invalid settings turn FG off"),
                       UStreamlineLibraryDLSSG::GetDLSSGMode() == EStreamlineDLSSGMode::Off);
        G->Apply(Original, false);
        return true;
    }

  private:
    FAutomationTestBase *Test;
    TWeakObjectPtr<UHoverGraphicsSettings> Settings;
    FHoverGraphicsOptions Original;
    TArray<int32> Modes;
    double Start = 0;
    int32 Step = 0, CurrentMode = 0;
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHoverGraphicsRuntimeTest, "AFS.Graphics.Standalone",
                                 EAutomationTestFlags::ClientContext | EAutomationTestFlags::EngineFilter)
bool FHoverGraphicsRuntimeTest::RunTest(const FString &Parameters)
{
    ADD_LATENT_AUTOMATION_COMMAND(FHoverGraphicsRuntimeProbe(this));
    return true;
}
#endif
