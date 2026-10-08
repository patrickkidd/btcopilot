"""The conversational-flow numbers per model and prompt version (R-0669),
written as counts to files outside every repository, never as text."""

import datetime
import itertools
import json
import pathlib
import re
import subprocess

import click

from btcopilot import flow
from btcopilot.diagramjson import TAG
from btcopilot.admin.guard import writes
from btcopilot.admin.quality import _allowed
from btcopilot.extensions import db
from btcopilot.models import (
    Change,
    Diagram,
    Discussion,
    DiscussionKind,
    ModelCall,
    Purpose,
    Speaker,
    SpeakerType,
    Statement,
    StatementKind,
    User,
)
from btcopilot.schema import ItemKind, QuestionKind
from btcopilot.tuning import TEST_ACCOUNTS

OUT = pathlib.Path("~/.claude/research/FD-conversation-flow/tracked").expanduser()
UNKNOWN = "unknown"
THREAD_KEY = ("thread", "model", "prompt_version", "rules_version")
ACCOUNT_KEY = ("account", "rules_version")
YEAR = re.compile(r"^(\d{4})")


def _at(value) -> datetime.datetime:
    return (
        value
        if isinstance(value, datetime.datetime)
        else datetime.datetime.fromisoformat(value)
    )


def _plain(value):
    """A tagged value of the diagram's JSON (a QDateTime) as the text it holds."""
    return value["v"] if isinstance(value, dict) and TAG in value else value


def exported(folder: pathlib.Path) -> tuple[list[dict], list[dict]]:
    return (
        json.loads((folder / "stmts.json").read_text()),
        json.loads((folder / "changes.json").read_text()),
    )


def stored() -> tuple[list[dict], list[dict]]:
    """The statements and changes in the export's shape, with the model and
    prompt version of each coach turn and the account's time zone, which picks
    the crisis line. Chat sessions only: a recording, a note or a synthetic
    thread is not a person talking with the coach."""
    models = dict(
        db.session.query(ModelCall.turn_id, ModelCall.model)
        .filter(ModelCall.purpose == Purpose.Coach)
        .order_by(ModelCall.id)
    )
    found = (
        db.session.query(
            Statement,
            Discussion,
            Speaker.type,
            User.username,
            User.timezone,
            Diagram.scratch,
        )
        .join(Discussion, Statement.discussion_id == Discussion.id)
        .join(Speaker, Statement.speaker_id == Speaker.id)
        .join(Diagram, Discussion.diagram_id == Diagram.id)
        .join(User, Discussion.user_id == User.id)
        .filter(Discussion.kind == DiscussionKind.Chat, Discussion.synthetic.is_(False))
    )
    stmts = [
        {
            "id": s.id,
            "did": d.id,
            "uid": d.user_id,
            "diagram_id": d.diagram_id,
            "created_at": s.created_at,
            "spk": spk.name,
            "text": s.text,
            "turn_id": s.turn_id,
            "kind": s.kind,
            "ord": s.order,
            "model": models.get(s.turn_id),
            "prompt_version": s.prompt_version,
            "username": username,
            "zone": zone,
            "scratch": scratch,
        }
        for s, d, spk, username, zone, scratch in found
    ]
    changes = [
        {
            "diagram_id": c.diagram_id,
            "turn_id": c.turn_id,
            "created_at": c.created_at,
            "deltas": c.deltas,
        }
        for c in Change.query.filter(
            Change.diagram_id.in_({s["diagram_id"] for s in stmts})
        )
    ]
    return stmts, changes


def kept(s: dict) -> bool:
    return (
        bool(s["text"])
        and s["kind"] != StatementKind.Play
        and not s.get("scratch")
        and not (s.get("username") or "").startswith(TEST_ACCOUNTS.rstrip("%"))
    )


def message(s: dict) -> flow.Message:
    return flow.Message(
        (
            flow.Role.Person
            if SpeakerType[s["spk"]] is SpeakerType.Subject
            else flow.Role.Coach
        ),
        s["text"],
        _at(s["created_at"]),
        s["turn_id"],
        s.get("model") or UNKNOWN,
        s.get("prompt_version") or UNKNOWN,
    )


