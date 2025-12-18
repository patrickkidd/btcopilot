# Prompt Engineering Extraction Strategy

**Purpose**: Systematic strategy for improving SARF data extraction F1 scores. Documents the process, known blockers, and best practices learned through experimentation.

**Status**: Active - update as learnings emerge.

**Last Updated**: 2025-12-18

---

## Current State Summary

### F1 Baseline (as of 2025-12-17)

| Metric | Score | Assessment |
|--------|-------|------------|
| Aggregate F1 | ~0.15 | Very low |
| People F1 | ~0.72 | Acceptable |
| Events F1 | ~0.13 | Very low |
| Symptom F1 | 0.00-0.03 | Near zero |
| Anxiety F1 | 0.00-0.01 | Near zero |
| Relationship F1 | 0.00-0.03 | Near zero |
| Functioning F1 | 0.00-0.01 | Near zero |

**Diagnosis**: People extraction works reasonably well. Event extraction is the primary blocker. SARF variable F1 scores are near zero because:
1. Event matching fails before SARF variables can be compared
2. Sparse GT signal (few events have SARF variables coded)
3. High model stochasticity (same prompt yields different results)

---

## Known Blockers (in priority order)

### 1. Event Matching Brittleness (Critical)

**Problem**: Event F1 uses strict matching that fails on "close but different" extractions.

**Current matching requirements** (all must pass):
- `kind` exact match
- `description` fuzzy similarity >= 0.5 (40% weight)
- `dateTime` within 7 days (20% weight)
- **All person IDs must match exactly** (person, spouse, child, relationshipTargets, relationshipTriangles)

**Cascading failure**: If person matching fails (even slightly), event matching fails, SARF variables never get compared.

**Evidence from induction reports**:
```
GT: "Trouble sleeping" (16 chars)
AI: "Having trouble sleeping and feeling really anxious" (48 chars)
Similarity: 0.477 (below 0.5 threshold) → No match → All SARF F1 = 0
```

**Potential fixes**:
- [ ] Lower `DESCRIPTION_SIMILARITY_THRESHOLD` from 0.5 to 0.4 in `f1_metrics.py`
- [ ] Use semantic similarity (embeddings) instead of fuzzy string matching
- [ ] Allow partial person ID matches with lower weight
- [ ] Separate "event detected" from "event details correct" metrics

### 2. High Model Stochasticity (Critical)

**Problem**: Same prompt produces different outputs across runs.

**Evidence**: Anxiety F1 varied 0.000-0.014 on identical prompts.

**Root cause**: Gemini 2.0 Flash has high variance at default temperature.

**Impact**: Cannot distinguish signal from noise during prompt optimization.

**Potential fixes**:
- [ ] Reduce temperature via pydantic_ai configuration
- [ ] Run multiple extractions per statement, take consensus
- [ ] Increase GT dataset size to average out variance
- [ ] Add deterministic tests that verify specific input→output pairs

### 3. Sparse GT Signal

**Problem**: Very few events have SARF variables coded in ground truth.

**Evidence from anxiety report**:
```
GT has only 11 anxiety events across 74 cases - very sparse signal
11/88 events = 12.5% have anxiety coded
```

