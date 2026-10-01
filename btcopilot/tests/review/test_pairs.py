import json
import random
from decimal import Decimal

import pytest

from btcopilot import ledger
from btcopilot.extensions import db
from btcopilot.models import (
    Discussion,
    ModelCall,
    Purpose,
    ShadowTurn,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.review.models import Pick, PickChoice, PickSource
from btcopilot.review.models.pick import NOTE_CAP

REAL = "claude-opus-5-5"
SHADOW = "gemini-3-flash"
REPLY = "Your aunt Zoë moved to Tromsø the spring your father fell ill, yes?"


@pytest.fixture(autouse=True)
def no_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "PATH", tmp_path / "ledger.jsonl")


def chat(user, diagram, lines: list[str]) -> Discussion:
    """A session whose lines alternate user, coach, user, ..."""
    discussion = Discussion(user_id=user.id, diagram_id=diagram.id)
    db.session.add(discussion)
    db.session.flush()
    you = Speaker(discussion_id=discussion.id, name="You", type=SpeakerType.Subject)
    coach = Speaker(discussion_id=discussion.id, name="Coach", type=SpeakerType.Expert)
    db.session.add_all([you, coach])
    db.session.flush()
    discussion.chat_user_speaker_id = you.id
    discussion.chat_ai_speaker_id = coach.id
    for order, text in enumerate(lines):
        db.session.add(
            Statement(
                discussion_id=discussion.id,
                speaker_id=coach.id if order % 2 else you.id,
                text=text,
                order=order,
                turn_id=f"t{discussion.id}-{order // 2}",
            )
        )
    db.session.commit()
    return discussion


def statements(discussion: Discussion) -> list[Statement]:
    return sorted(discussion.statements, key=lambda s: s.order)


def shadow(
    user, diagram, discussion: Discussion, turn=0, text=REPLY, model=SHADOW
) -> ShadowTurn:
    said, real = statements(discussion)[2 * turn : 2 * turn + 2]
    db.session.add(
        ModelCall(
            user_id=user.id,
            diagram_id=diagram.id,
            turn_id=real.turn_id,
            purpose=Purpose.Coach,
            model=REAL,
            input_tokens=10,
            output_tokens=5,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            cost_usd=Decimal("0.01"),
            duration_ms=900,
            tool_calls=0,
        )
    )
    row = ShadowTurn(
        turn_id=real.turn_id,
        user_id=user.id,
        diagram_id=diagram.id,
        discussion_id=discussion.id,
        statement_id=said.id,
        model=model,
        text=text,
    )
    db.session.add(row)
    db.session.commit()
    return row


def shadowed(user, diagram, text=REPLY) -> ShadowTurn:
    discussion = chat(user, diagram, ["My aunt moved away.", "When was that?"])
    return shadow(user, diagram, discussion, text=text)


def test_a_pair_names_no_model_and_its_sides_vary(patrick, test_user, case):
    # R-0599
    for _ in range(8):
        shadowed(test_user, case)
    random.seed(3)
    pairs = patrick.get("/review/pairs").json
    assert len(pairs) == 8
    served = json.dumps(pairs)
    assert REAL not in served and SHADOW not in served
    assert {pair["left"] for pair in pairs} == {"When was that?", REPLY}
    assert pairs[0]["context"] == [{"who": "user", "text": "My aunt moved away."}]


def test_each_shadow_of_a_turn_pairs_with_the_real_reply(patrick, test_user, case):
    # R-0596, R-0599
    discussion = chat(test_user, case, ["My aunt moved away.", "When was that?"])
    shadow(test_user, case, discussion)
    shadow(test_user, case, discussion, text="Which spring?", model="sonnet")
    pairs = patrick.get("/review/pairs").json
    assert len(pairs) == 2
    assert {frozenset((pair["left"], pair["right"])) for pair in pairs} == {
        frozenset(("When was that?", REPLY)),
        frozenset(("When was that?", "Which spring?")),
    }


def test_a_pair_keeps_its_sides_once_served(patrick, test_user, case):
    # R-0599
    shadowed(test_user, case)
    first = patrick.get("/review/pairs").json
    for seed in range(6):
        random.seed(seed)
        assert patrick.get("/review/pairs").json == first


def test_a_pick_reveals_the_models_and_counts_in_the_summary(patrick, test_user, case):
    # R-0599
    shadowed(test_user, case)
    pair = patrick.get("/review/pairs").json[0]
    shadow_side = PickChoice.Left if pair["left"] == REPLY else PickChoice.Right
    seen = patrick.put(
        f"/review/picks/{pair['id']}", json={"choice": shadow_side, "note": "warmer"}
    ).json
    assert seen[shadow_side] == SHADOW
    assert Pick.query.one().choice is shadow_side
    assert patrick.get("/review/pairs").json == []
    assert patrick.get("/review/picks").json == [
        {"model": REAL, "won": 0, "lost": 1, "tied": 0},
        {"model": SHADOW, "won": 1, "lost": 0, "tied": 0},
    ]


def test_pairs_come_a_conversation_at_a_time_in_the_order_said(
    patrick, test_user, case
):
    # R-0599
    first = chat(test_user, case, ["a one", "coach", "a two", "coach"])
    second = chat(test_user, case, ["b one", "coach", "b two", "coach"])
    for discussion, turn in ((second, 1), (first, 1), (second, 0), (first, 0)):
        shadow(test_user, case, discussion, turn)
    pairs = patrick.get("/review/pairs").json
    assert [pair["context"][-1]["text"] for pair in pairs] == [
        "a one",
        "a two",
        "b one",
        "b two",
    ]


