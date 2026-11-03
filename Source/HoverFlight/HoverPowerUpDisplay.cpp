#include "HoverPowerUpDisplay.h"

#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "UObject/ConstructorHelpers.h"
#if WITH_EDITOR
#include "Editor.h"
#include "LevelEditorViewport.h"
#endif

// AFS 2026-10-31: see HoverPowerUpDisplay.h. Everything here is presentation, driven by the clock of one life:
//   0 .. SpawnIn                 pop in (scale ease-out-back)
//   0 .. Life                    spin, bob, aura, neon, Geiger ticks, the alternating spark / pop schedule
//   Life - Warning .. Life       heartbeat (and the arc crawl) ease in from zero and speed up
//   Life .. Life + Fade          shrink and fade out
//   .. + RespawnDelay            hidden, then the next life (bLoopForEvaluation only)

namespace
{
const FName PEmblemGlow(TEXT("EmblemGlow")), PEmblemColor(TEXT("EmblemColor")), PSeamGlow(TEXT("SeamGlow")),
    PSeamColor(TEXT("SeamColor")), PGlowBoost(TEXT("GlowBoost")), PArcIntensity(TEXT("ArcIntensity")),
    PArcRate(TEXT("ArcRate")), PArcPatch(TEXT("ArcPatch")), PEmissiveIntensity(TEXT("EmissiveIntensity"));

float Gauss(float Phase, float Centre, float Width)
{
    float D = FMath::Abs(Phase - Centre);
    D = FMath::Min(D, 1.f - D); // circular: the beat phase wraps
    return FMath::Exp(-FMath::Square(D / Width));
}

float EaseOutBack(float X)
{
    const float C1 = 1.70158f, C3 = C1 + 1.f;
    X = FMath::Clamp(X, 0.f, 1.f);
    return 1.f + C3 * FMath::Pow(X - 1.f, 3.f) + C1 * FMath::Pow(X - 1.f, 2.f);
}

// Niagara pool size per role (SparkA, SparkB, Single, PopSparks, Smoke, Motes): single sparks fire up to ~3 a second
// at the top of the Nuke's warning (life <= 1.1 s) on top of the dribble; motes fire every 1.1 s and live up to 3.6 s.
constexpr int32 FxPoolSizes[] = {3, 3, 8, 4, 3, 5};

UStaticMeshComponent *MakeMesh(AActor *Owner, const TCHAR *Name, USceneComponent *Parent, bool bShadow)
{
    auto *C = Owner->CreateDefaultSubobject<UStaticMeshComponent>(Name);
    C->SetupAttachment(Parent);
    C->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    C->SetGenerateOverlapEvents(false);
    C->SetCanEverAffectNavigation(false);
    C->CastShadow = bShadow;
    C->bCastDynamicShadow = bShadow;
    C->bReceivesDecals = false;
    return C;
}

UPointLightComponent *MakeLight(AActor *Owner, const TCHAR *Name, USceneComponent *Parent)
{
    auto *L = Owner->CreateDefaultSubobject<UPointLightComponent>(Name);
    L->SetupAttachment(Parent);
    L->SetIntensityUnits(ELightUnits::Candelas);
    L->SetIntensity(0.f);
    L->SetCastShadows(false);
    L->bUseInverseSquaredFalloff = true;
    return L;
}
} // namespace

int32 AHoverPowerUpDisplay::FxNum(int32 Role)
{
    static_assert(UE_ARRAY_COUNT(FxPoolSizes) == FxRoleCount, "one pool size per Fx role");
    return FxPoolSizes[Role];
}

int32 AHoverPowerUpDisplay::FxFirst(int32 Role)
{
    int32 N = 0;
    for (int32 R = 0; R < Role; ++R)
        N += FxPoolSizes[R];
    return N;
}

AHoverPowerUpDisplay::AHoverPowerUpDisplay()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true;
    SetCanBeDamaged(false);

    Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
    SetRootComponent(Root);
    ItemPivot = CreateDefaultSubobject<USceneComponent>(TEXT("ItemPivot"));
    ItemPivot->SetupAttachment(Root);
    ItemMesh = MakeMesh(this, TEXT("ItemMesh"), ItemPivot, true);
    for (int32 I = 0; I < MaxShells; ++I)
    {
        auto *S = MakeMesh(this, *FString::Printf(TEXT("Shell%d"), I), ItemMesh, false);
        S->SetVisibility(false);
        S->TranslucencySortPriority = 1;
        S->SetBoundsScale(1.8f); // the shell material inflates the copy by up to ~15 cm (WPO)
        ShellMeshes.Add(S);
    }
    KeyLight = MakeLight(this, TEXT("KeyLight"), Root);

    NeonPivot = CreateDefaultSubobject<USceneComponent>(TEXT("NeonPivot"));
    NeonPivot->SetupAttachment(Root);
    NeonSign = MakeMesh(this, TEXT("NeonSign"), NeonPivot, false);
    NeonSign->SetVisibility(false);
    NeonLight = MakeLight(this, TEXT("NeonLight"), NeonPivot);

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Plane(TEXT("/Engine/BasicShapes/Plane.Plane"));
    PopPivot = CreateDefaultSubobject<USceneComponent>(TEXT("PopPivot"));
    PopPivot->SetupAttachment(ItemMesh);
    PopCore = MakeMesh(this, TEXT("PopCore"), PopPivot, false);
    PopGlow = MakeMesh(this, TEXT("PopGlow"), PopPivot, false);
    for (int32 I = 0; I < MaxRays; ++I)
        PopRays.Add(MakeMesh(this, *FString::Printf(TEXT("PopRay%d"), I), PopPivot, false));
    PopLight = MakeLight(this, TEXT("PopLight"), PopPivot);
    GlintPivot = CreateDefaultSubobject<USceneComponent>(TEXT("GlintPivot"));
    GlintPivot->SetupAttachment(ItemMesh);
    for (int32 I = 0; I < 3; ++I)
        GlintRays.Add(MakeMesh(this, *FString::Printf(TEXT("Glint%d"), I), GlintPivot, false));
    TArray<UStaticMeshComponent *> Planes = {PopCore, PopGlow};
    for (auto &R : PopRays)
        Planes.Add(R);
    for (auto &G : GlintRays)
        Planes.Add(G);
    for (auto *P : Planes)
    {
        if (Plane.Succeeded())
            P->SetStaticMesh(Plane.Object);
        P->SetVisibility(false);
        P->TranslucencySortPriority = 3;
    }

    static const TCHAR *RoleNames[] = {TEXT("SparkA"), TEXT("SparkB"), TEXT("Single"), TEXT("PopSparks"), TEXT("Smoke"),
                                       TEXT("Motes")};
    for (int32 R = 0; R < FxRoleCount; ++R)
        for (int32 I = 0; I < FxNum(R); ++I)
        {
            auto *F = CreateDefaultSubobject<UNiagaraComponent>(*FString::Printf(TEXT("Fx_%s_%d"), RoleNames[R], I));
            F->SetupAttachment(Root);
            F->SetAutoActivate(false);
            F->SetAutoDestroy(false);
            F->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            F->SetCanEverAffectNavigation(false);
            FxPool.Add(F);
        }

    LabelText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("Label"));
    LabelText->SetupAttachment(Root);
    LabelText->SetHorizontalAlignment(EHTA_Center);
    LabelText->SetVerticalAlignment(EVRTA_TextCenter);
    LabelText->SetTextRenderColor(FColor(225, 225, 215));
    LabelText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    LabelText->CastShadow = false;
    LabelText->SetVisibility(false);
}

