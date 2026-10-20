"""The rules find runs of events as a hint; the model holds each period of
heightened difficulty as a hypothesis and the code only backstops it.

The first half of this file runs without a model at all. The second half
scripts the model and checks what the code drops, merges and keeps.
"""

import dataclasses
import datetime
import json
from contextlib import contextmanager

import pytest
from google.genai import _transformers
from mock import Mock, patch

from btcopilot import clusters, diagramjson
from btcopilot.clusters import (
    FLOOR_YEARS,
    Answer,
    ClusterCheck,
    ClusterError,
    ClusterListResponse,
    Declined,
    ModelCluster,
    TheirPeriod,
    _deltas,
    answer_schema,
    candidates,
    detect_clusters,
    joinable,
    overlapping,
    silence,
    sync,
    too_long,
)
from btcopilot.extensions import db
from btcopilot.llmutil import Parsed, Served, Spent, gemini_structured_sync
from btcopilot.models import (
    Author,
    Change,
    Observation,
    ObservationKind,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.seed import seed_diagram_data
from btcopilot.schema import (
    Cluster,
    ClusterSource,
    DateCertainty,
    DiagramData,
    Event,
    EventKind,
    Fact,
    ItemKind,
    PairBond,
    Person,
    QuestionKind,
    QuestionOutcome,
    QuestionState,
    RelationshipKind,
    VariableShift,
    asdict,
)


SHIFTS = ("symptom", "anxiety", "relationship", "functioning")


def moment(event_id: int, date: str, **kwargs) -> dict:
    """A shift; one given no variable is a rise in anxiety, a shift that
    supports a cluster [Oracle: R-0850]."""
    kwargs.setdefault("kind", EventKind.Shift)
    if kwargs["kind"] is EventKind.Shift and not any(k in kwargs for k in SHIFTS):
        kwargs["anxiety"] = VariableShift.Up
    return asdict(Event(id=event_id, dateTime=date, **kwargs))


def record(
    *events: dict, people: int = 3, bonds: list = (), clusters: list = ()
) -> DiagramData:
    return DiagramData(
        people=[asdict(Person(id=n, name=f"P{n}")) for n in range(1, people + 1)],
        events=list(events),
        pair_bonds=[asdict(b) for b in bonds],
        clusters=[asdict(c) for c in clusters],
    )


# The fictional Hale family, shaped like the fault seen on production: three
# runs of events decades apart and one stray, a grandparent on the 1948
# marriage and on the 1998 death the only bridge between the 1950s and the
# 1990s. Nobody real. 1 Walter and 2 Edith (the grandparents), 3 June and 4 Ray
# (the parents), 5 Nell (the person), 6 Mae (her aunt), 7 Theo (her husband).
HALE_NAMES = ("Walter", "Edith", "June", "Ray", "Nell", "Mae", "Theo")
HALE_BONDS = (
    PairBond(id=1, person_a=1, person_b=2),
    PairBond(id=2, person_a=3, person_b=4),
    PairBond(id=3, person_a=5, person_b=7),
)
HALE_EVENTS = (
    asdict(
        Event(id=1, kind=EventKind.Married, person=1, spouse=2, dateTime="1948-06-12")
    ),
    moment(
        2,
        "1954-02-10",
        person=2,
        symptom=VariableShift.Up,
        description="Edith's headaches began",
    ),
    moment(
        3,
        "1954-09-01",
        person=1,
        relationship=RelationshipKind.Distance,
        relationshipTargets=[2],
        description="Walter away at the mill most nights",
    ),
    moment(
        4,
        "1955-04-20",
        person=2,
        functioning=VariableShift.Down,
        description="Edith stopped keeping the books",
    ),
    asdict(
        Event(
            id=5,
            kind=EventKind.Birth,
            child=6,
            person=1,
            spouse=2,
            dateTime="1955-11-02",
        )
    ),
    asdict(
        Event(id=6, kind=EventKind.Divorced, person=3, spouse=4, dateTime="1994-03-05")
    ),
    moment(
        7,
        "1994-06-10",
        person=5,
        relationship=RelationshipKind.Distance,
        relationshipTargets=[3],
        description="Nell stopped calling her mother",
    ),
    moment(
        8,
        "1994-10-20",
        person=3,
        symptom=VariableShift.Up,
        description="June's drinking",
    ),
    asdict(
        Event(id=9, kind=EventKind.Married, person=5, spouse=7, dateTime="1996-09-01")
    ),
    moment(
        10,
        "1997-04-12",
        person=5,
        symptom=VariableShift.Up,
        description="Nell's panic attacks",
    ),
    asdict(Event(id=11, kind=EventKind.Death, person=1, dateTime="1998-01-15")),
    moment(
        12,
        "1998-09-30",
        person=5,
        relationship=RelationshipKind.Conflict,
        relationshipTargets=[7],
        description="fights over money",
    ),
    moment(
        13,
        "2000-02-14",
        person=7,
        functioning=VariableShift.Down,
        description="Theo lost his job",
    ),
    asdict(
        Event(
            id=14, kind=EventKind.Separated, person=5, spouse=7, dateTime="2001-06-30"
        )
    ),
)
# The three runs the rules offer of it, the 1994 one with two supporting
# shifts, and the 1948 marriage in none.
HALE_PROPOSALS = [[2, 3, 4, 5], [6, 7, 8], [9, 10, 11, 12, 13, 14]]
HALE_STRAYS = [1]
ALL_HALE = list(range(1, 15))


def hale(*clusters: Cluster) -> DiagramData:
    return DiagramData(
        people=[
            asdict(Person(id=n, name=name)) for n, name in enumerate(HALE_NAMES, 1)
        ],
        events=list(HALE_EVENTS),
        pair_bonds=[asdict(b) for b in HALE_BONDS],
        clusters=[asdict(c) for c in clusters],
    )


HALE = hale()


def grouped(data: DiagramData) -> list[list[int]]:
    return [c.eventIds for c in candidates(data)]


def test_a_pair_of_related_moves_is_not_yet_a_cluster():
    # R-0215
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-08-01", person=1, description="the month after"),
    )
    assert grouped(data) == []


def test_a_birth_long_before_anything_is_recorded_is_scaffolding():
    # R-0037, R-0850
    """A birth years before the first shift is scaffolding; one a few months
    before may be what opened the run."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Birth, child=1, dateTime="1980-01-01")),
        asdict(Event(id=5, kind=EventKind.Birth, child=2, dateTime="1994-02-01")),
        moment(2, "1994-06-01", person=1),
        moment(3, "1994-09-01", person=1),
        moment(4, "1994-11-01", person=1),
    )
    assert grouped(data) == [[5, 2, 3, 4]]


def test_the_recorded_period_starts_at_the_first_shift():
    # R-0037, R-0850
    """A birth years before the first shift is held out; an early marriage and
    a birth months before the shift are not."""
    data = record(
        asdict(
            Event(id=1, kind=EventKind.Married, person=1, spouse=2, dateTime="1950-01-01")
        ),
        asdict(Event(id=2, kind=EventKind.Birth, child=3, dateTime="1950-06-01")),
        asdict(Event(id=3, kind=EventKind.Birth, child=4, dateTime="1952-01-01")),
        moment(4, "1952-06-01", person=3),
    )
    assert [e.id for e in joinable(data)] == [1, 3, 4]


def test_a_change_in_the_family_among_the_shifts_opens_their_period():
    # R-0375, R-0850
    """The marriage between the shifts belongs to their run and is read as
    the period's opening; the shifts are what the period is about."""
    data = record(
        moment(1, "1994-06-01", person=1),
        asdict(
            Event(id=2, kind=EventKind.Married, person=1, spouse=2, dateTime="1994-09-01")
        ),
        moment(3, "1994-11-01", person=1),
        moment(4, "1995-02-01", person=2, symptom=VariableShift.Up),
    )
    assert grouped(data) == [[1, 2, 3, 4]]
    read = clusters.judge({"eventIds": [1, 2, 3, 4]}, data)
    assert (read.opening, read.shiftIds) == (2, [1, 3, 4])


def test_any_change_in_the_family_may_open_a_run_and_trouble_may_come_first():
    # R-0850, R-0375
    """No kind list seeds or filters a run: a run is seeded at three shifts
    of anyone in the family, and every event near them, the move and the
    grandmother's death after the first shift, is offered as its possible
    opening."""
    data = record(
        moment(1, "1998-01-01", person=1, functioning=VariableShift.Down),
        asdict(Event(id=2, kind=EventKind.Death, person=3, dateTime="1998-04-01")),
        asdict(
            Event(
                id=3,
                kind=EventKind.Noted,
                person=2,
                dateTime="1998-05-01",
                description="moved",
            )
        ),
        moment(4, "1998-08-01", person=2, symptom=VariableShift.Up),
        moment(5, "1999-01-01", person=1, relationship=RelationshipKind.Cutoff),
    )
    assert grouped(data) == [[1, 2, 3, 4, 5]]
    assert [c.shiftIds for c in candidates(data)] == [[1, 4, 5]]


def test_a_death_with_no_shifts_near_it_opens_nothing():
    # R-0850
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=1, dateTime="1994-06-01")),
        moment(2, "1994-09-01", person=2, kind=EventKind.Noted, description="moved"),
        moment(3, "1994-11-01", person=2, kind=EventKind.Noted, description="new job"),
    )
    assert grouped(data) == []


def test_a_run_with_fewer_than_three_supporting_shifts_is_offered_with_its_count():
    # R-0850
    """Fewer than three supporting shifts counts against a run, never keeps
    it from the hint: the death and the two shifts after it are offered, the
    count beside them; two events stay too few."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=1, dateTime="1994-06-01")),
        moment(2, "1994-09-01", person=2),
        moment(3, "1994-11-01", person=2),
    )
    proposed = candidates(data)
    assert [(c.eventIds, c.shiftIds) for c in proposed] == [([1, 2, 3], [2, 3])]
    prompt = clusters._prompt(proposed, joinable(data), {}, [], None)
    hint = prompt.split("(A HINT ONLY)")[1].split("THE PEOPLE")[0]
    assert [
        (run["supportingShifts"], run["default"], run["eventIds"])
        for run in json.loads(hint)
    ] == [(2, False, [1, 2, 3])]


def test_a_run_around_a_single_shift_is_not_offered():
    # R-0850
    """One shift alone is a reaction: a death, the funeral and one rise in
    anxiety after it are no run; a second shift makes them one."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=2, dateTime="2026-08-14")),
        moment(2, "2026-08-22", person=1, kind=EventKind.Noted, description="funeral"),
        moment(3, "2026-09-15", person=1),
    )
    assert grouped(data) == []
    data.events.append(moment(4, "2026-10-01", person=3))
    assert grouped(data) == [[1, 2, 3, 4]]


def test_an_event_of_unknown_date_is_offered_marked_as_opening_nothing():
    # R-0850
    unknown = moment(1, "1994-06-01", person=1, dateCertainty=DateCertainty.Unknown)
    sure = moment(2, "1994-07-01", person=1)
    shown = [clusters._event_json(e) for e in joinable(record(unknown, sure))]
    assert [one.get("neverOpens") for one in shown] == [True, None]


