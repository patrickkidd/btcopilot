"""The rules propose a hint; the model surveys the record for its periods and
names them; the code judges each returned cluster on its own.

The first half of this file runs without a model at all: the proposal the model
is shown. The second half scripts the model and checks what the code keeps,
what it drops and why, that one dropped cluster never costs the others, and
that nothing is ever stored under a name made of its years.
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
    judge,
    overlapping,
    silence,
    sync,
    too_long,
)
from btcopilot.extensions import db
from btcopilot.llmutil import Parsed, Served, Spent, Unreadable, gemini_structured_sync
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


# The fictional Hale family, shaped like a fault seen on production: three
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
# The three runs the rules propose, and the two events in none.
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


# The proposal: a hint from the record alone, no model in the loop.


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


def test_the_hale_record_proposes_three_runs_decades_apart_and_two_strays():
    # R-0841, R-0215
    proposed = candidates(HALE)
    assert [c.eventIds for c in proposed] == HALE_PROPOSALS
    assert [c.startDate for c in proposed] == ["1954-02-10", "1994-03-05", "1996-09-01"]
    placed = {i for c in proposed for i in c.eventIds}
    assert [e.id for e in joinable(HALE) if e.id not in placed] == HALE_STRAYS


# The person's own clusters: fixed, their events held out of the hint.


def own(*event_ids: int, cluster_id="u1", name="The years I was ill") -> Cluster:
    return Cluster(
        id=cluster_id,
        title=name,
        name=name,
        summary="",
        eventIds=list(event_ids),
        source=ClusterSource.User,
    )


AROUND = record(
    moment(30, "2008-03-01", person=1, anxiety=VariableShift.Up),
    moment(31, "2008-06-01", person=1, description="that summer"),
    moment(34, "2008-11-01", person=1, description="that autumn"),
    moment(20, "2009-02-01", person=1, symptom=VariableShift.Up),
    moment(21, "2010-05-01", person=1, description="the next year"),
    moment(22, "2011-06-01", person=1, functioning=VariableShift.Down),
    moment(32, "2011-09-01", person=1, description="that autumn too"),
    moment(70, "2015-03-01", person=2, symptom=VariableShift.Up),
    moment(71, "2015-09-01", person=2, description="that autumn"),
    moment(72, "2016-02-01", person=2, description="that winter"),
    clusters=[own(20, 21, 22)],
)


def test_the_hint_is_built_with_the_persons_own_events_held_out():
    # R-0841
    """Her own three events are not the model's to group: they are in no
    proposal and in no list the model is shown, so the hint around them is
    the 2008 run alone."""
    assert [e.id for e in joinable(AROUND)] == [30, 31, 34, 32, 70, 71, 72]
    assert grouped(AROUND) == [[30, 31, 34], [70, 71, 72]]


# The model, scripted.

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
):
    return ModelCluster(
        id=cluster_id, eventIds=list(event_ids), name=name, reason=reason
    )


@contextmanager
def replies(*responses):
    yield Mock(side_effect=list(responses))


def real(prompt: str, schema: dict, limit: int) -> ClusterListResponse:
    return gemini_structured_sync(prompt, ClusterListResponse, schema=schema).value


def spans(result) -> list[tuple[str, str]]:
    return [(c.startDate[:4], c.endDate[:4]) for c in result.clusters]


def test_the_model_names_the_candidates_it_was_given():
    # R-0076, R-0287
    with replies(
        answers(named(1, 2, 3), named(4, 5, 6, name="The winter after"))
    ) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3], [4, 5, 6]]
    assert [c.name for c in result.clusters] == ["A hard spring", "The winter after"]
    assert all(c.reason for c in result.clusters)
    assert ask.call_count == 1


def test_an_event_the_record_does_not_hold_is_left_out_of_the_cluster_it_named():
    # R-0076, R-0841
    """The model may group and name, never invent a member: the invented one
    goes, the cluster stays, and nobody is asked again."""
    with replies(answers(named(1, 2, 3, 99))) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert ask.call_count == 1


def test_the_model_may_join_two_candidates():
    # R-0287, R-0371, R-0842
    with replies(answers(named(1, 2, 3, 4, 5, 6))) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3, 4, 5, 6]]


def test_a_cluster_under_three_events_is_dropped_and_the_rest_kept():
    # R-0215, R-0841
    seen = []
    with replies(
        answers(named(1, 2, 3), named(4, 5, name="A pair"), named(6, name="Alone"))
    ) as ask:
        result = detect_clusters(RECORD, ask, seen.append)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert [(d.check, d.eventIds) for d in seen] == [
        (ClusterCheck.TooSmall, [4, 5]),
        (ClusterCheck.TooSmall, [6]),
    ]
    assert ask.call_count == 1


def test_an_answer_leaving_events_out_is_kept():
    # R-0844, R-0841
    """Most events sit outside any period: the 1997 shift and its months are
    left out, and the one cluster the model named is stored."""
    with replies(answers(named(1, 2, 3))) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert ask.call_count == 1


def test_a_cluster_in_words_from_outside_the_given_terms_is_dropped_and_the_rest_kept():
    # R-0195, R-0841
    seen = []
    with replies(
        answers(named(1, 2, 3, name="The toxic spring"), named(4, 5, 6))
    ) as ask:
        result = detect_clusters(RECORD, ask, seen.append)
    assert [c.eventIds for c in result.clusters] == [[4, 5, 6]]
    assert [d.check for d in seen] == [ClusterCheck.OutsideWords]
    assert "toxic" in seen[0].why
    assert ask.call_count == 1


def test_an_answer_that_cannot_be_read_is_asked_for_once_more():
    # R-0841
    garbled = Unreadable(
        "not the JSON asked for", Served("gemini-3.1-flash-lite"), Spent()
    )
    with replies(garbled, answers(named(1, 2, 3))) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3]]
    assert ask.call_count == 2
    with replies(answers(), answers(named(4, 5, 6))) as ask:
        result = detect_clusters(RECORD, ask)
    assert [c.eventIds for c in result.clusters] == [[4, 5, 6]]
    assert ask.call_count == 2


def test_two_answers_that_cannot_be_read_give_up_and_name_nothing():
    # R-0841, R-0843
    garbled = Unreadable(
        "not the JSON asked for", Served("gemini-3.1-flash-lite"), Spent()
    )
    with replies(garbled, garbled) as ask:
        with pytest.raises(ClusterError) as unread:
            detect_clusters(RECORD, ask)
    assert unread.value.check is ClusterCheck.Unreadable
    assert ask.call_count == 2
    assert not hasattr(clusters, "by_years") and not hasattr(clusters, "years")


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


# The model's own earlier clusters: shown with their ids, free to rename.

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


def test_a_cluster_already_there_is_handed_back_under_its_id():
    # R-0842, R-0371
    with replies(answers(named(1, 2, 3, cluster_id="c1", name=SPRING))) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [("c1", SPRING)]
    asked = ask.call_args_list[0].args[0]
    assert "EXISTING GROUPS" in asked and '"id": "c1"' in asked and SPRING in asked


def test_a_renamed_cluster_is_kept_with_no_reason_asked():
    # R-0842, R-0372
    with replies(
        answers(named(1, 2, 3, cluster_id="c1", name="A better sounding name"))
    ) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [
        ("c1", "A better sounding name")
    ]
    assert ask.call_count == 1


FAR = record(
    moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
    moment(2, "1994-09-01", person=1, description="they argued"),
    moment(3, "1994-11-01", person=1, description="she stepped back"),
    moment(7, "1999-03-01", person=2, description="five years later"),
    clusters=[already(1, 2, 3)],
)


def test_a_reshaped_cluster_is_kept_under_its_id():
    # R-0842, R-0374, R-0194
    """The 18 months the rules reach is a hint, not a wall: an event five years
    on joins the model's own cluster when it says so, and the id stays."""
    assert grouped(FAR) == [[1, 2, 3]]
    with replies(
        answers(named(1, 2, 3, 7, cluster_id="c1", name="The autumn after"))
    ) as ask:
        result = detect_clusters(FAR, ask)
    assert [(c.id, c.eventIds) for c in result.clusters] == [("c1", [1, 2, 3, 7])]


