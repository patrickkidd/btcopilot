# Merge review — branch FD-362 onto the live server

What this is: a read-only comparison of branch `FD-362` against `master` in the btcopilot
repo, written for deploying onto the existing production server that already serves the Pro
desktop app and the training app. Compatibility with previously released Personal app
versions is out of scope by the owner's direction and is not assessed.

Evidence base: `git diff master...HEAD`, the alembic revision the branch adds, the route
tables of both branches, and `grep` over the read-only desktop client at
`~/theapp/familydiagram`. Tests were run from this worktree and pass: the Pro suite plus the
diagram-encoding tests (126 passed, 11 skipped) and the Personal and schema suites (506
passed, 23 skipped). Nothing was changed or committed.

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

The whole `/personal` surface is replaced. The old route files moved to
`btcopilot/personal/archive/` and that blueprint is no longer registered
(`btcopilot/personal/routes/__init__.py:97` registers only the new one). Compatibility with
released Personal app versions is out of scope by the owner's direction, so the removals are
not treated as breakage here.

Authentication under this prefix changes: it used to be by signed header and is now by
cookie session (`btcopilot/personal/routes/__init__.py:28`), with CSRF protection on every
write method.

New routes, all under `/personal/`: the chat page and its assets (`/`, `/sw.js`,
`/apple-touch-icon.png`, `/manifest.webmanifest`, `/timeline`), sessions and chat (`/chat`,
`/sessions`, `/sessions/<id>` with GET/PATCH/DELETE, `/sessions/<id>/statements`), record
editing (`/people`, `/people/<id>`, `/events`, `/events/<id>`), `/play`, `/interactions`,
`/preferences`, `/account`, `/diagrams`, `/diagrams/<id>/select`.

Sign-in routes added under the same prefix: `/personal/login`, `/login/verify`, `/logout`,
`/me`, `/invite/<token>`, `/signins`, `/signins/<id>/revoke`, and five `/passkeys` routes.

Two new Flask CLI commands, `flask personal fixtures` and `flask personal migrate`, are
commands and not HTTP routes. The fixtures command creates throwaway users on whatever
database it is pointed at, so it must never be run against production.

---

## 4. Existing rows in the new app

The question here is different from the migration question: not "does the database accept
the new schema" but "does a row written on master behave correctly when the chat app opens
it". The short answer is that nothing crashes, one thing is wrong on screen, one thing is
silently unreachable, and one thing lets a reader write where they should not.

### Which old rows the new app can even reach

The switcher lists every diagram the user owns plus every diagram granted to them
(`btcopilot/personal/routes/diagrams.py:19-29`). For a Pro clinician signing into the chat
app, that is every client diagram they have. Selecting one puts the app on it
(`/diagrams/<id>/select`).

Sessions are filtered to the signed-in user and the selected diagram
(`btcopilot/personal/routes/__init__.py:63-70`). So an old Personal-app discussion appears
as soon as the app is on its diagram, and a training-app discussion appears only if the same
user owns the diagram and selects it.

### Diagrams written by the Pro app or on master

| What old rows carry | What the new code expects | Result |
|---|---|---|
| pickle blob | JSON or pickle | fine; `diagramjson.loads` sniffs the first byte |
| no `clusters` key | `data.clusters` | empty, and the picture draws no boxes — see below |
| no `clusterCacheKey` | a cache key | absent, so the next sync recomputes |
| a person with id 2 named "Assistant" | id 2 reserved, never a person | the Assistant shows up as a family member — see below |
| `pdp` with uncommitted items | nothing reads it | unreachable — see below |
| `people`, `events`, `pair_bonds` | same field names | fine |

