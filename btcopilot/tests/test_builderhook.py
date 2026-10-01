import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).parents[2] / "bin" / "builder-hook"
VERSIONS = Path("btcopilot/migrations/versions")


def run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=repo, capture_output=True, text=True)


def git(repo: Path, *args: str) -> str:
    result = run(repo, "git", *args)
    assert result.returncode == 0, result.stderr
    return result.stdout


def write(repo: Path, path: str, text: str = "x\n"):
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(text)


def commit(repo: Path, *paths: str) -> subprocess.CompletedProcess:
    git(repo, "add", *paths)
    return run(repo, "git", "commit", "-m", "change")


@pytest.fixture
def repo(tmp_path):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    git(work, "config", "user.email", "new@fd362-fixture.invalid")
    git(work, "config", "user.name", "Builder")
    write(work, f"{VERSIONS}/a_first.py")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "master")
    git(work, "push", "-q", "origin", "master")
    git(work, "checkout", "-q", "-b", "FD-1")
    return work


def install(repo: Path, files: str | None = None, name=None, base=None):
    args = ["install"]
    for flag, value in (("--files", files), ("--name", name), ("--base", base)):
        if value:
            args += [flag, value]
    result = run(repo, sys.executable, str(HOOK), *args)
    assert result.returncode == 0, result.stderr


def test_second_new_migration_refused(repo):
    # R-0622
    install(repo)
    write(repo, f"{VERSIONS}/b_one.py")
    assert commit(repo, str(VERSIONS)).returncode == 0
    write(repo, f"{VERSIONS}/c_two.py")
    result = commit(repo, str(VERSIONS))
    assert result.returncode == 1
    assert "one migration per PR" in result.stderr


def test_file_outside_declared_set_refused(repo):
    # R-0575
    install(repo, "app/mine.py,app/tests/*")
    write(repo, "app/mine.py")
    write(repo, "app/tests/test_mine.py")
    assert commit(repo, "app").returncode == 0
    write(repo, "app/theirs.py")
    result = commit(repo, "app/theirs.py")
    assert result.returncode == 1
    assert "app/theirs.py is outside" in result.stderr


def test_coordinator_without_set_allowed(repo):
    # R-0575
    install(repo, "app/mine.py")
    install(repo)
    write(repo, "app/theirs.py")
    assert commit(repo, "app/theirs.py").returncode == 0


def test_stash_entry_refused(repo):
    # R-0575
    install(repo)
    write(repo, f"{VERSIONS}/a_first.py", "changed\n")
    git(repo, "stash")
    write(repo, "app/mine.py")
    result = commit(repo, "app/mine.py")
    assert result.returncode == 1
    assert "never git stash" in result.stderr


def test_migration_counted_against_the_base_branch(repo):
    # R-0575
    write(repo, f"{VERSIONS}/b_one.py")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "push", "-q", "origin", "FD-1")
    git(repo, "checkout", "-q", "-b", "FD-2")
    install(repo, base="origin/FD-1")
    write(repo, f"{VERSIONS}/c_two.py")
    assert commit(repo, str(VERSIONS)).returncode == 0


def test_stash_entry_from_before_the_install_ignored(repo):
    # R-0575
    write(repo, f"{VERSIONS}/a_first.py", "changed\n")
    subprocess.run(
        ["git", "stash"],
        cwd=repo,
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_COMMITTER_DATE": "2025-01-01T00:00:00"},
    )
    install(repo)
    write(repo, "app/mine.py")
    assert commit(repo, "app/mine.py").returncode == 0


def test_each_builder_commits_within_its_own_set(repo):
    # R-0575
    install(repo, "app/a.py", name="a")
    install(repo, "app/b.py", name="b")
    write(repo, "app/a.py")
    assert commit(repo, "app/a.py").returncode == 0
    write(repo, "app/b.py")
    assert commit(repo, "app/b.py").returncode == 0
    write(repo, "app/a.py", "again\n")
    write(repo, "app/b.py", "again\n")
    assert commit(repo, "app").returncode == 1


def test_conflict_marker_refused(repo):
    # R-0575
    install(repo)
    write(repo, "app/mine.py", "a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> FD-2\n")
    result = commit(repo, "app/mine.py")
    assert result.returncode == 1
    assert "no conflict markers" in result.stderr
