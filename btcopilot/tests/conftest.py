import sys
import logging
import contextlib

import pytest
import mock
from langchain.docstore.document import Document

from btcopilot import Engine, Response

IS_DEBUGGER = bool(sys.gettrace() is not None)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Tun integration tests",
    )
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests (requires external dependencies)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test.")


def pytest_collection_modifyitems(session, config, items):
    # Skip mark "integration" by default, run only "integration" marks when "--integration" is passed
    if not IS_DEBUGGER:
        if not config.getoption("--integration"):
            skip_mark = pytest.mark.skip(reason="Requires passing --integration to run")
            for item in items:
                if "integration" in [x.name for x in item.own_markers]:
                    item.add_marker(skip_mark)
        else:
            skip_mark = pytest.mark.skip(
                reason="Skipped because --integration was passed"
            )
            for item in items:
                if "integration" not in [x.name for x in item.own_markers]:
                    item.add_marker(skip_mark)
    
    # Skip e2e tests by default, only run when --e2e is passed
    if not config.getoption("--e2e"):
        skip_e2e = pytest.mark.skip(reason="Requires passing --e2e to run")
        for item in items:
            if "e2e" in [x.name for x in item.own_markers]:
                item.add_marker(skip_e2e)


@pytest.fixture(autouse=True, scope="session")
def _logging():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


@pytest.fixture
def llm_response():
    """
    Zero latency mock.
    """

    @contextlib.contextmanager
    def _llm_response(response: str, sources: list[Document] = None):

        if sources is None:
            sources = []

        with mock.patch.object(
            Engine,
            "vector_db",
            return_value=mock.Mock(
                similarity_search_with_score=mock.Mock(
                    return_value=[(x, 1.0) for x in sources]
                )
            ),
        ):
            with mock.patch.object(Engine, "llm") as llm:
                llm.return_value.invoke.return_value = response
                yield

    return _llm_response
