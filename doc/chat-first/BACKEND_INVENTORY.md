# Backend inventory — what already exists

Survey of the existing btcopilot backend as of branch `chat-first-app` at commit
`9f31f76`. Purpose: the chat-first app reuses what is here instead of
reinventing it. Nothing in this file is a proposal; it is a description of code
that exists today.

Two baselines matter and are distinguished throughout:

| Baseline | Meaning |
|---|---|
| **master** | `btcopilot` origin clone, the shipped backend |
| **branch** | this worktree, master plus commits `cf4f927` (companion module port) and `9f31f76` (preferences, birthdate, discussion title) |

---

## 1. SQLAlchemy models

### 1.1 The mixin every model inherits

`btcopilot/modelmixin.py` defines `AsDictMixin` and `ModelMixin(AsDictMixin)`.
Every model in the codebase is `db.Model, ModelMixin`.

`ModelMixin` contributes three columns to every table:

| column | type | nullable | default |
|---|---|---|---|
| `id` | Integer | no | primary key, indexed |
| `created_at` | DateTime | no | `datetime.utcnow` |
| `updated_at` | DateTime | yes | none; set by `update()` |

`ModelMixin` methods:

| method | behaviour |
|---|---|
| `update(_commit=False, **kwargs)` | setattr for each kwarg that is an existing attribute, stamps `updated_at`, optional commit |
| `filter_attrs(kwargs)` classmethod | filters a dict down to real column names |

`AsDictMixin` is the project's serialization layer (section 6).

### 1.2 `users` — `btcopilot/pro/models/user.py`

| column | type | nullable | default |
|---|---|---|---|
| `active` | Boolean | no | server default `1` |
| `username` | String(100) | no | unique; holds the email address |
| `password` | String(255) | no | server default `""`; bcrypt hash |
| `reset_password_code` | String(100) | yes | bcrypt hash |
| `status` | String(64) | no | `"pending"` set in `__init__`; values `pending` / `confirmed` |
| `secret` | String(64) | yes | random 32-char; the HMAC signing secret |
| `roles` | String(255) | yes | `ROLE_SUBSCRIBER`; comma-joined string |
| `first_name` | String(100) | no | server default `""` |
| `last_name` | String(100) | no | server default `""` |
| `birthdate` | Date | yes | none — **added on this branch** |
| `preferences` | JSON | no | `{}` — **added on this branch** |
| `stripe_id` | String(200) | yes | none |
| `free_diagram_id` | Integer FK `diagrams.id` | yes | `use_alter=True` to break the circular FK |

Relationships:

| name | target | direction |
|---|---|---|
| `machines` | Machine | one-to-many, `back_populates="user"` |
| `licenses` | License | one-to-many, `back_populates="user"` |
| `sessions` | Session | one-to-many, `back_populates="user"` |
| `diagrams` | Diagram | one-to-many on `Diagram.user_id`, `back_populates="user"` |
| `discussions` | Discussion | one-to-many, `back_populates="user"` |
| `free_diagram` | Diagram | many-to-one on `User.free_diagram_id`, no back ref |

Methods: `set_password` / `check_password`, `set_reset_password_code` /
`check_reset_password_code`, `full_name()`, `set_role` / `has_role` (admin
satisfies every role; every user satisfies subscriber), `set_free_diagram()`
(creates the free diagram named "Free Diagram" if absent, then writes the blob),
and the preference accessors below. `as_dict` is overridden to exclude
`password`, `reset_password_code`, `stripe_id` and to split `roles` into a list.

### 1.3 Preference accessors and key space — `btcopilot/pro/models/preferences.py`

Added on this branch. `PrefKey` is a `StrEnum` with four keys; three of them have
their own value enum, one is a plain bool.

| key | value space | default |
|---|---|---|
| `speak` | bool | `False` |
| `proactive` | `Proactive` = never / rarely / weekly | `never` |
| `mode` | `ChatMode` = text / voice | `text` |
| `theme` | `Theme` = system / light / dark | `system` |

`coerce_pref(key, value)` validates and coerces; it raises on a non-bool for
`speak` and raises `ValueError` from the enum constructor for an unknown value.

On `User`: `pref(key)` returns one coerced value or the default; `prefs()`
returns the whole dict of coerced values; `set_prefs(**kwargs)` coerces and
merges into the JSON column, rejecting unknown keys because `PrefKey(name)`
raises.

### 1.4 `diagrams` — `btcopilot/pro/models/diagram.py`

| column | type | nullable | default |
|---|---|---|---|
| `user_id` | Integer FK `users.id` | no | indexed |
| `name` | String | yes | none |
| `alias` | String | yes | none |
| `use_real_names` | Boolean | yes | none |
| `require_password_for_real_names` | Boolean | yes | none |
| `data` | LargeBinary | yes | the pickled diagram blob |
| `version` | Integer | no | `1`; optimistic-lock counter |

