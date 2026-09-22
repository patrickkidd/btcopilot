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
from btcopilot.schema import DateCertainty, EventKind

_log = logging.getLogger(__name__)

MODEL = "haiku-4.5"
#: One tool call per step is how the cheap model works: a sentence that names
#: two new people and one event needs three, and a wasted guess a fourth.
MAX_STEPS = 8

TURN = """The turn the coder tapped, said by {who}:
{turn}

What the coder says it tells them happened:
{said}
"""


class Refused(ValueError):
    """The scribe could not finish. Its words go to the coder as they are,
    since they already say what is wrong (a ValueError is a 400 here)."""


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
    # A whole name said outright settles it ("Marcus's father" against
    # "Marcus's grandmother"); only then do shared words count.
    lowered = " ".join(spoken_word.lower() for spoken_word in words)
    whole = [
        person
        for person in people
        if " ".join(WORDS.findall(_name(person))).lower() in lowered
    ]
    if whole:
        # Naming two people outright is naming them, not pointing vaguely at
        # one: "Marcus married Delphine" is a sentence about a bond. Only two
        # people the sentence cannot tell apart are asked about, and a name
        # inside a longer one ("Marcus" in "Marcus's father") is the shorter
        # reading of the same words.
        rival = _rival(whole)
        return _which(rival) if rival else ""
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
        could = [p for p in people if _fits(pointed, p)]
        if len(could) != 1:
            return _which(could or people)
    return ""


def _rival(named: list[dict]) -> list[dict]:
    """Two of the people the sentence names outright whose names are the same
    words, which is the one case naming somebody does not say who."""
    words = {id(p): frozenset(w.lower() for w in WORDS.findall(_name(p))) for p in named}
    for person in named:
        same = [p for p in named if words[id(p)] == words[id(person)]]
        if len(same) > 1:
            return same
    return []


#: Words that name a person by their place in the family, which a coder uses
#: the way they would a name ("grandmother stopped speaking to him").
RELATIONS = {
    "father", "mother", "dad", "mom", "grandmother", "grandfather", "grandma",
    "grandpa", "brother", "sister", "son", "daughter", "wife", "husband",
    "partner", "aunt", "uncle", "cousin", "niece", "nephew", "stepfather",
    "stepmother", "parents", "grandparents",
}
MALE = {Pronoun.He.value, Pronoun.Him.value, Pronoun.His.value}
FEMALE = {Pronoun.She.value, Pronoun.Her.value}


def _fits(pointed: set[str], person: dict) -> bool:
    """Whether a pronoun could mean this person, going by the gender the
    record holds; a person with none recorded could be anyone."""
    gender = person.get("gender")
    if pointed & MALE and gender == "female":
        return False
    if pointed & FEMALE and gender == "male":
        return False
    return True


def _new_name(words: list[str]) -> bool:
    """A name the record does not hold yet: a capitalised word the coder wrote
    inside the sentence rather than at the start of it."""
    return any(
        (word[:1].isupper() and word.lower() not in {p.value for p in Pronoun})
        or word.lower() in RELATIONS
        for word in words
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
        _log.info(f"Scribe asked before the model: {question}")
        return {"lines": [], "asked": question, "made": [], "turn_id": turn_id}
    toolbox = adapter.scribe_toolbox(
        coding.diagram_id, coding.user_id, statement.id, turn_id
    )
    coach = model or adapter.coach_model(MODEL)
    system = adapter.scribe_prompt(adapter.render_record(coding.diagram_id))
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
    unfinished = False

    for step in range(MAX_STEPS):
        turn = _say(coach, system, messages, tools)
        asked = turn.text.strip()
        unfinished = bool(turn.calls)
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
    # Every call is committed as it lands, so a loop that ran out of steps has
    # written part of the sentence; the coder is told which part, never shown
    # it as done (R-0302: no silent loss).
    if unfinished:
        raise Refused(_short(lines))
    if not lines and not asked:
        raise Refused("the scribe wrote nothing and said nothing")
    if asked and not lines:
        _log.info(f"Scribe asked instead of writing: {asked}")
    return {
        "lines": lines,
        "asked": "" if lines else asked,
        "made": made(toolbox.deltas),
        "turn_id": turn_id,
    }


def _short(lines: list[str]) -> str:
    wrote = ", ".join(line.removeprefix("+ ") for line in lines)
    kept = f" after adding {wrote}" if wrote else ""
    return f"The scribe stopped before it finished{kept}. Say it again in one sentence."


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
        _touched(deltas, "pair_bond"),
    )


