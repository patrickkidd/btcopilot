"""The scribe: one coder's words about one turn, written into their record.

It is not the coach. There is no conversation, no coaching and no reply: a
cheap model reads the turn and what the coder said about it, and calls the
record-writing tools. When it cannot tell which person is meant it writes
nothing and offers the people it could be, one tap each (R-0270). What it
wrote and what the diagram refused reach the coder as rows, never sentences
(R-0883).
"""

import enum
import logging
import re
import uuid
from collections import Counter

from btcopilot.review import adapter
from btcopilot.review.scribetools import ScribeTools
from btcopilot.schema import DateCertainty, DatePrecision, EventKind, event_title

_log = logging.getLogger(__name__)

MODEL = "gemini-3.8-flash"
#: Model answers, each with one or more tool calls; a refusal read back and
#: corrected is one more.
MAX_STEPS = 8

TURN = """The turn the coder tapped, said by {who}:
{turn}

What the coder says it tells them happened:
{said}
"""
CHOSEN = "\nThe person this is about: {line}\n"
#: Said back to a scribe that stopped on words while a call was refused, so it
#: corrects the call rather than giving up on it.
AGAIN = "Not entered yet: {refused} Correct the call and make it again."
#: Said back to a scribe that answered in words before making any call: the
#: coder's statement goes in as given, never weighed against the turn (R-0884).
ENTER = "Nothing is entered yet. Enter the coder's statement as they gave it."


class Verb(enum.StrEnum):
    """Whether a row's entry was made or changed, said as the chat's tool-call
    lines say it: "Added ...", "Changed ..." (R-0883)."""

    Add = "add"
    Change = "change"


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


def unclear(said: str, people: list[dict]) -> list[dict] | None:
    """The people the coder could mean, to tap one of, or None when the words
    say who. A coder who points at a person without naming one, or names one
    that could be two people in the record, picks which before any word of it
    is written (R-0270)."""
    words = WORDS.findall(said)
    spoken = {word.lower() for word in words}
    # A whole name said outright settles it ("Marcus's father" against
    # "Marcus's grandmother"); only then do shared words count.
    lowered = " ".join(spoken_word.lower() for spoken_word in words)
    whole = [person for person in people if _says(lowered, _name(person))]
    if whole:
        # Naming two people outright is naming them, not pointing vaguely at
        # one: "Marcus married Delphine" is a sentence about a bond. Only two
        # people the sentence cannot tell apart are asked about, and a name
        # inside a longer one ("Marcus" in "Marcus's father") is the shorter
        # reading of the same words. A first and last name said together
        # ("Robert Stinson") tells two Roberts apart.
        rivals = _rival(whole)
        full = [p for p in rivals if p.get("last_name") and _says(lowered, _full(p))]
        wholes = Counter(_full(p).lower() for p in people)
        # Each named in full by a whole name no one else holds: "Robert Belgard,
        # not Robert Stinson" names both.
        if full and all(wholes[_full(p).lower()] == 1 for p in full):
            return None
        return full or rivals or None
    matched = [
        person
        for person in people
        if spoken & {word.lower() for word in WORDS.findall(_name(person))}
    ]
    if len(matched) > 1:
        return matched
    if matched:
        return None
    pointed = spoken & {p.value for p in Pronoun}
    if pointed and not _new_name(words):
        could = [p for p in people if _fits(pointed, p)]
        if len(could) != 1:
            # With nobody in the record there is no one to pick, so the
            # statement goes in as given (R-0884).
            return could or people or None
    return None


def _says(lowered: str, name: str) -> bool:
    return " ".join(WORDS.findall(name)).lower() in lowered


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


def _choices(could: list[dict], data: dict) -> list[dict]:
    names = called(data, full=True)
    return [{"id": person["id"], "name": names[str(person["id"])]} for person in could]


