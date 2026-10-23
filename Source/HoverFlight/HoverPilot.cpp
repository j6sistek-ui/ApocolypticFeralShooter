#include "HoverPilot.h"
#include "HoverTestController.h"
#include "HoverAnimInstance.h"
#include "HoverZombie.h"
#include "HoverMotion.h"
#include "HoverMovementComponent.h"
#include "EngineUtils.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NiagaraFunctionLibrary.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "TimerManager.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"

namespace
{
float Stick(float Value)
{
    return FMath::Abs(Value) < .16f ? 0.f : FMath::Sign(Value) * (FMath::Abs(Value) - .16f) / .84f;
}
} // namespace

AHoverPilot::AHoverPilot(const FObjectInitializer &ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UHoverMovementComponent>(
          ACharacter::CharacterMovementComponentName))
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(32.f, 97.f);
    bUseControllerRotationYaw = true;
    GetCharacterMovement()->MaxWalkSpeed = 500.f;
    GetCharacterMovement()->JumpZVelocity = 420.f;
    GetCharacterMovement()->MaxFlySpeed = 8000.f;
    GetCharacterMovement()->BrakingDecelerationFlying = 0.f;
    GetCharacterMovement()->BrakingFrictionFactor = 0.f;
    GetCharacterMovement()->bUseSeparateBrakingFriction = true;
    GetCharacterMovement()->BrakingFriction = 0.f;
    GetMesh()->SetRelativeLocation(FVector(0, 0, -97));
    GetMesh()->SetRelativeRotation(FRotator(0, -90, 0));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("FPSCamera"));
    Camera->SetupAttachment(GetRootComponent());
    Camera->SetRelativeLocation(FVector(0, 0, 65));
    Camera->bUsePawnControlRotation = true;
    Camera->FieldOfView = 95;
    ReviewArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("ReviewArm"));
    ReviewArm->SetupAttachment(GetRootComponent());
    ReviewArm->TargetArmLength = 430;
    ReviewArm->SocketOffset = FVector(0, 40, 15);
    ReviewArm->bUsePawnControlRotation = true;
    ReviewCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ReviewCamera"));
    ReviewCamera->SetupAttachment(ReviewArm);
    ReviewCamera->SetAutoActivate(false);
    ViewGun = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FPSGun"));
    ViewGun->SetupAttachment(Camera);
    ViewGun->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ViewGun->CastShadow = false;
    ViewGun->SetOnlyOwnerSee(true);
    WorldGun = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HeldGun"));
    WorldGun->SetupAttachment(GetMesh(), TEXT("hand_r"));
    WorldGun->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AHoverPilot::BeginPlay()
{
    Super::BeginPlay();
    SetCanBeDamaged(false);
    StartLocation = GetActorLocation();
    StartRotation = GetActorRotation();
    Assets = LoadObject<UHoverPilotAssets>(nullptr, TEXT("/Game/HoverPrototype/DA_HoverPilot.DA_HoverPilot"));
    if (!Assets || !Assets->Glider || Assets->BodyParts.IsEmpty())
    {
        StatusMessage = TEXT("Prototype assets missing - run the asset setup script.");
        UE_LOG(LogTemp, Error, TEXT("HOVER: required prototype assets missing"));
        return;
    }
    for (int32 Index = 0; Index < Assets->BodyParts.Num(); ++Index)
    {
        const FHoverBodyPart &Part = Assets->BodyParts[Index];
        USkeletalMeshComponent *Component = Index == 0 ? GetMesh() : NewObject<USkeletalMeshComponent>(this, Part.Name);
        if (Index != 0)
        {
            Component->SetupAttachment(GetMesh());
            Component->RegisterComponent();
            Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        }
        Component->SetSkeletalMesh(Part.Mesh);
        for (int32 M = 0; M < Part.Materials.Num(); ++M)
            Component->SetMaterial(M, Part.Materials[M]);
        if (Index != 0)
            Component->SetLeaderPoseComponent(GetMesh());
        Parts.Add(Component);
    }
    ViewGun->SetStaticMesh(Assets->Gun);
    ViewGun->SetRelativeLocation(FVector(35, 18, -20));
    ViewGun->SetRelativeRotation(FRotator(0, -90, 0));
    WorldGun->SetStaticMesh(Assets->Gun);
    WorldGun->SetRelativeLocation(FVector(4, 2, 0));
    WorldGun->SetRelativeRotation(FRotator(0, 90, -90));
    BoardActor = GetWorld()->SpawnActor<AActor>();
    BoardActor->SetOwner(this);
    BoardBody = NewObject<UBoxComponent>(BoardActor, TEXT("HoverCollision"));
    BoardActor->SetRootComponent(BoardBody);
    BoardBody->SetBoxExtent(FVector(90, 38, 9));
    BoardBody->SetCollisionProfileName(TEXT("PhysicsActor"));
    BoardBody->SetCollisionResponseToChannel(ECC_Pawn, ECR_Ignore);
    BoardBody->SetCollisionResponseToChannel(ECC_Camera, ECR_Ignore);
    BoardBody->SetLinearDamping(.3f);
    BoardBody->SetAngularDamping(4.f);
    BoardBody->RegisterComponent();
    BoardBody->SetMassOverrideInKg(NAME_None, 35.f);
    BoardBody->SetNotifyRigidBodyCollision(true);
    BoardBody->SetUseCCD(true);
    BoardBody->OnComponentHit.AddDynamic(this, &AHoverPilot::BoardHit);
    Board = NewObject<UPoseableMeshComponent>(BoardActor, TEXT("HoverMechanism"));
    Board->SetupAttachment(BoardBody);
    Board->RegisterComponent();
    Board->SetSkinnedAssetAndUpdate(Assets->Glider);
    Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Board->SetBoundsScale(2.f);
    for (const FMeshBoneInfo &Bone : Assets->Glider->GetRefSkeleton().GetRefBoneInfo())
        BoardRest.Add(Bone.Name, Board->GetBoneTransformByName(Bone.Name, EBoneSpaces::ComponentSpace));
    ParkedLocation = StartLocation + GetActorForwardVector() * 150.f - FVector(0, 0, 73);
    BoardActor->SetActorLocationAndRotation(ParkedLocation, StartRotation + FRotator(0, -90, 0));
    BoardBody->SetSimulatePhysics(true);
    if (Assets->BoosterEffect)
    {
        const auto &Parameters = Assets->BoosterEffect->GetExposedParameters();
        BoosterSize = Parameters.GetParameterValue<float>(
            FNiagaraVariable(FNiagaraTypeDefinition::GetFloatDef(), TEXT("User.ThrustSize")));
        BoosterSpawnRate = Parameters.GetParameterValue<float>(
            FNiagaraVariable(FNiagaraTypeDefinition::GetFloatDef(), TEXT("User.ThurstSpawningRate")));
        UE_LOG(LogTemp, Display, TEXT("HOVER_BOOSTER size=%.3f rate=%.3f"), BoosterSize, BoosterSpawnRate);
        for (float Side : {-1.f, 1.f})
        {
            UNiagaraComponent *Effect = NewObject<UNiagaraComponent>(BoardActor);
            Effect->SetupAttachment(Board);
            Effect->SetAutoActivate(false);
            Effect->SetAsset(Assets->BoosterEffect);
            Effect->SetRelativeLocation(FVector(Side * 48.f, -22.f, 0));
            Effect->SetRelativeRotation(FRotator(0, 90, 0));
            Effect->RegisterComponent();
            Boosters.Add(Effect);
        }
    }
    GetMesh()->SetAnimInstanceClass(UHoverAnimInstance::StaticClass());
    PlayPose(Assets->Stand, true);
    SetView();
    if (APlayerController *PC = Cast<APlayerController>(GetController()))
    {
        PC->SetInputMode(FInputModeGameOnly());
        PC->bShowMouseCursor = false;
        PC->PlayerCameraManager->ViewPitchMin = -75.f;
        PC->PlayerCameraManager->ViewPitchMax = 75.f;
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_READY Vexa parts=%d glider=%s gun=%s"), Parts.Num(),
           *GetNameSafe(Assets->Glider), *GetNameSafe(Assets->Gun));
}

