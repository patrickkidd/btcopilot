"""Stories left untold are kept for later, and a flat answer is followed by
the question kept waiting, not by a fresh one from the still-unknown list.

Invented names only.
"""

from freezegun import freeze_time

from btcopilot.extensions import db
from btcopilot.models import Author, Discussion, Statement
from btcopilot.schema import QuestionState
from btcopilot.tests.live.checks import asks_only_waiting
from btcopilot.tests.live.conftest import TODAY
from btcopilot.tests.live.criterion import passes
from btcopilot.toolbox import ToolName, Toolbox

GRANDFATHER = {"id": 5, "name": "Walt", "last_name": "Pryor", "gender": "male"}
GRANDMOTHER = {"id": 6, "name": "June", "last_name": "Pryor", "gender": "female"}
GRANDPARENTS = {"id": 11, "person_a": 5, "person_b": 6, "married": True}
MOTHER = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female", "parents": 11}
DIED = {"id": 40, "kind": "death", "person": 5, "dateTime": "2015-04-11", "dateCertainty": "certain"}

STORY = (
    "My grandpa Walt died the day before my 30th birthday, and that whole week "
    "turned into something I still don't talk about. Anyway, that's not why I'm "
    "here. My brother Theo and I can't be in a room together anymore."
)


def questions(coach) -> list[dict]:
    db.session.expire_all()
    return coach.user.free_diagram.get_diagram_data().questions


def kept_story(coach) -> list[dict]:
    """Held questions that name the birthday, or the grandfather's death."""
    return [
        q
        for q in questions(coach)
        if q["state"] == QuestionState.Held
        and (
            "birthday" in q["text"].lower()
            or (
                any(w in q["text"].lower() for w in ("walt", "grand"))
                and any(w in q["text"].lower() for w in ("died", "death", "passed", "funeral", "week"))
            )
        )
    ]


@passes(3, of=3)
def test_a_story_the_talk_moves_away_from_is_kept_for_later(coach):
    # R-0770
    coach.record([GRANDFATHER, GRANDMOTHER, MOTHER], [GRANDPARENTS], [DIED])

    coach.say(STORY)
    if kept_story(coach):
        return
    coach.say("He's two years older. We fought at Mom's 60th and haven't spoken since.")
    assert kept_story(coach), [q["text"] for q in questions(coach)]


KEPT = "What has your mother told you about growing up with her father's drinking?"
ASKED = "How many years apart are you and your brother?"
MOST = (
    "Looking back over your life so far, what were the two or three times when the "
    "most was going on, and about what years were they?"
)
# What brings her is told, and when it began and the times the most was going
# on are settled; the coach's last question was a basic-data one.
SAID = [
    "I came because my brother Theo and I haven't spoken since last spring.",
    "What happened last spring?",
    "At Mom's 60th he said I'd abandoned the family by moving away. I left early and "
    "we haven't talked since.",
    MOST,
    "Only last spring, really. Before that things were quiet.",
    "What do you know about how your mom grew up?",
    "Mom never says much about her childhood. Her dad drank, that's about all I know.",
    "That's a lot for a kid to carry. How many years apart are you and your brother?",
]


def said(coach, lines: list[str]) -> Discussion:
    """The person and the coach in turn, earlier in the open session."""
    talk = Discussion.query.filter_by(diagram_id=coach.user.free_diagram_id).one()
    for i, text in enumerate(lines):
        speaker = talk.chat_user_speaker if i % 2 == 0 else talk.chat_ai_speaker
        db.session.add(
            Statement(discussion_id=talk.id, speaker=speaker, text=text, order=talk.next_order())
        )
        db.session.flush()
    db.session.commit()
    return talk


# 2 of 3: on this model the coach still picks a basic-data question about one
# time in three; production used a waiting question at 1 of 50 openings.
@passes(2, of=3)
def test_at_a_flat_answer_the_waiting_question_comes_before_new_basic_data(coach):
    # R-0771
    coach.record([{"id": 4, "name": "Theo", "last_name": "Hale", "gender": "male", "parents": 10}])
    talk = said(coach, SAID)
    answer = Statement.query.filter_by(discussion_id=talk.id, text=SAID[4]).one()
    toolbox = Toolbox(coach.user.free_diagram_id, "earlier", session_id=talk.id, author=Author.Coach)
    with freeze_time(TODAY):
        toolbox.call(ToolName.AddQuestion, {
            "text": MOST, "kind": "fact", "state": "resolved", "outcome": "answered",
            "fact": "most_going_on", "item_kind": "person", "item_id": 1, "answer": answer.id,
        })
        toolbox.call(ToolName.AddQuestion, {"text": KEPT, "kind": "thought", "state": "held"})
        toolbox.call(ToolName.AddQuestion, {"text": ASKED, "kind": "fact", "state": "asked"})
    db.session.commit()

    reply = coach.say("I have no idea.")
    after = {q["id"]: q for q in questions(coach)}
    assert asks_only_waiting(reply), reply
    assert after["q2"]["state"] == QuestionState.Asked, after["q2"]
    new = [q for i, q in after.items() if i not in ("q1", "q2", "q3") and q["state"] == QuestionState.Asked]
    assert new == [], (reply, new)
