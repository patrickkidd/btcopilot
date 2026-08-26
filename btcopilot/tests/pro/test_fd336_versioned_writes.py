"""FD-336 item 3: every server-side write bumps the row version, so a client
holding the pre-write snapshot conflicts instead of silently clobbering it."""

import pickle
from datetime import datetime

import PyQt5.sip  # noqa: F401  required for pickling QtCore objects

from btcopilot.extensions import db


def _put(client, diagram_id, blob, expected_version):
    return client.put(
        f"/v1/diagrams/{diagram_id}",
        data=pickle.dumps(
            {
                "data": blob,
                "updated_at": datetime.utcnow(),
                "expected_version": expected_version,
            }
        ),
    )


def _server_side_write(diagram, last_item_id):
    diagram_data = diagram.get_diagram_data()
    diagram_data.lastItemId = last_item_id
    diagram.set_diagram_data(diagram_data)
    db.session.commit()


def test_set_diagram_data_increments_version_once_per_call(flask_app, test_user):
    diagram = test_user.free_diagram
    start = diagram.version
    diagram_data = diagram.get_diagram_data()

    diagram.set_diagram_data(diagram_data)
    db.session.commit()
    assert diagram.version == start + 1

    diagram.set_diagram_data(diagram_data)
    db.session.commit()
    assert diagram.version == start + 2


def test_stale_client_save_conflicts_after_a_server_side_write(flask_app, test_user):
    diagram = test_user.free_diagram
    stale_version = diagram.version
    _server_side_write(diagram, 42)

    with flask_app.test_client(user=test_user) as client:
        response = _put(client, diagram.id, diagram.data, stale_version)
    assert response.status_code == 409


def test_current_client_save_succeeds_after_a_server_side_write(flask_app, test_user):
    diagram = test_user.free_diagram
    _server_side_write(diagram, 42)

    with flask_app.test_client(user=test_user) as client:
        response = _put(client, diagram.id, diagram.data, diagram.version)
    assert response.status_code == 200
