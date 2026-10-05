"""The one pass that brings each family's case report to where it would stand
had the report been there from the family's first session, and no further
(R-0739): one call to the family's coach, with its own prompt and map, which
may only put a raised guess or an existing question that came in after the
newest card was set on a card, and add the question about the person's own
part when the record has none. Cards already set stay, under the record's own
card rules. Any other call is refused and writes nothing. The dry run saves
what it would write; the apply writes that saved plan and calls no model."""

import datetime
import json
import pathlib

import click

from btcopilot import coverage, profile, questions, record
from btcopilot.admin import setting
from btcopilot.admin.diagrams import find
from btcopilot.admin.guard import writes
from btcopilot.admin.output import rows_option
from btcopilot.admin.setting import SettingKey
from btcopilot.coachmodel import ToolCall, model_for
from btcopilot.coachturn import drain, run_call
from btcopilot.metered import Metered
from btcopilot.models import Author, Change, Diagram, Purpose
from btcopilot.prompts import get_agent_prompt
from btcopilot.recordtext import note_line, on_map, outline, question_order
from btcopilot.schema import CaseReportCard, DiagramData, ItemKind, QuestionState
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

CARD = record.CARD
ALLOWED = {
    ToolName.SetImpression: ("id", CARD),
    ToolName.SetQuestion: ("id", CARD),
    ToolName.AddQuestion: ("text", "kind", "state", CARD),
}
SHORT = 60
CLOSED = "CLOSED QUESTIONS"
START = (
    "This is not a chat; nobody reads your words. The case report's cards "
    "stay as the map shows them. These guesses and questions came in since a "
    "card was last set and are on no card: {ids}. Put each one that belongs on "
    "a card on it, by the same rules you follow in a chat, with set_impression "
    "or set_question giving only its id and case_report_card; leave one that "
    "belongs on no card as it is. Then, only if no question, open or answered, "
    "already asks about the person's own part, add one with add_question on "
    "the own_part card, in state asked. Change nothing else: no new guesses, "
    "no rewording, no closing, no people, events or notes."
)


def raised(data: DiagramData) -> list[dict]:
    return [
        q
        for q in data.questions
        if record.note(q) is record.IMPRESSION and q["state"] == QuestionState.Raised
    ]


def fresh(diagram: Diagram, data: DiagramData) -> set[str]:
    """The ids of the raised guesses and the questions on no card that came
    into the record after the newest card was set, from the change log; every
    one of them before any card was."""
    added, last = {}, 0
    for change in Change.query.filter_by(diagram_id=diagram.id).order_by(Change.id):
        for delta in change.deltas:
            if delta["item_kind"] != ItemKind.Question.value:
                continue
            whole = delta["field"] is None and delta.get("before") is None and delta["after"]
            if whole:
                added[str(delta["item_id"])] = change.id
            if (whole and whole.get(CARD)) or (delta["field"] == CARD and delta["after"]):
                last = change.id
    return {
        q["id"]
        for q in raised(data) + [q for q in data.questions if record.note(q) is record.QUESTION]
        if not q.get(CARD) and (not last or added.get(q["id"], 0) > last)
    }


def closed(data: DiagramData) -> str:
    """The questions the coach's map leaves out once closed, so the pass sees
    an own part question that was already answered."""
    lines = [
        note_line(q)
        for q in sorted(data.questions, key=question_order)
        if record.note(q) is record.QUESTION and not on_map(q)
    ]
    return f"\n\n{CLOSED}\n" + "\n".join(lines) if lines else ""


def offered() -> list[dict]:
    """The three tools, with only the fields the pass may give."""
    out = []
    for schema in schemas():
        if schema["name"] not in ALLOWED:
            continue
        fields = ALLOWED[ToolName(schema["name"])]
        given = schema["input_schema"]
        out.append(
            {
                **schema,
                "input_schema": {
                    "type": "object",
                    "properties": {k: v for k, v in given["properties"].items() if k in fields},
                    "required": [k for k in given.get("required", []) if k in fields],
                },
            }
        )
    return out


def allowed(name: str, args: dict, data: DiagramData, new: set[str], owned: bool) -> dict:
    """The call as it will run, or ToolError when the pass may not make it.
    `new` is what came in since a card was last set; `owned` is whether a
    question is already on the own part card, in the record or by this pass's
    own earlier calls."""
    tool = next((t for t in ALLOWED if t.value == name), None)
    if tool is None:
        raise ToolError(f"{name} is not part of this pass", "Only cards are set here.")
    extra = sorted(set(args) - set(ALLOWED[tool]))
    if extra:
        raise ToolError(f"{name} may not give {', '.join(extra)} here", "Only cards are set here.")
    card = args.get(CARD)
    if tool is ToolName.SetImpression:
        if not any(q["id"] == str(args.get("id")) for q in raised(data)):
            raise ToolError(f"No raised guess {args.get('id')}", "Only raised guesses go on cards.")
        if str(args["id"]) not in new:
            raise ToolError(f"{args['id']} came in before the cards were set", "Cards already set stay.")
        if card not in tuple(CaseReportCard):
            raise ToolError(f"No case report card {card}", "There is no such card.")
        return {"id": str(args["id"]), CARD: card}
    if tool is ToolName.SetQuestion:
        found = next((q for q in data.questions if q["id"] == str(args.get("id"))), None)
        if found is None or record.note(found) is not record.QUESTION:
            raise ToolError(f"No question {args.get('id')}", "Only questions already there go on cards.")
        if found["id"] not in new:
            raise ToolError(f"{found['id']} came in before the cards were set", "Cards already set stay.")
        if card not in record.QUESTION_CARDS:
            raise ToolError(f"a question goes on own_part or choice, not {card}", "Not that card.")
        return {"id": found["id"], CARD: card}
    if card != CaseReportCard.OwnPart:
        raise ToolError("the one question added here is on the own_part card", "Only the own part question is added here.")
    if owned:
        raise ToolError("a question is already on the own_part card", "There is one already.")
    if args.get("state") != QuestionState.Asked:
        raise ToolError("the own part question is added asked", "It must be asked.")
    return dict(args)


