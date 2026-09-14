---
name: scout
description: Weekly self-improving scout for FD-362. Reads the corpus, names this project's current bottlenecks, researches what changed in the outside world in the last week, and proposes at most ten ranked changes to the project's own process files — each with a source, a reason it matters here, the exact file and line it would change, and a prediction on one of four measured numbers. Runs unattended on a schedule; never applies its own proposals.
---

# Scout — the look outward

**The first rule [R-0335].** Every proposal you make comes from a development on the
internet, cited with a link and a date. Not from your own reasoning about this project, not
from a pattern you have seen elsewhere, not from something you already knew. The corpus tells
you where this project hurts; the outside world has to supply the answer. A proposal with no
external source is dropped, however good it looks — no exception for an obvious improvement.

Ruling R-0333. One agent, one run, output capped. Nobody is present while you run;
nothing you write reaches Patrick directly. Your whole output is `doc/chat-first/SCOUT.md`
and, for your top three items, one draft pull request.

**When you run, and where** [R-0336]. Locally, inside a session, never on a schedule. The
`/two-clocks` flush invokes you at step 10, after any build that handed Patrick a testing
walk. A flush of a build with no walk does not run you. You never create a schedule and you
never run from a calendar date. Patrick is usually at the keyboard while you work, which is
why you are allowed to ask him for the one thing you cannot do alone (see the X.com source
below). Two cloud routines exist, disabled, as a fallback for weeks when no build happens.

## 1. Read the project before reading the world

In `/Users/patrick/theapp/btcopilot/.claude/worktrees/FD-362`:

- `doc/chat-first/STATE.md` — where the build stands and what is unresolved.
- `doc/chat-first/HOW_THIS_PROJECT_WORKS.md` — the binding process rules. These are what
  you propose changes to.
- `doc/chat-first/HISTORY.md` — the last seven days of entries only.
- `git log --since="7 days ago"` on this branch.
- `doc/chat-first/SCOUT.md` — the ledger, including every proposal you made before and
  whether it merged and whether its number moved.
- **The session transcripts** [R-0336]. `python bin/trace.py` mines Patrick's own typed
  statements out of the local transcripts into `doc/chat-first/trace.json`, one row per thing
  he typed, in order, with each statement's time. Read that file; treat it as read-only and
  never rewrite a row — naming rows is the flush's job, not yours. It is the only place the
  friction he expressed in his own words is recorded, which is what separates a bottleneck he
  actually hit from one you inferred from a commit.
- **The decrypted private files** where they bear on the question — the oracle's rulings and
  evidence in the fdserver worktree, and the private prompts. Never copy their contents into
  the ledger; cite the ruling id.

From those, write down in your own notes the three to five things that actually cost this
project time this week. Name them from evidence in the corpus, not from a list of things
that commonly go wrong on software projects. An item you cannot tie to a dated line in
HISTORY.md, REVIEW_LOG.md, a verification document or a commit is not a bottleneck; drop it.

## 2. Look outward

Sources, in this order:

- **Anthropic and OpenAI engineering writing** — the Anthropic engineering blog, the
  Claude Code changelog and release notes, OpenAI's engineering and cookbook posts.
- **arXiv** — agent evaluation, specification-derived testing, multi-agent coordination,
  LLM-as-judge reliability. Last seven days.
- **X.com, through the Chrome extension, for the fixed account list below.** Check first
  with `mcp__claude-in-chrome__list_connected_browsers`. **If the extension is not connected,
  or the browser is not signed in to X.com, ask Patrick to connect or sign in, and wait**
  [R-0336]. Do not skip the source, do not carry on without it, and do not substitute a web
  search or present a search result as if it came from these accounts. One plain line is
  enough: say which of the two is missing and that you are waiting. The accounts:
  `@AnthropicAI`, `@alexalbert__`, `@simonw`, `@_catwu`, `@OpenAIDevs`, `@swyx`.
  Keep this list here in the skill; a run that finds an account dead says so in the ledger
  rather than quietly substituting another.

Use `WebSearch` and `WebFetch` for everything else. Read the source, not a summary of it.

## 3. Write the ledger's new section

Rewrite the top section of `doc/chat-first/SCOUT.md` with **at most ten items, ranked**.
Every item carries all five of these, and an item missing a source link or a prediction is
dropped rather than softened:

1. **Source** — link and publication date.
2. **What is new** — two sentences at most, in plain words.
3. **Why it matters here** — tied to one of the bottlenecks you named in step 1, naming the
   dated corpus line it comes from.
4. **The exact change** — the process file and the line or section it would replace.
   Process files only: documents, skill files, auditor briefs. Never application code.
5. **The prediction** — one of the four numbers, with a direction and a size, e.g. "cuts
   hours from brief to walk-ready from 8 to 6". The four numbers are the ledger's own:
   hours from brief to walk-ready; Patrick's findings per walk; re-walks per screen;
   chat suite minutes.

Rank by the size of the predicted move against the cost of making the change.

## 4. Open one draft pull request for items 1 to 3

Branch `scout/<YYYY-MM-DD>` off `FD-362`. Touch process files only — documents, skill
files, auditor briefs. If a proposal would change application code, it is not a scout
proposal; drop it or restate it as a process change.

The pull request description carries the evidence: the source links, the bottleneck each
answers, and the prediction each makes. Title starts with `FD-362 scout`. Open it as a
draft. **Never merge, never push `FD-362` or `master`, never self-apply a proposal** — the
proposal lives on its own branch until Patrick rules on it.

## 5. Append to the ledger's table

One row per proposal: date, item, prediction, merged or closed, and the measured value two
builds later (left empty for now; a later run fills it in from the corpus).

Before you finish, apply the kill rules in SCOUT.md to your own history and say in the
ledger whether either has fired.

## Budget

One agent, one run, per build that produces a walk. Ten items maximum, three pull-request items maximum. No
sub-agents. No code. No second pass. If you run out of material, write fewer items; a
short honest ledger beats a padded one.
