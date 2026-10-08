# Clusters

How the record's events become clusters. Rules first, model second.

## What a cluster is (ruled 2026-10-08, from job 021's reading of the sources)

A cluster is a run of events in the record during which the family's anxiety
stood higher than it did before and after: a period of stress against the
family's calm, in the books' own sense. It opens where something disturbs the
family's balance (a person added, a person lost, a person's position changed,
or several weighty events falling close together) and the disturbance, not the
opening event, is the cluster: the family's reactions carry it through specific
people and the people in a pair-bond with them. It closes where the record
shows the family settled: a symptom lifting, functioning coming back, a
settlement, or a span with no recorded shift long enough for that family to have
adjusted, judged against how close together the cluster's own events fall. Two
runs are two clusters when the record shows the family settled between them,
even when the same people, the same pair-bond and the same trouble recur: the
same people alone never joins two runs. A cluster is never a stage of the
household's life, never the family's ordinary level, and never the whole span of
a symptom that became chronic; those are what clusters stand out against. A
quiet span after a run of shifts is the ordinary sign that the family settled,
with the caveat that families misremember. It is named for the event that
opened it or the shift at its heart, with its time, in the person's own words
[Oracle: R-0836]. The passages behind this sit behind the book button on the
page behind a cluster's small i (doc/SCREENS.md).

The prompt carries that definition (the seven lines the books contradicted were
reworded on 2026-10-08 [Oracle: R-0836]), and the model still judges every edge
[Oracle: R-0374]. One thing is a check in code, because it is about the kind of
thing a cluster is and not about its edges:

**The ten-year check [Oracle: R-0837].** A returned group whose first and last
dated events are more than ten years apart (`MAX_SPAN_YEARS` in
`btcopilot/clusters.py`) is refused with the reason, "a group of more than 10
years is this family's ordinary level, not a disturbance of it; return the
groups inside it", and the model is asked again as every refusal is; after two
refusals the by-years fallback applies. The refusal is written to the
observations table as `cluster_refused` with check `too_long`, so the quality
dashboard counts it [Oracle: R-0780]. The rationale for the number, so it can be
judged rather than taken: the sources bound it on both sides. Above, the longest
run of dated events any source draws as one period of stress is five years, the
longest named family period a six-year plateau of illness, and the one decade
accepted as a single tag was events leading up to a death held together by one
man's long illness. Below, Bowen's typical stage of the household is "ten
years", and his own ten-year narrative chapter is explicitly several periods of
stress with calm between. Ten is the smallest whole number no wave on record
reaches and the first a stage does; five would refuse runs the books call one,
twenty would pass two stages. The check binds nothing inside the range the
sources place waves (hours to six years), so it does not touch the judgment
R-0374 protects, and the two tests that encode that freedom (joining proposals
792 days apart; a loose event joining 1581 days on) pass unchanged. Applying the
same number to the proposal's cuts or to a group's internal gaps would be a rule
about edges, which R-0374 rejects, and is not done.

