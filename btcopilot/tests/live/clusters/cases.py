"""The cluster F1 suite's cases, one JSON file each in cases/ [Oracle: R-0856].

A case holds a fictional diagram, the person's answers to when the most was
going on (the answer's message and the coach's question), the clusters
expected of it (some marked hypothesis, scored neither way), the periods it
says are not clusters, and the periods the person named. Every case whose
person answered is also tried as if they had not, `<name>-unasked`: the same
diagram, all of its expected clusters left to the app.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from btcopilot.clusters import Answer
from btcopilot.schema import DiagramData
from btcopilot.tests.live.clusters.score import Expected, NotCluster, Theirs

HERE = Path(__file__).parent / "cases"


@dataclass
class Case:
    name: str
    about: str
    data: DiagramData
    said: list[Answer]
    expected: list[Expected]
    theirs: list[Theirs]
    not_clusters: list[NotCluster]
    placeholder: bool
    draft: bool


def read(path: Path) -> Case:
    raw = json.loads(path.read_text())
    return Case(
        name=path.stem,
        about=raw["about"],
        data=DiagramData(**raw["diagram"]),
        said=[Answer(**one) for one in raw["said"]],
        expected=[Expected(**one) for one in raw["expected"]],
        theirs=[Theirs(**one) for one in raw["theirs"]],
        not_clusters=[NotCluster(**one) for one in raw.get("notClusters", [])],
        placeholder=bool(raw.get("placeholder")),
        draft=bool(raw.get("draft")),
    )


def unasked(case: Case) -> Case:
    return Case(
        name=f"{case.name}-unasked",
        about=f"{case.about} Tried as if the person had not answered.",
        data=case.data,
        said=[],
        expected=case.expected,
        theirs=[],
        not_clusters=case.not_clusters,
        placeholder=case.placeholder,
        draft=case.draft,
    )


def load() -> list[Case]:
    cases = [read(path) for path in sorted(HERE.glob("*.json"))]
    return cases + [unasked(case) for case in cases if case.said]
