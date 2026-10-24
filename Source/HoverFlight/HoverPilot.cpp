#include "HoverPilot.h"
#include "HoverCyberCity.h"
#include "HoverCombatBridge.h"
#include "HoverLocomotionBridge.h"
#include "HoverTestController.h"
#include "HoverAnimInstance.h"
#include "HoverZombie.h"
#include "HoverShotVisual.h"
#include "HoverMotion.h"
#include "HoverMovementComponent.h"
#include "Settings/ZE_PlayerSettings.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/ConfigCacheIni.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Perception/AISense_Hearing.h"
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
#include "Engine/PostProcessVolume.h"
#include "Engine/DirectionalLight.h"
#include "Components/DirectionalLightComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/SpringArmComponent.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/UnrealType.h"

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
    bUseControllerRotationYaw = false;
    GetCharacterMovement()->MaxWalkSpeed = 600.f;
    GetCharacterMovement()->JumpZVelocity = 600.f;
    GetCharacterMovement()->MaxFlySpeed = 8000.f;
    GetCharacterMovement()->BrakingDecelerationFlying = 0.f;
    GetCharacterMovement()->BrakingFrictionFactor = 0.f;
    GetCharacterMovement()->bUseSeparateBrakingFriction = true;
    GetCharacterMovement()->BrakingFriction = 0.f;
    GetMesh()->SetRelativeLocation(FVector(0, 0, -97));
    GetMesh()->SetRelativeRotation(FRotator(0, -90, 0));
    GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    GetMesh()->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FPSCamera"));
    FirstPersonCamera->SetupAttachment(GetRootComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0, 0, 65));
    FirstPersonCamera->bUsePawnControlRotation = true;
    FirstPersonCamera->FieldOfView = 95;
    ReviewArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("ReviewArm"));
    ReviewArm->SetupAttachment(GetRootComponent());
    ReviewArm->TargetArmLength = 430;
    ReviewArm->SocketOffset = FVector(0, 40, 15);
    ReviewArm->bUsePawnControlRotation = true;
    ReviewCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ReviewCamera"));
    ReviewCamera->SetupAttachment(ReviewArm);
    ReviewCamera->SetAutoActivate(false);
    ViewGun = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("FPSGun"));
    ViewGun->SetupAttachment(FirstPersonCamera);
    ViewGun->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ViewGun->CastShadow = false;
    ViewGun->SetOnlyOwnerSee(true);
    WorldGun = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HeldGun"));
    // The hand supplies position; its animated rotation must not rotate the aim twice.
    WorldGun->SetupAttachment(GetRootComponent());
    WorldGun->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AHoverPilot::BeginPlay()
{
    Super::BeginPlay();
    GetMesh()->AddTickPrerequisiteActor(this);
    SetCanBeDamaged(true); // Hit reactions remain active while invincible.
    GConfig->GetBool(TEXT("AFS.Graphics"), TEXT("Invincible"), bInvincible, GGameUserSettingsIni);
    StartLocation = GetActorLocation();
    StartRotation = GetActorRotation();
    BodyYaw = StartRotation.Yaw;
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
        Component->bCastContactShadow = true;
        if (Part.PhysicsOverride)
            Component->SetPhysicsAsset(Part.PhysicsOverride);
        for (int32 M = 0; M < Part.Materials.Num(); ++M)
            Component->SetMaterial(M, Part.Materials[M]);
        if (Index != 0)
        {
            if (Component->GetBoneIndex(TEXT("afs_chain_01")) != INDEX_NONE)
            {
                Component->SetAnimInstanceClass(UHoverAccessoryAnimInstance::StaticClass());
                Component->AddTickPrerequisiteComponent(GetMesh());
                Component->VisibilityBasedAnimTickOption =
                    EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
            }
            else
                Component->SetLeaderPoseComponent(GetMesh());
        }
        for (const auto &Morph : Part.Morphs)
            Component->SetMorphTarget(Morph.Key, Morph.Value);
        Parts.Add(Component);
    }
    ViewGun->SetStaticMesh(Assets->Gun);
    ViewGun->SetRelativeLocation(FVector(35, 18, -20));
    ViewGun->SetRelativeRotation(FRotator(0, -90, 0));
    WorldGun->SetStaticMesh(Assets->Gun);
    if (Assets->GunOptic)
        for (auto *Gun : {ViewGun.Get(), WorldGun.Get()})
        {
            auto *Optic = NewObject<UStaticMeshComponent>(this);
            Optic->SetupAttachment(Gun);
            Optic->SetStaticMesh(Assets->GunOptic);
            Optic->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Optic->SetOnlyOwnerSee(Gun == ViewGun);
            Optic->CastShadow = Gun != ViewGun;
            Optic->RegisterComponent();
        }
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
    if (auto *BodyPhysics = LoadClass<UAnimInstance>(
            nullptr, TEXT("/Game/HoverPrototype/Appearance/ABP_Vexa_BodyPhysics.ABP_Vexa_BodyPhysics_C")))
        GetMesh()->SetOverridePostProcessAnimBP(BodyPhysics);
    if (bCLSLocomotion)
    {
        LocomotionBridge = NewObject<UHoverLocomotionBridge>(this, TEXT("CLS_Bridge"));
        LocomotionBridge->RegisterComponent();
    }
    PlayPose(Assets->Stand, true);
    MeleeWeapon = GetWorld()->SpawnActor<AHoverMeleeWeapon>();
    if (MeleeWeapon)
    {
        MeleeWeapon->SetWeaponDefinition(LoadObject<UZE_WeaponDefinition>(
            nullptr, TEXT("/Game/HoverPrototype/ZombieEngine/DA_AFS_Melee.DA_AFS_Melee")));
        MeleeWeapon->Equip(this);
    }
    if (Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode()))
    {
        Combat = NewObject<UHoverCombatBridge>(this, TEXT("CyberCitySystems"));
        Combat->RegisterComponent();
    }
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

void AHoverPilot::EndPlay(const EEndPlayReason::Type Reason)
{
    if (bKnockedDown && KnockdownController.IsValid())
        KnockdownController->SetIgnoreMoveInput(false);
    if (DefeatedController.IsValid())
        DefeatedController->SetIgnoreMoveInput(false);
    if (MeleeWeapon)
        MeleeWeapon->Destroy();
    Super::EndPlay(Reason);
}

