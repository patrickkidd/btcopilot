# MVP Dashboard

**Last consolidated:** 2026-04-12  
**Source of truth:** This file + GitHub milestones. GitHub project board is unreliable (OpenClaw marked items Done without verification).

**How to use:** Milestones are ordered. Pick the next open task under the highest-priority milestone. Mark done with date when verified in code or app.

---

## MVP 1: Extraction E2E

> Hand Personal app to a human tester → chat → tap extract → view diagram+timeline with clusters.
> **Done condition:** One real human completes the full flow without showstopper friction.

**Status: ~90% complete.** Core extraction pipeline, chat, timeline, clusters all working. Auto-accept endpoint needed (2026-04-12 decision: skip PDP approval step). Two Learn tab bugs remain.

**Flow (revised 2026-04-12):** chat → tap "Build my diagram" → single BE endpoint: extract_full() + commit_pdp_items() + cluster detect (atomic DB transaction) → view diagram+timeline. PDP drawer bypassed (code preserved, not wired up).

### Open

| # | Task | Owner | Effort | Details |
|---|------|-------|--------|---------|
| NEW | E2E Personal app test harness | Patrick (parallel) | In progress | familydiagram-testing MCP. Enables Claude Code to walk through app and verify. Prerequisite for all implementation. |
| NEW | Auto-accept BE endpoint | CC | ~2-4 hr | New endpoint: extract_full() + commit_pdp_items() + cluster detect in one atomic DB transaction. Frontend calls this, hides PDP badge/drawer. |
| #129 | Cluster date range missing end year | CC | ~15 min | ~~LearnView.qml:598 formatDateRange() missing eYear.~~ **FIX WRITTEN** (2026-04-12, not yet committed). |
| #131 | Cluster titles truncated in focused state | CC | Low | LearnView.qml elide without conditional width on isFocused. Nice-to-have. |
| NEW | Chat history lost on diagram reopen | CC | | Personal app: send chat message, close+reopen diagram, chat message+response gone. Statements are in Discussion DB table, not DiagramData — should survive regardless of diagram saves. Found during T04-04 concurrent testing. |
| T8-1 | Beta test redo | Patrick | | After auto-accept + bug fixes. One human completes full flow. GH #81 incorrectly closed by OpenClaw. |

### Done

| Item | Date | Evidence |
|------|------|----------|
| T7-1: extract_full() pipeline | 2026-02-26 | pdp.py, tests pass |
| T7-2: POST /extract endpoint | 2026-02-26 | personal/routes/discussions.py |
| T7-3: Chat is chat-only | 2026-02-26 | chat.py, no extraction in ask() |
| T7-4: "Build my diagram" button | 2026-02-26 | PersonalAppController.py, GH #79 |
| T7-9: Idempotent re-extraction | 2026-03 | 12 tests (6 unit, 6 e2e). Positive-ID filtering in apply_deltas(). |
| T7-10: Birth event self-reference fix | 2026-03-03 | fix_birth_event_self_references() in pdp.py, 7 tests |
| T3-8: Auto-detect clusters on accept | 2026-03-05 | GH #85. personalappcontroller.py triggers ClusterModel.detect() |
| T7-13: Timeline zoom/overflow | 2026-03-11 | GH #87 closed |
| T3-1 through T3-6 | 2026-02 | Cluster overlap, selection, zoom, SARF format, Client/Coach labels, scroll-to-bottom |
| T0-1, T0-2, T0-3, T0-5 | 2026-02 | Crash blockers |
| T1-1 through T1-5 | 2026-02 | Extraction quality |
| T4-1 through T4-5 | 2026-02 | Synthetic pipeline |
| T5-4 through T5-6 | 2026-02 | F1 infrastructure |
| T6-2: Cumulative F1 baseline | 2026-02-24 | calculate_cumulative_f1() |
| GH #99: Remove per-statement extraction | 2026-03-05 | pdp.update() deleted, prompts consolidated |
| GH #94: 2-pass split extraction | 2026-03-04 | Pass 1 people/pairbonds, Pass 2 events |
| GH #90: Prompt induction infra | 2026-03-11 | Prod DB + extraction/f1 setup |
| GH #85: Auto-detect clusters | 2026-03-05 | personalappcontroller.py |
| GH #101/#124: iOS build + simulator test | 2026-03-11 | build.sh ios works, Patrick tested, found bugs #128-133 |
| GT coded (6 discussions) | 2026-03 | Discussions 36/37/39/48/50/51 verified in gt_export.json |
| F1 above all targets | 2026-04-12 verified | People 0.900, Events 0.411, PairBonds 0.762, Aggregate 0.616 |