void AHoverPilot::SetupPlayerInputComponent(UInputComponent *Input)
{
    Super::SetupPlayerInputComponent(Input);
}

bool AHoverPilot::HasBoardNearby() const
{
    return BoardActor && FVector::Dist(GetActorLocation(), BoardActor->GetActorLocation() + FVector(0, 0, 125)) < 240.f;
}

bool AHoverPilot::FindDismountLocation(FVector &Location) const
{
    if (!Board || !bMounted || GetVelocity().Size() > 300.f)
        return false;
    const float FeetHeight = Board->GetBoneLocationByName(TEXT("foot_contact_L"), EBoneSpaces::WorldSpace).Z;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverSafeDismount), false, this);
    Params.AddIgnoredActor(BoardActor);
    for (float Side : {-1.f, 1.f})
    {
        const FVector Candidate = GetActorLocation() + GetActorRightVector() * (Side * 165.f);
        FHitResult Floor;
        if (!GetWorld()->LineTraceSingleByChannel(Floor, Candidate + FVector(0, 0, 30),
                                                  FVector(Candidate.X, Candidate.Y, FeetHeight - 150.f), ECC_Visibility,
                                                  Params) ||
            Floor.ImpactNormal.Z < .7f || FeetHeight - Floor.ImpactPoint.Z > 150.f)
            continue;
        Location = FVector(Candidate.X, Candidate.Y, Floor.ImpactPoint.Z + 99.f);
        if (!GetWorld()->OverlapBlockingTestByChannel(Location, FQuat::Identity, ECC_Pawn,
                                                      FCollisionShape::MakeCapsule(32.f, 97.f), Params))
            return true;
    }
    return false;
}

bool AHoverPilot::CanDismount() const
{
    FVector Location;
    return FindDismountLocation(Location);
}

