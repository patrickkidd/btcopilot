"""Noticing the periods of heightened difficulty in a family's events, each held
as a hypothesis that the family's balance was upset around then by someone
joining or leaving it, or by a key member's functioning changing [Oracle: R-0850].

The rules' runs of events are computed with no model call and go to the model
as a hint only, never stored: a run is seeded at shifts that support a cluster,
anyone's in the family, and every event near them is offered as its possible
opening; which opening mattered is the model's judgement. The model returns the
app's periods as they should now stand, and reads the periods the person named
when asked when the most was going on, each written once as theirs; the
person's own stay as they drew them and are judged against the data like the
app's [Oracle: R-0853]. The code only backstops: three events at least,
nothing over ten years, no name told in the person's trouble, two periods
sharing days become one, and a period that fails is set aside, never deleted.
Fewer than three supporting shifts counts against a period and never refuses
it: the case report's refresh hears the count [Oracle: R-0850]. Spec and ruling
ids: doc/CLUSTERS.md.
"""

import datetime
import enum
import json
import logging
import re
from dataclasses import dataclass, field

from btcopilot.extensions import db
from btcopilot.llmutil import (
    PDP_FORCE_REQUIRED,
    PDP_SCHEMA_DESCRIPTIONS,
    UNANSWERED,
    Billed,
    OutputTruncatedError,
    Unreadable,
    dataclass_to_json_schema,
)
from btcopilot.matching import TITLE_PREFIXES
from btcopilot.metered import Metered
from btcopilot import record
from btcopilot.models import Author, Change, Observation, ObservationKind, Purpose
from btcopilot import coverage, profile, prompts
from btcopilot.models import Diagram, Discussion, Statement
from btcopilot.schema import (
    MIN_CLUSTER_EVENTS,
    DateCertainty,
    VariableShift,
    Cluster,
    ClusterResult,
    ClusterSource,
    DiagramData,
    Event,
    EventKind,
    Fact,
    ItemKind,
    QuestionOutcome,
    asdict,
    from_dict,
    hash_sarf_dicts,
    parse_date,
)

_log = logging.getLogger(__name__)

# Bumped whenever the candidate rules or the naming prompt change, so a record
# grouped by the older rules re-groups on its next event-changing turn. 6: the
# prompt lines the books contradict reworded and the ten-year check added, so
# every record regroups on its next event change [Oracle: R-0836, R-0838].
# 7: two groups never share years, the person's own shown to the model and
# counted, so every record regroups on its next event change [Oracle: R-0839].
# 8: periods as hypotheses of a family process, the person's own free to
# reshape, overlaps merged, no fallback [Oracle: R-0841 to R-0846].
# 9: a stored model period named only by its years is not handed back, so every
# record regroups on its next event change [Oracle: R-0844, R-0840].
# 10: a run is seeded at a shift that supports a cluster, any change in the
# family may open it, events of unknown date are left out, the person's own
# periods are kept as they drew them, and a failing period is set aside
# [Oracle: R-0850].
# 11: the periods the person named when asked when the most was going on are
# written as theirs, and their answers join the cache key, so every record
# regroups on its next event change [Oracle: R-0853].
# 12: fewer than three supporting shifts counts against a period and no longer
# refuses or sets it aside, so every record regroups on its next event change
# [Oracle: R-0850].
# 13: the runs offered as a hint include those with fewer than three supporting
# shifts, each with its count, and the prompt lets such a period stand with its
# shortfall noted, so every record regroups on its next event change
# [Oracle: R-0850].
# 14: an event whose date is unknown is offered, may belong to a period and
# support it, and never opens one; a period's name is checked against every
# word the person's own trouble is told in; the person's answer to when the
# most was going on is found for a question closed before the answer was
# written on it, so every record regroups on its next event change
# [Oracle: R-0850, R-0853, R-0376].
# 15: a run is seeded only at a shift whose date is known, the people are
# offered with what each is to the person, and a run with three or more
# supporting shifts comes back as a period or is declined with a reason, so
# every record regroups on its next event change [Oracle: R-0850, R-0856].
DETECTION_VERSION = 15

SHIFT_FIELDS = ("symptom", "anxiety", "relationship", "functioning")
ARRIVALS = frozenset({EventKind.Birth, EventKind.Adopted})
RISES = (("symptom", VariableShift.Up), ("anxiety", VariableShift.Up))

# How far either side of a shift a related event is proposed as
# part of the same cluster. A suggestion to the model, not a limit on what it
# may hand back: an event outside it joins when the model says why. Same for
# CALM_GAP_DAYS, the stretch with nothing recorded that proposes a break. The
# floor of three events is the one number that is ruled and enforced
# (MIN_CLUSTER_EVENTS in schema.py), at the model's answer and again at the write.
SPAN_DAYS = 548
# The grouping answer's token limit, thinking included: room for the thinking
# (its budget is 1024, yet calls on a 91-event record used up to 2454) and, per
# event the record may group, its id in the answer and its share of the names,
# reasons and changes (accepted answers used about 9). 89 groupable events get
# 6232 tokens; with no limit, one answer repeated a sentence for 63000.
THINKING_ROOM = 4096
PER_EVENT = 24
# Room per answer of the person's for the periods read from it: the question
# asks for two or three times, each a name, a sentence of theirs and two years.
PER_ANSWER = 160
CALM_GAP_DAYS = 730
# A returned group whose dated events span more than this is refused and the
# model is asked again with the reason; on the second answer it is dropped and
# the rest kept [Oracle: R-0837, R-0846]. It only catches an answer that draws
# the family's whole span as one period; edges stay the model's call. A group
# that long is a stage of the household or the family's ordinary level, not a
# disturbance of it. The sources bound the number on both sides.
# Above: the longest run of dated events any of them draws as one period of
# stress is five years, the longest named family period a six-year plateau of
# illness, and the one decade accepted as a single tag was events leading up to
# a death held together by one man's long illness (Family Therapy in Clinical
# Practice ch. 21 and ch. 3; the seminar; theory.md T105 to T108 in the corpus
# research). Below: Bowen's typical stage of the household is "ten years"
# (Basic Series 3, T1), and his own ten-year narrative chapter is several
# periods of stress with calm between (ch. 21, T81). Ten is the smallest whole
# number no wave on record reaches and the first a stage does. It binds nothing
# inside the range the sources place waves, so the model still judges every
# edge [Oracle: R-0842].
MAX_SPAN_YEARS = 10

# Diagnostic and popular-psychology words the definitions the model is given do
# not contain. The prompt forbids vocabulary from outside those definitions;
# this is the part of that instruction the record can hold it to.
OUTSIDE_WORDS = (
    "toxic",
    "narcissis",
    "gaslight",
    "codepend",
    "dysfunctional",
    "trauma",
    "inner child",
    "love language",
    "red flag",
    "boundaries",
    "enmesh",
    "manipulat",
    "abusive",
    "passive-aggressive",
    "attachment style",
    "emotional labor",
)


# How many letters of a word the naming check compares, and the words it never
# reads as the person's trouble whatever their descriptions say.
STEM = 4
COMMON_WORDS = frozenset(
    {
        "about", "after", "again", "another", "away", "back", "became", "been",
        "before", "could", "during", "family", "from", "have", "home", "into",
        "life", "only", "over", "period", "since", "that", "their", "them",
        "then", "they", "this", "time", "until", "were", "when", "while", "with",
        "would", "year", "years",
    }
)


