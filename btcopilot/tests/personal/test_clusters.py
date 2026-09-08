"""The rules make the episodes; the model only names them and says why.

The first half of this file runs without a model at all — that is the point of
the deterministic pass. The second half scripts the model and checks what the
record refuses to store.
"""

import pytest
from mock import patch

from btcopilot.personal.clusters import (
    ClusterError,
    ClusterListResponse,
    ModelCluster,
    candidates,
    detect_clusters,
)
from btcopilot.personal.seed import seed_diagram_data
from btcopilot.schema import (
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


def record(*events: dict, people: int = 3, bonds: list = ()) -> DiagramData:
    return DiagramData(
        people=[asdict(Person(id=n, name=f"P{n}")) for n in range(1, people + 1)],
        events=list(events),
        pair_bonds=[asdict(b) for b in bonds],
    )


def grouped(data: DiagramData) -> list[list[int]]:
    return [c.eventIds for c in candidates(data)]


def test_an_anchor_gathers_the_moves_around_it():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-11-01", person=1, description="stopped sleeping"),
        moment(3, "1994-09-01", person=2, description="someone else entirely"),
    )
    assert grouped(data) == [[1, 2]]


def test_a_move_beyond_the_span_is_a_different_episode():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1996-06-01", person=1, description="two years later"),
    )
    assert grouped(data) == []


def test_structure_dated_before_the_first_shift_is_scaffolding():
    data = record(
        asdict(Event(id=1, kind=EventKind.Birth, child=1, dateTime="1994-01-01")),
        moment(2, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(3, "1994-09-01", person=1, description="and then this"),
    )
    assert grouped(data) == [[2, 3]]


def test_structure_after_the_first_shift_belongs_to_the_episode():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        asdict(
            Event(
                id=2, kind=EventKind.Married, person=1, spouse=2, dateTime="1994-09-01"
            )
        ),
    )
    assert grouped(data) == [[1, 2]]


def test_a_couple_share_an_episode_through_their_pair_bond():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=2, description="her side of it"),
        moment(3, "1994-10-01", person=3, description="a stranger to them"),
        bonds=[PairBond(id=7, person_a=1, person_b=2)],
    )
    assert grouped(data) == [[1, 2]]


def test_a_lone_anchor_with_no_related_move_stays_a_dot():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=2, description="someone else entirely"),
    )
    assert grouped(data) == []


def test_two_anchors_that_reach_the_same_move_are_one_episode():
    data = record(
        moment(1, "1994-01-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-11-01", person=1, description="the middle of it"),
        moment(3, "1995-06-01", person=1, functioning=VariableShift.Down),
    )
    assert grouped(data) == [[1, 2, 3]]


def test_two_years_with_no_anchor_ends_the_episode():
    """The two anchors reach the same middle event, so the rules first put all
    five together; nothing marks the stretch between the anchors, so it breaks
    at the widest silence between them."""
    data = record(
        moment(1, "1990-01-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1990-03-01", person=1, description="the week after"),
        moment(3, "1991-04-01", person=1, description="the quiet middle"),
        moment(4, "1992-06-01", person=1, functioning=VariableShift.Down),
        moment(5, "1992-08-01", person=1, description="right after"),
    )
    assert grouped(data) == [[1, 2, 3], [4, 5]]


def test_a_break_can_leave_an_anchor_standing_alone():
    """When the break takes the only companion away, what is left is an anchor
    with no related move, which is a dot and not an episode."""
    data = record(
        moment(1, "1990-01-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1991-06-01", person=1, description="the quiet middle"),
        moment(3, "1992-10-01", person=1, functioning=VariableShift.Down),
        moment(4, "1992-12-01", person=1, description="right after"),
    )
    assert grouped(data) == [[2, 3, 4]]


def test_an_undated_event_never_enters_an_episode():
    data = record(
        moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
        moment(2, "1994-09-01", person=1, description="dated"),
        moment(3, None, person=1, description="no date at all"),
    )
    assert grouped(data) == [[1, 2]]


def test_a_relationship_move_anchors_an_episode():
    data = record(
        moment(
            1,
            "1994-06-01",
            person=1,
            relationship=RelationshipKind.Conflict,
            relationshipTargets=[2],
        ),
        moment(2, "1994-09-01", person=2, description="her answer to it"),
    )
    assert grouped(data) == [[1, 2]]


