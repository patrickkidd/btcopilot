from datetime import datetime
import pickle
from urllib.parse import quote

import pytest

import vedana
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram

from btcopilot.tests.conftest import TEST_USER_2_ATTRS


def test_diagrams_create(flask_app, test_user):
    with flask_app.test_client(user=test_user) as client:
        response = client.post(
            "/v1/diagrams",
            data=pickle.dumps(
                {"name": "bleh", "data": pickle.dumps({"something": "fake"})}
            ),
        )
    assert response.status_code == 200
    data = pickle.loads(response.data)
    diagram_id = data["id"]

    diagram = Diagram.query.get(diagram_id)
    assert diagram != None
    assert pickle.loads(diagram.data)["something"] == "fake"


def test_diagrams_index_as_anonymous(flask_app):
    with flask_app.test_client() as client:
        response = client.get("/v1/diagrams")
    assert response.status_code == 401


def test_diagrams_index(flask_app, test_user, test_user_2):
    """Only show diagrams that the user has access to."""
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_ONLY)

    # Add own diagram that is not shared
    first_diagram = Diagram(
        data=test_user.free_diagram.data,
        user_id=test_user_2.id,
    )
    db.session.add(first_diagram)
    db.session.merge(first_diagram)

    # Add a diagram that is also shared
    second_diagram = Diagram(
        data=test_user.free_diagram.data,
        user_id=test_user.id,
    )
    db.session.add(second_diagram)
    second_diagram.grant_access(test_user_2, vedana.ACCESS_READ_ONLY)

    # Add a diagram that is NOT shared
    third_diagram = Diagram(
        data=pickle.dumps(test_user.free_diagram.data),
        user_id=test_user.id,
    )
    db.session.add(third_diagram)

    with flask_app.test_client(user=test_user_2) as client:
        response = client.get("/v1/diagrams")
    response_data = pickle.loads(response.data)
    assert type(response_data) == list
    assert len(response_data) == 3
    assert response_data[0]["id"] == test_user.free_diagram.id
    assert response_data[1]["id"] == first_diagram.id
    assert response_data[2]["id"] == second_diagram.id


@pytest.mark.parametrize("user_id_attr", ["username", "id"])
def test_diagrams_get_others_diagrams(flask_app, test_user, test_user_2, user_id_attr):
    test_user.roles = "admin"
    diagram_1 = Diagram(data=pickle.dumps({}), user_id=test_user_2.id)
    diagram_2 = Diagram(data=pickle.dumps({}), user_id=test_user_2.id)
    db.session.add_all([diagram_1, diagram_2])
    db.session.commit()

    if user_id_attr == "username":
        user_id = quote(test_user_2.username)
    else:
        user_id = test_user_2.id
    with flask_app.test_client(user=test_user) as client:
        # give me a url encoded string of test_user_2.username which is an email
        response = client.get(f"/v1/diagrams?user_id={user_id}")
    assert response.status_code == 200
    data = pickle.loads(response.data)
    assert len(data) == 2
    assert data[0]["id"] == diagram_1.id
    assert data[1]["id"] == diagram_2.id


def test_diagrams_get_own_diagram(flask_app, test_user):
    with flask_app.test_client(user=test_user) as client:
        response = client.get(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 200
    pickle.loads(pickle.loads(response.data)["data"])


def test_diagrams_get_others_diagram(flask_app, test_user, test_user_2):
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_ONLY)
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 200
    pickle.loads(pickle.loads(response.data)["data"])


def test_diagrams_get_others_diagram_no_access(flask_app, test_user, test_user_2):
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 401


def test_diagrams_patch_own_diagram(flask_app, test_user):
    with flask_app.test_client(user=test_user) as client:
        response = client.patch(
            f"/v1/diagrams/{test_user.free_diagram_id}",
            data=pickle.dumps(
                {
                    "updated_at": datetime.utcnow(),
                    "data": pickle.dumps({"some": "fake", "data": 123}),
                }
            ),
        )
        assert response.status_code == 200
    bdata = Diagram.query.get(test_user.free_diagram_id).data
    data = pickle.loads(bdata)
    assert data["some"] == "fake"


def test_diagrams_patch_others_diagram_no_access(flask_app, test_user, test_user_2):
    with flask_app.test_client(user=test_user_2) as client:
        response = client.patch(
            f"/v1/diagrams/{test_user.free_diagram_id}", data=pickle.dumps({})
        )
    assert response.status_code == 401


