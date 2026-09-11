"""Personal app REST surface: sessions, preferences, account, event CRUD."""

import datetime

import pytest

import btcopilot
from btcopilot import diagramjson
from btcopilot.personal.routes.settings import PLAN_PLACEHOLDER
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement
from btcopilot.pro.models import Diagram, License, Policy
from btcopilot.pro.models.license import LicenseStatus
from btcopilot.pro.models.preferences import ChatMode, PrefKey, Proactive, Theme
from btcopilot.schema import (
    Cluster,
    DateCertainty,
    DiagramData,
    EventKind,
    Person,
    RelationshipKind,
    TraceKey,
    VariableShift,
    asdict,
)
from btcopilot.tests.personal.conftest import csrf_token


@pytest.fixture(autouse=True)
def no_auto_auth(monkeypatch):
    monkeypatch.delenv("FLASK_AUTO_AUTH_USER", raising=False)


@pytest.fixture
def token(web):
    return csrf_token(web)


@pytest.fixture
def family(test_user):
    """Three people to hang events on. Invented names only."""
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [
        asdict(Person(id=1, name="Wren")),
        asdict(Person(id=2, name="Bo")),
        asdict(Person(id=3, name="Nell")),
    ]
    data.lastItemId = 3
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def post(web, token, url, body):
    return web.post(url, json=body, headers={"X-CSRFToken": token})


def patch(web, token, url, body):
    return web.patch(url, json=body, headers={"X-CSRFToken": token})


# ── sessions ────────────────────────────────────────────────────────────────


@pytest.mark.chat_flow(response="a coach reply", title="Sleep and the move")
def test_session_auto_titled_after_first_exchange(web, token, test_user):
    post(web, token, "/personal/chat", {"statement": "hello"})

    discussion = Discussion.query.one()
    assert discussion.title == "Sleep and the move"


@pytest.mark.chat_flow(title="Sleep and the move")
def test_session_title_kept_after_later_exchanges(web, token):
    post(web, token, "/personal/chat", {"statement": "one"})
    Discussion.query.one().update(title="Hand written")
    db.session.commit()
    post(web, token, "/personal/chat", {"statement": "two"})

    assert Discussion.query.one().title == "Hand written"


@pytest.mark.chat_flow
def test_session_list(web, token):
    post(web, token, "/personal/chat", {"statement": "hello"})

    sessions = web.get("/personal/sessions").get_json()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["summary"]
    assert sessions[0]["last_activity"]


def test_session_list_omits_a_transcript_import(web, token, test_user):
    """A discussion brought in from a recording has no chat speaker ids and
    is not a session the chat app can open."""
    imported = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        summary="Induction transcript",
    )
    db.session.add(imported)
    db.session.commit()

    assert web.get("/personal/sessions").get_json() == []
    assert web.get(f"/personal/sessions/{imported.id}").status_code == 404


def test_session_create(web, token, test_user):
    response = post(web, token, "/personal/sessions", {})
    assert response.status_code == 201
    assert response.get_json()["message_count"] == 0
    assert Discussion.query.one().diagram_id == test_user.free_diagram_id


@pytest.mark.chat_flow
def test_session_switch_by_last_activity(web, token):
    first = post(web, token, "/personal/chat", {"statement": "one"}).get_json()
    second = post(web, token, "/personal/sessions", {}).get_json()
    post(
        web,
        token,
        f"/personal/sessions/{first['discussion_id']}/statements",
        {"statement": "back to the first"},
    )

    listed = web.get("/personal/sessions").get_json()
    assert [s["id"] for s in listed] == [first["discussion_id"], second["id"]]


@pytest.mark.chat_flow(response="a coach reply")
def test_session_statements(web, token):
    created = post(web, token, "/personal/chat", {"statement": "hello"}).get_json()

    session = web.get(f"/personal/sessions/{created['discussion_id']}").get_json()
    assert [(s["role"], s["text"]) for s in session["statements"]] == [
        ("user", "hello"),
        ("coach", "a coach reply"),
    ]


def test_session_rename(web, token):
    created = post(web, token, "/personal/sessions", {}).get_json()

    renamed = patch(
        web, token, f"/personal/sessions/{created['id']}", {"title": "The move"}
    )
    assert renamed.get_json()["title"] == "The move"
    assert db.session.get(Discussion, created["id"]).title == "The move"