void AHoverPowerUpDisplay::OnConstruction(const FTransform &Transform)
{
    Super::OnConstruction(Transform);
    if (Look && Look != InitedLook)
    {
        InitLook();
        RestartLife();
    }
    LabelText->SetText(Label);
    LabelText->SetWorldSize(LabelSizeCm);
    LabelText->SetRelativeLocation(FVector(0, 0, LabelHeightCm));
    LabelText->SetVisibility(bShowLabel);
}

void AHoverPowerUpDisplay::BeginPlay()
{
    Super::BeginPlay();
    // a fresh, visible first life whatever state the editor copy was saved or duplicated in
    LoopIndex = 0;
    Clock = 0.f;
    NeonStutterUntil = 0.f;
    NeonNextStutter = 1.f;
    InitLook();
    RestartLife();
}

void AHoverPowerUpDisplay::PreSave(FObjectPreSaveContext SaveContext)
{
#if WITH_EDITOR
    // Save the visible rest pose, never a mid-animation state (a save during the hidden respawn window used to keep
    // the item and the neon hidden). The editor tick carries on from the same life clock afterwards.
    if (ItemPivot && NeonPivot)
    {
        bHiddenPhase = false;
        ResetVisibility();
        ItemPivot->SetRelativeLocation(FVector(0, 0, Look ? Look->HoverCm : 30.f));
        ItemPivot->SetRelativeRotation(FRotator::ZeroRotator);
        ShudderOffset = ShudderFrom = ShudderTo = FVector::ZeroVector;
    }
#endif
    // The dynamic instances are transient: the saved level references the authored instances.
    ApplyMaterials(false);
    bMaterialsNeedReapply = true;
    Super::PreSave(SaveContext);
}

void AHoverPowerUpDisplay::ResetVisibility()
{
    ItemPivot->SetVisibility(true, true); // propagates; the parts that start hidden are switched off below
    NeonPivot->SetVisibility(true, true);
    ItemPivot->SetRelativeScale3D(FVector(1));
    for (int32 I = 0; I < ShellMeshes.Num(); ++I)
    {
        const bool bUsed = Look && I < Look->Shells.Num() && Look->Shells[I].Material && ShellMeshes[I]->GetStaticMesh();
        ShellMeshes[I]->SetVisibility(bUsed && Look->Shells[I].Role == EHoverPowerUpShellRole::Aura);
        ShellMeshes[I]->SetRelativeLocation(FVector::ZeroVector);
        ShellMeshes[I]->SetRelativeScale3D(FVector(1));
    }
    PopCore->SetVisibility(false);
    PopGlow->SetVisibility(false);
    for (auto &R : PopRays)
        R->SetVisibility(false);
    for (auto &G : GlintRays)
        G->SetVisibility(false);
    NeonSign->SetVisibility(NeonSign->GetStaticMesh() != nullptr);
    NeonPivot->SetRelativeScale3D(FVector(Look ? Look->NeonScale : 1.f));
}

void AHoverPowerUpDisplay::RestartLife()
{
    LifeTime = 0.f;
    // always (not only when bHiddenPhase says so: that flag is not saved or duplicated with the components)
    bHiddenPhase = false;
    ResetVisibility();
    TickFlash = GlintFlash = LightKick = WarnAmount = BeatPhase = DischargeFlash = 0.f;
    ShudderOffset = ShudderFrom = ShudderTo = FVector::ZeroVector;
    ShudderPhase = 0.f;
    PopAge = EchoAge = 100.f;
    NextMoteBurst = 0.f;
    LiveRng.Initialize(Seed * 7919 + LoopIndex * 104729 + 3);
    BuildSchedule();
}

