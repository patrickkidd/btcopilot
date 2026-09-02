# The nature of this data (phase A — for Patrick's correction)

Basis: the seven marker-densest clinical cases (case_29, 41, 03, 40, 48, 61, 50),
anonymized structure only, recomputed 2026-09-01 and independently re-verified by
adversarial recomputation (all numbers below survived it). Labels: **[computed]** =
fact from the files; **[inference NN%]** = a read, with confidence; **[Q]** = a
one-line question where inference runs out. Grounded in the ruled teachings (no
absolute S/A/R/F values; episodic clusters; emergent baselines; sampling bias toward
periods of running process; never guess a position). Owner facts folded in:
case_29 was hand-curated by Patrick BEFORE the full SARF model existed and he
counts THREE clusters in it — so (a) mechanical gap-clustering over-splits
(clusters are nameable clinical episodes, not gap artifacts), and (b) case_29's
idioms are hand-curation style, not app-era practice; it is treated as its own
regime below.

## 1. A worked case is two layers with a sharp boundary

**[computed]** Every case is a genealogical scaffold (20–120 dated unmarked
points: births, marriages, deaths) carrying a diagnostic payload of 9–33 marked
points (nodal flag or variable value). The payload share of dated material runs
10%–39% (case_48 lowest, case_41 highest) — a minority everywhere, but the share
varies 4x across cases. Marks start at 1965 at the earliest; scaffold reaches
back to the 1930s. **[inference 85%]** The scaffold exists FOR the payload —
context that makes the few marked years interpretable, not an attempt at
complete family history. (Untestable in-file — no creation order — held at 85%
on the strength of the ruled teachings.)

## 2. The mark: a worded, custom observation carrying one variable — or none

**[computed]** 122 marks across the seven cases. 110 are "custom" events (kind
= other); structural events are almost never marked (deaths occasionally, as
nodal). Every mark carries text (median 20–176 bytes — phrase to sentence; zero
exceptions). Variable arithmetic: ~28% of marks (34/122) are nodal-only with NO
variable; nearly all the rest carry exactly ONE variable; exactly two marks
carry two variables, and exactly one point (case_29, pre-SARF) carries four.
**[inference 80%]** The mark is a note-taking act: one observation, one
dimension at most, in words, pinned to a time — never a scoring pass.
**[Q]** Nodal-only marks (~28%): a deliberate "something turned here" class
distinct from variable shifts, or under-coding you'd backfill today?

## 3. Variable use is narrow and case-specific — cause unknown

**[computed]** case_40 codes anxiety only; case_41 and case_61 are
symptom-dominant; case_48 is nodal-only (zero variables); case_29 (pre-SARF)
runs symptom+anxiety. Functioning: 7 uses across all seven cases. Relationship
as a variable: rare. Differentiation: zero uses in the entire corpus (the field
exists in every event).
**[Q]** Does the per-case variable palette track the presenting problem (the
palette itself being diagnostic), or your coding history at the time each case
was worked? The files cannot decide this.
**[computed]** Some direction values are the enum value "other" (not up/down;
the anonymizer maps any non-up/down value there): case_29: 9, case_03: 4,
case_41: 5, case_40: 2.
**[Q]** What are those non-up/down direction values in the source — early
schema leftovers, or qualitative shifts up/down can't hold?

## 4. Time: episodic clusters; ordering is trustworthy, position is not

**[computed]** Marks arrive in clusters separated by multi-year silent gaps in
every case (mechanical gap>3y finds 1–7 per case; the owner's count for case_29
is 3 — the mechanical split over-counts singletons and near-gaps, so cluster =
nameable episode, threshold detection is only a first pass). Cluster recency is
NOT a law: the biggest cluster is the most recent in 3 of 7 cases only.
**[computed]** What DOES separate old from recent: composition. Pre-2005 marks
are 60% nodal-only (25/42); post-2005 marks 33% (26/80) — the deep past is
remembered as turning points, the nearer record carries variable shifts.
**[inference 75%]** That composition gradient is the two data-generating
processes: remembered history (a historical intake yields a few nameable
periods, mostly "something turned here") vs closer observation (variable
shifts). Case-level recency of bulk depends on when the case was worked, which
the files don't carry.
**[computed]** Dating is guessed-but-precise: 46–100% of marks carry the unsure
flag, yet 74% of dated marks (83/112) have month resolution. **[inference 85%]**
Dates preserve ORDER and local spacing, not absolute position — per the ruled
"ordering IS drawable" / "never guess a position". The unsure flag means "don't
trust the axis position", not "don't trust the sequence".

