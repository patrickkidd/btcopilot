# F1 Metrics for AI Data Extraction Evaluation

## Overview

The F1 metrics system evaluates AI extraction quality by comparing AI-generated codes (`Statement.pdp_deltas`) against human ground truth codes (`Feedback.edited_extraction`). This enables systematic measurement of extraction accuracy and guides prompt improvement.

## Calculation Strategy

- **When**: On-demand when pages load (admin dashboard, auditor dashboard, audit pages)
- **How**: Pure Python computation with in-memory caching
- **Cost**: No external API calls, ~5-10s for 100 discussions
- **Caching**: Keyed by `statement_id/feedback_id/approved_hash`, invalidated on approval changes
- **Storage**: In-memory only, no database persistence

## Entity Matching Logic

F1 scores require matching entities between AI and ground truth extractions. Entities are matched by **content similarity**, not IDs.

### People Matching

**Criteria**:
- Name similarity > 0.8 (rapidfuzz ratio on `name` + `last_name`)
- Parent links match after ID resolution (null parents ignored)
- IDs ignored (handles AI negative IDs vs GT negative IDs)

**Example**:
```python
AI:  Person(id=-1, name="John", last_name="Smith", parent_a=-2)
GT:  Person(id=-5, name="Jon", last_name="Smith", parent_a=-8)
```
- Name similarity: 0.95 (fuzzy match "John Smith" vs "Jon Smith") ✓
- Parent links: Resolve -2 → matched GT person, -8 → same matched GT person ✓
- **Match**: YES

### Event Matching

**Criteria**:
- `kind` exact match (enum: Birth, Death, Marriage, etc.)
- `description` similarity ≥ 0.5 (rapidfuzz ratio)
- `dateTime` proximity (±7 days if both specified, None matches any)
- Links match after ID resolution: `person`, `spouse`, `child`, `relationshipTargets`, `relationshipTriangles`
- **Overall score**: 0.8 × description_similarity + 0.2 × date_similarity

**Date Handling**:
- Flexible parsing via `dateutil` (handles "2025-03-12", "March 12 2025", "spring break")
- None dates match any date (treated as unknown/unspecified)
- Tolerance: ±7 days for specified dates

**Example**:
```python
AI:  Event(kind=Visit, description="didn't talk for a while", dateTime="2025-03-15", person=-1)
GT:  Event(kind=Visit, description="didn't talk during spring break", dateTime="2025-03-12", person=-5)
```
- kind: Visit == Visit ✓
- description: 0.65 similarity ("didn't talk" common phrase) ✓
- dateTime: 3 days apart (within ±7 days) → date_sim=0.95 ✓
- person: -1 → resolved GT person -5 ✓
- Overall score: 0.8 × 0.65 + 0.2 × 0.95 = 0.71 ✓
- **Match**: YES

### PairBond Matching

**Criteria**:
- `person_a` and `person_b` match resolved people IDs (order-independent)

**Example**:
```python
AI:  PairBond(person_a=-1, person_b=-2)
GT:  PairBond(person_a=-5, person_b=-8)
```
- person_a: -1 → resolved -5 ✓
- person_b: -2 → resolved -8 ✓
- **Match**: YES

### SARF Variable Matching

**Criteria** (per matched event):
- Exact enum match for: `symptom`, `anxiety`, `relationship`, `functioning`
- Only calculated for events that matched via event matching logic
- Macro-F1: Average F1 across all matched events for each variable

**Example**:
```python
# After matching events...
AI Event:  symptom=Symptom.Depression, anxiety=Anxiety.High
GT Event:  symptom=Symptom.Depression, anxiety=Anxiety.Moderate
```
- symptom: Depression == Depression ✓ (TP)
- anxiety: High != Moderate ✗ (FP for AI, FN for GT)

## F1 Score Types

### 1. Aggregate Micro-F1 (Primary Metric)

Pools all entities (People + Events + PairBonds) into single TP/FP/FN counts.

