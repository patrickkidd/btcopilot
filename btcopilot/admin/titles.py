"""The one pass that gives every noted event and shift already in a record its
title (R-0681): words that already serve as one are kept as they stand, an
empty shift is named by what moved, Patrick's own record takes a file of titles
he read, and other people's records take the app's own model call."""

import enum
import json

import click

from btcopilot import diagramjson, prompts, record
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.extensions import db
from btcopilot.llmutil import EXTRACTION_MODEL
from btcopilot.metered import Metered
from btcopilot.models import Diagram
from btcopilot.models.modelcall import Purpose
from btcopilot.schema import (
    LOOSE_ENDS,
    TITLE_WORDS,
    EventKind,
    RelationshipKind,
    enum_val,
    plain_title,
)
from btcopilot.timeline import VARIABLES, _shift_words

WORDED = (EventKind.Noted.value, EventKind.Shift.value)


class Source(enum.StrEnum):
    File = "file"
    Description = "description"
    Moved = "what moved"
    Model = "the app's model"
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


def moved(event: dict) -> str | None:
    """An empty shift, with no words and no notes, named by what it stores."""
    if (event.get("description") or "").strip() or (event.get("notes") or "").strip():
        return None
    for variable, _ in VARIABLES:
        direction = enum_val(event.get(variable))
        if direction:
            words = _shift_words(variable, direction)
            return words[0].upper() + words[1:]
    relationship = enum_val(event.get("relationship"))
    if relationship:
        return f"{RelationshipKind(relationship).menuLabel()} move"
    return None


def checked(title: str, where: str) -> str:
    words = title.split()
    if not TITLE_WORDS[0] <= len(words) <= TITLE_WORDS[1] or words[-1].lower() in LOOSE_ENDS:
        raise click.ClickException(
            f"{where}: {title!r} is not a whole phrase of {TITLE_WORDS[0]} to "
            f"{TITLE_WORDS[1]} words"
        )
    return title


def written(path: str) -> dict[tuple[int, int], str]:
    out = {}
    for row in json.loads(open(path).read()):
        title = (row.get("title") or "").strip()
        if title:
            where = f"record {row['diagram']} event {row['event']}"
            out[(int(row["diagram"]), int(row["event"]))] = checked(title, where)
    return out


def asked(meter: Metered, event: dict, where: str) -> str:
    said = meter.gemini(
        prompt=prompts.event_title(
            kind=enum_val(event.get("kind")),
            description=event.get("description") or "",
            notes=event.get("notes") or "",
        ),
        model=EXTRACTION_MODEL,
        thinking_budget=0,
    )
    return checked(said.strip().strip('"').rstrip("."), where)


@click.command("fill")
@click.option(
    "--diagram", "diagram_ids", type=int, multiple=True, help="Only these records."
)
@click.option(
    "--file",
    "path",
    type=click.Path(exists=True, dir_okay=False),
    help="Titles read and approved: a JSON list of {diagram, event, title}, the "
    "shape --json prints.",
)
@click.option(
    "--ask",
    is_flag=True,
    help="Have the app's own model write the titles nothing else gives, one short "
    "call per event, each written to the model-calls ledger.",
)
@click.option("--yes", is_flag=True, help="Write the titles; without it, only the preview.")
@rows_option
def fill(diagram_ids, path, ask, yes):
    """Give each noted event and shift with no title one: from --file when it
    has one; else its description when that is already 2 to 4 words ending on a
    whole phrase and naming no one the event links, which also covers events
    written after the file was made; else, for a shift with no words and no
    notes, what moved; else, with --ask, the app's own model. Prints every
    event it found without a title, the title it gets and where that came
    from; the model is asked only with --yes. With --yes it refuses, before any
    model call and writing nothing, while an event would be left "still
    untitled": a record holding one does not load."""
    titles = written(path) if path else {}
    diagrams = (
        [find(i) for i in diagram_ids]
        if diagram_ids
        else Diagram.query.order_by(Diagram.id).all()
    )
    rows, found, records = [], [], []
    for diagram in diagrams:
        data = diagramjson.loads(diagram.data)
        if untitled(data):
            records.append((diagram, data))
        for event in untitled(data):
            title = titles.get((diagram.id, event["id"]))
            source = Source.File
            if not title:
                title, source = proposed(data, event), Source.Description
            if not title:
                title, source = moved(event), Source.Moved
            if not title:
                source = Source.Model if ask else Source.Nobody
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
            found.append((diagram, event, rows[-1]))
    left = [r for r in rows if r["from"] == Source.Nobody]
    if yes and left:
        raise click.ClickException(
            f"{len(left)} events would be left untitled and their records would not "
            "load; nothing written. Add their titles to --file, or --ask: "
            + ", ".join(f"record {r['diagram']} event {r['event']}" for r in left)
        )
    if not yes:
        return rows
    for diagram, event, row in found:
        if row["from"] == Source.Model:
            meter = Metered(diagram.user_id, diagram.id, f"titles-{diagram.id}", Purpose.Backfill)
            row["title"] = asked(meter, event, f"record {diagram.id} event {event['id']}")
        event["title"] = row["title"]
    for diagram, data in records:
        diagram.data = diagramjson.encode(data, diagram.data)
        diagram.version += 1
    db.session.commit()
    return rows


@click.group("titles")
def titles_group():
    """The short titles of noted events and shifts."""


titles_group.add_command(writes(fill))
