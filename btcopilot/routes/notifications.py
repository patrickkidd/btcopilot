"""Where a browser is reached for web push, and each person's notifications:
coach messages, coding tasks and product notices, each stamped when its person
opens or dismisses it."""

import datetime

import click
from flask import abort, current_app, jsonify, request

from btcopilot import auth, push
from btcopilot.discussions import utc_iso
from btcopilot.extensions import db
from btcopilot.models import (
    Notice,
    NoticeLink,
    Notification,
    NotificationChannel,
    NotificationKind,
    PushSubscription,
    Statement,
    User,
)
from btcopilot.routes import bp


@bp.route("/push-subscriptions", methods=["GET"])
def push_subscriptions():
    """The server's public key comes with the rows, since a browser needs it
    to make one."""
    rows = PushSubscription.query.filter_by(user_id=auth.current_user().id).all()
    return jsonify(
        {
            "key": current_app.config["VAPID_PUBLIC_KEY"],
            "subscriptions": [{"id": r.id, "endpoint": r.endpoint} for r in rows],
        }
    )


@bp.route("/push-subscriptions", methods=["POST"])
def create_push_subscription():
    """A browser's own subscription as it serializes it; one it already sent
    moves to whoever is signed in on it now."""
    data = request.get_json()
    row = PushSubscription.query.filter_by(
        endpoint=data["endpoint"]
    ).first() or PushSubscription(endpoint=data["endpoint"])
    row.user_id = auth.current_user().id
    row.p256dh = data["keys"]["p256dh"]
    row.auth = data["keys"]["auth"]
    # added only once whole: reading the user may flush the session
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id, "endpoint": row.endpoint}), 201


# The screen a row that is no notice opens; a coach message opens its thread.
LINKS = {
    NotificationKind.Task: NoticeLink.Task,
    NotificationKind.Reminder: NoticeLink.Task,
}


def row(notification: Notification) -> dict:
    notice = notification.notice
    statement = notification.statement
    link = notice.link if notice else LINKS.get(notification.kind)
    return {
        "id": notification.id,
        "kind": notification.kind.value,
        "channel": notification.channel.value,
        "title": notice.title if notice else push.SUBJECT[notification.kind],
        "body": notice.body if notice else None,
        "link": link,
        "statement_id": notification.statement_id,
        "discussion_id": statement.discussion_id if statement else None,
        "cut_id": notification.cut_id,
        "created_at": utc_iso(notification.created_at),
        "opened_at": (
            utc_iso(notification.opened_at) if notification.opened_at else None
        ),
    }


def missed(user) -> list[Notification]:
    """A row in the app's list, sent nowhere, for each running notice this
    person joined the audience of after it was sent. Not committed."""
    have = {
        row.notice_id
        for row in Notification.query.filter(
            Notification.user_id == user.id, Notification.notice_id.isnot(None)
        )
    }
    rows = [
        Notification(
            user_id=user.id,
            kind=NotificationKind.Notice,
            notice_id=notice.id,
            channel=NotificationChannel.App,
        )
        for notice in Notice.live(datetime.datetime.utcnow())
        if notice.id not in have and notice.reaches(user)
    ]
    db.session.add_all(rows)
    return rows


@bp.route("/notifications", methods=["GET"])
def notifications():
    """Unread rows of every kind, newest first; ?all=true adds the opened
    ones. A notice this person joined the audience of after it was sent
    becomes their row here."""
    user = auth.current_user()
    missed(user)
    db.session.commit()
    query = Notification.query.filter_by(user_id=user.id)
    if request.args.get("all") != "true":
        query = query.filter(Notification.opened_at.is_(None))
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
    return jsonify([row(notification) for notification in query])


@bp.route("/notifications/<int:notification_id>", methods=["PATCH"])
def update_notification(notification_id: int):
    """Opening and dismissing are one stamp, and the first counts; the answer
    is the row, saying where the app opens: the thread at a coach message, the
    task card for a cut, or a notice's link."""
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != auth.current_user().id:
        abort(404)
    if request.get_json() != {"opened": True}:
        raise ValueError('a notification only takes {"opened": true}')
    notification.opened_at = notification.opened_at or datetime.datetime.utcnow()
    db.session.commit()
    return jsonify(row(notification))


@bp.cli.command("notify")
@click.argument("email")
@click.argument("statement_id", type=int)
def notify_command(email: str, statement_id: int):
    """Point one person at one coach message now: a push, or an email when
    they have no subscription. Prints the notification's id and channel."""
    user = User.query.filter_by(username=email).one()
    notification = push.send(user, db.session.get(Statement, statement_id))
    db.session.commit()
    click.echo(f"{notification.id} {notification.channel.value}")