def test_an_id_the_record_does_not_hold_is_dropped_and_the_cluster_kept_as_new():
    # R-0076, R-0841
    with replies(answers(named(1, 2, 3, cluster_id="c99", name=SPRING))) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name) for c in result.clusters] == [("c2", SPRING)]


def test_a_cluster_returned_twice_is_merged_not_refused():
    # R-0841
    with replies(
        answers(
            named(1, 2, cluster_id="c1", name=SPRING),
            named(2, 3, cluster_id="c1", name="Said again"),
        )
    ) as ask:
        result = detect_clusters(KEPT, ask)
    assert [(c.id, c.name, c.eventIds) for c in result.clusters] == [
        ("c1", SPRING, [1, 2, 3])
    ]
    assert ask.call_count == 1


def test_the_answer_may_name_only_the_groups_the_record_holds():
    # R-0517, R-0780
    group = answer_schema({"c2": {}, "c1": {}})["properties"]["clusters"]["items"]
    assert group["properties"]["id"]["enum"] == ["c1", "c2"]
    assert group["required"] == ["eventIds", "name", "reason"]
    assert "change" not in group["properties"]
    fresh = answer_schema({})["properties"]["clusters"]["items"]
    assert "id" not in fresh["properties"]


# The three judgements, cluster by cluster.

