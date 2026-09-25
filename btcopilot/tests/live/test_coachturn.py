"""What one real coach turn writes on the record, on the private prompts.

Every expected value is the coding the owner ruled for the words said. Invented
names only.
"""

import re

from btcopilot import prompts
from btcopilot.tests.live.criterion import once, passes

NOTHING = ("", None)


def on(events, person):
    return [e for e in events if e.get("person") == person]


@once
def test_a_feeling_that_interferes_with_work_is_a_symptom(coach):
    # R-0424
    coach.record()
    coach.say("My hands shake so badly before work that I've started calling in sick.")
    assert [e for e in on(coach.events, 1) if e.get("symptom") == "up"]


@once
def test_a_feeling_that_interferes_with_nothing_is_not_a_symptom(coach):
    # R-0424
    coach.record()
    coach.say(
        "I get a little nervous before big meetings, but it never gets in the way of anything."
    )
    assert [e for e in coach.events if e.get("symptom") not in NOTHING] == []


@once
def test_a_diagnosis_is_symptom_up_on_the_person_it_happened_to_dated_when_it_happened(
    coach,
):
    # R-0425
    coach.record()
    coach.say("My mother was diagnosed with breast cancer in March 2019.")
    symptoms = [e for e in on(coach.events, 2) if e.get("symptom") == "up"]
    assert symptoms
    (event,) = symptoms
    assert (event.get("dateTime") or "").startswith("2019")


@once
def test_a_date_known_to_the_month_is_approximate(coach):
    # R-0482
    coach.record()
    coach.say("My dad died in June 1998.")
    (death,) = [e for e in on(coach.events, 3) if e.get("kind") == "death"]
    assert (death.get("dateTime") or "").startswith("1998-06")
    assert death.get("dateCertainty") == "approximate"


@once
def test_the_coach_infers_anxiety_down_from_what_is_described(coach):
    # R-0427
    coach.record()
    coach.say("My dad finally retired last year and he seems so much more relaxed now.")
    assert [e for e in on(coach.events, 3) if e.get("anxiety") == "down"]


@once
def test_the_coach_infers_anxiety_up_around_a_stressor_half_remembered(coach):
    # R-0427
    coach.record()
    coach.say(
        "I barely remember the year we moved, except that my parents fought about money."
    )
    assert [e for e in coach.events if e.get("anxiety") == "up"]


@once
def test_things_rocky_since_the_divorce_is_functioning_down_on_the_speaker(coach):
    # R-0428
    coach.record()
    coach.say("Things have always been rocky for me since the divorce.")
    assert [e for e in on(coach.events, 1) if e.get("functioning") == "down"]


@once
def test_the_coach_prompt_defines_functioning_in_the_spec_words():
    # R-0428
    assert re.search(r"balanc\w* emotion and intellect", prompts.get_agent_prompt())


BROTHER = {"id": 4, "name": "Colm", "gender": "male", "parents": 10}
MOMS_DIAGNOSIS = (
    "Ever since Mom got her diagnosis, he's stepped back and I'm doing everything."
)


@once
def test_mom_diagnosis_is_a_symptom_on_mom_and_stepping_back_is_under_and_over_functioning(
    coach,
):
    # R-0433
    coach.record([BROTHER])
    coach.say(f"My brother Colm lives nearby. {MOMS_DIAGNOSIS}")
    assert [e for e in on(coach.events, 2) if e.get("symptom") == "up"]
    kinds = {(e.get("person"), e.get("relationship")) for e in coach.events}
    assert (4, "underfunctioning") in kinds
    assert (1, "overfunctioning") in kinds


MICHAEL = {"id": 5, "name": "Michael", "gender": "male"}


@once
def test_a_visit_and_an_argument_is_one_conflict_event_from_the_visitor_to_the_speaker(
    coach,
):
    # R-0434
    coach.record([MICHAEL])
    coach.say("Michael came over to visit, and we ended up arguing.")
    conflicts = [e for e in coach.events if e.get("relationship") == "conflict"]
    assert [e["person"] for e in conflicts] == [5]
    assert conflicts[0].get("relationshipTargets") == [1]


