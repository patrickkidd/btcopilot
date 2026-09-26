"""The impressions the coach keeps: raised on what the record and the sessions
hold, never removed, pushed back on only by the user, on the map, and shown on
the page only once raised.

Invented names only.
"""

import datetime

import pytest

from btcopilot import chips, record, turnlog
from btcopilot.extensions import db
from btcopilot.interactions import recent
from btcopilot.models import Author, Change, InteractionKind, Observation, ObservationKind, Statement
from btcopilot.recordtext import outline
from btcopilot.schema import DiagramData, ItemKind
from btcopilot.tests.conftest import Model, called, calling, csrf_token, said, version
from btcopilot.tests.test_questions import TODAY, box, stored
from btcopilot.tests.test_turnhistory import coach, family, post, statements, titles  # noqa: F401
from btcopilot.toolbox import ToolError, ToolName

TENSE = "When things get tense, your father gets busy and your mother goes quiet."
LATCH = "You latch on hard to someone, then go deep into something alone."
DOESNT_FIT = "You said that one doesn't fit."


def impress(toolbox, text=TENSE, evidence=({"kind": "person", "id": "1"},), state="raised"):
    return toolbox.call(
        ToolName.AddImpression, {"text": text, "evidence": list(evidence), "state": state}
    )


def settle(toolbox, diagram, impression_id, **args):
    return toolbox.call(
        ToolName.SetImpression, {"id": impression_id, "version": version(diagram), **args}
    )


def by_user(diagram, impression_id, turn="u1", **fields):
    return record.apply(
        diagram.id,
        [
            {"item_kind": "question", "item_id": impression_id, "field": f, "after": v}
            for f, v in fields.items()
        ],
        author=Author.User,
        turn_id=turn,
    )


def event(toolbox, description="Moved out", person=1, date="1994-06-01") -> str:
    toolbox.call(
        ToolName.EditEvent,
        {
            "kind": "noted",
            "description": description,
            "person": person,
            "date": date,
            "date_certainty": "certain",
        },
    )
    return str(toolbox.data.events[-1]["id"])


def test_a_raised_impression_is_one_whole_add_never_removed_and_left_by_undo(family):
    # R-0006, R-0084
    box(family, "t1").call(ToolName.EditPerson, {"name": "Nell"})
    impress(box(family, "t2"))

    row = Change.query.filter_by(turn_id="t2").one()
    assert row.deltas == [
        {
            "item_id": "i1",
            "item_kind": "question",
            "field": None,
            "before": None,
            "after": {
                "id": "i1",
                "text": TENSE,
                "kind": "impression",
                "evidence": [{"kind": "person", "id": "1"}],
                "pushback": None,
                "state": "raised",
                "outcome": None,
                "session_id": 7,
                "asked_at": TODAY,
            },
        }
    ]
    with pytest.raises(ToolError) as refused:
        box(family, "t3").call(
            ToolName.Remove, {"item_kind": "question", "item_id": "i1", "version": version(family)}
        )
    assert refused.value.plain == "A question is never removed."
    box(family, "t4").call(ToolName.Undo, {})
    assert [p["name"] for p in family.get_diagram_data().people] == ["Wren"]
    assert stored(family)["i1"]["state"] == "raised"
    reads = [box(family).call(tool, {})[0].split("\n")[0] for tool in (ToolName.ReadQuestions, ToolName.ReadImpressions)]
    assert reads == ["No questions.", f'i1 raised "{TENSE}" on person 1']


@pytest.mark.parametrize(
    "evidence,plain",
    [
        ([], "It gave the impression nothing to rest on."),
        ([{"kind": "event", "id": "99"}], "That is not in the record."),
        ([{"kind": "statement", "id": "9999"}], "That is not in the record."),
    ],
)
def test_an_impression_must_rest_on_something_the_record_or_the_sessions_hold(
    family, evidence, plain
):
    # R-0084, R-0006
    with pytest.raises(ToolError) as refused:
        impress(box(family), evidence=evidence)
    assert refused.value.plain == plain
    assert stored(family) == {}