THREE = answers(
    named(2, 3, 4, 5, name="Edith's headaches"),
    named(6, 7, 8, name="June's divorce"),
    named(9, 10, 12, 13, 14, name="Nell and Theo"),
)


def test_the_three_hale_runs_as_proposed_are_kept():
    # R-0841, R-0287, R-0844
    with replies(THREE) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result) == [("1954", "1955"), ("1994", "1994"), ("1996", "2001")]
    assert all(1 not in c.eventIds for c in result.clusters)


def test_a_ten_year_cluster_is_dropped_and_the_rest_kept():
    # R-0837, R-0841
    """One cluster from 1954 to 1994 is the history, not a period: it goes,
    with the model's whole answer for it written down, and the 1996 to 2001
    cluster is kept; nobody is asked again."""
    seen = []
    with replies(
        answers(
            named(2, 3, 4, 5, 6, 7, 8, name="The women of this family"),
            named(9, 10, 12, 13, 14, name="Nell and Theo"),
        )
    ) as ask:
        result = detect_clusters(HALE, ask, seen.append)
    assert spans(result) == [("1996", "2001")]
    assert [(d.check, d.name, d.start, d.end, d.eventIds) for d in seen] == [
        (
            ClusterCheck.TooLong,
            "The women of this family",
            "1954-02-10",
            "1994-10-20",
            [2, 3, 4, 5, 6, 7, 8],
        )
    ]
    assert "more than 10 years" in seen[0].why
    assert ask.call_count == 1


def test_without_the_ten_year_judgement_the_long_cluster_is_kept():
    # R-0837
    """What makes the difference is the ceiling: lifted, the forty-year
    cluster is stored."""
    with patch.object(clusters, "MAX_SPAN_YEARS", 100):
        with replies(answers(named(2, 3, 4, 5, 6, 7, 8))) as ask:
            result = detect_clusters(HALE, ask)
    assert spans(result) == [("1954", "1994")]


