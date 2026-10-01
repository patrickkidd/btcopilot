"""A new auditor and one conversation on the agenda for the onboarding walk
(sandboxonboarding): each run makes an auditor who has seen nothing yet, tells
them of the cut the way dating it on the agenda does, and prints the id of
that notification and then their sign-in link. Run from the repo root with the
sandbox's Flask settings: uv run python btcopilot/tests/frontend/seedauditor.py"""

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
    Notification,
    Speaker,
    SpeakerType,
    Statement,
    User,
)
from btcopilot.review import notify
from btcopilot.review.models import Cut
from btcopilot.routes.fixtures import DOMAIN

LINES = [
    "My mother moved in with us in 2019, after my father died.",
    "Since then my sister and I barely speak.",
    "I started sleeping badly that winter.",
]


def account(name: str, role: str) -> User:
    user = User(username=f"{name}@{DOMAIN}", status="confirmed", roles=role)
    db.session.add(user)
    db.session.commit()
    return user


app = create_app()
with app.app_context():
    stamp = secrets.token_hex(4)
    auditor = account(f"auditor-{stamp}", btcopilot.ROLE_AUDITOR)
    auditor.set_free_diagram(_commit=True)
    admin = account(f"agenda-{stamp}", btcopilot.ROLE_ADMIN)
    case = Diagram(user_id=admin.id, name="Case", data=diagramjson.dumps({}))
    db.session.add(case)
    db.session.flush()
    discussion = Discussion(
        user_id=admin.id, diagram_id=case.id, title="Onboarding case"
    )
    db.session.add(discussion)
    db.session.flush()
    client = Speaker(
        discussion_id=discussion.id, name="Client", type=SpeakerType.Subject
    )
    db.session.add(client)
    db.session.flush()
    turns = [
        Statement(
            discussion_id=discussion.id, speaker_id=client.id, text=text, order=order
        )
        for order, text in enumerate(LINES)
    ]
    db.session.add_all(turns)
    db.session.flush()
    cut = Cut(
        diagram_id=discussion.diagram_id,
        start_statement_id=turns[0].id,
        end_statement_id=turns[-1].id,
        user_id=admin.id,
        meeting_date=datetime.date.today() + datetime.timedelta(days=7),
    )
    db.session.add(cut)
    db.session.flush()
    notify.told(cut, datetime.datetime.utcnow())
    db.session.commit()
    told = Notification.query.filter_by(user_id=auditor.id, cut_id=cut.id).one()
    print(f"notification {told.id}")
    token = Invitation.issue(
        auditor.username, current_app.config["INVITATION_DAYS"]
    ).token
    print(f"{current_app.config['SITE_URL']}/app/invite/{token}")
