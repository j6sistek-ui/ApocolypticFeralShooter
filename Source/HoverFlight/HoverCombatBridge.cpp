#include "HoverCombatBridge.h"
#include "HoverPilot.h"
#include "HoverLocomotionBridge.h"
#include "HoverAnimInstance.h"
#include "HoverCyberCity.h"
#include "HoverGunFeel.h"
#include "HoverEffects.h"
#include "Kismet/GameplayStatics.h"
#include "Inventory/ZE_InventoryComponent.h"
#include "Inventory/ZE_ItemDefinition.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Inventory/ZE_AmmoDefinition.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "Zombies/ZE_ZombieCharacter.h"
#include "Weapons/ZE_WeaponComponent.h"
#include "Interaction/ZE_InteractionTraceComponent.h"
#include "Interaction/ZE_InteractableInterface.h"
#include "UI/ZE_InventoryWidgetBase.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimMontage.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerInput.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "InputCoreTypes.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/AnalogCursor.h"
#include "HAL/PlatformApplicationMisc.h"

namespace
{
class FHoverInventoryCursor : public FAnalogCursor
{
  public:
    virtual void Tick(float DT, FSlateApplication &App, TSharedRef<ICursor> Cursor) override
    {
        if (FPlatformApplicationMisc::IsThisApplicationForeground())
            FAnalogCursor::Tick(DT, App, Cursor);
        else
            ClearAnalogValues();
    }

  protected:
    virtual bool IsRelevantInput(const FInputEvent &Event) const override
    {
        return FPlatformApplicationMisc::IsThisApplicationForeground() && FAnalogCursor::IsRelevantInput(Event);
    }
};
} // namespace

