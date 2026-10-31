#include "HoverGunFeel.h"
#include "Animation/AnimSequence.h"
#include "GameFramework/ForceFeedbackEffect.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "NiagaraSystem.h"
#include "Sound/SoundBase.h"
#include "UObject/Package.h"

namespace
{
TArray<FVector2D> GunFeelKeys(std::initializer_list<FVector2D> Values)
{
    return TArray<FVector2D>(Values);
}
FHoverRumbleCurve GunFeelLightFireRumble()
{
    FHoverRumbleCurve Curve;
    Curve.LeftLarge = GunFeelKeys({{0.f, .45f}, {.04f, .3f}, {.07f, 0.f}});
    Curve.RightSmall = GunFeelKeys({{0.f, .9f}, {.04f, 0.f}});
    return Curve;
}
FHoverRumbleCurve GunFeelHeavyFireRumble()
{
    FHoverRumbleCurve Curve;
    Curve.LeftLarge = GunFeelKeys({{0.f, .8f}, {.08f, .5f}, {.2f, 0.f}});
    Curve.RightLarge = Curve.LeftLarge;
    return Curve;
}
TSoftObjectPtr<UNiagaraSystem> GunFeelTrail(const TCHAR *Name)
{
    return TSoftObjectPtr<UNiagaraSystem>(
        FSoftObjectPath(FString::Printf(TEXT("/Game/ArrowTrail/FX/%s.%s"), Name, Name)));
}
// Folder is relative to /Game/HoverPrototype/Audio/NYC, for example Weapons/Rifle1.
TSoftObjectPtr<USoundBase> GunFeelSound(const TCHAR *Folder, const FString &Name)
{
    return TSoftObjectPtr<USoundBase>(
        FSoftObjectPath(FString::Printf(TEXT("/Game/HoverPrototype/Audio/NYC/%s/%s.%s"), Folder, *Name, *Name)));
}
// Stem_001..Count; most NYC weapon folders carry four shot variations.
TArray<TSoftObjectPtr<USoundBase>> GunFeelSoundPool(const TCHAR *Folder, const TCHAR *Stem, int32 Count = 4)
{
    TArray<TSoftObjectPtr<USoundBase>> Pool;
    for (int32 Shot = 1; Shot <= Count; ++Shot)
        Pool.Add(GunFeelSound(Folder, FString::Printf(TEXT("%s_%03d"), Stem, Shot)));
    return Pool;
}
// Stem_1..Count under an absolute /Game folder (the Etherion zombie pack numbers without zero padding).
TArray<TSoftObjectPtr<USoundBase>> GunFeelSoundPoolAt(const TCHAR *Folder, const TCHAR *Stem, int32 Count)
{
    TArray<TSoftObjectPtr<USoundBase>> Pool;
    for (int32 Index = 1; Index <= Count; ++Index)
    {
        const FString Name = FString::Printf(TEXT("%s_%d"), Stem, Index);
        Pool.Add(TSoftObjectPtr<USoundBase>(
            FSoftObjectPath(FString::Printf(TEXT("%s/%s.%s"), Folder, *Name, *Name))));
    }
    return Pool;
}
USoundBase *GunFeelPick(const TArray<TSoftObjectPtr<USoundBase>> &Pool, int32 &InOutLast)
{
    const int32 Count = Pool.Num();
    if (Count == 0)
        return nullptr;
    int32 Index = FMath::RandRange(0, Count - 1);
    if (Count > 1 && Index == InOutLast)
        Index = (Index + FMath::RandRange(1, Count - 1)) % Count;
    InOutLast = Index;
    return Pool[Index].LoadSynchronous();
}
} // namespace

