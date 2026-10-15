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

from btcopilot import casereport, record, turnlog
from btcopilot.admin import admin
from btcopilot.coachmodel import CoachModel
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Discussion, ModelCall, Observation, ObservationKind, Purpose, TokenMeter
from btcopilot.schema import Cluster, DiagramData, Person
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


def test_the_coachs_last_card_write_is_what_the_report_is_measured_from(written, family):
    # R-0850, R-0826
    impress(box(family, "r2"), text="The coach's own guess.", evidence=({"kind": "event", "id": written},))
    card(family, "i2", "coach_guess", "c2")
    moved(family, written, "e3", date="2005-01-01")
    impress(box(family, "e3"), text="A guess on the new date.", evidence=({"kind": "event", "id": written},))
    card(family, "i3", "main_guess", "e3")

    assert out_of_date(family) is None


def test_a_refresh_with_no_change_after_it_is_current_and_one_change_after_it_is_not(
    web, past, written, family
):
    # R-0850, R-0826
    moved(family, written, "e3", date="2005-01-01")
    assert out_of_date(family)
    rewrite(web, Model(calling(*every(past))))
    assert out_of_date(family) is None
    moved(family, written, "e4", date="2006-01-01")
    assert out_of_date(family)["sentence"] == (
        "The date of Wren's “Stopped sleeping well” in 2006 changed after the coach wrote this report."
    )


def forced(family, value: bool | None = None) -> bool:
    db.session.expire_all()
    if value is not None:
        family.case_report_forced_out_of_date = value
        db.session.commit()
    return family.case_report_forced_out_of_date


def test_a_report_forced_out_of_date_stays_so_through_a_card_write_until_a_refresh(
    web, past, written, family
):
    # R-0772
    forced(family, True)
    found = out_of_date(family)
    assert (found["sentence"], found["change_id"]) == (
        casereport.NEW_WAY,
        Change.query.filter_by(turn_id="c1").one().id,
    )
    impress(box(family, "r2"), text="A second guess.")
    card(family, "i2", "main_guess", "c2")
    assert out_of_date(family)["sentence"] == casereport.NEW_WAY
    rewrite(web, Model(calling(*every(past))))
    assert out_of_date(family) is None
    assert not forced(family)


def test_a_refresh_that_writes_no_card_leaves_the_report_forced_out_of_date(
    web, past, written, family
):
    # R-0772
    forced(family, True)
    turn_id = rewrite(web, Model(calling(), calling())).get_json()["id"]

    assert turnlog.read_from(turn_id, 0)[-1][1]["cards"] == []
    assert forced(family)


def test_an_entry_on_the_retired_choice_card_is_never_a_card_write(written, family):
    # R-0850
    happened(family, "death", "2019-03-01", person=2)
    impress(box(family, "r2"), text="An old choice.")
    record.apply(
        family.id,
        [{"item_kind": "question", "item_id": "i2", "field": "case_report_card", "after": "choice"}],
        author=Author.Coach,
        turn_id="c9",
        user_id=family.user_id,
    )

    assert out_of_date(family)["sentence"] == "Ada's death in 2019 was added after the coach wrote this report."


def test_the_timeline_says_what_put_the_report_out_of_date(web, written, family):
    # R-0826, R-0827
    happened(family, "death", "2019-03-01", person=2)

    found = web.get("/app/timeline").get_json()["report_out_of_date"]
    assert found["sentence"] == "Ada's death in 2019 was added after the coach wrote this report."


# The cards guessed from the diagram, each parent's family twice, one a side;
# with what brought the person in, every card a refresh writes.
GUESSED = [
    (ToolName.AddImpression, {"text": f"The app's guess for {name}{side}.", "state": "raised",
                              "evidence": [{"kind": "person", "id": "1"}], "case_report_card": name})
    for name, side in [*((n, "") for n in ("main_guess", "coach_guess", "couple", "own_part", "work_on", "family")),
                       ("sides", ", mother's side"), ("sides", ", father's side")]
]
CARDS_WRITTEN = sorted(["coach_guess", "couple", "family", "main_guess", "own_part", "sides", "sides", "what_brought", "work_on"])


def every(past) -> list:
    return [brought(past["user"]), *GUESSED]


def refusals(**detail) -> list[Observation]:
    return [
        o for o in Observation.query.filter_by(kind=ObservationKind.ToolRefused)
        if all(word in o.detail[key] for key, word in detail.items())
    ]


