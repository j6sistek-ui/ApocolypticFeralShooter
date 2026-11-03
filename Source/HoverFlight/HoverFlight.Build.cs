using UnrealBuildTool;
public class HoverFlight : ModuleRules
{
    public HoverFlight(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "AnimGraphRuntime", "EnhancedInput", "ChaosVehicles", "UMG", "Niagara", "IKRig", "PoseSearch", "GameplayTags", "ZombieEngineStudio", "AIModule", "NavigationSystem", "ImageCore", "HLMovementSystem" });
        PrivateDependencyModuleNames.AddRange(new[] { "SlateCore", "Slate", "ApplicationCore", "Json", "PhysicsCore", "DLSSBlueprint", "StreamlineBlueprint", "StreamlineDLSSGBlueprint", "StreamlineReflexBlueprint" }); // AFS 2026-11-01: PhysicsCore for the weather rain collision delegate (UPhysicalMaterial)
        if (Target.bBuildEditor)
            PrivateDependencyModuleNames.AddRange(new[] { "UnrealEd", "VirtualTexturingEditor", "BlueprintGraph", "KismetCompiler", "AnimGraph", "PhysicsUtilities", "NiagaraEditor", "RHI", "RenderCore" }); // AFS 2026-11-01: RHI for UHoverAuthoring::MaterialCompileErrors; RenderCore + RHI for GetThreadTimesMs (weather cost)
    }
}