def record(changes: list[dict]) -> flow.Record:
    """The names, places and years with the time each was stored, every edit,
    the turns a todo was stored from, and each event's words in order of time."""
    facts, edits, todos, events = {}, [], set(), {}
    for change in sorted(changes, key=lambda c: _at(c["created_at"])):
        at = _at(change["created_at"])
        for delta in change["deltas"]:
            kind, field, after = delta["item_kind"], delta["field"], delta["after"]
            edits.append(
                flow.Edit(change["turn_id"], kind, field, delta["before"], after)
            )
            values = (
                after if field is None and isinstance(after, dict) else {field: after}
            )
            values = {k: _plain(v) for k, v in values.items()}
            if kind == ItemKind.Question and values.get("kind") == QuestionKind.Todo:
                todos.add(change["turn_id"])
            if kind == ItemKind.Event:
                events.setdefault(delta["item_id"], {}).update(values)
            for name, fact in (
                ("name", flow.FactKind.Name),
                ("location", flow.FactKind.Place),
                ("dateTime", flow.FactKind.Year),
            ):
                value = values.get(name)
                if kind not in (ItemKind.Person, ItemKind.Event) or not isinstance(
                    value, str
                ):
                    continue
                if fact is flow.FactKind.Year:
                    year = YEAR.match(value)
                    if year is None:
                        continue
                    value = year.group(1)
                facts.setdefault((fact, value), flow.Fact(fact, value, at))
    named = [
        (
            e.get("dateTime") or "~",
            tuple(w for w in flow.words(e.get("description") or "") if flow.content(w))
            + ((e["location"],) if e.get("location") else ()),
        )
        for e in events.values()
    ]
    return flow.Record(
        tuple(facts.values()),
        tuple(edits),
        frozenset(todos),
        tuple(words for _, words in sorted(named) if words),
    )


def tracked(stmts: list[dict], changes: list[dict], now: datetime.datetime):
    """One row per thread, model and prompt version, and one per account;
    counts only."""
    stmts = sorted(filter(kept, stmts), key=lambda s: (_at(s["created_at"]), s["id"]))
    threads, accounts = [], []
    by = sorted(stmts, key=lambda s: s["diagram_id"])
    for thread, said in itertools.groupby(by, key=lambda s: s["diagram_id"]):
        said = list(said)
        held = record([c for c in changes if c["diagram_id"] == thread])
        counted = flow.rows(list(map(message, said)), held, said[0].get("zone"))
        for (model, prompt), row in counted.items():
            threads.append(
                {
                    "thread": thread,
                    "account": said[0]["uid"],
                    "model": model,
                    "prompt_version": prompt,
                }
                | row
            )
    for account, said in itertools.groupby(
        sorted(stmts, key=lambda s: s["uid"]), key=lambda s: s["uid"]
    ):
        messages = list(map(message, said))
        if any(m.role is flow.Role.Person for m in messages):
            accounts.append({"account": account} | flow.account_row(messages, now))
    return threads, accounts


def inside_git(folder: pathlib.Path) -> bool:
    there = next(p for p in (folder, *folder.parents) if p.exists())
    done = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=there,
        capture_output=True,
        text=True,
    )
    return done.returncode == 0 and done.stdout.strip() == "true"


def merged(
    path: pathlib.Path, rows: list[dict], key: tuple, again: bool
) -> tuple[int, int]:
    """Rows under a key already in the file are kept unless again; returns
    how many were written and kept."""
    old = (
        [json.loads(line) for line in path.read_text().splitlines() if line]
        if path.exists()
        else []
    )
    out = {tuple(r[k] for k in key): r for r in old}
    written = 0
    for row in rows:
        k = tuple(row[n] for n in key)
        if k in out and not again:
            continue
        out[k] = row
        written += 1
    path.write_text("".join(json.dumps(r) + "\n" for r in out.values()))
    return written, len(rows) - written


@click.group("flow")
def flow_group():
    """The conversational-flow numbers per model and prompt version."""


@writes
@flow_group.command("track")
@click.option(
    "--export",
    "folder",
    type=click.Path(exists=True, file_okay=False, path_type=pathlib.Path),
    help="A folder holding stmts.json and changes.json.",
)
@click.option("--database", is_flag=True, help="Read the configured database.")
@click.option(
    "--out",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default=OUT,
    show_default=True,
    help="Where threads.jsonl and accounts.jsonl go; never inside a git work tree.",
)
@click.option("--again", is_flag=True, help="Recompute keys already written.")
@click.option(
    "--production",
    is_flag=True,
    help="Read the production database: Patrick agreed.",
)
def flow_track(folder, database, out, again, production):
    """Count the flow rules over every real thread, leaving out claude-test
    accounts, scratch records and plays, and add the counts per thread, model,
    prompt version and rules version to threads.jsonl and the return of each
    account to accounts.jsonl. No text is written."""
    _allowed(production)
    if (folder is None) == (not database):
        raise click.UsageError("give one of --export DIR or --database")
    out = out.expanduser().resolve()
    if inside_git(out):
        raise click.UsageError(f"{out} is inside a git work tree")
    stmts, changes = exported(folder) if folder else stored()
    threads, accounts = tracked(stmts, changes, datetime.datetime.utcnow())
    out.mkdir(parents=True, exist_ok=True)
    for name, rows, key in (
        ("threads", threads, THREAD_KEY),
        ("accounts", accounts, ACCOUNT_KEY),
    ):
        written, skipped = merged(out / f"{name}.jsonl", rows, key, again)
        click.echo(f"{name}: {written} written, {skipped} already there")
