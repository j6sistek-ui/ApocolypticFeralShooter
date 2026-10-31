#pragma once
#include "CoreMinimal.h"
#include "HoverCyberCity.h"
#include "HoverAttackSlots.h"
#include "BehaviorTree/Tasks/BTTask_MoveTo.h"
#include "Zombies/ZE_BTService_CheckAttackRange.h"
#include "Zombies/ZE_BTTask_ZombieAttack.h"
#include "HoverNYCZombie.generated.h"

// Per-instance variation rolled once per zombie (design Section 4 §5 item 4). Bosses use half
// of each range. Rolled lazily so the controller can read it in OnPossess, before BeginPlay.
USTRUCT(BlueprintType)
struct FHoverNYCJitter
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) float Speed = 1.f;
    UPROPERTY(BlueprintReadOnly) float Accel = 1.f;
    UPROPERTY(BlueprintReadOnly) float Yaw = 1.f;
    UPROPERTY(BlueprintReadOnly) float Cooldown = 0.f;
    UPROPERTY(BlueprintReadOnly) float Separation = 1.f;
    UPROPERTY(BlueprintReadOnly) float LateralBias = 0.f;
    UPROPERTY(BlueprintReadOnly) float Acceptance = 1.f;
    bool bRolled = false;
};

// NYC Survival zombie. Opt-in only: AHoverNYCSurvivalGameMode makes it the wave zombie class;
// Cyber City, Lakeside, PostApo and NYC Exploration never spawn it. It keeps the vendor
// death, loot and hit montages, and adds attack tokens, cadence jitter and the flinch rule
// without editing the purchased plugin (the design's zero-edit route, §9).
UCLASS()
class HOVERFLIGHT_API AHoverNYCZombie : public AHoverCyberZombie
{
    GENERATED_BODY()
  public:
    AHoverNYCZombie();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void PerformAttack(AActor *Target) override;
    virtual float TakeDamage(float Damage, const FDamageEvent &Event, AController *EventController,
                             AActor *Causer) override;

    const FHoverNYCJitter &GetJitter() const;
    const UHoverCyberZombieDefinition *GetNYCDefinition() const;
    // Brute and Boss roles, or a definition with bHeavySlot: at most two hold inner sectors.
    bool IsHeavySlot() const;
    // EHoverZombieRole::Boss once the role enum carries it (matched by name, so this compiles
    // before and after the enum is extended).
    bool IsBoss() const;
    // True while the running tree is the unmodified vendor BT_Zombie (no AttackSlotLocation key).
    bool IsUsingVendorTree() const;
    bool IsKilled() const
    {
        return bIsDead;
    }
    bool IsSwingActive() const
    {
        return bIsAttacking;
    }
    // Every gate PerformAttack applies before asking for a token (cooldown, vendor reset, swing).
    bool CanStartAttack() const;
    // Releases the slot, token and swing timers. The NYC mode calls this after RelocateZombie
    // teleports the zombie, and the downed-player grace window calls it through the AI.
    void ReleaseCrowdClaims();

    // Validation counters (read by the offscreen review script).
    UPROPERTY(BlueprintReadOnly) int32 MontageFlinches = 0;
    UPROPERTY(BlueprintReadOnly) int32 SuppressedFlinches = 0;
    UPROPERTY(BlueprintReadOnly) int32 FlinchCancels = 0;
    UPROPERTY(BlueprintReadOnly) int32 AttackSwings = 0;
    UPROPERTY(BlueprintReadOnly) int32 TokenDenials = 0;

  protected:
    void StartSwing(AActor *Target);
    void EndSwing();
    void CancelSwing();
    void HandleKilled();
    void SetCrowdSimulation(bool bAttacking) const;
    void SetBlackboardAttacking(bool bAttacking) const;

    FTimerHandle AttackEndTimer;
    FTimerHandle DeferredSwingTimer;
    bool bSwingPending = false;
    float NextAttackTime = 0.f;
    float AttackStartTime = -10.f;
    float LastMontageFlinch = -10.f;
    // The vendor PerformAttack resets bIsAttacking on a local timer that cannot be cancelled.
    // A new swing waits until that timer has fired, so it never clears a later swing.
    float VendorResetAt = 0.f;
    mutable FHoverNYCJitter Jitter;
};

// NYC Survival controller: C++ equivalents of the owned-BT rules that run under the unmodified
// vendor BT_Zombie. When BT_NYCZombie (blackboard with AttackSlotLocation) is running instead,
// the MoveTo rewrite and abort-reissue switch themselves off and the BT nodes below take over.
UCLASS()
class HOVERFLIGHT_API AHoverNYCZombieAI : public AHoverCyberZombieAI
{
    GENERATED_BODY()
  public:
    AHoverNYCZombieAI();
    virtual void OnPossess(APawn *InPawn) override;
    virtual void Tick(float DeltaSeconds) override;
    virtual FPathFollowingRequestResult MoveTo(const FAIMoveRequest &MoveRequest,
                                               FNavPathSharedPtr *OutPath = nullptr) override;

