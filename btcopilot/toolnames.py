"""What a tool line calls each thing its call touches (R-0478). Taken from the
record when the call is made and kept with it, so a line names what the coach
touched as it was then, even once it is renamed or removed; the page never
shows an id."""

from btcopilot import record
from btcopilot.clusters import _title
from btcopilot.schema import ITEM_COLLECTIONS, DiagramData, EventKind, ItemKind, enum_val
from btcopilot.timeline import _label, _person_label, _who
from btcopilot.toolbox import REMOVABLE, ToolName
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
}


def _event(event: dict, people: dict) -> str:
    kind = enum_val(event.get("kind"))
    if kind in NOUNS:
        return f"{_who(event, people)}'s {NOUNS[kind]}"
    words = (event.get("description") or "").strip()
    if words:
        return words
    if record._moved(event):
        return f"{_person_label(people.get(event.get('person')))}'s {_label(event, people)}"
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


def names(data: DiagramData, tool: str, args: dict) -> dict:
    """What each id in the call's args is called, keyed by the arg, and what
    the call itself touches under `it`: the thing it changes or removes as the
    record holds it, or the thing it adds as its args describe it."""
    people = {p["id"]: p for p in data.people}

    def name(kind: ItemKind, item_id) -> str:
        item = next(
            (
                i
                for i in getattr(data, ITEM_COLLECTIONS[kind])
                if str(i.get("id")) == str(item_id)
            ),
            None,
        )
        return GONE[kind] if item is None else LABELS[kind](item, people)

    out = {
        arg: [name(kind, i) for i in value] if isinstance(value, list) else name(kind, value)
        for arg, value in args.items()
        if (kind := ARGS.get(arg)) and value is not None
    }
    if tool == ToolName.Remove:
        kind = REMOVABLE.get(args.get("item_kind"))
        out["it"] = NO_KIND if kind is None else name(kind, args.get("item_id"))
    elif tool in SUBJECT:
        kind = SUBJECT[tool]
        out["it"] = (
            LABELS[kind](args, people) if args.get("id") is None else name(kind, args["id"])
        )
    return out


def toolcall(data: DiagramData, tool: str, args: dict) -> dict:
    """A tool call as its turn keeps it, named from the record before it runs."""
    return {
        "type": TurnEventKind.ToolCall.value,
        "name": tool,
        "args": args,
        "names": names(data, tool, args),
    }
