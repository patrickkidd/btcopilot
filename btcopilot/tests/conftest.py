"""The suite imports everything it uses by name from btcopilot.tests.fixtures
and names its own stubs (R-0332)."""

import contextlib
import datetime
import logging
import re
import socket
import flask.testing
import pytest
from mock import patch
from sqlalchemy import text
import btcopilot
from btcopilot import provider
from btcopilot.extensions import db
from btcopilot.llmutil import EXTRACTION_MODEL, Served, Spent, Text
from btcopilot.coachmodel import ModelTurn, ToolCall
from btcopilot.coachturn import SPEAK, run_call
from btcopilot.models import Diagram, Discussion, Statement, Speaker, SpeakerType
from btcopilot.promptdir import missing
from btcopilot.toolbox import ToolName
from btcopilot import casereport, turnlog, turns
from btcopilot.turnlog import TurnEventKind

from btcopilot.tables import TABLES
from btcopilot.tests.fixtures import (
    make_app,
    STUBS,
    add_e2e_option,
    add_markers,
    stubbed,
    admin,  # noqa: F401
    anonymous,  # noqa: F401
    db_session,  # noqa: F401
    e2e,  # noqa: F401
    fast_passwords,  # noqa: F401
    web_client,  # noqa: F401
    subscriber,  # noqa: F401
    test_license,  # noqa: F401
    test_policy,  # noqa: F401
    test_user,  # noqa: F401
    test_user_2,  # noqa: F401
    unmocks,  # noqa: F401
)


def pytest_terminal_summary(terminalreporter):
    if missing():
        terminalreporter.write_line(missing())


def pytest_addoption(parser):
    add_e2e_option(parser)
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run the tests that need a real Postgres (starts a container with Docker)",
    )


def pytest_configure(config):
    add_markers(config)


@pytest.fixture(scope="session", autouse=True)
def extensions():
    with stubbed(STUBS) as originals:
        yield originals


# Read machine's provider before the suite pins it for tests.
MACHINE = provider.provider()


@pytest.fixture(scope="session", autouse=True)
def anthropic_provider():
    """Pin provider to Anthropic; suite uses stand-in calls."""
    patched = pytest.MonkeyPatch()
    patched.delenv(provider.SETTING, raising=False)
    yield
    patched.undo()


@pytest.fixture
def flask_app(request, tmp_path):
    """Tests run on the app's own tables and nothing else (R-0322, R-0327): a
    path that reaches a Pro or Training table the database does not hold fails
    here, not on the beta server."""
    yield from make_app(request, tmp_path, tables=TABLES)


@pytest.fixture
def foreign_keys(flask_app):
    """SQLite enforces foreign keys only when asked; Postgres always does."""
    db.session.execute(text("PRAGMA foreign_keys=ON"))
    yield
    db.session.execute(text("PRAGMA foreign_keys=OFF"))


SERVED = "claude-opus-5-5"


def version(diagram) -> int:
    """The record's version as it stands, for a change that has to name it."""
    return db.session.query(Diagram.version).filter_by(id=diagram.id).scalar()


def said(text: str) -> ModelTurn:
    return ModelTurn(
        text=text, blocks=[{"type": "text", "text": text}], served=Served(SERVED)
    )


def wrote(words: str) -> Text:
    return Text(words, Spent(), Served(SERVED))


def called(tool: ToolName, text: str = "", **args) -> ModelTurn:
    return calling((tool, args), text=text)


def calling(*wanted: tuple[ToolName, dict], text: str = "") -> ModelTurn:
    """One model call that asks for several tools at once, optionally saying
    something first — which is how a real model leaks its planning."""
    turn = ModelTurn(text=text, served=Served(SERVED))
    if text:
        turn.blocks.append({"type": "text", "text": text})
    for index, (tool, args) in enumerate(wanted):
        call = ToolCall(id=f"tu_{tool.value}_{index}", name=tool.value, args=args)
        turn.calls.append(call)
        turn.blocks.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.args}
        )
    return turn


def run_then_stop(toolbox, call):
    answer = run_call(toolbox, call)
    turnlog.halt(toolbox.turn_id)
    return answer


def opening(messages: list[dict]) -> str:
    """The record and the day a coach turn puts in its new message, just
    before the person's words: the message after the last settled one, which
    is the only place the chat is marked before the call."""
    settled = [
        i
        for i, message in enumerate(messages)
        if isinstance(message["content"], list)
        and any("cache_control" in block for block in message["content"])
    ]
    message = messages[settled[-1] + 1 if settled else 0]
    if message["role"] != "user" or isinstance(message["content"], str):
        return ""
    words = [
        block["text"]
        for block in message["content"]
        if block["type"] == "text" and block["text"] != SPEAK
    ]
    return words[-2] if len(words) > 1 else ""


