"""The three things the coach must have before it goes on: the person's first
name, last name and birth date (Patrick, 2026-09-21). They live on the person's
own entry in the record, and are mirrored onto the account so the preferences
page shows the same values."""

import datetime
import enum

from btcopilot.schema import DEFAULT_SUBJECT_NAME, DiagramData, EventKind

PLACEHOLDER_NAME = "User"
# the person the chat app makes the user on a diagram that has none yet
FIRST_PERSON_ID = 1


class Required(enum.StrEnum):
    FirstName = "first name"
    LastName = "last name"
    BirthDate = "birth date"


def own(data: DiagramData) -> dict | None:
    """The person's own entry: the primary person, which the chat app creates
    as person 1 named "User" on the first session."""
    return data.primary_person() or next(
        (p for p in data.people if p.get("id") == 1), None
    )


def own_id(data: DiagramData) -> int:
    """The person's own entry's id, or the one the chat app gives it."""
    person = own(data)
    return person["id"] if person else FIRST_PERSON_ID


def person_of(user, diagram) -> int | None:
    """Who the user is on the case: the person their row names, or None for
    someone who is not in the family, such as a human coach, the owner
    included (FD-387)."""
    row = diagram.access_right(user)
    return row.person_id if row is not None else None


def is_subject(person_id: int | None, data: DiagramData) -> bool:
    """Whether that is the person the family belongs to."""
    return person_id is not None and person_id == own_id(data)


def named(diagram, data: DiagramData) -> str | None:
    """The first name the coach writes about the person the case belongs to
    when nobody on it is that person, or None when it speaks to them as
    "you" (FD-387)."""
    if addressed(diagram, data):
        return None
    return (own(data) or {}).get("name") or DEFAULT_SUBJECT_NAME


def addressed(diagram, data: DiagramData) -> bool:
    """Whether anyone on the case is the person it belongs to, so its case
    report is written to them as "you"."""
    return any(is_subject(row.person_id, data) for row in diagram.access_rights)


def birth(data: DiagramData, person_id: int) -> dict | None:
    return next(
        (
            e
            for e in data.events
            if e.get("kind") == EventKind.Birth.value
            and e.get("child") == person_id
            and e.get("dateTime")
        ),
        None,
    )


def missing(data: DiagramData) -> list[Required]:
    person = own(data) or {}
    gaps = []
    if not person.get("name") or person.get("name") == PLACEHOLDER_NAME:
        gaps.append(Required.FirstName)
    if not person.get("last_name"):
        gaps.append(Required.LastName)
    if not person or birth(data, person["id"]) is None:
        gaps.append(Required.BirthDate)
    return gaps


def mirror(user, data: DiagramData) -> None:
    """The record is what the coach writes; the account row is what the
    preferences page reads. Keep the second equal to the first."""
    person = own(data)
    if not person:
        return
    if person.get("name") and person.get("name") != PLACEHOLDER_NAME:
        user.first_name = person["name"]
    if person.get("last_name"):
        user.last_name = person["last_name"]
    born = birth(data, person["id"])
    if born:
        user.birthdate = datetime.date.fromisoformat(born["dateTime"][:10])
