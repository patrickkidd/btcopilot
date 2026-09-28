"""A case told as snapshots: the play-by-play for one cluster [R-0563].

The coach tells a cluster in 3 to 6 snapshots through one tool call, or one per
date when the cluster has fewer than three dates. A snapshot
is one date: the events on it, a fact line in the person's own words, and an
optional line starting "My guess:" that holds the coach's hypothesis apart from
the facts. The case makes one point and ends on the coach's question.

Code refuses only what would make the page draw something the record does not
hold: an event outside the cluster, a date that is not its events' date,
snapshots out of order or too few or too many, a guess without its prefix
(R-0074). Judgement (a cause word, a pattern named as fact, a weak point) is
observed in the evals, never blocked here. The page draws each snapshot from
the record itself, so the coach can pick and word but never invent.
"""

import enum
from dataclasses import asdict, dataclass

from btcopilot import recordtext
from btcopilot.schema import DateCertainty, EventKind

GUESS = "My guess:"
FEWEST, MOST = 3, 6


class Tool(enum.StrEnum):
    """The one tool a play-by-play offers the coach."""

    PlayByPlay = "play_by_play"


class Untold(ValueError):
    """A tool call that does not tell the cluster it was asked for."""


class RecordFault(ValueError):
    """The record contradicts itself where the picture has to draw it."""


def faults(data) -> list[str]:
    """Couples the record marries or divorces in an event but does not mark
    married. The drawing never guesses a solid line from an event, so the
    record is corrected first."""
    names = {p.get("id"): p.get("name") for p in data.people}
    unmarried = {
        frozenset((b.get("person_a"), b.get("person_b")))
        for b in data.pair_bonds
        if b.get("married") is False
    }
    return [
        f"{names.get(e.get('person'))} and {names.get(e.get('spouse'))} have a "
        f"{e['kind']} event but are not marked married"
        for e in data.events
        if e.get("kind") in (EventKind.Married.value, EventKind.Divorced.value)
        and frozenset((e.get("person"), e.get("spouse"))) in unmarried
    ]


def on(date: str, event: dict) -> bool:
    """Whether an event falls on a snapshot's date, at the event's own date
    certainty: the day when certain, the year when approximate, any date when
    unknown."""
    certainty = DateCertainty(event.get("dateCertainty") or DateCertainty.Certain)
    have = recordtext.date_text(event.get("dateTime")) or ""
    if certainty is DateCertainty.Unknown:
        return True
    if certainty is DateCertainty.Approximate:
        return have[:4] == date[:4]
    return have == date


@dataclass
class Snapshot:
    date: str
    event_ids: list[int]
    fact: str
    guess: str | None


TYPES = {"object": dict, "array": list, "string": str, "integer": int}


def broken(value, schema: dict, where: str = "") -> str | None:
    """The first way `value` breaks `schema` (types and required fields, which
    is all the tool's schema uses), or None. A model's call is checked against
    the tool's own schema before anything reads it."""
    kind = TYPES[schema["type"]]
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        return f"{where or 'the call'} must be {'an' if schema['type'][0] in 'aeiou' else 'a'} {schema['type']}"
    if kind is dict:
        for name in schema.get("required", []):
            if name not in value:
                return f"{where + '.' if where else ''}{name} is required"
        for name, sub in schema.get("properties", {}).items():
            # an optional field left empty is a field not given
            if value.get(name) is not None or name in schema.get("required", []):
                wrong = broken(value[name], sub, f"{where + '.' if where else ''}{name}")
                if wrong:
                    return wrong
    if kind is list:
        for i, item in enumerate(value):
            wrong = broken(item, schema["items"], f"{where}[{i}]")
            if wrong:
                return wrong
    return None


