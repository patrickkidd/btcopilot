# Open topics — the state clock, one block per topic

This file is rewritten in full by the flush at the end of every session (`/two-clocks`). Each block
is the current truth for one topic and stands on its own: what is decided (ruling ids in the
private oracle store), what is open, where the work lives, and the next action. The event
clock is [HISTORY.md](HISTORY.md), whose entries are tagged with the topic ids below. A topic
is never deleted; when it closes its status says CLOSED and the block stays.

Fields every block carries: **Status · Decided · Open · Lives in · Next action · Updated.**
Every numbered item under **Open** begins with one of four tags in square brackets: `[ruling]`
needs Patrick's word, `[build]` is work not yet done, `[verify]` is built but unchecked or
unmeasured, `[waiting]` is blocked on something outside the topic; an item that mixes two is
split into two items.

Patrick never reads a page generated from this file; the register and the dashboard pages are
retired (his word, 2026-09-11: too verbose to read). The ledger `events.json` is kept for the
record only.

---

## T-1 · Ship the personal app to the first beta users

**Status:** the app is live at familydiagram.com/app and Patrick tests every batch in his own
thread. The fast-follow FD-363 went to production twice on 2026-09-25: kept tool calls with
[try again], record versions, the map of the record, the check after each turn, hand edits
through the coach's writer, and the Questions tab with its one-time backfill. A second batch —
his fixes from his own use, required date certainty, and the coach's impressions — went out on
2026-09-26 at commit 1faeeaa with the database at 1b00000000ae. A third went out on 2026-09-26
at commit 5b2a6bb, by hand on the box: the play button under each coach reply, italic names in
tool lines, the iPhone message-box fix, the coach's notes behind a circled (i) for admins and
auditors, and questions dated in UTC. Pushed since, not deployed: the GitHub environment for
deploys and saved paid responses.
**Decided:** one server for Pro, training and the chat app; old Pro diagrams stay pickle and
new rows are JSON in the same column [Oracle: R-0241]; the beta users are the app working
group of three clinicians [R-0079]; sign-in is passwordless with Face ID on a capable phone;
the beta starts from empty records, invited by email, with no import of the old Pro database at
cutover [R-0355]; the app is served at familydiagram.com/app [R-0356]; pricing and plans are
deferred to the first $20–40 bill [R-0354]. Production is where the beta iterates, and every
deploy keeps the old container up until the new one answers. Proving a deploy is never done on
the live site with scratch accounts; one reusable test account stays. The fast-follow is one
batch PR pushed to production continuously and tested in his own thread with no data loss
[R-0484]; before any push, evidence is shown from the stored rows and from the page [R-0483].
Added 2026-09-25, not yet numbered: a build for him to test goes to the box by a release run
dispatched from the ticket branch, never by a merge, and only after the 14-point pre-deploy
test bar passes; production and testing run on separate keys. The deploy credentials live in a
GitHub environment only branch FD-363 may use, deploying only on a manual dispatch [R-0530]; a
paid response is paid for once and replayed after [R-0531].
**Open:** (1) [verify] the 5b2a6bb batch waits on his test in his own thread; (2) [ruling] whether the 4 questions the backfill found in his whole history
are too few; (3) [verify] no real coach turn had run on production before his own, because a
test sign-in link on the box was refused by the permission checks; (4) [build] production's
title bar reads "Free Diagram" instead of the diagram's real name; (5) [build] onboarding the
first beta users [R-0400]; the two invite links for their email addresses have not been sent;
(6) [build] the summary shown for a session in the sessions list answers the first message
with generic advice instead of summarising the exchange; (7) [verify] the app has never been
opened on Android; (8) [verify] passkeys have never been tried on a real https domain;
(9) [waiting] cluster quality on anyone else's record stays unmeasured until the coding loop
produces numbers; (10) [verify] no deploy has yet been dispatched through the GitHub
environment; the first dispatch from FD-363 proves it; (11) [verify] saved paid responses are
proven to replay for each case's first call only; one paid run followed by a replay-only run
proves the rest; (12) [verify] the message-box fix is checked in desktop WebKit, not yet on his
iPhone.
**Lives in:** btcopilot PR #138 (branch FD-363, open, not merged); doc/STATE.md; the private
corpus's PREDEPLOY_TESTING_RULES.md, session-dc02180f/ and
session-b147ab7f/; deploy/; .github/workflows/release.yml; btcopilot/tests/live/replay.py; the
backup prod-2026-09-26-0540-pre-fd363-5b2a6bb.dump in btcopilot-sources.
**Next action:** he tests the 5b2a6bb batch in his own thread; the next deploy is dispatched from
FD-363 through the environment.
**Updated:** 2026-09-26.

## T-2 · The coach knows the clinical definitions, and we can measure it

