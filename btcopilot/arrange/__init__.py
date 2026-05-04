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


# Algorithm lives in submodules:
#   btcopilot.arrange.layout.layout   — main entry point (deterministic Bowen layout + refine)
#   btcopilot.arrange.refine.refine   — iterative hill-climbing refinement layer
# Dev workflow + decision log: familydiagram/doc/plans/2026-05-02--auto-arrange-layout.md
#
# DO NOT add a `layout` function here — Python's submodule resolution will shadow it
# with the layout.py module once anything imports btcopilot.arrange.layout, breaking
# `from btcopilot.arrange import layout` for callers who got the function first.
