import pytest
import requests
import time
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import Page, Browser, BrowserContext, Route
from flask.testing import FlaskClient
from btcopilot.extensions import db
from btcopilot.pro.models import User
from btcopilot.personal.models import Discussion, Statement, Speaker, SpeakerType
import btcopilot

from btcopilot.tests.conftest import flask_app


def pytest_configure(config):
    config.addinivalue_line("markers", "audit_ui: Tests for the audit user interface")
    config.addinivalue_line(
        "markers", "feedback_system: Tests for the feedback submission system"
    )
    config.addinivalue_line(
        "markers", "data_display: Tests for data display and formatting"
    )
    config.addinivalue_line("markers", "navigation: Tests for navigation functionality")
    config.addinivalue_line("markers", "performance: Tests for performance aspects")
    config.addinivalue_line(
        "markers", "accessibility: Tests for accessibility features"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "fast: marks tests as fast")

    config.option.browser = ["chromium"]
    config.option.headed = False
    config.option.video = "retain-on-failure"
    config.option.screenshot = "only-on-failure"
    config.option.tracing = "retain-on-failure"


def is_server_running(host="127.0.0.1", port=80):
    try:
        requests.get(f"http://{host}:{port}", timeout=1)
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


def _flask_route_handler(route: Route, test_client: FlaskClient):
    request = route.request
    parsed_url = urlparse(request.url)
    path = parsed_url.path
    query_string = parsed_url.query
    post_data = request.post_data_buffer if request.post_data_buffer else None

    headers = {}
    for name, value in request.headers.items():
        if name.lower() not in ["host", "content-length", "connection"]:
            headers[name] = value

    try:
        response = test_client.open(
            path,
            method=request.method,
            data=post_data,
            query_string=query_string,
            headers=headers,
            follow_redirects=False,
        )

        response_headers = {}
        for key, value in response.headers:
            response_headers[key] = value

        route.fulfill(
            status=response.status_code,
            headers=response_headers,
            body=response.get_data(),
        )

    except Exception as e:
        route.fulfill(status=500, body=f"Flask test client error: {str(e)}")


@pytest.fixture(scope="function")
def playwright_flask_context(browser: Browser, flask_app) -> BrowserContext:
    context = browser.new_context()
    test_client = flask_app.test_client()

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    return context


@pytest.fixture(scope="function")
def playwright_flask_page(playwright_flask_context: BrowserContext) -> Page:
    page = playwright_flask_context.new_page()
    page.goto("http://testserver/")
    return page


@pytest.fixture(scope="function")
def authenticated_auditor_context(browser: Browser, flask_app) -> BrowserContext:
    auditor_user = User(
        username="test_auditor@example.com",
        password="testpass",
        first_name="Test",
        last_name="Auditor",
        status="confirmed",
    )
    auditor_user._plaintext_password = "testpass"
    auditor_user.set_role(btcopilot.ROLE_AUDITOR)

    db.session.add(auditor_user)
    db.session.commit()

    discussion = Discussion(user=auditor_user)
    db.session.add(discussion)

    subject_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Subject, name="Test User"
    )
    expert_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Expert, name="AI Assistant"
    )
    db.session.add(subject_speaker)
    db.session.add(expert_speaker)

    stmt1 = Statement(
        discussion=discussion,
        speaker=subject_speaker,
        text="Hello, I need help with my family diagram",
        order=1,
        pdp_deltas={"people": [{"name": "AI Person"}], "events": []},
    )
    stmt2 = Statement(
        discussion=discussion,
        speaker=expert_speaker,
        text="I'd be happy to help you with your family diagram. What specific information would you like to include?",
        order=2,
    )
    db.session.add(stmt1)
    db.session.add(stmt2)
    db.session.commit()

    context = browser.new_context()
    context.discussion_id = discussion.id
    context.auditor_user = auditor_user
    context.username = auditor_user.username
    context.user_id = auditor_user.id

    flask_app.test_client_class = FlaskClient
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = auditor_user.id

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    return context


@pytest.fixture(scope="function")
def audit_page(authenticated_auditor_context: BrowserContext) -> Page:
    page = authenticated_auditor_context.new_page()
    page.goto("http://testserver/training/audit/")
    return page


@pytest.fixture(scope="function")
def discussion_audit_page(authenticated_auditor_context: BrowserContext) -> Page:
    page = authenticated_auditor_context.new_page()
    discussion_id = authenticated_auditor_context.discussion_id
    page.goto(f"http://testserver/training/discussions/{discussion_id}")
    return page


