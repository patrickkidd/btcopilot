# Fall 2026 direction — return-from-break assessment and 9-month plan (brainstorm)

**Date:** 2026-08-25
**Status:** BRAINSTORM / PLANNING. Nothing here is decided. Decisions get logged in `decisions/log.md` once Patrick rules on the forks in §6.
**Method:** Evidence reconstructed from git logs and PR bodies (3 repos), worktree timestamps, Claude Code session transcripts (Mar–Aug 2026), Jira FD project, and the docs on disk. Patrick's from-memory recollection was then checked against that record (§3). Timeline scope: March 2026 onward.

---

## 1. What actually happened, Mar → Aug 2026

| When | What | Evidence |
|---|---|---|
| Mar 2–14 | 2-pass extraction split; gemini-3-flash; Opus for chat; voice input; IRR meetings 3–4 | btcopilot #112/#113, retrospective R1–R3 |
| Apr 11–12 | FR-2 concurrent-write fix; **auto-accept decision** (skip PDP approval for MVP 1); dashboard consolidation | decisions 2026-04-12 |
| May 1–4 | MVP merge fix (FD-311); **deterministic auto-arrange shipped in Pro** (FD-245); **MVP dashboard retired → Jira FD-264** | PRs #114/#135; MVP_DASHBOARD header |
| May 16–26 | PDP re-extraction cursor + accept mechanics (FD-319/331/332/333/312); **returning-user coach** (FD-325/326); **connectivity repair** (FD-324, LCC 51→89%); import polish (FD-335); flash-lite model; app 2.1.23b3 | PRs #115–#123, #136–#145 |
| May 23–Jun 1 | Workstream-engine (the `/workstream` skill) brainstorm + plan | doc/brainstorming/2026-05-23--* |
| Jun 2 | **FD-337** windowed re-extraction + cross-session parent back-fill. Found a Pass-3 crash that had broken every prod extraction since May 21 (fix deployed Jun 25) | PR #124 |
| Jun 9–10 | claude-fable-5 experiment (rejected: 2–3 orders of magnitude cost); **FD-338 deep re-extraction (rebuild)** built; human walk on Patrick's own diagram (1924) → 5 structural errors, C12 human criterion not passed | PR #126, fd-338.json |
| Jun 11–24 | **FD-321** user identity (name/birth) wizard + feed into extraction; merged Jun 24 | PRs #127/#148 |
| Jun 24–26 | **FD-338 merged** with the human criterion only partly cleared (proxy run: proband triplication fixed; wrong parents / missing brother / nephew-on-wrong-uncle NOT cleared). **FD-339 "conversational family editing" ticketed as the answer to the rebuild ceiling.** | PR #125/#147, FD-339 |
| Jun 9–Jul 14 | Workstream skill development in `~/pkskills` (CI-green merge gate, guards); Jul 13 "workstream cockpit" brainstorm | session d5d79a5b (6.5 MB), pkskills uncommitted |
| Jul 11–12 | Migrated to M5 laptop (dev app runs x86 under Rosetta); **FD-340 PySide6 port** started and paused the same day — draft PR #149, 7 decisions blocking | familydiagram #149 |
| Jul 21 | Manual test of rebuild on own diagram → **two Connies, self-parent bond, self-marriage, "Client" duplicate of Patrick, blank single-token labels, Robert Kidd misplaced.** Triage done; **never ticketed.** | session a17b40d6 |
| Jul 22–23 | **gemini-3.6-flash switch** (agg 0.652→0.704, events 0.413→0.544; E4 scorer era); retrospective series on one ruler. **Deployed to prod Jul 23.** | PRs #128/#129, fdserver #25/#26 |
| Aug 19–22 | "State of the App 2026" article drafted (uncommitted). Names auto-arrange as "the last bug." | doc/state-of-the-app/ |

**Break length:** 5 weeks of no engineering (Jul 23 → Aug 25), not "a few months." Context is fresher than it feels.

**Production state:** master of btcopilot + fdserver deployed Jul 23 (3.6-flash extraction live). App at 2.1.23b3 (May 20).

---

