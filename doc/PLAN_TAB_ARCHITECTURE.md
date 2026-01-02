# Plan Tab Architecture: Applying Universal Context Graph Principles

## Reference

This architecture applies principles from the universal context graph:
- `github.com/patrickkidd/ccmemory-graph` (or successor repo)

Key source papers:
- "AI's trillion-dollar opportunity: Context graphs" (Gupta & Garg, 2024)
- "How to build a context graph" (Koratana, 2024)

## The Two Clocks Problem

Every system has two clocks (Koratana):
- **State clock**: What's true right now — "user has insomnia"
- **Event clock**: What happened, in what order, with what reasoning — "user tried melatonin, it helped initially, then stopped working, switched to magnesium based on research"

Traditional apps capture state. The Plan tab captures the event clock — the trajectory of understanding, not just the current snapshot.

### What State Clock Captures vs Event Clock

| State Clock | Event Clock |
|-------------|-------------|
| "Sleep is poor" | Which interventions were tried, outcomes, what was learned |
| "Relationship with X is difficult" | The trajectory of interactions, what patterns emerged |
| "Anxiety during family visits" | Which visits, what correlated, what hypotheses tested |

## Decision Traces

A **decision trace** captures not just what was decided, but:
- What options were considered
- What reasoning led to the choice
- What would trigger reconsideration
- What the outcome was

For Family Diagram, decision traces apply to:

### User's Intervention Decisions
```
Decision: Try limiting contact with [person]
Options considered: More contact, less contact, structured contact
Reasoning: Previous contact correlated with symptom flares
Revisit trigger: If symptoms don't improve in 30 days
Outcome: [tracked over time]
```

### Pattern Recognition Decisions
```
Decision: Surface pattern "sleep disruption ↔ family visits"
Basis: 3 co-occurrences in timeline data
Confidence: 0.7
User validation: Confirmed
Status: Promoted to established pattern
```

### Hypothesis Lifecycle
```
Hypothesis: Post-visit recovery > 5 days
Proposed: Jan 2025
Basis: 2 observations + Bowen anxiety transmission concept
Predictions made: Recovery will exceed typical stress recovery time
Observations collected: [list]
Current status: Tracking / Supported / Refuted
```

## Two-Domain Architecture Applied

### Domain 1: User's Specifics (High Confidence)

Everything the user reports or the app observes:
- Timeline events (visits, conflicts, distances)
- Chat-extracted observations ("I didn't sleep well")
- Symptom reports
- Relationship assessments
- User decisions and outcomes

**Confidence: HIGH** — the user lived it.

### Domain 2: Reference Knowledge (Medium Confidence)

Bowen theory and family systems concepts:
- Anxiety transmission patterns
- Triangle dynamics
- Differentiation concepts
- Cutoff/distance effects

Also: General research on relationship stress and symptoms.

**Confidence: MEDIUM** — literature says, but may not apply to this specific user.

### Bridges: Connecting User Data to Theory

When Domain 1 patterns match Domain 2 concepts:

```
Observation: Sleep disrupts during high-anxiety family events
         ↓
Bridge (proposed): This matches "anxiety transmission" pattern
         ↓
User validation: Yes, this connection makes sense to me
         ↓
Bridge (validated): High-confidence link for future reference
```

Rejected bridges are also valuable — they prevent repeated bad suggestions.

## Implementation Approach

### Data Model Extensions

Current SARF data model + additions:

```python
class Observation:
    timestamp: datetime
    content: str  # What was observed
    source: str   # "chat", "manual", "app_detected"
    confidence: float
    related_events: List[TimelineEvent]

class Pattern:
    description: str
    observation_ids: List[str]  # What observations support this
    occurrence_count: int
    confidence: float
    user_validated: bool
    bowen_concept: Optional[str]  # Bridge to Domain 2

class Hypothesis:
    statement: str
    basis: List[str]  # Observation and pattern IDs
    testable_prediction: str
    status: Enum["proposed", "tracking", "supported", "refuted"]
    observations_for: List[str]
    observations_against: List[str]

class Outcome:
    hypothesis_id: str
    result: Enum["supported", "refuted", "inconclusive"]
    evidence: List[str]
    learned: str  # What we now know
```

### Pattern Detection

Minimal viable pattern detection:

1. **Temporal co-occurrence**: Events that happen within N days of each other
2. **Repeated co-occurrence**: Same pattern observed 3+ times
3. **User-reported correlation**: User explicitly connects events in chat

More sophisticated detection (future):
- Statistical correlation analysis
- Bowen pattern matching (triangle detection, cutoff patterns)
- Cross-family-member pattern propagation

### Hypothesis Generation

When patterns emerge, generate hypotheses:

```python
def generate_hypothesis(pattern: Pattern) -> Hypothesis:
    # Match pattern to Bowen concepts
    bowen_match = match_bowen_concept(pattern)

    # Generate testable prediction
    prediction = generate_prediction(pattern, bowen_match)

    return Hypothesis(
        statement=f"Your {pattern.description} may be related to {bowen_match}",
        basis=[pattern.id] + pattern.observation_ids,
        testable_prediction=prediction,
        status="proposed"
    )
```

### Outcome Tracking

As new observations arrive:

```python
def check_hypotheses(new_observation: Observation):
    for hypothesis in active_hypotheses:
        if supports_prediction(new_observation, hypothesis):
            hypothesis.observations_for.append(new_observation.id)
        elif contradicts_prediction(new_observation, hypothesis):
            hypothesis.observations_against.append(new_observation.id)

        # Update status if enough evidence
        hypothesis.status = evaluate_hypothesis(hypothesis)
```

## Integration Points

### Chat → Observations

Extract observations from chat using existing SARF extraction pipeline:
- Symptom mentions → Observation nodes
- Event descriptions → Timeline events + Observations
- Relationship assessments → Relationship data + Observations

### Timeline → Patterns

Analyze timeline for co-occurrence patterns:
- Events close in time to symptom reports
- Repeated relationship-symptom correlations
- Seasonal or cyclical patterns

### Bowen RAG → Bridges

Query Bowen literature (existing RAG system) to:
- Match patterns to theoretical concepts
- Provide educational context for users
- Generate hypothesis frameworks

## Success Metrics

- **Pattern detection accuracy**: Do surfaced patterns match user intuition?
- **Hypothesis validation rate**: What % of hypotheses get confirmed/refuted?
- **User engagement**: Do users interact with the Plan tab?
- **Outcome tracking completion**: Do users report back on predictions?

## Phased Implementation

### Phase 1: Manual Observations + Simple Patterns
- User manually adds observations
- Basic temporal co-occurrence detection
- Simple pattern display

### Phase 2: Chat Extraction + Hypotheses
- Automatic observation extraction from chat
- Hypothesis generation with Bowen connections
- Outcome tracking

### Phase 3: Full Event Clock
- Complete decision traces
- Sophisticated pattern detection
- Export to ccmemory-graph for power analysis
