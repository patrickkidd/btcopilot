"""The case report against the diagram: out of date once, after the coach last
wrote a card, an event a card rests on changes its date or kind, or a death, a
marriage, a separation, a divorce or a shift with a symptom is added; the
rewrite of every card the coach writes at once, in one model call, run in the
worker and polled by the page; and the catch-up that runs the same rewrite on
every record holding a card, from a saved plan.

Invented names only.
"""

import json
from dataclasses import asdict

import pytest
from mock import patch

from btcopilot import casereport, turnlog
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Change, ModelCall, Observation, ObservationKind, Purpose, TokenMeter
from btcopilot.schema import Person
from btcopilot.tests.conftest import Model, calling, csrf_token, version
from btcopilot.tests.test_casereport import card, cards
from btcopilot.tests.test_impressions import impress
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.tests.test_questions import box, stored
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolName

FELL = "Your sleep went the winter after your mother fell ill."


def happened(diagram, kind, date, person=1, turn="e1", **fields) -> str:
    toolbox = box(diagram, turn)
    if "title" in fields:
        fields["description"] = fields["title"]
    toolbox.call(
        ToolName.EditEvent,
        {"kind": kind, "person": person, "date": date, "date_certainty": "certain", **fields},
    )
    return str(toolbox.data.events[-1]["id"])


def moved(diagram, event_id, turn="e2", **fields):
    box(diagram, turn).call(
        ToolName.EditEvent,
        {"id": int(event_id), "version": version(diagram), "date_certainty": "certain", **fields},
    )


@pytest.fixture
def written(family):
    """Wren's mother Ada; the coach's main guess resting on Wren's sleep
    trouble in 2004."""
    data = family.get_diagram_data()
    data.people.append(asdict(Person(id=2, name="Ada")))
    data.lastItemId = 2
    family.set_diagram_data(data)
    db.session.commit()
    sleep = happened(family, "shift", "2004-09-01", title="Stopped sleeping well", symptom="up")
    impress(box(family, "r1"), text=FELL, evidence=({"kind": "event", "id": sleep},))
    card(family, "i1", "main_guess", "c1")
    return sleep


def out_of_date(family) -> dict | None:
    db.session.expire_all()
    return casereport.stale(family.id, family.get_diagram_data())


def test_a_report_the_coach_never_wrote_is_never_out_of_date(family):
    # R-0825, R-0827
    happened(family, "death", "2010-01-01")

    assert out_of_date(family) is None


@pytest.mark.parametrize(
    "kind, fields, said",
    [
        ("death", {"person": 2}, "Ada's death in 2019 was added after the coach wrote this report."),
        ("married", {"spouse": 2}, "Wren and Ada's marriage in 2019 was added after the coach wrote this report."),
        ("separated", {"spouse": 2}, "Wren and Ada's separation in 2019 was added after the coach wrote this report."),
        ("divorced", {"spouse": 2}, "Wren and Ada's divorce in 2019 was added after the coach wrote this report."),
        (
            "shift",
            {"person": 2, "title": "Got a diagnosis", "symptom": "up"},
            "Ada's “Got a diagnosis” in 2019 was added after the coach wrote this report.",
        ),
    ],
)
def test_an_added_death_marriage_separation_divorce_or_symptom_puts_the_report_out_of_date(
    written, family, kind, fields, said
):
    # R-0827
    happened(family, kind, "2019-03-01", **fields)

    found = out_of_date(family)
    assert found["sentence"] == said
    assert found["change_id"] and found["at"]


def test_a_card_events_new_date_or_kind_puts_the_report_out_of_date(written, family):
    # R-0827
    moved(family, written, date="2005-01-01")

    assert out_of_date(family)["sentence"] == (
        "The date of Wren's “Stopped sleeping well” in 2005 changed after the coach wrote this report."
    )


def test_any_change_to_the_family_puts_the_report_out_of_date_and_several_are_counted(written, family):
    # R-0825, R-0826
    other = happened(family, "noted", "2019-03-01", title="Moved to Leeds")

    assert out_of_date(family)["sentence"] == "Wren's “Moved to Leeds” in 2019 was added after the coach wrote this report."
    moved(family, other, "e3", date="2020-01-01")
    found = out_of_date(family)
    assert found["sentence"] == "2 changes to the diagram since the coach wrote this report."
    assert found["change_id"] == Change.query.filter_by(turn_id="e3").one().id


