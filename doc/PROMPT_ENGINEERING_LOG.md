# Prompt Engineering Context

**Purpose**: Authoritative record of prompt engineering decisions, experiments, and lessons learned for the SARF data extraction system. Prevents regressions by documenting what works, what doesn't, and why.

**Last Updated**: 2026-03-04 (T7-20 flash-lite + thinking budget)

---

## Model Selection

### Current: Gemini 2.5 Flash (extraction) / Gemini 3 Flash Preview (responses)

**Extraction**: gemini-2.5-flash (production), gemini-3.1-flash-lite-preview (validated alternative — see T7-20)
**Responses**: gemini-3-flash-preview (conversational chat responses)
**Thinking**: `thinking_budget=1024` (CRITICAL — see T7-20 findings below)

**Why Gemini 2.5 Flash for extraction:**
- gemini-2.0-flash deprecated March 31, 2026 and showing server-side drift
- Aggregate F1 within 3% of 2.0-flash, better SARF variable scores
- 64K output token limit supports large imports

**Flash-lite alternative (validated 2026-03-04):**
- gemini-3.1-flash-lite-preview matches 2.5-flash quality when thinking=1024 (Events F1: 0.368 vs 0.378)
- ~6x lower cost ($0.25/1M input, $1.50/1M output)
- Zero API 500 errors with 2-pass split architecture
- Risk: preview model, may change without notice
- Recommended for cost optimization after thinking_budget=1024 is deployed

**Why Gemini 2.0 Flash over GPT-4o-mini:**
- Larger context window (1M tokens vs 128K)
- Lower cost per token
- Native structured JSON output
- Better performance on classification tasks in our testing

**Model names configurable** via `LLM.extractionModel`, `LLM.extractionModelLarge`, `LLM.responseModel` class attributes. CLI override: `--model` on `run_prompts_live.py`.

---

## Known Gemini 2.0 Flash Issues

### 1. Value Repetition in Nested Arrays

**Issue**: Gemini may repeat values indefinitely until token limit when processing nested arrays of objects.

**Affected fields**:
- `Event.relationshipTargets: list[int]`
- `Event.relationshipTriangles: list[int]`

**Mitigation**: Runtime instrumentation in `btcopilot/pdp.py` logs `GEMINI_ARRAY_ISSUE` warnings when duplicate values detected. Monitor logs - if frequent (>5% of extractions), consider schema flattening.

### 2. Missing Expected Fields

**Issue**: Gemini may omit expected fields from output, especially with complex nested structures.

**Mitigation**: All required fields are non-Optional in dataclass schema. pydantic_ai handles this automatically.

### 3. Prompt Order Sensitivity

**Finding**: Gemini documentation suggests few-shot examples early in prompts improve quality.

**Current assembly order** (`btcopilot/pdp.py`):

Per-statement (training app only):
```python
data_extraction_prompt = (
    DATA_EXTRACTION_PROMPT      # 1. Extraction intent + brief overview
    + DATA_EXTRACTION_EXAMPLES  # 2. Few-shot examples EARLY
    + DATA_EXTRACTION_RULES     # 3. Detailed schema/rules
    + DATA_EXTRACTION_CONTEXT   # 4. Actual data to process
)
```

Full extraction (production, 2-pass):
```python
# Pass 1: People + PairBonds + Structural Events
prompt1 = DATA_EXTRACTION_PASS1_PROMPT + DATA_EXTRACTION_PASS1_CONTEXT
# Pass 2: Shift Events + SARF (given Pass 1 output)
prompt2 = DATA_EXTRACTION_PASS2_PROMPT + DATA_EXTRACTION_PASS2_CONTEXT
```

---

## Critical Lessons Learned

### 1. Prompt Size Matters - Less is More

**Experiment (Dec 2024)**: Added exhaustive SARF definitions from literature review to extraction prompt.

**Result**: F1 scores degraded significantly.

**Analysis**: Prompt doubled in size (37K → 74K chars). The model was overwhelmed with too much definitional context and lost focus on the extraction task.

