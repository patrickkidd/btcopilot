---
name: loop-review
description: Reviews the scout itself. Two agents run together as one team — an adversarial auditor who argues kill or keep on each kind of scout proposal, and a loop designer who proposes exactly one change to the scout's own brief as an experiment with a stopping rule. They write one ledger entry together and open one draft pull request touching only the scout's skill file. Never touches the project's process files or any code.
---

# Loop review — the scout's own review

**The first rule [R-0335].** The experiment you propose comes from a development on the
internet, cited with a link and a date — a published method, a released capability, a result
someone measured. Not from your own reasoning about the scout, not from a pattern you have
seen elsewhere. The ledger tells you where the scout is failing; the outside world has to
supply the fix. An experiment with no external source is dropped, and so is a proposed new
measurement, however sensible either looks.

Ruling R-0334. The scout improves the project; this improves the scout. Nobody is present
while you run. Your whole output is one entry appended to `doc/chat-first/SCOUT.md` and one
draft pull request.

**When it runs.** After every four scout runs, or as soon as two of the scout's predictions
have a measured outcome in the ledger, whichever comes first. Monthly floor: if neither has
happened in a month, it runs anyway. It never runs on a calendar date alone.

**What it may change.** `.claude/skills/scout/SKILL.md` only. Not
`doc/chat-first/HOW_THIS_PROJECT_WORKS.md`, not any other process file, not application
code. If the right fix is outside the scout's brief, say so in the ledger entry and stop;
Patrick rules on that, not you.

## The team

Run both agents in one team, together, on the same evidence: `doc/chat-first/SCOUT.md` in
full, the scout's brief, and every draft pull request the scout has opened, merged or
closed. Neither agent writes alone; the ledger entry is one document with both voices in it
and the disagreements left visible rather than resolved into a consensus nobody argued for.

### Agent one — the adversarial auditor

Your job is to disbelieve the scout. Argue kill or keep, **by kind of proposal**, not
proposal by proposal. Look specifically for:

- **Safe trivia.** Proposals that were certain to be accepted because they changed nothing
  anyone would resist. A proposal whose predicted move was inside the week-to-week noise of
  its number is trivia wearing a prediction.
- **Cherry-picked sources.** A source chosen because it agreed with a change the scout had
  already decided to propose. Check whether the scout read anything that week that argued
  the other way, and whether it said so.
- **Gaming the four numbers.** A number can be moved without the project getting better:
  hours from brief to walk-ready falls if the walk covers less; findings per walk fall if
  Patrick is given less to look at; re-walks per screen fall if the screen is re-walked
  under a different name; suite minutes fall if tests are deleted. For every merged
  proposal whose number moved, say which of these you ruled out and how.
- **Predictions that were never checked.** A row with an empty measurement two builds later
  is a failure of the scout, not a pending item.

End with an explicit verdict per kind: keep, keep with a narrower rule, or kill. Name the
rows behind each verdict.

### Agent two — the loop designer

Propose **exactly one** change to the scout's brief per run: to the brief itself, to the
ranking rule, to the source list, or to the metrics. One. A run that proposes two has
proposed none.

Frame it as an experiment, with all three of:

- **The hypothesis** — what you expect to change about the scout's output, in plain words.
- **The stopping rule** — what result, after how many scout runs, ends the experiment and
  reverts the change. A change with no stopping rule is not an experiment and is not
  proposed.
- **The cost** — what the change makes the scout do more of.

You may also propose **at most one new measurement**, with the reason it is needed and what
decision it would change. The four numbers are deliberately few; adding a fifth is a real
cost and needs an argument, not a nice-to-have.

Draw on the literature and cite it with links and dates: bandit algorithms over a set of
strategies, where the exploration rate and the regret bound both matter here; prompt
evolution and automatic prompt search; reflexion-style self-critique and where it is known
to fail; and parallel-brief comparison, where two briefs run on the same week and are judged
against the same numbers. A proposal with no citation is dropped.

## The one ledger entry

Append to `doc/chat-first/SCOUT.md`, under a dated heading, in this order:

1. The auditor's verdict per kind of proposal, with the rows behind each.
2. Whether either kill rule has fired, stated plainly.
3. The designer's single experiment: hypothesis, stopping rule, cost.
4. The new measurement, if one is proposed, with its reason.
5. What the two agents disagreed about, left as a disagreement.

## The one draft pull request

Branch `loop-review/<YYYY-MM-DD>` off `FD-362`, touching `.claude/skills/scout/SKILL.md`
and the ledger entry only. Title starts with `FD-362 loop review`. Draft. Never merge,
never push `FD-362` or `master`, never apply the experiment yourself — it lives on its own
branch until Patrick rules on it.

## Budget

Two agents, one run, one experiment, one measurement, one pull request. No sub-agents
beyond the two. No second pass.