def test_removing_what_an_impression_rests_on_unlinks_it_keeps_it_raised_and_undo_puts_it_back(
    family,
):
    # R-0084, R-0482
    toolbox = box(family, "t1")
    toolbox.call(ToolName.EditPerson, {"name": "Nell"})
    moved = event(toolbox)
    impress(toolbox, evidence=[{"kind": "person", "id": "2"}, {"kind": "event", "id": moved}])

    for turn, kind, item_id in (("t2", "person", "2"), ("t3", "event", moved)):
        box(family, turn).call(
            ToolName.Remove, {"item_kind": kind, "item_id": item_id, "version": version(family)}
        )
    assert (stored(family)["i1"]["state"], stored(family)["i1"]["evidence"]) == ("raised", [])
    assert f'i1 raised "{TENSE}" on nothing' in outline(family.get_diagram_data(), 1)

    box(family, "t4").call(ToolName.Undo, {})
    assert stored(family)["i1"]["evidence"] == [{"kind": "event", "id": moved}]


def test_only_the_user_turns_an_impression_down_and_only_the_coach_revises_or_lets_it_go(family):
    # R-0077
    toolbox = box(family)
    impress(toolbox)
    impress(toolbox, LATCH)

    for args, plain in (
        ({"state": "resolved", "outcome": "doesnt_fit"}, "Only you can push back on an impression."),
        ({"state": "resolved", "outcome": "answered"}, "That is not how an impression ends."),
    ):
        with pytest.raises(ToolError) as refused:
            settle(toolbox, family, "i1", **args)
        assert refused.value.plain == plain
    for fields in ({"pushback": "partly", "text": "Something else."}, {"state": "resolved", "outcome": "revised"}):
        with pytest.raises(record.Invalid) as invalid:
            by_user(family, "i1", **fields)
        assert invalid.value.plain == "Only you can push back on an impression."
    with pytest.raises(record.Invalid):
        record.apply(
            family.id,
            [{"item_kind": "question", "item_id": "i1", "field": "pushback", "after": "partly"}],
            author=Author.Coach,
            turn_id="t9",
        )

    by_user(family, "i1", pushback="partly")
    by_user(family, "i2", "u2", state="resolved", outcome="doesnt_fit")
    settle(toolbox, family, "i1", state="resolved", outcome="revised")
    assert [(q["state"], q["outcome"], q["pushback"]) for q in stored(family).values()] == [
        ("resolved", "revised", "partly"),
        ("resolved", "doesnt_fit", None),
    ]


def test_the_words_of_an_impression_that_did_not_fit_are_never_raised_again(family):
    # R-0479, R-0482
    toolbox = box(family)
    impress(toolbox)
    with pytest.raises(ToolError) as refused:
        impress(toolbox, TENSE.upper())
    assert refused.value.plain == "That impression is already there."
    toolbox.call(ToolName.AddQuestion, {"text": TENSE, "kind": "thought", "state": "asked"})
    by_user(family, "i1", state="resolved", outcome="doesnt_fit")

    with pytest.raises(ToolError) as refused:
        impress(toolbox, f"  {TENSE} ")
    assert refused.value.plain == DOESNT_FIT
    assert sorted(stored(family)) == ["i1", "q1"]