AHoverCyberRifle::AHoverCyberRifle()
{
    // The vendor ticks only WITH_EDITOR. Packaged builds keep that default and tick only once the
    // pilot's opt-in gun feel enables it (PlayFireAnimation), so gate-off packaged recoil is unchanged.
    PrimaryActorTick.bCanEverTick = true;
#if !WITH_EDITOR
    PrimaryActorTick.bStartWithTickEnabled = false;
#endif
}
void AHoverCyberRifle::Tick(float DT)
{
    const auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const bool Enhanced = Pilot && Pilot->bEnhancedGunFeel;
    // Before Super: HandleFire's vendor kick must not reach the view; AHoverPilot applies the recoil.
    if (Enhanced)
        CurrentRecoil = TargetRecoil = FRotator::ZeroRotator;
    Super::Tick(DT);
    // Vendor spread recovers only after release; a held trigger blooms back at SpreadRecovery / 6.
    if (Enhanced && bIsFiring && WeaponDefinition)
        CurrentSpread = FMath::FInterpConstantTo(CurrentSpread, WeaponDefinition->CombatStats.BaseSpread, DT,
                                                 WeaponDefinition->CombatStats.SpreadRecovery / 6.f);
}
const FHoverGunFeelTier &AHoverCyberRifle::GetFeelTier() const
{
    const auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    if (!Pilot || !Pilot->bEnhancedGunFeel)
        return FHoverGunFeelTier::Legacy();
    return Pilot->GetGunFeel()->Find(WeaponDefinition);
}
float AHoverCyberRifle::GetEffectiveFireRate() const
{
    return (WeaponDefinition ? WeaponDefinition->FireRate : 8.f) * FMath::Max(.1f, FireRateScale);
}
float AHoverCyberRifle::GetEffectiveSpreadDegrees() const
{
    const auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const float AimAlpha = Pilot && Pilot->bEnhancedGunFeel ? FMath::Clamp(Pilot->WeaponAimAlpha, 0.f, 1.f) : 0.f;
    return CurrentSpread * FMath::Lerp(1.f, .35f, AimAlpha);
}
void AHoverCyberRifle::StartFire()
{
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    // Dry fire is a trigger pull on an empty magazine. The vendor base (and the cadence path below)
    // turns it into Reload() while reserve ammo exists, and the rigged rifle's Reload clip starts
    // bolt locked back; with nothing left to load it plays the click (GunDryFire) instead.
    const bool EmptyPull =
        !bIsFiring && !bIsReloading && WeaponDefinition && WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0;
    if (!Pilot || !Pilot->bEnhancedGunFeel)
    {
        Super::StartFire();
        if (EmptyPull && Pilot && !bIsReloading)
            Pilot->PlayGunDryFire();
        return;
    }
    // Cadence cap: the vendor fires at once on every StartFire, so tapping beat the 8/s timer and
    // semi weapons (Sidearm 6/s, Heavy 4/s) had no cadence at all. The same gates as the vendor
    // (firing, reloading, empty clip reloads), then the interval since the last shot is honoured.
    if (bIsFiring || bIsReloading || !WeaponDefinition)
        return;
    if (WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0)
    {
        Reload();
        if (!bIsReloading)
            Pilot->PlayGunDryFire();
        return;
    }
    const float Interval = 1.f / FMath::Max(.1f, GetEffectiveFireRate());
    const float Wait = LastShotTime + Interval - GetWorld()->GetTimeSeconds();
    FTimerManager &Timers = GetWorldTimerManager();
    bIsFiring = true;
    if (WeaponDefinition->bAutomatic)
    {
        if (Wait <= 0.f)
            HandleFire();
        Timers.SetTimer(FireTimerHandle, this, &AHoverCyberRifle::HandleFire, Interval, true,
                        Wait <= 0.f ? Interval : Wait);
    }
    else if (Wait <= 0.f)
        HandleFire();
    else
        Timers.SetTimer(BufferedShot, this, &AHoverCyberRifle::HandleFire, Wait, false); // buffered semi press
}
void AHoverCyberRifle::HandleFire()
{
    // A buffered or looping shot never lands on a reloading or holstered weapon.
    if (bIsReloading || !bIsEquipped || !OwnerPawn)
    {
        StopFire();
        return;
    }
    if (WeaponDefinition && (!WeaponDefinition->bUsesAmmo || CurrentClipAmmo > 0))
        LastShotTime = GetWorld()->GetTimeSeconds();
    // Vendor: ammo, PlayFireAnimation, PerformLineTrace, spread per shot, StopFire at 0.
    Super::HandleFire();
}
void AHoverCyberRifle::PerformLineTrace()
{
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && WeaponDefinition)
        Pilot->FireShot(WeaponDefinition->CombatStats.Damage, GetEffectiveSpreadDegrees(),
                        WeaponDefinition->CombatStats.Range, this);
}
void AHoverCyberRifle::OnEquipped_Implementation(APawn *NewOwnerPawn)
{
    Super::OnEquipped_Implementation(NewOwnerPawn);
    // Wall buys, pickups, quickbar cycling and the Pack-a-Punch swap all end in this equip, so the held
    // definition picks its rig here: its GunRigs key, else the DA's default rig, else the static Ballista.
    if (auto *Pilot = Cast<AHoverPilot>(NewOwnerPawn))
        Pilot->ApplyGunRig(Pilot->FindGunRig(WeaponDefinition));
    if (auto *Pilot = Cast<AHoverPilot>(NewOwnerPawn); Pilot && Pilot->Combat && Pilot->Combat->Inventory)
    {
        FZE_InventoryItemInstance Item;
        auto *Inventory = Pilot->Combat->Inventory.Get();
        if (Inventory->GetQuickbarItem(Inventory->GetActiveQuickbarSlot(), Item))
        {
            ItemId = Item.InstanceId;
            if (const int32 *Saved = Pilot->Combat->SavedMagazines.Find(ItemId))
                CurrentClipAmmo = FMath::Clamp(*Saved, 0, GetMagazineSize());
        }
    }
    if (auto *Pilot = Cast<AHoverPilot>(NewOwnerPawn))
    {
        // After the saved magazine is restored: an empty one leaves the bolt locked back after the rack.
        Pilot->SetGunEmpty(WeaponDefinition && WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0);
        Pilot->PlayGunChamber(); // Rigged rifle only: one cycle of the action per equip.
    }
}
void AHoverCyberRifle::OnUnequipped_Implementation(APawn *OldOwnerPawn)
{
    if (auto *Pilot = Cast<AHoverPilot>(OldOwnerPawn); Pilot && Pilot->Combat && ItemId.IsValid())
        Pilot->Combat->SavedMagazines.Add(ItemId, CurrentClipAmmo);
    CancelReload();
    GetWorldTimerManager().ClearTimer(BufferedShot);
    Super::OnUnequipped_Implementation(OldOwnerPawn);
}
void AHoverCyberRifle::PlayFireAnimation()
{
    // Existing Ballista presentation emits one flash/sound/tracer per vendor-approved shot.
    // Super is never called: it would add a second gunshot, a flash on the hidden weapon root,
    // and push FireMontage_TP into the Parkour/CLS body graph.
    const float Now = GetWorld()->GetTimeSeconds();
    LastFireAnimTime = Now;
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    // HandleFire calls this once per round actually fired, so the rigged rifle's bolt cycles on
    // every shot whatever TPFireEveryN skips on the body and whether or not the gun feel gate is on.
    // Automatic fire faster than the clip speeds the clip up so the bolt is home for the next round.
    // The vendor has already spent this round, so an empty clip here means it was the last one.
    if (Pilot && WeaponDefinition)
        Pilot->PlayGunFire(WeaponDefinition->bAutomatic ? 1.f / FMath::Max(.1f, GetEffectiveFireRate()) : 0.f,
                           WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0);
    if (!Pilot || !Pilot->bEnhancedGunFeel || !WeaponDefinition)
        return;
    if (!IsActorTickEnabled())
        SetActorTickEnabled(true); // Packaged builds: recoil/bloom handling in Tick.
    const FHoverGunFeelTier &Tier = GetFeelTier();
    // HandleFire calls this only for a round that is actually fired.
    Pilot->PlayFireShake(Tier, WeaponDefinition);
    // StopFire resets ShotsSinceLastAnim, so 0 marks the first shot of a burst.
    const bool BurstStart = ShotsSinceLastAnim == 0;
    const int32 EveryN = FMath::Max(1, WeaponDefinition->FireAnimEveryNShots);
    bool PlayMontage = BurstStart || ShotsSinceLastAnim >= EveryN;
    if (PlayMontage)
        ShotsSinceLastAnim = 0;
    ++ShotsSinceLastAnim;
    if (WeaponDefinition->MinFireAnimInterval > 0 && Now - LastFireMontageTime < WeaponDefinition->MinFireAnimInterval)
        PlayMontage = false;
    if (BurstStart)
        TPFireCounter = 0;
    const bool PlayReaction = TPFireCounter++ % FMath::Max(1, Tier.TPFireEveryN) == 0;
    if (bIsReloading || !Pilot->IsOnFoot())
        return;
    if (Pilot->IsThirdPersonView())
    {
        // Upper-body reaction; never cut a reload, hit react or Parkour action. Static Ballista only (design A1,
        // 2026-10-30): a driver montage drops the aim layer and the support IK, so the left hand followed the
        // retargeted RIFLE fire clip to a handguard's distance, ahead of a 30 cm SMG's or a revolver's muzzle. A
        // rigged gun gets its stance fire reaction as an additive over the aim pose in FHoverAnimProxy instead
        // (UHoverPilotAssets::RifleFireAdd / PistolFireAdd), on every shot, with both hands kept on the gun.
        if (PlayReaction && !Pilot->UsesRiggedGun() && Pilot->LocomotionBridge &&
            !Pilot->LocomotionBridge->IsActionPlaying())
            if (auto *Clip = Tier.TPFireAction.LoadSynchronous())
                Pilot->LocomotionBridge->PlayAction(Clip, 0.f, true);
    }
    else if (PlayMontage && Pilot->ViewArms)
        if (auto *Instance = Pilot->ViewArms->GetAnimInstance())
        {
            UAnimMontage *Montage = Pilot->IsAiming() ? WeaponDefinition->AimFireMontage_FP.LoadSynchronous() : nullptr;
            if (!Montage)
                Montage = WeaponDefinition->FireMontage_FP.LoadSynchronous();
            if (Montage)
            {
                Instance->Montage_Play(Montage);
                LastFireMontageTime = Now;
            }
        }
}
void AHoverCyberRifle::EjectShellAt(const FTransform &Transform)
{
    // The imported Ballista is static and has no native ejection socket. Supply
    // its visible breech as the vendor shell system's fallback transform.
    const FTransform Previous = GetActorTransform();
    SetActorTransform(Transform);
    SpawnShellEffect();
    SetActorTransform(Previous);
}
void AHoverCyberRifle::EjectRigShellAt(const FTransform &Transform, const FVector &LocalDirection, float Impulse)
{
    // Mirrors AZE_WeaponBase::SpawnShellEffect, whose throw direction is the definition's and would send
    // the rigs' brass back into the camera; Transform is the rig's ejection socket at scale 1.
    UStaticMesh *ShellMesh = WeaponDefinition ? WeaponDefinition->BulletShellMesh.LoadSynchronous() : nullptr;
    if (!ShellMesh || !GetWorld())
        return;
    const UZE_WeaponDefinition *Def = WeaponDefinition;
    const int32 NumShells = FMath::Max(1, Def->ShellsPerShot);
    for (int32 Index = 0; Index < NumShells; ++Index)
    {
        FActorSpawnParameters Params;
        Params.Owner = this;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        auto *Shell = GetWorld()->SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(),
                                                               Transform.GetLocation(), Transform.Rotator(), Params);
        UStaticMeshComponent *Mesh = Shell ? Shell->GetStaticMeshComponent() : nullptr;
        if (!Mesh)
            continue;
        Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetStaticMesh(ShellMesh);
        Mesh->SetRelativeScale3D(Def->BulletShellScale);
        Mesh->SetSimulatePhysics(true);
        Mesh->SetCollisionEnabled(ECollisionEnabled::PhysicsOnly);
        Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
        Mesh->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
        Mesh->SetCollisionResponseToChannel(ECC_WorldDynamic, ECR_Block);
        Mesh->SetEnableGravity(Def->BulletShellGravityScale > 0.f);
        FVector Direction = Transform.GetRotation().RotateVector(LocalDirection);
        if (NumShells > 1)
            Direction += FMath::VRand() * .2f;
        const float Speed = (Impulse > 0 ? Impulse : Def->BulletShellImpulse) * FMath::RandRange(.85f, 1.15f);
        Mesh->AddImpulse(Direction * Speed, NAME_None, true);
        Mesh->AddAngularImpulseInDegrees(
            FVector(FMath::RandRange(-40.f, 40.f), FMath::RandRange(-40.f, 40.f), FMath::RandRange(-40.f, 40.f)) *
                100.f,
            NAME_None, true);
        Shell->SetLifeSpan(Def->ShellLifeTime);
    }
}
void AHoverCyberRifle::Reload()
{
    const bool WasReloading = IsReloading();
    // Rounds fired since the last load: a revolver rig drops that many empties during its Reload clip.
    const int32 Spent = WeaponDefinition ? FMath::Max(0, GetMagazineSize() - CurrentClipAmmo) : 0;
    const bool Tactical = CurrentClipAmmo > 0; // Rounds left: bolt home, the rig's ReloadTactical.
    Super::Reload();
    if (!WasReloading && IsReloading())
    {
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->ViewArms && WeaponDefinition)
            if (auto *Instance = Pilot->ViewArms->GetAnimInstance())
                if (auto *Montage = WeaponDefinition->ReloadMontage_FP.LoadSynchronous())
                    Instance->Montage_Play(Montage, Montage->GetPlayLength() / FMath::Max(ReloadDuration, .01f));
        // The stock body reload (MM_Rifle_Reload on the CLS driver) is for the static Ballista only. A rigged
        // gun keeps the aim pose and moves just the left hand, by IK, to the hand_l_target its own Reload
        // clip keys (AHoverPilot::SupportGripOffset): the hands meet the real magazine instead of a phantom
        // one, and the gun hand never spins round the grip. Playing the action would also drop the anim
        // instance's bAiming (IsActionPlaying gate) and with it the support IK's weight.
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge && !Pilot->UsesRiggedGun())
            Pilot->LocomotionBridge->PlayAction(
                LoadObject<UAnimSequence>(
                    nullptr,
                    TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/MM_Rifle_Reload.MM_Rifle_Reload")),
                ReloadDuration);
        // Same ReloadDuration as the body clip above, so the hands and the drum magazine agree in time.
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn))
        {
            Pilot->PlayGunReload(ReloadDuration, Tactical);
            Pilot->ScheduleReloadEject(this, ReloadDuration, Spent);
        }
    }
}
void AHoverCyberRifle::CancelReload()
{
    GetWorldTimerManager().ClearTimer(ReloadTimerHandle);
    bIsReloading = false;
    StopFire();
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
        Pilot->LocomotionBridge->CancelAction();
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->ViewArms && Pilot->ViewArms->GetAnimInstance())
        Pilot->ViewArms->GetAnimInstance()->Montage_Stop(.12f);
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn))
    {
        // The magazine was not refilled: an empty one idles locked back.
        Pilot->SetGunEmpty(WeaponDefinition && WeaponDefinition->bUsesAmmo && CurrentClipAmmo <= 0);
        Pilot->StopGunClip();
    }
}
AHoverMeleeWeapon::AHoverMeleeWeapon()
{
    PrimaryActorTick.bCanEverTick = true;
}
bool AHoverMeleeWeapon::IsSwinging() const
{
    return GetWorld() && GetWorld()->GetTimeSeconds() < SwingEnd;
}
void AHoverMeleeWeapon::CancelSwing()
{
    SetFirstPersonDetail(false);
    if (IsSwinging())
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
        {
            Pilot->LocomotionBridge->CancelAction();
            if (Pilot->ViewArms && Pilot->ViewArms->GetAnimInstance())
                Pilot->ViewArms->GetAnimInstance()->Montage_Stop(.12f);
        }
    GetWorldTimerManager().ClearTimer(ContactTimer);
    for (FTimerHandle &Timer : SwingTimers)
        GetWorldTimerManager().ClearTimer(Timer);
    SwingTimers.Reset();
    ResetStrikeState();
    SwingEnd = 0;
    SetActorHiddenInGame(true);
    StaticMeshTP->SetVisibility(false);
    StaticMeshFP->SetVisibility(false);
}
void AHoverMeleeWeapon::EndPlay(const EEndPlayReason::Type Reason)
{
    ReleaseTwoHandGrip();
    CancelSwing();
    Super::EndPlay(Reason);
}
void AHoverMeleeWeapon::Tick(float DT)
{
    Super::Tick(DT);
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const bool Active = Pilot && Pilot->IsOnFoot() && !Pilot->IsKnockedDown() && !Pilot->IsDefeated() &&
                        !(Pilot->Combat && Pilot->Combat->IsInventoryOpen()) &&
                        (IsHeldBy(Pilot) || IsSwinging());
    SetFirstPersonDetail(Active && !Pilot->IsThirdPersonView());
    SetActorHiddenInGame(!Active);
    if (!Active)
    {
        // The spear (bCancelWhenInactive): board, knockdown, defeat or inventory end the strike or the charge.
        if (Profile.bCancelWhenInactive && (IsSwinging() || bCharging))
            CancelSwing();
        StopStance(Pilot);
    }
    if (!Active)
    {
        StaticMeshTP->SetVisibility(false);
        StaticMeshFP->SetVisibility(false);
        return;
    }
    ConfigureGrip(Pilot);
    UpdateStance(Pilot);
    const bool ThirdPerson = Pilot->IsThirdPersonView();
    StaticMeshTP->SetHiddenInGame(!ThirdPerson);
    StaticMeshFP->SetHiddenInGame(ThirdPerson);
    StaticMeshTP->SetVisibility(ThirdPerson);
    StaticMeshFP->SetVisibility(!ThirdPerson);
}
void AHoverMeleeWeapon::SetFirstPersonDetail(bool Enabled)
{
    if (bFirstPersonDetail != Enabled)
    {
        // A near-camera weapon must not settle on the world-mesh 1K mip.
        // Release the request when holstered or viewed in third person.
        StaticMeshFP->SetTextureForceResidentFlag(Enabled);
        bFirstPersonDetail = Enabled;
    }
}
void AHoverMeleeWeapon::PerformMeleeTrace()
{
    // Owner 2026-10-31: "melee feel sucks, targeting feels like a small window to do damage". The vendor resolves one
    // 20 cm sphere trace from eye height along the camera, once, 0.30 s into the 0.80 s swing. The katana now sweeps
    // the arc instead: at 0.22, 0.30, 0.38 and 0.48 s a wide sphere is swept from the chest out to the blade's reach
    // along the camera yaw only (no pitch, so a crawler under the crosshair still counts), and every zombie touched is
    // damaged once per swing through the vendor's ProcessHit (damage, flinch, blood, the hit confirm).
    // AFS 2026-10-31 (spear item): the times, reach and radius now come from the active strike of the weapon's
    // FHoverMeleeProfile; FHoverMeleeProfile::Katana() holds exactly the values above.
    ClearSweeps();
    for (int32 Index = 0; Index < ActiveStrike.SweepTimes.Num(); ++Index)
        ScheduleSweep(Index, ActiveStrike.SweepTimes[Index]);
}

