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
    else:
        args.setdefault("date_certainty", "certain")
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
    # R-0446, R-0649
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
    one, _ = tools.call(
        ToolName.ReadEvents.value, {"ids": [first["id"]], "fields": ["notes"]}
    )
    assert one.splitlines()[1] == "  notes: Took the job in Tulsa"
    every, _ = tools.call(ToolName.ReadEvents.value, {"fields": ["notes"]})
    assert [line for line in every.splitlines() if "notes:" in line] == [
        "  notes: Took the job in Tulsa",
        '  notes: "Finally some quiet"',
    ]


def test_a_wrong_field_is_cleared_and_the_rest_stays(subscriber):
    # R-0533, R-0649
    diagram = _diagram(subscriber.user)
    added = _event(
        diagram, kind="shift", date="2019-03-01", person=1, description="Stopped calling",
        anxiety="up", relationship="distance", relationship_targets=[2],
        location="Tulsa", end_date="2019-06-01",
    )
    changed = _event(
        diagram, id=added["id"],
        clear=["location", "end_date", "relationship", "relationship_targets"],
    )
    assert [changed.get(k) for k in ("location", "endDateTime", "relationship")] == [None] * 3
    assert changed["anxiety"] == "up"
    assert changed["description"] == "Stopped calling"


def test_a_field_both_set_and_cleared_is_refused(subscriber):
    # R-0533
    diagram = _diagram(subscriber.user)
    added = _event(diagram, kind="noted", date="2019-03-01", person=1, description="Moved")
    with pytest.raises(ToolError, match="both set and cleared"):
        _event(diagram, id=added["id"], location="Tulsa", clear=["location"])


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


def test_a_couple_event_with_no_spouse_is_refused_to_the_coach(subscriber):
    # R-0453
    diagram = _diagram(subscriber.user)
    with pytest.raises(ToolError, match="name the other one as spouse") as refused:
        _event(diagram, kind="married", date="2010-06-01", person=1)
    assert refused.value.plain
    assert diagram.get_diagram_data().events == []


def test_a_move_with_no_target_is_refused_to_the_coach_naming_the_rule(subscriber):
    # R-0585
    diagram = _diagram(subscriber.user)
    with pytest.raises(
        ToolError, match="every relationship move names who it was aimed at"
    ) as refused:
        _event(
            diagram,
            kind="shift",
            date="2013-06-01",
            person=1,
            relationship="toward",
            description="Told her about the new plan",
        )
    assert refused.value.plain == "Toward needs the person it was aimed at."
    assert diagram.get_diagram_data().events == []


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


def test_a_date_with_no_certainty_is_refused_and_a_change_leaves_it(subscriber):
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
    for args in (
        {"kind": "shift", "date": "2001-01-01", "person": 2, "symptom": "up", "description": "Back pain"},
        {"id": added["id"], "version": version(diagram), "date": "2019-04-01"},
    ):
        with pytest.raises(ToolError) as refused:
            Toolbox(diagram.id, "t1").call(ToolName.EditEvent.value, args)
        assert refused.value.plain == (
            "Say how sure the date is: certain for an exact day, approximate for a "
            'month or a year only, unknown for "sometime around" or any hedge.'
        )
    assert diagram.get_diagram_data().events[-1]["dateTime"] == "2019-03-01"

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
        {"id": added["id"], "date": "2018-03-01", "date_certainty": "certain", "version": version(diagram)},
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
    with pytest.raises(ToolError, match="'moved' is not one of the event kinds"):
        _event(diagram, kind="moved", date="2019-03-01", person=1, description="moved to Arizona")
    assert diagram.get_diagram_data().events == []
    kinds = next(s for s in schemas() if s["name"] == ToolName.EditEvent.value)
    assert "moved" not in kinds["input_schema"]["properties"]["kind"]["enum"]


RULES = {
    "people": FAMILY["people"]
    + [
        {"id": 3, "name": "Corinne", "parents": 9},
        {"id": 4, "name": "Theo"},
        {"id": 5, "name": "Errol"},
        {"id": 6, "name": "Ivy", "parents": 9},
    ],
    "pair_bonds": [{"id": 9, "person_a": 1, "person_b": 2}],
    "events": [
        {"id": 20, "kind": "birth", "child": 3, "person": 1, "spouse": 2, "dateTime": "1975-01-01"},
        {"id": 21, "kind": "death", "person": 5, "dateTime": "1989-01-01"},
        {"id": 22, "kind": "married", "person": 1, "spouse": 2, "dateTime": "1970-06-01"},
    ],
    "lastItemId": 22,
}
MOVE = {"kind": "shift", "date": "2001-02-03", "person": 1, "description": "Stopped calling"}


