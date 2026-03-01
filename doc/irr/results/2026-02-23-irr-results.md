# IRR Results Snapshot — 2026-02-23

State of all IRR products after Meeting 2 (Sarah case, statements 1844-1846).

## Study Maturity

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Baseline | Train coders, code shared cases independently | Done (Sarah, Marcus, Jennifer) |
| 2. Calibration | Review disagreements, refine guidelines, re-code | **In progress** — 2 meetings complete |
| 3. Formal Study | Independent coding, final IRR metrics | Not started |
| 4. Integration | Validated scheme feeds AI training + new coder onboarding | Not started |

**Current position:** Early Phase 2. Two calibration meetings complete. Approximately 6 of ~20 Sarah statements reviewed (statements 1-4 in Meeting 1, statements 1844-1846 in Meeting 2). Three cases total to calibrate (Sarah, Marcus, Jennifer). No re-coding round has occurred yet.

**Coders:** Patrick (facilitator/primary coder), Laura Havstad, Kathy Jablonski, Guillermo Cancio-Bello. Laura was absent from Meeting 2 (traveling).

## Measurement Approach — Open Question

Unchanged from previous snapshot. Per-statement vs. cumulative/end-state measurement remains the most important unresolved design question. Meeting 2 added supporting evidence for cumulative approach: Kathy described the weight study's "relevant/not-relevant" underlining method and holistic assessment. Patrick observed statement-by-statement drift (coders agree on same shifts but at slightly different statements).

**Sources:** [Deliberation record Meeting 2](meetings/2026-02-23-sarah-round1-calibration-meeting2-deliberation.md), [Previous snapshot](2026-02-16-irr-results.md)

## Quantitative Metrics

### SARF Kappas

| Variable | Round 1 (pre-calibration) | Post-calibration | Target |
|----------|---------------------------|------------------|--------|
| Symptom | - | - | TBD |
| Anxiety | - | - | TBD |
| Relationship | - | - | TBD |
| Functioning | - | - | TBD |

Unchanged. No re-coding round has occurred.

## Coding Rules

14 rules now established across 2 meetings (8 from Meeting 1 + 6 new/refined from Meeting 2).

| # | Rule | Source | Unanimity | Confidence | Tested by re-coding? |
|---|------|--------|-----------|------------|---------------------|
| 1 | One shift per event, one event per atomic shift | Meeting 1, Statement 3 | Unanimous | High | No |
| 2 | Two separate shifts for different people in one statement | Meeting 1, Statement 1 | Unanimous | High | No |
| 3 | Deduplication: same timestamp + person + shift = duplicate; also no re-entry for re-mentions | Meeting 1 + Meeting 2 (reinforced) | Unanimous | High | No |
| 4 | First sibling naming → add common parent pair bond | Meeting 1, Statement 3 | Unanimous | High | No |
| 5 | Semantic similarity between description tense and timestamp | Meeting 1, Statement 4 | Unanimous | Moderate | No |
| 6 | Don't change reviewed case data | Meeting 1, process | Unanimous | High | No |
| 7 | Minimize assumptions: prefer away over distance when ambiguous | Meeting 1, Statement 4 | Majority | Moderate | No |
| 8 | Over/under functioning: automatic behavior with "wiggle room" | Meeting 1, Statement 2 | Proposed | Low | No |
| 9 | Use mechanism-specific R shift codes, not toward/away as default | Meeting 2, Statement 1844 | Unanimous (present) | Moderate | No |
| 10 | Prefer "moved" over "distance" for geographic relocations | Meeting 2, Statement 1846 | Unanimous (present) | Moderate | No |
| 11 | Geographic distance ≠ emotional distance | Meeting 2, Statement 1846 | Unanimous (present) | High | No |
| 12 | Preemptively add parents when family member first mentioned | Meeting 2, Statement 1846 | Unanimous (present) | High | No |
| 13 | Person field = actor; recipients in separate fields | Meeting 2, Statement 1844 | Unanimous (present) | High | No |
| 14 | "Same" value requires different timestamp from original shift | Meeting 2, process | Unanimous (present) | Moderate | No |

