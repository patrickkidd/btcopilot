"""What the release workflow builds, tags and runs on the box."""

import hashlib
import subprocess

import pytest
import yaml

from btcopilot.tests.repo import REPO

RELEASE = yaml.safe_load((REPO / ".github" / "workflows" / "release.yml").read_text())
BUILD = {step.get("name"): step for step in RELEASE["jobs"]["build"]["steps"]}
DEPLOY = RELEASE["jobs"]["deploy"]["steps"][0]["with"]["script"]


def test_the_version_is_a_dated_three_and_the_image_tag_swaps_the_plus():
    # R-0419
    stamp = BUILD["Version"]["run"]
    assert "--date=format-local:%Y.%-m.%-d" in stamp
    assert 'version="3.${day}.${n}+g$(git rev-parse --short=7 HEAD)"' in stamp
    assert 'echo "tag=${version/+/-}"' in stamp
    tags = BUILD["Build and push the image"]["with"]["tags"]
    assert "${{ steps.version.outputs.tag }}" in tags
    assert not (REPO / "deploy" / "chat" / "appcast").exists()


def test_one_migration_and_the_box_is_stamped_to_it_on_deploy():
    # R-0417
    migrations = sorted((REPO / "btcopilot" / "migrations" / "versions").glob("*.py"))
    assert migrations[0].name == "1b00000000aa_the_app_from_empty.py"
    assert "down_revision = None" in migrations[0].read_text()
    for retired in ("1a00000000ae", "1a00000000af"):
        stamp = next(line for line in DEPLOY.splitlines() if line.strip().startswith(f"{retired})"))
        assert "UPDATE alembic_version SET version_num = '1b00000000aa'" in stamp
    assert DEPLOY.index("1a00000000af)") < DEPLOY.index("flask admin db upgrade")


@pytest.mark.parametrize(
    "at, stops",
    [
        ("", False),
        ("1a00000000ae", False),
        ("1a00000000af", False),
        ("1b00000000aa", False),
        ("1b00000000ae", False),
        ("1c00000000aa", True),
    ],
)
def test_the_revision_check_passes_the_current_chain_and_stops_before_the_swap(
    at, stops
):
    # R-0417
    lines = DEPLOY.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == 'case "$at" in')
    end = next(i for i, l in enumerate(lines) if l.strip() == "esac")
    check = "\n".join(lines[start : end + 1])
    ran = subprocess.run(
        ["bash", "-c", f'set -e; psql() {{ :; }}; at="{at}"\n{check}'],
        cwd=REPO / "deploy",
        capture_output=True,
        text=True,
    )
    assert (ran.returncode != 0) is stops, ran.stderr
    assert DEPLOY.index('case "$at" in') < DEPLOY.index("docker rollout")


def test_a_migration_that_ran_in_production_is_never_rewritten_and_later_ones_chain():
    # R-0417
    migrations = sorted((REPO / "btcopilot" / "migrations" / "versions").glob("*.py"))
    released = hashlib.sha256(migrations[0].read_bytes()).hexdigest()
    assert released == "e543ab5be81bc03624dad70ea3b6c4e40c08e2301379c9845902d7608cd6b1a1"
    for before, after in zip(migrations, migrations[1:]):
        revision = before.name.split("_")[0]
        assert f'down_revision = "{revision}"' in after.read_text(), after.name


def test_a_deploy_imports_no_old_records():
    # R-0355
    assert "flask admin db upgrade" in DEPLOY
    assert "imports" not in DEPLOY and "proimport" not in DEPLOY

