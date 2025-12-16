# Gemini 2.0 Flash Schema Optimization

**Status**: Research complete, implementation deferred
**Priority**: Medium - address if F1 scores plateau or Gemini array issues observed
**Related**: Prompt induction workflow, `btcopilot/btcopilot/schema.py`

---

## Problem Statement

The data extraction uses Gemini 2.0 Flash with structured JSON output via pydantic_ai. Gemini 2.0 Flash has documented issues with complex nested schemas that may affect extraction quality.

**Current architecture constraints:**
- Schema defined as Python `dataclasses` (not Pydantic models)
- Dataclasses required for embedding in Pro and Personal desktop apps (PyQt)
- Cannot use Pydantic's `Field()` with descriptions in the schema itself

---

## Known Gemini 2.0 Flash Issues

### 1. Value Repetition in Nested Arrays

**Issue**: Gemini may repeat values indefinitely until token limit when processing nested arrays of objects.

**Affected fields in our schema:**
```python
@dataclass
class Event:
    relationshipTargets: list[int]    # Array within array of Events
    relationshipTriangles: list[int]  # Array within array of Events
```

**Instrumentation added** (`btcopilot/pdp.py`):
```python
# Gemini 2.0 Flash array repetition detection
for event in pdp_deltas.events:
    if event.relationshipTargets:
        if len(set(event.relationshipTargets)) != len(event.relationshipTargets):
            _log.warning(f"GEMINI_ARRAY_ISSUE: Repeated values in relationshipTargets...")
    if event.relationshipTriangles:
        if len(set(event.relationshipTriangles)) != len(event.relationshipTriangles):
            _log.warning(f"GEMINI_ARRAY_ISSUE: Repeated values in relationshipTriangles...")
```

**Action**: Monitor logs for `GEMINI_ARRAY_ISSUE` warnings. If frequent, consider schema flattening.

### 2. Missing Expected Fields

**Issue**: Gemini may omit expected fields from output, especially with complex nested structures.

**Workaround**: Explicitly mark all required fields as `required` in JSON schema. For dataclasses via pydantic_ai, this is handled automatically for non-Optional fields.

---

## Optimizations Implemented

### Prompt Reordering (Dec 2024)

**Current assembly order** (`btcopilot/pdp.py`):
```python
data_extraction_prompt = (
    DATA_EXTRACTION_PROMPT      # 1. Extraction intent + brief overview
    + DATA_EXTRACTION_EXAMPLES  # 2. Few-shot examples EARLY (per Gemini docs)
    + DATA_EXTRACTION_RULES     # 3. Detailed schema/rules
    + DATA_EXTRACTION_CONTEXT   # 4. Actual data to process
)
```

### Removed Exhaustive SARF Definitions (Dec 2024)

**Problem**: Commit `f6a7ee8` added exhaustive literature review definitions to prompts.py, doubling prompt size (37K → 74K chars). This overwhelmed Gemini with too much definitional context and degraded F1 scores.

**Fix**: Removed verbose SARF definitions from extraction prompt. Restored concise operational definitions. Exhaustive definitions preserved in `btcopilot/doc/SARF_EXTRACTION_REFERENCE.md` for future reference.

**Prompt size**: 74K → 41K characters (44% reduction)

### Strengthened Extraction Intent

Prompt now starts with explicit extraction task description:
```
**Extract the following information from the user statement:**
1. NEW people mentioned for the first time...
2. NEW events - specific incidents at a point in time...
```

---

## Deferred Improvements

### A. Convert to Pydantic with Field Descriptions

**Benefit**: Pydantic `Field(description="...")` is included in JSON schema sent to Gemini.

**Blocker**: Cannot embed Pydantic models in PyQt desktop apps.

**Workaround applied**: All semantic guidance in prompt text (SECTION 1 + SECTION 2) rather than schema.

### B. Flatten Triangle Arrays

**Current structure:**
```python
relationshipTriangles: list[int]  # [person1_id, person2_id, person3_id]
```

**Proposed structure:**
```python
@dataclass
class Triangle:
    insider1: int
    insider2: int
    outsider: int
```

**Status**: Deferred pending evidence that this is actually causing issues. Monitor `GEMINI_ARRAY_ISSUE` logs.

### C. Explicit Required Fields via TypeAdapter

**Potential approach**: Use pydantic_ai's `TypeAdapter` to generate enhanced JSON schema with explicit `required` arrays, then inject into prompt as documentation.

**Status**: Not implemented. Current approach relies on pydantic_ai's automatic schema generation.

---

## Monitoring & Decision Points

### When to revisit schema changes:

1. **F1 plateau at <80%**: If prompt induction can't push past 80% F1, schema issues may be the bottleneck
2. **Frequent GEMINI_ARRAY_ISSUE warnings**: If >5% of extractions log array repetition warnings
3. **Consistent triangle extraction failures**: If triangle F1 significantly lags other metrics

### Metrics to track:

- `relationshipTargets` extraction accuracy (via GT evaluation)
- `relationshipTriangles` extraction accuracy (via GT evaluation)
- Frequency of `GEMINI_ARRAY_ISSUE` log warnings
- Overall extraction latency (schema complexity affects inference time)

---

## References

- [Gemini Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini 2.0 Flash Issue #449](https://github.com/google-gemini/cookbook/issues/449) - Value repetition bug
- [Pydantic Dataclasses](https://docs.pydantic.dev/latest/concepts/dataclasses/)

---

## Files

| File | Purpose |
|------|---------|
| `btcopilot/btcopilot/schema.py` | Dataclass definitions (PDPDeltas, Event, Person, etc.) |
| `btcopilot/btcopilot/personal/prompts.py` | Extraction prompts (DATA_EXTRACTION_*) |
| `btcopilot/btcopilot/pdp.py` | Prompt assembly + array issue instrumentation |
| `btcopilot/btcopilot/extensions/llm.py` | Gemini integration via pydantic_ai |
