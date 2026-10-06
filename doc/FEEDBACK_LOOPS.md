# Feedback loops

Every place the project collects something to drive an action: what closes it, who closes it,
and the number that shows the loop is working. The `/product-owner` skill
(`.claude/skills/product-owner/SKILL.md`) reads this file on demand and reports on every row.
A test (`btcopilot/tests/test_feedbackloops.py`) fails when an observation kind, report kind,
notification kind or dashboard panel in `deploy/grafana/` is not named here, so a new signal
gets its row the day it is added [R-0578].

Status words. **Live**: the signal is collected in production and the action it drives has
happened at least once. **Partial**: only one side exists: the signal is collected but nobody
acts on it on a schedule, or it is built but not deployed. **Missing**: ruled or designed, not
built. **Retired**: stopped by a ruling. **Open**: data may be collected, but no automated step yet turns it into a product change; parked, and watched for others like it [R-0668].

Written 2026-09-30. Production runs the build of the FD-365 branch, which carries the sittings
work (the coach writing first, coach-offered reports, notices, the coach's memory across
sittings). "Last known" numbers are the last ones the docs gave; the skill reads fresh ones.

Left out on purpose, because they block rather than learn: the production deploy lock, the git
guard on master, the pinned fingerprints of the rulings store, and each person's monthly token cap.

## The goal these loops serve

Product-market fit: people come back on their own and report a felt shift. Today's proxies:

- **Return within a week**: of the people who chatted, the share who chatted again within seven
  days, not counting a return in the two days after a message the coach wrote first. Query G1.
- **Journal-entry rate**: messages from people, per person active, per week. Query G2.
- **A felt shift, reported**: no signal is collected today.

Panels that show the same people and messages: "People who chatted", "Messages from people",
"Coach replies", "Messages a day, by person", "Coach replies a day".

## The ledger

