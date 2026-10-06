# Coverage of the basic data

The basic data is what a family evaluation gathers about the person's family
(Kerr, *Family Evaluation* ch. 10; Bowen, *Family Therapy in Clinical Practice*
ch. 9). Coverage says how much of it the coach has accounted for. It replaces
counting the people mentioned (Patrick, 2026-09-29; queued as R-0618, replacing
R-0485). The design Patrick approved on 2026-09-30 is FD-366's coverage
decisions (a) to (g).

## The checklist

Worked out from the record every time it is read; nothing is stored but the
per-turn counts below. Code: `btcopilot/coverage.py`.

**Who is on it.** Only people and couples already in the record. The list grows
as the record does, in Kerr's loose order:

1. The person, each partner, each child. The person also needs who their
   parents are and the family's periods of major stress; each of the person's
   couples needs when the two met and how many children they had. Right after
   their birth date the person needs the two or three times when the most was
   going on, which opens the history and does not replace it [Oracle: R-0735].
   It is known only from a fact question naming it, never from clusters or
   events, so on a thread where it was never asked it heads the list; a time
   named with nothing in it yet answers it.
2. Parents (each needing who their own parents are), step-parents, full, half
   and step siblings, and the siblings' children. The parents' couple needs how
   many children it had, so siblings not yet named still show as a gap.
3. The partner's parents and siblings, as far as the person is attached to the
   partner: two or more of married, children together, five or more years
   together, two or more of the partner's family in the record means the full
   list; otherwise only their names and whether they are alive.
4. Grandparents; their couples need how many children, so aunts and uncles not
   yet named show as a gap.
5. Aunts and uncles, then first cousins.
6. Great-grandparents, only those already named.

**Items per person, by depth.**

| Who | Items |
|---|---|
| Person, partner, children, parents, siblings, the partner's siblings when attached | name, birth date, alive, schooling, work, health, marriages with dates, places lived, contact, birth order, sex |
| Grandparents, step-parents, the partner's parents when attached | the same without birth order and sex |
| Aunts and uncles | name, birth order, birth date, alive, work, places lived, marriages, life course, contact |
| Cousins, siblings' children | name, birth order, sex, alive |
| Great-grandparents | name, alive, places lived |
| The partner's parents and siblings when not attached | name, alive |

Anyone the record says has died also needs the death date and the cause of
death; a great-grandparent needs only the death date, and cousins, siblings'
children and the partner's family when not attached need neither.

## The five states

| State | From |
|---|---|
| Known | The record: a name; a dated birth; a death event (alive), its date and its description (cause); a shift with a symptom, or a noted event naming health (health); a noted event naming schooling or work; a dated bond, marriage, separation or divorce (marriages); a noted event with a place, or naming places lived (places lived); a man or woman (sex); a parents' couple (parents); every child of the parents with a dated birth, two or more of them or their number known (birth order); a dated bond or marriage on the couple (met); any cluster (periods of stress; never the times the most was going on). Or a fact question naming the item, closed as a fact or answered. |
| Asked | A fact question naming the item, asked and not yet closed. |
| Said unknown | A fact question naming the item, closed as unknown. |
| Declined | A fact question naming the item, closed as declined, by the person or in the chat. |
| Not asked | Required, not in the record, and no such question asked or closed. A question held for later, or let go, leaves its item not asked. |

A noted event names which of schooling, work, health or where they lived it
records in its `item` field, set by the coach when it records such a fact told
unasked; that item is then known for the event's person. Contact, life course
and how many children a couple had are known only from a closed question.
When several questions name one item, the last one sets its state.

A said unknown about parents or grandparents is one fact for a hypothesis about
cutoff in the parents' generation, never a fact about the person.

## What the coach was already told [Oracle: R-0760]

The coach never asks for what the person already said. Four rules on the
question tool hold it to that; the chat stays free text, so each steers the
coach rather than the person.

- **A fact the person states unasked is kept as a question already answered.**
  "We can't have children", "my father is still alive", "my parents are still
  married": the coach adds the fact question closed in one call, with outcome
  answered (or unknown, when they said they do not know), the fact and the
  person or couple it is about, and the person's own message as the answer.
  The question carries the session and the day it was kept, so it shows where
  closed questions show. "We can't have children" closes the couple's children
  item as answered, with no number; it is never asked again. A question can only
  be born closed as a fact question naming its fact and its item.
