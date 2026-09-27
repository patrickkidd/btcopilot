# SARF Definitions Extraction Methodology

## Executive Summary

This document describes the methodology for extracting operational definitions of Bowen Family Systems Theory terms from authoritative source materials. These definitions will be used in AI system prompts to classify and extract data from clinical interview transcripts converted to chat threads.

**Goal:** Maximum accuracy and semantic clarity for LLM extraction/classification.

**Constraint:** Definitions must be derived EXCLUSIVELY from three authorized sources—no AI training data, no external references, no inference beyond what the sources explicitly state.

---

## Authorized Sources

| Abbreviation | Full Title | Author |
|--------------|------------|--------|
| **FE** | *Family Evaluation* | Michael E. Kerr |
| **FTiCP** | *Family Therapy in Clinical Practice* | Murray Bowen |
| **Havstad** | *Weight Loss Article* | Havstad (seminal SARF variables article) |

**Source files:**
- `btcopilot-sources/bowentheory/FE Chapters/*.md` (12 chapters)
- `btcopilot-sources/bowentheory/FTiCP Chapters/*.md` (23 chapters)
- `btcopilot-sources/bowentheory/Havstad-Weight-Loss-Article.md`

---

## Terms to Define

### Priority 1: Core SARF Variables
1. **Functioning (F)** - Functional level of differentiation
2. **Anxiety (A)** - Automatic response to real/imagined threat
3. **Symptom (S)** - Physical/emotional/social dysfunction

### Priority 2: Anxiety-Binding Mechanisms (RelationshipKind)
4. **Conflict** - Neither gives in; mutual attack
5. **Distance** - Emotional/physical avoidance
6. **Cutoff** - Severing relationship
7. **Overfunctioning** - Excessive responsibility for others
8. **Underfunctioning** - Ceding responsibility to others
9. **Projection** - Parent focus on child's problem

### Priority 3: Triangle Positions (RelationshipKind)
10. **Inside** - Comfortable twosome position
11. **Outside** - Excluded third position

### Priority 4: Mature Move (RelationshipKind)
12. **DefinedSelf** - I-position; stating self without attack

---

## Methodology

### Phase 1: Source Mapping (per term)

Before reading, identify ALL potentially relevant chapters for each term:

1. **Grep scan** - Find explicit mentions of term and synonyms across all sources
2. **Chapter identification** - List chapters with substantive treatment (not just passing mentions)
3. **Synonym/related term mapping** - Identify words that discuss the concept without naming it
   - Example: "Functioning" may be discussed as "level of self," "differentiation," "borrowing self"

### Phase 2: Contextual Reading (per term, per source)

**Critical:** Full sequential reading is non-negotiable. Grep snippets lose critical context—qualifying statements, examples, and nuances that inform interpretation.

For each identified chapter:

1. **Full sequential read** - Read entire chapter start-to-finish, not grep snippets
2. **Mark passages in context** - Note page/line for each relevant passage
3. **Capture surrounding context** - Include qualifying statements, examples, exceptions
4. **Note what is NOT said** - Explicit negations ("F is not X") are critical for classification
5. **Flag ambiguities** - Where the source is vague, contradictory, or incomplete

**Documentation requirement:** The reasoning log MUST record:
- Line count read per source (demonstrates full read, not grep)
- Key insights discovered from surrounding context
- Nuances that would have been missed by grep snippets alone

**Example (Functioning term):**
| Source | Lines Read | Method |
|--------|-----------|--------|
| Havstad article | ~100 lines | Full sequential read |
| FE Ch 4 | ~200 lines | Full sequential read |
| FE Ch 7 | 306 lines | Full sequential read |
| FTiCP Ch 9 | 129 lines | Full sequential read |
| FTiCP Ch 21 | 300 lines | Full sequential read |

The indexed passages are selected FROM these full reads; surrounding context informs interpretation even when not explicitly excerpted.

### Phase 3: Cross-Reference Analysis (per term)

After reading all sources for a term:

1. **Second pass with full picture** - Re-read key passages knowing what other sources say
2. **Identify convergence** - Where do sources agree?
3. **Identify tension/contradiction** - Where do sources differ? Flag for domain expert adjudication
4. **Map term relationships** - How does this term interact with other SARF terms?
5. **Identify gaps** - What do the sources NOT address that would be useful for classification?

### Phase 4: Definition Synthesis (per term)

Produce a comprehensive definition document with this **exact structure**:

**Part 1: Synthesized Content (for human review)**
1. **Operational Definition** - Synthesized from passages; every claim traceable
2. **Key Discriminators** - What distinguishes this term; positive AND negative definitions
3. **Observable Markers** - Speech/behavior patterns that indicate this term
4. **What Triggers Shifts** - Events/contexts that cause changes (for variables)
5. **Cross-Reference Analysis** - Convergence and tensions across sources
6. **Gaps & Uncertainties** - Where sources are silent or ambiguous
7. **Confidence Ratings** - High/Medium/Low for each extracted concept
8. **Inter-term Relationships** - How this term connects to other SARF terms

