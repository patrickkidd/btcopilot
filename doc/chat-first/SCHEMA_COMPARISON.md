# Schema comparison: existing record vs chat-first additions

What the record holds today, and what must be added for the chat-first personal app.
Every existing claim carries `file:line`. Every addition is marked **ruled** (decided by
Patrick) or **proposed**. Nothing here changes an existing field.

Paths are relative to `~/theapp`.

## 1. The existing record, object by object

The record is `DiagramData` (`btcopilot/btcopilot/schema.py:425-471`). On the server it is
stored as one pickled blob in `diagrams.data`, a `LargeBinary` column
(`btcopilot/btcopilot/pro/models/diagram.py:72`). The Pro app writes the same layout from
`Scene.write` (`familydiagram/pkdiagram/scene/scene.py:1357-1435`). Nine of its fields are
lists of dict chunks, listed in `SCENE_COLLECTION_FIELDS` (`schema.py:473-483`); the rest are
scalars for display and access.

| Object | Where the fields are declared | Fields that matter for chat |
|---|---|---|
| Person | `schema.py:295-301` (server), `familydiagram/pkdiagram/scene/person.py:99-155` (app) | id, name, last_name, gender, parents (a pair-bond id), confidence. The app chunk adds ~25 display fields (nickname, deceased, color, size, layers). |
| Event | `schema.py:317-338`, `familydiagram/pkdiagram/scene/event.py:27-60` | id, kind, person, spouse, child, description, notes, location, dateTime, endDateTime, dateCertainty, plus the four variables: anxiety, symptom, functioning, relationship. Relationship events also carry relationshipTargets and relationshipTriangles (lists of person ids). |
| Pair-bond | `schema.py:274-282`, `familydiagram/pkdiagram/scene/marriage.py:124-136` | id, person_a, person_b, married (None means unknown), confidence. The app chunk adds separated, divorced, custody, notes. |
| Emotion | `familydiagram/pkdiagram/scene/emotions.py:1163-1180` | kind (one of the twelve in `RelationshipKind`, `schema.py:241-268`), intensity, event, person, target, color, notes, layers. Server-side only as an opaque dict in `DiagramData.emotions`; there is no server dataclass for it. |
| Layer | `familydiagram/pkdiagram/scene/layer.py:16-29` | name, description, order, active, internal, storeGeometry, and `itemProperties`, a free dict of per-item property overrides. |
| Cluster | `schema.py:396-406` | id (a string), title, summary, eventIds, startDate, endDate, pattern, dominantVariable. |
| Multiple births, pencil strokes, callouts, pruned | `scene.py:1357-1435` | Drawing artifacts. Irrelevant to chat; must survive round-trip. |

Enums that fix the value space: `EventKind` (`schema.py:182-239`), `RelationshipKind`
(`241-268`), `PersonKind` (`174-179`), `VariableShift` up/down/same (`304-308`),
`DateCertainty` unknown/approximate/certain (`310-314`), `ClusterPattern` (`387-393`).

Ids are integers allocated from a single counter, `DiagramData.lastItemId`
(`schema.py:449`). Pending items get negative ids and are renumbered on commit
(`schema.py:614-749`). Merge is per-collection, per-id, last-write-wins, comparing a
snapshot against local and server (`schema.py:486-549`). There is no author and no
timestamp on any change: the record knows its current state, never who set it or when.

