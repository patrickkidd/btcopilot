# MVP Dashboard

## How to Use This Document

Primary development punchlist. Goals → open tasks → reference material.

**Task workflow:** Pick the next open task under the highest-priority goal. Mark done when verified.

**Legend:** CC = Claude Code. CC+H = CC implements, human reviews. H = Human only.

---

## Goal 1: Single-Prompt Extraction E2E

Full conversation → single LLM call → complete PDP → accept all → view diagram+timeline.

**Status: Backend + UI implemented.** Single-prompt extraction (`pdp.extract_full()`) and extract endpoint live. Chat is chat-only. Personal app has extract button + PDP "Refresh" button. PDP cleared before each re-extraction for idempotency. Need to validate on fresh GT and prompt-tune.

### Open Tasks

| # | Task | Auto | Effort | Notes |
|---|------|------|--------|-------|
| T7-5 | Code GT for fresh discussions | H | ~3 hr | Patrick codes People/Events/PairBonds in SARF editor. ~60 min each. Synthetic discussions already generated in prod. |
| T7-7 | Validate single-prompt F1 on fresh GT | CC | ~30 min | Run `calculate_cumulative_f1()` on T7-5 discussions. Target: People > 0.7, Events > 0.3. |
| T7-8 | Prompt-tune on single-prompt path | CC+H | ~2 hr | Iterate on `fdserver/prompts/private_prompts.py` using fresh GT from T7-5. Stable surface — one call, low variance. |
| T7-9 | Validate idempotent re-extraction (no duplication after accept) | CC | ~1 hr | Chat → extract → accept all → extract again → verify no duplicate people/events vs committed items. Tests LLM-based dedup in `DATA_FULL_EXTRACTION_CONTEXT`. |
| T7-10 | Fix birth event self-reference bug | CC+H | ~2 hr | Birth events set person=child (person births themselves). Should set person=parent, child=born person, create parent PairBonds, infer sibling relationships from existing data. Prompt rules, examples, and validation all need updating. Needs design discussion first. |
| T7-11 | Fix extraction dedup against committed items | CC+H | ~2 hr | `extract_full` re-extracts people/events already committed in `diagram_data`. LLM prompt says "avoid duplicates with committed items" but isn't working. May need rules-based post-filter in `_extract_and_validate` or `apply_deltas` to strip entries matching committed IDs/names, not just prompt reliance. |
| T5-1 | Fix 18 GT events with person=None | H | ~3 hr | SARF editor. Existing disc 48 GT cleanup. |
| T5-2 | Fix 24 GT events with placeholder descriptions | H | ~4 hr | Read transcripts, write correct descriptions. |

### Done

T0-1, T0-2, T0-3, T0-5 (crash blockers), T1-1 through T1-5 (extraction quality), T4-1 through T4-5 (synthetic pipeline), T5-4 through T5-6 (F1 infrastructure), T6-2 (cumulative F1 baseline established 2026-02-24), T7-1 (`extract_full()` implemented), T7-2 (extract endpoint), T7-3 (chat-only, extraction removed), T7-4 (extract button + PDP Refresh button in Personal app).

---

## Goal 2: Human Beta

Hand Personal app to human → chat → tap extract button → accept PDP → view diagram+timeline with clusters.

**Status: Blocked on Goal 1 validation.** Chat, PDP drawer, timeline, extract button all functional. Needs GT validation (T7-5/T7-7) and prompt tuning (T7-8) before beta handoff.

### Open Tasks

| # | Task | Auto | Effort | Notes |
|---|------|------|--------|-------|
| T3-7 | Click event in timeline → highlight people in diagram | CC+H | ~3 hr | Signal plumbing between LearnView and scene. [Analysis](doc/analyses/2026-02-20_personal_app_beta_readiness.md) |
| T8-1 | Beta test with 1 human user | H | ~2 hr | Patrick or trusted tester runs full flow: chat → build diagram → review → accept. Notes friction points. |

