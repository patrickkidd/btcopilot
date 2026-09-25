"""The live venue never falls back to the production key (Patrick, 2026-09-25)."""

import pytest

from btcopilot.tests.live.conftest import require_testing_key


def test_the_live_venue_refuses_to_run_without_a_testing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_TESTING_KEY", raising=False)
    with pytest.raises(AssertionError, match="ANTHROPIC_TESTING_KEY"):
        require_testing_key()
