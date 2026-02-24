# MVP Dashboard

Three goals. Every task below is tagged with which goal(s) it serves. Goals 1 and 2 are Personal-app-only; Goal 3 adds Pro app viewing.

**Goal 1 (Synthetic E2E):** Generate synthetic discussion → AI-extract PDP → accept all deltas → view diagram+timeline in Personal app.

**Goal 2 (Human Beta):** Hand Personal app to human → chat → accept PDP data → detect event clusters → view SARF shifts meaningfully in Personal app.

**Goal 3 (Pro App Viewing):** Open Personal-app-generated diagrams in the Pro app with correct layout. Deferred — Pro app is in production; avoid risky changes to core behavior until Goals 1+2 are validated.

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
| 2026-02-24 | T1-1, T1-2, T5-4, T5-6, F1 numbers | Code audit vs dashboard claims | T1-1 DONE (PairBond examples in fdserver). T1-2 DONE (18 event examples in fdserver). T5-4 N/A (no workarounds exist to revert). T5-6 DONE (cumulative F1 implemented + wired into admin/audit routes). F1 numbers stale (from Dec 2025 GT, before Feb 2026 prompt improvements). |
| 2026-02-24 | All open tasks (T0-4, T1-4, T2-1, T2-5, T3-7, T4-2, T4-4, T5-1–T5-3, T5-7) | Code audit via subagents reading actual source | All confirmed real. T0-4 DEFERRED (Pro app in production, Personal has no users yet, Pro is read-only re: Personal data — risk of destabilizing Pro save path outweighs benefit). T2-5 root cause unknown (needs investigation session). T5-3 low impact (F1 defaults to Approximate gracefully). |

---

## Current State Summary

*Last updated: 2026-02-24 (Goal 3 split out: Pro app viewing deferred. Goals 1+2 = Personal app only.)*

| Subsystem | Status | Blocking Goal |
|-----------|--------|---------------|
| Chat flow (Personal app) | Working | - |
| PDP extraction (AI→deltas) | Working. F1 numbers stale (Dec 2025 GT snapshot, before Feb 2026 prompt overhaul adding 18 event + 2 PairBond examples). Actual current quality unknown — requires re-running F1 against cleaned GT. | 1, 2 |
| Delta acceptance ("accept all") | Working. T0-1 emotionalunit crash fixed. T0-2 phantom pair bonds fixed. T0-5 birth child resolution crash fixed. Accept-all no longer crashes on birth/separated/divorced events. | 1, 2 |
| Diagram auto-arrange | Non-functional (LLM-based, unreliable). Moved to Goal 3 (Pro app). | 3 |
| Pro app file loading | T0-3 STALE — crash cannot be triggered by current code. Goal 3. | 3 |
| Personal app timeline/clusters | Improved. Cluster label overlap fixed (T3-1), optimal zoom (T3-3), selection border added. | 2 |
| Personal app PDP drawer | Improved. Single-line SARF format (T3-4), Client/Coach labels (T3-5). Still no SARF legend or onboarding. | 2 |
| Synthetic generation pipeline | Improved. Exceptions propagate (T4-1), DiscussionStatus tracking (T4-3), JSON validation (T4-5). Still no auto-extraction trigger. | 1 |
| GT/F1 evaluation | Cumulative F1 code complete (T5-6 done). SARF editor validation prevents new bad data (T5-5 done). Prompt examples complete (T1-1, T1-2 done). **Remaining blocker: GT data quality** — 18 events with person=None, 24 with placeholder descriptions. F1 numbers from Dec 2025 snapshot, not re-run since Feb 2026 prompt changes. | 1 |
| Pro↔Personal data sync | Working. FR-2 violation (T0-4) confirmed but deferred to Goal 3. Pro is in production; read-only re: Personal data. | 3 |
| Event cluster detection | Working (LLM-based, cached) | 2 |
| PlanView (Personal app) | Empty placeholder | 2 |

Review tracker: [REVIEW.md](doc/log/mvp_dashboard/REVIEW.md)

---

## Critical Path

