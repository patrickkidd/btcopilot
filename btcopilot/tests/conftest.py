import sys
import logging
import contextlib

import pytest

import mock

from btcopilot.extensions import db
from btcopilot import create_app, Engine, Response

IS_DEBUGGER = bool(sys.gettrace() is not None)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Tun integration tests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test.")


def pytest_collection_modifyitems(session, config, items):

    # Skip mark "integration" by default, run only "integration" marks when "--integration" is passed
    if not IS_DEBUGGER:
        if not config.getoption("--integration"):
            skip_mark = pytest.mark.skip(reason="Requires passing --integration to run")
            for item in items:
                if "integration" in [x.name for x in item.own_markers]:
                    item.add_marker(skip_mark)
        else:
            skip_mark = pytest.mark.skip(
                reason="Skipped because --integration was passed"
            )
            for item in items:
                if "integration" not in [x.name for x in item.own_markers]:
                    item.add_marker(skip_mark)


@pytest.fixture(autouse=True, scope="session")
def _logging():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


@pytest.fixture
def flask_app(tmp_path):

    kwargs = {
        "CONFIG": "testing",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    }

    app = create_app(kwargs, instance_path=tmp_path)

    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def client(flask_app):
    with flask_app.test_client() as _client:
        yield _client


@pytest.fixture
def llm_response():

    @contextlib.contextmanager
    def _llm_response(response: str, sources: list[dict] = None):
        if sources is None:
            sources = [
                {
                    "sources": "source_file_1.pdf",
                    "passage": "Some source passage 1",
                },
                {
                    "sources": "source_file_2.pdf",
                    "passage": "Some source passage 2",
                },
            ]
        with mock.patch.object(Engine, "ask", return_value=Response(response, sources)):
            yield

    return _llm_response
