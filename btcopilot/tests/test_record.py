import datetime
import pickle

import pytest

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot import record
from btcopilot.models import Author, Change
from btcopilot.models import Diagram
from btcopilot.schema import EventKind, ItemKind


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


def test_write_path_creates_a_cluster(subscriber):
    # R-0076, R-0085
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

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
        {"clusters": [{"id": "c1", "name": "Cutoff", "eventIds": [1, 2, 3]}]},
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

    with pytest.raises(record.Invalid, match="early birth"):
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


def test_a_thing_made_is_logged_whole_and_undo_takes_it_off(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}], "lastItemId": 1})
    change = record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Person, "item_id": 2, "field": "name", "after": "Bea"},
            {"item_kind": ItemKind.Diagram, "item_id": None, "field": "lastItemId", "after": 2},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "title", "after": "Cutoff"},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "eventIds", "after": [1, 2, 3]},
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert [(d["item_id"], d["field"], d["before"], d["after"]) for d in change.deltas] == [
        (2, None, None, {"id": 2, "name": "Bea"}),
        (None, "lastItemId", 1, 2),
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
        ],
        author=Author.User,
        turn_id="t2",
    )

    with pytest.raises(record.Conflict) as excinfo:
        record.undo(diagram.id, "t1", author=Author.User)
    assert excinfo.value.actual == ["event 3"]
    assert [p["id"] for p in diagram.get_diagram_data().people] == [1, 2]
