import contextlib

import pytest
from mock import Mock, patch
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

        with (
            patch.object(
                Engine,
                "get_vector_db",
                return_value=Mock(
                    similarity_search_with_score=Mock(
                        return_value=[(x, 1.0) for x in sources]
                    )
                ),
            ),
            patch.object(Engine, "get_llm") as llm,
            patch.object(Engine, "_chat_template") as _chat_template,
        ):
            llm.return_value.invoke.return_value = response
            yield

    return _llm_response
