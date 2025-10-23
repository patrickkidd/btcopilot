import pytest
from unittest.mock import patch, AsyncMock
from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
from btcopilot.training.routes.discussions import extract_next_statement
from btcopilot.schema import (
    Diagram,
    PDPDeltas,
    Event,
    Person,
    Anxiety,
    Shift,
    Conflict,
    RelationshipKind,
)


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement(mock_pdp_update, mock_celery, flask_app, discussion):
    """Test that background processing works for one unprocessed Subject statement at a time"""

    # Setup: Clear pdp_deltas to make Subject statements unprocessed and enable extracting
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None

    # Enable extraction for this discussion
    discussion.extracting = True

    # Update text for better test readability
    subject_statement = next(
        s for s in discussion.statements if s.speaker.type == SpeakerType.Subject
    )
    subject_statement.text = "I'm feeling anxious about work lately"

    # Add additional unprocessed Subject statement
    subject_speaker = next(
        s for s in discussion.speakers if s.type == SpeakerType.Subject
    )
    new_statement = Statement(
        discussion_id=discussion.id,
        speaker_id=subject_speaker.id,
        text="I had a fight with my mom yesterday",
        order=2,  # After existing statements
    )
    db.session.add(new_statement)
    db.session.commit()

    # Mock the pdp.update function to avoid LLM API calls
    mock_pdp_deltas = PDPDeltas(
        events=[
            Event(
                id=1,
                description="Work anxiety and family conflict",
                anxiety=Anxiety(shift=Shift.Down),
                relationship=Conflict(
                    kind=RelationshipKind.Conflict,
                    shift=Shift.Up,
                    movers=[1],
                    recipients=[2],
                ),
            )
        ],
        people=[Person(id=1, name="User"), Person(id=2, name="Mom")],
    )

    mock_pdp_update.return_value = (Diagram().pdp, mock_pdp_deltas)

    # Get initial count of Subject statements (all should be unprocessed in this test)
    subject_statements = (
        Statement.query.join(Speaker)
        .filter(
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
        )
        .order_by(Statement.discussion_id.asc(), Statement.id.asc())
        .all()
    )

    # Should have 2 Subject statements with text
    assert len(subject_statements) == 2

    # Verify they have no pdp_deltas (using direct attribute access to avoid SQLAlchemy JSON issues)
    unprocessed_count = sum(1 for stmt in subject_statements if stmt.pdp_deltas is None)
    assert unprocessed_count == 2

    # Run the background processing once - should process only the first statement
    with flask_app.app_context():
        result = extract_next_statement()
    assert result is True
    assert mock_pdp_update.call_count == 1

    # Verify the function was called with correct arguments for the first statement
    call_args = mock_pdp_update.call_args[0]
    assert len(call_args) == 3
    discussion, database, text = call_args
    assert isinstance(discussion, Discussion)
    assert isinstance(database, Diagram)
    assert text == "I'm feeling anxious about work lately"

    db.session.refresh(subject_statements[0])
    db.session.refresh(subject_statements[1])
    assert subject_statements[0].pdp_deltas is not None
    assert subject_statements[1].pdp_deltas is None

    # Run the background processing again - should process the second statement
    with flask_app.app_context():
        result = extract_next_statement()
    assert result is True
    assert mock_pdp_update.call_count == 2

    # Refresh the session again
    db.session.refresh(subject_statements[1])
    assert subject_statements[1].pdp_deltas is not None

    with flask_app.app_context():
        result = extract_next_statement()
    assert result is False
    assert mock_pdp_update.call_count == 2  # not called again


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement_error_handling(mock_pdp_update, flask_app, discussion):
    """Test that errors in processing individual statements return False and don't crash"""

    # Setup: Clear pdp_deltas to make Subject statements unprocessed and enable extracting
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None

    # Enable extraction for this discussion
    discussion.extracting = True
    db.session.commit()
    mock_pdp_update.side_effect = Exception("LLM API error")

    # Get initial count using direct attribute access
    subject_statements_before = (
        Statement.query.join(Speaker)
        .filter(
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
        )
        .all()
    )
    unprocessed_before = sum(
        1 for stmt in subject_statements_before if stmt.pdp_deltas is None
    )
    assert unprocessed_before == 1

    with flask_app.app_context():
        result = extract_next_statement()
    assert result is False
    assert mock_pdp_update.call_count == 1

    # Refresh the session to get updated data
    for stmt in subject_statements_before:
        db.session.refresh(stmt)

    # All statements should still be unprocessed due to error
    subject_statements_after = (
        Statement.query.join(Speaker)
        .filter(
            Speaker.type == SpeakerType.Subject,
            Statement.text.isnot(None),
            Statement.text != "",
        )
        .all()
    )

    unprocessed_after = sum(
        1 for stmt in subject_statements_after if stmt.pdp_deltas is None
    )
    assert unprocessed_after == 1  # Still unprocessed due to error


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement_idempotent(mock_pdp_update, flask_app, discussion):
    """Test that once a statement is processed, it won't be processed again"""

    # Setup: Clear pdp_deltas to make Subject statements unprocessed and enable extracting
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None

    # Enable extraction for this discussion
    discussion.extracting = True
    db.session.commit()

    mock_pdp_update.return_value = (Diagram().pdp, PDPDeltas(events=[], people=[]))

    # Run the background processing multiple times
    with flask_app.app_context():
        result1 = extract_next_statement()  # Should process first statement
        result2 = extract_next_statement()  # Should find nothing
        result3 = extract_next_statement()  # Should still find nothing

    # First call should succeed, rest should return False since we only have one Subject statement
    assert result1 is True
    assert result2 is False
    assert result3 is False

    # Should only be called once (only one Subject statement in base discussion fixture)
    assert mock_pdp_update.call_count == 1


