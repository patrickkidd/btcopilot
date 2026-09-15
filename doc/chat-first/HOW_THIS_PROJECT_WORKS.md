# How this project works (process rules — read before working)

**FD-362 is the single source of truth at this altitude.** The working corpus is this
branch. Both are maintained continuously; neither is a snapshot.

## One branch, one name, every repo
`FD-362` in btcopilot (code + `doc/chat-first/` + `doc/DRAWABILITY.md` + `decisions/log.md`)
and `FD-362` in fdserver (`doc/oracle/` + the private prompts). No new branch per session.
No new worktree per session. A ticket-shaped piece of work may still get its own; this
project does not. familydiagram is out of scope for this trajectory.

## The corpus is maintained automatically, by every session
This is not optional and not deferred to the end of a session:
- **STATE.md** — revise it as the current truth changes.
- **HISTORY.md** — append what happened; never rewrite it (two clocks).
- **Rulings** — log every ruling Patrick makes to the oracle store in fdserver the moment
  he makes it. Never author a ruling he did not say.
- **FD-362's description** — keep it in line with STATE.md at *this* altitude only:
  inspiration, motivation, the bet, guardrails, what carries over, the product, and this
  maintenance rule. Detail belongs in the corpus, not the epic. Updating the epic needs
  Patrick's one-line yes for the operation, not for the content.
- **decisions/log.md** — every significant decision, immediately.

## The flush: every session ends with `/two-clocks`, and topics are picked up by name
The corpus keeps two clocks per topic — [TOPICS.md](TOPICS.md) is the state clock (one block
per topic, headed by its plain name, rewritten in full), [HISTORY.md](HISTORY.md) the event
clock (one entry per session, never rewritten by a later session). The skill
`.claude/skills/two-clocks/SKILL.md` runs the flush idempotently; `bin/flushcheck.py` verifies it.
No page is generated or shown to Patrick from the register or the ledger (retired 2026-09-11).
A new session reads STATE.md, then TOPICS.md. Patrick names a topic in plain words — "let's
continue designing the pro and training features", "list the open issues" — and the session
matches the words to a block and continues from its Open and Next action; ids are for tags
only and are never said to him.

## The scout: every session reads SCOUT.md after STATE.md

A scout runs locally, inside a session, at the flush of any build that handed Patrick a
testing walk — `/two-clocks` invokes it, there is no schedule [R-0336] — and looks outward: at
what Anthropic and OpenAI published, at what the Claude Code changelog changed, at new
research on evaluating agents and deriving tests from a specification, and at a fixed list of
accounts on X.com through the Chrome extension, asking Patrick to connect or sign in when it
cannot reach them rather than skipping the source. It reads inward too — the corpus, and
Patrick's own typed statements as the trace script mines them out of the local transcripts —
so a bottleneck is one he hit, not one inferred from a commit. It proposes at most ten ranked
changes to this project's own
process files, each carrying a source, the dated line in the corpus it answers, the exact
file it would change, and a prediction on one of four measured numbers: hours from brief to
walk-ready, Patrick's findings per walk, re-walks per screen, chat suite minutes. It never
touches application code and never applies its own proposals; its top three arrive as a draft
pull request on a branch of their own. [SCOUT.md](SCOUT.md) carries the current baselines, the
open items, the rules that retire the scout if it stops earning its keep, and the record of
every proposal and whether its number moved. **Every session reads SCOUT.md immediately after
STATE.md and says in its first reply whether any open item applies to today's work** — naming
the item and what it would change, or saying plainly that none applies.

A second pair of agents reviews the scout itself [R-0334]: an adversarial auditor who argues
kill or keep on each kind of scout proposal, catching proposals that were safe trivia, sources
picked because they agreed, and numbers moved by covering less rather than working better; and
a designer who proposes exactly one change to the scout's brief per run, framed as an
experiment with a stopping rule. They write one ledger entry together and open one draft pull
request touching the scout's brief alone — never these process rules and never code. The same
flush step invokes it, after every fourth scout run or as soon as two predictions have a
measured outcome, both counted in SCOUT.md. Its brief is
`.claude/skills/loop-review/SKILL.md`. Every proposal and every experiment at both levels
must come from a development on the internet, cited with a link and a date [R-0335]; an item
with no external source is dropped.

