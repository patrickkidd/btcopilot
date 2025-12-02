import pickle
import base64

import btcopilot
from btcopilot.pro.models import Diagram
from btcopilot.schema import DiagramData, PDP, Person, Event, EventKind, asdict
from btcopilot.extensions import db


def test_create_diagram(subscriber):
    response = subscriber.post("/personal/diagrams/", json={"name": "My New Diagram"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert "diagram" in data
    assert data["diagram"]["name"] == "My New Diagram"
    assert "id" in data["diagram"]
    assert "version" in data["diagram"]

    diagram_id = data["diagram"]["id"]
    diagram = Diagram.query.get(diagram_id)
    assert diagram is not None
    assert diagram.name == "My New Diagram"
    assert diagram.user_id == subscriber.user.id
    assert diagram.version == 1

    diagram_data = diagram.get_diagram_data()
    assert len(diagram_data.people) == 2
    assert diagram_data.people[0]["name"] == "User"
    assert diagram_data.people[1]["name"] == "Assistant"


def test_create_diagram_missing_name(subscriber):
    response = subscriber.post("/personal/diagrams/", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_create_diagram_empty_name(subscriber):
    response = subscriber.post("/personal/diagrams/", json={"name": "  "})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data


def test_list_diagrams(subscriber):
    diagram = subscriber.user.free_diagram

    response = subscriber.get("/personal/diagrams/")
    assert response.status_code == 200
    data = response.get_json()
    assert "diagrams" in data
    assert len(data["diagrams"]) >= 1
    diagram_ids = [d["id"] for d in data["diagrams"]]
    assert diagram.id in diagram_ids
    for d in data["diagrams"]:
        assert "id" in d
        assert "name" in d
        assert "version" in d


def test_list_includes_shared(subscriber, test_user_2):
    owned_diagram = subscriber.user.free_diagram
    test_user_2.set_free_diagram(pickle.dumps({}))
    db.session.commit()
    shared_diagram = test_user_2.free_diagram
    shared_diagram.grant_access(subscriber.user, btcopilot.ACCESS_READ_WRITE)
    db.session.commit()

    response = subscriber.get("/personal/diagrams/")
    assert response.status_code == 200
    data = response.get_json()
    diagram_ids = [d["id"] for d in data["diagrams"]]
    assert owned_diagram.id in diagram_ids
    assert shared_diagram.id in diagram_ids


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
            "data": base64.b64encode(pickle.dumps(asdict(diagram_data))).decode(
                "utf-8"
            ),
            "expected_version": initial_version + 999,
        },
    )
    assert response.status_code == 409

    diagram = Diagram.query.get(diagram.id)
    assert diagram.version == initial_version
