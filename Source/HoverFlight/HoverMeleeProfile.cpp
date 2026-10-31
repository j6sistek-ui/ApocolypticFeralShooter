#include "HoverMeleeProfile.h"
#include "Animation/AnimSequence.h"
#include "UObject/SoftObjectPath.h"

namespace
{
TSoftObjectPtr<UAnimSequence> MeleeProfileClip(const TCHAR *Path)
{
    return TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(Path));
}
// Scripts/AuthorSpear.py writes the retargeted pack clips here (UE4 mannequin -> the CLS driver's UE5 skeleton).
const TCHAR *const MeleeProfileSpearAnims = TEXT("/Game/HoverPrototype/Spear/Anims/");
TSoftObjectPtr<UAnimSequence> SpearClip(const TCHAR *Name)
{
    const FString Path = FString(MeleeProfileSpearAnims) + Name + TEXT(".") + Name;
    return TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(Path));
}
FHoverMeleeStrike SpearStrike(FName Name, const TCHAR *ClipName, float Duration, TArray<float> Sweeps, float Reach,
                              float Radius, float DamageScale, float HitStop, float ChainOpen, float ChainAt)
{
    FHoverMeleeStrike S;
    S.Name = Name;
    S.Clip = SpearClip(ClipName);
    S.Duration = Duration;
    S.SweepTimes = MoveTemp(Sweeps);
    S.Reach = Reach;
    S.ReachPad = 20.f;
    S.Radius = Radius;
    S.StartHeight = 25.f;
    S.DamageScale = DamageScale;
    S.HitStopSeconds = HitStop;
    S.HitStopDilation = .05f;
    S.ChainOpenSeconds = ChainOpen;
    S.ChainAtSeconds = ChainAt;
    return S;
}
} // namespace

FHoverMeleeProfile FHoverMeleeProfile::Katana()
{
    FHoverMeleeProfile P;
    P.LogTag = TEXT("KATANA");
    P.HudName = TEXT("KATANA");
    FHoverMeleeStrike &S = P.Light.AddDefaulted_GetRef();
    S.Name = TEXT("Slash");
    S.Clip = MeleeProfileClip(TEXT("/Game/HoverPrototype/Animations/QA_Katana.QA_Katana"));
    S.ViewClip = MeleeProfileClip(TEXT("/Game/HoverPrototype/Animations/QA_KatanaView.QA_KatanaView"));
    S.Duration = .8f;
    S.SweepTimes = {.22f, .30f, .38f, .48f};
    S.Reach = 0.f;    // DA_AFS_Melee MeleeRange
    S.ReachPad = 30.f;
    S.Radius = 0.f;   // max(50, MeleeRadius x 2.5)
    S.StartHeight = 15.f;
    return P;
}

FHoverMeleeProfile FHoverMeleeProfile::SpearDefaults()
{
    // Longer and narrower than the katana (reach 180 cm with a 50 cm sphere): the jab and thrust sweep a 24-26 cm
    // sphere straight down the spear line to 240-270 cm, the swing walks a 30 cm sphere across +-30 deg only.
    // AuthorSpear.py replaces the sweep times, arc direction and reach with values measured on the clips.
    FHoverMeleeProfile P;
    P.LogTag = TEXT("SPEAR");
    P.HudName = TEXT("SPEAR");
    P.Light.Add(SpearStrike(TEXT("Jab"), TEXT("AS_Spear_Jab"), .55f, {.16f, .22f, .28f}, 240.f, 24.f, .8f, .05f, .18f,
                            .40f));
    P.Light.Add(SpearStrike(TEXT("Thrust"), TEXT("AS_Spear_Thrust"), .70f, {.24f, .30f, .36f, .42f}, 270.f, 26.f, 1.1f,
                            .07f, .25f, .55f));
    FHoverMeleeStrike Swing = SpearStrike(TEXT("Swing"), TEXT("AS_Spear_Swing"), .85f, {.26f, .33f, .40f, .47f, .54f},
                                          220.f, 30.f, .9f, .06f, .40f, .80f);
    Swing.ArcStartYaw = 30.f;
    Swing.ArcEndYaw = -30.f;
    P.Light.Add(Swing);
    P.ComboResetSeconds = .6f;
    P.bHasHeavy = true;
    P.Heavy = SpearStrike(TEXT("Heavy"), TEXT("AS_Spear_Heavy_P4Mid"), .95f, {.40f, .47f, .54f, .61f}, 300.f, 28.f,
                          1.f, .12f, 0.f, 0.f);
    P.Heavy.WindupFraction = .35f;
    P.ChargeThreshold = .22f;
    P.FullChargeSeconds = .9f;
    P.MaxChargeHoldSeconds = 3.f;
    P.HeavyMinScale = 1.6f;
    P.HeavyMaxScale = 3.f;
    P.StanceLoop = SpearClip(TEXT("AS_Spear_Stance"));
    P.bTwoHandGrip = true;
    P.bTipTowardLeftHand = true;
    P.bFlipMeshTip = false;
    P.GripFromButt = .3f;
    P.bCancelWhenInactive = true;
    P.bPierce = true;
    return P;
}

FHoverMeleeProfile FHoverMeleeProfile::LoadSpear()
{
    if (const auto *Asset = LoadObject<UHoverMeleeProfileAsset>(
            nullptr, TEXT("/Game/HoverPrototype/Spear/DA_SpearProfile.DA_SpearProfile"), nullptr, LOAD_NoWarn))
    {
        UE_LOG(LogTemp, Display, TEXT("HOVER_SPEAR_PROFILE source=asset light=%d heavy=%d stance=%d"),
               Asset->Profile.Light.Num(), Asset->Profile.bHasHeavy, !Asset->Profile.StanceLoop.IsNull());
        return Asset->Profile;
    }
    FHoverMeleeProfile P = SpearDefaults();
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPEAR_PROFILE source=defaults light=%d heavy=%d stance=%d"), P.Light.Num(),
           P.bHasHeavy, !P.StanceLoop.IsNull());
    return P;
}

void UHoverMeleeProfileAsset::ResetToSpearDefaults()
{
    Modify();
    Profile = FHoverMeleeProfile::SpearDefaults();
    MarkPackageDirty();
}
