#include "HoverNYCSurvival.h"
#include "HoverSpawnDirector.h"
#include "HoverNYCZombie.h"
#include "HoverAttackSlots.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/PlayerStart.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/PackageName.h"
#include "Sound/SoundBase.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "TimerManager.h"
#include "World/ZE_ZombieSpawnPoint.h"

namespace
{
const TCHAR *NYCWavesPath = TEXT("/Game/HoverPrototype/NYC/DA_NYCWaves.DA_NYCWaves");
const TCHAR *NYCEncountersPath = TEXT("/Game/HoverPrototype/NYC/DA_NYCEncounters.DA_NYCEncounters");

// Checked first so a missing asset logs one clear line instead of a loader warning.
UObject *LoadIfPresent(const TCHAR *ObjectPath)
{
    return FPackageName::DoesPackageExist(FPackageName::ObjectPathToPackageName(FString(ObjectPath)))
               ? LoadObject<UObject>(nullptr, ObjectPath)
               : nullptr;
}

TSoftObjectPtr<USoundBase> NYCZombieSound(const TCHAR *Folder, const TCHAR *Name)
{
    return TSoftObjectPtr<USoundBase>(FSoftObjectPath(
        FString::Printf(TEXT("/Game/HoverPrototype/Audio/NYC/Zombies/%s/%s.%s"), Folder, Name, Name)));
}
} // namespace

// ---------------------------------------------------------------------------------------------
// Audio defaults (audio additions) for the HoverCyberVariants.h classes, which have no .cpp.

UHoverNYCEncounterSettings::UHoverNYCEncounterSettings()
{
    HordeAmbience =
        NYCZombieSound(TEXT("Crowd"), TEXT("SFX_Zombie_Group_Moaning_Roaming_Aggressive_ShortDistance_001"));
    // Bands: under 8 alive, 8-16, over 16.
    RoundAmbience = {
        NYCZombieSound(TEXT("Crowd"), TEXT("SFX_Zombie_Group_Moaning_Roaming_Medium_ShortDistance_001")),
        NYCZombieSound(TEXT("Crowd"), TEXT("SFX_Zombie_Group_Moaning_Roaming_Large_MidDistance_001")),
        NYCZombieSound(TEXT("Crowd"), TEXT("SFX_Zombie_Group_Moaning_Roaming_Large_ShortDistance_001")),
    };
    WeatherBed = TSoftObjectPtr<USoundBase>(
        FSoftObjectPath(TEXT("/Game/cplomedia_WeatherSFXLoops/Cues/Cue_WindLoop01_Cue.Cue_WindLoop01_Cue")));
}

UHoverCyberZombieDefinition::UHoverCyberZombieDefinition()
{
    const TCHAR *Feeding[] = {
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Light_001"),
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Light_002"),
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Medium_001"),
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Heavy_with_Crackling_Bones_Loop_001"),
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Heavy_with_Zombies_001"),
        TEXT("SFX_Gore_Eating_Flesh_Disgusting_Muddy_Squishy_Light_with_Crackling_Bones_001"),
    };
    for (const TCHAR *Name : Feeding)
        FeedingSounds.Add(NYCZombieSound(TEXT("Feeding"), Name));
    // Zombie-diversity defaults (also the in-class initialisers; repeated here so the contract
    // values live next to the other definition defaults).
    SkinMaterialSlot = NAME_None;
    bRandomizeMorphTargets = false;
    MorphTargetMax = .8f;
    // Neutral: only definitions that author a range are varied (review 2026-10-31).
    ScaleJitter = FVector2D(1.f, 1.f);
    AnimRateJitter = FVector2D(1.f, 1.f);
    bAlignMeshYaw = false;
    MeshYawOffset = 0.f;
    SightRoarChance = .4f;
    VoicePitch = FVector2D(.95f, 1.05f);
    VoiceVolume = 1.f;
    VocalInterval = FVector2D(3.f, 8.f);
    FootstepVolume = .6f;
    FootstepStride = 75.f;
    BloodScale = 1.f;
}

// ---------------------------------------------------------------------------------------------
// UHoverNYCEncounterSettings boss schedule (06.4). Lives here because HoverCyberVariants.h has no .cpp.

