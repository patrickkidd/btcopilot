import btcopilot
from btcopilot.extensions import db
from btcopilot.pro.models import Diagram, User
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.schema import DiagramData
from btcopilot.tests.pro.fdencryptiontestclient import FDEncryptionTestClient
from btcopilot.tests.training.conftest import set_test_session


def test_audit_403(subscriber):
    response = subscriber.get("/training/audit/")
    assert response.status_code == 403


def test_audit_index(auditor, discussion):
    response = auditor.get("/training/audit/")
    assert response.status_code == 200
    assert response.data is not None


def test_audit_index_no_threads(auditor):
    response = auditor.get("/training/audit/")
    assert response.status_code == 200


def test_audit_discussion_without_read_access(flask_app, test_user, test_user_2):
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram.set_diagram_data(DiagramData())
    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.commit()

    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user_2)
    db.session.commit()

    flask_app.test_client_class = FDEncryptionTestClient
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 302


def test_audit_discussion_with_read_access(flask_app, test_user, test_user_2):
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram.set_diagram_data(DiagramData())
    db.session.add(diagram)
    db.session.commit()

    diagram.grant_access(test_user_2, btcopilot.ACCESS_READ_ONLY, _commit=True)

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.commit()

    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user_2)
    db.session.commit()

    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user_2
        with client.session_transaction() as sess:
            set_test_session(sess, test_user_2.id)
        response = client.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200


def test_audit_discussion_admin_bypasses_access_check(
    flask_app, test_user, test_user_2
):
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram.set_diagram_data(DiagramData())
    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.commit()

    test_user_2.roles = btcopilot.ROLE_ADMIN
    db.session.merge(test_user_2)
    db.session.commit()

    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user_2
        with client.session_transaction() as sess:
            set_test_session(sess, test_user_2.id)
        response = client.get(f"/training/discussions/{discussion.id}")
    assert response.status_code == 200


def test_export_discussion_without_read_access(flask_app, test_user, test_user_2):
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram.set_diagram_data(DiagramData())
    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.commit()

    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user_2)
    db.session.commit()

    flask_app.test_client_class = FDEncryptionTestClient
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/training/discussions/{discussion.id}/export")
    assert response.status_code == 302


def test_progress_discussion_without_read_access(flask_app, test_user, test_user_2):
    diagram = Diagram(user_id=test_user.id, name="Test Diagram")
    diagram.set_diagram_data(DiagramData())
    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id, diagram_id=diagram.id, summary="Test discussion"
    )
    db.session.add(discussion)
    db.session.commit()

    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user_2)
    db.session.commit()

    flask_app.test_client_class = FDEncryptionTestClient
    with flask_app.test_client(user=test_user_2) as client:
        response = client.get(f"/training/discussions/{discussion.id}/progress")
    assert response.status_code == 302