class ClusterCheck(enum.StrEnum):
    """Which check refused a grouping, so refusals are counted by kind."""

    Missing = "missing"
    UnknownEvent = "unknown_event"
    UnknownDate = "unknown_date"
    TooSmall = "too_small"
    NoName = "no_name"
    NoReason = "no_reason"
    UnknownGroup = "unknown_group"
    GroupTwice = "group_twice"
    OutsideWords = "outside_words"
    TooLong = "too_long"
    YearsName = "years_name"
    SymptomName = "symptom_name"
    Theirs = "theirs"
    NoYears = "no_years"
    Renamed = "renamed"
    UnknownMessage = "unknown_message"
    Merged = "merged"
    Unanswered = "unanswered"
    Declined = "declined"
    CutOff = "cut_off"
    Unreadable = "unreadable"
    CallFailed = "call_failed"


class ClusterError(Exception):
    """The model's answer, or one cluster in it, fails a check. `said` is the
    model's own answer for that cluster, for the observations row."""

    def __init__(self, message: str, check: ClusterCheck, said: dict | None = None):
        super().__init__(message)
        self.check = check
        self.said = said


def _enum_value(val):
    """Extract enum value or return as-is for non-enum types."""
    return val.value if hasattr(val, "value") else val


def supports(event: Event) -> bool:
    """A rise in symptom or anxiety, a fall in functioning, or a relationship
    shift; a drop in anxiety or a rise in functioning does not [Oracle: R-0850]."""
    return troubled(event) or event.relationship is not None


def unsure(event: Event) -> bool:
    """Whether nobody knows the event's date: it may belong to a period and
    support it, and it opens nothing [Oracle: R-0850]."""
    return event.dateCertainty == DateCertainty.Unknown


def troubled(event: Event) -> bool:
    """A rise in symptom or anxiety or a fall in functioning: the person's
    trouble when it is theirs."""
    return (
        any(_enum_value(getattr(event, name)) == way for name, way in RISES)
        or _enum_value(event.functioning) == VariableShift.Down
    )


def _scaffold(event: Event, opens: datetime.date) -> bool:
    """Early births give people ages and generations and are diagnostically
    inert [Oracle: R-0037]; the diagnostic period opens at the first shift that
    supports a cluster, and a change in the family up to
    SPAN_DAYS before it may still open it, since trouble can come first or
    after [Oracle: R-0850]."""
    return (
        event.kind in ARRIVALS
        and (opens - parse_date(event.dateTime)).days > SPAN_DAYS
    )


def _people(event: Event) -> set[int]:
    ids = {event.person, event.spouse, event.child}
    ids.update(event.relationshipTargets or [])
    ids.update(event.relationshipTriangles or [])
    return {person_id for person_id in ids if person_id is not None}


def _years_after(day: datetime.date, count: int) -> datetime.date:
    try:
        return day.replace(year=day.year + count)
    except ValueError:  # the 29th of February
        return day.replace(year=day.year + count, day=28)


def too_long(dates: list[datetime.date]) -> bool:
    """Whether a group's dated events span more than MAX_SPAN_YEARS
    [Oracle: R-0837]."""
    return bool(dates) and max(dates) > _years_after(min(dates), MAX_SPAN_YEARS)


Span = tuple[datetime.date, datetime.date]


def backstop(ids: list[int], when: dict[int, datetime.date]) -> ClusterCheck | None:
    """The first check an app period fails, returned by the model or stored:
    three events, ten years at most [Oracle: R-0850, R-0837]. `when` dates the
    events it may hold. Its supporting shifts are never checked here: too few
    counts against it on the case report, never refuses it [Oracle: R-0850]."""
    if len(ids) < MIN_CLUSTER_EVENTS:
        return ClusterCheck.TooSmall
    if too_long([when[i] for i in ids]):
        return ClusterCheck.TooLong
    return None


def years_name(name: str) -> bool:
    """Whether a name is only a year or a run of years, a length rather than
    a hypothesis [Oracle: R-0844, R-0841]."""
    return re.fullmatch(r"[\d\s\u2013\u2014-]*\d[\d\s\u2013\u2014-]*", name) is not None


def span_of(dates: list[datetime.date]) -> Span | None:
    """The years the timeline draws for a group: its first dated event to its
    last; nothing for a group with no dated event of its own."""
    return (min(dates), max(dates)) if dates else None


def overlapping(a: Span, b: Span) -> bool:
    """Whether two groups would share a day on the timeline [Oracle: R-0845].
    Two groups that only touch on one day do not: the page draws neighbouring
    pills apart at a seam (web/src/picture.ts, `edges`), so touching is the
    one closeness it can still draw as two."""
    return a[0] < b[1] and b[0] < a[1]


def _said(label: str, span: Span) -> str:
    return f"{label} ({span[0].isoformat()} to {span[1].isoformat()})"


def silence(gap: datetime.timedelta) -> str:
    """The stretch with nothing recorded before a proposed group, in the plain
    words the model is shown: "38 years and 4 months", "7 months", "12 days"."""
    years, rest = divmod(gap.days, 365)
    months = rest // 30
    parts = [
        f"{n} {word}{'' if n == 1 else 's'}"
        for n, word in ((years, "year"), (months, "month"))
        if n
    ]
    return (
        " and ".join(parts)
        if parts
        else f"{gap.days} day{'' if gap.days == 1 else 's'}"
    )


def _dated(data: DiagramData) -> list[Event]:
    """Every event with a date, however sure: one whose date is unknown is
    grouped like any other and only opens nothing [Oracle: R-0850]."""
    dated = [e for e in _events(data) if parse_date(e.dateTime)]
    return sorted(dated, key=lambda e: (parse_date(e.dateTime), e.id))


def joinable(data: DiagramData) -> list[Event]:
    """Every dated event a cluster may hold: the scaffolding before the
    first supporting shift of a known date is held out."""
    events = _dated(data)
    marked = [e for e in events if supports(e) and not unsure(e)]
    if not marked:
        return []
    opens = parse_date(marked[0].dateTime)
    return [e for e in events if not _scaffold(e, opens)]


def _split(ids: list[int], when: dict, marked: set[int]) -> list[list[int]]:
    """Two years with no supporting shift in them is not one cluster.
    Cut between two such events that far apart, at the widest silence."""
    ordered = [event_id for event_id in ids if event_id in marked]
    cuts = set()
    for first, second in zip(ordered, ordered[1:]):
        if (when[second] - when[first]).days < CALM_GAP_DAYS:
            continue
        between = ids[ids.index(first) : ids.index(second) + 1]
        cuts.add(
            max(
                (
                    ((when[later] - when[earlier]).days, ids.index(later))
                    for earlier, later in zip(between, between[1:])
                ),
            )[1]
        )
    pieces, piece = [], []
    for index, event_id in enumerate(ids):
        if index in cuts:
            pieces.append(piece)
            piece = []
        piece.append(event_id)
    pieces.append(piece)
    return pieces


