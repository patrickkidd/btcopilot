# The event model — the three complaints, and a normalised shape

Status: **complaint 1 built; the rest still a proposal.** Rulings 1, 3 and 6 are ruled
[Oracle: R-0363, R-0364, R-0365]: `noted` is a kind, a move is a noted event, and it was
done now rather than after the beta. `moved` has left the kind list, and no code translates
a stored event carrying the old kind. Rulings 2, 4 and 5 are open and
nothing under them is built. Three problems Patrick raised with the timeline data
model the chat app inherited from the desktop app, each mapped to the field that causes it,
one proposed shape, and the rulings at the end. Page version: `mockups/eventmodel.html`.
Examples use the stand-in family (`mockups/family.md`).

## The shape today

One flat row: `kind`, `person`, `spouse`, `child`, `description`, `location`, `dateTime`,
`endDateTime`, `dateCertainty`, `symptom`, `anxiety`, `functioning`, `relationship`,
`relationshipTargets`, `relationshipTriangles`.

| # | The moment | Today |
|---|---|---|
| 1 | Corinne was born, 1975 | `{kind: "birth", person: 4 (Delphine), spouse: 3 (Marcus), child: 5}` |
| 2 | Errol died, 1989 | `{kind: "death", person: 1}` |
| 3 | Marcus and Delphine married, 1970 | `{kind: "married", person: 3, spouse: 4}` |
| 4 | …divorced, 1981 | `{kind: "divorced", person: 3, spouse: 4}` |
| 5 | Marcus moved to Arizona, Mar 1969 | `{kind: "moved", person: 3, location: "Arizona"}` |
| 6 | Marcus finished his apprenticeship, Mar 1969 | **no home** — see complaint 1 |
| 7 | Theo's grades collapsed, 1992 | `{kind: "shift", person: 6, functioning: "down", description: "his grades collapsed"}` |
| 8 | Corinne pulled away from Theo, 1995 | `{kind: "shift", person: 5, relationship: "away", relationshipTargets: [6]}` |
| 9 | Corinne moved toward Theo and away from Marcus | `{kind: "shift", person: 5, relationship: "toward", relationshipTargets: [6], relationshipTriangles: [3]}` |

## Complaint 1 — "Moved" is not first-class, and ordinary events have nowhere to go

`EventKind.isPairBond()` returns true for `Moved`, so the desktop app files a move in the
marriage's event buckets and prints it in the couple's detail lines. A move is one person's.

Separately, the enum is seven structural kinds plus `shift`, and `record._moves` refuses a
shift unless a variable or a relationship moved. "Finished his apprenticeship" can only be
written by lying. The desktop corpus wrote these as kind `other` with free text; the chat
app's closed enum dropped that class.

## Complaint 2 — a birth is the mother's event, with the child in a side field

`person` is a parent, `child` is the person born. `record._words` refuses a birth whose
`child` is unset; `toolbox._edit_event` invents a generic second parent when only one is
given; the timeline reads "who this is about" from `child` only for births. Writing "Corinne
was born in 1975" forces two parents into the record before it will save.

## Complaint 3 — one actor field carrying four different role shapes

`person` means four things depending on `kind`, and the code special-cases each:

- **mutual** (bonded, married, separated, divorced): `person` + `spouse`, order meaningless;
  the matcher compares them as an unordered set (`is_couple` in `match_events`).
- **directed** (conflict, distance, over/under-functioning, projection, toward, away, cutoff):
  `person` does it to `relationshipTargets`.
- **triangle** (inside, outside): two positions in `relationshipTargets` plus
  `relationshipTriangles` — two unnamed lists whose meaning is positional.
- **one person alone** (death, a variable shift, moved): `person` only.

Nothing in the row says which shape applies. Every reader re-derives it from `kind`.

## Proposed shape

`kind` is a closed set in three classes, and the class decides the role shape:

- **structural** — `born`, `died`, `bonded`, `married`, `separated`, `divorced`, `adopted`,
  `miscarried`: who exists and who belongs to whom.
- **shift** — a SARF variable or a relationship moved.
- **noted** — important, neither of those: moved, finished an apprenticeship, started therapy.

Three role fields for every kind: `about`, the one person it happens to (the child for a
birth, the mover for a directed move, either partner for a mutual kind); `with`, the others
(the other partner, or the targets of a directed move); `positions`, triangles only, named
rather than positional. Payload: `moved` on shifts only, over the three variables;
`relationship` keeps its own field because it decides whether `with` or `positions` is used.
Dates unchanged.

