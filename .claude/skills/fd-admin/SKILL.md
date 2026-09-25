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

### `flask admin db`

The chat database's own migration chain.

### `flask admin db current`

Which revision the database is at.

### `flask admin db upgrade`

Bring the database up to the newest revision, creating it from empty if it holds nothing yet.

Changes something: needs `--yes`.

### `flask admin diagrams`

The family records.

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

### `flask admin diagrams show <diagram_id>`

One record's counts.

| Argument | What it is |
|---|---|
| `diagram_id` | required |
| `--json` | Print JSON, not a table. |

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

Go back once through every past session not yet gone through and fill in the impressions said in it. Makes model calls. Without --yes it prints what it would do and writes nothing.

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

### `flask admin observations`

What the watcher after each coach turn noticed.

### `flask admin observations list`

Every row, oldest first.

| Argument | What it is |
|---|---|
| `--diagram` | Only one record's rows. |
| `--kind` | Only one kind of row. |
| `--json` | Print JSON, not a table. |

### `flask admin questions`

The questions the coach keeps in each record.

### `flask admin questions backfill`

Go back once through every past session not yet gone through and fill in the questions said in it. Makes model calls. Without --yes it prints what it would do and writes nothing.

Changes something: needs `--yes`.

| Argument | What it is |
|---|---|
| `--diagram` | Only this record. |
| `--json` | Print JSON, not a table. |

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
