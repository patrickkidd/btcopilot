"""The chat app's suite: the personal app, the review, the admin commands, the
prompt files and the privacy check.

R-0332: this suite stands on its own. Everything it uses is imported by name
from btcopilot.tests.fixtures, and it names its own stubs rather than
taking Pro's by directory: Stripe is never started here at all.
"""

import pytest

from btcopilot.chattables import TABLES
from btcopilot.tests.fixtures import (
    make_app,
    CHAT_STUBS,
    add_e2e_option,
    add_markers,
    stubbed,
    admin,  # noqa: F401
    anonymous,  # noqa: F401
    db_session,  # noqa: F401
    e2e,  # noqa: F401
    fast_passwords,  # noqa: F401
    flask_app,  # noqa: F401
    pro_client,  # noqa: F401
    subscriber,  # noqa: F401
    test_license,  # noqa: F401
    test_policy,  # noqa: F401
    test_user,  # noqa: F401
    test_user_2,  # noqa: F401
    unmocks,  # noqa: F401
)


def pytest_addoption(parser):
    add_e2e_option(parser)


def pytest_configure(config):
    add_markers(config)


@pytest.fixture(scope="session", autouse=True)
def extensions():
    with stubbed(CHAT_STUBS) as originals:
        yield originals


@pytest.fixture
def flask_app(request, tmp_path):
    """The chat app's tests run on the chat app's own tables and nothing else
    (R-0322, R-0327): a path that reaches a Pro or Training table the chat
    database does not hold fails here, not on the beta server."""
    yield from make_app(request, tmp_path, tables=TABLES)