**Status:** the coach runs on a map of the record and reads the rest through tools; it keeps
open questions and impressions through its own tools; a date it adds must say how sure it is.
The paid live suite holds behaviour evals only; every clinical-coding eval waits for ground
truth from the IRR review group. The prompts' clinical content is still unreviewed by Patrick
and unmeasured. Since 2026-09-26 the coach keeps its own notes each turn through a tool and reads
them back the next; admins and auditors see them behind a circled (i). The frame of reference —
the theory written as requirements for the coach and the picture — has a first draft, kept out
of the repo and waiting for its own session.
**Decided:** the agent loop is the only writer and must carry the data model and clinical
definitions [R-0236]; placement rule — a rule the computer can test becomes a refusal in the
record's commit function, a field's meaning goes on the tool parameter, judgement goes in the
system prompt; Claude Code stays the entry point for improving prompts [R-0239]; IRR compares
final records, not per-statement deltas [R-0242]; every variable definition, prompt and
fragment is private [R-0305, R-0314], encrypted with sops in this repo. The coach onboards the
person first, birth date required [R-0360]; replies end with one question and no offered
answers [R-0361]; the coach owns which events belong together and never says the technical
word for a grouping [R-0371, R-0373, R-0374]. The coach works over the record like Claude Code
over code, with a map, reads and only the necessary changes [R-0479]; reads carry the record
version [R-0480]; repeats are observed, never blocked [R-0481, R-0482]; coverage of the history
is its judgement, with no number bar [R-0485]. Added 2026-09-25, not yet numbered: a refusal
that is right every time stays as code; every tool call draws a line; a fact to find is kept
only when the coach judges it relevant, including it when in doubt; impressions are stored
before they are said; prompt evals come only from a human oracle; clinical-coding evals wait
for ratified ground truth; his over- and under-functioning coding rulings are rescinded as
evals; R-0428 and R-0057 are undecided. Gaps in the coding rules are filled from the literature
with no provisional label and judged by F1 after coding [R-0519]. The coach states its own read
of each turn through a notes tool, not a field in a structured reply, and whether it is on track
stays a judgement, never a code check [R-0520, R-0485]. Anything an agent proposes about the
coach or the picture starts from his clinical frame, not the model's training, and the frame is
built and checked in a separate Fable session [R-0524, R-0525].
**Open:** (1) [ruling] the date-certainty rule (exact day certain, month or year approximate,
hedge unknown) was built without words of his and needs his yes; (2) [ruling] his review of the
"What goes in the record" section of the prompt; (3) [waiting] every clinical-coding eval waits
for the IRR review group to ratify the code it asserts; (4) [waiting] the first measurement
cannot run until his two conversations are coded as ground truth; (5) [build] the induction
instructions have not been retargeted at the agent path; (6) [build] the coach does not yet ask
about the older households around each death, separation and move; (7) [build] the scribe adds
a generically named parent or partner when the coder names a relation not on the record
[R-0325]; (8) [build] an old kept tool call that changes an existing event still shows that
event's old words; (9) [ruling] whether the separate Fable session on the frame starts from
this session's draft or from nothing; (10) [build] the frame itself: one document of the theory
as requirements, passed when a fresh session reading only it and one cluster names the key shift
the way he does, across about ten of his and clinic clusters; (11) [verify] the coach's notes
were proven on the real model for one first turn; the read-back is proven by a unit test only.
**Lives in:** btcopilot/{record.py,toolbox.py,recordtext.py,timeline.py}; the prompts under
private/prompts/; btcopilot/tests/live (the paid suite and its waiting list in README.md);
doc/PROMPT_ENGINEERING_LOG.md; doc/HOW_THIS_PROJECT_WORKS.md (spend and eval rules); the frame
draft doc/FRAME_OF_REFERENCE.md in the FD-363 worktree (uncommitted) and its copy in the private
corpus's session-b147ab7f/.
**Next action:** his word on the frame draft, then the separate Fable session builds the frame.
**Updated:** 2026-09-26.

## T-3 · One app: Pro and Training as thin layers on the chat

