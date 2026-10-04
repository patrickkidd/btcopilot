"""The case report's cards the coach marks on its guesses and questions, the
person's own answer about their own part, and the book passages behind each
card.

Invented names only.
"""

import pytest

from btcopilot import diagramjson, questions, record
from btcopilot.extensions import db
from btcopilot.models import Author, Change, Diagram, Statement
from btcopilot.routes.diagrams import diagram_payload
from btcopilot.routes.fixtures import CASE_REPORT_CHAT, install
from btcopilot.tests.conftest import version
from btcopilot.tests.test_impressions import LATCH, TENSE, first, impress  # noqa: F401
from btcopilot.tests.test_questions import add, box, clock, stored  # noqa: F401
from btcopilot.tests.test_turnhistory import family  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName, Toolbox

QUIET = "When you and Tom go quiet, your mother calls you more."
CLOSE = "Your sister moved home the year your father fell ill."
OWN = "What do you think your own part was?"


def raised(diagram, *texts) -> list[str]:
    for n, text in enumerate(texts):
        impress(box(diagram, f"r{n}"), text=text)
    return list(stored(diagram))


def card(diagram, entry_id, value, turn="c1", tool=ToolName.SetImpression):
    return box(diagram, turn).call(
        tool, {"id": entry_id, "version": version(diagram), "case_report_card": value}
    )


def cards(diagram) -> dict:
    return {i: q.get("case_report_card") for i, q in stored(diagram).items()}


def test_the_newest_main_guess_takes_the_card_off_the_one_before_in_the_same_change(family):
    # R-0709
    raised(family, TENSE, LATCH)
    card(family, "i1", "main_guess", "c1")
    card(family, "i2", "main_guess", "c2")

    assert cards(family) == {"i1": None, "i2": "main_guess"}
    row = Change.query.filter_by(turn_id="c2").one()
    assert sorted((d["item_id"], d["after"]) for d in row.deltas) == [
        ("i1", None),
        ("i2", "main_guess"),
    ]


def test_what_to_work_on_keeps_the_three_newest(family):
    # R-0709
    raised(family, TENSE, LATCH, QUIET, CLOSE)
    for n, entry in enumerate(["i1", "i2", "i3", "i4"]):
        card(family, entry, "work_on", f"c{n}")

    assert cards(family) == {"i1": None, "i2": "work_on", "i3": "work_on", "i4": "work_on"}


def test_a_card_is_set_without_moving_the_state_and_taken_off_with_null(family):
    # R-0709
    raised(family, TENSE)
    card(family, "i1", "own_part")

    assert stored(family)["i1"]["state"] == "raised"
    assert cards(family) == {"i1": "own_part"}
    card(family, "i1", None, "c2")
    assert cards(family) == {"i1": None}


def test_an_impression_added_on_a_card_is_on_it_and_on_the_coachs_map(family):
    # R-0709
    box(family).call(
        ToolName.AddImpression,
        {
            "text": TENSE,
            "evidence": [{"kind": "person", "id": "1"}],
            "state": "raised",
            "case_report_card": "choice",
        },
    )

    assert cards(family) == {"i1": "choice"}
    assert "card=choice" in box(family).call(ToolName.ReadImpressions, {})[0]


def test_a_question_goes_only_on_the_own_part_or_the_choice_card(family):
    # R-0709
    add(box(family), text=OWN, kind="thought", case_report_card="own_part")
    assert cards(family) == {"q1": "own_part"}

    with pytest.raises(ToolError, match="only on own_part or choice"):
        card(family, "q1", "main_guess", tool=ToolName.SetQuestion)


def test_a_guess_kept_for_later_goes_on_no_card(family):
    # R-0709
    with pytest.raises(ToolError, match="is held"):
        box(family).call(
            ToolName.AddImpression,
            {
                "text": TENSE,
                "evidence": [{"kind": "person", "id": "1"}],
                "state": "held",
                "case_report_card": "main_guess",
            },
        )


def test_only_the_coach_puts_an_entry_on_a_card(family):
    # R-0709
    raised(family, TENSE)

    with pytest.raises(record.Invalid):
        record.apply(
            family.id,
            [{"item_kind": "question", "item_id": "i1", "field": "case_report_card", "after": "main_guess"}],
            author=Author.User,
            turn_id="u1",
        )
    assert cards(family) == {"i1": None}


