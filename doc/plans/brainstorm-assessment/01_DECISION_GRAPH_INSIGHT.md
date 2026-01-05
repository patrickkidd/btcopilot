# Decision Graph Insight: Implicit Behavioral Model Extraction

**Date**: 2026-01-04
**Context**: Brainstorm session evaluating PATTERN_INTELLIGENCE_VISION.md against ccmemory's Universal Context Graph architecture
**Status**: Raw insight capture — do not compress or summarize

---

## The Gap Identified

PATTERN_INTELLIGENCE_VISION.md treats the two-domain architecture as a **data organization principle** but misses the deeper abstraction: **decision graphs as a model of the person's behavioral logic**.

The current document focuses on:
- Correlations (X precedes Y)
- Events as data points
- "I notice a pattern" reactive surfacing
- Symptom focus

What's missing:
- Choices (faced X, chose Y, because Z)
- Decisions as behavioral logic
- "You tend to choose X in situation Y" — treating user as agent
- Predictive: "Given your pattern, what might you do here?"
- Choice focus (closer to functioning than symptoms)

---

## The Deeper Abstraction

In ccmemory for software, a decision captures:
- **What was chosen** (the branch taken)
- **Options considered** (alternatives)
- **Rationale** (why this, not that)
- **Precedent it sets** (future decisions will reference this)

This creates a **behavioral model of the developer**: given context X, they tend to choose approach Y for reason Z.

**The insight**: People make "decisions" about emotional/relational behavior too — but they're often **implicit, unconscious, and automatic**. The Personal app could extract these implicit behavioral decisions and surface them as patterns.

---

## What a Decision Graph for Emotional Functioning Would Look Like

### Explicit Decisions (Rare but High Value)

When users actually articulate choices:
- "I decided not to call my sister back."
- "I'm going to avoid the family dinner."
- "I told my husband to handle it this time."

These are **relational posture decisions** — consciously choosing distance, delegation, avoidance, engagement.

### Implicit Decisions (The Gold Mine)

When users describe behavior that reveals unstated choices:
- "I just didn't feel like calling" → **Implicit decision: distance**
- "I ended up handling all the arrangements" → **Implicit decision: overfunctioning**
- "I brought up the topic with my mom" → **Implicit decision: triangulation attempt**

The AI could detect these and ask: "It sounds like you chose to take on the arrangements yourself. What was driving that choice?"

This surfaces the **implicit rationale** — which is often anxiety-driven and unconscious.

### The Behavioral Model That Emerges

Over time, you could extract:
- **Default anxiety binding mechanism**: "When anxious, you tend to overfunction"
- **Relational posture patterns**: "With X, you distance. With Y, you engage conflict."
- **Decision precedents**: "Last time you faced this situation with Z, you chose to avoid. How did that work out?"

This is the **implicit behavioral model** — what Bowen theory calls the person's "functional position" in their family system.

---

## Decision Graph Architecture for Personal App

### Node Types

```
DecisionPoint
├── context: What situation triggered this?
├── implicit_options: What could have been done?
├── choice: What was actually done?
├── rationale_stated: What the user said about why (if anything)
├── rationale_inferred: What Bowen framework suggests about why
├── mechanism: Which anxiety binding mechanism? (distance, conflict, reciprocity, projection)
├── outcome: What happened after? (if known)
├── confidence: How certain is this inference?
```

### Extraction Examples

**User says**: "My mom called about Thanksgiving and I just said I was too busy to talk."

**Extracted**:
```
DecisionPoint {
  context: "Mother initiated contact about family event"
  choice: "Declined engagement, cited external constraint"
  mechanism: Distance
  rationale_stated: "Too busy"
  rationale_inferred: "Avoidance of anxiety around family gathering"
  confidence: 0.7
}
```

**User says**: "I ended up making all the travel arrangements for my brother's wedding."

**Extracted**:
```
DecisionPoint {
  context: "Family event requiring coordination"
  choice: "Took on coordination responsibility for others"
  mechanism: Overfunctioning
  rationale_stated: None
  rationale_inferred: "Reduced own anxiety by taking control; possibly compensating for perceived underfunctioning by others"
  confidence: 0.6
}
```

---

## The Precedent System for Personal App

This is where it gets powerful. In ccmemory:
- "How did we handle X before?" → precedent search
- "Why is it this way?" → decision trace

In Personal app:
- "How did you handle this with [person] before?" → relational precedent search
- "What typically happens when you [behavior]?" → outcome pattern

