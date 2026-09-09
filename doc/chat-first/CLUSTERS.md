# Clusters

How the record's events become clusters. Rules first, model second.

## The rules make the candidates

Computed from `DiagramData` alone, no model call, in `btcopilot/personal/clusters.py`:

- A cluster is seeded by a **nodal event or a shift**: one of the kinds the
  intake engine already counts as nodal (death, married, divorced, separated,
  moved), or any event carrying a symptom, anxiety, relationship, or functioning
  value. [Oracle: R-0054 — no absolute values exist, only relative shifts,
  captured in clusters.] The nodal kinds are reused from `btcopilot/personal/intake.py`
  rather than redefined, and that set now compares against `EventKind` instead of
  raw strings.
- A **candidate** is a seeding event plus every event within **18 months** either
  side of it that shares a person, or shares a couple, with it. Sharing a couple
  means each event names a member of the same pair-bond.
- **Scaffolding never joins.** A structural event that is neither nodal nor
  carries a shift — in practice a birth or an adoption — and is dated before the
  first seeding event is age and generation scaffolding, diagnostically inert.
  [Oracle: R-0037, R-0038.] The predicate reads `EventKind`, never a string. A
  consequence worth knowing: an early marriage is nodal, so it opens the recorded
  period and the births after it are no longer scaffolding.
- Candidates sharing any event **merge**.
- Two years with no nodal event and no shift inside a merged candidate **split**
  it, at the widest silence between the two seeding events either side.
- A candidate holding fewer than **three** events is **not a cluster** — a lone
  shift with no related move, or a bare pair, stays dots on the line. The
  minimum is `MIN_EVENTS`, and it binds the rules, the model's regrouping, and
  the write: `sync` raises rather than store a grouping under it.

Parameters `SPAN_DAYS` and `CALM_GAP_DAYS` are module constants. Undated events
never enter a candidate.

## Open for the owner

**The record has no nodal flag.** The `Event` dataclass at `btcopilot/schema.py:317`
has no `nodal` field and never has; the word does not appear in that file. The
owner ruled the flags in the old corpus are used inconsistently and are to be
ignored (`doc/chat-first/NATURE_OF_THE_DATA.md`). So nodal here means the event
kind — death, married, divorced, separated, moved — which is what the intake
engine has always meant by it, and a cluster is seeded by one of those kinds or
by any recorded shift. If the owner wants a per-event nodal flag it is an
additive schema field and one more term in the seeding predicate.

## The model only names and explains

It receives the candidates and the events that fell outside them. It returns one
entry per final group: `eventIds`, `name`, `reason`, and `change`.

- `reason` is one sentence saying what the record shows the events have in
  common: who they involve, when they happened, which shifts were recorded.
  Required on every group. It is not an interpretation and not a claim the events
  do not carry.
- The model may **join** two candidates, **break** one apart, or **pull in** an
  event that fell outside them. Any group that is not a candidate exactly as
  given requires `change`, a sentence saying why. Changes are logged.
- It may not name an event it was not given, put one event in two groups, or drop
  a seeding event. [Oracle: R-0076 — the model may group and name, never invent
  members.]
- A name, reason, or change containing a diagnostic or popular-psychology word
  the prompt's terms do not contain (`OUTSIDE_WORDS`) is rejected too.

- A group holding fewer than `MIN_EVENTS` events is rejected. A group that only
  falls under the minimum because a grouping the user made takes its events is
  dropped instead, silently — those events go back to being dots.

Validation rejects a violation with a sentence; the prompt is re-asked once with
that sentence and then the failure propagates.

## What is deliberately undefined

No ruling says what makes a set of events one cluster, so neither the code nor
the prompt says it. The prompt gives the model the four variables and the
relationship mechanisms from `doc/specs/BOWEN_THEORY.md`, the relationship moves
the record's own enum holds, and the rulings above — then forbids everything
else. `CONTEXT.md` is not cited: its domain section is a pointer to the same
theory spec and carries no cluster content.

## The prompt

The public default (`btcopilot/personal/prompts.py`) asks for the naming and
nothing else. The terms live only in the private prompt
(`fdserver/prompts/private_prompts.py`), quoted rather than referenced, with the
closed-vocabulary instruction: use only the terms given, no outside Bowen theory,
family therapy, or popular psychology. Rule-by-example examples are an empty
owner-marked section, pending.

## What a stored cluster holds

Name, reason, source, event ids, and the dates they span. The invented pattern
vocabulary (anxiety cascade, triangle activation and the rest) and the dominant
variable are removed from the schema and from persistence; they came from earlier
AI output, not from the owner. Old rows carrying them are not migrated — the next
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

A recomputed cluster keeps the id of the stored cluster it shares the most
events with, so a chip already placed in an earlier coach message keeps
resolving to the same cluster after the record is re-clustered.

**Nothing selective exists.** There is no logic that limits recomputation to
only the clusters touched by the new event — it is whole-record every time.
Cost is one model call per event-changing turn, for the whole record.

A change to the candidate rules or the naming prompt bumps `DETECTION_VERSION`,
which changes the cache key, so the next event-changing turn re-clusters the
whole record even though no event itself changed.

The owner ruled: "let's just play with it and see how it works in the Beta."
[Oracle: R-0208] Selective invalidation is not being built now — revisit only
if whole-record recompute shows a problem in use.

## Only a restarted server groups by the current rules (learned 2026-09-08)

`DETECTION_VERSION` makes a *stored* grouping stale; it cannot make a *running
process* stale. A long-running sandbox server keeps the module it imported at
start, so a rules or prompt change reaches real turns only after that server is
restarted. On 2026-09-08 a server started before the minimum-size change stored
one-event clusters on the owner's record hours after the change was committed,
and wrote the cache key its older code computed. Restart the sandbox after every
commit that touches this module, and read a surprising stored grouping as a
question about which code the server was running before treating it as a rules bug.

## How to re-run clustering on a record by hand

The resync path is `btcopilot.personal.clusters.sync(diagram_id, turn_id=...,
user_id=..., session_id=...)` — the same function a coach turn calls. It
re-detects clusters for the whole record and writes the result through
`record.apply` with `author=Coach`, so it needs a `turn_id` the way any other
record change does. Back up the database first — `sync` writes through the
normal delta/apply path, so a mistaken run is just another change to correct,
not something reversible in place.
