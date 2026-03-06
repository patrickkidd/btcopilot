# Extraction Comparison Page

## Problem

We need to compare definition-enhanced AI extraction against domain expert GT to evaluate whether AI-generated SARF coding (grounded in operational definitions from academic literature) is better than manually produced GT. The existing per-statement coding page and IRR view don't work for this because `extract_full()` produces a single merged PDP, not per-statement deltas.

## Proposal

A new training app page at `/training/compare/<discussion_id>` that shows a side-by-side event timeline comparison.

## Design

### Layout: Two-Column Event Timeline

```
┌─────────────────────────────────────────────────────────┐
│  Extraction Comparison: Synthetic: Sarah (ID: 36)       │
│  Source A: patrick@...  |  Source B: ai-definitions     │
├────────────────────────┬────────────────────────────────┤
│  GT (Patrick)          │  AI-Definitions                │
├────────────────────────┼────────────────────────────────┤
│  ▼ Matched Events                                      │
│                        │                                │
│  Sarah: Increased      │  Sarah: Increased anxiety      │
│  anxiety and insomnia  │  and insomnia                  │
│  S: [up]  A: [up]     │  S: [up]  A: [up]             │
│  R: -     F: -        │  R: -     F: [down] ← DIFF    │
│  2025-06-17            │  2025-06-17                    │
│                        │                                │
│  Carol: Emotional      │  Carol: Emotional collapse     │
│  collapse              │  after loss                    │
│  S: [up]  A: -        │  S: [up]  A: [up] ← DIFF     │
│  R: -     F: [down]   │  R: -     F: [down]           │
│  2018-01-01            │  2018-01-01                    │
│                        │                                │
│  ▼ Only in GT (missed by AI)                           │
│                        │                                │
│  Michael: Conflict     │  (no match)                    │
│  with Sarah            │                                │
│  R: [conflict]         │                                │
│                        │                                │
│  ▼ Only in AI (extra)                                  │
│                        │                                │
│  (no match)            │  Sarah: Social isolation       │
│                        │  S: same  A: [up]             │
│                        │  R: [distance]  F: [down]     │
└────────────────────────┴────────────────────────────────┘
```

### Key Features

1. **Event matching** — Reuse `match_events()` from `f1_metrics.py` (matches on kind + dateTime + person links). Groups events into: Matched, GT-only (missed), AI-only (extra).

2. **SARF badge styling** — Match the existing SARF editor's badge appearance (colored tags for up/down/same, relationship type badges). Reuse CSS from `sarf_editor.html`.

3. **Disagreement highlighting** — When matched events have different SARF values, highlight the differing field with a colored border/background.

4. **People F1 is done** — Skip people comparison (F1 at 0.915). Focus entirely on shift events + SARF variables.

5. **Source selector** — Dropdowns for Source A and Source B. Populate from available auditor_ids + "AI" (Statement.pdp_deltas). Default: approved GT auditor vs "ai-definitions".

### Data Flow

1. Route receives `discussion_id`
2. Build cumulative PDP for each source:
   - For auditor sources: `pdp.cumulative(discussion, last_stmt, auditor_id=X)`
   - For "AI": `pdp.cumulative(discussion, last_stmt)` or diagram PDP fallback
   - For "ai-definitions": same as auditor, `auditor_id="ai-definitions"`
3. Run `match_events()` to align events between the two sources
4. Render matched pairs, source-A-only, source-B-only sections

### Implementation

| File | Purpose |
|------|---------|
| `training/routes/compare.py` | New blueprint, route `/compare/<discussion_id>` |
| `training/templates/compare.html` | Timeline comparison template |
| Reuse from `sarf_editor.html` | SARF badge CSS, event card styling |
| Reuse from `f1_metrics.py` | `match_events()`, `match_people()` for ID mapping |

### Existing Infrastructure to Reuse

- `f1_metrics.py:match_events()` — event matching with configurable date tolerance
- `f1_metrics.py:match_people()` — person matching for ID map (needed by match_events)
- `pdp.cumulative()` — builds cumulative PDP from per-statement deltas or Feedback records
- `sarf_editor.html` CSS — badge styles for S/A/R/F values
- Feedback records with `auditor_id="ai-definitions"` — already injected by `inject_enhanced_extraction.py`

### Context: Definition-Enhanced Extraction Pipeline

The AI extraction pipeline now includes a Pass 3 that reviews shift events against condensed operational definitions from academic literature (Kerr, Bowen, Havstad). The definitions include:
- Operational definitions for all 12 SARF variables
- Key discriminators (what IS vs is NOT each variable)
- Observable speech/behavior markers for classification
- Passage IDs traceable to primary clinical sources

Changes made:
- `sarfdefinitions.py` — `all_condensed_definitions()` returns ~15.7K tokens of condensed definitions
- `pdp.py` — Pass 3 now injects definitions and corrects all SARF fields (S/A/F/R), not just R
- `prompts.py` + `fdserver/prompts/private_prompts.py` — `SARF_REVIEW_PROMPT` replaces `RELATIONSHIP_REVIEW_PROMPT`
- `inject_enhanced_extraction.py` — Script to run extraction and store as `Feedback` records with `auditor_id="ai-definitions"`

### Running the Extraction

```bash
# Inject on one discussion
GOOGLE_GEMINI_API_KEY=... uv run python -m btcopilot.training.inject_enhanced_extraction --discussion 36

# Inject on all GT discussions
GOOGLE_GEMINI_API_KEY=... uv run python -m btcopilot.training.inject_enhanced_extraction --clear

# Available GT discussions: 36, 37, 39, 48, 50, 51
```

### Goal

Compare AI extraction quality against domain expert GT. The hypothesis: operational definitions from the academic literature can produce SARF coding that is as good or better than domain expert manual entry, shifting the expert role from manual data entry to review/correction.