def rewrite(web, model):
    with patch("btcopilot.casereport.model_for", return_value=model):
        return web.post("/app/case-report-rewrites", headers={"X-CSRFToken": csrf_token(web)})


def test_a_rewrite_writes_every_card_again_in_one_model_call(web, past, written, family):
    # R-0825
    card(family, "i1", "coach_guess", "c2")
    model = Model(calling(*every(past)))
    response = rewrite(web, model)

    assert response.status_code == 202
    turn_id = response.get_json()["id"]
    assert web.get(f"/app/case-report-rewrites/{turn_id}").get_json() == {"id": turn_id, "state": "done"}
    done = turnlog.read_from(turn_id, 0)[-1][1]
    assert done["cards"] == [
        "what_brought", "main_guess", "coach_guess", "couple", "own_part", "work_on", "family", "sides"
    ]
    now = cards(family)
    assert now["i1"] is None
    assert sorted(v for v in now.values() if v) == CARDS_WRITTEN
    assert model.offered == [["add_impression"]]
    assert ModelCall.query.filter_by(purpose=Purpose.Coach, turn_id=turn_id).count() == 1
    assert TokenMeter.query.filter_by(user_id=family.user_id).count() == 1


def test_on_the_subscription_a_rewrite_is_answered_by_claude_code_at_no_cost(
    web, past, written, family, subscribed
):
    # R-0568, R-0825
    claude = subscribed(*[
        {"type": "tool_use", "id": f"tu_{index}", "name": tool.value, "input": args}
        for index, (tool, args) in enumerate(every(past))
    ])
    turn_id = rewrite(web, CoachModel()).get_json()["id"]

    assert [c[:2] for c in claude.commands] == [["claude", "-p"]]
    assert claude.offered == [["add_impression"]]
    row = ModelCall.query.filter_by(purpose=Purpose.Coach, turn_id=turn_id).one()
    assert (row.model, row.cost_usd) == ("claude-opus-5-5", 0)
    assert sorted(v for v in cards(family).values() if v) == CARDS_WRITTEN


def test_a_rewrite_refuses_any_other_tool_and_writes_it_down(web, past, written, family):
    # R-0825
    asked = (ToolName.AddQuestion, {"text": "What happened?", "kind": "thought", "state": "asked"})
    rewrite(web, Model(calling(GUESSED[0], asked), calling()))

    assert cards(family)["i1"] is None
    assert len(refusals(tool="add_question")) == 1


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
    turnlog.release(family.id, "lost")

    assert web.get("/app/case-report-rewrites/lost").get_json() == {"id": "lost", "state": "failed"}


class Edited(Model):
    """The model's call, during which the person adds a death to the family."""

    def __init__(self, family, *turns):
        super().__init__(*turns)
        self.family = family

    def turn(self, system, messages, tools, turn_id=""):
        happened(self.family, "death", "2019-03-01", person=2, turn="e9")
        return (yield from super().turn(system, messages, tools, turn_id))


def test_a_rewrite_whose_family_changed_during_the_call_writes_nothing_and_stays_out_of_date(
    web, past, written, family
):
    # R-0825, R-0826
    response = rewrite(web, Edited(family, calling(*every(past))))

    turn_id = response.get_json()["id"]
    assert turnlog.read_from(turn_id, 0)[-1][1] == {"type": "failed", "message": casereport.MOVED}
    assert cards(family)["i1"] == "main_guess"
    assert out_of_date(family)["sentence"] == "Ada's death in 2019 was added after the coach wrote this report."
    assert turnlog.rewriting(family.id) is None


def test_a_rewrite_whose_hold_ran_out_never_holds_or_lets_go_of_the_next_ones(family):
    # R-0825
    turnlog.claim(family.id, "next")
    turnlog.hold(family.id, "lost")
    turnlog.release(family.id, "lost")
    assert turnlog.rewriting(family.id) == "next"
    turnlog.release(family.id, "next")
    assert turnlog.rewriting(family.id) is None


def test_a_rewrite_reads_every_events_words_and_notes_into_its_one_call(web, past, written, family):
    # R-0825
    model = Model(calling(*every(past)))
    rewrite(web, model)

    opening = model.histories[0][0]["content"]
    assert ("EVENTS" in opening, "Stopped sleeping well" in opening) == (True, True)