## Sessions start at any altitude, from any angle
Patrick will start sessions this week to learn and to pivot, sometimes at product
altitude, sometimes at architecture, sometimes on a single surface. The corpus is what
makes that possible. So:
- Read STATE.md first, always. Then whatever the angle needs.
- Ask what this session is for before proposing an agenda.
- Do not re-open what is ruled; confirm it and move on.
- Divergent options first; he rules; never converge unilaterally.

## Working rules carried from experience
- Sub-agents for all investigation, to preserve the main context.
- Set the model explicitly on every sub-agent call: Fable only for generating and judging
  ideas, Opus for detailed work, Sonnet or Haiku for mechanics.
- Never review, harden or polish anything that has not been picked.
- Test to the audience: a mockup gets one look; only real code gets the full loop.
- No real names, emails, case identifiers or clinical content in any repo.

## Running tests: `bin/t`, and nothing else, while you build

`bin/t` is the only way an agent runs tests mid-build. Given a component name — chat,
review, personal, admin, prompts, web, walks, pro, training, or all — it runs that
component and prints what it chose and why; given nothing, it reads the working diff and
runs only the suites whose paths the diff touches, so a change to the review runs the
review's ninety tests in five seconds instead of everything in fifty. It exits non-zero if
any suite fails. Run one component per change while building; run the whole suite once at
the end, never per item. The chat app's tests are their own suite under
`btcopilot/tests/chat` with their own settings file and their own fixtures imported by
name (R-0332) — they do not inherit Pro's stubs, Pro's failures, or the training app's
markers, and the suites are meant to be run one invocation each.

## Rules that came from things going wrong (dated; these bind every session)

Each of these was written down after a specific failure on this project. They are copied
here, paraphrased, from Patrick's global agent instructions so a session working only from
the corpus still has them.

**Eyeball review first (2026-09-08).** The moment a build is believed to work, Patrick gets
the link and a short list of what he will notice — and the session stops there. Continuous
integration, coverage, desktop goldens and re-walks come after he has looked, and only on
what he confirms is intended. His words that day: if you think something is finished, get me
to test it myself first, because you go off on terribly long rabbit holes on things that are
not even intended correctly.

**An eyeball round is at most three items (2026-09-08).** Edit, take one headless screenshot
at 393x852 for the coordinator to check, then Patrick refreshes the dev server and sees it
himself. Goldens, gates, suites and CI run once at the end of the day, never per round.

**A user interface is never reported verified on the builder's own screenshots
(2026-09-08).** A subagent once reported six journeys passing; Patrick opened it and
nothing worked. Verified means a real browser at phone and desktop sizes, hostile fixtures
(empty, one item, sparse across decades, dense, undated, long labels, long names, unicode),
deterministic gates (no console errors, no failed requests, no box outside its parent, no
horizontal scroll, the page changed after every click), and Playwright screenshot goldens he
approves. The builder and the verifier are different agents, and the verifier gets the spec
and the fixtures, never the builder's report.

**A build brief carries the approved references themselves (2026-09-08).** Hand the builder
the ratified mockups, galleries and rulings by path, and say the reference wins over
simplicity. Never paraphrase an approved design into something simpler — that is how the
ratified move language and the ruled resting strip got dropped from a brief and then from the
build. Every interface build ends with an approved-versus-built deviation table before anyone
may call it done.

**Every multi-agent run spawns a persistent auditor before the workers start (2026-09-08).**
It runs on the cheapest model that can poll the clock and read a diff (Sonnet), with the goal statement and the references, and stays alive until stood down [R-0301, 2026-09-11]; only judgement-heavy work runs on Opus.
Its first job is the clock and the cost: a ten-minute stall alarm, checking the sandbox is
reachable, and flagging any verification beyond the one screenshot [Oracle: R-0228]. Its
second is goal alignment — within the first check, read each worker's early output and
confirm it understands the goal; correct it immediately if not; flag scope drift and
misreadings; escalate only when a worker does not correct after one nudge. An auditor that
misses a stall is replaced.

**Nothing an agent says reaches Patrick (2026-09-01).** No interim reports, no sign-offs,
no coordination chatter, and never a summary while a subagent is still running. Hold
everything until the deliverable is ready for his action, then send one message with all of
it. Never ask him to review before the agents have finished.