**Cluster persistence, checked because the answer was in doubt.** Clusters are stored, but
only the app ever writes them. The server endpoint is stateless: it takes an events array in
the request body, calls the detector, returns clusters and a cache key, and saves nothing
(`btcopilot/btcopilot/personal/routes/diagrams.py:206-229`). The Personal app copies the
detector's output onto the record before upload (`familydiagram/pkdiagram/personal/personalappcontroller.py:345-346`),
the client blob writer puts `clusters` and `clusterCacheKey` into the pickle
(`familydiagram/pkdiagram/server_types.py:319-331`), and the app reloads them when a scene
opens (`personalappcontroller.py:366-372`). It also keeps a redundant copy in a local disk
cache file (`familydiagram/pkdiagram/personal/clustermodel.py:98-135`). The server's own
writer, used by the extraction commit path, updates people, events, pair-bonds, pending data
and the id counter, and never touches clusters (`btcopilot/btcopilot/pro/models/diagram.py:92-107`).
So a server-side change to the record leaves the stored clusters stale rather than
recomputing them. Cluster ids are strings while every other id is an integer
(`schema.py:398`).

## 2. Chat, pending data, and ground truth: the existing tables

These are real database tables, separate from the record blob.

| Table | Declared | Links to the record |
|---|---|---|
| discussions | `btcopilot/btcopilot/personal/models/discussion.py:20-121` | Foreign keys to the user and to the diagram. Holds a summary, the discussion date, status, and the two re-extraction cursors that mark how far into the conversation has been accepted. |
| statements | `.../models/statement.py:17-45` | Foreign keys to a discussion and a speaker. Holds the text, an integer order within the discussion, the pending data this statement produced (`pdp_deltas`, a JSON blob), and auditor approval fields. |
| speakers | `.../models/speaker.py:14-40` | Foreign key to a discussion. **`person_id` is a bare integer column with no foreign key** (`speaker.py:19-21`) — confirmed. Nothing in the database enforces that it names a real person in the record, and nothing repairs it when the pending-data commit renumbers ids. |
| feedbacks | `btcopilot/btcopilot/training/models.py:17-36` | Foreign key to a statement. This is the ground truth: an auditor's corrected extraction lives in `edited_extraction`, alongside a thumbs-down flag and approval fields. |
| reconciliation_notes | `btcopilot/btcopilot/training/models.py:52-60` | Foreign key to a statement. Free-text auditor notes. |
| access_rights | `btcopilot/btcopilot/pro/models/etc.py:41-58` | Diagram plus user plus a right string. This is the existing grant mechanism. |

Pending data (`PDP`, `schema.py:349-357`) lives **inside** the record, not in a table: three
lists of people, events and pair-bonds carrying negative ids, plus a list of ids to delete.
It is the only part of the record that is provisional.

The one link from an event back to the chat statement that produced it does not exist.
`Statement.pdp_deltas` names what an extraction proposed, but once committed the resulting
event carries no reference back.

## 3. Additions

Every row is additive: a new key in the record JSON, a new table, or a new log. No existing
field changes type or meaning, so the Pro app reads an unchanged record.

| Addition | Lives in | Shape | Additive | Pro app impact |
|---|---|---|---|---|
| Change log (**ruled**) | New table beside the record | One row per change: record id, target ids, the change itself, author kind (user via chat, coach tool call, clinician via Pro), author id, time, and the statement that caused it. Append-only, never edited. | Yes, nothing in the record changes | None. Pro writes the record as it does today; its writes are logged by the server, so provenance is partial until Pro is taught to send them. |
| Clusters as first-class, model-made and stored (**ruled**) | Already a record field, `clusters` | Keep the existing shape. Add the author and correction trail through the change log rather than new cluster fields. Members are always existing event ids; a cluster that names an id not in the record is rejected on write. | Yes | None; Pro ignores the field today. |
| Coach tool: read the record (**ruled**) | No storage | Query over the record. | Yes | None |
| Coach tool: edit the record (**ruled**) | Writes the record, writes the change log | Same command shape as any other author. | Yes | None |
| Coach tool: show on the picture (**ruled**) | New record slice, `views` | A view name from a closed set (triangle over three people, span over a time range, compare two moments, sequence of moves) plus parameters that are record ids and dates. Every parameter must resolve to stored data or the call fails. | Yes | Pro ignores an unknown key today (see section 4). |
| Chips (**ruled**) | Inside statement text plus a per-statement reference list | A reference token in the message text naming a kind (event, cluster, person) and an id, rendered in both directions. | Yes, a new column on statements | None |
| Tap log (**ruled**) | New table | One row per tap, including taps that send nothing: what was tapped, its record id, time, and the discussion. Readable by the coach as context. | Yes | None |
| Event to statement provenance (**ruled**) | New record slice, or a column on the change log | Event id to statement id. Chat is the event clock and is never rewritten; the record is the state clock. | Yes | None |
| Clinician access (**ruled**) | Existing `access_rights` table | The client owns the record; a clinician is granted a right. | Yes, already exists | None |
| Typed pure JSON on the server (**ruled**) | Replaces the pickle as the stored form | Same field names and shapes. A converter serves the released Pro app the pickle it expects, built from the JSON. | Yes at the field level; the storage format changes | The released Pro app must keep working unchanged, which is the converter's whole job. This is the one item with real migration risk: every pickled Qt value (dates, colors, points) needs a JSON form and a faithful round-trip back. |
| Flexible slice channel (**ruled**) | New top-level record keys | See section 4. | Yes by construction | None |

