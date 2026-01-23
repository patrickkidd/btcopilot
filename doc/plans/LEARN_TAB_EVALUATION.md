# Learn Tab: Post-Processing and Clinical Evaluation

**Status**: Literature Review Complete → Domain Expert Calibration Required
**Owner**: Patrick
**Last Updated**: 2026-01-03
   
---

## Executive Summary

The Learn tab needs AI-powered clinical evaluation to help users make sense of raw timeline data. The user collects data via chat, audio, manual entry, and bulk import. The system must detect meaningful patterns, cluster events temporally, and surface clinical insights grounded in Bowen theory.

**Core Problem**: Raw timeline data is overwhelming. Events stack on single pixels when displayed. Users need help seeing:
1. What clusters of events are meaningful
2. How events relate across time (not just within a cluster)
3. What the clinical interpretation of patterns might be

---

## Literature Review Status

**COMPLETED**: Exhaustive sequential read of ALL authoritative sources (2026-01-03).

**Sources Read**:
- **Family Evaluation** (Kerr) - All 12 chapters (~500KB)
- **Family Therapy in Clinical Practice** (Bowen) - All 23 chapters (~900KB)
- **Havstad Weight Loss Article** - Full article (~30KB)

**Full findings**: [CLINICAL_EVAL_LIT_REVIEW.md](../sarf-definitions/log/CLINICAL_EVAL_LIT_REVIEW.md)

### Key Findings from Exhaustive Review

1. **THE HAVSTAD TIMELINE METHOD is the operational model**
   - Family System Shift → Anxiety Shift → Functioning Shift → Symptom Shift
   - **4-12 week window** between nodal events and symptom shifts (documented)
   - The "key shift" can be reliably identified by independent observers
   - Shifts organized into chronological timeline

2. **FE Chapter 10's Ten Questions framework for clinical evaluation**
   - What's the symptom? Who's symptomatic?
   - What are the relationship patterns? (distance, conflict, over/underfunctioning, projection)
   - What's the intensity and what influences it? (stressors vs adaptiveness)
   - Extended family stability and cutoff level

3. **Reciprocal functioning is central**
   - One up, one down - when one gains strength, another loses
   - Symptoms are systemic expression, not individual pathology
   - Clusters may include BOTH up-shifts and down-shifts

4. **Four anxiety-binding mechanisms** (FE Ch 7)
   - Marital conflict, spouse dysfunction, child dysfunction, emotional distance
   - Most families use a combination

5. **Context linking via triangle dynamics**
   - Distant events connect via triangle shifts that ripple forward
   - Family is a single emotional unit - nothing is isolated
   - Multigenerational patterns replicate

---

## Current State

### Data Sources (Implemented)
- Chat with AI (extracts PDP deltas)
- Audio transcription
- Manual entry
- Bulk import from journal notes

### Existing UI Components
- **Line Graph**: Events stacked on single pixels when one event is far in past
- **Timeline List**: More for editing than sense-making
- **SARF Graph**: Designed but not fully operationalized (see SARF_GRAPH.md)

### Pain Points
1. Graph unusable when events span long time ranges (e.g., birth date + recent events)
2. No cluster detection or labeling
3. No navigation between temporal contexts
4. No way to see meaningful relationships between distant events
5. No clinical interpretation layer

---

## Open Questions Requiring Domain Expert Calibration