def write(coding, statement, said: str, chosen=None, model=None) -> dict:
    """One coding turn. Returns the rows it wrote and the rows the diagram
    refused, or the people to pick from instead. `chosen` is the person the
    coder tapped when they were asked which."""
    turn_id = uuid.uuid4().hex
    record = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    people = record.get("people") or []
    about = ""
    if chosen is None:
        could = unclear(said, people)
        if could is not None:
            choices = _choices(could, record)
            _log.info(f"Scribe asked which person: {choices}")
            return _result([], [], [], turn_id, choices)
    else:
        person = next((p for p in people if str(p["id"]) == str(chosen)), None)
        if person is None:
            raise ValueError("that person is not in this diagram")
        about = CHOSEN.format(line=f"{person['id']} {_full(person)}")
    toolbox = adapter.scribe_toolbox(
        coding.diagram_id, coding.user_id, statement.id, turn_id
    )
    coach = adapter.Metered(
        coding.user_id,
        coding.diagram_id,
        turn_id,
        adapter.Purpose.Scribe,
        model=model or adapter.scribe_model(MODEL),
    )
    system = adapter.scribe_prompt(adapter.render_record(coding.diagram_id))
    messages = [
        {
            "role": "user",
            "content": TURN.format(
                who=_who(statement), turn=statement.text or "", said=said
            )
            + about,
        }
    ]
    hands = ScribeTools(toolbox)
    refused: list[str] = []
    kept: list[dict] = []
    nudged = False

    for step in range(MAX_STEPS):
        turn = _say(coach, system, messages, hands.tools)
        if not turn.calls:
            if turn.text.strip():
                _log.info(f"Scribe said: {turn.text.strip()!r}")
            # A scribe that stops on words after a refusal is told once what
            # did not go in, so it fixes its own call instead of giving up; one
            # that answers in words before any call is told once to enter it.
            if nudged or (kept and not refused):
                break
            nudged = True
            if turn.blocks:
                messages.append({"role": "assistant", "content": turn.blocks})
            told = AGAIN.format(refused=" ".join(refused)) if refused else ENTER
            messages.append({"role": "user", "content": told})
            continue
        nudged = False
        results = []
        refused = []
        for call in turn.calls:
            text, plain, ran = hands.call(call.name, call.args)
            kept += ran
            if plain:
                refused.append(plain)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": text,
                    "is_error": bool(plain),
                }
            )
        messages.append({"role": "assistant", "content": turn.blocks})
        messages.append({"role": "user", "content": results})
        if refused:
            _log.warning(f"Scribe step {step} was refused: {results}")
    else:
        _log.warning("Scribe ran out of steps")

    adapter.keep_calls(turn_id, statement.discussion_id, coding.diagram_id, kept)
    lines = edit_lines(coding.diagram_id, toolbox.deltas)
    # Every call is committed as it lands, so a scribe that ran out of steps or
    # gave up on a refusal has written part of the sentence; the coder sees
    # those rows and a "not saved" row for each entry the diagram still refused
    # (R-0302: no silent loss). The refusals' own words and the model's speak
    # of how the code works, so they stay in the log (R-0869, R-0883).
    data = adapter.record_of(adapter.diagram_of(coding.diagram_id))
    entered = {line["text"] for line in lines}
    missed = [one for one in tried(data, kept) if one["text"] not in entered]
    if missed:
        _log.warning(f"Scribe left refused: {[c['refusal'] for c in kept if c['refusal']]}")
    return _result(lines, missed, made(toolbox.deltas), turn_id, [])


def _result(lines, refused, made, turn_id, choices) -> dict:
    return {
        "lines": lines,
        "refused": refused,
        "choices": choices,
        "made": made,
        "turn_id": turn_id,
    }


#: The tools whose refused calls are drawn as what they tried to enter.
TRIED = (
    adapter.ToolName.EditPerson,
    adapter.ToolName.EditPairBond,
    adapter.ToolName.EditEvent,
)


def tried(data: dict, kept: list[dict]) -> list[dict]:
    """What the scribe tried to enter and the diagram refused, in the words a
    written row has, leaving out a call a later one of the same kind entered
    after all."""
    out: list[dict] = []
    for at, call in enumerate(kept):
        if not call["refusal"] or call["name"] not in TRIED:
            continue
        if any(_entered(call, later) for later in kept[at + 1 :]):
            continue
        verb = Verb.Add if call["args"].get("id") is None else Verb.Change
        _add(out, {"verb": verb, "text": _tried_words(data, call)})
    return out


