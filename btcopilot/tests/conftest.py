"""The schema and root suites. The chat app's suite lives in chat/ and imports
what it wants by name (R-0332)."""

import pytest

from btcopilot.tests.fixtures import (
    STUBS,
    add_e2e_option,
    add_markers,
    stubbed,
    anonymous,  # noqa: F401
    db_session,  # noqa: F401
    e2e,  # noqa: F401
    fast_passwords,  # noqa: F401
    flask_app,  # noqa: F401
    test_license,  # noqa: F401
    test_policy,  # noqa: F401
    test_user,  # noqa: F401
    test_user_2,  # noqa: F401
    unmocks,  # noqa: F401
    web_client,  # noqa: F401
)


def pytest_addoption(parser):
    add_e2e_option(parser)


def pytest_configure(config):
    add_markers(config)


@pytest.fixture(scope="session", autouse=True)
def extensions():
    with stubbed(STUBS) as originals:
        yield originals
