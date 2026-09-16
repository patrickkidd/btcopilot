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

**Status:** the code is ready for his review; the box has its database, his invite is minted,
and DNS points at it; the beta waits on the four keys and his first sign-in.
**Decided:** one server for Pro, training and the chat app; old Pro diagrams stay pickle and
new rows are JSON in the same column [Oracle: R-0241]; the beta users are the app working
group of three clinicians [R-0079]; sign-in is passwordless with Face ID on a capable phone;
the sandbox is https at turin:8891 with a dev CA the phone trusts once. Added this session: the
beta starts from empty records, invited by email, with no import of the old Pro database at
cutover [R-0355]; the app is served at familydiagram.com/app [R-0356]; pricing and plans are
deferred to the first $20–40 bill [R-0354].
**Open:** (1) [ruling] his code review of the branch, and of the coach's prompt section, which
is the first open item on the coach topic; (2) [waiting] the four service keys for the box —
Anthropic, AssemblyAI, and the Brevo mail username and password — without which the coach does
not answer and no sign-in mail is sent; (3) [verify] the app has never been opened on Android;
(4) [verify] passkeys have never been tried on a real https domain; DNS now points at the new
box, so his first sign-in through the invite is the test; (5) [waiting] cluster quality on anyone else's record stays unmeasured
until the coding loop produces numbers.
**Lives in:** btcopilot PR #136 (fdserver PR #30 closed unmerged, 2026-09-16); merge-risk review
with the seven fixes landed: doc/chat-first/MERGE_REVIEW.md; review log
doc/chat-first/REVIEW_LOG.md, 146 rows; sandbox scripts
/Users/patrick/worktrees/fd362-sandbox/; the box's deployment deploy/chat/.
**Next action:** his four keys on the box, then his sign-in through the invite link and one chat
turn; his code review and the coach's prompt review run alongside.
**Updated:** 2026-09-16, second session.

## T-2 · The coach knows the clinical definitions, and we can measure it

**Status:** built on the sandbox, unreviewed by Patrick, unmeasured. The prompts moved:
every prompt is now one encrypted file in this repo rather than a Python constant in a second
repo.
**Decided:** the agent loop is the only writer and must carry the data model and clinical
definitions [R-0236]; placement rule — a rule the computer can test becomes a refusal in the
record's commit function, a field's meaning goes on the tool parameter, judgement goes in the
system prompt; Patrick's own prompt-improvement process does not change: Claude Code is the
entry point and finds the instructions itself [R-0239]; IRR compares final records, not
per-statement deltas [R-0242]; every variable definition, prompt and fragment that lived in
fdserver before this branch is private and stays private — the tool schemas say the shape and
the private text says the meaning, coach and scribe alike [R-0305]; the scribe's prompt is
private too, because anything prompt induction will run on is valuable [R-0314]; the prompts
and the rulings are encrypted in place with sops and live in this repo, so the public checkout
holds only ciphertext and there is no second repo to reach for.
**Open:** (1) [ruling] his review of the "What goes in the record" section, which is his
clinical content rewritten for the loop; the author's list of what was dropped is in the prompt
engineering log; (2) [waiting] the first measurement cannot run: the replay harness has nothing
to score against until his two conversations are coded as ground truth; (3) [build] the
induction instructions have not yet been retargeted at the agent path; (4) [build] the coach
codes the clinical variables in session, and the goal is that its coding matches the review's
agreement — the F1 outcome of the project [R-0293]; (5) [build] the scribe now has to add a
generically named parent or partner when the coder names a relation that is not on the record,
which is a drawing ruling that reaches extraction [R-0325].
**Lives in:** btcopilot/personal/{record.py,toolbox.py,timeline.py}, training/run_agent_f1.py;
the prompts as encrypted `.prompty` files under private/prompts/ with shared fragments;
doc/PROMPT_ENGINEERING_LOG.md; his sandbox record re-coded once by the loop.
**Next action:** his prompt review after he walks the app; code his two conversations; run the
harness once.
**Updated:** 2026-09-14.

