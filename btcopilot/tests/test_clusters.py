"""The rules find runs of events as a hint; the model holds each period of
heightened difficulty as a hypothesis and the code only backstops it.

The first half of this file runs without a model at all. The second half
scripts the model and checks what the code drops, merges and keeps.
"""

import datetime
from contextlib import contextmanager

import pytest
from mock import Mock, patch

from btcopilot import clusters
from btcopilot.clusters import (
    MAX_SPAN_YEARS,
    ClusterCheck,
    ClusterError,
    ClusterListResponse,
    ModelCluster,
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
from btcopilot.models import Observation, ObservationKind
from btcopilot.seed import seed_diagram_data
from btcopilot.schema import (
    Cluster,
    ClusterSource,
    DiagramData,
    Event,
    EventKind,
    PairBond,
    Person,
    RelationshipKind,
    VariableShift,
    asdict,
)


def moment(event_id: int, date: str, **kwargs) -> dict:
    kwargs.setdefault("kind", EventKind.Shift)
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
# runs of events decades apart and two strays, a grandparent on the 1948
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
# The three proposals the rules make of it, and the two events in none.
HALE_PROPOSALS = [[2, 3, 4, 5], [6, 7, 8], [9, 10, 12, 13, 14]]
HALE_STRAYS = [1, 11]
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


def test_a_birth_before_anything_is_recorded_is_scaffolding():
    # R-0037, R-0038
    data = record(
        asdict(Event(id=1, kind=EventKind.Birth, child=1, dateTime="1994-01-01")),
        moment(2, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(3, "1994-09-01", person=1, description="and then this"),
        moment(4, "1994-11-01", person=1, description="and this"),
    )
    assert grouped(data) == [[2, 3, 4]]


def test_structure_from_the_recorded_period_belongs_to_the_cluster():
    # R-0037, R-0375
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        asdict(
            Event(
                id=2, kind=EventKind.Married, person=1, spouse=2, dateTime="1994-09-01"
            )
        ),
        moment(3, "1994-11-01", person=1, description="the months after"),
    )
    assert grouped(data) == [[1, 2, 3]]


def test_a_lone_shift_with_no_related_move_stays_a_dot():
    # R-0215
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=2, description="someone else entirely"),
    )
    assert grouped(data) == []


def test_a_break_can_leave_a_shift_standing_alone():
    # R-0215
    """When the break takes the only companion away, what is left is a shift
    with no related move, which is a dot and not a cluster."""
    data = record(
        moment(1, "1990-01-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1991-06-01", person=1, description="the quiet middle"),
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


def test_a_nodal_event_seeds_a_cluster_with_no_variable_on_it():
    # R-0375
    """The nodal kinds seed a cluster on their own; a birth is not one of
    them."""
    data = record(
        asdict(Event(id=1, kind=EventKind.Death, person=1, dateTime="1994-06-01")),
        moment(2, "1994-09-01", person=1, description="the months after"),
        moment(3, "1994-11-01", person=1, description="and the months after that"),
    )
    assert grouped(data) == [[1, 2, 3]]


def test_a_birth_alone_seeds_nothing():
    # R-0037
    data = record(
        asdict(Event(id=1, kind=EventKind.Birth, child=1, dateTime="1994-06-01")),
        moment(2, "1994-09-01", person=1, description="the months after"),
    )
    assert grouped(data) == []


def test_a_nodal_event_opens_the_recorded_period_for_the_births_after_it():
    # R-0038, R-0037
    """The period starts at the first nodal event or shift, so a birth dated
    after an early marriage is no longer scaffolding."""
    data = record(
        asdict(
            Event(
                id=1, kind=EventKind.Married, person=1, spouse=2, dateTime="1950-01-01"
            )
        ),
        asdict(Event(id=2, kind=EventKind.Birth, child=3, dateTime="1952-01-01")),
        moment(3, "1952-06-01", person=3, anxiety=VariableShift.Up),
        moment(4, "1952-09-01", person=3, description="the months after"),
    )
    assert grouped(data) == [[2, 3, 4]]


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
    moment(2, "1994-09-01", person=1, description="they argued"),
    moment(3, "1994-11-01", person=1, description="she stepped back"),
    moment(4, "1997-01-01", person=1, functioning=VariableShift.Down),
    moment(5, "1997-04-01", person=1, description="he moved out"),
    moment(6, "1997-06-01", person=1, description="the summer after"),
)


def answers(*clusters: ModelCluster) -> ClusterListResponse:
    return ClusterListResponse(clusters=list(clusters))


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
    moment(2, "1994-09-01", person=1, description="they argued"),
    moment(3, "1994-11-01", person=1, description="she stepped back"),
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
    group = answer_schema({"c2": {}, "c1": {}})["properties"]["clusters"]["items"]
    assert group["properties"]["id"]["enum"] == ["c1", "c2"]
    assert group["required"] == ["eventIds", "name", "reason"]
    fresh = answer_schema({})["properties"]["clusters"]["items"]
    assert "id" not in fresh["properties"]


