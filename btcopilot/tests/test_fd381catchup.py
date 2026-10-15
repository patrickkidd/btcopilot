"""The FD-381 catch-up: the plan says, for every record, whether it is
regrouped and whether its case report is marked out of date, and makes no
model call; the apply writes exactly that plan, each regroup through the
function a coach turn runs and never the case report's refresh, each regroup
as change rows and each mark as the diagram's case_report_forced_out_of_date,
both of which the undo takes back.

Invented names only.
"""

import datetime
import json
from decimal import Decimal

import pytest
from mock import patch

from btcopilot import casereport, diagramjson, record
from btcopilot.admin import admin
from btcopilot.clusters import ClusterListResponse, ModelCluster, compute_cache_key
from btcopilot.extensions import db
from btcopilot.models import (
    Author,
    Change,
    Diagram,
    ModelCall,
    Observation,
    ObservationKind,
    Purpose,
)
from btcopilot.schema import (
    Cluster,
    ClusterSource,
    DateCertainty,
    Event,
    EventKind,
    Person,
    asdict,
)
from btcopilot.tests.test_casereport import card
from btcopilot.tests.test_casereportrewrite import happened
from btcopilot.tests.test_clustersync import (  # noqa: F401
    clusters_of,
    family,
    parsed,
    regrouping,
)
from btcopilot.tests.test_impressions import impress
from btcopilot.tests.test_questions import box

GROUPED = ClusterListResponse(
    clusters=[
        ModelCluster(eventIds=[10, 11, 12, 13, 14, 15], name="A hard year", reason="r")
    ]
)
DEPLOYED = "2026-06-01T00:00:00+00:00"
BEFORE = datetime.datetime(2026, 1, 1)
PER_CALL = Decimal("0.0125")
CALLED = (
    "the grouping cache key differs from the stored one: one grouping call, a second "
    "when the first answer is refused"
)
CURRENT = "the grouping cache key is the stored one"
SAME = (
    "same as a turn: yes for {} of {} regrouped records: each ran "
    "clusters.sync(force=True), the function a coach turn runs, on the record as "
    "stored and the person's answers, and holds the grouping cache key sync computes now"
)
UNLIKE = "; no for diagrams {}: failed, refused, taken back or changed since"


def done(done=0, failed=0, back=0, skipped=0, left=0) -> str:
    planned = done + failed + back + skipped + left
    return (
        f"completed: {planned} planned, {done} done, {failed} failed, {back} taken back, "
        f"{skipped} skipped, {left} not yet written"
    )


def reported(user, name: str) -> Diagram:
    """A record grouped as its events stand, with a case report whose main
    guess the coach wrote."""
    diagram = Diagram(user_id=user.id, name=name, data=diagramjson.dumps({}))
    db.session.add(diagram)
    db.session.commit()
    data = diagram.get_diagram_data()
    data.people = [asdict(Person(id=1, name=name))]
    data.lastItemId = 1
    data.clusterCacheKey = compute_cache_key([])
    diagram.set_diagram_data(data)
    db.session.commit()
    impress(box(diagram, "r1"), text="When things get tense, she goes quiet.")
    card(diagram, "i1", "main_guess", "c1")
    return diagram


@pytest.fixture
def old(test_user_2):
    """A report the coach wrote before the deploy."""
    diagram = reported(test_user_2, "Ada")
    Change.query.filter_by(diagram_id=diagram.id).update({"created_at": BEFORE})
    db.session.commit()
    return diagram


@pytest.fixture
def current(test_user_2, old):
    """A report the coach wrote after the deploy, on a record grouped as its
    events stand."""
    return reported(test_user_2, "Nell")


def paid(user_id: int, turn_id: str, diagram_id: int | None = None) -> None:
    """A grouping call in the ledger."""
    db.session.add(
        ModelCall(
            user_id=user_id,
            diagram_id=diagram_id,
            turn_id=turn_id,
            purpose=Purpose.Cluster,
            model="gemini-3.1-flash-lite",
            input_tokens=900,
            output_tokens=60,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            cost_usd=PER_CALL,
            duration_ms=1,
            tool_calls=0,
        )
    )
    db.session.commit()