@dataclass
class Candidate:
    eventIds: list[int]
    shiftIds: list[int]
    startDate: str
    endDate: str
    id: str = ""

    @property
    def strong(self) -> bool:
        """Three supporting shifts or more: the call's default reading, kept
        unless it says why not [Oracle: R-0856]."""
        return len(self.shiftIds) >= MIN_CLUSTER_EVENTS


def candidates(data: DiagramData) -> list[Candidate]:
    """Runs of events close in time around the shifts that support a
    cluster, anyone's in the extended family, with no model in the loop. Any
    event near a run may be its opening; which ones matter is the grouping
    call's judgement, never a list of kinds. A run with fewer than three
    supporting shifts is offered too, its count beside it [Oracle: R-0850].
    Only a shift whose date is known seeds a run: a placeholder date shows
    nothing close in time, and may only join a run seeded near it."""
    free = joinable(data)
    marked = [e for e in free if supports(e)]
    seeds = [e for e in marked if not unsure(e)]
    if not seeds:
        return []

    when = {e.id: parse_date(e.dateTime) for e in free}

    groups: list[set[int]] = []
    for seed in seeds:
        near = {
            e.id
            for e in free
            if abs((when[e.id] - when[seed.id]).days) <= SPAN_DAYS
        }
        touching = [group for group in groups if group & near]
        for group in touching:
            groups.remove(group)
            near |= group
        groups.append(near)

    marked_ids = {e.id for e in marked}
    kept = [
        Candidate(
            eventIds=ids,
            shiftIds=[i for i in ids if i in marked_ids],
            startDate=when[ids[0]].isoformat(),
            endDate=when[ids[-1]].isoformat(),
        )
        for group in groups
        for ids in _split(
            sorted(group, key=lambda event_id: (when[event_id], event_id)),
            when,
            marked_ids,
        )
        if marked_ids & set(ids) and len(ids) >= MIN_CLUSTER_EVENTS
    ]
    kept.sort(key=lambda c: (c.startDate, c.eventIds[0]))
    for n, candidate in enumerate(kept, 1):
        candidate.id = f"r{n}"
    return kept


@dataclass
class Judgement:
    """A stored cluster read against the data, the app's and the person's
    alike [Oracle: R-0850]. `shiftIds` are its events that support it; `runOf`
    is the one person whose shifts they all are, else None; `opening` the first
    of its events that is a change in who is in the family, else None; the
    gaps are days from that opening to its first and last supporting shift,
    negative when the trouble came first."""

    shiftIds: list[int]
    runOf: int | None
    opening: int | None
    toFirst: int | None
    toLast: int | None

    @property
    def supported(self) -> bool:
        return len(self.shiftIds) >= MIN_CLUSTER_EVENTS


def judge(cluster: dict, data: DiagramData) -> Judgement:
    events = {e.id: e for e in _dated(data)}
    held = sorted(
        (events[i] for i in cluster.get("eventIds") or [] if i in events),
        key=lambda e: (parse_date(e.dateTime), e.id),
    )
    shifts = [e for e in held if supports(e)]
    people = {e.person for e in shifts}
    named = cluster.get("openingEventId")
    changes = [e for e in held if e.id == named and not unsure(e)] or [
        e for e in held if e.kind.isStructural() and not unsure(e)
    ]
    opening = changes[0] if changes else None

    def gap(shift: Event) -> int | None:
        if opening is None:
            return None
        return (parse_date(shift.dateTime) - parse_date(opening.dateTime)).days

    return Judgement(
        shiftIds=[e.id for e in shifts],
        runOf=next(iter(people)) if len(people) == 1 else None,
        opening=opening.id if opening else None,
        toFirst=gap(shifts[0]) if shifts else None,
        toLast=gap(shifts[-1]) if shifts else None,
    )


def _stems(text: str | None) -> set[str]:
    """Each word of four letters or more by its first four, so "moved" and
    "move", or "burnout" and "burn", are one word."""
    return {w[:STEM] for w in re.findall(r"[a-z]{4,}", (text or "").lower())}


def trouble_words(data: DiagramData) -> set[str]:
    """The words the person's own trouble is told in, by stem: those of the
    descriptions of their rises in symptom or anxiety and falls in functioning,
    less any another event, an event's kind, a name, a word for a relative or
    a common word also uses, so a name says the loss and not the trouble
    [Oracle: R-0376, R-0850]."""
    me = (profile.own(data) or {}).get("id")
    events = _dated(data)
    theirs = {e.id for e in events if me is not None and e.person == me and troubled(e)}
    told = set().union(*(_stems(e.description) for e in events if e.id in theirs))
    plain = set().union(
        *(_stems(e.description) for e in events if e.id not in theirs),
        *(_stems(kind.value) for kind in EventKind),
        *(_stems(p.get("name")) for p in data.people if isinstance(p, dict)),
        _stems(" ".join(TITLE_PREFIXES | COMMON_WORDS)),
    )
    return told - plain


def trouble_in(name: str, told: set[str]) -> list[str]:
    """The words of a name that tell the person's trouble."""
    return sorted(
        w for w in re.findall(r"[a-z]{4,}", name.lower()) if w[:STEM] in told
    )


def plain_name(cluster: "ModelCluster", when: dict[int, datetime.date]) -> str:
    """The name a period gets when its name twice told the person's trouble."""
    first, last = span_of([when[i] for i in cluster.eventIds])
    years = str(first.year) if first.year == last.year else f"{first.year}\u2013{last.year}"
    return f"A change in the family, {years}"


@dataclass
class ModelCluster:
    id: str | None = None
    eventIds: list[int] = field(default_factory=list)
    name: str = ""
    reason: str = ""
    change: str | None = None
    openingId: int | None = None


@dataclass
class TheirPeriod:
    """A period the person named, as the grouping call read it from their
    message: their name for it and their sentence, both in their words, and
    its years."""

    messageId: int
    name: str
    words: str
    startYear: int | None = None
    endYear: int | None = None


@dataclass
class Declined:
    """A run with three or more supporting shifts the call does not make a
    period, with its one sentence why."""

    run: str
    reason: str


@dataclass
class ClusterListResponse:
    clusters: list[ModelCluster] = field(default_factory=list)
    periods: list[TheirPeriod] = field(default_factory=list)
    declined: list[Declined] = field(default_factory=list)


@dataclass
class Answer:
    """The person's message answering when the most was going on, with the
    coach's question it answered [Oracle: R-0853]."""

    messageId: int
    question: str
    words: str


def _closes(delta: dict, question_id: str) -> bool:
    after = delta.get("after")
    return (
        delta.get("item_kind") == ItemKind.Question.value
        and str(delta.get("item_id")) == question_id
        and (
            (delta.get("field") == "outcome" and after == QuestionOutcome.Answered)
            or (
                delta.get("field") is None
                and isinstance(after, dict)
                and after.get("outcome") == QuestionOutcome.Answered
            )
        )
    )