# The Hale record: the rules' proposal, the scripted answers the check refuses
# and passes, and the prompt it is given.

MERGED_WHY = (
    "Edith's headaches after the marriage, June's divorce and Nell's own marriage "
    "breaking up while her grandfather died are one story of the women in this family"
)
MERGED = answers(named(*ALL_HALE, name="The women of this family", change=MERGED_WHY))
THREE = answers(
    named(2, 3, 4, 5, name="Edith's headaches"),
    named(6, 7, 8, name="June's divorce"),
    named(9, 10, 12, 13, 14, name="Nell and Theo"),
)


def spans(result) -> list[tuple[str, str]]:
    return [(c.startDate[:4], c.endDate[:4]) for c in result.clusters]


def test_the_hale_record_proposes_three_groups_decades_apart_and_two_strays():
    # R-0837, R-0215
    proposed = candidates(HALE)
    assert [c.eventIds for c in proposed] == HALE_PROPOSALS
    assert [c.startDate for c in proposed] == ["1954-02-10", "1994-03-05", "1996-09-01"]
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


def test_the_three_proposals_as_given_pass():
    # R-0837, R-0287
    with replies(THREE) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result) == [("1954", "1955"), ("1994", "1994"), ("1996", "2001")]
    assert all(1 not in c.eventIds for c in result.clusters)


def test_the_grandfathers_death_joins_the_run_it_fell_in():
    # R-0837, R-0842
    joined = "Walter's death in early 1998 sits inside Nell and Theo's trouble."
    with replies(
        answers(
            named(2, 3, 4, 5, name="Edith's headaches"),
            named(6, 7, 8, name="June's divorce"),
            named(9, 10, 11, 12, 13, 14, name="After Walter's death", change=joined),
        )
    ) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result)[2] == ("1996", "2001")
    assert result.changes == [joined]