**Full question set**: See [CLINICAL_EVALUATION_METHODOLOGY.md Part 7](../CLINICAL_EVALUATION_METHODOLOGY.md#part-7-open-questions-for-domain-expert)

### Priority Questions for First Calibration Session

#### Cluster Detection

1. **Temporal density threshold**: My hypothesis is 3+ SARF shifts within 6 months = cluster. Correct?

2. **Nodal events vs SARF shifts**: Can demographic events alone (births, deaths) form meaningful clusters, or must there be F/A/S shifts?

3. **Minimum cluster size**: Can a single isolated event be clinically significant, or does significance require patterns?

#### Context Linking

4. **Typical lag window**: Havstad found 4-12 weeks for weight loss. What's typical for other symptoms? Longer-term effects (years)?

5. **Causal vs coincidental**: What cues distinguish causally-related distant events from coincidental timing?

#### Formulation

6. **Must-have elements**: What are the non-negotiables in a clinical formulation?

7. **Bad formulation**: What would a bad formulation look like? (Helps define negative space)

#### Implementation

8. **User language**: How much Bowen theory terminology should the user see?

9. **Confidence thresholds**: What confidence level should block an interpretation from being shown?

---

## Domain Knowledge Status

### From Literature (COMPLETED)
- [x] Bowen theory clinical evaluation methodology (FE Ch 10)
- [x] Temporal shift model (Havstad)
- [x] Observable markers for F, A, S shifts (SARF definitions)
- [x] Context linking rationale (nodal events, stressor accumulation)

### From Patrick (INTERVIEW REQUIRED)
- [ ] Validation of cluster detection thresholds
- [ ] Validation of context linking windows
- [ ] Examples of good vs. poor theoretical formulations
- [ ] Edge cases and common pitfalls
- [ ] How to handle sparse vs. dense data

---

## Proposed Architecture (Draft)

### Data Model Extensions

```python
@dataclass
class EventCluster:
    id: int
    label: str  # User-visible name (e.g., "Mom's illness period")
    start_date: str
    end_date: str
    event_ids: list[int]  # Events in this cluster
    context_event_ids: list[int]  # Related events outside temporal bounds
    summary: str  # AI-generated description
    confidence: float

@dataclass
class ClinicalEvaluation:
    id: int
    diagram_id: int
    created_at: str
    updated_at: str
    clusters: list[EventCluster]
    formulation: str  # Theoretical formulation text
    key_patterns: list[str]  # Bullet points
    hypotheses: list[str]  # Connections to track
    confidence: float
```

### Processing Pipeline

```
Timeline Events → Cluster Detection → Context Linking → Clinical Evaluation
                       ↓                    ↓                    ↓
               EventCluster[]       Context relationships    Formulation
```

### UI Components (TBD)

1. **Cluster Navigator**: Horizontal bar showing cluster labels, tap to navigate
2. **Context Overlay**: When viewing cluster, show related distant events
3. **Evaluation Panel**: Formulation, patterns, hypotheses

---

## Task Breakdown

### Phase 1: Domain Discovery
- [ ] Interview Patrick on clinical evaluation process
- [ ] Document Bowen theory evaluation methodology
- [ ] Create examples of good theoretical formulations
- [ ] Define cluster detection criteria

### Phase 2: Cluster Detection
- [ ] Implement temporal clustering algorithm
- [ ] Add cluster labeling (AI-generated)
- [ ] Implement context event linking
- [ ] Add cluster storage to data model

### Phase 3: Graph/Timeline Improvements
- [ ] Add cluster navigation UI
- [ ] Implement animated zoom/pan to event
- [ ] Add context overlay for distant events
- [ ] Handle outlier events gracefully

### Phase 4: Clinical Evaluation
- [ ] Design evaluation prompt (with Patrick)
- [ ] Implement evaluation generation
- [ ] Add evaluation storage
- [ ] Create evaluation display UI

### Phase 5: Integration
- [ ] Connect Learn tab to evaluation system
- [ ] Add user feedback on evaluations
- [ ] Iterate based on real-world usage

---

## Risks and Unknowns

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bowen theory operationalization is complex | High | Iterative discovery with Patrick |
| LLM training data on Bowen is wrong | High | Ground prompts in literature + Patrick's expertise |
| Cluster detection may not match user intuition | Medium | User-editable clusters |
| Temporal context relationships are subjective | Medium | Let users confirm/reject AI suggestions |
| Mobile graph performance with many events | Medium | Virtualization, progressive loading |

---

## Success Criteria (Draft)

- [ ] User can identify meaningful clusters without manual selection
- [ ] Graph shows events in context regardless of time span
- [ ] Evaluation provides actionable clinical insight
- [ ] Non-expert users can understand Bowen-grounded interpretations

---

## References

- [SARF_GRAPH.md](../../../familydiagram/doc/SARF_GRAPH.md) - Existing graph design
- [PLAN_TAB_VISION.md](../PLAN_TAB_VISION.md) - Related insights feature
- [DATA_MODEL_FLOW.md](../DATA_MODEL_FLOW.md) - Current data structures
- [CONTEXT.md](../../CONTEXT.md) - Bowen theory domain context

---

## Session Notes

### 2026-01-03 - Initial Scoping
- Patrick identified core problem: graph/timeline don't help users make sense of data
- Key insight: Events usually cluster into 2-3 meaningful periods (sampling bias)
- Challenge: Showing clusters misses context from distant events
- Clinical evaluation is complex - requires iterative knowledge capture
- Most LLM knowledge of Bowen theory is wrong - must ground in literature + Patrick

### 2026-01-03 - Literature Review Completed

**Sources Read (Full Sequential)**:
- FE Chapter 10 - Family Evaluation (~50,000 chars)
- Havstad Weight Loss Article (~30,000 chars)
- SARF definitions: 01-functioning.md, 02-anxiety.md

**Key Discoveries**:
1. **FE Ch 10 provides the 10-question evaluation framework** - Therapists answer specific questions about family process, not freeform interpretation
2. **Havstad's timeline method is THE operational model** - Shifts tracked chronologically: family system → anxiety → functioning → symptom
3. **4-12 week window is documented** for event-to-response lag (can be longer)
4. **"Context events" = stressors that precede clusters** - cumulative stress matters
5. **Existing SARF definitions provide observable markers** - can reuse for shift detection

**Deliverables Created**:
- [CLINICAL_EVALUATION_METHODOLOGY.md](../CLINICAL_EVALUATION_METHODOLOGY.md) - Full findings with open questions

**Next Steps**:
1. Patrick to review CLINICAL_EVALUATION_METHODOLOGY.md
2. Schedule calibration session to answer questions in Part 7
3. After calibration: begin Phase 1 (shift detection using existing SARF markers)
