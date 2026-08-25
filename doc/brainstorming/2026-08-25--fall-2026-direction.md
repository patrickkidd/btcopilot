# Fall 2026 direction (brainstorm, 2026-08-25)

Status: nothing decided. Forks in §4 become `decisions/log.md` entries when ruled. Full evidence trail: git history of this file (commit 0a5a6bd).

## 1. Where things stand

- Last engineering: Jul 23 (Gemini 3.6-flash switch, deployed; agg 0.65→0.70, events 0.41→0.54). Break = 5 weeks.
- **Jun 24 ruling, on record, forgotten:** rebuild hit a ceiling on Patrick's own family; "stop tuning extraction on AI-residue data"; pivot to human-in-the-loop corrections in chat = FD-339 (grounded, 7 reqs, never started).
- Jul 21 test of own diagram: duplicate of Patrick, self-parent bond, self-marriage, two Connies, blank single-token labels, wrong ancestor. Never ticketed.
- Paused: FD-340 PySide6 port (draft PR, 7 decisions). Not on the iOS critical path — PyQt5 iOS builds work.
- Stalled: IRR (no meeting since Apr 27, no kappas); FD-318 MVP done condition untouched; retrospective's one follow-up experiment (Mar-4 prompt on 3.6-flash — SARF fell 0.64→0.39 Mar→May) not run.
- ~25–30% of Jun–Jul session volume went into the workstream skill itself.

## 2. Recollection vs record

| Claim | Verdict |
|---|---|
| Tested chat with one conversation only | Wrong — own diagram has ≥3 sessions; that data was the test bed. True gap: nobody has *lived* the return loop (weeks later → new session → extract adds to diagram) and judged the feel. |
| Making incremental progress on diagram generation | Wrong — ceiling declared Jun 24; pivot to corrections already ruled. |
| "Diagram generation" is the blocker | Two problems conflated: structural correctness (unsolved; record) vs auto-arrange (shipped in Pro May 4; Aug article calls it "the last bug"). Contradiction — fork 1. |
| GT too sparse/synthetic → ceiling | Supported: real-family failures (same-first-name men cross-matched, same-last-name welds, ex-partners, speaker identity) are exactly what scripted personas never exercise; benchmark stopped discriminating ~0.7. Twist: what fell since March is SARF, not structure. |
| Beta testers will generate real data | Unverified — non-Patrick conversation count unknown (Jul 12 prod dump at `fdserver/prod.dump`; Docker was down). |

## 3. Direction

**Recommendation:** long-horizon chat loop as the MVP; diagram correctness via corrections in chat (FD-339, user-initiated only), not extraction tuning. Fence the two failures that break accumulation itself (duplicate self, self-bonds) as commit invariants first. Park FD-340, Personal auto-arrange, FD-336, workstream tooling.

Why this isn't echoing the prompt: it restates the Jun 24 ruling; it contradicts the intuition that diagram quality can "start terrible" (two failures break the loop); it replaces IRR self-coding with cross-coding.

**Unrebutted case against it:** "chat is useful" is n=1 (Patrick). Retention of returning users is unmeasured. Kill condition: seminar testers don't return in the Dec block.

**Chat + timeline App Store MVP** (Patrick, round 2): narrows scope correctly; no port needed. Does not escape: (a) accuracy target moves to the *weakest* metrics (events 0.54, SARF 0.39); (b) timeline stores up/down/same deltas and cannot draw a trend — design gap ahead of extraction; (c) strangers' mental-health chat = consent-for-research, retention, health-category review, liability framing; (d) **coder throughput, not data volume, is the GT bottleneck** (6 IRR meetings ≈ 10 statements).

**Corrections as GT:** structural error labels for real families, user as oracle. Not SARF GT; negative-biased (the "rest was right" half rests on lazy card acceptance, ruled unreliable Jun 9).

**Beta/coding agent seed (separate session):** highest leverage = training-app coding agent with tools + guidelines-as-manual so coders judge instead of click (coding advisor exists in calibration pages). Tester feedback: one experience question at session end into a feedback table — outside the coaching transcript.

## 4. Forks (Patrick rules)

1. Blocker is structural correctness or auto-arrange? (Sep dogfood answers empirically.)
2. MVP = long-horizon chat(+timeline) in App Store, or clinician-in-Pro loop (FD-264 as written)?
3. FD-339 scope: user corrections only, or full bidirectional + ledger?
4. FD-340: park with trigger, or continue?
5. Tester GT: self-coding vs cross-coding; consent/de-identification protocol.
6. Aug article: publish "last bug = auto-arrange" as-is, or align with record?

