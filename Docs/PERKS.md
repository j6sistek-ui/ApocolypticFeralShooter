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
- Open: is Life Blood itself lost after the revive like the other perks (re-buy to get the next use), and do the 3
  uses count across re-buys? Is the Second Wind name reused for another perk or dropped?