    // Crowd agent settings from the definition and jitter. Re-run by the zombie after its
    // BeginPlay capsule resize, because possession happens before BeginPlay.
    void ApplyCrowdSettings();
    bool IsUsingVendorTree() const
    {
        return bVendorTree;
    }
    // The AHoverPilot (on foot or riding the hoverboard), otherwise the player pawn.
    APawn *FindChaseTarget() const;
    const FHoverSlotClaim &GetCurrentClaim() const
    {
        return CurrentClaim;
    }
    // Acceptance radius for a slot of this kind (tuning placeholders: inner 40, queue 60, roam 120).
    float GetAcceptanceRadius(const FHoverSlotClaim &Claim) const;

    static const FName Key_AttackSlotLocation;

    // Validation counters: MoveToRewrites > 0 proves UAITask_MoveTo routes through
    // AAIController::MoveTo; SlotReissues counts the abort-and-reissue path.
    UPROPERTY(BlueprintReadOnly) int32 MoveToRewrites = 0;
    UPROPERTY(BlueprintReadOnly) int32 SlotReissues = 0;

  protected:
    virtual void OnUnPossess() override;

  private:
    void UpdateDestination(class AHoverNYCZombie *Zombie, APawn *Target);
    bool bVendorTree = true;
    FHoverSlotClaim CurrentClaim;
    FVector LastIssuedSlot = FVector::ZeroVector;
    bool bHasIssuedSlot = false;
    float LastReissueTime = -10.f;
    FVector ApproachPoint = FVector::ZeroVector;
    FVector ApproachTargetAt = FVector::ZeroVector;
    float NextApproachRefresh = 0.f;
    float ApproachSide = 1.f;
    bool bFarApproachActive = false;
    TWeakObjectPtr<APawn> ChaseTarget;
};

// NYC Survival navigation (Section 2 Â§7 / Section 4 Â§8): one crowd agent sized for the tallest
// Stage 1 unit (radius 55, height 320, step 50) and UHoverNYCCrowdManager as the crowd manager.
// Bound per map through the L_NYC_Survival WorldSettings navigation_system_config
// (Scripts/AuthorNYCSurvival.py set_game_mode), so every other map keeps its own agent profile.
UCLASS()
class HOVERFLIGHT_API UHoverNYCNavigationSystem : public UNavigationSystemV1
{
    GENERATED_BODY()
  public:
    virtual void PostInitProperties() override;
};

// Owned-BT nodes for the later editor pass (BT_NYCZombie). They are compiled now but unused at
// runtime until a behavior tree references them.
UCLASS()
class HOVERFLIGHT_API UHoverBTTask_MoveToSlot : public UBTTask_MoveTo
{
    GENERATED_BODY()
  public:
    UHoverBTTask_MoveToSlot(const FObjectInitializer &ObjectInitializer);
};

// Cylinder in-range test that replaces the vendor 3D centre distance, so a 23 cm crawler can
// reach the mounted pilot: Dist2D <= InnerRadius + 30 (+30 hysteresis once in range) and
// |dz| <= TargetHalfHeight + SelfHalfHeight.
UCLASS()
class HOVERFLIGHT_API UHoverBTService_AttackSlot : public UZE_BTService_CheckAttackRange
{
    GENERATED_BODY()
  public:
    UHoverBTService_AttackSlot();

  protected:
    virtual void TickNode(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory, float DeltaSeconds) override;
};

// Token-gated attack: without a token it fails latently after 0.25-0.4 s instead of returning
// Succeeded on a vendor early-out (the lockstep bug).
UCLASS()
class HOVERFLIGHT_API UHoverBTTask_ZombieAttack : public UZE_BTTask_ZombieAttack
{
    GENERATED_BODY()
  public:
    UHoverBTTask_ZombieAttack();

  protected:
    struct FRetryMemory
    {
        float Remaining = 0.f;
    };
    virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory) override;
    virtual void TickTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory, float DeltaSeconds) override;
    virtual EBTNodeResult::Type AbortTask(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory) override;
    virtual uint16 GetInstanceMemorySize() const override;
    virtual void InitializeMemory(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory,
                                  EBTMemoryInit::Type InitType) const override;
    virtual void CleanupMemory(UBehaviorTreeComponent &OwnerComp, uint8 *NodeMemory,
                               EBTMemoryClear::Type CleanupType) const override;
};
