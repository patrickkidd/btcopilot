"""The coding pass of a desktop file import: the model reads the text the file
holds and codes what it states happened, by the coach's own rules for what goes
in the record, so imports and conversations code alike [Oracle: R-0860]. What
the file's author coded by hand stays as it is [Oracle: R-0859]; a shift that
cannot be coded becomes a noted event, so nothing is lost and nothing is
guessed [Oracle: R-0868].

Each person's part is their events, the text on them, their bonds and their
own notes, with the names of their relatives so a move can name whom it was
aimed at; people share a call, in file order, up to PER_CALL items. Each answer is checked by the record's own rules before any of it
is kept; a refused one is said by name in the decisions."""

import collections
import copy
import enum
import re
import types
from dataclasses import dataclass, field

from btcopilot import prompts, record
from btcopilot.fdledger import Decision
from btcopilot.llmutil import (
    OutputTruncatedError,
    Unreadable,
    dataclass_to_json_schema,
    gemini_structured_sync,
)
from btcopilot.models import Author
from btcopilot.prompts import ToolText
from btcopilot.schema import (
    DateCertainty,
    EventKind,
    ItemKind,
    NotedFact,
    RelationshipKind,
    VariableShift,
    plain_title,
)

PROMPT = "import_coding"
# On a person, pair-bond, event or the diagram: what the importer leaves for
# this pass, as the file held it [Oracle: R-0869, R-0870].
RAW = "fileValues"
VARIABLES = ("symptom", "anxiety", "functioning")
MOVES = ("relationshipTargets", "relationshipTriangles")
# What makes a shift a shift; who a move was aimed at alone does not.
CODED = (*VARIABLES, "relationship")
HAND = (*CODED, *MOVES)
WORDED = (EventKind.Shift.value, EventKind.Noted.value)
BY_CHILD = (EventKind.Birth.value, EventKind.Adopted.value)
LINKS = ("person", "spouse", "child", *MOVES)
TEXTS = ("description", "notes")
MEANINGS = (
    ToolText.Title,
    ToolText.Description,
    ToolText.Notes,
    ToolText.Item,
    ToolText.Symptom,
    ToolText.Anxiety,
    ToolText.Functioning,
    ToolText.Relationship,
    ToolText.RelationshipTargets,
    ToolText.RelationshipTriangles,
)
# What a noted event left by a refused answer is called until someone codes it.
UNCODED = "Not coded yet"
WHOLE = "the whole diagram"
ROOM = 4096
PER_ITEM = 512
# Events and texts in one call; a person with more has a call alone.
PER_CALL = 24


class Todo(enum.StrEnum):
    Code = "code"
    Reword = "reword"
    Title = "title"
    Read = "read"


@dataclass
class Coded:
    kind: str = ""
    title: str = ""
    description: str | None = None
    symptom: str | None = None
    anxiety: str | None = None
    functioning: str | None = None
    relationship: str | None = None
    relationshipTargets: list[str] = field(default_factory=list)
    relationshipTriangles: list[str] = field(default_factory=list)
    item: str | None = None
    quote: str = ""


@dataclass
class Coding(Coded):
    event: str = ""


@dataclass
class Addition(Coded):
    source: str = ""
    person: str = ""
    dateTime: str | None = None
    dateCertainty: str = ""


@dataclass
class Answer:
    codings: list[Coding] = field(default_factory=list)
    additions: list[Addition] = field(default_factory=list)


@dataclass
class Batch:
    who: str
    people: list[int]
    events: list[dict]
    todo: dict[str, Todo]
    texts: dict[str, str]

    @property
    def size(self) -> int:
        return len(self.events) + len(self.texts)


class Refused(Exception):
    pass


def ask(prompt: str, response_format, schema: dict, limit: int):
    """The app's cheap side-call model, the one cluster grouping uses."""
    return gemini_structured_sync(
        prompt, response_format, schema=schema, limit=limit
    ).value


def _said(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.lower()))


def _quoted(quote: str, text: str) -> bool:
    said = _words(quote)
    return bool(said) and said in _words(text)


def labels(data: dict) -> dict[int, str]:
    """Each person's name as the model is to give it back, made unique by id
    where two people share one."""
    named = {
        p["id"]: " ".join(filter(None, (p.get("name"), p.get("last_name"))))
        or f"person {p['id']}"
        for p in data["people"]
    }
    count = collections.Counter(named.values())
    return {
        pid: f"{name} ({pid})" if count[name] > 1 else name
        for pid, name in named.items()
    }