FHoverGunFeelTier::FHoverGunFeelTier()
{
    FireRumble = GunFeelLightFireRumble();
    TailSound = TSoftObjectPtr<USoundBase>(
        FSoftObjectPath(TEXT("/Game/HoverPrototype/Audio/A_Cyberpunk_Rifle1_Tail.A_Cyberpunk_Rifle1_Tail")));
    TPFireAction = TSoftObjectPtr<UAnimSequence>(
        FSoftObjectPath(TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/MM_Rifle_Fire.MM_Rifle_Fire")));
}

const FHoverGunFeelTier &FHoverGunFeelTier::Legacy()
{
    static const FHoverGunFeelTier Tier = [] {
        FHoverGunFeelTier T;
        T.Pierce = 0;
        T.Tracer.Reset();
        T.bTracerColor = true;
        T.bTracerColorAB = false;
        T.TracerColor = T.TracerColorB = FLinearColor(1.f, .65f, .25f);
        T.TracerLength = 55.f;
        T.TracerWidth = .014f;
        T.TracerSpeed = 90000.f;
        T.TracerMinDuration = .06f;
        T.TracerMaxDuration = .09f;
        T.TracerLifetime = .06f;
        T.TracerTrailSize = 1.4f;
        T.TracerEmissive = 2.f;
        T.MinTracerDistance = 0.f;
        T.FireShake = nullptr;
        T.ShakeScale = 0.f;
        T.bOverrideRecoil = true;
        T.RecoilKick = FVector2D::ZeroVector;
        T.RecoilDebtCap = 0.f;
        T.SoundVolume = .60f;
        T.SoundPitch = 1.f;
        T.SoundPitchJitter = .04f;
        T.FireSoundPool.Reset();
        T.TailSound.Reset();
        T.TailSoundPool.Reset();
        T.FireRumble = FHoverRumbleCurve(); // Legacy fire keeps PlayDynamicForceFeedback(.18, .06).
        T.MuzzleLightIntensity = 0.f;
        T.MuzzleFlashSeconds = .09f;
        T.TPFireAction.Reset();
        T.KillTimeDilation = 1.f;
        T.KillHitStopSeconds = 0.f;
        T.bKillFlash = false;
        return T;
    }();
    return Tier;
}

USoundBase *FHoverGunFeelTier::PickFireSound(int32 &InOutLast) const
{
    return GunFeelPick(FireSoundPool, InOutLast);
}

USoundBase *FHoverGunFeelTier::PickTailSound(int32 &InOutLast) const
{
    return TailSoundPool.IsEmpty() ? TailSound.LoadSynchronous() : GunFeelPick(TailSoundPool, InOutLast);
}

UHoverGunFeel::UHoverGunFeel()
{
    HitRumble.RightSmall = GunFeelKeys({{0.f, .35f}, {.04f, 0.f}});
    HitRumble.LeftSmall = HitRumble.RightSmall;
    HeadshotRumble.RightSmall = GunFeelKeys({{0.f, .6f}, {.05f, 0.f}});
    HeadshotRumble.RightLarge = GunFeelKeys({{0.f, .3f}, {.06f, 0.f}});
    KillRumble.LeftLarge = GunFeelKeys({{0.f, .7f}, {.06f, .5f}, {.14f, 0.f}});
    KillRumble.RightLarge = KillRumble.LeftLarge;
    KillHeadshotRumble.LeftLarge = GunFeelKeys({{0.f, .91f}, {.06f, .65f}, {.14f, 0.f}});
    KillHeadshotRumble.RightLarge = KillHeadshotRumble.LeftLarge;
    HitConfirmSoundPool = GunFeelSoundPool(TEXT("Gameplay/HitMetalWound"), TEXT("A_Hit_MetalWound"), 8);
    // Audio pass 2026-10-31: melee and footsteps from the sets already imported on 2026-10-29.
    MeleeSwingSoundPool = GunFeelSoundPoolAt(TEXT("/Game/Zombie/Sound/Whoosh"), TEXT("S_Whoosh"), 10);
    MeleeHitSoundPool = GunFeelSoundPool(TEXT("Gameplay/KatanaCut"), TEXT("A_Katana_Cut"), 4);
    FootstepWalkConcrete = GunFeelSoundPool(TEXT("Player/Footsteps/Walk_Concrete"), TEXT("A_WW2_Walk_Concrete"), 8);
    FootstepWalkDirt = GunFeelSoundPool(TEXT("Player/Footsteps/Walk_Dirt"), TEXT("A_WW2_Walk_Dirt"), 8);
    FootstepWalkPuddle = GunFeelSoundPool(TEXT("Player/Footsteps/Walk_Puddle"), TEXT("A_WW2_Walk_Puddle"), 8);
    FootstepRunConcrete = GunFeelSoundPool(TEXT("Player/Footsteps/Run_Concrete"), TEXT("A_WW2_Run_Concrete"), 8);
    FootstepRunPuddle = GunFeelSoundPool(TEXT("Player/Footsteps/Run_Puddle"), TEXT("A_WW2_Run_Puddle"), 8);
}

USoundBase *UHoverGunFeel::PickHitConfirmSound(int32 &InOutLast) const
{
    return GunFeelPick(HitConfirmSoundPool, InOutLast);
}

USoundBase *UHoverGunFeel::PickMeleeSwingSound(int32 &InOutLast) const
{
    return GunFeelPick(MeleeSwingSoundPool, InOutLast);
}

USoundBase *UHoverGunFeel::PickMeleeHitSound(int32 &InOutLast) const
{
    return GunFeelPick(MeleeHitSoundPool, InOutLast);
}

USoundBase *UHoverGunFeel::PickFootstep(bool bRun, int32 Surface, int32 &InOutLast) const
{
    const TArray<TSoftObjectPtr<USoundBase>> &Pool =
        bRun ? (Surface == 2 ? FootstepRunPuddle : FootstepRunConcrete)
             : (Surface == 2 ? FootstepWalkPuddle : Surface == 1 ? FootstepWalkDirt : FootstepWalkConcrete);
    return GunFeelPick(Pool, InOutLast);
}

const FHoverGunFeelTier &UHoverGunFeel::Find(const UZE_WeaponDefinition *Definition) const
{
    if (!Definition)
        return Default;
    const FName Key = Definition->GetFName();
    if (const FHoverGunFeelTier *Tier = Tiers.Find(Key))
        return *Tier;
    if (!ReportedMissing.Contains(Key))
    {
        ReportedMissing.Add(Key);
        UE_LOG(LogTemp, Warning, TEXT("HOVER_RIFLE_TIER missing %s"), *Key.ToString());
    }
    return Default;
}

const UHoverGunFeel *UHoverGunFeel::BuiltIn()
{
    static UHoverGunFeel *Feel = nullptr;
    if (Feel)
        return Feel;
    Feel = NewObject<UHoverGunFeel>(GetTransientPackage());
    Feel->AddToRoot(); // Never collected: tiers and rumble curves are read for the whole session.
    // Until the Ballista DAs are retuned, the built-in table owns the per-shot view kick.
    Feel->Default.bOverrideRecoil = true;
    Feel->Default.RecoilKick = FVector2D(.35f, .15f);
    Feel->Default.RecoilRecovery = 10.f;
    struct FRow
    {
        const TCHAR *Key;
        int32 PaP, Pierce;
        const TCHAR *Tracer;
        float Shake, Pitch;
        bool bHeavy;
        // Audio/NYC/Weapons/<Sound>/A_Cyberpunk_<Sound>_001..004 plus A_Cyberpunk_<Sound>_Tail.
        const TCHAR *Sound;
    };
    const FRow Rows[] = {
        {TEXT("DA_AFS_Ballista"), 0, 0, TEXT("NS_ArrowTrail_Basic_02"), 1.f, 1.f, false, TEXT("Rifle1")},
        {TEXT("DA_AFS_Ballista_2"), 1, 0, TEXT("NS_ArrowTrail_Fire"), 1.05f, .97f, false, TEXT("Rifle1")},
        {TEXT("DA_AFS_Ballista_3"), 2, 0, TEXT("NS_ArrowTrail_Ice"), 1.10f, .94f, false, TEXT("Rifle1")},
        {TEXT("DA_AFS_Ballista_4"), 3, 0, TEXT("NS_ArrowTrail_Holy"), 1.20f, .90f, false, TEXT("Rifle2")},
        {TEXT("DA_AFS_Ballista_5"), 3, 0, TEXT("NS_ArrowTrail_Magic"), 1.60f, .85f, true, TEXT("Rifle2")},
        {TEXT("DA_NYC_Ballista"), 0, 0, TEXT("NS_ArrowTrail_Basic_02"), 1.f, 1.f, false, TEXT("Rifle1")},
        {TEXT("DA_NYC_Ballista_2"), 1, 0, TEXT("NS_ArrowTrail_Fire"), 1.05f, .97f, false, TEXT("Rifle1")},
        {TEXT("DA_NYC_Ballista_3"), 2, 1, TEXT("NS_ArrowTrail_Ice"), 1.10f, .94f, false, TEXT("Rifle1")},
        {TEXT("DA_NYC_Ballista_4"), 3, 2, TEXT("NS_ArrowTrail_Holy"), 1.20f, .90f, false, TEXT("Rifle2")},
    };
    for (const FRow &Row : Rows)
    {
        FHoverGunFeelTier Tier = Feel->Default;
        Tier.PaP = Row.PaP;
        Tier.Pierce = Row.Pierce;
        Tier.Tracer = GunFeelTrail(Row.Tracer);
        const bool Basic = FCString::Strcmp(Row.Tracer, TEXT("NS_ArrowTrail_Basic_02")) == 0;
        const bool Magic = FCString::Strcmp(Row.Tracer, TEXT("NS_ArrowTrail_Magic")) == 0;
        Tier.bTracerColor = Basic;
        Tier.bTracerColorAB = Magic;
        if (Magic)
        {
            Tier.TracerColor = FLinearColor(.6f, .3f, 1.f);
            Tier.TracerColorB = FLinearColor(.25f, .8f, 1.f);
        }
        Tier.ShakeScale = Row.Shake;
        Tier.SoundPitch = Row.Pitch;
        if (Row.bHeavy)
            Tier.FireRumble = GunFeelHeavyFireRumble();
        const FString Folder = FString::Printf(TEXT("Weapons/%s"), Row.Sound);
        Tier.FireSoundPool = GunFeelSoundPool(*Folder, *FString::Printf(TEXT("A_Cyberpunk_%s"), Row.Sound));
        Tier.TailSound = GunFeelSound(*Folder, FString::Printf(TEXT("A_Cyberpunk_%s_Tail"), Row.Sound));
        // Audio pass 2026-10-31 ("the gun sounds, terrible"): the cyberpunk rifle recordings peak at -15 dBFS
        // with a 30-130 ms attack, so every Ballista tier (the M4A1 rig) fires the WW2 machine gun set instead
        // (-8 dBFS, 5-14 ms attack, 8 shots + 4 tails), louder, tail every other shot. Pitch per tier stays.
        Tier.FireSoundPool = GunFeelSoundPool(TEXT("Weapons/WW2_MachineGun"), TEXT("A_WW2_MachineGun_Fire"), 8);
        Tier.TailSound.Reset();
        Tier.TailSoundPool = GunFeelSoundPool(TEXT("Weapons/WW2_MachineGun"), TEXT("A_WW2_MachineGun_Tail"), 4);
        Tier.TailEveryN = 2;
        Tier.SoundVolume = 1.4f;
        Feel->Tiers.Add(FName(Row.Key), Tier);
    }
    // M16 rifles get the WW2 machine gun, the sidearm the cyberpunk pistol; Shotgun and Sniper are staged
    // under plain keys for the later NYC weapons. A null TailStem means no tail was recorded.
    struct FPoolRow
    {
        const TCHAR *Key, *Folder, *Stem;
        int32 Count;
        const TCHAR *TailStem;
        int32 TailCount;
    };
    const TCHAR *MachineGun = TEXT("Weapons/WW2_MachineGun");
    const FPoolRow PoolRows[] = {
        {TEXT("DA_Weapon_Rifle_001"), MachineGun, TEXT("A_WW2_MachineGun_Fire"), 8, TEXT("A_WW2_MachineGun_Tail"), 4},
        {TEXT("DA_Weapon_Rifle_002"), MachineGun, TEXT("A_WW2_MachineGun_Fire"), 8, TEXT("A_WW2_MachineGun_Tail"), 4},
        {TEXT("DA_Weapon_Rifle_003"), MachineGun, TEXT("A_WW2_MachineGun_Fire"), 8, TEXT("A_WW2_MachineGun_Tail"), 4},
        {TEXT("DA_Weapon_Rifle_004"), MachineGun, TEXT("A_WW2_MachineGun_Fire"), 8, TEXT("A_WW2_MachineGun_Tail"), 4},
        {TEXT("DA_Weapon_Rifle_005"), MachineGun, TEXT("A_WW2_MachineGun_Fire"), 8, TEXT("A_WW2_MachineGun_Tail"), 4},
        // The revolver rig (EM_08): the cyberpunk pistol set attacks in 33-49 ms and reads as a pop; the sniper
        // set (5-8 ms attack) pitched up is a crack. Audio pass 2026-10-31.
        {TEXT("DA_Weapon_Pistol_001"), TEXT("Weapons/Sniper"), TEXT("A_Cyberpunk_Sniper"), 4, nullptr, 0},
        {TEXT("DA_NYC_Pistol"), TEXT("Weapons/Sniper"), TEXT("A_Cyberpunk_Sniper"), 4, nullptr, 0},
        {TEXT("Shotgun"), TEXT("Weapons/Shotgun"), TEXT("A_Cyberpunk_Shotgun"), 4, nullptr, 0},
        {TEXT("Sniper"), TEXT("Weapons/WW2_Rifle"), TEXT("A_WW2_Rifle"), 4, nullptr, 0},
    };
    for (const FPoolRow &Row : PoolRows)
    {
        FHoverGunFeelTier Tier = Feel->Default;
        Tier.FireSoundPool = GunFeelSoundPool(Row.Folder, Row.Stem, Row.Count);
        Tier.TailSound.Reset();
        if (Row.TailStem)
            Tier.TailSoundPool = GunFeelSoundPool(Row.Folder, Row.TailStem, Row.TailCount);
        Tier.SoundVolume = 1.35f;
        if (FCString::Strcmp(Row.Key, TEXT("DA_Weapon_Pistol_001")) == 0 ||
            FCString::Strcmp(Row.Key, TEXT("DA_NYC_Pistol")) == 0)
            Tier.SoundPitch = 1.22f; // revolver crack
        else if (FCString::Strcmp(Row.Key, TEXT("DA_Weapon_Rifle_002")) == 0)
            Tier.SoundPitch = 1.12f; // the SMG rig (EM_21) on the machine-gun set, a touch lighter
        Feel->Tiers.Add(FName(Row.Key), Tier);
    }
    return Feel;
}

UForceFeedbackEffect *HoverHaptics::Build(UObject *Outer, const FHoverRumbleCurve &Curve)
{
    if (Curve.LeftLarge.IsEmpty() && Curve.LeftSmall.IsEmpty() && Curve.RightLarge.IsEmpty() &&
        Curve.RightSmall.IsEmpty())
        return nullptr;
    auto *Effect = NewObject<UForceFeedbackEffect>(Outer ? Outer : GetTransientPackage());
    Effect->ChannelDetails.Reset();
    float Duration = 0;
    auto AddChannel = [&](const TArray<FVector2D> &Values, int32 Channel) {
        if (Values.IsEmpty())
            return;
        FForceFeedbackChannelDetails Details;
        Details.bAffectsLeftLarge = Channel == 0;
        Details.bAffectsLeftSmall = Channel == 1;
        Details.bAffectsRightLarge = Channel == 2;
        Details.bAffectsRightSmall = Channel == 3;
        FRichCurve *Rich = Details.Curve.GetRichCurve();
        for (const FVector2D &Key : Values)
        {
            Rich->AddKey(Key.X, Key.Y);
            Duration = FMath::Max(Duration, float(Key.X));
        }
        Effect->ChannelDetails.Add(Details);
    };
    AddChannel(Curve.LeftLarge, 0);
    AddChannel(Curve.LeftSmall, 1);
    AddChannel(Curve.RightLarge, 2);
    AddChannel(Curve.RightSmall, 3);
    // A code-built effect never runs the editor recompute; a zero duration would stop at once.
    Effect->Duration = Duration;
    return Effect;
}

UHoverShakePattern::UHoverShakePattern(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer) {}

void UHoverShakePattern::GetShakePatternInfoImpl(FCameraShakeInfo &OutInfo) const
{
    // Custom: this pattern applies its own blend envelope and reports when it is finished.
    OutInfo.Duration = FCameraShakeDuration::Custom(Duration);
}

void UHoverShakePattern::StartShakePatternImpl(const FCameraShakePatternStartParams &Params)
{
    Age = 0;
    for (float &Seed : Seeds)
        Seed = FMath::FRandRange(0.f, 1000.f);
}

void UHoverShakePattern::UpdateShakePatternImpl(const FCameraShakePatternUpdateParams &Params,
                                                FCameraShakePatternUpdateResult &OutResult)
{
    Age += Params.DeltaTime;
    const float In = BlendInTime > 0 ? FMath::Clamp(Age / BlendInTime, 0.f, 1.f) : 1.f;
    const float Out = BlendOutTime > 0 ? FMath::Clamp((Duration - Age) / BlendOutTime, 0.f, 1.f) : 1.f;
    const float Weight = In * Out;
    auto Noise = [this, Weight](const FVector2D &Axis, int32 Index) {
        return float(Axis.X) * Weight * FMath::PerlinNoise1D(Seeds[Index] + Age * float(Axis.Y));
    };
    OutResult.Rotation = FRotator(Noise(Pitch, 0), Noise(Yaw, 1), Noise(Roll, 2));
    OutResult.FOV = Noise(FOV, 3);
    OutResult.Location = FVector::ForwardVector * Noise(X, 4);
}

bool UHoverShakePattern::IsFinishedImpl() const
{
    return Age >= Duration;
}

UHoverFireShake::UHoverFireShake(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer)
{
    bSingleInstance = false; // 8 shots/s overlap one or two .12 s shakes.
    SetRootShakePattern(CreateDefaultSubobject<UHoverShakePattern>(TEXT("RootShakePattern")));
}

UHoverHurtShake::UHoverHurtShake(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer)
{
    bSingleInstance = false;
    auto *Pattern = CreateDefaultSubobject<UHoverShakePattern>(TEXT("RootShakePattern"));
    Pattern->Duration = .2f;
    Pattern->BlendOutTime = .12f;
    Pattern->Pitch = FVector2D(1.2f, 16.f);
    Pattern->Yaw = FVector2D::ZeroVector;
    Pattern->Roll = FVector2D(1.5f, 12.f);
    Pattern->FOV = FVector2D::ZeroVector;
    Pattern->X = FVector2D::ZeroVector;
    SetRootShakePattern(Pattern);
}

UHoverBlastShake::UHoverBlastShake(const FObjectInitializer &ObjectInitializer) : Super(ObjectInitializer)
{
    bSingleInstance = false;
    auto *Pattern = CreateDefaultSubobject<UHoverShakePattern>(TEXT("RootShakePattern"));
    Pattern->Duration = .45f;
    Pattern->BlendOutTime = .3f;
    Pattern->Pitch = FVector2D(2.f, 12.f);
    Pattern->Yaw = FVector2D(.6f, 10.f);
    Pattern->Roll = FVector2D(.6f, 9.f);
    Pattern->FOV = FVector2D(2.f, 8.f);
    Pattern->X = FVector2D(2.f, 14.f);
    SetRootShakePattern(Pattern);
}