**Status:** the whole loop is built, including people and family structure, and stands on the
chat app's own database on the beta3 sandbox. Patrick walked sections one to six himself on
14 and 15 September and ruled ten times as he went; every one of those rulings is built except
the last, R-0346, which was in flight when the session stopped. Sections seven, eight and nine
of doc/archive/2026-09-TEST_2026-09-14.md were driven step by step in a browser and corrected to the
screen, but he has not walked them.
**Decided:** one Vite app, features by licence, role and view; coding is documenting a case,
Pro on desktop; training is auditor/admin features on top [R-0237]; the rule stays: an
existing surface can carry the addition [R-0243]; Pro adds cases, sessions with a recording
upload and a speaker-mapping sheet, notes, and a wider desktop layout with the drawer pinned;
coding protocol: no assignments, any coder any time, each Done joins the pool and recomputes
agreement, blind until your own Done [R-0242]; three stages — code blind, vote on a phone
without names, then a meeting with names and tallies that ratifies [R-0250, R-0254, R-0257];
the unit is a conversation up to a cut Patrick selects [R-0267]; the coder's screen is one card
for the one task [R-0258, R-0265]; the agenda screen is his administration [R-0259]; the review
front end is isolated so it can never break Personal or Pro [R-0245].
**Ruled walking it, 2026-09-12/13, and built:** the word is "on the agenda", never "on the
table" [R-0308]; the meeting's choice is a "decision", never a "settle", and only resolved
events feed the guidelines [R-0309]; the screen says "coding guidelines", not codebook
[R-0310]; a professional licence holder is not a coder — only the auditor role sees the task
card, the ballot and the meeting [R-0311]; an unresolved event never returns to a later
meeting and the agenda box holds only flagged rules [R-0312]; the eleven-second wait on ratify
is accepted [R-0313]; a coder's version of an event is an "opinion", and the "left out by N
coders" line is a sentence hidden when nobody left it out [R-0315]; every event row names who
and what [R-0318]; the meeting list sorts by divergence or by time and agreed events are
readable [R-0316]; an agreed event opens on a tap of its row with a close button top right
[R-0317]; on a split the room selects which version to keep [R-0319]; every dot on the
agreement wire answers a tap [R-0320]; the meeting header is one title, a labelled figures
line, a colour legend, the wire, the sort control and the list, with the teal tally chip gone
[R-0321]; fixture data reads like real use [R-0307]; the dev flow is build, sandbox, verify
independently, fix, then one walk document with sign-in links [R-0306].
**People and family structure, ruled and built:** testing stopped so that people, pair-bonds
and who somebody is born to could be designed pixel by pixel before anything else was built
[R-0322], and they are ADDED to the decided flow, never a re-conception of it [R-0323]. The
order was a conventions sheet from the desktop app's drawing code (the code wins over the
written visual specification), then a renderer-drawn gallery of hostile cases, then goldens
[R-0324]. Twelve drawing rules came out of the gallery [R-0325]; two of them reach past
drawing — a missing or unnamed parent or partner is added as a generically named person
("Sarah's father") so the bond can exist, and a child whose parents are not on the record
stands alone. In the review [R-0326]: structure words go in the coding thread's own lines; the
people list stays as it is, with no chips and no second line, because chips imply a tap into
chat; the person editor gains "born to" and lists pair-bonds one per other person ever; the
ballot shows a family fragment per version; structure items stay off the meeting wire and are
counted in the legend. The costs he weighs are technical and architectural complexity,
inference cost and accuracy — never agent effort.
**Ruled walking it himself, 2026-09-14/15, and built:** sessions are never dropped fast, so he
is not signed out mid-walk [R-0337]; agents may edit the front end while he walks, because a page
reload is acceptable [R-0338]; on the ballot, no box round a selected family fragment, the
statement outlined in the transcript, "none" last in the relationship field, and a prev button
beside next [R-0337]; the walk document carries its link in every section, one action per step,
and the action verb in a different colour [R-0337]; on the meeting, a dot tap travels the list
with an animated scroll, the title and figures scroll away while the wire, its legend and the
sort control stay at the top [R-0338, R-0340], structure cards are laid out like event cards
[R-0338], a tap on a version keeps it and the kept version is stored on the item so it lights on
every later reading [R-0339], version rows carry initials only [R-0342], and a decided item keeps
its seat and collapses in place [R-0341]; the agenda's way in is a filled button reading "run the
meeting", and a ratified conversation offers its result, ratified rows told apart by date
[R-0341]; the result screen is reachable again from the task card's done list and the agenda, its
summary scrolls under a title and one labelled figures line, finished tasks look tappable, and a
coach pass that was never coded is said in words [R-0343, R-0344]; the list button opens the
events and people list full screen over the chat and the picture, and the person editor says
"born to" with a mother and father picked by name and "Partners" beneath, never "bond" [R-0345].
A walk document is now driven literally in a real browser by an independent agent before it is
handed to him [R-0343].
**Ruled from his own use of the app, 2026-09-22:** the wider layout, with the events and
people list standing beside the chat, is no longer held back for a professional licence — it
turns on for everybody once the window is wide enough, a phone sideways counts too, just to try it out
[R-0367]. The first of his three complaints about the inherited event shape is answered: a move
is no longer a kind of its own, ordinary notable events carry a "noted" kind, and the change
was made before the beta rather than after [R-0363, R-0364, R-0365].
**Open:** (1) [verify] Patrick has walked sections one to six; seven, eight and nine are driven
and corrected but he has not walked them; (2) [build] only an admin may flag a ratified guideline
or control the agenda, the vote and the meeting, and the account button shows its icon [R-0346] —
this was being built when the session stopped and nothing has landed; (3) [ruling] the event
model: the first complaint is answered by the noted kind, and the rest of the normalised shape
and the remaining questions on that page are still unanswered (doc/EVENT_MODEL.md,
page
https://claude.ai/code/artifact/d4dbc090-fbde-464c-bcdc-0cc31e1a5c53); (4) [ruling] whether a
person's name is written above the shape or below it
(https://claude.ai/code/artifact/2c391e04-6283-4590-b9ba-9e46910b5fab); (5) [ruling] adoptive and
foster parents, possibly several on one person, are a known open design question [R-0345];
(6) [ruling] two questions his earlier walk raised: whether a professional signing in should land
on their chat rather than anything from the review, and whether the ratify wait should move to a
background worker the sandbox does not run; (7) [build] the catalogue for beta users still draws
its built screens by hand rather than from captures of a running fixture sandbox [R-0279];
(8) [build] Pro "notes" has no mockup; (9) [build] the two-sided compare view folds into the
ballot or the meeting screen; (10) [build] the old SARF coding page becomes a legacy link,
deleted after re-coding [R-0238]; (11) [waiting] migrating last year's IRR material — 25 rules
keyed to meeting number, six meetings' agreement tables of about 40–60 rows, six deliberation
records in prose, six raw transcripts never migrated — needs his yes on the plan [R-0262,
R-0273]; (12) [waiting] the interface calls still on the drawing page, none of which block the
beta.
**Lives in:** the spec sheet for beta users, doc/SCREENS.md, rendered by
bin/screenspage.py to https://claude.ai/code/artifact/4d218257-5aac-4196-b8ca-c76b159a95ba; the
review screens https://claude.ai/code/artifact/78a2f31e-45b3-44c9-8c46-29ce877aaed9; the coding
page https://claude.ai/code/artifact/62abcc8b-0e87-4bfa-962f-cdaa03475d5a; Pro's surfaces
https://claude.ai/code/artifact/fdb8a5b5-d043-46f4-afea-700a886210a3; the fragment conventions
doc/FRAGMENT_CONVENTIONS.md and the gallery doc/mockups/fragment.html;
btcopilot/review/, web/src/, the walks in web/tests/walks/, the suite btcopilot/tests
run by bin/t; VERIFY_2026-09-14.md; TEST_2026-09-14.md; doc/EVENT_MODEL.md and its
page https://claude.ai/code/artifact/d4dbc090-fbde-464c-bcdc-0cc31e1a5c53; the names
comparison https://claude.ai/code/artifact/2c391e04-6283-4590-b9ba-9e46910b5fab; the walk page
https://claude.ai/code/artifact/ad9750a2-d38c-469c-b5af-5a143f7ab3ab.
**Next action:** Patrick walks sections seven, eight and nine of
doc/archive/2026-09-TEST_2026-09-14.md, and rules on the rest of the event model page and on the
names comparison page.
**Updated:** 2026-09-22.

## T-4 · Existing records and conversations in the new app; wipe and re-code

**Status:** the shape question is answered by test; the import itself is deferred past the beta.
**Decided:** previously released Personal app versions do not matter; existing diagrams and
discussions must work in the new app; colleagues' earlier sessions must be migrated in; "wipe
all coding and re-run the agent loop over the conversation" is a feature to build, like the
old training app's clear-and-re-extract. Added this session: the beta starts from empty records
and a per-diagram manual import comes later, on the evidence that the old diagram format maps
onto the new record field for field [R-0355].
**Proved this session:** a Pro-shaped record carrying relationship moves with their targets,
triangles, an emotion, a layer, intensity, colour, Qt dates and points is stored, read back by
the chat page with the sub-fields intact, returned to the Pro app equal, and keeps its
desktop-only fields after a hand edit. The comparison page "Old Record, New Record" is
https://claude.ai/artifact/VAUvng5FkgXs16eUQzxCLi. Writing it found that DATA_MODEL.md gave a
triangle's type as pairs; it is a list of person ids, and the document is fixed.
Added this session: the event kinds changed under the beta — "moved" left the kind list and
ordinary notable events became a "noted" kind, so a diagram imported from the desktop app has
to have its moves translated at the import boundary [R-0365]. The eight moves already stored on
the box were rewritten in place at the storage level, with no translation at read time.
**Open:** (1) [build] old training transcripts are now kept out of the session list, the fix
having landed, but they are not yet importable on purpose — that is the upload and
speaker-mapping path on the one-app topic; (2) [build] three carry-over defects: diagrams
carried over have no stored clusters until a turn writes an event, every diagram that ever had
a chat carries an "Assistant" person, and items extracted but never committed on old diagrams
are unreachable; (3) [build] after a wipe, chips in the old thread point at deleted events and
read as plain words, so the re-code should re-link matches on kind, date and people;
(4) [build] the by-hand re-code script is ephemeral and the feature needs the same thing as a
session-menu item; (5) [verify] the importer dry run against a restored July dump stays
Patrick's to run — restoring the dump here was refused as personal-data handling (review log
row 137).
**Lives in:** btcopilot/tests/test_prorecord.py; doc/specs/DATA_MODEL.md;
MERGE_REVIEW.md §4; run_agent_f1.replay.
**Next action:** build "re-code with the coach" in the session menu (T-3 build); the per-diagram
import waits until after the beta.
**Updated:** 2026-09-22.

## T-5 · Picture and interface rulings still open

**Status:** everything Patrick hit using the app on his phone through 2026-09-25 is ruled and
built on the branch; the drawer's third tab, now "From the coach", holds the coach's open
questions (on production) and its impressions (built, deploying). The SARF story has a
brainstorm with its one question answered. Four pages of earlier drawings still wait on him.
Deployed 2026-09-26: the play button under each coach reply and italic names in tool lines. The
play-by-play has confirmed drawing bugs, and the chalkboard design is blocked on the frame of
reference (T-2).
**Decided:** the picked-moment words on the timeline (option A) [R-0235]; the about page behind
an i, ✕ in the arrow's place; one icon-button size [R-0234]; the card slides the whole region;
who·what words [T-2]. Ruled and built from his own use, 20–22 September: the amber question mark
on the line is hidden for now, both where the line is empty and past the end for undated facts,
with the reasoning kept in comments and the drawing rule left standing [R-0359]; the amber
closing question in a coach reply stays, because it reads as bold and that is where the eye
should go [R-0358]; the back arrow inside an open cluster always closes the cluster rather than
only putting a picked event down [R-0362]; a noted event is a lead, so it raises the question of
order beside a shift the way a structural event does [R-0366]; the wide layout comes up for
anyone on a wide window, a phone turned on its side included [R-0367]; Return starts a new line
and only the send button sends [R-0368]; selecting an event and tapping "in chat" finds the words
even when the coach wrote them in the session on screen. Ruled on the drawings, 22 and 23
September: event dots sit on the line at one height always, or people get confused, and the soft
boxes round a cluster are good enough for the beta but do not feel right [R-0377]; the picture
spot always shows a picture, so a words-only view does not belong there, though a list could go
elsewhere later [R-0378]; the line gets a short sideways scroll built on what exists, rather than
another round of drawings [R-0381] — built and live, the recent years filling the width, the rest
one swipe away, never more than two screens, and an open cluster printing its real years; the
main view still needs one word for its name, and as the dots multiply the picture must keep
saying something at a glance rather than becoming a wall of dots nobody can tap [R-0402].
Added 2026-09-24 and 25, not yet numbered: new screens are allowed when thought through; the
coach's open questions are a third tab beside Events and People, showing only open questions it
asked, in "Food for thought" and "Facts to find", a tap putting the question in the message box
and a swipe left dismissing it; the tab is renamed "From the coach" with a third section,
"Impressions", where the coach's inferences can be pushed back on with "Doesn't fit" or
"Partly"; every label names all its people, the speaker included, superseding R-0457; the
picture band is 72 pixels tall instead of 66 so an event's title sits clear of its dot, with
touch targets sized to common conventions; the list button has no circle and sits at chip
height; more room between a reply's tool lines and its words; the close button lines up with
the ask button; a chip tap behaves like a dot tap, with a per-user switch back; SARF shifts as
people report them are remembered, isolated episodes, so no line or step graph of those shifts.

**The literature research (finished, written up, his verdicts in):** what was read — Family
Evaluation (Kerr and Bowen) and the SARF sources, the passages listed one per concept in
doc/PICTURE_IDEAS.md. What came out of it — fourteen concepts for the picture spot
drawn by three designers from those passages and from his own record, put through a critic and
an auditor; six survived, ranked: the line we have with a short sideways scroll; only words, one
line per cluster; the family drawn with the trouble lit and a strip of clusters beside it; a
stack of generations; the gap between a cluster's opening event and its symptom; a carved strip
of hills. The finding was that nothing beat the line, and each survivor says one thing the line
cannot, which argues for the picture changing with whatever the coach is talking about. What he
ruled — words-only is out, because the picture spot must hold a picture [R-0378]; the family
drawing needs the traditional diagram and automatic arrangement, so it is a goal for later
[R-0379]; the lanes of generations carry no message on a record where only one person has a
recorded change, and are kept in the corpus until there is data [R-0380]; the gap between what
opened a cluster and the symptom that followed is fundamental to a proper family evaluation and
is kept and tracked [R-0382]; build the scroll rather than draw more [R-0381]; and depth or
motion only where it communicates what flat cannot [R-0399]. What is unread or undecided — the
sources he approved for this reading were items 2, 3, 4, 5 and 7 of the list put to him, and the
rest of that list is unmined; his own idea that a cluster's height could mean how much clinical
signal sits under it is unruled; and no source has yet been read on what the picture should do
when a record holds several people's symptoms.

**The phone-app research (finished, written up, one round drawn from it):** what was read —
twenty-four small-screen data views from shipped apps, Garmin Connect's sleep views among them,
with Apple Health, Oura, Whoop, Bearable, Flighty and Carrot, each written up in
doc/MOBILE_VIEWS.md. What came out of it — each view mapped onto the eight things the
picture has to say, with three of the eight showable on his record today (where the history
gathers, the long quiet years, and nearness of a date to a symptom on two of his five clusters)
and five needing data the record does not hold (a named key shift per cluster, a symptom in a
second person, consequences in other people after the two deaths, functioning and relationship
shifts at the dates already on the line, and the older generations). Five hybrids came out of
that mapping and three were drawn as round 8 on the app's own line: one line of words above the
line survived, the gap drawn inside a cluster box was killed because the app spreads dots evenly
inside a box so the bracket contradicts its own words, and before-and-after on a tap was killed
as drawn because the app's cluster tap already opens the whole cluster — the idea belongs as a
mark inside that view. What is undecided — the three questions on the round 8 page below, and
whether the two unbuilt hybrids (a fixed row of words naming the newest cluster, and four
stacked sparklines one per variable) are worth drawing once the data exists. Standing rule
throughout: when a view cannot be drawn until the record holds more, say so plainly [R-0380].

A fault reported in the last drawing is explained and closed: a tap on a cluster there only
selected it and showed its title, because the brief gave the designer the tap language for dots
and left out the app's own behaviour, where a cluster slides in as a card [R-0224, R-0230,
R-0223, R-0213]; no ruling changed it and the app itself is unaffected.
**Open:** (1) [ruling] the coach writes the line of words above the picture, so every load spends
a model call on one sentence that can be wrong: may it put two things side by side when the
record holds only their dates, the way the drawn one pairs the 1994 move with the trouble
sleeping in 1996? On the round 8 page https://claude.ai/artifact/WrGWM6m2cXJfQ3FLHnNMu3 ; (2) [ruling] that sentence needs a row of its
own, so the picture grows from 132 to 154 pixels and the chat under it loses 22: is one line of
words worth that room? Same page; (3) [ruling] with the sentence there the line comes to rest
where the sentence points rather than at the present, so the first thing on screen is the middle
of the record instead of today: should the picture follow the words or always open on today?
Same page. He has tested the sideways scroll on the deployed app and says it works well.
The recommendation put to him, which is a recommendation and not his decision, is to build
nothing from round 8 now and to fold the line of words into the cluster work instead, where the
coach names each cluster's key shift; (4) [ruling] the earlier page on the crowded line https://claude.ai/artifact/Twf8XW5GHDVRiUWsxQcARj and the
brainstorm of concepts https://claude.ai/artifact/G5gYDqzhvar5KXPJAhtbzm carry their own decisions and are unanswered; the
withdrawn redraw is https://claude.ai/artifact/FzfjSGH6EQVt61vC5R2DFi ; (5) [ruling] whether a cluster's height should mean
how much clinical signal sits under it — which of the four variables moved, in how many people,
how close together — never the number of events; his own idea, unruled; (6) [build] two faults
of the line found while drawing round 8: at true scale the seven dots of the 2009 to 2011 cluster
merge into one solid bar, and the 1996 dot cannot be tapped because the 1997 dot's target covers
it; (7) [build] a third fault: the two-events-face-to-face drawing reads a row that does not
exist, so its second label and seam come out as nothing — nothing on his own path reaches it
yet; (8) [build] grouping is the coach's judgement with a one-line scope and the floor binds only
the automatic draft [R-0287]; the nodal ring stays and its flag follows the clinical definition
[R-0283]; no trend lines until real data [R-0284]; (9) [build] the event editor's relationship
fields; (10) [ruling] whether tapping an event's words inside an open cluster jumps to its
editor, which he will say after testing [R-0207]; (11) [waiting] the gap between a cluster's
opening event and its symptom waits for a record with enough data [R-0382]; (12) [waiting] the
family drawing waits for the traditional diagram and automatic arrangement [R-0379], and the
lanes of generations wait for a record that carries shocks between households [R-0380];
(13) [build] a play button under each coach bubble that plays or replays that message, the way
the Claude app has one [R-0387]; (14) [ruling] which voice reads the replies: the phone's own
today, cloud neural voices at roughly a cent a reply, ElevenLabs at several times that, or
self-hosted models the box cannot run. Anything paid also waits on the measurement question on
the platform topic [R-0388]; (15) [ruling] three choices the impressions build made under his
general yes: "Partly" counts as push-back only once the reply is sent; "Doesn't fit" posts the
impression into the chat as a chip rather than plain words; the empty tab reads "Nothing from
the coach yet."; (16) [ruling] the SARF story: whether other kinds of shift may suggest a line;
the brainstorm recommends the coach naming each cluster's key shift in one sentence with its
caveat, and the coach noticing one person moving the same way three chapters running and asking
about it — neither is ruled or built, and it is a topic for Fable; (17) [waiting] what his own
record can show as it is, and a pass correcting events whose dates were guessed, both wait on a
read of his record that the permission checks refused; (18) [ruling] the two picture goldens
board-first-move and rest-dense60 wait on his approval; (19) [verify] a chip tap working like a
dot tap is built with a switch back and he has not tried it; (20) [build] the play-by-play
bugs he confirmed [R-0526]: a distance move drawn on the mover's own figure; a bond line drawn
outside the bond's dates; a bond and a separation drawn alike; a second shift on the same event
not drawn; an undated-certainty event left out of the steps; app words in the captions —
fixed after the frame, not before; (21) [build] events accept a move whose target is its own
mover, which pair bonds already refuse [R-0527]; (22) [waiting] the chalkboard: how the coach
draws a story arc that fits every case, not only the one cluster tried, waits on the frame of
reference [R-0524, R-0525].
**Lives in:** doc/PICTURE_IDEAS.md (the fourteen concepts, the passage behind each,
the critic's verdicts); doc/MOBILE_VIEWS.md (the twenty-four phone views, the mapping
onto the eight messages, the five hybrids); doc/archive/2026-09-UI_GAP.md; REVIEW_LOG.md round 5;
STATE.md; doc/FRAGMENT_CONVENTIONS.md; the drawings and their verdict files in
~/theapp/btcopilot-sources/fd-corpus/design/round6, round7 and round8; the published pages
https://claude.ai/artifact/Twf8XW5GHDVRiUWsxQcARj , https://claude.ai/artifact/FzfjSGH6EQVt61vC5R2DFi , https://claude.ai/artifact/G5gYDqzhvar5KXPJAhtbzm and https://claude.ai/artifact/WrGWM6m2cXJfQ3FLHnNMu3 ; the open-questions mockups
https://claude.ai/artifact/XSmWsbSEdyChP1SM6AHKMd and the impressions mockups
https://claude.ai/artifact/AfUU6Pzq2vaLPm3QvY7BH7 ; the SARF brainstorm and the two build
contracts in the private corpus's session-dc02180f/; the play-by-play step shots, the sheet and
the survey of 56 clusters in the private corpus's session-b147ab7f/.
**Next action:** he tries the 5b2a6bb batch on production and answers the three impressions
choices; the chalkboard and the SARF story resume on Fable after the frame.
**Updated:** 2026-09-26.

