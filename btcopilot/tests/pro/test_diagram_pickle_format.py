import pickle
import json
import pytest

from btcopilot.pro.models import Diagram
from btcopilot.schema import DiagramData, PDP, PDPDeltas, Person, Event, EventKind


def test_pickle_contains_json_serializable_dicts(db_session, test_user):
    """Verify that diagram pickle contains JSON-serializable dicts, not dataclass instances."""
    diagram = Diagram(name="Test", user_id=test_user.id)
    db_session.add(diagram)
    db_session.flush()

    diagram_data = DiagramData(
        people=[{"id": 1, "name": "Alice", "spouses": []}],
        events=[{"id": 2, "kind": "shift", "person": 1}],
        pdp=PDP(
            people=[Person(id=-1, name="Bob")],
            events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
        ),
        last_id=2,
    )

    diagram.set_diagram_data(diagram_data)

    pickled_data = pickle.loads(diagram.data)

    # Verify all data is JSON-serializable (no dataclass instances)
    try:
        json_str = json.dumps(pickled_data)
        assert json_str is not None
    except (TypeError, ValueError) as e:
        pytest.fail(f"Pickle contains non-JSON-serializable data: {e}")

    # Verify structure
    assert "people" in pickled_data
    assert "events" in pickled_data
    assert "pdp" in pickled_data
    assert "last_id" in pickled_data

    # Verify people/events are dicts
    assert isinstance(pickled_data["people"], list)
    assert len(pickled_data["people"]) == 1
    assert isinstance(pickled_data["people"][0], dict)
    assert pickled_data["people"][0]["name"] == "Alice"

    assert isinstance(pickled_data["events"], list)
    assert len(pickled_data["events"]) == 1
    assert isinstance(pickled_data["events"][0], dict)
    assert pickled_data["events"][0]["kind"] == "shift"

    # Verify PDP is dict
    assert isinstance(pickled_data["pdp"], dict)
    assert isinstance(pickled_data["pdp"]["people"], list)
    assert len(pickled_data["pdp"]["people"]) == 1
    assert isinstance(pickled_data["pdp"]["people"][0], dict)
    assert pickled_data["pdp"]["people"][0]["name"] == "Bob"


def test_get_diagram_data_converts_dicts_to_dataclasses(db_session, test_user):
    """Verify that get_diagram_data converts dicts back to dataclasses."""
    diagram = Diagram(name="Test", user_id=test_user.id)
    db_session.add(diagram)
    db_session.flush()

    # Manually create pickle with dicts
    data = {
        "people": [{"id": 1, "name": "Alice", "spouses": []}],
        "events": [{"id": 2, "kind": "shift", "person": 1}],
        "pdp": {
            "people": [{"id": -1, "name": "Bob", "spouses": []}],
            "events": [{"id": -2, "kind": "shift", "person": -1}],
        },
        "last_id": 2,
    }
    diagram.data = pickle.dumps(data)

    # Read back
    diagram_data = diagram.get_diagram_data()

    # Verify outer people/events are raw dicts
    assert len(diagram_data.people) == 1
    assert isinstance(diagram_data.people[0], dict)
    assert diagram_data.people[0]["name"] == "Alice"

    assert len(diagram_data.events) == 1
    assert isinstance(diagram_data.events[0], dict)
    assert diagram_data.events[0]["kind"] == "shift"

    # Verify PDP is dataclass
    assert isinstance(diagram_data.pdp, PDP)
    assert len(diagram_data.pdp.people) == 1
    assert isinstance(diagram_data.pdp.people[0], Person)
    assert diagram_data.pdp.people[0].name == "Bob"
