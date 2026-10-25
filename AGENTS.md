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

Preserve the existing vehicle Blueprints. The owner authorized a runtime mapping copy
for bike RT throttle, LT brake/reverse, B boost and corrected right-stick camera;
keyboard and truck bindings remain vendor controls. Scope is free flight, mounting,
dismounting, rifle aiming/shooting, the supplied bike and Doomsday pickup truck, plus
respawning zombies with blood impacts and death. Vexa defaults to invincible; the
pause-menu toggle permits normal health testing and a quick reset at zero health.
Cyber City explicitly includes the supplied Zombie Engine inventory,
quickbar, ammo/reload, melee, loot, gold/wall buys, waves and compatible live RGCL
settings. Preserve Vexa/CLS/Parkour instead of replacing her with the vendor pawn.
PostApo remains outside Zombie Engine. Chinese Lakeside Town has separate wave data
using its own five newly supplied creatures; never reuse the Cyber City or
PostApo zombie roster there. Keep later texture replacements reimportable.
No main-game integration, network play,
or production release is implied. See Docs/ANIMATION_POLISH_20261025.txt for latest
posture/crouch/FPS katana checks and Docs/ASSET_AUDIT_REPAIRS_20261025.txt for current
audit repairs, Docs/NIGHT_QUALITY_20261024.txt for earlier rendered evidence,
and Docs/QUALITY_20261023.txt for the historical integration
matrix, native plugin patches and remaining animation gaps.

Use offscreen Unreal runs for automated inspection. Do not run captures concurrently.
The owner explicitly chose no GitHub destination: keep this project local and do not create a PR.
