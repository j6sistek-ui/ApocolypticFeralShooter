# AFS flight test

An isolated Unreal5.8 prototype using Vexa, the black/red personal glider, the
installed post-apocalyptic environment, the supplied sci-fi rifle and the drivable
ScifiHoverbike and Doomsday pickup truck. The board spans left-to-right beneath the rider's feet.
In PostApo, twenty zombies spawn across the surrounding area, wander or approach, and respawn after
being shot. Vexa starts invincible; the pause menu can enable normal health loss.
Rifle body hits deal 35 damage; headshots kill immediately.
BloodShot Niagara impacts and ragdoll deaths provide hit feedback; ammo is unlimited.

Cyber City uses Zombie Engine's escalating waves, behavior tree, attack/hit/death
animations, damage numbers, loot and wave display. The local adapter keeps Vexa,
CLS/Parkour, the Ballista and all three rides. Zombies target the currently possessed
player or vehicle; Vexa defaults to invincible and occupied rides remain invulnerable. Wave one has ten
zombies; later waves grow in count, health and speed. Nuke and timed speed pickups
work with the AFS player. Cyber City now uses the supplied magazine/reserve,
reload, melee, inventory, quickbar, gold, loot and wall-buy systems. Three supply
crates offer Ballista tiers and ammunition. PostApo keeps unlimited ammo and its
original zombie range; it has no Zombie Engine inventory or waves.

Cyber City now has four new standard appearances, a heavy brute on rounds12/14/16...
and eight-kid swarm rounds5/15/25... as editable starting settings. The brute uses
the supplied stomp and smash clips; its landing pulse knocks nearby on-foot Vexa
down, with walls blocking the effect. Chinese Lakeside Town is a third selectable
map with all three rides and separate wave data. Its five new creatures are Horror,
BogZombie, Mythical, Plant and Pirate. BogZombie uses the owner's rigged `(3)` source.
None of Cyber City's or PostApo's zombies are used there. See
`Docs/ZOMBIE_SPECIALS_20261024.txt` for Cyber roles and
`Docs/LAKESIDE_CREATURES_20261024.txt` for the independent roster and texture reimport.

R3/V uses the supplied bloodied katana on foot in all test levels. It uses the
purchased knife slash, native melee contact/cooldown and a local hand attachment.
The rifle hides during the swing. FPS now has fitted view-arm idle/slash clips;
the blade follows the hand, gripped just below the guard with its curvature reversed.
Original4K weapon detail is requested while in FPS and released when holstered.
See `Docs/KATANA_TERRAIN_20261025.txt` for grip, streaming and terrain support checks,
`Docs/ANIMATION_POLISH_20261025.txt` for the preceding animation evidence and
`Docs/KATANA_20261023.txt` for historical provenance,
timing, rollback files and the distinction between CPU checks and rendered review.

Eight curated entrances use the construction area, shop alcoves, service streets
and courtyard. Their navigation routes connect to the starting street. Spawns wait
when an entrance is within14m, openly visible ahead, occupied, or more than100m
away. When none is suitable, spawning waits instead of falling back to PlayerStart.
The local map uses `/Game/HoverPrototype/ZombieEngine/BP_CyberWaves`; its data assets
expose wave and zombie tuning. The copied ZombieEngineStudio plugin is required
and enabled locally, with isolated UE5.8 compatibility fixes. Licensed plugin
source, binaries and content remain outside Git; preserve the native installation.
During Play, use Window > ZESP Control Panel for the purchased live tuning tool.
`Docs/QUALITY_20261023.txt` lists supported fields and native integration patches.
`Docs/ASSET_AUDIT_REPAIRS_20261025.txt` contains the latest asset-integration
repairs and remaining limits. `Docs/NIGHT_QUALITY_20261024.txt` retains earlier
rendered checks and the separate engine-only shutdown reproduction.

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

On foot, a local copy of ParkourMovementPack's original Blueprint movement graph
controls movement, wall running, jump buffering and coyote time. Walking is capped at
500 cm/s and held-L3 running at900 cm/s. The template's1000 cm/s² acceleration,
2.5 gravity scale and1102.5 cm/s jump velocity remain. A feeds its buffered Space
jump event. Stationary tap B/Shift crouches or stands; holding enters prone.
Moving tap slides; moving hold dives and lands with a brief supported settle.
Standing checks
headroom. The purchased template has movement logic but no skeletal animations:
the slide uses a local leg/torso variant of the owned crouch pose. Supported
prone uses the purchased belly pose with forearm/foot contact; moving unarmed
crawl uses the owner's animation-only loop, retargeted without the donor mesh.
Directional crouch uses 13 owned ZESP clips. Full-body actions run after CLS root/foot
corrections so they stay centred on the moving capsule. Dedicated human slide and
prone-entry/exit clips remain missing. See `Docs/ANIMATION_POLISH_20261025.txt`
for current motion checks and `Docs/NIGHT_QUALITY_20261024.txt` for earlier
effect/loot fixes.
CLS selects and retargets locomotion
poses through a hidden mannequin while Parkour retains movement and special actions.
Third-person Vexa faces travel unless aiming. F7 / D-pad Right toggles the original
poses and CLS on the same pawn; glider, weapon and vehicle controls remain available.
The local CLS data component cannot overwrite Parkour movement settings. Grounded
CLS motion uses lower friction while input is held, restoring braking on release.

The pre-change runnable project is preserved at
`D:/AFS_Comparisons/Before_Parkour_2026-10-23/AFS`, with a SHA256 manifest beside it.
Use `Open_Before_Parkour.cmd` in its parent directory to compare the old behavior.

