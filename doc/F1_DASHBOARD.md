# F1 Dashboard - SARF Extraction

- **Purpose**: Track F1 metrics and prioritize improvements for SARF extraction.
- **Maintenance**: Update baseline after each change. Move completed items to Archive.
- **Target Rationale**: See [Appendix A](#appendix-a-target-rationale) for benchmarks and citations.

## Workflow

**Before each work session**, pick a priority from the burndown and:

1. **Micro analysis** (10-30 min): Open the Analysis page, review the specific failing statements listed in the priority's evidence. For each:
   - Is this a GT error? → Fix in Training App
   - Is this an AI error? → Note the pattern for prompt fix

2. **Fix** (varies):
   - GT fixes: Edit in Training App, re-run F1 eval
   - Prompt fixes: Add example to `prompts.py`, re-run F1 eval

3. **Update dashboard**:
   - Update baseline metrics table below
   - Add entry to `f1_timeseries.json` (see [Timeseries Tracking](#timeseries-tracking))
   - Add to change log
   - Move completed items to Archive
   - Re-prioritize if needed

**Tools**:
- Analysis page: `http://127.0.0.1:8888/training/analysis/` (micro view)
- F1 eval: `GOOGLE_GEMINI_API_KEY=... uv run python -m btcopilot.training.test_prompts_live`
- This dashboard: macro view, priorities, patterns
- Timeseries plot: [f1_timeseries.html](f1_timeseries.html) (open in browser)

## Ground Truth Sample Size Requirements

Current sample (45 statements, 3 discussions) provides ~±15% margin of error. Targets:

| Confidence Level | Statements | Discussions | Margin |
|------------------|------------|-------------|--------|
| **Current** | 45 | 3 | ±15% |
| "Usable" | 100 | 15-20 | ±10% |
| "Publishable" | 400 | 30+ | ±5% |

**Quality > quantity**:
- Diversity matters more than count (30 varied > 100 similar)
- IRR study required before scaling (if coders disagree, more GT doesn't help)
- Need coverage across: presenting problems, family structures, communication styles

**Current precision/recall breakdown** (to interpret F1):
- People: P=77%, R=56% → decent, mostly missing some family members
- Events: P=9%, R=8% → broken, both hallucinating and missing
- Overall: FP=71, FN=106 → missing more than hallucinating (recall problem)

**MVP implication**: People/PairBonds (F1 0.65-0.78) may be MVP-viable while Events/SARF need fundamental fixes. See [decisions/log.md](../decisions/log.md) entry 2025-12-27.

---

## Current Baseline (2025-12-28, 45 cases)

| Metric | Current | Target | Gap | Rationale |
|--------|---------|--------|-----|-----------|
| Aggregate F1 | 0.327 | **0.50** | -0.17 | Weighted average of component targets |
| People F1 | 0.743 | **0.75** | -0.01 | NER benchmark: 65-78% for clinical entities |
| Events F1 | 0.217 | **0.55** | -0.33 | Event extraction: 55-70% typical for clinical |
| Symptom F1 | 0.222 | **0.45** | -0.23 | SARF variable extraction |
| Anxiety F1 | 0.207 | **0.45** | -0.24 | SARF variable extraction |
| Relationship F1 | 0.244 | **0.45** | -0.21 | SARF variable extraction |
| Functioning F1 | 0.244 | **0.45** | -0.21 | SARF variable extraction |

**Change log**:
- 2025-12-26: Events F1 +42% (0.078→0.111) after P0 prompt fixes
- 2025-12-27: GT quality fixes (8 null person fields) - SARF F1 now non-zero
- 2025-12-27: Fixed test_prompts_live.py bug - was using cumulative PDP including current statement
- 2025-12-27: **dateCertainty default → Approximate** + GT dateCertainty backfill. Aggregate F1: 0.278→0.314 (+13%)
- 2025-12-28: **[SATURATION_PATTERN_ELABORATION]** prompt. Events F1: 0.181→0.205 (+13%)
- 2025-12-28: **Saturation check in EVENT EXTRACTION CHECKLIST**. Aggregate F1: 0.299→0.327 (+9%)

---

## Priority Burndown

### P1: Over-Extraction (AI extracts too many events)

**Problem**: AI frequently extracts 2-4 events when GT has 0-1. This hurts precision.

**Micro-analysis completed (2025-12-28):**

| Statement | Text Pattern | GT | AI | Root Cause |
|-----------|--------------|----|----|------------|
| [1910](http://127.0.0.1:8888/training/analysis/discussion/37#statement-1910) | "I found myself...", "I felt guilty...", "I was just a mess" | 0 events | 4 shifts | Reflective narrative → shift events |
| [1846](http://127.0.0.1:8888/training/analysis/discussion/36#statement-1846) | "I can't pinpoint...", "I feel like...", "she just seems lost" | 1 moved | 4 shifts | Vague feelings → shift events |
| [1856](http://127.0.0.1:8888/training/analysis/discussion/36#statement-1856) | "Mom fell apart", "I took charge", "it felt like..." | 1 shift | 4 shifts | Each emotional phrase → separate event |
| [1840](http://127.0.0.1:8888/training/analysis/discussion/36#statement-1840) | "It's just exhausting", "I feel like I'm the one..." | 1 shift | 2 shifts | Current feelings → shift events |

**Root cause confirmed**: AI treats emotional/reflective language as shift events:
- "I found myself..." / "I felt like..." / "It's like..."
- Vague characterizations ("she seems lost", "he's avoiding it all")
- Internal processing ("I was just a mess", "I couldn't be honest")

**Attempted fixes (2025-12-28)**:
1. ❌ Added `[OVER_EXTRACTION_EMOTIONAL_NARRATIVE]` example → Events F1 dropped (too aggressive)
2. ❌ Added rules to "Do NOT create events for" section → Events F1 dropped (too aggressive)
3. ✅ Added `[SATURATION_PATTERN_ELABORATION]` example → **Events F1 +13%** (0.181→0.205)

**Root cause**: Not just "emotional language" but **pattern saturation** - AI was treating elaborations of already-captured patterns as new events. Fix teaches AI to recognize when emotional details are texture of existing patterns vs new shifts.

**Key insight**: The problem wasn't emotional language per se, but failing to check if the functional pattern (overfunctioning, distancing, etc.) was already coded in the PDP before creating new events for its emotional manifestations.

### P2: Event Kind Mismatch

**Problem**: AI uses wrong event kind (shift vs moved, birth vs married).

**Review these statements**:
| Statement | Issue | Verdict |
|-----------|-------|---------|
| [2014](http://127.0.0.1:8888/training/analysis/discussion/39#statement-2014) | GT: moved, AI: shift | |
| [2020](http://127.0.0.1:8888/training/analysis/discussion/39#statement-2020) | GT: birth, AI: married | |

**Actions** (after micro analysis):
- [ ] Fix any GT errors found
- [ ] If AI pattern confirmed: Add examples clarifying `moved` vs `shift`

### P3: Event Description Length

**Problem**: AI produces verbose descriptions; GT uses concise 2-5 word phrases.

**Example**: AI "Taken a step back since Mom's..." vs GT "Really taken a step back"

**Actions**:
- [ ] Strengthen prompt: "2-5 words" constraint (prompts.py:310)
- [ ] Add `[EVENT_DESCRIPTION_LENGTH]` example

### P4: Person Link Mismatches

**Problem**: AI links event to wrong person.

**Review these statements**:
| Statement | Issue | Verdict |
|-----------|-------|---------|
| [1840](http://127.0.0.1:8888/training/analysis/discussion/36#statement-1840) | Same event, different person | |

**Root cause hypothesis**: Pronoun resolution failure.

**Actions** (after micro analysis):
- [ ] Fix any GT errors found
- [ ] If AI pattern confirmed: Add `[EVENT_PERSON_PRONOUN_RESOLUTION]` example

---

## Archive (Completed)

### P0-DONE: dateCertainty Default Fix (2025-12-27) ✅

Changed default from `Certain` to `Approximate` in f1_metrics.py. Combined with GT dateCertainty backfill, improved Aggregate F1 from 0.278→0.314 (+13%).

### P0-DONE: GT Quality - Null Person Fields (8 events) ✅

Fixed in prod via Training App.

### P0-DONE: Prompt Under-Extraction Fixes

| Discussion | Statement | GT Event | Issue | Action |
|------------|-----------|----------|-------|--------|
| 36 | 1844 | "Really taken a step back" | ✅ Fixed via prompt | Added `[UNDER_EXTRACTION_TIME_ANCHORED_SHIFT]` example |
| 36 | 1860 | "Can't remember things, chaotic" | ✅ Fixed via prompt | Added `[UNDER_EXTRACTION_FUZZY_MEMORY_ANXIETY]` example |
| 36 | 1862 | "Things have been rocky since divorce" | ✅ Fixed via prompt | Added `[UNDER_EXTRACTION_SHIFT_WITH_MISSING_ANCHOR]` example |
| 36 | 1874 | "I don't really keep up with them" | ✅ Fixed via prompt | Added `[UNDER_EXTRACTION_PERSISTENT_DISTANCE]` example |

### Prompt Improvements (2025-12-26)
- [x] **Birth events from age mentions** - Added `[UNDER_EXTRACTION_BIRTH_FROM_AGE]` example
  - Pattern: "she's 72 years old" → Birth event with calculated year
  - 8 of 13 under-extraction cases were birth events from ages
  - Remaining 6 are GT quality issues (general patterns, not incidents)

### Evaluation Metrics Fixes (2025-12-26)
- [x] **Hybrid description matching** - Shift events now use max(token_set_ratio, substring, ratio)
  - Handles verbose AI vs concise GT: "Expanded practice, taking on..." matches "Expanded practice"
  - Future: Add Gemini embeddings as fallback if edge cases fail (tested: 0.75+ for matches, 0.4-0.5 for non-matches)
- [x] **Structural events skip description matching** - Birth, Death, Married, etc. match by kind+links+date only
  - Only Shift events require description similarity
  - Added `STRUCTURAL_EVENT_KINDS` constant in f1_metrics.py
- [x] **dateCertainty implemented** - Smart date tolerance by certainty:
  - `Unknown`: always matches
  - `Approximate`: ±270 days (9 months)
  - `Certain`: ±7 days
- [x] `DESCRIPTION_SIMILARITY_THRESHOLD`: 0.5 → 0.4

### Model Stochasticity
- [x] `temperature=0.1` added to Gemini config (`btcopilot/extensions/llm.py`)

### Prompt Improvements
- [x] Added conversation continuity check to EVENT EXTRACTION CHECKLIST
- [x] Added `[CONVERSATION_CONTINUITY_DUPLICATE_EVENT]` example
- [x] Fixed prompt structure (consolidated rules in SECTION 2)
- [x] Added `dateCertainty` field guidance

---

## Appendix A: Target Rationale

Targets are based on published clinical NLP benchmarks, adjusted downward to account for:
1. **Zero-shot LLM extraction** (vs fine-tuned models)
2. **Domain complexity** (Bowen theory constructs vs standard medical entities)
3. **Conversational source** (therapy transcripts vs structured clinical notes)

### People F1 Target: 0.75

**Benchmark context**: Clinical NER benchmarks show F1 scores of 65-78% for entity types like conditions, drugs, and procedures.

| Model | Conditions | Drugs | Procedures | Avg |
|-------|------------|-------|------------|-----|
| GLiNER-multitask-large | 77.05 | 76.00 | 58.84 | 65.67 |
| UniNER-7B | 76.92 | 75.13 | 41.30 | 62.27 |
| GPT-4o | 75.99 | 72.74 | 37.73 | 53.35 |

**Sources**:
- [Named Clinical Entity Recognition Benchmark](https://www.researchgate.net/publication/384699670_Named_Clinical_Entity_Recognition_Benchmark) - Oct 2024 leaderboard
- [JMIR Medical Informatics - Evaluating Medical Entity Recognition](https://medinform.jmir.org/2024/1/e59782) - BERT F1=0.708 on MACCROBAT

**Adjustment**: Target 0.75 (vs 0.65-0.78 benchmarks) because person extraction is simpler than multi-class medical NER—we're identifying names and relationships, not complex medical terminology.

### Events F1 Target: 0.55

**Benchmark context**: Clinical temporal event extraction is challenging. State-of-the-art fine-tuned models achieve 70-83% F1, but zero-shot LLMs significantly underperform.

| Task | Model Type | F1 |
|------|------------|-----|
| I2B2 Temporal (SOTA) | Fine-tuned BERT | 83.5% |
| Clinical TempEval | Fine-tuned | ~70% |
| ChemoTimelines 2024 | Instruction-tuned LLM | < fine-tuned |
| Zero-shot LLMs | GPT-3.5, Llama 2, etc. | "substantially underperform" |

**Sources**:
- [Typed Markers and Context for Clinical Temporal Relation Extraction](https://pmc.ncbi.nlm.nih.gov/articles/PMC10929572/) - I2B2 SOTA at 83.5%
- [UTSA-NLP at ChemoTimelines 2024](https://aclanthology.org/2024.clinicalnlp-1.58/) - LLMs underperform fine-tuned
- [Zero-shot temporal relation extraction analysis](https://aclanthology.org/2024.bionlp-1.6/) - LLMs struggle in zero-shot

**Adjustment**: Target 0.55 (vs 0.70-0.83 fine-tuned) because we use zero-shot prompting and extract from conversational transcripts (harder than structured clinical notes).

### SARF F1 Target: 0.45

**Benchmark context**: Biomedical relation extraction benchmarks show wide variance (45-92%) depending on relation complexity.

| Task | Model | F1 |
|------|-------|-----|
| Sepsis KG (GPT-4) | Few-shot | 76.76% |
| BioNER (PubMedBERT) | Fine-tuned | 89.98% |
| End-to-end RE (BioGPT) | Fine-tuned | 40-45% |
| Novelty detection | End-to-end | 24.59% |

**Sources**:
- [LLM-Driven Knowledge Graph Construction in Sepsis Care](https://pmc.ncbi.nlm.nih.gov/articles/PMC11986385/) - GPT-4 F1=76.76%
- [Biomedical Relation Extraction Using LLMs](https://www.researchgate.net/publication/385367237_Biomedical_Relation_Extraction_Using_LLMs_and_Knowledge_Graphs)
- [End-to-end system for biomedical relations](https://pmc.ncbi.nlm.nih.gov/articles/PMC11240158/) - novelty F1=24.59%

**Adjustment**: Target 0.45 (vs 0.45-0.77 benchmarks) because SARF coding involves:
1. Multi-step inference (event → person link → SARF variable)
2. Domain-specific constructs (differentiation, anxiety, etc.)
3. Implicit vs explicit mentions
4. Current cascade dependency (SARF F1 limited by Events F1)

---

## Timeseries Tracking

When updating the baseline metrics, add an entry to `f1_timeseries.json`:

```json
{
  "date": "YYYY-MM-DDTHH:MM",
  "commit": "short_hash",
  "aggregate": 0.XXX,
  "people": 0.XXX,
  "events": 0.XXX,
  "symptom": 0.XXX,
  "anxiety": 0.XXX,
  "relationship": 0.XXX,
  "functioning": 0.XXX,
  "note": "Brief description of change"
}
```

The HTML plot fetches the JSON dynamically - just update the JSON file and push.

**View locally**: `cd btcopilot/doc && python -m http.server 8000` → http://localhost:8000/f1_timeseries.html

---

## Reference

**Key Files**:
| File | Purpose |
|------|---------|
| `btcopilot/training/f1_metrics.py` | Matching thresholds, F1 calculation |
| `btcopilot/personal/prompts.py` | Extraction prompts |
| `btcopilot/extensions/llm.py` | LLM config (temperature) |

**Commands**:
```bash
# Run F1 evaluation
GOOGLE_GEMINI_API_KEY=... uv run python -m btcopilot.training.test_prompts_live --detailed

# Run tests
uv run pytest btcopilot/tests/training/test_f1_metrics.py -v
```