def test_a_rewrite_of_a_family_the_reader_cannot_open_is_not_found(web):
    # R-0825
    assert web.get("/app/case-report-rewrites/nobody").status_code == 404


def brought(statement, text="“My grandmother raised me.”"):
    return (ToolName.AddImpression, {"text": text, "state": "raised", "case_report_card": "what_brought",
                                     "evidence": [{"kind": "statement", "id": str(statement)}]})


def guessed(text, card="coach_guess", evidence=({"kind": "person", "id": "1"},)):
    return (ToolName.AddImpression, {"text": text, "state": "raised", "case_report_card": card,
                                     "evidence": list(evidence)})


def texts(family) -> dict:
    return {q["case_report_card"]: q["text"] for q in stored(family).values() if q.get("case_report_card")}


def test_a_rewrite_reads_one_summary_per_conversation_and_the_first_ones_opening(web, past, written, family):
    # R-0850
    db.session.get(Discussion, past["session"]).summary = "Ruth raised the person."
    db.session.commit()
    model = Model(calling(*every(past)))
    rewrite(web, model)

    opening = model.histories[0][0]["content"]
    assert "Ruth raised the person." in opening.split(casereport.SUMMARIES)[1]
    raw = opening.split(casereport.OPENING)[1]
    assert f"[message {past['user']}" in raw and "My grandmother raised me." in raw
    assert len(raw) <= casereport.OPENING_CHARS + len(raw.splitlines()) + 1


def test_a_rewrite_writes_a_summary_for_a_conversation_with_none(web, past, written, family):
    # R-0850
    db.session.get(Discussion, past["session"]).summary = None
    db.session.commit()
    with patch.object(Discussion, "update_summary", autospec=True,
                      side_effect=lambda d, meter: setattr(d, "summary", "Written now.")) as summarized:
        model = Model(calling(*every(past)))
        rewrite(web, model)

    assert summarized.call_count == 1
    assert "Written now." in model.histories[0][0]["content"]


def test_what_brought_is_written_from_the_persons_own_message_and_then_no_opening_is_read(web, past, written, family):
    # R-0850
    rewrite(web, Model(calling(*every(past))))

    assert texts(family)["what_brought"] == "“My grandmother raised me.”"
    model = Model(calling(*every(past)))
    rewrite(web, model)
    assert casereport.OPENING not in model.histories[0][0]["content"]


def test_the_family_and_each_parents_family_not_given_are_asked_for_once_more(web, past, written, family):
    # R-0850, R-0866
    model = Model(calling(*every(past)[:-3]), calling(*GUESSED[-3:]))
    rewrite(web, model)

    asked = model.histories[1][-1]["content"][-1]["text"]
    assert "family" in asked and "sides" in asked and "couple" not in asked
    written = sorted(v for v in cards(family).values() if v)
    assert written == CARDS_WRITTEN
    assert refusals(refusal="no family card") and refusals(refusal="no sides card")


def test_what_brought_resting_on_no_message_of_the_person_is_refused_and_asked_for_once_more(
    web, past, written, family
):
    # R-0850, R-0852
    model = Model(calling(guessed("They came about sleep.", "what_brought"), *GUESSED), calling(brought(past["user"])))
    rewrite(web, model)

    assert texts(family)["what_brought"] == "“My grandmother raised me.”"
    (refused,) = refusals(refusal="statement")
    assert refused.detail["retried"] is True
    assert "statement" in model.histories[1][-1]["content"][0]["content"]

    rewrite(web, Model(calling(guessed("They came about sleep.", "what_brought"), *GUESSED), calling()))
    assert texts(family)["what_brought"] == "“My grandmother raised me.”"
    assert [o.detail["retried"] for o in refusals(refusal="statement")] == [True, True]
    (still,) = refusals(refusal="no what_brought card")
    assert still.detail["reason"].startswith("case report rewrite: what_brought: missing; first try: refused: ")
    assert "statement" in still.detail["reason"]


def test_a_card_refused_on_both_tries_is_written_down_once_per_try(web, past, written, family):
    # R-0850
    sleep = guessed("They came about sleep.", "what_brought")
    rewrite(web, Model(calling(sleep, *GUESSED), calling(sleep)))

    rows = refusals(reason="case report rewrite: what_brought: ")
    assert [o.detail["reason"].split("; ")[0] for o in rows] == [
        "case report rewrite: what_brought: refused: " + rows[0].detail["refusal"],
        "case report rewrite: what_brought: refused: " + rows[1].detail["refusal"],
    ]
    assert refusals(refusal="no what_brought card") == []


