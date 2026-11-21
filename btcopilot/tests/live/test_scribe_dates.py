"""The coding scribe dates what a coder says by the three kinds (R-0958,
R-0956, R-0957): a life stage counted from the birth of the person the case
belongs to is an estimate marked unknown with the coder's words kept, even on
a copy that lacks the birth; an order said places the event after its bound;
a standing pattern has no date and never a stand-in year. A case passes when
2 of 3 runs leave the copy as stated.

Run on the coach's Claude model through the subscription, not on the scribe's
Gemini, so it spends nothing: it proves the prompt and the tools, not the
Gemini model's reading of them.

Fails on the old prompt and tools: the tools required a date on every event
and kept no words about when, so a coder's undated note took a stand-in year.

The family is invented.
"""

import pytest

from btcopilot import diagramjson, record
from btcopilot.coachmodel import CoachModel
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.review import adapter
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_scribe_evals import ANN, BORN, UNBORN, coding_of, events, told

MEMA = {"id": 3, "name": "Mema", "gender": "female"}
MEMA_DIED = {"id": 4, "kind": "death", "person": 3, "dateTime": "1990-06-01", "dateCertainty": "certain"}
WITH_MEMA = {"people": [ANN, MEMA], "events": [MEMA_DIED], "lastItemId": 4}


@pytest.fixture(autouse=True)
def claude(monkeypatch):
    monkeypatch.setattr(adapter, "scribe_model", lambda name: CoachModel())


def case_of(user, copy: dict):
    """A coding copy whose case diagram holds Ann and her birth."""
    coding, statement = coding_of(user, copy)
    db.session.get(Diagram, coding.cut.diagram_id).data = diagramjson.dumps({"people": [ANN], "events": [BORN], "lastItemId": 2})
    db.session.commit()
    return coding, statement


def year(event: dict) -> int | None:
    written = adapter.date_text(event.get("dateTime"))
    return int(written[:4]) if written else None


@passes(2, of=3)
def test_a_life_stage_is_counted_from_the_cases_birth_and_marked_unknown(test_user):
    # R-0958, R-0957, R-0940
    coding, statement = case_of(test_user, UNBORN)
    told(coding, statement, "Ann's anxiety went up around high school")
    (shift,) = events(coding)
    assert 1994 <= (year(shift) or 0) <= 1999, shift
    assert adapter.plain(shift.get("dateCertainty")) == "unknown", shift
    assert "high school" in (shift.get("dateEvidence") or ""), shift


@passes(2, of=3)
def test_an_order_said_places_the_event_after_its_bound(test_user):
    # R-0958, R-0957
    coding, statement = case_of(test_user, WITH_MEMA)
    told(coding, statement, "After Mema died, Ann stopped eating properly")
    entered = [e for e in events(coding) if e["id"] != MEMA_DIED["id"]]
    assert entered, "nothing was entered"
    assert all((year(e) or 0) >= 1990 for e in entered), entered
    assert all("after" in (e.get("dateEvidence") or "").lower() for e in entered), entered


@passes(2, of=3)
def test_a_standing_pattern_has_no_date_and_no_stand_in_year(test_user):
    # R-0958, R-0956
    coding, statement = case_of(test_user, UNBORN)
    told(coding, statement, "Ann's father was always a drinker")
    entered = events(coding)
    assert entered, "nothing was entered"
    assert all(not e.get("dateTime") for e in entered), entered
    assert not any(record.standin_day(e.get("dateTime")) for e in entered), entered
