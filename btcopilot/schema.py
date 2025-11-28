import enum
import logging
import datetime
from dataclasses import (
    dataclass,
    field,
    asdict as dataclass_asdict,
    fields,
    MISSING,
    replace,
)
from typing import get_origin, get_args
from PyQt5.QtCore import QDate, QDateTime, QTime

_log = logging.getLogger(__name__)

BLANK_DATE_TEXT = "--/--/----"
BLANK_TIME_TEXT = "--:-- pm"


def validatedDateTimeText(dateText, timeText=None):
    """mm/dd/yyyy. useTime is a QDateTime to take the time from."""
    import dateutil.parser

    ret = None
    if len(dateText) == 8 and "/" in dateText:  # 05111980
        try:
            x = int(dateText)
        except ValueError:
            x = None
        if x is not None:
            mm = int(dateText[:2])
            dd = int(dateText[2:4])
            yyyy = int(dateText[4:8])
            ret = QDateTime(QDate(yyyy, mm, dd))
    if ret is None and dateText not in (None, "", BLANK_DATE_TEXT):
        # normal route
        try:
            dt = dateutil.parser.parse(dateText)
        except ValueError:
            ret = QDateTime()
        if ret is None:
            ret = QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    if timeText not in (None, "", BLANK_TIME_TEXT):
        try:
            dt2 = dateutil.parser.parse(timeText)
        except ValueError:
            dt2 = None
        if dt2:
            if not ret:
                ret = QDateTime.currentDateTime()
            ret.setTime(
                QTime(dt2.hour, dt2.minute, dt2.second, int(dt2.microsecond / 1000))
            )
    return ret


