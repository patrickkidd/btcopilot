# Merge review — branch FD-362 onto the live server

What this is: a read-only comparison of branch `FD-362` against `master` in the btcopilot
repo, written for deploying onto the existing production server that already serves the Pro
desktop app, the training app, and the old Personal mobile app.

Evidence base: `git diff master...HEAD`, the alembic revision the branch adds, the route
tables of both branches, and `grep` over the read-only Pro/Personal client at
`~/theapp/familydiagram`. The Pro test suite and the diagram-encoding tests were run from
this worktree and pass (126 passed, 11 skipped). Nothing was changed or committed.

What could not be checked: the production database has no local copy running (Docker is
not up), so no real diagram row was put through the new encoder. The production container
image was not built or run, so the two deploy blockers below are stated from the build
files, not from a failed boot.

---

## 1. Database

The branch adds exactly one alembic revision, `e1f2a3b4c5d6`, at
`alembic/versions/e1f2a3b4c5d6_personal_chat_app.py`. Its parent is `c8f1a2d3e4b5`, which
is the single head on master. One head before, one head after. No existing revision is
edited.

### New tables

| Table | Who reads/writes it on master | On the branch |
|---|---|---|
| `changes` | nobody, new | written on every Pro app save and every coach turn |
| `interactions` | nobody, new | written by the chat web app only |
| `web_sessions` | nobody, new | passwordless sign-in sessions |
| `passkeys` | nobody, new | passkey sign-in |
| `invitations` | nobody, new | invite tokens |
| `login_codes` | nobody, new | email sign-in codes |

All six are pure creates. No lock on anything the running apps touch.

### Changed columns on existing tables

| Table.column | Type | Null | Default | Additive? |
|---|---|---|---|---|
| `users.preferences` | JSON | NOT NULL | `{}` | yes |
| `users.birthdate` | Date | NULL | — | yes |
| `users.current_diagram_id` | Integer, foreign key to `diagrams.id` | NULL | — | yes |
| `discussions.title` | Text | NULL | — | yes |
| `discussions.title_set_by_user` | Boolean | NOT NULL | false | yes |
| `statements.views` | JSON | NULL | — | yes |
| `statements.kind` | enum `statementkind` | NOT NULL | `turn` | yes |
| `statements.cluster_id` | String(64) | NULL | — | yes |

`users` is read and written by all three apps. `discussions` and `statements` are read and
written by the training app on nearly every page, and by the Personal backend.

Migration risk on live Postgres: low. Every added column is either nullable or has a
constant server default, so Postgres 11 and later adds them without rewriting the table.
There is no backfill and no `NOT NULL` without a default. The four new enum types are
created before the columns that use them. The foreign key on `users.current_diagram_id`
takes a brief lock on `diagrams` to validate, on a table with no rows to validate against
for that column. Expect the whole revision to finish in well under a second.

The one thing to know: `downgrade()` drops all six new tables. Rolling the migration back
after the chat app has been used destroys every sign-in session, passkey, invitation and
change record. That is normal, but it means the rollback story for this deploy is "restore
from backup", not "alembic downgrade".

---

## 2. Diagram storage

**The stored format changes from pickle to JSON, and a Pro save is what rewrites it.**

The encoder is `btcopilot/diagramjson.py`. It turns the Pro app's pickled scene dict into
JSON by wrapping each type JSON cannot express in a tagged object: `QDateTime`, `QDate`,
`QTime`, `QPoint`, `QPointF`, `QSize`, `QSizeF`, `QColor`, tuples, dictionaries with
non-string keys, and enums defined in `schema.py`. Anything else raises `TypeError`
(`btcopilot/diagramjson.py:83`).

### What runs on a Pro save

`PUT /v1/diagrams/<id>` at `btcopilot/pro/routes.py:230`:

1. `old = diagramjson.loads(diagram.data)` reads the current row. `loads` looks at the
   first byte: `{` means JSON, anything else is unpickled. So old pickled rows still read
   (`btcopilot/diagramjson.py:110`).
