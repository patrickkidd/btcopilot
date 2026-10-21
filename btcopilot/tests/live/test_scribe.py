"""Live checks of what the scribe writes for a coder's statement, on Gemini
Flash with its own tools (R-0885, R-0886).

The first three are the faults seen on the walk sandbox on 2026-10-21; the rest
are the walk's steps. Every family is invented. One try each; the run stops at
CAP dollars of model calls.
"""

import datetime
from decimal import Decimal

import pytest

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, Speaker, SpeakerType, Statement
from btcopilot.review import adapter, scribe
from btcopilot.review.models import Cut
from btcopilot.tests.live.criterion import once
from btcopilot.tests.review.conftest import coded

CAP = Decimal("1.00")

# The shape the faults were seen on: the speaker, his parents, and his
# mother's parents, her father sharing his father's first name.
PEOPLE = [
    {"id": 1, "name": "Liam", "last_name": "Ward", "gender": "male", "parents": 4},
    {"id": 2, "name": "Owen", "last_name": "Ward", "gender": "male"},
    {"id": 3, "name": "Maeve", "last_name": "Doyle", "gender": "female", "parents": 8},
    {"id": 6, "name": "Owen", "last_name": "Doyle", "gender": "male"},
    {"id": 7, "name": "Clare", "last_name": "Doyle", "gender": "female"},
]
RECORD = {
    "people": PEOPLE,
    "pair_bonds": [
        {"id": 4, "person_a": 2, "person_b": 3},
        {"id": 8, "person_a": 6, "person_b": 7},
    ],
    "events": [
        {
            "id": 5,
            "kind": "birth",
            "child": 1,
            "person": 2,
            "spouse": 3,
            "dateTime": "1980-01-01",
            "dateCertainty": "approximate",
        }
    ],
    "lastItemId": 8,
}
FATHER = 2
# Liam's sister and her husband, married in 2005.
SISTER = dict(
    RECORD,
    people=PEOPLE
    + [
        {
            "id": 9,
            "name": "Aoife",
            "last_name": "Ward",
            "gender": "female",
            "parents": 4,
        },
        {"id": 10, "name": "Ciaran", "last_name": "Byrne", "gender": "male"},
    ],
    pair_bonds=RECORD["pair_bonds"]
    + [{"id": 11, "person_a": 9, "person_b": 10, "married": True}],
    events=RECORD["events"]
    + [
        {
            "id": 12,
            "kind": "married",
            "person": 9,
            "spouse": 10,
            "dateTime": "2005-01-01",
            "dateCertainty": "approximate",
        }
    ],
    lastItemId=12,
)
UNCLE = dict(
    RECORD,
    people=PEOPLE
    + [{"id": 9, "name": "Declan", "last_name": "Ward", "gender": "male"}],
    lastItemId=9,
)


@pytest.fixture(autouse=True)
def capped(run):
    run.cap = min(run.cap, CAP)


def coding_of(user, line: str, record: dict):
    case = Diagram(user_id=user.id, name="Case", data=diagramjson.dumps({}))
    db.session.add(case)
    db.session.flush()
    discussion = Discussion(user_id=user.id, diagram_id=case.id)
    db.session.add(discussion)
    db.session.flush()
    speaker = Speaker(
        discussion_id=discussion.id, name="Liam", type=SpeakerType.Subject
    )
    db.session.add(speaker)
    db.session.flush()
    statement = Statement(
        discussion_id=discussion.id, speaker_id=speaker.id, text=line, order=0
    )
    db.session.add(statement)
    db.session.flush()
    cut = Cut(
        diagram_id=case.id,
        start_statement_id=statement.id,
        end_statement_id=statement.id,
        user_id=user.id,
        meeting_date=datetime.date(2026, 10, 1),
    )
    db.session.add(cut)
    db.session.commit()
    return coded(user, cut, record, done=False), statement


def said(user, line: str, words: str, chosen=None, record=RECORD) -> tuple[dict, dict]:
    """What the scribe answered, and the diagram it left, when the coder said
    `words` about the chat line `line`."""
    coding, statement = coding_of(user, line, record)
    before = adapter.diagram_of(coding.diagram_id).version
    result = scribe.write(coding, statement, words, chosen)
    diagram = adapter.diagram_of(coding.diagram_id)
    return result, dict(
        adapter.record_of(diagram), version=diagram.version, before=before
    )


def entered(user, line: str, words: str, chosen=None, record=RECORD) -> list[dict]:
    """The events the scribe added or left changed on the record."""
    _, data = said(user, line, words, chosen, record)
    return [e for e in data.get("events") or [] if e["id"] != 5]