def test_the_persons_answer_about_their_own_part_is_on_the_page_in_their_words(
    web, family, first  # noqa: F811
):
    # R-0708
    add(box(family), text=OWN, kind="thought", case_report_card="own_part")
    box(family, "t2").call(
        ToolName.SetQuestion,
        {"id": "q1", "version": version(family), "state": "resolved", "outcome": "answered", "answer": first["id"]},
    )

    shown = web.get("/app/timeline").get_json()["asked_questions"]
    answer = shown[0]["answer"]
    assert (shown[0]["case_report_card"], answer["id"], answer["text"]) == (
        "own_part",
        first["id"],
        "My parents fight a lot.",
    )
    assert answer["label"].startswith("You said, ")


def test_closing_a_carded_question_as_answered_keeps_the_message_being_replied_to(
    family, first  # noqa: F811
):
    # R-0708
    add(box(family), text=OWN, kind="thought", case_report_card="own_part")
    said = db.session.get(Statement, first["id"])
    from_turn = Toolbox(family.id, "t2", session_id=7, author=Author.Coach, said=said)
    from_turn.call(
        ToolName.SetQuestion,
        {"id": "q1", "version": version(family), "state": "resolved", "outcome": "answered"},
    )

    assert stored(family)["q1"]["answer"]["id"] == first["id"]


def test_an_answer_is_kept_only_on_a_question_closed_as_answered(family, first):  # noqa: F811
    # R-0708
    add(box(family), text=OWN, kind="thought")

    with pytest.raises(ToolError, match="only when closing a question as answered"):
        box(family, "t2").call(
            ToolName.SetQuestion,
            {"id": "q1", "version": version(family), "state": "resolved", "outcome": "let_go", "answer": first["id"]},
        )


@pytest.fixture
def passages(flask_app, monkeypatch):
    held = flask_app.extensions["passages"]
    monkeypatch.setattr(held, "file", lambda name: '{"1": [{"text": "a diagram", "by": "a book"}]}')
    return held


def test_the_book_passages_are_served_to_a_reader_who_may_open_the_diagram(web, family, passages):
    # R-0692, R-0715
    response = web.get(f"/app/case-report-passages?diagram_id={family.id}")

    assert response.get_json() == {"1": [{"text": "a diagram", "by": "a book"}]}


def test_the_book_passages_are_a_404_to_one_who_may_not(web, test_user_2, passages):
    # R-0692, R-0715
    theirs = Diagram(user_id=test_user_2.id, name="Their Family", data=diagramjson.dumps({}))
    db.session.add(theirs)
    db.session.commit()

    assert web.get(f"/app/case-report-passages?diagram_id={theirs.id}").status_code == 404


def test_the_case_report_fixture_holds_every_card_and_the_persons_own_answer(flask_app):
    # R-0708, R-0709
    diagram = install("case-report").free_diagram
    shown = {q["id"]: q for q in questions.asked(diagram.id, diagram.get_diagram_data())}

    assert {i: q["case_report_card"] for i, q in shown.items() if q["case_report_card"]} == {
        "i1": "main_guess",
        "i2": "own_part",
        "i3": "choice",
        "i4": "work_on",
        "i5": "work_on",
        "q1": "own_part",
        "q2": "choice",
    }
    assert "i7" not in shown
    assert shown["q1"]["answer"]["text"] == CASE_REPORT_CHAT[2][1]
    card(diagram, "i6", "main_guess")
    assert cards(diagram)["i1"] is None


def test_the_thin_and_dense_case_report_fixtures_install(flask_app):
    # R-0699, R-0709
    thin = install("case-report-thin").free_diagram.get_diagram_data()
    dense = install("case-report-dense").free_diagram.get_diagram_data()

    assert (len(thin.people), thin.questions) == (1, [])
    assert (len(dense.people), len(dense.events)) == (125, 281)
    assert any(e["dateTime"] is None for e in dense.events)


def test_the_case_report_names_its_owner_by_name_and_never_by_email(flask_app):
    # R-0715
    named = install("case-report")
    nameless = install("one")

    assert diagram_payload(named.free_diagram, named)["owner_name"] == "Nora Halloran"
    assert diagram_payload(nameless.free_diagram, nameless)["owner_name"] is None
    assert diagram_payload(nameless.free_diagram, nameless)["owner"] == nameless.username
