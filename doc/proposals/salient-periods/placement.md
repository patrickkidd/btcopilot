# Where the question sits, how each named time is followed up, and how the gaps are checked later

Judge: judge-010, 2026-10-04. App facts verified in the public export at origin/master
(doc/COVERAGE.md, btcopilot/coverage.py, btcopilot/prompty/agent.prompty, onboarding.prompty, the
public fragments, btcopilot/toolbox.py, btcopilot/schema.py). The private opening and flow fragments
were not read; where the running coach's order is set there, this file says so.

## 1. Where it sits in the coverage order

What the order is today. The coach's first words to a new person are fixed by the onboarding
block: first name, last name, birth date, and then "carry on with whatever they said first". After
that nothing scripts a first question. Each turn carries WHAT IS STILL UNKNOWN: the nearest eight
unasked items of Kerr's basic data in the checklist's order, at most three per person, "for your
judgement, never a script", with "ask one item from this list this turn" when the person's thread
leaves an opening (agent.prompty, last paragraph; doc/COVERAGE.md "What the coach reads each turn").
"Periods of major stress" is the thirteenth and last item on the person (coverage.py `_walk`, the
first `person(...)` call, with `Fact.Stress` last), so with eight slots and three per person it
does not reach the block on an early turn, and it becomes known from any cluster at all or from a
closed fact question naming it (coverage.py `_recorded`, `case Fact.Stress`).

The proposed place. Not a new checklist item and not a reorder of the dated history: one early
question, asked once, placed by a prompt rule, in this order.

1. Onboarding as today: the person's own name and birth date.
2. What brings them, and when it began. Kerr and Bowen both start with the presenting problem and
   its dates (FE ch10 L11; FTiCP ch9 L85); the onboarding text already says to carry on with what
   they said first. The coach dates the start and course of that before anything else.
3. The early question, once: what were the two or three times when the most was going on, and about what years
   (phrasings.md, candidate 1). Asked as soon as the presenting problem's start has a date, or at
   once when the person brings no one thing ("I just want to understand my family"). Never as the
   first question after onboarding when the person has come with something specific: Kerr, "let the
   family tell its story" (FE ch10 L11); "the presenting problems may be so consuming that there is
   little time to do more" in a first interview (FE ch10 L65, note 14).
4. The named times, one per turn, as in section 2 below, interleaved with the person's own thread
   whenever it opens: the coverage block's rule, "when the person's thread leaves an opening",
   governs the follow-ups of the early question too; the early question itself goes ahead of any
   item from that list, once (fragments-edits.md, edit 1).
5. The dated history as today, driven by the coverage block in Kerr's loose order: the person's own items,
   partner and children, parents, siblings, the partner's side, grandparents, aunts and uncles.
6. Kerr's catch-all when the block reaches "periods of major stress": "besides the years you have
   told me about, were there other times when a lot was going on for the family, and when?" (FE
   ch10 L15). This is the sweep the early question brought forward, asked again at its proper place.
7. The gaps, section 3 below, asked as plain fact questions through the rest of the coaching.

Why the early question does not move "periods of major stress" up the list. The item marks the
family's periods as known, and the early question's answer is the person's markers, not the periods
(theory.md, sections 1 and 3). Leaving the item last keeps the block prompting the catch-all after
the dated history,
which is where Kerr has it. This is decide.md item 4; the alternative is below in section 4.

## 2. How the coach follows up each named time without a questionnaire

The rule the fragments already hold: one question per reply, in the coach's words, no list of
answers (agent_fidelity.md "Closing a reply"); the question kept in the record on the turn it is
asked (open_questions.md); the coach's notes carry what it is holding for later (coach_notes.md).
The follow-up adds nothing to those mechanics; it says what to ask, in what order, for each time.

For each time the person named, at most three asks, one per turn, each following the last answer:

a. The year, by the person's own anchors, with arithmetic done by the coach: "how old were you",
   "what grade", "was that before or after your brother was born" (FTiCP ch9 L93; BS 3 L488-490).
   A year the person gives with a hedge is written with that hedge (agent_fidelity.md, date
   certainty), never sharpened. When the person gave the year in the early question, this ask is skipped.
b. What happened, to whom, on both sides. Events, dated: who was born, who died, who moved, who
   was ill, who lost a job, in the person's house and in their parents' and partner's families
   (FE ch10 L15, L19; FTiCP ch9 L85, L89 "a fix on the entire family system"). One ask opens it
   ("what else was going on in the family that year"); the facts come over turns.
