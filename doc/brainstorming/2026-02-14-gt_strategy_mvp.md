# GT Strategy: Metric-Goal Alignment for MVP

## Date: 2026-02-14

## Context

Brainstorming session analyzing whether the current GT coding strategy (per-statement delta coding → per-statement F1) effectively targets the MVP user experience goal (useful cumulative PDP in Learn view after "accept all").

## Current State

- **GT volume**: 45 approved feedbacks across 3 discussions (1,135 total statements, 4 auditors, 0 exports)
- **Coding workflow**: Per-statement delta editing in SARF editor (people, events, pair bonds, SARF variables, relationship targets/triangles, deletes)
- **Metric**: Per-statement micro/macro F1 with fuzzy entity matching
- **IRR study**: Insufficient matched events for kappa calculation
- **Learn view**: SARF graphs + event timeline + AI-driven clusters (Gemini). Consumes committed events from accepted PDP.
- **Guide/Plan view**: Placeholder only

## Core Problem: Metric-Goal Misalignment

Per-statement F1 measures extraction fidelity per utterance. The user experience depends on cumulative PDP quality after a full conversation. These diverge because:

1. **Temporal allocation mismatch**: AI and GT coder may extract the same entity at different statements → penalized as FP+FN even though cumulative result is identical
2. **Delta granularity noise**: Intermediate deltas that get superseded inflate FP/FN without affecting end result
3. **ID matching brittleness**: Fuzzy thresholds (name 0.6, description 0.4, date 7-day) introduce noise at statement level that washes out cumulatively
4. **SARF F1 built on noisy event matching**: Variable accuracy only computed on matched events, which is itself noisy

**Result**: F1 scores contain substantial noise from delta-level evaluation that doesn't reflect actual UX quality. Can't distinguish "mediocre extraction" from "fine extraction with messy per-statement alignment."

## Throughput Bottleneck

Per-statement coding is 4-8+ hours per discussion. At current rate, "100+ expert-validated conversations" is unreachable on any MVP timeline. IRR can't compute kappas. Prompt improvement cycle has never completed (zero exports).

## Options Considered

### A: Conversation-Level Cumulative GT
Code expected cumulative PDP after reading whole conversation. One pass per discussion.
- 5-10x faster to code
- Directly measures what user sees
- Loses per-statement diagnostics, streaming evaluation, per-statement IRR

### B: Two-Tier GT (Recommended)
- **Tier 1**: Cumulative GT for many conversations (primary metric, high volume)
- **Tier 2**: Per-statement delta GT for small subset (IRR study, streaming diagnostics)

### C: Acceptance-Based GT
Run AI, have experts review/correct resulting cumulative PDP. Grade entities as correct/incorrect/missing.
- Fastest coding workflow
- Doesn't produce structured GT for fine-tuning
- Metric: precision/recall on entities

### D: End-to-End UX Evaluation
Evaluate Learn view directly (SARF graph correctness, cluster quality, entity presence).
- Measures actual user experience
- Subjective, hard to automate, conflates extraction with clustering

## Proposed New Metric: Cumulative F1

After processing all statements in a conversation, compare AI cumulative PDP vs. expert expected cumulative PDP using existing entity matching logic. Small code change (run matching on cumulative instead of per-statement).

Eliminates:
- False negatives from temporal allocation mismatch
- False positives from superseded intermediate states
- ID assignment noise amplified across statements

## Risks

1. Cumulative GT still requires substantial coding (10-20 people, 30-50 events per discussion)
2. Loses ability to diagnose *where* extraction fails
3. Prompt improvement becomes less precise (conversation-level, not statement-level)
4. Cluster detection quality is a separate problem requiring separate evaluation
5. Existing per-statement GT investment feels wasted (mitigated: becomes Tier 2)

## Impact on Existing Infrastructure

- **Delta model**: Unchanged for runtime (AI still produces per-statement deltas)
- **SARF editor**: Preserved for Tier 2. Cumulative view already exists — could be adapted to be editable.
- **F1 calculation code**: Extended with cumulative variant, not replaced
- **IRR study**: Descoped from MVP timeline, focused on small discussion subset

## Empirical Evidence: 2026-02-14 Induction Run

Ran 6 iterations of prompt tuning on gemini-2.5-flash. Key findings:

### GT Data Quality Is the Primary Blocker

