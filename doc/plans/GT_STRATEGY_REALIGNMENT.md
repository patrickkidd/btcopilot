# Plan: GT Strategy Realignment for MVP

## Problem Statement

The GT (Ground Truth) pipeline is meant to enable a prompt improvement cycle: domain experts code GT → compute F1 → export → analyze → improve prompts → remeasure. This cycle has never completed. Six prompt tuning iterations on gemini-2.5-flash produced F1 scores of 0.217-0.243 (±0.03 noise floor) — statistically indistinguishable. The pipeline cannot currently tell us whether the Personal app's extraction quality is improving.

Two root causes:

1. **GT data quality**: ~40% of the 88 GT events are structurally unmatchable (20.5% missing person links, 27.3% placeholder descriptions, 100% missing dateCertainty). Workarounds were applied to f1_metrics.py to mask these issues (person=None wildcard, placeholder auto-pass).

2. **Metric-goal misalignment**: F1 is computed per-statement (comparing AI deltas vs GT deltas for each utterance), but the MVP user experience depends on cumulative PDP quality after a full conversation. Per-statement F1 contains noise from temporal allocation mismatch (same entity coded at different statements by AI vs expert), delta granularity (intermediate states that get superseded), and fuzzy matching brittleness — none of which affect what the user sees.

## Goal

Establish a GT evaluation strategy that:
- Produces actionable signal for prompt improvement (F1 scores that differentiate between prompt quality)
- Directly measures what the MVP user experiences (cumulative PDP quality after "accept all" in the Learn view)
- Can scale GT volume fast enough to support MVP validation (current: 45 approved cases across 3 discussions)

## Background: How GT Currently Works

### The Delta Model
The AI produces `PDPDeltas` per user statement — sparse change sets containing new/changed people, events, pair bonds, and deletes. These accumulate into a `PDP` (Pending Data Pool) that the user reviews and accepts into their diagram. The delta model enables real-time streaming extraction during conversations.

### GT Coding Workflow (SARF Editor)
Domain experts open a discussion in the training app's SARF editor, which shows three columns: conversation flow, per-statement delta editor, and cumulative PDP view. The expert edits the delta for each statement to reflect what the AI *should have* extracted. Edits auto-save as `Feedback.edited_extraction` records. An admin bulk-approves an expert's feedbacks for a discussion.

### F1 Calculation
Per-statement: for each approved statement, compare AI's `Statement.pdp_deltas` against the approved `Feedback.edited_extraction` using fuzzy entity matching (name similarity ≥0.6, description similarity ≥0.4, date proximity ≤7 days / 270 days approximate). Produces aggregate micro-F1, per-type micro-F1, and SARF variable macro-F1.

### Current GT Data State
- 45 approved feedbacks across 3 discussions (1,135 total statements, 4 auditors)
- 88 GT events total; 18 with person=None, 24 with placeholder descriptions, 88 with dateCertainty=None
- Zero GT exports ever executed
- IRR kappas showing "-" (insufficient matched events)

### What the User Actually Sees
The Personal app user chats in Discuss view → accepts PDP items → views Learn tab. The Learn tab shows:
- Cumulative SARF line graphs (symptom/anxiety/functioning over time)
- Relationship event markers
- Chronological event list grouped by AI-detected clusters (via separate Gemini prompt)
- Guide/Plan view is placeholder only (not implemented)

The user's experience depends entirely on the cumulative PDP after accepting items — not on per-statement delta fidelity.

## Plan

### Phase 1: Fix GT Data Quality
**Goal**: Make the existing per-statement F1 metric trustworthy by fixing broken GT data. Determine if per-statement F1 can produce actionable signal once data is clean.

- [ ] 1.1: Fix 18 GT events with person=None — assign correct person links in SARF editor
- [ ] 1.2: Fix 24 GT events with placeholder descriptions ("New Event", "") — write real descriptions
- [ ] 1.3: Add dateCertainty to all 88 GT events (approximate vs certain)
- [ ] 1.4: Review suspicious GT dates (repeated 2025-06-01, 2025-12-15/16) — fix placeholders
- [ ] 1.5: Revert f1_metrics.py workarounds (person=None wildcard, placeholder auto-pass) after data fixes
- [ ] 1.6: Add SARF editor validation — require person link and non-empty description before saving events. Root-cause fix preventing future broken GT.
- [ ] 1.7: Re-run 6 prompt iterations against fixed GT. Record whether F1 scores now differentiate. **Decision point**: if scores still cluster within ±0.03, proceed to Phase 2. If they differentiate, per-statement F1 is viable and Phase 2 becomes an enhancement rather than a necessity.

### Phase 2: Implement Cumulative F1
**Goal**: Add a conversation-level F1 metric that directly measures what the user sees after "accept all."