The two goals share a common critical path. Items are ordered by dependency — later items cannot be verified until earlier ones work.

### Tier 0: Can't Demo Anything Without These

These are crash-level blockers. Both goals fail immediately without them.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T0-1** | ~~Fix emotionalunit.py crash on PDP accept~~ | 1, 2 | CRASH | 2026-02-20 ✅ | CC | `familydiagram/pkdiagram/scene/emotionalunit.py:34` | DONE. Guard added in `update()`. |
| ~~**T0-2**~~ | ~~Fix childOf bugs on accept (Conflict, Separated events)~~ | 1, 2 | ~~CRASH~~ | 2026-02-24 ✓ | CC+H | `btcopilot/schema.py` | **Not a bug**: `isPairBond()` correctly infers pair bonds for Separated/Divorced (those events imply the couple existed). Original MCP harness bug was fixed earlier in inspector.py. Pair bond inference validated with tests. |
| ~~**T0-5**~~ | ~~Fix birth event child resolution crash in accept flow~~ | 1, 2 | ~~CRASH~~ | 2026-02-24 ✓ | CC | `btcopilot/schema.py:782-796` | **Fixed**: `_create_inferred_birth_items` Case 2 (person set, no spouse) created spouse but never created child, leaving `event.child=None`. Scene then crashed at `eventsFor(item.child())`. Fix: Case 2 now creates inferred child when `event.child` is unset. |
| ~~**T0-3**~~ | ~~Fix Pro app pickle TypeError on version conflict~~ | ~~1, 2~~ | ~~CRASH~~ | 2026-02-20: STALE | - | `familydiagram/pkdiagram/server_types.py:295` | All code paths set `self.data` to `bytes`. Crash cannot be triggered by current code. Remove or demote to "monitor." |
| **T0-4** | Fix Pro app FR-2 violation (applyChange overwrites Personal data) | 3 | DATA LOSS | 2026-02-20 ✓ | CC+H | `familydiagram/pkdiagram/server_types.py`, `familydiagram/pkdiagram/models/serverfilemanagermodel.py:538` | **DEFERRED to Goal 3**: Pro app is in production; Personal app has no real users yet. Bug only fires on concurrent Pro+Personal writes to the same diagram. Risk of destabilizing Pro save path outweighs benefit until Personal has users. Pro app's role re: Personal data is read-only for now. `applyChange` ignores refreshed `diagramData` argument — returns `DiagramData` from closed-over local bytes. Fix pattern exists in Personal app's `personalappcontroller.py:260-277`. |

### Tier 1: Extraction Must Produce Usable Data

Even if accepting doesn't crash, the extracted data must be good enough to be useful.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T1-1** | ~~Add PairBond extraction examples to fdserver prompt~~ | 1, 2 | HIGH | H | `fdserver/prompts/private_prompts.py` | DONE 2026-02-15. 2 PairBond-specific examples (`[PAIR_BOND_EXTRACTION]`, `[PAIR_BOND_WITH_MARRIAGE_EVENT]`) + explicit trigger rules + ID namespace rules. |
| **T1-2** | ~~Add 10+ event extraction examples to fdserver prompt~~ | 1, 2 | HIGH | H | `fdserver/prompts/private_prompts.py` | DONE 2026-02-15. 18 labeled event examples covering: over-extraction, under-extraction (birth, age, shifts, anxiety, distance), relationship targets, timeframe incidents, duplicate detection, saturation, triangles, SARF shifts, death events. |
| **T1-3** | ~~Require Event.description in validation (reject null)~~ | 1, 2 | MEDIUM | CC | `btcopilot/pdp.py:187-191` | DONE 2026-02-20. Validation rejects null/placeholder descriptions. |
| **T1-4** | ~~Require Event.dateTime (use 1/1/YYYY with low dateCertainty for vague dates)~~ | 1, 2 | MEDIUM | CC+H | `btcopilot/pdp.py`, fdserver prompt | DONE 2026-02-24. Validator now rejects null dateTime (pdp.py:193-196). Prompt already had "CRITICAL: dateTime is REQUIRED" + 18 examples with dateTime. Retry mechanism re-prompts LLM on failure. |
| **T1-5** | ~~Include current date in extraction prompt~~ | 2 | LOW | CC | fdserver prompt | DONE 2026-02-20. Already implemented. |