void AHoverPowerUpDisplay::InitLook()
{
    InitedLook = Look;
    ShellDMIs.Reset();
    ItemDMI = NeonLitDMI = NeonDeadDMI = PopCoreDMI = PopGlowDMI = PopRayDMI = GlintDMI = nullptr;
    if (!Look)
        return;
    auto MakeDMI = [this](UMaterialInterface *M) -> UMaterialInstanceDynamic * {
        if (!M)
            return nullptr;
        auto *D = UMaterialInstanceDynamic::Create(M, this);
        D->SetFlags(RF_Transient);
        return D;
    };
    ItemMesh->SetStaticMesh(Look->ItemMesh);
    ItemMesh->SetRelativeScale3D(FVector(Look->ItemScale));
    ItemBounds = Look->ItemMesh ? Look->ItemMesh->GetBoundingBox() : FBox(FVector(-15), FVector(15, 15, 45));
    ItemDMI = MakeDMI(Look->ItemMaterial);
    if (ItemDMI)
    {
        BaseEmblemGlow = ItemDMI->K2_GetScalarParameterValue(PEmblemGlow);
        BaseSeamGlow = ItemDMI->K2_GetScalarParameterValue(PSeamGlow);
        BaseArcPatch = ItemDMI->K2_GetScalarParameterValue(PArcPatch);
        BaseEmblemColor = ItemDMI->K2_GetVectorParameterValue(PEmblemColor);
        BaseSeamColor = ItemDMI->K2_GetVectorParameterValue(PSeamColor);
    }
    for (int32 I = 0; I < MaxShells; ++I)
    {
        const bool bUsed = I < Look->Shells.Num() && Look->Shells[I].Material && Look->ItemMesh;
        ShellMeshes[I]->SetStaticMesh(bUsed ? Look->ItemMesh.Get() : nullptr);
        ShellMeshes[I]->SetVisibility(bUsed && Look->Shells[I].Role == EHoverPowerUpShellRole::Aura);
        ShellMeshes[I]->SetRelativeLocation(FVector::ZeroVector);
        ShellMeshes[I]->SetRelativeScale3D(FVector(1));
        ShellDMIs.Add(bUsed ? MakeDMI(Look->Shells[I].Material) : nullptr);
    }
    NeonSign->SetStaticMesh(Look->NeonMesh);
    NeonSign->SetVisibility(Look->NeonMesh != nullptr);
    NeonLitDMI = MakeDMI(Look->NeonLitMaterial);
    NeonDeadDMI = MakeDMI(Look->NeonDeadMaterial);
    PopCoreDMI = MakeDMI(Look->PopCoreMaterial);
    PopGlowDMI = MakeDMI(Look->PopGlowMaterial);
    PopRayDMI = MakeDMI(Look->PopRayMaterial);
    GlintDMI = MakeDMI(Look->PopRayMaterial);
    UNiagaraSystem *Systems[FxRoleCount] = {Look->SparkBurstA, Look->SparkBurstB, Look->SparkSingle,
                                            Look->PopSparks,   Look->PopSmoke,    Look->MoteSystem};
    for (int32 R = 0; R < FxRoleCount; ++R)
        for (int32 I = 0; I < FxNum(R); ++I)
        {
            UNiagaraComponent *F = FxPool.IsValidIndex(FxFirst(R) + I) ? FxPool[FxFirst(R) + I].Get() : nullptr;
            if (!F)
                continue;
            if (F->GetAsset() != Systems[R])
                F->SetAsset(Systems[R]);
            F->Deactivate();
        }
    ApplyMaterials(true);
}

void AHoverPowerUpDisplay::ApplyMaterials(bool bDynamic)
{
    bMaterialsNeedReapply = false;
    if (!Look)
        return;
    auto Set = [](UStaticMeshComponent *C, UMaterialInterface *M) {
        if (C && M && C->GetStaticMesh())
            for (int32 I = 0; I < C->GetNumMaterials(); ++I)
                C->SetMaterial(I, M);
    };
    auto Pick = [bDynamic](UMaterialInstanceDynamic *D, UMaterialInterface *Base) -> UMaterialInterface * {
        return bDynamic && D ? static_cast<UMaterialInterface *>(D) : Base;
    };
    Set(ItemMesh, Pick(ItemDMI, Look->ItemMaterial));
    for (int32 I = 0; I < MaxShells && I < ShellDMIs.Num(); ++I)
        Set(ShellMeshes[I], Pick(ShellDMIs[I], I < Look->Shells.Num() ? Look->Shells[I].Material.Get() : nullptr));
    if (NeonSign->GetStaticMesh())
    {
        // slots by name (the neon props have Lit / Dead / Frame); unknown slots take the frame
        for (int32 I = 0; I < NeonSign->GetNumMaterials(); ++I)
        {
            const FString Slot = NeonSign->GetMaterialSlotNames().IsValidIndex(I) ? NeonSign->GetMaterialSlotNames()[I].ToString() : FString();
            UMaterialInterface *M = Look->NeonFrameMaterial;
            if (Slot.Contains(TEXT("Lit")))
                M = Pick(NeonLitDMI, Look->NeonLitMaterial);
            else if (Slot.Contains(TEXT("Dead")))
                M = Pick(NeonDeadDMI, Look->NeonDeadMaterial);
            if (M)
                NeonSign->SetMaterial(I, M);
        }
    }
    Set(PopCore, Pick(PopCoreDMI, Look->PopCoreMaterial));
    Set(PopGlow, Pick(PopGlowDMI, Look->PopGlowMaterial));
    for (UStaticMeshComponent *R : PopRays)
        Set(R, Pick(PopRayDMI, Look->PopRayMaterial));
    for (UStaticMeshComponent *G : GlintRays)
        Set(G, Pick(GlintDMI, Look->PopRayMaterial));
}

