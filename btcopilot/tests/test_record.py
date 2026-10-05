import datetime
import pickle

import pytest

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot import record
from btcopilot.models import Author, Change
from btcopilot.models import Diagram
from btcopilot.schema import Event, EventKind, ItemKind, RelationshipKind, from_dict


def _diagram(user, data: dict) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(data)
    db.session.add(diagram)
    db.session.commit()
    return diagram


def test_pickle_row_reads_and_stays_pickle(subscriber):
    # R-0422
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})
    assert not diagramjson.is_json(diagram.data)

    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Ada"}]

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Bea"}],
        author=Author.Coach,
        turn_id="t1",
        user_id=subscriber.user.id,
    )
    db.session.refresh(diagram)
    assert not diagramjson.is_json(diagram.data)
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Bea"}]


def test_change_written_with_compression(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    change = record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "B"},
            {"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "C"},
            {"item_kind": ItemKind.Person, "item_id": 1, "field": "age", "after": 40},
        ],
        author=Author.User,
        turn_id="t1",
        user_id=subscriber.user.id,
    )
    assert [(d["field"], d["before"], d["after"]) for d in change.deltas] == [
        ("name", "Ada", "C"),
        ("age", None, 40),
    ]
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "C", "age": 40}]


def test_undo_turn_restores_and_logs(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Bea"}],
        author=Author.Coach,
        turn_id="t1",
    )

    record.undo(diagram.id, "t1", author=Author.User, user_id=subscriber.user.id)
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Ada"}]
    assert Change.query.filter_by(turn_id="undo:t1").count() == 1


def test_undo_conflict_names_the_failing_delta(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Bea"}],
        author=Author.Coach,
        turn_id="t1",
    )
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Cy"}],
        author=Author.User,
        turn_id="t2",
    )

    with pytest.raises(record.Conflict) as excinfo:
        record.undo(diagram.id, "t1", author=Author.User)
    assert excinfo.value.delta["field"] == "name"
    assert excinfo.value.actual == "Cy"
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Cy"}]


def test_undo_changes_takes_back_only_the_rows_named_each_logged_and_a_conflict_writes_nothing(
    subscriber,
):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})
    named = [
        record.apply(
            diagram.id,
            [{"item_kind": ItemKind.Person, "item_id": 1, "field": field, "after": after}],
            author=Author.Coach,
            turn_id="t1",
        )
        for field, after in (("name", "Bea"), ("age", 40), ("gender", "female"))
    ]

    record.undo_changes(diagram.id, [named[2].id, named[1].id], author=Author.Coach)
    person = diagram.get_diagram_data().people[0]
    assert (person["name"], person.get("age"), person.get("gender")) == ("Bea", None, None)
    assert [c.turn_id for c in Change.query.filter(Change.turn_id.like("undo:%"))] == [
        f"undo:t1#{named[2].id}",
        f"undo:t1#{named[1].id}",
    ]
    assert record.undone(diagram.id) == {named[1].id, named[2].id}

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Cy"}],
        author=Author.User,
        turn_id="t2",
    )
    rows = Change.query.count()
    with pytest.raises(record.Conflict):
        record.undo_changes(diagram.id, [named[0].id], author=Author.Coach)
    assert (diagram.get_diagram_data().people[0]["name"], Change.query.count()) == ("Cy", rows)


def test_undo_changes_passes_over_a_row_that_changed_nothing_and_a_field_emptied_since(
    subscriber,
):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    def put(item_id, field, after, turn="t1"):
        return record.apply(
            diagram.id,
            [{"item_kind": ItemKind.Person, "item_id": item_id, "field": field, "after": after}],
            author=Author.Coach,
            turn_id=turn,
        )

    same = put(1, "name", "Ada")
    put(1, "name", "Bo", turn="t2")
    made = put(2, "name", "Cal")
    aged = put(2, "age", 40)

    record.undo_changes(diagram.id, [same.id, made.id, aged.id], author=Author.Coach)
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Bo"}]
    assert record.undone(diagram.id) == {same.id, made.id, aged.id}


THREE = [
    {"id": i, "kind": "noted", "person": 1, "description": "Moved", "dateTime": f"200{i}-01-01"}
    for i in (1, 2, 3)
]


