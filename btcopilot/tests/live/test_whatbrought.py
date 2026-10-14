"""What brought the person in, in two made-up first conversations (R-0854):
one that opens on a trip and one that opens on a sleep problem. Each ends with
the coach's note on the what_brought card, resting on the person's message.

Invented names only.
"""

import re

from btcopilot.extensions import db
from btcopilot.models import Discussion, Statement
from btcopilot.record import CARD, IMPRESSION, note
from btcopilot.schema import CaseReportCard, EvidenceKind, Fact
from btcopilot.tests.live.checks import questions
from btcopilot.tests.live.criterion import passes

# The prompt's limit on when the coach asks; the prompt line holds the number.
REPLIES = 10
# Another topic, told over ten messages, none of them why she came.
ELSEWHERE = [
    "I just got back from Lisbon. My brother Jude lives there now.",
    "He moved in 2021, right after he finished his degree.",
    "We walked everywhere. He knows every bakery in the old town.",
    "His girlfriend Marta came along most days. She's a nurse.",
    "Our mother calls him every Sunday, same time, without fail.",
    "Jude is the youngest. I'm the oldest, and Ivy is in the middle.",
    "Ivy couldn't come on the trip, her kids had school.",
    "The flight back was eleven hours with the layover.",
    "I brought back far too much coffee.",
    "Anyway, that was the trip.",
]
WHY = "I guess I came because I'm always the one in the middle of everyone's arguments, and I'm worn out by it."
OPENING = "I can't sleep and it's getting worse."
AFTER = [
    "It started in the spring, around when my dad moved in with us.",
    "Mostly I lie awake until three and then I'm useless at work.",
]
# A question asking what brings them, for one asked without keeping it.
ASKS = r"\b(brings? you|brought you|made you (decide|want)|reach(ed)? out|come here|came here|here today|looking for help)\b"


def asks_why(reply: str) -> bool:
    return any(re.search(ASKS, q, re.I) for q in questions(reply))


def kept(coach) -> list[dict]:
    """What the record keeps of it: questions naming the item, and the notes on
    its card."""
    db.session.expire_all()
    return [
        q
        for q in coach.user.free_diagram.get_diagram_data().questions
        if q.get("fact") == Fact.WhatBrought or q.get(CARD) == CaseReportCard.WhatBrought
    ]


def rests_on(coach, text: str) -> bool:
    """A note on the what_brought card rests on the person's message saying this."""
    talk = Discussion.query.filter_by(diagram_id=coach.user.free_diagram_id).one()
    said = Statement.query.filter_by(
        discussion_id=talk.id, speaker_id=talk.chat_user_speaker_id, text=text
    ).one()
    return any(
        note(q) is IMPRESSION
        and q.get(CARD) == CaseReportCard.WhatBrought
        and any(e["kind"] == EvidenceKind.Statement and e["id"] == said.id for e in q["evidence"])
        for q in kept(coach)
    )


@passes(8, of=10)
def test_the_coach_follows_another_topic_and_asks_what_brings_them_by_its_tenth_reply(coach):
    # R-0854, R-0852
    coach.record()
    lines = iter(ELSEWHERE)
    for _ in range(REPLIES):
        reply = coach.say(next(lines))
        if asks_why(reply) or any(q.get("fact") == Fact.WhatBrought for q in kept(coach)):
            break
    else:
        raise AssertionError(f"not asked by reply {REPLIES}")
    coach.say(WHY)
    assert rests_on(coach, WHY), kept(coach)


@passes(8, of=10)
def test_the_coach_writes_down_what_brings_them_when_they_say_it_and_never_asks(coach):
    # R-0854, R-0852
    coach.record()
    replies = [coach.say(OPENING)]
    assert rests_on(coach, OPENING), kept(coach)
    replies += [coach.say(line) for line in AFTER]
    assert not any(asks_why(r) for r in replies), replies
    assert not any(q.get("fact") == Fact.WhatBrought for q in kept(coach)), kept(coach)