class Model:
    """A coach that says exactly what the test scripted, in order."""

    model = SERVED

    def __init__(self, *turns: ModelTurn):
        self.turns = list(turns)
        self.systems = []
        self.histories = []
        self.offered = []

    def turn(self, system, messages, tools, turn_id=""):
        self.systems.append(
            (system if isinstance(system, str) else "".join(system))
            + opening(messages)
        )
        self.histories.append(messages)
        self.offered.append([schema["name"] for schema in tools])
        scripted = self.turns.pop(0)
        if scripted.text:
            yield scripted.text
        return scripted




@pytest.fixture(autouse=True)
def turn_log():
    """Turns run where the test can read them: one log in this process, and the
    worker's task run as the POST returns rather than on a broker."""
    turnlog.use(turnlog.MemoryLog())
    with patch("btcopilot.turns.enqueue", new=turns.run), patch(
        "btcopilot.casereport.enqueue", new=casereport.run
    ):
        yield turnlog.store()
    turnlog.use(None)


def replied(response) -> dict:
    """What the coach said, from the turn the POST started."""
    turn_id = response.get_json()["turn_id"]
    done = turnlog.read_from(turn_id, 0)[-1][1]
    assert done["type"] == TurnEventKind.Done.value, done
    return done


@pytest.fixture(autouse=True)
def regrouping():
    """A turn that moves an event re-groups the line, which costs a model call.
    Tests get no regrouping unless they put the real one back."""
    with patch("btcopilot.clusters.sync", return_value=None) as sync:
        yield sync


@pytest.fixture(autouse=True)
def chat_flow(request):

    marker = request.node.get_closest_marker("chat_flow")

    with contextlib.ExitStack() as stack:
        if marker is not None:

            response = marker.kwargs.get("response", "some response")

            # The coach's turn is the agent loop; a test that scripts the
            # coach's words scripts them there too.
            stack.enter_context(
                patch(
                    "btcopilot.turns.model_for",
                    new=lambda *a, **k: Model(said(response)),
                )
            )
            title = marker.kwargs.get("title", "A session title")
            stack.enter_context(
                patch(
                    "btcopilot.metered.gemini_text_sync",
                    return_value=Text(title, Spent(), Served(EXTRACTION_MODEL)),
                )
            )
            ret = {
                "response": response,
                "title": title,
            }
        else:
            stack.enter_context(
                patch(
                    "btcopilot.metered.gemini_text_sync",
                    return_value=Text("A session title", Spent(), Served(EXTRACTION_MODEL)),
                )
            )
            ret = None
        yield ret


@pytest.fixture
def web(flask_app, test_user):
    """Browser client for the chat app: a logged-in session cookie, the
    way the page itself is served."""
    test_user.roles = btcopilot.ROLE_SUBSCRIBER
    db.session.merge(test_user)
    db.session.commit()
    flask_app.test_client_class = flask.testing.FlaskClient
    with flask_app.test_client(use_cookies=True) as client:
        client.user = test_user
        with client.session_transaction() as sess:
            sess["user_id"] = test_user.id
            sess["logged_in_at"] = datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        yield client


@pytest.fixture
def logged(monkeypatch):
    """The app's loggers on, whichever tests ran first: alembic's fileConfig,
    run by any test that migrates, turns off every logger it does not name."""
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith("btcopilot") and isinstance(logger, logging.Logger):
            monkeypatch.setattr(logger, "disabled", False)


def csrf_token(web) -> str:
    response = web.get("/app/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)


@pytest.fixture
def discussions(test_user):
    items = [
        Discussion(user_id=test_user.id, summary=f"test thread {i}") for i in range(3)
    ]
    db.session.add_all(items)
    db.session.commit()
    return items


@pytest.fixture
def discussion(test_user):
    discussion = Discussion(
        user_id=test_user.id,
        diagram_id=test_user.free_diagram_id,
        summary="Test discussion",
    )
    db.session.add(discussion)
    db.session.commit()

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
    db.session.add_all([family_speaker, expert_speaker])
    db.session.commit()

    # Create statements
    statement1 = Statement(
        discussion_id=discussion.id, speaker_id=family_speaker.id, text="Hello", order=0
    )
    statement2 = Statement(
        discussion_id=discussion.id,
        speaker_id=expert_speaker.id,
        text="Hi there",
        order=1,
    )
    db.session.add_all([statement1, statement2])
    db.session.commit()

    return discussion


_connect = socket.socket.connect


@pytest.fixture(autouse=True)
def hermetic(request, monkeypatch):
    if any(
        request.node.get_closest_marker(m)
        for m in ("integration", "e2e", "live", "conventions")
    ):
        yield
        return

    def connect(self, address):
        if self.family == socket.AF_UNIX:
            return _connect(self, address)
        raise ConnectionRefusedError(f"unit tests may not open sockets: {address}")

    monkeypatch.setattr(socket.socket, "connect", connect)
    yield