### Done

T3-1 through T3-6 (cluster overlap, selection, zoom, SARF format, Client/Coach labels, scroll-to-bottom).

---

## Goal 3: Pro App Viewing

Open Personal-app-generated diagrams in the Pro app with correct layout.

**Status: Blocked on Goal 2.** Avoid risky Pro app changes until Goals 1+2 validated.

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
| Single-prompt hits context limit on long conversations | Extraction fails or truncates | gemini-2.5-flash has 1M token context; typical discussion is ~30K chars. Monitor. |
| Events F1 plateaus below 0.4 | Users see wrong events | Prompt-tune on stable single-prompt surface (T7-8). Fallback: hide events, show People/PairBonds only. |
| GT coding bottleneck (Patrick only) | Limits measurement iterations | ~60 min/discussion is fast enough for 3-5 GT cases needed for MVP. |
| Auto-arrange is 2-3 weeks | Delays Goal 3 | Consider simpler generational Y-alignment only. |

---

## Metrics

| Metric | Last Measured | Target | Notes |
|--------|-------------|--------|-------|
| People F1 (cumulative) | 0.72 (Feb 2026, single-prompt, disc 48) | > 0.7 | At target. Validate on fresh GT. |
| Event F1 (cumulative) | 0.29 (Feb 2026, single-prompt, disc 48) | > 0.4 | Below target. Prompt tuning on T7-8. |
| PairBond F1 (cumulative) | 0.33 (Feb 2026, single-prompt, disc 48) | > 0.5 | Below target. |
| GT coded discussions | 4 (disc 36/37/39/48) | 5-8 for MVP | T7-5 adds fresh GT coding. |
| E2E synthetic | Verified 2026-02-24 | Functional | test_e2e_synthetic.py |

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
| Single-prompt extraction | `btcopilot/pdp.py` (`extract_full()`) |
| Extract endpoint | `btcopilot/personal/routes/discussions.py` (`POST /extract`) |
| PDP validation | `btcopilot/pdp.py` (`validate_pdp_deltas()`) |
| Delta acceptance | `btcopilot/schema.py` (`commit_pdp_items()`) |
| Chat (chat-only) | `btcopilot/personal/chat.py` (`ask()`) |
| Extraction prompts | `btcopilot/personal/prompts.py` (defaults), `fdserver/prompts/` (production) |
| F1 metrics | `btcopilot/training/f1_metrics.py` |
| Synthetic generation | `btcopilot/tests/personal/synthetic.py` |
| E2E pipeline test | `btcopilot/tests/personal/test_e2e_synthetic.py` |
| Personal app QML | `familydiagram/pkdiagram/resources/qml/Personal/` |
| Decision log | `btcopilot/decisions/log.md` |
| Hand-written notes | [TODO.md](../../TODO.md) |

### Verification Log

| Date | Checked | Findings |
|------|---------|----------|
| 2026-02-20 | T0-*, T2-1, T4-* | T0-3 STALE. T4 descriptions refined. |
| 2026-02-24 | All open tasks | T0-4 deferred. T4-2 not needed. E2E pipeline verified. |
| 2026-02-24 | Architecture pivot | Single-prompt extraction proven. Dashboard rewritten. See decision log 2026-02-24. |
| 2026-02-26 | T7-1 through T7-4 | Implemented and moved to Done. Extract button + PDP Refresh in Personal app. Chat is chat-only. PDP cleared before re-extraction. All architecture docs updated. |

### Deferred (Post-MVP)

PlanView content, SARF variable editing, IRR study (Guillermo/Kathy), fine-tuning, per-statement F1 diagnostics, conversation flow versioning, LLM model selection, PDF export, pattern intelligence, Add Notes to PDP (`btcopilot/doc/plans/ADD_NOTES_TO_PDP.md`), per-statement delta extraction for training app.
