"""The one pass that brings each family's case report to where it would stand
had the report been there from the family's first session, and no further
(R-0739): one call to the family's coach, with its own prompt and map, which
may only put a raised guess on a card and add the question about the
person's own part when the record has none. Any other call is refused and
writes nothing."""

import datetime

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
from btcopilot.models import Author, Diagram, Purpose
from btcopilot.prompts import get_agent_prompt
from btcopilot.recordtext import outline
from btcopilot.schema import CaseReportCard, DiagramData, QuestionState
from btcopilot.toolbox import ToolError, ToolName, Toolbox, schemas

CARD = record.CARD
ALLOWED = {
    ToolName.SetImpression: ("id", CARD),
    ToolName.AddQuestion: ("text", "kind", "state", CARD),
}
SHORT = 60
START = (
    "This is not a chat; nobody reads your words. The case report is new: none "
    "of the guesses and questions on the map is on one of its cards yet. Put "
    "each raised guess that belongs on a card on it, by the same rules you "
    "follow in a chat, with set_impression giving only its id and "
    "case_report_card; leave a guess that belongs on no card as it is. Then, "
    "only if no open question already asks about the person's own part, add "
    "one with add_question on the own_part card, in state asked. Change "
    "nothing else: no new guesses, no rewording, no closing, no people, events "
    "or notes."
)


def marked(data: DiagramData) -> bool:
    return any(q.get(CARD) for q in data.questions)


def raised(data: DiagramData) -> list[dict]:
    return [
        q
        for q in data.questions
        if record.note(q) is record.IMPRESSION and q["state"] == QuestionState.Raised
    ]


def offered() -> list[dict]:
    """The two tools, with only the fields the pass may give."""
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


def allowed(name: str, args: dict, data: DiagramData, version: int, added: bool) -> dict:
    """The call as it will run, or ToolError when the pass may not make it."""
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
        if card not in tuple(CaseReportCard):
            raise ToolError(f"No case report card {card}", "There is no such card.")
        return {"id": str(args["id"]), CARD: card, "version": version}
    if card != CaseReportCard.OwnPart:
        raise ToolError("the one question added here is on the own_part card", "Only the own part question is added here.")
    if added or any(
        record.note(q) is record.QUESTION and q.get(CARD) == CaseReportCard.OwnPart
        for q in data.questions
    ):
        raise ToolError("the record already has its own part question", "There is one already.")
    if args.get("state") != QuestionState.Asked:
        raise ToolError("the own part question is added asked", "It must be asked.")
    return dict(args)


def short(text: str) -> str:
    return text if len(text) <= SHORT else text[: SHORT - 1] + "…"


def pass_over(diagram: Diagram, apply: bool) -> list[dict]:
    """One model call for this family; the cards it would set, or did."""
    data = diagram.get_diagram_data()
    version = diagram.version
    found = questions.sessions(diagram)
    session = found[-1].id if found else None
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
        record=outline(data, version, own and own["id"]),
        today=datetime.date.today().isoformat(),
        coverage=coverage.block(data),
    )
    turn = drain(meter.turn(system, [{"role": "user", "content": START}], offered(), turn_id))
    toolbox = Toolbox(
        diagram.id, turn_id, user_id=diagram.user_id, session_id=session, author=Author.Coach
    )
    before = {q["id"]: q for q in data.questions}
    rows, added = [], False
    for call in turn.calls:
        entry = before.get(str(call.args.get("id")), {})
        rows.append(
            {
                "diagram": diagram.id,
                "owner": diagram.user_id,
                "tool": call.name,
                "entry": entry.get("id", "new"),
                "text": short(entry.get("text") or call.args.get("text") or ""),
                "card_before": entry.get(CARD),
                "card_after": call.args.get(CARD),
            }
        )
        try:
            if call.name == ToolName.AddQuestion and session is None:
                raise ToolError("the family has no session to ask it in", "No session.")
            args = allowed(call.name, call.args, data, version, added)
        except ToolError as e:
            rows[-1].update(card_after=entry.get(CARD), refused=str(e))
            continue
        added = added or call.name == ToolName.AddQuestion
        if apply:
            _, _, refusal = run_call(toolbox, ToolCall(id=call.id, name=call.name, args=args))
            if refusal:
                rows[-1]["refused"] = refusal
    if apply:
        after = {q["id"]: q for q in toolbox.data.questions}
        new = next((i for i in after if i not in before), None)
        for row in rows:
            if row["entry"] == "new" and new and not row.get("refused"):
                row["entry"] = new
            if row.get("entry") in after:
                row["card_after"] = after[row["entry"]].get(CARD)
    return rows or [{"diagram": diagram.id, "owner": diagram.user_id, "refused": "no cards set"}]


@click.command("backfill")
@click.option("--diagram", "diagram_id", type=int, help="Only this record.")
@click.option(
    "--apply/--dry-run",
    default=False,
    help="Write the cards; the default, --dry-run, makes the same model call and writes nothing to the record.",
)
@rows_option
def backfill(diagram_id, apply):
    """Put each family's raised guesses on the case report's cards, and add the
    question about the person's own part where the record has none, as the
    coach would have had the report been there from the start. One model call
    per family that has a raised guess and nothing on a card yet; a family
    with anything on a card is skipped. Every call goes to the model-calls
    ledger. Prints, per guess, the card before and after."""
    diagrams = (
        [find(diagram_id)] if diagram_id else Diagram.query.order_by(Diagram.id).all()
    )
    rows = []
    for diagram in diagrams:
        data = diagram.get_diagram_data()
        if raised(data) and not marked(data):
            rows += pass_over(diagram, apply)
    columns = ["diagram", "owner", "tool", "entry", "text", "card_before", "card_after", "refused"]
    return columns, rows


@click.group("case-report")
def case_report_group():
    """The case report's cards in each record."""


case_report_group.add_command(writes(backfill))
