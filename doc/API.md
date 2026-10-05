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
| `POST /chat` | `{statement, time_zone?}` into the family's current sitting: the session last spoken in, or a new one once its last statement is 12 hours old. `time_zone` is the browser's IANA zone name (`America/Anchorage`); the coach's "today", the follow-up date check and the day a question was asked on are worked out in it, so an evening in Alaska is not already tomorrow. Left out, or a name the server does not know, the day is the server's own (UTC on the box); stored times stay UTC (R-0758) |
| `GET /statements` | the family's one thread across its sessions, 50 statements at a time, oldest first; `?before=<statement id>` reads the page just older. Each carries `session_id`; a session's first statement carries `sitting: {id, started, previous_started}`, the last being when the sitting before it started, or null for the first. Each also carries `feedback`, the number of shadow replies its turn has on a coach reply, 0 on the user's words and on a reply made with Conversation Feedback off, and `stopped`, true on the user's words whose turn was ended with Stop, with `conflict`, why that turn's edits stayed in the record, or null when they were taken back (R-0636) |
| `POST /sessions/<id>/statements` | `{statement, time_zone?}` into a named session |
| `GET /sessions` | the user's sessions on the family the app is on (`?diagram_id=` another readable one, or the one an admin is viewing, whose sessions are its owner's), most recently active first; `?all=true`, admins only (403 otherwise), is every session on every family, whoever had it, each with `family`, its family's name (every row carries `diagram_id`), which is what the meeting page puts one on the agenda from; `?words=` keeps those where something said carries every word, the coach's chat search, each with `match`, the newest line that does, chips shown as their words |
| `POST /sessions` | new empty session, 201 |
| `GET /sessions/<id>` | one session plus `statements: [{id, role, text}]`, role is `user` or `coach` |
| `PATCH /sessions/<id>` | `{title}` only |
| `POST /turns/<id>/stop` | 202 `{turn_id}`: asks the running turn to end; the worker checks before each model call and each tool call, writes no reply (the words typed out so far are dropped), takes the turn's edits back as one change, and runs no shadow replies. Its last event is done with `stopped: true`, `statement: null`, `statement_id` (the person's own message), `version` (the record's version after the edits were taken back), `views: []`, `events: []`, `turn_id`, `discussion_id`, `kind`, `session`, `release`; and `conflict` (a sentence) only when an edit had been changed since and the turn's edits were left in place. A turn already past its last call finishes as usual. A stopped turn does not count for the Conversation Feedback timer. 409 when the turn is not running (R-0636) |

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

Each entry of `asked_questions` also carries `case_report_card`: `main_guess`,
`own_part`, `choice`, `work_on`, `coach_guess` or null, the case report card the
coach put it on (R-0709, R-0732). One guess is on each card, the newest;
`work_on` and `coach_guess` hold up to three, in record order. A question is only ever on `own_part` or `choice`. And
`answer`: null, or the person's own message that answered the question,
`{kind: "statement", id, label, discussion_id, at, text}`, with `text` their
words (null once the session is gone); on the `own_part` question it is the
person's view of their own part (R-0708). The case report reads this same
`/timeline`; there is no case report endpoint.

## Case report

`GET /case-report-passages?diagram_id=` — the passages behind each card's book
button, `{key: [{text, by}]}`, read from `case-report/passages.json` in the
private corpus the way the theory pages are, and given only to a signed-in user
who may open the diagram; any other is a 404 (R-0692, R-0715). The keys are the
mockup's: `why`, `1` to `6`, `7a`, `9a`, `10`, `3s` and `order`.

## Preferences

`GET /preferences`, `PATCH /preferences` — one object: `speak`, `proactive`,
`mode`, `theme`, `bug_reports` (`ask` or `always`), `first_name`, `last_name`,
`birthdate`. PATCH takes any subset; an unknown key or a bad value is a 400.
`shadow_models` (the Conversation Feedback switch, a list of names from
`shadow_candidates`; empty is off; turning it on is auditors only, 403
otherwise; a name not in `shadow_candidates` is a 400) turns itself off 5 minutes after the latest of the coach's last
reply being written, the person's last vote (a pick saved with a choice) and
the switch going on [Oracle: R-0637]. `shadow_since` (UTC ISO time
it went on, null when off) is set by the server and is a 400 in a PATCH;
`shadow_expires_at` (UTC ISO time it turns off: 5 minutes after the latest of
those three, null when off) is read-only.
GET, PATCH and every coach turn turn an expired switch off and store that; a
turn sent more than 5 minutes after all three runs no shadow replies.
`shadow_candidates` is the admin setting `shadow_candidates` (set with
`flask admin coach-model shadows set`), `["sonnet"]` when unset; GET, PATCH
and every coach turn first drop from `shadow_models` any name no longer in it,
and turn the switch off when none is left [Oracle: R-0637].

## Reports

`POST /reports` — a bug or feedback the coach offered from the conversation and
the person answered on the page, one row in the reports table. It takes no CSRF
token, so only a post from this site is taken (403 otherwise); one sender (the
person, or a signed-out page's address) gets 20 an hour, then 429. `kind` is
`bug` or `feedback`, `status` is `sent` or `declined`, `release` is the app's
version; `address` (the screen), `turn_id` and `statement_id` (the coach's
reply that offered it) are optional. A report sent carries the offered `words`;
one declined, none. During the beta a declined bug is a 400. Any other field is a
400; answers `{"id"}` with 201. An
error in the page or the server is never a report: those go to Grafana (Faro
on the page, Alloy for the server's logs), and every answer's `X-Request-Id`
names the server's log lines for that request.

## Account

`GET /account` — `email`, `sign_in_method`, `plan` (placeholder text until
Patrick sets the numbers), `diagrams` (`id`, `name`, `last_activity`, `free`),
`licenses` (`id`, `policy`, `status`). Sign out is the existing auth route.

| | |
|---|---|
| `GET /diagrams` | the diagrams the caller may write to, most recently active first; `?user_id=` lists another person's, admins only (403 otherwise), with `current` still meaning the caller's own |
| `POST /diagrams/<id>/select` | puts the app on that diagram and answers it with `access` (`own`, `shared`, `admin-view`) and `owner` (the owner's full name, or email) and `owner_name` (the owner's first name, null when the account has none, which the case report's header shows); an admin may open anyone's diagram as `admin-view`, which writes no row in `access_rights`; anyone else gets 404 for a diagram they cannot write to |
| `admin-view` | the admin reads the diagram, its timeline and its owner's sessions (`/statements`, `/sessions`, `/sessions/<id>`); every write on it (a turn, a session, a note, a record edit, a question, a play, a rename or delete) is a 403 with the words "this diagram is open read-only", and nothing is written; selecting one of the admin's own diagrams ends it |
| `GET /users?q=` | admins only (403 otherwise): up to 20 people whose email or full name contains the words, any case, each `id`, `username`, `name`; fewer than two letters is a 400 |

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
A noted event or a shift needs a `title` of 2 to 4 words (R-0681); a write
leaving one without it is a 400.

Every write takes the diagram's optimistic lock, so an edit racing a background
extraction re-reads instead of clobbering; sustained contention is a 409.

Saving normalizes rather than refusing: a non-shift kind clears the four shift
values, targets need a relationship kind, triangles survive only for inside and
outside. So a stored event can never break the editor's rules, and switching a
shift to a death clears its shift values.

## Review picks (`/review`, the model_picks table)

| | |
|---|---|
| `GET /review/pairs` | admins only: every pick not yet made, each `{id, source, context, left, right}`; a pair seen for the first time gets its pick row and its random side order here; replay pairs come from the eval ledger file, and a line is used only when the replay passes table of this database holds that replay (same scratch record, turns and token counts) |
| `GET /review/picks` | admins only: each model's `{model, won, lost, tied}` over the picks made |
| `GET /review/picks?turn=<turn id>` | the owner of that turn's session, admin or auditor (403 otherwise): `{replies: [{key, text}], real_key, picks: [{id, left_key, right_key, choice, left_acceptable, right_acceptable, note, shown}], pending, expected}`, a pick's last five null until it is voted, the real reply and each finished shadow reply keyed `a`, `b`, `c` in a random order, and one pick per shadow against the real reply, made here if missing as `GET /review/pairs` makes it; a shadow with an error is left out and no model is named; `expected` counts the shadow replies started for the turn and `pending` those with neither text nor error yet |
| `PUT /review/picks/<id>` | `{choice, note, left_acceptable, right_acceptable, source, shown}`, `shown` (`left` or `right`, optional) the side shown first on screen, kept as `shown_first` in that side's ref [Oracle: R-0640]; an admin, or an auditor on their own session's pick; answers the pick with both model names |

`choice` is `left`, `right` or `tie`; the client sends it already resolved. A
reply marked unacceptable never wins; with only one acceptable, that one wins;
with neither, it is a tie; any other `choice` is a 400. The two flags are
optional, true or false. `source` is optional and may only be `chat`, which a
pick voted in the chat sets. `note` is optional, at most 200 characters.
