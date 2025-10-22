import enum
from typing import Literal, Annotated, Union
from pydantic import BaseModel, Field


class Person(BaseModel):
    id: int | None = None
    name: str | None = None
    spouses: list[int] = Field(default_factory=list)
    offspring: list[int] = Field(default_factory=list)
    confidence: float | None = None  # PDP
    parents: list[int] = Field(default_factory=list)


class Shift(enum.StrEnum):
    Up = "up"
    Down = "down"
    Same = "same"


class Variable(BaseModel):
    shift: Shift | None = None
    rationale: str | None = None  # for auditing


class Anxiety(Variable):
    shift: Shift


class Symptom(Variable):
    shift: Shift


class Functioning(Variable):
    shift: Shift


class RelationshipKind(enum.StrEnum):
    """
    Any action/behavior in relation to another person, namely triangle and one
    of four mechanisms.
    """

    Triangle = "triangle"
    Conflict = "conflict"
    Distance = "distance"
    Reciprocity = "reciprocity"
    ChildFocus = "child-focus"


class Relationship(Variable):
    kind: RelationshipKind


class Mechanism(Relationship):
    movers: list[int] = Field(default_factory=list)
    recipients: list[int] = Field(default_factory=list)


class Distance(Mechanism):
    kind: Literal[RelationshipKind.Distance] = RelationshipKind.Distance


class Conflict(Mechanism):
    kind: Literal[RelationshipKind.Conflict] = RelationshipKind.Conflict


class Reciprocity(Mechanism):
    kind: Literal[RelationshipKind.Reciprocity] = RelationshipKind.Reciprocity


class ChildFocus(Mechanism):
    """
    Recipients should be a single child. Movers should be parent(s).
    """

    kind: Literal[RelationshipKind.ChildFocus] = RelationshipKind.ChildFocus


class Triangle(Relationship):
    kind: Literal[RelationshipKind.Triangle] = RelationshipKind.Triangle
    inside_a: list[int] = Field(default_factory=list)
    inside_b: list[int] = Field(default_factory=list)
    outside: list[int] = Field(default_factory=list)


RelationshipType = Annotated[
    Union[Distance, Conflict, Reciprocity, ChildFocus, Triangle],
    Field(discriminator="kind"),
]


class Event(BaseModel):
    id: int
    description: str | None = None
    dateTime: str | None = None
    people: list[int] = Field(default_factory=list)
    symptom: Symptom | None = None
    anxiety: Anxiety | None = None
    functioning: Functioning | None = None
    relationship: RelationshipType | None = None
    confidence: float | None = None  # PDP


class PDPDeltas(BaseModel):
    people: list[Person] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    delete: list[int] = Field(default_factory=list)


class PDP(BaseModel):
    people: list[Person] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


class Database(BaseModel):
    people: list[Person] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    pdp: PDP = Field(default_factory=PDP)
    last_id: int = Field(default=0)

    def add_person(self, person: Person) -> None:
        person.id = self._next_id()
        self.people.append(person)

    def add_event(self, event: Event) -> None:
        event.id = self._next_id()
        self.events.append(event)

    def _next_id(self) -> int:
        self.last_id += 1
        return self.last_id

    @staticmethod
    def create_with_defaults() -> "Database":
        """
        Create a new Database instance with default User and Assistant people.
        This ensures speaker mapping always works even after clearing extracted data.
        """
        database = Database()

        # Add default User person (ID 1) - matches default chat_user_speaker
        user_person = Person(id=1, name="User")
        database.people.append(user_person)

        # Add default Assistant person (ID 2) - matches default chat_ai_speaker
        assistant_person = Person(id=2, name="Assistant")
        database.people.append(assistant_person)

        # Ensure last_id accounts for the default people
        database.last_id = max(database.last_id, 2)

        return database
