# Decision Log

Running record of major decisions. See root CLAUDE.md for logging criteria.

**Order:** Newest entries first within each month section. Add new entries at the top of the relevant month.

---

## 2026-02

### 2026-02-14: PairBonds are first-class entities, explicitly extracted by AI

**Context:** Cumulative F1 revealed AI extracts zero pair bonds across all discussions (0.000 F1). Investigation showed the fdserver prompt has zero positive PairBond extraction examples, and `cleanup_pair_bonds()` aggressively prunes pair bonds not referenced by Person.parents.

**Background — two creation paths exist:**
1. **Explicit**: AI/auditor creates PairBond entity, sets Person.parents to reference it
2. **Inferred**: AI creates Married/Birth event with person+spouse → system auto-creates PairBond at commit time via `_create_inferred_pair_bond_items()` / `_create_inferred_birth_items()`

**Options considered:**
1. Fix AI prompt to extract PairBonds directly as first-class delta entities
2. Lean into auto-inference only, exclude pair bonds from F1
3. Add pair bond inference to F1 calculation to mirror commit-time behavior

**Decision:** Option 1 — PairBonds are first-class, explicitly extracted.

**Reasoning:**
- PairBonds encode *relationships* (stated facts). Events encode *occurrences*. "My parents are Mary and John" is a relationship, not an occurrence — only a PairBond makes sense.
- The pro app's event-first design ("add events, diagram builds itself") was a UX simplification for non-technical clinicians, not a statement about PairBond importance in the domain model.
- Person.parents needs a PairBond ID to reference. The SARF editor needs PairBonds for coding. F1 needs them for measurement. All downstream consumers expect explicit PairBonds.
- Auto-inference stays as a fallback for cases the AI misses, not the primary path.

**Changes:**
- Add positive PairBond extraction examples to fdserver prompt
- Fix `cleanup_pair_bonds()` to keep pair bonds referenced by events (not just Person.parents)
- Keep pair bonds in F1 metric
- Update DATA_MODEL_FLOW.md to correctly document PairBond lifecycle

**The conceptual inconsistency** (Birth events + explicit PairBonds both establish parentage) is acceptable for MVP. Dedup logic in `_create_inferred_pair_bond_items()` handles it. Full resolution would require major refactoring not warranted now.

**Revisit trigger:** If PairBond F1 remains low after prompt fix, revisit whether the extraction schema or inference approach needs restructuring.

---

## 2026-01

### 2026-01-08: IRR analysis page using F1 + Cohen's/Fleiss' Kappa for SARF validation

**Context:** First GT discussion coded by Patrick and one IRR coder, with two more coders finishing the same synthetic discussion soon. Need formal, publishable IRR metrics for clinical validity of SARF data model.

**Options considered:**
1. Reuse existing F1 analysis page (AI vs GT) for coder-vs-coder comparison
2. Build new IRR page with clinical-standard Kappa metrics alongside F1
3. Use traditional eyeball/non-scalable IRR methods from clinical psychology literature

**Decision:** Option 2 - New `/training/irr/` page with:
- Entity-level F1 (reusing existing matching logic from f1_metrics.py)
- Cohen's Kappa (pairwise, sklearn) per SARF variable
- Fleiss' Kappa (3+ coders) per SARF variable
- Primary vs IRR coder distinction via existing `Feedback.approved` field (no schema change)

**Reasoning:**
- Existing F1 matching logic is source-agnostic (compares two PDPDeltas regardless of origin)
- Kappa is the clinical standard for IRR - chance-corrected, publishable
- Dual-purpose: validates SARF clinical reliability + provides IRR-validated GT for AI training
- Fleiss' extends to 3+ coders (Guillermo, Kathy, Patrick) without N² pairwise comparisons
- Separate page avoids confusing AI evaluation with human agreement metrics

**Publication focus:** SARF variable kappas (symptom, anxiety, relationship, functioning) on matched events - this is the clinically novel contribution. Entity F1 is secondary infrastructure.

