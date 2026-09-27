import datetime

import pytest
import flask.json

import btcopilot
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.theorypages import TheoryPages

from btcopilot.tests.personal.conftest import discussion, discussions


def set_test_session(sess, user_id):
    sess["user_id"] = user_id
    sess["logged_in_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()


@pytest.fixture
def logged_in(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def subscriber(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def auditor(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def admin(flask_app, test_user):
    test_user.roles = btcopilot.ROLE_ADMIN
    db.session.merge(test_user)
    db.session.commit()
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            set_test_session(sess, test_user.id)
        yield client


@pytest.fixture
def diagram_with_full_data(test_user):
    """Create a diagram with discussions, speakers, statements, feedbacks, and access rights"""
    from btcopilot.pro.models import Diagram, AccessRight
    from btcopilot.schema import DiagramData
    from btcopilot.training.models import Feedback

    diagram = Diagram(
        user_id=test_user.id,
        name="Test Diagram",
        data=b"",
    )

    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=diagram.id,
        summary="Test discussion",
    )
    db.session.add(discussion)
    db.session.commit()

    subject_speaker = Speaker(
        discussion_id=discussion.id,
        name="User",
        type=SpeakerType.Subject,
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id,
        name="AI",
        type=SpeakerType.Expert,
    )
    db.session.add_all([subject_speaker, expert_speaker])
    db.session.commit()

    statement1 = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I feel anxious",
        order=0,
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Tell me more",
        order=1,
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    feedback = Feedback(
        statement_id=statement1.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db.session.add(feedback)

    access_right = AccessRight(
        diagram_id=diagram.id,
        user_id=test_user.id,
        right="read_write",
    )
    db.session.add(access_right)
    db.session.commit()

    return {
        "diagram": diagram,
        "discussion": discussion,
        "speakers": [subject_speaker, expert_speaker],
        "statements": [statement1, statement2],
        "feedback": feedback,
        "access_right": access_right,
    }


@pytest.fixture
def simple_diagram(test_user):
    """Create a simple diagram without discussions"""
    from btcopilot.pro.models import Diagram
    from btcopilot.schema import DiagramData

    diagram = Diagram(
        user_id=test_user.id,
        name="Simple Diagram",
        data=b"",
    )

    empty_database = DiagramData()
    diagram.set_diagram_data(empty_database)

    db.session.add(diagram)
    db.session.commit()

    return diagram


def flask_json(data: dict) -> dict:
    sdata = flask.json.dumps(data)
    return flask.json.loads(sdata)


THEORY_PAGES = {
    "README.md": """# Concept pages for coders

## Public copy

| Key | Source | File | Visibility |
|---|---|---|---|
| FE*n* L*x* | Kerr and Bowen, *Family Evaluation* | [`BT:FE`](../../bowentheory/FE.md) | PUBLIC |
| SEM *m* | App Seminar | [`FR:transcripts/seminar/`](../transcripts/seminar/) | CONFIDENTIAL |
""",
    "INDEX.md": """# Concept pages: index

| Page | Covers | Entries | Status of the code |
|---|---|---|---|
| [`anxiety.md`](anxiety.md) (A) | What anxiety is | 3 | Own evidence ruled |
| [`conflict.md`](conflict.md) (C) | Conflict as a move | 1 | Two rules |

Total: 4 entries, 2 CONFIDENTIAL.
""",
    "anxiety.md": """# Anxiety (A)

- Sources are in [`README.md`](README.md); see [`conflict.md`](conflict.md#C1) and [`../REFERENCE.md`](../REFERENCE.md).

## 2. What the original authors wrote

- <a id="A1"></a>**A1** \u201canxiety is the response to a threat\u201d Kerr, FE5 L9 \u00b7 PUBLIC. The standard definition. <!-- v BT:FE Chapters/5 - Chronic Anxiety.md L9 -->
- <a id="A2"></a>**A2** \u201cthe lighthouse keeper worried all winter\u201d Member, SEM 2024 @00:01:00 \u00b7 CONFIDENTIAL. A seminar reading. <!-- v FR:transcripts/seminar/x.tsv @00:01:00 -->
<!-- CONFIDENTIAL -->
### App Seminar
- <a id="A3"></a>**A3** \u201cthe ferry captain stopped sleeping\u201d Member, SEM 2025 @00:02:00. A second reading.
<!-- /CONFIDENTIAL -->
""",
    "conflict.md": """# Conflict (C)

- <a id="C1"></a>**C1** \u201ctwo people fight over an issue\u201d Bowen, FE7 L2 \u00b7 PUBLIC. A move by two.
""",
}


@pytest.fixture
def theory_dir(tmp_path):
    path = tmp_path / "CONCEPTS"
    path.mkdir()
    for name, text in THEORY_PAGES.items():
        (path / name).write_text(text)
    return path


@pytest.fixture
def theory(flask_app, theory_dir):
    flask_app.extensions["theory"] = TheoryPages(dir=theory_dir)
    return theory_dir