void AHoverMeleeWeapon::ClearSweeps()
{
    for (FTimerHandle &Timer : SwingTimers)
        GetWorldTimerManager().ClearTimer(Timer);
    SwingTimers.Reset();
    SwingHits.Reset();
}

void AHoverMeleeWeapon::ScheduleSweep(int32 Index, float Delay)
{
    GetWorldTimerManager().SetTimer(SwingTimers.AddDefaulted_GetRef(),
                                    FTimerDelegate::CreateUObject(this, &AHoverMeleeWeapon::SweepAt, Index),
                                    FMath::Max(Delay, .001f), false);
}

void AHoverMeleeWeapon::SweepOnce()
{
    SweepAt(0);
}

void AHoverMeleeWeapon::SweepAt(int32 Index)
{
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    if (!Pilot || !Pilot->IsOnFoot() || !IsSwinging() || !GetWorld())
        return;
    const FHoverMeleeStrike &Strike = ActiveStrike;
    const float Range = Strike.Reach > 0.f       ? Strike.Reach
                        : WeaponDefinition       ? WeaponDefinition->MeleeStats.MeleeRange
                                                 : 150.f;
    const float DefinitionRadius = WeaponDefinition ? WeaponDefinition->MeleeStats.MeleeRadius * 2.5f : 50.f;
    const float Radius = Strike.Radius > 0.f ? Strike.Radius : FMath::Max(50.f, DefinitionRadius);
    // A straight line along the spear (jab, thrust: both yaws 0) or a narrow arc walked sweep by sweep (swing).
    const int32 Count = Strike.SweepTimes.Num();
    const float ArcYaw = Count > 1 ? FMath::Lerp(Strike.ArcStartYaw, Strike.ArcEndYaw, float(Index) / float(Count - 1))
                                   : Strike.ArcStartYaw;
    const FVector Forward = FRotator(0.f, Pilot->GetControlRotation().Yaw + ArcYaw, 0.f).Vector();
    const FVector Start =
        Pilot->GetActorLocation() + FVector(0, 0, Strike.StartHeight) + Forward * Strike.StartForward;
    const FVector End = Start + Forward * (Range + Strike.ReachPad);
    TArray<FHitResult> Hits;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverKatanaSweep), false, this);
    Params.AddIgnoredActor(OwnerPawn);
    Params.bReturnPhysicalMaterial = true;
    if (Profile.bPierce)
    {
        // Every touch comes back as an overlap (the query's response caps the object's), nearest first; the line
        // ends at the first non-zombie that would have blocked the Pawn channel (a wall, a car).
        GetWorld()->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Pawn,
                                        FCollisionShape::MakeSphere(Radius), Params, FCollisionResponseParams(ECR_Overlap));
        Hits.Sort([](const FHitResult &A, const FHitResult &B) { return A.Time < B.Time; });
        const int32 Wall = Hits.IndexOfByPredicate([](const FHitResult &Hit) {
            const UPrimitiveComponent *Component = Hit.GetComponent();
            return !Cast<AZE_ZombieCharacter>(Hit.GetActor()) && Component &&
                   Component->GetCollisionResponseToChannel(ECC_Pawn) == ECR_Block;
        });
        if (Wall != INDEX_NONE)
            Hits.SetNum(Wall);
    }
    else
        GetWorld()->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Pawn,
                                        FCollisionShape::MakeSphere(Radius), Params);
    int32 Struck = 0;
    for (FHitResult &Hit : Hits)
    {
        AActor *Actor = Hit.GetActor();
        if (!Actor || !Cast<AZE_ZombieCharacter>(Actor) || SwingHits.Contains(Actor))
            continue;
        SwingHits.Add(Actor);
        if (Hit.ImpactPoint.IsNearlyZero())
            Hit.ImpactPoint = Actor->GetActorLocation();
        if (Hit.ImpactNormal.IsNearlyZero())
            Hit.ImpactNormal = -Forward;
        Hit.bBlockingHit = true;
        const float Distance = FVector::Dist2D(Actor->GetActorLocation(), Pilot->GetActorLocation());
        StrikeActor(Hit);
        if (Strike.HitStopSeconds > 0.f)
        {
            FTimerHandle HitStopTimer; // Per victim, as the gun's kill hit-stop (a shared handle cancels restores).
            HoverEffects::HitStop(Actor, Strike.HitStopDilation, Strike.HitStopSeconds, HitStopTimer);
        }
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_HIT strike=%s actor=%s dist=%.0f scale=%.2f"), *Profile.LogTag,
               *Strike.Name.ToString(), *Actor->GetName(), Distance, ActiveDamageScale);
        ++Struck;
    }
    StrikeHits += Struck;
    if (Struck)
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_SWEEP struck=%d radius=%.0f range=%.0f strike=%s index=%d yaw=%.0f"),
               *Profile.LogTag, Struck, Radius, Range, *Strike.Name.ToString(), Index, ArcYaw);
}

