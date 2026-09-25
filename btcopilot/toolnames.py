"""What a tool line calls each thing its call touches (R-0478). Taken from the
record when the call is made and kept with it, so a line names what the coach
touched as it was then, even once it is renamed or removed; the page never
shows an id."""

from btcopilot import record
from btcopilot.clusters import _title
from btcopilot.extensions import db
from btcopilot.models import Statement
from btcopilot.schema import (
    ITEM_COLLECTIONS,
    DiagramData,
    EventKind,
    EvidenceKind,
    ItemKind,
    enum_val,
)
from btcopilot.timeline import _person_label, _who, event_label
from btcopilot.toolbox import REMOVABLE, ToolName, said_label
from btcopilot.turnlog import TurnEventKind

NOUNS = {
    EventKind.Birth.value: "birth",
    EventKind.Adopted.value: "adoption",
    EventKind.Married.value: "marriage",
    EventKind.Separated.value: "separation",
    EventKind.Divorced.value: "divorce",
    EventKind.Bonded.value: "bond",
    EventKind.Death.value: "death",
}

# An event with no words and nothing that moved, by its kind.
UNSAID = {EventKind.Noted.value: "a note", EventKind.Shift.value: "a shift"}

GONE = {
    ItemKind.Person: "a person no longer in the record",
    ItemKind.Event: "an event no longer in the record",
    ItemKind.PairBond: "a pair bond no longer in the record",
    ItemKind.Cluster: "a cluster no longer in the record",
    ItemKind.Emotion: "a relationship no longer in the record",
    ItemKind.Question: "a question no longer in the record",
}
# What a remove call names when its kind is none the record holds; the toolbox
# refuses the call.
NO_KIND = "something the record has no kind for"

ARGS = {
    **dict.fromkeys(
        (
            "person",
            "spouse",
            "child",
            "person_a",
            "person_b",
            "persons",
            "relationship_targets",
            "relationship_triangles",
        ),
        ItemKind.Person,
    ),
    **dict.fromkeys(
        ("event", "event_a", "event_b", "events", "event_ids", "ids"), ItemKind.Event
    ),
    "cluster": ItemKind.Cluster,
    "parents": ItemKind.PairBond,
}

SUBJECT = {
    ToolName.EditPerson: ItemKind.Person,
    ToolName.EditPairBond: ItemKind.PairBond,
    ToolName.EditEvent: ItemKind.Event,
    ToolName.EditCluster: ItemKind.Cluster,
    ToolName.AddQuestion: ItemKind.Question,
    ToolName.SetQuestion: ItemKind.Question,
    ToolName.AddImpression: ItemKind.Question,
    ToolName.SetImpression: ItemKind.Question,
}


def _event(event: dict, people: dict) -> str:
    kind = enum_val(event.get("kind"))
    if kind in NOUNS:
        return f"{_who(event, people)}'s {NOUNS[kind]}"
    said = event_label(event, people)
    if (event.get("description") or "").strip():
        return said
    if record._moved(event):
        return f"{_person_label(people.get(event.get('person')))}'s {said}"
    return f"{UNSAID.get(kind, 'an event')} about {_who(event, people)}"


LABELS = {
    ItemKind.Person: lambda person, people: _person_label(person),
    ItemKind.Event: _event,
    ItemKind.PairBond: lambda bond, people: (
        f"{_person_label(people.get(bond.get('person_a')))} & "
        f"{_person_label(people.get(bond.get('person_b')))}'s pair bond"
    ),
    ItemKind.Cluster: lambda cluster, people: (
        f"the cluster {_title(cluster)}" if _title(cluster) else "an unnamed cluster"
    ),
    ItemKind.Emotion: lambda emotion, people: (
        f"the relationship between {_person_label(people.get(emotion.get('person')))}"
        f" and {_person_label(people.get(emotion.get('target')))}"
    ),
    ItemKind.Question: lambda question, people: question["text"],
}


def label(data: DiagramData, kind: ItemKind, item_id) -> str:
    """What the record calls one of its items, or that it is gone."""
    item = next(
        (i for i in getattr(data, ITEM_COLLECTIONS[kind]) if str(i.get("id")) == str(item_id)),
        None,
    )
    return GONE[kind] if item is None else LABELS[kind](item, {p["id"]: p for p in data.people})


MESSAGE_GONE = "a message no longer in the record"


def evidence_label(data: DiagramData, one: dict) -> str:
    """What an impression rests on, as a chip names it. A stored message keeps
    the label it was given, since its session can be deleted."""
    if one["kind"] != EvidenceKind.Statement:
        return label(data, ItemKind(one["kind"]), one["id"])
    if "label" in one:
        return one["label"]
    statement = db.session.get(Statement, int(one["id"]))
    return MESSAGE_GONE if statement is None else said_label(statement)


def names(data: DiagramData, tool: str, args: dict) -> dict:
    """What each id in the call's args is called, keyed by the arg, and what
    the call itself touches under `it`: the thing it changes or removes as the
    record holds it, or the thing it adds as its args describe it."""
    people = {p["id"]: p for p in data.people}

    out = {
        arg: [label(data, kind, i) for i in value] if isinstance(value, list) else label(data, kind, value)
        for arg, value in args.items()
        if (kind := ARGS.get(arg)) and value is not None
    }
    if args.get("evidence"):
        out["evidence"] = [evidence_label(data, one) for one in args["evidence"]]
    if tool == ToolName.Remove:
        kind = REMOVABLE.get(args.get("item_kind"))
        out["it"] = NO_KIND if kind is None else label(data, kind, args.get("item_id"))
    elif tool in SUBJECT:
        kind = SUBJECT[tool]
        out["it"] = (
            LABELS[kind](args, people) if args.get("id") is None else label(data, kind, args["id"])
        )
    return out


def _unasked(data: DiagramData, tool: str, args: dict) -> bool:
    """The call touches a question the person has never been asked, and does
    not ask it."""
    asks = args.get("state") in record.SHOWN
    if tool in (ToolName.AddQuestion, ToolName.AddImpression):
        return not asks
    if tool in (ToolName.SetQuestion, ToolName.SetImpression):
        question = next((q for q in data.questions if q["id"] == str(args.get("id"))), None)
        return question is not None and question["asked_at"] is None and not asks
    return False


def toolcall(data: DiagramData, tool: str, args: dict) -> dict:
    """A tool call as its turn keeps it, named from the record before it runs.
    The words of a question kept for later stay on the server: the call is kept
    without them, so neither the live page nor the thread ever gets them."""
    named = names(data, tool, args)
    if _unasked(data, tool, args):
        args = {key: value for key, value in args.items() if key != "text"}
        named.pop("it")
    return {
        "type": TurnEventKind.ToolCall.value,
        "name": tool,
        "args": args,
        "names": named,
    }
