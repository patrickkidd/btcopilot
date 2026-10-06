"""The one pass that brings each record's questions to where they would stand
had the coach's newest question rules been there from the first session: a
question filed on the wrong kind of thing moves to the right person or
pair-bond by fixed rules, a fact the person already said is kept as a question
already answered (R-0760), and a story the talk moved past is kept to come
back to (R-0770), and the days the coach asked an open question again and the
person passed over it are kept on it (R-0774). The dry run makes the one model call per record and saves a
plan a person can read; the apply writes exactly that plan, each item one
change row, with no model call. Chat messages are never changed."""

import copy
import datetime
import enum
import json
import pathlib

import click

from btcopilot import clock, coverage, profile, record
from btcopilot.admin import setting
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import model_for
from btcopilot.coachturn import drain
from btcopilot.extensions import db
from btcopilot.metered import Metered
from btcopilot.models import Author, Change, Diagram, Discussion, Purpose, Statement
from btcopilot.prompts import get_agent_prompt
from btcopilot.recordtext import outline
from btcopilot.schema import (
    DiagramData,
    Fact,
    FactState,
    ItemKind,
    QuestionKind,
    QuestionOutcome,
    QuestionState,
)
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

TURN = "catch-up:{}"
SAID = 120
STORIES = 8
# What must still hold of a question for its move to be written.
MATCHED = ("text", "state", "outcome", "fact", "item_kind", "item_id")
FIELDS = ("text", "kind", "state", "outcome", "answer", "item_kind", "item_id", "fact")
STATEMENT = {
    "type": "integer",
    "description": "The id of the person's message this rests on.",
}
AGAIN = {
    "type": "integer",
    "description": "The id of the coach's message that asked it again.",
}
START = (
    "This is not a chat; nobody reads your words. Below is everything said in "
    "this family's sessions, oldest first, each message numbered. Read it against the map and the checklist and propose, with "
    "add_question, giving statement each time:\n"
    "1. Each fact on the checklist the person said outright that the map does "
    "not show as known: kind fact, state resolved, outcome answered, the fact, "
    "the person or couple it is about, and answer and statement both the "
    "message that said it. For example, they said they have no children, or "
    "that a parent died.\n"
    "2. Each story the person raised that the talk moved on from before it was "
    "told, and never came back to: an event, a time a symptom flared, a "
    "conflict they named. Kind thought, state held, worded the way the person "
    f"put it, statement the message that raised it. At most {STORIES}, the ones "
    "with the most behind them first.\n"
    "3. Each question the map shows asked and still open that the coach put to "
    "the person again after first asking it, and the person passed over: "
    "set_question with its id, state asked, and statement the coach's message "
    "that asked it again, once for each such message.\n"
    "Propose nothing the map already holds, open or closed. Change nothing "
    "else.\n\n{transcript}"
)


class Part(enum.StrEnum):
    Move = "wrong kind"
    Left = "left as is"
    Fact = "fact said"
    Story = "story to come back to"
    Again = "asked again"
    Dropped = "dropped"


def offered() -> list[dict]:
    """The coach's add_question, without the fields this pass never gives,
    and with the message each proposal rests on; and its set_question as a
    question asked again, with the coach's message that asked it."""
    tools = {s["name"]: s for s in schemas()}
    tool = tools[ToolName.AddQuestion]
    given = tool["input_schema"]
    again = tools[ToolName.SetQuestion]
    return [
        {
            **tool,
            "input_schema": {
                "type": "object",
                "properties": {
                    **{k: v for k, v in given["properties"].items() if k in FIELDS},
                    "statement": STATEMENT,
                },
                "required": [*given["required"], "statement"],
            },
        },
        {
            **again,
            "description": "A question the coach asked the person again, and they passed over.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": again["input_schema"]["properties"]["id"],
                    "state": {"type": "string", "enum": [QuestionState.Asked.value]},
                    "statement": AGAIN,
                },
                "required": ["id", "state", "statement"],
            },
        },
    ]


def said(diagram: Diagram) -> tuple[str, dict[int, Statement], dict[int, Statement]]:
    """Every session's words, oldest first, each message numbered, and the
    person's messages and the coach's by id."""
    lines, mine, coach = [], {}, {}
    sessions = Discussion.query.filter_by(diagram_id=diagram.id).order_by(
        Discussion.created_at, Discussion.id
    )
    for discussion in sessions:
        for statement in sorted(discussion.statements, key=lambda s: (s.order or 0, s.id)):
            if not statement.text:
                continue
            if statement.speaker_id == discussion.chat_user_speaker_id:
                mine[statement.id] = statement
                lines.append(f"[person message {statement.id}] {statement.text}")
            else:
                coach[statement.id] = statement
                lines.append(f"[coach message {statement.id}] {statement.text}")
    return "\n\n".join(lines), mine, coach


