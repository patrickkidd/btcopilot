"""Where a browser is reached for web push, and the pointers sent to a coach
message, each stamped when its person opens it."""

import datetime

import click
from flask import abort, current_app, jsonify, request

from btcopilot import auth, push
from btcopilot.discussions import utc_iso
from btcopilot.extensions import db
from btcopilot.models import Notification, PushSubscription, Statement, User
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


@bp.route("/notifications/<int:notification_id>", methods=["PATCH"])
def update_notification(notification_id: int):
    """The first open counts; the answer says where the thread opens."""
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != auth.current_user().id:
        abort(404)
    if request.get_json() != {"opened": True}:
        raise ValueError('a notification only takes {"opened": true}')
    notification.opened_at = notification.opened_at or datetime.datetime.utcnow()
    db.session.commit()
    return jsonify(
        {
            "id": notification.id,
            "channel": notification.channel.value,
            "statement_id": notification.statement_id,
            "discussion_id": notification.statement.discussion_id,
            "opened_at": utc_iso(notification.opened_at),
        }
    )


@bp.cli.command("notify")
@click.argument("email")
@click.argument("statement_id", type=int)
def notify_command(email: str, statement_id: int):
    """Point one person at one coach message now: a push, or an email when
    they have no subscription. Prints the notification's id and channel."""
    user = User.query.filter_by(username=email).one()
    notification = push.send(user, db.session.get(Statement, statement_id))
    click.echo(f"{notification.id} {notification.channel.value}")
