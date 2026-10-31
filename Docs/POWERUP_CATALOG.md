# AFS: power-up model catalogue

The owner's Tripo models for power-ups, batch by batch. Owner 2026-10-31: "power ups, to be defined, may not be
needed, but assets none the less. I imagine these being hologram in bright different colors, temporary effects of
sorts. ... name does not equal intent." So each entry is judged from the render, not the file name.

Sources are in `SourceAssets/PowerUps/<Batch>/` (GLB, Tripo, about 1 m tall, one texture set each). Renders and the
contact sheet are in `D:/AFS_Comparisons/PowerUps_<date>/<Batch>/` (`sheet_34.png`, per-model `_34` and `_front`
PNGs, `props.json` with triangles and sizes), made by `Scripts/Blender/RenderPropSheet.py`.

## The look: must fit the vibe (owner, 2026-10-31)

After seeing typical store pickup VFX (neon ring pads, magic circles, pentagrams, glowing swords, rainbow sparks) the
owner said "none of those are it; let's see what fits the vibe". Power-ups must look like they belong in a ruined,
dusty, dusk-lit New York: grounded, a bit grimy, readable at 10 m in dust and low light; holograms dirty, low-fi or
projected, not clean neon. Ten looks are being tried on the medkit and the Nuke (road flare, chemlight, supply-drop
beacon, salvaged holo-projector, radioactive, blood-magic relic, infected glow, dust shaft, tagged salvage, dirty
hologram shell) before any is applied to all 15. Owner follow-up: "it may be something like that, with a different
twist or game appropriate style" ("yes, better ideas"), so four looks take the store ideas and ground them: a scrap
ring pad with hazard lights, a graffiti circle glowing like UV paint, a busted NYC neon-sign icon, a searchlight
pillar. The section below was the first idea.

## Style round 1 (2026-10-31): 14 looks on the medkit and the Nuke

Sheets (local): `D:/AFS_Comparisons/PowerUps_20261031/Styles/styles_sheet.png` (2.5 m) and `styles_sheet_10m.png`.
Showcase map `/Game/HoverPrototype/Maps/L_PowerUpShowcase`; looks under `/Game/HoverPrototype/PowerUps/Styles/` and
`/Game/HoverPrototype/Effects/PowerUps/`; scripts `Scripts/ImportPowerUps.py`, `Scripts/AuthorPowerUpStyles.py`.
Strongest reads: 11 scrap ring pad, 13 busted neon, 14 searchlight pillar, 1 road flare, 12 graffiti circle (icon
missing); 3 supply beacon is the best at 10 m but a haze up close. Weak or off-brief: 4 and 10 (holograms read pale or
like fire), 5 (items look frosted), 6 (item goes black), 7 (white crackle), 8 (no colour, no visible shaft), 9 (items
too dark). Lit only in the showcase map; nothing wired to gameplay; owner to pick or combine. Round 2 adds the owner's
closer references below.

**Owner verdict on round 1:** rule out anything with beacons or extra objects: a power-up is the item that spawns,
plus effects on and around it. No added props, ground features, rings or markings ("not very power-up like").
Keep 5 Radioactive, 6 Blood Relic, 7 Infected, 8 Dust Shaft, 13 Busted Neon; round 2 refines those and adds new
options built with the closer references below.

## Style round 2 (2026-10-31): kept looks refined, new effect-only looks, owner combo

Sheets (local): `D:/AFS_Comparisons/PowerUps_20261031/Styles/round2_sheet.png`, `round2_sheet_10m.png`,
`round1_vs_round2_kept.png`. Looks 5, 6, 7, 8, 13 refined; new 15 Energy Swirl, 16 Arc Crawl, 17 Soul Wisps, 18 Ember
Corona, 19 Inner Glow, 20 Heartbeat, 21 Toxic Aura, 22 Rarity Mist; 23 is the owner's combo of 5 + 6 + 13.
Independent check, top four: 23 Combo (strongest at 10 m, item readable), 8 Dust Shaft, 21 Toxic Aura (closest to the
references), 17 Soul Wisps (clearest item). Known gaps: sparks, embers, bolts and the heartbeat echo in 16, 18, 20 are
driven by the preview script and need real Niagara emitters to ship; most looks light a soft pool on the street from a
key light; 6 and 21 show doubled outlines on the Nuke; 7 still reads as lava cracks; colourable Niagara on disk is
scarce.

**Owner on round 2 (2026-10-31):** the moving looks should be shown as GIFs (recorded). A few items need their own
signature on top of the shared look, starting with the Nuke: it must read as volatile and nuclear, with sparks, tracer
streaks and micro-explosions; a yellow fog makes it look like toxic waste, not a nuclear device. Round 3: a signature
pass per item, Nuke first. Owner after the GIFs: look 16 Arc Crawl is a solid Nuke contender too.

