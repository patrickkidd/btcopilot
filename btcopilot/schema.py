import enum
from dataclasses import dataclass, field, asdict as dataclass_asdict, fields, MISSING
from typing import get_origin, get_args

__all__ = [
    "asdict",
    "from_dict",
    "EventKind",
    "RelationshipKind",
    "VariableShift",
    "Person",
    "Event",
    "PDPDeltas",
    "PDP",
    "DiagramData",
]


def asdict(obj):
    """Convert dataclass to dict with enums as their string values."""
    return dataclass_asdict(
        obj,
        dict_factory=lambda items: {
            k: v.value if isinstance(v, enum.Enum) else v for k, v in items
        },
    )


def from_dict(cls, data):
    """
    Reconstruct a dataclass from a dict, converting string values back to enums.

    Usage:
        event = from_dict(Event, {"kind": "shift", "anxiety": "up", ...})
    """
    if data is None:
        return None

    if not hasattr(cls, "__dataclass_fields__"):
        # Not a dataclass, return as-is
        return data

    kwargs = {}
    for field_info in fields(cls):
        field_name = field_info.name
        field_type = field_info.type

        if field_name not in data:
            # Use default if available
            if field_info.default is not MISSING:
                kwargs[field_name] = field_info.default
            elif field_info.default_factory is not MISSING:
                kwargs[field_name] = field_info.default_factory()
            continue

        value = data[field_name]

        # Handle None values
        if value is None:
            kwargs[field_name] = None
            continue

        # Get origin type for generics like list[int]
        origin = get_origin(field_type)

        # Handle list types
        if origin is list:
            args = get_args(field_type)
            if args:
                item_type = args[0]
                if hasattr(item_type, "__dataclass_fields__"):
                    # List of dataclasses
                    kwargs[field_name] = [from_dict(item_type, item) for item in value]
                else:
                    kwargs[field_name] = value
            else:
                kwargs[field_name] = value
        # Handle enum types
        elif isinstance(field_type, type) and issubclass(field_type, enum.Enum):
            kwargs[field_name] = field_type(value)
        # Handle nested dataclasses
        elif hasattr(field_type, "__dataclass_fields__"):
            kwargs[field_name] = from_dict(field_type, value)
        # Handle union types (e.g., int | None)
        elif origin is type(int | None):  # UnionType in Python 3.10+
            # Try each type in the union
            args = get_args(field_type)
            converted = False
            for arg_type in args:
                if arg_type is type(None) and value is None:
                    kwargs[field_name] = None
                    converted = True
                    break
                elif isinstance(arg_type, type) and issubclass(arg_type, enum.Enum):
                    try:
                        kwargs[field_name] = arg_type(value)
                        converted = True
                        break
                    except (ValueError, KeyError):
                        continue
            if not converted:
                kwargs[field_name] = value
        else:
            # Primitive type, use as-is
            kwargs[field_name] = value

    return cls(**kwargs)


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

    def menuLabel(self) -> str:
        labels = {
            self.Bonded: "Bonded",
            self.Married: "Married",
            self.Separated: "Separated",
            self.Divorced: "Divorced",
            self.Moved: "Moved",
            self.Birth: "Birth",
            self.Adopted: "Adopted",
            self.Death: "Death",
            self.Shift: "Shift",
        }
        return labels[self]


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

    def menuLabel(self) -> str:
        labels = {
            # self.Fusion: "Fusion",
            self.Conflict: "Conflict",
            self.Distance: "Distance",
            self.Overfunctioning: "Overfunctioning",
            self.Underfunctioning: "Underfunctioning",
            self.Projection: "Projection",
            self.DefinedSelf: "Defined Self",
            self.Toward: "Toward",
            self.Away: "Away",
            self.Inside: "Triangle to inside",
            self.Outside: "Triangle to outside",
            self.Cutoff: "Cutoff",
        }
        return labels[self]


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
class DiagramData:
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
        diagramData = DiagramData()

        # Add default User person (ID 1) - matches default chat_user_speaker
        user_person = Person(id=1, name="User")
        diagramData.people.append(user_person)

        # Add default Assistant person (ID 2) - matches default chat_ai_speaker
        assistant_person = Person(id=2, name="Assistant")
        diagramData.people.append(assistant_person)

        # Ensure last_id accounts for the default people
        diagramData.last_id = max(diagramData.last_id, 2)

        return diagramData