def kinds(events: list[dict], kind: str) -> list[dict]:
    return [e for e in events if adapter.plain(e.get("kind")) == kind]


def year(event: dict) -> str:
    return (adapter.date_text(event.get("dateTime")) or "")[:4]


def called(data: dict, name: str) -> list[int]:
    return [p["id"] for p in data["people"] if p.get("name") == name]


@once
def test_a_birth_names_the_person_born_as_its_child(test_user):
    # R-0884, R-0886
    events = entered(
        test_user,
        "Dad grew up on a farm outside Cork.",
        "Owen was born in 1948.",
        FATHER,
    )
    assert [str(e.get("child")) for e in kinds(events, "birth")] == [
        str(FATHER)
    ], events
    assert kinds(events, "noted") == [], events


@once
def test_a_marriage_whose_title_would_name_the_spouse_is_entered_once(test_user):
    # R-0884, R-0886
    events = entered(
        test_user,
        "Mum remarried when I was in college.",
        "Maeve married Declan Farrell in 1999.",
    )
    assert len(kinds(events, "married")) == 1, events


@once
def test_a_death_is_entered_though_the_line_says_the_person_is_alive(test_user):
    # R-0884, R-0885
    events = entered(
        test_user,
        "Dad is still alive, he turns eighty next spring.",
        "Owen died in 2001.",
        FATHER,
    )
    assert [str(e.get("person")) for e in kinds(events, "death")] == [
        str(FATHER)
    ], events


@once
def test_a_new_person_and_their_partner_are_entered_with_the_marriage(test_user):
    # R-0886, R-0270
    _, data = said(
        test_user,
        "My sister got married young.",
        "Liam's sister Aoife married Ciaran Byrne in 2005.",
    )
    married = kinds(data.get("events") or [], "married")
    assert len(married) == 1, data
    couple = {married[0]["person"], married[0]["spouse"]}
    assert couple == {called(data, "Aoife")[0], called(data, "Ciaran")[0]}, data
    assert year(married[0]) == "2005", data


@once
def test_a_corrected_date_changes_the_marriage(test_user):
    # R-0886, R-0270
    events = entered(
        test_user,
        "My sister got married young.",
        "Aoife and Ciaran married in 2006, not 2005.",
        record=SISTER,
    )
    married = kinds(events, "married")
    assert [(e["id"], year(e)) for e in married] == [(12, "2006")], events


@once
def test_the_same_statement_again_writes_nothing(test_user):
    # R-0883, R-0886
    _, data = said(
        test_user,
        "My sister got married young.",
        "Aoife married Ciaran Byrne in 2005.",
        record=SISTER,
    )
    assert data["version"] == data["before"], data
    assert len(data["events"]) == len(SISTER["events"]), data


@once
def test_a_first_name_two_people_share_asks_which(test_user):
    # R-0270
    result, data = said(
        test_user, "Grandad moved a lot.", "Owen moved to Galway in 1975."
    )
    assert [one["id"] for one in result["choices"]] == [2, 6], result
    assert data["version"] == data["before"], data


@once
def test_a_full_name_settles_who_moved(test_user):
    # R-0270, R-0886
    events = entered(
        test_user, "Grandad moved a lot.", "Owen Doyle moved to Galway in 1975."
    )
    noted = kinds(events, "noted")
    assert [(e["person"], year(e)) for e in noted] == [(6, "1975")], events


@once
def test_a_move_is_a_noted_event(test_user):
    # R-0886, R-0364
    events = entered(
        test_user, "I left home for work.", "Liam moved to Boston in 2008."
    )
    noted = kinds(events, "noted")
    assert [(e["person"], year(e)) for e in noted] == [(1, "2008")], events


@once
def test_a_corrected_father_moves_the_birth_and_the_child(test_user):
    # R-0886
    _, data = said(
        test_user,
        "I never knew who my real dad was until I was twenty.",
        "Liam's father was Declan Ward, not Owen Ward.",
        record=UNCLE,
    )
    birth = next(e for e in data["events"] if e["id"] == 5)
    liam = next(p for p in data["people"] if p["id"] == 1)
    bond = next(b for b in data["pair_bonds"] if b["id"] == liam["parents"])
    assert {birth["person"], birth["spouse"]} == {9, 3}, data
    assert {bond["person_a"], bond["person_b"]} == {9, 3}, data


@once
def test_a_death_is_entered_on_the_person_named(test_user):
    # R-0886
    events = entered(
        test_user, "Gran was the heart of the family.", "Clare died in 2015."
    )
    deaths = kinds(events, "death")
    assert [(e["person"], year(e)) for e in deaths] == [(7, "2015")], events
