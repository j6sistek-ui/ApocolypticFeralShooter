#include "HoverPilot.h"
#include "HoverCyberCity.h"
#include "HoverNYCSurvival.h"
#include "HoverCombatBridge.h"
#include "HoverLocomotionBridge.h"
#include "HoverTestController.h"
#include "HoverAnimInstance.h"
#include "HoverZombie.h"
#include "HoverShotVisual.h"
#include "HoverGunFeel.h"
#include "HoverEffects.h"
#include "HoverMotion.h"
#include "HoverMovementComponent.h"
#include "HLRawMovementComponent.h"
#include "Settings/ZE_PlayerSettings.h"
#include "Inventory/ZE_WeaponDefinition.h"
#include "Weapons/ZE_Projectile.h"
#include "Components/SphereComponent.h"
#include "GameFramework/ProjectileMovementComponent.h"
#include "Interaction/ZE_PickupBase.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/ConfigCacheIni.h"
#include "Survival/ZE_SurvivalComponent.h"
#include "Survival/ZE_WaveGameModeSettings.h"
#include "Zombies/ZE_ZombieCharacter.h"
#include "Zombies/ZE_ZombieSettings.h"
#include "Perception/AISense_Hearing.h"
#include "EngineUtils.h"

#include "Animation/AnimSequence.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/PoseableMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/PointLightComponent.h"
#include "GameFramework/ForceFeedbackEffect.h"
#include "Sound/SoundBase.h"
#include "Components/AudioComponent.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "NiagaraFunctionLibrary.h"
#include "Particles/ParticleSystem.h"
#include "Particles/ParticleSystemComponent.h"
#include "TimerManager.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkeletalMeshSocket.h"
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
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "UObject/UnrealType.h"

namespace
{
float Stick(float Value)
{
    return FMath::Abs(Value) < .16f ? 0.f : FMath::Sign(Value) * (FMath::Abs(Value) - .16f) / .84f;
}

FHitResult TraceWeaponRay(UWorld *World, const FVector &Start, const FVector &End, FCollisionQueryParams Params)
{
    FHitResult Hit;
    // Loot retains Visibility for interaction, but must not become bullet cover
    // or pull the muzzle's aim point away from the target behind it.
    while (World->LineTraceSingleByChannel(Hit, Start, End, ECC_Visibility, Params))
    {
        AActor *Actor = Hit.GetActor();
        if (!Actor || (!Actor->IsA<AZE_PickupBase>() && !Actor->IsA<AZE_PowerUpPickup>()))
            break;
        Params.AddIgnoredActor(Actor);
        Hit = FHitResult();
    }
    return Hit;
}

// Component-space reference-pose transform of a socket (or, failing that, a bone) on a skeletal mesh.
// Walks the reference skeleton directly so the offsets can be derived at BeginPlay, before the gun
// component has ticked a pose.
bool ResolveGunSocket(const USkeletalMesh *Mesh, FName Name, FTransform &Out)
{
    if (!Mesh || Name.IsNone())
        return false;
    const FReferenceSkeleton &Ref = Mesh->GetRefSkeleton();
    const auto ComponentSpace = [&Ref](int32 Bone) {
        FTransform Result = FTransform::Identity;
        for (; Bone != INDEX_NONE; Bone = Ref.GetParentIndex(Bone))
            Result = Result * Ref.GetRefBonePose()[Bone];
        return Result;
    };
    if (const USkeletalMeshSocket *Socket = Mesh->FindSocket(Name))
    {
        const int32 Bone = Ref.FindBoneIndex(Socket->BoneName);
        if (Bone == INDEX_NONE)
            return false;
        Out = Socket->GetSocketLocalTransform() * ComponentSpace(Bone);
        return true;
    }
    const int32 Bone = Ref.FindBoneIndex(Name);
    if (Bone == INDEX_NONE)
        return false;
    Out = ComponentSpace(Bone);
    return true;
}

bool IsGunFeelZombie(const AActor *Actor)
{
    return Cast<AHoverZombie>(Actor) || Cast<AZE_ZombieCharacter>(Actor);
}

bool IsGunFeelCorpse(const AActor *Actor)
{
    if (const auto *Simple = Cast<AHoverZombie>(Actor))
        return Simple->IsDead();
    const auto *Zombie = Cast<AZE_ZombieCharacter>(Actor);
    if (!Zombie)
        return false;
    // The vendor death flag is protected; read the reflected property instead of patching the plugin.
    if (const auto *Dead = FindFProperty<FBoolProperty>(AZE_ZombieCharacter::StaticClass(), TEXT("bIsDead")))
        return Dead->GetPropertyValue_InContainer(Zombie);
    return Zombie->SurvivalComponent && Zombie->SurvivalComponent->GetHealth() <= 0;
}

bool IsGunFeelHeadshot(const AActor *Actor, const FHitResult &Hit)
{
    if (Cast<AHoverZombie>(Actor))
        return Hit.BoneName.ToString().Contains(TEXT("head")); // Same rule as AHoverZombie::TakeDamage.
    const auto *Zombie = Cast<AZE_ZombieCharacter>(Actor);
    return Zombie && Zombie->ZombieData && Hit.BoneName == Zombie->ZombieData->Stats.HeadBoneName;
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
    ViewArms = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPSArms"));
    ViewArms->SetupAttachment(FirstPersonCamera);
    ViewArms->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ViewArms->SetGenerateOverlapEvents(false);
    ViewArms->SetOnlyOwnerSee(true);
    ViewArms->CastShadow = false;
    // This arms-only mesh has no physics asset to expand its animated bounds.
    // The FPS reach extends beyond its imported A-pose bounds near the camera.
    ViewArms->BoundsScale = 3.f;
    ViewArms->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    WorldGun = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("HeldGun"));
    // The hand supplies position; its animated rotation must not rotate the aim twice.
    WorldGun->SetupAttachment(GetRootComponent());
    WorldGun->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    // Rigged rifle pair: same rules as the static pair, hidden until ApplyGunRig gives it a mesh
    // so the Ballista path renders nothing from it.
    ViewGunSkel = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("FPSGunRig"));
    ViewGunSkel->SetupAttachment(FirstPersonCamera);
    ViewGunSkel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ViewGunSkel->SetGenerateOverlapEvents(false);
    ViewGunSkel->CastShadow = false;
    ViewGunSkel->SetOnlyOwnerSee(true);
    ViewGunSkel->SetVisibility(false, true);
    WorldGunSkel = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("HeldGunRig"));
    WorldGunSkel->SetupAttachment(GetRootComponent());
    WorldGunSkel->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WorldGunSkel->SetGenerateOverlapEvents(false);
    WorldGunSkel->SetVisibility(false, true);
}

void AHoverPilot::BeginPlay()
{
    Super::BeginPlay();
    GetMesh()->AddTickPrerequisiteActor(this);
    SetCanBeDamaged(true); // Hit reactions remain active while invincible.
    GConfig->GetBool(TEXT("AFS.Graphics"), TEXT("Invincible"), bInvincible, GGameUserSettingsIni);
    const auto *Policy = IHoverTestLevelPolicy::Get(GetWorld());
    if (Policy && Policy->ForcesMortal())
    {
        bMortalLocked = true;
        bInvincible = false;
    }
    bSurvivalRules = Policy && Policy->UsesSurvivalRules();
    bSandboxResetAllowed = !Policy || Policy->AllowsSandboxReset();
    StartLocation = GetActorLocation();
    StartRotation = GetActorRotation();
    BodyYaw = StartRotation.Yaw;
    Assets = LoadObject<UHoverPilotAssets>(nullptr, TEXT("/Game/HoverPrototype/DA_HoverPilot.DA_HoverPilot"));
    if (Assets)
    {
        // DA values first; ApplyGunRig overwrites them from the rig's sockets when asked to.
        GunMuzzle = Assets->GunMuzzle;
        GunForward = Assets->GunForward;
        GunGrip = Assets->GunGrip;
        GunSupportGrip = Assets->GunSupportGrip;
        GunSight = Assets->GunSight;
    }
    if (!Assets || !Assets->Glider || Assets->BodyParts.IsEmpty())
    {
        StatusMessage = TEXT("Prototype assets missing - run the asset setup script.");
        UE_LOG(LogTemp, Error, TEXT("HOVER: required prototype assets missing"));
        return;
    }
    // Section 5 gun feel is opt-in; without it every mode keeps the existing presentation.
    bool EnhancedFeel = false;
    GConfig->GetBool(TEXT("AFS.Gunplay"), TEXT("EnhancedFeel"), EnhancedFeel, GGameUserSettingsIni);
    bEnhancedGunFeel = bEnhancedGunFeel || EnhancedFeel || FParse::Param(FCommandLine::Get(), TEXT("AFSGunFeel")) ||
                       (Policy && Policy->EnablesEnhancedGunFeel());
    if (bEnhancedGunFeel)
    {
        float ShakePercent = 100, RecoilPercent = 100, RumblePercent = 100;
        GConfig->GetFloat(TEXT("AFS.Gunplay"), TEXT("ShakeScale"), ShakePercent, GGameUserSettingsIni);
        GConfig->GetFloat(TEXT("AFS.Gunplay"), TEXT("RecoilScale"), RecoilPercent, GGameUserSettingsIni);
        GConfig->GetFloat(TEXT("AFS.Gunplay"), TEXT("RumbleScale"), RumblePercent, GGameUserSettingsIni);
        ShakeSetting = FMath::Clamp(ShakePercent, 0.f, 100.f) / 100.f;
        RecoilSetting = FMath::Clamp(RecoilPercent, 0.f, 100.f) / 100.f;
        if (auto *PC = Cast<APlayerController>(GetController()))
            // From the class default, so a respawned pilot never compounds the scale.
            PC->ForceFeedbackScale = GetDefault<APlayerController>(PC->GetClass())->ForceFeedbackScale *
                                     FMath::Clamp(RumblePercent, 0.f, 100.f) / 100.f;
        EnsureMuzzleLight();
        UE_LOG(LogTemp, Display, TEXT("HOVER_GUNFEEL enabled shake=%.2f recoil=%.2f rumble=%.2f feel=%s"), ShakeSetting,
               RecoilSetting, RumblePercent / 100.f, *GetNameSafe(GetGunFeel()));
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
    ViewArms->SetSkeletalMesh(LoadObject<USkeletalMesh>(
        nullptr, TEXT("/Game/HoverPrototype/Weapons/FirstPerson/SK_Vexa_FPSArms.SK_Vexa_FPSArms")));
    ViewArms->SetAnimInstanceClass(UHoverViewAnimInstance::StaticClass());
    ViewArms->AddTickPrerequisiteActor(this);
    ViewArms->SetDisablePostProcessBlueprint(true);
    ViewPoseHandle = ViewArms->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &AHoverPilot::FinalizeViewPose));
    GunPoseHandles[0] = ViewGunSkel->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &AHoverPilot::FinalizeGunPose,
                                                                        ViewGunSkel.Get()));
    GunPoseHandles[1] = WorldGunSkel->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &AHoverPilot::FinalizeGunPose,
                                                                        WorldGunSkel.Get()));
    if (Assets->RiggedGun)
    {
        // The loose Weapon|Rigged fields are the default rig: every definition GunRigs has no key for.
        DefaultGunRig = NewObject<UHoverGunRig>(this, TEXT("DefaultGunRig"), RF_Transient);
        DefaultGunRig->Mesh = Assets->RiggedGun;
        DefaultGunRig->Idle = Assets->GunIdle;
        DefaultGunRig->Fire = Assets->GunFire;
        DefaultGunRig->DryFire = Assets->GunDryFire;
        DefaultGunRig->Reload = Assets->GunReload;
        DefaultGunRig->Chamber = Assets->GunChamber;
        DefaultGunRig->MuzzleSocket = Assets->GunMuzzleSocket;
        DefaultGunRig->EjectSocket = Assets->GunEjectSocket;
        DefaultGunRig->SightSocket = Assets->GunSightSocket;
        DefaultGunRig->GripSocket = Assets->GunGripSocket;
        DefaultGunRig->SupportSocket = Assets->GunSupportSocket;
        DefaultGunRig->bSocketsDriveOffsets = Assets->bRiggedGunSocketsDriveOffsets;
        DefaultGunRig->Description = TEXT("DA_HoverPilot Weapon|Rigged fields");
    }
    // Null keeps the static Ballista. The rifle's OnEquipped re-applies per held definition.
    ApplyGunRig(DefaultGunRig);
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
        // Paired lift/down jets, side jets and two forward-facing braking jets.
        // Same purchased emitter; each nozzle is driven independently below.
        const FVector Nozzles[] = {FVector(-42, 0, -5), FVector(42, 0, -5), FVector(-42, 0, 5),  FVector(42, 0, 5),
                                   FVector(-72, 0, 0),  FVector(72, 0, 0),  FVector(-40, 22, 0), FVector(40, 22, 0)};
        for (const FVector &Nozzle : Nozzles)
        {
            auto *Effect = NewObject<UNiagaraComponent>(BoardActor);
            Effect->SetupAttachment(Board);
            Effect->SetAutoActivate(false);
            Effect->SetAsset(Assets->BoosterEffect);
            Effect->SetRelativeLocation(Nozzle);
            Effect->RegisterComponent();
            DirectionalBoosters.Add(Effect);
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
    // Life Engine rides along only under NYC Survival rules (owner 2026-10-31: "load Life Engine, but ONLY in the
    // survival mode in NYC, so I can switch out and recheck the locomotion in the other version"). The solver never
    // polls input itself here: UpdateLifeEngine feeds the pilot's sampled sticks and keys and the resolved walk /
    // sprint speed every tick, and it ticks after this actor so the feed is fresh.
    if (bSurvivalRules)
    {
        LifeMovement = NewObject<UHLRawMovementComponent>(this, TEXT("LifeEngine"));
        LifeMovement->bAutoActivate = false;
        LifeMovement->PrimaryComponentTick.bStartWithTickEnabled = false;
        LifeMovement->bAutoLoadMovementSettings = false;
        // AFS 2026-11-01 (walking): a movement component asks by default to tick BEFORE its owner (bTickBeforeOwner),
        // while the solver must tick AFTER the pilot (AddTickPrerequisiteActor below), so the two edges formed a
        // cycle: the owner's NYC session logged 2583 + 984 "would form a cycle" warnings and the engine dropped a
        // different edge from frame to frame. One order only: pilot (input feed) -> solver -> mesh.
        LifeMovement->bTickBeforeOwner = false;
        LifeMovement->RegisterComponent();
        PrimaryActorTick.RemovePrerequisite(LifeMovement, LifeMovement->PrimaryComponentTick);
        LifeMovement->SetUpdatedComponent(GetCapsuleComponent());
        LifeMovement->bEnableKeyboardMovement = false;
        LifeMovement->bEnableJumpInput = false;
        LifeMovement->bEnableMouseLook = false;
        LifeMovement->bEnableCrouch = false;
        LifeMovement->bEnableDebugDraw = false;
        LifeMovement->bEnableStepUp = true;
        LifeMovement->StepHeight = LifeMovement->MaxStepUpDelta = GetCharacterMovement()->MaxStepHeight;
        // Step over anything that is not walkable floor, as the character movement does; the solver's default only
        // steps near-vertical faces (normal z < 0.15) and sloped rubble between that and 46 deg trapped her.
        LifeMovement->StepWallNormalZLimit = 0.68f;
        LifeMovement->AddTickPrerequisiteActor(this);
        GetMesh()->AddTickPrerequisiteComponent(LifeMovement);
        LifeMovement->OnLanded.AddDynamic(this, &AHoverPilot::OnLifeEngineLanded);
        bLifeEngine = true;
        UE_LOG(LogTemp, Display, TEXT("LIFE_ENGINE created for NYC Survival (preset %d), on by default"),
               int32(LifeMovement->MovementPreset));
    }
    // AFS 2026-10-31 visual pass: the survival fill light on Vexa (lighting channel 1 only), NYC Survival only.
    if (bSurvivalRules)
        SetupFillLight();
    if (Policy && Policy->ForcesThirdPerson())
    {
        bReview = true;
        bForcedThirdPerson = true;
        // Section 2 Â§4 OTS camera: 300 / 210 cm arm, (0, 58, 42) offset, 88 / 68 FOV. Owner 2026-10-31: "the
        // camera needs to stay at a fixed distance, except zooming or maybe sprinting", so the positional lag
        // (up to 60 cm of trailing) is off; the arm only changes for the aim zoom and a sprint stretch.
        // bDoCollisionTest stays on: zombie capsules and meshes ignore ECC_Camera.
        ReviewArm->TargetArmLength = Assets->SurvivalArmLength;
        ReviewArm->SocketOffset = Assets->SurvivalSocketOffset;
        ReviewArm->bEnableCameraLag = false;
        ReviewArm->bEnableCameraRotationLag = false;
        ReviewCamera->SetFieldOfView(Assets->SurvivalHipFOV);
        // Spring-arm collision can pin the camera against Vexa; UpdateCameraBodyHide then hides her
        // from her own view (bOwnerNoSee), and her ground shadow must stay while she is hidden.
        for (USkeletalMeshComponent *Part : Parts)
            Part->SetCastHiddenShadow(true);
    }
    SetView();
    WeaponPoseHandle = GetMesh()->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateUObject(this, &AHoverPilot::UpdateGunTransform));
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
    GetMesh()->UnregisterOnBoneTransformsFinalizedDelegate(WeaponPoseHandle);
    ViewArms->UnregisterOnBoneTransformsFinalizedDelegate(ViewPoseHandle);
    ViewGunSkel->UnregisterOnBoneTransformsFinalizedDelegate(GunPoseHandles[0]);
    WorldGunSkel->UnregisterOnBoneTransformsFinalizedDelegate(GunPoseHandles[1]);
    GetWorldTimerManager().ClearTimer(GunClipTimer);
    GetWorldTimerManager().ClearTimer(GunReloadEjectTimer);
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
    {
        UE_LOG(LogTemp, Display, TEXT("HOVER_MELEE rejected foot=%d weapon=%d knocked=%d defeated=%d"), IsOnFoot(),
               MeleeWeapon != nullptr, IsKnockedDown(), IsDefeated());
        return;
    }
    if (Combat)
        Combat->Melee();
    else
    {
        MeleeWeapon->StartFire();
        MeleeWeapon->StopFire();
    }
    UE_LOG(LogTemp, Display, TEXT("HOVER_MELEE R3/V swing=%d"), MeleeWeapon->IsSwinging());
    if (MeleeWeapon->IsSwinging())
    {
        StatusMessage = TEXT("Katana strike");
        StatusTime = 1.f;
    }
}