**Formula**:
```
Precision = TP / (TP + FP)
Recall = TP / (TP + FN)
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

**Where**:
- TP (True Positive): Matched entities between AI and GT
- FP (False Positive): AI entities with no GT match
- FN (False Negative): GT entities with no AI match

**Use**: Overall extraction accuracy across all entity types.

### 2. Per-Type Micro-F1

Separate F1 for each entity type:
- **People F1**: Only people entities
- **Events F1**: Only event entities
- **PairBonds F1**: Only pair bond entities

**Use**: Identify which entity types need improvement (e.g., low Events F1 suggests description matching issues).

### 3. SARF Variable Macro-F1

Macro-average F1 across matched events for each SARF variable:
- **Symptom Macro-F1**: Average F1 for symptom coding across matched events
- **Anxiety Macro-F1**: Average F1 for anxiety coding across matched events
- **Relationship Macro-F1**: Average F1 for relationship coding across matched events
- **Functioning Macro-F1**: Average F1 for functioning coding across matched events

**Formula** (per variable):
```
F1_per_event = [calculate F1 for variable in each matched event]
Macro_F1 = mean(F1_per_event)
```

**Use**: Identify which SARF variables AI is coding incorrectly (e.g., low Relationship F1 suggests prompt needs relationship examples).

### 4. Exact Match Rate

Percentage of statements where AI extraction **exactly matches** ground truth after ID normalization.

**Normalization**:
- Sort entities by kind/name
- Renumber IDs sequentially (1, 2, 3...)
- Remove confidence fields
- Handle both "parents" and "parent_a"/"parent_b" formats

**Formula**:
```
Exact_Match_Rate = (# statements with exact match) / (# total statements)
```

**Use**: Benchmark for "perfect" extractions. Low rate is expected (AI rarely perfect), but should increase with prompt improvements.

## Data Structure

### StatementF1Metrics

Per-statement metrics:
```python
@dataclass
class StatementF1Metrics:
    statement_id: int
    aggregate_micro_f1: float          # Primary metric
    people_f1: float
    events_f1: float
    pair_bonds_f1: float
    symptom_macro_f1: float
    anxiety_macro_f1: float
    relationship_macro_f1: float
    functioning_macro_f1: float
    exact_match: bool
    people_tp: int
    people_fp: int
    people_fn: int
    events_tp: int
    events_fp: int
    events_fn: int
    # ... (full TP/FP/FN breakdown)
```

### SystemF1Metrics

System-wide metrics (aggregated across all approved statements):
```python
@dataclass
class SystemF1Metrics:
    aggregate_micro_f1: float
    people_f1: float
    events_f1: float
    symptom_macro_f1: float
    anxiety_macro_f1: float
    relationship_macro_f1: float
    functioning_macro_f1: float
    exact_match_rate: float
    total_statements: int
    total_discussions: int
```

## Ground Truth Requirements

Only **approved** feedback is used for F1 calculation:
- `Feedback.approved = True`
- `Feedback.edited_extraction` must be present (JSON PDPDeltas)
- Only ONE feedback per statement can be approved (existing constraint)

**Workflow**:
1. Auditor codes discussion with ground truth corrections
2. Auditor/admin approves feedback (sets `approved=True`)
3. F1 cache invalidated for that statement
4. Next page load recalculates F1 with new ground truth

## UI Display

### Admin Dashboard (`/training/admin/`)

**F1 Metrics Card**:
- Overall F1 (aggregate micro-F1)
- People F1, Events F1
- Exact Match Rate (% Perfect PDPs)
- SARF Variable Coding (macro-F1): Symptom, Anxiety, Relationship, Functioning
- Export All Ground Truth button (admin only)

**Visibility**: All auditors and admins

### Auditor Dashboard (`/training/audit/`)

**F1 Metrics Card**: Same as admin dashboard

**Visibility**: All auditors

### Discussion Audit Page (`/training/audit/discussion/<id>`)

**Statement-Level F1** (if approved feedback exists):
- F1 badge in statement header
- Collapsible section with per-category F1 scores
- Detailed TP/FP/FN counts table

## Cache Invalidation

**Triggers**:
- Feedback approved/unapproved: `invalidate_f1_cache(statement_id)`
- Feedback `edited_extraction` modified: `invalidate_f1_cache(statement_id)`
- Bulk approval: Invalidate all affected statements
- Manual cache clear: Admin dashboard button (future)

**Cache Key Format**:
```
f"stmt_{statement_id}_{feedback_id}_{hash(approved_feedbacks)}"
```

## Ground Truth Export

**Endpoint**: `/training/admin/export_ground_truth`

**Query Params**:
- `?discussion_ids=30,31,32` - Export specific discussions
- `?all=true` - Export all approved discussions

**JSON Format** (matches `discussion_30_full.json`):
```json
{
  "discussion": {
    "id": 30,
    "summary": "Discussion summary",
    "created_at": "2025-01-15T10:30:00Z"
  },
  "statements": [
    {
      "id": 981,
      "text": "Statement text",
      "speaker_type": "Subject",
      "pdp_deltas": { /* AI extraction */ },
      "approved_feedback": {
        "auditor_id": "patrick@example.com",
        "edited_extraction": { /* Ground truth */ },
        "approved": true
      }
    }
  ]
}
```

**Use**: Provide to Claude Code for prompt improvement analysis.

## Prompt Improvement Workflow

1. User observes AI extraction problems in personal app
2. User goes to training app audit page for that discussion
3. User codes discussion with ground truth corrections
4. User approves feedback as ground truth
5. User views F1 scores on dashboard to quantify problem
6. User exports approved ground truth discussions
7. **User provides ground truth export to Claude Code** with request to improve extraction prompts
8. Claude Code analyzes F1 categories with lowest scores
9. Claude Code examines ground truth examples where AI failed
10. Claude Code proposes prompt improvements to `btcopilot/btcopilot/personal/prompts.py`
11. User tests improved prompts, codes more discussions, repeat

**Key**: Ground truth export serves as reference dataset for prompt analysis.

## Configuration Constants

**File**: `btcopilot/btcopilot/training/f1_metrics.py`

```python
NAME_SIMILARITY_THRESHOLD = 0.8
DESCRIPTION_SIMILARITY_THRESHOLD = 0.5
DATE_TOLERANCE_DAYS = 7
DESCRIPTION_WEIGHT = 0.8
DATE_WEIGHT = 0.2
```

**Tuning**:
- Lower thresholds: More lenient matching (higher F1, may include false matches)
- Higher thresholds: Stricter matching (lower F1, fewer false matches)
- Adjust based on observed F1 patterns with discussion #30 examples

## Dependencies

**Required packages** (in `pyproject.toml`):
- `rapidfuzz>=3.0.0` - Name/description similarity
- `scikit-learn>=1.3.0` - F1 calculation utilities
- `python-dateutil` - Flexible date parsing (bundled with other deps)

## Testing

**Unit Tests**: `btcopilot/btcopilot/tests/training/test_f1_metrics.py`
- People matching (name similarity, parent links, ID resolution)
- Event matching (kind, description, date, links)
- PairBond matching
- SARF variable macro-F1
- Exact match rate (JSON normalization)
- Date parsing edge cases
- Caching (store, retrieve, invalidate)

**Integration Tests**:
- `test_admin_f1_display.py` - Dashboard F1 display
- `test_bulk_approval.py` - Bulk approval + cache invalidation
- `test_ground_truth_export.py` - JSON export format

## Cumulative F1

### Purpose

Per-statement F1 compares AI vs GT at each individual statement. This has weaknesses:
- Statements with no pair bonds get trivial 1.0 scores, inflating the average
- Missing people referenced later get penalized as FN then TP — double-counting
- AI over-extraction on one statement and under-extraction on another can cancel out

**Cumulative F1** compares the full accumulated PDP at the end of a discussion. Uses `pdp.cumulative()` to build both AI and GT PDPs from all statements, then runs the same matching logic.

### Implementation

- **`CumulativeF1Metrics`** dataclass: Per-discussion metrics
- **`calculate_cumulative_f1(discussion_id)`**: Build AI + GT cumulative PDPs, run matching
- **`calculate_all_cumulative_f1()`**: Run across all discussions with approved GT

### Key Finding: Pair Bonds

AI currently extracts **zero pair bonds** across all discussions. Per-statement F1 shows ~0.778 because most statements have 0 AI + 0 GT pair bonds → `calculate_f1_from_counts(0, 0, 0)` returns 1.0. Cumulative F1 correctly shows 0.000 since GT accumulates 3-5 pair bonds while AI stays at zero. This is a real AI capability gap for prompt improvement.

## Known Limitations

1. **Fuzzy matching thresholds**: May need tuning based on real-world data
2. **Date parsing**: Vague dates ("spring break") parsed via dateutil, may fail for ambiguous inputs
3. **ID resolution complexity**: Requires matching people first, then resolving event links
4. **Exact match rate**: Expected to be low (AI rarely perfect), but should increase with prompt improvements
5. **Scalability**: On-demand calculation acceptable for ~100 discussions (~10s load time). If >500 discussions, consider background job + database storage.

## Future Enhancements

- Manual cache clear button on admin dashboard
- Background job for system-wide F1 calculation (if >500 discussions)
- Database storage of F1 results (avoid recalculation)
- Configurable thresholds via admin UI
- F1 trend charts over time (track prompt improvement progress)
- Per-auditor F1 comparison (identify coding inconsistencies)
- Export format versioning (v1, v2, etc.) with JSON schema validation

## References

- **Core logic**: `btcopilot/btcopilot/training/f1_metrics.py`
- **Admin routes**: `btcopilot/btcopilot/training/routes/admin.py`
- **Audit routes**: `btcopilot/btcopilot/training/routes/audit.py`
- **Templates**: `btcopilot/btcopilot/training/templates/partials/f1_metrics_card.html`
- **Tests**: `btcopilot/btcopilot/tests/training/test_f1_metrics.py`
- **Example ground truth**: `/Users/patrick/Downloads/discussion_30_full.json`
