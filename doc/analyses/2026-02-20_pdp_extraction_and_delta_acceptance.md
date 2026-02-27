# PDP Extraction & Delta Acceptance Flow Analysis

**Date:** 2026-02-20

## Current State

**Updated 2026-02-26**: The Personal app pivoted from per-statement delta
extraction to single-prompt extraction on 2026-02-24. See
[decisions/log.md](../decisions/log.md) entry for rationale.

The PDP pipeline is functionally complete with two extraction modes:
- **Single-prompt** (Personal app): `pdp.extract_full()` — full conversation in
  one LLM call, dramatically better F1.
- **Per-statement** (Training app): `pdp.update()` — sparse deltas per
  statement, used for GT coding workflows.

## Extraction Pipeline

### Single-Prompt Results (2026-02-24, disc 48)
| Entity | F1 |
|--------|-----|
| People | 0.72 |
| PairBonds | 0.33 |
| Events | 0.29 |
| Aggregate | 0.45 |

vs per-statement: Aggregate 0.25, Events 0.10.

### What Works
- ID collision handling (`reassign_delta_ids()` in pdp.py:38-123)
- Retry loop with validation (pdp.py:473-527, 3 retries on validation failure)
- Comprehensive validation (pdp.py:125-305)
- Sparse delta handling (only changed fields via `model_fields_set`)
- Single-prompt extraction produces complete, coherent PDP in one call

### Known Issues
- **LLM-based dedup unreliable**: Prompt includes committed items but LLM
  sometimes re-extracts them anyway. May need rules-based post-filter.
- **Birth event self-reference**: Prompt says `person = who was BORN, child =
  same ID`, causing person to birth themselves. Needs design fix.
- **Event descriptions can be null** (pdp.py:187-191 warns but doesn't reject)
- **No date enforcement** — dateTime can be null, breaking timeline positioning

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

### Current Metrics — Single-Prompt (2026-02-24, disc 48)
| Entity | F1 |
|--------|-----|
| People | 0.72 |
| PairBonds | 0.33 |
| Events | 0.29 |
| Aggregate | 0.45 |

### Legacy Per-Statement Metrics (2026-02-20, 45 statements, 3 discussions)
| Entity | Precision | Recall | F1 |
|--------|-----------|--------|-----|
| People | 77% | 56% | 0.65 |
| PairBonds | - | - | 0.78 |
| Events | 9% | 8% | 0.09 |
| SARF Variables | - | - | 0.11 |

### Notes
- Single-prompt is the primary extraction path going forward
- Per-statement F1 plateaued across 6 prompt iterations (0.217-0.243 ±0.03)
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
| Component | File | Notes |
|-----------|------|-------|
| Single-prompt extraction | btcopilot/pdp.py | `extract_full()` |
| Per-statement extraction | btcopilot/pdp.py | `update()` (training app) |
| Validation | btcopilot/pdp.py | `validate_pdp_deltas()` |
| commit_pdp_items() | btcopilot/schema.py | Acceptance/commit logic |
| Birth inference | btcopilot/schema.py | `_create_inferred_birth_items()` |
| Default prompts | btcopilot/personal/prompts.py | Overridden by fdserver |
| Chat (chat-only) | btcopilot/personal/chat.py | `ask()` — no extraction |
| Extract endpoint | btcopilot/personal/routes/discussions.py | `POST /extract` |
| F1 metrics | btcopilot/training/f1_metrics.py | |