const FHoverBossRound *UHoverNYCEncounterSettings::FindBossRound(int32 Round) const
{
    if (Round <= 0)
        return nullptr;
    const auto HasBoss = [](const TArray<TObjectPtr<UHoverCyberZombieDefinition>> &Bosses) {
        return Bosses.ContainsByPredicate(
            [](const TObjectPtr<UHoverCyberZombieDefinition> &D) { return D != nullptr; });
    };
    for (const FHoverBossRound &Row : BossRounds)
        if (Row.Round == Round)
            return HasBoss(Row.Bosses) ? &Row : nullptr;
    // Generated cycle: 33 + 6k in a three-step composition. Horde beats boss: a horde round keeps
    // its round and the boss plays one round later; the step is taken from the nominal round, so
    // the shift never changes the composition.
    const int32 Interval = FMath::Max(1, BossCycleInterval);
    const auto OnCycle = [&](int32 N) { return N >= BossCycleFromRound && (N - BossCycleFromRound) % Interval == 0; };
    int32 Nominal = INDEX_NONE;
    if (OnCycle(Round) && !IsHordeRound(Round))
        Nominal = Round;
    else if (OnCycle(Round - 1) && IsHordeRound(Round - 1))
        Nominal = Round - 1;
    if (Nominal == INDEX_NONE)
        return nullptr;
    Generated = FHoverBossRound();
    Generated.Round = Round;
    switch (((Nominal - BossCycleFromRound) / Interval) % 3)
    {
    case 0:
        // The golem with two additive Brute adds.
        Generated.Bosses = {StoneGolem, Brute, Brute};
        break;
    case 1:
        Generated.Bosses = {GiantKid, GiantKid};
        Generated.SecondEntersAtFraction = .5f;
        break;
    default:
        Generated.Bosses = {StoneGolem, GiantKid};
        Generated.SecondEntersAtFraction = .5f;
        break;
    }
    Generated.Bosses.RemoveAll([](const TObjectPtr<UHoverCyberZombieDefinition> &D) { return D == nullptr; });
    // Without its lead boss the row is no boss round (the adds alone would be a stray heavy round).
    return Generated.Bosses.Num() && IsBossDefinition(Generated.Bosses[0]) ? &Generated : nullptr;
}

bool UHoverNYCEncounterSettings::IsBossDefinition(const UZE_ZombieDataAsset *Definition) const
{
    const auto *Cyber = Cast<UHoverCyberZombieDefinition>(Definition);
    return Cyber && (Cyber->Role == EHoverZombieRole::Boss || Cyber == StoneGolem.Get() || Cyber == GiantKid.Get());
}

// ---------------------------------------------------------------------------------------------
// AHoverNYCSurvivalGameMode

AHoverNYCSurvivalGameMode::AHoverNYCSurvivalGameMode()
{
    // The vendor 0.5 s tick (ZE_ZombieWaveGameMode.cpp:30) would quantise the 0.35 s horde floor.
    PrimaryActorTick.TickInterval = .1f;
}