CONTAMINATED = {
    2: "his toxic narcissistic gaslighting",
    3: "her codependent enabling of the abuse",
}


def test_the_words_in_a_description_never_move_a_boundary():
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


EPISODE = record(
    moment(1, "1994-06-01", person=1, anxiety=VariableShift.Up),
    moment(2, "1994-09-01", person=1, description="they argued"),
    moment(3, "1997-01-01", person=1, functioning=VariableShift.Down),
    moment(4, "1997-04-01", person=1, description="she stepped back"),
)


def answers(*clusters: ModelCluster) -> ClusterListResponse:
    return ClusterListResponse(clusters=list(clusters))


def named(
    *event_ids: int,
    name="A hard spring",
    reason="one thing led to the next",
    change=None,
):
    return ModelCluster(
        eventIds=list(event_ids), name=name, reason=reason, change=change
    )


def replies(*responses):
    return patch(
        "btcopilot.personal.clusters.gemini_structured_sync",
        side_effect=list(responses),
    )


def test_the_model_names_the_candidates_it_was_given():
    with replies(answers(named(1, 2), named(3, 4, name="The winter after"))):
        result = detect_clusters(EPISODE)
    assert [c.eventIds for c in result.clusters] == [[1, 2], [3, 4]]
    assert [c.name for c in result.clusters] == ["A hard spring", "The winter after"]
    assert all(c.reason for c in result.clusters)


def test_a_grouping_that_names_an_event_the_record_does_not_hold_is_rejected():
    with replies(answers(named(1, 2, 99)), answers(named(1, 2, 99))):
        with pytest.raises(ClusterError, match="99"):
            detect_clusters(EPISODE)


def test_a_group_that_is_not_a_candidate_and_says_no_why_is_rejected():
    joined = named(1, 2, 3, 4)
    with replies(answers(joined), answers(joined)):
        with pytest.raises(ClusterError, match="says no reason"):
            detect_clusters(EPISODE)


def test_the_model_may_join_two_candidates_when_it_says_why():
    with replies(
        answers(named(1, 2, 3, 4, change="the same argument came back in 1997"))
    ):
        result = detect_clusters(EPISODE)
    assert [c.eventIds for c in result.clusters] == [[1, 2, 3, 4]]


def test_an_anchor_may_not_be_left_out():
    left_out = named(1, 2)
    with replies(answers(left_out), answers(left_out)):
        with pytest.raises(ClusterError, match=r"\[3\]"):
            detect_clusters(EPISODE)


def test_one_event_may_not_sit_in_two_groups():
    twice = answers(named(1, 2), named(2, 3, 4, change="it reads both ways"))
    with replies(twice, twice):
        with pytest.raises(ClusterError, match="two clusters"):
            detect_clusters(EPISODE)


def test_a_group_with_no_reason_is_rejected():
    silent = answers(named(1, 2, reason=""), named(3, 4))
    with replies(silent, silent):
        with pytest.raises(ClusterError, match="needs a reason"):
            detect_clusters(EPISODE)


def test_words_from_outside_the_given_definitions_are_rejected():
    """The prompt tells the model to use only the definitions it was handed;
    the record refuses to store the diagnostic vocabulary anyway."""
    outside = answers(
        named(1, 2, name="The codependent spring"),
        named(3, 4, reason="his narcissistic withdrawal set it off"),
    )
    with replies(outside, outside):
        with pytest.raises(ClusterError, match="codepend"):
            detect_clusters(EPISODE)


def test_a_rejected_grouping_is_asked_for_once_more():
    with replies(answers(named(1, 2, 99)), answers(named(1, 2), named(3, 4))) as ask:
        result = detect_clusters(EPISODE)
    assert [c.eventIds for c in result.clusters] == [[1, 2], [3, 4]]
    second = ask.call_args_list[1].args[0]
    assert "thrown out" in second and "99" in second


@pytest.mark.e2e
def test_a_real_model_names_the_seeded_record():
    data = seed_diagram_data()
    proposed = candidates(data)
    result = detect_clusters(data)
    print(f"candidates: {len(proposed)}  named: {len(result.clusters)}")
    for cluster in result.clusters:
        print(f"  {len(cluster.eventIds)} events — {cluster.reason}")
    assert result.clusters
    assert all(cluster.reason for cluster in result.clusters)