Relationships: `user` (many-to-one), `access_rights` (one-to-many to
AccessRight), `discussions` (one-to-many to Discussion).

Methods that matter to the chat-first app:

| method | behaviour |
|---|---|
| `get_diagram_data()` | unpickles `data`, rebuilds `DiagramData`, rebuilds `pdp` via `from_dict(PDP, …)` |
| `set_diagram_data(dd)` | unpickles current blob, overwrites `pdp`, `lastItemId`, `people`, `events`, `pair_bonds`, repickles. Everything else in the blob is preserved untouched |
| `update_with_version_check(expected_version, new_data=None, diagram_data=None)` | conditional UPDATE on `version`; returns `(ok, new_version)`, `(False, None)` on conflict |
| `reserve_id_block(count)` | atomically reserves a range of item ids; `SELECT FOR UPDATE` plus optimistic version check. Pro app only |
| `check_read_access(user)` / `check_write_access(user)` | owner or matching AccessRight |
| `grant_access(user, right)` | replaces any existing right |
| `saved_at()` | `updated_at` or `created_at` |

`set_diagram_data` writes only the five keys above. It does **not** bump
`version`, so a caller that needs the optimistic lock must use
`update_with_version_check(diagram_data=…)` instead.

`FIELD_MIN_VERSIONS` plus `clientSupportsField` gate `version` out of `as_dict`
for Pro clients older than 2.1.11 and always drop the obsolete `database` field.

### 1.5 `discussions` — `btcopilot/personal/models/discussion.py`

| column | type | nullable | default |
|---|---|---|---|
| `user_id` | Integer FK `users.id` | yes | none |
| `diagram_id` | Integer FK `diagrams.id` | yes | none |
| `title` | Text | yes | none — **added on this branch** |
| `summary` | Text | yes | none |
| `discussion_date` | Date | yes | none |
| `last_topic` | Text | yes | none |
| `status` | Enum `DiscussionStatus` | no | `pending` |
| `extracting` | Boolean | no | `False` |
| `synthetic` | Boolean | no | `False` |
| `synthetic_persona` | JSON | yes | none |
| `synthetic_persona_id` | Integer FK `synthetic_personas.id` | yes | none |
| `calibration_report` | JSON | yes | none |
| `calibration_advice` | JSON | yes | none |
| `statement_reviews` | JSON | yes | none |
| `extracted_through_order` | Integer | yes | re-extraction cursor |
| `pending_extracted_through_order` | Integer | yes | cursor held until accept |
| `chat_user_speaker_id` | Integer FK `speakers.id` | yes | none |
| `chat_ai_speaker_id` | Integer FK `speakers.id` | yes | none |

`DiscussionStatus` is a StrEnum: pending, generating, failed,
pending_extraction, extracting, ready.

Relationships: `user`, `diagram` (back to `Diagram.discussions`), `statements`
(ordered by `Statement.order`, cascade delete-orphan), `speakers` (cascade
delete-orphan), and the two single-valued speaker roles `chat_user_speaker` /
`chat_ai_speaker`.

Methods: `conversation_history(up_to_order=None)` renders the transcript as
`Name: text` lines; `update_summary()` calls the LLM with
`SUMMARIZE_MESSAGES_PROMPT` and writes `summary`; `next_order()` allocates the
next statement order under a `SELECT FOR UPDATE` on the discussion row.

### 1.6 `statements` — `btcopilot/personal/models/statement.py`

| column | type | nullable | default |
|---|---|---|---|
| `text` | Text | yes | none |
| `discussion_id` | Integer FK `discussions.id` | yes | none |
| `speaker_id` | Integer FK `speakers.id` | yes | none |
| `pdp_deltas` | JSON | yes | none |
| `custom_prompts` | JSON | yes | none |
| `order` | Integer | yes | ordering within the discussion |
| `approved` | Boolean | yes | `False` |
| `approved_by` | String(100) | yes | none |
| `approved_at` | DateTime | yes | none |
| `exported_at` | DateTime | yes | none |

Relationships: `discussion`, `speaker`, plus a `feedbacks` backref from
`Feedback`. Properties `is_approved` and `can_export`.

### 1.7 `speakers` — `btcopilot/personal/models/speaker.py`

| column | type | nullable | default |
|---|---|---|---|
| `discussion_id` | Integer FK `discussions.id` | yes | none |
| `person_id` | Integer | yes | id of a Person inside the diagram blob, not an FK |
| `name` | String(255) | yes | none |
| `type` | Enum `SpeakerType` | yes | expert / subject |

Relationships: `discussion`, `statements`, and the two back references
`user_discussion` / `ai_discussion`.