void AHoverNYCSurvivalGameMode::InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage)
{
    // Vendor InitGame, then the Cyber pawn/PC/HUD and DA_CyberWaves/DA_CyberEncounters.
    Super::InitGame(MapName, Options, ErrorMessage);
    auto *Waves = Cast<UZE_WaveGameModeSettings>(LoadIfPresent(NYCWavesPath));
    NYC = Cast<UHoverNYCEncounterSettings>(LoadIfPresent(NYCEncountersPath));
    if (Waves)
    {
        WaveSettings = Waves;
        // Only the NYC asset spawns the crowd-AI zombie; the Cyber data keeps its own class. A
        // Blueprint child authored on the asset (BP_NYCZombie with ABP_NYCZombie) is kept; only a
        // missing or foreign class is replaced.
        if (!Waves->ZombieClass || !Waves->ZombieClass->IsChildOf(AHoverNYCZombie::StaticClass()))
            Waves->ZombieClass = AHoverNYCZombie::StaticClass();
    }
    if (NYC)
        Encounters = NYC;
    if (!Waves || !NYC)
    {
        // Until the editor pass authors the NYC assets, run the Cyber data with the NYC
        // pacing constants from the class defaults.
        UE_LOG(LogTemp, Warning, TEXT("HOVER_NYC_SURVIVAL missing data waves=%s encounters=%s; using %s"),
               Waves ? TEXT("ok") : TEXT("missing"), NYC ? TEXT("ok") : TEXT("missing"), *GetNameSafe(WaveSettings));
        if (!NYC)
            NYC = GetMutableDefault<UHoverNYCEncounterSettings>();
    }
    // In memory only, as in the Cyber loader; the asset is never saved from here.
    if (WaveSettings)
        WaveSettings->WaveHUDClass = UHoverCyberWaveHUD::StaticClass();
    bExternalSpawnDirector = true;
    Director = NewObject<UHoverSpawnDirector>(this, TEXT("NYCSpawnDirector"));
    UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_SURVIVAL waves=%s encounters=%s zombieClass=%s"),
           *GetNameSafe(WaveSettings), *GetNameSafe(NYC),
           WaveSettings ? *GetNameSafe(WaveSettings->ZombieClass.Get()) : TEXT("none"));
    // Stage 1 narrowing, stated here so the 06.8 pool rule and the Section 8 Â§11 door-isolation
    // checks are visibly skipped rather than silently passing: zone pools (player zone plus one open
    // hop), doors and their prices, the power hold, Pack-a-Punch, perk and armory stations are
    // deferred. Zones are tagged volumes only and every spawner is a candidate from round 1. The
    // definition fields marked "data only" in HoverCyberVariants.h (phases, crawlers, gore, vocals)
    // and the AI hooks GetWaveScales / ApplyPursuitSpeed / SelectChaseTarget are deferred as well.
    UE_LOG(LogTemp, Display,
           TEXT("HOVER_NYC_SURVIVAL deferred=zone-pools,doors,power,pap,stations,boss-phases,crawlers,gore,vocals,"
                "ai-hooks"));
}

void AHoverNYCSurvivalGameMode::BeginPlay()
{
    Super::BeginPlay();
    if (Director)
        Director->Init(this, NYC);
    UHoverAttackSlotSubsystem::ApplyNYCCrowdTuning(GetWorld());
    OnWaveStateChanged.AddUniqueDynamic(this, &AHoverNYCSurvivalGameMode::OnRoundStateChanged);
}

void AHoverNYCSurvivalGameMode::Tick(float DeltaSeconds)
{
    // The director runs first so Chosen and its bIsEnabled flag are fresh when the vendor spawns.
    if (Director)
        Director->Update(DeltaSeconds);
    UpdateBossArming();
    // With bExternalSpawnDirector the Cyber tick keeps damage/HUD upkeep and always runs the vendor tick.
    Super::Tick(DeltaSeconds);
    // Optional extra spawns in one tick (MaxSpawnsPerTick defaults to 1, so this is off). The vendor
    // SpawnZombie is private and spawns one zombie per tick; re-entering its tick with a zero
    // delta and a zero spawn rate is the only adapter-side route to a second spawn.
    for (int32 Extra = 1; Director && NYC && Extra < NYC->MaxSpawnsPerTick &&
                          GetWaveState() == EZE_WaveState::WaveInProgress && Director->PrepareExtraSpawn();
         ++Extra)
        AZE_ZombieWaveGameMode::Tick(0.f);
    if (Director)
        ActiveSpawnCount = Director->GetCandidateCount();
    if (bAmbienceActive && NYC && (AmbienceCheckTimer += DeltaSeconds) >= NYC->AmbienceCheckSeconds)
    {
        AmbienceCheckTimer = 0.f;
        UpdateAmbience();
    }
}

void AHoverNYCSurvivalGameMode::EndPlay(const EEndPlayReason::Type Reason)
{
    bAmbienceActive = false;
    StopAmbience(0.f);
    if (UAudioComponent *Weather = WeatherAmbience.Get(); IsValid(Weather))
    {
        Weather->Stop();
        Weather->DestroyComponent();
    }
    WeatherAmbience = nullptr;
    Super::EndPlay(Reason);
}

