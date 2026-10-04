# Live-eval drafts for the early question and what the coach writes when a time is named

Judge: judge-010, 2026-10-04. Drafts only, not run. Style: btcopilot/tests/live (the `coach` fixture
seeds Wren Hale, id 1, born 1985-04-12, with parents Ada 2 and Hugh 3 and their bond 10; the prompt's
date is fixed at 2026-09-25; `@once` or `@passes(k, of=n)`; the ruling line first under the def;
deterministic checks on the record, the reply or the turn stream; no model as judge). No ruling
exists yet, so every citation reads `# R-0NNN to be assigned`. Names and dates are invented. The
file would be a new module beside test_coachturn.py; the `questions` reader at its top is the only
helper the fixture lacks. The suite runs on the private prompts, so these drafts see the public
fragment edits only once they are mirrored into the private copies, or when the suite is run with
`FD_PRIVATE_PROMPTS` pointed at a copy of the private prompts carrying the same edits (see the last
section).

```python
"""Real coach turns around the early question which times of a life the most was
going on in, and what the coach writes when the person names one.

Invented names only.
"""

import re

from btcopilot.extensions import db
from btcopilot.tests.live.criterion import once, passes
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

NOTHING = ("", None)
YEARS = re.compile(r"\b(year|years|time|times|when)\b", re.I)
GROUPING = re.compile(r"\b(cluster|chapter|episode|period|timeline)\b", re.I)


def questions(coach) -> list[dict]:
    db.session.expire_all()
    return coach.user.free_diagram.get_diagram_data().questions


def asked(events, tool) -> list[dict]:
    """The calls of one tool that were not refused, with their arguments."""
    return [
        e
        for e in events
        if e["type"] == TurnEventKind.ToolCall and e["name"] == tool and e["refusal"] is None
    ]
```

## 1. With no one thing brought, the first question is which times the most was going on, kept as a fact question on the person

Pass criterion: 2 of 3 runs. Checks: an `add_question` call kept on the person, kind fact, state
asked, whose words ask about times or years; the reply ends in one question mark and uses none of
the grouping words; nothing was added to the record (the person said no fact).

```python
NO_ONE_THING = "I don't have one thing I'm here about. I just want to understand my family better."


@passes(2, of=3)
def test_with_no_one_thing_brought_the_coach_asks_which_times_the_most_was_going_on(coach):
    # R-0NNN to be assigned
    coach.record()
    events = coach.turn(NO_ONE_THING)
    reply = events[-1]["statement"]
    kept = [
        e["args"]
        for e in asked(events, ToolName.AddQuestion)
        if e["args"].get("kind") == "fact"
        and e["args"].get("state") == "asked"
        and e["args"].get("item_kind") == "person"
        and str(e["args"].get("item_id")) == "1"
    ]
    assert kept and YEARS.search(kept[0]["text"])
    assert reply.rstrip().endswith("?") and reply.count("?") == 1
    assert not GROUPING.search(reply)
    assert [e["id"] for e in coach.events] == [30]
```

## 2. A time named with nothing in it is a kept question naming the years, not an event

Pass criterion: 2 of 3 runs. Checks: a question kept on the record whose words name both years; no
new noted event (a noted event must say what happened, R-0363, and "the worst" says nothing that
happened); no new event dated certain (a hedged span never becomes a sure date); the reply asks one
question. The draft does not assert "no event at all": whether "everything went wrong" codes a
functioning shift on the speaker is the undecided rule behind the waiting R-0428 case. It asserts
nothing about clusters: the code already refuses a cluster under three dated events at the write
(doc/CLUSTERS.md), so such a check could not fail.

```python
WORST = "Looking back, 2014 to 2016 was the worst time of my life. Everything went wrong at once."


@passes(2, of=3)
def test_a_time_named_with_nothing_in_it_is_a_question_naming_the_years_not_an_event(coach):
    # R-0NNN to be assigned
    coach.record()
    reply = coach.say(WORST)
    span = [q for q in questions(coach) if "2014" in q["text"] and "2016" in q["text"]]
    assert span and span[0]["state"] in ("asked", "held")
    new = [e for e in coach.events if e["id"] != 30]
    assert [e for e in new if e.get("kind") == "noted"] == []
    assert [e for e in new if e.get("dateCertainty") == "certain"] == []
    assert reply.rstrip().endswith("?")
```

## 3. A time named with facts in it becomes dated events with the sureness given, and the coach asks about one of them

