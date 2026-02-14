# Prompt Engineering Context

**Purpose**: Authoritative record of prompt engineering decisions, experiments, and lessons learned for the SARF data extraction system. Prevents regressions by documenting what works, what doesn't, and why.

**Last Updated**: December 2024

---

## Model Selection

### Current: Gemini 2.0 Flash (extraction) / Gemini 3 Flash Preview (responses)

**Extraction**: gemini-2.0-flash (small), gemini-2.5-flash (large imports via `import_text`)
**Responses**: gemini-3-flash-preview (conversational chat responses)

**Why Gemini 2.0 Flash for extraction over newer models:**
- Prompts and few-shot examples tuned specifically for 2.0-flash behavior
- Gemini 2.5-flash and 3-flash-preview both showed F1 regression (see Feb 2026 decision log)
- 2.5-flash used only for large imports due to 64K output token limit

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
```python
data_extraction_prompt = (
    DATA_EXTRACTION_PROMPT      # 1. Extraction intent + brief overview
    + DATA_EXTRACTION_EXAMPLES  # 2. Few-shot examples EARLY
    + DATA_EXTRACTION_RULES     # 3. Detailed schema/rules
    + DATA_EXTRACTION_CONTEXT   # 4. Actual data to process
)
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

### File: `btcopilot/btcopilot/personal/prompts.py`

**Constants**:
| Constant | Purpose | Template Variables |
|----------|---------|-------------------|
| `DATA_EXTRACTION_PROMPT` | Extraction intent + data model overview | `{current_date}` |
| `DATA_EXTRACTION_EXAMPLES` | Few-shot error pattern examples | None (literal JSON) |
| `DATA_EXTRACTION_RULES` | Operational extraction guidance | None |
| `DATA_EXTRACTION_CONTEXT` | Runtime data to process | `{diagram_data}`, `{conversation_history}`, `{user_message}` |

**Why split into multiple constants**:
1. Examples contain literal JSON with curly braces - keeping them separate avoids escaping issues with `.format()`
2. Makes it clear which parts have template variables
3. Easier to maintain and test independently

### Prompt Size Guidelines

| Metric | Target | Current |
|--------|--------|---------|
| Total prompt chars | <50K | ~41K |
| Lines | <1000 | ~960 |
| Examples | 5-10 | 9 |

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

- **Test harness**: `uv run python -m btcopilot.training.run_prompts_live`
- **Ground truth**: `instance/gt_export.json` (symlinked from btcopilot-sources)
- **Metrics tracked**: Aggregate F1, People F1, Events F1, per-variable F1 (symptom, anxiety, relationship, functioning)

### Gemini Issue Detection

- **Log pattern**: `GEMINI_ARRAY_ISSUE` in application logs
- **Threshold**: If >5% of extractions show array issues, consider schema changes

### Prompt Induction Reports

- **Location**: `btcopilot/induction-reports/<timestamp>/`
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
| `btcopilot/btcopilot/personal/prompts.py` | Extraction prompts (modify with care) |
| `btcopilot/btcopilot/pdp.py` | Prompt assembly + Gemini issue instrumentation |
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
