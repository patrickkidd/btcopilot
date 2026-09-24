"""The three things the coach must have before it goes on: the person's first
name, last name and birth date (Patrick, 2026-09-21). They live on the person's
own entry in the record, and are mirrored onto the account so the preferences
page shows the same values."""

import datetime
import enum

from btcopilot.schema import DiagramData, EventKind

PLACEHOLDER_NAME = "User"


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
