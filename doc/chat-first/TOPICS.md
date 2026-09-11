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

Patrick audits this file as a page, never by command: the flush renders it with
`bin/topicpage.py` and republishes it to the same artifact every time —
**https://claude.ai/code/artifact/8a56716d-dca5-4123-ae2e-572da33a392c** (pass that URL to the
Artifact tool as `url`), and the two-clock dashboard — every dated event since the first
session as a branching timeline or tree, toggled with this register as the state view — to
**https://claude.ai/code/artifact/be081e64-9efa-45de-b329-42e82f9d4857**. The ledger behind
it is `events.json` beside this file, rebuilt by `bin/ledger.py`. In VS Code the file itself
is this one.

---

## T-1 · Ship the personal app to the first beta users

**Status:** ready for Patrick's review before merge; deploying on the existing production
server, merge-first (his direction 2026-09-10).
**Decided:** one server for Pro, training and the chat app; old Pro diagrams stay pickle and
new rows are JSON in the same column [Oracle: R-0241]; the beta users are the app working
group of three clinicians [R-0079]; sign-in is passwordless with Face ID on a capable phone;
the sandbox is https at turin:8891 with a dev CA the phone trusts once.
**Open:** (1) [ruling] his code review of the branch, and of the coach's prompt section, which
is the first open item on the coach topic; (2) [build] continuous integration is red — ten web
unit tests written before rounds 2–4, screenshot goldens recorded only on macOS, and nine older
extraction tests that fail only when the whole backend suite runs in one process;
(3) [verify] the app has never been opened on Android; (4) [verify] passkeys have never been
tried on a real https domain; (5) [waiting] cluster quality on anyone else's record stays
unmeasured until the coding loop produces numbers.
**Lives in:** btcopilot PR #136, fdserver PR #30; merge-risk review with the seven fixes
landed: doc/chat-first/MERGE_REVIEW.md (fix commit 9f1707a); review log
doc/chat-first/REVIEW_LOG.md; sandbox scripts /Users/patrick/worktrees/fd362-sandbox/.
**Next action:** Patrick reviews; then merge, deploy, invite the three.
**Updated:** 2026-09-11.

## T-2 · The coach knows the clinical definitions, and we can measure it

