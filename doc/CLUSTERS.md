# Clusters

How the record's events become clusters: a clinician's survey by the model,
judged cluster by cluster by the code. Rulings: R-0841 (the premise and the
three judgements), R-0842 (renaming), R-0843 (nothing named after its years),
R-0844 (events may stay loose), with R-0837, R-0839 and R-0840 standing.

## What a cluster is

A period when the family was stirred up: a disturbance, often a death, shakes
the family, and in the months and years after it anxiety spreads and minor
problems become major ones at vulnerable points. Bowen surveyed every family
for such periods; Family Evaluation asks about "periods of major stress on the
family" one at a time and weighs the magnitude, number and spacing of events.
Between periods a family has quiet years, sometimes decades, and most of a
history sits outside any period. Nobody drew edges. The timeline exists so a
person sees on their own family's line where things piled up and where it was
quiet, in broad strokes [Oracle: R-0841]. The passages behind this sit behind
the book button on the page behind a cluster's small i (doc/SCREENS.md).

## What the model does

Given the record's events, the clusters the person made (shown as fixed, with
their years, their events held out of everything else it sees), its own
earlier clusters (shown with their ids) and the rules' proposal as a hint, the
model points to the periods and names each for what the family was going
through, with a one-sentence reason. It leaves most events out
[Oracle: R-0844]. It may rename or reshape its own earlier clusters freely; no
reason is required, and a kept or reshaped cluster keeps its id so the coach's
earlier chips still point at it [Oracle: R-0842]. The prompt is
`private/prompts/cluster.prompty` with its terms fragment, and the public copy
`btcopilot/prompty/cluster.prompty`; both say this in a few plain lines.

The hint is `candidates()` in `btcopilot/clusters.py`: every nodal event
(death, marriage, divorce, separation) or recorded shift gathers the events
within 18 months sharing a person or a pair-bond, runs that touch merge, a
silence of two years between marked events cuts a run, and a run under three
events is no hint. Early births are scaffolding and held out [Oracle: R-0037,
R-0038]; so are the person's own clusters' events. The hint is never stored.

## What the code judges, cluster by cluster

One model call per regroup; a second only when the first answer cannot be read
at all (not JSON, no clusters), and when that one cannot be either nothing
changes this run. Every returned cluster is kept except [Oracle: R-0841]:

1. one spanning more than ten years (`MAX_SPAN_YEARS`; ten to the day passes):
   that is the history, not a period [Oracle: R-0837];
2. one overlapping a cluster the person made: the person's reading wins
   [Oracle: R-0839];
3. one overlapping a kept model cluster: one line, so the one with more events
   stays and the other goes [Oracle: R-0839].

Two clusters that only touch on one day do not overlap: the page draws
neighbouring pills apart at a seam. A cluster left with fewer than three events
of its own is dropped too, since the write refuses it [Oracle: R-0215], as is
one named in words outside the given terms [Oracle: R-0195]. An event the
record does not hold is stripped from the cluster that named it; an id the
record does not hold is ignored; a cluster returned twice is merged. Clusters
are judged largest first, and an event already in a kept cluster is not in a
second one. A dropped cluster's events stay as dots, no one is asked again, and
the other clusters of the answer are kept. Each drop is a warning in the log
and an observations row `cluster_refused` whose detail carries the check and
the model's whole answer for that cluster: name, first and last date, event
ids [Oracle: R-0780].

A stored model cluster that now fails judgement 1 or 2, or overlaps another
stored cluster, is not shown to the model as its own and is removed, with a
warning and an observations row; the person's own clusters never fail
[Oracle: R-0838, R-0840]. There is no fallback: when nothing passes, the line
shows the events alone, and nothing is ever named after its years
[Oracle: R-0843].

## When clusters are recomputed

After any coach turn that adds or changes an event, for the whole record. A
cache key hashes the four variables on every event plus `DETECTION_VERSION`
(now 8); when it matches what is stored the model is not called. A change to
the hint's rules or the prompt bumps the version, so every record regroups on
its next event change; `flask admin diagrams regroup --apply` is the catch-up
[Oracle: R-0772]. A cluster the person made (`source=user`) is never touched.
Nothing about a regrouping is drawn; the coach never says "cluster"
[Oracle: R-0372, R-0373].

## What is stored and the floor at the write

A cluster holds name, reason, source, its events and the dates they span
[Oracle: R-0205]. A cluster holds at least three events; `MIN_CLUSTER_EVENTS`
in `btcopilot/schema.py` is enforced at the write in `record._commit`, so no
writer, the coach's `edit_cluster` tool and the undo path included, can store
fewer. Fixture and seed data written through `set_diagram_data` bypasses it.

## The header

An open cluster says each fact once: the path over the line reads
"Timeline › <name>" (the years alone for a cluster with no name) and the words
under the line read "<years> · <count> events" [Oracle: R-0767, R-0583,
R-0841]. The page behind the small i shows the reason, the years and the count,
each event with its year, and the book button [Oracle: R-0213, R-0691].

## Re-running by hand

`btcopilot.clusters.sync(diagram_id, turn_id=..., user_id=..., force=True)`,
the same function a coach turn calls, writes through `record.apply` as the
coach, so a mistaken run is another change to correct, not something reversible
in place. A long-running sandbox server keeps the module it imported at start:
restart it after a change to this module.