def _closed_by(diagram_id: int, question_id: str) -> int | None:
    """The person's message in the turn whose change closed the question as
    answered: a question closed before the answer was written on it carries
    no link, and the change log still holds the turn."""
    change = next(
        (
            change
            for change in Change.query.filter_by(diagram_id=diagram_id).order_by(
                Change.id.desc()
            )
            if any(_closes(delta, question_id) for delta in change.deltas)
        ),
        None,
    )
    said = change and (
        Statement.query.join(Discussion, Statement.discussion_id == Discussion.id)
        .filter(
            Statement.turn_id == change.turn_id,
            Statement.speaker_id == Discussion.chat_user_speaker_id,
        )
        .order_by(Statement.order, Statement.id)
        .first()
    )
    if said is None:
        _log.warning(
            f"Question {question_id} on diagram {diagram_id} is answered with no "
            "message of the person's behind it"
        )
        return None
    return said.id


def _asked(diagram_id: int, data: DiagramData) -> dict[int, str]:
    """The person's answers to when the most was going on, by message id, each
    with the question it answered [Oracle: R-0853]."""
    asked = {}
    for question in data.questions:
        if question.get("fact") != Fact.MostGoingOn:
            continue
        if question.get("answer"):
            said = question["answer"]["id"]
        elif question.get("outcome") == QuestionOutcome.Answered:
            said = _closed_by(diagram_id, question["id"])
        else:
            continue
        if said is not None:
            asked[said] = question.get("text") or ""
    return asked


def told_ids(diagram_id: int, data: DiagramData) -> tuple[int, ...]:
    return tuple(sorted(_asked(diagram_id, data)))


def most_going_on(diagram_id: int, data: DiagramData) -> list[Answer]:
    return [
        Answer(messageId=i, question=text, words=db.session.get(Statement, i).spoken)
        for i, text in sorted(_asked(diagram_id, data).items())
    ]


def compute_cache_key(events: list[Event], told_ids: tuple[int, ...] = ()) -> str:
    event_data = [
        {
            "id": e.id,
            "dateTime": e.dateTime,
            "symptom": _enum_value(e.symptom) if e.symptom else None,
            "anxiety": _enum_value(e.anxiety) if e.anxiety else None,
            "relationship": _enum_value(e.relationship) if e.relationship else None,
            "functioning": _enum_value(e.functioning) if e.functioning else None,
            "dateCertainty": _enum_value(e.dateCertainty),
        }
        for e in events
    ]
    return hash_sarf_dicts(
        [{"detectionVersion": DETECTION_VERSION, "told": sorted(told_ids)}] + event_data
    )


def _event_json(event: Event) -> dict:
    chunk = {
        "id": event.id,
        "date": event.dateTime,
        "kind": _enum_value(event.kind),
        "description": event.description or "",
        "people": sorted(_people(event)),
    }
    for name in SHIFT_FIELDS:
        value = getattr(event, name)
        if value is not None:
            chunk[name] = _enum_value(value)
    if event.dateCertainty != DateCertainty.Certain:
        chunk["dateCertainty"] = _enum_value(event.dateCertainty)
    if event.notes:
        chunk["notes"] = event.notes
    return chunk


def _before(candidate: Candidate, when: dict[int, datetime.date]) -> str:
    """One plain line on the silence before a proposed group, so the model
    reads the gap instead of inferring it from two date strings: Kerr weighs
    "the time spacing between events" (Family Evaluation, line 3355)."""
    first = parse_date(candidate.startDate)
    earlier = [day for day in when.values() if day < first]
    if not earlier:
        return "first group in the record"
    return f"{silence(first - max(earlier))} with nothing recorded before this group"


THEIRS = "the person drew this period"
TROUBLE = "named by the person's trouble"


def _prompt(
    cands: list[Candidate],
    free: list[Event],
    stored: dict[str, dict],
    said: list[Answer],
    born: str | None,
    told: set[str] = frozenset(),
    people: list[str] = (),
) -> str:
    when = {e.id: parse_date(e.dateTime) for e in free}
    sure = {e.id for e in free if not unsure(e)}
    existing = []
    for cluster_id, cluster in stored.items():
        shown = {
            "id": cluster_id,
            "name": _title(cluster),
            "reason": cluster.get("reason") or cluster.get("summary") or "",
            "eventIds": [i for i in cluster.get("eventIds") or [] if i in when],
        }
        if cluster.get("openingEventId") in sure:
            shown["openingId"] = cluster["openingEventId"]
        if not _regroupable(cluster):
            shown["note"] = THEIRS
        elif trouble_in(_title(cluster), told):
            shown["note"] = TROUBLE
        existing.append(shown)
    return prompts.CLUSTER_PROMPT.format(
        existing=json.dumps(existing, indent=2),
        candidates=json.dumps(
            [
                {
                    "id": candidate.id,
                    "before": _before(candidate, when),
                    "supportingShifts": len(candidate.shiftIds),
                    "default": candidate.strong,
                    "eventIds": candidate.eventIds,
                }
                for candidate in cands
            ],
            indent=2,
        ),
        people=json.dumps(list(people), indent=2),
        events=json.dumps([_event_json(e) for e in free], indent=2),
        told=json.dumps(
            {
                "personBorn": born,
                "answers": [
                    {"messageId": one.messageId, "question": one.question, "said": one.words}
                    for one in said
                ],
            },
            indent=2,
        ),
    )


def _title(cluster: dict) -> str:
    return cluster.get("name") or cluster.get("title") or ""


def _cast(data: DiagramData, free: list[Event]) -> list[str]:
    """Everyone the offered events name, with what each is to the person when
    the diagram says, so which change mattered is judged by who changed and a
    period is named in words the person knows [Oracle: R-0426, R-0376]."""
    ids = sorted(set().union(*(_people(e) for e in free)))
    return [coverage.label(data, ItemKind.Person, pid) for pid in ids]


def _sculpted(cluster: ModelCluster, was: dict, known: set[int]) -> bool:
    """Whether the model handed a stored grouping back other than as it was,
    among the events it was offered."""
    return set(cluster.eventIds) != set(was.get("eventIds") or []) & known or (
        cluster.name != _title(was)
    )


def _said_of(cluster: ModelCluster, when: dict[int, datetime.date]) -> dict:
    """The model's own answer for one cluster, as an observations row keeps it."""
    dates = [when[i] for i in cluster.eventIds if i in when]
    return {
        "name": cluster.name,
        "eventIds": list(cluster.eventIds),
        "start": min(dates).isoformat() if dates else None,
        "end": max(dates).isoformat() if dates else None,
    }