void AHoverPilot::ToggleMeleeWeapon()
{
    if (!IsOnFoot() || !MeleeWeapon || IsKnockedDown() || IsDefeated() || (Combat && Combat->IsInventoryOpen()))
        return;
    if (Combat)
    {
        Combat->SetTrigger(false);
        if (auto *Rifle = Cast<AHoverCyberRifle>(Combat->GetWeapon()))
            Rifle->CancelReload();
    }
    MeleeWeapon->CancelSwing();
    if (bSpearHeld)
    {
        // AFS 2026-10-31 (spear item): the spear slot owns the melee flag; Y / G or a number key leaves it.
        StatusMessage = TEXT("Spear in hand | Y: next weapon");
        StatusTime = 2.f;
        return;
    }
    bMeleeEquipped = !bMeleeEquipped;
    GunRecoil = GunRecoilVelocity = 0;
    bSuppressFireUntilRelease = true;
    bAiming = false;
    GunRaisedTime = 0;
    StatusMessage = bMeleeEquipped ? TEXT("Katana equipped | R2: swing | Hold R3: gun") : TEXT("Gun equipped");
    StatusTime = 2.f;
    SetView();
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
    bMeleeEquipped = false;
    bSuppressFireUntilRelease = true;
    GunRecoil = GunRecoilVelocity = 0;
    GroundSlideTime = 0;
    bGroundCrouchHeld = false;
    UnCrouch();
    GetCharacterMovement()->UnCrouch(false);
    if (bIsCrouched)
        return false;
    bProne = bDiving = false;
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
        FlightEffectAcceleration = FVector::ZeroVector;
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
    // Survival only forces the DEFAULT view (BeginPlay sets bReview with the OTS arm); the design keeps
    // F5 / Menu as a toggle to first person (NYC_ZOMBIE_SURVIVAL_DESIGN "F5/Menu toggles to first person").
    // The old early return here left the key dead in game, so the editor viewport ate it instead
    // (owner 2026-10-30: "it was supposed to toggle first person and 3rd person").
    bReview = !bReview;
    StatusMessage = bReview ? TEXT("Third person") : TEXT("First person");
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
    const bool Swinging = bMeleeEquipped || (MeleeWeapon && MeleeWeapon->IsSwinging());
    ActiveGunPrimitive(false)->SetVisibility(!Swinging && FirstPerson, true);
    ViewArms->SetVisibility(FirstPerson);
    ActiveGunPrimitive(true)->SetVisibility(!Swinging && !FirstPerson && (bAiming || GunRaisedTime > 0), true);
    // The full-body riding pose crosses the eye camera during pitch and recoil.
    // Keep it for the external view; the FPS camera renders its own rifle.
    // A third-person camera pinned inside her (UpdateCameraBodyHide) keeps the body hidden.
    if (FirstPerson && bCameraHidesBody)
        ApplyCameraBodyHide(false);
    for (USkeletalMeshComponent *Part : Parts)
        Part->SetOwnerNoSee(FirstPerson || bCameraHidesBody);
}

void AHoverPilot::ApplyCameraBodyHide(bool bHide)
{
    bCameraHidesBody = bHide;
    for (USkeletalMeshComponent *Part : Parts)
    {
        // Forced third person keeps hidden shadows on permanently (BeginPlay); other review modes
        // keep the shadow only while hidden, so their first-person view is unchanged.
        if (!bForcedThirdPerson)
            Part->SetCastHiddenShadow(bHide);
        Part->SetOwnerNoSee(bHide || !bReview);
    }
    // The rifle and its optic sit in the same frame. Owner-only: its SetVisibility logic is untouched.
    UPrimitiveComponent *HeldGun = ActiveGunPrimitive(true);
    HeldGun->SetOwnerNoSee(bHide);
    for (USceneComponent *Child : HeldGun->GetAttachChildren())
        if (auto *Primitive = Cast<UPrimitiveComponent>(Child))
            Primitive->SetOwnerNoSee(bHide);
}

void AHoverPilot::UpdateCameraBodyHide()
{
    if (!bReview || !Assets)
    {
        if (bCameraHidesBody)
            ApplyCameraBodyHide(false);
        return;
    }
    // Camera-to-capsule-centre distance: the spring arm's collision probe (bDoCollisionTest) can
    // collapse the 300 cm arm to near zero when zombies push her into the truck, filling the frame
    // with her own mesh. Hysteresis keeps a jostled camera from flickering her in and out.
    const float CamDist = FVector::Dist(ReviewCamera->GetComponentLocation(), GetActorLocation());
    const float HideDistance = Assets->SurvivalMeshHideDistance;
    const bool bHide = CamDist < (bCameraHidesBody ? HideDistance + 15.f : HideDistance);
    if (bHide == bCameraHidesBody)
        return;
    ApplyCameraBodyHide(bHide);
    ++CameraBodyHideCount;
    const float Now = GetWorld()->GetTimeSeconds();
    if (Now - LastCameraHideLog >= .5f)
    {
        LastCameraHideLog = Now;
        UE_LOG(LogTemp, Display, TEXT("HOVER_CAM_HIDE %s dist=%.0f threshold=%.0f arm=%.0f count=%d"),
               bHide ? TEXT("hide") : TEXT("show"), CamDist, HideDistance, ReviewArm->TargetArmLength,
               CameraBodyHideCount);
    }
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
    GunRecoil = GunRecoilVelocity = 0;
    bMeleeEquipped = false;
    bSuppressFireUntilRelease = true;
    bDiving = bProne = false;
    GroundSlideTime = 0;
    CancelPostureInput();
    bDefeated = false;
    if (DefeatedController.IsValid())
        DefeatedController->SetIgnoreMoveInput(false);
    DefeatedController.Reset();
    SandboxHealth = GetMaxHealth();
    if (Combat && Combat->Survival)
        Combat->Survival->SetHealth(SandboxHealth);
    RespawnGraceUntil = GetWorld()->GetTimeSeconds() + 2.f;
    if (LocomotionBridge)
        LocomotionBridge->CancelAction();
    if (LifeMovement)
        LifeMovement->SetHLVelocity(FVector::ZeroVector);
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
    UE_LOG(LogTemp, Display, TEXT("HOVER_STATE mounted=%d aim=%d pos=%s velocity=%s targetZ=%.1f lifeEngine=%d/%d"),
           bMounted, bAiming, *GetActorLocation().ToString(), *GetVelocity().ToString(), TargetAltitude, bLifeEngine,
           bLifeEngineActive);
}

void AHoverPilot::LifeEngine(int32 Mode)
{
    if (!LifeMovement)
    {
        if (GEngine)
            GEngine->AddOnScreenDebugMessage(-1, 4.f, FColor::Orange, TEXT("Life Engine lives only in NYC Survival"));
        return;
    }
    bLifeEngine = Mode < 0 ? !bLifeEngine : Mode != 0;
    UpdateLifeEngine(0.f);
    if (GEngine)
        GEngine->AddOnScreenDebugMessage(-1, 4.f, bLifeEngine ? FColor::Green : FColor::Yellow,
                                         bLifeEngine ? TEXT("Life Engine ON (Source-style movement)")
                                                     : TEXT("Life Engine OFF (character movement)"));
    UE_LOG(LogTemp, Display, TEXT("LIFE_ENGINE %s"), bLifeEngine ? TEXT("on") : TEXT("off"));
}

void AHoverPilot::UpdateLifeEngine(float DT)
{
    if (!LifeMovement)
        return;
    auto *Move = GetCharacterMovement();
    // AFS 2026-10-31: the NYC pawn is the parkour template, so it cannot be excluded outright (the first proof
    // never activated). The template takes over only when it changes the movement mode (vault, wall run) or
    // plays a root-motion montage; the solver steps aside for that and resumes once she is back on the ground.
    const auto *Anim = GetMesh() ? GetMesh()->GetAnimInstance() : nullptr;
    const bool RootMotion = Anim && Anim->GetRootMotionMontageInstance() != nullptr;
    // AFS 2026-10-31 (Life Engine x parkour): the template also engages without a mode change of its own. Its
    // wall run raises its IsWallRunning flag and rewrites GravityScale (which only the character movement reads),
    // and a slide or crouch needs the character movement's capsule resize; each of those hands the capsule over
    // too. UHoverMovementComponent reports the solver's ground state, so the template's IsFalling wall-run check
    // fires mid-jump, and its Launch override hands over on a wall jump. Landing gives the capsule back.
    // The template variable is "IsWallRunning?" (with the question mark; checked in the asset's name table).
    static const TCHAR *const WallRunFlags[] = {TEXT("IsWallRunning?"), TEXT("IsWallRunning"), TEXT("Is Wall Running")};
    bool WallRunning = false;
    for (const TCHAR *Name : WallRunFlags)
        if (const auto *Flag = FindFProperty<FBoolProperty>(GetClass(), Name))
        {
            WallRunning = Flag->GetPropertyValue_InContainer(this);
            break;
        }
    if (WallRunning != bTemplateWallRunWas)
    {
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_PARKOUR_WALLRUN %s solver=%d mode=%d z=%.1f vz=%.1f"),
               WallRunning ? TEXT("start") : TEXT("end"), bLifeEngineActive, int32(Move->MovementMode.GetValue()),
               GetActorLocation().Z, GetVelocity().Z);
        bTemplateWallRunWas = WallRunning;
    }
    // AFS 2026-10-31 guard: after a hand-off the template's wall-run flag must not outlive the landing. If the
    // character movement has walked on the ground for 0.25 s with the flag (and its 0.25 gravity) still set, the
    // template will not clear it (it only re-evaluates while falling), so clear it here and restore the baseline
    // gravity; the solver then resumes as on any landing.
    if (bLifeEngineTemplateOverride && WallRunning && Move->MovementMode == MOVE_Walking && Move->IsMovingOnGround())
    {
        TemplateWallRunGroundTime += DT;
        if (TemplateWallRunGroundTime >= .25f)
        {
            for (const TCHAR *Name : WallRunFlags)
                if (const auto *Flag = FindFProperty<FBoolProperty>(GetClass(), Name))
                {
                    Flag->SetPropertyValue_InContainer(this, false);
                    break;
                }
            UE_LOG(LogTemp, Verbose, TEXT("HOVER_PARKOUR_WALLRUN_CLEAR grounded=%.2fs gravity=%.2f->%.2f"),
                   TemplateWallRunGroundTime, Move->GravityScale, LifeEngineGravityScale);
            Move->GravityScale = LifeEngineGravityScale;
            WallRunning = false;
            bTemplateWallRunWas = false;
            TemplateWallRunGroundTime = 0.f;
        }
    }
    else
        TemplateWallRunGroundTime = 0.f;
    const bool Crouching = Move->bWantsToCrouch || bIsCrouched;
    const bool GravityChanged =
        bLifeEngineActive && !FMath::IsNearlyEqual(Move->GravityScale, LifeEngineGravityScale);
    const bool WasOverride = bLifeEngineTemplateOverride;
    if (bLifeEngineActive &&
        (Move->MovementMode != MOVE_None || RootMotion || WallRunning || GravityChanged || Crouching))
        bLifeEngineTemplateOverride = true;
    else if (bLifeEngineTemplateOverride && Move->IsMovingOnGround() && !RootMotion && !WallRunning && !Crouching)
        bLifeEngineTemplateOverride = false;
    // AFS 2026-11-01 (walking): at Display, so a player session log names the reason for every hand-off (the
    // owner's NYC run showed 20 suspend / resume switches in 90 s with no reason in the log).
    if (bLifeEngineTemplateOverride != WasOverride)
        UE_LOG(LogTemp, Display,
               TEXT("HOVER_PARKOUR_%s mode=%d rootmotion=%d (%s) wallrun=%d gravity=%.2f (base %.2f) crouch=%d "
                    "solver_ground=%d z=%.1f v=%s"),
               bLifeEngineTemplateOverride ? TEXT("YIELD") : TEXT("RESUME"), int32(Move->MovementMode.GetValue()),
               RootMotion, RootMotion ? *GetNameSafe(Anim->GetRootMotionMontageInstance()->Montage) : TEXT("-"),
               WallRunning, Move->GravityScale, LifeEngineGravityScale, Crouching, LifeMovement->bGrounded,
               GetActorLocation().Z, *GetVelocity().ToString());
    const bool Want = bLifeEngine && !bMounted && !bLifeEngineTemplateOverride && !bDefeated && !bKnockedDown &&
                      TransitionTime <= 0;
    if (Want != bLifeEngineActive)
    {
        bLifeEngineActive = Want;
        if (Want)
        {
            LifeMovement->SetHLVelocity(Move->Velocity);
            Move->StopMovementImmediately();
            // AFS 2026-10-31: seed the solver's ground flag and the template gravity baseline from the character
            // movement, so the first solver tick neither fires a false landing nor reports a frame of falling.
            LifeMovement->bGrounded = Move->IsMovingOnGround();
            LifeEngineGravityScale = Move->GravityScale;
            Move->SetMovementMode(MOVE_None);
            LifeMovement->Activate(true);
        }
        else
        {
            // AFS 2026-10-31: read the solver velocity before deactivating it; afterwards it reads zero, and a
            // wall-run hand-off at a sprint started the template's wall run from a standstill (680 -> 0 cm/s).
            const FVector HandVelocity = LifeMovement->GetHLVelocity();
            LifeMovement->Deactivate();
            // Leave a mode the template already chose alone; otherwise hand back walking or falling.
            // A wall-run hand-off (flag or gravity) always goes back through falling, even on the landing tick:
            // the template clears IsWallRunning? and restores its gravity only in OnLanded, which the engine
            // fires from a falling landing. Handing back walking there left the flag and GravityScale 0.25 stuck,
            // so the solver never resumed (ProveParkourLifeEngine run 1, 2026-10-31).
            if (Move->MovementMode == MOVE_None)
                Move->SetMovementMode(LifeMovement->bGrounded && !WallRunning && !GravityChanged ? MOVE_Walking
                                                                                                : MOVE_Falling);
            Move->Velocity = HandVelocity;
        }
        UE_LOG(LogTemp, Display, TEXT("LIFE_ENGINE %s%s"), Want ? TEXT("active") : TEXT("suspended"),
               bLifeEngineTemplateOverride ? TEXT(" (parkour template)") : TEXT(""));
    }
    // AFS 2026-10-31: truthful ground state for the template and every IsFalling / IsMovingOnGround reader while
    // the solver drives (UHoverMovementComponent applies it only in MOVE_None).
    if (auto *HoverMove = Cast<UHoverMovementComponent>(Move))
        HoverMove->SetExternalSolverState(bLifeEngineActive, LifeMovement->bGrounded);
    if (!bLifeEngineActive)
        return;
    // The pilot's own sampled input (sticks and keys alike) drives the solver; the speed target follows the
    // walk / sprint / crouch value UpdateInput already resolved on the character movement, the solver keeps its
    // own acceleration, friction, gravity and jump. Velocity is mirrored from the solver's last tick (it ticks
    // after this actor) so GetVelocity() stays truthful for the animation, aim and camera code.
    LifeMovement->InputForward = ForwardInput;
    LifeMovement->InputRight = SideInput;
    const auto *PC = Cast<APlayerController>(GetController());
    LifeMovement->bJumpHeld =
        PC && (PC->IsInputKeyDown(EKeys::Gamepad_FaceButton_Bottom) || PC->IsInputKeyDown(EKeys::SpaceBar));
    LifeMovement->MaxGroundSpeed = bIsCrouched ? Move->MaxWalkSpeedCrouched : Move->MaxWalkSpeed;
    Move->Velocity = LifeMovement->GetHLVelocity();
}

void AHoverPilot::OnLifeEngineLanded()
{
    // Same landing feel as the character movement path; the mirrored velocity still holds the fall speed.
    // AFS 2026-10-31 (parkour): report the landing to the character movement at once. The solver ticks after
    // the pilot, so the cached flag would otherwise say "falling" for one more template tick, on the ground,
    // and the template started a wall run beside the start barrier at landing height (ProveParkourLifeEngine).
    if (auto *HoverMove = Cast<UHoverMovementComponent>(GetCharacterMovement()))
        HoverMove->SetExternalSolverState(bLifeEngineActive, true);
    FHitResult Hit;
    Hit.ImpactNormal = LifeMovement ? LifeMovement->GroundNormal : FVector::UpVector;
    Hit.ImpactPoint = GetActorLocation() - FVector(0, 0, GetCapsuleComponent()->GetScaledCapsuleHalfHeight());
    Landed(Hit);
}

