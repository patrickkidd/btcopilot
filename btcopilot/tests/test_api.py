"""Personal app REST surface: sessions, preferences, account, event CRUD."""

import datetime

import pytest

import btcopilot
from btcopilot import diagramjson
from btcopilot.routes.settings import PLAN_PLACEHOLDER
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Discussion, Interaction, Statement
from btcopilot.models.interaction import InteractionKind
from btcopilot.models import Diagram, License, Policy
from btcopilot.models.license import LicenseStatus
from btcopilot.models.preferences import ChatMode, PrefKey, Proactive, Theme
from btcopilot.schema import (
    Cluster,
    DateCertainty,
    DiagramData,
    EventKind,
    ItemKind,
    Person,
    RelationshipKind,
    TraceKey,
    VariableShift,
    asdict,
)
from btcopilot.tests.conftest import csrf_token, replied, version
from btcopilot.toolbox import ToolName, Toolbox


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
    # R-0097
    post(web, token, "/app/chat", {"statement": "hello"})

    discussion = Discussion.query.one()
    assert discussion.title == "Sleep and the move"


@pytest.mark.chat_flow(title="Sleep and the move")
def test_session_title_kept_after_later_exchanges(web, token):
    # R-0097
    post(web, token, "/app/chat", {"statement": "one"})
    Discussion.query.one().update(title="Hand written")
    db.session.commit()
    post(web, token, "/app/chat", {"statement": "two"})

    assert Discussion.query.one().title == "Hand written"


@pytest.mark.chat_flow
def test_session_list(web, token):
    # R-0097
    post(web, token, "/app/chat", {"statement": "hello"})

    sessions = web.get("/app/sessions").get_json()
    assert len(sessions) == 1
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["summary"]
    assert sessions[0]["last_activity"]


def test_session_create(web, token, test_user):
    # R-0285
    response = post(web, token, "/app/sessions", {})
    assert response.status_code == 201
    assert response.get_json()["message_count"] == 0
    assert Discussion.query.one().diagram_id == test_user.free_diagram_id


@pytest.mark.chat_flow
def test_session_switch_by_last_activity(web, token):
    # R-0347
    first = post(web, token, "/app/chat", {"statement": "one"}).get_json()
    second = post(web, token, "/app/sessions", {}).get_json()
    post(
        web,
        token,
        f"/app/sessions/{first['discussion_id']}/statements",
        {"statement": "back to the first"},
    )

    listed = web.get("/app/sessions").get_json()
    assert [s["id"] for s in listed] == [first["discussion_id"], second["id"]]


@pytest.mark.chat_flow(response="a coach reply")
def test_session_statements(web, token):
    # R-0016
    created = post(web, token, "/app/chat", {"statement": "hello"}).get_json()

    session = web.get(f"/app/sessions/{created['discussion_id']}").get_json()
    assert [(s["role"], s["text"]) for s in session["statements"]] == [
        ("user", "hello"),
        ("coach", "a coach reply"),
    ]


def test_session_rename(web, token):
    # R-0097
    created = post(web, token, "/app/sessions", {}).get_json()

    renamed = patch(
        web, token, f"/app/sessions/{created['id']}", {"title": "The move"}
    )
    assert renamed.get_json()["title"] == "The move"
    assert db.session.get(Discussion, created["id"]).title == "The move"


