# Prompt Engineering Extraction Strategy

**Purpose**: Systematic strategy for improving SARF data extraction F1 scores. Documents the process, known blockers, and best practices learned through experimentation.

**Status**: Active - update as learnings emerge.

**Last Updated**: 2026-03-04 (T7-20 flash-lite model evaluation + thinking budget discovery)

---

## Current State Summary

### F1 Baseline — Full Extraction, 2-Pass Split (as of 2026-03-04, 6 GT discussions)

**Current production** (gemini-2.5-flash, thinking=0):

| Metric | Score | Assessment |
|--------|-------|------------|
| Aggregate F1 | 0.545 | Moderate |
| People F1 | 0.920 | Strong |
| Events F1 | 0.265 | Below Stage 1 target |
| PairBonds F1 | 0.648 | Moderate |

**With thinking=1024** (recommended, pending deployment):

| Metric | 2.5-flash | flash-lite | Assessment |
|--------|-----------|------------|------------|
| Aggregate F1 | 0.609 | 0.600 | Good |
| People F1 | 0.915 | 0.911 | Strong |
| Events F1 | 0.378 | 0.368 | Stage 1+ |
| PairBonds F1 | 0.626 | 0.650 | Moderate |

Multi-run averages (2-3 runs each). 6/6 discussions, 0 API errors. Description-free event matching.

**Key insight**: thinking_budget=1024 is the single biggest lever (+43% Events F1 on 2.5-flash, +139% on flash-lite). Flash-lite matches 2.5-flash quality at ~6x lower cost. See report: `doc/induction-reports/2026-03-04_13-15-00--model-evaluation-flash-lite/`

### Previous Baselines (archived)

**Per-statement** (2026-02-14, gemini-2.5-flash, 45 GT cases): Aggregate ~0.24, People ~0.72, Events ~0.14. Superseded by full-extraction pipeline.

**Full-extraction single-prompt** (2026-03-03): Aggregate 0.595, Events 0.470, PairBonds 0.539. Superseded by 2-pass split.

**Diagnosis**: Primary remaining blockers are GT data quality and SARF accuracy (relationship F1 low). People and structural extraction are strong. Event detection has crossed the 0.5 threshold.

---

## Known Blockers (in priority order)

### 1. GT Data Quality (Critical - NEW 2026-02-14)

**Problem**: GT data has systematic quality issues that prevent fair evaluation.

**Evidence from 2026-02-14 analysis** (88 GT events total):
- **20.5% of GT events (18/88) have person=None** — these can NEVER match AI events since the prompt requires person. 16 of 60 cases with events have at least one person=None event.
- **27.3% of GT events (24/88) have placeholder descriptions** — "New Event" or empty. These fail description similarity matching.
- **100% of GT events have dateCertainty=None** — the 7-day DATE_TOLERANCE_DAYS path is never taken; all dates use the 270-day approximate tolerance.

**Fixes applied (2026-02-14)**:
- [x] Treat GT person=None as wildcard in event matching
- [x] Treat placeholder descriptions ("New Event", empty) as auto-pass
- [ ] Review and fix GT person assignments (18 events need person set)
- [ ] Review and fix GT descriptions (24 events have placeholders)
- [ ] Add dateCertainty to GT events

### 2. ~~Full-Extraction: Per-Statement Training Dominance~~ — RESOLVED (2026-03-03)

**Resolution**: 2-pass split extraction. Pass 1 and Pass 2 use independent prompts (`DATA_EXTRACTION_PASS1_PROMPT`, `DATA_EXTRACTION_PASS2_PROMPT`) that don't include per-statement training examples. This eliminates the dominance problem entirely — the 1770 lines of per-statement examples are only used by `update()` (training app).

**Original problem**: Single-prompt `extract_full()` layered ~50 lines of full-extraction context on ~1770 lines of per-statement training. The per-statement training dominated model behavior, and no amount of override framing could change it.

### 3. ~~Event Matching Brittleness~~ — RESOLVED (2026-03-03)

**Resolution**: Strategy B — removed `Event.description` as both hard gate and soft scoring signal. Events match on `kind + dateTime + person links` only. Events F1 jumped from 0.335 to 0.470 (+40%) with no extraction changes.

**Original problem**: `description` fuzzy similarity >= 0.4 was a hard gate that rejected legitimate matches due to paraphrasing variance between AI clinical summaries and GT verbatim words.

**Remaining risk**: If a person has 2+ genuinely different shift events within the 730-day date tolerance, they'll match incorrectly. Accepted as rare with current GT dataset. SARF Signature Match (Proposal A from the experiment plan) is available as a future upgrade if this becomes a problem.

### 3. High Model Stochasticity (Critical)

**Problem**: Same prompt produces different outputs across runs.

**Evidence**: Anxiety F1 varied 0.000-0.014 on identical prompts.

**Root cause**: Gemini 2.0 Flash has high variance at default temperature.

**Impact**: Cannot distinguish signal from noise during prompt optimization.