## 5. Plan (each block gated on the prior's done condition)

| Block | Done condition |
|---|---|
| Sep wk 1–2: dogfood, no code — 3 return sessions on own diagram ≥3 days apart | Friction log; fork 1 ruled |
| Sep–Oct: fence return path (reject identical-endpoint bonds, self-parenting, speaker weld, flat-name labels) | 3-session dogfood with zero structural errors on the user node |
| Oct–Nov: FD-339 MVP (user corrections → reviewable structural edits, persisted as GT) | Own diagram corrected to "my family" via chat alone; 32-assertion GT passes |
| Dec–Feb: 3–5 seminar testers on the return loop (consent first) | ≥3 testers × ≥3 sessions; real-case GT v2 exported |
| Feb–Mar: run the SARF experiment; re-baseline on GT v2 | Decision logged: reopen extraction tuning or keep frozen |
| Mar–May: cross-coded IRR on real cases; FD-318 only if diagrams coherent | Kappas for one real case; App Store go/no-go with evidence |

## 6. Housekeeping (Patrick's git)
Remove 11 stale worktrees (keep FD-340, this one); commit/discard familydiagram M5 build fixes, pkskills, article; close fdserver PRs #6/#15; ticket the Jul 21 bugs (Claude can file on request).

## 7. Round 3 — chat as the only UI (Patrick thinking out loud, 2026-08-25)

- **Claim:** agent with diagram-edit tools (Micron "builder door" pattern) becomes the UI; diagram = derived view; drop manual arranging. **Holds:** FD-339 already covers dedupe/split/re-parent by chat. **Breaks:** correctness ≠ layout; layout on correct data is median-good/p95-bad with multiple right answers. Derived vs authored (Bowen tradition authors placement) is the real fork.
- **Salvage:** persist arrangement as **constraints** ("maternal side left", "keep A adjacent to B"), not coordinates; deterministic render; a manual tweak = a chat edit; nothing flushed. Personal app: clean. Pro: file-format migration of hand-placed coordinates — separate project with rollback.
- **Guardrail from record:** narrative extraction stays batch (single-prompt beat per-turn delta 2×, Feb 24); explicit user edits become tool calls. FD-339 R4 is that line. Don't let the agent extract implicit facts turn-by-turn via tools.
- **Prereq either way:** incremental single-person placement (deferred May 4) for live diagram-while-chatting.
- Voice: input + read-aloud exist; voice-only deferred (correction precision).
- Evidence base is n=2 warm testers (Patrick, Guillermo); non-sycophantic metric = unprompted return. Don't invite the working group before the return path is fenced (Sep–Oct) — first impression on their own families would be the Jul 21 bugs.
- **Candidate ruling for forks 1+2 (not decided):** MVP = chat + timeline; diagram derived with constraint hints, Personal only; Pro keeps authored layout.

## 8. Round 4 — local arrangement by the agent, reference resolution, voice (2026-08-25)

- **Local arrangement:** agent tools emit *relations/constraints* ("X next to Y", "maternal side left", sibling order), never coordinates; a deterministic engine re-places only the touched neighborhood after each structural edit. Rules: move only what the edit invalidated; no global reflow from chat; animate; deterministic replay. Prereq = incremental single-person placement (deferred May 4).
- **Read-before-write / collisions:** reuse snapshot-diff merge + server-side ids (May) and version-checked write-back (FD-338). Agent = third writer through the same merge path; conflict → re-read, re-apply.
- **Reference resolution (agentic-dev patterns that survive non-technical users):** selection-as-context (ids into the turn); model cites entities as tappable chips that halo items (FD-310 exists); tap-to-disambiguate for clarifying questions (FD-339 dir. A with a UI answer path); neighborhood context not whole diagram; commit invariants as post-edit guards with retry (FD-329 pattern); one turn = one undo step; trust tiers (auto-apply + highlight + undo for low-risk; confirm for re-parent/merge) instead of diffs; suggestion chips. **Doesn't transfer:** textual diffs, per-edit plan gating, anything requiring the user to read structure.
- **Voice:** April eval — poor voices are a macOS artifact (iOS uses Apple neural voices); Gemini TTS rejected for no streaming (5–20 s gap). Order: verify on iPhone → sentence-chunked streaming TTS with any premium provider → do NOT adopt realtime speech-to-speech (binds chat to vendor model, breaks Opus-for-chat + prompt-IP boundary). ~$18/user/mo at heavy use = free-tier problem. Typing stays an equal citizen. Voice raises ambiguity → pointing/tapping is its enabler. **Ruled 2026-08-25: current voice is fine for now; revisit as improvement-vs-cost shifts.**
