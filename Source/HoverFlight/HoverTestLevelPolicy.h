#pragma once
#include "CoreMinimal.h"
#include "Engine/World.h"
#include "GameFramework/GameModeBase.h"
#include "UObject/Interface.h"
#include "HoverTestLevelPolicy.generated.h"

// Per-level rules for the shared test rides and Vexa. The defaults keep PostApo,
// Cyber City, Lakeside and NYC Exploration unchanged; NYC Survival overrides them.
UINTERFACE(MinimalAPI)
class UHoverTestLevelPolicy : public UInterface
{
    GENERATED_BODY()
};

class IHoverTestLevelPolicy
{
    GENERATED_BODY()

  public:
    virtual bool SpawnsTestBike() const
    {
        return true;
    }
    virtual bool SpawnsTestTruck() const
    {
        return true;
    }
    virtual bool AllowsTruckMount() const
    {
        return true;
    }
    virtual bool ForcesThirdPerson() const
    {
        return false;
    }
    virtual bool ForcesMortal() const
    {
        return false;
    }
    virtual float GetPlayerMaxHealth() const
    {
        return 100.f;
    }
    // Section 5 gun feel; the NYC mode turns it on, every other level keeps the config gate.
    virtual bool EnablesEnhancedGunFeel() const
    {
        return false;
    }
    // Home / R teleport-and-heal reset. NYC Survival turns it off: 0 HP is game over there.
    virtual bool AllowsSandboxReset() const
    {
        return true;
    }
    // Section 5 survival rules on the pilot (sprint-fire gate); only the NYC mode turns them on.
    virtual bool UsesSurvivalRules() const
    {
        return false;
    }
    static const IHoverTestLevelPolicy *Get(const UWorld *World)
    {
        return World ? Cast<IHoverTestLevelPolicy>(World->GetAuthGameMode()) : nullptr;
    }
};
