#include "HoverGraphicsSettings.h"
#include "DLSSLibrary.h"
#include "StreamlineLibraryDLSSG.h"
#include "StreamlineLibraryReflex.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/App.h"
#include "HoverPilot.h"
#include "EngineUtils.h"

namespace
{
const TCHAR *SettingsSection = TEXT("AFS.Graphics");
const TCHAR *RendererCVars[] = {
    TEXT("r.ScreenPercentage"),         TEXT("r.AntiAliasingMethod"),
    TEXT("r.DynamicRes.OperationMode"), TEXT("r.TemporalAA.Upscaler"),
    TEXT("r.TemporalAA.Upsampling"),    TEXT("r.Editor.Viewport.OverridePIEScreenPercentage")};

void SetRendererValue(const TCHAR *Name, float Value)
{
    if (auto *CVar = IConsoleManager::Get().FindConsoleVariable(Name))
        CVar->Set(Value, EConsoleVariableFlags(CVar->GetFlags() & ECVF_SetByMask));
}

UDLSSMode DLSSMode(EHoverUpscaling Mode)
{
    switch (Mode)
    {
    case EHoverUpscaling::DLAA:
        return UDLSSMode::DLAA;
    case EHoverUpscaling::Quality:
        return UDLSSMode::Quality;
    case EHoverUpscaling::Balanced:
        return UDLSSMode::Balanced;
    case EHoverUpscaling::Performance:
        return UDLSSMode::Performance;
    case EHoverUpscaling::UltraPerformance:
        return UDLSSMode::UltraPerformance;
    default:
        return UDLSSMode::Off;
    }
}

EStreamlineDLSSGMode FGMode(int32 Mode)
{
    switch (Mode)
    {
    case 1:
        return EStreamlineDLSSGMode::OnDynamic;
    case 2:
        return EStreamlineDLSSGMode::On2X;
    case 3:
        return EStreamlineDLSSGMode::On3X;
    case 4:
        return EStreamlineDLSSGMode::On4X;
    case 5:
        return EStreamlineDLSSGMode::On5X;
    case 6:
        return EStreamlineDLSSGMode::On6X;
    default:
        return EStreamlineDLSSGMode::Off;
    }
}
} // namespace

