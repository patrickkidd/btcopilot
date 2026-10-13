"""One real coach turn run again, k times, on a family exported from production,
the way a shadow turn runs (btcopilot/shadow.py): the same words, the chat as it
stood, the coach's own notes as they stood, and the record rewound to where the
turn found it, written onto a scratch copy that is thrown away after each run.
The model, the wire and the tool loop are the app's own (CoachTurn, CoachModel);
the prompt is read from FD_PRIVATE_PROMPTS, so a prompt variant is a folder of
prompt copies, never an edit of private/prompts. A variant that changes a tool's
words, which live in code, names a file of replacements with --tools.

  BTCOPILOT_MODEL_PROVIDER=bedrock FD_PRIVATE_PROMPTS=<prompt folder> \\
      uv run python bin/turntrial.py <export folder> <statement id> \\
      --variant <name> --runs 5 --out <folder>

The export folder holds the production rows as JSON: discussions.json,
statements.json, turn_events.json, diagram_changes.json, and the record in
diagram_decoded.json. Everything runs on the unit suite's in-memory SQLite app;
nothing is written but --out, the first call's request under --requests, and one
eval-ledger line per run. What the user had been looking at (the interactions
table) is not in the export, so that block of the prompt is empty.
"""

import argparse
import datetime
import json
import subprocess
import sys
import tempfile
import time
import types
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import DateTime, Enum

from btcopilot import clock, ledger, shadow, turnlog
from btcopilot.coachmodel import CoachModel, model_for
from btcopilot.coachturn import CoachTurn, prompt_version
from btcopilot.extensions import db
from btcopilot.models import (
    Change,
    Diagram,
    Discussion,
    ModelCall,
    Purpose,
    Speaker,
    Statement,
    TurnEvent,
    User,
)
from btcopilot.models.speaker import SpeakerType
from btcopilot.quality import Outcome, Source
from btcopilot.tests.fixtures import STUBS, make_app, stubbed
from btcopilot.toolbox import schemas
from btcopilot.turnlog import TurnEventKind

HERE = Path(__file__).resolve().parent


def _row(model, raw: dict):
    """A model row from an exported one: only the table's own columns, each
    timestamp parsed and each enum taken by its stored value."""
    kept = {}
    for column in model.__table__.columns:
        if column.name not in raw:
            continue
        value = raw[column.name]
        if value is not None and isinstance(column.type, DateTime):
            value = datetime.datetime.fromisoformat(value)
        elif value is not None and isinstance(column.type, Enum) and column.type.enum_class:
            value = column.type.enum_class(value)
        kept[column.name] = value
    return model(**kept)


def _read(folder: Path, name: str):
    return json.loads((folder / name).read_text())


def load(folder: Path) -> None:
    """The family as production held it at the export: its user, the record,
    every session and its two speakers, every statement, turn row and change."""
    discussions = _read(folder, "discussions.json")
    statements = _read(folder, "statements.json")
    user_id = discussions[0]["user_id"]
    diagram_id = discussions[0]["diagram_id"]
    record = _read(folder, "diagram_decoded.json")
    db.session.add(
        User(id=user_id, username=f"export-{user_id}@example.com", status="confirmed")
    )
    db.session.add(
        Diagram(
            id=diagram_id,
            user_id=user_id,
            name="export",
            data=json.dumps(record).encode("utf-8"),
        )
    )
    db.session.flush()
    for raw in discussions:
        db.session.add(_row(Discussion, raw))
    db.session.flush()
    for raw in discussions:
        for key, kind in (
            ("chat_user_speaker_id", SpeakerType.Subject),
            ("chat_ai_speaker_id", SpeakerType.Expert),
        ):
            db.session.add(
                Speaker(id=raw[key], discussion_id=raw["id"], type=kind, name=kind.value)
            )
    db.session.flush()
    for raw in statements:
        db.session.add(_row(Statement, raw))
    for raw in _read(folder, "turn_events.json"):
        db.session.add(_row(TurnEvent, raw))
    for raw in _read(folder, "diagram_changes.json"):
        db.session.add(_row(Change, raw))
    db.session.commit()


def version_before(said: Statement) -> int:
    """The record's version when the turn these words started first read it:
    one below the first change taken back to reach it."""
    taken = shadow.rewound(said)
    if taken and taken[-1].version:
        return taken[-1].version - 1
    return db.session.get(Diagram, said.discussion.diagram_id).version


