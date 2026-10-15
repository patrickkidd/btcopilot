"""The rules find runs of events as a hint; the model holds each period of
heightened difficulty as a hypothesis and the code only backstops it.

The first half of this file runs without a model at all. The second half
scripts the model and checks what the code drops, merges and keeps.
"""

import datetime
import json
from contextlib import contextmanager

import pytest
from google.genai import _transformers
from mock import Mock, patch

from btcopilot import clusters, diagramjson
from btcopilot.clusters import (
    MAX_SPAN_YEARS,
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
    hint = prompt.split("RUNS THE APP'S RULES FOUND (A HINT ONLY)")[1].split("THE PEOPLE")[0]
    assert [
        (run["supportingShifts"], run["default"], run["eventIds"])
        for run in json.loads(hint)
    ] == [(2, False, [1, 2, 3])]


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
    # R-0856, R-0850
    """A run with three or more supporting shifts is the app's default: an
    answer that neither returns it nor declines it is asked again with the
    reason; a run declined with a reason is heard, the rest kept."""
    data = record(
        moment(1, "1994-01-01", person=1),
        moment(2, "1994-03-01", person=1),
        moment(3, "1994-05-01", person=2),
        moment(10, "2010-01-01", person=1),
        moment(11, "2010-02-01", person=2),
        moment(12, "2010-04-01", person=3),
    )
    assert [(c.id, c.strong) for c in candidates(data)] == [("r1", True), ("r2", True)]
    first = answers(named(1, 2, 3))
    second = answers(named(1, 2, 3))
    second.declined = [Declined(run="r2", reason="three reactions to one storm")]
    seen = []
    with replies(first, second) as ask:
        result = detect_clusters(data, ask, heard(seen))
    assert seen == [(1, ClusterCheck.Unanswered), (2, ClusterCheck.Declined)]
    again = ask.call_args_list[1].args[0]
    assert "Run r2 (2010-01-01 to 2010-04-01) has 3 shifts" in again
    assert 'Your last answer was: {"clusters": [{"id": null, "eventIds": [1, 2, 3]' in again
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert answer_schema({}, [], candidates(data))["properties"]["declined"]["items"][
        "properties"
    ]["run"]["enum"] == ["r1", "r2"]


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
    period and counted as support; named as its opening it is refused, then
    kept with no opening; read against the data, the death opens it."""
    opened = named(60, 61, 62, 63, name="Lou's illness and death")
    opened.openingId = 60
    again = named(60, 61, 62, 63, name="Lou's illness and death")
    again.openingId = 60
    seen = []
    with replies(answers(opened), answers(again)) as ask:
        result = detect_clusters(BROOK, ask, heard(seen))
    events = ask.call_args_list[0].args[0].split("EVERY EVENT")[1].split("WHEN THE")[0]
    assert json.loads(events)[0]["dateCertainty"] == "unknown"
    assert seen == [(1, ClusterCheck.UnknownDate), (2, ClusterCheck.UnknownDate)]
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
        declined=[Declined(run=run, reason="nothing piles up") for run in declined],
    )


def named(
    *event_ids: int,
    cluster_id=None,
    name="A hard spring",
    reason="one thing led to the next",
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
    assert [c.name for c in result.clusters] == ["A hard spring", "The winter after"]
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
        "The spring they argued",
        "A hard spring",
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
        reason="one thing led to the next",
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
    assert [(c.id, c.name) for c in result.clusters] == [("c1", SPRING)]
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
    assert [(c.id, c.name) for c in result.clusters] == [("c1", "After the move")]


def test_changing_a_grouping_already_there_passes_its_sentence_on():
    # R-0371, R-0372
    moved = "She stepped back a month later than the record first said."
    with replies(
        answers(named(1, 2, 3, cluster_id="c1", name="The autumn after", change=moved))
    ) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [("c1", "The autumn after")]
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
    # R-0837, R-0215, R-0850
    proposed = candidates(HALE)
    assert [c.eventIds for c in proposed] == HALE_PROPOSALS
    assert [c.startDate for c in proposed] == ["1954-02-10", "1994-03-05", "1996-09-01"]
    assert [len(c.shiftIds) for c in proposed] == [3, 2, 3]
    grouped = {i for c in proposed for i in c.eventIds}
    assert [e.id for e in joinable(HALE) if e.id not in grouped] == HALE_STRAYS


def test_a_whole_history_period_given_twice_fails_the_grouping():
    # R-0837, R-0846
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


def test_a_ten_year_period_is_dropped_and_the_rest_kept():
    # R-0846
    long = answers(
        named(1, 2, 3, 4, 5, 6, 7, 8, name="The women of this family"),
        named(9, 10, 12, 13, 14, name="Nell and Theo"),
    )
    with replies(long, long) as ask:
        result = detect_clusters(HALE, ask)
    assert ask.call_count == 2
    assert [c.name for c in result.clusters] == ["Nell and Theo"]


def test_without_the_ten_year_check_the_merged_answer_is_accepted():
    # R-0837
    with patch.object(clusters, "MAX_SPAN_YEARS", 100):
        with replies(MERGED) as ask:
            result = detect_clusters(HALE, ask)
    assert spans(result) == [("1948", "2001")]


def test_ten_years_to_the_day_passes_and_a_day_more_is_too_long():
    # R-0837
    day = datetime.date(1990, 1, 1)
    assert not too_long([day, datetime.date(1990 + MAX_SPAN_YEARS, 1, 1)])
    assert too_long([day, datetime.date(1990 + MAX_SPAN_YEARS, 1, 2)])
    assert not too_long([])
    assert not too_long([datetime.date(1996, 2, 29), datetime.date(2006, 2, 28)])


def test_the_proposals_as_given_pass():
    # R-0837, R-0287
    with replies(PROPOSED) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result) == [("1954", "1955"), ("1996", "2001")]
    assert all(1 not in c.eventIds for c in result.clusters)


def test_the_grandfathers_death_joins_the_run_it_fell_in():
    # R-0837, R-0842
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
    # R-0837, R-0842
    """1948 to 1955 is seven years, under the ceiling: whether the marriage
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
    # R-0836, R-0841, R-0850
    with replies(PROPOSED) as ask:
        detect_clusters(HALE, ask)
    # the prompt's lines wrap, so phrases are matched on its words alone
    asked = " ".join(ask.call_args_list[0].args[0].split())
    assert "5 years and 8 months with nothing recorded before this group" in asked
    assert "1 year and 10 months with nothing recorded before this group" in asked
    for sentence in (
        "Each period is a loose hypothesis",
        "a change in who is in the family",
        "how a key member functions",
        "These are examples, not a list",
        "a rise in symptom or anxiety, a fall in functioning, or a relationship shift",
        "A drop in anxiety or a rise in functioning does not",
        "The trouble may begin months before the change",
        "about eighteen months either side is usual",
        "never by the person's own trouble or symptom",
        "infer it from what piles up",
        "no visible opening event and no definite end",
        "two periods never cover the same days",
        "Most events stay outside any period",
        "or decline it the same way",
        "never its length, and never its years alone",
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
    assert '"before": "first group in the record"' in asked
    assert (
        '"before": "2 years and 2 months with nothing recorded before this group"'
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
    # R-0837, R-0838, R-0844
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
        ("The years she was unwell", WIDER)
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
        ("Nine years of it", [40, 41, 42, 43, 44, 45, 46, 50, 51, 52, 47])
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


def test_refused_twice_sets_aside_a_stored_model_group_over_ten_years(test_user):
    # R-0840, R-0850
    done, removed, kept = regrouped(
        test_user,
        record(
            moment(70, "1990-01-01", person=1, anxiety=VariableShift.Up),
            moment(71, "1995-01-01", person=1, description="later"),
            moment(72, "2003-01-01", person=1, description="much later"),
            *EARLY,
            clusters=[
                already(70, 71, 72, cluster_id="c1", name="Thirteen years"),
                already(60, 61, 62, cluster_id="c2", name="That year"),
            ],
        ),
    )
    assert done is not None
    assert [(r["setAside"], r["check"]) for r in removed] == [("c1", "too_long")]
    assert "(1990-01-01 to 2003-01-01)" in removed[0]["detail"]
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
    kept.declined = [Declined(run="r2", reason="three reactions with nothing around them")]
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
    assert [c.name for c in result.clusters] == ["Aunt Bea's illness and death"]


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
    offered = json.loads(offered.split("RUNS THE APP'S RULES")[0])
    assert offered[0]["note"] == clusters.TROUBLE
    dates = {e["id"]: e["dateTime"] for e in data.events}
    assert [
        (d["item_id"], d["after"])
        for d in _deltas(data.clusters, result.clusters, dates)
        if d["field"] == "name"
    ] == [("c1", "Aunt Bea's illness and death")]


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
    run = clusters.judge({"eventIds": [1, 2, 3, 4, 5], "openingEventId": 1}, SLEEP)
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


def test_a_regroup_leaves_the_persons_period_as_it_is():
    # R-0853
    stored = asdict(
        Cluster(
            id="c1",
            title=DIVORCE,
            name=DIVORCE,
            summary=ROWAN_SAID,
            reason=ROWAN_SAID,
            eventIds=[40, 41, 42],
            source=ClusterSource.User,
        )
    )
    data = asked(record(*ASH.events), 7)
    data.clusters = [stored]
    seen = []
    with replies(ClusterListResponse(periods=[period(7, years=(2004, 2006))])) as ask:
        result = detect_clusters(
            data, ask, heard(seen), [Answer(7, "When?", ROWAN_SAID)]
        )
    assert '"note": "the person drew this period"' in ask.call_args_list[0].args[0]
    assert seen == [(1, ClusterCheck.Theirs)]
    dates = {e["id"]: e["dateTime"] for e in data.events}
    assert _deltas(data.clusters, result.clusters, dates) == []


def test_an_unsupported_period_of_theirs_is_kept_and_judged_unsupported():
    # R-0853
    with replies(ClusterListResponse(periods=[period(7)])) as ask:
        result = detect_clusters(ASH, ask, said=[Answer(7, "When?", ROWAN_SAID)])
    [theirs] = result.clusters
    assert theirs.source is ClusterSource.User
    assert not clusters.judge(asdict(theirs), ASH).supported


DECLINED = [Declined(run="r1", reason="the person's own reading is the one to hear")]


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
    offered = asked.split("PERIODS THIS DIAGRAM HAS")[1].split("RUNS THE APP'S RULES")[0]
    assert json.loads(offered)[0]["eventIds"] == [50, 51, 52, 53, 54]
    assert Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all() == []
    [cluster] = diagram.get_diagram_data().clusters
    assert (cluster["eventIds"], cluster["openingEventId"]) == (
        [50, 51, 52, 53, 54, 55],
        51,
    )
    assert (cluster["startDate"], cluster["endDate"]) == ("1994-01-01", "1994-08-01")
