"""The scribe enters the coder's statement as given: a birth names the person
born as its child, an event already entered is changed rather than added again,
and the coder's words are never weighed against the chat line they code
(R-0884).

Each case is one of the faults seen on the walk sandbox on 2026-10-21, with
invented people.
"""

import datetime

from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.models import Diagram, Discussion, Speaker, SpeakerType, Statement
from btcopilot.review import adapter, scribe
from btcopilot.review.models import Cut
from btcopilot.tests.live.criterion import passes
from btcopilot.tests.review.conftest import coded

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


def entered(user, line: str, said: str, chosen=None) -> list[dict]:
    """The events the scribe added to a fresh coding of the record when the
    coder said `said` about the chat line `line`."""
    case = Diagram(user_id=user.id, name="Case", data=diagramjson.dumps({}))
    db.session.add(case)
    db.session.flush()
    discussion = Discussion(user_id=user.id, diagram_id=case.id)
    db.session.add(discussion)
    db.session.flush()
    speaker = Speaker(discussion_id=discussion.id, name="Liam", type=SpeakerType.Subject)
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
    coding = coded(user, cut, RECORD, done=False)
    scribe.write(coding, statement, said, chosen)
    events = adapter.record_of(adapter.diagram_of(coding.diagram_id)).get("events") or []
    return [e for e in events if e["id"] != 5]


def kinds(events: list[dict], kind: str) -> list[dict]:
    return [e for e in events if adapter.plain(e.get("kind")) == kind]


@passes(3, of=3)
def test_a_birth_names_the_person_born_as_its_child(test_user):
    # R-0884
    events = entered(
        test_user, "Dad grew up on a farm outside Cork.", "Owen was born in 1948.", FATHER
    )
    assert [str(e.get("child")) for e in kinds(events, "birth")] == [str(FATHER)], events
    assert kinds(events, "noted") == [], events


@passes(3, of=3)
def test_a_marriage_whose_title_would_name_the_spouse_is_entered_once(test_user):
    # R-0884
    events = entered(
        test_user,
        "Mum remarried when I was in college.",
        "Maeve married Declan Farrell in 1999.",
    )
    assert len(kinds(events, "married")) == 1, events


@passes(3, of=3)
def test_a_death_is_entered_though_the_line_says_the_person_is_alive(test_user):
    # R-0884
    events = entered(
        test_user,
        "Dad is still alive, he turns eighty next spring.",
        "Owen died in 2001.",
        FATHER,
    )
    assert [str(e.get("person")) for e in kinds(events, "death")] == [str(FATHER)], events
