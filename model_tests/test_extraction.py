"""
Data extraction model test suite

This test suite runs all exported test cases against the current extraction model
to detect regressions and measure accuracy across different categories.
"""

import asyncio
from pathlib import Path

import pytest

from btcopilot.personal import pdp
from btcopilot.personal.database import Database, PDPDeltas
from .conftest import make_discussion, assert_deltas_equal


def generate_test_id(case: dict) -> str:
    return case["file_path"].replace("/", "_").replace(".json", "")


def test_no_duplicate_test_case_ids(test_cases):
    test_ids = [case.get("test_id", "unknown") for case in test_cases]
    duplicates = [tid for tid in set(test_ids) if test_ids.count(tid) > 1]
    assert len(duplicates) == 0, f"Duplicate test case IDs found: {duplicates}"


def test_that_cases_have_required_fields(test_cases):

    REQUIRED_FIELDS = ["test_id", "source", "inputs", "expected_output"]
    REQUIRED_INPUTS = ["conversation_history", "database", "user_statement"]

    for case in test_cases:
        for field in REQUIRED_FIELDS:
            assert (
                field in case
            ), f"Test case {case.get('test_id', 'unknown')} missing field: {field}"

        inputs = case.get("inputs", {})
        for field in REQUIRED_INPUTS:
            assert (
                field in inputs
            ), f"Test case {case.get('test_id', 'unknown')} missing input field: {field}"

        conv_history = inputs.get("conversation_history", [])
        for i, msg in enumerate(conv_history):
            assert (
                "speaker" in msg
            ), f"Test case {case.get('test_id', 'unknown')} conversation[{i}] missing speaker"
            assert (
                "text" in msg
            ), f"Test case {case.get('test_id', 'unknown')} conversation[{i}] missing text"
            assert msg["speaker"] in [
                "Subject",
                "Expert",
            ], f"Test case {case.get('test_id', 'unknown')} conversation[{i}] invalid speaker: {msg['speaker']}"


@pytest.mark.asyncio
async def test_extraction_accuracy(test_cases):
    """
    Test each extraction case against expected output

    This test:
    1. Reconstructs the extraction context from each test case
    2. Calls the current extraction model
    3. Compares the result to the expected output
    4. Provides detailed failure information for debugging
    """

    # Track results for summary
    total_cases = len(test_cases)
    passed_cases = 0
    failed_cases = []

    for case in test_cases:
        try:
            # Reconstruct inputs from test case
            inputs = case["inputs"]
            expected_output = case["expected_output"]

            # Build database context
            database = Database(**inputs["database"])

            # Build discussion context
            discussion = make_discussion(inputs["conversation_history"])

            # Get the user statement to analyze
            user_statement = inputs["user_statement"]

            # Call the extraction model
            try:
                _, result_deltas = await pdp.update(
                    thread=discussion, database=database, user_message=user_statement
                )
            except Exception as e:
                failed_cases.append(f"{case['test_id']}: Extraction failed - {e}")
                continue

            # Convert expected output to PDPDeltas for comparison
            try:
                expected_deltas = PDPDeltas(**expected_output)
            except Exception as e:
                failed_cases.append(
                    f"{case['test_id']}: Invalid expected output format - {e}"
                )
                continue

            # Compare results
            try:
                assert_deltas_equal(result_deltas, expected_deltas, case["test_id"])
                passed_cases += 1
            except Exception as e:
                failed_cases.append(f"{case['test_id']}: {str(e)}")

        except Exception as e:
            failed_cases.append(
                f"{case.get('test_id', 'unknown')}: Unexpected error - {e}"
            )

    # Report summary
    if failed_cases:
        failure_summary = (
            f"\n\nTest Summary: {passed_cases}/{total_cases} passed\n\nFailures:\n"
            + "\n".join(failed_cases)
        )
        pytest.fail(failure_summary)

    print(f"\nAll {total_cases} test cases passed successfully!")