void AHoverPilot::HoverMount()
{
    if (!Board || TransitionTime > 0)
        return;
    auto *Movement = GetCharacterMovement();
    if (!bMounted)
    {
        if (auto *PC = Cast<AHoverTestController>(GetController()); PC && PC->TryEnterBike())
            return;
        if (!HasBoardNearby())
        {
            StatusMessage = TEXT("Move closer to the glider.");
            StatusTime = 3.f;
            UE_LOG(LogTemp, Display, TEXT("HOVER_MOUNT blocked: distance"));
            return;
        }
        if (BoardBody->GetPhysicsLinearVelocity().Size() > 100.f)
        {
            StatusMessage = TEXT("Wait for the glider to settle");
            StatusTime = 3.f;
            UE_LOG(LogTemp, Display, TEXT("HOVER_MOUNT blocked: moving board %s"),
                   *BoardBody->GetPhysicsLinearVelocity().ToString());
            return;
        }
        FVector MountPoint = BoardActor->GetActorLocation() + FVector(0, 0, 132);
        FHitResult Hit;
        const FVector Before = GetActorLocation();
        SetActorLocation(MountPoint, true, &Hit);
        if (FVector::Dist(GetActorLocation(), MountPoint) > 8.f)
        {
            UE_LOG(LogTemp, Display,
                   TEXT("HOVER_MOUNT blocked: hit=%s component=%s point=%s target=%s startPenetrating=%d"),
                   *GetNameSafe(Hit.GetActor()), *GetNameSafe(Hit.GetComponent()), *GetActorLocation().ToString(),
                   *MountPoint.ToString(), Hit.bStartPenetrating);
            SetActorLocation(Before);
            StatusMessage = TEXT("Not enough room to mount here.");
            StatusTime = 3.f;
            return;
        }
        GetCapsuleComponent()->SetCapsuleSize(90, 142);
        BoardBody->SetSimulatePhysics(false);
        BoardBody->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        BoardActor->SetActorRotation(FRotator(0, GetActorRotation().Yaw - 90, 0));
        BoardPitch = BoardBank = WingSweep = RiderLean = 0;
        PitchVelocity = BankVelocity = WingVelocity = LeanVelocity = 0;
        MountFeet[0] = GetMesh()->GetSocketLocation(TEXT("foot_l"));
        MountFeet[1] = GetMesh()->GetSocketLocation(TEXT("foot_r"));
        MountFrom = Before;
        MountTo = MountPoint;
        SetActorLocation(Before);
        GetMesh()->SetRelativeLocation(FVector(0, 0, -110));
        bSteppingOn = true;
        bMounted = true;
        Movement->SetMovementMode(MOVE_Flying);
        Movement->StopMovementImmediately();
        TargetAltitude = GetActorLocation().Z;
        bHeightHolding = true;
        TransitionTime = .85f;
        StatusMessage = TEXT("Pads locking");
        StatusTime = 0;
    }
    else
    {
        FVector Exit;
        if (!FindDismountLocation(Exit))
        {
            StatusMessage = TEXT("Slow down and descend near clear ground to get off");
            UE_LOG(LogTemp, Display, TEXT("HOVER_DISMOUNT blocked: height, speed or landing clearance"));
            return;
        }
        const FVector ReleaseVelocity = Movement->Velocity;
        BoardActor->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
        ParkedLocation = BoardActor->GetActorLocation();
        BoardBody->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        BoardBody->SetSimulatePhysics(true);
        BoardBody->SetPhysicsLinearVelocity(ReleaseVelocity);
        BoardBody->WakeAllRigidBodies();
        bMounted = false;
        bSteppingOn = false;
        GetCapsuleComponent()->SetCapsuleSize(32, 97);
        GetMesh()->SetRelativeLocation(FVector(0, 0, -97));
        SetActorLocation(Exit);
        Movement->StopMovementImmediately();
        Movement->SetMovementMode(MOVE_Falling);
        TransitionTime = .5f;
        StatusMessage = TEXT("Pads released");
    }
    HoverStatus();
}

void AHoverPilot::HoverView()
{
    bReview = !bReview;
    SetView();
}

void AHoverPilot::SetView()
{
    Camera->SetActive(!bReview);
    ReviewCamera->SetActive(bReview);
    ViewGun->SetVisibility(!bReview);
    WorldGun->SetVisibility(bReview && (bAiming || GunRaisedTime > 0));
    // The full-body riding pose crosses the eye camera during pitch and recoil.
    // Keep it for the external view; the FPS camera renders its own rifle.
    for (USkeletalMeshComponent *Part : Parts)
        Part->SetOwnerNoSee(!bReview);
}

void AHoverPilot::HoverReset()
{
    if (!BoardActor)
        return;
    BoardActor->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
    BoardBody->SetSimulatePhysics(false);
    bMounted = false;
    bSteppingOn = false;
    BoardPitch = BoardBank = WingSweep = RiderLean = 0;
    PitchVelocity = BankVelocity = WingVelocity = LeanVelocity = 0;
    BoostCharge = 1;
    BoostRechargeDelay = 0;
    bBoostExhausted = false;
    TransitionTime = 0;
    HopTime = 0;
    GetCapsuleComponent()->SetCapsuleSize(32, 97);
    GetMesh()->SetRelativeLocation(FVector(0, 0, -97));
    GetMesh()->SetRelativeRotation(FRotator(0, -90, 0));
    SetActorLocationAndRotation(StartLocation + FVector(0, 0, 20), StartRotation);
    GetCharacterMovement()->SetMovementMode(MOVE_Falling);
    GetCharacterMovement()->StopMovementImmediately();
    ParkedLocation = StartLocation + StartRotation.Vector() * 150.f - FVector(0, 0, 73);
    BoardActor->SetActorLocationAndRotation(ParkedLocation, StartRotation + FRotator(0, -90, 0));
    BoardBody->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    BoardBody->SetSimulatePhysics(true);
    BoardBody->SetPhysicsLinearVelocity(FVector::ZeroVector);
    BoardBody->SetPhysicsAngularVelocityInDegrees(FVector::ZeroVector);
    if (Controller)
        Controller->SetControlRotation(StartRotation);
}

void AHoverPilot::HoverStatus()
{
    UE_LOG(LogTemp, Display, TEXT("HOVER_STATE mounted=%d aim=%d pos=%s velocity=%s targetZ=%.1f"), bMounted, bAiming,
           *GetActorLocation().ToString(), *GetVelocity().ToString(), TargetAltitude);
}

