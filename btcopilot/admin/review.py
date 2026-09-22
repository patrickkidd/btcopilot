"""The coding meeting from the command line: what is on the agenda, what has
been coded, and the switch that stops the app nudging anybody."""

import click

from btcopilot.admin import setting
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.admin.setting import SettingKey
from btcopilot.review.models import Coding, Cut, Rule
from btcopilot.review.routes.coders import roster, state_of
from btcopilot.review.routes.cuts import agenda_cuts, payload as cut_payload
from btcopilot.admin.guard import writes



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


@review.command("codings")
@click.option("--meeting-date", help="Only this meeting's codings.")
@click.option("--cut", "cut_id", type=int, help="Only this cut's codings.")
@rows_option
def review_codings(cut_id, meeting_date):
    """How far each coder has got on what is on the agenda."""
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
