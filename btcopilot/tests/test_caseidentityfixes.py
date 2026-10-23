"""Who each user is on a case, in the places the first build missed: the
migration on Postgres, the meter, the event-reading tool's words, the case
report backfill, the comparison turn and the question catch-up (FD-387).

Invented names only.
"""

import datetime
import json

from mock import patch

import btcopilot
from btcopilot import casereport, recordtext, shadow
from btcopilot.admin import admin, catchup
from btcopilot.coachmodel import Spent
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Statement, TokenMeter
from btcopilot.routes.diagrams import diagrams_payload
from btcopilot.schema import ItemKind
from btcopilot.tests.conftest import Model, calling, csrf_token, said
from btcopilot.tests.test_caseidentities import (  # noqa: F401
    BORN,
    MIGRATION,
    NOTE,
    coached,
    titles,
    turn,
)
from btcopilot.tests.test_casereportbackfill import MAIN, backfill, guesses  # noqa: F401
from btcopilot.tests.test_catchup import catch_up, fact, kin  # noqa: F401
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.tests.test_shadow import shadows
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ReadField, ToolName, Toolbox


def migration():
    namespace = {}
    exec(compile(MIGRATION.read_text(), str(MIGRATION), "exec"), namespace)
    return namespace


# 1. one column and its backfill


def test_the_migration_reads_a_blob_postgres_hands_back_as_a_memoryview():
    # R-0888
    owner_person = migration()["owner_person"]
    blob = memoryview(b'{"people": [{"id": 3, "primary": true}]}')
    assert owner_person(blob, free=False) == 3


# 2. voice follows the row, in every place


def test_a_human_coachs_turn_is_charged_to_the_human_coach(web, monkeypatch, coached):
    # R-0895
    reply = said("Tell me more.")
    reply.spent = Spent(input=1000, output=50)
    monkeypatch.setattr("btcopilot.turns.model_for", lambda *a, **k: Model(reply))
    web.user.current_diagram_id = coached.id
    db.session.commit()
    response = web.post(
        f"/app/chat?diagram_id={coached.id}",
        json={"statement": "Her sister is Nell."},
        headers={"X-CSRFToken": csrf_token(web)},
    )
    assert response.status_code == 202, response.get_data(as_text=True)
    meter = TokenMeter.query.filter_by(user_id=web.user.id).one()
    assert (meter.input_tokens, meter.output_tokens) == (1000, 50)
    assert TokenMeter.query.filter_by(user_id=coached.user_id).count() == 0


def test_a_human_coachs_comparison_turn_speaks_to_them_as_a_consultant(
    web, monkeypatch, test_user, coached
):
    # R-0889
    candidate = Model(said("Tell me about her."))
    monkeypatch.setattr("btcopilot.shadow.model_for", lambda *a, **k: candidate)
    shadows(test_user, "sonnet")
    with patch("btcopilot.shadow.enqueue", shadow.run):
        turn(web, monkeypatch, coached)
    (told,) = candidate.systems
    assert NOTE in told
    assert recordtext.SPEAKER not in told


def test_the_question_catch_up_marks_the_owner_as_speaker_only_when_they_are_the_person(
    flask_app, tmp_path, test_user, kin, past
):
    # R-0889
    model = Model(calling(fact(past)))
    catch_up(flask_app, "--plans", str(tmp_path), model=model)
    assert recordtext.SPEAKER in model.systems[0]

    kin.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    model = Model(calling(fact(past)))
    catch_up(flask_app, "--plans", str(tmp_path), model=model)
    assert recordtext.SPEAKER not in model.systems[0]


# 3. the coach reads the diagram only, and only its own user's words


def test_the_event_words_never_carry_another_users_words(test_user, test_user_2, coached):
    # R-0890
    owners = open_session(test_user_2, coached)
    db.session.add(
        Statement(
            discussion_id=owners.id,
            speaker_id=owners.chat_user_speaker_id,
            text="Mum was born in the spring of 1980.",
            turn_id="t1",
            created_at=datetime.datetime(2026, 1, 5, 10),
        )
    )
    db.session.add(
        Change(
            diagram_id=coached.id,
            turn_id="t1",
            author=Author.Coach,
            deltas=[
                {
                    "item_kind": ItemKind.Event.value,
                    "item_id": str(BORN["id"]),
                    "field": "kind",
                    "before": None,
                    "after": BORN["kind"],
                }
            ],
        )
    )
    db.session.commit()

    def words(user):
        read, _ = Toolbox(coached.id, "t9", user_id=user.id).call(
            ToolName.ReadEvents, {"fields": [ReadField.Words]}
        )
        return read

    assert "spring of 1980" not in words(test_user)
    assert "spring of 1980" in words(test_user_2)


# 4. one case report, written to the person only when they are on the case


def test_the_case_report_backfill_writes_about_the_person_when_no_one_on_the_case_is_them(
    flask_app, tmp_path, test_user, family, guesses
):
    # R-0891
    model = Model(calling(MAIN))
    backfill(flask_app, "--plans", str(tmp_path), model=model)
    assert recordtext.SPEAKER in model.systems[0]
    assert casereport.ABOUT.split(":")[0] not in model.histories[0][0]["content"]

    family.grant_access(test_user, btcopilot.ACCESS_READ_WRITE, person_id=None)
    db.session.commit()
    model = Model(calling(MAIN))
    result = backfill(flask_app, "--plans", str(tmp_path), model=model)
    assert result.exit_code == 0, result.output
    assert recordtext.SPEAKER not in model.systems[0]
    assert casereport.ABOUT.format(name="Wren") in model.histories[0][0]["content"]
    assert json.loads(result.stdout)


def test_the_question_catch_up_reads_only_the_owners_sessions(test_user, test_user_2, coached):
    # R-0890
    for user, text in ((test_user_2, "Mum moved to the coast."), (test_user, "Ask about the coast.")):
        session = open_session(user, coached)
        db.session.add(
            Statement(
                discussion_id=session.id,
                speaker_id=session.chat_user_speaker_id,
                text=text,
                created_at=datetime.datetime(2026, 1, 5, 10),
            )
        )
    db.session.commit()
    transcript, mine, _ = catchup.said(coached)
    assert "Mum moved to the coast." in transcript
    assert "Ask about the coast." not in transcript
    assert [s.text for s in mine.values()] == ["Mum moved to the coast."]


def test_the_diagram_list_says_who_the_user_is_on_each_case(test_user, test_user_2, coached):
    # R-0888
    (theirs,) = [d for d in diagrams_payload(test_user) if d["id"] == coached.id]
    assert (theirs["person_id"], theirs["owner_name"]) == (None, test_user_2.first_name)
    (own,) = [d for d in diagrams_payload(test_user_2) if d["id"] == coached.id]
    assert own["person_id"] == 1