void AHoverPilot::UpdateInput(float DT)
{
    APlayerController *PC = Cast<APlayerController>(GetController());
    if (!PC)
        return;
    auto Down = [PC](FKey Key) { return PC->IsInputKeyDown(Key); };
    ForwardInput = FMath::Clamp(Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY)) + float(Down(EKeys::W)) -
                                    float(Down(EKeys::S)),
                                -1.f, 1.f);
    SideInput = FMath::Clamp(Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX)) + float(Down(EKeys::D)) -
                                 float(Down(EKeys::A)),
                             -1.f, 1.f);
    BankInput = float(Down(EKeys::Gamepad_RightShoulder) || Down(EKeys::E)) -
                float(Down(EKeys::Gamepad_LeftShoulder) || Down(EKeys::Q));
    TurnInput = Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightX));
    float MouseX = 0, MouseY = 0;
    PC->GetInputMouseDelta(MouseX, MouseY);
    FRotator Look = PC->GetControlRotation();
    Look.Yaw += TurnInput * 120.f * DT + MouseX * .12f;
    Look.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch) -
                                  Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightY)) * 90.f * DT + MouseY * .12f,
                              -75.f, 75.f);
    Look.Roll = 0;
    PC->SetControlRotation(Look);
    bBoostHeld = Down(EKeys::Gamepad_LeftThumbstick) || Down(EKeys::LeftShift);
    const bool Hold = Down(EKeys::Gamepad_FaceButton_Left) || Down(EKeys::X);
    if (Hold && !bHoldConsumed)
    {
        HoldTime += DT;
        if (HoldTime >= .65f)
        {
            HoverMount();
            bHoldConsumed = true;
        }
    }
    if (!Hold)
    {
        HoldTime = 0;
        bHoldConsumed = false;
    }
    const bool JumpPressed = Down(EKeys::Gamepad_FaceButton_Bottom) || Down(EKeys::SpaceBar);
    if (JumpPressed && !bWasJump && TransitionTime <= 0)
    {
        if (bMounted)
        {
            GetCharacterMovement()->Velocity.Z = 440;
            HopTime = .5f;
            bHeightHolding = false;
        }
        else
            Jump();
    }
    if (!JumpPressed && bWasJump)
        StopJumping();
    bWasJump = JumpPressed;
    const bool Slide = Down(EKeys::Gamepad_FaceButton_Right) || Down(EKeys::LeftControl);
    if (Slide && !bWasSlide && bMounted && GetVelocity().Size2D() > 100)
        SlideTime = .65f;
    bWasSlide = Slide;
    const bool View = Down(EKeys::F5) || Down(EKeys::Gamepad_Special_Right);
    if (View && !bWasView)
        HoverView();
    bWasView = View;
    const bool Reset = Down(EKeys::R);
    if (Reset && !bWasReset)
        HoverReset();
    bWasReset = Reset;
    const bool Aim = PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > .2f || Down(EKeys::RightMouseButton);
    if (Aim != bAiming)
    {
        bAiming = Aim;
        if (Aim)
        {
            AimExitTime = 0;
            if (bMounted)
                PlayPose(Assets->AimStart, false);
        }
        else
        {
            if (bMounted)
                PlayPose(Assets->AimEnd, false);
            AimExitTime = bMounted && Assets->AimEnd ? Assets->AimEnd->GetPlayLength() : 0;
        }
        SetView();
    }
    if ((PC->GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > .2f || Down(EKeys::LeftMouseButton)) &&
        FireCooldown <= 0 && TransitionTime <= 0)
        FireShot();
}