def test_write_path_creates_a_cluster(subscriber):
    # R-0076, R-0085
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}], "events": THREE})

    record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "name", "after": "Cutoff"},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "eventIds", "after": [1, 2, 3]},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "source", "after": "model"},
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().clusters == [
        {"id": "c1", "name": "Cutoff", "eventIds": [1, 2, 3], "source": "model"}
    ]


def test_the_write_refuses_a_cluster_under_three_events(subscriber):
    # R-0215
    """The floor is enforced where every writer passes, on the record the write
    would leave behind, not on the delta that carries the events."""
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    with pytest.raises(record.Invalid, match="fewer than 3"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "name", "after": "Cutoff"},
                {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "eventIds", "after": [1, 2]},
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert diagram.get_diagram_data().clusters == []
    assert Change.query.filter_by(diagram_id=diagram.id).count() == 0


def test_the_write_refuses_a_description_that_names_a_person_the_event_links(
    subscriber,
):
    # R-0457
    """Owner ruling 2026-09-09: the links say who, so the words may not say the
    same person again."""
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Elizabeth"}]})

    with pytest.raises(record.Invalid, match="already its child"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 20, "field": "kind", "after": "birth"},
                {"item_kind": ItemKind.Event, "item_id": 20, "field": "child", "after": 1},
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 20,
                    "field": "description",
                    "after": "Elizabeth born in Anchorage",
                },
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert diagram.get_diagram_data().events == []


def test_the_write_refuses_a_birth_hung_on_the_person_instead_of_the_child(subscriber):
    # R-0456
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Elizabeth"}]})

    with pytest.raises(record.Invalid, match="set child, not person"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 20, "field": "kind", "after": "birth"},
                {"item_kind": ItemKind.Event, "item_id": 20, "field": "person", "after": 1},
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert diagram.get_diagram_data().events == []


def test_a_birth_about_the_child_with_words_of_its_own_commits(subscriber):
    # R-0457
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Elizabeth"}]})

    record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Event, "item_id": 20, "field": "kind", "after": "birth"},
            {"item_kind": ItemKind.Event, "item_id": 20, "field": "child", "after": 1},
            {
                "item_kind": ItemKind.Event,
                "item_id": 20,
                "field": "description",
                "after": "in Anchorage, AK",
            },
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().events[0]["description"] == "in Anchorage, AK"


def test_a_write_that_only_renames_a_cluster_is_not_held_to_events_it_did_not_touch(
    subscriber,
):
    # R-0215
    """A rename touches no events, so it is judged on the cluster it leaves
    behind -- which still holds three."""
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}],
            "events": THREE,
            "clusters": [{"id": "c1", "name": "Cutoff", "eventIds": [1, 2, 3]}],
        },
    )

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "name", "after": "The year after"}],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().clusters[0]["name"] == "The year after"


def test_a_grouping_stored_under_the_older_floor_blocks_nothing_else(subscriber):
    # R-0215
    """A record can hold a grouping made when two events were enough. The write
    answers for what it touches, so unrelated work still commits."""
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}],
            "clusters": [{"id": "c1", "name": "Cutoff", "eventIds": [1, 2]}],
        },
    )

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": "name", "after": "Bea"}],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Bea"}]
    assert diagram.get_diagram_data().clusters[0]["eventIds"] == [1, 2]


def test_undo_may_not_put_back_a_cluster_under_three_events(subscriber):
    # R-0215
    """Undo reaches the record without going through apply, so the floor has to
    live where both of them commit; otherwise undoing the removal of a pair puts
    the pair straight back."""
    diagram = _diagram(
        subscriber.user,
        {"clusters": [{"id": "c1", "name": "Cutoff", "eventIds": [1, 2]}]},
    )
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Cluster, "item_id": "c1", "field": None, "after": None}],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().clusters == []

    with pytest.raises(record.Invalid, match="fewer than 3"):
        record.undo(diagram.id, "t1", author=Author.User)
    assert diagram.get_diagram_data().clusters == []


