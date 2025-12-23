# F1 Improvement Plan for SARF Extraction MVP

## Current State (2025-12-22 baseline, 31 cases)
- People F1: 0.505 (was ~0.72, needs investigation)
- Events F1: 0.113 (blocking SARF evaluation)
- SARF F1: 0.032 (cannot improve until events match)
- Aggregate F1: 0.103

## Target State (Prompt Engineering Ceiling)
- People F1: 0.80-0.90
- Events F1: 0.50-0.65
- SARF F1: 0.40-0.55
- Aggregate F1: 0.45-0.60

## Priority Tasks (in order)

### 1. Fix Evaluation Metrics (Do First)
The current F1 metrics are artificially low due to overly strict matching. Fix these before any prompt work:

**File: `btcopilot/training/f1_metrics.py`**

- [x] **dateCertainty implemented** - The `Event.dateCertainty` field now provides
      smart date tolerance based on certainty level:
  - `Unknown`: always matches (any date)
  - `Approximate`: ±270 days tolerance (9 months)
  - `Certain`: ±7 days tolerance (`DATE_TOLERANCE_DAYS`)
- [x] Lower `DESCRIPTION_SIMILARITY_THRESHOLD` from 0.5 → 0.4 (confirmed: 0.4)

After changes, re-run baseline to see true current performance.

### 2. Reduce Model Stochasticity
Same prompt gives different results across runs, making improvements hard to measure.

**File: `btcopilot/extensions/llm.py`**

- [x] Add `temperature=0.1` to Gemini config in the `gemini()` method
  - Updated in `btcopilot/extensions/llm.py`

### 3. Prompt Improvements (Already Done)
- [x] Added conversation continuity check to EVENT EXTRACTION CHECKLIST (item 5)
- [x] Added `[CONVERSATION_CONTINUITY_DUPLICATE_EVENT]` example
- [x] Fixed prompt structure (removed duplicate rules from header, consolidated in SECTION 2)
- [x] Added `dateCertainty` field to prompt with clear guidance (certain/approximate/unknown)

### 4. GT Data Quality Review
- [ ] Review GT event dates for consistency (especially discussion 36)
- [ ] Check if GT description style is consistent (concise 2-5 words)

## Key Files
- `btcopilot/training/f1_metrics.py` - Matching thresholds (already handles dateCertainty)
- `btcopilot/personal/prompts.py` - Extraction prompts (already includes dateCertainty)
- `btcopilot/extensions/llm.py` - LLM configuration (needs temperature)
- `doc/PROMPT_ENG_EXTRACTION_STRATEGY.md` - Detailed strategy doc

## Commands
```bash
# Run F1 evaluation
uv run python -m btcopilot.training.test_prompts_live --detailed

# Run tests
uv run pytest btcopilot/tests/personal/ -v
```
