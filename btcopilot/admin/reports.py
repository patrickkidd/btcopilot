"""The report sheet raised in a person's app by hand, to try it out. The page
hears the coach only during a turn and puts the sheet up once the reply is
done, so the offer rides the person's next turn."""

import time

import click
from flask import current_app
from sqlalchemy import select

from btcopilot import turnlog, turns
from btcopilot.admin.guard import writes
from btcopilot.admin.users import find
from btcopilot.config import Config
from btcopilot.extensions import db
from btcopilot.models import Discussion, ReportKind, User
from btcopilot.turnlog import TurnEventKind

POLL_S = 0.25


def running(user: User) -> tuple[str, int] | None:
    """The turn the coach is running for this person, and its sitting."""
    sittings = db.session.scalars(select(Discussion.id).where(Discussion.user_id == user.id))
    return next(((turn, one) for one in sittings if (turn := turnlog.running(one))), None)


@click.group("report")
def report_group():
    """The report sheet in a person's app, raised by hand in development."""


@writes
@report_group.command("offer")
@click.argument("email")
@click.argument("words")
@click.option(
    "--kind",
    type=click.Choice([kind.value for kind in ReportKind]),
    default=ReportKind.Feedback.value,
    show_default=True,
    help="Which sheet: feedback, or a bug report.",
)
@click.option(
    "--wait",
    type=int,
    default=600,
    show_default=True,
    help="Seconds to wait for the person's next message.",
)
def report_offer(email, words, kind, wait):
    """Offer to send WORDS from the person's app, as the coach's report tool
    does: the offer goes on their next coach turn, or the one running now, and
    the sheet comes up once that reply is done, at most once a sitting on a
    device. Never on production."""
    if current_app.config["CONFIG"] == Config.Production:
        raise click.UsageError("the report sheet is raised by hand in development only")
    user = find(email)
    click.echo(f"waiting up to {wait}s for {user.username} to send a message")
    until = time.monotonic() + wait
    while (turn := running(user)) is None:
        if time.monotonic() > until:
            raise click.ClickException(f"{user.username} sent no message in {wait}s")
        time.sleep(POLL_S)
    turn_id, sitting = turn
    event = {
        "type": TurnEventKind.Report.value,
        "report": {"kind": kind, "words": words},
    }
    turns.written(turn_id, sitting, event)
    told = [one for _, one in turnlog.read_from(turn_id, 0)]
    if any(turnlog.ended(one) for one in told[: told.index(event)]):
        raise click.ClickException("that reply was done before the offer reached it")
    click.echo(f"offered {kind} on turn {turn_id} in sitting {sitting}: {words}")
