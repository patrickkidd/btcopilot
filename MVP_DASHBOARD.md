# MVP Dashboard

Two convergent goals. Every task below is tagged with which goal(s) it serves.

**Goal 1 (Synthetic E2E):** Generate synthetic discussion → AI-extract PDP → accept all deltas → view diagram+timeline in both Pro and Personal apps.

**Goal 2 (Human Beta):** Hand Personal app to human → chat → accept PDP data → detect event clusters → view SARF shifts meaningfully in Personal app → see timeline+diagram in Pro app.

## Evidence Base

All tasks below were derived from comprehensive codebase analysis on 2026-02-20.
Before questioning or re-investigating a task, read the relevant analysis first.

| Analysis | Covers | Tiers |
|----------|--------|-------|
| [PDP Extraction & Delta Acceptance](doc/analyses/2026-02-20_pdp_extraction_and_delta_acceptance.md) | Extraction pipeline, validation, commit flow, F1 metrics | T0-1, T0-2, T1-* |
| [Auto-Arrange](doc/analyses/2026-02-20_auto_arrange.md) | Layout algorithm, Gemini approach, what's needed | T2-1, T2-2, T2-3 |
| [Synthetic Pipeline](doc/analyses/2026-02-20_synthetic_pipeline.md) | Celery tasks, error handling, evaluators | T4-* |
| [Diagram Viewing & Sync](doc/analyses/2026-02-20_diagram_viewing_and_sync.md) | Scene loading, version conflicts, FR-2 violation, clusters | T0-3, T0-4, T2-4, T2-5, T2-6 |
| [Personal App Beta Readiness](doc/analyses/2026-02-20_personal_app_beta_readiness.md) | Chat UX, PDP drawer, timeline, PlanView | T3-* |
| [Server API & Data Model](doc/analyses/2026-02-20_server_api_and_data_model.md) | Endpoints, validation, sync, data integrity | T0-3, T0-4 |
| [Bugs & TODOs Inventory](doc/analyses/2026-02-20_bugs_and_todos_inventory.md) | Complete bug list, skipped tests, existing plans | All |

User's hand-written notes with additional context: [TODO.md](../../TODO.md)

### Spot-Check Log

| Date | Tasks Checked | Method | Findings |
|------|---------------|--------|----------|
| 2026-02-20 | T0-1, T0-2, T0-3, T0-4, T2-1, T4-* | Static code analysis + git log | T0-3 STALE (crash path no longer exists). All others confirmed. T4 descriptions refined (inline extraction, Exception swallowing). |

---

## Current State Summary

| Subsystem | Status | Blocking Goal |
|-----------|--------|---------------|
| Chat flow (Personal app) | Working | - |
| PDP extraction (AI→deltas) | Working but low quality (Events F1=0.09, SARF F1=0.11) | 1, 2 |
| Delta acceptance ("accept all") | Crashes (emotionalunit.py AttributeError, childOf bugs) | 1, 2 |
| Diagram auto-arrange | Non-functional (LLM-based, unreliable) | 1, 2 |
| Pro app file loading | Working but crashes on version conflict (pickle TypeError) | 1, 2 |
| Personal app timeline/clusters | Partially working (text overlap, no selection feedback, empty space) | 2 |
| Personal app PDP drawer | Working with UX gaps (no SARF legend, no onboarding) | 2 |
| Synthetic generation pipeline | Works manually, no error recovery, no auto-extraction trigger | 1 |
| GT/F1 evaluation | Not actionable (40% GT data broken, per-statement F1 indistinguishable across prompts) | 1 |
| Pro↔Personal data sync | Working but Pro app overwrites Personal data on conflict (FR-2 violation) | 1, 2 |
| Event cluster detection | Working (LLM-based, cached) | 2 |
| PlanView (Personal app) | Empty placeholder | 2 |

---

## Critical Path

The two goals share a common critical path. Items are ordered by dependency — later items cannot be verified until earlier ones work.

### Tier 0: Can't Demo Anything Without These

