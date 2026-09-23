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


def test_an_omitted_certainty_is_unknown_and_a_change_leaves_it(subscriber):
    # R-0438
    diagram = _diagram(subscriber.user)
    added = _event(
        diagram,
        kind="shift",
        date="2019-03-01",
        person=1,
        anxiety="up",
        description="On edge",
        date_certainty="approximate",
    )
    changed = _event(diagram, id=added["id"], description="On edge at work")
    assert changed["dateCertainty"] == "approximate"
    guessed = _event(
        diagram,
        kind="shift",
        date="2001-01-01",
        person=2,
        symptom="up",
        description="Back pain",
    )
    assert guessed["dateCertainty"] == "unknown"


def test_a_birth_naming_both_parents_makes_the_child_their_offspring(subscriber):
    # R-0438
    diagram = _diagram(
        subscriber.user,
        {"people": FAMILY["people"] + [{"id": 3, "name": "Corinne"}], "lastItemId": 3},
    )
    _event(diagram, kind="birth", date="1990-05-05", person=1, spouse=2, child=3)
    data = diagram.get_diagram_data()
    assert len(data.pair_bonds) == 1
    assert data.people[2]["parents"] == data.pair_bonds[0]["id"]


def test_a_marriage_sets_married_on_the_couples_bond(subscriber):
    # R-0430
    diagram = _diagram(
        subscriber.user,
        dict(
            FAMILY, pair_bonds=[{"id": 9, "person_a": 1, "person_b": 2}], lastItemId=9
        ),
    )
    _event(diagram, kind="married", date="1988-06-11", person=1, spouse=2)
    assert diagram.get_diagram_data().pair_bonds == [
        {"id": 9, "person_a": 1, "person_b": 2, "married": True}
    ]


def test_a_marriage_with_no_bond_adds_a_married_bond(subscriber):
    # R-0430
    diagram = _diagram(subscriber.user)
    _event(diagram, kind="married", date="1988-06-11", person=1, spouse=2)
    [bond] = diagram.get_diagram_data().pair_bonds
    assert (bond["person_a"], bond["person_b"], bond["married"]) == (1, 2, True)


def test_an_adoption_invents_no_parent(subscriber):
    # R-0430
    diagram = _diagram(
        subscriber.user,
        {"people": FAMILY["people"] + [{"id": 3, "name": "Corinne"}], "lastItemId": 3},
    )
    _event(diagram, kind="adopted", date="1995-01-01", person=2, child=3)
    data = diagram.get_diagram_data()
    assert len(data.people) == 3
    assert data.pair_bonds == []
    assert data.people[2].get("parents") is None