def test_ten_years_to_the_day_passes_and_a_day_more_is_too_long():
    # R-0837
    day = datetime.date(1990, 1, 1)
    assert not too_long([day, datetime.date(1990 + MAX_SPAN_YEARS, 1, 1)])
    assert too_long([day, datetime.date(1990 + MAX_SPAN_YEARS, 1, 2)])
    assert not too_long([])
    assert not too_long([datetime.date(1996, 2, 29), datetime.date(2006, 2, 28)])


def test_the_grandfathers_death_may_join_the_run_it_fell_in():
    # R-0841, R-0374
    with replies(
        answers(
            named(2, 3, 4, 5, name="Edith's headaches"),
            named(6, 7, 8, name="June's divorce"),
            named(9, 10, 11, 12, 13, 14, name="Nell and Theo"),
        )
    ) as ask:
        result = detect_clusters(HALE, ask)
    assert spans(result)[2] == ("1996", "2001")
    assert 11 in result.clusters[2].eventIds


def test_the_early_marriage_joined_to_the_first_run_is_kept():
    # R-0841, R-0374
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


def test_a_cluster_overlapping_the_persons_own_is_dropped_and_the_rest_kept():
    # R-0839, R-0841
    """The 2008 run stretched to the autumn of 2011 runs over her own 2009 to
    2011: the person's reading wins, the 2015 cluster is kept, and nobody is
    asked again."""
    seen = []
    with replies(
        answers(
            named(30, 31, 34, 32, name="The years around her illness"),
            named(70, 71, 72, name="His bad year"),
        )
    ) as ask:
        result = detect_clusters(AROUND, ask, seen.append)
    assert spans(result) == [("2015", "2016")]
    assert [(d.check, d.name, d.start, d.end) for d in seen] == [
        (
            ClusterCheck.Overlap,
            "The years around her illness",
            "2008-03-01",
            "2011-09-01",
        )
    ]
    assert "'The years I was ill' (2009-02-01 to 2011-06-01)" in seen[0].why
    assert "the person's reading wins" in seen[0].why
    assert ask.call_count == 1


def test_a_cluster_beside_the_persons_own_is_kept():
    # R-0839, R-0841
    with replies(answers(named(30, 31, 34, name="The year before"))) as ask:
        result = detect_clusters(AROUND, ask)
    assert spans(result) == [("2008", "2008")]


def test_the_persons_own_clusters_are_shown_to_the_model_as_fixed():
    # R-0841, R-0839
    with replies(answers(named(30, 31, 34))) as ask:
        detect_clusters(AROUND, ask)
    prompt = ask.call_args_list[0].args[0]
    assert '"name": "The years I was ill"' in prompt
    assert '"from": "2009-02-01"' in prompt and '"to": "2011-06-01"' in prompt
    assert (
        '"id": 20,' not in prompt
        and '"id": 21,' not in prompt
        and '"id": 22,' not in prompt
    )


INSIDE_ONE = [40, 41, 42, 43, 44, 45, 46, 47]
INSIDE_TWO = [50, 51, 52]
# Her run is nine years of shifts about sixteen months apart; his sits inside it.
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
INSIDE_ANSWER = answers(
    named(*INSIDE_TWO, name="His bad year"),
    named(*INSIDE_ONE, name="Nine years of it"),
)


def test_two_overlapping_model_clusters_keep_the_one_with_more_events():
    # R-0839, R-0841
    """One line: of two clusters sharing years the larger stays, whatever the
    order the model wrote them in, and the smaller is written down with the
    name of the one it ran into."""
    seen = []
    with replies(INSIDE_ANSWER) as ask:
        result = detect_clusters(INSIDE, ask, seen.append)
    assert [c.eventIds for c in result.clusters] == [INSIDE_ONE]
    assert [(d.check, d.name, d.eventIds) for d in seen] == [
        (ClusterCheck.Overlap, "His bad year", INSIDE_TWO)
    ]
    assert "'Nine years of it' (2017-01-10 to 2026-04-01)" in seen[0].why
    assert "holds more events" in seen[0].why
    assert ask.call_count == 1


