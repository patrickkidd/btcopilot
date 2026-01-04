# Clinical Evaluation Methodology for Personal App

**Status**: Discovery Phase - Literature Review Complete, Domain Expert Interview Required
**Last Updated**: 2026-01-03

---

## Executive Summary

This document operationalizes clinical evaluation under Bowen theory for automated AI analysis in the Personal app. It synthesizes findings from the authoritative literature (FE, FTiCP, Havstad) with the existing SARF definitions literature review to define:

1. **What clinical evaluation IS** under Bowen theory
2. **The temporal shift model** for tracking meaningful patterns
3. **Cluster detection criteria** for identifying significant periods
4. **Context linking** for connecting distant events to symptom clusters
5. **Open questions** requiring domain expert calibration

---

## Part 1: What Is Clinical Evaluation Under Bowen Theory?

### Source: FE Chapter 10 - Family Evaluation

Clinical evaluation under Bowen theory answers **ten core questions** (FE10, p. 1):

| # | Question | What It Reveals |
|---|----------|-----------------|
| 1 | Who initiated therapy? | Motivation, family dynamics |
| 2 | What is the symptom and who is symptomatic? | Presenting problem, which relationship is symptomatic |
| 3 | What is the immediate relationship system? | Nuclear family structure |
| 4 | What are the patterns of emotional functioning? | Distance, conflict, over/underfunctioning, projection |
| 5 | What is the intensity of the emotional process? | Severity of patterns |
| 6 | What influences that intensity? | Stressors AND/OR low adaptiveness |
| 7 | Nature of extended family systems? | Stability and availability |
| 8 | Degree of emotional cutoff from extended family? | Support system isolation |
| 9 | Prognosis? | Likelihood of improvement |
| 10 | Important directions for therapy? | Focus areas |

### The Five Components of Assessment

From FE Chapter 10, five variables are assessed:

1. **Stressors** - Events that disturbed emotional equilibrium
2. **Emotional Reactivity** - Level of chronic anxiety/reactivity in the family
3. **Nuclear Family Adaptiveness** - Reactivity level compared to stress level
4. **Extended Family Stability** - Functioning level and availability of extended system
5. **Emotional Cutoff** - Degree of unresolved attachment managed through distance

### Key Insight: It's About Temporal Patterns

> "Fairly exact dates of when symptoms developed or recurred are important. These dates may be found to correlate with information that is gathered later in the interview. For example, a wife's first diagnosis of rheumatoid arthritis may be found to have occurred three months after her husband's mother died." (FE10)

**Implication for AI**: Clinical evaluation requires detecting temporal correlations between events and symptoms across the timeline.

---

## Part 2: The Temporal Shift Model (Havstad)

### The Clinical Hypothesis

From Havstad Weight Loss Article:

> "The course of symptoms over time appears to be regulated to a significant degree by the family emotional system. This will be referred to here as the clinical hypothesis from Bowen theory."

### The Four Tracked Variables

Havstad operationalizes clinical evaluation as tracking **shifts in four interconnected variables**:

| Variable | Definition | How It Shifts |
|----------|------------|---------------|
| **Family System** | Patterns of relationship functioning | Nodal events, triangle movements, reciprocal position changes |
| **Anxiety (A)** | Level of chronic anxiety in subject | Up = more reactive; Down = more autonomous |
| **Functioning (F)** | Functional level of differentiation | Up = more solid self; Down = more pseudo-self |
| **Symptom (S)** | Clinical symptom status | Better, worse, remission, exacerbation |

### The Temporal Sequence

Havstad's core finding:

```
Family System Shift → Anxiety Shift → Functioning Shift → Symptom Shift
        ↑                                                      ↓
        └──────────────── (feedback loop) ────────────────────┘
```

> "Shifts in the subjects' functional level of self, along with changes in their anxiety level, often followed the shift in the family system that preceded their diet to goal weight."

### The Timeline Method

Havstad developed a method to document shifts:

1. **Identify nodal events** (births, deaths, moves, separations, illness)
2. **Track relationship pattern shifts** that follow events
3. **Document anxiety level changes** in the subject
4. **Document functioning level changes** in the subject
5. **Organize into single timeline** in chronological order
6. **Identify the KEY SHIFT** that preceded symptom change

### Critical Observation: 4-12 Week Window

> "Those subjects all gave evidence of shifts in their family system that occurred between four to twelve weeks before they initiated their successful diet effort."

**Implication for AI**: There is a typical temporal window between life events and symptomatic response. This is the "context linking" Patrick identified.

