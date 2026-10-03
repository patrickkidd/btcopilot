"""The one pass that gives every noted event and shift already in a record its
title (R-0681): words that already serve as one are kept as they stand, and the
rest come from a file of titles someone wrote and Patrick read."""

import enum
import json

import click

from btcopilot import diagramjson, record
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.models import Diagram
from btcopilot.schema import TITLE_WORDS, EventKind, enum_val, plain_title

WORDED = (EventKind.Noted.value, EventKind.Shift.value)


class Source(enum.StrEnum):
    File = "file"
    Description = "description"
    Nobody = "still untitled"


def untitled(data: dict) -> list[dict]:
    return [
        e
        for e in data.get("events") or []
        if enum_val(e.get("kind")) in WORDED and not (e.get("title") or "").strip()
    ]


def proposed(data: dict, event: dict) -> str | None:
    title = plain_title(event.get("description"))
    if title and record.linked_name(data, event, title) is None:
        return title
    return None


def written(path: str) -> dict[tuple[int, int], str]:
    out = {}
    for row in json.loads(open(path).read()):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        if not TITLE_WORDS[0] <= len(title.split()) <= TITLE_WORDS[1]:
            raise click.ClickException(
                f"record {row['diagram']} event {row['event']}: {title!r} is not "
                f"{TITLE_WORDS[0]} to {TITLE_WORDS[1]} words"
            )
        out[(int(row["diagram"]), int(row["event"]))] = title
    return out


@click.command("fill")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--file",
    "path",
    type=click.Path(exists=True, dir_okay=False),
    help="Titles read and approved: a JSON list of {diagram, event, title}, the "
    "shape --json prints.",
)
@click.option("--yes", is_flag=True, help="Write the titles; without it, only the preview.")
@rows_option
def fill(diagram_id, path, yes):
    """Give each noted event and shift with no title one: from --file when it
    has one, else its description when that is already 2 to 4 words ending on a
    whole phrase and naming no one the event links, which also covers events
    written after the file was made. Prints every event it found without a
    title, the title it gets and where that came from. With --yes it writes
    every title, and refuses, writing nothing, while any event would be left
    "still untitled": a record holding one does not load."""
    titles = written(path) if path else {}
    diagrams = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    rows, filled = [], []
    for diagram in diagrams:
        data = diagramjson.loads(diagram.data)
        found = untitled(data)
        for event in found:
            title = titles.get((diagram.id, event["id"]))
            source = Source.File if title else None
            if not title:
                title = proposed(data, event)
                source = Source.Description if title else Source.Nobody
            rows.append(
                {
                    "diagram": diagram.id,
                    "event": event["id"],
                    "kind": enum_val(event.get("kind")),
                    "description": event.get("description") or "",
                    "title": title or "",
                    "from": source.value,
                }
            )
            event["title"] = title
        if found:
            filled.append((diagram, data))
    left = [r for r in rows if not r["title"]]
    if yes and left:
        raise click.ClickException(
            f"{len(left)} events would be left untitled and their records would not "
            "load; nothing written. Add their titles to --file: "
            + ", ".join(f"record {r['diagram']} event {r['event']}" for r in left)
        )
    if yes:
        for diagram, data in filled:
            diagram.data = diagramjson.encode(data, diagram.data)
            diagram.version += 1
        db.session.commit()
    return rows


@click.group("titles")
def titles_group():
    """The short titles of noted events and shifts."""


titles_group.add_command(writes(fill))
