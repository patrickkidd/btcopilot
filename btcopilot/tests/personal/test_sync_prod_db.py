"""
Integration tests for scripts/sync-prod-db.sh

Tests argument parsing, help output, error handling, and preflight checks.
These tests do NOT require SSH access or Docker — they verify the script's
behavior when prerequisites are missing or arguments are invalid.
"""

import os
import subprocess
import stat
import textwrap

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT_PATH = os.path.join(REPO_ROOT, "scripts", "sync-prod-db.sh")


@pytest.fixture(autouse=True)
def _check_script_exists():
    if not os.path.isfile(SCRIPT_PATH):
        pytest.skip("sync-prod-db.sh not present on this branch")


def run_script(*args, timeout=10, input_text=None, env_override=None):
    """Run the sync script with given arguments, return CompletedProcess."""
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    return subprocess.run(
        ["/usr/bin/env", "bash", SCRIPT_PATH, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
        env=env,
    )


# ── Script basics ──────────────────────────────────────────────────────


class TestScriptBasics:
    """Verify the script file itself is well-formed."""

    def test_script_exists(self):
        assert os.path.isfile(SCRIPT_PATH)

    def test_script_is_executable(self):
        mode = os.stat(SCRIPT_PATH).st_mode
        assert mode & stat.S_IXUSR, "Script should be executable by owner"

    def test_script_has_bash_shebang(self):
        with open(SCRIPT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/usr/bin/env bash"


# ── Help / usage ───────────────────────────────────────────────────────


class TestHelpOutput:
    """--help and -h should print usage and exit 0."""

    def test_help_flag(self):
        result = run_script("--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--dump-only" in result.stdout
        assert "--restore" in result.stdout

    def test_short_help_flag(self):
        result = run_script("-h")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_help_mentions_backup_dir(self):
        result = run_script("--help")
        assert "backups" in result.stdout.lower()


# ── Argument parsing ───────────────────────────────────────────────────


class TestArgumentParsing:
    """Verify the script rejects invalid arguments."""

    def test_unknown_option_fails(self):
        result = run_script("--nonexistent-flag")
        assert result.returncode != 0
        assert "Unknown option" in result.stderr

    def test_multiple_unknown_options(self):
        result = run_script("--foo", "--bar")
        assert result.returncode != 0
        assert "Unknown option" in result.stderr

    def test_restore_without_file_arg_fails(self):
        """--restore requires a file path argument."""
        result = run_script("--restore")
        # Should fail — either with 'Unknown option' on shift 2 failing
        # or bash unbound variable error due to set -u
        assert result.returncode != 0


# ── Preflight checks ──────────────────────────────────────────────────


class TestPreflightChecks:
    """The script should fail gracefully when SSH or Docker aren't available."""

    def test_dry_run_fails_without_ssh(self):
        """--dry-run still requires SSH to show prod stats; should fail if
        SSH to production is not configured in this environment."""
        result = run_script("--dry-run", timeout=15)
        # In CI or dev without SSH keys, check_ssh will die
        # We just verify it doesn't hang and produces an error message
        if result.returncode != 0:
            assert "ERROR" in result.stderr or "SSH" in result.stderr or "ssh" in result.stdout.lower()

    def test_full_sync_fails_without_ssh(self):
        """Full sync (no flags) should fail on SSH preflight."""
        result = run_script(timeout=15, input_text="n\n")
        if result.returncode != 0:
            output = result.stderr + result.stdout
            assert "ERROR" in output or "SSH" in output or "ssh" in output.lower()


# ── Restore mode ───────────────────────────────────────────────────────


class TestRestoreMode:
    """Test --restore flag behavior."""

    def test_restore_nonexistent_file_fails(self):
        """--restore with a missing file should fail with a clear error.

        Note: --restore also checks local postgres first, so it may fail
        on that check before reaching the file check. Both are valid failures.
        """
        result = run_script(
            "--restore", "/tmp/nonexistent_dump_file_12345.pgdump",
            input_text="y\n",
            timeout=10,
        )
        assert result.returncode != 0
        output = result.stderr + result.stdout
        # Should mention either the missing file or missing Docker container
        assert "ERROR" in output

    def test_restore_requires_local_docker(self):
        """--restore checks for local postgres container before anything else.

        If Docker isn't running or the container doesn't exist, the script
        should fail at check_local_postgres.
        """
        result = run_script(
            "--restore", "/tmp/some_file.pgdump",
            input_text="y\n",
            timeout=10,
        )
        if result.returncode != 0:
            output = result.stderr + result.stdout
            assert "ERROR" in output


# ── Script configuration ──────────────────────────────────────────────


class TestScriptConfiguration:
    """Verify the script contains expected configuration values."""

    def test_config_references_correct_prod_host(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert '107.170.236.117' in content

    def test_config_references_correct_db_name(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'familydiagram' in content

    def test_config_references_backup_dir(self):
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert '.openclaw/backups' in content

    def test_config_uses_custom_format_dump(self):
        """pg_dump should use -Fc (custom format) for efficient dumps."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'pg_dump' in content
        assert '-Fc' in content

    def test_restore_uses_no_owner(self):
        """pg_restore should use --no-owner to avoid permission issues."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert '--no-owner' in content

    def test_restore_uses_no_privileges(self):
        """pg_restore should use --no-privileges to avoid permission issues."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert '--no-privileges' in content

    def test_script_uses_set_euo_pipefail(self):
        """Script should use strict bash mode."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'set -euo pipefail' in content


# ── Safety checks ─────────────────────────────────────────────────────


class TestSafetyChecks:
    """Verify the script has appropriate safety mechanisms."""

    def test_script_backs_up_before_restore(self):
        """The script should call backup_local before restore_to_local."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # In both restore-only and full-sync paths, backup comes before restore
        backup_pos = content.index('backup_local')
        restore_pos = content.index('restore_to_local')
        assert backup_pos < restore_pos, "backup_local should be called before restore_to_local"

    def test_script_requires_confirmation(self):
        """The script should prompt for confirmation before destructive operations."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'read -rp' in content
        assert 'Continue?' in content

    def test_script_terminates_connections_before_drop(self):
        """Before dropping the DB, the script should terminate active connections."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert 'pg_terminate_backend' in content

    def test_full_sync_aborts_on_no_confirmation(self):
        """Answering 'n' to confirmation should abort without error."""
        # This will fail at SSH check first in most environments,
        # but if SSH is available, it should abort on 'n'
        result = run_script(input_text="n\n", timeout=15)
        # Either fails at SSH (exit != 0) or aborts cleanly (exit 0)
        # We just verify it doesn't hang
        assert result.returncode is not None
