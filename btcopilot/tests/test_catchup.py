"""The one pass that catches each record's questions up to the coach's newest
question rules: wrong-kind fact questions moved by fixed rules, facts the
person already said kept answered, stories the talk moved past kept for later.
The dry run makes the one model call and writes nothing; the apply writes
exactly the plan, each item a change row undo takes back.

Invented names only.
"""

import datetime
import json
from dataclasses import asdict

import pytest
from mock import patch

from btcopilot import record
from btcopilot.admin import admin
from btcopilot.extensions import db
from btcopilot.models import Author, Change, ModelCall, Purpose, Statement
from btcopilot.schema import PairBond, Person
from btcopilot.tests.conftest import Model, calling
from btcopilot.tests.test_questionbackfill import past  # noqa: F401
from btcopilot.recordtext import outline
from btcopilot.tests.test_questions import stored
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolName

STORY = "The summer your brother left home"


def fact(past, iid="2", name="alive", kind="person"):
    return (
        ToolName.AddQuestion,
        {
            "text": "Is Ash still alive?",
            "kind": "fact",
            "state": "resolved",
            "outcome": "answered",
            "answer": past["user"],
            "item_kind": kind,
            "item_id": iid,
            "fact": name,
            "statement": past["user"],
        },
    )


def story(past, text=STORY):
    return (
        ToolName.AddQuestion,
        {"text": text, "kind": "thought", "state": "held", "statement": past["user"]},
    )


@pytest.fixture
def kin(family, past):
    """Wren and Ash, a couple, and Rue, Ash's partner before."""
    data = family.get_diagram_data()
    data.people = [
        asdict(Person(id=1, name="Wren")),
        asdict(Person(id=2, name="Ash")),
        asdict(Person(id=4, name="Rue")),
    ]
    data.pair_bonds = [
        asdict(PairBond(id=3, person_a=1, person_b=2)),
        asdict(PairBond(id=5, person_a=2, person_b=4)),
    ]
    data.lastItemId = 5
    family.set_diagram_data(data)
    db.session.commit()
    return family


def filed(diagram, qid, name, kind, iid, state="resolved", outcome="answered"):
    """A fact question on the wrong kind of thing, as the coach filed them
    before its tool checked the kind."""
    fields = {
        "text": f"Asked {qid}?",
        "kind": "fact",
        "state": state,
        "outcome": outcome if state == "resolved" else None,
        "item_kind": kind,
        "item_id": iid,
        "fact": name,
        "session_id": 7,
        "asked_at": "2026-09-20",
    }
    record.apply(
        diagram.id,
        [
            {"item_kind": "question", "item_id": qid, "field": k, "after": v}
            for k, v in fields.items()
        ],
        author=Author.Coach,
        turn_id=f"old:{qid}",
    )


