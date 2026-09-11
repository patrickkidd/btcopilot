import datetime

import pytest
from mock import patch

import btcopilot
from btcopilot import diagramjson
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Speaker, SpeakerType, Statement
from btcopilot.pro.models import Diagram
from btcopilot.review import ruledraft
from btcopilot.review.models import Coding, Cut
from btcopilot.tests.pro.conftest import pro_client  # noqa: F401  autouse client


@pytest.fixture(autouse=True)
def no_csrf(flask_app):
    """The review's endpoints are JSON, driven here without a page to read a
    token from. One test puts the check back to prove it is on."""
    flask_app.config["WTF_CSRF_METHODS"] = []


@pytest.fixture(autouse=True)
def no_coach():
    """No test reaches the real coach; the drafting test scripts its own."""
    with patch.object(ruledraft, "draft", return_value=[]) as drafted:
        yield drafted


def sign_in(flask_app, user, role):
    user.roles = role
    db.session.merge(user)
    db.session.commit()
    client = flask_app.test_client(use_cookies=True, user=user)
    client.user = user
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["logged_in_at"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
    return client


@pytest.fixture
def patrick(flask_app, test_user):
    """The admin: the only one who opens a vote or ratifies (R-0273)."""
    return sign_in(flask_app, test_user, btcopilot.ROLE_ADMIN)


@pytest.fixture
def coder(flask_app, test_user_2):
    return sign_in(flask_app, test_user_2, btcopilot.ROLE_SUBSCRIBER)


@pytest.fixture
def case(test_user):
    diagram = Diagram(
        user_id=test_user.id, name="Case A", data=diagramjson.dumps({})
    )
    db.session.add(diagram)
    db.session.commit()
    return diagram


@pytest.fixture
def session(test_user, case):
    """A session of the case with four turns to cut."""
    discussion = Discussion(user_id=test_user.id, diagram_id=case.id)
    db.session.add(discussion)
    db.session.commit()
    subject = Speaker(
        discussion_id=discussion.id, name="Client", type=SpeakerType.Subject
    )
    db.session.add(subject)
    db.session.commit()
    for order in range(4):
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=subject.id,
                text=f"turn {order}",
                order=order,
            )
        )
    db.session.commit()
    return discussion


@pytest.fixture
def turns(session):
    return sorted(session.statements, key=lambda s: s.order)


@pytest.fixture
def cut(test_user, session, turns):
    cut = Cut(
        discussion_id=session.id,
        start_statement_id=turns[0].id,
        end_statement_id=turns[1].id,
        user_id=test_user.id,
        meeting_date=datetime.date(2026, 10, 1),
    )
    db.session.add(cut)
    db.session.commit()
    return cut


def coded(user, cut, record: dict, done=True) -> Coding:
    """A finished coding on a record with the given people and events."""
    diagram = Diagram(
        user_id=user.id, name=f"coding by {user.id}", data=diagramjson.dumps(record)
    )
    db.session.add(diagram)
    db.session.flush()
    coding = Coding(
        cut_id=cut.id,
        user_id=user.id,
        diagram_id=diagram.id,
        done_at=datetime.datetime.utcnow() if done else None,
    )
    db.session.add(coding)
    db.session.commit()
    return coding


def person(person_id: int, name: str) -> dict:
    return {"id": person_id, "name": name, "gender": "female"}


def shift(event_id: int, person_id: int, description: str, date="2020-01-01") -> dict:
    return {
        "id": event_id,
        "kind": "shift",
        "person": person_id,
        "description": description,
        "symptom": "up",
        "dateTime": date,
    }
