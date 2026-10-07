"""The Executive Summary, the case report's first card: asked to sum up the
whole story, the coach puts on the main_guess card a reading that sets the
person's hard stretches beside what happened in the family across at least two
generations, ends on what does not fit yet, and never describes the person as
a standing type (R-0820).

The family: a grandfather dies, and a few months later the speaker stops going
to classes; years later the speaker has panic attacks at work with no family
event near them. A pass is a main_guess impression, stored as raised, whose
evidence holds events of at least two generations, which names the 2016
stretch by its event or its year, which places the speaker among her brothers
and sisters (her sister by name or as evidence), and which never describes her
as a standing type ("you tend to", "your trouble tends to", "you always").
Two runs of three: the reading is the coach's judgement.

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


@passes(2, of=3)
def test_the_executive_summary_reads_the_family_over_generations_and_ends_on_what_does_not_fit(coach):
    # R-0820
    coach.record(people=[ADA, HUGH, SILAS, RUTH, WALT, IRIS, TESS], pair_bonds=BONDS, events=EVENTS)
    coach.turn(ASKED)
    main = summary(coach)
    assert main, "no raised impression on the main_guess card"
    events = {e["id"]: e for e in coach.events}
    cited = [events[int(one["id"])] for one in main["evidence"] if one["kind"] == "event" and int(one["id"]) in events]
    generations = {GENERATION[e.get("child") or e["person"]] for e in cited if (e.get("child") or e["person"]) in GENERATION}
    unfit = PANIC["id"] in {e["id"] for e in cited} or "2016" in main["text"]
    placed = TESS["name"] in main["text"] or {"kind": "person", "id": str(TESS["id"])} in main["evidence"]
    assert (len(generations) >= 2, unfit, placed, TYPE.search(main["text"]) is None) == (True,) * 4, main
