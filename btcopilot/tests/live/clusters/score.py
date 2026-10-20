"""One try of cluster detection scored against a case's expected clusters
[Oracle: R-0856].

Pairing reuses the F1 suite's cluster match (matching.py): a stored cluster
pairs with an expected one when the events they share are at least
CLUSTER_OVERLAP (half) of the larger one's events, each used once. Over the
pairs: cluster precision, recall and F1, and the F1 of the member events
within the paired clusters. An expected cluster may be met by the app's period
or the person's, since a period the person names over the same days is stored
as theirs and the app's then gives way [Oracle: R-0853].

A key Patrick signed may hold two more kinds of period [Oracle: R-0856,
R-0857]. A cluster marked `hypothesis` counts neither way: a
stored cluster that pairs with it is neither a hit nor an extra, one left out is
not a miss, and its opening is not checked. A period the case lists in
`notClusters` is one he said is not a cluster: a stored cluster that pairs with
it is an extra in cluster F1 and a miss named beside it.

The rules that are not F1 are checked beside it, each miss named:
- A6: no app period is named by the person's trouble, and none fell back to
  the plain name the code gives when the answer twice did [Oracle: R-0376].
- A9: no period opens at an event of unknown date, and a period expected to
  hold one person's shifts holds only that person's [Oracle: R-0850].
- The person's own periods come back as theirs, and no app period shares their
  days [Oracle: R-0853].
- Voice and cause: no cluster the app made speaks as the person outside
  their quoted words, and none gives a cause, in its name, summary or
  sentence, by the server's own word lists (record.py) [Oracle: R-0860,
  R-0864].
- Openings: the expected opening of each paired cluster is the one stored;
  reported always, required only where a case's criterion says so.
"""

import datetime
import enum
from dataclasses import dataclass, field

from btcopilot.clusters import (
    ModelCluster,
    judge,
    overlapping,
    plain_name,
    span_of,
    trouble_in,
    trouble_words,
    unsure,
)
from btcopilot.record import caused, ided, voiced
from btcopilot.matching import (
    F1Metrics,
    calculate_f1_from_counts,
    match_clusters,
)
from btcopilot.schema import (
    Cluster,
    ClusterSource,
    DiagramData,
    Event,
    from_dict,
    parse_date,
)


class Rule(enum.StrEnum):
    TroubleName = "A6 named by the person's trouble"
    UnknownOpening = "A9 opens at an unknown date"
    RunOf = "A9 not the one person's shifts"
    Theirs = "the person's period missing or changed"
    Voice = "speaks as the person"
    Cause = "gives a cause"
    Id = "id violations"
    Opening = "opening differs"
    NotACluster = "a period the case says is not a cluster"


@dataclass
class Expected:
    """A cluster of the key; `hypothesis` marks one scored neither way."""

    name: str
    eventIds: list[int]
    opening: int | None = None
    runOf: int | None = None
    hypothesis: bool = False


@dataclass
class NotCluster:
    """A period the key says is not a cluster: a try that stores it misses."""

    name: str
    eventIds: list[int]


@dataclass
class Theirs:
    """A period the person named, by the years their words give."""

    name: str
    startYear: int
    endYear: int


@dataclass
class Score:
    clusters: F1Metrics
    members: F1Metrics
    pairs: list[tuple[Cluster, Expected]]
    misses: list[tuple[Rule, str]] = field(default_factory=list)
    hypotheses: list[tuple[Cluster, Expected]] = field(default_factory=list)

    def count(self, rule: Rule) -> int:
        return sum(r is rule for r, _ in self.misses)

    def missed(self, rules: frozenset[Rule]) -> list[str]:
        return [why for rule, why in self.misses if rule in rules]

    @property
    def openings(self) -> tuple[int, int]:
        """Paired clusters whose expected opening was stored, of those with one."""
        named = [(c, e) for c, e in self.pairs if e.opening is not None]
        return sum(c.openingEventId == e.opening for c, e in named), len(named)


def events(data: DiagramData) -> list[Event]:
    return [from_dict(Event, chunk) for chunk in data.events]


def within(data: DiagramData, period: Theirs) -> list[int]:
    """Every dated event inside the years, as a period of the person's is
    stored [Oracle: R-0853]."""
    first = datetime.date(period.startYear, 1, 1)
    last = datetime.date(period.endYear, 12, 31)
    return [
        e.id
        for e in events(data)
        if parse_date(e.dateTime) and first <= parse_date(e.dateTime) <= last
    ]


def _as_cluster(index: int, name: str, ids: list[int]) -> Cluster:
    return Cluster(id=f"x{index}", title=name, summary="", eventIds=ids)


