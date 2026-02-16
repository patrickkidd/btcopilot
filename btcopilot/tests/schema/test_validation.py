import pytest

from btcopilot.pdp import (
    get_all_pdp_item_ids,
    validate_pdp_deltas,
    apply_deltas,
    reassign_delta_ids,
)
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    PDPValidationError,
    Person,
    Event,
    EventKind,
    VariableShift,
    RelationshipKind,
    PairBond,
)


def test_get_all_pdp_item_ids():
    pdp = PDP(
        people=[Person(id=-1, name="Bob"), Person(id=-2, name="David")],
        events=[
            Event(id=-3, kind=EventKind.Shift, person=-1),
            Event(id=-4, kind=EventKind.Shift, person=-2),
        ],
    )
    ids = get_all_pdp_item_ids(pdp)
    assert ids == {-1, -2, -3, -4}


def test_validate_deltas_valid_new_person():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=-1, name="New Person")])
    validate_pdp_deltas(pdp, deltas)


def test_validate_deltas_valid_event_with_positive_person_id():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=1,
                anxiety=VariableShift.Up,
            )
        ]
    )
    validate_pdp_deltas(pdp, deltas)


def test_validate_deltas_valid_event_with_new_person_in_same_delta():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Bob")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-1,
                anxiety=VariableShift.Up,
            )
        ],
    )
    validate_pdp_deltas(pdp, deltas)


def test_validate_deltas_rejects_positive_id_for_person():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=1, name="Bad Person")])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "positive ID 1" in exc_info.value.errors[0]


def test_validate_deltas_rejects_positive_id_for_event():
    pdp = PDP()
    deltas = PDPDeltas(events=[Event(id=1, kind=EventKind.Shift, person=1)])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "positive ID 1" in exc_info.value.errors[0]


def test_validate_deltas_allows_positive_id_in_committed_diagram():
    pdp = PDP(
        pair_bonds=[PairBond(id=-5, person_a=1, person_b=-3)],
        people=[Person(id=-3, name="Richard")],
    )
    diagram_data = DiagramData(
        people=[{"id": 1, "name": "Jennifer"}],
        events=[],
        pair_bonds=[],
    )
    deltas = PDPDeltas(
        people=[Person(id=1, parents=-5, confidence=0.99)],
    )
    validate_pdp_deltas(pdp, deltas, diagram_data)


def test_validate_deltas_detects_id_collision_in_delta():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        events=[Event(id=-1, kind=EventKind.Shift, person=-1)],
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "share same ID" in exc_info.value.errors[0]


def test_validate_deltas_detects_person_pair_bond_collision():
    """Person and pair_bond cannot share the same ID."""
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        pair_bonds=[PairBond(id=-1, person_a=1, person_b=2)],
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "share same ID" in exc_info.value.errors[0]


def test_validate_deltas_detects_event_pair_bond_collision():
    """Event and pair_bond cannot share the same ID."""
    pdp = PDP()
    deltas = PDPDeltas(
        events=[Event(id=-1, kind=EventKind.Shift, person=1)],
        pair_bonds=[PairBond(id=-1, person_a=1, person_b=2)],
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "share same ID" in exc_info.value.errors[0]


def test_validate_deltas_detects_all_three_types_collision():
    """Person, event, and pair_bond all using the same ID."""
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        events=[Event(id=-1, kind=EventKind.Shift, person=-1)],
        pair_bonds=[PairBond(id=-1, person_a=1, person_b=2)],
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "share same ID" in exc_info.value.errors[0]


def test_validate_deltas_rejects_event_with_nonexistent_pdp_person():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=-999,
                anxiety=VariableShift.Up,
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP person -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_event_with_nonexistent_pdp_spouse():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Married,
                person=1,
                spouse=-999,
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP spouse -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_pair_bond_event_without_spouse():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Divorced,
                person=1,
                spouse=None,
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "requires spouse" in exc_info.value.errors[0]


def test_validate_deltas_allows_offspring_without_spouse():
    pdp = PDP()
    for kind in (EventKind.Birth, EventKind.Adopted):
        deltas = PDPDeltas(
            events=[Event(id=-1, kind=kind, person=1, child=1, spouse=None)]
        )
        validate_pdp_deltas(pdp, deltas)


def test_validate_deltas_allows_moved_without_spouse():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Moved,
                person=1,
                spouse=None,
            )
        ]
    )
    validate_pdp_deltas(pdp, deltas)


def test_validate_deltas_rejects_event_with_nonexistent_pdp_child():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Birth,
                person=1,
                spouse=2,
                child=-999,
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP child -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_event_with_nonexistent_pdp_relationship_target():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=1,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[-999],
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP relationship target -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_event_with_nonexistent_pdp_triangle_person():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=1,
                relationship=RelationshipKind.Inside,
                relationshipTriangles=[1, -999],
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP person -999 in triangle" in exc_info.value.errors[0]