**The overlap check [Oracle: R-0839].** The timeline is one line, so two
clusters never share a day. A returned grouping in which any two clusters' years
overlap is refused with the reason naming both by their dates ("The group 'A'
(2008-03-01 to 2011-09-01) and the group this person made, 'B' (2009-02-01 to
2011-06-01) overlap in time"), and the model is asked again; the refusal is an
observations row `cluster_refused` with check `overlap`, and after two refusals
the by-years fallback applies. A cluster's years are those the timeline draws,
its first dated event to its last (`span_of`, the same dates the ten-year check
reads), and a returned group is measured without the events of the person's own
clusters, which the write holds out of it. The person's own clusters count: a
model group straddling one is refused, and the prompt lists the person's own
clusters by name and years under GROUPS THIS PERSON MADE, so the model sees them
before its first answer. Two clusters that only touch on one day
are not overlapping (`overlapping` in `btcopilot/clusters.py` is strict on both
ends), because the page draws neighbouring pills apart at a seam
(`web/src/picture.ts`, `edges`), so touching is a closeness it can still draw as
two. The proposal shown to the model is left as the rules make it; the
fallback (`by_years`), which stores what it is given, joins proposals whose
years overlap into one, whatever their people (`_one_axis`), leaves out the
person's own events and any dated inside their clusters' years, and cuts a
proposal wherever one of their clusters falls (`_apart`), so the fallback never
stores an overlap either; groups that only touch stay two. A joined group running past ten years is
dropped rather than split, logged and written as a `cluster_failed`
observation, and its events wait for the next accepted regroup
[Oracle: R-0837, R-0840].

**A stored cluster that fails the check is not handed back [Oracle: R-0838].**
"Keep what is there" protects a reading, not a category error: a stored
model-made cluster that fails the ten-year check, or whose years overlap another
stored cluster's (the person's own included) [Oracle: R-0839], is left out of
the groups the model is told to keep, its id is offered nowhere in the answer's shape (an answer naming
it is refused as an unknown group), its events fall back to the proposal, and
the record change removes it, so a diagram holding one regroups on its next run.
Such a cluster also does not count as "the model's own groups already there"
when both answers are refused, so the by-years fallback replaces it.
`DETECTION_VERSION` was bumped to 6 so every diagram regroups on its next event
change; the production catch-up is `flask admin diagrams regroup --apply`
[Oracle: R-0772]. Not changed on this pass: `--apply` still hands the stored
groups that pass the check to the model as existing.

**Refused twice, the failing stored clusters are removed [Oracle: R-0840].**
When both answers are refused and at least one stored model cluster passes the
checks, nothing is regrouped, but every stored model cluster that fails the
ten-year or overlap check is deleted in one record change by the coach. Two
model clusters overlapping each other both fail, as neither has the better
claim to the years; one overlapping the person's own cluster fails and the
person's stays. Each removal logs a warning and writes a `cluster_failed`
observations row whose detail names the cluster, its dates, the check, and
`removed` with its id. The cache key is not advanced, so the next turn regroups.
A coach chip pointing at a removed cluster keeps the words it was written with,
and a tap on it does nothing.

**Data shown, not a rule.** Each proposed group the model is shown carries one
plain line before its events, "38 years and 4 months with nothing recorded
before this group" (or "first group in the record"), so the model reads the
silence instead of inferring it from two date strings; Kerr weighs "the time
spacing between events".

The fictional Hale record (`btcopilot/tests/test_clusters.py`: three runs in
1954 to 1955, 1994 and 1996 to 2001, a 1948 marriage and a 1998 death in none)
is the shape of the fault this fixes: on the old prompt and code one group of
all fourteen events, 1948 to 2001, passed every check and was stored. The live
case `btcopilot/tests/live/test_clusters.py` runs it k of n against the real
grouping call; the counts are in `doc/PROMPT_ENGINEERING_LOG.md`.

## The rules propose the candidates (revised 2026-09-22)

The rules no longer decide the clusters. They compute a **proposal** the model is
free to overrule whenever it says why, because a cluster is a chapter of the
story of family emotional process, found by judgement under Bowen theory, and no
fixed time window bounds one [Oracle: R-0371, R-0373, R-0375]. Only the floor of
three events is a wall.

Computed from `DiagramData` alone, no model call, in `btcopilot/clusters.py`:

- A cluster is seeded by a **nodal event or a shift**: one of the nodal kinds
  (death, married, divorced, separated, moved), or any event carrying a
  symptom, anxiety, relationship, or functioning value. [Oracle: R-0054 — no
  absolute values exist, only relative shifts, captured in clusters.] The nodal
  kinds are `NODAL_KINDS` in `btcopilot/clusters.py` and compare against
  `EventKind`, not raw strings.
