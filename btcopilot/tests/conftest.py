import sys
import logging
import contextlib

import pytest

import mock
from flask import current_app

from btcopilot.extensions import db
from btcopilot import create_app, Engine, Response


@pytest.fixture(autouse=True)
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
