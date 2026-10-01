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
    git(work, "config", "user.email", "builder@example.com")
    git(work, "config", "user.name", "Builder")
    write(work, f"{VERSIONS}/a_first.py")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "master")
    git(work, "push", "-q", "origin", "master")
    git(work, "checkout", "-q", "-b", "FD-1")
    return work


def install(repo: Path, files: str | None = None):
    args = ["install"] + (["--files", files] if files else [])
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


def test_conflict_marker_refused(repo):
    # R-0575
    install(repo)
    write(repo, "app/mine.py", "a\n<<<<<<< HEAD\nb\n=======\nc\n>>>>>>> FD-2\n")
    result = commit(repo, "app/mine.py")
    assert result.returncode == 1
    assert "no conflict markers" in result.stderr