- A **candidate** is a seeding event plus every event within **18 months** either
  side of it that shares a person, or shares a couple, with it. Sharing a couple
  means each event names a member of the same pair-bond. The 18 months are a
  suggestion, not a boundary: an event years outside it joins a cluster when the
  model says in one sentence what in the record puts it there. A structural event
  (birth, marriage, divorce, death) opens a chapter and the shifts recorded
  around it are what that chapter is about; consequences years on can still
  belong [Oracle: R-0375].
- **Scaffolding never joins.** A structural event that is neither nodal nor
  carries a shift — in practice a birth or an adoption — and is dated before the
  first seeding event is age and generation scaffolding, diagnostically inert.
  [Oracle: R-0037, R-0038.] The predicate reads `EventKind`, never a string. A
  consequence worth knowing: an early marriage is nodal, so it opens the recorded
  period and the births after it are no longer scaffolding.
- Candidates sharing any event **merge**.
- Two years with no nodal event and no shift inside a merged candidate **split**
  the proposal, at the widest silence between the two seeding events either side.
  This too is only a suggestion to the model.
- A candidate holding fewer than **three** events is **not a cluster** — a lone
  shift with no related move, or a bare pair, stays dots on the line. The
  minimum is `MIN_CLUSTER_EVENTS` in `btcopilot/schema.py`, one number for every
  writer (see "The floor is enforced at the write" below).

Parameters `SPAN_DAYS` and `CALM_GAP_DAYS` are module constants and shape only
the proposal. `MIN_CLUSTER_EVENTS` is the one ruled number and is enforced twice,
at the model's answer and again at the write. Undated events never enter a
candidate.

## Open for Patrick

**The record has no nodal flag.** The `Event` dataclass at `btcopilot/schema.py:317`
has no `nodal` field and never has; the word does not appear in that file. The
owner ruled the flags in the old corpus are used inconsistently and are to be
ignored (`doc/NATURE_OF_THE_DATA.md`). So nodal here means the event
kind — death, married, divorced, separated — which is what the intake engine has
always meant by it (a move stopped being a kind of its own on 2026-09-22
[R-0364], and a noted event does not seed a cluster), and a cluster is seeded by one of those kinds or
by any recorded shift. If Patrick wants a per-event nodal flag it is an
additive schema field and one more term in the seeding predicate.

## The model decides, names and explains (revised 2026-09-22)

It receives the clusters the record already has, the candidates the rules
propose, and the events that fell outside them. It returns one entry per final
group: `id` when the group already exists, `eventIds`, `name`, `reason`, and
`change`.

- `reason` is one sentence saying what the record shows the events have in
  common: who they involve, when they happened, which shifts were recorded.
  Required on every group. It is not an interpretation and not a claim the events
  do not carry.
- The model may **join** two candidates, **break** one apart, or **pull in** an
  event that fell outside them, including one years outside the proposed window.
  Any group that is not a candidate exactly as given, and any stored cluster
  handed back with different events or a different name, requires `change`: a
  sentence in story saying what in the record made the old shape wrong. Changes
  are logged and given to the coach.
- It may not name an event it was not given, put one event in two groups, or drop
  a seeding event. [Oracle: R-0076 — the model may group and name, never invent
  members.]
- A name, reason, or change containing a diagnostic or popular-psychology word
  the prompt's terms do not contain (`OUTSIDE_WORDS`) is rejected too.

- A group holding fewer than `MIN_EVENTS` events is rejected. A group that only
  falls under the minimum because a grouping the user made takes its events is
  dropped instead, silently — those events go back to being dots.

