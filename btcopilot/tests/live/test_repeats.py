"""Real coach turns that invite a repeat: a turn tried again after it failed, an
event said again, and a person the record already holds. Each is scored on
zero repeats, in the record and in what the watcher after the turn wrote down.

Invented names only.
"""

import pytest
from mock import patch

from btcopilot import turns
from btcopilot.coachmodel import CoachModel
from btcopilot.models import Observation, ObservationKind
from btcopilot.tests.conftest import replied
from btcopilot.tests.live.criterion import once


class Breaks:
    """The real coach, cut off after its first round of tool calls, the way a
    turn stops when the model's service goes down halfway through."""

    def __init__(self):
        self.real = CoachModel()
        self.rounds = 0

    def turn(self, system, messages, tools, turn_id=""):
        self.rounds += 1
        if self.rounds == 2:
            raise RuntimeError("the model went away")
        return (yield from self.real.turn(system, messages, tools, turn_id))


def repeats() -> list[Observation]:
    return Observation.query.filter(
        Observation.kind != ObservationKind.AddWithoutRead
    ).all()


def named(people, name) -> list[dict]:
    return [p for p in people if p.get("name") == name]


SIBLINGS = "My sister Nell was born in 1990 and my brother Colm in 1993."


@once
def test_trying_a_failed_turn_again_repeats_nothing(coach):
    # R-0477, R-0481
    coach.record()
    with (
        patch("btcopilot.coachturn.CoachModel", Breaks),
        patch("btcopilot.turns.enqueue"),
    ):
        body = coach.web.post(
            "/app/chat",
            json={"statement": SIBLINGS},
            headers={"X-CSRFToken": coach.token},
        ).get_json()
        with pytest.raises(RuntimeError):
            turns.run(body["turn_id"], body["discussion_id"], body["statement_id"])
    response = coach.web.post(
        f"/app/turns/{body['turn_id']}/resume", headers={"X-CSRFToken": coach.token}
    )
    replied(response)
    assert [len(named(coach.people, n)) for n in ("Nell", "Colm")] == [1, 1]
    assert repeats() == []


GRANDFATHER = {"id": 8, "name": "Joe", "last_name": "Hale", "gender": "male"}
DIED = {"id": 31, "kind": "death", "person": 8, "dateTime": "2010-03-15"}


@once
def test_an_event_said_again_is_not_added_again(coach):
    # R-0442, R-0481
    coach.record([GRANDFATHER], events=[DIED])
    coach.say("Like I said, my grandpa Joe died in March 2010. It hit my mom hard.")
    assert [e["id"] for e in coach.events if e.get("kind") == "death"] == [31]
    assert repeats() == []


BROTHER = {"id": 4, "name": "Colm", "gender": "male", "parents": 10}
BROTHER_BORN = {
    "id": 32,
    "kind": "birth",
    "person": 2,
    "spouse": 3,
    "child": 4,
    "dateTime": "1988-06-02",
}
BROTHER_LEFT = {
    "id": 33,
    "kind": "noted",
    "person": 4,
    "dateTime": "2015-08-01",
    "description": "Moved to Denver",
}


@once
def test_a_brother_the_record_holds_is_not_added_again(coach):
    # R-0479, R-0481
    coach.record([BROTHER], events=[BROTHER_BORN, BROTHER_LEFT])
    coach.say("My brother moved back home last month and he's sleeping on my couch.")
    assert [p["id"] for p in coach.people] == [1, 2, 3, 4]
    assert repeats() == []