def test_a_pick_keeps_what_was_judged_once_the_shadow_row_is_gone(
    patrick, test_user, case
):
    # R-0599
    row = shadowed(test_user, case)
    served = patrick.get("/review/pairs").json
    db.session.delete(row)
    db.session.commit()
    assert patrick.get("/review/pairs").json == served
    patrick.put(f"/review/picks/{served[0]['id']}", json={"choice": PickChoice.Tie})
    pick = Pick.query.one()
    assert {pick.left_text, pick.right_text} == {"When was that?", REPLY}
    assert patrick.get("/review/picks").json == [
        {"model": REAL, "won": 0, "lost": 0, "tied": 1},
        {"model": SHADOW, "won": 0, "lost": 0, "tied": 1},
    ]


def test_a_long_note_is_refused(patrick, test_user, case):
    # R-0599
    shadowed(test_user, case)
    pair = patrick.get("/review/pairs").json[0]
    response = patrick.put(
        f"/review/picks/{pair['id']}",
        json={"choice": PickChoice.Tie, "note": "x" * (NOTE_CAP + 1)},
    )
    assert response.status_code == 400


def test_replays_of_one_discussion_pair_turn_by_turn(patrick, test_user, case):
    # R-0599
    real = chat(test_user, case, ["one", "real a", "two", "real b"])
    first = chat(test_user, case, ["one", "opus a", "two", "opus b"])
    second = chat(test_user, case, ["one", "flash a", "two", "flash b"])
    for model, scratch in ((REAL, first), (SHADOW, second)):
        row = dict.fromkeys(ledger.FIELDS)
        row.update(
            kind=ledger.LedgerKind.Replay,
            model=model,
            discussion_id=real.id,
            scratch_discussion_id=scratch.id,
        )
        ledger.append(row, ledger.PATH)
    pairs = patrick.get("/review/pairs").json
    assert [sorted([p["left"], p["right"]]) for p in pairs] == [
        ["flash a", "opus a"],
        ["flash b", "opus b"],
    ]
    assert [line["text"] for line in pairs[1]["context"]] == ["one", "real a", "two"]


def test_only_patrick_sees_the_pairs(coder, test_user, case):
    # R-0599
    shadowed(test_user, case)
    assert coder.get("/review/pairs").status_code in (302, 403)
    assert coder.get("/review/picks").status_code in (302, 403)


def turn_of(user, diagram) -> str:
    discussion = chat(user, diagram, ["My aunt moved away.", "When was that?"])
    shadow(user, diagram, discussion)
    shadow(user, diagram, discussion, text="Which spring?", model="sonnet")
    shadow(user, diagram, discussion, model="haiku").error = "overloaded"
    db.session.commit()
    return statements(discussion)[0].turn_id


def test_a_turn_serves_its_replies_blind_in_a_random_order(patrick, test_user, case):
    # R-0636
    turn = turn_of(test_user, case)
    served = []
    for seed in range(6):
        random.seed(seed)
        served.append(patrick.get(f"/review/picks?turn={turn}").json)
    first = served[0]
    assert {reply["text"] for reply in first["replies"]} == {
        "When was that?",
        REPLY,
        "Which spring?",
    }
    assert {reply["key"] for reply in first["replies"]} == {"a", "b", "c"}
    assert len({body["real_key"] for body in served}) > 1
    assert not any(model in json.dumps(served) for model in (REAL, SHADOW, "sonnet"))
    assert Pick.query.count() == 2
    assert {pick["id"] for pick in first["picks"]} == {pick.id for pick in Pick.query}
    for pick in first["picks"]:
        assert first["real_key"] in (pick["left_key"], pick["right_key"])


def test_a_chat_pick_keeps_whether_each_reply_was_acceptable(
    patrick, test_user, case
):
    # R-0640
    pick = patrick.get(f"/review/picks?turn={turn_of(test_user, case)}").json["picks"][0]
    response = patrick.put(
        f"/review/picks/{pick['id']}",
        json={
            "choice": PickChoice.Right,
            "left_acceptable": False,
            "right_acceptable": True,
            "source": PickSource.Chat,
        },
    )
    assert response.status_code == 200
    stored = db.session.get(Pick, pick["id"])
    assert (stored.source, stored.choice) == (PickSource.Chat, PickChoice.Right)
    assert (stored.left_acceptable, stored.right_acceptable) == (False, True)


def test_an_unacceptable_reply_cannot_win(patrick, test_user, case):
    # R-0640
    pick = patrick.get(f"/review/picks?turn={turn_of(test_user, case)}").json["picks"][0]
    response = patrick.put(
        f"/review/picks/{pick['id']}",
        json={
            "choice": PickChoice.Left,
            "left_acceptable": False,
            "right_acceptable": False,
            "source": PickSource.Chat,
        },
    )
    assert response.status_code == 400
    assert db.session.get(Pick, pick["id"]).choice is None


def test_a_turn_is_voted_only_by_a_coder(subscriber, test_user_2, case):
    # R-0636
    turn = turn_of(test_user_2, case)
    assert subscriber.get(f"/review/picks?turn={turn}").status_code in (302, 403)