def ours_of(stored: list[Cluster]) -> list[Cluster]:
    return [c for c in stored if c.source is ClusterSource.Model]


def score(
    stored: list[Cluster],
    expected: list[Expected],
    data: DiagramData,
    theirs: list[Theirs] = (),
    not_clusters: list[NotCluster] = (),
) -> Score:
    every = {e.id: e for e in events(data)}
    when = {i: parse_date(e.dateTime) for i, e in every.items() if e.dateTime}
    identity = {i: i for i in every}
    key = [*expected, *not_clusters]
    wanted = [_as_cluster(n, e.name, e.eventIds) for n, e in enumerate(key)]
    matched = match_clusters(stored, wanted, identity)
    by_id = {w.id: e for w, e in zip(wanted, key)}
    paired = [(c, by_id[w.id]) for c, w in matched.matched_pairs]
    pairs = [(c, e) for c, e in paired if isinstance(e, Expected) and not e.hypothesis]
    held = [(c, e) for c, e in paired if isinstance(e, Expected) and e.hypothesis]
    ruled_out = [(c, e) for c, e in paired if isinstance(e, NotCluster)]
    left_out = [
        w
        for w in matched.gt_unmatched
        if isinstance(by_id[w.id], Expected) and not by_id[w.id].hypothesis
    ]
    clusters = calculate_f1_from_counts(
        len(pairs), len(matched.ai_unmatched) + len(ruled_out), len(left_out)
    )
    tp = sum(len(set(c.eventIds) & set(e.eventIds)) for c, e in pairs)
    members = calculate_f1_from_counts(
        tp,
        sum(len(c.eventIds) for c, _ in pairs) - tp,
        sum(len(e.eventIds) for _, e in pairs) - tp,
    )
    result = Score(clusters=clusters, members=members, pairs=pairs, hypotheses=held)
    for c, e in ruled_out:
        result.misses.append(
            (Rule.NotACluster, f"{c.name!r} is {e.name!r}, not a cluster")
        )

    told = trouble_words(data)
    for c in stored:
        if c.source is not ClusterSource.Model:
            continue
        if trouble_in(c.name, told):
            result.misses.append(
                (Rule.TroubleName, f"{c.name!r} tells {trouble_in(c.name, told)}")
            )
        elif c.name == plain_name(ModelCluster(eventIds=c.eventIds), when):
            result.misses.append(
                (
                    Rule.TroubleName,
                    f"{c.name!r} is the plain name the code fell back to",
                )
            )
    for c in ours_of(stored):
        for field_, text in (
            ("name", c.name),
            ("summary", c.summary),
            ("reason", c.reason),
        ):
            if text and voiced(text):
                result.misses.append(
                    (Rule.Voice, f"{field_} {text!r} says {voiced(text)!r}")
                )
            if text and caused(text):
                result.misses.append(
                    (Rule.Cause, f"{field_} {text!r} says {caused(text)!r}")
                )
            if text and ided(text):
                result.misses.append(
                    (Rule.Id, f"{field_} {text!r} holds {ided(text)!r}")
                )
    for c in stored:
        opening = every.get(c.openingEventId)
        if opening is not None and unsure(opening):
            result.misses.append(
                (Rule.UnknownOpening, f"{c.name!r} opens at event {opening.id}")
            )
    for c, e in pairs:
        if e.runOf is not None:
            run = judge({"eventIds": c.eventIds}, data).runOf
            if run != e.runOf:
                result.misses.append(
                    (Rule.RunOf, f"{c.name!r}: the shifts of {run}, not of {e.runOf}")
                )
        if e.opening is not None and c.openingEventId != e.opening:
            result.misses.append(
                (
                    Rule.Opening,
                    f"{c.name!r} opens at {c.openingEventId}, expected {e.opening}",
                )
            )

    hers = [c for c in stored if c.source is ClusterSource.User]
    ours = [c for c in stored if c.source is ClusterSource.Model]
    periods = [_as_cluster(n, p.name, within(data, p)) for n, p in enumerate(theirs)]
    found = match_clusters(hers, periods, identity)
    for missing in found.gt_unmatched:
        result.misses.append(
            (Rule.Theirs, f"{missing.title!r} is not stored as theirs")
        )
    for c, _ in found.matched_pairs:
        days = span_of([when[i] for i in c.eventIds])
        for other in ours:
            if overlapping(days, span_of([when[i] for i in other.eventIds])):
                result.misses.append(
                    (Rule.Theirs, f"{other.name!r} shares days with theirs {c.name!r}")
                )
    return result