MAP = DiagramData(
    people=[{"id": 1, "name": "Wren"}],
    questions=[
        {"id": "q1", "text": "Who raised you?", "kind": "fact", "state": "asked", "outcome": None},
        {"id": "i1", "text": LATCH, "kind": "impression", "state": "raised", "outcome": None,
         "pushback": "partly", "evidence": [{"kind": "event", "id": 3}, {"kind": "statement", "id": 812}]},
        {"id": "i2", "text": "A lot was happening in 1998 to 1999.", "kind": "impression",
         "state": "resolved", "outcome": "doesnt_fit", "pushback": None,
         "evidence": [{"kind": "cluster", "id": "c2"}]},
        {"id": "i3", "text": TENSE, "kind": "impression", "state": "raised", "outcome": None,
         "pushback": None, "evidence": [{"kind": "event", "id": 14}, {"kind": "event", "id": 22}]},
        {"id": "i4", "text": "Kept.", "kind": "impression", "state": "held", "outcome": None,
         "pushback": None, "evidence": [{"kind": "person", "id": 1}]},
        {"id": "i5", "text": "Taken back.", "kind": "impression", "state": "resolved",
         "outcome": "revised", "pushback": None, "evidence": [{"kind": "person", "id": 1}]},
        {"id": "i6", "text": "Dropped.", "kind": "impression", "state": "resolved",
         "outcome": "let_go", "pushback": None, "evidence": [{"kind": "person", "id": 1}]},
    ],
)


def test_the_map_lists_each_impression_by_what_happened_to_it():
    # R-0479
    text = outline(MAP, 5)
    assert (
        "IMPRESSIONS (raised and held; one the user said doesn't fit is never raised "
        "again in those words)\n"
        f'i1 raised partly "{LATCH}" on event 3, statement 812\n'
        f'i3 raised "{TENSE}" on event 14, event 22\n'
        'i4 held "Kept." on person 1\n'
        'i2 doesn\'t fit "A lot was happening in 1998 to 1999." on cluster c2'
    ) in text
    assert "Taken back." not in text and "Dropped." not in text
    assert 'q1 asked fact "Who raised you?"' in text.split("IMPRESSIONS")[0]


def raising_turn(web, monkeypatch, said_before: int):
    coach(
        monkeypatch,
        Model(
            calling(
                (
                    ToolName.AddImpression,
                    {
                        "text": TENSE,
                        "state": "raised",
                        "evidence": [
                            {"kind": "person", "id": "1"},
                            {"kind": "statement", "id": str(said_before)},
                        ],
                    },
                ),
                (
                    ToolName.AddImpression,
                    {"text": LATCH, "state": "held", "evidence": [{"kind": "person", "id": "1"}]},
                ),
            ),
            called(ToolName.ReadImpressions),
            said(f"Here is what I notice. {TENSE}"),
        ),
    )
    return post(web, csrf_token(web), "Dad works late when Mum goes quiet.").get_json()


@pytest.fixture
def first(web, family, monkeypatch) -> dict:
    coach(monkeypatch, Model(said("Tell me more.")))
    body = post(web, csrf_token(web), "My parents fight a lot.").get_json()
    return statements(web, body["discussion_id"])[0]


def test_impression_calls_are_kept_with_their_names_and_one_change_row_each(
    web, family, monkeypatch, first
):
    # R-0478
    body = raising_turn(web, monkeypatch, first["id"])

    reply = statements(web, body["discussion_id"])[-1]
    assert [(t["name"], t["names"].get("it"), t["names"].get("evidence")) for t in reply["tools"]] == [
        ("add_impression", TENSE, ["Wren", f"You said, {first_day(first)}"]),
        ("add_impression", None, ["Wren"]),
        ("read_impressions", None, None),
    ]
    rows = Change.query.filter_by(statement_id=reply["id"]).all()
    assert len(rows) == len([t for t in reply["tools"] if t["name"] != "read_impressions"])


def made(statement: dict) -> datetime.datetime:
    return db.session.get(Statement, statement["id"]).created_at


def first_day(statement: dict) -> str:
    return f"{made(statement).day} {made(statement):%b}"