### Dead / Superseded

| Item | Reason |
|------|--------|
| T7-11: Rules-based dedup | Implemented (PR #88), too rigid, reverted (PR #108). LLM-based dedup via T7-9 positive-ID filtering is the chosen approach. |
| T7-5/T7-7/T7-8 as blocking tasks | Satisfied. GT coded for 6 discussions (target 5-8), F1 above targets. |
| T5-1/T5-2 GT cleanup | Partially addressed by Patrick. 6 coded discussions meet target. |
| T3-7: Timeline→diagram highlight | Not implemented. Moved to Jira UI epic (nice-to-have, Pro app). |
| PDP approval flow | Bypassed by auto-accept decision (2026-04-12). PDP drawer code preserved but dormant. |
| Delta-by-delta extraction | Architecture pivot 2026-02-24. Single-prompt 2x better F1. |
| Gemini coaching eyeball test | Deferred. Opus is excellent, no one will use Gemini until later. |

### PDP Drawer Bugs (dormant — bypassed by auto-accept)

These exist but are not blocking MVP 1 since the PDP drawer is bypassed.

| # | Title | File | Details |
|---|-------|------|---------|
| #128 | Badge count doesn't decrement | PersonalContainer.qml | pdpCount binding only updates on full PDP refresh |
| #130 | Sheet stays open across tabs | PDPSheet.qml | Drawer parented to Overlay.overlay |
| #132 | Time field shown by default | EventForm.qml | startTimePicker always visible, needs hideTime |
| #133 | No dismiss gesture | PDPSheet.qml | dragMargin: 0 disables swipe-down |

---

## MVP 2: Pro App Viewing

> Open Personal-app-generated diagrams in the Pro app with correct layout.
> **Done condition:** Pro app opens a Personal-generated diagram with correct auto-layout, no data corruption, no FR-2 violation.

**Status: ~10% complete.** T0-4 in progress (Patrick). Auto-arrange is the long pole.

**Note:** Pro app is basically done and out of scope for MVP 1. Only comes into picture for this milestone.

### Open

| # | Task | Owner | Effort | Details |
|---|------|-------|--------|---------|
| T0-4 | FR-2 fix (concurrent write corruption) | Patrick | ~4 hr | Code complete on branches `familydiagram:fix/t0-4-fr2-applychange-merge`, `btcopilot:fix/t0-4-fr2-schema-cleanup`. 5 tests pass. **Pending Patrick manual test before merge.** GH #82. |
| T0-5 | Partial-write bugs in `setDiagramData()` and server-side `set_diagram_data()` | CC | ~3 hr | Same root cause as T0-4 but in different code paths. `Diagram.setDiagramData()` (familydiagram `server_types.py`) only writes 5 of 43 fields — drops emotions, layers, UI flags on local writes (affects PDP undo). Server-side `Diagram.set_diagram_data()` (btcopilot `pro/models/diagram.py`) drops clusters and clusterCacheKey — affects server-side extraction. Both need field-by-field merge matching the T0-4 pattern. Found during FMEA of T0-4. |
| T2-1 | Deterministic auto-arrange | CC+H | 2-3 wk | Replace Gemini with graph algorithm. GH #83. Analysis: doc/analyses/2026-02-20_auto_arrange.md. Simplified MVP option: generational Y-alignment (~1 week, ~70% value). |
| T2-5 | Baseline view fix | CC+H | ~2 hr | GH #84. Root cause unknown, needs investigation. |

### Done

| Item | Date | Evidence |
|------|------|----------|
| T2-2, T2-3: Arrange error handling | 2026-02 | |
| T2-4, T2-6 | 2026-02 | |

### Likely blockers (from analysis docs, need verification)

| Item | Source | Status |
|------|--------|--------|
| Pickle TypeError on version conflict | Analysis: diagram_viewing, TODO.md stack trace | Unknown if fixed. server_types.py:295. |
| _log not defined on view deletion | Analysis: bugs_inventory, TODO.md | Not fixed → Jira UI epic. |
| Views: can't add people then activate | TODO.md | Not fixed → Jira UI epic. |

---

## MVP 3: SARF Accuracy

> Systematic SARF extraction F1 improvement using lit review definitions.

**Status: 0% complete. Not developer burndown.** Patrick is mobilizing human testers. Tracked separately.

**Strategy constraints** (from `doc/PROMPT_ENG_EXTRACTION_STRATEGY.md`): verbose definitions kill F1, examples cause regressions, review passes work, most prompt changes regress on gemini-3-flash.

### Open (human tester scope)

| # | Task | GH Issue | Wave | Notes |
|---|------|----------|------|-------|
| T9-1 | SARF Calibration & IRR Review Tool | #103 | 1 | Training app feature. Requires planning session. |
| T9-2 | Inter-term consistency check | #104 (epic) | 1 | Complete CROSS-REFERENCES.md + GAPS.md |
| T9-3 | Symptom review pass | #104 (epic) | 1 | Target: S > 0.518 |
| T9-4 | Anxiety review pass | #104 (epic) | 1 | Target: A > 0.597 |
| T9-5 | Functioning review pass | #104 (epic) | 1 | Target: F > 0.291 (weakest) |
| T9-6 | R review enhancement | #105 (epic) | 2 | Depends on T9-2 |
| T9-7 | Unified review architecture | #105 (epic) | 2 | Depends on T9-3/4/5 |
| T9-8 | Decision Guide boundary tuning | #105 (epic) | 2 | Depends on T9-2 |
| T9-9 | SARF definitions refinement | #106 (epic) | 3 | Depends on T9-3/4/5 |
| T9-10 | GT expansion | #106 (epic) | 3 | Human. Depends on T9-1/2. |
| T9-11 | Definition reference panel | #106 (epic) | 3 | Training app. Shares T9-1 infra. |
| — | Further improve SARF F1 | (project board only) | — | No GH issue. General improvement tracking. |

Individual GH issues #107-116 were closed and rolled into wave epics #104/#105/#106.

---

## Metrics

| Metric | Value | Measured | Target | Status |
|--------|-------|----------|--------|--------|
| People F1 | 0.900 | 2026-04-12 verified | > 0.7 | PASS |
| Events F1 | 0.411 | 2026-04-12 verified | > 0.3 | PASS |
| PairBonds F1 | 0.762 | 2026-04-12 verified | > 0.5 | PASS |
| Aggregate Micro-F1 | 0.616 | 2026-04-12 verified | > 0.5 | PASS |
| Structural Events F1 | 0.413 | 2026-04-12 | — | Birth=0.204, Death=0.800, Married=0.333 |
| Shift Events F1 | 0.419 | 2026-04-12 | — | |
| SARF Macro F1 | 0.602 | 2026-04-12 | > 0.5 | PASS (S=0.757, A=0.640, R=0.487, F=0.524) |
| GT coded discussions | 6 | 2026-04-12 | 5-8 | PASS (disc 36/37/39/48/50/51) |

Per-discussion: 36=0.698, 37=0.487, 39=0.612, 48=0.642, 50=0.561, 51=0.697.

**Note:** All 6 GT discussions flagged `synthetic=True`. Audit dashboard shows 0 (filters synthetic). Admin dashboard shows correctly via toggle.

**Note:** Previous dashboard (Mar 2026) reported higher F1 (Events 0.509, PairBonds 0.832). Different measurement conditions or extraction run. Current values verified from gt_export.json on 2026-04-12.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-accept with no human review | ~38% of items wrong/missing (F1=0.616) | T7-9 dedup working (12 tests). Users can re-extract. Acceptable for beta. |
| Single-prompt context limit | Extraction fails on long conversations | gemini-2.5-flash 1M tokens; typical ~30K chars. Monitor. |
| Auto-arrange is 2-3 weeks | Delays MVP 2 | Simpler generational Y-alignment (~1 week, ~70% value). |
| Atomic transaction endpoint | Data corruption if not transactional | Design requirement — extract + commit + cluster in single DB transaction. |

---

## Architecture Decisions (from decisions/log.md)

| Date | Decision | Key Detail |
|------|----------|------------|
| 2026-04-12 | Auto-accept extraction, bypass PDP drawer | Users won't understand approval step. Atomic BE endpoint. PDP code preserved. |
| 2026-02-24 | Single-prompt extraction replaces delta-by-delta | 2x F1 improvement. User-initiated "Build my diagram" button. |
| 2026-02-24 | Patrick is sole GT source for MVP | IRR study deferred. ~60 min/discussion. Target 3-5 (achieved 6). |
| 2026-02-14 | PairBonds are first-class entities | Explicitly extracted by AI. F1 went 0.0→0.762 after prompt examples added. |

---

## Completed Historical Work (project board / closed issues)

Items completed during the OpenClaw automation period (Feb-Mar 2026). Preserved for context.

| Item | Source | Date |
|------|--------|------|
| T7-19: Gemini thinking budget experiment | Project board | 2026-03 |
| T7-20: Baseline F1 with gemini-3.1-flash-lite | Project board | 2026-03 |
| Add per-entity-type F1 breakdown to eval harness | Project board | 2026-03 |
| Batch dead-code cleanup (#44, #47, #48, #49) | Project board | 2026-03 |
| Generate F1 extraction quality report | Project board | 2026-03 |
| Fix Master CI stuck in pending | Project board | 2026-03 |
| Add integration tests for db-sync-capability | Project board | 2026-03 |
| Improve Events extraction F1 0.29→0.4+ | Project board | 2026-03 |
| Improve SARF extraction F1 for gemini-3-flash | Project board | 2026-03 |
| Add DB performance indexes | Project board | 2026-03 |
| Fix pro app crash: remove personal objects from pickle | Project board | 2026-03 |
| #75: Update test suite to new Scene API | GH closed | 2026-02-26 |
| #76: Data sync reliability | GH closed | 2026-02-26 |
| #77: QML UI polish and stability | GH closed | 2026-02-26 |
| #78: Dev environment setup (x2) | GH closed | 2026-03-05 |
| #89: Prompt induction setup (duplicate) | GH closed | 2026-03-03 |
| #92: T7-17 simplified prompt experiment | GH closed | 2026-03-03 |
| #93: T7-18 prompt architecture review | GH closed | 2026-03-03 |

---

## Deferred (Post-MVP)

| Item | Source | Notes |
|------|--------|-------|
| PlanView content (GH #100) | Patrick 2026-03-11 | "deferred to post MVP" |
| Gemini coaching validation | 2026-04-12 | Opus is excellent. Gemini later. |
| TestFlight distribution | GH #101 Phase 3 | Simulator works. TestFlight not set up. |
| T3-7: Timeline→diagram highlight | Jira UI epic | Nice-to-have, Pro app |
| Coaching style settings visual verification | doc/plans/CONVERSATIONAL_MODEL_QUALITY.md | Settings implemented, not visually verified |
| SARF variable editing | Old dashboard | |
| IRR study (Guillermo/Kathy) | Decision log 2026-02-24 | |
| Fine-tuning | Old dashboard | |
| Per-statement F1 diagnostics | Old dashboard | |
| Conversation flow versioning | Old dashboard | |
| PDF export | Old dashboard | |
| Pattern intelligence | Old dashboard | |
| Add Notes to PDP | btcopilot/doc/plans/ADD_NOTES_TO_PDP.md | |
| Per-statement delta extraction for training app | Old dashboard | |

---

## Reference

### Key Files

| Component | Location |
|-----------|----------|
| Single-prompt extraction | `btcopilot/pdp.py` (`extract_full()`) |
| Extract endpoint | `btcopilot/personal/routes/discussions.py` (`POST /extract`) |
| PDP validation | `btcopilot/pdp.py` (`validate_pdp_deltas()`) |
| Delta acceptance | `btcopilot/schema.py` (`commit_pdp_items()`) |
| Chat (chat-only) | `btcopilot/personal/chat.py` (`ask()`) |
| Extraction prompts | `btcopilot/personal/prompts.py` (defaults), `fdserver/prompts/` (production) |
| F1 metrics | `btcopilot/training/f1_metrics.py` |
| Synthetic generation | `btcopilot/tests/personal/synthetic.py` |
| E2E pipeline test | `btcopilot/tests/personal/test_e2e_synthetic.py` |
| Idempotent re-extraction tests | `btcopilot/tests/personal/test_reextract_commit.py`, `test_committed_reextract_e2e.py` |
| Personal app QML | `familydiagram/pkdiagram/resources/qml/Personal/` |
| PersonalAppController | `familydiagram/pkdiagram/personal/personalappcontroller.py` |
| Decision log | `btcopilot/decisions/log.md` |
| Consolidation plan (full raw data) | `btcopilot/doc/plans/MVP_CONSOLIDATION.md` |

### Analyses (2026-02-20)

| Analysis | Covers |
|----------|--------|
| [PDP Extraction & Delta Acceptance](doc/analyses/2026-02-20_pdp_extraction_and_delta_acceptance.md) | Extraction pipeline, validation, commit flow, F1 |
| [Synthetic Pipeline](doc/analyses/2026-02-20_synthetic_pipeline.md) | Celery tasks, error handling, evaluators |
| [Personal App Beta Readiness](doc/analyses/2026-02-20_personal_app_beta_readiness.md) | Chat UX, PDP drawer, timeline, PlanView |
| [Auto-Arrange](doc/analyses/2026-02-20_auto_arrange.md) | Layout algorithm, Gemini approach |
| [Diagram Viewing & Sync](doc/analyses/2026-02-20_diagram_viewing_and_sync.md) | Scene loading, version conflicts, FR-2 |
| [Server API & Data Model](doc/analyses/2026-02-20_server_api_and_data_model.md) | Endpoints, validation, sync |
| [Bugs & TODOs Inventory](doc/analyses/2026-02-20_bugs_and_todos_inventory.md) | Complete bug list, skipped tests |

### GitHub State (as of 2026-04-12)

**Issues to fix:**
- #80 (T3-7): Incorrectly closed by OpenClaw. Not implemented. → Jira
- #81 (T8-1): Incorrectly closed by OpenClaw. Partial — needs redo.
- #82, #83: Assigned to old MVP 3 milestone on GitHub, belong to MVP 2.
- #100: Should be closed (deferred by Patrick).
- MVP 1 milestone description: Remove T3-7 from done-condition. Update flow to reflect auto-accept.
- MVP 2 milestone title: "Human Beta" is misleading — this is Pro viewing.
- Old MVP 3 milestone: Close (collapsed into MVP 2). Old MVP 4 renamed to MVP 3.

**Project board trust level: LOW.** OpenClaw marked human-only tasks Done, reverted code as Done. Use this dashboard + GitHub issues as source of truth, not the project board.