void AHoverMeleeWeapon::StrikeActor(const FHitResult &Hit)
{
    if (FMath::IsNearlyEqual(ActiveDamageScale, 1.f) || !WeaponDefinition)
    {
        ProcessHit(Hit); // The katana and every unscaled strike: the vendor path, unchanged.
        return;
    }
    // ProcessHit's own damage pick (MeleeDamage for a melee definition) times the strike's scale; the vendor
    // function has no scale input. Same ApplyPointDamage call, so flinch, blood, kill points and the hit confirm
    // (Causer is this AHoverMeleeWeapon) stay identical.
    const float Base = WeaponDefinition->WeaponType == EZE_WeaponType::Melee ? WeaponDefinition->MeleeStats.MeleeDamage
                                                                             : WeaponDefinition->CombatStats.Damage;
    if (OwnerPawn && OwnerPawn->GetController())
        UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Base * ActiveDamageScale, Hit.ImpactNormal, Hit,
                                           OwnerPawn->GetController(), this, nullptr);
}

void AHoverMeleeWeapon::PlayFireAnimation()
{
    // Vendor HandleFire path (the katana): the profile's first light strike, swept by PerformMeleeTrace.
    if (Profile.Light.IsEmpty())
        Profile = FHoverMeleeProfile::Katana();
    ActiveStrike = Profile.Light[0];
    ActiveDamageScale = 1.f;
    PresentStrike();
}

bool AHoverMeleeWeapon::PresentStrike(bool bPlayClip)
{
    LastFireAnimTime = GetWorld()->GetTimeSeconds();
    StrikeStart = LastFireAnimTime;
    SwingEnd = LastFireAnimTime + ActiveStrike.Duration;
    StrikeHits = 0;
    MaxTipReach = 0.f;
    bool Played = false;
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn))
        Pilot->PlayMeleeSwingSound(); // audio pass 2026-10-31
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge && bPlayClip)
    {
        ConfigureGrip(Pilot);
        auto *Clip = ActiveStrike.Clip.LoadSynchronous();
        Played = Pilot->LocomotionBridge->PlayAction(Clip, ActiveStrike.Duration, ActiveStrike.bUpperBody);
        if (Clip && Pilot->ViewArms && !ActiveStrike.ViewClip.IsNull())
            if (auto *View = Cast<UHoverViewAnimInstance>(Pilot->ViewArms->GetAnimInstance()))
            {
                View->bMelee = true;
                auto *ViewClip = ActiveStrike.ViewClip.LoadSynchronous();
                if (ViewClip)
                    View->PlaySlotAnimationAsDynamicMontage(ViewClip, TEXT("DefaultSlot"), .08f, .15f,
                                                            ViewClip->GetPlayLength() / ActiveStrike.Duration);
            }
    }
    return Played;
}

void AHoverMeleeWeapon::SetProfile(const FHoverMeleeProfile &InProfile)
{
    CancelSwing();
    ReleaseTwoHandGrip();
    Profile = InProfile;
    if (Profile.Light.IsEmpty())
        Profile.Light = FHoverMeleeProfile::Katana().Light;
    ActiveStrike = Profile.Light[0];
    ComboIndex = 0;
    bGripConfigured = false;
}

bool AHoverMeleeWeapon::IsHeldBy(const AHoverPilot *Pilot) const
{
    if (!Pilot)
        return false;
    const UHoverCombatBridge *Bridge = Pilot->Combat.Get();
    const bool SpearSelected = Bridge && Bridge->IsSpearSelected();
    if (Bridge && Bridge->SpearWeapon.Get() == this)
        return SpearSelected;
    // The katana: the hold-R3 toggle, except while the spear's quickbar slot carries the melee flag.
    return Pilot->IsMeleeEquipped() && !SpearSelected;
}

bool AHoverMeleeWeapon::CanStrike() const
{
    const auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    return Pilot && GetWorld() && Pilot->IsOnFoot() && !Pilot->IsKnockedDown() && !Pilot->IsDefeated() &&
           !(Pilot->Combat && Pilot->Combat->IsInventoryOpen()) && IsHeldBy(Pilot);
}

float AHoverMeleeWeapon::GetChargeAlpha() const
{
    if (!bCharging || !GetWorld())
        return 0.f;
    return FMath::Clamp((GetWorld()->GetTimeSeconds() - ChargeStart) / FMath::Max(.1f, Profile.FullChargeSeconds), 0.f,
                        1.f);
}

void AHoverMeleeWeapon::PressLight()
{
    if (Profile.Light.IsEmpty() || bCharging || !CanStrike())
        return;
    const float Now = GetWorld()->GetTimeSeconds();
    if (IsSwinging())
    {
        // Too early: ignored. Inside the chain window: buffered for the chain point. Past it: the tail is cancelled.
        if (Now >= ChainAtTime)
            StartLight();
        else if (Now - StrikeStart >= ActiveStrike.ChainOpenSeconds && !bBufferedLight)
        {
            bBufferedLight = true;
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_BUFFER after=%s"), *Profile.LogTag, *ActiveStrike.Name.ToString());
        }
        return;
    }
    StartLight();
}

void AHoverMeleeWeapon::StartLight()
{
    const float Now = GetWorld()->GetTimeSeconds();
    if (Now > ComboExpiresAt)
        ComboIndex = 0;
    const int32 Index = ComboIndex % Profile.Light.Num();
    ComboIndex = (Index + 1) % Profile.Light.Num();
    bBufferedLight = false;
    StartStrike(Profile.Light[Index], Profile.Light[Index].DamageScale, Index + 1);
    const float ChainAt = ActiveStrike.ChainAtSeconds > 0.f
                              ? FMath::Min(ActiveStrike.ChainAtSeconds, ActiveStrike.Duration)
                              : ActiveStrike.Duration;
    ChainAtTime = Now + ChainAt;
    GetWorldTimerManager().SetTimer(ChainTimer, this, &AHoverMeleeWeapon::OnChainPoint, FMath::Max(.05f, ChainAt),
                                    false);
    ComboExpiresAt = SwingEnd + Profile.ComboResetSeconds;
}

void AHoverMeleeWeapon::OnChainPoint()
{
    if (bBufferedLight && !bCharging && CanStrike())
        StartLight();
    bBufferedLight = false;
}

void AHoverMeleeWeapon::StartStrike(const FHoverMeleeStrike &Strike, float Scale, int32 ComboStep)
{
    FinishStrike(); // A chained strike closes the previous strike's receipt line first.
    ActiveStrike = Strike;
    ActiveDamageScale = Scale;
    const bool Played = PresentStrike();
    ClearSweeps();
    for (int32 Index = 0; Index < Strike.SweepTimes.Num(); ++Index)
        ScheduleSweep(Index, Strike.SweepTimes[Index]);
    GetWorldTimerManager().SetTimer(StrikeEndTimer, this, &AHoverMeleeWeapon::FinishStrike,
                                    FMath::Max(.05f, Strike.Duration), false);
    bStrikeOpen = true;
    UE_LOG(LogTemp, Verbose,
           TEXT("HOVER_%s_STRIKE begin name=%s combo=%d clip=%s played=%d duration=%.2f scale=%.2f reach=%.0f "
                "radius=%.0f"),
           *Profile.LogTag, *Strike.Name.ToString(), ComboStep, *Strike.Clip.GetAssetName(), Played, Strike.Duration,
           Scale, Strike.Reach, Strike.Radius);
}

void AHoverMeleeWeapon::FinishStrike()
{
    GetWorldTimerManager().ClearTimer(StrikeEndTimer);
    if (!bStrikeOpen)
        return;
    bStrikeOpen = false;
    LastStrikeHits = StrikeHits;
    LastStrikeName = ActiveStrike.Name;
    LastTipReach = MaxTipReach;
    ++StrikesFinished;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_STRIKE end name=%s hits=%d tip_reach=%.0f scale=%.2f"), *Profile.LogTag,
           *ActiveStrike.Name.ToString(), StrikeHits, MaxTipReach, ActiveDamageScale);
}

void AHoverMeleeWeapon::SetAttackHeld(bool Held)
{
    if (Held == bAttackHeld)
        return;
    bAttackHeld = Held;
    FTimerManager &Timers = GetWorldTimerManager();
    if (Held)
    {
        bHoldIsCharge = false;
        // No heavy, or a press during a strike: a light press now (chain buffer or cancel), never a charge.
        if (!Profile.bHasHeavy || IsSwinging() || bCharging)
        {
            PressLight();
            return;
        }
        if (!CanStrike())
            return;
        bHoldIsCharge = true;
        Timers.SetTimer(ChargeTimer, this, &AHoverMeleeWeapon::BeginCharge, FMath::Max(.05f, Profile.ChargeThreshold),
                        false);
        return;
    }
    if (bCharging)
        ReleaseHeavy();
    else if (bHoldIsCharge && Timers.IsTimerActive(ChargeTimer))
    {
        // Released before ChargeThreshold: a tap, the light combo.
        Timers.ClearTimer(ChargeTimer);
        PressLight();
    }
    bHoldIsCharge = false;
}