These are crash-level blockers. Both goals fail immediately without them.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T0-1** | Fix emotionalunit.py crash on PDP accept | 1, 2 | CRASH | 2026-02-20 ✓ | CC | `familydiagram/pkdiagram/scene/emotionalunit.py:34` | `self._layer` is None → `else` branch accesses `self._layer.id`. Guard needed in `update()`. |
| **T0-2** | Fix childOf bugs on accept (Conflict, Separated events) | 1, 2 | CRASH | 2026-02-20 ✓ | CC+H | `btcopilot/schema.py:674-830` | No code handles Shift/Conflict events in birth inference. Case 1 misfires on Separated creating phantom parents. Needs domain review of intended behavior. |
| ~~**T0-3**~~ | ~~Fix Pro app pickle TypeError on version conflict~~ | ~~1, 2~~ | ~~CRASH~~ | 2026-02-20: STALE | - | `familydiagram/pkdiagram/server_types.py:295` | All code paths set `self.data` to `bytes`. Crash cannot be triggered by current code. Remove or demote to "monitor." |
| **T0-4** | Fix Pro app FR-2 violation (applyChange overwrites Personal data) | 1, 2 | DATA LOSS | 2026-02-20 ✓ | CC+H | `familydiagram/pkdiagram/server_types.py`, `familydiagram/pkdiagram/models/serverfilemanagermodel.py:538` | `applyChange` ignores refreshed `diagramData` argument entirely — returns `DiagramData` from closed-over local bytes. Must merge PDP/cluster fields from server. Needs review of merge semantics. |

### Tier 1: Extraction Must Produce Usable Data

Even if accepting doesn't crash, the extracted data must be good enough to be useful.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T1-1** | Add PairBond extraction examples to fdserver prompt | 1, 2 | HIGH | H | `fdserver/...prompts...` | Requires domain expertise to write clinically accurate examples. CC can scaffold but human must validate content. |
| **T1-2** | Add 10+ event extraction examples to fdserver prompt | 1, 2 | HIGH | H | `fdserver/...prompts...` | Same — needs domain expert to craft representative event examples with correct SARF coding. |
| **T1-3** | Require Event.description in validation (reject null) | 1, 2 | MEDIUM | CC | `btcopilot/pdp.py:187-191` | Currently warns but doesn't reject. Straightforward validation change + test. |
| **T1-4** | Require Event.dateTime (use 1/1/YYYY with low dateCertainty for vague dates) | 1, 2 | MEDIUM | CC+H | `btcopilot/pdp.py`, fdserver prompt | Validation change is CC-automatable. Prompt wording for date estimation needs human review. |
| **T1-5** | Include current date in extraction prompt | 2 | LOW | CC | fdserver prompt | Inject `datetime.now()` into prompt context. Mechanical change. |

### Tier 2: Diagram Must Render Coherently

Accepted data must be viewable as a family diagram in both apps.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T2-1** | Implement deterministic auto-arrange algorithm | 1, 2 | HIGH | 2026-02-20 ✓ | CC+H | `btcopilot/arrange.py`, `btcopilot/pro/routes.py:923-1032` | Still 100% Gemini-based, zero deterministic code. CC can implement the graph algorithm but needs human review of layout aesthetics. **Largest single item (~2-3 weeks).** |
| **T2-2** | Add error handling to arrange endpoint | 1, 2 | MEDIUM | 2026-02-20 ✓ | CC | `btcopilot/pro/routes.py:1032` | No try/except. Mechanical fix. |
| **T2-3** | Show arrange error feedback in UI | 1, 2 | LOW | - | CC | `familydiagram/pkdiagram/documentview/documentcontroller.py:927` | `_onError()` only logs to console. |
| **T2-4** | Fix _do_addItem missing relationshipTriangle symbols | 1, 2 | MEDIUM | - | CC | `familydiagram/pkdiagram/scene/scene.py:433` | Needs to mirror relationshipTarget symbol logic. |
| **T2-5** | Fix baseline view in new diagrams | 2 | MEDIUM | - | CC+H | familydiagram views code | Needs investigation to determine root cause. |
| **T2-6** | Fix `_log not defined` when re-opening after deleting views | 1, 2 | LOW | - | CC | familydiagram views code | Layer reference cleanup. |

### Tier 3: Personal App Must Present Data Meaningfully (Goal 2)