def _fault(
    cluster: ModelCluster,
    known: set[int],
    stored: dict[str, dict],
    claimed: set[str],
    told: set[str],
    unsure_ids: set[int] = frozenset(),
) -> tuple[str, ClusterCheck] | None:
    """What makes one returned cluster unusable before any merge, or nothing."""
    unknown = [event_id for event_id in cluster.eventIds if event_id not in known]
    if unknown:
        return f"Events {unknown} are not among the events you were given.", (
            ClusterCheck.UnknownEvent
        )
    if not cluster.name.strip():
        return "Every period needs a name.", ClusterCheck.NoName
    if cluster.openingId is not None and cluster.openingId not in cluster.eventIds:
        return (
            f"Period {cluster.name!r} opens at event {cluster.openingId}, which is "
            "not one of its events.",
            ClusterCheck.UnknownEvent,
        )
    if cluster.openingId in unsure_ids:
        return (
            f"Period {cluster.name!r} opens at event {cluster.openingId}, whose date "
            "is unknown; an event of unknown date opens nothing.",
            ClusterCheck.UnknownDate,
        )
    if not cluster.reason.strip():
        return "Every period needs a reason.", ClusterCheck.NoReason
    if cluster.id is not None and not _regroupable(stored.get(cluster.id, {})):
        return (
            f"Period {cluster.id!r} is not one of the app's periods listed.",
            ClusterCheck.UnknownGroup,
        )
    if cluster.id is not None and cluster.id in claimed:
        return f"Period {cluster.id!r} came back twice.", ClusterCheck.GroupTwice
    spoken = " ".join([cluster.name, cluster.reason, cluster.change or ""]).lower()
    outside = [word for word in OUTSIDE_WORDS if word in spoken]
    if outside:
        return (
            f"Period {cluster.name!r} uses {outside}, which the definitions you "
            "were given do not contain.",
            ClusterCheck.OutsideWords,
        )
    trouble = trouble_in(cluster.name, told)
    if trouble:
        return (
            f"Period {cluster.name!r} is named by the person's trouble ({trouble}); "
            "name it by the change in the family and its years.",
            ClusterCheck.SymptomName,
        )
    return None


def _merged(
    clusters: list[ModelCluster], when: dict[int, datetime.date]
) -> tuple[list[ModelCluster], list[tuple[ModelCluster, ModelCluster]]]:
    """Periods sharing a day or an event made one: the family is one emotional
    unit, so one reading of it never draws two periods over the same days
    [Oracle: R-0845]. The one holding more events carries the name and id, the
    earlier on a tie. Returns the periods and each one absorbed with the period
    it went into."""

    def span(cluster: ModelCluster) -> Span:
        return span_of([when[i] for i in cluster.eventIds])

    out: list[ModelCluster] = []
    absorbed: list[tuple[ModelCluster, ModelCluster]] = []
    for cluster in sorted(clusters, key=lambda c: (span(c)[0], span(c)[1])):
        last = out[-1] if out else None
        if last is None or not (
            overlapping(span(last), span(cluster))
            or set(last.eventIds) & set(cluster.eventIds)
        ):
            out.append(cluster)
            continue
        keep, lose = (
            (last, cluster)
            if len(last.eventIds) >= len(cluster.eventIds)
            else (cluster, last)
        )
        events = sorted(
            set(last.eventIds) | set(cluster.eventIds), key=lambda i: (when[i], i)
        )
        out[-1] = ModelCluster(
            id=keep.id,
            eventIds=events,
            name=keep.name,
            reason=keep.reason,
            change=keep.change,
            openingId=keep.openingId,
        )
        absorbed.append((lose, out[-1]))
    return out, absorbed


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _in_their_words(text: str, said: str) -> bool:
    """Whether a phrase is the person's own: its words side by side, in order,
    in their message."""
    part, whole = _words(text), _words(said)
    return bool(part) and any(
        whole[i : i + len(part)] == part for i in range(len(whole) - len(part) + 1)
    )


def _years(period: TheirPeriod) -> Span | None:
    if period.startYear is None or period.endYear is None or period.startYear > period.endYear:
        return None
    return datetime.date(period.startYear, 1, 1), datetime.date(period.endYear, 12, 31)


@dataclass
class Named:
    """A period the person named, with the events inside its years."""

    period: TheirPeriod
    eventIds: list[int]


def _read_theirs(
    periods: list[TheirPeriod],
    said: list[Answer],
    data: DiagramData,
) -> tuple[list[Named], list[ClusterError]]:
    """The periods the person named, each with every dated event in the family
    inside its years, never reshaped [Oracle: R-0853]. One with no readable
    years, not in their own words, too few events, or sharing days with a
    period of theirs already stored or read first is not written; each such is
    a fault, never asked again, since asking cannot add years to their words."""
    events = _dated(data)
    when = {e.id: parse_date(e.dateTime) for e in events}
    messages = {one.messageId: one.words for one in said}
    taken = [
        span
        for cluster in data.clusters
        if isinstance(cluster, dict)
        and not _regroupable(cluster)
        and (span := span_of([when[i] for i in cluster.get("eventIds") or [] if i in when]))
    ]
    kept: list[Named] = []
    faults: list[ClusterError] = []

    def fault(message: str, check: ClusterCheck, period: TheirPeriod, ids: list[int]):
        dates = [when[i] for i in ids]
        faults.append(
            ClusterError(
                message,
                check,
                {
                    "name": period.name,
                    "eventIds": ids,
                    "start": min(dates).isoformat() if dates else None,
                    "end": max(dates).isoformat() if dates else None,
                    "messageId": period.messageId,
                },
            )
        )

    for period in periods:
        if period.messageId not in messages:
            fault(
                f"Message {period.messageId} is not one of the person's answers you "
                "were given.",
                ClusterCheck.UnknownMessage,
                period,
                [],
            )
            continue
        words = messages[period.messageId]
        if not (_in_their_words(period.name, words) and _in_their_words(period.words, words)):
            fault(
                f"The person's period {period.name!r} is not in their own words.",
                ClusterCheck.Renamed,
                period,
                [],
            )
            continue
        years = _years(period)
        if years is None:
            fault(
                f"The person's period {period.name!r} has no years their words "
                "give.",
                ClusterCheck.NoYears,
                period,
                [],
            )
            continue
        ids = [e.id for e in events if years[0] <= when[e.id] <= years[1]]
        if len(ids) < MIN_CLUSTER_EVENTS:
            fault(
                f"The person's period {period.name!r} holds {len(ids)} events in "
                f"its years; anything under {MIN_CLUSTER_EVENTS} is never a period.",
                ClusterCheck.TooSmall,
                period,
                ids,
            )
            continue
        span = span_of([when[i] for i in ids])
        if any(overlapping(span, other) for other in taken):
            fault(
                f"The person's period {period.name!r} shares days with a period "
                "of theirs already stored.",
                ClusterCheck.Theirs,
                period,
                ids,
            )
            continue
        taken.append(span)
        kept.append(Named(period=period, eventIds=ids))
    return kept, faults


@dataclass
class Screened:
    """One answer read against the checks: the periods that pass, each period
    that fails with why, each period merged into another, and the person's
    periods read from their answers with those not written."""

    kept: list[ModelCluster]
    faults: list[ClusterError]
    absorbed: list[tuple[ModelCluster, ModelCluster]]
    named: list[Named] = field(default_factory=list)
    unnamed: list[ClusterError] = field(default_factory=list)
    declined: list[ClusterError] = field(default_factory=list)