def test_the_early_marriage_joined_to_the_first_run_passes_the_check():
    # R-0837, R-0842
    """1948 to 1955 is seven years, under the ceiling: whether the marriage
    belongs with the headaches six years on is the model's call."""
    with replies(
        answers(
            named(1, 2, 3, 4, 5, name="The marriage"),
            named(6, 7, 8, name="June's divorce"),
            named(9, 10, 12, 13, 14, name="Nell and Theo"),
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
    shape, and the record change removes it."""
    with replies(THREE) as ask:
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
    assert [c.id for c in result.clusters] == ["c2", "c3", "c4"]
    dates = {e["id"]: e["dateTime"] for e in HALE_EVENTS}
    removed = [
        d
        for d in _deltas(HALE_STORED.clusters, result.clusters, dates)
        if d["item_id"] == "c1"
    ]
    assert removed == [
        {"item_kind": "cluster", "item_id": "c1", "field": None, "after": None}
    ]


def test_the_model_handing_back_the_dropped_groups_id_is_refused_as_unknown():
    # R-0838, R-0076
    kept = answers(named(*ALL_HALE, cluster_id="c1", name="The women of this family"))
    with replies(kept, kept) as ask:
        with pytest.raises(ClusterError, match="not one this diagram") as refused:
            detect_clusters(HALE_STORED, ask)
    assert refused.value.check is ClusterCheck.UnknownGroup


def test_a_stored_group_within_ten_years_is_still_handed_back():
    # R-0838
    data = hale(already(6, 7, 8, cluster_id="c1", name="June's divorce"))
    with replies(
        answers(
            named(2, 3, 4, 5, name="Edith's headaches"),
            named(6, 7, 8, cluster_id="c1", name="June's divorce"),
            named(9, 10, 12, 13, 14, name="Nell and Theo"),
        )
    ) as ask:
        result = detect_clusters(data, ask)
    assert '"id": "c1"' in ask.call_args_list[0].args[0]
    assert [c.id for c in result.clusters] == ["c2", "c1", "c3"]


def test_the_prompt_holds_periods_as_hypotheses_with_the_silence_before_each_hint():
    # R-0836, R-0841
    with replies(THREE) as ask:
        detect_clusters(HALE, ask)
    # the prompt's lines wrap, so phrases are matched on its words alone
    asked = " ".join(ask.call_args_list[0].args[0].split())
    assert "5 years and 8 months with nothing recorded before this group" in asked
    assert "38 years and 4 months with nothing recorded before this group" in asked
    assert "1 year and 10 months with nothing recorded before this group" in asked
    for sentence in (
        "Each period is a loose hypothesis",
        "some bigger shift happened in the family around then",
        "A shift can be a fall as well as a rise",
        "infer it from what piles up",
        "no visible opening event and no definite end",
        "two periods never cover the same days",
        "Most events stay outside any period",
        "a hint only",
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
    fifty-year period is removed, and nothing is stored in its place."""
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
    assert hale_diagram.get_diagram_data().clusters == []


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
    # R-0843
    with replies(answers(named(*OWN, cluster_id="u1", name="The years I was ill"))) as ask:
        detect_clusters(GRANDMOTHER, ask)
    asked = ask.call_args_list[0].args[0]
    assert '"note": "the person drew this period"' in asked
    assert '"reason": "I was not well"' in asked
    assert ask.call_args_list[0].args[1]["properties"]["clusters"]["items"][
        "properties"
    ]["id"]["enum"] == ["u1"]


def test_a_wider_period_named_for_the_hypothesis_absorbs_the_persons_own():
    # R-0843, R-0841
    with replies(answers(named(*WIDER, name=HYPOTHESIS))) as ask:
        result = detect_clusters(GRANDMOTHER, ask)
    assert [(c.name, c.startDate, c.endDate) for c in result.clusters] == [
        (HYPOTHESIS, "2008-09-01", "2011-02-01")
    ]
    assert result.clusters[0].source is ClusterSource.Model
    dates = {e["id"]: e["dateTime"] for e in GRANDMOTHER.events}
    deltas = _deltas(GRANDMOTHER.clusters, result.clusters, dates)
    assert {"item_kind": "cluster", "item_id": "u1", "field": None, "after": None} in (
        deltas
    )


def test_a_reshaped_persons_own_period_is_kept_under_its_id():
    # R-0843
    with replies(answers(named(*WIDER, cluster_id="u1", name=HYPOTHESIS))) as ask:
        result = detect_clusters(GRANDMOTHER, ask)
    assert [(c.id, c.eventIds, c.source) for c in result.clusters] == [
        ("u1", WIDER, ClusterSource.Model)
    ]


def test_the_persons_own_period_handed_back_as_it_was_stays_theirs():
    # R-0843
    with replies(answers(named(*OWN, cluster_id="u1", name="The years I was ill"))) as ask:
        result = detect_clusters(GRANDMOTHER, ask)
    assert [(c.id, c.source) for c in result.clusters] == [("u1", ClusterSource.User)]


def test_two_periods_sharing_days_are_merged_into_the_one_holding_more():
    # R-0845, R-0844
    """Her own period handed back as it was, beside the model's wider one over
    the same years: one family, one reading, so they become one period under
    the wider one's name, and the merge is heard with her period's own words."""
    seen = []
    with replies(
        answers(
            named(*OWN, cluster_id="u1", name="The years I was ill"),
            named(30, 31, 32, name=HYPOTHESIS),
        )
    ) as ask:
        result = detect_clusters(
            GRANDMOTHER, ask, lambda n, err, _: seen.append((n, err.check, err.said))
        )
    assert ask.call_count == 1
    assert [(c.name, c.eventIds) for c in result.clusters] == [(HYPOTHESIS, WIDER)]
    assert seen == [
        (
            1,
            ClusterCheck.Merged,
            {
                "name": "The years I was ill",
                "eventIds": OWN,
                "start": "2009-09-01",
                "end": "2011-01-01",
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
    removed = [
        o.detail
        for o in Observation.query.filter_by(kind=ObservationKind.ClusterFailed)
        if "removed" in o.detail
    ]
    return done, removed, [c["id"] for c in diagram.get_diagram_data().clusters]


def test_refused_twice_removes_a_stored_model_group_over_ten_years(test_user):
    # R-0840
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
    assert [(r["removed"], r["check"]) for r in removed] == [("c1", "too_long")]
    assert "(1990-01-01 to 2003-01-01)" in removed[0]["detail"]
    assert kept == ["c2"]


def test_refused_twice_keeps_the_persons_own_and_every_passing_group(test_user):
    # R-0840, R-0844
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
    assert done is None
    assert removed == []
    assert kept == ["u1", "c2"]


def test_refused_twice_with_nothing_stored_names_nothing_after_its_years(test_user):
    # R-0844
    done, removed, kept = regrouped(test_user, record(*EARLY))
    assert done is None
    assert kept == []
    assert not test_user.free_diagram.get_diagram_data().clusterCacheKey


def test_a_stored_model_group_named_by_its_years_is_not_handed_back(test_user):
    # R-0844, R-0840
    data = hale(
        already(2, 3, 4, 5, cluster_id="c2", name="Edith's headaches"),
        own(6, 7, 8, cluster_id="u1", name="1985 - 1987"),
        already(9, 10, 12, 13, 14, cluster_id="c1", name="1996–2001"),
    )
    assert list(clusters.mine(data)) == ["c2", "u1"]

    diagram = test_user.free_diagram
    diagram.set_diagram_data(data)
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync", side_effect=[parsed(THREE)]
    ):
        sync(diagram.id, turn_id="t1", user_id=diagram.user_id, force=True)
    failed = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).all()
    assert [(o.detail["removed"], o.detail["check"]) for o in failed] == [
        ("c1", "years_name")
    ]
    assert "1996–2001 (1996-" in failed[0].detail["detail"]
    assert "c1" not in [c["id"] for c in diagram.get_diagram_data().clusters]