**Fix**: Removed verbose SARF definitions, restored concise operational definitions. Exhaustive definitions preserved in `btcopilot/doc/SARF_EXTRACTION_REFERENCE.md` for human reference only.

**Lesson**:
- Extraction prompts need concise, actionable guidance - not academic definitions
- More context ≠ better extraction
- Keep prompts focused on the task, not the theory

### 2. Dataclass Constraint (Cannot Use Pydantic Models)

**Constraint**: Schema must use Python `dataclasses`, not Pydantic models.

**Reason**: Dataclasses are required for embedding in Pro and Personal desktop apps (PyQt). Pydantic models have dependencies that don't work in the embedded environment.

**Implication**: Cannot use Pydantic's `Field(description="...")` to add descriptions to the JSON schema. All semantic guidance must be in prompt text instead.

### 3. Few-Shot Examples Are Critical

**Finding**: Gemini responds well to concrete examples of correct vs incorrect output.

**Current approach**: `DATA_EXTRACTION_EXAMPLES` contains labeled error patterns:
- `[OVER_EXTRACTION_GENERAL_CHARACTERIZATION]` - Don't create events for general feelings
- `[UNDER_EXTRACTION_BIRTH_EVENT]` - Always create birth events when birth dates mentioned
- `[UNDER_EXTRACTION_PEOPLE_INDIRECT_MENTION]` - Extract people mentioned indirectly
- `[RELATIONSHIP_TARGETS_REQUIRED]` - Always populate relationshipTargets

**Lesson**: Each common error pattern should have a labeled example in the prompt.

### 4. Extraction Intent Must Be Explicit

**Finding**: Starting with clear extraction task description improves quality.

**Current approach**: `DATA_EXTRACTION_PROMPT` begins with:
```
**Extract the following information from the user statement:**
1. **NEW people** mentioned for the first time
2. **NEW events** - specific incidents at a point in time
3. **UPDATES** to existing people
4. **DELETIONS** when user corrects previous errors
```

---

## Prompt Architecture

### File: `btcopilot/btcopilot/personal/prompts.py` (defaults) / `fdserver/prompts/private_prompts.py` (overrides)

**Per-statement constants** (training app only):
| Constant | Purpose | Template Variables |
|----------|---------|-------------------|
| `DATA_EXTRACTION_PROMPT` | Extraction intent + data model overview | `{current_date}` |
| `DATA_EXTRACTION_EXAMPLES` | Few-shot error pattern examples | None (literal JSON) |
| `DATA_EXTRACTION_RULES` | Operational extraction guidance | None |
| `DATA_EXTRACTION_CONTEXT` | Runtime data to process | `{diagram_data}`, `{conversation_history}`, `{user_message}` |

**Full-extraction constants** (production, 2-pass):
| Constant | Purpose | Template Variables |
|----------|---------|-------------------|
| `DATA_EXTRACTION_PASS1_PROMPT` | Pass 1: People + PairBonds + structural events | `{current_date}` |
| `DATA_EXTRACTION_PASS1_CONTEXT` | Pass 1 runtime data | `{diagram_data}`, `{conversation_history}` |
| `DATA_EXTRACTION_PASS2_PROMPT` | Pass 2: Shift events + SARF coding | `{current_date}` |
| `DATA_EXTRACTION_PASS2_CONTEXT` | Pass 2 runtime data | `{pass1_data}`, `{conversation_history}` |

**Why split into multiple constants**:
1. Examples contain literal JSON with curly braces - keeping them separate avoids escaping issues with `.format()`
2. Makes it clear which parts have template variables
3. Easier to maintain and test independently

### Prompt Size Guidelines

| Metric | Target | Current |
|--------|--------|---------|
| Per-statement prompt chars | <50K | ~41K |
| Per-statement lines | <1000 | ~960 |
| Per-statement examples | 5-10 | 9 |
| Pass 1 prompt (full) | — | ~150 lines |
| Pass 2 prompt (full) | — | ~225 lines |