- **Asking a known item is refused, with the answer.** An asked fact question on
  an item the record already answers (a death event for alive, a dated birth for
  the birth date, a closed question naming the item, and so on, by the table
  above) is not kept; the refusal quotes the entry or the closed question that
  answers it, for the coach to use. A thought question, a question kept for
  later, and a question naming no item are untouched.
- **The chat is searched before an asked question is kept.** When the record
  does not answer the item, the tool itself searches what was said before, in
  one query, for a fixed list of everyday words per item (children: children,
  kids, son, daughter, pregnant, baby, IVF, adopt, "start a family"; alive:
  alive, living, died, passed, death, funeral, "still married"; and so on, in
  `coverage.SEARCH_WORDS`), in messages that name the person or what they are
  called for what they are to the person (father, dad; mother, mom; and so on,
  in `coverage.CALLED`). The person themself and their own couples are searched
  by the item's words alone, since they say "I" and "we". The question is kept
  and the hits come back with it, so the coach can close it as answered citing
  the message instead of asking. No meaning-based search; a paraphrase the list
  misses is reported from the live cases for Patrick to decide on.
- **A second open question on one item is refused.** While a fact question on a
  person or couple and item is asked and open, another on the same item is not
  kept, in any words; the refusal names the open one, to close with the
  person's answer first.

A fact placed on the wrong kind of thing (how many children or when they met on
a person, any other item on a couple) names no item of the checklist, so these
rules leave it alone: it is kept as it always was.

## The metrics

Each coach turn's done row keeps the counts before and after the turn: items
required, known, asked, said unknown, declined and not asked. An evaluation question is
a fact question that names an item.

- **Coverage**: known over required.
- **Resolution**: known plus said unknown plus declined, over required.
- **Yield**: over the last N coach turns, items that became known, divided by
  the evaluation questions asked in those turns.
- **Ask density**: evaluation questions asked per coach turn.

## On the dashboard

The Features dashboard's section "Coverage of the basic data" reads the counts
after each coach turn, for real families only (scratch diagrams, synthetic
sittings and the claude-test accounts left out). A family is a diagram; a
sitting is a discussion.

- **Coverage curve**, two panels: known over required after each coach turn,
  one line per family against its coach turns counted from the first, and one
  line per sitting against the coach turns counted from the start of that
  sitting.
- **Coach turns to 50% coverage**: per family, the first coach turn after which
  half the required items were known, where reached.

Next, not built:

- Facts per evaluation question: items that became known per evaluation
  question asked.
- Free coverage on coaching turns: items that became known on turns labelled
  coaching in the coach's notes, where no evaluation question was asked.
- Engagement after an evaluation question: whether the person's next message
  comes and how long it is.
- Ask density against return within a week.

## What the coach reads each turn

Each coach turn's prompt carries a block headed WHAT IS STILL UNKNOWN, rendered
by `coverage.block` beside the record's map, after the chat, so it never
breaks the cached coaching text. Two sentences under it say it is what is
still unknown, for the coach's judgement, never a script, and that a fact said
unknown is evidence about cutoff in the parents' generation, not a stop.

- **The nearest unasked items**: the first eight not asked, in the checklist's
  order, at most three on one person or couple so the list reaches past the
  first person with many gaps; one line per person or couple, with the id,
  the name and what they are to the person ("2 Ada (mother): birth date,
  alive or not, schooling"). An item asked and still open is not listed.
- **Said unknown**: every item said unknown, on one line, as evidence.
- **One line of fractions**: coverage (known over required) and resolution
  (known, said unknown or declined over required).

**The plateau.** When the coach's notes say the plateau is reached, the list
is cut to the nearest three and a line says which turn of the plateau it is.
The plateau starts at the first of the coach's unbroken notes saying it is
reached and lapses after five turns (the corpus sets no number), or as soon as
a person or event is added after the turn that started it; the coach can set it
again. The block's own line says so; the prompt has no sentence about it. It
never closes an item, and the said-unknown list and the fractions stay.
