#include "HoverTestController.h"
#include "HoverLocomotionBridge.h"
#include "HoverPilot.h"
#include "HoverCombatBridge.h"
#include "HoverAnimInstance.h"
#include "InputModifiers.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "InputAction.h"
#include "ChaosWheeledVehicleMovementComponent.h"
#include "Blueprint/WidgetLayoutLibrary.h"
#include "HoverGraphicsMenu.h"
#include "HoverGraphicsSettings.h"
#include "GameFramework/PlayerInput.h"
#include "InputKeyEventArgs.h"
#include "PhysicsEngine/PhysicsThrusterComponent.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Misc/PackageName.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

void AHoverTestController::BeginPlay()
{
    Super::BeginPlay();
#if WITH_EDITOR
    bSpawnAttempted = FParse::Param(FCommandLine::Get(), TEXT("AFSReviewNoVehicles"));
#endif
    GraphicsSettings = NewObject<UHoverGraphicsSettings>(this);
    GraphicsSettings->Initialize(GetWorld());
}

void AHoverTestController::EndPlay(const EEndPlayReason::Type Reason)
{
    if (GraphicsMenu)
        CloseGraphicsMenu(false);
    if (GraphicsSettings)
        GraphicsSettings->RestoreRenderer();
    Super::EndPlay(Reason);
}

void AHoverTestController::HoverGraphics()
{
    if (GraphicsMenu)
    {
        CloseGraphicsMenu(false);
        return;
    }
    if (!GraphicsSettings || IsPaused() || !SetPause(true))
        return;
    if (auto *ActivePilot = Cast<AHoverPilot>(GetPawn()))
    {
        ActivePilot->CancelPostureInput();
        if (ActivePilot->Combat && ActivePilot->Combat->IsInventoryOpen())
            ActivePilot->Combat->ToggleInventory();
    }
    GraphicsMenu = CreateWidget<UHoverGraphicsMenu>(this);
    GraphicsMenu->Open(GraphicsSettings);
    GraphicsMenu->AddToViewport(10000);
    SetIgnoreMoveInput(true);
    SetIgnoreLookInput(true);
    if (PlayerInput)
        PlayerInput->FlushPressedKeys();
    SetInputMode(FInputModeGameOnly());
    bShowMouseCursor = false;
}

void AHoverTestController::CloseGraphicsMenu(bool bApply)
{
    if (!GraphicsMenu)
        return;
    const int32 Level = GraphicsMenu->GetSelectedLevel();
    const bool ChangeLevel =
        bApply && Level != (UGameplayStatics::GetCurrentLevelName(this).Contains(TEXT("Cyber")) ? 1 : 0);
    if (bApply)
        GraphicsSettings->Apply(GraphicsMenu->GetSelection());
    GraphicsMenu->RemoveFromParent();
    GraphicsMenu = nullptr;
    if (PlayerInput)
        PlayerInput->FlushPressedKeys();
    ExitHold = 0;
    bExitConsumed = true;
    SetIgnoreMoveInput(false);
    SetIgnoreLookInput(false);
    SetPause(false);
    if (ChangeLevel)
        HoverLoadLevel(Level);
}

void AHoverTestController::HoverLoadLevel(int32 Level)
{
    const FName Map(Level == 1 ? TEXT("/Game/HoverPrototype/Maps/L_CyberCity")
                               : TEXT("/Game/JustBStudios/PostApo/Levels/PostApo"));
    if (!FPackageName::DoesPackageExist(Map.ToString()))
    {
        ClientMessage(TEXT("That test level is not installed yet."));
        return;
    }
    UGameplayStatics::OpenLevel(this, Map, true,
                                Level == 1
                                    ? TEXT("game=/Game/HoverPrototype/ZombieEngine/BP_CyberWaves.BP_CyberWaves_C")
                                    : TEXT("game=/Script/HoverFlight.HoverGameMode"));
}

