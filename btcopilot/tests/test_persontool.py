"""What the coach's person tool writes onto the record."""

import pickle

from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.tests.conftest import version
from btcopilot.toolbox import ToolName, Toolbox


def _diagram(user) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(
        {
            "people": [
                {"id": 1, "name": "Marcus", "gender": "male", "primary": True},
                {"id": 2, "name": "Delphine", "gender": "female"},
            ],
            "lastItemId": 2,
        }
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _edit(diagram, **args) -> dict[int, dict]:
    Toolbox(diagram.id, "t1").call(
        ToolName.EditPerson.value, dict(args, version=version(diagram))
    )
    return {p["id"]: p for p in diagram.get_diagram_data().people}


def test_marking_the_user_takes_the_mark_off_anyone_else(subscriber):
    # R-0879
    people = _edit(_diagram(subscriber.user), id=2, primary=True)
    assert people[2]["primary"] is True
    assert not people[1]["primary"]


def test_every_kept_attribute_can_be_changed(subscriber):
    # R-0881
    people = _edit(
        _diagram(subscriber.user),
        id=2,
        notes="Worked nights at the mill",
        middle_name="Rose",
        nickname="Del",
        birth_name="Aubert",
        alias="D",
    )
    assert {
        k: people[2][k] for k in ("notes", "middleName", "nickName", "birthName", "alias")
    } == {
        "notes": "Worked nights at the mill",
        "middleName": "Rose",
        "nickName": "Del",
        "birthName": "Aubert",
        "alias": "D",
    }