### 1.8 `licenses` — `btcopilot/pro/models/license.py`

| column | type | nullable | default |
|---|---|---|---|
| `user_id` | Integer FK `users.id` | yes | indexed |
| `policy_id` | Integer FK `policies.id` | no | none |
| `key` | String(64) | no | unique; uuid4 assigned in `__init__` |
| `activated_at` | DateTime | yes | none |
| `active` | Boolean | no | `True` |
| `canceled_at` | DateTime | yes | none |
| `canceled` | Boolean | yes | `False` |
| `stripe_id` | String(64) | yes | none |

Relationships: `user`, `policy` (many-to-one, `uselist=False`), `activations`.
`days_old()` returns days since activation.

### 1.9 `policies` — `btcopilot/pro/models/policy.py`

| column | type | nullable | default |
|---|---|---|---|
| `code` | String(255) | yes | unique |
| `interval` | String(32) | yes | matches the Stripe plan interval |
| `product` | String(128) | yes | none |
| `maxActivations` | Integer | yes | `2` |
| `name` | String(64) | yes | none |
| `description` | String(2048) | yes | none |
| `amount` | Float(2) | yes | `0.0` |
| `active` | Boolean | yes | `False`; works but not advertised |
| `public` | Boolean | yes | `False`; advertised |

`Policy.POLICIES` is a class-level list of the six seeded policies: free, beta,
alpha, client, professional monthly, professional annual, each with a name,
amount and description. The plan screen's price and description text can come
from these rows rather than from a new constant.

### 1.10 `sessions` — `btcopilot/pro/models/session.py`

| column | type | nullable | default |
|---|---|---|---|
| `user_id` | Integer FK `users.id` | no | indexed |
| `token` | String(64) | no | unique uuid4 |

This is the Pro app's API token, unrelated to the browser cookie session and
unrelated to a chat session. `account_editor_dict()` builds the whole account
payload the Pro app's account screen renders: every active user, every public
policy, the deactivated version list, and the current session with its user,
licenses, activations, machines and free diagram.

### 1.11 `machines`, `activations`, `access_rights` — `btcopilot/pro/models/etc.py`

| model | columns | relationships |
|---|---|---|
| `Machine` | `user_id` FK not null, `code` String(36) unique indexed not null, `name` String(255) | `user`, `activations` |
| `Activation` | `license_id` FK not null, `machine_id` FK not null | `license`, `machine` |
| `AccessRight` | `diagram_id` FK not null indexed, `user_id` FK not null indexed, `right` String not null | `diagram`, `user` |

### 1.12 `synthetic_personas` — `btcopilot/personal/models/syntheticpersona.py`

Columns `name` (Text unique not null), `background`, `traits` (JSON, list of
trait strings), `attachment_style`, `presenting_problem`, `data_points` (JSON),
`sex`, `age` (Integer not null). No relationships except the FK pointed at it
from `Discussion.synthetic_persona_id`. `to_persona()` rebuilds the test-harness
dataclass. Training only; not relevant to the chat-first app.

### 1.13 `feedbacks`, `reconciliation_notes` — `btcopilot/training/models.py`

`Feedback`: `statement_id` FK not null, `auditor_id` String(100) not null,
`feedback_type` String(20) not null (conversation or extraction), `thumbs_down`
Boolean, `comment` Text, `edited_extraction` JSON, `meta` JSON, plus the
approval quartet `approved` / `approved_by` / `approved_at` / `exported_at` and
`rejection_reason`. Relationship `statement` with a `feedbacks` backref.

`ReconciliationNote`: `statement_id` FK not null, `note` Text not null,
`resolved` Boolean, `created_by` String(255) not null.

---

## 2. Alembic

| item | value |
|---|---|
| config | `alembic.ini` at the repo root |
| revision directory | `alembic/versions/` |
| template | `alembic/script.py.mako` |
| `target_metadata` | `None` in `alembic/env.py`, so autogenerate is not wired up; revisions are written by hand |
| revision count | 18 on this branch |
| head on master | `c8f1a2d3e4b5` (re-extraction cursor on discussion) |
| head on this branch | `e1f2a3b4c5d6` (preferences, birthdate, discussion title) |

The chain from base: `cbc6ba6febe0` → `7c9e805e2b21` → `b30fb43b8f92` →
`fc24860407c0` → `6a711267d4ed` → `fea616e0fe7d` → `a1b2c3d4e5f6` →
`c8d9e0f1a2b3` → `d4e5f6a7b8c9` → `3b7558242b72` → `e5f6a7b8c9d0` →
`d2a5320cadc4` → `a2b3c4d5e6f7` → `b3c4d5e6f7a8` → `a57ced0bc0eb` →
`c8f1a2d3e4b5` → `e1f2a3b4c5d6`.