Validation rejects a violation with a sentence; the prompt is re-asked once with
that sentence. Each refused answer writes an observations row `cluster_refused`
naming the check; when both are refused, a `cluster_failed` row is written and the
rules' groups are stored titled with their years ("2024–2026"), unless the model's
own groups are already there, which are kept [Oracle: R-0517, R-0780]. The answer's
schema offers `id` only as one of the record's stored group ids, and not at all when
it holds none: offered a free-text id, the grouping model made one up for every new
group and both answers were refused (production, 2026-10-05). An answer cut off at
its token limit, one that is not the JSON asked for, and a call that errors are
refused the same way, so grouping never fails the coach's turn; the limit is 4096
tokens of room for thinking plus 24 per event the record may group. After a fix to
the grouping, `flask admin diagrams regroup` lists the records whose events changed
since their last grouping or that have events and no groups, and `--apply` regroups
them, each as one change row `diagrams undo` takes back [Oracle: R-0772].

## What is deliberately undefined

No ruling says what makes a set of events one cluster, so neither the code nor
the prompt says it. The prompt gives the model the four variables and the
relationship mechanisms from `doc/specs/BOWEN_THEORY.md`, the relationship moves
the record's own enum holds, and the rulings above — then forbids everything
else. `CONTEXT.md` is not cited: its domain section is a pointer to the same
theory spec and carries no cluster content.

## The prompt

Every prompt is a file. The public default (`btcopilot/prompty/cluster.prompty`)
asks for the grouping in plain words and nothing clinical. The terms live only in
the encrypted private prompt (`private/prompts/cluster.prompty` and its fragments),
quoted rather than referenced, with the closed-vocabulary instruction: use only
the terms given, no outside Bowen theory, family therapy, or popular psychology.
`fragments/cluster_terms.md` carries what opens and closes a cluster and that a
reading already given to a record is kept rather than rebuilt.

## What a stored cluster holds

Name, reason, source, event ids, and the dates they span. The invented pattern
vocabulary (anxiety cascade, triangle activation and the rest) and the dominant
variable are removed from the schema and from persistence; they came from earlier
AI output, not from Patrick. Old rows carrying them are not migrated — the next
regrouping overwrites them.

`reason` is additive on `schema.Cluster`, is in `STORED_FIELDS` so a change row is
written for it, reaches the record only through `record.apply` with author Coach,
is served on the timeline payload, and is given to the play-by-play prompt through
the cluster line [Oracle: R-0074]. A user correction through `edit_cluster` sets
`source=user` and clears the coach's reason.

## When clusters are recomputed (ruled 2026-09-08)

Clusters are recomputed for the **whole record, from scratch**, after any coach
turn that adds or changes an event. A message that adds no event, or only adds
or changes a person, never triggers a recompute. A cache key hashes the SARF
fields on every event (symptom, anxiety, relationship, functioning) plus
`DETECTION_VERSION`; even on an event-changing turn, if that key still matches
what is stored, the model is not called.

A cluster the user corrected (`source=user`) is never touched by a recompute —
those events are held out of detection entirely, and a recomputed cluster that
overlaps a user-corrected one yields the overlapping events to it.

**A cluster is sculpted, never rewritten (ruled 2026-09-22, R-0374).** Every
stored cluster the model made is handed to it with its id, its name and its
events. It keeps all three by default. It may reshape one only when it returns
`change`: one sentence, in story, saying what in the record makes the old shape
wrong. A better-sounding name is not a reason. Validation rejects an entry
carrying an id whose events or name differ from the stored cluster and says
nothing in `change`, and rejects any id the record does not hold.

Ids come from the model's own statement of which stored cluster each returned
group is. The old heuristic that re-attached ids after the fact by event overlap
is gone. A chip placed in an earlier coach message therefore keeps resolving to
the same cluster after a recompute, and the write refuses a detected group whose
id belongs to a cluster the user made.

Every `change` sentence of a turn is carried to the coach. The regrouping runs
inside the agent loop, after the step that moved an event and before the step
that answers, so the sentences sit in the system prompt of the call that
produces the reply under the heading "What changed in the story since last
time". They also go out on the turn as a `story` event, which the page draws
nothing for: nothing about a regrouping is ever drawn on the picture, and the
coach never says "cluster", "group", "chapter", "period" or "timeline", never
that an event was added, never that anything was regrouped [Oracle: R-0373]. The
fragment `coach_story_shape.md`, included in the coach's system prompt, holds
that instruction.

