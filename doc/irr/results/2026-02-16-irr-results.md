# IRR Results Snapshot — 2026-02-16

State of all IRR products after Meeting 1 (Sarah case, statements 1-4).

## Study Maturity

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Baseline | Train coders, code shared cases independently | Done (Sarah, Marcus, Jennifer) |
| 2. Calibration | Review disagreements, refine guidelines, re-code | **In progress** — 1 meeting complete |
| 3. Formal Study | Independent coding, final IRR metrics | Not started |
| 4. Integration | Validated scheme feeds AI training + new coder onboarding | Not started |

**Current position:** Early Phase 2. One calibration meeting (4 of ~20 Sarah statements reviewed). Three more coders' worth of Sarah statements to review, plus Marcus and Jennifer cases. No re-coding round has occurred yet, so no post-calibration metrics exist.

**Coders:** Patrick (facilitator/primary coder), Laura Havstad, Kathy Jablonski, Guillermo Cancio-Bello.

## Measurement Approach — Open Question

The most important unresolved design question. Current metrics assume per-statement delta comparison, but whether that's the right level of analysis is actively under debate.

### Options

| Approach | What it measures | Status |
|----------|-----------------|--------|
| **Per-statement deltas** | Agreement on each statement's SARF coding independently | Implemented in dashboard (`/training/irr/`). All kappas showing "-" due to insufficient matched events. |
| **Cumulative/end-state** | Agreement on the resulting PDP after a full conversation | Proposed in [GT Strategy Realignment](../../plans/GT_STRATEGY_REALIGNMENT.md) Phase 2. Not implemented. |
| **Hybrid** | Per-statement for IRR study subset, cumulative for scaling | Mentioned in GT Strategy Realignment Phase 5. Not implemented. |

### Arguments

**For cumulative/end-state:**
- Laura (Meeting 1, empirical): In her prior weight loss IRR study with Kathy, "the thing that mattered in the end was was there a shift, whatever the heck it was, that affected anxiety and functioning." Statement-level mechanism labels mattered less than end-state agreement.
- Patrick (Meeting 1): "that level of granularity may be too high because there's so much variation... should I shift towards really just measuring the end state? Because the end state is really what matters."
- GT Strategy Realignment (Feb 14): Per-statement F1 on 6 prompt iterations produced scores of 0.217-0.243 — statistically indistinguishable. The metric may not be sensitive enough to differentiate quality.
- The Personal app user experience depends on cumulative PDP quality, not per-statement delta fidelity.

**For per-statement:**
- AI training requires explicit, mechanistic rules at the statement level — the extraction model produces per-statement deltas.
- Per-statement diagnostics enable debugging (which statements cause extraction failures).
- The IRR calibration meetings operate at statement level — comparing per-statement codings is what drives rule discovery.

**For hybrid:**
- Per-statement is valuable for calibration (finding disagreements) even if cumulative is the right evaluation metric.
- Could use per-statement for the IRR study subset and cumulative for scaling GT volume (5-10x faster to code).

**Status:** Under evaluation. Needs discussion and possibly prototyping of cumulative F1 before deciding.

**Sources:** [Deliberation record Theme 3](meetings/2026-02-16-sarah-round1-calibration-deliberation.md), [GT Strategy Realignment](../../plans/GT_STRATEGY_REALIGNMENT.md), [Meeting 1 notes](meetings/2026-02-16-sarah-round1-calibration-notes.md)

## Quantitative Metrics

All metrics below assume per-statement measurement. May change if the measurement approach shifts (see above).

### SARF Kappas

| Variable | Round 1 (pre-calibration) | Post-calibration | Target |
|----------|---------------------------|------------------|--------|
| Symptom | - | - | TBD |
| Anxiety | - | - | TBD |
| Relationship | - | - | TBD |
| Functioning | - | - | TBD |

Kappas show "-" because insufficient matched events exist for calculation. Coders are not yet identifying the same person + event type combinations consistently enough for the matching algorithm to pair their entries.

