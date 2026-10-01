"""Two records of one person joined in chat on the person's yes: the tool, its
refusals, one change that one undo reverses whole, and the line that tells the
coach a pair may be one person only when the turn touched one of them."""

import copy
import pickle

import pytest

from btcopilot import record, recordtext
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram
from btcopilot.schema import DiagramData, ItemKind, PairBond, Person, from_dict
from btcopilot.matching import likely_same
from btcopilot.tests.conftest import version
from btcopilot.toolbox import ToolError, ToolName, Toolbox

FAMILY = {
    "people": [
        {"id": 1, "name": "Mary", "gender": "female"},
        {"id": 3, "name": "Robert", "last_name": "Stinson", "gender": "male"},
        {"id": 7, "name": "Robert", "gender": "male", "notes": "Took the pipeline job."},
        {"id": 5, "name": "Catherine", "gender": "female", "parents": 20},
        {"id": 8, "name": "Anne", "gender": "female", "parents": 21},
        {"id": 9, "name": "Sue", "gender": "female"},
    ],
    "pair_bonds": [
        {"id": 20, "person_a": 3, "person_b": 1, "married": None},
        {"id": 21, "person_a": 7, "person_b": 1, "married": True},
        {"id": 22, "person_a": 7, "person_b": 9, "married": False},
    ],
    "events": [
        {"id": 30, "kind": "birth", "child": 3, "dateTime": "1942-01-01", "dateCertainty": "approximate"},
        {"id": 31, "kind": "birth", "child": 7, "dateTime": "1944-01-01", "dateCertainty": "approximate"},
        {"id": 32, "kind": "noted", "person": 7, "description": "Moved to Fairbanks", "dateTime": "1981-06-01", "dateCertainty": "approximate"},
        {"id": 33, "kind": "married", "person": 7, "spouse": 1, "dateTime": "1980-05-01", "dateCertainty": "approximate"},
        {"id": 34, "kind": "birth", "child": 8, "person": 7, "spouse": 1, "dateTime": "1982-02-01", "dateCertainty": "approximate"},
    ],
    "questions": [
        {"id": "q1", "kind": "fact", "text": "When was Robert born?", "state": "held", "item_kind": "person", "item_id": 7},
        {"id": "i1", "kind": "impression", "text": "Robert moves when it gets close.", "state": "held", "evidence": [{"kind": "person", "id": 7}]},
    ],
    "lastItemId": 34,
}


def _diagram(user, data: dict) -> Diagram:
    diagram = Diagram(user_id=user.id, name="Record")
    diagram.data = pickle.dumps(copy.deepcopy(data))
    db.session.add(diagram)
    db.session.commit()
    return diagram


def _held(items: list[dict]) -> list[dict]:
    """Items as the page reads them: a field taken back to empty reads as unset."""
    return sorted(
        ({k: v for k, v in i.items() if v is not None} for i in items), key=lambda i: str(i["id"])
    )


def _merge(diagram, turn="t1", **args):
    return Toolbox(diagram.id, turn).call(
        ToolName.MergePeople.value, {"keep": 3, "drop": 7, "version": version(diagram), **args}
    )


def _data(diagram) -> DiagramData:
    db.session.refresh(diagram)
    return diagram.get_diagram_data()


def test_a_merge_of_one_person_with_themselves_is_refused(subscriber):
    # R-0326
    diagram = _diagram(subscriber.user, FAMILY)
    with pytest.raises(ToolError, match="both person 3"):
        _merge(diagram, drop=3)


def test_a_merge_on_a_stale_version_is_refused(subscriber):
    # R-0084
    diagram = _diagram(subscriber.user, FAMILY)
    seen = version(diagram)
    record.apply(
        diagram.id,
        [{"item_kind": ItemKind.Person, "item_id": 9, "field": "name", "after": "Susan"}],
        author=Author.User,
        turn_id="hand",
    )
    with pytest.raises(ToolError, match="changed since version"):
        _merge(diagram, version=seen, take={"birth": "keep", "notes": "keep"})