void AHoverPilot::Melee()
{
    if (!IsOnFoot() || !MeleeWeapon || IsKnockedDown() || IsDefeated())
        return;
    if (Combat)
        Combat->Melee();
    else
    {
        MeleeWeapon->StartFire();
        MeleeWeapon->StopFire();
    }
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

bool AHoverPilot::PrepareForRide()
{
    if (IsKnockedDown() || IsDefeated())
        return false;
    if (MeleeWeapon)
        MeleeWeapon->CancelSwing();
    GroundSlideTime = 0;
    bGroundCrouchHeld = false;
    UnCrouch();
    GetCharacterMovement()->UnCrouch(false);
    if (bIsCrouched)
        return false;
    bProne = false;
    if (Combat)
        Combat->SuspendForRide();
    if (LocomotionBridge)
        LocomotionBridge->CancelAction();
    return true;
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
        if (!PrepareForRide())
            return;
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
        FlightPitch = FlightPitchVelocity = HopTilt = 0;
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
    const bool FirstPerson = !bReview;
    TInlineComponentArray<UCameraComponent *> Cameras(this);
    for (auto *C : Cameras)
        C->SetActive(false);
    FirstPersonCamera->SetActive(FirstPerson);
    ReviewCamera->SetActive(!FirstPerson);
    const bool Swinging = MeleeWeapon && MeleeWeapon->IsSwinging();
    ViewGun->SetVisibility(!Swinging && FirstPerson, true);
    WorldGun->SetVisibility(!Swinging && !FirstPerson && (bAiming || GunRaisedTime > 0), true);
    // The full-body riding pose crosses the eye camera during pitch and recoil.
    // Keep it for the external view; the FPS camera renders its own rifle.
    for (USkeletalMeshComponent *Part : Parts)
        Part->SetOwnerNoSee(FirstPerson);
}

void AHoverPilot::OnStartCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
    Super::OnStartCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
    UpdateCameraPosture(0.f);
}

void AHoverPilot::OnEndCrouch(float HalfHeightAdjust, float ScaledHalfHeightAdjust)
{
    Super::OnEndCrouch(HalfHeightAdjust, ScaledHalfHeightAdjust);
    UpdateCameraPosture(0.f);
}

void AHoverPilot::UpdateCameraPosture(float DT)
{
    const float StandingHeight =
        GetClass()->GetDefaultObject<AHoverPilot>()->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
    const float CapsuleDrop = bMounted ? 0.f : StandingHeight - GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
    // Capsule resizing must not teleport the viewpoint. Compensate immediately,
    // then ease the actual stance height; neither jumping nor animation changes arm length.
    const float Smoothed = FMath::FInterpTo(CameraPostureHeight, bKnockedDown ? -65.f : -CapsuleDrop, DT, 8.f);
    CameraPostureHeight += FMath::Clamp(Smoothed - CameraPostureHeight, -100.f * DT, 100.f * DT);
    const float Offset = CapsuleDrop + CameraPostureHeight;
    ReviewArm->SetRelativeLocation(FVector(0, 0, Offset));
    FirstPersonCamera->SetRelativeLocation(FVector(0, 0, (bMounted ? 33.f : 65.f) + Offset));
}

void AHoverPilot::HoverReset()
{
    bDefeated = false;
    if (DefeatedController.IsValid())
        DefeatedController->SetIgnoreMoveInput(false);
    DefeatedController.Reset();
    SandboxHealth = 100.f;
    if (Combat && Combat->Survival)
        Combat->Survival->SetHealth(100.f);
    RespawnGraceUntil = GetWorld()->GetTimeSeconds() + 2.f;
    if (LocomotionBridge)
        LocomotionBridge->CancelAction();
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
    if (bDefeated)
    {
        ForwardInput = SideInput = TurnInput = PitchInput = 0;
        ConsumeMovementInputVector();
        if (Combat)
            Combat->SetTrigger(false);
        if (GetWorld()->GetTimeSeconds() >= DefeatedUntil)
            HoverReset();
        return;
    }
    if (bKnockedDown)
    {
        ForwardInput = SideInput = TurnInput = PitchInput = 0;
        ConsumeMovementInputVector();
        if (Combat)
            Combat->SetTrigger(false);
        if (GetWorld()->GetTimeSeconds() >= KnockdownUntil)
        {
            bKnockedDown = false;
            if (KnockdownController.IsValid())
                KnockdownController->SetIgnoreMoveInput(false);
            KnockdownController.Reset();
            KnockdownGraceUntil = GetWorld()->GetTimeSeconds() + 1.f;
        }
        return;
    }
    if (Combat && Combat->IsInventoryOpen())
    {
        ForwardInput = SideInput = TurnInput = PitchInput = 0;
        Combat->SetTrigger(false);
        return;
    }
    auto Down = [PC](FKey Key) { return PC->IsInputKeyDown(Key); };
    ForwardInput = FMath::Clamp(Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftY)) + float(Down(EKeys::W)) -
                                    float(Down(EKeys::S)),
                                -1.f, 1.f);
    SideInput = FMath::Clamp(Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftX)) + float(Down(EKeys::D)) -
                                 float(Down(EKeys::A)),
                             -1.f, 1.f);
    PitchInput = ForwardInput;
    BankInput = float(Down(EKeys::Gamepad_LeftShoulder) || Down(EKeys::Q));
    if (bMounted)
        ForwardInput =
            FMath::Clamp(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) + float(Down(EKeys::E)), 0.f, 1.f);
    TurnInput = Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightX));
    float MouseX = 0, MouseY = 0;
    PC->GetInputMouseDelta(MouseX, MouseY);
    FRotator Look = PC->GetControlRotation();
    const bool TemplateOnFoot = bParkourMovement && !bMounted;
    const auto *LiveSettings = Combat ? GetDefault<UZE_PlayerSettings>() : nullptr;
    const float Sensitivity = LiveSettings ? LiveSettings->LookSensitivity : 1.f;
    Look.Yaw += TurnInput * 120.f * DT * Sensitivity + (TemplateOnFoot ? 0.f : MouseX * .12f);
    Look.Pitch = FMath::Clamp(FRotator::NormalizeAxis(Look.Pitch) -
                                  Stick(PC->GetInputAnalogKeyState(EKeys::Gamepad_RightY)) * 90.f * DT * Sensitivity +
                                  (TemplateOnFoot ? 0.f : MouseY * .12f),
                              -75.f, 75.f);
    Look.Roll = 0;
    PC->SetControlRotation(Look);
    bBoostHeld = Down(EKeys::Gamepad_LeftThumbstick) || Down(EKeys::LeftShift);
    if (!bMounted)
    {
        auto *Move = GetCharacterMovement();
        const bool Sprint = Down(EKeys::Gamepad_LeftThumbstick);
        const auto *CyberMode = Cast<AHoverCyberCityGameMode>(GetWorld()->GetAuthGameMode());
        const float PowerUpSpeed = CyberMode ? CyberMode->GetSpeedBonus() : 1.f;
        const float RunSpeed = LiveSettings ? LiveSettings->SprintSpeed : 900.f;
        const float WalkSpeed = LiveSettings ? LiveSettings->WalkSpeed : 500.f;
        Move->MaxWalkSpeed = (Sprint ? RunSpeed : WalkSpeed) * PowerUpSpeed;
        // Per-axis controller dead zones reduce diagonal magnitude. A deliberate
        // held sprint retains its gait through a turn; partial walking stays analog.
        Move->MinAnalogWalkSpeed =
            Sprint && !bIsCrouched && FVector2D(ForwardInput, SideInput).Size() > .6f ? RunSpeed * PowerUpSpeed : 0.f;
    }
    const bool Hold = Down(EKeys::Gamepad_FaceButton_Left) || Down(EKeys::X);
    const bool HasInteractable = Combat && !Combat->GetPrompt().IsEmpty();
    if (Hold && !bHoldConsumed && !HasInteractable)
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
        if (Combat && HoldTime > 0 && HoldTime < .65f && !bHoldConsumed && !HasInteractable)
            Combat->Reload();
        HoldTime = 0;
        bHoldConsumed = false;
    }
    const bool JumpPressed = Down(EKeys::Gamepad_FaceButton_Bottom) || Down(EKeys::SpaceBar);
    if (JumpPressed && !bWasJump && TransitionTime <= 0)
    {
        if (bMounted && HopTime <= 0)
        {
            HopStartZ = GetActorLocation().Z;
            HopTime = 1.20f;
            bHeightHolding = false;
            ImpactPulse(BoardActor->GetActorLocation() - FVector(0, 0, 8), FVector::UpVector, .28f, .15f, .40f);
        }
        else if (!bParkourMovement)
            Jump();
    }
    if (!JumpPressed && bWasJump && !bParkourMovement)
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
    const bool Reset = Down(EKeys::Home) || (!Combat && Down(EKeys::R));
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
    const bool FirePressed = bMounted ? Down(EKeys::Gamepad_RightShoulder)
                                      : PC->GetInputAnalogKeyState(EKeys::Gamepad_RightTriggerAxis) > .2f;
    if (Combat)
        Combat->SetTrigger((FirePressed || Down(EKeys::LeftMouseButton)) && TransitionTime <= 0);
    else if ((FirePressed || Down(EKeys::LeftMouseButton)) && FireCooldown <= 0 && TransitionTime <= 0 &&
             !(MeleeWeapon && MeleeWeapon->IsSwinging()))
        FireShot();
}

