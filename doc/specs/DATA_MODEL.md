# Diagram Data Model Reference

Schema definitions and validation rules for the diagram data structures.

For how AI-extracted data flows through the PDP, see
[specs/PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md). For how data syncs between
apps and server, see [DATA_SYNC_FLOW.md](../../familydiagram/doc/specs/DATA_SYNC_FLOW.md).

---

## DiagramData (Top-level Container)

```python
@dataclass
class DiagramData:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pair_bonds: list[PairBond] = field(default_factory=list)
    pdp: PDP = field(default_factory=PDP)
    lastItemId: int = field(default=0)

    # Scene collections (managed by Qt frontend)
    emotions: list = field(default_factory=list)
    multipleBirths: list = field(default_factory=list)
    layers: list = field(default_factory=list)
    layerItems: list = field(default_factory=list)
    items: list = field(default_factory=list)
    pruned: list = field(default_factory=list)

    # Metadata
    version: int | None = None
    versionCompat: int | None = None
    name: str | None = None

    # UI flags
    hideNames: bool = False
    showAliases: bool = False
    scaleFactor: float = 1.0
    # ... other UI flags

    # Clusters
    clusters: list = field(default_factory=list)
    clusterCacheKey: str | None = None
```

Stored as a pickle blob in `diagrams.data` (PostgreSQL `LARGEBINARY`). All 40+
fields are loaded dynamically via `dataclasses.fields()` — never a hardcoded
subset.

---

## Person

```python
@dataclass
class Person:
    id: int | None = None
    name: str | None = None
    last_name: str | None = None
    nick_name: str | None = None
    gender: str | None = None
    parents: int | None = None       # PairBond ID
    confidence: float | None = None  # 1.0 = committed, 0.0-0.9 = PDP
```

**ID Convention** (shared across Person, Event, PairBond):
- Positive integers: committed diagram items
- Negative integers: uncommitted PDP items
- IDs 1 and 2 reserved for User and Assistant

**Parents**: Single PairBond ID (not a list). A person has exactly one pair of
biological parents. The PairBond must exist before the Person can reference it.

**PDPDeltas can reference positive IDs** to update committed items (e.g.
setting `parents` on the speaker after learning who their parents are).

---

## Event

```python
@dataclass
class Event:
    id: int
    kind: EventKind
    person: int | None = None
    spouse: int | None = None
    child: int | None = None
    description: str | None = None
    dateTime: str | None = None
    endDateTime: str | None = None
    symptom: VariableShift | None = None
    anxiety: VariableShift | None = None
    relationship: RelationshipKind | None = None
    relationshipTargets: list[int] = field(default_factory=list)
    relationshipTriangles: list[tuple[int, int]] = field(default_factory=list)
    functioning: VariableShift | None = None
    confidence: float | None = None
```

---

## PairBond

```python
@dataclass
class PairBond:
    id: int | None = None
    person_a: int | None = None
    person_b: int | None = None
    confidence: float | None = None
```

Represents a reproductive/emotional pair bond. Central to Bowen theory.

