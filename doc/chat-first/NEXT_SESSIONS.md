# Chat-first rebuild — kickoff brief for the next session

Read [STATE.md](STATE.md) FIRST. Standing rules from the previous briefs still
bind (oracle store, content-blind for clinic data, plain words, TLDR first,
one-list decision questions, two-clocks upkeep).

## Session — chat against the real diagram, with the ruled picture

**Goal**: Patrick chats with the coach against HIS real record and the pinned
picture above the chat is generated live from it: wire-with-episode-clusters →
tap-zoom into an episode → the moves played in the ratified move language. Every
interaction is logged (loop engineering). This is the first real loop.

**Inputs**:
- FD-360 worktree (~/theapp/btcopilot/.claude/worktrees/FD-360, draft PR #133) —
  working chat page + resting strip + sandbox on 8889 (relaunch command in
  STATE.md; real-record DB at /tmp/fd360-sandbox.db).
- The ratified move language: rulings in ~/fd-corpus/OWNER_RULINGS.md
  (2026-09-01, batches 1-3 + projection + anxiety-everywhere rule); reference
  HTML at ~/fd-corpus/design/move-language.html (galleries, ratified) and
  ~/fd-corpus/design/drilldown.html (three-level drill-down, KNOWN BUGGY — build
  against the rulings, not this file; its episode/zoom/step machinery is still
  the best starting sketch).
- His real diagram: prod dump in the fd-scratch-pg container (diagram 1924) or
  the FD-360 sandbox real-record DB; his master .fd file for the fuller record.

**Scope, in order**:
1. Port the three-level picture into the FD-360 page over the real record
   (episodes computed server-side from his events; zoom; moves in the ruled
   language, S/A/F moments included).
2. Fix the known gesture bugs against the rulings (his walk found: targetless
   cutoffs mis-drawn, zigzag wavelength, inside/outside reading as toward,
   arrow-tail bug; MORE EXIST — verify every gesture against OWNER_RULINGS).
3. Log signals server-side: taps, drill-downs, moves watched, corrections typed
   in chat (loop engineering ruling in decisions/log.md 2026-09-01).
4. He chats; corrections land in the record through the existing pipeline.

**Definition of done**: he can open the sandbox page, chat about his family, see
the wire update, drill into an episode, watch the moves play correctly per the
rulings, and every interaction row lands in a signals table he can query.

**Not in scope**: the clinical corpus (extraction still running under its own
thread), symptom's final visual (interim cross+arrow stands), genogram layout in
the play-by-play (circle + partner adjacency is the ruled fallback).
