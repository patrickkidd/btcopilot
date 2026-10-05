"""The one pass that puts each family's raised guesses on the case report's
cards: it writes only cards on guesses already there and one own part
question, refuses every other call, and skips a family with a card already.

Invented names only.
"""

import json

import pytest
from mock import patch

from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Change, ModelCall, Purpose
from btcopilot.tests.conftest import Model, calling, said
from btcopilot.tests.test_casereport import OWN, card, cards, raised
from btcopilot.tests.test_impressions import LATCH, TENSE
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.tests.test_questions import stored
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolName


@pytest.fixture
def guesses(family, past):
    raised(family, TENSE, LATCH)
    return stored(family)


def backfill(flask_app, *turns, args=()) -> tuple[list[dict], Model]:
    model = Model(*turns)
    with patch("btcopilot.admin.casereport.model_for", return_value=model):
        result = flask_app.test_cli_runner().invoke(
            admin, ["case-report", "backfill", *args, "--json"]
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output), model


MAIN = (ToolName.SetImpression, {"id": "i1", "case_report_card": "main_guess"})
ASK_OWN = (
    ToolName.AddQuestion,
    {"text": OWN, "kind": "thought", "state": "asked", "case_report_card": "own_part"},
)


def test_a_dry_run_shows_the_cards_and_writes_nothing(flask_app, family, guesses):
    # R-0739
    changes = Change.query.count()
    rows, _ = backfill(flask_app, calling(MAIN, ASK_OWN))

    assert [(r["entry"], r["card_before"], r["card_after"]) for r in rows] == [
        ("i1", None, "main_guess"),
        ("new", None, "own_part"),
    ]
    assert rows[0]["owner"] == family.user_id
    assert stored(family) == guesses
    assert Change.query.count() == changes
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_apply_puts_only_cards_on_the_guesses_and_adds_the_own_part_question(
    flask_app, family, guesses
):
    # R-0739
    rows, _ = backfill(flask_app, calling(MAIN, ASK_OWN), args=["--apply"])

    after = stored(family)
    assert cards(family) == {"i1": "main_guess", "i2": None, "q1": "own_part"}
    assert {k: v for k, v in after["i1"].items() if k != "case_report_card"} == {
        k: v for k, v in guesses["i1"].items() if k != "case_report_card"
    }
    assert after["i2"] == guesses["i2"]
    assert after["q1"]["text"] == OWN
    assert [r["entry"] for r in rows] == ["i1", "q1"]


def test_every_other_call_is_refused_and_writes_nothing(flask_app, family, guesses):
    # R-0739
    data = family.get_diagram_data()
    rows, _ = backfill(
        flask_app,
        calling(
            (ToolName.AddImpression, {"text": "New.", "state": "raised", "evidence": []}),
            (ToolName.SetImpression, {"id": "i1", "text": "Reworded."}),
            (ToolName.SetImpression, {"id": "i1", "state": "resolved"}),
            (ToolName.SetImpression, {"id": "i9", "case_report_card": "main_guess"}),
            (ToolName.EditPerson, {"id": 1, "name": "Nell"}),
            (ToolName.AddQuestion, {"text": "Why?", "kind": "fact", "state": "asked"}),
        ),
        args=["--apply"],
    )

    assert all(r["refused"] for r in rows)
    db.session.expire_all()
    assert family.get_diagram_data() == data


def test_a_family_with_a_card_already_is_skipped(flask_app, family, guesses):
    # R-0739
    card(family, "i2", "work_on")
    rows, model = backfill(flask_app, args=["--apply"])

    assert rows == []
    assert model.histories == []


def test_the_own_part_question_is_added_once(flask_app, family, guesses):
    # R-0739
    rows, _ = backfill(flask_app, calling(ASK_OWN, ASK_OWN), args=["--apply"])

    own = [q for q in stored(family).values() if q.get("case_report_card") == "own_part"]
    assert len(own) == 1
    assert rows[1]["refused"]


def test_said_alone_sets_no_card(flask_app, family, guesses):
    # R-0739
    rows, _ = backfill(flask_app, said("Nothing to mark."), args=["--apply"])

    assert rows[0]["refused"] == "no cards set"
    assert stored(family) == guesses
