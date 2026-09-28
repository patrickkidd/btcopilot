"""Real play-by-plays: the coach tells one cluster as dated pictures through its
one tool (PROMPT_DRAFT.md, 2026-09-27). Pass criterion: first try, 3 of 3. The
call must validate on its first try (a hand-back fails the run, so a refused
call costs one call, not three), the question is one question, and no cause is
named in the point or a guess line. Whether the point is of the ruled kind
waits on Patrick's ruling on one recorded output.

The old prompt fails this: it asked for a walk in prose with chips and never
called the tool, so the old code stored no case, which the mocked case below
shows. It also named a cause in production: statement 109 of
prod-2026-09-27-1927 says one thing happened "because" of another.

Invented names only: the Whitlock stand-in family, case 2 (doc/mockups/family.md).
"""

import re

import pytest

from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import DiagramData
from btcopilot.tests.conftest import Model, said
from btcopilot.tests.live.criterion import once, passes

PEOPLE = [
    {"id": 3, "name": "Marcus", "last_name": "Whitlock", "gender": "male"},
    {"id": 4, "name": "Delphine", "last_name": "Reyes", "gender": "female"},
    {"id": 5, "name": "Corinne", "last_name": "Whitlock", "gender": "female", "primary": True, "parents": 21},
    {"id": 6, "name": "Theo", "last_name": "Whitlock", "gender": "male", "parents": 21},
]
PARENTS = {"id": 21, "person_a": 3, "person_b": 4, "married": True}


def event(id, kind, date, **fields) -> dict:
    return {"id": id, "kind": kind, "dateTime": date, "dateCertainty": "certain", **fields}


CASE_2 = [
    event(107, "birth", "1975-06-01", person=3, spouse=4, child=5),
    event(108, "birth", "1979-06-01", person=3, spouse=4, child=6),
    event(201, "separated", "1980-09-15", person=3, spouse=4),
    event(202, "noted", "1980-09-15", person=3, description="Took a room over the hardware store"),
    event(203, "shift", "1981-01-15", person=3, symptom="up", description="Drinking most nights, as Delphine put it"),
    event(204, "divorced", "1981-06-15", person=3, spouse=4),
    event(205, "noted", "1981-09-15", person=6, description="Started at the church day care"),
    event(206, "shift", "1982-04-15", person=3, symptom="down", description="Hadn't had a drink since Easter"),
    event(207, "noted", "1982-09-15", person=5, description="Started school"),
    event(208, "shift", "1982-11-15", person=5, symptom="up", description="Her teacher called Delphine: she had stopped talking in class"),
]
CAUSE = re.compile(r"\b(because|caused|made you|why)\b", re.I)


def play(coach) -> Statement:
    response = coach.web.post("/app/sessions", json={}, headers={"X-CSRFToken": coach.token})
    assert response.status_code == 201, response.get_data(as_text=True)
    coach.user.free_diagram.set_diagram_data(
        DiagramData(
            people=PEOPLE,
            pair_bonds=[PARENTS],
            events=CASE_2,
            clusters=[{"id": "apart", "title": "The years apart", "eventIds": [e["id"] for e in CASE_2[2:]]}],
            lastItemId=300,
        )
    )
    db.session.commit()
    response = coach.web.post(
        "/app/play", json={"cluster_id": "apart"}, headers={"X-CSRFToken": coach.token}
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return db.session.get(Statement, response.get_json()["statement_id"])


@pytest.fixture(autouse=True)
def first_try(monkeypatch):
    """One try: a call the cluster does not bear out fails the run."""
    monkeypatch.setattr("btcopilot.playturn.TRIES", 1)


def shaped(told: Statement) -> None:
    case = told.told_case
    assert case is not None, "no case was told"
    assert case["question"].endswith("?"), case["question"]
    judged = [case["point"]] + [s["guess"] for s in case["snapshots"] if s["guess"]]
    assert not [line for line in judged if CAUSE.search(line)], judged


@passes(3, of=3)
def test_the_coach_tells_case_two_as_dated_pictures_with_no_cause_named(coach):
    # R-0563, R-0569
    shaped(play(coach))


# A walk in prose with chips, as the old prompt asked for.
OLD_WALK = (
    "In September 1980 [[event:201|Marcus and Delphine separated]], and in January "
    "[[event:203|Marcus was drinking most nights]]. What do you remember of that winter?"
)


@once
def test_the_old_prompts_walk_fails_the_case_checks(coach, monkeypatch):
    # R-0563, R-0569
    monkeypatch.setattr("btcopilot.playturn.CoachModel", lambda *a, **k: Model(said(OLD_WALK)))
    with pytest.raises(AssertionError, match="500"):
        shaped(play(coach))