def test_a_new_guess_off_the_cards_leaves_the_report_as_it_was(written, family):
    # R-0825
    impress(box(family, "r2"), text="A guess on no card.")

    assert out_of_date(family) is None


def test_a_card_written_after_the_change_makes_the_report_current_again(written, family):
    # R-0827
    happened(family, "death", "2019-03-01", person=2)
    impress(box(family, "r2"), text="A second guess.")
    card(family, "i2", "main_guess", "c2")

    assert out_of_date(family) is None


def test_the_coach_writing_one_card_again_leaves_the_others_out_of_date(web, past, written, family):
    # R-0825, R-0826
    impress(box(family, "r2"), text="The coach's own guess.", evidence=({"kind": "event", "id": written},))
    card(family, "i2", "coach_guess", "c2")
    moved(family, written, "e3", date="2005-01-01")
    impress(box(family, "e3"), text="A guess on the new date.", evidence=({"kind": "event", "id": written},))
    card(family, "i3", "main_guess", "e3")

    assert out_of_date(family)["sentence"] == (
        "The date of Wren's “Stopped sleeping well” in 2005 changed after the coach wrote this report."
    )
    rewrite(web, Model(calling(*FIVE)))
    assert out_of_date(family) is None


def test_the_timeline_says_what_put_the_report_out_of_date(web, written, family):
    # R-0826, R-0827
    happened(family, "death", "2019-03-01", person=2)

    found = web.get("/app/timeline").get_json()["report_out_of_date"]
    assert found["sentence"] == "Ada's death in 2019 was added after the coach wrote this report."


FIVE = [
    (ToolName.AddImpression, {"text": f"Guess for {name}.", "state": "raised",
                              "evidence": [{"kind": "person", "id": "1"}], "case_report_card": name})
    for name in ("main_guess", "coach_guess", "own_part", "choice", "work_on")
]


def rewrite(web, model):
    with patch("btcopilot.casereport.model_for", return_value=model):
        return web.post("/app/case-report-rewrites", headers={"X-CSRFToken": csrf_token(web)})


def test_a_rewrite_writes_every_card_again_in_one_model_call(web, past, written, family):
    # R-0825
    card(family, "i1", "coach_guess", "c2")
    model = Model(calling(*FIVE))
    response = rewrite(web, model)

    assert response.status_code == 202
    turn_id = response.get_json()["id"]
    assert web.get(f"/app/case-report-rewrites/{turn_id}").get_json() == {"id": turn_id, "state": "done"}
    done = turnlog.read_from(turn_id, 0)[-1][1]
    assert done["cards"] == ["main_guess", "coach_guess", "own_part", "choice", "work_on"]
    now = cards(family)
    assert now["i1"] is None
    assert sorted(v for v in now.values() if v) == ["choice", "coach_guess", "main_guess", "own_part", "work_on"]
    assert model.offered == [["add_impression"]]
    assert ModelCall.query.filter_by(purpose=Purpose.Coach, turn_id=turn_id).count() == 1
    assert TokenMeter.query.filter_by(user_id=family.user_id).count() == 1


def test_a_rewrite_refuses_any_other_tool_and_writes_it_down(web, past, written, family):
    # R-0825
    asked = (ToolName.AddQuestion, {"text": "What happened?", "kind": "thought", "state": "asked"})
    rewrite(web, Model(calling(FIVE[0], asked)))

    assert cards(family)["i1"] is None
    refused = Observation.query.filter_by(kind=ObservationKind.ToolRefused).one()
    assert refused.detail["tool"] == "add_question"


def test_a_rewrite_that_fails_says_so_on_its_turn_and_keeps_the_cards(web, past, written, family):
    # R-0825
    turnlog.claim(family.id, "broke")
    with patch("btcopilot.casereport.model_for", return_value=Model()):
        with pytest.raises(IndexError):
            casereport.run("broke", family.id, family.user_id)

    assert turnlog.read_from("broke", 0)[-1][1]["type"] == "failed"
    assert cards(family)["i1"] == "main_guess"
    assert Observation.query.filter_by(kind=ObservationKind.TurnFailed).count() == 1
    assert turnlog.rewriting(family.id) is None


