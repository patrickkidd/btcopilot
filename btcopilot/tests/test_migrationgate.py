"""The migration gate's per-reply change count (bin/migrationgate.py:AGENT_CHANGES)."""

import sqlalchemy as sa

import bin.migrationgate as migrationgate
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Discussion, Speaker, SpeakerType, Statement

WITHOUT_TURN_ID = migrationgate.AGENT_CHANGES.replace(" AND c.turn_id = s.turn_id", "")


def _count(where: str, statement_id: int) -> int:
    query = sa.text(
        f"SELECT count(*) FROM diagram_changes c, statements s WHERE {where} AND s.id = :sid"
    )
    return db.session.execute(
        query, {"coach": Author.Coach.value, "sid": statement_id}
    ).scalar_one()


def _reply(test_user) -> Statement:
    discussion = Discussion(user_id=test_user.id, diagram_id=test_user.free_diagram_id)
    db.session.add(discussion)
    db.session.commit()
    ai = Speaker(discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert)
    db.session.add(ai)
    db.session.commit()
    discussion.chat_ai_speaker_id = ai.id
    statement = Statement(
        discussion_id=discussion.id, speaker_id=ai.id, text="ok", turn_id="turn-1"
    )
    db.session.add(statement)
    db.session.commit()
    db.session.add_all(
        [
            Change(
                diagram_id=test_user.free_diagram_id,
                statement_id=statement.id,
                turn_id="turn-1",
                author=Author.Coach,
                deltas=[],
            ),
            Change(
                diagram_id=test_user.free_diagram_id,
                statement_id=statement.id,
                turn_id="turn-1",
                author=Author.Coach,
                deltas=[],
            ),
            Change(
                diagram_id=test_user.free_diagram_id,
                statement_id=statement.id,
                turn_id=f"backfill:{discussion.id}",
                author=Author.Coach,
                deltas=[],
            ),
        ]
    )
    db.session.commit()
    return statement


def test_agent_changes_excludes_a_backfill_row_on_the_same_statement(flask_app, test_user):
    # R-0487
    statement = _reply(test_user)
    seen = _count(migrationgate.AGENT_CHANGES, statement.id)
    assert seen == 2


def test_dropping_the_turn_id_match_also_counts_the_backfill_row(flask_app, test_user):
    # R-0487
    statement = _reply(test_user)
    seen = _count(WITHOUT_TURN_ID, statement.id)
    assert seen == 3


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Conn:
    """What the live check reads: a turn's write calls, and what its change
    rows touched."""

    def __init__(self, writes, touched):
        self.results = {migrationgate.WRITES: writes, migrationgate.TOUCHED: touched}

    def execute(self, query):
        return _Rows(self.results[query])


def _call(turn_id, result):
    return type("Call", (), {"turn_id": turn_id, "result": result})()


def test_an_impression_write_is_found_in_its_turns_question_rows(flask_app):
    # R-0487
    """An impression is stored as a question item, so the call's noun is not
    the change row's item kind."""
    conn = _Conn(
        [_call("t1", "Added impression i1."), _call("t1", "Changed question q2.")],
        [("t1", "question", "i1"), ("t1", "question", "q2")],
    )
    [(_, expected, seen)] = migrationgate.live_checks(conn)
    assert (expected, seen) == (2, 2)