---

## What NOT to Include in Extraction Prompts

Based on failed experiments:

1. **Academic definitions** - The "What X IS" / "What X is NOT" discriminators from literature review. Too verbose, confused the model.

2. **Observable marker tables** - Long tables of indicators. Model doesn't need this level of detail for extraction.

3. **Theoretical background** - Why constructs exist, how they relate to each other. Irrelevant for extraction task.

4. **All possible enum values** - Only document values that are commonly confused or have special rules.

**Rule**: If it reads like a textbook, it doesn't belong in an extraction prompt.

---

## What TO Include in Extraction Prompts

1. **Concise field definitions** - One-liner descriptions of what each field means operationally.

2. **Critical rules** - Things the model commonly gets wrong (e.g., "relationshipTargets is REQUIRED").

3. **Labeled examples** - Concrete wrong/right output pairs for common error patterns.

4. **Extraction intent** - What to extract, what not to extract.

5. **ID assignment rules** - Negative IDs for new items, how to avoid collisions.

---

## Monitoring & Metrics

### F1 Score Tracking

- **Full-extraction harness**: `uv run python -m btcopilot.training.run_extract_full_f1` (production 2-pass, 6 GT discussions)
- **Per-statement harness**: `uv run python -m btcopilot.training.run_prompts_live` (training app, 45 GT cases)
- **Ground truth**: `instance/gt_export.json` (symlinked from btcopilot-sources)
- **Metrics tracked**: Aggregate F1, People F1, Events F1, PairBonds F1, per-variable F1 (symptom, anxiety, relationship, functioning)

### Gemini Issue Detection

- **Log pattern**: `GEMINI_ARRAY_ISSUE` in application logs
- **Threshold**: If >5% of extractions show array issues, consider schema changes

### Prompt Induction Reports

- **Location**: `doc/induction-reports/<timestamp>/`
- **Contains**: Iteration logs, F1 deltas, final report

---

## Future Improvements (Deferred)

See `btcopilot/doc/TODO_GEMINI_SCHEMA.md` for:

1. **Convert to Pydantic with Field descriptions** - Blocked by PyQt embedding constraint
2. **Flatten triangle arrays** - Deferred pending evidence of issues
3. **TypeAdapter for enhanced JSON schema** - Not implemented, relying on pydantic_ai defaults

---

## Related Files

| File | Purpose |
|------|---------|
| `btcopilot/btcopilot/personal/prompts.py` | Extraction prompt defaults (empty stubs for private prompts) |
| `fdserver/prompts/private_prompts.py` | Real extraction prompts (PASS1/PASS2 + per-statement) |
| `btcopilot/btcopilot/pdp.py` | Prompt assembly + extraction pipeline (2-pass + per-statement) |
| `btcopilot/btcopilot/schema.py` | Dataclass definitions |
| `btcopilot/doc/TODO_GEMINI_SCHEMA.md` | Deferred Gemini optimizations |
| `btcopilot/doc/SARF_EXTRACTION_REFERENCE.md` | Exhaustive SARF definitions (reference only) |
| `btcopilot/doc/sarf-definitions/` | Literature review source material |
| `btcopilot/btcopilot/training/prompts/induction_agent.md` | Prompt induction meta-prompt |

---

## Decision Log

### Dec 2024: Remove exhaustive SARF definitions from prompt

**Context**: Commit `f6a7ee8` added comprehensive SARF definitions from literature review, doubling prompt size.

**Outcome**: F1 scores degraded significantly.

**Decision**: Reverted to concise operational definitions. Preserved exhaustive definitions in separate reference file.

**Lesson**: Extraction prompts need focused, actionable guidance - not academic background.

### Dec 2024: Gemini 2.0 Flash prompt ordering

**Context**: Gemini docs suggest few-shot examples early improve quality.

**Decision**: Reordered prompt assembly: PROMPT → EXAMPLES → RULES → CONTEXT

