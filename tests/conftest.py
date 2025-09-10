import contextlib
import pytest
from mock import patch, AsyncMock
import flask.json
from flask import Flask, g
from btcopilot.training import init_web_app
from btcopilot.training.models import Base, Discussion, Statement, Speaker, SpeakerType, Feedback
from btcopilot.training.prompts import get_prompt


def pytest_addoption(parser):
    """Add custom command-line options for pytest"""
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="run end-to-end tests (requires browser setup)"
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "extraction_flow: mock extraction for testing extraction lifecycle",
    )


@pytest.fixture
def app():
    """Create and configure a test Flask app instance for btcopilot"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Create mock database session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    
    class MockDB:
        def __init__(self):
            self.session = SessionLocal()
        
        def create_all(self):
            pass
            
        def drop_all(self):
            pass
    
    # Mock stand-in user management
    class StandInUser:
        def __init__(self, username="test_user", roles=None):
            self.username = username
            self.roles = roles or ["auditor"]
            self.is_authenticated = True
            self.id = 1
    
    with app.app_context():
        # Set up mock database
        app.extensions = {'sqlalchemy': MockDB()}
        db = app.extensions['sqlalchemy']
        
        # Initialize btcopilot with stand-ins
        init_web_app(app)
        
        # Mock current_user for templates
        @app.before_request
        def mock_user():
            g.current_user = StandInUser()
            g.custom_prompts = {}  # Allow fdserver to override prompts
        
        yield app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Get database session for tests"""
    return app.extensions['sqlalchemy'].session


@pytest.fixture
def test_user():
    """Create a stand-in test user"""
    class TestUser:
        def __init__(self):
            self.id = 1
            self.username = "test_auditor"
            self.roles = ["auditor"]
            self.is_authenticated = True
            self.free_diagram_id = 1
    
    return TestUser()


@pytest.fixture
def discussions(test_user, db_session):
    """Create test discussions"""
    _discussions = [
        Discussion(user_id=test_user.id, summary=f"test thread {i}") for i in range(3)
    ]
    db_session.add_all(_discussions)
    db_session.commit()
    return _discussions


@pytest.fixture
def discussion(test_user, db_session):
    """Create a test discussion with speakers and statements"""
    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        summary="Test discussion",
    )
    db_session.add(discussion)
    db_session.commit()

    # Create speakers for the discussion
    family_speaker = Speaker(
        discussion_id=discussion.id,
        name="Family Member",
        type=SpeakerType.Subject,
        person_id=1,
    )
    expert_speaker = Speaker(
        discussion_id=discussion.id,
        name="Expert",
        type=SpeakerType.Expert,
    )
    db_session.add_all([family_speaker, expert_speaker])
    db_session.commit()

    # Create statements
    statement1 = Statement(
        discussion_id=discussion.id, speaker_id=family_speaker.id, text="Hello", order=0
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Hi there",
        pdp_deltas={"events": [{"symptom": {"shift": "better"}}]},
        order=1,
    )
    db_session.add_all([statement1, statement2])
    db_session.commit()

    return discussion


@pytest.fixture
def feedback(discussion, test_user, db_session):
    """Create test feedback for a statement"""
    statement = discussion.statements[1]  # Expert statement
    feedback = Feedback(
        statement_id=statement.id,
        auditor_id=test_user.username,
        feedback_type="extraction",
        thumbs_down=False,
        comment="Good extraction",
    )
    db_session.add(feedback)
    db_session.commit()
    return feedback


@pytest.fixture(autouse=True)
def extraction_flow(request):
    """Mock extraction for testing extraction lifecycle"""
    extraction_flow = request.node.get_closest_marker("extraction_flow")

    with contextlib.ExitStack() as stack:
        if extraction_flow is not None:
            # Get extraction results from marker kwargs or use defaults
            extractions = extraction_flow.kwargs.get("extractions", [])

            # If extractions is a list, cycle through them for multiple calls
            if not isinstance(extractions, list):
                extractions = [extractions]

            # Create an iterator that will return each extraction in sequence
            extraction_iter = iter(extractions)

            def mock_update(*args, **kwargs):
                try:
                    result = next(extraction_iter)
                    # If result is a tuple, return as-is
                    # If it's just deltas, return (None, result)
                    if isinstance(result, tuple):
                        return result
                    else:
                        return (None, result if result else {})
                except StopIteration:
                    # If we run out of extractions, return empty deltas
                    return (None, {})

            # Mock the stand-in extraction function
            stack.enter_context(
                patch(
                    "btcopilot.training.routes.admin.mock_extract_data",
                    AsyncMock(side_effect=mock_update),
                )
            )
            yield {"extractions": extractions}
        else:
            yield None


@pytest.fixture(autouse=True)
def e2e(request):
    """Skip e2e tests unless --e2e flag is provided"""
    if request.node.get_closest_marker("e2e") is not None:
        if not request.config.getoption("--e2e"):
            pytest.skip("need --e2e option to run")


def flask_json(data: dict) -> dict:
    """Helper to serialize/deserialize data like Flask does"""
    sdata = flask.json.dumps(data)
    return flask.json.loads(sdata)


# Mock authentication fixtures for web app testing
@pytest.fixture
def auditor(client, test_user):
    """Create authenticated auditor client"""
    with client.session_transaction() as sess:
        sess['user_id'] = test_user.id
        sess['username'] = test_user.username
        sess['roles'] = ['auditor']
    return client


@pytest.fixture
def admin(client):
    """Create authenticated admin client"""  
    with client.session_transaction() as sess:
        sess['user_id'] = 2
        sess['username'] = 'admin_user'
        sess['roles'] = ['admin']
    return client


@pytest.fixture
def subscriber(client):
    """Create authenticated subscriber client (limited permissions)"""
    with client.session_transaction() as sess:
        sess['user_id'] = 3
        sess['username'] = 'subscriber'
        sess['roles'] = ['subscriber']
    return client


@pytest.fixture
def anonymous(client):
    """Create anonymous (unauthenticated) client"""
    return client