def test_validate_deltas_rejects_person_with_nonexistent_pdp_parents():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=-1, name="Child", parents=-999)])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP pair_bond -999" in exc_info.value.errors[0]


def test_validate_deltas_multiple_errors():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice", parents=-999)],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=-888,
                spouse=-777,
            )
        ],
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 3


def test_add_pdp_deltas_success():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Bob")],
        events=[
            Event(
                id=-2,
                kind=EventKind.Shift,
                person=1,
                anxiety=VariableShift.Up,
            )
        ],
    )
    validate_pdp_deltas(pdp, deltas)
    new_pdp = apply_deltas(pdp, deltas)
    assert len(new_pdp.people) == 1
    assert new_pdp.people[0].name == "Bob"
    assert len(new_pdp.events) == 1
    assert new_pdp.events[0].person == 1


def test_add_pdp_deltas_failure():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=-999,
            )
        ]
    )
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP person -999" in exc_info.value.errors[0]


def test_add_pdp_deltas_without_validation():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Shift,
                person=-999,
            )
        ]
    )
    new_pdp = apply_deltas(pdp, deltas)
    assert len(new_pdp.events) == 1


def test_dataclass_to_json_schema_force_required():
    """Verify force_required adds fields to required list even if they have defaults."""
    from btcopilot.llmutil import dataclass_to_json_schema

    # Event has description with default=None, so without force_required it's optional
    schema_no_force = dataclass_to_json_schema(Event, {}, {})
    assert "description" not in schema_no_force.get("required", [])
    assert "dateTime" not in schema_no_force.get("required", [])

    # With force_required, these should be in required list
    force_required = {"Event": ["description", "dateTime", "person", "dateCertainty"]}
    schema_with_force = dataclass_to_json_schema(Event, {}, force_required)
    assert "description" in schema_with_force["required"]
    assert "dateTime" in schema_with_force["required"]
    assert "person" in schema_with_force["required"]
    assert "dateCertainty" in schema_with_force["required"]


def test_pdp_deltas_schema_has_event_required_fields():
    """Verify PDPDeltas schema marks Event required fields via PDP_FORCE_REQUIRED."""
    from btcopilot.llmutil import (
        dataclass_to_json_schema,
        PDP_SCHEMA_DESCRIPTIONS,
        PDP_FORCE_REQUIRED,
    )

    schema = dataclass_to_json_schema(
        PDPDeltas, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )

    # Get nested Event schema from events array items
    events_schema = schema["properties"]["events"]["items"]
    event_required = events_schema.get("required", [])

    # id and kind are required by default (no default value in dataclass)
    assert "id" in event_required
    assert "kind" in event_required

    # These are forced required via PDP_FORCE_REQUIRED
    assert "description" in event_required
    assert "dateTime" in event_required
    assert "person" in event_required
    assert "dateCertainty" in event_required


def test_reassign_delta_ids_no_collision():
    """When no collision, IDs remain unchanged."""
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
    )
    reassign_delta_ids(pdp, deltas)
    assert deltas.people[0].id == -1
    assert deltas.events[0].id == -2
    assert deltas.events[0].person == -1


def test_reassign_delta_ids_fixes_collision():
    """Colliding IDs are reassigned to unique values."""
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice")],
        events=[Event(id=-1, kind=EventKind.Shift, person=-1)],
    )
    reassign_delta_ids(pdp, deltas)

    # IDs now unique
    assert deltas.people[0].id != deltas.events[0].id
    # Reference updated
    assert deltas.events[0].person == deltas.people[0].id


def test_reassign_delta_ids_with_pair_bond():
    """Pair bond collisions are fixed."""
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
        events=[Event(id=-1, kind=EventKind.Shift, person=-1)],
        pair_bonds=[PairBond(id=-2, person_a=-1, person_b=-2)],
    )
    reassign_delta_ids(pdp, deltas)

    all_ids = {
        deltas.people[0].id,
        deltas.people[1].id,
        deltas.events[0].id,
        deltas.pair_bonds[0].id,
    }
    assert len(all_ids) == 4

    # References updated
    assert deltas.pair_bonds[0].person_a == deltas.people[0].id
    assert deltas.pair_bonds[0].person_b == deltas.people[1].id


def test_reassign_delta_ids_avoids_existing_pdp():
    """New IDs don't collide with existing PDP IDs."""
    pdp = PDP(people=[Person(id=-1, name="Existing")])
    deltas = PDPDeltas(
        people=[Person(id=-1, name="New")],
    )
    reassign_delta_ids(pdp, deltas)

    assert deltas.people[0].id != -1
    assert deltas.people[0].id < -1