---

## Part 3: Cluster Detection

### What Makes a Period "Meaningful"?

Based on the literature, a **meaningful cluster** appears to be:

1. **A concentration of SARF shifts** - Multiple shifts in A, F, or S occurring in temporal proximity
2. **Following nodal events** - Often preceded by significant life events (within 4-12 weeks)
3. **Connected by relationship process** - Shifts that fit together as reactions to the same disturbance

### User Sampling Bias (Patrick's Observation)

Patrick noted that users tend to focus on 2-3 periods they believe are pertinent. This is consistent with the literature:

> "Evaluation of a family's functioning in response to highly stressful periods and/or evaluation of the level of stress on a family during unusually symptomatic periods provide an impression about the family's overall adaptiveness." (FE10)

Users intuitively focus on periods of high stress or high symptoms - these ARE the meaningful clusters.

### Draft Cluster Detection Criteria

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Temporal density | 3+ SARF shifts within 6 months | Multiple shifts = meaningful activity |
| Nodal event proximity | Within 12 weeks before cluster | Events trigger shifts |
| Symptom presence | At least one S shift | Symptom = why user cares |
| Relationship pattern | Identifiable mechanism (distance, conflict, etc.) | Not random; fits pattern |

**CALIBRATION NEEDED**: These thresholds are hypothesized. Patrick must validate or adjust.

---

## Part 4: Context Linking

### The "In the Wake of" Problem

Patrick identified: Deaths/births 2 years before a cluster of SARF shifts (6-month span, 1 year after the deaths/births).

From the literature, this is addressed by the concept of **stressor accumulation**:

> "The magnitude of the events, the number of events, and the time spacing between events are used to determine the level of stress a family is under." (FE10)

> "People with high basic levels can adapt to changes such as births and deaths without much alteration in functional level, but poorly differentiated people can experience a permanent drop in functional level after such events." (FE4-15)

### Why Distant Events Matter

The temporal sequence (Havstad) shows events can have **delayed effects**:

1. **Event occurs** (death, birth, divorce)
2. **Immediate acute anxiety** (may or may not show)
3. **Relationship patterns shift** to manage anxiety
4. **Chronic anxiety level adjusts** based on new patterns
5. **Functioning shifts** follow anxiety
6. **Symptoms emerge** when system can't manage

This process can take **months to years** depending on:
- Magnitude of the event
- Level of differentiation
- Whether relationship patterns were already strained
- Availability of support systems

### Draft Context Linking Rules

| Rule | Rationale |
|------|-----------|
| **Nodal events within 24 months before cluster** = potential context | Delayed effects documented |
| **Deaths in parent generation** = highest context priority | Parent relationships most influential |
| **Multiple events clustering** = higher significance | Cumulative stress documented |
| **Events in extended family** = relevant if cutoff is low | Extended family stability matters |

**CALIBRATION NEEDED**: Patrick must specify typical lag windows from clinical experience.

---

## Part 5: Observable Markers for AI Detection

### From SARF Definitions Literature Review

The existing SARF definitions provide observable markers for detecting shifts:

**F Shift UP Markers** (from [01-functioning.md](sarf-definitions/01-functioning.md)):
- I-position statements: "This is what I believe," "This is what I will do"
- Principle language over feeling language
- Staying on course despite pressure
- Self-responsibility without blame

**F Shift DOWN Markers**:
- Feeling-based decisions: "It feels right"
- Blame language
- Togetherness-seeking
- Adaptation to preserve harmony

**A Shift UP Markers** (from [02-anxiety.md](sarf-definitions/02-anxiety.md)):
- Focus on what others think, say, do
- Overload language: "overwhelmed," "isolated"
- Pursuit-distance cycles
- Escalation language: "I can't survive unless..."

**A Shift DOWN Markers**:
- Self-focus over other-focus
- Calm under pressure
- Process awareness
- Long-term thinking

**S Markers** (from [03-symptom.md](sarf-definitions/03-symptom.md)):
- Physical symptom reports
- Emotional symptom reports
- Social dysfunction reports
- Functional impairment language

### For AI Classification

The AI can detect shifts by:
1. Scanning timeline events for speech markers
2. Comparing event descriptions to marker patterns
3. Assigning shift direction (up/down/same) to each variable
4. Building cumulative shift trajectory

---

## Part 6: Theoretical Formulation

### What Is a Theoretical Formulation?

From FE Chapter 10, the formulation synthesizes the ten questions into a coherent narrative that:

