#include "HoverMotion.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FHoverMotionTest, "AFS.HoverMotion.MomentumAndDirection",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FHoverMotionTest::RunTest(const FString &Parameters)
{
    const FVector Forward(1800, 0, 0);
    const FVector Coast = HoverMotion::HorizontalVelocity(Forward, FVector::ZeroVector, 1800, 1.f / 60, false);
    const FVector Brake = HoverMotion::HorizontalVelocity(Forward, -FVector::ForwardVector, 1800, 1.f / 60, false);
    TestTrue(TEXT("Release preserves momentum"), Coast.X > 1700 && Coast.X < Forward.X);
    TestTrue(TEXT("Braking is stronger than coasting, without instant reversal"), Brake.X > 0 && Brake.X < Coast.X);
    for (int32 Rate : {30, 60, 120})
    {
        FVector V = Forward;
        for (int32 I = 0; I < Rate * 3; ++I)
            V = HoverMotion::HorizontalVelocity(V, FVector::ZeroVector, 1800, 1.f / Rate, false);
        TestTrue(TEXT("Coasting settles without reversing"), V.IsNearlyZero(.1f));
        float Angle = 0, AngularVelocity = 0;
        for (int32 I = 0; I < Rate; ++I)
            HoverMotion::Spring(Angle, AngularVelocity, -20, 1.f / Rate);
        TestTrue(TEXT("Reverse reaction has correct sign and no overshoot"), Angle < -19.9f && Angle >= -20);
        for (int32 I = 0; I < Rate; ++I)
            HoverMotion::Spring(Angle, AngularVelocity, 20, 1.f / Rate);
        TestTrue(TEXT("Direction reversal smoothly reaches opposite reaction"), Angle > 19.9f && Angle <= 20);
    }
    return true;
}
#endif
