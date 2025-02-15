"""
Validity tests for the model and source material.
"""

import sys
import os.path
import logging

import pytest

from btcopilot import Engine
from btcopilot.tests.data import quizzes

_log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def engine():
    DATA_DIR = os.path.realpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "instance", "vector_db")
    )
    if not os.path.exists(DATA_DIR):
        pytest.fail(
            "No vector db found. Create it with `flask ingest` in the root folder of the repo."
        )
    _engine = Engine(data_dir=DATA_DIR)
    _log.debug(f"Initializing vector db from {DATA_DIR}..")
    _engine.vector_db()
    _log.debug(f"Initializing llm..")
    _engine.llm()
    _log.debug(f"Engine initialized.")
    yield _engine


EVAL_PROMPT = """
Expected Response: {expected_response}
Actual Response: {actual_response}
---
(Answer with 'true' or 'false') Does the actual response match the expected response? 
"""


@pytest.mark.integration
@pytest.mark.parametrize("question, correct_answer", quizzes.FTICP_QUIZ)
def test_bowens_book(engine, question, correct_answer):

    response = engine.ask(question)
    check_prompt = EVAL_PROMPT.format(
        expected_response=correct_answer, actual_response=response.answer
    )

    status = engine.llm().invoke(check_prompt).strip().lower()
    result = f"\n\n**** QUESTION:{question}\n\n**** EXPECTED ANSWER:{correct_answer}\n\n**** RECEIVED ANSWER: {response.answer}\n\n"
    _log.info(result)
    _log.debug(f"Copilot vector db time: {response.vectors_time}")
    _log.debug(f"Copilot llm time: {response.llm_time}")
    _log.debug(f"Copilot total time: {response.total_time}")
    assert "true" == status, result
