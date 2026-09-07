import datetime
import re

import flask.testing
import pytest

import btcopilot
from btcopilot.companion.seed import seed_diagram_data
from btcopilot.extensions import db
from btcopilot.personal.models import (
    Discussion,
    InteractionKind,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.personal.routes.interactions import recent
from btcopilot.schema import Event, EventKind, ItemKind
from btcopilot.tests.personal.conftest import csrf_token


@pytest.fixture(autouse=True)
def no_auto_auth(monkeypatch):
    monkeypatch.delenv("FLASK_AUTO_AUTH_USER", raising=False)


def test_page_loads(web):
    """The page is the built web bundle: the picture, the composer, and the
    menu that holds the timeline."""
    response = web.get("/companion/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert 'id="view"' in page
    assert 'id="composer"' in page
    assert 'id="menu-open"' in page
    assert 'id="menu-screen"' in page
    assert "/companion/static/web/app.js" in page


def test_page_carries_what_only_the_server_knows(web, test_user):
    """The bundle is static; the CSRF token, the diagram and the session the
    user returns to are injected into it."""
    page = web.get("/companion/").get_data(as_text=True)
    assert 'name="csrf-token"' in page
    assert f'"diagram_id": {test_user.free_diagram_id}' in page
    assert "window.COMPANION=" in page


def test_page_requires_login(flask_app):
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        response = client.get("/companion/")
        assert response.status_code == 302
        assert "/training/auth/login" in response.headers["Location"]


def test_timeline_shows_own_data_only(web, test_user):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    token = csrf_token(web)
    data = web.get("/companion/timeline").get_json()
    assert {p["id"] for p in data["people"]} == {1, 2, 3, 4, 5, 6, 7}
    assert {b["id"] for b in data["pair_bonds"]} == {8, 9}


def test_timeline_empty_for_user_without_diagram(flask_app, test_user_2):
    test_user_2.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user_2)
    db.session.commit()
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        with client.session_transaction() as sess:
            sess["user_id"] = test_user_2.id
            sess["logged_in_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        data = client.get("/companion/timeline").get_json()
        assert data["people"] == []
        assert data["lanes"] == []


@pytest.mark.chat_flow(response="a coach reply")
def test_chat_round_trip(web, test_user):
    token = csrf_token(web)
    response = web.post(
        "/companion/chat",
        json={"statement": "hello there"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    assert response.get_json()["statement"] == "a coach reply"

    discussion = Discussion.query.filter_by(user_id=test_user.id).one()
    assert discussion.diagram_id == test_user.free_diagram_id
    statements = (
        Statement.query.filter_by(discussion_id=discussion.id)
        .order_by(Statement.order)
        .all()
    )
    assert [s.text for s in statements] == ["hello there", "a coach reply"]
    assert statements[0].speaker.type == SpeakerType.Subject
    assert statements[1].speaker.type == SpeakerType.Expert


@pytest.mark.chat_flow
def test_chat_reuses_discussion(web, test_user):
    token = csrf_token(web)
    first = web.post(
        "/companion/chat", json={"statement": "one"}, headers={"X-CSRFToken": token}
    ).get_json()
    second = web.post(
        "/companion/chat", json={"statement": "two"}, headers={"X-CSRFToken": token}
    ).get_json()
    assert first["discussion_id"] == second["discussion_id"]
    assert Discussion.query.count() == 1


def test_chat_rejects_missing_csrf(web):
    response = web.post("/companion/chat", json={"statement": "forged"})
    assert response.status_code == 400
    assert Statement.query.count() == 0


def test_chat_rejects_bad_csrf(web):
    response = web.post(
        "/companion/chat",
        json={"statement": "forged"},
        headers={"X-CSRFToken": "not-a-real-token"},
    )
    assert response.status_code == 400


def test_personal_hmac_not_bridged_by_session(flask_app, test_user):
    """A session cookie must never authenticate /personal/* — HMAC only."""
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["logged_in_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        response = client.get("/personal/discussions/")
        assert response.status_code == 401


def _make_discussion(test_user, order):
    discussion = Discussion(
        user_id=test_user.id, diagram_id=test_user.free_diagram_id, summary="t"
    )
    db.session.add(discussion)
    db.session.flush()
    speaker = Speaker(
        discussion_id=discussion.id, name="Client", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()
    statement = Statement(
        discussion_id=discussion.id, speaker_id=speaker.id, text="hi", order=order
    )
    db.session.add(statement)
    db.session.commit()
    return discussion


def test_extraction_status_chat_ahead(web, test_user):
    _make_discussion(test_user, order=3)
    data = web.get("/companion/timeline").get_json()
    assert data["extraction"] == {"state": "chat_ahead", "up_to_date": False}


def test_extraction_status_current(web, test_user):
    discussion = _make_discussion(test_user, order=3)
    discussion.extracted_through_order = 3
    db.session.commit()
    data = web.get("/companion/timeline").get_json()
    assert data["extraction"] == {"state": "current", "up_to_date": True}


def test_extraction_status_extracting(web, test_user):
    discussion = _make_discussion(test_user, order=3)
    discussion.extracting = True
    db.session.commit()
    data = web.get("/companion/timeline").get_json()
    assert data["extraction"] == {"state": "extracting", "up_to_date": False}


def test_extraction_status_pending_review(web, test_user):
    discussion = _make_discussion(test_user, order=3)
    discussion.extracted_through_order = 3
    diagram = test_user.free_diagram
    diagram_data = diagram.get_diagram_data()
    diagram_data.pdp.events.append(
        Event(id=-1, kind=EventKind.Shift, person=1, description="staged")
    )
    diagram.set_diagram_data(diagram_data)
    db.session.commit()
    data = web.get("/companion/timeline").get_json()
    assert data["extraction"] == {"state": "pending_review", "up_to_date": False}


def test_pwa_files_are_served_from_the_app_root(web):
    """The service worker has to answer from /companion/ or its scope cannot
    cover the app."""
    assert web.get("/companion/sw.js").status_code == 200
    assert web.get("/companion/manifest.webmanifest").status_code == 200


def test_a_tap_is_recorded_against_the_diagram(web, test_user):
    """The page runs on a session cookie, so it cannot reach /personal/, which
    is signed by the native apps. It writes to the same store through here."""
    token = csrf_token(web)
    response = web.post(
        "/companion/interactions",
        json={
            "diagram_id": test_user.free_diagram_id,
            "kind": InteractionKind.Look.value,
            "item_kind": ItemKind.Cluster.value,
            "item_id": "ch0",
        },
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 201
    stored = recent(test_user.free_diagram_id)
    assert [(i.kind, i.item_kind, i.item_id) for i in stored] == [
        (InteractionKind.Look, ItemKind.Cluster, "ch0")
    ]


def test_play_names_the_cluster_events_in_date_order(web, test_user):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    chapter = web.get("/companion/timeline").get_json()["chapters"][0]
    token = csrf_token(web)

    reply = web.post(
        "/companion/play",
        json={"cluster_id": chapter["id"]},
        headers={"X-CSRFToken": token},
    ).get_json()
    assert reply["cluster_id"] == chapter["id"]
    cited = [int(i) for i in re.findall(r"\[\[events:(\d+)\|", reply["statement"])]
    assert cited == chapter["event_ids"]


def test_play_refuses_a_cluster_that_is_not_on_the_line(web, test_user):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    token = csrf_token(web)

    response = web.post(
        "/companion/play",
        json={"cluster_id": "nope"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 400
