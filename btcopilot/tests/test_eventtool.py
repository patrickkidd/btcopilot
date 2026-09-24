"""What the coach's event tool writes onto the record."""

import json
import pickle

import pytest

from btcopilot.extensions import db
from btcopilot.recordtext import event_line, render
from btcopilot.timeline import build_timeline
from btcopilot.models import Author, Change
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas
from btcopilot.models import Diagram
from btcopilot.tests.conftest import version

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
    if "id" in args:
        args["version"] = version(diagram)
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
    assert "(has notes)" in event_line(changed)


def test_notes_are_read_by_tool_not_shown_in_the_record(subscriber):
    # R-0446
    diagram = _diagram(subscriber.user)
    first = _event(
        diagram, kind="noted", date="2019-03-01", person=1, description="Moved",
        notes="Took the job in Tulsa",
    )
    second = _event(
        diagram, kind="noted", date="2020-05-01", person=2, description="Retired",
        notes='"Finally some quiet"',
    )
    _event(diagram, kind="noted", date="2021-01-01", person=1, description="Sold house")
    record = render(diagram.get_diagram_data())
    assert "Tulsa" not in record and "quiet" not in record
    assert record.count("(has notes)") == 2
    tools = Toolbox(diagram.id, "t2")
    one, _ = tools.call(ToolName.ReadNotes.value, {"event": first["id"]})
    assert one.splitlines()[0] == f"{first['id']}: Took the job in Tulsa"
    every, _ = tools.call(ToolName.ReadNotes.value, {})
    assert every.splitlines()[:2] == [
        f"{first['id']}: Took the job in Tulsa",
        f"{second['id']}: \"Finally some quiet\"",
    ]


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


def test_a_birth_adds_the_parents_bond_without_marrying_them(subscriber):
    # R-0445
    diagram = _diagram(
        subscriber.user,
        {"people": FAMILY["people"] + [{"id": 3, "name": "Corinne"}], "lastItemId": 3},
    )
    _event(diagram, kind="birth", date="1990-05-05", person=1, spouse=2, child=3)
    (bond,) = diagram.get_diagram_data().pair_bonds
    assert bond.get("married") is not True


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


def test_an_event_carries_its_end_into_the_record_and_the_picture(subscriber):
    # R-0437
    diagram = _diagram(subscriber.user)
    added = _event(
        diagram,
        kind="shift",
        date="2015-01-01",
        end_date="2019-06-01",
        person=1,
        relationship="cutoff",
        relationship_targets=[2],
        description="Stopped speaking",
    )
    assert added["endDateTime"] == "2019-06-01"
    assert "2015-01-01 to 2019-06-01" in event_line(added)
    [drawn] = build_timeline(diagram.get_diagram_data())["events"]
    assert (drawn["dateTime"], drawn["endDateTime"]) == ("2015-01-01", "2019-06-01")


def test_an_end_before_the_start_is_refused(subscriber):
    # R-0437
    diagram = _diagram(subscriber.user)
    with pytest.raises(ToolError, match="ends before it begins"):
        _event(
            diagram,
            kind="shift",
            date="2019-06-01",
            end_date="2015-01-01",
            person=1,
            anxiety="up",
            description="On edge",
        )


def _edit_event_schema() -> dict:
    tool = next(t for t in schemas() if t["name"] == ToolName.EditEvent.value)
    return tool["input_schema"]["properties"]


def test_the_event_tool_offers_the_two_triangle_moves_and_their_third_people():
    # R-0049
    fields = _edit_event_schema()
    assert {"inside", "outside"} <= set(fields["relationship"]["enum"])
    assert fields["relationship_triangles"]["type"] == "array"


def test_a_triangle_move_keeps_its_third_people_on_the_record(subscriber):
    # R-0049
    data = dict(FAMILY, people=FAMILY["people"] + [{"id": 3, "name": "Ines"}], lastItemId=3)
    diagram = _diagram(subscriber.user, data)
    added = _event(
        diagram,
        kind="shift",
        date="2012-01-15",
        person=1,
        relationship="inside",
        relationship_targets=[2],
        relationship_triangles=[3],
        description="Sided with her against him",
    )
    assert added["relationship"] == "inside"
    assert added["relationshipTriangles"] == [3]
    assert "relationship=inside targets=[2] triangles=[3]" in event_line(added)


def test_the_event_tool_has_a_notes_field_beside_the_description():
    # R-0431
    fields = _edit_event_schema()
    assert fields["notes"]["type"] == "string"
    assert fields["description"]["type"] == "string"


def test_saying_a_recorded_shift_again_is_refused_and_points_at_the_event(subscriber):
    # R-0442
    diagram = _diagram(subscriber.user)
    first = _event(
        diagram, kind="shift", date="2019-03-01", person=1, anxiety="up",
        description="Worried after the move",
    )
    with pytest.raises(ToolError, match=rf"edit_event\(id={first['id']}\)"):
        _event(
            diagram, kind="shift", date="2019-03-01", person=1, anxiety="up",
            description="Anxious that spring",
        )
    assert len(diagram.get_diagram_data().events) == 1


def test_a_re_mention_changes_the_recorded_shift_in_place(subscriber):
    # R-0442
    diagram = _diagram(subscriber.user)
    first = _event(
        diagram, kind="shift", date="2019-03-01", person=1, anxiety="up",
        description="Worried after the move",
    )
    changed = _event(
        diagram, id=first["id"], description="Worried after the move to Tulsa",
        notes="Could not sleep for weeks",
    )
    events = diagram.get_diagram_data().events
    assert [e["id"] for e in events] == [first["id"]]
    assert changed["description"] == "Worried after the move to Tulsa"
    assert changed["notes"] == "Could not sleep for weeks"


def test_a_correction_changes_the_record_at_once_with_nothing_held_pending(subscriber):
    # R-0086
    diagram = _diagram(subscriber.user)
    added = _event(
        diagram, kind="shift", date="2019-03-01", person=1, anxiety="up",
        description="Worried after the move",
    )
    Toolbox(diagram.id, "t2").call(
        ToolName.EditEvent.value,
        {"id": added["id"], "date": "2018-03-01", "version": version(diagram)},
    )
    data = diagram.get_diagram_data()
    assert data.events[0]["dateTime"] == "2018-03-01"
    assert (data.pdp.people, data.pdp.events, data.pdp.pair_bonds) == ([], [], [])
    changes = Change.query.filter_by(diagram_id=diagram.id).order_by(Change.id).all()
    assert [(c.turn_id, c.author) for c in changes] == [
        ("t1", Author.Coach),
        ("t2", Author.Coach),
    ]



def test_moved_is_not_an_event_kind_the_coach_can_write(subscriber):
    # R-0364
    diagram = _diagram(subscriber.user)
    with pytest.raises(ValueError, match="moved"):
        _event(diagram, kind="moved", date="2019-03-01", person=1, description="moved to Arizona")
    assert diagram.get_diagram_data().events == []
    kinds = next(s for s in schemas() if s["name"] == ToolName.EditEvent.value)
    assert "moved" not in kinds["input_schema"]["properties"]["kind"]["enum"]
