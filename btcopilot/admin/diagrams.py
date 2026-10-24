"""The family records themselves: who owns them, how much is in them, the
whole diagram written out as JSON, change rows taken back, who else is on a
case, and the records still stored as a pickle rewritten as JSON."""

import hashlib
import json
import pathlib
import uuid

import click
from sqlalchemy import update as sql_update

import btcopilot
from btcopilot import diagramjson, fdafter, fdfile, fdimport, fdledger, record
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
        "clusters": len(data.drawn_clusters()),
        "format": "json" if diagramjson.is_json(diagram.data) else "pickle",
        "updated_at": diagram.updated_at,
        "hidden": diagram.deleted_at is not None,
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
@click.option(
    "--yes", is_flag=True, help="Take them back; without it, only the preview."
)
@rows_option
def diagram_undo(diagram_id, change_ids, yes):
    """Take these change rows of one record back off it, newest first, each
    logged as its own undo naming the row; the questions and impressions they
    added come off too. A value changed since stops it before anything is
    written. Without --yes it prints what each row would take back and writes
    nothing."""
    diagram = find(diagram_id)
    changes = Change.query.filter(
        Change.diagram_id == diagram.id, Change.id.in_(change_ids)
    ).all()
    if len(changes) != len(set(change_ids)):
        raise click.ClickException(
            f"not every change of {change_ids} is on diagram {diagram.id}"
        )
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
            "taken_back": ", ".join(
                f"{d['item_kind']} {d['item_id']} {said(d)}" for d in deltas
            ),
        }
        for change, deltas in taken
    ]


def said(delta: dict) -> str:
    if delta["field"] is not None:
        return f"{delta['field']} back to {delta['after']}"
    return "taken off" if delta["after"] is None else "put back"


diagrams.add_command(writes(click.command("undo")(diagram_undo)))


def on_case(diagram: Diagram, user) -> dict:
    row = diagram.access_right(user)
    return {
        "diagram": diagram.id,
        "email": user.username,
        "right": row.right if row else "",
        "person": row.person_id if row and row.person_id is not None else "",
    }


@writes
@diagrams.command("add-user")
@click.argument("diagram_id", type=int)
@click.argument("email")
@click.option(
    "--person",
    type=int,
    help="The id of the person in the diagram this user is; left out, they are "
    "no one in the family, such as a human coach consulting on the case.",
)
@rows_option
def diagram_add_user(diagram_id, email, person):
    """Put somebody on a case, read-write, as the person given or as no one in
    the family. Somebody already on it gets this person instead."""
    diagram = find(diagram_id)
    user = find_user(email)
    if person is not None and not any(
        p.get("id") == person for p in diagram.get_diagram_data().people
    ):
        raise click.ClickException(f"no person {person} in diagram {diagram.id}")
    diagram.grant_access(user, btcopilot.ACCESS_READ_WRITE, person_id=person)
    db.session.commit()
    return [on_case(diagram, user)]


@writes
@diagrams.command("remove-user")
@click.argument("diagram_id", type=int)
@click.argument("email")
@rows_option
def diagram_remove_user(diagram_id, email):
    """Take somebody off a case. The owner stays on their own."""
    diagram = find(diagram_id)
    user = find_user(email)
    if user.id == diagram.user_id:
        raise click.ClickException(f"{email} owns diagram {diagram.id}")
    diagram.revoke_access(user)
    db.session.commit()
    return [on_case(diagram, user)]


MISSING = object()


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def converted(diagram: Diagram, plans: pathlib.Path) -> dict:
    """One pickled diagram's dry run: the pickle and the JSON it becomes both
    decoded and compared field by field; when equal, the plan and the pickle
    saved for apply and undo."""
    pickled = diagramjson.loads(diagram.data)
    text = diagramjson.dumps(pickled)
    loaded = diagramjson.loads(text)
    fields = sorted(set(pickled) | set(loaded))
    differ = [f for f in fields if pickled.get(f, MISSING) != loaded.get(f, MISSING)]
    row = {
        "diagram": diagram.id,
        "kind": "pickle",
        "fields": len(fields),
        "equal": "no" if differ else "yes",
        "differ": ", ".join(differ),
        "plan": None,
    }
    if differ:
        return row
    plans.mkdir(parents=True, exist_ok=True)
    (plans / f"to-json-{diagram.id}.pickle").write_bytes(diagram.data)
    path = plans / f"to-json-{diagram.id}.json"
    path.write_text(
        json.dumps(
            {
                "diagram": diagram.id,
                "version": diagram.version,
                "pickle": _sha(diagram.data),
                "json": text.decode("utf-8"),
            }
        )
    )
    return {**row, "plan": str(path)}


