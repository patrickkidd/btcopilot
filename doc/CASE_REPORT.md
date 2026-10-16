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

What the report's readings rest on, from Kerr's evaluation (FE 3101-3119, ten questions) and
Bowen's method. Each point names the book lines it comes from. [Oracle: R-0850]

The full framing, with the Kerr passages it rests on by book and line, lives in the private corpus
file `research/case-report-cards/FORMULATION-2026-10-14.md` (R-0850). Every future case report
change starts from that file, not from this summary, and improves it as the work goes on.

1. The pattern. Kerr names three patterns that carry a family's anxiety into a symptom: illness
   in a spouse, conflict between the spouses, a problem in a child (FE 1905); which one
   predominates decides where the symptom shows (FE 1907). One partner over-functioning while the
   other under-functions lies behind the first (FE 1979-1981); distance is a further way anxiety
   is held (FE 945-947, 957). The coach's guess names the pattern, the nuclear family it runs in
   (the person's parents with the person as their child, or the person's own couple), and rests
   it on the relationship marks the events carry.
2. Through whom and when. The coach's guess lays out the people in time order with the time
   between them, and never says anything passed, flowed or was transmitted from one to another.
   It says what happened, how, when and where, never why (FTiCP 1312, 2036).
3. Triangles. Who sits in which triangle, from the principal triangles each partner grew up in
   (FE 3225) to the ones that outlive their members (FE 1615). The coach's guess names a
   triangle only when the events' inside and outside marks show one; otherwise it asks about it
   on its Open line.
4. Cutoff and positions in each extended family. How cut off each partner is from each side
   (FE 3115, 3209): a side the person knows little about is a fact toward cutoff (FE 3205), held
   as the app's guess. Each person's place among their brothers and sisters, and each parent's
   (FE 3221, 3461).
5. Stressors against adaptiveness. How many changes piled up in the family, past and present
   (FE 3109-3111, 3187, 3435), weighed against how the family has held up: marriages that lasted,
   people alive and in touch (FE 3229-3231, 3465). Each For line of the coach's guess gives the
   changes in that cluster's years and who was rearranged around its opening: the opening event
   matters through the relationships it unbalances (FE 1375-1377).
6. Onset. Whether the trouble came on fast near events or built slowly (FE 3127, 1373, 3467).
   When the person says when the trouble is worst or least, that is a fact for or against the
   pattern (FE 947, 1981, 3447).
7. The balance after. After a run of raised anxiety the family settles at a new balance, which
   may hold a symptom (FE 1379, 1381). Each For line says how things stood after its cluster,
   the symptom included when it went on, as facts; never what the symptom does for anyone.
8. The clusters are the when. A cluster is a stretch when the family's anxiety ran above its
   usual level, opened by someone joining or leaving the family or a key member's functioning
   changing (FE 1375-1377, 1389; FTiCP 2470, 2474). It is the formulation's evidence in time,
   not the formulation; that trouble follows a loss over months to years is a hypothesis the
   data may disprove (FTiCP 2474).
9. Facts side by side, then stop. Families hide the connection between such events and deny it
   when it is shown (FTiCP 2474, 2482), so a card sets the dated facts beside each other and
   explains no connection beyond its dates.
10. The prognosis lives on card nine only, built on the cards before it (FE 3117, 3423-3425), and
    says what it rests on: one pattern across the years or several (FE 3463), the pile-up against
    how the family has held up (FE 3465), fast or slow onset (FE 3467). No other card says what
    will come.
11. Every reading is marked as the person's ("you said") or the app's, and a card with too little
    says what it still needs to know.

## The ten cards

1. Executive Summary: who has the trouble and what it is, then the pattern from card 6 in one
   sentence; three sentences at most, no run of events.
2. The family: one note by the coach, one line per household the person grew up in and lives in
   now, with the one fact that turns the list into a reading (who left, who died, when), never a
   head count; a chip per person and event it rests on, then the family picture button on the
   phone (on a wide window the picture stands beside the cards). With too little, the "Not enough
   in the diagram yet:" line. [Oracle: R-0850, R-0866]