void AHoverPilot::CancelPostureInput()
{
    bGroundCrouchHeld = false;
    GroundCrouchHold = 0;
    bCrouchedAtPress = false;
}

void AHoverPilot::SetParkourCrouch(bool Held)
{
    if (IsKnockedDown() || IsDefeated())
        return;
    if (bMounted)
        return;
    auto *Move = GetCharacterMovement();
    Move->GetNavAgentPropertiesRef().bCanCrouch = true;
    if (Held == bGroundCrouchHeld)
        return;
    if (Held)
    {
        GroundCrouchHold = 0;
        bCrouchedAtPress = bIsCrouched;
        if (Move->IsMovingOnGround() && !bIsCrouched)
        {
            Move->SetCrouchedHalfHeight(60.f);
            if (GetVelocity().Size2D() > 600.f)
            {
                GroundSlideTime = .9f;
                GroundSlideSpeed = FMath::Min(GetVelocity().Size2D(), 900.f);
            }
            Crouch();
        }
    }
    else if (GroundCrouchHold < .55f && bCrouchedAtPress)
    {
        GroundSlideTime = 0;
        UnCrouch();
    }
    bGroundCrouchHeld = Held;
}

void AHoverPilot::UpdateGroundPosture(float DT)
{
    if (bMounted)
        return;
    auto *Move = GetCharacterMovement();
    if (!bIsCrouched)
        bProne = false;
    GroundCrouchHold += bGroundCrouchHeld ? DT : 0.f;
    if (bGroundCrouchHeld && GroundCrouchHold >= .55f && GroundSlideTime <= 0 && Move->IsMovingOnGround() && !bProne)
    {
        bProne = true;
        Move->SetCrouchedHalfHeight(34.f);
        Crouch();
        // Apply a second crouched size through CharacterMovement's floor-preserving path.
        Move->Crouch(false);
    }
    if (GroundSlideTime > 0 && Move->IsMovingOnGround())
    {
        GroundSlideTime = FMath::Max(0.f, GroundSlideTime - DT);
        Move->MaxWalkSpeedCrouched = GroundSlideSpeed;
        // Preserve the purchased Parkour slide's low-friction mechanism, with
        // CharacterMovement handling capsule/floor and an airborne guard.
        Move->GroundFriction = .08f;
        Move->BrakingDecelerationWalking = 450.f;
    }
    else if (bIsCrouched)
    {
        GroundSlideTime = 0;
        Move->MaxWalkSpeedCrouched =
            bProne ? 120.f : (Combat ? GetDefault<UZE_PlayerSettings>()->CrouchedSpeed : 400.f);
        Move->GroundFriction = 8.f;
        Move->BrakingDecelerationWalking = 2048.f;
    }
}