**Status**: Active, monitoring F1 impact.

### Mar 2026: Full-extraction prompt optimization (9 iterations)

**Context**: Manual session optimizing `DATA_FULL_EXTRACTION_CONTEXT` in `fdserver/prompts/private_prompts.py` for the `extract_full()` pipeline. Tested on 6 GT discussions (36/37/39/48/50/51) using gemini-2.5-flash.

**Baseline**: Events F1 = 0.302 (avg across 6 discussions).

**Results**: 9 iterations, 1 kept (V9), 7 reverted, 1 superseded. Final Events F1 = 0.335 avg (3 runs), best single run 0.367.

**What worked (V9)**: Minimal intervention — quality hints layered on original "extract everything" prompt:
1. Scene-detail suppression with concrete examples ("slammed door", "made a drink" = not clinical events)
2. Birth event reminder with age calculation formula
3. Relationship type disambiguation (projection vs overfunctioning, inside vs conflict)
4. Deduplication guidance
5. Soft calibration ("15-30 events typical")

**What failed (V1-V7)**:
- Aggressive consolidation rules → model ignored them or killed TP proportionally to FP
- "IGNORE" / "DO NOT APPLY" framing → destroyed useful per-statement event detection
- "Follow BUT override" framing → model reverted to per-statement behavior (76 events)
- Person-centric extraction → no improvement in event selection quality
- Hard count targets → model drops events randomly, not by significance
- Pre-transcript rule placement → less effective than post-transcript

**Key lesson**: The 1770 lines of per-statement training examples dominate model behavior. Full-extraction context (~50 lines) cannot override this. The correct strategy is minimal quality hints layered on top of per-statement training, not overrides or rewrites.

**Additional finding**: Description style mismatch (GT verbatim words vs AI clinical summaries) is the binding constraint on Events F1. Any consolidation that abstracts descriptions hurts matching. Raising similarity threshold from 0.4 to 0.5 is theoretically correct but hurts measured F1.

**Report**: `doc/induction-reports/2026-03-03_08-20-00--full-extraction/`

### Dec 2024: Add Gemini array issue instrumentation

**Context**: Known Gemini 2.0 Flash issue with nested arrays causing value repetition.

**Decision**: Added runtime detection in `pdp.py` to log `GEMINI_ARRAY_ISSUE` warnings.

**Status**: Active, monitoring frequency.

### Feb 2026: Gemini 3 Flash Preview extraction evaluation

**Context**: Evaluated switching extraction from gemini-2.0-flash/2.5-flash to gemini-3-flash-preview for potential quality improvements. Also made model names configurable via `LLM` class attributes and added `--model` CLI arg to `run_prompts_live.py` for A/B testing.

**Results** (45 GT cases):

| Metric | gemini-2.0-flash (baseline) | gemini-2.5-flash | gemini-3-flash-preview |
|--------|----------------------------|------------------|------------------------|
| Aggregate F1 | **0.327** | 0.241 (-26%) | 0.188 (-43%) |
| People F1 | **0.743** | 0.701 | 0.582 |
| Events F1 | **0.217** | 0.134 | 0.101 |
| Symptom F1 | 0.222 | 0.111 | **0.200** |
| Anxiety F1 | 0.207 | 0.111 | **0.200** |
| Relationship F1 | 0.244 | 0.133 | **0.222** |
| Functioning F1 | 0.244 | 0.133 | **0.200** |

**Decision**: Keep gemini-2.0-flash for extraction (small), gemini-2.5-flash for large imports. Use gemini-3-flash-preview only for conversational responses.

**Rationale**: Each successive model generation performed worse on aggregate extraction despite being "better" overall. Prompts and few-shot examples were tuned for gemini-2.0-flash behavior. Newer models respond differently to the same prompt structure. SARF variables showed slight improvement on 3-flash but not enough to offset the people/events regression.

**Lesson**: Model upgrades don't automatically improve extraction when prompts were tuned for a specific model. Moving extraction to a newer model requires prompt re-tuning via the induction workflow.

