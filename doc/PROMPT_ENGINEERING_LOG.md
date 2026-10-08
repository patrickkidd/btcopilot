# Prompt Engineering Context

**Purpose**: Dated record of prompt engineering decisions, experiments, and lessons learned, from the extraction pipeline era through the coach. Entries are never rewritten; the newest entry wins.

**Last Updated**: 2026-10-08 (structure before stories; a fact to find stays open)

---

## Worker job 024 — structure before stories; a fact to find stays open (2026-10-08)

**Change**: two things the coach reads. (1) The block headed WHAT IS STILL UNKNOWN now lists the
structure items first, in the order Patrick gave them (who each person is, whose parents are whose
and how many children each couple had; then marriages with dates and when the person's couple met),
and the story items after, each part in Kerr's order; the times the most was going on keep their
place ahead of everything (`coverage.structure_first`, the same rule read from the record's shape
for every diagram). The private question fragment's "What to ask next" paragraph gains two
sentences: when the choice of question is the coach's, take the first item of that list, so the
structure is mapped before any story the coach would open itself; a topic the person brings, or a
story they are telling, always comes first. (2) The same fragment's closing sentence now says
`unknown` is for a fact nobody can tell the person, and a fact they say they will find out or ask
someone for is not settled: leave it `asked`, on their list of facts to find, with what they said
they would do as their todo. The question tool's outcome descriptions say the same, and the tool
refuses a close as unknown, or a question born closed as unknown, while the message being answered
says the person will find out (`toolbox.FIND_OUT`: "I'll ask", "let me find out", "I'd have to
look it up", and so on); the refusal says to leave it asked and keep the todo. The public copy of
the fragment (`btcopilot/prompty/fragments/open_questions.md`) was not edited: it is outside this
job's file list, so it now lags the private one by these sentences.

**Why**: Patrick, 2026-10-07: "the basic family structure should be mapped out at least earlier
than later. Definitely before any Coach driven rabbit holes on stories"; then "just to be clear, I
specifically said Coach driven questions. When the client wants to talk about something the coach
has to follow them." On a diagram like his, how many children a parent's parents had sat at
position 100 of 163 in the one fixed order, and the coach sees eight items, so it never came up.
And "Yes" to keeping a question open when the person says they will find out: "I don't know, I'll
ask my uncle" was closed as unknown, the same as "nobody knows", and fell off the facts-to-find
list.

**Measured**: `btcopilot/tests/live/test_structurefirst.py`, three cases, each 2 of 3, on the
worker machine's Claude Code (AWS Bedrock, model `us.anthropic.claude-opus-5`, which the app prices
as `claude-opus-5`; not the production model) through `bin/subscribe.py` with a PATH wrapper that
restores the Bedrock sign-in the nested `claude -p` is otherwise stripped of. Fictional record:
Wren, her parents Ada and Hugh, three events (two moves, one symptom), an earlier sitting with
what brings her and the two or three times answered.
- Given the floor ("That's about all I can think of for now. What else do you need to know?"), the
  coach keeps a fact question naming a structure item (or asks one in those words): old prompt and
  block 0 of 3 (it asked what she hopes to get from the conversations, twice, and her mother's age
  once); new 2 of 3 (the miss opened the year 1996 she had named, as the fidelity fragment tells it
  to follow a named time).
- A topic she brings ("My sister Nell called last night and we ended up arguing about Mom's care
  again. I hung up on her."): no fact question on anyone's parents, marriages or meeting is kept,
  and the first question is about the story: 3 of 3 on both, as it should be; this case guards
  Patrick's correction rather than measuring the change.
- A fact she will ask for ("Honestly, no idea. Dad never talked about himself and I never asked. I
  suppose I could ask my mom sometime." to an open question on her father's birth date): the
  question stays asked: 3 of 3 on both, also with the plainer "I honestly don't know when Dad was
  born. I'll ask my mom next time I see her." So this run did not reproduce the production
  finding on the old prompt (which already said a todo is not the answer to the fact question);
  what guarantees it now is the tool's refusal, proven by the unit tests in
  `btcopilot/tests/test_questions.py`, which fail without it.

**Then, on Patrick's ruling the same day** ("sounds like you should at least add the person with no
name"): closing how many children a couple had as answered now requires `count`, the number the
person said, as a tool argument (0 for none or cannot have any); for each child counted beyond
those the record holds, the tool adds a person named only as the couple's child, the record's own
way with an unnamed parent or partner (R-0325), removes nobody, and says what it added; the child's
name is then an open structure item in the WHAT IS STILL UNKNOWN list. The fragment's closing
paragraph says the same in one sentence; the tool's `count` description says it too. Proven by unit
tests on the tool and the checklist, not by a live case: the behaviour is the tool's, not the
model's.

## FD-375 — a file attached to a message is read into text once (2026-10-07)

**Change**: a new instruction, `fragments/attachment` (private, with the same public wording), is
the system prompt of one model call that reads an attached PDF or photo: write out everything the
file holds as plain text, people with their dates, events with their dates as given, in the file's
own words and order, saying where a date or a part is unclear; no interpretation, summary or
remarks. The file goes as a document or image block; a photo is sent as a JPEG no larger than 1568
pixels on its longest side. Output is capped at 16000 tokens. Text and Markdown files make no call.
The read text reaches the coach after the person's words, marked "From the file <name> (enter
every person and every dated event in it, births too, before you reply):", and the private record
contract gains a paragraph saying the same: enter everything the file holds this turn, a person
added first and their events, birth among them, once their id is back, every date checked before
replying [R-0828, R-0829, R-0830].

**Why**: Patrick wants any file dropped on the app to be input to the case, with the coach seeing
only text. The live eval `test_attachments.py` (2 of 3, subscription replay) proves the coach
enters a one-page PDF's people and events on the reply that carries it; the reading call itself is
stood in for by the PDF's extracted text there, so its own wording is not yet measured on a real
file. Before this there was no way to attach a file, so the case cannot pass on the old code.
Measured on the subscription: with neither instruction 0 of 3 runs entered the added son's
birth (the coach added him and his parents' events in one round, then never came back for his
birth); with the record-contract paragraph alone, 1 of 3; with the words beside the file text
too, 2 of 3, which passes but has no margin. One more wording was tried and dropped: the
reminder moved after the file's text, "(Enter all of this file in the record before you reply:
every person in it, then an event for every date it gives, the birth of each person you add
included.)", scored 1 of 3. The words before the file's text stay. A PDF is now read 25 pages a
call, and a part cut off at the output limit fails the read instead of keeping cut text.

## FD-375 — the coach notes when the person corrects it (2026-10-07)

**Change**: the coach's notes tool takes an optional `corrected` field: what the person's newest
message corrected, only when it says the coach got them wrong (assumed, misheard, put words or
feelings in their mouth). The notes fragment, private and public alike, gains one sentence telling
the coach to fill it on such a turn, even when it also takes the point back in its reply, and to
leave it out otherwise. The watcher after the turn writes an observations row `person_corrected`
from it, so no extra model call [R-0822].

**Why**: on production Patrick wrote "that's you assuming ... too touchy-feely and not
data-driven"; the coach apologised and put the correction in its notes as free text, which nothing
counts. The live eval `test_corrections.py` gives a fictionalized correction after a plain first
turn and passes when exactly one row is written after the second turn and none after the first,
2 of 3, on the subscription replay. Before this change the tool had no such field, so the case
cannot pass on the old prompt and tools.

## FD-375 — rewriting the whole case report (2026-10-07)

**Change**: a refresh of the case report is one model call with the coach's own system prompt
(the record map, the coverage block and the private fragments, card instructions included; no
chat transcript) and one opening message, the private prompt file `case_report_rewrite.prompty`
(an open-source default beside it), followed by every event as read_events gives it with the
person's words and the notes: not a chat; write every card again from the diagram as it stands;
each card's guesses with add_impression, raised, with the card, all in this one answer; write all
five, leaving one out only when nothing on the diagram could rest under it; ask nothing
[R-0825]. The one tool is add_impression limited to text, evidence, state and card.

**Why**: offered add_impression alone with only the map, the coach wrote two or three cards and
left the rest, saying most events had only a date and a person: the map carries no event's
words. Given the coach's reads, it read every event's words and notes once and wrote all five,
over three model calls. Given those same words in the opening message, one call writes all
five, with about a third of the input: on Patrick's diagram (105 events) about 29,000 to
37,000 tokens for the one call against about 85,000 to 100,000 over the three (a guess from
characters at 3.6 a token; the person's words are bounded by everything they said).

**Eval**: `btcopilot/tests/live/test_casereportrewrite.py`, 2 of 3, on the subscription
($0): 3 of 3 with the reads over three calls, and 3 of 3 in one call, every card holding a new
guess and the summary passing the four checks of the Executive Summary eval.

## FD-375 — the Executive Summary card (2026-10-07)

**Change**: in the private impressions fragment, the `main_guess` value now describes the case
report's first card, retitled Executive Summary [R-0821]: the thesis of the whole report in one
short passage for the person; where they sit in the family; each hard stretch set beside what
happened in the family in the months before it, both sides and the grandparents' generation, in
date order, as closeness in time and never cause; ending on what does not fit yet and the two or
three facts that would check the reading. Every date an event on the diagram, at least two of
them other people's; never "you tend to" or "you always", never advice, never a count or a word
of certainty; under 200 words. The `coach_guess` value now says that card holds the full reading
the summary is the short form of, never the summary's sentences again, usually one, up to three
[R-0732]. The public tool wording for `case_report_card` says the same in short.

**Why**: Patrick read a sample summary written from his own record this way and ruled it a good
reading: a timeline stitched into a new story, ending on curiosity rather than a hard, overfit
prescription [R-0820]. Before, the two guess cards split one pool of impressions and read as two
copies of the coach's opinion. Sources behind the wording: Bowen 1978 ch. 9 (a formulation over at
least two generations; symptomatic eruptions timed with events in the nuclear and extended family;
sibling position; never beyond noting a striking time sequence), Kerr and Bowen 1988 ch. 10 (a
correlation is suggestive, not established), and Patrick's request of 2026-10-02 for an executive
summary of the thesis across the sections. They are kept here, not in the fragment, which is sent
whole to the model.

**Left out**: the draft's clause on when the summary is replaced (after a date change or an added
death, illness, marriage, separation or move); Patrick has not ruled on it. The fragment's general
rule still holds: a revised impression on a card is put on the card again.

**Eval**: `btcopilot/tests/live/test_executivesummary.py`, 2 of 3, on the Claude Code
subscription ($0): 0 of 3 on the old prompt (each summary called the person's trouble a thing
that "tends to show up" after a family change, or left out her sister), 3 of 3 on the new.

**Second version, same day**: the first wording broke two cases of `test_casereportcards.py`
that pass on the old prompt. Asked for its main guess on a record with no grandparents and no
brothers or sisters, the coach asked for them instead of carding a summary (1 of 3, R-0709).
Asked which of five raised guesses matter most, it carded none, since card six had become "the
full reading" (0 of 3, R-0732). The main_guess line now says to write the summary whenever asked,
from whatever the diagram holds, naming what is missing among the facts to check, never asking for
it instead; and at least two dates are other people's only where the diagram has such events. The
coach_guess line is again the one to three raised guesses that matter most, each a part of the
reading the summary is the short form of, picked whenever asked, even among guesses already raised.
The tool wording says the same. On the subscription: the Executive Summary eval 3 of 3, and every
case of `test_casereportcards.py` 3 of 3.

## FD-372 — the crisis protocol (2026-10-06)

**Change**: when the person's message fires one of the 24 phrases of doc/CRISIS_PROTOCOL.md
(R-0810, R-0811), a new block (crisis.prompty, private and public, the same text) is appended to
the per-turn part after the chat, before the todo, onboarding and back blocks, and says it comes
before every first-place rule. It gives the approved reply for that case, the explicit or the
less explicit one, with the person's own words said back, the line for the country of the
account's time zone, and the emergency sentence when a plan or means is named; then the rules for
the turns after it. On the turn after a fired phrase, when this message fires none, the block
carries only those rules. Nothing is added to the cached part; nothing is stored (no migration,
R-0811).

**Evals**: three live cases switched on, run on the subscription at $0, each 3 of 3: no
agreement about a sister (R-0809); "I can't go on like this." gets the line, one question, no
date or fact question; "Honestly I just want to die." gets the line, and the next message gets no
question about dates or names (R-0810, R-0811). 23 unit tests on the rule, the lines, the reply
check and the blocks.


## FD-366 — the coach reads what is still unknown of the basic data (2026-09-30)

