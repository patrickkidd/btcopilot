"""The revision that gives each play-by-play told before it the done event its
turn never wrote, so every statement carrying a turn has that turn's events.
Invented names only."""

import sqlalchemy as sa
from alembic import command

import bin.migrationgate as migrationgate
from btcopilot.admin.database import config
from btcopilot.tests.test_turnbackfill import at, kept, rows, seed

SAID = [
    {"id": 1, "discussion_id": 1, "speaker_id": 1, "kind": "turn", "turn_id": "asked",
     "text": "My sister is Nell.", "order": 0, "created_at": at(0)},
    {"id": 2, "discussion_id": 1, "speaker_id": 2, "kind": "turn", "turn_id": "asked",
     "text": "Nell is in.", "order": 1, "created_at": at(1)},
    {"id": 3, "discussion_id": 1, "speaker_id": 2, "kind": "play", "turn_id": "told",
     "cluster_id": "c1", "text": "Wren moved when Nell left.", "order": 2,
     "created_at": at(2)},
]
EVENTS = [
    {"turn_id": "asked", "discussion_id": 1, "seq": 1, "kind": "done",
     "payload": {"type": "done", "statement_id": 2}, "created_at": at(1)},
]


def test_a_play_told_before_the_revision_gets_its_done_event(flask_app, tmp_path):
    # R-0542, R-0478
    seeded = rows({}, SAID, [])
    seeded.pop("diagram_changes")
    seeded["turn_events"] = EVENTS
    engine = seed(flask_app, tmp_path, seeded, revision="1b00000000b1")
    with engine.connect() as conn:
        unlogged = conn.execute(sa.text(migrationgate.UNLOGGED_PLAYS)).scalar_one()
    assert unlogged == 1

    with flask_app.app_context():
        command.upgrade(config(), "head")

    assert kept(engine) == [
        ("asked", 1, "done", {"type": "done", "statement_id": 2}),
        ("told", 1, "done", {"type": "done", "statement_id": 3}),
    ]
    orphans = migrationgate.ORPHANS["statements carrying a turn with no turn events"]
    with engine.connect() as conn:
        assert conn.execute(sa.text(orphans)).scalar_one() == 0