void AHoverPilot::SetupFillLight()
{
    // AFS 2026-10-31 visual pass (owner: "maybe the lighting on the player just a bit"). A soft, shadowless,
    // warm-neutral point light riding on the capsule behind her right shoulder, on the over-the-shoulder camera's
    // side (SurvivalArmLength 300 cm back along the control yaw, SurvivalSocketOffset 58 cm right / 42 cm up from
    // the capsule centre; the capsule yaw follows the control yaw on foot), so it lifts the side of her the
    // survival camera sees. It shines on lighting channel 1 only; Vexa's body parts, first-person arms and held
    // guns join channel 1 (keeping channel 0 for the level's lights), so zombies, props and the street never
    // receive it. No indirect or volumetric contribution: Lumen ignores lighting channels and would bounce it
    // onto the level. `HoverFillLight [0|1] [cd]` switches it in play for A/B.
    if (FillLight || !Assets)
        return;
    FillLight = NewObject<UPointLightComponent>(this, TEXT("SurvivalFillLight"));
    FillLight->SetupAttachment(GetRootComponent());
    FillLight->SetRelativeLocation(Assets->SurvivalFillLightOffset);
    FillLight->SetIntensityUnits(ELightUnits::Candelas);
    FillLight->SetIntensity(Assets->SurvivalFillLightIntensity);
    FillLight->SetAttenuationRadius(Assets->SurvivalFillLightRadius);
    FillLight->SetSourceRadius(Assets->SurvivalFillLightSourceRadius);
    FillLight->SetLightColor(Assets->SurvivalFillLightColor);
    FillLight->SetCastShadows(false);
    FillLight->SetSpecularScale(Assets->SurvivalFillLightSpecular);
    FillLight->SetIndirectLightingIntensity(0.f);
    FillLight->SetVolumetricScatteringIntensity(0.f);
    FillLight->SetAffectTranslucentLighting(false);
    FillLight->SetLightingChannels(false, true, false);
    FillLight->RegisterComponent();
    const auto JoinFillChannel = [](UPrimitiveComponent *Primitive) {
        if (Primitive)
            Primitive->SetLightingChannels(true, true, Primitive->LightingChannels.bChannel2);
    };
    for (USkeletalMeshComponent *Part : Parts)
        JoinFillChannel(Part);
    JoinFillChannel(ViewArms);
    JoinFillChannel(ViewGun);
    JoinFillChannel(WorldGun);
    JoinFillChannel(ViewGunSkel);
    JoinFillChannel(WorldGunSkel);
    bFillLightOn = Assets->SurvivalFillLightIntensity > 0.f;
    FillLight->SetVisibility(bFillLightOn);
    UE_LOG(LogTemp, Display, TEXT("HOVER_FILL_LIGHT created on=%d intensity=%.2f cd radius=%.0f offset=%s parts=%d"),
           bFillLightOn, FillLight->Intensity, FillLight->AttenuationRadius,
           *Assets->SurvivalFillLightOffset.ToString(), Parts.Num());
}