void AHoverPilot::UpdateFlight(float DT)
{
    UCharacterMovementComponent *Move = GetCharacterMovement();
    if (!bBoostHeld && BoostCharge >= .2f)
        bBoostExhausted = false;
    bBoost =
        bMounted && TransitionTime <= 0 && bBoostHeld && !bBoostExhausted && BoostCharge > 0 && ForwardInput > .05f;
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
        const FRotator Facing(0, GetControlRotation().Yaw, 0);
        // The template owns grounded movement. The visual body can face travel
        // without changing the capsule basis used by its original input graph.
        if (!bParkourMovement)
        {
            SetActorRotation(Facing);
            AddMovementInput(Facing.Vector(), ForwardInput);
            AddMovementInput(FRotationMatrix(Facing).GetUnitAxis(EAxis::Y), SideInput);
        }
        const FVector Travel = GetVelocity();
        const float TargetYaw = UsesAimFacing() ? Facing.Yaw : Travel.Size2D() > 12.f ? Travel.Rotation().Yaw : BodyYaw;
        const float TurnRate = LocomotionBridge && LocomotionBridge->bEnabled ? 180.f : 540.f;
        const float Step =
            FMath::Clamp(FMath::FindDeltaAngleDegrees(BodyYaw, TargetYaw), -TurnRate * DT, TurnRate * DT);
        GroundYawRate = DT > 0 ? Step / DT : 0;
        BodyYaw = FRotator::NormalizeAxis(BodyYaw + Step);
        return;
    }
    const float ForwardSpeed = FVector::DotProduct(Move->Velocity, GetActorForwardVector());
    const float BankYaw = HoverMotion::BankYawRate(BoardBank, ForwardSpeed);
    // Flight heading is independent of the head/weapon camera. Banking bends
    // the velocity; the left stick supplies low-speed steering authority too.
    const float SteeringYaw = SideInput * (30.f + 15.f * BankInput);
    SetActorRotation(FRotator(0, GetActorRotation().Yaw + (SteeringYaw + BankYaw) * DT, 0));
    GroundYawRate = 0;
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
    const float Speed = bBoost ? 5600.f : 2160.f;
    FVector Direction = GetActorForwardVector() * ForwardInput;
    Direction = Direction.GetClampedToMaxSize(1.f);
    const FVector PreviousVelocity = Move->Velocity;
    FVector Desired = HoverMotion::HorizontalVelocity(PreviousVelocity, Direction, Speed, DT, bBoost);
    Desired = HoverMotion::ApplyBank(Desired, BoardBank * (ForwardSpeed < 0 ? -1.f : 1.f), DT);
    HoverMotion::Spring(FlightPitch, FlightPitchVelocity, PitchInput * 45.f, DT, 7.f);
    const float Pitch = FlightPitch;
    const float AlongSpeed = FVector::DotProduct(Desired, GetActorForwardVector());
    const float VerticalCommand = FMath::Abs(PitchInput) > .05f
                                      ? FMath::Sin(FMath::DegreesToRadians(Pitch)) /
                                            FMath::Sin(FMath::DegreesToRadians(45.f)) *
                                            (PitchInput > 0 ? 1800.f : 2400.f) * (bBoost ? 1.25f : 1.f)
                                      : 0.f;
    HopTilt = 0;
    if (HopTime > 0)
    {
        HopTime = FMath::Max(0.f, HopTime - DT);
        const float T = 1.20f - HopTime;
        Desired.Z = (HopStartZ + HoverMotion::OllieHeight(T) - GetActorLocation().Z) / FMath::Max(DT, .001f);
        HopTilt = T < .42f ? 11.f * FMath::Sin(PI * T / .42f) : -4.f * FMath::Sin(PI * (T - .42f) / .78f);
        TargetAltitude = HopStartZ + 166.f;
        bHeightHolding = HopTime <= 0;
    }
    else if (FMath::Abs(VerticalCommand) > 1)
    {
        Desired.Z = FMath::FInterpConstantTo(PreviousVelocity.Z, VerticalCommand, DT, 3600.f);
        bHeightHolding = false;
        TargetAltitude = GetActorLocation().Z;
    }
    else
    {
        if (!bHeightHolding)
        {
            // Account for the remaining vertical stopping distance before holding.
            TargetAltitude = GetActorLocation().Z + PreviousVelocity.Z * FMath::Abs(PreviousVelocity.Z) / 7200.f;
            bHeightHolding = true;
        }
        Desired.Z = FMath::FInterpConstantTo(
            PreviousVelocity.Z, FMath::Clamp((TargetAltitude - GetActorLocation().Z) * 3.f, -2400.f, 2400.f), DT,
            3600.f);
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
    const float Travel = FMath::Clamp(AlongSpeed / 2160.f, -1.f, 1.f);
    const float MomentumPitchWeight = 1.f - FMath::Clamp(FMath::Abs(Pitch) / 20.f, 0.f, 1.f);
    HoverMotion::Spring(
        BoardPitch, PitchVelocity,
        FMath::Clamp(Pitch * .85f + HopTilt - (Travel * 6.f + ForwardForce * 8.f) * MomentumPitchWeight, -42.f, 42.f),
        DT);
    HoverMotion::Spring(BoardBank, BankVelocity, SideInput * (18.f + BankInput * 17.f), DT);
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
    if (Combat)
        if (const auto *Weapon = Combat->GetWeapon(); Weapon && Weapon->IsReloading())
            GunRaisedTime = FMath::Max(GunRaisedTime, .5f);
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
            if (FVector::DotProduct(GetVelocity(), GetActorForwardVector()) < -150.f && Assets->RideReverse)
                Pose = Assets->RideReverse;
            if (BoardBank < -7.f)
                Pose = Assets->RideLeft;
            if (BoardBank > 7.f)
                Pose = Assets->RideRight;
        }
        else if (GetCharacterMovement()->IsFalling())
            Pose = GetVelocity().Z > 80.f ? Assets->JumpPose : Assets->FallPose;
        else if (GetVelocity().Size2D() < 12.f && FMath::Abs(GroundYawRate) > 8.f)
            Pose = GroundYawRate < 0 ? Assets->TurnLeft : Assets->TurnRight;
        PlayPose(Pose, true);
    }
    FirstPersonCamera->SetFieldOfView(FMath::FInterpTo(FirstPersonCamera->FieldOfView,
                                                       bAiming ? 65.f : (bBoost && bMounted ? 105.f : 95.f), DT, 10.f));
    ReviewCamera->SetFieldOfView(FMath::FInterpTo(ReviewCamera->FieldOfView, bAiming ? 72.f : 90.f, DT, 10.f));
    UpdateCameraPosture(DT);
    const FQuat GunBasis = FQuat::FindBetweenNormals(Assets->GunForward.GetSafeNormal(), FVector::ForwardVector);
    const FVector SightAligned = FVector(20, 0, 0) - GunBasis.RotateVector(Assets->GunSight);
    WeaponAimAlpha = FMath::FInterpTo(WeaponAimAlpha, bAiming ? 1.f : 0.f, DT, 12.f);
    ViewGun->SetRelativeLocation(FMath::Lerp(FVector(35, 18, -20), SightAligned, WeaponAimAlpha));
    ViewGun->SetRelativeRotation(GunBasis);
    const float LockTarget = bMounted && !bSteppingOn ? 1.f : 0.f;
    // Substep the pad spring without discarding elapsed time on slow frames.
    for (float Remaining = DT; Remaining > 0;)
    {
        const float Step = FMath::Min(Remaining, 1.f / 120.f);
        LockVelocity += (100.f * (LockTarget - LockAlpha) - 16.f * LockVelocity) * Step;
        LockAlpha = FMath::Clamp(LockAlpha + LockVelocity * Step, 0.f, 1.06f);
        Remaining -= Step;
    }
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
                 : FRotator(0, BodyYaw - GetActorRotation().Yaw - 90.f, 0));
    if (auto *Instance = Cast<UHoverAnimInstance>(GetMesh()->GetAnimInstance()))
    {
        Instance->FootLock = bMounted ? 1.f : 0.f;
        Instance->bProne = bProne;
        const FVector LocalVelocity =
            FRotator(0, bMounted ? GetActorRotation().Yaw : BodyYaw, 0).UnrotateVector(GetVelocity());
        const float Speed = LocalVelocity.Size2D();
        if (Speed > 8.f)
            GroundDirection = FMath::RadiansToDegrees(FMath::Atan2(LocalVelocity.Y, LocalVelocity.X));
        Instance->Locomotion = Assets->Locomotion;
        Instance->LocomotionInput = FVector(GroundDirection, Speed, 0);
        const bool Turning = !bMounted && Speed < 12.f && FMath::Abs(GroundYawRate) > 8.f;
        Instance->bGroundLocomotion = !bMounted && !GetCharacterMovement()->IsFalling() && !Turning;
        Instance->SequenceRate = Turning ? FMath::Clamp(FMath::Abs(GroundYawRate) / 95.f, .25f, 1.4f) : 1.f;
        Instance->RideBlend = Assets->RideBlend;
        Instance->bRiding = bMounted;
        const float Along = FVector::DotProduct(GetVelocity(), GetActorForwardVector());
        const float PitchDemand = FlightPitch;
        Instance->RideInput = FVector(FMath::Clamp((BoardBank + SideInput * 12.f + TurnInput * 12.f) / 28.f, -1.f, 1.f),
                                      FMath::Clamp(Along / 1800.f - PitchDemand / 50.f, -1.f, 1.f), 0);
        Instance->RifleAim = bMounted && Assets->RideGunPose ? Assets->RideGunPose : Assets->RifleAim;
        Instance->RifleFire = bMounted ? Assets->Fire.Get() : nullptr;
        Instance->ShotSerial = ShotsFired;
        Instance->bAiming =
            (bAiming || GunRaisedTime > 0) && !(LocomotionBridge && LocomotionBridge->IsActionPlaying());
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
    const bool Swinging = MeleeWeapon && MeleeWeapon->IsSwinging();
    WorldGun->SetVisibility(!Swinging && bReview && (bAiming || GunRaisedTime > 0), true);
    ViewGun->SetVisibility(!Swinging && !bReview, true);
    UpdateGunTransform();
    const bool Powered = bMounted && TransitionTime <= 0 && !bSteppingOn;
    const float Thrust = FMath::Max(FMath::Abs(ForwardInput), FMath::Abs(SideInput));
    for (UNiagaraComponent *Effect : Boosters)
    {
        const bool Active = Powered && Thrust > .05f;
        const float Scale = bBoost ? .70f : .30f + .10f * Thrust;
        Effect->SetVariableFloat(TEXT("User.ThrustAlpha"), bBoost ? .80f : .40f * Thrust);
        Effect->SetVariableFloat(TEXT("User.ThrustSize"), BoosterSize * Scale);
        Effect->SetVariableFloat(TEXT("User.ThurstSpawningRate"), BoosterSpawnRate * (bBoost ? 1.f : .40f * Thrust));
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
    if (!Assets)
        return;
    const UCameraComponent *Camera = bReview ? ReviewCamera : FirstPersonCamera;
    const FVector Eye = Camera->GetComponentLocation();
    const FVector RayEnd = Eye + Camera->GetForwardVector() * 50000.f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverWeaponAlignment), true, this);
    Params.AddIgnoredActor(BoardActor);
    FHitResult Hit;
    GetWorld()->LineTraceSingleByChannel(Hit, Eye, RayEnd, ECC_Visibility, Params);
    const FVector Target = Hit.bBlockingHit ? Hit.ImpactPoint : RayEnd;
    const FQuat Basis = FQuat::FindBetweenNormals(Assets->GunForward.GetSafeNormal(), FVector::ForwardVector);
    const FVector Hand = GetMesh()->GetSocketLocation(TEXT("hand_r"));
    FQuat WorldRotation = GetControlRotation().Quaternion() * Basis;
    for (int32 I = 0; I < 3; ++I)
    {
        const FVector Origin = Hand - WorldRotation.RotateVector(Assets->GunGrip);
        const FVector Muzzle = Origin + WorldRotation.RotateVector(Assets->GunMuzzle);
        WorldRotation = (Target - Muzzle).Rotation().Quaternion() * Basis;
    }
    WorldGun->SetWorldLocationAndRotation(Hand - WorldRotation.RotateVector(Assets->GunGrip), WorldRotation);
    // Keep the sight centred while the barrel converges on the same aim point.
    // The tracer then travels along that barrel axis with no steering in flight.
    const FVector SightAnchor = ViewGun->GetComponentTransform().TransformPosition(Assets->GunSight);
    FQuat ViewRotation = FirstPersonCamera->GetComponentQuat() * Basis;
    for (int32 I = 0; I < 3; ++I)
    {
        const FVector Origin = SightAnchor - ViewRotation.RotateVector(Assets->GunSight);
        const FVector Muzzle = Origin + ViewRotation.RotateVector(Assets->GunMuzzle);
        ViewRotation = (Target - Muzzle).Rotation().Quaternion() * Basis;
    }
    ViewGun->SetWorldLocationAndRotation(SightAnchor - ViewRotation.RotateVector(Assets->GunSight), ViewRotation);
}

