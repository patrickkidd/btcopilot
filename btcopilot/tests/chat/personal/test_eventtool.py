"""What the coach's event tool writes onto the record."""

import pickle

from btcopilot.extensions import db
from btcopilot.personal.recordtext import event_line
from btcopilot.personal.toolbox import ToolName, Toolbox
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
        diagram, kind="shift", date="2019-03-01", person=1, anxiety="up",
        description="Worried after the move",
    )
    changed = _event(diagram, id=added["id"], notes='"I never slept that spring"')
    assert changed["notes"] == '"I never slept that spring"'
    assert len(diagram.get_diagram_data().events) == 1
    assert "I never slept that spring" in event_line(changed)
