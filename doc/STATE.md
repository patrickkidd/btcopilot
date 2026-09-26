# Chat-first rebuild — STATE (the system of record)

**FD-362 is this project's epic and single source of truth at product altitude; this
branch is the corpus. Process rules: [HOW_THIS_PROJECT_WORKS.md](HOW_THIS_PROJECT_WORKS.md).**

Read this first, every session. This is the current truth; the derivation lives in
[HISTORY.md](HISTORY.md). Both are living documents under the two-clocks regime:
**append to HISTORY, revise STATE** as part of any work that changes either.
Ten-minute read by design.

## The product (ruled)

**"A coach who never forgets your family."** You talk to it (voice or text) the way
you'd talk to someone trained in Bowen theory; it asks what a trained coach asks; the
family record — structure + timeline — is its visible, touchable memory, growing for
years. Conversation drives everything, AND manual tweaking stays: chat tool calls
control everything in the app with full bidirectional reactivity (oracle R-0055).
One picture rides pinned above the chat:
strip-small at rest, cartoon-level detail, always current. Chat is the event clock
(never rewritten); the record is the state clock (corrections change it). Proactive
messages exist and default to near zero. The product's acceptance test is the felt
shift — one or two brain-rearranging correlations per user, not a dataset. Coverage
serves exactly two things: better coach questions, and the timeline's own
correlations.

No modes: one agent; coaching, app-help (manual tool), corrections, and journaling
are registers routed from context, never user-visible switches. Lanes are queries
over the existing schema, not entities (a person-variable lane; a household lane =
pair-bond + members' events; "sleep" is a label from descriptions — symptom lanes are
untyped, a known limit). Lane choice: the coach aims lanes as part of its reply;
the strip resumes where it left off; proactive messages carry their lanes; user pins
outrank everything. Within-lane density merges to worded count chips at scale.

All drawing/asking rules are canonical in [../DRAWABILITY.md](DRAWABILITY.md)
(five drawability rules; one amber question treatment in three places; cartoon rule;
at-rest vocabulary = line, dots, question mark; words-on-tap; no legends; no
lane-filter UI; expanded view must be designed for sparse data; tokens-only styling
so themes are A/B-testable with stable semantics: teal=data, amber=asking).

**The human oracle binds all agentic development** (his ruling: among the most
valuable inputs to the entire process — canonicalized and continually maintained).
The ENTIRE store (his BKM SPEC + rulings index + evidence) is IP and lives in the
PRIVATE fdserver repo at doc/oracle/; public docs cite ruling ids ([Oracle: R-NNNN])
and never restate quotes. Ops: append/merge/split/reword; SUPERSEDED chains (newest
wins); the initial mined set (R-0001..R-0064) awaits his feature-grouped
ratification pass (SPEC §10); no raw transcripts anywhere (R-0064). Core of it: this data is far more nuanced than it looks; no rubric
or quality judgment is inferred without Patrick — he rules by example and by
correcting proposed values; scaffold vs active events (early births are age
scaffolding, not SARF material; the diagnostic period starts at the first event with
a nodal flag or variable value); max-effort model spend only on the filtered corpus.

## Architecture and stack (ruled, unbuilt except FD-360)

