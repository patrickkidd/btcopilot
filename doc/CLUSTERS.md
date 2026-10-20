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
  event whose date is unknown opens nothing: it is never a cluster's opening
  event, and is otherwise offered, held and counted as support like any dated
  event, its certainty shown to the grouping call (A9).
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
   person drew this period"), and the hint. The 548 days only pick the hint's
   events and are not in the prompt. The prompt gives no usual length: a period
   ends where the events show the family settled, judged against how close
   together its own events fall (weeks apart, a few quiet months end it; a year
   apart, a longer quiet), as the theory review found no source derives a number
   (research/clusters/theory.md 3.3, 3.6 in the corpus) [Oracle: R-0836]; nothing
   over ten years is one period [Oracle: R-0846]. It returns the app's periods: id when one grew
   out of a stored app period, events, name, reason, `openingId` for the event
   that opened it, and a change sentence when it is not as given. The person's
   ids are never offered in the answer's shape.
3. The code backstops: known events, a name, a reason, the opening among its
   events, an opening whose date is known, no outside vocabulary, no word the
   person's trouble is told in (the words of the descriptions of the person's
   own rises in symptom or anxiety and falls in functioning, compared by their
   first four letters, less those another event, an event kind, a name, a word
   for a relative or a common word also uses), no days shared with
   the person's own period. Then the app's periods sharing a day or an event are
   merged into the one holding more. Then at least three events and no more than
   ten years [Oracle: R-0846, R-0837]. Fewer than three supporting shifts never
   refuses a period: it counts against it (A1), on that cluster's Against line of
   the coach's guess (step 8) [Oracle: R-0850]. A first answer with any fault is
   asked once more with the reasons; on the second, a failing period is dropped,
   except one still named by the trouble, which is kept as "A change in the
   family, <years>", and one still opening at an event of unknown date, which is
   kept with no opening. A stored app period whose name breaks the naming check
   is handed to the call marked "named by the person's trouble", and the call
   renames it under its id (A6).
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
   own are never changed by a regroup. A period holds every event with a stored
   date, however sure, on or between its first and last day, whichever events
   the model named: an event added inside a cluster's years joins it at the next
   detection, decided by the code [Oracle: R-0873].
6a. A new app period that opens at no live app period's opening event, proposed
   while the diagram has a live app period, is stored set aside with
   `proposedAt`, the cache key of that detection, and is never handed to the
   model. When the next detection proposes a period opening at the same event,
   that row is shown under its id with the new answer's days and name, and
   `proposedAt` is cleared; not proposed again, it stays set aside with
   `proposedAt` cleared. A diagram's first detection and a from-scratch catch-up
   show their periods at once. A set aside the person made carries no
   `proposedAt` [Oracle: R-0873].
