# AFS: perks (Phase 1 design, in progress)

The owner drafts the perk ideas; this file holds them with the design notes until each is settled. Rule: familiar
jobs (players should recognise what a perk machine gives), original names, fiction and twists; no Call of Duty names
or copied numbers. Numbers come from `NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md` (2,500 + 500 per perk owned) and get
tuned in play.

Working slots from 2026-10-29 (being replaced by the owner's drafts below): Second Wind (revive) -> Life Blood,
Ironhide (max health) -> Necrosiphon, Fast Lane (reload), Bullseye (aim and
headshots), Hair Trigger (fire rate), Marathon (stamina).

## 1. Necrosiphon (owner draft, 2026-10-31; first called Necroflora): the health perk

**Owner's idea.** Killing zombies makes them release the soul of their lost human host. Walking over a soul overheals
Vexa, a little per soul, up to 2x normal health. Souls only overheal when she is at full health, not when she is
damaged, so standing in a pile of zombies does not keep her topped up. Fiction: the souls merge with her human
existence and give their last moments to help her survive. Adapted from the familiar "more health" perk.

**Owner follow-up (2026-10-31):** also +20 % health recovery rate. Reasoning: like the familiar max-health perk, once
you are low it does not matter where you started, so the souls stay an at-full-health overcharge and the regen buff is
what helps while hurt ("gives it a better home"). This answers the "does nothing when hurt" note below.

**Design notes (AI, for the owner to accept or reject):**
- Strong fit: original fiction, a visible pickup that rewards aggression and pulls the player through the kill zone
  (risk and reward), and it reuses ghost / blood-magic VFX already on disk.
- Gap (answered by the owner's +20 % regen): with souls only working at full health, the perk did nothing at the
  moment the player is hurt. Options: (a) a small passive max-health bonus as the familiar base, with souls stacking
  overheal on top; (b) souls picked up while hurt are banked and turn into overheal once health is full again (keeps
  "no healing inside the pile").
- Overheal should decay slowly or only last the round, otherwise players bank 2x permanently.
- Overheal is lost first when hit, shown as a separate layer on the health bar in the soul colour.
- Not every kill should drop a soul (a chance, more from specials and bosses); souls live a few seconds and drift to
  her within about 1.5 m so it never becomes tedious collecting.
- Name: Necrosiphon (owner, 2026-10-31; typed "Neceosiphon", spelling to confirm), replacing Necroflora: it siphons
  the hosts' souls.
- Open: does it replace the Ironhide slot? Souls per player or shared in multiplayer?

## 2. Life Blood (owner draft, 2026-10-31): the revive perk

**Owner's idea.** Revive teammates faster. A second chance when downed: in solo it brings Vexa back up; in
multiplayer it covers not being revived in time. Works 3 times per match. After a Life Blood revival you lose your
perks but keep your guns and gear. In multiplayer, a normal death (no Life Blood) respawns you the next round with the
match's starting loadout, regardless of difficulty, and without the perk. The owner's own note: "basically the
familiar quick-revive perk, but it's necessary".

**Owner answers (2026-10-31):**
- Downed state comes first. Solo: with Life Blood you are revived a moment after going down; without it the run
  ends.
- While downed you can crawl and shoot. That has nothing to do with the perk: in multiplayer anyone downed can crawl
  and shoot as long as someone is still alive.
- Revived player: revived by someone without Life Blood, no buff. Revived by someone with Life Blood, the revived
  player gets 3 s of shielding to find their feet and run.
- Revive speed: 2x.
- Life Blood replaces the Second Wind working name (Second Wind was the 2026-10-29 placeholder for the revive slot).

**Design notes (AI, for the owner to accept or reject):**
- Familiar on purpose is right here: players look for a revive perk and its job should read instantly.
- Small twists that make it AFS without changing the job: the revive shown as blood (the Blood Magic pack: her own
  blood pulls her back up), a short blood shockwave on a self-revive that pushes nearby zombies back so the second
  chance is not instantly lost, and the 3 uses shown as three blood vials on the HUD.
- Owner (2026-10-31): "same name, the indicator can get a small sub indicator (red x in corner of it)". Read as:
  after a Life Blood revival the perk keeps its name and its HUD icon stays, with a small red X in the icon's corner
  marking the spent use.
- Owner (2026-10-31): "once it's all spent you get the passive effects, not the continuation security". So Life Blood
  keeps working for its remaining uses; after all 3 second chances are used it stays as a passive perk (2x revive
  speed, the 3 s shield it gives the players you revive) and no longer brings you back. The red X marks that state.

## 3. Headhunter (owner draft, 2026-10-31): replaces the reload perk

**Owner's idea.** Instead of reloading faster: magazines last twice as long, and headshots return ammo into the
active magazine.

**Design notes (AI):** keeps the familiar job (less time spent reloading) by a different route, which is a good
original twist. "Twice as long" can be each shot costing half a round (the magazine shown stays the same size) or a
50 % chance a shot costs nothing; the first is steadier. Headshot refund: +1 round per headshot, capped at the
magazine size. It rewards accuracy, so it overlaps the aim / headshot slot (Bullseye); worth deciding whether that
slot still exists. Interacts with the unlimited-ammo power-up (no effect while it runs).
Name: Headhunter (owner, 2026-10-31).

## 4. Survivalist (owner draft, 2026-10-31): replaces the stamina perk

**Owner's idea.** Movement speed buff (exact numbers once the Life Engine has been tested), melee strength buff, and
carry one extra lethal and one extra tactical.

**Design notes (AI):** three jobs in one perk, so it is the generalist's pick; keep each buff modest (for example
+10 % speed, +25 % melee) so it does not become the automatic first buy. Speed applies to both movement modes (the
solver's max ground speed and Classic's walk/sprint). Overlaps the energy-cell power-up (unlimited sprint, +25 %
speed): the power-up should stack on top so it still feels like a burst.

## 5. Bioreactor (owner draft, 2026-10-31; name tentative): a passive damage perk

**Owner's idea.** Sliding into zombies damages them and can knock them down. Walking over blood makes footsteps send
small shockwaves for a few seconds: a slight local area ripple of damage. A passive, low-impact bonus that adds DPS,
not meant to be lethal.

**Design notes (AI):** gives the slide and the blood a purpose and fits the gritty-playful tone. Needs: the slide
(the parkour template's slide, B) to report hits; a record of where blood lands (the death splashes already spawn
there) so footsteps can check "on blood"; a short cooldown per zombie so the ripple cannot chain into a kill
machine. Knockdown chance lower on Brutes and bosses. The ripple can reuse the Vefects shockwave at a small scale.

### Reference: the familiar perk it spins off (Black Ops 7 PhD Flopper, researched 2026-10-31)

- Base: immunity to self-inflicted damage and status effects; diving to prone sets off an explosion that grows with
  the fall height.
- Augments (one major and two minor active per match): PhD Slider (sliding into enemies explodes), Double Whammy
  (a second explosion follows), DR Ram (sprinting into normal enemies knocks them down and damages them), EOD
  Technician (lower height and distance needed for explosions), Tribologist (longer, faster slides), Stuntman (wall
  jumps explode), Gravity Doctor (even small falls explode).
- Sources: Dot Esports "All Perk-a-Colas in Black Ops 7 Zombies"; Call of Duty blog "Black Ops 7 Zombies Augments";
  U4GM and The Filibuster Blog augment guides.

**How Bioreactor differs (AI notes):** the slide hit and knockdown overlap PhD Slider and DR Ram; the blood-footstep
ripple has no counterpart and is the original part. To keep it a spin-off: biology instead of explosions (blood
waves, bio pulses), and the movement hooks AFS has that the familiar perk only gets through augments: wall runs, wall
jumps and landings from the Life Engine and parkour (a blood pulse on a hard landing). Worth borrowing in AFS form:
immunity to your own area damage (grenades, the toxic gas bomb, the spider drone's blast), since PhD's base job is
"your own explosives can't hurt you". Upgrade tiers later could mirror the augment idea without copying names.

## Slots so far

Health: Necrosiphon. Revive: Life Blood. Reload: Headhunter. Stamina: Survivalist. New
passive damage: Bioreactor. Still holding working names: Bullseye (aim and headshots) and Hair Trigger (fire rate).
With five drafted, one more makes six; decide whether it is Bullseye, Hair Trigger or something new.

## Machines (owner concept art, 2026-10-31)

Preliminary concepts for five machines (local copies in `Docs/References/PerkMachines/`, not in git): Bioreactor
(dark tech tower, cyan bubbling liquid tube, brain "perk active" screen), Survivalist (rusted olive military vending
unit, CRT biohazard screen, green formula canister on pipes), Lifeblood (burgundy and brass cabinet, glowing anatomical
heart, blood cylinder, coin slot), Headhunter (gunmetal jukebox shape, laurel skull crest, blood-streaked tube with a
crosshair skull), Necrosiphon (spiked dome, green tentacle tank, skull and tentacle relief, swirl porthole).

The owner is remaking them in Tripo as subcomponents, optimising first, then cleanup with the AI. Notes for that
pass: keep each part a separate mesh (body shell, glass tube, inner liquid or creature, screen panel, sign plate,
hoses, dispense tray) so the glass and liquid get their own translucent and emissive materials and Niagara (bubbles,
swirl, heartbeat) can live inside; signs and screens as flat panels so text and screen content can be swapped without
re-modelling; one shared real-world scale (about 2.1-2.4 m tall, like a vending machine), front on -Y, pivot at the
bottom centre. The concept art's own text (taglines, the Survivalist dial labels) is placeholder.

Open: "Lifeblood" (one word, as on the machine) or "Life Blood"?

### Lifeblood machine assembled (2026-10-31)

Four owner parts, separate meshes, 2.2 m, pivot bottom centre, 13k tris total (`Scripts/Blender/AssembleLifeblood.py`,
outputs `SourceAssets/PerkMachines/Lifeblood/Clean/`; renders `D:/AFS_Comparisons/PerkMachines_20261031/Lifeblood/clean/`).
Body, blood core (with a glow mask `T_Lifeblood_Core_Emissive` for an Unreal pulse), coin panel, tagline plate.
Reads like the concept. Known gaps from the source meshes: the core fills about 55 % of the window (the concept about
75 %), rails dark metal not brass, five rods baked in the cabinet show behind the core, the side panel text is garbled
in the cabinet texture ("LIFEPAOON"), the coin panel sits proud like a box. Not in Unreal yet.