void AHoverPilot::UpdateFlight(float DT)
{
    UCharacterMovementComponent *Move = GetCharacterMovement();
    if (!bBoostHeld && BoostCharge >= .2f)
        bBoostExhausted = false;
    bBoost = bMounted && TransitionTime <= 0 && bBoostHeld && !bBoostExhausted && BoostCharge > 0 &&
             (FMath::Abs(ForwardInput) > .05f || FMath::Abs(SideInput) > .05f);
    if (bBoost)
    {
        BoostCharge = FMath::Max(0.f, BoostCharge - DT / 4.f);
        BoostRechargeDelay = 1.25f;
        if (BoostCharge <= 0)
            bBoostExhausted = true;
    }
    else
    {
        BoostRechargeDelay = FMath::Max(0.f, BoostRechargeDelay - DT);
        if (BoostRechargeDelay <= 0)
            BoostCharge = FMath::Min(1.f, BoostCharge + DT / 8.f);
    }
    if (!bMounted)
    {
        AddMovementInput(GetActorForwardVector(), ForwardInput);
        AddMovementInput(GetActorRightVector(), SideInput);
        return;
    }
    Move->SetMovementMode(MOVE_Flying);
    if (bSteppingOn)
    {
        const float T = FMath::Clamp(1.f - TransitionTime / .85f, 0.f, 1.f);
        SetActorLocation(FMath::Lerp(MountFrom, MountTo, FMath::SmoothStep(0.f, 1.f, T)), true);
        if (TransitionTime <= 0)
        {
            bSteppingOn = false;
            BoardActor->AttachToComponent(GetRootComponent(), FAttachmentTransformRules::KeepWorldTransform);
            BoardActor->SetActorRelativeLocation(FVector(0, 0, -132));
            BoardActor->SetActorRelativeRotation(FRotator(0, -90, 0));
            TargetAltitude = GetActorLocation().Z;
        }
    }
    if (TransitionTime > 0)
    {
        Move->StopMovementImmediately();
        TargetAltitude = GetActorLocation().Z;
        return;
    }
    const float Speed = bBoost ? 5600.f : 1800.f;
    FVector Direction = GetActorForwardVector() * ForwardInput + GetActorRightVector() * SideInput;
    Direction = Direction.GetClampedToMaxSize(1.f);
    const FVector PreviousVelocity = Move->Velocity;
    FVector Desired = HoverMotion::HorizontalVelocity(PreviousVelocity, Direction, Speed, DT, bBoost);
    const float Pitch = FRotator::NormalizeAxis(GetControlRotation().Pitch);
    const float AlongSpeed = FVector::DotProduct(Desired, GetActorForwardVector());
    const float VerticalCommand =
        FMath::Abs(Pitch) > 5.f ? FMath::Sin(FMath::DegreesToRadians(Pitch)) * AlongSpeed : 0.f;
    if (HopTime > 0)
    {
        HopTime -= DT;
        Desired.Z = FMath::Max(0.f, PreviousVelocity.Z - 500.f * DT);
        TargetAltitude = GetActorLocation().Z;
        bHeightHolding = false;
    }
    else if (FMath::Abs(VerticalCommand) > 1)
    {
        Desired.Z = FMath::FInterpConstantTo(PreviousVelocity.Z, VerticalCommand, DT, 2200.f);
        bHeightHolding = false;
        TargetAltitude = GetActorLocation().Z;
    }
    else
    {
        if (!bHeightHolding)
        {
            // Account for the remaining vertical stopping distance before holding.
            TargetAltitude = GetActorLocation().Z + PreviousVelocity.Z * FMath::Abs(PreviousVelocity.Z) / 4400.f;
            bHeightHolding = true;
        }
        Desired.Z = FMath::FInterpConstantTo(
            PreviousVelocity.Z, FMath::Clamp((TargetAltitude - GetActorLocation().Z) * 3.f, -1200.f, 1200.f), DT,
            2200.f);
    }
    if (SlideTime > 0)
    {
        SlideTime -= DT;
        Desired.X = Move->Velocity.X;
        Desired.Y = Move->Velocity.Y;
    }
    Move->Velocity = Desired;
    if (bHeightHolding && FMath::Abs(Move->Velocity.Z) < 1.f && FMath::Abs(TargetAltitude - GetActorLocation().Z) < 1.f)
        Move->Velocity.Z = 0;
    const FVector Acceleration = (Move->Velocity - PreviousVelocity) / FMath::Max(DT, .001f);
    const float ForwardForce =
        FMath::Clamp(FVector::DotProduct(Acceleration, GetActorForwardVector()) / 3000.f, -1.f, 1.f);
    const float Travel = FMath::Clamp(AlongSpeed / 1800.f, -1.f, 1.f);
    HoverMotion::Spring(BoardPitch, PitchVelocity, FMath::Clamp(Pitch * .65f - ForwardForce * 8.f, -30.f, 30.f), DT);
    HoverMotion::Spring(BoardBank, BankVelocity,
                        FMath::Clamp(BankInput * 28.f + SideInput * 10.f + TurnInput * 5.f, -35.f, 35.f), DT);
    HoverMotion::Spring(WingSweep, WingVelocity,
                        FMath::Clamp(Travel * 10.f + ForwardForce * 5.f + Pitch * .12f, -20.f, 20.f), DT);
    HoverMotion::Spring(RiderLean, LeanVelocity,
                        FMath::Clamp(Travel * 3.f + ForwardForce * 4.f - Pitch * .1f, -8.f, 8.f), DT);
    FHitResult Floor;
    FCollisionQueryParams FloorParams(SCENE_QUERY_STAT(HoverLanding), false, this);
    FloorParams.AddIgnoredActor(BoardActor);
    const FVector Bottom = GetActorLocation() - FVector(0, 0, 142);
    const bool Grounded =
        GetWorld()->LineTraceSingleByChannel(Floor, Bottom + FVector(0, 0, 8), Bottom - FVector(0, 0, 12),
                                             ECC_Visibility, FloorParams) &&
        Floor.ImpactNormal.Z > .7f;
    if (Grounded && !bGliderGrounded && FMath::Min(PreviousVelocity.Z, PreviousFlightVerticalSpeed) < -60.f)
        ImpactPulse(Floor.ImpactPoint + Floor.ImpactNormal * 2, Floor.ImpactNormal, .45f, .18f, .5f);
    bGliderGrounded = Grounded;
    PreviousFlightVerticalSpeed = Desired.Z;
}

void AHoverPilot::PlayPose(UAnimSequence *Animation, bool bLoop)
{
    if (!Animation || CurrentAnimation == Animation)
        return;
    CurrentAnimation = Animation;
    if (auto *Instance = Cast<UHoverAnimInstance>(GetMesh()->GetAnimInstance()))
    {
        Instance->Sequence = Animation;
        Instance->bLoop = bLoop;
        ++Instance->RestartSerial;
    }
}

