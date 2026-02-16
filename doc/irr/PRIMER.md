# IRR Primer

What we're doing, why it matters, and how the process works.

## The Big Picture

We all just coded the same clinical case independently. Now we compare
notes. Where we agree, great. Where we disagree, we talk it through and
figure out why.

The disagreements aren't mistakes -- they're where the coding guidelines
aren't clear enough yet. Every disagreement we resolve makes the system
sharper. That's the whole point.

## Why This Matters

If four trained people can read the same session and arrive at the same
coding, that's strong evidence the scheme works. If they can't, the
scheme needs refinement. Either outcome is useful -- one validates the
tool, the other tells us exactly what to fix.

This process is also what makes our findings publishable. Reviewers will
ask "how do you know your coders agree?" and we need a real answer.

## What We're Coding

Each statement in a session might contain evidence of a shift in one or
more of four variables:

| | Variable | What we're listening for |
|-|----------|------------------------|
| **S** | Symptom | Physical or emotional symptoms getting better or worse |
| **A** | Anxiety | Stress response rising or falling |
| **R** | Relationship | A relationship pattern showing up (conflict, distance, etc.) |
| **F** | Functioning | Someone's ability to think clearly under pressure changing |

For S, A, and F we code a direction: **up**, **down**, or **same**.
For R we name the pattern: Conflict, Distance, Cutoff, Overfunctioning,
Underfunctioning, Projection, Inside, Outside, DefinedSelf, Toward,
Away, or Fusion.

Key rule: only code when there's actual evidence. No evidence = nothing
to code. Silence is not "same."

## How Calibration Works

1. **Code independently** -- everyone codes the same case on their own
2. **Compare** -- look at where we coded differently
3. **Meet** -- discuss the disagreements, hear each other's reasoning
4. **Write it down** -- document any rules we agree on
5. **Re-code if needed** -- apply the new rules, see if agreement improves
6. **Repeat** -- until we're consistently landing in the same place

The goal is not to make everyone think the same way. It's to make the
guidelines precise enough that four reasonable clinicians reach the same
conclusions from the same evidence.

## Where We Expect to Disagree

These are the kinds of questions that come up in every calibration:

- **"Is that a symptom or anxiety?"** -- They overlap. Stomach pain during
  a stressful story could be either. We need a rule for when it's one
  vs the other vs both.
- **"Is that distance or cutoff?"** -- Similar patterns, different
  intensity. Where's the line?
- **"Does this statement have enough to code anything?"** -- Threshold
  questions. One person's "clearly anxious" is another's "not enough info."
- **"Is this one event or two?"** -- Someone describes conflict with mom
  and distance from dad in the same breath. One code or two?
- **"Which direction?"** -- "Things got worse" could mean functioning
  went down, anxiety went up, or both.

These are exactly the questions we want to surface. The rules we write
from resolving them become the coding guidelines.

## What "Good Agreement" Looks Like

We'll measure agreement with a statistic called **kappa** (see reference
section below). The short version:

- Kappa corrects for luck. Raw percent agreement is misleading because
  some agreement happens by chance.
- Kappa runs from -1 to 1. Zero means "no better than random." One means
  "perfect agreement."
- For clinical coding like ours, landing above **0.6** is a strong
  result. Many published instruments are in the 0.5 - 0.7 range.

We haven't set a formal target yet -- that's something for the group to
discuss. The calibration process itself will show us what's realistic.

---

## Reference: Statistics and Terms

Technical details for when you want them. Not required reading for meetings.

### Cohen's Kappa (two coders)

Measures agreement between a pair of coders, corrected for chance.

Raw agreement ("we agreed 80% of the time") is misleading because some
agreement happens by luck. If there are only two options and both coders
pick randomly, they'll agree ~50% of the time. Kappa removes that luck
factor.

- kappa = 1.0 -- perfect agreement
- kappa = 0.0 -- agreement no better than coin flipping
- kappa < 0 -- actively disagreeing (worse than random)

### Fleiss' Kappa (three or more coders)