void AHoverMeleeWeapon::BeginCharge()
{
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    if (!bAttackHeld || bCharging || IsSwinging() || !CanStrike())
        return;
    FinishStrike();
    ClearSweeps();
    GetWorldTimerManager().ClearTimer(ChainTimer);
    bBufferedLight = false;
    ComboIndex = 0;
    bCharging = true;
    ChargeStart = GetWorld()->GetTimeSeconds();
    ActiveStrike = Profile.Heavy;
    ActiveDamageScale = Profile.HeavyMinScale;
    StrikeStart = ChargeStart;
    ChainAtTime = ChargeStart + 1000.f;
    // IsSwinging stays true through the wind-up: the gun stays down and the stance loop waits.
    SwingEnd = ChargeStart + FMath::Max(Profile.FullChargeSeconds, Profile.MaxChargeHoldSeconds) +
               Profile.Heavy.Duration + 1.f;
    const float Windup = FMath::Clamp(Profile.Heavy.WindupFraction, .05f, .9f);
    bChargeClipPlaying = false;
    if (Pilot && Pilot->LocomotionBridge)
    {
        ConfigureGrip(Pilot);
        // The wind-up plays the heavy clip from its start and reaches WindupFraction at full charge, where it holds.
        bChargeClipPlaying = Pilot->LocomotionBridge->PlayAction(
            Profile.Heavy.Clip.LoadSynchronous(), FMath::Max(.1f, Profile.FullChargeSeconds) / Windup,
            Profile.Heavy.bUpperBody);
    }
    FTimerManager &Timers = GetWorldTimerManager();
    Timers.SetTimer(ChargeFreezeTimer, this, &AHoverMeleeWeapon::FreezeCharge,
                    FMath::Max(.1f, Profile.FullChargeSeconds), false);
    Timers.SetTimer(ChargeAutoTimer, this, &AHoverMeleeWeapon::ReleaseHeavy,
                    FMath::Max(Profile.FullChargeSeconds, Profile.MaxChargeHoldSeconds), false);
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_CHARGE begin clip=%s played=%d windup=%.2f"), *Profile.LogTag,
           *Profile.Heavy.Clip.GetAssetName(), bChargeClipPlaying, Windup);
}

void AHoverMeleeWeapon::FreezeCharge()
{
    if (bCharging && bChargeClipPlaying)
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
            Pilot->LocomotionBridge->SetActionPlayRate(0.f);
}

void AHoverMeleeWeapon::ReleaseHeavy()
{
    if (!bCharging)
        return;
    bCharging = false;
    FTimerManager &Timers = GetWorldTimerManager();
    Timers.ClearTimer(ChargeFreezeTimer);
    Timers.ClearTimer(ChargeAutoTimer);
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const FHoverMeleeStrike &Heavy = Profile.Heavy;
    const float Now = GetWorld()->GetTimeSeconds();
    const float Alpha = FMath::Clamp((Now - ChargeStart) / FMath::Max(.1f, Profile.FullChargeSeconds), 0.f, 1.f);
    const float Windup = FMath::Clamp(Heavy.WindupFraction, .05f, .9f);
    // The clip reached Windup at full charge and held there; an early release lets go from where it got to.
    float FracNow = Windup * Alpha;
    float Remaining = FMath::Max(.1f, Heavy.Duration * (1.f - Windup));
    ActiveStrike = Heavy;
    ActiveDamageScale = FMath::Lerp(Profile.HeavyMinScale, Profile.HeavyMaxScale, Alpha);
    UAnimSequence *Clip = Heavy.Clip.LoadSynchronous();
    bool Resumed = false;
    if (Pilot && Pilot->LocomotionBridge && Clip && bChargeClipPlaying)
        Resumed = Pilot->LocomotionBridge->SetActionPlayRate(Clip->GetPlayLength() * (1.f - FracNow) / Remaining);
    if (Resumed)
        PresentStrike(false); // Sound, timing and receipt fields; the wind-up montage carries on at the new rate.
    else
    {
        // The wind-up montage was replaced (a crouch, a hit react) or never played: the whole clip from its start.
        FracNow = 0.f;
        Remaining = FMath::Max(.1f, Heavy.Duration);
        PresentStrike(true);
    }
    SwingEnd = Now + Remaining;
    ChainAtTime = SwingEnd;
    ClearSweeps();
    const float Span = FMath::Max(.05f, 1.f - FracNow);
    for (int32 Index = 0; Index < Heavy.SweepTimes.Num(); ++Index)
    {
        const float Fraction = Heavy.SweepTimes[Index] / FMath::Max(.05f, Heavy.Duration);
        if (Fraction > FracNow)
            ScheduleSweep(Index, (Fraction - FracNow) / Span * Remaining);
    }
    Timers.SetTimer(StrikeEndTimer, this, &AHoverMeleeWeapon::FinishStrike, Remaining, false);
    Timers.SetTimer(ChainTimer, this, &AHoverMeleeWeapon::OnChainPoint, Remaining, false);
    ComboExpiresAt = SwingEnd + Profile.ComboResetSeconds;
    bStrikeOpen = true;
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_HEAVY charge=%.2f scale=%.2f resumed=%d remaining=%.2f"), *Profile.LogTag,
           Alpha, ActiveDamageScale, Resumed, Remaining);
}

void AHoverMeleeWeapon::ResetStrikeState()
{
    FinishStrike();
    FTimerManager &Timers = GetWorldTimerManager();
    for (FTimerHandle *Timer : {&ChainTimer, &ChargeTimer, &ChargeFreezeTimer, &ChargeAutoTimer})
        Timers.ClearTimer(*Timer);
    bCharging = bBufferedLight = bHoldIsCharge = bChargeClipPlaying = false;
    ChainAtTime = 0.f;
}

void AHoverMeleeWeapon::OnHolstered()
{
    CancelSwing();
    bAttackHeld = false;
    StopStance(Cast<AHoverPilot>(OwnerPawn));
}

bool AHoverMeleeWeapon::IsStancePlaying() const
{
    const auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const auto *Bridge = Pilot ? Pilot->LocomotionBridge.Get() : nullptr;
    return bStanceActive && Bridge && StanceMontage.IsValid() && Bridge->GetAction() == StanceMontage.Get() &&
           Bridge->IsActionPlaying();
}

void AHoverMeleeWeapon::StopStance(AHoverPilot *Pilot)
{
    // Only our own loop is stopped: a crouch, knockdown or ride action that replaced it keeps playing.
    if (IsStancePlaying() && Pilot && Pilot->LocomotionBridge)
        Pilot->LocomotionBridge->CancelAction();
    bStanceActive = false;
    StanceMontage.Reset();
}

void AHoverMeleeWeapon::UpdateStance(AHoverPilot *Pilot)
{
    auto *Bridge = Pilot ? Pilot->LocomotionBridge.Get() : nullptr;
    if (!Bridge || Profile.StanceLoop.IsNull())
        return;
    bStanceActive = IsStancePlaying(); // A strike, crouch or hit montage replaces the loop.
    if (IsSwinging() || bCharging)
        return;
    const bool Want = IsHeldBy(Pilot) && Pilot->IsThirdPersonView() && !Pilot->GetCharacterMovement()->IsFalling();
    if (Want && !Bridge->IsActionPlaying())
    {
        UAnimSequence *Loop = Profile.StanceLoop.LoadSynchronous();
        if (Loop && Bridge->PlayAction(Loop, 0.f, true, 100000))
        {
            StanceMontage = Bridge->GetAction();
            bStanceActive = true;
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_%s_STANCE start clip=%s"), *Profile.LogTag, *Loop->GetName());
        }
    }
    else if (!Want)
        StopStance(Pilot);
}

bool AHoverMeleeWeapon::GetShaft(FVector &Butt, FVector &Axis, float &Length) const
{
    const UStaticMesh *Mesh = StaticMeshTP ? StaticMeshTP->GetStaticMesh() : nullptr;
    if (!Mesh)
        return false;
    // The shaft is the mesh's longest bounds axis; the head is at its maximum unless the profile flips it.
    const FBox Box = Mesh->GetBoundingBox();
    const FVector Size = Box.GetSize();
    const int32 A = Size.X >= Size.Y && Size.X >= Size.Z ? 0 : (Size.Y >= Size.Z ? 1 : 2);
    Axis = FVector::ZeroVector;
    Axis[A] = Profile.bFlipMeshTip ? -1.f : 1.f;
    Butt = Box.GetCenter();
    Butt[A] = Profile.bFlipMeshTip ? Box.Max[A] : Box.Min[A];
    Length = Size[A];
    return Length > 1.f;
}

FVector AHoverMeleeWeapon::GetTipLocation() const
{
    FVector Butt, Axis;
    float Length = 0.f;
    if (!GetShaft(Butt, Axis, Length))
        return GetActorLocation();
    return StaticMeshTP->GetComponentTransform().TransformPosition(Butt + Axis * Length);
}