| # | Loop | Signal and where it lives | Closing action and who | Status | The number that proves it | Read by |
|---|------|---------------------------|------------------------|--------|---------------------------|---------|
| 1 | The watcher's findings and your accept-or-reject queue | After every coach turn, one row in the observations table per likely mistake: `duplicate_person`, `duplicate_event`, `add_without_read`, `question_unsaid`. Rows are grouped into a queue of at most ten. | You reject a group (a row in observation_rejects, through `flask admin observations reject`) or take it up as a coach eval case. Taking a group up leaves no record, and no row links a group to its eval case. | partial | Groups on the queue; groups rejected; eval cases linked to a group. Last known: 3 cases seeded 09-24, 0 linked. | "Watcher findings per coach turn, by kind"; "Tuning queue: the ten biggest groups not yet rejected"; query 1 |
| 2 | Refused writes and failed turns | Observations rows `tool_refused` (the record refused a coach tool call), `step_cap` (a turn used all 20 steps), `turn_failed`, `turn_declined` (every model declined the turn), `play_refused`, `play_failed` (a play-by-play refused or failed), `cluster_refused` (a grouping answer the checks refused, with the attempt, the check and its detail), `cluster_failed` (both grouping answers of a turn refused; the rules' groups are stored under their years unless the model's groups are already there). A hand edit the record refuses answers 400 and writes no row. | The coach reads the refusal and retries [R-0579]. The rows join the same queue as row 1. | partial | Refusals per 100 coach turns, by kind. Refused hand edits: not counted. | "Refused tool calls, used-up turns and failures per day, by kind"; "Steps per coach turn, by model"; query 2 |
| 3 | Cost per turn and dollars by kind | model_calls, one row per model call: whose, what it was for (`coach`, `shadow`, `proactive`, `replay`, `play`, `backfill`, `summary`, `cluster`, `scribe`, `ratify`, `judge`, `transcribe`), the model, four token counts, cost, duration. A play-by-play asked for in a session, a message the coach writes first, a session's title and summary, the regrouping of events into clusters after a turn, each scribe step on a coding, the rule draft and divergence reasons written when an admin ratifies a cut (charged to that admin, no diagram), the quality judge (charged to the user whose thread is judged, no diagram), and each finished AssemblyAI transcription (charged to the user who recorded it, no diagram, priced by audio length with zero tokens) are each written there. Shadow calls are left out of every real-spend panel and shown only in "Cost a day, by purpose"; the per-turn panels count coach calls only. | A session changes the prompt layout or the model. Closed once: a day with 78% of its cost in cache writes led to the record moving into the user message on 09-28 [R-0595]. | live | Cost per coach turn; dollars by kind. Last known: $22.99 from 09-23 to 09-28, five accounts. | "Cost per coach turn, by model"; "Dollars by kind, coach calls" (cache-write, cache-read, output and uncached-input dollars a day, stacked; dollars on cache writes is the gauge the cost follows, where the cache-read share of tokens read 77% while writes were 77% of the dollars); "Cost in range"; "All model spend" (every row of the ledger, scratch records, shadows and the claude-test account included); "All model spend, by purpose" (the same rows by what they were for, replays on scratch records, shadows and the claude-test account each on a line of their own); "Tokens in range"; "Cost a day, by person"; "Cost a day, by model"; "Cost a day, by purpose"; "This month by person"; "Slowest coach calls (last 24h)"; the Coach cost dashboard: "Cost per coach turn a day, warm and cold, with the 14-day mean", "Dollars by kind, coach calls", "Calls per coach turn a day", "Tokens written on a cold turn's first call, a day", "Share of coach turns that start cold, a day", "Coverage of the basic data over time, by family", "Cost per coach turn by release" (each coach turn's release is read from its done row in turn_events), "Replay passes" (the replay_passes table, section 17); the quality dashboard's section "In production: every coach turn people took, test accounts left out"; query 3 |
| 4 | Each beta user sees their own use and cost | token_meters: each person's tokens this month and their cap. | The person sees it, and you learn whether people will pay. You ruled on 09-22 that no paid per-use feature comes before this exists. No screen shows a person their use. | missing | None today. | Query 4 (the meter only) |
| 5 | Messages the coach writes first | proactive_messages, one row per message with its trigger (a pattern in the record, or a follow-up the person agreed to). Observations rows `proactive_sent`, `proactive_opened`, `proactive_replied`, `proactive_returned`, and `proactive_refused` when the words break the message's shape. Each sent message reaches the person as a notifications row of kind `coach`, with opened_at. | You change the budget or the triggers. The four counts are kept out of the queue; a panel shows them, and nobody reads it on a schedule. | partial | Opened, replied and returned, each as a share of sent. | "Messages the coach wrote first, by the week they were sent"; query 5 |
| 6 | The coach's memory across sittings | Observations row `earlier_edit` when a coach turn's edits change items an earlier sitting made. | A session tunes what the coach reads: the last 20 statements, its last notes, the chat search. The rows land in your queue as one group with no reason attached. | partial | Share of coach turns with such a row. | "Watcher findings per coach turn, by kind"; "Coach edits to things an earlier sitting put down, per week"; query 6 |
| 7 | Corrections by the person to the coach's record | diagram_changes rows written by the person on a record the coach built; "Doesn't fit" and dismissals in diagram_interactions. | Each correction is kept as a case an eval can run against, and the fix goes through the change log [R-0533]. Three case files since 09-26. A general policy and queue for record corrections is not built. | partial | Hand edits per week; correction cases with a passing eval. | "Coach edits by kind"; query 7; the correction cases in the private corpus |
| 8 | Bug reports and feedback the coach offers | reports, kind `bug` or `feedback`, sent or declined, when the coach offers one and the person answers the sheet. Sent rows carry the person's words. Errors in the code are Grafana's, never a row. | Nobody yet. The route only takes posts and no admin command lists the rows; a panel counts them, and nobody reads it on a schedule. | partial | Sent and declined per week. | "Bug reports and feedback the coach offered to send, per week"; query 8 |
| 9 | Product notices | notices, and a notifications row of kind `notice` for each person a notice reaches, with opened_at. | You decide the next notice. `flask admin notice list` prints how many got and opened each one. | partial | Opened ÷ got, per notice. | "Notices: how many people each was sent to, and how many opened it"; query 9 |
| 10 | Which features people use | product_events: every screen a person opens and about sixty named taps. | What to cut or build next. Nobody reads it on a schedule. | partial | People active per week; days active per person. | "People active"; "Sessions"; "Taps"; "Screens opened"; "Features by use"; "Features by person"; "Feature use a day"; "Screens opened a day"; "First use of each feature, by person"; "Days active, by person"; "First session path"; "Cost per person per feature share"; the Features dashboard's section "What the coach and the app sent, and what came back"; the Features dashboard's section "Coverage of the basic data": "Coverage curve, across all sittings", "Coverage curve, each sitting", "Coach turns to 50% coverage, by family"; query 10 |
| 11 | Errors on the page and session replay | Grafana Faro on familydiagram.com: page errors in Grafana's logs with kind exception, and session replay with every element masked. | Someone opens Frontend Observability. You ruled that alerts wait until after the beta (09-22). | partial | Page errors and error groups per week; sessions with an error. Last known: 296 page errors in the 30 days to 09-29. | Query 11 |
| 12 | Server logs and traces | Alloy sends container logs, host metrics and the coach turn traces to Grafana Cloud. Every request carries an id. | Read when something breaks. No alerting. | partial | Server error lines per day; failed traces per day. | "Memory available"; "Disk free on /"; "CPU busy"; "Load (1m)"; "Memory used by container"; "CPU by container"; "Errors and exceptions (last 6h)"; "Log lines a minute by container"; query 12 |
| 13 | How much of the family evaluation is covered | The coach's own notes on each turn: whether the history has levelled off, its biggest gap, and whether the turn is evaluation or coaching. Stored with each coach turn's tool calls. | The three-generation coverage brainstorm, which you ruled waits for the frame session. Nothing counts the notes. | missing | None today. One candidate: the share of families with grandparents named. | None |
| 14 | Requests to join the beta | The landing page's form emails you each request. No table stores the requests, because new schema needs your yes [R-0581]. The page needs its Turnstile keys before it can go out. | You send an invite, a row in invitations. | missing | Requests: none. Invites sent per week. | Query 14 |
| 15 | Evals gating a prompt change | A live eval case built from your ruling, answered on the Claude Code subscription and saved as a replay in private/replays, then one paid run at the end of the batch. | The session ships the prompt change or holds it. Of the 3 prompt changes logged since 09-28, one is held and two are not evaluated. Ten live cases have no saved answers. | partial | Prompt changes shipped with a passing eval ÷ prompt changes made. Last known: 0 of 3. | doc/PROMPT_ENGINEERING_LOG.md; btcopilot/tests/live; private/replays |
| 16 | Recorded runs on the quality dashboard | A kept live run is copied into quality/evals, and every release loads it into quality_runs. | You see pass rates by model over time. Copying a run in is done by hand. | live | Recorded runs and their pass rate. Last known: 1 run (09-26), 9 of 9 passed, $0.64. | "Recorded runs: kept in the repository, loaded by every release"; "Behaviour evals: share of cases passed, by model and who answered"; "Behaviour evals: each case over time"; "Behaviour evals: each case, by model"; "Extraction F1 history, with its sub-scores"; query 16 |
| 17 | Which model replies better | shadow_turns: a real turn re-run on each of the person's shadow models, one row per model, never shown to them. Quality replay scores a model against a record you corrected. Your blind picks on Better replies, in model_picks. | You pick, and the tally decides the model. Beta users stay on Opus 5.5. Patrick's own account shadows on the latest Gemini Flash and the latest Sonnet (2026-09-29). Models a shadow or a replay can name, by alias: `opus-5.5`, `opus-4.6`, `sonnet`, `sonnet-5`, `haiku-4.5`, `gemini-flash` (3.8 Flash), `gemini-pro` (3.1 Pro preview), `gemini-3.6-flash`, `gemini-2.5-flash`, and `gpt` (GPT-6.1 Sol through OpenAI, under Patrick's BAA; key `OPENAI_API_KEY`, 2026-09-30). | partial | Won, lost and tied per model; shadow turns per week. | Query 17 |
| 18 | The IRR coding review | review_codings, review_votes, review_cuts (ratified_at, audit), review_rules. A coder is told of a cut to code by a notifications row of kind `task`, and nudged by one of kind `reminder`. | Ratified codings become ground truth, coding F1 is scored against them, and coding rules reach the prompt. Nothing writes coding F1 yet. The last meeting on file is 2026-04-27. | partial | Cuts ratified; coding F1 points. | "Coding F1 against the IRR group's ground truth: empty until the group ratifies its codings"; query 18 |
| 19 | The frame of reference test | A fresh session reads the frame document and one cluster, then writes a reading naming the key shift. Not built. | You grade the readings against your own across about ten clusters, and each disagreement becomes an example in the document. Waits on the frame session. | missing | Clusters where your reading agrees ÷ clusters graded. | None |
| 20 | Your rulings and the check that every test cites one | Your words become rulings in the store. Every test cites a ruling, and CI fails a test that cites none. | Sessions queue your rulings in the private corpus (RULINGS_TO_APPEND files), and you append them by hand with your key. | live | Rulings waiting and how long; rulings with no citing test. Last known: 14 waiting (R-0603 to R-0616, since 09-28); 115 uncited (46 owed a test, 69 waived). | fd-corpus/private/RULINGS_TO_APPEND_*.md; btcopilot/tests/conventions/exceptions.txt |
| 21 | Test spend | The live suite checks the balance, charges each call at the app's prices, stops at $3 a run, and writes a line per paid call to the eval ledger (btcopilot/tests/live/results/ledger.jsonl in the main clone, not in git). | Sessions use the free path first (the subscription or the local model) and ask you once per batch for paid calls. | live | API dollars per batch. Last known: $0.1563, the one calibration on 09-28. | The eval ledger |
| 22 | The migration check before a deploy | bin/migrationgate.py restores a copy of production into a throwaway Postgres and runs the migrations on it: row counts, orphans, and tool lines per coach reply. | The deploy goes ahead or stops. | live | Deploys, and deploys that ran the check. | `gh run list --workflow release.yml`; the deploy entries in doc/HISTORY.md |
| 23 | The efficiency skill | Your corrections on cost, speed and method, each dated, in ~/.claude/skills/efficiency/references/corrections.md. | Each correction becomes a numbered rule. A session writes bindings for the rules in play, and a rule broken twice goes into your CLAUDE.md. Bindings live in each job's temporary folder, so repeats are not counted across sessions. | live | New rules and repeats per week. Last known: 43 rules; 111 dated corrections from 09-22 to 09-29. | ~/.claude/skills/efficiency/ACCEPTANCE_CRITERIA.md; references/corrections.md |
| 24 | The scout and the loop review | The scout was to read the corpus and propose up to ten ranked process changes. | Retired on 2026-09-23 [R-0420] without ever running once. | retired | None. | None |
| 25 | Notes on votes in the chat | The optional note a person writes with a vote on shadow replies in the chat, stored with the vote in the model_picks table, source chat [R-0668]. | Nobody yet. The aim is an automated step that turns the notes into checks on replies, a rubric; it is not built and not designed. | open | None today. | None |
| 26 | Acceptable and best marks on votes in the chat | The replies a person marks acceptable and the one marked best, on every vote in the chat, stored with the vote in the model_picks table, source chat [R-0668]. | Nobody yet. Nothing turns the marks into a change to the coach; it is not built and not designed. | open | None today. | None |
| 27 | The measurement suite for the coach's replies | Not built. Checks on every stored reply, grouped by prompt version and model [R-0669]. | A session finds the checks and keeps improving them, and you review the direction. Parked on 2026-10-02 until you ask; files in the private corpus folder private/eval-suite/. | missing | None today. | None |

## Queries

Production tables are read with psql inside the fd-postgres container on the box, in a
read-only transaction:

```bash
ssh root@familydiagram "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' \
  fd-postgres psql -U familydiagram -d familydiagram -At -F '|' -v ON_ERROR_STOP=1" < queries.sql
```

Every query on people's data leaves out the claude-test account and scratch diagrams, the same
way the dashboards do, and returns counts only: never a name, an email or a person's words.
Grafana's logs are read with LogQL through Grafana's API, as the skill says.

### G1. Return within a week

```sql
with days as (
  select distinct d.user_id, s.created_at::date as day
  from statements s
  join discussions d on d.id = s.discussion_id
  join speakers sp on sp.id = s.speaker_id
  join users u on u.id = d.user_id
  where sp.type = 'Subject' and u.username not like 'claude-test%'
    and not exists (select 1 from diagrams dg where dg.id = d.diagram_id and dg.scratch)
    and s.created_at > now() - interval '37 days'
)
select count(distinct a.user_id) as chatted_8_to_30_days_ago,
       count(distinct a.user_id) filter (where exists (
         select 1 from days b where b.user_id = a.user_id and b.day > a.day and b.day <= a.day + 7
           and not exists (select 1 from proactive_messages pm where pm.user_id = a.user_id
                           and pm.sent_at between b.day - interval '2 days' and b.day + interval '1 day')
       )) as came_back_within_7_days
from days a
where a.day > current_date - 30 and a.day <= current_date - 7;
```

### G2. Journal-entry rate

```sql
select count(*) filter (where s.created_at > now() - interval '7 days') as messages_7d,
       count(distinct d.user_id) filter (where s.created_at > now() - interval '7 days') as people_7d,
       count(*) as messages_30d,
       count(distinct d.user_id) as people_30d,
       round(count(*)::numeric / nullif(count(distinct d.user_id), 0) / (30 / 7.0), 1) as per_person_per_week_30d
from statements s
join discussions d on d.id = s.discussion_id
join speakers sp on sp.id = s.speaker_id
join users u on u.id = d.user_id
where sp.type = 'Subject' and u.username not like 'claude-test%'
  and not exists (select 1 from diagrams dg where dg.id = d.diagram_id and dg.scratch)
  and s.created_at > now() - interval '30 days';
```

### 1. The watcher's findings and your accept-or-reject queue

```sql
select count(*) filter (where o.created_at > now() - interval '7 days') as rows_7d,
       count(*) filter (where o.created_at > now() - interval '30 days') as rows_30d,
       count(distinct left(md5(o.kind::text || ':' || coalesce(o.detail->>'reason', '')), 8)) as groups,
       (select count(*) from observation_rejects) as groups_rejected,
       (select max(created_at)::date from observation_rejects) as last_reject
from observations o
join diagrams d on d.id = o.diagram_id
join users u on u.id = d.user_id
where not d.scratch and u.username not like 'claude-test%'
  and o.kind::text in ('duplicate_person', 'duplicate_event', 'add_without_read', 'question_unsaid');
```

### 2. Refused writes and failed turns

```sql
with t as (
  select count(distinct mc.turn_id) as turns
  from model_calls mc join users u on u.id = mc.user_id
  where u.username not like 'claude-test%' and mc.created_at > now() - interval '30 days'
)
select o.kind::text,
       count(*) filter (where o.created_at > now() - interval '7 days') as rows_7d,
       count(*) as rows_30d,
       round(100.0 * count(*) / nullif((select turns from t), 0), 1) as per_100_turns_30d
from observations o
join diagrams d on d.id = o.diagram_id
join users u on u.id = d.user_id
where not d.scratch and u.username not like 'claude-test%'
  and o.created_at > now() - interval '30 days'
  and o.kind::text in ('tool_refused', 'step_cap', 'turn_failed', 'turn_declined', 'play_refused', 'play_failed')
group by 1;
```

### 3. Cost per turn and dollars by kind

The Coach cost dashboard (`deploy/grafana/fd-cost.json`, written 2026-10-01 for FD-366) follows a prompt or model change through to the cost of a real turn. It opens with the single figure to watch, with no projection over sittings: "Cost per turn now" (a large tile: the latest day with a real coach turn, with the day shown) and, small beneath it, "Cost per turn, last 7 days" (a tile: dollars of coach calls over distinct coach turns in the last 7 days, two decimals) and "Average cost per turn" (a line: dollars over distinct coach turns for each day, warm and cold together, with a 7-day rolling mean) beside them. Coach calls only; real families only, as everywhere. A turn is the coach calls sharing one turn id; it starts when its first call starts (the row's time less the call's duration). A turn is cold when it starts more than 5 minutes after the start of the same family's previous turn, the cache's life [R-0595]; the first turn of a family is cold. Turns are read from 14 days before the range so the first day's mean and cold flags are whole. The coverage panel takes the last done row of each day on each record, known items over required items. Not on it, because the database does not hold them: the release a turn ran on (model_calls and the done rows carry no version), and the replay passes' scores and settings (each pass's line is kept only in the eval ledger file inside the container, lost when the container is replaced; the database keeps the pass's model calls as model_calls rows of purpose `replay` on a scratch record, with no key, thinking level, prompt version or score).

The tool list differs by role (a coder's navigate also lists the coder's screens, R-0626), so a coder's and a non-coder's turns share no cached prefix: the tools head it.

```sql
select count(distinct mc.turn_id) filter (where mc.created_at > now() - interval '7 days') as turns_7d,
       count(distinct mc.turn_id) as turns_30d,
       round(coalesce(sum(mc.cost_usd) filter (where mc.created_at > now() - interval '7 days'), 0), 2) as dollars_7d,
       round(coalesce(sum(mc.cost_usd), 0), 2) as dollars_30d,
       round(sum(mc.cost_usd) / nullif(count(distinct mc.turn_id), 0), 3) as dollars_per_turn_30d,
       round(sum(mc.cache_read_tokens)::numeric
             / nullif(sum(mc.input_tokens + mc.cache_read_tokens + mc.cache_creation_tokens), 0), 2) as cache_hit_share_30d
from model_calls mc
join users u on u.id = mc.user_id
where u.username not like 'claude-test%' and mc.created_at > now() - interval '30 days'
  and mc.purpose = 'coach'
  and not exists (select 1 from diagrams dg where dg.id = mc.diagram_id and dg.scratch);
```

### 4. Each beta user sees their own use and cost

```sql
select tm.period, count(*) as people, sum(tm.input_tokens + tm.output_tokens) as tokens,
       count(*) filter (where tm.cap is not null) as with_a_cap
from token_meters tm join users u on u.id = tm.user_id
where u.username not like 'claude-test%'
group by 1 order by 1 desc limit 2;
```

### 5. Messages the coach writes first

```sql
select o.kind::text,
       count(*) filter (where o.created_at > now() - interval '7 days') as rows_7d,
       count(*) filter (where o.created_at > now() - interval '30 days') as rows_30d
from observations o
join diagrams d on d.id = o.diagram_id
join users u on u.id = d.user_id
where not d.scratch and u.username not like 'claude-test%' and o.kind::text like 'proactive_%'
group by 1;

select pm.trigger::text, count(*) as written, count(pm.sent_at) as sent, count(pm.replied_at) as replied
from proactive_messages pm join users u on u.id = pm.user_id
where u.username not like 'claude-test%' and pm.created_at > now() - interval '30 days'
group by 1;
```

### 6. The coach's memory across sittings

```sql
with t as (
  select distinct mc.turn_id
  from model_calls mc join users u on u.id = mc.user_id
  where u.username not like 'claude-test%' and mc.created_at > now() - interval '30 days'
)
select count(*) as turns_30d,
       count(*) filter (where exists (select 1 from observations o
                                      where o.turn_id = t.turn_id and o.kind::text = 'earlier_edit')) as turns_with_earlier_edit
from t;
```

### 7. Corrections by the person to the coach's record

```sql
select 'hand_edits' as what,
       count(*) filter (where c.created_at > now() - interval '7 days') as rows_7d,
       count(*) filter (where c.created_at > now() - interval '30 days') as rows_30d
from diagram_changes c
join diagrams d on d.id = c.diagram_id
join users u on u.id = d.user_id
where c.author::text = 'user' and not d.scratch and u.username not like 'claude-test%'
  and exists (select 1 from diagram_changes cc where cc.diagram_id = c.diagram_id and cc.author::text = 'coach')
union all
select i.kind::text,
       count(*) filter (where i.created_at > now() - interval '7 days'),
       count(*) filter (where i.created_at > now() - interval '30 days')
from diagram_interactions i join users u on u.id = i.user_id
where i.kind::text in ('doesnt_fit', 'dismiss') and u.username not like 'claude-test%'
group by 1;
```

### 8. Bug reports and feedback the coach offers

```sql
select r.kind::text, r.status::text,
       count(*) filter (where r.created_at > now() - interval '7 days') as rows_7d,
       count(*) filter (where r.created_at > now() - interval '30 days') as rows_30d
from reports r left join users u on u.id = r.user_id
where coalesce(u.username, '') not like 'claude-test%'
group by 1, 2;
```

### 9. Product notices

```sql
select n.id, n.created_at::date as written, count(nt.id) as got, count(nt.opened_at) as opened
from notices n left join notifications nt on nt.notice_id = n.id
group by 1, 2 order by 2 desc limit 10;

select nt.kind::text, nt.channel::text,
       count(*) filter (where nt.created_at > now() - interval '7 days') as rows_7d,
       count(*) filter (where nt.created_at > now() - interval '30 days') as rows_30d,
       count(nt.opened_at) filter (where nt.created_at > now() - interval '30 days') as opened_30d
from notifications nt join users u on u.id = nt.user_id
where u.username not like 'claude-test%'
group by 1, 2;
```

### 10. Which features people use

```sql
select count(distinct pe.user_id) filter (where pe.created_at > now() - interval '7 days') as people_7d,
       count(distinct pe.user_id) filter (where pe.created_at > now() - interval '30 days') as people_30d,
       count(*) filter (where pe.created_at > now() - interval '7 days') as events_7d,
       count(*) filter (where pe.created_at > now() - interval '30 days') as events_30d
from product_events pe join users u on u.id = pe.user_id
where u.username not like 'claude-test%';

select string_agg(days::text, ',' order by days desc) as days_active_per_person_30d
from (select count(distinct pe.created_at::date) as days
      from product_events pe join users u on u.id = pe.user_id
      where u.username not like 'claude-test%' and pe.created_at > now() - interval '30 days'
      group by pe.user_id) x;

select pe.name, count(*) as uses_30d
from product_events pe join users u on u.id = pe.user_id
where u.username not like 'claude-test%' and pe.created_at > now() - interval '30 days'
  and pe.name <> 'screen_open'
group by 1 order by 2 desc limit 10;
```

**Coverage of the basic data.** A section of the Features dashboard, read from
the done row each coach turn leaves in turn_events, which carries the counts of
the basic data's items before and after the turn (doc/COVERAGE.md). Real
families only: scratch diagrams, synthetic sittings and the claude-test
accounts are left out.

- "Coverage curve, across all sittings": one line per family, the items known
  after each coach turn as a share of the items required after it, against the
  family's coach turns counted from its first.
- "Coverage curve, each sitting": the same share, one line per sitting, with
  the coach turns counted again from the start of each sitting.
- "Coach turns to 50% coverage, by family": the first coach turn after which
  half the required items were known; families that have not reached half are
  left out.

Next, not built: facts per evaluation question; coverage gained on coaching
turns without an evaluation question; engagement after an evaluation question;
ask density against return within a week.

### 11. Errors on the page and session replay

LogQL on the data source `grafanacloud-logs`:

```
sum(count_over_time({kind="exception"}[7d]))
sum(count_over_time({kind="exception"}[30d]))
count(sum by (value) (count_over_time({kind="exception"} | logfmt | keep value [30d])))
count(sum by (session_id) (count_over_time({kind="exception"} | logfmt | keep session_id [30d])))
```

### 12. Server logs and traces

LogQL on `grafanacloud-logs`, the same filter as the "Errors and exceptions (last 6h)" panel:

```
sum by (service_name) (count_over_time({service_name=~"fd-app|fd-worker|fd-beat|fd-shadow"} |~ "(?i)error|traceback|exception" [7d]))
```

Failed traces: TraceQL `{ status = error }` on the data source `grafanacloud-traces`, over 7 days.

### 14. Requests to join the beta

```sql
select count(*) filter (where created_at > now() - interval '7 days') as invites_7d,
       count(*) filter (where created_at > now() - interval '30 days') as invites_30d
from invitations;
```

### 16. Recorded runs on the quality dashboard

```sql
select kind::text, count(distinct ran_at) as runs, max(ran_at)::date as last_run
from quality_runs group by 1;
```

### 17. Which model replies better

```sql
select count(*) filter (where created_at > now() - interval '7 days') as shadow_turns_7d,
       count(*) filter (where created_at > now() - interval '30 days') as shadow_turns_30d,
       count(*) filter (where error is not null and created_at > now() - interval '30 days') as failed_30d,
       round(coalesce(sum(cost_usd) filter (where created_at > now() - interval '30 days'), 0), 2) as dollars_30d
from shadow_turns;

select source::text, coalesce(choice::text, 'not yet') as choice, count(*) as picks
from model_picks group by 1, 2;
```

Past turns can be run on a shadow model too, so the comparison does not wait for new
turns. The backfill rebuilds each record as it stood before each past turn by taking
that turn's changes, and every change after it by anyone, back off today's record,
newest first; the shadow then runs on that copy exactly as a live one does. It is run
by hand for one person and a list of model aliases with `flask admin coach-model
backfill <email> <alias>...`: without `--yes` it prints, per model, the turns to run,
the replies too old to carry a turn id (skipped) and the estimated dollars priced from
the real turns' token counts; with `--yes` it hands the turns to the shadow queue
[R-0596].

Every quality replay is kept as a row in the `replay_passes` table: model, thinking
level, prompt version, the person and statements replayed, turns, calls, tokens,
dollars, the scores by part, the release and who answered. A pass under a key (case,
prompt version, model, thinking level) already in the table is not run again without
`--again`, and `--key` prints the passes kept under it. The cost dashboard's Replay
passes panel lists them, beside its cost per coach turn by release [R-0597].

```sql
select created_at::date, model, thinking, prompt, release, turns, calls,
       round(cost_usd / nullif(turns, 0), 4) as dollars_per_turn, overall
from replay_passes order by created_at desc;
```

### 18. The IRR coding review

```sql
select count(*) as cuts, count(ratified_at) as ratified, max(ratified_at)::date as last_ratified,
       max(meeting_date) as last_meeting,
       (select count(*) from review_votes where created_at > now() - interval '30 days') as votes_30d,
       (select count(*) from review_codings where created_at > now() - interval '30 days') as codings_30d,
       (select count(*) from quality_runs where kind::text = 'coding_f1') as coding_f1_points
from review_cuts;
```