def tool() -> dict:
    return {
        # strict holds every call to the schema; forcing the call with
        # tool_choice is refused by the coach's model, so the prompt asks for it
        "strict": True,
        "name": Tool.PlayByPlay.value,
        "description": (
            "Tell the cluster as 3 to 6 pictures, or one per date when it has fewer than "
            "three dates; one per date, in date order. "
            "Call it exactly once; nothing reaches the person until it is called."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "string"},
                "point": {
                    "type": "string",
                    "description": "The one point, one line of at most 140 characters.",
                },
                "snapshots": {
                    # strict schemas take no size bounds; Case.told holds the count
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "YYYY-MM-DD: the date of the events it covers.",
                            },
                            "event_ids": {"type": "array", "items": {"type": "integer"}},
                            "fact": {"type": "string", "description": "One or two sentences."},
                            "guess": {
                                "type": "string",
                                "description": f'Optional; starts "{GUESS}"',
                            },
                        },
                        "required": ["date", "event_ids", "fact"],
                        "additionalProperties": False,
                    },
                },
                "question": {"type": "string", "description": 'One sentence ending in "?".'},
            },
            "required": ["cluster_id", "point", "snapshots", "question"],
            "additionalProperties": False,
        },
    }


@dataclass
class Case:
    cluster_id: str
    point: str
    snapshots: list[Snapshot]
    question: str

    @classmethod
    def told(cls, args: dict, cluster: dict, events: list[dict]) -> "Case":
        """The case a tool call tells, or `Untold` saying what is wrong with it.
        `events` are the cluster's own."""
        wrong = broken(args, tool()["input_schema"])
        if wrong:
            raise Untold(wrong)
        if str(args.get("cluster_id")) != str(cluster["id"]):
            raise Untold(f"Tell cluster {cluster['id']}, not {args.get('cluster_id')}")
        by_id = {e["id"]: e for e in events}
        raw = args.get("snapshots") or []
        # three pictures at least, unless the cluster has fewer dates than that
        dates = {recordtext.date_text(e.get("dateTime")) for e in events if e.get("dateTime")}
        least = min(FEWEST, len(dates))
        if not least <= len(raw) <= MOST:
            raise Untold(f"Tell it in {least} to {MOST} snapshots, not {len(raw)}")
        snapshots = []
        for n, shot in enumerate(raw, 1):
            ids = shot.get("event_ids") or []
            if not ids:
                raise Untold(f"Snapshot {n} names no event")
            stray = [i for i in ids if i not in by_id]
            if stray:
                raise Untold(f"Snapshot {n} names events not in this cluster: {stray}")
            date = shot.get("date") or ""
            off = [i for i in ids if not on(date, by_id[i])]
            if off:
                raise Untold(f"Snapshot {n} is dated {date or 'nothing'} but events {off} are not on it")
            guess = (shot.get("guess") or "").strip() or None
            if guess and not guess.startswith(GUESS):
                raise Untold(f'Snapshot {n}: a guess starts "{GUESS}"')
            snapshots.append(Snapshot(shot["date"], ids, shot["fact"].strip(), guess))
        named = [i for s in snapshots for i in s.event_ids]
        if len(named) != len(set(named)):
            raise Untold("Name each event in one snapshot only")
        # one snapshot per date: events that share one are told together
        by_date: dict[str, list[Snapshot]] = {}
        for s in snapshots:
            by_date.setdefault(s.date, []).append(s)
        for date, same in by_date.items():
            if len(same) > 1:
                ids = [i for s in same for i in s.event_ids]
                raise Untold(
                    f"Events {', '.join(map(str, ids[:-1]))} and {ids[-1]} share {date}: "
                    "put them in one snapshot, with one fact line covering them"
                )
        order = [s.date for s in snapshots]
        if order != sorted(order):
            raise Untold("Put the snapshots in date order")
        return cls(
            cluster_id=str(cluster["id"]),
            point=args["point"].strip(),
            snapshots=snapshots,
            question=args["question"].strip(),
        )

    def asdict(self) -> dict:
        return asdict(self)
