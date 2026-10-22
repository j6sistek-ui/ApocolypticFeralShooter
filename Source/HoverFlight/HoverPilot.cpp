#include "HoverPilot.h"
#include "HoverTestController.h"
#include "HoverAnimInstance.h"
#include "HoverZombie.h"
#include "EngineUtils.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
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

AHoverPilot::AHoverPilot()
{
    PrimaryActorTick.bCanEverTick = true;
    GetCapsuleComponent()->InitCapsuleSize(32.f, 97.f);
    bUseControllerRotationYaw = true;
    GetCharacterMovement()->MaxWalkSpeed = 500.f;
    GetCharacterMovement()->JumpZVelocity = 420.f;
    GetCharacterMovement()->MaxFlySpeed = 4500.f;
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
    ReviewArm->TargetArmLength = 380;
    ReviewArm->SocketOffset = FVector(0, 40, 60);
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
    Board = NewObject<UPoseableMeshComponent>(BoardActor, TEXT("HoverMechanism"));
    BoardActor->SetRootComponent(Board);
    Board->RegisterComponent();
    Board->SetSkinnedAssetAndUpdate(Assets->Glider);
    Board->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Board->SetBoundsScale(2.f);
    for (const FMeshBoneInfo &Bone : Assets->Glider->GetRefSkeleton().GetRefBoneInfo())
        BoardRest.Add(Bone.Name, Board->GetBoneTransformByName(Bone.Name, EBoneSpaces::ComponentSpace));
    ParkedLocation = StartLocation + GetActorForwardVector() * 150.f - FVector(0, 0, 102);
    BoardActor->SetActorLocationAndRotation(ParkedLocation, StartRotation + FRotator(0, -90, 0));
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
            return;
        }
        FVector MountPoint = BoardActor->GetActorLocation() + FVector(0, 0, 132);
        FHitResult Hit;
        const FVector Before = GetActorLocation();
        SetActorLocation(MountPoint, true, &Hit);
        if (FVector::Dist(GetActorLocation(), MountPoint) > 8.f)
        {
            SetActorLocation(Before);
            StatusMessage = TEXT("Not enough room to mount here.");
            return;
        }
        GetCapsuleComponent()->SetCapsuleSize(90, 110);
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
    }
    else
    {
        FVector Exit = GetActorLocation() + GetActorRightVector() * 130.f + FVector(0, 0, 15);
        FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverExit), false, this);
        const FCollisionShape Shape = FCollisionShape::MakeCapsule(32, 97);
        if (GetWorld()->OverlapBlockingTestByChannel(Exit, FQuat::Identity, ECC_Pawn, Shape, Params))
        {
            Exit = GetActorLocation() - GetActorRightVector() * 130.f + FVector(0, 0, 15);
            if (GetWorld()->OverlapBlockingTestByChannel(Exit, FQuat::Identity, ECC_Pawn, Shape, Params))
            {
                StatusMessage = TEXT("Both sides blocked. Move into clear space.");
                return;
            }
        }
        BoardActor->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
        ParkedLocation = BoardActor->GetActorLocation();
        BoardActor->SetActorRotation(FRotator(0, GetActorRotation().Yaw - 90, 0));
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
    WorldGun->SetVisibility(bReview && bAiming);
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
    bMounted = false;
    bSteppingOn = false;
    BoardPitch = BoardBank = 0;
    TransitionTime = 0;
    HopTime = 0;
    GetCapsuleComponent()->SetCapsuleSize(32, 97);
    GetMesh()->SetRelativeLocation(FVector(0, 0, -97));
    GetMesh()->SetRelativeRotation(FRotator(0, -90, 0));
    SetActorLocationAndRotation(StartLocation + FVector(0, 0, 20), StartRotation);
    GetCharacterMovement()->SetMovementMode(MOVE_Falling);
    GetCharacterMovement()->StopMovementImmediately();
    ParkedLocation = StartLocation + StartRotation.Vector() * 150.f - FVector(0, 0, 102);
    BoardActor->SetActorLocationAndRotation(ParkedLocation, StartRotation + FRotator(0, -90, 0));
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
    UpInput = float(Down(EKeys::Gamepad_RightShoulder) || Down(EKeys::E)) -
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
    bBoost = Down(EKeys::Gamepad_LeftThumbstick) || Down(EKeys::LeftShift);
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
            PlayPose(Assets->AimStart, false);
        }
        else
        {
            PlayPose(Assets->AimEnd, false);
            AimExitTime = Assets->AimEnd ? Assets->AimEnd->GetPlayLength() : 0;
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
    const float Speed = bBoost ? 4000.f : 1800.f;
    FVector Direction = GetActorForwardVector() * ForwardInput + GetActorRightVector() * SideInput;
    Direction = Direction.GetClampedToMaxSize(1.f);
    FVector Desired = Direction * Speed;
    const float Pitch = FRotator::NormalizeAxis(GetControlRotation().Pitch);
    float VerticalCommand = UpInput * 900.f;
    if (FMath::IsNearlyZero(UpInput) && FMath::Abs(ForwardInput) > .05f && FMath::Abs(Pitch) > 5.f)
        VerticalCommand = FMath::Sin(FMath::DegreesToRadians(Pitch)) * ForwardInput * Speed;
    if (HopTime > 0)
    {
        HopTime -= DT;
        Desired.Z = FMath::Max(0.f, Move->Velocity.Z - 500.f * DT);
        TargetAltitude = GetActorLocation().Z;
        bHeightHolding = false;
    }
    else if (FMath::Abs(VerticalCommand) > 1)
    {
        Desired.Z = VerticalCommand;
        bHeightHolding = false;
        TargetAltitude = GetActorLocation().Z;
    }
    else
    {
        if (!bHeightHolding)
        {
            TargetAltitude = GetActorLocation().Z;
            bHeightHolding = true;
        }
        Desired.Z = FMath::Clamp((TargetAltitude - GetActorLocation().Z) * 5.f, -500.f, 500.f);
    }
    if (SlideTime > 0)
    {
        SlideTime -= DT;
        Desired.X = Move->Velocity.X;
        Desired.Y = Move->Velocity.Y;
    }
    Move->Velocity = FMath::VInterpTo(Move->Velocity, Desired, DT, 4.5f);
    if (bHeightHolding && FMath::Abs(Move->Velocity.Z) < 1.f && FMath::Abs(TargetAltitude - GetActorLocation().Z) < 1.f)
        Move->Velocity.Z = 0;
    BoardPitch = FMath::FInterpTo(BoardPitch, -ForwardInput * 8.f + FMath::Clamp(Pitch * .18f, -12.f, 12.f), DT, 5.f);
    BoardBank = FMath::FInterpTo(BoardBank, SideInput * 12.f + TurnInput * 6.f, DT, 5.f);
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
    if (!bAiming && AimExitTime <= 0)
    {
        UAnimSequence *Pose = Assets->Stand;
        if (bMounted)
        {
            Pose = Assets->RideIdle;
            if (ForwardInput > .2f)
                Pose = Assets->RideMove;
            if (UpInput < -.1f)
                Pose = Assets->RideDown;
            if (SideInput < -.25f || TurnInput < -.25f)
                Pose = Assets->RideLeft;
            if (SideInput > .25f || TurnInput > .25f)
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
            Pose.SetRotation(FQuat(FVector::UpVector, FMath::DegreesToRadians(Sign * (FMath::Abs(ForwardInput) * 12.f +
                                                                                      FMath::Abs(SideInput) * 6.f))) *
                             Rest->GetRotation());
            Board->SetBoneTransformByName(Wing, Pose, EBoneSpaces::ComponentSpace);
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
        Instance->bAiming = bAiming;
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
    if (bAiming)
    {
        const FVector Hand = GetMesh()->GetSocketLocation(TEXT("hand_r"));
        const FVector Aim = GetControlRotation().Vector();
        WorldGun->SetWorldLocationAndRotation(Hand + Aim * 20.f + GetActorUpVector() * 3.f,
                                              FRotationMatrix::MakeFromYZ(Aim, GetActorUpVector()).Rotator());
    }
}

void AHoverPilot::FireShot()
{
    ++ShotsFired;
    FireCooldown = .18f;
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
    FHitResult Hit;
    const FVector ShotDirection = (Target - Muzzle).GetSafeNormal();
    GetWorld()->LineTraceSingleByChannel(Hit, Muzzle, Target + ShotDirection * 3.f, ECC_Visibility, Params);
    const FVector Impact = Hit.bBlockingHit ? Hit.ImpactPoint : Target;
    DrawDebugLine(GetWorld(), Muzzle, Impact, FColor(255, 185, 65), false, .1f, 0, 1.5f);
    if (Hit.bBlockingHit)
        DrawDebugSphere(GetWorld(), Impact, 4.f, 8, FColor::Orange, false, .35f);
    if (auto *Zombie = Cast<AHoverZombie>(Hit.GetActor()))
        UGameplayStatics::ApplyPointDamage(Zombie, 35.f, ShotDirection, Hit, GetController(), this, nullptr);
    if (bAiming && Assets->Fire)
    {
        CurrentAnimation = nullptr;
        PlayPose(Assets->Fire, false);
    }
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_SHOT hit=%s"), *GetNameSafe(Hit.GetActor()));
}

void AHoverPilot::Tick(float DT)
{
    Super::Tick(DT);
    if (!Assets)
        return;
    DT = FMath::Min(DT, .05f);
    TransitionTime = FMath::Max(0.f, TransitionTime - DT);
    FireCooldown = FMath::Max(0.f, FireCooldown - DT);
    UpdateInput(DT);
    UpdateFlight(DT);
    UpdateAppearance(DT);
    if (GetActorLocation().Z < -10000)
        HoverReset();
}

FString AHoverPilot::GetPrompt() const
{
    if (TransitionTime > 0)
        return bMounted ? TEXT("Pads locking...") : TEXT("Pads released");
    if (!bMounted)
        if (const auto *PC = Cast<AHoverTestController>(GetController()); PC && PC->IsNearTruck())
            return TEXT("Hold X to drive the Doomsday truck");
    if (!bMounted)
        if (const auto *PC = Cast<AHoverTestController>(GetController()); PC && PC->IsNearBike())
            return TEXT("Hold X to ride the hoverbike");
    if (bMounted)
        return TEXT("Hold X: get off   |   R1 / E: up   L1 / Q: down");
    return HasBoardNearby() ? TEXT("Hold X to step on and lock the pads")
                            : TEXT("Walk to the glider   |   R: reset test");
}

void AHoverHUD::DrawHUD()
{
    Super::DrawHUD();
    const auto *Pilot = Cast<AHoverPilot>(GetOwningPawn());
    if (!Canvas)
        return;
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
    DrawText(FString::Printf(TEXT("A / Space hop   L3 / Shift boost   B / Ctrl slide   F5 review view   %.0f m/s"),
                             Pilot->GetSpeedMps()),
             FLinearColor(.8f, .85f, .9f), 32, Canvas->ClipY - 44);
    if (Pilot->HoldProgress() > 0 && Pilot->HoldProgress() < 1)
        DrawRect(FLinearColor(.9f, .1f, .08f), X - 70, Y + 35, 140 * Pilot->HoldProgress(), 5);
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