SON = {"id": 6, "name": "Finn", "gender": "male", "parents": 11}
MARRIAGE = {"id": 11, "person_a": 1, "person_b": 7}
PARTNER = {"id": 7, "name": "Rory", "gender": "male"}
GRADES = (
    "Finn's grades slipped last fall and I got so anxious about him that I was "
    "checking his homework every night and on him constantly."
)


@once
def test_projection_is_coded_in_the_turn_it_is_described_without_asking(coach):
    # R-0435
    coach.record([PARTNER, SON], [MARRIAGE])
    reply = coach.say(GRADES)
    assert [e for e in coach.events if e.get("relationship") == "projection"]
    assert "project" not in reply.lower()


@passes(2, of=3)
def test_a_reply_ends_in_a_question_while_the_family_is_unknown(coach):
    # R-0436
    coach.record()
    reply = coach.say("Hi. I'd like to talk about my family.")
    assert reply.rstrip().endswith("?")


@once
def test_the_coach_prompt_marks_its_fallback_coding_rules_provisional():
    # R-0440
    assert "provisional" in prompts.get_agent_prompt().lower()


@once
def test_the_scribe_prompt_marks_its_fallback_coding_rules_provisional():
    # R-0440
    assert "provisional" in prompts.scribe_prompt().lower()


BOB = {"id": 12, "name": "Bob", "gender": "male", "parents": 10}
JAMES = {"id": 13, "name": "James", "gender": "male", "parents": 10}
TOM = {"id": 14, "name": "Tom", "gender": "male", "parents": 10}
TWO_BROTHERS = "I've only got two brothers, Bob and James."


@once
def test_a_complete_list_removes_no_one_and_the_coach_asks_about_the_one_left_out(
    coach,
):
    # R-0441
    coach.record([BOB, JAMES, TOM])
    reply = coach.say(TWO_BROTHERS)
    assert 14 in [p["id"] for p in coach.people]
    assert "Tom" in reply
    assert "?" in reply


WORRY = {
    "id": 20,
    "kind": "shift",
    "person": 1,
    "dateTime": "2019-03-01",
    "anxiety": "up",
    "description": "Worried after the move",
}
AGAIN = "Like I said, I was really worried after we moved in 2019, I couldn't sleep."


@once
def test_a_shift_said_again_makes_no_second_event_and_is_folded_into_the_first(coach):
    # R-0442
    coach.record(events=[WORRY])
    coach.say(AGAIN)
    assert [e for e in on(coach.events, 1) if e.get("anxiety") == "up"] == [
        next(e for e in coach.events if e["id"] == 20)
    ]
    (event,) = [e for e in coach.events if e["id"] == 20]
    assert event.get("notes") or event.get("description") != WORRY["description"]


@once
def test_a_couple_splitting_over_having_kids_is_an_away_move_between_the_two_of_them(
    coach,
):
    # R-0057
    coach.record([PARTNER], [MARRIAGE])
    coach.say("Rory and I split up in 2015 because he wanted kids and I didn't.")
    moves = [e for e in coach.events if e.get("relationship") == "away"]
    assert moves
    (away,) = moves
    assert {away.get("person"), *(away.get("relationshipTargets") or [])} == {1, 7}


INSOMNIA = {
    "id": 21,
    "kind": "shift",
    "person": 1,
    "dateTime": "2000-03-01",
    "symptom": "up",
    "description": "Stopped sleeping",
}
MOVED = "We moved to Arizona in early 2000."


@once
def test_a_move_is_a_noted_event_and_the_coach_wonders_whether_it_played_in_a_shift(
    coach,
):
    # R-0366
    coach.record(events=[INSOMNIA])
    reply = coach.say(MOVED)
    moves = [e for e in coach.events if e["id"] not in (21, 30)]
    assert [e.get("kind") for e in moves] == ["noted"]
    assert all(
        e.get(v) in NOTHING
        for e in moves
        for v in ("symptom", "anxiety", "functioning")
    )
    assert re.search(r"sleep|move|Arizona", reply, re.I)
    assert "?" in reply
