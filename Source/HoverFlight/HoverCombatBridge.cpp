#include "HoverCombatBridge.h"
#include "HoverPilot.h"
#include "HoverLocomotionBridge.h"
#include "Inventory/ZE_InventoryComponent.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Inventory/ZE_AmmoDefinition.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "Weapons/ZE_WeaponComponent.h"
#include "Interaction/ZE_InteractionTraceComponent.h"
#include "Interaction/ZE_InteractableInterface.h"
#include "UI/ZE_InventoryWidgetBase.h"
#include "Animation/AnimSequence.h"
#include "Blueprint/UserWidget.h"
#include "GameFramework/PlayerController.h"
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

void AHoverCyberRifle::PerformLineTrace()
{
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && WeaponDefinition)
        Pilot->FireShot(WeaponDefinition->CombatStats.Damage, CurrentSpread, WeaponDefinition->CombatStats.Range);
}
void AHoverCyberRifle::OnEquipped_Implementation(APawn *NewOwnerPawn)
{
    Super::OnEquipped_Implementation(NewOwnerPawn);
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
}
void AHoverCyberRifle::OnUnequipped_Implementation(APawn *OldOwnerPawn)
{
    if (auto *Pilot = Cast<AHoverPilot>(OldOwnerPawn); Pilot && Pilot->Combat && ItemId.IsValid())
        Pilot->Combat->SavedMagazines.Add(ItemId, CurrentClipAmmo);
    CancelReload();
    Super::OnUnequipped_Implementation(OldOwnerPawn);
}
void AHoverCyberRifle::PlayFireAnimation()
{
    // Existing Ballista presentation emits one flash/sound/tracer per vendor-approved shot.
    LastFireAnimTime = GetWorld()->GetTimeSeconds();
}
void AHoverCyberRifle::Reload()
{
    const bool WasReloading = IsReloading();
    Super::Reload();
    if (!WasReloading && IsReloading())
        if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge && Pilot->IsOnFoot())
            Pilot->LocomotionBridge->PlayAction(
                LoadObject<UAnimSequence>(
                    nullptr,
                    TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/MM_Rifle_Reload.MM_Rifle_Reload")),
                ReloadDuration);
}
void AHoverCyberRifle::CancelReload()
{
    GetWorldTimerManager().ClearTimer(ReloadTimerHandle);
    bIsReloading = false;
    StopFire();
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
        Pilot->LocomotionBridge->CancelAction();
}
void AHoverMeleeWeapon::PlayFireAnimation()
{
    LastFireAnimTime = GetWorld()->GetTimeSeconds();
    if (auto *Pilot = Cast<AHoverPilot>(OwnerPawn); Pilot && Pilot->LocomotionBridge)
        Pilot->LocomotionBridge->PlayAction(
            LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Animations/QA_Melee.QA_Melee")));
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
    const auto *Waves = LoadObject<UZE_WaveGameModeSettings>(
        nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_CyberWaves.DA_CyberWaves"));
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
        Inventory->SetActiveQuickbarSlot(1);
        if (auto *Weapon = GetWeapon())
            Weapon->FinalizeEquipped();
    }
    MeleeWeapon = GetWorld()->SpawnActor<AHoverMeleeWeapon>();
    if (MeleeWeapon)
    {
        MeleeWeapon->SetWeaponDefinition(LoadObject<UZE_WeaponDefinition>(
            nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_AFS_Melee.DA_AFS_Melee")));
        MeleeWeapon->Equip(Pilot);
        MeleeWeapon->SetActorHiddenInGame(true);
    }
}
AZE_WeaponBase *UHoverCombatBridge::GetWeapon() const
{
    return Weapons ? Weapons->GetCurrentWeapon() : nullptr;
}
void UHoverCombatBridge::SetTrigger(bool Held)
{
    Held = Held && !InventoryUI;
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
    if (!InventoryUI)
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
    if (!Pilot || !Pilot->IsOnFoot() || InventoryUI || !MeleeWeapon)
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
    if (MeleeWeapon)
        MeleeWeapon->Destroy();
    if (Weapons)
        Weapons->UnequipCurrentWeapon();
    Super::EndPlay(Reason);
}
