---
name: product-owner
description: On-demand product owner report over every feedback loop in the ledger (doc/FEEDBACK_LOOPS.md). Read-only Haiku readers pull the latest numbers from production, Grafana, the private corpus and git; one Sonnet judge writes a status line per loop; one Fable call assesses results and direction against product-market fit and ranks at most five recommendations. The report is five terminal lines; a page only when a recommendation needs the table. Never scheduled. Trigger on "/product-owner", "check the loops", "product owner report", "are we closer to product market fit", "how are the loops doing".
argument-hint: "[since YYYY-MM-DD] | [<a question to weigh in the assessment>]"
---

# Product owner

Patrick asked for one skill that acts like a product owner over every feedback loop in the
project: it reads the latest data for each loop, judges it, and recommends priorities, with a
Fable-level assessment aimed at reaching product-market fit faster. It runs only when he invokes
it.

`SKILL=.claude/skills/product-owner` in the checkout. `LEDGER=doc/FEEDBACK_LOOPS.md`.
`<today>` is the UTC date, `date -u +%F`, as the box and the logs keep it.
`RUN=$CLAUDE_JOB_DIR/tmp/product-owner-<today>` (or the session's scratchpad when that variable
is unset) holds the run's working files; nothing there is committed.

## Never

- **Scheduled.** Never put this in `/loop`, `/schedule`, cron or a hook. Patrick decided on
  2026-09-28 against an automated digest. A request to schedule it is answered by saying so.
- **A write outside the run folder and the run record.** No write to the app's database,
  Grafana, Jira, the rulings store or its queue, any CLAUDE.md, or the ledger. Production is
  read inside a read-only transaction (`bin/tables.py` sets it). No `flask admin` command that
  changes something, no `--yes`, no queue group rejected, no eval run, no deploy, no notice sent.
- **A ledger edit.** Changes to the ledger are proposed as a unified diff for Patrick's yes.
- **A secret printed.** `bin/grafana.py` reads the laptop Grafana's password from the main clone's `deploy/laptop/.env` itself.
  Nobody runs `env`, `docker inspect`, `cat .env` or reads `/etc/fd/`.
- **A person named.** No name, email or person's words in any file or line. People are counts,
  or "the heaviest user". The scripts return counts only; readers keep it that way.
- **A paid model call.** Every agent runs on the Claude Code subscription. The run spends $0 in
  API calls.
- **A trend from noise.** With a handful of accounts, most 7-day windows hold a few rows. Under
  five rows in a window is "too few rows to judge", never a rise or a fall.

## Cost cap per run

At most eight readers (Haiku or Sonnet), one Sonnet judge, one Fable call: ten agents. The
default run uses five readers. A source that would need a ninth reader is listed as "not read
this run". A reader not finished in 10 minutes is stopped with TaskStop and its loops read "not
read this run". The whole run stops at 30 minutes and reports what it has.

## Step 0 — before any agent (free, done by the session itself)

1. Work in a worktree, never the main clone (CLAUDE.md, "Worktrees"). From the main clone,
   create one named `product-owner-<today>` first.
2. `uv run pytest btcopilot/tests/test_feedbackloops.py -q`. A failure names an observation
   kind, report kind, notification kind or dashboard panel with no ledger row: each one becomes a
   proposed row in the ledger diff.
3. SINCE = the date in the newest file name in `doc/log/product-owner/`, or 30 days ago when
   there is none, or the `since` argument. LAST = that file's lines, for comparison.
4. `mkdir -p $RUN`.

Every agent below returns asynchronously. Wait for readers with one Bash `until` loop on the
five files existing (timeout 10 minutes), and for the judge and the Fable call on their
completion notice; never poll their transcripts.

## Step 1 — readers, in parallel

Spawn all five in one message, `run_in_background: true`, each with `model` set as below and a
brief of at most 15 lines holding: its commands, its loop names copied exactly from the
ledger's Loop column, the output file, and these rules: read only; write nothing but
`$RUN/<reader>.json`; never print a secret, a name, an email or a person's words; reply with
the one line "wrote <path>".

The scripts in `bin/` hold every query and path, so a reader only runs its commands and writes
the file. `tables.py` and `files.py` print JSON keyed by the ledger's loop names ("goal: ..."
for the goal); `grafana.py panels` keys by dashboard, then panel title, and the ledger's "Read
by" column says which loop a panel belongs to. Each file is one JSON object with those keys
exactly as printed (never renamed or snake-cased), each value an object of numbers or YYYY-MM-DD
dates, plus `"not_read": {"<loop>": "<why>"}` for anything that failed. A reader never goes
looking for a file a script did not name: a script's error goes under "not_read" verbatim.