void AHoverPilot::UpdateAppearance(float DT)
{
    AimExitTime = FMath::Max(0.f, AimExitTime - DT);
    GunRaisedTime = FMath::Max(0.f, GunRaisedTime - DT);
    // Grounded aiming keeps the locomotion pose below the spine. The supplied
    // full-body gun clips are glider poses and lift the feet when used on foot.
    if (!bMounted || (!bAiming && AimExitTime <= 0))
    {
        UAnimSequence *Pose = Assets->Stand;
        if (bMounted)
        {
            Pose = Assets->RideIdle;
            if (FVector::DotProduct(GetVelocity(), GetActorForwardVector()) > 150.f)
                Pose = Assets->RideMove;
            if (GetVelocity().Z < -200.f)
                Pose = Assets->RideDown;
            if (BoardBank < -7.f)
                Pose = Assets->RideLeft;
            if (BoardBank > 7.f)
                Pose = Assets->RideRight;
        }
        else if (GetVelocity().Size2D() > 20)
            Pose = Assets->Walk;
        PlayPose(Pose, true);
    }
    Camera->SetFieldOfView(
        FMath::FInterpTo(Camera->FieldOfView, bAiming ? 65.f : (bBoost && bMounted ? 105.f : 95.f), DT, 10.f));
    Camera->SetRelativeLocation(
        FMath::VInterpTo(Camera->GetRelativeLocation(), FVector(0, 0, bMounted ? 33.f : 65.f), DT, 8.f));
    ViewGun->SetRelativeLocation(FMath::VInterpTo(ViewGun->GetRelativeLocation(),
                                                  bAiming ? FVector(55, 2, -22) : FVector(35, 18, -20), DT, 12.f));
    const float LockTarget = bMounted && !bSteppingOn ? 1.f : 0.f;
    LockVelocity += (100.f * (LockTarget - LockAlpha) - 16.f * LockVelocity) * DT;
    LockAlpha = FMath::Clamp(LockAlpha + LockVelocity * DT, 0.f, 1.06f);
    if (!Board)
        return;
    if (bMounted && !bSteppingOn)
        BoardActor->SetActorRelativeRotation(FRotator(BoardPitch, 0, BoardBank).Quaternion() *
                                             FRotator(0, -90, 0).Quaternion());
    for (const auto &Pair : BoardRest)
        Board->SetBoneTransformByName(Pair.Key, Pair.Value, EBoneSpaces::ComponentSpace);
    for (const TCHAR *Side : {TEXT("L"), TEXT("R")})
    {
        const float Sign = FString(Side) == TEXT("L") ? 1.f : -1.f;
        const FName SlideBone(*FString::Printf(TEXT("pad_slide_%s"), Side));
        if (const FTransform *Rest = BoardRest.Find(SlideBone))
            Board->SetBoneLocationByName(SlideBone, Rest->GetLocation() + FVector(-Sign * 3.5f * LockAlpha, 0, 0),
                                         EBoneSpaces::ComponentSpace);
        Board->RefreshBoneTransforms();
        const FName PressBone(*FString::Printf(TEXT("pad_press_%s"), Side));
        FTransform Press = Board->GetBoneTransformByName(PressBone, EBoneSpaces::ComponentSpace);
        Press.AddToTranslation(FVector(0, 0, -.8f * LockAlpha));
        Board->SetBoneTransformByName(PressBone, Press, EBoneSpaces::ComponentSpace);
        Board->RefreshBoneTransforms();
        const FName Wing(*FString::Printf(TEXT("wing_sweep_%s"), Side));
        if (const FTransform *Rest = BoardRest.Find(Wing))
        {
            FTransform Pose = *Rest;
            Pose.SetRotation(FQuat(FVector::UpVector, FMath::DegreesToRadians(Sign * WingSweep)) * Rest->GetRotation());
            Board->SetBoneTransformByName(Wing, Pose, EBoneSpaces::ComponentSpace);
        }
        Board->RefreshBoneTransforms();
        const FName Cant(*FString::Printf(TEXT("wing_cant_%s"), Side));
        if (BoardRest.Contains(Cant))
        {
            FTransform Pose = Board->GetBoneTransformByName(Cant, EBoneSpaces::ComponentSpace);
            Pose.SetRotation(FQuat(FVector::RightVector, FMath::DegreesToRadians(BoardBank * .25f)) *
                             Pose.GetRotation());
            Board->SetBoneTransformByName(Cant, Pose, EBoneSpaces::ComponentSpace);
        }
    }
    Board->RefreshBoneTransforms();
    GetMesh()->SetRelativeRotation(
        bMounted ? (FRotator(BoardPitch, 0, BoardBank).Quaternion() * FRotator(0, -90, 0).Quaternion()).Rotator()
                 : FRotator(0, -90, 0));
    if (auto *Instance = Cast<UHoverAnimInstance>(GetMesh()->GetAnimInstance()))
    {
        Instance->FootLock = bMounted ? 1.f : 0.f;
        Instance->RifleAim = Assets->RifleAim;
        Instance->bAiming = bAiming || GunRaisedTime > 0;
        Instance->RiderLean = bMounted ? RiderLean : 0;
        FVector Feet[2];
        for (int32 I = 0; I < 2; ++I)
        {
            Feet[I] = Board->GetBoneLocationByName(I == 0 ? TEXT("foot_contact_L") : TEXT("foot_contact_R"),
                                                   EBoneSpaces::WorldSpace) +
                      Board->GetUpVector() * 8.5f;
            if (bSteppingOn)
            {
                const float T = 1.f - TransitionTime / .85f;
                const float Step = FMath::SmoothStep(I == 0 ? 0.f : .35f, I == 0 ? .6f : 1.f, T);
                Feet[I] = FMath::Lerp(MountFeet[I], Feet[I], Step) + FVector(0, 0, FMath::Sin(Step * PI) * 15.f);
            }
            Feet[I] = GetMesh()->GetComponentTransform().InverseTransformPosition(Feet[I]);
        }
        Instance->LeftFoot = Feet[0];
        Instance->RightFoot = Feet[1];
    }
    WorldGun->SetVisibility(bReview && (bAiming || GunRaisedTime > 0));
    UpdateGunTransform();
    const bool Powered = bMounted && TransitionTime <= 0 && !bSteppingOn;
    const float Thrust = FMath::Max(FMath::Abs(ForwardInput), FMath::Abs(SideInput));
    for (UNiagaraComponent *Effect : Boosters)
    {
        const bool Active = Powered && Thrust > .05f;
        const float Scale = bBoost ? 1.4f : .55f + .3f * Thrust;
        Effect->SetVariableFloat(TEXT("User.ThrustAlpha"), bBoost ? 1.f : .75f * Thrust);
        Effect->SetVariableFloat(TEXT("User.ThrustSize"), BoosterSize * Scale);
        Effect->SetVariableFloat(TEXT("User.ThurstSpawningRate"), BoosterSpawnRate * (bBoost ? 1.8f : Thrust));
        if (Active && !Effect->IsActive())
            Effect->Activate(true);
        else if (!Active && Effect->IsActive())
            Effect->Deactivate();
        Effect->SetRelativeScale3D(FVector(Scale));
        if (Thrust > .05f)
        {
            const FVector ThrustDirection = FRotator(BoardPitch, GetActorRotation().Yaw, 0).Vector() * ForwardInput +
                                            GetActorRightVector() * SideInput;
            Effect->SetWorldRotation(
                FRotationMatrix::MakeFromXZ(ThrustDirection.GetSafeNormal(), Board->GetUpVector()).Rotator());
        }
    }
}

