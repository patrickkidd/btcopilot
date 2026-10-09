import json

from btcopilot.admin import admin, setting
from btcopilot.admin.setting import SettingKey
from btcopilot.extensions import db


def invoke(flask_app, *args):
    return flask_app.test_cli_runner().invoke(admin, ["coach-model", *args, "--json"])


def test_set_rejects_an_unknown_model(flask_app, test_user):
    # R-0596
    result = invoke(flask_app, "set", test_user.username, "opus-typo")
    assert result.exit_code != 0 and "unknown model opus-typo" in result.output
    assert setting.read(SettingKey.CoachModel, test_user.id) is None


def test_shadows_set_names_the_shadow_models_for_everyone(flask_app):
    # R-0637
    assert json.loads(invoke(flask_app, "shadows", "show").output) == [
        {"model": "sonnet"}
    ]
    invoke(flask_app, "shadows", "set", "sonnet", "opus-5.5")
    assert setting.shadow_candidates() == ["sonnet", "opus-5.5"]
    result = invoke(flask_app, "shadows", "set", "opus-typo")
    assert result.exit_code != 0 and "unknown model opus-typo" in result.output


def test_set_writes_and_clears_a_persons_model_and_show_names_their_shadows(
    flask_app, test_user
):
    # R-0596
    invoke(flask_app, "set", test_user.username, "sonnet-5")
    test_user.set_prefs(shadow_models=["haiku-4.5", "sonnet"])
    db.session.commit()
    shown = json.loads(invoke(flask_app, "show").output)
    assert shown[1] == {
        "email": test_user.username,
        "model": "sonnet-5",
        "shadow": ["haiku-4.5", "sonnet"],
    }
    invoke(flask_app, "set", test_user.username, "default")
    test_user.set_prefs(shadow_models=[])
    db.session.commit()
    assert setting.read(SettingKey.CoachModel, test_user.id) is None
    assert len(json.loads(invoke(flask_app, "show").output)) == 1