def test_a_card_giving_a_cause_is_asked_for_again_once(web, past, written, family):
    # R-0850, R-0569
    model = Model(calling(guessed("Your sleep went because your mother fell ill.")),
                  calling(guessed("Your sleep went the winter your mother fell ill.")))
    rewrite(web, model)

    assert len(model.histories) == 2
    result = model.histories[1][-1]["content"][0]
    assert (result["is_error"], "because" in result["content"]) == (True, True)
    assert texts(family)["coach_guess"] == "Your sleep went the winter your mother fell ill."


def test_a_card_giving_a_cause_twice_is_written_without_that_sentence(web, past, written, family):
    # R-0850, R-0569
    why = guessed("Your sleep and your mother's illness came the same winter. That is why you pulled away.")
    rewrite(web, Model(calling(why), calling(why)))

    assert texts(family)["coach_guess"] == "Your sleep and your mother's illness came the same winter."


def test_a_card_saying_one_event_created_a_period_is_refused_written_down_and_asked_for_again(
    web, past, written, family
):
    # R-0864, R-0850, R-0569
    model = Model(
        calling(guessed("Your parents' separation and the symphony created a period of heightened anxiety.")),
        calling(guessed("The app's guess: your parents separated around the same time as the symphony auditions.")),
    )
    rewrite(web, model)

    assert len(model.histories) == 2
    (row,) = refusals(reason="case report rewrite: coach_guess: ")
    assert row.detail["refusal"].startswith("'created'")
    assert texts(family)["coach_guess"] == "The app's guess: your parents separated around the same time as the symphony auditions."


def test_a_card_in_the_persons_voice_is_refused_and_their_quoted_words_pass(web, past, written, family):
    # R-0860
    model = Model(
        calling(guessed("I remember my mother was ill that winter.")),
        calling(guessed('You said "I remember my mother was ill" that winter.')),
    )
    rewrite(web, model)

    result = model.histories[1][-1]["content"][0]
    assert (result["is_error"], "'I' speaks as the person" in result["content"]) == (True, True)
    assert refusals(refusal="speaks as the person")
    assert texts(family)["coach_guess"] == 'You said "I remember my mother was ill" that winter.'


def test_a_card_in_the_persons_voice_twice_is_written_without_that_sentence(web, past, written, family):
    # R-0860
    voice = guessed("Your mother was ill in 2004. I was scared then.")
    rewrite(web, Model(calling(voice), calling(voice)))

    assert texts(family)["coach_guess"] == "Your mother was ill in 2004."


@pytest.mark.parametrize(
    "said, refusal",
    [
        ("You married in 2009 because your mother fell ill.", "gives a cause"),
        ("We married in 2009 and I saw less of my mother.", "speaks as the person"),
    ],
)
def test_the_couple_card_refuses_a_cause_and_the_persons_voice_like_the_others(
    web, past, written, family, said, refusal
):
    # R-0850
    plain = "You married in 2009; within a year you saw your mother less."
    model = Model(calling(guessed(said, "couple")), calling(guessed(plain, "couple")))
    rewrite(web, model)

    assert len(refusals(refusal=refusal, reason="case report rewrite: couple: ")) == 1
    assert texts(family)["couple"] == plain


@pytest.fixture
def grouped(family, written):
    data = family.get_diagram_data()
    data.clusters.append(asdict(Cluster(id="c1", title="Ada's illness", summary="", eventIds=[int(written)])))
    family.set_diagram_data(data)
    db.session.commit()
    return "c1"


def test_the_coach_guess_gives_for_and_against_each_cluster_it_rests_on(web, past, grouped, family):
    # R-0850
    text = "The app's guess: distance between you and your mother, 2004.\nFor c1: the sleep trouble began that autumn.\nAgainst c1: one event."
    rewrite(web, Model(calling(guessed(text, evidence=[{"kind": "cluster", "id": grouped}])), calling()))

    assert texts(family)["coach_guess"] == text


def test_a_rewrite_reads_a_cluster_with_fewer_than_three_supporting_shifts(web, past, grouped, family):
    # R-0850
    model = Model(calling(*every(past)))
    rewrite(web, model)

    held = model.histories[0][0]["content"].split(casereport.HELD)[1]
    assert held.split("\n\n")[0].strip().splitlines() == [
        "c1: 1 supporting shift, fewer than 3; all of them Wren's; changes in the family in its years: none in the diagram"
    ]