Conventions a new revision must follow, taken from the existing files:

- File name `<hex id>_<snake_case_summary>.py`; the id is an invented hex string,
  not necessarily generated by alembic.
- Module docstring is the human summary, then a blank line, then
  `Revision ID:`, `Revises:`, `Create Date:`.
- `from alembic import op` and `import sqlalchemy as sa` only.
- Four module-level identifiers: `revision`, `down_revision`, `branch_labels =
  None`, `depends_on = None`.
- Both `upgrade()` and `downgrade()` are implemented; downgrade reverses the
  upgrade in the opposite order.
- New non-nullable columns carry a `server_default` so the migration works
  against populated tables.

A second revision added by this work must set `down_revision =
"e1f2a3b4c5d6"`, not the master head, or the chain forks.

---

## 3. The diagram payload

### 3.1 Where it lives

`btcopilot/schema.py` is the only public submodule. It is imported by the Pro
and Personal app builds, where Flask and SQLAlchemy are unavailable, so it must
never import from another btcopilot module. `btcopilot/tests/schema/test_isolation.py`
enforces that.

### 3.2 Enums

| enum | base | members |
|---|---|---|
| `PersonKind` | StrEnum | male, female, abortion, miscarriage, unknown |
| `EventKind` | Enum | bonded, married, birth, adopted, moved, separated, divorced, shift, death |
| `RelationshipKind` | Enum | fusion, conflict, distance, overfunctioning, underfunctioning, projection, defined-self, toward, away, inside, outside, cutoff |
| `VariableShift` | StrEnum | up, down, same |
| `DateCertainty` | StrEnum | unknown, approximate, certain |
| `ClusterPattern` | StrEnum | see `schema.py` |
| `DiscussionStatus` | StrEnum | in `personal/models/discussion.py`, not schema |

`EventKind` carries the predicates the UI needs: `isPairBond()`,
`isSelfDescribing()`, `isStructural()`, `isOffspring()`, and `menuLabel()`.
`RelationshipKind.menuLabel()` gives the display label for each kind, including
"Triangle to inside" and "Triangle to outside".

`DateCertainty` also encodes the F1 matching window: unknown matches any date,
approximate is plus or minus 365 days, certain is plus or minus 7 days.

### 3.3 Dataclasses

`Person`: `id`, `name`, `last_name`, `gender` (PersonKind), `parents` (the id of
a PairBond, not of a person), `confidence`.

`PairBond`: `id`, `person_a`, `person_b`, `married` (tri-state: None unknown,
True married, False romantic but unmarried), `confidence`.

`Event`: `id` (required), `kind` (required, EventKind), `person`, `spouse`,
`child`, `description`, `notes`, `location`, `dateTime`, `endDateTime`,
`dateCertainty` (defaults to certain), `symptom`, `anxiety`, `relationship`,
`relationshipTargets` (list of person ids), `relationshipTriangles` (list of
person ids), `functioning`, `confidence`.

Note the field names the event editor must use: the spec calls them summary,
details and where; the dataclass calls them `description`, `notes` and
`location`. The four shift variables are `symptom`, `anxiety`, `functioning` and
`relationship`, and only `relationship` takes an enum from `RelationshipKind`;
the other three take `VariableShift`.

`PDPDeltas` and `PDP` each hold `people`, `events`, `pair_bonds` and a `delete`
list of ids. Negative ids are staged items; positive ids inside the PDP are
pending edits to already-committed items.

`Cluster`: `id`, `title`, `summary`, `eventIds`, `startDate`, `endDate`,
`pattern`, `dominantVariable`. `ClusterResult` wraps a list plus a `cacheKey`.

### 3.4 `DiagramData`

The whole diagram. Scene-facing collections are **lists of plain dicts**, not
dataclasses: `people`, `events`, `pair_bonds`, `emotions`, `multipleBirths`,
`layers`, `layerItems`, `items`, `pruned` (the `SCENE_COLLECTION_FIELDS` list).
Only `pdp` holds dataclasses. Scalars include `id`, `uuid`, `name`, `tags`,
`loggedDateTime`, `masterKey`, `alias`, `version`, `versionCompat`, `clusters`,
`clusterCacheKey`, `lastItemId`, and a long block of Scene display flags
(`readOnly`, `useRealNames`, `hideNames`, `hideSARFGraphics` and the rest).

This dict-versus-dataclass split is the single most important fact for event
CRUD. A committed event is a dict inside `DiagramData.events`; the `Event`
dataclass describes its shape but is not what is stored.

Helpers already on `DiagramData` that event CRUD should use rather than
reimplement:

| helper | behaviour |
|---|---|
| `_next_id()` | increments and returns `lastItemId` |
| `add_person(Person)` | assigns the next id, appends `asdict(person)` |
| `add_event(Event)` | assigns the next id, appends `asdict(event)` |
| `add_pair_bond(PairBond)` | assigns the next id, appends the coerced bond chunk |
| `commit_pdp_items(ids)` | promotes staged negative-id items to committed positive-id dicts, returns the id mapping |
| `apply_parent_edits()` | applies staged parent links to committed people |
| `primary_person()` | the person dict flagged `primary` |
| `subject_display_name()` | the user's display name, or the neutral default |
| `ensure_chat_defaults()` | idempotently creates the User and Assistant people |
| `apply_local_changes(server, snapshot, local)` static | the three-way merge for one scene collection |
| `clear()` | resets every collection and flag |

Two conversions that hand-written CRUD will otherwise get wrong:
`commit_pdp_items` converts `dateTime` and `endDateTime` from ISO strings to
Qt datetimes via `validatedDateTimeText` before appending, and
`committed_bond_chunk` coerces `married=None` to `True`. Committed event dicts
therefore hold Qt datetime objects, not strings.

Module-level helpers: `asdict(obj)` and `from_dict(cls, data)` are the
dataclass/dict converters used throughout; `validatedDateTimeText`,
`pyDateTimeString`, `get_all_pdp_item_ids`, `is_parents_edit`, `next_neg`,
`hash_sarf_dicts`, `committed_bond_chunk`.

### 3.5 Storage, read and write

The diagram is a pickle in `Diagram.data`. The pickle may contain only builtins
and PyQt5 QtCore types; never a btcopilot class, dataclass or third-party class.
Both `get_diagram_data` and `set_diagram_data` import `PyQt5.sip` for its
unpickling side effect.

Every code path that writes diagram data today:

| caller | what it writes |
|---|---|
| `personal/routes/diagrams.py:38` | new diagram creation |
| `personal/routes/diagrams.py:189` | `import-text`, writes the extracted PDP |
| `personal/routes/discussions.py:115` | `extract`, writes the extracted PDP |
| `training/routes/discussions.py:78` | discussion import |
| `training/routes/discussions.py:1077` | training extract |
| `training/routes/discussions.py:1157` | clear extracted data |
| `training/routes/admin.py:449` | admin clear-database on a user's free diagram |
| `training/routes/diagrams.py:49` | new training diagram |
| `training/routes/speakers.py:56` | creating a Person when a speaker is mapped |
| `companion/seed.py:150` | seeding the companion demo diagram |
| `personal/deepreextract.py:155`, `personal/tasks.py:74`, `training/connectivity_check.py:143` | call `commit_pdp_items` on a working copy |

The two routes that write the whole blob under an optimistic lock are
`PUT /personal/diagrams/<id>` and `PATCH|PUT /v1/diagrams/<id>`, both via
`update_with_version_check`.

---

## 4. HTTP APIs

### 4.1 Blueprint map

| blueprint | prefix | body format | auth |
|---|---|---|---|
| `v1` (pro) | `/v1` | pickle | HMAC header signature |
| `personal` | `/personal` | JSON | HMAC header signature |
| `training` | `/training` | JSON and HTML | browser cookie session |
| `companion` | `/companion` | JSON and HTML | browser cookie session, plus CSRF |

The format split matters more than the path split. The `/personal` endpoints are
clean JSON REST but are authenticated by a request signature that a browser
cannot produce, so the chat-first page cannot call them directly. The
`/companion` blueprint exists precisely because of this: it is session
authenticated and re-uses the personal helpers server-side.

### 4.2 Companion — `btcopilot/companion/routes.py`

| method | path | accepts | returns |
|---|---|---|---|
| GET | `/companion/` | none | the page, with the latest discussion's statements |
| POST | `/companion/chat` | JSON `{statement}` | JSON `{statement, discussion_id}` |
| GET | `/companion/timeline` | none | the timeline payload plus an `extraction` status block |

`before_request` runs `csrf.protect()` on every mutating method then
`_authenticate_training_app()`. A context processor injects `csrf_token`. A
`CSRFError` handler returns the description with 400.

`_discussion(user, create=False)` picks the most recent discussion on the user's
free diagram, optionally creating one via the personal blueprint's
`_create_discussion`.

`GET /companion/timeline` calls `Diagram.get_diagram_data()` then
`build_timeline(data)` and adds `_extraction_status`, whose state is one of
extracting, pending_review, chat_ahead, current.

`build_timeline` (in `companion/timeline.py`) returns `people`, `pair_bonds`,
`lanes`, `bond_lanes`, `strip`, `shelf`, `questions` and `axis`. Undated or
unknown-certainty events land on the `shelf`; the amber question marks come from
`questions`.

### 4.3 Personal — JSON REST, signature authenticated

