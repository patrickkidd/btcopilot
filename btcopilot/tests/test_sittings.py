"""Sittings: one thread per family, split where the family went quiet."""

import datetime

import pytest

from btcopilot.discussions import SITTING_GAP, open_session
from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.routes.sessions import THREAD_PAGE
from btcopilot.tests.conftest import csrf_token


@pytest.fixture
def token(web):
    return csrf_token(web)


def say(web, token, words) -> int:
    return web.post(
        "/app/chat", json={"statement": words}, headers={"X-CSRFToken": token}
    ).get_json()["discussion_id"]


def age(discussion_id: int, by: datetime.timedelta):
    for s in Statement.query.filter_by(discussion_id=discussion_id):
        s.created_at -= by
    db.session.commit()


@pytest.mark.chat_flow
def test_quiet_family_starts_a_new_sitting(web, token):
    # R-0055
    first = say(web, token, "one")
    assert say(web, token, "two") == first

    age(first, SITTING_GAP + datetime.timedelta(minutes=1))
    assert say(web, token, "three") != first


@pytest.mark.chat_flow(response="noted")
def test_thread_marks_each_sitting_start(web, token):
    # R-0055
    first = say(web, token, "one")
    age(first, SITTING_GAP * 2)
    second = say(web, token, "two")

    thread = web.get("/app/statements").get_json()
    assert [(s["text"], (s["sitting"] or {}).get("id")) for s in thread] == [
        ("one", first),
        ("noted", None),
        ("two", second),
        ("noted", None),
    ]
    assert thread[0]["sitting"]["summary"] == "A session title"


def test_thread_pages_back(web, test_user):
    # R-0055
    discussion = open_session(test_user, test_user.free_diagram)
    db.session.add_all(
        Statement(
            discussion_id=discussion.id,
            speaker_id=discussion.chat_user_speaker_id,
            text=str(i),
            order=i,
        )
        for i in range(THREAD_PAGE + 10)
    )
    db.session.commit()

    newest = web.get("/app/statements").get_json()
    assert [s["text"] for s in newest] == [str(i) for i in range(10, THREAD_PAGE + 10)]
    assert newest[0]["sitting"] is None

    older = web.get(f"/app/statements?before={newest[0]['id']}").get_json()
    assert [s["text"] for s in older] == [str(i) for i in range(10)]
    assert older[0]["sitting"]["id"] == discussion.id