void AHoverPilot::UpdateGunTransform()
{
    const FVector Hand = GetMesh()->GetSocketLocation(TEXT("hand_r"));
    const FVector Aim = GetControlRotation().Vector();
    WorldGun->SetWorldLocationAndRotation(Hand + Aim * 20.f + GetActorUpVector() * 3.f,
                                          FRotationMatrix::MakeFromYZ(Aim, GetActorUpVector()).Rotator());
}

void AHoverPilot::FireShot()
{
    ++ShotsFired;
    FireCooldown = .18f;
    GunRaisedTime = 3.f;
    UpdateGunTransform();
    SetView();
    const UCameraComponent *ActiveCamera = bReview ? ReviewCamera : Camera;
    const FVector Eye = ActiveCamera->GetComponentLocation();
    const FVector End = Eye + ActiveCamera->GetForwardVector() * 50000.f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverShot), true, this);
    Params.AddIgnoredActor(BoardActor);
    FHitResult AimHit;
    GetWorld()->LineTraceSingleByChannel(AimHit, Eye, End, ECC_Visibility, Params);
    const FVector Target = AimHit.bBlockingHit ? AimHit.ImpactPoint : End;
    const FVector Muzzle = bReview ? WorldGun->GetComponentLocation() + WorldGun->GetRightVector() * 45.f
                                   : ViewGun->GetComponentLocation() + Camera->GetForwardVector() * 50.f;
    ImpactPulse(Muzzle, (Target - Muzzle).GetSafeNormal(), .04f, 0.f, .10f, Assets->MuzzleEffect);
    FHitResult Hit;
    const FVector ShotDirection = (Target - Muzzle).GetSafeNormal();
    GetWorld()->LineTraceSingleByChannel(Hit, Muzzle, Target + ShotDirection * 3.f, ECC_Visibility, Params);
    if (auto *Zombie = Cast<AHoverZombie>(Hit.GetActor()))
        UGameplayStatics::ApplyPointDamage(Zombie, 35.f, ShotDirection, Hit, GetController(), this, nullptr);
    if (bMounted && bAiming && Assets->Fire)
    {
        CurrentAnimation = nullptr;
        PlayPose(Assets->Fire, false);
    }
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_SHOT hit=%s"), *GetNameSafe(Hit.GetActor()));
}

void AHoverPilot::ImpactPulse(const FVector &Location, const FVector &Normal, float Scale, float Rumble, float Duration,
                              UFXSystemAsset *Template)
{
    if (!Assets)
        return;
    if (!Template)
        Template = Assets->ShockwaveEffect;
    if (!Template)
        return;
    if (Rumble > 0)
    {
        if (GetWorld()->GetTimeSeconds() - LastLandingPulse < .45f)
            return;
        LastLandingPulse = GetWorld()->GetTimeSeconds();
        if (APlayerController *PC = Cast<APlayerController>(GetController()))
            PC->PlayDynamicForceFeedback(Rumble, .09f, false, true, false, true);
    }
    UFXSystemComponent *Effect = nullptr;
    const FRotator Rotation = FRotationMatrix::MakeFromZ(Normal).Rotator();
    if (UNiagaraSystem *System = Cast<UNiagaraSystem>(Template))
    {
        auto *Niagara = UNiagaraFunctionLibrary::SpawnSystemAtLocation(GetWorld(), System, Location, Rotation,
                                                                       FVector(Scale), true, false);
        if (Niagara && Template == Assets->ShockwaveEffect)
        {
            // This pack exposes world-space size/lifetime controls; component
            // scale alone does not scale its particles.
            Niagara->SetVariableFloat(TEXT("User.Scale Overall"), Scale);
            Niagara->SetVariableFloat(TEXT("User.Lifetime Overall"), Duration);
            Niagara->SetVariableFloat(TEXT("User.Emissiveness Overall"), Rumble < .1f ? .25f : .6f);
        }
        if (Niagara)
            Niagara->Activate(true);
        Effect = Niagara;
    }
    else if (UParticleSystem *Particles = Cast<UParticleSystem>(Template))
        Effect =
            UGameplayStatics::SpawnEmitterAtLocation(GetWorld(), Particles, Location, Rotation, FVector(Scale), true);
    if (Effect)
    {
        TWeakObjectPtr<UFXSystemComponent> WeakEffect(Effect);
        FTimerHandle Timer;
        GetWorld()->GetTimerManager().SetTimer(
            Timer,
            [WeakEffect]() {
                if (WeakEffect.IsValid())
                    WeakEffect->DestroyComponent();
            },
            Duration, false);
        UE_LOG(LogTemp, Display, TEXT("HOVER_PULSE scale=%.3f duration=%.2f"), Scale, Duration);
    }
}

void AHoverPilot::Landed(const FHitResult &Hit)
{
    const float FallSpeed = -GetVelocity().Z;
    Super::Landed(Hit);
    if (!bMounted && FallSpeed > 150.f)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, .07f, .06f, .2f);
}

