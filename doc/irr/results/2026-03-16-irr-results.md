# IRR Results Snapshot — 2026-03-16

State of all IRR products after Meeting 3 (Sarah case, tools review & calibration).

## Study Maturity

| Phase | Description | Status |
|-------|-------------|--------|
| 1. Baseline | Train coders, code shared cases independently | Done (Sarah, Marcus, Jennifer) |
| 2. Calibration | Review disagreements, refine guidelines, re-code | **In progress** — 3 meetings complete |
| 3. Formal Study | Independent coding, final IRR metrics | Not started |
| 4. Integration | Validated scheme feeds AI training + new coder onboarding | Not started |

**Current position:** Phase 2. Three calibration meetings complete on one case (Sarah). Approximately 6 of ~20 Sarah statements reviewed in meetings 1-2. Meeting 3 focused on tools review rather than statement-by-statement comparison. Round 2 cases (Arthur, Dominic, Cassandra, Robert) available for coding — Arthur assigned as next case. No re-coding round has occurred yet.

**Coders:** Patrick (facilitator/primary coder), Laura Havstad, Kathy Jablonski, Guillermo Cancio-Bello. All four present for Meeting 3.

## Measurement Approach — Partially Resolved

**Meeting 3 advancement:** Patrick concluded cumulative timeline comparison is the primary comparison unit. Statement-by-statement data entry is needed for workflow, but calibration review should focus on whether coders produce the same cumulative timeline. This aligns with AI extraction behavior (full-conversation extraction outperforms statement-by-statement). The new AI calibration tool supports this by detecting underlying constructs across coders regardless of which statement they coded them at.

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

14 coding rules + 2 process rules established across 3 meetings.

| # | Rule | Source | Unanimity | Confidence | Tested by re-coding? |
|---|------|--------|-----------|------------|---------------------|
| 1 | One shift per event, one event per atomic shift | Meeting 1, Statement 3 | Unanimous | High | No |
| 2 | Two separate shifts for different people in one statement | Meeting 1, Statement 1 | Unanimous | High | No |
| 3 | Deduplication: same timestamp + person + shift = duplicate; no re-entry for re-mentions | Meeting 1 + Meeting 2 + Meeting 3 (Laura aligned) | Unanimous | High | No |
| 4 | First sibling naming → add common parent pair bond | Meeting 1, Statement 3 | Unanimous | High | No |
| 5 | Semantic similarity between description tense and timestamp | Meeting 1, Statement 4 | Unanimous | Moderate | No |
| 6 | Don't change reviewed case data | Meeting 1, process | Unanimous | High | No |
| 7 | Minimize assumptions: prefer away over distance when ambiguous | Meeting 1, Statement 4 | Majority | Moderate | No |
| 8 | Over/under functioning: automatic behavior with "wiggle room" | Meeting 1, Statement 2 | Proposed | Low | No |
| 9 | Use mechanism-specific R shift codes, not toward/away as default | Meeting 2, Statement 1844 | Unanimous (3 present) | Moderate | No |
| 10 | Prefer "moved" over "distance" for geographic relocations | Meeting 2, Statement 1846 | Unanimous (3 present) | Moderate | No |
| 11 | Geographic distance ≠ emotional distance | Meeting 2, Statement 1846 | Unanimous (3 present) | High | No |
| 12 | Preemptively add parents when family member first mentioned | Meeting 2, Statement 1846 | Unanimous (3 present) | High | No |
| 13 | Person field = actor; recipients in separate fields | Meeting 2, Statement 1844 | Unanimous (3 present) | High | No |
| 14 | "Same" value requires different timestamp from original shift | Meeting 2, process | Unanimous (3 present) | Moderate | No |

**Process rules (methodology, not in GUIDELINES.md):**
- Blind coding protocol: complete own coding before using AI lit review tool (Meeting 3)
- Cumulative timeline as primary comparison unit for calibration review (Meeting 3)

**Note:** Rules 9-14 were established with only 3 of 4 coders present (Laura absent Meeting 2). Laura was present for Meeting 3 and aligned on deduplication (rule 3) but did not revisit rules 9-14 explicitly.