2. `diagram.update_with_version_check(expected_version, new_data=data["data"])` calls
   `diagramjson.store(new_data)` at `btcopilot/pro/models/diagram.py:221`. `store` is
   `dumps(loads(blob))`: it unpickles what the client sent and writes JSON.
3. `record.diff(old, ...)` compares the two and, if anything changed, inserts a `changes`
   row carrying the before and after of every changed field
   (`btcopilot/pro/routes.py:257-266`).
4. The response is `diagram.pickled`, which is `pickle.dumps(loads(...))` — the row decoded
   from JSON and re-pickled (`btcopilot/pro/models/diagram.py:86`).

So yes: **the first Pro save of any existing diagram rewrites that row from pickle to JSON,
with no migration step and no backup.** There is no opt-out and no dual write.

### What the Pro app receives on read

`GET /v1/diagrams/<id>` returns `diagram.as_dict()`, and `as_dict` now injects
`data = self.pickled` (`btcopilot/pro/models/diagram.py:267`). The client gets a freshly
re-pickled blob rather than the bytes it originally sent. Both ends require Python 3.11 or
later (`familydiagram/pyproject.toml:13`, `btcopilot/pyproject.toml:9`), so pickle protocol
5 loads on both sides. The list endpoint excludes `data` and defers the column
(`btcopilot/pro/routes.py:183-199`), so listing diagrams does not pay the re-encode cost.

### What happens to a row that fails to convert

Two different answers, and only one of them is safe.

**In the one-off converter** `btcopilot/diagrams/migrate_json.py`: a row that raises
`TypeError`, `ValueError`, `KeyError` or `AttributeError` is counted as failed, rolled back,
logged, and left as pickle (lines 31-37). Since `loads` still reads pickle, a failed row
keeps working. The script is idempotent and prints counts only. That behaviour is safe. It
has no dry-run mode, so the only way to find out how many rows fail is to run it and read
the failed count, having taken a database backup first.

**In the Pro save path**: there is no such guard. `diagramjson.store()` at
`btcopilot/pro/models/diagram.py:221` is not wrapped. A scene carrying a value the encoder
does not know raises inside the request, the response is a 500, and `session.commit()` at
`btcopilot/pro/routes.py:274` never runs. The clinician's save is lost. Retrying saves the
same scene and fails the same way, so that diagram becomes permanently unsaveable until
code changes.

How likely is that? The type survey of the Pro client's save path
(`familydiagram/pkdiagram/scene/property.py`, `scene/item.py`, `scene/scene.py`) found
these types reaching the blob: `str`, `int`, `float`, `bool`, `None`, `list`, `dict`,
`QDateTime`, `QPointF`, `QColor`, `QSize`, and enums stored as their string values. The
encoder covers all of them, and the round-trip test over three real `.fd` fixtures passes
(`btcopilot/tests/test_diagramjson.py`). Two holes remain that static analysis cannot
close:

- `Item.write` at `familydiagram/pkdiagram/scene/item.py:132` does
  `chunk.update(self._readChunk)`, which passes through untouched any key from a file
  written by a different app version. A value type from an older or newer build survives
  into the blob unexamined.
- `Layer.itemProperties` (`familydiagram/pkdiagram/scene/layer.py:26`) is a free-form
  dictionary whose values are whatever a layered property stored.

So the failure is unlikely for a scene built by the current app and not provable to be
impossible for a scene built by some other version. The fix is cheap and removes the
question entirely: catch the encode failure in the save path and fall back to storing the
pickle bytes as they arrived.

### A second, separate risk on the same path

`record.diff` and the `Change` insert run inside the Pro request, after the diagram UPDATE
has been flushed but before the commit. If anything in that Personal-app code raises, the
Pro save is rolled back and lost. A Pro clinician's ability to save now depends on
Personal-app code that has nothing to do with Pro.

And every Pro save now writes a `changes` row holding the before and after values of every
field that changed — names, dates, descriptions. That is clinical content duplicated into a
new table, growing without bound, with no retention rule. This is a decision to make, not a
bug.

---