Keep the Flask/Celery/Postgres/Redis backend. Target shape: diagram = JSON document +
append-only command log; one Python module mutates; browser and agent are clients of
the same endpoint; agent loop in a worker streaming via Redis→SSE (async worker;
agent queue separate from long extractions); server sends patches, client has a small
reducer for optimistic drags; per-turn undo with compare-and-set inverses. Front end:
one Vite/TypeScript SVG page, phone+desktop, installed as a PWA (no Xcode, no store;
Capacitor only if store presence / locked-screen recording / hostile-Apple forces it —
a packaging step, not a rewrite). Release: PR checks → tag → one Docker image (web
bundle inside) → GHCR → one SSH compose pull. Login: passwordless (pre-authed QR/link
onboarding, months-long sessions, passkeys/Face ID, 6-digit emailed code recovery;
login IS signup for later self-serve). Migration from Pro pickles: one-shot converter,
gate = positions exact + count differences explained. Known debt to schedule: secrets
committed in compose need rotation. The record format and the change log are settled
below in [Architecture and data](#architecture-and-data-ruled-2026-09-07), which
supersedes the old hard-cutover plan.

## Where the build stands (live — revise, do not append)

**PR #136 (branch `FD-362`) is merged to master; the fast-follow is branch `FD-363`, one batch
PR [R-0484]. fdserver is out of this work (2026-09-16):**
the prompts and the rulings are encrypted files in this repo, the new box's deployment is
`deploy/` here, and Patrick closed fdserver PR #30 unmerged. Nothing the chat app runs
reads from fdserver. The beta build is real code against the real database, not a throwaway.

**2026-09-16 — the overnight build, then the box.** Overnight, on his word to build whatever
needs no input from him: the chat database boundary (tests build only the chat chain's tables;
the coder's notes table joins the chain; a session with content deletes); the image with prompts
and sops inside and the migration chain runnable on a box; continuous integration green on the
runner with Linux goldens; the sandbox walks and golden specs rewritten to the rulings; three
defects they found fixed. Then, on his confirmation, a box: droplet familydiagram-app at
209.38.135.250 in sfo3, two processors and 2 GB, Ubuntu 24.04, backups and monitoring on,
firewall open on 22, 80 and 443 only, the repo cloned at /var/www/btcopilot, secrets in a
root-owned /etc/fd/secrets.env that every compose command passes, and the box's own encryption
key added so it can read the encrypted prompts and rulings. All five containers run — the web
app, the worker, Postgres, Redis and Caddy — and the Caddyfile serves familydiagram.com with
/app redirecting to /personal/ until the mount is renamed, everything else redirecting to
alaskafamilysystems.com/family-diagram [R-0356].

**Later on 2026-09-16, on his grant of DNS and production access [R-0357].** The migration
chain failed on Postgres because the generated revision created tables alphabetically and
Postgres refuses a foreign key to a table that does not exist yet (SQLite, where it was tested,
does not); rewritten in dependency order, proven on a scratch database on the box, then run for
real: the database is at the head revision and his invite is minted, valid to 2026-09-30. The
compose file now sets the Flask app path so the admin commands resolve, and the worker's
healthcheck pings celery, so all five containers are healthy. The root and www records of
familydiagram.com were pointed at 209.38.135.250 at TTL 300.

**Verified after DNS propagated (about 35 minutes; DigitalOcean's edge served the old record
until its one-hour TTL ran out):** Caddy holds the certificate; https://familydiagram.com/app
redirects to the app, www redirects to the bare name, the update feeds serve, and everything
else redirects to the old site. The first invite was consumed by the verification request
itself, which created his account; a second invite was minted and left untouched.

**Then, on his word that R-0356 already covered it:** the app's mount was renamed from /personal
to /app across code, tests, web and Caddy (48 files, 576 tests green), a branch image built by
the release workflow on dispatch, pulled onto the box, and Caddy recreated (a single-file bind
mount keeps the old inode after the file is replaced, so a reload is not enough). The app
answers at https://familydiagram.com/app; /personal now redirects to the old site like every
other path. A third invite was minted under /app. Known wart: the sign-in redirect's `next`
carries http, not https, because Flask does not read the proxy's scheme header; harmless
because Caddy upgrades http, but a ProxyFix belongs in the app.

**2026-09-20 to 22 — the app is live and Patrick has used it.** He signed in through his invite
link, put the service keys on the box himself, and chatted with the coach from his phone. His
first message threw an error, and six more faults sat behind it, each hidden by the last: the
twelve shared prompt fragments were never re-encrypted for the box's key; the private text
giving the tools' parameters their meaning was missing three entries the tools now require, which
the public default happened to have, so the tests passed; the image pulled a newer Anthropic
client library that drops an argument the app passes in six places; the installed package never
shipped the public prompt directory, so the one prompt defined only publicly was absent; and the
Gemini key that groups events into clusters had no home in the secrets template. All are fixed,
and a test now fails when any setting the app reads without a fallback has nowhere to come from
on the box.

Deploying changed with it. Dependencies are their own image layer, so a build takes minutes
rather than twelve, and every deploy keeps the old container answering until the new one is
healthy (106 probes during a roll, none failed). Production is where the beta iterates: a change
to the web pages is copied into the running container while the image rebuilds behind it.

**Later on 2026-09-22.** Observability left Datadog for Grafana Cloud Free, which costs nothing
and covers figures, logs, traces and browser sessions [R-0370]; no health information of any kind
reaches any of them. Every coach call now reads the fixed coaching text and the tool definitions
from the model's cache, and each step of a turn reuses the steps before it: measured live, a step
read about ten thousand words from cache and paid full price for a few hundred. Every call writes
a row saying who it was for, which model, how many words of each kind and what it cost. The
command line that runs the site previews and stops before anything that changes data unless told
to go ahead, and Patrick's own assistant reaches it over one pinned key. The invite mail has been
sent and received.

**2026-09-23.** Which events belong together is now the coach's judgement rather than a rule
about dates: it is handed the groups that already exist and keeps them unless the story gives it
a reason to change one, so the picture stops changing under him between messages [R-0371, R-0374].
A birth, marriage, divorce or death opens a chapter and the changes recorded around it are what
the chapter is about [R-0375]. Nothing is drawn to show what changed between readings; the coach
mentions it in ordinary words instead, and never uses a technical word for a group [R-0372,
R-0373]. The line now scrolls sideways a little — the recent years fill the width, the rest is one
swipe away, never more than two screens — and an opened group prints its real years [R-0381].
Event dots sit on the line at one height, always [R-0377], and the picture spot always shows a
picture rather than a list of words [R-0378].

**What the research says the picture should show (2026-09-23).** Two threads finished this
session and both are written up so they can be picked up cold. The literature thread read Family
Evaluation and the SARF sources and produced fourteen concepts for the picture spot, each tied to
the passage behind it, with the critic's verdict and Patrick's ruling on each:
[PICTURE_IDEAS.md](PICTURE_IDEAS.md). The phone-app thread read twenty-four small-screen data
views from shipped apps and mapped them onto the eight things this picture has to say, marking
which three his record can show today and which five need data it does not hold:
[MOBILE_VIEWS.md](MOBILE_VIEWS.md). Three of the five hybrids that came out of the mapping were
drawn on the app's own line; one survived, a single line of words above the picture, and it waits
on three of his decisions. The standing rule from both threads is that when a view cannot be
drawn until the record holds more, it is said plainly [R-0380].

**2026-09-23, later — the branch is the chat app and nothing else [R-0404].** The Pro backend,
the training app, the old migration chain, the old release workflow and the scratch folders are
deleted from this branch; master-legacy keeps them for long-term support, and the deletion is in
PR #136 rather than a new repository because the rebuild is one unit of work. What the chat app
keeps moved out from under the old names: the user, diagram and licence tables, and the matching
code the coders' review app also uses. The coach now speaks through Opus 5.5 [R-0405]: thinking
is always on there, so temperature is gone and effort is the control, set to medium for a coach
turn and high for extraction; the reply budget grew so thinking fits inside it; the model's
thinking blocks are echoed back through a turn's tool steps; and a refused turn now fails
naming its category instead of arriving as empty words. A live turn with three tool steps cost
about three cents. Session replay is on in Grafana with every element masked [R-0406]. Sub-agents
run on Opus 5.5 [R-0408]. After Patrick reviews this pull request toward merge, beta work
proceeds in small fast-follow pull requests [R-0407].

**2026-09-23, the review round.** Patrick reviewed PR #136 and ruled, one item at a time. The
coach: a refused turn is never a dead end — it falls back to Opus 5, then Opus 4.8, every hop
logged with its category, and only a whole-chain refusal shows one sentence in the coach's voice
with no retry [R-0409, R-0410]; the tool-call cap is twenty and hitting it is logged [R-0411]; what
a regroup says goes into the tool answer so the model keeps its reasoning and the cached prefix
holds [R-0412]. The repo: the extraction pipeline and the pending data pool are gone [R-0414];
names are canonical, one app, with the migration chain squashed to one migration and the box
stamped on deploy [R-0417]; the version is 3.YYYY.M.D.N+g<sha>, stamped by the release workflow,
which now builds, tags and deploys [R-0419]; bin/ holds only what runs; the old-diagram reader
stays as the import-later path [R-0422]; the auto-arrange code is gone with its analysis naming the
commit that held it [R-0418]. The corpus: the chat-first folder is the top-level docs folder,
old-state documents are archived with dated headers, the screen images and two unused skills are
deleted [R-0420]; the inter-rater meetings' de-identified findings are public in doc/irr [R-0413].
Tests: every test cites its ruling id or says "no ruling", checked by a test; screenshot goldens
are down to nine phone pictures, everything else gated by words and geometry, desktop out of the
gate [R-0416, R-0421]. His prompt review is a published sheet with 22 gaps and 4 contradictions
to rule on. The private prompts and the rulings store now also exist decrypted in the corpus
folder outside every repo, by his hand, because agents are refused the decrypt.

**2026-09-23, evening — the prompt fidelity round.** A claim-by-claim audit traced every old
extraction-prompt claim into the coach prompts: most survived, but worked examples, value mappings
and the machinery the rules assume had been lost in a one-commit rewrite of 09-10 that never
read the one-block prompt, and nothing from the IRR meetings had reached any prompt. Patrick
ruled the open points [R-0424 to R-0442]: the symptom interference test, a diagnosis as symptom up
on the diagnosed person, the coach infers and the user corrects, functioning in the spec's
wording, the worked examples as he coded them, projection coded without asking, replies end in a
question while the family evaluation's minimum data has gaps, notes on events with detail folded
in, a re-mention folded into the existing event, ask before removing someone left off a list.
The coding-judgment questions stay open for the coders; each gap carries a best-guess rule worded
from the literature, judged by F1 after coding [R-0439, R-0519]; any change resting on last year's IRR
agreements comes to him first [R-0423]. Code: events carry notes; two same-day shifts with
different variables both land; the coach is told the speaker and today's date; omitted certainty
is unknown; a marriage sets the bond's flag; adoption invents no parent; end dates are carried;
one name per unnamed person. The second look returns in a fast-follow PR as a narrow independent
review at session end, shown as coaching, measured by replay against the IRR codes [R-0443,
R-0444]. The plain mirror of the private prompts lives in the private btcopilot-sources repo for
review links.

**2026-09-24 — PR #136 ready to merge.** CI is green with every oracle guard live: every
test cites a ruling that stands, every ruling has a citing test or a stated exception (TEST OWED
where the behaviour is not built, WAIVED where nothing observable could check it), ids are pinned
to their evidence, no ruling text sits outside the store [R-0447, R-0449, R-0451]. Uncited tests
were grounded from Patrick's own recorded words: 15 rulings mined with his quotes, the rest cited,
dead or ungrounded tests deleted; the unclear points are kept in the private corpus ledger. Known
defects the new tests found are strict expected failures listed in doc/KNOWN_DEFECTS.md, for the
fast-follow PRs, as is the session-end second look [R-0443].

**2026-09-24 to 26 — FD-363, the fast-follow, deployed.** Landed on branch FD-363 (draft PR #138)
and, after the gates below passed, deployed to production on 2026-09-25:
- **Every tool call stays on the thread.** A coach turn's tool calls are kept in the database
  when it ends, whether it finished, failed or was refused, so every session shows them after a
  reload [R-0478]. The coach is given its own earlier tool calls; an earlier read's answer is
  replaced by a line telling it to read again. A migration fills this in for old turns from the
  change log and marks turns that never answered as unfinished.
- **A failed turn is picked up, not redone.** Its edits stay and are tied to the words that asked
  for them. Trying again resumes the same turn with its own tool calls and stores no new words;
  only the last message can be tried again, and only when its turn failed [R-0477]. The user's
  words are stored before the turn runs, not with the reply.
- **Record versions.** Every read ends with the record version, and every change to something
  already in the record names the version it was based on. A change made after another writer's
  write is refused, and the coach reads again [R-0480].
- **A map instead of the whole record.** The prompt carries people with ids, birth and death
  years and event counts, pair bonds, clusters, events per decade and the version. The coach
  reads the rest through tools: events by id, by words or by notes, and a list of the newest
  changes. The public and private prompt wording tells it to look before it adds, change only
  what the story needs, name the version, and read again when refused [R-0479].
- **A check after every turn writes down likely mistakes and changes nothing.** It writes a row
  for a person with the same name and birth year as another, an event with the same kind, day
  and people as another, and an add made before any read in that turn. It looks only at what the
  turn touched. An admin command lists the rows; they seed regression evals [R-0481, R-0482].
  Three live eval cases — a retry after a failure, an event said again, a read before asking —
  are scored on zero repeats and run only with a key.
- **The page** draws the stored tool lines on every coach reply, reads included as plain lines,
  and show calls too ("Showed a triangle"). An event's date on a tool line reads as the record
  list says it ("Jun 1994"). A failed last turn shows the lines that landed and [try again],
  which resumes that turn rather than sending the words again.
- **Hand edits of events write a change row.** Adding, editing or deleting an event on the page
  now goes through the coach's write path, marked as the user, so undo and the recent-changes
  read see it; people and pair bonds already did. Known behaviour that follows: a hand edit must
  pass the same record rules as the coach, so some edits the page used to accept are refused
  (for example a noted event with no words); deleting an event by hand also removes the
  emotions it caused, as the coach's delete does. The editor now stops a shift with nothing
  moved before it can be saved. Any other refusal from the record reads in plain words, for
  example "The end date is before the start date.", and stays on screen until the user
  edits a field or closes the editor.
- **The old single-call chat path is deleted.** The chat runs only on the coach's tool loop. The
  old conversation-flow prompt, public and private, the one-shot ask path and the
  fixed-category intake engine are gone; the helpers other code used from them moved beside
  that code.
- **Open questions.** The coach keeps a question with a tool before it writes the reply that
  asks it; a question is never removed, only closed, and only the user dismisses it. The drawer's
  third tab, beside Events and People, lists the open questions the coach has asked, in two
  sections, "Food for thought" and "Facts to find"; declined ones, dead ends and questions held
  back never reach the page. A tap puts the question into the message box; swipe left to
  dismiss. The map lists open and declined questions so the coach does not ask a declined one
  again. Removing what a question is about lets it go. Past sessions were backfilled once.
- **The migration gate** is a script that restores a Postgres dump into a throwaway container,
  runs the migrations, and checks row counts, orphans and tool lines per coach reply. Deleting a
  session now keeps the edits its words made: the links from change rows and turn records to
  those words are emptied instead of the delete failing on Postgres.

**Before the deploy, the gates passed:** the migration ran clean against a copy of the production
database; the pages were checked at phone and desktop sizes; three full live coach runs gave zero
empty replies across 75 turns; and the one-off backfill ran against a copy of the production
database, with a second run against that same copy making no calls and writing nothing. The build
is now live: commit ec757d5, image 3.2026.9.25.2-gec757d5, the database migrated to 1b00000000ad
before the rollout, with a backup taken first. That migration cannot be undone, so a rollback
from here means rolling forward, not reverting. The one-off backfill then ran for real on the box,
over 3 families, 3 model calls each; Patrick's own family got 4 questions, all facts to find, and
he still has to judge whether that is the right number.

The sandbox also makes real model calls on its own: a real coach turn and a real [try again]
were run there. The live eval cases and the tests that need a key have not run.

**Landed after the first deploy, deployed 2026-09-26.** In plain words: every
tool line in the thread now names an event or person by the one shared label everywhere, kept
events included, and touch targets were widened so a crowded dot can be tapped on a phone. The
list button sits at chip height, with more room after tool lines in the thread, and the
picture's back and close glyphs now line up with the ask button. A tap on a chip and a tap on
an event's dot are the same behaviour, with a per-user switch in admin back to the old,
separate behaviour. Speaking a reply out loud now works on iPhone. Adding an event or changing
a date is refused unless its certainty is given. The events list explains why an event has no
cluster instead of grouping it wrong silently. A command installs a stand-in test record for
review. The coach can raise, close and read impressions in the same way it handles open
questions, shown to the user in the drawer with what each rests on and two ways to push back.
The live suite now counts its own spend, stops at its hard caps, and keeps a results row per
run. A local model can stand in for Anthropic and Gemini, so the sandbox runs free by default.
The paid suite holds behaviour evals only; the clinical-coding cases wait for ground truth from
the IRR review group. Every test path spends the testing key; the box runs on the new
production key, and the old key is off it.

**Deployed 2026-09-26 00:25 UTC.** Everything above is live: commit 1faeeaa, image
3.2026.9.25.4-g1faeeaa, the database at 1b00000000ae (which, like 1b00000000ad, only rolls
forward), a backup taken first. The behaviour evals on the real model: 10 passed, 1 failed, the
failure being the private scribe prompt missing the word "provisional" on its fallback coding
rules, which fails on master too; that marker was never Patrick's ruling, so the marker and its
two checks were removed on 2026-09-25 [R-0519]. The impressions backfill ran over three families. No real coach
turn has run on this build yet, because the permission checks block a sign-in link for the test
account; Patrick's next message is the first. Real spend is asked for first.

Open:
- The new tests cite the nearest already-numbered ruling instead of a real id, because the
  oracle spec forbids a pending-ruling marker. Four spend tests, the case proving a question is
  stored before the reply, and the tests behind R-0479 and R-0482 in Patrick's store all need
  re-citing once he appends the ruling.
- Three rulings were skipped as needing a design rather than built: R-0187; R-0213, R-0376 and
  R-0378 together; R-0122 and R-0127 together.
- The count of guess-dated events is blocked by the personal-data safety check and is not built.
- An old kept tool call that changes an existing event still keeps that event's old words
  instead of writing the new ones.

**Rulings appended to the store 2026-09-25: R-0477 to R-0518.** R-0477 to R-0485 are the
previous session's; R-0486 to R-0518 are this session's, each with his words in the evidence
file. Deploy and testing: R-0486, R-0487, R-0488, R-0506. The coach and the record: R-0489
(narrows R-0481), R-0490, R-0491, R-0492. From the coach tab: R-0493, R-0495 to R-0497, R-0504,
R-0505. The picture and the thread: R-0498 to R-0503. Spend and evals: R-0507 to R-0511 (R-0510
rescinds the over- and under-functioning parts of R-0433; R-0511 marks R-0428 and R-0057
undecided; neither status is changed in the store yet). How sessions run: R-0494, R-0512 to
R-0516, R-0518. The learning loop: R-0517. R-0498 conflicts with R-0457 on naming people in
event titles; R-0457 still stands in the store until Patrick says to supersede it.
Five candidates still need his yes before they get ids, listed in RULINGS_TO_APPEND_2026-09-25.md
in the private corpus folder: date certainty on added dates; held questions never shown and the
drawer's width and title; when "Partly" counts; "Doesn't fit" as a chip; the empty tab's words.

Still true after the deploys: production's title bar reads "Free Diagram" instead
of the diagram's real name, and four live coach cases fail the same way on the master branch.
**What is not true yet on the box.** The dashboards and the cost rows are built but not deployed:
that waits on Patrick putting the Grafana token there and refreshing the dependency lock. There is
no automated database backup. Nine scratch accounts with chats, made while proving deploys, sit in
the live database, filtered out of the dashboards and waiting on his word to delete or keep; from
now on checks run against the development server on his Mac, never the live site. Every secret in
the committed compose file still needs rotating.

**Ruled 2026-09-16.** The beta starts from empty records, invited by email, with no import at
cutover and a per-diagram import later [R-0355], which he agreed to only once a test proved the
old diagram format maps onto the record field for field, relationship sub-fields included (page
"Old Record, New Record"). Claude creates the droplet and changes DNS only on his explicit
confirmation, each time [R-0353]. Pricing waits for the first $20–40 bill [R-0354].

**What the Personal app does today.** A signed-in person chats with the coach. The coach
answers and calls tools that add, change and remove people, pair-bonds, events, variable
shifts and clusters; each edit is named in the thread in its own formatting, and the picture
and the lists change as the reply lands. One picture rides pinned above the chat in a fixed
132px region, with three levels: clusters over time at rest, one cluster open on a tap, and a
moves board for a play-by-play. A lower level slides in from the right as a card over the
level it came from, and back reverses it. The grey line above the picture is the title of the
level you are on, with a back arrow beside it; tapping either goes up one level. Under the
picture, one chip row — ask, explain, in chat, and the list button — reads the same however
the level was reached. The back arrow inside an open cluster always closes the cluster [R-0362],
and the amber question mark is hidden for now, both on an empty line and past the end for
undated facts [R-0359]. The list button opens one drawer with Events and People tabs, each row
opening an editor with 44px fields; a person's birth and death jump to those events and back.
A sessions sheet holds past sessions with rename and sort. The account page slides over the
content. Sign-in is passwordless from an emailed invite link and lasts 180 days. A send that
fails says which of three things happened and offers to go again. Three dots show while the
coach is thinking, and the coach's words and tool steps show up live as the coach
produces them: this keeps going on the server on its own, so leaving the page and coming
back, or switching apps and returning, just reconnects to wherever the reply currently
stands [R-0369]. Before anything else the coach asks for first name, last name and
birth date, because without a birth date it turns an age into a year it invented [R-0360]. It no
longer holds out answers to tap; people type their own words [R-0361], and its closing question
stays amber [R-0358]. Return starts a new line and only the send button sends [R-0368]. With the
speaking preference on, the phone's own voice reads each reply as it arrives. A wide window, a
phone turned on its side included, gives anyone the wider layout with the list beside the chat
[R-0367]. Ordinary notable events carry a "noted" kind — one person, words that must be there, an
optional place and date — and "moved" has left the kind list; a noted event changes nothing about
the family but raises the question of order beside a shift [R-0363, R-0364, R-0366]. Every word
the app says is selectable and copyable. Users see the name
"Family Diagram" everywhere; "Personal app" is the internal name only.

**Patrick reviewed it on his phone over four rounds, 2026-09-08 and 09**, and his word at
the end of round 4 was that it is ready for him to start using like an app on the phone from
the home screen. Every finding, round by round, with the commit that fixed it:
[REVIEW_LOG.md](REVIEW_LOG.md), 66 rows. Rounds 1–4 are folded into the oracle store as
R-0165..R-0228.

**Built 2026-09-12 to 14 on the same branch, unreviewed by Patrick.** Three things happened
after the overnight review-loop build was walked. First, most of what he found walking it was
the words, and they are all renamed in the screens, the code and the walk document: "on the
agenda" rather than "on the table" [R-0308], a "decision" rather than a "settle" [R-0309],
"coding guidelines" rather than codebook [R-0310], an "opinion" rather than a "take" [R-0315],
and no placeholder titles [R-0318]. With them came ruled behaviour, all built: only the auditor
role sees the task card, the ballot and the meeting, and a professional signs in to their chat
[R-0311]; an unresolved event never returns to a later meeting and the agenda box holds only
flagged rules [R-0312]; the eleven-second wait on ratify is accepted [R-0313]; the meeting
header is one title, a labelled figures line, a colour legend, the wire, the sort control and
the list, sorted by divergence or by time, with agreed events readable, every wire dot tappable,
an agreed event opening on a tap of its row, and the room selecting which version to keep on a
split [R-0316, R-0317, R-0319, R-0320, R-0321].

Second, he stopped the testing and had people and family structure designed pixel by pixel
before anything else was built [R-0322], added to the flow already decided rather than
re-conceiving it [R-0323]. A conventions sheet was taken from the desktop app's own drawing
code, a gallery of hostile cases was drawn by the real renderer, and twelve drawing rules came
out of it [R-0324, R-0325]; two of them reach past drawing, because a missing or unnamed parent
or partner is now added as a generically named person ("Sarah's father") so the bond can exist,
and a child whose parents are not on the record stands alone. Structure then reached the app:
pair-bonds and who somebody is born to through the coach and the scribe, the record refusing a
bond that cannot exist and naming a missing parent, people matched by where they stand with the
room told when the match is unsure, the person editor carrying "born to" and every pair-bond one
per other person, the ballot showing a family fragment per version, and structure items off the
meeting wire and counted in the legend [R-0326]. The people list stays as it is, name alone.

Third, the platform work was built and proved locally: every prompt is one encrypted file with
shared fragments rather than a Python constant in a second repo, the oracle rulings moved here
encrypted too, files naming real people left every repo, the chat app took its own migration
chain and its own database from empty with its own accounts [R-0327], the importer of the old
Pro users and diagrams was written and dry-run, and the site is run from a command line whose
skill file it generates from its own declarations. The chat app's tests are their own suite
under `btcopilot/tests`, run by `bin/t` filtered to what changed [R-0331, R-0332]; they
measure at 89 back-end tests in 6.4 seconds and 113 front-end in 1.9
(doc/TEST_STRATEGY.md), and are not worth optimising. The deterministic walks moved
out of the sandbox into `web/tests/walks/` and fold into the goldens' harness.

An independent agent that read no builder's report then walked every screen a browser can
drive, in Chromium and WebKit at 393x852 and Chromium at 1280x800, against the chat app's own
database: 683 checks, 671 passed (doc/archive/2026-09-VERIFY_2026-09-14.md). One failure was a real
mismatch with the written spec — a second faint line under a name in the people list — one was
a ruled behaviour the gate misread, and ten were walk-script artefacts. The list is the name
alone again, and a year the coder gave only as a year reads back as the year.

**Patrick walked sections one to six himself, 14 and 15 September.** The walk is
doc/archive/2026-09-TEST_2026-09-14.md — the whole app by hand in dependency order, nine sections,
four reusable sign-in links; the walk of 12 September is archived. A separate agent then went
through every step of sections six to nine itself in a real browser, using the same test
accounts, and fixed any step that did not match the actual screen — now the standard before
any walk reaches him [R-0343]. **He walked seven, eight and nine on 15 September** and said it is all fine
for now; what he found is rows 114–132 of the review log and rulings R-0347..R-0352, all built
except row 124 (deleting a session with content fails on the chat database, an isolation
question) and row 132 (the plan codes are the Pro app's; pricing and plans are not decided).

Ten rulings came out of his walk [R-0337..R-0346] and all but the last are built. Sessions are
never dropped fast, so he is not signed out mid-walk [R-0337]. Agents may keep editing the front
end while he walks [R-0338]. On the ballot: no box round a selected family fragment, the
statement outlined in the transcript, "none" last in the relationship field, a prev button beside
next [R-0337]. On the meeting: a dot tap travels the list with an animated scroll; the title and
figures scroll away while the wire, its legend and the sort control stay at the top [R-0338,
R-0340]; structure cards are laid out like event cards [R-0338]; a tap on a version keeps it and
the kept version is stored on the item, so it lights on every later reading [R-0339]; version
rows carry initials only [R-0342]; a decided item keeps its seat and collapses in place [R-0341].
On the agenda: a filled button reading "run the meeting", and a ratified conversation offers its
result, ratified rows told apart by date [R-0341]. The result screen is reachable again from the
task card's done list and from the agenda, its summary scrolls under a title and one labelled
figures line, finished tasks look tappable, and a coach pass that was never coded is said in
words [R-0343, R-0344]. The list button opens the events and people list full screen over the
chat and the picture, and the person editor says "born to" with a mother and father picked by
name and "Partners" beneath, never "bond" [R-0345]. The one not built is R-0346 — only an admin
flags a ratified guideline or controls the agenda, the vote and the meeting, and the account
button shows its icon — which was in flight when the session stopped; nothing of it has landed
on the branch and one edit to the account button's mark is uncommitted in the worktree.
(R-0346 landed on 15 September, commit 8364eb4.)

**Two design questions are open and neither is decided.** doc/EVENT_MODEL.md, with its
page at https://claude.ai/code/artifact/d4dbc090-fbde-464c-bcdc-0cc31e1a5c53, writes down his
three complaints with the timeline shape the chat app inherited from the desktop app — a move is
filed as the couple's event and an ordinary event like finishing an apprenticeship has nowhere to
go, a birth is the mother's event with the child in a side field, and one actor field carries
four different role shapes — proposes a normalised shape, and ends in six questions for him,
including whether it changes now or after the beta. Nothing is built from it. A second page
compares a person's name written above the shape against below it:
https://claude.ai/code/artifact/2c391e04-6283-4590-b9ba-9e46910b5fab. Adoptive and foster
parents, possibly several on one person, he named as open rather than deciding [R-0345]. The
sandbox fixtures were repaired again so the screens read as a real case, on Lena's family and
the Ortega case.

**Built 2026-09-11/12 on the same branch:** the review's tables
(`review_cuts`, `review_codings`, `review_items`, `review_votes`, `review_rules`, one column
`discussions.kind`, the branch's `changes` and `interactions` renamed `diagram_changes` and
`diagram_interactions`) in an isolated package `btcopilot/review` with endpoints, the coach's
replay as a task and the export; and the coding screens — the one-task card, the read-only
thread up to the cut, the scribe on a cheap model with the record's tools, Done in the title
row with a confirmation, the guidelines behind (i). Review suite 32 passed (2026-09-11 night;
the personal suite was last recorded at 401 and not re-run tonight). Three rounds of
independent browser walks on fixture accounts found and closed four defects. The fourth, found
2026-09-11 night at phone and desktop size: when the record starts empty, the scribe lost the
event — its tool loop was capped at three steps, the cheap model spent them guessing a person
id, being refused, and adding two people, and the coder was shown "+ Marcus" as if it had
worked. The cap is eight now; a loop that still runs out answers with what it did write and the
screen re-reads the record; three prompt lines went in (ids only from the record or a tool
result; a relative named by relation is added under that relation, never "someone"; the coder's
date is kept at its precision). The re-walk on a fresh coder passed 74 of 75 checks on the
restarted sandbox; the one failing check is the Vite dev server's own hot-reload socket
(a console error on every page load in dev mode, not the app). The coding screen is ready for
Patrick's own test. The design
of every screen is ruled and drawn in `doc/mockups/` and the catalogue for beta
users; `doc/archive/2026-09-REVIEW_TABLES.html` is the database scope of the pull request.

**Built overnight 2026-09-12, unreviewed by Patrick:** the rest of the review loop and Pro —
his table, cut and vote-opening screens; the ballot; the meeting; the result; Pro's cases,
recording upload (through the training app's transcription path), notes and pinned desktop
drawer; the small items; and the clinical tool text moved back to fdserver behind an
overridable callable [R-0305]. An independent verifier ran 366 checks in Chromium and WebKit
at phone size and Chromium at desktop; the 24 failures were fixed at the cause; 9 checks
remain that are fixture or walk artefacts (VERIFY_2026-09-12.md). Suites: review and
personal 495 passed, web units 58 passed (the ten stale ones rewritten), type check clean.
Patrick's coding-screen eyeball on 2026-09-11 night: works; the bubbles were reshaped to his
pick (C6).

**His own record is small**: seven events, and one cluster he made himself holding two events.
It predates the three-event floor and is grandfathered; see Open issues.

**Review sandbox** (addresses use `turin`, never `turin.local`; the API is started with the ABSOLUTE database path; the sandbox's error mailer recipient is blank). Durable scripts live in `/Users/patrick/worktrees/fd362-sandbox/`, outside
every job directory on purpose: a database inside a job directory is deleted with the job, and
that has already cost one sandbox.

- `serve.sh 8890 beta3.db` — the Flask API from this worktree, bound to every interface, no
  reload, so a Python change needs a restart.
- `dev.sh` — the Vite dev server on 8891 proxying to 8890, host header forwarded so sign-in and
  cookies mint for 8891; the service worker is off. **Patrick reviews at
  https://turin:8891/personal/** and every saved front-end edit shows on refresh, no
  build. This is the dev mode he asked for [Oracle: R-0227]. A page already open on his
  phone reloads itself when a file is saved; that socket was refused for the host name
  `turin` (only `turin.local` was allowed) until 2026-09-11 night, so open pages never
  refreshed — allowed now. A home-screen app on iOS keeps its own cookies, separate from
  Safari: the first open inside it shows the sign-in page, and the email code signs it in
  once; an invite link opened from Mail signs in Safari, not the home-screen app.
- `invite.sh <email>` — a sign-in link at turin, not 127.0.0.1, so his phone can open it. A
  sandbox link is reusable: it signs that browser in as many times as you like until it
  expires, so a walk can be repeated. A phone already signed in needs no new invite.
- `env.sh` — the settings both scripts source. It no longer points at a second repo: the
  prompts are encrypted files in this one, read with the key at
  `/Users/patrick/worktrees/fd362-sandbox/keys/dev.agekey` (set `SOPS_AGE_KEY_FILE` to it).
  His own public key is beside it as `patrick-mac.pub`, so the same files decrypt on his Mac.
- `beta3.db` is the chat app's own database, on its own migration chain from empty, with its
  own accounts — nothing shared with Pro [R-0327]. It is never seeded blindly, never wiped,
  and backed up before any restart. `beta2.db` is the older shared-chain database, kept only
  for reference. Session history is kept across code changes [Oracle: R-0191].
- Mail is on, so sign-in codes and nudges send. It was off during the overnight walks.
- **On this Mac, open `https://127.0.0.1:8891/personal/`, not turin** — the name turin only
  resolves over the network, and with Tailscale off the Mac cannot look it up. On his phone,
  on his own wifi, turin works.

**Suites and continuous integration (2026-09-16 morning, first green on a runner).** The chat
suite is 572 passed and 25 skipped in 31 seconds, built on the chat chain's tables alone. The
whole backend ran green on the Ubuntu runner (1147 passed, 40 skipped) once the runner tests ran
from the checkout and the desktop-fixture round trips skipped without a desktop checkout. The
visual suite is 275 passed and 21 skipped on the runner, with its goldens recorded there by a
manual run of CI and committed to the branch; the specs were brought to the rulings by a builder
under an auditor. The Playwright sandbox walks pass at phone and desktop for the app, the table,
the ballot, the meeting and the meeting detail; the tap, scribe and structure walks skip on fixture
state. The release workflow builds the browser app into the wheel, ships sops and the encrypted
prompts in the image, and starts the image on an empty database to fetch the chat page.

**Found by Patrick testing alone, 2026-09-09 evening** (rows 67–69 of the review log): a
failed coach turn used to leave the user's words stored, so a retry stored them again. Since
2026-09-24 the words are stored before the turn runs, not with the reply, and trying again
resumes that same turn without storing them a second time [R-0477]; a second send while one is
in flight does nothing. One tap posted learning data with no item kind and is not yet identified. The coach in
the sandbox makes real model calls again as of 2026-09-24.

**Spec and gap.** UI_SPEC.md carries 444 value rows, 52 resolutions and 3 open items.
UI_GAP.md sets every one against the build: MET 318, PARTIAL 11, CHANGED 12, MISSING 5,
NEEDS-OWNER 13, UNCHECKED 16, N/A 76, over 451 rows. UI_GAP is hand-maintained now; its
generator is retired and must never be run again — it silently reverted other people's
corrections three times.

## Open issues

**The register of open topics is [TOPICS.md](TOPICS.md)** — one block per topic with its
decisions, open questions, where it lives and the next action, rewritten by `/two-clocks` at the
end of every session. The entries below are the older, longer form and are kept until each is
folded into its topic block.

Each entry below is a whole issue, readable on its own. The build is not blocked on any of
them except where an entry says so.

### Isolation and beta deployment

The Personal app shares a database, a process, a deploy and one migration chain with the Pro
desktop app and the Training app, and daily churn on the chat app can break either of them.
[ISOLATION_OPTIONS.md](archive/2026-09-ISOLATION_OPTIONS.md) maps what this branch touches — 249 files in
btcopilot, 29 of them shared with Pro, one with Training, one the public schema — and holds
the full detail behind everything in this entry. Patrick has parked the isolation
discussion itself until the prototype is done; the three blockers below are not parked,
because they are conditions on merging this branch at all.

**Three things must come out of the Pro app's path before this branch merges.**

1. Every Pro diagram is rewritten from pickle to JSON in place on its next save, through an
   encoder written for the chat app, with no migration step and no backup. A bug there
   silently damages the only copy of a Pro user's family diagram. Pro rows stay pickle until
   an explicit, backed-up migration; only chat-app rows are JSON.
2. The Pro save endpoint imports Personal code and writes a row to the Personal change table,
   so an exception there fails a desktop save. It comes out; the Personal package registers a
   hook instead.
3. The shared schema dropped the cluster pattern list and the pattern and dominant-variable
   fields, which the desktop app still reads. They are restored as tolerated fields the
   Personal app never writes. Standing rule from here: no symbol the desktop app reads
   changes without its desktop change in the same pull request.

**The isolation recommendation is A now, B later, never C.** A is a package boundary inside
btcopilot, where one adapter module is the only thing reaching Pro models and the shared
schema, held by a lint rule in continuous integration — one to two days, mechanical. B is a
second service with its own tables, which waits until the chat app's shape stops moving. C is
its own repository, which is the wrong trade while speed is the point.

**Deployment.** The shape is ruled: one Docker image with the web bundle inside it, pushed to
GHCR, pulled by one SSH compose command; passwordless invite links for the app working group
of three clinicians; the coaching prompts staying in the private fdserver repo and read
through a path in the environment. Verified 2026-09-09: btcopilot's release workflow builds a
wheel and an image and pushes it to GHCR on every push to master, and can also be started by
hand on any branch; fdserver's release workflow, on a push to its master, pulls that image on
the production host, brings the compose stack up and runs the migrations. The gap is that
**the image contains no browser app**: the bundle is written to a gitignored directory, the
Dockerfile has no Node step to build it, and `pyproject.toml` names package data for the
Training and Pro packages but not the Personal one, so even a built bundle is left out of the
wheel. Deploying today serves the API with no page. Three edits, one place each.

**Where the beta runs: ruled 2026-09-13, its own droplet (T-11 in TOPICS.md).** The chat app gets a new 2 GB DigitalOcean droplet with Caddy, secrets in sops with age, the DigitalOcean backup add-on, Datadog kept (superseded 2026-09-22: Grafana Cloud Free, R-0370, see PLATFORM_BUILD.md); the old droplet is frozen to serve Pro until Pro is sunset. Prompts and the oracle rulings move into btcopilot encrypted in place with sops, one `.prompty` file per prompt; files with real people in them stay in fdserver as an archive. Full evaluation: https://claude.ai/code/artifact/355dc50c-086b-417c-8cdb-4b10735cc9d8. The two shapes weighed before that ruling, kept for the record:
(a) a second compose stack beside production — its own Postgres, its own hostname, the
image built by hand from this branch under a branch tag — so the three clinicians use the
branch without it ever merging, Pro users share nothing with it, and the three pre-merge
blockers bind only the merge, which can wait until the app's shape settles; (b) merge first
and deploy on the production stack, which needs the three blockers and a green CI before
anyone outside sees it. Cost of (a): the three image edits, a branch-tagged image build, a
beta service pair in compose, an nginx server block and certificate, and a database
initialised by the migrations — one to two days.

**Continuous integration is failing on this branch**, for three understood reasons: two web
unit tests assert a reload event the turn handler no longer sends; every screenshot test
fails by construction, because the approved images are recorded on macOS while the runner is
Ubuntu and looks for images that were never recorded; and the spotlight selector now matches
two elements, so the tests using it error before comparing anything. Neither the backend nor
the visual suite has ever been watched green on a runner.

**Also true before other people's records are on a server**: the secrets committed in the
compose file need rotating.

### The coach writes the record without the clinical definitions

The agent loop is the innovation of the rewrite, and it is the only writer of events in
the chat app: the old batch extraction is not in its path. But the coach is handed no
definition of an event, a shift, a variable, a nodal event or a relationship move — the
agent prompt is the coaching voice plus tool rules, and the tool fields say one line each.
Everything that defines the data clinically lives only in the extraction prompts (the two
passes, the coding guide, the distinctions, the examples) and in rulings no prompt carries.
Patrick's direction [Oracle: R-0236]: put that knowledge into the loop so the coach knows
how and when to add, change and remove events by the clinical definitions. No data exists
yet on how well an agent loop does this; the only numbers are for single-call extraction.
Four ways in and the measurement to build beside them are laid out for his decision
(artifact "What the Coach Knows", 2026-09-09): definitions into the agent prompt, meanings
into the tool fields, the deterministic rules into the commit function, and a
reference-manual tool later; plus a replay harness that runs a conversation through the
loop and scores the record with the existing F1 code.

### Open with Patrick, 2026-09-10 (tracked here until each is closed)

1. **His review of the coach's new prompt section** — the 168 lines added to the private
   prompt file ("What goes in the record"), his clinical content rewritten for the loop. Diff:
   `git -C ~/theapp/fdserver/.claude/worktrees/FD-362 show HEAD -- prompts/private_prompts.py`.
   The author's account of what was dropped from the batch prompts is the newest entry in
   doc/PROMPT_ENGINEERING_LOG.md. Unreviewed; unmeasured until his conversations are coded.
2. **Deploy on the existing production server, merge first** [his direction 2026-09-10; superseded 2026-09-13 by the own-droplet ruling, T-11]: a
   read-only review of every table and endpoint change against master is being written to
   doc/archive/2026-09-MERGE_REVIEW.md; nothing merges before he has read it.
3. **Existing rows must work in the new app** — diagrams and discussions made on master
   (including colleagues' earlier sessions) load as sessions; old Personal app releases do
   not matter. Part of the merge review.
4. **Wipe and re-code as a feature** — clear a record's coding and re-run the agent loop
   over its existing conversation, the way the old training app cleared and re-extracted.
   Done once by hand on his sandbox record (2026-09-10) into a new session under the same
   record. Open question he raised: chips in the old thread point at events that no longer
   exist after a wipe; a chip carries its own words, so it reads as plain text, and the
   re-code can re-link the ones that match on kind, date and people.
5. **One app** [Oracle: R-0237] — coding as Pro features on desktop, training as
   auditor/admin features, one Vite page with features by licence, role and view. The coding
   page is drawn and tabled [R-0247]. The IRR review is a three-stage ground-truth process —
   blind coding of a conversation up to a cut Patrick selects, a blind human-only vote on a
   phone before the meeting, a ratifying meeting — approved as drawn 2026-09-11 [R-0250,
   R-0267, R-0268]; six decisions and the migration of last year's IRR material stay open in
   the topic register. No build until those land.
6. **Sub-agents are token- and model-optimised** — judgement on Opus, mechanics on Sonnet
   or Haiku, smallest file set each; a standing check on every spawn.

### The three-event floor and groupings the user makes himself

A cluster needs three events, one number in the schema enforced at the record's commit for
every writer including undo and the coach's own grouping tool. Patrick's own record holds a
two-event cluster he made himself, which predates the floor and is grandfathered. **His
decision:** does the floor bind a grouping the user made? If it does, that cluster gains an
event or is dropped. If it does not, user groupings are exempt and the write path needs a
second door.

### The nodal ring on a dot

**His decision:** keep it or drop it.

### Rule by example on clusters

The rules make the candidates and the model only names them and gives a reason. Patrick
ruled that the judgment calls linking events which are not adjacent in time cannot be written
as a rule yet and must wait for real examples he marks [Oracle: R-0193, R-0194]. Until he has
marked some, cluster quality on anyone else's record is unmeasured. This gates inviting beta
users, not the build.

### Thirteen interface rows where the build is defensibly different

[UI_GAP.md](archive/2026-09-UI_GAP.md) marks thirteen rows NEEDS-OWNER: the build differs from a value that
is a team default or an unruled call rather than from a ruling, so acting on the row without
asking would be guessing. Three of those no rule in the corpus reaches at all, and they are
stated with their alternatives at the foot of UI_SPEC.md: what "+" does on a family the app is
not currently on, how a close-up triangle is drawn, and how two moments are compared.

### The felt call on the board

Whether each move reads without a legend, and whether the coach's words and the drawings tell
the same story. Only Patrick can answer it, by playing a stretch through.

### The event editor's missing fields

The editor lacks the relationship field with its target and triangle lists, and the person,
spouse and child fields are not hidden by event kind the way the Pro app hides them. No
judgment is needed; it is unbuilt work.

### The desktop app and Android are unverified

Nobody has opened a chat-app record in the released Pro desktop app — journey 7 is deferred
on the auto-arrange evidence, which never met Patrick's approval. Nobody has opened the page
on an Android phone; there is no hardware, and the review log calls for an emulator check
before beta users.

### Rows still open in the review log

[REVIEW_LOG.md](REVIEW_LOG.md) carries the row-by-row record and rows are never deleted.
Reconciled 2026-09-09 against `git log` and later rows in the same log; every row this found
a commit or a later ruling for is now marked FIXED or RULED in place. Two rows are still
genuinely open, both already named above: row 54 (does the three-event cluster floor bind a
grouping Patrick made himself, see "The three-event floor and groupings the user makes
himself") and row 66 (isolating and deploying the Personal app, see "Isolation and beta
deployment").

## Prototyping status (honest)

- **FD-360 page** (PR #133, draft, worktree ~/theapp/btcopilot/.claude/worktrees/FD-360):
  works and independently verified — chat through the real coach pipeline;
  session-cookie auth bridged WITHOUT touching the HMAC path (tested); CSRF added;
  per-person timeline math with a regression test against the Qt app's
  mixed-people-sum bug; resting strip obeys the three-mark rule; tap-a-mark speaks a
  plain sentence; seeded or real-record sandbox on 8889 (relaunch command in the PR /
  worker report; real-record DB at /tmp/fd360-sandbox.db). **Ruled good, superseded 2026-09-02 by the
  sentence spotlight**: the narrow-lane always-on resting strip; inline chips in coach
  text aiming the picture.
  **Ruled not understood**: the expanded/detail view — Patrick's walk found it
  illegible on real sparse data; it is a placeholder pending ground-up design FROM
  the corpus analysis. Era-compression work exists reverted-but-recoverable at commit
  35dd13b — NOTE: that is one of the two contaminated commits, so a history purge
  deletes it (re-implement from HISTORY's description if purged).
  Rebuild/reseed: `python -m btcopilot.seed <username> --from-lanes
  <chat.json> <journal.json> --alias "WRITTEN=CANONICAL"...` (identities only ever in
  the ephemeral command); sandbox: from ~/theapp, `PYTHONPATH=<FD-360 worktree>
  FLASK_APP=btcopilot.app:create_app FLASK_CONFIG=development
  FLASK_SQLALCHEMY_DATABASE_URI=sqlite:////tmp/fd360-sandbox.db
  FLASK_AUTO_AUTH_USER=patrickkidd+unittest@gmail.com FDSERVER_PROMPTS_PATH=<fdserver
  private_prompts.py> uv run python -m flask run -p 8889 --no-reload`.
  Open judgment calls recorded on the ticket (deferred_risk): default second lane
  needs the coach-default/pin mechanism; ask-the-coach server queue unbuilt (chips
  prefill the chat input instead); relationship keyword→kind mapping; the chat
  "Assistant" person appears in lane data; unknown-certainty dated events route to
  the shelf; rule-5 fades/death hard-stops unimplemented. One Jira closing comment on
  FD-360 is pre-authorized but HELD until Patrick reviews the PR.
- **proto.html** (durable copy: ~/theapp/btcopilot-sources/fd-corpus/design/proto.html; jobs-tmp original is ephemeral): interactive two-concept prototype — REJECTED by Patrick,
  shelved. It embeds real names inside prod-derived event descriptions: NEVER publish
  or commit it; local file only. Its creative-round survivors (Chapter Shelf, Quiet Threads) and
  cross-cutting findings remain hypotheses only.
- Three artifacts stand as reference: Drawability, "Three Ways to Ask", "Flowing
  Through It" (URLs in HISTORY.md; readable any session via the Artifact tool's read action).

## The move language (RATIFIED 2026-09-01)

The visual vocabulary for the picture above the chat is ratified: ten relationship
moves + three variable shifts, one action-green, 8s felt animations on the field
vocabulary (rings = a person's emotional field; tremble = moved by it; wall +
field shadow = withdrawal; ghost-double + spikes = anxiety EVERYWHERE it appears;
F-up ≈ defined self; symptom = interim cross + up/down arrow). Rulings:
~/theapp/btcopilot-sources/fd-corpus/OWNER_RULINGS.md (2026-09-01). Reference HTML (durable):
~/theapp/btcopilot-sources/fd-corpus/design/move-language.html (ratified galleries) and drilldown.html
(three-level drill-down on two real records — KNOWN BUGGY; the rulings are the
standard, not the prototype). Three-level shape, REVISED 2026-09-03 by the UI
principle: wire with episode clusters → (the tap-zoom episode level is CUT; a tap is
point-and-ask) → moves step-by-step driven from the chat's play-by-play; words and
claims live in chat; loop engineering rules (all interactions collected). Next: build it on
FD-360 against his real record — brief in NEXT_SESSIONS.md.

On 2026-09-02 the picture design CONVERGED on the SENTENCE SPOTLIGHT — the coach's
latest message lights the events it names, the rest of the dots stay dim, and up to
three rows of words sit on the picture tied to their dots by leader lines (Oracle:
OWNER_RULINGS.md 2026-09-02; folder ~/theapp/btcopilot-sources/fd-corpus/design/crowded-chapter/).
This supersedes the FD-360 resting strip as the picture reference. The fidelity
standard for every front-end build from here on is: playbyplay_ab.html pane A,
move-language.html + OWNER_RULINGS.md, crowded-chapter/, and DRAWABILITY.md — each
build is checked against them with an approved-vs-built deviation table.

## The corpus (system of record for phases A and B)

Location **~/theapp/btcopilot-sources/fd-corpus/** (moved 2026-09-02 from ~/fd-corpus, symlink left behind; his ruling: everything load-bearing consolidates into the PRIVATE btcopilot-sources repo — supersedes the older never-in-a-repo rule for this data); rebuild everything with
`rebuild.py <diagrams-dir> <out-dir>` (self-verifying allowlist, no data inside it).
- `clinic/case_01..61.json` + `index.json`: his 61 real clinical cases, one-way
  anonymized (P-ids, gender, decimal years, unsure flags, kind enums, per-variable
  direction enums incl. differentiation, nodal flag, text byte-lengths; free text
  never extracted). Content-blind protocol holds until the Anthropic BAA exists.
- `design/`: his own record (corpus_patrick_chat/journal.json), prod-derived
  comparisons (corpus_304/9/1341/757.json), and `prod_candidates.csv` — 104 prod
  diagrams (email + id; floor = ≥40 dated events AND ≥20y span AND ≥5 people; his own
  excluded; UNRANKED; volume column explicitly "not quality"; caveat: nothing in prod
  marks clinic-derived diagrams, owner-exclusion was the only cross-contamination
  filter).
- `PRIVATE_case_mapping.md`: case_NN → his actual diagram file, HIS EYES ONLY,
  regenerated on the active basis.
- `QUALITY_NOTES.md`: volume ≠ quality, in writing. `OWNER_RULINGS.md`: his teachings.

Corpus facts (details in HISTORY). **Numbers rule: never trust counts written in
docs — ~/theapp/btcopilot-sources/fd-corpus/clinic/index.json is always authoritative; recompute before use.**
Computed from index.json 2026-09-01 10:44: events live in five homes; median dated-bearing case
28 dated events over ~85 years; direction tagging in 21% of his cases;
uncertainty right-skewed (median ~96% guessed); he dates marriages 2–3x more than the
prod population. Active-basis tiers: **11 cases ≥30 active, 13 at 10–29, 4 at 1–9
active (case_01/10/28/42 — NO in/out ruling yet, do not infer), 28 zero-active with
people (pure scaffold by the marker — possibly coding style; his eyeball decides),
5 blank.** Worst volume illusion currently case_13 (52 dated / 0 active).

**The active basis is itself a period measure, not a signal measure (computed
2026-09-01):** rebuild.py marks everything dated at or after the first marker-bearing
point as active, so the tiers rank the LENGTH of the diagnostic period, not how much
function he marked. Counting points that actually carry a nodal flag or a non-"none"
variable: only 6 cases have >=10, 15 have >=5, and 33 files have zero. The ranking
reorders against the active tiers (the #2 case by period has 13 marks, all bare nodal
flags with no variable value; two top-tier-by-period cases carry 3 marks each). Also:
**61 files are not 61 families** - two pairs are identical across every extracted
field (one pair inside each of the top two tiers, inflating both by one) and a third
pair shares people and nearly all events; **differentiation is never used anywhere**
(symptom most, then anxiety, then functioning, relationship rare); **every marked
point is dated** (no undated-shelf problem on the function side); marks are sparse
per person and clustered in time (densest case = 33 marks over 9 people / 30 years).

The corpus self-sorted into the two planned subsets: active-bearing → FUNCTION candidates;
zero-active-but-structure-rich → STRUCTURE candidates. **RULED 2026-09-01: no eyeball gate — the FUNCTION subset is simply the
marker-densest cases (case_29/41/03/40/48/61/50, the seven with >=9 annotated
points); phase A proceeds on them now. The four 1-9-active cases and the
zero-active question are moot for phase A.**

**PII rule (binding, FD-360 incident is the precedent-as-rule):** real user emails
(prod_candidates.csv), case filenames, prod identifiers, and any corpus values NEVER
appear in repo docs or commits; sessions reference cases as case_NN only.

A disposable Postgres container `fd-scratch-pg` (port 55432) holds the restored July
prod dump for any further prod queries; `docker rm -f fd-scratch-pg` when done.

## The main stream and the pinned branch (corrected 2026-09-03)

The corpus work (phases A and B above — filter → nature-of-the-data document →
model-optimized visual choices → build) was a **branch of the stream, not the main
stream**, and Patrick pinned it in favor of generating more data through chat. The main
stream landed on: **the minimum viable prototype as a mobile app so he can just chat.**
Governing principle (his words, 2026-09-03): **build the smallest and most powerful
simple UI that we can test and iterate on.** When he went to use the prototype he found
flaws in the demo that overlap with core architectural questions the original vision and
plan never addressed. The corpus, the FUNCTION/STRUCTURE-subset sessions and the
notability pipeline stay documented below as pinned threads; they are not the next step.
Model policy still holds: judgment on the big model; implementation to precise spec on
cheaper models; mechanics on the cheapest.

## The UI principle (RULED 2026-09-03 — step-back item 1)

**The picture never lets the user teach the coach directly.** Tapping anywhere on it is
routed into the chat as if the user had said it out loud; any tap that skips the chat
turns into its own separate feature with its own UI problems. The agent loop is the one
engine behind everything; chips and what a tap sends back are just its plumbing. [Oracle: R-0065]

- The picture stays plain: pack in as much as fits without feeling busy and without
  needing a tap to see everything; the wire timeline felt busy, which was a sign it was
  showing too much. Revealing a title with one tap is fine. [R-0066]
- The tap-zoom cluster view (level 2 of the three-level shape) is CUT: tapping a cluster
  is point-and-ask, and the cluster's words live in the chat via the play-by-play, never
  in a navigable data view. The move step-through (level 3) survives, driven from chat.
- One consistent visual mark says "this tap puts words in the chat"; anything without
  the mark never costs a turn. Users control both tokens and flow. [R-0068]

UI_SPEC.md (doc/) is the exhaustive canonical record of every
approved UI element — 441 rows, each with the exact value and its owner source.
UI_GAP.md is the live approved-vs-built table. Every front-end build works row by row
from UI_SPEC, and is verified against it — prose in this file never outranks UI_SPEC on
a UI question. 36 rows in UI_SPEC are marked "Needs Patrick's ruling" and are open.
- Manual editing isn't part of what's being tested. The first release only counts as done
  once the chat loop can make tool-call edits in real time (bringing back R-0055); before
  building, Patrick signs off on which features are in versus deferred. [R-0067]
- The prototype's full timeline + event editor stays as designed, behind a menu, off the
  main journey, with a one-line banner that editing by chat also works. [R-0069]
- A button that jumps straight to one whole, easy-to-follow idea is fine — whether it's
  actually easy to follow gets tested with users; stepping through single data points one
  at a time was turned down. [R-0071]
- Every feature has to produce data and corrections the team can learn from — folded into
  the first UI principle above. [R-0070]

Ruled 2026-09-07, closing every sub-ruling that was open here:

- **Chips are the primitive.** A chip points at something in the record — an event, a
  cluster, a person — and shows up in both the coach's and the user's messages. Tapping
  one puts that reference into the user's own message, which they then finish in their
  own words; sending just the reference alone means "tell me about this." Tapping a chip
  is the user talking as themselves, not directing the coach. [Oracle: R-0072]
- **Two taps on the picture.** A first tap just looks — it shows a title or caption and
  costs nothing. A second tap is a chip, and that one speaks. The chip is the one visual
  that means "this sends words to the chat"; nothing else uses up a turn. [R-0073]
- **The play-by-play is written by the coach, not the app.** The moves themselves are
  fixed data that animate the same way every time; the coach supplies the narration,
  choosing which moves to use and their order, turning each into a chip, but cannot make
  up a move that did not happen. It always finishes by offering chips. This beat having
  the app generate its own captions, compared side by side in a mockup. The tap-and-zoom
  view into a cluster was dropped. [R-0074]
- **The show tool.** Anything that needs no judgment becomes a tool call with fixed
  parameters. This tool takes ids from the record plus one of a closed list of view
  types — for now: a triangle across three people, a stretch of time, two moments side by
  side, or a sequence of moves. Every id has to point at real stored data or the call
  fails; accuracy to what the user actually said comes from how the tool is built, not
  from trusting the model. Any view type added later has to earn its place by showing
  something real; the list starts small and grows one view at a time. [R-0075]
- **Every tap is learning data**, including the looks that send nothing, and the coach sees
  them as context. First entry on the A/B-test list below. [R-0077]

## Architecture and data (RULED 2026-09-07)

What the record holds today, field by field with line references, is in
[SCHEMA_COMPARISON.md](archive/2026-09-SCHEMA_COMPARISON.md). This section is what was ruled on top of it.

- **Clusters are model-derived and stored**, which is what the data model already does. The
  model may group and name; it may never invent a member; the user corrects it. Triangle
  moves already live on the event, in the relationship field and its target and triangle
  lists. [Oracle: R-0076]
- **The record belongs to the client, not the clinician.** A clinician only gets access
  granted to them. The client pays for their own chat subscription and keeps the record
  both outside of and after any work with a human clinician. [R-0080]
- **Nothing is ruled about the Pro app.** Its role and its stack are both open; everything
  said about Pro this session was brainstorm input, and no irreversible decision about Pro
  is to be made. The chat app must not corner it. [R-0081] Proposed and unratified, held as
  an interim only: the Pro app can read a record made by the chat app, but only the chat
  app can write to it, until something exists to merge changes from more than one
  writer. [R-0082]
- **The record becomes pure JSON.** The stored diagram data column stops being a Python
  pickle; the Qt-specific values are written out as tagged plain types instead. When the
  currently released Pro app asks for the data, the server converts it back to a pickle on
  the fly, so Pro itself does not change. The format is open and statically typed, built on
  the existing structure to keep the migration path simple; Patrick decides himself when a
  better feature is worth breaking backward compatibility. [R-0083] Tested: an exact round
  trip on three test cases and on 1997 out of 1998 real diagrams — the one that failed never
  loaded correctly even before this change — and the converted data loads fine through
  Pro's own code. Converter at `btcopilot/diagramjson.py`, commit f32eb2c.
- **A change log next to the record.** A new database table, Change, sits alongside
  Discussion and Statement: one row for every command — a tool call, a save from Pro, or a
  hand edit — holding a list of what changed (item, kind, field, old value, new value).
  Rows group under a turn id, meaning one coach reply or one save. If the same item and
  field changes more than once in a row, only the first old value and the last new value
  are kept. Each row also carries who made it and in which session. The server processes
  commands one at a time, in arrival order, per diagram. Undoing a turn applies the
  opposite of each delta, checked against the old value still matching. The system has to
  support several readers and writers at once, and this log is kept apart from the record
  itself so old history can be trimmed later without touching the record. [R-0084]
- **New shapes, all additive.** Chip reference tokens live inside the statement text and are
  validated against the record on write. Coach statements gain a views field: a view kind
  plus its parameters, where every id must resolve. A new Interaction model records who
  looked, said, tapped a chip, or played, against which item and when. Cluster gains a name
  and a source, model or user. Pins are a list of references on the discussion. The rule
  behind all of it: what the picture draws lives in the record, and who did what when lives
  in tables beside it. [R-0085]
- **The beta build skips PDP entirely.** Whatever the coach edits gets applied right away
  as a change row; fixes happen by saying so in chat. This is being tried, not settled —
  Patrick's words were "let's play with no PDP". [R-0086]

## Beta build (RULED)

**This build is meant to go live, not get thrown away** — real sign-in without a password
and the real database, everything a beta user needs right now. [Oracle: R-0078]

Included: typing to chat, with the phone's own dictation standing in for voice; the chat
loop making tool calls that add, change, or remove people, pair-bonds, events, and
variable shifts, showing up live in both the picture and the list, and reversible just by
telling the coach; one picture pinned on screen showing clusters over time at rest,
pointed by the coach's chips; a play-by-play behind a button for each cluster; the
tap-to-look versus tap-to-speak pattern; chips that steer the conversation; a timeline and
event editor tucked behind a menu, with a note that chat can also make the same edits;
every tap, chip, correction, and coach edit gets logged; this is Patrick's own record.

Left out for later: messages the coach sends unprompted; a view showing which of the
user's own words something came from; pinning things to a lane; moving data to the Pro
app; importing what's notable; sharing with others; a full undo history beyond the current
turn; compressing long stretches of time; stopping the timeline at a death or fade point.

**First users** [R-0079]: the app working group, three clinicians, iterated with until the
thing is extremely valuable. Then the app seminar, three more. Then the wider Bowen
network. Names live only in the private oracle evidence.

**The journeys that check the build** [R-0087] — walked PASS 2026-09-08:

1. A first conversation from an emailed link, no password, the picture growing from nothing.
2. Fixing something by chatting about it updates that event directly, tracked as a change
   row, and chips made before the fix still work. [R-0087]
3. Tap a cluster, see its title, tap the chip, type, and the coach answers with a
   play-by-play that animates.
4. The coach draws a triangle with a chip and the user taps it to ask about it.
5. Return a week later: the coach resumes and the picture is where it was left.
6. The menu opens the timeline list with the event editor and the banner.

Journey 7, opening the record in the released Pro app, is **deferred** pending how
chat-generated family structure auto-arranges. The evidence: auto-arrange shipped in Pro on
2026-05-04 and the best recorded result was 885 px average error against Patrick's hand
layouts, 974 px today, with cross-family marriages and large extended families unsolved and
the Personal app not wired to it. No ruling of his ever called auto-arrange satisfactory.

**What was built against this.** The Vite/TypeScript page on the ruled front-end shape:
passwordless login, the real database, JSON diagram data through the converter, the Change and
Interaction models, tool calls, chips, the play-by-play, and the timeline and editor behind a
menu. Code in btcopilot, prompts in fdserver, both on branch FD-362. Journeys 1 through 6
walked PASS on 2026-09-08.

### Owner review rounds 1–4 (2026-09-08 and 09) — the standing rulings

Every finding row by row, with its commit: [REVIEW_LOG.md](REVIEW_LOG.md). All of it is in
the oracle store as R-0165..R-0228; what follows is only what constrains future work.

- **Only one thing can be selected at a time.** Tapping a chip and tapping a dot do the
  same thing: the dot lights up, and a caption row appears below it holding the ask chip,
  the board button, and the "in chat" chip. This row looks the same whether it is a whole
  cluster open or a single event inside one selected. [R-0168, R-0211]
- **Chips are one size, full text**, never truncated and never expandable. Labels are capped
  at the source at 28 grapheme clusters with one re-ask, never trimmed afterwards. Every chip
  has a pressed state.
- **The board fits its content.** This superseded the fixed 264px rows; every UI_SPEC row
  carrying RESOLVED #28 is superseded by it. Its control row is always back, explain, forward,
  with explain dead only while the coach is answering the last one. The way onto the board
  from the timeline is the play mark alone, no words.
- **Each move stays on screen until its narration finishes typing, plus about two more
  seconds.** A separate eight-second animation timer runs alongside but is never adjusted
  to match it [R-0171]. Tapping a step's chip moves the board forward and never jumps back
  to the timeline; the kind of statement (a play turn) and which cluster it belongs to are
  saved with it. [R-0170]
- **The words under the board are a person and their own words** — no count, no clinical
  term — in a block keeping two lines of room; the date is written once, under the dot.
  Nothing is drawn behind the move being played; the dot itself is drawn last, in action green.
- **Each line of what the coach did lights what it made** as that line lands: a moment through
  the picture's spotlight, a person on the figure wherever people are drawn.
- **The grey line above the picture is the current view's title**, with the back arrow beside
  it; tapping either goes up one level. Drilling in slides the lower view in from the right
  over the higher one, about 240ms, instant under reduced motion; the account page covers the
  content the same way.
- **An open cluster shows its name and its reason, never a list of its events** — a cluster
  can hold fifteen. Events stay dots; a tapped dot shows its words. At rest the band says
  "tap a cluster".
- **Blank ground puts the picture down.** Tapping empty space or the picture's own name
  deselects; a label picks its moment; tapping the label of the moment already picked jumps to
  where it was coded in the chat.
- **Everything the app says is selectable and copyable**; only controls carrying no prose are
  held back. Three dots show while the coach thinks, superseding the mockups' blinking caret,
  which stays on words being written out. Sign-in tokens last as long as the session.
- **Preserved on his word, do not remove**: the agent's tool-call summaries in the thread, and
  their formatting standing apart from the coach's reply. He likes them as they are.
- **The symptom arrow stands as tall as the health cross**, superseding the symbol sheet's 32.
  Every number is the sheet's halved because the board draws people at radius 13 where the
  sheet draws them at 17; the stroke is unscaled.
- **Cluster detection**: [CLUSTERS.md](CLUSTERS.md) — the rules make the candidates, the model
  only names them and gives a reason. The floor is three events, one number in the schema,
  enforced at the record's commit for every writer including undo and the coach's own grouping
  tool.
- **Invite links use `turin`**, never 127.0.0.1, so he can open them from his phone.

## A/B-test list

Kept for when there are enough users to run one.

1. Silent looks visible to the coach as context, versus recorded only. [Oracle: R-0077]

## Pending threads (designed, not landed)

- Coach elicitation upgrade: additive prompt edits (triangle/who-else questions,
  year-before probe, SARF-dimension rotation, done-rule criteria) await Patrick's
  clinical sign-off on the phrasings; the measurement instrument scores planted facts
  by transcript scan (never through extraction); the synthetic client must be fixed
  first (canned evasions ~50–60% of turns); the baseline run doubles as the tabled
  Sonnet-vs-Opus coaching test. Ruled: in-story follow-ups are exempt from the
  ~1-question/session budget (it caps only out-of-flow clarifications).

- **Notability handwritten cases (ruled 2026-09-01, corrected same day)**: NO
  anonymization machinery — no translator, no scrub guard; inference on this data is
  rare and goes straight to a BAA provider (OpenAI/Gemini) with raw content. Scope:
  PDFs (auto-backup ON, landing in Google Drive) → TWO-armed interpretation
  bake-off (GPT vs Gemini; local arm ruled OUT — no vision model installed, 30-40GB
  pull not worth it vs frontier; keys in theapp/.env) → import script
  writes NEW .fd diagram files (originals preserved untouched) → profile the new
  diagrams exactly like the app cases. BAKE-OFF SCORED (2026-09-01): synthesis wins
  (both models extract from images at max effort; third image-checked merge call);
  ~3 calls/case ruled fine — data irreplaceable. Verbatim transcription kept as a
  separate archival call, never chained into extraction. Open rulings: (a)
  baseline-configuration cases (no dated events; binding mechanisms + implied
  triangles) → relationship symbols + notes instead of forced events? (b) scope of
  the "no diagram, saw once" exclusion (row 10 ruled out — whole class or per case?).
  Review at volume happens in the app on imported diagrams, not in .md files.
  PDFs are LOCAL in btcopilot-sources/clinical/
  (56 cases, ~420 PDFs after dropping Individual Coaching per his ruling); Claude
  never manages that repo's git and never reads its client-named paths into context;
  PRIVATE_pdf_mapping.md there maps folders→diagrams (ratified: 44 exact, 7 fuzzy,
  14 no-match = new-to-app cases); bake-off samples = mapping rows 10/34/37/32/55;
  spec = doc/archive/2026-09-NOTES_TO_DIAGRAM_PIPELINE.md (schema v0 awaiting his markup) (marker density, span, people) → Patrick
  eyeballs which are viable for functioning-timeline inference. Work home: PRIVATE
  btcopilot-sources. RULED: the pipeline is REUSABLE PRODUCT TECH — professionals
  scan/export notes to PDF → diagram file; build it as a clean module (interpretation
  prompt + output schema + .fd writer + per-item confidence for human review) with
  the method documented, bake-off findings included; user-facing surface deferred.
  Placement RULED: module in public btcopilot, prompts in the private layer like
  the coach prompts; it will be factored into the new part of the training app that
  becomes the released user app. Does NOT gate the visualization prototype — only the
  FUNCTION-subset ruling does.

- **Patrick's own comprehensive timeline (queued 2026-09-01, after the clinical
  run)**: merge his old diagram, new diagram, and journal into one timeline —
  sources exist in ~/theapp/btcopilot-sources/fd-corpus/design/ (his chat/journal corpus files) plus his
  live records; same synthesis machinery expected to apply.

## Jira / branches

- FD-359 epic (chat-first web app) with FD-360 (built, draft PR #133) and FD-361
  (corrections through chat — not started). FD-341 untouched as the June plan of
  record; FD-336 superseded as the first chat surface (in docs, not yet in Jira).
- The branch is `FD-362`, the same name in both repos, in the built-in worktree location.
  It carries decision log entries, the brainstorm docs, DRAWABILITY.md, this package, the
  schema comparison and the converter in btcopilot, and the oracle store in fdserver.
  btcopilot #136 is merged; fdserver #30 was closed unmerged (#135 and #29 are closed
  predecessors). The fast-follow is FD-363, one batch branch in btcopilot, **draft PR #138**.

## Open security items (Patrick's calls, untouched)

1. FD-360 branch git history: two commits with real personal data (f55c5b0,
   35dd13b). Recommended: delete remote branch + PR, re-push clean, reopen.
2. Public master, pre-existing: a test-fixture name, names in decisions/log.md, and
   IRR meeting transcripts under doc/irr/meetings quoting Patrick on family matters.
   Recommended: PR moving transcripts to fdserver + neutralizing names; his risk call.
3. Business model TABLED (numbers in HISTORY); LLM-provider BAAs EXIST, the ANTHROPIC
   BAA is the pending one — until it lands, clinical content never enters model
   context (structure-only corpus).
4. Oracle-store items: (a) guards are code (SPEC §7: store-integrity, oracle-outside-
   store, trace, coverage, id-stability) — follow-on ticket to implement in CI;
   (b) the workstream skill's per-ticket oracle files are a second corpus (SPEC §11)
   — unification or a bounded carve-out is his ruling; (c) the proposed tag
   vocabulary needs his ratification; (d) the store awaits parent placement into an fdserver worktree from the staged
   files (see session report); (e) his feature-grouped ratification pass over the
   initial 64-ruling set.

## The architectural step back (CLOSED 2026-09-07)

All six items are ruled. Where each one landed:

1. **The UI principle** — [The UI principle](#the-ui-principle-ruled-2026-09-03--step-back-item-1).
2. **The Pro app** — [Architecture and data](#architecture-and-data-ruled-2026-09-07): nothing is ruled, deliberately.
3. **User journeys** — [Beta build](#beta-build-ruled): the six that check the build, and the deferred seventh.
4. **Architecture as a concept** — the show tool in [The UI principle](#the-ui-principle-ruled-2026-09-03--step-back-item-1); the pending pool dropped, no PDP in the beta build.
5. **The data format** — [Architecture and data](#architecture-and-data-ruled-2026-09-07): JSON record, change log, additive shapes.
6. **Front-end shape** — the Vite page in the build brief under [Beta build](#beta-build-ruled).

That build is done and reviewed; where it stands is at the head of this file.

**Session discipline (ruled 2026-09-07 R-0088, extended through the review rounds of
2026-09-08 and 09).** The full process rules are binding and live in
[HOW_THIS_PROJECT_WORKS.md](HOW_THIS_PROJECT_WORKS.md). The short form:

- The big model rules and drafts concepts. Sub-agents do every read, write, git command and
  build — Opus for work to a spec, Sonnet or Haiku for mechanics.
- **An eyeball round covers at most three items**: edit, one headless screenshot at 393x852
  for the coordinator to check, then Patrick refreshes the dev server and sees it himself.
  Goldens, gates, suites and CI run once at the end of the day, never per round.
- **Patrick looks before anything is polished.** The moment a build is believed to work he
  gets the link and a list of what he will notice. CI, coverage and re-walks come after.
- **Every multi-agent run spawns a persistent auditor before the workers start.** Its job is
  the clock and the cost first — a ten-minute stall alarm, checking the sandbox is reachable,
  and flagging any verification beyond the one screenshot. An auditor that misses a stall is
  replaced.
- **Nothing an agent says reaches Patrick.** No interim reports, no sign-offs, no
  coordination chatter — one deliverable message when the work is ready for his action.
- One worktree per builder. Shared-index sweeps and gap-file clobbers have cost hours.
- Rulings are written to the store as they are made, not batched to the end of a session.
- Every claim needs a tag saying whether it is a fact or a guess. Write in plain sentences
  using Patrick's own words, never invent a new term, and do not offer multiple choices
  when he asked to brainstorm freely. [R-0088]
- Read this file first. Read HISTORY only for a specific fact.

Pinned, not active: the corpus/subset sessions in [NEXT_SESSIONS.md](archive/2026-09-NEXT_SESSIONS.md).