def _texts(prefix: str, item: dict) -> list[tuple[str, str]]:
    found = [*((key, item.get(key)) for key in TEXTS), *(item.get(RAW) or {}).items()]
    return [(f"{prefix} {key}", str(text)) for key, text in found if text]


def _owner(event: dict):
    if event["kind"] in BY_CHILD and event.get("child") is not None:
        return event["child"]
    return (
        event.get("person") if event.get("person") is not None else event.get("spouse")
    )


def _todo(data: dict, event: dict) -> Todo:
    kind = event["kind"]
    if kind == EventKind.Shift.value and (
        not any(event.get(name) for name in CODED)
        or event.get(RAW)
        or (event.get("relationship") and not event.get("relationshipTargets"))
        or (
            event.get("relationship") in record.TRIANGLES
            and not event.get("relationshipTriangles")
        )
    ):
        return Todo.Code
    if any(
        record.linked_name(data, event, event.get(key) or "")
        for key in ("title", "description")
    ):
        return Todo.Reword
    if kind in WORDED and plain_title(event.get("title")) is None:
        return Todo.Title
    return Todo.Read


def _kin(data: dict, pid: int, events: list[dict]) -> list[int]:
    people = {p["id"]: p for p in data["people"]}
    bonds = data["pair_bonds"]

    def parents(x):
        bond = next((b for b in bonds if b["id"] == people[x].get("parents")), None)
        return [bond["person_a"], bond["person_b"]] if bond else []

    def partners(x):
        return [
            b[side]
            for b in bonds
            if x in (b["person_a"], b["person_b"])
            for side in ("person_a", "person_b")
        ]

    def children(x):
        own = {b["id"] for b in bonds if x in (b["person_a"], b["person_b"])}
        return [p["id"] for p in people.values() if p.get("parents") in own]

    def siblings(x):
        return [
            p["id"]
            for p in people.values()
            if people[x].get("parents") and p.get("parents") == people[x]["parents"]
        ]

    found = [pid, *parents(pid), *siblings(pid), *partners(pid), *children(pid)]
    for parent in [p for p in parents(pid) if p in people]:
        found += parents(parent) + siblings(parent)
    for partner in [p for p in partners(pid) if p in people]:
        found += parents(partner)
    for event in events:
        for key in LINKS:
            value = event.get(key)
            found += value if isinstance(value, list) else [value]
    return list(dict.fromkeys(x for x in found if x in people))


def batches(data: dict) -> list[Batch]:
    """One per person with text or events to code, and one for the diagram's
    own text and any event with nobody on it."""
    people = {p["id"] for p in data["people"]}
    owned = collections.defaultdict(list)
    for event in data["events"]:
        owned[_owner(event)].append(event)
    bonded = collections.defaultdict(list)
    for bond in data["pair_bonds"]:
        bonded[
            bond["person_a"] if bond["person_a"] is not None else bond["person_b"]
        ].append(bond)
    named = labels(data)

    def batch(who, kin, events, texts) -> Batch | None:
        for event in events:
            texts += _texts(f"event {event['id']}", event)
        todo = {str(e["id"]): _todo(data, e) for e in events}
        if not texts and all(t is Todo.Read for t in todo.values()):
            return None
        return Batch(who, kin, events, todo, dict(texts))

    found = [
        batch(
            named[p["id"]],
            _kin(data, p["id"], owned[p["id"]]),
            owned[p["id"]],
            _texts(f"person {p['id']}", p)
            + [t for b in bonded[p["id"]] for t in _texts(f"pair-bond {b['id']}", b)],
        )
        for p in data["people"]
    ]
    loose = [e for pid, events in owned.items() if pid not in people for e in events]
    found.append(batch(WHOLE, list(people), loose, _texts("diagram", data)))
    return [b for b in found if b is not None]


def _joined(found: list[Batch]) -> Batch:
    return Batch(
        "; ".join(b.who for b in found),
        list(dict.fromkeys(pid for b in found for pid in b.people)),
        [e for b in found for e in b.events],
        {eid: todo for b in found for eid, todo in b.todo.items()},
        {source: text for b in found for source, text in b.texts.items()},
    )


