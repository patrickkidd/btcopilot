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

## Bake-off VERDICT (2026-09-01, Patrick scored blind)

**Synthesis wins.** Three arms: GPT-5.2 (reasoning=high) and Gemini 3.1 Pro extract
independently from page images; a third call (Gemini) merges both JSONs while
re-checking every kept item against the page images (dedup name variants; on
disagreement downgrade dateCertainty rather than pick; nothing legible dropped —
losers go to unplaced). Patrick's scores: two cases "C is a good merge", one
"can't tell the three apart, default C", one excluded (case seen once, notes-only,
no diagram — class ruled OUT of the corpus), one revealed a data-nature class
rather than a model difference (see below). The production pipeline is therefore
BOTH models + synthesis, ~3 calls/case; accuracy over cost is ruled (the data is
irreplaceable).

**Baseline-configuration cases (open design point):** some handwritten cases carry
almost no dated events — they describe the family's baseline emotional
configuration: anxiety-binding mechanisms, who's who structure, implied triangle
positions, with ordering only implied by narrative sequence. Forcing these into
dated events is wrong; candidate target = relationship symbols + person/diagram
notes, dates absent. Awaiting Patrick's ruling before the full run treats them.

**Transcription (ruled path):** each PDF also gets a verbatim plain-text
transcription as a SEPARATE archival call — never as an intermediate step feeding
extraction (chaining flattens the drawing's spatial information and propagates
transcription errors); structure is always extracted image→JSON directly. The
transcript is for archive, search, and human review.

**Review at volume:** .md eyeballing does not scale past a cursory pass (his
verdict); the real review surface for the 56-case run is the imported diagram
opened in the app, corrected by hand.

## Bake-off protocol (approved, two-armed → superseded by verdict above)

5 sample cases spanning difficulty (1 PDF → 40 PDFs). Both models get identical
prompts + the schema. Patrick scores blind per case: people found/missed,
structure correct, dates right, handwriting misreads, hallucinated content.
His scores pick the winner and get recorded here; the loser's characteristic
errors are kept as a checklist for reviewing the winner's output at volume.

## Scoring dimensions ruled out for now

No automatic accuracy metric — the oracle is Patrick's eyeball, per the standing
rule that no rubric is inferred without him.