## T-6 · Clusters by example

**Status:** the fault he found — clusters appearing and vanishing between messages — is fixed
and live: the model is handed the clusters that already exist and keeps them unless there is a
stated reason in the story to change one.
**Decided:** the rules make the candidates, the model names them and gives a reason
[R-0193, R-0194]; the floor is three events, enforced at the commit; user groupings under the
old floor are grandfathered. Ruled 2026-09-22 and 23, and built: which events belong together is
a judgement under Bowen theory rather than a rule about dates, so the coach's own guidelines do
it, keeping what exists so the picture does not thrash and reshaping only on a strong reason
[R-0371]; no fixed stretch of time bounds one, and the work is sculpting rather than rewriting
[R-0374]; a birth, marriage, divorce or death opens a chapter and the shifts recorded around it
are what the chapter is about [R-0375]; nothing on the picture draws what changed between one
reading and the next — when it changes the coach says so in ordinary conversation [R-0372]; and
the coach never says the word for these groupings, nor that an event was added to one, because
that is technical: it talks about the story [R-0373]. What one should show, taken from the
sources: which single shift matters most, who has been carrying the trouble and that it passed between people, the start
event and what followed, dates lining up with a symptom shown as nearness and never as proof,
and never a count [R-0376].
**Open:** (1) [build] the model does not yet name the one key shift of each grouping, nor who
carries the trouble in it, which is what the picture has to show [R-0376]; (2) [ruling]
he has marked no example clusters yet, and the examples are the input only he can give;
(3) [waiting] cluster quality on anyone else's record stays unmeasured until the coding loop
produces numbers.
**Lives in:** btcopilot/clusters.py; the grouping prompt in the private prompt files;
doc/PICTURE_IDEAS.md; the drawings in ~/theapp/btcopilot-sources/fd-corpus/design/ and
their pages https://claude.ai/artifact/FzfjSGH6EQVt61vC5R2DFi , https://claude.ai/artifact/G5gYDqzhvar5KXPJAhtbzm and https://claude.ai/artifact/WrGWM6m2cXJfQ3FLHnNMu3 .
**Next action:** teach the model to name each grouping's key shift and who carries the trouble,
so the picture can say it.
**Updated:** 2026-09-22.

