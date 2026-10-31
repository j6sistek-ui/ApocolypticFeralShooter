#include "HoverCombatBridge.h"
#include "HoverPilot.h"
#include "HoverLocomotionBridge.h"
#include "HoverAnimInstance.h"
#include "HoverCyberCity.h"
#include "HoverGunFeel.h"
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
    SwingEnd = 0;
    SetActorHiddenInGame(true);
    StaticMeshTP->SetVisibility(false);
    StaticMeshFP->SetVisibility(false);
}
void AHoverMeleeWeapon::EndPlay(const EEndPlayReason::Type Reason)
{
    CancelSwing();
    Super::EndPlay(Reason);
}
void AHoverMeleeWeapon::Tick(float DT)
{
    Super::Tick(DT);
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    const bool Active = Pilot && Pilot->IsOnFoot() && !Pilot->IsKnockedDown() && !Pilot->IsDefeated() &&
                        !(Pilot->Combat && Pilot->Combat->IsInventoryOpen()) &&
                        (Pilot->IsMeleeEquipped() || IsSwinging());
    SetFirstPersonDetail(Active && !Pilot->IsThirdPersonView());
    SetActorHiddenInGame(!Active);
    if (!Active)
    {
        StaticMeshTP->SetVisibility(false);
        StaticMeshFP->SetVisibility(false);
        return;
    }
    ConfigureGrip(Pilot);
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
    for (FTimerHandle &Timer : SwingTimers)
        GetWorldTimerManager().ClearTimer(Timer);
    SwingTimers.Reset();
    SwingHits.Reset();
    for (const float At : {.22f, .30f, .38f, .48f})
        GetWorldTimerManager().SetTimer(SwingTimers.AddDefaulted_GetRef(),
                                        FTimerDelegate::CreateUObject(this, &AHoverMeleeWeapon::SweepOnce), At, false);
}

void AHoverMeleeWeapon::SweepOnce()
{
    auto *Pilot = Cast<AHoverPilot>(OwnerPawn);
    if (!Pilot || !Pilot->IsOnFoot() || !IsSwinging() || !GetWorld())
        return;
    const float Range = WeaponDefinition ? WeaponDefinition->MeleeStats.MeleeRange : 150.f;
    const float Radius = FMath::Max(50.f, WeaponDefinition ? WeaponDefinition->MeleeStats.MeleeRadius * 2.5f : 50.f);
    const FVector Start = Pilot->GetActorLocation() + FVector(0, 0, 15.f);
    const FVector Forward = FRotator(0.f, Pilot->GetControlRotation().Yaw, 0.f).Vector();
    const FVector End = Start + Forward * (Range + 30.f);
    TArray<FHitResult> Hits;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverKatanaSweep), false, this);
    Params.AddIgnoredActor(OwnerPawn);
    Params.bReturnPhysicalMaterial = true;
    GetWorld()->SweepMultiByChannel(Hits, Start, End, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeSphere(Radius),
                                    Params);
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
        ProcessHit(Hit);
        ++Struck;
    }
    if (Struck)
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_KATANA_SWEEP struck=%d radius=%.0f range=%.0f"), Struck, Radius, Range);
}
void AHoverMeleeWeapon::PlayFireAnimation()
{
    LastFireAnimTime = GetWorld()->GetTimeSeconds();
    SwingEnd = LastFireAnimTime + .8f;
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn))
        Pilot->PlayMeleeSwingSound(); // audio pass 2026-10-31
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
    {
        ConfigureGrip(Pilot);
        auto *Clip = LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Animations/QA_Katana.QA_Katana"));
        Pilot->LocomotionBridge->PlayAction(Clip, .8f);
        if (Clip && Pilot->ViewArms)
            if (auto *View = Cast<UHoverViewAnimInstance>(Pilot->ViewArms->GetAnimInstance()))
            {
                View->bMelee = true;
                auto *ViewClip = LoadObject<UAnimSequence>(
                    nullptr, TEXT("/Game/HoverPrototype/Animations/QA_KatanaView.QA_KatanaView"));
                if (ViewClip)
                    View->PlaySlotAnimationAsDynamicMontage(ViewClip, TEXT("DefaultSlot"), .08f, .15f,
                                                            ViewClip->GetPlayLength() / .8f);
            }
    }
}
void AHoverMeleeWeapon::ConfigureGrip(AHoverPilot *Pilot)
{
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
    Super::EndPlay(Reason);
}