def test_without_the_overlap_judgement_the_nested_clusters_are_both_kept():
    # R-0839
    with patch.object(clusters, "overlapping", return_value=False):
        with replies(INSIDE_ANSWER) as ask:
            result = detect_clusters(INSIDE, ask)
    assert sorted(spans(result)) == [("2017", "2026"), ("2025", "2026")]


TOUCHING = record(
    moment(60, "2014-01-01", person=1, anxiety=VariableShift.Up),
    moment(61, "2014-09-01", person=1, description="that autumn"),
    moment(62, "2015-06-01", person=1, description="to the next summer"),
    moment(70, "2015-06-01", person=2, symptom=VariableShift.Up),
    moment(71, "2016-01-01", person=2, description="that winter"),
    moment(72, "2016-08-01", person=2, description="to the next summer"),
)


def test_two_clusters_that_touch_on_one_day_are_both_kept():
    # R-0839
    """The page draws neighbouring pills apart at a seam, so touching is a
    closeness it can still draw as two."""
    assert grouped(TOUCHING) == [[60, 61, 62], [70, 71, 72]]
    day = datetime.date(2015, 6, 1)
    assert not overlapping(
        (datetime.date(2014, 1, 1), day), (day, datetime.date(2016, 8, 1))
    )
    with replies(answers(named(60, 61, 62), named(70, 71, 72, name="His turn"))) as ask:
        result = detect_clusters(TOUCHING, ask)
    assert spans(result) == [("2014", "2015"), ("2015", "2016")]


def test_an_event_already_in_a_kept_cluster_is_not_in_a_second_one():
    # R-0841
    """Two clusters that share one event where they meet: the larger keeps it,
    the smaller goes on without it."""
    with replies(
        answers(named(60, 61, 62, name="Hers"), named(62, 70, 71, 72, name="His"))
    ) as ask:
        result = detect_clusters(TOUCHING, ask)
    assert [(c.name, c.eventIds) for c in result.clusters] == [
        ("His", [62, 70, 71, 72]),
        ("Hers", [60, 61]),
    ] or [(c.name, c.eventIds) for c in result.clusters] == [("His", [62, 70, 71, 72])]


# A fixture shaped like Patrick's case: his own cluster of thirteen events from
# September 2009 to January 2011, inside a model cluster of eighteen from
# September 2008 to February 2011, and another period elsewhere in the record.

HIS = [
    moment(
        100 + n,
        day,
        person=1,
        symptom=VariableShift.Up if n % 3 == 0 else None,
        description=f"his {n}",
    )
    for n, day in enumerate(
        [
            "2009-09-05",
            "2009-10-12",
            "2009-11-20",
            "2010-01-08",
            "2010-02-14",
            "2010-04-02",
            "2010-05-19",
            "2010-07-07",
            "2010-08-23",
            "2010-10-01",
            "2010-11-11",
            "2010-12-20",
            "2011-01-15",
        ]
    )
]
BEFORE_AND_AFTER = [
    moment(90, "2008-09-01", person=1, anxiety=VariableShift.Up),
    moment(91, "2008-12-01", person=1, description="that winter"),
    moment(92, "2009-03-01", person=1, description="that spring"),
    moment(93, "2011-02-01", person=1, description="after"),
    moment(94, "2011-02-20", person=1, functioning=VariableShift.Down),
]
ELSEWHERE = [
    moment(80, "2019-02-01", person=2, symptom=VariableShift.Up),
    moment(81, "2019-07-01", person=2, description="that summer"),
    moment(82, "2020-01-01", person=2, description="that winter"),
]
LIKE_PATRICK = record(
    *BEFORE_AND_AFTER,
    *HIS,
    *ELSEWHERE,
    clusters=[own(*(e["id"] for e in HIS), name="Between jobs")],
)


