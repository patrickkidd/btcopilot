from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Size:
    width: float
    height: float


@dataclass
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass
class Person:
    id: int
    center: Point
    boundingRect: Rect
    isMovable: bool
    partners: List[int] = field(default_factory=list)
    parent_a: Optional[int] = None
    parent_b: Optional[int] = None
    birthDateTime: Optional[str] = None


@dataclass
class PersonDelta:
    """
    Sparse person record with only the suggested change to reduce token count.
    """

    id: int
    center: Point


@dataclass
class Diagram:
    people: List[Person] = field(default_factory=list)


@dataclass
class DiagramDelta:
    """
    Sparse diagram record with only the suggested changes to reduce token count.
    """

    people: List[PersonDelta] = field(default_factory=list)
