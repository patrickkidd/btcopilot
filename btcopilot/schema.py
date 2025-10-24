import enum
from dataclasses import dataclass, field


class EventKind(enum.Enum):

    Bonded = "bonded"
    Married = "married"
    Birth = "birth"
    Adopted = "adopted"
    Moved = "moved"
    Separated = "separated"
    Divorced = "divorced"

    Shift = "shift"
    Death = "death"

    def isPairBond(self) -> bool:
        return self in (
            self.Bonded,
            self.Married,
            self.Birth,
            self.Adopted,
            self.Moved,
            self.Separated,
            self.Divorced,
        )

    def isOffspring(self) -> bool:
        return self in (self.Birth, self.Adopted)


class RelationshipKind(enum.Enum):
    Fusion = "fusion"
    #
    Conflict = "conflict"
    Distance = "distance"
    Overfunctioning = "overfunctioning"
    Underfunctioning = "underfunctioning"
    Projection = "projection"
    DefinedSelf = "defined-self"
    Toward = "toward"
    Away = "away"
    Inside = "inside"
    Outside = "outside"
    Cutoff = "cutoff"


@dataclass
class Person:
    id: int | None = None
    name: str | None = None
    last_name: str | None = None
    spouses: list[int] = field(default_factory=list)
    # Pair-Bonds are inferred from parent_a, parent_b
    parent_a: int | None = None
    parent_b: int | None = None
    confidence: float | None = None  # PDP


class VariableShift(enum.StrEnum):
    Up = "up"
    Down = "down"
    Same = "same"


@dataclass
class Event:
    id: int
    kind: EventKind
    person: int | None = None
    spouse: int | None = None
    child: int | None = None
    description: str | None = None
    dateTime: str | None = None
    endDateTime: str | None = None
    symptom: VariableShift | None = None
    anxiety: VariableShift | None = None
    relationship: RelationshipKind | None = None
    relationshipTargets: list[int] = field(default_factory=list)
    relationshipTriangles: list[tuple[int, int]] = field(default_factory=list)
    functioning: VariableShift | None = None

    # meta
    confidence: float | None = None  # PDP


@dataclass
class PDPDeltas:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)


@dataclass
class PDP:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


@dataclass
class Diagram:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pdp: PDP = field(default_factory=PDP)
    last_id: int = field(default=0)

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
    def create_with_defaults() -> "Diagram":
        """
        Create a new Diagram instance with default User and Assistant people.
        This ensures speaker mapping always works even after clearing extracted data.
        """
        database = Diagram()

        # Add default User person (ID 1) - matches default chat_user_speaker
        user_person = Person(id=1, name="User")
        database.people.append(user_person)

        # Add default Assistant person (ID 2) - matches default chat_ai_speaker
        assistant_person = Person(id=2, name="Assistant")
        database.people.append(assistant_person)

        # Ensure last_id accounts for the default people
        database.last_id = max(database.last_id, 2)

        return database