**Partial mitigation (2026-03-04)**: thinking_budget=1024 slightly reduces variance by giving the model reasoning steps, but 10-15% Events F1 variance persists across identical configs.

**Potential fixes**:
- [x] Reduce temperature — tested 0.0 vs 0.1, negligible difference (2026-03-04)
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
5. Adding missing relationship types to prompt (toward, away, defined-self, cutoff, fusion) — schema-aligned (2026-02-14)
6. Fixing F1 matching for GT person=None and placeholder descriptions (2026-02-14)
7. Scene-detail suppression with concrete negative examples in full-extraction context → Events F1 +0.033 avg (2026-03-03)
8. Soft calibration hints ("15-30 events typical") — non-destructive count guidance for full-extraction (2026-03-03)
9. Minimal intervention approach for full-extraction: quality hints layered on per-statement training, not overrides (2026-03-03)
10. 2-pass split extraction: Pass 1 (people+bonds+structural) then Pass 2 (shifts+SARF) — Aggregate +12%, Events +8%, PairBonds +54%, 100% completion (2026-03-03, T7-18)
11. Description-free event matching (Strategy B): remove Event.description from F1 matching gates — Events F1 +40% with no extraction changes (2026-03-03, T7-18)
12. thinking_budget=1024 on structured extraction: enables model reasoning about event classification. Events F1 +43% (2.5-flash) and +139% (flash-lite). Sweet spot is exactly 1024 — bell curve from 0 to 4096 tested. (2026-03-04, T7-20)
13. gemini-3.1-flash-lite-preview viability: matches 2.5-flash quality (Events 0.368 vs 0.378) at ~6x lower cost when thinking=1024 is enabled. Without thinking, flash-lite fails completely on event extraction. (2026-03-04, T7-20)

