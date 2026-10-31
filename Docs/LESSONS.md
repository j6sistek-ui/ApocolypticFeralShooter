# AFS: lessons learned

Things that were expensive to find out. Newest first within each group.

## Playtest 2026-10-31 (first full NYC run)

- **Installing a pack is not integrating it.** Explosives SFX, weather loops, footstep sets and the owner's free audio
  were all in Content and none of it played. The owner judged the game on what plays, and was right to.
- **The vendor zombie launches corpses.** `AZE_ZombieCharacter::TakeDamage` scales a dead body's impulse with the
  damage number (x100) and a death without a montage gets a deliberate "fly away" kick (18 m/s up). The Nuke power-up's
  999,999 damage turned every corpse into a rocket. Clamped and slumped in the plugin source (we compile it).
- **Zombie capsules were walkable**, so the player could stand on heads. `SetWalkableSlopeOverride(Unwalkable)` on the
  capsule fixes it; nothing else needed.
- **The vendor melee is one 20 cm sphere trace at 0.3 s.** Any melee "feel" complaint starts there, not in the
  animation. Replaced with a swept arc that damages each zombie once per swing.
- **A power-up with no presentation reads as a bug.** The Nuke killed everything with one generic pickup sound.
- **Two directional lights in a map put an engine warning on every frame** ("lights are competing ... ForwardShadingPriority").

## Gun rigging and gun feel (2026-10-29 to 10-31)

- Blender FBX bones must point +Y, roll 0, to land as identity in UE; set the scene fps after `import_scene.fbx`
  (the importer resets it); a rig whose orientation changed must be deleted in UE before re-import; the armature must
  be named `Armature` and clip FBX must carry the mesh.
- The owner's free gun recordings are quiet and slow: cyberpunk rifle peaks -15 dBFS with a 30-130 ms attack. The WW2
  machine gun set (-8 dBFS, 5-14 ms) is the one that reads as a gunshot. Measure before wiring.
- A warm muzzle light (300 cd, scaled per rig) was the "comic book blue" whiteout, not the sprite.
- Hands stay on the gun through recoil only if the gun rides the hand (GunHandKick) and the stance fire additive is
  kept off the finger bones.
- Every rig's `grip_r` is the grip top; the palm seat needs an explicit offset (`GripSeatOffset`) or the fist floats on
  the receiver.

## Headless pipelines

- **Blender FBX exporter writes the current pose as the joint transforms.** Clear the action and every pose bone
  before exporting a skeletal mesh or Unreal's reference pose is a frame of the animation.
- **A mesh node named like a bone (Eye_L vs eye_l) becomes a joint** in Interchange. Rename the mesh.
- `duplicate_asset` then `load_level` on the copy crashes the editor (old package not collected); use
  `new_level_from_template`.
- A running game or editor holds assets open; `delete_asset` fails silently and `create_asset` returns None. Reuse what
  exists or wait.
- Data Transfer in Blender matches destination layers by name; Cycles refuses to bake while any material on the active
  object holds an uninitialised image node; freestyle draws nothing headless (use a Wireframe modifier copy).
- Painter remote scripting: project create/open/close are async on the main thread; a sleep inside the script deadlocks
  Painter. Split create and build into separate calls.
- The nullrhi FBX skeletal export in UE 5.8 crashes; export GLTF and go through Blender.

## Machine and editor

- The DualSense Edge reaches Unreal only as Steam's virtual Xbox pad. GameInputWindows and WinDualShock never saw it.
- UE's `BaseInput.ini` ships F1-F5 view-mode debug bindings and Shift debug-column cycling that fire in play; the
  red/green screen on F5 was `viewmode shadercomplexity`. Cancelled in `Config/DefaultInput.ini`.
- `read_factory_settings` in headless Blender wipes the extension wheels (three times in one night).
- `get_editor_property` returns copies for struct arrays; `set_material_instance_texture_parameter_value` reports False
  on success; `FRotator(roll=90).Quaternion()` is `FQuat(X, -90)`.
- UE Python `unreal.Vector` has no `size2d`; use `math.hypot(v.x, v.y)`. A proof that trips on a helper method
  measures nothing: read the receipt's error list before its summary.
- A feature gated on `bParkourMovement` never runs in NYC Survival: the NYC pawn is `BP_Vexa_CLS_Parkour`, so that
  flag is always true there. Gate on what the template is actually doing (movement mode changed, root-motion montage
  playing), not on the pawn class (Life Engine, 2026-10-31).
- "Walks backwards" can be the mesh, not the actor. Actor-forward vs velocity passed at 0% while the Standard bodies'
  toes pointed 178 deg from travel. Measure the rendered toes (foot/ball bones) against travel, and author the mesh yaw
  per definition from a rendered measurement; an AnimPose retarget at authoring time gives the wrong answer because the
  clip goes through the ZESP skeleton of ABP_ZombieMaster first (2026-10-31).
- In MOVE_None CharacterMovement reports neither IsFalling nor IsMovingOnGround and drops LaunchCharacter, so any
  Blueprint that reads movement state goes blind while another component moves the capsule; report the real state
  from a CharacterMovement subclass (2026-10-31).
- Actors spawned at runtime are not in a static navmesh; cut them out with a nav modifier or the AI paths into them
  (the NYC truck, 2026-10-31).
- AHUD::Canvas is protected in UE 5.8; Blueprint variable names can end in "?" (`IsWallRunning?`) (2026-10-31).
- A background run redirected into a folder that does not exist yet fails before the editor starts (twice on
  2026-10-31): mkdir the receipt folder before launching.
- Script-driven previews of effects cost about as much as building them in Unreal and then have to be rebuilt once a
  look is picked (the power-up rounds moved sparks, embers and arcs as spheres from Python). Build explorations
  in-engine from the start: real Niagara, a display actor with spin/bob/pulse components, placed in a trial map, so
  the approved option is the shipping asset (owner, 2026-10-31).
- Two zombie playlists exist: DA_NYCEncounters.Standards and DA_NYCWaves CustomWaves rows. Changing one left the old
  standards spawning (2026-10-31).

## Design

- Zombies bunched because the vendor BT moves every zombie to the same point with a 5 cm acceptance and no slots;
  spawning stalled then burst because the vendor tick is skipped when no entrance qualifies. Attack slots, per-instance
  jitter and a spawn director fixed the structure; the kid swarm still clumps at its spawn (open).
- The Feral pack is an all-fours feral, not a belly crawler; the Kid is a feral by owner decision.
- Character bodies were not the problem for the SpaceSurvival pole routine; the routine's retargeting was (owner,
  2026-10-31). Do not solve a motion problem with a new mesh.
