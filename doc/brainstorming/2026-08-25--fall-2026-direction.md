# Fall 2026 direction (brainstorm, 2026-08-25)

Status: **fork 2 ruled 2026-08-25 → alternative (returning long-horizon chat; diagram improved through chat).** Logged in `decisions/log.md` 2026-08-25. Forks 1/3/4/5/6 still open (fork 1 and 4 effectively follow from the ruling: structural correctness is the blocker; FD-340 parked). Jira: epic **FD-341** (first beta), 5 children: FD-336 → FD-339 → FD-351 → FD-352 → FD-353 (FD-342 dogfood folded into FD-339's human walk, 2026-08-26). FD-264 left open for Patrick to close. **2026-08-29 pivot:** chat-first web app runs as a PARALLEL epic — see `2026-08-29--claude-code-for-family-diagram.md`; FD-336's role as first chat surface is superseded there. Full evidence trail: git history of this file (commit 0a5a6bd).

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
2. ~~MVP = long-horizon chat(+timeline) in App Store, or clinician-in-Pro loop (FD-264 as written)?~~ **RULED: long-horizon chat; clinician loop → next epic.**
3. FD-339 scope: user corrections only, or full bidirectional + ledger?
4. FD-340: park with trigger, or continue?
5. Tester GT: self-coding vs cross-coding; consent/de-identification protocol.
6. Aug article: publish "last bug = auto-arrange" as-is, or align with record?

## 5. Plan (each block gated on the prior's done condition)

| Block | Done condition |
|---|---|
| Sep: FD-336 embed Personal app in Pro (full, as scoped) — chat beside the canvas | Patrick chats in Pro, extracts, sees the change on the diagram |
| Sep–Oct: fence return path as commit invariants (identical-endpoint bonds, self-parenting, speaker weld, flat-name labels) | 3-session dogfood with zero structural errors on the user node |
| Oct: incremental single-person placement + local neighborhood re-place (engine under every chat-edit) | New person from a return session lands next to its anchors without a global reflow; no overlap on own diagram |
| Oct–Nov: FD-339 vibe-code the diagram in Pro — phases: 0 guards + speaker identity, 1 full CRUD + trust tiers + undo + GT log, 2 pointing UI, 3 placement + arrangement hints, 4 agentic-extraction spike | Own diagram corrected to "my family" via chat in the Pro drawer; 32-assertion GT passes; spike decision logged (replace / split / keep hybrid) |
| Dec–Feb: 3–5 seminar testers on the return loop (consent first) | ≥3 testers × ≥3 sessions unprompted; real-case GT v2 exported |
| Feb–Mar: run the SARF experiment; re-baseline on GT v2; timeline trend (level vs delta) design | Decision logged: reopen extraction tuning or keep frozen |
| Mar–May: cross-coded IRR on real cases; App Store go/no-go; clinician loop becomes next epic if diagrams coherent | Kappas for one real case; go/no-go with evidence |

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

## 9. Round 5 — architecture B ruled (2026-08-25)
- Chat can only add today (FD-342 finding). B = one authoring tool surface (person/parents/bonds/events/SARF/merge/split/arrangement hint) used for corrections with full CRUD; FD-349/350 absorbed into FD-339.
- Narrative extraction stays batch until FD-355 spike measures agentic extraction (read-before-write, guard feedback per call) against it. Burden of proof on B (Feb 24: per-turn deltas lost 2x).
- Personal app has no diagram view; testers have both devices (phone chat, desktop diagram). FD-336 (full embed) ranked first — Patrick: well-scoped, not weeks; tickets consolidated to 5 journey-shaped workstreams: FD-336 → FD-339 → FD-351 → FD-352 → FD-353 (343–350, 354, 355 folded into 336/339 and deleted; text preserved in the absorbing tickets). Personal-app diagram concept = separate design story, off the critical path.
- FD-348 calibration: does not improve the layout engine; supplies topology decisions + persistence. ~60% acceptable after ≤3 hints on 30-person families.

## 10. Round 6 — "Claude Code for Family Diagram" (2026-08-26)
- FD-339 gains a `read_manual(section)` tool: SARF model + event semantics (from fdserver extraction prompts), Bowen concepts, app usage. Architecture (per-turn tool vs cached system prefix vs both; sectioning; single source of truth with extraction prompts) = design brainstorm with Patrick before build.
- Two writers: batch extraction = proposals accepted in the review sheet, F1-validated, unchanged. Agent writes only what the user asked for or said yes to; PDP reused as the inline approval (negative-id item, one-line question + tap); trust tiers. Edit log records what the user did; how those records become accuracy labels is deferred to FD-353 (side thread, not load-bearing). Design terms (oracle, ratification) stay out of user-facing language.
- Dedup on record: FD-319 same-conversation re-extraction 10/10 → 0/10 (N=10, flash+pro) with carve-out + deterministic repair. Cross-session incremental resolution unmeasured; July two-Connies came from rebuilds. Double-write test required.
- ACs (human-authored/ratified): scripted SARF-CRUD conversation set with expected tool calls; ~30-item education/how-to question set with rubric; double-write 0/10; provenance on every write.