## T-7 · The drawn family and auto-arrange

**Status:** off the path, on the list [R-0240].
**Decided:** the agent loop's family-structure data is built before this; the family picture follows
later as one more picture level, auto-arranged first, hand layout after.
**Open:** (1) [waiting] whether auto-arrange works well enough on agent-loop data is untested,
and cannot be tested until the coding work produces structure data.
**Lives in:** btcopilot/arrange/, the training app's SVG renderer, familydiagram plan doc
2026-05-02--auto-arrange-layout.md.
**Next action:** none until T-3 produces structure data.
**Updated:** 2026-09-11.

## T-8 · Isolation of the Personal package (option A)

**Status:** largely overtaken by the platform reset and the separate database. The chat app no
longer shares a database, a migration chain, a user table or a prompt file with Pro; what is
left of the original ruling is the lint-held package boundary inside the repo.
**Decided:** isolate the Personal app with a package boundary inside btcopilot; a single adapter module is the sole
importer of Pro code and the shared schema, enforced by a lint rule; a second service can come later, but not a separate
repository [R-0233]. Since then: the chat app takes its own database and its own accounts, and
old Pro users are imported once rather than shared live [R-0327]; the review package is already
isolated and a test asserts it [R-0245].
**Open:** (1) [build] the lint rule holding the adapter as the only importer is still unwritten;
(2) [verify] the importer of the old Pro users and diagrams has been dry-run only, never run
against a real dump.
**Lives in:** doc/archive/2026-09-ISOLATION_OPTIONS.md; doc/PLATFORM_BUILD.md steps 6 and 7;
btcopilot/review/.
**Next action:** after Patrick's walk, with the platform work.
**Updated:** 2026-09-14.

