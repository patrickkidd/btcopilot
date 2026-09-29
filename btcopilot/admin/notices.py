"""Product notices: a message written once for everyone, a role, or named
people, sent to each of them at once; whoever joins its audience later finds
it in the app."""

import datetime
import logging

import click
from pywebpush import WebPushException

from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot import push
from btcopilot.admin.users import ROLES, find
from btcopilot.extensions import db
from btcopilot.models import Audience, Notice, NoticeLink, Notification, User

_log = logging.getLogger(__name__)


def audience(to: str) -> dict:
    """--to as the notice's columns."""
    if to == Audience.Everyone:
        return {"audience": Audience.Everyone}
    if to in ROLES:
        return {"audience": Audience.Role, "role": to}
    return {
        "audience": Audience.People,
        "user_ids": [find(email).id for email in to.split(",")],
    }


def recipients(notice: Notice) -> str:
    if notice.audience == Audience.People:
        people = User.query.filter(User.id.in_(notice.user_ids)).order_by(User.id)
        return ",".join(user.username for user in people)
    return notice.role or notice.audience.value


def people(notice: Notice) -> list[User]:
    active = User.query.filter_by(active=True).order_by(User.id)
    return [user for user in active if notice.reaches(user)]


@click.group("notice")
def notice_group():
    """Product notices shown in the app, to everyone, a role, or named people."""


@writes
@notice_group.command("send")
@click.option(
    "--to",
    required=True,
    help=f"everyone, a role ({', '.join(ROLES)}), or email addresses joined by commas.",
)
@click.option("--title", required=True, help="The heading, and the words of the push.")
@click.option("--body", required=True, help="One or two short sentences.")
@click.option(
    "--link",
    type=click.Choice([link.value for link in NoticeLink]),
    help="The screen a tap opens; left out, it opens nothing.",
)
@click.option(
    "--until",
    type=click.DateTime(["%Y-%m-%d"]),
    help="The last day, in UTC, that it reaches anyone new; left out, it runs on.",
)
@click.option(
    "--email",
    is_flag=True,
    help="Email everyone it is for who has no browser that takes a push.",
)
@click.option("--by", help="The email of the admin sending it.")
@rows_option
def notice_send(to, title, body, link, until, email, by):
    """Keep a notice and send it now to everyone it is for: a push to whoever
    has one, else an email when --email is given, and in the app's own list
    either way. Whoever joins its audience later finds it in the app's list
    the next time they open the app. Prints the notice and how many people it
    was sent to."""
    notice = Notice(
        title=title,
        body=body,
        link=NoticeLink(link) if link else None,
        ends_at=until + datetime.timedelta(days=1) if until else None,
        created_by=find(by).id if by else None,
        **audience(to),
    )
    db.session.add(notice)
    db.session.commit()
    sent = 0
    for user in people(notice):
        try:
            with db.session.begin_nested():
                push.send_notice(user, notice, email)
            sent += 1
        except WebPushException as e:
            _log.error(f"notice {notice.id} did not reach {user.username}: {push.failure(e)}")
        db.session.commit()
    return [{"id": notice.id, "people": sent}]


@notice_group.command("list")
@rows_option
def notice_list():
    """Every notice, newest first: who it is for, how many that is now, and
    how many have it and opened it."""
    rows = []
    for notice in Notice.query.order_by(Notice.id.desc()):
        got = Notification.query.filter_by(notice_id=notice.id)
        rows.append(
            {
                "id": notice.id,
                "title": notice.title,
                "to": recipients(notice),
                "link": notice.link.value if notice.link else None,
                "ends_at": notice.ends_at,
                "people": len(people(notice)),
                "got": got.count(),
                "opened": got.filter(Notification.opened_at.isnot(None)).count(),
            }
        )
    return rows
