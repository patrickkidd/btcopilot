# Chat-first rebuild — kickoff brief for the next session

Read [STATE.md](STATE.md) FIRST. Standing rules from earlier briefs still bind
(oracle store, content-blind for clinic data, plain words, TLDR first, decision
questions in ONE numbered list with inline examples, two-clocks upkeep,
adversarial review on every deliverable, batch sub-agent work into one message).

## Session — refine the pixel design into the full app

**Where it stands**: the basic concept is APPROVED in principle and pixel
convergence has begun. The living mockup is
~/fd-corpus/design/coach-screen.html (published artifact; job-tmp copy is
ephemeral — treat the fd-corpus copy as source, republish to the same artifact
URL). It has: generic phone chrome (status bar, no app header); the picture
pinned above the chat with per-level heights (rest wire ~78px with episode
clusters and amber ?s → tap-zoom cluster view ~158px with ✕ close → play-by-play
~264px with ← back) playing the RATIFIED move language
(~/fd-corpus/OWNER_RULINGS.md, 2026-09-01 entries — the standard for every
gesture); scripted coach chat with chips that aim the picture; typing adds a
moment to the wire; a test-record cycler OUTSIDE the phone frame (his record /
dense clinical / empty / pathological — keep all four working at every step).

**Goal**: Patrick iterates this into the complete app design — refine the core
concept AND add the app shell around it:
- session menu (past conversations, new session)
- preferences
- account view
- whatever else he directs — he drives, one surface at a time

**Method rules learned the hard way (follow them)**:
- Concepts regress to the happy path. Every change is walked against all four
  test records and adversarially reviewed BEFORE showing him.
- The rulings file is the standard, not any prototype. Log every new ruling he
  makes to OWNER_RULINGS.md immediately; visual language changes go through
  divergent options first — never converge unilaterally.
- Visual communication to him: show, don't describe; no tables; one-line
  captions; same-length loop animations; ONE green for all moves.
- Keep the fd-corpus copy and the artifact in sync on every edit.

**Open design questions carried in**:
1. One moment firing S+A+F+relationship plays as several board steps with the
   same caption — collapse to one composite step, or keep per-dimension?
2. Symptom visual is interim (cross + up/down arrow) — revisit when he says.
3. Episode clustering over-splits vs his hand count (JoseJ: 4 vs his 3).

**After his sign-off on the full design**: the build session (chat against the
real diagram on the FD-360 worktree, loop-engineering signal logging server-side
— see STATE.md for the sandbox command and PR #133).
