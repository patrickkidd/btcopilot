import datetime
import re

import flask.testing
import pytest

import btcopilot
from btcopilot.seed import seed_diagram_data
from btcopilot.extensions import db
from btcopilot.models import (
    Discussion,
    InteractionKind,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
)
from btcopilot.interactions import recent
from btcopilot.schema import Event, EventKind, ItemKind
from btcopilot.case import Tool
from btcopilot.tests.conftest import Model, called, csrf_token, replied, said


@pytest.fixture(autouse=True)
def no_auto_auth(monkeypatch):
    monkeypatch.delenv("FLASK_AUTO_AUTH_USER", raising=False)


def test_health_reports_the_version(flask_app):
    # R-0419
    assert flask_app.test_client().get("/health").get_data(as_text=True) == btcopilot.__version__


def test_page_is_asked_for_again_on_every_load(web):
    # R-0486
    response = web.get("/app/")
    assert response.headers["Cache-Control"] == "no-cache"


def test_version_is_the_release_the_server_runs(web):
    # R-0486
    response = web.get("/app/version")
    assert response.get_json() == {"version": btcopilot.__version__}
    assert response.headers["Cache-Control"] == "no-cache"


def test_version_needs_no_sign_in(flask_app):
    # R-0486
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        response = client.get("/app/version")
        assert response.status_code == 200
        assert response.get_json() == {"version": btcopilot.__version__}


def test_page_requires_login(flask_app):
    # R-0080
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        response = client.get("/app/")
        assert response.status_code == 302
        assert "/app/login" in response.headers["Location"]


def test_timeline_shows_own_data_only(web, test_user):
    # R-0080
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    token = csrf_token(web)
    data = web.get("/app/timeline").get_json()
    assert {p["id"] for p in data["people"]} == {1, 3, 4, 5, 6, 7}
    assert {b["id"] for b in data["pair_bonds"]} == {8, 9}


def test_timeline_empty_for_user_without_diagram(flask_app, test_user_2):
    # R-0080
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
        data = client.get("/app/timeline").get_json()
        assert data["people"] == []
        assert data["lanes"] == []


@pytest.mark.chat_flow(response="a coach reply")
def test_chat_round_trip(web, test_user):
    # R-0019
    token = csrf_token(web)
    response = web.post(
        "/app/chat",
        json={"statement": "hello there"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 202
    assert replied(response)["statement"] == "a coach reply"

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
    # R-0466
    token = csrf_token(web)
    first = web.post(
        "/app/chat", json={"statement": "one"}, headers={"X-CSRFToken": token}
    ).get_json()
    second = web.post(
        "/app/chat", json={"statement": "two"}, headers={"X-CSRFToken": token}
    ).get_json()
    assert first["discussion_id"] == second["discussion_id"]
    assert Discussion.query.count() == 1


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


def test_the_timeline_says_nothing_about_extraction(web, test_user):
    # R-0203
    """The picture is written by the coach as it talks, so there is no cursor
    behind the conversation to report and no badge saying so."""
    _make_discussion(test_user, order=3)
    assert "extraction" not in web.get("/app/timeline").get_json()


def test_pwa_files_are_served_from_the_app_root(web):
    # R-0226
    """The service worker has to answer from /app/ or its scope cannot
    cover the app."""
    assert web.get("/app/sw.js").status_code == 200
    assert web.get("/app/manifest.webmanifest").status_code == 200


def test_a_tap_is_recorded_against_the_diagram(web, test_user):
    # R-0077
    """The page runs on a session cookie, so it cannot reach /app/, which
    is signed by the native apps. It writes to the same store through here."""
    token = csrf_token(web)
    response = web.post(
        "/app/interactions",
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


def test_a_tap_that_names_no_item_kind_is_refused_in_words(web, test_user):
    # R-0453
    response = web.post(
        "/app/interactions",
        json={
            "diagram_id": test_user.free_diagram_id,
            "kind": InteractionKind.ChipTap.value,
            "statement_id": 7,
        },
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert response.status_code == 400
    assert "chip_tap tap on statement 7" in response.get_data(as_text=True)


def test_play_hands_the_coach_the_cluster_events_and_returns_the_told_case(
    web, test_user, monkeypatch
):
    # R-0074, R-0563
    """The coach picks and words the snapshots; the events it may name are the
    cluster's, handed to it in date order."""
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    timeline = web.get("/app/timeline").get_json()
    cluster = timeline["clusters"][0]
    dated = {e["id"]: e["dateTime"][:10] for e in timeline["events"] if e["dateTime"]}
    one_a_day = {dated[i]: i for i in reversed(cluster["event_ids"])}
    picked = sorted(one_a_day.items())[:6]
    ids = [i for _, i in picked]
    model = Model(
        called(
            Tool.PlayByPlay,
            cluster_id=cluster["id"],
            point="One thing followed another.",
            snapshots=[
                {"date": date, "event_ids": [i], "fact": f"Fact {i}."} for date, i in picked
            ],
            question="Who else was there?",
        )
    )
    monkeypatch.setattr("btcopilot.playturn.CoachModel", lambda *a, **k: model)
    reply = web.post(
        "/app/play",
        json={"cluster_id": cluster["id"]},
        headers={"X-CSRFToken": csrf_token(web)},
    ).get_json()
    assert reply["cluster_id"] == cluster["id"]
    assert [s["event_ids"] for s in reply["case"]["snapshots"]] == [[i] for i in ids]
    handed = model.histories[0][-1]["content"]
    assert all(str(i) in handed for i in cluster["event_ids"])

    session = web.get("/app/sessions").get_json()[0]["id"]
    thread = web.get(f"/app/sessions/{session}").get_json()["statements"]
    assert (thread[-1]["kind"], thread[-1]["cluster_id"], thread[-1]["case"]) == (
        StatementKind.Play.value,
        cluster["id"],
        reply["case"],
    )


def test_play_refuses_a_cluster_that_is_not_on_the_line(web, test_user):
    # R-0075
    diagram = test_user.free_diagram
    diagram.set_diagram_data(seed_diagram_data())
    db.session.commit()
    token = csrf_token(web)

    response = web.post(
        "/app/play",
        json={"cluster_id": "nope"},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 400