def _entered(refused: dict, later: dict) -> bool:
    """Whether a later call entered what a refused one tried: the same item, or
    an event of the same kind once the person the refused one named by a ref
    nothing had added yet is in the record, its title and date put right on
    the way (R-0883, R-0884)."""
    if later["refusal"] or later["name"] != refused["name"]:
        return False
    if _subject(later) == _subject(refused):
        return True
    return (
        _about(refused) == UNADDED
        and _subject(refused)[:2] == _subject(later)[:2]
        and refused["name"] not in (adapter.ToolName.EditPerson, adapter.ToolName.EditPairBond)
    )


#: Who an event is about when the call named a person by a ref nothing in the
#: same answer had added, which is only ever settled by a later call.
UNADDED = "unadded"


def _about(call: dict) -> str:
    args = call["args"]
    about = args.get("child") if args.get("child") is not None else args.get("person")
    return UNADDED if about is None or str(about).startswith("-") else str(about)


def _subject(call: dict) -> tuple:
    """What a call is about, so a refused call and the one that fixed it match:
    the item it changes, or the person, pair or event it adds."""
    args = call["args"]
    if args.get("id") is not None:
        return (call["name"], str(args["id"]))
    if call["name"] == adapter.ToolName.EditPerson:
        return (call["name"], (args.get("name") or "").strip().lower())
    if call["name"] == adapter.ToolName.EditPairBond:
        return (call["name"], _pair_of(args.get("person_a"), args.get("person_b")))
    return (call["name"], _plain(args.get("kind")), _about(call))


def _tried_words(data: dict, call: dict) -> str:
    """A refused call's entry as the diagram would have read it: what was
    already there under its id, with the call's own values over it."""
    people = {str(p.get("id")): p for p in data.get("people") or []}
    names = called(data)
    bonds = {str(b.get("id")): b for b in data.get("pair_bonds") or []}
    events = {str(e.get("id")): e for e in data.get("events") or []}
    args = {key: value for key, value in call["args"].items() if value is not None}
    one = str(args.get("id"))
    if call["name"] == adapter.ToolName.EditPerson:
        return _full({**people.get(one, {}), **args})
    if call["name"] == adapter.ToolName.EditPairBond:
        return _bond_words({**bonds.get(one, {}), **args}, names, events)
    event = {**events.get(one, {}), **args}
    if args.get("date"):
        event["dateTime"] = args["date"]
    if args.get("date_certainty"):
        event["dateCertainty"] = args["date_certainty"]
    # A missing title is often why it was refused; what happened stands in.
    event["title"] = event.get("title") or event.get("description") or _plain(event.get("kind"))
    return _event_words(event, names)


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


def edit_lines(diagram_id: int, deltas: list[dict]) -> list[dict]:
    """What this scribe turn put in the record, one line each."""
    return lines_of(adapter.record_of(adapter.diagram_of(diagram_id)), deltas)


def lines_of(data: dict, deltas: list[dict]) -> list[dict]:
    """The rows one scribe turn's deltas read as on the record as it stands,
    the same when the statement is sent and when the thread is reopened."""
    events = {str(e.get("id")): e for e in data.get("events") or []}
    named = {
        str(event.get(key))
        for event in events.values()
        for key in ("person", "child", "spouse")
        if event.get(key) is not None
    }
    # A person the statement added has a row of its own, as an added person
    # does in the chat; one it only changed has one unless an event names them.
    # One whose parents it changed has one too, saying whose child they now are.
    added = {kind: _added(deltas, kind) for kind in ("person", "pair_bond", "event")}
    parented = {
        str(delta["item_id"])
        for delta in deltas
        if delta.get("item_kind") == "person" and delta.get("field") == "parents"
    }
    rows = _rows(
        data,
        _touched(deltas, "event"),
        [
            one
            for one in _touched(deltas, "person")
            if one in added["person"] or one in parented or one not in named
        ],
        _touched(deltas, "pair_bond"),
        added["pair_bond"],
    )
    return [
        {"verb": Verb.Add if one in added[kind] else Verb.Change, "text": text}
        for (kind, one), text in rows
    ]


#: The kinds that happen to two partners at once, which read as both names.
PAIR_KINDS = ("married", "bonded", "separated", "divorced")


def written(
    data: dict, event_ids, person_ids=(), bond_ids=(), bonds_added=()
) -> list[str]:
    """The record's own words for what a coder wrote, people and pair-bonds
    first, then events: who it is about, what kind of thing it is, and when. A
    marriage reads as two names joined and the year; a person born into a bond
    reads as whose child they are (R-0326, R-0883)."""
    return [text for _, text in _rows(data, event_ids, person_ids, bond_ids, bonds_added)]