def calls(data: dict) -> list[Batch]:
    """The people's batches packed in file order into calls of at most
    PER_CALL items, one person's never split; the diagram's own stays alone."""
    found = batches(data)
    people = [b for b in found if b.who != WHOLE]
    whole = [b for b in found if b.who == WHOLE]
    packed, current = [], []
    for batch in people:
        if current and sum(b.size for b in current) + batch.size > PER_CALL:
            packed.append(_joined(current))
            current = []
        current.append(batch)
    if current:
        packed.append(_joined(current))
    return packed + whole


def answer_schema(batch: Batch, named: dict[int, str]) -> dict:
    schema = dataclass_to_json_schema(Answer)
    people = [named[pid] for pid in batch.people]
    asked = [eid for eid, todo in batch.todo.items() if todo is not Todo.Read]
    for key in ("codings", "additions"):
        props = schema["properties"][key]["items"]["properties"]
        props["kind"]["enum"] = list(WORDED)
        for name in VARIABLES:
            props[name]["enum"] = [v.value for v in VariableShift]
        props["relationship"]["enum"] = [r.value for r in RelationshipKind]
        props["item"]["enum"] = [f.value for f in NotedFact]
        for name in MOVES:
            props[name]["items"]["enum"] = people
    coding = schema["properties"]["codings"]["items"]
    coding["properties"]["event"]["enum"] = asked
    coding["required"] = ["event", "kind", "title", "quote"]
    addition = schema["properties"]["additions"]["items"]
    addition["properties"]["person"]["enum"] = people
    addition["properties"]["source"]["enum"] = list(batch.texts)
    addition["properties"]["dateCertainty"]["enum"] = [c.value for c in DateCertainty]
    addition["required"] = [
        "source",
        "person",
        "kind",
        "title",
        "description",
        "dateCertainty",
        "quote",
    ]
    if not asked:
        del schema["properties"]["codings"]
    if not batch.texts:
        del schema["properties"]["additions"]
    return schema


def _when(event: dict) -> str:
    if not event.get("dateTime"):
        return "no date"
    return f"{event['dateTime']}, {event.get('dateCertainty') or DateCertainty.Certain.value}"


def _line(event: dict, todo: Todo, named: dict[int, str]) -> str:
    def who(value):
        ids = value if isinstance(value, list) else [value]
        return ", ".join(named.get(x, f"person {x}") for x in ids)

    head = f"- event {event['id']} · {event['kind']} · {_when(event)} · to do: {todo}"
    links = [
        f"{key}: {who(event[key])}" for key in LINKS if event.get(key) not in (None, [])
    ]
    hand = [f"{key} {event[key]}" for key in CODED if event.get(key)]
    lines = [head, f"  {'; '.join(links)}" if links else None]
    if event.get("title"):
        lines.append(f"  title: {event['title']}")
    if hand:
        lines.append(f"  coded by hand: {', '.join(hand)}")
    return "\n".join(line for line in lines if line)


def prompt(batch: Batch, named: dict[int, str]) -> str:
    meanings = prompts.tool_meanings()
    return prompts.files().text(
        PROMPT,
        who=batch.who,
        people="\n".join(f"- {named[pid]}" for pid in batch.people),
        events="\n".join(
            _line(e, batch.todo[str(e["id"])], named) for e in batch.events
        )
        or "(none)",
        texts="\n\n".join(
            f"[{source}]\n{text}" for source, text in batch.texts.items()
        ),
        meanings="\n".join(f"- {name}: {meanings[name]}" for name in MEANINGS),
    )


def _ids(names: list[str], ids: dict[str, int]) -> list[int]:
    unknown = [name for name in names if name not in ids]
    if unknown:
        raise Refused(
            f"it named {', '.join(unknown)}, who is not among this person's relatives."
        )
    return [ids[name] for name in names]


def _check(data: dict, event: dict, added: bool) -> None:
    """The record's own rules, on the diagram as it would be with this event."""
    trial = {
        **data,
        "events": [e for e in data["events"] if e["id"] != event["id"]] + [event],
    }
    delta = {
        "item_kind": ItemKind.Event.value,
        "item_id": event["id"],
        "field": None,
        "before": None if added else event,
        "after": event,
    }
    try:
        record.validate(trial, [delta], Author.Pro, undoing=True)
    except record.Invalid as invalid:
        raise Refused(invalid.plain) from invalid