- [ ] 2.1: Implement cumulative F1 calculation — run `pdp.cumulative()` for AI and `pdp.cumulative(auditor_id=...)` for GT, then apply existing entity matching logic to the two cumulative PDPs. One F1 score per discussion.
- [ ] 2.2: Add cumulative F1 display to the auditor dashboard alongside existing per-statement F1
- [ ] 2.3: Run cumulative F1 on all 3 GT-coded discussions. Compare against per-statement F1. Document the delta and what it reveals about metric-goal alignment.
- [ ] 2.4: Investigate the 50% AI under-extraction (AI: ~45 events vs GT: 88). Using cumulative comparison, determine: is the AI actually missing entities, or is per-statement GT over-coding (allocating the same entity to multiple statements)?

### Phase 3: Scale GT Volume via Cumulative Coding Workflow
**Goal**: Get to 20-30 cumulative-GT-coded discussions to reduce noise floor to ±0.01-0.02 and make prompt improvement measurable.

- [ ] 3.1: Build "cumulative review" coding workflow — expert reads full conversation, then reviews and corrects the AI's cumulative PDP (not per-statement deltas). This is editing the AI's output, not coding from scratch.
- [ ] 3.2: Determine where this workflow lives in the training app. Options: (a) editable cumulative column in existing SARF editor, (b) new dedicated cumulative review page, (c) standalone export/review tool.
- [ ] 3.3: Time-trial the cumulative coding workflow on 2-3 discussions. Measure hours per discussion vs per-statement coding. Target: <1 hour per discussion.
- [ ] 3.4: Code 20-30 discussions using cumulative workflow. Prioritize diversity of conversation topics and lengths.
- [ ] 3.5: Establish cumulative F1 baseline across the expanded dataset. This becomes the primary MVP quality metric.

### Phase 4: Resume Prompt Improvement
**Goal**: Use cumulative F1 on the expanded dataset to run a prompt improvement cycle that produces measurable gains.

- [ ] 4.1: Re-run prompt tuning iterations against cumulative F1 on 20-30 discussions
- [ ] 4.2: Determine "good enough" cumulative F1 threshold for MVP. Criteria: does a domain expert reviewing the cumulative PDP agree it's useful for the Learn view?
- [ ] 4.3: Iterate prompts until cumulative F1 meets threshold or diminishing returns are clear
- [ ] 4.4: Document final prompt configuration and cumulative F1 score as MVP extraction baseline

### Post-MVP: IRR Study and Fine-Tuning
Not blocking MVP. Tracked here for continuity.

- [ ] 5.1: Per-statement GT coding for 5-10 discussions (IRR study subset)
- [ ] 5.2: Run formal IRR with 2-3 coders on the subset
- [ ] 5.3: Evaluate fine-tuning readiness based on cumulative GT dataset size

## Risks

1. **Cumulative GT coding may still be slow.** If a discussion produces 15 people and 40 events, reviewing the cumulative PDP is still substantial. Mitigation: time-trial in Phase 3.3.
2. **Cumulative F1 loses per-statement diagnostics.** If cumulative F1 is low, you can't tell which statements caused it without drilling in. Mitigation: per-statement F1 remains available as a diagnostic tool.
3. **AI under-extraction may be real.** If the AI genuinely misses 50% of events, prompt improvement is a bigger lift than expected. Mitigation: Phase 2.4 investigates this before committing to Phase 4.
4. **Cluster detection quality is a separate problem.** Even with perfect extraction, Gemini clustering could be bad. This plan does not address cluster evaluation — that's a separate effort.
5. **SARF editor validation (1.6) may block existing coders.** If experts have partially-coded work in progress, new validation could prevent saves. Mitigation: validate only on new saves, not retroactively.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-14 | Brainstorming: GT strategy may need realignment | Per-statement F1 not measuring UX goal; throughput bottleneck blocking GT volume |
| 2026-02-14 | Evidence: 6 prompt iterations indistinguishable (0.217-0.243) | GT data quality + metric design = no actionable signal |
| | | |

## References

- [Brainstorming: GT Strategy MVP](../brainstorming/2026-02-14-gt_strategy_mvp.md) — full strategic analysis with options considered
- [SARF_GROUND_TRUTH_TECHNICAL.md](../SARF_GROUND_TRUTH_TECHNICAL.md) — GT coding workflow and approval state machine
- [F1_METRICS.md](../F1_METRICS.md) — current F1 calculation methodology
- [DATA_MODEL.md](../specs/DATA_MODEL.md) — schema definitions
- [specs/PDP_DATA_FLOW.md](../specs/PDP_DATA_FLOW.md) — delta model and PDP architecture
- [IRR_STUDY_VISION.md](../IRR_STUDY_VISION.md) — IRR study design (post-MVP)