def test_a_shift_of_unknown_date_alone_seeds_no_run():
    # R-0850
    """A placeholder date shows nothing close in time: shifts whose dates
    nobody knows join a run seeded near them and never seed one."""
    unknown = DateCertainty.Unknown
    data = record(
        moment(1, "1955-01-01", person=1, dateCertainty=unknown),
        moment(2, "1955-03-01", person=1, dateCertainty=unknown),
        moment(3, "1955-06-01", person=2, dateCertainty=unknown),
    )
    assert grouped(data) == []
    data.events.append(moment(4, "1955-09-01", person=2))
    assert grouped(data) == [[1, 2, 3, 4]]


def test_a_run_of_three_shifts_comes_back_as_a_period_or_is_declined_with_a_reason():
    # R-0856, R-0850, R-0873
    """A hint with three or more supporting shifts and a change in who is in
    the family is the app's default: an answer that neither returns it nor
    declines it is asked again with the reason; a hint declined with a reason
    is heard, the rest kept, holding the death inside its days the answer
    left out."""
    data = record(
        moment(1, "1994-01-01", person=1),
        asdict(Event(id=4, kind=EventKind.Death, person=4, dateTime="1994-02-01")),
        moment(2, "1994-03-01", person=1),
        moment(3, "1994-05-01", person=2),
        moment(10, "2010-01-01", person=1),
        moment(11, "2010-02-01", person=2),
        asdict(
            Event(
                id=13, kind=EventKind.Married, person=1, spouse=2, dateTime="2010-03-01"
            )
        ),
        moment(12, "2010-04-01", person=3),
        people=4,
    )
    assert [(c.id, c.strong) for c in candidates(data)] == [("r1", True), ("r2", True)]
    first = answers(named(1, 2, 3))
    second = answers(named(1, 2, 3))
    second.declined = [Declined(hint="r2", reason="three reactions to one storm")]
    seen = []
    with replies(first, second) as ask:
        result = detect_clusters(data, ask, heard(seen))
    assert seen == [(1, ClusterCheck.Unanswered), (2, ClusterCheck.Declined)]
    again = ask.call_args_list[1].args[0]
    assert "Run r2 (2010-01-01 to 2010-04-01) has 3 shifts" in again
    assert 'Your last answer was: {"clusters": [{"id": null, "eventIds": [1, 2, 3]' in again
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3, 4]]
    declined = answer_schema({}, [], candidates(data))["properties"]["declined"]["items"]
    assert declined["properties"]["hint"]["enum"] == ["r1", "r2"]
    assert "run" not in declined["properties"]
    assert "never its count of shifts" in declined["properties"]["reason"]["description"]


def test_the_people_are_offered_with_what_each_is_to_the_person():
    # R-0426, R-0376
    """Which change mattered is judged by who changed, so the call is told who
    each person the events name is to the person."""
    data = record(
        moment(1, "1994-01-01", person=2),
        moment(2, "1994-03-01", person=3),
        bonds=[PairBond(id=9, person_a=2, person_b=3)],
    )
    data.people[0]["parents"] = 9
    data.people[1]["gender"] = "female"
    assert clusters._cast(data, joinable(data)) == ["2 P2 (mother)", "3 P3 (parent)"]


def test_a_calmer_shift_supports_nothing_and_an_unknown_date_still_supports():
    # R-0850
    """A drop in anxiety or a rise in functioning is no support; a rise in
    anxiety whose date is unknown belongs to the run and supports it like any
    other."""
    data = record(
        moment(1, "1994-06-01", person=1),
        moment(2, "1994-07-01", person=1, anxiety=VariableShift.Down),
        moment(3, "1994-08-01", person=1, functioning=VariableShift.Up),
        moment(4, "1994-09-01", person=1, dateCertainty=DateCertainty.Unknown),
        moment(5, "1994-10-01", person=1),
    )
    assert [(c.eventIds, c.shiftIds) for c in candidates(data)] == [
        ([1, 2, 3, 4, 5], [1, 4, 5])
    ]
    assert [e.id for e in joinable(data)] == [1, 2, 3, 4, 5]


def test_a_shift_told_as_how_things_always_were_supports_no_hint():
    # R-0850, R-0856
    """Two of the three shifts after the death are told as how things always
    were, the family's ordinary level: the one left is a reaction, so no hint
    is offered. Told as departures, the same three make one."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=3, dateTime="1963-01-10")),
        moment(
            2,
            "1963-02-10",
            person=1,
            relationship=RelationshipKind.Distance,
            description="has always bickered with her aunt",
        ),
        moment(
            3,
            "1963-03-10",
            person=1,
            functioning=VariableShift.Down,
            description="has forever kept the shop going on her own",
        ),
        moment(4, "1963-05-10", person=2, anxiety=VariableShift.Up),
    )
    assert grouped(data) == []
    data.events[1]["description"] = "stopped visiting her aunt"
    data.events[2]["description"] = "let the shop slide"
    assert [c.shiftIds for c in candidates(data)] == [[2, 3, 4]]
    told = ["always late", "forever on edge", "how things always were"]
    assert all(
        clusters.standing(Event(id=9, kind=EventKind.Shift, description=one))
        for one in told
    )
    assert not clusters.standing(
        Event(id=9, kind=EventKind.Shift, description="wholly new, nevertheless")
    )


def test_a_change_told_with_never_or_for_years_still_supports_a_hint():
    # R-0850, R-0856
    """Only always and forever mark a shift as how things always were: a
    cutoff told with "never" and a drinking told with "for years" are changes
    after a loss, and they count."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=4, dateTime="1981-02-01")),
        moment(
            2,
            "1981-03-01",
            person=1,
            relationship=RelationshipKind.Cutoff,
            relationshipTargets=[3],
            description="never spoke to his father again after the funeral",
        ),
        moment(
            3,
            "1981-06-01",
            person=2,
            symptom=VariableShift.Up,
            description="drank heavily for years after the divorce",
        ),
        moment(4, "1981-09-01", person=1, anxiety=VariableShift.Up),
        people=4,
    )
    events = clusters._events(data)
    assert [clusters.supports(e, events) for e in events[1:3]] == [True, True]
    assert [(c.shiftIds, c.strong) for c in candidates(data)] == [([2, 3, 4], True)]


# Three shifts that count, months apart, and a change in the family to put
# beside them: a diagnosis noted on its own event, and a death.
SHIFTS_ALONE = [
    moment(1, "1963-02-01", person=1),
    moment(2, "1963-04-01", person=2),
    moment(3, "1963-06-01", person=1),
]
DIAGNOSIS = Event(
    id=4,
    kind=EventKind.Noted,
    person=3,
    dateTime="1963-03-01",
    dateCertainty=DateCertainty.Approximate,
    description="diagnosed with diabetes",
)
DEATH = Event(id=5, kind=EventKind.Death, person=3, dateTime="1963-05-01")


def defaults(data: DiagramData) -> list[bool]:
    """Each hint's `default` as the call is shown it."""
    proposed = candidates(data)
    prompt = clusters._prompt(proposed, joinable(data), {}, [], None)
    hint = prompt.split("(A HINT ONLY)")[1].split("THE PEOPLE")[0]
    return [one["default"] for one in json.loads(hint)]


def test_a_hint_whose_only_change_is_a_diagnosis_on_a_known_date_is_the_default():
    # R-0850, R-0856
    """A change in the family is any event the diagram lists that is not a
    shift: a diagnosis noted on a known date, approximate or certain, makes
    three shifts that count the default reading, as a death does."""
    diagnosed = record(*SHIFTS_ALONE, asdict(DIAGNOSIS))
    assert [(c.changeIds, c.strong) for c in candidates(diagnosed)] == [([4], True)]
    assert defaults(diagnosed) == [True]
    died = record(*SHIFTS_ALONE, asdict(DEATH))
    assert [(c.changeIds, c.strong) for c in candidates(died)] == [([5], True)]


def test_a_hint_with_only_shifts_or_a_change_of_unknown_date_is_not_the_default():
    # R-0850, R-0856, R-0855
    """Three shifts that count with no change in the family beside them, or
    with one whose date nobody knows, are offered as a question, never the
    default reading."""
    alone = record(*SHIFTS_ALONE)
    assert [(c.shiftIds, c.strong) for c in candidates(alone)] == [([1, 2, 3], False)]
    assert defaults(alone) == [False]
    unknown = DateCertainty.Unknown
    unsure = record(
        *SHIFTS_ALONE,
        asdict(dataclasses.replace(DIAGNOSIS, dateCertainty=unknown)),
        asdict(dataclasses.replace(DEATH, dateCertainty=unknown)),
    )
    assert [(c.changeIds, c.strong) for c in candidates(unsure)] == [([], False)]
    assert defaults(unsure) == [False]