**Example**:
```
User: "My mother-in-law is visiting next week."

AI: [Queries decision graph for mother-in-law interactions]
AI: "Last time she visited, you mentioned taking on all the meal planning
    and ending up exhausted. You said you wished you'd asked for more help.
    Is there a different approach you'd like to try this time?"
```

This is **precedent-aware coaching** — the coach remembers not just events, but the user's choices and their expressed reflections on outcomes.

---

## Implicit Behavioral Model Extraction

The deep abstraction: **What if the system could articulate the user's implicit operating model?**

After sufficient data:
```
Your Implicit Behavioral Model (draft):

When anxiety rises in your nuclear family:
- With spouse: You tend toward conflict (3 instances)
- With children: You tend toward overfunctioning (5 instances)

When anxiety rises with family of origin:
- With mother: Distance (4 instances)
- With siblings: Triangulation via spouse (2 instances)

Pattern: Your anxiety often manifests as over-responsibility
followed by resentment. You've mentioned "I wish I hadn't taken
that on" after 4 of 5 overfunctioning instances.
```

This isn't just "pattern intelligence" — it's a **structured model of behavioral tendencies** that could be:
1. Shown to the user as self-insight
2. Used to inform coaching (recognize the pattern before they fall into it)
3. Tracked over time for change

---

## How This Differs from PATTERN_INTELLIGENCE_VISION.md

| Current Document | Decision Graph Extension |
|-----------------|-------------------------|
| Correlations (X precedes Y) | Choices (faced X, chose Y, because Z) |
| Events as data points | Decisions as behavioral logic |
| "I notice a pattern" | "You tend to choose X in situation Y" |
| Reactive surfacing | Predictive: "Given your pattern, what might you do here?" |
| Symptom focus | Choice focus (closer to functioning) |

The decision graph treats the user as an **agent making choices** (even implicit ones), not just a **sensor generating data**.

---

## Integration with SARF Timeline

The SARF timeline captures **what happened**. The decision graph captures **what choices were embedded in what happened**.

Every Event in the timeline could have linked DecisionPoints:
- Event: "Had argument with spouse about finances"
  - DecisionPoint: Chose engagement over distance
  - DecisionPoint: Escalated rather than de-escalated (reciprocal pattern)

- Event: "Took over project at work when colleague dropped it"
  - DecisionPoint: Overfunctioning response to perceived gap

The timeline is the **event clock**. The decision graph is the **choice clock** — the record of behavioral responses to circumstances.

---

## What This Enables

1. **Precedent-aware coaching**: "Last time you faced X, you chose Y. How did that work?"

2. **Predictive pattern recognition**: "Based on your patterns, you might be tempted to [overfunction/distance/etc]. Is that what you want?"

3. **Behavioral model articulation**: Actually telling users their implicit operating model

4. **Change tracking over time**: "Six months ago you defaulted to distance with your mother. Recently you've been engaging more directly. What shifted?"

5. **Rationale extraction**: Mining *why* they make choices, not just what they do — the implicit logic

---

## Key Conceptual Links

- **ccmemory Decision node** → **Personal App DecisionPoint node**
- **ccmemory rationale field** → **Personal App rationale_inferred (Bowen-grounded)**
- **ccmemory precedent search** → **Personal App relational precedent search**
- **ccmemory decision trace** → **Personal App behavioral pattern trace**
- **ccmemory options_considered** → **Personal App implicit_options (what could have been done)**

---

## Open Questions

1. **Extraction feasibility**: Can we reliably extract implicit decisions from natural conversation?

2. **Validation UX**: How do we confirm inferred decisions without cognitive overload?

3. **Bowen theory mapping**: How do the four mechanisms (distance, conflict, reciprocity, projection) map to decision categories?

4. **Outcome tracking**: How do we link decisions to later-reported outcomes?

5. **Temporal scope**: How far back should the system look for precedent?

---

## Source Documents Referenced

- `/Users/patrick/ccmemory/doc/UNIVERSAL_CONTEXT_GRAPH.md`
- `/Users/patrick/ccmemory/doc/IMPLEMENTATION_SPEC.md`
- `../PATTERN_INTELLIGENCE_VISION.md`
- `../../CHAT_FLOW.md`
- `../../../CONTEXT.md`

---

## Next Steps

- Await additional documents from Patrick (Iain Couzin research article, Patrick's "implicit model" presentation)
- Synthesize all source materials into unified framework
- Do not compress or lose detail until final synthesis complete