@pytest.fixture
def measured(test_user):
    """The last grouping call in the ledger."""
    paid(test_user.id, "t0")


def catchup(flask_app, *args):
    result = flask_app.test_cli_runner().invoke(
        admin, ["fd381-catchup", *args, "--json"]
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout), result.stderr


def planned(flask_app, tmp_path) -> tuple[list[dict], str]:
    rows, _ = catchup(
        flask_app, "plan", "--deployed", DEPLOYED, "--plans", str(tmp_path)
    )
    return rows, rows[0]["plan"]


def calmed(user) -> Diagram:
    """A record whose events support no cluster, with a cluster of the app's
    stored from before the rules changed."""
    calmer = Diagram(user_id=user.id, name="Calmer", data=diagramjson.dumps({}))
    db.session.add(calmer)
    db.session.commit()
    data = calmer.get_diagram_data()
    data.people = [asdict(Person(id=1, name="Bea"))]
    data.events = [
        asdict(
            Event(
                id=20 + n,
                kind=EventKind.Shift,
                person=1,
                dateTime=f"1999-0{n + 1}-01",
                dateCertainty=DateCertainty.Certain,
                description=f"calmer {n}",
                anxiety="down",
            )
        )
        for n in range(3)
    ]
    data.clusters = [
        asdict(
            Cluster(
                id="c1",
                title="A calmer year",
                summary="r",
                eventIds=[20, 21, 22],
                source=ClusterSource.Model,
            )
        )
    ]
    data.lastItemId = 22
    calmer.set_diagram_data(data)
    db.session.commit()
    return calmer


def forced(diagram) -> bool:
    db.session.expire_all()
    return db.session.get(Diagram, diagram.id).case_report_forced_out_of_date


def kept(path: str) -> dict:
    return json.loads(open(path.replace(".json", ".marks.json")).read())


def filed(diagram, entry_id: str, value: str) -> None:
    """A copy of the main guess on another card, written as the record holds
    it, with no change row."""
    stored = diagramjson.loads(diagram.data)
    guess = next(q for q in stored["questions"] if q["id"] == "i1")
    stored["questions"].append({**guess, "id": entry_id, "case_report_card": value})
    diagram.data = diagramjson.dumps(stored)
    db.session.commit()


def marks(rows: list[dict]) -> list[tuple]:
    return [(r["diagram"], r["mark"], r["mark_why"]) for r in rows]


def stale(diagram) -> dict | None:
    db.session.expire_all()
    return casereport.stale(diagram.id, diagram.get_diagram_data())


def test_the_plan_shows_each_record_and_makes_no_model_call(
    flask_app, tmp_path, test_user, family, old, current, measured
):
    # R-0772, R-0850
    changes = Change.query.count()
    with patch("btcopilot.metered.gemini_structured_sync") as asked:
        rows, path = planned(flask_app, tmp_path)

    assert not asked.called
    assert Change.query.count() == changes
    assert [
        (
            r["diagram"],
            r["owner"],
            r["regroup"],
            r["regroup_why"],
            r["mark"],
            r["mark_why"],
            r["estimate_usd"],
        )
        for r in rows
    ] == [
        (
            family.id,
            test_user.username,
            True,
            CALLED,
            False,
            "the coach never wrote a report",
            0.0125,
        ),
        (
            old.id,
            old.user.username,
            False,
            CURRENT,
            True,
            "a card on the report was last written before the deploy",
            0.0,
        ),
        (
            current.id,
            current.user.username,
            False,
            CURRENT,
            False,
            "the coach wrote every card on the report after the deploy",
            0.0,
        ),
    ]
    saved = json.loads(open(path).read())
    assert [d["diagram"] for d in saved["diagrams"]] == [family.id, old.id, current.id]
    assert saved["per_call_usd"] == 0.0125


