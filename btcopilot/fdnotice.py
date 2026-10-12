"""The coach writing first once a desktop file is in a diagram [Oracle: R-0878]:
what came in, how many things it will check with the person as they go, a few
at a time [Oracle: R-0852], and which of the people is them when the file did
not mark exactly one [Oracle: R-0871]. While the questions the import left
stay open and the person has gone quiet, it reminds them, within the limits
every message the coach writes first keeps.

The import's questions are told apart from the coach's own by the change-log
turn that added them: the import's own turn."""

import datetime
from dataclasses import dataclass

# proactive picks this module's reminders and this module sends through
# proactive; neither uses the other at import time.
from btcopilot import fdimport, proactive, record
from btcopilot.discussions import chats
from btcopilot.extensions import db
from btcopilot.familymatch import unnamed
from btcopilot.fdledger import many
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    Discussion,
    ProactiveMessage,
    Statement,
    Trigger,
    User,
)
from btcopilot.schema import DiagramData, ItemKind, QuestionKind, QuestionState

PREFIX = fdimport.TURN.format("")
# The first reminder comes this long after the person last spoke or was
# written to about the import, each later one a week after the last; no more
# than REMINDERS for one import. A message still waiting for an answer and two
# ignored in a row hold them back as they hold back every other.
FIRST = datetime.timedelta(days=2)
EVERY = datetime.timedelta(days=7)
REMINDERS = 4
HEAD = "QUESTIONS FROM THE IMPORTED FILE"


@dataclass(frozen=True)
class Summary:
    """What an import brought in, as the importer counts it."""

    turn_id: str
    # Added or joined to someone already in the diagram; `events` counts the
    # `drawn` ones the coding pass found in the file's notes, and the ones the
    # import made from the file's ticks and relationship lines.
    people: int
    events: int
    pair_bonds: int
    drawn: int = 0
    # The events the file itself holds, as its import record counts them.
    filed: int = 0
    # The events whose coding the pass refused, left to code later.
    uncoded: int = 0
    # The people the file marked as the one it is about, when not exactly one.
    primaries: tuple[int, ...] = ()


def after_import(diagram_id: int, user_id: int, summary: Summary) -> ProactiveMessage:
    """One coach message in the person's thread, sent now. When the diagram
    says nobody is them, or only a person with no name yet, the import also
    keeps the question of which one is, under its own turn, so it is counted
    and reminded of with the rest."""
    user = db.session.get(User, user_id)
    data = db.session.get(Diagram, diagram_id).get_diagram_data()
    who = None
    primary = data.primary_person()
    if primary is None or unnamed(primary.get("name")):
        who = _ask_who(diagram_id, user_id, summary, data, primary)
        data = db.session.get(Diagram, diagram_id).get_diagram_data()
    message = ProactiveMessage(
        user_id=user_id,
        diagram_id=diagram_id,
        trigger=Trigger.Import,
        key=summary.turn_id,
        question=_words(summary, len(opened(diagram_id, data)), who),
    )
    proactive.send(user, message, message.question, datetime.datetime.utcnow())
    db.session.commit()
    return message


def _ask_who(
    diagram_id: int,
    user_id: int,
    summary: Summary,
    data: DiagramData,
    primary: dict | None,
) -> dict:
    """On the person with no name yet, when the diagram has one, so the
    answer joins them to the person chosen [Oracle: R-0871]."""
    taken = {q["id"] for q in data.questions}
    people = {p["id"]: p for p in data.people}
    named = [_name(people[i]) for i in summary.primaries if i in people]
    question = {
        "id": record.next_key("q", taken),
        "text": (
            f"Which of {', '.join(named[:-1])} and {named[-1]} is you?"
            if len(named) > 1
            else "Which of the people in your file is you?"
        ),
        "kind": QuestionKind.Fact.value,
        "item_kind": primary and ItemKind.Person.value,
        "item_id": primary and str(primary["id"]),
        "fact": None,
        "state": QuestionState.Held.value,
        "outcome": None,
        "session_id": None,
        "asked_at": None,
    }
    record.apply(
        diagram_id,
        [
            {
                "item_kind": ItemKind.Question.value,
                "item_id": question["id"],
                "field": None,
                "after": question,
            }
        ],
        author=Author.Pro,
        turn_id=summary.turn_id,
        user_id=user_id,
    )
    return question