| Reader | Model | Runs | Loops it covers |
|---|---|---|---|
| production | haiku | `python3 $SKILL/bin/tables.py G1 G2 1 2 3 4 5 6 7 8 9 14 16 17 18` | goal and rows 1-9, 14, 16-18 |
| product events | haiku | `python3 $SKILL/bin/tables.py 10` | row 10 |
| grafana | haiku | `python3 $SKILL/bin/grafana.py panels` (every panel of the repository's dashboards over 30 days, written whole under "panels": a rate panel gives its days' mean, a count panel its total, a table its rows); `python3 $SKILL/bin/grafana.py logsql` with each LogsQL line under the ledger's queries 11 and 12; `python3 $SKILL/bin/grafana.py traces` (all from the laptop's Grafana, doc/MONITORING.md; with the laptop's stack down, every grafana loop goes under "not_read") | rows 11 and 12, and every row whose "Read by" names a panel |
| corpus | haiku | `python3 $SKILL/bin/files.py SINCE`: the rulings queue in the private corpus, the tests owed and waived, the correction cases, prompt changes logged since SINCE, saved replays and live cases, recorded runs, the API dollars in every checkout's eval ledger, and the efficiency skill's rules and corrections | rows 7, 15, 16, 20, 21, 23 |
| git | haiku | `git fetch -q origin`; `gh pr list --state merged --search "merged:>=SINCE" --json number,title,mergedAt --limit 100`; `gh pr list --state open --json number,title,isDraft`; `gh run list --workflow release.yml --created ">=SINCE" --json conclusion,headBranch,createdAt --limit 100` | "closures": each merged pull request as number, date and title; row 22: deploys and failed deploys |

The main clone's root is `$(git rev-parse --path-format=absolute --git-common-dir)/..`.

## Step 2 — one Sonnet judge

When every reader has replied or been stopped, spawn one agent, `model: "sonnet"`.
Brief: read the ledger table, every `$RUN/*.json`, and LAST. For each of the ledger's rows, in
order, write one line to `$RUN/status.md`:

`<n>. <loop> | flowing: <7d / 30d rows, or "too few rows to judge", or "no signal built"> |
closing: <what acted on it since SINCE: groups rejected, evals run, pull requests merged (by
number), rulings appended; or "nothing"> | lag: <days from first signal to first action, or "not
measurable: nothing dates the action"> | cost: <API dollars or hours in the window, or "none"> |
status: <live, partial, missing or retired>, <"as the ledger says" or "ledger says X">`

Then, under a heading "Ledger changes", one line per row whose status or last-known number the
numbers contradict, and one per kind or panel the Step 0 test named. It reads nothing else and
writes nothing else. A panel belongs to the row whose "Read by" cell names its title; where a
panel and a ledger query disagree, the query's number stands and the line says so. It maps a
pull request to a loop only when its title names that loop's signal or table.

## Step 3 — one Fable call, the only one

Spawn one agent, `model: "fable"`. Brief:

> Read `doc/FEEDBACK_LOOPS.md`, `$RUN/status.md`, every `$RUN/*.json`, LAST, and "The product
> (ruled)" in `doc/STATE.md`. Nothing else. Write `$RUN/assessment.md` and reply "done".
>
> The one goal is product-market fit as this project defines it: people come back on their own
> and report a felt shift. Today's proxies are return within a week and the journal-entry rate
> (messages from people per active person per week); a felt shift has no signal yet.
>
> 1. **Assessment**, at most eight sentences: are the loops producing evidence about that goal,
>    is the work of the last window moving the proxies or only the machinery, and what the
>    direction should be. Separate observation, inference and recommendation. Label guesses.
> 2. **Recommendations**, at most five, ranked by how much each shortens the path to the goal
>    per hour spent. Each: the evidence (numbers from the files, with their window), one action,
>    its cost in hours or dollars, and what Patrick must decide. A window with too few rows is
>    evidence of too few people, not of a trend.
> 3. **The five lines**, plain words for someone who reads only these lines: no file paths,
>    symbol names, table names or coined terms; each line stands alone:
>    `Goal: <return within a week, the journal-entry rate, and felt shift, each with its number>`
>    `Loops: <n> live, <n> partial, <n> missing, <n> retired<, change since the last run>`
>    `Do next: <the top recommendation, its cost>`
>    `Biggest gap: <the one missing signal or action that most hides progress toward the goal>`
>    `You decide: <the one decision Patrick must make, with its example>`
> 4. **Page**: "needed" only when a recommendation cannot be decided without the per-loop
>    table; say which one. Otherwise "not needed".
>
> Patrick's terms only (PDP, clusters, pair-bonds, events, sittings, the coach, the record);
> never coin a term. No person's name, email or words. Numbers with their window; no mood
> words: a number, a range, or "guess:".

## Step 4 — report

1. Print the five lines from `$RUN/assessment.md`, then one more:
   `spent $0 on API calls; <n> agents; <m> minutes`. That is the whole reply, unless the ledger
   diff exists: then add one line naming what it changes and ask for his yes.
2. Ledger diff: copy the ledger to `$RUN/FEEDBACK_LOOPS.md`, apply the judge's "Ledger changes"
   there, and keep `diff -u doc/FEEDBACK_LOOPS.md $RUN/FEEDBACK_LOOPS.md > $RUN/ledger.diff`.
   Apply it to the ledger only after his yes.
3. Page, only when the assessment says "needed": load the `artifact-design` skill, build one page
   with the assessment, the ranked recommendations and the per-loop status table, every link
   with `target="_blank" rel="noopener"`, and publish it as a private artifact. The page carries
   no names, only counts.
4. Record the run in `doc/log/product-owner/<today>.md`: a title line, the five lines, the spend
   line, "Ledger diff proposed: yes/no", and "Page: <link or none>". Commit it on the worktree's
   branch by pathspec. The next run compares against it.
