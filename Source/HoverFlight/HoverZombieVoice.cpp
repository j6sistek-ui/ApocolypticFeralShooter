#include "HoverZombieVoice.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"

namespace
{
USoundAttenuation *MakeAttenuation(UObject *Outer, const TCHAR *Name, float InnerRadius, float Falloff)
{
    auto *Attenuation = NewObject<USoundAttenuation>(Outer, Name);
    FSoundAttenuationSettings &Settings = Attenuation->Attenuation;
    Settings.bAttenuate = true;
    Settings.bSpatialize = true;
    Settings.AttenuationShape = EAttenuationShape::Sphere;
    Settings.AttenuationShapeExtents = FVector(InnerRadius, 0.f, 0.f);
    Settings.FalloffDistance = Falloff;
    Settings.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
    return Attenuation;
}
} // namespace

UHoverZombieVoice *UHoverZombieVoice::Get(const UObject *WorldContext)
{
    const UWorld *World = WorldContext ? WorldContext->GetWorld() : nullptr;
    return World ? World->GetSubsystem<UHoverZombieVoice>() : nullptr;
}

bool UHoverZombieVoice::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UHoverZombieVoice::Initialize(FSubsystemCollectionBase &Collection)
{
    Super::Initialize(Collection);
    // Vocals: full volume inside 3 m, fading out over 30 m. Steps carry less far.
    VoiceAttenuation = MakeAttenuation(this, TEXT("HoverZombieVoiceAttenuation"), 300.f, 3000.f);
    FootstepAttenuation = MakeAttenuation(this, TEXT("HoverZombieStepAttenuation"), 150.f, 2200.f);
}

void UHoverZombieVoice::Deinitialize()
{
    Active.Reset();
    Super::Deinitialize();
}

const TCHAR *UHoverZombieVoice::KindName(EHoverZombieVoiceKind Kind)
{
    switch (Kind)
    {
    case EHoverZombieVoiceKind::Idle:
        return TEXT("Idle");
    case EHoverZombieVoiceKind::Chase:
        return TEXT("Chase");
    case EHoverZombieVoiceKind::Attack:
        return TEXT("Attack");
    case EHoverZombieVoiceKind::Pain:
        return TEXT("Pain");
    case EHoverZombieVoiceKind::Death:
        return TEXT("Death");
    case EHoverZombieVoiceKind::Roar:
        return TEXT("Roar");
    }
    return TEXT("Unknown");
}

FVector UHoverZombieVoice::GetListenerLocation() const
{
    if (const APlayerCameraManager *Camera = UGameplayStatics::GetPlayerCameraManager(this, 0))
        return Camera->GetCameraLocation();
    if (const APawn *Player = UGameplayStatics::GetPlayerPawn(this, 0))
        return Player->GetActorLocation();
    return FVector::ZeroVector;
}

float UHoverZombieVoice::DistanceToListener(const AActor *Actor, const FVector &Listener) const
{
    return Actor ? FVector::Dist(Actor->GetActorLocation(), Listener) : TNumericLimits<float>::Max();
}

void UHoverZombieVoice::Prune()
{
    Active.RemoveAll([](const FActiveVocal &Entry) { return !Entry.Audio.IsValid() || !Entry.Audio->IsPlaying(); });
}

int32 UHoverZombieVoice::GetActiveVocalCount()
{
    Prune();
    return Active.Num();
}

UAudioComponent *UHoverZombieVoice::PlayVocal(AActor *Zombie, EHoverZombieVoiceKind Kind, USoundBase *Sound,
                                              USceneComponent *Attach, FName Socket, float Volume, float Pitch,
                                              const FString &DefinitionName)
{
    if (!Zombie || !Sound || !Attach)
        return nullptr;
    Prune();
    int32 Regular = 0, Deaths = 0;
    for (const FActiveVocal &Entry : Active)
        (Entry.bDeathSlot ? Deaths : Regular) += 1;

    bool bDeathSlot = false;
    if (Kind == EHoverZombieVoiceKind::Death && Deaths < MaxExtraDeathVocals)
        bDeathSlot = true;
    else if (Regular >= MaxVocals)
    {
        // Full: the nearest zombies win. Pre-empt the farthest regular vocal if this one is closer.
        const FVector Listener = GetListenerLocation();
        const float Mine = DistanceToListener(Zombie, Listener);
        int32 Farthest = INDEX_NONE;
        float FarthestDistance = -1.f;
        for (int32 Index = 0; Index < Active.Num(); ++Index)
        {
            if (Active[Index].bDeathSlot)
                continue;
            const float Distance = DistanceToListener(Active[Index].Owner.Get(), Listener);
            if (Distance > FarthestDistance)
            {
                FarthestDistance = Distance;
                Farthest = Index;
            }
        }
        if (Farthest == INDEX_NONE || Mine >= FarthestDistance)
        {
            ++VocalsDenied;
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_VOICE_DENIED %s %s %s active=%d"), KindName(Kind),
                   *GetNameSafe(Sound), *DefinitionName, Active.Num());
            return nullptr;
        }
        if (UAudioComponent *Old = Active[Farthest].Audio.Get())
            Old->FadeOut(.15f, 0.f);
        Active.RemoveAt(Farthest);
        ++VocalsPreempted;
    }

    UAudioComponent *Audio = UGameplayStatics::SpawnSoundAttached(
        Sound, Attach, Socket, FVector::ZeroVector, EAttachLocation::SnapToTarget, /*bStopWhenAttachedToDestroyed*/ false,
        Volume, Pitch, 0.f, VoiceAttenuation, nullptr, /*bAutoDestroy*/ true);
    if (!Audio)
        return nullptr;
    FActiveVocal Entry;
    Entry.Audio = Audio;
    Entry.Owner = Zombie;
    Entry.bDeathSlot = bDeathSlot;
    Active.Add(Entry);
    ++VocalsPlayed;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_ZOMBIE_VOICE %s %s %s active=%d"), KindName(Kind), *GetNameSafe(Sound),
           *DefinitionName, Active.Num());
    return Audio;
}

bool UHoverZombieVoice::TryConsumeFootstep()
{
    const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
    if (Now - StepWindowStart >= StepWindowSeconds)
    {
        StepWindowStart = Now;
        StepsInWindow = 0;
    }
    if (StepsInWindow >= MaxStepsPerWindow)
    {
        ++StepsDenied;
        return false;
    }
    ++StepsInWindow;
    ++StepsPlayed;
    return true;
}

bool UHoverZombieVoice::TryStartRoar()
{
    const float Now = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
    if (Now - LastRoarTime < RoarCooldownSeconds)
        return false;
    LastRoarTime = Now;
    ++RoarsStarted;
    return true;
}