**There is a dev mode and it is used (2026-09-09).** Code changes on disk refresh the page
instantly; working without one wastes his time [Oracle: R-0227]. The recipe is in STATE.md
under the review sandbox.

**Test to the audience, not the artifact (2026-09-02).** A mockup he will look at once gets
one load and one screenshot. A gallery he must judge across records gets a deterministic
gate. Only code gets the full loop.

**Captions are written for someone who was not in the room (2026-09-02).** Card captions,
trade-off lines and option names use common words and name concrete things on screen: what
you are looking at, what to tap, what happens, what you give up. Never a term coined during
the work, never a reference to a rule the reader has not read.

**A reply is a quarter of what feels complete (2026-09-11).** The answer, the one thing he
does next, nothing restated, no evidence walk unless he asks [R-0304]. His words after a
three-screen report on a scroll bug: "You could have given me that in 25% of the length."

**Never repeat an artifact's content in the console (2026-09-12).** When the deliverable is
an artifact, document or page, the console reply is the link plus the decisions he must make
and nothing else: no summary of the artifact, no restated findings, no "TLDR" that duplicates
its first section. His mental token budget is the bottleneck; anything he must read twice
is a cost, and most output tokens are not necessary. His words: "It just makes for double
reading where the main bottleneck to productivity is my own mental token budget."

**Fixtures are Claude's to stand up; bugs are fixed before he looks (2026-09-11).** If a
harness, a role or a permission blocks a test fixture, fix the harness — never hand the block
to Patrick. Every known bug is fixed before he is asked to test, and the ask names one clear
thing to test [R-0302]. His words: "You need total freedom to stand up test fixtures" and
"why not fix all the bugs before asking me to test?"

**Build, then hand over a walk (2026-09-12; his words: "this follows exactly my ideal vision for our dev flow").** When a batch of work is finished, stand up the sandbox with fixture people and records on the stand-in family, with history kept the way real use leaves it (sessions, codings, votes), each fixture with a way to put it back. Then write one testing document for Patrick: one numbered walk per screen, what to tap and what he should see, in plain words for someone who was not in the room, with the sign-in links at the top and the order dependencies stated. Independent browser verification runs before he sees it, and known bugs are fixed first. That is the whole handover; nothing else is reported. Keep this instruction light so it never treads on what the model already does well.

**Precedent is tracked (2026-09-12, Patrick).** Every dilemma or question about process or methodology in the coding and review work (units, agreement, unresolved items, codebook revision, blinding, adjudication) gets its intersections with the literature noted in doc/chat-first/LITERATURE.md as it comes up: author, year, what they did, how it maps or differs here. Social-science content analysis and the AI labs' labeling practice both count. This feeds a future literature review; the app's scope is wider and more exploratory than most published IRR work, and the notes say so where it matters.

- **Every screen has a visible hierarchy (2026-09-13, Patrick).** A header is a title, then at most one line of figures, each labelled; a datum with no place in the hierarchy is cut, never parked as a bare span. No figure appears twice on a screen. No label is built from counts into shorthand ("2 to 1 — talk"); a label is a word a first-time reader already knows, or it goes. Verifiers check words on new screens, not only behaviour.

**An Opus-level auditor for wall-clock time overall (2026-09-14, R-0331).** With judgement, not a stopwatch: flags test suites run too early or unfiltered (only the changed components run mid-build; the whole suite once at the end), flags tests not derived from a ruling (the chat app is greenfield and its tests are 100% oracle-derived), flags unit tests that do I/O beyond the logic under test or take more than an instant, flags integration tests without a reason for their fixtures, flags database fixture and spin-up waste, and flags code organisation and prioritisation that will cost later. Fable-level oversight where the call needs it.

**A walk is serial, step by step, and never cross-references (2026-09-14, Patrick).** Each step says what to tap and what he sees, in place; never "see Walk 5", never "this is the line the spec disagrees with", never a list of known differences to hold in mind. Anything known to be wrong is fixed before the walk is handed over, not annotated.

**A walk is driven before it is handed over (2026-09-15, R-0343).** An independent agent, not the author, follows the walk document literally in a real browser on the fixture accounts, step by step, and corrects every step that does not match the screen. Only then does Patrick get it. His words: "There are big inconsistencies between the walk instructions and what I actually see, seemingly at every walk."
