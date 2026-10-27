"""Live checks of the scribe on the faults of a production coding on
2026-10-25: an age dated with an invented year, a coder's question written as
an event, and a birth given later that left the wrong year in place
(R-0940 to R-0943), and of one on 2026-10-27: asked how a person's parents
were added, the scribe said they were there from the beginning when a
distance note of the coder's had added them (R-0946). The family is invented.
The run stops at CAP dollars of model calls.
"""

import datetime
from decimal import Decimal

import pytest

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, Speaker, SpeakerType, Statement
from btcopilot.review import adapter, scribe
from btcopilot.review.models import Cut, Note
from btcopilot.tests.live.criterion import once, passes
from btcopilot.tests.review.conftest import coded

CAP = Decimal("0.50")

ANN = {"id": 1, "name": "Ann", "last_name": "Lee", "gender": "female", "primary": True}
BORN = {"id": 2, "kind": "birth", "child": 1, "dateTime": "1980-05-11", "dateCertainty": "certain"}
GIVEN = {"people": [ANN], "events": [BORN], "lastItemId": 2}
UNBORN = {"people": [ANN], "lastItemId": 1}
LINE = "Things got hard at home when I was sixteen, I stopped eating properly."
AGE = "Symptom up for Ann when she was 16"


@pytest.fixture(autouse=True)
def capped(run):
    run.cap = min(run.cap, CAP)


def coding_of(user, record: dict):
    case = Diagram(user_id=user.id, name="Case", data=diagramjson.dumps({}))
    db.session.add(case)
    db.session.flush()
    discussion = Discussion(user_id=user.id, diagram_id=case.id)
    db.session.add(discussion)
    db.session.flush()
    speaker = Speaker(discussion_id=discussion.id, name="Ann", type=SpeakerType.Subject)
    db.session.add(speaker)
    db.session.flush()
    statement = Statement(discussion_id=discussion.id, speaker_id=speaker.id, text=LINE, order=0)
    db.session.add(statement)
    db.session.flush()
    cut = Cut(
        diagram_id=case.id,
        start_statement_id=statement.id,
        end_statement_id=statement.id,
        user_id=user.id,
        meeting_date=datetime.date(2026, 10, 1),
    )
    db.session.add(cut)
    db.session.commit()
    return coded(user, cut, record, done=False), statement


def told(coding, statement, words: str) -> dict:
    """The scribe's answer, with the coder's words kept on the coding as the
    route keeps them."""
    result = scribe.write(coding, statement, words)
    db.session.add(
        Note(coding_id=coding.id, statement_id=statement.id, text=words, turn_id=result["turn_id"])
    )
    db.session.commit()
    return result


def events(coding) -> list[dict]:
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    return [
        e
        for e in data.get("events") or []
        if (e["id"], adapter.plain(e.get("kind"))) != (BORN["id"], "birth")
    ]


def shifts(coding) -> list[dict]:
    return [e for e in events(coding) if adapter.plain(e.get("kind")) == "shift"]


def dated(event: dict) -> tuple:
    return (
        (adapter.date_text(event.get("dateTime")) or "")[:4],
        adapter.plain(event.get("dateCertainty")),
    )


@once
def test_an_age_is_dated_from_the_birth_in_the_diagram(test_user):
    # R-0943, R-0940
    """Passes when the one event entered is a symptom-up shift dated 1996,
    marked approximate."""
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, AGE)
    entered = events(coding)
    assert [(adapter.plain(e["kind"]), adapter.plain(e.get("symptom"))) for e in entered] == [
        ("shift", "up")
    ], entered
    assert dated(entered[0]) == ("1996", "approximate"), entered


@once
def test_an_age_with_no_birth_in_the_diagram_has_no_date(test_user):
    # R-0943
    """Passes when the one event entered is a symptom-up shift with no date."""
    coding, statement = coding_of(test_user, UNBORN)
    told(coding, statement, AGE)
    entered = events(coding)
    assert [adapter.plain(e["kind"]) for e in entered] == ["shift"], entered
    assert not adapter.date_text(entered[0].get("dateTime")), entered


@once
def test_a_question_is_answered_and_writes_nothing(test_user):
    # R-0942
    """Passes when the answer has words and the diagram's version is unchanged."""
    coding, statement = coding_of(test_user, UNBORN)
    before = adapter.diagram_of(coding.diagram_id).version
    result = told(coding, statement, "Do you have a birthdate for her yet?")
    assert result["reply"].strip(), result
    assert (result["lines"], adapter.diagram_of(coding.diagram_id).version) == ([], before), result


@once
def test_a_birth_given_after_an_age_dates_the_earlier_event(test_user):
    # R-0941, R-0943
    """Passes when the second message carries the first statement and the
    shift ends dated 1996, marked approximate, the only shift on the diagram."""
    coding, statement = coding_of(test_user, UNBORN)
    told(coding, statement, AGE)
    assert "- " + AGE in scribe._earlier(coding, adapter.record_of(adapter.diagram_of(coding.diagram_id)))
    told(coding, statement, "She was born in 1980")
    (shift,) = shifts(coding)
    assert dated(shift) == ("1996", "approximate"), events(coding)


@passes(2, of=3)
def test_a_question_about_how_people_were_added_names_the_statement_that_added_them(test_user):
    # R-0946
    """Passes when the distance note wrote something and the answer to how her
    parents were added speaks of that distance note and never says they were
    there from the beginning."""
    coding, statement = coding_of(test_user, GIVEN)
    wrote = told(coding, statement, "Add distance from Ann to her parents")
    assert wrote["lines"], wrote
    answer = told(coding, statement, "How were her parents added?")["reply"].lower()
    assert "distance" in answer, answer
    assert "beginning" not in answer, answer