bool AHoverTestController::InputKey(const FInputKeyEventArgs &Params)
{
#if WITH_EDITOR
    if (bTestInputOnly && !bInjectingTestKey)
        return false;
#endif
    const bool Pressed = Params.Event == IE_Pressed;
    const FKey Key = Params.Key;
    if (!GraphicsMenu)
        if (auto *ActivePilot = Cast<AHoverPilot>(GetPawn());
            ActivePilot && ActivePilot->Combat && ActivePilot->Combat->IsInventoryOpen())
        {
            if (Pressed && (Key == EKeys::Gamepad_FaceButton_Right || Key == EKeys::Escape || Key == EKeys::Tab ||
                            Key == EKeys::Gamepad_DPad_Down))
                ActivePilot->Combat->ToggleInventory();
            else if (Pressed && (Key == EKeys::F6 || Key == EKeys::Gamepad_DPad_Up))
                HoverGraphics();
            // Slate handles the inventory cursor/click first. Unhandled UI keys
            // must not stand up from prone, jump or reach the Parkour Blueprint.
            return true;
        }
    if (!GraphicsMenu)
    {
        if (Pressed && (Key == EKeys::Gamepad_RightThumbstick || Key == EKeys::V))
            if (auto *ActivePilot = Cast<AHoverPilot>(GetPawn()))
            {
                ActivePilot->Melee();
                return true;
            }
        if (auto *P = Cast<AHoverPilot>(GetPawn());
            Pressed && P && P->IsProne() && (Key == EKeys::SpaceBar || Key == EKeys::Gamepad_FaceButton_Bottom))
        {
            P->UnCrouch();
            return true;
        }
        if (auto *P = Cast<AHoverPilot>(GetPawn()); Pressed && P && P->Combat)
        {
            if (P->Combat->IsInventoryOpen() && Key == EKeys::Gamepad_FaceButton_Right)
            {
                P->Combat->ToggleInventory();
                return true;
            }
            const FKey Slots[] = {EKeys::One, EKeys::Two, EKeys::Three, EKeys::Four, EKeys::Five};
            for (int32 I = 0; I < 5; ++I)
                if (Key == Slots[I])
                {
                    P->Combat->SelectQuickbar(I + 1);
                    return true;
                }
            if (Key == EKeys::Gamepad_DPad_Left)
            {
                P->Combat->SelectQuickbar();
                return true;
            }
            if (Key == EKeys::R)
            {
                P->Combat->Reload();
                return true;
            }
            if (Key == EKeys::Tab || Key == EKeys::Gamepad_DPad_Down ||
                (Key == EKeys::Escape && P->Combat->IsInventoryOpen()))
            {
                P->Combat->ToggleInventory();
                return true;
            }
        }
        if (Pressed && (Key == EKeys::F7 || Key == EKeys::Gamepad_DPad_Right))
            if (auto *ActivePilot = Cast<AHoverPilot>(GetPawn());
                ActivePilot && ActivePilot->IsOnFoot() && !ActivePilot->GetCharacterMovement()->IsFalling())
                if (auto *Bridge = ActivePilot->FindComponentByClass<UHoverLocomotionBridge>())
                {
                    Bridge->bEnabled = !Bridge->bEnabled;
                    ActivePilot->GetCharacterMovement()->GroundFriction = 8;
                    ActivePilot->GetCharacterMovement()->BrakingDecelerationWalking = 2048;
                    return true;
                }
        if (Pressed && (Key == EKeys::F6 || Key == EKeys::Gamepad_DPad_Up))
        {
            HoverGraphics();
            return true;
        }
        // The template's jump buffer is bound to Space; feed the same event
        // for controller A instead of bypassing it with a second jump implementation.
        if (auto *P = Cast<AHoverPilot>(GetPawn());
            P && P->bParkourMovement && P->IsOnFoot() &&
            (Key == EKeys::Gamepad_FaceButton_Bottom || Key == EKeys::Gamepad_FaceButton_Right))
        {
            FInputKeyEventArgs Jump = Params;
            if (Key == EKeys::Gamepad_FaceButton_Right)
            {
                P->SetParkourCrouch(Params.Event != IE_Released);
                return true;
            }
            Jump.Key = EKeys::SpaceBar;
            Super::InputKey(Jump);
        }
        return Super::InputKey(Params);
    }
    // Intercept before pawn/vendor input, including axes and trigger input while paused.
    if (Pressed || Params.Event == IE_Repeat)
    {
        if (Key == EKeys::Up || Key == EKeys::Gamepad_DPad_Up)
            GraphicsMenu->Navigate(-1);
        else if (Key == EKeys::Down || Key == EKeys::Gamepad_DPad_Down)
            GraphicsMenu->Navigate(1);
        else if (Key == EKeys::Left || Key == EKeys::Gamepad_DPad_Left)
            GraphicsMenu->Adjust(-1);
        else if (Key == EKeys::Right || Key == EKeys::Gamepad_DPad_Right)
            GraphicsMenu->Adjust(1);
        else if (Pressed && (Key == EKeys::Enter || Key == EKeys::Gamepad_FaceButton_Bottom))
            CloseGraphicsMenu(true);
        else if (Pressed && (Key == EKeys::F6 || Key == EKeys::Escape || Key == EKeys::Gamepad_FaceButton_Right))
            CloseGraphicsMenu(false);
    }
    return true;
}

