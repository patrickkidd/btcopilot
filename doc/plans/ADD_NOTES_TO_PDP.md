# Plan: Add Notes to Person and Event in btcopilot.schema

## Summary

Add two types of notes fields:
- **Person.notes**: `list[Note]` with append-only semantics during delta application
- **Event.notes**: `str | None` with standard overwrite semantics

## Files to Modify

1. `btcopilot/btcopilot/schema.py` - Add Note dataclass, update Person and Event
2. `btcopilot/btcopilot/pdp.py` - Add append logic for Person.notes in apply_deltas()
3. `btcopilot/btcopilot/personal/prompts.py` - Update LLM guidance for notes extraction
4. `btcopilot/btcopilot/tests/training/test_pdp.py` - Add test coverage

## Implementation Steps

### 1. Schema Changes (schema.py)

**Add Note dataclass** (before Person, ~line 254):
```python
@dataclass
class Note:
    content: str
    timestamp: str | None = None  # ISO format datetime
    statement: int | None = None  # originating statement ID
```

**Update Person** (add notes field):
```python
@dataclass
class Person:
    id: int | None = None
    name: str | None = None
    last_name: str | None = None
    parents: int | None = None
    confidence: float | None = None
    notes: list[Note] = field(default_factory=list)  # NEW
```

**Update Event** (add notes field after confidence):
```python
    confidence: float | None = None
    notes: str | None = None  # NEW - simple string, overwrites
```

### 2. Delta Application Changes (pdp.py)

**Modify apply_deltas()** (~lines 305-321) to handle Person.notes append:

```python
for item, existing in to_update_all:
    for field in getattr(item, "model_fields_set", set()):
        value = getattr(item, field)
        if hasattr(existing, field):
            # Person.notes uses append semantics
            if isinstance(item, Person) and field == "notes" and value:
                existing_notes = getattr(existing, "notes", []) or []
                existing_keys = {(n.content, n.timestamp) for n in existing_notes}
                for note in value:
                    if (note.content, note.timestamp) not in existing_keys:
                        existing_notes.append(note)
                setattr(existing, field, existing_notes)
            else:
                setattr(existing, field, value)
```

Add import at top: `from btcopilot.schema import Person`

### 3. Prompt Updates (prompts.py)

**Update DATA_MODEL_DEFINITIONS** to add Note definition and update Person/Event:

```
*Note*: A timestamped observation about a Person. Notes capture qualitative
  information that doesn't fit into structured events. Fields:
  - `content`: The text of the note
  - `timestamp`: When noted (ISO format or fuzzy like "last Tuesday")
  - `statement`: (optional) Links to originating statement

*Person*: ...existing...
  Persons can have `notes` - a list of observations:
  - Add notes for qualitative info that doesn't map to specific events
  - Example: "Described as stubborn" (characterization, not event)
  - Example: "Has PhD in psychology" (background fact)
```

**Update PDP_ROLE_AND_INSTRUCTIONS** with guidance:

```
**When to use Person.notes vs Events:**
- Event: SPECIFIC INCIDENTS at a point in time with variable shifts
- Person.notes: GENERAL OBSERVATIONS or BACKGROUND that doesn't map to incident
- Person.notes are APPEND-ONLY - new notes add, never replace

Examples:
- "My mom has always been anxious" → Person.notes
- "My mom had a panic attack at the wedding" → Event
```

**Add example to PDP_EXAMPLES**:

```
Example: Person notes vs Events

Input: "My brother has always been the black sheep. He got arrested last month."

Output:
{
    "people": [{
        "id": -1,
        "name": "Brother",
        "notes": [{"content": "Described as 'the black sheep'", "timestamp": null}],
        "confidence": 0.8
    }],
    "events": [{
        "id": -2,
        "kind": "shift",
        "person": -1,
        "description": "Got arrested",
        "dateTime": "2025-11-07",
        "functioning": "down",
        "confidence": 0.7
    }]
}
```

### 4. Test Coverage (test_pdp.py)

Add tests for:
- `test_apply_deltas_appends_person_notes` - verify append semantics
- `test_apply_deltas_deduplicates_person_notes` - same content+timestamp not duplicated
- `test_apply_deltas_overwrites_event_notes` - verify Event.notes overwrites
- `test_commit_person_preserves_notes` - notes survive commit to diagram

## Notes

- `from_dict()` already handles `list[Dataclass]` - no changes needed
- `asdict()` will serialize Note correctly - no changes needed
- Notes for already-committed persons (positive IDs): Not handled in this implementation. LLM only generates deltas for PDP items (negative IDs). Future enhancement if needed.
- Backward compatibility: Default `notes=[]` for Person and `notes=None` for Event handles existing data without notes field.