## Nuke round 3 (2026-10-31): volatile signatures, GIFs

GIFs (local) `D:/AFS_Comparisons/PowerUps_20261031/Styles/gifs_nuke/`: N1 Spark Crackle, N2 Micro-Detonations, N3
Tracer Streaks, N4 Unstable Core, N5 Ticking Bomb (the owner's spec: swells on accelerating ticks, spark ring, flash),
N6 Combo (N5 + N2 + N3); `nuke_grid.gif`, `nuke_far.gif`. Checker's top three: N6, N5, N2. Notes: N2's smoke puffs read
as tan blobs; N3 reads more like ricochets; N4 looks glassy; flashes light an oval on the ground. All motion is
script-driven (Niagara candidates on disk ignore scale or are rings); the chosen look gets built as real Niagara on
a display actor (see LESSONS). Owner also named round-2 look 16 Arc Crawl a contender.

**Owner direction for the Nuke (2026-10-31, still thinking):** the GIFs felt too aggressive because of the fast 2.4 s
loop; "aggressive" meant the look, not the pace. Leaning N6, but wants: N4's shaking (unstable casing), mild sparking
(a little of N1), and 2-3 spark combos from N2's micro-detonations spread through its dropped life (a power-up sits
30 s before it despawns, vendor `InitialLifeSpan`). Pace the events over those 30 s, not a 2.4 s loop. Possible
addition to confirm: intensity rising as the despawn nears, as a warning.

## Closer references (owner, 2026-10-31)

Seven reference boards the owner found closer to the target (local copies in `Docs/References/PowerUpStyle/`, not in
git): **realistic, grimy PBR objects with strong coloured Niagara energy around them** (glow swirls, goo pools and
splashes, sparks and embers, lightning arcs, ghostly wisps) on a dark wet street; tone "dark, gritty, playful, not
overly serious". This is the direction for round two of the style tests, after the owner picks from round one.

### Idea bank from those boards (not adopted; for repurposing the owner's models into something better)

