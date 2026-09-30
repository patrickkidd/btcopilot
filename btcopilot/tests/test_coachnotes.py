"""The coach's own notes each turn: kept on the thread, read back next turn
from the stored call in whichever session, and seen only by admins and auditors
(R-0520).

Invented names only.
"""

import json

import pytest

import btcopilot
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import TurnEvent
from btcopilot.schema import Person, asdict
from btcopilot.toolbox import Register, ToolName, Variable, schemas
from btcopilot.turnlog import TurnEventKind
from btcopilot.tests.conftest import Model, called, csrf_token, said

NOTES = {
    "register": Register.Coaching.value,
    "lane": "the mother's side",
    "why": "her mother's move came up twice",
    "holding": "the brother's silence",
    "plateau": {"reached": False, "biggest_gap": "the father's parents"},
    "hunch": "none yet",
    "person": "guarded, warming up",
    "variable": Variable.Anxiety.value,
}


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.models.discussion.response_text_sync",
        lambda *a, **k: "A session title",
    )


@pytest.fixture
def family(test_user):
    diagram = test_user.free_diagram
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Wren"))]
    data.lastItemId = 1
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def coach(monkeypatch, model):
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    return model


def post(web, statement="My sister is Nell."):
    return web.post(
        "/app/chat", json={"statement": statement}, headers={"X-CSRFToken": csrf_token(web)}
    ).get_json()


def noted(web, monkeypatch, roles: str) -> dict:
    web.user.roles = roles
    db.session.commit()
    coach(monkeypatch, Model(called(ToolName.CoachNotes, **NOTES), said("Tell me more.")))
    return post(web)


def streamed(web, turn_id) -> list[dict]:
    body = web.get(f"/app/turns/{turn_id}/events").get_data(as_text=True)
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_the_notes_tool_asks_for_every_field():
    # R-0520
    schema = next(s for s in schemas() if s["name"] == ToolName.CoachNotes)
    assert set(schema["input_schema"]["required"]) == set(NOTES)
    assert schema["input_schema"]["properties"]["register"]["enum"] == [r.value for r in Register]


def test_the_notes_tool_says_evaluation_and_not_journaling():
    # R-0535
    schema = next(s for s in schemas() if s["name"] == ToolName.CoachNotes)
    register = schema["input_schema"]["properties"]["register"]
    assert "evaluation" in register["enum"]
    assert "journaling" not in register["enum"]
    assert "Evaluation is a turn" in register["description"]
    assert "Coaching is ongoing conversation" in register["description"]


def test_the_notes_are_kept_and_read_back_next_turn_in_another_session(
    web, family, monkeypatch, test_user
):
    # R-0520
    body = noted(web, monkeypatch, btcopilot.ROLE_SUBSCRIBER)
    kept = [e.payload for e in TurnEvent.query.filter_by(turn_id=body["turn_id"])]
    assert any(e.get("name") == ToolName.CoachNotes and e["args"] == NOTES for e in kept)
    assert family.get_diagram_data().people == [asdict(Person(id=1, name="Wren"))]

    later = open_session(test_user, family)
    db.session.commit()
    next_turn = coach(monkeypatch, Model(said("And your father?")))
    web.post(
        f"/app/sessions/{later.id}/statements",
        json={"statement": "She moved away."},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    history = next_turn.histories[0]
    assert "tool_use" not in str(history)
    newest = history[-1]["content"][0]["text"]
    assert "YOUR NOTES FROM YOUR LAST TURN, written " in newest
    assert "lane: the mother's side" in newest.splitlines()
    plateau = "plateau: reached=False, biggest_gap=the father's parents"
    assert plateau in newest.splitlines()


def test_a_subscriber_never_receives_the_notes(web, family, monkeypatch):
    # R-0520
    body = noted(web, monkeypatch, btcopilot.ROLE_SUBSCRIBER)
    shown = web.get(f"/app/sessions/{body['discussion_id']}").get_json()["statements"]
    assert shown[1]["tools"] == []

    events = streamed(web, body["turn_id"])
    assert "guarded" not in json.dumps(events)
    assert events[-1]["type"] == TurnEventKind.Done.value


@pytest.mark.parametrize("roles", [btcopilot.ROLE_AUDITOR, btcopilot.ROLE_ADMIN])
def test_an_auditor_or_admin_sees_the_notes(web, family, monkeypatch, roles):
    # R-0520
    body = noted(web, monkeypatch, roles)
    shown = web.get(f"/app/sessions/{body['discussion_id']}").get_json()["statements"]
    assert shown[1]["tools"] == [
        {"name": ToolName.CoachNotes.value, "args": NOTES, "names": {}, "refusal": None}
    ]

    events = streamed(web, body["turn_id"])
    assert events[0]["name"] == ToolName.CoachNotes
    assert events[-1]["events"][0]["args"] == NOTES