void AHoverTestController::UpdateBikeMappings()
{
    auto *Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer());
    auto *Source = LoadObject<UInputMappingContext>(
        nullptr, TEXT("/Game/ScifiHoverbike/Vehicles/Inputs/Mappings/"
                      "IMC_ExampleVehicleInputMappingContext.IMC_ExampleVehicleInputMappingContext"));
    if (!Subsystem || !Source)
        return;
    if (GetPawn() != Bike)
    {
        if (BikeMappings)
            Subsystem->RemoveMappingContext(BikeMappings);
        return;
    }
    if (!BikeMappings)
    {
        BikeMappings = DuplicateObject<UInputMappingContext>(Source, this);
        for (int32 I = BikeMappings->GetMappings().Num() - 1; I >= 0; --I)
        {
            auto &Mapping = BikeMappings->GetMapping(I);
            if (Mapping.Key == EKeys::Gamepad_LeftY || Mapping.Key == EKeys::Gamepad_FaceButton_Bottom)
                BikeMappings->UnmapKey(Mapping.Action, Mapping.Key);
            else if (Mapping.Key == EKeys::Gamepad_RightX)
                Mapping.Modifiers.RemoveAll(
                    [](const UInputModifier *M) { return M && M->IsA<UInputModifierNegate>(); });
        }
        for (const auto &Mapping : Source->GetMappings())
            if (Mapping.Action && Mapping.Action->GetName() == TEXT("Input_AxisVehicleThrottle"))
            {
                BikeMappings->MapKey(Mapping.Action, EKeys::Gamepad_RightTriggerAxis);
                auto &Reverse = BikeMappings->MapKey(Mapping.Action, EKeys::Gamepad_LeftTriggerAxis);
                Reverse.Modifiers.Add(NewObject<UInputModifierNegate>(BikeMappings));
                break;
            }
        for (const auto &Mapping : Source->GetMappings())
            if (Mapping.Action && Mapping.Action->GetName() == TEXT("Input_ActionVehicleBoost"))
            {
                BikeMappings->MapKey(Mapping.Action, EKeys::Gamepad_FaceButton_Right);
                break;
            }
    }
    if (Subsystem->HasMappingContext(Source))
        Subsystem->RemoveMappingContext(Source);
    if (!Subsystem->HasMappingContext(BikeMappings))
        Subsystem->AddMappingContext(BikeMappings, 1);
}

bool AHoverTestController::IsNearTruck() const
{
    return Truck && Pilot && !Pilot->IsMounted() &&
           FMath::Abs(Pilot->GetActorLocation().Z - Truck->GetActorLocation().Z) < 220.f &&
           FVector::Dist2D(Pilot->GetActorLocation(), Truck->GetActorLocation()) < 420.f;
}

bool AHoverTestController::IsNearBike() const
{
    return Bike && Pilot && !Pilot->IsMounted() &&
           FMath::Abs(Pilot->GetActorLocation().Z - Bike->GetActorLocation().Z) < 220.f &&
           FVector::Dist2D(Pilot->GetActorLocation(), Bike->GetActorLocation()) < 280.f;
}

