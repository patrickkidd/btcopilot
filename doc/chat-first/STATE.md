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

All drawing/asking rules are canonical in [../DRAWABILITY.md](../DRAWABILITY.md)
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

**Branch `FD-362` in both repos; draft PRs btcopilot #136 and fdserver #30.** The beta build
is real code against the real database, not a throwaway.

**What the Personal app does today.** A signed-in person chats with the coach. The coach
answers and calls tools that add, change and remove people, pair-bonds, events, variable
shifts and clusters; each edit is named in the thread in its own formatting, and the picture
and the lists change as the reply lands. One picture rides pinned above the chat in a fixed
132px region, with three levels: clusters over time at rest, one cluster open on a tap, and a
moves board for a play-by-play. A lower level slides in from the right as a card over the
level it came from, and back reverses it. The grey line above the picture is the title of the
level you are on, with a back arrow beside it; tapping either goes up one level. Under the
picture, one chip row — ask, explain, in chat, and the list button — reads the same however
the level was reached. The list button opens one drawer with Events and People tabs, each row
opening an editor with 44px fields; a person's birth and death jump to those events and back.
A sessions sheet holds past sessions with rename and sort. The account page slides over the
content. Sign-in is passwordless from an emailed invite link and lasts 180 days. A send that
fails says which of three things happened and offers to go again. Three dots show while the
coach is thinking. Every word the app says is selectable and copyable. Users see the name
"Family Diagram" everywhere; "Personal app" is the internal name only.

**Patrick reviewed it on his phone over four rounds, 2026-09-08 and 09**, and his word at
the end of round 4 was that it is ready for him to start using like an app on the phone from
the home screen. Every finding, round by round, with the commit that fixed it:
[REVIEW_LOG.md](REVIEW_LOG.md), 66 rows. Rounds 1–4 are folded into the oracle store as
R-0165..R-0228.

**Built 2026-09-11/12 on the same branch, unreviewed by Patrick:** the review's tables
(`review_cuts`, `review_codings`, `review_items`, `review_votes`, `review_rules`, one column
`discussions.kind`, the branch's `changes` and `interactions` renamed `diagram_changes` and
`diagram_interactions`) in an isolated package `btcopilot/review` with endpoints, the coach's
replay as a task and the export; and the coding screens — the one-task card, the read-only
thread up to the cut, the scribe on a cheap model with the record's tools, Done in the title
row with a confirmation, the guidelines behind (i). Review and personal suites 431 passed. Two
independent browser walks on a fixture account found and closed three defects; a last browser
re-check of the drawer refresh and the pronoun guard was still running at the flush. The design
of every screen is ruled and drawn in `doc/chat-first/mockups/` and the catalogue for beta
users; `doc/chat-first/REVIEW_TABLES.html` is the database scope of the pull request. Next:
Patrick tests the coding screen at https://turin:8891/personal/ (the one-task card is the first
screen), then the remaining build steps in the ruled order.

**His own record is small**: seven events, and one cluster he made himself holding two events.
It predates the three-event floor and is grandfathered; see Open issues.

