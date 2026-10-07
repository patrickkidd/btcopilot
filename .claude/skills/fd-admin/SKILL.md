---
name: fd-admin
description: Run the Family Diagram site from the command line — accounts, licences, family records, the one-time import of the old Pro database, monthly coach caps, and the coding meeting. Use when asked to look up or change anything on the running site.
---

# Running the site from the command line

There is no admin web page. Everything below is run on the engine, from the
repository, as `flask admin ...`.

## Confirmation

Run every command as `flask admin run -- <words>`, for example
`flask admin run -- users list`.
A command that only reads runs at once.
A command that changes something needs `--yes` among the words. Without it
nothing runs: the preview line and the command's help are printed instead.
Show that preview to the person and wait for their yes before adding `--yes`.

Every command prints a table. Add `--json` to any of them to get the same rows
as JSON, which is what to use when the answer is going to be read by a program.
A command that changes something prints the row it changed.

This file is generated from the commands themselves by `flask admin skill`. Do
not edit it by hand; change the commands and generate it again.

## The commands

### `flask admin case-report`

The case report's cards in each record.

### `flask admin case-report backfill`

Put each family's raised guesses and its questions on the case report's cards, and add the question about the person's own part where the record has none, as the coach would have had the report been there from the start. The dry run makes one model call per family that has a raised guess or question on no card that came in after the newest card was set, goes to the model-calls ledger, prints each card before and after, and saves the plan to a file; --apply --plan writes exactly that plan, checked again, with no model call.

Changes something with `--apply`. Through `flask admin run`, the words also need `--yes`, even for the dry run.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--apply` | Write saved plans; the default, --dry-run, makes the model call and saves the plan, writing nothing to the record. |
| `--plan` | With --apply: a plan file the dry run printed. |
| `--plans` | Where the dry run saves its plans. |
| `--json` | Print JSON, not a table. |

### `flask admin coach-model`

The coach model and the shadow models of one person, and the shadow models anyone may have.

### `flask admin coach-model backfill <email> <aliases>`

Run each of this person's past turns again on each model alias given, over the record as it stood before each turn. Makes model calls. Without --yes it prints, per model, the turns to run, the replies too old to run and what the run would cost, and writes nothing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `aliases` | required |
| `--json` | Print JSON, not a table. |

### `flask admin coach-model set <email> <alias>`

Coach this person on a model alias, or on the default with the word default.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `alias` | required |
| `--json` | Print JSON, not a table. |

### `flask admin coach-model shadows`

The models staff may turn on to run each turn again, for everyone.

### `flask admin coach-model shadows set <aliases>`

The models staff may turn on, as model aliases. A person who had one that is left out loses it on their next turn or settings visit.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `aliases` | required |
| `--json` | Print JSON, not a table. |

### `flask admin coach-model shadows show`

The models staff may turn on; Sonnet alone when none were set.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin coach-model show [email]`

One person's models, or the default and everyone who differs from it.

| Argument | What it is |
|---|---|
| `email` | optional |
| `--json` | Print JSON, not a table. |

### `flask admin db`

The chat database's own migration chain.

### `flask admin db current`

Which revision the database is at.

### `flask admin db upgrade`

Bring the database up to the newest revision, creating it from empty if it holds nothing yet.

Changes something: needs `--yes`.

### `flask admin diagrams`

The family records.

### `flask admin diagrams dates`

List each event date stored as a Qt date object rather than text, with the text it becomes, and why the date rule would refuse the write when it would; nothing else in the event is checked or changed. --apply writes each record's dates the rule takes as one change row that `diagrams undo` takes back.

Changes something with `--apply`. Through `flask admin run`, the words also need `--yes`, even for the dry run.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--apply` | Write the text dates; the default, --dry-run, lists them and writes nothing. |
| `--json` | Print JSON, not a table. |

### `flask admin diagrams export <diagram_id>`

Write one record out as JSON.

| Argument | What it is |
|---|---|
| `diagram_id` | required |
| `--out` | Write to this file instead of the screen. |

### `flask admin diagrams list`

Every record, with how much is in it.

| Argument | What it is |
|---|---|
| `--email` | Only the records one person owns. |
| `--json` | Print JSON, not a table. |

### `flask admin diagrams regroup`

Regroup each record whose events changed since its last grouping, or that has events to group and no groups. The dry run lists them and makes no model call; --apply makes the grouping calls a turn makes, one or two per record, each in the model-calls ledger, and writes each record's new grouping as one change row that `diagrams undo` takes back. A record whose answers are both refused gets the rules' groups under their years, and `failed` says so.

Changes something with `--apply`. Through `flask admin run`, the words also need `--yes`, even for the dry run.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--apply` | Regroup the records listed; the default, --dry-run, lists them and makes no model call. |
| `--json` | Print JSON, not a table. |

