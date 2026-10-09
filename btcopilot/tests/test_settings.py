import datetime
from decimal import Decimal

import pytest

import btcopilot
from btcopilot import shadow
from btcopilot.discussions import open_session, utc_iso
from btcopilot.extensions import db
from btcopilot.models import ModelCall, Purpose, ShadowTurn, Statement
from btcopilot.admin import setting
from btcopilot.admin.setting import SettingKey
from btcopilot.models.preferences import PrefKey
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


def ran(said, turn_id, model, usd):
    discussion = said.discussion
    row = ShadowTurn(
        turn_id=turn_id,
        user_id=discussion.user_id,
        diagram_id=discussion.diagram_id,
        discussion_id=discussion.id,
        statement_id=said.id,
        model=model,
        cost_usd=Decimal(usd),
    )
    db.session.add(row)
    db.session.flush()
    spent(discussion.user, f"shadow-{row.id}", usd)


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
    # R-0637, R-0642, R-0643
    test_user.roles = btcopilot.ROLE_AUDITOR
    setting.write(SettingKey.ShadowCandidates, ["sonnet", "haiku-4.5"])
    body = shadows(web, token, ["sonnet", "haiku-4.5"]).get_json()
    assert body[PrefKey.ShadowModels.value] == ["sonnet", "haiku-4.5"]
    assert body["shadow_candidates"] == ["sonnet", "haiku-4.5"]
    assert "shadow_cost" not in body

    test_user.roles = btcopilot.ROLE_ADMIN
    discussion = open_session(test_user, test_user.free_diagram)
    said = Statement(
        discussion_id=discussion.id, speaker_id=discussion.chat_ai_speaker_id, text="Hi"
    )
    db.session.add(said)
    db.session.flush()
    # the first turn ran on both models, the second on one
    ran(said, "t1", "sonnet", "0.30")
    ran(said, "t1", "haiku-4.5", "0.10")
    ran(said, "t2", "sonnet", "0.20")
    db.session.commit()
    body = web.get("/app/preferences").get_json()
    assert body["shadow_cost"] == {"per_turn_usd": 0.3, "month_usd": 0.6}


def test_only_sonnet_is_a_shadow_model_until_an_admin_sets_others(
    web, token, test_user
):
    # R-0637, R-0658
    test_user.roles = btcopilot.ROLE_AUDITOR
    db.session.commit()
    assert web.get("/app/preferences").get_json()["shadow_candidates"] == ["sonnet"]
    assert shadows(web, token, ["haiku-4.5"]).status_code == 400
    assert test_user.pref(PrefKey.ShadowModels) == ()


@pytest.mark.parametrize(
    "candidates, left", [(["sonnet"], ["sonnet"]), (["opus-5.5"], [])]
)
def test_a_model_taken_off_the_shadow_models_is_dropped_from_whoever_had_it(
    web, token, test_user, candidates, left
):
    # R-0637
    test_user.roles = btcopilot.ROLE_AUDITOR
    setting.write(SettingKey.ShadowCandidates, ["sonnet", "haiku-4.5"])
    shadows(web, token, ["sonnet", "haiku-4.5"])
    setting.write(SettingKey.ShadowCandidates, candidates)
    body = web.get("/app/preferences").get_json()
    assert body[PrefKey.ShadowModels.value] == left
    assert test_user.pref(PrefKey.ShadowModels) == tuple(left)
    assert (test_user.pref(PrefKey.ShadowSince) is None) == (not left)


@pytest.mark.parametrize("minutes, on", [(6, False), (4, True)])
def test_shadows_turn_off_five_minutes_after_the_coach_last_replied(
    web, test_user, minutes, on
):
    # R-0637, R-0672
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
    assert body["shadow_expires_at"] == (utc_iso(said + shadow.IDLE) if on else None)
    assert bool(test_user.pref(PrefKey.ShadowModels)) == on


def test_a_vote_keeps_shadows_on_five_minutes_after_it(web, test_user):
    # R-0637, R-0672
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
    assert body["shadow_expires_at"] == utc_iso(voted + shadow.IDLE)
