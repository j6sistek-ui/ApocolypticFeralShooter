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
        float Peak = 0;
        float Previous = 0;
        for (int32 I = 0; I <= Rate * 2; ++I)
        {
            const float Height = HoverMotion::OllieHeight(float(I) / Rate);
            Peak = FMath::Max(Peak, Height);
            TestTrue(TEXT("Ollie stays above its start and has no position jump"),
                     Height >= 0 && FMath::Abs(Height - Previous) < 45.f);
            Previous = Height;
        }
        TestTrue(TEXT("Ollie visibly pops above the final hover height"), Peak > 299.f && Peak <= 300.01f);
        TestTrue(TEXT("Ollie settles to the existing height at every sample rate"),
                 FMath::IsNearlyEqual(Previous, 166.f, .01f));
        FVector Banked = Forward;
        for (int32 I = 0; I < Rate; ++I)
            Banked = HoverMotion::ApplyBank(Banked, 28.f, 1.f / Rate);
        TestTrue(TEXT("A right bank bends travel right without deleting momentum"),
                 Banked.Y > 400 && FMath::Abs(Banked.Size() - Forward.Size()) < .1f);
        TestTrue(TEXT("Bank has no turn authority while stationary"), HoverMotion::BankYawRate(28.f, 0) == 0);
        TestTrue(TEXT("Enhanced bank materially tightens a normal-speed turn"),
                 HoverMotion::BankYawRate(35.f, 2160.f) > HoverMotion::BankYawRate(18.f, 2160.f) * 1.8f);
        TestTrue(TEXT("Reverse travel changes the bank turn sign"), HoverMotion::BankYawRate(28.f, -1800) < 0);
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