Beta testers need to understand what the app is showing them.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T3-1** | Fix cluster graph text overlap | 2 | HIGH | CC | `familydiagram/pkdiagram/resources/qml/Personal/LearnView.qml` | QML layout fix. Needs MCP testing to verify. |
| **T3-2** | Add event selection indication on cluster graph | 2 | MEDIUM | CC | Same | Add visual feedback state to QML. |
| **T3-3** | Fix empty space to right of clusters | 2 | MEDIUM | CC | Same | QML layout fix. |
| **T3-4** | SARF extraction should show direction format | 2 | MEDIUM | CC | PDPEventCard.qml | Show "Symptom: Up" instead of raw coding. Format string change. |
| **T3-5** | Rename "User"→"Client", "Assistant"→"Coach" | 2 | LOW | CC | DiscussView.qml, prompts, server | Multi-file string rename. Grep + replace. |
| **T3-6** | Scroll to bottom on chat submit | 2 | LOW | CC | DiscussView.qml | Standard QML ListView positioning. |
| **T3-7** | Click event in timeline → highlight people in diagram | 2 | MEDIUM | CC+H | familydiagram scene code | Needs investigation of signal plumbing between timeline and scene. |

### Tier 4: Synthetic Pipeline Must Be Reliable (Goal 1)

Manual synthetic generation works but breaks under real usage.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T4-1** | Fix Celery task error handling (currently swallows Exception) | 1 | HIGH | 2026-02-20 ✓ | CC | `btcopilot/training/tasks.py` | Broad `except Exception` returns `{"success": False}` — Celery sees SUCCESS. Should re-raise or use specific exceptions. |
| **T4-2** | Auto-trigger extraction after synthetic generation | 1 | HIGH | 2026-02-20 ✓ | CC | `btcopilot/training/tasks.py` | Extraction is inline per-turn via `ask_fn`, not post-generation. Dashboard description was imprecise — real gap is that `skip_extraction=True` path has no recovery. |
| **T4-3** | Add Discussion.status state machine | 1 | MEDIUM | 2026-02-20 ✓ | CC | `btcopilot/personal/models/discussion.py` | Only `extracting` boolean exists. Needs enum column + migration. |
| **T4-4** | Integrate quality+coverage evaluators into Celery task | 1 | MEDIUM | 2026-02-20 ✓ | CC+H | `btcopilot/training/tasks.py` | `ConversationSimulator.run()` never calls evaluators — `result.quality` and `result.coverage` always None. CC can wire them in, human reviews thresholds. |
| **T4-5** | Validate generated persona JSON | 1 | LOW | - | CC | `btcopilot/tests/personal/synthetic.py` | Add JSONDecodeError handling. |

### Tier 5: GT/F1 Must Produce Actionable Signal (Goal 1)

Without this, we can't measure whether prompt changes improve extraction.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T5-1** | Fix 18 GT events with person=None | 1 | HIGH | H | SARF editor (training app) | Manual data fix by domain expert. Must review each event and assign correct person. |
| **T5-2** | Fix 24 GT events with placeholder descriptions | 1 | HIGH | H | SARF editor | Must read original discussion text and write correct descriptions. Domain expertise required. |
| **T5-3** | Add dateCertainty to all 88 GT events | 1 | MEDIUM | H | SARF editor | Must assess each event's temporal specificity. Domain judgment. |
| **T5-4** | Revert f1_metrics.py workarounds | 1 | MEDIUM | CC | `btcopilot/training/f1_metrics.py` | Remove person=None wildcard and placeholder auto-pass. Mechanical once T5-1/T5-2 done. |
| **T5-5** | Add SARF editor validation (require person link + description) | 1 | MEDIUM | CC | Training app event form | Form validation. Straightforward. |
| **T5-6** | Implement cumulative F1 metric | 1 | HIGH | CC+H | `btcopilot/training/f1_metrics.py` | Algorithm is CC-implementable. Human reviews whether metric captures intended signal. |
| **T5-7** | Scale GT to 20-30 coded discussions | 1 | HIGH | H | Training app | Pure human labor — clinician must code each discussion. |

---

## Automation Summary

