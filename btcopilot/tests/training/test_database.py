import logging

import pytest

from btcopilot.schema import (
    Diagram,
    PDP,
    Person,
    Event,
    Distance,
    Conflict,
    Reciprocity,
    ChildFocus,
    Triangle,
    RelationshipKind,
    Shift,
    Anxiety,
    Symptom,
    Functioning,
)

_log = logging.getLogger(__name__)


def test_distance_model_dump():
    d = Distance(movers=[-1], recipients=[])
    assert d.model_dump() == {
        "kind": RelationshipKind.Distance,
        "movers": [-1],
        "recipients": [],
        "rationale": None,
        "shift": None,
    }


def test_triangle_model_dump():
    d = Triangle(inside_a=[-1], inside_b=[-2], outside=[-3])
    assert d.model_dump() == {
        "kind": RelationshipKind.Triangle,
        "inside_a": [-1],
        "inside_b": [-2],
        "outside": [-3],
        "rationale": None,
        "shift": None,
    }


def test_PDPerson_as_dict():
    assert Person(id=1, name="Alice", confidence=0.9).model_dump() == {
        "id": 1,
        "name": "Alice",
        "offspring": [],
        "spouses": [],
        "parents": [],
        "confidence": 0.9,
    }


@pytest.mark.parametrize(
    "relationship",
    [
        Distance(movers=[-1], recipients=[]),
        Conflict(movers=[-1], recipients=[]),
        Reciprocity(movers=[-1], recipients=[]),
        ChildFocus(movers=[-1], recipients=[]),
        Triangle(inside_a=[-1], inside_b=[], outside=[]),
    ],
    ids=[
        "Distance",
        "Conflict",
        "Reciprocity",
        "ChildFocus",
        "Triangle",
    ],
)
def test_PDEvent_as_dict(relationship):
    assert Event(
        id=-2,
        description="Brother-in-law stopped talking during spring break due to stress.",
        dateTime="2025-03-01",
        relationship=relationship,
        people=[-1],
        anxiety=Anxiety(shift=Shift.Up),
        symptom=Symptom(shift=Shift.Down),
        functioning=Functioning(shift=Shift.Same),
        confidence=0.7,
    ).model_dump() == {
        "id": -2,
        "description": "Brother-in-law stopped talking during spring break due to stress.",
        "dateTime": "2025-03-01",
        "people": [-1],
        "symptom": {"shift": Shift.Down, "rationale": None},
        "anxiety": {"shift": Shift.Up, "rationale": None},
        "relationship": relationship.model_dump(),
        "functioning": {"shift": Shift.Same, "rationale": None},
        "confidence": 0.7,
    }


@pytest.fixture
def database():
    return Diagram(
        people=[
            Person(id=1, name="Alice"),
            Person(id=2, name="Bob"),
        ],
        events=[
            Event(
                id=3,
                description="Alice and Bob had a conversation",
                dateTime="2023-10-01T12:00:00Z",
                symptom=Symptom(shift=Shift.Down),
                anxiety=Anxiety(shift=Shift.Up),
                functioning=Functioning(shift=Shift.Same),
                relationship=Triangle(
                    inside_a=[1],
                    inside_b=[2],
                    outside=[],
                ),
            )
        ],
        pdp=PDP(
            people=[Person(id=-1, name="Alice")],
            events=[
                Event(
                    id=-2,
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
                "spouses": [],
                "offspring": [],
                "parents": [],
                "confidence": None,
            },
            {
                "id": 2,
                "name": "Bob",
                "spouses": [],
                "offspring": [],
                "parents": [],
                "confidence": None,
            },
        ],
        "last_id": 0,
        "events": [
            {
                "id": 3,
                "description": "Alice and Bob had a conversation",
                "dateTime": "2023-10-01T12:00:00Z",
                "people": [],
                "symptom": {
                    "shift": Shift.Down,
                    "rationale": None,
                },
                "anxiety": {
                    "shift": Shift.Up,
                    "rationale": None,
                },
                "functioning": {
                    "shift": Shift.Same,
                    "rationale": None,
                },
                "relationship": {
                    "kind": RelationshipKind.Triangle,
                    "inside_a": [1],
                    "inside_b": [2],
                    "outside": [],
                    "rationale": None,
                    "shift": None,
                },
                "confidence": None,
            }
        ],
        "pdp": {
            "people": [
                {
                    "id": -1,
                    "name": "Alice",
                    "spouses": [],
                    "offspring": [],
                    "parents": [],
                    "confidence": None,
                }
            ],
            "events": [
                {
                    "id": -2,
                    "description": "Conversation between Alice and Bob",
                    "dateTime": "2023-08-01T12:00:00Z",
                    "people": [],
                    "symptom": None,
                    "anxiety": None,
                    "relationship": None,
                    "functioning": None,
                    "confidence": None,
                }
            ],
        },
    }


def test_Diagram_model_dump(database, as_dict):
    assert database.model_dump() == as_dict


def test_from_dict(database, as_dict):
    assert Diagram(**as_dict) == database