def target(data: DiagramData, kind, iid) -> str | None:
    try:
        return f"{kind} {iid}: {coverage.label(data, ItemKind(kind), int(iid))}"
    except (StopIteration, TypeError, ValueError):
        return kind and f"{kind} {iid}"


def item(data: DiagramData, args: dict, mine: dict[int, Statement]) -> dict:
    statement = mine.get(args.get("statement"))
    return {
        "words": args.get("text"),
        "target": target(data, args.get("item_kind"), args.get("item_id")),
        "state": args.get("state"),
        "outcome": args.get("outcome"),
        "statement": args.get("statement"),
        "said": statement and statement.text[:SAID],
    }


def moves(data: DiagramData) -> tuple[list[dict], list[dict]]:
    """Fact questions filed on the wrong kind of thing (coverage.fits): a
    couple's fact on a person moves to that person's one pair-bond, a
    person's fact on a pair-bond to its partner, and a closed one to each
    partner, as one question per partner with the same words, state, outcome,
    answer and dates (R-0773). Any other is left as is, with the reason: the
    record keeps an open question once in the same words, so it cannot be
    open on both partners."""
    moved, left = [], []
    for q in data.questions:
        if q.get("fact") is None or q.get("item_kind") not in (
            ItemKind.Person,
            ItemKind.PairBond,
        ):
            continue
        fact, kind = Fact(q["fact"]), ItemKind(q["item_kind"])
        if coverage.fits(fact, kind):
            continue
        entry = {
            "question": q["id"],
            "words": q["text"],
            "fact": fact.value,
            "state": q["state"],
            "outcome": q.get("outcome"),
            "from": target(data, kind, q["item_id"]),
            "before": {k: q.get(k) for k in MATCHED},
        }
        closed = q["state"] == QuestionState.Resolved
        if kind is ItemKind.PairBond:
            bond = next(b for b in data.pair_bonds if str(b["id"]) == str(q["item_id"]))
            to = [
                (ItemKind.Person, p) for p in (bond["person_a"], bond["person_b"]) if p is not None
            ]
            fits = len(to) == 1 or (closed and len(to) > 1)
            why = f"the pair-bond has {len(to)} partners in the record" + (
                "" if closed else ", and an open question is kept once"
            )
        else:
            to = [
                (ItemKind.PairBond, b["id"])
                for b in data.pair_bonds
                if int(q["item_id"]) in (b["person_a"], b["person_b"])
            ]
            fits = len(to) == 1
            why = f"the person has {len(to)} pair-bonds, not one"
        if not fits:
            left.append({**entry, "reason": why})
            continue
        moved.append(
            {
                **entry,
                "to": ", ".join(target(data, k.value, i) for k, i in to),
                "links": [[k.value, str(i)] for k, i in to],
            }
        )
    return moved, left


class Proposed(Toolbox):
    """The coach's question tool run over a copy of the record: every check
    the tool makes, and what it would keep added to the copy, so the next
    proposal is checked against it. Nothing is written."""

    def __init__(self, diagram: Diagram, held: DiagramData, session_id: int):
        super().__init__(
            diagram.id, TURN.format(diagram.id), user_id=diagram.user_id, session_id=session_id
        )
        self.held = held

    @property
    def data(self) -> DiagramData:
        return self.held

    def _write(self, kind, item_id, fields, statement_id=None):
        taken = {q["id"] for q in self.held.questions if q["id"].startswith("q")}
        self.held.questions.append({"id": record.next_key("q", taken), **fields})
        return "", {}


def kept_from(diagram: Diagram) -> set[int]:
    """The messages a story this pass kept already rests on."""
    return {
        change.statement_id
        for change in Change.query.filter_by(diagram_id=diagram.id, turn_id=TURN.format(diagram.id))
        if any(
            d["item_kind"] == ItemKind.Question.value
            and d["field"] is None
            and d["after"].get("state") == QuestionState.Held
            for d in change.deltas
        )
    }


def counted_from(diagram: Diagram) -> set[int]:
    """The coach's messages this pass already counted as a question asked
    again."""
    return {
        change.statement_id
        for change in Change.query.filter_by(diagram_id=diagram.id, turn_id=TURN.format(diagram.id))
        if any(d["field"] == record.ASKED_AGAIN for d in change.deltas)
    }