bool AHoverTestController::TryEnterBike()
{
    const bool bTruck =
        IsNearTruck() && (!IsNearBike() || FVector::Dist2D(Pilot->GetActorLocation(), Truck->GetActorLocation()) <
                                               FVector::Dist2D(Pilot->GetActorLocation(), Bike->GetActorLocation()));
    if (!bTruck && !IsNearBike())
        return false;
    if (!Pilot->PrepareForRide())
        return false;
    Pilot->SetActorHiddenInGame(true);
    Pilot->SetActorEnableCollision(false);
    Pilot->GetCharacterMovement()->StopMovementImmediately();
    Pilot->GetCharacterMovement()->DisableMovement();
    Pilot->SetActorTickEnabled(false);
    Possess(bTruck ? Truck : Bike);
    if (!bTruck)
        SetBikeParked(false);
    if (bTruck)
    {
        if (auto *Move = Truck->FindComponentByClass<UChaosWheeledVehicleMovementComponent>())
        {
            Move->SetHandbrakeInput(false);
            Move->SetBrakeInput(0);
        }
        if (auto *Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
            if (auto *Mapping = LoadObject<UInputMappingContext>(
                    nullptr, TEXT("/Game/Crossroad_Pickup/Input/IMC_Default.IMC_Default")))
                Subsystem->AddMappingContext(Mapping, 0);
    }
    ExitHold = 0;
    bExitConsumed = true;
    UE_LOG(LogTemp, Display, TEXT("HOVER_VEHICLE entered %s"), *GetNameSafe(GetPawn()));
    return true;
}

void AHoverTestController::SetBikeParked(bool bParked)
{
    if (!Bike)
        return;
    // Enhanced Input does not guarantee a Completed event after possession changes.
    // Clear both the vendor's cached controls and the physics inputs.
    for (const FName Name : {FName("ThrottleInput"), FName("SteeringInput"), FName("SteeringAngle")})
        if (auto *P = FindFProperty<FDoubleProperty>(Bike->GetClass(), Name))
            P->SetPropertyValue_InContainer(Bike, 0.0);
    for (const FName Name : {FName("BoostPressed"), FName("BoostActivated")})
        if (auto *P = FindFProperty<FBoolProperty>(Bike->GetClass(), Name))
            P->SetPropertyValue_InContainer(Bike, false);
    if (auto *P = FindFProperty<FBoolProperty>(Bike->GetClass(), TEXT("bHandbrake")))
        P->SetPropertyValue_InContainer(Bike, bParked);
    if (auto *P = FindFProperty<FObjectProperty>(Bike->GetClass(), TEXT("BoostThruster")))
        if (auto *Thruster = Cast<UPhysicsThrusterComponent>(P->GetObjectPropertyValue_InContainer(Bike)))
            Thruster->ThrustStrength = 0;
    if (auto *Move = Bike->FindComponentByClass<UChaosWheeledVehicleMovementComponent>())
    {
        Move->SetRequiresControllerForInputs(!bParked);
        Move->SetThrottleInput(0);
        Move->SetSteeringInput(0);
        Move->SetBrakeInput(bParked ? 1.f : 0.f);
        Move->SetHandbrakeInput(bParked);
        Move->SetUseAutomaticGears(!bParked);
        Move->SetTargetGear(bParked ? 0 : 1, true);
    }
    if (!bParked && bBikeParkingLock)
        if (auto *Body = Cast<UPrimitiveComponent>(Bike->GetRootComponent()))
            if (FBodyInstance *BI = Body->GetBodyInstance())
            {
                BI->bLockXTranslation = bBikeLockX;
                BI->bLockYTranslation = bBikeLockY;
                BI->bLockZRotation = bBikeLockYaw;
                BI->SetDOFLock(static_cast<EDOFMode::Type>(BikeSavedDOF));
                bBikeParkingLock = false;
            }
    if (bParked)
        if (auto *Body = Cast<UPrimitiveComponent>(Bike->GetRootComponent()); Body && Body->IsSimulatingPhysics())
        {
            // The hover lift can unload the tires, so wheel brakes alone cannot
            // park it reliably. Apply horizontal drag without suppressing gravity.
            FVector Planar = Body->GetPhysicsLinearVelocity();
            Planar.Z = 0;
            Body->AddForce(-Planar * 6.f, NAME_None, true);
            const FVector Spin = Body->GetPhysicsAngularVelocityInRadians();
            Body->AddTorqueInRadians(FVector(0, 0, -Spin.Z * 6.f), NAME_None, true);
            // Once nearly stopped over ground, engage a planar parking constraint.
            // Hover lift unloads wheel brakes; this prevents residual sideways creep
            // while leaving gravity, vertical suspension, pitch and roll simulated.
            if (!bBikeParkingLock && Planar.Size() < 150.f)
            {
                FHitResult Floor;
                FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverbikeParking), false, Bike);
                Params.AddIgnoredActor(Pilot);
                const FVector P = Body->GetComponentLocation();
                if (GetWorld()->LineTraceSingleByChannel(Floor, P + FVector(0, 0, 100), P - FVector(0, 0, 180),
                                                         ECC_Visibility, Params) &&
                    Floor.ImpactNormal.Z > .5f)
                    if (FBodyInstance *BI = Body->GetBodyInstance())
                    {
                        bBikeLockX = BI->bLockXTranslation;
                        bBikeLockY = BI->bLockYTranslation;
                        bBikeLockYaw = BI->bLockZRotation;
                        BikeSavedDOF = uint8(BI->DOFMode.GetValue());
                        BI->bLockXTranslation = BI->bLockYTranslation = BI->bLockZRotation = true;
                        BI->SetDOFLock(EDOFMode::SixDOF);
                        bBikeParkingLock = true;
                    }
            }
        }
}