| method | path | accepts | returns |
|---|---|---|---|
| GET | `/personal/assemblyai-key` | none | `{success, api_key}` |
| POST | `/personal/discussions` | `{statement?, model?}` | the discussion with speakers and statements, plus `statement` if a message was sent |
| GET | `/personal/discussions` | none | list of discussions for the current user |
| GET | `/personal/discussions/<id>` | none | one discussion with speakers and statements |
| POST | `/personal/discussions/<id>/statements` | `{statement, model?}` | `{statement}` — the coach reply, via `ask()` |
| POST | `/personal/discussions/<id>/extract` | none | counts plus the extracted PDP |
| POST | `/personal/discussions/<id>/commit-pdp` | `{item_ids, full_accept?, accepted_through_order?}` | commit result |
| POST | `/personal/discussions/<id>/deep-reextract` | `{k}` | `{task_id}` |
| GET | `/personal/discussions/<id>/deep-reextract-status/<task_id>` | none | progress |
| POST | `/personal/discussions/<id>/deep-reextract/<task_id>/cancel` | none | `{success}` |
| POST | `/personal/diagrams/` | `{name}` | `{success, diagram}` |
| GET | `/personal/diagrams/` | none | `{diagrams: [{id, name, version}]}` |
| GET | `/personal/diagrams/<id>` | none | the diagram including base64 data, discussions, access rights |
| PUT | `/personal/diagrams/<id>` | `{expected_version, data}` | `{success, version}` or 409 with the current version and data |
| GET | `/personal/diagrams/<id>/discussions` | none | discussions on that diagram |
| POST | `/personal/diagrams/<id>/import-text` | `{text}` | `{success, pdp, summary}` |
| POST | `/personal/diagrams/<id>/clusters` | `{events}` | `{clusters, cacheKey}` |

There is **no** update, rename or delete route for a discussion in the personal
blueprint, and **no** user, profile, preferences or account route anywhere in it.

### 4.4 Training — session authenticated

Relevant rows only; the full set spans thirteen child blueprints.

| method | path | accepts | returns | role |
|---|---|---|---|---|
| GET | `/training/account` | none | the account page with user and licenses | auditor |
| PATCH | `/training/discussions/<id>` | any of `discussion_date`, `summary`, `last_topic`, `extracting` | `{success, updated_fields}` | auditor |
| DELETE | `/training/discussions/<id>` | none | `{success, message}` | owner or admin |
| POST | `/training/discussions/<id>/extract` | none | extraction counts | admin |
| POST | `/training/diagrams` | `{user_id, name}` | the new diagram | auditor |
| DELETE | `/training/diagrams/<id>` | none | `{success}` | owner or admin |
| GET/POST/DELETE | `/training/diagrams/<id>/access-rights[/<id>]` | grant and revoke | access-right JSON | owner or admin |
| GET | `/training/diagrams/render/<statement_id>[/<auditor_id>]` | `embed` | the SVG diagram | auditor |
| PUT | `/training/speakers/<id>` | `{person_id?, name?, type?}` | `{success, updated_fields}` | auditor |
| GET | `/training/admin/users/<id>/details` | none | the user with discussions and licenses | admin |
| PUT/PATCH | `/training/admin/users/<id>` | `{roles?, first_name?, last_name?, status?, active?}` | `{success, changes}` | admin |
| POST | `/training/auth/logout` | CSRF token | redirect to login, session cleared | none |
| GET | `/training/auth/login` | none | the login landing page | none |
| GET | `/training/auth/app` | `token` | redirect into the app | token |

`PATCH /training/discussions/<id>` is the closest existing thing to a rename,
but it is auditor-gated and does not accept `title`.

### 4.5 Pro — pickle over HTTP, signature authenticated

Not callable from a browser. Listed because it is where account, license and
plan behaviour already lives: `/v1/init` (session plus licenses),
`/v1/sessions` (login), `/v1/sessions/<token>` (GET and DELETE, the latter being
sign-out), `/v1/policies`, `/v1/licenses` and `/v1/licenses/<key>` with cancel
and import, `/v1/machines/<code>`, `/v1/activations`, `/v1/access_rights`,
`/v1/users/<id>` (updates first name, last name, password),
`/v1/users/<id>/free_diagram`, `/v1/diagrams` and `/v1/diagrams/<id>`,
`/v1/diagrams/<id>/reserve_ids`, and the legacy `/v1/copilot/chat`.

### 4.6 Which existing routes a new front end can call as-is

