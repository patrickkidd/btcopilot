"""A waiting question the person has passed over twice is left alone at an
opening: it stays on their list, and the coach asks something else or follows
them.

Invented names only.
"""

from freezegun import freeze_time

from btcopilot import record
from btcopilot.extensions import db
from btcopilot.models import Author, Discussion, Statement
from btcopilot.schema import QuestionState
from btcopilot.tests.live.checks import asks_passed_over
from btcopilot.tests.live.conftest import TODAY
from btcopilot.tests.live.criterion import passes
from btcopilot.toolbox import ToolName, Toolbox

GRANDFATHER = {"id": 5, "name": "Walt", "last_name": "Pryor", "gender": "male"}
GRANDMOTHER = {"id": 6, "name": "June", "last_name": "Pryor", "gender": "female"}
GRANDPARENTS = {"id": 11, "person_a": 5, "person_b": 6, "married": True}
MOTHER = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female", "parents": 11}
BROTHER = {"id": 4, "name": "Theo", "last_name": "Hale", "gender": "male", "parents": 10}

KEPT = "What has your mother told you about growing up with her father's drinking?"
# What brings her is told; the coach asked the kept question three times in
# all, and each time she talked about something else.
SAID = [
    "I came because my brother Theo and I haven't spoken since last spring.",
    "What happened last spring?",
    "At Mom's 60th he said I'd abandoned the family by moving away.",
    f"That stung. {KEPT}",
    "Honestly I'd rather talk about Theo. He won't answer my texts.",
    "How long since you last texted him?",
    "Two weeks. I sent him a birthday message.",
    f"I wonder about your mom's side too. {KEPT}",
    "I don't know. Anyway, Theo's wife posted photos from a trip and I wasn't invited.",
    "How old is Theo now?",
]
ASKED_AGAIN = ["2026-09-24", "2026-09-25"]


def kept(coach) -> dict:
    db.session.expire_all()
    return next(q for q in coach.user.free_diagram.get_diagram_data().questions if q["text"] == KEPT)


@passes(3, of=3)
def test_a_question_passed_over_twice_is_not_asked_a_third_time(coach):
    # R-0774
    coach.record([GRANDFATHER, GRANDMOTHER, MOTHER, BROTHER], [GRANDPARENTS])
    talk = Discussion.query.filter_by(diagram_id=coach.user.free_diagram_id).one()
    for i, text in enumerate(SAID):
        speaker = talk.chat_user_speaker if i % 2 == 0 else talk.chat_ai_speaker
        db.session.add(
            Statement(discussion_id=talk.id, speaker=speaker, text=text, order=talk.next_order())
        )
        db.session.flush()
    db.session.commit()
    toolbox = Toolbox(coach.user.free_diagram_id, "earlier", session_id=talk.id, author=Author.Coach)
    with freeze_time(TODAY):
        _, patch = toolbox.call(
            ToolName.AddQuestion, {"text": KEPT, "kind": "thought", "state": "asked"}
        )
    qid = patch["deltas"][0]["item_id"]
    for n in (1, 2):
        record.apply(
            coach.user.free_diagram_id,
            [{"item_kind": "question", "item_id": qid, "field": record.ASKED_AGAIN, "after": ASKED_AGAIN[:n]}],
            author=Author.Coach,
            turn_id=f"earlier:{n}",
        )

    reply = coach.say("Thirty-four, I think. What should we talk about next?")
    assert asks_passed_over(reply) == [], reply
    after = kept(coach)
    assert (after["state"], after[record.ASKED_AGAIN]) == (QuestionState.Asked, ASKED_AGAIN), after
