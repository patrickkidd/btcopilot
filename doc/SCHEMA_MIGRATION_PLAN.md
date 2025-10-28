# Schema Migration Plan: btcopilot.training Web App UI Updates

## Overview
The new `btcopilot.schema` data model introduces breaking changes to the Person and Event structures. The training web app UI and data handling must be updated to accommodate these changes.

## Critical Breaking Changes

### 1. Person Model Changes (btcopilot/schema.py:183-192)

**OLD:**
```python
{
    "id": int,
    "name": str,
    "spouses": [int],      # ✓ KEPT
    "offspring": [int],    # ✗ REMOVED
    "parents": [int],      # ✗ REPLACED
    "confidence": float
}
```

**NEW:**
```python
@dataclass
class Person:
    id: int | None = None
    name: str | None = None
    last_name: str | None = None
    spouses: list[int] = field(default_factory=list)  # ✓ KEPT
    parent_a: int | None = None  # ✗ NEW - replaces parents[0]
    parent_b: int | None = None  # ✗ NEW - replaces parents[1]
    confidence: float | None = None
```

**Impact:**
- Offspring relationships now inferred from parent_a/parent_b across all people
- Parents changed from list to two nullable fields
- No more arbitrary parent lists (max 2 parents enforced at schema level)

### 2. Event Variable Shifts: Dict → Enum (btcopilot/schema.py:194-216)

**OLD:**
```python
{
    "symptom": {"shift": "up"},
    "anxiety": {"shift": "down"},
    "functioning": {"shift": "same"}
}
```

**NEW:**
```python
symptom: VariableShift | None  # Direct enum: "up" | "down" | "same"
anxiety: VariableShift | None
functioning: VariableShift | None
```

**Impact:**
- No more nested dicts - direct enum values
- Access pattern changes from `event["symptom"].get("shift")` to `event["symptom"]`

### 3. Event Relationship: Nested Dict → Flat Structure (btcopilot/schema.py:212-214)

**OLD:**
```python
{
    "relationship": {
        "kind": "triangle",        # String
        "movers": [1, 2],         # For mechanisms
        "recipients": [3],         # For mechanisms
        "inside_a": [1],          # For triangles
        "inside_b": [2],          # For triangles
        "outside": [3]            # For triangles
    }
}
```

**NEW:**
```python
relationship: RelationshipKind | None  # Enum value directly
relationshipTargets: list[int] = []    # Replaces movers/recipients
relationshipTriangles: list[tuple[int, int]] = []  # Replaces inside_a/inside_b/outside
```

**Impact:**
- Relationship kind is now top-level enum, not nested dict key
- Triangle structure completely redesigned: list of tuples instead of three separate lists
- Mechanisms use `relationshipTargets` instead of movers/recipients

## Files Requiring Changes

### Phase 1: Backend Data Handling

#### File: `btcopilot/btcopilot/training/routes/feedback.py`

**Function: `compile_feedback_datapoints()` (lines 28-168)**

**Changes needed:**

1. **Lines 94-102: Person datapoint compilation**
   ```python
   # OLD:
   datapoint["has_offspring"] = bool(person.get("offspring"))
   datapoint["has_parents"] = bool(person.get("parents"))

   # NEW:
   # Compute offspring from ALL people/events with this person as parent
   all_people = deltas.get("people", [])
   offspring_ids = [p.get("id") for p in all_people
                    if person.get("id") in [p.get("parent_a"), p.get("parent_b")]]
   datapoint["has_offspring"] = len(offspring_ids) > 0

   # Convert parent_a/parent_b to list for compatibility
   parents = [p for p in [person.get("parent_a"), person.get("parent_b")] if p is not None]
   datapoint["has_parents"] = len(parents) > 0
   ```

2. **Lines 108-132: Variable shift datapoint extraction**
   ```python
   # OLD:
   if event.get("symptom"):
       datapoint["shift"] = event["symptom"].get("shift", "none")

   # NEW:
   if event.get("symptom"):
       datapoint["shift"] = event["symptom"]  # Direct enum value
   ```

   Apply same pattern to `anxiety` and `functioning`.

