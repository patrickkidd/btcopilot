# F1 Improvement Plan for SARF Extraction MVP

## Current State
- People F1: ~0.72 ✓ (good enough, no more work needed)
- Events F1: ~0.13 (blocking SARF evaluation)
- SARF F1: ~0.00-0.03 (cannot improve until events match)
- Aggregate F1: ~0.15

## Target State (Prompt Engineering Ceiling)
- People F1: 0.80-0.90
- Events F1: 0.50-0.65
- SARF F1: 0.40-0.55
- Aggregate F1: 0.45-0.60

## Priority Tasks (in order)

### 1. Fix Evaluation Metrics (Do First)
The current F1 metrics are artificially low due to overly strict matching. Fix these before any prompt work:

**File: `btcopilot/training/f1_metrics.py`**

- [ ] Increase `DATE_TOLERANCE_DAYS` from 7 → 30 (or 60)
- [ ] Lower `DESCRIPTION_SIMILARITY_THRESHOLD` from 0.5 → 0.4

After changes, re-run baseline to see true current performance.

### 2. Reduce Model Stochasticity
Same prompt gives different results across runs, making improvements hard to measure.

- [ ] Check pydantic_ai configuration in `btcopilot/pdp.py` for temperature settings
- [ ] If using Gemini 2.0 Flash, reduce temperature to 0.1-0.3

### 3. Prompt Improvements (Already Done)
- [x] Added conversation continuity check to EVENT EXTRACTION CHECKLIST (item 5)
- [x] Added `[CONVERSATION_CONTINUITY_DUPLICATE_EVENT]` example
- [x] Fixed prompt structure (removed duplicate rules from header, consolidated in SECTION 2)

### 4. GT Data Quality Review
- [ ] Review GT event dates for consistency (especially discussion 36)
- [ ] Check if GT description style is consistent (concise 2-5 words)

## Key Files
- `btcopilot/training/f1_metrics.py` - Matching thresholds
- `btcopilot/personal/prompts.py` - Extraction prompts
- `btcopilot/pdp.py` - LLM configuration
- `doc/PROMPT_ENG_EXTRACTION_STRATEGY.md` - Detailed strategy doc

## Commands
```bash
# Run F1 evaluation
uv run python -m btcopilot.training.test_prompts_live --detailed

# Run tests
uv run pytest btcopilot/tests/personal/ -v