3. What brought the person: their own words, quoted, with the date.
4. The couple: one statement by the coach on the person's own couple (them and their partner
   now, never their parents) from its early years: when they met, when they married, what
   changed in contact with each one's family after, with each event it rests on as a dated chip.
   With too little it is one line, "Not enough in the diagram yet:" and what it still needs,
   shown as the dashed amber chip. [Oracle: R-0850] FE 3165.
5. Each parent's family: two notes by the coach on the one card value `sides`, one per side, each
   one statement that turns the side's list into a reading (what repeats on that side, or a loss
   and when) with its chips, or that side's "Not enough in the diagram yet:" line. The page puts
   each under the side whose people it rests on (the parent, everyone above them, and their
   descendants but the parent's own children), never by a word in its text; a note resting on
   neither side, or on both equally, takes the side left open in the order written, the mother's
   first, as the prompt asks. The pictures of each side are behind the family button.
   [Oracle: R-0850, R-0866]
6. The coach's guess: one pattern statement (what bound the anxiety, in which nuclear family,
   through whom, when, the people in time order), one chip per cluster with "For" and "Against",
   and the open question naming what it needs to know; it says nothing of what will come.
7. The person's part: what the person did, toward whom, with dates, inside the pattern of card 6,
   then the other way it could have gone.
8. The choice: merged into card 7; no separate card.
9. What to work on: Kerr's therapeutic focus, built on card 6, saying whether it agrees with the
   person's aim, then the prognosis with what it rests on; the person's aim as a chip in their
   words, or no aim line when they have not said one.
10. The effort: what the person has done since setting the aim and what followed, as dated chips.

## How the refresh writes them (as built)

- One model call, the coach's own prompt, offered only add_impression; it writes cards 1 to 7 and
  9 (`main_guess`, `family`, `what_brought`, `couple`, `sides` twice, `coach_guess`, `own_part`,
  `work_on`); a card not given is asked for once more; the page draws the effort from the
  sessions. [Oracle: R-0825, R-0850, R-0866]
- Its inputs: every event with its words and notes, the coach's notes and questions, one summary
  per conversation (the stored one; a conversation with none gets one written then, one extra
  call each), and, while no note is on card 3, the first conversation's opening read raw, each
  message by its number, up to 2000 characters, and for each drawn cluster its supporting shifts
  (how many, whether all one person's, the days from its opening to the first and last), the
  changes in the family in its years by year, and who its opening is about with their partners
  and children. Beside them, computed from the diagram each time: what each person is to the
  person and whose side they are on; the person's and each parent's brothers and sisters in birth
  order; how many events the diagram holds on each side of the family; each triangle the events'
  inside and outside marks show, with who was inside and outside when; and the relationship events
  of each pair that includes the person's own family, their parents or grandparents, by date,
  with pairs farther out counted. Never the whole thread. On the dense stand-in family (125
  people, 281 events) these blocks add about 6,500 characters.
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
- A card other than card 9 that says what will come (will, expect, likely, predicts, prognosis,
  outside the person's quoted words), and an Executive Summary of more than three sentences, are
  refused and asked for once more; refused again, the card keeps what it had.
- Card 8, the choice, is no longer written or drawn; the page has nine cards, so what to work on
  is numbered 8 on it.

## Catch-up

After the deploy carrying FD-381, with a database backup first: `flask admin fd381-catchup plan` lists each report with a card the coach last wrote before the deploy, `apply --plan <file>` marks those out of date so the owner's next tap rewrites them (the catch-up never calls the refresh), and `undo --plan <file>` takes the marks back [Oracle: R-0772]. The mark is the diagram's `case_report_forced_out_of_date` column, apart from the change-date check: the page says "The coach now writes this report a new way." while it is true and no family change since the last card write says more; only a Refresh that writes cards sets it back to false, never one card the coach writes in a turn.

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
