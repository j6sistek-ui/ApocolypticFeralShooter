# AFS flight test

An isolated Unreal5.8 prototype using Vexa, the black/red personal glider, the
installed post-apocalyptic environment, the supplied sci-fi rifle and the drivable
ScifiHoverbike and Doomsday pickup truck. The board spans left-to-right beneath the rider's feet.
Twenty zombies spawn across the surrounding area, wander or approach, and respawn after
being shot. They cannot hurt Vexa. Rifle body hits deal 35 damage; headshots kill immediately.
BloodShot Niagara impacts and ragdoll deaths provide hit feedback; ammo is unlimited.

Build with `Scripts/Build.ps1`, open `AFS.uproject`, and press Play. The default
map is `/Game/JustBStudios/PostApo/Levels/PostApo`. If the editor has another level
open, open that map first. Hold X near the settled glider to mount; hold X to get off
only when slow and within 1.5 m of clear walkable ground. Released gliders fall and settle.
Walk toward the parked bike and hold X to drive it. Its supplied E exit action
returns to the retained Vexa player; hold X is also supported.
The truck is parked on the opposite side of the starting area. Hold X nearby to
enter; hold Y on a controller (X on keyboard) to exit. Its supplied X throttle
binding remains unchanged. AFS is the local sandbox for testing these assets.

The local data asset `/Game/HoverPrototype/DA_HoverPilot` holds the character's
modular meshes/materials, glider, rifle and animation references. Native purchased
assets are deliberately excluded from source control; a source checkout alone
does not contain a playable installation. The locally authored assets must be
retained alongside the code.

On foot, an eight-direction idle/walk/jog blend follows actual movement speed;
stationary camera turns use stepping animations. Vexa retains her source body/face
morphs, physics overrides, contact shadows and 600 cm/s walk/jump defaults. Chest
and glute springs run on foot and on the personal glider, limited to 2 cm. The
supplied bike keeps its own riding animation graph and receives Vexa's appearance.

The local `HoverPrototype/Appearance` material graph contains complete virtual
UDIM textures; original materials and SpaceSurvival remain intact. The PostApo
runtime lighting lowers exposure/bloom, removes film grain and preserves its
Lumen final-gather quality. The data asset exposes Balanced Test Lighting,
Test Exposure Bias and Test Bloom Intensity. Turning this treatment off restores
the authored map on the next Play session. Local renderer configuration enables
virtual textures and Lumen hardware ray tracing; restart after changing these.

See `Docs/CONTROLS.txt` for the input map and `Docs/VALIDATION.txt` for evidence
and current limits. Right-stick pitch drives climb/dive along the direction of travel;
L1/R1 bank left/right. Released thrust coasts, opposing thrust brakes before reverse,
and board/rider/wing reactions use signed motion with damped transitions. Leveling pitch
settles vertical motion into altitude hold. L3 boost has a draining/recharging meter.
Vexa is invulnerable; R resets the player and glider to the test start.

The data asset also exposes booster, muzzle and landing effect references. Local effect
copies preserve vendor originals. Niagara thrust follows direction and boost strength;
landing shockwaves and muzzle pulses are intentionally brief. Landings request a light
controller pulse, whose physical feel still needs owner review.

Press D-pad Up or F6 for the graphics menu. D-pad/arrows select and adjust, A/Enter
applies and saves, B/F6 cancels. DLAA, DLSS quality modes and supported frame-generation
multipliers are available. Frame generation requires Standalone Game; editor Play saves
that preference without activating it. Reflex enables automatically with frame generation.
The menu pauses all movement and firing, including the supplied vehicles. Preferences live
in the local GameUserSettings.ini `[AFS.Graphics]` section. Editor renderer values are
restored when Play ends. The project requires the locally installed NVIDIA UE5.8 v8.9
plugins DLSS, StreamlineDLSSG, StreamlineReflex, StreamlineCore and StreamlineNGXCommon.
These licensed dependencies are excluded from Git. Ray reconstruction and cinematic
Movie Render Queue configuration are outside this menu's scope.

Run portable script syntax checks with:

```powershell
docker build -t afs-script-check .
docker run --rm afs-script-check
```

Native builds and rendered play checks use the existing Windows Unreal toolchain.
No packages are installed on the host. This is a local gameplay prototype, not a
packaged release or SpaceSurvival integration.