void AHoverMeleeWeapon::ConfigureTwoHandGrip(AHoverPilot *Pilot)
{
    auto *Body = Pilot ? Pilot->GetMesh() : nullptr;
    FVector Butt, Axis;
    float Length = 0.f;
    if (!Body || !GetShaft(Butt, Axis, Length))
        return;
    // Carry (no pack clip holding both hands, e.g. mid-jump): the shaft along the fist, gripped as the katana's
    // handle, at GripFromButt of its length.
    StaticMeshTP->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("hand_r"));
    const FTransform HandWorld = Body->GetSocketTransform(TEXT("hand_r"));
    const FVector Index = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("index_02_r")));
    const FVector Pinky = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("pinky_02_r")));
    const FVector Palm = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("middle_01_r")));
    const FVector FistAxis = (Index - Pinky).GetSafeNormal(SMALL_NUMBER, FVector::UpVector);
    const FVector Grip = FMath::Lerp((Index + Pinky) * .5f, Palm, .75f);
    const FQuat Rotation = FQuat::FindBetweenNormals(Axis, FistAxis);
    const FVector GripLocal = Butt + Axis * (Length * Profile.GripFromButt);
    CarryRelative = FTransform(Rotation, Grip - Rotation.RotateVector(GripLocal));
    TwoHandRelative = CarryRelative;
    TwoHandWeight = 0.f;
    StaticMeshTP->SetRelativeTransform(CarryRelative);
    if (Pilot->ViewArms)
    {
        StaticMeshFP->AttachToComponent(Pilot->ViewArms, FAttachmentTransformRules::SnapToTargetNotIncludingScale,
                                        TEXT("hand_r"));
        StaticMeshFP->SetRelativeTransform(CarryRelative);
        StaticMeshFP->CastShadow = false;
        AddTickPrerequisiteComponent(Pilot->ViewArms);
    }
    AddTickPrerequisiteComponent(Body);
    // Same-frame update after the body's bones are final, as AHoverPilot::UpdateGunTransform does for the guns.
    GripBody = Body;
    GripPoseHandle = Body->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &AHoverMeleeWeapon::UpdateTwoHandGrip));
    bGripConfigured = true;
    UE_LOG(LogTemp, Display, TEXT("HOVER_%s_GRIP length=%.0f grip_from_butt=%.2f tip_left=%d flip=%d"),
           *Profile.LogTag, Length, Profile.GripFromButt, Profile.bTipTowardLeftHand, Profile.bFlipMeshTip);
}

void AHoverMeleeWeapon::ReleaseTwoHandGrip()
{
    if (auto *Body = GripBody.Get(); Body && GripPoseHandle.IsValid())
        Body->UnregisterOnBoneTransformsFinalizedDelegate(GripPoseHandle);
    GripPoseHandle.Reset();
    GripBody.Reset();
}

void AHoverMeleeWeapon::UpdateTwoHandGrip()
{
    auto *Body = GripBody.Get();
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    if (!Body || !Pilot || !GetWorld() || IsHidden())
        return;
    // The pack's own rig (BP_SpearFighter) plays a spear-tracking clip and FABRIKs the hands onto it; here the hands
    // keep the retargeted body clip and the spear follows them: the shaft runs from the rear palm through the front
    // palm whenever a pack clip holds both hands on it (strike, wind-up, stance loop).
    const bool HandsOnShaft = IsSwinging() || bCharging || IsStancePlaying();
    const FTransform HandWorld = Body->GetSocketTransform(TEXT("hand_r"));
    FVector Butt, Axis;
    float Length = 0.f;
    if (HandsOnShaft && GetShaft(Butt, Axis, Length))
    {
        auto PalmOf = [Body](const TCHAR *IndexBone, const TCHAR *PinkyBone, const TCHAR *MiddleBone) {
            const FVector Knuckles = (Body->GetSocketLocation(IndexBone) + Body->GetSocketLocation(PinkyBone)) * .5f;
            return FMath::Lerp(Knuckles, Body->GetSocketLocation(MiddleBone), .75f);
        };
        const FVector Right = PalmOf(TEXT("index_02_r"), TEXT("pinky_02_r"), TEXT("middle_01_r"));
        const FVector Left = PalmOf(TEXT("index_02_l"), TEXT("pinky_02_l"), TEXT("middle_01_l"));
        // AFS 2026-10-31 (spear proof): the pack's lead hand changes between clips (the jab leads with the left
        // palm, the thrusts and the heavy with the right), so a fixed "head on the left hand" laid the spear
        // backwards through every thrust (head 86-94 cm ahead while the sweep reached 270-300 cm). The head now
        // goes on whichever palm is ahead along her facing, with hysteresis so it never flips while the hands pass.
        const float LeftAhead =
            FVector::DotProduct((Left - Right).GetSafeNormal(), Pilot->GetActorForwardVector());
        if (TipLeftLive < 0)
            TipLeftLive = Profile.bTipTowardLeftHand ? 1 : 0;
        if (LeftAhead > .3f)
            TipLeftLive = 1;
        else if (LeftAhead < -.3f)
            TipLeftLive = 0;
        const FVector Rear = TipLeftLive ? Right : Left;
        const FVector Front = TipLeftLive ? Left : Right;
        const float Spacing = FVector::Dist(Rear, Front);
        if (Spacing >= Profile.TwoHandMinSpacing && Spacing <= Profile.TwoHandMaxSpacing)
        {
            const FVector Direction = (Front - Rear) / Spacing;
            // Roll from the right hand's Z so the head's flat turns with the wrist.
            const FQuat Shaft = FRotationMatrix::MakeFromXZ(Direction, HandWorld.GetUnitAxis(EAxis::Z)).ToQuat();
            const FQuat MeshWorld = Shaft * FQuat::FindBetweenNormals(Axis, FVector::ForwardVector);
            const FVector GripLocal = Butt + Axis * (Length * Profile.GripFromButt);
            const FTransform World(MeshWorld, Rear - MeshWorld.RotateVector(GripLocal));
            TwoHandRelative = World.GetRelativeTransform(HandWorld);
            TwoHandRelative.SetScale3D(FVector::OneVector);
        }
    }
    // Only the switch between the carry and the two-hand line is eased (about 0.1 s); while a clip holds both hands
    // the spear tracks them exactly, frame for frame.
    const float DT = FMath::Max(GetWorld()->GetDeltaSeconds(), 0.f);
    TwoHandWeight = FMath::FInterpConstantTo(TwoHandWeight, HandsOnShaft ? 1.f : 0.f, DT, 10.f);
    FTransform Relative;
    Relative.SetLocation(FMath::Lerp(CarryRelative.GetLocation(), TwoHandRelative.GetLocation(), TwoHandWeight));
    Relative.SetRotation(
        FQuat::Slerp(CarryRelative.GetRotation(), TwoHandRelative.GetRotation(), TwoHandWeight).GetNormalized());
    StaticMeshTP->SetRelativeTransform(Relative);
    if (IsSwinging() && !bCharging)
    {
        // Receipt: how far ahead of Vexa (along the camera yaw) the head reached in this strike.
        const FVector Forward = FRotator(0.f, Pilot->GetControlRotation().Yaw, 0.f).Vector();
        MaxTipReach =
            FMath::Max(MaxTipReach, float(FVector::DotProduct(GetTipLocation() - Pilot->GetActorLocation(), Forward)));
    }
}