def _coded(
    data: dict, event: dict, todo: Todo, answer: Coding, ids: dict[str, int]
) -> dict:
    """The fields the answer changes on the event. Only an event asked to be
    coded takes variables, and only where the file left them empty."""
    hand = {name for name in HAND if event.get(name)}
    kind = event["kind"]
    changes = {}
    if kind in WORDED and answer.kind != kind:
        if answer.kind not in WORDED or todo is not Todo.Code:
            raise Refused(f"it called a {kind} event {answer.kind!r}.")
        if hand & set(CODED):
            raise Refused("it made a noted event of a shift the file coded by hand.")
        changes["kind"] = answer.kind
    title = event.get("title") or ""
    if changes.get("kind", kind) in WORDED and (
        plain_title(title) is None or record.linked_name(data, event, title)
    ):
        changes["title"] = answer.title
    description = event.get("description") or ""
    if record.linked_name(data, event, description):
        if not answer.description:
            raise Refused("it gave no description without the name.")
        changes["notes"] = "\n\n".join(filter(None, (event.get("notes"), description)))
        changes["description"] = answer.description
    elif answer.description and description.strip().lower() in record.PLACEHOLDERS:
        changes["description"] = answer.description
    if todo is Todo.Code:
        for name in (*VARIABLES, "relationship", "item"):
            value = getattr(answer, name)
            if value and name not in hand and not event.get(name):
                changes[name] = value
        for name in MOVES:
            if getattr(answer, name) and name not in hand:
                changes[name] = _ids(getattr(answer, name), ids)
    return changes


def _fallback(data: dict, event: dict, todo: Todo) -> dict:
    """What a refused or missing answer leaves: a shift nobody coded by hand
    becomes a noted event, and anything that still needs words gets them
    without a name it links."""
    changes = {}
    if (
        todo is Todo.Code
        and event["kind"] == EventKind.Shift.value
        and not any(event.get(name) for name in CODED)
    ):
        changes["kind"] = EventKind.Noted.value
    worded = changes.get("kind", event["kind"]) in WORDED
    description = event.get("description") or ""
    if record.linked_name(data, event, description):
        changes["notes"] = "\n\n".join(filter(None, (event.get("notes"), description)))
        description = ""
        changes["description"] = UNCODED if worded else None
    if not worded:
        return changes
    title = event.get("title") or ""
    if plain_title(title) is None or record.linked_name(data, event, title):
        changes["title"] = plain_title(description) or UNCODED
    if description.strip().lower() in record.PLACEHOLDERS:
        changes["description"] = changes["title"] if "title" in changes else title
    return changes


def _moveless(event: dict, named: dict[int, str], decisions: list) -> None:
    """Whom a move nobody could complete was aimed at stays with the file's
    values, by name: the record names them only on a relationship move."""
    if event.get("relationship"):
        return
    for name in MOVES:
        said = ", ".join(named[pid] for pid in event.pop(name, None) or [])
        if not said:
            continue
        event.setdefault(RAW, {})[name] = said
        decisions.append(
            Decision(
                f"event {event['id']}",
                name,
                said,
                "",
                "With no relationship move to aim it, the name stays with the file's values.",
            )
        )


def _change(decisions: list, event: dict, changes: dict, reason: str) -> None:
    for name, value in changes.items():
        decisions.append(
            Decision(
                f"event {event['id']}",
                name,
                _said(event.get(name)),
                _said(value),
                reason,
            )
        )
        if value is None:
            event.pop(name, None)
        else:
            event[name] = value


def _added(
    data: dict, batch: Batch, answer: Addition, ids: dict[str, int], new_id: int
) -> dict:
    if answer.source not in batch.texts:
        raise Refused(
            f"it read a text called {answer.source!r}, which is not in the file."
        )
    if not _quoted(answer.quote, batch.texts[answer.source]):
        raise Refused(
            f"the words it quoted, {answer.quote!r}, are not in {answer.source}."
        )
    if answer.kind not in WORDED:
        raise Refused(f"a new event is a shift or a noted event, not {answer.kind!r}.")
    if not answer.dateTime and answer.dateCertainty != DateCertainty.Unknown.value:
        raise Refused(f"it gave no date but called the date {answer.dateCertainty!r}.")
    event = {
        "id": new_id,
        "kind": answer.kind,
        "person": _ids([answer.person], ids)[0],
        "title": answer.title,
        "description": answer.description,
        "notes": answer.quote,
        "dateTime": answer.dateTime,
        "dateCertainty": answer.dateCertainty,
        **{
            name: getattr(answer, name) for name in (*VARIABLES, "relationship", "item")
        },
        **{name: _ids(getattr(answer, name), ids) for name in MOVES},
    }
    event = {key: value for key, value in event.items() if value not in (None, "", [])}
    _check(data, event, added=True)
    return event


