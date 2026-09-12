"""The scribe: one coder's words about one turn, written into their record.

It is not the coach. There is no conversation, no coaching and no reply: a
cheap model reads the turn and what the coder said about it, and calls the
record-writing tools. When it cannot tell which person is meant it writes
nothing and asks, in one line, which person (R-0270).
"""

import enum
import logging
import re
import uuid

from btcopilot.review import adapter

_log = logging.getLogger(__name__)

MODEL = "haiku-4.5"
MAX_STEPS = 3

PROMPT = """You are a scribe for a research team coding transcripts of family \
conversations. You are given one turn of a transcript and, in their own words, \
what a coder says that turn tells them happened. Write that into the record \
with the tools, and nothing else.

Rules:
- Write only what the coder said. Never add events, people or detail they did \
not give you.
- The coder's words are what you write. The turn is background only. Never \
question whether what the coder said matches the turn, and never ask about \
that: they read the whole conversation and you did not.
- When the coder names a person who is not in the record, add that person and \
then write the event. A name is enough to write from; never ask whether to add \
someone the coder named.
- Add the person first and wait for the id the tool gives you back, then write \
the event in your next turn. Never guess an id for a person you have just \
added.
- Only when the coder points at a person without naming them, and two or more \
people already in the record could be meant, call no tool at all and reply \
with one short question naming the people it could be. That is the only thing \
you may ask about.
- Never change an event the record already holds unless the coder names that \
event: whose it is and what happened. A statement about something that \
happened adds an event; it never edits one. Never change the certainty, the \
date, or any other value of an event the coder did not name.
- The coder cannot see this exchange as a conversation, so never ask about \
anything you could work out, and never ask twice.
- Say nothing when the writing worked. Words are for asking only.

The record as it stands:
{record}
"""

TURN = """The turn the coder tapped, said by {who}:
{turn}

What the coder says it tells them happened:
{said}
"""


class Refused(Exception):
    """The record would not take what the scribe wrote. Its words go to the
    coder as they are, since they already say what is wrong."""


class Pronoun(enum.StrEnum):
    """The words a coder points at a person with instead of naming them."""

    He = "he"
    She = "she"
    They = "they"
    Him = "him"
    Her = "her"
    His = "his"
    Their = "their"


WORDS = re.compile(r"[A-Za-z][A-Za-z']*")


def unclear(said: str, people: list[dict]) -> str:
    """The question to ask instead of writing, or nothing. A coder who points
    at a person without naming one, or names one that could be two people in
    the record, is asked which before any word of it is written (R-0270)."""
    words = WORDS.findall(said)
    spoken = {word.lower() for word in words}
    matched = [
        person
        for person in people
        if spoken & {word.lower() for word in WORDS.findall(_name(person))}
    ]
    if len(matched) > 1:
        return _which(matched)
    if matched:
        return ""
    pointed = spoken & {p.value for p in Pronoun}
    if pointed and not _new_name(words):
        return _which(people)
    return ""


def _new_name(words: list[str]) -> bool:
    """A name the record does not hold yet: a capitalised word the coder wrote
    inside the sentence rather than at the start of it."""
    return any(
        word[:1].isupper() and word.lower() not in {p.value for p in Pronoun}
        for word in words[1:]
    )


def _which(people: list[dict]) -> str:
    named = [_name(person) for person in people]
    if not named:
        return "Which person is this about? The record has nobody in it yet."
    if len(named) == 1:
        return f"Is this about {named[0]}?"
    return f"Which person is this about — {', '.join(named[:-1])} or {named[-1]}?"