void AHoverPilot::FireShot(float Damage, float Spread, float Range)
{
    ++ShotsFired;
    FireCooldown = .18f;
    GunRaisedTime = 3.f;
    UpdateGunTransform();
    SetView();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverShot), true, this);
    Params.AddIgnoredActor(BoardActor);
    const UStaticMeshComponent *Gun = bReview ? WorldGun.Get() : ViewGun.Get();
    const FVector Muzzle = GetMuzzlePosition();
    if (Combat)
        UAISense_Hearing::ReportNoiseEvent(this, Muzzle, 1.f, this, 3000.f, TEXT("Gunshot"));
    const FVector BarrelDirection =
        Gun->GetComponentTransform().TransformVectorNoScale(Assets->GunForward).GetSafeNormal();
    const FVector ShotDirection = FMath::VRandCone(BarrelDirection, FMath::DegreesToRadians(Spread));
    const FVector Target = Muzzle + ShotDirection * Range;
    if (auto *System = Cast<UNiagaraSystem>(Assets->MuzzleEffect))
    {
        auto *Flash = UNiagaraFunctionLibrary::SpawnSystemAttached(
            System, bReview ? WorldGun : ViewGun, NAME_None, Assets->GunMuzzle,
            FRotationMatrix::MakeFromZ(Assets->GunForward).Rotator(), EAttachLocation::KeepRelativeOffset, true);
        if (Flash)
        {
            TWeakObjectPtr<UNiagaraComponent> WeakFlash(Flash);
            FTimerHandle Timer;
            GetWorld()->GetTimerManager().SetTimer(
                Timer,
                [WeakFlash]() {
                    if (WeakFlash.IsValid())
                        WeakFlash->DestroyComponent();
                },
                .07f, false);
        }
    }
    FHitResult Hit;
    GetWorld()->LineTraceSingleByChannel(Hit, Muzzle, Target + ShotDirection * 3.f, ECC_Visibility, Params);
    auto *Tracer = GetWorld()->SpawnActor<AHoverShotVisual>();
    if (Tracer)
        Tracer->Launch(Muzzle, Hit.bBlockingHit ? Hit.ImpactPoint : Target);
    if (auto *Zombie = Cast<AHoverZombie>(Hit.GetActor()))
        UGameplayStatics::ApplyPointDamage(Zombie, Damage, ShotDirection, Hit, GetController(), this, nullptr);
    else if (auto *CyberZombie = Cast<AHoverCyberZombie>(Hit.GetActor()))
        UGameplayStatics::ApplyPointDamage(CyberZombie, Damage, ShotDirection, Hit, GetController(), this, nullptr);
    else if (Hit.bBlockingHit && Assets->SurfaceImpact)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, 1.f, 0, .9f, Assets->SurfaceImpact);
    if (Assets->ShotSound)
        UGameplayStatics::PlaySoundAtLocation(this, Assets->ShotSound, Muzzle, .60f, FMath::FRandRange(.96f, 1.04f));
    if (bMounted && bAiming && Assets->Fire)
    {
        CurrentAnimation = nullptr;
        PlayPose(Assets->Fire, false);
    }
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_SHOT hit=%s"), *GetNameSafe(Hit.GetActor()));
}

