# Chat-first rebuild — STATE (the system of record)

**FD-362 is this project's epic and single source of truth at product altitude; this
branch is the corpus. Process rules: [HOW_THIS_PROJECT_WORKS.md](HOW_THIS_PROJECT_WORKS.md).**

Read this first, every session. This is the current truth; the derivation lives in
[HISTORY.md](HISTORY.md). Both are living documents under the two-clocks regime:
**append to HISTORY, revise STATE** as part of any work that changes either.
Ten-minute read by design.

**Play-by-play redesign — approved and built.** The snapshot-based drawer, designed on Fable
from the theory corpus and approved by Patrick 2026-09-27, replaced the old moves board; see
"Where the build stands" below for what shipped and where it stands.

**Handovers are retired (2026-09-26).** This file is where a session starts: "FD-365" alone
starts one. FD-365 is the second fast-follow batch (Jira FD-365, branch `FD-365`, draft PR #142,
child of epic FD-362); everything for this work goes into FD-365, with no new ticket (Patrick,
2026-09-29). Its open scope is the "Next PR" list below. FD-363 is merged. The production deploy
lock is on FD-365 (`uv run bin/deploy-lock show`, 2026-09-30) and stays there until Patrick
names another session [R-0530]. The flush revises this file and appends to HISTORY, and that is
the whole handover.
The older handover files in the private corpus stay as they were, for the record only.

FD-366 is the follow-on ticket (child of epic FD-362): the coverage checklist per Kerr chapter 10 with four states, prose quality by Patrick's picks, the conversational regression test, and the shadow spend category. FD-365 is frozen for review and merge as of 2026-09-30; new work goes on branch FD-366 from the FD-365 head, and the deploy lock moves to FD-366 when Patrick says so.