| Idea | Effect | Could repurpose |
|---|---|---|
| Corpse Magnet | a necrotic gravity well pulls zombies in, slams them together | Curse tower (#2) |
| Puke Napalm / Toxic Sludge Grenade / Sludge Cocktail | goo explosion, slippery toxic puddle that slows and damages | Toxic gas (#13), already close |
| Boom Box | a dropped speaker blasts cursed music: zombies disoriented, explosive beats | needs a model |
| Ghost Snack / Zombie Buddy Vial | friendly spectral wisps or a pal that bite zombies and heal you | Boss totem (#9) alternative |
| Molten Coffee / Caffeine Overdrive | speed and damage boost with jitter streaks, heartbeat VFX | Energy cell (#11) |
| Zombie Be-Gone Cloud | a plume that makes zombies dance | needs a model |
| Frostbite Shake | ground shake that freezes zombies in place | Hourglass (#4) variant |
| Lucky Scav Box / Loot Goblin Orb | risky random loot, maybe a rubber chicken | Loot crate (#5) or clover flask (#15) |
| Bouncy Grenade | glowing ribbon-trail grenade that bounces, then explodes | a tactical |
| Shrink Ray | shrink zombies to pocket size | a weapon, later |
| Good Boy (spectral or zombie dog) | a companion that distracts and bites zombies | Boss totem (#9) alternative |
| Hemo Burst | zombies burst from the inside, blood shockwave (blood-magic pack fits) | Curse (#2) or eye (#7) |
| Static Surprise | a dropped device zaps zombies in a radius, ragdolls | Spider pod (#16) variant |
| Radioactive Burger | weird lucky buff with Geiger ticks and heat waves | humour item, needs a model |
| Rusty Revitalizer | heal over time plus a damage buff, sparks and dust vortex | Medkit (#6) variant |
| Banshee's Whistle | a wail that confuses zombies (some flee, some trip) | needs a model |

## First idea: holograms

One shared master material, a material instance per power-up colour:
- fresnel-edge emissive in the power-up's colour, with the model's own texture kept faint inside for detail;
- scrolling scanlines and a slight flicker, translucent and additive, depth-faded where it meets the ground;
- a slow spin and bob, a soft point light in the same colour, a pickup burst in that colour.

The vendor pickup (`AZE_PowerUpPickup`, AFS subclass `AHoverCyberPowerUp`) already spawns, times out and applies
the effect. Only the mesh, material and colour change per type.

## Vendor power-up types already working

`EZE_PowerUpType`: MaxHealth, MaxAmmo, InstaKill, SpeedBoost, Nuke, Danger (explosive trap).

## Batch 01 (2026-10-31, 10 models)

| # | File | What it is (from the render) | Tris | Proposed use | Colour | Status |
|---|---|---|---|---|---|---|
| 1 | ammo_can | Green ammo canister, "UNLIMITED AMMO" with an infinity mark | 4.7k | **MaxAmmo** now. Later: a timed bottomless magazine (no reload for 15 s), which matches the label. | yellow-green | now |
| 6 | medkit | Canister with a red cross, red cap | 4.9k | **MaxHealth** now | red | now |
| 9 | stone_skull_shield | Stone skull wreathed in green ooze and chains | 9.7k | **InstaKill** now: a skull reads as "one-hit kills" | toxic green | now |
| 2 | fantasy_prop | Stone tower with a green crystal on top, skulls, chains, up/down runes | 7.2k | Later: a lure totem that draws zombies to it. (Was the Nuke until batch 02 brought a radiation model.) | orange-white | later |
| 8 | rusted_flask_2 | Battered hip flask with a yellow clover emblem | 4.7k | Duplicate of batch 02's rusted_flask, which has 4K textures: use that one. | - | dup |
| 5 | loot_crate | Military crate with a hazard stripe and an emblem | 4.7k | Later: a mystery crate (random weapon) or the ammo buy-point prop (waiting on the owner's OK for buy points). Not a timed power-up. | gold | later |
| 3 | fantasy_shield | Ornate shield with a gold star | 4.9k | Later: a ward, about 8 s of invulnerability | gold-white | later |
| 4 | hourglass_with_clock | Blue hourglass with a pocket watch | 4.7k | Later: slow time, zombies at about 40 % speed for 10 s | blue | later |
| 7 | monster_eyeball | Veined eyeball, blue iris, green drip | 4.9k | Later: reveal, zombie outlines through walls for 12 s | magenta | later |
| 10 | tactical_vest | Plate carrier with a white cross | 7.2k | Later: armour plates through the vendor armour slots (`ZE_ArmorSlotsConfig`), or a temporary damage cut | steel blue | later |

**Duplicates:** none inside this batch. The two shields (3 and 9) look different and get different jobs. Batch 02
repeats two of these (see below).

## Batch 02 (2026-10-31, 7 files, 5 new)

Byte-identical repeats of batch 01, dropped: monster_eyeball, rusted_flask_2. Batch 02's `rusted_flask` is the same
model as batch 01's `rusted_flask_2` (same 4,740 triangles, same look) with 4K textures instead of 2K: it replaces it.

| # | File | What it is (from the render) | Tris | Proposed use | Colour | Status |
|---|---|---|---|---|---|---|
| 12 | futuristic_grenade | Black and gold canister with a radiation trefoil | 83k (needs a decimate to ~8k) | **Nuke** now: the radiation mark reads as "blast" | orange-white | now |
| 13 | futuristic_grenade_2 | Grey sphere with a glowing green radiation window | 4.8k | **Danger** now (the vendor's explosive trap: a radioactive hazard). Also a candidate throwable for the tactical slot later. | hazard red-green | now |
| 11 | energy_cell | Cracked green battery with a lightning bolt | 4.8k | **SpeedBoost** now (energy) | cyan | now |
| 15 | rusted_flask (4K) | The clover flask | 4.7k | Later: luck, points doubled for 30 s (named originally, not after any other game) | gold-green | later |
| 14 | medical_supply_crate | Red-and-steel crate with white crosses | 4.4k | Later: a health buy station or shop item, not a timed power-up | red | later |

## Batch 03 (2026-10-31, 1 model)

| # | File | What it is (from the render) | Tris | Proposed use | Colour | Status |
|---|---|---|---|---|---|---|
| 16 | futuristic_trap_device | Oval pod, amber glass inside, a spider-legged mechanism folded in the middle; a small loose spider-shaped fragment floats above it (Tripo stray, delete on import) | 4.8k | The Robot Mine's pickup and deploy pod. The owner's Robot Mine design (2026-10-31): a tactical, thrown, lands and assembles, seeks the nearest zombie, explodes with area damage. The `SilkTrap` spider robot is already in AFS with Assembly, Jump, Attack and Death clips: the pod is what you pick up and what lands, the SilkTrap unfolds out of it. | amber | later (with the Robot Mine) |

## Batch 04 (2026-10-31, 1 model)

| # | File | What it is (from the render) | Tris | Use |
|---|---|---|---|---|
| 17 | radiation_grenade | The same black-and-gold radiation canister as #12, clean, one piece | 4.8k | **The Nuke model.** Replaces #12 (83k triangles, segmented; kept as a source only). One piece, so the owner's ticking expand/contract is a pulse of the whole body and its glow. |

## Batch 05 (2026-10-31, 1 model)

| # | File | What it is (from the render) | Tris | Use |
|---|---|---|---|---|
| 18 | ammo_canister | Gunmetal drum with olive bands and orange trim, "MAX AMMO" embossed, red side lights | 4.6k | **Max Ammo**, the common refill drop (the last missing model). Cleaned as `PU_18_MaxAmmo` (45 cm). Distinct from the green "UNLIMITED AMMO" can (#1, the rare drop). |

Note: "Max Ammo" is also the Call of Duty power-up name and it is embossed on this model; the no-COD-names rule was
set for perks. Owner to decide whether the label stays.

## Owner design (2026-10-31, from the numbered sheet)

The owner numbered the 15 tiles in order, so from the eighth tile on the owner's number is one less than the
catalogue number (catalogue #8 was the duplicate flask). This table supersedes the earlier proposals.

| Cat. # | Owner # | Model | Owner's design | Kind |
|---|---|---|---|---|
| 1 | 1 | Ammo can | Unlimited ammo for 30 s; uncommon random drop (rarer than Max Ammo); does not consume normal ammo while active | timed power-up |
| 2 | 2 | Stone tower | **Curse**, 30 s: elemental and magic power on your attacks, more damage and occasional area effects (Blood Magic VFX fits) | timed power-up |
| 3 | 3 | Gold-star shield | 10 s of total invincibility | timed power-up |
| 4 | 4 | Hourglass | 30 s: time slows for zombies and everything except the player, including the car or board she is driving while she controls it | timed power-up |
| 5 | 5 | Loot crate | Armour box: adds armour to inventory, if armour is added later | pickup (later) |
| 6 | 6 | Medkit | Health canister: max health for all players plus 30 s of faster healing (multiplayer-ready wording) | timed power-up |
| 7 | 7 | Eyeball | Zombie eye, perfect vision: every zombie gets a red glowing outline, and weather or any effect that hurts visibility is greatly reduced | timed power-up |
| 9 | 8 | Stone skull | Zombie boss totem, 60 s: a zombie boss / high-value target spawns and fights on your side, strong, takes out a lot; when its rampage ends it turns on you and you must defeat it | timed power-up |
| 10 | 9 | Tactical vest | Max armour | pickup |
| 11 | 10 | Energy cell | 30 s unlimited sprint, movement speed +25 % | timed power-up |
| 12 / 17 | 11 | Radiation canister (model #17 from batch 04) | **Nuke**: animated, expands and contracts like a ticking bomb; picking it up kills every spawned zombie and greatly damages a high-value target (bosses survive) | instant power-up |
| 13 | 12 | Radiation sphere | **Toxic gas** tactical: throw a gas sludge bomb that melts zombies in an area for 60 s in one spot (acid death) | tactical (equipment slot) |
| 14 | 13 | Medical crate | Health pickup: recover 20-25 % health instantly; more common than the power-ups | pickup |
| 15 | 14 | Clover flask | Gas can: fuel for the hoverboard and cars, if they stay and need fuel to be fair (maybe) | pickup (maybe) |
| 16 | 15 | Trap pod | Silk spider drone, a tool with modes (owner 2026-10-31, tabled, not designed): mini-nuke hunter (seeks a zombie, area explosion); a temporary electrical defence field that protects; a healing pulse that sends several waves over time and heals all nearby players. A pickup grants a charge; also in the shop | tactical tool / shop |

Notes for implementation:
- Most power-ups are 30 s timed effects with a HUD timer; the vendor already has `ActivatePowerUp(Type, Duration)`.
  New effect types are needed for unlimited ammo, Curse, slow time, perfect vision, invincibility and the boss totem.
- Owner 2026-10-31: these are suggested concepts per item; mechanics get fine-tuned later. Leave the current build
  as it is (the Nuke presentation in progress stays as built; the boss-sparing rule and the ticking animation come
  with the power-up pass).
- Max Ammo stays as a separate drop (vendor refill) and is the MORE COMMON one; the 30 s unlimited ammo (ammo can) is
  the more uncommon one (owner, corrected 2026-10-31). Its model is #18 (batch 05).
  Insta-Kill has no model in the owner's design.
- Slow time must exclude the player and the vehicle she controls (custom time dilation on both).
- Perfect vision needs a custom-depth outline pass for zombies and a hook into the weather system's visibility.
- The boss totem reuses the boss roster (Stone Golem, Giant Kid) with a temporary friendly team.

## Implementation plan

Now: import the models for the effects that already exist or are being built (Nuke, health pickup, ammo), decimating the radiation canister first (Interchange glTF, textures at 1K, they are small on screen), build the hologram
master material and one instance per colour, and bind each vendor type to its model and colour in NYC Survival. This
waits for the current integration run, because that run edits `AHoverCyberPowerUp` for the Nuke presentation.

Later: the nine "later" ideas each need a new effect, station or shop entry. Their models stay catalogued here until the owner picks.
