import pytest
import mock

from btcopilot import Engine


ANSWER = "There is no point"


@pytest.fixture
def engine(tmp_path):
    from langchain.docstore.document import Document

    with mock.patch.object(
        Engine,
        "vector_db",
        similarity_search_with_score=mock.Mock(
            return_value=[
                Document(
                    page_content="The term mallbock means I love you 1.",
                    metadata={"source": "capture_1.pdf"},
                ),
                Document(
                    page_content="The term mallbock means I love you 2.",
                    metadata={"source": "capture_2.pdf"},
                ),
            ]
        ),
    ):
        with mock.patch.object(Engine, "llm") as llm:
            llm.return_value.invoke.return_value = ANSWER
            yield Engine(tmp_path)


def test_ask(engine):
    response = engine.ask("What is the point?")
    assert response.answer == ANSWER
    engine.vector_db().similarity_search_with_score.assert_called_once()
    engine.llm().invoke.assert_called_once()