### Tier 2: Diagram Must Render Coherently (Goal 3 — Pro App)

Pro app diagram viewing. Deferred until Goals 1+2 validated. Pro app is in production — avoid risky changes to core behavior.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T2-1** | Implement deterministic auto-arrange algorithm | 3 | HIGH | 2026-02-20 ✓ | CC+H | `btcopilot/arrange.py`, `btcopilot/pro/routes.py:923-1032` | Still 100% Gemini-based, zero deterministic code. CC can implement the graph algorithm but needs human review of layout aesthetics. **Largest single item (~2-3 weeks).** |
| **T2-2** | ~~Add error handling to arrange endpoint~~ | 3 | MEDIUM | 2026-02-20 ✅ | CC | `btcopilot/pro/routes.py:1032` | DONE 2026-02-20. |
| **T2-3** | ~~Show arrange error feedback in UI~~ | 3 | LOW | 2026-02-20 ✅ | CC | `familydiagram/pkdiagram/documentview/documentcontroller.py:927` | DONE 2026-02-20. QMessageBox.warning on HTTPError. |
| **T2-4** | ~~Fix _do_addItem missing relationshipTriangle symbols~~ | 3 | MEDIUM | 2026-02-20 | CC | `familydiagram/pkdiagram/scene/scene.py:433` | REVERTED — triangles are exclusively Inside/Outside. Domain constraint now in `doc/specs/BOWEN_THEORY.md`. |
| **T2-5** | Fix baseline view in new diagrams | 3 | MEDIUM | - | CC+H | familydiagram views code | Needs investigation to determine root cause. |
| **T2-6** | ~~Fix `_log not defined` when re-opening after deleting views~~ | 3 | LOW | 2026-02-20 | CC | familydiagram views code | Cannot reproduce. Likely fixed by T0-1 or never existed as described. |

### Tier 3: Personal App Must Present Data Meaningfully (Goal 2)

Beta testers need to understand what the app is showing them.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T3-1** | ~~Fix cluster graph text overlap~~ | 2 | HIGH | CC | `familydiagram/pkdiagram/resources/qml/Personal/LearnView.qml` | DONE 2026-02-20. Constrained narrow label width from 240 → max(barWidth,80). |
| **T3-2** | ~~Add event selection indication on cluster graph~~ | 2 | MEDIUM | CC | Same | DONE 2026-02-20. Already implemented (dot scale, ring highlights, row color, border). |
| **T3-3** | ~~Fix empty space to right of clusters~~ | 2 | MEDIUM | CC | Same | DONE 2026-02-20. Used calculateOptimalZoom() instead of hardcoded 2.0. |
| **T3-4** | ~~SARF extraction should show direction format~~ | 2 | MEDIUM | CC | PDPEventCard.qml | DONE 2026-02-20. Uses variableLabel() and relationshipLabel(). |
| **T3-5** | ~~Rename "User"→"Client", "Assistant"→"Coach"~~ | 2 | LOW | CC | DiscussView.qml, prompts, server | DONE 2026-02-20. |
| **T3-6** | ~~Scroll to bottom on chat submit~~ | 2 | LOW | CC | DiscussView.qml | DONE 2026-02-20. Already implemented. |
| **T3-7** | Click event in timeline → highlight people in diagram | 2 | MEDIUM | CC+H | familydiagram scene code | Needs investigation of signal plumbing between timeline and scene. |

### Tier 4: Synthetic Pipeline Must Be Reliable (Goal 1)

Manual synthetic generation works but breaks under real usage.

