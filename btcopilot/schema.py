"""
The JSON data schema for diagram files stored on the server and apps.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ItemDetailsData:
    itemPos: Optional[dict[str, float]] = None


@dataclass
class ChildOfData:
    person: int
    parents: Optional[int] = None
    multipleBirth: Optional[int] = None


@dataclass
class PersonData:
    id: int
    kind: str = "Person"
    itemPos: Optional[dict[str, float]] = None
    name: str = ""
    middleName: str = ""
    lastName: str = ""
    nickName: str = ""
    birthName: str = ""
    alias: str = ""
    primary: bool = False
    deceased: bool = False
    deceasedReason: str = ""
    adopted: bool = False
    gender: str = "male"
    diagramNotes: str = ""
    notes: str = ""
    showLastName: bool = True
    showMiddleName: bool = True
    showNickName: bool = True
    showVariableColors: bool = True
    hideDetails: bool = False
    hideDates: bool = False
    hideVariables: bool = False
    color: Optional[str] = None
    itemOpacity: Optional[float] = None
    size: int = 3
    bigFont: bool = False
    layers: list[int] = field(default_factory=list)
    marriages: list[int] = field(default_factory=list)
    childOf: dict = field(default_factory=dict)
    detailsText: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class MarriageData:
    id: int
    kind: str = "Marriage"
    person_a: int = 0
    person_b: int = 0
    detailsText: dict = field(default_factory=dict)
    separationIndicator: dict = field(default_factory=dict)
    hideDetails: bool = False
    itemOpacity: Optional[float] = None
    color: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class EventData:
    id: int
    kind: str = "shift"
    dateTime: Optional[str] = None
    endDateTime: Optional[str] = None
    unsure: bool = True
    description: str = ""
    nodal: bool = False
    notes: str = ""
    color: Optional[str] = None
    location: str = ""
    includeOnDiagram: Optional[bool] = None
    person: Optional[int] = None
    spouse: Optional[int] = None
    child: Optional[int] = None
    relationshipTargets: list[int] = field(default_factory=list)
    relationshipTriangles: list[int] = field(default_factory=list)
    relationshipIntensity: int = 3
    dynamicProperties: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class EmotionData:
    id: int
    kind: str
    person: int
    target: Optional[int] = None
    event: Optional[int] = None
    itemOpacity: Optional[float] = None
    color: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class LayerData:
    id: int
    kind: str = "Layer"
    name: str = ""
    color: Optional[str] = None
    itemProperties: dict[int, dict] = field(default_factory=dict)
    storeGeometry: bool = False
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class LayerItemData:
    id: int
    kind: str
    itemPos: Optional[dict[str, float]] = None
    color: Optional[str] = None
    itemOpacity: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class MultipleBirthData:
    id: int
    kind: str = "MultipleBirth"
    children: list[int] = field(default_factory=list)
    parents: Optional[int] = None
    tags: list[str] = field(default_factory=list)
    loggedDateTime: Optional[str] = None


@dataclass
class SceneData:
    version: str
    versionCompat: str
    name: str = ""
    pruned: bool = False
    people: list[dict] = field(default_factory=list)
    marriages: list[dict] = field(default_factory=list)
    emotions: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    layers: list[dict] = field(default_factory=list)
    layerItems: list[dict] = field(default_factory=list)
    multipleBirths: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    currentDateTime: Optional[str] = None
    showAliases: bool = False