def test_diff_at_item_and_field_level():
    # R-0084
    old = {"people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Gone"}]}
    new = {"people": [{"id": 1, "name": "Bea"}, {"id": 3, "name": "New"}]}

    deltas = {(d["item_id"], d["field"]): (d["before"], d["after"]) for d in record.diff(old, new)}
    assert deltas[(1, "name")] == ("Ada", "Bea")
    assert deltas[(3, "name")] == (None, "New")
    assert deltas[(2, "name")] == ("Gone", None)


def _family(user) -> Diagram:
    return _diagram(
        user,
        {
            "people": [
                {"id": 1, "name": "Ada"},
                {"id": 2, "name": "Bo"},
                {"id": 3, "name": "Kid", "parents": 10},
            ],
            "pair_bonds": [{"id": 10, "person_a": 1, "person_b": 2}],
            "events": [
                {"id": 20, "child": 1, "kind": "birth"},
                {"id": 21, "person": 2, "kind": "shift"},
            ],
            "emotions": [{"id": 30, "person": 1, "target": 2, "event": 20}],
        },
    )


def test_delete_person_cascades_like_the_scene(subscriber):
    # R-0078
    diagram = _family(subscriber.user)

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": None, "after": None}],
        author=Author.Coach,
        turn_id="t1",
    )
    data = diagram.get_diagram_data()
    assert [p["id"] for p in data.people] == [2, 3]
    assert data.pair_bonds == []
    assert [e["id"] for e in data.events] == [21]
    assert data.emotions == []
    assert data.people[1]["parents"] is None


def test_undo_of_delete_restores_the_family(subscriber):
    # R-0084
    diagram = _family(subscriber.user)
    before = diagram.get_diagram_data()

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 1, "field": None, "after": None}],
        author=Author.Coach,
        turn_id="t1",
    )
    record.undo(diagram.id, "t1", author=Author.User)

    after = diagram.get_diagram_data()
    assert sorted(p["id"] for p in after.people) == sorted(
        p["id"] for p in before.people
    )
    assert after.pair_bonds == before.pair_bonds
    assert sorted(e["id"] for e in after.events) == sorted(
        e["id"] for e in before.events
    )
    assert after.emotions == before.emotions
    assert [p for p in after.people if p["id"] == 3][0]["parents"] == 10


def test_delete_of_a_missing_item_raises(subscriber):
    # R-0453
    diagram = _family(subscriber.user)

    with pytest.raises(ValueError):
        record.apply(
            diagram.id,
            [
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 99,
                    "field": None,
                    "after": None,
                }
            ],
            author=Author.Coach,
            turn_id="t1",
        )


def test_the_write_refuses_a_shift_that_says_nothing_moved(subscriber):
    # R-0363
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    with pytest.raises(record.Invalid, match="shift with no variable"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 30, "field": "kind", "after": "shift"},
                {"item_kind": ItemKind.Event, "item_id": 30, "field": "person", "after": 1},
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 30,
                    "field": "description",
                    "after": "a hard week",
                },
                {"item_kind": ItemKind.Event, "item_id": 30, "field": "title", "after": "Hard week"},
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert diagram.get_diagram_data().events == []


def test_the_write_refuses_an_early_birth_that_carries_a_variable(subscriber):
    # R-0037
    """Owner ruling R-0037: a birth before the story starts anchors age only."""
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}],
            "events": [
                {"id": 10, "kind": "shift", "person": 1, "dateTime": "1990-04-02", "anxiety": "up"}
            ],
        },
    )

    with pytest.raises(record.Invalid, match="only a shift carries"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 31, "field": "kind", "after": "birth"},
                {"item_kind": ItemKind.Event, "item_id": 31, "field": "child", "after": 1},
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 31,
                    "field": "dateTime",
                    "after": "1962-01-05",
                },
                {"item_kind": ItemKind.Event, "item_id": 31, "field": "anxiety", "after": "up"},
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert len(diagram.get_diagram_data().events) == 1


def test_the_write_refuses_a_moment_already_in_the_record(subscriber):
    # R-0442
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}],
            "events": [
                {"id": 10, "kind": "married", "person": 1, "spouse": 2, "dateTime": "1988-06-11"}
            ],
        },
    )

    with pytest.raises(record.Invalid, match="already event 10"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 32, "field": "kind", "after": "married"},
                {"item_kind": ItemKind.Event, "item_id": 32, "field": "person", "after": 1},
                {"item_kind": ItemKind.Event, "item_id": 32, "field": "spouse", "after": 2},
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 32,
                    "field": "dateTime",
                    "after": "1988-06-11",
                },
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert len(diagram.get_diagram_data().events) == 1