@pytest.mark.chat_flow(response="a coach reply")
def test_session_delete_keeps_the_record(web, token, test_user):
    created = post(web, token, "/personal/chat", {"statement": "hello"}).get_json()
    events = len(test_user.free_diagram.get_diagram_data().events)

    response = web.delete(
        f"/personal/sessions/{created['discussion_id']}", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 204
    assert db.session.get(Discussion, created["discussion_id"]) is None
    assert len(test_user.free_diagram.get_diagram_data().events) == events


def test_session_delete_of_another_user_is_not_found(web, token, test_user_2):
    other = Discussion(user_id=test_user_2.id, summary="theirs")
    db.session.add(other)
    db.session.commit()

    response = web.delete(
        f"/personal/sessions/{other.id}", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 404
    assert db.session.get(Discussion, other.id) is not None


def test_session_rename_rejects_unknown_field(web, token):
    created = post(web, token, "/personal/sessions", {}).get_json()

    response = patch(
        web, token, f"/personal/sessions/{created['id']}", {"summary": "x"}
    )
    assert response.status_code == 400


def test_chat_requires_json(web, token):
    response = web.post("/personal/chat", data="hello", headers={"X-CSRFToken": token})
    assert response.status_code == 415


def test_session_of_another_user_is_not_found(web, token, test_user_2):
    other = Discussion(user_id=test_user_2.id, summary="theirs")
    db.session.add(other)
    db.session.commit()

    assert web.get(f"/personal/sessions/{other.id}").status_code == 404


# ── chips ───────────────────────────────────────────────────────────────────
@pytest.mark.chat_flow(
    response="That sits in [[event:10|two winters]], with [[person:1|Wren]]."
)
def test_chat_keeps_the_chips_the_record_resolves(web, token, family):
    """Chips are the primitive (R-0072): they live in the words the page
    renders. Three kinds only — event, cluster, person."""
    data = family.get_diagram_data()
    data.events = [
        {
            "id": 10,
            "kind": EventKind.Shift.value,
            "person": 1,
            "dateTime": "2010-03-01",
        }
    ]
    family.set_diagram_data(data)
    db.session.commit()

    body = post(web, token, "/personal/chat", {"statement": "hi"}).get_json()
    assert body["statement"] == (
        "That sits in [[event:10|two winters]], with [[person:1|Wren]]."
    )

    stored = Statement.query.order_by(Statement.order).all()[-1]
    assert stored.text == body["statement"]


@pytest.mark.chat_flow(response="I mean [[person:99|someone]].")
def test_a_chip_pointing_at_nothing_becomes_its_own_words(web, token, family):
    body = post(web, token, "/personal/chat", {"statement": "hi"}).get_json()
    assert body["statement"] == "I mean someone."



@pytest.fixture
def dated(family):
    """Two dated events and a cluster over them, so there is a cluster to aim at."""
    data = family.get_diagram_data()
    data.events = [
        {
            "id": 10,
            "kind": EventKind.Shift.value,
            "person": 1,
            "dateTime": "2010-03-01",
        },
        {
            "id": 11,
            "kind": EventKind.Shift.value,
            "person": 1,
            "dateTime": "2010-06-01",
        },
    ]
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="A run",
                summary="",
                eventIds=[10, 11],
                startDate="2010-03-01",
            )
        )
    ]
    data.lastItemId = 11
    family.set_diagram_data(data)
    db.session.commit()
    return family


def test_clusters_survive_a_server_side_write(dated):
    """The cluster chip aims at a stored cluster, so a server write that keeps
    events but drops clusters would silently kill it."""
    data = dated.get_diagram_data()
    data.events[0]["description"] = "edited"
    dated.set_diagram_data(data)
    db.session.commit()
    assert [c["id"] for c in dated.get_diagram_data().clusters] == ["c1"]

@pytest.mark.chat_flow(response="That cluster: [[cluster:c1|the run]].")
def test_a_cluster_chip_survives_when_the_record_holds_it(web, token, dated):
    body = post(web, token, "/personal/chat", {"statement": "hi"}).get_json()
    assert body["statement"] == "That cluster: [[cluster:c1|the run]]."


@pytest.mark.chat_flow(response="Off the line: [[cluster:c9|elsewhere]].")
def test_a_cluster_chip_the_record_does_not_hold_is_dropped(web, token, dated):
    body = post(web, token, "/personal/chat", {"statement": "hi"}).get_json()
    assert body["statement"] == "Off the line: elsewhere."