void AHoverNYCSurvivalGameMode::StartWave()
{
    // The vendor builds the quota and the schedule through ConfigureWave (ZE cpp:494).
    Super::StartWave();
    if (Director && GetWaveState() == EZE_WaveState::WaveInProgress)
        Director->BeginRound(GetCurrentWave(), GetRoundKind(GetCurrentWave()), RoundQuota);
    if (auto *Slots = UHoverAttackSlotSubsystem::Get(this))
    {
        // Tuning placeholders: 3 tokens, 2 on horde rounds, corpse budget off.
        Slots->SetTokenBudget(3, 2);
        Slots->SetHordeRound(NYC && NYC->IsHordeRound(GetCurrentWave()));
        Slots->SetMaxLiveCorpses(0);
    }
    // Crowd ambience starts with the first round and is re-picked at every round start.
    if (GetWaveState() == EZE_WaveState::WaveInProgress && !bGameOver)
    {
        bAmbienceActive = true;
        AmbienceCheckTimer = 0.f;
        UpdateAmbience();
        // The weather bed starts once, with the first round, and runs under every crowd bed until EndPlay.
        if (!WeatherAmbience && NYC && !NYC->WeatherBed.IsNull())
            if (USoundBase *Wind = NYC->WeatherBed.LoadSynchronous())
            {
                WeatherAmbience =
                    UGameplayStatics::CreateSound2D(this, Wind, NYC->WeatherBedVolume, 1.f, 0.f, nullptr, false, false);
                if (WeatherAmbience)
                    WeatherAmbience->FadeIn(4.f, 1.f);
                UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_WEATHER_BED %s"), *GetNameSafe(Wind));
            }
    }
}

USoundBase *AHoverNYCSurvivalGameMode::ChooseAmbience() const
{
    if (!NYC || bGameOver)
        return nullptr;
    // GetRoundKind, not IsHordeRound: without a Kid definition the swarm round plays as a normal round.
    if (GetRoundKind(GetCurrentWave()) == EHoverRoundKind::Horde)
        return NYC->HordeAmbience.LoadSynchronous();
    if (NYC->RoundAmbience.IsEmpty())
        return nullptr;
    const int32 Alive = Director ? Director->GetLiveCount() : 0;
    const int32 Band = Alive >= NYC->AmbienceLargeBandAlive ? 2 : Alive >= NYC->AmbienceMidBandAlive ? 1 : 0;
    return NYC->RoundAmbience[FMath::Min(Band, NYC->RoundAmbience.Num() - 1)].LoadSynchronous();
}

void AHoverNYCSurvivalGameMode::UpdateAmbience()
{
    USoundBase *Sound = ChooseAmbience();
    if (Sound == AmbienceSound && (Sound ? Ambience && Ambience->IsPlaying() : !Ambience))
        return;
    const float Fade = NYC ? NYC->AmbienceFadeSeconds : 0.f;
    StopAmbience(Fade);
    if (!Sound)
        return;
    // Kept (bAutoDestroy false) so the bed can be faded and swapped; created stopped so FadeIn is its only start.
    Ambience = UGameplayStatics::CreateSound2D(this, Sound, NYC->AmbienceVolume, 1.f, 0.f, nullptr, false, false);
    if (!Ambience)
        return;
    AmbienceSound = Sound;
    Ambience->FadeIn(Fade, 1.f);
    UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_AMBIENCE round=%d sound=%s"), GetCurrentWave(), *GetNameSafe(Sound));
}

void AHoverNYCSurvivalGameMode::StopAmbience(float FadeSeconds)
{
    if (UAudioComponent *Old = Ambience.Get(); IsValid(Old))
    {
        if (FadeSeconds > 0.f && Old->IsPlaying())
        {
            Old->bAutoDestroy = true; // The retired bed removes itself once faded out.
            Old->FadeOut(FadeSeconds, 0.f);
        }
        else
        {
            Old->Stop();
            Old->DestroyComponent();
        }
    }
    Ambience = nullptr;
    AmbienceSound = nullptr;
}

void AHoverNYCSurvivalGameMode::OnRoundStateChanged(int32 Wave, EZE_WaveState State, float Timer)
{
    if (Director && State != EZE_WaveState::WaveInProgress)
        Director->EndRound();
}

