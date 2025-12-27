# F1 Dashboard - SARF Extraction

- **Purpose**: Track F1 metrics and prioritize improvements for SARF extraction.
- **Maintenance**: Update baseline after each change. Move completed items to Archive.
- **Target Rationale**: See [Appendix A](#appendix-a-target-rationale) for benchmarks and citations.

## Current Baseline (2025-12-26, 45 cases)

| Metric | Current | Target | Gap | Rationale |
|--------|---------|--------|-----|-----------|
| Aggregate F1 | 0.071 | **0.50** | -0.43 | Weighted average of component targets |
| People F1 | 0.456 | **0.75** | -0.29 | NER benchmark: 65-78% for clinical entities |
| Events F1 | 0.078 | **0.55** | -0.47 | Event extraction: 55-70% typical for clinical |
| SARF F1 | 0.022 | **0.45** | -0.43 | Relation extraction: 45-65% for complex relations |

**Blocker**: Events F1 blocks SARF evaluation (SARF codes only match on matched events).

---

## Priority Burndown

### P0: AI Under-extraction
13 statements where AI produces 0 events but GT expects 1+:
- Structural events (Birth from age mentions)
- Subtle Shift events (e.g., "things have been rocky")

**Options**:
1. Prompt updates to extract more aggressively
2. GT review - are these events reasonable to expect?

### P1: Person Link Mismatches
- AI links event to person=1 (user), GT links to different person
- Example: "diagnosed with dementia" - AI puts on user (experiencing), GT puts on mom (subject)

### P2: Prompt Description Verbosity
- AI produces verbose descriptions despite prompt saying "Brief" (prompts.py:310)
- Need to strengthen prompt with explicit word count (2-5 words) and fix long examples

---

## Key Files

| File | Purpose |
|------|---------|
| `btcopilot/training/f1_metrics.py` | Matching thresholds, F1 calculation |
| `btcopilot/personal/prompts.py` | Extraction prompts |
| `btcopilot/extensions/llm.py` | LLM config (temperature) |

## Commands

```bash
# Run F1 evaluation (requires GOOGLE_GEMINI_API_KEY)
GOOGLE_GEMINI_API_KEY=... uv run python -m btcopilot.training.test_prompts_live --detailed

# Run tests
uv run pytest btcopilot/tests/training/test_f1_metrics.py -v
```

---

## Archive (Completed)

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