def _gaps(first: str, last: str) -> str:
    """What the refresh is told of one cluster opened by a death on a known
    day, its first shift's date marked `first` and its last `last`."""
    shift = lambda id, date, sure: {
        "id": id, "kind": "shift", "person": 1, "symptom": "up", "dateTime": date, "dateCertainty": sure,
    }
    data = DiagramData(
        people=[{"id": 1, "name": "Wren"}, {"id": 2, "name": "Ada"}],
        events=[
            {"id": 10, "kind": "death", "person": 2, "dateTime": "1998-03-01", "dateCertainty": "certain"},
            shift(11, "1998-07-01", first),
            shift(12, "1998-09-01", "certain"),
            shift(13, "2001-02-01", last),
        ],
        clusters=[asdict(Cluster(id="c1", title="After Ada's death", summary="", eventIds=[10, 11, 12, 13]))],
    )
    return casereport.held(data).split("; changes")[0]


def test_the_refresh_is_told_how_far_shifts_fall_from_an_opening_no_finer_than_their_dates():
    # R-0855
    assert _gaps("certain", "certain") == (
        "c1: 3 supporting shifts; all of them Wren's; opened by event 10, "
        "the first shift 122 days after its opening, the last 1068 days after its opening"
    )
    assert _gaps("approximate", "unknown") == (
        "c1: 3 supporting shifts; all of them Wren's; opened by event 10, "
        "the first shift within about a year of its opening, the last at a date nobody knows"
    )
    assert _gaps("certain", "approximate").endswith("the last about 3 years after its opening")


def _wrens() -> DiagramData:
    """Wren, her parents Ada and Cal, Ada's parents and sister Ivy and Ivy's
    husband, Cal's mother, Wren's brother, her partner and their child, with
    Wren's distance and cutoff toward Ada, a triangle of Ada, Ivy and Wren,
    Ada's mother's death and Ivy's conflict with her husband."""
    person = lambda id, name, gender, parents=None: {"id": id, "name": name, "gender": gender, "parents": parents}
    born = lambda id, child, date, sure="certain": {
        "id": id, "kind": "birth", "child": child, "dateTime": date, "dateCertainty": sure,
    }
    marked = lambda id, mover, kind, date, targets, words, triangles=(): {
        "id": id, "kind": "shift", "person": mover, "relationship": kind, "dateTime": date,
        "dateCertainty": "certain", "relationshipTargets": list(targets),
        "relationshipTriangles": list(triangles), "description": words,
    }
    bond = lambda id, a, b: {"id": id, "person_a": a, "person_b": b}
    return DiagramData(
        people=[
            person(1, "Wren", "female", 10), person(2, "Ada", "female", 11), person(3, "Cal", "male", 12),
            person(4, "Bo", "male", 10), person(5, "Gran", "female"), person(6, "Gramps", "male"),
            person(7, "Ivy", "female", 11), person(8, "Nan", "female"), person(9, "Rex", "male"),
            person(14, "Kit", "female", 13), person(15, "Jo", "male"),
        ],
        pair_bonds=[bond(10, 2, 3), bond(11, 5, 6), bond(12, 8, None), bond(13, 1, 9), bond(16, 7, 15)],
        events=[
            born(20, 1, "1978-04-01"), born(21, 4, "1980-01-01", "approximate"), born(22, 2, "1952-06-01"),
            born(23, 7, "1950-02-01"), born(24, 14, "2012-09-01"),
            {"id": 25, "kind": "death", "person": 5, "dateTime": "1998-02-01", "dateCertainty": "certain"},
            marked(30, 1, "distance", "1998-05-01", [2], "Stopped calling her mother"),
            marked(31, 2, "inside", "2010-03-01", [7], "Took her sister in", triangles=[1]),
            marked(32, 1, "cutoff", "2015-01-01", [2], "Cut off from her mother"),
            marked(33, 7, "conflict", "2001-01-01", [15], "Fights over money"),
            {"id": 34, "kind": "shift", "person": 1, "symptom": "up", "dateTime": "1998-07-01",
             "dateCertainty": "certain"},
        ],
        clusters=[asdict(Cluster(id="c1", title="After Gran's death", summary="", eventIds=[25, 30, 34]))],
    )


