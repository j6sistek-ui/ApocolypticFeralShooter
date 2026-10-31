#pragma once
#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "HoverZombieVoice.generated.h"

class AActor;
class UAudioComponent;
class USceneComponent;
class USoundAttenuation;
class USoundBase;

UENUM(BlueprintType)
enum class EHoverZombieVoiceKind : uint8
{
    Idle,
    Chase,
    Attack,
    Pain,
    Death,
    Roar
};

// NYC Survival zombie voice budget (2026-10-31 diversity pass). Only AHoverNYCZombie calls it, so
// Cyber City, Lakeside and PostApo never play through it. At most MaxVocals zombie vocals play at
// once and the zombies nearest the listener win; death vocals get MaxExtraDeathVocals more on top.
// Footsteps share a separate per-window budget, and the sight roar a world-wide cooldown.
UCLASS()
class HOVERFLIGHT_API UHoverZombieVoice : public UWorldSubsystem
{
    GENERATED_BODY()
  public:
    static constexpr int32 MaxVocals = 6;
    static constexpr int32 MaxExtraDeathVocals = 3;
    static constexpr int32 MaxStepsPerWindow = 8;
    static constexpr float StepWindowSeconds = .25f;
    static constexpr float RoarCooldownSeconds = 4.f;

    static UHoverZombieVoice *Get(const UObject *WorldContext);

    virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;
    virtual void Initialize(FSubsystemCollectionBase &Collection) override;
    virtual void Deinitialize() override;

    // Plays Sound attached to Attach (Socket may be NAME_None) when the budget allows. Returns the
    // component, or null when the budget denied it. Logs HOVER_ZOMBIE_VOICE.
    UAudioComponent *PlayVocal(AActor *Zombie, EHoverZombieVoiceKind Kind, USoundBase *Sound, USceneComponent *Attach,
                               FName Socket, float Volume, float Pitch, const FString &DefinitionName);
    // One footstep slot in the current window (at most MaxStepsPerWindow per StepWindowSeconds).
    bool TryConsumeFootstep();
    // True (and starts the cooldown) when no sight roar started in the last RoarCooldownSeconds.
    bool TryStartRoar();
    // Camera location of player 0, otherwise its pawn, otherwise the origin.
    FVector GetListenerLocation() const;
    int32 GetActiveVocalCount();

    USoundAttenuation *GetVoiceAttenuation() const
    {
        return VoiceAttenuation;
    }
    USoundAttenuation *GetFootstepAttenuation() const
    {
        return FootstepAttenuation;
    }

    static const TCHAR *KindName(EHoverZombieVoiceKind Kind);

    // Validation counters (read by the proof scripts).
    UPROPERTY(BlueprintReadOnly) int32 VocalsPlayed = 0;
    UPROPERTY(BlueprintReadOnly) int32 VocalsDenied = 0;
    UPROPERTY(BlueprintReadOnly) int32 VocalsPreempted = 0;
    UPROPERTY(BlueprintReadOnly) int32 StepsPlayed = 0;
    UPROPERTY(BlueprintReadOnly) int32 StepsDenied = 0;
    UPROPERTY(BlueprintReadOnly) int32 RoarsStarted = 0;

  private:
    struct FActiveVocal
    {
        TWeakObjectPtr<UAudioComponent> Audio;
        TWeakObjectPtr<AActor> Owner;
        bool bDeathSlot = false;
    };
    void Prune();
    float DistanceToListener(const AActor *Actor, const FVector &Listener) const;

    TArray<FActiveVocal> Active;
    UPROPERTY() TObjectPtr<USoundAttenuation> VoiceAttenuation;
    UPROPERTY() TObjectPtr<USoundAttenuation> FootstepAttenuation;
    float StepWindowStart = -100.f;
    int32 StepsInWindow = 0;
    float LastRoarTime = -100.f;
};
