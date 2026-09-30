import json

from btcopilot.admin import admin, setting
from btcopilot.admin.setting import SettingKey


def invoke(flask_app, *args):
    return flask_app.test_cli_runner().invoke(admin, ["coach-model", *args, "--json"])


def test_set_rejects_an_unknown_model(flask_app, test_user):
    # R-0596
    result = invoke(flask_app, "set", test_user.username, "opus-typo")
    assert result.exit_code != 0 and "unknown model opus-typo" in result.output
    assert setting.read(SettingKey.CoachModel, test_user.id) is None


def test_shadow_rejects_a_list_with_an_unknown_model(flask_app, test_user):
    # R-0596
    result = invoke(flask_app, "shadow", test_user.username, "sonnet", "opus-typo")
    assert result.exit_code != 0 and "unknown model opus-typo" in result.output
    assert setting.read(SettingKey.ShadowModel, test_user.id) is None


def test_set_and_shadow_write_and_clear_a_persons_models(flask_app, test_user):
    # R-0596
    invoke(flask_app, "set", test_user.username, "sonnet-5")
    invoke(flask_app, "shadow", test_user.username, "gemini-flash", "sonnet")
    shown = json.loads(invoke(flask_app, "show").output)
    assert shown[1] == {
        "email": test_user.username,
        "model": "sonnet-5",
        "shadow": ["gemini-flash", "sonnet"],
    }
    invoke(flask_app, "set", test_user.username, "default")
    invoke(flask_app, "shadow", test_user.username, "off")
    assert setting.read(SettingKey.CoachModel, test_user.id) is None
    assert setting.read(SettingKey.ShadowModel, test_user.id) is None
    assert len(json.loads(invoke(flask_app, "show").output)) == 1
