"""On a thread with years behind it, the coach asks once which two or three
times the most was going on: not as the first question when the person comes
with something specific, soon after, and never again in a later sitting.

Invented names only.
"""

import datetime

from btcopilot.extensions import db
from btcopilot.models import Discussion, Speaker, SpeakerType, Statement
from btcopilot.schema import Fact
from btcopilot.tests.live.criterion import passes

SISTER = {"id": 4, "name": "Nell", "last_name": "Hale", "gender": "female", "parents": 10}
EVENTS = [
    {"id": 31, "kind": "birth", "person": 2, "spouse": 3, "child": 4, "dateTime": "1988-02-03", "dateCertainty": "certain"},
    {"id": 32, "kind": "noted", "person": 1, "dateTime": "2009-09-01", "dateCertainty": "approximate", "title": "Left for college", "description": "Moved to Ohio for college"},
    {"id": 33, "kind": "shift", "person": 3, "dateTime": "2010-01-01", "dateCertainty": "approximate", "symptom": "up", "title": "Lost his job", "description": "Laid off from the mill"},
    {"id": 34, "kind": "noted", "person": 4, "dateTime": "2010-06-01", "dateCertainty": "approximate", "title": "Moved back home", "description": "Came home to help"},
]
CLUSTERS = [{"id": "mill", "title": "The year the mill closed", "summary": "", "eventIds": [32, 33, 34]}]
# Two earlier sittings ten days apart, as a thread with weeks behind it
# leaves them.
EARLIER = [
    [
        "I want to understand why I always end up the one holding things together.",
        "What happens in the family when something goes wrong?",
        "The year the mill closed Dad lost his job and Nell came home to help.",
        "Who did what that year?",
    ],
    [
        "Mom calls me every Sunday and it's mostly about Nell.",
        "What does she say about her?",
        "That Nell is struggling and I should check on her more.",
        "How do you answer her?",
    ],
]
OPENING = "My sister Nell and I haven't spoken since Dad's birthday dinner. She said I never show up for the family."
WHEN = "It started about two years ago, when Dad got sick and I moved across the country for work."
THEN = "I just feel stuck about whether to call her."
BACK = "Hi, I'm back. Nell texted me yesterday."


def asked(coach) -> list[dict]:
    """The kept questions naming the item; one on a named span names none."""
    db.session.expire_all()
    return [
        q
        for q in coach.user.free_diagram.get_diagram_data().questions
        if q.get("fact") == Fact.MostGoingOn.value
    ]


def back(days: int) -> None:
    """Every sitting so far moved back in time."""
    for row in (*Statement.query.all(), *Discussion.query.all()):
        row.created_at -= datetime.timedelta(days=days)
        if isinstance(row, Discussion) and row.discussion_date:
            row.discussion_date -= datetime.timedelta(days=days)
    db.session.commit()


def sitting(coach, lines: list[str]) -> None:
    """A finished sitting: the person and the coach in turn."""
    talk = Discussion(
        user_id=coach.user.id,
        diagram_id=coach.user.free_diagram_id,
        summary=lines[0],
        discussion_date=datetime.date.today(),
    )
    db.session.add(talk)
    db.session.flush()
    person = Speaker(discussion_id=talk.id, name="Wren", type=SpeakerType.Subject, person_id=1)
    expert = Speaker(discussion_id=talk.id, name="Coach", type=SpeakerType.Expert)
    db.session.add_all([person, expert])
    db.session.flush()
    talk.chat_user_speaker_id, talk.chat_ai_speaker_id = person.id, expert.id
    db.session.add_all(
        Statement(
            discussion_id=talk.id,
            speaker_id=(person if i % 2 == 0 else expert).id,
            text=text,
            order=i,
        )
        for i, text in enumerate(lines)
    )
    db.session.commit()


def opened(coach) -> None:
    response = coach.web.post("/app/sessions", json={}, headers={"X-CSRFToken": coach.token})
    assert response.status_code == 201, response.get_data(as_text=True)


@passes(3, of=3)
def test_the_coach_asks_once_soon_after_the_person_says_what_brings_them(coach):
    # R-0735
    coach.record([SISTER], events=EVENTS)
    data = coach.user.free_diagram.get_diagram_data()
    data.clusters = CLUSTERS
    coach.user.free_diagram.set_diagram_data(data)
    db.session.commit()
    for lines in EARLIER:
        sitting(coach, lines)
        back(10)
    assert asked(coach) == []

    opened(coach)
    coach.say(OPENING)
    assert asked(coach) == []

    coach.say(WHEN)
    coach.say(THEN)
    assert len(asked(coach)) == 1

    back(3)
    opened(coach)
    coach.say(BACK)
    assert len(asked(coach)) == 1


PANIC = {"id": 35, "kind": "shift", "person": 1, "dateTime": "2024-03-01", "dateCertainty": "approximate", "symptom": "up", "title": "Panic attacks", "description": "Panic attacks at work began"}
# What brings her and when it began were said weeks ago; the question was not
# asked then.
SAID = [
    [
        "I came because I've been having panic attacks at work.",
        "When did they start?",
        "About March of last year, right after my promotion.",
        "What was happening at home around then?",
    ],
    [
        "The attacks were bad again this week, twice in meetings.",
        "Who did you tell?",
        "Only my husband. I don't want my parents to worry.",
        "How does he take it?",
    ],
]
ELSEWHERE = "My mom's birthday is next week and I can't decide what to get her."


@passes(3, of=3)
def test_the_coach_asks_in_its_next_reply_once_the_record_holds_what_brings_them(coach):
    # R-0762
    coach.record(events=[PANIC])
    for lines in SAID:
        sitting(coach, lines)
        back(10)
    assert asked(coach) == []

    opened(coach)
    reply = coach.say(ELSEWHERE)
    assert "two or three times when the most was going on" in reply, reply
    assert len(asked(coach)) == 1
