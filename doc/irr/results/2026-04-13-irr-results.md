# IRR Results Snapshot — 2026-04-13

State of all IRR products after Meeting 5 (Arthur case, statements 7-8 + 2192 partial).

## Study Maturity

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Baseline | Train coders, code shared cases independently | Done (Sarah, Marcus, Jennifer, Arthur) |
| 2. Calibration | Review disagreements, refine guidelines, re-code | **In progress** — 5 meetings complete |
| 3. Formal Study | Independent coding, final IRR metrics | Not started |
| 4. Integration | Validated scheme feeds AI training + new coder onboarding | Not started |

**Current position:** Phase 2. Five calibration meetings complete across two cases (Sarah: 3 meetings, Arthur: 2 meetings). Arthur case in progress — statements 1-8 and partially 2192 reviewed. Statement 2192 to continue in Meeting 6. No re-coding round has occurred yet.

**Coders:** Patrick (facilitator/primary coder), Laura Havstad, Kathy Jablonski, Guillermo Cancio-Bello. Guillermo absent from Meeting 5.

## Measurement Approach — Partially Resolved

**Resolved in Meeting 3:** Cumulative timeline comparison is the primary comparison unit. Statement-by-statement data entry is needed for workflow, but calibration review focuses on whether coders produce the same cumulative timeline. AI calibration tool supports this by detecting underlying constructs across coders regardless of which statement they coded them at.

**Remaining question:** How to handle timing differences when coders agree on the same shift but code it at different statements.

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

23 coding rules + 2 process rules established across 5 meetings.

**Process rules (methodology, not in GUIDELINES.md):**
- Blind coding protocol: complete own coding before using AI lit review tool (Meeting 3)
- Cumulative timeline as primary comparison unit for calibration review (Meeting 3)

| # | Rule | Source | Unanimity | Confidence | Tested by re-coding? |
|---|------|--------|-----------|------------|---------------------|
| 1 | One shift per event, one event per atomic shift | Meeting 1 | Unanimous | High | No |
| 2 | Two separate shifts for different people in one statement | Meeting 1 | Unanimous | High | No |
| 3 | Deduplication: same timestamp + person + shift = duplicate; no re-entry for re-mentions | Meetings 1-3 (Laura aligned M3) | Unanimous | High | No |
| 4 | First sibling naming → add common parent pair bond | Meeting 1 | Unanimous | High | No |
| 5 | Semantic similarity between description tense and timestamp | Meeting 1 | Unanimous | Moderate | No |
| 6 | Don't change reviewed case data | Meeting 1 | Unanimous | High | No |
| 7 | Minimize assumptions: prefer away over distance when ambiguous | Meeting 1 | Majority | Moderate | No |
| 8 | Over/under functioning: automatic behavior with "wiggle room" — reality-driven vs emotionally-driven | Meetings 1, 5 (reinforced) | Unanimous (present) | Moderate | No |
| 9 | Use mechanism-specific R shift codes, not toward/away as default | Meeting 2 | Unanimous (3 present) | Moderate | No |
| 10 | Prefer "moved" over "distance" for geographic relocations | Meeting 2 | Unanimous (3 present) | Moderate | No |
| 11 | Geographic distance ≠ emotional distance | Meeting 2 | Unanimous (3 present) | High | No |
| 12 | Preemptively add parents when family member first mentioned | Meeting 2 | Unanimous (3 present) | High | No |
| 13 | Person field = actor; recipients in separate fields | Meeting 2 | Unanimous (3 present) | High | No |
| 14 | "Same" value requires different timestamp from original shift | Meeting 2 | Unanimous (3 present) | Moderate | No |
| 15 | Spouse pair bond: when spouse first mentioned, add marriage event | Meeting 4 | Unanimous | High | No |
| 16 | Functioning down indicators: "unsure of oneself," frozen, impaired attention | Meeting 4 | Unanimous | High | No |
| 17 | Anxiety-functioning reciprocity: both can co-occur, different variables | Meeting 4 | Unanimous | High | No |
| 18 | Date placeholders: year-only → Jan 1st; month known → month-01 | Meeting 4 | Unanimous | High | No |
| 19 | Symptom = functional breakdown, not behavior/sensitivity/reactivity | Meeting 5 | Unanimous (3 present) | High | No |
| 20 | Baseline vs shift: "always been X" = baseline (code once, unknown date). Shifts need timestamps. | Meeting 5 | Unanimous (3 present) | High | No |
| 21 | Structural events (birth/death/marriage) ≠ SARF shifts. Track separately. | Meeting 5 | Unanimous (3 present) | High | No |
| 22 | Functional facts (occupation, education, health, location) are not shifts | Meeting 5 | Unanimous (3 present) | High | No |
| 23 | No functioning coding for infants | Meeting 5 | Unanimous (3 present) | High | No |