@pytest.mark.parametrize(
    "tool, args, match",
    [
        ("edit_event", dict(MOVE, anxiety="sideways"), "'sideways' is not one of the anxiety shifts"),
        ("edit_event", {"kind": "birth", "date": "1980-01-01"}, "is a birth with no child"),
        ("edit_event", {"kind": "death", "date": "1980-01-01"}, "is a death event about nobody"),
        ("edit_event", dict(MOVE, person=77, anxiety="up"), "No person 77 in the record"),
        ("edit_event", {"kind": "married", "date": "1980-01-01", "person": 4, "spouse": 4}, "names person 4 as both person and spouse"),
        ("edit_event", {"kind": "birth", "date": "1980-01-01", "person": 4, "spouse": 5, "child": 4}, "has person 4 as both the child and a parent"),
        ("edit_event", dict(MOVE, relationship="inside", relationship_targets=[2]), "is an inside move with no third person"),
        (
            "edit_event",
            dict(MOVE, relationship="inside", relationship_targets=[2], relationship_triangles=[2]),
            "has person 2 as both a target and the third person",
        ),
        ("edit_event", dict(MOVE, anxiety="up", relationship_targets=[2]), "has relationship_targets but no relationship move"),
        (
            "edit_event",
            dict(MOVE, relationship="distance", relationship_targets=[2], relationship_triangles=[4]),
            "has relationship_triangles but is not an inside or outside move",
        ),
        ("edit_event", dict(MOVE, kind="noted", anxiety="up"), "is a noted event, and only a shift carries"),
        ("edit_event", dict(MOVE, description=None, anxiety="up"), "is a shift event with no words"),
        ("edit_event", dict(MOVE, date="1998", anxiety="up"), "'1998' is not a date"),
        ("edit_event", dict(MOVE, date=None, anxiety="up"), "Every event needs a date"),
        ("edit_event", {"kind": "birth", "date": "1980-01-01", "person": 4, "child": 6}, "names person 4 as a parent of person 6, who is born to pair bond 9"),
        ("edit_event", {"kind": "birth", "date": "1976-01-01", "child": 3}, "person 3 already has a birth, event 20"),
        ("edit_event", {"kind": "death", "date": "1990-01-01", "person": 5}, "person 5 already has a death, event 21"),
        ("edit_person", {"gender": "female"}, "has no name"),
        ("edit_person", {"name": "Gus", "gender": "robot"}, "'robot' is not one of the genders"),
        ("remove", {"item_kind": "pair_bond", "item_id": 9}, "leaves event 22 naming persons 1 and 2 as a couple with no pair bond"),
        ("edit_cluster", {"name": "A", "event_ids": [20, 21, 99]}, "No event 99 in the record"),
    ],
)
def test_a_record_rule_is_refused_to_the_coach_naming_the_rule(subscriber, tool, args, match):
    # R-0593
    diagram = _diagram(subscriber.user, RULES)
    args = {k: v for k, v in args.items() if v is not None}
    if tool == "edit_event":
        args.setdefault("date_certainty", "certain")
    if tool == "remove":
        args["version"] = version(diagram)
    with pytest.raises(ToolError, match=match) as refused:
        Toolbox(diagram.id, "t1").call(tool, args)
    assert refused.value.plain
    data = diagram.get_diagram_data()
    assert (data.events, data.pair_bonds) == (RULES["events"], RULES["pair_bonds"])


def test_a_couple_event_adds_the_couples_bond_first(subscriber):
    # R-0593
    diagram = _diagram(subscriber.user, RULES)
    _event(diagram, kind="divorced", date="1999-01-01", person=4, spouse=5)
    bond = diagram.get_diagram_data().pair_bonds[-1]
    assert (bond["person_a"], bond["person_b"], bond.get("married")) == (4, 5, None)


def test_a_birth_with_one_parent_takes_the_other_from_the_childs_parents(subscriber):
    # R-0593
    diagram = _diagram(subscriber.user, RULES)
    birth = _event(diagram, kind="birth", date="1978-01-01", person=1, child=6)
    assert (birth["person"], birth["spouse"]) == (1, 2)
    assert len(diagram.get_diagram_data().people) == len(RULES["people"])