def reworded(replacements: list[dict]):
    """The coach's tool schemas with each `old` phrase put as `new`; a phrase
    found in no schema fails the run rather than leave the variant unapplied."""

    def swap(value, found: set):
        if isinstance(value, str):
            for i, r in enumerate(replacements):
                if r["old"] in value:
                    found.add(i)
                    value = value.replace(r["old"], r["new"])
            return value
        if isinstance(value, list):
            return [swap(v, found) for v in value]
        if isinstance(value, dict):
            return {k: swap(v, found) for k, v in value.items()}
        return value

    def changed(coder: bool = False) -> list[dict]:
        found = set()
        given = swap(schemas(coder), found)
        missing = [r["old"] for i, r in enumerate(replacements) if i not in found]
        if missing:
            raise KeyError(f"tool words not found: {missing}")
        return given

    return changed


class Recorded(CoachModel):
    """The app's own coach model, keeping the first request of the turn."""

    def __init__(self, model: CoachModel):
        self.model, self.effort, self.timeout = model.model, model.effort, model.timeout
        self.requests = []

    def turn(self, system, messages, tools, turn_id=""):
        self.requests.append({"system": system, "messages": messages, "tools": tools})
        return (yield from super().turn(system, messages, tools, turn_id))


def git() -> str:
    return subprocess.run(
        ["git", "-C", str(HERE), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def run_once(said: Statement, args, index: int) -> dict:
    """One turn on a fresh scratch copy of the record as the turn found it."""
    snapshot = shadow.rebuilt(said)
    version = version_before(said)
    diagram = Diagram(
        user_id=said.discussion.user_id,
        name=f"trial {args.variant} {said.id} {index}",
        data=snapshot,
        scratch=True,
        version=version,
    )
    db.session.add(diagram)
    db.session.flush()
    copy = shadow._copy(said, diagram)
    db.session.commit()
    model = Recorded(model_for(args.model))
    turn_id = f"trial-{args.variant}-{said.id}-{index}"
    started = time.monotonic()
    error = None
    reply = None
    turn = CoachTurn(
        copy,
        said.spoken,
        purpose=Purpose.Replay,
        model=model,
        statement_id=said.id,
        turn_id=turn_id,
        scratch=True,
    )
    try:
        reply = turn.run()["statement"]
    except Exception as failed:
        db.session.rollback()
        error = f"{type(failed).__name__}: {failed}"
    duration = round((time.monotonic() - started) * 1000)
    calls = [
        {
            "purpose": str(call.purpose),
            "model": call.model,
            "input": call.input_tokens,
            "output": call.output_tokens,
            "cache_creation": call.cache_creation_tokens,
            "cache_read": call.cache_read_tokens,
            "tool_calls": call.tool_calls,
            "cost": float(call.cost_usd),
        }
        for call in ModelCall.query.filter_by(turn_id=turn_id).order_by(ModelCall.id)
    ]
    tools = [
        {"name": e["name"], "args": e["args"], "refusal": e.get("refusal")}
        for e in turn.kept
        if e["type"] == TurnEventKind.ToolCall.value
    ]
    aloud = [
        block["text"]
        for e in turn.kept
        if e["type"] == TurnEventKind.Step.value
        for block in e["blocks"]
        if block["type"] == "text" and block["text"].strip()
    ]
    shadow._drop(diagram, copy)
    db.session.commit()
    return {
        "variant": args.variant,
        "statement_id": said.id,
        "run": index,
        "model": calls[0]["model"] if calls else args.model,
        "prompt_version": prompt_version(),
        "git": git(),
        "today": clock.today().isoformat(),
        "record_version": version,
        "reply": reply,
        "error": error,
        "tool_calls": tools,
        "thought_aloud": aloud,
        "calls": calls,
        "first_request_tokens": (
            calls[0]["input"] + calls[0]["cache_creation"] + calls[0]["cache_read"]
            if calls
            else None
        ),
        "cost": sum(c["cost"] for c in calls),
        "duration_ms": duration,
        "request": model.requests[0] if model.requests else None,
    }


def page(result: dict) -> str:
    """One run as a page a person reads."""
    tools = "\n".join(
        f"- `{t['name']}` {json.dumps(t['args'], ensure_ascii=False)}"
        + (f" (refused: {t['refusal']})" if t["refusal"] else "")
        for t in result["tool_calls"]
    )
    calls = "\n".join(
        f"- {c['purpose']} on {c['model']}: {c['input']} in, {c['output']} out, "
        f"{c['cache_creation']} written to the cache, {c['cache_read']} read back, "
        f"{c['tool_calls']} tool calls, ${c['cost']:.4f}"
        for c in result["calls"]
    )
    aloud = "\n\n".join(f"> {t}" for t in result["thought_aloud"]) or "(none)"
    reply = result["reply"] if result["reply"] is not None else f"(failed: {result['error']})"
    return (
        f"# {result['variant']} / statement {result['statement_id']} / run {result['run']}\n\n"
        f"- model: {result['model']}\n"
        f"- prompt version: {result['prompt_version']}\n"
        f"- code: {result['git'][:8]}\n"
        f"- today: {result['today']}; record version {result['record_version']}\n"
        f"- first call's prompt: {result['first_request_tokens']} tokens\n"
        f"- cost: ${result['cost']:.4f} in {len(result['calls'])} calls, "
        f"{result['duration_ms'] / 1000:.1f} s\n\n"
        f"## Reply\n\n{reply}\n\n"
        f"## Tool calls\n\n{tools or '(none)'}\n\n"
        f"## Words written before a tool call (never shown)\n\n{aloud}\n\n"
        f"## Model calls\n\n{calls}\n"
    )


def ledger_line(result: dict) -> dict:
    tokens = {
        key: sum(c[key] for c in result["calls"])
        for key in ("input", "output", "cache_creation", "cache_read")
    }
    return {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "kind": ledger.LedgerKind.Live,
        "git": result["git"],
        "model": result["model"],
        "requested": result["model"],
        "discussion_id": None,
        "reference_diagram_id": None,
        "scratch_diagram_id": None,
        "scratch_discussion_id": None,
        "case": f"turn trial {result['variant']} statement {result['statement_id']} run {result['run']}",
        "outcome": Outcome.Passed if result["reply"] is not None else Outcome.Failed,
        "turns": 1,
        "scores": None,
        "faults": None,
        "tokens": tokens,
        "cost": result["cost"],
        "duration_ms": result["duration_ms"],
        "source": Source.Api,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("export", type=Path)
    parser.add_argument("statement", type=int)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--first", type=int, default=1, help="index of the first run")
    parser.add_argument("--model", default=None, help="a coach model alias; none is the app's")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--requests", type=Path, help="where the first call's request is kept")
    parser.add_argument("--cap", type=Decimal, default=Decimal("10"), help="dollars for this run")
    parser.add_argument(
        "--tools", type=Path, help='JSON list of {"old", "new"} phrases for the tool schemas'
    )
    args = parser.parse_args()
    replacements = json.loads(args.tools.read_text()) if args.tools else []

    turnlog.use(turnlog.MemoryLog())
    with stubbed(STUBS):
        made = make_app(types.SimpleNamespace(), Path(tempfile.mkdtemp()))
        next(made)
        load(args.export)
        said = db.session.get(Statement, args.statement)
        day = said.created_at.date()
        spent = Decimal(0)
        with patch("btcopilot.clock.today", lambda zone=None: day), patch(
            "btcopilot.coachturn.schemas", reworded(replacements)
        ):
            for index in range(args.first, args.first + args.runs):
                if spent >= args.cap:
                    print(f"stopped at the cap of ${args.cap}", file=sys.stderr)
                    break
                result = run_once(said, args, index)
                spent += Decimal(str(result["cost"]))
                folder = args.out / args.variant / str(said.id)
                folder.mkdir(parents=True, exist_ok=True)
                request = result.pop("request")
                (folder / f"{index}.md").write_text(page(result))
                (folder / f"{index}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
                if args.requests and request:
                    kept = args.requests / args.variant / str(said.id)
                    kept.mkdir(parents=True, exist_ok=True)
                    (kept / f"{index}.json").write_text(
                        json.dumps(request, indent=1, ensure_ascii=False, default=str)
                    )
                ledger.append(ledger_line(result))
                print(
                    f"{args.variant} {said.id} run {index}: ${result['cost']:.4f}, "
                    f"{result['first_request_tokens']} tokens in the first call, "
                    f"{len(result['tool_calls'])} tool calls"
                    + (f", FAILED {result['error']}" if result["error"] else "")
                )
        print(f"spent ${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