def test_a_shift_that_names_its_move_beside_an_anchoring_birth_commits(subscriber):
    # R-0037
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}],
            "events": [{"id": 10, "kind": "birth", "child": 1, "dateTime": "1962-01-05"}],
        },
    )

    record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Event, "item_id": 33, "field": "kind", "after": "shift"},
                {"item_kind": ItemKind.Event, "item_id": 33, "field": "description", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 33, "field": "title", "after": "Stopped calling"},
            {"item_kind": ItemKind.Event, "item_id": 33, "field": "person", "after": 1},
            {"item_kind": ItemKind.Event, "item_id": 33, "field": "dateTime", "after": "1990-04-02"},
            {"item_kind": ItemKind.Event, "item_id": 33, "field": "anxiety", "after": "up"},
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert len(diagram.get_diagram_data().events) == 2


def test_the_write_refuses_a_noted_event_with_no_words(subscriber):
    # R-0363
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    with pytest.raises(record.Invalid, match="say what happened"):
        record.apply(
            diagram.id,
            [
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 30,
                    "field": "kind",
                    "after": EventKind.Noted.value,
                },
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 30,
                    "field": "person",
                    "after": 1,
                },
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 30,
                    "field": "dateTime",
                    "after": "2019-03-01",
                },
            ],
            author=Author.Coach,
            turn_id="t1",
            user_id=subscriber.user.id,
        )


def test_the_write_refuses_a_shift_with_no_title(subscriber):
    # R-0681
    diagram = _diagram(subscriber.user, RULES)
    with pytest.raises(record.Invalid, match="event 40 is a shift event and needs a title") as refused:
        _write(diagram, ItemKind.Event, 40, {k: v for k, v in SHIFT.items() if k != "title"})
    assert "title" in refused.value.plain
    assert diagram.get_diagram_data().events == RULES["events"]


def test_the_write_refuses_a_title_naming_the_person_the_event_links(subscriber):
    # R-0681
    diagram = _diagram(subscriber.user, RULES)
    with pytest.raises(record.Invalid, match="event 40's title names Ada, who is already its person"):
        _write(diagram, ItemKind.Event, 40, dict(SHIFT, title="Ada stopped calling"))
    assert diagram.get_diagram_data().events == RULES["events"]


def test_a_thing_made_is_logged_whole_and_undo_takes_it_off(subscriber):
    # R-0084
    diagram = _diagram(
        subscriber.user, {"people": [{"id": 1, "name": "Ada"}], "events": THREE, "lastItemId": 3}
    )
    change = record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Person, "item_id": 4, "field": "name", "after": "Bea"},
            {"item_kind": ItemKind.Diagram, "item_id": None, "field": "lastItemId", "after": 4},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "title", "after": "Cutoff"},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "eventIds", "after": [1, 2, 3]},
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert [(d["item_id"], d["field"], d["before"], d["after"]) for d in change.deltas] == [
        (4, None, None, {"id": 4, "name": "Bea"}),
        (None, "lastItemId", 3, 4),
        ("c1", None, None, {"id": "c1", "title": "Cutoff", "eventIds": [1, 2, 3]}),
    ]

    record.undo(diagram.id, "t1", author=Author.User)
    data = diagram.get_diagram_data()
    assert data.people == [{"id": 1, "name": "Ada"}]
    assert data.clusters == []


def test_undo_will_not_take_off_a_thing_something_since_hangs_on(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 2, "field": "name", "after": "Bea"}],
        author=Author.Coach,
        turn_id="t1",
    )
    record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "kind", "after": "noted"},
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "person", "after": 2},
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "description", "after": "Moved"},
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "title", "after": "Moved away"},
        ],
        author=Author.User,
        turn_id="t2",
    )

    with pytest.raises(record.Conflict) as excinfo:
        record.undo(diagram.id, "t1", author=Author.User)
    assert excinfo.value.actual == ["event 3"]
    assert [p["id"] for p in diagram.get_diagram_data().people] == [1, 2]