AActor *AHoverNYCSurvivalGameMode::ChoosePlayerStart_Implementation(AController *Player)
{
    for (TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
        if (It->ActorHasTag(TEXT("AFS_SurvivalStart")))
            return *It;
    return Super::ChoosePlayerStart_Implementation(Player);
}

const FZE_WaveConfig *AHoverNYCSurvivalGameMode::FindRow(const UZE_WaveGameModeSettings *Settings, int32 Wave)
{
    // Mirrors the vendor match rule (ZE_WaveGameModeSettings.cpp:14-21).
    if (Settings && Settings->bUseCustomWaves && Wave > 0)
        for (int32 Index = 0; Index < Settings->CustomWaves.Num(); ++Index)
        {
            const FZE_WaveConfig &Row = Settings->CustomWaves[Index];
            if ((Row.WaveNumber > 0 ? Row.WaveNumber : Index + 1) == Wave)
                return &Row;
        }
    return nullptr;
}

EHoverRoundKind AHoverNYCSurvivalGameMode::GetRoundKind(int32 Wave) const
{
    if (!NYC || Wave <= 0)
        return EHoverRoundKind::Normal;
    // Spine order: horde beats boss beats heavy. FindBossRound already resolves the horde shift, and
    // a boss round is never a heavy round (no heavy Brutes on a shifted even round).
    if (NYC->Kid && NYC->IsHordeRound(Wave))
        return EHoverRoundKind::Horde;
    if (NYC->FindBossRound(Wave))
        return EHoverRoundKind::Boss;
    if (NYC->Brute && Wave == NYC->BruteDebutWave)
        return EHoverRoundKind::BruteDebut;
    if (NYC->Brute && NYC->BruteInterval > 0 && Wave >= NYC->BruteFirstWave &&
        (Wave - NYC->BruteFirstWave) % NYC->BruteInterval == 0)
        return EHoverRoundKind::Heavy;
    return EHoverRoundKind::Normal;
}

void AHoverNYCSurvivalGameMode::ConfigureWave(int32 Wave, int32 &Count, TArray<UZE_ZombieDataAsset *> &Types)
{
    // Skip the Cyber parent: its 24 swarm clamp and IsBruteWave schedule do not apply here.
    AZE_ZombieWaveGameMode::ConfigureWave(Wave, Count, Types);
    ScheduledSpecials.Reset();
    PendingBosses.Reset();
    LeadBoss = nullptr;
    BossesReleased = 0;
    SecondEntersAtFraction = 0.f;
    SpawnedThisRound = 0;
    bVendorSpawnPending = false;
    bAdditiveSpawnPending = false;
    // R1-30: the incoming Count is the row's BaseZombieCount (vendor StartWave), and Types are the
    // row's ZombieTypes or DefaultZombieTypes. Only rounds without a row use the endurance formula.
    if (!FindRow(WaveSettings, Wave) && NYC && Wave >= NYC->EnduranceFromRound)
        Count = NYC->CountBase + (NYC->CountQuadPercent * Wave * Wave) / 100;
    if (Types.IsEmpty() && NYC)
        for (const auto &Definition : NYC->Standards)
            if (Definition)
                Types.Add(Definition);
    const EHoverRoundKind Kind = GetRoundKind(Wave);
    if (Kind == EHoverRoundKind::Horde)
    {
        Count = NYC->HordeBase + NYC->HordePerRound * Wave;
        if (NYC->HordeCountCap > 0)
            Count = FMath::Min(Count, NYC->HordeCountCap);
        Types.Reset();
        Types.Add(NYC->Kid.Get());
    }
    Count = FMath::Clamp(FMath::RoundToInt(Count * Tuning.Count), 1, 200);
    if (NYC && Kind != EHoverRoundKind::Horde)
    {
        // Brutes replace standards inside the quota, at fixed fractions of the spawn order.
        const int32 Brutes = Kind == EHoverRoundKind::BruteDebut ? 1
                             : Kind == EHoverRoundKind::Heavy
                                 ? FMath::Min(NYC->BruteCountCap,
                                              1 + (Wave - NYC->BruteDebutWave) / FMath::Max(1, NYC->BruteCountDivisor))
                                 : 0;
        for (int32 Index = 0; Index < Brutes && NYC->Brute; ++Index)
        {
            const float Fraction = Brutes == 1                               ? NYC->LoneBrutePlacement
                                   : NYC->BrutePlacement.IsValidIndex(Index) ? NYC->BrutePlacement[Index]
                                                                             : (Index + 1.f) / (Brutes + 1.f);
            int32 Slot = FMath::Clamp(FMath::RoundToInt(Count * Fraction), 0, Count - 1);
            while (ScheduledSpecials.Contains(Slot))
                ++Slot;
            if (Slot < Count)
                ScheduledSpecials.Add(Slot, NYC->Brute.Get());
        }
        // Late rounds bleed Kids into the standard rounds: one per ten, at ordinals 5, 15, 25, ...
        if (NYC->Kid && Wave >= NYC->KidBleedFromRound)
            for (int32 Kid = 1, Kids = Count / 10; Kid <= Kids; ++Kid)
            {
                int32 Slot = Kid * 10 - 5;
                while (ScheduledSpecials.Contains(Slot))
                    ++Slot;
                if (Slot < Count)
                    ScheduledSpecials.Add(Slot, NYC->Kid.Get());
            }
        // Boss rounds: the row's entries are additive to the quota and never scaled. Stored
        // reversed so Pop() releases the listed order (R27: the golem before the Giant Kid).
        if (const FHoverBossRound *Boss = Kind == EHoverRoundKind::Boss ? NYC->FindBossRound(Wave) : nullptr)
        {
            for (int32 Index = Boss->Bosses.Num() - 1; Index >= 0; --Index)
                if (Boss->Bosses[Index])
                    PendingBosses.Add(Boss->Bosses[Index]);
            SecondEntersAtFraction = Boss->SecondEntersAtFraction;
            Count += PendingBosses.Num();
        }
    }
    RoundQuota = Count;
    UE_LOG(LogTemp, Display,
           TEXT("HOVER_NYC_ROUND round=%d kind=%s quota=%d specials=%d bosses=%d health=%.2f damage=%.2f"), Wave,
           *UEnum::GetValueAsString(Kind), RoundQuota, ScheduledSpecials.Num(), PendingBosses.Num(),
           GetRoundHealthScale(Wave), GetRoundDamageScale(Wave));
}

void AHoverNYCSurvivalGameMode::UpdateBossArming()
{
    bool bArm = false;
    if (Director && NYC && PendingBosses.Num() && !bGameOver && GetWaveState() == EZE_WaveState::WaveInProgress)
    {
        bArm = GetZombiesKilledThisWave() >= FMath::CeilToInt(NYC->BossTriggerFraction * RoundQuota);
        // A second boss on a row with SecondEntersAtFraction waits for the lead boss's health (or its
        // death); a Brute add rides out right behind the boss it belongs to.
        if (bArm && BossesReleased > 0 && SecondEntersAtFraction > 0.f && NYC->IsBossDefinition(PendingBosses.Last()))
            if (const AHoverCyberZombie *Lead = LeadBoss.Get(); Lead && !Lead->IsDead() && Lead->SurvivalComponent)
                bArm = Lead->SurvivalComponent->GetHealth() <=
                       SecondEntersAtFraction * FMath::Max(1.f, Lead->SurvivalComponent->GetMaxHealth());
    }
    if (Director)
        Director->SetBossSpawnArmed(bArm);
}

bool AHoverNYCSurvivalGameMode::IsBossAlive() const
{
    const AHoverCyberZombie *Lead = LeadBoss.Get();
    return Lead && !Lead->IsDead();
}

UZE_ZombieDataAsset *AHoverNYCSurvivalGameMode::SelectZombieData(int32 Wave, int32 SpawnIndex,
                                                                 const TArray<UZE_ZombieDataAsset *> &Types)
{
    // The vendor index (killed + alive, ZE cpp:536) repeats after kills; use our own ordinal.
    bVendorSpawnPending = true;
    // An armed boss (or boss add) takes the next free slot before any standard, and costs no ordinal.
    if (Director && Director->IsBossSpawnArmed() && PendingBosses.Num())
    {
        bAdditiveSpawnPending = true;
        return PendingBosses.Pop();
    }
    if (const auto *Special = ScheduledSpecials.Find(SpawnedThisRound); Special && *Special)
        return *Special;
    // AFS 2026-10-31: was Types[SpawnedThisRound % Num], which restarts every round, so a quota of 6-8 never
    // reached the later roster entries (owner: "I saw 2-3 maybe?").
    return DrawStandard(Types);
}

UZE_ZombieDataAsset *AHoverNYCSurvivalGameMode::DrawStandard(const TArray<UZE_ZombieDataAsset *> &Types)
{
    if (Types.IsEmpty())
        return nullptr;
    // Drop cards that are not in this round's list (a Kid-only horde round, a roster edit).
    StandardDeck.RemoveAll([&Types](const TObjectPtr<UZE_ZombieDataAsset> &Card)
                           { return !Card || !Types.Contains(Card.Get()); });
    if (StandardDeck.IsEmpty())
    {
        for (UZE_ZombieDataAsset *Type : Types)
            if (Type)
                StandardDeck.Add(Type);
        for (int32 i = StandardDeck.Num() - 1; i > 0; --i)
            StandardDeck.Swap(i, FMath::RandRange(0, i));
        // Pop takes from the back; never hand out the same type twice in a row across a reshuffle.
        if (StandardDeck.Num() > 1 && StandardDeck.Last() == LastStandardDrawn)
            StandardDeck.Swap(StandardDeck.Num() - 1, 0);
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_NYC_DECK reshuffle types=%d"), StandardDeck.Num());
    }
    if (StandardDeck.IsEmpty())
        return nullptr;
    LastStandardDrawn = StandardDeck.Pop();
    return LastStandardDrawn;
}

float AHoverNYCSurvivalGameMode::GetEffectiveSpawnRate() const
{
    // 0 = spawn this tick, BIG_NUMBER = hold. Never 0 without an enabled spawner, or the vendor
    // would fall back to an arbitrary PlayerStart (ZE cpp:413-420).
    return Director && !bGameOver ? Director->GetSpawnRate() : BIG_NUMBER;
}

float AHoverNYCSurvivalGameMode::GetRoundHealthScale(int32 Wave) const
{
    if (const auto *Row = FindRow(WaveSettings, Wave))
        return Row->HealthMultiplier;
    if (NYC && Wave >= NYC->EnduranceFromRound)
    {
        // H(r) in HP for the 100 HP standard: H(30) plus the per-round endurance steps, capped.
        int64 Health = NYC->EnduranceBaseHP;
        for (int32 Round = NYC->EnduranceFromRound; Round <= Wave && Health < NYC->HealthCapHP; ++Round)
            Health += Round <= NYC->HealthStepUntilRound ? NYC->HealthStepTo40 : NYC->HealthStep;
        return FMath::Min<int64>(Health, NYC->HealthCapHP) / 100.f;
    }
    return Super::GetRoundHealthScale(Wave);
}

float AHoverNYCSurvivalGameMode::GetRoundDamageScale(int32 Wave) const
{
    if (const auto *Row = FindRow(WaveSettings, Wave))
        return Row->DamageMultiplier;
    if (NYC && Wave >= NYC->EnduranceFromRound)
        return NYC->DamageScaleLate;
    return Super::GetRoundDamageScale(Wave);
}

FString AHoverNYCSurvivalGameMode::GetEncounterLabel() const
{
    const int32 Wave = GetCurrentWave();
    switch (GetRoundKind(Wave))
    {
    case EHoverRoundKind::Horde:
        return TEXT("KID SWARM - stay moving");
    case EHoverRoundKind::BruteDebut:
    case EHoverRoundKind::Heavy:
        return TEXT("HEAVY TANK - brute round");
    case EHoverRoundKind::Boss:
        return TEXT("BOSS ROUND - hold the street");
    default:
        return Wave > 0 ? FString::Printf(TEXT("NYC SURVIVAL - ROUND %d"), Wave) : FString(TEXT("NYC SURVIVAL"));
    }
}

void AHoverNYCSurvivalGameMode::OnZombieSpawned(AHoverCyberZombie &Zombie)
{
    // Only the vendor wave spawn passes through SelectZombieData first; a level-placed zombie
    // is tracked as live but costs no ordinal, credit or spawner use.
    const bool bVendorSpawn = bVendorSpawnPending;
    const bool bAdditiveSpawn = bVendorSpawn && bAdditiveSpawnPending;
    bVendorSpawnPending = false;
    bAdditiveSpawnPending = false;
    const int32 Wave = GetCurrentWave();
    // The one frozen health scale; the AI tick reads it instead of the round lookup.
    Zombie.HealthScale = GetRoundHealthScale(Wave);
    Zombie.SpawnTime = GetWorld()->GetTimeSeconds();
    Zombie.SpawnerUsed = bVendorSpawn && Director ? Director->GetChosen() : nullptr;
    if (NYC)
        switch (Zombie.GetRole())
        {
        case EHoverZombieRole::Standard: {
            const int32 Speed = Wave <= 1 ? 0 : NYC->RollPerRound * Wave;
            const int32 Roll = FMath::RandRange(Speed, Speed + NYC->RollWindow);
            Zombie.SpeedTier = Roll <= NYC->WalkerMaxRoll   ? NYC->WalkerSpeed
                               : Roll <= NYC->RunnerMaxRoll ? NYC->RunnerSpeed
                                                            : NYC->SprinterSpeed;
            break;
        }
        case EHoverZombieRole::Kid:
            Zombie.SpeedTier = NYC->KidSpeedTier;
            break;
        default:
            // Brutes and bosses keep their data asset speeds.
            Zombie.SpeedTier = 0.f;
            break;
        }
    if (NYC && NYC->IsBossDefinition(Zombie.ZombieData))
    {
        ++BossesReleased;
        if (!IsBossAlive())
            LeadBoss = &Zombie;
        UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_BOSS round=%d boss=%s released=%d pending=%d kills=%d quota=%d"), Wave,
               *GetNameSafe(Zombie.ZombieData), BossesReleased, PendingBosses.Num(), GetZombiesKilledThisWave(),
               RoundQuota);
    }
    if (Director)
        Director->OnSpawned(Zombie, bVendorSpawn);
    if (bVendorSpawn && !bAdditiveSpawn)
        ++SpawnedThisRound;
}