def test_apply_regroups_only_the_planned_record_through_sync_and_never_refreshes_a_report(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0850
    _, path = planned(flask_app, tmp_path)
    with (
        patch(
            "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
        ) as asked,
        patch("btcopilot.casereport.rewrite") as refreshed,
    ):
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert asked.call_count == 1
    assert not refreshed.called
    assert [c["title"] for c in clusters_of(family).values()] == ["A hard year, 1994"]
    assert clusters_of(old) == clusters_of(current) == {}
    regroup = Change.query.filter(Change.turn_id.like("fd381-catchup:%")).all()
    assert [c.diagram_id for c in regroup] == [family.id]
    spent = ModelCall.query.filter_by(turn_id=regroup[0].turn_id).one()
    assert [
        (r["diagram"], r["done"], r["failed"], r["groups"], r["cost_usd"]) for r in rows
    ] == [
        (family.id, True, False, 1, float(spent.cost_usd)),
        (old.id, True, None, 0, 0.0),
    ]
    assert rows[0]["changes"] == [regroup[0].id]
    assert [r["same_as_turn"] for r in rows] == [True, None]
    assert said.splitlines() == [SAME.format(1, 1), done(done=2)]


def test_apply_marks_only_the_planned_report_out_of_date(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0850
    _, path = planned(flask_app, tmp_path)
    assert stale(old) is None
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        rows, _ = catchup(flask_app, "apply", "--plan", path)

    found = stale(old)
    assert found["change_id"] == Change.query.filter_by(turn_id="c1", diagram_id=old.id).one().id
    assert found["sentence"] == casereport.NEW_WAY
    assert [forced(d) for d in (family, old, current)] == [False, True, False]
    assert stale(current) is None
    assert stale(family) is None
    assert (rows[1]["marked"], rows[1]["changes"]) == ("set", [])
    assert kept(path) == {str(old.id): "set"}


def test_undo_takes_back_the_regroup_and_the_mark(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0850
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    key = family.get_diagram_data().clusterCacheKey

    preview, _ = catchup(flask_app, "undo", "--plan", path)
    assert [(r["diagram"], r["undone"]) for r in preview] == [
        (family.id, False),
        (old.id, False),
    ]
    assert family.get_diagram_data().clusterCacheKey == key

    rows, _ = catchup(flask_app, "undo", "--plan", path, "--yes")
    assert [(r["diagram"], r["undone"], r["refused"]) for r in rows] == [
        (family.id, True, None),
        (old.id, True, None),
    ]
    assert clusters_of(family) == {}
    assert family.get_diagram_data().clusterCacheKey is None
    assert stale(old) is None
    assert not forced(old)
    assert kept(path) == {str(old.id): "cleared"}


def test_limit_writes_that_many_records_and_the_next_run_finishes(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ) as asked:
        rows, said = catchup(flask_app, "apply", "--plan", path, "--limit", "1")
        assert [(r["diagram"], r["done"]) for r in rows] == [
            (family.id, True),
            (old.id, False),
        ]
        assert said.splitlines()[1] == done(done=1, left=1)
        assert stale(old) is None

        rows, said = catchup(flask_app, "apply", "--plan", path)
    assert asked.call_count == 1
    assert [r["done"] for r in rows] == [True, True]
    assert said.splitlines()[1] == done(done=2)
    assert stale(old)


def test_diagram_writes_only_that_record(flask_app, tmp_path, family, old, current):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    with patch("btcopilot.metered.gemini_structured_sync") as asked:
        rows, said = catchup(
            flask_app, "apply", "--plan", path, "--diagram", str(old.id)
        )

    assert not asked.called
    assert [r["diagram"] for r in rows] == [old.id]
    assert clusters_of(family) == {}
    assert stale(old)
    assert said.splitlines()[1] == done(done=1, left=1)


def test_a_grouping_with_no_answer_is_failed_and_not_called_again(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0517
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync",
        side_effect=[TimeoutError(), TimeoutError()],
    ) as asked:
        rows, said = catchup(flask_app, "apply", "--plan", path)
        assert [(r["diagram"], r["done"], r["failed"]) for r in rows[:1]] == [
            (family.id, False, True)
        ]
        assert said.splitlines() == [
            SAME.format(0, 1) + UNLIKE.format(family.id),
            done(done=1, failed=1),
        ]

        catchup(flask_app, "apply", "--plan", path)
    assert asked.call_count == 2
    assert clusters_of(family) == {}


def test_a_regroup_the_record_refuses_is_failed_written_down_and_the_rest_go_on(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0517
    _, path = planned(flask_app, tmp_path)
    refused = record.Invalid(
        "that would leave clusters ['c1'] with fewer than 3 events", ""
    )
    with patch("btcopilot.clusters.sync", side_effect=refused):
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert [(r["diagram"], r["done"], r["failed"]) for r in rows] == [
        (family.id, False, True),
        (old.id, True, None),
    ]
    assert said.splitlines()[1] == done(done=1, failed=1)
    (seen,) = Observation.query.filter_by(kind=ObservationKind.ClusterFailed).all()
    assert seen.diagram_id == family.id
    assert seen.detail["reason"] == "the record refused the regroup"
    assert "fewer than 3 events" in seen.detail["detail"]


def test_a_family_change_after_the_last_card_write_is_said_over_the_mark(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0827
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    happened(old, "noted", "2019-03-01", title="Moved to Leeds")

    found = stale(old)
    assert found["sentence"] == (
        "Ada's “Moved to Leeds” in 2019 was added after the coach wrote this report."
    )
    assert found["change_id"] == Change.query.filter_by(turn_id="e1").one().id


def test_a_card_the_coach_writes_in_a_turn_leaves_the_mark(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0827
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    assert stale(old)["sentence"] == casereport.NEW_WAY

    impress(box(old, "r2"), text="When things get tense, she goes out.")
    card(old, "i2", "main_guess", "c2")
    found = stale(old)
    assert found["sentence"] == casereport.NEW_WAY
    assert found["change_id"] == Change.query.filter_by(turn_id="c2", diagram_id=old.id).one().id


def test_one_card_written_before_the_deploy_marks_the_report_and_the_choice_card_never_does(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0850
    impress(box(old, "r2"), text="She goes quiet and he steps in.")
    card(old, "i2", "coach_guess", "c2")
    filed(current, "i2", "choice")

    rows, _ = planned(flask_app, tmp_path)
    assert marks(rows)[1:] == [
        (old.id, True, "a card on the report was last written before the deploy"),
        (
            current.id,
            False,
            "the coach wrote every card on the report after the deploy",
        ),
    ]


def test_a_report_the_change_log_cannot_place_is_not_marked(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    Change.query.filter_by(diagram_id=current.id).delete()
    db.session.commit()

    rows, path = planned(flask_app, tmp_path)
    assert marks(rows)[2] == (
        current.id,
        False,
        "the change log holds no write of the report's cards",
    )
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    assert Change.query.filter_by(diagram_id=current.id).count() == 0
    assert stale(current) is None


def test_a_card_the_change_log_holds_no_write_of_beside_a_logged_one_is_marked(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    filed(current, "i2", "coach_guess")

    rows, _ = planned(flask_app, tmp_path)
    assert marks(rows)[2] == (
        current.id,
        True,
        "a card on the report was last written before the deploy",
    )


def test_undo_leaves_a_record_changed_since_as_it_is_and_takes_the_rest_back(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    (cluster_id,) = clusters_of(family)
    record.apply(
        family.id,
        [
            {
                "item_kind": "cluster",
                "item_id": cluster_id,
                "field": "title",
                "after": "Renamed",
            }
        ],
        author=Author.User,
        turn_id="u1",
    )

    rows, _ = catchup(flask_app, "undo", "--plan", path, "--yes")
    assert [(r["diagram"], r["undone"], bool(r["refused"])) for r in rows] == [
        (family.id, False, True),
        (old.id, True, False),
    ]
    assert clusters_of(family)[cluster_id]["title"] == "Renamed"
    assert stale(old) is None
    _, said = catchup(flask_app, "apply", "--plan", path)
    assert said.splitlines()[0] == SAME.format(0, 1) + UNLIKE.format(family.id)


def test_an_undone_plan_is_not_written_again_and_no_grouping_is_paid_twice(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ) as asked:
        catchup(flask_app, "apply", "--plan", path)
        catchup(flask_app, "undo", "--plan", path, "--yes")
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert asked.call_count == 1
    assert ModelCall.query.count() == 1
    assert not forced(old)
    assert kept(path) == {str(old.id): "cleared"}
    assert clusters_of(family) == {}
    assert stale(old) is None
    assert [(r["done"], r["undone"]) for r in rows] == [(False, True), (False, True)]
    assert said.splitlines()[1] == done(back=2)


def test_a_report_the_coach_wrote_again_since_the_plan_is_not_marked(
    flask_app, tmp_path, family, old, current
):
    # R-0772, R-0827
    _, path = planned(flask_app, tmp_path)
    impress(box(old, "r2"), text="When things get tense, she goes out.")
    card(old, "i2", "main_guess", "c2")
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert stale(old) is None
    assert not forced(old)
    assert (rows[1]["done"], rows[1]["marked"], rows[1]["skipped"]) == (
        True,
        None,
        "the coach wrote every card again since the plan",
    )
    assert said.splitlines()[1] == done(done=2)


def test_undo_takes_the_mark_back_when_the_regroup_changed_since(
    flask_app, tmp_path, test_user, family, current
):
    # R-0772, R-0827
    impress(box(family, "r1"), text="When things get tense, she goes quiet.")
    card(family, "i1", "main_guess", "c1")
    Change.query.filter_by(diagram_id=family.id).update({"created_at": BEFORE})
    db.session.commit()
    rows, path = planned(flask_app, tmp_path)
    assert (rows[0]["regroup"], rows[0]["mark"]) == (True, True)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    assert stale(family)["sentence"] == casereport.NEW_WAY
    (cluster_id,) = clusters_of(family)
    record.apply(
        family.id,
        [
            {
                "item_kind": "cluster",
                "item_id": cluster_id,
                "field": "name",
                "after": "My own name",
            }
        ],
        author=Author.User,
        turn_id="u1",
        user_id=test_user.id,
    )

    rows, _ = catchup(
        flask_app, "undo", "--plan", path, "--diagram", str(family.id), "--yes"
    )
    assert [
        (r["turn"] and r["turn"].split(":")[0], r["undone"], bool(r["refused"]))
        for r in rows
    ] == [
        (None, True, False),
        ("fd381-catchup", False, True),
    ]
    assert stale(family) is None
    assert not forced(family)
    assert clusters_of(family)[cluster_id]["name"] == "My own name"


def test_a_plan_entry_whose_owner_is_not_the_diagrams_is_not_written(
    flask_app, tmp_path, test_user, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    old.user_id = test_user.id
    db.session.commit()
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert stale(old) is None
    assert not forced(old)
    assert Change.query.filter(Change.turn_id.like(f"%:{old.id}:%")).count() == 0
    assert (rows[1]["done"], rows[1]["skipped"]) == (
        False,
        "its owner is not the plan's",
    )
    assert said.splitlines()[1] == done(done=1, skipped=1)


def test_a_deployed_time_with_an_offset_is_read_as_utc(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    Change.query.filter_by(diagram_id=current.id).update(
        {"created_at": datetime.datetime(2026, 6, 1, 1, 0)}
    )
    db.session.commit()
    rows, _ = catchup(
        flask_app,
        "plan",
        "--deployed",
        "2026-06-01T02:00:00+02:00",
        "--plans",
        str(tmp_path),
    )

    assert marks(rows) == [
        (family.id, False, "the coach never wrote a report"),
        (old.id, True, "a card on the report was last written before the deploy"),
        (
            current.id,
            False,
            "the coach wrote every card on the report after the deploy",
        ),
    ]


def test_a_scratch_copy_is_never_planned(flask_app, tmp_path, family, old, current):
    # R-0772
    old.scratch = True
    db.session.commit()

    rows, _ = planned(flask_app, tmp_path)
    assert [r["diagram"] for r in rows] == [family.id, current.id]


def test_with_nothing_left_to_group_the_apps_clusters_are_set_aside_with_no_call(
    flask_app, tmp_path, test_user_2, family, old, current
):
    # R-0772, R-0850
    calmer = calmed(test_user_2)
    empty = Diagram(user_id=test_user_2.id, name="Empty", data=diagramjson.dumps({}))
    db.session.add(empty)
    db.session.commit()

    rows, path = planned(flask_app, tmp_path)
    assert [(r["diagram"], r["regroup"], r["regroup_why"]) for r in rows[3:]] == [
        (
            calmer.id,
            True,
            "the grouping cache key differs from the stored one and nothing is left "
            "to group: the app's clusters are set aside with no call",
        ),
        (empty.id, False, "nothing to group and no cluster of the app's drawn"),
    ]
    with patch("btcopilot.metered.gemini_structured_sync") as asked:
        catchup(flask_app, "apply", "--plan", path, "--diagram", str(calmer.id))
    assert not asked.called
    assert clusters_of(calmer)["c1"]["setAside"]


def test_an_undone_regroup_with_no_call_is_not_written_again(
    flask_app, tmp_path, test_user_2, family, old, current
):
    # R-0772
    calmer = calmed(test_user_2)
    _, path = planned(flask_app, tmp_path)
    for step in (["apply"], ["undo", "--yes"], ["apply"]):
        catchup(
            flask_app, step[0], "--plan", path, "--diagram", str(calmer.id), *step[1:]
        )

    regroups = Change.query.filter(Change.turn_id.like(f"fd381-catchup:{calmer.id}:%"))
    assert regroups.count() == 1
    assert not clusters_of(calmer)["c1"].get("setAside")


def test_a_run_stopped_after_a_paid_call_does_not_pay_again(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    made = json.loads(open(path).read())["made"]
    paid(family.user_id, f"fd381-catchup:{family.id}:{made}", family.id)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ) as asked:
        rows, said = catchup(flask_app, "apply", "--plan", path)

    assert not asked.called
    assert (rows[0]["failed"], rows[0]["cost_usd"]) == (True, float(PER_CALL))
    assert said.splitlines()[1] == done(done=1, failed=1)


def test_undo_stopped_partway_says_which_rows_it_took_back(
    flask_app, tmp_path, family, old, current
):
    # R-0772
    _, path = planned(flask_app, tmp_path)
    with patch(
        "btcopilot.metered.gemini_structured_sync", return_value=parsed(GROUPED)
    ):
        catchup(flask_app, "apply", "--plan", path)
    (first,) = Change.query.filter(
        Change.turn_id.like(f"fd381-catchup:{family.id}:%")
    ).all()
    second = record.apply(family.id, [], author=Author.Coach, turn_id=first.turn_id)
    real, calls = record.taking_back, []

    def written_between(data, changes):
        # the third and fourth reads are undo_changes taking back each row,
        # newest first: a write between them stops the older one
        calls.append(changes)
        if len(calls) == 4:
            raise record.Conflict(
                {"before": None, "item_kind": "diagram", "item_id": None, "field": "f"},
                1,
            )
        return real(data, changes)

    with patch("btcopilot.record.taking_back", side_effect=written_between):
        rows, _ = catchup(
            flask_app, "undo", "--plan", path, "--diagram", str(family.id), "--yes"
        )

    assert [(r["change"], r["undone"], bool(r["refused"])) for r in rows] == [
        (second.id, True, False),
        (first.id, False, True),
    ]