def test_the_refresh_reads_what_each_person_is_to_the_person_and_whose_side_they_are_on():
    # R-0850
    assert casereport.kin(_wrens()).splitlines() == [
        "the person: 1 Wren",
        "mother: 2 Ada",
        "father: 3 Cal",
        "brother: 4 Bo",
        "grandmother on the mother's side: 5 Gran",
        "grandfather on the mother's side: 6 Gramps",
        "aunt on the mother's side: 7 Ivy",
        "grandmother on the father's side: 8 Nan",
        "partner: 9 Rex",
        "daughter: 14 Kit",
        "a relative on the mother's side: 15 Jo",
    ]


def test_the_refresh_reads_the_brothers_and_sisters_of_the_person_and_each_parent_in_birth_order():
    # R-0850
    assert casereport.order_of_birth(_wrens()).splitlines() == [
        "1 Wren (the person): born 1 of 2: 1 Wren 1978, 4 Bo about 1980",
        "2 Ada (mother): born 2 of 2: 7 Ivy 1950, 2 Ada 1952",
        "3 Cal (father): no brothers or sisters in the diagram",
    ]


def test_a_place_among_brothers_and_sisters_is_not_known_when_a_birth_has_no_date():
    # R-0850, R-0855
    wrens = _wrens()
    next(e for e in wrens.events if e["id"] == 21)["dateCertainty"] = "unknown"

    assert casereport.order_of_birth(wrens).splitlines()[0] == (
        "1 Wren (the person): place not known, a birth among them has no date: 1 Wren 1978, 4 Bo date unknown"
    )


def test_the_refresh_reads_each_triangle_the_events_mark_with_who_was_inside_and_outside():
    # R-0850
    assert casereport.triangles(_wrens()) == (
        "1 Wren (the person), 2 Ada (mother), 7 Ivy (aunt): "
        "2010 Ada and Ivy inside, Wren outside “Took her sister in”"
    )


def test_the_refresh_reads_each_close_pairs_relationship_events_by_date_and_counts_the_rest():
    # R-0850, R-0864
    assert casereport.pairs(_wrens()).splitlines() == [
        "1 Wren (the person) and 2 Ada (mother): "
        "1998 Wren distance “Stopped calling her mother”; 2015 Wren cutoff “Cut off from her mother”",
        "1 more pair farther out in the family has relationship events",
    ]


def test_the_refresh_reads_each_side_of_the_family_its_events_its_deaths_and_the_persons_last_contact():
    # R-0850
    assert casereport.by_side(_wrens()).splitlines() == [
        "the side of 2 Ada (mother): 7 events; died: 5 Gran 1998; "
        "no death in the diagram: 2 Ada, 6 Gramps, 7 Ivy, 15 Jo; "
        "the person's last relationship event with each one on it: 2 Ada 2015 Wren cutoff “Cut off from her mother”",
        "the side of 3 Cal (father): 0 events; died: none in the diagram; no death in the diagram: 3 Cal, 8 Nan; "
        "the person's last relationship event with each one on it: none in the diagram",
    ]


def test_the_refresh_reads_the_changes_in_a_clusters_years_and_who_its_opening_is_about():
    # R-0850
    assert casereport.held(_wrens()) == (
        "c1: 2 supporting shifts, fewer than 3; all of them Wren's; opened by event 25, the first shift "
        "89 days after its opening, the last 150 days after its opening; changes in the family in its years: 1998 death; "
        "its opening is about 5 Gran (grandmother), partners: 6 Gramps (grandfather), "
        "children: 2 Ada (mother) born 1952, 7 Ivy (aunt) born 1950"
    )


def test_a_rewrite_reads_the_family_blocks_after_the_events(web, past, written, family):
    # R-0850
    model = Model(calling(*every(past)))
    rewrite(web, model)

    opening = model.histories[0][0]["content"]
    assert opening.index("EVENTS") < opening.index(casereport.KIN) < opening.index(casereport.SUMMARIES)


def test_a_prediction_off_what_to_work_on_is_refused_and_asked_for_once_more(web, past, written, family):
    # R-0850
    model = Model(
        calling(guessed("Distance with your mother, 2004. The next loss will bring more distance.")),
        calling(guessed('Distance with your mother, 2004. You said "it will pass".')),
    )
    rewrite(web, model)

    assert "Prognosis line of work_on" in model.histories[1][-1]["content"][0]["content"]
    assert texts(family)["coach_guess"] == 'Distance with your mother, 2004. You said "it will pass".'
    assert len(refusals(refusal="'will' says what will come")) == 1