3. **Lines 134-152: Relationship datapoint extraction**
   ```python
   # OLD:
   if event.get("relationship"):
       rel = event["relationship"]
       datapoint["relationship_type"] = rel.get("kind", "unknown")
       if rel.get("kind") == "triangle":
           datapoint["triangle_inside_a"] = rel.get("inside_a", [])
           datapoint["triangle_inside_b"] = rel.get("inside_b", [])
           datapoint["triangle_outside"] = rel.get("outside", [])
       else:
           datapoint["mechanism_movers"] = rel.get("movers", [])
           datapoint["mechanism_recipients"] = rel.get("recipients", [])

   # NEW:
   if event.get("relationship"):
       datapoint["relationship_type"] = event["relationship"]  # Direct enum value

       # Get targets and triangles from new fields
       datapoint["relationship_targets"] = event.get("relationshipTargets", [])
       datapoint["relationship_triangles"] = event.get("relationshipTriangles", [])
   ```

### Phase 2: Frontend Templates - Data Editor

#### File: `btcopilot/btcopilot/training/templates/discussion_audit.html`

**Section 1: Person creation (lines 793-800)**
```javascript
// OLD:
this.extractedData.people.push({
    id: -Date.now(),
    name: 'New Person',
    spouses: [],
    offspring: [],
    parents: [],
    confidence: 0.5
});

// NEW:
this.extractedData.people.push({
    id: -Date.now(),
    name: '',
    last_name: '',
    spouses: [],
    parent_a: null,
    parent_b: null,
    confidence: null
});
```

**Section 2: Person list field handling (lines 1300-1462)**

Replace all `offspring` and `parents` array operations:

```javascript
// OLD:
if (isPersonField) {
    // Handle Person list fields (spouses, offspring, parents)
    const person = this.extractedData.people[personIndex];
    // ... array manipulation
}

// NEW:
if (isPersonField) {
    // Handle Person list fields (spouses only) and nullable parent fields
    const person = this.extractedData.people[personIndex];

    if (fieldName === 'spouses') {
        // Keep array logic for spouses
        person.spouses[listIndex] = value;
    } else if (fieldName === 'parent_a' || fieldName === 'parent_b') {
        // Direct assignment for single parent fields
        person[fieldName] = value;
    }
}
```

**Section 3: Person form HTML generation (lines 2400-2423)**

```html
<!-- OLD: -->
<div class="field">
    <label class="label is-small">Offspring (IDs, comma-separated)</label>
    <div class="control">
        <input class="input is-small" type="text"
               value="${(person.offspring || []).join(',')}"
               onchange="updatePersonField(${index}, 'offspring', ...)">
    </div>
</div>

<div class="field">
    <label class="label is-small">Parents (IDs, comma-separated)</label>
    <div class="control">
        <input class="input is-small" type="text"
               value="${(person.parents || []).join(',')}"
               onchange="updatePersonField(${index}, 'parents', ...)">
    </div>
</div>

<!-- NEW: -->
<div class="field">
    <label class="label is-small">Last Name</label>
    <div class="control">
        <input class="input is-small" type="text"
               value="${person.last_name || ''}"
               onchange="updatePersonField(${index}, 'last_name', this.value)">
    </div>
</div>

<div class="field">
    <label class="label is-small">Parent A (ID)</label>
    <div class="control">
        <input class="input is-small" type="number"
               value="${person.parent_a || ''}"
               onchange="updatePersonField(${index}, 'parent_a', this.value ? parseInt(this.value) : null)">
    </div>
</div>

<div class="field">
    <label class="label is-small">Parent B (ID)</label>
    <div class="control">
        <input class="input is-small" type="number"
               value="${person.parent_b || ''}"
               onchange="updatePersonField(${index}, 'parent_b', this.value ? parseInt(this.value) : null)">
    </div>
</div>

<!-- REMOVE offspring field entirely -->
```

**Section 4: Person template object (lines 2700-2708)**
```javascript
// OLD:
currentEditingData.people.push({
    id: null,
    name: '',
    spouses: [],
    offspring: [],
    parents: [],
    confidence: null
});

// NEW:
currentEditingData.people.push({
    id: null,
    name: '',
    last_name: '',
    spouses: [],
    parent_a: null,
    parent_b: null,
    confidence: null
});
```

