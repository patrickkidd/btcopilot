"""The revision that adds kept turn events fills them in for the turns that ran
before it, from the change log: a coach reply gets a tool call per item its turn
touched, named from the record as it stood at that change, and the edits of a
turn that never answered go onto the words that asked for it, marked
unfinished. Invented names only."""

import datetime
import json

import sqlalchemy as sa
from alembic import command

from btcopilot.admin.database import config

T0 = datetime.datetime(2026, 9, 20, 12, 0, 0)
STATUS = "ready"
LEEDS = {"id": 3, "kind": "noted", "description": "Moved to Leeds", "dateTime": "1990-01-01"}
# The record now: Nell renamed Nella by hand, and the move she was given removed.
NOW = {
    "people": [{"id": 1, "name": "Wren", "notes": "has a sister"}, {"id": 2, "name": "Nella"}],
    "events": [],
    "lastItemId": 3,
}


def at(minutes: int) -> datetime.datetime:
    return T0 + datetime.timedelta(minutes=minutes)


def delta(kind, item_id, field, after, before=None) -> dict:
    return {
        "item_kind": kind,
        "item_id": item_id,
        "field": field,
        "before": before,
        "after": after,
    }


def rows(data: dict, said: list[dict], changes: list[dict]) -> dict:
    return {
        "users": [
            {"id": 1, "username": "coach@example.com", "roles": "subscriber",
             "created_at": T0, "status": "confirmed", "active": True,
             "password": "", "first_name": "Wren", "last_name": "Ash",
             "preferences": "{}"},
        ],
        "diagrams": [
            {"id": 1, "user_id": 1, "name": "Wren", "data": json.dumps(data).encode(), "version": 9,
             "created_at": T0},
        ],
        "discussions": [
            {"id": 1, "user_id": 1, "diagram_id": 1, "kind": "chat", "created_at": T0,
             "title_set_by_user": False, "status": STATUS, "synthetic": False,
             "chat_user_speaker_id": 1, "chat_ai_speaker_id": 2},
        ],
        "speakers": [
            {"id": 1, "discussion_id": 1, "name": "Wren", "type": "subject",
             "created_at": T0},
            {"id": 2, "discussion_id": 1, "name": "Coach", "type": "expert",
             "created_at": T0},
        ],
        "statements": said,
        "diagram_changes": changes,
    }


def migrate(flask_app, tmp_path, seeded: dict) -> sa.Engine:
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'old.db'}"
    engine = sa.create_engine(flask_app.config["SQLALCHEMY_DATABASE_URI"])
    with flask_app.app_context():
        command.upgrade(config(), "1b00000000aa")
        with engine.begin() as conn:
            for table, values in seeded.items():
                meta = sa.Table(table, sa.MetaData(), autoload_with=conn)
                conn.execute(meta.insert(), values)
        command.upgrade(config(), "head")
    return engine


def kept(engine) -> list[tuple]:
    with engine.connect() as conn:
        return [
            (turn_id, seq, kind, json.loads(payload))
            for turn_id, seq, kind, payload in conn.execute(
                sa.text(
                    "SELECT turn_id, seq, kind, payload FROM turn_events "
                    "ORDER BY turn_id, seq"
                )
            ).all()
        ]


SAID = [
    {"id": 1, "discussion_id": 1, "speaker_id": 1, "kind": "turn",
     "text": "My sister is Nell.", "order": 0, "created_at": at(0)},
    {"id": 2, "discussion_id": 1, "speaker_id": 2, "kind": "turn",
     "text": "Nell is in.", "order": 1, "created_at": at(1)},
    {"id": 3, "discussion_id": 1, "speaker_id": 1, "kind": "turn",
     "text": "She moved to Leeds in 1990.", "order": 2, "created_at": at(5)},
]
CHANGES = [
    {"id": 1, "diagram_id": 1, "statement_id": 2, "turn_id": "answered",
     "session_id": "1", "author": "coach", "created_at": at(1),
     "deltas": ([
         delta("person", 2, "name", "Nell"),
         delta("diagram", None, "lastItemId", 2, before=1),
         delta("person", 1, "notes", "has a sister"),
     ])},
    {"id": 2, "diagram_id": 1, "statement_id": None, "turn_id": "hand",
     "session_id": None, "author": "user", "created_at": at(3),
     "deltas": ([delta("person", 2, "name", "Nella", before="Nell")])},
    {"id": 3, "diagram_id": 1, "statement_id": None, "turn_id": "broke",
     "session_id": "1", "author": "coach", "created_at": at(6),
     "deltas": ([
         delta("event", 3, "kind", "noted"),
         delta("event", 3, "description", "Moved to Leeds"),
         delta("event", 3, "dateTime", "1990-01-01"),
         delta("diagram", None, "lastItemId", 3, before=2),
     ])},
    {"id": 4, "diagram_id": 1, "statement_id": None, "turn_id": "unmoved",
     "session_id": None, "author": "user", "created_at": at(7),
     "deltas": ([delta("event", 3, None, None, before=LEEDS)])},
]


