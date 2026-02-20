# PDP Data Flow

How AI-extracted data enters, accumulates in, and exits the Pending Data Pool.

For the data structures themselves, see [DATA_MODEL.md](DATA_MODEL.md).
For how diagram data syncs between apps and server, see
[DATA_SYNC_FLOW.md](../../../familydiagram/doc/specs/DATA_SYNC_FLOW.md).

## Two-Tier Delta Architecture

PDP operates as a two-tier delta system:

- **Tier 1 (per-statement)**: AI extraction produces `PDPDeltas` for each user
  statement, applied to the PDP via `apply_deltas()`.
- **Tier 2 (PDP → diagram)**: The accumulated PDP contains deltas for the
  committed diagram data, applied when the user accepts items via
  `commit_pdp_items()`.

Both tiers can reference committed diagram items (positive IDs) or PDP items
(negative IDs).

## Extraction Pipeline

### Chat Flow

1. User submits statement via Personal app
2. Server loads current DiagramData from diagram blob
3. `pdp.update()` compiles prompt with diagram state + conversation history +
   new statement, calls LLM
4. LLM returns `PDPDeltas` (JSON-structured response)
5. `apply_deltas(diagram_data.pdp, pdp_deltas)` → updated PDP
6. Updated PDP written back to diagram blob
7. `PDPDeltas` stored as JSON in `Statement.pdp_deltas` column
8. Response + updated PDP returned to client

```
User statement
    → btcopilot.personal.chat.ask()
        → pdp.update(discussion, diagram_data, statement)
            → LLM → PDPDeltas
        → apply_deltas(pdp, pdp_deltas) → new PDP
        → diagram.set_diagram_data(updated)
        → statement.pdp_deltas = asdict(pdp_deltas)
```

### apply_deltas()

`btcopilot/pdp.py`

Takes current PDP + new PDPDeltas, returns updated PDP:
1. Deep copies existing PDP
2. Builds ID maps for upsert logic
3. Updates existing items (only changed fields via `model_fields_set`)
4. Adds new items
5. Processes deletes
6. Calls `cleanup_pair_bonds()` to remove orphaned pair bonds

### cumulative()

`btcopilot/pdp.py`

Rebuilds the PDP state at any point in a discussion by replaying all
statement deltas in order up to that point. Used for display context in the
training app — shows "what the PDP looked like after statement N".

Each statement's `pdp_deltas` (or auditor `edited_extraction` if approved) is
applied sequentially. Later statements override earlier ones for the same ID.

**Not the same as `apply_deltas()`**: `cumulative()` is for read-only
reconstruction. `apply_deltas()` is the live mutation used during chat.

## Prompt Engineering Rules

The LLM is instructed to produce **sparse deltas**:

1. **SPARSE**: Most deltas contain very few items, often empty arrays
2. **NEW ONLY**: Don't re-extract data already in the diagram or PDP
3. **SINGLE EVENTS**: Each statement typically generates 0-1 new events
4. **UPDATE ONLY CHANGED FIELDS**: When updating, include only fields that
   changed

Real prompts are in fdserver (production overrides btcopilot defaults).
`btcopilot/personal/prompts.py` has the default prompt constants.

## Delta Examples

### Simple Event

```python
PDPDeltas(
    events=[Event(
        id=-2, kind=EventKind.Shift, person=1,
        description="Felt anxious when mom called",
        anxiety=VariableShift.Up, confidence=0.8
    )]
)
```

### New Person + Relationship Event

```python
PDPDeltas(
    people=[Person(id=-5, name="Mother", confidence=0.9)],
    events=[Event(
        id=-6, kind=EventKind.Shift, person=1,
        description="Told brother about mom's meddling",
        relationship=RelationshipKind.Conflict,
        relationshipTargets=[-5], confidence=0.7
    )]
)
```

### Update Committed Person (Positive ID)

```python
# Speaker (id=1) mentions parents → link to new PairBond
PDPDeltas(
    people=[
        Person(id=-3, name="Richard", gender="male", parents=-4),
        Person(id=1, parents=-4),  # Update committed speaker
    ],
    pair_bonds=[PairBond(id=-4, person_a=-5, person_b=-3)],
)
```

### Triangle

```python
PDPDeltas(
    people=[Person(id=-3, name="Brother")],
    events=[Event(
        id=-4, kind=EventKind.Shift, person=1,
        description="Triangled brother against mother",
        relationship=RelationshipKind.Inside,
        relationshipTriangles=[(1, -3)],
    )]
)
```

### Invalid: Positive ID Not in Diagram

```python
# LLM hallucinates positive ID 5, but only IDs 1 and 2 exist in diagram
PDPDeltas(people=[Person(id=5, parents=-2)])
# Raises PDPValidationError
```

## PDP Acceptance

When the user accepts a PDP item, `DiagramData.commit_pdp_items([id])`:

1. Finds the item and all transitively referenced items (accepting a person
   includes their events; accepting a pair-bond event includes the pair bond)
2. Assigns new positive IDs via `_next_id()`
3. Moves items from `pdp.*` to top-level `people`/`events`/`pair_bonds`
4. Remaps all references to use new IDs
5. Creates inferred items where needed (`_create_inferred_pair_bond_items`,
   `_create_inferred_birth_items`)

