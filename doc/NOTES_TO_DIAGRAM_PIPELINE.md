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
   pages of one case together and emits ONE JSON case document (btcopilot.schema, below).
   Multi-PDF cases are one call when the pages fit, else per-PDF calls merged by
   a second model pass that deduplicates people/events across PDFs.
3. **Import**: deterministic Python writes the .fd via the app's scene schema —
   people (name, gender, birth/death), pair-bonds, parent-child, relationship
   symbols, dated events with descriptions, variable shifts, nodal flags. Every
   imported item carries its provenance (PDF + page) in its notes tail.
4. **Review**: the professional opens the diagram in the app and corrects it.
   Uncertain items are flagged (unsure=true) rather than dropped.

## Interpretation output format: btcopilot.schema (existing), not a new schema

The model emits the SAME data model the chat extraction pipeline already produces
(btcopilot/btcopilot/schema.py): `Person` (name, last_name, gender: PersonKind,
parents, confidence), `PairBond` (married tri-state, confidence), `Event` (kind:
EventKind, person/spouse/child, description, notes, location, dateTime,
dateCertainty: DateCertainty = certain|approximate|unknown, symptom/anxiety/
functioning: VariableShift = up|down|same, relationship: RelationshipKind +
targets/triangles, confidence). One addition for this pipeline, per item:
`source: {pdf, page}` provenance (carried into the imported item's notes tail).

Dates: transcribed as written; a missing or guessed-at year is dateTime=None or
dateCertainty=approximate/unknown — the model never silently invents a date.

Unattributable content: legible text the model cannot confidently pin to a person
or date goes in an `unplaced[]` list (text + source page) INSIDE the per-case
interpretation JSON — a sidecar file next to the PDFs, not markdown, not separate
files, not in the diagram. During review it is either placed by hand or discarded;
nothing legible is ever silently dropped. (Whether any of it should also land in
the diagram's own notes field is Patrick's call, default no.)

## Bake-off protocol (approved, two-armed)

5 sample cases spanning difficulty (1 PDF → 40 PDFs). Both models get identical
prompts + the schema. Patrick scores blind per case: people found/missed,
structure correct, dates right, handwriting misreads, hallucinated content.
His scores pick the winner and get recorded here; the loser's characteristic
errors are kept as a checklist for reviewing the winner's output at volume.

## Scoring dimensions ruled out for now

No automatic accuracy metric — the oracle is Patrick's eyeball, per the standing
rule that no rubric is inferred without him.