def checked(diagram: Diagram, data: DiagramData, calls: list[tuple[str, dict]]) -> list[dict]:
    """Each call with what it would write, or why it is refused. Cards on what
    is already there go first, so a question put on the own part card bars a
    new one."""
    before = {q["id"]: q for q in data.questions}
    new = fresh(diagram, data)
    owned = any(
        record.note(q) is record.QUESTION and q.get(CARD) == CaseReportCard.OwnPart
        for q in data.questions
    )
    rows = []
    for name, args in sorted(calls, key=lambda c: c[0] == ToolName.AddQuestion):
        entry = before.get(str(args.get("id")), {})
        row = {
            "diagram": diagram.id,
            "owner": diagram.user_id,
            "tool": name,
            "entry": entry.get("id", "new"),
            "text": short(entry.get("text") or args.get("text") or ""),
            "card_before": entry.get(CARD),
            "card_after": args.get(CARD),
        }
        try:
            row["args"] = allowed(name, args, data, new, owned)
        except ToolError as e:
            row.update(card_after=entry.get(CARD), refused=str(e))
        else:
            owned = owned or (
                name != ToolName.SetImpression and row["card_after"] == CaseReportCard.OwnPart
            )
        rows.append(row)
    return rows


def short(text: str) -> str:
    return text if len(text) <= SHORT else text[: SHORT - 1] + "…"


def planned(diagram: Diagram, plans: pathlib.Path) -> list[dict]:
    """The one model call for this family; the cards it would set, saved."""
    data = diagram.get_diagram_data()
    turn_id = f"case-report-backfill:{diagram.id}"
    meter = Metered(
        diagram.user_id,
        diagram.id,
        turn_id,
        Purpose.Backfill,
        model=model_for(setting.read(SettingKey.CoachModel, diagram.user_id)),
    )
    own = profile.own(data)
    system = get_agent_prompt(
        record=outline(data, diagram.version, own and own["id"]) + closed(data),
        today=datetime.date.today().isoformat(),
        coverage=coverage.block(data),
    )
    start = START.format(ids=", ".join(sorted(fresh(diagram, data))))
    turn = drain(meter.turn(system, [{"role": "user", "content": start}], offered(), turn_id))
    rows = checked(diagram, data, [(c.name, c.args) for c in turn.calls])
    path = plans / f"case-report-{diagram.id}.json"
    plans.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"diagram": diagram.id, "calls": [[r["tool"], r["args"]] for r in rows if "args" in r]},
            indent=2,
        )
    )
    for row in rows:
        row["plan"] = str(path)
    return rows


def applied(path: pathlib.Path) -> list[dict]:
    """A saved plan written through the same checks, against the record as it
    stands now; no model call."""
    plan = json.loads(path.read_text())
    diagram = find(plan["diagram"])
    data = diagram.get_diagram_data()
    rows = checked(diagram, data, [tuple(call) for call in plan["calls"]])
    found = questions.sessions(diagram)
    toolbox = Toolbox(
        diagram.id,
        f"case-report-backfill:{diagram.id}",
        user_id=diagram.user_id,
        session_id=found[-1].id if found else None,
        author=Author.Coach,
    )
    version = diagram.version
    for n, row in enumerate(rows):
        args = row.get("args")
        if args is None:
            continue
        if row["tool"] == ToolName.AddQuestion and toolbox.session_id is None:
            row["refused"] = "the family has no session to ask it in"
            continue
        if row["tool"] != ToolName.AddQuestion:
            args = {**args, "version": version}
        _, _, refusal = run_call(toolbox, ToolCall(id=f"plan-{n}", name=row["tool"], args=args))
        if refusal:
            row["refused"] = refusal
    after = {q["id"]: q for q in toolbox.data.questions}
    new = next((i for i in after if i not in {q["id"] for q in data.questions}), None)
    for row in rows:
        if row["entry"] == "new" and new and not row.get("refused"):
            row["entry"] = new
        if row["entry"] in after:
            row["card_after"] = after[row["entry"]].get(CARD)
    return rows


@click.command("backfill")
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
    default="case-report-plans",
    show_default=True,
    help="Where the dry run saves its plans.",
)
@rows_option
def backfill(diagram_id, apply, plan_paths, plans):
    """Put each family's raised guesses and its questions on the case report's
    cards, and add the question about the person's own part where the record
    has none, as the coach would have had the report been there from the
    start. The dry run makes one model call per family that has a raised
    guess or question on no card that came in after the newest card was set,
    goes to the model-calls ledger, prints
    each card before and after, and saves the plan to a file; --apply --plan
    writes exactly that plan, checked again, with no model call."""
    columns = ["diagram", "owner", "tool", "entry", "text", "card_before", "card_after", "refused"]
    if apply:
        if not plan_paths:
            raise click.ClickException("--apply writes a saved plan: give --plan, from a dry run")
        rows = [row for path in plan_paths for row in applied(path)]
    else:
        columns.append("plan")
        rows = [
            row
            for diagram in (
                [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
            )
            if fresh(diagram, diagram.get_diagram_data())
            for row in planned(diagram, plans)
        ]
    return columns, [{k: v for k, v in row.items() if k != "args"} for row in rows]


@click.group("case-report")
def case_report_group():
    """The case report's cards in each record."""


case_report_group.add_command(writes(backfill))