### `flask admin diagrams show <diagram_id>`

One record's counts.

| Argument | What it is |
|---|---|
| `diagram_id` | required |
| `--json` | Print JSON, not a table. |

### `flask admin diagrams undo <diagram_id> <change_ids>`

Take these change rows of one record back off it, newest first, each logged as its own undo naming the row; the questions and impressions they added come off too. A value changed since stops it before anything is written. Without --yes it prints what each row would take back and writes nothing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `diagram_id` | required |
| `change_ids` | required |
| `--json` | Print JSON, not a table. |

### `flask admin flow`

The conversational-flow numbers per model and prompt version.

### `flask admin flow track`

Count the flow rules over every real thread, leaving out claude-test accounts, scratch records and plays, and add the counts per thread, model, prompt version and rules version to threads.jsonl and the return of each account to accounts.jsonl. No text is written.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--export` | A folder holding stmts.json and changes.json. |
| `--database` | Read the configured database. |
| `--out` | Where threads.jsonl and accounts.jsonl go; never inside a git work tree. |
| `--again` | Recompute keys already written. |
| `--production` | Read the production database: Patrick agreed. |

### `flask admin imports`

The one-time read of the old Pro database.

### `flask admin imports dry-run <dump>`

Read the dump, or a live connection string, and report what would come across, writing nothing.

| Argument | What it is |
|---|---|
| `dump` | required |
| `--json` | Print JSON, not a table. |

### `flask admin imports run <dump>`

Read the dump and write the accounts and records it holds.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `dump` | required |
| `--json` | Print JSON, not a table. |

### `flask admin impressions`

The impressions the coach keeps in each record.

### `flask admin impressions backfill`

Go back once through every past session not yet gone through, and through what a session gone through holds after the last message its pass read, and fill in the impressions said there. Makes model calls. Without --yes it prints what it would do and writes nothing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--json` | Print JSON, not a table. |

### `flask admin licences`

What people have bought.

### `flask admin licences grant <email> <plan>`

Give somebody a licence on the plan named.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `plan` | required |
| `--json` | Print JSON, not a table. |

### `flask admin licences list`

Every licence, one line each.

| Argument | What it is |
|---|---|
| `--email` | Only the licences one person holds. |
| `--plan` | Only this plan's licences. |
| `--json` | Print JSON, not a table. |

### `flask admin licences plans`

The plans a licence can be granted on.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin licences revoke <key>`

Turn a licence off, which stops the app it unlocks.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `key` | required |
| `--json` | Print JSON, not a table. |

### `flask admin notice`

Product notices shown in the app, to everyone, a role, or named people.

### `flask admin notice list`

Every notice, newest first: who it is for, how many that is now, and how many have it and opened it.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin notice send`

Keep a notice and send it now to everyone it is for: a push to whoever has one, else an email when --email is given, and in the app's own list either way. Whoever joins its audience later finds it in the app's list the next time they open the app. Prints the notice and how many people it was sent to.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--to` | everyone, a role (subscriber, auditor, admin), or email addresses joined by commas. |
| `--title` | The heading, and the words of the push. |
| `--body` | One or two short sentences. |
| `--link` | The screen a tap opens: account, coach_settings, task, agenda, or any address in the app such as /app/account/notices; left out, it opens nothing. |
| `--until` | The last day, in UTC, that it reaches anyone new; left out, it runs on. |
| `--email` | Email everyone it is for who has no browser that takes a push. |
| `--by` | The email of the admin sending it. |
| `--json` | Print JSON, not a table. |

### `flask admin observations`

What shows the coach or the app needing tuning.

### `flask admin observations list`

Every row, oldest first.

| Argument | What it is |
|---|---|
| `--diagram` | Only one record's rows. |
| `--kind` | Only one kind of row. |
| `--json` | Print JSON, not a table. |

### `flask admin observations queue`

The ten biggest groups of rows not yet rejected, test accounts left out: a kind and its reason with ids taken out, most often first.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin observations reject <key>`

