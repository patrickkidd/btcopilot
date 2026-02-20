# Personal App v2: Pattern Intelligence for Emotional Functioning

## Design Decisions (Confirmed)

| Dimension | Decision |
|-----------|----------|
| User cognitive load | **Light** — occasional in-chat confirmations, not active data management |
| Bowen theory visibility | **Invisible** — framework runs under the hood, insights in plain language |
| Value proposition | **Pattern intelligence** — "discover correlations you couldn't see yourself" |

## Core Insight

The Personal app's value proposition parallels what you're building with ccmemory for software/career, but for **emotional functioning**:

| Dimension | ccmemory (Software/Career) | Personal App v2 |
|-----------|---------------------------|-----------------|
| Domain 1 | Your decisions, corrections, exceptions | User's functioning shifts, relationship events, patterns |
| Domain 2 | Docs, APIs, literature | Bowen theory constructs (invisible to user) |
| Capture | Explicit (corrections, decisions) | Implicit (chat extraction via PDP) |
| User engagement | High (research-oriented) | Lower (consumer-grade, coaching-seeking) |
| Bridge validation | Manual (you confirm links) | Light (in-chat "does this seem right?") |
| Output | Research partnership, hypothesis testing | Pattern intelligence, surfaced insights |

The Personal app already has the core extraction infrastructure (PDP delta extraction from chat). What it lacks is:
1. **Trajectory accumulation** — building a longitudinal model of functioning over time
2. **Pattern detection** — recognizing correlations across events/relationships
3. **Light validation** — occasional in-chat confirmation of detected patterns
4. **Context-aware responses** — chat that knows user's accumulated patterns

---

## Refined Approach: Relational Pattern Intelligence

Based on your selections, the v2 value centers on **pattern detection in relationship systems** — the core Bowen theory insight, delivered invisibly:

### What the System Does
1. **Accumulates** events/shifts extracted from chat (existing PDP system)
2. **Correlates** temporal patterns: which relationships precede which symptoms
3. **Surfaces** patterns in plain language: "I've noticed X happens before Y"
4. **Validates lightly** in chat: "Does this ring true?"
5. **Refines** based on confirmations/corrections

### What Users Experience
- Chat naturally, no data management
- Occasionally see pattern insights: "The last 3 times you mentioned [X], you also described feeling [Y]"
- Sometimes asked to confirm: "Does this pattern feel accurate to you?"
- Over time, the coach "knows" them — references past patterns, avoids re-asking what it already knows

### Invisible Framework Translation

| Bowen Construct | User-Facing Language |
|-----------------|---------------------|
| Triangle | "When [A] and [B] are in conflict, [C] often gets pulled in" |
| Distance | "You tend to create space when things get tense with [X]" |
| Conflict | "Tension with [X] tends to peak around [event type]" |
| Reciprocity | "When [X] takes charge, you seem to step back" |
| ChildFocus | "Worries about [child] seem to increase when tension rises elsewhere" |
| Anxiety transmission | "[X]'s stress seems to show up in your symptoms within a few days" |

### Pattern Types to Detect

1. **Temporal correlations**: Event A precedes symptom shift B within N days
2. **Relationship clustering**: Person X appears in multiple distress-related events
3. **Mechanism profiling**: User's default anxiety binding (distance, conflict, reciprocity)
4. **Multigenerational echoes**: Patterns that repeat across generations
5. **Cyclical patterns**: Time-based (holidays, anniversaries) correlations

---

## Key Differences from ccmemory

1. **Extraction vs. capture**: ccmemory captures explicitly when you tell it "I decided X". Personal app extracts implicitly from natural conversation.

2. **Confidence without validation**: ccmemory relies on your explicit confirmation. Personal app tracks confidence internally, only occasionally seeks light validation in-chat.

3. **Proactive surfacing**: ccmemory responds to explicit knowledge management. Personal app proactively surfaces patterns: "I notice X pattern. Can we talk about this?"

4. **Framework invisibility**: You engage with concepts explicitly. Personal app users never see "triangle" — they see "when A and B fight, C gets pulled in."

---

## Implementation Architecture

### Layered Approach