**Kappa target:** Not set. Group has not discussed. PRIMER.md suggests 0.6+ (Substantial) as the publishable bar, with 0.4 (Moderate) as a reasonable floor.

### Entity F1

| Metric | Sarah | Marcus | Jennifer |
|--------|-------|--------|----------|
| Average Events F1 | - | - | - |
| Average People F1 | - | - | - |

**Dashboard:** `/training/irr/` (requires auditor role)

## Coding Rules

8 rules established from Meeting 1. This is the primary concrete product so far.

| # | Rule | Source | Unanimity | Confidence | Tested by re-coding? |
|---|------|--------|-----------|------------|---------------------|
| 1 | One shift per event, one event per atomic shift | Meeting 1, Statement 3 | Unanimous | High | No |
| 2 | Two separate shifts for different people in one statement | Meeting 1, Statement 1 | Unanimous | High | No |
| 3 | Deduplication: same timestamp + person + shift = duplicate | Meeting 1, Statement 3 | Unanimous | High | No |
| 4 | First sibling naming → add common parent pair bond | Meeting 1, Statement 3 | Unanimous | High | No |
| 5 | Semantic similarity between description tense and timestamp | Meeting 1, Statement 4 | Unanimous | Moderate | No |
| 6 | Don't change reviewed case data | Meeting 1, process | Unanimous | High | No |
| 7 | Minimize assumptions: prefer away over distance when ambiguous | Meeting 1, Statement 4 | Majority (Laura, Guillermo, Patrick) | Moderate | No |
| 8 | Over/under functioning: automatic behavior with "wiggle room" | Meeting 1, Statement 2 | Proposed (not formally adopted) | Low | No |

**None have been tested by re-coding.** Until coders apply these rules to new cases independently and agreement is measured, we don't know if the rules actually improve convergence vs. just reflecting in-meeting social influence.

Full rule text: [GUIDELINES.md](GUIDELINES.md)

## Unresolved Ambiguities

These are the open questions where the group did not converge. Each represents a point where the coding scheme needs refinement.

### 1. Triangle vs Over/Under Functioning vs Toward/Away

**Statements:** 2, 3, 4
**The question:** When textual evidence supports multiple relational mechanisms simultaneously, which code to use?

**Positions:**
- **Toward/away (most conservative):** Laura, Kathy (seminar principle). Makes fewest assumptions. Avoids premature conclusions about mechanism.
- **Over/under functioning:** Patrick, Guillermo (converged during discussion). "Easy to write a rule for" — the wiggle room definition. But not formally adopted.
- **Triangle:** Guillermo (initially, then abandoned for Statements 2-3). Evidence acknowledged as present but insufficient to justify as primary code.

**What would resolve it:** More cases with clear-cut examples of each mechanism. A rule for when to "upgrade" from toward/away to a higher-inference code. Possibly Guillermo's therapeutic question heuristic: "if you're marking it over functioning, would the relevant therapeutic question be about over functioning?"

**Quality of arguments:** Extended (longest discussion of the meeting). Strong arguments on all sides. No resolution.

### 2. New Shift vs Reiteration

**Statement:** 3
**The question:** When a later statement reiterates evidence from an earlier one, does it warrant a new shift entry?

**Positions:**
- **No new shift (reiteration):** Laura revised to this view during discussion.
- **New shift (additional evidence):** Patrick saw new emotional sentiment ("I don't understand why he can't step up more") as additional triangle evidence.
- **Flip the distribution:** Guillermo proposed coding over/under in Statement 2 and triangle in Statement 3, distributing mechanisms across statements.

**What would resolve it:** A clear rule for what constitutes "new evidence" vs "reiteration." Possibly: new factual information = new event; same pattern restated = reiteration.

### 3. Recipient Ambiguity

**Statement:** 4
**The question:** When someone is moving away/distancing, who is the recipient?