**Revisit trigger:** If kappa values are unacceptably low (<0.4), indicating SARF model needs refinement before scaling IRR coder recruitment.

---

## 2025-12

### 2025-12-27: MVP scope - consider shipping People/PairBonds only, defer Events/SARF

**Context:** Evaluating whether F1 is the right metric for MVP given human-in-the-loop accept/reject workflow. Analysis of current extraction performance revealed asymmetric quality across entity types.

**Current metrics (45 statements, 3 discussions):**
- People: Precision 77%, Recall 56%, F1 0.65
- PairBonds: F1 0.78
- Events: Precision 9%, Recall 8%, F1 0.09 (broken)
- SARF variables: All at 0.11 (non-functional)
- Overall: FP=71, FN=106 (missing more than hallucinating)

**Options to consider:**
1. Ship full extraction (People + Events + SARF) and iterate on quality
2. Ship People/PairBonds only (decent F1), add Events/SARF later
3. Delay MVP until Events/SARF quality improves

**Key insight:** Human-in-the-loop makes FPs cheap (professional rejects bad suggestions) but FNs dangerous (professional might not notice missing clinical info). Current FN > FP means recall is the actual problem. However, People/PairBonds at 0.65-0.78 F1 may provide enough value for MVP while Events extraction is fundamentally broken.

**Implications:**
- If scoped to People/PairBonds only, F1 is reasonable metric (both above 0.6)
- Events need architectural fix before worrying about metric choice
- SARF coding may be premature - model isn't learning it at all
- Small GT sample (45 statements) limits statistical confidence

**Decision:** Pending - need to think through UX implications of partial extraction.

**Revisit trigger:** When Events F1 exceeds 0.4, or when UX design clarifies whether partial extraction is viable.

---

### 2025-12-09: Synthetic discussion generation for ground truth manual coding

**Context:** Extraction accuracy evals required ground truth separate from conversational flow assessment - needed raw coding tasks without chat context.

**Options considered:**
1. Use same synthetic discussions for both conversational flow and extraction evals
2. Extract snippets from real audited discussions
3. Generate standalone synthetic discussions specifically for extraction coding

**Decision:** Option 3 - Generate synthetic discussions focused solely on extraction accuracy without conversational flow constraints.

**Reasoning:**
- Conversational flow scenarios optimize for coaching quality, not extraction difficulty
- Targeted synthetic discussions can stress-test edge cases (complex triangles, ambiguous functioning shifts)
- Separates two distinct eval dimensions (conversation quality vs. extraction precision)
- Enables focused prompt tuning without confounding variables
- Experts can code extraction-focused scenarios faster than full coaching conversations

**Revisit trigger:** If maintaining two synthetic generation systems becomes unsustainable, or if real discussion volume makes targeted synthesis unnecessary.

---

### 2025-12-09: Minimum required data checklist in system prompts and for human evaluators

**Context:** Both AI and human evaluators were inconsistent about what data constitutes a "complete" Bowen theory case evaluation.

**Options considered:**
1. Leave completeness criteria implicit in training
2. Provide general guidelines without specific requirements
3. Define explicit minimum data checklist in both AI system prompts and human training materials

**Decision:** Option 3 - Explicit checklist: 3+ generations, all SARF variables tracked, at least one triangle identified, timeline with notable periods.

**Reasoning:**
- Ensures AI prompts don't prematurely conclude data gathering
- Provides objective standard for human evaluators to measure against
- Prevents incomplete evaluations from entering ground truth dataset
- Supports certification criteria (students must meet checklist to pass)
- Makes implicit domain knowledge explicit and teachable

**Revisit trigger:** If checklist proves too rigid for real clinical variation, or if it excludes valid evaluation approaches.

---

### 2025-12-09: Conversational flow evals for measuring therapist skill

**Context:** Bowen theory training focuses on conceptual knowledge but lacks objective measurement of conversational coaching skill.

