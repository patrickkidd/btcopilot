"""The family records themselves: who owns them, how much is in them, and the
whole record written out as JSON."""

import json

import click

from btcopilot import diagramjson
from btcopilot.admin.users import find as find_user
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.models import Diagram


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