@pytest.fixture(scope="function")
def logged_in_page(browser: Browser, flask_app) -> Page:
    with flask_app.app_context():
        user = User.query.filter_by(username="test@example.com").first()
        if not user:
            user = User(
                username="test@example.com",
                password="testpass",
                first_name="Test",
                last_name="User",
                status="confirmed",
            )
            user._plaintext_password = "testpass"
            user.set_role(btcopilot.ROLE_SUBSCRIBER)
            db.session.add(user)
            db.session.commit()

    context = browser.new_context()
    test_client = flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = user.id

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    page = context.new_page()
    page.goto("http://testserver/")

    return page


@pytest.fixture(scope="function")
def therapist_flask_app(flask_app):
    return flask_app


@pytest.fixture(scope="function")
def therapist_test_data(therapist_flask_app):
    auditor_user = User(
        username="session_auditor@example.com",
        password="testpass",
        first_name="Session",
        last_name="Auditor",
        status="confirmed",
    )
    auditor_user._plaintext_password = "testpass"
    auditor_user.set_role(btcopilot.ROLE_AUDITOR)

    db.session.add(auditor_user)
    db.session.commit()

    discussion = Discussion(user=auditor_user)
    db.session.add(discussion)

    subject_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Subject, name="Test User"
    )
    expert_speaker = Speaker(
        discussion=discussion, type=SpeakerType.Expert, name="AI Assistant"
    )
    db.session.add(subject_speaker)
    db.session.add(expert_speaker)

    stmt1 = Statement(
        discussion=discussion,
        speaker=subject_speaker,
        text="Hello, I need help with my family diagram",
        order=1,
        pdp_deltas={"people": [{"name": "AI Person"}], "events": []},
    )
    stmt2 = Statement(
        discussion=discussion,
        speaker=expert_speaker,
        text="I'd be happy to help you with your family diagram. What specific information would you like to include?",
        order=2,
    )
    db.session.add(stmt1)
    db.session.add(stmt2)
    db.session.commit()

    return {
        "user_id": auditor_user.id,
        "username": auditor_user.username,
        "discussion_id": discussion.id,
        "auditor_user": auditor_user,
        "discussion": discussion,
    }


@pytest.fixture(scope="function")
def db_transaction():
    connection = db.engine.connect()
    transaction = connection.begin()
    old_bind = db.session.get_bind()
    db.session.configure(bind=connection)

    yield

    transaction.rollback()
    db.session.configure(bind=old_bind)
    connection.close()


@pytest.fixture(scope="function")
def class_auditor_context(
    browser: Browser, therapist_flask_app, therapist_test_data
) -> BrowserContext:
    context = browser.new_context()

    context.discussion_id = therapist_test_data["discussion_id"]
    context.user_id = therapist_test_data["user_id"]
    context.username = therapist_test_data["username"]

    therapist_flask_app.test_client_class = FlaskClient
    test_client = therapist_flask_app.test_client()
    with test_client.session_transaction() as sess:
        sess["user_id"] = therapist_test_data["user_id"]

    def route_handler(route: Route):
        _flask_route_handler(route, test_client)

    context.route("**/*", route_handler)
    context.test_client = test_client

    return context


@pytest.fixture(scope="function")
def class_discussion_page(class_auditor_context: BrowserContext) -> Page:
    page = class_auditor_context.new_page()
    discussion_id = class_auditor_context.discussion_id
    page.goto(f"http://testserver/training/discussions/{discussion_id}")
    return page


@pytest.fixture(scope="function")
def class_audit_page(class_auditor_context: BrowserContext) -> Page:
    page = class_auditor_context.new_page()
    page.goto("http://testserver/training/audit/")
    return page


@pytest.fixture(autouse=True, scope="function")
def track_test_performance(request):
    start = time.time()
    yield
    duration = time.time() - start

    if duration > 3.0:
        print(f"\n⚠️ SLOW: {request.node.name}: {duration:.2f}s")
    elif duration > 1.0:
        print(f"\n⏱️  {request.node.name}: {duration:.2f}s")


@pytest.fixture(scope="session")
def optimized_browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "bypass_csp": True,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "reduced_motion": "reduce",
    }


browser_context_args = optimized_browser_context_args