**Note:** Rules 9-14 were established with only 3 of 4 coders present (Laura absent). Laura may have different views, particularly on rule 9 (she advocated toward/away in Meeting 1).

Full rule text: [GUIDELINES.md](../GUIDELINES.md)

## Unresolved Ambiguities

### 1. Triangle vs Over/Under Functioning vs Toward/Away (updated)

**Status:** Partially resolved. Meeting 2 established that mechanism-specific codes (not toward/away) are the default, given infrastructure constraints. However, Laura (absent) was the strongest advocate for toward/away. This may resurface when she returns.

The over-functioning consensus strengthened in Meeting 2 — all three present coders agreed Sarah's over-functioning appears automatic.

**Open sub-question:** Is Michael's distance/stepping back a separate event or subsumed into the over/under functioning pattern? Guillermo raised this; not resolved.

### 2. New Shift vs Reiteration (updated)

**Status:** Clarified. Meeting 2 established that re-mentions of the same shift do not get new entries. One person + one action + one time period = one entry. Exception: genuinely different timestamp allows a new entry with "same" value.

### 3. Recipient Ambiguity

Unchanged from previous snapshot.

### 4. Statement-Level vs End-State (updated)

Kathy's weight study "relevant/not-relevant" method and Patrick's observation of statement-by-statement drift both support cumulative approach. No formal resolution yet.

### 5. Distance Subsumed into Over/Under (new)

**Statement:** 1844
**The question:** When one person is over-functioning and the other is under-functioning/stepping back, is the stepping-back person's distance a separate event or is it part of the over/under pattern?
**Positions:** Guillermo raised the question. No positions taken. Bookmarked.
**What would resolve it:** More cases with clear examples. Possibly a rule: if the distance is the reciprocal of the over-functioning (same dyad, same time), treat it as one pattern, not two events.

## Coder Status

| Coder | Cases coded | Meetings attended | Notes |
|-------|-------------|-------------------|-------|
| Patrick | Sarah, Marcus, Jennifer | 2 | Reversed his own "away" coding to over-functioning. Acknowledged infrastructure built around mechanism codes. |
| Laura | Sarah, Marcus, Jennifer | 1 (absent Meeting 2) | May disagree with rule 9 (mechanism codes as default). Her "symptom same" for mother not discussed. |
| Kathy | Sarah, Marcus, Jennifer | 2 | Corrected person field directionality errors. Accepted deduplication rule. Proposed toward/away default but accepted infrastructure argument. |
| Guillermo | Sarah, Marcus, Jennifer | 2 | Consistent over-functioning position. Raised distance-subsumed question. |

## Product Pipeline

| Link | Status | Blocker |
|------|--------|---------|
| Calibration meetings → coding rules | **Active** — 14 rules from 2 meetings | More meetings needed |
| Coding rules → GUIDELINES.md | **Active** — updated after Meeting 2 | None |
| Coding rules → AI system prompt | **Blocked** | Rules not mature enough; Laura absent for key decisions |
| Re-coding → kappa scores | **Blocked** | No re-coding round has occurred |
| Kappa scores → publication | **Blocked** | No kappas exist |
| GT coding → extraction model training data | **Blocked** | GT data quality issues |
| Validated scheme → new coder onboarding | **Blocked** | Scheme not validated |
| IRR dashboard improvements | **In progress** | Statement ID references, AI question display, name display bug |

## Next Steps

1. **Meeting 3** (2026-03-16): Continue Sarah statements. Laura expected to return.
2. **Laura alignment:** Revisit rule 9 (mechanism codes as default) with Laura present — she may advocate toward/away.
3. **Dashboard fixes:** Statement ID references, AI question display, name display bug.
4. **Kathy's corrections:** Fix edit-existing-event usage in Jennifer and Marcus codings (carryover from Meeting 1).
5. **Meeting length:** Consider extending to 90 minutes if 1-hour continues to feel rushed.
6. **Primer review:** Kathy and Guillermo to review primer document before Meeting 3.