### Phase 3: Frontend Templates - Filters & Display

#### File: `btcopilot/btcopilot/training/templates/feedback_index.html`

**Lines 169-186: Relationship type filter options**

Update to match `RelationshipKind` enum values from schema.py:149-180:

```html
<!-- OLD: -->
<select id="relationshipTypeFilter" onchange="filterTable()">
    <option value="">Any</option>
    <option value="triangle">Triangle</option>
    <option value="distance">Distance</option>
    <option value="conflict">Conflict</option>
    <option value="reciprocity">Reciprocity</option>
    <option value="child-focus">Child Focus</option>
</select>

<!-- NEW: -->
<select id="relationshipTypeFilter" onchange="filterTable()">
    <option value="">Any</option>
    <option value="fusion">Fusion</option>
    <option value="conflict">Conflict</option>
    <option value="distance">Distance</option>
    <option value="overfunctioning">Overfunctioning</option>
    <option value="underfunctioning">Underfunctioning</option>
    <option value="projection">Projection</option>
    <option value="defined-self">Defined Self</option>
    <option value="toward">Toward</option>
    <option value="away">Away</option>
    <option value="inside">Inside (Triangle)</option>
    <option value="outside">Outside (Triangle)</option>
    <option value="cutoff">Cutoff</option>
</select>
```

**Lines 293-305: Display logic for variable shifts**

Update to handle direct enum values:

```html
<!-- OLD: -->
{% elif dp.data_type in ['symptom', 'anxiety', 'functioning'] %}
    <span class="tag {% if dp.shift == 'up' %}is-success...">
        {{ dp.shift|upper }}
    </span>

<!-- NEW: Keep same - backend already provides string value -->
<!-- No changes needed here if backend properly extracts enum value -->
```

### Phase 4: Data Migration Compatibility

#### Consideration: Backward Compatibility with Stored Feedback

**Problem:** Existing `Feedback.edited_extraction` JSON blobs use old schema.

**Options:**

1. **Migration Script:** Convert all existing edited_extraction data
2. **Runtime Adapter:** Detect old format and convert on-the-fly
3. **Dual Support:** Accept both formats during transition period

**Recommended: Runtime Adapter**

Add to `btcopilot/training/routes/feedback.py`:

```python
def normalize_pdp_deltas_to_new_schema(data):
    """Convert old schema to new schema format for backward compatibility."""
    if not data:
        return data

    normalized = {"people": [], "events": [], "delete": data.get("delete", [])}

    # Normalize people
    for person in data.get("people", []):
        normalized_person = {
            "id": person.get("id"),
            "name": person.get("name"),
            "last_name": person.get("last_name"),  # May be None in old data
            "spouses": person.get("spouses", []),
            "confidence": person.get("confidence"),
        }

        # Convert old parents list to parent_a/parent_b
        old_parents = person.get("parents", [])
        normalized_person["parent_a"] = old_parents[0] if len(old_parents) > 0 else None
        normalized_person["parent_b"] = old_parents[1] if len(old_parents) > 1 else None

        # offspring is dropped - it's computed from parent relationships

        normalized["people"].append(normalized_person)

    # Normalize events
    for event in data.get("events", []):
        normalized_event = {
            "id": event.get("id"),
            "kind": event.get("kind"),
            "person": event.get("person"),
            "spouse": event.get("spouse"),
            "child": event.get("child"),
            "description": event.get("description"),
            "dateTime": event.get("dateTime"),
            "endDateTime": event.get("endDateTime"),
            "confidence": event.get("confidence"),
        }

        # Normalize variable shifts (dict → direct value)
        for var in ["symptom", "anxiety", "functioning"]:
            old_value = event.get(var)
            if isinstance(old_value, dict):
                normalized_event[var] = old_value.get("shift")
            else:
                normalized_event[var] = old_value

        # Normalize relationship (nested dict → flat structure)
        old_rel = event.get("relationship")
        if old_rel:
            if isinstance(old_rel, dict):
                # Old format: nested dict with kind
                normalized_event["relationship"] = old_rel.get("kind")

                # Convert movers/recipients to relationshipTargets
                movers = old_rel.get("movers", [])
                recipients = old_rel.get("recipients", [])
                normalized_event["relationshipTargets"] = movers + recipients

                # Convert triangle structure
                inside_a = old_rel.get("inside_a", [])
                inside_b = old_rel.get("inside_b", [])
                # Create tuples pairing inside_a with inside_b
                triangles = []
                for i in range(max(len(inside_a), len(inside_b))):
                    a = inside_a[i] if i < len(inside_a) else None
                    b = inside_b[i] if i < len(inside_b) else None
                    if a is not None and b is not None:
                        triangles.append([a, b])
                normalized_event["relationshipTriangles"] = triangles
            else:
                # Already new format
                normalized_event["relationship"] = old_rel
                normalized_event["relationshipTargets"] = event.get("relationshipTargets", [])
                normalized_event["relationshipTriangles"] = event.get("relationshipTriangles", [])

        normalized["events"].append(normalized_event)

    return normalized
```