def test_old_turns_get_their_tool_calls_and_a_turn_that_broke_is_marked_unfinished(
    flask_app, tmp_path
):
    # R-0478, R-0477
    engine = migrate(flask_app, tmp_path, rows(NOW, SAID, CHANGES))

    with engine.connect() as conn:
        turn_ids = dict(conn.execute(sa.text("SELECT id, turn_id FROM statements")).all())
        assert turn_ids == {1: None, 2: "answered", 3: "broke"}

        attached = dict(
            conn.execute(sa.text("SELECT id, statement_id FROM diagram_changes")).all()
        )
        assert attached == {1: 2, 2: None, 3: 3, 4: None}

    events = kept(engine)
    assert [(t, s, k) for t, s, k, _ in events] == [
        ("answered", 1, "tool_call"),
        ("answered", 2, "tool_call"),
        ("broke", 1, "tool_call"),
        ("broke", 2, "failed"),
    ]
    assert events[0][3] == {
        "type": "tool_call",
        "name": "edit_person",
        "args": {"name": "Nell"},
        "names": {"it": "Nell"},
        "result": "Added person 2.",
    }
    assert events[1][3]["args"] == {"id": 1}
    assert events[1][3]["names"] == {"it": "Wren"}
    assert events[1][3]["result"] == "Changed person 1."
    assert events[2][3]["args"] == {
        "kind": "noted",
        "description": "Moved to Leeds",
        "date": "1990-01-01",
    }
    assert events[2][3]["names"] == {"it": "Moved to Leeds"}
    assert events[3][3] == {"type": "failed", "message": "The coach did not finish that turn."}


def test_a_cluster_id_used_again_after_a_removal_names_each_cluster_as_it_was(
    flask_app, tmp_path
):
    # R-0478: a new cluster takes the lowest free id, so a removed c7 comes back
    # as a different c7, and each line still names the one it touched. The first
    # c7 is logged as one whole add, the way rows are written now; the second as
    # field sets on its id, the way rows were written before.
    old = {"id": "c7", "title": "Old move", "eventIds": [1, 2, 3]}
    new = {"id": "c7", "title": "The wedding", "eventIds": [4, 5, 6]}
    said = [
        {"id": i, "discussion_id": 1, "speaker_id": 1 + (i + 1) % 2, "kind": "turn",
         "text": f"line {i}", "order": i, "created_at": at(i)}
        for i in range(1, 7)
    ]
    changes = [
        {"id": 1, "diagram_id": 1, "statement_id": 2, "turn_id": "made",
         "session_id": "1", "author": "coach", "created_at": at(2),
         "deltas": [delta("cluster", "c7", None, old)]},
        {"id": 2, "diagram_id": 1, "statement_id": 4, "turn_id": "unmade",
         "session_id": "1", "author": "coach", "created_at": at(4),
         "deltas": [delta("cluster", "c7", None, None, before=old)]},
        {"id": 3, "diagram_id": 1, "statement_id": 6, "turn_id": "remade",
         "session_id": "1", "author": "coach", "created_at": at(6),
         "deltas": [delta("cluster", "c7", field, new[field]) for field in ("title", "eventIds")]},
    ]
    engine = migrate(flask_app, tmp_path, rows({"clusters": [new]}, said, changes))

    events = kept(engine)
    assert [(t, e["args"], e["names"], e["result"]) for t, _, _, e in events] == [
        ("made", {"title": "Old move"}, {"it": "the cluster Old move"}, "Added cluster c7."),
        ("remade", {"title": "The wedding"}, {"it": "the cluster The wedding"}, "Added cluster c7."),
        (
            "unmade",
            {"item_kind": "cluster", "item_id": "c7"},
            {"it": "the cluster Old move"},
            "Removed cluster c7.",
        ),
    ]
