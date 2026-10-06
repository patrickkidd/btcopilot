"""The regroup command catches up records whose clusters are behind their
events, without waiting for the person's next turn."""

import json

from mock import patch

from btcopilot.admin import admin
from btcopilot.clusters import ClusterListResponse, ModelCluster, compute_cache_key
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Observation, ObservationKind
from btcopilot.schema import Event, from_dict
from btcopilot.tests.test_clustersync import (  # noqa: F401
    clusters_of,
    family,
    parsed,
    regrouping,
)

GROUPED = ClusterListResponse(
    clusters=[
        ModelCluster(eventIds=[10, 11, 12, 13, 14, 15], name="A hard year", reason="r")
    ]
)


def regroup(flask_app, *args) -> list[dict]:
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "regroup", *args, "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def grouped_now(diagram) -> None:
    """The record as it stands after a grouping that found nothing to keep."""
    data = diagram.get_diagram_data()
    data.clusterCacheKey = compute_cache_key(
        [from_dict(Event, e) for e in data.events]
    )
    diagram.set_diagram_data(data)
    db.session.commit()


def test_the_dry_run_lists_records_behind_their_events_and_calls_no_model(
    flask_app, family
):
    # R-0772, R-0780
    with patch("btcopilot.metered.gemini_structured_sync") as asked:
        rows = regroup(flask_app)
    assert [(r["diagram"], r["why"], r["groups"]) for r in rows] == [
        (family.id, "events changed since the last grouping", 0)
    ]
    assert not asked.called
    assert clusters_of(family) == {}


def test_a_record_with_events_and_no_groups_is_listed_though_its_events_held(
    flask_app, family
):
    # R-0772, R-0780
    grouped_now(family)
    rows = regroup(flask_app)
    assert [r["why"] for r in rows] == ["events and no groups"]


def test_apply_regroups_as_one_change_that_undo_takes_back(flask_app, family):
    # R-0772, R-0780
    grouped_now(family)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        rows = regroup(flask_app, "--apply")
    assert [(r["regrouped"], r["failed"]) for r in rows] == [(1, False)]
    assert [c["title"] for c in clusters_of(family).values()] == ["A hard year"]
    assert ModelCall.query.count() == 1
    assert regroup(flask_app) == []

    undone = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(family.id), str(rows[0]["change"]), "--yes"]
    )
    assert undone.exit_code == 0, undone.output
    assert clusters_of(family) == {}


def test_apply_says_which_records_fell_back_to_their_years(flask_app, family):
    # R-0517, R-0780
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[TimeoutError(), TimeoutError()],
    ):
        rows = regroup(flask_app, "--apply", "--diagram", str(family.id))
    assert [(r["regrouped"], r["failed"]) for r in rows] == [(1, True)]
    assert [c["title"] for c in clusters_of(family).values()] == ["1994"]
    assert Observation.query.filter_by(kind=ObservationKind.ClusterFailed).count() == 1
