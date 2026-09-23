"""What the coach's event tool writes onto the record."""

import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.personal.recordtext import event_line
from btcopilot.personal.toolbox import ToolError, ToolName, Toolbox
from btcopilot.models import Diagram

FAMILY = {
    "people": [
        {"id": 1, "name": "Marcus", "gender": "male"},
        {"id": 2, "name": "Delphine", "gender": "female"},
    ],
    "lastItemId": 2,
}


def _diagram(user, data: dict | None = None) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(data if data is not None else FAMILY)
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _event(diagram, **args) -> dict:
    Toolbox(diagram.id, "t1").call(ToolName.EditEvent.value, args)
    return diagram.get_diagram_data().events[-1]


def test_notes_fold_into_the_existing_event(subscriber):
    # R-0431
    diagram = _diagram(subscriber.user)
    added = _event(
        diagram,
        kind="shift",
        date="2019-03-01",
        person=1,
        anxiety="up",
        description="Worried after the move",
    )
    changed = _event(diagram, id=added["id"], notes='"I never slept that spring"')
    assert changed["notes"] == '"I never slept that spring"'
    assert len(diagram.get_diagram_data().events) == 1
    assert "I never slept that spring" in event_line(changed)


def test_two_same_day_shifts_on_one_person_land_when_the_variables_differ(subscriber):
    # R-0432
    diagram = _diagram(subscriber.user)
    _event(
        diagram,
        kind="shift",
        date="2019-03-01",
        person=1,
        symptom="up",
        description="Trouble sleeping",
    )
    _event(
        diagram,
        kind="shift",
        date="2019-03-01",
        person=1,
        anxiety="up",
        description="On edge",
    )
    assert len(diagram.get_diagram_data().events) == 2


def test_a_same_day_shift_moving_the_same_variable_is_refused(subscriber):
    # R-0432
    diagram = _diagram(subscriber.user)
    first = _event(
        diagram,
        kind="shift",
        date="2019-03-01",
        person=1,
        symptom="up",
        description="Trouble sleeping",
    )
    with pytest.raises(ToolError, match=f"already event {first['id']}"):
        _event(
            diagram,
            kind="shift",
            date="2019-03-01",
            person=1,
            symptom="up",
            description="Drinking more",
        )