After commit, the caller adds items to the Qt scene and pushes to server. See
[DATA_SYNC_FLOW.md](../../../familydiagram/doc/specs/DATA_SYNC_FLOW.md) for
transport mechanics.

### Commit Invariants

`commit_pdp_items()` guarantees these invariants before returning committed data
to the caller:

1. **PairBond completeness**: Every committed `isPairBond()` event (Bonded,
   Married, Separated, Divorced, Moved, Birth, Adopted) that has both `person`
   and `spouse` will have a corresponding PairBond between those two people.
   Created by `_create_inferred_pair_bond_items()` for non-offspring events, and
   by `_create_inferred_birth_items()` for Birth/Adopted events.

2. **Birth/Adopted completeness**: Every committed Birth/Adopted event will have
   `person`, `spouse`, `child`, and a PairBond. Missing people are inferred.
   The child's `parents` field is set to the PairBond ID. Three cases:
   - Child only → infer both parents + pair bond
   - Person only → find existing pair bond or infer spouse + pair bond
   - Person + spouse → infer child + pair bond if missing

3. **Transitive closure**: Accepting any item also commits all items it
   transitively references (a person's events, an event's person/spouse/child,
   an event's pair bond, a person's parents pair bond, etc.).

4. **ID remapping**: All negative PDP IDs are replaced with positive committed
   IDs. No negative IDs remain in the committed output.

These invariants are required by the Qt scene's `_do_addItem()`, which validates
that `isPairBond()` events have a Marriage object — a check suppressed only
during `isInitializing` (see FR-4 in DATA_SYNC_FLOW.md).

## PDP Rejection

Removing an item transitively cascade-deletes all dependents:
- Events referencing the rejected person (as `person`, `spouse`, `child`,
  `relationshipTargets`, `relationshipTriangles`)
- Pair bonds referencing the rejected person
- People whose `parents` references the rejected pair bond

## Storage

| What | Where | Format |
|------|-------|--------|
| Accumulated PDP | `diagrams.data` blob → `DiagramData.pdp` | Pickle (via `asdict`) |
| Per-statement deltas | `statements.pdp_deltas` | JSON (via `asdict`) |
| Expert corrections | `feedback.edited_extraction` | JSON (via `asdict`) |

```
LLM → PDPDeltas (Python object)
    → asdict() → JSON (Statement.pdp_deltas)
    → apply_deltas() → Updated PDP
    → pickle.dumps(asdict(diagram_data)) → Diagram.data blob
```

## Training App / Ground Truth Coding

The training app extends the PDP pipeline with expert review:

| Model | Column | Purpose |
|-------|--------|---------|
| Statement | pdp_deltas | AI extraction (raw LLM output) |
| Feedback | edited_extraction | Expert correction of AI extraction |

### Approval Workflow

For any statement, EITHER the AI extraction OR one expert correction is
approved as ground truth — never both (mutual exclusivity rule).

```
AI extracts → Statement.pdp_deltas
    → Expert reviews in SARF Editor
        → AI correct → approve Statement
        → AI wrong → Expert corrects → Feedback.edited_extraction
                                      → approve Feedback
```

Approving Statement unapproves all Feedback for that statement, and vice versa.

### Ground Truth Data Access

- **AI extraction**: `statement.pdp_deltas`
- **GT correction**: `Feedback.query.filter_by(statement_id=...,
  feedback_type='extraction').first().edited_extraction`
- **Cumulative GT**: Iterate statements, use approved `edited_extraction` where
  available, fall back to `pdp_deltas`
- `pdp_module.cumulative()` uses AI `pdp_deltas` — NOT auditor feedback. For GT
  cumulative, build manually from Feedback records.

### Dropdown Data Sources (Training UI)

When combining people for dropdowns, later sources override earlier:
1. `window.diagramPeople` — committed people from diagram
2. `cumulativePdp.people` — accumulated from prior statements
3. `extractedData.people` — current statement's extraction

Positive IDs from cumulative override diagram data (shows updated names).

For complete GT technical details, see
[SARF_GROUND_TRUTH_TECHNICAL.md](../SARF_GROUND_TRUTH_TECHNICAL.md).

## File Reference

| File | Contains |
|------|----------|
| `btcopilot/schema.py` | `DiagramData.commit_pdp_items()`, `PDPDeltas`, `PDP` |
| `btcopilot/pdp.py` | `update()`, `apply_deltas()`, `cumulative()`, `cleanup_pair_bonds()`, `validate_pdp_deltas()` |
| `btcopilot/personal/chat.py` | `ask()` — integrates extraction + storage + response |
| `btcopilot/personal/prompts.py` | Default prompt constants (overridden by fdserver) |
| `btcopilot/personal/routes/diagrams.py` | Server-side diagram endpoints |
| `btcopilot/personal/models/statement.py` | `Statement.pdp_deltas` column |
| `btcopilot/training/routes/admin.py` | GT approval with mutual exclusivity |
| `familydiagram/personal/personalappcontroller.py` | Client-side accept/reject callers |
