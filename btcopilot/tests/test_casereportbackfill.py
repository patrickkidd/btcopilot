"""The one pass that puts each family's guesses and questions on the case
report's cards: the dry run makes the one model call and saves its plan; the
apply writes that plan and nothing else, with no model call; every other call
is refused, a family with a card already is skipped, and the own part question
is added only when no question is on that card.

Invented names only.
"""

import json

import pytest
from mock import patch

from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Change, ModelCall, Purpose
from btcopilot.tests.conftest import Model, calling
from btcopilot.tests.test_casereport import OWN, card, cards, raised
from btcopilot.tests.test_impressions import LATCH, TENSE
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.tests.test_questions import add, box, stored
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolName

MAIN = (ToolName.SetImpression, {"id": "i1", "case_report_card": "main_guess"})
ASK_OWN = (
    ToolName.AddQuestion,
    {"text": OWN, "kind": "thought", "state": "asked", "case_report_card": "own_part"},
)


@pytest.fixture
def guesses(family, past):
    raised(family, TENSE, LATCH)
    return stored(family)


def backfill(flask_app, *args, model=None):
    model = model or Model()
    with patch("btcopilot.admin.casereport.model_for", return_value=model):
        return flask_app.test_cli_runner().invoke(
            admin, ["case-report", "backfill", *args, "--json"]
        )


def dry(flask_app, tmp_path, *turns) -> list[dict]:
    result = backfill(flask_app, "--plans", str(tmp_path), model=Model(*turns))
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def apply(flask_app, rows) -> list[dict]:
    result = backfill(flask_app, "--apply", "--plan", rows[0]["plan"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_a_dry_run_shows_and_saves_the_cards_and_writes_nothing(
    flask_app, tmp_path, family, guesses
):
    # R-0739
    changes = Change.query.count()
    rows = dry(flask_app, tmp_path, calling(ASK_OWN, MAIN))

    assert [(r["entry"], r["card_before"], r["card_after"]) for r in rows] == [
        ("i1", None, "main_guess"),
        ("new", None, "own_part"),
    ]
    assert rows[0]["owner"] == family.user_id
    assert json.loads(open(rows[0]["plan"]).read())["diagram"] == family.id
    assert stored(family) == guesses
    assert Change.query.count() == changes
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_apply_writes_the_saved_plan_with_no_model_call(flask_app, tmp_path, family, guesses):
    # R-0739
    rows = apply(flask_app, dry(flask_app, tmp_path, calling(MAIN, ASK_OWN)))

    after = stored(family)
    assert cards(family) == {"i1": "main_guess", "i2": None, "q1": "own_part"}
    assert {k: v for k, v in after["i1"].items() if k != "case_report_card"} == {
        k: v for k, v in guesses["i1"].items() if k != "case_report_card"
    }
    assert after["i2"] == guesses["i2"]
    assert after["q1"]["text"] == OWN
    assert [r["entry"] for r in rows] == ["i1", "q1"]
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_apply_without_a_plan_is_refused(flask_app, family, guesses):
    # R-0739
    result = backfill(flask_app, "--apply")

    assert result.exit_code != 0
    assert stored(family) == guesses


def test_every_other_call_is_refused_and_writes_nothing(flask_app, tmp_path, family, guesses):
    # R-0739
    data = family.get_diagram_data()
    rows = dry(
        flask_app,
        tmp_path,
        calling(
            (ToolName.AddImpression, {"text": "New.", "state": "raised", "evidence": []}),
            (ToolName.SetImpression, {"id": "i1", "text": "Reworded."}),
            (ToolName.SetImpression, {"id": "i1", "state": "resolved"}),
            (ToolName.SetImpression, {"id": "i9", "case_report_card": "main_guess"}),
            (ToolName.SetQuestion, {"id": "i1", "case_report_card": "own_part"}),
            (ToolName.EditPerson, {"id": 1, "name": "Nell"}),
            (ToolName.AddQuestion, {"text": "Why?", "kind": "fact", "state": "asked"}),
        ),
    )
    assert all(r["refused"] for r in rows)
    assert json.loads(open(rows[0]["plan"]).read())["calls"] == []

    apply(flask_app, rows)
    db.session.expire_all()
    assert family.get_diagram_data() == data


def test_a_family_with_a_card_already_is_skipped(flask_app, tmp_path, family, guesses):
    # R-0739
    card(family, "i2", "work_on")

    assert dry(flask_app, tmp_path) == []


def test_the_own_part_question_is_added_once(flask_app, tmp_path, family, guesses):
    # R-0739
    rows = dry(flask_app, tmp_path, calling(ASK_OWN, ASK_OWN))
    apply(flask_app, rows)

    own = [q for q in stored(family).values() if q.get("case_report_card") == "own_part"]
    assert len(own) == 1
    assert rows[1]["refused"]


def test_a_question_already_there_goes_on_the_own_part_card_and_none_is_added(
    flask_app, tmp_path, family, guesses
):
    # R-0739
    add(box(family), text=OWN, kind="thought")
    asked = next(i for i, q in stored(family).items() if q["text"] == OWN)
    rows = dry(
        flask_app,
        tmp_path,
        calling(ASK_OWN, (ToolName.SetQuestion, {"id": asked, "case_report_card": "own_part"})),
    )
    apply(flask_app, rows)

    assert cards(family)[asked] == "own_part"
    assert [q["text"] for q in stored(family).values()].count(OWN) == 1
    assert [(r["tool"], bool(r.get("refused"))) for r in rows] == [
        ("set_question", False),
        ("add_question", True),
    ]