## 3. Endpoints

### Pro app — `/v1/*`

Route table compared decorator by decorator against master: **identical**. No path, method,
or auth change. Only the body of the diagrams handler and the free-diagram handler changed,
as described above.

### Training app — `/training/*`

Route table compared against master: **identical**. The only change to
`btcopilot/training/routes/__init__.py` is the removal of an unused import.

### Personal — `/personal/*`

Every route the old Personal mobile app calls is gone. The files were moved to
`btcopilot/personal/archive/` and that blueprint is no longer registered
(`btcopilot/personal/routes/__init__.py:97`, which registers only the new one). The archive
README states this is deliberate, citing the 2026-09-08 ruling that the Qt Personal app is
superseded.

| Route on master | Called by | On the branch |
|---|---|---|
| `GET /personal/assemblyai-key` | `personalappcontroller.py:740` | gone, 404 |
| `POST`, `GET /personal/discussions/` | `personalappcontroller.py:1113` | gone, 404 |
| `GET /personal/discussions/<id>` | via the above | gone, 404 |
| `POST /personal/discussions/<id>/statements` | `personalappcontroller.py:1175` | gone, 404 |
| `POST /personal/discussions/<id>/extract` | `personalappcontroller.py:1986` | gone, 404 |
| `POST /personal/discussions/<id>/commit-pdp` | `personalappcontroller.py:1277` | gone, 404 |
| `POST /personal/discussions/<id>/deep-reextract` | `personalappcontroller.py:2032` | gone, 404 |
| `GET /personal/discussions/<id>/deep-reextract-status/<task>` | `personalappcontroller.py:2096` | gone, 404 |
| `POST /personal/discussions/<id>/deep-reextract/<task>/cancel` | `personalappcontroller.py:2130` | gone, 404 |
| `POST`, `GET /personal/diagrams/` | `personalappcontroller.py:910`, `:1052` | replaced by `GET /personal/diagrams`, different shape and auth |
| `GET`, `PUT /personal/diagrams/<id>` | `personalappcontroller.py:979`, `server_types.py:223` | gone, 404 |
| `GET /personal/diagrams/<id>/discussions` | not found in the client | gone |
| `POST /personal/diagrams/<id>/import-text` | `personalappcontroller.py:1928` | gone, 404 |
| `POST /personal/diagrams/<id>/clusters` | `clustermodel.py:244` | gone, 404 |

The client reaches these with `from_root=True`, so the paths are `/personal/...` with no
`/v1` prefix (`familydiagram/pkdiagram/util.py:144`). They are real routes on master and
absent on the branch.

Even if a path had survived, the authentication changed underneath it: `/personal/*` used
to authenticate by signed header and now authenticates by cookie session
(`btcopilot/personal/routes/__init__.py:28`), and every write method is now CSRF-protected,
which the Qt client sends no token for.

**A copy of the Personal mobile app still installed on a phone stops working at the next
launch.** Whether that matters is a question about who is running it, not a question about
the code.

New routes added, all under `/personal/`, all cookie-authenticated and CSRF-protected on
writes: the chat page and its assets (`/`, `/sw.js`, `/apple-touch-icon.png`,
`/manifest.webmanifest`, `/timeline`), sessions and chat (`/chat`, `/sessions`,
`/sessions/<id>` with GET/PATCH/DELETE, `/sessions/<id>/statements`), record editing
(`/people`, `/people/<id>`, `/events`, `/events/<id>`), `/play`, `/interactions`,
`/preferences`, `/account`, `/diagrams`, `/diagrams/<id>/select`.

Sign-in routes added under the same prefix: `/personal/login`, `/login/verify`, `/logout`,
`/me`, `/invite/<token>`, `/signins`, `/signins/<id>/revoke`, and five `/passkeys` routes.

Two new Flask CLI commands, `flask personal fixtures` and `flask personal migrate`, are
commands and not HTTP routes. The fixtures command creates throwaway users on whatever
database it is pointed at, so it must never be run against production.

---

## 4. Shared code the Pro app imports