**Positions:**
- Michael distancing from **Sarah** (Kathy)
- Michael distancing from **Sarah's mother** (Laura — temporally linked to diagnosis)
- Michael distancing from **both** (Patrick — used multiple recipients)

**What would resolve it:** A rule for recipient identification when evidence is ambiguous. Possibly: code all plausible recipients rather than choosing one.

### 4. Statement-Level Mechanism Precision vs End-State Agreement

**Statements:** all (meta-question)
**The question:** Does it matter if coders disagree on specific mechanism labels (triangle vs over/under) as long as they agree on the end-state (shift occurred, direction, impact on anxiety/functioning)?

**Positions:**
- **End-state matters more:** Laura (empirical evidence from weight loss study), Kathy (corroborated)
- **Statement-level needed for AI training:** Patrick (vertical alignment constraint)
- **Unresolved tension** between human evaluation needs and AI training needs

**What would resolve it:** Implementing cumulative F1 and comparing it to per-statement F1. If cumulative agreement is high while per-statement is low, that validates Laura's empirical observation.

## Coder Status

| Coder | Cases coded | Meetings attended | Notes |
|-------|-------------|-------------------|-------|
| Patrick | Sarah, Marcus, Jennifer | 1 | Facilitator. Most experience operationalizing SARF. Acknowledged conformity risk: "It's really easy to agree with me." |
| Laura | Sarah, Marcus, Jennifer | 1 | Empirical IRR experience (weight loss study). Proposed toward/away as conservative default. Finished Sarah coding the night before meeting 1. Traveling for Meeting 2. |
| Kathy | Sarah, Marcus, Jennifer | 1 | Steepest learning curve — coded Sarah while still learning mechanics. Discovered two-pass worksheet method for later cases. Needs to fix edit-existing-event usage in Jennifer and Marcus. |
| Guillermo | Sarah, Marcus, Jennifer | 1 | Started improving after Sarah. Proposed therapeutic question heuristic for mechanism selection. |

All four coders acknowledged Sarah was their first case and a learning exercise. Kathy explicitly described it as "throwaway" learning. Guillermo: "I started getting better after Sarah." The real test is Marcus and Jennifer.

## Product Pipeline

How IRR outputs feed downstream systems.

| Link | Status | Blocker |
|------|--------|---------|
| Calibration meetings → coding rules | **Active** — 8 rules from 1 meeting | More meetings needed |
| Coding rules → GUIDELINES.md | **Active** — updated after Meeting 1 | None |
| Coding rules → AI system prompt | **Blocked** | Rules not mature enough; measurement approach unresolved |
| Re-coding → kappa scores | **Blocked** | No re-coding round has occurred |
| Kappa scores → publication | **Blocked** | No kappas exist |
| GT coding → extraction model training data | **Blocked** | GT data quality issues ([GT Strategy Realignment](../../plans/GT_STRATEGY_REALIGNMENT.md) Phase 1) |
| Validated scheme → new coder onboarding | **Blocked** | Scheme not validated |

**Cross-reference:** [GT Strategy Realignment](../../plans/GT_STRATEGY_REALIGNMENT.md) — addresses the GT data quality and metric-goal alignment issues that also affect IRR.

## Next Steps

1. **Meeting 2** (2026-02-23): Continue Sarah statements. Attendees: Patrick, Kathy, Guillermo (Laura traveling).
2. **Kappa target discussion:** Group needs to set a target. Suggest discussing at Meeting 2 or 3.
3. **Measurement approach evaluation:** Prototype cumulative F1 (GT Strategy Realignment Phase 2) to compare against per-statement metrics before committing to one approach for the IRR study.
4. **Kathy's corrections:** Fix edit-existing-event usage in Jennifer and Marcus codings.
5. **Re-coding round:** After calibration meetings complete for Sarah, re-code independently to test whether rules improved agreement.
6. **Dashboard improvements:** Side-by-side coder comparison for calibration meetings.
