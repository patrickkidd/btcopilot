# IRR Study Vision

Inter-Rater Reliability study for SARF coding validation.

## Purpose

Establish clinical validity of SARF (Symptom, Anxiety, Relationship, Functioning) coding through formal inter-rater reliability analysis suitable for publication.

## Strategic Context

The IRR study is one component of a larger R&D pipeline:

1. **Ground Truth Collection** - Human experts code clinical discussions
2. **IRR Validation** - Multiple coders establish reliability of the coding scheme
3. **AI Training** - Validated ground truth trains extraction models
4. **Continuous Improvement** - IRR metrics inform both coder training and AI refinement

High IRR scores validate that SARF coding is learnable and consistent, which is prerequisite for:
- Clinical tool credibility
- AI model training data quality
- Publication of clinical findings

## Study Design

### Coders
- **Primary coder**: Patrick (approved extractions = ground truth baseline)
- **IRR coders**: Additional trained coders submitting unapproved extractions
- Current: 2-3 coders per discussion
- Target: 3+ coders for Fleiss' Kappa calculation

### Materials
- Synthetic discussions with known clinical content
- Real clinical discussions (Dr. Bowen interviews)

### Metrics

**Entity-level agreement:**
- F1 scores for People, Events, PairBonds matching
- Uses fuzzy name matching with configurable thresholds

**SARF variable agreement (primary focus):**
- Cohen's Kappa (pairwise, 2 coders)
- Fleiss' Kappa (3+ coders)
- Per-variable: symptom, anxiety, relationship, functioning
- Calculated only on matched events (same person, same event type)

### Kappa Interpretation (Landis & Koch 1977)
| Range | Interpretation |
|-------|----------------|
| 0.81-1.00 | Almost Perfect |
| 0.61-0.80 | Substantial |
| 0.41-0.60 | Moderate |
| 0.21-0.40 | Fair |
| ≤0.20 | Poor |

## IRR Strategy

### Phase 1: Baseline (Current)
- Train 2-3 coders on SARF coding protocol
- Code shared synthetic discussions
- Identify disagreement patterns

### Phase 2: Calibration
- Review discrepancies in group sessions
- Refine coding guidelines based on common confusions
- Re-code after calibration

### Phase 3: Formal Study
- Code additional discussions independently
- Calculate final IRR metrics
- Document for publication

### Phase 4: Integration
- Use validated coding scheme for ongoing ground truth
- IRR metrics become quality gate for new coders
- Periodic recalibration as scheme evolves

## Current Status

- IRR analysis page implemented at `/training/irr/`
- 2 discussions with multiple coders available
- SARF kappas showing "-" (insufficient matched events for calculation)

## Next Steps

1. Complete coding on synthetic discussion by all 3 IRR coders
2. Ensure events match across coders (same person, same event type)
3. Collect SARF kappa values once matched events exist
4. Expand to additional discussions
5. Write up results for publication

## Publication Target

Clinical validation paper demonstrating:
- Reliability of SARF coding scheme
- Inter-rater agreement on clinical variables
- Feasibility of standardized Bowen theory assessment
