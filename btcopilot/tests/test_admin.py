import json

import pytest

import btcopilot
from btcopilot.admin import admin
from btcopilot.admin import setting, skill
from btcopilot.tests import olddump
from btcopilot.admin.setting import SettingKey



@pytest.fixture
def run(flask_app):
    runner = flask_app.test_cli_runner()

    def invoke(*args):
        result = runner.invoke(admin, list(args))
        assert result.exit_code == 0, result.output
        return result.output

    return invoke


def rows(output: str) -> list[dict]:
    return json.loads(output)


def test_users_list_and_show(run, test_user):
    listed = rows(run("users", "list", "--json"))
    assert [one["email"] for one in listed] == [test_user.username]

    shown = rows(run("users", "show", test_user.username, "--json"))
    assert shown[0]["diagram_ids"] == [test_user.free_diagram_id]


def test_users_roles_set_then_read(run, test_user):
    run("users", "roles", test_user.username, btcopilot.ROLE_AUDITOR)
    assert rows(run("users", "roles", test_user.username, "--json"))[0]["roles"] == (
        btcopilot.ROLE_AUDITOR
    )


def test_users_invite_prints_a_link(run, flask_app):
    invited = rows(run("users", "invite", "new@fd362-fixture.invalid", "--json"))
    assert "/personal/invite/" in invited[0]["url"]


def test_unknown_user_is_named(flask_app):
    result = flask_app.test_cli_runner().invoke(admin, ["users", "show", "nobody@x.com"])
    assert result.exit_code != 0 and "no account for nobody@x.com" in result.output


def test_licence_granted_then_revoked(run, test_user, test_policy):
    granted = rows(run("licences", "grant", test_user.username, test_policy.code, "--json"))
    assert granted[0]["status"] == "active"

    revoked = rows(run("licences", "revoke", granted[0]["key"], "--json"))
    assert revoked[0]["status"] == "inactive"


def test_diagram_counts_and_export(run, test_user):
    listed = rows(run("diagrams", "list", "--json"))
    assert listed[0]["id"] == test_user.free_diagram_id

    exported = json.loads(run("diagrams", "export", str(test_user.free_diagram_id)))
    assert isinstance(exported, dict)


def test_import_dry_run_counts_and_writes_nothing(run, tmp_path):
    dump = olddump.build(tmp_path / "old.db")
    counted = rows(run("imports", "dry-run", dump, "--json"))
    assert [one["what"] for one in counted[:2]] == ["users", "diagrams"]
    assert counted[1]["written"] == 1
    assert counted[-1]["why"].startswith("UnpicklingError")
    assert rows(run("users", "list", "--json")) == []


def test_token_cap_default_and_one_person(run, test_user):
    run("token-cap", "set", "default", "100000")
    run("token-cap", "set", test_user.username, "250000")

    mine = rows(run("token-cap", "show", test_user.username, "--json"))
    assert mine[0]["cap"] == 250000 and mine[0]["source"] == "their own"

    assert setting.read(SettingKey.TokenCap) == 100000


def test_token_cap_refuses_a_negative(flask_app, test_user):
    result = flask_app.test_cli_runner().invoke(
        admin, ["token-cap", "set", test_user.username, "--", "-1"]
    )
    assert result.exit_code != 0 and "below zero" in result.output


def test_nudge_switch(run):
    assert rows(run("review", "nudge", "off", "--json"))[0]["nudges"] == "off"
    assert setting.read(SettingKey.NudgesOn) is False

    run("review", "nudge", "on")
    assert setting.read(SettingKey.NudgesOn) is True


def test_agenda_is_empty_before_any_cut(run):
    assert rows(run("review", "agenda", "--json")) == []


def test_table_output_has_a_header(run, test_user):
    output = run("users", "list")
    assert "email" in output.splitlines()[0]


def test_skill_file_is_the_same_bytes_twice():
    assert skill.render(admin) == skill.render(admin)


def test_skill_file_names_every_command():
    text = skill.render(admin)
    for path, command, _ in skill._walk(admin, "flask admin"):
        assert f"`{path}" in text


def test_skill_file_on_disk_is_current(flask_app):
    result = flask_app.test_cli_runner().invoke(admin, ["skill", "--check"])
    assert result.exit_code == 0, result.output
