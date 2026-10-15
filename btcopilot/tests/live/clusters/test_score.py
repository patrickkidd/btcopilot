"""The cluster F1 scorer on hand-written groupings of the dense placeholder
case, no model involved. Under live/ these collect with the suite and run with
--e2e (offline with LIVE_REPLAY=only, $0)."""

import pytest

from btcopilot.clusters import ModelCluster, plain_name
from btcopilot.schema import Cluster, ClusterSource, parse_date
from btcopilot.tests.live.clusters.cases import load
from btcopilot.tests.live.clusters.score import Rule, Theirs, score
from btcopilot.tests.live.criterion import once

DENSE = next(case for case in load() if case.name == "dense")
DEATH, LEAVING = (e.eventIds for e in DENSE.expected)


def stored(ids, name="A change in the household", source=ClusterSource.Model, opening=None):
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
    assert (result.clusters.precision, result.clusters.recall) == (pytest.approx(2 / 3), 1.0)
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
    hers = stored([9, 10, 11, 12], name="the hard years at home", source=ClusterSource.User)
    period = Theirs("the hard years at home", 1988, 1989)
    assert scored(hers, stored(LEAVING), theirs=[period]).missed(frozenset({Rule.Theirs})) == []
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
