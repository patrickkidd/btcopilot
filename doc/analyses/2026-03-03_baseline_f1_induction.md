# Baseline F1 Induction Report

**Date**: 2026-03-03
**Task**: T7-9 — Prompt induction setup
**Data source**: Prod database dump restored to local Postgres
**Model**: Gemini 2.0 Flash (cached extractions; no live re-extraction)

---

## Environment Setup

- Prod dump: `~/.openclaw/workspace-hurin/prod.dump` (5.5MB, pg16 format)
- Restored via `pg_restore` (required libpq 18 due to pg14/pg16 version mismatch)
- Database: 2183 users, 1859 diagrams, 19 discussions, 1317 statements, 273 feedbacks
- GT export: 95 approved cases
- Evaluated: 63/95 cases (32 missing AI extractions — no `GOOGLE_GEMINI_API_KEY` for live re-extraction)

---

## Baseline F1 Scores

| Metric | F1 Score |
|--------|----------|
| **Aggregate F1** | **0.271** |
| People F1 | 0.739 |
| Events F1 | 0.180 |
| Symptom F1 | 0.286 |
| Anxiety F1 | 0.291 |
| Relationship F1 | 0.286 |
| Functioning F1 | 0.254 |

---

## Pattern Analysis

### Dominant failure pattern: People detected, Events missed

The most common pattern across statements is:
- **People F1 = 1.0** but **Events F1 = 0.0** (and all SARF = 0.0)

This occurs in ~35 of 63 evaluated statements. The model correctly identifies people mentioned in conversation but fails to extract events (shifts, relationships, structural events) associated with them.

### Cascade effect: Events F1 drives SARF scores

SARF metrics (symptom, anxiety, relationship, functioning) are only computed on **matched event pairs**. When Events F1 = 0.0, there are no matched events to evaluate SARF variables on, so all SARF scores = 0.0. This means:

> **Improving Events F1 is the single highest-leverage change.** It will directly improve all 5 other metrics.

### Statements with strong scores

A few statements score perfectly (F1 = 1.0 across all metrics): 1848, 1874, 2042. These tend to be shorter statements with clear, unambiguous clinical content.

### Statements with zero scores across all metrics

Several statements (1842, 1846, 1880, 1918, 1922, 2204) score 0.0 on everything, including People F1. These may represent edge cases where the AI extraction produced nothing or completely different content than GT.

---

## Top 3 Areas Needing Improvement

### 1. Events F1: 0.180 (CRITICAL — root cause of all low scores)

**What's failing**: The AI is not extracting events that match GT events. Event matching requires:
- Exact `kind` match (shift vs structural)
- Description similarity >= 0.40 (for shift events)
- Person/spouse/child link match
- Date proximity (within tolerance)

**Likely causes**:
- AI extracts events with different `kind` classification than GT
- AI descriptions don't match GT descriptions well enough
- AI links events to wrong people
- AI misses events entirely (low recall)

**Recommended approach**:
1. Export a few specific failing cases and compare AI vs GT event-by-event
2. Check if event `kind` classification is the main mismatch (shift vs structural confusion)
3. Add more extraction examples to `DATA_EXTRACTION_PROMPT` Section 3 covering common failure patterns
4. Tighten description guidance — the "3-5 words describing WHAT HAPPENED" rule may be too vague

### 2. Functioning F1: 0.254 (worst SARF variable)

**What's failing**: Even when events match, functioning direction coding (up/down/same) is least accurate.

**Likely causes**:
- "Functioning" is the most abstract SARF variable (work, social, self-care capacity)
- Prompt doesn't provide enough concrete examples of what constitutes functioning changes
- Model may confuse symptom changes with functioning changes

**Recommended approach**:
1. Add explicit functioning examples to extraction prompt: "Lost job" = functioning down, "Started exercising" = functioning up
2. Differentiate from symptom: symptoms are internal states, functioning is observable behavior/capacity
3. Review GT coding guidelines in `doc/irr/` for functioning-specific rules

### 3. Symptom F1: 0.286 / Relationship F1: 0.286 (tied)

**What's failing**: Symptom and relationship direction coding are similarly weak.

**Likely causes**:
- Symptom: model may not recognize indirect symptom indicators (sleep changes, appetite, somatic complaints)
- Relationship: model may fail to identify correct `relationshipTargets` (all people involved in the pattern)
- Both: small number of matched events means even one mismatch tanks the score

**Recommended approach**:
1. For symptoms: add examples of indirect symptom indicators in prompts
2. For relationships: add explicit guidance on identifying relationship patterns vs single incidents
3. For both: focus on Events F1 first — more matched events = more SARF data points = more stable SARF F1

---

## Improvement Strategy (Priority Order)

1. **Get `GOOGLE_GEMINI_API_KEY` configured** — need live re-extraction to measure impact of prompt changes on all 95 cases
2. **Fix Events extraction first** — single highest-leverage improvement, cascades to all SARF metrics
3. **Analyze specific failure cases** — export GT and compare event-by-event on worst-performing statements
4. **Iterate on extraction prompt examples** — add 3-5 new examples covering common failure patterns
5. **Tune SARF variable definitions** — after Events F1 improves, refine functioning/symptom/relationship guidance

---

## Prerequisites for Next Steps

- [ ] `GOOGLE_GEMINI_API_KEY` must be set in environment for live extraction
- [ ] Run `uv run python -m btcopilot.training.run_prompts_live --detailed` for full 95-case baseline
- [ ] Analyze specific failing statements (1842, 1846, 1916, 1918) to understand event extraction failures
