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
   couples needs when the two met and how many children they had.
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
| Known | The record: a name; a dated birth; a death event (alive), its date and its description (cause); a shift with a symptom, or a noted event naming health (health); a noted event naming schooling or work; a dated bond, marriage, separation or divorce (marriages); a noted event with a place, or naming places lived (places lived); a man or woman (sex); a parents' couple (parents); every child of the parents with a dated birth, two or more of them or their number known (birth order); a dated bond or marriage on the couple (met); any cluster (periods of stress). Or a fact question naming the item, closed as a fact or answered. |
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

## The metrics

Each coach turn's done row keeps the counts before and after the turn: items
required, known, asked, said unknown, declined and not asked. An evaluation question is
a fact question that names an item.

- **Coverage**: known over required.
- **Resolution**: known plus said unknown plus declined, over required.
- **Yield**: over the last N coach turns, items that became known, divided by
  the evaluation questions asked in those turns.
- **Ask density**: evaluation questions asked per coach turn.

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