void AHoverPilot::HoverFillLight(int32 Mode, float Intensity)
{
    if (!FillLight && bSurvivalRules)
        SetupFillLight();
    if (!FillLight)
    {
        if (GEngine)
            GEngine->AddOnScreenDebugMessage(-1, 4.f, FColor::Orange, TEXT("The fill light lives only in NYC Survival"));
        return;
    }
    bFillLightOn = Mode < 0 ? !bFillLightOn : Mode != 0;
    if (Intensity >= 0.f)
        FillLight->SetIntensity(Intensity);
    FillLight->SetVisibility(bFillLightOn);
    if (GEngine)
        GEngine->AddOnScreenDebugMessage(-1, 3.f, FColor::Cyan,
                                         FString::Printf(TEXT("Fill light %s (%.1f cd)"),
                                                         bFillLightOn ? TEXT("ON") : TEXT("OFF"), FillLight->Intensity));
    UE_LOG(LogTemp, Display, TEXT("HOVER_FILL_LIGHT %s intensity=%.2f"), bFillLightOn ? TEXT("on") : TEXT("off"),
           FillLight->Intensity);
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
    if (RecoilPitchDebt > 0)
    {
        // Pulling down against the climb pays the debt, so auto-recovery never over-corrects.
        const float UserPitch = Look.Pitch - FRotator::NormalizeAxis(PC->GetControlRotation().Pitch);
        if (UserPitch < 0)
            RecoilPitchDebt = FMath::Max(0.f, RecoilPitchDebt + UserPitch);
    }
    PC->SetControlRotation(Look);
    RecoilTrackedPitch = Look.Pitch;
    bBoostHeld = Down(EKeys::Gamepad_LeftThumbstick) || Down(EKeys::LeftShift);
    if (!bMounted)
    {
        auto *Move = GetCharacterMovement();
        const bool Sprint = Down(EKeys::Gamepad_LeftThumbstick);
        // Promoted for the survival sprint-fire gate: a sprint is the held run with real stick input.
        const bool Sprinting = Sprint && !bIsCrouched && FVector2D(ForwardInput, SideInput).Size() > .6f;
        if (bSprinting && !Sprinting)
            SprintEndTime = GetWorld()->GetTimeSeconds();
        bSprinting = Sprinting;
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
    // NYC Survival keeps the glider (owner 2026-10-29: a future quick-escape / travel feature, maybe
    // timed or fuelled, outdoors only). There the ride moves to a held Y / G so a long press on the
    // reload button never mounts it mid-fight; every other level keeps hold-X mount, tap-X reload.
    const bool Hold = bSurvivalRules ? (Down(EKeys::Gamepad_FaceButton_Top) || Down(EKeys::G))
                                     : (Down(EKeys::Gamepad_FaceButton_Left) || Down(EKeys::X));
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
        if (!bSurvivalRules && Combat && HoldTime > 0 && HoldTime < .65f && !bHoldConsumed && !HasInteractable)
            Combat->Reload();
        // NYC Survival (owner 2026-10-31: "Y to switch weapons, have the pistol on hand"): a tap of Y / G cycles
        // to the next weapon on the quickbar; the hold still mounts the board.
        else if (bSurvivalRules && Combat && HoldTime > 0 && HoldTime < .65f && !bHoldConsumed && !HasInteractable &&
                 IsOnFoot())
            Combat->CycleWeapon();
        HoldTime = 0;
        bHoldConsumed = false;
    }
    if (bSurvivalRules)
    {
        // X / square is reload only here: any press length reloads on release.
        const bool ReloadKey = Down(EKeys::Gamepad_FaceButton_Left) || Down(EKeys::X);
        if (!ReloadKey && bWasReloadKey && Combat && !HasInteractable && IsOnFoot())
            Combat->Reload();
        bWasReloadKey = ReloadKey;
    }
    const bool JumpPressed = Down(EKeys::Gamepad_FaceButton_Bottom) || Down(EKeys::SpaceBar);
    if (JumpPressed && !bWasJump && TransitionTime <= 0)
    {
        if (bMounted && HopTime <= 0)
        {
            HopStartZ = GetActorLocation().Z;
            HopTime = 1.20f;
            bHeightHolding = false;
            ImpactPulse(BoardActor->GetActorLocation() - FVector(0, 0, 8), FVector::UpVector, 1.7f, .15f, .40f);
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
    // Survival has no teleport-and-heal: 0 HP is game over there (IHoverTestLevelPolicy::AllowsSandboxReset).
    if (Reset && !bWasReset && bSandboxResetAllowed)
        HoverReset();
    bWasReset = Reset;
    // AFS 2026-10-31 (spear item), NYC Survival: the quickbar's spear slot (UHoverCombatBridge::IsSpearSelected) is a
    // melee stance, so the katana flag carries it on foot (no aim, gun hidden, strafe facing, unarmed CLS stance) and
    // the trigger below feeds its tap / hold input. Leaving the slot hands the gun back.
    const bool SpearHeld = Combat && Combat->IsSpearSelected() && IsOnFoot();
    if (SpearHeld != bSpearHeld || (SpearHeld && !bMeleeEquipped))
    {
        const bool Changed = SpearHeld != bSpearHeld;
        bSpearHeld = SpearHeld;
        bMeleeEquipped = SpearHeld;
        bSuppressFireUntilRelease = true;
        bAiming = false;
        GunRaisedTime = 0;
        GunRecoil = GunRecoilVelocity = 0;
        if (Changed)
        {
            StatusMessage = SpearHeld ? TEXT("Spear | R2 / V: combo | Hold R2: heavy thrust | Y: next weapon")
                                      : TEXT("Gun equipped");
            StatusTime = 2.f;
        }
        SetView();
    }
    const bool Aim = !bMeleeEquipped && (PC->GetInputAnalogKeyState(EKeys::Gamepad_LeftTriggerAxis) > .2f ||
                                         Down(EKeys::RightMouseButton));
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
    const bool TriggerHeld = FirePressed || Down(EKeys::LeftMouseButton);
    if (!TriggerHeld)
        bSuppressFireUntilRelease = false;
    // Section 5 sprint-fire gate (survival rules only): no shot while sprinting or within 0.15 s after.
    const bool SprintBlocked =
        bSurvivalRules && IsOnFoot() && (bSprinting || GetWorld()->GetTimeSeconds() - SprintEndTime < .15f);
    const bool CanFire = TriggerHeld && !bSuppressFireUntilRelease && TransitionTime <= 0 && !SprintBlocked;
    if (bMeleeEquipped && IsOnFoot())
    {
        if (Combat)
            Combat->SetTrigger(false);
        if (bSpearHeld && Combat)
            Combat->SetSpearTrigger(CanFire); // Tap: light combo on release; hold: heavy thrust.
        else if (CanFire && MeleeWeapon && !MeleeWeapon->IsSwinging())
            Melee();
    }
    else if (Combat)
        Combat->SetTrigger(CanFire);
    else if (CanFire && FireCooldown <= 0 && !(MeleeWeapon && MeleeWeapon->IsSwinging()))
        FireShot();
}

void AHoverPilot::CancelPostureInput()
{
    bGroundCrouchHeld = false;
    GroundCrouchHold = 0;
    bCrouchedAtPress = false;
    bMovingAtPosturePress = false;
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
        bMovingAtPosturePress = Move->IsMovingOnGround() && GetVelocity().Size2D() > 180.f && !bProne;
        PostureTravel = GetVelocity().GetSafeNormal2D();
        if (bMovingAtPosturePress)
            GroundSlideSpeed = FMath::Min(GetVelocity().Size2D(), 900.f);
        if (Move->IsMovingOnGround() && !bIsCrouched)
        {
            Move->SetCrouchedHalfHeight(60.f);
            if (bMovingAtPosturePress)
            {
                GroundSlideTime = .85f;
                GroundSlideSpeed = FMath::Min(GetVelocity().Size2D(), 900.f);
            }
            Crouch();
        }
    }
    else if (GroundCrouchHold < .38f && bCrouchedAtPress && !bDiving)
    {
        GroundSlideTime = 0;
        UnCrouch();
    }
    bGroundCrouchHeld = Held;
}

void AHoverPilot::UpdateGroundPosture(float DT)
{
    ProneLandingTime = FMath::Max(0.f, ProneLandingTime - DT);
    if (bMounted)
        return;
    auto *Move = GetCharacterMovement();
    if (!bIsCrouched && !bDiving)
        bProne = false;
    GroundCrouchHold += bGroundCrouchHeld ? DT : 0.f;
    if (bGroundCrouchHeld && GroundCrouchHold >= .38f && Move->IsMovingOnGround() && !bProne)
    {
        bProne = true;
        GroundSlideTime = 0;
        // The supplied hands-and-knees crawl is taller than the old belly crawl.
        Move->SetCrouchedHalfHeight(42.f);
        Crouch();
        // Apply a second crouched size through CharacterMovement's floor-preserving path.
        Move->Crouch(false);
        if (bMovingAtPosturePress)
        {
            bDiving = true;
            LaunchCharacter(PostureTravel * FMath::Clamp(GroundSlideSpeed, 600.f, 900.f) + FVector(0, 0, 210.f), true,
                            true);
        }
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
        // AFS 2026-11-01 (owner: crouch "penguin waddle"): Vexa's chooser (CHT_VexaRifle) crouches on
        // PSD_DirectionalCrouch, whose loops (QA_Crouch_Walk_Fwd / Bwd / Left / Right) are all authored at 300 cm/s
        // and played at rate ~1.0. At the old 400 cm/s (CrouchedSpeed in DefaultGame.ini and the 400 here) the capsule
        // outran the steps by a third and the planted feet skated (ProveWalking crouch). Crouch at the clips' speed.
        Move->MaxWalkSpeedCrouched =
            bProne ? 120.f : (Combat ? GetDefault<UZE_PlayerSettings>()->CrouchedSpeed : 300.f);
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
    const float HeadingStep = (SteeringYaw + BankYaw) * DT;
    SetActorRotation(FRotator(0, GetActorRotation().Yaw + HeadingStep, 0));
    // Follow the board's heading while preserving the right-stick look offset.
    // Previously the camera remained locked to world yaw as the board turned away.
    if (Controller)
    {
        FRotator Look = Controller->GetControlRotation();
        Look.Yaw += HeadingStep;
        Controller->SetControlRotation(Look);
    }
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
    FlightEffectAcceleration = FMath::VInterpTo(FlightEffectAcceleration, Acceleration, DT, 8.f);
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
        ImpactPulse(Floor.ImpactPoint + Floor.ImpactNormal * 2, Floor.ImpactNormal, 2.2f, .18f, .5f);
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
    // The forced third-person (NYC Survival) OTS values; the 90 / 72 review camera everywhere else.
    const float ReviewFOV =
        bForcedThirdPerson ? (bAiming ? Assets->SurvivalAimFOV : Assets->SurvivalHipFOV) : (bAiming ? 72.f : 90.f);
    ReviewCamera->SetFieldOfView(FMath::FInterpTo(ReviewCamera->FieldOfView, ReviewFOV, DT, 10.f));
    if (bForcedThirdPerson)
        ReviewArm->TargetArmLength = FMath::FInterpTo(
            ReviewArm->TargetArmLength,
            bAiming ? Assets->SurvivalAimArmLength : Assets->SurvivalArmLength + (bSprinting ? 40.f : 0.f), DT, 6.f);
    UpdateCameraPosture(DT);
    // Before the board early-out: the body hide must run every third-person frame.
    UpdateCameraBodyHide();
    WeaponAimAlpha = FMath::FInterpTo(WeaponAimAlpha, bAiming ? 1.f : 0.f, DT, 12.f);
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
        const bool OnGround = bLifeEngineActive ? LifeMovement->bGrounded : GetCharacterMovement()->IsMovingOnGround();
        const bool InAir = bLifeEngineActive ? !LifeMovement->bGrounded : GetCharacterMovement()->IsFalling();
        Instance->bSupportedProne = UsesSupportedProne() && OnGround;
        GroundContactTime =
            IsOnFoot() && (bProne || GroundSlideTime > 0) ? .4f : FMath::Max(0.f, GroundContactTime - DT);
        Instance->bGroundContacts = false;
        if (IsOnFoot() && GroundContactTime > 0)
        {
            FHitResult Ground;
            FCollisionQueryParams Query(SCENE_QUERY_STAT(HoverPostureContact), false, this);
            Query.AddIgnoredActor(BoardActor);
            if (GetWorld()->LineTraceSingleByChannel(Ground, GetActorLocation(),
                                                     GetActorLocation() - FVector(0, 0, 240), ECC_Visibility, Query) &&
                Ground.ImpactNormal.Z > .65f)
            {
                Instance->bGroundContacts = true;
                const FTransform MeshTransform = GetMesh()->GetComponentTransform();
                auto PlaneForHit = [&](const FHitResult &Hit) {
                    return FPlane(MeshTransform.InverseTransformPosition(Hit.ImpactPoint),
                                  MeshTransform.InverseTransformVectorNoScale(Hit.ImpactNormal).GetSafeNormal());
                };
                Instance->GroundPlane = PlaneForHit(Ground);
                const FName Contacts[] = {TEXT("ball_l"),     TEXT("ball_r"), TEXT("lowerarm_r"),
                                          TEXT("lowerarm_l"), TEXT("hand_r"), TEXT("hand_l")};
                for (int32 I = 0; I < UE_ARRAY_COUNT(Contacts); ++I)
                {
                    Instance->ContactPlanes[I] = Instance->GroundPlane;
                    const FVector Point = GetMesh()->GetSocketLocation(Contacts[I]);
                    FHitResult Contact;
                    if (GetWorld()->LineTraceSingleByChannel(Contact, Point + FVector(0, 0, 150),
                                                             Point - FVector(0, 0, 250), ECC_Visibility, Query) &&
                        Contact.ImpactNormal.Z > .65f)
                        Instance->ContactPlanes[I] = PlaneForHit(Contact);
                }
            }
        }
        const FVector LocalVelocity =
            FRotator(0, bMounted ? GetActorRotation().Yaw : BodyYaw, 0).UnrotateVector(GetVelocity());
        const float Speed = LocalVelocity.Size2D();
        if (Speed > 8.f)
            GroundDirection = FMath::RadiansToDegrees(FMath::Atan2(LocalVelocity.Y, LocalVelocity.X));
        Instance->Locomotion = Assets->Locomotion;
        Instance->LocomotionInput = FVector(GroundDirection, Speed, 0);
        const bool Turning = !bMounted && Speed < 12.f && FMath::Abs(GroundYawRate) > 8.f;
        Instance->bGroundLocomotion = !bMounted && !InAir && !Turning;
        Instance->SequenceRate = Turning ? FMath::Clamp(FMath::Abs(GroundYawRate) / 95.f, .25f, 1.4f) : 1.f;
        Instance->RideBlend = Assets->RideBlend;
        Instance->RideAssets = Assets;
        Instance->bRiding = bMounted;
        Instance->bMountedReload = bMounted && Combat && Combat->GetWeapon() && Combat->GetWeapon()->IsReloading() &&
                                   LocomotionBridge && LocomotionBridge->IsActionPlaying();
        const float Along = FVector::DotProduct(GetVelocity(), GetActorForwardVector());
        const float PitchDemand = FlightPitch;
        Instance->RideInput = FVector(FMath::Clamp((BoardBank + SideInput * 12.f) / 28.f, -1.f, 1.f),
                                      FMath::Clamp(Along / 1800.f, -1.f, 1.f), 0);
        Instance->RidePitch = FMath::Clamp(PitchDemand / 45.f, -1.f, 1.f);
        Instance->bRideThrust = ForwardInput > .08f;
        Instance->RideAimInput = FVector(
            FMath::Clamp(FMath::FindDeltaAngleDegrees(GetActorRotation().Yaw, GetControlRotation().Yaw) / 90.f, -1.f,
                         1.f),
            FMath::Clamp((FRotator::NormalizeAxis(GetControlRotation().Pitch) - BoardPitch) / 60.f, -1.f, 1.f), 0);
        // Stance pose per rig (a pistol is held two-handed on one grip, not shouldered like a rifle).
        Instance->RifleAim = bMounted && Assets->RideGunPose ? Assets->RideGunPose.Get() : GetStanceAimPose();
        Instance->RifleFire = bMounted ? Assets->Fire.Get() : nullptr;
        Instance->ShotSerial = ShotsFired;
        // Through a rigged reload no body action plays (AHoverCyberRifle::Reload) and PlayGunReload holds
        // GunRaisedTime, so this stays true and the support IK keeps its full weight on the moving target.
        Instance->bAiming =
            (bAiming || GunRaisedTime > 0) && !(LocomotionBridge && LocomotionBridge->IsActionPlaying());
        // The aim layer's settle clock for the hand-rest cache (UpdateGunTransform): UpperBody blends in at 10/s,
        // so .5 s is within 1 % of the stance pose and hand_r reads as the pose holds it, not mid-blend.
        AimLayerUpTime = Instance->bAiming && !bMounted && Instance->RifleAim ? AimLayerUpTime + DT : 0.f;
        // Live: the rig's hand_l_target bone as the current Reload clip has placed it, else the static grip_l.
        Instance->SupportGripOffset = SupportGripOffset(WorldGunSkel);
        // The IK offset is measured from where the gun is seated (UpdateGunTransform): palm or wrist.
        Instance->bGripAtPalm = bRiggedGun && GunRig && GunRig->bGripAtPalm;
        // Including the rig's grip rotation (GripRotationOffset): the IK node's gun frame must be the drawn gun's.
        Instance->WeaponRotation =
            GetMesh()->GetComponentQuat().Inverse() * GetControlRotation().Quaternion() *
            FQuat::FindBetweenNormals(GunForward.GetSafeNormal(), FVector::ForwardVector) * GunGripRotation();
        // Design B1: the same bone's rotation delta and local scale X are the hand's turn and finger curl.
        SupportHandPose(WorldGunSkel, Instance->SupportHandRotation, Instance->SupportHandCurl);
#if WITH_EDITOR
        if (bSupportHandOverride)
        {
            Instance->SupportHandRotation = SupportHandOverrideRotation;
            Instance->SupportHandCurl = SupportHandOverrideCurl;
        }
#endif
        // Design A2: the rigged gun is drawn at the right hand (same rule as the held gun's visibility below, minus
        // the aim-exit tail); the support IK then runs at full weight through hit reacts and actions that drop
        // bAiming, so the left hand stays on the gun the right hand carries. Never while mounted (the glider poses
        // place both hands themselves).
        const bool MeleeNow = bMeleeEquipped || (MeleeWeapon && MeleeWeapon->IsSwinging());
        Instance->bRiggedGunUp = bRiggedGun && !bMounted && !MeleeNow && (bAiming || GunRaisedTime > 0);
        // Design A1: the stance fire additive (restarted per shot in the proxy) replaces the driver montage.
        Instance->StanceFireAdd = GetStanceFireAdditive(Instance->StanceRecoilScale);
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
    const bool Swinging = bMeleeEquipped || (MeleeWeapon && MeleeWeapon->IsSwinging());
    ActiveGunPrimitive(true)->SetVisibility(!Swinging && bReview && (bAiming || GunRaisedTime > 0 || AimExitTime > 0),
                                            true);
    ActiveGunPrimitive(false)->SetVisibility(!Swinging && !bReview, true);
    ViewArms->SetVisibility(!bReview);
    UpdateGunTransform();
    const bool Powered = bMounted && TransitionTime <= 0 && !bSteppingOn;
    const float Thrust = FMath::Max(0.f, ForwardInput);
    for (UNiagaraComponent *Effect : Boosters)
    {
        const bool Active = Powered && Thrust > .05f;
        const float Scale = bBoost ? .70f : .30f + .10f * Thrust;
        Effect->SetVariableFloat(TEXT("User.ThrustAlpha"), bBoost ? 1.f : .85f * Thrust);
        // Size is already reduced in the local asset and by component scale.
        // Multiplying this parameter too made the directional jets disappear.
        Effect->SetVariableFloat(TEXT("User.ThrustSize"), BoosterSize);
        Effect->SetVariableFloat(TEXT("User.ThurstSpawningRate"), BoosterSpawnRate * (bBoost ? 1.f : .7f * Thrust));
        if (Active && !Effect->IsActive())
            Effect->Activate(true);
        else if (!Active && Effect->IsActive())
            Effect->Deactivate();
        Effect->SetRelativeScale3D(FVector(Scale));
        if (Thrust > .05f)
        {
            const FVector ThrustDirection = FRotator(BoardPitch, GetActorRotation().Yaw, 0).Vector();
            Effect->SetWorldRotation(
                FRotationMatrix::MakeFromXZ(ThrustDirection.GetSafeNormal(), Board->GetUpVector()).Rotator());
        }
    }
    const float ForwardSpeed = FVector::DotProduct(GetVelocity(), GetActorForwardVector());
    const float Brake =
        ForwardInput < .05f
            ? FMath::Clamp(FMath::Max(ForwardSpeed / 1200.f,
                                      -FVector::DotProduct(FlightEffectAcceleration, GetActorForwardVector()) / 1800.f),
                           0.f, 1.f)
            : 0.f;
    const float Lift = FMath::Clamp(.18f + FMath::Max(0.f, PitchInput) * .55f +
                                        FMath::Max(0.f, float(FlightEffectAcceleration.Z)) / 5000.f,
                                    .18f, 1.f);
    const float Down = FMath::Clamp(
        FMath::Max(0.f, -PitchInput) * .7f + FMath::Max(0.f, -float(FlightEffectAcceleration.Z)) / 5000.f, 0.f, 1.f);
    const float SideForce = FVector::DotProduct(FlightEffectAcceleration, GetActorRightVector()) / 1800.f;
    for (int32 I = 0; I < DirectionalBoosters.Num(); ++I)
    {
        auto *Effect = DirectionalBoosters[I].Get();
        const float Target = I < 2    ? Lift
                             : I < 4  ? Down
                             : I == 4 ? FMath::Clamp(FMath::Max(-SideInput * .7f, -SideForce), 0.f, 1.f)
                             : I == 5 ? FMath::Clamp(FMath::Max(SideInput * .7f, SideForce), 0.f, 1.f)
                                      : Brake;
        const float Demand = JetDemands[I] = FMath::FInterpTo(JetDemands[I], Powered ? Target : 0.f, DT, 8.f);
        const FVector Force = I < 2    ? FVector::UpVector
                              : I < 4  ? -FVector::UpVector
                              : I == 4 ? -GetActorRightVector()
                              : I == 5 ? GetActorRightVector()
                                       : -GetActorForwardVector();
        const bool Active = Powered && Demand > .08f;
        const float Scale = .22f + .20f * Demand;
        Effect->SetVariableFloat(TEXT("User.ThrustAlpha"), .2f + Demand * .8f);
        Effect->SetVariableFloat(TEXT("User.ThrustSize"), BoosterSize);
        Effect->SetVariableFloat(TEXT("User.ThurstSpawningRate"), BoosterSpawnRate * (.22f + .6f * Demand));
        Effect->SetRelativeScale3D(FVector(Scale));
        Effect->SetWorldRotation(FRotationMatrix::MakeFromX(Force).Rotator());
        if (Active && !Effect->IsActive())
            Effect->Activate(true);
        else if (!Active && Effect->IsActive())
            Effect->Deactivate();
    }
}

void AHoverPilot::FinalizeViewPose()
{
    // Capture only after the FPS idle pose has evaluated, never from the
    // skeleton's A-pose while another component finishes its first tick.
    if (!bViewReferenceReady)
    {
        ViewReferenceHand = ViewArms->GetSocketTransform(TEXT("hand_r"), RTS_Component);
        ViewReferenceHand.SetLocation(
            FMath::Lerp(ViewReferenceHand.GetLocation(),
                        ViewArms->GetSocketTransform(TEXT("middle_01_r"), RTS_Component).GetLocation(), .5f));
        bViewReferenceReady = ViewReferenceHand.GetLocation().Size() > 20.f;
    }
    UpdateGunTransform();
}

void AHoverPilot::UpdateGunTransform()
{
    if (!Assets)
        return;
    const bool MeleeActive = bMeleeEquipped || (MeleeWeapon && MeleeWeapon->IsSwinging());
    if (auto *View = Cast<UHoverViewAnimInstance>(ViewArms->GetAnimInstance()))
        View->bMelee = MeleeActive;
    if (MeleeActive)
    {
        const FQuat ArmsRotation = FirstPersonCamera->GetComponentQuat() * FRotator(0, -90, 0).Quaternion();
        ViewArms->SetWorldLocationAndRotation(
            FirstPersonCamera->GetComponentTransform().TransformPosition(FVector(4, 2, -130)), ArmsRotation);
        return;
    }
    const UCameraComponent *Camera = bReview ? ReviewCamera : FirstPersonCamera;
    const FVector Eye = Camera->GetComponentLocation();
    const FVector RayEnd = Eye + Camera->GetForwardVector() * 50000.f;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverWeaponAlignment), true, this);
    Params.AddIgnoredActor(BoardActor);
    const FHitResult Hit = TraceWeaponRay(GetWorld(), Eye, RayEnd, Params);
    // A close enemy may be between the third-person camera and the muzzle.
    // Never turn the rifle back toward a target behind its own barrel.
    // Close obstruction is resolved by the breech-to-muzzle damage trace below.
    const FVector AimForward = Camera->GetForwardVector();
    const float AimDepth = Hit.bBlockingHit ? FVector::DotProduct(Hit.ImpactPoint - Eye, AimForward) : 50000.f;
    const float MinimumDepth = FMath::Max(180.f, FVector::DotProduct(GetMuzzlePosition() - Eye, AimForward) + 180.f);
    const FVector Target = Eye + AimForward * FMath::Max(AimDepth, MinimumDepth);
    const FQuat Basis = FQuat::FindBetweenNormals(GunForward.GetSafeNormal(), FVector::ForwardVector);
    // The gun hand is the anchor: the grip rides it and the gun takes its rotation from the aim ray, never
    // from the hand, so the right hand holds still through a reload while the body keeps its aim pose.
    // A rig that asks for it (bGripAtPalm) seats grip_r at the palm centre, where the fingers close, rather
    // than at the wrist joint about 5 cm behind it; this is the same midpoint FHoverSupportHandNode gives
    // the left hand and the first-person arms already use (HandPose below). The Ballista keeps its wrist offset.
    FVector Hand = GetMesh()->GetSocketLocation(TEXT("hand_r"));
    if (bRiggedGun && GunRig && GunRig->bGripAtPalm && GetMesh()->DoesSocketExist(TEXT("middle_01_r")))
        Hand = FMath::Lerp(Hand, GetMesh()->GetSocketLocation(TEXT("middle_01_r")), .5f);
    // The palm goes on the rig's SEAT (grip_r + GripSeatOffset: the grip's middle, not its top; 2026-10-31 "fist at
    // the bottom of the receiver, grip hanging empty"), and the gun turns by the rig's GripRotationOffset about that
    // seat so the grip axis runs through the fist. The convergence below keeps aiming the aim-ray frame; the offset's
    // pitch/yaw part is what the drawn barrel then deviates from the ray by (the rig keeps it under 6 deg).
    const FVector Seat = GunSeatPoint();
    const FQuat GripQ = GunGripRotation();
    FQuat WorldRotation = GetControlRotation().Quaternion() * Basis;
    for (int32 I = 0; I < 3; ++I)
    {
        const FVector Origin = Hand - (WorldRotation * GripQ).RotateVector(Seat);
        const FVector Muzzle = Origin + (WorldRotation * GripQ).RotateVector(GunMuzzle);
        WorldRotation = (Target - Muzzle).Rotation().Quaternion() * Basis;
    }
    const float RecoilStrength = GunRecoil * FMath::Lerp(1.f, .55f, WeaponAimAlpha);
    const FQuat Kick = FRotator(Assets->GunRecoilPitch * RecoilStrength, 0, 0).Quaternion();
    // Pitch around the grip in third person so the rifle stays in her hand.
    WorldRotation = WorldRotation * Basis.Inverse() * Kick * Basis;
    GunAimWorldRotation = WorldRotation;
    GunHandKick = FQuat::Identity;
    GunHandKickDeg = 0.f;
    if (bRiggedGun)
    {
        // The gun rides the right hand's kick (2026-10-30 23:30, "her hand is not on the grip"). The stance fire
        // additive turns hand_r; the grip already tracks the palm's POSITION, so only the rotation (and the fingers,
        // held in FHoverStanceFireNode) peeled the hand off the grip. The rest is hand_r in the settled aim pose,
        // re-read on every quiet frame (so the aim loop's own sway never accumulates) and frozen from the shot on,
        // so what reaches the gun is exactly the additive's deviation; dropped when the layer goes down (hit reacts,
        // parkour, the lowered gun) or the stance pose changes, since hand_r then moves for other reasons. Pitch
        // aiming never enters: the arms hold the pose whatever the control pitch (no aim-offset layer).
        const float Now = GetWorld()->GetTimeSeconds();
        if (ShotsFired != GunHandShotSerial)
        {
            GunHandShotSerial = ShotsFired;
            LastShotWorldTime = Now;
        }
        float AddScale;
        const UAnimSequence *Add = GetStanceFireAdditive(AddScale);
        const bool Quiet = !Add || Now - LastShotWorldTime > Add->GetPlayLength() + .1f;
        const bool Reloading = Combat && Combat->GetWeapon() && Combat->GetWeapon()->IsReloading();
        UAnimSequence *Stance = GetStanceAimPose();
        const FQuat HandNow = GetMesh()->GetSocketTransform(TEXT("hand_r"), RTS_Component).GetRotation();
        if (bMounted || Stance != GunHandRestStance || AimLayerUpTime <= 0.f)
        {
            bGunHandRestValid = false;
            GunHandRestStance = Stance;
        }
        if (!bMounted && Quiet && !Reloading && AimLayerUpTime > .5f)
        {
            GunHandRestRotation = HandNow;
            bGunHandRestValid = true;
        }
        if (bGunHandRestValid)
        {
            // Component-space delta, clamped as a safety, then the same turn about the same axes in world: a hand
            // pitching up kicks the muzzle up. The IK node applies the identical delta to its gun frame.
            GunHandKick = HoverClampRotation(HandNow * GunHandRestRotation.Inverse(), GunHandKickMaxDeg);
            GunHandKickDeg = FMath::RadiansToDegrees(GunHandKick.GetAngle());
            const FQuat MeshRotation = GetMesh()->GetComponentQuat();
            WorldRotation = (MeshRotation * GunHandKick * MeshRotation.Inverse() * WorldRotation).GetNormalized();
        }
        if (auto *Instance = Cast<UHoverAnimInstance>(GetMesh()->GetAnimInstance()))
        {
            Instance->GripHandRestRotation = GunHandRestRotation;
            Instance->bGripHandRestValid = bGunHandRestValid;
        }
    }
    else
        bGunHandRestValid = false;
    const FQuat GunRotation = WorldRotation * GripQ;
    ActiveGunPrimitive(true)->SetWorldLocationAndRotation(Hand - GunRotation.RotateVector(Seat), GunRotation);
    // Keep the sight centred while the barrel converges on the same aim point.
    // The tracer then travels along that barrel axis with no steering in flight.
    // Derive a fresh rest pose: reading the already-kicked component here would
    // accumulate sight drift when a shot and the appearance tick both update it.
    const FVector SightAligned = FVector(20, 0, 0) - Basis.RotateVector(GunSight);
    const FVector RestLocation = FMath::Lerp(FVector(35, 18, -20), SightAligned, WeaponAimAlpha);
    const FVector SightAnchor = FirstPersonCamera->GetComponentTransform().TransformPosition(
        RestLocation + Basis.RotateVector(GunSight));
    FQuat ViewRotation = FirstPersonCamera->GetComponentQuat() * Basis;
    for (int32 I = 0; I < 3; ++I)
    {
        const FVector Origin = SightAnchor - (ViewRotation * GripQ).RotateVector(GunSight);
        const FVector Muzzle = Origin + (ViewRotation * GripQ).RotateVector(GunMuzzle);
        ViewRotation = (Target - Muzzle).Rotation().Quaternion() * Basis;
    }
    // ViewGrip is the SEAT's world point (the palm goes there); the sight stays on its anchor whatever the grip
    // rotation, which pivots the view gun about the sight here and about the seat once the hand places it below.
    const FVector ViewGrip = SightAnchor + (ViewRotation * GripQ).RotateVector(Seat - GunSight);
    const FVector KickBack = FirstPersonCamera->GetForwardVector() * Assets->GunRecoilDistance * RecoilStrength;
    ViewRotation = ViewRotation * Basis.Inverse() * Kick * Basis;
    ActiveGunPrimitive(false)->SetWorldLocationAndRotation(
        ViewGrip - KickBack - (ViewRotation * GripQ).RotateVector(Seat), ViewRotation * GripQ);
    if (ViewArms->GetSkeletalMeshAsset())
    {
        FTransform HandPose = ViewArms->GetSocketTransform(TEXT("hand_r"), RTS_Component);
        HandPose.SetLocation(FMath::Lerp(HandPose.GetLocation(),
                                         ViewArms->GetSocketTransform(TEXT("middle_01_r"), RTS_Component).GetLocation(),
                                         .5f));
        if (bViewReferenceReady)
        {
            const FQuat ArmsRotation = FirstPersonCamera->GetComponentQuat() * FRotator(0, -90, 0).Quaternion();
            const FVector RestGrip = ViewGrip - KickBack;
            ViewArms->SetWorldLocationAndRotation(RestGrip - ArmsRotation.RotateVector(ViewReferenceHand.GetLocation()),
                                                  ArmsRotation);
            const FQuat Delta = ArmsRotation * HandPose.GetRotation() * ViewReferenceHand.GetRotation().Inverse() *
                                ArmsRotation.Inverse();
            const FQuat AnimatedRotation = Delta * ViewRotation * GripQ;
            const FVector AnimatedGrip = ViewArms->GetComponentTransform().TransformPosition(HandPose.GetLocation());
            ActiveGunPrimitive(false)->SetWorldLocationAndRotation(
                AnimatedGrip - AnimatedRotation.RotateVector(Seat), AnimatedRotation);
            if (auto *View = Cast<UHoverViewAnimInstance>(ViewArms->GetAnimInstance()))
            {
                // ADS moves the complete view model to its sight anchor. Keeping
                // the same hand reference prevents an extra animation sight drift.
                View->AimAlpha = 0.f;
                View->SupportGripOffset = SupportGripOffset(ViewGunSkel);
                View->WeaponRotation = ArmsRotation.Inverse() * AnimatedRotation;
                // Design B3: the first-person arms share the node type, so the same bone drives them.
                SupportHandPose(ViewGunSkel, View->SupportHandRotation, View->SupportHandCurl);
            }
        }
    }
}