def _screen(
    response: ClusterListResponse | None,
    free: list[Event],
    stored: dict[str, dict],
    told: set[str],
    data: DiagramData,
    said: list[Answer],
    last: bool = False,
    runs: list[Candidate] = (),
) -> Screened:
    """`last` is the second answer: a period still named by the person's
    trouble is kept under a plain name, and one still opening at an event of
    unknown date is kept with no opening, instead of dropped. The person's
    periods are read first, so the app's never share their days."""
    if response is None:
        raise ClusterError("No grouping came back.", ClusterCheck.Missing)
    named, unnamed = _read_theirs(response.periods, said, data)
    known = {e.id for e in free}
    unsure_ids = {e.id for e in free if unsure(e)}
    when = {e.id: parse_date(e.dateTime) for e in free}
    full = {e.id: parse_date(e.dateTime) for e in _dated(data)}
    theirs = [
        (cluster, span)
        for cluster in stored.values()
        if not _regroupable(cluster)
        and (span := span_of([when[i] for i in cluster.get("eventIds") or [] if i in when]))
    ] + [
        ({"name": one.period.name}, span_of([full[i] for i in one.eventIds]))
        for one in named
    ]
    faults: list[ClusterError] = []
    usable: list[ModelCluster] = []
    claimed: set[str] = set()
    for cluster in response.clusters:
        fault = _fault(cluster, known, stored, claimed, told, unsure_ids)
        if fault and fault[1] is ClusterCheck.UnknownDate and last:
            faults.append(ClusterError(*fault, said=_said_of(cluster, when)))
            cluster.openingId = None
            fault = _fault(cluster, known, stored, claimed, told, unsure_ids)
        if fault and fault[1] is ClusterCheck.SymptomName and last:
            faults.append(ClusterError(*fault, said=_said_of(cluster, when)))
            cluster.name = plain_name(cluster, when)
            fault = None
        if fault:
            faults.append(ClusterError(*fault, said=_said_of(cluster, when)))
            continue
        if not cluster.eventIds:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} holds no events.",
                    ClusterCheck.TooSmall,
                    _said_of(cluster, when),
                )
            )
            continue
        span = span_of([when[i] for i in cluster.eventIds])
        drawn = next((c for c, s in theirs if overlapping(s, span)), None)
        if drawn is not None:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} shares days with the person's own "
                    f"period {_title(drawn)!r}, which stays as they drew it.",
                    ClusterCheck.Theirs,
                    _said_of(cluster, when),
                )
            )
            continue
        if cluster.id is not None:
            claimed.add(cluster.id)
        usable.append(cluster)
    merged, absorbed = _merged(usable, when)
    kept = []
    for cluster in merged:
        said = _said_of(cluster, when)
        check = backstop(cluster.eventIds, when)
        if check is ClusterCheck.TooSmall:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} holds {len(cluster.eventIds)} events; "
                    f"anything under {MIN_CLUSTER_EVENTS} is never a period.",
                    check,
                    said,
                )
            )
        elif check is ClusterCheck.TooLong:
            faults.append(
                ClusterError(
                    f"Period {cluster.name!r} runs from {said['start'][:4]} to "
                    f"{said['end'][:4]}: more than {MAX_SPAN_YEARS} years is this "
                    "family's ordinary level, not a period. Return the periods "
                    "inside it.",
                    check,
                    said,
                )
            )
        else:
            kept.append(cluster)
    unanswered, declined = _answered_runs(response, runs, named, stored)
    return Screened(
        kept=kept,
        faults=faults + unanswered,
        absorbed=absorbed,
        named=named,
        unnamed=unnamed,
        declined=declined,
    )


def _answered_runs(
    response: ClusterListResponse,
    runs: list[Candidate],
    named: list[Named],
    stored: dict[str, dict],
) -> tuple[list[ClusterError], list[ClusterError]]:
    """Each run that no period holds a shift of, the app's as returned or the
    person's: declined with a reason, it is kept as an observation; neither
    returned nor declined, it is a fault, asked again, so every run offered is
    judged [Oracle: R-0856, R-0850]."""
    held = [set(c.eventIds) for c in response.clusters]
    held += [set(one.eventIds) for one in named]
    held += [
        set(c.get("eventIds") or []) for c in stored.values() if not _regroupable(c)
    ]
    why = {d.run: d.reason.strip() for d in response.declined if d.reason.strip()}
    unanswered, declined = [], []
    for run in runs:
        if any(set(run.shiftIds) & ids for ids in held):
            continue
        said = {
            "run": run.id,
            "eventIds": run.eventIds,
            "start": run.startDate,
            "end": run.endDate,
        }
        line = (
            f"Run {run.id} ({run.startDate} to {run.endDate}) has "
            f"{len(run.shiftIds)} shifts that count"
        )
        if run.id in why:
            declined.append(
                ClusterError(
                    f"{line} and was declined: {why[run.id]}",
                    ClusterCheck.Declined,
                    {**said, "reason": why[run.id]},
                )
            )
        else:
            unanswered.append(
                ClusterError(
                    f"{line} and came back neither as a period nor under "
                    "`declined` with a reason.",
                    ClusterCheck.Unanswered,
                    said,
                )
            )
    return unanswered, declined


def _judged(
    data: DiagramData,
) -> tuple[dict[str, dict], list[tuple[dict, ClusterCheck, str]]]:
    """The stored clusters handed back to the model, by id, and each stored
    model cluster that fails a check a returned one must pass, or is named
    only by its years, with a sentence naming it and its years. The person's
    own are always handed back, as they drew them, and only judged
    [Oracle: R-0850, R-0853, R-0844]."""
    dated = _dated(data)
    when = {e.id: parse_date(e.dateTime) for e in dated}
    kept, failing = {}, []
    for cluster in data.drawn_clusters():
        ids = [i for i in cluster.get("eventIds") or [] if i in when]
        span = span_of([when[i] for i in ids])
        name = _said(_title(cluster), span) if span else repr(_title(cluster))
        named = f"Stored grouping {cluster['id']} {name}"
        check = backstop(ids, when)
        if not _regroupable(cluster):
            kept[str(cluster["id"])] = cluster
        elif check is ClusterCheck.TooSmall:
            failing.append((cluster, check, f"{named} holds {len(ids)} dated events"))
        elif check is ClusterCheck.TooLong:
            failing.append(
                (cluster, check, f"{named} fails the {MAX_SPAN_YEARS}-year check")
            )
        elif years_name(_title(cluster)):
            failing.append(
                (cluster, ClusterCheck.YearsName, f"{named} is named only by its years")
            )
        else:
            kept[str(cluster["id"])] = cluster
    return kept, failing


def mine(data: DiagramData) -> dict[str, dict]:
    """The stored clusters handed to the model as existing. A model cluster
    that fails a check a returned one must pass, or is named only by its
    years, is left out and set aside, its events back to the hint
    [Oracle: R-0838, R-0844, R-0850]."""
    kept, failing = _judged(data)
    for _, _, why in failing:
        _log.info(f"{why} and is not handed back")
    return kept


def broken(data: DiagramData) -> list[tuple[dict, ClusterCheck, str]]:
    """The stored model clusters that fail a backstop, each with the check
    and a sentence naming its years."""
    return _judged(data)[1]


def answer_schema(
    stored: dict[str, dict], said: list[Answer] = (), runs: list[Candidate] = ()
) -> dict:
    """The answer's shape, with `id` limited to the groups the record holds and
    left out when it holds none (the person's own are never the model's to
    hand back), and every group's events, name and reason
    required. Offered a free-text id, the grouping model wrote one for every
    new group, and the check refused each answer; with nothing required, it
    once left out every group's events. The person's periods are asked for
    only when they answered, each under one of their messages, its years left
    out when their words give none; a run is declined by its id."""
    schema = dataclass_to_json_schema(
        ClusterListResponse, PDP_SCHEMA_DESCRIPTIONS, PDP_FORCE_REQUIRED
    )
    group = schema["properties"]["clusters"]["items"]
    group["required"] = ["eventIds", "name", "reason"]
    fields = group["properties"]
    ours = sorted(i for i, cluster in stored.items() if _regroupable(cluster))
    if ours:
        fields["id"]["enum"] = ours
    else:
        del fields["id"]
    if runs:
        declined = schema["properties"]["declined"]["items"]
        declined["required"] = ["run", "reason"]
        declined["properties"]["run"]["enum"] = [run.id for run in runs]
    else:
        del schema["properties"]["declined"]
    if not said:
        del schema["properties"]["periods"]
        return schema
    period = schema["properties"]["periods"]["items"]
    period["required"] = ["messageId", "name", "words"]
    return schema