@pytest.mark.parametrize(
    "said, refused",
    [
        ("The app's guess: in 2009 you stopped going to classes.", False),
        ("The app's guess: you were going to visit her that spring.", False),
        ("The app's guess: your sleep is going to go again at the next loss.", True),
        ("The app's guess: it's going to come back.", True),
    ],
)
def test_going_to_says_what_will_come_only_after_is_or_are(web, past, written, family, said, refused):
    # R-0850
    rewrite(web, Model(calling(guessed(said)), calling()))

    assert (texts(family).get("coach_guess") != said) == refused
    assert bool(refusals(refusal="says what will come")) == refused


def test_an_executive_summary_longer_than_the_trouble_and_the_pattern_is_kept_and_observed(web, past, written, family):
    # R-0850
    run = "You said you sleep badly. It began in 1998. Your grandmother died that year. You stopped calling your mother."
    model = Model(calling(guessed(run, "main_guess")))
    rewrite(web, model)

    assert texts(family)["main_guess"] == run
    assert refusals(refusal="has 4 sentences")[0].detail["sentences"] == 4


def test_a_card_not_saying_whose_reading_it_is_is_refused_and_asked_for_once_more(web, past, written, family):
    # R-0850
    model = Model(
        calling(guessed("Distance between you and your mother, 2004.")),
        calling(guessed("The app's guess: distance between you and your mother, 2004.")),
    )
    rewrite(web, model)

    assert "whose reading" in model.histories[1][-1]["content"][0]["content"]
    assert texts(family)["coach_guess"] == "The app's guess: distance between you and your mother, 2004."
    assert len(refusals(refusal="whose reading")) == 1


def test_a_card_not_saying_whose_reading_it_is_twice_is_written_and_written_down(web, past, written, family):
    # R-0850
    bare = guessed("Distance between you and your mother, 2004.")
    rewrite(web, Model(calling(bare), calling(bare)))

    assert texts(family)["coach_guess"] == "Distance between you and your mother, 2004."
    first, last = refusals(refusal="whose reading")
    assert (first.detail["retried"], last.detail["retried"]) == (True, False)
    assert last.detail["reason"].startswith("case report rewrite: coach_guess: kept: the card does not say")
    assert last.detail["reason"].endswith("; first try: refused: " + first.detail["refusal"])


@pytest.mark.parametrize(
    "text, card",
    [
        ("Not enough in the diagram yet: your father's parents' names.", "sides"),
        ('You said "I stopped calling her" in 2004.', "own_part"),
        ("In 2004 you stopped calling your mother. The app's guess: distance.", "own_part"),
    ],
)
def test_a_card_saying_whose_reading_it_is_or_how_little_the_diagram_holds_is_never_refused_for_it(
    web, past, written, family, text, card
):
    # R-0850
    rewrite(web, Model(calling(guessed(text, card)), calling()))

    assert texts(family)[card] == text
    assert refusals(refusal="whose reading") == []


def test_a_for_or_against_on_a_cluster_the_guess_does_not_rest_on_is_refused(web, past, grouped, family):
    # R-0850
    rewrite(web, Model(calling(guessed("Distance, 2004.\nFor c9: nothing.")), calling()))

    assert "coach_guess" not in texts(family)
    assert len(refusals(refusal="c9")) == 1


def test_the_choice_is_written_on_the_part_card_with_the_other_way_and_never_on_its_own(web, past, written, family):
    # R-0850
    part = "The app's guess: in 2004 you stopped calling your mother.\nOther way: could contact have stayed light?"
    rewrite(web, Model(calling(guessed(part, "own_part"), guessed("You could have called.", "choice")), calling()))

    assert texts(family) == {"main_guess": FELL, "own_part": part}


def test_what_to_work_on_carries_the_prognosis_and_the_aim(web, past, written, family):
    # R-0850, R-0868
    work = "The app's guess: more contact with your mother.\nPrognosis: trouble may come again near the next loss.\nAim: call her weekly"
    rewrite(web, Model(calling(guessed(work, "work_on")), calling()))

    assert texts(family)["work_on"] == work


