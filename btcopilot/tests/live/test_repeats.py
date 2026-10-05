"""Real coach turns that invite a repeat: a turn tried again after it failed, an
event said again, a person the record already holds, and a question the person
already answered. Each is scored on zero repeats, in the record and in what the
watcher after the turn wrote down.

Invented names only.
"""

import datetime
import re

import pytest
from mock import patch

from btcopilot import coverage, turns
from btcopilot.coachmodel import CoachModel
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import Discussion, Observation, ObservationKind, Statement
from btcopilot.schema import Fact, FactState, ItemKind
from btcopilot.tests.conftest import replied
from btcopilot.tests.live.criterion import once, passes


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


def repeats(coach) -> list[Observation]:
    """What the observer wrote down on this run's record, less the read it was
    not asked about and the failure a case breaks on purpose; a k of n case's
    earlier runs leave theirs on records of their own."""
    return Observation.query.filter(
        Observation.diagram_id == coach.user.free_diagram_id,
        Observation.kind.notin_([ObservationKind.AddWithoutRead, ObservationKind.TurnFailed]),
    ).all()


def named(people, name) -> list[dict]:
    return [p for p in people if p.get("name") == name]


SIBLINGS = "My sister Nell was born in 1990 and my brother Colm in 1993."


@once
def test_trying_a_failed_turn_again_repeats_nothing(coach):
    # R-0477, R-0481
    coach.record()
    with (
        patch("btcopilot.turns.model_for", lambda *a, **k: Breaks()),
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
    assert repeats(coach) == [], [(o.kind, o.detail) for o in repeats(coach)]


GRANDFATHER = {"id": 8, "name": "Joe", "last_name": "Hale", "gender": "male"}
DIED = {"id": 31, "kind": "death", "person": 8, "dateTime": "2010-03-15"}


# 2 of 3: the coach sometimes keeps "it hit my mom hard" as a new shift whose
# first try lacks a title, and the retry is written down as a refusal; that is
# not a repeat (seen once on the subscription, 2026-10-05).
@passes(2, of=3)
def test_an_event_said_again_is_not_added_again(coach):
    # R-0442, R-0481
    coach.record([GRANDFATHER], events=[DIED])
    coach.say("Like I said, my grandpa Joe died in March 2010. It hit my mom hard.")
    assert [e["id"] for e in coach.events if e.get("kind") == "death"] == [31]
    assert repeats(coach) == [], [(o.kind, o.detail) for o in repeats(coach)]


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
    "title": "Moved to Denver",
    "description": "Moved to Denver",
}


@once
def test_a_brother_the_record_holds_is_not_added_again(coach):
    # R-0479, R-0481
    coach.record([BROTHER], events=[BROTHER_BORN, BROTHER_LEFT])
    coach.say("My brother moved back home last month and he's sleeping on my couch.")
    assert [p["id"] for p in coach.people] == [1, 2, 3, 4]
    assert repeats(coach) == [], [(o.kind, o.detail) for o in repeats(coach)]


PARTNER = {"id": 5, "name": "Sam", "last_name": "Reyes", "gender": "male"}
COUPLE = {"id": 11, "person_a": 1, "person_b": 5, "married": True}
NO_CHILDREN = "Sam and I can't have children. We found out in 2019, after two rounds of IVF."
NEVER_A_FAMILY = "Sam and I were never able to start a family. We stopped trying in 2019."
FATHER_BORN = "Dad was born on 12 March 1956, and my parents are still married."
ABOUT_US = "What else do you want to know about Sam and me?"
ABOUT_PARENTS = "Anything else about my parents you need?"
# One sitting of other talk, long enough that what was said before it has
# left the words the coach reads back each turn, as 205 messages did on the
# thread this guards (R-0760).
FILLER = [
    "Work has been relentless this month.",
    "What makes it relentless?",
    "A new manager who changes the plan every week.",
    "How do you take that?",
    "I go quiet and get it done, then I'm exhausted at home.",
    "Who sees the exhausted side?",
    "Mostly the dog. And Mom, when she calls on Sundays.",
    "What does your mother make of it?",
    "She says I work too hard, like Dad did at the mill.",
    "Does that comparison fit, from where you sit?",
    "Partly. I don't drink like he did, but I do disappear into it.",
    "When did you first notice yourself disappearing into work?",
    "College, probably. Finals were the only time the house felt calm.",
    "Calm because everyone was busy, or because nobody was asking anything?",
    "Because nobody was asking anything of me.",
    "What did they usually ask of you?",
    "To keep the peace between Mom and Nell, mostly.",
    "How did you keep it?",
    "By being the easy one. Never a problem, never a need.",
    "Is that still the role you play with them?",
    "Yes, though Sam says I've started pushing back a little.",
    "What does pushing back look like?",
    "Saying no to Sunday dinner twice this year.",
    "What happened when you said no?",
    "Mom went quiet for a week, then acted like nothing happened.",
    "And your father?",
    "He stays out of it. He always has.",
    "What do you make of him staying out of it?",
    "I used to think it was peace. Now I think it's a way of not being there.",
    "Which of those weeks of quiet stand out to you?",
]