The desktop app imports from `btcopilot` (the package constants and `sign` /
`httpAuthHeader`), from `btcopilot.schema`, and lazily from `btcopilot.arrange.layout`.
Only `schema` changed.

Every name the desktop imports still exists with the same shape: `DiagramData`, `PDP`,
`Person`, `Event`, `PairBond`, `EventKind`, `RelationshipKind`, `VariableShift`,
`DateCertainty`, `Cluster`, `ClusterPattern`, `asdict`, `from_dict`, `hash_sarf_dicts`,
`is_parents_edit`, `validatedDateText`, `pyDateTimeString`. `ClusterPattern` is kept
explicitly for that reason, with a comment saying so at `btcopilot/schema.py:396`.

Two shape changes, neither of which reaches the desktop app:

- `Cluster` loses the fields `pattern` and `dominantVariable` and gains `name`, `source`,
  `reason`. Two QML files in the old Personal app read `pattern` and `dominantVariable`
  (`familydiagram/pkdiagram/resources/qml/Personal/VignetteCard.qml:111,157`), both behind
  an `undefined` check, so they render as absent rather than error. The Pro app does not
  read either field. Old stored clusters that still carry the two dropped fields are safe:
  `from_dict` iterates the dataclass fields and ignores unknown keys
  (`btcopilot/schema.py:108`).
- `DiagramData.ensure_chat_defaults()` returns a 2-tuple instead of a 3-tuple. Every caller
  is server-side; the three training-app callers ignore the return value entirely
  (`training/routes/admin.py:448`, `training/routes/discussions.py:73`,
  `training/routes/diagrams.py:48`).

**`btcopilot/pro/routes.py` now imports Personal modules at module scope**: `record` and the
`Author` / `Change` models (lines 57-58). What that puts inside a Pro request is described
in section 2: the diff and the change-log insert, either of which failing loses the save.

**And a new hard import of Qt's GUI module.** `btcopilot/diagramjson.py:29` does
`from PyQt5.QtGui import QColor` at module scope. That module is imported at module scope by
`btcopilot/pro/models/diagram.py:11` and `btcopilot/pro/routes.py:40`, so it is imported
when the app factory runs. On master only `PyQt5.QtCore` was imported at module scope
(`schema.py:16`), and the pickle registration was a deferred import inside methods. The
production image installs `libglib2.0-0` and nothing else, with the comment "PyQt5.QtCore
runtime dependency" (`Dockerfile:8`). QtGui typically needs `libGL.so.1` on Linux, which
that image does not install. If it is missing, `create_app()` raises at import and the whole
server fails to start — Pro, training and chat together. This is one command to settle and
must be settled before merge.

---

## 5. Auth

**Pro, signed-header path: unchanged in effect.** `_authenticate_pro_personal_apps` was
renamed to `_authenticate_pro_app` and now matches only paths starting with `/v1/`
(`btcopilot/auth/__init__.py:229`). Since the Pro app calls only `/v1/*`, nothing about a
Pro request's authentication changed. The signature check itself is untouched.

**Training, session path: one new condition.** `_authenticate_training_app` now also calls
`_web_session_ok()` (`btcopilot/auth/__init__.py:303`). That function returns `True`
immediately when the cookie carries no chat session token, which is the case for every
training-app login. A training user is refused only if their cookie carries a chat token
whose `web_sessions` row is missing, revoked or expired. So training logins behave as before.

**Three global changes that reach beyond the chat app**, and these are the ones worth
knowing:

1. `app.session_interface = LongSessions()` replaces Flask's session handling for the whole
   app (`btcopilot/auth/__init__.py:32`). It extends the cookie lifetime only for sessions
   carrying a chat token and defers to the old behaviour otherwise, so the training app's
   eight-hour policy is preserved. Reviewed and correct, but it is a server-wide swap.
2. `WTF_CSRF_TIME_LIMIT = None` is set in the app config (`btcopilot/app.py:36`). CSRF
   tokens now never expire, for the training app as well as the chat app. The stated reason
   is that a chat page token must outlive an hour. The cost is that a leaked training-app
   token stays valid indefinitely.
