import pytest
from mock import patch

from btcopilot.extensions import db
from btcopilot.personal.models import Discussion, DiscussionStatus, Statement, Speaker, SpeakerType
from btcopilot.training.routes.discussions import extract_next_statement
from btcopilot.schema import (
    DiagramData,
    PDPDeltas,
    Event,
    Person,
    VariableShift,
    RelationshipKind,
    EventKind,
)


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement(mock_pdp_update, mock_celery, flask_app, discussion):

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
                kind=EventKind.Shift,
                person=1,
                description="Work anxiety and family conflict",
                anxiety=VariableShift.Down,
                relationship=RelationshipKind.Conflict,
                relationshipTargets=[2],
            )
        ],
        people=[Person(id=1, name="User"), Person(id=2, name="Mom")],
    )

    mock_pdp_update.return_value = (DiagramData().pdp, mock_pdp_deltas)

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
    assert len(call_args) == 4
    discussion, database, text, up_to_order = call_args
    assert isinstance(discussion, Discussion)
    assert isinstance(database, DiagramData)
    assert text == "I'm feeling anxious about work lately"
    assert up_to_order == 0  # First statement has order=0

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
def test_extract_next_statement_error_propagates(mock_pdp_update, flask_app, discussion):

    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None

    discussion.extracting = True
    db.session.commit()
    mock_pdp_update.side_effect = Exception("LLM API error")

    with flask_app.app_context():
        with pytest.raises(Exception, match="LLM API error"):
            extract_next_statement()


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extract_next_statement_idempotent(mock_pdp_update, flask_app, discussion):

    # Setup: Clear pdp_deltas to make Subject statements unprocessed and enable extracting
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None

    # Enable extraction for this discussion
    discussion.extracting = True
    db.session.commit()

    mock_pdp_update.return_value = (DiagramData().pdp, PDPDeltas(events=[], people=[]))

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

    async def mock_async_update(discussion, database, text, up_to_order):
        processed_texts.append(text)
        return (DiagramData().pdp, PDPDeltas(events=[], people=[]))

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


@patch("btcopilot.training.routes.discussions.pdp.update")
def test_extraction_sets_ready_status(mock_pdp_update, flask_app, discussion):
    for statement in discussion.statements:
        if statement.speaker.type == SpeakerType.Subject:
            statement.pdp_deltas = None
    discussion.extracting = True
    discussion.status = DiscussionStatus.Extracting
    db.session.commit()

    mock_pdp_update.return_value = (DiagramData().pdp, PDPDeltas(events=[], people=[]))

    with flask_app.app_context():
        result = extract_next_statement()
    assert result is True

    db.session.refresh(discussion)
    assert discussion.extracting is False
    assert discussion.status == DiscussionStatus.Ready