## T-9 · How sessions run (process)

**Status:** binding; extended 2026-09-12/13/14 and 2026-09-24/25.
**Decided:** everything in doc/HOW_THIS_PROJECT_WORKS.md plus: never coin a term;
build only on an explicit go; mockups are drawn with the app's own stylesheet; the flush at
session end is `/two-clocks` and is idempotent; sub-agents do the work, one status line only
[R-0248]; he is Patrick, never "Patrick" [R-0261]; artifacts are UI drawings, never text
documents [R-0255]; every turn on a design topic shows drawn options [R-0256, R-0260]. Added
this session: he wants replies cut to about a quarter length — just the answer and the one thing he
does next, nothing restated [R-0304]; the dev flow is build the batch, stand the sandbox up on
fixtures with history kept, verify independently in real browsers, fix, then hand him one
document of numbered walks in plain words with the sign-in links [R-0306]; fixture data is
realistic, because filler hides what a screen shows [R-0307]; the corpus's own vocabulary is
not his, so it is said in plain words; an Opus-level auditor watches wall-clock time, that no
suite is run too early or unfiltered, and that tests are derived from rulings [R-0331]; the
chat app's tests are their own suite, filtered to the changed component and run whole once at
the end [R-0332]. Added 2026-09-15: someone other than the builder walks the document step by step, in a real
browser, on the same fixture accounts, before it reaches him, and
every step that does not match the screen is corrected first [R-0343]; the document carries its
sign-in link in every section, puts one action in a step, and colours the action verb [R-0337];
agents may keep editing the front end while he walks, because a page reload is acceptable
[R-0338].
Added this session: the branch instructions now carry the correction that sub-agents do the
mechanical work while the coordinator holds one-line summaries, relays nothing while a run is
going, and posts one message at the end; and that no verification walk ever runs against the live
site, because nine scratch accounts made that way turned up on Patrick's own dashboard — walks
run against the development server on his Mac instead. Added 2026-09-21 to 23, from his own use and the drawing rounds: he reports bugs, comments and
brainstorms continuously while he uses the app, and every one is written down as it arrives and
fixed only when he says to fix it [R-0383]; a status line never leaves a thing open ended — it
says whether it is done and what happens next [R-0384]; nothing is called fixed on reasoning, only
on evidence from the real call with the real prompt [R-0385]; before research begins, the list of
sources to be read goes to him so he can confirm they are the right ones [R-0395]; what gets found is
folded into the conversation instead of left for him to dig out of documents later, and those
documents themselves stay in the project [R-0397]; the flush records where each research thread
stands, so he can pick it up where he left off [R-0401]; the admin path and the dashboards belong
to the other session, and the two keep to their own work, meeting only over code they both touch in the shared
worktree and on the box [R-0391]; exactly one test account exists and is reused [R-0393]; and
trying things stops happening on the live server; a dev server on his Mac comes next, reachable
from his phone over Tailscale as the next step, timing open, while testing continues on the box
with the first beta users meanwhile [R-0403]. From the drawing rounds: a drawing is published as a page, never left as a file on disk; a separate agent reviews
every frame before he sees it and only survivors are published; a page gives direction and a
recommendation rather than a menu, with the prose cut to what he must decide; motion or depth is
used only when it says something flat cannot; a drawing's tap behaves exactly as the app's tap
does, built on the app's own picture code; and a frame a stranger cannot read unaided has failed,
because users never see the prose beside it [R-0398]; clever technology earns its place only
where it communicates what flat space cannot, and rotation for its own sake communicates nothing
[R-0399]; and a gallery passes an aesthetic critique, an argument between agents if that is what
it takes, before he sees it [R-0396]. Added 2026-09-24 and 25, not yet numbered: brainstorm topics are taken one at a time, and
anything brought to him comes one related chunk at a time; development runs in an agent team so
the coordinator talks to him at product level; mockups are always published as artifacts, and
while he is on his phone everything reaches him through artifacts without permission dialogs;
the session tells him when to switch between Opus and Fable; a build for him to test is
deployed from the branch, never by merging, and the session's own testing against the 14-point
pre-deploy bar is what makes that safe; every real-model spend is asked for first and happens
only at the end of a batch when a prompt or tool changed, the sandbox running on a local model
by default; agents must be able to run what the work needs on the production box. Added
2026-09-26: replies to him are specific and carry only what changes his decision, never
echoing his words or raising questions that are not open [R-0523]; agent chatter is never
relayed and the final message stands alone [R-0025]; the rulings on a topic are read before
any coach behaviour is proposed; testing does not spend on every run, and a paid response is
saved and replayed [R-0531]; design starts from his clinical frame, not the model's training
[R-0524].
**Open:** (1) [build] the permission checks still refuse production reads, a test sign-in
link on the box and reads of personal data; the answer so far is that he restarts in bypass
mode, which his settings already default to; (2) [ruling] five rulings of this session were
decided by an agent under his general yes and wait on his word (listed in the private corpus's
RULINGS_TO_APPEND_2026-09-25.md).
**Lives in:** doc/HOW_THIS_PROJECT_WORKS.md; the private corpus's PREDEPLOY_TESTING_RULES.md; doc/TEST_STRATEGY.md;
btcopilot/CLAUDE.md; .claude/skills/two-clocks/SKILL.md; bin/flushcheck.py; bin/t.
**Next action:** he restarts in bypass mode.
**Updated:** 2026-09-26.

