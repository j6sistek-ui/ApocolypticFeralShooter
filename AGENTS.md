# AFS hover prototype

This is an isolated local gameplay test. Keep SpaceSurvival and all supplied source art intact.
Track authored code and documentation only. Do not commit Content, SourceAssets, Saved,
Intermediate, Binaries, local configuration, asset inventories, or purchased source artwork.
Never merge a PR automatically.

Use the Dockerfile for portable Python script syntax checks. Do not install host packages.
Unreal Editor builds and real graphics tests require the installed Windows UE5.8 toolchain;
the container does not validate native gameplay. Build with Scripts/Build.ps1. Format authored
C++ using clang-format and the checked-in style. Inspect the actual rider, pad contact, gun,
and bike in a rendered play session after changes affecting them.

Preserve the existing vehicle Blueprints and their controls. Scope is free flight, mounting,
dismounting, rifle aiming/shooting, the supplied bike and Doomsday pickup truck, plus
respawning zombies with blood impacts and death. Vexa is invulnerable; zombies cannot
damage her. No main-game integration, inventory, network play, or production release is implied.

Use offscreen Unreal runs for automated inspection. Do not run captures concurrently.
The owner explicitly chose no GitHub destination: keep this project local and do not create a PR.