def asked_again(
    held: DiagramData,
    args: dict,
    coach: dict[int, Statement],
    first: dict[str, dict],
    counted: set[int],
    zone: str | None,
) -> tuple[dict, str | None]:
    """A question the coach asked again, its day kept on the copy, or why
    not (R-0774)."""
    q = next((x for x in held.questions if x["id"] == args.get("id")), None)
    statement = coach.get(args.get("statement"))
    entry = {
        "question": args.get("id"),
        "words": q and q["text"],
        "statement": args.get("statement"),
        "said": statement and statement.text[:SAID],
    }
    if statement is None:
        return entry, "it names no message of the coach's in this record"
    if q is None or record.note(q) is not record.QUESTION or q["state"] != QuestionState.Asked:
        return entry, "only a question still asked is asked again"
    day = clock.day(statement.created_at, zone).isoformat()
    asked = first.get(q["id"], {}).get("statement_id")
    replies = sorted(i for i in coach if asked is not None and i > asked)
    if day < q["asked_at"] or (replies and statement.id <= replies[0]):
        return entry, "the coach's message is not after the question was first asked"
    if statement.id in counted:
        return entry, "the coach's message was already counted"
    counted.add(statement.id)
    q[record.ASKED_AGAIN] = [*(q.get(record.ASKED_AGAIN) or []), day]
    return {**entry, "day": day}, None


def refusal(held: DiagramData, args: dict, part: Part, stories: int, cited: set[int]) -> str | None:
    """Why this pass, before the tool, will not keep a proposal: the record's
    own rule on the same words, and this pass's own limits."""
    if part is Part.Story and args["statement"] in cited:
        return "a question was already kept from that message"
    if part is Part.Story and stories >= STORIES:
        return f"more than {STORIES} stories"
    if part is Part.Fact:
        try:
            state = coverage.state_of(
                held,
                Fact(args.get("fact")),
                ItemKind(args.get("item_kind")),
                int(args.get("item_id")),
            )
        except (StopIteration, TypeError, ValueError):
            state = None
        if state is FactState.Known:
            return "the record already holds it"
    for other in held.questions:
        if record.normal(other["text"]) != record.normal(args.get("text") or ""):
            continue
        if other.get("outcome") == QuestionOutcome.DeclinedByUser:
            return f"the person turned those words down as {other['id']}"
        if other["state"] != QuestionState.Resolved:
            return f"those words are already {other['id']}, {other['state']}"
    return None


def part_of(args: dict) -> Part | None:
    if args.get("kind") == QuestionKind.Fact and args.get("state") == QuestionState.Resolved:
        return Part.Fact
    if args.get("kind") == QuestionKind.Thought and args.get("state") == QuestionState.Held:
        return Part.Story
    return None


