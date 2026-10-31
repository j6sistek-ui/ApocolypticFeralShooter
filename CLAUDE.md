# AFS: working rules for every chat

AFS is a UE 5.8 zombie shooter prototype (module `HoverFlight`, mode in focus: NYC Survival). This repo keeps
design, issues, needs and context; content stays on the owner's machine.

## The two lists (most important)

- `Docs/BACKLOG.md` holds only open work: bugs, the ranked to-do list, decisions waiting on the owner. Every idea,
  bug or piece of feedback goes in the same day, ranked, and is pushed.
- When the owner raises something that is not game-breaking, confirm where it ranks. When the owner asks for it now,
  name the current top task and confirm pulling the new item ahead of it before starting. Game-breaking bugs go
  straight to the top.
- When work is done, remove it from the backlog and add it to `Docs/DONE.md`: what to check in game and how it was
  validated. The owner ticks it after playing, or it goes back to the backlog with the note. No stale done items.

## Read for context

`Docs/SCOPE.md` (what the game is), `Docs/RULES.md` (owner rulings), `Docs/CONTINUITY.md` (build, run, scripts,
proof folders), `Docs/LESSONS.md` (what already went wrong), design in `Docs/NYC_ZOMBIE_SURVIVAL_DESIGN_20261029.md`
and `Docs/POWERUP_CATALOG.md`, packs in `Docs/ASSET_KITS.md`. `Docs/Archive/` is history only.

## Working rules

- Prove changes in a rendered offscreen run with a receipt and stills; the owner judges feel in game.
- Never build or run the editor while another AFS editor is open; one AFS Unreal process at a time.
- Never commit Content, SourceAssets, Saved, Binaries, Plugins or local config. Docs commits need no approval; push
  source after a green build and proof. Never auto-merge.
- Never edit vendor or other-map assets in place: duplicate into `/Game/HoverPrototype/`. Patches to compiled
  plugins carry an `AFS <date>` comment.
- No Call of Duty names. No animation invented from scratch when a pack clip exists.
- Keep it simple: short docs, no new process unless the owner asks for it.
