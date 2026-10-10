"""The family records themselves: who owns them, how much is in them, the
whole record written out as JSON, and change rows taken back."""

import json
import pathlib

import click

from btcopilot import diagramjson, fdfile, fdimport, record
from btcopilot.admin.guard import writes
from btcopilot.admin.users import find as find_user
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram


def find(diagram_id: int) -> Diagram:
    diagram = db.session.get(Diagram, diagram_id)
    if diagram is None:
        raise click.ClickException(f"no diagram with id {diagram_id}")
    return diagram


def counts(diagram: Diagram) -> dict:
    data = diagram.get_diagram_data()
    return {
        "id": diagram.id,
        "name": diagram.name or "",
        "email": diagram.user.username if diagram.user else "",
        "people": len(data.people),
        "events": len(data.events),
        "pair_bonds": len(data.pair_bonds),
        "clusters": len(data.clusters),
        "format": "json" if diagramjson.is_json(diagram.data) else "pickle",
        "updated_at": diagram.updated_at,
    }


@click.group()
def diagrams():
    """The family records."""


@diagrams.command("list")
@click.option("--email", help="Only the records one person owns.")
@rows_option
def diagram_list(email):
    """Every record, with how much is in it."""
    query = Diagram.query.order_by(Diagram.id)
    if email:
        query = query.filter_by(user_id=find_user(email).id)
    return [counts(diagram) for diagram in query.all()]


@diagrams.command("show")
@click.argument("diagram_id", type=int)
@rows_option
def diagram_show(diagram_id):
    """One record's counts."""
    return [counts(find(diagram_id))]


@diagrams.command("export")
@click.argument("diagram_id", type=int)
@click.option(
    "--out",
    type=click.Path(dir_okay=False, writable=True),
    help="Write to this file instead of the screen.",
)
def diagram_export(diagram_id, out):
    """Write one record out as JSON."""
    diagram = find(diagram_id)
    text = json.dumps(diagramjson.to_json(diagramjson.loads(diagram.data)), indent=2)
    if out:
        with open(out, "w") as file:
            file.write(text)
        click.echo(f"wrote {out}")
    else:
        click.echo(text)


@click.argument("diagram_id", type=int)
@click.argument("change_ids", type=int, nargs=-1, required=True)
@click.option("--yes", is_flag=True, help="Take them back; without it, only the preview.")
@rows_option
def diagram_undo(diagram_id, change_ids, yes):
    """Take these change rows of one record back off it, newest first, each
    logged as its own undo naming the row; the questions and impressions they
    added come off too. A value changed since stops it before anything is
    written. Without --yes it prints what each row would take back and writes
    nothing."""
    diagram = find(diagram_id)
    changes = Change.query.filter(Change.diagram_id == diagram.id, Change.id.in_(change_ids)).all()
    if len(changes) != len(set(change_ids)):
        raise click.ClickException(f"not every change of {change_ids} is on diagram {diagram.id}")
    earlier = record.undone(diagram.id)
    try:
        taken = record.taking_back(diagramjson.loads(diagram.data), changes)
        if yes:
            record.undo_changes(diagram.id, list(change_ids), author=Author.Coach)
    except ValueError as e:
        raise click.ClickException(str(e))
    except record.Conflict as e:
        # rows are written one at a time, so a write between them can stop the
        # rest after some were taken back
        done = sorted((record.undone(diagram.id) - earlier) & set(change_ids))
        raise click.ClickException(
            f"changed since it was written: {e}; taken back before it: {done or 'nothing'}"
        )
    return [
        {
            "change": change.id,
            "turn": change.turn_id,
            "undone": yes,
            "taken_back": ", ".join(f"{d['item_kind']} {d['item_id']} {said(d)}" for d in deltas),
        }
        for change, deltas in taken
    ]


def said(delta: dict) -> str:
    if delta["field"] is not None:
        return f"{delta['field']} back to {delta['after']}"
    return "taken off" if delta["after"] is None else "put back"


diagrams.add_command(writes(click.command("undo")(diagram_undo)))


@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option("--email", required=True, help="Whose new record it is.")
@click.option("--name", help="The record's name; the file's name when left out.")
@click.option("--yes", is_flag=True, help="Write it; without it, only the check and the counts.")
@rows_option
def diagram_import(path, email, name, yes):
    """Make a new record for one person from a Family Diagram desktop file
    (.fd), written as one change so one undo takes it all back. Without --yes
    the record's rules are checked and the counts printed; nothing is kept."""
    user = find_user(email)
    try:
        imported = fdimport.convert(fdfile.read(path))
        made = fdimport.save(user.id, name or path.stem, imported, yes=yes)
    except (ValueError, record.Invalid) as e:
        db.session.rollback()
        raise click.ClickException(str(e))
    rows = [
        {"what": "diagram", "count": made.id if made else None, "detail": "written" if made else "dry run"},
        *({"what": what, "count": count, "detail": ""} for what, count in imported.summary().items()),
        *(
            {"what": "left blank", "count": blank["event"], "detail": f"{blank['field']}: {blank['raw']}"}
            for blank in imported.blanks
        ),
        *({"what": "dropped", "count": count, "detail": what} for what, count in sorted(imported.dropped.items())),
    ]
    return ["what", "count", "detail"], rows


diagrams.add_command(writes(click.command("import")(diagram_import)))