def _answered(ask, prompt: str, schema: dict, limit: int) -> "ClusterListResponse":
    """An answer cut off at its limit, unreadable, or never given is refused
    like any other, so grouping never fails the turn."""
    try:
        return ask(prompt, schema, limit)
    except OutputTruncatedError as cut:
        raise ClusterError(
            "Your answer ran past its length limit. Give each name, reason and "
            "change in one short sentence.",
            ClusterCheck.CutOff,
        ) from cut
    except Unreadable as garbled:
        raise ClusterError(
            "Your answer was not the JSON asked for.", ClusterCheck.Unreadable
        ) from garbled
    except (Billed, *UNANSWERED) as failed:
        raise ClusterError(
            f"The grouping call failed: {type(failed).__name__}",
            ClusterCheck.CallFailed,
        ) from failed


def detect_clusters(
    data: DiagramData, ask, refused=None, said: list[Answer] = ()
) -> ClusterResult:
    """`ask` takes the prompt, the answer's schema and its token limit and
    returns the model's ClusterListResponse; `refused`, when given, hears each
    refused answer, dropped cluster, merged cluster and period of the person's
    not written, with its attempt number and the answer it came in. `said` is
    the person's answers to when the most was going on; each period they name
    there is returned once as theirs [Oracle: R-0853].

    A first answer with any fault is asked for once more with the reasons. On
    the second, a cluster that still fails is dropped and the rest kept; an
    answer that cannot be read, or keeps nothing out of what it returned,
    raises [Oracle: R-0846, R-0844]."""
    cache_key = compute_cache_key(
        _events(data), tuple(sorted(one.messageId for one in said))
    )
    cands = candidates(data)
    if not cands and not said:
        return ClusterResult(clusters=[], cacheKey=cache_key)

    free = joinable(data)
    taken = {
        str(c["id"]) for c in data.clusters if isinstance(c, dict) and c.get("id")
    }
    existing = mine(data)
    told = trouble_words(data)
    own = profile.own(data)
    born = own and profile.birth(data, own["id"])
    prompt = _prompt(
        cands, free, existing, said, born and born["dateTime"], told, _cast(data, free)
    )
    schema = answer_schema(existing, said, cands)
    limit = (
        THINKING_ROOM
        + PER_EVENT * len(free)
        + PER_ANSWER * (len(said) + len(cands))
    )
    _log.info(
        f"Grouping {len(free)} events: {len(existing)} groups already there, "
        f"{len(cands)} proposed as a hint"
    )

    def heard(attempt: int, error: ClusterError, answer) -> None:
        _log.warning(f"Grouping answer {attempt}: {error}")
        if refused:
            refused(attempt, error, answer)

    given: list[ClusterListResponse] = []

    def attempt(n: int, words: str) -> Screened:
        answer = None
        try:
            answer = _answered(ask, words, schema, limit)
            given.append(answer)
            screened = _screen(
                answer, free, existing, told, data, said, last=n == 2, runs=cands
            )
        except ClusterError as failed:
            heard(n, failed, answer)
            raise
        for fault in screened.faults:
            heard(n, fault, answer)
        for lost, into in screened.absorbed:
            heard(
                n,
                ClusterError(
                    f"Period {lost.name!r} shares days with {into.name!r} and is "
                    "merged into it.",
                    ClusterCheck.Merged,
                    _said_of(lost, {e.id: parse_date(e.dateTime) for e in free}),
                ),
                answer,
            )
        if (
            n == 2
            and screened.faults
            and not screened.kept
            and not screened.named
            and answer.clusters
            and not all(f.check is ClusterCheck.Theirs for f in screened.faults)
        ):
            raise screened.faults[0]
        return screened

    try:
        screened = attempt(1, prompt)
        retry = bool(screened.faults)
        # The second call does not see the first answer unless it is told it,
        # so without it every period is read afresh, not only the faulty one.
        why = " ".join(
            [
                *(str(fault) for fault in screened.faults),
                f"Your last answer was: {json.dumps(asdict(given[0]))}",
            ]
        )
    except ClusterError as failed:
        retry, why = True, str(failed)
    if retry:
        screened = attempt(2, prompt + prompts.CLUSTER_REJECTED.format(why=why))
    for fault in screened.unnamed:
        heard(2 if retry else 1, fault, None)
    for declined in screened.declined:
        heard(2 if retry else 1, declined, None)

    when = {e.id: e.dateTime for e in free}
    known = set(when)
    clusters, changes = [], []
    for cluster in screened.kept:
        spanned = sorted(when[event_id] for event_id in cluster.eventIds)
        cluster_id = cluster.id or next_id(taken)
        taken.add(cluster_id)
        was = existing.get(cluster.id) if cluster.id else None
        # An event with no date, or scaffolding, is never offered, so one a
        # stored period holds stays on it as it was [Oracle: R-0850].
        held = [i for i in (was or {}).get("eventIds") or [] if i not in known]
        clusters.append(
            Cluster(
                id=cluster_id,
                title=cluster.name,
                name=cluster.name,
                summary=cluster.reason,
                reason=cluster.reason,
                eventIds=[*cluster.eventIds, *held],
                openingEventId=cluster.openingId,
                startDate=spanned[0],
                endDate=spanned[-1],
                source=(
                    _source(was)
                    if was is not None and not _sculpted(cluster, was, known)
                    else ClusterSource.Model
                ),
            )
        )
        if cluster.change:
            changes.append(cluster.change)
            _log.info(f"Regrouped {cluster.name!r}: {cluster.change}")
    dated = {e.id: e.dateTime for e in _dated(data)}
    for one in screened.named:
        cluster_id = next_id(taken)
        taken.add(cluster_id)
        clusters.append(
            Cluster(
                id=cluster_id,
                title=one.period.name,
                name=one.period.name,
                summary=one.period.words,
                reason=one.period.words,
                eventIds=one.eventIds,
                startDate=dated[one.eventIds[0]],
                endDate=dated[one.eventIds[-1]],
                source=ClusterSource.User,
            )
        )
        _log.info(f"Wrote the person's period {one.period.name!r}")
    return ClusterResult(clusters=clusters, cacheKey=cache_key, changes=changes)


STORED_FIELDS = (
    "title",
    "name",
    "summary",
    "reason",
    "eventIds",
    "startDate",
    "endDate",
    "source",
    "setAside",
    "openingEventId",
)


def next_id(taken: set[str]) -> str:
    return record.next_key("c", taken)


def _source(cluster: dict) -> ClusterSource | None:
    source = cluster.get("source")
    return ClusterSource(source) if source else None