void AHoverPowerUpDisplay::BuildSchedule()
{
    Schedule.Reset();
    if (!Look)
        return;
    FRandomStream Rng(Seed * 7919 + LoopIndex * 104729);
    const float Life = Look->LifeSeconds;
    if (Look->bGeigerTicks)
        for (float T = .6f + Rng.FRand() * .6f; T < Life;)
        {
            const bool bTriple = Rng.FRand() < Look->TickTripleChance;
            for (int32 K = 0; K < (bTriple ? 3 : 1); ++K)
            {
                FHoverPowerUpEvent E;
                E.Time = T + K * Look->TickTripleGap * (1.f + .25f * (Rng.FRand() - .5f));
                E.Kind = 0;
                E.Count = bTriple ? 3 : 1;
                Schedule.Add(E);
            }
            const float Gap = -FMath::Loge(FMath::Max(Rng.FRand(), 1e-3f)) * Look->TickMeanInterval;
            T += FMath::Clamp(Gap, Look->TickMinInterval, Look->TickMaxInterval) + (bTriple ? 2.f * Look->TickTripleGap : 0.f);
        }
    TArray<float> MainTimes;
    const bool bSparks = Look->bSparkBursts && (Look->SparkBurstA || Look->SparkBurstB);
    const bool bPops = Look->bPops;
    if (bSparks || bPops)
    {
        int32 N = 0;
        for (float T = Look->FirstEventSeconds; T < Life - .3f;
             T += Rng.FRandRange(Look->EventIntervalMin, Look->EventIntervalMax), ++N)
        {
            FHoverPowerUpEvent E;
            E.Time = T;
            E.Kind = bSparks && bPops ? (N % 2 == 0 ? 1 : 2) : (bSparks ? 1 : 2);
            if (E.Kind == 1)
            {
                const float R = Rng.FRand();
                E.Count = R < Look->SparkBothChance ? 13 : (R < .5f + Look->SparkBothChance * .5f ? 6 : 7);
            }
            else
                E.Count = Rng.FRand() < .5f ? 3 : 6;
            Schedule.Add(E);
            MainTimes.Add(T);
        }
    }
    if (Look->SparkSingle && Look->DribbleMeanInterval > 0.f)
        for (float T = .9f; T < Life - .2f;
             T += FMath::Clamp(-FMath::Loge(FMath::Max(Rng.FRand(), 1e-3f)) * Look->DribbleMeanInterval, .35f, 4.f))
        {
            bool bNear = false;
            for (float M : MainTimes)
                bNear |= FMath::Abs(M - T) < .45f;
            if (bNear)
                continue;
            FHoverPowerUpEvent E;
            E.Time = T;
            E.Kind = 3;
            E.Count = 1;
            Schedule.Add(E);
        }
    Schedule.Sort([](const FHoverPowerUpEvent &A, const FHoverPowerUpEvent &B) { return A.Time < B.Time; });
}

float AHoverPowerUpDisplay::Hash(float X) const
{
    return FMath::Frac(FMath::Sin(X * 12.9898f) * 43758.5453f);
}

bool AHoverPowerUpDisplay::GetViewLocation(FVector &Out) const
{
    const UWorld *W = GetWorld();
    if (!W)
        return false;
    if (W->IsGameWorld())
        if (const APlayerController *PC = W->GetFirstPlayerController())
        {
            FRotator R;
            PC->GetPlayerViewPoint(Out, R);
            return true;
        }
#if WITH_EDITOR
    if (!W->IsGameWorld() && GCurrentLevelEditingViewportClient)
    {
        Out = GCurrentLevelEditingViewportClient->GetViewLocation();
        return true;
    }
#endif
    if (W->ViewLocationsRenderedLastFrame.Num() > 0)
    {
        Out = W->ViewLocationsRenderedLastFrame[0];
        return true;
    }
    return false;
}

FVector AHoverPowerUpDisplay::RandomCasingPoint(FRandomStream &Rng, bool bAllowCap) const
{
    const FVector C = ItemBounds.GetCenter(), Ext = ItemBounds.GetExtent();
    // bias toward the side the viewer sees (mesh space)
    float ViewAngle = Rng.FRand() * 360.f;
    FVector Cam;
    if (GetViewLocation(Cam))
    {
        const FVector L = ItemMesh->GetComponentTransform().InverseTransformPosition(Cam);
        ViewAngle = FMath::RadiansToDegrees(FMath::Atan2(L.Y - C.Y, L.X - C.X));
    }
    if (Look->CasingPoints.Num() > 0)
    {
        // AFS 2026-11-03: a random authored point on the side the viewer sees (within 75 deg, as the bounds rings
        // below; the old best-of-three pick put about one burst in eight behind the item), the cap only if allowed
        const FVector2D V(FMath::Cos(FMath::DegreesToRadians(ViewAngle)), FMath::Sin(FMath::DegreesToRadians(ViewAngle)));
        const float MinDot = FMath::Cos(FMath::DegreesToRadians(75.f));
        TArray<int32, TInlineAllocator<128>> Near;
        for (int32 I = 0; I < Look->CasingPoints.Num(); ++I)
        {
            const FVector &P = Look->CasingPoints[I];
            if (!bAllowCap && P.Z > ItemBounds.Max.Z - 1.f)
                continue;
            if (FVector2D::DotProduct(FVector2D(P.X - C.X, P.Y - C.Y).GetSafeNormal(), V) >= MinDot)
                Near.Add(I);
        }
        return Look->CasingPoints[Near.Num() ? Near[Rng.RandRange(0, Near.Num() - 1)]
                                             : Rng.RandRange(0, Look->CasingPoints.Num() - 1)];
    }
    const float Radius = FMath::Min(Ext.X, Ext.Y) * .92f;
    if (bAllowCap && Rng.FRand() < .3f)
    {
        const float A = Rng.FRand() * UE_TWO_PI, R = Radius * .45f * FMath::Sqrt(Rng.FRand());
        return FVector(C.X + R * FMath::Cos(A), C.Y + R * FMath::Sin(A), ItemBounds.Max.Z - .5f);
    }
    const TArray<float> &Fr = Look->SeamHeightFractions;
    const float H = Fr.Num() ? Fr[Rng.RandRange(0, Fr.Num() - 1)] : Rng.FRandRange(.2f, .85f);
    const float A = FMath::DegreesToRadians(ViewAngle + Rng.FRandRange(-75.f, 75.f));
    return FVector(C.X + Radius * FMath::Cos(A), C.Y + Radius * FMath::Sin(A),
                   FMath::Lerp(ItemBounds.Min.Z, ItemBounds.Max.Z, H));
}

