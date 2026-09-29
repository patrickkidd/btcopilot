"""A person's symptom or anxiety going up, or functioning going down, soon
after they lost or moved away from a relationship, seen more than once. Each
time may be with a different person; what repeats is the person and the
variable. The two events are set side by side for their nearness only, never
as cause and effect."""

import calendar
import datetime
import enum
from dataclasses import dataclass

from btcopilot.recordtext import date_text
from btcopilot.schema import (
    DateCertainty,
    DiagramData,
    EventKind,
    RelationshipKind,
    VariableShift,
    enum_val,
)

WINDOW = datetime.timedelta(days=60)
THRESHOLD = 2

ENDINGS = (EventKind.Separated, EventKind.Divorced)
AWAY = (
    RelationshipKind.Cutoff,
    RelationshipKind.Distance,
    RelationshipKind.Away,
    RelationshipKind.Conflict,
)


class Variable(enum.StrEnum):
    Symptom = "symptom"
    Anxiety = "anxiety"
    Functioning = "functioning"


WORSE = {
    Variable.Symptom: VariableShift.Up,
    Variable.Anxiety: VariableShift.Up,
    Variable.Functioning: VariableShift.Down,
}


@dataclass(frozen=True)
class Firing:
    """(loss event id, variable event id) pairs, oldest first; the last one
    is the pair that made the pattern visible."""

    person: int
    variable: Variable
    pairs: tuple[tuple[int, int], ...]

    @property
    def key(self) -> str:
        return f"{self.person}:{self.variable.value}"


Span = tuple[datetime.date, datetime.date]


def span(event: dict) -> Span | None:
    """The days the event may have fallen on: the day itself when certain, the
    calendar month when approximate. A year-only date (approximate on the
    first of January, R-0326) and an unknown one give no span."""
    written = date_text(event.get("dateTime"))
    certainty = DateCertainty(enum_val(event["dateCertainty"]))
    if not written or certainty is DateCertainty.Unknown:
        return None
    day = datetime.date.fromisoformat(written)
    if certainty is DateCertainty.Certain:
        return day, day
    if (day.month, day.day) == (1, 1):
        return None
    last = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last)


def near(loss: Span, shift: Span) -> bool:
    """Whether the shift may have come within the window after the loss."""
    return shift[1] >= loss[0] and shift[0] <= loss[1] + WINDOW


def _who(event: dict) -> int | None:
    kind = EventKind(enum_val(event["kind"]))
    return event.get("child") if kind.isOffspring() else event.get("person")


def _linked(data: DiagramData, person: int) -> set[int]:
    """Everyone tied to a person by a pair bond, as their parent or as their
    child."""
    bonds = {b["id"]: (b.get("person_a"), b.get("person_b")) for b in data.pair_bonds}
    linked = {
        other
        for a, b in bonds.values()
        if person in (a, b)
        for other in (a, b)
        if other != person
    }
    parents = next((p.get("parents") for p in data.people if p["id"] == person), None)
    linked.update(bonds.get(parents, ()))
    linked.update(
        p["id"] for p in data.people if person in bonds.get(p.get("parents"), ())
    )
    linked.discard(None)
    return linked


def losers(data: DiagramData, event: dict) -> set[int]:
    """The people who lost or moved away from a relationship in this event."""
    kind = EventKind(enum_val(event["kind"]))
    relationship = enum_val(event.get("relationship"))
    if kind in ENDINGS:
        found = {event.get("person"), event.get("spouse")}
    elif kind is EventKind.Death:
        found = _linked(data, event["person"])
    elif relationship and RelationshipKind(relationship) in AWAY:
        found = {event.get("person"), *event.get("relationshipTargets", [])}
    else:
        found = set()
    found.discard(None)
    return found


def _shift(event: dict, variable: Variable) -> VariableShift | None:
    value = enum_val(event.get(variable.value))
    return VariableShift(value) if value else None


def firings(data: DiagramData) -> list[Firing]:
    """Each (person, variable) group once, at the pair that brought it to
    THRESHOLD. A loss and a shift each count toward one pair only, and an
    event never pairs with itself."""
    dated = [(span(e), e) for e in data.events]
    dated = sorted(
        ((s, e) for s, e in dated if s is not None), key=lambda x: (x[0], x[1]["id"])
    )
    losses: dict[int, list[tuple[Span, int]]] = {}
    for s, event in dated:
        for person in losers(data, event):
            losses.setdefault(person, []).append((s, event["id"]))
    found = []
    for person, lost in losses.items():
        for variable, worse in WORSE.items():
            shifts = [
                (s, e["id"])
                for s, e in dated
                if _who(e) == person and _shift(e, variable) is worse
            ]
            pairs = _pairs(lost, shifts)
            if len(pairs) >= THRESHOLD:
                found.append(Firing(person, variable, tuple(pairs[:THRESHOLD])))
    return sorted(found, key=lambda f: (f.person, f.variable))


def _pairs(losses, shifts) -> list[tuple[int, int]]:
    taken: set[int] = set()
    pairs = []
    for loss_span, loss_id in losses:
        for shift_span, shift_id in shifts:
            if shift_id in taken or shift_id == loss_id:
                continue
            if near(loss_span, shift_span):
                taken.add(shift_id)
                pairs.append((loss_id, shift_id))
                break
    return pairs