**Things that failed**:
1. Adding explicit negative examples for SARF variables (caused model to stop using them)
2. Adding percentage guidance ("only ~10-15% should have anxiety") - too constraining
3. Shortening description instruction (broke other patterns)
4. Verbose academic definitions (doubled prompt size, killed F1)
5. Divorce event extraction example (2025-12-18) - no improvement, dates block matching
6. Adding "away"/"toward" relationship kinds (2025-12-18) - no improvement, model already handles
7. Verb phrase description style guidance (2025-12-18) - no improvement, dates block matching
8. ~~thinking_budget=1024 on gemini-2.5-flash (2026-02-14) - CATASTROPHIC latency: 29+ min per case, API hangs. Thinking+structured_output incompatible.~~ **CORRECTED 2026-03-04**: Thinking+structured_output works fine with 2-pass split. The Feb 2026 failure was specific to the old single-prompt architecture (larger context + output). With the split, thinking=1024 is the #1 quality lever (+43% Events F1). See T7-20 report.
9. Encouraging more extraction ("empty arrays should be rare") (2026-02-14) - aggregate dropped, reverted
10. Temperature 0.0 vs 0.1 (2026-02-14) - negligible difference, reverted
11. DATE_TOLERANCE_DAYS 7→30 (2026-02-14) - no effect because 100% of GT has dateCertainty=None (already uses 270-day tolerance)
12. Aggressive consolidation rules in full-extraction context (2026-03-03) — kills TP proportionally to FP, model drops events randomly not intelligently
13. "IGNORE" / "DO NOT APPLY" framing to override per-statement training (2026-03-03) — destroys useful event detection capability
14. Person-centric extraction "1-3 episodes per person" (2026-03-03) — no improvement in event selection quality
15. Hard event count targets in full-extraction (2026-03-03) — model drops events randomly, not by clinical significance
16. Explicit birth event instructions at any specificity level (2026-03-03) — Gemini 2.5 Flash birth generation is non-deterministic regardless of prompt
17. Pre-transcript rule placement for full-extraction (2026-03-03) — less effective than post-transcript (recency bias matters but 1770 lines of examples still dominate)
18. Raising description similarity threshold from 0.4 to 0.5 (2026-03-03) — eliminates false matches but hurts measured F1 because false TPs were being counted
19. Hybrid per-pass model selection (flash-lite P1, 2.5-flash P2) (2026-03-04) — does NOT outperform flash-lite on both passes when thinking=1024 is enabled. The bottleneck is thinking budget, not model capability.
20. thinking_budget > 1024 on flash-lite (2026-03-04) — 2048 and 4096 both worse than 1024. Model over-thinks and second-guesses, dropping valid events.
21. Temperature 0.0 on flash-lite (2026-03-04) — negligible difference vs 0.1, confirms earlier temp=0 finding (item #10)

**Key insights**:
- The model is extremely sensitive to SARF-related prompt changes
- GT data quality is the primary measurement blocker, not prompt quality
- 45-case benchmark has ~±0.03 noise floor — cannot measure improvements smaller than this
- gemini-2.5-flash thinking mode is incompatible with structured JSON output (catastrophic latency)
- Description style mismatch (GT uses speaker verbatim words, AI uses clinical summaries) is the binding constraint on Events F1 — resolved by removing description from matching (2026-03-03)
- 1770 lines of per-statement examples dominate full-extraction model behavior — resolved by using independent split prompts (2026-03-03)
- Full-extraction requires fundamentally different strategy than per-statement: minimal hints, not overrides (2026-03-03)
- LLM non-determinism is ~10-15% for full-extraction — multi-run averaging is required for reliable signal (2026-03-03)
- Task decomposition (2-pass split) is more effective than prompt engineering on a monolithic extraction — reducing cognitive load per LLM call improves quality on every metric (2026-03-03)
- Thinking budget is a first-class quality lever, not just a speed/cost tradeoff. Without thinking, lite models skip entire extraction categories (zero structural events). With thinking=1024, lite models match full-size models on quality. (2026-03-04)
- Previous findings can become invalid as APIs evolve. The "thinking is catastrophic" finding from Feb 2026 was corrected in March 2026. Always re-test assumptions when architecture changes. (2026-03-04)
- LLM non-determinism on extraction runs 10-15% variance on Events F1 across identical configs. Multi-run averaging (3+ runs) is mandatory for reliable comparison. (2026-03-04, confirmed with 3-run data)
- "Structural events" (birth, death, married, divorced, bonded, separated, adopted, moved) vs "shift events" (kind=shift, SARF-coded) is the correct taxonomy for the two event categories in the 2-pass split. Pass 1 extracts structural events; Pass 2 extracts shift events. (2026-03-04)

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

Current state: **Stage 2 reached** (Events F1 = 0.509). Next target: SARF F1 > 0.3 (Stage 3). Symptom (0.727) and Functioning (0.627) already exceed Stage 4. Relationship (0.311) barely at Stage 3. Anxiety (0.399) at Stage 3.

---

## Evaluation Improvements to Consider

### F1 Metric Modifications

| Change | Rationale | Status |
|--------|-----------|--------|
| ~~Lower description threshold to 0.4~~ | ~~More lenient matching~~ | ✅ Superseded — description removed entirely (Strategy B) |
| ~~Semantic (embedding) matching~~ | ~~Better "same meaning" detection~~ | ✅ Superseded — description removed entirely |
| SARF Signature Match | More precise than kind+date+person | Deferred — available if false matches emerge |
| Separate detection vs accuracy | "Found event" distinct from "correct details" | Not done |

### GT Quality Improvements

| Change | Rationale | Effort |
|--------|-----------|--------|
| Assign person to 18 GT events | Remove wildcard matching dependency | Medium |
| Replace 24 placeholder descriptions | Clean data for analysis | Medium |
| Add more SARF-coded events | Increase signal density | High |
| Add more GT discussions | Reduce noise from 6-discussion benchmark | High |

---

## Next Recommended Actions

### Immediate (Highest Impact)

1. **Remove per-statement extraction path** (issue #99) — `update()`, `extract_next_statement()`, `reextract_statement()` are training-app only and no longer needed for production. Convert `import_text()` to 2-pass. Remove orphaned prompt constants (`DATA_EXTRACTION_PROMPT`, `DATA_EXTRACTION_EXAMPLES`, `DATA_EXTRACTION_CONTEXT`).

2. **Fix GT data quality** — Still the #1 measurement blocker:
   - Assign `person` to 18 GT events currently set to None
   - Replace 24 "New Event" placeholder descriptions with real descriptions
   - Add `dateCertainty` to all GT events

3. **Improve Relationship F1** (0.311) — Lowest SARF variable. Investigate whether GT relationship coding is consistent, or if the Pass 2 prompt needs relationship-specific guidance.

### Short-term

4. **Improve Anxiety F1** (0.399) — Second-lowest SARF variable. Same investigation as #3.

5. **SARF Signature Match** — If kind+date+person matching proves too loose (false matches on events with different SARF patterns for the same person near the same date), upgrade to Proposal A from the experiment plan.

### Medium-term

6. **GT expansion** — Add more discussions with all fields populated (person, description, dateCertainty, SARF variables). Current 6-discussion benchmark is small.

7. **Confidence-based testing** — Run each discussion 3-5x and report mean±std to reduce noise.

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
| [PROMPT_OPTIMIZATION.md](PROMPT_OPTIMIZATION.md) | Prompt optimization process |
| [F1_METRICS.md](F1_METRICS.md) | F1 calculation details |
| [training/prompts/induction_agent.md](../btcopilot/training/prompts/induction_agent.md) | Agent meta-prompt |
| [personal/prompts.py](../btcopilot/personal/prompts.py) | Extraction prompt defaults (empty stubs) |
| [fdserver/prompts/private_prompts.py](../../fdserver/prompts/private_prompts.py) | Real extraction prompts (PASS1/PASS2) |
| [training/f1_metrics.py](../btcopilot/training/f1_metrics.py) | F1 calculation (matching logic) |
| [training/run_extract_full_f1.py](../btcopilot/training/run_extract_full_f1.py) | Full-extraction F1 harness |
| [induction-reports/](induction-reports/) | Historical run logs |
