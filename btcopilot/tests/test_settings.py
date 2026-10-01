from decimal import Decimal

import pytest

import btcopilot
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Purpose
from btcopilot.models.preferences import SHADOW_CANDIDATES, PrefKey
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
