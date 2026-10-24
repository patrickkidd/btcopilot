"""A cut ready for the meeting walk (sandboxmeeting): each run makes an admin
who runs the table, a conversation on its own meeting day, two coders who each
submitted a coding of it that read four events differently and one the same,
and opens the vote on it, the way the table does. Prints the cut's id, its
meeting day and the admin's sign-in link. Run from the repo root with the
sandbox's Flask settings: uv run python btcopilot/tests/frontend/seedmeeting.py"""

import datetime
import secrets

from flask import current_app

import btcopilot
from btcopilot import diagramjson
from btcopilot.app import create_app
from btcopilot.auth.invitation import Invitation
from btcopilot.extensions import db
from btcopilot.models import (
    Diagram,
    Discussion,
    Speaker,
    SpeakerType,
    Statement,
    User,
)
from btcopilot.review import adapter, snapshot
from btcopilot.review.models import Coding, Cut
from btcopilot.routes.fixtures import DOMAIN

LINES = [
    "My mother moved in with us in 2019, after my father died.",
    "Since then my sister and I barely speak.",
    "I started sleeping badly that winter.",
    "My husband works longer hours now.",
]

PEOPLE = [
    {"id": 1, "name": "Ann", "gender": "female"},
    {"id": 2, "name": "Ruth", "gender": "female"},
]


def shift(event_id: int, person: int, description: str, date: str, **fields) -> dict:
    return {
        "id": event_id,
        "kind": "shift",
        "person": person,
        "title": description,
        "description": description,
        "dateTime": date,
        **fields,
    }


# The same five events as each coder wrote them: the first four read
# differently, the last the same way, so the vote has four items to decide and
# one agreed before it.
EVENTS = [
    ("Mother moved in", 2, "2019-03-01", {"functioning": "down"}, {"functioning": "up"}),
    ("Stopped speaking to sister", 1, "2019-06-01", {"relationship": "distance", "relationshipTargets": [2]}, {"relationship": "conflict", "relationshipTargets": [2]}),
    ("Sleeping badly", 1, "2019-12-01", {"symptom": "up"}, {"anxiety": "up"}),
    ("Husband works longer hours", 1, "2020-02-01", {"anxiety": "up"}, {"anxiety": "same"}),
    ("Father died", 2, "2018-11-01", {"symptom": "up"}, {"symptom": "up"}),
]


def account(name: str, role: str, first="", last="") -> User:
    user = User(
        username=f"{name}@{DOMAIN}",
        status="confirmed",
        roles=role,
        first_name=first,
        last_name=last,
    )
    db.session.add(user)
    db.session.commit()
    user.set_free_diagram(_commit=True)
    return user


def coded(user: User, cut: Cut, version: int) -> Coding:
    record = {
        "people": PEOPLE,
        "events": [
            shift(10 + at, person, text, date, **(first, second)[version])
            for at, (text, person, date, first, second) in enumerate(EVENTS)
        ],
    }
    diagram = Diagram(
        user_id=user.id, name="coding of Case", data=diagramjson.dumps(record)
    )
    db.session.add(diagram)
    db.session.flush()
    adapter.grant_write(diagram, user)
    coding = Coding(
        cut_id=cut.id,
        user_id=user.id,
        diagram_id=diagram.id,
        done_at=adapter.utcnow(),
    )
    db.session.add(coding)
    db.session.flush()
    return coding


app = create_app()
with app.app_context():
    stamp = secrets.token_hex(4)
    admin = account(f"table-{stamp}", btcopilot.ROLE_ADMIN)
    # Named, so the meeting's tally line carries their initials.
    coders = [
        account(f"coder{n}-{stamp}", btcopilot.ROLE_AUDITOR, first, last)
        for n, (first, last) in enumerate([("Cara", "Dunn"), ("Eli", "Fox")])
    ]
    case = Diagram(user_id=admin.id, name="Case", data=diagramjson.dumps({}))
    db.session.add(case)
    db.session.flush()
    discussion = Discussion(
        user_id=admin.id, diagram_id=case.id, title=f"Meeting case {stamp}"
    )
    db.session.add(discussion)
    db.session.flush()
    client = Speaker(
        discussion_id=discussion.id, name="Client", type=SpeakerType.Subject
    )
    coach = Speaker(
        discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert
    )
    db.session.add_all([client, coach])
    db.session.flush()
    discussion.chat_user_speaker_id = client.id
    discussion.chat_ai_speaker_id = coach.id
    turns = [
        Statement(
            discussion_id=discussion.id,
            speaker_id=(client, coach)[order % 2].id,
            text=text,
            order=order,
        )
        for order, text in enumerate(LINES)
    ]
    db.session.add_all(turns)
    db.session.flush()
    # A meeting day of its own, so another walk's cuts on the shared sandbox
    # are never in this meeting.
    day = datetime.date.today() + datetime.timedelta(
        days=30 + secrets.randbelow(20000)
    )
    cut = Cut(
        diagram_id=case.id,
        start_statement_id=turns[0].id,
        end_statement_id=turns[-1].id,
        user_id=admin.id,
        meeting_date=day,
    )
    db.session.add(cut)
    db.session.flush()
    for version, user in enumerate(coders):
        coded(user, cut, version)
    db.session.refresh(cut)
    cut.vote_opened_at = adapter.utcnow()
    snapshot.build(cut)
    snapshot.recompute(cut)
    db.session.commit()
    print(f"cut {cut.id}")
    print(f"day {day.isoformat()}")
    token = Invitation.issue(
        admin.username, current_app.config["INVITATION_DAYS"]
    ).token
    print(f"{current_app.config['SITE_URL']}/app/invite/{token}")
