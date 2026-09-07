import datetime
import pickle

import pytest

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.personal import record
from btcopilot.personal.models import Author, Change
from btcopilot.pro.models import Diagram
from btcopilot.schema import ItemKind


def _diagram(user, data: dict) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(data)
    db.session.add(diagram)
    db.session.commit()
    return diagram


def test_pickle_row_reads_and_rewrites_as_json(subscriber):
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
    assert diagramjson.is_json(diagram.data)
    assert diagram.get_diagram_data().people == [{"id": 1, "name": "Bea"}]


def test_change_written_with_compression(subscriber):
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
    diagram = _diagram(subscriber.user, {"people": [{"id": 1, "name": "Ada"}]})

    record.apply(
        diagram.id,
        [
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "name", "after": "Cutoff"},
            {"item_kind": ItemKind.Cluster, "item_id": "c1", "field": "source", "after": "model"},
        ],
        author=Author.Coach,
        turn_id="t1",
    )
    assert diagram.get_diagram_data().clusters == [
        {"id": "c1", "name": "Cutoff", "source": "model"}
    ]


def test_diff_at_item_and_field_level():
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
                {"id": 20, "person": 1, "kind": "birth"},
                {"id": 21, "person": 2, "kind": "shift"},
            ],
            "emotions": [{"id": 30, "person": 1, "target": 2, "event": 20}],
        },
    )


def test_delete_person_cascades_like_the_scene(subscriber):
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


def test_pro_put_round_trip_and_logs_a_change(flask_app, test_user):
    diagram = test_user.free_diagram
    diagram.data = pickle.dumps({"people": [{"id": 1, "name": "Ada"}]})
    db.session.commit()

    payload = pickle.dumps({"people": [{"id": 1, "name": "Bea"}]})
    with flask_app.test_client(user=test_user) as client:
        response = client.patch(
            f"/v1/diagrams/{diagram.id}",
            data=pickle.dumps(
                {"updated_at": datetime.datetime.utcnow(), "data": payload}
            ),
        )
    assert response.status_code == 200

    body = pickle.loads(response.data)
    assert pickle.loads(body["data"]) == {"people": [{"id": 1, "name": "Bea"}]}

    db.session.refresh(diagram)
    assert diagramjson.is_json(diagram.data)

    change = Change.query.filter_by(diagram_id=diagram.id).one()
    assert change.author == Author.Pro
    assert change.deltas == [
        {
            "item_id": 1,
            "item_kind": "person",
            "field": "name",
            "before": "Ada",
            "after": "Bea",
        }
    ]