@pytest.mark.parametrize(
    "field, value",
    [("relationshipTargets", [1]), ("relationshipTriangles", [2, 1])],
)
def test_the_write_refuses_an_event_whose_mover_is_also_its_target(
    subscriber, field, value
):
    # R-0526, R-0532
    diagram = _diagram(
        subscriber.user,
        {"people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}]},
    )

    with pytest.raises(record.Invalid, match="event 34 has person 1 as both"):
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "kind", "after": "shift"},
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "description", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "title", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "person", "after": 1},
                {
                    "item_kind": ItemKind.Event,
                    "item_id": 34,
                    "field": "relationship",
                    "after": "distance",
                },
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "relationshipTargets", "after": [2]},
                {"item_kind": ItemKind.Event, "item_id": 34, "field": field, "after": value},
                {"item_kind": ItemKind.Event, "item_id": 34, "field": "dateTime", "after": "1990-04-02"},
            ],
            author=Author.Coach,
            turn_id="t1",
        )
    assert diagram.get_diagram_data().events == []


@pytest.mark.parametrize("move", [kind.value for kind in RelationshipKind])
def test_the_write_refuses_a_move_with_no_target(subscriber, move):
    # R-0585
    diagram = _diagram(
        subscriber.user,
        {"people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}]},
    )

    with pytest.raises(record.Invalid, match=f"event 36 is a {move} move with no target") as refused:
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "kind", "after": "shift"},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "description", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "title", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "person", "after": 1},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "relationship", "after": move},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "dateTime", "after": "1990-04-02"},
            ],
            author=Author.User,
            turn_id="t1",
        )
    assert refused.value.plain == f"{RelationshipKind(move).menuLabel()} needs the person it was aimed at."
    assert diagram.get_diagram_data().events == []


def test_a_move_already_missing_its_target_does_not_block_other_writes(subscriber):
    # R-0585
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}],
            "events": [
                {
                    "id": 3,
                    "kind": "shift",
                    "person": 1,
                    "relationship": "defined-self",
                    "relationshipTargets": [],
                    "dateTime": "2015-09-01",
                    "description": "Left for school",
                }
            ],
        },
    )

    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 2, "field": "name", "after": "Bee"}],
        author=Author.User,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().people[1]["name"] == "Bee"


@pytest.mark.parametrize("kind", ["married", "bonded", "separated", "divorced"])
def test_the_write_refuses_a_couple_event_with_no_spouse(subscriber, kind):
    # R-0453
    diagram = _diagram(
        subscriber.user,
        {"people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}]},
    )

    with pytest.raises(record.Invalid, match=f"event 36 is a {kind} event") as refused:
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "kind", "after": kind},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "person", "after": 1},
                {"item_kind": ItemKind.Event, "item_id": 36, "field": "dateTime", "after": "1990-04-02"},
            ],
            author=Author.User,
            turn_id="t1",
        )
    assert refused.value.plain
    assert diagram.get_diagram_data().events == []


@pytest.mark.parametrize(
    "field, value",
    [("relationshipTargets", None), ("relationshipTriangles", None), ("relationshipTargets", 2)],
)
def test_the_write_refuses_an_event_whose_people_of_a_move_are_not_a_list(
    subscriber, field, value
):
    # R-0453
    diagram = _diagram(
        subscriber.user,
        {"people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Bea"}]},
    )

    with pytest.raises(record.Invalid, match=f"event 35's {field} is not a list") as refused:
        record.apply(
            diagram.id,
            [
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "kind", "after": "shift"},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "description", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "title", "after": "Stopped calling"},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "person", "after": 1},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "relationship", "after": "distance"},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": field, "after": value},
                {"item_kind": ItemKind.Event, "item_id": 35, "field": "dateTime", "after": "1990-04-02"},
            ],
            author=Author.User,
            turn_id="t1",
        )
    assert refused.value.plain
    assert diagram.get_diagram_data().events == []