def _answer(batch: Batch, named: dict[int, str], model) -> tuple[Answer | None, str]:
    try:
        return (
            model(
                prompt(batch, named),
                Answer,
                answer_schema(batch, named),
                ROOM + PER_ITEM * batch.size,
            ),
            "",
        )
    except OutputTruncatedError:
        return None, "the model's answer ran past its length limit."
    except Unreadable:
        return None, "the model's answer was not the JSON asked for."


def _batch(
    data: dict, batch: Batch, named: dict[int, str], model, ids_of, decisions: list
) -> None:
    ids = {named[pid]: pid for pid in batch.people}
    answer, failed = _answer(batch, named, model)
    events = {str(e["id"]): e for e in batch.events}
    refused = {
        eid: failed or "the model gave no coding for it."
        for eid, todo in batch.todo.items()
        if todo is not Todo.Read
    }
    text = "\n".join(batch.texts.values())
    done = set()
    for coding in answer.codings if answer else []:
        event = events.get(coding.event)
        try:
            if event is None or batch.todo[coding.event] is Todo.Read:
                raise Refused(
                    f"it coded event {coding.event}, which it was not asked to code."
                )
            if coding.event in done:
                raise Refused(f"it coded event {coding.event} twice.")
            if not _quoted(coding.quote, text):
                raise Refused(
                    f"the words it quoted, {coding.quote!r}, are not in the file's text."
                )
            changes = _coded(data, event, batch.todo[coding.event], coding, ids)
            _check(data, {**event, **changes}, added=False)
        except Refused as why:
            if coding.event in refused:
                refused[coding.event] = str(why)
            else:
                decisions.append(
                    Decision(
                        f"event {coding.event}",
                        "",
                        "",
                        "",
                        f"The model's coding was refused: {why}",
                    )
                )
            continue
        refused.pop(coding.event)
        done.add(coding.event)
        _change(decisions, event, changes, f'The file\'s text says "{coding.quote}".')
    for eid, why in refused.items():
        event = events[eid]
        changes = _fallback(data, event, batch.todo[eid])
        reason = f"The model's coding was refused: {why}"
        if changes.get("kind") == EventKind.Noted.value:
            reason += " It is kept as a noted event, so nothing is lost."
        if changes:
            _change(decisions, event, changes, reason)
        else:
            decisions.append(Decision(f"event {eid}", "", "", "", reason))
        _moveless(event, named, decisions)
    for addition in answer.additions if answer else []:
        # Said on the item whose text it was read in, so the ledger shows it there.
        item, _, name = addition.source.rpartition(" ")
        try:
            event = _added(data, batch, addition, ids, record.next_id(ids_of))
        except Refused as why:
            decisions.append(
                Decision(
                    item,
                    name,
                    "",
                    "",
                    f"An event the model read in {addition.source} was refused: {why}",
                )
            )
            continue
        data["events"].append(event)
        decisions.append(
            Decision(
                item,
                name,
                "",
                f"a new {event['kind']} event: {event['title']}",
                f'Added from {addition.source}, which says "{addition.quote}".',
            )
        )


def code(data: dict, model=ask) -> tuple[dict, list[Decision]]:
    """`model` takes the prompt, the answer's dataclass, its schema and its
    token limit, and returns the answer, as Metered.structured does."""
    data = copy.deepcopy(data)
    data.setdefault("pair_bonds", [])
    named = labels(data)
    ids_of = types.SimpleNamespace(
        people=data["people"],
        events=data["events"],
        pair_bonds=data["pair_bonds"],
        emotions=data.get("emotions") or [],
        lastItemId=data.get("lastItemId") or 0,
    )
    decisions: list[Decision] = []
    for batch in calls(data):
        _batch(data, batch, named, model, ids_of, decisions)
    return data, decisions
