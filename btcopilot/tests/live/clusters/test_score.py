"""The cluster F1 scorer on hand-written tries of the dense placeholder case
and of the signed deep case, no LLM call. Under live/ these are collected with
the suite and need --e2e (offline with LIVE_REPLAY=only, $0)."""

import dataclasses

import pytest

from btcopilot.clusters import ModelCluster, plain_name
from btcopilot.schema import Cluster, ClusterSource, parse_date
from btcopilot.tests.live.clusters.cases import load
from btcopilot.tests.live.clusters.score import NotCluster, Rule, Theirs, score
from btcopilot.tests.live.criterion import once

DENSE = next(case for case in load() if case.name == "dense")
DEATH, LEAVING = (e.eventIds for e in DENSE.expected)
DEEP = next(case for case in load() if case.name == "deep")
# the dense key with its second cluster held as a hypothesis
HELD = [DENSE.expected[0], dataclasses.replace(DENSE.expected[1], hypothesis=True)]


def stored(
    ids, name="A change in the household", source=ClusterSource.Model, opening=None
):
    return Cluster(
        id=f"c{ids[0]}",
        title=name,
        summary="",
        name=name,
        eventIds=list(ids),
        source=source,
        openingEventId=opening,
    )


def scored(*clusters, theirs=()):
    return score(list(clusters), DENSE.expected, DENSE.data, list(theirs))


@once
def test_a_perfect_grouping_scores_one():
    # R-0856
    result = scored(stored(DEATH, opening=11), stored(LEAVING, opening=15))
    assert (result.clusters.f1, result.members.f1, result.misses) == (1.0, 1.0, [])
    assert result.openings == (2, 2)


@once
def test_a_missing_cluster_costs_recall():
    # R-0856
    result = scored(stored(LEAVING, opening=15))
    assert (result.clusters.precision, result.clusters.recall) == (1.0, 0.5)
    assert result.clusters.f1 == pytest.approx(2 / 3)


@once
def test_an_extra_cluster_costs_precision():
    # R-0856
    result = scored(stored(DEATH), stored(LEAVING), stored([21, 22, 23]))
    assert (result.clusters.precision, result.clusters.recall) == (
        pytest.approx(2 / 3),
        1.0,
    )
    assert result.clusters.f1 == pytest.approx(0.8)


@once
def test_a_wrong_span_pairs_while_half_is_shared_and_costs_event_f1():
    # R-0856
    shifted = scored(stored([11, 12, 13, 21, 22]), stored(LEAVING))
    assert shifted.clusters.f1 == 1.0
    # 9 of the 11 events stored and of the 11 expected are shared
    assert shifted.members.f1 == pytest.approx(9 / 11)
    astray = scored(stored([12, 13, 21, 22, 23, 24]), stored(LEAVING))
    assert (astray.clusters.precision, astray.clusters.recall) == (0.5, 0.5)


@once
def test_the_rules_that_are_not_f1_are_each_named():
    # R-0376, R-0850, R-0853
    when = {e["id"]: parse_date(e["dateTime"]) for e in DENSE.data.events}
    plain = plain_name(ModelCluster(eventIds=DEATH), when)
    result = scored(
        stored(DEATH, name=plain),
        stored([*LEAVING, 12], name="Migraines", opening=14),
        theirs=[Theirs("the hard years at home", 1988, 1989)],
    )
    assert sorted(rule for rule, _ in result.misses) == sorted(
        [
            Rule.TroubleName,
            Rule.TroubleName,
            Rule.UnknownOpening,
            Rule.RunOf,
            Rule.Opening,
            Rule.Opening,
            Rule.Theirs,
        ]
    )


@once
def test_the_persons_period_stored_as_theirs_holds_unless_an_app_period_shares_its_days():
    # R-0853
    hers = stored(
        [9, 10, 11, 12], name="the hard years at home", source=ClusterSource.User
    )
    period = Theirs("the hard years at home", 1988, 1989)
    assert (
        scored(hers, stored(LEAVING), theirs=[period]).missed(frozenset({Rule.Theirs}))
        == []
    )
    overlaid = scored(hers, stored([11, 12, 13]), theirs=[period])
    assert overlaid.missed(frozenset({Rule.Theirs}))


@once
def test_a_cause_word_in_a_sentence_is_a_cause_violation():
    # R-0864
    cluster = stored([21, 22, 23])
    cluster.reason = "The move created a period of strain."
    result = scored(stored(DEATH), stored(LEAVING), cluster)
    assert result.count(Rule.Cause) == 1