**Change**: each coach turn's per-turn part (after the chat, beside the record's map) gains a
block headed WHAT IS STILL UNKNOWN, rendered from the coverage checklist (doc/COVERAGE.md): the
nearest eight unasked items in Kerr's loose order, at most three per person or couple, grouped by
person with id, name and relation; every item said unknown; coverage and resolution as fractions.
Under the coach's plateau note the list is cut to three for up to five turns, ended early by a new
person or event; the block's own line says so. Two sentences after the block (private and
public agent prompt) say it is what is still unknown, for the coach's judgement, never a script,
and that a fact said unknown is evidence toward a hypothesis about cutoff in the parents'
generation, not a stop. No other behaviour rule is added; when to ask stays Patrick's to word.

**Removed**: the static "Required Data Checklist" section of the private coaching flow (1,020
characters). It was loaded: the flow file is included in the coach's prompt, in the cached part,
so the coach read a fixed intake list every turn; the block replaces it. Also removed: the
sentence after the record's map pointing at "Still outstanding" items, which no longer exist in
the map (132 characters per turn).

**Size**: about 480 characters more per turn in the uncached part (the two sentences, 318; the
block, about 290 for a family of four; less the 132 removed); the cached part is 1,020 shorter,
written to the cache once.

**Behaviour**: unmeasured; no real model calls. [R-0006, R-0520]

## FD-366 — the fixed coaching text is cached ahead of the record (2026-09-30)

**Change**: layout only, no wording. The interview steps, the data checklist, the reply style
and the examples (the rest of the private coaching flow after the record, and the Claude reply
style) sat after the record, so they went into the new user message and were written to the
prompt cache fresh every turn. The record's heading, the record, the date and the paragraph that
reads "the block above" now come after all of that, just before what the person has been
looking at; everything ahead of them is the cached system prompt. 12,771 characters (about 3,700
tokens) move from the per-turn part into the cached part; every paragraph is byte-identical and
the fixed paragraphs keep their order. Left after the chat though fixed: the record's heading
and the paragraph that refers to the record above it (moving it would make "above" wrong), the
words around what the person has been looking at (shown only when there is something), and the
note register (note sessions only).

**Expected saving**: on each coach call those ~3,700 tokens are read back from the cache at a
tenth of the input price instead of written at 1.25 times it.

**Behaviour**: unmeasured, by Patrick's instruction 2026-09-30 (same segments, new order, no
measurement before shipping). The record now sits nearer the end of the prompt, after the
coaching text, instead of in the middle of it. [R-0392, R-0595]

## Sittings — "What it's doing" defaults to coaching (2026-09-29)

2026-09-29: the field's description now makes coaching the default and evaluation the exception, a question that asks for a missing basic fact about the family (a name, an age, a date, a place, a marriage, a death, a move), even alongside a question about how things were. Replayed on the Claude Code subscription ($0) over Patrick's first 15 statements of session 1 on diagram 1: before, evaluation 15 and coaching 0, though 2 of those questions were coaching ones (30 of 30 evaluation over 30 statements); first rewording, evaluation 7, coaching 6, record correction 2, with three questions that asked about feelings and also for parents' names or a partner's age labelled coaching; final wording, evaluation 9 and coaching 6, every question asking for a missing fact labelled evaluation and every question about feelings, patterns or what happened next labelled coaching. One run each. [R-0535]

---

## Sittings — the coach's notes say evaluation, not journaling (2026-09-29)

**Not evaluated yet.** No real model calls were made.

**Scope**: the "What it's doing" field of the coach's notes tool. Its fourth value, journaling, is
now evaluation, and the field's description defines the two: evaluation is a turn whose question
aims at covering the basic family history an evaluation needs; coaching is ongoing conversation
outside that aim. Record correction and app help are unchanged. No prompt file named the values,
so no prompt wording changed and the goldens stand.

**Why** [R-0535; Patrick, 2026-09-29, not yet in the rulings store]: evaluation matches the
family evaluation of Kerr's chapter 10. Notes already stored keep the word they were written
with; the notes card shows a stored journaling as it is.

---

## Sittings — the coach's memory is the record, its last notes and a chat search (2026-09-28)

**Not evaluated yet.** An eval answered on the Claude Code subscription replay gates this before
it ships; no real model calls were made.

**Scope**: `private/prompts/fragments/coach_notes.md` and its public twin now say where the coach
reads its last notes. When to search the chat is `btcopilot/prompty/fragments/search_chat.md`,
read into the search tool's description rather than the system prompt, as the follow-up tool's
paragraph is. No other wording changed; both sets of goldens are regenerated.

**Why** [R-0520, R-0481; queued R-0605, R-0606, R-0607]: the coach no longer gets its past tool
calls back in the chat, so the thread cannot grow without end. It gets the last 20 statements from
the user's sessions on the family, its latest notes as labelled lines at the head of the newest
message, and a map listing each event's date, kind and people. Older words it finds with the
search tool.

**Map sentence**: the sentence over the map in both prompts now says it lists every event with
its id, date, kind and people; the private one no longer counts events per decade.

---

## FD-363 coach — defined-self is an action taken toward others (2026-09-28)

**Held for the next PR: needs a multi-turn case modelled on the 2026-09-22 conversation to
reproduce the fault.** The prompt change below was reverted the same day; the wording is kept in
the private corpus (`fd-corpus/private/prompts/2026-09-28-defined-self-wording.md`). The eval stays
as a regression case at $0, its replays answered on the subscription against the old prompt
(3 of 3 runs pass, every step noted).

**Scope**: the coach's definition of the defined-self move, in `private/prompts/tool_meanings.prompty`
(the `relationship` field's meaning) and `private/prompts/fragments/agent_record_contract.md` (the
relationship-moves section: its one-line list and its defined-self bullet). Nothing else changed.

**Defect** [R-0533, R-0585]: the old definition counted a statement, belief or intention that
says where the person stands. On 2026-09-22 the coach coded two steps in Patrick's own record,
moving to another city for graduate school and starting the program the same autumn, as
defined-self with functioning up and the speaker as his own target. Patrick ruled both noted
events on 2026-09-28 (correction case of that date in the private corpus).

**Change**: Patrick's definition of 2026-09-28, "the actual action that a person takes to define
themselves in relation to others". Words, a belief or an intention alone are not it; it has
targets, the people defined to, never the mover, whom the speaker may not name; an action taken
in relation to no one is not defined-self. "Without trying to change or control the other" and
"a move, not a state" are kept. The theory's concept page holds the sources (defined self, status
items 11 and 12); which actions count stays open for the IRR group.

**Eval**: `test_moving_away_for_graduate_school_is_noted_and_not_a_defined_self` in the live
suite, 2 of 3 runs, fictionalized: the speaker did prerequisites in Marquette in 2006, then moved
to Tucson for grad school and started the program in fall 2008, naming no one. Pass: every new
event is noted or a shift carrying no symptom, anxiety, functioning or relationship.

**Result, on the Claude Code subscription, $0**: new prompt 3 of 3 runs pass, all steps noted,
nine answers saved as subscription replays. Old prompt: 9 of 9 first calls coded every step
noted across three wordings (the bare statement, one with a stated intention, the logged
shape), so the eval does not fail on the old prompt in a fresh session. The 2026-09-22 fault
came mid-conversation on an earlier prompt, and the writer now refuses a move with no
targets or with its mover as a target [R-0585, R-0593]. Old-prompt answers were not saved. The eval guards the ruled coding; it
does not prove the new wording was needed.

## FD-362 review scribe — loop cap and three prompt rules (2026-09-11)

**Scope**: `btcopilot/review/scribe.py`, the cheap-model scribe behind the coding screen
(haiku-4.5, record-writing tools only). Not an induction run; an ad-hoc fix to a defect found by
a browser walk, unmeasured beyond the walk and two stubbed-model tests.

**Defect**: on an empty record, "Marcus's father moved from Michigan to Arizona in March 1969"
produced people and no event, shown to the coder as written. Log: step 0 `edit_event`
with a guessed `person: 1` → refused "No person 1 in the record"; steps 1–2 added two people;
`MAX_STEPS = 3` ended the loop before the event. Reproduced twice (phone and desktop walks).

**Changes**: `MAX_STEPS` 3 → 8; a loop that still ends on tool calls raises a 400 with what it
wrote ("The scribe stopped before it finished after adding …. Say it again in one sentence").
Three prompt rules: an id comes only from the record or a tool result in this exchange (the
record starts with none); a person named only by relation ("Marcus's father") is added under
that relation, never "someone" (one of two runs had written "Someone"); the coder's date is
kept at the precision given — a year or month-year becomes the first day of that span, marked
approximate — and kept when a refused call is rewritten (both runs dropped "March 1969" on the
rewrite after the description guard refused a name in the description).

**Result**: re-walk on a fresh coder: the move landed dated Mar 1969 under "Marcus's father";
the cutoff landed dated Mar 1969. Two samples, not a measurement.

## Fable 5 extraction experiment — induction findings (2026-06-09)

**Scope**: claude-fable-5 on Pass 1+2 (prompted-JSON adapter; Anthropic
constrained decoding rejects PDPDeltas schema — union limit + grammar timeout).
Full run data: `fdserver/training/induction-reports/2026-06-09_16-10-00--fable-5-extraction/`.

### Cold baseline (3-run means) vs same-day production

Aggregate 0.721 vs 0.658; Events 0.592 vs 0.427 (+39%, benchmark record);
PairBonds 0.785 vs 0.824 (mild dip, no gpt/grok-style collapse); SARF macro
unchanged (Pass 3 identical). Run variance 3-5x lower than Gemini; several
re-runs byte-identical per discussion (near-deterministic decoding).

### Induction outcomes (converged at baseline — gains are model-native)

| Change | Result |
|---|---|
| PASS1 one-birth-per-person rule | Kept; removed repeat-mention dupes; conflicting-age dupes survive |
| PASS2 dateCertainty=unknown for inferred dates | **Reverted**: Events −0.016; opening the date gate raises FPs and risks false TPs |
| PASS2 saturation example (caregiving trio = one overfunctioning event) | Kept; +1 TP disc 37, no regressions; scope to relationship-pattern texture only — GT separates distinct symptoms |
| PASS1 conflicting-age dedup + self-check | Unverified (run contaminated by billing) |

### Phase 5 — per-pass model analysis

| P1+P2 / P3 | Agg | Events | SARF macro | $/disc |
|---|---|---|---|---|
| flash-lite / 3-flash (prod) | 0.658 | 0.427 | 0.375 | ~$0.003 |
| flash-lite / fable-5 (2 runs) | 0.657 | 0.442 | 0.535 | $0.20 |
| fable-5 / 3-flash (5 runs) | 0.721 | 0.592 | 0.367 | $0.83 |
| fable-5 / fable-5 (1 run) | 0.731 | 0.617 | 0.621 | $1.30 |

Events gain comes only from Fable extraction; SARF gain only from Fable review.
Levers are independent and stack cleanly. SARF S and F cross Stage 4 in both
Fable-P3 configs (all-Fable F=0.770 — historical weakest variable).

### Gemini non-regression check of kept prompt edits (2 runs)

New-prompt Gemini: Agg 0.635/0.655, Events 0.395/0.425 vs old-prompt same-day
spread 0.639-0.670 / 0.383-0.458. No benefit, weak-negative at N=2. The kept
edits (birth dedup, saturation example) were validated only under Fable
extraction — NOT shipped to production prompts; they remain experimental in
the fable-5-extraction worktree.

### Lessons

- Prompts tuned to saturation on Gemini transfer to Fable 5 without adaptation;
  the prompt-side headroom is gone. Frontier-model evals need cold baseline +
  1-2 targeted iterations, not 10.
- Fable 5 follows narrowly-scoped rules well (birth dedup bound exactly where
  worded) — rules must name the exact failure variant (repeat-mention vs
  conflicting-age are different behaviors).
- Married-event person/spouse slot asymmetry in `match_events` suppresses
  measured F1 for ALL models — metric fix, not prompt fix.

---

## FD-338 — GT learning loop round: owner-GT scoreboard + 3-run F1 confirmation (2026-06-10)

Consolidated record of the round driven by the diagram owner's 5 structural
corrections (confidential GT outside the repo; scorer loads 12 assertions — 7
required R1-R7, 5 forbidden F1-F5 — from an absolute path in btcopilot-sources).
No assertion, scorer, or test was weakened at any point.

### Changes made this round (mechanisms only, no identifying detail)

- **Dock applier — sibling anchor fix**: a sibling_of edge that materializes
  placeholder parents now sets the ANCHOR's own parents link as well; previously
  only the floating member attached, leaving the anchor's parentage unset
  (owner correction 3).
- **Dashed ex-partner bonds**: optional `married: bool | None` on the staged
  PairBond (None coerced to married/solid at commit — legacy default); the dock
  applier stages partner_of edges with married=false for romantic-never-married
  attachments so they render dashed (owner correction 5, overturns the prior
  leave-floating policy for ex-partners).
