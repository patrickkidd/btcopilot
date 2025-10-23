"""
Test fixtures and configuration for data extraction model tests
"""

import pytest
import json
from pathlib import Path
from typing import Any

from btcopilot.schema import PDPDeltas
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType


@pytest.fixture
def test_cases() -> list[dict[str, Any]]:
    data_dir = Path("./model_tests/data")
    cases = []

    for json_file in data_dir.rglob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                case = json.load(f)
                # Add metadata about file location for categorization
                case["file_path"] = str(json_file.relative_to(data_dir))
                case["category"] = json_file.parent.name
                cases.append(case)
        except Exception as e:
            pytest.fail(f"Failed to load test case {json_file}: {e}")

    return cases


def make_discussion(conversation_history: list[dict[str, str]]) -> Discussion:
    """
    conversation_history: List of {"speaker": "Subject/Expert", "text": "..."}
    """
    discussion = Discussion()
    discussion.id = 1
    discussion.statements = []

    subject_speaker = Speaker(id=1, type=SpeakerType.Subject, name="User")
    expert_speaker = Speaker(id=2, type=SpeakerType.Expert, name="Assistant")

    for i, msg in enumerate(conversation_history):
        statement = Statement()
        statement.id = i + 1
        statement.text = msg["text"]
        statement.order = i

        if msg["speaker"] == "Subject":
            statement.speaker = subject_speaker
            statement.speaker_id = 1
        else:
            statement.speaker = expert_speaker
            statement.speaker_id = 2

        discussion.statements.append(statement)

    return discussion


def assert_deltas_equal(actual: PDPDeltas, expected: PDPDeltas, test_id: str):
    """
    Compare two PDPDeltas objects for equality with detailed error reporting

    Args:
        actual: The result from the extraction
        expected: The expected result from test case
        test_id: Test case identifier for error messages
    """
    # Convert to dicts for easier comparison
    actual_dict = actual.model_dump() if hasattr(actual, "model_dump") else actual
    expected_dict = (
        expected.model_dump() if hasattr(expected, "model_dump") else expected
    )

    # Compare people
    actual_people = actual_dict.get("people", [])
    expected_people = expected_dict.get("people", [])

    if len(actual_people) != len(expected_people):
        pytest.fail(
            f"Test {test_id}: People count mismatch. "
            f"Expected {len(expected_people)}, got {len(actual_people)}"
        )

    # Compare events
    actual_events = actual_dict.get("events", [])
    expected_events = expected_dict.get("events", [])

    if len(actual_events) != len(expected_events):
        pytest.fail(
            f"Test {test_id}: Events count mismatch. "
            f"Expected {len(expected_events)}, got {len(actual_events)}"
        )

    # Compare deletions
    actual_deletes = actual_dict.get("delete", [])
    expected_deletes = expected_dict.get("delete", [])

    if actual_deletes != expected_deletes:
        pytest.fail(
            f"Test {test_id}: Deletions mismatch. "
            f"Expected {expected_deletes}, got {actual_deletes}"
        )

    # Detailed comparison of people
    for i, (actual_person, expected_person) in enumerate(
        zip(actual_people, expected_people)
    ):
        for key in expected_person.keys():
            if actual_person.get(key) != expected_person.get(key):
                pytest.fail(
                    f"Test {test_id}: Person {i} field '{key}' mismatch. "
                    f"Expected {expected_person.get(key)}, got {actual_person.get(key)}"
                )

    # Detailed comparison of events
    for i, (actual_event, expected_event) in enumerate(
        zip(actual_events, expected_events)
    ):
        for key in expected_event.keys():
            if key == "relationship" and expected_event.get(key):
                # Special handling for relationship comparison
                actual_rel = actual_event.get("relationship", {})
                expected_rel = expected_event.get("relationship", {})

                for rel_key in expected_rel.keys():
                    if actual_rel.get(rel_key) != expected_rel.get(rel_key):
                        pytest.fail(
                            f"Test {test_id}: Event {i} relationship '{rel_key}' mismatch. "
                            f"Expected {expected_rel.get(rel_key)}, got {actual_rel.get(rel_key)}"
                        )
            else:
                if actual_event.get(key) != expected_event.get(key):
                    pytest.fail(
                        f"Test {test_id}: Event {i} field '{key}' mismatch. "
                        f"Expected {expected_event.get(key)}, got {actual_event.get(key)}"
                    )


@pytest.fixture(params=[])
def parametrized_test_case(request):
    """Parametrized fixture for individual test cases"""
    return request.param
