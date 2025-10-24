import logging
from dataclasses import asdict

import pytest

from btcopilot.schema import (
    DiagramData,
    PDP,
    Person,
    Event,
    RelationshipKind,
    EventKind,
    VariableShift,
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
        "description": "Brother-in-law stopped talking during spring break due to stress.",
        "dateTime": "2025-03-01",
        "person": -1,
        "symptom": VariableShift.Up.value,
        "anxiety": VariableShift.Down.value,
        "relationship": RelationshipKind.Distance.value,
        "functioning": VariableShift.Same,
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
    assert DiagramData(**as_dict) == database
