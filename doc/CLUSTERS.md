# Clusters

How a diagram's events become clusters. Rewritten 2026-10-08 (FD-375, job 034)
on Patrick's reading; the earlier pages are in git history.

## What a cluster is

A cluster is a period when difficulty was heightened for someone in the family,
held loosely as a hypothesis that something bigger shifted in the family around
then: a birth, a death, a move, someone's position changing. It is inferred from
shifts and events piling up; anxiety is never recorded, only inferred, and a
shift can be a fall (functioning down) as well as a rise. It needs no visible
opening event and no definite end; it ends where things look settled. It is
named for the hypothesis (what seems to have shifted, or the event that
dominates it), never for its length or its years alone. The family is one
emotional unit, so one reading of it never has two periods over the same days,
and most events sit outside any period [Oracle: R-0841, R-0845].

The person's own period is the usual starting point, because families routinely
lose the link between their own troubles and what else was going on. It is a
hypothesis like the model's. The model sees it marked as the person's and may
change it like any other, fold it into a wider one, or let it go [Oracle: R-0843]. The
model renames and reshapes any period freely as the diagram grows [Oracle: R-0842].

## What the books say (job 021, theory.md sections 2.9 to 2.11)

- "Many symptomatic eruptions can be timed exactly with other events in the
  nuclear and extended family fields" (T190); dates "may be found to correlate
  with information that is gathered later in the interview" (T193); "a striking
  time sequence", never causality (T199).
- "It is so routine for family member to obliterate any connectedness between
  this death or this traumatic event and the events that follow" (T200).
- "do a 'fix' on the entire family system, including place, date, ages of each
  person in the household" (T192); a fast onset "deserves a thorough exploration
  for disturbance in the extended family" (T204).
- "listen to the incidence of these phenomena" (T203): the pile-up is the signal.
- No ceiling on a period's length is stated anywhere; the start can be
  unplaceable, the end may never come, a quiet span may be a gap in the telling,
  and a name is revised as the clinician gets clearer (section 2.11, T189).

## The coach stays curious

When the person's own topic leaves room, and never in place of it, the coach asks
what was going on in the extended family around a period's dates: parents,
grandparents, their brothers and sisters; deaths, illnesses, moves, births. It
asks and never tells the person the link. What comes in is new events, and the
next regroup revises the period and its name. The lines are in the coach prompt's
story fragment; the live case is `btcopilot/tests/live/test_clustercuriosity.py`
[Oracle: R-0841].

## How detection runs (`btcopilot/clusters.py`)

1. The rules find runs of related events with no model call (`candidates`): an
   event within 548 days of a nodal event or shift about the same people or
   pair-bond, cut at two years with no shift, at least three events. Early births
   before the first nodal event or shift are scaffolding and held out. The runs
   go to the model as a hint only, each with the silence before it in words; they
   are never stored.
2. The model gets every event, the stored periods (the person's own marked "the
   person drew this period", with their reason), and the hint, and returns the
   periods as they should stand: id when one grew out of a stored one, events,
   name, reason, and a change sentence when it is not as given.
3. The code backstops only. Per period: events it was given, a stored id, a name,
   a reason, no outside vocabulary. Then periods sharing a day or an event are
   merged into the one holding more events. Then at least three events and no
   more than ten years [Oracle: R-0846, R-0837]. A first answer with any fault is
   asked once more with the reasons; on the second, a failing period is dropped
   and the rest kept. Periods touching on one day stay two: the page draws them
   apart at a seam.
4. Every refused answer, dropped period and merged period is a cluster_refused
   row in the observations table carrying the model's own answer for it (name,
   event ids, first and last date), and a warning in the log [Oracle: R-0844].
5. No usable answer twice (unreadable, cut off, failed, or nothing kept): the
   stored periods that pass stay, a stored model period over ten years is
   removed, and nothing is ever named after its years; with nothing stored, the
   line shows the events alone [Oracle: R-0840, R-0844]. A stored model period
   over ten years is never handed back to the model as existing [Oracle: R-0838].
   Nor is a stored model period named only by its years ("1996–2001"): it is
   dropped with a warning and a cluster_failed row (check years_name), the
   person's own untouched [Oracle: R-0844, R-0840].
6. Every stored period the answer did not return is removed, the person's own
   included. A period returned exactly as stored keeps its source; any other is
   the model's.

## When it runs

After any coach turn that adds or changes an event, when the cache key (the
events' dates and shifts plus `DETECTION_VERSION`, now 9) differs from the
stored one; `flask admin diagrams regroup` reruns diagrams that are behind. A running
server keeps the module it started with, so restart a sandbox after a change
here. The floor of three events is enforced again at the write.

## What a stored cluster holds

Name, reason, source (model or user), event ids, and the dates they span
[Oracle: R-0205]. The header over the line says the name once, in the path, and
the years and count once, under the line (doc/SCREENS.md).