FVector AHoverPowerUpDisplay::CasingNormal(const FVector &P) const
{
    const FVector C = ItemBounds.GetCenter();
    if (P.Z > ItemBounds.Max.Z - 1.f)
        return FVector::UpVector;
    return FVector(P.X - C.X, P.Y - C.Y, 0.f).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
}

void AHoverPowerUpDisplay::FireFx(EFx FxRole, const FVector &WorldLoc, const FVector &WorldDir)
{
    const int32 Index = FxFirst(FxRole) + FxNext[FxRole];
    FxNext[FxRole] = (FxNext[FxRole] + 1) % FxNum(FxRole);
    UNiagaraComponent *F = FxPool.IsValidIndex(Index) ? FxPool[Index].Get() : nullptr;
    if (!F || !F->GetAsset())
        return;
    F->SetWorldLocationAndRotation(WorldLoc, FRotationMatrix::MakeFromZ(WorldDir).Rotator());
    F->Activate(true);
}

void AHoverPowerUpDisplay::FireEvent(FHoverPowerUpEvent &E)
{
    const FTransform &XF = ItemMesh->GetComponentTransform();
    auto Out = [&](const FVector &Local) {
        const FVector N = XF.TransformVectorNoScale(CasingNormal(Local));
        return (N + FVector::UpVector * .7f).GetSafeNormal();
    };
    switch (E.Kind)
    {
    case 0: // Geiger tick
    {
        TickFlash = 1.f;
        GlintFlash = 1.f;
        GlintRoll = LiveRng.FRand() * 90.f;
        const FVector P = RandomCasingPoint(LiveRng, false);
        GlintPivot->SetRelativeLocation(P + CasingNormal(P) * .6f);
        LightKick += Look->TickLightKick;
        break;
    }
    case 1: // N1 spark burst
    {
        const FVector P = RandomCasingPoint(LiveRng, true);
        E.Point = P;
        const FVector W = XF.TransformPosition(P), D = Out(P);
        if (E.Count != 7)
            FireFx(FxSparkA, W, D);
        if (E.Count != 6)
            FireFx(FxSparkB, W, (D + FMath::VRand() * .25f).GetSafeNormal());
        LightKick += Look->SparkLightKick * (E.Count > 7 ? 1.5f : 1.f);
        break;
    }
    case 2: // N2 pop
    {
        if (!Look->bPops)
            break;
        const FVector P = RandomCasingPoint(LiveRng, true);
        E.Point = P;
        PopPivot->SetRelativeLocation(P + CasingNormal(P) * 1.f);
        PopAge = 0.f;
        PopRayCount = LiveRng.RandRange(FMath::Clamp(Look->PopRaysMin, 1, MaxRays), FMath::Clamp(Look->PopRaysMax, 1, MaxRays));
        const float Start = LiveRng.FRand() * 360.f;
        for (int32 I = 0; I < PopRayCount; ++I)
        {
            PopRayRolls[I] = Start + I * 360.f / PopRayCount + LiveRng.FRandRange(-14.f, 14.f);
            PopRayLens[I] = Look->PopRayLengthCm * LiveRng.FRandRange(.55f, 1.15f);
        }
        JoltDir = -XF.TransformVectorNoScale(CasingNormal(P));
        const FVector W = XF.TransformPosition(P), D = Out(P);
        FireFx(FxPopSparks, W, D);
        if (E.Count > 3)
            FireFx(FxPopSparks, W, (D + FMath::VRand() * .35f).GetSafeNormal());
        FireFx(FxSmoke, W + D * Look->PopSmokeOffsetCm, FVector::UpVector);
        break;
    }
    case 3: // single-spark dribble
    {
        const FVector P = RandomCasingPoint(LiveRng, true);
        FireFx(FxSingle, XF.TransformPosition(P), Out(P));
        break;
    }
    default:
        break;
    }
}

void AHoverPowerUpDisplay::FaceCamera(USceneComponent *Plane, const FVector &CamLoc, float RollDeg, const FVector &Scale)
{
    const FVector Dir = (CamLoc - Plane->GetComponentLocation()).GetSafeNormal(UE_SMALL_NUMBER, FVector::ForwardVector);
    const FQuat Q = FQuat(Dir, FMath::DegreesToRadians(RollDeg)) * FRotationMatrix::MakeFromZ(Dir).ToQuat();
    Plane->SetWorldRotation(Q);
    Plane->SetWorldScale3D(Scale);
}

void AHoverPowerUpDisplay::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!Look)
        return;
    if (Look != InitedLook)
    {
        InitLook();
        RestartLife();
    }
    if (bMaterialsNeedReapply)
        ApplyMaterials(true);
    UpdateAnimation(FMath::Min(DeltaSeconds, .1f));
}

