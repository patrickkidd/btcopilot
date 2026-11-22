"""The migration gate's per-reply change count (bin/migrationgate.py:AGENT_CHANGES)."""

import pytest
import sqlalchemy as sa

import bin.migrationgate as migrationgate
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Discussion, Speaker, SpeakerType, Statement
from btcopilot.models.turnevent import TurnEvent
from btcopilot.review.models import Coding, Cut, Note

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


def test_a_navigate_call_names_a_place_not_an_item():
    # R-0487
    assert migrationgate.gone({"name": "navigate", "args": {"address": "/app/"}}, "it") == []


def test_a_tool_with_no_subject_fails_with_its_name():
    # R-0487
    with pytest.raises(SystemExit, match="show"):
        migrationgate.gone({"name": "show", "args": {}}, "it")


def test_the_session_deleted_is_never_one_a_cut_is_on(flask_app, test_user):
    # R-0487
    statement = _reply(test_user)
    discussion = statement.discussion
    person = Speaker(discussion_id=discussion.id, name="Ann", type=SpeakerType.Subject)
    db.session.add(person)
    db.session.flush()
    discussion.chat_user_speaker_id = person.id
    db.session.commit()
    assert db.session.execute(migrationgate.DELETABLE).all() == [(discussion.id, test_user.id)]
    db.session.add(
        Cut(
            diagram_id=discussion.diagram_id,
            start_statement_id=statement.id,
            end_statement_id=statement.id,
            user_id=test_user.id,
        )
    )
    db.session.commit()
    assert db.session.execute(migrationgate.DELETABLE).all() == []


def test_a_scribe_turn_is_carried_by_the_coders_note(flask_app, test_user):
    # R-0487
    statement = _reply(test_user)
    db.session.add(
        TurnEvent(
            turn_id="scribe-1", discussion_id=statement.discussion_id, seq=0, kind="done", payload={}
        )
    )
    db.session.commit()
    orphans = sa.text(migrationgate.ORPHANS["turn events no statement or coder's note carries"])
    assert db.session.execute(orphans).scalar_one() == 1
    cut = Cut(
        diagram_id=test_user.free_diagram_id,
        start_statement_id=statement.id,
        end_statement_id=statement.id,
        user_id=test_user.id,
    )
    db.session.add(cut)
    db.session.flush()
    coding = Coding(cut_id=cut.id, user_id=test_user.id, diagram_id=test_user.free_diagram_id)
    db.session.add(coding)
    db.session.flush()
    db.session.add(Note(coding_id=coding.id, statement_id=statement.id, text="Mom died", turn_id="scribe-1"))
    db.session.commit()
    assert db.session.execute(orphans).scalar_one() == 0


def test_a_merge_names_what_it_moves_and_drops_beside_its_args():
    # R-0487
    call = {"name": "merge_people", "args": {"keep": 1, "drop": 2, "take": {}}}
    assert migrationgate.gone(call, "moved") == []
    assert migrationgate.gone(call, "dropped") == []
    assert migrationgate.gone(call, "drop") == [("person", "2")]