def test_a_lift_counts_beside_another_persons_rise_in_the_same_months_and_never_alone():
    # R-0850, R-0856
    """A drop in one person's symptom beside another's rise is one movement
    in the family and counts; beside only its own person's rise it counts for
    nothing; and a lift never starts a hint, so an event more than a year and
    a half after the last rise stays out though it is near the lift."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=3, dateTime="1975-02-01")),
        moment(2, "1975-03-01", person=1, symptom=VariableShift.Up),
        moment(3, "1975-04-01", person=1, anxiety=VariableShift.Up),
        moment(
            4,
            "1975-05-15",
            person=2,
            symptom=VariableShift.Down,
            description="her headaches cleared",
        ),
        moment(5, "1976-10-01", person=2, kind=EventKind.Noted, description="new job"),
    )
    assert [(c.eventIds, c.shiftIds) for c in candidates(data)] == [
        ([1, 2, 3, 4], [2, 3, 4])
    ]
    data.events[3]["person"] = 1
    assert [c.shiftIds for c in candidates(data)] == [[2, 3]]
    data.events[3]["person"] = 2
    data.events[3]["dateTime"] = "1975-09-01"
    assert [c.shiftIds for c in candidates(data)] == [[2, 3]]


# The fictional Brook family: Ida (1) falls apart after her aunt Lou (2) is
# diagnosed, a diagnosis nobody can date, and Lou dies the next spring.
BROOK = record(
    asdict(
        Event(
            id=60,
            kind=EventKind.Shift,
            person=2,
            symptom=VariableShift.Up,
            description="diagnosed with lung cancer",
            dateTime="2003-01-01",
            dateCertainty=DateCertainty.Unknown,
        )
    ),
    moment(61, "2003-04-01", person=1, functioning=VariableShift.Down),
    moment(62, "2003-08-01", person=1, anxiety=VariableShift.Up),
    asdict(Event(id=63, kind=EventKind.Death, person=2, dateTime="2004-03-01")),
)


def test_an_event_of_unknown_date_is_offered_belongs_and_supports_but_opens_nothing():
    # R-0850
    """The undatable diagnosis is offered with its certainty, held by the
    period and counted as support; named as its opening it is heard and kept
    with no opening, never asked again, since asking cannot make the date
    known; read against the data, the death opens it."""
    opened = named(60, 61, 62, 63, name="Lou's illness and death")
    opened.openingId = 60
    seen = []
    with replies(answers(opened)) as ask:
        result = detect_clusters(BROOK, ask, heard(seen))
    events = ask.call_args_list[0].args[0].split("EVERY EVENT")[1].split("WHEN THE")[0]
    assert json.loads(events)[0]["dateCertainty"] == "unknown"
    assert seen == [(1, ClusterCheck.UnknownDate)]
    [cluster] = result.clusters
    assert (cluster.eventIds, cluster.openingEventId) == ([60, 61, 62, 63], None)
    assert (cluster.startDate, cluster.endDate) == ("2003-01-01", "2004-03-01")
    read = clusters.judge(asdict(cluster), BROOK)
    assert (read.shiftIds, read.opening) == ([60, 61, 62], 63)


def test_a_lone_shift_with_no_related_move_stays_a_dot():
    # R-0215
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=2, description="someone else entirely"),
    )
    assert grouped(data) == []


def test_a_break_can_leave_a_shift_standing_alone():
    # R-0215
    """Two years of silence cuts the run; the shift left alone before it is a
    dot and not a cluster."""
    data = record(
        moment(1, "1990-01-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1992-08-01", person=1, description="the quiet ends"),
        moment(3, "1992-10-01", person=1, functioning=VariableShift.Down),
        moment(4, "1992-12-01", person=1, description="right after"),
    )
    assert grouped(data) == [[2, 3, 4]]


def test_an_undated_event_never_enters_a_cluster():
    # R-0013
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=1, description="dated"),
        moment(3, "1994-11-01", person=1, description="also dated"),
        moment(4, None, person=1, description="no date at all"),
    )
    assert grouped(data) == [[1, 2, 3]]


CONTAMINATED = {
    2: "his toxic narcissistic gaslighting",
    3: "her codependent enabling of the abuse",
}


def test_the_words_in_a_description_never_move_a_boundary():
    # R-0195
    """A record full of popular-psychology phrasing groups exactly as the same
    record in plain words does."""
    plain = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=1, description="they argued"),
        moment(3, "1994-11-01", person=1, description="she stepped back"),
    )
    loaded = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=1, description=CONTAMINATED[2]),
        moment(3, "1994-11-01", person=1, description=CONTAMINATED[3]),
    )
    assert grouped(plain) == grouped(loaded) == [[1, 2, 3]]


RECORD = record(
    moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
    moment(2, "1994-09-01", person=2, description="they argued"),
    moment(3, "1994-11-01", person=2, description="she stepped back"),
    moment(4, "1997-01-01", person=1, functioning=VariableShift.Down),
    moment(5, "1997-04-01", person=2, description="he moved out"),
    moment(6, "1997-06-01", person=2, description="the summer after"),
)


def answers(*clusters: ModelCluster, declined=()) -> ClusterListResponse:
    return ClusterListResponse(
        clusters=list(clusters),
        declined=[Declined(hint=run, reason="nothing piles up") for run in declined],
    )


def named(
    *event_ids: int,
    cluster_id=None,
    name="A hard spring",
    reason="these events fell close together",
    change=None,
):
    return ModelCluster(
        id=cluster_id,
        eventIds=list(event_ids),
        name=name,
        reason=reason,
        change=change,
    )


@contextmanager
def replies(*responses):
    yield Mock(side_effect=list(responses))


def real(prompt: str, schema: dict) -> ClusterListResponse:
    return gemini_structured_sync(prompt, ClusterListResponse, schema=schema).value


def heard(seen: list):
    return lambda n, err, _: seen.append((n, err.check))


def test_the_model_names_the_candidates_it_was_given():
    # R-0076, R-0287
    with replies(
        answers(named(1, 2, 3), named(4, 5, 6, name="The winter after"))
    ) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3], [4, 5, 6]]
    assert [c.name for c in result.clusters] == ["A hard spring, 1994", "The winter after, 1997"]
    assert all(c.reason for c in result.clusters)


def test_an_answer_leaving_events_out_is_kept_on_the_first_ask():
    # R-0842, R-0841
    """Most events stay outside any period: an answer that leaves a marked
    shift out, and joins nothing the rules proposed, says no change sentence
    and is still kept as given."""
    with replies(answers(named(1, 2, 3, 4, 5))) as ask:
        result = detect_clusters(RECORD, ask)
    assert ask.call_count == 1
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3, 4, 5]]


def test_a_grouping_that_names_an_event_the_record_does_not_hold_is_rejected():
    # R-0076
    with replies(answers(named(1, 2, 3, 99)), answers(named(1, 2, 3, 99))) as ask:
        with pytest.raises(ClusterError, match="99"):
            detect_clusters(RECORD, ask)


def test_a_group_under_three_events_is_dropped_on_the_second_answer():
    # R-0215
    """Asked once more and still handing back a pair and a single, the pieces
    under three are dropped and the rest kept."""
    small = answers(named(1, 2, 3), named(4, 5), named(6))
    seen = []
    with replies(small, small) as ask:
        result = detect_clusters(RECORD, ask, heard(seen))
    assert ask.call_count == 2
    assert "thrown out" in ask.call_args_list[1].args[0]
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert seen == [(n, ClusterCheck.TooSmall) for n in (1, 1, 2, 2)]


def test_a_split_under_the_minimum_that_is_corrected_is_stored():
    # R-0215
    with replies(
        answers(named(1, 2, 3), named(4, 5), named(6)),
        answers(named(1, 2, 3), named(4, 5, 6)),
    ) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3], [4, 5, 6]]


def test_a_group_with_no_reason_is_dropped_on_the_second_answer():
    # R-0287, R-0205
    silent = answers(named(1, 2, 3, reason=""), named(4, 5, 6))
    with replies(silent, silent) as ask:
        result = detect_clusters(RECORD, ask)
    assert "needs a reason" in ask.call_args_list[1].args[0]
    assert [c.eventIds for c in result.clusters] == [[4, 5, 6]]


def test_words_from_outside_the_given_definitions_are_rejected():
    # R-0195
    """The record refuses to store the diagnostic vocabulary. Asked once more,
    still contaminated everywhere, nothing is kept and the grouping fails."""
    outside = answers(
        named(1, 2, 3, name="The toxic spring"),
        named(4, 5, 6, reason="his narcissistic gaslighting set it off"),
    )
    with replies(outside, outside) as ask:
        with pytest.raises(ClusterError, match="toxic"):
            detect_clusters(RECORD, ask)
    assert ask.call_count == 2
    assert "thrown out" in ask.call_args_list[1].args[0]


def test_a_contaminated_name_that_is_corrected_on_the_second_ask_is_stored():
    # R-0195
    with replies(
        answers(named(1, 2, 3, name="The gaslighting spring"), named(4, 5, 6)),
        answers(named(1, 2, 3, name="The spring they argued"), named(4, 5, 6)),
    ) as ask:
        result = detect_clusters(RECORD, ask)
    assert ask.call_count == 2
    assert [c.name for c in result.clusters] == [
        "The spring they argued, 1994",
        "A hard spring, 1997",
    ]


def test_a_rejected_grouping_is_asked_for_once_more():
    # R-0076
    with replies(
        answers(named(1, 2, 99)), answers(named(1, 2, 3), named(4, 5, 6))
    ) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3], [4, 5, 6]]
    second = ask.call_args_list[1].args[0]
    assert "thrown out" in second and "99" in second


FORBIDDEN = (
    "toxic",
    "narcissis",
    "gaslight",
    "codepend",
    "dysfunctional",
    "trauma",
    "enabler",
    "boundaries",
    "abusive",
    "enmesh",
    "manipulat",
    "triggered",
    "inner child",
    "attachment style",
)


@pytest.mark.e2e
def test_a_real_model_names_the_seeded_record():
    # R-0076, R-0287
    data = seed_diagram_data()
    proposed = candidates(data)
    result = detect_clusters(data, real)
    print(f"candidates: {len(proposed)}  named: {len(result.clusters)}")
    for cluster in result.clusters:
        print(f"  {len(cluster.eventIds)} events — {cluster.reason}")
    assert result.clusters
    assert all(cluster.reason for cluster in result.clusters)


@pytest.mark.e2e
def test_a_real_model_does_not_repeat_the_words_it_was_fed():
    # R-0195
    """Every description in this record is written in popular-psychology terms
    the prompt does not define. Nothing the model writes back may use them."""
    data = seed_diagram_data()
    for event in data.events:
        if event.get("description"):
            event["description"] = f"his toxic narcissistic {event['description']}"
    result = detect_clusters(data, real)
    spoken = [(c.name, c.reason) for c in result.clusters]
    print(f"named: {len(spoken)}")
    for name, reason in spoken:
        print(f"  {name} — {reason}")
    assert spoken
    for name, reason in spoken:
        words = f"{name} {reason}".lower()
        assert not [word for word in FORBIDDEN if word in words]


SPRING = "The spring they argued"


def already(*event_ids: int, cluster_id="c1", name=SPRING) -> Cluster:
    return Cluster(
        id=cluster_id,
        title=name,
        name=name,
        summary="one thing led to the next",
        reason="these events fell close together",
        eventIds=list(event_ids),
        source=ClusterSource.Model,
    )


KEPT = record(
    moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
    moment(2, "1994-09-01", person=2, description="they argued"),
    moment(3, "1994-11-01", person=2, description="she stepped back"),
    clusters=[already(1, 2, 3)],
)


def test_a_grouping_already_there_is_handed_back_and_kept():
    # R-0842, R-0371
    with replies(answers(named(1, 2, 3, cluster_id="c1", name=SPRING))) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [("c1", f"{SPRING}, 1994")]
    assert result.changes == []
    assert SPRING in ask.call_args_list[0].args[0]


def test_a_grouping_already_there_is_given_to_the_model_with_its_id():
    # R-0842
    with replies(answers(named(1, 2, 3, cluster_id="c1", name=SPRING))) as ask:
        detect_clusters(KEPT, ask)
    asked = ask.call_args_list[0].args[0]
    assert "PERIODS THIS DIAGRAM HAS" in asked
    assert '"id": "c1"' in asked


def test_a_renamed_grouping_with_no_change_sentence_is_kept():
    # R-0842
    """The name is the hypothesis, revised as the picture clears: a rename
    needs no sentence and costs no second call."""
    renamed = answers(named(1, 2, 3, cluster_id="c1", name="After the move"))
    with replies(renamed) as ask:
        result = detect_clusters(KEPT, ask)
    assert ask.call_count == 1
    assert [(c.id, c.name) for c in result.clusters] == [("c1", "After the move, 1994")]


def test_changing_a_grouping_already_there_passes_its_sentence_on():
    # R-0371, R-0372
    moved = "She stepped back a month later than the record first said."
    with replies(
        answers(named(1, 2, 3, cluster_id="c1", name="The autumn after", change=moved))
    ) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [("c1", "The autumn after, 1994")]
    assert result.changes == [moved]


def test_an_id_the_record_does_not_have_is_rejected():
    # R-0076
    invented = answers(named(1, 2, 3, cluster_id="c99", name=SPRING))
    with replies(invented, invented) as ask:
        with pytest.raises(ClusterError, match="c99"):
            detect_clusters(KEPT, ask)


FAR = record(
    moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
    moment(2, "1994-09-01", person=1, description="they argued"),
    moment(3, "1994-11-01", person=1, description="she stepped back"),
    moment(7, "1999-03-01", person=2, description="five years later"),
)


def test_an_event_years_outside_the_proposal_may_join():
    # R-0842, R-0194
    """The 18 months the rules reach is a hint, not a wall."""
    assert grouped(FAR) == [[1, 2, 3]]
    with replies(answers(named(1, 2, 3, 7))) as ask:
        result = detect_clusters(FAR, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3, 7]]


def test_the_answer_may_name_only_the_groups_the_record_holds():
    # R-0517, R-0844
    model, user = {"source": "model"}, {"source": "user"}
    group = answer_schema({"c2": model, "c1": model, "u1": user})["properties"][
        "clusters"
    ]["items"]
    assert group["properties"]["id"]["enum"] == ["c1", "c2"]
    assert group["required"] == ["eventIds", "name", "reason"]
    for fresh in ({}, {"u1": user}):
        items = answer_schema(fresh)["properties"]["clusters"]["items"]
        assert "id" not in items["properties"]


def test_gemini_takes_the_answer_shape_when_the_person_answered():
    # R-0853
    """Gemini reads every enum as text, so a list of message ids would refuse
    the call before it is made; the code checks the message ids instead."""
    said = [Answer(messageId=7, question="When?", words="In my late 20s.")]
    schema = answer_schema({"c1": {"source": "model"}}, said)
    assert _transformers.t_schema(None, schema) is not None
    assert "only wonder" in schema["properties"]["periods"]["items"]["description"]


# The Hale record: the rules' proposal, the scripted answers the check refuses
# and passes, and the prompt it is given.

MERGED_WHY = (
    "Edith's headaches after the marriage, June's divorce and Nell's own marriage "
    "breaking up while her grandfather died are one story of the women in this family"
)
MERGED = answers(named(*ALL_HALE, name="The women of this family", change=MERGED_WHY))
PROPOSED = answers(
    named(2, 3, 4, 5, name="After the marriage"),
    named(9, 10, 12, 13, 14, name="Nell and Theo"),
    declined=["r2"],
)


def spans(result) -> list[tuple[str, str]]:
    return [(c.startDate[:4], c.endDate[:4]) for c in result.clusters]


def test_the_hale_record_proposes_three_groups_decades_apart_and_one_stray():
    # R-0215, R-0850
    proposed = candidates(HALE)
    assert [c.eventIds for c in proposed] == HALE_PROPOSALS
    assert [c.startDate for c in proposed] == ["1954-02-10", "1994-03-05", "1996-09-01"]
    assert [len(c.shiftIds) for c in proposed] == [3, 2, 3]
    grouped = {i for c in proposed for i in c.eventIds}
    assert [e.id for e in joinable(HALE) if e.id not in grouped] == HALE_STRAYS


def test_a_whole_history_period_given_twice_fails_the_grouping():
    # R-0846
    """One period of all fourteen events, 1948 to 2001, on both asks: it is
    dropped, nothing is left, and the grouping fails rather than store it."""
    seen = []
    with replies(MERGED, MERGED) as ask:
        with pytest.raises(ClusterError, match="ordinary level") as refused:
            detect_clusters(HALE, ask, heard(seen))
    assert refused.value.check is ClusterCheck.TooLong
    assert seen == [(1, ClusterCheck.TooLong), (2, ClusterCheck.TooLong)]
    second = ask.call_args_list[1].args[0]
    assert "thrown out" in second and "1948 to 2001" in second


def test_a_period_over_half_the_history_is_dropped_and_the_rest_kept():
    # R-0846
    """1948 to 1994 is more than half of the family's 1948 to 2001."""
    long = answers(
        named(1, 2, 3, 4, 5, 6, 7, 8, name="The women of this family"),
        named(9, 10, 12, 13, 14, name="Nell and Theo"),
    )
    with replies(long, long) as ask:
        result = detect_clusters(HALE, ask)
    assert ask.call_count == 2
    assert [c.name for c in result.clusters] == ["Nell and Theo, 1996–2001"]


