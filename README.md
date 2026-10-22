# AFS flight test

An isolated Unreal5.8 prototype using Vexa, the black/red personal glider, the
installed post-apocalyptic environment, the supplied sci-fi rifle and the drivable
ScifiHoverbike and Doomsday pickup truck. The board spans left-to-right beneath the rider's feet.
Twenty zombies spawn across the surrounding area, wander or approach, and respawn after
being shot. They cannot hurt Vexa. Rifle body hits deal 35 damage; headshots kill immediately.
BloodShot Niagara impacts and ragdoll deaths provide hit feedback; ammo is unlimited.

Build with `Scripts/Build.ps1`, open `AFS.uproject`, and press Play. The default
map is `/Game/JustBStudios/PostApo/Levels/PostApo`. If the editor has another level
open, open that map first. Hold X near the glider to mount; hold X again to get off.
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

See `Docs/CONTROLS.txt` for the input map and `Docs/VALIDATION.txt` for evidence
and current limits. On the glider, right-stick pitch also drives climb/dive while
forward or reverse thrust is applied. With no vertical command, the movement
controller damps vertical velocity and holds the current height. Vexa is invulnerable.
Dismounting in the air makes the rider fall; R resets
the player and glider to the test start.

Run portable script syntax checks with:

```powershell
docker build -t afs-script-check .
docker run --rm afs-script-check
```

Native builds and rendered play checks use the existing Windows Unreal toolchain.
No packages are installed on the host. This is a local gameplay prototype, not a
packaged release or SpaceSurvival integration.