def _rows(
    data: dict, event_ids, person_ids=(), bond_ids=(), bonds_added=()
) -> list[tuple[tuple[str, str], str]]:
    """Each row's words with the kind and id of the entry it is, so a row can
    say whether its entry was made or changed."""
    people = {str(p.get("id")): p for p in data.get("people") or []}
    names = called(data)
    events = {str(e.get("id")): e for e in data.get("events") or []}
    bonds = {str(b.get("id")): b for b in data.get("pair_bonds") or []}
    said = {
        _pair_of(events[str(one)].get("person"), events[str(one)].get("spouse"))
        for one in event_ids
        if str(one) in events and _plain(events[str(one)].get("kind")) in PAIR_KINDS
    }
    out: list[tuple[tuple[str, str], str]] = []

    def row(kind: str, one, words: str):
        if all(words != text for _, text in out):
            out.append(((kind, str(one)), words))

    for one in person_ids:
        person = people.get(str(one))
        if person is not None:
            row("person", one, _person_words(person, names, bonds))
    for one in bond_ids:
        bond = bonds.get(str(one))
        if bond is None:
            continue
        pair = _pair_of(bond.get("person_a"), bond.get("person_b"))
        if str(one) in bonds_added or pair not in said:
            row("pair_bond", one, _bond_words(bond, names, events))
    for one in event_ids:
        event = events.get(str(one))
        if event is not None:
            row("event", one, _event_words(event, names))
    return out


def called(data: dict, full: bool = False) -> dict[str, str]:
    """What each person is called on a row: the first name, or the whole name
    where two people share a first name, and then a parent or partner, or else
    their birth year, where the whole names are the same too (R-0883)."""
    people = data.get("people") or []
    first = Counter(_name(p).lower() for p in people)
    out = {
        str(p.get("id")): _full(p) if full or first[_name(p).lower()] > 1 else _name(p)
        for p in people
    }
    whole = dict(out)
    same = Counter(name.lower() for name in out.values())
    for person in people:
        one = str(person.get("id"))
        apart = _linked(person, data, first) if same[whole[one].lower()] > 1 else ""
        out[one] = f"{whole[one]} · {apart}" if apart else whole[one]
    # A link that reads the same for both is no help: the birth year is.
    still = Counter(name.lower() for name in out.values())
    for person in people:
        one = str(person.get("id"))
        born = _born(person, data) if still[out[one].lower()] > 1 else ""
        out[one] = f"{whole[one]} · {born}" if born else out[one]
    return out


def _linked(person: dict, data: dict, first: Counter) -> str:
    """A parent or partner that tells one of two people with the same whole
    name from the other, named so it reads apart itself: by a first name no one
    else has, or else in full; one whose whole name another person has too
    tells nothing."""
    people = {str(p.get("id")): p for p in data.get("people") or []}
    wholes = Counter(_full(p).lower() for p in people.values())
    one = str(person.get("id"))
    links = []
    for bond in data.get("pair_bonds") or []:
        pair = (str(bond.get("person_a")), str(bond.get("person_b")))
        if str(bond.get("id")) == str(person.get("parents")):
            word = CHILD_WORDS.get(_plain(person.get("gender")), "child")
            links += [(word, people[i]) for i in pair if i in people]
        elif one in pair:
            other = pair[1] if pair[0] == one else pair[0]
            links += [("partner", people[other])] if other in people else []
    for word, them in links:
        if first[_name(them).lower()] == 1:
            return f"{word} of {_name(them)}"
    for word, them in links:
        if wholes[_full(them).lower()] == 1:
            return f"{word} of {_full(them)}"
    return ""


def _born(person: dict, data: dict) -> str:
    one = str(person.get("id"))
    for event in data.get("events") or []:
        about = event.get("child") if event.get("child") is not None else event.get("person")
        if _plain(event.get("kind")) == EventKind.Birth.value and str(about) == one:
            year = (adapter.date_text(event.get("dateTime")) or "")[:4]
            if year:
                return f"b. {year}"
    return ""


def _pair_of(a, b) -> tuple:
    return tuple(sorted(str(one) for one in (a, b)))