def rewritten(path: pathlib.Path, undo: bool) -> dict:
    """A saved plan written, or with undo its saved pickle put back, only when
    the row still holds what the plan started from."""
    plan = json.loads(path.read_text())
    diagram = find(plan["diagram"])
    text = plan["json"].encode("utf-8")
    pickled = path.with_suffix(".pickle").read_bytes()
    held, after = (_sha(text), pickled) if undo else (plan["pickle"], text)
    if _sha(diagram.data) != held:
        raise click.ClickException(
            f"diagram {diagram.id} changed since the dry run: run it again"
        )
    db.session.execute(
        sql_update(Diagram)
        .where(Diagram.id == diagram.id)
        .values(data=after, version=Diagram.version + 1)
    )
    db.session.commit()
    return {"diagram": diagram.id, "kind": "pickle" if undo else "json", "plan": str(path)}


@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="Write saved plans; the default, --dry-run, compares and saves the "
    "plans, writing nothing to the records.",
)
@click.option("--undo", is_flag=True, help="With --plan: put the saved pickle back.")
@click.option(
    "--plan",
    "plan_paths",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    multiple=True,
    help="With --apply or --undo: a plan file the dry run printed.",
)
@click.option(
    "--plans",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default="to-json-plans",
    show_default=True,
    help="Where the dry run saves its plans and the pickles.",
)
@rows_option
def diagram_to_json(diagram_id, apply, undo, plan_paths, plans):
    """Rewrite every record still stored as a pickle as the JSON the app
    writes [Oracle: R-0913]. The dry run decodes each pickle and the JSON it
    becomes, compares them field by field, prints each record's id, blob kind
    and whether the two are equal, and saves a plan and the pickle for each
    equal one; it writes nothing. --apply --plan writes exactly that plan;
    --undo --plan puts the saved pickle back. Each refuses a record changed
    since the dry run. Back up the database before --apply."""
    if apply or undo:
        if not plan_paths:
            raise click.ClickException("--apply and --undo write a saved plan: give --plan, from a dry run")
        return [rewritten(path, undo) for path in plan_paths]
    found = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    return [
        converted(diagram, plans)
        for diagram in found
        if diagram.data and not diagramjson.is_json(diagram.data)
    ]


diagrams.add_command(writes(click.command("to-json")(diagram_to_json)))


@click.argument("path", type=click.Path(exists=True, path_type=pathlib.Path))
@click.option("--email", required=True, help="Whose record it is.")
@click.option("--name", help="The record's name; the file's name when left out.")
@click.option(
    "--ledger",
    type=click.Path(dir_okay=False, writable=True, path_type=pathlib.Path),
    help="Where a dry run writes the import record; the record's name in this folder when left out.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Write it and mail the import record; without it, only the check.",
)
@rows_option
def diagram_import(path, email, name, ledger, yes):
    """Make a new record for one person from a Family Diagram desktop file
    (.fd) as it stands, with no model call, written as one change so one undo
    takes it all back, and mail them the import record: every field of the
    file and every choice made. Without --yes the import record is written to
    a file and the counts printed; nothing is kept or mailed."""
    user = find_user(email)
    name = name or path.stem
    turn = fdimport.TURN.format(uuid.uuid4().hex)
    try:
        fd = fdfile.read(path)
        imported = fdimport.build(fd)
        made = fdimport.save(user.id, name, imported, yes=yes, turn=turn)
    except (ValueError, record.Invalid) as e:
        db.session.rollback()
        raise click.ClickException(str(e))
    if made:
        fdafter.land(made, user, path.name, fd, imported)
    else:
        ledger = ledger or pathlib.Path(fdledger.attachment(name))
        ledger.write_text(fdafter.ledger(path.name, fd, imported))
    rows = [
        {
            "what": "diagram",
            "count": made.id if made else None,
            "detail": "written and mailed" if made else "dry run",
        },
        *(
            {"what": what, "count": count, "detail": ""}
            for what, count in imported.summary().items()
        ),
        {"what": "turn", "count": None, "detail": turn},
        *(
            {"what": "dropped", "count": count, "detail": what}
            for what, count in sorted(imported.dropped.items())
        ),
    ]
    if not made:
        rows.append({"what": "import record", "count": None, "detail": str(ledger)})
    return ["what", "count", "detail"], rows


diagrams.add_command(writes(click.command("import")(diagram_import)))
