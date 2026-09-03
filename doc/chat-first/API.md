# Companion API (phase 2)

Everything is under `/companion`, behind the training-app login, on the user's
own free diagram. Writes need the CSRF token from the page's
`<meta name="csrf-token">` in `X-CSRFToken`. A rejected value returns 400 with a
plain-text reason; another user's resource returns 404.

## Chat and sessions (a session is a `Discussion`)

| | |
|---|---|
| `POST /chat` | `{statement}` into the session the user last spoke in, creating one if there is none |
| `POST /sessions/<id>/statements` | `{statement}` into a named session |
| `GET /sessions` | every session, most recently active first |
| `POST /sessions` | new empty session, 201 |
| `GET /sessions/<id>` | one session plus `statements: [{id, role, text}]`, role is `user` or `coach` |
| `PATCH /sessions/<id>` | `{title}` only |

A session reads `{id, title, summary, last_activity, message_count}`. The title
and summary are written by the coach after the first exchange and are editable
after that. There is no "switch" call: the list is ordered by activity, so
posting into a session makes it the one the page returns to.

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
`mode`, `theme`, `first_name`, `last_name`, `birthdate`. PATCH takes any subset;
an unknown key or a bad value is a 400.

## Account

`GET /account` — `email`, `sign_in_method`, `plan` (placeholder text until
Patrick sets the numbers), `diagrams` (`id`, `name`, `last_activity`, `free`),
`licenses` (`id`, `policy`, `status`). Sign out is the existing auth route.

## Events

`POST /events`, `PATCH /events/<id>`, `DELETE /events/<id>` (204). The body
carries any field `btcopilot.schema.Event` has except `id`; an unknown name is a
400, as is a person id that is not in the diagram. Dates are ISO in and out.

Saving normalizes rather than refusing: a non-shift kind clears the four shift
values, targets need a relationship kind, triangles survive only for inside and
outside. So a stored event can never break the editor's rules, and switching a
shift to a death clears its shift values.