**Options considered:**
1. Traditional supervisor observation (subjective, unscalable)
2. Self-reported skill assessments
3. Standardized conversational flow evals using validated scenarios

**Decision:** Option 3 - Evals developed for AI will be adapted for human therapist skill measurement.

**Reasoning:**
- Same rubric for AI and humans enables direct comparison
- Standardized scenarios ensure consistent assessment conditions
- Scalable via web interface (no supervisor scheduling required)
- Provides objective data for certification and training programs
- Repurposes AI development work for human training outcomes

**Revisit trigger:** If human therapists reject being measured by AI-derived standards, or if conversational complexity proves too nuanced for rubric-based assessment.

---

### 2025-12-09: Synthetic discussions and user personas for conversational flow

**Context:** Conversational flow prompts needed testing beyond manual expert simulation, but real user data was unavailable pre-launch.

**Options considered:**
1. Wait for real user data post-launch
2. Have experts manually simulate many conversation styles
3. Generate synthetic discussions using user personas (varying demographics, presenting problems, communication styles)

**Decision:** Option 3 - LLM-generated synthetic discussions with explicit user personas.

**Reasoning:**
- Enables pre-launch testing across diverse user types
- Expert time focused on validation rather than simulation
- Reproducible test scenarios for A/B testing prompts
- User personas (e.g., "anxious parent", "avoidant adult child") map to real clinical presentations
- Can generate volume needed for statistical significance

**Revisit trigger:** If synthetic conversations fail to predict real user issues, or if real user volume makes synthetic data obsolete.

---

### 2025-12-09: IRR study with parallel expert coding (Guillermo, Kathy)

**Context:** SARF data model had no formal inter-rater reliability validation - unclear if multiple experts would code cases consistently.

**Options considered:**
1. Sequential auditing (one expert per case)
2. Parallel coding with small sample (10-20 cases)
3. Parallel coding with large sample (100+ cases) for statistical power

**Decision:** Option 3 - Guillermo and Kathy independently code same cases in parallel with Patrick's work.

**Reasoning:**
- First formal IRR study for Bowen theory constructs at scale
- Validates whether SARF model is sufficiently well-defined for consistent application
- Essential for academic credibility and certification system
- Identifies ambiguous constructs requiring model refinement
- Parallel workflow doesn't slow down AI training data collection

**Revisit trigger:** If IRR results show unacceptable disagreement requiring SARF model redesign, or if expert availability drops.

---

### 2025-12-09: Hierarchical F1 dashboard for extraction accuracy

**Context:** Extraction errors varied widely across construct types (Person vs. Triangle vs. ChildFocus), making aggregate metrics misleading.

**Options considered:**
1. Single overall accuracy metric
2. Flat per-construct metrics
3. Hierarchical dashboard: overall → construct type → specific fields

**Decision:** Option 3 - Multi-level F1 score dashboard with drill-down capability.

**Reasoning:**
- High-priority constructs (Functioning, Triangle) need separate tracking
- Field-level granularity (e.g., Triangle.inside vs. outside) reveals specific prompt weaknesses
- Enables targeted prompt improvements instead of blind iteration
- Supports prioritization framework (high/medium/low impact errors)

**Revisit trigger:** If prompt engineering reaches plateau and dashboard complexity outweighs utility, or if fine-tuning makes granular tracking obsolete.

---

### 2025-12-09: Ground truth for standardizing human case evaluation

**Context:** Bowen theory lacks formal evaluation standards - application is subjective and inconsistent across practitioners.

**Options considered:**
1. Develop standards through academic committee consensus
2. Use AI-generated evaluations as standard
3. Use expert-audited ground truth dataset to define measurable evaluation criteria

**Decision:** Option 3 - Ground truth dataset from auditing system becomes the operational standard for case evaluation.

**Reasoning:**
- Auditing workflow forces experts to make explicit, measurable judgments
- Large dataset reveals consensus patterns and acceptable variation ranges
- Provides objective foundation for practitioner training and certification
- Can measure inter-rater reliability at scale for first time in Bowen theory

