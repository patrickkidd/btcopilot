"""When the person gives the coach the floor, the coach's own next question
maps the family's structure (who is whose parent, how many children each
couple had, the bonds and their dates) before any story it would open itself;
when the person brings a topic, the coach follows them and the structure item
waits; and a fact the person says they will find out stays asked, never closed
as unknown.

Invented names only.
"""

import re

from btcopilot.coverage import STRUCTURE
from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import Fact, QuestionKind, QuestionState
from btcopilot.tests.live.checks import questions as asked
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.live.test_mostgoingon import sitting
from btcopilot.toolbox import ToolName, Toolbox

# What brings her, and the two moves she named as the times the most was going on.
EVENTS = [
    {"id": 31, "kind": "noted", "person": 1, "dateTime": "1996-06-01", "dateCertainty": "approximate", "title": "Moved to Oregon", "description": "The family moved to Oregon", "item": "places"},
    {"id": 32, "kind": "noted", "person": 1, "dateTime": "2024-03-01", "dateCertainty": "approximate", "title": "Moved to Portland", "description": "Moved to Portland for work", "item": "places"},
    {"id": 33, "kind": "shift", "person": 1, "dateTime": "2024-07-01", "dateCertainty": "approximate", "symptom": "up", "title": "Freezes up when her mother calls", "description": "Freezes up whenever her mother calls"},
]
# An earlier sitting the same day: what brings her, when it began, and the
# times the most was going on, asked and answered.
EARLIER = [
    "I want to understand why I freeze up whenever my mother calls.",
    "When did that start?",
    "About two years ago, a few months after I moved to Portland.",
    "Looking back over your life so far, what were the two or three times when the most was going on, and about what years were they?",
    "The year we moved to Oregon, around 1996, and 2024 when I moved to Portland.",
    "Thank you. We'll come back to both of those.",
]
FLOOR = "That's about all I can think of for now. What else do you need to know?"
STORY = "My sister Nell called last night and we ended up arguing about Mom's care again. I hung up on her."
# The structure items as a reply words them, for a question kept without its fact.
STRUCTURE_WORDS = (
    r"\b(parents?|grandparents?|grandmother|grandfather|married|marriage|marry|husband|wife|"
    r"partner|children|kids|brothers?|sisters?|siblings?|only child)\b"
)
STORY_WORDS = r"\b(nell|sister|argu\w*|hung up|mom|mother|call\w*|care)\b"
# The item the coach is left asking in the facts-to-find case, and the answer that
# sounds like unknown but says the person will ask.
BORN = "When was your father born?"
WILL_ASK = (
    "Honestly, no idea. Dad never talked about himself and I never asked. I suppose I could "
    "ask my mom sometime."
)


def kept(coach, lines: list[str]) -> Statement:
    """The earlier sitting, its last line the person's, with the times the most
    was going on kept as a question already answered by that line."""
    sitting(coach, lines)
    said = Statement.query.filter(Statement.text == lines[-2]).order_by(Statement.id.desc()).first()
    Toolbox(
        coach.user.free_diagram.id,
        "t0",
        user_id=coach.user.id,
        session_id=said.discussion_id,
        said=said,
    ).call(
        ToolName.AddQuestion,
        {
            "text": lines[3],
            "kind": "fact",
            "state": "resolved",
            "outcome": "answered",
            "fact": Fact.MostGoingOn.value,
            "item_kind": "person",
            "item_id": "1",
        },
    )
    db.session.commit()
    return said


def questions_of(coach) -> list[dict]:
    db.session.expire_all()
    return coach.user.free_diagram.get_diagram_data().questions


def filed(before: list[dict], after: list[dict]) -> list[dict]:
    """The fact questions the turn kept asked."""
    had = {q["id"] for q in before}
    return [
        q
        for q in after
        if q["id"] not in had and q["kind"] == QuestionKind.Fact and q["state"] == QuestionState.Asked
    ]


@passes(2, of=3)
def test_given_the_floor_the_coach_asks_a_structure_item_before_a_story(coach):
    # R-0618, R-0006
    # Patrick, 2026-10-07: "the basic family structure should be mapped out at least
    # earlier than later. Definitely before any Coach driven rabbit holes on stories".
    coach.record(events=EVENTS)
    kept(coach, EARLIER)
    before = questions_of(coach)

    reply = coach.say(FLOOR)

    new = filed(before, questions_of(coach))
    facts = [q.get("fact") for q in new]
    assert asked(reply), reply
    assert any(Fact(f) in STRUCTURE for f in facts if f) or any(
        re.search(STRUCTURE_WORDS, q, re.I) for q in asked(reply)
    ), (facts, reply)


@passes(2, of=3)
def test_a_topic_the_person_brings_is_followed_and_the_structure_item_waits(coach):
    # R-0815, R-0618
    # Patrick, 2026-10-07: "I specifically said Coach driven questions. When the
    # client wants to talk about something the coach has to follow them."
    coach.record(events=EVENTS)
    kept(coach, EARLIER)
    before = questions_of(coach)

    reply = coach.say(STORY)

    new = filed(before, questions_of(coach))
    unrelated = [q for q in new if q.get("fact") in (Fact.Parents, Fact.Marriages, Fact.Met)]
    assert unrelated == [], (unrelated, reply)
    first = asked(reply)
    assert first and re.search(STORY_WORDS, first[0], re.I), reply


@passes(2, of=3)
def test_a_fact_the_person_will_find_out_stays_asked_not_closed_unknown(coach):
    # R-0803
    # Patrick, 2026-10-07: "Yes" to keeping a question open when the person says
    # they will find out, instead of closing it as unknown.
    coach.record(events=EVENTS)
    said = kept(coach, EARLIER)
    Toolbox(
        coach.user.free_diagram.id,
        "t1",
        user_id=coach.user.id,
        session_id=said.discussion_id,
    ).call(
        ToolName.AddQuestion,
        {"text": BORN, "kind": "fact", "state": "asked", "fact": "birth_date", "item_kind": "person", "item_id": "3"},
    )
    db.session.commit()

    coach.say(WILL_ASK)

    born = next(q for q in questions_of(coach) if q["text"] == BORN)
    assert (born["state"], born["outcome"]) == (QuestionState.Asked, None), born
