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
