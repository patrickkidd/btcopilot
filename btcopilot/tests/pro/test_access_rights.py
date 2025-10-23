import pickle

import pytest

import vedana
from btcopilot.pro.models import User, Diagram


@pytest.mark.access_rights
def test_access_right_create(flask_app, test_session, test_user, test_user_2):
    test_user_id = test_user.id
    test_user_2_id = test_user_2.id

    bdata = pickle.dumps(
        {
            "diagram_id": test_user.free_diagram.id,
            "user_id": test_user_2.id,
            "right": vedana.ACCESS_READ_ONLY,
            "session": test_session.token,
        }
    )
    with flask_app.test_client(user=test_user) as client:
        response = client.post("/v1/access_rights", data=bdata)
    test_user = User.query.get(test_user_id)
    test_user_2 = User.query.get(test_user_2_id)
    assert response.status_code == 200
    assert test_user.free_diagram.check_read_access(test_user_2) == True


@pytest.mark.access_rights
def test_access_right_update(flask_app, test_session, test_user, test_user_2):
    test_user_id = test_user.id
    test_user_2_id = test_user_2.id

    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_WRITE)
    free_diagram = Diagram.query.get(test_user.free_diagram_id)
    assert free_diagram.access_rights[0].right == vedana.ACCESS_READ_WRITE

    access_right = test_user.free_diagram.access_rights[0]
    with flask_app.test_client(user=test_user) as client:
        response = client.patch(
            f"/v1/access_rights/{access_right.id}",
            data=pickle.dumps(
                {"right": vedana.ACCESS_READ_ONLY, "session": test_session.token}
            ),
        )
    test_user = User.query.get(test_user_id)
    test_user_2 = User.query.get(test_user_2_id)
    assert response.status_code == 200
    assert test_user.free_diagram.access_rights[0].right == vedana.ACCESS_READ_ONLY


@pytest.mark.access_rights
def test_access_right_delete(flask_app, test_session, test_user, test_user_2):
    test_user_id = test_user.id
    test_user_2_id = test_user_2.id

    test_user.free_diagram.grant_access(test_user_2, vedana.ACCESS_READ_WRITE)
    access_right = Diagram.query.get(test_user.free_diagram_id).access_rights[0]
    bdata = pickle.dumps({"session": test_session.token})
    with flask_app.test_client(user=test_user) as client:
        response = client.delete(f"/v1/access_rights/{access_right.id}", data=bdata)
    test_user = User.query.get(test_user_id)
    test_user_2 = User.query.get(test_user_2_id)
    assert response.status_code == 200
    assert test_user.free_diagram.check_read_access(test_user_2) == False
