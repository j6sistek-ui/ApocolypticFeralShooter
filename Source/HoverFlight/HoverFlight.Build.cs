using UnrealBuildTool;
public class HoverFlight : ModuleRules
{
    public HoverFlight(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "AnimGraphRuntime", "EnhancedInput", "ChaosVehicles", "UMG", "Niagara" });
        if (Target.bBuildEditor)
            PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd" });
    }
}