# A question whether they have, had or plan children; one about how they took
# learning they could not have them is a story to come back to (R-0770).
KIDS = r"\b(children|child|kids?|sons?|daughters?|baby|babies)\b"
HAVING = (
    r"\b(do|did|does|are|were|will|would|have|has)\s+(you|you two|you both|both of you|"
    r"you and Sam|Sam|we)\s+(ever\s+|still\s+|now\s+)?(have|had|want|wanted|plan|planning|"
    r"planned|hope|hoping|try|trying|think|thinking|considered|considering|adopt)\b[^?]{0,40}"
    + KIDS
    + r"|\b(any|how many)\s+(\w+\s+)?"
    + KIDS
    + r"|\bhaving\s+(\w+\s+)?"
    + KIDS
)

def asks(reply: str, who: str, what: str) -> list[str]:
    """The questions in the reply that name the person and the item."""
    return [
        q.strip()
        for q in re.findall(r"[^.?!]*\?", reply)
        if re.search(who, q, re.I) and re.search(what, q, re.I)
    ]


def sitting(coach, lines: list[str]) -> None:
    """A finished sitting of the person and the coach in turn, in the words the
    coach reads back and searches."""
    session = open_session(coach.user, coach.user.free_diagram)
    db.session.add_all(
        Statement(
            discussion_id=session.id,
            speaker_id=(session.chat_user_speaker_id if i % 2 == 0 else session.chat_ai_speaker_id),
            text=text,
            order=i,
        )
        for i, text in enumerate(lines)
    )
    db.session.commit()


def back(days: int) -> None:
    """Every sitting so far moved back in time."""
    for row in (*Statement.query.all(), *Discussion.query.all()):
        row.created_at -= datetime.timedelta(days=days)
        if isinstance(row, Discussion) and row.discussion_date:
            row.discussion_date -= datetime.timedelta(days=days)
    db.session.commit()


def opened(coach) -> None:
    response = coach.web.post("/app/sessions", json={}, headers={"X-CSRFToken": coach.token})
    assert response.status_code == 201, response.get_data(as_text=True)


def state(coach, fact: Fact, kind: ItemKind, iid: int) -> FactState:
    db.session.expire_all()
    return coverage.state_of(coach.user.free_diagram.get_diagram_data(), fact, kind, iid)


@passes(3, of=3)
def test_a_person_who_said_they_cannot_have_children_is_not_asked_about_children(coach):
    # R-0760
    coach.record([PARTNER], pair_bonds=[COUPLE])
    coach.say(NO_CHILDREN)
    assert state(coach, Fact.Children, ItemKind.PairBond, 11) is FactState.Known
    sitting(coach, FILLER)
    back(10)
    opened(coach)

    reply = coach.say(ABOUT_US)
    assert asks(reply, r"\b(you|your|we|Sam)\b", HAVING) == [], reply
    assert state(coach, Fact.Children, ItemKind.PairBond, 11) is FactState.Known


@passes(3, of=3)
def test_a_father_given_a_birth_date_and_still_married_is_not_asked_if_alive_or_his_age(coach):
    # R-0760
    coach.record()
    coach.say(FATHER_BORN)
    assert state(coach, Fact.BirthDate, ItemKind.Person, 3) is FactState.Known
    sitting(coach, FILLER)
    back(10)
    opened(coach)

    reply = coach.say(ABOUT_PARENTS)
    assert asks(
        reply,
        r"\b(dad|father|Hugh)\b",
        r"\b(alive|living|still with|still around|passed|died|how old|age|aged|born|birthday|birth date)\b",
    ) == [], reply
    assert state(coach, Fact.Alive, ItemKind.Person, 3) is FactState.Known


@passes(3, of=3)
def test_what_a_past_sitting_said_of_children_is_found_before_the_coach_asks(coach):
    # R-0760
    """The thread as it stood before questions were kept closed: the person said
    it in other words, nothing was stored, and the question tool's own search
    must find it (the paraphrase "start a family" is on the children word list)."""
    coach.record([PARTNER], pair_bonds=[COUPLE])
    sitting(coach, [NEVER_A_FAMILY, "That is a long road to have walked. How did the two of you carry it?", *FILLER])
    back(10)
    opened(coach)

    reply = coach.say(ABOUT_US)
    assert asks(reply, r"\b(you|your|we|Sam)\b", HAVING) == [], reply