1. **Explains the symptom** in terms of family process
2. **Identifies key relationship patterns** that bind anxiety
3. **Places the symptom in temporal context** relative to stressors
4. **Assesses adaptiveness** (reactivity vs stress level)
5. **Suggests focus areas** for change

### Draft Formulation Structure

```markdown
## [User's Name]'s Pattern

### Presenting Concern
[Symptom description from user's own words]

### Key Temporal Patterns
- [Event] occurred [date]. Within [timeframe], [shift] occurred.
- [Pattern] appears to be the primary mechanism for managing anxiety.

### Cluster Analysis
- **[Cluster Label]** ([date range]): [Summary of shifts]
  - Context events: [distant events that preceded]

### Functioning Assessment
- Current anxiety level: [inferred from recent shifts]
- Current functioning level: [inferred from recent shifts]
- Adaptiveness: [high stress + low reactivity = high; low stress + high reactivity = low]

### Hypotheses
- [Testable prediction about what might trigger next shift]
- [Relationship process that may be worth examining]
```

**CALIBRATION NEEDED**: Patrick must review this structure against clinical practice.

---

## Part 7: Open Questions for Domain Expert

### Questions About Cluster Detection

1. **What temporal density constitutes a cluster?** (My hypothesis: 3+ shifts in 6 months. Correct?)

2. **Can demographic events (births, deaths) form clusters, or must there be SARF shifts?**

3. **What's the minimum size of a meaningful cluster?** (Single isolated event?)

4. **How do you weight events by significance?** (Death > job change?)

### Questions About Context Linking

5. **What is the typical lag window between life events and symptomatic response?**
   - Havstad found 4-12 weeks for weight loss
   - Is this consistent for other symptoms?
   - What about longer-term effects (years)?

6. **How do you connect distant events to later clusters clinically?**
   - What cues indicate causal relationship vs coincidence?

7. **Should context events be displayed differently than cluster events in UI?**

### Questions About Formulation

8. **When you write a clinical formulation, what are the must-have elements?**

9. **What would a BAD formulation look like?** (Helps define negative space)

10. **How do you handle uncertainty in formulation?** (When patterns are unclear)

### Questions About Practical Implementation

11. **Should the AI present one interpretation or multiple hypotheses?**

12. **How much Bowen theory language should the user see?** (Technical terms vs plain language)

13. **Should users be able to edit/reject AI interpretations?**

14. **What level of confidence should block an interpretation from being shown?**

---

## Part 8: Implementation Approach

### Phase 1: Shift Detection (Can Begin)

Using existing SARF definitions, implement:
- Parse timeline events for speech markers
- Assign A, F, S shift directions to events
- Store shift metadata with events

### Phase 2: Cluster Detection (Requires Calibration)

After Patrick validates thresholds:
- Implement temporal clustering algorithm
- Add cluster labeling (AI-generated)
- Store cluster metadata

### Phase 3: Context Linking (Requires Calibration)

After Patrick specifies lag windows:
- Implement backward-looking event search
- Link context events to clusters
- Display context in UI

### Phase 4: Formulation Generation (Requires Deep Collaboration)

Requires iterative prompt development with Patrick:
- Design formulation prompt
- Test against known cases
- Iterate until clinically valid

---

## References

### Primary Sources
- **FE Chapter 10** - Family Evaluation (Kerr)
- **Havstad Weight Loss Article** - Shifts methodology
- **FE Chapter 5** - Chronic Anxiety
- **FE Chapter 7** - Nuclear Family Emotional System
- **FTiCP Chapter 9** - Use of Family Theory in Clinical Practice
- **FTiCP Chapter 21** - On the Differentiation of Self

### Existing SARF Definitions
- [btcopilot/doc/sarf-definitions/](sarf-definitions/)

---

## Session Log

### 2026-01-03 - Initial Literature Review

**Sources Read**:
- FE Chapter 10 (full chapter - ~50,000 chars)
- Havstad Weight Loss Article (full article - ~30,000 chars)
- SARF definitions: 01-functioning.md, 02-anxiety.md (excerpts)

**Key Findings**:
1. Clinical evaluation = answering 10 specific questions about family process
2. Havstad provides the operational model: timeline of shifts in family system → anxiety → functioning → symptom
3. 4-12 week window between events and response is documented
4. Cluster detection = temporal density of shifts following nodal events
5. Context linking = tracking delayed effects of stressors (up to years)

**Next Steps**:
1. Patrick to review this document
2. Schedule interview to calibrate thresholds
3. Answer open questions in Part 7
4. Iterate on formulation structure
