# IRR Analysis - Technical Documentation

As-built documentation for the Inter-Rater Reliability analysis feature.

## Pages

### IRR Index (`/training/irr/`)
Dashboard showing all discussions with 2+ coders.

**Displays:**
- Discussion name (linked to detail page)
- Number of coders
- Coder emails (truncated)
- Statement count
- Average Events F1
- SARF kappas (S, A, R, F columns)
- Action buttons: detail view, pairwise matrix

**Data source:** `get_multi_coder_discussions()` query groups by discussion, filters to 2+ distinct auditor_ids.

### Discussion Detail (`/training/irr/discussion/<id>`)
Per-statement breakdown for one discussion.

**Summary section:**
- Average Events F1 across all coder pairs
- Average Aggregate F1
- SARF kappas (color-coded by Landis & Koch)

**Pairwise comparison table:**
- One row per coder pair (A ↔ B)
- Events F1, People F1, matched event count
- Per-pair SARF kappas

**Per-statement breakdown:**
- Statement text (truncated)
- Number of coders who coded that statement
- Events F1 for that statement
- Expandable table showing each coder pair's metrics
- "Insufficient coder data" message if < 2 coders

### Pairwise Matrix (`/training/irr/discussion/<id>/matrix`)
NxN matrices for visual coder comparison.

**Matrices shown:**
- Aggregate F1 matrix
- Events F1 matrix
- Symptom κ matrix
- Anxiety κ matrix
- Relationship κ matrix
- Functioning κ matrix

Each cell shows the metric for that coder pair. Diagonal shows "-". Color-coded by value ranges.

### System-Wide (`/training/irr/system`)
Cross-discussion aggregate metrics.

**Summary cards:**
- Average Events F1 (all discussions)
- Average Aggregate F1
- SARF kappas with color-coded backgrounds

**Per-discussion table:**
- Links to each discussion's detail page
- Coder count, statement count
- Events F1 and SARF kappas per discussion

## Routes

| Route | Template | Handler |
|-------|----------|---------|
| `/training/irr/` | `irr_index.html` | `index()` |
| `/training/irr/discussion/<id>` | `irr_discussion.html` | `discussion()` |
| `/training/irr/discussion/<id>/matrix` | `irr_matrix.html` | `pairwise_matrix()` |
| `/training/irr/system` | `irr_system.html` | `system()` |

## Data Model

### Coder Identification
- Uses `Feedback.auditor_id` (email) to identify coders
- `Feedback.approved=True` marks primary coder (ground truth)
- Unapproved feedback = IRR coder submissions
- Query: `string_agg(DISTINCT auditor_id)` grouped by discussion

### Extraction Data
- `Feedback.edited_extraction` contains coder's PDPDeltas
- Deserialized via `pdp_json_to_dataclass()`
- Contains: people, events, pair_bonds

## Metrics Calculation

### Entity Matching (from f1_metrics.py)
Reuses existing F1 infrastructure:
- `match_people()` - Fuzzy name matching, parent resolution
- `match_events()` - Person + event type matching
- `match_pair_bonds()` - Person pair matching

### Cohen's Kappa (Pairwise)
```python
sklearn.metrics.cohen_kappa_score(values_a, values_b)
```
- Requires 2+ samples
- Returns None if < 2 samples or single class

### Fleiss' Kappa (3+ Raters)
Manual implementation per Fleiss (1971):
```
κ = (P̄ - P̄e) / (1 - P̄e)
```
- P̄ = mean observed agreement
- P̄e = expected agreement by chance

### SARF Kappa Calculation
For each matched event pair:
1. Extract SARF values (up/down/same/None)
2. Skip None values
3. Calculate kappa on non-None pairs

## Files

| File | Purpose |
|------|---------|
| `training/irr_metrics.py` | Core calculation logic, dataclasses |
| `training/routes/irr.py` | Flask routes, data aggregation |
| `templates/training/irr_index.html` | Dashboard page |
| `templates/training/irr_discussion.html` | Discussion detail page |
| `templates/training/irr_matrix.html` | Pairwise matrix page |
| `templates/training/irr_system.html` | System-wide page |
| `templates/components/irr_macros.html` | Shared Jinja macros |
| `tests/training/test_irr_metrics.py` | 15 unit tests |

## Key Dataclasses

```python
@dataclass
class CoderPairMetrics:
    coder_a: str
    coder_b: str
    people_f1: float
    events_f1: float
    pair_bonds_f1: float
    aggregate_f1: float
    symptom_kappa: float | None
    anxiety_kappa: float | None
    relationship_kappa: float | None
    functioning_kappa: float | None
    percent_agreement: float
    matched_event_count: int

@dataclass
class StatementIRR:
    statement_id: int
    coders: list[str]
    coder_pairs: list[CoderPairMetrics]
    avg_events_f1: float | None

@dataclass
class DiscussionIRR:
    discussion_id: int
    coders: list[str]
    coded_statement_count: int
    pairwise_metrics: list[CoderPairMetrics]
    avg_events_f1: float | None
    avg_symptom_kappa: float | None
    # ... etc
```

## Template Macros

Shared in `components/irr_macros.html`:

```jinja2
{% macro render_kappa(kappa) %}
    {# Color-coded kappa with Landis & Koch interpretation #}
{% endmacro %}

{% macro render_kappa_large(kappa) %}
    {# Large format for summary cards #}
{% endmacro %}

{% macro kappa_class(kappa) %}
    {# Returns Bulma class for notification color #}
{% endmacro %}
```

NaN handling: `kappa == kappa` check (NaN != NaN in IEEE 754).

## Access Control

- Requires `@login_required`
- Requires `@role_required(Role.Auditor)`
- Navbar link visible to auditors+

## Known Limitations

1. **Matched events required** - SARF kappa only calculated when coders identify same person + event type. Low event F1 = no kappa values.

2. **Statement-level only** - Currently compares extractions at statement granularity, not discussion-level cumulative.

3. **No weighted kappa** - Uses unweighted Cohen's kappa. Could add quadratic weights for ordinal SARF values.

## Future Enhancements

- CSV export for statistical analysis
- Confusion matrices per SARF variable
- Coder calibration tracking over time
- Integration with coder training workflow