Pass criterion: 2 of 3 runs. Checks: a noted event on the speaker for leaving college, dated 2009,
not certain ("around" is a hedge); an event on the father dated 2009 (its coding, a symptom shift or
a noted health event, is left open here); the reply asks one question, about one of the two things
named, not both and not a third.

```python
DAD_SICK = (
    "The hardest years were around 2009. My dad got sick and I dropped out of college."
)


@passes(2, of=3)
def test_a_time_named_with_facts_becomes_dated_events_and_one_question_about_one_of_them(coach):
    # R-0NNN to be assigned
    coach.record()
    reply = coach.say(DAD_SICK)
    school = [
        e
        for e in coach.events
        if e.get("person") == 1 and e.get("kind") == "noted" and e.get("item") == "schooling"
    ]
    assert school and (school[0].get("dateTime") or "").startswith("2009")
    assert school[0].get("dateCertainty") != "certain"
    father = [
        e
        for e in coach.events
        if e.get("person") == 3
        and e.get("kind") != "birth"
        and (e.get("dateTime") or "").startswith("2009")
    ]
    assert father
    assert reply.count("?") == 1
    assert re.search(r"\b(dad|father|college|school)\b", reply, re.I)
```

## 4. An order the person is unsure of is written unsure, and the coach asks which came first rather than deciding

Pass criterion: 2 of 3 runs. Checks: the grandmother's death dated 2016 and not certain; the
sister's divorce written with its date marked the coach's own guess (unknown), since no year was
given for it; the reply asks about the order or the month. Nothing here asserts what the coach
says about the two events together; whether it may say they look like one story is the open
tension noted in decide.md.

```python
GRANDMOTHER = {"id": 50, "name": "Edith", "last_name": "Whitlock", "gender": "female"}
GRANDFATHER = {"id": 51, "name": "Walt", "last_name": "Whitlock", "gender": "male"}
GRANDPARENTS = {"id": 52, "person_a": 50, "person_b": 51, "married": True}
ADA = {"id": 2, "name": "Ada", "last_name": "Hale", "gender": "female", "parents": 52}
SISTER = {"id": 53, "name": "Greta", "last_name": "Hale", "gender": "female", "parents": 10}
DEV = {"id": 54, "name": "Dev", "last_name": "Okafor", "gender": "male"}
SISTERS_MARRIAGE = {"id": 55, "person_a": 53, "person_b": 54, "married": True}
BLUR = (
    "My grandma Edith died sometime in 2016. I think that was after Greta's divorce, "
    "or maybe just before. It's all a blur."
)


@passes(2, of=3)
def test_an_order_the_person_is_unsure_of_is_written_unsure_and_the_coach_asks_which_came_first(
    coach,
):
    # R-0NNN to be assigned
    coach.record(
        [GRANDMOTHER, GRANDFATHER, ADA, SISTER, DEV], [GRANDPARENTS, SISTERS_MARRIAGE]
    )
    reply = coach.say(BLUR)
    (death,) = [e for e in coach.events if e.get("kind") == "death" and e.get("person") == 50]
    assert (death.get("dateTime") or "").startswith("2016")
    assert death.get("dateCertainty") != "certain"
    (divorce,) = [
        e
        for e in coach.events
        if e.get("kind") == "divorced" and {e.get("person"), e.get("spouse")} == {53, 54}
    ]
    assert divorce.get("dateCertainty") == "unknown"
    assert "?" in reply
    assert re.search(r"\b(before|after|first|which came|what month|when)\b", reply, re.I)
```

## What each draft is proven against, and on which prompts

The live suite runs on the private prompts, and the private directory holds its own copy of each
of the three fragments the public patch edits (agent_fidelity.md, open_questions.md, coach_notes.md),
which wins over the public copy (btcopilot/prompts.py). So the public patch alone changes nothing
these drafts see. The proof is run either after a key-holder mirrors the three edits into the
private copies, or with `FD_PRIVATE_PROMPTS` pointed at a copy of the private prompts carrying the
same edits; first on the prompts before the edits (each draft should fail), then after (each should
pass). Expected: draft 1 fails before, because no rule asks the early question and the coach follows
the coverage block to schooling or work; draft 2 fails before on the span-question rule in
open_questions.md; drafts 3 and 4 mostly hold before under the date certainty text already in
agent_fidelity.md and are regression guards for the follow-up rule (one question, about one named
thing; the order asked, not decided). The subscription path can judge drafts 1 and 2 (which tools
are called, whether a question is kept); drafts 3 and 4 turn on date certainty, which the README
says only the paid run can judge.
