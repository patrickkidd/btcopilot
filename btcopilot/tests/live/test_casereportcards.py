"""The coach puts its guesses and questions on the case report's cards: its
main guess when asked for one, what it infers the person's own part was along
with the question asking what they think it was, and the person's answer to
that question, kept as their own view (R-0708, R-0709).

Each check reads the calls the turn made, refused or not, and the record it
left. Two runs of three: the card is the coach's judgement, asked for in plain
words, so one miss in three is allowed.

Invented names only.
"""

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.tests.live.conftest import MOTHER
from btcopilot.tests.live.criterion import passes
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

NOTES = (ToolName.AddImpression, ToolName.SetImpression)
ASKS = (ToolName.AddQuestion, ToolName.SetQuestion)


def shift(id, date, person, title, **fields):
    return {"id": id, "kind": "shift", "person": person, "dateTime": date, "title": title,
            "description": title, "dateCertainty": "approximate", **fields}


EVENTS = [
    shift(40, "2004-09-01", 1, "Stopped sleeping well", symptom="up"),
    shift(41, "2005-02-01", 1, "Stopped calling her mother", relationship="distance",
          relationshipTargets=[2]),
    shift(42, "2018-04-01", 2, "Hospitalized with pneumonia", symptom="up"),
    shift(43, "2019-01-01", 1, "Stopped visiting her mother", relationship="distance",
          relationshipTargets=[2]),
]


def guess(id, text, evidence, card=None) -> dict:
    return {"id": id, "text": text, "kind": "impression", "state": "raised",
            "outcome": None, "session_id": None, "asked_at": "2026-09-20",
            "evidence": [{"kind": "event", "id": str(e)} for e in evidence],
            "pushback": None, "case_report_card": card}


DISTANCE = guess("i1", "It looks to me as if twice you stopped being in touch with your "
                 "mother within months of a worry about her.", (41, 42, 43))
OWN = guess("i2", "My guess is that your part has been to stay away when things with "
            "your mother get tense.", (41, 43), "own_part")
ASKED = {"id": "q1", "text": "What do you think your own part was?", "kind": "thought",
         "state": "asked", "outcome": None, "session_id": None, "asked_at": "2026-09-20",
         "case_report_card": "own_part"}


def recorded(coach, *questions) -> None:
    coach.record(people=[dict(MOTHER)], events=EVENTS)
    diagram = coach.user.free_diagram
    data = diagramjson.loads(diagram.data)
    data["questions"] = list(questions)
    diagram.data = diagramjson.dumps(data)
    db.session.commit()


def carded(turn: list[dict], tools, card: str) -> list[dict]:
    return [
        e for e in turn
        if e["type"] == TurnEventKind.ToolCall
        and e["name"] in tools
        and e["args"].get("case_report_card") == card
    ]


def stored(coach) -> dict:
    db.session.expire_all()
    return {q["id"]: q for q in coach.user.free_diagram.get_diagram_data().questions}


@passes(2, of=3)
def test_asked_for_its_main_guess_the_coach_puts_one_on_the_card(coach):
    # R-0709
    recorded(coach, DISTANCE)
    turn = coach.turn("If you had to sum it up, what is your main guess about what is going on with me?")
    assert carded(turn, NOTES, "main_guess"), [e.get("name") for e in turn]


@passes(2, of=3)
def test_asked_about_their_part_the_coach_infers_it_and_asks_what_they_think(coach):
    # R-0708
    recorded(coach, DISTANCE)
    turn = coach.turn("Looking at all this, what do you think my own part in it has been?")
    assert (bool(carded(turn, NOTES, "own_part")), bool(carded(turn, ASKS, "own_part"))) == (
        True,
        True,
    ), [(e.get("name"), e.get("args")) for e in turn if e["type"] == TurnEventKind.ToolCall]


@passes(2, of=3)
def test_their_answer_about_their_own_part_is_kept_as_their_view(coach):
    # R-0708
    recorded(coach, DISTANCE, OWN, ASKED)
    coach.turn("Honestly, I think I go quiet and stay away instead of telling her what I need.")
    answered = stored(coach)["q1"]
    assert (answered["outcome"], bool(answered.get("answer"))) == ("answered", True), answered


