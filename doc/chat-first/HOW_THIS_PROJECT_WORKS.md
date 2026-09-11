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

## The flush: every session ends with `/flush`, and topics are picked up by name
The corpus keeps two clocks per topic — [TOPICS.md](TOPICS.md) is the state clock (one block
per topic, headed by its plain name, rewritten in full), [HISTORY.md](HISTORY.md) the event
clock (one entry per session, never rewritten by a later session). The skill
`.claude/skills/flush/SKILL.md` runs the flush idempotently; `bin/flushcheck.py` verifies it.
A new session reads STATE.md, then TOPICS.md. The owner names a topic in plain words — "let's
continue designing the pro and training features", "list the open issues" — and the session
matches the words to a block and continues from its Open and Next action; ids are for tags
only and are never said to him.

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

## Rules that came from things going wrong (dated; these bind every session)

Each of these was written down after a specific failure on this project. They are copied
here, paraphrased, from the owner's global agent instructions so a session working only from
the corpus still has them.

**Eyeball review first (2026-09-08).** The moment a build is believed to work, the owner gets
the link and a short list of what he will notice — and the session stops there. Continuous
integration, coverage, desktop goldens and re-walks come after he has looked, and only on
what he confirms is intended. His words that day: if you think something is finished, get me
to test it myself first, because you go off on terribly long rabbit holes on things that are
not even intended correctly.

**An eyeball round is at most three items (2026-09-08).** Edit, take one headless screenshot
at 393x852 for the coordinator to check, then the owner refreshes the dev server and sees it
himself. Goldens, gates, suites and CI run once at the end of the day, never per round.

**A user interface is never reported verified on the builder's own screenshots
(2026-09-08).** A subagent once reported six journeys passing; the owner opened it and
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
It runs on Opus with the goal statement and the references, and stays alive until stood down.
Its first job is the clock and the cost: a ten-minute stall alarm, checking the sandbox is
reachable, and flagging any verification beyond the one screenshot [Oracle: R-0228]. Its
second is goal alignment — within the first check, read each worker's early output and
confirm it understands the goal; correct it immediately if not; flag scope drift and
misreadings; escalate only when a worker does not correct after one nudge. An auditor that
misses a stall is replaced.

**Nothing an agent says reaches the owner (2026-09-01).** No interim reports, no sign-offs,
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