**Two creation paths** (system deduplicates via `_pair_bond_exists()`):
1. **Explicit**: AI/auditor creates PairBond directly ("my parents are Mary and
   John")
2. **Inferred**: System auto-creates at commit time when a committed event
   requires a PairBond between its person and spouse but none exists.
   - `_create_inferred_pair_bond_items()` handles non-offspring `isPairBond()`
     events: Bonded, Married, Separated, Divorced, Moved
   - `_create_inferred_birth_items()` handles Birth/Adopted events, also
     inferring missing people (spouse, child) and setting `child.parents`

Explicit extraction is primary. Inference is fallback. See decision log
2026-02-14.

---

## PDP (Pending Data Pool)

```python
@dataclass
class PDP:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pair_bonds: list[PairBond] = field(default_factory=list)
```

Container for AI-extracted items awaiting user confirmation. All items have
negative IDs. For how data enters and exits the PDP, see
[specs/PDP_DATA_FLOW.md](specs/PDP_DATA_FLOW.md).

---

## PDPDeltas (Change Set)

```python
@dataclass
class PDPDeltas:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pair_bonds: list[PairBond] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)
```

Per-statement change set produced by AI extraction. Can contain negative IDs
(new PDP items) and positive IDs (updates to committed diagram items).

---

## Enums

### EventKind

```python
class EventKind(enum.Enum):
    Bonded = "bonded"
    Married = "married"
    Birth = "birth"
    Adopted = "adopted"
    Moved = "moved"
    Separated = "separated"
    Divorced = "divorced"
    Shift = "shift"
    Death = "death"
```

`isPairBond()` returns True for: Bonded, Married, Birth, Adopted, Moved,
Separated, Divorced. These require a Marriage (pair bond) in the Qt scene.

### VariableShift

```python
class VariableShift(enum.StrEnum):
    Up = "up"
    Down = "down"
    Same = "same"
```

### RelationshipKind

```python
class RelationshipKind(enum.Enum):
    Fusion = "fusion"
    Conflict = "conflict"
    Distance = "distance"
    Overfunctioning = "overfunctioning"
    Underfunctioning = "underfunctioning"
    Projection = "projection"
    DefinedSelf = "defined-self"
    Toward = "toward"
    Away = "away"
    Inside = "inside"
    Outside = "outside"
    Cutoff = "cutoff"
```

---

## Validation & Constraints

### Shared ID Namespace

People, Events, and PairBonds share a single ID namespace. A person ID -1 and
an event ID -1 would collide — this is invalid. Validation rejects deltas with
ID collisions across entity types.

### Person Constraints
- At most one `parents` PairBond
- Deduplication by name during extraction

### Event Constraints
- One event per variable shift (merge by timestamp + people + variables)
- Relationship events require `relationshipTargets` or `relationshipTriangles`
- Triangle requires 2 inside + 1 outside (or vice versa)

### Confidence Levels
- 1.0 = committed diagram item
- 0.0-0.9 = PDP item (extraction confidence)

---

## Persistence

### Diagram Model

`btcopilot/pro/models/diagram.py`

```python
class Diagram(db.Model, ModelMixin):
    __tablename__ = "diagrams"
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    data = Column(LargeBinary)  # Pickled DiagramData dict
    version = Column(Integer)
    # ...
```

`get_diagram_data()` / `set_diagram_data()` handle pickle
serialization/deserialization. Version tracking and transport mechanics are in
[DATA_SYNC_FLOW.md](../../familydiagram/doc/specs/DATA_SYNC_FLOW.md).

### Statement Model

`btcopilot/personal/models/statement.py`

```python
class Statement(db.Model, ModelMixin):
    __tablename__ = "statements"
    text = Column(Text)
    discussion_id = Column(Integer, ForeignKey("discussions.id"))
    pdp_deltas = Column(JSON)  # asdict(PDPDeltas)
    approved = Column(Boolean, default=False)
    # ...
```

### Serialization

- **Pickle**: Entire DiagramData in `Diagram.data` (preserves Qt scene objects)
- **JSON**: PDPDeltas in `Statement.pdp_deltas` and `Feedback.edited_extraction`
- Conversion: `asdict()` / `from_dict()` in `btcopilot/schema.py`

---

## File Reference

| File | Contains |
|------|----------|
| `btcopilot/schema.py` | All dataclasses, enums, `asdict()`, `from_dict()`, `commit_pdp_items()` |
| `btcopilot/pro/models/diagram.py` | Diagram SQLAlchemy model, `get/set_diagram_data()`, `update_with_version_check()` |
| `btcopilot/personal/models/statement.py` | Statement model with `pdp_deltas` JSON column |
| `btcopilot/personal/models/feedback.py` | Feedback model with `edited_extraction` JSON column |
