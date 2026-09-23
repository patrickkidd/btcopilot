"""Who belongs to whom: what the record refuses, and the parent nobody named.

A person is never their own parent or their own partner, a bond is between two
different people, and any two people have one bond ever, because a child is the
offspring of a bond (R-0326). A bond or a birth written with a parent missing
gets that parent as a generically named person (R-0325 rules 9 and 10).
"""

import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.personal import prompts, record
from btcopilot.personal.models import Author
from btcopilot.personal.toolbox import ToolName, Toolbox
from btcopilot.models import Diagram
from btcopilot.schema import ItemKind

FAMILY = {
    "people": [
        {"id": 1, "name": "Marcus", "gender": "male"},
        {"id": 2, "name": "Delphine", "gender": "female"},
        {"id": 3, "name": "Corinne", "gender": "female", "parents": 10},
    ],
    "pair_bonds": [{"id": 10, "person_a": 1, "person_b": 2, "married": True}],
    "lastItemId": 10,
}


def _diagram(user, data: dict | None = None) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(data if data is not None else FAMILY)
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _bond(bond_id, a, b) -> list[dict]:
    return [
        {
            "item_kind": ItemKind.PairBond,
            "item_id": bond_id,
            "field": field,
            "after": value,
        }
        for field, value in (("person_a", a), ("person_b", b))
    ]


def _write(diagram, deltas):
    return record.apply(diagram.id, deltas, author=Author.Coach, turn_id="t1")


def test_a_bond_of_one_person_with_themselves_is_refused(subscriber):
    # no ruling
    diagram = _diagram(subscriber.user)
    with pytest.raises(record.Invalid, match="one person with themselves"):
        _write(diagram, _bond(11, 1, 1))


def test_a_bond_with_one_side_is_refused(subscriber):
    # no ruling
    diagram = _diagram(subscriber.user)
    with pytest.raises(record.Invalid, match="needs two people"):
        _write(
            diagram,
            [
                {
                    "item_kind": ItemKind.PairBond,
                    "item_id": 11,
                    "field": "person_a",
                    "after": 1,
                }
            ],
        )


def test_a_second_bond_between_the_same_two_is_refused(subscriber):
    # R-0326
    diagram = _diagram(subscriber.user)
    with pytest.raises(record.Invalid, match="already have pair bond 10"):
        _write(diagram, _bond(11, 2, 1))


def test_nobody_is_born_to_a_bond_they_are_in(subscriber):
    # no ruling
    diagram = _diagram(subscriber.user)
    with pytest.raises(record.Invalid, match="their own parent"):
        _write(
            diagram,
            [
                {
                    "item_kind": ItemKind.Person,
                    "item_id": 1,
                    "field": "parents",
                    "after": 10,
                }
            ],
        )


def test_a_bond_between_two_different_people_commits(subscriber):
    # no ruling
    diagram = _diagram(subscriber.user)
    _write(diagram, _bond(11, 2, 3))
    assert [b["id"] for b in diagram.get_diagram_data().pair_bonds] == [10, 11]


def _toolbox(diagram) -> Toolbox:
    return Toolbox(diagram.id, "t1")


def test_a_bond_named_on_one_side_gets_the_other_generically(subscriber):
    # R-0325
    diagram = _diagram(
        subscriber.user,
        {"people": [{"id": 1, "name": "Sarah", "gender": "female"}], "lastItemId": 1},
    )
    _toolbox(diagram).call(ToolName.EditPairBond.value, {"person_a": 1})

    data = diagram.get_diagram_data()
    assert [p["name"] for p in data.people] == ["Sarah", "Sarah's partner"]
    assert data.pair_bonds[0]["person_b"] == data.people[1]["id"]


def test_a_birth_naming_one_parent_gets_the_other_generically(subscriber):
    # R-0325
    diagram = _diagram(
        subscriber.user,
        {
            "people": [
                {"id": 1, "name": "Marcus", "gender": "male"},
                {"id": 2, "name": "Sarah", "gender": "female"},
            ],
            "lastItemId": 2,
        },
    )
    _toolbox(diagram).call(
        ToolName.EditEvent.value,
        {"kind": "birth", "date": "1975-04-02", "person": 1, "child": 2},
    )

    data = diagram.get_diagram_data()
    assert [p["name"] for p in data.people][-1] == "Sarah's mother"
    assert data.events[0]["spouse"] == data.people[-1]["id"]


def test_the_generic_name_is_the_overridable_wording():
    # R-0325
    assert prompts.generic_name("Sarah", prompts.Role.Father) == "Sarah's father"