def _regroupable(cluster: dict) -> bool:
    """Only a grouping the model is known to have made may be regrouped.
    A cluster of unknown provenance is treated as the user's, because the coach
    does not overwrite what the user asked for and the cost is asymmetric:
    guessing wrong about the model loses a name the user chose."""
    return _source(cluster) is ClusterSource.Model


def _detected(stored: list[dict], detected: list[Cluster], dates: dict) -> dict:
    """The model's grouping, each cluster under its own id: the model's own
    statement of which stored cluster it is, so what the coach said about it
    last turn still points at something the diagram holds. `dates` are the
    dated events, however sure; the span is theirs, and an event with no date
    a stored period held stays on it [Oracle: R-0850]. A grouping under the
    minimum is a bug in whatever produced it and raises."""
    taken = {str(c["id"]) for c in stored}
    kept: dict[str, Cluster] = {}
    for cluster in detected:
        if len(cluster.eventIds) < MIN_CLUSTER_EVENTS:
            raise ClusterError(
                f"Grouping {cluster.eventIds} arrived holding fewer than "
                f"{MIN_CLUSTER_EVENTS} events.",
                ClusterCheck.TooSmall,
            )
        cluster.name = cluster.name or cluster.title
        spanned = sorted(dates[e] for e in cluster.eventIds if e in dates)
        cluster.startDate, cluster.endDate = spanned[0], spanned[-1]
        cluster.id = str(cluster.id) if cluster.id else next_id(taken | set(kept))
        kept[cluster.id] = cluster
    return kept


def set_aside(cluster_ids) -> list[dict]:
    return [
        {
            "item_kind": ItemKind.Cluster.value,
            "item_id": cluster_id,
            "field": "setAside",
            "after": True,
        }
        for cluster_id in cluster_ids
    ]


def grouped(cache_key: str) -> dict:
    """Marks the record grouped as its events and answers now stand."""
    return {
        "item_kind": ItemKind.Diagram.value,
        "item_id": None,
        "field": "clusterCacheKey",
        "after": cache_key,
    }


def _deltas(stored: list[dict], detected: list[Cluster], dates: dict) -> list[dict]:
    """Every app cluster the answer did not return is set aside, never
    deleted; the person's own are kept as they drew them [Oracle: R-0850]."""
    stored = [
        c
        for c in stored
        if isinstance(c, dict) and c.get("id") is not None and not c.get("setAside")
    ]
    held = {str(c["id"]): c for c in stored}
    kept = _detected(stored, detected, dates)

    deltas = set_aside(
        cluster_id
        for cluster_id, cluster in held.items()
        if cluster_id not in kept and _regroupable(cluster)
    )
    for cluster_id, cluster in kept.items():
        was = held.get(cluster_id, {})
        now = asdict(cluster)
        deltas += [
            {
                "item_kind": ItemKind.Cluster.value,
                "item_id": cluster_id,
                "field": field_name,
                "after": now[field_name],
            }
            for field_name in STORED_FIELDS
            if now[field_name] != was.get(field_name)
        ]
    return deltas


@dataclass
class Regroup:
    """What one recompute did: the record change it wrote, and one sentence per
    grouping it reshaped, in story rather than in the language of grouping."""

    change: Change
    sentences: list[str]


def _events(data: DiagramData) -> list[Event]:
    return [
        from_dict(Event, chunk)
        for chunk in data.events
        if isinstance(chunk, dict) and chunk.get("id") is not None
    ]


def behind(diagram_id: int, data: DiagramData) -> bool:
    """Whether the record's events, or the person's answers to when the most
    was going on, changed since its last grouping."""
    return (
        compute_cache_key(_events(data), told_ids(diagram_id, data))
        != data.clusterCacheKey
    )


def sync(
    diagram_id: int,
    *,
    turn_id: str,
    user_id: int,
    session_id: int | None = None,
    metered: Metered | None = None,
    force: bool = False,
) -> Regroup | None:
    """Re-group the record's events and store the grouping. `force` regroups a
    record whose events are as they were at its last grouping.

    Clusters are stored, not derived on read, so the coach can point at one and
    have it still be there next turn. The rules' runs are a hint; the model
    decides the app's periods and reads the person's from their answers, never
    reshaping theirs and never inventing a member.
    """
    diagram = db.session.get(Diagram, diagram_id)
    data = diagram.get_diagram_data()
    events = _events(data)
    said = most_going_on(diagram_id, data)
    cache_key = compute_cache_key(events, tuple(one.messageId for one in said))
    if not force and cache_key == data.clusterCacheKey:
        return None

    dates = {e.id: e.dateTime for e in _dated(data)}
    metered = metered or Metered(user_id, diagram_id, turn_id, Purpose.Cluster)

    def observe(kind: ObservationKind, detail: dict) -> None:
        db.session.add(
            Observation(
                diagram_id=diagram_id, turn_id=turn_id, kind=kind, detail=detail
            )
        )

    def refused(attempt: int, error: ClusterError, answer) -> None:
        groups = answer.clusters if answer else []
        observe(
            ObservationKind.ClusterRefused,
            {
                "attempt": attempt,
                "check": error.check.value,
                "detail": str(error),
                "groups": len(groups),
                "events": sum(len(g.eventIds) for g in groups),
                "reason": error.check.value,
                **(error.said or {}),
            },
        )

    failing = broken(data)
    for cluster, check, why in failing:
        _log.warning(f"Turn {turn_id} sets aside: {why}")
        observe(
            ObservationKind.ClusterFailed,
            {
                "check": check.value,
                "detail": why,
                "fallback": False,
                "reason": check.value,
                "setAside": str(cluster["id"]),
            },
        )

    try:
        result = detect_clusters(
            data,
            lambda prompt, schema, limit: metered.structured(
                prompt, ClusterListResponse, schema, limit
            ),
            refused,
            said,
        )
    except ClusterError as failed:
        # No usable answer: the clusters that pass stay, a stored model cluster
        # that fails a check is set aside, its events dots until a regroup
        # passes, and a refused answer marks this state of the record grouped,
        # so the same calls are not made again until it changes; a call that
        # never answered is tried again next turn [Oracle: R-0840, R-0844,
        # R-0850].
        observe(
            ObservationKind.ClusterFailed,
            {
                "check": failed.check.value,
                "detail": str(failed),
                "fallback": False,
                "reason": failed.check.value,
            },
        )
        _log.warning(f"Turn {turn_id} grouping refused twice: {failed}")
        deltas = set_aside(str(cluster["id"]) for cluster, _, _ in failing)
        if failed.check is not ClusterCheck.CallFailed:
            deltas.append(grouped(cache_key))
        if not deltas:
            return None
        change = record.apply(
            diagram_id,
            deltas,
            author=Author.Coach,
            turn_id=turn_id,
            user_id=user_id,
            session_id=session_id,
        )
        return Regroup(change=change, sentences=[])
    deltas = _deltas(data.clusters, result.clusters, dates)
    deltas.append(grouped(cache_key))
    change = record.apply(
        diagram_id,
        deltas,
        author=Author.Coach,
        turn_id=turn_id,
        user_id=user_id,
        session_id=session_id,
    )
    return Regroup(change=change, sentences=result.changes)