def _name(person: dict) -> str:
    return " ".join(filter(None, (person.get("name"), person.get("last_name"))))


def _words(summary: Summary, checks: int, who: dict | None) -> str:
    said = [
        f"Your file is in: {many(summary.people, 'person', 'people')}, "
        f"{many(summary.filed, 'event')} and "
        f"{many(summary.pair_bonds, 'pair-bond')}."
    ]
    if summary.drawn:
        said.append(f"I also found {many(summary.drawn, 'more event')} in your notes.")
    if summary.uncoded:
        said.append(f"I couldn't code {summary.uncoded} of the events yet.")
    if checks:
        said.append(
            f"There {_is(checks)} {many(checks, 'thing')} in it I'd like to check "
            f"with you{', a few at a time as we go' if checks > 1 else ''}."
        )
    if who:
        said.append(f"First, {who['text'][0].lower()}{who['text'][1:]}")
    elif checks:
        said.append("Shall we start with the first one?")
    else:
        said.append("Where would you like to start?")
    return " ".join(said)


def _is(n: int) -> str:
    return "is" if n == 1 else "are"


def opened(diagram_id: int, data: DiagramData) -> list[dict]:
    """The questions an import added that are still open, oldest first."""
    added = {
        str(delta["item_id"])
        for change in _imports(diagram_id)
        for delta in change.deltas
        if delta["item_kind"] == ItemKind.Question.value and delta["field"] is None
    }
    return [
        q
        for q in data.questions
        if q["id"] in added and q["state"] != QuestionState.Resolved
    ]


def _imports(diagram_id: int) -> list[Change]:
    return (
        Change.query.filter(
            Change.diagram_id == diagram_id, Change.turn_id.startswith(PREFIX)
        )
        .order_by(Change.id)
        .all()
    )


def block(diagram_id: int, data: DiagramData) -> str:
    """What the coach sees each turn while the import's questions are open."""
    found = opened(diagram_id, data)
    if not found:
        return ""
    return (
        f"{HEAD}\n{many(len(found), 'question')} the desktop file import kept "
        f"{_is(len(found))} still open: "
        f"{', '.join(q['id'] for q in found)}."
    )


def reminder(user: User, now: datetime.datetime) -> ProactiveMessage | None:
    """The reminder due on the newest import into any of the person's
    diagrams whose questions are still open, unsaved; None when none is."""
    diagrams = Diagram.query.filter_by(user_id=user.id).order_by(Diagram.id)
    for diagram in diagrams:
        imports = _imports(diagram.id)
        if not imports:
            continue
        turn = imports[-1].turn_id
        found = opened(diagram.id, diagram.get_diagram_data())
        sent = (
            ProactiveMessage.query.filter(
                ProactiveMessage.diagram_id == diagram.id,
                ProactiveMessage.key.startswith(turn),
                ProactiveMessage.sent_at.isnot(None),
            )
            .order_by(ProactiveMessage.sent_at)
            .all()
        )
        reminded = sum(m.key != turn for m in sent)
        if not found or reminded >= REMINDERS:
            continue
        last = max(
            [
                imports[-1].created_at,
                *(m.sent_at for m in sent),
                *_said(user, diagram.id),
            ]
        )
        if now - last < (FIRST if reminded == 0 else EVERY):
            continue
        return ProactiveMessage(
            user_id=user.id,
            diagram_id=diagram.id,
            trigger=Trigger.Import,
            key=f"{turn}:{reminded + 1}",
            question=(
                f"{many(len(found), 'thing').capitalize()} from the file you brought in "
                f"{_is(len(found))} still to check with you. "
                "Shall we look at one now?"
            ),
        )
    return None


def _said(user: User, diagram_id: int) -> list[datetime.datetime]:
    """When the person last wrote on this family, if ever."""
    voices = [
        speaker_id
        for (speaker_id,) in chats(user, diagram_id).with_entities(
            Discussion.chat_user_speaker_id
        )
    ]
    newest = (
        Statement.query.filter(Statement.speaker_id.in_(voices))
        .order_by(Statement.created_at.desc())
        .first()
    )
    return [newest.created_at] if newest else []
