import pickle
import json
import pytest

from btcopilot.pro.models import Diagram
from btcopilot.schema import (
    DiagramData,
    PDP,
    PDPDeltas,
    Person,
    Event,
    EventKind,
    asdict,
)


def test_pickle_contains_json_serializable_dicts(db_session, test_user):
    """Verify that diagram pickle contains JSON-serializable dicts, not dataclass instances."""
    diagram = Diagram(name="Test", user_id=test_user.id)
    db_session.add(diagram)
    db_session.flush()

    diagram_data = DiagramData(
        people=[{"id": 1, "name": "Alice"}],
        events=[{"id": 2, "kind": "shift", "person": 1}],
        pdp=PDP(
            people=[Person(id=-1, name="Bob")],
            events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
        ),
        lastItemId=2,
    )

    diagram.set_diagram_data(diagram_data)

    expected = {
        "people": [{"id": 1, "name": "Alice"}],
        "events": [{"id": 2, "kind": "shift", "person": 1}],
        "pdp": {
            "people": [
                {
                    "id": -1,
                    "name": "Bob",
                    "last_name": None,
                    "parents": None,
                    "confidence": None,
                }
            ],
            "events": [
                {
                    "id": -2,
                    "kind": "shift",
                    "person": -1,
                    "spouse": None,
                    "child": None,
                    "description": None,
                    "dateTime": None,
                    "endDateTime": None,
                    "dateCertainty": "certain",
                    "symptom": None,
                    "anxiety": None,
                    "relationship": None,
                    "relationshipTargets": [],
                    "relationshipTriangles": [],
                    "functioning": None,
                    "confidence": None,
                }
            ],
            "pair_bonds": [],
        },
        "lastItemId": 2,
    }

    pickled_data = pickle.loads(diagram.data)

    try:
        json.dumps(pickled_data)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Pickle contains non-JSON-serializable data: {e}")

    assert pickled_data == expected


def test_get_diagram_data_converts_dicts_to_dataclasses(db_session, test_user):
    """Verify that get_diagram_data converts dicts back to dataclasses."""
    diagram = Diagram(name="Test", user_id=test_user.id)
    db_session.add(diagram)
    db_session.flush()

    data = {
        "people": [{"id": 1, "name": "Alice", "spouses": []}],
        "events": [{"id": 2, "kind": "shift", "person": 1}],
        "pdp": {
            "people": [{"id": -1, "name": "Bob", "spouses": []}],
            "events": [{"id": -2, "kind": "shift", "person": -1}],
        },
        "lastItemId": 2,
    }
    diagram.data = pickle.dumps(data)

    expected = DiagramData(
        people=[{"id": 1, "name": "Alice"}],
        events=[{"id": 2, "kind": "shift", "person": 1}],
        pdp=PDP(
            people=[Person(id=-1, name="Bob")],
            events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
        ),
        lastItemId=2,
    )

    diagram_data = diagram.get_diagram_data()

    assert diagram_data.people[0]["id"] == expected.people[0]["id"]
    assert diagram_data.people[0]["name"] == expected.people[0]["name"]
    assert diagram_data.events == expected.events
    assert diagram_data.lastItemId == expected.lastItemId
    assert len(diagram_data.pdp.people) == len(expected.pdp.people)
    assert diagram_data.pdp.people[0].id == expected.pdp.people[0].id
    assert diagram_data.pdp.people[0].name == expected.pdp.people[0].name