def test_the_model_cluster_around_his_own_is_dropped_and_his_and_the_others_kept():
    # R-0841, R-0839
    """The model's eighteen events, his thirteen among them, run from September
    2008 to February 2011 over his own September 2009 to January 2011: the
    model's is dropped, his stays as it was, and the 2019 cluster is kept."""
    seen = []
    eighteen = (
        [e["id"] for e in BEFORE_AND_AFTER[:3]] + [e["id"] for e in HIS] + [93, 94]
    )
    assert len(eighteen) == 18
    with replies(
        answers(
            named(*eighteen, name="The hard years"),
            named(80, 81, 82, name="Her move"),
        )
    ) as ask:
        result = detect_clusters(LIKE_PATRICK, ask, seen.append)
    assert [(c.name, c.eventIds) for c in result.clusters] == [
        ("Her move", [80, 81, 82])
    ]
    assert [(d.check, d.name, d.start, d.end) for d in seen] == [
        (ClusterCheck.Overlap, "The hard years", "2008-09-01", "2011-02-20")
    ]
    assert "'Between jobs' (2009-09-05 to 2011-01-15)" in seen[0].why
    # his thirteen were never the model's to name, so the model's answer for
    # the dropped cluster is written down with only the five it could reach
    assert seen[0].eventIds == [90, 91, 92, 93, 94]
    dates = {e["id"]: e["dateTime"] for e in LIKE_PATRICK.events}
    deltas = _deltas(LIKE_PATRICK.clusters, result.clusters, dates)
    assert not [d for d in deltas if d["item_id"] == "u1"]
    assert ask.call_count == 1


# Stored model clusters that fail a judgement are dropped and never offered.

FIFTY_YEARS = already(*ALL_HALE, cluster_id="c1", name="The women of this family")
HALE_STORED = hale(FIFTY_YEARS)


def test_a_stored_cluster_failing_a_judgement_is_not_offered_and_is_removed():
    # R-0840, R-0838, R-0841
    with replies(THREE) as ask:
        result = detect_clusters(HALE_STORED, ask)
    asked = ask.call_args_list[0].args[0]
    assert "EXISTING GROUPS\n\n[]" in asked
    assert "The women of this family" not in asked
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


def test_a_stored_cluster_overlapping_another_stored_cluster_is_not_offered():
    # R-0840, R-0839
    nested = record(
        *INSIDE.events,
        clusters=[
            already(*INSIDE_ONE, cluster_id="c1", name="Nine years of it"),
            already(*INSIDE_TWO, cluster_id="c2", name="His bad year"),
        ],
    )
    assert clusters.mine(nested) == {}
    straddling = record(
        *AROUND.events,
        clusters=[
            own(20, 21, 22),
            already(30, 31, 34, 32, cluster_id="c1", name="Around it"),
        ],
    )
    assert clusters.mine(straddling) == {}
    beside = record(
        *AROUND.events,
        clusters=[
            own(20, 21, 22),
            already(30, 31, 34, cluster_id="c1", name="The year before"),
        ],
    )
    assert list(clusters.mine(beside)) == ["c1"]


# The prompt the model is given.


def test_the_prompt_says_the_survey_and_shows_the_hint_with_its_silences():
    # R-0841, R-0836
    with replies(THREE) as ask:
        detect_clusters(HALE, ask)
    asked = " ".join(ask.call_args_list[0].args[0].split())
    for sentence in (
        "Survey this family's record the way a clinician does",
        "Most events sit outside any period",
        "keep, rename or reshape them",
        "The groups this person made are fixed",
        "Two periods never share years",
        "The proposed groups are a hint",
        "38 years and 4 months with nothing recorded before this group",
    ):
        assert sentence in asked, sentence
    for gone in ("Keep what is there", "Never leave out", "`change`", "thrown out"):
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


# Through the turn's own path: what is written down and what is stored.