| Issue | Count | % of 88 GT Events | Impact |
|-------|-------|--------------------|--------|
| person=None | 18 | 20.5% | Events can NEVER match AI output (AI always sets person) |
| Placeholder descriptions ("New Event", "") | 24 | 27.3% | Fail fuzzy description matching (threshold=0.4) |
| dateCertainty=None | 88 | 100% | 7-day tolerance never applies; all default to 270-day |
| Placeholder dates (2025-06-01 repeated, etc.) | unknown | ? | Temporal data unreliable |

16 of 60 cases with events have at least one person=None event.

### Measurement Is Noise

- 45-case benchmark has ±0.03 noise floor on aggregate F1
- 6 prompt/config variations all scored 0.217-0.243 — statistically indistinguishable
- Cannot reliably detect improvements < 0.03 with current GT size
- AI under-extracts by ~50% (45 events vs GT's 88) — but unclear if GT is over-coding

### Workarounds Applied to f1_metrics.py

- GT person=None treated as wildcard in event matching
- Placeholder descriptions auto-pass description matching
- **NOTE**: These are bandaid fixes that mask GT data quality problems. Should be reverted after GT is fixed.

## Integrated Analysis

The induction run confirms and sharpens the strategic analysis:

1. **The per-statement F1 metric is currently measuring noise.** Both from metric-goal misalignment (structural) AND from broken GT data (data quality). The 0.217-0.243 range is a ceiling imposed by data quality, not a measure of model quality.

2. **Prompt improvement is blocked.** You cannot improve what you cannot measure. With ±0.03 noise and broken GT data, prompt tuning is shooting blind.

3. **The SARF editor permits incomplete coding.** 20.5% person=None and 27.3% placeholder descriptions means the coding workflow lacks validation. Experts can (and do) save partially-coded events.

4. **The 50% under-extraction needs investigation before acting.** If GT is over-coding (extracting events a reasonable AI wouldn't extract from the text), the AI isn't wrong — the GT is inflated. This can only be determined by manual review.

5. **Cumulative GT would surface these problems faster.** An expert reviewing the final PDP holistically would immediately notice person=None events and placeholder descriptions because they'd look wrong in context. Per-statement coding hides these issues in the middle of hundreds of statements.

## Recommendations (Priority Order)

### Immediate (unblocks current F1 measurement)

1. **Fix the 18 person=None events** in existing GT. ~2 hours expert time. Highest ROI action available.
2. **Fix the 24 placeholder descriptions** in existing GT. ~2 hours expert time.
3. **Add dateCertainty to all 88 events.** Enables proper date tolerance matching.
4. **Revert f1_metrics.py workarounds** after GT data is fixed. Bandaid fixes mask the root cause and degrade metric trustworthiness.
5. **Add SARF editor validation**: require person link and non-empty description before saving events. Root-cause fix preventing future broken GT.
6. **Re-run prompt iterations** after GT fixes to see if F1 scores differentiate. If they still don't, confirms metric-goal misalignment is the real structural problem.

### Strategic (unblocks MVP validation)

7. **Implement cumulative F1** as primary MVP metric. Run existing entity matching on cumulative PDP instead of per-statement deltas. Small code change, big signal improvement.
8. **Adopt "correct AI output" coding workflow.** Expert reviews AI cumulative PDP and fixes errors, rather than coding from scratch. Faster AND higher quality (targeted corrections vs. building from nothing).
9. **Scale to 20-30 cumulative-GT-coded discussions.** Reduces noise floor to ±0.01-0.02. Makes prompt improvement measurable.
10. **Investigate the 50% under-extraction.** Manually review 5-10 cases: is the AI actually missing things, or is GT over-coding?

### Post-MVP

11. **Per-statement GT for IRR study** on small subset (5-10 discussions).
12. **Fine-tuning dataset** from cumulative GT (convert to per-statement format if needed).

## Open Questions

1. How much faster is cumulative GT coding in practice? Need to time a trial.
2. What cumulative F1 threshold constitutes "good enough" for MVP Learn view?
3. Should cumulative GT be coded from scratch or by reviewing/correcting AI output (Option C hybrid)?
4. How to evaluate cluster detection quality independently from extraction quality?
5. Is the 50% AI under-extraction real or a GT over-coding artifact?
6. After GT data fixes, do prompt iterations produce distinguishable F1 scores?
