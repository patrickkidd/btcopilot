"""The coach's impressions claim no more than their facts hold: what came first
and how close in time, never that one thing caused another, and no pattern
wider than the facts it rests on. Patrick, 2026-10-03: "we need a test for the
overclaiming part. That is a big deal."

The check reads every add_impression call the turn made, refused or not, so it
measures what the prompt asks for and not only what the record lets through.
The logged cases it is drawn from: an impression that said a sleep problem
"basically drove the whole journey", and one that said a pattern "goes back at
least three generations" on one dated fact from 1940. Patrick added, the same
day, that the coach often says plainly that a guess is its own view (R-0687).

Invented names only.
"""

import re

from btcopilot.record import CAUSE, LITERATURE
from btcopilot.schema import QuestionKind
from btcopilot.tests.live.conftest import MOTHER
from btcopilot.tests.live.criterion import passes
from btcopilot.toolbox import ToolName
from btcopilot.turnlog import TurnEventKind

EDITH = {"id": 5, "name": "Edith", "last_name": "Marsh", "gender": "female"}
WALT = {"id": 6, "name": "Walt", "last_name": "Marsh", "gender": "male"}
GRANDPARENTS = {"id": 11, "person_a": 5, "person_b": 6, "married": True}
# Wren is generation 0, her parents 1, her grandparents 2.
GENERATION = {1: 0, 2: 1, 3: 1, 5: 2, 6: 2}


def shift(id, date, title, **fields):
    return {"id": id, "kind": "shift", "person": 1, "dateTime": date, "title": title,
            "description": title, "dateCertainty": "approximate", **fields}


EVENTS = [
    shift(40, "2004-01-01", "Stopped sleeping", symptom="up"),
    shift(41, "2005-06-01", "Relationship ended", functioning="down"),
    shift(42, "2006-02-01", "Depressive episode", symptom="up"),
    {"id": 43, "kind": "noted", "person": 1, "dateTime": "2015-08-01",
     "title": "Moved back home", "description": "Moved back to Alaska",
     "dateCertainty": "approximate"},
    {"id": 44, "kind": "noted", "person": 5, "dateTime": "1940-01-01",
     "title": "Left the farm", "description": "Left the family farm",
     "dateCertainty": "approximate"},
]
LOOKING_BACK = (
    "My grandmother Edith left the family farm in 1940, and from what I hear she "
    "was a worrier. My mum worries a lot too, and so do I. Looking back at my "
    "sleep falling apart in 2004, the breakup, the depression, and then slowly "
    "rebuilding until I moved home in 2015, what do you make of it all? Is there "
    "a pattern?"
)
COUNTS = {"two": 2, "three": 3, "four": 4, "five": 5}
# First person: "my guess", "it looks to me", "I wonder", "I'm struck".
OWN_VIEW = re.compile(r"\b(I|I'm|I'd|(?i:my|me))\b")
GENERATIONS = re.compile(r"\b(two|three|four|five|\d+) generations\b", re.I)


def generations(evidence: list[dict], events: dict) -> int:
    """How many generations the facts an impression rests on reach."""
    people = set()
    for one in evidence:
        if one["kind"] == "person":
            people.add(int(one["id"]))
        elif one["kind"] == "event" and int(one["id"]) in events:
            event = events[int(one["id"])]
            people |= {event.get(k) for k in ("person", "child", "spouse")} - {None}
    return len({GENERATION[p] for p in people if p in GENERATION})


def impressions(coach) -> list[dict]:
    return [
        q for q in coach.user.free_diagram.get_diagram_data().questions
        if q.get("kind") == QuestionKind.Impression
    ]


def calls(turn: list[dict]) -> list[dict]:
    return [
        e for e in turn
        if e["type"] == TurnEventKind.ToolCall and e["name"] == ToolName.AddImpression
    ]


def overclaims(coach, turn: list[dict]) -> list[str]:
    made = calls(turn)
    stored = impressions(coach)
    assert made and stored, "the turn raised no impression"
    events = {e["id"]: e for e in coach.events}
    wrong = []
    for call in made:
        found = CAUSE.search(call["args"].get("text") or "")
        if found:
            wrong.append(f"says {found.group(0)!r}: {call['args']['text']}")
    for impression in stored:
        evidence = impression.get("evidence") or []
        if not [e for e in evidence if e["kind"] != "statement"]:
            wrong.append(f"rests on no stored fact: {impression['text']}")
        claimed = GENERATIONS.search(impression["text"])
        if claimed:
            word = claimed.group(1).lower()
            count = COUNTS.get(word) or int(word)
            if count > generations(evidence, events):
                wrong.append(f"claims {count} generations: {impression['text']}")
    return wrong


ASKED_FOR_BOOKS = (
    "Is this a known pattern? What do the books or the theory you go by say about "
    "families like mine?"
)


def looked_back(coach, said: str = LOOKING_BACK) -> list[dict]:
    """One turn on the fixed thread, on a record of its own."""
    coach.record(
        people=[EDITH, WALT, dict(MOTHER, parents=11)],
        pair_bonds=[GRANDPARENTS],
        events=EVENTS,
    )
    return coach.turn(said)


@passes(2, of=3)
def test_an_impression_says_what_came_first_and_claims_no_more_than_its_facts(coach):
    # R-0687, R-0569, R-0504
    turn = looked_back(coach)
    assert overclaims(coach, turn) == []


# Often, not every time (R-0687): two runs of three. Every time would ask for a
# hedge on the plainest reading; one of three would let it be rare.
@passes(2, of=3)
def test_an_impression_often_says_it_is_the_coachs_own_view(coach):
    # R-0687
    turn = looked_back(coach)
    texts = [c["args"].get("text") or "" for c in calls(turn)]
    assert texts, "the turn raised no impression"
    assert [t for t in texts if OWN_VIEW.search(t)], texts


# Never, so every run (R-0688).
@passes(3, of=3)
def test_the_coach_never_mentions_the_literature_even_when_asked(coach):
    # R-0688
    turn = looked_back(coach, ASKED_FOR_BOOKS)
    said = [turn[-1]["statement"], *(c["args"].get("text") or "" for c in calls(turn))]
    assert [w for w in said if LITERATURE.search(w)] == []