void AHoverPilot::FireShot(float Damage, float Spread, float Range, AZE_WeaponBase *SourceWeapon)
{
    ++ShotsFired;
    FireCooldown = .18f;
    GunRaisedTime = 3.f;
    UpdateGunTransform();
    SetView();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(HoverShot), true, this);
    Params.bReturnPhysicalMaterial = true;
    Params.AddIgnoredActor(BoardActor);
    Params.AddIgnoredActor(SourceWeapon);
    UPrimitiveComponent *ActiveGun = ActiveGunPrimitive(bReview);
    const UPrimitiveComponent *Gun = ActiveGun;
    const FVector Muzzle = GetMuzzlePosition();
    if (Combat)
        UAISense_Hearing::ReportNoiseEvent(this, Muzzle, 1.f, this, 3000.f, TEXT("Gunshot"));
    const FVector BarrelDirection =
        Gun->GetComponentTransform().TransformVectorNoScale(GunForward).GetSafeNormal();
    const FVector ShotDirection = FMath::VRandCone(BarrelDirection, FMath::DegreesToRadians(Spread));
    const FVector Target = Muzzle + ShotDirection * Range;
    const auto *Definition = SourceWeapon ? SourceWeapon->GetWeaponDefinition() : nullptr;
    // Gate off: Legacy() reproduces the presentation values that shipped before the gun feel.
    const bool Enhanced = bEnhancedGunFeel;
    auto *Rifle = Cast<AHoverCyberRifle>(SourceWeapon);
    const FHoverGunFeelTier &Tier = !Enhanced ? FHoverGunFeelTier::Legacy()
                                    : Rifle   ? Rifle->GetFeelTier()
                                              : GetGunFeel()->Default;
    // The held rig's own flash wins over the definition's (the Ballista's blue NS_BallistaMuzzle is what every
    // rigged gun fired until 2026-10-31); null falls through to the definition, then the DA's loose MuzzleEffect.
    const UHoverGunRig *HeldRig = bRiggedGun ? GunRig.Get() : nullptr;
    UNiagaraSystem *MuzzleSystem =
        HeldRig && HeldRig->MuzzleFlashOverride ? HeldRig->MuzzleFlashOverride.Get()
        : Definition && Definition->MuzzleFlashFX.EffectType == EZE_EffectType::Niagara
            ? Definition->MuzzleFlashFX.NiagaraFX.LoadSynchronous()
            : Cast<UNiagaraSystem>(Assets->MuzzleEffect);
    if (auto *System = MuzzleSystem)
    {
        auto *Flash = UNiagaraFunctionLibrary::SpawnSystemAttached(
            System, ActiveGun, MuzzleAttachSocket(), MuzzleAttachOffset(),
            FRotationMatrix::MakeFromZ(GunForward).Rotator(), EAttachLocation::KeepRelativeOffset, true);
        if (Flash)
        {
            // Design C1: the held rig scales the definition's flash (an SMG or a revolver is not an AR). When the
            // rig REPLACES the system (MuzzleFlashOverride) its scale is absolute: the definition's scale belongs
            // to the definition's own asset (DA_Weapon_Pistol_001 carries 300 for its flash, which would spawn
            // NS_GunFire at 450x on the revolver in real play; the capture never saw it because apply_gun_rig keeps
            // the Ballista definition at 1.0).
            const bool OverrideFlash = HeldRig && HeldRig->MuzzleFlashOverride;
            const FVector FlashScale((OverrideFlash || !Definition ? 1.f : Definition->MuzzleFlashFX.Scale) *
                                     (bRiggedGun && GunRig ? GunRig->MuzzleFlashScale : 1.f));
            if (bRiggedGun)
                Flash->SetWorldScale3D(FlashScale); // Not the rig socket's x100 root-bone import scale.
            else
                Flash->SetRelativeScale3D(FlashScale);
            TWeakObjectPtr<UNiagaraComponent> WeakFlash(Flash);
            FTimerHandle Timer;
            GetWorld()->GetTimerManager().SetTimer(
                Timer,
                [WeakFlash]() {
                    if (WeakFlash.IsValid())
                        WeakFlash->DestroyComponent();
                },
                Tier.MuzzleFlashSeconds, false);
        }
    }
    if (Enhanced && Tier.MuzzleLightIntensity > 0)
    {
        EnsureMuzzleLight();
        AttachMuzzleLight();
        // Warm per-rig light (orange by default) over the tier's colour; the Ballista keeps the tier's.
        MuzzleLight->SetLightColor(HeldRig && HeldRig->bOverrideMuzzleLightColor ? HeldRig->MuzzleLightColorOverride
                                                                                 : Tier.MuzzleLightColor);
        // The rig's own reach (150 cm on the four rigs since 2026-10-31: the light is the whiteout) over the tier's.
        MuzzleLight->SetAttenuationRadius(HeldRig && HeldRig->MuzzleLightRadiusOverride > 0.f
                                              ? HeldRig->MuzzleLightRadiusOverride
                                              : Tier.MuzzleLightRadius);
        // Design C1: per-rig light scale on the tier's candelas (the Ballista keeps the tier value).
        MuzzleLight->SetIntensity(Tier.MuzzleLightIntensity * (bRiggedGun && GunRig ? GunRig->MuzzleLightScale : 1.f));
        // A point light with no source radius is inverse-square down to zero: the hands and a chrome gun 10-20 cm
        // from the muzzle still blew to white at 3 cd (2026-10-31 flash sheet) while the torso read lit. A 20 cm
        // source radius caps the near field without dimming the room.
        MuzzleLight->SetSourceRadius(bRiggedGun ? 20.f : 0.f);
        GetWorldTimerManager().SetTimer(MuzzleLightTimer,
                                        FTimerDelegate::CreateWeakLambda(this,
                                                                         [this]() {
                                                                             if (MuzzleLight)
                                                                                 MuzzleLight->SetIntensity(0.f);
                                                                         }),
                                        FMath::Max(.01f, Tier.MuzzleLightSeconds), false);
    }
    // Catch enemies/walls intersecting the barrel instead of starting beyond them.
    const FVector Breech = Gun->GetComponentTransform().TransformPosition(GunGrip);
    FHitResult Hit = TraceWeaponRay(GetWorld(), Breech, Muzzle, Params);
    const bool ProjectileShot =
        Definition && Definition->CombatStats.bUseProjectiles && Definition->CombatStats.ProjectileClass;
    bool ProjectileLaunched = false;
    if (!Hit.bBlockingHit && ProjectileShot)
    {
        const auto &Stats = Definition->CombatStats;
        const FTransform LaunchTransform(ShotDirection.Rotation(), Muzzle);
        if (auto *Projectile =
                GetWorld()->SpawnActorDeferred<AZE_Projectile>(Stats.ProjectileClass, LaunchTransform, SourceWeapon,
                                                               this, ESpawnActorCollisionHandlingMethod::AlwaysSpawn))
        {
            Projectile->Damage = Damage;
            Projectile->InstigatorPawn = this;
            Projectile->SourceWeapon = SourceWeapon;
            if (Projectile->CollisionComp)
            {
                Projectile->CollisionComp->IgnoreActorWhenMoving(this, true);
                Projectile->CollisionComp->IgnoreActorWhenMoving(BoardActor, true);
                Projectile->CollisionComp->IgnoreActorWhenMoving(SourceWeapon, true);
                for (TActorIterator<AZE_PickupBase> It(GetWorld()); It; ++It)
                    Projectile->CollisionComp->IgnoreActorWhenMoving(*It, true);
            }
            if (auto *Movement = Projectile->ProjectileMovement)
            {
                Movement->InitialSpeed = Stats.InitialProjectileSpeed;
                Movement->MaxSpeed = Stats.MaxProjectileSpeed;
                Movement->ProjectileGravityScale = Stats.ProjectileGravityScale;
            }
            Projectile->FinishSpawning(LaunchTransform);
            Projectile->InitVelocity(ShotDirection);
            Projectile->SetLifeSpan(FMath::Clamp(Range / FMath::Max(1.f, Stats.InitialProjectileSpeed), .05f, 30.f));
            ProjectileLaunched = true;
        }
    }
    AActor *DamageSource = SourceWeapon ? static_cast<AActor *>(SourceWeapon) : this;
    AActor *FirstHitActor = nullptr;
    if (!Enhanced)
    {
        if (!Hit.bBlockingHit && !ProjectileLaunched)
            Hit = TraceWeaponRay(GetWorld(), Muzzle, Target + ShotDirection * 3.f, Params);
        if (!ProjectileLaunched &&
            (!Hit.bBlockingHit || FVector::DotProduct(Hit.ImpactPoint - Muzzle, ShotDirection) > 2.f))
            if (auto *Tracer = GetWorld()->SpawnActor<AHoverShotVisual>())
                Tracer->Launch(Muzzle, Hit.bBlockingHit ? Hit.ImpactPoint : Target);
        if (Hit.bBlockingHit)
        {
            if (SourceWeapon)
                SourceWeapon->ProcessHit(Hit);
            else if (Hit.GetActor())
                UGameplayStatics::ApplyPointDamage(Hit.GetActor(), Damage, ShotDirection, Hit, GetController(),
                                                   DamageSource, nullptr);
            // Zombie damage owns blood.
            if (!Cast<AHoverZombie>(Hit.GetActor()) && !Cast<AHoverCyberZombie>(Hit.GetActor()))
                SpawnSurfaceImpact(Hit, SourceWeapon, Definition);
        }
        FirstHitActor = Hit.GetActor();
    }
    else if (!ProjectileLaunched)
    {
        // Bounded penetration: corpses are free, each live body uses one pierce, a wall stops the round.
        FVector End = Target, Start = Muzzle;
        int32 PiercesLeft = Tier.Pierce;
        float Scale = 1.f;
        for (int32 Guard = 0; Guard < Tier.Pierce + 8; ++Guard)
        {
            if (Guard > 0 || !Hit.bBlockingHit) // Iteration 0 reuses the breech hit.
                Hit = TraceWeaponRay(GetWorld(), Start, Target + ShotDirection * 3.f, Params);
            if (!Hit.bBlockingHit)
                break;
            End = Hit.ImpactPoint;
            AActor *Victim = Hit.GetActor();
            if (!FirstHitActor)
                FirstHitActor = Victim;
            // The weapon path matches vendor ProcessHit (impact normal); PostApo keeps the shot direction.
            const FVector HitDirection = SourceWeapon ? FVector(Hit.ImpactNormal) : ShotDirection;
            if (IsGunFeelZombie(Victim))
            {
                const bool WasCorpse = IsGunFeelCorpse(Victim); // Sampled before damage.
                Params.AddIgnoredActor(Victim);
                Start = Hit.ImpactPoint + ShotDirection * 5.f;
                if (WasCorpse)
                    continue;
                const float Applied = UGameplayStatics::ApplyPointDamage(Victim, Damage * Scale, HitDirection, Hit,
                                                                         GetController(), DamageSource, nullptr);
                if (Applied > 0)
                {
                    const bool Kill = IsGunFeelCorpse(Victim);
                    NotifyHitConfirmed(IsGunFeelHeadshot(Victim, Hit), Kill, DamageSource);
                    if (Kill)
                    {
                        FTimerHandle HitStopTimer; // Per victim: a shared handle would cancel a pierced kill's restore.
                        HoverEffects::HitStop(Victim, Tier.KillTimeDilation, Tier.KillHitStopSeconds, HitStopTimer);
                    }
                }
                if (PiercesLeft-- <= 0)
                    break;
                Scale *= Tier.PierceScale;
                continue;
            }
            if (Victim)
                UGameplayStatics::ApplyPointDamage(Victim, Damage * Scale, HitDirection, Hit, GetController(),
                                                   DamageSource, nullptr);
            SpawnSurfaceImpact(Hit, SourceWeapon, Definition);
            break;
        }
        if (FVector::DotProduct(End - Muzzle, ShotDirection) > 2.f)
            if (auto *Tracer = GetWorld()->SpawnActor<AHoverShotVisual>())
            {
                if (HeldRig && HeldRig->TracerOverride)
                {
                    // Tracer trial: the rig's trail system over the tier's, coloured like the tier's tracer and cut
                    // to the rig's lifetime; a copy, so the tier table itself never changes.
                    FHoverGunFeelTier RigTier = Tier;
                    RigTier.Tracer = HeldRig->TracerOverride.Get();
                    RigTier.bTracerColor = HeldRig->bTracerOverrideTierColor;
                    RigTier.bTracerColorAB = false;
                    if (HeldRig->TracerOverrideLifetime > 0.f)
                        RigTier.TracerLifetime = HeldRig->TracerOverrideLifetime;
                    Tracer->Launch(Muzzle, End, RigTier);
                }
                else
                    Tracer->Launch(Muzzle, End, Tier);
            }
    }
    if (Rifle)
        EjectShellForShot(Rifle); // The rig's eject socket and timing; the Ballista ejects at its breech.
    else
        PlayGunFire(); // Mounted/direct shots have no rifle actor; the rifle path cycles from PlayFireAnimation.
    // A tier pool replaces the definition's single FireSound; Legacy() keeps the pool empty.
    USoundBase *ShotSound = Enhanced ? Tier.PickFireSound(LastFireSoundIndex) : nullptr;
    if (!ShotSound)
        ShotSound = Definition ? Definition->FireSound.LoadSynchronous() : Assets->ShotSound.Get();
    if (ShotSound && !Enhanced)
        UGameplayStatics::PlaySoundAtLocation(this, ShotSound, Muzzle, .60f, FMath::FRandRange(.96f, 1.04f));
    else if (ShotSound)
    {
        // Rig sockets carry the root bone's x100 import scale; the sounds keep world scale 1.
        const auto Unscaled = [this](USceneComponent *Sound) {
            if (Sound && bRiggedGun)
                Sound->SetWorldScale3D(FVector::OneVector);
        };
        Unscaled(UGameplayStatics::SpawnSoundAttached(
            ShotSound, ActiveGun, MuzzleAttachSocket(), MuzzleAttachOffset(), EAttachLocation::KeepRelativeOffset,
            false, Tier.SoundVolume,
            Tier.SoundPitch * FMath::FRandRange(1.f - Tier.SoundPitchJitter, 1.f + Tier.SoundPitchJitter)));
        if (Tier.TailEveryN > 0 && ShotsFired % Tier.TailEveryN == 0)
            if (auto *Tail = Tier.PickTailSound(LastTailSoundIndex))
                Unscaled(UGameplayStatics::SpawnSoundAttached(Tail, ActiveGun, MuzzleAttachSocket(),
                                                              MuzzleAttachOffset(), EAttachLocation::KeepRelativeOffset,
                                                              false, .5f, Tier.SoundPitch));
    }
    if (auto *PC = Cast<APlayerController>(GetController()))
    {
        if (!Enhanced)
            PC->PlayDynamicForceFeedback(.18f, .06f, false, true, false, true);
        else if (!PlayRumble(Definition ? Definition->GetFName() : FName(TEXT("HoverFire_Default")), Tier.FireRumble,
                             false))
            PC->PlayDynamicForceFeedback(.55f, .07f, true, true, false, true);
    }
    if (bMounted && bAiming && Assets->Fire)
    {
        CurrentAnimation = nullptr;
        PlayPose(Assets->Fire, false);
    }
    // Kick only after an actual round is fired. The next shot starts at the
    // currently recoiling barrel; flashes remain attached to that same muzzle.
    GunRecoil = FMath::Min(1.5f, GunRecoil + 1.f);
    GunRecoilVelocity = 0;
    if (Enhanced)
    {
        // View recoil: the weapon-model spring above stays as the visual layer.
        const FVector2D Kick = Tier.bOverrideRecoil ? Tier.RecoilKick
                               : Definition         ? Definition->CombatStats.RecoilKick
                                                    : FVector2D(.35f, .15f);
        const float PitchKick = float(Kick.X) * FMath::FRandRange(1.f - Tier.RecoilJitter, 1.f + Tier.RecoilJitter) *
                                (bAiming ? Tier.AimRecoilScale : 1.f) * RecoilSetting;
        const float YawKick = FMath::FRandRange(-float(Kick.Y), float(Kick.Y)) * RecoilSetting;
        ApplyViewRecoil(PitchKick, YawKick);
        // The rifle shakes from PlayFireAnimation; only the no-bridge (PostApo) path shakes here.
        if (!SourceWeapon)
            PlayFireShake(Tier, nullptr);
    }
    UpdateGunTransform();
    UE_LOG(LogTemp, Verbose, TEXT("HOVER_SHOT hit=%s"), *GetNameSafe(FirstHitActor));
}