def test_without_the_whole_history_check_the_merged_answer_is_accepted():
    # R-0846
    with patch.object(clusters, "HISTORY_SHARE", 1.0):
        with replies(MERGED) as ask:
            result = detect_clusters(HALE, ask)
    assert spans(result) == [("1948", "2001")]


def test_only_a_period_over_half_the_diagrams_dated_years_is_too_long():
    # R-0850, R-0856, R-0846
    """Twelve years in a family history of sixty is a period; twelve of
    twenty is most of the history. Ten years to the day is never too long,
    whatever the history, so a diagram told only as far as one period still
    gets it."""
    day = datetime.date(1990, 1, 1)
    sixty = (datetime.date(1960, 1, 1), datetime.date(2020, 1, 1))
    twenty = (datetime.date(1990, 1, 1), datetime.date(2010, 1, 1))
    twelve = [day, datetime.date(2002, 1, 1)]
    assert not too_long(twelve, sixty)
    assert too_long(twelve, twenty)
    ten = [day, datetime.date(1990 + FLOOR_YEARS, 1, 1)]
    assert not too_long(ten, (day, ten[1]))
    assert too_long([day, datetime.date(1990 + FLOOR_YEARS, 1, 2)], (day, ten[1]))
    assert not too_long([], twenty)
    assert not too_long(twelve, None)
    assert not too_long(
        [datetime.date(1996, 2, 29), datetime.date(2006, 2, 28)],
        (datetime.date(1996, 2, 29), datetime.date(2006, 2, 28)),
    )


# The fictional Fenn family, 1950 to 2015: after a grandmother's death in 1990
# Kit (1) and Jo (2) climb for more than eleven years, each step a shift with
# only partial relief between, no quiet long enough to end it.
CLIMB = [
    asdict(Event(id=20, kind=EventKind.Death, person=3, dateTime="1990-01-01")),
    moment(21, "1990-03-01", person=1, symptom=VariableShift.Up),
    moment(22, "1991-06-01", person=1, anxiety=VariableShift.Up),
    moment(23, "1992-09-01", person=2, functioning=VariableShift.Down),
    moment(24, "1994-01-01", person=1, symptom=VariableShift.Up),
    moment(25, "1995-06-01", person=2, anxiety=VariableShift.Up),
    moment(26, "1997-01-01", person=1, functioning=VariableShift.Down),
    moment(27, "1998-06-01", person=1, symptom=VariableShift.Up),
    moment(28, "2000-01-01", person=2, relationship=RelationshipKind.Conflict),
    moment(29, "2001-09-01", person=1, symptom=VariableShift.Up),
]
FENN = record(
    asdict(
        Event(id=10, kind=EventKind.Married, person=3, spouse=4, dateTime="1950-06-01")
    ),
    *CLIMB,
    asdict(Event(id=30, kind=EventKind.Death, person=4, dateTime="2015-01-01")),
    people=4,
)


def test_a_climb_over_more_than_ten_years_in_a_long_history_is_kept_on_one_ask():
    # R-0850, R-0856, R-0846
    """Eleven and a half years of a sixty-five-year history is a period; the
    whole history as one is refused with the reason that it covers more than
    half of the diagram's dated years."""
    climb = [event["id"] for event in CLIMB]
    with replies(answers(named(*climb, name="After the grandmother's death"))) as ask:
        result = detect_clusters(FENN, ask)
    assert ask.call_count == 1
    assert spans(result) == [("1990", "2001")]
    whole = answers(named(10, *climb, 30, name="The family"))
    seen = []
    with replies(whole, whole) as ask:
        with pytest.raises(ClusterError):
            detect_clusters(FENN, ask, heard(seen))
    assert seen == [(1, ClusterCheck.TooLong), (2, ClusterCheck.TooLong)]
    again = " ".join(ask.call_args_list[1].args[0].split())
    assert (
        "reaches from 1950 to 2015, more than half of the years this diagram's "
        "events after its early births cover (1950 to 2015)" in again
    )


def test_a_period_is_measured_against_the_years_a_period_may_hold_not_the_early_births():
    # R-0846
    """Grandparents born in 1921 and 1922 hold no period, so twenty years of a
    history the periods may cover from 1990 to 2025 is most of it, though the
    diagram's dated events reach back more than a century."""
    births = [
        asdict(Event(id=n, kind=EventKind.Birth, child=n, dateTime=f"192{n}-01-01"))
        for n in (1, 2)
    ]
    shifts = [moment(10 + n, f"{1990 + 5 * n}-01-01", person=3) for n in range(8)]
    strain = Cluster(
        id="c1",
        title="A long strain",
        summary="",
        name="A long strain",
        eventIds=[12, 13, 14, 15, 16],
        source=ClusterSource.Model,
    )
    data = record(*births, *shifts, clusters=[strain])
    assert clusters.history_of(joinable(data)) == (
        datetime.date(1990, 1, 1),
        datetime.date(2025, 1, 1),
    )
    [(cluster, check, _)] = clusters.broken(data)
    assert (cluster["id"], check) == ("c1", ClusterCheck.TooLong)


def test_the_proposals_as_given_pass():
    # R-0846, R-0287
    with replies(PROPOSED) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result) == [("1954", "1955"), ("1996", "2001")]
    assert all(1 not in c.eventIds for c in result.clusters)


def test_the_grandfathers_death_joins_the_run_it_fell_in():
    # R-0842
    joined = "Walter's death in early 1998 sits inside Nell and Theo's trouble."
    with replies(
        answers(
            named(2, 3, 4, 5, name="After the marriage"),
            named(9, 10, 11, 12, 13, 14, name="After Walter's death", change=joined),
            declined=["r2"],
        )
    ) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result)[1] == ("1996", "2001")
    assert result.changes == [joined]


def test_the_early_marriage_joined_to_the_first_run_passes_the_check():
    # R-0846, R-0842
    """1948 to 1955 is seven years, never too long: whether the marriage
    belongs with the headaches six years on is the model's call."""
    with replies(
        answers(
            named(1, 2, 3, 4, 5, name="The marriage"),
            named(9, 10, 12, 13, 14, name="Nell and Theo"),
            declined=["r2"],
        )
    ) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result)[0] == ("1948", "1955")


FIFTY_YEARS = already(*ALL_HALE, cluster_id="c1", name="The women of this family")
HALE_STORED = hale(FIFTY_YEARS)


def test_a_stored_group_that_fails_the_check_is_not_handed_back_as_existing():
    # R-0838
    """The fifty-year period is already stored as the model's. It is left out
    of what the model is shown, its id is offered nowhere in the answer's
    shape, and the record change sets it aside, never deletes it."""
    with replies(PROPOSED) as ask:
        result = detect_clusters(HALE_STORED, ask)
    asked = ask.call_args_list[0].args[0]
    assert "PERIODS THIS DIAGRAM HAS\n\n[]" in asked
    assert "The women of this family" not in asked
    assert (
        "id"
        not in ask.call_args_list[0].args[1]["properties"]["clusters"]["items"][
            "properties"
        ]
    )
    assert [c.id for c in result.clusters] == ["c2", "c3"]
    dates = {e["id"]: e["dateTime"] for e in HALE_EVENTS}
    aside = [
        d
        for d in _deltas(HALE_STORED.clusters, result.clusters, dates)
        if d["item_id"] == "c1"
    ]
    assert aside == [
        {"item_kind": "cluster", "item_id": "c1", "field": "setAside", "after": True}
    ]


def test_the_model_handing_back_the_dropped_groups_id_is_refused_as_unknown():
    # R-0838, R-0076
    kept = answers(named(*ALL_HALE, cluster_id="c1", name="The women of this family"))
    with replies(kept, kept) as ask:
        with pytest.raises(ClusterError, match="not one of the app's periods") as refused:
            detect_clusters(HALE_STORED, ask)
    assert refused.value.check is ClusterCheck.UnknownGroup


