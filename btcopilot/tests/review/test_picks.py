import json
import random
from decimal import Decimal

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


def test_a_turn_counts_the_shadow_replies_still_running(patrick, test_user, case):
    # R-0636
    turn = turn_of(test_user, case)
    row = db.session.get(Statement, ShadowTurn.query.first().statement_id)
    shadow(test_user, case, row.discussion, text=None, model="gemini-3-pro")
    body = patrick.get(f"/review/picks?turn={turn}").json
    assert (body["pending"], body["expected"], len(body["replies"])) == (1, 4, 3)


def test_a_chat_pick_keeps_whether_each_reply_was_acceptable(
    patrick, test_user, case
):
    # R-0640, R-0636
    turn = turn_of(test_user, case)
    pick = patrick.get(f"/review/picks?turn={turn}").json["picks"][0]
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
    voted = next(
        p
        for p in patrick.get(f"/review/picks?turn={turn}").json["picks"]
        if p["id"] == pick["id"]
    )
    assert [voted[k] for k in ("choice", "left_acceptable", "right_acceptable")] == [
        PickChoice.Right,
        False,
        True,
    ]


def test_a_chat_pick_keeps_which_reply_was_shown_first(patrick, test_user, case):
    # R-0640
    turn = turn_of(test_user, case)
    pick = patrick.get(f"/review/picks?turn={turn}").json["picks"][0]
    assert pick["shown"] is None
    patrick.put(
        f"/review/picks/{pick['id']}",
        json={"choice": PickChoice.Tie, "shown": PickChoice.Right},
    )
    stored = db.session.get(Pick, pick["id"])
    assert (stored.left_ref["shown_first"], stored.right_ref["shown_first"]) == (
        False,
        True,
    )
    voted = patrick.get(f"/review/picks?turn={turn}").json["picks"]
    assert next(p for p in voted if p["id"] == pick["id"])["shown"] == PickChoice.Right


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


def test_a_long_note_is_refused(patrick, test_user, case):
    # R-0636
    pick = patrick.get(f"/review/picks?turn={turn_of(test_user, case)}").json["picks"][0]
    response = patrick.put(
        f"/review/picks/{pick['id']}",
        json={"choice": PickChoice.Tie, "note": "x" * (NOTE_CAP + 1)},
    )
    assert response.status_code == 400
    assert db.session.get(Pick, pick["id"]).choice is None


def test_the_better_replies_screen_is_gone(patrick, test_user, case):
    # R-0828
    turn_of(test_user, case)
    assert patrick.get("/review/pairs").status_code == 404
    assert patrick.get("/review/picks").status_code == 400
