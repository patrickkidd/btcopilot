# SARF Literature Review

An exhaustive, 100% traceable literature review of passages from seminal sources
that define terms in the SARF data model for Bowen Family Systems Theory.

## Why This Matters

This is the first exhaustive literature review of its kind for Bowen Theory. Every passage in each primary source that could pertain to SARF terms has been indexed, coded, and listed. This provides:

1. **Theoretical grounding** for the Family Diagram app and btcopilot AI system
2. **Operational definitions** for AI classification of clinical interview data
3. **Traceable citations** - every claim links to searchable source passages
4. **Quality assurance** - definitions derived exclusively from authorized sources, no AI training data

---

## Table of Contents

### Results: SARF Term Definitions

| # | Term | File | Category | Status |
|---|------|------|----------|--------|
| 1 | [Functioning](sarf-definitions/01-functioning.md) | Core Variable (F) | Awaiting calibration |
| 2 | [Anxiety](sarf-definitions/02-anxiety.md) | Core Variable (A) | Awaiting calibration |
| 3 | [Symptom](sarf-definitions/03-symptom.md) | Core Variable (S) | Awaiting calibration |
| 4 | [Conflict](sarf-definitions/04-conflict.md) | Relationship Mechanism | Awaiting calibration |
| 5 | [Distance](sarf-definitions/05-distance.md) | Relationship Mechanism | Awaiting calibration |
| 6 | [Cutoff](sarf-definitions/06-cutoff.md) | Relationship Mechanism | Awaiting calibration |
| 7 | [Overfunctioning](sarf-definitions/07-overfunctioning.md) | Relationship Mechanism | Awaiting calibration |
| 8 | [Underfunctioning](sarf-definitions/08-underfunctioning.md) | Relationship Mechanism | Awaiting calibration |
| 9 | [Projection](sarf-definitions/09-projection.md) | Relationship Mechanism | Awaiting calibration |
| 10 | [Inside](sarf-definitions/10-inside.md) | Triangle Position | Awaiting calibration |
| 11 | [Outside](sarf-definitions/11-outside.md) | Triangle Position | Awaiting calibration |
| 12 | [DefinedSelf](sarf-definitions/12-definedself.md) | Mature Move | Awaiting calibration |

### Methodology & Process

| Document | Purpose |
|----------|---------|
| [METHODOLOGY.md](sarf-definitions/METHODOLOGY.md) | Full extraction methodology |
| [PROGRESS.md](sarf-definitions/PROGRESS.md) | Execution status and session log |
| [log/](sarf-definitions/log/) | Reasoning logs for each term (full audit trail) |

---

## Methodology Summary

Full details: [METHODOLOGY.md](sarf-definitions/METHODOLOGY.md)

### Authorized Sources

| Abbreviation | Title | Author |
|--------------|-------|--------|
| **FE** | *Family Evaluation* | Michael E. Kerr |
| **FTiCP** | *Family Therapy in Clinical Practice* | Murray Bowen |
| **Havstad** | Weight Loss Article (seminal SARF variables paper) | Havstad |

**Constraint**: Definitions derived EXCLUSIVELY from these three sources. No AI training data, no external references (e.g., Gilbert), no inference beyond explicit statements.

### Extraction Process

1. **Source Mapping** - Grep scan + chapter identification for each term
2. **Contextual Reading** - Full sequential reads (~3,500+ lines total), not grep snippets
3. **Cross-Reference Analysis** - Convergence and tension across sources documented
4. **Definition Synthesis** - Operational definitions with traceable passage IDs
5. **Domain Expert Calibration** - Patrick's review for each term
6. **Inter-Term Consistency** - Mutual exclusivity and hierarchy checks

### Definition Structure (per term)

Each definition file contains:

- **Operational Definition** - Synthesized from indexed passages
- **Key Discriminators** - What the term IS and is NOT
- **Observable Markers** - Speech/behavior patterns for classification
- **What Triggers Shifts** - Events that cause variable changes
- **Cross-Reference Analysis** - Convergence/tension across sources
- **Gaps & Uncertainties** - Where sources are silent or ambiguous
- **Confidence Ratings** - High/Medium/Low per concept
- **Passage Index** - Every relevant passage with search strings for PDF lookup

---

## Application to AI System Prompts

These definitions directly populate the SARF VARIABLE DEFINITIONS section in [btcopilot/personal/prompts.py](../btcopilot/personal/prompts.py).

The AI data extraction system uses these definitions to:

1. **Classify speech/behavior** into SARF categories (F shift up/down, A shift up/down, etc.)
2. **Identify relationship patterns** (conflict, distance, cutoff, overfunctioning, etc.)
3. **Detect triangle dynamics** (inside/outside positions)
4. **Extract events** with appropriate variable coding

Each definition includes "Observable Markers" tables that inform classification:

```
**Observable Markers - F Shift UP**:
| Category | Indicators |
|----------|------------|
| I-Position Statements | "These are my beliefs," "This is what I will do" |
| Principle Language | Decisions framed around principles rather than comfort |
| Staying on Course | Maintaining position despite pressure |
...
```

The AI system treats these as illustrative samples, not exhaustive lists - any speech matching the underlying construct definition is classified appropriately.

---

## Statistics

| Metric | Value |
|--------|-------|
| Definition files | 12 |
| Reasoning logs | 12 |
| Lines read (full contextual) | ~3,500+ |
| Indexed passages | ~400+ |
| Primary sources | 3 (FE, FTiCP, Havstad) |
| External sources used | 0 |

---

## Research Methods

This exhaustive review was conducted using:

- Previous manual exhaustive review from doctoral dissertation
- Domain expertise in Bowen theory training and literature
- Doctoral-level expertise in qualitative research methods
- AI Context Architecture for systematic source processing
- Agentic AI-assisted search with human-in-the-loop verification
- Software architecture expertise for operational definition design

Cost: ~$20 in agentic server time using Claude Code.

---

## Future Work

- **Eight concepts of Bowen Theory** - Same methodology to be applied to differentiation of self, triangles, nuclear family emotional system, family projection process, multigenerational transmission process, sibling position, emotional cutoff, and societal emotional process
- **Inter-term consistency checks** - Phase 6 validation pending
- **Integration with training pipeline** - Automated F1 scoring against definitions