void AHoverNYCSurvivalGameMode::BeginGameOver()
{
    if (bGameOver)
        return;
    bGameOver = true;
    // Section 2 Â§5 decision 3: the vendor HandleGameOver and OnPlayerHealthChanged are private, so
    // the mode owns the sequence. Zombies stop at once, the 2 s slow-motion death cam runs at this
    // mode's own dilation (the vendor's 0.001 would freeze it), then FinishDeathCam reaches the
    // vendor game-over path (death widget, button bindings, RestartLevel policy) by name, with
    // OpenLevel(RestartLevelName) as the fallback. No plugin edit.
    StopAllZombies();
    if (Director)
        Director->EndRound();
    bAmbienceActive = false;
    StopAmbience(NYC ? NYC->AmbienceFadeSeconds : 0.f);
    UWorld *World = GetWorld();
    const float Dilation = .3f;
    UGameplayStatics::SetGlobalTimeDilation(World, Dilation);
    // Timer delays are world seconds: two real seconds at the death-cam dilation.
    World->GetTimerManager().SetTimer(DeathCamTimer, this, &AHoverNYCSurvivalGameMode::FinishDeathCam, 2.f * Dilation,
                                      false);
    UE_LOG(LogTemp, Display, TEXT("HOVER_NYC_GAMEOVER round=%d kills=%d"), GetCurrentWave(), GetTotalZombiesKilled());
}