## 2. Open workstreams (what was actually in flight)

| Item | State | Where it lives |
|---|---|---|
| **FD-339 conversational family editing** (clarifying questions + "vibe-coding the family") | To Do; grounded with 7 requirements; explicitly next in line as of Jun 26; never started | Jira FD-339 |
| **FD-340 PySide6 port** | In Progress, paused Jul 12; mechanical pass done (169 files), runtime-unverified; 7 owner decisions block the dependency flip | familydiagram PR #149; `~/worktrees/FD-340` |
| **Jul 21 bug list** (dup people, self-bonds, Client dup, blank labels, wrong ancestor) | Triaged in chat, **no tickets** | session only — see §5 |
| **FD-338 findings F-001…F-015** (14 still open, incl. Client-dup, cross-name merge, wrong-parent weld) | Open, deferred to "follow-up tickets after the walk" that were never filed | `doc/workstreams/fd-338.json` |
| **FD-318 beta test pass** — the FD-264 MVP done condition (one warm clinician + one real client) | To Do, untouched since May 18 | Jira |
| **Retrospective follow-up experiment**: run the Mar-4 prompt on 3.6-flash (SARF macro fell 0.638→0.39 Mar→May and never recovered) | Not run | retrospective report finding 3 |
| **Auto-arrange in the Personal app** (incremental placement + `/arrange` endpoint) | Deferred since May 4; Pro-only today | auto-arrange plan §Open Problems |
| **IRR study** (Sarah + Arthur round 1) | No meeting since Apr 27; kappas never computed | `doc/irr/PROGRESS.md` |
| FD-336 embed Personal app in Pro; FD-327/330/328 intake-coverage UI | To Do | Jira |
| Workstream skill (pkskills) | 10 uncommitted files (CI-green gate) | `~/pkskills` |
| State of the App article | Uncommitted draft | `doc/state-of-the-app/` |
| Housekeeping | 12 worktrees on disk: 5 `retro-*` (disposable), 7 for merged tickets (FD-312/321/324/332/335/337/337-windowing/fable-5/gemini-3.6) removable, FD-340 keep. fdserver PRs #6/#15 stale since March. familydiagram origin clone has uncommitted M5 build fixes (CMake qmake pin, native dist rename). | — |

---

## 3. Adversarial check of Patrick's recollection

| Recollection | Record | Verdict |
|---|---|---|
| "A few months away" | 5 weeks since last code; 3 days since last writing | Overstated; little context is stale |
| "Only tested chat with a single conversation" | Own diagram 1924 has ≥3 discussions (55/58/60) built up over time; FD-337/338 were measured on exactly that multi-session data | **Partly wrong.** Multi-session *data* exists and was the test bed. What is true: nobody has lived the *returning* loop (open app weeks later → new discussion → chat → extract adds to existing diagram) and judged how it feels. The returning-user coach (FD-325/326) was validated by harness/REPL only. |
| "We wrote multi-session extraction code but I don't remember testing it" | Incremental extraction into an existing diagram is where fragmentation was measured (56% connected on 1924). The chosen fix was **rebuild** (FD-338), not fixing incremental. Rebuild then hit its own ceiling on Patrick's family. | **Correct instinct, wrong target.** The incremental return path is the untested one and it is the one that matters for the long-horizon use case. |
| "We were making incremental improvements on diagram generation; hard to tell when I was in a rabbit hole" | Jun 9 + Jun 24 decisions: rebuild measured out at a ceiling (recall/precision trade-off, merges reintroduce duplicates); ruled "stop tuning on AI-residue test data"; pivoted to **human-in-the-loop corrections (FD-339)**. | **The pivot already happened and was forgotten.** The record agrees with today's intuition: extraction alone won't get the family right; the chat is the correction surface. |
| "Diagram generation was the hangup for beta testers" | Two different problems are conflated: (a) *structural correctness* of the extracted family (people/bonds/parents) — unsolved, 5+ errors on Patrick's own family as of Jul 21; (b) *visual auto-arrange* — shipped in Pro May 4, never wired into Personal. The Aug article calls (b) "the last bug"; the engineering record says (a) is the blocker. | **Unresolved contradiction — needs a ruling (§6 fork 1).** |
| "GT too sparse and synthetic to get past the ceiling" | 6 synthetic discussions, Patrick sole GT source (decision 2026-02-24). Retrospective: the Mar→Jun era optimized idempotency/connectivity, and SARF quality dropped ~0.25 on a fixed ruler — likely prompt drift, not GT. | **Half right.** GT is sparse/synthetic, *and* there is a cheap un-run experiment that may recover SARF without new GT. Also: a real-case structural GT already exists — 32 edge assertions on diagram 1924 (Jun 24). The "second-generation GT" idea has a seed. |
| "Recent F1 improvement from the flash upgrade" | Confirmed, deployed Jul 23 | Correct |
| Not mentioned at all | FD-340 port (paused, 7 decisions), ~25–30% of Jun–Jul session volume spent on the workstream skill itself, the unticketed Jul 21 bugs, IRR stalled 4 months, FD-318 untouched, the uncommitted article | Blind spots |