## T-10 · Project memory: the two clocks, the flush, the trace

**Status:** the two clocks are the working system of record; the trace and dashboard pages are
retired as things he reads, kept for the record only. Agents cannot write the rulings store, so
each flush leaves a plain list of the session's rulings with his words for him to append. A move
of this work to a fresh clone at ~/btcopilot is planned and has not started.
**Decided:** one thought-and-decision trace in the order of Patrick's own statements, mined
from the transcripts; the flush is idempotent and topics are picked up by name; he never runs a
command — he reads pages or files; the register and dashboard pages are retired, his word
2026-09-11, too verbose to read. The oracle store is in this repo encrypted with sops, with his
own key as a recipient; agents may not decrypt it [R-0451]. Added 2026-09-25, not yet numbered:
the move to ~/btcopilot copies no sessions — the FD-362-onward sessions are reopened by id, from
a list with dates and topics kept in the private corpus — and carries over the memories that
apply; ~/theapp becomes the legacy home for master-legacy and the familydiagram release branches.
**Open:** (1) [waiting] R-0477 to R-0485 and this session's rulings wait for him to append them
by hand from RULINGS_TO_APPEND_2026-09-25.md in the private corpus, then re-pin the fingerprints;
tests written this session cite the nearest existing ruling until then and need re-citing;
(2) [ruling] the move plan's 13 remaining choices, each with a recommendation; (3) [build] the
move itself, after those choices; (4) [build] the word lists still leave records the ledger
cannot assign to a topic, and every trace name no flush has rewritten is a machine guess;
(5) [build] revision chains between rulings do not draw; (6) [verify] whether the ledger and
trace scripts run against the encrypted store has not been checked since the move into this repo.
**Lives in:** .claude/skills/two-clocks/; doc/{TOPICS.md,HISTORY.md}; private/oracle/
(encrypted); the private corpus's HANDOVER_2026-09-25-FD363.md (with the session list),
RULINGS_TO_APPEND_2026-09-25.md and session-dc02180f/MIGRATION_PLAN.md.
**Next action:** he appends the rulings; then his word on the move plan.
**Updated:** 2026-09-25.

## T-11 · Platform reset: repo, deployment, billing, identity, admin

