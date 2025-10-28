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


def test_validate_deltas_rejects_event_with_nonexistent_pdp_child():
    pdp = PDP()
    deltas = PDPDeltas(
        events=[
            Event(
                id=-1,
                kind=EventKind.Birth,
                person=1,
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


def test_validate_deltas_rejects_person_with_nonexistent_pdp_parent_a():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=-1, name="Child", parent_a=-999)])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP parent_a -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_person_with_nonexistent_pdp_parent_b():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=-1, name="Child", parent_b=-999)])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP parent_b -999" in exc_info.value.errors[0]


def test_validate_deltas_rejects_person_with_nonexistent_pdp_spouse():
    pdp = PDP()
    deltas = PDPDeltas(people=[Person(id=-1, name="Alice", spouses=[-999])])
    with pytest.raises(PDPValidationError) as exc_info:
        validate_pdp_deltas(pdp, deltas)
    assert len(exc_info.value.errors) == 1
    assert "non-existent PDP spouse -999" in exc_info.value.errors[0]


def test_validate_deltas_multiple_errors():
    pdp = PDP()
    deltas = PDPDeltas(
        people=[Person(id=-1, name="Alice", spouses=[-999])],
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