def test_a_stored_group_within_ten_years_is_still_handed_back():
    # R-0838
    data = hale(already(2, 3, 4, 5, cluster_id="c1", name="After the marriage"))
    with replies(
        answers(
            named(2, 3, 4, 5, cluster_id="c1", name="After the marriage"),
            named(9, 10, 12, 13, 14, name="Nell and Theo"),
            declined=["r2"],
        )
    ) as ask:
        result = detect_clusters(data, ask)
    assert '"id": "c1"' in ask.call_args_list[0].args[0]
    assert [c.id for c in result.clusters] == ["c1", "c2"]


def test_the_prompt_holds_periods_as_hypotheses_with_the_silence_before_each_hint():
    # R-0836, R-0841, R-0850, R-0846
    with replies(PROPOSED) as ask:
        detect_clusters(HALE, ask)
    # the prompt's lines wrap, so phrases are matched on its words alone
    asked = " ".join(ask.call_args_list[0].args[0].split())
    assert "5 years and 8 months with nothing in the diagram before these events" in asked
    assert "1 year and 10 months with nothing in the diagram before these events" in asked
    for sentence in (
        "Each period is a loose hypothesis",
        "a change in who is in the family",
        "how a key member functions",
        "These are examples, not a list",
        "a rise in symptom or anxiety, a fall in functioning, or a relationship shift",
        "A drop in anxiety or a rise in functioning does not",
        "The trouble may begin months before the change",
        "It ends where the events show the family settled",
        "judged against how close together the period's own events fall",
        "never by the person's own trouble or symptom",
        "infer it from what piles up",
        "no visible opening event and no definite end",
        "two periods never cover the same days",
        "Most events stay outside any period",
        "or decline it the same way",
        "never its length, and never its years alone",
        'Never call a period "chronic anxiety" in its name, `reason` or `change`',
    ):
        assert sentence in asked, sentence
    for gone in (
        "separate is the ordinary case",
        "Keep what is there",
        "Never leave out an event listed under",
        "those are fixed, and you cannot change them",
        "A change without that sentence is thrown out",
    ):
        assert gone not in asked, gone


def test_the_silence_is_said_in_years_months_or_days():
    # R-0836
    assert silence(datetime.timedelta(days=38 * 365 + 123)) == "38 years and 4 months"
    assert silence(datetime.timedelta(days=365 + 310)) == "1 year and 10 months"
    assert silence(datetime.timedelta(days=200)) == "6 months"
    assert silence(datetime.timedelta(days=366)) == "1 year"
    assert silence(datetime.timedelta(days=12)) == "12 days"


def test_a_record_whose_first_proposal_has_nothing_before_it_says_so():
    # R-0836
    with replies(
        answers(named(1, 2, 3), named(4, 5, 6, name="The winter after"))
    ) as ask:
        detect_clusters(RECORD, ask)
    asked = ask.call_args_list[0].args[0]
    assert '"before": "the first events in the diagram"' in asked
    assert (
        '"before": "2 years and 2 months with nothing in the diagram before these events"'
        in asked
    )


def parsed(response: ClusterListResponse) -> Parsed:
    return Parsed(
        response, Spent(input=900, output=60), Served("gemini-3.1-flash-lite")
    )


@pytest.fixture
def hale_diagram(test_user):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(HALE_STORED)
    db.session.commit()
    return diagram


def test_a_whole_history_answer_twice_stores_nothing_named_after_years(hale_diagram):
    # R-0846, R-0838, R-0844
    """Through the turn's own path: both answers refused by the ten-year check
    write two cluster_refused rows carrying the model's own answer, the stored
    fifty-year period is set aside, and nothing is stored in its place."""
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(MERGED), parsed(MERGED)],
    ):
        sync(hale_diagram.id, turn_id="t1", user_id=hale_diagram.user_id)
    refused = (
        Observation.query.filter_by(kind=ObservationKind.ClusterRefused)
        .order_by(Observation.id)
        .all()
    )
    assert [(o.detail["attempt"], o.detail["check"]) for o in refused] == [
        (1, "too_long"),
        (2, "too_long"),
    ]
    assert "1948 to 2001" in refused[0].detail["detail"]
    assert (refused[0].detail["name"], refused[0].detail["eventIds"]) == (
        "The women of this family",
        ALL_HALE,
    )
    assert (refused[0].detail["start"], refused[0].detail["end"]) == (
        "1948-06-12",
        "2001-06-30",
    )
    checks = [
        o.detail["check"]
        for o in Observation.query.filter_by(kind=ObservationKind.ClusterFailed)
    ]
    assert checks == ["too_long", "too_long"]
    assert [
        (c["id"], c["setAside"]) for c in hale_diagram.get_diagram_data().clusters
    ] == [("c1", True)]


def own(*event_ids: int, cluster_id="u1", name="The years I was ill") -> Cluster:
    return Cluster(
        id=cluster_id,
        title=name,
        name=name,
        summary="",
        reason="I was not well",
        eventIds=list(event_ids),
        source=ClusterSource.User,
    )


# Shaped like Patrick's own case, fictionalized: the person drew her own run of
# trouble from September 2009 to January 2011; her grandmother's cancer was in
# the autumn of 2008, and her trouble began with a burnout the next spring.
OWN = [20, 21, 22]
WIDER = [30, 31, 20, 21, 22, 32]
GRANDMOTHER = record(
    moment(30, "2008-09-01", person=2, symptom=VariableShift.Up),
    moment(31, "2009-03-01", person=1, functioning=VariableShift.Down),
    moment(20, "2009-09-01", person=1, symptom=VariableShift.Up),
    moment(21, "2010-05-01", person=1, anxiety=VariableShift.Up),
    moment(22, "2011-01-01", person=1, functioning=VariableShift.Down),
    moment(32, "2011-02-01", person=2, kind=EventKind.Death),
    clusters=[own(*OWN)],
)
HYPOTHESIS = "After her grandmother's cancer, 2008"


def test_the_persons_own_period_is_shown_to_the_model_as_theirs():
    # R-0850
    with replies(answers(named(30, 31, 20, name=HYPOTHESIS))) as ask:
        detect_clusters(GRANDMOTHER, ask)
    asked = ask.call_args_list[0].args[0]
    assert '"note": "the person drew this period"' in asked
    assert '"reason": "I was not well"' in asked
    items = ask.call_args_list[0].args[1]["properties"]["clusters"]["items"]
    assert "id" not in items["properties"]


def test_the_persons_own_period_is_kept_as_they_drew_it():
    # R-0850
    """A wider period over her own days is refused twice and nothing of hers
    is reshaped, merged or removed."""
    seen = []
    wider = answers(named(*WIDER, name=HYPOTHESIS))
    with replies(wider, wider) as ask:
        result = detect_clusters(GRANDMOTHER, ask, heard(seen))
    assert seen == [(1, ClusterCheck.Theirs), (2, ClusterCheck.Theirs)]
    assert result.clusters == []
    dates = {e["id"]: e["dateTime"] for e in GRANDMOTHER.events}
    assert _deltas(GRANDMOTHER.clusters, result.clusters, dates) == []


def test_two_periods_sharing_days_are_merged_into_the_one_holding_more():
    # R-0845, R-0844
    """Two of the app's periods over the same years: one family, one reading,
    so they become one period under the larger one's name, and the merge is
    heard with the smaller one's own words."""
    seen = []
    with replies(
        answers(
            named(31, *OWN, name="The years she was unwell"),
            named(30, 31, 32, name=HYPOTHESIS),
        )
    ) as ask:
        result = detect_clusters(
            record(*GRANDMOTHER.events),
            ask,
            lambda n, err, _: seen.append((n, err.check, err.said)),
        )
    assert ask.call_count == 1
    assert [(c.name, c.eventIds) for c in result.clusters] == [
        ("The years she was unwell, 2008–2011", WIDER)
    ]
    assert seen == [
        (
            1,
            ClusterCheck.Merged,
            {
                "name": HYPOTHESIS,
                "eventIds": [30, 31, 32],
                "start": "2008-09-01",
                "end": "2011-02-01",
            },
        )
    ]


INSIDE = record(
    moment(40, "2017-01-10", person=1, anxiety=VariableShift.Up),
    moment(41, "2018-05-01", person=1, anxiety=VariableShift.Up),
    moment(42, "2019-09-01", person=1, anxiety=VariableShift.Up),
    moment(43, "2021-01-01", person=1, anxiety=VariableShift.Up),
    moment(44, "2022-05-01", person=1, anxiety=VariableShift.Up),
    moment(45, "2023-09-01", person=1, anxiety=VariableShift.Up),
    moment(46, "2025-01-01", person=1, anxiety=VariableShift.Up),
    moment(47, "2026-04-01", person=1, anxiety=VariableShift.Up),
    moment(50, "2025-03-01", person=2, symptom=VariableShift.Up),
    moment(51, "2025-09-01", person=2, description="that autumn"),
    moment(52, "2026-02-01", person=2, description="this winter"),
)


def test_a_period_inside_anothers_years_is_merged_not_refused():
    # R-0845
    with replies(
        answers(
            named(40, 41, 42, 43, 44, 45, 46, 47, name="Nine years of it"),
            named(50, 51, 52, name="His bad year"),
        )
    ) as ask:
        result = detect_clusters(INSIDE, ask)
    assert ask.call_count == 1
    assert [(c.name, c.eventIds) for c in result.clusters] == [
        ("Nine years of it, 2017–2026", [40, 41, 42, 43, 44, 45, 46, 50, 51, 52, 47])
    ]


TOUCHING = record(
    moment(60, "2014-01-01", person=1, anxiety=VariableShift.Up),
    moment(61, "2014-09-01", person=1, description="that autumn"),
    moment(62, "2015-06-01", person=1, description="to the next summer"),
    moment(70, "2015-06-01", person=2, symptom=VariableShift.Up),
    moment(71, "2016-01-01", person=2, description="that winter"),
    moment(72, "2016-08-01", person=2, description="to the next summer"),
)


def test_two_periods_that_touch_on_one_day_stay_two():
    # R-0845
    """The page draws neighbouring pills apart at a seam, so touching is a
    closeness it can still draw as two."""
    day = datetime.date(2015, 6, 1)
    assert not overlapping(
        (datetime.date(2014, 1, 1), day), (day, datetime.date(2016, 8, 1))
    )
    with replies(answers(named(60, 61, 62), named(70, 71, 72, name="His turn"))) as ask:
        result = detect_clusters(TOUCHING, ask)
    assert spans(result) == [("2014", "2015"), ("2015", "2016")]


EARLY = [
    moment(60, "1970-02-01", person=2, anxiety=VariableShift.Up),
    moment(61, "1970-05-01", person=2, description="that spring"),
    moment(62, "1970-09-01", person=2, description="that autumn"),
]
UNKNOWN = answers(named(999, 60, 61))


def regrouped(test_user, data: DiagramData):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(data)
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(UNKNOWN), parsed(UNKNOWN)],
    ):
        done = sync(diagram.id, turn_id="t1", user_id=diagram.user_id, force=True)
    aside = [
        o.detail
        for o in Observation.query.filter_by(kind=ObservationKind.ClusterFailed)
        if "setAside" in o.detail
    ]
    drawn = [
        c["id"] for c in diagram.get_diagram_data().clusters if not c["setAside"]
    ]
    return done, aside, drawn


