"""The coding meeting from the command line: what is on the agenda, what has
been coded, a coder's draft cleared to start over, and the switch that stops the app nudging anybody."""

import logging

import click

from btcopilot.admin import setting
from btcopilot.admin.guard import writes
from btcopilot.admin.output import emit, rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.admin.users import find as find_user
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.review import adapter
from btcopilot.review.models import Coding, Cut, Note, Rule
from btcopilot.review.routes.coders import roster, state_of
from btcopilot.review.routes.cuts import agenda_cuts, payload as cut_payload

log = logging.getLogger(__name__)


def cut_row(cut: Cut) -> dict:
    data = cut_payload(cut)
    return {
        "id": cut.id,
        "session": data["session"],
        "meeting_date": data["meeting_date"],
        "cut_day": data["cut_day"],
        "started": data["started"],
        "vote_open": cut.vote_opened_at is not None,
        "ratified_at": cut.ratified_at,
    }


@click.group()
def review():
    """The coding meeting."""


@review.command("agenda")
@click.option("--meeting-date", help="The meeting's day, as 2026-09-18.")
@rows_option
def review_agenda(meeting_date):
    """What the next meeting has in front of it: the cuts, and the rules
    somebody flagged."""
    cuts = agenda_cuts(meeting_date)
    rows = [dict(cut_row(cut), kind="cut") for cut in cuts]
    for rule in Rule.query.filter(Rule.retired_at.is_(None)).all():
        if rule.open_flags():
            rows.append({"kind": "flagged rule", "id": rule.id, "session": rule.text})
    columns = ["kind", "id", "session", "meeting_date", "started", "vote_open"]
    return columns, rows


@review.command("cuts")
@click.option("--meeting-date", help="Only this meeting's cuts.")
@click.option("--all", "every", is_flag=True, help="Ratified cuts as well.")
@rows_option
def review_cuts(meeting_date, every):
    """The windows of a conversation the room codes."""
    if every:
        cuts = Cut.query.order_by(Cut.id).all()
    else:
        cuts = agenda_cuts(meeting_date)
    return [cut_row(cut) for cut in cuts]


@review.group("codings", invoke_without_command=True)
@click.option("--meeting-date", help="Only this meeting's codings.")
@click.option("--cut", "cut_id", type=int, help="Only this cut's codings.")
@click.option("--json", "as_json", is_flag=True, help="Print JSON, not a table.")
@click.pass_context
def review_codings(context, cut_id, meeting_date, as_json):
    """How far each coder has got on what is on the agenda."""
    if context.invoked_subcommand is not None:
        return
    cuts = [db.session.get(Cut, cut_id)] if cut_id else agenda_cuts(meeting_date)
    if cut_id and cuts[0] is None:
        raise click.ClickException(f"no cut with id {cut_id}")
    rows = []
    for user in roster(cuts):
        done = sum(
            1
            for cut in cuts
            if _coding_done(cut.id, user.id)
        )
        rows.append(
            {
                "coder": user.username,
                "state": state_of(user, cuts).value,
                "cuts_done": f"{done} of {len(cuts)}",
            }
        )
    emit(rows, None, as_json)


@writes
@review_codings.command("reset")
@click.argument("email")
@click.argument("cut_id", type=int)
@click.option(
    "--yes", is_flag=True, help="Reset it; without it, only the preview."
)
@rows_option
def review_codings_reset(email, cut_id, yes):
    """Clear one coder's draft coding of one cut so they can start over: their
    coding copy of the diagram is hidden, their notes to the scribe and the
    coding row are deleted, and the reset is logged. A submitted coding, or a
    coding copy the coder also uses on another cut, is refused before anything
    is written. Without --yes it prints what would change and writes nothing."""
    user = find_user(email)
    coding = Coding.query.filter_by(cut_id=cut_id, user_id=user.id).first()
    if coding is None:
        raise click.ClickException(f"{user.username} has no coding of cut {cut_id}")
    if coding.done_at is not None:
        raise click.ClickException("this coding was submitted; not reset")
    shared = Coding.query.filter(
        Coding.user_id == user.id,
        Coding.diagram_id == coding.diagram_id,
        Coding.id != coding.id,
    ).first()
    if shared is not None:
        raise click.ClickException(
            f"this coder's coding copy is also their coding of cut {shared.cut_id}; not reset"
        )
    diagram = db.session.get(Diagram, coding.diagram_id)
    notes = Note.query.filter_by(coding_id=coding.id)
    count = notes.count()
    rows = [
        {"change": "diagram hidden", "value": diagram.id, "done": yes},
        {"change": "notes deleted", "value": count, "done": yes},
        {"change": "coding deleted", "value": coding.id, "done": yes},
    ]
    if yes:
        diagram.deleted_at = adapter.utcnow()
        notes.delete()
        db.session.delete(coding)
        db.session.commit()
        log.info(
            "admin reset the coding of %s on cut %s: diagram %s hidden, %s notes deleted",
            user.username,
            cut_id,
            diagram.id,
            count,
        )
    return rows


def _coding_done(cut_id: int, user_id: int) -> bool:
    coding = Coding.query.filter_by(cut_id=cut_id, user_id=user_id).first()
    return coding is not None and coding.done_at is not None


@review.group("nudge")
def nudge():
    """Whether the app may nudge the coders who are not done."""


@writes
@nudge.command("on")
@rows_option
def nudge_on():
    """Let the app nudge coders again."""
    setting.write(SettingKey.NudgesOn, True)
    return [{"nudges": "on"}]


@writes
@nudge.command("off")
@rows_option
def nudge_off():
    """Stop the app nudging anybody."""
    setting.write(SettingKey.NudgesOn, False)
    return [{"nudges": "off"}]


@nudge.command("show")
@rows_option
def nudge_show():
    """Whether nudging is on, and when the agenda was last nudged."""
    last = [cut.nudged_at for cut in agenda_cuts(None) if cut.nudged_at]
    return [
        {
            "nudges": "on" if setting.nudges_on() else "off",
            "last_nudged_at": max(last) if last else None,
        }
    ]