c. How each person in the house managed that time, not only the person asking (FE ch10 L15,
   "how did each spouse adapt"; FE ch10 L45 reactivity against stress). This is the one ask of the
   three that is coaching in register; the first two are evaluation (the notes tool's register).

Not a questionnaire because: the three asks are a ceiling, not a script; each question is built on
the last answer (the sources' interviews run one short question at a time); the coach drops the
follow-up the turn the person's own thread opens and comes back to the time later from its notes;
and a time the person has nothing more to say about is let go, with its open question kept for a
later day. The coach never asks all three of one time in one reply and never asks about two named
times in one reply.

## 3. What the coach writes to the record when a time is named

- The early question itself: kept with `add_question` on the turn it is asked, kind `fact`, state `asked`,
  about the person (`item_kind` person, `item_id` the person's id), in the words the reply uses.
  Whether it also names the checklist item `fact: stress` is decide.md item 4; the judge's call is
  that it does not, so the item stays for the catch-all. Closed `answered` when the person names
  their times, `unknown` when they cannot, `declined_in_chat` when they will not.
- A time named with facts in it ("2009, when Dad was in hospital and I quit school"): each fact is
  an event on the turn it is given, people first (agent_fidelity.md): a noted event on the person
  for the schooling, item schooling, dated 2009 with the certainty the words carry; an event on the
  father for the hospital time, dated the same way. The named time is not itself an event.
- A time named with nothing in it yet ("2014 to 2016 was the worst"): no event, because a noted
  event must say what happened (R-0363) and a shift needs a variable that moved on a person at a
  date. The coach keeps a fact question on the person that names the span of years, "What was going
  on in your family between 2014 and 2016?", asked now or held, and the span lives on that question.
  A question naming a span of years is allowed in the data by R-0686 (named, not quoted; its text
  was not read for this proposal).
- A cluster never from a label, and nothing in the prompt need say so: the code computes clusters
  from dated events and refuses any group under three at the write, and `edit_cluster` refuses the
  same (doc/CLUSTERS.md).
- The coach's notes each turn: `holding` names the times named and not yet asked about, so it comes
  back to each; `hunch` holds what seems to line up, unsaid, until the dates are firm (FTiCP ch9
  L93; BS 6 L125); `register` evaluation for asks (a) and (b), coaching for (c).
- A range chip, `[[range:start..end|words]]`, may point at the years in the reply once at least one
  dated event lies inside them (coach_reference.md; timeline keeps a range only over dated events).

## 4. How the gaps are checked later

The named times are where the person's memory is loudest; the theory's periods include years the
person did not name (theory.md, risks 1, 2 and 4). Three kinds of gap, each asked as a plain fact
question at the point in the dated history where its people come up, never as a block of questions:

1. Between the named times. For a silence of several years between two named times: "between
   2011 and 2019, who came into or left your household, and did anyone move" (FTiCP ch15 L13, the
   additions and losses; FTiCP ch21 L95, Bowen reads from the stable years). A quiet answer is
   written as the person's answer, not as nothing happened; Kerr's 18-year-old had a quiet house
   (FE ch10 L45).
2. Before the person could remember. When the parents are reached in the dated history: "around the
   year you were born, what was going on for your mother and father, who died or moved in the two or
   three years before and after" (FTiCP ch21 L91-93, Bowen's own nodal point at about four; FE ch10
   L19 "when a person knows very little about his grandparents"). A said-unknown here is evidence
   about cutoff in the parents' generation, as the coverage text already says.
3. The wider family around each loss on the record. For each death, separation and move already
   recorded: "in the year or two after your grandfather died, did anything change for your mother,
   her brothers or sisters, or anyone else in the family" (FTiCP ch15 L15, L19; BS 6 L112-116; FE
   ch9 L74). doc/TOPICS.md lists "the coach does not yet ask about the older households around each
   death, separation and move" as an open build item; this is that item, approached from the named
   times. Also which relatives are not in the story at all (FE ch10 L19, "not involved").

When: gap 1 after the named times are gone through, before the catch-all; gap 2 when the dated history reaches
the parents; gap 3 whenever a loss lands on the record, in the turn after its date is fixed, and
again at the catch-all. The coverage block does not carry these; they are the coach's judgement
under the prompt rule, and the notes' `holding` field is where it keeps the ones still owed.

## 5. The alternative placement, for the record

Name `fact: stress` on the early question and close it `answered` when the person names their times.
Then "periods of major stress" is known from the early question, the block never prompts the catch-all, and the
sweep relies on the prompt rule alone. Simpler to file, truer to the tool text ("name it whenever
the question asks for one of the required facts"), but the data then says the periods are known
when only the person's markers are. The judge prefers the item left for the catch-all; either way
needs no code change and no change to the order of the dated history.