def pyDateTimeString(dateTime: datetime.datetime) -> str:
    if isinstance(dateTime, str):
        import dateutil.parser

        dateTime = dateutil.parser.parse(dateTime)
    return dateTime.strftime("%m/%d/%Y %I:%M %p")


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

    if hasattr(data, "__dataclass_fields__"):
        # Already a dataclass instance, return as-is
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
    id: int | None = None
    # Scene-facing collections (dict chunks compatible with Scene.read/write)
    people: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    pair_bonds: list[dict] = field(default_factory=list)
    emotions: list[dict] = field(default_factory=list)
    multipleBirths: list[dict] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)
    layerItems: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    pruned: list[dict] = field(default_factory=list)
    uuid: str | None = None
    name: str | None = None
    tags: list[str] = field(default_factory=list)
    loggedDateTime: list[str] = field(default_factory=list)
    masterKey: str | None = None
    alias: str | None = None
    version: str | None = None
    versionCompat: str | None = None
    # PDP (negative-id staging)
    pdp: PDP = field(default_factory=PDP)
    lastItemId: int = field(default=0)
    # Scene UI/display properties (for canonical diagram mutation support)
    readOnly: bool = False
    contributeToResearch: bool = False
    useRealNames: bool = False
    password: str | None = None
    requirePasswordForRealNames: bool = False
    showAliases: bool = False
    hideNames: bool = False
    hideToolBars: bool = False
    hideEmotionalProcess: bool = False
    hideEmotionColors: bool = False
    hideDateSlider: bool = False
    hideVariablesOnDiagram: bool = False
    hideVariableSteadyStates: bool = False
    exclusiveLayerSelection: bool = True
    storePositionsInLayers: bool = False
    currentDateTime: object = None  # Serialized QDateTime
    scaleFactor: float | None = None
    pencilColor: object = None  # Serialized color
    eventProperties: list = field(default_factory=list)
    legendData: dict | None = None

    def clear(self) -> None:
        self.people = []
        self.events = []
        self.pair_bonds = []
        self.emotions = []
        self.multipleBirths = []
        self.layers = []
        self.layerItems = []
        self.items = []
        self.pruned = []
        self.uuid = None
        self.name = None
        self.version = None
        self.versionCompat = None
        self.pdp = PDP()
        self.lastItemId = 0
        self.readOnly = False
        self.contributeToResearch = False
        self.useRealNames = False
        self.password = None
        self.requirePasswordForRealNames = False
        self.showAliases = False
        self.hideNames = False
        self.hideToolBars = False
        self.hideEmotionalProcess = False
        self.hideEmotionColors = False
        self.hideDateSlider = False
        self.hideVariablesOnDiagram = False
        self.hideVariableSteadyStates = False
        self.exclusiveLayerSelection = True
        self.storePositionsInLayers = False
        self.currentDateTime = None
        self.scaleFactor = None
        self.pencilColor = None
        self.eventProperties = []
        self.legendData = None
        self.id = None
        self.tags = []
        self.loggedDateTime = None
        self.masterKey = None
        self.alias = None

    def _next_id(self) -> int:
        self.lastItemId += 1
        return self.lastItemId

    def add_person(self, person: Person) -> None:
        person.id = self._next_id()
        self.people.append(asdict(person))
        _log.info(f"Added person with new ID {person.id}")

    def add_event(self, event: Event) -> None:
        event.id = self._next_id()
        self.events.append(asdict(event))
        _log.info(f"Added event with new ID {event.id}")

    def add_pair_bond(self, pair_bond: PairBond) -> None:
        pair_bond.id = self._next_id()
        chunk = asdict(pair_bond)
        self.pair_bonds.append(chunk)
        _log.info(f"Added pair bond with new ID {pair_bond.id}")

    def commit_pdp_items(self, item_ids: list[int]) -> dict[int, int]:
        """
        Returns mapping from old PDP IDs (negative) to new diagram IDs
        (positive)
        """
        for item_id in item_ids:
            if item_id >= 0:
                raise ValueError(f"Item ID {item_id} must be negative (PDP item)")

        # Create inferred items for Birth/Adopted events before gathering transitive refs
        self._create_inferred_birth_items(item_ids)

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
                chunk = asdict(new_pair_bond)
                _log.info(
                    f"Committed pair bond with new ID {new_pair_bond.id}: {new_pair_bond}"
                )
                self.pair_bonds.append(chunk)

        for old_id in all_item_ids:
            if old_id in pdp_people_map:
                person = pdp_people_map[old_id]
                new_person = self._remap_person_ids(person, id_mapping)
                _log.info(f"Committed person with new ID {new_person.id}: {new_person}")
                self.people.append(asdict(new_person))

        for old_id in all_item_ids:
            if old_id in pdp_events_map:
                event = pdp_events_map[old_id]
                new_event = self._remap_event_ids(event, id_mapping)
                _log.info(f"Committed event with new ID {new_event.id}: {new_event}")
                event_dict = asdict(new_event)
                # Convert string dateTime values to QDateTime for Scene compatibility

                for key in ("dateTime", "endDateTime"):
                    value = event_dict.get(key)
                    if value and isinstance(value, str):
                        event_dict[key] = validatedDateTimeText(value)
                self.events.append(event_dict)

        self.pdp.people = [p for p in self.pdp.people if p.id not in all_item_ids]
        self.pdp.events = [e for e in self.pdp.events if e.id not in all_item_ids]
        self.pdp.pair_bonds = [
            pb for pb in self.pdp.pair_bonds if pb.id not in all_item_ids
        ]

        # Update references in remaining PDP items to point to committed IDs
        self.pdp.people = [
            self._remap_person_ids(p, id_mapping) for p in self.pdp.people
        ]
        self.pdp.events = [
            self._remap_event_ids(e, id_mapping) for e in self.pdp.events
        ]
        self.pdp.pair_bonds = [
            self._remap_pair_bond_ids(pb, id_mapping) for pb in self.pdp.pair_bonds
        ]

        return id_mapping

    def reject_pdp_item(self, item_id: int) -> None:
        """Remove a PDP item and cascade-delete any items that reference it."""
        if item_id >= 0:
            raise ValueError(f"Item ID {item_id} must be negative (PDP item)")

        _log.info(f"Rejecting PDP item {item_id} and cascading deletes")
        ids_to_remove = {item_id}

        for event in self.pdp.events:
            if (
                event.person == item_id
                or event.spouse == item_id
                or event.child == item_id
                or item_id in event.relationshipTargets
                or item_id in event.relationshipTriangles
            ):
                _log.info(
                    f"Also removing PDP event {event.id} referencing rejected item {item_id}"
                )
                ids_to_remove.add(event.id)

        for pair_bond in self.pdp.pair_bonds:
            if pair_bond.person_a == item_id or pair_bond.person_b == item_id:
                _log.info(
                    f"Also removing PDP pair bond {pair_bond.id} referencing rejected item {item_id}"
                )
                ids_to_remove.add(pair_bond.id)

        for person in self.pdp.people:
            if person.parents == item_id:
                _log.info(
                    f"Also removing PDP person {person.id} whose parents reference rejected item {item_id}"
                )
                ids_to_remove.add(person.id)

        self.pdp.people = [p for p in self.pdp.people if p.id not in ids_to_remove]
        self.pdp.events = [e for e in self.pdp.events if e.id not in ids_to_remove]
        self.pdp.pair_bonds = [
            pb for pb in self.pdp.pair_bonds if pb.id not in ids_to_remove
        ]

    def _next_pdp_id(self) -> int:
        """Generate next available negative PDP ID."""
        all_ids = (
            [p.id for p in self.pdp.people if p.id is not None]
            + [e.id for e in self.pdp.events]
            + [pb.id for pb in self.pdp.pair_bonds if pb.id is not None]
        )
        return min(all_ids, default=0) - 1

    def _create_inferred_birth_items(self, item_ids: list[int]) -> None:
        """Create inferred parents/children for Birth/Adopted events being committed."""
        pdp_people_map = {p.id: p for p in self.pdp.people if p.id is not None}
        pdp_events_map = {e.id: e for e in self.pdp.events}

        for event_id in item_ids:
            if event_id not in pdp_events_map:
                continue
            event = pdp_events_map[event_id]
            if event.kind not in (EventKind.Birth, EventKind.Adopted):
                continue

            child_name = None
            person_name = None
            if event.child and event.child in pdp_people_map:
                child_name = pdp_people_map[event.child].name or "Child"
            if event.person and event.person in pdp_people_map:
                person_name = pdp_people_map[event.person].name or "Person"

            # Case 1: Birth with only child set - create inferred parents
            if event.child and not event.person and not event.spouse:
                # Create mother first, then father, then pair bond
                # Each call to _next_pdp_id() reads current PDP state
                mother = Person(id=self._next_pdp_id(), name=f"{child_name}'s mother")
                self.pdp.people.append(mother)

                father = Person(id=self._next_pdp_id(), name=f"{child_name}'s father")
                self.pdp.people.append(father)

                pair_bond = PairBond(
                    id=self._next_pdp_id(), person_a=mother.id, person_b=father.id
                )
                self.pdp.pair_bonds.append(pair_bond)

                # Update event references
                event_idx = next(
                    i for i, e in enumerate(self.pdp.events) if e.id == event_id
                )
                self.pdp.events[event_idx] = replace(
                    event, person=mother.id, spouse=father.id
                )

                # Update child's parents
                if event.child in pdp_people_map:
                    child_idx = next(
                        i for i, p in enumerate(self.pdp.people) if p.id == event.child
                    )
                    self.pdp.people[child_idx] = replace(
                        self.pdp.people[child_idx], parents=pair_bond.id
                    )

                _log.info(
                    f"Created inferred parents for {child_name}: mother={mother.id}, father={father.id}, pair_bond={pair_bond.id}"
                )

            # Case 2: Birth with person but no spouse - find or create spouse
            elif event.person and not event.spouse:
                # Check if there's an existing pair bond with this person
                existing_spouse_id = None
                for pb in self.pdp.pair_bonds:
                    if pb.person_a == event.person:
                        existing_spouse_id = pb.person_b
                        break
                    elif pb.person_b == event.person:
                        existing_spouse_id = pb.person_a
                        break

                if existing_spouse_id:
                    spouse_id = existing_spouse_id
                    _log.info(
                        f"Found existing spouse for {person_name} in pair bond: spouse={spouse_id}"
                    )
                else:
                    spouse_id = self._next_pdp_id()
                    spouse = Person(id=spouse_id, name=f"{person_name}'s spouse")
                    self.pdp.people.append(spouse)
                    _log.info(
                        f"Created inferred spouse for {person_name}: spouse={spouse_id}"
                    )

                event_idx = next(
                    i for i, e in enumerate(self.pdp.events) if e.id == event_id
                )
                self.pdp.events[event_idx] = replace(event, spouse=spouse_id)

            # Case 3: Birth with person/spouse but no child - create inferred child
            elif event.person and event.spouse and not event.child:
                child_id = self._next_pdp_id()
                child = Person(id=child_id, name=f"{person_name}'s child")
                self.pdp.people.append(child)

                event_idx = next(
                    i for i, e in enumerate(self.pdp.events) if e.id == event_id
                )
                self.pdp.events[event_idx] = replace(event, child=child_id)

                _log.info(f"Created inferred child for {person_name}: child={child_id}")

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
        return replace(
            person,
            id=id_mapping.get(person.id, person.id),
            parents=(
                id_mapping.get(person.parents, person.parents)
                if person.parents
                else None
            ),
        )

    def _remap_event_ids(self, event: Event, id_mapping: dict[int, int]) -> Event:
        return replace(
            event,
            id=id_mapping.get(event.id, event.id),
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
        return replace(
            pair_bond,
            id=id_mapping.get(pair_bond.id, pair_bond.id),
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
    def create_with_defaults() -> "DiagramData":
        diagram_data = DiagramData()

        # Add default User person (ID 1) - matches default chat_user_speaker
        user_person = Person(id=1, name="User")
        diagram_data.people.append(asdict(user_person))

        # Add default Assistant person (ID 2) - matches default chat_ai_speaker
        assistant_person = Person(id=2, name="Assistant")
        diagram_data.people.append(asdict(assistant_person))

        # Ensure lastItemId accounts for the default people
        diagram_data.lastItemId = max(diagram_data.lastItemId, 2)

        return diagram_data