| need | existing route | usable from the browser? |
|---|---|---|
| coach reply | `POST /companion/chat` | yes |
| the picture | `GET /companion/timeline` | yes |
| sign out | `POST /training/auth/logout` | yes |
| list diagrams | `GET /personal/diagrams/` | no, signature auth |
| list discussions | `GET /personal/discussions` | no, signature auth |
| rename a discussion | `PATCH /training/discussions/<id>` | only for auditors, and no `title` field |
| licenses and plan | `GET /training/account` | HTML page, auditor only |
| profile fields | `PUT /training/admin/users/<id>` | admin only |

---

## 5. Auth

`btcopilot/auth.py` has no routes. `current_user()` caches on `g` and then
dispatches on the request path:

| path prefix | mechanism |
|---|---|
| `/v1/` or `/personal` | `_authenticate_pro_personal_apps()` |
| `/training` | `_authenticate_training_app()` |
| anything else, `/companion` included | returns `None` |

`_authenticate_pro_personal_apps` reads the `FD-Authentication` header, splits it
on colons, and either takes the anonymous path or looks the user up by username
and recomputes the signature from the method, Content-MD5, Content-Type, Date
and the full resource path including the query string. A mismatch aborts 401.

`_authenticate_training_app` checks, in order: the `FLASK_AUTO_AUTH_USER`
environment variable (development and test convenience), then `session["user_id"]`
from the browser cookie. On failure it raises an HTTPException carrying a
redirect to the login page, so an unauthenticated web request lands on login as
a 302 rather than a 403.

Because `current_user()` returns `None` for `/companion`, the companion blueprint
calls `_authenticate_training_app()` itself in `before_request`; that populates
`g.current_user`, and the later `auth.current_user()` calls inside its views hit
the `g` cache. Any new blueprint outside the three known prefixes must do the
same.

Role gating: `require_role(minimum)` and the `minimum_role(role)` decorator,
which works on both a Blueprint and a view function, with the precedence
function, then nested blueprint, then parent blueprint, then subscriber.
`User.has_role` treats admin as satisfying everything and treats subscriber as
satisfied by everyone.

Sign-out is `POST /training/auth/logout`, which clears the Flask session and
redirects to login. The Pro app's equivalent is `DELETE /v1/sessions/<token>`.

CSRF: `CSRFProtect` is initialised in `extensions/init_csrf`, but `app.py` sets
`WTF_CSRF_CHECK_DEFAULT=False`, so protection is opt-in per blueprint. The
companion blueprint opts in by calling `csrf.protect()` on every mutating method
in `before_request` and exposes the token to templates through a context
processor.

---

## 6. Serialization

There is one serialization layer and it is `AsDictMixin` in
`btcopilot/modelmixin.py`. There is no marshmallow, no pydantic and no
per-model `to_dict`.

| method | behaviour |
|---|---|
| `as_dict(update, include, exclude, only)` | rails-style. `only` is exclusive; otherwise all columns plus anything named in `include`, minus anything in `exclude`. `include` and `only` accept a string, a list, or a nested dict whose values are the same argument set for the related model |
| `flask_dict(...)` | `as_dict` round-tripped through the project JSON encoder, so the result is JSON-safe |
| `as_json(...)` | the JSON string |
| `as_log_dict()` | override point for logging |

`_marshal_attr` recurses into relationship collections and single related
models, converts `Decimal` to float, and calls zero-argument callables so a
method name can be passed in `include` (this is how `Diagram.as_dict` exposes
`saved_at`). `created_at` and `updated_at` are included by default.

Two models override `as_dict`: `User` (drops the secrets, splits roles into a
list) and `Diagram` (defaults `include` to user, access rights and `saved_at`,
and drops version-gated fields).

For the dataclass layer, `schema.asdict` and `schema.from_dict` are the
converters. `from_dict` handles the nested dataclasses and enum coercion.

A new endpoint should return `model.as_dict(only=[...])` or `flask_dict`, and a
new diagram payload should go through `schema.asdict`. Neither needs a new
serializer.

---

## 7. Duplication verdict

Each row is what the build spec proposes to add, checked against the code.