7. The person's periods [Oracle: R-0853]. The call also gets the person's
   answers to the `most_going_on` item (each closed question's `answer`, the
   message it cites; for a question closed as answered before that link was
   written, the person's message in the turn whose change row closed it) and
   their birth date. For each period named there it
   returns their name for it and their sentence, both copied from the message,
   and its first and last year. The code writes it as a cluster with source
   `user` holding every dated event in the family inside those years, its dates
   the first and last of them. It is not written, and is a cluster_refused row
   instead, when the message is not one of the answers, the name or sentence is
   not the person's words in order, the years are missing, the years hold no
   event, or it shares days with another stored period of theirs
   or one read before it in the same answer. None of these is asked again. A
   period read again under the name of one of theirs already stored is that
   period: the new reading replaces the stored copy's events, dates and
   sentence under its id. The app's periods never share their days. Once
   written it is the person's like any other: never reshaped by the app,
   judged by `judge` with the same checks, kept and shown when unsupported. A
   dated event told later inside its days joins it at the next regroup, so it
   is judged against the data as it grows (rule A1 counts the shifts added
   later against a cluster's span); its name, sentence and days stay as
   written [Oracle: R-0853, R-0850].
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
answers to when the most was going on, plus `DETECTION_VERSION`, now 16)
differs from the stored one; `flask admin diagrams regroup` reruns diagrams that
are behind. Version 12 regroups every diagram on its next event change, so
periods set aside only for too few supporting shifts are offered again; version
13 does again, with runs of fewer than three supporting shifts in the hint;
version 14 does again, with events of unknown date offered, the wider naming
check, and answers found through the change log; version 15 does again, with a run seeded only at a shift whose date is known, the people offered with what each is to the person, and every run of three or more supporting shifts returned as a period or declined with a reason [Oracle: R-0850, R-0856]; version 16 does again, with the person's period read again from their answer under the same name replacing its stored copy's events and sentence, no longer refused as overlapping it; the no-overlap rule holds between different periods [Oracle: R-0853]. A turn
that only closes the `most_going_on` question, with no event change, does not
regroup; the next event change or `regroup` writes the person's periods.

## Catch-up

After the deploy carrying FD-381, with a database backup first: `flask admin fd381-catchup plan` saves a plan with no model call, `apply --plan <file>` regroups each diagram the plan names through `clusters.sync(force=True)`, the function a turn runs, and sets the diagram's `case_report_forced_out_of_date` where the plan marks the case report (doc/CASE_REPORT.md), and `undo --plan <file>` takes both back [Oracle: R-0772].

## What a stored cluster holds

Name, reason, source (model or user), event ids, the dates they span, the opening
event id, whether it is set aside, and, while it waits for a second detection,
`proposedAt` [Oracle: R-0205, R-0850, R-0873].

## When a cluster looks wrong

Patrick signed the expected clusters of the `deep` case on 2026-10-16: three clusters, and two
hypotheses scored neither way [Oracle: R-0857]. A session started on "evaluate this cluster
discrepancy" follows these steps.

1. Evidence: write Patrick's question and what he saw, quoted, into the session before anything
   else (diagram, dates, the clusters shown, the clusters he expected). A new real case is evidence
   too.
2. Re-ground: read btcopilot-sources `research/clusters/rules-2026-10-14.html`, then
   `research/case-report-cards/THEORY-HANDOVER-2026-10-14.md` and `CONTEXT-BUNDLE-2026-10-14.md`,
   then `theory/CORRECTIONS.md`. Pull each passage a rule cites in full from `bowentheory/`
   with `sed -n`, never from memory of it.
3. Mark each rule as theory (the books say it), hypothesis (a guess the books support in part),
   his ruling (cite the id) or design choice (ours, no book behind it).
4. Run the suite as it stands (the command in btcopilot/tests/live/README.md, "Cluster F1") and
   read where the discrepancy shows: which expected cluster, which stored one, which events.
5. Decide where the fault lies, with the passages: the expected clusters, a rule, the prompt,
   or the data (a date certainty label, a missing event). Only the first two are corrections to
   the standard; the last two are fixes.
6. A correction to the expected clusters or to a rule goes to Patrick as a ruling candidate
   first, with the passage quoted word for word. Nothing in the case files or rules changes
   before his answer.
7. After his answer, correct the case file, re-tune the prompts until the suite passes, and log
   every real call's spend to the eval ledger. Real calls follow the spend rule: ask first.
8. A new real case gets its own fictional case as a new file in `clusters/cases/`, built the way
   btcopilot/tests/live/README.md says under "Cluster F1" (dates shifted by one offset, structure
   changed outside the clusters, every word rewritten), never a real diagram.

The inventory behind the cluster prompt is in the private corpus, btcopilot-sources
`research/clusters/INVENTORY.md`: one row per source item, 237 passages (P-001 to P-237), 201
statements of Patrick's (S-001 to S-201) and 144 rulings (R-nnnn). The prompt's citation comments
use those ids, which are stable from that file on.
