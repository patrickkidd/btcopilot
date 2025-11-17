import enum
from dataclasses import dataclass, field, asdict as dataclass_asdict, fields, MISSING
from typing import get_origin, get_args


class PDPValidationError(ValueError):
    """Raised when PDP deltas fail validation."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(
            f"PDP validation failed with {len(errors)} error(s): {'; '.join(errors)}"
        )


def asdict(obj):
    """Convert dataclass to dict with enums as their string values."""
    return dataclass_asdict(
        obj,
        dict_factory=lambda items: {
            k: v.value if isinstance(v, enum.Enum) else v for k, v in items
        },
    )


def compute_spouses_for_person(person_id: int, events: list) -> list[int]:
    """
    Compute spouse list from Events (Bonded, Married, Birth, Adopted, etc.)
    Returns unique list of spouse IDs for this person.
    """
    spouses = set()

    for event in events:
        event_obj = event if hasattr(event, "kind") else from_dict(Event, event)
        if event_obj.kind and event_obj.kind.isPairBond():
            if event_obj.person == person_id and event_obj.spouse:
                spouses.add(event_obj.spouse)
            elif event_obj.spouse == person_id and event_obj.person:
                spouses.add(event_obj.person)

    return list(spouses)


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
class PairBond:
    id: int | None = None
    person_a: int | None = None
    person_b: int | None = None
    confidence: float | None = None


@dataclass
class Person:
    id: int | None = None
    name: str | None = None
    last_name: str | None = None
    parents: int | None = None
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
    relationshipTriangles: list[int] = field(default_factory=list)
    functioning: VariableShift | None = None

    # meta
    confidence: float | None = None  # PDP


@dataclass
class PDPDeltas:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pair_bonds: list[PairBond] = field(default_factory=list)
    delete: list[int] = field(default_factory=list)


@dataclass
class PDP:
    people: list[Person] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    pair_bonds: list[PairBond] = field(default_factory=list)


@dataclass
class DiagramData:
    people: list[dict] = field(
        default_factory=list
    )  # Raw dicts from pickle (READ-ONLY, may contain QtCore objects)
    events: list[dict] = field(
        default_factory=list
    )  # Raw dicts from pickle (READ-ONLY, may contain QtCore objects)
    pair_bonds: list[dict] = field(
        default_factory=list
    )  # Raw dicts from pickle (READ-ONLY, may contain QtCore objects)
    pdp: PDP = field(default_factory=PDP)
    last_id: int = field(default=0)

    def _next_id(self) -> int:
        self.last_id += 1
        return self.last_id

    def add_person(self, person: Person) -> None:
        person.id = self._next_id()
        self.people.append(asdict(person))

    def add_event(self, event: Event) -> None:
        event.id = self._next_id()
        self.events.append(asdict(event))

    def add_pair_bond(self, pair_bond: PairBond) -> None:
        pair_bond.id = self._next_id()
        self.pair_bonds.append(asdict(pair_bond))

    def commit_pdp_items(self, item_ids: list[int]) -> dict[int, int]:
        """
        Returns mapping from old PDP IDs (negative) to new diagram IDs
        (positive)
        """
        for item_id in item_ids:
            if item_id >= 0:
                raise ValueError(f"Item ID {item_id} must be negative (PDP item)")

        all_item_ids = self._get_transitive_pdp_references(item_ids)

        id_mapping = {}
        for old_id in sorted(all_item_ids):
            id_mapping[old_id] = self._next_id()

        pdp_people_map = {p.id: p for p in self.pdp.people if p.id is not None}
        pdp_events_map = {e.id: e for e in self.pdp.events}
        pdp_pair_bonds_map = {
            pb.id: pb for pb in self.pdp.pair_bonds if pb.id is not None
        }

        for old_id in all_item_ids:
            if old_id in pdp_pair_bonds_map:
                pair_bond = pdp_pair_bonds_map[old_id]
                new_pair_bond = self._remap_pair_bond_ids(pair_bond, id_mapping)
                self.pair_bonds.append(asdict(new_pair_bond))

        for old_id in all_item_ids:
            if old_id in pdp_people_map:
                person = pdp_people_map[old_id]
                new_person = self._remap_person_ids(person, id_mapping)
                self.people.append(asdict(new_person))

        for old_id in all_item_ids:
            if old_id in pdp_events_map:
                event = pdp_events_map[old_id]
                new_event = self._remap_event_ids(event, id_mapping)
                self.events.append(asdict(new_event))

        self.pdp.people = [p for p in self.pdp.people if p.id not in all_item_ids]
        self.pdp.events = [e for e in self.pdp.events if e.id not in all_item_ids]
        self.pdp.pair_bonds = [
            pb for pb in self.pdp.pair_bonds if pb.id not in all_item_ids
        ]

        return id_mapping

    def _get_transitive_pdp_references(self, item_ids: list[int]) -> set[int]:
        from btcopilot.pdp import get_all_pdp_item_ids

        pdp_item_ids = get_all_pdp_item_ids(self.pdp)
        pdp_people_map = {p.id: p for p in self.pdp.people if p.id is not None}
        pdp_events_map = {e.id: e for e in self.pdp.events}
        pdp_pair_bonds_map = {
            pb.id: pb for pb in self.pdp.pair_bonds if pb.id is not None
        }

        visited = set()
        to_visit = list(item_ids)

        while to_visit:
            item_id = to_visit.pop()

            if item_id in visited:
                continue

            if item_id not in pdp_item_ids:
                if item_id < 0:
                    raise ValueError(f"PDP item {item_id} not found in PDP")
                continue

            visited.add(item_id)

            if item_id in pdp_people_map:
                person = pdp_people_map[item_id]
                if person.parents and person.parents < 0:
                    to_visit.append(person.parents)

            if item_id in pdp_pair_bonds_map:
                pair_bond = pdp_pair_bonds_map[item_id]
                if pair_bond.person_a and pair_bond.person_a < 0:
                    to_visit.append(pair_bond.person_a)
                if pair_bond.person_b and pair_bond.person_b < 0:
                    to_visit.append(pair_bond.person_b)

            if item_id in pdp_events_map:
                event = pdp_events_map[item_id]
                if event.person and event.person < 0:
                    to_visit.append(event.person)
                if event.spouse and event.spouse < 0:
                    to_visit.append(event.spouse)
                if event.child and event.child < 0:
                    to_visit.append(event.child)
                for target in event.relationshipTargets:
                    if target < 0:
                        to_visit.append(target)
                for person_id in event.relationshipTriangles:
                    if person_id < 0:
                        to_visit.append(person_id)

        return visited

    def _remap_person_ids(self, person: Person, id_mapping: dict[int, int]) -> Person:
        from dataclasses import replace

        return replace(
            person,
            id=id_mapping[person.id],
            parents=(
                id_mapping.get(person.parents, person.parents)
                if person.parents
                else None
            ),
        )

    def _remap_event_ids(self, event: Event, id_mapping: dict[int, int]) -> Event:
        from dataclasses import replace

        return replace(
            event,
            id=id_mapping[event.id],
            person=id_mapping.get(event.person, event.person) if event.person else None,
            spouse=id_mapping.get(event.spouse, event.spouse) if event.spouse else None,
            child=id_mapping.get(event.child, event.child) if event.child else None,
            relationshipTargets=[
                id_mapping.get(t, t) for t in event.relationshipTargets
            ],
            relationshipTriangles=[
                id_mapping.get(person_id, person_id)
                for person_id in event.relationshipTriangles
            ],
        )

    def _remap_pair_bond_ids(
        self, pair_bond: PairBond, id_mapping: dict[int, int]
    ) -> PairBond:
        from dataclasses import replace

        return replace(
            pair_bond,
            id=id_mapping[pair_bond.id],
            person_a=(
                id_mapping.get(pair_bond.person_a, pair_bond.person_a)
                if pair_bond.person_a
                else None
            ),
            person_b=(
                id_mapping.get(pair_bond.person_b, pair_bond.person_b)
                if pair_bond.person_b
                else None
            ),
        )

    @staticmethod
    def create_with_defaults() -> "Diagram":
        diagramData = DiagramData()

        # Add default User person (ID 1) - matches default chat_user_speaker
        user_person = Person(id=1, name="User")
        diagramData.people.append(asdict(user_person))

        # Add default Assistant person (ID 2) - matches default chat_ai_speaker
        assistant_person = Person(id=2, name="Assistant")
        diagramData.people.append(asdict(assistant_person))

        # Ensure last_id accounts for the default people
        diagramData.last_id = max(diagramData.last_id, 2)

        return diagramData