**Start here for FD-366 (end of 2026-09-30).** Production runs release 3.2026.9.30.12. The deploy lock is on FD-366 (`uv run bin/deploy-lock set FD-366`; Claude moves it when Patrick says so, R-0623).
Live: the coach at low thinking, every model call metered by purpose (shadow kept out of real spend), shadow turns and backfill on a queue, the OpenAI client (GPT-6.1 alias gpt), coverage stages one to three (required items from the record, four states, the ranked unasked block in the coach's summary, the coverage curve on the features dashboard), the rewind fix for kindless events, the record-row lock fix.
Patrick's sitting measures: whether replies at low thinking and with the coverage block read as well as before, judged by his picks in Better replies.
Patrick's items: the A items on the open-issues page; the rulings queue waits for his key (R-0619, R-0622, R-0623, R-0624, the R-0618 note); the Sonnet and Flash picks in Better replies; the one-off correction of old fallback rows on production; a key for Muse Spark, and an OpenAI key on the box for live GPT shadows.
Ours: the four remaining coverage panels, the conversational regression test on Patrick's thread, the coverage-efficiency experiment, the pick-notes rubric, the coach-started email design pass.
Artifacts: cost page https://claude.ai/artifact/WMnou7A3UcZcUhAgZujQre ; open issues https://claude.ai/artifact/6V3sTBzxEz7WZKGZJNGe9s ; models https://claude.ai/artifact/2dHnrTjSaD2cTyzdjue5GL ; tools https://claude.ai/artifact/3sLhHczKGyWLLXmMw2DY8q ; coverage decisions https://claude.ai/artifact/TtrD5U4qYmut1bdb7jM4Yg
Local measurement harness: /Users/patrick/btcopilot-sandbox/prodcopy (its README says how to replay turns against a copy of production data).
Skills changed today and uncommitted in the sources repo: efficiency, token-optimization, theory.

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

**Production today (2026-09-30): release 3.2026.9.30.2 from branch FD-365, commit 600da16,
database at 1b00000000bd.** PR #142 stays the ticket's PR, open and unmerged. The sittings work
was built on branch `sittings` as PR #144 and merged into FD-365, not master, on 2026-09-30. The
landing page, PR #143, merged to master and was merged into FD-365. Releases dispatched from
FD-365 on 2026-09-29 and 30: 3.2026.9.29.1 (one back chevron and one step pill everywhere),
3.2026.9.29.2 (the ask button hidden for now), 3.2026.9.29.3 (the literature review row for
auditors and admins), 3.2026.9.29.5 (the landing page), 3.2026.9.30.1 (PR #144) and
3.2026.9.30.2. 3.2026.9.29.4 is the tag the build on master gave the landing page merge. Four
commits after 600da16 are pushed and not on the box: the features dashboard, the feedback loops
ledger, the product-owner skill and its first run. What production now does, by area:

**Sittings.** Each family has one chat thread. A new sitting starts by itself once the family
has been quiet 12 hours, and a light line with the day marks where it starts (with the time as
well when the sitting before it started the same day) [queued R-0604]. The list of sessions to
open and the New session button are gone for everyone: nobody opens, starts or switches a
session, and the person never manages what the coach remembers [queued R-0605]. A sitting's
summary stays in the database for the agenda and review and is not sent to the thread.

**The coach's memory.** The coach no longer gets its past tool calls back, so the thread cannot
grow without end. Each turn it reads its last notes from the database, the family's last 20 to
29 statements from every sitting (the window steps by 10, so the cached part of the prompt stays
the same until the next step), and a map listing each event's id, date, kind and people. It
finds duplicates from the record alone [queued R-0606] and finds older words with a search over
past chat [queued R-0607]. A follow-up tool, "ask later", keeps a question for a later day that
the person agreed to. A coach turn whose edits change items an earlier sitting made writes an
observations row for tuning. No eval has run on this change yet (PROMPT_ENGINEERING_LOG.md).

**The coach writes first.** A message the coach writes first is one coach message in the thread,
then a notification, with only one outstanding at a time [queued R-0608]. It has two triggers: a
question for later the person agreed to, and a pattern in their own record that has just reached
two occurrences, a symptom or anxiety going up, or functioning going down, within 60 days after
a relationship ended or they moved away from it. Never an anniversary of a hard event [queued
R-0607]. Unasked messages are off by default and at most one a week or one a month by the
person's setting, worded as a maximum, never a schedule; a follow-up the person agreed to is
outside that budget; two ignored in a row stop that kind until the person answers. Words that
make one event the cause of another ("led to", "because") are refused and tried again on a later
run. A scheduled run every 15 minutes picks who gets one, on a new scheduler service on the box,
fd-beat, which has its own health check since 3.2026.9.30.2; `flask admin proactive run
--dry-run` prints a row per person saying why nothing went, and stops before the model. How each
message fared (sent, opened, replied, returned) is counted and kept out of Patrick's
accept-or-reject queue.

**Web push.** The coach's message reaches the person as one web push at a time, the newest
replacing an unread one, or as one email when no browser is subscribed; a tap opens the thread at
that message and stamps it opened. Push sends no Topic header, which Apple refused. The app
added to a home screen shows the Family Diagram icon, drawn from the iOS app's own icon. The app
refuses to start without its push keys, and it runs on the box.

**Notices.** Two tables [queued R-0613]: `notices` holds a message once with who it is for
(everyone, a role, or named people); `notifications` holds one row per delivery to one person,
of kind coach, task, reminder or notice. `flask admin notice send` sends a notice at once: a push
to whoever subscribed a browser, an email only with `--email`, otherwise a row in the app's
list; `flask admin notice list` prints how many got and opened each. In the app the newest
unread notice, or a waiting coding task, is one small card above the message box, never in the
thread and never covering the page: folded to two lines, a tap unfolds the whole text with Open
and a cross under it. The account view has a Notices page with the unread count, and the account
mark carries an amber dot while one is unread.

**Bug reports and feedback.** A sheet slides up from the bottom only when the coach offers one
from the conversation [queued R-0615]: "Send this as a bug report?" with Send the report, Always
send and Don't send (disabled during the beta), or "Send this as feedback?" with Send the report and Not feedback. It is
modal, never touches the thread, and after Send turns into "Your report was sent" with OK,
closing by itself after ten seconds. Each answer is one row in the new `reports` table, status
sent (with the words) or declined (without them). The coach page has a "Bug reports" setting:
ask me, or always send. An exception reporter, which raised the sheet and wrote rows for errors
on the page and the server, was built and removed the same night, because Grafana Faro (the
page) and Alloy (the server's logs) already hold every error; a migration deleted the rows it
had written. Every server answer now carries an `X-Request-Id` naming its log lines, and source
maps are built hidden, never served, and kept 90 days with the release run.

**In-app addresses.** Every view and object has an address under /app/ [queued R-0616]: the
address bar follows the app, the browser's back button steps back, and an address naming a
message, session, notice, cut or snapshot scrolls it into view in its drawer and rings it. The
coach has a navigate tool: asked for help with the app, it takes the app there, and its reply
carries a chip such as "Opened the coach settings". A notice may point at any address. The
address table is in SCREENS.md.

**Coding and Quality in the account view.** "Your coding task" and "Next meeting" moved from the
sessions sheet to a Coding section of the account view for auditors and admins, Next meeting
for admins only, with the literature review row now titled "Auditor's Coding Guide" [queued
R-0609, R-0601]. Admins have a Quality section with one row, "Better replies", the page formerly
called Compare replies [queued R-0612]. Each opens as a page of the account view. A cut starts
from the meeting page, never from a session: "Put a session on the agenda" lists every session on
every family, searchable by words said in them. One meeting date is one meeting.

**Auditor onboarding** [queued R-0614]. A coder gets a task notice when Patrick gives a cut a
meeting date, and one reminder two days before the meeting if not submitted. The invitation and
sign-in code emails say what the work is in two sentences; the task card shows four numbered
lines under "How this works" until "Got it"; the first line tapped in the coding screen says to
type what it tells you happened.

**Development-only sign-in.** A development server lists every account on the sign-in page and
one tap signs in as it; `FLASK_DEV_AUTOLOGIN` (`sandbox up --autologin <email>`) signs every
request with no session in as one account. Neither exists under any other config, and a test
proves production has no such route.

**Smaller changes.** The lists drawer's third tab is "Questions", not "From the coach". In the
sessions sheet Rename is green and Delete red. With a real keyboard Return sends and Shift- or
Alt-Return makes a new line; on a touch screen Return makes a new line and only the send button
sends [queued R-0610]. The new-event and new-person forms slide up full screen. The coach's notes
field "What it's doing" says evaluation, not journaling [queued R-0617]; notes already stored
keep their old word.

**The landing page** (PR #143) is live since 3.2026.9.29.5: familydiagram.com/ serves it, both
forms behind Cloudflare Turnstile with its two keys on the box. Patrick submits the first real
form himself.

**The feedback loops ledger, the features dashboard and `/product-owner` (in the repo, not in a
release).** doc/FEEDBACK_LOOPS.md has one row per feedback loop, 23 rows, each with its signal,
closing action, status, the number that proves it, and a query; a test fails when an
observation kind, report kind, notification kind or dashboard panel has no row [R-0578]. The
features dashboard is in the repo (deploy/grafana/fd-features.json) with four new panels: the
coach's first messages, bug reports and feedback, notices, and coach edits to earlier sittings'
items; every release puts it on Grafana, and no release has run since it was committed. The
`/product-owner` skill runs only when Patrick asks: read-only readers pull each loop's numbers,
one Sonnet judge writes a line per loop, and one Fable call ranks at most five recommendations
toward product-market fit. Its first run is doc/log/product-owner/2026-09-30.md; its one
recommendation is to talk to the 4 people who opened the app, 20 minutes each, and its proposed
ledger diff awaits his yes.

**PR #136 (branch `FD-362`) is merged to master, and so is FD-363 (PR #138); FD-365 is the
current batch, one PR [R-0484]. fdserver is out of this work (2026-09-16):**
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

**Deployed 2026-09-26 05:40 UTC: commit 5b2a6bb, image 3.2026.9.26.1-g5b2a6bb.** In plain words:
- A coach reply has a thin line-drawn play button on its own row under its last line, as in
  the Claude Code mobile app; a tap reads that reply aloud, a second tap stops it, and a reply
  with no words gets none [R-0521].
- Each name a tool line acts on is set in italics, in the real italic of the tool lines' font
  [R-0528].
- On iPhone a long message no longer draws its lines over each other: the rounded outline sits
  on a wrapper and the text scrolls in a square box inside it.
- The coach keeps its own notes every turn through a tool: register, lane, why this question
  now, what it holds for later, history plateau and biggest gap, any hunch, its sense of the
  person, which variable is live. The record is untouched by them and reads its last notes
  back the next turn. The server strips them for anyone who is not an admin or auditor; they
  see a circled (i) at the bubble's top right that opens the notes in a panel growing out of
  the bubble and shrinking back into it on close [R-0520, R-0522, R-0529]. Replies from before
  this build have no notes. Confirmed in his 2026-09-26 afternoon message: his own thread showed
  zero notes on any reply, because his last turn before that message came before this deploy.
- A question asked this turn is dated in UTC, like the messages beside it.
The notes were proven on the real model for one first turn ($0.141, testing key); the read-back
is proven by a unit test, which Patrick accepted. The gate: 613 Python tests and 245 web tests
passed, the paid behaviour suite passed 9 of 9 ($0.64, testing key), no migrations, and his
thread had 78 statements before and after. It was deployed by hand on the box, because the
setting naming the server was missing from GitHub. Backup:
`/root/backups/prod-2026-09-26-0540-pre-fd363-5b2a6bb.dump`, copied to
`~/theapp/btcopilot-sources/`.

**Pushed after the 05:40 deploy, not part of the app on the box**:
- The paid behaviour suite saves each real response, sops-encrypted under private/replays and
  keyed by a hash of the whole request, and replays it; LIVE_REPLAY picks replay (the default,
  records what is missing), record or only; replayed calls go into the ledger at $0; the date
  the coach sees is pinned to 2026-09-25 in that suite (78ff857) [R-0531]. Two replay-only runs
  gave the same keys for each case's first call; later calls are unproven until one paid run is
  followed by a replay-only run.

**The play-by-play and the chalkboard.** Stepping through
one real cluster of eight events on a copy of production (named only in the private corpus's
session-b147ab7f/INDEX.md)
found bugs Patrick confirmed [R-0526]: a move with no one on the other end is drawn
on the mover's own figure; a bond line is drawn outside the bond's own dates, because it is drawn from
the whole record; a couple's bond and separation draw the same; a second shift on the same event
is not drawn, because only the first is; an event with unknown date certainty is dropped, so
eight events show as seven steps; captions show app words such as "bonded" and "separated". The
first bug starts in the record: two of his own events, dated 2015-09-01, are defined-self moves
that name him as their own target, and events, unlike pair bonds, do not refuse that [R-0527].
A chalkboard idea proposed from this one cluster missed his clinical
frame, and he ruled that the frame is built and checked first, in a separate Fable session, and
that the design must fit every case [R-0524, R-0525]. His question stands unanswered: how the
coach could draw a story arc the way a coach uses a chalkboard, drawing what the point needs
rather than a fixed wireframe of everything in the record, in a way that fits every case.

**Ruled 2026-09-26 [R-0532]: the play-by-play work splits into two lists.** Fixed and deployed
2026-09-26 (commit 2a797b0, see below): nothing may point a move back at the very person making
it, the same way two people cannot be bonded to themselves; a bond gets no line on the picture
before its own start; when two changes land on one event, both get their own place in the steps
instead of just the first; and an event missing a known date keeps its spot in the story at
wherever the coach set it, rather than dropping out. Waiting on the frame of reference: telling
an ended bond apart from an ongoing one, new picture words standing in for "bonded" and
"separated", and how to draw a move that names nobody on the far side — for now, words only,
nothing on the picture. A separate call the same day [R-0533]: when something in a person's
saved family information turns out wrong, it gets corrected, and the correction itself becomes
training material going forward — the original mistake is kept on file as a case an automated
check can run against later, and the fix travels through the same log every other record change
uses, never a direct database edit. The case, corrected: his two events from 2015-09-01 were
defined-self moves, not the distance move first suspected, each naming him as its own target;
both targets were cleared, tagged review, through the record's write path (change rows 269 and
270), and the second event is flagged in the case file as a suspected near-copy of the first.
The write-up is in the private corpus at correction-cases/2026-09-26-self-target.md; its eval
is still owed [R-0533]. The chalkboard concept has not moved; the frame still comes first.

**Deployed 2026-09-26 ~20:20 UTC: commit 2a797b0.** The release workflow's deploy job, which
reads the host, user and key from a GitHub environment named production that only branch
FD-363 may use [R-0530], ran for the first time on a real dispatch from FD-363 (run
36268785383). It carried onto the box: the play-by-play fixes above; the play-by-play
follow-ups — the event editor no longer offers the mover as their own move's target, dated
events play in date order with each undated event placed right after whichever event is stored
just before it, and an undated step draws bonds as they stood at the nearest dated step; and
Patrick's account becoming an admin, so the coach notes' (i) button now shows for him. (A
repository-wide host setting that would have deployed every push to master was made and removed
the same hour, before this dispatch.) Two bugs in the workflow itself turned up and were fixed
on the way: the job's host check was written as a condition, which cannot read environment
variables, so it skipped on every dispatch (df0dde9); and the check meant to stop an
already-superseded database revision instead stopped the current one and ran after the new app
had already gone live rather than before the image was pulled — it now runs first and lets the
current chain through (2a797b0). Backup:
`/root/backups/prod-2026-09-26-2013-pre-fd363-2a797b0.dump`, copied to
`~/theapp/btcopilot-sources/`. His thread was unchanged by the deploy: 81 statements, 29 people,
67 events, 12 pair-bonds, 5 clusters, 194 change rows, before and after. One real turn on the
claude-test account proved the running stack, for $0.16.

**Play-by-play rebuilt and the old moves board retired (first deployed as commit f66d603).** The
snapshot-based drawer Patrick approved 2026-09-27 ("This all looks good. let's do it.")
[R-0545 to R-0570] replaces the old moves board entirely [R-0570]. Old board-only rulings were
marked superseded once their own tests were confirmed gone (R-0130, R-0131, R-0135, R-0162,
R-0173, R-0177, R-0178, R-0180, R-0292); two triangle-drawing rulings (R-0286, R-0288) were kept
and narrowed to the new drawer instead, since their tests still pass there.

**Deployed 2026-09-28: commit 07b9d8b, image 3.2026.9.28.7+g07b9d8b, database at
1b00000000b2 (run 36428718588).** Everything queued the previous session went out together, as
he asked, so he can evaluate all of it at once:
- The cluster-select slide fix: opening a cluster from the timeline now redraws the same
  timeline with the cluster selected in place, never sliding a second view over the first
  [R-0542].
- The stale home-screen app fix: on returning to the foreground the page checks the release
  version and reloads if it changed; the HTML at `/app/` is served no-cache; the bundle's
  files carry hashed names; the service worker's cache is named per release.
- The pill strip [R-0543, R-0544]: one pill per cluster, no inner dots, the strip one screen
  wide, nothing merges.
- Play turns now write a done turn event, closing the gap the migration gate was flagging.
- An invalid event kind and an unknown evidence kind are refused back to the coach rather than
  failing the turn [R-0075]. A couple event with no spouse is refused at the writer [R-0453].
- The first migration's table order is fixed so an empty Postgres database builds [R-0417],
  a one-time exception logged as R-0574 because that revision had never run in production.
- The people and cost dashboard's Person filter, now in `deploy/grafana/fd-chat.json`.
- The sandbox kit lives in the repo at `bin/sandbox/sandbox`.

The first release attempt failed: the box's disk was full, about 48 GB of unpruned untagged
docker images. They were pruned by hand. Open: the release workflow should prune old images
itself so this does not recur.

**Ruled 2026-09-28.** The editor that would have opened from tapping an event's words inside a
cluster is not being built; chat is the real way to edit an event, with the event list as the
fallback [R-0572, supersedes R-0207]. And the timeline was never meant for picking out one
event at a time — clusters are what matter, since a cluster leads to the play-by-play [R-0573].
Process: work stays in a single worktree per ticket rather than spinning up many branches; the
merge rules only guard master [R-0575].

**Deployed 2026-09-28: commit 8ad08dc, image 3.2026.9.28.8+g8ad08dc, database at
1b00000000b4 (run 36443507214).** Three changes:
- The timeline's width, its start at the present, its swipe and snap, and its return to the
  present are carried over exactly from before the pill strip (commit 8974698), on his word that
  he wanted the zoom to stay exactly as it was [R-0381, R-0577]. The only change: snap points
  are rounded to whole pixels, so tapping a pill never moves the line [R-0542].
- Explain reuses a cluster's newest play-by-play telling, held in the `statements` table, while
  its `digest` column still matches. The digest covers everything the drawer draws for that
  cluster — the cluster, its events, the people it draws and their parents, its pair-bonds
  including married state — plus the play prompt's own text, so a change to the prompt also
  retells it [R-0576]. Migration 1b00000000b3 adds the column. Verified on production: a second
  explain on the claude-test account made no model call.
- New `observations` kinds: tool_refused, play_refused, play_failed, turn_failed, step_cap and
  turn_declined feed the tuning queue, at most ten groups, read with `flask admin observations
  queue` and dismissed with `flask admin observations reject <key>`, which stores the key in the
  new table `observation_rejects` (migration 1b00000000b4). The quality dashboard gained per-day
  counts and a "Tuning queue" panel. Refusing bad tool input back to the coach with a warning log
  and a retry is the approved pattern behind this [R-0579]; being aggressive about what gets
  tracked, dashboarded and queued for his later yes/no, on every signal that shows the coach or
  the app needs tuning, is now the binding rule everywhere, not just here [R-0578, refines
  R-0517].

**Schema debt, noted 2026-09-28, not built [R-0582, R-0581].** The `statements` table now carries
two kinds of row through its `kind` column, `turn` and `play`; four of its columns (`kind`,
`cluster_id`, `told_case`, `digest`) are read only by a `play` row, and a telling is also copied
into every thread that reuses it from the cache. He chose to leave this as it is while testing
continues, rather than split it into its own table now. Whenever a future feature strains this
shape further, the split (a `play_by_plays` table, with `statements` rows pointing into it) has
to carry every existing row across with nothing lost, proven first on a copy of production: a
beta thread cannot be recreated once its opportunity to chat has passed.

**Open, waiting on his yes:** the pill strip's one-screen line (R-0543) contradicts the earlier
crowded-line ruling [R-0402]; not superseded until he says so. R-0381 stands: he confirmed the
timeline's zoom, width, scroll and open position return exactly to what they were before the
pill strip, with no new zoom behaviour invented [R-0577], so it comes off this list. A ruling
candidate with no id yet, needing his yes: "after a deploy, the home-screen app loads the new
release when it comes back to the front" — its tests cite R-0486 until then.

Open for the next session: the first tap right after a rollout can hit a 502 while the
container comes back up.

**Next PR, as of 2026-09-30.** Open FD-365 items:
1. Record-data corrections get a general policy and a queue, not one-at-a-time fixes, and not in
   this PR (Patrick, 2026-09-28). Queued under it: event 26 in diagram 1, a noted event carrying
   a variable; the 8 births in diagram 11 naming an invented second parent, repair calls prepared
   but not run; diagram 14's two events naming nobody ("Leave for now").
2. The defined-self wording is rewritten to Patrick's definition and held: it needs a multi-turn
   eval, modelled on the logged conversation, that fails on the old wording, then one paid
   confirmation run (about 9 calls on claude-opus-5-5, $0.15 to $0.40). The wording is in the
   private corpus at prompts/2026-09-28-defined-self-wording.md.
3. The rulings store audit lists await Patrick's approval, none applied: 18 candidate merges, 19
   supersessions of which 5 conflict, 115 rulings no test cites, 7 rulings that are bug reports.
4. Whether Patrick's published papers may be quoted on the public concept pages: about 125
   quote lines, none published until he decides.
5. Ten live cases have no saved answers; the subscription run has re-answered some of them.

Left from 2026-09-29 and 30:
6. 15 queued rulings, R-0603 to R-0617, in the private corpus's
   RULINGS_TO_APPEND_2026-09-29.md, wait for Patrick to append them to the store with his key.
   Until then tests cite existing ids, and are re-cited after. The landing page's entries in
   HISTORY.md, decisions/log.md and SCREENS.md cite R-0601 and R-0602 from before the queue was
   renumbered; in the queue those ids are now the literature review row and sittings, and no
   queued ruling covers the landing page.
7. Two builder changes nobody asked for, for his yes or a revert: search results show chips as
   words; the Concept pages row moved into the Coding section and is now titled "Auditor's
   Coding Guide".
8. The bug sheet's forced send in the beta is on branch FD-365, not deployed: "Don't send" is
   drawn disabled with "Disabled during the beta" under it, and the server refuses a declined bug
   with a 400; one constant on the server turns the beta off. The feedback sheet keeps a live
   "Not feedback".
9. The memory change and the notes field's new word shipped with no eval run.
10. Every session in the meeting's "Put a session on the agenda" list is named "Free Diagram".
11. The coding screen's title is clipped.
12. The reports route's limit of 20 an hour per sender is held in the server's memory, so every
    restart resets it.
13. Source maps are kept 90 days with each release run; after that an error from that release
    cannot be traced to its source line.
14. Someone who joins a notice's audience after it was sent gets it in the app only: no push, no
    email, which matters for a pricing notice sent by email.
15. The coach's report tool has not been exercised on production: no real turn there has offered
    a report.
16. R-0096 (the sessions sheet is a plain list) lost its only citing test when the session list
    was removed; it needs a test or a supersession.
17. The first `/product-owner` run's proposed ledger diff awaits his yes.
18. The PR #144 description cites ruling ids from before the queue was renumbered.

**The rulings store is restructured (deployed 2026-09-28).** It is split into topic files with a
generated index and a hygiene guard; the ceiling is 300,000 bytes, so adding a ruling no longer
forces a trim elsewhere. An audit file of proposed merges, supersessions and uncited rulings
awaits Patrick's approval (Next PR, item 7).

**Deployed 2026-09-28, latest: commit d4971526, image 3.2026.9.28.10+gd497152, database at
1b00000000b5 (release run 36490165725).** It carries everything since a8b2245b:
- The shared teal × on all six views [R-0588, R-0589]; explain's teal replay chip [R-0590]; the
  chat box sitting above the keyboard, and compact, tap-safe chips [R-0591, R-0592]; the events
  list's kind marks [R-0594]. The event editor and the caption strip are fixed for iPhone Safari.
- Fourteen record rules refused at the writer and at the coach's tool [R-0593, R-0585]; the
  Next meeting agenda fix [R-0267].
- The cost work from branch FD-363-cost, folded in [R-0595 to R-0599]: prompt-cache reuse with
  the record in the newest user message, per-user coach and shadow models, the fd-shadow service,
  the Gemini settings, the Compare replies page, quality replay, and migration 1b00000000b5.
  The Gemini settings are absent on the box; an empty placeholder file sits at
  /etc/fd/gcp-sa.json, so no Gemini call can succeed yet.
- Dashboards exclude scratch diagrams. The rulings store was restructured into topic files with
  a generated index and a hygiene guard, ceiling 300,000 bytes, plus an audit file for Patrick's
  approval. The standalone-clone setup and doc/SETUP.md. The sandbox kit with the shadow worker.

Production data on that deploy: events 9 and 10 in diagram 1 are noted events with no move and
no functioning, by review change 642 (event 66 was made a toward move earlier, change 635). The
claude-test record gained a person and a birth for the post-deploy check.

The post-deploy turn on the claude-test account proved the record-in-user-message change: the
coach answered a birth year that existed only in the record, from the record. Spent: 8 paid API
calls, $0.1563, on the live suite's one-time calibration (Patrick's approval, 2026-09-28); every
other model call ran on the subscription or the local model.

**The live suite now runs on the Claude Code subscription** with the coach's real system prompt
and MCP tools (`bin/subscribe.py`) [R-0568]. Calibrated once against the API, the free path
judges tool choice, event kind, who is kept and what is asked; it does not judge finer fields or
wording, and those go to the ruled end-of-batch API run. The efficiency skill lives at
~/.claude/skills/efficiency with reminder, spend and audit modes.

**Deployed earlier 2026-09-28: commit a8b2245b, image 3.2026.9.28.9+ga8b2245, database still at
1b00000000b4 (run 36462083019).** The database revision is unchanged: this PR's migrations are
squashed into one [R-0584]. It carries:
- The play-by-play drawer's close button is the app's own ×, the same one the meeting card uses,
  and the drawer opens with its order path row, point and snapshot line in place.
- An event's words in the drawer stay inside the family's side margin, none running to the
  phone's edge.
- A selected cluster's title ends with its event count [R-0583].
- A "message" chip kind; the play-by-play's question and a coach bubble's closing question are
  both clickable amber chips [R-0587], each carrying its ruled pre-text phrase in the chat box
  before it — "To answer your question", "About your question" for Food for thought, "Here's
  what I know about" for Facts to find, "I want to ask about" for the ask button, which stays
  teal [R-0586].
- Every relationship move (toward and the rest) is refused without a target, at the writer and
  at the coach's tool [R-0585].
- The Next meeting agenda fix: picking your own session places its cut where it belongs [R-0267].
- Reinstalling the fixtures clears their agenda cuts; the app now imports with no sops key
  present; the fixture families' coach speakers are typed as the coach, not a person.
- CI's visual jobs run on the open-source prompts, same as the unit tests.

**Production data fixed.** Event 66 in diagram 1 is now a shift, toward, targeting person 54, by
review change 635 — the miscoding R-0585 caught. Events 9 and 10 in diagram 1, from 2015, were
never defined-self: Patrick ruled their words hold no defining-a-self behaviour, so their move is
cleared and they are noted events, not given targets. Still open: events 1 and 2 in diagram 14
have no target; any further edit to them is refused until one is given.

Also open: the coach rule that links the people an event's own words name, prompt written and
waiting on its eval, which needs the ruled end-of-batch API run on his approval (about $0.15 to
$0.40); the older ~/theapp copy of this worktree still awaits his word to discard it.

**2026-09-28, branch FD-363-cost off FD-363 (draft PR #141) — a prompt-cache cost fix.** A
heavy production day put 78% of that day's model cost in prompt-cache writes ($12.91 of $16.60
over 38 turns), because the record, the date and the "looked at" block sat in the system prompt
ahead of the chat and changed every turn, rewriting the whole cached chat each time. Fixed
[R-0595]: the system prompt now holds only the coaching text; the record block moved into the
new user message after the chat; the chat is marked at the previous two turn boundaries; tool
marks are capped at four; cache life stays 5 minutes. Measured on the sandbox with a
12,000-token chat: turns 2 and 3 cost 42% less, $0.2472 down to $0.1428. Estimated saving on
that production day is about $4.50, and near zero for a user whose gaps between replies mostly
exceed 5 minutes — 30 of 37 gaps were under 5 minutes for the heavy user, only 2 of 18 for
Patrick. A 1-hour cache life was weighed and left off, since it lands within measurement error
either way. Unproven: the saving on real production sessions, and whether moving about 14,000
characters of prompt out of the system prompt and into the user turn changes the coach's
behaviour — the post-deploy turn showed the coach answering a birth year that existed only in the
record, from the record; the wider live eval is the end-of-batch API run. Real model calls spent
proving this: $1.96.

**Same batch — model comparison plumbing, Patrick as the only oracle on which model is better.**
A per-user coach model and list of shadow models live in the per-user settings table, set by `flask admin
coach-model show/set/shadow`. A shadow turn runs each candidate model on the real turn's input on a
separate Celery queue, with a new fd-shadow worker service, stored in a new shadow_turns table
on a scratch diagram flagged scratch, never shown to the user and excluded from the user's
diagram list [R-0596]. `flask admin quality replay <discussion> <model> <reference_diagram>
[--cap 5]` replays a conversation's user statements on a model onto a scratch record and scores
people, pair-bonds, events, clusters and variables plus fault counts, appending a Replay line to
the ledger; the reference record is one Patrick corrected himself, never a model-built one
[R-0597]. A Gemini Flash coach model is wired in (google-genai, Vertex by default, aliases
gemini-flash, gemini-3.8-flash, gemini-3.6-flash, gemini-2.5-flash), because Patrick holds a
business associate agreement with Google [R-0598]; a real call on it awaits Vertex credentials
on the box and his confirmation of what the agreement covers. The review app's Compare replies
page serves blind pairs from shadow rows and replays and records Patrick's picks in a new
model_picks table [R-0599]. Live eval runs append one Live line per case to the ledger
(`btcopilot/ledger.py`, `ledger.jsonl`, gitignored). One migration, 1b00000000b5, squashed for
the whole pull request. Beta users stay on Opus 5.5, with no A/B test on them. Candidate pricing
at Anthropic's rates for that same production day: Sonnet 5 would have cost $9.16, Haiku 4.5
$4.58; Opus 5.5 and Sonnet 5 charge the same for cache reads.

**Usage on production to date, counts only, five accounts.** Guillermo sent 44 messages over 3
days for $17.31, no failed turns, never opened the picture, 78 of 111 events have certainty
unknown, and two people are duplicated; Patrick sent 43 messages, with 4 turns where the coach
saved edits but wrote no reply and 7 messages sent twice; Laura sent 6 messages, twice
challenging an assumption the coach made; Kathy signed in and sent no messages. Total spend
since the model_calls table began on 2026-09-23 is $22.99. Patrick's decision: no automated
fault digest for now.

**Testing stays on the Claude Code subscription, not paid API calls [R-0568].** A model call a
test needs goes to a Claude Code agent instead and is saved as a subscription-sourced replay;
the local model answers wherever the model itself isn't under test; the API is kept for the one
real turn on production after a deploy.

**The frame session.** A Claude Code skill named "frame" now exists: Patrick's persistent expert
on his clinical frame. The next session on this thread loads that skill first, then reads the
draft. What the session produces: one document, his clinical theory written as requirements a
coach reply or a drawing must meet — what the app is for, the unit and its variables, how a
symptom happens, the four variables as the record holds them, the period and its key shift, what
the evaluation collects and why, what the coach is, what a picture may claim, the off-frame
ideas to catch, and how to read a cluster in the frame. The test: a fresh session reads only
that document and one cluster and writes a short reading naming the key shift; Patrick grades it
against his own; agreement across about ten clusters, his and clinic cases, is the pass; each
disagreement becomes an example in the document. Inputs: the draft (on disk, uncommitted, at
doc/FRAME_OF_REFERENCE.md in this worktree, with a copy in the private corpus's
session-b147ab7f/); the survey and the play-by-play folder beside it; the primary sources in
btcopilot-sources/bowentheory/ (Family Evaluation, Family Therapy in Clinical Practice,
the Basic Series lectures, Havstad and Sheffield's shifts paper, Patrick's 2020 talk on the
implicit model); the coders' rules in doc/irr/; the rulings store. Whether the session starts
from the draft or from nothing is his decision.

**The survey of 56 clusters** (his 5 stored and 51 proposed by the grouping rule over the clinic
cases; roles only). By people: 16 have one person, 20 two, 20 three or more. 4 record a
triangle. 3 have trouble in more than one person. 31 have no relationship move at all. 31 open
on a noted event, 13 on a structural event, 12 on a shift. In 35, half or more of the events
are noted events with no variable. Four shapes recur: one person alone with a variable rising
and falling across noted events (the most common); a couple event with noted events around it
and nothing moving between people; a couple comes apart and the symptom lands on one person;
rarely, three people with inside or outside, toward or away, and symptoms trading places. Hard
to draw as people and moves: one person alone; a cutoff with no recorded target (5 times); a
56-event stretch; a family's reaction to one death split into three one-person clusters,
because the grouping rule never links parent and child.

Open:
- Whether saved responses replay beyond each case's first call waits on one paid run followed
  by a replay-only run.
- The message-box fix is checked in desktop WebKit only; Patrick's iPhone is the real check.
- Three play-by-play items still wait on the frame of reference.
- Three rulings were skipped as needing a design rather than built: R-0187; R-0213, R-0376 and
  R-0378 together; R-0122 and R-0127 together.
- The count of guess-dated events is blocked by the personal-data safety check and is not built.
- An old kept tool call that changes an existing event still keeps that event's old words
  instead of writing the new ones.
- Still open from 2026-09-25: three impressions choices made under his general yes; the SARF
  story (a Fable topic); the guessed-dates pass and a reading of his record, both blocked on
  personal-data reads; whether four questions from his whole history are too few.
- Patrick ruled 2026-09-26 that the three-generation coverage brainstorm waits until the frame
  session returns. Evidence: the first coach notes in his thread (his reply at 18:53 UTC
  2026-09-26) say his history has not levelled off, but the only gaps flagged for later are his
  half brother's name and age, his parents' ages, and the 2015 cutoff with his mother — nothing
  about grandparents, aunts, uncles, or their stories. Beside this: Patrick questions the word
  "coaching" for one of the four registers — coaching a person is offering inferences from data
  already collected, distinct from first gathering the basic facts. None of the four register
  names is defined anywhere, not in the tool schema and not in the private prompts, so the coach
  picks among them by name alone. Renaming and defining them waits for the coverage brainstorm
  after the frame session.
- Found, next batch to fix: the play-by-play's own model calls never reach the model-call
  record, so their spend goes uncounted.
- Patrick's question about a decrypted prompt copy was really about agents always reading the
  decrypted prompts instead of assuming their contents; resolved as a process rule in
  HOW_THIS_PROJECT_WORKS.md ("Encrypted is never a reason not to know"). No mirror or extra
  tooling was built.
- The coach producing a snapshot's point, facts, guess and question live is proven only by
  Claude Code subscription replies and one real turn on production; no full eval has run yet.
- Nothing yet holds a play-by-play to three to six snapshots; real cases have shown as many as
  eleven and seventeen steps.
- A real first name from Patrick's own record sat in committed code before today's fix; swapped
  for a stand-in name.
- The live eval run against the moved prompt (branch FD-363-cost) awaits Patrick's spend
  approval.
- A real Gemini call for the new coach model awaits Vertex credentials on the box and Patrick's
  confirmation of what his Google business associate agreement covers.

**Patrick's actions.**
1. Test the 5b2a6bb batch in his own thread, including a long message on his iPhone and the (i)
   on one new reply.
2. Decide on the frame draft: the frame session starts from it, or it is discarded.
3. Start the frame session on Fable when he wants the frame built.

**For the next session's coordinator.**
- Never deploy from master. The first deploy through the GitHub environment ran 2026-09-26 from
  FD-363 (commit 2a797b0); another ticket branch will still need the environment's branch rule
  widened before it can deploy the same way.
- After the next paid run, run the suite once with LIVE_REPLAY=only to prove saved responses
  replay beyond each case's first call; until then assume later calls still cost.
- Read the rulings on a topic before proposing coach behaviour; judgement calls stay in the
  prompt and the coach's tools, not in code checks [R-0485].
- Older tests carry real names from his thread: web/test/spotlight.test.ts lines 41 to 42 and
  btcopilot/tests/test_timeline.py line 468. Swap them for stand-in names from
  doc/mockups/family.md, as the italics test was (616c529).
- Plaintext copies of private prompt fragments sit in the b147ab7f job's temporary frame/
  folder; they go when the job is deleted.
- Model use: Fable for the frame session and the chalkboard design; Opus for the replay proof.

**Rulings appended 2026-09-28: R-0572 to R-0575**, each with his words in the evidence file: no
editor opens from an event's words inside a cluster, ship without it, chat is the primary way
to edit (R-0572, supersedes R-0207); the timeline is not meant for selecting individual events,
only clusters (R-0573); a one-time exception to R-0417 for the first migration's table-order
rewrite, since that revision never ran in production (R-0574); development stays in one
worktree per ticket, not many branches, and the merge rules only guard master (R-0575).

**Rulings appended 2026-09-28, second batch: R-0576 to R-0580**, each with his words in the
evidence file: explain caches a cluster's play-by-play telling until its events change (R-0576);
the timeline's zoom stays exactly as it was before the pill strip, no new behaviour invented,
which leaves R-0381 standing (R-0577); every signal a learning loop is needed anywhere in the
app is tracked, dashboarded and queued for his later yes/no, kept to about ten items, refining
R-0517 (R-0578); a bad tool call from the coach is refused back to it with a warning log and a
retry (R-0579); replies to him name the actual table, column, file or screen, narrowing R-0523
(R-0580).

**Rulings appended 2026-09-26: R-0519 to R-0531**, each with his words in the evidence file:
the provisional label (R-0519), the coach's notes and their buttons (R-0520 to R-0522, R-0529),
how replies to him are written (R-0523), the frame first and in its own session (R-0524,
R-0525), the play-by-play bugs and the self-targeted event (R-0526, R-0527), italic names in
tool lines (R-0528), the deploy setting (R-0530), paying for a response once (R-0531).
R-0025, R-0484, R-0485, R-0520 and R-0521 gained a restatement.

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

**Review sandbox** (addresses use `turin`, never `turin.local`). Since 2026-09-27 the kit is in
the repo, `bin/sandbox/sandbox`, and the Sandbox section of CLAUDE.md has its commands. Each
instance keeps its data, logs and settings in `~/btcopilot-sandbox/<name>/`, outside every job
directory on purpose: a database inside a job directory is deleted with the job, and that has
already cost one sandbox. Postgres runs in a container per instance, the Celery worker uses the
solo pool because the default one crashes on macOS, the turn log goes through Redis so the
worker's events reach the page, and the coach runs on the local Ollama model (qwen3:8b) unless
`--real` is given.

- `up <name> <port> --dev` adds the Vite dev server on 8891 proxying to the instance, host
  header forwarded so sign-in and cookies mint for 8891; the service worker is off. **Patrick
  reviews at https://turin:8891/app/** and every saved front-end edit shows on refresh, no
  build. This is the dev mode he asked for [Oracle: R-0227]. The certificate is made by the dev
  CA his phone already trusts, kept in `~/btcopilot-sandbox/certs/`. A home-screen app on iOS
  keeps its own cookies, separate from Safari: the first open inside it shows the sign-in page,
  and the email code signs it in once; the sandbox sends no mail, so the code is in the
  instance's `flask.log`. An invite link opened from Mail signs in Safari, not the home-screen
  app.
- `invite <name> <email>` prints a sign-in link at turin under `--dev`, plus the same link at
  127.0.0.1 for this Mac. A sandbox link is reusable until it expires, so a walk can be
  repeated.
- A new database is made from the models and stamped at the newest revision, because the chain's
  first revision creates discussions before diagrams and an empty Postgres refuses that; an
  instance that kept its data is upgraded the way production is. Session history is kept across
  code changes [Oracle: R-0191]: `down` keeps the data, `down --purge` and `reset` do not.
- **On this Mac, open `https://127.0.0.1:8891/app/`, not turin** — the name turin only
  resolves over the network, and with Tailscale off the Mac cannot look it up. On his phone,
  on his own wifi, turin works.
- Patrick's own walks run on the `walk` stack at https://turin.humboldt-mine.ts.net:8898, not on
  8891; HOW_THIS_PROJECT_WORKS.md holds its rules.
- The FD-362 folder `/Users/patrick/worktrees/fd362-sandbox/` is kept for reference only. Its
  SQLite databases and the review-screen fixtures (the ballot, the votes, the coach replay)
  import modules the current code no longer has, so the table, ballot and meeting walks have no
  working fixture until those are rebuilt against the kit.

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
- **proto.html** (durable copy: btcopilot-sources/fd-corpus/design/proto.html; jobs-tmp original is ephemeral): interactive two-concept prototype — REJECTED by Patrick,
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
btcopilot-sources/fd-corpus/OWNER_RULINGS.md (2026-09-01). Reference HTML (durable):
btcopilot-sources/fd-corpus/design/move-language.html (ratified galleries) and drilldown.html
(three-level drill-down on two real records — KNOWN BUGGY; the rulings are the
standard, not the prototype). Three-level shape, REVISED 2026-09-03 by the UI
principle: wire with episode clusters → (the tap-zoom episode level is CUT; a tap is
point-and-ask) → moves step-by-step driven from the chat's play-by-play; words and
claims live in chat; loop engineering rules (all interactions collected). Next: build it on
FD-360 against his real record — brief in NEXT_SESSIONS.md.

On 2026-09-02 the picture design CONVERGED on the SENTENCE SPOTLIGHT — the coach's
latest message lights the events it names, the rest of the dots stay dim, and up to
three rows of words sit on the picture tied to their dots by leader lines (Oracle:
OWNER_RULINGS.md 2026-09-02; folder btcopilot-sources/fd-corpus/design/crowded-chapter/).
This supersedes the FD-360 resting strip as the picture reference. The fidelity
standard for every front-end build from here on is: playbyplay_ab.html pane A,
move-language.html + OWNER_RULINGS.md, crowded-chapter/, and DRAWABILITY.md — each
build is checked against them with an approved-vs-built deviation table.

## The corpus (system of record for phases A and B)

Location **btcopilot-sources/fd-corpus/** (moved 2026-09-02 from ~/fd-corpus, symlink left behind; his ruling: everything load-bearing consolidates into the PRIVATE btcopilot-sources repo — supersedes the older never-in-a-repo rule for this data); rebuild everything with
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
docs — btcopilot-sources/fd-corpus/clinic/index.json is always authoritative; recompute before use.**
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

- **Timeline navigation design pass (queued 2026-09-26) [R-0538]**: a Fable session draws the
  timeline's views as one drawing rather than separate redraws, each emphasising what it needs
  to without losing the whole; a visible path with a way back on every level; a cluster's name
  shown once it is opened; the reply-focused look Patrick misses today made reachable again.
  Shown to him as a mockup artifact, not built code. What the play-by-play draws stays with the
  frame session, not this pass.

- **Play-by-play rebuild, queued (approved 2026-09-27, "This all looks good. let's do it.")
  [R-0545 to R-0565]**: a real family diagram generated by code from the record, to the family
  diagram's own visual spec, drawn once per case with a fixed layout, marked up snapshot by
  snapshot rather than redrawn; opens as a full-screen drawer; one emphasis colour for the
  current step and grey for what carries forward; moves drawn the moves board's own way; a
  snapshot makes one point of order, of trouble moving between people, or of a move after an
  event, with a fact line, an optional "My guess:" line and a closing question; tap-through only,
  never self-playing; built only from Patrick's own family's cases from here on. Brief:
  `btcopilot-sources/fd-corpus/design/playbyplay-snapshots/BUILD_BRIEF.md` (copied there
  2026-09-27; written during the design session at
  `/Users/patrick/.claude/jobs/0b7dc61d/tmp/pbp/BRIEF.md`), section 3 lists what the mockup does
  not prove: the coach writing a snapshot's point, facts, guess and question live (needs real
  coach turns and a prompt eval after the build), a group or institution on the far side of a
  move having no drawing yet, and a whole-family layout as a separate later project.

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
  sources exist in btcopilot-sources/fd-corpus/design/ (his chat/journal corpus files) plus his
  live records; same synthesis machinery expected to apply.

- **Sleep and alcohol over time (queued, a Fable brainstorm after the frame session returns)**:
  Patrick wants the coach to see his own sleep and drinking over time; sleep is his S, and his
  Garmin watch tracks it. Open question: can Apple Health, Android Health Connect or Garmin's
  own data feed the timeline as S data, and do sleep and drinking matter across the wider market,
  not just for him. Assumptions to check, not yet verified: a web app cannot read Apple Health
  directly (would need a native app, an export file, or a paid aggregator); Garmin's own data
  API needs partner approval; Apple Health has a count type for alcoholic drinks; the cheapest
  path for one person is a periodic export, imported by hand. Whether sleep or drinking counts
  as an S at all is a question for the frame.

- **Event title, replacing description (queued 2026-09-26) [R-0534]**: what shows as an event's
  name would stay brief, only enough to pick it out from other events, with the longer account
  living in that event's notes instead. The field now called description takes the name title,
  with existing rows carried over. Watch for: the Pro app's diagram data reads that same field,
  so the switch reaches across repositories into familydiagram's scene code and its
  file-manager field lists.

## Jira / branches

- FD-359 epic (chat-first web app) with FD-360 (built, draft PR #133) and FD-361
  (corrections through chat — not started). FD-341 untouched as the June plan of
  record; FD-336 superseded as the first chat surface (in docs, not yet in Jira).
- The branch is `FD-362`, the same name in both repos, in the built-in worktree location.
  It carries decision log entries, the brainstorm docs, DRAWABILITY.md, this package, the
  schema comparison and the converter in btcopilot, and the oracle store in fdserver.
  btcopilot #136 is merged; fdserver #30 was closed unmerged (#135 and #29 are closed
  predecessors). The first fast-follow, FD-363 (PR #138), is merged. The second is FD-365,
  **draft PR #142**, with the sittings work (PR #144) and the landing page (PR #143) merged into
  it; everything for this work goes into Jira FD-365, with no new ticket.

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

## Open issues from 2026-09-30

FD-366 session. Each item: what was done, why it matters, what you decide.

### A. Architecture and tool choices made without your ruling

You rule keep, change, or undo on each.

1. **A new column on the model-calls table naming why each call was made**
   - Done: Every row in the model-calls table now has a required purpose from a fixed list: coach, shadow, proactive, replay, play, backfill, summary. Each place that makes a call fills it in. The migration labelled old rows from their turn id.
   - Why it matters: It changes a production table and every call site, and the fixed list is now what all cost panels group by.
   - You decide: Keep, change the list, or undo.

2. **The plain text model call now returns token counts and the answering model, and always writes a row**
   - Done: The plain text call (used for proactive messages, session titles and summaries) used to return only text. It now returns token counts and the model that answered, and every such call writes a model-calls row. The metering code moved into its own module.
   - Why it matters: It changes the return shape that other code depends on, and it is the reason spend for these calls is now visible at all.
   - You decide: Keep, change, or undo.

3. **Shadow turns run through a background job queue**
   - Done: Shadow turns and the backfill are queued as background jobs on a dedicated shadow queue, with its own worker container on the box. You told me you did not know background workers existed.
   - Why it matters: It adds a new running part to production, and how background work is designed is a decision you have not made.
   - You decide: Rule on whether background workers belong in the app at all, and if so how they are designed. Otherwise undo and run shadow turns another way.

4. **Tests run on SQLite while production runs Postgres**
   - Done: The purpose migration was first written with Postgres-only casts and failed the tests. It was then rewritten to go through the database layer so it runs on both. You want tests to stay on SQLite.
   - Why it matters: Anything Postgres-only (enum types, JSON casts) can pass here and break there, or the other way round.
   - You decide: Rule how Postgres-only features are handled when tests run on SQLite.

5. **The change-history writer records an empty list instead of null when a list field was absent before an edit**
   - Done: Taking back a later edit now leaves an empty list, not null. Five stored production rows were corrected by hand to match, with your approval.
   - Why it matters: It changes what the history table holds for every future edit of a list field.
   - You decide: Keep or change.

6. **The shadow backfill rebuilds the record before a past turn by rewinding the change history**
   - Done: It starts from today's record and undoes change-history rows newest first, including edits made by other authors after that turn.
   - Why it matters: The rebuilt record may differ from what the coach really saw at that moment, so the backfilled shadow answers may be judged against the wrong facts.
   - You decide: Keep, restrict to the same author, or undo.

7. **The Gemini client on the box uses the developer endpoint with the API key**
   - Done: One line was added to the box environment file. The compose file still passes a service-account path that points to an empty file.
   - Why it matters: Production depends on a hand-edited box setting that is not in the repository, and the leftover service-account path is misleading.
   - You decide: Keep, and whether the leftover path is removed.

8. **Grafana panels were re-cut by purpose**
   - Done: Real-spend panels exclude shadow. A new panel, Cost a day by purpose, was added. The quality dashboard's per-turn panels now count coach calls only, so play-by-play and backfill calls are excluded there too.
   - Why it matters: The numbers you have watched before will look different, and you did not choose that cut.
   - You decide: Keep or change which purposes each panel counts.

9. **The splash screen loads the app through a small boot file**
   - Done: The app script is loaded by a small boot file with a dynamic import so the stylesheet arrives before the app runs. The offline worker is now registered from the app script instead of on the page-load event.
   - Why it matters: It changes how the app starts, and offline registration timing changed with it.
   - You decide: Keep or undo.

10. **The shape of the backfill admin command**
   - Done: Run without a flag it only previews. With the flag it runs. The cost estimate is priced from the real turns' token counts.
   - Why it matters: It is the command that spends money, and its safety depends on you liking preview by default.
   - You decide: Keep or change.

26. **Letting the coach write its words to the person in the same model call as its last record edits**
   - Done: Today the turn loop throws away words written beside a tool call, and the prompt tells the coach to ask its question only after its tool calls come back (R-0482, because 3 of 75 turns ended with no reply). Doing it in one call would save about $0.027 per turn, the separate closing call, which is 26% of calls. The turn loop would have to change. The prompt variant is drafted and ready to measure.
   - Why it matters: It changes how tools interact with the coach's words, so it needs his ruling.
   - You decide: Whether the loop may keep words written beside tool calls.

27. **Trying two outside models as shadows**
   - Done: GPT-6.1 Sol costs about $0.18 to $0.21 a turn, needs an OpenAI key and a new client, and health-data terms apply only after OpenAI approval. Muse Spark 1.1 from Meta costs about $0.11 a turn, needs a Meta key, and is reachable through the existing Anthropic-format client with a small routing change. No training, retention or health-data terms were found for it.
   - Why it matters: Clinical text would leave the current providers.
   - You decide: Which keys to create, and whether clinical text may go to either.

28. **The queued measurement spend**
   - Done: Replay his 13 turns on Opus 5.5 three ways: the current prompt at medium thinking as the baseline on the new layout, low thinking, and the batch-edits prompt variant. About $2.50 a run, $7.50 total. Plus one run on Gemini 3.1 Pro Preview through the existing Google client, about $2.50. The free routes cannot show it: the subscription replay gives no thinking control and the local model is not Opus.
   - Why it matters: Whether low thinking or the batch-edits prompt saves money without hurting replies cannot be judged without it.
   - You decide: Answer "go" or a number.

41. **For auditors, a coach reply with no saved note shows no (i)**
   - Done: Guillermo's case, 2026-10-01: 42 of his 45 replies have notes. The three without are the opener, a reply that only edited the record, and a play-by-play. Recommended: show a greyed (i) that reads "No notes for this reply" on tap.
   - Why it matters: Today an auditor cannot tell a missing note from a broken button.
   - You decide: Show the greyed (i) (recommended) or keep it hidden.

### B. Defects and unproven things

You rule fix now, later, or accept.

13. **Cluster regrouping model calls are not recorded at all**
   - Done: They never write a row in the model-calls table.
   - Why it matters: Their cost is invisible in spend panels.
   - You decide: Decide whether to record them and under which purpose.

15. **Production ran the previous image for about 15 minutes on 2026-09-30**
   - Done: The database carried the new migration while the app ran the old image, because a bare container restart dropped the image tag. No real turns fell in the window. The deploy README now says restarts must carry the tag.
   - Why it matters: It can happen again if someone restarts without the tag.
   - You decide: Decide whether a guard against it is worth building.

16. **45% of coach turns start more than 5 minutes after the previous one and miss the prompt cache**
   - Done: Keeping the cache alive would conflict with R-0595.
   - Why it matters: Those turns cost more than cached ones.
   - You decide: Rule whether R-0595 yields, or the cost stays.

17. **14 older coach replies on your account have no turn id**
   - Done: The backfill skipped them.
   - Why it matters: They have no shadow answers to compare.
   - You decide: Decide whether to leave them out or link them by hand.

20. **Tailscale on the Mac was stopped**
   - Done: That broke the phone link to the test stack.
   - Why it matters: Your phone walks fail until it is running again.
   - You decide: Turn it back on before the next walk.

11. **The rewritten purpose migration has not been run on Postgres**
   - Fixed 2026-09-30: The migration was proven on a fresh Postgres database from empty, and old rows were relabelled correctly.
   - Done: Production already carries the column from the earlier version of the migration, so the rewrite has only run on SQLite.
   - Why it matters: A fresh Postgres database built from the migrations could fail or differ from production.
   - You decide: Decide whether to have it run on a scratch Postgres database before the next migration.

12. **The fallback column on model calls reads as set on every row**
   - Fixed 2026-09-30: Fixed on the branch. The column stored a JSON null instead of an empty value. Old production rows need a one-off correction on the next deploy, which Patrick approves.
   - Done: It shows 100% while the real rate is 0%. This is a bug in how it is stored.
   - Why it matters: Any panel or question about fallbacks reads wrong.
   - You decide: Decide whether to fix it now.

14. **The coach eval judge and the synthetic-client helpers are changed but not run**
   - Fixed 2026-09-30: Fake-model tests now cover the judge and the simulated client reading the metered text reply. The persona generator and quality scorer still lack one.
   - Done: They were updated for the new text-call return shape. They make real model calls, so they were not run.
   - Why it matters: They may be broken and nobody would know until a run.
   - You decide: Decide whether to spend on one run, or check them another way first.

18. **The theory reference page is over its length limit**
   - Fixed 2026-09-30: The reference is at 7,459 corpus words (8,053 plain count). Remaining passages are all tripwires, open items, principles or the source index. The citation is corrected. Sources commit 739ec3c.
   - Done: It is 9,292 words against a 7,000 target and a 9,000 cap. One citation there points at line 93 of Bowen's chapter 9 in the source, where the text now sits at line 95.
   - Why it matters: It breaks the cap you set, and the citation is stale.
   - You decide: Decide whether to cut it now or later.

19. **Sub-agents could not enter the FD-366 worktree**
   - Fixed 2026-09-30: Cause found: this session runs from the sources repo, so the worktree tool treats the app repo's worktrees as foreign. Sessions on app tickets start in the app clone. No code change.
   - Done: The tool refused with a message that it belongs to another repository. Builders worked by absolute path.
   - Why it matters: Any rule that relies on entering the worktree does not hold for sub-agents.
   - You decide: Decide whether this is accepted or worth fixing.

25. **The shadow "sonnet" alias resolves to Sonnet 5.5**
   - Fixed 2026-09-30: The shadow "sonnet" alias is Sonnet 5.5, priced at the same rates as Sonnet 5 per the price sheet. Verified against 60 production calls with $0 difference. A test pins it.
   - Done: The alias points at Sonnet 5.5, which the price sheet prices the same as Sonnet 5.
   - Why it matters: A wrong rate would misstate shadow spend.
   - You decide: Nothing.

29. **The fixed coaching text is now cached ahead of the record**
   - Fixed 2026-09-30: The fixed coaching text (about 3,700 tokens) is cached ahead of the record instead of rewritten every turn. The part rewritten each turn fell from about 13,900 to about 1,100 characters plus the record. Behaviour unmeasured, by Patrick's instruction.
   - Why it matters: Nothing open.
   - You decide: Nothing.

30. **The coach's tool definitions were shortened**
   - Fixed 2026-09-30: They were cut from 22,989 to 15,259 characters (about 2,270 tokens), keeping every rule stated nowhere else. Rules that only the record-editing tools carried now sit in the scribe's prompt. About $0.007 per turn.
   - Why it matters: Nothing open.
   - You decide: Nothing.

31. **The cache-hit panel shows dollars by kind**
   - Fixed 2026-09-30: For coach calls it now shows dollars for cache write, cache read, output and uncached input, the gauge the cost follows.
   - Why it matters: Nothing open.
   - You decide: Nothing.

32. **Re-asks inside a turn are not worth a change**
   - Fixed 2026-09-30: Re-asks (shorter labels, sentences instead of chips, words after a silent stop) fired five times in two weeks and never since 23 Sep.
   - Why it matters: Nothing open.
   - You decide: Nothing.

33. **The replay tool can vary thinking, prompt and turn count**
   - Fixed 2026-09-30: It can run one person's turns under a thinking level, an alternative prompt file, or a turn cap, and prints cost and score. A "gemini-pro" alias for Gemini 3.1 Pro Preview exists, with its own price row.
   - Why it matters: Nothing open.
   - You decide: Nothing.

38. **Play-by-play: the symbols are drawn at different sizes that are not right**
   - Done: Queued, not started. Patrick reported it on 2026-10-01.
   - Why it matters: Symbols of different sizes make people look different in importance when they are not.
   - You decide: Nothing yet.

40. **Timeline strip: a page cut short when the picture folds**
   - Done: If a cluster's page or a two-event comparison is open when the picture folds, the strip shows that page cut short instead of the line. Found 2026-10-01 during the strip build. Not fixed.
   - Why it matters: The folded picture shows a broken page instead of the line.
   - You decide: Nothing yet.

### C. Housekeeping

21. **Queued rulings wait for your key**
   - Done: R-0619, R-0622, R-0623 and R-0624 and the note that R-0618 supersedes an earlier ruling are queued. R-0620 and R-0621 were demoted to decisions.
   - Why it matters: The rulings store does not yet say what you said.
   - You decide: Provide the key so they are written, and confirm the two demotions.

22. **26 shadow answers on your account await your picks**
   - Done: They are in Better replies.
   - Why it matters: Shadow quality cannot be judged until you pick.
   - You decide: Pick when you have time.

23. **The coach-started email needs a design pass**
   - Done: Nothing more should go out before it gets one.
   - Why it matters: Another send would repeat the unreviewed design.
   - You decide: Decide when the design pass happens.

24. **Parts of the ticket are still unbuilt**
   - Done: Not built: the coverage checklist and its panels, the conversational regression test, the coverage-efficiency experiment, and the pick-notes rubric. Also unbuilt: the low thinking setting and the batch-edits prompt, both waiting on the measurement in item 28.
   - Why it matters: The ticket's acceptance criteria are not met without them.
   - You decide: Decide the order, or drop any.

39. **A way for the person to search their own chat messages**
   - Done: Design not started. Patrick asked for it on 2026-10-01: "we need a way to search chat messages". The coach already has a search tool over the chat; the person has none.
   - Why it matters: People cannot find what they said earlier.
   - You decide: Decide when the design starts.
