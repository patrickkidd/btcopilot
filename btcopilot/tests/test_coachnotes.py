"""The coach's own notes each turn: kept on the thread, read back next turn,
and seen only by admins and auditors (R-0520).

Invented names only.
"""

import json

import pytest

import btcopilot
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
    monkeypatch.setattr("btcopilot.coachturn.CoachModel", lambda *a, **k: model)
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


def test_the_notes_are_kept_and_read_back_next_turn(web, family, monkeypatch):
    # R-0520
    body = noted(web, monkeypatch, btcopilot.ROLE_SUBSCRIBER)
    kept = [e.payload for e in TurnEvent.query.filter_by(turn_id=body["turn_id"])]
    assert any(e.get("name") == ToolName.CoachNotes and e["args"] == NOTES for e in kept)
    assert family.get_diagram_data().people == [asdict(Person(id=1, name="Wren"))]

    next_turn = coach(monkeypatch, Model(said("And your father?")))
    post(web, "She moved away.")
    uses = [
        block
        for message in next_turn.histories[0]
        if isinstance(message["content"], list)
        for block in message["content"]
        if block.get("type") == "tool_use"
    ]
    assert uses[0]["name"] == ToolName.CoachNotes
    assert uses[0]["input"] == NOTES


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
