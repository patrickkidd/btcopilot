"""A new item named by a handle, so its events go in the same reply."""

import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas


@pytest.fixture
def diagram(subscriber):
    made = Diagram(user_id=subscriber.user.id, name="Record")
    made.data = pickle.dumps({"people": [], "lastItemId": 0})
    db.session.add(made)
    db.session.commit()
    return made


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("COACH_HANDLES", "1")


def _edit_event_schema() -> dict:
    return next(s for s in schemas() if s["name"] == ToolName.EditEvent.value)


def test_a_new_persons_birth_names_them_by_handle(diagram, on):
    # ruling pending: Patrick's decision on handles, coach-fewer-calls experiment
    tools = Toolbox(diagram.id, "t1")
    tools.call(ToolName.EditPerson.value, {"name": "Ada", "handle": "a"})
    tools.call(
        ToolName.EditEvent.value,
        {"kind": "birth", "child": "a", "date": "1990-01-01", "date_certainty": "certain"},
    )
    data = diagram.get_diagram_data()
    assert data.events[-1]["child"] == data.people[0]["id"]


def test_an_unknown_handle_is_refused_and_nothing_written(diagram, on):
    # ruling pending: Patrick's decision on handles, coach-fewer-calls experiment
    with pytest.raises(ToolError) as refused:
        Toolbox(diagram.id, "t1").call(
            ToolName.EditEvent.value,
            {"kind": "birth", "child": "zz", "date": "1990-01-01", "date_certainty": "certain"},
        )
    assert str(refused.value) == (
        "no new item named 'zz' in this reply; add it first, in an earlier tool "
        "call of the same reply"
    )
    assert diagram.get_diagram_data().events == []


def test_a_handle_with_an_id_is_refused(diagram, on):
    # ruling pending: Patrick's decision on handles, coach-fewer-calls experiment
    with pytest.raises(ToolError) as refused:
        Toolbox(diagram.id, "t1").call(
            ToolName.EditPerson.value, {"id": 7, "version": 1, "name": "Ada", "handle": "a"}
        )
    assert str(refused.value) == "handle is only for a new item; this one already has id 7"


def test_off_the_event_tool_has_no_handle_and_integer_ids(monkeypatch):
    # ruling pending: Patrick's decision on handles, coach-fewer-calls experiment
    monkeypatch.delenv("COACH_HANDLES", raising=False)
    props = _edit_event_schema()["input_schema"]["properties"]
    assert "handle" not in props
    assert props["person"]["type"] == "integer"
