# Companion API (phase 2)

Everything is under `/personal`, behind the training-app login, on the user's
own free diagram. Writes need the CSRF token from the page's
`<meta name="csrf-token">` in `X-CSRFToken`. A rejected value returns 400 with a
plain-text reason; a write the record refuses returns 400 with the rule in plain
words for the person editing (no ids, no field names), while the coach gets the
same rule in its own words. Another user's resource returns 404. Every answer
carries `X-Request-Id`, the id every server log line written while serving it
names; a proxy's own error page has none.

## Chat and sessions (a session is a `Discussion`)

| | |
|---|---|
| `POST /chat` | `{statement}` into the family's current sitting: the session last spoken in, or a new one once its last statement is 12 hours old |
| `GET /statements` | the family's one thread across its sessions, 50 statements at a time, oldest first; `?before=<statement id>` reads the page just older. Each carries `session_id`; a session's first statement carries `sitting: {id, started, previous_started}`, the last being when the sitting before it started, or null for the first |
| `POST /sessions/<id>/statements` | `{statement}` into a named session |
| `GET /sessions` | the user's sessions on the family the app is on (`?diagram_id=` another readable one), most recently active first; `?all=true`, admins only (403 otherwise), is every session on every family, whoever had it, each with `family`, its family's name, which is what the meeting page puts one on the agenda from; `?words=` keeps those where something said carries every word, the coach's chat search, each with `match`, the newest line that does, chips shown as their words |
| `POST /sessions` | new empty session, 201 |
| `GET /sessions/<id>` | one session plus `statements: [{id, role, text}]`, role is `user` or `coach` |
| `PATCH /sessions/<id>` | `{title}` only |

A session reads `{id, title, summary, last_activity, message_count}`. The title
and summary are written by the coach after the first exchange and are editable
after that. A session is a sitting: nobody
opens, starts or switches one; the page shows one thread with a dated line where
each sitting starts, which adds the start time when the sitting before it started the same day, and the server starts the next sitting when the family has been
quiet 12 hours (`discussions.sitting`, which coach-first messages use too).

A chat reply reads `{statement, refs, discussion_id, session}`.

## Chips (`refs`)

`refs` is what the coach's reply pointed at, already stripped out of
`statement`. Empty when the reply pointed at nothing. Each entry carries
`kind`, `label`, and the fields for its kind:

| kind | payload |
|---|---|
| `chapter` | `cluster_id` |
| `events` | `event_ids` |
| `person` | `person_id` |
| `range` | `start`, `end` (ISO dates) |

References the diagram cannot aim at are dropped server-side, so every chip
resolves.

## Timeline

`GET /timeline` — unchanged, plus `coded_in`: `{event id: {discussion_id,
statement_id}}` for events whose coding session is known, which is what "coded
in …" reads. Events never traced are absent.

## Preferences

`GET /preferences`, `PATCH /preferences` — one object: `speak`, `proactive`,
`mode`, `theme`, `bug_reports` (`ask` or `always`), `first_name`, `last_name`,
`birthdate`. PATCH takes any subset; an unknown key or a bad value is a 400.

## Reports

`POST /observations` — a bug or feedback the person chose to send, stored as one
row in the observations table on the diagram the app is on. `kind` is `bug` or
`feedback`; `turn_id` is the turn it came from, empty when there is none. It
carries one of these sets of fields: `text`, the person's words the coach offered
to send (either kind); for a bug, `text`, `error` and `version`, or, for a request
the server broke on, `status`, `method`, `path` (every id in it replaced by
`:id`), `request_id` (the `X-Request-Id` its answer carried) and `version`, never
the server's own words. The page reports a request only when the server itself
answered 500 or above: never no answer, a refusal, a proxy's error page, or this
route. Any other kind or set of fields is a 400; answers `{"id"}` with 201.
Reports stay out of the queue Patrick accepts or rejects.

## Account

`GET /account` — `email`, `sign_in_method`, `plan` (placeholder text until
Patrick sets the numbers), `diagrams` (`id`, `name`, `last_activity`, `free`),
`licenses` (`id`, `policy`, `status`). Sign out is the existing auth route.

## Notifications

| | |
|---|---|
| `GET /notifications` | the signed-in person's unread rows of every kind, newest first, as a bare array; `?all=true` adds the opened ones. Each call first makes a row, channel `app`, for every running notice meant for them that they have none for: one whose audience they joined after it was sent |
| `PATCH /notifications/<id>` | `{"opened": true}` only, for opening and for dismissing alike; the first stamp counts; answers the row |
| `GET /push-subscriptions`, `POST /push-subscriptions` | the server's public key with this person's browsers; a browser's own subscription, 201 |

A row reads `{id, kind, channel, title, body, link, statement_id,
discussion_id, cut_id, created_at, opened_at}`. `kind` is `coach`, `task`,
`reminder` or `notice`. `channel` is `push`, `email`, or `app` for a notice sent
nowhere but this list. A notice carries its own `title`, `body` and `link`; any
other kind carries the push's title, a null body, and the link `task` for a task
or reminder, null for a coach message, which opens its thread at
`statement_id`. `link` is one of the fixed screens `account`, `coach_settings`,
`task` or `agenda`, or any address in the app starting with `/app/` (the address
table is in [SCREENS.md](SCREENS.md#addresses)), or null. The notices table keeps
it as text with a check that it is one or the other, and `flask admin notice send
--link` refuses an address the app does not have.

`flask admin notice send` writes a notice and sends it at once to everyone it
is for, each getting their own row: a push to every browser the person
subscribed, with the notice's title as its words under the kind `notice`, which
is its own tag, so it neither replaces nor waits on a coach message; with no
browser, an email only when the command was given `--email`; otherwise nothing
leaves the app. Someone who joins the audience later gets their row on their
next open, in the app only.
The body may carry `**bold**`, `_italics_`, `[words](https://…)` or `[words](/path)` links that open in a new tab, and line breaks; the app shows anything else as written, never as HTML.

## Events

`POST /events`, `PATCH /events/<id>`, `DELETE /events/<id>` (204). The body
carries any field `btcopilot.schema.Event` has except `id`; an unknown name is a
400, as is a person id that is not in the diagram. Dates are ISO in and out.

Every write takes the diagram's optimistic lock, so an edit racing a background
extraction re-reads instead of clobbering; sustained contention is a 409.

Saving normalizes rather than refusing: a non-shift kind clears the four shift
values, targets need a relationship kind, triangles survive only for inside and
outside. So a stored event can never break the editor's rules, and switching a
shift to a death clears its shift values.
