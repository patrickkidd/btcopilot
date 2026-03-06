# T7-9: Idempotent Re-extraction Analysis

**Date:** 2026-03-03
**Task:** Validate idempotent re-extraction (no duplication after accept)
**Status:** Bug confirmed — regression tests written, all 6 dedup-failure tests FAIL

## Summary

When the LLM fails to honor the "avoid duplicates with committed items" instruction
in `DATA_FULL_EXTRACTION_CONTEXT`, the extraction pipeline has no rules-based safety
net. People and events are duplicated on re-extraction. PairBond dedup also fails
in this scenario because duplicate PairBonds reference new negative person IDs
(not the committed positive IDs), so the dyad match in `commit_pdp_items()` can't
catch them.

## Test Results (2026-03-03)

```
10 PASSED  — "ideal LLM" tests (LLM correctly returns empty on re-extraction)
6 FAILED   — "LLM dedup failure" tests (LLM returns same items with new IDs)
```

### Failure Details

| Test | Expected | Actual | Root Cause |
|------|----------|--------|------------|
| `test_idempotent_reextraction_no_duplicate_people` | 2 people | 4 people | No name-based person dedup |
| `test_idempotent_reextraction_no_duplicate_events` | 1 event | 2 events | No description-based event dedup |
| `test_idempotent_reextraction_pairbond_dedup_works` | 1 pair bond | 2 pair bonds | Dyad dedup fails when PB refs new negative person IDs |
| `test_idempotent_reextraction_total_counts_stable` | (2,1,1) | (4,2,2) | All three entity types duplicated |
| `test_idempotent_reextraction_family_scenario` | (3,2,1) | (6,4,2) | Structural events (Married, Birth) also duplicated |
| `test_pdp_items_after_reextraction_with_duplicates` | 0 PDP items | 2 people, 1 event | No pre-commit dedup filtering |

### PairBond Dedup Failure Mechanism

The existing PairBond dedup in `commit_pdp_items()` (lines 528-543 of schema.py)
works by matching dyads: `{new_pair_bond.person_a, new_pair_bond.person_b}` against
`{pb["person_a"], pb["person_b"]}` in committed pair bonds.

This **fails** when the LLM returns duplicate PairBonds with new negative person IDs
(e.g., `-101, -102`) because:
1. The new PairBond references `-101` and `-102` (not yet committed)
2. `_remap_pair_bond_ids()` maps these to NEW positive IDs (e.g., `5, 6`)
3. The committed pair bond has the ORIGINAL positive IDs (e.g., `1, 2`)
4. Dyad `{5, 6}` != `{1, 2}` → no match → duplicate committed

The dedup would only catch it if the LLM returned positive IDs referencing
committed people — but when it fails to dedup at all, it returns fresh negative IDs.

## Architecture of the Bug

```
extract_full() flow:
  1. diagram_data.pdp = PDP()           # clear PDP (endpoint does this)
  2. LLM prompt includes committed data  # "avoid duplicates with committed items"
  3. LLM ignores instruction             # returns same people/events with new -IDs
  4. _extract_and_validate()             # no dedup against committed items
  5. apply_deltas(empty_pdp, deltas)     # adds everything (PDP was cleared)
  6. PDP now has duplicate items         # ready for user to accept
  7. commit_pdp_items()                  # commits all, creating duplicates

  Missing: step between 4 and 5 (or within 4) that filters deltas against
  committed diagram_data items.
```

## Fix Strategy (T7-11)

Three complementary approaches, from most to least impactful:

### 1. Post-extraction dedup filter (recommended primary fix)

Add a `dedup_against_committed()` function called after `_extract_and_validate()`
returns, before `apply_deltas()`:

```python
def dedup_against_committed(deltas: PDPDeltas, diagram_data: DiagramData) -> PDPDeltas:
    """Strip items from deltas that match committed diagram items."""
    # People: match by (name, gender) or (name, last_name)
    committed_people = {(p["name"], p.get("gender")) for p in diagram_data.people}
    deltas.people = [p for p in deltas.people
                     if (p.name, p.gender) not in committed_people]

    # Events: match by (kind, description, dateTime)
    committed_events = {(e["kind"], e.get("description"), str(e.get("dateTime")))
                        for e in diagram_data.events}
    deltas.events = [e for e in deltas.events
                     if (e.kind.value, e.description, e.dateTime) not in committed_events]

    # PairBonds: match by person names (resolve IDs to names first)
    # ... more complex, needs name resolution
    return deltas
```

### 2. Enhance commit_pdp_items() dedup

Extend the existing PairBond dyad dedup to also match People by name and Events
by (kind, description, dateTime). This is a defense-in-depth layer.

### 3. Improve LLM prompt (least reliable)

Strengthen the dedup instruction in `DATA_FULL_EXTRACTION_CONTEXT` with explicit
examples of what "avoid duplicates" means. This helps but is inherently unreliable —
the rules-based approach is the real fix.

## Test File

`btcopilot/tests/personal/test_idempotent_reextraction.py`

- `TestIdempotentReextractionInMemory` — 6 tests, all pass (ideal LLM)
- `TestIdempotentReextractionWithDB` — 3 tests, all pass (ideal LLM + DB round-trip)
- `TestIdempotentReextractionRelationships` — 1 test, passes (ideal LLM)
- `TestIdempotentLLMDedupFailure` — 6 tests, all FAIL (characterizes T7-9/T7-11 bug)

When T7-11 is fixed, all 6 dedup-failure tests should flip to PASS.
