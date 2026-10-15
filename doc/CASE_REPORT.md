# Case report

The case report is the page the app writes about one person's family from their diagram and
their conversations with the coach: ten cards, from who has the trouble to what the person is
doing about it. Every card is rewritten from all the data on each refresh. It presents the bare
facts in a way everyone can agree with, and every reading on it is a hypothesis the data may
disprove. Sources for the cards and the rules: btcopilot-sources
`research/case-report-cards/cards.md` and `research/clusters/rules-2026-10-14.html`. Book lines
are in btcopilot-sources `bowentheory/FE.txt` (Kerr and Bowen, Family Evaluation) and
`bowentheory/FTiCP.txt` (Bowen, Family Therapy in Clinical Practice).

## The formulation

1. A cluster is a stretch when the family's chronic anxiety runs above its usual level. A
   disturbance in its relationships opens it, the family's patterns bind it, and it ends at a
   new balance, which may hold a symptom. [Oracle: R-0850] FE 1373, 1375, 1389, 921, 1919,
   1379.
2. A cluster is evidence in time for the formulation; it is not the formulation itself.
   [Oracle: R-0850]
3. The coach's guess states the pattern: which of Kerr's three kinds of dysfunction carried the
   anxiety (illness in a spouse, marital conflict, impairment of a child), through whom, and
   when. [Oracle: R-0850] FE 1905.
4. Over- and under-functioning between two people lies behind illness in a spouse.
   [Oracle: R-0850] FE 1979.
5. Distance is a further way anxiety is bound. [Oracle: R-0850] FE 957.
6. The guess never says why; it says what happened, how, when and where, and may predict.
   [Oracle: R-0850] FTiCP 1312, 2036.
7. The event that opens a cluster matters through the relationships it unbalances, more than
   through the event itself. [Oracle: R-0850] FE 1377.
8. A cluster may open when someone joins or leaves the family, or when a key member's
   functioning changes: an addition, a loss, a threatened loss, a departure, a marriage, a
   cutoff. [Oracle: R-0850] FTiCP 2470, 2474.
9. Families hide the connection between such events and react with denial when it is shown, so
   the app shows the dates side by side and lets the person see it. [Oracle: R-0850] FTiCP 2474,
   2482.
10. That trouble follows a death over months to years is kept as a hypothesis and tested against
    the data, which may disprove it. [Oracle: R-0850] FTiCP 2474.
11. The prognosis lives on card nine, built on the eight cards before it. [Oracle: R-0850]
    FE 3117, 3425, 3463-3465.
12. Every reading is marked as the person's ("you said") or the app's, and a card with too little
    says what it still needs to know. [Oracle: R-0850]

## The ten cards

1. Executive Summary: who has the trouble and what it is, then the pattern from card 6 in one
   sentence.
2. The family: one line per household the person grew up in and lives in now, with the one fact
   that turns the list into a reading.
3. What brought the person: their own words, quoted, with the date.
4. The couple: one statement on the couple from its early years, with the facts as chips.
5. Each parent's family: one statement per side, with its chips.
6. The coach's guess: one pattern statement (what bound the anxiety, through whom, when), one chip
   per cluster with "For" and "Against", and the open question naming what it needs to know.
7. The person's part: what the person did, toward whom, with dates, inside the pattern of card 6,
   then the other way it could have gone.
8. The choice: merged into card 7; no separate card.
9. What to work on: Kerr's therapeutic focus, built on card 6, then the prognosis; the person's
   aim as a chip in their words.
10. The effort: what the person has done since setting the aim and what followed, as dated chips.

## How the refresh writes them (as built)

- One model call, the coach's own prompt, offered only add_impression; it writes cards 1, 3, 6, 7
  and 9; the page draws the rest from the diagram. [Oracle: R-0825, R-0850]
- Its inputs: every event with its words and notes, the coach's notes and questions, one summary
  per conversation (the stored one; a conversation with none gets one written then, one extra
  call each), and, while no note is on card 3, the first conversation's opening read raw, each
  message by its number, up to 2000 characters, and for each drawn cluster its supporting shifts
  (how many, whether all one person's, the days from its opening to the first and last). Never the
  whole thread.
- A cluster with fewer than three supporting shifts stays stored and drawn; the shortfall is said
  on its Against line of card 6, in words (A1). One whose supporting shifts are all one person's
  is that person's run: card 6 says so, and its Open line asks about the others in the family then
  (A9). [Oracle: R-0850]
- Card 3 (`what_brought`) quotes the person and rests on their message, which the page shows as
  "You said, <day>"; with none, the card reads "Not asked yet" and a dashed amber "What brings
  you here?".
- The coach's later lines are marked: "For <cluster>:" and "Against <cluster>:" (card 6, only on
  clusters it rests on), "Open:" (card 6, the dashed amber chip), "Other way:" (card 7, the
  alternative), "Prognosis:" and "Aim:" (card 9).
- A card that gives a cause or a why is refused and asked for once more; given again with one, it
  is written with those sentences taken out. The words are one list in the code.
- Card 8, the choice, is no longer written or drawn; the page has nine cards, so what to work on
  is numbered 8 on it.

## Cluster rules

- A1. A cluster is the app's opinion that shifts across the family belong to one span of time,
  stored with its events and who proposed it. Counts against it: fewer than three of its events
  are supporting shifts, or shifts added later fall mostly outside its span. Neither refuses it.
- A2. A cluster may open when someone joins or leaves the family, or a key member's
  functioning changes.
- A3. A cluster may reach months to years after a loss; the gaps are measured and kept as data.
- A4. Its members are the shifts of anyone in the extended family.
- A5. Which losses matter is the app's judgement of the lost person's importance, never a fixed
  list of event kinds.
- A6. A cluster is named by its loss and its years, never by the person's trouble.
- A7. Periods the person names are stored as the person's clusters and judged against the data.
- A8. The app never deletes a cluster; one that fails a check is set aside.
- A9. Only a rise in symptom or anxiety, a fall in functioning, or a relationship shift supports a
  cluster; a date of unknown certainty opens nothing.

Theory is guidance, hypotheses are tested: see
[HOW_THIS_PROJECT_WORKS.md](HOW_THIS_PROJECT_WORKS.md).