void AHoverPilot::SpawnSurfaceImpact(const FHitResult &Hit, AZE_WeaponBase *SourceWeapon,
                                     const UZE_WeaponDefinition *Definition)
{
    // World materials use the purchased weapon's impact map; the local dust
    // remains a fallback for unassigned surfaces.
    bool HasImpactFX = false;
    if (Definition)
    {
        const FZE_SurfaceImpactData *Impact = &Definition->DefaultImpactEffects;
        const FString Surface = GetNameSafe(Hit.PhysMaterial.Get());
        for (const auto &Candidate : Definition->ImpactEffectsMap)
            if (!Candidate.SurfaceTag.IsNone() && Surface.Contains(Candidate.SurfaceTag.ToString()))
            {
                Impact = &Candidate;
                break;
            }
        HasImpactFX = Impact->ImpactFX.EffectType == EZE_EffectType::Niagara ? !Impact->ImpactFX.NiagaraFX.IsNull()
                                                                             : !Impact->ImpactFX.CascadeFX.IsNull();
        SourceWeapon->SpawnImpactEffects(Hit);
    }
    if (!HasImpactFX && Assets->SurfaceImpact)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, 1.f, 0, .9f, Assets->SurfaceImpact);
}

const UHoverGunFeel *AHoverPilot::GetGunFeel() const
{
    return Assets && Assets->GunFeel ? Assets->GunFeel.Get() : UHoverGunFeel::BuiltIn();
}

const FHoverGunFeelTier &AHoverPilot::GetActiveFeelTier() const
{
    if (!bEnhancedGunFeel)
        return FHoverGunFeelTier::Legacy();
    if (const auto *Rifle = Combat ? Cast<AHoverCyberRifle>(Combat->GetWeapon()) : nullptr)
        return Rifle->GetFeelTier();
    return GetGunFeel()->Default;
}

void AHoverPilot::EnsureMuzzleLight()
{
    if (MuzzleLight)
        return;
    MuzzleLight = NewObject<UPointLightComponent>(this, TEXT("GunFeelMuzzleLight"));
    MuzzleLight->SetupAttachment(ActiveGunPrimitive(bReview), MuzzleAttachSocket());
    MuzzleLight->SetRelativeLocation(Assets ? MuzzleAttachOffset() : FVector::ZeroVector);
    MuzzleLight->SetIntensityUnits(ELightUnits::Candelas);
    MuzzleLight->SetIntensity(0.f);
    MuzzleLight->SetCastShadows(false);
    const FHoverGunFeelTier &Tier = GetGunFeel()->Default;
    MuzzleLight->SetAttenuationRadius(Tier.MuzzleLightRadius);
    MuzzleLight->SetLightColor(Tier.MuzzleLightColor);
    MuzzleLight->RegisterComponent();
}

void AHoverPilot::ApplyViewRecoil(float PitchKick, float YawKick)
{
    auto *PC = Cast<APlayerController>(GetController());
    if (!PC)
        return;
    // Write the control rotation directly; AddControllerPitchInput would apply the legacy input scale.
    FRotator View = PC->GetControlRotation();
    const float Before = FRotator::NormalizeAxis(View.Pitch);
    View.Pitch = FMath::Clamp(Before + PitchKick, -75.f, 75.f); // Same clamp as UpdateInput.
    View.Yaw += YawKick;
    View.Roll = 0;
    PC->SetControlRotation(View);
    const FHoverGunFeelTier &Tier = GetActiveFeelTier();
    RecoilPitchDebt = FMath::Clamp(RecoilPitchDebt + float(View.Pitch - Before) * Tier.RecoilAutoRecoverFraction, 0.f,
                                   Tier.RecoilDebtCap);
    RecoilTrackedPitch = View.Pitch;
    LastRecoilTime = GetWorld()->GetTimeSeconds();
}

void AHoverPilot::UpdateViewRecoil(float DT)
{
    if (!bEnhancedGunFeel || RecoilPitchDebt <= 0)
        return;
    auto *PC = Cast<APlayerController>(GetController());
    if (!PC)
    {
        RecoilPitchDebt = 0;
        return;
    }
    FRotator View = PC->GetControlRotation();
    const float Pitch = FRotator::NormalizeAxis(View.Pitch);
    // Look input applied outside UpdateInput (the Parkour template's mouse path) also pays the debt.
    if (Pitch < RecoilTrackedPitch)
        RecoilPitchDebt = FMath::Max(0.f, RecoilPitchDebt - (RecoilTrackedPitch - Pitch));
    RecoilTrackedPitch = Pitch;
    const auto *Weapon = Combat ? Combat->GetWeapon() : nullptr;
    const auto *Definition = Weapon ? Weapon->GetWeaponDefinition() : nullptr;
    const FHoverGunFeelTier &Tier = GetActiveFeelTier();
    const float FireRate = Definition && Definition->FireRate > 0 ? Definition->FireRate : 8.f;
    const float Quiet = FMath::Max(.2f, 1.5f / FireRate);
    if (RecoilPitchDebt <= 0 || (Weapon && Weapon->IsFiring()) || GetWorld()->GetTimeSeconds() - LastRecoilTime < Quiet)
        return;
    const float Rate = Tier.bOverrideRecoil ? Tier.RecoilRecovery
                       : Definition         ? Definition->CombatStats.RecoilRecovery
                                            : 10.f;
    const float Step = FMath::Min(RecoilPitchDebt, FMath::Max(0.f, Rate) * DT);
    View.Pitch = FMath::Clamp(Pitch - Step, -75.f, 75.f);
    PC->SetControlRotation(View);
    RecoilPitchDebt -= Step;
    RecoilTrackedPitch = View.Pitch;
}

void AHoverPilot::PlayFireShake(const FHoverGunFeelTier &Tier, const UZE_WeaponDefinition *Definition)
{
    auto *PC = Cast<APlayerController>(GetController());
    if (!PC || !PC->IsLocalController())
        return;
    TSubclassOf<UCameraShakeBase> Shake = Tier.FireShake;
    if (!Shake && Definition)
        Shake = Definition->FireCameraShake;
    if (!Shake)
    {
        static TWeakObjectPtr<UClass> FallbackShake;
        static bool bFallbackMissing = false;
        if (!FallbackShake.IsValid() && !bFallbackMissing)
        {
            FallbackShake = LoadClass<UCameraShakeBase>(
                nullptr, TEXT("/Game/ZESP/ZE/FX/CameraShake/BP_M16_FireShake.BP_M16_FireShake_C"));
            bFallbackMissing = !FallbackShake.IsValid();
        }
        Shake = FallbackShake.Get();
    }
    if (!Shake)
        Shake = UHoverFireShake::StaticClass();
    const UHoverGunFeel *Feel = GetGunFeel();
    const float ViewScale = bAiming   ? Feel->AimingShakeScale
                            : bReview ? Feel->ThirdPersonShakeScale
                                      : Feel->FirstPersonShakeScale;
    const float Scale = Tier.ShakeScale * ViewScale * ShakeSetting;
    if (Scale <= 0)
        return;
    // View only: the camera manager's POV moves, the aim traces do not.
    PC->ClientStartCameraShake(Shake, Scale);
    ++FireShakeCount;
}

bool AHoverPilot::PlayRumble(FName Key, const FHoverRumbleCurve &Curve, bool bIgnoreTimeDilation, FName Tag)
{
    auto *PC = Cast<APlayerController>(GetController());
    if (!PC || !PC->IsLocalController())
        return false;
    UForceFeedbackEffect *Effect = Curve.Override.IsNull() ? nullptr : Curve.Override.LoadSynchronous();
    if (!Effect)
    {
        if (const TObjectPtr<UForceFeedbackEffect> *Cached = RumbleCache.Find(Key))
            Effect = *Cached;
        else if ((Effect = HoverHaptics::Build(this, Curve)) != nullptr)
            RumbleCache.Add(Key, Effect);
    }
    if (!Effect)
        return false;
    FForceFeedbackParameters Parameters;
    Parameters.Tag = Tag;
    Parameters.bIgnoreTimeDilation = bIgnoreTimeDilation;
    PC->ClientPlayForceFeedback(Effect, Parameters);
    ++RumbleRequestCount;
    return true;
}

void AHoverPilot::NotifyHitConfirmed(bool Headshot, bool Kill, const AActor *Causer)
{
    if (!Assets || !bEnhancedGunFeel) // BeginPlay may have returned early without assets.
        return;
    const UHoverGunFeel *Feel = GetGunFeel();
    const float Now = GetWorld()->GetTimeSeconds();
    // A multi-kill (pierce, same frame) keeps the kill marker but plays one sting.
    const bool Merged = Kill && Now - LastKillStingTime < Feel->KillStingMinInterval;
    LastHitMarkTime = Now;
    bLastHitHeadshot = Headshot;
    bLastHitKill = Kill;
    ++HitMarkCount;
    if (Merged)
        return;
    const auto *Rifle = Cast<AHoverCyberRifle>(Causer);
    const FHoverGunFeelTier &Tier = Rifle ? Rifle->GetFeelTier() : Feel->Default;
    if (Kill)
    {
        LastKillStingTime = Now;
        ++KillStingCount;
        if (Tier.bKillFlash)
            KillFlashTime = Now;
    }
    // Null-safe until the hit-confirm audio is imported.
    const TSoftObjectPtr<USoundBase> &Cue = Kill       ? Feel->KillSound
                                            : Headshot ? Feel->HeadshotSound
                                                       : Feel->HitConfirmSound;
    if (USoundBase *Sound = Cue.IsNull() ? nullptr : Cue.LoadSynchronous())
        UGameplayStatics::PlaySound2D(this, Sound, Kill ? 1.f : .8f);
    const bool Melee = Cast<AHoverMeleeWeapon>(Causer) != nullptr; // Katana contact reuses the body-hit curve.
    // Metal-wound impact layer on every confirmed gun hit; the katana plays its own cut (audio pass 2026-10-31).
    if (Melee)
    {
        if (USoundBase *Cut = Feel->PickMeleeHitSound(LastMeleeHitSoundIndex))
            UGameplayStatics::PlaySound2D(this, Cut, Feel->MeleeHitVolume, Kill ? .92f : 1.f);
    }
    else if (USoundBase *Impact = Feel->PickHitConfirmSound(LastHitSoundIndex))
        UGameplayStatics::PlaySound2D(this, Impact, Feel->HitConfirmPoolVolume,
                                      Kill       ? Feel->KillPoolPitch
                                      : Headshot ? Feel->HeadshotPoolPitch
                                                 : 1.f);
    if (Kill)
        PlayRumble(Headshot ? FName(TEXT("HoverHit_KillHeadshot")) : FName(TEXT("HoverHit_Kill")),
                   Headshot ? Feel->KillHeadshotRumble : Feel->KillRumble, true, TEXT("Hit"));
    else if (Headshot && !Melee)
        PlayRumble(TEXT("HoverHit_Headshot"), Feel->HeadshotRumble, true, TEXT("Hit"));
    else
        PlayRumble(TEXT("HoverHit_Body"), Feel->HitRumble, true, TEXT("Hit"));
}

void AHoverPilot::PlayMeleeSwingSound()
{
    if (USoundBase *Whoosh = GetGunFeel()->PickMeleeSwingSound(LastMeleeSwingSoundIndex))
    {
        UGameplayStatics::PlaySoundAtLocation(this, Whoosh, GetActorLocation() + FVector(0, 0, 60),
                                              GetGunFeel()->MeleeSwingVolume, FMath::FRandRange(.95f, 1.05f));
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_MELEE_SWING_SOUND %s"), *Whoosh->GetName());
    }
}

void AHoverPilot::UpdateFootsteps(float DT)
{
    // Audio pass 2026-10-31: no clip carries footstep notifies, so the feet are read live. A step plants when a
    // ball bone drops back under PlantHeight after rising past LiftHeight; a cadence clock covers clips whose
    // swing stays lower than that. Only on foot, grounded and actually travelling.
    if (!GetWorld() || !GetMesh())
        return;
    const UHoverGunFeel *Feel = GetGunFeel();
    const bool Grounded =
        IsOnFoot() && !bDefeated && !bKnockedDown &&
        (bLifeEngineActive ? LifeMovement->bGrounded : GetCharacterMovement()->IsMovingOnGround());
    const float Speed = GetVelocity().Size2D();
    const float Now = GetWorld()->GetTimeSeconds();
    const float Bottom = GetActorLocation().Z - GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
    static const FName Feet[2] = {TEXT("ball_l"), TEXT("ball_r")};
    bool Planted = false;
    for (int32 Foot = 0; Foot < 2; ++Foot)
    {
        const FVector At = GetMesh()->GetSocketLocation(Feet[Foot]);
        const float Height = At.Z - Bottom;
        if (Height > Feel->FootstepLiftHeight)
            bFootWasUp[Foot] = true;
        else if (bFootWasUp[Foot] && Height < Feel->FootstepPlantHeight)
        {
            bFootWasUp[Foot] = false;
            if (Grounded && Speed > 40.f && Now - LastFootstepTime[Foot] > .18f && Now - LastAnyFootstepTime > .1f)
            {
                LastFootstepTime[Foot] = Now;
                PlayFootstep(At, Speed);
                Planted = true;
            }
        }
    }
    if (!Planted && Grounded && Speed > 80.f)
    {
        const float Stride = Speed > Feel->FootstepRunSpeed ? Feel->FootstepRunStride : Feel->FootstepWalkStride;
        if (Now - LastAnyFootstepTime > 1.6f * Stride / Speed)
            PlayFootstep(GetMesh()->GetSocketLocation(Feet[GFrameCounter & 1]), Speed);
    }
}

void AHoverPilot::PlayFootstep(const FVector &At, float Speed)
{
    const UHoverGunFeel *Feel = GetGunFeel();
    LastAnyFootstepTime = GetWorld()->GetTimeSeconds();
    // Surface from the physical material or the floor material's name: dirt-like words, water-like words,
    // everything else concrete (NYC is asphalt and pavement).
    int32 Surface = 0;
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(HoverFootstep), false, this);
    Query.bReturnPhysicalMaterial = true;
    Query.AddIgnoredActor(BoardActor);
    if (GetWorld()->LineTraceSingleByChannel(Hit, At + FVector(0, 0, 25), At - FVector(0, 0, 60), ECC_Visibility,
                                             Query))
    {
        FString Name = GetNameSafe(Hit.PhysMaterial.Get());
        FString MaterialName;
        if (const UPrimitiveComponent *Floor = Hit.GetComponent())
            if (const UMaterialInterface *Material = Floor->GetMaterial(0))
                MaterialName = Material->GetName().ToLower();
        Name = Name.ToLower() + TEXT(" ") + MaterialName;
        // AFS 2026-11-01 (owner: wet footsteps on dry NYC ground): the NYC streets are MI_Asphalt_Water (the city
        // pack's asphalt with an optional puddle layer) on DefaultPhysicalMaterial, so the word "water" in the
        // material name sent every street step to the puddle set. A paved material counts as dry unless its name says
        // puddle; water / wet still count from the physical material or any other material.
        const bool Paved = MaterialName.Contains(TEXT("asphalt")) || MaterialName.Contains(TEXT("concrete")) ||
                           MaterialName.Contains(TEXT("road")) || MaterialName.Contains(TEXT("pavement")) ||
                           MaterialName.Contains(TEXT("sidewalk"));
        const FString WetWords = Paved ? GetNameSafe(Hit.PhysMaterial.Get()).ToLower() : Name;
        if (Name.Contains(TEXT("puddle")) || WetWords.Contains(TEXT("water")) || WetWords.Contains(TEXT("wet")))
            Surface = 2;
        else if (Name.Contains(TEXT("dirt")) || Name.Contains(TEXT("grass")) || Name.Contains(TEXT("mud")) ||
                 Name.Contains(TEXT("soil")) || Name.Contains(TEXT("sand")) || Name.Contains(TEXT("gravel")) ||
                 Name.Contains(TEXT("ground")))
            Surface = 1;
    }
    const bool Run = Speed > Feel->FootstepRunSpeed;
    if (USoundBase *Step = Feel->PickFootstep(Run, Surface, LastFootstepSoundIndex))
    {
        UGameplayStatics::PlaySoundAtLocation(this, Step, At, Feel->FootstepVolume * (bIsCrouched ? .55f : 1.f),
                                              FMath::FRandRange(.94f, 1.06f));
        UE_LOG(LogTemp, Verbose, TEXT("HOVER_FOOTSTEP %s run=%d surface=%d speed=%.0f"), *Step->GetName(), Run, Surface,
               Speed);
    }
}

