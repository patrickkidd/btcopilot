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


def test_set_writes_and_clears_a_persons_model_and_show_names_their_shadows(
    flask_app, test_user
):
    # R-0596
    invoke(flask_app, "set", test_user.username, "sonnet-5")
    test_user.set_prefs(shadow_models=["gemini-pro", "sonnet"])
    db.session.commit()
    shown = json.loads(invoke(flask_app, "show").output)
    assert shown[1] == {
        "email": test_user.username,
        "model": "sonnet-5",
        "shadow": ["gemini-pro", "sonnet"],
    }
    invoke(flask_app, "set", test_user.username, "default")
    test_user.set_prefs(shadow_models=[])
    db.session.commit()
    assert setting.read(SettingKey.CoachModel, test_user.id) is None
    assert len(json.loads(invoke(flask_app, "show").output)) == 1
