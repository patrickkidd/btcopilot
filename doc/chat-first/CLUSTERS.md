# Clusters

How the record's events become episodes. Rules first, model second.

## The rules make the candidates

Computed from `DiagramData` alone, no model call, in `btcopilot/personal/clusters.py`:

- An **anchor** is any event carrying a symptom, anxiety, relationship, or
  functioning value. [Oracle: R-0054 — no absolute values exist; only relative
  shifts, captured in episodic clusters.]
- A **candidate** is an anchor plus every event within **18 months** either side
  of it that shares a person, or shares a couple, with it. Sharing a couple means
  each event names a member of the same pair-bond.
- **Scaffolding never joins.** A structural event (birth, adopted, married,
  bonded, separated, divorced, moved, death) that carries no variable value and
  is dated before the first anchor is age scaffolding, not episode material.
  [Oracle: R-0038 — the diagnostic period starts at the first nodal-or-variable
  event.] The predicate reads `EventKind.isStructural()`, never a string.
- Candidates sharing any event **merge**.
- A silence of **24 months or more** inside a merged candidate **splits** it.
- A candidate left with one event is **not a cluster** — a lone anchor with no
  related move stays a dot on the line.

Parameters `SPAN_DAYS`, `CALM_GAP_DAYS` and `ANCHOR_FIELDS` are module constants.
Undated events never enter a candidate.

**The record has no nodal flag.** `schema.Event` has never carried one, and the
owner ruled the nodal flags in the old corpus are not used consistently and are
to be ignored (`doc/chat-first/NATURE_OF_THE_DATA.md`). Anchors are therefore
variable-valued events only. If a nodal flag is ever added, it joins
`ANCHOR_FIELDS`.

## The model only names and explains

It receives the candidates and the events that fell outside them. It returns one
entry per final group: `eventIds`, `name`, `reason`, and `change`.

- `reason` is one sentence saying which chain of moves makes the events one
  episode. Required on every group.
- The model may **join** two candidates, **break** one apart, or **pull in** an
  unclustered event. Any group that is not a candidate exactly as given requires
  `change`, a sentence saying why. Changes are logged.
- It may not name an event the record does not hold, put one event in two
  groups, or drop a deterministic anchor. [Oracle: R-0076 — the model may group
  and name, never invent members.]

A name, reason, or change containing a diagnostic or popular-psychology word the
definitions do not contain (`OUTSIDE_WORDS`) is rejected too.

Validation rejects a violation with a sentence; the prompt is re-asked once with
that sentence and then the failure propagates.

## The prompt

The public default (`btcopilot/personal/prompts.py`) asks for the naming and
nothing else. The clinical definition of an episode lives only in the private
prompt (`fdserver/prompts/private_prompts.py`), quoted rather than referenced,
and carries a closed-vocabulary instruction: use only the definitions given, no
outside Bowen theory, no popular psychology. Rule-by-example examples are an
empty owner-marked section, pending.

## Where `reason` goes

Additive `Cluster.reason` in `schema.py`, stored through `record.apply` with
author Coach, served on the timeline payload, and given to the play-by-play
prompt through the cluster line [Oracle: R-0074]. A user correction through
`edit_cluster` sets `source=user` and clears the coach's reason.
