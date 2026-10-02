import datetime
from decimal import Decimal

import pytest

import btcopilot
from btcopilot import shadow
from btcopilot.discussions import open_session
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Purpose, Statement
from btcopilot.models.preferences import SHADOW_CANDIDATES, PrefKey
from btcopilot.review.models import Pick, PickChoice, PickSource
from btcopilot.tests.conftest import csrf_token


@pytest.fixture
def token(web):
    return csrf_token(web)


def shadows(web, token, models):
    return web.patch(
        "/app/preferences",
        json={PrefKey.ShadowModels.value: models},
        headers={"X-CSRFToken": token},
    )


def spent(user, turn_id, usd):
    db.session.add(
        ModelCall(
            user_id=user.id,
            turn_id=turn_id,
            purpose=Purpose.Shadow,
            model="claude-sonnet-5-5",
            input_tokens=10,
            output_tokens=5,
            cache_creation_tokens=0,
            cache_read_tokens=0,
            cost_usd=Decimal(usd),
            duration_ms=900,
            tool_calls=0,
        )
    )


def test_only_staff_may_turn_shadows_on(web, token, test_user):
    # R-0637
    assert shadows(web, token, ["sonnet"]).status_code == 403
    assert shadows(web, token, []).status_code == 200
    assert test_user.pref(PrefKey.ShadowModels) == ()


def test_an_auditor_turns_shadows_on_and_only_an_admin_sees_their_cost(
    web, token, test_user
):
    # R-0637
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    body = shadows(web, token, ["sonnet", "gemini-pro"]).get_json()
    assert body[PrefKey.ShadowModels.value] == ["sonnet", "gemini-pro"]
    assert body["shadow_candidates"] == list(SHADOW_CANDIDATES)
    assert "shadow_cost" not in body

    test_user.roles = btcopilot.ROLE_ADMIN
    spent(test_user, "shadow-1", "0.30")
    spent(test_user, "shadow-1", "0.10")
    spent(test_user, "shadow-2", "0.20")
    db.session.commit()
    body = web.get("/app/preferences").get_json()
    assert body["shadow_cost"] == {"per_turn_usd": 0.3, "month_usd": 0.6}


@pytest.mark.parametrize("minutes, on", [(6, False), (4, True)])
def test_shadows_turn_off_five_minutes_after_the_coach_last_replied(
    web, test_user, minutes, on
):
    # R-0637
    test_user.roles = btcopilot.ROLE_AUDITOR
    now = datetime.datetime.utcnow()
    shadow.switch(test_user, ["sonnet"], now - datetime.timedelta(minutes=10))
    discussion = open_session(test_user, test_user.free_diagram)
    said = now - datetime.timedelta(minutes=minutes)
    db.session.add(
        Statement(
            discussion_id=discussion.id,
            speaker_id=discussion.chat_ai_speaker_id,
            text="How much older?",
            created_at=said,
        )
    )
    db.session.commit()
    body = web.get("/app/preferences").get_json()
    assert body[PrefKey.ShadowModels.value] == (["sonnet"] if on else [])
    assert body["shadow_expires_at"] == (
        (said + shadow.IDLE).isoformat() if on else None
    )
    assert bool(test_user.pref(PrefKey.ShadowModels)) == on


def test_a_vote_keeps_shadows_on_five_minutes_after_it(web, test_user):
    # R-0637
    test_user.roles = btcopilot.ROLE_AUDITOR
    now = datetime.datetime.utcnow()
    shadow.switch(test_user, ["sonnet"], now - datetime.timedelta(minutes=10))
    discussion = open_session(test_user, test_user.free_diagram)
    voted = now - datetime.timedelta(minutes=4)
    db.session.add_all(
        [
            Statement(
                discussion_id=discussion.id,
                speaker_id=discussion.chat_ai_speaker_id,
                text="How much older?",
                created_at=now - datetime.timedelta(minutes=8),
            ),
            Pick(
                pair="a-b",
                source=PickSource.Chat,
                left_ref={"model": "sonnet"},
                right_ref={"model": "opus"},
                left_text="Older by two years?",
                right_text="How much older?",
                choice=PickChoice.Left,
                user_id=test_user.id,
                updated_at=voted,
            ),
        ]
    )
    db.session.commit()
    body = web.get("/app/preferences").get_json()
    assert body[PrefKey.ShadowModels.value] == ["sonnet"]
    assert body["shadow_expires_at"] == (voted + shadow.IDLE).isoformat()