def test_refused_twice_sets_aside_a_stored_model_group_over_half_the_history(
    test_user,
):
    # R-0840, R-0850, R-0846
    """1972 to 2003 is most of the family's 1970 to 2003."""
    done, removed, kept = regrouped(
        test_user,
        record(
            moment(70, "1972-01-01", person=1, anxiety=VariableShift.Up),
            moment(71, "1995-01-01", person=1, description="later"),
            moment(72, "2003-01-01", person=1, description="much later"),
            *EARLY,
            clusters=[
                already(70, 71, 72, cluster_id="c1", name="Thirty-one years"),
                already(60, 61, 62, cluster_id="c2", name="That year"),
            ],
        ),
    )
    assert done is not None
    assert [(r["setAside"], r["check"]) for r in removed] == [("c1", "too_long")]
    assert "(1972-01-01 to 2003-01-01)" in removed[0]["detail"]
    assert kept == ["c2"]


def test_refused_twice_keeps_the_persons_own_and_every_passing_group(test_user):
    # R-0840, R-0844, R-0850
    done, removed, kept = regrouped(
        test_user,
        record(
            *GRANDMOTHER.events,
            *EARLY,
            clusters=[
                own(*OWN),
                already(60, 61, 62, cluster_id="c2", name="That year"),
            ],
        ),
    )
    assert [d["field"] for d in done.change.deltas] == ["clusterCacheKey"]
    assert removed == []
    assert kept == ["u1", "c2"]


def test_refused_twice_with_nothing_stored_names_nothing_and_is_not_asked_again(
    test_user,
):
    # R-0844, R-0850
    done, removed, kept = regrouped(test_user, record(*EARLY))
    assert done is not None
    assert kept == []
    diagram = test_user.free_diagram
    with patch("btcopilot.metered.gemini_structured_sync") as asked:
        assert sync(diagram.id, turn_id="t2", user_id=diagram.user_id) is None
    assert not asked.called


# Shaped like Patrick's own diagram, fictionalized: two stored periods of the
# app's with too few shifts that support them, one with two, one with none,
# and a period the person drew with none.
THIN = record(
    moment(50, "2005-01-01", person=1, symptom=VariableShift.Up),
    moment(51, "2005-08-01", person=1, functioning=VariableShift.Down),
    moment(52, "2006-03-01", person=1, anxiety=VariableShift.Down),
    moment(53, "2010-04-01", person=2, anxiety=VariableShift.Up),
    moment(54, "2010-09-01", person=2, symptom=VariableShift.Up),
    moment(55, "2011-01-01", person=2, functioning=VariableShift.Down),
    asdict(Event(id=60, kind=EventKind.Birth, child=2, dateTime="2017-05-01")),
    asdict(Event(id=61, kind=EventKind.Birth, child=3, dateTime="2020-05-01")),
    moment(62, "2026-01-01", person=1, functioning=VariableShift.Up),
    moment(70, "1990-02-01", person=3, anxiety=VariableShift.Down),
    moment(71, "1990-06-01", person=3, anxiety=VariableShift.Down),
    moment(72, "1990-09-01", person=3, anxiety=VariableShift.Down),
    clusters=[
        already(50, 51, 52, cluster_id="c1", name="A breakup and the first symptoms"),
        already(60, 61, 62, cluster_id="c2", name="Back home and the family grows"),
        own(70, 71, 72),
    ],
)


def test_a_stored_period_with_too_few_shifts_is_handed_back_and_stays_drawn(
    test_user,
):
    # R-0850, R-0853
    """Fewer than three shifts that support a period counts against it on the
    case report and never sets it aside: the two thin periods are handed back
    as existing and stay drawn after the regroup."""
    assert list(clusters.mine(THIN)) == ["c1", "c2", "u1"]
    assert clusters.broken(THIN) == []

    diagram = test_user.free_diagram
    diagram.set_diagram_data(THIN)
    db.session.commit()
    kept = answers(
        named(50, 51, 52, cluster_id="c1", name="A breakup and the first symptoms"),
        named(60, 61, 62, cluster_id="c2", name="Back home and the family grows"),
    )
    kept.declined = [Declined(hint="r2", reason="three reactions with nothing around them")]
    with patch(
        "btcopilot.metered.gemini_structured_sync", side_effect=[parsed(kept)]
    ) as asked:
        sync(diagram.id, turn_id="t1", user_id=diagram.user_id)
    assert '"c1"' in asked.call_args_list[0].args[0]
    assert Observation.query.filter_by(kind=ObservationKind.ClusterFailed).count() == 0
    drawn = diagram.get_diagram_data().drawn_clusters()
    assert sorted(c["id"] for c in drawn) == ["c1", "c2", "u1"]


def test_a_stored_model_group_named_by_its_years_is_not_handed_back(test_user):
    # R-0844, R-0840
    data = hale(
        already(2, 3, 4, 5, cluster_id="c2", name="After the marriage"),
        own(6, 7, 8, cluster_id="u1", name="1985 - 1987"),
        already(9, 10, 12, 13, 14, cluster_id="c1", name="1996–2001"),
    )
    assert list(clusters.mine(data)) == ["c2", "u1"]

    diagram = test_user.free_diagram
    diagram.set_diagram_data(data)
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync", side_effect=[parsed(PROPOSED)]
    ):
        sync(diagram.id, turn_id="t1", user_id=diagram.user_id, force=True)
    failed = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).all()
    assert [(o.detail["setAside"], o.detail["check"]) for o in failed] == [
        ("c1", "years_name")
    ]
    assert "1996–2001 (1996-" in failed[0].detail["detail"]
    stored = {c["id"]: c for c in diagram.get_diagram_data().clusters}
    assert stored["c1"]["setAside"]


SLEEP = record(
    asdict(Event(id=1, kind=EventKind.Death, person=3, dateTime="1998-03-01")),
    moment(
        2, "1997-12-01", person=1, symptom=VariableShift.Up, description="poor sleep"
    ),
    moment(3, "1998-07-01", person=1, functioning=VariableShift.Down),
    moment(4, "1998-10-01", person=1, anxiety=VariableShift.Up),
    moment(5, "1998-11-01", person=2, anxiety=VariableShift.Down),
)


def test_a_period_named_by_the_persons_trouble_is_refused_then_named_plainly():
    # R-0850
    told = answers(named(1, 2, 3, 4, name="The poor sleep year"))
    seen = []
    with replies(told, told) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert seen == [(1, ClusterCheck.SymptomName), (2, ClusterCheck.SymptomName)]
    assert "sleep" in ask.call_args_list[1].args[0]
    assert [c.name for c in result.clusters] == ["A change in the family, 1997–1998"]


def test_a_period_saying_one_event_created_another_is_refused_then_kept_without_it():
    # R-0864, R-0850, R-0569
    caused = answers(
        named(
            1, 2, 3, 4,
            name="After grandfather's death",
            reason="The death and the pressure at work created a period of heightened "
            "anxiety. Your poor sleep came within three months of the death.",
        )
    )
    seen = []
    with replies(caused, caused) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert seen == [(1, ClusterCheck.Cause), (2, ClusterCheck.Cause)]
    assert "'created'" in ask.call_args_list[1].args[0]
    assert [c.reason for c in result.clusters] == [
        "Your poor sleep came within three months of the death."
    ]


def test_a_period_whose_events_fell_around_the_same_time_is_kept_on_one_ask():
    # R-0864
    near = answers(
        named(
            1, 2, 3, 4,
            name="After grandfather's death",
            reason="The death came around the same time as your poor sleep.",
        )
    )
    seen = []
    with replies(near) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert (seen, ask.call_count) == ([], 1)
    assert [c.reason for c in result.clusters] == [
        "The death came around the same time as your poor sleep."
    ]


def test_a_period_in_the_persons_voice_is_refused_and_their_quoted_words_pass():
    # R-0860
    seen = []
    with replies(
        answers(named(1, 2, 3, 4, name="After grandfather's death", reason="I remember my sleep went that winter.")),
        answers(named(1, 2, 3, 4, name="After grandfather's death", reason='You said "my sleep went" that winter.')),
    ) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert seen == [(1, ClusterCheck.FirstPerson)]
    assert "speaks as the person" in ask.call_args_list[1].args[0]
    assert [c.reason for c in result.clusters] == ['You said "my sleep went" that winter.']


# The fictional Reed family: Cal (1) wears out at the mill after his aunt
# Bea (2) is diagnosed; Bea's illness is hers, not his trouble.
REED = record(
    moment(
        70,
        "2001-02-01",
        person=2,
        symptom=VariableShift.Up,
        description="Bea diagnosed with heart failure",
    ),
    moment(
        71,
        "2001-05-01",
        person=1,
        anxiety=VariableShift.Up,
        description="burnout at the mill, sleepless",
    ),
    moment(
        72,
        "2001-09-01",
        person=1,
        functioning=VariableShift.Down,
        description="quit the mill",
    ),
    asdict(Event(id=73, kind=EventKind.Death, person=2, dateTime="2002-01-01")),
)


def test_a_name_from_the_persons_anxiety_or_functioning_is_their_trouble():
    # R-0376, R-0850
    """Words told on the person's own rise in anxiety or fall in functioning
    name their trouble; a relative's illness, a relative and an event's kind
    do not."""
    told = clusters.trouble_words(REED)
    assert clusters.trouble_in("Professional burnout and a move, 2001", told) == [
        "burnout"
    ]
    assert clusters.trouble_in("Aunt Bea's heart failure and death, 2001", told) == []
    seen = []
    with replies(
        answers(named(70, 71, 72, 73, name="Burnout at the mill")),
        answers(named(70, 71, 72, 73, name="Aunt Bea's illness and death")),
    ) as ask:
        result = detect_clusters(REED, ask, heard(seen))
    assert seen == [(1, ClusterCheck.SymptomName)]
    assert [c.name for c in result.clusters] == ["Aunt Bea's illness and death, 2001–2002"]


# The fictional Lowe family: Ida (2), Gus's (1) mother, dies; Gus stops
# calling his brother; the cutoff is his own relationship shift.
LOWE = record(
    moment(80, "2003-01-01", person=2, symptom=VariableShift.Up, description="Ida's stroke"),
    asdict(Event(id=81, kind=EventKind.Death, person=2, dateTime="2003-06-01")),
    moment(
        82,
        "2003-08-01",
        person=1,
        relationship=RelationshipKind.Cutoff,
        description="stopped calling his brother",
    ),
    moment(83, "2003-10-01", person=1, anxiety=VariableShift.Up, description="restless"),
)


def test_a_name_from_the_persons_relationship_shift_is_refused_once_and_renamed():
    # R-0850
    told = clusters.trouble_words(LOWE)
    assert clusters.trouble_in("Ida's death and the cutoff from family, 2003", told) == [
        "cutoff"
    ]
    assert clusters.trouble_in("Ida's death and the stopped calling, 2003", told) == [
        "calling",
        "stopped",
    ]
    assert clusters.trouble_in("Ida's stroke and death, 2003", told) == []
    seen = []
    with replies(
        answers(named(80, 81, 82, 83, name="Ida's death and the cutoff from family, 2003")),
        answers(named(80, 81, 82, 83, name="Ida's stroke and death, 2003")),
    ) as ask:
        result = detect_clusters(LOWE, ask, heard(seen))
    assert seen == [(1, ClusterCheck.SymptomName)]
    assert [c.name for c in result.clusters] == ["Ida's stroke and death, 2003"]


