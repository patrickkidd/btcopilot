"""
Beginning of validation suite
"""

import pytest

from btcopilot.personal import chat
from btcopilot.personal.models import Discussion, Statement

pytest.skip("not done yet", allow_module_level=True)


@pytest.mark.e2e
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_message, direction, topic, chroma_response, ai_response, expected_data_points, expected_message",
    [
        # Scenario 1: Follow direction, continuing topic, anxiety detected
        (
            "I still feel anxious about work",
            "follow",
            "Previous Topic",
            ["Similar statement: I felt anxious last week"],
            "Can you tell me more about what's making you anxious at work?",
            [DataPoint(user_id=1)],
            "Can you tell me more about what's making you anxious at work?",
        ),
        # Scenario 2: Follow direction, new topic, triangle detected
        (
            "My relationship with my partner is strained",
            "follow",
            "Relationship Issues",
            ["Similar statement: I had a fight with my partner"],
            "That sounds tough. What's been happening between you and your partner?",
            [DataPoint(user_id=1)],
            "That sounds tough. What's been happening between you and your partner?",
        ),
        # Scenario 3: Lead direction, no data points, past statements retrieved
        (
            "I don't know what to talk about",
            "lead",
            "Previous Topic",
            ["Similar statement: I felt lost last session"],
            "Let's explore your relationships. Have you noticed any patterns in how you connect with others?",
            [],
            "Let's explore your relationships. Have you noticed any patterns in how you connect with others?",
        ),
        # Scenario 4: Lead direction, ambiguous message, no past statements
        (
            "I'm not sure what's wrong",
            "lead",
            "Previous Topic",
            [],
            "That's okay. Let's dig into how you've been feeling lately—any changes in your mood or routines?",
            [],
            "That's okay. Let's dig into how you've been feeling lately—any changes in your mood or routines?",
        ),
    ],
    ids=[
        "follow-continue-topic-anxiety",
        "follow-new-topic-triangle",
        "lead-no-data-points",
        "lead-ambiguous-no-past-statements",
    ],
)
async def test_llm_chain_integration(
    user_message,
    direction,
    topic,
    chroma_response,
    ai_response,
    expected_data_points,
    expected_message,
):
    # Setup mocks
    llm.submit.side_effect = [
        direction,
        topic,
        ai_response,
    ]  # Direction, Summarize, Response
    chroma.similarity_search_with_score.return_value = chroma_response

    # Run the ask function
    discussion_id = 1
    response = chat(discussion_id, user_message)

    # Verify intermediate steps
    discussion = Discussion.query.get(discussion_id)
    assert discussion.id == discussion_id, "Thread ID should match"

    # Verify data points detection
    user_message_obj = Statement(
        discussion_id=discussion_id,
        user_message=user_message,
        origin=StatementOrigin.User,
    )
    results = await asyncio.gather(
        Anxiety.detect(user_message), Triangle.detect(user_message)
    )
    user_message_obj.data_points = [
        x for y in results for x in y if isinstance(x, DataPoint)
    ]
    assert len(user_message_obj.data_points) == len(
        expected_data_points
    ), "Data points detection failed"

    # Verify response direction
    detected_direction = await detect_response_direction(user_message, discussion)
    assert detected_direction == ResponseDirection(
        direction
    ), "Response direction detection failed"

    # Verify topic handling
    if direction == "follow":
        assert (
            llm.submit.call_args_list[1][0][1].find(topic) != -1
        ), "Topic detection failed"

    # Verify Chroma interaction (only in Lead direction)
    if direction == "lead":
        chroma.similarity_search_with_score.assert_called_with(user_message, k=7)

    # Verify final response
    assert response.message == expected_message, "AI response generation failed"
    assert response.added_data_points == [], "Added data points should be empty"
    assert response.removed_data_points == [], "Removed data points should be empty"
    assert response.guidance == [], "Guidance should be empty"