| # | Task | Goal | Severity | Verified | Auto | File(s) | Notes |
|---|------|------|----------|----------|------|---------|-------|
| **T4-1** | ~~Fix Celery task error handling (currently swallows Exception)~~ | 1 | HIGH | 2026-02-20 ✅ | CC | `btcopilot/training/tasks.py` | DONE 2026-02-20. Re-raises ValueError, uses autoretry_for on transient errors. |
| **T4-2** | Auto-trigger extraction after synthetic generation | 1 | HIGH | 2026-02-20 ✓ | CC | `btcopilot/training/tasks.py` | Extraction is inline per-turn via `ask_fn`, not post-generation. Dashboard description was imprecise — real gap is that `skip_extraction=True` path has no recovery. |
| **T4-3** | ~~Add Discussion.status state machine~~ | 1 | MEDIUM | 2026-02-20 ✅ | CC | `btcopilot/personal/models/discussion.py` | DONE 2026-02-20. DiscussionStatus enum + migration + transitions at all 5 mutation points. |
| **T4-4** | Integrate quality+coverage evaluators into Celery task | 1 | MEDIUM | 2026-02-20 ✓ | CC+H | `btcopilot/training/tasks.py` | `ConversationSimulator.run()` never calls evaluators — `result.quality` and `result.coverage` always None. CC can wire them in, human reviews thresholds. |
| **T4-5** | ~~Validate generated persona JSON~~ | 1 | LOW | 2026-02-20 ✅ | CC | `btcopilot/tests/personal/synthetic.py` | DONE 2026-02-20. JSONDecodeError → ValueError with context. |

### Tier 5: GT/F1 Must Produce Actionable Signal (Goal 1)

Without this, we can't measure whether prompt changes improve extraction.

| # | Task | Goal | Severity | Auto | File(s) | Notes |
|---|------|------|----------|------|---------|-------|
| **T5-1** | Fix 18 GT events with person=None | 1 | HIGH | H | SARF editor (training app) | Manual data fix by domain expert. Must review each event and assign correct person. |
| **T5-2** | Fix 24 GT events with placeholder descriptions | 1 | HIGH | H | SARF editor | Must read original discussion text and write correct descriptions. Domain expertise required. |
| **T5-3** | Add dateCertainty to all 88 GT events | 1 | MEDIUM | H | SARF editor | Must assess each event's temporal specificity. Domain judgment. |
| ~~**T5-4**~~ | ~~Revert f1_metrics.py workarounds~~ | 1 | ~~MEDIUM~~ | ~~CC~~ | `btcopilot/training/f1_metrics.py` | N/A 2026-02-24. Code audit found no workarounds to revert — no person=None wildcards or placeholder auto-passes exist. Events with missing person/description are skipped cleanly (lines 625-626, 653-655). Low F1 accurately reflects GT data quality, not masking. |
| **T5-5** | ~~Add SARF editor validation (require person link + description)~~ | 1 | MEDIUM | CC | Training app event form | DONE 2026-02-20. Client + server validation. |
| **T5-6** | ~~Implement cumulative F1 metric~~ | 1 | HIGH | CC+H | `btcopilot/training/f1_metrics.py` | DONE. `calculate_cumulative_f1()` (line 945) and `calculate_all_cumulative_f1()` (line 1050) fully implemented. Wired into admin route (line 271) and audit route (line 99). Builds cumulative AI+GT PDPs via `pdp.cumulative()`, runs entity matching, computes per-type and aggregate F1. |
| **T5-7** | Scale GT to 20-30 coded discussions | 1 | HIGH | H | Training app | Pure human labor — clinician must code each discussion. |

---

## Remaining Work Summary

**Legend:** CC = Claude Code can implement fully. CC+H = CC implements, human reviews/decides. H = Requires human domain expertise or manual data entry.

### Goals 1+2 (Personal App) — Open Tasks

