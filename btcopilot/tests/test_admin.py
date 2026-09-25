import json

import difflib
from unittest import mock

import click

import pytest

import btcopilot
from btcopilot.admin import admin
from btcopilot.admin import guard, setting, skill
from btcopilot.tests import olddump
from btcopilot.admin.setting import SettingKey
from btcopilot.extensions import db
from btcopilot.models import Observation, ObservationKind
from btcopilot.models.preferences import PrefKey, Spotlight


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
    # R-0390
    listed = rows(run("users", "list", "--json"))
    assert [one["email"] for one in listed] == [test_user.username]

    shown = rows(run("users", "show", test_user.username, "--json"))
    assert shown[0]["diagram_ids"] == [test_user.free_diagram_id]


def test_users_roles_set_then_read(run, test_user):
    # R-0390
    run("users", "roles", test_user.username, btcopilot.ROLE_AUDITOR)
    assert rows(run("users", "roles", test_user.username, "--json"))[0]["roles"] == (
        btcopilot.ROLE_AUDITOR
    )


def test_users_prefs_flip_the_spotlight_and_back(run, test_user):
    # R-0168
    shown = rows(run("users", "prefs", test_user.username, "--json"))
    assert shown[0]["spotlight"] == "unified"

    run("users", "prefs", test_user.username, "spotlight", "chip")
    assert test_user.pref(PrefKey.Spotlight) is Spotlight.Chip

    run("users", "prefs", test_user.username, "spotlight", "unified")
    assert test_user.pref(PrefKey.Spotlight) is Spotlight.Unified


def test_users_prefs_takes_a_switch_as_on_or_off(run, test_user):
    # R-0453
    run("users", "prefs", test_user.username, "speak", "on")
    assert test_user.pref(PrefKey.Speak) is True


def test_users_invite_prints_a_link(run, flask_app):
    # R-0390
    invited = rows(run("users", "invite", "new@fd362-fixture.invalid", "--json"))
    assert "/app/invite/" in invited[0]["url"]


def test_unknown_user_is_named(flask_app):
    # R-0390
    result = flask_app.test_cli_runner().invoke(admin, ["users", "show", "nobody@x.com"])
    assert result.exit_code != 0 and "no account for nobody@x.com" in result.output


def test_licence_granted_then_revoked(run, test_user, test_policy):
    # R-0390
    granted = rows(run("licences", "grant", test_user.username, test_policy.code, "--json"))
    assert granted[0]["status"] == "active"

    revoked = rows(run("licences", "revoke", granted[0]["key"], "--json"))
    assert revoked[0]["status"] == "inactive"


def test_diagram_counts_and_export(run, test_user):
    # R-0390
    listed = rows(run("diagrams", "list", "--json"))
    assert listed[0]["id"] == test_user.free_diagram_id

    exported = json.loads(run("diagrams", "export", str(test_user.free_diagram_id)))
    assert isinstance(exported, dict)


def test_observations_list_by_kind(run, test_user):
    # R-0482
    for kind in (ObservationKind.DuplicatePerson, ObservationKind.AddWithoutRead):
        db.session.add(
            Observation(
                diagram_id=test_user.free_diagram_id,
                turn_id="t1",
                kind=kind,
                detail={"ids": [2, 4]},
            )
        )
    db.session.commit()
    listed = rows(run("observations", "list", "--kind", "duplicate_person", "--json"))
    assert [(one["kind"], one["detail"]) for one in listed] == [
        ("duplicate_person", {"ids": [2, 4]})
    ]


def test_import_dry_run_counts_and_writes_nothing(run, tmp_path):
    # R-0327
    dump = olddump.build(tmp_path / "old.db")
    counted = rows(run("imports", "dry-run", dump, "--json"))
    assert [one["what"] for one in counted[:2]] == ["users", "diagrams"]
    assert counted[1]["written"] == 1
    assert counted[-1]["why"].startswith("UnpicklingError")
    assert rows(run("users", "list", "--json")) == []


def test_token_cap_refuses_a_negative(flask_app, test_user):
    # R-0453
    result = flask_app.test_cli_runner().invoke(
        admin, ["token-cap", "set", test_user.username, "--", "-1"]
    )
    assert result.exit_code != 0 and "below zero" in result.output


def test_skill_file_names_every_command():
    # R-0390
    text = skill.render(admin)
    for path, command, _ in skill._walk(admin, "flask admin"):
        assert f"`{path}" in text


def test_skill_file_on_disk_is_current(flask_app):
    # R-0390
    with flask_app.app_context():
        rendered = skill.render(admin)
    on_disk = skill.PATH.read_text()
    diff = "".join(
        difflib.unified_diff(
            on_disk.splitlines(True), rendered.splitlines(True), "on disk", "rendered"
        )
    )
    assert rendered == on_disk, diff


def test_db_upgrade_builds_the_chain_from_empty(flask_app, tmp_path):
    # R-0417
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{tmp_path / 'fresh.db'}"
    result = flask_app.test_cli_runner().invoke(admin, ["db", "upgrade"])
    assert result.exit_code == 0, result.output
    assert result.output.strip().startswith("at 1b00000000ad")


READS = {
    "users list", "users show", "licences list", "licences plans", "diagrams list",
    "diagrams show", "diagrams export", "observations list", "imports dry-run",
    "token-cap show",
    "review agenda", "review cuts", "review codings", "review nudge show",
    "db current", "skill", "run",
}


def test_every_command_is_a_read_or_marked_writes():
    # R-0390
    for path, command, _ in skill._walk(admin, ""):
        name = path.strip()
        if isinstance(command, click.Group):
            continue
        assert guard.marked(command) != (name in READS), name


def test_run_executes_a_read(flask_app, test_user):
    # R-0390
    result = flask_app.test_cli_runner().invoke(admin, ["run", "--", "users", "list"])
    assert result.exit_code == 0, result.output
    assert rows(result.output)[0]["email"] == test_user.username


def test_run_refuses_a_write_without_yes(flask_app, test_user, test_policy):
    # R-0390
    result = flask_app.test_cli_runner().invoke(
        admin, ["run", "--", "licences", "grant", test_user.username, test_policy.code]
    )
    assert result.exit_code == 3
    assert result.output.splitlines()[0] == (
        f"preview: flask admin licences grant {test_user.username} {test_policy.code} --json"
    )
    assert test_user.licenses == []


def test_run_executes_a_write_with_yes(flask_app, test_user, test_policy):
    # R-0390
    result = flask_app.test_cli_runner().invoke(
        admin,
        ["run", "--", "licences", "grant", test_user.username, test_policy.code, "--yes"],
    )
    assert result.exit_code == 0, result.output
    assert rows(result.output)[0]["status"] == "active"


def test_users_invite_send_emails_the_link(run):
    # R-0390
    with mock.patch("btcopilot.admin.users.send_invitation") as send_invitation:
        invited = rows(run("users", "invite", "new@fd362-fixture.invalid", "--send", "--json"))
    send_invitation.assert_called_once_with("new@fd362-fixture.invalid", invited[0]["url"])
