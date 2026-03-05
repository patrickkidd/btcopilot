# Calibration System — As-Built

Two LLM-powered calibration tools help SARF coders maintain coding consistency.

## Components

### Component A: Coding Advisor (per-event)

Single-event calibration. Coder clicks "Calibrate" on a SARF event in the extraction editor. The system sends the event's coding, the cumulative PDP (all shifts coded so far in the discussion), the statement context, and the applicable SARF operational definitions to Gemini. The LLM evaluates alignment with definitions, redundancy against prior shifts, and boundary-case misclassification risks.

- **Route**: `POST /calibration/event` (generate), `GET /calibration/event` (cached)
- **UI**: Modal overlay (`calibration_modal.html`), backed by `Alpine.store('calibration')` in `discussion.js`
- **Scope**: Operates on a single event within one coder's extraction. Builds a cumulative PDP up to the target statement to detect redundancy.

### Component B: IRR Review (full-discussion)

Inter-rater reliability report. Compares cumulative PDPs from all coders who have coded the same discussion, identifies disagreements, and sends each to Gemini for analysis against operational definitions.

- **Route**: `POST /calibration/irr/<discussion_id>` (generate), `GET /calibration/irr/<discussion_id>` (cached)
- **UI**: Slide-out drawer in `irr_review.html`, backed by `Alpine.store('calibrationReport')`
- **Scope**: Operates at the cumulative PDP level — compares final-state PDPs across coders, not per-statement extractions. This means disagreements about whether to code an event at all (redundancy across statements) are captured, but per-statement extraction differences are not compared directly.

## Architecture Decisions

### Caching: Two JSON columns on Discussion

`calibration_report` (JSON) — full IRR report blob for Component B.
`calibration_advice` (JSON) — dict keyed by `"{statement_id}:{auditor_id}:{event_index}"` for Component A.

No auto-invalidation. User clicks "Re-generate" / "Re-calibrate" to overwrite. Rationale: LLM output is expensive and slow (batched calls with rate limiting). Caching avoids re-running on every page load. Manual invalidation is acceptable because calibration is a deliberate review activity, not a real-time feature.

Migration: `a2b3c4d5e6f7_add_calibration_cache.py`

### UX: Cache-first with explicit regeneration

Both components check for cached data on load. If cached data exists, it renders immediately. A "Re-generate" (Component B) or "Re-calibrate" (Component A) button triggers a fresh LLM call and overwrites the cache. This avoids the UX problem of a loading spinner every time the page opens.

### Component B: Grouped by SARF variable

Disagreements are grouped by SARF variable/concept (functioning, anxiety, symptom, conflict, distance, cutoff, overfunctioning, underfunctioning, projection, inside, outside, defined-self), not by person or statement. Rationale: the calibration goal is to align coders on how to apply each SARF construct. Grouping by variable lets reviewers focus on one construct at a time during calibration meetings. A single event-disagreement with multiple field differences (e.g., both symptom and anxiety) appears in multiple variable groups with the same LLM analysis.

### Passage ID citations as clickable links

LLM analysis text references passage IDs from the SARF operational definitions (e.g., `FE4-1`, `H6`). These are post-processed into clickable markdown links pointing to the GitHub-hosted definition files.

Pipeline:
1. HTML anchors (`<a id="FE4-1"></a>`) added to passage index tables in `doc/sarf-definitions/*.md` (12 files, ~394 anchors)
2. `sarfdefinitions.py` extracts passage IDs at import time into `PASSAGE_URLS` dict mapping ID to GitHub blob URL with fragment
3. `linkify_passages()` replaces bare passage IDs in LLM output with `[ID](url)` markdown links
4. Applied to both Component A and B responses before caching

### Rate limiting

Gemini quota: 25 requests/min/model. Component B batches LLM calls in groups of 24 with 60-second delays between batches (`batch_llm_calls()`).

## Known Gaps

- **Per-statement redundancy**: Component B compares cumulative PDPs (final state), so it catches disagreements about what shifts exist but not about which specific statement a shift was coded on. If two coders agree on the shift but coded it on different statements, that difference is invisible.
- **No auto-invalidation**: If a coder updates their extraction after a calibration report was generated, the cached report becomes stale. The user must manually re-generate.

## Key Files

| File | Role |
|------|------|
| `training/routes/calibration.py` | All calibration endpoints |
| `training/calibrationprompts.py` | System/user prompts for both components |
| `training/calibrationutils.py` | PDP comparison, disagreement prioritization, statement tracing |
| `training/sarfdefinitions.py` | Definition loading, `PASSAGE_URLS`, `linkify_passages()` |
| `training/templates/components/calibration_modal.html` | Component A modal |
| `training/templates/training/irr_review.html` | Component B drawer (in IRR review page) |
| `training/static/js/discussion.js` | Alpine stores for both components |
| `personal/models/discussion.py` | `calibration_report`, `calibration_advice` columns |
| `doc/sarf-definitions/*.md` | Operational definitions with passage ID anchors |
