import datetime
import json
import logging

from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.review.models import Coding, Cut, Note
from btcopilot.tests.review.conftest import coded


def invoke(flask_app, *args):
    return flask_app.test_cli_runner().invoke(admin, list(args))


def noted(coding: Coding) -> Note:
    note = Note(coding_id=coding.id, statement_id=1, text="Mom died", turn_id="t1")
    db.session.add(note)
    db.session.commit()
    return note


def test_reset_hides_the_copy_and_deletes_the_notes_and_coding_and_nothing_else(
    flask_app, test_user, test_user_2, cut, caplog
):
    # R-0938
    draft = coded(test_user_2, cut, {}, done=False)
    noted(draft)
    other = coded(test_user, cut, {}, done=False)
    noted(other)
    draft_id, copy_id, other_id = draft.id, draft.diagram_id, other.id
    with caplog.at_level(logging.INFO, logger="btcopilot.admin.review"):
        result = invoke(
            flask_app,
            "run", "--", "review", "codings", "reset", test_user_2.username, str(cut.id), "--yes",
        )
    assert result.exit_code == 0, result.output
    assert [(r["change"], r["value"], r["done"]) for r in json.loads(result.output)] == [
        ("diagram hidden", copy_id, True),
        ("notes deleted", 1, True),
        ("coding deleted", draft_id, True),
    ]
    db.session.expire_all()
    assert db.session.get(Diagram, copy_id).deleted_at is not None
    assert db.session.get(Coding, draft_id) is None
    assert Note.query.filter_by(coding_id=draft_id).count() == 0
    assert db.session.get(Coding, other_id) is not None
    assert Note.query.filter_by(coding_id=other_id).count() == 1
    assert db.session.get(Diagram, other.diagram_id).deleted_at is None
    assert db.session.get(Diagram, cut.diagram_id).deleted_at is None
    assert db.session.get(Cut, cut.id) is not None
    assert f"diagram {copy_id} hidden, 1 notes deleted" in caplog.text
    assert test_user_2.username in caplog.text


def test_a_submitted_coding_is_refused_and_nothing_changes(flask_app, test_user_2, cut):
    # R-0938
    done = coded(test_user_2, cut, {}, done=True)
    noted(done)
    result = invoke(
        flask_app, "review", "codings", "reset", test_user_2.username, str(cut.id), "--yes"
    )
    assert result.exit_code == 1
    assert "this coding was submitted; not reset" in result.output
    assert db.session.get(Coding, done.id) is not None
    assert Note.query.filter_by(coding_id=done.id).count() == 1
    assert db.session.get(Diagram, done.diagram_id).deleted_at is None


def test_a_copy_shared_with_another_cut_is_refused(flask_app, test_user, test_user_2, cut):
    # R-0938
    draft = coded(test_user_2, cut, {}, done=False)
    later = Cut(
        diagram_id=cut.diagram_id,
        start_statement_id=cut.end_statement_id,
        end_statement_id=cut.end_statement_id,
        user_id=test_user.id,
        meeting_date=datetime.date(2026, 10, 8),
    )
    db.session.add(later)
    db.session.flush()
    db.session.add(Coding(cut_id=later.id, user_id=test_user_2.id, diagram_id=draft.diagram_id))
    db.session.commit()
    result = invoke(
        flask_app, "review", "codings", "reset", test_user_2.username, str(cut.id), "--yes"
    )
    assert result.exit_code == 1
    assert f"this coder's coding copy is also their coding of cut {later.id}; not reset" in result.output
    assert db.session.get(Coding, draft.id) is not None
    assert db.session.get(Diagram, draft.diagram_id).deleted_at is None


def test_without_yes_the_preview_prints_and_nothing_changes(flask_app, test_user_2, cut):
    # R-0938
    draft = coded(test_user_2, cut, {}, done=False)
    noted(draft)
    result = invoke(
        flask_app, "review", "codings", "reset", test_user_2.username, str(cut.id), "--json"
    )
    assert result.exit_code == 0, result.output
    assert [r["done"] for r in json.loads(result.output)] == [False, False, False]
    guarded = invoke(
        flask_app, "run", "--", "review", "codings", "reset", test_user_2.username, str(cut.id)
    )
    assert guarded.exit_code == 3
    assert guarded.output.startswith("preview: flask admin review codings reset")
    db.session.expire_all()
    assert db.session.get(Coding, draft.id) is not None
    assert Note.query.filter_by(coding_id=draft.id).count() == 1
    assert db.session.get(Diagram, draft.diagram_id).deleted_at is None


def test_an_unknown_email_or_a_coder_with_no_coding_is_named(flask_app, test_user_2, cut):
    # R-0938
    unknown = invoke(flask_app, "review", "codings", "reset", "dev-team@example.com", str(cut.id))
    assert "no account for dev-team@example.com" in unknown.output
    missing = invoke(flask_app, "review", "codings", "reset", test_user_2.username, str(cut.id))
    assert f"{test_user_2.username} has no coding of cut {cut.id}" in missing.output


def test_the_codings_table_still_reads_without_a_subcommand(flask_app, test_user_2, cut):
    # R-0938
    coded(test_user_2, cut, {}, done=True)
    result = invoke(flask_app, "run", "--", "review", "codings", "--cut", str(cut.id))
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)[0]["cuts_done"] == "1 of 1"
