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

A build session produced a running app on the approved design: `/companion`, behind the
existing login, wired to the real backend, run from this worktree on port 8889 against a
scratch database holding Patrick's own record. Draft PRs: btcopilot #135, fdserver #29.

**Patrick's live assessment of it (2026-09-03), carried verbatim because it is unresolved:**

> "This feels like our core vision for this is not yet stable. The goal is to make chat
> the UI for everything. I do not want the user to have to worry about complicated edit
> dialogs, they are just there in principle, not as part of the main user journey. I
> originally entitled this new project as Claude Code for Family Diagram. So it sounds
> like this code is crippled for a number of reasons partially from the original vision
> not being clear, and partly because you didn't complete the runnable code — and there
> is nothing more to test in this code than what I had already tried out in the
> familydiagram frontend?"
>
> "We need to take a step back and clarify the entire vision so that tactical questions
> about what to add into this demo are properly aligned and not band-aids."

Facts bearing on that, established rather than inferred:
- R-0055 rules that chat tool calls control everything with full bidirectional
  reactivity. The built app has **no tool calls** — the coach talks and points at the
  record but cannot change it. Manual editing works. The build inverted the ruling.
- **No user journeys or stories exist in any document.** This is why the build could be
  specified wrongly without anyone noticing.
- Ruled good during the build: the play-by-play, the coach-driven picture, and the
  chapter view that shows no words until the coach names them or you tap.
- Unverified: whether a live coach actually cites the reference index it is given.
- Never ruled: the fate of the pending-extraction pool (see ARCHITECTURE_HANDOFF.md).
- Storage under it is a pickled whole-document write under an optimistic lock; the page
  is hand-written JavaScript where the ruling says a Vite/TypeScript PWA. That page is to
  be rebuilt as the Vite page for the beta build.

Landed on this branch since: the schema comparison (commit 268e74a) and the JSON-record
proof with its converter (commit f32eb2c).

## Prototyping status (honest)

- **FD-360 page** (PR #133, draft, worktree ~/theapp/btcopilot/.claude/worktrees/FD-360):
  works and independently verified — chat through the real coach pipeline;
  session-cookie auth bridged WITHOUT touching the HMAC path (tested); CSRF added;
  per-person timeline math with a regression test against the Qt app's
  mixed-people-sum bug; resting strip obeys the three-mark rule; tap-a-mark speaks a
  plain sentence; seeded or real-record sandbox on 8889 (relaunch command in the PR /
  worker report; real-record DB at /tmp/fd360-sandbox.db). **Ruled good**: the
  narrow-lane always-on resting strip; inline chips in coach text aiming the picture.
  **Ruled not understood**: the expanded/detail view — Patrick's walk found it
  illegible on real sparse data; it is a placeholder pending ground-up design FROM
  the corpus analysis. Era-compression work exists reverted-but-recoverable at commit
  35dd13b — NOTE: that is one of the two contaminated commits, so a history purge
  deletes it (re-implement from HISTORY's description if purged).
  Rebuild/reseed: `python -m btcopilot.companion.seed <username> --from-lanes
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

**The journeys that check the build** [R-0087]:

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

**Build brief.** An Opus session starts from this file alone. It works in the FD-362
worktrees, code in btcopilot and prompts in fdserver, and builds the Vite/TypeScript page on
the ruled front-end shape: passwordless login, the real database, JSON diagram data through
the converter, the Change and Interaction models, tool calls, chips, the play-by-play, and
the timeline and editor behind a menu. It checks itself against journeys 1 through 6. The
draft PRs already exist: btcopilot #135 and fdserver #29.

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
  Draft PRs: btcopilot #135, fdserver #29.

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

## What's next — the architectural step back (CLOSED 2026-09-07)

All six items are ruled. Where each one landed:

1. **The UI principle** — [The UI principle](#the-ui-principle-ruled-2026-09-03--step-back-item-1).
2. **The Pro app** — [Architecture and data](#architecture-and-data-ruled-2026-09-07): nothing is ruled, deliberately.
3. **User journeys** — [Beta build](#beta-build-ruled): the six that check the build, and the deferred seventh.
4. **Architecture as a concept** — the show tool in [The UI principle](#the-ui-principle-ruled-2026-09-03--step-back-item-1); the pending pool dropped, no PDP in the beta build.
5. **The data format** — [Architecture and data](#architecture-and-data-ruled-2026-09-07): JSON record, change log, additive shapes.
6. **Front-end shape** — the Vite page in the build brief under [Beta build](#beta-build-ruled).

The next session is the build, not another brainstorm. Its brief is under Beta build.

**Session discipline (ruled 2026-09-07, R-0088).** The big model is for concepts only: it
rules and it drafts. Sub-agents do all reads, writes, git and builds — Opus for work to a
spec, Sonnet where quality is unaffected. Rulings are written to the store at the end of a
session in one pass, not as they are made. Every claim is labelled evidence or assumption;
stating something as fact without evidence is lying. Plain sentences, Patrick's own terms,
no coined labels, and no multiple-choice when he asked to brainstorm. For verification, a
test script through the Pro app's own loading code plus his eyeball beats an agent driving
the released app. Read this file to start; read HISTORY only for a specific fact.

Pinned (not next): the corpus/subset sessions in [NEXT_SESSIONS.md](NEXT_SESSIONS.md).
