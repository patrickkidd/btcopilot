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
- A candidate left with one event is **not a cluster** — a lone shift with no
  related move stays a dot on the line.

Parameters `SPAN_DAYS` and `CALM_GAP_DAYS` are module constants. Undated events
never enter a candidate.

**The record has no nodal flag.** `schema.Event` has never carried one, and the
owner ruled the flags in the old corpus are used inconsistently and are to be
ignored (`doc/chat-first/NATURE_OF_THE_DATA.md`). Nodal here means the event
kind, which is what the intake engine has always meant by it.

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