### Feb 2026: gemini-2.0-flash server-side regression and model migration

**Context**: Aggregate F1 dropped from 0.327 to ~0.257 with no code changes. Investigation confirmed: no GT data changes, no prompt changes, pinning `gemini-2.0-flash-001` produced identical results. Conclusion: server-side model behavior drift, likely related to 2.0-flash deprecation (March 31, 2026).

**Updated results** (45 GT cases, Feb 14 2026):

| Metric | gemini-2.0-flash | gemini-2.5-flash | gemini-3-flash-preview |
|--------|-----------------|------------------|------------------------|
| Aggregate F1 | **0.257** | 0.249 | 0.180 |
| People F1 | **0.718** | 0.718 | 0.582 |
| Events F1 | **0.179** | 0.154 | 0.081 |
| Symptom F1 | 0.200 | **0.205** | 0.178 |
| Anxiety F1 | 0.200 | **0.205** | 0.178 |
| Relationship F1 | 0.233 | **0.250** | 0.200 |
| Functioning F1 | 0.222 | **0.227** | 0.178 |

**Decision**: Switch all extraction to gemini-2.5-flash. The 3% aggregate gap vs 2.0-flash is within noise, SARF variable scores are better, and 2.0-flash is being deprecated.

**Config notes**: `thinking_config=ThinkingConfig(thinking_budget=1024)` enables thinking for quality (see T7-20 decision below). `max_output_tokens=65536` is within 2.5-flash limits.

### Feb 2026: Multi-turn prompt format evaluation

**Context**: Tested converting flat prompt (conversation history concatenated into system prompt) to Gemini's native multi-turn content structure, where prior conversation turns are passed as structured `(role, text)` tuples.

**Results** (gemini-2.5-flash, 45 GT cases):

| Metric | Flat prompt | Multi-turn | Delta |
|--------|------------|------------|-------|
| Aggregate F1 | **0.249** | 0.198 | -20% |
| People F1 | **0.718** | 0.680 | -5% |
| Events F1 | **0.154** | 0.133 | -14% |

**Decision**: Keep flat prompt format. Multi-turn causes 20% aggregate regression, more ID collision warnings, and worse people/events extraction. The model loses context about existing diagram_data when conversation history is separated from extraction instructions.

**Lesson**: Structured multi-turn is not automatically better for extraction tasks. The flat prompt keeps all context (instructions, examples, existing data, conversation, new statement) together, which helps the model track IDs and avoid re-extraction.

### Mar 2026: 2-pass split extraction (T7-18)

**Context**: Single-prompt `extract_full()` struggled with Events F1 (~0.47 with description-free matching). Hypothesis: splitting extraction into two focused passes would improve quality by reducing cognitive load per LLM call.

**Architecture**:
- **Pass 1**: Extract people, PairBonds, and structural events (birth, death, married, etc.) from full transcript
- **Pass 2**: Given Pass 1 output, extract shift events with SARF variable coding

Both passes route through `_extract_and_validate()` for retry/validation. Pass 2 receives `base_pdp=pass1_pdp` so validation runs against Pass 1's people/events.

**Results** (gemini-2.5-flash, 6 GT discussions, avg 2 runs):

| Metric | Baseline (single-prompt) | Split (2-pass) | Delta |
|--------|-------------------------|----------------|-------|
| Aggregate F1 | 0.595 | **0.669** | +12% |
| People F1 | 0.901 | 0.909 | +1% |
| Events F1 | 0.470 | **0.509** | +8% |
| PairBonds F1 | 0.539 | **0.832** | +54% |
| Completion | 4/6 (67%) | **6/6 (100%)** | fixed |

**Decision**: Replaced single-prompt `extract_full()` with 2-pass. Removed `DATA_FULL_EXTRACTION_CONTEXT`. The old single-prompt path no longer exists.

