# IRR Calibration: Multi-Coder Event Comparison

## Problem

The current calibration system compares coders **pairwise** (`compare_cumulative_pdps` in `calibrationutils.py`). With N coders, this produces N*(N-1)/2 pairs. The same event appears in multiple disagreement cards — once per pair that disagrees — causing:

1. **Redundancy**: 5 coders = 10 pairs. A single event where 4 agree and 1 disagrees generates 4 separate cards instead of 1.
2. **Missing context**: Each card shows only 2 coders' values. The meeting facilitator can't see that 3 other coders agree with one side, which would make triage obvious.
3. **Inflated counts**: 120 "disagreements" for discussion 36 with 5 coders is mostly duplicates of the same underlying events.

## Proposed Architecture

### Phase 1: Multi-coder event matching

Replace pairwise comparison with all-at-once matching:

1. Build a unified event match table across all coders using the existing matching criteria (kind + person + dateTime).
2. For each matched event, collect all coders' SARF values into one row: `{coder_id: {symptom, anxiety, relationship, functioning}}`.
3. A "disagreement" is a matched event where any coder's value differs from the others on any SARF field.

This collapses N*(N-1)/2 pairwise cards into ~E event-level cards where E << current count.

### Phase 2: Card redesign

Each card shows:
- All coders' values in one view (not just 2)
- Majority/minority split visible at a glance
- Each coder badge links to their source statement (using the deterministic tracing already fixed)

### Phase 3: LLM analysis adjustment

Currently one LLM call per pairwise disagreement. With multi-coder cards:
- One LLM call per event disagreement, with all coders' values as input
- The LLM sees the full picture and can identify majority consensus
- Fewer calls total (cost reduction proportional to deduplication)

## Key Files

| File | Current Role | Change Needed |
|------|-------------|---------------|
| `calibrationutils.py` | `compare_cumulative_pdps()` — pairwise | New `compare_all_coders()` — multi-coder match table |
| `calibrationutils.py` | `EventDisagreement` — stores event_a/event_b, coder_a/coder_b | New dataclass with `events: dict[str, Event]` (coder_id -> event) |
| `calibrationutils.py` | `trace_to_statements()` — per-coder description match | Extend to N coders (already uses per-coder descriptions) |
| `calibration.py` | Pairwise loop building pending LLM calls | Single pass over multi-coder disagreements |
| `calibrationprompts.py` | `IRR_REVIEW_USER` — references 2 coders | Update to show all coder values |
| `calibration_card.html` | Shows 2 coder badges per field row | Shows N coder badges per field row |

## Risks

- **Event matching across >2 coders is harder**: Pairwise matching is transitive in theory (if A matches B and B matches C, then A matches C), but fuzzy matching criteria could break transitivity. Need to handle this explicitly — probably union-find on matched pairs.
- **LLM prompt size**: With 5 coders' values per event, prompts grow. Flash can handle it but worth monitoring.
- **Stored report format change**: `discussion.calibration_report` JSON schema changes. Old reports won't render correctly — but per CLAUDE.md we prefer delete/re-create over backward compatibility.

## Estimation

~100-150 lines of new/modified Python, ~20 lines template changes. The matching logic is the hard part; the rest is plumbing.
