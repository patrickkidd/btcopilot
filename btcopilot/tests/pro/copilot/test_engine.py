import pytest
import mock

from btcopilot.pro.copilot import Engine, Event
from btcopilot.pro.copilot.engine import format_timeline_data


ANSWER = "There is no point"


@pytest.fixture
def engine(tmp_path):
    from langchain_core.documents import Document

    with mock.patch.object(
        Engine,
        "get_vector_db",
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
        with mock.patch.object(Engine, "get_llm") as llm:
            llm.return_value.invoke.return_value = ANSWER
            yield Engine(tmp_path)


def test_ask(engine):
    response = engine.ask("What is the point?")
    assert response.answer == ANSWER
    engine.get_vector_db().similarity_search_with_score.assert_called_once()
    engine.get_llm().invoke.assert_called_once()


def test_ask_with_events(engine):
    events = [
        Event(
            dateTime="2021-01-01",
            description="Bonded",
            people=["Alice", "Bob"],
            variables={"anxiety": "down"},
        ),
        Event(
            dateTime="2022-01-01",
            description="First argument",
            people=["Alice", "Bob"],
            variables={"anxiety": "up"},
        ),
    ]
    response = engine.ask("Where is the shift?", events=events)
    s_timeseries = format_timeline_data(events)
    assert response.answer == ANSWER
    engine.get_vector_db().similarity_search_with_score.assert_called_once()
    assert s_timeseries in engine.get_llm().invoke.call_args[0][0]