def test_extract_next_statement_no_statements(flask_app, test_user):
    """Test that the job handles cases with no statements gracefully"""

    # Create a discussion with no statements
    discussion = Discussion(user_id=test_user.id, summary="Empty discussion")
    db.session.add(discussion)
    db.session.commit()

    with patch("btcopilot.training.routes.discussions.pdp.update") as mock_pdp_update:
        # Run the background processing
        with flask_app.app_context():
            result = extract_next_statement()
    assert result is False
    assert mock_pdp_update.call_count == 0


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement_ordering(mock_pdp_update, flask_app, test_user):
    """Test that statements are processed in correct order (by discussion_id then statement_id)"""

    # Create two discussions with statements in reverse creation order
    discussion2 = Discussion(
        user_id=test_user.id, summary="Second discussion", extracting=True
    )
    db.session.add(discussion2)
    db.session.flush()

    discussion1 = Discussion(
        user_id=test_user.id, summary="First discussion", extracting=True
    )
    db.session.add(discussion1)
    db.session.flush()

    # Create Subject speakers for both discussions
    subject1 = Speaker(
        discussion_id=discussion1.id, name="Subject 1", type=SpeakerType.Subject
    )
    subject2 = Speaker(
        discussion_id=discussion2.id, name="Subject 2", type=SpeakerType.Subject
    )
    db.session.add_all([subject1, subject2])
    db.session.flush()

    # Create statements in reverse order to test ordering
    statement2 = Statement(
        discussion_id=discussion2.id,
        speaker_id=subject2.id,
        text="Second discussion text",
        order=0,
    )
    statement1 = Statement(
        discussion_id=discussion1.id,
        speaker_id=subject1.id,
        text="First discussion text",
        order=0,
    )
    db.session.add_all([statement2, statement1])
    db.session.commit()

    processed_texts = []

    async def mock_async_update(discussion, database, text):
        processed_texts.append(text)
        return (Diagram().pdp, PDPDeltas(events=[], people=[]))

    mock_pdp_update.side_effect = mock_async_update

    with flask_app.app_context():
        result1 = extract_next_statement()
        result2 = extract_next_statement()
        result3 = extract_next_statement()

    assert result1 is True
    assert result2 is True
    assert result3 is False

    # Verify statements were processed in order of (discussion_id, statement_id)
    # The statement with lower discussion_id should be processed first
    if discussion1.id < discussion2.id:
        expected_order = ["First discussion text", "Second discussion text"]
    else:
        expected_order = ["Second discussion text", "First discussion text"]

    assert processed_texts == expected_order
    assert mock_pdp_update.call_count == 2