**Key observations**:
- PairBonds F1 improved dramatically (+54%) — Pass 1's focused scope catches bonds that were missed in the single all-at-once prompt
- 100% discussion completion vs 67% — smaller per-pass output avoids token limit failures
- Per-statement prompt constants (`DATA_EXTRACTION_PROMPT`, `DATA_EXTRACTION_EXAMPLES`, etc.) are NOT used by `extract_full()` — the split prompts are independent

**Lesson**: Task decomposition works. Splitting a complex extraction into two focused passes reduces cognitive load and improves quality on every metric. The key insight from the earlier 9-iteration experiment ("per-statement training dominates full-extraction context") motivated this split — instead of fighting the single-prompt format, we redesigned the pipeline.

### Mar 2026: thinking_budget=1024 + flash-lite model evaluation (T7-20)

**Context**: T7-20 (issue #59) was blocked by HTTP 500 errors from gemini-3.1-flash-lite-preview. After T7-18 split extraction landed, re-evaluated flash-lite viability. Discovered thinking_budget=0 was a critical quality bottleneck for both models.

**Experiments**: 14 runs across 12 configurations testing model (2.5-flash vs flash-lite), thinking budget (0/512/1024/2048/4096), temperature (0.0/0.1), and hybrid per-pass model selection. Multi-run averaging on key configs.

**Results** (multi-run averages, 6 GT discussions):

| Config | Events F1 | Aggregate F1 | Time | Cost |
|--------|-----------|-------------|------|------|
| 2.5-flash think=0 (was prod) | 0.265 | 0.545 | 62s | 1x |
| 2.5-flash think=1024 | **0.378** | **0.609** | 51s | 1x |
| flash-lite think=0 | 0.154 | 0.589 | 101s | 0.17x |
| flash-lite think=1024 | **0.368** | **0.600** | 50s | 0.17x |

**Decision**: Deploy thinking_budget=1024 immediately (one-line change). Switch to flash-lite when ready to optimize cost.

**CORRECTION**: Previous finding (Feb 2026) that "thinking+structured_output is catastrophic" is no longer true with the 2-pass split architecture. All 14 runs used thinking=1024 with structured JSON output — zero hangs, ~8s per pass.

**Thinking budget sweet spot** (flash-lite, Events F1): 0→0.154, 512→0.295, **1024→0.368**, 2048→0.298, 4096→0.355. Clear bell curve.

**What failed**: Hybrid models (flash-lite P1, 2.5-flash P2) don't beat homogeneous flash-lite+think. Temperature 0.0 vs 0.1 is noise. Thinking > 1024 causes over-reasoning.

**Report**: `doc/induction-reports/2026-03-04_13-15-00--model-evaluation-flash-lite/`

### Mar 2026: Description-free event matching (Strategy B)

**Context**: Debug analysis of FP events in split extraction revealed many were semantically valid extractions that GT describes differently. `Event.description` is free-text prose — it varies widely between AI and human annotators. Fuzzy string matching at 0.4 threshold was a hard gate rejecting legitimate matches.

**Change**: Removed `description` as both hard gate and soft scoring signal from `match_events()` in `f1_metrics.py`. Events now match on `kind + dateTime + person links` only. Weighted score simplified to `date_sim`.

**Results** (same extraction output, different matching):

| Metric | With description matching | Without (Strategy B) | Delta |
|--------|--------------------------|---------------------|-------|
| Events F1 | 0.335 | **0.470** | +40% |

**Decision**: Adopted. Description matching was measuring "do AI and GT use similar words" not "did AI find the right event."

**Risk**: If a person has 2+ genuinely different shift events within the 730-day date tolerance, they'll match incorrectly. Accepted as rare in practice with current GT dataset.

**Alternatives considered but deferred**:
- **SARF Signature Match** — match on SARF variable agreement instead of description. More precise than kind+date+person but adds complexity and creates circular dependency (SARF accuracy used for both matching and scoring).
- **SARF + Description hybrid** — demote description to low-weight tiebreaker. Most complex, still affected by paraphrasing variance.
