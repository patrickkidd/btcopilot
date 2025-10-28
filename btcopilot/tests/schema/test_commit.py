import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    VariableShift,
    RelationshipKind,
)


def test_commit_single_person():
    data = DiagramData(pdp=PDP(people=[Person(id=-1, name="Bob")]))
    id_mapping = data.commit_pdp_items([-1])

    assert len(data.people) == 1
    assert data.people[0]["name"] == "Bob"
    assert data.people[0]["id"] == 1
    assert id_mapping == {-1: 1}
    assert data.last_id == 1
    assert len(data.pdp.people) == 0


def test_commit_single_event():
    data = DiagramData(pdp=PDP(events=[Event(id=-1, kind=EventKind.Shift, person=1)]))
    id_mapping = data.commit_pdp_items([-1])

    assert len(data.events) == 1
    assert data.events[0]["id"] == 1
    assert data.events[0]["person"] == 1
    assert id_mapping == {-1: 1}
    assert len(data.pdp.events) == 0


def test_commit_event_with_pdp_person_reference():
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Alice")],
            events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
        )
    )
    id_mapping = data.commit_pdp_items([-2])

    assert len(data.people) == 1
    assert len(data.events) == 1
    assert data.events[0]["person"] == data.people[0]["id"]
    assert id_mapping == {-2: 1, -1: 2}
    assert len(data.pdp.people) == 0
    assert len(data.pdp.events) == 0


def test_commit_person_with_pdp_parent_references():
    data = DiagramData(
        pdp=PDP(
            people=[
                Person(id=-1, name="Father"),
                Person(id=-2, name="Mother"),
                Person(id=-3, name="Child", parent_a=-1, parent_b=-2),
            ]
        )
    )
    id_mapping = data.commit_pdp_items([-3])

    assert len(data.people) == 3
    assert id_mapping == {-3: 1, -2: 2, -1: 3}

    child = [p for p in data.people if p["name"] == "Child"][0]
    father = [p for p in data.people if p["name"] == "Father"][0]
    mother = [p for p in data.people if p["name"] == "Mother"][0]
    assert child["parent_a"] == father["id"]
    assert child["parent_b"] == mother["id"]


def test_commit_person_with_pdp_spouse_references():
    data = DiagramData(
        pdp=PDP(
            people=[
                Person(id=-1, name="Alice", spouses=[-2]),
                Person(id=-2, name="Bob", spouses=[-1]),
            ]
        )
    )
    id_mapping = data.commit_pdp_items([-1])

    assert len(data.people) == 2
    alice = [p for p in data.people if p["name"] == "Alice"][0]
    bob = [p for p in data.people if p["name"] == "Bob"][0]
    assert alice["spouses"] == [bob["id"]]


def test_commit_event_with_pdp_relationship_targets():
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            events=[
                Event(
                    id=-3,
                    kind=EventKind.Shift,
                    person=-1,
                    relationship=RelationshipKind.Conflict,
                    relationshipTargets=[-2],
                )
            ],
        )
    )
    id_mapping = data.commit_pdp_items([-3])

    assert len(data.events) == 1
    event = data.events[0]
    assert event["relationshipTargets"] == [2]


def test_commit_event_with_pdp_triangles():
    data = DiagramData(
        pdp=PDP(
            people=[
                Person(id=-1, name="P1"),
                Person(id=-2, name="P2"),
                Person(id=-3, name="P3"),
            ],
            events=[
                Event(
                    id=-4,
                    kind=EventKind.Shift,
                    person=-1,
                    relationship=RelationshipKind.Inside,
                    relationshipTriangles=[-2, -3],
                )
            ],
        )
    )
    id_mapping = data.commit_pdp_items([-4])

    assert len(data.events) == 1
    event = data.events[0]
    p2 = [p for p in data.people if p["name"] == "P2"][0]
    p3 = [p for p in data.people if p["name"] == "P3"][0]
    assert event["relationshipTriangles"] == [p2["id"], p3["id"]]


def test_commit_preserves_committed_references():
    data = DiagramData(
        people=[{"id": 1, "name": "Committed Person"}],
        last_id=1,
        pdp=PDP(
            events=[
                Event(id=-1, kind=EventKind.Shift, person=1, anxiety=VariableShift.Up)
            ]
        ),
    )
    id_mapping = data.commit_pdp_items([-1])

    assert len(data.events) == 1
    event = data.events[0]
    assert event["person"] == 1
    assert id_mapping == {-1: 2}


def test_commit_multiple_items_at_once():
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Alice"), Person(id=-2, name="Bob")],
            events=[Event(id=-3, kind=EventKind.Shift, person=-1)],
        )
    )
    id_mapping = data.commit_pdp_items([-1, -2, -3])

    assert len(data.people) == 2
    assert len(data.events) == 1
    assert len(data.pdp.people) == 0
    assert len(data.pdp.events) == 0


def test_commit_partial_pdp():
    data = DiagramData(
        pdp=PDP(
            people=[Person(id=-1, name="Keep"), Person(id=-2, name="Commit")],
        )
    )
    id_mapping = data.commit_pdp_items([-2])

    assert len(data.people) == 1
    assert data.people[0]["name"] == "Commit"
    assert len(data.pdp.people) == 1
    assert data.pdp.people[0].name == "Keep"


def test_commit_rejects_positive_id():
    data = DiagramData(pdp=PDP(people=[Person(id=-1, name="Bob")]))
    with pytest.raises(ValueError) as exc_info:
        data.commit_pdp_items([1])
    assert "must be negative" in str(exc_info.value)


def test_commit_rejects_nonexistent_pdp_id():
    data = DiagramData(pdp=PDP(people=[Person(id=-1, name="Bob")]))
    with pytest.raises(ValueError) as exc_info:
        data.commit_pdp_items([-999])
    assert "not found in PDP" in str(exc_info.value)


def test_commit_complex_transitive_closure():
    data = DiagramData(
        pdp=PDP(
            people=[
                Person(id=-1, name="GrandFather"),
                Person(id=-2, name="GrandMother"),
                Person(id=-3, name="Father", parent_a=-1, parent_b=-2),
                Person(id=-4, name="Mother"),
                Person(id=-5, name="Child", parent_a=-3, parent_b=-4),
            ],
            events=[
                Event(id=-6, kind=EventKind.Birth, person=-3, child=-5),
            ],
        )
    )

    id_mapping = data.commit_pdp_items([-6])

    assert len(data.people) == 5
    assert len(data.events) == 1
    assert len(data.pdp.people) == 0
    assert len(data.pdp.events) == 0

    child = [p for p in data.people if p["name"] == "Child"][0]
    father = [p for p in data.people if p["name"] == "Father"][0]
    assert child["parent_a"] == father["id"]