| Task | Tier | Goal | Auto | Effort | What's Needed |
|------|------|------|------|--------|---------------|
| ~~T1-4~~ | ~~T1~~ | ~~1, 2~~ | ~~CC+H~~ | — | ~~DONE 2026-02-24. Validator enforces dateTime; prompt already correct.~~ |
| T4-2 | T4 | 1 | CC | ~2 hr | Wire extraction trigger after synthetic generation completes |
| T4-4 | T4 | 1 | CC+H | ~2 hr | Call evaluators in Celery task (human reviews quality/coverage thresholds) |
| T3-7 | T3 | 2 | CC+H | ~3 hr | Signal plumbing: timeline event click → diagram person highlight (human verifies UX) |
| T5-1 | T5 | 1 | H | ~3 hr | Review 18 GT events with person=None, assign correct person link |
| T5-2 | T5 | 1 | H | ~4 hr | Read transcripts, write correct event descriptions for 24 placeholder events |
| T5-3 | T5 | 1 | H | ~2 hr | Assess temporal specificity of 88 GT events (low impact — F1 defaults gracefully) |
| T5-7 | T5 | 1 | H | ~40+ hr | Clinician codes 17-27 additional discussions |

**Code tasks: ~9 hrs CC sessions. Human tasks: ~49+ hrs (dominated by T5-7 GT scaling).**

### Goal 3 (Pro App — Deferred)

| Task | Tier | Auto | Effort | What's Needed |
|------|------|------|--------|---------------|
| T0-4 | T0 | CC+H | ~4 hr | Field-level merge in Pro app `applyChange` (human reviews field ownership) |
| T2-1 | T2 | CC+H | ~2-3 wk | Deterministic auto-arrange algorithm (human reviews layout aesthetics) |
| T2-5 | T2 | CC+H | ~2 hr | Investigate + fix baseline view in new diagrams (human verifies UX) |
| T5-7 | T5 | ~40+ hr | Clinician codes 17-27 additional discussions |

### Recommended Execution Order (Goals 1+2)

1. ~~**T1-4** (dateTime validation)~~ DONE 2026-02-24
2. **T4-2** (auto-trigger extraction) — closes synthetic pipeline gap
3. **T4-4** (wire evaluators) — enables quality measurement for synthetics
4. **T3-7** (timeline → diagram highlight) — Personal app UX polish for beta
5. **T5-1, T5-2** (GT cleanup, human) — unblocks meaningful F1 signal
6. **T5-7** (GT scaling, human) — ongoing

---

## Work Estimates

| Tier | Goal | Open Tasks | Rough Effort | Dependency |
|------|------|-----------|--------------|------------|
| T0 (Crash blockers) | 1, 2 | All done (T0-4 deferred to Goal 3) | — | — |
| T1 (Extraction quality) | 1, 2 | All done | — | — |
| T2 (Diagram rendering) | 3 | T2-1, T2-5 | 2-4 weeks | Deferred until Goals 1+2 done |
| T3 (Personal app UX) | 2 | T3-7 only | ~3 hrs | None |
| T4 (Synthetic pipeline) | 1 | T4-2, T4-4 | ~4 hrs | None |
| T5 (GT/F1) | 1 | T5-1/T5-2/T5-3 (human), T5-7 (human) | ~9 hrs manual + 40+ hrs GT scaling | None |

**Goals 1+2 estimate: 1-2 weeks** (code tasks) + ongoing human GT work (T5-*).
**Goal 3 estimate: 2-4 weeks** (dominated by T2-1 auto-arrange). Deferred.

---

## Recommended Execution Order

### Sprint 1 (Week 1-2): Unblock "Accept All" — MOSTLY DONE

**Objective:** A user can accept all PDP items from a discussion without crashes.

1. ~~T0-1: Fix emotionalunit.py crash~~ DONE
2. ~~T0-2: Not a bug~~ — Separated/Divorced correctly infer pair bonds (2026-02-24)
3. ~~T0-3: Fix pickle TypeError~~ STALE — removed
4. ~~T0-4: FR-2 violation~~ — deferred to Goal 3 (Pro app)
5. ~~T0-5: Fix birth event child resolution crash~~ DONE (2026-02-24)
6. ~~T1-3: Require Event.description~~ DONE
7. ~~T1-4: Require Event.dateTime~~ DONE (2026-02-24)

**In parallel (prompt work, no code dependency):**
- ~~T1-1: Add PairBond examples to prompt~~ DONE (Feb 2026)
- ~~T1-2: Add event examples to prompt~~ DONE (Feb 2026)
- ~~T1-5: Include current date in prompt~~ DONE