void AHoverPowerUpDisplay::UpdateAnimation(float Dt)
{
    const UHoverPowerUpLook &L = *Look;
    Clock += Dt;
    LifeTime += Dt;
    const float Life = L.LifeSeconds, Fade = FMath::Max(L.FadeOutSeconds, .01f);
    if (LifeTime >= Life + Fade)
    {
        if (!bHiddenPhase)
        {
            bHiddenPhase = true;
            ItemPivot->SetVisibility(false, true);
            NeonPivot->SetVisibility(false, true);
            KeyLight->SetIntensity(0.f);
            NeonLight->SetIntensity(0.f);
            PopLight->SetIntensity(0.f);
        }
        if (bLoopForEvaluation && LifeTime >= Life + Fade + L.RespawnDelaySeconds)
        {
            ++LoopIndex;
            RestartLife();
        }
        return;
    }

    // ---- life envelope
    float LifeScale = 1.f, LifeGlow = 1.f;
    if (LifeTime < L.SpawnInSeconds)
    {
        const float X = LifeTime / FMath::Max(L.SpawnInSeconds, .01f);
        LifeScale = FMath::Max(EaseOutBack(X), .01f);
        LifeGlow = X;
    }
    else if (LifeTime > Life)
    {
        const float X = FMath::Clamp((LifeTime - Life) / Fade, 0.f, 1.f);
        LifeScale = FMath::Max(1.f - X * X, .01f);
        LifeGlow = 1.f - X;
    }

    // ---- scheduled events (an editor hitch skips events older than half a second instead of firing a pile)
    for (FHoverPowerUpEvent &E : Schedule)
    {
        if (E.Time > LifeTime)
            break;
        if (!E.bFired)
        {
            E.bFired = true;
            if (LifeTime - E.Time < .5f)
                FireEvent(E);
        }
    }

    // ---- warning (last WarningSeconds): heartbeat, and the arc crawl for the Nuke
    float Beat = 0.f, Progress = 0.f;
    const float WarnStart = Life - L.WarningSeconds;
    if (L.Warning != EHoverPowerUpWarning::None && LifeTime > WarnStart)
    {
        Progress = FMath::Clamp((LifeTime - WarnStart) / FMath::Max(L.WarningSeconds, .01f), 0.f, 1.f);
        WarnAmount = FMath::SmoothStep(0.f, FMath::Max(L.WarningEaseInSeconds, .01f), LifeTime - WarnStart);
        BeatHz = FMath::Lerp(L.BeatHzStart, L.BeatHzEnd, FMath::Pow(Progress, FMath::Max(L.BeatAccelPower, .05f)));
        const float Prev = BeatPhase;
        BeatPhase = FMath::Frac(BeatPhase + Dt * BeatHz);
        if ((Prev < .06f && BeatPhase >= .06f) || (BeatPhase < Prev && BeatPhase >= .06f))
            EchoAge = 0.f;
        Beat = Gauss(BeatPhase, .06f, .045f) + L.BeatDubStrength * Gauss(BeatPhase, .30f, .05f);
    }
    else
    {
        WarnAmount = 0.f;
        BeatHz = 0.f;
    }
    const bool bArcs = L.Warning == EHoverPowerUpWarning::HeartbeatAndArcs && WarnAmount > 0.f;
    if (bArcs)
    {
        const float Rate = FMath::Lerp(L.DischargeRateStart, L.DischargeRateEnd, Progress) * WarnAmount;
        if (LiveRng.FRand() < Rate * Dt)
        {
            DischargeFlash = 1.f;
            if (L.SparkSingle && LiveRng.FRand() < L.DischargeSparkChance)
            {
                FHoverPowerUpEvent E;
                E.Kind = 3;
                FireEvent(E);
            }
        }
    }
    DischargeFlash *= FMath::Exp(-Dt / .05f);

    // ---- decays
    TickFlash *= FMath::Exp(-Dt / FMath::Max(L.TickFlashSeconds, .01f));
    GlintFlash *= FMath::Exp(-Dt / FMath::Max(L.TickFlashSeconds * 1.4f, .01f));
    LightKick *= FMath::Exp(-Dt / .08f);
    PopAge += Dt;
    EchoAge += Dt;

    // ---- item: hover, bob, spin, shudder, jolt, heartbeat swell
    // shudder: a new random target TickShudderHz times a second, glided between (the same at any frame rate)
    ShudderPhase += Dt * FMath::Max(L.TickShudderHz, 1.f);
    while (ShudderPhase >= 1.f)
    {
        ShudderPhase -= 1.f;
        ShudderFrom = ShudderTo;
        ShudderTo = LiveRng.GetUnitVector() * FVector(1, 1, .5);
    }
    ShudderOffset = TickFlash > .02f ? FMath::Lerp(ShudderFrom, ShudderTo, ShudderPhase) * L.TickShudderCm * TickFlash
                                     : FVector::ZeroVector;
    const FVector Jolt = PopAge < 1.f ? JoltDir * L.PopJoltCm * FMath::Exp(-PopAge / FMath::Max(L.PopJoltSeconds, .01f)) : FVector::ZeroVector;
    const float Bob = L.BobCm * FMath::Sin(UE_TWO_PI * L.BobHz * Clock);
    // swell (and the spawn / fade scale) about the item's centre, not its base
    const float Swell = 1.f + L.BeatSwell * WarnAmount * Beat;
    const float S = LifeScale * Swell;
    const float CentreZ = ItemBounds.GetCenter().Z * L.ItemScale;
    ItemPivot->SetRelativeLocation(FVector(0, 0, L.HoverCm + Bob + CentreZ * (1.f - S)) + ShudderOffset + Jolt);
    ItemPivot->SetRelativeRotation(FRotator(0.f, FMath::Fmod(Clock * L.SpinDegPerSec, 360.f), 0.f));
    ItemPivot->SetRelativeScale3D(FVector(S));

    // ---- item skin
    const float Glow = LifeGlow * (1.f + L.BeatGlowFlash * WarnAmount * Beat);
    if (ItemDMI)
    {
        ItemDMI->SetScalarParameterValue(PGlowBoost, Glow);
        if (L.bGeigerTicks)
        {
            // GlowBoost multiplies the whole skin emission: a tick landing on a heartbeat flash is held under the caps
            // so the two cannot stack to white (the tick's share shrinks, the trefoil stays readable)
            auto Capped = [Glow](float Base, float Add, float Max) {
                return Max > 0.f ? FMath::Min(Add, FMath::Max(Max / FMath::Max(Glow, .01f) - Base, 0.f)) : Add;
            };
            const float EmblemAdd = Capped(BaseEmblemGlow, L.TickEmblemGlow * TickFlash, L.FlashEmblemGlowMax);
            const float SeamAdd = Capped(BaseSeamGlow, L.TickSeamGlow * TickFlash, L.FlashSeamGlowMax);
            const float Share = L.TickEmblemGlow * TickFlash > 1e-3f ? EmblemAdd / (L.TickEmblemGlow * TickFlash) : 1.f;
            const float T = FMath::Min(TickFlash * 1.2f, 1.f) * Share;
            ItemDMI->SetScalarParameterValue(PEmblemGlow, BaseEmblemGlow + EmblemAdd);
            ItemDMI->SetScalarParameterValue(PSeamGlow, BaseSeamGlow + SeamAdd);
            ItemDMI->SetVectorParameterValue(PEmblemColor, FMath::Lerp(BaseEmblemColor, L.TickWhiteHot, T));
            ItemDMI->SetVectorParameterValue(PSeamColor, FMath::Lerp(BaseSeamColor, L.TickWhiteHot, T));
        }
        if (L.Warning == EHoverPowerUpWarning::HeartbeatAndArcs)
        {
            ItemDMI->SetScalarParameterValue(PArcIntensity, WarnAmount * L.ArcSkinIntensity * (.55f + .9f * DischargeFlash));
            ItemDMI->SetScalarParameterValue(PArcRate, FMath::Lerp(L.ArcRateStart, L.ArcRateEnd, Progress));
            ItemDMI->SetScalarParameterValue(PArcPatch, FMath::Lerp(L.ArcPatchStart, L.ArcPatchEnd, Progress));
        }
    }

    // ---- shells
    for (int32 I = 0; I < ShellDMIs.Num() && I < L.Shells.Num(); ++I)
    {
        UMaterialInstanceDynamic *D = ShellDMIs[I];
        UStaticMeshComponent *Sh = ShellMeshes[I];
        if (!D)
            continue;
        switch (L.Shells[I].Role)
        {
        case EHoverPowerUpShellRole::Aura:
            D->SetScalarParameterValue(PGlowBoost, Glow);
            break;
        case EHoverPowerUpShellRole::ArcCrawl:
            Sh->SetVisibility(bArcs);
            if (bArcs)
            {
                D->SetScalarParameterValue(PArcIntensity, WarnAmount * L.ArcShellIntensity * (.5f + 1.f * DischargeFlash));
                D->SetScalarParameterValue(PArcRate, FMath::Lerp(L.ArcRateStart, L.ArcRateEnd, Progress) * .8f);
                D->SetScalarParameterValue(PArcPatch, FMath::Lerp(L.ArcPatchStart, L.ArcPatchEnd, Progress) - .05f);
                D->SetScalarParameterValue(PGlowBoost, LifeGlow);
            }
            break;
        case EHoverPowerUpShellRole::HeartbeatEcho:
        {
            const float X = EchoAge / FMath::Max(L.EchoSeconds, .01f);
            const bool bOn = WarnAmount > 0.f && X < 1.f;
            Sh->SetVisibility(bOn);
            if (bOn)
            {
                const float K = FMath::Lerp(1.f, L.EchoMaxScale, FMath::Sqrt(X));
                Sh->SetRelativeScale3D(FVector(K));
                Sh->SetRelativeLocation(ItemBounds.GetCenter() * (1.f - K));
                D->SetScalarParameterValue(PGlowBoost, WarnAmount * LifeGlow * FMath::Square(1.f - X));
            }
            break;
        }
        }
    }

    // ---- camera-facing parts
    FVector Cam;
    const bool bCam = GetViewLocation(Cam);
    // Geiger glint: a small four-point star at a seam
    const bool bGlint = GlintFlash > .03f && GlintDMI != nullptr && bCam;
    for (int32 I = 0; I < GlintRays.Num(); ++I)
    {
        GlintRays[I]->SetVisibility(bGlint);
        if (bGlint)
        {
            const float GS = L.GlintSizeCm * (I == 2 ? .45f : 1.f) / 100.f;
            FaceCamera(GlintRays[I], Cam, GlintRoll + I * 90.f, I == 2 ? FVector(GS, GS, 1) : FVector(GS, GS * .14f, 1));
        }
    }
    if (bGlint)
        GlintDMI->SetScalarParameterValue(PGlowBoost, GlintFlash * L.GlintIntensity * LifeGlow);
    // N2 pop: core, blast glow, rays, light
    const bool bPop = PopAge < .8f && bCam;
    PopCore->SetVisibility(bPop && PopCoreDMI != nullptr);
    PopGlow->SetVisibility(bPop && PopGlowDMI != nullptr);
    for (int32 I = 0; I < MaxRays; ++I)
        PopRays[I]->SetVisibility(bPop && PopRayDMI != nullptr && I < PopRayCount);
    if (bPop)
    {
        const float Core = FMath::Exp(-PopAge / FMath::Max(L.PopCoreSeconds, .005f));
        const float GlowE = FMath::Exp(-PopAge / FMath::Max(L.PopGlowSeconds, .005f)) * FMath::Min(PopAge / .015f + .3f, 1.f);
        const float RayE = FMath::Exp(-PopAge / FMath::Max(L.PopRaySeconds, .005f));
        const float CoreS = L.PopCoreCm * (1.f + PopAge * 6.f) / 100.f;
        const float GlowS = L.PopGlowCm * (.7f + .6f * FMath::Min(PopAge / .15f, 1.f)) / 100.f;
        FaceCamera(PopCore, Cam, 0.f, FVector(CoreS, CoreS, 1));
        FaceCamera(PopGlow, Cam, 0.f, FVector(GlowS, GlowS, 1));
        if (PopCoreDMI)
            PopCoreDMI->SetScalarParameterValue(PGlowBoost, Core);
        if (PopGlowDMI)
            PopGlowDMI->SetScalarParameterValue(PGlowBoost, GlowE);
        if (PopRayDMI)
            PopRayDMI->SetScalarParameterValue(PGlowBoost, RayE);
        const FVector C = PopPivot->GetComponentLocation();
        for (int32 I = 0; I < PopRayCount; ++I)
        {
            const float Len = PopRayLens[I] * (.6f + .8f * FMath::Min(PopAge / .1f, 1.f));
            FaceCamera(PopRays[I], Cam, PopRayRolls[I], FVector(Len / 100.f, L.PopRayWidthCm / 100.f, 1));
            PopRays[I]->SetWorldLocation(C + PopRays[I]->GetComponentQuat().GetAxisX() * Len * .32f);
        }
        PopLight->SetLightColor(L.PopLightColor);
        PopLight->SetAttenuationRadius(L.PopLightRadius);
        PopLight->SetIntensity(L.PopLightIntensity * FMath::Exp(-PopAge / .08f) * LifeGlow);
    }
    else
        PopLight->SetIntensity(0.f);

    // ---- key light
    {
        const float Pulse = 1.f + L.KeyLightPulseAmount * FMath::Sin(UE_TWO_PI * L.KeyLightPulseHz * Clock);
        // AFS 2026-11-03: a scaled item keeps its key light outside the casing (offset x ItemScale; at 1x the doubled
        // Nuke had the light 6 cm inside its 32 cm half-width) and lit (intensity x ItemScale for the doubled distance)
        const float K = FMath::Max(L.ItemScale, .01f);
        const float I = (L.KeyLightIntensity * LifeGlow * Pulse + LightKick + L.BeatLightKick * WarnAmount * Beat +
                         L.DischargeLightKick * DischargeFlash * LifeGlow) * K;
        KeyLight->SetRelativeLocation(FVector(0, 0, L.HoverCm) + L.KeyLightOffset * K);
        KeyLight->SetAttenuationRadius(L.KeyLightRadius * K);
        KeyLight->SetLightColor(FMath::Lerp(L.KeyLightColor, L.DischargeLightColor, FMath::Min(DischargeFlash, 1.f)));
        KeyLight->SetIntensity(I);
    }

    // ---- neon icon: yaw to the viewer, bob, lit-tube buzz, dead-tube stutter, buzzing light
    if (NeonSign->GetStaticMesh())
    {
        const float NB = L.NeonBobCm * FMath::Sin(UE_TWO_PI * L.NeonBobHz * Clock + 1.3f);
        NeonPivot->SetRelativeLocation(FVector(0, 0, L.HoverCm + L.NeonHeightCm + NB));
        if (bCam)
        {
            const FVector P = NeonPivot->GetComponentLocation();
            // the neon props face mesh +Y
            const float Yaw = FMath::RadiansToDegrees(FMath::Atan2(Cam.Y - P.Y, Cam.X - P.X)) - 90.f;
            NeonPivot->SetWorldRotation(FRotator(0.f, Yaw, 0.f));
        }
        NeonPivot->SetRelativeScale3D(FVector(L.NeonScale * LifeScale));
        const float Buzz = 1.f - L.NeonBuzzAmount * Hash(FMath::FloorToFloat(Clock * L.NeonBuzzRate));
        if (Clock >= NeonNextStutter)
        {
            NeonStutterUntil = Clock + LiveRng.FRandRange(L.NeonStutterBurstMin, L.NeonStutterBurstMax);
            NeonNextStutter = NeonStutterUntil + LiveRng.FRandRange(L.NeonStutterGapMin, L.NeonStutterGapMax);
        }
        const bool bDeadOn = Clock < NeonStutterUntil && Hash(FMath::FloorToFloat(Clock * L.NeonStutterHz) + 17.f) > .45f;
        const float Dead = bDeadOn ? L.NeonDeadOnIntensity : L.NeonDeadOffIntensity;
        if (NeonLitDMI)
            NeonLitDMI->SetScalarParameterValue(PEmissiveIntensity, L.NeonLitIntensity * Buzz * LifeGlow);
        if (NeonDeadDMI)
            NeonDeadDMI->SetScalarParameterValue(PEmissiveIntensity, Dead * LifeGlow);
        NeonLight->SetRelativeLocation(L.NeonLightOffset);
        NeonLight->SetAttenuationRadius(L.NeonLightRadius);
        NeonLight->SetLightColor(L.NeonLightColor);
        NeonLight->SetIntensity(L.NeonLightIntensity * LifeGlow *
                                (.8f * Buzz + .2f * Dead / FMath::Max(L.NeonDeadOnIntensity, .01f)));
    }

    // ---- motes: one Niagara burst every MoteBurstInterval, overlapping into a drift
    if (L.MoteSystem && LifeTime >= NextMoteBurst && LifeTime < Life)
    {
        NextMoteBurst = LifeTime + L.MoteBurstInterval;
        FireFx(FxMotes, ItemMesh->GetComponentTransform().TransformPosition(L.MoteOffset), FVector::UpVector); // x ItemScale
    }

    // ---- evaluation label
    if (bShowLabel && bCam)
    {
        const FVector P = LabelText->GetComponentLocation();
        LabelText->SetWorldRotation(FRotator(0.f, FMath::RadiansToDegrees(FMath::Atan2(Cam.Y - P.Y, Cam.X - P.X)), 0.f));
    }
}