FVector AHoverPilot::GetMuzzlePosition() const
{
    const UStaticMeshComponent *Gun = bReview ? WorldGun.Get() : ViewGun.Get();
    return Gun->GetComponentTransform().TransformPosition(Assets ? Assets->GunMuzzle : FVector(0, 46.f, 2.f));
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
        if (Niagara && Template == Assets->SurfaceImpact)
        {
            Niagara->SetVariableVec3(TEXT("User.DustOffset"), FVector::ZeroVector);
            Niagara->SetVariableVec3(TEXT("User.RockOffset"), FVector::ZeroVector);
            Niagara->SetVariableFloat(TEXT("User.DustSize"), 55.f);
            Niagara->SetVariableFloat(TEXT("User.DustSpawningRate"), 180.f);
            Niagara->SetVariableFloat(TEXT("User.RockImpulse"), 350.f);
            Niagara->SetVariableInt(TEXT("User.RockSpawningRate"), 8);
            Niagara->SetVariableFloat(TEXT("User.RockSpawnRate"), 45.f);
            Niagara->SetVariableLinearColor(TEXT("User.EffectColor"), FLinearColor(.25f, .20f, .15f, 1));
            TWeakObjectPtr<UNiagaraComponent> WeakDust(Niagara);
            FTimerHandle StopEmission;
            GetWorld()->GetTimerManager().SetTimer(
                StopEmission,
                [WeakDust]() {
                    if (WeakDust.IsValid())
                        WeakDust->Deactivate();
                },
                .08f, false);
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

float AHoverPilot::GetHealth() const
{
    return Combat && Combat->Survival ? Combat->Survival->GetHealth() : SandboxHealth;
}

float AHoverPilot::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventInstigator, AActor *Causer)
{
    if (bDefeated || Damage <= 0 || GetWorld()->GetTimeSeconds() < RespawnGraceUntil)
        return 0.f;
    if (Damage > 0 && Causer != this && LocomotionBridge && IsOnFoot() &&
        GetWorld()->GetTimeSeconds() - LastHitReaction > .65f && !LocomotionBridge->IsActionPlaying())
    {
        LastHitReaction = GetWorld()->GetTimeSeconds();
        LocomotionBridge->PlayAction(
            LoadObject<UAnimSequence>(nullptr, TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/HitReact/"
                                                    "MM_HitReact_Front_Lgt_01.MM_HitReact_Front_Lgt_01")));
    }
    if (bInvincible)
        return 0.f;
    const float Applied =
        FMath::Min(GetHealth(), FMath::Max(0.f, Super::TakeDamage(Damage, Event, EventInstigator, Causer)));
    SandboxHealth = FMath::Max(0.f, GetHealth() - Applied);
    if (Combat && Combat->Survival)
        Combat->Survival->SetHealth(SandboxHealth);
    if (SandboxHealth <= 0)
    {
        bDefeated = true;
        DefeatedUntil = GetWorld()->GetTimeSeconds() + 3.f;
        bKnockedDown = false;
        if (KnockdownController.IsValid())
            KnockdownController->SetIgnoreMoveInput(false);
        KnockdownController.Reset();
        DefeatedController = Controller;
        if (Controller)
            Controller->SetIgnoreMoveInput(true);
        GetCharacterMovement()->StopMovementImmediately();
        CancelPostureInput();
        if (Combat)
        {
            Combat->SetTrigger(false);
            if (Combat->IsInventoryOpen())
                Combat->ToggleInventory();
            if (auto *Weapon = Cast<AHoverCyberRifle>(Combat->GetWeapon()))
                Weapon->CancelReload();
        }
        if (MeleeWeapon)
            MeleeWeapon->CancelSwing();
        if (LocomotionBridge)
            LocomotionBridge->PlayAction(
                LoadObject<UAnimSequence>(
                    nullptr,
                    TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Death/MM_Death_Back_01.MM_Death_Back_01")),
                3.f, false);
    }
    return Applied;
}

void AHoverPilot::ShowStompPulse(const FVector &Location, const FVector &Normal, float Radius, bool Close)
{
    ImpactPulse(Location + Normal * 3.f, Normal, Radius / 800.f, Close ? .5f : 0.f, .8f);
}

bool AHoverPilot::ApplyStompKnockdown(FVector Origin)
{
    if (!IsOnFoot() || !Controller || bDefeated || bKnockedDown || GetWorld()->GetTimeSeconds() < KnockdownGraceUntil)
        return false;
    auto *Clip =
        LoadObject<UAnimSequence>(nullptr, TEXT("/Game/HoverPrototype/Animations/QA_StompRecovery.QA_StompRecovery"));
    if (!Clip || !LocomotionBridge)
        return false;
    if (Combat)
    {
        Combat->SetTrigger(false);
        if (Combat->IsInventoryOpen())
            Combat->ToggleInventory();
        if (auto *Weapon = Cast<AHoverCyberRifle>(Combat->GetWeapon()))
            Weapon->CancelReload();
    }
    if (MeleeWeapon)
        MeleeWeapon->CancelSwing();
    CancelPostureInput();
    GroundSlideTime = 0;
    bProne = false;
    UnCrouch();
    bAiming = false;
    LocomotionBridge->CancelAction();
    if (!LocomotionBridge->PlayAction(Clip, 2.1f, false))
        return false;
    bKnockedDown = true;
    KnockdownUntil = GetWorld()->GetTimeSeconds() + 2.1f;
    KnockdownController = Controller;
    Controller->SetIgnoreMoveInput(true);
    LaunchCharacter((GetActorLocation() - Origin).GetSafeNormal2D() * 430.f + FVector(0, 0, 90), true, true);
    SetView();
    return true;
}

void AHoverPilot::BoardHit(UPrimitiveComponent *HitComponent, AActor *OtherActor, UPrimitiveComponent *OtherComponent,
                           FVector NormalImpulse, const FHitResult &Hit)
{
    if (!bMounted && Hit.ImpactNormal.Z > .6f && NormalImpulse.Size() > 1800.f)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, .35f, .1f, .5f);
}