def write(coding, statement, said: str, model=None) -> dict:
    """One coding turn. Returns the edit lines it wrote, or the one question it
    asked instead."""
    turn_id = uuid.uuid4().hex
    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    question = unclear(said, record.get("people") or [])
    if question:
        return {"lines": [], "asked": question, "made": [], "turn_id": turn_id}
    toolbox = adapter.scribe_toolbox(
        coding.diagram_id, coding.user_id, statement.id, turn_id
    )
    coach = model or adapter.coach_model(MODEL)
    system = PROMPT.format(record=adapter.render_record(coding.diagram_id))
    messages = [
        {
            "role": "user",
            "content": TURN.format(
                who=_who(statement), turn=statement.text or "", said=said
            ),
        }
    ]
    tools = adapter.write_tools()
    asked = ""

    for step in range(MAX_STEPS):
        turn = _say(coach, system, messages, tools)
        asked = turn.text.strip()
        if not turn.calls:
            break
        results = []
        for call in turn.calls:
            text, refused = _call(toolbox, call)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": text,
                    "is_error": refused,
                }
            )
        messages.append({"role": "assistant", "content": turn.blocks})
        messages.append({"role": "user", "content": results})
        # A turn ends on words, never on a tool call: adding the person the
        # event is about is one step, writing the event is the next.
        asked = ""
        if any(r["is_error"] for r in results):
            _log.warning(f"Scribe step {step} was refused: {results}")

    lines = edit_lines(coding.diagram_id, toolbox.deltas)
    if not lines and not asked:
        raise Refused("the scribe wrote nothing and said nothing")
    return {
        "lines": lines,
        "asked": "" if lines else asked,
        "made": made(toolbox.deltas),
        "turn_id": turn_id,
    }


def made(deltas: list[dict]) -> list[dict]:
    """What the record now holds that it did not, so the picture can light it
    as the line lands, the way it does for the coach's own edits."""
    out: list[dict] = []
    for delta in deltas:
        one = {"kind": delta.get("item_kind"), "id": str(delta.get("item_id"))}
        if delta.get("item_id") is not None and one not in out:
            out.append(one)
    return out


def _who(statement) -> str:
    speaker = statement.speaker
    return (speaker.name if speaker and speaker.name else None) or "someone"


def _say(model, system: str, messages: list[dict], tools: list[dict]):
    words = model.turn(system, messages, tools)
    while True:
        try:
            next(words)
        except StopIteration as stop:
            return stop.value


def _call(toolbox, call) -> tuple[str, bool]:
    try:
        text, _ = toolbox.call(call.name, call.args)
    except adapter.ToolError as e:
        return str(e), True
    return text, False


def edit_lines(diagram_id: int, deltas: list[dict]) -> list[str]:
    """What this scribe turn put in the record, one line each."""
    data = adapter.record_of(adapter.diagram_of(diagram_id))
    events = {str(e.get("id")): e for e in data.get("events") or []}
    named = {
        str(event.get(key))
        for event in events.values()
        for key in ("person", "child", "spouse")
        if event.get(key) is not None
    }
    return written(
        data,
        _touched(deltas, "event"),
        [one for one in _touched(deltas, "person") if one not in named],
    )


def written(data: dict, event_ids, person_ids=()) -> list[str]:
    """The record's own words for what a coder wrote: who it is about, what
    kind of thing it is, and when."""
    people = {str(p.get("id")): p for p in data.get("people") or []}
    events = {str(e.get("id")): e for e in data.get("events") or []}
    out: list[str] = []
    for one in event_ids:
        event = events.get(str(one))
        if event is not None:
            _add(out, _event_words(event, people))
    for one in person_ids:
        person = people.get(str(one))
        if person is not None:
            _add(out, f"+ {_name(person)}")
    return out


def _add(out: list[str], line: str):
    if line not in out:
        out.append(line)


def _event_words(event: dict, people: dict) -> str:
    about = event.get("child")
    if about is None:
        about = event.get("person")
    who = _name(people.get(str(about), {})) if about is not None else "the family"
    kind = _plain(event.get("kind")) or "event"
    return f"+ {who} · {kind} · {_when(event.get('dateTime'))}"


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _when(value) -> str:
    """A day in the words the rest of the app uses: the month and the year."""
    written = adapter.date_text(value)
    if not written:
        return "no date yet"
    year, _, rest = written.partition("-")
    month = rest.split("-")[0]
    return f"{MONTHS[int(month) - 1]} {year}" if month.isdigit() else year


def _plain(value) -> str:
    return str(getattr(value, "value", value) or "")


def _name(person: dict) -> str:
    return (person.get("name") or "").strip() or "someone"


def _touched(deltas: list[dict], kind: str) -> list[str]:
    out: list[str] = []
    for delta in deltas:
        if delta.get("item_kind") != kind or delta.get("item_id") is None:
            continue
        _add(out, str(delta["item_id"]))
    return out