void AHoverMeleeWeapon::ConfigureGrip(AHoverPilot *Pilot)
{
    if (!bGripConfigured && Pilot && Profile.bTwoHandGrip)
        ConfigureTwoHandGrip(Pilot); // The spear; a failure falls through to the katana grip below.
    if (bGripConfigured || !Pilot)
        return;
    auto *Body = Pilot->GetMesh();
    const FTransform HandWorld = Body->GetSocketTransform(TEXT("hand_r"));
    const FVector Index = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("index_02_r")));
    const FVector Pinky = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("pinky_02_r")));
    const FVector Palm = HandWorld.InverseTransformPosition(Body->GetSocketLocation(TEXT("middle_01_r")));
    const FVector BladeAxis = (Index - Pinky).GetSafeNormal(SMALL_NUMBER, FVector::UpVector);
    StaticMeshTP->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetNotIncludingScale, TEXT("hand_r"));
    const FVector Grip = FMath::Lerp((Index + Pinky) * .5f, Palm, .75f);
    const FQuat Rotation =
        FRotationMatrix::MakeFromZX(BladeAxis, FVector::ForwardVector).ToQuat() * FQuat(FVector::UpVector, PI);
    // The mesh origin is 11cm above its pommel; its guard is at local Z=20cm.
    // Grip 5cm below the guard, and turn the cutting edge around the handle.
    const FVector HandleContact(-.4f, -.4f, 15.f);
    StaticMeshTP->SetRelativeLocation(Grip - Rotation.RotateVector(HandleContact));
    StaticMeshTP->SetRelativeRotation(Rotation);
    StaticMeshFP->AttachToComponent(Pilot->ViewArms, FAttachmentTransformRules::SnapToTargetNotIncludingScale,
                                    TEXT("hand_r"));
    StaticMeshFP->SetRelativeTransform(StaticMeshTP->GetRelativeTransform());
    StaticMeshFP->CastShadow = false;
    AddTickPrerequisiteComponent(Body);
    AddTickPrerequisiteComponent(Pilot->ViewArms);
    bGripConfigured = true;
}
UHoverCombatBridge::UHoverCombatBridge()
{
    PrimaryComponentTick.bCanEverTick = true;
}
void UHoverCombatBridge::BeginPlay()
{
    Super::BeginPlay();
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    if (!Pilot)
        return;
    Inventory = NewObject<UZE_InventoryComponent>(Pilot, TEXT("ZE_Inventory"));
    Inventory->RegisterComponent();
    Survival = NewObject<UZE_SurvivalComponent>(Pilot, TEXT("ZE_Survival"));
    Survival->RegisterComponent();
    // The level policy sets the pool (100 everywhere, 150 in NYC Survival).
    if (const auto *Policy = IHoverTestLevelPolicy::Get(GetWorld()))
    {
        const float Max = Policy->GetPlayerMaxHealth();
        Survival->SetMaxHealth(Max);
        Survival->SetHealth(Max);
        Pilot->SandboxHealth = Max;
    }
    const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>();
    const auto *Waves = Mode ? Mode->GetWaveSettings() : nullptr;
    Survival->SetGold(Waves ? Waves->StartingEquipment.StartingGold : 500);
    // Invulnerability is owned by Vexa's damage override, not by an unrelated health widget.
    Weapons = NewObject<UZE_WeaponComponent>(Pilot, TEXT("ZE_Weapons"));
    Weapons->RegisterComponent();
    Interaction = NewObject<UZE_InteractionTraceComponent>(Pilot, TEXT("ZE_Interaction"));
    Interaction->RegisterComponent();
    FZE_InteractionTraceSettings Trace;
    Trace.TraceDistance = 800; // Includes the third-person camera boom; pawn-distance gate remains 250cm.
    Trace.bUseSphereTrace = true;
    Interaction->ApplySettings(Trace);
    FGuid Id;
    if (Waves && !Waves->StartingEquipment.StartingWeapons.IsEmpty())
    {
        const auto &Gear = Waves->StartingEquipment;
        for (const auto &Slot : Gear.StartingWeapons)
            if (auto *Definition = Slot.WeaponDefinition.LoadSynchronous())
                if (Inventory->AddItemDefinition(Definition, 1, Id) && Slot.bAddToQuickbar)
                    Inventory->AssignInstanceToQuickbar(Id, Slot.QuickbarSlot);
        for (const auto &Ammo : Gear.StartingAmmo)
            if (auto *Definition = Ammo.LoadSynchronous())
                Inventory->AddItemDefinition(Definition, Gear.AmmoQuantity, Id);
        // Section 2 change 4: the frag stack and its quickbar slot. Cyber City authors GrenadeCount 0,
        // so only DA_NYCWaves (2 frags, slot 5) reaches this.
        if (Gear.GrenadeCount > 0)
            if (auto *Frag = Gear.GrenadeItem.LoadSynchronous())
                if (Inventory->AddItemDefinition(Frag, Gear.GrenadeCount, Id) && Gear.bAddGrenadesToQuickbar)
                    Inventory->AssignInstanceToQuickbar(Id, Gear.GrenadeQuickbarSlot);
        Inventory->SetActiveQuickbarSlot(1);
        if (auto *Weapon = GetWeapon())
            Weapon->FinalizeEquipped();
    }
    MeleeWeapon = Pilot->MeleeWeapon;
    // AFS 2026-10-31 (spear item), NYC Survival only (owner: the SpearAnimationsV2 pack is Vexa's melee). The spear is
    // a second AHoverMeleeWeapon owned here; Scripts/AuthorSpear.py authors DA_NYC_Spear (no WeaponActorClass), its
    // quickbar slot in DA_NYCWaves and DA_SpearProfile. Without the definition nothing changes.
    if (Pilot->bSurvivalRules)
        if (auto *Definition = LoadObject<UZE_WeaponDefinition>(
                nullptr, TEXT("/Game/HoverPrototype/NYC/Weapons/DA_NYC_Spear.DA_NYC_Spear"), nullptr, LOAD_NoWarn))
        {
            SpearDefinition = Definition;
            SpearWeapon = GetWorld()->SpawnActor<AHoverMeleeWeapon>();
            if (SpearWeapon)
            {
                SpearWeapon->SetProfile(FHoverMeleeProfile::LoadSpear());
                SpearWeapon->SetWeaponDefinition(Definition);
                SpearWeapon->Equip(Pilot);
            }
            UE_LOG(LogTemp, Display, TEXT("HOVER_SPEAR_READY actor=%s slot=%d"), *GetNameSafe(SpearWeapon),
                   FindSpearSlot());
        }
}
AZE_WeaponBase *UHoverCombatBridge::GetWeapon() const
{
    return Weapons ? Weapons->GetCurrentWeapon() : nullptr;
}
bool UHoverCombatBridge::IsReloading() const
{
    const AZE_WeaponBase *Weapon = GetWeapon();
    return Weapon && Weapon->IsReloading();
}
void UHoverCombatBridge::SetTrigger(bool Held)
{
    Held = Held && !InventoryUI && !(MeleeWeapon && MeleeWeapon->IsSwinging());
    if (auto *Weapon = GetWeapon())
    {
        if (Held && !bTriggerHeld)
            Weapon->StartFire();
        if (!Held)
            Weapon->StopFire();
    }
    bTriggerHeld = Held;
}
void UHoverCombatBridge::Reload()
{
    const auto *Pilot = Cast<AHoverPilot>(GetOwner());
    if (!InventoryUI && !(Pilot && Pilot->IsMeleeEquipped()) && !(MeleeWeapon && MeleeWeapon->IsSwinging()))
        if (auto *Weapon = GetWeapon())
            Weapon->Reload();
}
void UHoverCombatBridge::SuspendForRide()
{
    if (SpearWeapon)
        SpearWeapon->CancelSwing();
    if (InventoryUI)
        ToggleInventory();
    SetTrigger(false);
    if (auto *Weapon = Cast<AHoverCyberRifle>(GetWeapon()))
        Weapon->CancelReload();
    InteractionHeld = 0;
}
void UHoverCombatBridge::Melee()
{
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    // AFS 2026-10-31 (spear item): while the spear slot is selected the melee input is its light combo.
    if (bSpearSelected && SpearWeapon)
    {
        if (Pilot && Pilot->IsOnFoot() && !InventoryUI)
            SpearWeapon->PressLight();
        return;
    }
    if (!Pilot || !Pilot->IsOnFoot() || InventoryUI || !MeleeWeapon || MeleeWeapon->IsSwinging())
        return;
    if (auto *Weapon = Cast<AHoverCyberRifle>(GetWeapon()))
        Weapon->CancelReload();
    MeleeWeapon->StopFire();
    MeleeWeapon->StartFire();
    MeleeWeapon->StopFire();
}
void UHoverCombatBridge::RefillAmmo()
{
    auto *Weapon = GetWeapon();
    if (!Weapon || !Inventory)
        return;
    const auto *Def = Weapon->GetWeaponDefinition();
    if (Def)
        if (auto *Ammo = Def->AmmoDefinition.LoadSynchronous())
        {
            FGuid Id;
            const int32 Missing = FMath::Max(0, Def->MaxReserveAmmo - Weapon->GetReserveAmmo());
            if (Missing > 0)
                Inventory->AddItemDefinition(Ammo, Missing, Id);
        }
    Weapon->RefillAmmo(false);
}
void UHoverCombatBridge::SelectQuickbar(int32 Slot)
{
    if (!Inventory || InventoryUI)
        return;
    SetTrigger(false);
    if (Slot == 0)
        for (int32 Offset = 1; Offset <= Inventory->GetQuickbarSize(); ++Offset)
        {
            const int32 Candidate =
                (Inventory->GetActiveQuickbarSlot() + Offset - 1) % Inventory->GetQuickbarSize() + 1;
            FZE_InventoryItemInstance Item;
            if (Inventory->GetQuickbarItem(Candidate, Item))
            {
                Slot = Candidate;
                break;
            }
        }
    if (Slot > 0)
    {
        if (auto *Weapon = Cast<AHoverCyberRifle>(GetWeapon()))
            Weapon->CancelReload();
        Inventory->SetActiveQuickbarSlot(Slot);
        Inventory->RequestEquipQuickbarSlot(Slot);
    }
}
void UHoverCombatBridge::CycleWeapon()
{
    if (!Inventory || InventoryUI)
        return;
    const int32 Size = Inventory->GetQuickbarSize();
    const int32 Active = Inventory->GetActiveQuickbarSlot();
    for (int32 Offset = 1; Offset < Size; ++Offset)
    {
        const int32 Candidate = (Active + Offset - 1) % Size + 1;
        FZE_InventoryItemInstance Item;
        if (Inventory->GetQuickbarItem(Candidate, Item) && Cast<UZE_WeaponDefinition>(Item.Definition))
        {
            UE_LOG(LogTemp, Display, TEXT("HOVER_CYCLE_WEAPON %d -> %d (%s)"), Active, Candidate,
                   *GetNameSafe(Item.Definition));
            SelectQuickbar(Candidate);
            return;
        }
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_CYCLE_WEAPON no other weapon on the quickbar"));
}
AHoverMeleeWeapon *UHoverCombatBridge::GetActiveMelee() const
{
    return bSpearSelected && SpearWeapon ? SpearWeapon.Get() : MeleeWeapon.Get();
}
int32 UHoverCombatBridge::FindSpearSlot() const
{
    if (!SpearDefinition || !Inventory)
        return 0;
    for (int32 Slot = 1; Slot <= Inventory->GetQuickbarSize(); ++Slot)
    {
        FZE_InventoryItemInstance Item;
        if (Inventory->GetQuickbarItem(Slot, Item) && Item.Definition.Get() == SpearDefinition.Get())
            return Slot;
    }
    return 0;
}
bool UHoverCombatBridge::GiveSpear(int32 Slot)
{
    if (!SpearDefinition || !Inventory)
        return false;
    if (FindSpearSlot() > 0)
        return true;
    FGuid Id;
    if (!Inventory->AddItemDefinition(SpearDefinition.Get(), 1, Id))
        return false;
    const bool Assigned = Inventory->AssignInstanceToQuickbar(Id, FMath::Clamp(Slot, 1, 5));
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPEAR_GIVEN slot=%d assigned=%d"), Slot, Assigned);
    return Assigned;
}
void UHoverCombatBridge::UpdateSpearSelection()
{
    bool Selected = false;
    if (SpearWeapon && SpearDefinition && Inventory)
    {
        FZE_InventoryItemInstance Item;
        Selected = Inventory->GetQuickbarItem(Inventory->GetActiveQuickbarSlot(), Item) &&
                   Item.Definition.Get() == SpearDefinition.Get();
    }
    if (Selected == bSpearSelected)
        return;
    bSpearSelected = Selected;
    SetTrigger(false);
    if (!Selected && SpearWeapon)
        SpearWeapon->OnHolstered();
    UE_LOG(LogTemp, Display, TEXT("HOVER_SPEAR_SELECTED %d slot=%d"), Selected,
           Inventory ? Inventory->GetActiveQuickbarSlot() : 0);
}
void UHoverCombatBridge::SetSpearTrigger(bool Held)
{
    if (SpearWeapon)
        SpearWeapon->SetAttackHeld(Held && bSpearSelected && !InventoryUI);
}
FString UHoverCombatBridge::GetSpearHudText() const
{
    if (!SpearWeapon)
        return FString();
    const FString &Name = SpearWeapon->GetProfile().HudName;
    if (!SpearWeapon->IsCharging())
        return Name;
    return FString::Printf(TEXT("%s  CHARGE %d%%"), *Name, FMath::RoundToInt(SpearWeapon->GetChargeAlpha() * 100.f));
}
void UHoverCombatBridge::UpdateInventoryCursor()
{
    if (!FSlateApplication::IsInitialized())
        return;
    const bool Needed = InventoryUI && FPlatformApplicationMisc::IsThisApplicationForeground();
    if (Needed && !InventoryCursor)
    {
        InventoryCursor = MakeShared<FHoverInventoryCursor>();
        InventoryCursor->SetDeadZone(.2f);
        InventoryCursor->SetMaxSpeed(650.f);
        FSlateApplication::Get().RegisterInputPreProcessor(InventoryCursor);
    }
    else if (!Needed && InventoryCursor)
    {
        FSlateApplication::Get().UnregisterInputPreProcessor(InventoryCursor);
        InventoryCursor.Reset();
    }
}
void UHoverCombatBridge::ToggleInventory()
{
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    auto *PC = Pilot ? Cast<APlayerController>(Pilot->GetController()) : nullptr;
    if (!PC || !Pilot->IsOnFoot())
        return;
    SetTrigger(false);
    if (PC->PlayerInput)
        PC->PlayerInput->FlushPressedKeys();
    Pilot->CancelPostureInput();
    if (MeleeWeapon)
        MeleeWeapon->CancelSwing();
    if (SpearWeapon)
        SpearWeapon->CancelSwing();
    if (InventoryUI)
    {
        InventoryUI->RemoveFromParent();
        InventoryUI = nullptr;
        UpdateInventoryCursor();
        PC->SetIgnoreMoveInput(false);
        PC->SetIgnoreLookInput(false);
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
        return;
    }
    auto *Class = LoadClass<UUserWidget>(nullptr, TEXT("/Game/ZESP/ZE/UI/Inventory/WBP_Inventory.WBP_Inventory_C"));
    if (!Class)
        return;
    InventoryUI = CreateWidget<UUserWidget>(PC, Class);
    InventoryUI->AddToViewport(500);
    if (auto *UI = Cast<UZE_InventoryWidgetBase>(InventoryUI))
        UI->OpenInventory();
    Pilot->GetCharacterMovement()->StopMovementImmediately();
    PC->SetIgnoreMoveInput(true);
    PC->SetIgnoreLookInput(true);
    FInputModeGameAndUI Mode;
    Mode.SetWidgetToFocus(InventoryUI->TakeWidget());
    Mode.SetHideCursorDuringCapture(false);
    PC->SetInputMode(Mode);
    PC->bShowMouseCursor = true;
    UpdateInventoryCursor();
}
FString UHoverCombatBridge::GetPrompt() const
{
    return Interaction && Interaction->HasFocusedInteractable()
               ? TEXT("Hold X / F: ") + Interaction->GetFocusedInteractText().ToString()
               : FString();
}
void UHoverCombatBridge::TickComponent(float DT, ELevelTick Type, FActorComponentTickFunction *Function)
{
    Super::TickComponent(DT, Type, Function);
    UpdateInventoryCursor();
    UpdateSpearSelection();
    auto *Pilot = Cast<AHoverPilot>(GetOwner());
    auto *PC = Pilot ? Cast<APlayerController>(Pilot->GetController()) : nullptr;
    if (!PC)
    {
        SetTrigger(false);
        InteractionHeld = 0;
        return;
    }
    if (auto *Weapon = GetWeapon())
    {
        Weapon->FinalizeEquipped();
        Weapon->SetActorHiddenInGame(true); // Ballista presentation stays on Vexa.
        // P0-1 auto-reload (enhanced gun feel): the vendor StopFires at 0 ammo and the rising-edge
        // SetTrigger would otherwise wait for a release.
        if (bTriggerHeld && Pilot->bEnhancedGunFeel && Pilot->IsOnFoot() && Weapon->GetCurrentClipAmmo() == 0 &&
            !Weapon->IsReloading() && Weapon->GetReserveAmmo() > 0)
            Reload();
    }
    if (InventoryUI && !InventoryUI->IsInViewport())
        ToggleInventory();
    if (!Pilot->IsOnFoot())
    {
        InteractionHeld = 0;
        return; // Mounted firing remains controlled by the pilot's R1 input.
    }
    AActor *Target = Interaction ? Interaction->GetFocusedActor() : nullptr;
    const bool Held =
        !InventoryUI && (PC->IsInputKeyDown(EKeys::Gamepad_FaceButton_Left) || PC->IsInputKeyDown(EKeys::F));
    if (Target != InteractionTarget.Get() || !Held)
    {
        InteractionHeld = 0;
        bInteracted = false;
        InteractionTarget = Target;
    }
    if (!Held || !Target || bInteracted)
        return;
    InteractionHeld += DT;
    const float Required = IZE_InteractableInterface::Execute_RequiresHold(Target, Pilot)
                               ? IZE_InteractableInterface::Execute_GetHoldDuration(Target, Pilot)
                               : .05f;
    if (InteractionHeld >= Required)
    {
        Interaction->TryInteract(Pilot);
        bInteracted = true;
    }
}
void UHoverCombatBridge::EndPlay(const EEndPlayReason::Type Reason)
{
    if (InventoryUI)
        InventoryUI->RemoveFromParent();
    InventoryUI = nullptr;
    UpdateInventoryCursor();
    if (Weapons)
        Weapons->UnequipCurrentWeapon();
    if (SpearWeapon)
        SpearWeapon->Destroy();
    SpearWeapon = nullptr;
    Super::EndPlay(Reason);
}