```
┌─────────────────────────────────────────────────────────────┐
│  CHAT LAYER (existing)                                       │
│  - User messages                                             │
│  - AI responses (now context-aware)                          │
│  - Light validation prompts                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓ ↑
┌─────────────────────────────────────────────────────────────┐
│  PATTERN INTELLIGENCE LAYER (new)                           │
│  - Correlation detection                                     │
│  - Pattern storage with confidence                           │
│  - Context injection into chat                               │
│  - Validation tracking                                       │
└─────────────────────────────────────────────────────────────┘
                              ↓ ↑
┌─────────────────────────────────────────────────────────────┐
│  DOMAIN 1: USER'S SPECIFICS (existing PDP + extensions)     │
│  - People, Events, PairBonds (existing)                     │
│  - Cumulative event timeline                                 │
│  - Shift history per person                                  │
└─────────────────────────────────────────────────────────────┘
                              ↓ ↑
┌─────────────────────────────────────────────────────────────┐
│  DOMAIN 2: BOWEN CONSTRUCTS (internal reference)            │
│  - Mechanism definitions (invisible to user)                 │
│  - Pattern templates                                         │
│  - Correlation rules                                         │
└─────────────────────────────────────────────────────────────┘
```

### Technical Integration Points

| Component | Current State | v2 Extension |
|-----------|--------------|--------------|
| PDP extraction | Per-statement deltas | Accumulates into timeline |
| Chat context | Current statement + history | + relevant patterns, past correlations |
| Response generation | Bowen-informed but amnesiac | Pattern-aware, references past insights |
| Direction detection | Per-statement | Could factor in accumulated context |
| Diagram data | Relational structure | + temporal pattern annotations |

### Storage Options

**Option A: PostgreSQL Extension (simpler)**
- Add `patterns` table: correlations with confidence, validation status
- Add `pattern_instances` table: specific event pairs that constitute a pattern
- Use SQL window functions for temporal correlation queries
- Pro: No new infrastructure, simpler ops
- Con: Complex graph queries are awkward in SQL

**Option B: Neo4j Graph DB (matches ccmemory)**
- People, Events as nodes; relationships as edges
- Patterns as higher-order nodes connecting event clusters
- Cypher queries for pattern detection
- Pro: Natural fit for relationship data, rich queries
- Con: New infrastructure, sync complexity with PostgreSQL

**Recommendation**: Start with PostgreSQL extension for MVP. Migrate to graph DB if query complexity warrants it.

---

## MVP vs. v2 Relationship

### MVP (SARF Intake)
- Chat-based intake of family system data
- Extraction via PDP → people, events, pair_bonds
- Basic Bowen-informed responses
- **Output**: Populated diagram with initial data

### v2 (Pattern Intelligence)
- **Builds on MVP**: Same chat, same extraction, same data model
- **Adds**: Longitudinal accumulation, correlation detection, pattern surfacing
- **SARF intake becomes seeding**: First conversations populate initial graph
- **Post-intake**: Ongoing chat continues accumulating, patterns emerge over time

The transition is natural — users don't experience a phase change, just an increasingly "knowing" coach.

---

## Implementation Phases

### Phase 1: Temporal Pattern Detection
- Add correlation detection logic (SQL or Python)
- Detect: Event A with person X precedes symptom shift within N days
- Store detected patterns with confidence scores
- No user-facing changes yet — validation in logs

**Critical files**:
- `btcopilot/btcopilot/pdp.py` — extend to accumulate timeline
- `btcopilot/btcopilot/personal/patterns.py` — new module for detection

### Phase 2: Context Injection
- Modify `ask()` to query relevant patterns before response generation
- Inject pattern context into meta_prompt
- AI becomes aware of user's history

**Critical files**:
- `btcopilot/btcopilot/personal/chat.py` — add pattern context
- `btcopilot/btcopilot/personal/prompts.py` — add pattern injection template

### Phase 3: Light Validation in Chat
- AI occasionally surfaces a detected pattern: "I've noticed X..."
- Asks for confirmation: "Does this feel accurate?"
- User response updates pattern confidence
- Patterns with high confidence inform future responses