@pytest.mark.chat_flow(response="a coach reply")
def test_session_delete_keeps_the_record(web, token, test_user):
    # R-0019
    created = post(web, token, "/app/chat", {"statement": "hello"}).get_json()
    events = len(test_user.free_diagram.get_diagram_data().events)

    response = web.delete(
        f"/app/sessions/{created['discussion_id']}", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 204
    assert db.session.get(Discussion, created["discussion_id"]) is None
    assert len(test_user.free_diagram.get_diagram_data().events) == events


@pytest.mark.chat_flow(response="a coach reply")
def test_session_delete_keeps_the_edits_its_words_made(
    web, token, test_user, foreign_keys
):
    # R-0019
    created = post(web, token, "/app/chat", {"statement": "hello"}).get_json()
    said = Statement.query.filter_by(discussion_id=created["discussion_id"]).first()
    change = Change(
        diagram_id=test_user.free_diagram_id,
        statement_id=said.id,
        turn_id="t1",
        author=Author.Coach,
        deltas=[],
    )
    look = Interaction(
        diagram_id=test_user.free_diagram_id,
        statement_id=said.id,
        kind=InteractionKind.Look,
        item_kind=ItemKind.Person,
    )
    db.session.add_all([change, look])
    db.session.commit()

    response = web.delete(
        f"/app/sessions/{created['discussion_id']}", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 204
    db.session.expire_all()
    assert (change.statement_id, look.statement_id) == (None, None)


def test_session_delete_of_another_user_is_not_found(web, token, test_user_2):
    # R-0080
    other = Discussion(user_id=test_user_2.id, summary="theirs")
    db.session.add(other)
    db.session.commit()

    response = web.delete(
        f"/app/sessions/{other.id}", headers={"X-CSRFToken": token}
    )
    assert response.status_code == 404
    assert db.session.get(Discussion, other.id) is not None


def test_session_rename_rejects_unknown_field(web, token):
    # R-0453
    created = post(web, token, "/app/sessions", {}).get_json()

    response = patch(
        web, token, f"/app/sessions/{created['id']}", {"summary": "x"}
    )
    assert response.status_code == 400


def test_chat_requires_json(web, token):
    # R-0453
    response = web.post("/app/chat", data="hello", headers={"X-CSRFToken": token})
    assert response.status_code == 415


def test_session_of_another_user_is_not_found(web, token, test_user_2):
    # R-0080
    other = Discussion(user_id=test_user_2.id, summary="theirs")
    db.session.add(other)
    db.session.commit()

    assert web.get(f"/app/sessions/{other.id}").status_code == 404


# ── chips ───────────────────────────────────────────────────────────────────
@pytest.mark.chat_flow(
    response="That sits in [[event:10|two winters]], with [[person:1|Wren]]."
)
def test_chat_keeps_the_chips_the_record_resolves(web, token, family):
    # R-0072, R-0085
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

    body = replied(post(web, token, "/app/chat", {"statement": "hi"}))
    assert body["statement"] == (
        "That sits in [[event:10|two winters]], with [[person:1|Wren]]."
    )

    stored = Statement.query.order_by(Statement.order).all()[-1]
    assert stored.text == body["statement"]


@pytest.mark.chat_flow(response="I mean [[person:99|someone]].")
def test_a_chip_pointing_at_nothing_becomes_its_own_words(web, token, family):
    # R-0085
    body = replied(post(web, token, "/app/chat", {"statement": "hi"}))
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
    # R-0076
    """The cluster chip aims at a stored cluster, so a server write that keeps
    events but drops clusters would silently kill it."""
    data = dated.get_diagram_data()
    data.events[0]["description"] = "edited"
    dated.set_diagram_data(data)
    db.session.commit()
    assert [c["id"] for c in dated.get_diagram_data().clusters] == ["c1"]

@pytest.mark.chat_flow(response="That cluster: [[cluster:c1|the run]].")
def test_a_cluster_chip_survives_when_the_record_holds_it(web, token, dated):
    # R-0072, R-0085
    body = replied(post(web, token, "/app/chat", {"statement": "hi"}))
    assert body["statement"] == "That cluster: [[cluster:c1|the run]]."


@pytest.mark.chat_flow(response="Off the line: [[cluster:c9|elsewhere]].")
def test_a_cluster_chip_the_record_does_not_hold_is_dropped(web, token, dated):
    # R-0085
    body = replied(post(web, token, "/app/chat", {"statement": "hi"}))
    assert body["statement"] == "Off the line: elsewhere."


@pytest.mark.chat_flow(response="An undated one: [[event:12|that]].")
def test_a_chip_may_name_an_undated_event(web, token, dated):
    # R-0072
    """The old chip mechanism could only aim at the drawn line, so an undated
    event was dropped. A chip is a reference into the record, and the record
    holds undated events."""
    data = dated.get_diagram_data()
    data.events = data.events + [
        {"id": 12, "kind": EventKind.Shift.value, "person": 1, "dateTime": None}
    ]
    dated.set_diagram_data(data)
    db.session.commit()

    body = replied(post(web, token, "/app/chat", {"statement": "hi"}))
    assert body["statement"] == "An undated one: [[event:12|that]]."


# ── preferences ─────────────────────────────────────────────────────────────


def test_preferences_defaults(web, test_user):
    # R-0099, R-0017
    body = web.get("/app/preferences").get_json()
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
    # R-0099
    body = patch(
        web,
        token,
        "/app/preferences",
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
    assert web.get("/app/preferences").get_json()["first_name"] == "Wren"


def test_preferences_rejects_unknown_key(web, token):
    # R-0453
    assert (
        patch(web, token, "/app/preferences", {"colour": "blue"}).status_code
        == 400
    )


def test_preferences_rejects_bad_value(web, token):
    # R-0453
    response = patch(
        web, token, "/app/preferences", {PrefKey.Theme.value: "aubergine"}
    )
    assert response.status_code == 400


# ── account ─────────────────────────────────────────────────────────────────


def test_account(web, test_user):
    # R-0100
    policy = Policy(code="beta", name="Beta")
    db.session.add(policy)
    db.session.flush()
    db.session.add(License(user_id=test_user.id, policy_id=policy.id, active=True))
    db.session.commit()

    body = web.get("/app/account").get_json()
    assert body["email"] == test_user.username
    assert body["plan"] == PLAN_PLACEHOLDER
    assert body["sign_in_method"] == "password"
    assert [l["policy"] for l in body["licenses"]] == ["Beta"]
    assert body["licenses"][0]["status"] == LicenseStatus.Active.value
    assert test_user.free_diagram_id in [d["id"] for d in body["diagrams"]]


def test_account_license_status_follows_the_license(web, test_user):
    # R-0100
    policy = Policy(code="beta", name="Beta")
    db.session.add(policy)
    db.session.flush()
    db.session.add(
        License(user_id=test_user.id, policy_id=policy.id, active=True, canceled=True)
    )
    db.session.commit()

    body = web.get("/app/account").get_json()
    assert body["licenses"][0]["status"] == LicenseStatus.Canceled.value


# ── diagram access ──────────────────────────────────────────────────────────


def test_read_only_grant_is_not_listed_or_writable(web, token, test_user, test_user_2):
    # R-0080
    shared = Diagram(
        user_id=test_user_2.id, name="Shared Family", data=diagramjson.dumps({})
    )
    db.session.add(shared)
    db.session.commit()
    shared.grant_access(test_user, btcopilot.ACCESS_READ_ONLY, _commit=True)

    listed = web.get("/app/diagrams").get_json()
    assert shared.id not in {d["id"] for d in listed}

    response = post(web, token, f"/app/diagrams/{shared.id}/select", {})
    assert response.status_code == 404
    assert test_user.current_diagram_id is None

    # Force the app onto the read-only diagram the way a stale current_diagram_id
    # would, bypassing the switcher, and confirm the writing routes still refuse.
    test_user.current_diagram_id = shared.id
    db.session.commit()

    assert post(web, token, "/app/people", {"name": "Nova"}).status_code == 403
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
    # R-0141
    created = post(web, token, "/app/events", SHIFT)
    assert created.status_code == 201
    event = created.get_json()
    assert event["id"] > 0
    assert event["dateTime"] == "2019-04-02"
    assert event["relationshipTargets"] == [2]

    read = web.get("/app/timeline").get_json()
    assert [p["event_id"] for lane in read["lanes"] for p in lane["points"]] == [
        event["id"]
    ]

    updated = patch(
        web,
        token,
        f"/app/events/{event['id']}",
        {"description": "Sleep improved", "symptom": VariableShift.Down.value},
    ).get_json()
    assert updated["description"] == "Sleep improved"
    assert updated["symptom"] == VariableShift.Down.value
    assert updated["dateTime"] == "2019-04-02"

    assert (
        web.delete(
            f"/app/events/{event['id']}", headers={"X-CSRFToken": token}
        ).status_code
        == 204
    )
    assert family.get_diagram_data().events == []


def test_a_named_record_takes_the_write_and_a_stranger_s_does_not(
    web, token, family, test_user, test_user_2
):
    # R-0080
    """The coding screen writes onto the record its coding is of, which it names
    on the request; a record the user may not write is refused."""
    mine = Diagram(user_id=test_user.id, name="Coding", data=diagramjson.dumps({}))
    mine.set_diagram_data(family.get_diagram_data())
    theirs = Diagram(
        user_id=test_user_2.id, name="Theirs", data=diagramjson.dumps({})
    )
    db.session.add_all([mine, theirs])
    db.session.commit()

    created = post(web, token, f"/app/events?diagram_id={mine.id}", SHIFT)
    assert created.status_code == 201
    assert [e["description"] for e in mine.get_diagram_data().events] == [
        "Sleep got worse"
    ]
    assert family.get_diagram_data().events == []

    event_id = created.get_json()["id"]
    assert (
        patch(
            web,
            token,
            f"/app/events/{event_id}?diagram_id={mine.id}",
            {"description": "Sleep improved"},
        ).get_json()["description"]
        == "Sleep improved"
    )
    assert (
        web.delete(
            f"/app/events/{event_id}?diagram_id={mine.id}",
            headers={"X-CSRFToken": token},
        ).status_code
        == 204
    )
    assert mine.get_diagram_data().events == []

    refused = post(web, token, f"/app/people?diagram_id={theirs.id}", {"name": "Nova"})
    assert refused.status_code == 403
    assert theirs.get_diagram_data().people == []


def test_event_write_takes_the_diagram_lock(web, token, family):
    # R-0084
    before = family.version
    post(web, token, "/app/events", SHIFT)
    db.session.refresh(family)
    assert family.version == before + 1


def test_a_hand_edit_of_an_event_is_logged_as_the_users_own_change(
    web, token, family, test_user
):
    # R-0084
    event = post(web, token, "/app/events", SHIFT).get_json()
    last = Change.query.order_by(Change.id.desc()).first().id

    patch(web, token, f"/app/events/{event['id']}", {"description": "Sleep improved"})
    rows = Change.query.filter(Change.id > last).all()
    assert [(r.author, r.user_id, r.version) for r in rows] == [
        (Author.User, test_user.id, version(family))
    ]
    assert [(d["field"], d["before"], d["after"]) for d in rows[0].deltas] == [
        ("description", "Sleep got worse", "Sleep improved")
    ]


def test_the_coach_reads_a_hand_edit_among_the_recent_changes(web, token, family):
    # R-0084
    event = post(web, token, "/app/events", SHIFT).get_json()
    patch(web, token, f"/app/events/{event['id']}", {"description": "Sleep improved"})

    text, _ = Toolbox(family.id, "coach-turn").call(ToolName.ReadChanges.value, {})
    assert text.splitlines()[0] == (
        f'Version {version(family)}, user: event {event["id"]} '
        'description="Sleep improved"'
    )


def test_undo_puts_back_a_hand_edit_of_an_event(web, token, family):
    # R-0084
    event = post(web, token, "/app/events", SHIFT).get_json()
    patch(web, token, f"/app/events/{event['id']}", {"description": "Sleep improved"})

    Toolbox(family.id, "coach-turn").call(ToolName.Undo.value, {})
    db.session.expire_all()
    assert [e["description"] for e in family.get_diagram_data().events] == [
        "Sleep got worse"
    ]


def test_event_variables_dropped_when_kind_is_not_shift(web, token, family):
    # R-0144
    event = post(
        web, token, "/app/events", dict(SHIFT, kind=EventKind.Death.value)
    ).get_json()
    assert event["symptom"] is None
    assert event["relationship"] is None
    assert event["relationshipTargets"] == []


def test_event_switching_kind_drops_the_shift_values(web, token, family):
    # R-0144
    event = post(web, token, "/app/events", SHIFT).get_json()

    updated = patch(
        web,
        token,
        f"/app/events/{event['id']}",
        {"kind": EventKind.Death.value},
    ).get_json()
    assert updated["symptom"] is None
    assert updated["relationship"] is None
    assert updated["relationshipTargets"] == []


def test_event_targets_dropped_without_a_relationship(web, token, family):
    # R-0144
    body = dict(SHIFT)
    del body["relationship"]
    event = post(web, token, "/app/events", body).get_json()
    assert event["relationshipTargets"] == []


def test_event_triangles_kept_only_for_inside_and_outside(web, token, family):
    # R-0144, R-0076
    conflict = post(
        web,
        token,
        "/app/events",
        dict(SHIFT, relationshipTriangles=[3]),
    ).get_json()
    assert conflict["relationshipTriangles"] == []

    inside = post(
        web,
        token,
        "/app/events",
        dict(
            SHIFT,
            relationship=RelationshipKind.Inside.value,
            relationshipTriangles=[3],
        ),
    ).get_json()
    assert inside["relationshipTriangles"] == [3]


def test_event_rejects_unknown_field(web, token, family):
    # R-0453
    response = post(web, token, "/app/events", dict(SHIFT, mood="blue"))
    assert response.status_code == 400
    assert b"mood" in response.get_data()


def test_event_rejects_unknown_person(web, token, family):
    # R-0453
    response = post(web, token, "/app/events", dict(SHIFT, person=99))
    assert response.status_code == 400


def test_event_the_record_refuses_is_told_in_plain_words(web, token, family):
    # R-0453
    response = post(web, token, "/app/events", dict(SHIFT, endDateTime="2019-01-01"))
    assert response.status_code == 400
    assert response.get_data(as_text=True) == "The end date is before the start date."


def test_event_rejects_bad_kind(web, token, family):
    # R-0363
    assert (
        post(web, token, "/app/events", dict(SHIFT, kind="wedding")).status_code
        == 400
    )


def test_event_of_missing_id_is_404(web, token, family):
    # R-0453
    assert (
        patch(web, token, "/app/events/404", {"description": "x"}).status_code
        == 404
    )


# ── traceability ────────────────────────────────────────────────────────────


def test_timeline_reports_where_an_event_was_coded(web, family):
    # R-0140
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

    body = web.get("/app/timeline").get_json()
    assert body["coded_in"] == {"10": {"discussion_id": 77, "statement_id": None}}


def test_timeline_omits_events_never_traced(web, family):
    # R-0140
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

    assert web.get("/app/timeline").get_json()["coded_in"] == {}