def proposals(
    diagram: Diagram,
    data: DiagramData,
    moved: list[dict],
    calls: list[tuple[str, dict]],
    mine: dict[int, Statement],
    coach: dict[int, Statement],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """The facts and stories the coach's tool would keep, in order, and the
    questions asked again, by the coach's message, all checked against the
    record with the planned moves made; and every other proposal with why it
    was dropped."""
    held = after_moves(data, moved)
    cited, counted = kept_from(diagram), counted_from(diagram)
    first = record.asked_in(diagram.id)
    zone = Toolbox(diagram.id, TURN.format(diagram.id), user_id=diagram.user_id).zone
    facts, stories, again, dropped = [], [], [], []
    ordered = sorted(
        calls, key=lambda c: (c[0] == ToolName.SetQuestion and c[1].get("statement")) or 0
    )
    for name, args in ordered:
        if name == ToolName.SetQuestion:
            entry, reason = asked_again(held, args, coach, first, counted, zone)
            (again if reason is None else dropped).append(
                entry if reason is None else {**entry, "reason": reason}
            )
            continue
        entry = item(data, args, mine)
        part = part_of(args)
        if name != ToolName.AddQuestion or part is None:
            reason = "only a fact already answered or a story held is kept here"
        elif args.get("statement") not in mine:
            reason = "it names no message of the person's in this record"
        else:
            reason = refusal(held, args, part, len(stories), cited)
        if reason is None:
            tool = {k: v for k, v in args.items() if k in FIELDS}
            try:
                Proposed(diagram, held, mine[args["statement"]].discussion_id).call(
                    ToolName.AddQuestion, tool
                )
            except ToolError as e:
                reason = str(e)
            else:
                (facts if part is Part.Fact else stories).append({**entry, "args": tool})
                continue
        dropped.append({**entry, "reason": reason})
    return facts, stories, again, dropped


def planned(diagram: Diagram, plans: pathlib.Path) -> pathlib.Path | None:
    """The one model call for this record, and the plan it makes, saved; None
    for a record with no session and nothing filed on the wrong kind."""
    data = diagram.get_diagram_data()
    turn_id = TURN.format(diagram.id)
    transcript, mine, coach = said(diagram)
    moved, left = moves(data)
    if not (mine or moved or left):
        return None
    facts, stories, again, dropped = [], [], [], []
    if mine:
        meter = Metered(
            diagram.user_id,
            diagram.id,
            turn_id,
            Purpose.Backfill,
            model=model_for(setting.read(SettingKey.CoachModel, diagram.user_id)),
        )
        own = profile.own(data)
        system = get_agent_prompt(
            record=outline(data, diagram.version, own and own["id"]),
            today=datetime.date.today().isoformat(),
            coverage=coverage.block(data),
        )
        start = START.replace("{transcript}", transcript)
        turn = drain(meter.turn(system, [{"role": "user", "content": start}], offered(), turn_id))
        facts, stories, again, dropped = proposals(
            diagram, data, moved, [(c.name, c.args) for c in turn.calls], mine, coach
        )
    plan = {
        "diagram": diagram.id,
        "owner": diagram.user_id,
        "counts": {
            "moved": len(moved),
            "left_as_is": len(left),
            "facts": len(facts),
            "stories": len(stories),
            "asked_again": len(again),
            "dropped": len(dropped),
        },
        "moved": moved,
        "left_as_is": left,
        "facts": facts,
        "stories": stories,
        "asked_again": again,
        "dropped": dropped,
    }
    plans.mkdir(parents=True, exist_ok=True)
    path = plans / f"catch-up-{diagram.id}.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    return path


def shown(plan: dict, path: pathlib.Path | None = None) -> list[dict]:
    """One row per item of a plan, as the command prints it."""
    rows = []
    for part, key in (
        (Part.Move, "moved"),
        (Part.Left, "left_as_is"),
        (Part.Fact, "facts"),
        (Part.Story, "stories"),
        (Part.Again, "asked_again"),
        (Part.Dropped, "dropped"),
    ):
        for one in plan[key]:
            rows.append(
                {
                    "diagram": plan["diagram"],
                    "part": part.value,
                    "entry": one.get("question", "new"),
                    "words": one["words"],
                    "target": one.get("to") or one.get("target") or one.get("from"),
                    "statement": one.get("statement"),
                    "refused": one.get("reason"),
                    **({"plan": str(path)} if path else {}),
                }
            )
    return rows


def refiled(questions: list[dict], q: dict, links: list[list[str]]) -> list[tuple[str, dict]]:
    """The fields each question takes in a move: the question itself to the
    first link, and a whole copy under a new id to each other link."""
    first, *rest = links
    taken = {x["id"] for x in questions if x["id"].startswith("q")}
    filed = [(q["id"], dict(zip(record.REFILED, first)))]
    for link in rest:
        copy_id = record.next_key("q", taken)
        taken.add(copy_id)
        whole = {k: v for k, v in q.items() if k != "id" and v is not None}
        filed.append((copy_id, {**whole, **dict(zip(record.REFILED, link))}))
    return filed


def after_moves(data: DiagramData, moved: list[dict]) -> DiagramData:
    """A copy of the record with the planned moves made, so proposals are
    checked against the record the apply leaves."""
    held = copy.deepcopy(data)
    for one in moved:
        q = next(x for x in held.questions if x["id"] == one["question"])
        for qid, fields in refiled(held.questions, q, one["links"]):
            mine = next((x for x in held.questions if x["id"] == qid), None)
            if mine is None:
                held.questions.append({"id": qid, **fields})
            else:
                mine.update(fields)
    return held


def move(diagram: Diagram, one: dict) -> str | None:
    """One wrong-kind question to its right target, and a copy of it to each
    other target, as one change row; why not, when the question or where it
    goes changed since the dry run, or the record refuses."""
    data = diagram.get_diagram_data()
    q = next((q for q in data.questions if q["id"] == one["question"]), None)
    if q is None or {k: q.get(k) for k in one["before"]} != one["before"]:
        return "the question changed since the dry run"
    now = next((m for m in moves(data)[0] if m["question"] == q["id"]), None)
    if now is None or now["links"] != one["links"]:
        return "where the question goes changed since the dry run"
    filed = refiled(data.questions, q, one["links"])
    try:
        record.apply(
            diagram.id,
            [
                {
                    "item_kind": ItemKind.Question.value,
                    "item_id": qid,
                    "field": field,
                    "after": value,
                }
                for qid, fields in filed
                for field, value in fields.items()
            ],
            author=Author.Coach,
            turn_id=TURN.format(diagram.id),
            user_id=diagram.user_id,
            refile=True,
        )
    except record.Invalid as e:
        return str(e)
    return None


def keep(diagram: Diagram, one: dict) -> tuple[str | None, str | None]:
    """One fact or story through the coach's own tool, as one change row
    carrying the message it rests on."""
    statement = db.session.get(Statement, one["statement"])
    if statement is None:
        return None, "the message is gone"
    toolbox = Toolbox(
        diagram.id,
        TURN.format(diagram.id),
        user_id=diagram.user_id,
        session_id=statement.discussion_id,
        author=Author.Coach,
        statement_id=statement.id,
    )
    try:
        _, patch = toolbox.call(ToolName.AddQuestion, one["args"])
    except ToolError as e:
        return None, str(e)
    return patch["deltas"][0]["item_id"], None


def ask_again(diagram: Diagram, one: dict, counted: set[int]) -> str | None:
    """One day a question was asked again, as one change row carrying the
    coach's message that asked it; why not, when the record refuses."""
    if one["statement"] in counted:
        return "the coach's message was already counted"
    q = next((q for q in diagram.get_diagram_data().questions if q["id"] == one["question"]), None)
    if q is None:
        return "the question is gone"
    try:
        record.apply(
            diagram.id,
            [
                {
                    "item_kind": ItemKind.Question.value,
                    "item_id": q["id"],
                    "field": record.ASKED_AGAIN,
                    "after": [*(q.get(record.ASKED_AGAIN) or []), one["day"]],
                }
            ],
            author=Author.Coach,
            turn_id=TURN.format(diagram.id),
            user_id=diagram.user_id,
            statement_id=one["statement"],
        )
    except record.Invalid as e:
        return str(e)
    counted.add(one["statement"])
    return None


def applied(path: pathlib.Path) -> list[dict]:
    """A saved plan written as it stands: the moves, then the facts, then the
    stories, then the questions asked again, each refused alone when the
    record no longer allows it."""
    plan = json.loads(path.read_text())
    diagram = find(plan["diagram"])
    for one in plan["moved"]:
        one["reason"] = move(diagram, one)
    for one in plan["facts"] + plan["stories"]:
        one["question"], one["reason"] = keep(diagram, one)
    counted = counted_from(diagram)
    for one in plan["asked_again"]:
        one["reason"] = ask_again(diagram, one, counted)
    return shown({**plan, "left_as_is": [], "dropped": []})


@click.command("catch-up")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="Write saved plans; the default, --dry-run, makes the model call and saves "
    "the plan, writing nothing to the record.",
)
@click.option(
    "--plan",
    "plan_paths",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
    multiple=True,
    help="With --apply: a plan file the dry run printed.",
)
@click.option(
    "--plans",
    type=click.Path(file_okay=False, path_type=pathlib.Path),
    default="catch-up-plans",
    show_default=True,
    help="Where the dry run saves its plans.",
)
@rows_option
def catch_up(diagram_id, apply, plan_paths, plans):
    """Bring each record's questions to where they would stand had the coach's
    question rules been there from the first session: a fact question filed
    on the wrong kind of thing moves to the right person or pair-bond, a fact
    the person already said is kept as a question already answered, a story
    the talk moved past is kept to come back to, and each day the coach asked
    an open question again and the person passed over it is kept on that
    question. Chat messages are never changed. The dry run makes one model call per record with a session, goes
    to the model-calls ledger, and saves a plan a person can read; --apply
    --plan writes exactly that plan, each item one change row that
    `diagrams undo` takes back, with no model call."""
    columns = ["diagram", "part", "entry", "words", "target", "statement", "refused"]
    if apply:
        if not plan_paths:
            raise click.ClickException("--apply writes a saved plan: give --plan, from a dry run")
        rows = [row for path in plan_paths for row in applied(path)]
    else:
        columns.append("plan")
        diagrams = [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
        rows = []
        for diagram in diagrams:
            path = planned(diagram, plans)
            if path is not None:
                rows += shown(json.loads(path.read_text()), path)
    return columns, rows


catch_up = writes(catch_up)