Apply this function in `compile_feedback_datapoints()` before processing:

```python
def compile_feedback_datapoints():
    feedbacks = Feedback.query...

    for feedback in feedbacks:
        # ... existing code ...

        if feedback.feedback_type == "extraction" and feedback.statement.pdp_deltas:
            # Normalize to new schema
            deltas = normalize_pdp_deltas_to_new_schema(feedback.statement.pdp_deltas)

            # Process normalized data
            if deltas.get("people"):
                for person in deltas["people"]:
                    # ... rest of processing uses normalized structure
```

## Testing Plan

### Unit Tests to Add

1. **Test `normalize_pdp_deltas_to_new_schema()`**
   - Old format → New format conversion
   - New format passes through unchanged
   - Edge cases (empty lists, None values)

2. **Test Person offspring computation**
   - Given people with parent_a/parent_b, verify offspring inference
   - Test with None parents
   - Test with missing parent references

3. **Test relationship structure handling**
   - Old triangle format → New tuple format
   - Old movers/recipients → New relationshipTargets
   - Enum value extraction

### Integration Tests

1. Load existing feedback and verify it displays correctly
2. Create new feedback with new schema and save
3. Edit old feedback and verify it saves in new format
4. Filter by relationship types using new enum values

### Manual Testing Checklist

- [ ] Open discussion with old feedback - verify it displays
- [ ] Edit person: remove offspring field, test parent_a/parent_b
- [ ] Create new person - verify schema matches
- [ ] Edit event with relationship - verify new structure
- [ ] Submit feedback - verify saved format matches new schema
- [ ] Filter feedback by relationship type - verify enum values work
- [ ] Download feedback JSON - verify exported format is new schema
- [ ] Approve feedback - verify approval workflow works with new structure

## Migration Steps (Execution Order)

1. **Phase 1: Backend (No Breaking Changes)**
   - Add `normalize_pdp_deltas_to_new_schema()` function
   - Update `compile_feedback_datapoints()` to use normalizer
   - Test with existing data
   - Deploy backend changes

2. **Phase 2: Frontend Data Editor**
   - Update person creation/editing JavaScript
   - Remove offspring handling
   - Convert parents list to parent_a/parent_b
   - Test in dev environment
   - Deploy template changes

3. **Phase 3: Frontend Filters**
   - Update relationship enum values in filters
   - Test filtering with new values
   - Deploy template changes

4. **Phase 4: Validation & Cleanup**
   - Run full test suite
   - Verify existing feedback still loads
   - Verify new feedback uses new schema
   - Optional: Background job to migrate all stored edited_extraction data

## Rollback Plan

If issues are discovered:

1. Backend normalizer can be updated to handle more edge cases without frontend changes
2. Frontend can be rolled back independently (templates are stateless)
3. Database data is not modified (only JSON interpretation changes)

## Timeline Estimate

- Backend changes: 2-3 hours
- Frontend person editor: 3-4 hours
- Frontend filters/display: 1-2 hours
- Testing & validation: 2-3 hours
- **Total: 8-12 hours**

## Notes

- No database migrations required (using JSON columns)
- Changes are mostly backward-compatible via runtime normalization
- New schema enforces better data integrity (max 2 parents, clear relationship structure)
- Consider adding `last_name` field to UI even though optional