float AHoverPilot::GetHitMarkerAge() const
{
    return GetWorld() ? GetWorld()->GetTimeSeconds() - LastHitMarkTime : 1e6f;
}

float AHoverPilot::GetKillFlashAge() const
{
    return GetWorld() ? GetWorld()->GetTimeSeconds() - KillFlashTime : 1e6f;
}

FVector AHoverPilot::GetMuzzlePosition() const
{
    // A rig's muzzle socket is read live, so the trace starts where the Fire clip's body kick put the barrel.
    // GunMuzzle starts at the DA header default, so a missing DA reads the same (0, 46, 2) as before.
    const UPrimitiveComponent *Gun = ActiveGunPrimitive(bReview);
    const FName Socket = MuzzleAttachSocket();
    return Socket.IsNone() ? Gun->GetComponentTransform().TransformPosition(GunMuzzle) : Gun->GetSocketLocation(Socket);
}

UPrimitiveComponent *AHoverPilot::ActiveGunPrimitive(bool bReviewView) const
{
    if (bRiggedGun)
        return bReviewView ? static_cast<UPrimitiveComponent *>(WorldGunSkel.Get()) : ViewGunSkel.Get();
    return bReviewView ? static_cast<UPrimitiveComponent *>(WorldGun.Get()) : ViewGun.Get();
}

FName AHoverPilot::MuzzleAttachSocket() const
{
    // Riding the socket keeps flash, light and sound on the barrel through any body recoil baked
    // into the Fire clip; the static Ballista has no sockets and uses the GunMuzzle offset.
    return bRiggedGun && !GunRig->MuzzleSocket.IsNone() && WorldGunSkel->DoesSocketExist(GunRig->MuzzleSocket)
               ? GunRig->MuzzleSocket
               : NAME_None;
}

FVector AHoverPilot::MuzzleAttachOffset() const
{
    return MuzzleAttachSocket().IsNone() ? GunMuzzle : FVector::ZeroVector;
}

bool UHoverPilotAssets::FindGunRig(FName DefinitionName, const UHoverGunRig *&OutRig) const
{
    const TObjectPtr<UHoverGunRig> *Found = GunRigs.Find(DefinitionName);
    if (!Found)
        Found = GunRigs.Find(UHoverGunRig::NormalizeWeaponKey(DefinitionName));
    OutRig = Found ? Found->Get() : nullptr;
    return Found != nullptr;
}

const UHoverGunRig *AHoverPilot::FindGunRig(const UZE_WeaponDefinition *Definition) const
{
    const UHoverGunRig *Rig = nullptr;
    if (Assets && Definition && Assets->FindGunRig(Definition->GetFName(), Rig))
        return Rig; // A key mapped to None pins that definition to the static Ballista.
    return DefaultGunRig;
}

void AHoverPilot::SetupStaticGun()
{
    bStaticGunReady = true;
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
            // The small reflex lens is translucent; Nanite cannot render it.
            Optic->SetForceDisableNanite(true);
            Optic->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Optic->SetOnlyOwnerSee(Gun == ViewGun);
            Optic->CastShadow = Gun != ViewGun;
            Optic->RegisterComponent();
        }
    WorldGun->SetRelativeLocation(FVector(4, 2, 0));
    WorldGun->SetRelativeRotation(FRotator(0, 90, -90));
}

void AHoverPilot::SetMuzzleFlashOverride(UNiagaraSystem *System)
{
    // GunRig is held const because the pilot only reads it; this one in-memory write is the gallery's and is
    // never saved (no Modify / MarkPackageDirty), so the DA on disk keeps what AuthorGunRigs.py authored.
    if (!GunRig)
        return;
    const_cast<UHoverGunRig *>(GunRig.Get())->MuzzleFlashOverride = System;
    UE_LOG(LogTemp, Log, TEXT("HOVER_GUN muzzle flash override %s on %s"), System ? *System->GetName() : TEXT("cleared"),
           *GunRig->GetName());
}

void AHoverPilot::ApplyGunRig(const UHoverGunRig *Rig)
{
    if (!Assets)
        return;
    if (Rig && !Rig->Mesh)
        Rig = nullptr;
    if (Rig == GunRig && (Rig ? bRiggedGun : bStaticGunReady))
        return;
    // The camera body hide marks the held gun it found; hand that state over to the new held gun.
    const bool HideHeld = bCameraHidesBody;
    if (HideHeld)
        ApplyCameraBodyHide(false);
    GetWorldTimerManager().ClearTimer(GunClipTimer);
    GetWorldTimerManager().ClearTimer(GunReloadEjectTimer);
    // Before any SetSkeletalMesh: the old skeleton's sequence must not stay on the single-node instance.
    for (auto *Gun : {ViewGunSkel.Get(), WorldGunSkel.Get()})
        if (Gun->GetSingleNodeInstance())
        {
            Gun->Stop();
            Gun->SetAnimation(nullptr);
        }
    CurrentGunClip = nullptr;
    GunRig = Rig;
    bRiggedGun = Rig != nullptr;
    bGunEmpty = false;
    GunCylinderAngle = 0.f;
    GunClipRate = 1.f;
    if (Rig)
    {
        // Every rig is X forward from grip_r; its own fallbacks, never the Y-forward Ballista DA vectors.
        GunForward = FVector::ForwardVector;
        GunMuzzle = Rig->FallbackMuzzle;
        GunGrip = Rig->FallbackGrip;
        GunSupportGrip = Rig->FallbackSupportGrip;
        GunSight = Rig->FallbackSight;
        for (auto *Gun : {ViewGunSkel.Get(), WorldGunSkel.Get()})
        {
            Gun->SetSkeletalMesh(Rig->Mesh);
            Gun->SetAnimationMode(EAnimationMode::AnimationSingleNode);
            // Clips keep time while a pair member is hidden (view toggle, camera body hide) so a view
            // switch mid-reload shows the magazine where the other view left it.
            Gun->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        }
        // Rest poses before the first UpdateGunTransform; the rig is X forward so no yaw is needed.
        ViewGunSkel->SetRelativeLocation(FVector(35, 18, -20));
        WorldGunSkel->SetRelativeLocation(FVector(4, 2, 0));
        // The static Ballista pair stays hidden while rigged (a rigged start never gives it a mesh).
        ViewGun->SetVisibility(false, true);
        WorldGun->SetVisibility(false, true);
        if (Rig->bSocketsDriveOffsets)
        {
            // Locations only: the root bone's x100 import scale is in the transform, not in the positions.
            const TPair<FName, FVector *> Sockets[] = {{Rig->MuzzleSocket, &GunMuzzle},
                                                       {Rig->GripSocket, &GunGrip},
                                                       {Rig->SupportSocket, &GunSupportGrip},
                                                       {Rig->SightSocket, &GunSight}};
            for (const auto &Socket : Sockets)
            {
                FTransform Transform;
                if (ResolveGunSocket(Rig->Mesh, Socket.Key, Transform))
                    *Socket.Value = Transform.GetLocation();
                else
                    UE_LOG(LogTemp, Warning, TEXT("HOVER_GUN socket %s missing on %s; keeping the rig fallback %s"),
                           *Socket.Key.ToString(), *GetNameSafe(Rig->Mesh), *Socket.Value->ToString());
            }
        }
        if (MuzzleAttachSocket().IsNone())
            UE_LOG(LogTemp, Warning, TEXT("HOVER_GUN muzzle socket %s missing on %s; flash, light and sound use %s"),
                   *Rig->MuzzleSocket.ToString(), *GetNameSafe(Rig->Mesh), *GunMuzzle.ToString());
        PlayGunIdle();
    }
    else
    {
        // DA values, as at BeginPlay: the Ballista's own Y-forward frame.
        GunMuzzle = Assets->GunMuzzle;
        GunForward = Assets->GunForward;
        GunGrip = Assets->GunGrip;
        GunSupportGrip = Assets->GunSupportGrip;
        GunSight = Assets->GunSight;
        if (!bStaticGunReady)
            SetupStaticGun();
        for (auto *Gun : {ViewGunSkel.Get(), WorldGunSkel.Get()})
            Gun->SetVisibility(false, true);
    }
    // EnsureMuzzleLight may have attached the light to the pair that is now hidden.
    if (MuzzleLight)
        AttachMuzzleLight();
    // OwnerNoSee is set only on a hide transition; re-apply the current state to the new held gun.
    if (HideHeld)
        ApplyCameraBodyHide(true);
    UE_LOG(LogTemp, Display, TEXT("HOVER_GUN rigged=%d mesh=%s muzzle=%s grip=%s support=%s rig=%s"), bRiggedGun,
           Rig ? *GetNameSafe(Rig->Mesh) : *GetNameSafe(Assets->Gun), *GunMuzzle.ToString(), *GunGrip.ToString(),
           *GunSupportGrip.ToString(), *GetNameSafe(Rig));
}

FTransform AHoverPilot::GunEjectTransform() const
{
    // Live, not bind pose: a revolver's ejection_port lines up with the swung-out cylinder only mid-Reload.
    const UPrimitiveComponent *Gun = ActiveGunPrimitive(bReview);
    // Rotation and location only: rig sockets carry the root bone's x100 import scale, and the vendor
    // shell code sets the rifle actor's transform from this one.
    if (bRiggedGun && !GunRig->EjectSocket.IsNone() && Gun->DoesSocketExist(GunRig->EjectSocket))
        return FTransform(Gun->GetSocketQuaternion(GunRig->EjectSocket), Gun->GetSocketLocation(GunRig->EjectSocket));
    const FVector Breech = Gun->GetComponentTransform().TransformPosition(GunGrip);
    // A rig without the socket ejects at its grip with the socket convention's X to the gun's right.
    if (bRiggedGun)
        return FTransform(Gun->GetComponentQuat() * FRotator(0, 90, 0).Quaternion(), Breech);
    // The static Ballista has no socket and keeps its visible breech at the grip.
    return FTransform(Gun->GetComponentQuat(), Breech);
}

void AHoverPilot::EjectGunShell(AHoverCyberRifle *Rifle) const
{
    if (bRiggedGun)
        Rifle->EjectRigShellAt(GunEjectTransform(), GunRig->EjectDirection, GunRig->EjectImpulse);
    else
        Rifle->EjectShellAt(GunEjectTransform());
}

void AHoverPilot::AttachMuzzleLight()
{
    UPrimitiveComponent *ActiveGun = ActiveGunPrimitive(bReview);
    if (MuzzleLight->GetAttachParent() != ActiveGun || MuzzleLight->GetAttachSocketName() != MuzzleAttachSocket())
        MuzzleLight->AttachToComponent(ActiveGun, FAttachmentTransformRules::KeepRelativeTransform,
                                       MuzzleAttachSocket());
    MuzzleLight->SetRelativeLocation(MuzzleAttachOffset());
    // Rig sockets carry the root bone's x100 import scale; the light keeps world scale 1.
    if (bRiggedGun)
        MuzzleLight->SetWorldScale3D(FVector::OneVector);
    else
        MuzzleLight->SetRelativeScale3D(FVector::OneVector);
}

void AHoverPilot::SetGunEmpty(bool bEmpty)
{
    bGunEmpty = bEmpty;
}

void AHoverPilot::EjectShellForShot(AHoverCyberRifle *Rifle)
{
    if (!bRiggedGun || (GunRig->bEjectsPerShot && GunRig->EjectDelay <= 0))
        EjectGunShell(Rifle);
    else if (GunRig->bEjectsPerShot)
        // Pump, lever and bolt: the casing leaves on the stroke, which plays at the Fire clip's rate.
        ScheduleGunEject(Rifle, GunRig->EjectDelay / FMath::Max(GunClipRate, .01f), 1);
}

void AHoverPilot::ScheduleGunEject(AHoverCyberRifle *Rifle, float Delay, int32 Count, FTimerHandle *Handle)
{
    FTimerHandle Stroke; // Per round: a shared handle would cancel the previous round's casing.
    const TWeakObjectPtr<AHoverCyberRifle> WeakRifle(Rifle);
    const UHoverGunRig *Rig = GunRig;
    const auto Eject = [this, WeakRifle, Rig, Count]() {
        // A rig swap before the casing falls drops it with the old gun.
        if (!WeakRifle.IsValid() || GunRig != Rig)
            return;
        for (int32 I = 0; I < Count; ++I)
            EjectGunShell(WeakRifle.Get());
    };
    GetWorldTimerManager().SetTimer(Handle ? *Handle : Stroke, FTimerDelegate::CreateWeakLambda(this, Eject),
                                    FMath::Max(Delay, .01f), false);
}

void AHoverPilot::ScheduleReloadEject(AHoverCyberRifle *Rifle, float Duration, int32 Spent)
{
    if (!Rifle || !bRiggedGun || GunRig->bEjectsPerShot || GunRig->EjectDelay <= 0 || Spent <= 0)
        return;
    // EjectDelay is clip time; PlayGunReload stretches the clip to Duration, so the empties keep the beat.
    // Called right after PlayGunReload, so CurrentGunClip is the reload clip (empty or tactical) now playing.
    const bool Reloading =
        CurrentGunClip && (CurrentGunClip == GunRig->Reload || CurrentGunClip == GunRig->ReloadTactical);
    const float Length = Reloading ? FMath::Max(CurrentGunClip->GetPlayLength(), .01f) : 0.f;
    const float Scale = Length > 0 && Duration > 0 ? Duration / Length : 1.f;
    ScheduleGunEject(Rifle, GunRig->EjectDelay * Scale, FMath::Min(Spent, 8), &GunReloadEjectTimer);
}

void AHoverPilot::AdvanceGunCylinder()
{
    if (bRiggedGun && !GunRig->CylinderBone.IsNone())
        GunCylinderAngle = FRotator::ClampAxis(GunCylinderAngle + GunRig->IndexDegrees);
}

float AHoverPilot::GunCylinderApplied() const
{
    if (!bRiggedGun || !GunRig || GunRig->CylinderBone.IsNone())
        return 0.f;
    // AdvanceGunCylinder runs as the indexing clip starts, so while that clip plays the bone only gets the
    // angle from before this shot; the clip itself supplies the rest and lands exactly on GunCylinderAngle.
    const bool Indexing = CurrentGunClip && (CurrentGunClip == GunRig->Fire || CurrentGunClip == GunRig->FireLast ||
                                             CurrentGunClip == GunRig->DryFire || CurrentGunClip == GunRig->Chamber);
    return FRotator::NormalizeAxis(GunCylinderAngle - (Indexing ? GunRig->IndexDegrees : 0.f));
}

void AHoverPilot::FinalizeGunPose(USkeletalMeshComponent *Gun)
{
    const float Applied = GunCylinderApplied();
    if (!Gun || FMath::IsNearlyZero(Applied, .01f) || !Gun->GetSkeletalMeshAsset())
        return;
    const int32 Bone = Gun->GetBoneIndex(GunRig->CylinderBone);
    // The finalized read buffer is what SendRenderDynamicData and GetSocketTransform use for this frame;
    // the next evaluation rewrites it from the clip, so nothing accumulates. Single-node playback has no
    // graph to put a ModifyBone node in, hence the in-place edit.
    auto &Pose = const_cast<TArray<FTransform> &>(Gun->GetComponentSpaceTransforms());
    if (Bone == INDEX_NONE || !Pose.IsValidIndex(Bone))
        return;
    const FTransform Pivot = Pose[Bone];
    // Spin about the cylinder bone's own X axis (every rig bone is identity-oriented in component space, so
    // this is the same axis the clips turn it about), through the bone's origin.
    const FQuat Spin = Pivot.GetRotation() * FQuat(FVector::ForwardVector, FMath::DegreesToRadians(Applied)) *
                       Pivot.GetRotation().Inverse();
    const FTransform Delta = FTransform(-Pivot.GetLocation()) * FTransform(Spin) * FTransform(Pivot.GetLocation());
    const FReferenceSkeleton &Ref = Gun->GetSkeletalMeshAsset()->GetRefSkeleton();
    for (int32 I = Bone; I < Pose.Num(); ++I)
        if (I == Bone || Ref.BoneIsChildOf(I, Bone))
            Pose[I] = Pose[I] * Delta;
}