**Rabbit-hole audit (by session volume, Jun–Jul):** FD-338 rebuild ~10 MB across sessions; workstream tooling ~6.5 MB + cockpit brainstorm; FD-321 5.5 MB; extraction experiments 2.7 MB; FD-340 1.4 MB. Tooling was the second-largest sink. Whether that pays off depends on whether the Fall plan runs many parallel tickets (it shouldn't — see §4).

---

## 4. Direction options for Sep 2026 – May 2027

Framing constraint from the record: **no automated extraction setting produced a correct family for Patrick's own diagram.** Any plan that requires a correct diagram *before* a human touches it is betting against three months of measurement.

### Option A — Long-horizon dogfood: chat is the product, corrections are the diagram fix
The user (Patrick first, then app-seminar testers) returns at will over weeks/months, chats about what's happening, and the diagram/timeline accumulate. Diagram correctness comes from the user correcting it in chat (FD-339 direction B), not from extraction tuning. Every correction is a real-case GT assertion by construction (FD-339 R5 already says so).

- Matches Patrick's Aug-25 intuition *and* the Jun-24 pivot on record.
- Requires: incremental return path to not create duplicates of the user or self-bonds (Jul 21 bugs — these are commit-validation gaps, cheap to fence); FD-339 cut to an MVP (user-initiated corrections only; no clarifying-question loop, no ledger UI).
- Defers: auto-arrange in Personal (manual arrangement accepted), FD-336, FD-340.
- Risk: the returning-coach "feel" is unmeasured — if it re-asks known facts or loses the thread, the loop dies at step 1. Mitigation: dogfood 3–4 return sessions **before** writing code.

### Option B — FD-264 as written: one warm clinician + one client loop (FD-318)
Requires the Pro-app diagram to be usable in session → structural correctness + Personal auto-arrange → the exact area where the ceiling was measured. High rabbit-hole risk; low confidence it closes in 9 months without Option A's correction mechanism anyway.

### Option C — Platform first (FD-340 PySide6, FD-336 embed)
Defers every user-facing outcome; 7 open decisions; no user learns anything for months. Only justified if PyQt5 on the M5 laptop becomes a hard blocker (today: runs under Rosetta).

### Recommendation (opinion, since asked)
**A, with FD-264's done condition rewritten** from "clinician uses the diagram in a Pro session" to "a tester returns and chats ≥3 sessions over ≥4 weeks; the diagram and timeline stay coherent (no duplicate self, no self-bonds, new facts land on the right people) and the tester says the chat was worth returning to." B becomes the *next* epic's done condition, unlocked by A's correction loop. C is parked with an explicit re-open trigger.

Do **one** cheap extraction experiment anyway (Mar-4 prompt on 3.6-flash): 1 session, may recover ~0.25 SARF macro for free. Everything else in extraction tuning is frozen unless real-case corrections point at a specific failure.

### The GT feedback loop (Patrick's idea, stress-tested)
- Mechanism: FD-339 corrections persist as structure + transcript → real-case GT accrues from use, not from coding sessions. This is already in the ticket's design.
- Objectivity: IRR coders coding their *own* families is the Bowen-tradition precedent and a known validity hole. Cheaper alternative that keeps the data real: **cross-coding** — each participant codes a de-identified case belonging to another participant. Same real data, no self-coding.
- Privacy/consent: real family data of colleagues seen by other colleagues. Needs a written consent + de-identification step before any tester content enters the training app. Not solved by code; Patrick's call.
- Unverified premise: how many real (non-Patrick) Personal-app conversations exist today. A Jul-12 prod dump is at `fdserver/prod.dump` — count before assuming testers will generate volume: `docker compose -f fdserver/docker-compose.yml up -d fd-postgres` then restore and `select user_id, count(*) from discussions group by 1`.

---

## 5. Proposed 9-month calendar (each block has a done condition; nothing starts without the prior block's condition)

| Block | Goal | Done condition |
|---|---|---|
| **Sep (weeks 1–2): dogfood, no code** | Patrick returns to diagram 1924 in 3 separate sessions ≥3 days apart; chats about current life; taps extract each time | Friction log with ≥1 entry per session; a ruling on §6 fork 1 |
| **Sep–Oct: fence the return path** | Ticket + fix the Jul 21 bugs as commit-time invariants (reject bond with identical endpoints; reject person parented by own bond; identity weld of the speaker; labels from flat `name`) | Repeat the 3-session dogfood with zero structural errors on the user node |
| **Oct–Nov: FD-339 MVP** | User-initiated corrections in chat only ("X is Y's sister, not daughter") applied as reviewable structural edits; persisted as GT assertions | Patrick fixes his own diagram to "my family as I know it" through chat alone; the Jun-24 32-assertion GT passes on a rebuild |
| **Dec–Feb: seminar testers on the long horizon** | 3–5 app-seminar testers use the returning loop; consent + de-identification agreed first | ≥3 testers × ≥3 sessions; corrections captured; first real-case GT set (v2) exported |
| **Feb–Mar: extraction re-baseline on GT v2** | Run the one pending SARF experiment; re-measure F1 on real-case GT; decide whether extraction tuning is worth reopening | A decision-log entry either reopening or keeping extraction frozen, with numbers |
| **Mar–May: IRR round 2 on real cases + MVP-2 done condition** | Cross-coded IRR on de-identified real cases; then FD-318 clinician loop only if diagrams are coherent | Kappas computed for one real case; go/no-go on the clinician loop; App Store decision with evidence |

Parked with re-open triggers: FD-340 (trigger: PyQt5/Rosetta breaks a build, or App Store submission needs it), FD-336, Personal-app auto-arrange (trigger: a tester says manual arrangement blocked them), workstream-skill work (trigger: >2 tickets genuinely in parallel).

---

## 6. Forks that only Patrick can rule on

1. **Which "diagram" problem blocks testers** — structural correctness (record) or visual arrangement (article)? Determines whether auto-arrange stays parked. The Sep dogfood should answer it empirically.
2. **Rewrite FD-264's done condition** to the long-horizon loop (§4), or keep the clinician-in-Pro loop?
3. **FD-339 scope**: user-initiated corrections only (MVP) vs the full bidirectional design with clarifying questions + ledger?
4. **FD-340**: park with trigger, or continue (needs the 7 decisions on the ticket)?
5. **GT from testers**: self-coding (tradition) vs cross-coding (validity); and the consent/de-identification protocol.
6. **State of the App article**: publish as-is ("last bug = auto-arrange") or align it with the record before it goes out.

Once ruled, each becomes a `decisions/log.md` entry cross-referenced here.

---

## 7. Immediate housekeeping (mechanical, Patrick's git)
- Remove merged worktrees (FD-312/321/324/332/335/337/337-windowing/fable-5/gemini-3.6-flash, retro-*); keep FD-340 and this one.
- Commit or discard: familydiagram M5 build fixes; pkskills CI-green gate; the article draft.
- Close or rebase fdserver PRs #6 and #15 (stale since March).
- File the Jul 21 bug list as tickets under FD-264 (can be done by Claude on request — content is in §2).
