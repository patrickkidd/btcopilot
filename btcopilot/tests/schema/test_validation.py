import pytest

from btcopilot.pdp import get_all_pdp_item_ids, validate_pdp_deltas, apply_deltas
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
    assert "negative ID" in exc_info.value.errors[0]


def test_validate_deltas_rejects_positive_id_for_event():
    pdp = PDP()
    deltas = PDPDeltas(events=[Event(id=1, kind=EventKind.Shift, person=1)])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "negative ID" in exc_info.value.errors[0]


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
    from btcopilot.extensions.llm import dataclass_to_json_schema

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
    from btcopilot.extensions.llm import (
        dataclass_to_json_schema,
        PDP_SCHEMA_DESCRIPTIONS,
        PDP_FORCE_REQUIRED,
    )

    schema = dataclass_to_json_schema(PDPDeltas, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED)

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