# The fictional Marsh family: Ott (1) clashes with his stepfather (3) and
# moves out to make films; his stepmother Ada (2) is diagnosed and dies.
MARSH = record(
    moment(
        90,
        "2011-01-01",
        person=2,
        symptom=VariableShift.Up,
        description="diagnosed with a heart condition",
    ),
    moment(
        91,
        "2011-03-01",
        person=1,
        relationship=RelationshipKind.Conflict,
        relationshipTargets=[3],
        description="clashed with his stepfather",
    ),
    moment(
        92,
        "2011-06-01",
        person=1,
        anxiety=VariableShift.Up,
        description="moved out to make a movie in the city",
    ),
    asdict(Event(id=93, kind=EventKind.Death, person=2, dateTime="2011-09-01")),
)


def test_a_name_is_checked_word_for_word_and_the_ordinary_relatives_are_free():
    # R-0850, R-0856
    """A word of the person's own events is refused only whole: "move" is not
    "moved", "moving" is not "movie", and "stepmother" is a relative, never
    the person's trouble, though they clashed with their stepfather."""
    told = clusters.trouble_words(MARSH)
    assert clusters.trouble_in("Your stepmother Ada's death, 2011", told) == []
    assert clusters.trouble_in("Ada's illness and Bram moving house, 2011", told) == []
    assert clusters.trouble_in("Ada's death and the move to the city, 2011", told) == [
        "city"
    ]
    seen = []
    stepmother = named(90, 91, 92, 93, name="Your stepmother Ada's death")
    with replies(answers(stepmother)) as ask:
        result = detect_clusters(MARSH, ask, heard(seen))
    assert seen == []
    assert [c.name for c in result.clusters] == ["Your stepmother Ada's death, 2011"]


def test_a_relative_the_person_also_names_is_still_free_to_use_in_a_name():
    # R-0850, R-0856, R-0426
    """When the person's own words say "stepmother", the same whole word in a
    name is still allowed: a word for a relative names who changed, never the
    person's trouble."""
    data = record(*MARSH.events)
    data.events[1] = {**data.events[1], "description": "clashed with his stepmother"}
    told = clusters.trouble_words(data)
    assert "stepmother" not in told
    assert clusters.trouble_in("Your stepmother Ada's death, 2011", told) == []
    assert clusters.trouble_in("Ada's death and the clashed years, 2011", told) == [
        "clashed"
    ]


def test_a_returned_name_with_other_years_than_its_span_is_stored_with_its_span():
    # R-0853
    with replies(
        answers(named(80, 81, 82, 83, name="Ida's stroke and death, 2001\u20132002"))
    ) as ask:
        result = detect_clusters(LOWE, ask)
    assert [(c.name, c.startDate, c.endDate) for c in result.clusters] == [
        ("Ida's stroke and death, 2003", "2003-01-01", "2003-10-01")
    ]
    assert clusters.with_years("After the move (1994 to 96)", "1994-02-01", "1997-01-01") == (
        "After the move, 1994\u20131997"
    )


def test_a_stored_period_named_by_the_persons_trouble_is_renamed_under_its_id():
    # R-0376
    data = record(*REED.events, clusters=[already(70, 71, 72, 73, name="The burnout")])
    renamed = named(
        70,
        71,
        72,
        73,
        cluster_id="c1",
        name="Aunt Bea's illness and death",
        change="Bea's diagnosis and death are what changed.",
    )
    with replies(answers(renamed)) as ask:
        result = detect_clusters(data, ask)
    offered = ask.call_args_list[0].args[0].split("PERIODS THIS DIAGRAM HAS")[1]
    offered = json.loads(offered.split("\n\n")[1])
    assert offered[0]["note"] == clusters.TROUBLE
    dates = {e["id"]: e["dateTime"] for e in data.events}
    assert [
        (d["item_id"], d["after"])
        for d in _deltas(data.clusters, result.clusters, dates)
        if d["field"] == "name"
    ] == [("c1", "Aunt Bea's illness and death, 2001–2002")]


def test_a_period_with_two_shifts_that_count_is_kept_with_its_opening():
    # R-0850
    """The calmer shift does not count, so the death holds two shifts that
    support it: that counts against it on the case report, and the first
    answer is kept as it came, with the event that opened it."""
    opened = named(1, 3, 4, 5, name="After the death")
    opened.openingId = 1
    seen = []
    with replies(answers(opened)) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert (seen, ask.call_count) == ([], 1)
    assert (result.clusters[0].eventIds, result.clusters[0].openingEventId) == (
        [1, 3, 4, 5],
        1,
    )


def test_a_stored_period_is_judged_against_the_data():
    # R-0850
    """One person's shifts make that person's run; the gaps run from the
    opening, negative when the trouble came first; two shifts that count do
    not support a period the person drew."""
    run = clusters.judge({"eventIds": [1, 2, 3, 4], "openingEventId": 1}, SLEEP)
    assert (run.shiftIds, run.runOf, run.opening) == ([2, 3, 4], 1, 1)
    assert (run.toFirst, run.toLast, run.supported) == (-90, 214, True)
    theirs = clusters.judge({"eventIds": [1, 3, 5], "source": "user"}, SLEEP)
    assert not theirs.supported


def test_a_set_aside_cluster_stays_stored_but_is_never_drawn():
    # R-0845, R-0850
    aside = asdict(already(1, 2, 3, cluster_id="c1"))
    aside["setAside"] = True
    data = record(*RECORD.events, clusters=[already(4, 5, 6, cluster_id="c2")])
    data.clusters.append(aside)
    assert [c["id"] for c in data.drawn_clusters()] == ["c2"]
    assert [c["id"] for c in data.clusters] == ["c2", "c1"]


# The fictional Ash family: Rowan (1) says the years after the divorce were the
# worst. In those years her own trouble, her sister Iris's (2) remarriage and
# Iris's fall at work: two shifts that count, so the period is not supported.
ROWAN_SAID = "Honestly the years after my divorce, 2005 to 2006, were the worst."
DIVORCE = "the years after my divorce"
ASH = record(
    moment(40, "2005-03-01", person=1, symptom=VariableShift.Up),
    asdict(
        Event(id=41, kind=EventKind.Married, person=2, spouse=3, dateTime="2006-01-10")
    ),
    moment(42, "2006-08-01", person=2, functioning=VariableShift.Down),
    moment(43, "2009-05-01", person=2, anxiety=VariableShift.Up),
)


def period(message_id: int, name=DIVORCE, words=ROWAN_SAID, years=(2005, 2006)):
    return TheirPeriod(
        messageId=message_id,
        name=name,
        words=words,
        startYear=years and years[0],
        endYear=years and years[1],
    )


def asked(data: DiagramData, message_id: int) -> DiagramData:
    data.questions = [
        {
            "id": "q1",
            "kind": QuestionKind.Fact.value,
            "text": "When in your life was the most going on?",
            "state": QuestionState.Resolved.value,
            "outcome": QuestionOutcome.Answered.value,
            "fact": Fact.MostGoingOn.value,
            "item_kind": ItemKind.Person.value,
            "item_id": 1,
            "answer": {"kind": "statement", "id": message_id, "label": "You said, 3 Oct"},
        }
    ]
    return data


def told_by(discussion, words: str) -> int:
    statement = Statement(
        discussion_id=discussion.id,
        speaker_id=discussion.chat_user_speaker_id,
        text=words,
        order=2,
    )
    db.session.add(statement)
    db.session.commit()
    return statement.id


def grouped_with(discussion, data: DiagramData, *answered: ClusterListResponse):
    diagram = discussion.diagram
    diagram.set_diagram_data(data)
    stored = diagramjson.loads(diagram.data)
    stored["questions"] = data.questions
    diagram.data = diagramjson.dumps(stored)
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(one) for one in answered],
    ) as ask:
        sync(diagram.id, turn_id="t1", user_id=diagram.user_id)
    return diagram.get_diagram_data(), ask


def test_a_period_the_person_names_is_stored_as_theirs(discussion):
    # R-0853
    said = told_by(discussion, ROWAN_SAID)
    data, ask = grouped_with(
        discussion,
        asked(record(*ASH.events), said),
        ClusterListResponse(periods=[period(said)]),
    )
    asked_ = " ".join(ask.call_args_list[0].args[0].split())
    assert ROWAN_SAID in asked_
    assert "Never rename, merge, split, shorten or widen a period of theirs" in asked_
    assert ask.call_args_list[0].kwargs["schema"]["properties"]["periods"]
    [cluster] = data.clusters
    assert (cluster["name"], cluster["source"], cluster["eventIds"]) == (
        DIVORCE,
        ClusterSource.User.value,
        [40, 41, 42],
    )
    assert (cluster["startDate"], cluster["endDate"]) == ("2005-03-01", "2006-08-01")


# Rowan names the long slow crawl from 2008; an earlier reading stored it
# from 2010. The years away, a second period of hers, share its days.
CRAWL = "the long slow crawl"
CRAWL_SAID = "From 2008 to 2011 was the long slow crawl."
AWAY_SAID = "From 2009 to 2011 were the years away."


def test_a_regroup_reads_the_persons_period_again_in_place_of_its_stored_copy():
    # R-0853
    stored = Cluster(
        id="c1",
        title=CRAWL,
        name=CRAWL,
        summary="When was the most going on?",
        reason="When was the most going on?",
        eventIds=[52, 53],
        startDate="2010-01-01",
        endDate="2011-02-07",
        source=ClusterSource.User,
    )
    data = asked(
        record(
            moment(50, "2008-09-01", person=1),
            moment(51, "2009-06-01", person=2),
            moment(52, "2010-01-01", person=1),
            moment(53, "2011-02-07", person=1),
            clusters=[stored],
        ),
        7,
    )
    seen = []
    periods = [
        period(7, name=CRAWL, words=CRAWL_SAID, years=(2008, 2011)),
        period(7, name="the years away", words=AWAY_SAID, years=(2009, 2011)),
    ]
    with replies(ClusterListResponse(periods=periods)) as ask:
        result = detect_clusters(
            data, ask, heard(seen), [Answer(7, MOST, f"{CRAWL_SAID} {AWAY_SAID}")]
        )
    assert '"note": "the person drew this period"' in ask.call_args_list[0].args[0]
    assert seen == [(1, ClusterCheck.Theirs)]
    dates = {e["id"]: e["dateTime"] for e in data.events}
    changed = {
        (d["item_id"], d["field"]): d["after"]
        for d in _deltas(data.clusters, result.clusters, dates)
    }
    assert changed == {
        ("c1", "eventIds"): [50, 51, 52, 53],
        ("c1", "startDate"): "2008-09-01",
        ("c1", "summary"): CRAWL_SAID,
        ("c1", "reason"): CRAWL_SAID,
    }


def test_an_event_told_later_inside_their_period_joins_it_as_they_named_it():
    # R-0853, R-0850
    stored = Cluster(
        id="c1",
        title=CRAWL,
        name=CRAWL,
        summary=CRAWL_SAID,
        reason=CRAWL_SAID,
        eventIds=[52, 53],
        startDate="2010-01-01",
        endDate="2011-02-07",
        source=ClusterSource.User,
    )
    calm = {"functioning": VariableShift.Up}
    data = asked(
        record(
            moment(52, "2010-01-01", **calm),
            moment(53, "2011-02-07", **calm),
            moment(54, "2010-06-01", **calm),
            moment(55, "2012-03-01", **calm),
            clusters=[stored],
        ),
        7,
    )
    with replies(ClusterListResponse()) as ask:
        result = detect_clusters(data, ask, said=[Answer(7, MOST, CRAWL_SAID)])
    dates = {e["id"]: e["dateTime"] for e in data.events}
    assert _deltas(data.clusters, result.clusters, dates) == [
        {"item_kind": "cluster", "item_id": "c1", "field": "eventIds", "after": [52, 53, 54]}
    ]