**Critical files**:
- `btcopilot/btcopilot/personal/chat.py` — validation flow
- New: `btcopilot/btcopilot/personal/validation.py` — pattern confirmation logic

### Phase 4: Proactive Pattern Surfacing
- System proactively mentions relevant patterns when contextually appropriate
- "Last time you mentioned [X], you also described [Y]. Is that happening now?"
- Avoids re-asking questions about confirmed patterns

---

## Example Interaction Flow (v2)

**Early sessions (MVP-like):**
```
User: "My sister called yesterday and I couldn't sleep last night."
AI: [extracts: Event(person=sister, kind=contact), Symptom(shift=down)]
AI: "That sounds frustrating. How did the call go?"
```

**After 5+ similar events (v2):**
```
User: "My sister's visiting next week."
AI: [detects: sister visits correlate with sleep disruption, 4 instances]
AI: "I've noticed that after interactions with your sister, you often
    mention sleep difficulty. Does that pattern feel accurate?"
User: "Yeah, actually. I never connected those."
AI: [updates pattern confidence: 0.85]
AI: "What do you think triggers that for you?"
```

**Established pattern:**
```
User: "My sister's coming for Thanksgiving."
AI: [high-confidence pattern established]
AI: "Given what we've noticed about how visits with your sister affect
    your sleep, is there anything you're thinking about differently
    this time?"
```

---

## Relationship to Learn Tab Evaluation

See [LEARN_TAB_EVALUATION.md](LEARN_TAB_EVALUATION.md) for the related feature.

| Aspect | Learn Tab Evaluation | Pattern Intelligence (v2) |
|--------|---------------------|--------------------------|
| Surface | Visual timeline, cluster navigation | Chat conversation |
| Output | Clinical formulation, evaluation panel | In-chat pattern insights |
| User action | View, explore, navigate | Confirm patterns, chat naturally |
| Trigger | User opens Learn tab | Pattern detected during chat |
| Grounding | FE Ch 10 questions, Havstad method | Same underlying framework |

### Shared Components (Build Once)

1. **Temporal correlation detection** — Event A precedes shift B within N days
2. **Cluster detection** — 3+ SARF shifts within 6 months (see LEARN_TAB_EVALUATION.md)
3. **Context linking** — Distant events connected via anxiety transmission
4. **Confidence scoring** — How reliable is a detected pattern?
5. **Bowen framework mapping** — Invisible categorization of mechanisms

### Different Concerns

| Learn Tab | Pattern Intelligence |
|-----------|---------------------|
| Handles sparse data visualization | Handles chat context injection |
| User explores at their pace | AI proactively surfaces |
| Clinical formulation (text block) | Conversational validation |
| Full evaluation (10 questions) | Light confirmations |

### Implementation Sequence

**Recommended**: Build shared components first (cluster detection, correlation), then branch:
- Learn Tab uses them for visualization + formulation
- Pattern Intelligence uses them for chat context + validation

---

## Status

**Document Type**: Vision/Brainstorm (not implementation plan)
**Phase**: Concept documented, awaiting prioritization
**Dependencies**: LEARN_TAB_EVALUATION.md (may share components)
**Next Steps**:
- Review both documents together
- Decide implementation priority
- Identify shared component scope

---

## References

- [UNIVERSAL_CONTEXT_GRAPH.md](/Users/patrick/ccmemory/doc/UNIVERSAL_CONTEXT_GRAPH.md) — ccmemory architecture that inspired this
- [LEARN_TAB_EVALUATION.md](LEARN_TAB_EVALUATION.md) — related Learn tab feature
- [CHAT_FLOW.md](../CHAT_FLOW.md) — existing chat architecture
- [CONTEXT.md](../../CONTEXT.md) — Bowen theory domain model
- [DATA_MODEL.md](../specs/DATA_MODEL.md) — schema definitions
- [specs/PDP_DATA_FLOW.md](../specs/PDP_DATA_FLOW.md) — PDP extraction pipeline

---

## Document Metadata

**Created**: 2026-01-04
**Author**: Claude (brainstorm session with Patrick)
**Inspired by**: ccmemory Universal Context Graph architecture