void AHoverPilot::Tick(float DT)
{
    bUseControllerRotationYaw = bParkourMovement && !bMounted;
    if (bParkourMovement)
    {
        // Keep the template's dynamic material alive across editor garbage collection.
        if (auto *Property = FindFProperty<FObjectProperty>(GetClass(), TEXT("Speedline Material Instance")))
        {
            auto *Material = Cast<UMaterialInstanceDynamic>(Property->GetObjectPropertyValue_InContainer(this));
            if (!IsValid(Material))
            {
                auto *Parent = LoadObject<UMaterialInterface>(
                    nullptr, TEXT("/Game/ParkourMovementPack/Materials/MI_Speedlines.MI_Speedlines"));
                Material = UMaterialInstanceDynamic::Create(Parent, this);
                Property->SetObjectPropertyValue_InContainer(this, Material);
            }
            ParkourSpeedlines = Material;
        }
    }
    Super::Tick(DT);
    if (!Assets)
        return;
    // Movement, input and timers must use the same elapsed time as the world.
    // The explicit pad spring substeps separately; board springs are analytic.
    TransitionTime = FMath::Max(0.f, TransitionTime - DT);
    FireCooldown = FMath::Max(0.f, FireCooldown - DT);
    StatusTime = FMath::Max(0.f, StatusTime - DT);
    UpdateInput(DT);
    UpdateGroundPosture(DT);
    if (LocomotionBridge && LocomotionBridge->bEnabled && !bMounted && GetCharacterMovement()->IsMovingOnGround() &&
        GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight() >= 70)
    {
        const bool InputHeld = FMath::Abs(ForwardInput) + FMath::Abs(SideInput) > .05f;
        GetCharacterMovement()->GroundFriction = InputHeld ? 4.5f : 8.f;
        GetCharacterMovement()->BrakingDecelerationWalking = InputHeld ? 350.f : 2048.f;
    }
    UpdateFlight(DT);
    GetMesh()->SetRelativeLocation(
        FVector(0, 0, bMounted ? -97.f : -GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight()));
    UpdateAppearance(DT);
    if (GetActorLocation().Z < -10000)
        HoverReset();
}

FString AHoverPilot::GetPrompt() const
{
    if (bDefeated)
        return TEXT("Defeated - resetting at the start...");
    if (Combat && !Combat->GetPrompt().IsEmpty())
        return Combat->GetPrompt();
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
        return CanDismount() ? TEXT("Hold X: get off   |   Hold L1 / Q: stronger bank while steering")
                             : TEXT("Descend and slow down to get off   |   Hold L1 / Q: stronger bank");
    return HasBoardNearby() ? TEXT("Hold X to step on and lock the pads")
                            : (Combat ? TEXT("Walk to the glider   |   Home: reset test")
                                      : TEXT("Walk to the glider   |   R: reset test"));
}

void AHoverHUD::DrawHUD()
{
    Super::DrawHUD();
    const auto *Pilot = Cast<AHoverPilot>(GetOwningPawn());
    if (!Canvas)
        return;
    DrawText(TEXT("D-pad Up / F6: graphics + test level"), FLinearColor(.7f, .85f, 1.f), 24, 16);
    const FString HealthLabel =
        Pilot ? FString::Printf(TEXT("%s | HP %.0f/100"), Pilot->IsInvincible() ? TEXT("INVINCIBLE") : TEXT("NORMAL"),
                                Pilot->GetHealth())
              : TEXT("VEHICLE");
    if (auto *Waves = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>())
        DrawText(FString::Printf(TEXT("%s | Kills: %d | Gold: %d%s"), *HealthLabel, Waves->GetTotalZombiesKilled(),
                                 Waves->GetGold(),
                                 Waves->GetSpeedBonus() > 1.f ? TEXT(" | SPEED PICKUP 1.5x") : TEXT("")),
                 FLinearColor(.8f, 1.f, .8f), 24, 38);
    for (TActorIterator<AHoverZombieRange> It(GetWorld()); It; ++It)
    {
        DrawText(
            FString::Printf(TEXT("%s | Zombies: %d | Kills: %d"), *HealthLabel, It->GetAliveCount(), It->GetKills()),
            FLinearColor(.8f, 1.f, .8f), 24, 38);
        break;
    }
    if (!Pilot)
    {
        DrawRect(FLinearColor(0, 0, 0, .6f), 18, Canvas->ClipY - 68, 900, 50);
        const auto *PC = Cast<AHoverTestController>(GetOwningPlayerController());
        DrawText(PC && PC->IsDrivingTruck()
                     ? TEXT("TRUCK | R2 / W gas | L2 / S brake | LS / AD steer | Tab camera | Hold Y / keyboard X exit")
                     : TEXT("BIKE | RT gas | LT brake / hold reverse | LS steer | RS look | B boost | Hold X exit"),
                 FLinearColor::White, 30, Canvas->ClipY - 50);
        return;
    }
    if (const auto *Bridge = Pilot->FindComponentByClass<UHoverLocomotionBridge>(); Bridge && Pilot->IsOnFoot())
        DrawText(Bridge->bEnabled ? TEXT("CLS motion + Parkour | D-pad Right / F7: compare")
                                  : TEXT("Original motion + Parkour | D-pad Right / F7: compare"),
                 FLinearColor(.7f, .85f, 1.f), 24, 60);
    const float X = Canvas->ClipX * .5f, Y = Canvas->ClipY * .5f;
    if (Pilot->IsAiming())
        DrawRect(FLinearColor(1.f, .08f, .025f), X - 1.5f, Y - 1.5f, 3.f, 3.f);
    else
    {
        DrawLine(X - 5, Y, X + 5, Y, FLinearColor::White);
        DrawLine(X, Y - 5, X, Y + 5, FLinearColor::White);
    }
    DrawRect(FLinearColor(0, 0, 0, .65f), 18, Canvas->ClipY - 108, FMath::Min(Canvas->ClipX - 36, 850.f), 90);
    DrawText(Pilot->GetPrompt(), FLinearColor::White, 32, Canvas->ClipY - 96, nullptr, 1.1f);
    DrawText(Pilot->IsMounted() ? TEXT("R2 / E thrust   LS / WASD steer + pitch   RS look   L2 aim   R1 / LMB fire")
                                : TEXT("LS / WASD move   RS / mouse aim   L2 / RMB aim gun   R2 / LMB fire"),
             FLinearColor(.8f, .85f, .9f), 32, Canvas->ClipY - 69);
    const FString MovementHelp =
        Pilot->IsMounted()
            ? FString::Printf(TEXT("A / Space hop   L3 / Shift boost   B / Ctrl coast   F5 view   %.0f m/s"),
                              Pilot->GetSpeedMps())
            : FString::Printf(
                  TEXT("A / Space jump   Hold L3 run   Tap B crouch/stand, hold prone   F5 view   %.0f m/s"),
                  Pilot->GetSpeedMps());
    DrawText(MovementHelp, FLinearColor(.8f, .85f, .9f), 32, Canvas->ClipY - 44);
    if (Pilot->HoldProgress() > 0 && Pilot->HoldProgress() < 1)
        DrawRect(FLinearColor(.9f, .1f, .08f), X - 70, Y + 35, 140 * Pilot->HoldProgress(), 5);
    if (Pilot->IsMounted())
    {
        DrawText(TEXT("BOOST"), FLinearColor::White, 28, Canvas->ClipY - 148);
        DrawRect(FLinearColor(.08f, .1f, .13f, .9f), 88, Canvas->ClipY - 141, 220, 12);
        DrawRect(FLinearColor(.2f, .7f, 1.f), 88, Canvas->ClipY - 141, 220 * Pilot->GetBoostCharge(), 12);
    }
    if (Pilot->Combat)
        if (const auto *Weapon = Pilot->Combat->GetWeapon())
        {
            const FString Ammo =
                FString::Printf(TEXT("%d / %d%s"), Weapon->GetCurrentClipAmmo(), Weapon->GetReserveAmmo(),
                                Weapon->IsReloading()               ? TEXT("  RELOADING")
                                : Weapon->GetCurrentClipAmmo() == 0 ? TEXT("  EMPTY - tap X / R")
                                                                    : TEXT(""));
            DrawText(Ammo, FLinearColor::White, Canvas->ClipX - 285, Canvas->ClipY - 185, nullptr, 1.4f);
            DrawText(TEXT("Tap X / R reload | R3 / V melee | D-pad Down / Tab inventory"), FLinearColor(.8f, .85f, .9f),
                     32, Canvas->ClipY - 120);
        }
}

