import re

import pytest

from btcopilot.case import GUESS, Case, RecordFault, Tool, Untold, tool
from btcopilot.playturn import Untellable
from btcopilot import prompts
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Statement, StatementKind
from btcopilot import playturn
from btcopilot.playturn import PlayTurn
from btcopilot.tests.repo import REPO
from btcopilot.routes import fixtures
from btcopilot.schema import (
    Cluster,
    DiagramData,
    Event,
    EventKind as Kind,
    Person,
    VariableShift,
    asdict,
)
from btcopilot.tests.conftest import Model, called, csrf_token, said

# Invented names only: the Whitlock stand-in family (doc/mockups/family.md).

EVENTS = [
    Event(id=201, kind=Kind.Separated, person=3, spouse=4, dateTime="1980-09-15"),
    Event(id=202, kind=Kind.Noted, person=3, dateTime="1980-09-15", description="Took a room"),
    Event(id=203, kind=Kind.Shift, person=3, dateTime="1981-01-15", symptom=VariableShift.Up),
    Event(id=204, kind=Kind.Divorced, person=3, spouse=4, dateTime="1981-06-15"),
    Event(id=208, kind=Kind.Shift, person=5, dateTime="1982-11-15", symptom=VariableShift.Up),
]


def record() -> DiagramData:
    return DiagramData(
        people=[
            asdict(Person(id=3, name="Marcus")),
            asdict(Person(id=4, name="Delphine")),
            asdict(Person(id=5, name="Corinne")),
        ],
        events=[asdict(e) for e in EVENTS],
        clusters=[
            asdict(Cluster(id="apart", title="Apart", summary="", eventIds=[e.id for e in EVENTS]))
        ],
    )


SHOTS = [
    {
        "date": "1980-09-15",
        "event_ids": [201, 202],
        "fact": "Marcus and Delphine separated, and Marcus took a room.",
    },
    {"date": "1981-01-15", "event_ids": [203], "fact": "Marcus was drinking most nights."},
    {
        "date": "1982-11-15",
        "event_ids": [208],
        "fact": "Your teacher called Delphine.",
        "guess": "My guess: the trouble moved from Marcus to you.",
    },
]


def told(**over) -> dict:
    return {
        "cluster_id": "apart",
        "point": "As Marcus drank less, school got hard for you.",
        "snapshots": SHOTS,
        "question": "Who was looking after the two of you that autumn?",
        **over,
    }


def refused(args: dict) -> str:
    data = record()
    with pytest.raises(Untold) as caught:
        Case.told(args, data.clusters[0], PlayTurn.stored(data, "apart").events)
    return str(caught.value)


def test_a_case_is_one_point_in_three_to_six_dated_snapshots():
    # R-0563
    data = record()
    case = Case.told(told(), data.clusters[0], PlayTurn.stored(data, "apart").events)
    assert [(s.date, s.event_ids) for s in case.snapshots] == [
        ("1980-09-15", [201, 202]),
        ("1981-01-15", [203]),
        ("1982-11-15", [208]),
    ]
    assert case.snapshots[2].guess.startswith(GUESS)
    assert "3 to 6" in refused(told(snapshots=SHOTS[:2]))


def test_a_case_names_only_the_clusters_events_on_their_own_dates_in_order():
    # R-0563, R-0074
    stray = dict(SHOTS[1], event_ids=[999])
    assert "not in this cluster" in refused(told(snapshots=[SHOTS[0], stray, SHOTS[2]]))
    misdated = dict(SHOTS[1], date="1981-02-01")
    assert "dated 1981-02-01" in refused(told(snapshots=[SHOTS[0], misdated, SHOTS[2]]))
    assert "date order" in refused(told(snapshots=[SHOTS[1], SHOTS[0], SHOTS[2]]))
    assert "not x" in refused(told(cluster_id="x"))


def test_a_snapshot_matches_its_events_at_their_own_date_certainty():
    # R-0563
    data = record()
    data.events[1]["dateTime"] = "1980-09-20"
    events = PlayTurn.stored(data, "apart").events
    with pytest.raises(Untold, match=r"events \[202\] are not on it"):
        Case.told(told(), data.clusters[0], events)
    data.events[1]["dateCertainty"] = "approximate"
    assert Case.told(told(), data.clusters[0], events).snapshots[0].event_ids == [201, 202]
    data.events[1]["dateCertainty"] = "unknown"
    assert Case.told(told(), data.clusters[0], events).snapshots[0].event_ids == [201, 202]


def test_a_divorce_on_a_couple_never_marked_married_is_a_record_fault_not_a_drawing():
    # R-0560, R-0563
    data = record()
    data.pair_bonds = [{"id": 21, "person_a": 3, "person_b": 4, "married": False}]
    with pytest.raises(RecordFault, match="Marcus and Delphine have a divorced event but are not marked married"):
        PlayTurn.stored(data, "apart", model=Model()).run()


