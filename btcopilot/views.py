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


class Unshowable(Exception):
    """A view that does not resolve. The reason is for the coach; `plain` says
    it to the person reading the thread, with no ids."""

    def __init__(self, reason: str, plain: str):
        super().__init__(reason)
        self.plain = plain


NO_PERSON = "Someone it named is not in the record."
NO_EVENT = "An event it named is not in the record."
NO_CLUSTER = "The cluster it named is not in the record."

PARAMS = {
    ViewKind.Triangle: ["persons"],
    ViewKind.Span: ["start", "end"],
    ViewKind.Compare: ["event_a", "event_b"],
    ViewKind.Sequence: ["events"],
    ViewKind.Cluster: ["cluster"],
}
UNNAMED = {
    ViewKind.Triangle: "No people were named.",
    ViewKind.Span: "It did not give a start and an end date.",
    ViewKind.Compare: "It did not name two events.",
    ViewKind.Sequence: "No events were named.",
    ViewKind.Cluster: "No cluster was named.",
}


def _ids(items: list[dict]) -> set[str]:
    return {
        str(i["id"]) for i in items if isinstance(i, dict) and i.get("id") is not None
    }


def _person(person_id, data: DiagramData) -> int:
    if str(person_id) not in _ids(data.people):
        raise Unshowable(f"No person {person_id} in the record", NO_PERSON)
    return int(person_id)


def _event(event_id, data: DiagramData) -> int:
    if str(event_id) not in _ids(data.events):
        raise Unshowable(f"No event {event_id} in the record", NO_EVENT)
    return int(event_id)


def _date(value: str) -> str:
    try:
        return datetime.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise Unshowable(f"{value} is not a date: use YYYY-MM-DD", "A date could not be read.")


def build(kind: ViewKind, params: dict, data: DiagramData) -> dict:
    """A view the picture can draw, or Unshowable naming what did not resolve."""
    try:
        kind = ViewKind(kind)
    except ValueError:
        raise Unshowable(f"There is no {kind} view", "There is no such picture.")
    missing = [name for name in PARAMS[kind] if params.get(name) is None]
    if missing:
        raise Unshowable(f"A {kind.value} view needs {', '.join(missing)}", UNNAMED[kind])

    if kind is ViewKind.Triangle:
        persons = list(params["persons"])
        if len(persons) != 3:
            raise Unshowable(
                "A triangle view takes exactly three people",
                "A triangle takes exactly three people.",
            )
        built = {"persons": [_person(p, data) for p in persons]}
    elif kind is ViewKind.Span:
        start, end = _date(params["start"]), _date(params["end"])
        if end < start:
            raise Unshowable(
                f"A span ends before it starts: {start}..{end}",
                "The end date is before the start date.",
            )
        built = {"start": start, "end": end}
    elif kind is ViewKind.Compare:
        built = {
            "event_a": _event(params["event_a"], data),
            "event_b": _event(params["event_b"], data),
        }
    elif kind is ViewKind.Sequence:
        events = list(params["events"])
        if not events:
            raise Unshowable(
                "A sequence view needs at least one event", UNNAMED[ViewKind.Sequence]
            )
        built = {"events": [_event(e, data) for e in events]}
    else:
        cluster = str(params["cluster"])
        if cluster not in _ids(data.clusters):
            raise Unshowable(f"No cluster {cluster} in the record", NO_CLUSTER)
        built = {"cluster": cluster}

    return {"kind": kind.value, **built}
