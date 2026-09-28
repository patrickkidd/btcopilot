import json
import random
from decimal import Decimal

import pytest

from btcopilot import ledger
from btcopilot.extensions import db
from btcopilot.models import (
    Discussion,
    ModelCall,
    ShadowTurn,
    Speaker,
    SpeakerType,
    Statement,
)
from btcopilot.review.models import Pick, PickChoice

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


def shadowed(user, diagram, text=REPLY) -> ShadowTurn:
    discussion = chat(user, diagram, ["My aunt moved away.", "When was that?"])
    said, real = statements(discussion)
    db.session.add(
        ModelCall(
            user_id=user.id,
            diagram_id=diagram.id,
            turn_id=real.turn_id,
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
        model=SHADOW,
        text=text,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_a_pair_names_no_model_and_its_sides_vary(patrick, test_user, case):
    # R-0598
    for _ in range(8):
        shadowed(test_user, case)
    random.seed(3)
    pairs = patrick.get("/review/pairs").json
    assert len(pairs) == 8
    served = json.dumps(pairs)
    assert REAL not in served and SHADOW not in served
    assert {pair["left"] for pair in pairs} == {"When was that?", REPLY}
    assert pairs[0]["context"] == [{"who": "user", "text": "My aunt moved away."}]


def test_a_pair_keeps_its_sides_once_served(patrick, test_user, case):
    # R-0598
    shadowed(test_user, case)
    first = patrick.get("/review/pairs").json
    for seed in range(6):
        random.seed(seed)
        assert patrick.get("/review/pairs").json == first


def test_a_pick_reveals_the_models_and_counts_in_the_summary(
    patrick, test_user, case
):
    # R-0598
    shadowed(test_user, case)
    pair = patrick.get("/review/pairs").json[0]
    shadow_side = "left" if pair["left"] == REPLY else "right"
    seen = patrick.put(
        f"/review/picks/{pair['id']}", json={"choice": shadow_side, "note": "warmer"}
    ).json
    assert seen[shadow_side] == SHADOW
    assert Pick.query.one().choice is PickChoice(shadow_side)
    assert patrick.get("/review/pairs").json == []
    assert patrick.get("/review/picks").json == [
        {"model": REAL, "won": 0, "lost": 1, "tied": 0},
        {"model": SHADOW, "won": 1, "lost": 0, "tied": 0},
    ]


def test_a_long_note_is_refused(patrick, test_user, case):
    # R-0598
    shadowed(test_user, case)
    pair = patrick.get("/review/pairs").json[0]
    response = patrick.put(
        f"/review/picks/{pair['id']}", json={"choice": "tie", "note": "x" * 201}
    )
    assert response.status_code == 400


def test_replays_of_one_discussion_pair_turn_by_turn(patrick, test_user, case):
    # R-0598
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
    # R-0598
    shadowed(test_user, case)
    assert coder.get("/review/pairs").status_code in (302, 403)
    assert coder.get("/review/picks").status_code in (302, 403)