void AHoverTestController::ExitTruck()
{
    if (!Truck || !Pilot)
        return;
    FVector Exit = FVector::ZeroVector;
    bool bClear = false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(TruckExit), false, Pilot);
    for (float Side : {-1.f, 1.f})
    {
        Exit = Truck->GetActorLocation() + Truck->GetActorRightVector() * Side * 250.f + FVector(0, 0, 140);
        FHitResult Floor;
        if (GetWorld()->LineTraceSingleByChannel(Floor, Exit + FVector(0, 0, 150), Exit - FVector(0, 0, 800),
                                                 ECC_Visibility, Params))
            Exit.Z = Floor.ImpactPoint.Z + 100.f;
        if (!GetWorld()->OverlapBlockingTestByChannel(Exit, FQuat::Identity, ECC_Pawn,
                                                      FCollisionShape::MakeCapsule(32.f, 97.f), Params))
        {
            bClear = true;
            break;
        }
    }
    if (!bClear)
        return;
    if (auto *Move = Truck->FindComponentByClass<UChaosWheeledVehicleMovementComponent>())
    {
        Move->SetThrottleInput(0);
        Move->SetBrakeInput(1);
        Move->SetHandbrakeInput(true);
    }
    if (auto *Subsystem = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(GetLocalPlayer()))
        if (auto *Mapping =
                LoadObject<UInputMappingContext>(nullptr, TEXT("/Game/Crossroad_Pickup/Input/IMC_Default.IMC_Default")))
            Subsystem->RemoveMappingContext(Mapping);
    Pilot->SetActorLocationAndRotation(Exit, Truck->GetActorRotation());
    Pilot->SetActorHiddenInGame(false);
    Pilot->SetActorEnableCollision(true);
    Pilot->SetActorTickEnabled(true);
    Pilot->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
    Possess(Pilot);
    UWidgetLayoutLibrary::RemoveAllWidgets(this);
    SetInputMode(FInputModeGameOnly());
    bShowMouseCursor = false;
    UE_LOG(LogTemp, Display, TEXT("HOVER_TRUCK returned to Vexa"));
}