3. The 403 handler no longer special-cases Personal paths (`btcopilot/app.py:105`). A 403
   on `/personal/*` now redirects to a login page instead of returning 403. That is right
   for a browser app and wrong for an API client, which is consistent with the Personal API
   being retired.

**One thing to rule on rather than fix.** Signing in with an emailed code creates the
account if the address has no user, with the subscriber role
(`btcopilot/auth/signin.py:20-31`). That row lands in the same `users` table the Pro app and
the training app authenticate against. An invited chat reader therefore holds a real account
on the shared server. Invitations gate who can get one, so this is a deliberate design, but
it is worth stating plainly.

---

## 6. Verdict

| What breaks | For whom | Severity | Smallest fix, or the proof it is safe |
|---|---|---|---|
| Qt's GUI module is imported when the app starts; the image installs no GL library | everyone — the server does not boot | blocker if real | Run `from PyQt5.QtGui import QColor` inside the built image. If it fails, add `libgl1` to `Dockerfile:8` |
| The chat page bundle is never built for the release image | chat app only; `/personal/` raises at request time | blocker for the chat app | Add the Node build to `release.yml` before `python -m build`, and add `"btcopilot.personal" = ["static/**/*"]` and `"btcopilot.auth" = ["templates/**/*"]` to the package data at `pyproject.toml:93` |
| A Pro save whose scene holds a type the encoder does not know returns 500 and loses the save, permanently for that diagram | Pro clinicians | high | Wrap `diagramjson.store()` in the save path and fall back to storing the pickle bytes unchanged |
| Personal-app code runs inside the Pro save transaction; if it raises, the save is rolled back | Pro clinicians | high | Move the change-log insert after the commit, or wrap it so its failure cannot undo the save |
| Existing Pro rows are rewritten from pickle to JSON on first save, with no migration and no backup | Pro clinicians | high | Take a database backup, then run `python -m btcopilot.diagrams.migrate_json` before opening the app to users, and read its failed count |
| Every Pro save writes clinical before/after values into a new `changes` table, unbounded | storage and confidentiality | medium | A decision, not a fix: keep it, limit it to the chat app, or set a retention rule |
| The old Personal mobile app's endpoints are all gone | anyone still running that app | medium, deliberate | Confirm nobody is running it. The code is kept at `btcopilot/personal/archive/` if it must come back |
| CSRF tokens never expire, server-wide | training app | low | Set the limit on the chat blueprint alone rather than in the app config |
| Chat sign-in creates a subscriber account in the shared users table | shared user base | low, deliberate | Confirm the intent |
| Every Pro diagram read decodes JSON and re-pickles it | Pro read latency, one worker with two threads | low | Measure once on the largest diagram after deploy |
| Alembic revision | all tables | safe | One head before and after, all columns nullable or defaulted, no backfill, no rewrite |
| Pro and training route tables | Pro and training clients | safe | Compared decorator by decorator: identical to master |
| Schema symbols the desktop imports | Pro desktop | safe | All present with the same shape; unknown keys in stored data are ignored on read |
| Pickle protocol across the wire | Pro desktop | safe | Both ends require Python 3.11 or later |

### Must fix before merge

1. Prove Qt's GUI module imports inside the production image, or add the missing system
   library.
2. Build the chat page bundle in the release workflow and include it, and the sign-in
   template, in the wheel.
3. Make a Pro save survive an encoder failure instead of losing the save.
4. Keep the change-log insert from being able to roll back a Pro save.
5. Back up the database and run the one-off pickle-to-JSON conversion before users reach it,
   and read the failed count.

### Should fix

6. Decide what the `changes` table keeps from Pro saves, and for how long.
7. Narrow the never-expiring CSRF token to the chat app.
8. Confirm the old Personal mobile app has no users left.

### Safe as is

The alembic revision. The Pro and training route tables. The schema symbols the desktop
imports. The pickle protocol on the wire. The one-off conversion script's own failure
handling. The training app's session authentication.
