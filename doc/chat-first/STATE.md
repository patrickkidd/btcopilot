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

The beta build is on branch FD-362 (draft PR btcopilot #136, fdserver #30), current
through the overnight run: night-symbols (commits 94410f7..6bec01e), night-shell
(b95d79e, a75e077, 7a8d49a), and night-shell-2 (c18d74a..2c2ac86, which includes a
revert at 0d1bfc1 — a filter-based screen-dim night-shell added was found to double up
on the sessions-sheet scrim, which already dims the screen on its own, so the filter was
taken back out). Full range: `git log --oneline -20`.

**Personal API consolidated (2026-09-08)**: the browser app's routes are the personal
API, served at `/personal/` on the session cookie, and the old Qt Personal app's
signature-authenticated routes are unregistered under `btcopilot/personal/archive/`
with their tests. Everything the page fetches moved from `/companion/` to `/personal/`,
including the service-worker scope, the manifest and the bundle path, and the Flask CLI
group is now `flask personal`. A cold-start circular import in the personal blueprint's
auth binding is fixed (commit 2117528).

**Resolved overnight, previously listed as still open from owner review round 1**:
play-by-play step chips now route on the page (a teal chip opens the board on its
stretch, or steps it to the move it names, and never returns to the timeline — commit
9140a66, independently re-verified green in the night-shell-2 sandbox); the board's SVG
height is no longer fixed at 264 inside the drawing — `board()` and `triangle()` now
return a height, so a cast of three no longer leaves an empty band (commit 94410f7);
visual tests that pin a ruling now cite it by id, `[Oracle: R-NNNN]` (commit 2c2ac86).

**Still open from owner review round 1**: the event editor lacks the relationship field
and relationshipTargets/Triangles/Intensity, and the person/spouse/child conditional
visibility by event kind (mirror Pro's rules); a client-side chip clipping line in
chips.ts needs removing. Sandbox note below supersedes the earlier one — read it before
touching the sandbox.

**Suites.** Backend: 905 passed, 33 skipped, run against this worktree after the personal
API consolidation (the drop from the prior 982/37 is old Qt Personal app tests archived,
not lost coverage — new coverage was added alongside: play.spec.ts, gestures.spec.ts).
Visual: 95 green on the phone viewport at the last recorded run. Neither has been watched
run green on CI.

**Spec and gap.** UI_SPEC.md carries 444 value rows, 52 resolutions and 3 open items.
UI_GAP.md sets every one against the build, folded with the overnight builders'
findings and regenerated by `tools/ui_gap_counts.py`: MET 318, PARTIAL 11, CHANGED 12,
MISSING 5, NEEDS-OWNER 13, UNCHECKED 16, N/A 76, over 451 rows.

**NEEDS-OWNER — needs Patrick's word, listed by name (UI_GAP.md carries the full
detail on each)**:
1. Crumb line — the ruling says the line above the picture is empty at rest and carries
   the year range only at chapter level; the build keeps a permanent left label reading
   "FAMILY TIME LINE" instead.
2. Title row padding — mockup pads 14px with a 10px gap; build pads 10px with an 8px
   gap so the 44px controls reach the edge; moving to the mockup shifts every golden
   that includes the row, for 4px.
3. Picture container padding — mockup is `4px 10px 8px`; build is `6px 0 4px` with 16px
   gutters; a difference the row itself calls a hair, moving every picture golden.
4. Spacing, chat and message bar — UI_STANDARDS asks 16px gutters; both converged
   mockups write `padding:14px 12px` on the chat; build matches the mockups at 12px/10px.
5. Data chip fill, play-by-play — pane A's mockup draws a filled teal-soft pill at
   12.5px, under the 13px text floor; build draws an outlined 13px pill; adopting the
   fill moves nearly every chat, picture and board golden for a colour change no ruling
   reaches.
6. Drawability marks, which level draws them — built only at the level where the coach
   has named something, never at rest, because the middle (chapter) level is cut; no
   rule says this is the right level.
7. Drawability marks, geometry — no mockup fixes the tick's 10px height, the flat
   mark's 14px width, the step line's 6px offset from the wire, the guessed-date band's
   cap at an eighth of the wire, or the open-ended fade's run length; all five are
   builder choices.
8. Step line on alternating data — on data that alternates up and down every month the
   step line reads as a zigzag woven through the dots; whether a trend should draw at
   all at that density is a judgment call.
9. New session refused on another family — the build now switches the app to that
   family and starts the session there rather than refusing; whether "+" should switch
   families at all is still open item 1 in UI_SPEC.
10. Count chip inside coach prose — a dense chapter's count ring already opens the
    chapter when tapped at the resting level; a count chip written into the coach's own
    prose is not built, and no rule says the coach may write one.
11. Historical coach messages carry chips — the spec row says a reopened session's old
    coach messages carry no chips; the build renders them, and journey 2 requires the
    old chips to still resolve, so the two readings cannot both hold.
12/13. `triangle` and `compare` drawings (pre-existing, open items 2 and 3 in UI_SPEC) —
    no mockup fixes either geometry; both are drawn from the nearest approved concept
    with no source ruling them in.

**The three things no rule reaches**, stated in full with their alternatives at the foot
of UI_SPEC.md: (1) what tapping "+" on a family the app is not on should do (item 9
above); (2) how a close-up triangle is drawn (item 12 above); (3) how two moments are
compared (item 13 above).

**The felt call.** A move holds about one second on the board while its own animation is
written to run eight, so each move is cut off early when a stretch plays through.
Resolution 21 rules the 8-second loop and the per-move advance as two separate cadences,
so the build is not wrong, only fast. Whether it feels right is Patrick's to judge.

**What he will see that is still open** (narrowed after the overnight fold — several
items previously listed here are now built: the freshness banner, the title's own
family name, the sessions-row swipe gesture, the sort-order hold, the question-mark
breathing, and the chat fading on a session swap):

- **Two remaining picture-vocabulary judgment calls**, both above: the drawability
  marks' level and their geometry have no ruling, and a dense alternating record draws
  a zigzag that may or may not be the right thing to draw.
- **The chat does not fade when the picture changes level** (it does fade on a session
  swap, which is a different trigger).
- **A long press outside a session row does nothing** — the session-row long press
  (rename) is built; a card title, a crumb or a list row still has no long-press
  handler.
- **The line always fits the width**; he cannot pan or zoom it. Neither mockup pans
  either, so this may be a requirement that outlived its design.
- **The one thing only he can answer**: whether each move reads without a legend, and
  whether the coach's words and the drawings tell the same story.

**Review sandbox — READ BEFORE TOUCHING.** The durable script and database are
`/Users/patrick/worktrees/fd362-sandbox/serve.sh` and its `.db` files in that same
directory — never an agent job's tmp directory. That rule exists because it was broken
once already: a prior job directory was deleted on a session restart and took the
owner's `beta.db` with it. The stranded record from that database survives nowhere
except inside the still-running process on port 8889, pid 86248 — that process must NOT
be restarted, killed, or reused until Patrick decides how (or whether) to recover the
data from it. All new sandbox work goes on port 8890 against the durable script and
database above, with fixtures `play` and `dense60` installed and invite links
single-use.

**Sandbox recipe (port 8890, durable location).**
`/Users/patrick/worktrees/fd362-sandbox/serve.sh 8890 <db>` runs it. From ~/theapp:
`PYTHONPATH=<btcopilot worktree> FLASK_APP=btcopilot.app:create_app
FLASK_CONFIG=development FLASK_SQLALCHEMY_DATABASE_URI=sqlite:///<db>
FDSERVER_PROMPTS_PATH=<fdserver worktree>/prompts/private_prompts.py uv run python -m
flask run -p 8890 --no-reload` after `npm --prefix web run build`; then `flask personal
migrate` if the database predates a schema change, and `python -m btcopilot.auth.invite
<email>` for a single-use link. No auto-auth.

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
a UI question. 36 rows in UI_SPEC are marked "Needs the owner's ruling" and are open.
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

**Build brief.** An Opus session starts from this file alone. It works in the FD-362
worktrees, code in btcopilot and prompts in fdserver, and builds the Vite/TypeScript page on
the ruled front-end shape: passwordless login, the real database, JSON diagram data through
the converter, the Change and Interaction models, tool calls, chips, the play-by-play, and
the timeline and editor behind a menu. It checks itself against journeys 1 through 6. The
draft PRs already exist: btcopilot #135 and fdserver #29.

### Owner review round 1 (2026-09-08, RULED, not yet in the oracle store — append next fold)

Every finding from every review round, row by row: [REVIEW_LOG.md](REVIEW_LOG.md).

One selection state: a chip tap is a dot tap — spotlight plus a caption row carrying the
ask chip, the board button, and the "coded in" chip. Chips are one size, full text, no
truncation and no expand; labels are capped at the source, at most 28 grapheme clusters,
one re-ask, never trimmed after the fact; chips carry pressed-state feedback. In a
play-by-play, step chips move the board and never return to the timeline — the statement
kind Play/Turn plus its cluster_id is now persisted. A play-through holds each move until
its narration line has finished typing plus about two seconds; the owner tunes the feel
directly, and the eight-second loop stays a separate clock, never stretched to match. Chat
stays pinned to the bottom while the coach types. The moves board fits its content — this
supersedes the fixed 264px rows: mark every UI_SPEC.md row carrying RESOLVED #28 as
SUPERSEDED by this ruling. Editor fields are 44px with the mockup's padding. Tapping a
diagram row opens that diagram, one open at a time (User.current_diagram_id). The old
Personal app is superseded: its endpoints are archived and the chat app's routes are the
personal API — models, prompts and the agent loop stay; Pro routes are untouched. Done.

### Owner review round 2 (2026-09-08, RULED, not yet in the oracle store)

The board has one control row whichever way it was opened: back, "explain", forward, with
explain dead only while the coach is answering the last one. The way onto the board from
the timeline is the play mark alone, no words. The words under the board are a person and
their own words — no count, no clinical term — in a block that keeps two lines of room;
the date is written once, under the dot. The line above the wire says only "Family
timeline". Nothing is drawn behind the move being played: the dot itself is drawn last, in
the action green. Blank ground anywhere on the picture, and the picture's own name, put it
down; a label picks its moment, and the words of the moment already picked go to where it
was said. Every word the app says is selectable and copyable; only controls carrying no
prose are held back. A send that fails says which of three things happened and offers to
go again, and clears when anything lands. Three dots while the coach is thinking — this
supersedes the mockups' blinking caret, which stays on words being written out. Sign-in
tokens last as long as the session.

**Preserved on the owner's word, do not remove**: the agent's tool-call summaries in the
thread, and their formatting, separate from the coach's reply. He likes them as they are.

**Measured, not changed**: the symptom arrow is exactly the ratified drawing — 26 of
shaft, 10 of head, 2.6 stroke, 26 across from the cross. It reads tall because the board
draws people at radius 13 where the ratified sheet draws them at 17, so the same arrow is
1.23 of a person's width instead of 0.94. Side by side at
`~/worktrees/fd362-sandbox/symptom_arrow_compare.png`.

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
the released app. Every multi-agent run spawns a persistent goal auditor before the
workers start. Read this file to start; read HISTORY only for a specific fact. One
worktree per builder next round — shared-index sweeps and gap-file clobbers cost hours.

Pinned (not next): the corpus/subset sessions in [NEXT_SESSIONS.md](NEXT_SESSIONS.md).