def parsed(response: ClusterListResponse) -> Parsed:
    return Parsed(
        response, Spent(input=900, output=60), Served("gemini-3.1-flash-lite")
    )


def stored_on(test_user, data: DiagramData):
    diagram = test_user.free_diagram
    diagram.set_diagram_data(data)
    db.session.commit()
    return diagram


def test_a_dropped_cluster_is_an_observation_row_carrying_the_models_answer_for_it(
    test_user,
):
    # R-0780, R-0841
    diagram = stored_on(test_user, HALE)
    answer = answers(
        named(2, 3, 4, 5, 6, 7, 8, name="The women of this family"),
        named(9, 10, 12, 13, 14, name="Nell and Theo"),
    )
    with patch("btcopilot.clusters.sync", new=sync):
        with patch(
            "btcopilot.metered.gemini_structured_sync", return_value=parsed(answer)
        ) as asked:
            done = sync(diagram.id, turn_id="t1", user_id=diagram.user_id)
    assert asked.call_count == 1
    assert done is not None
    rows = Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all()
    assert [
        (
            r.detail["check"],
            r.detail["name"],
            r.detail["start"],
            r.detail["end"],
            r.detail["eventIds"],
        )
        for r in rows
    ] == [
        (
            "too_long",
            "The women of this family",
            "1954-02-10",
            "1994-10-20",
            [2, 3, 4, 5, 6, 7, 8],
        )
    ]
    assert "more than 10 years" in rows[0].detail["detail"]
    assert not Observation.query.filter_by(kind=ObservationKind.ClusterFailed).count()
    stored = diagram.get_diagram_data().clusters
    assert [c["title"] for c in stored] == ["Nell and Theo"]


def test_no_fallback_cluster_is_ever_stored(test_user):
    # R-0843, R-0840
    """Two answers that cannot be read: nothing is named, no cluster is made
    from the hint or its years, the failure is written down, and a stored
    cluster failing a judgement is still removed."""
    diagram = stored_on(test_user, HALE_STORED)
    garbled = Unreadable(
        "not the JSON asked for", Served("gemini-3.1-flash-lite"), Spent()
    )
    with patch("btcopilot.clusters.sync", new=sync):
        with patch(
            "btcopilot.metered.gemini_structured_sync", side_effect=[garbled, garbled]
        ):
            done = sync(diagram.id, turn_id="t1", user_id=diagram.user_id, force=True)
    assert done is not None
    assert diagram.get_diagram_data().clusters == []
    failed = (
        Observation.query.filter_by(kind=ObservationKind.ClusterFailed)
        .order_by(Observation.id)
        .all()
    )
    assert [
        (f.detail["check"], f.detail["fallback"], f.detail.get("removed"))
        for f in failed
    ] == [
        ("unreadable", False, None),
        ("too_long", False, "c1"),
    ]
    refused = Observation.query.filter_by(kind=ObservationKind.ClusterRefused).all()
    assert [(r.detail["attempt"], r.detail["check"]) for r in refused] == [
        (1, "unreadable"),
        (2, "unreadable"),
    ]


def test_unreadable_answers_leave_a_passing_stored_cluster_as_it_was(test_user):
    # R-0840
    diagram = stored_on(
        test_user,
        record(
            *AROUND.events,
            clusters=[
                own(20, 21, 22),
                already(30, 31, 34, cluster_id="c1", name="The year before"),
            ],
        ),
    )
    garbled = Unreadable(
        "not the JSON asked for", Served("gemini-3.1-flash-lite"), Spent()
    )
    with patch("btcopilot.clusters.sync", new=sync):
        with patch(
            "btcopilot.metered.gemini_structured_sync", side_effect=[garbled, garbled]
        ):
            done = sync(diagram.id, turn_id="t1", user_id=diagram.user_id, force=True)
    assert done is None
    assert [c["id"] for c in diagram.get_diagram_data().clusters] == ["u1", "c1"]
