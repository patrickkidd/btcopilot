"""Product notices: a message written once for everyone, a role, or named
people, which reaches each of them the next time they open the app."""

import datetime

import click

from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.admin.users import ROLES, find
from btcopilot.extensions import db
from btcopilot.models import Audience, Notice, NoticeLink, Notification, User


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


def people(notice: Notice) -> int:
    return sum(notice.reaches(user) for user in User.query.filter_by(active=True))


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
@click.option("--by", help="The email of the admin sending it.")
@rows_option
def notice_send(to, title, body, link, until, by):
    """Keep a notice. Each person it is for gets it the next time they open
    the app: a push when they have one, else an email when their role gets
    email, and in the app's own list either way. Prints the notice and how many
    people it is for now."""
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
    return [{"id": notice.id, "people": people(notice)}]


@notice_group.command("list")
@rows_option
def notice_list():
    """Every notice, newest first: who it is for, how many that is now, and
    how many got it and opened it."""
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
                "people": people(notice),
                "got": got.count(),
                "opened": got.filter(Notification.opened_at.isnot(None)).count(),
            }
        )
    return rows
