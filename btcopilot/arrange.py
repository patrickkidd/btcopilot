from typing import List, Dict, Optional
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
    spouses: List[str] = field(default_factory=list)
    parent_a: Optional[int] = None
    parent_b: Optional[int] = None


@dataclass
class Diagram:
    people: List[Person] = field(default_factory=list)
