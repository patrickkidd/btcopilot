# Clusters

How a diagram's events become clusters. Rewritten 2026-10-08 (FD-375, job 034)
on Patrick's reading; the earlier pages are in git history.

## What a cluster is

The definition of a cluster as the case report's evidence in time, with its book lines, is in
[CASE_REPORT.md](CASE_REPORT.md) [Oracle: R-0850].

The rules as built (FD-381, 2026-10-14) are the approved rules page,
`btcopilot-sources/research/clusters/rules-2026-10-14.html`, A1 to A9 [Oracle: R-0850].

- A cluster may open when someone joins or leaves the family, or when a key
  member's functioning changes: an addition, a loss, a threatened loss, a
  departure, a marriage, a cutoff, a fall in a key member's functioning. Which opening
  mattered is the grouping call's judgement of the lost or changed person's
  importance, never a list of event kinds in code. Trouble may begin before the
  opening event (A2, A5).
- A shift supports a cluster only when it is a rise in symptom or anxiety, a
  fall in functioning, or a relationship shift; a drop in anxiety or a rise in
  functioning does not. The shifts may be anyone's in the extended family. An
  event whose date is unknown opens nothing and supports nothing (A4, A9).
- A cluster is named by the change that opened it and its years, never by the
  person's trouble (A6). The family is one unit: two of the app's periods never
  share days [Oracle: R-0845].
- The person's own periods are kept as they drew them and judged against the
  data like the app's; an unsupported one stays shown as the person's (A7).
  The periods the person names when the coach asks when the most was going on
  are stored as theirs, source `user` [Oracle: R-0853].
- The app never deletes a cluster: one that fails a check is set aside (stored
  with `setAside`, not drawn) (A8).

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

1. The rules find runs with no model call (`candidates`): every dated event
   within 548 days of a supporting shift, anyone's, cut at two years with no
   supporting shift, at least three events. Births and adoptions more
   than 548 days before the first supporting shift are scaffolding and held out.
   The runs go to the model as a hint only, each with the silence before it and
   its count of supporting shifts; a run with fewer than three is offered too
   (A1) [Oracle: R-0850]. The prompt says a period is stronger with three or
   more and one with fewer may stand when its events belong together, its
   reason saying so.
2. The model gets every event, the stored periods (the person's own marked "the
   person drew this period"), and the hint. The 548 days and the ten-year cap are
   both given as suggestions (A3). It returns the app's periods: id when one grew
   out of a stored app period, events, name, reason, `openingId` for the event
   that opened it, and a change sentence when it is not as given. The person's
   ids are never offered in the answer's shape.
3. The code backstops: known events, a name, a reason, the opening among its
   events, no outside vocabulary, no word the person's trouble is told in (the
   words of symptom events' descriptions not used elsewhere), no days shared with
   the person's own period. Then the app's periods sharing a day or an event are
   merged into the one holding more. Then at least three events and no more than
   ten years [Oracle: R-0846, R-0837]. Fewer than three supporting shifts never
   refuses a period: it counts against it (A1), on that cluster's Against line of
   the coach's guess (step 8) [Oracle: R-0850]. A first answer with any fault is
   asked once more with the reasons; on the second, a failing period is dropped,
   except one still named by the trouble, which is kept as "A change in the
   family, <years>".
4. Every refused answer, dropped period and merged period is a cluster_refused
   row in the observations table with the model's own answer [Oracle: R-0844].
5. Before the call, every stored app period meets the same checks as a returned
   one (three dated events, ten years at most) and is
   not named only by its years; one that fails is never handed back, and is set
   aside with a cluster_failed row naming it and its years [Oracle: R-0838,
   R-0844, R-0840, R-0850]. The person's own are never set aside, only judged
   (A7) [Oracle: R-0853]. No usable answer twice: the stored periods that pass
   stay, and when the answers were refused (not when the call never answered)
   the cache key is written, so no turn makes the same calls again until the
   events or the person's answers change.
6. Every stored app period the answer did not return is set aside. The person's
   own are never changed by a regroup.
7. The person's periods [Oracle: R-0853]. The call also gets the person's
   answers to the `most_going_on` item (each closed question's `answer`, the
   message it cites) and their birth date. For each period named there it
   returns their name for it and their sentence, both copied from the message,
   and its first and last year. The code writes it as a cluster with source
   `user` holding every dated event in the family inside those years, its dates
   the first and last of them. It is not written, and is a cluster_refused row
   instead, when the message is not one of the answers, the name or sentence is
   not the person's words in order, the years are missing, the years hold fewer
   than three events, or it shares days with a stored period of theirs or one
   read before it in the same answer. None of these is asked again. The app's
   periods never share their days. Once written it is the person's like any
   other: never reshaped, judged by `judge` with the same checks, kept and shown
   when unsupported.
8. `judge(cluster, data)` reads any stored period against the data: its
   supporting shifts, whether they are one person's run, its opening (the stored
   `openingEventId`, else its first change in the family), and the days from the
   opening to its first and last supporting shift, negative when the trouble came
   first (A3, A9). It is not stored. The case report's refresh reads it for every
   drawn cluster, and a cluster with fewer than three supporting shifts gets that
   on its Against line (doc/CASE_REPORT.md). A cluster whose supporting shifts
   are all one person's is that person's run: the coach's guess says so, and its
   Open line asks about the others in the family then (A9) [Oracle: R-0850].

## When it runs

After any coach turn that adds or changes an event, when the cache key (the
events' dates, date certainty and shifts, the message ids of the person's
answers to when the most was going on, plus `DETECTION_VERSION`, now 13)
differs from the stored one; `flask admin diagrams regroup` reruns diagrams that
are behind. Version 12 regroups every diagram on its next event change, so
periods set aside only for too few supporting shifts are offered again; version
13 does again, with runs of fewer than three supporting shifts in the hint. A turn
that only closes the `most_going_on` question, with no event change, does not
regroup; the next event change or `regroup` writes the person's periods.

## What a stored cluster holds

Name, reason, source (model or user), event ids, the dates they span, the opening
event id, and whether it is set aside [Oracle: R-0205, R-0850].
