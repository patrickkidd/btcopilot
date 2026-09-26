# How this project works (process rules — read before working)

**FD-362 is the single source of truth at this altitude.** The working corpus is this
branch. Both are maintained continuously; neither is a snapshot.

## One branch, one name, every repo
`FD-362` in btcopilot (code + `doc/` + `doc/DRAWABILITY.md` + `decisions/log.md`)
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

## The flush: every session ends with `/two-clocks`
`.claude/skills/two-clocks/SKILL.md` holds the full procedure, including its scripts (now in
`.claude/skills/two-clocks/bin/`) and how a topic is picked back up by name.

## The scout and the loop review

The scout (`.claude/skills/scout/`) retired 2026-09-23 [R-0420].
The loop review (`.claude/skills/loop-review/`) retired 2026-09-23 [R-0420].

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
the end, never per item. The tests are one suite under `btcopilot/tests` with one settings file and fixtures
imported by name (R-0332) — none of Pro's stubs or the training app's markers.

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

**A reply is a quarter of what feels complete (2026-09-11).** Give the answer and what he
must do, skip anything he already knows, and only walk through the evidence if he asks for
it [R-0304]. He said a three-screen report on a scroll bug should have been a quarter as long.

**Never repeat an artifact's content in the console (2026-09-12).** When the deliverable is
an artifact, document or page, the console reply is the link plus the decisions he must make
and nothing else: no summary of the artifact, no restated findings, no "TLDR" that duplicates
its first section. His mental token budget is the bottleneck; anything he must read twice
is a cost, and most output tokens are not necessary. His words: "It just makes for double
reading where the main bottleneck to productivity is my own mental token budget."

**Fixtures are Claude's to stand up; bugs are fixed before he looks (2026-09-11).** If a
harness, a role or a permission blocks a test fixture, fix the harness — never hand the block
to Patrick. Every known bug is fixed before he is asked to test, and the ask names one clear
thing to test [R-0302]. He asked for full freedom to set up test fixtures, and for every bug to be fixed before
he is asked to test.

**Build, then hand over a walk (2026-09-12; his words: "this follows exactly my ideal vision for our dev flow").** When a batch of work is finished, stand up the sandbox with fixture people and records on the stand-in family, with history kept the way real use leaves it (sessions, codings, votes), each fixture with a way to put it back. Then write one testing document for Patrick: one numbered walk per screen, what to tap and what he should see, in plain words for someone who was not in the room, with the sign-in links at the top and the order dependencies stated. Independent browser verification runs before he sees it, and known bugs are fixed first. That is the whole handover; nothing else is reported. Keep this instruction light so it never treads on what the model already does well.

**Precedent is tracked (2026-09-12, Patrick).** Every dilemma or question about process or methodology in the coding and review work (units, agreement, unresolved items, codebook revision, blinding, adjudication) gets its intersections with the literature noted in doc/LITERATURE.md as it comes up: author, year, what they did, how it maps or differs here. Social-science content analysis and the AI labs' labeling practice both count. This feeds a future literature review; the app's scope is wider and more exploratory than most published IRR work, and the notes say so where it matters.

- **Every screen has a visible hierarchy (2026-09-13, Patrick).** A header is a title, then at most one line of figures, each labelled; a datum with no place in the hierarchy is cut, never parked as a bare span. No figure appears twice on a screen. No label is built from counts into shorthand ("2 to 1 — talk"); a label is a word a first-time reader already knows, or it goes. Verifiers check words on new screens, not only behaviour.

**An Opus-level auditor for wall-clock time overall (2026-09-14, R-0331).** With judgement, not a stopwatch: flags test suites run too early or unfiltered (only the changed components run mid-build; the whole suite once at the end), flags tests not derived from a ruling (the chat app is greenfield and its tests are 100% oracle-derived), flags unit tests that do I/O beyond the logic under test or take more than an instant, flags integration tests without a reason for their fixtures, flags database fixture and spin-up waste, and flags code organisation and prioritisation that will cost later. Fable-level oversight where the call needs it.

**A walk is serial, step by step, and never cross-references (2026-09-14, Patrick).** Each step says what to tap and what he sees, in place; never "see Walk 5", never "this is the line the spec disagrees with", never a list of known differences to hold in mind. Anything known to be wrong is fixed before the walk is handed over, not annotated.

**A walk is driven before it is handed over (2026-09-15, R-0343).** An independent agent, not the author, follows the walk document literally in a real browser on the fixture accounts, step by step, and corrects every step that does not match the screen. Only then does Patrick get it. He had found the walk instructions disagreeing with the screen on nearly every walk.

