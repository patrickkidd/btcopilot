"""Early on the coach says in one plain sentence what this is and asks what the
person hopes to get from it, keeps that as a thought question, and closes it
with their own words when they answer.

Invented names only.
"""

from freezegun import freeze_time

from btcopilot.extensions import db
from btcopilot.models import Author, Discussion, Statement
from btcopilot.schema import QuestionKind, QuestionOutcome, QuestionState
from btcopilot.tests.live.checks import explains_and_asks_hope
from btcopilot.tests.live.conftest import TODAY
from btcopilot.tests.live.criterion import passes
from btcopilot.toolbox import ToolName, Toolbox

OPENING = "My sister and I aren't speaking."
FOLLOW = "It's been about a year. She stopped answering after Dad's birthday."
HOPE = "What are you hoping to get from this?"
REPLY = (
    "That sounds hard. I'll ask about what's going on and the people around it, and "
    "over a few conversations a picture of your life over time builds up that you can "
    f"look at. {HOPE}"
)
WANT = "I want to stop dreading holidays"


@passes(3, of=3)
def test_the_first_or_second_reply_says_what_this_is_and_asks_the_hope(coach):
    # R-0782, R-0781
    coach.record()

    reply = coach.say(OPENING)
    if explains_and_asks_hope(reply):
        return
    reply = coach.say(FOLLOW)
    assert explains_and_asks_hope(reply), reply


@passes(2, of=3)
def test_the_hope_question_is_closed_with_their_own_words(coach):
    # R-0782, R-0781
    coach.record()
    talk = Discussion.query.filter_by(diagram_id=coach.user.free_diagram_id).one()
    for speaker, text in ((talk.chat_user_speaker, OPENING), (talk.chat_ai_speaker, REPLY)):
        db.session.add(
            Statement(discussion_id=talk.id, speaker=speaker, text=text, order=talk.next_order())
        )
        db.session.flush()
    db.session.commit()
    toolbox = Toolbox(coach.user.free_diagram_id, "earlier", session_id=talk.id, author=Author.Coach)
    with freeze_time(TODAY):
        toolbox.call(ToolName.AddQuestion, {"text": HOPE, "kind": "thought", "state": "asked"})
    db.session.commit()

    coach.say(WANT)
    db.session.expire_all()
    said = Statement.query.filter_by(discussion_id=talk.id, text=WANT).one()
    kept = coach.user.free_diagram.get_diagram_data().questions
    closed = [
        q
        for q in kept
        if q["kind"] == QuestionKind.Thought
        and q["state"] == QuestionState.Resolved
        and q.get("outcome") == QuestionOutcome.Answered
        and (q.get("answer") or {}).get("id") == said.id
    ]
    assert closed, [(said.id, q["state"], q.get("outcome"), q.get("answer")) for q in kept]
