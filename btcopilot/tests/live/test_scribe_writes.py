"""Live checks of the scribe on faults a sweep of the first coding meeting's
codings found (R-0971, R-0956, R-0489): a coder's "take out this duplicate
passage" deleted a person with her pair-bond and twelve events; a relationship
move was aimed at a made-up group entry, "Ann's family", as if it were a
person; and a second event of the same kind for the same person in the same
estimated year was refused as already there, then folded into the first. A
case passes when 2 of 3 runs leave the copy as stated.

Run on the coach's Claude model through the subscription, not on the scribe's
Gemini, so it spends nothing: it proves the prompt and the tools, not the
Gemini model's reading of them.

The family is invented.
"""

import re

import pytest

from btcopilot.coachmodel import CoachModel
from btcopilot.review import adapter
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_scribe_evals import ANN, BORN, coding_of, events, told

GIVEN = {"people": [ANN], "events": [BORN], "lastItemId": 2}
GROUP = re.compile(r"\b(family|siblings|relatives|kids|children|parents|brothers|sisters)\b", re.I)


@pytest.fixture(autouse=True)
def claude(monkeypatch):
    monkeypatch.setattr(adapter, "scribe_model", lambda name: CoachModel())


def diagram(coding) -> dict:
    return adapter.record_of(adapter.diagram_of(coding.diagram_id))


@passes(2, of=3)
def test_a_vague_delete_asks_and_deletes_nothing(test_user):
    # R-0971, R-0942
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, "Ann's sister Mia lost her job in 2001, moved to the coast in 2003 and stopped calling home in 2005")
    before = diagram(coding)
    assert len(events(coding)) >= 3, before
    result = told(coding, statement, "Take out this duplicate passage")
    after = diagram(coding)
    assert [p["id"] for p in after["people"]] == [p["id"] for p in before["people"]], after
    assert len(after.get("events") or []) == len(before.get("events") or []), after
    assert result["reply"].strip(), result


@passes(2, of=3)
def test_a_move_toward_a_group_never_adds_the_group_as_a_person(test_user):
    # R-0971
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, "Add distance from Ann to her family starting when she moved out in 1999")
    data = diagram(coding)
    assert not [p for p in data["people"] if GROUP.search(p.get("name") or "")], data["people"]


@passes(2, of=3)
def test_two_events_of_one_kind_in_one_estimated_year_are_both_kept(test_user):
    # R-0971, R-0956, R-0489
    coding, statement = coding_of(test_user, GIVEN)
    told(coding, statement, "Ann's anxiety went up around 1996 when her father lost his job")
    told(coding, statement, "Separately, Ann's anxiety went up again around 1996 when her grandmother got sick")
    ups = [
        e
        for e in events(coding)
        if adapter.plain(e.get("kind")) == "shift" and adapter.plain(e.get("anxiety")) == "up"
    ]
    assert len(ups) == 2, events(coding)
