# MVP Consolidation Plan

**Created:** 2026-04-11  
**Updated:** 2026-04-12  
**Purpose:** Single reference document for the MVP consolidation effort. Contains all raw data, decisions, and analysis needed to rewrite MVP_DASHBOARD.md and fix GitHub state. Designed to survive context compaction — all data inline, no external references required to continue work.

**Note:** This document references "MVP 3" and "MVP 4" from the original GitHub milestones. These were subsequently collapsed: old MVP 3 (undefined) merged into MVP 2, old MVP 4 (SARF Accuracy) renumbered to MVP 3. See MVP_DASHBOARD.md for current numbering.

---

## Q&A Decisions (2026-04-12)

| Q | Topic | Decision |
|---|-------|----------|
| Q1 | Source of truth | **GitHub milestone descriptions are correct.** Dashboard goal numbering is wrong. Reorganize everything under milestones. |
| Q2 | GT tasks | GT coded for discussions 36/37/39/48/50/51 (6 total, target 5-8 = **met**). T5-1/T5-2 partially addressed — Patrick recalls working on them but unclear if 100% complete. |
| Q3 | T7-11 dedup | Rules-based dedup was too rigid. Reverted (PR #88 added, PR #108 reverted). LLM-based dedup via T7-9 positive-ID filtering is the chosen approach (working, 12 tests). **T7-11 is dead.** |
| Q4 | T8-1 beta test | iOS bugs (#128-133) not fixed. T8-1 needs redo after fixes. |
| Q5 | T3-7 | Nice-to-have, belongs in Patrick's private Jira under UI epic. **⚠️ Contradicts MVP 1 milestone description — needs removal from done-condition.** |
| Q6 | TODO.md | Patrick's scratchpad — don't promote to GitHub. Exception: Views bug → Jira UI epic. |
| Q7 | SARF accuracy | For human testers Patrick is mobilizing. Not developer burndown. |
| Q8 | Definition of shipped | Per Q1: MVP 1 = one real human completes full Personal app flow without showstoppers. |

### Strategic decision (2026-04-12): Auto-accept extraction results

**Patrick's direction:** Make the "Build my diagram" button auto-accept all PDP items. Skip the PDP drawer review/edit interface entirely. Rationale:
- Users won't understand or want the extra approval step
- LLM-based deduplication (T7-9 positive-ID filtering) makes re-extraction mostly idempotent
- PDP drawer code preserved but dormant for potential future use

**Impact on MVP 1:**
- PDP drawer bugs become irrelevant for MVP 1: #128 (badge count), #130 (sheet across tabs), #132 (time field), #133 (dismiss gesture)
- Only Learn tab bugs remain blocking: #129 (cluster date range), #131 (cluster titles)
- The beta flow simplifies to: chat → tap "Build my diagram" → auto-accept + cluster detect → view diagram+timeline
- T7-9 idempotent re-extraction becomes more safety-critical (no human review step)
- emotionalunit.py crash on accept (if still live) becomes more critical — no human to see the error

**Implementation required:**
- New single backend endpoint: extract_full() + commit_pdp_items() + cluster detect in one atomic DB transaction. NOT frontend wiring — must be transactional to avoid data corruption.
- Frontend: "Build my diagram" button calls new endpoint, hides PDP badge/trigger
- Preserve PDP drawer code — don't delete, just don't wire it up

### Clarifications (2026-04-12, second round)

- **T3-7 is definitively NOT MVP.** Nice-to-have for Pro app Jira UI epic. Remove from MVP 1 milestone done-condition.
- **emotionalunit.py crash is a Pro app issue.** Deprioritized for MVP 1. Pro app is basically done and not in scope for MVP except T0-4 (Patrick working in parallel).
- **Timeline is the primary content view for MVP 1** (not PDP). At this stage of testing, timeline and PDP have the same content, and the timeline is easier to digest.
- **Pro app does not come into the picture for MVP** except T0-4 which Patrick is working on in a parallel session.
- **E2E Personal app test harness** is a prerequisite — Patrick is working on getting familydiagram-testing MCP to work in a parallel session. Once available, Claude Code can walk through the app and verify bug states directly.

---

## GitHub Milestone Definitions (authoritative)

These are the correct source of truth per Q1.

**MVP 1: Extraction E2E** (Milestone #1)
- Description: "Hand Personal app to a human tester → chat → tap extract → accept PDP → view diagram+timeline with clusters."
- Done condition: "One real human completes the full flow without showstopper friction. Timeline-to-diagram interaction works (T3-7)."
- Tasks listed: T3-7 (click event in timeline → highlight people in diagram), T8-1 (beta test)
- State: Open. 0 open issues, 8 closed issues assigned.
- **⚠️ T3-7 must be removed from done-condition per Q5 decision.**
- **⚠️ Description must be updated to reflect auto-accept flow (no PDP approval step).**

**MVP 2: Human Beta** (Milestone #2) — actually "Pro App Viewing"
- Description: "Open Personal-app-generated diagrams in the Pro app with correct layout."
- Done condition: "Pro app opens a Personal-generated diagram with correct auto-layout, no data corruption, no FR-2 violation."
- Tasks listed: T2-1 (auto-arrange), T0-4 (FR-2 fix), T2-5 (baseline view fix)
- State: Open. 4 open issues, 2 closed issues.
- **⚠️ Title "Human Beta" is misleading — this is Pro viewing. Consider renaming.**

**MVP 3: Pro Viewing** (Milestone #3)
- Description: (none)
- State: Open. 2 open issues (#82, #83), 3 closed.
- **⚠️ #82 and #83 belong to MVP 2 per descriptions. This milestone has no purpose.**

**MVP 4: SARF Accuracy** (Milestone #5)
- Description: "Systematic SARF extraction F1 improvement using lit review definitions"
- State: Open. 4 open issues (#103, #104, #105, #106), 0 closed.

---

## All Open GitHub Issues (raw data)

### #133 — PDP sheet has no dismiss gesture (swipe-down blocked)
- Milestone: none
- Created: 2026-03-12 (AI UI/UX test)
- File: `pkdiagram/resources/qml/Personal/PDPSheet.qml`
- Problem: `interactive: false` and `dragMargin: 0` prevent swipe-to-close. Users must Accept All to dismiss.
- **MVP 1 status: IRRELEVANT (auto-accept bypasses PDP drawer)**

### #132 — Add Data Point: time field shown by default, person field is free-text
- Milestone: none
- Created: 2026-03-12 (AI UI/UX test)
- File: `pkdiagram/resources/qml/EventForm.qml`
- Problem: (1) Time field '--:-- pm' shown by default for historical events. (2) Person field is free-text, should autocomplete from diagram persons.
- **MVP 1 status: IRRELEVANT (auto-accept bypasses manual event editing)**

### #131 — Cluster titles still truncated in focused/expanded state
- Milestone: none
- Created: 2026-03-12 (AI UI/UX test)
- File: `pkdiagram/resources/qml/Personal/LearnView.qml`
- Problem: Titles show '...' truncation in expanded/focused state. Need conditional width binding on `isFocused`.
- **MVP 1 status: LOW — cosmetic but visible in Learn tab**

### #130 — PDP sheet stays open across tab switches
- Milestone: none
- Created: 2026-03-12 (AI UI/UX test)
- Problem: Drawer parented to Overlay.overlay persists across tabs. Confusing with Discuss tab header badge.
- **MVP 1 status: IRRELEVANT (auto-accept bypasses PDP drawer)**

### #129 — Cluster card date range shows incomplete end date
- Milestone: none
- Created: 2026-03-12 (AI UI/UX test)
- File: `pkdiagram/resources/qml/Personal/LearnView.qml`
- Problem: formatDateRange() at line 598 missing `eYear` in output. One-line fix.
- **MVP 1 status: MEDIUM — visible bug in Learn tab, trivial fix**

### #128 — PDP badge count does not decrement on individual accept/reject
- Milestone: none
- Labels: bug
- Created: 2026-03-12 (AI UI/UX test)
- File: `PersonalContainer.qml` pdpCount binding
- Problem: Badge stays at initial value after individual accept/reject. Only clears after Accept All.
- **MVP 1 status: IRRELEVANT (auto-accept bypasses PDP drawer)**

### #124 — Test Personal app in iOS Simulator (M2)
- Milestone: MVP 2: Human Beta
- Created: 2026-03-10
- Contains full build/deploy instructions and test checklist. Has comment thread where Patrick corrected OpenClaw about pyqtdeploy (not Flutter).
- **Status: Testing done 2026-03-11. Bugs #128-133 found. Build pipeline works.**

### #106 — Wave 3: Refinement & GT Expansion
- Milestone: MVP 4: SARF Accuracy
- Labels: goal-4-sarf-accuracy
- Sub-issues: T9-9 (definitions refinement), T9-10 (GT expansion, human), T9-11 (definition reference panel)
- Depends on Waves 1-2.
- **Status: Not started. Human tester scope per Q7.**

### #105 — Wave 2: Review Enhancement & Architecture
- Milestone: MVP 4: SARF Accuracy
- Labels: goal-4-sarf-accuracy
- Sub-issues: T9-6 (R review), T9-7 (unified review architecture), T9-8 (decision guide tuning)
- Depends on Wave 1.
- **Status: Not started. Human tester scope per Q7.**

### #104 — Wave 1: SARF Review Passes & Inter-Term Consistency
- Milestone: MVP 4: SARF Accuracy
- Labels: goal-4-sarf-accuracy
- Sub-issues: T9-1 (calibration tool), T9-2 (inter-term consistency), T9-3/4/5 (S/A/F review passes)
- All parallel, can start immediately.
- **Status: Not started. Human tester scope per Q7.**

### #103 — T9-1: SARF Calibration & IRR Review Tool
- Milestone: MVP 4: SARF Accuracy
- Labels: goal-4-sarf-accuracy, wave-1
- Two components: (A) within-expert manual review with frontier LLM, (B) between-expert IRR with Cohen's kappa.
- Requires planning session.
- **Status: Not started. Human tester scope per Q7.**

### #101 — T7-21: Build Personal app for iPhone simulator and TestFlight
- Milestone: MVP 2: Human Beta
- Labels: P1-high, infra
- Three phases: (1) environment setup, (2) build + simulator, (3) TestFlight distribution.
- Phases 1-2 complete. Phase 3 (TestFlight) not done.
- **Status: Simulator build works. TestFlight deferred.**

### #100 — Populate PlanView with cross-generational pattern summary
- Milestone: MVP 1
- **Explicitly deferred post-MVP by Patrick (2026-03-11 comment: "this should be deferred to post MVP").**

### #84 — T2-5: Fix baseline view in new diagrams
- Milestone: none (should be MVP 2)
- Labels: P2-medium, frontend, wave-1
- Root cause unknown, needs investigation. ~2 hr effort.
- **Status: Not started. MVP 2 scope.**

### #83 — T2-1: Implement deterministic auto-arrange algorithm (replace Gemini)
- Milestone: MVP 3: Pro Viewing (should be MVP 2)
- Labels: P2-medium, frontend, ai-ml, wave-1
- Replace Gemini with graph algorithm. 2-3 week effort. Analysis: doc/analyses/2026-02-20_auto_arrange.md.
- Simplified MVP option: generational Y-alignment only (~1 week, ~70% value).
- **Status: Not started. MVP 2 scope. Long pole.**

### #82 — T0-4: Fix FR-2 violation: applyChange overwrites Personal data
- Milestone: MVP 3: Pro Viewing (should be MVP 2)
- Labels: P2-medium, backend, frontend
- Only fires on concurrent Pro+Personal writes. ~4 hr effort. Analysis: doc/analyses/2026-02-20_diagram_viewing_and_sync.md.
- **Status: Not started. MVP 2 scope.**

---

## Key Closed GitHub Issues (context preservation)

### #80 — T3-7: Click event in timeline → highlight people in diagram
- Closed: 2026-03-11 (by OpenClaw, incorrectly)
- **Actual status: NOT IMPLEMENTED. Zero code exists.**
- Per Q5: Jira nice-to-have. Remove from MVP 1 done-condition.

### #81 — T8-1: Beta test with 1 human user (full flow)
- Closed: 2026-03-11 (by OpenClaw, incorrectly)
- **Actual status: PARTIAL.** Patrick tested 2026-03-11, captured friction in TODO.md. No formal log. Bugs found but not fixed.

### #99 — Remove per-statement extraction path and consolidate prompts
- Closed: 2026-03-05. **Legitimately done.** pdp.update() removed, prompts consolidated.

### #94 — Experiment with dividing extraction into specialized prompts
- Closed: 2026-03-04. **Legitimately done.** Led to 2-pass split extraction (Pass 1 people/pairbonds, Pass 2 events).

### #85 — T3-8: Auto-detect clusters on PDP accept
- Closed: 2026-03-05. **Legitimately done.**

### #87 — T7-13: Fix timeline initial zoom and right-edge overflow
- Closed: 2026-03-11. **Legitimately done.**

### #107-116 — Individual SARF T9-* tasks
- All closed 2026-03-05, rolled into wave epics #104/#105/#106.

---

## Decision Log Entries (relevant to MVP strategy)

### 2026-02-24: Single-prompt extraction replaces delta-by-delta
- Delta-by-delta: Aggregate F1 0.25, Events F1 0.099, 3-4x event inflation
- Single-prompt: Aggregate F1 0.45, Events F1 0.29 — nearly 2x improvement
- **Decision:** User-initiated single-prompt extraction ("Build my diagram" button)
- UX flow: chat → tap button → full conversation as one prompt → complete PDP → accept
- chat.py drops extraction path (chat-only). New pdp.extract_full().
- Per-statement pipeline kept for training app GT coding only.

### 2026-02-24: Patrick is sole GT source for MVP
- IRR study with Guillermo/Kathy deferred. Too slow for MVP iteration loop.
- Patrick codes all GT. ~60 min/discussion. Target: 3-5 coded (achieved: 6).

### 2026-02-14: PairBonds are first-class entities
- AI was extracting zero pair bonds. Prompt had zero positive examples.
- **Decision:** PairBonds explicitly extracted by AI, not just inferred from events.
- cleanup_pair_bonds() fixed. Positive examples added to prompt.
- Result: PairBond F1 went from 0.0 to 0.76.

### 2026-03-05: IRR calibration features
- Per-event coding advisor needs `deep=True` (4096 tokens + thinking)
- IRR review unit = matched cumulative events across coders

---

## Verified F1 Metrics (from code/data, 2026-04-12)

Source: gt_export.json (6 discussions, all synthetic=True)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| People F1 | 0.900 | > 0.7 | PASS |
| Events F1 | 0.411 | > 0.3 | PASS |
| PairBonds F1 | 0.762 | > 0.5 | PASS |
| Aggregate Micro-F1 | 0.616 | > 0.5 | PASS |
| Structural Events F1 | 0.413 | — | — |
| Shift Events F1 | 0.419 | — | — |
| SARF Macro F1 | 0.602 | > 0.5 | PASS |
| SARF S (Symptom) | 0.757 | — | — |
| SARF A (Anxiety) | 0.640 | — | — |
| SARF R (Relationship) | 0.487 | — | — |
| SARF F (Functioning) | 0.524 | — | — |
| GT coded discussions | 6 (36/37/39/48/50/51) | 5-8 | PASS |

Per-discussion breakdown:
- Disc 36: F1=0.698 (People 0.846, Events 0.533)
- Disc 37: F1=0.487 (People 0.846, Events 0.300)
- Disc 39: F1=0.612 (People 0.970, Events 0.286)
- Disc 48: F1=0.642 (People 0.889, Events 0.489)
- Disc 50: F1=0.561 (People 0.917, Events 0.346)
- Disc 51: F1=0.697 (People 0.933, Events 0.510)

Weakest per-kind: Birth events F1=0.204 (n=62), Married F1=0.333 (n=10).

**⚠️ All discussions flagged synthetic=True.** Audit dashboard shows 0 scores (filters synthetic). Admin dashboard shows correctly via toggle.

---

## Analysis Doc Findings (2026-02-20, possibly stale)

These were identified in 7 analysis documents. Many items have been fixed since Feb 2026. Items marked [LIKELY FIXED] need code verification.

### Crashes
- emotionalunit.py AttributeError (NoneType.id) on PDP accept — [LIKELY FIXED: T0-5 marked Done]
- Pickle TypeError on version conflict save — [UNKNOWN: stack trace in TODO.md]
- _log not defined on view deletion — [NOT FIXED: Patrick says → Jira]

### Data integrity
- Conflict event childOf not set correctly on accept — [UNKNOWN]
- Extra grandparents on Separated accept — [UNKNOWN]
- Chat response race condition (async overwrite) — [UNKNOWN]
- Undo doesn't persist to server — [KNOWN, LOW]
- Silent ID reassignment in reassign_delta_ids() — [BY DESIGN]
- Duplicate dyad collapse on commit (remarriage scenario) — [KNOWN LIMITATION]

### UX gaps (Personal app "40% beta-ready" assessment)
- No loading indicator during AI response — [UNKNOWN]
- No onboarding/first-use guidance — [NOT DONE]
- No SARF variable legend — [UNKNOWN]
- PlanView empty — [DEFERRED by Patrick]
- Cluster text overlaps — [PARTIALLY FIXED via T7-13]
- No conversation titles — [UNKNOWN]

### Extraction issues (MOSTLY FIXED since Feb)
- Event F1 = 0.09 → now 0.411 ✅
- SARF F1 = 0.11 → now 0.602 ✅
- PairBond F1 = 0.0 → now 0.762 ✅
- Birth event self-reference → FIXED (T7-10) ✅
- 40% of GT events structurally unmatchable → GT partially cleaned (Q2) ✅

### Synthetic pipeline
- No error handling in Celery task — [NOT FIXED, non-blocking for MVP]
- No auto-extraction trigger after generation — [NOT FIXED, non-blocking]
- No discussion state machine — [NOT FIXED, non-blocking]
- Quality/coverage evaluators not integrated — [NOT FIXED, non-blocking]

---

## Coaching Quality Status (from doc/plans/CONVERSATIONAL_MODEL_QUALITY.md)

### Opus coaching prompt
- Exp1 rewrite shipped and validated 2026-03-16. Excellent quality. No known issues.

### Gemini coaching prompt
- Guideline-based addendum rewrite (2026-04-11) partially improved.
- Fixed: FM1 (topic stagnation), FM3 (fragment completion)
- Remaining: FM2 (reformulation loops), FM4 (zero response type variety), FM5 (off-domain pivots)
- **Blocker:** Synthetic client was broken (generating fragments), so all Gemini evaluations were confounded. Need human eyeball test.

### User-facing model settings
- Names: "Premium" (Opus) / "Standard" (Gemini). Help text added.
- Settings menu renamed "Model" → "Coaching Style".
- Visual verification in app still pending.

---

## Skipped Tests Summary (38 active, by category)

- **14 frontend tests** — batch-disabled for cherry-picking re-enablement (test_audit_feedback.py, test_audit_ui.py, test_audit_integration.py, test_event_delta_modal.py)
- **4 Stripe-conditional** — require ENABLE_STRIPE env var (test_licensing.py)
- **3 flaky UI tests** — bounding rect, QML visibility, pixel changes
- **8 feature-not-implemented** — validation code, __le__ support, import validation
- **2 forgotten** — "Can't remember why" (test_diagrams.py)
- **1 debug-only** — test_hangWatchdog
- **1 CI-only skip** — HuggingFace unavailable on GitHub Actions
- **5 misc** — need rethinking, not sure if needed, date buddies unused

---

## Code TODO Comments (30 total, no urgent items)

Mostly architectural notes. Notable:
- `model_tests/test_extraction.py:92` — "Rewrite to use pdp.extract_full() — per-statement pdp.update() was removed in #99"
- `mainwindow.py:2042` — "Support iPhone X safe areas"
- `serverfilemanagermodel.py:576` — "Make synchronous"
- `DiscussView.qml:606` — "re-enable when voice input is polished"

---

## TODO.md Raw Inventory (Patrick's scratchpad — do not promote to GitHub)

### From Testing (2026-03-11 iOS)
- Add top margin to notes field
- Intro flow: set user's name and birth date
- Is it adding every variable to almost every event, or display bug?
- Startup time slow, no splash screen
- Event list view disappears sometimes
- Need diagram ID, event ID, user ID in dev for reporting
- Clusters should encompass all events on timeline
- S, A, F icons as flags not useful — need values (R is okay)

### Training
- Can't delete assistant person delta
- Need date of discussion in synthetic cases
- Divider line between birth and bonded in event kind menu

### Personal bugs
- No indication on cluster graph when selecting event
- Text overlaps between cluster titles
- Extraction for S, A, F should show direction only ("Symptom: Up: {NAME}")
- Lots of unused space to right of clusters

### Pro bugs (→ Jira UI epic)
- Can't clear SARF variable in event
- Click event in timeline → highlight people (T3-7 — Jira)
- Outside move should only show Event.relationshipTargets
- Only show isDateRange for shift events
- _do_addItem doesn't add symbols for Event.relationshipTriangles
- Baseline view doesn't work in new diagram (T2-5)
- Can't add people to view then activate (→ Jira)
- _log not defined on view re-open (→ Jira)
- Fix journal notes import
- Export extractions and debug PDP bugs

### Data extraction ideas
- Ensure JSON examples use statement inference not string matching
- Evaluate conversation history usage
- Add both parents on first parent mention
- Initialize Event.description to Unknown in SARF editor
- "User" still shown after person delta
- Show location field for moved events
- Use 1/1/* datetime with low confidence for estimated dates
- Add confidence to SARF editor
- Track low confidence dates for UI

### Conversational flow
- Keep from giving guidance (not there yet)
- Don't ignore repeated family evasions (3-4 times)
- Definition of done for diagram + timeline interview

### Runtime errors (stack traces)
- TypeError in save flow: `a bytes-like object is required, not 'DiagramData'` (mainwindow.py:708 → serverfilemanagermodel.py:545 → server_types.py:216)
- AttributeError: 'NoneType' object has no attribute 'id' in layer filtering (person.py:1334 → scene.py → emotionalunit.py → property.py)
- Uncommitted person picker warning broken

### Other
- Data ticket: 2025-12-22 pair bond cleanup (fdserver/data_tickets/)
- Set interview date as reference for implied timestamps
- Need ability to reference existing events for corrections ("Is Update" button)
- Rename Assistant to "clinician", default type to Expert
- Deemphasize SARF event ID badge
- Limit SARF Parents to 2

---

## MVP 1: Final Evaluation (post auto-accept + clarifications)

### Revised flow
chat → tap "Build my diagram" → single BE endpoint: extract_full() + commit_pdp_items() + cluster detect (atomic transaction) → view diagram+timeline

### Revised done-condition
One real human completes full Personal app flow (chat → extract → view timeline) without showstopper friction. No PDP approval step. No T3-7 requirement.

### What's now irrelevant for MVP 1
- #128 (PDP badge count) — no PDP drawer shown
- #130 (PDP stays open across tabs) — no PDP drawer shown
- #132 (time field default) — no manual event editing
- #133 (PDP dismiss gesture) — no PDP drawer shown
- PDP editor overlay UX — not shown
- SARF variable legend in PDP — not shown
- T3-7 (timeline→diagram highlight) — Jira nice-to-have, Pro app
- emotionalunit.py crash (T0-5) — Pro app issue, deprioritized
- All Pro app bugs — Pro is out of MVP scope (except T0-4 in parallel)

### What's still blocking MVP 1

| Item | Severity | Effort | Owner | Details |
|------|----------|--------|-------|---------|
| **E2E test harness** | Prerequisite | In progress | Patrick (parallel session) | familydiagram-testing MCP server. Enables Claude Code to walk through app and verify bug states. |
| **Auto-accept BE endpoint** | Critical (new work) | ~2-4 hr | Claude Code | New endpoint: extract_full() + commit_pdp_items() + cluster detect in one atomic DB transaction. Frontend calls this instead of current extract → PDP flow. |
| **#129 cluster date range** | Medium | ~15 min | Claude Code | One-line fix in LearnView.qml:598 — append `eYear` to formatDateRange(). |
| **T8-1 beta test redo** | Required (gate) | ~1 hr | Patrick | After auto-accept + #129 fix. One human completes full flow. |

**Deferred:** Gemini coaching eyeball test — Opus is excellent, no one will use Gemini until later. Gemini validation deferred post-MVP.

### What's nice-to-have for MVP 1
- #131 (cluster titles truncated) — cosmetic, low severity
- Loading indicator during AI response
- Onboarding/first-use guidance
- Conversation titles

### Progress assessment

| Milestone | Progress | Critical Path |
|-----------|----------|---------------|
| **MVP 1** | **~90% complete** | E2E harness (parallel) → auto-accept endpoint (~2-4 hr) → fix #129 (15 min) → verify in test harness → Patrick eyeball test + beta test (~2 hr). **Single focused day once harness is ready.** |
| **MVP 2** | ~15% complete | T0-4 (Patrick, parallel). T2-1 auto-arrange is long pole (1-3 weeks). T2-5 (~2 hr). |
| **MVP 3** | Undefined | No description, no purpose. Recommend close or repurpose. |
| **MVP 4** | 0% | Human testers being mobilized. Not developer-blocking. |

### Risk: auto-accept + dedup reliability

With no human review step, extraction quality matters more:
- **T7-9 positive-ID filtering** (12 tests) prevents duplicate people/events on re-extraction. This is the safety net.
- **Birth event self-reference** fixed (T7-10, 7 tests).
- **Atomic transaction** prevents partial commits on failure — if extract or commit fails, nothing is written.
- **LLM extraction variance**: Different runs may extract slightly different items. Without human review, the diagram is whatever the LLM produces. F1 of 0.616 means ~38% of items are wrong or missing. Acceptable for beta; users can re-extract.

---

## Remaining Actions

### Prerequisites (in progress)
1. **E2E Personal app test harness** — Patrick working on familydiagram-testing MCP in parallel session. Once working, Claude Code can verify bug states directly.

### Implementation work (Claude Code)
2. **Auto-accept BE endpoint** — new endpoint with atomic transaction: extract + commit + cluster detect
3. **Fix #129** (cluster date range one-liner)
4. **Frontend: wire "Build my diagram" to new endpoint**, hide PDP badge/trigger
5. **Verify all changes via E2E test harness** once available

### Patrick's tasks (parallel)
6. **T8-1 beta test redo** after implementation complete (~1 hr)
7. **T0-4 FR-2 fix** (working in parallel session)
8. ~~Eyeball test Gemini coaching~~ — **Deferred.** Opus is excellent, Gemini validation post-MVP.

### GitHub cleanup
9. Reopen #81 (T8-1 — not done)
10. Remove T3-7 from MVP 1 milestone description
11. Update MVP 1 description to reflect auto-accept flow (no PDP, no T3-7)
12. Rename MVP 2 title from "Human Beta" to "Pro App Viewing"
13. Reassign #82/#83 from MVP 3 to MVP 2
14. Close or repurpose MVP 3 milestone
15. Close #100 (PlanView — deferred)
16. Move PDP drawer bugs (#128/#130/#132/#133) to post-MVP or PDP drawer revival milestone

### Documentation
17. Rewrite MVP_DASHBOARD.md aligned to this document
18. Update CLAUDE.md to reference milestones as source of truth
