import datetime
import json

import http_ece
import pytest

import btcopilot
from btcopilot import extensions, push
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
from btcopilot.tests.conftest import csrf_token
from btcopilot.tests.test_push import service, subscribe  # noqa: F401

BODY = "Choose how often under Coach messages on your account page."
DAY = datetime.timedelta(days=1)


def notice(title: str, **columns) -> Notice:
    row = Notice(title=title, body=BODY, **columns)
    db.session.add(row)
    db.session.commit()
    return row


def test_each_open_makes_one_row_per_running_notice_meant_for_the_person(
    web, test_user, test_user_2
):
    # R-0017
    now = datetime.datetime.utcnow()
    everyone = notice("For all", audience=Audience.Everyone, link=NoticeLink.Account)
    notice("For coders", audience=Audience.Role, role=btcopilot.ROLE_AUDITOR)
    notice("For them", audience=Audience.People, user_ids=[test_user_2.id])
    notice("Over", audience=Audience.Everyone, ends_at=now)
    notice("Not yet", audience=Audience.Everyone, starts_at=now + DAY)
    first = web.get("/app/notifications").json
    assert first == web.get("/app/notifications").json
    assert [(r["kind"], r["title"], r["body"], r["link"]) for r in first] == [
        ("notice", "For all", BODY, "account")
    ]
    push.notices(test_user_2)
    db.session.commit()
    assert sorted(
        (n.user_id, n.notice.title)
        for n in Notification.query.filter_by(kind=NotificationKind.Notice)
    ) == [
        (test_user.id, "For all"),
        (test_user_2.id, "For all"),
        (test_user_2.id, "For them"),
    ]
    assert Notification.query.filter_by(notice_id=everyone.id).count() == 2


def test_someone_who_joins_the_audience_later_gets_it_on_their_next_open(
    web, test_user
):
    # R-0017
    notice("For coders", audience=Audience.Role, role=btcopilot.ROLE_AUDITOR)
    assert web.get("/app/notifications").json == []
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    [row] = web.get("/app/notifications").json
    assert (row["title"], row["link"], row["opened_at"]) == ("For coders", None, None)
    path = f"/app/notifications/{row['id']}"
    opened = web.patch(
        path, json={"opened": True}, headers={"X-CSRFToken": csrf_token(web)}
    )
    assert opened.json["opened_at"] is not None
    assert web.get("/app/notifications").json == []
    assert [r["id"] for r in web.get("/app/notifications?all=true").json] == [row["id"]]


def test_a_notice_push_carries_its_own_kind_and_its_title(test_user, service):
    # R-0017
    posts, _ = service
    key, secret = subscribe(test_user, "https://push.example/phone")
    notice("New in the app", audience=Audience.Everyone)
    with extensions.mail.record_messages() as outbox:
        [sent] = push.notices(test_user)
    [post] = posts
    body = http_ece.decrypt(
        post["data"], private_key=key, auth_secret=secret, version="aes128gcm"
    )
    assert json.loads(body) == {
        "id": sent.id,
        "kind": "notice",
        "body": "New in the app",
    }
    assert (sent.channel, outbox) == (NotificationChannel.Push, [])


@pytest.mark.parametrize(
    "role, channel, emails",
    [
        (btcopilot.ROLE_SUBSCRIBER, NotificationChannel.App, []),
        (btcopilot.ROLE_AUDITOR, NotificationChannel.Email, ["New in the app"]),
    ],
)
def test_with_no_push_only_a_role_that_gets_email_is_emailed(
    test_user, role, channel, emails
):
    # R-0017
    test_user.roles = role
    db.session.commit()
    notice("New in the app", audience=Audience.Everyone)
    with extensions.mail.record_messages() as outbox:
        [sent] = push.notices(test_user)
    assert sent.channel == channel
    assert [m.subject for m in outbox] == emails


def test_the_command_reads_everyone_a_role_or_addresses(
    flask_app, test_user, test_user_2
):
    # R-0390
    test_user_2.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    runner = flask_app.test_cli_runner()

    def send(to, *extra):
        words = ["notice", "send", "--to", to, "--title", "T", "--body", BODY]
        return runner.invoke(admin, [*words, *extra, "--json"])

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
    listed = json.loads(runner.invoke(admin, ["notice", "list", "--json"]).output)
    assert [r["to"] for r in listed] == [test_user.username, "auditor", "everyone"]
    refused = send("nobody@example.com")
    assert (
        refused.exit_code != 0 and "no account for nobody@example.com" in refused.output
    )


def test_the_notice_fixture_reinstalls_and_reaches_no_other_fixture(
    flask_app, foreign_keys
):
    # R-0322
    install("notice")
    user = install("notice")
    other = install("one")
    assert push.notices(user) == push.notices(other) == []
    assert sorted(
        (n.kind, n.notice.title if n.notice else None, n.opened_at is None)
        for n in Notification.query.filter_by(user_id=user.id)
    ) == [
        (NotificationKind.Coach, None, True),
        (NotificationKind.Notice, "Coach messages can now come weekly", True),
        (NotificationKind.Notice, "Welcome to the app", False),
    ]
    assert Notice.query.count() == 2