**Legend:** CC = Claude Code can implement fully. CC+H = CC implements, human reviews/decides. H = Requires human domain expertise or manual data entry.

### CC-Automatable (knock these out first)

| Task | Tier | Effort | What CC Does |
|------|------|--------|-------------|
| T0-1 | T0 | ~1 hr | Guard `self._layer` in `emotionalunit.py:34` `else` branch + test |
| T1-3 | T1 | ~1 hr | Change warn→reject for null `Event.description` in `pdp.py` + test |
| T1-5 | T1 | ~30 min | Inject `datetime.now()` into extraction prompt context |
| T2-2 | T2 | ~1 hr | Add try/except to arrange endpoint, return structured error |
| T2-3 | T2 | ~1 hr | Surface arrange error in QML UI instead of just logging |
| T2-4 | T2 | ~2 hr | Add relationshipTriangle symbol creation in `_do_addItem` |
| T2-6 | T2 | ~2 hr | Fix layer reference cleanup on view deletion |
| T3-1 | T3 | ~2 hr | Fix QML text overlap in cluster graph |
| T3-2 | T3 | ~1 hr | Add selection highlight to cluster graph events |
| T3-3 | T3 | ~1 hr | Fix cluster graph layout spacing |
| T3-4 | T3 | ~1 hr | Format SARF display as "Symptom: Up" |
| T3-5 | T3 | ~1 hr | Rename User→Client, Assistant→Coach across codebase |
| T3-6 | T3 | ~30 min | Add `positionViewAtEnd()` on chat submit |
| T4-1 | T4 | ~1 hr | Fix exception handling — re-raise or use specific exceptions |
| T4-3 | T4 | ~2 hr | Add Discussion.status enum + migration |
| T4-5 | T4 | ~30 min | Add JSONDecodeError handling to persona generation |
| T5-4 | T5 | ~1 hr | Remove f1_metrics.py workarounds (after T5-1/T5-2 done) |
| T5-5 | T5 | ~2 hr | Add SARF editor validation (person link + description required) |

**18 tasks, ~20 hrs of CC sessions (you approving, CC driving). Individual estimates are speculative — some may balloon on investigation.**

### CC+Human (CC implements, human reviews)

| Task | Tier | Effort | CC Does | Human Does |
|------|------|--------|---------|------------|
| T0-2 | T0 | ~4 hr | Implement fix in birth inference | Review: what *should* Conflict/Separated events infer? |
| T0-4 | T0 | ~4 hr | Implement field-level merge in `applyChange` | Review: which fields does Pro app own vs. Personal? |
| T1-4 | T1 | ~2 hr | Add validation + prompt change | Review prompt wording for date estimation |
| T2-1 | T2 | ~2-3 wk | Implement graph algorithm | Review layout aesthetics, edge cases |
| T2-5 | T2 | ~2 hr | Investigate + fix | Verify UX is acceptable |
| T3-7 | T3 | ~3 hr | Implement signal plumbing | Verify highlighting behavior |
| T4-2 | T4 | ~2 hr | Wire extraction into skip path | Review: should extraction be async or inline? |
| T4-4 | T4 | ~2 hr | Call evaluators in Celery task | Review quality/coverage thresholds |
| T5-6 | T5 | ~4 hr | Implement cumulative F1 algorithm | Validate metric captures intended signal |

**9 tasks. CC implements, you review design decisions before and results after. ~3-4 weeks total (dominated by T2-1 auto-arrange).**

### Human-Only (domain expertise / manual data entry)

| Task | Tier | Effort | Why Human |
|------|------|--------|-----------|
| T1-1 | T1 | ~4 hr | Writing clinically accurate PairBond extraction examples |
| T1-2 | T1 | ~8 hr | Writing 10+ diverse event extraction examples with correct SARF |
| T5-1 | T5 | ~3 hr | Review 18 events, assign correct person link |
| T5-2 | T5 | ~4 hr | Read transcripts, write correct event descriptions |
| T5-3 | T5 | ~2 hr | Assess temporal specificity of 88 events |
| T5-7 | T5 | ~40+ hr | Clinician codes 17-27 additional discussions |