AIM = {"id": 44, "kind": "noted", "person": 1, "dateTime": "2026-09-01",
       "title": "Working on visiting more", "description": "Said she is working on visiting her mother more",
       "dateCertainty": "approximate"}


@passes(2, of=3)
def test_what_to_work_on_rests_first_on_where_they_said_what_they_are_working_on(coach):
    # R-0707
    coach.record(people=[dict(MOTHER)], events=[*EVENTS, AIM])
    turn = coach.turn("So what do you think I should work on, and what should I expect when I do?")
    marked = carded(turn, (ToolName.AddImpression,), "work_on")
    assert marked and marked[0]["args"]["evidence"][0] == {"kind": "event", "id": "44"}, marked


MAIN = guess("i3", "My guess is that when your mother is unwell you keep your distance from her, "
             "and your sleep goes first.", (40, 42, 43), "main_guess")
OTHERS = [
    guess("i4", "Your sleep went before you stopped calling your mother in 2005.", (40, 41)),
    guess("i5", "You stopped visiting your mother within a year of her time in hospital.", (42, 43)),
    guess("i6", "Twice the distance from your mother came in the same years as trouble of your own.", (40, 41, 43)),
    guess("i7", "Your mother was in hospital the year before you stopped visiting.", (42, 43)),
]


@passes(2, of=3)
def test_the_coachs_guess_card_holds_only_the_parts_that_matter_most(coach):
    # R-0732
    recorded(coach, DISTANCE, MAIN, *OTHERS)
    coach.turn("Of everything you have noticed about me, which parts matter most for me to look at?")
    marked = [i for i, q in stored(coach).items() if q.get("case_report_card") == "coach_guess"]
    assert 1 <= len(marked) <= 2 and "i3" not in marked, marked


OWEN = {"id": 20, "name": "Owen", "last_name": "Reyes", "gender": "male"}
WED = {"id": 21, "person_a": 1, "person_b": 20, "married": True}
PARENTS_WED = {"id": 50, "kind": "married", "person": 2, "spouse": 3, "dateTime": "1981-06-01",
               "dateCertainty": "certain"}
COUPLE = [
    {"id": 51, "kind": "bonded", "person": 1, "spouse": 20, "dateTime": "2006-05-01", "dateCertainty": "approximate"},
    {"id": 52, "kind": "married", "person": 1, "spouse": 20, "dateTime": "2009-09-12", "dateCertainty": "certain"},
    shift(53, "2010-03-01", 1, "Stopped calling her mother", relationship="distance", relationshipTargets=[2]),
    shift(54, "2010-08-01", 20, "Visited his brother every weekend", relationship="toward"),
]


def refreshed(coach, said: str) -> dict | None:
    coach.turn(said)
    response = coach.web.post("/app/case-report-rewrites", headers={"X-CSRFToken": coach.token})
    assert response.status_code == 202, response.get_data(as_text=True)
    assert coach.web.get(f"/app/case-report-rewrites/{response.get_json()['id']}").get_json()["state"] == "done"
    return next((q for q in reversed(list(stored(coach).values())) if q.get("case_report_card") == "couple"), None)


@passes(2, of=3)
def test_a_refresh_writes_the_couple_card_on_the_persons_own_couple_not_their_parents(coach):
    # R-0850
    # pass: the couple card rests on Wren and Owen's own events and never on her parents' wedding
    coach.record(people=[OWEN], pair_bonds=[WED], events=[PARENTS_WED, *COUPLE])
    card = refreshed(coach, "Owen and I met in 2006 and married three years later; after that I called my mother less.")
    rests = {str(e["id"]) for e in (card or {}).get("evidence", []) if e["kind"] == "event"}
    assert card and rests & {"51", "52", "53", "54"} and "50" not in rests, card


@passes(2, of=3)
def test_with_no_partner_on_the_diagram_the_couple_card_says_what_it_still_needs(coach):
    # R-0850
    # pass: the couple card is the one line saying there is not enough in the diagram yet
    coach.record(events=[PARENTS_WED])
    card = refreshed(coach, "I've been thinking about my family a lot lately.")
    assert card and card["text"].startswith("Not enough in the diagram yet"), card
