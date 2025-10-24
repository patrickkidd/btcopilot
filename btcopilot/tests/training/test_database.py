import logging

import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    Person,
    Event,
    RelationshipKind,
    EventKind,
    VariableShift,
    asdict,
)

_log = logging.getLogger(__name__)


def test_PDPerson_as_dict():
    assert asdict(Person(id=1, name="Alice", confidence=0.9)) == {
        "id": 1,
        "name": "Alice",
        "last_name": None,
        "spouses": [],
        "parent_a": None,
        "parent_b": None,
        "confidence": 0.9,
    }


def test_PDEvent_as_dict():
    assert asdict(
        Event(
            id=-2,
            kind=EventKind.Shift,
            description="Brother-in-law stopped talking during spring break due to stress.",
            dateTime="2025-03-01",
            relationship=RelationshipKind.Distance,
            person=-1,
            anxiety=VariableShift.Up,
            symptom=VariableShift.Down,
            functioning=VariableShift.Same,
            confidence=0.7,
        )
    ) == {
        "id": -2,
        "kind": "shift",
        "person": -1,
        "spouse": None,
        "child": None,
        "description": "Brother-in-law stopped talking during spring break due to stress.",
        "dateTime": "2025-03-01",
        "endDateTime": None,
        "symptom": "down",
        "anxiety": "up",
        "relationship": "distance",
        "relationshipTargets": [],
        "relationshipTriangles": [],
        "functioning": "same",
        "confidence": 0.7,
    }


@pytest.fixture
def database():
    return DiagramData(
        people=[
            Person(id=1, name="Alice"),
            Person(id=2, name="Bob"),
        ],
        events=[
            Event(
                id=3,
                kind=EventKind.Shift,
                description="Alice and Bob had a conversation",
                dateTime="2023-10-01T12:00:00Z",
                symptom=VariableShift.Down,
                anxiety=VariableShift.Up,
                functioning=VariableShift.Same,
                relationship=RelationshipKind.Distance,
                relationshipTargets=[1, 2],
            )
        ],
        pdp=PDP(
            people=[Person(id=-1, name="Alice")],
            events=[
                Event(
                    id=-2,
                    kind=EventKind.Shift,
                    description="Conversation between Alice and Bob",
                    dateTime="2023-08-01T12:00:00Z",
                )
            ],
        ),
    )


@pytest.fixture
def as_dict():
    return {
        "people": [
            {
                "id": 1,
                "name": "Alice",
                "last_name": None,
                "spouses": [],
                "parent_a": None,
                "parent_b": None,
                "confidence": None,
            },
            {
                "id": 2,
                "name": "Bob",
                "last_name": None,
                "spouses": [],
                "parent_a": None,
                "parent_b": None,
                "confidence": None,
            },
        ],
        "last_id": 0,
        "events": [
            {
                "id": 3,
                "kind": "shift",
                "person": None,
                "spouse": None,
                "child": None,
                "description": "Alice and Bob had a conversation",
                "dateTime": "2023-10-01T12:00:00Z",
                "endDateTime": None,
                "symptom": "down",
                "anxiety": "up",
                "relationship": "distance",
                "relationshipTargets": [1, 2],
                "relationshipTriangles": [],
                "functioning": "same",
                "confidence": None,
            }
        ],
        "pdp": {
            "people": [
                {
                    "id": -1,
                    "name": "Alice",
                    "last_name": None,
                    "spouses": [],
                    "parent_a": None,
                    "parent_b": None,
                    "confidence": None,
                }
            ],
            "events": [
                {
                    "id": -2,
                    "kind": "shift",
                    "person": None,
                    "spouse": None,
                    "child": None,
                    "description": "Conversation between Alice and Bob",
                    "dateTime": "2023-08-01T12:00:00Z",
                    "endDateTime": None,
                    "symptom": None,
                    "anxiety": None,
                    "relationship": None,
                    "relationshipTargets": [],
                    "relationshipTriangles": [],
                    "functioning": None,
                    "confidence": None,
                }
            ],
        },
    }


def test_Database_asdict(database, as_dict):
    assert asdict(database) == as_dict


def test_from_dict(database, as_dict):
    from btcopilot.schema import from_dict

    reconstructed = from_dict(DiagramData, as_dict)
    assert reconstructed == database


def test_bidirectional_conversion():
    """Test that asdict() and from_dict() work together"""
    from btcopilot.schema import from_dict

    # Create an event with enums
    original = Event(
        id=1,
        kind=EventKind.Shift,
        person=10,
        description="Test event",
        anxiety=VariableShift.Up,
        relationship=RelationshipKind.Distance,
        relationshipTargets=[1, 2],
    )

    # Convert to dict (enums become strings)
    dict_form = asdict(original)
    assert dict_form["kind"] == "shift"
    assert dict_form["anxiety"] == "up"
    assert dict_form["relationship"] == "distance"

    # Convert back to dataclass (strings become enums)
    reconstructed = from_dict(Event, dict_form)
    assert reconstructed == original
    assert isinstance(reconstructed.kind, EventKind)
    assert isinstance(reconstructed.anxiety, VariableShift)
    assert isinstance(reconstructed.relationship, RelationshipKind)