**Clusters.** Master never stored clusters in the diagram row: `set_diagram_data` on master
writes only `pdp`, `lastItemId`, `people`, `events` and `pair_bonds`. Clusters were computed
on demand and returned by an endpoint. The new picture draws only stored clusters
(`btcopilot/personal/timeline.py:250`), so **every diagram carried over opens as a flat line
of loose dots with no boxes.** The lazy fix exists but does not fire on its own: cluster
detection runs from `CoachTurn._regroup` at `btcopilot/personal/coachturn.py:258`, which
returns early unless that same turn wrote an event. A reader can therefore talk for several
turns about an old family and never see the picture group anything. Either call
`clusters.sync` once per diagram as a one-shot step, or drop the early return so the first
turn on a diagram with no stored cache key syncs.

**The Assistant person.** Master's `ensure_chat_defaults` always created a person with id 2
named "Assistant" (`schema.py` on master). The branch reserves id 2 and never creates one,
but it never removes the existing one either. Nothing filters it: the people list handed to
the page is every person on the diagram (`btcopilot/personal/timeline.py:590-605`). So any
diagram that ever had a Personal-app or training-app chat on it **shows "Assistant" as a
member of the family.** It has no events, so it draws no lane, but it is in the people list
and in the person picker. One-shot fix: delete the person with id 2 from every diagram whose
people list has one, where no event links to it.

**Pending extractions.** Uncommitted PDP items live on old rows under `data["pdp"]` with
negative ids. The new app reads only the committed collections, and the endpoint that used
to commit them is archived. The remaining callers of `commit_pdp_items` are the background
re-extraction task and a training connectivity check, neither of which a chat reader can
trigger. **Anything extracted but never committed on an old diagram is invisible and
uncommittable from the new app.** Decide whether to commit it in a one-shot step or accept
losing it.

### Discussions and statements

| Origin | `chat_user_speaker_id` / `chat_ai_speaker_id` | `title` | Behaviour in the new app |
|---|---|---|---|
| old Personal app | both set | null | loads correctly as a session |
| training app import | both null, many Subject speakers | null | **every existing message renders as the user talking** |

`title` being null is handled: the coach names the session on the first turn, because
`CoachTurn` calls `update_title()` whenever the title is null
(`btcopilot/personal/coachturn.py:247`). `title_set_by_user` gets the `false` server default.
`kind` gets the `turn` server default. `views` and `cluster_id` are null and both readers
tolerate null. None of those need a migration step.

The speaker problem does. Both the page and the model prompt decide who said what by
comparing `statement.speaker_id` to `discussion.chat_ai_speaker_id`
(`btcopilot/personal/routes/sessions.py:41`, `btcopilot/personal/coachturn.py:302`). A
training discussion has that column null and its statements point at real speakers, so every
line reads as the user. Worse, `sync_chat_speakers`
(`btcopilot/personal/discussions.py:56`) takes the first Subject-type speaker it finds, in no
defined order, and overwrites its `person_id` and its `name` — **it renames a speaker inside
a clinical transcript.** New coach statements on such a discussion are written with a null
speaker (`btcopilot/personal/coachturn.py:237`), which then compares equal to the null
`chat_ai_speaker_id` and happens to render as the coach.

The smallest fix is to refuse rather than repair: treat a discussion with no
`chat_ai_speaker_id` as not a chat session, and leave it out of the session list. If those
transcripts are meant to be openable as sessions, they need a real one-shot step that adds a
Coach speaker, stamps the two chat speaker columns, and maps the existing speakers, which is
a bigger piece of work than this deploy.

### Two smaller things on the same path

Editing an event through the new editor writes with
`update_with_version_check(diagram_data=...)`
(`btcopilot/personal/routes/events.py:114`), and that path does not write `clusters` or
`clusterCacheKey` (`btcopilot/pro/models/diagram.py:225-231`). Existing stored clusters are
preserved, because the other keys of the blob are left alone, but they are not updated, so
the boxes on the picture go stale against the edited events until a coach turn re-syncs them.

And the record-writing routes check nothing about write access. `diagram()` returns whichever
diagram the user selected, and `readable()` includes diagrams granted read-only
(`btcopilot/personal/routes/diagrams.py:16`). `record.apply` and the event and person routes
never check the grant (`btcopilot/personal/routes/people.py:46-56`,
`btcopilot/personal/routes/events.py:102-119`). **An existing read-only access grant becomes
write access through the chat app.** That is an authorization hole reached entirely through
rows that already exist in production.