def test_a_merge_of_a_parent_and_their_child_is_refused(subscriber):
    # R-0326
    diagram = _diagram(subscriber.user, FAMILY)
    with pytest.raises(ToolError, match="partners, or parent and child"):
        Toolbox(diagram.id, "t1").call(
            ToolName.MergePeople.value, {"keep": 1, "drop": 8, "version": version(diagram)}
        )


def test_a_differing_fact_not_named_is_refused_and_named(subscriber):
    # R-0326
    diagram = _diagram(subscriber.user, FAMILY)
    with pytest.raises(ToolError, match="birth: 1942-01-01 on person 3, 1944-01-01 on person 7"):
        _merge(diagram)
    assert {p["id"] for p in _data(diagram).people} == {1, 3, 5, 7, 8, 9}


def test_a_merge_moves_everything_over_as_one_change_and_undo_puts_both_back(subscriber):
    # R-0084, R-0326
    diagram = _diagram(subscriber.user, FAMILY)
    before = _data(diagram)

    text, patch = _merge(diagram, take={"birth": "keep", "notes": "drop"})
    data = _data(diagram)
    events = {e["id"]: e for e in data.events}
    assert {p["id"] for p in data.people} == {1, 3, 5, 8, 9}
    assert events[32]["person"] == 3
    assert (events[33]["person"], events[33]["spouse"]) == (3, 1)
    assert events[34]["person"] == 3
    assert 31 not in events
    assert events[30]["dateTime"] == "1942-01-01"
    assert {(b["id"], record.pair(b)) for b in data.pair_bonds} == {
        (20, ("1", "3")),
        (22, ("3", "9")),
    }
    assert next(b for b in data.pair_bonds if b["id"] == 20)["married"] is True
    people = {p["id"]: p for p in data.people}
    assert people[8]["parents"] == 20
    assert people[3]["notes"] == "Took the pipeline job."
    questions = {q["id"]: q for q in data.questions}
    assert questions["q1"]["item_id"] == 3
    assert questions["i1"]["evidence"] == [{"kind": "person", "id": 3}]
    assert Change.query.filter_by(diagram_id=diagram.id, turn_id="t1").count() == 1
    assert "born 1944 dropped · 1942 kept" in text
    assert "Joined 7 Robert (male)" in text

    Toolbox(diagram.id, "t2").call(ToolName.Undo.value, {})
    after = _data(diagram)
    for collection in ("people", "events", "pair_bonds", "questions"):
        assert _held(getattr(after, collection)) == _held(getattr(before, collection))


def test_a_fact_named_in_take_is_the_dropped_persons(subscriber):
    # R-0326
    diagram = _diagram(subscriber.user, FAMILY)
    text, _ = _merge(diagram, take={"birth": "drop", "notes": "keep"}, name="Robert Louis")
    data = _data(diagram)
    assert next(e for e in data.events if e["id"] == 30)["dateTime"] == "1944-01-01"
    assert next(p for p in data.people if p["id"] == 3)["name"] == "Robert Louis"
    assert "born 1942 dropped · 1944 kept" in text


def test_people_with_near_names_and_no_differing_parents_may_be_one():
    # R-0326
    people = [from_dict(Person, p) for p in FAMILY["people"]]
    bonds = [from_dict(PairBond, b) for b in FAMILY["pair_bonds"]]
    assert [(a.id, b.id) for a, b in likely_same(people, bonds)] == [(3, 7)]


def _record() -> DiagramData:
    return DiagramData(**{k: copy.deepcopy(v) for k, v in FAMILY.items() if k != "lastItemId"})


def test_the_coach_is_told_of_a_pair_only_when_the_turn_touched_one_of_them():
    # R-0072
    data = _record()
    assert recordtext.pairs(data, "Sue called on Sunday.", set()) == ""
    line = recordtext.pairs(data, "Robert moved to Fairbanks.", set())
    assert line.startswith("Persons 3 Robert Stinson (male)")
    assert "they differ on birth 1942-01-01 and 1944-01-01" in line
    assert line.endswith("Their card: [[merge:3,7]]")
    assert recordtext.pairs(data, "That one.", {"7"}) == line