Same idea as Cohen's but works for groups. Since we have four coders,
this is our primary metric.

### The Landis & Koch Scale

The standard interpretation (1977), used universally in clinical research:

| Kappa | Interpretation |
|-------|----------------|
| 0.81 - 1.00 | Almost Perfect |
| 0.61 - 0.80 | Substantial |
| 0.41 - 0.60 | Moderate |
| 0.21 - 0.40 | Fair |
| 0.00 - 0.20 | Slight |
| < 0.00 | Poor (worse than chance) |

For reference, many published clinical coding instruments land in the
0.5 - 0.7 range. Getting above 0.6 with a new scheme is a solid result.

### F1 Score

Before we can measure agreement on SARF variables, we need to know
whether coders even found the same things. F1 measures entity-level
agreement: did we identify the same people, the same events?

Think of it as two questions combined:
- **Precision**: Of the events I found, how many did you also find?
- **Recall**: Of the events you found, how many did I also find?

F1 is the harmonic mean of those two. It ranges from 0 (no overlap) to
1 (perfect match). F1 must be reasonable before kappa means anything.

### Our Target

**TBD** -- to be discussed as a group. Factors to consider:

- Clinical judgment coding is inherently harder than binary classification
- 0.4 (Moderate) is a reasonable floor to keep iterating
- 0.6+ (Substantial) is the standard bar for publishable clinical schemes
- 0.8+ (Almost Perfect) is aspirational and rare for nuanced coding
- The target may differ by variable (Relationship is harder than Symptom)

### Glossary

| Term | Plain English |
|------|---------------|
| **IRR** | Inter-Rater Reliability -- how much coders agree |
| **Kappa** | Agreement score, corrected for chance |
| **F1** | Did we find the same events? |
| **Calibration** | Meeting to discuss disagreements and write rules |
| **Ground truth** | The "correct" coding, established by group consensus |
| **Delta** | What changed in a single statement (sparse, not cumulative) |
| **Cumulative** | Everything coded up to a given point in the session |
| **SARF** | Symptom, Anxiety, Relationship, Functioning |

---

## Independence, Diversity, and Validity

This section covers the theoretical foundation for *how* we work
together in calibration. It draws on collective intelligence research
and Bowen family systems theory. Understanding these ideas will help us
get more out of the process and avoid common pitfalls.

### Why disagreement is valuable

The instinct in calibration is to eliminate disagreement as fast as
possible. But disagreement between coders who bring different
perspectives is not noise -- it is information about where the coding
scheme is ambiguous or where clinical judgment genuinely diverges.

Research on collective intelligence shows that groups produce more
accurate and more valid judgments when members maintain diverse
perspectives and think independently before aggregating their views
(Surowiecki, 2004; Page, 2007). Hong and Page (2004) demonstrated
formally that groups of diverse problem solvers can outperform groups of
individually high-ability solvers -- not because diversity feels good,
but because different frameworks catch different things.

This means that the diversity in our group -- different levels of
clinical experience, different depths of theoretical knowledge, different
orientations toward operationalizing concepts -- is not a limitation to
be overcome. It is what makes the resulting coding scheme *more valid*
than any one person's version would be. When coders with genuinely
different vantage points converge on the same code, that convergence
carries far more weight than agreement among people who all think the
same way.

### How social influence undermines the process

The same research shows that collective accuracy collapses when
independence breaks down. Lorenz, Rauhut, Schweitzer, and Helbing (2011)
found that when group members learned each other's estimates during the
process, the diversity of opinion narrowed without improving accuracy --
the group became more confident but not more correct. Social influence
replaced independent judgment.

In a calibration meeting, this can happen through:

- **Anchoring**: The first person to state their code sets the frame.
  Others evaluate their own position relative to that anchor rather than
  on its own merits.
- **Authority effects**: When the most experienced or senior member
  speaks first, less experienced members may defer rather than genuinely
  evaluate.
- **Conformity pressure**: The discomfort of being the only person who
  coded something differently can drive people to abandon positions they
  actually believe in.