def test_a_second_rewrite_while_one_runs_is_refused(web, past, written, family):
    # R-0825
    turnlog.claim(family.id, "running")

    assert rewrite(web, Model()).status_code == 409


def test_a_family_with_no_session_has_no_report_to_write_again(web, written, family):
    # R-0825
    assert rewrite(web, Model()).status_code == 409
    assert stored(family)


def test_a_rewrite_whose_worker_let_go_reads_failed(web, past, written, family):
    # R-0825
    turnlog.claim(family.id, "lost")
    turnlog.release(family.id)

    assert web.get("/app/case-report-rewrites/lost").get_json() == {"id": "lost", "state": "failed"}


def test_a_rewrite_reads_every_events_words_and_notes_into_its_one_call(web, past, written, family):
    # R-0825
    model = Model(calling(*FIVE))
    rewrite(web, model)

    opening = model.histories[0][0]["content"]
    assert ("EVENTS" in opening, "Stopped sleeping well" in opening) == (True, True)


def test_a_rewrite_of_a_family_the_reader_cannot_open_is_not_found(web):
    # R-0825
    assert web.get("/app/case-report-rewrites/nobody").status_code == 404


def catch_up(flask_app, *args, model=None) -> list[dict]:
    with patch("btcopilot.admin.casereport.model_for", return_value=model or Model()):
        result = flask_app.test_cli_runner().invoke(admin, ["case-report", "rewrite", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_the_catch_up_dry_run_saves_the_plan_and_writes_nothing(flask_app, tmp_path, past, written, family):
    # R-0820, R-0825
    before = stored(family)
    with patch.object(TokenMeter, "charge") as charge:
        rows = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*FIVE)))

    assert (rows[0]["card"], rows[0]["before"]) == ("main_guess", FELL)
    assert stored(family) == before
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1
    assert charge.called is False


def test_the_catch_up_writes_the_plan_and_names_the_changes_undo_takes_back(
    flask_app, tmp_path, past, written, family
):
    # R-0820, R-0825
    plan = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*FIVE)))[0]["plan"]
    (done,) = catch_up(flask_app, "--apply", "--plan", plan)

    assert done["cards"] == "main_guess, coach_guess, own_part, choice, work_on"
    assert cards(family)["i1"] is None
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(family.id), *done["changes"].split(), "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert cards(family)["i1"] == "main_guess"


def test_the_catch_up_refuses_a_plan_the_record_moved_past(flask_app, tmp_path, past, written, family):
    # R-0825
    plan = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*FIVE)))[0]["plan"]
    happened(family, "death", "2019-03-01", person=2)
    result = flask_app.test_cli_runner().invoke(admin, ["case-report", "rewrite", "--apply", "--plan", plan])

    assert "run the dry run again" in result.output


def test_the_catch_up_saves_requests_for_the_subscription_and_takes_its_answers(
    flask_app, tmp_path, past, written, family
):
    # R-0825
    asked, model = tmp_path / "requests", Model()
    model.effort = "high"
    catch_up(flask_app, "--requests", str(asked), model=model)
    request = json.loads((asked / f"case-report-{family.id}.json").read_text())
    assert [t["name"] for t in request["tools"]] == ["add_impression"]
    answers = tmp_path / "answers"
    answers.mkdir()
    blocks = [
        {"type": "tool_use", "id": f"a{n}", "name": "add_impression", "input": args}
        for n, (_, args) in enumerate(FIVE)
    ]
    (answers / f"case-report-{family.id}.json").write_text(json.dumps({"model": "m", "content": blocks}))
    rows = catch_up(flask_app, "--plans", str(tmp_path / "plans"), "--saved-answers", str(answers))

    assert len(rows) == 5
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 0


def test_the_catch_up_leaves_a_record_with_no_written_card(flask_app, tmp_path, past, family):
    # R-0825
    assert catch_up(flask_app, "--plans", str(tmp_path)) == []