void AHoverTestController::DressDriver()
{
    if (!Bike)
        return;
    FObjectProperty *Property = FindFProperty<FObjectProperty>(Bike->GetClass(), TEXT("PlayerCharacterRef"));
    ACharacter *Driver = Property ? Cast<ACharacter>(Property->GetObjectPropertyValue_InContainer(Bike)) : nullptr;
    if (!Driver || Driver == DressedDriver)
        return;
    Driver->SetCanBeDamaged(false);
    auto *Assets = LoadObject<UHoverPilotAssets>(nullptr, TEXT("/Game/HoverPrototype/DA_HoverPilot.DA_HoverPilot"));
    if (!Assets || Assets->BodyParts.IsEmpty())
        return;
    USkeletalMeshComponent *Leader = Driver->GetMesh();
    UClass *AnimClass = Leader->GetAnimClass();
    for (int32 I = 0; I < Assets->BodyParts.Num(); ++I)
    {
        const auto &Part = Assets->BodyParts[I];
        USkeletalMeshComponent *C = I == 0 ? Leader : NewObject<USkeletalMeshComponent>(Driver, Part.Name);
        if (I != 0)
        {
            C->SetupAttachment(Leader);
            C->RegisterComponent();
            C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        }
        C->SetSkeletalMesh(Part.Mesh);
        C->bCastContactShadow = true;
        if (Part.PhysicsOverride)
            C->SetPhysicsAsset(Part.PhysicsOverride);
        for (int32 J = 0; J < Part.Materials.Num(); ++J)
            C->SetMaterial(J, Part.Materials[J]);
        if (I != 0)
        {
            if (C->GetBoneIndex(TEXT("afs_chain_01")) != INDEX_NONE)
            {
                C->SetAnimInstanceClass(UHoverAccessoryAnimInstance::StaticClass());
                C->AddTickPrerequisiteComponent(Leader);
                C->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            }
            else
                C->SetLeaderPoseComponent(Leader);
        }
        for (const auto &Morph : Part.Morphs)
            C->SetMorphTarget(Morph.Key, Morph.Value);
    }
    Leader->SetAnimInstanceClass(AnimClass);
    if (auto *AnimProperty = FindFProperty<FObjectProperty>(Driver->GetClass(), TEXT("As ABP Quinn")))
        AnimProperty->SetObjectPropertyValue_InContainer(Driver, Leader->GetAnimInstance());
    if (UFunction *Driving = Driver->FindFunction(TEXT("PlayerInVehicle")))
        Driver->ProcessEvent(Driving, nullptr);
    Leader->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    DressedDriver = Driver;
    UE_LOG(LogTemp, Display, TEXT("HOVER_BIKE Vexa appearance applied to supplied rider"));
}