**Status:** COMPLETE. All crash blockers fixed, all extraction validation done.

### Sprint 2: Extraction Quality + Synthetic Pipeline

**Objective:** Extraction produces timeline-ready data. Synthetic pipeline runs end-to-end reliably.

1. ~~T1-4: Require Event.dateTime~~ DONE (2026-02-24)
2. T4-2: Auto-trigger extraction after generation — open (CC)
3. T4-4: Integrate quality/coverage evaluators — open (CC+H)

**In parallel (Human):**
- T5-1 through T5-3: Fix GT data — open
- ~~T5-4: Revert f1_metrics.py workarounds~~ N/A (no workarounds exist)
- ~~T5-5: SARF editor validation~~ DONE
- ~~T5-6: Implement cumulative F1~~ DONE
- T5-7: Scale GT — ongoing

**Status:** Sprint 2 is the current focus.

### Sprint 3: Personal App Polish + E2E Validation

**Objective:** Full synthetic E2E works reliably in Personal app. Human beta tester can use the app meaningfully.

1. T3-7: Click event → highlight people — open (CC+H)
2. Run full E2E synthetic test (generate → extract → accept → view timeline in Personal app)
3. Fix any issues found
4. Run cumulative F1 on cleaned GT
5. Iterate prompts based on F1 signal

**Previously completed:**
- ~~T3-1 through T3-6~~ — all DONE
- ~~T4-1, T4-3, T4-5~~ — all DONE

**Verification:** Generate 5 synthetic discussions → all successfully produce viewable timelines in Personal app.

### Sprint 4 (Goal 3 — Deferred): Pro App Viewing

**Objective:** Personal-app-generated diagrams open and display correctly in Pro app.

1. T2-1: Implement deterministic auto-arrange — open (largest item, ~2-3 weeks)
2. T2-5: Fix baseline view in new diagrams — open (needs investigation)
3. T0-4: Fix FR-2 violation in applyChange — open (data loss risk on concurrent edits)

**Precondition:** Goals 1+2 validated first. Pro app is in production — avoid risky changes until Personal app has real users.

---

## Known Risks

| Risk | Impact | Goal | Mitigation |
|------|--------|------|------------|
| Event extraction F1 may stay low even with prompt improvements | Goal 2 users see mostly wrong events | 1, 2 | Scope MVP to People/PairBonds only (decision pending from 2025-12-27), hide events until quality improves |
| GT scaling to 20-30 discussions is manual labor | Blocks ability to measure prompt improvement | 1 | Build cumulative coding workflow first (Phase 3 in GT plan), time-trial to estimate total effort |
| SARF variable extraction F1=0.11 (non-functional) | Timeline visualization shows wrong shift data | 1, 2 | Hide SARF variables from user-facing views until extraction improves. Show only event kind + description + date. |
| Cluster detection is LLM-based (Gemini) | Inconsistent clustering across calls | 2 | Cache aggressively (already implemented). Consider deterministic fallback for temporal proximity grouping. |
| Auto-arrange is 2-3 weeks of graph algorithm work | Delays Pro app viewing | 3 | Consider simpler approach: just generational Y-alignment + basic horizontal spacing, skip complex constraint solving |
| Pro app applyChange fix (T0-4) may have subtle merge bugs | Data loss on concurrent edits | 3 | Test thoroughly with simultaneous Pro+Personal app edits |

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
| People F1 | 0.65 (Dec 2025, stale) | > 0.7 | Cumulative F1 on 20+ discussions |
| PairBond F1 | 0.78 (Dec 2025, stale; explicit: 0.0) | > 0.5 (explicit) | Re-run cumulative F1 after GT data fix |
| Event F1 | 0.09 (Dec 2025, stale) | > 0.4 | Re-run after GT data fix. Prompt examples added Feb 2026 — current score unknown. |
| SARF Variable F1 | 0.11 (Dec 2025, stale) | Deferred | Not targeting for MVP |
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