| spec proposes | verdict | what exists |
|---|---|---|
| `preferences` JSON column on `User` | **Already built on this branch.** Do not add | `users.preferences`, JSON, not null, default `{}`, in commit `9f31f76`, with `PrefKey` / `Proactive` / `ChatMode` / `Theme` and the `pref` / `prefs` / `set_prefs` accessors in `pro/models/preferences.py`. Covers speak, proactive, mode and theme, which is the entire Coach and Appearance settings surface |
| `birthdate` column on `User` | **Already built on this branch.** Do not add | `users.birthdate`, Date, nullable, same commit. `first_name` and `last_name` were already on master |
| `title` column on `Discussion` | **Already built on this branch.** Do not add | `discussions.title`, Text, nullable, same commit |
| one alembic revision for the above | **Already built on this branch.** Do not add a second one for these columns | `alembic/versions/e1f2a3b4c5d6_add_user_preferences_birthdate_discussion_title.py`. It is the new head; any further revision must set `down_revision = "e1f2a3b4c5d6"` |
| event CRUD endpoints | **New endpoint, existing machinery.** Write the route, not the mutation logic | No route anywhere creates, edits or deletes a single committed event. The machinery exists: `Diagram.get_diagram_data` / `set_diagram_data`, `DiagramData.add_event` (which assigns the id from `lastItemId`), `DiagramData.events` as a list of dicts, and `update_with_version_check` for the optimistic lock. Two conversions must be honoured or the Pro app will read a broken diagram: dates go through `validatedDateTimeText` on the way in, and only builtins and QtCore types may reach the pickle |
| session list, switch, create endpoints | **New endpoints for the browser, but reuse the personal helpers** | `GET /personal/discussions` and `POST /personal/discussions` already do exactly this in JSON, but they are HMAC authenticated and a browser cannot sign a request. The companion blueprint already imports and reuses `_create_discussion` and `_sync_chat_speakers` from that module; do the same for list and switch rather than duplicating the query. Do not add a second creation path |
| session rename endpoint | **New endpoint.** Do not reuse the training one | `PATCH /training/discussions/<id>` exists but is auditor-gated and accepts only `discussion_date`, `summary`, `last_topic` and `extracting`. Add `title` to the companion-side route. For the auto-title, `Discussion.update_summary()` already runs a summarizing LLM call and writes `summary`; the auto-title belongs beside it rather than in a separate new mechanism |
| a preferences endpoint | **New endpoint, no new storage or validation** | No route reads or writes preferences. The whole read/write/validate contract is `User.prefs()` and `User.set_prefs(**kwargs)`; the endpoint is a thin wrapper. `set_prefs` already rejects unknown keys and bad values by raising, so the route needs no validation of its own. The speak checkbox on the chat view and the Coach settings row are one value, `PrefKey.Speak`, so they agree by construction |
| an account endpoint | **New endpoint, reuse the existing shapes** | Profile fields are `User.first_name`, `last_name`, `birthdate`, `username`. Plan and licence data is `User.licenses` → `License.policy` → `Policy`, and `Policy` already carries `name`, `amount`, `interval` and `description` for all six seeded plans, so the beta pricing placeholder can be a policy row rather than a constant in the front end. Diagrams are `User.diagrams` and `User.free_diagram`. Serialization is `as_dict(only=…)`. `Session.account_editor_dict()` is the Pro app's version of this payload; read it as the reference shape, but do not call it, since it returns every active user in the system and a pile of Pro-only machine and activation data |
| sign out | **Already exists.** Reuse | `POST /training/auth/logout` clears the Flask session and redirects to login. It is the same cookie session the companion blueprint authenticates against, so it signs the user out of `/companion` too |
| coach reference chips | **Genuinely new, end to end** | Nothing in `personal/chat.py`, `personal/prompts.py` or the companion module parses or emits references. `ask()` returns `Response(statement=str)` and nothing else; the reply is stored verbatim as a `Statement`. The four target kinds, the parser and the payload are all new. The place to extend is `Response`, since both `POST /companion/chat` and `POST /personal/discussions/<id>/statements` return from it |
| traceability from an event to the statement that coded it | **Genuinely new, and the hard one** | No link exists in either direction. `Event` has no discussion or statement field, `Statement.pdp_deltas` holds the extracted items but under their staged negative ids, and `commit_pdp_items` returns the negative-to-positive `id_mapping` to its caller and then discards it. Every caller drops it. To build this, capture that mapping at the commit sites and persist it; the sites are `personal/routes/discussions.py:355`, `personal/deepreextract.py:155`, `personal/tasks.py:74` and `training/connectivity_check.py:143`. Note that `_export_commit_state` already writes the mapping to a file in development mode, which is a debugging aid, not a storage mechanism |

Two further points that are not rows in the spec table but change how it should
be built.

**The picture is already built.** `companion/timeline.py:build_timeline` returns
people, pair bonds, lanes, bond lanes, a strip, a shelf of undated events,
questions and an axis, and `GET /companion/timeline` already serves it with an
extraction freshness state. The three levels of the picture are rendering
concerns over this payload, not a new server-side builder.

**The event editor's field names differ from the spec's.** Summary is
`description`, details is `notes`, where is `location`, when is `dateTime`, end
is `endDateTime`, certainty is `dateCertainty`. The four shift variables are
`symptom`, `anxiety`, `functioning` and `relationship`, with the first three
taking `VariableShift` and the last taking `RelationshipKind`. The targets and
triangles pickers write `relationshipTargets` and `relationshipTriangles`, both
lists of person ids. `RelationshipKind.menuLabel()` already supplies display
labels, though not the context-sensitive picker labels the spec specifies.