void AHoverTestController::PlayerTick(float DT)
{
    Super::PlayerTick(DT);
    if (GraphicsMenu)
        return;
    if (auto *P = Cast<AHoverPilot>(GetPawn()))
        Pilot = P;
    UpdateBikeMappings();
    if (Pilot && !bSpawnAttempted)
    {
        bSpawnAttempted = true;
        auto RideStart = [this](FName Tag, FVector Offset) {
            TArray<AActor *> Starts;
            UGameplayStatics::GetAllActorsWithTag(this, Tag, Starts);
            return Starts.IsEmpty() ? Pilot->GetActorLocation() + Offset : Starts[0]->GetActorLocation();
        };
        UClass *Class =
            LoadClass<APawn>(nullptr, TEXT("/Game/ScifiHoverbike/Vehicles/Blueprint/BP_Hoverbike.BP_Hoverbike_C"));
        if (Class)
        {
            FVector Location = RideStart(TEXT("AFS_BikeStart"), FVector(550, 120, 80));
            FHitResult Floor;
            FCollisionQueryParams Params(SCENE_QUERY_STAT(BikeSpawn), false, Pilot);
            if (GetWorld()->LineTraceSingleByChannel(Floor, Location + FVector(0, 0, 500),
                                                     Location - FVector(0, 0, 2000), ECC_Visibility, Params))
                Location.Z = Floor.ImpactPoint.Z + 150;
            FTransform Transform(Pilot->GetActorRotation(), Location);
            Bike = GetWorld()->SpawnActorDeferred<APawn>(
                Class, Transform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
            if (Bike)
            {
                Bike->AutoPossessPlayer = EAutoReceiveInput::Disabled;
                UGameplayStatics::FinishSpawningActor(Bike, Transform);
            }
        }
        UClass *TruckClass = LoadClass<APawn>(
            nullptr, TEXT("/Game/Crossroad_Pickup/Blueprints/BP_Crossroad_Pickup.BP_Crossroad_Pickup_C"));
        if (TruckClass)
        {
            FVector Location = RideStart(TEXT("AFS_TruckStart"), FVector(350, -650, 150));
            FHitResult Floor;
            FCollisionQueryParams Params(SCENE_QUERY_STAT(TruckSpawn), false, Pilot);
            if (GetWorld()->LineTraceSingleByChannel(Floor, Location + FVector(0, 0, 500),
                                                     Location - FVector(0, 0, 2000), ECC_Visibility, Params))
                Location.Z = Floor.ImpactPoint.Z + 120;
            FTransform Transform(Pilot->GetActorRotation(), Location);
            Truck = GetWorld()->SpawnActorDeferred<APawn>(
                TruckClass, Transform, nullptr, nullptr,
                ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn);
            if (Truck)
            {
                Truck->AutoPossessPlayer = EAutoReceiveInput::Disabled;
                UGameplayStatics::FinishSpawningActor(Truck, Transform);
                // Vendor BeginPlay only initializes this reference when already possessed.
                if (auto *Property = FindFProperty<FObjectProperty>(Truck->GetClass(),
                                                                    TEXT("Chaos Wheeled Vehicle Movement Component")))
                    Property->SetObjectPropertyValue_InContainer(
                        Truck, Truck->FindComponentByClass<UChaosWheeledVehicleMovementComponent>());
            }
        }
    }
    if (GetPawn() == Truck && Truck)
    {
        // X is a supplied truck throttle binding. Y exits without replacing that control.
        const bool Held = IsInputKeyDown(EKeys::X) || IsInputKeyDown(EKeys::Gamepad_FaceButton_Top);
        if (!Held)
        {
            ExitHold = 0;
            bExitConsumed = false;
        }
        if (Held && !bExitConsumed)
        {
            ExitHold += DT;
            if (ExitHold >= .65f)
            {
                bExitConsumed = true;
                ExitTruck();
            }
        }
    }
    else if (GetPawn() == Bike && Bike)
    {
        DressDriver();
        // Keep the supplied exit action, with a clear placement for its spawned demo pawn.
        if (auto *Property = FindFProperty<FObjectProperty>(Bike->GetClass(), TEXT("ExitLocation")))
        {
            auto *ExitPoint = Cast<USceneComponent>(Property->GetObjectPropertyValue_InContainer(Bike));
            FCollisionQueryParams Params(SCENE_QUERY_STAT(BikeExit), false, Pilot);
            for (float Side : {-1.f, 1.f})
            {
                FVector Exit =
                    Bike->GetActorLocation() + Bike->GetActorRightVector() * Side * 220.f + FVector(0, 0, 130);
                FHitResult Floor;
                if (GetWorld()->LineTraceSingleByChannel(Floor, Exit + FVector(0, 0, 150), Exit - FVector(0, 0, 800),
                                                         ECC_Visibility, Params))
                    Exit.Z = Floor.ImpactPoint.Z + 105;
                if (ExitPoint && !GetWorld()->OverlapBlockingTestByChannel(
                                     Exit, FQuat::Identity, ECC_Pawn, FCollisionShape::MakeCapsule(45, 100), Params))
                {
                    ExitPoint->SetWorldLocation(Exit);
                    break;
                }
            }
        }
        const bool Held = IsInputKeyDown(EKeys::X) || IsInputKeyDown(EKeys::Gamepad_FaceButton_Left);
        if (!Held)
        {
            ExitHold = 0;
            bExitConsumed = false;
        }
        if (Held && !bExitConsumed)
        {
            ExitHold += DT;
            if (ExitHold >= .65f)
            {
                bExitConsumed = true;
                SetBikeParked(true);
                if (UFunction *Eject = Bike->FindFunction(TEXT("EjectPlayer")))
                    Bike->ProcessEvent(Eject, nullptr);
            }
        }
    }
    else if (Pilot && Bike && GetPawn() && GetPawn() != Pilot)
    {
        SetBikeParked(true);
        // The supplied E action creates its demo pawn. Hand control back to the retained Vexa.
        APawn *ExitPawn = GetPawn();
        const FVector Exit = ExitPawn->GetActorLocation();
        const FRotator Rotation = ExitPawn->GetActorRotation();
        Pilot->SetActorLocationAndRotation(Exit, Rotation);
        Pilot->SetActorHiddenInGame(false);
        Pilot->SetActorEnableCollision(true);
        Pilot->SetActorTickEnabled(true);
        Pilot->GetCharacterMovement()->SetMovementMode(MOVE_Falling);
        Possess(Pilot);
        ExitPawn->Destroy();
        UWidgetLayoutLibrary::RemoveAllWidgets(this);
        SetInputMode(FInputModeGameOnly());
        bShowMouseCursor = false;
        DressedDriver = nullptr;
        UE_LOG(LogTemp, Display, TEXT("HOVER_BIKE returned to Vexa"));
    }
    if (Bike && GetPawn() != Bike)
        SetBikeParked(true);
}