def test_the_page_gets_raised_impressions_with_labelled_evidence_and_never_a_held_one(
    web, family, monkeypatch, first
):
    # R-0006, R-0072
    body = raising_turn(web, monkeypatch, first["id"])

    shown = web.get("/app/timeline").get_json()["asked_questions"]
    assert shown == [
        {
            "id": "i1",
            "text": TENSE,
            "kind": "impression",
            "open": True,
            "asked_at": TODAY,
            "asked_in": {
                "discussion_id": body["discussion_id"],
                "statement_id": statements(web, body["discussion_id"])[-1]["id"],
            },
            "evidence": [
                {"kind": "person", "id": "1", "label": "Wren"},
                {
                    "kind": "statement",
                    "id": first["id"],
                    "label": f"You said, {first_day(first)}",
                    "discussion_id": body["discussion_id"],
                    "at": made(first).date().isoformat(),
                },
            ],
            "pushback": None,
        }
    ]
    everything = [
        web.get("/app/timeline").get_data(as_text=True),
        web.get(f"/app/sessions/{body['discussion_id']}").get_data(as_text=True),
        str([event for _, event in turnlog.read_from(body["turn_id"], 0)]),
    ]
    assert [LATCH in text for text in everything] == [False, False, False]


def test_the_user_says_an_impression_doesnt_fit_or_pushes_back_in_part(
    web, family, monkeypatch, first
):
    # R-0077
    raising_turn(web, monkeypatch, first["id"])
    token = csrf_token(web)

    partly = web.patch("/app/questions/i1", json={"pushback": "partly"}, headers={"X-CSRFToken": token})
    assert partly.get_json() == {"id": "i1", "state": "raised", "outcome": None, "pushback": "partly"}
    turned = web.patch(
        "/app/questions/i1",
        json={"state": "resolved", "outcome": "doesnt_fit"},
        headers={"X-CSRFToken": token},
    )
    assert turned.status_code == 200
    tap = web.post(
        "/app/interactions",
        json={"diagram_id": family.id, "kind": "doesnt_fit", "item_kind": "question", "item_id": "i1"},
        headers={"X-CSRFToken": token},
    )
    assert tap.status_code == 201
    assert [(i.kind, i.item_kind, i.item_id) for i in recent(family.id)] == [
        (InteractionKind.DoesntFit, ItemKind.Question, "i1")
    ]
    assert f'i1 doesn\'t fit "{TENSE}"' in outline(family.get_diagram_data(), 1)


def test_an_impression_chip_and_a_pair_bond_chip_survive_and_a_wrong_kind_does_not():
    # R-0072
    data = DiagramData(
        people=[{"id": 1, "name": "Wren"}, {"id": 2, "name": "Bo"}],
        pair_bonds=[{"id": 3, "person_a": 1, "person_b": 2}],
        questions=MAP.questions,
    )
    text = chips.validate("[[impression:i3]] [[pair_bond:3]] [[impression:q1]]", data)
    assert text == "[[impression:i3]] [[pair_bond:3]] this impression"
    assert chips.context("[[pair_bond:3]] [[impression:i3]]", data).splitlines()[1:] == [
        "pair bond 3: Wren & Bo",
        f'impression i3: "{TENSE}"',
    ]


def test_a_cluster_keeps_the_reason_the_coach_gives_for_it(family):
    # R-0076
    toolbox = box(family)
    ids = [int(event(toolbox, f"Move {n}", date=f"199{n}-01-01")) for n in (7, 8, 9)]
    toolbox.call(
        ToolName.EditCluster,
        {"name": "Upheaval", "event_ids": ids, "reason": "A lot was happening in 1997 to 1999."},
    )
    assert family.get_diagram_data().clusters[-1]["reason"] == "A lot was happening in 1997 to 1999."


def test_a_reply_that_hardly_holds_the_impression_it_raised_is_observed(web, family, monkeypatch):
    # R-0482
    coach(
        monkeypatch,
        Model(
            calling(
                (
                    ToolName.AddImpression,
                    {"text": TENSE, "state": "raised", "evidence": [{"kind": "person", "id": "1"}]},
                )
            ),
            said("Tell me more about that."),
        ),
    )
    post(web, csrf_token(web), "Dad works late.")

    assert [o.detail["question"] for o in Observation.query.filter_by(kind=ObservationKind.QuestionUnsaid)] == ["i1"]