@pytest.mark.chat_flow(response="An undated one: [[event:12|that]].")
def test_a_chip_may_name_an_undated_event(web, token, dated):
    """The old chip mechanism could only aim at the drawn line, so an undated
    event was dropped. A chip is a reference into the record, and the record
    holds undated events."""
    data = dated.get_diagram_data()
    data.events = data.events + [
        {"id": 12, "kind": EventKind.Shift.value, "person": 1, "dateTime": None}
    ]
    dated.set_diagram_data(data)
    db.session.commit()

    body = post(web, token, "/personal/chat", {"statement": "hi"}).get_json()
    assert body["statement"] == "An undated one: [[event:12|that]]."



# ── preferences ─────────────────────────────────────────────────────────────


def test_preferences_defaults(web, test_user):
    body = web.get("/personal/preferences").get_json()
    assert body == {
        PrefKey.Speak.value: False,
        PrefKey.Proactive.value: Proactive.Never.value,
        PrefKey.Mode.value: ChatMode.Text.value,
        PrefKey.Theme.value: Theme.System.value,
        "first_name": test_user.first_name,
        "last_name": test_user.last_name,
        "birthdate": None,
    }


def test_preferences_round_trip(web, token, test_user):
    body = patch(
        web,
        token,
        "/personal/preferences",
        {
            PrefKey.Speak.value: True,
            PrefKey.Theme.value: Theme.Dark.value,
            "first_name": "Wren",
            "birthdate": "1984-02-29",
        },
    ).get_json()
    assert body[PrefKey.Speak.value] is True
    assert body[PrefKey.Theme.value] == Theme.Dark.value
    assert body["birthdate"] == "1984-02-29"

    assert test_user.pref(PrefKey.Theme) is Theme.Dark
    assert test_user.birthdate == datetime.date(1984, 2, 29)
    assert web.get("/personal/preferences").get_json()["first_name"] == "Wren"


def test_preferences_rejects_unknown_key(web, token):
    assert (
        patch(web, token, "/personal/preferences", {"colour": "blue"}).status_code
        == 400
    )


def test_preferences_rejects_bad_value(web, token):
    response = patch(
        web, token, "/personal/preferences", {PrefKey.Theme.value: "aubergine"}
    )
    assert response.status_code == 400


# ── account ─────────────────────────────────────────────────────────────────


def test_account(web, test_user):
    policy = Policy(code="beta", name="Beta")
    db.session.add(policy)
    db.session.flush()
    db.session.add(License(user_id=test_user.id, policy_id=policy.id, active=True))
    db.session.commit()

    body = web.get("/personal/account").get_json()
    assert body["email"] == test_user.username
    assert body["plan"] == PLAN_PLACEHOLDER
    assert body["sign_in_method"] == "password"
    assert [l["policy"] for l in body["licenses"]] == ["Beta"]
    assert body["licenses"][0]["status"] == LicenseStatus.Active.value
    assert test_user.free_diagram_id in [d["id"] for d in body["diagrams"]]


def test_account_license_status_follows_the_license(web, test_user):
    policy = Policy(code="beta", name="Beta")
    db.session.add(policy)
    db.session.flush()
    db.session.add(
        License(user_id=test_user.id, policy_id=policy.id, active=True, canceled=True)
    )
    db.session.commit()

    body = web.get("/personal/account").get_json()
    assert body["licenses"][0]["status"] == LicenseStatus.Canceled.value


# ── diagram access ──────────────────────────────────────────────────────────


