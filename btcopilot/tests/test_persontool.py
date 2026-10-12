"""What the coach's person tool writes onto the record."""

import pickle

from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.tests.conftest import version
from btcopilot.toolbox import ToolName, Toolbox


def _diagram(user, data=None) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(
        data
        or {
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


def _imported(**bond) -> dict:
    """A new account's nameless stand-in for the person, beside the people an
    import brought in, none of them marked as the person."""
    return {
        "people": [
            {"id": 1, "name": "User", "primary": True},
            {"id": 2, "name": "Delphine", "gender": "female"},
        ],
        "pair_bonds": [{"id": 4, "person_a": 1, "person_b": 2, "married": False}] if bond else [],
        "events": [
            {"id": 3, "kind": "noted", "person": 1, "title": "Moved to Fairbanks", "description": "Moved to Fairbanks", "dateTime": "2025-03-01", "dateCertainty": "approximate"}
        ],
        "questions": [
            {"id": "q1", "kind": "fact", "text": "Which of these people is you?", "state": "held", "item_kind": "person", "item_id": 1}
        ],
        "lastItemId": 4 if bond else 3,
    }


def test_marking_the_user_joins_the_nameless_stand_in_into_them(subscriber):
    # R-0871, R-0879
    diagram = _diagram(subscriber.user, _imported())
    text, _ = Toolbox(diagram.id, "t1").call(
        ToolName.EditPerson.value, {"id": 2, "primary": True, "version": version(diagram)}
    )
    data = diagram.get_diagram_data()
    assert [(p["id"], p["name"], p.get("primary")) for p in data.people] == [(2, "Delphine", True)]
    assert [e["person"] for e in data.events] == [2]
    assert [q["item_id"] for q in data.questions] == [2]
    assert text.splitlines()[-1] == "Joined 1 User into them."


def test_a_stand_in_the_merge_would_refuse_only_loses_the_mark(subscriber):
    # R-0871, R-0879
    people = _edit(_diagram(subscriber.user, _imported(bond=True)), id=2, primary=True)
    assert (people[2]["primary"], people[1]["primary"]) == (True, False)


def test_one_undo_puts_back_the_stand_in_and_the_mark(subscriber):
    # R-0871, R-0879
    diagram = _diagram(subscriber.user, _imported())
    _edit(diagram, id=2, primary=True)
    Toolbox(diagram.id, "t2").call(ToolName.Undo.value, {})
    db.session.expire_all()
    data = diagram.get_diagram_data()
    assert sorted((p["id"], p["name"], bool(p.get("primary"))) for p in data.people) == [
        (1, "User", True),
        (2, "Delphine", False),
    ]
    assert ([e["person"] for e in data.events], [q["item_id"] for q in data.questions]) == ([1], [1])


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
