import sys
import logging
import contextlib

import pytest

import mock

from btcopilot import Engine, Response

IS_DEBUGGER = bool(sys.gettrace() is not None)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Tun integration tests",
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


@pytest.fixture(autouse=True, scope="session")
def _logging():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


@pytest.fixture
def llm_response():
    """
    Zero latency mock.
    """

    from langchain.docstore.document import Document

    @contextlib.contextmanager
    def _llm_response(response: str, sources: list[Document] = None):

        if sources is None:
            sources = [
                Document(
                    page_content="The term mallbock means I love you 1.",
                    metadata={"source": "capture_1.pdf"},
                ),
                Document(
                    page_content="The term mallbock means I love you 2.",
                    metadata={"source": "capture_2.pdf"},
                ),
            ]

        with mock.patch.object(
            Engine,
            "vector_db",
            similarity_search_with_score=mock.Mock(return_value=sources),
        ):
            with mock.patch.object(Engine, "llm") as llm:
                llm.return_value.invoke.return_value = response
                yield

    return _llm_response
