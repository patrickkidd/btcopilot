import datetime
import json

import http_ece
import pytest

import btcopilot
from btcopilot import extensions
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import (
    Audience,
    Notice,
    NoticeLink,
    Notification,
    NotificationChannel,
    NotificationKind,
)
from btcopilot.routes.fixtures import install
from btcopilot.routes.notifications import missed
from btcopilot.tests.conftest import csrf_token
from btcopilot.tests.test_push import service, subscribe  # noqa: F401

BODY = "Choose how often under Coach messages on your account page."
DAY = datetime.timedelta(days=1)


def notice(title: str, **columns) -> Notice:
    row = Notice(title=title, body=BODY, **columns)
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture
def send(flask_app):
    runner = flask_app.test_cli_runner()

    def invoke(to, *extra):
        words = ["notice", "send", "--to", to, "--title", "New", "--body", BODY]
        return runner.invoke(admin, [*words, *extra, "--json"])

    return invoke


@pytest.mark.parametrize(
    "flag, channel, emails", [((), "app", []), (("--email",), "email", ["New"])]
)
def test_sending_delivers_now_to_everyone_it_is_for(
    send, test_user, test_user_2, service, flag, channel, emails
):
    # R-0017
    posts, _ = service
    key, secret = subscribe(test_user, "https://push.example/phone")
    with extensions.mail.record_messages() as outbox:
        result = send("everyone", *flag)
    assert json.loads(result.output)[0]["people"] == 2
    rows = {n.user_id: n for n in Notification.query}
    assert (rows[test_user.id].channel, rows[test_user_2.id].channel) == (
        NotificationChannel.Push,
        NotificationChannel(channel),
    )
    [post] = posts
    body = http_ece.decrypt(
        post["data"], private_key=key, auth_secret=secret, version="aes128gcm"
    )
    assert json.loads(body) == {
        "id": rows[test_user.id].id,
        "kind": "notice",
        "body": "New",
    }
    assert [m.subject for m in outbox] == emails


def test_each_open_makes_one_row_per_running_notice_meant_for_the_person(
    web, test_user, test_user_2
):
    # R-0017
    now = datetime.datetime.utcnow()
    notice("For all", audience=Audience.Everyone, link=NoticeLink.Account)
    notice("For coders", audience=Audience.Role, role=btcopilot.ROLE_AUDITOR)
    notice("For them", audience=Audience.People, user_ids=[test_user_2.id])
    notice("Over", audience=Audience.Everyone, ends_at=now)
    notice("Not yet", audience=Audience.Everyone, starts_at=now + DAY)
    first = web.get("/app/notifications").json
    assert first == web.get("/app/notifications").json
    assert [
        (r["kind"], r["channel"], r["title"], r["body"], r["link"]) for r in first
    ] == [("notice", "app", "For all", BODY, "account")]


def test_someone_who_joins_the_audience_later_finds_it_in_the_app_only(
    web, test_user, send, service
):
    # R-0017
    posts, _ = service
    send("auditor", "--email")
    assert web.get("/app/notifications").json == []
    subscribe(test_user, "https://push.example/phone")
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    with extensions.mail.record_messages() as outbox:
        [row] = web.get("/app/notifications").json
    assert (row["title"], row["channel"], row["opened_at"]) == ("New", "app", None)
    assert (posts, outbox) == ([], [])
    path = f"/app/notifications/{row['id']}"
    opened = web.patch(
        path, json={"opened": True}, headers={"X-CSRFToken": csrf_token(web)}
    )
    assert opened.json["opened_at"] is not None
    assert web.get("/app/notifications").json == []
    assert [r["id"] for r in web.get("/app/notifications?all=true").json] == [
        row["id"]
    ]


def test_the_command_reads_everyone_a_role_or_addresses(
    flask_app, send, test_user, test_user_2
):
    # R-0390
    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    people = {
        to: json.loads(send(to).output)[0]["people"] for to in ("everyone", "auditor")
    }
    people[test_user.username] = json.loads(
        send(test_user.username, "--link", "account", "--until", "2026-10-01").output
    )[0]["people"]
    assert people == {"everyone": 2, "auditor": 1, test_user.username: 1}
    assert [
        (n.audience, n.role, n.user_ids, n.link, n.ends_at)
        for n in Notice.query.order_by(Notice.id)
    ] == [
        (Audience.Everyone, None, None, None, None),
        (Audience.Role, btcopilot.ROLE_AUDITOR, None, None, None),
        (
            Audience.People,
            None,
            [test_user.id],
            NoticeLink.Account,
            datetime.datetime(2026, 10, 2),
        ),
    ]
    runner = flask_app.test_cli_runner()
    listed = json.loads(runner.invoke(admin, ["notice", "list", "--json"]).output)
    assert [(r["to"], r["got"]) for r in listed] == [
        (test_user.username, 1),
        ("auditor", 1),
        ("everyone", 2),
    ]
    refused = send("nobody@example.com")
    assert refused.exit_code != 0
    assert "no account for nobody@example.com" in refused.output


def test_the_notice_fixture_reinstalls_and_reaches_no_other_fixture(
    flask_app, foreign_keys
):
    # R-0322
    install("notice")
    user = install("notice")
    other = install("one")
    assert missed(user) == missed(other) == []
    assert sorted(
        (n.kind, n.notice.title if n.notice else None, n.opened_at is None)
        for n in Notification.query.filter_by(user_id=user.id)
    ) == [
        (NotificationKind.Coach, None, True),
        (NotificationKind.Notice, "Coach messages can now come weekly", True),
        (NotificationKind.Notice, "Welcome to the app", False),
    ]
    assert Notice.query.count() == 2