**Impact**:
- Random chance baseline is ~0% F1 for SARF variables
- Small improvements are indistinguishable from noise
- Model learns to over-extract (47.6% vs GT's 12.5%)

**Potential fixes**:
- [ ] Collect more GT cases with SARF variables coded
- [ ] Focus on events with ANY SARF variable first, then individual variables
- [ ] Weight precision vs recall differently (prefer under-extraction)
- [ ] Create synthetic GT cases targeting specific SARF patterns

### 4. AI vs GT Description Style Mismatch

**Problem**: AI produces longer, more detailed descriptions than GT.

**GT style**: "Trouble sleeping" (concise, 2-3 words)
**AI style**: "Having trouble sleeping and feeling really anxious lately" (verbose, multiple issues)

**Impact**: Even semantically identical events fail fuzzy matching.

**Potential fixes**:
- [ ] Add explicit "SHORT description (2-5 words)" instruction (tested: caused other regressions)
- [ ] Post-process AI descriptions to extract key phrases
- [ ] Train on GT description style examples
- [ ] Use embedding similarity instead of string similarity

### 5. Combined Events Problem

**Problem**: AI combines multiple issues into single events; GT separates them.

**Example**:
- AI: 1 event with "Trouble sleeping and drinking more"
- GT: 2 events - "Trouble sleeping" and "Drinking more"

**Impact**: Combined event matches neither GT event.

**Fix applied**: Changed rule from "0-1 events per statement" to "separate events per issue". Partially helped.

### 6. Date Matching Failure (Critical - NEW as of 2025-12-18)

**Problem**: F1 metric's 7-day date tolerance fails on relative dates.

**Evidence from 2025-12-18 run**:
```
Statement 1838: "Trouble sleeping" at 100% description similarity
- GT dateTime: 2025-06-01
- AI dateTime: 2025-12-17
- Date difference: 199 days → NO MATCH (requires ≤7 days)

Statement 1856: "Fell apart when mother died" at 69% similarity
- GT dateTime: 2025-12-15
- AI dateTime: 2018-01-01 (correctly dated to when grandma died)
- Date difference: 2905 days → NO MATCH
```

**Root causes**:
1. AI interprets "six months ago" from current runtime date
2. GT uses incorrect dates (2025-12-15 for events from 2018)
3. DATE_TOLERANCE_DAYS = 7 is too strict for relative expressions

**Impact**: Even 100% description matches fail due to date mismatch. This blocks ALL Events F1 improvement.

**Required fixes (MUST be done before next induction run)**:
- [ ] Increase DATE_TOLERANCE_DAYS from 7 to 30-90 days in f1_metrics.py
- [ ] Review and correct GT event dates (especially discussion 36)
- [ ] Consider semantic date matching for relative expressions

---

## Established Best Practices

### From Prompt Optimization Literature

| Technique | Description | Applied? |
|-----------|-------------|----------|
| Few-shot examples | Concrete WRONG/RIGHT patterns | ✅ Yes |
| Incremental changes | One change per iteration | ✅ Yes |
| Revert on regression | Undo changes that hurt F1 | ✅ Yes |
| Holdout validation | Reserve 20% of GT for overfitting detection | ⚠️ Designed but not verified |
| Ablation testing | Remove prompt sections to find what matters | ❌ Not done |
| Temperature control | Reduce randomness | ❌ Not done |
| Stratified evaluation | Separate metrics by error type | ⚠️ Partial |

### From Our Experimentation

**Things that worked**:
1. Expanding SARF variable definitions with specific categories
2. Clarifying direction coding ("up" almost always, "down" only for improvement)
3. Requiring separate events per issue
4. Preserving names with titles exactly as spoken

**Things that failed**:
1. Adding explicit negative examples for SARF variables (caused model to stop using them)
2. Adding percentage guidance ("only ~10-15% should have anxiety") - too constraining
3. Shortening description instruction (broke other patterns)
4. Verbose academic definitions (doubled prompt size, killed F1)
5. Divorce event extraction example (2025-12-18) - no improvement, dates block matching
6. Adding "away"/"toward" relationship kinds (2025-12-18) - no improvement, model already handles
7. Verb phrase description style guidance (2025-12-18) - no improvement, dates block matching

**Key insight**: The model is extremely sensitive to SARF-related prompt changes. Small modifications cause the model to stop coding SARF variables entirely.

---

## Manual Troubleshooting Process

When prompt induction plateaus, follow this manual investigation process:

### Phase 1: Identify Failure Mode

```bash
# Run live extraction with detailed output
uv run python -m btcopilot.training.test_prompts_live --detailed

# For specific discussion
uv run python -m btcopilot.training.test_prompts_live --discussion <ID> --detailed
```

**Classify each failure**:
1. **Person mismatch** - AI extracted different person than GT (check name similarity)
2. **Event mismatch** - Same kind but description/date/links differ
3. **SARF mismatch** - Event matched but wrong SARF value
4. **Over-extraction** - AI created event GT didn't have
5. **Under-extraction** - GT has event AI missed

### Phase 2: Deep Dive on Event Matching

For events with low F1, manually inspect the matching logic:

```python
# In Python REPL with app context
from btcopilot.training.f1_metrics import match_events, match_people
from btcopilot.schema import from_dict, PDPDeltas, Event

# Compare specific case
ai_deltas = statement.pdp_deltas  # From Statement
gt_deltas = feedback.edited_extraction  # From Feedback

# Get people ID mapping first
people_result, id_map = match_people(ai_deltas['people'], gt_deltas['people'])
print(f"People matched: {len(people_result.matched_pairs)}")
print(f"AI unmatched: {people_result.ai_unmatched}")
print(f"GT unmatched: {people_result.gt_unmatched}")

# Then check events
events_result = match_events(ai_deltas['events'], gt_deltas['events'], id_map)
print(f"Events matched: {len(events_result.matched_pairs)}")
```

### Phase 3: Test Hypothesis Locally

Before changing prompts.py, test hypothesis with single extraction:

```bash
# Create test script
uv run python -m btcopilot.training.test_single_extraction \
    --statement-id <ID> \
    --prompt-override "your hypothesis change here"
```

### Phase 4: Targeted Prompt Edit

Based on investigation, make ONE targeted change:

1. **If description style issue**: Add example showing correct description length
2. **If SARF under-coding**: Add example showing when TO code (not when NOT to code)
3. **If person resolution**: Add example showing pronoun resolution
4. **If event granularity**: Adjust "separate events per issue" guidance

**CRITICAL**: Do NOT add negative examples for SARF variables - they cause complete suppression.

---

## Metrics-Driven Strategy

### Priority Order

Focus improvement efforts in this order:

1. **Events F1** - This is the gatekeeper. SARF F1 cannot improve until events match.
2. **People F1** - Already acceptable but affects event matching via ID resolution.
3. **Individual SARF variables** - Only after Events F1 > 0.5

### Success Thresholds

| Stage | Target | Rationale |
|-------|--------|-----------|
| Stage 1 | Events F1 > 0.3 | Events matching at basic level |
| Stage 2 | Events F1 > 0.5 | Events reliably detected |
| Stage 3 | SARF F1 > 0.3 | Variable coding working |
| Stage 4 | SARF F1 > 0.5 | Production-ready quality |

Current state: Stage 1 not yet reached.

---

## Evaluation Improvements to Consider

### F1 Metric Modifications

| Change | Rationale | Risk |
|--------|-----------|------|
| Lower description threshold to 0.4 | More lenient matching | May increase false positives |
| Partial person ID matching | Don't fail event if 1 of 5 IDs wrong | May hide real errors |
| Semantic (embedding) matching | Better "same meaning" detection | Slower, harder to debug |
| Separate detection vs accuracy | "Found event" distinct from "correct details" | More metrics to track |

### GT Quality Improvements

| Change | Rationale | Effort |
|--------|-----------|--------|
| Review GT description style | Align GT with expected AI output | Medium |
| Add more SARF-coded events | Increase signal density | High |
| Standardize GT formats | Reduce arbitrary variation | Medium |
| Add synthetic cases for edge patterns | Targeted coverage | Low |

---

## Next Recommended Actions

### Immediate (Before Next Induction Run)

1. **Lower description threshold**: Edit `btcopilot/training/f1_metrics.py`:
   ```python
   DESCRIPTION_SIMILARITY_THRESHOLD = 0.4  # was 0.5
   ```
   Re-run baseline to see impact.

2. **Reduce model temperature**: Check pydantic_ai configuration in `btcopilot/pdp.py` for temperature settings.

3. **Run ablation test**: Remove SECTION 3 examples entirely, measure F1. Determine if examples help or hurt.

### Short-term (This Week)

4. **Add event-only F1 view**: Separate "event detected at all" from "event details match".

5. **Investigate GT quality**: Manually review 10 GT cases for description style consistency.

6. **Run multiple extractions**: Extract same statement 3x, compare variance.

### Medium-term (This Month)

7. **Semantic matching prototype**: Test embedding-based event matching on subset.

8. **GT expansion**: Add 20+ cases with SARF variables coded.

9. **Prompt structure experiment**: Test prompt without SARF definitions (Events-only).

---

## Self-Updating Instructions

**When to update this document**:

1. After any prompt induction run, regardless of outcome
2. After manual troubleshooting sessions
3. When F1 calculation logic changes
4. When new blockers are discovered
5. When a technique works or fails definitively

**Update process**:

1. Add findings to "Known Blockers" if new blocker discovered
2. Move items to "Things that worked/failed" after testing
3. Update F1 baseline when sustained improvement achieved
4. Add new recommended actions based on learnings
5. Archive obsolete sections to `archive/` when no longer relevant

**Automated reminders**: The induction agent (`induction_agent.md`) should:
- Read this file before each run
- Log findings to induction reports
- Propose updates to this doc in the final report

---

## Related Files

| File | Purpose |
|------|---------|
| [PROMPT_ENGINEERING_CONTEXT.md](PROMPT_ENGINEERING_CONTEXT.md) | Lessons learned, what NOT to include |
| [PROMPT_INDUCTION_CLI.md](PROMPT_INDUCTION_CLI.md) | Automated induction process |
| [F1_METRICS.md](F1_METRICS.md) | F1 calculation details |
| [training/prompts/induction_agent.md](../btcopilot/training/prompts/induction_agent.md) | Agent meta-prompt |
| [personal/prompts.py](../btcopilot/personal/prompts.py) | Extraction prompts (edit target) |
| [training/f1_metrics.py](../btcopilot/training/f1_metrics.py) | F1 calculation (matching logic) |
| [induction-reports/](../induction-reports/) | Historical run logs |