- **2026-09-22 — one test account, never a spray of them (Patrick).** Deploy walks and sandbox
  checks on production made nine claude-test accounts that showed up as "people who chatted" on
  the dashboard. Rule: a test account is deleted the moment it is not needed, or one account is
  reused: `the claude-test account`. Never create a numbered series. Dashboards exclude
  the `claude-test` prefix, and the review walks run against a sandbox, not the box.

**Spot-check evidence at two levels before any push to production (2026-09-24, Patrick).**
A feature is not tested until the report shows evidence from both levels of the stack, for
the specific feature, on the sandbox: (1) the data layer before rendering — the rows, the
turn events, the record, the change log, printed as actual values from a query; (2) the
rendered HTML in the sandbox — the words and elements on the page, from a real browser, with
the deterministic gates. Each level names what was expected and what was seen. A pass with
no printed values at both levels is not a pass. This exists because testing routinely got
lazy: a feature was called done on one level, or on a builder's say-so, and Patrick found
it broken. Only features validated this way go to production, where beta data is precious
and cannot be reproduced.

**Brainstorm topics are taken one at a time (2026-09-24, Patrick).** One topic per round,
never several topics presented together.

**A sandbox must be able to make real model calls (2026-09-24, Patrick).** A missing key is
escalated to Patrick, never worked around by testing without it.

**Test well, then push for him to test (2026-09-24, Patrick) [Oracle: R-0486].** Testing
protects the beta data first; then a build goes to the production box for him to test.
Deploying a build for him to test is not a merge. Since FD-362, every production deploy has
been the release workflow dispatched from the ticket branch (`gh workflow run release.yml
--ref <branch>`); the pull request stays open and unmerged. For the fast-follow (R-0484), once
the gates pass, the coordinator dispatches that deploy without asking for a yes, then verifies
on production.

**Every test path spends the testing key, never the production key (2026-09-25, Patrick).**
The sandbox, live evals, and browser walks with real turns all spend `ANTHROPIC_TESTING_KEY`;
none of them ever spends `ANTHROPIC_API_KEY`, which is production's key, and there is no
fallback to it. A missing testing key fails loudly, the same as a missing model key above,
and is escalated to Patrick rather than worked around.

**Real spend is asked first, every time, and only at the end of a batch (2026-09-25, Patrick).**
A real call to Anthropic happens only right before a deploy, and only when a prompt or a tool
changed since the last one. There is no free tier — every dollar spent is asked for first.

**The live suite has hard caps (2026-09-25, Patrick).** Three dollars per run, and a daily
ledger across runs. A balance check runs before any call. Every run writes a row of results.
A run that stopped partway is reported as stopped, never counted as a pass.

**The sandbox's coach runs on a local model by default (2026-09-25, Patrick).** Local Ollama,
not a paid key. The testing key is spent only when the lead says so, and the sandbox never
spends on Gemini by default either.

**A prompt change ships with an eval built from a human ruling (2026-09-25, Patrick).** A
candidate ruling is confirmed first; the eval then cites the confirmed ruling, fails on the
old prompt, and passes on the new one. Its inputs are fictionalised, drawn from the shape of
logged real cases but not the cases themselves.

**Clinical-coding evals wait on the review group, not on Patrick case by case (2026-09-25,
Patrick).** Ground truth for coding rules has to be ratified by the IRR review group; Patrick
is never asked to certify a coding rule one case at a time. A code with no ruling yet goes on
the waiting list in btcopilot/tests/live/README.md, never into the paid suite. The paid suite
holds only behaviour evals and wording tests.

**A ready message says what it spent (2026-09-25, Patrick).** It ends "spent $X on Y" — the
amount and what it bought.

**Read the rulings on a topic before proposing coach behaviour (2026-09-25, Patrick).** The
coordinator proposed a deterministic after-turn coverage check one day after R-0485 ruled that
coverage is the coach's judgement, never rules; Patrick restated that ruling, adding that
judgement calls belong to inference, not to code (R-0485). Rule: before any design proposal about what the coach does, decrypt the
store and grep the topic; cite the ruling in the proposal. Judgement calls stay inference
(state-based prompting, tools the coach calls); code only where the behaviour is meant to be
mechanical.

**Spend is the exception, not the test method (2026-09-25, Patrick; R-0531).** Rule: plumbing is proven with mocks, the local model and recorded real responses replayed from
fixtures; a real call is never used to prove wiring a unit test already proves. Every paid
response is saved as a replay fixture so it is paid for once. Real calls happen only once per
batch, before deploy, and only for a changed prompt or tool.