The risk is that calibration produces high kappa that reflects social
conformity rather than genuine convergence on the clinical material. That
kind of agreement would not replicate with new coders who weren't in the
room.

### Differentiation of self as the mechanism

Bowen family systems theory offers a precise framework for understanding
what it takes to maintain independent judgment within a group. Bowen
(1978) described **differentiation of self** as the capacity to maintain
one's own thinking and functioning while remaining in meaningful
emotional contact with others. Kerr and Bowen (1988) further
distinguished between the intellectual system (principled positions
based on careful thought) and the emotional system (automatic responses
to anxiety and togetherness pressure).

In a calibration meeting, the emotional system is active. There is
anxiety about being wrong, pressure to agree, and the natural pull of
togetherness. The less differentiated response is to resolve that
tension automatically -- either by fusing with the group position
(shifting to match the majority without genuinely updating one's
clinical judgment) or by reactively opposing (digging in because it
feels like pressure, not because the evidence supports the position).

The more differentiated response is to stay in contact with the group's
reasoning while maintaining the capacity to evaluate it on its merits.
This means genuinely updating when someone else's reasoning reveals
something you missed, and genuinely holding your position when it
doesn't -- with the distinction being driven by the clinical evidence,
not by who said it or how much pressure you feel.

### Complementary expertise and productive tension

Our group includes members with deep theoretical and clinical
backgrounds alongside members with strong technical and operational
orientations. These are genuinely different ways of engaging with the
same material, and they produce different kinds of insight.

Conceptual depth helps identify what a clinical moment *is* -- what
pattern is actually present in the therapeutic material. Technical
operationalization asks how to translate that recognition into a
consistent, reproducible code -- what rules would let someone who wasn't
in the room arrive at the same answer.

These contributions are complementary, and the tension between them is
productive. A coding scheme needs both: theoretical fidelity (it
captures real clinical phenomena) and operational clarity (different
people apply it the same way). Neither perspective alone produces a
valid scheme. The disagreements that arise from these different
orientations are often the most valuable ones to work through, because
they reveal where the scheme is theoretically sound but operationally
ambiguous, or operationally clean but clinically imprecise.

### Practical implications for meetings

- **Code independently first, always.** Independence must be established
  before any discussion. Once you know how someone else coded a
  statement, you cannot un-know it.
- **Hear from each coder before opening discussion.** Go around the
  table on each disagreement. This prevents anchoring and ensures every
  perspective is on record before social influence begins.
- **Distinguish updating from deferring.** "Your reasoning changed my
  mind" is different from "I don't want to be the only one who
  disagrees." Both feel like agreement, but only the first one is real.
- **The re-coding test is the real measure.** After calibration, code
  the next case independently. If kappa improves when everyone is
  working alone, the guidelines actually got clearer. If agreement only
  holds during group discussion, what improved was conformity, not the
  scheme.
- **Protect the less experienced coders' independence.** Members with
  less experience are more susceptible to anchoring and authority
  effects. Their independent perspective is especially valuable
  precisely because it tests whether the guidelines are clear enough for
  someone without deep background to apply correctly.
- **Welcome the disagreements that come from different expertise.**
  When a theoretically-grounded reading clashes with an operationally-
  oriented one, that is where the most important coding rules get
  written.

### References

Bowen, M. (1978). *Family therapy in clinical practice*. Jason Aronson.

Hong, L., & Page, S. E. (2004). Groups of diverse problem solvers can
    outperform groups of high-ability problem solvers. *Proceedings of
    the National Academy of Sciences, 101*(46), 16385-16389.

Kerr, M. E., & Bowen, M. (1988). *Family evaluation*. Norton.

Lorenz, J., Rauhut, H., Schweitzer, F., & Helbing, D. (2011). How
    social influence can undermine the wisdom of crowd effect.
    *Proceedings of the National Academy of Sciences, 108*(22),
    9020-9025.

Page, S. E. (2007). *The difference: How the power of diversity creates
    better groups, firms, schools, and societies*. Princeton University
    Press.

Surowiecki, J. (2004). *The wisdom of crowds*. Doubleday.