## 5. Marks concentrate on one or two people — but not only on people

**[computed]** The top-marked person carries 47–82% of a case's marks, always
at least twice the runner-up; 2–9 people carry any mark, out of 27–71 people in
these diagrams. Index gender: female in 4 cases, male in 2 (one case mixed);
one diagram uses the "abortion" person kind. **[computed]** Marks also attach
to pair-bonds, not just people: 8 of case_29's 33 marks are couple events
(1 each in case_48/50) — and case_29's scaffold is nearly half couple events
(48 dated). **[inference 90%]** One index person (sometimes plus spouse/child)
is the observational center; the other ~90% of people are the system the marks
sit in. Whole-family variable tracking does not appear anywhere.

## 6. Relationship symbols: two idioms, and Cutoff is first-class

**[computed]** Six of seven cases: symbols are mostly or entirely UNDATED
(case_03: 2 of 26 dated; case_41: 4 of 21; case_48: 0 of 3) and the undated
vocabulary is rich: Inside/Outside sets (triangles), Projection, Distance,
Conflict, Fusion, Cutoff (10 corpus-wide, 5 in case_29 alone), Toward,
DefinedSelf. case_29 inverts the idiom: 25 of 31 symbols dated — and 18 of
those carry END dates (episodes, not points) and 25 carry text (other cases:
0–5 worded symbols). **[inference 85%]** The dominant idiom draws the BASELINE
EMOTIONAL CONFIGURATION — standing triangles, chronic distance, projection
routes; a structural portrait with no time axis. This converges independently
with the handwritten-notes finding (baseline-configuration cases). The dated
idiom moves relationship process onto the timeline as SPANS — but its one rich
exemplar is pre-SARF hand-curation, so whether it represents your intended
practice is an open owner question, not an inference.
**[Q]** One triangle = several Inside/Outside symbols (per-leg), so symbol
count >> triangle count?
**[Q]** Is case_29's dated-span symbol idiom the future (intended practice) or
an artifact of that case's hand curation?

## 7. Where uncertainty actually lives

**[computed]** Not in whether things happened (every mark is worded) but in:
axis position (unsure flags 46–100%), symbol dating (absent by idiom in 6/7),
direction semantics ("other" values), event duration (t_end is used on ZERO
person/couple events — durations exist only on dated relationship symbols), and
coverage (multi-year silent gaps between clusters in every case).
**[inference — doctrine, not file-testable]** The gaps are
unobserved-not-calm; drawing them as stable periods would fabricate data. This
is the most dangerous default a visualization could adopt.

## 8. Constraints handed to phase B (constraints, not designs)

1. The drawable unit is the nameable episode-cluster (few per case), separated
   by silent gaps that must read as unknown, never as calm.
2. Order and within-cluster spacing are trustworthy; absolute position is not —
   precision-implying drawings lie (46–100% unsure).
3. Foreground population is tiny (1–2 marked people + occasionally the
   pair-bond itself as a mark-carrier); background population is huge.
4. Variables arrive one-per-mark in a narrow per-case palette; ~28% of marks
   carry no variable at all (nodal-only) — the drawing needs a lane-less mark
   class, and a 5-lane grid would be mostly empty everywhere.
5. Two symbol registers: undated baseline configuration (a portrait, not a
   timeline) vs dated relationship SPANS with end dates (episodes) — never
   force both onto one axis; person/couple events have no durations at all.
6. Every mark has words: text on tap is always available; nothing needs a
   synthetic label.
7. The deep past is nodal-heavy turning points; the nearer record carries
   variable shifts — one visual treatment will not fit both.

## 9. Open questions (answer any subset, by number)

1. Nodal-only marks: deliberate turning-point class or under-coding? (§2)
2. Per-case variable palette: clinical signal or coding history? (§3)
3. Non-up/down direction values in the source: what are they? (§3)
4. One triangle = several Inside/Outside symbols? (§6)
5. Dated-span symbols (case_29 style): intended future practice or curation
   artifact? (§6)
6. The four-variable point in case_29: deliberate "everything moved here" or
   over-coding? (§2)
7. Are the small decades-old clusters intake-remembered periods, or archaeology
   added while working the case later? (§4)