def test_a_guess_is_marked_as_the_coachs():
    # R-0563
    unmarked = dict(SHOTS[2], guess="The trouble moved from Marcus to you.")
    assert GUESS in refused(told(snapshots=SHOTS[:2] + [unmarked]))


def test_the_play_turn_offers_only_its_tool_and_keeps_the_case(discussion):
    # R-0563, R-0170
    model = Model(called(Tool.PlayByPlay, **told()))
    reply = PlayTurn.stored(record(), "apart", discussion=discussion, model=model).run()

    assert model.offered == [[Tool.PlayByPlay.value]]
    assert "201 1980-09-15" in model.histories[0][-1]["content"]
    assert reply["statement"] == told()["point"]
    assert reply["case"]["snapshots"][1]["event_ids"] == [203]
    kept = db.session.get(Statement, reply["statement_id"])
    assert (kept.kind, kept.text, kept.told_case) == (
        StatementKind.Play,
        told()["point"],
        reply["case"],
    )
    assert [c.turn_id for c in ModelCall.query.all()] == [kept.turn_id]


def test_a_case_the_cluster_does_not_bear_out_is_handed_back_with_why():
    # R-0563
    model = Model(
        called(Tool.PlayByPlay, **told(snapshots=SHOTS[:2])),
        called(Tool.PlayByPlay, **told()),
    )
    reply = PlayTurn.stored(record(), "apart", model=model).run()

    assert reply["case"]["point"] == told()["point"]
    handed = model.histories[1][-1]["content"][0]
    assert handed["is_error"] and "3 to 6" in handed["content"]


def test_a_coach_that_never_tells_the_case_fails_the_turn():
    # R-0563
    with pytest.raises(Untellable, match="couldn't tell this one"):
        PlayTurn.stored(record(), "apart", model=Model(said("Here is what happened."))).run()


def test_the_tool_asks_for_dated_pictures_of_the_clusters_events():
    # R-0563
    shot = tool()["input_schema"]["properties"]["snapshots"]
    assert (shot["minItems"], shot["maxItems"]) == (3, 6)
    assert shot["items"]["required"] == ["date", "event_ids", "fact"]


def test_the_sandbox_fixtures_tell_their_clusters_in_cases_the_server_accepts():
    # R-0563
    for build, chat in ((fixtures.play, fixtures.PLAY_CHAT), (fixtures.whitlock, fixtures.WHITLOCK_CHAT)):
        data = build()
        kept = chat[-1][2]["told_case"]
        turn = PlayTurn.stored(data, kept["cluster_id"])
        assert Case.told(kept, turn.cluster, turn.events).asdict() == kept


def test_the_prompt_asks_for_only_the_dates_and_people_the_point_needs():
    # R-0547, R-0563
    """The coach narrows the point; the code never drops a person to fit a row."""
    wanted = re.sub(r"\s+", " ", prompts.PLAY_BY_PLAY_PROMPT)
    assert re.search(r"only the dates (the point needs )?and (only )?the people the point needs", wanted)


def test_the_page_waits_for_a_play_as_long_as_the_server_can_take():
    # R-0563
    """A slow model fails with the server's error, never a guess on the page."""
    api = (REPO / "web" / "src" / "api.ts").read_text()
    assert f"PLAY_WAIT_S = {playturn.WAIT};" in api


def test_a_call_that_breaks_the_tools_own_schema_is_handed_back_never_a_crash():
    # R-0563, R-0074
    missing = dict(SHOTS[1])
    del missing["fact"]
    assert "snapshots[1].fact is required" in refused(told(snapshots=[SHOTS[0], missing, SHOTS[2]]))
    wrong = dict(SHOTS[1], event_ids="203")
    assert "snapshots[1].event_ids must be an array" in refused(told(snapshots=[SHOTS[0], wrong, SHOTS[2]]))
    assert "point must be a string" in refused(told(point=7))
    model = Model(
        called(Tool.PlayByPlay, **told(snapshots=[SHOTS[0], missing, SHOTS[2]])),
        called(Tool.PlayByPlay, **told()),
    )
    assert PlayTurn.stored(record(), "apart", model=model).run()["case"]["point"] == told()["point"]



def test_a_coach_that_cannot_tell_the_case_in_three_tries_is_a_clear_refusal(web, test_user, monkeypatch):
    # R-0563, R-0182
    """The page says what happened in plain words; never a bare server error."""
    diagram = test_user.free_diagram
    diagram.set_diagram_data(record())
    db.session.commit()
    short = told(snapshots=SHOTS[:2])
    model = Model(*[called(Tool.PlayByPlay, **short) for _ in range(3)])
    monkeypatch.setattr("btcopilot.playturn.CoachModel", lambda *a, **k: model)
    response = web.post("/app/play", json={"cluster_id": "apart"}, headers={"X-CSRFToken": csrf_token(web)})
    assert response.status_code == 422
    assert response.get_data(as_text=True) == "untold: The coach couldn't tell this one; try again."
