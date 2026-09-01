# Notes→Diagram pipeline (reusable module, spec draft)

Purpose: a professional scans handwritten paper/pencil case notes (or exports
digital notes) to PDF; the pipeline produces a NEW Family Diagram .fd file for
human review in the app. Originals are never modified. First user: Patrick's
Notability corpus (~56 cases, ~420 PDFs). Home: btcopilot module; interpretation
prompts live in the private layer (like the coach prompts). This spec is the
bake-off scoring target; the winning model + prompt + failure modes get documented
here as part of the method.

## Stages

1. **Render**: PDF pages → images (local, deterministic).
2. **Interpret**: a BAA-covered vision model (bake-off: GPT vs Gemini) reads all
   pages of one case together and emits ONE JSON case document (schema below).
   Multi-PDF cases are one call when the pages fit, else per-PDF calls merged by
   a second model pass that deduplicates people/events across PDFs.
3. **Import**: deterministic Python writes the .fd via the app's scene schema —
   people (name, gender, birth/death), pair-bonds, parent-child, relationship
   symbols, dated events with descriptions, variable shifts, nodal flags. Every
   imported item carries its provenance (PDF + page) in its notes tail.
4. **Review**: the professional opens the diagram in the app and corrects it.
   Uncertain items are flagged (unsure=true) rather than dropped.

## Interpretation output schema (v0 draft — the bake-off scores against this)

One JSON object per case:

- `people[]`: `{ref, name_as_written, other_names[], gender|null, birth{year?, unsure}, death{year?, unsure}, notes}`
- `parent_child[]`: `{child_ref, parent_refs[]}`
- `pair_bonds[]`: `{a_ref, b_ref, kind: bonded|married|separated|divorced, year?, unsure}`
- `events[]`: `{who_refs[], year?|year_range?, unsure, kind: shift|moved|death|birth|other,
  description (verbatim-close), variables: {symptom|anxiety|functioning|relationship|differentiation: up|down}?,
  nodal: bool, source: {pdf, page}}`
- `relationship_symbols[]`: `{a_ref, b_ref?, kind: Conflict|Cutoff|Distance|Toward|Fusion|Projection|Overfunctioning|Underfunctioning|DefinedSelf|Inside|Outside|Reciprocity|Away, start_year?, end_year?, unsure, source}`
- `unplaced[]`: anything legible but not confidently attributable — text + source,
  never silently dropped.
- Refs are per-case ids (p1, p2…): names stay only in `name_as_written`.

Rules for the model: transcribe dates as written, never infer a missing year
(year absent + unsure=true instead); names verbatim; every claim carries a source
page; genogram glyph conventions (squares/circles, double lines, zigzags, cutoff
bars) are read as structure, not decoration.

## Bake-off protocol (approved, two-armed)

5 sample cases spanning difficulty (1 PDF → 40 PDFs). Both models get identical
prompts + the schema. Patrick scores blind per case: people found/missed,
structure correct, dates right, handwriting misreads, hallucinated content.
His scores pick the winner and get recorded here; the loser's characteristic
errors are kept as a checklist for reviewing the winner's output at volume.

## Scoring dimensions ruled out for now

No automatic accuracy metric — the oracle is Patrick's eyeball, per the standing
rule that no rubric is inferred without him.