---

## 5. Shared code the Pro app imports

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
  `reason`. The Pro app reads none of these. Old stored clusters that still carry the two
  dropped fields are safe: `from_dict` iterates the dataclass fields and ignores unknown
  keys (`btcopilot/schema.py:108`).
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

## 6. Auth

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

## 7. Verdict

| What breaks | For whom | Severity | Smallest fix, or the proof it is safe |
|---|---|---|---|
| Qt's GUI module is imported when the app starts; the image installs no GL library | everyone — the server does not boot | blocker if real | Run `from PyQt5.QtGui import QColor` inside the built image. If it fails, add `libgl1` to `Dockerfile:8` |
| The chat page bundle is never built for the release image | chat app only; `/personal/` raises at request time | blocker for the chat app | Add the Node build to `release.yml` before `python -m build`, and add `"btcopilot.personal" = ["static/**/*"]` and `"btcopilot.auth" = ["templates/**/*"]` to the package data at `pyproject.toml:93` |
| A Pro save whose scene holds a type the encoder does not know returns 500 and loses the save, permanently for that diagram | Pro clinicians | high | Wrap `diagramjson.store()` in the save path and fall back to storing the pickle bytes unchanged |
| Personal-app code runs inside the Pro save transaction; if it raises, the save is rolled back | Pro clinicians | high | Move the change-log insert after the commit, or wrap it so its failure cannot undo the save |
| Existing Pro rows are rewritten from pickle to JSON on first save, with no migration and no backup | Pro clinicians | high | Take a database backup, then run `python -m btcopilot.diagrams.migrate_json` before opening the app to users, and read its failed count |
| Every Pro save writes clinical before/after values into a new `changes` table, unbounded | storage and confidentiality | medium | A decision, not a fix: keep it, limit it to the chat app, or set a retention rule |
| An existing read-only access grant becomes write access through the chat app | anyone sharing a diagram | high | Check the grant in the record-writing routes before applying a change |
| An old training discussion renders as if the user said everything, and the first turn renames a transcript speaker | anyone who selects a training diagram | high | Leave discussions with no chat coach speaker out of the session list |
| Diagrams carried over have no stored clusters, and detection only runs on a turn that writes an event | every existing diagram | medium | Sync clusters once per diagram, or drop the early return in the coach turn's regroup step |
| Old diagrams show an "Assistant" person as a family member | every diagram that ever had a chat on it | medium | One-shot delete of the person with id 2 where nothing links to it |
| Extracted-but-uncommitted items on old diagrams are invisible and uncommittable | old Personal diagrams | medium | Commit them in a one-shot step, or accept losing them |
| Event edits do not refresh stored clusters, so the boxes go stale | chat app | low | Re-sync clusters on the event write path |
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
6. Check write access in the record-writing routes, so a read-only grant cannot be written
   through.
7. Keep discussions with no chat coach speaker out of the session list, so a training
   transcript cannot be opened as a session and have a speaker renamed.

### Should fix

8. Make clusters appear on a diagram carried over, either by a one-shot sync or by letting
   the first coach turn sync when there is no stored cache key.
9. Delete the leftover "Assistant" person from diagrams that have one.
10. Decide what happens to extracted-but-uncommitted items on old diagrams.
11. Decide what the `changes` table keeps from Pro saves, and for how long.
12. Re-sync clusters when an event is edited, so the boxes do not go stale.
13. Narrow the never-expiring CSRF token to the chat app.

### Safe as is

The alembic revision. The Pro and training route tables. The schema symbols the desktop
imports. The pickle protocol on the wire. The one-off conversion script's own failure
handling. The training app's session authentication. Old diagram blobs still reading as
pickle. Old discussion titles, and the `kind`, `views` and `cluster_id` columns on old
statements. Old Personal-app discussions, which carry both chat speaker columns and load as
sessions unchanged.