def test_read_only_grant_is_not_listed_or_writable(web, token, test_user, test_user_2):
    shared = Diagram(
        user_id=test_user_2.id, name="Shared Family", data=diagramjson.dumps({})
    )
    db.session.add(shared)
    db.session.commit()
    shared.grant_access(test_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    listed = web.get("/personal/diagrams").get_json()
    assert shared.id not in {d["id"] for d in listed}

    response = post(web, token, f"/personal/diagrams/{shared.id}/select", {})
    assert response.status_code == 404
    assert test_user.current_diagram_id is None

    # Force the app onto the read-only diagram the way a stale current_diagram_id
    # would, bypassing the switcher, and confirm the writing routes still refuse.
    test_user.current_diagram_id = shared.id
    db.session.commit()

    assert post(web, token, "/personal/people", {"name": "Nova"}).status_code == 403
    assert shared.get_diagram_data().people == []


# ── event CRUD ──────────────────────────────────────────────────────────────


SHIFT = {
    "kind": EventKind.Shift.value,
    "person": 1,
    "description": "Sleep got worse",
    "dateTime": "2019-04-02",
    "dateCertainty": DateCertainty.Approximate.value,
    "symptom": VariableShift.Up.value,
    "relationship": RelationshipKind.Conflict.value,
    "relationshipTargets": [2],
}


def test_event_round_trip(web, token, family):
    created = post(web, token, "/personal/events", SHIFT)
    assert created.status_code == 201
    event = created.get_json()
    assert event["id"] > 0
    assert event["dateTime"] == "2019-04-02"
    assert event["relationshipTargets"] == [2]

    read = web.get("/personal/timeline").get_json()
    assert [p["event_id"] for lane in read["lanes"] for p in lane["points"]] == [
        event["id"]
    ]

    updated = patch(
        web,
        token,
        f"/personal/events/{event['id']}",
        {"description": "Sleep improved", "symptom": VariableShift.Down.value},
    ).get_json()
    assert updated["description"] == "Sleep improved"
    assert updated["symptom"] == VariableShift.Down.value
    assert updated["dateTime"] == "2019-04-02"

    assert (
        web.delete(
            f"/personal/events/{event['id']}", headers={"X-CSRFToken": token}
        ).status_code
        == 204
    )
    assert family.get_diagram_data().events == []


def test_event_write_takes_the_diagram_lock(web, token, family):
    before = family.version
    post(web, token, "/personal/events", SHIFT)
    db.session.refresh(family)
    assert family.version == before + 1


def test_event_variables_dropped_when_kind_is_not_shift(web, token, family):
    event = post(
        web, token, "/personal/events", dict(SHIFT, kind=EventKind.Death.value)
    ).get_json()
    assert event["symptom"] is None
    assert event["relationship"] is None
    assert event["relationshipTargets"] == []


def test_event_switching_kind_drops_the_shift_values(web, token, family):
    event = post(web, token, "/personal/events", SHIFT).get_json()

    updated = patch(
        web,
        token,
        f"/personal/events/{event['id']}",
        {"kind": EventKind.Death.value},
    ).get_json()
    assert updated["symptom"] is None
    assert updated["relationship"] is None
    assert updated["relationshipTargets"] == []


def test_event_targets_dropped_without_a_relationship(web, token, family):
    body = dict(SHIFT)
    del body["relationship"]
    event = post(web, token, "/personal/events", body).get_json()
    assert event["relationshipTargets"] == []


def test_event_triangles_kept_only_for_inside_and_outside(web, token, family):
    conflict = post(
        web,
        token,
        "/personal/events",
        dict(SHIFT, relationshipTriangles=[3]),
    ).get_json()
    assert conflict["relationshipTriangles"] == []

    inside = post(
        web,
        token,
        "/personal/events",
        dict(
            SHIFT,
            relationship=RelationshipKind.Inside.value,
            relationshipTriangles=[3],
        ),
    ).get_json()
    assert inside["relationshipTriangles"] == [3]


def test_event_rejects_unknown_field(web, token, family):
    response = post(web, token, "/personal/events", dict(SHIFT, mood="blue"))
    assert response.status_code == 400
    assert b"mood" in response.get_data()


def test_event_rejects_unknown_person(web, token, family):
    response = post(web, token, "/personal/events", dict(SHIFT, person=99))
    assert response.status_code == 400


def test_event_rejects_bad_kind(web, token, family):
    assert (
        post(web, token, "/personal/events", dict(SHIFT, kind="wedding")).status_code
        == 400
    )


def test_event_of_missing_id_is_404(web, token, family):
    assert (
        patch(web, token, "/personal/events/404", {"description": "x"}).status_code
        == 404
    )


# ── traceability ────────────────────────────────────────────────────────────


def test_timeline_reports_where_an_event_was_coded(web, family):
    data = family.get_diagram_data()
    data.events = [
        {
            "id": 10,
            "kind": EventKind.Shift.value,
            "person": 1,
            "dateTime": "2019-04-02",
            "symptom": VariableShift.Up.value,
        }
    ]
    data.stamp_event_source([10], discussion_id=77)
    family.set_diagram_data(data)
    db.session.commit()

    body = web.get("/personal/timeline").get_json()
    assert body["coded_in"] == {"10": {"discussion_id": 77, "statement_id": None}}


def test_timeline_omits_events_never_traced(web, family):
    data = family.get_diagram_data()
    data.events = [
        {
            "id": 10,
            "kind": EventKind.Shift.value,
            "person": 1,
            "dateTime": "2010-03-01",
        }
    ]
    family.set_diagram_data(data)
    db.session.commit()

    assert web.get("/personal/timeline").get_json()["coded_in"] == {}