**Part 2: Domain Expert Review Section**
9. **Patrick's Feedback** - Space for calibration review
10. **Calibration Questions** - Specific questions for domain expert
11. **Methodology Calibration Notes** - Learnings to apply to future terms
12. **Final Validated Definition** - After iteration

**Part 3: Source Data (raw passage index)**
13. **Passage Index** - Every relevant passage with:
    - Unique ID (e.g., FE4-17)
    - Search string (5-15 words to locate in PDF)
    - Full context summary (not just snippet)
    - Extracted concept

This structure ensures the expert review section appears AFTER synthesized definitions but BEFORE the raw source data, facilitating efficient calibration.

### Phase 5: Domain Expert Calibration

**Critical:** The first term (Functioning) serves as a pilot to calibrate methodology.

1. Present Functioning draft to Patrick for detailed review
2. Capture feedback on:
   - Missed nuances
   - Misinterpretations
   - Over/under-emphasis
   - Missing observable markers
3. Adjust methodology based on feedback
4. Apply refined process to remaining terms

### Phase 6: Inter-Term Consistency Check

After all 12 terms are drafted:

1. **Mutual exclusivity review** - Can the same utterance be classified as multiple terms? Is that appropriate?
2. **Hierarchy clarification** - How do Variables (F, A, S) relate to RelationshipKinds?
3. **Boundary cases** - Document edge cases where classification is ambiguous
4. **Cross-reference validation** - Ensure definitions don't contradict each other

---

## Quality Standards

### Traceability
- Every claim in a definition must cite specific passage IDs
- Every passage must have a search string for PDF lookup
- A human reader must be able to verify any claim against original source

### Source Purity
- NO concepts from AI training data
- NO external Bowen theory sources (Gilbert, etc.)
- NO inference beyond what sources explicitly state
- Flag any synthesis that goes beyond direct quotation

### Classification Utility
- Definitions must support binary or ordinal classification decisions
- Include observable speech/behavior markers where sources provide them
- Flag gaps where sources don't address observability

### Uncertainty Transparency
- Explicit confidence ratings (High/Medium/Low)
- Flag ambiguities and contradictions
- Document where sources are silent

---

## Output Structure

Each term will have a definition file in `btcopilot/doc/sarf-definitions/`:

```
01-functioning.md      # Pilot term - calibration
02-anxiety.md
03-symptom.md
04-conflict.md
05-distance.md
06-cutoff.md
07-overfunctioning.md
08-underfunctioning.md
09-projection.md
10-inside.md
11-outside.md
12-definedself.md
```

Plus supporting documents:
```
METHODOLOGY.md         # This document
PROGRESS.md            # Execution checklist and status
CROSS-REFERENCES.md    # Inter-term relationships and consistency notes
GAPS.md                # Documented gaps across all terms
```

### Reasoning Logs (Required)

**Every term MUST have a corresponding reasoning log** in `btcopilot/doc/sarf-definitions/log/`:

```
log/01-functioning-review.md
log/02-anxiety-review.md
log/03-symptom-review.md
...etc
```

Each log file must contain:

1. **Session-by-Session History**
   - What was attempted in each session
   - What worked, what failed
   - Flaws identified and how they were corrected

2. **Full Reasoning Chain**
   - Why specific sources were prioritized
   - How passages were selected
   - How conflicts between sources were resolved
   - Why specific markers were derived

3. **Key Discoveries**
   - Unexpected insights from full contextual reads
   - Critical passages that changed understanding
   - Nuances that grep snippets would have missed

4. **Cross-Reference Analysis Details**
   - Specific convergences found (with passage IDs)
   - Specific tensions found (with passage IDs)
   - How tensions were resolved or flagged

5. **Definition Evolution**
   - How the definition changed across iterations
   - What feedback prompted changes
   - Version history of key components

6. **Open Questions**
   - Questions for domain expert calibration
   - Unresolved ambiguities
   - Gaps that sources don't address

7. **Methodology Lessons**
   - What was learned that applies to future terms
   - Process improvements identified

**Purpose:** These logs provide full auditability of the extraction process. Anyone reviewing the definitions can trace back through the reasoning chain to understand how conclusions were reached and verify them against sources.

---

## Revision History

| Date | Change | Author |
|------|--------|--------|
| 2024-12-14 | Initial methodology | Claude + Patrick |
| 2024-12-14 | Added required reasoning logs (`log/` folder) for full auditability | Claude + Patrick |
| 2024-12-14 | Added Phase 2 documentation requirements: line counts, context insights, grep-miss examples | Claude + Patrick |