Mutuality becomes a property of the **kind**, declared once, not a different field layout per
event. That is the whole normalisation: readers ask the kind, never the columns.

| # | Proposed |
|---|---|
| 1 | `{kind: "born", about: 5}` — parents are not required; they live on the person's pair-bond link |
| 2 | `{kind: "died", about: 1}` |
| 3 | `{kind: "married", about: 3, with: [4]}` — mutual, so order carries no meaning |
| 4 | `{kind: "divorced", about: 3, with: [4]}` |
| 5 | `{kind: "noted", about: 3, description: "moved to Arizona", location: "Arizona"}` |
| 6 | `{kind: "noted", about: 3, description: "finished his apprenticeship"}` |
| 7 | `{kind: "shift", about: 6, moved: {functioning: "down"}, description: "his grades collapsed"}` |
| 8 | `{kind: "shift", about: 5, relationship: "away", with: [6]}` |
| 9 | `{kind: "shift", about: 5, relationship: "toward", positions: {toward: [6], away: [3]}}` |

## What it costs

The chat chain is unreleased, so no user's data is at stake. It is still not free.

- **Stored records.** One JSON blob per diagram row, so no SQL migration — but every blob
  needs a one-pass rewrite, and so does every stored edit delta, because a delta names the
  field it changed (`"field": "spouse"`). Undo history left unrewritten breaks silently.
- **The Pro app — no cost since R-0471.** This app has no connection to the desktop app; only the opt-in
  import of an old Pro diagram (R-0422) reads its format, one way.
- **The coach's tool text** (private, fdserver): `edit_event` loses four parameters and gains
  three. Fewer parameters and one rule per kind should raise the hit rate, not lower it.
- **The refusals.** "A birth is about the child" disappears — the shape enforces it. "A shift
  must say which way something moved" stays. One new one: a noted event must carry a
  description, since its kind no longer says what happened.
- **The fragment renderer** asks the kind's class instead of scanning `person`/`spouse`.
- **The review's matching.** `match_events` drops `is_couple` and `is_child_centric`.
- **The old-diagram importer.** One converter path, exercised by the desktop files that exist.

After the beta: all of the above plus migrating real users' records.

## The rulings

1. **RULED [Oracle: R-0363] — "noted" is a kind, and its description is required.** Is "noted" a kind, or is kind optional? "Marcus finished his apprenticeship, Mar
   1969" has no home today. Either it is written `{kind: "noted", about: 3, description:
   "finished his apprenticeship"}`, or events carry no kind at all when nothing structural
   or SARF happened, and a kind is the exception. A named kind keeps the enum closed and the
   refusals checkable; no kind makes the ordinary case the default and the structural case
   the marked one.
2. **Does a birth ever carry parents?** "Corinne was born, 1975" is `{kind: "born", about:
   5}` and her parents come from her pair-bond link. Alternative: `with` may hold the parents
   when the person telling the story gives them in the same breath, and the parents are
   derived from the bond otherwise. Never carrying them is one way to say a thing; allowing
   them means two places can disagree about who Corinne's mother is.
3. **RULED [Oracle: R-0364] — a move is a noted event; `moved` has left the kind list.** Is "moved" a noted event, or does it keep its own kind? `{kind: "noted", about: 3,
   description: "moved to Arizona", location: "Arizona"}` versus keeping `moved` as a kind
   that is no longer tied to the couple. Keeping it means the word "moved" is drawn and
   searched without reading anyone's description; dropping it means one less kind and the
   location field does the work.
4. **Is a triangle's two positions named, or ordered?** "Corinne moved toward Theo and away
   from Marcus" is `positions: {toward: [6], away: [3]}` — or it stays two lists whose
   meaning you have to know. Naming them costs a nested object in every triangle row.
5. **Do the three variables move into one `moved` object?** `moved: {functioning: "down"}`
   versus the three flat fields `symptom`, `anxiety`, `functioning` as today. Nesting says
   "these three are one thing, and only a shift has them"; flat fields are what the Pro app
   already reads.
6. **RULED [Oracle: R-0365] — now, before the beta. No migration and no translation on read: Patrick fixes the few stored rows in the database himself after the deploy.** Now, or after the beta? Now is one rewrite of unreleased records plus a permanent
   translation layer at the Pro app boundary. After the beta is the same work plus a
   migration of real people's records, and every refusal and tool text written twice.
