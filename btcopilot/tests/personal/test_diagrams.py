import pickle
import base64

from btcopilot.pro.models import Diagram
from btcopilot.schema import DiagramData, PDP, Person, Event, EventKind, asdict
from btcopilot.extensions import db


def test_diagrams_get(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.get(f"/personal/diagrams/{diagram.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == diagram.id
    assert data["version"] == diagram.version
    assert "data" in data
    assert isinstance(data["data"], str)


def test_diagrams_update(subscriber):
    diagram = subscriber.user.free_diagram
    initial_version = diagram.version

    diagram_data = diagram.get_diagram_data()
    diagram_data.lastItemId = 999

    response = subscriber.put(
        f"/personal/diagrams/{diagram.id}",
        json={
            "data": base64.b64encode(pickle.dumps(asdict(diagram_data))).decode("utf-8")
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["version"] == initial_version + 1

    diagram = Diagram.query.get(diagram.id)
    assert diagram.version == initial_version + 1
    assert diagram.get_diagram_data().lastItemId == 999


def test_diagrams_optimistic_locking_success(subscriber):
    diagram = subscriber.user.free_diagram
    initial_version = diagram.version

    diagram_data = diagram.get_diagram_data()
    diagram_data.lastItemId = 123

    response = subscriber.put(
        f"/personal/diagrams/{diagram.id}",
        json={
            "data": base64.b64encode(pickle.dumps(asdict(diagram_data))).decode(
                "utf-8"
            ),
            "expected_version": initial_version,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["version"] == initial_version + 1

    diagram = Diagram.query.get(diagram.id)
    assert diagram.version == initial_version + 1


def test_diagrams_optimistic_locking_conflict(subscriber):
    diagram = subscriber.user.free_diagram
    initial_version = diagram.version

    diagram_data = diagram.get_diagram_data()

    response = subscriber.put(
        f"/personal/diagrams/{diagram.id}",
        json={
            "diagram_data": diagram_data.__dict__,
            "expected_version": initial_version + 999,
        },
    )
    assert response.status_code == 409

    diagram = Diagram.query.get(diagram.id)
    assert diagram.version == initial_version