void UHoverGraphicsSettings::Initialize(UWorld *World)
{
    if (bInitialized)
        return;
    PlayWorld = World;
    bInitialized = true;
    for (const TCHAR *Name : RendererCVars)
        if (auto *CVar = IConsoleManager::Get().FindConsoleVariable(Name))
            RendererBeforePlay.Add(Name, CVar->GetFloat());
    bDLSSBeforePlay = UDLSSLibrary::IsDLSSEnabled();
    FrameGenerationBeforePlay = uint8(UStreamlineLibraryDLSSG::GetDLSSGMode());
    ReflexBeforePlay = uint8(UStreamlineLibraryReflex::GetReflexMode());

    int32 SavedUpscaling = 0, SavedFG = 0;
    GConfig->GetBool(SettingsSection, TEXT("Invincible"), Current.bInvincible, GGameUserSettingsIni);
    if (GConfig->GetInt(SettingsSection, TEXT("Upscaling"), SavedUpscaling, GGameUserSettingsIni))
    {
        Current.Upscaling = EHoverUpscaling(SavedUpscaling);
        GConfig->GetInt(SettingsSection, TEXT("FrameGeneration"), SavedFG, GGameUserSettingsIni);
        Current.FrameGeneration = SavedFG;
        Apply(Current, false);
    }
    else if (bDLSSBeforePlay)
    {
        // Reflect an externally selected mode without changing an owner's renderer on first launch.
        float BestDistance = TNumericLimits<float>::Max();
        const float Screen = RendererBeforePlay.FindRef(TEXT("r.ScreenPercentage"));
        for (EHoverUpscaling Mode : GetUpscalingOptions())
        {
            if (Mode == EHoverUpscaling::Native)
                continue;
            bool Supported, Fixed;
            float Optimal, Min, Max, Sharpness;
            UDLSSLibrary::GetDLSSModeInformation(DLSSMode(Mode), FVector2D::ZeroVector, Supported, Optimal, Fixed, Min,
                                                 Max, Sharpness);
            if (Supported && FMath::Abs(Screen - Optimal) < BestDistance)
            {
                BestDistance = FMath::Abs(Screen - Optimal);
                Current.Upscaling = Mode;
            }
        }
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_GRAPHICS initialized: %s | %s"), *GetRuntimeStatus(), *GetAvailabilityNote());
}

void UHoverGraphicsSettings::RestoreRenderer()
{
    if (!bInitialized)
        return;
    UStreamlineLibraryDLSSG::SetDLSSGMode(EStreamlineDLSSGMode(FrameGenerationBeforePlay));
    UStreamlineLibraryReflex::SetReflexMode(EStreamlineReflexMode(ReflexBeforePlay));
    UDLSSLibrary::EnableDLSS(bDLSSBeforePlay);
    for (const auto &Pair : RendererBeforePlay)
        SetRendererValue(*Pair.Key, Pair.Value);
    bInitialized = false;
}

TArray<EHoverUpscaling> UHoverGraphicsSettings::GetUpscalingOptions() const
{
    TArray<EHoverUpscaling> Result{EHoverUpscaling::Native};
    for (EHoverUpscaling Mode : {EHoverUpscaling::DLAA, EHoverUpscaling::Quality, EHoverUpscaling::Balanced,
                                 EHoverUpscaling::Performance, EHoverUpscaling::UltraPerformance})
        if (UDLSSLibrary::IsDLSSModeSupported(DLSSMode(Mode)))
            Result.Add(Mode);
    return Result;
}

TArray<int32> UHoverGraphicsSettings::GetFrameGenerationOptions() const
{
    TArray<int32> Result{0};
    if (UStreamlineLibraryReflex::IsReflexSupported())
        for (int32 Mode : {2, 3, 4, 5, 6, 1})
            if (UStreamlineLibraryDLSSG::IsDLSSGModeSupported(FGMode(Mode)))
                Result.Add(Mode);
    return Result;
}

bool UHoverGraphicsSettings::IsFrameGenerationPreviewOnly() const
{
    return PlayWorld && PlayWorld->WorldType == EWorldType::PIE;
}

bool UHoverGraphicsSettings::Apply(FHoverGraphicsOptions Options, bool bSave)
{
    if (!bInitialized)
        return false;
    const bool Supported = GetUpscalingOptions().Contains(Options.Upscaling) &&
                           GetFrameGenerationOptions().Contains(Options.FrameGeneration);
    if (!GetUpscalingOptions().Contains(Options.Upscaling))
        Options.Upscaling = EHoverUpscaling::Native;
    if (!GetFrameGenerationOptions().Contains(Options.FrameGeneration))
        Options.FrameGeneration = 0;
    float Screen = 100.f;
    if (Options.Upscaling != EHoverUpscaling::Native)
    {
        bool ModeSupported, Fixed;
        float Min, Max, Sharpness;
        UDLSSLibrary::GetDLSSModeInformation(DLSSMode(Options.Upscaling), FVector2D::ZeroVector, ModeSupported, Screen,
                                             Fixed, Min, Max, Sharpness);
        if (!ModeSupported)
            return false;
    }
    SetRendererValue(TEXT("r.DynamicRes.OperationMode"), 0);
    SetRendererValue(TEXT("r.AntiAliasingMethod"), 4);
    SetRendererValue(TEXT("r.Editor.Viewport.OverridePIEScreenPercentage"), 0);
    UDLSSLibrary::EnableDLSS(Options.Upscaling != EHoverUpscaling::Native);
    SetRendererValue(TEXT("r.ScreenPercentage"), Screen);
    const int32 EffectiveFG = IsFrameGenerationPreviewOnly() ? 0 : Options.FrameGeneration;
    if (EffectiveFG != 0)
        UStreamlineLibraryReflex::SetReflexMode(EStreamlineReflexMode::Enabled);
    UStreamlineLibraryDLSSG::SetDLSSGMode(FGMode(EffectiveFG));
    Current = Options;
    if (bSave)
    {
        GConfig->SetBool(SettingsSection, TEXT("Invincible"), Current.bInvincible, GGameUserSettingsIni);
        GConfig->SetInt(SettingsSection, TEXT("Upscaling"), int32(Current.Upscaling), GGameUserSettingsIni);
        GConfig->SetInt(SettingsSection, TEXT("FrameGeneration"), Current.FrameGeneration, GGameUserSettingsIni);
        GConfig->Flush(false, GGameUserSettingsIni);
    }
    for (TActorIterator<AHoverPilot> It(PlayWorld); It; ++It)
        It->SetInvincible(Current.bInvincible);
    UE_LOG(LogTemp, Display, TEXT("HOVER_GRAPHICS applied %s | FG preference=%s saved=%d | %s"),
           *UpscalingName(Current.Upscaling), *FrameGenerationName(Current.FrameGeneration), bSave,
           *GetRuntimeStatus());
    return Supported;
}

FString UHoverGraphicsSettings::UpscalingName(EHoverUpscaling Mode)
{
    switch (Mode)
    {
    case EHoverUpscaling::DLAA:
        return TEXT("DLAA - native resolution");
    case EHoverUpscaling::Quality:
        return TEXT("DLSS Quality");
    case EHoverUpscaling::Balanced:
        return TEXT("DLSS Balanced");
    case EHoverUpscaling::Performance:
        return TEXT("DLSS Performance");
    case EHoverUpscaling::UltraPerformance:
        return TEXT("DLSS Ultra Performance");
    default:
        return TEXT("Native TSR (DLSS off)");
    }
}

FString UHoverGraphicsSettings::FrameGenerationName(int32 Mode)
{
    if (Mode == 0)
        return TEXT("Off");
    if (Mode == 1)
        return TEXT("Dynamic");
    return FString::Printf(TEXT("%dX"), Mode);
}

FString UHoverGraphicsSettings::GetAvailabilityNote() const
{
    if (!UDLSSLibrary::IsDLSSSupported())
        return FString::Printf(
            TEXT("DLSS unavailable: %s"),
            *StaticEnum<UDLSSSupport>()->GetDisplayNameTextByValue(int64(UDLSSLibrary::QueryDLSSSupport())).ToString());
    if (!UStreamlineLibraryDLSSG::IsDLSSGSupported())
        return FString::Printf(TEXT("Frame generation unavailable: %s"),
                               *StaticEnum<EStreamlineFeatureSupport>()
                                    ->GetDisplayNameTextByValue(int64(UStreamlineLibraryDLSSG::QueryDLSSGSupport()))
                                    .ToString());
    if (IsFrameGenerationPreviewOnly())
        return TEXT("Frame generation is saved for Standalone Game; inactive in editor Play.");
    return TEXT("Supported modes only. Frame generation enables NVIDIA Reflex automatically.");
}

FString UHoverGraphicsSettings::GetRuntimeStatus() const
{
    const auto *Screen = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"));
    float FPS = 0;
    int32 Presented = 0;
    UStreamlineLibraryDLSSG::GetDLSSGFrameTiming(FPS, Presented);
    return FString::Printf(
        TEXT("DLSS enabled=%d | render scale=%.1f%% | FG mode=%s | presented=%d | %.1f FPS | foreground=%d"),
        UDLSSLibrary::IsDLSSEnabled(), Screen ? Screen->GetFloat() : 0.f,
        *StaticEnum<EStreamlineDLSSGMode>()
             ->GetDisplayNameTextByValue(int64(UStreamlineLibraryDLSSG::GetDLSSGMode()))
             .ToString(),
        Presented, FPS, FApp::HasFocus());
}
