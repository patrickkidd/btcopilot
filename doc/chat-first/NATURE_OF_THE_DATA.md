# The nature of this data (phase A — for Patrick's correction)

Basis: the seven marker-densest clinical cases (case_29, 41, 03, 40, 48, 61, 50),
anonymized structure only, recomputed 2026-09-01. Every claim is labeled:
**[computed]** = fact from the files; **[inference NN%]** = my read, with
confidence; **[Q]** = a one-line question where inference runs out. Grounded in
the ruled clinical teachings (no absolute S/A/R/F values; episodic clusters;
emergent baselines; sampling bias toward periods of running process; never guess
a position). General genogram/therapy priors are not used.

## 1. A worked case is two layers with a sharp boundary

Every case is a large scaffold carrying a small diagnostic payload. **[computed]**
Scaffold: 21–121 dated points of plain genealogy (births, marriages, deaths).
Payload: 9–33 marked points (nodal flag or variable value). The payload is
1/5 to 1/10 of the dated material. The boundary is real, not an artifact: the
scaffold establishes who exists and when generations turn over; clinical
attention begins at the first mark and never retroactively marks the deep past.
**[inference 85%]** The scaffold is built FOR the payload — context to make the
few marked years interpretable — not an attempt at complete family history.

## 2. The mark is a worded, custom, single-variable observation

**[computed]** Across all seven cases: marks are overwhelmingly "custom" events
(kind = other), not structural ones — structural events (births/marriages) are
almost never marked; deaths occasionally are, as nodal. Every single mark
carries text (no zero-text marks anywhere; median 20–176 bytes — a phrase to a
sentence). Marks carry ONE variable at a time almost without exception (a
handful of S+A; exactly one S+A+F+R point in ~120 marks).
**[inference 80%]** The mark is a clinical note-taking act: one observation,
one dimension, in words, pinned to a time — not a scoring pass over the
timeline. Multi-variable scoring of a moment is not how you work.
**[Q]** Is the lone S+A+F+R point in case_29 a deliberate "everything moved
here" nodal statement, or an over-coding you'd undo?

## 3. Each case is coded in a variable dialect, not the full palette

**[computed]** case_40 codes anxiety only. case_41 and case_61 are
symptom-dominant. case_48 is nodal-flags only, zero variables. case_29 runs
symptom+anxiety. Functioning appears in single digits across all seven;
relationship-as-variable barely exists; differentiation is used exactly zero
times in the entire corpus.
**[inference 70%]** The dialect tracks the case's presenting problem (an
anxiety case gets anxiety marks, a symptom case symptom marks) — the variable
chosen IS diagnostic information, not a coding-style accident.
**[Q]** Is per-case dialect real clinical signal, or just when-you-learned-
which-feature coding history?
**[computed]** Some direction values are neither up nor down but free text
("other" in the enum: 9 in case_29, 3 in case_03).
**[Q]** Are text-valued directions early-schema leftovers or deliberate
qualitative shifts that up/down can't hold?

## 4. Time is episodic clusters with a recency gradient; order beats position

**[computed]** Marks arrive in 1–7 clusters (gap >3y separates), and the
LARGEST cluster is the most recent in nearly every case: case_29 puts 18 of 33
marks in 2015–2019; case_41 puts 16 of 26 in 2014–2023; case_61 is one long
2010–2019 episode. Earlier clusters are small (1–7 marks) and decades apart.
**[inference 90%]** This is the ruled sampling bias made visible: the dense
recent cluster is the consultation period (live observation); the sparse old
clusters are the 3–5 remembered periods a historical intake yields. Two
different data-generating processes in one timeline — remembered history vs
observed present — and they look different: old clusters are sparser, more
nodal, longer-gapped.
**[computed]** Dating is guessed-but-precise: 50–100% of marks carry the unsure
flag, yet most have month resolution. **[inference 85%]** You date to preserve
ORDER and local spacing, not absolute position — consistent with the ruled
"ordering IS drawable" and "never guess a position" teachings. The unsure flag
means "don't trust the axis position", not "don't trust the sequence".

## 5. Marks concentrate on one or two people; everyone else is context

**[computed]** The top-marked person carries 40–80% of a case's marks; 2–9
people carry any mark at all, out of 27–113 people in the diagram. **[inference
90%]** One index person (plus sometimes a spouse/child) is the observational
center; the other ~90% of people exist to give the marks a system to sit in.
The corpus never shows whole-family variable tracking.

## 6. Relationship symbols live in two distinct idioms

**[computed]** Six of seven cases: relationship symbols are mostly or entirely
UNDATED (case_03: 2 of 26 dated; case_41: 4 of 21; case_48: 0 of 3) — and the
undated set is rich: Inside/Outside pairs (triangles), Projection, Distance,
Conflict, Fusion. case_29 alone inverts this: 25 of 31 symbols dated, spanning
the timeline. **[inference 85%]** Two idioms, matching the handwritten-notes
finding independently: the dominant idiom draws the BASELINE EMOTIONAL
CONFIGURATION (standing triangles, chronic distance, projection routes — a
structural portrait, no time axis), and the second, used when observation is
dense enough, moves relationship process ONTO the timeline. Same construct, two
temporal registers.
**[computed]** Triangles are represented as Inside/Outside symbol sets
(case_03: 10 Inside + 7 Outside; case_41: 5 Inside + 3 Outside).
**[Q]** In your notation, does one triangle produce several Inside/Outside
symbols (per-leg), so symbol count >> triangle count?

## 7. Where uncertainty actually lives

**[computed]** Not in whether events happened (marks always carry words) but
in: axis position (unsure flags, 50–100% of marks), symbol dating (mostly
absent by idiom), direction semantics (text-valued directions), and coverage
(the years between clusters are unknowns, not quiet). **[inference 95%]** The
inter-cluster gaps are unobserved-not-calm — treating them as "stable periods"
would fabricate data. This is the single most dangerous default a
visualization could assume.

## 8. Constraints this hands phase B (not designs — constraints)

1. The drawable unit is the episodic cluster, not the year grid: 1–7 clusters
   per case, dense-recent, sparse-old.
2. Order and within-cluster spacing are trustworthy; absolute axis position is
   not (unsure regime) — a drawing that implies precision lies.
3. One case = one or two marked people + a system: the picture's foreground
   population is tiny even when the diagram is huge.
4. Variables come one-per-mark in a per-case dialect: a 5-lane variable grid
   would be ~80% empty everywhere; the case's own dialect defines its lanes.
5. Baseline configuration (undated symbols) and timeline process (dated marks)
   are different pictures of the same family and must not be forced onto one
   axis; case_29 shows the bridge state when symbols become datable.
6. Gaps are unknowns: empty timeline space must read as "not asked/not
   remembered", never as calm.
7. Every mark has words: text is always available on tap; nothing needs a
   synthetic label.

## 9. Open questions (all one-liners, answer any subset)

1. The per-case variable dialect: clinical signal or coding history? (§3)
2. Text-valued directions: keep as qualitative shifts or normalize? (§3)
3. One triangle = several Inside/Outside symbols? (§6)
4. Is case_29's dated-symbol idiom your current practice (i.e. the future), or
   case-specific?
5. The lone everything-moved point in case_29: deliberate or over-coded? (§2)
6. Are the small ancient clusters (2-4 marks, decades back) intake-remembered
   periods as inferred, or later-added archaeology?