**Nothing selective exists.** There is no logic that limits recomputation to
only the clusters touched by the new event — it is whole-record every time.
Cost is one model call per event-changing turn, for the whole record.

A change to the candidate rules or the grouping prompt bumps `DETECTION_VERSION`,
which changes the cache key, so the next event-changing turn re-clusters the
whole record even though no event itself changed.

Patrick ruled to try it as it is and judge it during the beta.
[Oracle: R-0208] Selective invalidation is not being built now — revisit only
if whole-record recompute shows a problem in use.

## The floor is enforced at the write (ruled 2026-09-08)

A cluster holds at least three events. The number lives in `btcopilot/schema.py`
as `MIN_CLUSTER_EVENTS`, because every writer imports schema and schema imports
nothing.

It is enforced in `record._commit`, which is the one function every writer
reaches: `record.apply`, `record.undo` (which builds its inverse deltas and
commits them without going through `apply`), the coach's `edit_cluster` tool,
and the regrouping pass. The check runs on the record the write would leave
behind, not on the deltas, because a cluster's fields arrive as separate deltas
and only the assembled item says how many events it ends up holding. It raises
before anything is written, so the transaction does not commit.

A write answers for the clusters it touches, not for the ones it inherited. A
turn that never mentions a cluster is never held to it, so a grouping stored
under the older floor does not block unrelated work — but any write that touches
that grouping fails until it holds three.

Three further gates sit upstream of the write, and they exist for the message
they give, not for the guarantee:
- the rules never propose a candidate under the minimum;
- validation rejects a model group under it and re-asks once with the reason;
- detection raises if a group reaches it already under the minimum, which
  separates "the producer is wrong" from "a grouping the user made took these
  events", the second of which drops the leftovers silently.

The coach's `edit_cluster` tool refuses a group under the minimum, and refuses a
new cluster with no events at all, with words the model can act on. The tools
also translate the write's refusal into those words, in both the apply and the
undo path, so a turn that trips the floor comes back as a sentence rather than a
5xx. That matters for a grouping stored under the older floor: renaming it
carries no events, so nothing catches it until the write, and the coach is told
to add an event or remove the grouping.

What the floor does NOT do: it cannot protect a record from a server running
older code, which is what caused the incident below. The invariant lives in the
same codebase as everything else, so a process that predates it does not have
it. It closes the undo path, the coach's tools and the detection path for any
process running current code. Making staleness itself impossible is separate
work, and not funded.

Fixture and seed data written through `set_diagram_data` bypasses `record`
entirely and is not covered. Those are dev fixtures, and the fix there is the
data, not a second rule.

## Only a restarted server groups by the current rules (learned 2026-09-08)

`DETECTION_VERSION` makes a *stored* grouping stale; it cannot make a *running
process* stale. A long-running sandbox server keeps the module it imported at
start, so a rules or prompt change reaches real turns only after that server is
restarted. On 2026-09-08 a server started before the detection-version
change stored one-event clusters on Patrick's record hours after the
two-event minimum was committed. It was identified by the cache key it wrote:
that key is reproduced only by hashing the events with no detection version in
the hash, which is the code from before 15:08 that day, while both later
versions produce different keys. Restart the sandbox after every
commit that touches this module, and read a surprising stored grouping as a
question about which code the server was running before treating it as a rules bug.

## How to re-run clustering on a record by hand

The resync path is `btcopilot.clusters.sync(diagram_id, turn_id=...,
user_id=..., session_id=...)` — the same function a coach turn calls. It
re-detects clusters for the whole record and writes the result through
`record.apply` with `author=Coach`, so it needs a `turn_id` the way any other
record change does. Back up the database first — `sync` writes through the
normal delta/apply path, so a mistaken run is just another change to correct,
not something reversible in place.