Vexa retains her face/body shape, material and physics overrides. The local fitted
torso/legs mesh bakes her existing leg morphs and joins the waist boundary. Two new
bones animate the back chain. The local post-process Blueprint
`/Game/HoverPrototype/Appearance/ABP_Vexa_BodyPhysics` contains the four original
Xandra Spring Controllers, mapped to chest_l/r and glute_l/r. Glute stiffness160,
damping10 and a6.5 cm limit give slower followthrough; chest uses220/12 and3.5 cm.
Grounded settings remain unchanged. Airborne motion blends to softer, more damped
springs and a steady0.45 strength, avoiding acceleration-threshold flicker. Teleport
reset distance accounts for normal travel during slow frames. The prior native body
spring offsets are bypassed when this Blueprint is present. The fitted visible
body copies the final pose, then applies persistent chain pendulum motion.
The chain reacts to movement and animated spine acceleration and settles after stops.
Whole hanging links follow the chain bones; belt vertices retain their source skin
weights so belt pieces do not flap with the hanging chain.

The selected local outfit combines the Cloth-02 top and Cloth-05 bottoms in matching
ivory, with all original chains retained. Face, torso and limb skin materials share
a warmer tan-brown SkinColour override. The original fabric top and pants are removed from this
copy. Garments have skin weights matched to Vexa; they are not Chaos cloth simulation.
Original geometry, previous fitted versions and separate editable garments remain
in the D-drive/workspace backups. The supplied bike retains its riding graph and
receives the fitted body/chain. Original SpaceSurvival meshes remain unchanged.
Find the playable Blueprint by searching `BP_Vexa_CLS_Parkour`, and the outfit by
searching `SK_Vexa_SelectedOutfit` in the Content Browser.

The local `HoverPrototype/Appearance` material graph contains complete virtual
UDIM textures; original materials and SpaceSurvival remain intact. The PostApo
runtime lighting allows bounded exposure adaptation in shaded streets, reduces bloom,
removes film grain and preserves its
Lumen final-gather quality. The data asset exposes Balanced Test Lighting,
Test Exposure Bias and Test Bloom Intensity. Turning this treatment off restores
the authored map on the next Play session. Local renderer configuration enables
virtual textures and Lumen hardware ray tracing; restart after changing these.

See `Docs/CONTROLS.txt` for the input map and `Docs/VALIDATION.txt` for evidence
and current limits. On the glider R2 supplies thrust, left-stick forward/back controls
climb/dive and left/right steers. Right stick aims/looks independently of travel.
Hold L1 while steering to increase bank from 18 to 35 degrees. R1 fires and L2 aims.
A performs an ollie-like hop: a3.00 m peak settles to the existing1.66 m height gain,
with board tilt and a small shockwave. Released thrust coasts with damped pitch and
wing reactions. Base speed is21.6 m/s; climb reaches18 m/s and descent24 m/s.
L1 bank now adds substantially stronger heading and velocity curvature.
L3 boost reaches56 m/s and has a draining/recharging meter.
Vexa defaults to invincible. Test Settings can enable normal health loss; at zero
health she resets after3seconds. Home resets the player/glider; R also resets in PostApo,
while R reloads in Cyber City.

The data asset also exposes booster, muzzle and landing effect references. Local effect
copies preserve vendor originals. Narrow white/blue Niagara jets follow thrust,
lift, descent, steering and braking at existing board features, without new nozzle geometry.
The supplied Ballista replaces the first rifle and has a local removable reflex
sight. L2 uses centred sights in FPS and screen zoom while staying external in
third person. Crouch height eases without changing camera-arm distance; jump
animations do not request a zoom. Its muzzle pulse is attached to the measured
barrel tip, and a straight tracer with a short purchased Niagara trail follows
the barrel axis. Solid hits produce dust/debris, and
CP Rifle1 audio004 provides the shot sound. The original gun assets remain intact.
The configured Ballista tiers use hitscan with a cosmetic tracer; the combat bridge
also honors a weapon's explicit projectile configuration. FPS has Vexa-derived
arms and a native reload action; the static gun has no detachable magazine.
The glider uses turn/movement entry and exit clips, held pitch poses, nine aim
offsets, an upper-body reload action and recoil, with independent camera look.
The hips adjust to both legs' reach before foot IK, keeping the feet on the pads
through taller poses without stretching the legs. Animation evaluates after the
pilot updates the board and foot targets. Input, motion and boost timers retain
elapsed time on slow frames; the spring-loaded pads substep independently.
Landing shockwaves are intentionally brief. Landings request a light
controller pulse, whose physical feel still needs owner review.

Press D-pad Up or F6 for test settings. The Test level row switches between Post-apocalypse,
Cyber City (`/Game/HoverPrototype/Maps/L_CyberCity`), Chinese Lakeside Town
(`/Game/Chinese_Lakeside_Town/Levels/L_Showcase`) and NYC - Exploration
(`/Game/HoverPrototype/Maps/L_NYC_Explore`), starting a fresh test session.
NYC uses Vexa, the hoverboard and Doomsday truck, with no zombies or wave systems.
The other three levels retain their existing vehicles and encounters.
Switching levels discards the current test session. See `Docs/NYC_EXPLORATION_20261028.txt`.
D-pad/arrows select and adjust, A/Enter
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

A separate reversible development copy lives at
D:/AFS_Comparisons/CLS_MM_2026-10-23/After_CLS_MM/AFS.
Normal Play now uses CLS poses with Parkour gameplay. The earlier two-pawn
ClsComparisonGameMode remains available for the preserved experiment. Both candidates
use the same speed caps. Matched rendered clips are comparison evidence, not an FPS benchmark.