#: What a person born into a bond is called, by the record's own gender field.
CHILD_WORDS = {"male": "son", "female": "daughter"}


def _person_words(person: dict, names: dict, bonds: dict) -> str:
    """A person, and whose child they are when the record says so."""
    name = names[str(person.get("id"))]
    bond = bonds.get(str(person.get("parents"))) if person.get("parents") else None
    if bond is None:
        return name
    word = CHILD_WORDS.get(_plain(person.get("gender")), "child")
    return f"{name} · {word} of {_both(bond, names)}"


def _joined(names: dict, *ids) -> str:
    return " & ".join(names.get(str(one), "someone") for one in ids)


def _both(bond: dict, names: dict) -> str:
    return _joined(names, bond.get("person_a"), bond.get("person_b"))


def _bond_words(bond: dict, names: dict, events: dict) -> str:
    """A bond nobody wrote an event for: who the two are, whether they married,
    and the year the record has for it."""
    pair = _pair_of(bond.get("person_a"), bond.get("person_b"))
    started = [
        event
        for event in events.values()
        if _plain(event.get("kind")) in ("married", "bonded")
        and _pair_of(event.get("person"), event.get("spouse")) == pair
    ]
    word = "Married" if bond.get("married") else "Together"
    when = _when(*_dated(started[0])) if started else "no date yet"
    return f"{_both(bond, names)} · {word} · {when}"


def _add(out: list, line):
    if line not in out:
        out.append(line)


def _dated(event: dict) -> tuple:
    return event.get("dateTime"), event.get("dateCertainty"), event.get("datePrecision")


def _event_words(event: dict, names: dict) -> str:
    kind = _plain(event.get("kind"))
    said = _what(event, kind)
    if kind in PAIR_KINDS and event.get("spouse") is not None:
        both = _joined(names, event.get("person"), event.get("spouse"))
        return f"{both} · {said} · {_when(*_dated(event))}"
    about = event.get("child")
    if about is None:
        about = event.get("person")
    who = names.get(str(about), "someone") if about is not None else "the family"
    return f"{who} · {said} · {_when(*_dated(event))}"


def _what(event: dict, kind: str) -> str:
    """A noted event or a shift reads by its title (R-0681); any other kind is
    its own name, with its description after it only when that says more."""
    if kind in (EventKind.Noted.value, EventKind.Shift.value):
        return event_title(event)
    word = kind.capitalize()
    description = (event.get("description") or "").strip().removesuffix(".").strip()
    if description.lower() in ("", kind):
        return word
    return f"{word} · {description}"


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _when(value, certainty=None, precision=None) -> str:
    """A day in the words the rest of the app uses: the month and the year,
    or the year alone when that is all the coder said (R-0896).

    An event from before precision was kept, dated the first of January and
    marked approximate, was a year alone too; the month there was never said,
    so it is not read back (R-0326)."""
    written = adapter.date_text(value)
    if not written:
        return "no date yet"
    year, _, rest = written.partition("-")
    month, _, day = rest.partition("-")
    if not month.isdigit() or _plain(precision) == DatePrecision.Year.value:
        return year
    approximate = _plain(certainty) == DateCertainty.Approximate.value
    if approximate and month == "01" and day == "01":
        return year
    return f"{MONTHS[int(month) - 1]} {year}"


def _plain(value) -> str:
    return str(getattr(value, "value", value) or "")


def _name(person: dict) -> str:
    return (person.get("name") or "").strip() or "someone"


def _full(person: dict) -> str:
    whole = " ".join(
        part.strip() for part in (person.get("name"), person.get("last_name")) if part
    )
    return whole.strip() or "someone"


def _touched(deltas: list[dict], kind: str) -> list[str]:
    out: list[str] = []
    for delta in deltas:
        if delta.get("item_kind") != kind or delta.get("item_id") is None:
            continue
        _add(out, str(delta["item_id"]))
    return out


def _added(deltas: list[dict], kind: str) -> set[str]:
    """The items of one kind the deltas made, not just changed: an add is
    logged as the whole item with no field."""
    return {
        str(delta["item_id"])
        for delta in deltas
        if delta.get("item_kind") == kind
        and delta.get("field") is None
        and delta.get("before") is None
        and delta.get("after") is not None
    }