Take the group with this key off the queue for good.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `key` | required |
| `--json` | Print JSON, not a table. |

### `flask admin proactive`

Messages the coach writes before the person does.

### `flask admin proactive run`

Write and send at most one message per person, within their budget. Each person nothing went to gets the reason instead. Then each coder's reminder that is due, a row each, outside that budget.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--dry-run` | Print what would be sent; keep and send nothing, and make no model call. |
| `--json` | Print JSON, not a table. |

### `flask admin quality`

The recorded runs the quality dashboard reads.

### `flask admin quality keep-passes`

Keep the replays of 2026-09-30 in the replay passes table.

Changes something: needs `--yes`.

### `flask admin quality load [root]`

Load every recorded run under a checkout or the image into the table, updating the ones already there.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `root` | optional |

### `flask admin quality replay <discussion_id> <model> <reference_diagram_id>`

Replay a session's words on MODEL onto a scratch record, score it against the record Patrick corrected, and append one ledger line. It spends on the model and writes scratch records. MODEL is a model alias; the coach's own is opus-5.5.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `discussion_id` | required |
| `model` | required |
| `reference_diagram_id` | required |
| `--cap` | Dollars; no model call is made that could pass it. |
| `--thinking` | How hard the coach thinks, for this replay only. |
| `--prompt-dir` | A folder holding any of agent.prompty and fragments/*.md; each file there replaces the same-named prompt for this replay only, and the rest are read from the usual places. |
| `--turns` | The last turn replayed. |
| `--production` | Run on the production database: Patrick agreed the spend. |

### `flask admin quality replay-person <user_id> <model>`

Replay the words of the live coach turns one person took, oldest first, on MODEL onto one scratch record that starts as their record stood before the first, score it against their record as it stood after the last, keep the pass and append one ledger line. A key a kept pass already holds is not run again. MODEL is a model alias; the coach's own is opus-5.5.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `user_id` | required |
| `model` | required |
| `--reference` | The diagram to score against; the person's record as it stood after the last replayed turn when left out. |
| `--key` | Print the key and the passes kept under it, and stop. |
| `--again` | Run a key a kept pass already holds. |
| `--start` | Begin at this turn, going on in the scratch session and record of the kept pass --after names, which replayed every turn before it. |
| `--after` | The kept pass to go on from. |
| `--cap` | Dollars; no model call is made that could pass it. |
| `--thinking` | How hard the coach thinks, for this replay only. |
| `--prompt-dir` | A folder holding any of agent.prompty and fragments/*.md; each file there replaces the same-named prompt for this replay only, and the rest are read from the usual places. |
| `--turns` | The last turn replayed. |
| `--production` | Run on the production database: Patrick agreed the spend. |

### `flask admin questions`

The questions the coach keeps in each record.

### `flask admin questions backfill`

Go back once through every past session not yet gone through, and through what a session gone through holds after the last message its pass read, and fill in the questions said there. Makes model calls. Without --yes it prints what it would do and writes nothing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--json` | Print JSON, not a table. |

### `flask admin questions catch-up`

Bring each record's questions to where they would stand had the coach's question rules been there from the first session: a fact question filed on the wrong kind of thing moves to the right person or pair-bond, a fact the person already said is kept as a question already answered, a story the talk moved past is kept to come back to, and each day the coach asked an open question again and the person passed over it is kept on that question. Chat messages are never changed. The dry run makes one model call per record with a session, goes to the model-calls ledger, and saves a plan a person can read; --apply --plan writes exactly that plan, each item one change row that `diagrams undo` takes back, with no model call.

Changes something with `--apply`. Through `flask admin run`, the words also need `--yes`, even for the dry run.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--apply` | Write saved plans; the default, --dry-run, makes the model call and saves the plan, writing nothing to the record. |
| `--plan` | With --apply: a plan file the dry run printed. |
| `--plans` | Where the dry run saves its plans. |
| `--json` | Print JSON, not a table. |

### `flask admin report`

The report sheet in a person's app, raised by hand in development.

### `flask admin report offer <email> <words>`

Offer to send WORDS from the person's app, as the coach's report tool does: the offer goes on their next coach turn, or the one running now, and the sheet comes up once that reply is done, at most once a sitting on a device. Never on production.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `words` | required |
| `--kind` | Which sheet: feedback, or a bug report. |
| `--wait` | Seconds to wait for the person's next message. |

### `flask admin review`

The coding meeting.

### `flask admin review agenda`

What the next meeting has in front of it: the cuts, and the rules somebody flagged.

| Argument | What it is |
|---|---|
| `--meeting-date` | The meeting's day, as 2026-09-18. |
| `--json` | Print JSON, not a table. |

### `flask admin review codings`

How far each coder has got on what is on the agenda.

| Argument | What it is |
|---|---|
| `--meeting-date` | Only this meeting's codings. |
| `--cut` | Only this cut's codings. |
| `--json` | Print JSON, not a table. |

### `flask admin review cuts`

The windows of a conversation the room codes.

| Argument | What it is |
|---|---|
| `--meeting-date` | Only this meeting's cuts. |
| `--all` | Ratified cuts as well. |
| `--json` | Print JSON, not a table. |

### `flask admin review nudge`

Whether the app may nudge the coders who are not done.

### `flask admin review nudge off`

Stop the app nudging anybody.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin review nudge on`

Let the app nudge coders again.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin review nudge show`

Whether nudging is on, and when the agenda was last nudged.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin run [words]`

Run an admin command given after --. One that changes something needs --yes; without it the preview is printed and nothing runs.

| Argument | What it is |
|---|---|
| `words` | optional |

### `flask admin skill`

Write the skill file an agent reads before running these commands.

| Argument | What it is |
|---|---|
| `--check` | Fail if the file on disk is not what the commands say. |
| `--out` | Write somewhere else. |
| `--print` | Print the file instead of writing it. |

### `flask admin titles`

The short titles of noted events and shifts.

### `flask admin titles fill`

Give each noted event and shift with no title one: from --file when it has one; else its description when that is already 2 to 4 words ending on a whole phrase and naming no one the event links, which also covers events written after the file was made; else, for a shift with no words and no notes, what moved; else, with --ask, the app's own model. Prints every event it found without a title, the title it gets and where that came from; the model is asked only with --yes. With --yes it refuses, before any model call and writing nothing, while an event would be left "still untitled": a record holding one does not load.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--diagram` | Only these records. |
| `--file` | Titles read and approved: a JSON list of {diagram, event, title}, the shape --json prints. |
| `--ask` | Have the app's own model write the titles nothing else gives, one short call per event, each written to the model-calls ledger. |
| `--json` | Print JSON, not a table. |

### `flask admin token-cap`

The monthly ceiling on coach use.

### `flask admin token-cap set <email> <tokens>`

Set the cap, in tokens a month. Use the word default for everyone else.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `tokens` | required |
| `--json` | Print JSON, not a table. |

### `flask admin token-cap show [email]`

The cap for one person, or the default and everyone who differs from it.

| Argument | What it is |
|---|---|
| `email` | optional |
| `--json` | Print JSON, not a table. |

### `flask admin users`

The people with accounts.

### `flask admin users invite <email>`

A one-time sign-in link, which also creates the account on first use.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `--base-url` | Overrides the site address the link points at. |
| `--send` | Also email the link to the address. |
| `--json` | Print JSON, not a table. |

### `flask admin users list`

Every account, one line each.

| Argument | What it is |
|---|---|
| `--role` | Only people with this role. |
| `--email` | Only addresses containing this text. |
| `--json` | Print JSON, not a table. |

### `flask admin users prefs <email> [key] [value]`

Show somebody's settings, or set the one named to the value given. `spotlight chip` gives them back the old way a chip lit the picture; `spotlight unified`, the default, has a chip and a dot do the same thing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `key` | optional |
| `value` | optional |
| `--json` | Print JSON, not a table. |

### `flask admin users roles <email> [roles]`

Show somebody's roles, or set them to the roles named.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `email` | required |
| `roles` | optional |
| `--json` | Print JSON, not a table. |

### `flask admin users show <email>`

One account in full, with the licences and diagrams it owns.

| Argument | What it is |
|---|---|
| `email` | required |
| `--json` | Print JSON, not a table. |
