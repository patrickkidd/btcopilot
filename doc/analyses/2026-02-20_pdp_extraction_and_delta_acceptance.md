# PDP Extraction & Delta Acceptance Flow Analysis

**Date:** 2026-02-20

## Current State

The PDP pipeline is functionally complete but with significant quality gaps and edge case crashes. The architecture (two-tier delta system) is sound.

## Extraction Pipeline

### What Works
- ID collision handling (`reassign_delta_ids()` in pdp.py:38-123)
- Retry loop with validation (pdp.py:473-527, 3 retries on validation failure)
- Comprehensive validation (pdp.py:125-305)
- Sparse delta handling (only changed fields via `model_fields_set`)

### What Doesn't Work
- **Event extraction F1 = 0.09** (Precision 9%, Recall 8%). Prompt lacks event examples.
- **Zero PairBond extraction by AI** (F1 = 0.0). No positive examples in fdserver prompt. Fallback inference at commit time handles some cases.
- **SARF variable F1 = 0.11** (non-functional). Model isn't learning S/A/R/F coding.
- **Event descriptions can be null** (pdp.py:187-191 warns but doesn't reject)
- **No date enforcement** — dateTime can be null, breaking timeline positioning and F1 matching
- **Conversation history usage unclear** — prompt includes history but no guidance on leveraging it

## Delta Acceptance Flow

### What Works
- Transitive closure (schema.py:871-931) — accepting item includes all dependencies
- Pair bond deduplication (schema.py:503-527)
- Birth/Adopted event completeness with 3-case inference (schema.py:674-830)
- Non-birth pair bond inference (schema.py:842-869)
- ID remapping (schema.py:933-976)

### Crashes and Bugs

**CRASH: emotionalunit.py:34** — AttributeError: 'NoneType' has no attribute 'id'
- Trigger: Adding PDP item with parent references
- Root cause: `self._layer` is None when filtering person layers during `emotionalUnit().update()`
- Called from scene.py:433 `_do_addItem()` → `item.parents().emotionalUnit().update()`

**BUG: childOf not set correctly for Conflict events**
- "Accepting Conflict between Tom and Susan does not properly set Mary with childOf"

**BUG: Extra grandparents on Separated accept**
- "Accept Tom and Linda Separated event adds Grandma Joe and Grandma Mary"
- Birth inference logic has edge cases creating unwanted ancestors

**BUG: Event.description can be None after commit**
- pdp.py:187-191 warns but doesn't reject
- Scene's Learn view shows empty event text

## F1 Evaluation

### Current Metrics (45 statements, 3 discussions)
| Entity | Precision | Recall | F1 |
|--------|-----------|--------|-----|
| People | 77% | 56% | 0.65 |
| PairBonds | - | - | 0.78 |
| Events | 9% | 8% | 0.09 |
| SARF Variables | - | - | 0.11 |

### Cumulative vs Per-Statement
- Per-statement F1 indistinguishable across 6 prompt iterations (0.217-0.243 ±0.03)
- Cumulative F1 not yet implemented (measures what user actually sees after "accept all")
- GT data quality: ~40% of 88 GT events structurally unmatchable

## Test Coverage

### Good Coverage
- PDP commit/reject flows (`tests/personal/test_pdp.py`)
- ID collision detection, cross-reference validation (`tests/schema/test_validation.py`)
- Transitive closure, cascade deletes, pair bond commit

### Gaps
- No e2e test of LLM extraction → validation → PDP apply
- No test for accept-all workflow with scene integration
- No test for events with null description
- No test for birth inference with duplicate person+spouse pairs
- No test for Moved event pair bond inference

## Key Files
| Component | File | Lines |
|-----------|------|-------|
| Core extraction | btcopilot/pdp.py | 565-614 |
| Validation | btcopilot/pdp.py | 125-305 |
| commit_pdp_items() | btcopilot/schema.py | 463-571 |
| Birth inference | btcopilot/schema.py | 674-830 |
| Default prompts | btcopilot/personal/prompts.py | 247-687 |
| Chat integration | btcopilot/personal/chat.py | 24-90 |
| F1 metrics | btcopilot/training/f1_metrics.py | 1-1257 |