def test_an_unsupported_period_of_theirs_is_kept_and_judged_unsupported():
    # R-0853
    with replies(ClusterListResponse(periods=[period(7)])) as ask:
        result = detect_clusters(ASH, ask, said=[Answer(7, "When?", ROWAN_SAID)])
    [theirs] = result.clusters
    assert theirs.source is ClusterSource.User
    assert not clusters.judge(asdict(theirs), ASH).supported


def test_a_period_of_theirs_with_two_events_is_stored_as_theirs():
    # R-0853
    data = record(*[e for e in ASH.events if e["id"] != 41])
    seen = []
    with replies(ClusterListResponse(periods=[period(7)])) as ask:
        result = detect_clusters(
            data, ask, heard(seen), [Answer(7, "When?", ROWAN_SAID)]
        )
    [theirs] = result.clusters
    assert (theirs.name, theirs.source, theirs.eventIds) == (
        DIVORCE,
        ClusterSource.User,
        [40, 42],
    )
    assert seen == []


def test_a_period_of_theirs_with_two_events_is_written_to_the_diagram(discussion):
    # R-0853
    """The person's period is theirs at any count from one, through the write
    as through detection; the app's still need three."""
    said = told_by(discussion, ROWAN_SAID)
    data, _ = grouped_with(
        discussion,
        asked(record(*[e for e in ASH.events if e["id"] != 41]), said),
        ClusterListResponse(periods=[period(said)]),
    )
    [theirs] = data.drawn_clusters()
    assert (theirs["source"], theirs["eventIds"]) == (ClusterSource.User.value, [40, 42])
    assert data.clusterCacheKey


def test_ages_the_person_gives_are_read_as_years_from_their_birth_date():
    # R-0853
    born = datetime.date(1978, 4, 1)
    said = "In my late 20s, and when I was 15, not the late 80s, aged 18 to 21"
    assert [(a.said, a.startYear, a.endYear) for a in clusters.ages(said, born)] == [
        ("my late 20s", 2005, 2008),
        ("when I was 15", 1993, 1994),
        ("aged 18 to 21", 1996, 2000),
    ]
    assert clusters.ages(said, None) == []


# Rowan, born in April 1978, opens by repeating the question, then tells the
# period in her own sentence with her ages.
MOST = "Looking back, what were the two or three times when the most was going on?"
OPENER = "The two or three times that stand out to me were the divorce."
LATE = "My late 20s, after the divorce, were the worst, and I barely slept."


def test_a_period_of_theirs_keeps_the_ages_they_gave_and_is_told_in_their_own_sentence():
    # R-0853
    born = asdict(Event(id=39, kind=EventKind.Birth, child=1, dateTime="1978-04-01"))
    data = record(born, *ASH.events)
    shortened = period(7, name="the divorce", words=OPENER, years=(2006, 2006))
    with replies(ClusterListResponse(periods=[shortened])) as ask:
        result = detect_clusters(data, ask, said=[Answer(7, MOST, f"{OPENER} {LATE}")])
    told = json.loads(ask.call_args_list[0].args[0].split("WHEN THE PERSON SAID THE MOST WAS GOING ON")[1])
    assert told["answers"][0]["agesAsYears"] == [
        {"said": "My late 20s", "startYear": 2005, "endYear": 2008}
    ]
    [theirs] = result.clusters
    assert (theirs.eventIds, theirs.summary) == ([40, 41, 42], LATE)
    assert clusters.their_sentence("the divorce", LATE, MOST) == LATE


DECLINED = [Declined(hint="r1", reason="the person's own reading is the one to hear")]


def test_a_period_in_other_words_than_theirs_is_not_written():
    # R-0853
    seen = []
    renamed = period(7, name="After the divorce")
    with replies(ClusterListResponse(periods=[renamed], declined=DECLINED)) as ask:
        result = detect_clusters(
            ASH, ask, heard(seen), [Answer(7, "When?", ROWAN_SAID)]
        )
    assert seen == [(1, ClusterCheck.Renamed), (1, ClusterCheck.Declined)]
    assert result.clusters == []


def test_a_period_with_no_years_is_not_written_and_is_observed(discussion):
    # R-0853
    words = "When everything happened at once, I suppose."
    said = told_by(discussion, words)
    data, _ = grouped_with(
        discussion,
        asked(record(*ASH.events), said),
        ClusterListResponse(
            periods=[
                period(said, name="everything happened at once", words=words, years=None)
            ],
            declined=DECLINED,
        ),
    )
    assert data.clusters == []
    noted = Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all()
    assert [(n.detail["check"], n.detail.get("messageId")) for n in noted] == [
        ("no_years", said),
        ("declined", None),
    ]


def test_a_declined_run_is_observed_and_not_asked_again(discussion):
    # R-0856
    data = record(
        moment(1, "1994-01-01", person=1),
        moment(2, "1994-03-01", person=1),
        moment(3, "1994-05-01", person=2),
    )
    grouped, ask = grouped_with(discussion, data, answers(declined=["r1"]))
    assert grouped.clusters == []
    noted = Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all()
    assert [(n.detail["check"], n.detail["reason"]) for n in noted] == [
        ("declined", "nothing piles up")
    ]
    assert ask.call_count == 1
    assert sync(discussion.diagram.id, turn_id="t2", user_id=discussion.diagram.user_id) is None
    assert ask.call_count == 1


def test_an_answer_closed_before_its_message_was_kept_is_found_in_the_change_log(
    discussion,
):
    # R-0853
    """A question closed as answered before the answer was written on it is
    read from the turn that closed it: the person's message in that turn is
    their answer, and the period they name there is stored as theirs."""
    discussion.chat_user_speaker_id = (
        Speaker.query.filter_by(discussion_id=discussion.id, type=SpeakerType.Subject)
        .one()
        .id
    )
    said = Statement(
        discussion_id=discussion.id,
        speaker_id=discussion.chat_user_speaker_id,
        text=ROWAN_SAID,
        order=2,
        turn_id="t0",
    )
    db.session.add(said)
    db.session.add(
        Change(
            diagram_id=discussion.diagram_id,
            turn_id="t0",
            author=Author.Coach,
            deltas=[
                {
                    "item_kind": ItemKind.Question.value,
                    "item_id": "q1",
                    "field": "outcome",
                    "before": None,
                    "after": QuestionOutcome.Answered.value,
                }
            ],
        )
    )
    db.session.commit()
    data = asked(record(*ASH.events), said.id)
    del data.questions[0]["answer"]
    data, ask = grouped_with(
        discussion, data, ClusterListResponse(periods=[period(said.id)])
    )
    assert ROWAN_SAID in " ".join(ask.call_args_list[0].args[0].split())
    [cluster] = data.clusters
    assert (cluster["name"], cluster["source"]) == (DIVORCE, ClusterSource.User.value)


def test_the_persons_answer_alone_puts_the_grouping_behind():
    # R-0853
    data = record(*ASH.events)
    data.clusterCacheKey = clusters.compute_cache_key(clusters._events(data))
    assert not clusters.behind(1, data)
    assert clusters.behind(1, asked(data, 7))


def test_editing_what_detection_reads_of_an_event_puts_the_grouping_behind():
    # R-0853
    data = record(*ASH.events)
    data.clusterCacheKey = clusters.compute_cache_key(clusters._events(data))
    for field, value in (
        ("description", "always anxious"),
        ("person", 99),
        ("kind", EventKind.Noted.value),
    ):
        edited = record(*ASH.events)
        edited.events[0][field] = value
        edited.clusterCacheKey = data.clusterCacheKey
        assert clusters.behind(1, edited), field


def test_a_stored_period_with_undated_events_regroups_and_keeps_them(test_user):
    # R-0850
    """An event with no date is never offered, so the answer that hands the
    period back without it is not refused and it stays on it as it was; one
    whose date is unknown is offered like any other, and the opening the
    answer names is stored."""
    after = named(50, 51, 52, 53, 54, cluster_id="c1", name="After the death")
    after.openingId = 51
    diagram = test_user.free_diagram
    diagram.set_diagram_data(
        record(
            moment(50, "1994-01-01", person=1),
            asdict(
                Event(id=51, kind=EventKind.Death, person=2, dateTime="1994-03-01")
            ),
            moment(52, "1994-05-01", person=1),
            moment(53, "1994-08-01", person=1),
            moment(54, "1994-04-01", person=1, dateCertainty=DateCertainty.Unknown),
            asdict(
                Event(id=55, kind=EventKind.Shift, person=1, anxiety=VariableShift.Up)
            ),
            clusters=[already(50, 51, 52, 53, 54, 55)],
        )
    )
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[parsed(answers(after))],
    ) as ask:
        sync(diagram.id, turn_id="t1", user_id=diagram.user_id)
    asked = ask.call_args_list[0].args[0]
    offered = asked.split("PERIODS THIS DIAGRAM HAS")[1].split("\n\n")[1]
    assert json.loads(offered)[0]["eventIds"] == [50, 51, 52, 53, 54]
    assert Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all() == []
    [cluster] = diagram.get_diagram_data().clusters
    assert (cluster["eventIds"], cluster["openingEventId"]) == (
        [50, 51, 52, 53, 54, 55],
        51,
    )
    assert (cluster["startDate"], cluster["endDate"]) == ("1994-01-01", "1994-08-01")


def test_an_illness_the_grouping_names_opens_the_period_without_it_the_marriage_does():
    # R-0853, R-0850
    data = record(
        asdict(Event(id=1, kind=EventKind.Married, person=1, spouse=2, dateTime="1994-01-01")),
        moment(2, "1994-06-01", person=1),
        moment(3, "1994-09-01", person=1, kind=EventKind.Shift, functioning=VariableShift.Down, description="illness found"),
        moment(4, "1995-01-01", person=1),
    )
    cluster = {"eventIds": [1, 2, 3, 4]}
    assert clusters.judge(cluster, data).opening == 1
    assert clusters.judge({**cluster, "openingEventId": 3}, data).opening == 3


def test_a_period_naming_events_by_number_is_refused_and_years_pass():
    # R-0864, R-0850
    seen = []
    with replies(
        answers(named(1, 2, 3, 4, name="After grandfather's death", reason="Events 41, 51 pile up.")),
        answers(named(1, 2, 3, 4, name="After grandfather's death", reason="Sleep went in 1998.")),
    ) as ask:
        result = detect_clusters(SLEEP, ask, heard(seen))
    assert seen == [(1, ClusterCheck.RawId)]
    assert "never by number" in ask.call_args_list[1].args[0]
    assert [c.reason for c in result.clusters] == ["Sleep went in 1998."]


def test_the_second_answer_with_an_id_is_stored_without_that_sentence():
    # R-0864
    cluster = ModelCluster(
        name="Period c6", eventIds=[1, 2], reason="Sleep went in 1998. Events 41 and 51 pile up."
    )
    clusters._plain(cluster, {1: datetime.date(1998, 1, 1), 2: datetime.date(1998, 6, 1)})
    assert cluster.reason == "Sleep went in 1998."
    assert not clusters.record.ided(cluster.name)
