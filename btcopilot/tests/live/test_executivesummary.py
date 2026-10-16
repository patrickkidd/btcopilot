"""The Executive Summary, the case report's first card, in the approved shape
(cards.md card 1, rule B1, R-0850): asked to sum up the whole story, the coach
puts on the main_guess card who has the symptom and what it is first, then the
pattern in one sentence, with no chronology of more than one sentence.

The family: a grandfather dies, and a few months later the speaker (Wren)
stops going to classes; years later she has panic attacks at work. A pass is a
main_guess impression, stored as raised, whose first sentence names Wren, or
calls her "you" as the coach speaks to her (R-0860), and
one of her symptoms (panic attacks, stopping classes, sleeping most days),
whose later text names the pattern (a link of her symptoms to her
grandfather's death, her mother or the distance from her), and in which at
most one sentence carries a year or a month. Two runs of three: the reading
is the coach's judgement.

Invented names only.
"""

import re

from btcopilot.extensions import db
from btcopilot.tests.live.conftest import FATHER, MOTHER
from btcopilot.tests.live.criterion import passes

ADA = dict(MOTHER, parents=11)
HUGH = dict(FATHER, parents=12)
SILAS = {"id": 4, "name": "Silas", "last_name": "Marsh", "gender": "male"}
RUTH = {"id": 5, "name": "Ruth", "last_name": "Marsh", "gender": "female"}
WALT = {"id": 6, "name": "Walt", "last_name": "Hale", "gender": "male"}
IRIS = {"id": 7, "name": "Iris", "last_name": "Hale", "gender": "female"}
TESS = {"id": 8, "name": "Tess", "last_name": "Hale", "gender": "female", "parents": 10}
BONDS = [
    {"id": 11, "person_a": 4, "person_b": 5, "married": True},
    {"id": 12, "person_a": 6, "person_b": 7, "married": True},
]


def event(id, kind, date, person, title="", **fields):
    return {"id": id, "kind": kind, "person": person, "dateTime": date, "dateCertainty": "approximate",
            "title": title, "description": title, **fields}


GRANDFATHER_DIED = event(32, "death", "2009-03-14", 4)
STOPPED_CLASSES = event(33, "shift", "2009-08-01", 1, "Stopped going to classes, slept most days", symptom="up")
PANIC = event(34, "shift", "2016-05-01", 1, "Panic attacks at work", symptom="up")
EVENTS = [
    event(31, "birth", "1988-07-02", 2, spouse=3, child=8),
    GRANDFATHER_DIED,
    STOPPED_CLASSES,
    event(35, "noted", "2012-06-01", 3, "Retired from the mill"),
    PANIC,
]
GENERATION = {1: 0, 8: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 2}
TYPE = re.compile(r"\b(you|your \w+) tends? to\b|\byou always\b", re.I)
ASKED = "If you had to sum it up, what is your main guess about what is going on with me?"


def summary(coach) -> dict | None:
    db.session.expire_all()
    questions = coach.user.free_diagram.get_diagram_data().questions
    carded = [q for q in questions if q.get("case_report_card") == "main_guess" and q["state"] == "raised"]
    return carded[-1] if carded else None


SYMPTOM = re.compile(r"panic|classes|slept|sleep", re.I)
PERSON = re.compile(r"\bWren\b|\byou\b", re.I)
PATTERN = re.compile(r"grandfather|Silas|death|died|loss|mother|Ada|distance|calling", re.I)
WHEN = re.compile(r"\b(19|20)\d\d\b|\b(January|February|March|April|May|June|July|August|September|October|November|December)\b")


def reads(main: dict, events: list[dict]) -> tuple[bool, bool, bool]:
    """Opens on Wren, or "you" in the coach's voice (R-0860), and her symptom,
    names the pattern after it, and tells no more than one sentence of
    chronology."""
    first, *rest = re.split(r"(?<=[.!?])\s+", main["text"].strip())
    opens = SYMPTOM.search(first) is not None and PERSON.search(first) is not None
    pattern = any(PATTERN.search(one) for one in rest)
    return opens, pattern, sum(WHEN.search(one) is not None for one in [first, *rest]) <= 1


@passes(2, of=3)
def test_the_executive_summary_opens_on_the_symptom_and_its_person_then_names_the_pattern(coach):
    # R-0850
    coach.record(people=[ADA, HUGH, SILAS, RUTH, WALT, IRIS, TESS], pair_bonds=BONDS, events=EVENTS)
    coach.turn(ASKED)
    main = summary(coach)
    assert main, "no raised impression on the main_guess card"
    assert reads(main, coach.events) == (True,) * 3, main
