import subprocess

from btcopilot.tests.repo import REPO

OLD_APPS = {"personal", "pro", "training", "chat", "chatauth", "fdserver"}


def test_no_folder_or_module_is_named_for_an_old_app():
    # R-0469, R-0470, R-0471, R-0472
    tracked = subprocess.run(
        ["git", "ls-files", "btcopilot", "deploy"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    named = {
        path
        for path in tracked
        for part in path.split("/")[:-1] + [path.rsplit("/", 1)[-1].split(".")[0]]
        if part in OLD_APPS
    }
    assert named == set()
