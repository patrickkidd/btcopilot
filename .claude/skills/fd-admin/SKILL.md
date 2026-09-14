---
name: fd-admin
description: Run the Family Diagram site from the command line — accounts, licences, family records, the one-time import of the old Pro database, monthly coach caps, and the coding meeting. Use when asked to look up or change anything on the running site.
---

# Running the site from the command line

There is no admin web page. Everything below is run on the engine, from the
repository, as `flask admin ...`.

Every command prints a table. Add `--json` to any of them to get the same rows
as JSON, which is what to use when the answer is going to be read by a program.
A command that changes something prints the row it changed.

This file is generated from the commands themselves by `flask admin skill`. Do
not edit it by hand; change the commands and generate it again.

## The commands

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

| Argument | What it is |
|---|---|
| `dump` | required |
| `--json` | Print JSON, not a table. |

### `flask admin licences`

What people have bought.

### `flask admin licences grant <email> <plan>`

Give somebody a licence on the plan named.

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

| Argument | What it is |
|---|---|
| `key` | required |
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

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin review nudge on`

Let the app nudge coders again.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin review nudge show`

Whether nudging is on, and when the agenda was last nudged.

| Argument | What it is |
|---|---|
| `--json` | Print JSON, not a table. |

### `flask admin skill`

Write the skill file an agent reads before running these commands.

| Argument | What it is |
|---|---|
| `--check` | Fail if the file on disk is not what the commands say. |
| `--out` | Write somewhere else. |

### `flask admin token-cap`

The monthly ceiling on coach use.

### `flask admin token-cap set <email> <tokens>`

Set the cap, in tokens a month. Use the word default for everyone else.

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

| Argument | What it is |
|---|---|
| `email` | required |
| `--base-url` | Overrides the site address the link points at. |
| `--json` | Print JSON, not a table. |

### `flask admin users list`

Every account, one line each.

| Argument | What it is |
|---|---|
| `--role` | Only people with this role. |
| `--email` | Only addresses containing this text. |
| `--json` | Print JSON, not a table. |

### `flask admin users roles <email> [roles]`

Show somebody's roles, or set them to the roles named.

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