void AHoverNYCSurvivalGameMode::FinishDeathCam()
{
    UWorld *World = GetWorld();
    UGameplayStatics::SetGlobalTimeDilation(World, 1.f);
    // OnPlayerHealthChanged(0, Max) sets the vendor GameOver state and runs HandleGameOver. Both are
    // private UFUNCTIONs, so they are reached through reflection, as HoverTestController already does.
    if (UFunction *Function = FindFunction(TEXT("OnPlayerHealthChanged")))
    {
        struct FParams
        {
            float NewValue;
            float MaxValue;
        } Params{0.f, GetPlayerMaxHealth()};
        ProcessEvent(Function, &Params);
        return;
    }
    FName Level = WaveSettings ? WaveSettings->RestartLevelName : NAME_None;
    if (Level.IsNone())
    {
        FString Map = World->GetMapName();
        Map.RemoveFromStart(World->StreamingLevelsPrefix);
        Level = FName(*Map);
    }
    UGameplayStatics::OpenLevel(World, Level);
}

bool AHoverNYCSurvivalGameMode::RelocateZombie(AHoverCyberZombie &Zombie)
{
    if (!Director || !Director->RelocateZombie(Zombie))
        return false;
    if (auto *NYCZombie = Cast<AHoverNYCZombie>(&Zombie))
        NYCZombie->ReleaseCrowdClaims();
    return true;
}
