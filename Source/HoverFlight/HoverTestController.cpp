#include "HoverTestController.h"
#include "HoverPilot.h"
#include "Animation/AnimInstance.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/UnrealType.h"
#include "EnhancedInputSubsystems.h"
#include "InputMappingContext.h"
#include "ChaosWheeledVehicleMovementComponent.h"
#include "Blueprint/WidgetLayoutLibrary.h"

bool AHoverTestController::IsNearTruck() const
{
    return Truck && Pilot && !Pilot->IsMounted() &&
           FVector::Dist2D(Pilot->GetActorLocation(), Truck->GetActorLocation()) < 420.f;
}

bool AHoverTestController::IsNearBike() const
{
    return Bike && Pilot && !Pilot->IsMounted() &&
           FVector::Dist2D(Pilot->GetActorLocation(), Bike->GetActorLocation()) < 280.f;
}

bool AHoverTestController::TryEnterBike()
{
    const bool bTruck =
        IsNearTruck() && (!IsNearBike() || FVector::Dist2D(Pilot->GetActorLocation(), Truck->GetActorLocation()) <
                                               FVector::Dist2D(Pilot->GetActorLocation(), Bike->GetActorLocation()));
    if (!bTruck && !IsNearBike())
        return false;
    Pilot->SetActorHiddenInGame(true);
    Pilot->SetActorEnableCollision(false);
    Pilot->GetCharacterMovement()->StopMovementImmediately();
    Pilot->GetCharacterMovement()->DisableMovement();
    Pilot->SetActorTickEnabled(false);
    Possess(bTruck ? Truck : Bike);
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
        for (int32 J = 0; J < Part.Materials.Num(); ++J)
            C->SetMaterial(J, Part.Materials[J]);
        if (I != 0)
            C->SetLeaderPoseComponent(Leader);
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
    if (auto *P = Cast<AHoverPilot>(GetPawn()))
        Pilot = P;
    if (Pilot && !bSpawnAttempted)
    {
        bSpawnAttempted = true;
        UClass *Class =
            LoadClass<APawn>(nullptr, TEXT("/Game/ScifiHoverbike/Vehicles/Blueprint/BP_Hoverbike.BP_Hoverbike_C"));
        if (Class)
        {
            FVector Location = Pilot->GetActorLocation() + FVector(550, 120, 80);
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
            FVector Location = Pilot->GetActorLocation() + FVector(350, -650, 150);
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
                if (UFunction *Eject = Bike->FindFunction(TEXT("EjectPlayer")))
                    Bike->ProcessEvent(Eject, nullptr);
            }
        }
    }
    else if (Pilot && Bike && GetPawn() && GetPawn() != Pilot)
    {
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
}