**Review sandbox** (addresses use `turin`, never `turin.local`; the API is started with the ABSOLUTE database path; the sandbox's error mailer recipient is blank). Durable scripts live in `/Users/patrick/worktrees/fd362-sandbox/`, outside
every job directory on purpose: a database inside a job directory is deleted with the job, and
that has already cost one sandbox.

- `serve.sh 8890 beta2.db` — the Flask API from this worktree, bound to every interface, no
  reload, so a Python change needs a restart.
- `dev.sh` — the Vite dev server on 8891 proxying to 8890, host header forwarded so sign-in and
  cookies mint for 8891; the service worker is off. **Patrick reviews at
  https://turin:8891/personal/** and every saved front-end edit shows on refresh, no
  build. This is the dev mode he asked for [Oracle: R-0227].
- `invite.sh <email>` — a sign-in link at turin, not 127.0.0.1, so his phone can open it.
  A phone already signed in needs no new invite.
- `env.sh` — the settings both scripts source, including the path to the private prompts in the
  fdserver worktree.
- `beta2.db` is the review database: never seeded, never wiped, backed up before any restart,
  migrated with `flask personal migrate`. Its session history is kept across code changes
  [Oracle: R-0191].

**Suites (re-run 2026-09-09 evening).** Backend Personal tests: 389 pass, 23 skipped, run in
this worktree; the whole backend was last recorded at 905 passed, 33 skipped. Web unit tests:
44 pass, 10 fail — all ten are assertions written before the round 2–4 rulings (a second tap on
the picked moment now leaves it picked; the spotlight rows; cluster chips by cluster id; the
reload step the turn handler no longer sends) and not yet rewritten to them. The 95 visual
tests were last recorded green on a Mac. Continuous integration fails on this branch (unit
tests and visual both red on the pull request), and neither suite has ever been watched green
on a runner; the causes are under Open issues.

**Found by Patrick testing alone, 2026-09-09 evening** (rows 67–69 of the review log): a
failed coach turn used to leave the user's words stored, so a retry stored them again — fixed,
the words now land only with the coach's answer, and a second send while one is in flight does
nothing. One tap posted learning data with no item kind and is not yet identified. The coach in
the sandbox is down until the Anthropic API account behind the key has credit again.

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
[ISOLATION_OPTIONS.md](ISOLATION_OPTIONS.md) maps what this branch touches — 249 files in
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

**Where the beta runs is not yet ruled.** Two shapes, decision pending with Patrick:
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
2. **Deploy on the existing production server, merge first** [his direction 2026-09-10]: a
   read-only review of every table and endpoint change against master is being written to
   doc/chat-first/MERGE_REVIEW.md; nothing merges before he has read it.
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

[UI_GAP.md](UI_GAP.md) marks thirteen rows NEEDS-OWNER: the build differs from a value that
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
  Rebuild/reseed: `python -m btcopilot.personal.seed <username> --from-lanes
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

**The coach never hands over the chalk.** Every tap on the picture loops back into the
chat as communication to the coach, exactly like a spoken turn; visual input that does
not return to the chat flow becomes a separate process and spawns UI and user-story
complexity. One core engine — the agent loop — is everything; inline chips, what a tap
sends back, and how the picture is aimed are harness. [Oracle: R-0065]

- The picture is exceedingly simple: it shows as much as it can without crowding and
  without requiring a tap for everything; a crowded visual (the wire timeline) means it
  is doing too much. One tap to reveal a title is acceptable. [R-0066]
- The tap-zoom cluster view (level 2 of the three-level shape) is CUT: tapping a cluster
  is point-and-ask, and the cluster's words live in the chat via the play-by-play, never
  in a navigable data view. The move step-through (level 3) survives, driven from chat.
- One consistent visual mark says "this tap puts words in the chat"; anything without
  the mark never costs a turn. Users control both tokens and flow. [R-0068]

UI_SPEC.md (doc/chat-first/) is the exhaustive canonical record of every
approved UI element — 441 rows, each with the exact value and its owner source.
UI_GAP.md is the live approved-vs-built table. Every front-end build works row by row
from UI_SPEC, and is verified against it — prose in this file never outranks UI_SPEC on
a UI question. 36 rows in UI_SPEC are marked "Needs Patrick's ruling" and are open.
- Manual editing is NOT under test. The MVP is feature-complete only with the agent loop
  and real-time tool-call edits (R-0055 restored); an include/defer feature list is
  confirmed by Patrick before build. [R-0067]
- The prototype's full timeline + event editor stays as designed, behind a menu, off the
  main journey, with a one-line banner that editing by chat also works. [R-0069]
- Play-by-play via a button that jumps to a complete, digestible concept is fine
  (digestibility is a user test); drilling one datum at a time is rejected. [R-0071]
- Every designed feature carries the learning loop: it generates data and corrections we
  learn from. Part of principle one, product-ownership-wise. [R-0070]

Ruled 2026-09-07, closing every sub-ruling that was open here:

- **Chips are the primitive.** A chip is a reference into the record — an event, a
  cluster, a person — and it renders as a chip in coach messages and in the user's own
  messages. Tapping one drops the reference into the user's message and they type their
  own words; a reference sent bare means "tell me about this". A chip tap is the user
  speaking as themselves, never steering the coach. [Oracle: R-0072]
- **Two taps on the picture.** The first tap looks: a title or caption, free, nothing
  enters the chat. The second tap is a chip and speaks. The chip IS the standard visual
  for "this puts words in the chat", so nothing else ever costs a turn. [R-0073]
- **The play-by-play is coach-authored.** The moves are data and animate deterministically;
  the coach writes the words around them, picks which moves and in what order, makes each
  move a chip, and cannot invent a move. It ends in offered chips. Chosen over
  app-generated captions from a side-by-side mockup. The tap-zoom cluster view is
  cut. [R-0074]
- **The show tool.** Anything deterministic is a tool call with parameters. The show tool
  takes record ids plus a closed set of view kinds — to start: a triangle over three
  people, a span over a time range, two moments compared, a sequence of moves. Every
  parameter must resolve to stored data or the call fails. Fidelity to what the user said
  is enforced by the tool's design, never left to the model. Each view kind added must
  show something meaningful; start simple and extend one view at a time. [R-0075]
- **Every tap is learning data**, including the looks that send nothing, and the coach sees
  them as context. First entry on the A/B-test list below. [R-0077]

## Architecture and data (RULED 2026-09-07)

What the record holds today, field by field with line references, is in
[SCHEMA_COMPARISON.md](SCHEMA_COMPARISON.md). This section is what was ruled on top of it.

- **Clusters are model-derived and stored**, which is what the data model already does. The
  model may group and name; it may never invent a member; the user corrects it. Triangle
  moves already live on the event, in the relationship field and its target and triangle
  lists. [Oracle: R-0076]
- **The client owns their record.** A clinician is granted access to it. The client pays
  for their own chat and keeps the record outside and after their sessions with the
  human. [R-0080]
- **Nothing is ruled about the Pro app.** Its role and its stack are both open; everything
  said about Pro this session was brainstorm input, and no irreversible decision about Pro
  is to be made. The chat app must not corner it. [R-0081] Proposed and unratified, held as
  an interim only: Pro reads a chat-app record and only the chat app writes it, until
  multi-writer merge exists. [R-0082]
- **The record becomes pure JSON.** The diagram data column stops holding a pickle; Qt
  values are written as tagged plain types. The server converts back to pickle whenever the
  released Pro app asks, so Pro is unchanged. Open formats, statically typed, reusing the
  existing structure so the migration path is clear; better features outrank backward
  compatibility and Patrick judges those himself. [R-0083] Proven: the round trip is exact
  on three fixtures and on 1997 of 1998 real diagrams, and the single failure never
  unpickled in the old code either; the result loads through Pro's own read path. Converter
  at `btcopilot/diagramjson.py`, commit f32eb2c.
- **A change log beside the record.** A new model, Change, sits next to Discussion and
  Statement: one row per command, whether a tool call, a Pro save, or a manual edit,
  carrying a list of deltas of item, kind, field, before and after. A turn id groups a
  macro — one coach reply, or one save. Consecutive deltas on the same item and field
  compress at write time, keeping the first before and the last after. Rows carry user and
  session. The server applies commands in arrival order, one at a time per diagram. Undo is
  per user per turn, by inverse deltas with compare-and-set on the before value. Multiple
  readers and writers are required, and the log stays separate from the record so history
  can be compacted later. [R-0084]
- **New shapes, all additive.** Chip reference tokens live inside the statement text and are
  validated against the record on write. Coach statements gain a views field: a view kind
  plus its parameters, where every id must resolve. A new Interaction model records who
  looked, said, tapped a chip, or played, against which item and when. Cluster gains a name
  and a source, model or user. Pins are a list of references on the discussion. The rule
  behind all of it: what the picture draws lives in the record, and who did what when lives
  in tables beside it. [R-0085]
- **No PDP in the beta build.** Coach edits apply immediately as change rows and correction
  happens through chat. Exploratory — Patrick's words were "let's play with no PDP". [R-0086]

## Beta build (RULED)

**The next build is the beta build, not a throwaway** — passwordless login and the real
database, everything beta users need today. [Oracle: R-0078]

In: chat by text, with phone dictation covering voice; the agent loop with tool calls that
add, change and remove people, pair-bonds, events and variable shifts, live in both the
picture and the list, reversible by telling the coach; one pinned picture showing clusters
over time at rest, aimed by the coach's chips; a play-by-play per cluster behind a button;
the look/say tap semantic; steering chips; the timeline and event editor behind a menu with
the line saying you can also edit by chatting; every tap, chip, correction and coach edit
recorded; Patrick's own record.

Deferred: proactive messages; a "what you said" provenance view; lane pinning; Pro
migration; notability import; sharing; a formal undo stack beyond per-turn; era
compression; death and fade stops.

**First users** [R-0079]: the app working group, three clinicians, iterated with until the
thing is extremely valuable. Then the app seminar, three more. Then the wider Bowen
network. Names live only in the private oracle evidence.

**The journeys that check the build** [R-0087] — walked PASS 2026-09-08:

1. A first conversation from an emailed link, no password, the picture growing from nothing.
2. A correction through chat changes the event in place with a change row, and old chips
   still resolve.
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

- **One selection state.** A chip tap is a dot tap: spotlight, plus a caption row carrying
  the ask chip, the board button and the "in chat" chip. That row reads the same whether a
  cluster is open or an event inside it is selected.
- **Chips are one size, full text**, never truncated and never expandable. Labels are capped
  at the source at 28 grapheme clusters with one re-ask, never trimmed afterwards. Every chip
  has a pressed state.
- **The board fits its content.** This superseded the fixed 264px rows; every UI_SPEC row
  carrying RESOLVED #28 is superseded by it. Its control row is always back, explain, forward,
  with explain dead only while the coach is answering the last one. The way onto the board
  from the timeline is the play mark alone, no words.
- **A play-through holds each move** until its narration line finishes typing plus about two
  seconds. The eight-second animation loop is a separate clock and is never stretched to
  match. Step chips move the board and never return to the timeline.
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
  spec = doc/NOTES_TO_DIAGRAM_PIPELINE.md (schema v0 awaiting his markup) (marker density, span, people) → Patrick
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
  **Draft PRs: btcopilot #136, fdserver #30** (#135 and #29 are closed predecessors).

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
- Every claim is labelled evidence or assumption. Plain sentences, his own terms, no coined
  labels, no multiple-choice when he asked to brainstorm.
- Read this file first. Read HISTORY only for a specific fact.

Pinned, not active: the corpus/subset sessions in [NEXT_SESSIONS.md](NEXT_SESSIONS.md).
