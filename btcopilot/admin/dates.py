"""Putting back as text the event dates a hand edit on the page stored as Qt
date objects before FD-371, so the record reads the way every other write
leaves it [Oracle: R-0084]."""

import datetime

import click

from btcopilot import record
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.models import Author, Diagram
from btcopilot.schema import ItemKind, parse_date


def qt_dates(diagram: Diagram) -> list[dict]:
    return [
        {
            "event": event["id"],
            "field": field,
            "before": event[field].toString("yyyy-MM-ddTHH:mm:ss"),
            "after": parse_date(event[field]).isoformat(),
        }
        for event in diagram.get_diagram_data().events
        for field in record.DATES
        if event.get(field) and not isinstance(event[field], str)
    ]


@click.command("dates")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="Write the text dates; the default, --dry-run, lists them and writes nothing.",
)
@rows_option
def dates(diagram_id, apply):
    """List each event date stored as a Qt date object rather than text, with
    the text it becomes, and why the date rule would refuse the write when it
    would; nothing else in the event is checked or changed. --apply writes each record's dates the rule takes as one change
    row that `diagrams undo` takes back."""
    columns = ["diagram", "event", "field", "before", "after", "refused", "change"]
    found = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S")
    turn = record.DATE_REPAIR + "{}:" + stamp
    rows = []
    for diagram in found:
        fixes = qt_dates(diagram)
        if not fixes:
            continue
        deltas = [
            {
                "item_kind": ItemKind.Event.value,
                "item_id": f["event"],
                "field": f["field"],
                "after": f["after"],
            }
            for f in fixes
        ]
        refused = change = None
        try:
            record.preview(
                diagram.id, deltas, author=Author.Coach, turn_id=turn.format(diagram.id)
            )
        except record.Invalid as e:
            refused = str(e)
        if apply and refused is None:
            change = record.apply(
                diagram.id,
                deltas,
                author=Author.Coach,
                turn_id=turn.format(diagram.id),
                user_id=diagram.user_id,
            ).id
            db.session.commit()
        rows.extend(
            {"diagram": diagram.id, **f, "refused": refused, "change": change}
            for f in fixes
        )
    return columns, rows


dates = writes(dates)