RULES = {
    "people": [
        {"id": 1, "name": "Ada", "gender": "female"},
        {"id": 2, "name": "Bea", "gender": "male"},
        {"id": 3, "name": "Cal", "parents": 9},
        {"id": 4, "name": "Dee"},
        {"id": 5, "name": "Eve", "parents": 9},
    ],
    "pair_bonds": [
        {"id": 9, "person_a": 1, "person_b": 2},
        {"id": 10, "person_a": 2, "person_b": 4},
    ],
    "events": [
        {"id": 20, "kind": "birth", "child": 3, "person": 1, "spouse": 2, "dateTime": "1990-01-01"},
        {"id": 21, "kind": "death", "person": 4, "dateTime": "2000-01-01"},
        {"id": 22, "kind": "married", "person": 2, "spouse": 4, "dateTime": "1995-06-01"},
    ],
    "clusters": [],
    "lastItemId": 22,
}
SHIFT = {
    "kind": "shift",
    "person": 1,
    "dateTime": "2001-02-03",
    "title": "Stopped calling",
    "description": "Stopped calling",
    "anxiety": "up",
}


def _write(diagram, kind: ItemKind, item_id, fields: dict):
    return record.apply(
        diagram.id,
        [
            {"item_kind": kind, "item_id": item_id, "field": field, "after": value}
            for field, value in fields.items()
        ],
        author=Author.Coach,
        turn_id="t1",
    )


@pytest.mark.parametrize(
    "fields, match",
    [
        ({"kind": "moved"}, "event 40's kind is 'moved', which is not one of the event kinds"),
        ({"anxiety": "sideways"}, "event 40's anxiety is 'sideways', which is not one of"),
        ({"relationship": "hug", "relationshipTargets": [2]}, "event 40's relationship is 'hug'"),
        ({"dateCertainty": "maybe"}, "event 40's dateCertainty is 'maybe'"),
        ({"kind": "birth", "person": None, "anxiety": None}, "event 40 is a birth with no child"),
        ({"kind": "death", "person": None, "anxiety": None}, "event 40 is a death event about nobody"),
        ({"person": 7}, "event 40 names person 7, who is not in the record"),
        ({"kind": "married", "spouse": 1, "anxiety": None}, "event 40 names person 1 as both person and spouse"),
        ({"kind": "birth", "child": 1, "spouse": 2, "anxiety": None}, "event 40 has person 1 as both the child and a parent"),
        (
            {"anxiety": None, "relationship": "inside", "relationshipTargets": [2]},
            "event 40 is an inside move with no third person",
        ),
        (
            {"anxiety": None, "relationship": "outside", "relationshipTargets": [2], "relationshipTriangles": [2]},
            "event 40 has person 2 as both a target and the third person",
        ),
        ({"relationshipTargets": [2]}, "event 40 has relationship_targets but no relationship move"),
        (
            {"anxiety": None, "relationship": "distance", "relationshipTargets": [2], "relationshipTriangles": [4]},
            "event 40 has relationship_triangles but is not an inside or outside move",
        ),
        ({"kind": "noted"}, "event 40 is a noted event, and only a shift carries"),
        ({"kind": "birth", "child": 5, "person": None}, "event 40 is a birth event, and only a shift carries"),
        ({"description": None}, "event 40 is a shift event with no words"),
        ({"description": "New Event"}, "event 40 is a shift event with no words"),
        ({"description": " unknown "}, "event 40 is a shift event with no words"),
        ({"dateTime": "1998"}, "event 40's dateTime '1998' is not a date"),
        ({"kind": "divorced", "spouse": 3, "anxiety": None}, "event 40 is a divorced event between persons 1 and 3, who have no pair bond"),
        ({"kind": "birth", "child": 5, "spouse": 4, "anxiety": None}, "event 40 names person 4 as a parent of person 5, who is born to pair bond 9"),
        ({"kind": "birth", "child": 3, "person": None, "anxiety": None, "dateTime": "1991-01-01"}, "person 3 already has a birth, event 20"),
        ({"kind": "death", "person": 4, "anxiety": None}, "person 4 already has a death, event 21"),
    ],
)
def test_the_write_refuses_an_event_that_breaks_a_record_rule(subscriber, fields, match):
    # R-0593
    diagram = _diagram(subscriber.user, RULES)
    event = {k: v for k, v in dict(SHIFT, **fields).items() if v is not None}
    with pytest.raises(record.Invalid, match=match) as refused:
        _write(diagram, ItemKind.Event, 40, event)
    assert refused.value.plain
    assert diagram.get_diagram_data().events == RULES["events"]


