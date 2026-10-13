"""With COACH_REPLY_WITH_EDITS on, words that come with tool calls that all
succeed are the reply, so the turn makes no second model call."""

import pytest

from btcopilot.extensions import db
from btcopilot.models import Statement, StatementKind
from btcopilot.toolbox import ToolName
from btcopilot.schema import Person, asdict
from btcopilot.tests.conftest import Model, called, csrf_token, said, wrote


@pytest.fixture(autouse=True)
def titles(monkeypatch):
    monkeypatch.setattr(
        "btcopilot.metered.response_text_sync",
        lambda *a, **k: wrote("A session title"),
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


def turn(web, monkeypatch, *scripted) -> tuple[Model, str]:
    model = Model(*scripted)
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: model)
    response = web.post(
        "/app/chat",
        json={"statement": "My sister is Nell."},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert response.status_code == 202
    reply = (
        Statement.query.filter_by(kind=StatementKind.Turn)
        .order_by(Statement.id.desc())
        .first()
    )
    return model, reply.text


def names(diagram) -> list[str]:
    return [person["name"] for person in diagram.get_diagram_data().people]


def test_words_with_a_successful_edit_are_the_reply(web, family, monkeypatch):
    # ruling pending: Patrick's decision on the reply call, coach-fewer-calls experiment
    monkeypatch.setenv("COACH_REPLY_WITH_EDITS", "1")
    model, reply = turn(
        web, monkeypatch, called(ToolName.EditPerson, text="Added Nell.", name="Nell")
    )
    assert len(model.systems) == 1
    assert reply == "Added Nell."
    assert "Nell" in names(family)


def test_words_with_a_refused_edit_are_dropped(web, family, monkeypatch):
    # ruling pending: Patrick's decision on the reply call, coach-fewer-calls experiment
    monkeypatch.setenv("COACH_REPLY_WITH_EDITS", "1")
    model, reply = turn(
        web,
        monkeypatch,
        called(
            ToolName.EditEvent,
            text="Noted the headaches.",
            kind="symptom",
            date="2019-03-01",
            date_certainty="certain",
            person=1,
            description="Headaches",
        ),
        said("Tell me about the headaches."),
    )
    assert len(model.systems) == 2
    assert reply == "Tell me about the headaches."


def test_switch_off_keeps_the_closing_call(web, family, monkeypatch):
    # ruling pending: Patrick's decision on the reply call, coach-fewer-calls experiment
    monkeypatch.delenv("COACH_REPLY_WITH_EDITS", raising=False)
    model, reply = turn(
        web,
        monkeypatch,
        called(ToolName.EditPerson, text="Adding Nell.", name="Nell"),
        said("Added Nell."),
    )
    assert len(model.systems) == 2
    assert reply == "Added Nell."
    assert "Nell" in names(family)