## 4. The flexible slice mechanism (**proposed** as a mechanism; the channel itself is **ruled**)

The precedent already exists and is proven in the shipped app. Every item keeps the raw dict
it was read from and re-emits it on write, so unrecognized keys survive a load-and-save round
trip untouched (`familydiagram/pkdiagram/scene/item.py:132` writes the retained chunk
back before anything else; `item.py:139` captures it on read). At the scene level, a chunk
whose `kind` the app does not recognize is not dropped but parked in a list and written back
out unchanged (`scene.py:1263-1265` on read, `scene.py:1429-1431` on write). Layers do the
same thing for per-item property overrides through a free-form dict (`layer.py:26`).

The proposal is to make that behaviour a named, versioned channel rather than an accident:

- A slice is one top-level key in the record JSON holding an object with its own version
  number and its own contents. Views, provenance and any future experiment each get one.
- A reader that does not know a slice must carry it through its write unchanged. That is the
  existing item behaviour, promoted to a rule that applies to the whole record.
- A reader that knows the slice but sees a higher version must carry it through unchanged
  rather than guess. Forward compatibility comes from carrying, never from coercing.
- Ids inside a slice are always record ids. A slice never holds a copy of anything the record
  already holds, so a slice can go stale but can never disagree.
- Retiring a slice means deleting its key. Nothing else references it.

The one thing the existing mechanism does not give for free: the carry-through preserves
unknown keys on *items*, and unknown *item kinds*, but a new top-level key on the record is
dropped by both readers, which rebuild the record from the known field list only
(`btcopilot/btcopilot/pro/models/diagram.py:88-89` and
`familydiagram/pkdiagram/server_types.py:314-315` both filter to the declared fields). Making
slices survive requires those two readers to keep the leftover keys. That is a change to two
functions, and it changes no existing field.

## 5. Open questions, and what each answer costs in schema

1. **What happens to pending data.** If an extraction becomes a command like any other, the
   pending lists disappear from the record and the change log carries the proposal and its
   acceptance, which is one fewer thing in the record but makes every extraction immediately
   visible in the picture. If a review gate stays, the pending lists stay exactly as they are
   and the change log has to represent a proposed change distinct from an applied one, which
   means a status on every log row. These are different logs, so this is worth settling before
   the log is built.
2. **Whether a moment is always an event.** If yes, the compare-two-moments and
   sequence-of-moves views take event ids and nothing new is stored. If no, a moment is a new
   kind of record object with its own id, and every view parameter that names a moment has to
   accept both kinds.
3. **Whether anything needs a time range beyond an event's end date.** Events already carry a
   start and an end (`schema.py:326-327`) and clusters already carry a start and end date
   string (`schema.py:402-403`), so the span view can be built today. A range that belongs to
   neither an event nor a cluster would be a new object with its own id, which is the same
   cost as question 2.