def test_diagrams_patch_others_diagram_read_access(flask_app, test_user, test_user_2):
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_ONLY)
    with flask_app.test_client(user=test_user_2) as client:
        response = client.patch(
            f"/v1/diagrams/{test_user.free_diagram_id}", data=pickle.dumps({})
        )
    assert response.status_code == 401


def test_diagrams_patch_others_diagram(flask_app, test_user, test_user_2):
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_WRITE)
    with flask_app.test_client(user=test_user_2) as client:
        response = client.patch(
            f"/v1/diagrams/{test_user.free_diagram_id}",
            data=pickle.dumps(
                {"updated_at": datetime.utcnow(), "data": pickle.dumps({})}
            ),
        )
    assert response.status_code == 200


def test_diagrams_delete_own_diagram(flask_app, test_user):
    with flask_app.test_client(user=test_user) as client:
        response = client.delete(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 200
    assert Diagram.query.filter_by(user_id=test_user.id).count() == 0


def test_diagrams_delete_others_diagram_no_access(flask_app, test_user, test_user_2):
    with flask_app.test_client(user=test_user_2) as client:
        response = client.delete(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 401
    assert Diagram.query.filter_by(user_id=test_user.id).count() == 1


def test_diagrams_delete_others_diagram_read_access(flask_app, test_user, test_user_2):
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_ONLY)
    with flask_app.test_client(user=test_user_2) as client:
        response = client.delete(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 401
    assert Diagram.query.filter_by(user_id=test_user.id).count() == 1


def test_diagrams_delete_others_diagram(flask_app, test_user, test_user_2):
    db.session.commit()
    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_WRITE)
    db.session.commit()
    with flask_app.test_client(user=test_user) as client:
        response = client.delete(f"/v1/diagrams/{test_user.free_diagram_id}")
    assert response.status_code == 200
    assert Diagram.query.filter_by(user_id=test_user.id).count() == 0


@pytest.mark.skip(reason="Can't remember why this is skipped.")
def test_diagrams_admin(flask_app, test_user):
    test_user.roles = "admin"
    db.session.commit()

    with flask_app.test_client(user=test_user) as client:
        response = client.get("/v1/diagrams")
    data = pickle.loads(response.data)
    assert type(data) == dict


def _test_get_first_diagram(flask_app):
    # mark every other one as shown
    for i, (uuid, entry) in enumerate(flask_app).database.metadata.items():
        if i % 2:
            entry["shown"] = True
    with flask_app.test_client() as client:
        response = client.get("/v1/diagrams")
    data = pickle.loads(response.data)
    assert type(data) == dict
    first = None
    for k, v in data.items():
        first = v
        break
    assert "uuid" in first

    with flask_app.test_client() as client:
        response = client.get("/v1/diagrams/" + first["uuid"])
    data = pickle.loads(response.data)
    assert type(data) == dict
    assert data["uuid"] == first["uuid"]


def _test_get_all_diagramsapp(flask_app):
    with flask_app.test_client() as client:
        response = client.get("/v1/diagrams")
    data = pickle.loads(response.data)
    assert type(data) == dict
    for uuid, entry in data.items():
        with flask_app.test_client() as client:
            response = client.get("/v1/diagrams/" + uuid)
        data = pickle.loads(response.data)
        assert type(data) == dict
        # assert data['uuid'] == uuid


@pytest.mark.skip(reason="Can't remember why this is skipped")
def _test_set_diagram_shown(flask_app, admin_client):
    # index
    with flask_app.test_client() as client:
        response = client.get("/v1/diagrams")
    data = pickle.loads(response.data)
    assert type(data) == dict
    first = None
    for k, v in data.items():
        first = v
        break
    assert "uuid" in first
    # # set (fail)
    bdata = pickle.dumps({})
    shown = not first["shown"]
    set_url = "/v1/diagrams/" + first["uuid"] + "?shown=" + str(shown)
    # with flask_app.test_client() as client:
    #     response = client.patch(set_url, data=bdata)
    # assert response.status_code == 401
    # set (success)
    db.session.commit()
    response = admin_client.patch(set_url, data=bdata)
    data = pickle.loads(response.data)
    assert type(data) == dict
    assert data["uuid"] == first["uuid"]
    assert data["shown"] == shown


# def test_set_diagram_data_doesnt_overwrite_scene(test_user):
#     from btcopilot.schema import DiagramData

#     diagram = Diagram(data=SIP_DIAGRAM, user=test_user)
#     diagram.set_diagram_data(DiagramData())
#     assert b"version\x94\x8c\x051.5.0" in diagram.data