**6 tasks, ~60+ hrs of your time (CC can't help — domain expertise and manual data entry). Dominated by T5-7 GT scaling.**

### Recommended Automation Execution Order

Start with the CC-automatable tasks that unblock the most downstream work:

1. **T0-1** (emotionalunit crash) — unblocks all PDP acceptance testing
2. **T1-3, T1-5** (validation + date) — improves extraction output immediately
3. **T2-2, T2-4, T2-6** (scene fixes) — unblocks diagram viewing
4. **T3-1 through T3-6** (Personal app UX) — batch of independent QML fixes
5. **T4-1, T4-3, T4-5** (synthetic pipeline) — hardens generation
6. **T5-5** (SARF editor validation) — prevents future GT corruption

---

## Work Estimates

| Tier | Task Count | Rough Effort | Dependency |
|------|-----------|--------------|------------|
| T0 (Crash blockers) | 4 | 3-5 days | None — start here |
| T1 (Extraction quality) | 5 | 3-5 days | Can parallel with T0 (prompt work is independent of code fixes) |
| T2 (Diagram rendering) | 6 | 2-4 weeks | T0 must be done. Auto-arrange (T2-1) is the largest item. |
| T3 (Personal app UX) | 7 | 3-5 days | T0, T1 should be done. |
| T4 (Synthetic pipeline) | 5 | 3-4 days | Independent of T0-T3. |
| T5 (GT/F1) | 7 | 2-3 weeks | T5-1 through T5-5 are manual data work + training app fixes. T5-6 is code. T5-7 is ongoing effort. |

**Total estimate for both MVPs: 5-9 weeks** depending on how much can be parallelized.

---

## Recommended Execution Order

### Sprint 1 (Week 1-2): Unblock "Accept All"

**Objective:** A user can accept all PDP items from a discussion without crashes, and the Pro app can open the resulting diagram file.

1. T0-1: Fix emotionalunit.py crash
2. T0-2: Fix childOf edge cases
3. T0-3: Fix pickle TypeError
4. T0-4: Fix FR-2 violation
5. T1-3: Require Event.description
6. T1-4: Require Event.dateTime

**In parallel (prompt work, no code dependency):**
- T1-1: Add PairBond examples to prompt
- T1-2: Add event examples to prompt
- T1-5: Include current date in prompt

**Verification:** Generate a synthetic discussion → extract → accept all → open in Pro app → no crashes.

### Sprint 2 (Week 2-4): Auto-Arrange + Extraction Quality

**Objective:** Accepted diagram auto-arranges into a readable family diagram. Extraction quality reaches "useful" level.

1. T2-1: Implement deterministic auto-arrange (the big one)
2. T2-2: Error handling for arrange endpoint
3. T2-4: Fix relationshipTriangle symbols

**In parallel:**
- T5-1 through T5-5: Fix GT data + SARF editor validation
- T5-6: Implement cumulative F1

**Verification:** Diagram from accepted PDP data auto-arranges into recognizable family structure with generational alignment.

### Sprint 3 (Week 4-5): Personal App Beta Polish

**Objective:** A human beta tester can use the Personal app, understand what they see, and find value.

1. T3-1: Fix cluster text overlap
2. T3-2: Event selection feedback
3. T3-3: Fix empty space
4. T3-4: SARF direction format
5. T3-5: Rename User→Client, Assistant→Coach
6. T3-6: Scroll to bottom on submit

**In parallel:**
- T4-1 through T4-5: Harden synthetic pipeline
- T2-5: Fix baseline view

**Verification:** Hand app to non-technical person → they can chat, review extracted data, and navigate timeline without confusion.

### Sprint 4 (Week 5-7): E2E Synthetic Validation

**Objective:** Full synthetic E2E works reliably: generate → extract → accept → view in both apps.

1. Run full E2E synthetic test
2. Fix any remaining issues found
3. T5-7: Begin scaling GT to 20-30 discussions
4. Run cumulative F1 on expanded dataset
5. Iterate prompts based on cumulative F1 signal

**Verification:** Generate 5 synthetic discussions → all successfully produce viewable diagrams in both apps.

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Auto-arrange is 2-3 weeks of graph algorithm work | Delays everything in T2 | Consider simpler approach: just generational Y-alignment + basic horizontal spacing, skip complex constraint solving |
| Event extraction F1 may stay low even with prompt improvements | Goal 2 users see mostly wrong events | Scope MVP to People/PairBonds only (decision pending from 2025-12-27), hide events until quality improves |
| GT scaling to 20-30 discussions is manual labor | Blocks ability to measure prompt improvement | Build cumulative coding workflow first (Phase 3 in GT plan), time-trial to estimate total effort |
| Pro app applyChange fix (T0-4) may have subtle merge bugs | Data loss on concurrent edits | Test thoroughly with simultaneous Pro+Personal app edits |
| SARF variable extraction F1=0.11 (non-functional) | Timeline visualization shows wrong shift data | Hide SARF variables from user-facing views until extraction improves. Show only event kind + description + date. |
| Cluster detection is LLM-based (Gemini) | Inconsistent clustering across calls | Cache aggressively (already implemented). Consider deterministic fallback for temporal proximity grouping. |

---

## Deferred (Post-MVP)

These are tracked but explicitly not blocking either MVP goal.

- PlanView content generation (action items based on patterns)
- SARF variable editing/display in Personal app (F1 too low)
- IRR study (Cohen's/Fleiss' Kappa) — decision logged 2026-01-08
- Fine-tuning on GT dataset
- Per-statement F1 diagnostics
- Conversation flow prompt versioning
- LLM model selection for synthetic generation
- Export to PDF
- Pattern intelligence layer
- Add Notes to PDP feature (plan exists: `btcopilot/doc/plans/ADD_NOTES_TO_PDP.md`)

---

## Key Metrics to Track

| Metric | Current | Target (MVP) | How to Measure |
|--------|---------|--------------|----------------|
| People F1 | 0.65 | > 0.7 | Cumulative F1 on 20+ discussions |
| PairBond F1 | 0.78 (explicit: 0.0) | > 0.5 (explicit) | After prompt fix, cumulative F1 |
| Event F1 | 0.09 | > 0.4 | After prompt fix + GT data fix |
| SARF Variable F1 | 0.11 | Deferred | Not targeting for MVP |
| Accept-all crash rate | ~100% (crashes on most accept) | 0% | Manual testing |
| Auto-arrange success rate | ~40% (LLM-based) | > 90% | Deterministic algorithm |
| E2E synthetic success rate | Unknown (manual only) | > 95% | Automated test suite |
| GT coded discussions | 3 | 20-30 | Training app count |
| Beta tester task completion | Untested | > 80% can complete chat+review flow | User testing |

---

## Architecture Reference

| Component | Location | Purpose |
|-----------|----------|---------|
| PDP extraction | `btcopilot/pdp.py` | Delta extraction, validation, cumulative rebuild |
| Delta acceptance | `btcopilot/schema.py:463-976` | commit_pdp_items(), inference, ID remapping |
| Chat orchestration | `btcopilot/personal/chat.py` | ask(), PDP update, response direction |
| Extraction prompts | `btcopilot/personal/prompts.py` (defaults), `fdserver` (production overrides) |
| F1 metrics | `btcopilot/training/f1_metrics.py` | Entity matching, F1 calculation |
| Cluster detection | `btcopilot/personal/clusters.py` | LLM-based temporal clustering |
| Synthetic generation | `btcopilot/tests/personal/synthetic.py` | ConversationSimulator, personas |
| Synthetic web UI | `btcopilot/training/routes/synthetic.py` | Web form, Celery task management |
| Scene system | `familydiagram/pkdiagram/scene/` | Person, Event, Marriage rendering |
| Auto-arrange | `btcopilot/arrange.py`, `btcopilot/pro/routes.py:923-1032` | Layout data + Gemini prompt |
| Data sync | `familydiagram/doc/specs/DATA_SYNC_FLOW.md` | Optimistic locking, domain partitioning |
| Personal app QML | `familydiagram/pkdiagram/resources/qml/Personal/` | DiscussView, LearnView, PDPSheet |
| GT strategy plan | `btcopilot/doc/plans/GT_STRATEGY_REALIGNMENT.md` | 4-phase GT improvement plan |
| Decision log | `btcopilot/decisions/log.md` | Major architectural decisions |
