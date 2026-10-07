"""The case report against the diagram: out of date once, after the coach last
wrote a card, an event a card rests on changes its date or kind, or a death, a
marriage, a separation, a divorce or a shift with a symptom is added; and the
rewrite of every card the coach writes at once, in one model call, run in the
worker and followed on the turn log.

Invented names only.
"""

from dataclasses import asdict

import pytest
from mock import patch

from btcopilot import casereport, turnlog
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Observation, ObservationKind, Purpose, TokenMeter
from btcopilot.schema import Person
from btcopilot.tests.conftest import Model, calling, csrf_token, said, version
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
    # R-0827
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
    assert found["text"] == said
    assert found["change_id"] and found["at"]


def test_a_card_events_new_date_or_kind_puts_the_report_out_of_date(written, family):
    # R-0827
    moved(family, written, date="2005-01-01")

    assert out_of_date(family)["text"] == (
        "The date of Wren's “Stopped sleeping well” in 2005 changed after the coach wrote this report."
    )


@pytest.mark.parametrize(
    "kind, fields",
    [("noted", {"title": "Moved to Leeds"}), ("shift", {"title": "Started a new job", "functioning": "up"})],
)
def test_a_move_a_job_or_an_uncited_date_leaves_the_report_as_it_was(written, family, kind, fields):
    # R-0827
    other = happened(family, kind, "2019-03-01", **fields)
    moved(family, other, "e3", date="2020-01-01")

    assert out_of_date(family) is None


def test_a_card_written_after_the_change_makes_the_report_current_again(written, family):
    # R-0827
    happened(family, "death", "2019-03-01", person=2)
    impress(box(family, "r2"), text="A second guess.")
    card(family, "i2", "main_guess", "c2")

    assert out_of_date(family) is None


def test_the_timeline_says_what_put_the_report_out_of_date(web, written, family):
    # R-0826, R-0827
    happened(family, "death", "2019-03-01", person=2)

    report = web.get("/app/timeline").get_json()["case_report"]
    assert report["out_of_date"]["text"] == "Ada's death in 2019 was added after the coach wrote this report."
    assert report["rewriting"] is None


FIVE = [
    (ToolName.AddImpression, {"text": f"Guess for {name}.", "state": "raised",
                              "evidence": [{"kind": "person", "id": "1"}], "case_report_card": name})
    for name in ("main_guess", "coach_guess", "own_part", "choice", "work_on")
]


def rewrite(web, model):
    with patch("btcopilot.casereport.model_for", return_value=model):
        return web.post("/app/case-report", headers={"X-CSRFToken": csrf_token(web)})


def test_a_rewrite_writes_every_card_again_until_the_coach_stops(web, past, written, family):
    # R-0825
    card(family, "i1", "coach_guess", "c2")
    model = Model(calling(*FIVE[:3]), calling(*FIVE[3:]), said("Done."))
    response = rewrite(web, model)

    assert response.status_code == 202
    done = turnlog.read_from(response.get_json()["turn_id"], 0)[-1][1]
    assert (done["type"], done["cards"]) == ("done", ["main_guess", "coach_guess", "own_part", "choice", "work_on"])
    now = cards(family)
    assert now["i1"] is None
    assert sorted(v for v in now.values() if v) == ["choice", "coach_guess", "main_guess", "own_part", "work_on"]
    assert [names[-1] for names in model.offered] == ["add_impression"] * 3
    turn_id = response.get_json()["turn_id"]
    assert ModelCall.query.filter_by(purpose=Purpose.Coach, turn_id=turn_id).count() == 3
    assert TokenMeter.query.filter_by(user_id=family.user_id).count() == 1


def test_a_rewrite_refuses_any_other_tool_and_writes_it_down(web, past, written, family):
    # R-0825
    asked = (ToolName.AddQuestion, {"text": "What happened?", "kind": "thought", "state": "asked"})
    rewrite(web, Model(calling(FIVE[0], asked), said("Done.")))

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


def test_the_page_follows_a_rewrite_on_its_turn_like_a_coach_reply(web, past, written, family):
    # R-0825
    turn_id = rewrite(web, Model(calling(*FIVE), said("Done."))).get_json()["turn_id"]

    followed = web.get(f"/app/turns/{turn_id}/events").get_data(as_text=True)
    assert '"type": "done"' in followed