def catch_up(flask_app, *args, model=None):
    with patch("btcopilot.admin.catchup.model_for", return_value=model or Model()):
        result = flask_app.test_cli_runner().invoke(
            admin, ["questions", "catch-up", *args, "--json"]
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def dry(flask_app, tmp_path, *turns) -> dict:
    rows = catch_up(flask_app, "--plans", str(tmp_path), model=Model(*turns))
    path = rows[0]["plan"]
    return {**json.loads(open(path).read()), "path": path, "rows": rows}


def apply(flask_app, plan) -> list[dict]:
    return catch_up(flask_app, "--apply", "--plan", plan["path"])


def test_the_dry_run_saves_a_readable_plan_and_writes_nothing(flask_app, tmp_path, kin, past):
    # R-0760, R-0770, R-0772
    filed(kin, "q1", "met", "person", "1", state="asked")
    before, changes = stored(kin), Change.query.count()
    plan = dry(flask_app, tmp_path, calling(fact(past), story(past)))

    assert plan["counts"] == {
        "moved": 1,
        "left_as_is": 0,
        "facts": 1,
        "stories": 1,
        "asked_again": 0,
        "dropped": 0,
    }
    assert plan["facts"][0]["said"] == "My grandmother raised me."
    assert plan["facts"][0]["target"].startswith("person 2")
    assert plan["stories"][0]["words"] == STORY
    assert (stored(kin), Change.query.count()) == (before, changes)
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_apply_writes_exactly_the_plan_one_row_each_with_no_model_call(
    flask_app, tmp_path, kin, past
):
    # R-0760, R-0770, R-0772
    plan = dry(flask_app, tmp_path, calling(fact(past), story(past)))
    start = db.session.query(db.func.max(Change.id)).scalar() or 0
    rows = apply(flask_app, plan)

    assert [(r["entry"], r["refused"]) for r in rows] == [("q1", None), ("q2", None)]
    after = stored(kin)
    assert {k: after["q1"][k] for k in ("state", "outcome", "fact", "item_id")} == {
        "state": "resolved",
        "outcome": "answered",
        "fact": "alive",
        "item_id": "2",
    }
    assert after["q1"]["answer"]["id"] == past["user"]
    assert (after["q2"]["text"], after["q2"]["state"]) == (STORY, "held")
    made = Change.query.filter(Change.id > start).all()
    assert [(c.turn_id, c.statement_id) for c in made] == [(f"catch-up:{kin.id}", past["user"])] * 2
    assert ModelCall.query.filter_by(purpose=Purpose.Backfill).count() == 1


def test_a_second_pass_proposes_nothing_already_written(flask_app, tmp_path, kin, past):
    # R-0760, R-0770, R-0772
    filed(kin, "q9", "met", "person", "1", state="asked")
    apply(flask_app, dry(flask_app, tmp_path, calling(fact(past), story(past))))
    again = dry(flask_app, tmp_path, calling(fact(past), story(past, "The summer he left")))

    assert again["counts"] == {
        "moved": 0,
        "left_as_is": 0,
        "facts": 0,
        "stories": 0,
        "asked_again": 0,
        "dropped": 2,
    }
    assert [d["reason"] for d in again["dropped"]] == [
        "the record already holds it",
        "a question was already kept from that message",
    ]


def test_a_proposal_the_tool_would_refuse_is_dropped_with_its_reason(
    flask_app, tmp_path, kin, past
):
    # R-0760, R-0770, R-0772
    plan = dry(
        flask_app,
        tmp_path,
        calling(
            fact(past, "2", "children"),
            fact(past, "2", "name"),
            fact(past),
            fact(past),
            (ToolName.AddQuestion, {**fact(past)[1], "state": "asked"}),
            (ToolName.AddQuestion, {**story(past)[1], "statement": past["reply"]}),
            *[story(past, f"Story {n}") for n in range(9)],
        ),
    )

    reasons = [d["reason"] for d in plan["dropped"]]
    assert "children is asked of a pair_bond, not a person" in reasons[0]
    assert reasons[1:5] == [
        "the record already holds it",
        "the record already holds it",
        "only a fact already answered or a story held is kept here",
        "it names no message of the person's in this record",
    ]
    assert reasons[5:] == ["more than 8 stories"]
    assert (plan["counts"]["facts"], plan["counts"]["stories"]) == (1, 8)


def test_a_couple_fact_on_a_person_moves_to_their_one_pair_bond(flask_app, tmp_path, kin, past):
    # R-0760, R-0772
    filed(kin, "q1", "met", "person", "1", state="asked")
    filed(kin, "q2", "children", "person", "2", state="held")
    plan = dry(flask_app, tmp_path, calling())
    assert [m["question"] for m in plan["moved"]] == ["q1"]
    assert plan["left_as_is"][0]["reason"] == "the person has 2 pair-bonds, not one"

    rows = apply(flask_app, plan)
    assert rows[0]["refused"] is None
    after = stored(kin)
    assert (after["q1"]["item_kind"], after["q1"]["item_id"]) == ("pair_bond", "3")
    assert (after["q2"]["item_kind"], after["q2"]["item_id"]) == ("person", "2")


def test_a_question_the_record_will_not_move_is_left_as_is_with_the_reason(
    flask_app, tmp_path, kin, past
):
    # R-0760, R-0772
    filed(kin, "q2", "work", "pair_bond", "3", state="asked")
    before = stored(kin)
    plan = dry(flask_app, tmp_path, calling())

    assert plan["moved"] == []
    assert [(m["question"], m["reason"]) for m in plan["left_as_is"]] == [
        ("q2", "the pair-bond has 2 partners in the record, and an open question is kept once"),
    ]
    apply(flask_app, plan)
    assert stored(kin) == before


def test_a_closed_persons_fact_on_a_pair_bond_becomes_one_question_per_partner(
    flask_app, tmp_path, kin, past
):
    # R-0773, R-0772
    filed(kin, "q1", "birth_date", "pair_bond", "3")
    filed(kin, "q2", "met", "person", "1", outcome="unknown")
    before = stored(kin)
    start = db.session.query(db.func.max(Change.id)).scalar() or 0
    plan = dry(flask_app, tmp_path, calling())
    assert [m["question"] for m in plan["moved"]] == ["q1", "q2"]

    rows = apply(flask_app, plan)
    assert [r["refused"] for r in rows if r["part"] == "wrong kind"] == [None, None]
    after = stored(kin)
    same = ("text", "kind", "state", "outcome", "fact", "session_id", "asked_at")
    assert [(after[q]["item_kind"], after[q]["item_id"]) for q in ("q1", "q3", "q2")] == [
        ("person", "1"),
        ("person", "2"),
        ("pair_bond", "3"),
    ]
    assert {k: after["q3"][k] for k in same} == {k: before["q1"][k] for k in same}
    taken = [str(c.id) for c in Change.query.filter(Change.id > start)]
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(kin.id), *taken, "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert stored(kin) == before


def test_a_fact_a_planned_move_makes_known_is_not_proposed_again(flask_app, tmp_path, kin, past):
    # R-0773, R-0760
    filed(kin, "q1", "alive", "pair_bond", "3")
    plan = dry(flask_app, tmp_path, calling(fact(past, iid="2")))
    assert [d["reason"] for d in plan["dropped"]] == ["the record already holds it"]

    apply(flask_app, plan)
    alive = [
        (q["item_kind"], q["item_id"]) for q in stored(kin).values() if q.get("fact") == "alive"
    ]
    assert sorted(alive) == [("person", "1"), ("person", "2")]


def test_only_the_catch_up_moves_a_closed_question(kin):
    # R-0773
    filed(kin, "q1", "birth_date", "pair_bond", "3")
    moved = [
        {"item_kind": "question", "item_id": "q1", "field": "item_kind", "after": "person"},
        {"item_kind": "question", "item_id": "q1", "field": "item_id", "after": "1"},
    ]
    with pytest.raises(record.Invalid) as refused:
        record.apply(kin.id, moved, author=Author.Coach, turn_id="coach")
    assert refused.value.plain == "That question is already closed."
    reworded = [{"item_kind": "question", "item_id": "q1", "field": "text", "after": "New?"}]
    with pytest.raises(record.Invalid) as refused:
        record.apply(kin.id, reworded, author=Author.Coach, turn_id="t", refile=True)
    assert refused.value.plain == "A question can only be moved here."
    record.apply(kin.id, moved, author=Author.Coach, turn_id="catch-up", refile=True)
    assert (stored(kin)["q1"]["item_kind"], stored(kin)["q1"]["item_id"]) == ("person", "1")


def test_a_question_changed_since_the_dry_run_is_not_moved(flask_app, tmp_path, kin, past):
    # R-0772
    filed(kin, "q1", "met", "person", "1", state="asked")
    plan = dry(flask_app, tmp_path, calling())
    record.apply(
        kin.id,
        [{"item_kind": "question", "item_id": "q1", "field": "text", "after": "Reworded?"}],
        author=Author.Coach,
        turn_id="later",
    )

    rows = apply(flask_app, plan)
    assert rows[0]["refused"] == "the question changed since the dry run"
    assert stored(kin)["q1"]["item_kind"] == "person"


def test_a_question_whose_partners_changed_since_the_dry_run_is_not_moved(
    flask_app, tmp_path, kin, past
):
    # R-0772, R-0773
    filed(kin, "q1", "birth_date", "pair_bond", "3")
    plan = dry(flask_app, tmp_path, calling())
    data = kin.get_diagram_data()
    data.pair_bonds[0]["person_b"] = 4
    kin.set_diagram_data(data)
    db.session.commit()

    rows = apply(flask_app, plan)
    assert rows[0]["refused"] == "where the question goes changed since the dry run"
    assert [q["id"] for q in stored(kin).values()] == ["q1"]
    assert stored(kin)["q1"]["item_kind"] == "pair_bond"


def test_undo_takes_a_catch_up_row_back(flask_app, tmp_path, kin, past):
    # R-0772
    filed(kin, "q1", "met", "person", "1", state="asked")
    before = stored(kin)
    start = db.session.query(db.func.max(Change.id)).scalar() or 0
    apply(flask_app, dry(flask_app, tmp_path, calling(story(past))))
    rows = [str(c.id) for c in Change.query.filter(Change.id > start)]

    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(kin.id), *rows, "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert stored(kin) == before


def again(qid, statement):
    return (ToolName.SetQuestion, {"id": qid, "state": "asked", "statement": statement})


@pytest.fixture
def asked_twice(kin, past) -> dict:
    """An open question asked on 20 Sep, and the coach's two later messages
    that asked it again, on 21 and 22 Sep."""
    filed(kin, "q1", "met", "pair_bond", "3", state="asked")
    later = Statement.query.filter_by(text="Tell me more.").one()
    first = db.session.get(Statement, past["reply"])
    first.created_at = datetime.datetime(2026, 9, 21, 12)
    later.created_at = datetime.datetime(2026, 9, 22, 12)
    db.session.commit()
    return {"first": first.id, "later": later.id}


def test_the_days_a_question_was_asked_again_are_planned_and_applied(
    flask_app, tmp_path, kin, past, asked_twice
):
    # R-0774, R-0772
    start = db.session.query(db.func.max(Change.id)).scalar() or 0
    before = stored(kin)
    plan = dry(
        flask_app,
        tmp_path,
        calling(
            again("q1", asked_twice["later"]),
            again("q1", asked_twice["first"]),
            again("q1", past["user"]),
            again("q9", asked_twice["first"]),
        ),
    )

    assert [(a["statement"], a["day"]) for a in plan["asked_again"]] == [
        (asked_twice["first"], "2026-09-21"),
        (asked_twice["later"], "2026-09-22"),
    ]
    assert [d["reason"] for d in plan["dropped"]] == [
        "it names no message of the coach's in this record",
        "only a question still asked is asked again",
    ]
    assert stored(kin) == before

    rows = apply(flask_app, plan)
    assert [(r["part"], r["entry"], r["refused"]) for r in rows] == [
        ("asked again", "q1", None),
        ("asked again", "q1", None),
    ]
    assert stored(kin)["q1"][record.ASKED_AGAIN] == ["2026-09-21", "2026-09-22"]
    assert "passed over: not waiting" in outline(kin.get_diagram_data(), 5)
    made = Change.query.filter(Change.id > start).all()
    assert [c.statement_id for c in made] == [asked_twice["first"], asked_twice["later"]]

    again_ = dry(flask_app, tmp_path, calling(again("q1", asked_twice["first"])))
    assert [d["reason"] for d in again_["dropped"]] == ["the coach's message was already counted"]
    result = flask_app.test_cli_runner().invoke(
        admin, ["diagrams", "undo", str(kin.id), *[str(c.id) for c in made], "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert stored(kin)["q1"] == {**before["q1"], record.ASKED_AGAIN: None}


def test_a_message_from_before_the_first_ask_is_not_counted(flask_app, tmp_path, kin, past, asked_twice):
    # R-0774
    db.session.get(Statement, asked_twice["first"]).created_at = datetime.datetime(2026, 9, 19)
    db.session.commit()
    plan = dry(flask_app, tmp_path, calling(again("q1", asked_twice["first"])))

    assert [d["reason"] for d in plan["dropped"]] == [
        "the coach's message is not after the question was first asked"
    ]