@once
def test_first_person_outside_quotes_is_a_voice_violation():
    # R-0860
    cluster = stored([21, 22, 23])
    cluster.summary = "I remember the move."
    result = scored(stored(DEATH), stored(LEAVING), cluster)
    assert result.count(Rule.Voice) == 1


@once
def test_time_closeness_and_quoted_words_pass():
    # R-0860, R-0864
    cluster = stored([21, 22, 23])
    cluster.reason = 'Around the same time, "I couldn\'t sleep", she said.'
    cluster.summary = "The move came around the same time."
    result = scored(stored(DEATH), stored(LEAVING), cluster)
    assert (result.count(Rule.Voice), result.count(Rule.Cause)) == (0, 0)


@once
def test_a_hypothesis_stored_or_left_out_counts_neither_way():
    # R-0856, R-0857
    left_out = score([stored(DEATH, opening=11)], HELD, DENSE.data)
    proposed = score(
        [stored(DEATH, opening=11), stored(LEAVING, opening=15)], HELD, DENSE.data
    )
    for result in (left_out, proposed):
        assert (result.clusters.f1, result.members.f1, result.misses) == (1.0, 1.0, [])
    assert (len(proposed.pairs), len(proposed.hypotheses)) == (1, 1)
    # signed, the same omission costs recall; out of the key, the same
    # proposal costs precision
    assert scored(stored(DEATH, opening=11)).clusters.recall == 0.5
    outside = score(
        [stored(DEATH, opening=11), stored(LEAVING, opening=15)],
        HELD[:1],
        DENSE.data,
    )
    assert outside.clusters.precision == 0.5


@once
def test_a_hypothesis_is_not_checked_for_its_opening_its_persons_shifts_or_its_events():
    # R-0856, R-0857
    tries = [stored(DEATH, opening=11), stored([*LEAVING, 12], opening=16)]
    held = score(tries, HELD, DENSE.data)
    assert (held.clusters.f1, held.members.f1, held.misses) == (1.0, 1.0, [])
    assert held.openings == (1, 1)
    signed = scored(*tries)
    assert sorted(rule for rule, _ in signed.misses) == sorted(
        [Rule.RunOf, Rule.Opening]
    )
    assert signed.members.f1 < 1.0


@once
def test_storing_a_period_the_case_says_is_not_a_cluster_misses():
    # R-0856, R-0857
    told = NotCluster("A death and a move, 1998", [21, 22, 23])
    tries = [stored(DEATH, opening=11), stored(LEAVING, opening=15), stored([21, 22])]
    named = score(tries, DENSE.expected, DENSE.data, not_clusters=[told])
    assert named.missed(frozenset({Rule.NotACluster})) == [
        "'A change in the household' is 'A death and a move, 1998', not a cluster"
    ]
    assert named.clusters.precision == pytest.approx(2 / 3)
    unlisted = scored(*tries)
    assert (unlisted.count(Rule.NotACluster), unlisted.clusters.precision) == (
        0,
        pytest.approx(2 / 3),
    )
    left_out = score(tries[:2], DENSE.expected, DENSE.data, not_clusters=[told])
    assert (left_out.clusters.f1, left_out.misses) == (1.0, [])


@once
def test_the_signed_deep_key_holds_three_clusters_two_hypotheses_and_the_lake_weekend():
    # R-0856, R-0857
    signed = [e for e in DEEP.expected if not e.hypothesis]
    held = [e for e in DEEP.expected if e.hypothesis]
    assert (len(signed), len(held), len(DEEP.not_clusters)) == (3, 2, 1)

    def tried(*clusters):
        return score(list(clusters), DEEP.expected, DEEP.data, [], DEEP.not_clusters)

    three = [stored(e.eventIds) for e in signed]
    alone, with_both = tried(*three), tried(*three, *(stored(e.eventIds) for e in held))
    for result in (alone, with_both):
        assert (result.clusters.f1, result.members.f1) == (1.0, 1.0)
        assert result.count(Rule.NotACluster) == 0
    assert len(with_both.hypotheses) == 2
    weekend = tried(*three, stored(DEEP.not_clusters[0].eventIds))
    assert weekend.count(Rule.NotACluster) == 1
    assert weekend.clusters.precision == pytest.approx(3 / 4)