void AHoverPilot::PlayGunClip(UAnimSequence *Clip, float DurationOrZero, bool bLoop)
{
    if (!bRiggedGun)
        return;
    GetWorldTimerManager().ClearTimer(GunClipTimer);
    CurrentGunClip = Clip;
    GunClipStartTime = GetWorld()->GetTimeSeconds();
    if (!Clip)
    {
        for (auto *Gun : {ViewGunSkel.Get(), WorldGunSkel.Get()})
            Gun->Stop();
        return;
    }
    const float Length = FMath::Max(Clip->GetPlayLength(), .01f);
    const float Rate = DurationOrZero > 0 ? Length / FMath::Max(DurationOrZero, .01f) : 1.f;
    GunClipRate = Rate;
    for (auto *Gun : {ViewGunSkel.Get(), WorldGunSkel.Get()})
    {
        Gun->PlayAnimation(Clip, bLoop);
        Gun->SetPlayRate(Rate);
        Gun->SetPosition(0.f, false); // A re-triggered Fire clip restarts the bolt from home.
    }
    if (!bLoop)
        GetWorldTimerManager().SetTimer(GunClipTimer, this, &AHoverPilot::PlayGunIdle, Length / Rate, false);
}

void AHoverPilot::PlayGunIdle()
{
    // Locked back after the last round until a reload; a rig without IdleEmpty idles bolt home.
    UAnimSequence *Clip = GunRig && bGunEmpty && GunRig->IdleEmpty ? GunRig->IdleEmpty.Get()
                          : GunRig                                 ? GunRig->Idle.Get()
                                                                   : nullptr;
    PlayGunClip(Clip, 0.f, true);
}

void AHoverPilot::PlayGunFire(float MaxSeconds, bool bLastRound)
{
    if (!bRiggedGun)
        return;
    UAnimSequence *Clip = bLastRound && GunRig->FireLast ? GunRig->FireLast.Get() : GunRig->Fire.Get();
    if (!Clip)
        return;
    bGunEmpty = bGunEmpty || bLastRound; // Its finish timer hands over to IdleEmpty.
    // A semi press faster than the clip lets the running cycle finish rather than snapping the bolt home;
    // past 60 % it restarts. The last round always plays, so the bolt locks back. No cylinder index for a
    // press the clip swallows: the additive would jump a chamber under the still-running clip.
    if (!bLastRound && CurrentGunClip == GunRig->Fire && CurrentGunClip->GetPlayLength() > 0 &&
        (GetWorld()->GetTimeSeconds() - GunClipStartTime) * GunClipRate < .6f * CurrentGunClip->GetPlayLength())
        return;
    AdvanceGunCylinder();
    const float Length = Clip->GetPlayLength();
    PlayGunClip(Clip, MaxSeconds > 0 && Length > MaxSeconds ? MaxSeconds : 0.f);
}

void AHoverPilot::PlayGunDryFire()
{
    if (!bRiggedGun || !GunRig->DryFire)
        return;
    AdvanceGunCylinder();
    PlayGunClip(GunRig->DryFire, 0.f);
}

void AHoverPilot::PlayGunReload(float Duration, bool bTactical)
{
    if (!bRiggedGun)
        return;
    // The empty Reload starts locked back and releases the bolt; the tactical one keeps it home.
    UAnimSequence *Clip = bTactical && GunRig->ReloadTactical ? GunRig->ReloadTactical.Get() : GunRig->Reload.Get();
    bGunEmpty = false; // A cancelled reload re-sets it from the magazine (AHoverCyberRifle::CancelReload).
    // The body plays no reload of its own: it keeps the aim pose for the whole clip (plus a beat to settle
    // the left hand back on grip_l) and only the support IK moves, following the clip's hand_l_target.
    // UpdateAppearance also tops GunRaisedTime up to .5 s on every reloading tick; this covers the whole
    // duration up front so a cancelled reload still lowers the gun on the same schedule.
    GunRaisedTime = FMath::Max(GunRaisedTime, Duration + .3f);
    if (Clip)
        PlayGunClip(Clip, Duration);
}

UAnimSequence *AHoverPilot::GetStanceAimPose() const
{
    if (!Assets)
        return nullptr;
    if (bRiggedGun && GunRig && GunRig->Stance == EHoverGunStance::Pistol && Assets->PistolAim)
        return Assets->PistolAim;
    return Assets->RifleAim;
}

FVector AHoverPilot::SupportGripOffset(const USkeletalMeshComponent *Gun) const
{
    // Component space of a rig is gun space (X forward, origin at grip_r); the root bone's x100 import scale
    // sits on the socket transform, not in its location, so the location reads in cm as the other offsets do.
    // Read from the component's current pose, not the reference skeleton: the Reload clips move this bone
    // to the magazine, the belt and back, and the hand is meant to follow it frame by frame.
    // Measured from the SEAT (grip_r + GripSeatOffset), the point UpdateGunTransform puts at the right palm: the IK
    // node adds this to the right palm in the gun's frame, so anything else would misplace the left hand by the seat.
    if (bRiggedGun && GunRig && Gun && !GunRig->HandTargetSocket.IsNone() &&
        Gun->DoesSocketExist(GunRig->HandTargetSocket))
        return Gun->GetSocketTransform(GunRig->HandTargetSocket, RTS_Component).GetLocation() - GunSeatPoint();
    return GunSupportGrip - GunSeatPoint();
}

void AHoverPilot::SupportHandPose(const USkeletalMeshComponent *Gun, FQuat &OutRotation, float &OutCurl) const
{
    OutRotation = FQuat::Identity;
    OutCurl = 1.f;
    if (!bRiggedGun || !GunRig || !Gun || GunRig->HandTargetSocket.IsNone() ||
        !Gun->DoesSocketExist(GunRig->HandTargetSocket))
        return;
    // Rotation: component (gun) space, which every rig bone rests at identity in (ValidateGunClips.py), so the
    // bone's current rotation IS the authored delta; the socket transform's scale (root x100) never touches it.
    OutRotation = Gun->GetSocketTransform(GunRig->HandTargetSocket, RTS_Component).GetRotation().GetNormalized();
    // Curl: the bone's own parent-relative scale X. The component-space scale would be 100 x the key.
    const int32 Bone = Gun->GetBoneIndex(GunRig->HandTargetSocket);
    const TArrayView<const FTransform> Local = const_cast<USkeletalMeshComponent *>(Gun)->GetBoneSpaceTransformsView();
    if (Bone != INDEX_NONE && Local.IsValidIndex(Bone))
    {
        const float Curl = float(Local[Bone].GetScale3D().X);
        if (FMath::IsFinite(Curl) && Curl > KINDA_SMALL_NUMBER)
            OutCurl = FMath::Clamp(Curl, 0.f, 1.6f);
    }
}

UAnimSequence *AHoverPilot::GetStanceFireAdditive(float &OutScale) const
{
    OutScale = 1.f;
    if (!Assets || !bRiggedGun || !GunRig || bMounted)
        return nullptr;
    const bool Pistol = GunRig->Stance == EHoverGunStance::Pistol;
    UAnimSequence *Add = Pistol ? Assets->PistolFireAdd.Get() : Assets->RifleFireAdd.Get();
    OutScale = Pistol ? Assets->PistolRecoilScale : Assets->RifleRecoilScale;
    // A non-additive sequence accumulated as one would add a whole pose on top of the aim pose.
    return Add && Add->IsValidAdditive() ? Add : nullptr;
}

void AHoverPilot::PlayGunChamber()
{
    if (!bRiggedGun || !GunRig->Chamber)
        return;
    AdvanceGunCylinder();
    PlayGunClip(GunRig->Chamber, 0.f);
}

void AHoverPilot::StopGunClip()
{
    GetWorldTimerManager().ClearTimer(GunReloadEjectTimer); // A cancelled reload drops no empties.
    PlayGunIdle();
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
        auto *Niagara = UNiagaraFunctionLibrary::SpawnSystemAtLocation(
            GetWorld(), System, Location, Rotation, FVector(Template == Assets->ShockwaveEffect ? 1.f : Scale), true,
            false);
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
            Niagara->SetVariableFloat(TEXT("User.DustSize"), 65.f);
            Niagara->SetVariableFloat(TEXT("User.DustSpawningRate"), 240.f);
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
                    {
                        // Stop the source while letting emitted dust/debris finish.
                        // The vehicle dust system kills particles on Deactivate.
                        WeakDust->SetVariableFloat(TEXT("User.DustSpawningRate"), 0.f);
                        WeakDust->SetVariableInt(TEXT("User.RockSpawningRate"), 0);
                        WeakDust->SetVariableFloat(TEXT("User.RockSpawnRate"), 0.f);
                    }
                },
                .14f, false);
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
    if (bDiving)
    {
        bDiving = false;
        ProneLandingTime = .45f;
        bProne = true;
        GetCharacterMovement()->SetCrouchedHalfHeight(42.f);
        Crouch();
    }
    if (!bMounted && FallSpeed > 150.f)
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, .5f, .06f, .3f);
}

float AHoverPilot::GetHealth() const
{
    return Combat && Combat->Survival ? Combat->Survival->GetHealth() : SandboxHealth;
}

float AHoverPilot::GetMaxHealth() const
{
    return Combat && Combat->Survival ? Combat->Survival->GetMaxHealth() : 100.f;
}

bool AHoverPilot::UsesAimFacing() const
{
    // Out of line so the complete bridge type is visible for the reload term (NYC Section 2 Â§4).
    return bMeleeEquipped || bAiming || GunRaisedTime > 0 || !bReview || (Combat && Combat->IsReloading());
}

float AHoverPilot::TakeDamage(float Damage, const FDamageEvent &Event, AController *EventInstigator, AActor *Causer)
{
    if (bDefeated || Damage <= 0 || GetWorld()->GetTimeSeconds() < RespawnGraceUntil)
        return 0.f;
    if (Damage > 0 && Causer != this && LocomotionBridge && IsOnFoot() &&
        GetWorld()->GetTimeSeconds() - LastHitReaction > .65f && !LocomotionBridge->IsActionPlaying())
    {
        LastHitReaction = GetWorld()->GetTimeSeconds();
        const FVector TowardImpact = Causer ? Causer->GetActorLocation() - GetActorLocation() : FVector::ZeroVector;
        const bool FromBehind = FVector::DotProduct(FRotator(0, BodyYaw, 0).Vector(), TowardImpact) < 0;
        const TCHAR *Clip = FromBehind ? TEXT("MM_HitReact_Back_Med_01") : TEXT("MM_HitReact_Front_Lgt_01");
        const FString Path =
            FString::Printf(TEXT("/Game/CLS/Example/SetupYourHeroExample/Anims/Rifle/HitReact/%s.%s"), Clip, Clip);
        LocomotionBridge->PlayAction(LoadObject<UAnimSequence>(nullptr, *Path));
    }
    if (bInvincible)
        return 0.f;
    // The vendor wave system calculates damage scaling but its attack trace
    // still sends base damage. Apply it per hit, never to the shared zombie data.
    if (Cast<AHoverCyberZombie>(Causer))
        if (const auto *Mode = GetWorld()->GetAuthGameMode<AHoverCyberCityGameMode>(); Mode && Mode->GetWaveSettings())
            Damage *= FMath::Max(0.f, Mode->GetRoundDamageScale(Mode->GetCurrentWave()));
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
        if (bMortalLocked)
        {
            // NYC Survival (Section 2 Â§5): no 3 s reset, no teleport, no heal. The mode owns game over.
            DefeatedUntil = BIG_NUMBER;
            if (auto *Mode = GetWorld()->GetAuthGameMode<AHoverNYCSurvivalGameMode>())
                Mode->BeginGameOver();
        }
    }
    return Applied;
}

void AHoverPilot::ShowStompPulse(const FVector &Location, const FVector &Normal, float Radius, bool Close)
{
    // The local purchased ring measures about 70 cm in radius at scale 1.
    // Match its visible reach to the actual distance-gated knockdown area.
    ImpactPulse(Location + Normal * 3.f, Normal, Radius / 70.f, Close ? .5f : 0.f, .8f);
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
    bProne = bDiving = false;
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
        ImpactPulse(Hit.ImpactPoint + Hit.ImpactNormal * 2, Hit.ImpactNormal, 1.7f, .1f, .5f);
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
    HoverMotion::Spring(GunRecoil, GunRecoilVelocity, 0.f, DT, Assets->GunRecoilRecovery);
    UpdateViewRecoil(DT);
    UpdateInput(DT);
    UpdateGroundPosture(DT);
    UpdateLifeEngine(DT);
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
    UpdateFootsteps(DT);
    if (GetActorLocation().Z < -10000)
        HoverReset();
}

FString AHoverPilot::GetPrompt() const
{
    if (bDefeated)
        return bMortalLocked ? TEXT("Vexa is down - game over") : TEXT("Defeated - resetting at the start...");
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
    {
        if (bSurvivalRules)
            return CanDismount() ? TEXT("Hold Y / G: get off   |   Hold L1 / Q: stronger bank while steering")
                                 : TEXT("Descend and slow down to get off   |   Hold L1 / Q: stronger bank");
        return CanDismount() ? TEXT("Hold X: get off   |   Hold L1 / Q: stronger bank while steering")
                             : TEXT("Descend and slow down to get off   |   Hold L1 / Q: stronger bank");
    }
    if (bSurvivalRules)
        return HasBoardNearby() ? TEXT("Hold Y / G: glider (quick escape)   |   X: reload")
                                : TEXT("Glider: hold Y / G next to it   |   X: reload");
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
    UHoverPickupFeedback::DrawHUD(this); // AFS 2026-10-31: Nuke flash/banner, pickup toasts (NYC only)
    DrawText(TEXT("D-pad Up / F6: test settings + level"), FLinearColor(.7f, .85f, 1.f), 24, 16);
    const FString HealthLabel =
        Pilot ? FString::Printf(TEXT("%s | HP %.0f/%.0f"), Pilot->IsInvincible() ? TEXT("INVINCIBLE") : TEXT("NORMAL"),
                                Pilot->GetHealth(), Pilot->GetMaxHealth())
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
    if (Pilot->bEnhancedGunFeel)
    {
        const UHoverGunFeel *Feel = Pilot->GetGunFeel();
        const float Age = Pilot->GetHitMarkerAge();
        if (Feel->HitMarkerSeconds > 0 && Age >= 0 && Age < Feel->HitMarkerSeconds)
        {
            const bool Kill = Pilot->WasLastHitKill();
            FLinearColor Color = Kill                          ? Feel->KillMarkerColor
                                 : Pilot->WasLastHitHeadshot() ? Feel->HeadMarkerColor
                                                               : Feel->BodyMarkerColor;
            Color.A = 1.f - Age / Feel->HitMarkerSeconds;
            // Spread-driven gap (P0-5): 4 px plus 6 px per degree of the rifle's effective spread.
            const auto *Rifle = Pilot->Combat ? Cast<AHoverCyberRifle>(Pilot->Combat->GetWeapon()) : nullptr;
            const float Gap = 4.f + (Rifle ? Rifle->GetEffectiveSpreadDegrees() * 6.f : 0.f);
            const float Size = Kill ? Feel->KillMarkerScale : 1.f;
            const float Signs[4][2] = {{1, 1}, {-1, 1}, {1, -1}, {-1, -1}};
            for (const auto &Sign : Signs)
                DrawLine(X + Sign[0] * (Gap + 2) * Size, Y + Sign[1] * (Gap + 2) * Size,
                         X + Sign[0] * (Gap + 10) * Size, Y + Sign[1] * (Gap + 10) * Size, Color, 2.f);
        }
        const float Flash = Pilot->GetKillFlashAge();
        if (Flash >= 0 && Flash < .06f)
            DrawRect(FLinearColor(1, 1, 1, .12f * (1.f - Flash / .06f)), 0, 0, Canvas->ClipX, Canvas->ClipY);
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
            : FString::Printf(TEXT("A jump   Hold L3 run   Moving: tap B slide, hold B dive   Still: B crouch/prone   "
                                   "F5 view   %.0f m/s"),
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
    if (Pilot->IsOnFoot())
        DrawText(TEXT("Tap R3 / V: slash | Hold R3: katana / gun | R2: use weapon"), FLinearColor(.8f, .85f, .9f), 32,
                 Canvas->ClipY - 120);
    // AFS 2026-10-31 (spear item): no vendor weapon is equipped while the spear slot is selected.
    if (Pilot->Combat && Pilot->Combat->IsSpearSelected())
        DrawText(Pilot->Combat->GetSpearHudText(), FLinearColor::White, Canvas->ClipX - 285, Canvas->ClipY - 185,
                 nullptr, 1.4f);
    if (Pilot->Combat)
        if (const auto *Weapon = Pilot->Combat->GetWeapon())
        {
            const FString Ammo =
                Pilot->IsMeleeEquipped()
                    ? TEXT("KATANA")
                    : FString::Printf(TEXT("%d / %d%s"), Weapon->GetCurrentClipAmmo(), Weapon->GetReserveAmmo(),
                                      Weapon->IsReloading()               ? TEXT("  RELOADING")
                                      : Weapon->GetCurrentClipAmmo() == 0 ? TEXT("  EMPTY - tap X / R")
                                                                          : TEXT(""));
            DrawText(Ammo, FLinearColor::White, Canvas->ClipX - 285, Canvas->ClipY - 185, nullptr, 1.4f);
            UHoverPickupFeedback::DrawReserveFlash(this, Weapon->GetCurrentClipAmmo(), Weapon->GetReserveAmmo(),
                                                    Pilot->IsMeleeEquipped(), Canvas->ClipX - 285, Canvas->ClipY - 185,
                                                    1.4f);
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
    if (bSpawnRangeZombies)
        GetWorld()->SpawnActor<AHoverZombieRange>();
}

AHoverExplorationGameMode::AHoverExplorationGameMode()
{
    bSpawnRangeZombies = false;
    bSpawnBike = false;
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
