## https://www.redmadrobot.com/fyi/designing-mobile-app-architecture

import os, logging

# if os.getenv("FLASK_CONFIG") == "production":
#     import ddtrace

#     ddtrace.patch_all(logging=True)


_log = logging.getLogger(__name__)


## Add Git SHA and Cache Headers

_git_sha = None


def git_sha():
    global _git_sha

    if not _git_sha:
        import subprocess

        try:
            # Try to find git executable in common locations
            import shutil

            git_executable = shutil.which("git")
            if not git_executable:
                # Try common locations
                for git_path in [
                    "/usr/bin/git",
                    "/usr/local/bin/git",
                    "/opt/git/bin/git",
                ]:
                    if os.path.isfile(git_path):
                        git_executable = git_path
                        break

            if git_executable:
                # Try to get git SHA from the project root
                project_root = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..")
                )

                # Check if we're in a git repository
                if os.path.isdir(os.path.join(project_root, ".git")):
                    _git_sha = (
                        subprocess.check_output(
                            [git_executable, "rev-parse", "HEAD"],
                            cwd=project_root,
                            stderr=subprocess.DEVNULL,
                        )
                        .decode("utf-8")
                        .strip()[:8]
                    )
                else:
                    _log.debug("Not in a git repository")
                    _git_sha = "no-git"
            else:
                _log.debug("Git executable not found")
                _git_sha = "no-git"

        except Exception as e:
            _log.debug(f"Could not get git SHA: {e}")
            _git_sha = "unknown"

    return _git_sha