AHoverGameMode::AHoverGameMode()
{
    DefaultPawnClass =
        LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Parkour/BP_AFS_ParkourPilot.BP_AFS_ParkourPilot_C"));
    if (!DefaultPawnClass)
        DefaultPawnClass = AHoverPilot::StaticClass();
    HUDClass = AHoverHUD::StaticClass();
    PlayerControllerClass = AHoverTestController::StaticClass();
}
void AHoverGameMode::BeginPlay()
{
    Super::BeginPlay();
    const auto *Defaults =
        LoadObject<UHoverPilotAssets>(nullptr, TEXT("/Game/HoverPrototype/DA_HoverPilot.DA_HoverPilot"));
    if (Defaults && Defaults->bBalancedTestLighting && GetWorld()->GetMapName().EndsWith(TEXT("PostApo")))
    {
        // Local runtime treatment; the purchased map and its authored light actors remain intact.
        for (TActorIterator<APostProcessVolume> It(GetWorld()); It; ++It)
        {
            auto &Settings = It->Settings;
            Settings.bOverride_AutoExposureBias = true;
            Settings.AutoExposureBias = Defaults->TestExposureBias;
            // The source map fixes min=max, leaving shaded streets unexposed.
            // Allow bounded adaptation while retaining the daylight ceiling.
            Settings.bOverride_AutoExposureMinBrightness = true;
            Settings.AutoExposureMinBrightness = -1.5f;
            Settings.bOverride_AutoExposureMaxBrightness = true;
            Settings.AutoExposureMaxBrightness = 1.f;
            Settings.bOverride_AutoExposureSpeedUp = true;
            Settings.AutoExposureSpeedUp = 2.f;
            Settings.bOverride_AutoExposureSpeedDown = true;
            Settings.AutoExposureSpeedDown = 1.f;
            Settings.bOverride_LocalExposureShadowContrastScale = true;
            Settings.LocalExposureShadowContrastScale = .75f;
            Settings.bOverride_LocalExposureHighlightContrastScale = true;
            Settings.LocalExposureHighlightContrastScale = .8f;
            Settings.bOverride_BloomIntensity = true;
            Settings.BloomIntensity = Defaults->TestBloomIntensity;
            Settings.bOverride_FilmGrainIntensity = true;
            Settings.FilmGrainIntensity = 0;
            Settings.bOverride_MotionBlurAmount = true;
            Settings.MotionBlurAmount = .15f;
            Settings.bOverride_LumenFinalGatherQuality = true;
            Settings.LumenFinalGatherQuality = FMath::Max(Settings.LumenFinalGatherQuality, 2.f);
        }
        for (TActorIterator<ADirectionalLight> It(GetWorld()); It; ++It)
        {
            It->GetLightComponent()->SetIndirectLightingIntensity(1.f);
            It->GetLightComponent()->SetVolumetricScatteringIntensity(1.f);
        }
        UE_LOG(LogTemp, Display, TEXT("HOVER_LIGHTING exposure=%.2f bloom=%.2f indirect=1 grain=0"),
               Defaults->TestExposureBias, Defaults->TestBloomIntensity);
    }
#if WITH_EDITOR
    if (FParse::Param(FCommandLine::Get(), TEXT("AFSReviewNoVehicles")))
        return;
#endif
    GetWorld()->SpawnActor<AHoverZombieRange>();
}

void AHoverGameMode::InitGame(const FString &MapName, const FString &Options, FString &ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);
    // Resolve after module startup, avoiding a native CDO's early asset-load fallback.
    if (auto *Parkour =
            LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Parkour/BP_AFS_ParkourPilot.BP_AFS_ParkourPilot_C")))
        DefaultPawnClass = Parkour;
    if (auto *Hybrid =
            LoadClass<APawn>(nullptr, TEXT("/Game/HoverPrototype/Hybrid/BP_Vexa_CLS_Parkour.BP_Vexa_CLS_Parkour_C")))
        DefaultPawnClass = Hybrid;
}
