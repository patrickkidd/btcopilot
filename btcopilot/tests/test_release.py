"""What the release workflow builds, tags and runs on the box."""

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
    assert [m.name for m in migrations] == ["1b00000000aa_the_app_from_empty.py"]
    assert "down_revision = None" in migrations[0].read_text()
    for retired in ("1a00000000ae", "1a00000000af"):
        stamp = next(line for line in DEPLOY.splitlines() if line.strip().startswith(f"{retired})"))
        assert "UPDATE alembic_version SET version_num = '1b00000000aa'" in stamp
    assert DEPLOY.index("1a00000000af)") < DEPLOY.index("flask admin db upgrade")


def test_a_deploy_imports_no_old_records():
    # R-0355
    assert "flask admin db upgrade" in DEPLOY
    assert "imports" not in DEPLOY and "proimport" not in DEPLOY