#: The kinds that happen to two partners at once, which read as both names.
PAIR_KINDS = ("married", "bonded", "separated", "divorced")


def written(data: dict, event_ids, person_ids=(), bond_ids=()) -> list[str]:
    """The record's own words for what a coder wrote: who it is about, what
    kind of thing it is, and when. A marriage reads as two names joined and the
    year; a person born into a bond reads as whose child they are (R-0326)."""
    people = {str(p.get("id")): p for p in data.get("people") or []}
    events = {str(e.get("id")): e for e in data.get("events") or []}
    bonds = {str(b.get("id")): b for b in data.get("pair_bonds") or []}
    out: list[str] = []
    said: set[tuple] = set()
    for one in event_ids:
        event = events.get(str(one))
        if event is None:
            continue
        if _plain(event.get("kind")) in PAIR_KINDS:
            said.add(_pair_of(event.get("person"), event.get("spouse")))
        _add(out, _event_words(event, people))
    for one in bond_ids:
        bond = bonds.get(str(one))
        if bond is None:
            continue
        pair = _pair_of(bond.get("person_a"), bond.get("person_b"))
        if pair not in said:
            _add(out, _bond_words(bond, people, events))
    for one in person_ids:
        person = people.get(str(one))
        if person is not None:
            _add(out, f"+ {_person_words(person, people, bonds)}")
    return out


def _pair_of(a, b) -> tuple:
    return tuple(sorted(str(one) for one in (a, b)))


#: What a person born into a bond is called, by the record's own gender field.
CHILD_WORDS = {"male": "son", "female": "daughter"}


def _person_words(person: dict, people: dict, bonds: dict) -> str:
    """A person, and whose child they are when the record says so."""
    name = _name(person)
    bond = bonds.get(str(person.get("parents"))) if person.get("parents") else None
    if bond is None:
        return name
    word = CHILD_WORDS.get(_plain(person.get("gender")), "child")
    return f"{name} · {word} of {_both(bond, people)}"


def _joined(people: dict, *ids) -> str:
    return " & ".join(_name(people.get(str(one), {})) for one in ids)


def _both(bond: dict, people: dict) -> str:
    return _joined(people, bond.get("person_a"), bond.get("person_b"))


def _bond_words(bond: dict, people: dict, events: dict) -> str:
    """A bond nobody wrote an event for: who the two are, whether they married,
    and the year the record has for it."""
    pair = _pair_of(bond.get("person_a"), bond.get("person_b"))
    started = [
        event
        for event in events.values()
        if _plain(event.get("kind")) in ("married", "bonded")
        and _pair_of(event.get("person"), event.get("spouse")) == pair
    ]
    word = "married" if bond.get("married") else "together"
    when = _when(*_dated(started[0])) if started else "no date yet"
    return f"+ {_both(bond, people)} · {word} · {when}"


def _add(out: list[str], line: str):
    if line not in out:
        out.append(line)


def _dated(event: dict) -> tuple:
    return event.get("dateTime"), event.get("dateCertainty")


def _event_words(event: dict, people: dict) -> str:
    kind = _plain(event.get("kind"))
    if kind in PAIR_KINDS and event.get("spouse") is not None:
        both = _joined(people, event.get("person"), event.get("spouse"))
        return f"+ {both} · {kind} · {_when(*_dated(event))}"
    about = event.get("child")
    if about is None:
        about = event.get("person")
    who = _name(people.get(str(about), {})) if about is not None else "the family"
    # A noted event's own words are what happened; its kind says nothing.
    if kind == EventKind.Noted.value:
        said = (event.get("description") or "").strip()
    else:
        said = kind or "event"
    return f"+ {who} · {said} · {_when(*_dated(event))}"


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _when(value, certainty=None) -> str:
    """A day in the words the rest of the app uses: the month and the year.

    A coder who says only a year leaves the scribe writing the first of
    January and marking it approximate, which is within a year either way; the
    month there was never said, so it is not read back (R-0326)."""
    written = adapter.date_text(value)
    if not written:
        return "no date yet"
    year, _, rest = written.partition("-")
    month, _, day = rest.partition("-")
    if not month.isdigit():
        return year
    approximate = _plain(certainty) == DateCertainty.Approximate.value
    if approximate and month == "01" and day == "01":
        return year
    return f"{MONTHS[int(month) - 1]} {year}"


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