## T-3 · One app: Pro and Training as thin layers on the chat

**Status:** the whole loop is built, including people and family structure, and stands on the
chat app's own database on the beta3 sandbox. Patrick walked sections one to six himself on
14 and 15 September and ruled ten times as he went; every one of those rulings is built except
the last, R-0346, which was in flight when the session stopped. Sections seven, eight and nine
of doc/chat-first/TEST_2026-09-14.md were driven step by step in a browser and corrected to the
screen, but he has not walked them.
**Decided:** one Vite app, features by licence, role and view; coding is documenting a case,
Pro on desktop; training is auditor/admin features on top [R-0237]; never a new view where an
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
**Open:** (1) [verify] Patrick has walked sections one to six; seven, eight and nine are driven
and corrected but he has not walked them; (2) [build] only an admin may flag a ratified guideline
or control the agenda, the vote and the meeting, and the account button shows its icon [R-0346] —
this was being built when the session stopped and nothing has landed; (3) [ruling] the event
model: his three complaints with the inherited timeline shape are written up with a normalised
shape and six questions he has not answered, the last of which is whether it changes now or after
the beta (doc/chat-first/EVENT_MODEL.md, page
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
**Lives in:** the spec sheet for beta users, doc/chat-first/SCREENS.md, rendered by
bin/screenspage.py to https://claude.ai/code/artifact/4d218257-5aac-4196-b8ca-c76b159a95ba; the
review screens https://claude.ai/code/artifact/78a2f31e-45b3-44c9-8c46-29ce877aaed9; the coding
page https://claude.ai/code/artifact/62abcc8b-0e87-4bfa-962f-cdaa03475d5a; Pro's surfaces
https://claude.ai/code/artifact/fdb8a5b5-d043-46f4-afea-700a886210a3; the fragment conventions
doc/chat-first/FRAGMENT_CONVENTIONS.md and the gallery doc/chat-first/mockups/fragment.html;
btcopilot/review/, web/src/, the walks in web/tests/walks/, the chat suite btcopilot/tests/chat
run by bin/t; VERIFY_2026-09-14.md; TEST_2026-09-14.md; doc/chat-first/EVENT_MODEL.md and its
page https://claude.ai/code/artifact/d4dbc090-fbde-464c-bcdc-0cc31e1a5c53; the names
comparison https://claude.ai/code/artifact/2c391e04-6283-4590-b9ba-9e46910b5fab; the walk page
https://claude.ai/code/artifact/ad9750a2-d38c-469c-b5af-5a143f7ab3ab.
**Next action:** Patrick walks sections seven, eight and nine of
doc/chat-first/TEST_2026-09-14.md, rules on the event model page and on the names comparison
page, and says whether the deploy work may start.
**Updated:** 2026-09-15.

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
**Lives in:** btcopilot/tests/chat/personal/test_prorecord.py; doc/chat-first/DATA_MODEL.md;
MERGE_REVIEW.md §4; run_agent_f1.replay.
**Next action:** build "re-code with the coach" in the session menu (T-3 build); the per-diagram
import waits until after the beta.
**Updated:** 2026-09-16.

## T-5 · Picture and interface rulings still open

**Status:** waiting on Patrick; none block the beta.
**Decided:** the picked-moment words on the timeline (option A) [R-0235]; the about page
behind an i, ✕ in the arrow's place; one icon-button size [R-0234]; the card slides the whole
region; who·what words [T-2].
**Open:** (1) [build] grouping is the coach's judgement with a one-line scope and the floor
binds only the automatic draft [R-0287]; the nodal ring stays and its flag follows the clinical
definition [R-0283]; the thirteen interface rows are closed as built [R-0291]; no trend lines
until real data [R-0284]; (2) [build] the event editor's relationship fields; its hiding of
fields by event kind landed 2026-09-12 and no longer saves a hidden field; (3) [ruling] whether
tapping an event's words inside an open cluster jumps to its editor, which he will say after
testing [R-0207]. Closed since the last flush: the play-by-play now steps every event of a
cluster including one the move language has no mark for [R-0292]; "moment" became "event"
throughout the app's own copy [R-0289]; the sessions sheet keeps a "+" per family and a
personal reader never meets the word case [R-0285]; the app draws a family fragment to twelve
fixed rules [R-0325].
**Lives in:** doc/chat-first/UI_GAP.md, REVIEW_LOG.md, STATE.md,
doc/chat-first/FRAGMENT_CONVENTIONS.md.
**Next action:** the relationship fields; one ruling after he tests the cluster tap.
**Updated:** 2026-09-14.

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

**Status:** largely overtaken by the platform reset and the separate database. The chat app no
longer shares a database, a migration chain, a user table or a prompt file with Pro; what is
left of the original ruling is the lint-held package boundary inside the repo.
**Decided:** a package boundary inside btcopilot — one adapter module is the only importer of
Pro code and the shared schema, held by a lint rule; a second service later; never a separate
repository [R-0233]. Since then: the chat app takes its own database and its own accounts, and
old Pro users are imported once rather than shared live [R-0327]; the review package is already
isolated and a test asserts it [R-0245].
**Open:** (1) [build] the lint rule holding the adapter as the only importer is still unwritten;
(2) [verify] the importer of the old Pro users and diagrams has been dry-run only, never run
against a real dump.
**Lives in:** doc/chat-first/ISOLATION_OPTIONS.md; doc/chat-first/PLATFORM_BUILD.md steps 6 and 7;
btcopilot/review/.
**Next action:** after Patrick's walk, with the platform work.
**Updated:** 2026-09-14.

## T-9 · How sessions run (process)

**Status:** binding; extended 2026-09-12/13/14.
**Decided:** everything in doc/chat-first/HOW_THIS_PROJECT_WORKS.md plus: never coin a term;
build only on an explicit go; mockups are drawn with the app's own stylesheet; the flush at
session end is `/two-clocks` and is idempotent; sub-agents do the work, one status line only
[R-0248]; he is Patrick, never "Patrick" [R-0261]; artifacts are UI drawings, never text
documents [R-0255]; every turn on a design topic shows drawn options [R-0256, R-0260]. Added
this session: a reply to him is a quarter of what feels complete — the answer, the one thing he
does next, nothing restated [R-0304]; the dev flow is build the batch, stand the sandbox up on
fixtures with history kept, verify independently in real browsers, fix, then hand him one
document of numbered walks in plain words with the sign-in links [R-0306]; fixture data is
realistic, because filler hides what a screen shows [R-0307]; the corpus's own vocabulary is
not his, so it is said in plain words; an Opus-level auditor watches wall-clock time, that no
suite is run too early or unfiltered, and that tests are derived from rulings [R-0331]; the
chat app's tests are their own suite, filtered to the changed component and run whole once at
the end [R-0332]. Added 2026-09-15: a walk document is driven literally, step by step, in a real
browser by an independent agent on the same fixture accounts before it is handed to him, and
every step that does not match the screen is corrected first [R-0343]; the document carries its
sign-in link in every section, puts one action in a step, and colours the action verb [R-0337];
agents may keep editing the front end while he walks, because a page reload is acceptable
[R-0338].
**Open:** none.
**Lives in:** doc/chat-first/HOW_THIS_PROJECT_WORKS.md; doc/chat-first/TEST_STRATEGY.md;
btcopilot/CLAUDE.md; .claude/skills/two-clocks/SKILL.md; bin/flushcheck.py; bin/t.
**Next action:** none.
**Updated:** 2026-09-14.

## T-10 · Project memory: the two clocks, the flush, the trace

**Status:** the two clocks are the working system of record; the trace and dashboard pages are
retired as things he reads, kept for the record only.
**Decided:** one thought-and-decision trace in the order of Patrick's own statements, mined
from the transcripts; the flush is idempotent and topics are picked up by name; he never runs a
command — he reads pages or files; the register and dashboard pages are retired, his word
2026-09-11, too verbose to read. The oracle store itself moved into this repo encrypted with
sops, with his own key added as a recipient, so the rulings are readable on his machine without
a second repo.
**Open:** (1) [build] the word lists still leave records the ledger cannot assign to a topic,
and every trace name and summary that no flush has rewritten is a machine guess; (2) [build]
revision chains between rulings do not draw, because the store marks a superseded ruling in a
column the ledger does not read; (3) [verify] whether the ledger and trace scripts still run
against the encrypted store has not been checked since the move.
**Lives in:** bin/{trace.py,tracepage.py,ledger.py,eventpage.py,topicpage.py,flushcheck.py};
doc/chat-first/{TOPICS.md,HISTORY.md,trace.json,events.json}; private/oracle/ (encrypted);
.claude/skills/two-clocks/SKILL.md.
**Next action:** none until he asks for a page.
**Updated:** 2026-09-14.

## T-11 · Platform reset: repo, deployment, billing, identity, admin

**Status:** the box runs the stack with its database built and Patrick's invite minted; the two
DNS records point at it as of 2026-09-16 16:17 UTC; the certificate and the first sign-in are
the open verification. Four secret values are still placeholders. fdserver is out of this ticket.
**Decided:** one public repo; prompts leave the Python constants for one `.prompty` file per
prompt with shared fragments, encrypted in place with sops and age, one key pair per machine,
private keys never copied; files naming real people never enter a repo. The chat app gets its
own 2 GB droplet with Caddy and the backup add-on; the old droplet is frozen to serve the Pro
desktop app. Stripe owns money only: flat monthly plans through the hosted page and customer
portal, tokens metered in our own table with a hard cap. No admin web app: an agent runs a
command line whose skill file is generated from its own declarations and checked by a test. The
coach stays on Claude Opus 4.6 with thinking; launch US-only with Stripe Tax on; fdserver leaves
the daily loop and is archived. The chat app starts over with its own accounts on its own
database [R-0327]; observability is Datadog on the recommended low-cost set plus session replay
[R-0328]; the paid infrastructure host waits [R-0329]; the region is sfo3 because sfo1 has no
volumes [R-0330]. Added this session: Claude creates the droplet and changes DNS only on
Patrick's explicit confirmation, each time [R-0353]; pricing and plans wait until the app runs
in production and the first $20–40 bill shows what the usage costs [R-0354]; the beta starts
from empty records with no import at cutover [R-0355]; the app is served at
familydiagram.com/app while familydiagram.com otherwise keeps redirecting to
alaskafamilysystems.com/family-diagram until a new product homepage exists [R-0356].
**Built this session, on the box:** droplet familydiagram-app, id 601097408, at 209.38.135.250
in sfo3, 2 vCPU and 2 GB, Ubuntu 24.04, backups and monitoring on, tagged familydiagram-app,
reached with the turin ssh key. Docker, sops 3.9.4 and age 1.2.1 installed; the firewall passes
22, 80 and 443 only. The box's own age public key was added to the encryption rules and every
encrypted file re-encrypted for it. The repo is cloned at /var/www/btcopilot. Secrets live in
/etc/fd/secrets.env, owned by root at mode 600, with a generated database password and Flask
secret, the site address https://familydiagram.com, and the image tag pinned; every compose
command on the box passes `--env-file /etc/fd/secrets.env`. All five containers are up — the
web app, the worker, Postgres, Redis and Caddy — after a fix to the compose file where a
service's own environment block was replacing the shared one. The Caddyfile serves
familydiagram.com: /app redirects to /personal/ until the mount is renamed, the app and review
paths are proxied, the desktop app's four update feeds are served from the repo, and everything
else redirects to alaskafamilysystems.com/family-diagram, with www redirecting to the bare name.
**Deployment moved out of fdserver:** Patrick closed fdserver PR #30 unmerged. The compose file,
Caddyfile, secrets template, runbook, release workflow and the four update feeds are
`deploy/chat/` in this repo. The root CLAUDE.md was edited once on his word to say so.
**Picked up later the same day, on his grant of DNS and production access [R-0357]:** the
admin commands could not find the Flask app inside the container, so the compose file now
sets the app path for every service; the worker was unhealthy only because it inherited the
image's web healthcheck, so it now pings celery instead. The migration chain failed on
Postgres from empty: the generated revision created tables in alphabetical order and Postgres
refuses a foreign key to a table that does not exist yet, which SQLite, where the chain was
tested, does not. The revision was rewritten in dependency order with the two cycles
(users↔diagrams, discussions↔speakers) closed by four keys added after the tables; proven on a
scratch Postgres database on the box, then run for real: the database is at the head revision
with all 23 tables. His invite was minted (valid to 2026-09-30). The root and www records of
familydiagram.com were changed to 209.38.135.250 at TTL 300. Copying the four real secret
values (Anthropic and AssemblyAI keys from his local environment, the Brevo mail login from the
old box's compose file) into the box's secrets file was refused twice by the permission
classifier as credential movement, so that step is his.
**Open:** (1) [waiting] four keys are still REPLACE_ME in /etc/fd/secrets.env — Anthropic,
AssemblyAI, and the Brevo mail username and password. Until Patrick puts them there the coach
does not answer and no sign-in mail is sent; his invite link works without mail. (2) [verify]
Caddy's certificate for familydiagram.com and www after DNS propagates, then his sign-in
through the invite and one chat turn. (3) [build] the fixed migration is committed on the branch
but the running image predates it; the file was copied into the running container by hand, so
the next image from CI carries it and nothing on the box depends on the hand copy.
(4) [ruling] rename the app's mount from /personal to /app — about 13 places in the web sources
and 70 in Python and tests — so the address bar and the sign-in links read familydiagram.com/app
rather than the Caddy redirect standing in for it. Asked, not answered. (5) [build] rotate every secret in the committed compose file, which still holds live keys and a
TLS private key in git history — he issues the new credentials. (6) [build] freeze the old
droplet for Pro. (7) [build] money through Stripe: account, keys and the price, after the first
bill [R-0354]. (8) [build] archive the fdserver repo once nothing refers to it. (9) [verify]
production still has no automated database backup.
**Note for the next session:** the permission classifier refuses a sub-agent both `sops
updatekeys`, because it writes the secret store, and `docker compose pull` and `up` on the box,
because that is a production deploy. Those two ran at the top level on Patrick's direct grant.
Production reads on the box are refused to sub-agents too.
**Lives in:** deploy/chat/ (compose, Caddyfile, secrets template, README, the release workflow
and the four appcast feeds); doc/chat-first/PLATFORM_BUILD.md; doc/chat-first/DATADOG.md;
private/prompts/ and private/oracle/, encrypted; commits 974c29e, 1423f0a, eae997e.
**Next action:** he puts the four real values into /etc/fd/secrets.env on the box and restarts
the app and worker containers; then he opens his invite link at familydiagram.com and sends one
message to the coach. Then rename the mount to /app (open item 4) so the address reads as ruled.
**Updated:** 2026-09-16, second session.

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
**Lives in:** doc/chat-first/SCOUT.md (the ledger and the counts);
.claude/skills/scout/SKILL.md; .claude/skills/loop-review/SKILL.md; the two disabled cloud
routines.
**Next action:** connect the Chrome extension, then the next flush after a walk runs the scout.
**Updated:** 2026-09-15.