Full rule text: [GUIDELINES.md](../GUIDELINES.md)

## Unresolved Ambiguities

### 1. Triangle vs Over/Under Functioning vs Toward/Away (updated)

**Status:** Partially resolved. Rule 9 established mechanism-specific codes as default. Laura present for Meeting 3 but did not challenge this directly. AI lit review tool validated over-functioning coding for Sarah against FE 218, 224.

### 2. Distance vs Conflict (updated via AI tool)

AI calibration tool analysis sided with distance over conflict for Michael: "Michael's behavior, avoiding it all, is the opposite of engagement. It is the cessation of the fight through withdrawal." Cited FE 677, 681. Laura noted "stepping back" is ambiguous — can mean anxiety-driven distancing or thoughtful detachment. Not formally resolved by the group.

### 3. New Shift vs Reiteration (updated)

Clarified in Meeting 2, Laura aligned in Meeting 3. Rule is firm: one delta per construct per time period. Kathy's weight study observation (frequency = emotional salience) acknowledged as a separate valid insight but not grounds for duplicate deltas.

### 4. Statement-Level vs End-State (partially resolved)

Cumulative timeline established as primary comparison unit in Meeting 3. Statement-by-statement still needed for data entry but calibration focuses on cumulative results.

### 5. Distance Subsumed into Over/Under

Unchanged from Meeting 2. Still bookmarked.

### 6. Recipient Ambiguity

Unchanged.

## AI Tools Status (new)

| Tool | Status | Assessment |
|------|--------|------------|
| AI calibration report (discussion-level) | Introduced Meeting 3 | Construct detection "pretty reliable"; event linking bugs, may duplicate entries |
| AI lit review (per-event) | Introduced Meeting 3 | Concept accuracy good, citation precision approximate ("half right") |
| Timeline comparison | Introduced Meeting 3 | Functional; Patrick and Laura had highest agreement on Sarah |

**AI-generated language concern:** Tool produced "emotional insulation" — Laura flagged as unfamiliar. Group decided not to constrain AI language; traceable source passages are what matter.

## Coder Status

| Coder | Cases coded | Meetings attended | Notes |
|-------|-------------|-------------------|-------|
| Patrick | Sarah, Marcus, Jennifer, Arthur, Dominic, Cassandra | 3 | Already coded 3 round-2 cases blind. Concluded cumulative > statement-by-statement. |
| Laura | Sarah, Marcus, Jennifer | 3 (absent Meeting 2) | Aligned on deduplication. Noted "stepping back" ambiguity. Hasn't coded round-2 cases yet. |
| Kathy | Sarah, Marcus, Jennifer | 3 | Advocated blind coding protocol. Preserved Sarah coding per "don't change reviewed data" rule. |
| Guillermo | Sarah, Marcus, Jennifer | 3 | Praised Arthur case quality: "like listening to real conversations." |

## Product Pipeline

| Link | Status | Blocker |
|------|--------|---------|
| Calibration meetings → coding rules | **Active** — 14 rules from 3 meetings | More meetings needed |
| Coding rules → GUIDELINES.md | **Active** — updated after Meeting 2 | None |
| Coding rules → AI system prompt | **Blocked** | Rules not mature enough |
| Re-coding → kappa scores | **Blocked** | No re-coding round has occurred |
| Kappa scores → publication | **Blocked** | No kappas exist |
| AI calibration tool | **In progress** | Event linking bugs, R variable display |
| AI lit review tool | **In progress** | Citation precision, AI-generated language |
| Timeline comparison tool | **In progress** | May duplicate entries |

## Next Steps

1. **All coders: code Arthur blind** before Meeting 4 (March 30)
2. **Meeting 4** (March 30): Arthur case — first blind coding comparison on round-2 case
3. **Tool bug fixes:** Calibration report event linking, R variable display, entry deduplication
4. **Consent forms:** Patrick to send to Kathy and Guillermo
5. **Florida conference video:** Forward to Laura and Kathy
