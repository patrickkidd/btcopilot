# MVP Dashboard

## How to Use This Document

This is the primary development punchlist. It flows **goals → open tasks → reference material**.

**Re-evaluation:** Prompt "Re-evaluate the dashboard goals based on [new insight/question]" at any time. Goals and priorities may shift as the product evolves.

**Task workflow:** Pick the next open task under the highest-priority goal. Read the linked analysis before investigating. Mark done when verified. Never add defensive code — fix root causes.

**Legend:** CC = Claude Code. CC+H = CC implements, human reviews. H = Human only.

---

## Goal 1: Synthetic E2E

Generate synthetic discussion → AI-extract PDP → accept all deltas → view diagram+timeline in Personal app.

**Status: Pipeline functional.** E2E verified 2026-02-24 (test_e2e_synthetic.py). Remaining tasks are quality measurement, not pipeline blockers. Known issue: over-extraction (too many events on same date) breaks clustering — needs GT round to measure and tune.

### Open Tasks

| # | Task | Auto | Effort | Notes |
|---|------|------|--------|-------|
| T6-1 | Code GT for 3 synthetic discussions | H | ~6 hr | Generate 3 synthetic discussions, then manually code correct People/Events/PairBonds as ground truth in SARF editor. These become the first GT cases with known synthetic personas. |
| T6-2 | Establish cumulative F1 baseline | CC+H | ~1 hr | Run cumulative F1 against the 3 new GT cases from T6-1. Records baseline scores for People, PairBond, Event, SARF extraction. All future prompt/extraction changes measured against this. |
| T4-4 | Wire quality/coverage evaluators into Celery task | CC+H | ~2 hr | `result.quality` and `result.coverage` always None. [Analysis](doc/analyses/2026-02-20_synthetic_pipeline.md) |
| T5-1 | Fix 18 GT events with person=None | H | ~3 hr | SARF editor. Assign correct person link per event. |
| T5-2 | Fix 24 GT events with placeholder descriptions | H | ~4 hr | Read transcripts, write correct descriptions. |
| T5-3 | Add dateCertainty to 88 GT events | H | ~2 hr | Low impact — F1 defaults to Approximate gracefully. |
| T5-7 | Scale GT to 20-30 coded discussions | H | ~40+ hr | Clinician codes each discussion. Ongoing. |

### Done

T0-1, T0-2, T0-3, T0-5 (crash blockers), T1-1 through T1-5 (extraction quality), T4-1 through T4-5 (synthetic pipeline), T5-4 through T5-6 (F1 infrastructure). T4-2 not needed (extraction is inline per-turn).

---

## Goal 2: Human Beta

Hand Personal app to human → chat → accept PDP data → detect event clusters → view SARF shifts meaningfully.

**Status: Partially ready.** Chat, PDP drawer, timeline all functional. Missing: timeline→diagram event highlighting, SARF legend, onboarding.

### Open Tasks

| # | Task | Auto | Effort | Notes |
|---|------|------|--------|-------|
| T3-7 | Click event in timeline → highlight people in diagram | CC+H | ~3 hr | Signal plumbing between LearnView and scene. [Analysis](doc/analyses/2026-02-20_personal_app_beta_readiness.md) |

### Done

T3-1 through T3-6 (cluster overlap, selection, zoom, SARF format, Client/Coach labels, scroll-to-bottom).

---

## Goal 3: Pro App Viewing (Deferred)

Open Personal-app-generated diagrams in the Pro app with correct layout. **Deferred** — Pro app is in production; avoid risky changes until Goals 1+2 validated.

### Open Tasks

| # | Task | Auto | Effort | Notes |
|---|------|------|--------|-------|
| T0-4 | Fix FR-2 violation (applyChange overwrites Personal data) | CC+H | ~4 hr | Only fires on concurrent Pro+Personal writes. [Analysis](doc/analyses/2026-02-20_diagram_viewing_and_sync.md) |
| T2-1 | Implement deterministic auto-arrange algorithm | CC+H | ~2-3 wk | Replace Gemini with graph algorithm. [Analysis](doc/analyses/2026-02-20_auto_arrange.md) |
| T2-5 | Fix baseline view in new diagrams | CC+H | ~2 hr | Root cause unknown, needs investigation. |

### Done

T2-2, T2-3 (arrange error handling), T2-4, T2-6.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Over-extraction (many events on same date) | Clusters become meaningless (single-day buckets) | New GT round with synthetic personas → measure F1 → tune prompts |
| F1 stays low even with prompt tuning | Goal 2 users see wrong events | Scope MVP to People/PairBonds only; hide events until quality improves |
| SARF variable F1=0.11 (non-functional) | Timeline shows wrong shift data | Hide SARF variables from user-facing views |
| GT scaling is 40+ hrs manual labor | Blocks ability to measure improvement | Time-trial with cumulative coding workflow |
| Auto-arrange is 2-3 weeks | Delays Goal 3 | Consider simpler generational Y-alignment only |

---

## Metrics

| Metric | Last Measured | Target | Notes |
|--------|-------------|--------|-------|
| People F1 | 0.65 (Dec 2025, stale) | > 0.7 | Re-run after GT fix (T5-1/T5-2) |
| PairBond F1 | 0.78 (Dec 2025, stale) | > 0.5 explicit | Prompt examples added Feb 2026 |
| Event F1 | 0.09 (Dec 2025, stale) | > 0.4 | Unknown current score |
| GT coded discussions | 3 | 20-30 | T5-7 |
| E2E synthetic | Verified 2026-02-24 | > 95% automated | test_e2e_synthetic.py |

---

## Reference

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

### Key Files

| Component | Location |
|-----------|----------|
| PDP extraction + validation | `btcopilot/pdp.py` |
| Delta acceptance | `btcopilot/schema.py:463-976` |
| Chat orchestration | `btcopilot/personal/chat.py` |
| Extraction prompts | `btcopilot/personal/prompts.py` (defaults), `fdserver/prompts/` (production) |
| F1 metrics | `btcopilot/training/f1_metrics.py` |
| Synthetic generation | `btcopilot/tests/personal/synthetic.py` |
| E2E pipeline test | `btcopilot/tests/personal/test_e2e_synthetic.py` |
| Personal app QML | `familydiagram/pkdiagram/resources/qml/Personal/` |
| GT strategy | `btcopilot/doc/plans/GT_STRATEGY_REALIGNMENT.md` |
| Decision log | `btcopilot/decisions/log.md` |
| Hand-written notes | [TODO.md](../../TODO.md) |

### Verification Log

| Date | Checked | Findings |
|------|---------|----------|
| 2026-02-20 | T0-*, T2-1, T4-* | T0-3 STALE. T4 descriptions refined. |
| 2026-02-24 | All open tasks | T0-4 deferred. T4-2 not needed. E2E pipeline verified. |

### Deferred (Post-MVP)

PlanView content, SARF variable editing, IRR study, fine-tuning, per-statement F1 diagnostics, conversation flow versioning, LLM model selection, PDF export, pattern intelligence, Add Notes to PDP (`btcopilot/doc/plans/ADD_NOTES_TO_PDP.md`).