**Revisit trigger:** If IRR study reveals SARF model is insufficiently reliable, or if academic community rejects data-driven standardization approach.

---

### 2025-12-09: Ground truth extracted data for system prompt refinement

**Context:** System prompts for extraction were underperforming without concrete examples to tune against.

**Options considered:**
1. Rely solely on expert feedback post-deployment
2. Manually craft synthetic examples
3. Have domain experts audit real discussions to create ground truth dataset

**Decision:** Option 3 - Expert auditing system to create ground truth from real conversations.

**Reasoning:**
- Real examples capture edge cases synthetic data misses
- Expert corrections provide precise training signal
- Dataset serves both prompt engineering and future fine-tuning
- Auditing workflow validates the SARF data model itself

**Revisit trigger:** If expert availability drops below sustainable threshold, or if synthetic generation quality improves enough to supplement real data.

---

## 2025-11 (Reconstructed from ARCHITECTURE.md)

### 2025-11-XX: Restructure fdserver as deployment-only repo

**Context:** fdserver contained both application code and deployment config, causing GitHub cache limitations in private repo.

**Options considered:**
1. Keep monolith with fdserver extending btcopilot
2. Split: btcopilot (open source, all app code) + fdserver (private, deploy only)

**Decision:** Option 2 - fdserver becomes deployment-only, all app code to btcopilot.

**Reasoning:**
- GitHub cache works better in public repo
- Single wheel architecture (btcopilot only)
- Clear BUILD vs DEPLOY separation
- Extended prompts and policies can be open source

**Revisit trigger:** If btcopilot needs to be made private, or if deployment complexity increases.

---

## 2025-06

### 2025-06-11: Real-time PDP data flow into diagram files

**Context:** Personal app needed a way to show users extracted data before committing it to their diagram database.

**Options considered:**
1. Separate staging database requiring explicit sync
2. Negative IDs in-memory only (lost on restart)
3. Embedded PDP pool in diagram file with negative IDs

**Decision:** Option 3 - PDP stored directly in diagram pickle with negative IDs, converted to positive on accept.

**Reasoning:**
- Users can see extracted data immediately in UI without server round-trip
- Negative IDs prevent collisions with committed data
- Diagram file remains single source of truth
- Accept/reject operations are atomic and traceable

**Revisit trigger:** If PDP grows too large and bloats diagram files, or if multi-device sync requires server-side PDP storage.

---

### 2025-06-11: PDP Deltas as dual-purpose UX and ML training signal

**Context:** Need both a user-friendly accept/reject workflow and ground truth data for extraction accuracy. Traditional approaches require separate labeling steps.

**Options considered:**
1. Show full extracted data, require users to manually edit JSON
2. Separate UX layer (simple approve/reject) from ML layer (engineer extracts training signal)
3. LLM outputs deltas that serve as both UX proposal and atomic training examples

**Decision:** Option 3 - PDP deltas are the atomic unit for both user interaction and ML ground truth.

**Reasoning:**
- User sees only what changed (cognitive load matches clinical review process)
- Each delta is independently accept/reject (granular feedback, not all-or-nothing)
- Rejected deltas are negative examples (prevents model from repeating errors)
- No separate labeling workflow needed (UI interaction generates training data automatically)
- Deltas are traceable and reusable (can replay decisions, analyze patterns)
- Atomic structure enables field-level accuracy metrics (which attributes are hardest to extract)

**Source:** https://grok.com/share/bGVnYWN5_04d604a7-a3e9-4078-a007-3d2f659fc155

**Revisit trigger:** If users struggle with delta-based review (prefer full-context editing), or if delta granularity proves too fine/coarse for effective learning signal.

---

## Template

```markdown
## YYYY-MM-DD: [Decision Title]

**Context:** Brief situation summary

**Options considered:** What alternatives were weighed

**Decision:** What was decided

**Reasoning:** Key factors that drove the decision

**Revisit trigger:** Conditions that would prompt reconsideration
```
