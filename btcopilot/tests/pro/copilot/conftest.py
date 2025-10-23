import contextlib

import pytest
import mock
from langchain_core.documents import Document

from btcopilot.pro.copilot import Engine


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