**Status:** built on the sandbox, unreviewed by Patrick, unmeasured.
**Decided:** the agent loop is the only writer and must carry the data model and clinical
definitions [R-0236]; placement rule — a rule the computer can test becomes a refusal in the
record's commit function, a field's meaning goes on the tool parameter, judgement goes in the
system prompt; Patrick's own prompt-improvement process does not change: Claude Code is the
entry point and finds the instructions itself [R-0239]; IRR compares final records, not
per-statement deltas [R-0242].
**Open:** (1) [ruling] his review of the 168-line "What goes in the record" section in the
private prompt file, which is his clinical content rewritten for the loop; the author's list of
what was dropped is the newest entry in the prompt engineering log; (2) [waiting] the first
measurement cannot run: the replay harness has nothing to score against until his two
conversations are coded as ground truth; (3) [build] the induction instructions have not yet
been retargeted at the agent path; (4) [ruling] whether the coach should code the clinical
variables itself in conversation or leave them to a review pass.
**Lives in:** btcopilot/personal/{record.py,toolbox.py,timeline.py}, training/run_agent_f1.py;
the private prompt section (`git -C ~/theapp/fdserver/.claude/worktrees/FD-362 show HEAD~3 --
prompts/private_prompts.py`, or the file's section by that title); the induction instructions
(btcopilot/training/prompts/induction_agent.md, doc/PROMPT_OPTIMIZATION.md, the strategy doc);
doc/PROMPT_ENGINEERING_LOG.md; his sandbox record re-coded once by the loop (session "Living
With Chronic Insomnia (re-coded)").
**Next action:** his prompt review; code his two conversations (T-3's coding mode, or by hand
in the editor); run the harness once.
**Updated:** 2026-09-11.

## T-3 · One app: Pro and Training as thin layers on the chat

**Status:** designed and ruled; the IRR review is a three-stage ground-truth process whose
screens are approved as drawn (version 5); the coding page is tabled; nothing built.
**Decided:** one Vite app, features by licence, role and view; coding is documenting a case,
Pro on desktop; training is auditor/admin features on top [R-0237]; never a new view where an
existing surface can carry the addition [R-0243]; Pro adds cases (= the family switcher on the
account page), sessions (= the sessions sheet + "upload a recording" with a speaker-mapping
sheet), notes, and a wider desktop layout with the drawer pinned; coding is a read-only session
whose composer bar becomes "select a line, type an instruction, a cheap scribe records it" with
Done; coding protocol: no assignments, any coder any time, each Done joins the pool and
recomputes agreement, results visible only to contributors, blind until your own Done [R-0242];
the coach's replay is one coding among others; the upload/speaker-mapping sheet is approved as
drawn; the coding-page design is tabled except where it overlaps the review [R-0247].
**The IRR review, ruled 2026-09-11:** the approaches are tried in the meetings and each meeting
teaches the next [R-0244]; the review front end is isolated so it can never break Personal or
Pro [R-0245]; two families, data slices and an AI-guided walk, with the AI's help important
[R-0246]; "gold" means ratified — the AI's set is the proposed record, the ratified record is
ground truth [R-0249]; **three stages** — code blind from scratch; once three coders are done,
each votes on a phone before the meeting on every disputed item, takes shown without names and
with no AI takes at all; the meeting sees only what the vote left open, with names and tallies,
every item given one of keep / change / unresolved before ratify, and ratifies with unresolved
items kept as data [R-0250, R-0254, R-0257]; nobody is paid, the work is a rolling window, and
convergence is required but not forced [R-0251]; original opinions are kept in full fidelity,
leaning yes to hiding who chose what until ratification [R-0252]; **the unit** is a
conversation up to a cut Patrick selects — the cut is the last turn when he puts it on the
table, he can move it back by tapping a line but never before the last ratified cut, a cut at
the end of a finished conversation or recording is the whole thing, and anything changed since
the last cut is re-coded [R-0267]; the coder's screen is one card for the one task and history
under it, never a list [R-0258, R-0265]; Patrick's administration is the table screen — date,
what is on the table, who is done, nudge; the AI writes the guideline changes itself from the
settles and a result screen shows them with their provenance, nothing to choose [R-0259]; the
page is approved as drawn [R-0268].
**Open:** (1) [ruling] on the review screens, version 6
(https://claude.ai/code/artifact/78a2f31e-45b3-44c9-8c46-29ce877aaed9): the agreement timeline
above the meeting's list — A, one dot per moment, teal agreed and amber disputed with a count,
or B, one dot with a column of coder squares under it; (2) [ruling] where the coding
guidelines are reached in the app — the help row on the account page as drawn, or the sessions
sheet. Ruled today and drawn: names hidden whenever people vote and shown only at the meeting
[R-0272]; the vote opens when Patrick opens it [R-0273]; no numerical rule settles an item, the
meeting sees every disputed item most split first with the unanimous ones collapsed [R-0274];
the database is the record and the coding guidelines are the one written output, readable in
the app [R-0275]; flags, unresolved items and unfinished tasks fill the next meeting's agenda
by themselves, with a close link each [R-0276]; one timeline shows agreement and disagreement,
never a lane per coder [R-0277]; (3) [build] the spec sheet for beta users is a picture
catalogue (https://claude.ai/code/artifact/4d218257-5aac-4196-b8ca-c76b159a95ba): built views
are the app's test goldens of 2026-09-09 (some show test data), five screens have no picture
(signing in, the person editor, the account page, the about page, when something goes wrong) —
fresh renders from a fictional fixture record are the next fix, blocked on the fixture
sign-in links returning 404 against a fixture sandbox; (7) [waiting] migrating last year's IRR material, the last follow-up item of this unit [R-0262, R-0273] — inventory 2026-09-11 of
doc/irr/: 25 rules in tables keyed to meeting number with unanimity and confidence (migrate as
rows with the meeting as provenance); six meetings' agreement/disagreement/action tables keyed
to statement ids of last year's discussions, about 40–60 rows (migrate as settle rows once
those discussions are imported through the upload path); six deliberation records in prose
(keep as text, mine for rationale later); six raw transcripts (irreplaceable, never migrated);
the old per-statement feedback stays the batch harness's ground truth until re-coded — his yes
or no on that plan; (8) [build] the coding screens are approved as drawn, version 3, nothing open
(https://claude.ai/code/artifact/62abcc8b-0e87-4bfa-962f-cdaa03475d5a): the one-task card; the
transcript up to the cut with the last ratified cut as a hairline, earlier turns shown in full
but not codable; the coder's own words in the thread with the scribe's edit line under them;
Done in the top bar with a confirmation sheet; the next task card [R-0270, R-0271]; (9) [build] the two-sided
compare view already drawn folds into the ballot or the meeting screen; (10) [build] Pro
"notes" has no mockup; (11) [build] build order once the six rulings land: codings, cuts,
ballots, votes and scores tables; endpoints; replay as a task; export of ratified items to the
ground-truth files; the session menu items; the coding mode; the review module isolated;
(12) [build] the old SARF coding page becomes a legacy link, deleted after re-coding [R-0238].
**Lives in:** the spec sheet for beta users, every screen's behaviour in plain words, kept by the
flush: https://claude.ai/code/artifact/4d218257-5aac-4196-b8ca-c76b159a95ba (source
doc/chat-first/SCREENS.md, renderer bin/screenspage.py); the review screens, version 5, approved
https://claude.ai/code/artifact/78a2f31e-45b3-44c9-8c46-29ce877aaed9 (source
/Users/patrick/.claude/jobs/16d9eee6/tmp/ballot-meeting.html, ephemeral — the artifact is the
durable copy); the coding loop plan
https://claude.ai/code/artifact/7a033173-bff2-41ca-bbde-39385d4ab7f3; thin layers
https://claude.ai/code/artifact/daeb8856-4a5b-42d4-ab62-4c14bc3784b4; upload and compare
https://claude.ai/code/artifact/c5040b6a-75e3-47de-aba7-54aabbda69f4; IRR concepts round 1
https://claude.ai/code/artifact/a7637a73-8ebc-4166-8b5b-c6a3269aa973; review-room ideas
https://claude.ai/code/artifact/40ba5500-7be3-4bc2-82ed-193f8367448f; the three-stage analysis
(text; superseded in form by R-0255)
https://claude.ai/code/artifact/67988998-6e49-4924-a9b3-579979901eaf; the coding page
https://claude.ai/code/artifact/62abcc8b-0e87-4bfa-962f-cdaa03475d5a; mockups are drawn with
web/src/theme.css and the app's markup (his rule 2026-09-10); last year's material in
doc/irr/.
**Next action:** Patrick rules on the review screens' six choices, confirms Pro's surfaces one
by one (notes undrawn), and answers the migration plan; the spec sheet for beta users becomes
a picture catalogue of every ruled view; then any remaining screens are drawn pixel for pixel
before code review [R-0269].
**Updated:** 2026-09-11.

## T-4 · Existing records and conversations in the new app; wipe and re-code

**Status:** understood; one part fixed, the feature unbuilt.
**Decided:** previously released Personal app versions do not matter; existing diagrams and
discussions must work in the new app; colleagues' earlier sessions must be migrated in; "wipe
all coding and re-run the agent loop over the conversation" is a feature to build, like the
old training app's clear-and-re-extract.
**Open:** (1) [build] old training transcripts are now kept out of the session list, the fix
having landed, but they are not yet importable on purpose — that is the upload and
speaker-mapping path on the one-app topic; (2) [build] three carry-over defects: diagrams
carried over have no stored clusters until a turn writes an event, every diagram that ever had
a chat carries an "Assistant" person, and items extracted but never committed on old diagrams
are unreachable; (3) [build] after a wipe, chips in the old thread point at deleted events and
read as plain words, so the re-code should re-link matches on kind, date and people;
(4) [build] the by-hand re-code script is ephemeral and the feature needs the same thing as a
session-menu item.
**Lives in:** MERGE_REVIEW.md §4; run_agent_f1.replay; the by-hand script
/Users/patrick/.claude/jobs/33d688bb/tmp/recode.py.
**Next action:** build "re-code with the coach" in the session menu (T-3 build).
**Updated:** 2026-09-11.

## T-5 · Picture and interface rulings still open

**Status:** waiting on Patrick; none block the beta.
**Decided:** the picked-moment words on the timeline (option A) [R-0235]; the about page
behind an i, ✕ in the arrow's place; one icon-button size [R-0234]; the card slides the whole
region; who·what words [T-2].
**Open:** (1) [ruling] does the three-event cluster floor bind a grouping the user made himself,
which is row 54 of the review log; (2) [ruling] the nodal ring on a dot, keep or drop;
(3) [ruling] thirteen rows in the interface gap list are marked as needing his word;
(4) [build] the event editor's relationship fields and its hiding of fields by event kind;
(5) [ruling] the felt call on the moves board.
**Lives in:** doc/chat-first/UI_GAP.md, REVIEW_LOG.md, STATE.md.
**Next action:** his rulings, in any order.
**Updated:** 2026-09-11.

## T-6 · Clusters by example

**Status:** waiting on examples he marks.
**Decided:** the rules make the candidates, the model names them and gives a reason
[R-0193, R-0194]; the floor is three events, enforced at the commit; user groupings under the
old floor are grandfathered.
**Open:** (1) [ruling] he has marked no example clusters yet, and the examples are the input
only he can give; (2) [waiting] cluster quality on anyone else's record stays unmeasured until
the coding loop produces numbers.
**Lives in:** btcopilot/personal/clusters.py; the cluster prompt in the private prompt file.
**Next action:** none until T-3 yields coded conversations.
**Updated:** 2026-09-11.

## T-7 · The drawn family and auto-arrange

**Status:** off the path, on the list [R-0240].
**Decided:** family-structure data from the agent loop comes first; the drawn family arrives
later as one more picture level, auto-arranged first, hand layout after.
**Open:** (1) [waiting] whether auto-arrange works well enough on agent-loop data is untested,
and cannot be tested until the coding work produces structure data.
**Lives in:** btcopilot/arrange/, the training app's SVG renderer, familydiagram plan doc
2026-05-02--auto-arrange-layout.md.
**Next action:** none until T-3 produces structure data.
**Updated:** 2026-09-11.

## T-8 · Isolation of the Personal package (option A)

**Status:** ruled, not built [R-0233].
**Decided:** a package boundary inside btcopilot — one adapter module is the only importer of
Pro code and the shared schema, held by a lint rule; a second service later; never a separate
repository.
**Open:** (1) [build] the package boundary is unbuilt, one to two days when it is scheduled.
**Lives in:** doc/chat-first/ISOLATION_OPTIONS.md.
**Next action:** after the beta is up.
**Updated:** 2026-09-11.

## T-9 · How sessions run (process)

**Status:** binding; extended 2026-09-09/10/11.
**Decided:** everything in doc/chat-first/HOW_THIS_PROJECT_WORKS.md plus: never coin a term;
estimate the work not the validation; build only on an explicit go — a question about an
estimate or a plan is part of the brainstorm; mockups are drawn with the app's own stylesheet;
the flush at session end is `/two-clocks` and is idempotent. Added 2026-09-11: sub-agents do the
work, one status line only, one short final reply per turn, model and effort chosen per agent
[R-0248]; he is Patrick, never "Patrick" [R-0261]; artifacts are UI drawings in the app's
style, never text documents, and the open decisions live on the drawing in one numbered list,
never repeated in the reply [R-0255]; every turn on a design topic shows drawn options with
descriptions long enough to explain what is not self-evident, never a research project
[R-0256, R-0260]; every question mark is covered somewhere, not recited [R-0253, R-0264].
**Open:** none.
**Lives in:** doc/chat-first/HOW_THIS_PROJECT_WORKS.md; btcopilot/CLAUDE.md (his corrections);
.claude/skills/two-clocks/SKILL.md; bin/flushcheck.py.
**Next action:** none.
**Updated:** 2026-09-11.

## T-10 · Project memory: the two clocks, the flush, the trace

**Status:** built in first form; names are mechanical until a flush rewrites them.
**Decided:** one thought-and-decision trace in the order of Patrick's own statements,
mined statement by statement from the transcripts, branching where a thread starts; a node at
rest is a name plus one line, his words behind a click; shape B — threads as stacked lines
across time, his trace stepping between them; dates, commits and artifacts are secondary
under the statement that caused them [R-0244]; the flush is idempotent and topics are picked
up by name; he never runs a command — he reads pages or files.
**Open:** (1) [build] 253 of 723 statements are not yet placed on a piece of work, and every
name and summary is script-made until a flush session rewrites this session's; the word lists
are one mechanism and the flush's judgement step is the other; (2) [build] the session filter
pulled in about 14 statements from two unrelated sessions that mention "coach", so the filter
needs tightening; (3) [build] revision chains between rulings do not draw yet, because the store
marks a superseded ruling in a column the ledger does not read; (4) [ruling] whether the opening
view should sit at the newest statements, with "fit" showing the whole; (5) [verify] the flush
step that rewrites names has never been run in anger.
**Lives in:** bin/{trace.py,tracepage.py,ledger.py,eventpage.py,topicpage.py,flushcheck.py},
doc/chat-first/{trace.json,events.json,TOPICS.md,HISTORY.md}, .claude/skills/two-clocks/SKILL.md;
the trace page https://claude.ai/code/artifact/be081e64-9efa-45de-b329-42e82f9d4857; the
shape mockups https://claude.ai/code/artifact/fefb75e5-dade-4cf9-8892-eb7e61af6dc7.
**Next action:** a fresh session runs `/two-clocks` for real — assigns the unplaced statements,
rewrites this session's names, tightens the filter — then he reviews the page for fidelity.
**Updated:** 2026-09-11.