Full rule text: [GUIDELINES.md](../GUIDELINES.md)

## Unresolved Ambiguities

### 1. Conflict vs. Distance — Operational Definitions (major)

**Status:** Unresolved across Meetings 4-5. Laura: conflict = any resistance (including passive/Cold War). Distance = true avoidance/disengagement. Patrick: not sure Arthur is engaging. AI lit review tool (Meeting 3) sided with distance, citing FE 677, 681. No new evidence in Meeting 5.

### 2. Defined Self — Scope and Inference Threshold

**Status:** Unresolved from Meeting 4. Laura alone in coding it.

### 3. Symptom vs. Anxiety Boundary (partially resolved)

**Status:** Meeting 5 narrowed symptom significantly. Sensitivity/reactivity = anxiety. Symptom = breakdown point where anxiety exceeds functioning capacity. Kathy's broadened usage retracted. Remaining question: where exactly is the threshold? Laura's alcohol analogy (drinking isn't a symptom unless it interferes with functioning) provides a heuristic but edge cases remain.

### 4. Face-Value Reporting

**Status:** Unresolved from Meeting 4.

### 5. Baseline vs. Shift Coding (new — partially resolved)

**Statement:** 2192 (Arthur case)
**The question:** When someone describes a lifelong characteristic ("always been sensitive"), is that a SARF shift or a baseline?
**Resolution:** Baseline descriptions are NOT shifts. Code once with unknown date certainty. But if evidence shows the baseline changed permanently at a specific event, that IS a timestamped shift. Example: Sylvia's sensitivity fluctuated, then "when Claire was born, that shift became permanent" — valid shift to new basic level. Novel insight that none of the coders initially captured.

### 6. Functional Facts Data Model Gap (new)

Laura identified that Bowen's multigenerational functioning markers (occupation, education, health, location) have no proper home in the current coding system. These are important for tracking multigenerational process but don't fit as SARF shifts. Currently tracked via person/event notes. Needs a data model solution long-term.

### 7. Triangle vs Over/Under Functioning vs Toward/Away

Partially resolved. Rule 9 established mechanism-specific codes as default. Not challenged in Meetings 4-5.

### 8. Distance Subsumed into Over/Under

Unchanged from Meeting 2. Still bookmarked.

### 9. Recipient Ambiguity

Unchanged.

## AI Tools Status

| Tool | Status | Last tested |
|------|--------|------------|
| AI calibration report (discussion-level) | In progress | Meeting 3 (Sarah) |
| AI lit review (per-event) | In progress | Meeting 3 (Sarah) |
| Timeline comparison | In progress | Meeting 3 (Sarah) |
| AI summary column (IRR comparison page) | Not started | Patrick started but got sidetracked |

## Coder Status

| Coder | Cases coded | Meetings attended | Notes |
|-------|-------------|-------------------|-------|
| Patrick | Sarah, Marcus, Jennifer, Arthur, Dominic, Cassandra | 5 | Articulated structure vs function distinction. Engineering FMEA analogy for symptom. |
| Laura | Sarah, Marcus, Jennifer, Arthur | 4 (absent Meeting 2) | Drove symptom narrowing, baseline vs shift distinction. Found Rackauer 2022 FSJ article (30 variables). Pruned her Arthur coding before Meeting 5. |
| Kathy | Sarah, Marcus, Jennifer, Arthur | 5 | Retracted broadened symptom usage. Added to TestFlight. Learning repository navigation. |
| Guillermo | Sarah, Marcus, Jennifer, Arthur | 4 (absent Meeting 5) | No update this meeting. |

## Product Pipeline

| Link | Status | Blocker |
|------|--------|---------|
| Calibration meetings → coding rules | **Active** — 23 rules from 5 meetings | More meetings needed |
| Coding rules → GUIDELINES.md | **Active** — updated after Meeting 5 | None |
| Coding rules → AI system prompt | **Blocked** | Rules not mature enough; major ambiguities remain |
| Re-coding → kappa scores | **Blocked** | No re-coding round has occurred |
| Kappa scores → publication | **Blocked** | No kappas exist |
| AI calibration tool | **In progress** | Event linking bugs (Meeting 3) |
| AI lit review tool | **In progress** | Citation precision approximate |
| Timeline comparison tool | **In progress** | May duplicate entries |
| AI summary column | **Not started** | Patrick sidetracked |
| Functional facts data model | **Not started** | Identified Meeting 5 — needs design |

## Next Steps

1. **Meeting 6** (2026-04-27): Continue Arthur Statement 2192 and beyond.
2. **Functional facts:** Design approach for occupation/education/health/location markers in data model.
3. **Bowen archives:** Laura to look for 30 variables of differentiation (Rackauer 2022 FSJ reference).
4. **AI summary column:** Patrick to finish per-statement summary column on IRR comparison page.
5. **Guillermo re-engagement:** Ensure he attends Meeting 6.