void AHoverPilot::BoardHit(UPrimitiveComponent *HitComponent, AActor *OtherActor, UPrimitiveComponent *OtherComponent,
                           FVector NormalImpulse, const FHitResult &Hit)
{
    if (!bMounted && Hit.ImpactNormal.Z > .6f && NormalImpulse.Size() > 1800.f)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, .35f, .1f, .5f);
}

void AHoverPilot::Tick(float DT)
{
    Super::Tick(DT);
    if (!Assets)
        return;
    DT = FMath::Min(DT, .05f);
    TransitionTime = FMath::Max(0.f, TransitionTime - DT);
    FireCooldown = FMath::Max(0.f, FireCooldown - DT);
    StatusTime = FMath::Max(0.f, StatusTime - DT);
    UpdateInput(DT);
    UpdateFlight(DT);
    UpdateAppearance(DT);
    if (GetActorLocation().Z < -10000)
        HoverReset();
}

FString AHoverPilot::GetPrompt() const
{
    if (StatusTime > 0)
        return StatusMessage;
    if (TransitionTime > 0)
        return bMounted ? TEXT("Pads locking...") : TEXT("Pads released");
    if (!bMounted)
        if (const auto *PC = Cast<AHoverTestController>(GetController()); PC && PC->IsNearTruck())
            return TEXT("Hold X to drive the Doomsday truck");
    if (!bMounted)
        if (const auto *PC = Cast<AHoverTestController>(GetController()); PC && PC->IsNearBike())
            return TEXT("Hold X to ride the hoverbike");
    if (bMounted)
        return CanDismount() ? TEXT("Hold X: get off   |   L1 / Q: bank left   R1 / E: bank right")
                             : TEXT("Slow down and descend near clear ground to get off   |   L1 / R1: bank");
    return HasBoardNearby() ? TEXT("Hold X to step on and lock the pads")
                            : TEXT("Walk to the glider   |   R: reset test");
}

void AHoverHUD::DrawHUD()
{
    Super::DrawHUD();
    const auto *Pilot = Cast<AHoverPilot>(GetOwningPawn());
    if (!Canvas)
        return;
    DrawText(TEXT("D-pad Up / F6: graphics"), FLinearColor(.7f, .85f, 1.f), 24, 16);
    for (TActorIterator<AHoverZombieRange> It(GetWorld()); It; ++It)
    {
        DrawText(FString::Printf(TEXT("INVULNERABLE | Zombies: %d | Kills: %d"), It->GetAliveCount(), It->GetKills()),
                 FLinearColor(.8f, 1.f, .8f), 24, 38);
        break;
    }
    if (!Pilot)
    {
        DrawRect(FLinearColor(0, 0, 0, .6f), 18, Canvas->ClipY - 68, 900, 50);
        const auto *PC = Cast<AHoverTestController>(GetOwningPlayerController());
        DrawText(
            PC && PC->IsDrivingTruck()
                ? TEXT("TRUCK | R2 / W gas | L2 / S brake | LS / AD steer | Tab camera | Hold Y / keyboard X exit")
                : TEXT("HOVERBIKE | LS / WASD drive | A / Space brake | Shift boost | V camera | E or hold X exit"),
            FLinearColor::White, 30, Canvas->ClipY - 50);
        return;
    }
    const float X = Canvas->ClipX * .5f, Y = Canvas->ClipY * .5f;
    DrawLine(X - 5, Y, X + 5, Y, FLinearColor::White);
    DrawLine(X, Y - 5, X, Y + 5, FLinearColor::White);
    DrawRect(FLinearColor(0, 0, 0, .65f), 18, Canvas->ClipY - 108, FMath::Min(Canvas->ClipX - 36, 850.f), 90);
    DrawText(Pilot->GetPrompt(), FLinearColor::White, 32, Canvas->ClipY - 96, nullptr, 1.1f);
    DrawText(TEXT("LS / WASD move   RS / mouse aim   L2 / RMB aim gun   R2 / LMB fire"), FLinearColor(.8f, .85f, .9f),
             32, Canvas->ClipY - 69);
    const FString MovementHelp =
        Pilot->IsMounted()
            ? FString::Printf(TEXT("A / Space hop   L3 / Shift boost   B / Ctrl coast   F5 view   %.0f m/s"),
                              Pilot->GetSpeedMps())
            : FString::Printf(TEXT("A / Space jump   F5 / Menu view   R reset   %.0f m/s"), Pilot->GetSpeedMps());
    DrawText(MovementHelp, FLinearColor(.8f, .85f, .9f), 32, Canvas->ClipY - 44);
    if (Pilot->HoldProgress() > 0 && Pilot->HoldProgress() < 1)
        DrawRect(FLinearColor(.9f, .1f, .08f), X - 70, Y + 35, 140 * Pilot->HoldProgress(), 5);
    if (Pilot->IsMounted())
    {
        DrawText(TEXT("BOOST"), FLinearColor::White, 28, Canvas->ClipY - 148);
        DrawRect(FLinearColor(.08f, .1f, .13f, .9f), 88, Canvas->ClipY - 141, 220, 12);
        DrawRect(FLinearColor(.2f, .7f, 1.f), 88, Canvas->ClipY - 141, 220 * Pilot->GetBoostCharge(), 12);
    }
}

AHoverGameMode::AHoverGameMode()
{
    DefaultPawnClass = AHoverPilot::StaticClass();
    HUDClass = AHoverHUD::StaticClass();
    PlayerControllerClass = AHoverTestController::StaticClass();
}
void AHoverGameMode::BeginPlay()
{
    Super::BeginPlay();
    GetWorld()->SpawnActor<AHoverZombieRange>();
}