**Status:** the app is live at https://familydiagram.com/app with its certificate, its database
and Patrick's account, at commit ec757d5 and migration 1b00000000ad since 2026-09-25, on its
own production key; he has chatted with the coach from his phone, and the invite mail has been
sent and received. Deploys roll without dropping a request. Datadog is gone and Grafana Cloud is
live in its place. Every coach call now reads most of its words from the model's cache and writes
what it cost to a table. fdserver is out of this ticket and the Pro backend has its own
maintenance branch. A second session owns the dashboards, the command line the bot drives and the
per-call cost rows; it shares this branch and commits within minutes of each change.
**Decided:** one public repo; every prompt is one encrypted file with shared fragments, one key
pair per machine, private keys never copied; files naming real people never enter a repo. The
chat app has its own 2 GB droplet with Caddy and backups; the old droplet stays for the Pro
desktop app. Stripe owns money only, with tokens metered in our own table and a hard cap. No
admin web app: an agent runs a command line. The coach stays on Claude Opus 4.6 with thinking;
launch US-only with Stripe Tax on. The chat app starts over with its own accounts on its own
database [R-0327]; the region is sfo3 [R-0330]; Claude creates the droplet and changes DNS only
on his explicit confirmation each time [R-0353]; pricing waits for the first bill [R-0354]; the
beta starts from empty records [R-0355]; the app is served at familydiagram.com/app while
everything else on familydiagram.com keeps redirecting to alaskafamilysystems.com/family-diagram
[R-0356]; he granted DNS and production access to get it running [R-0357]. Observability was
ruled Datadog [R-0328] and this session moved it to Grafana Cloud Free, which covers metrics,
logs, traces and browser sessions at no cost and is the stack Patrick already runs at work
[R-0370]; self-hosting the stores on the 2 GB box and running them on his laptop were both set
aside. No health information of any kind goes into a log, a metric, a trace or a session
recording.
Added 2026-09-25, not yet numbered: production and testing use separate Anthropic keys — the box
runs on the new production key and the old key is off it, every test path spends the testing
key and fails loudly without it; a deploy for him to test is a release run dispatched from the
ticket branch, never a merge; agents must be able to run what the work needs on the box.
**Live on the box:** droplet familydiagram-app at 209.38.135.250 in sfo3; five containers — the
web app, the worker, Postgres, Redis and Caddy; secrets in a root-owned file every compose
command passes; the migration chain rewritten in dependency order because Postgres refuses a
foreign key to a table that does not exist yet, and the database at its head revision; the root
and www records pointing at the box; Caddy holding the certificate; the app mounted at /app.
**Built this session:** seven faults that stopped the very first coach turn — the twelve shared
prompt fragments never re-encrypted for the box's key, three tool meanings missing from the
private prompt that the tools now require, the Anthropic client library pulled forward to a
version that drops an argument the app passes in six places, the public prompt directory missing
from the installed package, and the Gemini key having no home in the secrets template. A test
now fails when any setting the app reads without a fallback has no home on the box. Dependencies
are their own image layer, so a build is minutes rather than twelve. Every deploy keeps the old
container answering until the new one is healthy: 106 probes during a roll, none failed. The
coach turn now runs on the server independent of the request and streams, with its log going
through Redis at the address the box sets [R-0369]; the first deploy of that broke every message
because the app looked for Redis on the local machine, and was rolled back in two minutes.
**Built later the same day:** every coach call reads the fixed coaching text and the tool
definitions from the model's cache, and each step of a turn reuses the steps before it. Measured
live on one four-step turn: each step read between 10,200 and 10,800 words from cache and paid
full price for between 86 and 360 new ones; the fixed coaching text alone is 3,893. Every call
also writes a row saying who it was for, which model, four counts of words and what it cost. The
command line that runs the site now previews and stops before anything that changes data unless
it is told to go ahead, and Patrick's own assistant reaches it over one pinned key on the box.
**Ruled this session:** the Pro backend continues on its own branch with the same release flow,
so a merged bug fix rebuilds the image and deploys the old box [R-0386]; cost over time per user
has to reach the dashboards, and the brainstorm about leaving Datadog ran in a separate session
that reported back by message rather than filling this one [R-0389]; his own model in openclaw
administers the site from a markdown file linked in its instructions and kept current with the
deployed source, running read-only commands freely and confirming anything destructive [R-0390];
prompt caching is used on every coach call because the cost is already noticeable [R-0392]; the
old committed compose values were never exposed because that repository is private, so there is
no rotation, and its branches for this work are deleted [R-0394]; and the scratch accounts are
deleted with one test account kept and reused [R-0393].
**The Pro maintenance stream:** master on btcopilot is tagged `pre-chat-first`; a `master-legacy`
branch starts there, is protected like master, builds an image tagged `:legacy` on every merge
and deploys the old box. btcopilot PR #137 and fdserver PR #31 carry the last two pieces and
await his merge.
**Open:** (1) [ruling] no feature that costs money per use is switched on until each beta user
can see their own use and what it costs, and that measurement sits inside the learning this app
exists for — will people pay for it, and do they like it. The example on the table is a paid
voice reading the coach's replies at roughly one cent a reply: he tabled it rather than dropping
it, and money out of his own pocket is the lesser of his two concerns. What those measures are
has not been designed. (2) [build] freeze the old droplet for Pro. (3) [build] money
through Stripe: account, keys and the price, after the first bill [R-0354]. (4) [build] archive
the fdserver repo once nothing refers to it. (5) [verify] production still has no automated
database backup. (6) [verify] one invite driven from his
Discord assistant end to end has never been done. (7) [build] three loose ends on the
dashboards, all the other session's: the form for the browser session recordings, per-container
figures after the metrics agent was remounted, and revoking the administrator token used to set
the stack up. (8) [waiting] the dashboards are built but not on the box: deploying them
needs the Grafana token there, a refresh of the dependency lock at the workspace root that only
Patrick can run, and a release build.
**Note for the next session:** the permission classifier refuses a sub-agent both `sops
updatekeys`, because it writes the secret store, and `docker compose pull` and `up` on the box,
because that is a production deploy. Production reads on the box are refused to sub-agents too.
Those run at the top level on Patrick's direct grant.
**Lives in:** deploy/ (compose, Caddyfile, secrets template, README, the release workflow
and the four appcast feeds); doc/PLATFORM_BUILD.md; doc/archive/2026-09-DATADOG.md;
private/prompts/ and private/oracle/, encrypted.
**Deploys, 2026-09-26:** the release workflow's deploy job reads the host, user and key from a
GitHub environment named production that only branch FD-363 may use, runs only on a manual
dispatch and checks out the dispatched commit on the box [R-0530]. Until then every deploy ran
by hand on the box because the host setting was missing. A repository-wide host setting that
would have deployed master was created and removed the same hour. Open: (9) [verify] the first
dispatch through the environment has not run; (10) [build] a later ticket branch needs the
environment's branch rule widened before it can deploy.
**Next action:** he sets a spend limit on the testing workspace in the Anthropic console; he
puts the Grafana token on the box and refreshes the dependency lock so the observability commit
can deploy; the next deploy is dispatched from FD-363.
**Updated:** 2026-09-26.

## T-12 · The learning loop: a scout that looks outward and a review of the scout

**Status:** built and wired into the flush; never run.
**Decided:** a scout runs in this repo, reads the process docs, the week's history and his own
typed statements out of the session transcripts, researches current agentic-development
practice, and writes at most ten ranked items, each with a source, why it matters here, the
exact file and line it would change, and one prediction against one of four measured numbers —
hours from brief to walk, his findings per walk, re-walks per screen, suite minutes; it opens
draft pull requests touching only process files and never applies its own proposals [R-0333].
Everything proposed at either level comes from a cited development outside this project, with a
link and a date [R-0335]. A conservative auditor and a progressive designer form one two-agent
review of the scout itself, writing one ledger entry and touching only the scout's own brief
[R-0334]. The loop is local and event-driven, not scheduled: the flush invokes the scout after
any build that handed him a walk, and the review after every fourth scout run or two measured
outcomes; two cloud routines exist as a fallback for weeks with no build and stay disabled
[R-0336]. Kill rules: fewer than one proposal in six merged after eight runs retires the scout;
a merged change that does not move its number within two builds stops that kind of proposal.
**Open:** (1) [waiting] the first scout run has still not happened: it reads a fixed list of
accounts on X.com through the Chrome extension, the extension was not connected on 15 September
either, and the run waits rather than skipping the source; (2) [verify] none of the four baseline numbers
has been measured twice, so no prediction can yet be scored.
**Lives in:** doc/archive/2026-09-SCOUT.md (the ledger and the counts);
.claude/skills/scout/SKILL.md; .claude/skills/loop-review/SKILL.md; the two disabled cloud
routines.
**Next action:** connect the Chrome extension, then the next flush after a walk runs the scout.
**Updated:** 2026-09-15.
