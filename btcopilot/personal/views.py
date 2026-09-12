"""The show tool's closed set of views [Oracle: R-0075].

Anything deterministic is a tool call with parameters, and every parameter must
resolve to stored data or the call fails. There is no free drawing: the model
picks a view kind and names record ids, and the picture does the rest.
"""

import datetime
import enum

from btcopilot.schema import DiagramData


class ViewKind(enum.StrEnum):
    Triangle = "triangle"
    Span = "span"
    Compare = "compare"
    Sequence = "sequence"
    Cluster = "cluster"


PARAMS = {
    ViewKind.Triangle: ["persons"],
    ViewKind.Span: ["start", "end"],
    ViewKind.Compare: ["event_a", "event_b"],
    ViewKind.Sequence: ["events"],
    ViewKind.Cluster: ["cluster"],
}


def _ids(items: list[dict]) -> set[str]:
    return {
        str(i["id"]) for i in items if isinstance(i, dict) and i.get("id") is not None
    }


def _person(person_id, data: DiagramData) -> int:
    if str(person_id) not in _ids(data.people):
        raise ValueError(f"No person {person_id} in the record")
    return int(person_id)


def _event(event_id, data: DiagramData) -> int:
    if str(event_id) not in _ids(data.events):
        raise ValueError(f"No event {event_id} in the record")
    return int(event_id)


def _date(value: str) -> str:
    return datetime.date.fromisoformat(str(value)).isoformat()


def build(kind: ViewKind, params: dict, data: DiagramData) -> dict:
    """A view the picture can draw, or ValueError naming what did not resolve."""
    kind = ViewKind(kind)
    missing = [name for name in PARAMS[kind] if params.get(name) is None]
    if missing:
        raise ValueError(f"A {kind.value} view needs {', '.join(missing)}")

    if kind is ViewKind.Triangle:
        persons = list(params["persons"])
        if len(persons) != 3:
            raise ValueError("A triangle view takes exactly three people")
        built = {"persons": [_person(p, data) for p in persons]}
    elif kind is ViewKind.Span:
        start, end = _date(params["start"]), _date(params["end"])
        if end < start:
            raise ValueError(f"A span ends before it starts: {start}..{end}")
        built = {"start": start, "end": end}
    elif kind is ViewKind.Compare:
        built = {
            "event_a": _event(params["event_a"], data),
            "event_b": _event(params["event_b"], data),
        }
    elif kind is ViewKind.Sequence:
        events = list(params["events"])
        if not events:
            raise ValueError("A sequence view needs at least one event")
        built = {"events": [_event(e, data) for e in events]}
    else:
        cluster = str(params["cluster"])
        if cluster not in _ids(data.clusters):
            raise ValueError(f"No cluster {cluster} in the record")
        built = {"cluster": cluster}

    return {"kind": kind.value, **built}