@pytest.mark.parametrize(
    "kind, item_id, fields, match",
    [
        (ItemKind.Person, 30, {"gender": "female"}, "person 30 has no name"),
        (ItemKind.Person, 30, {"name": "Gus", "gender": "robot"}, "person 30's gender is 'robot'"),
        (ItemKind.Person, 3, {"parents": 10}, "event 20 names person 1 as a parent of person 3, who is born to pair bond 10"),
        (ItemKind.PairBond, 9, {"married": "yes"}, "pair bond 9's married is 'yes'"),
        (ItemKind.PairBond, 10, {"person_b": 5}, "leaves event 22 naming persons 2 and 4 as a couple with no pair bond"),
        (ItemKind.PairBond, 10, {}, "leaves event 22 naming persons 2 and 4 as a couple with no pair bond"),
        (ItemKind.Cluster, "c1", {"title": "A", "summary": "", "eventIds": [20, 21, 99]}, "cluster c1 names event 99, which is not in the record"),
    ],
)
def test_the_write_refuses_an_item_that_breaks_a_record_rule(subscriber, kind, item_id, fields, match):
    # R-0593
    diagram = _diagram(subscriber.user, RULES)
    with pytest.raises(record.Invalid, match=match) as refused:
        if fields:
            _write(diagram, kind, item_id, fields)
        else:
            _write(diagram, kind, item_id, {None: None})
    assert refused.value.plain
    assert diagram.get_diagram_data().pair_bonds == RULES["pair_bonds"]
    assert diagram.get_diagram_data().people == RULES["people"]


def test_removing_an_event_takes_it_out_of_its_clusters(subscriber):
    # R-0593
    events = [dict(SHIFT, id=i, dateTime=f"200{i - 40}-01-01") for i in range(40, 45)]
    diagram = _diagram(
        subscriber.user,
        dict(
            RULES,
            events=events,
            clusters=[
                {"id": "c1", "title": "A", "summary": "", "eventIds": [40, 41, 42, 43]},
                {"id": "c2", "title": "B", "summary": "", "eventIds": [42, 43, 44]},
            ],
        ),
    )
    _write(diagram, ItemKind.Event, 42, {None: None})
    assert [(c["id"], c["eventIds"]) for c in diagram.get_diagram_data().clusters] == [
        ("c1", [40, 41, 43])
    ]


def test_taking_back_targets_set_on_an_event_leaves_an_empty_list(subscriber):
    # R-0596, R-0084
    """Production FD-366: a hand edit gave an event with no targets a
    relationship and a target; the backfill took that row back and the shadow
    turn failed reading the event."""
    diagram = _diagram(
        subscriber.user,
        {
            "people": [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Lou"}],
            "events": [{"id": 3, "kind": "shift", "person": 1, "title": "Went into treatment", "description": "went into treatment"}],
        },
    )
    change = record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "relationship", "after": "toward"},
            {"item_kind": ItemKind.Event, "item_id": 3, "field": "relationshipTargets", "after": [2]},
        ],
        author=Author.Review,
        turn_id="t1",
        user_id=subscriber.user.id,
    )
    data = diagramjson.loads(diagram.data)
    record.rewind(data, change.deltas)
    assert from_dict(Event, data["events"][0]).relationshipTargets == []


def test_taking_back_an_event_made_by_field_sets_then_given_targets_removes_it():
    # R-0596, R-0084
    """Production FD-366: rewinding Patrick's record left event 66 holding only
    an empty target list and no kind, and coverage failed reading it."""
    made = [
        {"item_kind": "event", "item_id": 66, "field": field, "before": None, "after": after}
        for field, after in (("kind", "noted"), ("person", 1), ("description", "told Lou"))
    ]
    targeted = [
        {"item_kind": "event", "item_id": 66, "field": "kind", "before": "noted", "after": "shift"},
        {"item_kind": "event", "item_id": 66, "field": "relationshipTargets", "before": [], "after": [2]},
    ]
    data = {"events": [{"id": 66, "kind": "shift", "person": 1, "description": "told Lou", "relationshipTargets": [2]}]}
    record.rewind(data, targeted)
    record.rewind(data, made)
    assert data["events"] == []