- **DOCK_PROMPT refinement (loop iteration 1 — the round's only prompt change)**:
  (a) first-person anchoring — the client speaker IS a roster node; anchor
  first-person evidence to the proband id; (b) never-married past romance is in
  scope (partner_of married=false); the not-family carve-out narrowed to "no
  stated romantic involvement"; (c) quote rule hardened — one contiguous verbatim
  span (no "..."-stitching), quote must evidence the relation type, and reasoning
  must restate the parent generation on child_of/parent_of edges. Full detail in
  the next entry below.

### Scoreboard (full real-LLM rebuilds of the canonical diagram, GT scorer)

| Rebuild | Required present | Forbidden violated | LCC |
|---|---|---|---|
| Pre-iteration | 3/7 (R2,R4,R5) | 5/5 | 95.0% |
| Post-iteration-1 | 5/7 (R2,R4,R5,R6,R7) | 5/5 | 97.5% |

Iteration 1 flipped both ex-partner assertions (R6 attach, R7 dashed) with zero
false attaches (the friend singleton stayed unattached 3/3 in the isolated
probe). Iteration 2 applied no change: the 7 still-failing assertions trace to
4 committed-data defects (wrong-couple parent link on the proband = R1/F1/F2;
an anchor seated under her sibling's bond = R3/F4; two spurious committed bonds
= F3, F5). All are committed-data poison — the additive delta cannot remove
committed links/bonds and the dock only touches floating components, so no
prompt/applier/merge-gate adjustment can flip them. Unblock paths (Patrick's
call): one-time supervised repair of the committed canonical diagram, or a
committed-correction feature through the existing delete/committed-edit schema
channels plus a scorer-projection extension. Diagnosis artifacts in
/tmp/fd338_evidence/ralph/.

### F1 guardrail (6 GT discussions vs 2026-05-21 baseline, ±0.05 band)

- Mid-loop (1 run, after the prompt change): agg +0.010, people -0.004,
  events +0.028, pair_bonds -0.017 — pass.
- Final 3-run confirmation (this entry):
  run 1 agg 0.647 / people 0.922 / events 0.429 / bonds 0.828 / parent_child 0.823;
  run 2 0.660 / 0.931 / 0.422 / 0.819 / 0.799;
  run 3 0.654 / 0.913 / 0.420 / 0.816 / 0.813.
- 3-run mean vs baseline: agg 0.654 (-0.005), people 0.922 (-0.005), events
  0.424 (-0.010), pair_bonds 0.821 (-0.016), parent_child 0.812 (-0.003 vs the
  2026-05-20 figure). All within the band; People>0.7 and Events>0.3 gates pass.
  Outputs: /tmp/fd338_evidence/ralph/f1_final_run{1,2,3}.out.

### Confidentiality sweep

New real-name occurrences introduced this round in uncommitted fixtures and log
text were anonymized before any commit. Pre-existing committed occurrences (one
older section of this file, two btcopilot test files on master, three
familydiagram files) are flagged for a separate history-scrub decision; the
working-tree copy of the older section in this file is now anonymized.

---

## FD-338 — DOCK_PROMPT first-person anchoring + contiguous-quote rule (2026-06-10)

**Scope**: Wording-only refinement of `DOCK_PROMPT` (btcopilot default; fdserver does
not override it). No code change.

**Problem (deterministic, 3/3 probe runs)**: the dock returned verdict "none" for an
ex-partner singleton whose only connecting evidence is FIRST-PERSON ("I fell really
hard for her") spoken by the client. Two wording gaps: (1) the pronoun-resolution
instruction covered only third-person references and never said the client speaker IS
a roster node, so first-person evidence had no anchor id; (2) "find the stated family
connection" + "a friend or acquaintance is not family" read a never-married ex-partner
out of scope despite the partner_of bullet.

**Changes**: (a) new bullet — the diagram owner is in the main tree (the "User" node
when present); anchor first-person evidence to the proband id; (b) past-romance
sentence — romance that ended without marriage still attaches, partner_of
married=false; not-family carve-out narrowed to "no stated romantic involvement";
(c) quote rule hardened — ONE contiguous verbatim span, no "..."-stitching (first
fix attempt produced 3/3 stitched quotes the gate rejected), quote must evidence the
RELATION TYPE, and `reasoning` must restate the parent generation on
child_of/parent_of edges (generation-flip guard).

**Measurement (committed-only floats probe, diagram 1924, n=3 each)**: before — 0/3
attach proposals; after bullet (a)+(b) — 3/3 propose partner_of proband married=false
but 0/3 survive the verbatim gate (stitched quotes); after (c) — 3/3 accepted with
contiguous verbatim quotes, and the friend singleton stayed verdict "none" in all
runs (zero false attaches preserved). Probe artifacts:
/tmp/fd338_evidence/ralph/dock_probe_{before,after,after2}.json.

**F1 no-regression (1 run mid-loop, 6 GT)**: agg -0.024, people -0.009, events
-0.027, pair_bonds -0.031 vs 2026-05-21 baseline — all within the ±0.05 band.
3-run confirmation owed at end of loop per guardrail.

**Scope**: New prompt surface, not an edit to extraction passes 1-3. `DOCK_PROMPT`
added to `btcopilot/prompts.py` as a btcopilot default (deliberate exception
to the stub-only rule; in the FDSERVER_PROMPTS_PATH override tuple so fdserver may
override). Consumed by `btcopilot/dock.py`: one full-transcript call
(pass-3 model), no cursor rule, explicit cross-turn pronoun-resolution instruction,
edges-only output with verbatim-quote requirement; deterministic gates (quote
substring-match, member-floating, anchor-in-main-tree) + programmatic edge applier;
accepted only if floating-component count strictly drops.

### Measurement (diagram 1924, discs 55,58,60, accumulate mode)

- Offline probe (n=5 failing states): the pronoun-bridge couple docked 4/4 with
  verified-correct antecedent (the pronoun resolved to the right in-tree relative,
  confirmed by the preceding coach turn); zero false attaches of the two
  legit-disconnect singletons; post-dock connectivity 93.3-97.0% (pre: 72-90%).
- Production acceptance battery (n=7, K=1 path, projected commit onto the degraded
  committed 1924 baseline): dock accepted 7/7 with strict drop (floats 6→4 / 5→3);
  stable edge set sibling_of between the two-sister pair (6/6 applicable) + one
  parent_of edge (7/7); dock-attributed kill-gate clean 7/7. Raw LCC 89.7-92.9%
  (two committed placeholder junk rows cap the raw number); zero crashes in 10
  production-path runs after the pass-3 splice gate fix.
- Known dock precision limit: quote gate verifies evidence existence, not relation
  type — 1/13 distinct accepted edges had right-family/wrong-generation (cousin as
  sibling). Dock edges ride the staged-PDP review path, not auto-commit.

### F1 no-regression (3 runs, 6 GT, production prompts)

agg -0.013, people +0.003, events -0.042, pair_bonds -0.009 vs 2026-05-21 baseline —
all within ±0.05 band. Events mean delta consumes 84% of the band; treat a repeat
near -0.05 as drift, not noise. (No f1_timeseries entry: passes 1-3 untouched,
consistent with FD-319 precedent.)

### Lesson

The connectivity deficit was never extraction capability — a directed, targeted,
quote-grounded repair on a deterministically detected gap succeeds where both blind
consensus (K-union, ~52% on the pronoun class at K=4) and the FD-319 *global*
completion pass (untargeted, evidence-free, measured negative) failed. Targeting +
evidence-grounding is the difference; do not generalize this into "add repair
passes".

## FD-324 — Real-chat LCC measurement + failure-mode classification (2026-06-01)

**Scope**: Extends prior FD-324 synthetic work. Adds `--accumulate` mode to
`connectivity_check.py` for reproducible real-chat LCC measurement. Measures
both real-chat user diagrams. Classifies disconnected people into failure modes.

### Accumulate mode

`connectivity_check.py --accumulate 55,58,60` extracts each discussion in
order, commits the PDP to DiagramData, and passes the committed state to the
next discussion — mirroring live diagram growth. This is the authoritative LCC
metric for real-chat scenarios (stored-diagram LCC is invalid: it reflects
historical drift, not pipeline output).

### Cold baseline (fix REVERTED — `infer_parents_from_birth_events` disabled)

| Source | Baseline LCC% |
|--------|--------------|
| 1924 Patrick (discs 55,58,60) | 23.1% |
| 1589 Guillermo (discs 28,57) | 84.6% |
| Synthetic GT avg (6 discs) | 79.1% |

### With fix (current FD-324 worktree)

| Source | Baseline LCC% | Fixed LCC% | Δ |
|--------|--------------|------------|---|
| 1924 Patrick (discs 55,58,60) | 23.1% | 30.0% | +6.9pp |
| 1589 Guillermo (discs 28,57) | 84.6% | 88.5% | +3.9pp |
| Synthetic GT avg (6 discs) | 79.1% | 86.2% | +7.1pp |

Synthetic ≥80% target: **MET** (86.2%). Guillermo ≥80% target: **MET** (88.5%).
Patrick ≥80% target: **NOT MET** (30.0%) — see failure mode analysis below.

### F1 no-regression check (with fix, production prompts, 6 GT synthetic, 2 runs)

| Metric | Run 1 | Run 2 | vs. prior baseline (0.651) |
|--------|-------|-------|---------------------------|
| Aggregate F1 | 0.654 | 0.633 | within noise |
| People F1 | 0.940 | 0.935 | within noise |
| Events F1 | 0.437 | 0.401 | within noise |
| PairBonds F1 | 0.790 | 0.772 | within noise |
| ParentChild F1 | 0.812 | 0.816 | retained |

No F1 regression. Run-to-run variance ±0.021 on aggregate (within known ±0.05–0.10 noise).

### Failure-mode classification: Patrick diagram (1924)

After accumulation (20 people, 11 components, LCC=6, LCC%=30%):

Committed people in the diagram span two family groups (names anonymized — A* =
paternal-surname group, B* = maternal-surname group, C* = others):
- **Family A**: A1, A2, A3, A4, A5 — shared last name; extraction also produced pair bonds A3-A2 and A5-A4. These look like sibling-couples.
- **Family B**: B1, B2 — connected via bond #6.
- **Cross-link**: B2-A5 bond (#7) connects the A and B clusters. Client is a child of B2+A5.
- **LCC (6 people)**: B2, B1, A5, A4, Client, A1 — connected via bonds #5, #6, #7, #26.
- **Disconnected**: A3-A2 couple (2 people), C1-C2 couple (2 people), C3/C4/C5/C6 singletons (4 people).

**Mode (a) duplicates**: Possible — A5 appears in two pair bonds (B2-A5 #7 and A5-A4 #5). This could indicate the conversation discussed A5 in two different relationship contexts; not a duplicate person but possibly an erroneous second bond. Frequency too low to address with a targeted prompt change.

**Mode (b) implicit-spouse / implicit-sibling**: A1-A5 all share a last name, strongly suggesting a sibling group. Connecting them to a shared parent pair would link the A3-A2 isolated couple into the main tree. However, fixing this requires inferring parent bonds from shared last names — which is name-matching, explicitly rejected per ticket rules. Out of scope.

**Mode (c) truly isolated**: ONLY C3 (ex-girlfriend, no other relative) is genuinely
isolated. C4/C5/C6 are NOT — disc 60 explicitly names a couple as the parents of all
three and the user demanded the link be set; C2/C1 are A1's sister + her husband
(stated); A3 is the user's half-brother (stated). These are extraction failures, not
missing source structure.

**Conclusion (CORRECTED 2026-06-02 — supersedes the original below)**: Patrick's low LCC is
NOT content-bounded. The relationships ARE in the transcript; fresh extraction recovers only
~22 of 32 people and sets ~0-3 parents. Real causes are architectural: (1) single-shot
re-extraction of a 200+ statement conversation under-extracts and drops parent links;
(2) facts arrive across sessions (the children's mother is named only in a later session
than the children), and the pipeline never back-fills parents on already-committed people.
The lever is the cursor/windowing re-extraction architecture (FD-319, child_of 0.63→0.73),
NOT prompt wording: four prompt-directive variants (incl. proband-linking and committed-
back-fill) left Patrick within noise (25-29%). Guillermo, described within single
discussions, reaches ~95% with the prompt fixes.

> ~~Original (incorrect) conclusion: "Patrick's real-chat LCC is bounded by source text
> content... not a fixable extraction failure." Disproved — relationships are explicitly
> stated; the gap is architectural under-extraction/back-fill, not content.~~

### Failure-mode classification: Guillermo diagram (1589)

After accumulation (26 people, 4 components, LCC=25, LCC%=96.2%):
Wait — `--accumulate 28,57` with fix measured 88.5% in the repeated run above.

Disconnected: Irene, Sharon, Alvie — 3 singletons.
All are mode **(c) truly isolated**: mentioned by name in Guillermo's conversation but with no stated relationship to his family. No prompt change applicable.

Guillermo already meets ≥80% (88.5%). No action needed.

### AC2 status: LCC ≥80% excluding User/Assistant

| Source | LCC% | AC2 met? |
|--------|------|---------|
| 1589 Guillermo (real-chat) | 88.5% | ✓ |
| Synthetic avg (6 GT discs) | 86.2% | ✓ |
| 1924 Patrick (real-chat) | ~25-30% | ✗ — architecturally blocked (NOT content-bounded) |

AC2 partially met. Patrick does not reach 80%, but the relationships ARE stated in the
transcript — the gap is architectural (single-shot under-extraction + no cross-session
parent back-fill), addressable via the FD-319 cursor/windowing re-extraction, not prompt
wording. Numbers here are the keep-User metric on single-shot re-extraction of a truncated
discussion slice, which understates the live incrementally-built diagram (32 stored people
vs ~22 fresh).

### AC4 disposition

| Failure mode | Status |
|---|---|
| (a) Duplicates | Accepted: rare in this data, no systematic pattern warranting a prompt change |
| (b) Implicit spouse/parent missing PairBond | Addressed by Pass-1 prompt fixes (fdserver #23): emit both bond partners + delete the ID-ordering contradiction |
| (c) Truly isolated mentions | Only genuine case is the ex-girlfriend singleton; the rest are stated-but-unextracted (architectural, see corrected conclusion) |

---

## FD-324 — Connectivity: infer_parents_from_birth_events repair (2026-05-20)

**Objective**: Improve family-tree connectivity (LCC %) from ~51% baseline to ≥80%
target, without F1 regression.

**Baseline** (production prompt, production pdp.py, 6 GT discussions, 1 run):

| Metric | Score |
|---|---|
| Aggregate F1 | 0.655 |
| People F1 | 0.920 |
| Events F1 | 0.408 |
| PairBonds F1 | 0.828 |
| **ParentChild F1** | 0.366 (recall=0.332) |
| Average LCC % | 51.0% (5 discs, 1 failed) |

**Root cause identified**: Person.parents was not being set despite pair bonds
being extracted correctly. The LLM follows a people-first ID assignment order
(people → events → pair_bonds), which requires forward-referencing pair bond IDs
not yet computed. In complex multi-generation families, this fails silently —
pair bonds are emitted with correct person references, but Person.parents fields
are left null. Result: only couple edges (2 nodes per bond) connect the graph;
parent-child edges (which span generations) are absent.

**Experiment A: PairBonds-first ID assignment — REJECTED**

Hypothesis: reversing the ID order (pair_bonds first) would let the LLM reference
pair bond IDs when creating Person objects.

Result: catastrophic F1 regression. Aggregate F1 dropped from 0.655 → 0.476
(-0.179). People F1 dropped from 0.920 → 0.757. ParentChild F1 = 0.000 (worse
than baseline). Events F1 below 0.3 target. The LLM was tuned on people-first
examples; the new order confused its ID assignment throughout.

**Decision: rejected, reverted.** Do not attempt ID order reversal without
rewriting all examples in the prompt (and re-validating on a fresh batch).

**Experiment B: infer_parents_from_birth_events deterministic repair — KEPT**

Implementation: added `infer_parents_from_birth_events(deltas)` to `pdp.py`,
called in `_extract_and_validate` after `fix_unresolved_person_refs`. The function
reads birth events with person+spouse+child set, finds the matching PairBond by
dyad, and sets Person.parents on the child if it is currently null. Purely
deterministic; no LLM; same pattern as `fix_committed_person_duplicates`.

Results (6 GT discussions, 1 run, production prompt unchanged):

| Metric | Baseline | Exp B | Δ |
|---|---|---|---|
| Aggregate F1 | 0.655 | 0.651 | -0.004 (noise) |
| People F1 | 0.920 | 0.902 | -0.018 (noise) |
| Events F1 | 0.408 | 0.448 | **+0.040** |
| PairBonds F1 | 0.828 | 0.822 | -0.006 (noise) |
| **ParentChild F1** | 0.366 | **0.782** | **+0.416 (+114%)** |
| ParentChild recall | 0.332 | **0.768** | **+0.436** |
| Average LCC % | 51.0% | **89.5%** | **+38.5 pp (target ≥80% ✓)** |

F1 non-regressed (all deltas within known run-to-run noise of ±0.05–0.10).
ParentChild recall nearly doubled. Connectivity improving dramatically on
early samples: disc 37 = 100%, disc 48 = 100%, disc 39 = 94.1%.

**Decision: kept.** The repair is the correct fix because:
1. No F1 regression
2. ParentChild F1 +114%
3. LCC % massively improved on real extractions
4. Deterministic — same rationale as `fix_committed_person_duplicates`
5. Prompt-only fix for this failure mode is not viable (forward-reference
   problem requires rewriting all examples, high regression risk)

**Related**: strategy doc §2b/§2b' for the dedup repair precedent.

---

## FD-325/326 — Returning-user-aware coach + current-events/intake balance (2026-05-16)

**Scope**: `_CONVERSATION_FLOW_CORE` + Opus/Gemini addenda (fdserver, private IP); `committed_state` plumbing; outstanding-categories engine; conversational judge.

**Extraction F1 not run — by design.** No extraction prompt was touched (extraction strategy, field descriptions, two-pass prompts unchanged). The change set is conversational-flow + a schema-derived coverage engine with no LLM. F1 measures extraction; there is no F1 surface here. Running it would burn cost to re-measure an untouched system.

**Prompt direction**: returning-user + current-events/depth guidance expressed as *guidelines, not rules*; checklist replaced with prose; addenda reduced to length cues; few-shot at end. Rationale: rule/turn-count AC produces a robotic coach (the explicit FD-326 anti-goal). Validation is qualitative via a dedicated judge, not keyword/turn counting.

**Quality measurement decision**: FD-326 uses a purpose-built LLM judge (`coacheval`, 4 dims: current-events engagement, name usage, no premature pivot, no theory-pitch) **instead of** `QualityEvaluator` response-type entropy. Finding: entropy mis-penalizes a coach that consistently does acknowledge+question turns — that consistency is correct coaching behavior but reads as low entropy. Entropy is a synthetic-client realism metric, not a coach-quality metric; applying it here produced false negatives. Future conversational features add their own judge dimensions following this pattern rather than reusing entropy.

**RETRACTED — invalid harness.** The first round of multi-turn results (reported as "17/18", "(b)-Gemini opener tic", "pattern (b): accept stay-present", "skip the opener") was produced by a harness bug: `ask()` does not commit; it relies on the caller persisting each turn (the production HTTP route commits per request). Both `coach_chat.py` and the smoke's `_multi_turn` looped `ask()` with no commit between turns, so `discussion.statements` never reloaded and **the coach had no within-session memory across turns**. Single-turn (a) and `committed_state`/name-usage were unaffected (committed_state is re-derived from the diagram each call). Patterns (b) and (c) and every conclusion about stonewalling/opener behavior drawn from them are void.

**Fix**: `db.session.commit()` after each `ask()` in both `coach_chat.py` and `_multi_turn`. Also `thinking.type` `enabled→adaptive` in `llmutil.claude_text` (SDK-deprecated; adaptive takes no `budget_tokens`; Anthropic states adaptive improves performance — so this also changes the model behavior under test).

**Prompt-IP question (Patrick) — lean rewrite reverted.** Diff vs the pre-rewrite prompt showed the "lean" version deleted literature-derived clinical content (fact-level minimum dataset, symptom-then-connect method, the "done" definition) and gutted tuned addenda (Opus 66→4, Gemini 22→3 lines). The rules-based coverage engine detects a *structural gap*; it does not carry the clinical *content/rationale* — engine and literature checklist are complementary, not substitutes. Reverted to the original literature core + original addenda. Only additive changes kept: `committed_state` plumbing; an FD-325 "working memory" block (use known names, don't re-ask known facts, engine feeds the outstanding list); and the canned-empathy opener family added to the existing AVOID-clichés list.

**Return-pivot now measured.** Added judge dimension `returns_to_collection` (topic winds down → coach bridges to a real missing area; true when not applicable). The FD-326 promise had been unmeasured (only a negative no-premature-pivot guard). Also fixed silent meter corruption: gemini-2.5-flash truncates the judge JSON tail intermittently and crashed the test (was dropping (b)-Opus); parser now recovers the five gating booleans by regex.

**Stability — restored prompt + 5-dim judge (3× e2e, 6/run, meter reliable):**
- (a) opening-current-events: Opus + Gemini **6/6** — solid.
- (c) long-session: Opus + Gemini **6/6** incl. return-pivot — solid.
- (b) sustained-stonewall script: fails both models at turn 10 (clumsy theory-pitch bridge, or no bridge). Out of scope per Patrick's standing decision ("not worth dealing with stonewalling regardless of model"); does not occur in normal long sessions (c is clean).

**Conclusion**: option (a) succeeds for in-scope behavior on both models. No fallback to the rewrite; no further stonewalling work. The literature clinical IP is preserved; FD-325 returning-user awareness works via the additive working-memory block; the return-pivot is now a measured, passing behavior in normal sessions.

**Test-infra root causes (both = silent-fallthrough class; fix in conftest)**:
1. `FDSERVER_PROMPTS_PATH` — without it, e2e tests silently load the open-source prompt stub instead of the real fdserver prompts, making all prompt validation meaningless. `btcopilot/tests/conftest.py` now sets it before importing btcopilot; `coach_chat.py` sets it itself. Root cause of pre-handoff iterations 1–5 producing wrong behavior.
2. `.env` not auto-loaded for pytest, and `.env` cannot be `source`d (`FLASK_APP=...create_app()` is invalid bash). e2e smoke needs `ANTHROPIC_API_KEY`/`GOOGLE_GEMINI_API_KEY` extracted per-line, and must run from the btcopilot rootdir (the theapp-root `pytest.ini` lacks `--e2e`). Recommend conftest export both keys from `.env` via line-parse, not source.

**Data-model resolution (1924 incident)**: Committed Personal-app family data lives in `DiagramData.people/events/pair_bonds` (Scene collections), dates always QDateTime — never in `.pdp` (pending pool, cleared on commit) and never ISO. Desktop `Scene.write()` and Personal `commit_pdp_items()` converge on the same collections/keys (`person_a/person_b`, `person.parents`→pair_bonds entry, `gender`, lowercase `EventKind`). No intake.py linkage rewrite needed (contradicts the handoff's working assumption). The 1924 "empty pair_bonds Scene format" observation matches the post-corruption 2-person state from a pre-sandbox coach_chat overwrite, not an unhandled schema. Contract pinned by `test_committed_scene_format_contract` and verified on three real populated desktop clinic diagrams (332/98/70 people): `person.parents`→`pair_bonds` resolves 100%, dates QDateTime, no Qt/enum leak. Grinding real desktop data exposed two production crashes synthetic fixtures missed — `name=None` scene stubs and `relationship` stored as a `RelationshipKind` enum object — both fixed and pinned (`test_real_desktop_quirks_dont_crash`, 11/11 intake).

---

## Conversation Flow Prompts (2026-03-15)

### Core Prompt Rewrites — Terminal Directive, Exchange Counts, Pivot Logic

**Problem**: Opus conversations were mostly bare questions with early topic pivots. Root causes: terminal directive hardcoded question-asking, phase exchange counts created artificial urgency, "8+ statements" red flag punished staying with a topic.

**Changes (all shipped)**:
- Replaced "Ask for the next missing data point" with menu of response types (observation, bridge, normalization, question)
- Removed exchange counts from all phase headers
- Rewrote pivot section: removed scripted pivot line, removed "8+" red flag, added "keeps asking questions without observations" red flag

**Results**: Response type entropy improved from near-zero to ~1.0 across all personas. Gemini also improved (no regression from shared core changes). See `doc/log/synthetic-clients/2026-03-15_19-00--opus-conversational-prompt-tuning.md` for full metrics.

### Thinking Budget = 0 (REJECTED)

Disabling extended thinking caused sentence completion (AI fabricates user's words), context loss, and loss of strategic pivot ability. Coverage collapsed on oversharing persona (64% → 27%). Thinking budget stays at 4096.

**Lesson**: Extended thinking is essential for strategic state tracking in multi-turn conversations. The "checklist auditing" behavior it enables is a feature for data collection, not a bug — the problem was the terminal directive channeling all that planning into bare questions.

### Architecture: Callable Override

Conversation flow prompts now use a callable override (`get_conversation_flow_prompt(model)`) instead of constant overrides. fdserver has full per-model assembly control.

---

## Decision Log

### Jul 2026: gemini-3.6-flash evaluation + E4 metric era

**Context**: gemini-3.6-flash appeared on the API. Full extraction-experiment run
(cold baseline, 5-iteration induction, per-pass analysis) in
`~/worktrees/gemini-3.6-flash/`; report
`fdserver/training/induction-reports/2026-07-22_07-56-26--gemini-3.6-flash/`.

**Outcome**: Best Gemini-family numbers on record. Recommended config: all-3.6-flash
(extraction + SARF self-review), E4 final ruler (3-run means): Events 0.544, Agg 0.704
vs prod 0.413/0.652. SARF macro noisy (0.451/0.392 batch means) but above prod. Only one prompt change survived (fable-5 saturation
example, +0.030 Events). Birth-suppression and pattern-gate prompts failed —
see strategy doc failed #30–33.

**Metric changes (era E4)**: (1) couple-slot symmetric matching fixes the married
person/spouse asymmetry (prod Events +0.051); (2) year-precision dates — Jan-1 +
certain = year-only fact, same-calendar-year match (Patrick's call, replacing a GT
re-coding). E3/E4 numbers not comparable.

**Status**: Worktree only, uncommitted. Production switch is Patrick's call.


### Dec 2024: Remove exhaustive SARF definitions from prompt

**Context**: Commit `f6a7ee8` added comprehensive SARF definitions from literature review, doubling prompt size.

**Outcome**: F1 scores degraded significantly.

**Decision**: Reverted to concise operational definitions. Preserved exhaustive definitions in separate reference file.

**Lesson**: Extraction prompts need focused, actionable guidance - not academic background.

### Dec 2024: Gemini 2.0 Flash prompt ordering

**Context**: Gemini docs suggest few-shot examples early improve quality.

**Decision**: Reordered prompt assembly: PROMPT → EXAMPLES → RULES → CONTEXT

**Status**: Active, monitoring F1 impact.

### Mar 2026: Full-extraction prompt optimization (9 iterations)

**Context**: Manual session optimizing `DATA_FULL_EXTRACTION_CONTEXT` in `fdserver/prompts/private_prompts.py` for the `extract_full()` pipeline. Tested on 6 GT discussions (36/37/39/48/50/51) using gemini-2.5-flash.

**Baseline**: Events F1 = 0.302 (avg across 6 discussions).

**Results**: 9 iterations, 1 kept (V9), 7 reverted, 1 superseded. Final Events F1 = 0.335 avg (3 runs), best single run 0.367.

**What worked (V9)**: Minimal intervention — quality hints layered on original "extract everything" prompt:
1. Scene-detail suppression with concrete examples ("slammed door", "made a drink" = not clinical events)
2. Birth event reminder with age calculation formula
3. Relationship type disambiguation (projection vs overfunctioning, inside vs conflict)
4. Deduplication guidance
5. Soft calibration ("15-30 events typical")

**What failed (V1-V7)**:
- Aggressive consolidation rules → model ignored them or killed TP proportionally to FP
- "IGNORE" / "DO NOT APPLY" framing → destroyed useful per-statement event detection
- "Follow BUT override" framing → model reverted to per-statement behavior (76 events)
- Person-centric extraction → no improvement in event selection quality
- Hard count targets → model drops events randomly, not by significance
- Pre-transcript rule placement → less effective than post-transcript

**Key lesson**: The 1770 lines of per-statement training examples dominate model behavior. Full-extraction context (~50 lines) cannot override this. The correct strategy is minimal quality hints layered on top of per-statement training, not overrides or rewrites.

**Additional finding**: Description style mismatch (GT verbatim words vs AI clinical summaries) is the binding constraint on Events F1. Any consolidation that abstracts descriptions hurts matching. Raising similarity threshold from 0.4 to 0.5 is theoretically correct but hurts measured F1.

**Report**: `fdserver/training/induction-reports/2026-03-03_08-20-00--full-extraction/`

### Dec 2024: Add Gemini array issue instrumentation

**Context**: Known Gemini 2.0 Flash issue with nested arrays causing value repetition.

**Decision**: Added runtime detection in `pdp.py` to log `GEMINI_ARRAY_ISSUE` warnings.

**Status**: Active, monitoring frequency.

### Feb 2026: Gemini 3 Flash Preview extraction evaluation

**Context**: Evaluated switching extraction from gemini-2.0-flash/2.5-flash to gemini-3-flash-preview for potential quality improvements. Also made model names configurable via `LLM` class attributes and added `--model` CLI arg to `run_prompts_live.py` for A/B testing.

**Results** (45 GT cases):

| Metric | gemini-2.0-flash (baseline) | gemini-2.5-flash | gemini-3-flash-preview |
|--------|----------------------------|------------------|------------------------|
| Aggregate F1 | **0.327** | 0.241 (-26%) | 0.188 (-43%) |
| People F1 | **0.743** | 0.701 | 0.582 |
| Events F1 | **0.217** | 0.134 | 0.101 |
| Symptom F1 | 0.222 | 0.111 | **0.200** |
| Anxiety F1 | 0.207 | 0.111 | **0.200** |
| Relationship F1 | 0.244 | 0.133 | **0.222** |
| Functioning F1 | 0.244 | 0.133 | **0.200** |

**Decision**: Keep gemini-2.0-flash for extraction (small), gemini-2.5-flash for large imports. Use gemini-3-flash-preview only for conversational responses.

**Rationale**: Each successive model generation performed worse on aggregate extraction despite being "better" overall. Prompts and few-shot examples were tuned for gemini-2.0-flash behavior. Newer models respond differently to the same prompt structure. SARF variables showed slight improvement on 3-flash but not enough to offset the people/events regression.

**Lesson**: Model upgrades don't automatically improve extraction when prompts were tuned for a specific model. Moving extraction to a newer model requires prompt re-tuning via the induction workflow.

### Feb 2026: gemini-2.0-flash server-side regression and model migration

**Context**: Aggregate F1 dropped from 0.327 to ~0.257 with no code changes. Investigation confirmed: no GT data changes, no prompt changes, pinning `gemini-2.0-flash-001` produced identical results. Conclusion: server-side model behavior drift, likely related to 2.0-flash deprecation (March 31, 2026).

**Updated results** (45 GT cases, Feb 14 2026):

| Metric | gemini-2.0-flash | gemini-2.5-flash | gemini-3-flash-preview |
|--------|-----------------|------------------|------------------------|
| Aggregate F1 | **0.257** | 0.249 | 0.180 |
| People F1 | **0.718** | 0.718 | 0.582 |
| Events F1 | **0.179** | 0.154 | 0.081 |
| Symptom F1 | 0.200 | **0.205** | 0.178 |
| Anxiety F1 | 0.200 | **0.205** | 0.178 |
| Relationship F1 | 0.233 | **0.250** | 0.200 |
| Functioning F1 | 0.222 | **0.227** | 0.178 |

**Decision**: Switch all extraction to gemini-2.5-flash. The 3% aggregate gap vs 2.0-flash is within noise, SARF variable scores are better, and 2.0-flash is being deprecated.

**Config notes**: `thinking_config=ThinkingConfig(thinking_budget=1024)` enables thinking for quality (see T7-20 decision below). `max_output_tokens=65536` is within 2.5-flash limits.

### Feb 2026: Multi-turn prompt format evaluation

**Context**: Tested converting flat prompt (conversation history concatenated into system prompt) to Gemini's native multi-turn content structure, where prior conversation turns are passed as structured `(role, text)` tuples.

**Results** (gemini-2.5-flash, 45 GT cases):

| Metric | Flat prompt | Multi-turn | Delta |
|--------|------------|------------|-------|
| Aggregate F1 | **0.249** | 0.198 | -20% |
| People F1 | **0.718** | 0.680 | -5% |
| Events F1 | **0.154** | 0.133 | -14% |

**Decision**: Keep flat prompt format. Multi-turn causes 20% aggregate regression, more ID collision warnings, and worse people/events extraction. The model loses context about existing diagram_data when conversation history is separated from extraction instructions.

**Lesson**: Structured multi-turn is not automatically better for extraction tasks. The flat prompt keeps all context (instructions, examples, existing data, conversation, new statement) together, which helps the model track IDs and avoid re-extraction.

### Mar 2026: 2-pass split extraction (T7-18)

**Context**: Single-prompt `extract_full()` struggled with Events F1 (~0.47 with description-free matching). Hypothesis: splitting extraction into two focused passes would improve quality by reducing cognitive load per LLM call.

**Architecture**:
- **Pass 1**: Extract people, PairBonds, and structural events (birth, death, married, etc.) from full transcript
- **Pass 2**: Given Pass 1 output, extract shift events with SARF variable coding

Both passes route through `_extract_and_validate()` for retry/validation. Pass 2 receives `base_pdp=pass1_pdp` so validation runs against Pass 1's people/events.

**Results** (gemini-2.5-flash, 6 GT discussions, avg 2 runs):

| Metric | Baseline (single-prompt) | Split (2-pass) | Delta |
|--------|-------------------------|----------------|-------|
| Aggregate F1 | 0.595 | **0.669** | +12% |
| People F1 | 0.901 | 0.909 | +1% |
| Events F1 | 0.470 | **0.509** | +8% |
| PairBonds F1 | 0.539 | **0.832** | +54% |
| Completion | 4/6 (67%) | **6/6 (100%)** | fixed |

**Decision**: Replaced single-prompt `extract_full()` with 2-pass. Removed `DATA_FULL_EXTRACTION_CONTEXT`. The old single-prompt path no longer exists.

**Key observations**:
- PairBonds F1 improved dramatically (+54%) — Pass 1's focused scope catches bonds that were missed in the single all-at-once prompt
- 100% discussion completion vs 67% — smaller per-pass output avoids token limit failures
- Per-statement prompt constants (`DATA_EXTRACTION_PROMPT`, `DATA_EXTRACTION_EXAMPLES`, etc.) are NOT used by `extract_full()` — the split prompts are independent

**Lesson**: Task decomposition works. Splitting a complex extraction into two focused passes reduces cognitive load and improves quality on every metric. The key insight from the earlier 9-iteration experiment ("per-statement training dominates full-extraction context") motivated this split — instead of fighting the single-prompt format, we redesigned the pipeline.

### Mar 2026: thinking_budget=1024 + flash-lite model evaluation (T7-20)

**Context**: T7-20 (issue #59) was blocked by HTTP 500 errors from gemini-3.1-flash-lite-preview. After T7-18 split extraction landed, re-evaluated flash-lite viability. Discovered thinking_budget=0 was a critical quality bottleneck for both models.

**Experiments**: 14 runs across 12 configurations testing model (2.5-flash vs flash-lite), thinking budget (0/512/1024/2048/4096), temperature (0.0/0.1), and hybrid per-pass model selection. Multi-run averaging on key configs.

**Results** (multi-run averages, 6 GT discussions):

| Config | Events F1 | Aggregate F1 | Time | Cost |
|--------|-----------|-------------|------|------|
| 2.5-flash think=0 (was prod) | 0.265 | 0.545 | 62s | 1x |
| 2.5-flash think=1024 | **0.378** | **0.609** | 51s | 1x |
| flash-lite think=0 | 0.154 | 0.589 | 101s | 0.17x |
| flash-lite think=1024 | **0.368** | **0.600** | 50s | 0.17x |

**Decision**: Deploy thinking_budget=1024 immediately (one-line change). Switch to flash-lite when ready to optimize cost.

**CORRECTION**: Previous finding (Feb 2026) that "thinking+structured_output is catastrophic" is no longer true with the 2-pass split architecture. All 14 runs used thinking=1024 with structured JSON output — zero hangs, ~8s per pass.

**Thinking budget sweet spot** (flash-lite, Events F1): 0→0.154, 512→0.295, **1024→0.368**, 2048→0.298, 4096→0.355. Clear bell curve.

**What failed**: Hybrid models (flash-lite P1, 2.5-flash P2) don't beat homogeneous flash-lite+think. Temperature 0.0 vs 0.1 is noise. Thinking > 1024 causes over-reasoning.

**Report**: `fdserver/training/induction-reports/2026-03-04_13-15-00--model-evaluation-flash-lite/`

### Mar 2026: Description-free event matching (Strategy B)

**Context**: Debug analysis of FP events in split extraction revealed many were semantically valid extractions that GT describes differently. `Event.description` is free-text prose — it varies widely between AI and human annotators. Fuzzy string matching at 0.4 threshold was a hard gate rejecting legitimate matches.

**Change**: Removed `description` as both hard gate and soft scoring signal from `match_events()` in `f1_metrics.py`. Events now match on `kind + dateTime + person links` only. Weighted score simplified to `date_sim`.

**Results** (same extraction output, different matching):

| Metric | With description matching | Without (Strategy B) | Delta |
|--------|--------------------------|---------------------|-------|
| Events F1 | 0.335 | **0.470** | +40% |

**Decision**: Adopted. Description matching was measuring "do AI and GT use similar words" not "did AI find the right event."

**Risk**: If a person has 2+ genuinely different shift events within the 730-day date tolerance, they'll match incorrectly. Accepted as rare in practice with current GT dataset.

**Alternatives considered but deferred**:
- **SARF Signature Match** — match on SARF variable agreement instead of description. More precise than kind+date+person but adds complexity and creates circular dependency (SARF accuracy used for both matching and scoring).
- **SARF + Description hybrid** — demote description to low-weight tiebreaker. Most complex, still affected by paraphrasing variance.

### Mar 2026: Drop SARF operational definitions from Pass 3 review prompt

**Context**: Commit `fb1b603d` (fdserver) added `all_condensed_definitions()` (~62,886 chars / ~15,700 tokens) to the Pass 3 SARF review prompt. This comprised 98% of the prompt. A/B testing (3 runs each) showed marginal benefit: Aggregate F1 +0.006, SARF macro F1 +0.016 mean. This echoes the Dec 2024 lesson where exhaustive definitions degraded F1.

**Change**: Replaced the definitions-heavy prompt with a compact inline-rules version (~30 lines). Removed `all_condensed_definitions()` call from `pdp.py`, removed import of `sarfdefinitions` from `pdp.py`. Updated both `btcopilot/prompts.py` and `fdserver/prompts/private_prompts.py`.

**Results** (3-run A/B mean, gemini-3-flash-preview, 6 discussions):

| Metric | With definitions | Without | Delta |
|--------|-----------------|---------|-------|
| Aggregate F1 | 0.647 | 0.641 | -0.006 |
| SARF macro F1 | 0.489 | 0.473 | -0.016 |
| Pass 3 prompt size | ~64K chars | ~1.5K chars | -98% |

**Decision**: Dropped. Cost/benefit strongly favors removal: ~15,700 fewer input tokens per extraction for negligible F1 difference within run-to-run variance. Reduces complexity and cost.

**Note**: `sarfdefinitions.py` and `all_condensed_definitions()` remain available — they are used independently by IRR calibration (Components A/B) via `calibrationprompts.py`.

### Mar 2026: Multi-model conversation prompt architecture

**Context**: After switching chat responses from Gemini Flash to Claude Opus 4.6, output degraded to terse single-line questions. The monolithic `CONVERSATION_FLOW_PROMPT` was tuned for Gemini's natural verbosity — its brevity constraints ("Keep responses brief", "One question per turn") are counterproductive for Opus, which is already terse by nature.

**Architecture change**: Split `CONVERSATION_FLOW_PROMPT` into:
- `_CONVERSATION_FLOW_CORE` — shared domain knowledge, phases, data checklist (btcopilot, open)
- `_CONVERSATION_FLOW_OPUS` — response style tuned for Claude Opus (fdserver, private IP)
- `_CONVERSATION_FLOW_GEMINI` — response style preserving existing Gemini behavior (btcopilot, open)

`get_conversation_flow_prompt(model)` assembles core + appropriate addendum at runtime. Override mechanism uses `hasattr` so fdserver only defines pieces it wants to override.

**Opus addendum design**: Combines stronger persona framing ("experienced consultant fascinated by family patterns") with response type rotation guidance (question/observation/bridging/normalizing turns), length calibration (2-4 sentences), and concrete good/bad response examples. The few-shot examples are the most reliable prompt intervention per prior extraction prompt findings.

**IP migration**: Tuned prompt content moved from btcopilot to fdserver. btcopilot retains only architectural stubs.

**Key insight**: Gemini and Opus have opposite natural tendencies. Constraints that guard Gemini from verbosity cause Opus to produce one-liners. Per-model addenda resolve this without compromising either model.

**Status**: Initial architecture deployed. No conversational quality metrics exist yet — next step is building a rubric-based evaluation framework to baseline and iterate the Opus addendum. See plan at `btcopilot/plans/opus-conversational-prompts.md`.

### May 2026: PASS1_CONTEXT committed-data carve-out (FD-319 prompt idempotency)

**Context**: FD-319 shipped a deterministic repair (`fix_committed_person_duplicates`)
as a safety net. Remaining ticket scope: measure the raw-LLM committed-duplicate rate
and test whether a prompt change reduces how often the repair must fire.

**Measurement** (PRODUCTION prompts, repair bypassed, Pass-1 only, N=10 ×
{gemini-3-flash-preview, gemini-3-pro-preview}):

| scenario | flash baseline | pro baseline |
|---|---|---|
| simple_people / simple_marriage | 0/10 | 0/10 |
| complex (15-person re-narration) | **10/10** (exactly 2 dup pair_bonds/run) | 1/10 |

Strategy doc §2b's 2026-03-05 "Resolved" claim was falsified at scale: the prior
prompt fix eliminated people/marriage re-emission but not committed **pair-bond**
re-emission by flash on a large committed state. The ticket's N=1 "people+marriage"
observation was a default-prompt artifact (`FDSERVER_PROMPTS_PATH` unset everywhere).

**Change**: one additive edit to `DATA_EXTRACTION_PASS1_CONTEXT` in
`fdserver/prompts/private_prompts.py`. The proximal directive
`EXTRACT: ... all pair bonds between couples/parents ...` had no committed
carve-out and beat the upstream "COMMITTED DATA — REFERENCE, DON'T RECREATE"
section + Example 6. Qualified to `All NEW ...` + an adjacent pair-bond-specific
`⚠️ ALREADY-COMMITTED ITEMS` block with a pre-return self-check. No working
content removed.

**Results**: raw committed-dup rate → 0/10 across all cells/models (flash/complex
1.00→0.00, pro/complex 0.10→0.00; simple cells unchanged at 0.00). F1 gate
(gemini-3-flash, 6 GT, avg 2 runs): people 0.925→0.919, events 0.474→0.518,
pair_bonds 0.820→0.845, aggregate 0.671→0.687 — all within run-to-run variance.

**Decision**: SHIP (pending Patrick commit of fdserver). F1 claim bounded to
"no regression" (N=2; documented 10-15% events stochasticity). Deterministic
repair stays load-bearing — the prompt reduces repair firing frequency, it does
not make the repair redundant (no idempotency guarantee at temperature 0.1 on
unseen inputs).

**Alternatives considered**: (a) prompt-only, drop the repair — rejected: stochastic,
no guarantee, prior "Resolved" already failed this way; (b) repair-only, no prompt
change — rejected: leaves flash at 100% raw dup on large states, repair load
unbounded; (c) enumerate committed IDs into PASS1_CONTEXT via a new format
placeholder — deferred: requires a `pdp.py` signature change, not needed since the
salience edit alone reached 0/10.

**Report**: `fdserver/training/induction-reports/2026-05-16_08-40-13--fd319-prompt-idempotency/`.
**Follow-up (non-blocking)**: 3-run F1 confirmation folded into next routine F1 run.

### May 2026: Structural-completion pass — rejected (negative result)

**Hypothesis**: a dedicated post-Pass-1 LLM pass to recover missing parent/child
and couple links would fix structural under-extraction.

**Measurement infra added (kept)**: isolated parent/child (`child_of`) recall/F1
metric in `f1_metrics.match_child_of`, surfaced in `run_extract_full_f1` and the
training F1 dashboard (also charted Pair Bonds, previously tracked but unplotted).
This metric stays regardless of the pass outcome.

**A/B (6 GT discussions, 2 runs, structural pass ON vs OFF)**:
parent/child recall 0.872→0.882 (+0.01, inside noise — this metric ranges
0.4–1.0 run-to-run); aggregate 0.690→0.670; events 0.517→0.480; pair-bonds
−0.01; people flat.

**Decision: rejected, reverted.** No recall signal above noise; net negative on
aggregate/events; adds an LLM pass + latency. Logged in strategy doc "things
that failed" #18.

**Reframe**: structural under-extraction is scenario-specific. Fresh single-shot
extraction already reaches ~0.87 parent/child recall. The low ~0.63 is specific
to re-extraction with committed context — and the cursor/windowing experiment
already lifts that (0.63→0.73). The cursor architecture is the lever for both
re-extraction idempotency and the re-extraction structural-recall gap; a separate
completion pass is not warranted.

### May 2026: Re-extraction cursor rule (FD-319) — kept

Prompt change: a cursor rule appended to Pass 1 when a discussion has an
accepted re-extraction cursor; the full conversation is context but only
content after a nonced marker is emitted. Measured (re-extraction scenario, 6
GT, 2 runs): committed-event re-emission ~⅓ down, parent/child recall
0.63→0.73, no F1 regression. Standard fresh-extraction F1 unchanged (cursor
inactive without an accepted cursor), so no f1_timeseries entry. Deterministic
committed-duplicate guard stays load-bearing — the rule reduces how often it
fires, it is not the safety mechanism. Marker is a per-call random nonce so
user text cannot forge the boundary. Concurrency defects found in adversarial
review (concurrent extract / diagram-blob clobber) are deferred to a separate
FD-264 child, not fixed here. Report:
`fdserver/training/induction-reports/2026-05-16_19-50-22--fd319-cursor-windowing/`.

### September 2026: Clinical definitions into the coach's agent loop (FD-362, R-0236)

**Change**: the chat coach's per-turn system prompt gained a section, "What goes
in the record", carrying the Pass 1 and Pass 2 clinical contract rewritten for a
writer that edits a record it can see rather than a batch extractor reading a
transcript. Every rule, distinction and definition is preserved: people and name
fidelity, deduplication, pair bonds and the parents link, the eight
self-describing event kinds and their required person/spouse/child links, ages
as births, the never-null date and the certainty scale, the four-question test
for a shift, the do-not-create and do-create lists, saturation and the
one-event-per-pattern rule, the four variables with their coding direction, the
twelve relationship moves, the required targets and triangles, and the four
distinctions the old Pass 3 review existed to fix (projection over
overfunctioning, triangle-inside over conflict, distance over anxiety or
functioning, overfunctioning over functioning down). Section is ~9.5k
characters; the assembled agent prompt is ~29k.

**Dropped, and why**: the negative/positive ID assignment scheme, the
committed-data reference rules and the re-extraction cursor, the JSON output
format and array shapes, the per-pass "do not extract the other pass's items"
fences, the 8–15 events per discussion calibration, and the Pass 3 "return the
corrected version" framing. All of those exist only because a batch pass emits a
delta against a state it cannot address. The agent addresses the record
directly, so they were replaced with the loop's own mechanics: the record is in
front of you, add what is new, change what is wrong, leave what is right, and
read before adding when unsure. Four of the worked examples were kept, rewritten
as "they say X, you call edit_event with these fields" so the tool call is the
example.

**Also**: every edit_event parameter now carries its meaning from the same
passes — kind, the four variables with their coding rule, the relationship moves
and what each aims at, targets and triangles and when they are required, date
certainty, and who links where by kind. JSON schema shape unchanged; the
edit_event definition is ~4.3k characters.

**Measurement**: none. There is no F1 for the agent write path — the extraction
harness scores the two batch passes, not tool calls made mid-conversation. An
agent-path harness is being built separately; until it exists this change is
unmeasured and the claim is confined to "the definitions are now present in the
loop". The 26 agent tests pass, which proves assembly and schema validity only.


### September 2026: Prompts move to files, encrypted in place (FD-362)

**Change**: every prompt leaves the Python constants and becomes one `.prompty`
file per prompt with shared Jinja2 fragments, encrypted in place with sops so
the public repo holds only ciphertext. The stock renderer holds only the
prompt itself, so a subclass with a file loader resolves fragments and a
missing fragment raises rather than rendering empty. [R-0305, R-0314]

### September 2026: A prompt is read when it is asked for

**Change**: a prompt is read when it is asked for, not when a module is
imported, so a checkout with no key can still run the tests that do not need
one.

### September 2026: The scribe reasons about who a sentence names

**Change**: the scribe's prompt learned that a sentence naming two people is
about both of them, and refuses a pair-bond that cannot exist rather than
guessing; a missing parent is named.

### September 2026: The scribe keeps a date at the precision it was given

**Change**: the scribe keeps a date at the precision the coder gave it, so a
year given as a year reads back as the year alone.

### September 2026: The coach asks who you are before anything else

**Change**: the coach's prompt carries which of first name, last name and birth
date are still missing from the record, and asks for them before it goes on with
anything else. Without a birth date it has no anchor for an age, so "twenty-five
or twenty-six" became a year it invented. The account row mirrors the three
values for the preferences page. [R-0360]

### September 2026: The coach no longer offers answers to tap

**Change**: the coach is no longer told to end a reply with bracketed answers the
reader can tap, and any it still writes is stripped before the transcript is
stored. Its closing question keeps its own amber line. The public prompt goldens
were re-captured after the change. [R-0358, R-0361]

### September 2026: The private tool meanings must cover every required parameter

**Change**: the private text that gives each tool parameter its meaning was
missing three entries the tools now require — parents, person_a and person_b —
while the public default happened to carry them, so every test passed and only the
box failed. The private text is now the one that must be complete; the public
default is not a fallback for it.

### September 2026: The extraction pipeline and the pending data pool are retired (R-0414)

**Change**: on 2026-09-23 the extraction pipeline (the passes that read a whole
conversation and proposed a pool of pending people, events and pair-bonds for the
user to accept) and the pending data pool itself were removed. The coach now edits
the record turn by turn with its tools, and every entry above that describes
extraction prompts, passes or F1 on extraction is history. The undated sections
that described that pipeline as the current design (model selection, Gemini issues,
prompt architecture, what to include in extraction prompts, monitoring, related
files) were removed with it. The pipeline's code was last present in a7eeb2c.

### September 2026: The coach keeps the family's open questions (FD-363)

**Change**: the agent prompt gains one paragraph, a fragment shared with a new
backfill prompt, on keeping open questions in the record. Two kinds: food for
thought, sourced to Kerr's "people usually require questions to stimulate their
thinking" (Family Evaluation, ch. 10), and facts to find, kept only when the
coach judges them relevant to the evaluation or the family's historical context,
with inclusion as the default when in doubt and nothing kept that would spend the
person's time, attention and motivation for nothing. It names the three question
tools, the map's QUESTIONS section, and never asking again a question the person
declined. It is worded as judgement, not rules. The backfill prompt goes once over
a past session and adds the questions worth keeping with the message they were
asked in. The private fragment sits after the record contract so it stays in the
cached head. Public and private goldens were re-captured. [R-0482, R-0485]

### September 2026: The question wording checks the record first and keeps one question per unknown (FD-363)

**Change**: a backfill run on a copy of production kept 23 questions from about 33
replies for one family. At least 7 were already answered in the record, 3 asked
about one person's parents, and 3 of the 9 food-for-thought questions were facts.
The shared paragraph now says: food for thought asks the person to think, and a
question answered by a name, date, place or number is a fact; look first, and never
keep a question the record already answers; keep one question per thing to find
out, in the best-worded version; weigh every question for the person's time before
keeping it, with inclusion still the default when in doubt. The backfill prompt
says the map is drawn after every later session, so it often holds the answer.
Not yet measured: the model account was out of credit. [R-0482, R-0485]

### September 2026: A kept question reads on its own, and anything with a factual answer is a fact (FD-363)

**Change**: stored questions read in the Questions tab away from the conversation,
and real runs kept fragments such as "And how old are they now?". The coach now
words a question it keeps so it names the person and the subject ("How old is
Elizabeth's brother now?") and stores it in those words; the backfill may reword a
question that leans on its context, changing nothing else about what it asks. A
live turn filed an intake question as food for thought, so food for thought is now
a thinking question about patterns or meaning, and anything with a factual answer,
including the basics of who is in the family, is a fact to find. Not yet measured
live. [R-0482, R-0485]

### September 2026: A kept question says "you", and asking a question is keeping it (FD-363)

**Change**: real turns stored questions that named the user in the third person
("When [user] and [husband] go quiet…") while the reply said "you", and 3 of 5
turns that asked a question stored nothing. The shared paragraph now says a kept
question speaks to the person as "you" and names everyone else, and that asking
and keeping are one act: a question put to the person is stored the same turn,
asked, in the reply's words, unless it does not matter at all; one meant for later
is stored held. The backfill keeps the "you" of the message. Not yet measured
live. [R-0482, R-0485]

### September 2026: A kept question is the question alone (FD-363)

**Change**: a stored question carried the reply's lead-in ("Before we go further,
what's your last name…") into the Questions tab. The shared paragraph and the
backfill now say the reply may frame a question however it likes, but what is kept
is the question alone, with no lead-in, hedge or reason, still in "you" wording and
readable on its own. Not yet measured live. [R-0482, R-0485]

### September 2026: Keep the question first, then write the reply that asks it (FD-363)

**Change**: in 3 of 75 live turns the coach wrote its closing question as text
beside an add_question call; that text was cleared as working notes and the turn
ended with no words. The shared paragraph now says to call add_question on its
own, then write the reply once the call comes back, so the reply is the last
round's words, and that words beside a tool call never reach the person. Not yet
measured live. [R-0482]

### September 2026: Every date says how sure it is (FD-363)

**Change**: the coach is told to give date_certainty (certain, approximate or
unknown for a guess) whenever it adds an event or changes its date, public and
private wording alike; the toolbox now refuses a date without it. Not yet measured
live. [R-0482]

### September 2026: The review scribe gives every date its certainty too (FD-363)

**Change**: the scribe calls the same event tool, which now refuses a date without
certainty, so its prompt, public and private, says to give date_certainty whenever
it adds an event or changes a date. Not yet measured live. [R-0482]

### September 2026: A date's certainty follows what was said about the day (FD-363)

**Change**: "My dad died in June 1998" was stored as certain, but certain means
within a week. The agent, scribe and onboarding wording now map it plainly:
certain for an exact day, approximate for a month or a year only, unknown for
"sometime around" or any hedge, or for the coach's own guess. The private record
contract's "March 2019 is certain" is reversed to approximate. A live case checks
the June 1998 death is stored approximate. [R-0482]

### September 2026: The record moves out of the system prompt and into the user turn, to cut prompt-cache cost (FD-363-cost)

**Scope**: coach prompt assembly on branch FD-363-cost (draft PR #141), off FD-363 — the record
block, the date and the "looked at" block. Not a wording change; a structural change to where
these three pieces sit in a turn.

**Change**: a heavy production day put 78% of that day's model cost in prompt-cache writes,
because these three pieces sat in the system prompt ahead of the chat and changed every turn, so
the whole cached chat was rewritten each turn. The system prompt now holds only the coaching
text; the record block moves into the new user message after the chat; the chat is marked at the
previous two turn boundaries; tool marks are capped at four; cache life stays 5 minutes [R-0595].

**Measured**: on the sandbox, with a 12,000-token chat, turns 2 and 3 cost 42% less ($0.2472 to
$0.1428). Real model calls spent proving this: $1.96.

**Not yet measured**: whether moving about 14,000 characters of prompt out of the system prompt
and into the user turn changes the coach's behaviour. The coaching text now sits further from
the record it reasons about, in the prompt's own order, than before; whether that changes what
the coach asks or notices needs the live eval suite run against it, which awaits Patrick's spend
approval. Until that runs, this change is deployed on cost grounds alone, not proven neutral on
behaviour.

### September 2026: The coach raises impressions and keeps them (FD-363)

**Change**: a new paragraph, shared by the agent prompt and a new impression
backfill prompt, public and private. An impression is the coach's inference, a
pattern across chapters or a reading of a stretch of years. It is raised with its
tool, with the evidence it rests on, before the reply says it in the same words.
A stretch of years where a lot was happening becomes a cluster made or extended
with that reason, not only words. Anxiety, symptom and functioning shifts are
remembered episodes each reported on its own, never a series or a trend. An
impression the user said doesn't fit is not raised again in those words; one
they said fits partly is revised or let go. Not yet measured live: model calls
are unavailable. [R-0482, R-0485]

### September 2026: Tool text stated once (FD-366)

**Change**: what each event field means is now written only on the coach's
edit_event fields; the record rules in the private coach prompt point there and
keep the theory, the worked examples, the provisional rules and the rulings.
Defined-self is one sentence, on the relationship field, in the theory corpus's
wording: the action a person takes to define themselves in relation to others.
read_notes is gone: read_events takes a list of extra fields (the user's words,
the notes, the location), and the rule to read the notes before adding to them
moved to edit_event's notes field. edit_event can empty a field with a list of
fields to clear, and its text names three rules the record enforces: only a shift
carries a variable or a move, a shift says in words what happened, and no one is
both a target and a third person. Not yet measured live: no model calls were made.
[R-0446, R-0480, R-0533]

### September 2026: The coach thinks at low effort (FD-366)

**Change** (2026-09-30): the coach's thinking effort is low, down from medium. The replay's thinking option still overrides it.
**Measured** on eight of Patrick's turns, one pass each: low cost $0.051 a turn against $0.071 at medium (28% cheaper). Events scored higher at low (0.75 against 0.55). The four variables scored lower at low (0.49 against 0.60).
**Decision**: Patrick chose low and queued the question of giving the variables more thinking (open question 40 in the theory corpus).

### October 2026: Sitting titles and summaries run on Gemini Flash Lite (FD-366)

**Change** (2026-10-01): the title and the summary of a sitting are written by Gemini Flash Lite (`gemini-3.1-flash-lite`, the model the cluster regrouping uses), down from the response model, Opus 5.5. A model change only: the prompt wording is unchanged, the ledger purpose is still Summary, and the row's model column holds the model that answered. Thinking is off for these two calls.
**Decision**: Patrick, 2026-10-01: "yes gemini flash is good for that". Not yet measured live: no model calls were made.

### October 2026: The chip label limit was already in the coach's prompt (FD-368)

**Change** (2026-10-01): none in the end. The sentence "Every label is at most 28 characters — a noun phrase, not a clause." was first added to the private coach reference fragment, then taken out the same day: no prompt the coach is sent includes that fragment, and the coach's own prompt already says the limit in its paragraph on pointing at the record, with an example and the warning that a label that does not fit is sent back.
**Reason**: a 29-character label failed a turn on 2026-10-01. The queued R-0654 replaces R-0169: a labels-only retry, then a cut at a word boundary.
**Modelled cost**: nothing; the coach's prompt is unchanged.
**Decision**: Patrick, 2026-10-01.

### October 2026: Every observation the coach offers is raised as an impression (FD-367)

**Change** (2026-10-04): the impressions paragraph now counts a connection noticed between two things the person told (a death and a first grandchild in the same year) as an impression, asked for or not, to be raised before it is said; the private reply-style section's observation turns say the same.
**Reason**: on production one account had 110 coach turns over two days with many replies connecting two events and not one `add_impression` call, so no impression was stored and the case report's guess cards stayed empty. The prompt taught observation turns as plain talk and defined an impression only as a pattern across chapters of a life or a reading of years.
**Measured** on the subscription ($0), the new live case where the person tells a birth in the same year as a death already in the record and asks nothing: 1 of 3 runs raised an impression on the old prompt, 3 of 3 on the new. The other impression and case report cases pass as before; the literature case was 2 of 3 on both prompts.
[R-0504]

**Follow-up** (2026-10-04): the failing literature runs refused in words ("I won't speak for any book", "I can't tell you what the books say"), which still names them. The paragraph now gives those two as bad examples and a good opening that starts straight from the person's story. Measured on the subscription: every impression and case report case passes, the literature case 3 of 3. Public and private prompt goldens re-captured. [R-0688]

### October 2026: The times the most was going on are asked on a thread that never asked (FD-371)

**Change** (2026-10-05): the fidelity paragraph on the times the most was going on now also says that where what brings the person and when it began are already in the record from an earlier sitting and the question was never kept, the coach's next reply asks it, ahead of any other question, whatever the person just said. The set wording, its storing as a fact question naming the item, and the follow-ups are unchanged; public and private copies carry the same paragraph.
**Reason**: after the 2026-10-05 deploy Patrick's own thread had four coach turns with no such question, though the coverage list showed the item first among unknowns. The paragraph fired only in the reply right after the person says when the trouble began, which on his thread was weeks earlier.
**Measured** on the subscription ($0), the new live case (a dated problem said in two earlier sittings, a new sitting opening on a birthday gift): 0 of 3 on the old prompt, 3 of 3 on the new. The live case's earlier sittings now mark the coach's lines as the coach's, so the history reads as a chat. Public and private prompt goldens re-captured.
[R-0762]

### October 2026: Stories left untold are kept, and a waiting question comes first at an opening (FD-371)

**Change** (2026-10-05): the open questions fragment gains two paragraphs, in the public and private copies alike. A story (an event, a symptom episode or a named conflict with more behind it) that the talk moves away from before it is told is kept in that turn as a held question naming it in the person's terms. At a natural opening (a finished point, a short or flat answer, or "what next"), a waiting question, held or asked and never answered, comes before any new basic-data question; the question about the times the most was going on keeps its place ahead of this. The sentence under the still-unknown list now sends the coach to the map's questions first and asks a list item only when none is waiting. A held question is asked by marking it asked, never by a second add; an asked one is asked again with no call. The map now shows the day each asked question was asked, and the two refusals a return used to hit (the same words kept twice, and marking an asked question asked again) now say how to come back to it instead.
**Reason**: on production, 5 of the coach's 198 questions were kept for later, 13 of 15 stories the talk moved away from left no question, and on one long thread 3 to 5 asked-but-unanswered questions waited at each of 50 replies, 33 of them at a natural opening, while one reply used a waiting question.
**Measured** on the subscription ($0): the storing case 0 of 3 on the old prompt (1 of 3 on an earlier sample), 3 of 3 on the new; the returning case 0 of 3 on the old prompt, and 3 of 3 then 2 of 3 on two samples of the new, so it is not yet a steady 3 of 3. Its miss asks the father's age or a move instead of the waiting question. With the rule only in the questions fragment it was 1 and 2 of 3: the sentence under the still-unknown list kept winning until it named the waiting questions itself. A further sentence on short or flat answers did not help (2 of 3) and was dropped. Whole live suite on the final text: 30 pass, 3 short. Besides the returning case, the cannot-have-children case went 2 of 3: its miss asks what happened between the couple after they learned they could not have children, a waiting story, which that case's word check counts as asking about children. The event-said-again case failed its one run on a shift title refusal, outside this change. Public and private prompt goldens re-captured.
[R-0770, R-0771]

### October 2026: The two or three times question keeps its place ahead of waiting questions, and the live checks are tightened (FD-371)

**Change** (2026-10-05): the sentence under the still-unknown list, which sends the coach to a waiting question instead of a list item, now also says the question about the two or three times the most was going on keeps its place ahead of any waiting question, as the open questions fragment already said. Public and private copies carry the same sentence; both prompt goldens re-captured.
**Reason**: an independent check found the sentence left out the fragment's order, and found five live checks that let wrong replies through. The checks now sit in plain functions proven on made-up replies with no model: a children question counts whether the couple have, had, want or plan children, but not a question about what followed learning they could not; the father question catches "he" and "your parents"; the waiting case passes only when every question the reply asks is the waiting one; the two or three times case passes only when that question comes first; and in the event-said-again case a second death row, or anything written down other than a refused shift title the coach then fixed, fails the case on any run, so the 2 of 3 tolerates only the title retry.
**Measured** on the subscription ($0): whole live suite on the new text with the new checks, 33 of 33 pass, as before the change.
[R-0760, R-0762, R-0771, R-0442]

### October 2026: A waiting question passed over twice is left alone (FD-371)

**Change** (2026-10-05): the open questions fragment, public and private alike, now has the coach mark an asked question asked again with `set_question` when it comes back to it, instead of asking with no call. After the person has passed over it twice, the coach leaves it alone unless they return to its topic, and then names their message with `raised_in`. A waiting question is now one the person has not passed over twice. The tool keeps each repeat day in the question's `asked_again_on`, refuses a third repeat ask without `raised_in`, and the map marks such a question as not waiting; it stays open and listed on the page. Both prompt goldens re-captured; the question backfill prompt shares the fragment.
**Reason**: per R-0774. Until now a repeat ask left no trace, so the times a question was passed over could not be counted.
**Measured** on the subscription ($0), the new live case (a question about the mother's father's drinking asked and passed over twice, then the person asks what to talk about next): 0 of 3 on the old code, where the coach closed the question each time instead of leaving it open, and 3 of 3 on the new. Whole live suite on the new text: 34 of 34 pass.
[R-0774]

### October 2026: The sentence under the still-unknown list is shorter (FD-371)

**Change** (2026-10-05): the sentence that sends the coach to a waiting question before a list item was reworded 67 characters shorter, with the same instructions in the same order; public and private copies alike, both prompt goldens re-captured.
**Reason**: that sentence sits after the record, outside the cached part of the prompt, so it is paid for in full on every turn; this week's additions had pushed the fixed text there to 1536 characters, over the 1500 the caching test allows. Now 1469.
**Measured** on the subscription ($0), the four live cases for these rulings on the shorter text: the three 3 of 3 cases pass 3 of 3, the 2 of 3 case passes.
[R-0392, R-0595, R-0762, R-0770, R-0771, R-0774]

### October 2026: The person's own todos are kept and picked up first on a new sitting (FD-372)

**Change** (2026-10-06): a new question kind, "todo", in the record's questions list, stored only when the person says they will find something out or do something themselves, in their words, resting on their message. It is shown on the coach's map line and never on the page, a card or the coverage count. A new block in back.prompty has the coach pick up an open todo first when the person comes back after a sitting's gap. `flask admin questions catch-up` gains a part that keeps the todos the thread has not yet reported done, three at most.
**Reason**: per R-0803.
**Measured** on the subscription ($0): stored in their words 3 of 3; picked up first a day later 3 of 3; closed as answered with the finding recorded when they come back with it, 2 of 3 or better. The pick-up is driven by the map line in code, so the prompt text alone was not proven: the old prompt with the new code also passes. Both prompt goldens re-captured.
[R-0803]

### October 2026: The coach gives the person's dated facts back early, in order of time (FD-372)

**Change** (2026-10-06): the private coaching flow and the narration prompt (public and private copies) gain a sentence: early, once, the coach gives the person's own dated facts back in one sentence, in order of time, with names and years (or their age, or a step from the time before) and no cause word.
**Reason**: per R-0804.
**Measured** on the subscription ($0), the live placing case: old prompt 0 of 3, new prompt 1 of 3 against a bar of 2 of 3, after three passes at the wording and the check. Not met: the replies place two of the three events. The case is marked as a known miss in the live suite. Both prompt goldens re-captured.
[R-0804]

### October 2026: The opening says what this is, and any answered question keeps the person's message (FD-372)

**Change** (2026-10-06): the private opening and the public opening gain a sentence saying what this is; the onboarding rules allow it. `set_question` now stores the person's message as the answer whenever any question closes as answered; before, only case report questions did.
**Reason**: per R-0802 and R-0801.
**Measured** on the subscription ($0): the sentence in reply one and the hope question by reply three, old 0 of 3, new 3 of 3. The second case, the answer stored on close, old 0 of 3, new 3 of 3. Both prompt goldens re-captured.
[R-0802, R-0801]

### October 2026: No ban on early correlations (FD-372)

**Change** (2026-10-06): none. A proposed rule against offering correlations early was withdrawn by Patrick; no prompt changed.
[R-0805]

### October 2026: No zero target for why or feeling questions (FD-372)

**Change** (2026-10-06): none to the prompt. The zero targets for why questions and feeling questions are withdrawn (the 2026-10-06 rulings on why and feeling questions): both are allowed, counted per model and prompt version, and compared with the rates on Murray Bowen's tapes (9 why questions in 329), never gated. The live case that asked for no feeling question is deleted. The flow counts gain how much the person speaks of their own feelings in the reply after a feeling question, against the reply after any other coach message.

- 2026-10-06 (FD-372): no prompt change. The live case "What should I do about my brother Theo? He won't return my calls." is switched on under R-0812 (never give advice) and R-0669: no advice and no teaching in the reply, 3 of 3 on the subscription, $0.
- 2026-10-06 (FD-372): no prompt change. Saved replies of the live cases are a local cache from now on (R-0813): `private/replays/` is git-ignored, the 368 replies this branch had committed are removed from the repo and kept on disk, and replies unused for 14 days are deleted at the start of a run. What is kept from a run is its result (the count per case, prompt version and model), here and in the ledger.
### October 2026: The person's own clusters are shown to the grouping prompt (job 030, second pass)

**Change** (2026-10-08): the grouping prompt, private and public copies alike, gains a section GROUPS THIS PERSON MADE listing each cluster the person made with its name and its first and last date, and the overlap line now names that section as fixed and not to be overlapped. The by-years fallback leaves out the person's own events and cuts a proposal around their clusters, so it never stores a cluster across one. Both prompt goldens re-captured.
**Reason**: per R-0839. Before, the person's own clusters were held out of the prompt, so on the first regroup of a diagram with one the model could not see the years to avoid and spent a refusal on it; and the fallback could store a model cluster straddling the person's.
**Measured**: no live run (no model calls); the no-model tests in `btcopilot/tests/test_clusters.py` check the section is in the prompt and that the fallback cuts around the person's cluster, the second failing on the code before the change.
[R-0839, R-0780]

### October 2026: Two groups never overlap in time (job 030)

**Change** (2026-10-08): one line in the grouping prompt, private and public copies alike: never return two groups whose years overlap, the person's own groups included; the timeline is one line, and a group's years run from its first event to its last. In code, a returned grouping with two overlapping clusters is refused with the two named by their dates and asked again (`overlap`, an observations row), a stored model cluster overlapping another stored cluster is not handed back as existing, the by-years fallback joins overlapping proposals into one (the proposal the model sees is unchanged), and `DETECTION_VERSION` is 7. Both prompt goldens re-captured. doc/CLUSTERS.md carries the check beside the ten-year one.
**Reason**: per R-0839. A real regroup of Patrick's diagram on the production model returned a cluster 2008 to 2011 over the one he made for 2009 to 2011, and 2025 to 2026 inside 2017 to 2026; nothing stopped two clusters' years overlapping on the one timeline.
**Measured**: no live run on this machine (the brief: the coordinator runs the production model's check); the no-model tests in `btcopilot/tests/test_clusters.py` refuse both shapes seen and accept them with the check switched off.
[R-0839, R-0780]

### October 2026: The cluster prompt says what a period is, and a group over ten years is refused (job 025, from job 021's reading of the sources)

**Change** (2026-10-08): the seven lines of the grouping prompt that the books contradict take the wording job 021's detection.md (section 3.4) proposed, in the private prompt and its terms fragment and in the public copy alike: a proposed group comes back as one group unless one recorded shift ties two into one story with nothing settled between, and separate is the ordinary case; the same people alone is never a reason to join; an event months or years later belongs only while nothing in between shows the family settled; a group ends where the record shows the family settled, and is never a stage of the family's life, the ordinary level or a chronic symptom's whole span; a stored group is not protected when it covers most of the record's years; the name says what opened the group and its time; and a quiet span after a run of shifts is read as the family settling, with the caveat that families misremember. Each proposed group is shown with the silence before it ("38 years and 4 months with nothing recorded before this group"). In code, a returned group spanning more than ten years is refused and asked again with the reason (`too_long`, an observations row), a stored group that fails that check is not handed back as existing, and `DETECTION_VERSION` is 6. Both prompt goldens re-captured. doc/CLUSTERS.md carries the definition and the rationale for the number.
**Reason**: per R-0836, R-0837 and R-0838. On production the grouping model folded three runs of events decades apart into one group of fifty years on the strength of a shared grandparent, and "keep what is there" then handed it back on every rerun.
**Measured** on this machine's Claude Code (AWS Bedrock; the app's own grouping model, Gemini, has no key here), the fictional Hale record in `btcopilot/tests/live/test_clusters.py`, 8 of 10 stated. Sonnet 5 (`us.anthropic.claude-sonnet-5`, about $0.90 per ten-run pass): old prompt and code 5 of 10, every miss the 1948 marriage joined to the 1954 run on the strength of the same couple, six quiet years before the first shift; new prompt and code 10 of 10, the marriage left out every run, and the stored fifty-year group redone as three on its one run. Opus 5 (`us.anthropic.claude-opus-5`, $0.64): old 9 of 10 (the one miss the same join), new 10 of 10. Neither model reproduced the production fold of three runs into one fifty-year group on the old prompt; the proof that the ceiling refuses it is the no-model pair in `btcopilot/tests/test_clusters.py`, where the merged answer is accepted with the ceiling lifted and refused with it in place. On the stored variant the old code let the model reshape the fifty-year group into three with change sentences on both models; the new code never offers it. A run on the production model is owed before the pass rate is trusted.
[R-0836, R-0837, R-0838, R-0780]

- 2026-10-07 (FD-372): the back block and the open-questions fragment (public and private) no longer put the person's todo first when they come back (R-0815, R-0803): with something new, the coach follows it; with nothing, it offers the todo once as one of two doors; not taken up, it is let go. Live cases on the subscription, $0: back with nothing, the todo offered with another door, 0 of 3 on the old prompt, 3 of 3 on the new; back with news of a call, the reply not led by the todo and engaging the call, 0 of 3 old, 3 of 3 new; back with the answer, recorded and closed, passes on the new. Both prompt goldens re-captured.
- 2026-10-08 (worker job 027, the couple card): the case report paragraph of the impressions fragment (public and private alike) gains one sentence on what to ask when the diagram holds little about the person's own marriage, the smallest set of the questions job 023 drew from Kerr and Bowen: the floor first (when they married, where each stands among their brothers and sisters, the children in order), then the first year or two of the marriage for each of them, then around each birth how each was doing and where they lived, then after a death or serious illness in either family what changed in their house over the two years after; in Kerr's order, one or two a turn, as openings come. The couple card itself now says what it still needs of that floor [R-0835]. No live eval ran: this machine has no model key and no Ollama; the sentence is to be proven on a logged thin-diagram case before it is counted as working. Both prompt goldens re-captured.
[R-0833, R-0834, R-0835]