def test_a_mark_inside_a_line_is_refused_and_asked_for_once_more(web, past, grouped, family):
    # R-0850
    inline = "Distance, 2004. For c1: the sleep trouble began that autumn. Open: the father's side."
    lined = "Distance, 2004.\nFor c1: the sleep trouble began that autumn.\nOpen: the father's side."
    rests = [{"kind": "cluster", "id": grouped}]
    model = Model(calling(guessed(inline, evidence=rests)), calling(guessed(lined, evidence=rests)))
    rewrite(web, model)

    assert texts(family)["coach_guess"] == lined
    assert "on a line of its own" in model.histories[1][-1]["content"][0]["content"]
    assert len(refusals(refusal="inside a line")) == 1


@pytest.mark.parametrize("raw", ["c1", "(210)", "event 116"])
def test_an_id_in_a_cards_words_is_refused_and_asked_for_once_more(web, past, grouped, family, raw):
    # R-0850
    rests = [{"kind": "cluster", "id": grouped}]
    clean = "Distance between you and your mother, 2004.\nFor c1: the sleep trouble began that autumn."
    model = Model(
        calling(guessed(f"Distance, 2004, as {raw} shows.", evidence=rests)),
        calling(guessed(clean, evidence=rests)),
    )
    rewrite(web, model)

    assert texts(family)["coach_guess"] == clean
    assert len(refusals(refusal="is an id")) == 1


def test_a_card_not_given_is_asked_for_once_more_and_still_missing_keeps_its_note(web, past, written, family):
    # R-0850
    model = Model(calling(*every(past)[1:3]), calling(*GUESSED[2:]))
    rewrite(web, model)

    asked = model.histories[1][-1]["content"][-1]["text"]
    assert "what_brought" in asked and "own_part" in asked and "main_guess" not in asked
    assert texts(family)["work_on"] == "The app's guess for work_on."
    assert "what_brought" not in texts(family)
    first, last = refusals(refusal="no what_brought card")
    assert (first.detail["retried"], last.detail["retried"]) == (True, False)
    assert first.detail["reason"] == "case report rewrite: what_brought: missing"
    assert last.detail["reason"] == "case report rewrite: what_brought: missing; first try: missing"

    rewrite(web, Model(calling(*every(past)[:1]), calling()))
    assert texts(family)["main_guess"] == "The app's guess for main_guess."


def catch_up(flask_app, *args, model=None) -> list[dict]:
    with patch("btcopilot.admin.casereport.model_for", return_value=model or Model()):
        result = flask_app.test_cli_runner().invoke(admin, ["case-report", "rewrite", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def test_the_catch_up_dry_run_saves_the_plan_and_writes_nothing(flask_app, tmp_path, past, written, family):
    # R-0820, R-0825
    before = stored(family)
    with patch.object(TokenMeter, "charge") as charge:
        rows = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*GUESSED)))

    assert (rows[0]["card"], rows[0]["before"]) == ("main_guess", FELL)
    assert stored(family) == before
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1
    assert charge.called is False


def test_the_catch_up_writes_the_plan_and_names_the_changes_undo_takes_back(
    flask_app, tmp_path, past, written, family
):
    # R-0820, R-0825
    plan = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*GUESSED)))[0]["plan"]
    (done,) = catch_up(flask_app, "--apply", "--plan", plan)

    assert done["cards"] == "main_guess, coach_guess, couple, own_part, work_on, family, sides"
    assert cards(family)["i1"] is None
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(family.id), *done["changes"].split(), "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert cards(family)["i1"] == "main_guess"


def test_the_catch_up_refuses_a_plan_the_record_moved_past(flask_app, tmp_path, past, written, family):
    # R-0825
    plan = catch_up(flask_app, "--plans", str(tmp_path), model=Model(calling(*GUESSED)))[0]["plan"]
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
        for n, (_, args) in enumerate(GUESSED)
    ]
    (answers / f"case-report-{family.id}.json").write_text(json.dumps({"model": "m", "content": blocks}))
    rows = catch_up(flask_app, "--plans", str(tmp_path / "plans"), "--saved-answers", str(answers))

    assert len(rows) == len(GUESSED)
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 0


def test_the_catch_up_leaves_a_record_with_no_written_card(flask_app, tmp_path, past, family):
    # R-0825
    assert catch_up(flask_app, "--plans", str(tmp_path)) == []