## What a cluster is, from the sources (2026-09-22)

The books have no word "cluster". Their word is **period**, and a period is
bounded by stress and symptoms, not by the calendar: "There may be several
periods in a family's history when a series of stressful events converged and/or
when symptoms were prominent" (Family Evaluation, line 3373).

**What opens one.** A disturbance of the family's balance: "An event, or more
likely a series of events, can disturb the balance of a relationship system and
trigger symptoms" (Family Evaluation, 2875). Bowen is narrower: the balance "is disturbed by
either the addition of a new member or the loss of a member", and a loss may be
physical, functional, or emotional (Family Therapy in Clinical Practice, 2470;
quoted again in Gilbert 2006, 781).

**What closes one.** The return of the earlier level of anxiety. "If family
anxiety soon returns to 'pre-event' levels, the symptom will usually be
short-lived" (Family Evaluation, 2881); if anxiety instead binds around the
symptomatic person, the trouble becomes chronic (same line). Bowen puts the same
boundary as a new balance reached, and its length varies with the family and
with the size of the disturbance (Family Therapy in Clinical Practice, 2470).
Lengths on record run from several months to several years (Family Evaluation,
3213, 2885).

**What belongs together.** Weight and nearness in time: "The magnitude of the
events, the number of events, and the time spacing between events are used to
determine the level of stress a family is under" (Family Evaluation, 3355).
Dates lining up between an event and a symptom's onset, "suggestive" and never
proof (3127, 3569). A symptom lifting in one person as it appears in
another is one story, not two (3179). Aftershocks months or years later still
belong to the event that started them, and without that knowledge the sequence
"is treated as separate, unrelated events" (Family Therapy in Clinical Practice,
2474, 2478). One period turns on one key shift; earlier shifts set the stage and
later ones sustain, and the timeline is what settles which is which (Havstad,
line 58). A structural event is not itself a shift — "A birth is not an SARF
shift, and neither is getting married or divorced or death" (coders, 2026-04-13,
line 14) — it is placed on the line and the shifts in response are recorded
separately.

**When a reading may change.** "Assessments are not written in stone, but are
continually modified as new information comes to light" (Family Evaluation, line
37). The bar for hardening a link is repetition, not one coincidence (3571). The
coders are narrower: code the shift once, and add another entry only when a
genuinely different date appears (2026-02-23, line 241; 2026-04-13, line 44).

**The rule.** A cluster opens where an event, or a run of events, disturbs the
family's balance — someone added, someone lost, someone's position changed. It
closes where anxiety comes back to the level it sat at before. Events belong to
the same cluster when they are close in time and weighty together, when a
symptom's date lines up with them, when trouble moves from one person to another,
or when they are the later consequences of the opening event. A cluster is kept
as it stands and is reshaped only when new information gives a strong reason —
a genuinely new date, or a symptom that turns out to sit elsewhere. The coach
never says "cluster" and never says an event was added to one. It speaks of the
story: what happened, what the record shows changed, and why it matters now.

## The message the picture must carry when a record holds many events (2026-09-22)

At a glance a person should take in two things: where their history gathers into
a few clusters, and that trouble moved between people and between the four
variables rather than sitting still. The books warn that a picture risks showing a static
situation instead of a moving one, and that events read as unrelated unless
something ties them. The picture's job is to make one tie visible unasked.

The person must never be asked to count events, to scan a dense cluster, to
compare how full one year looks against another, or to work out for themselves
which events belong together. A crowded cluster means it was remembered, not that
it was worse.

Ruled 2026-09-23 [R-0376]: a cluster's drawing carries a single turning point —
when things changed hands — plus who is carrying it now, the event that started
it, later events on tap, and closeness of dates read as a hint, not confirmed
cause. No tallies of events. A change from one look to the next is spoken by the
coach, never drawn [R-0372]. Neither is built yet; the model does not name a
turning point or say who carries the trouble.
