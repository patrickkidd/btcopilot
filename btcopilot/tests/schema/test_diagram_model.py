"""Tests for Diagram model business logic (schema-level tests, not endpoint tests)."""

import os
import pickle
import subprocess
import sys
from pathlib import Path

from btcopilot import diagramjson
from btcopilot.pro.models import Diagram
from btcopilot.schema import DiagramData, asdict
from btcopilot.extensions import db


def test_update_with_version_check_atomicity(test_user):
    """Test that update_with_version_check atomically updates both data and version."""
    diagram = test_user.free_diagram
    initial_version = diagram.version
    new_data = pickle.dumps({"test": "atomic"})

    success, new_version = diagram.update_with_version_check(
        expected_version=initial_version, new_data=new_data
    )
    assert success is True
    assert new_version == initial_version + 1

    db.session.flush()
    db.session.refresh(diagram)
    assert diagram.version == initial_version + 1
    assert diagramjson.loads(diagram.data)["test"] == "atomic"


def test_update_with_version_check_conflict(test_user):
    """Test that update_with_version_check rejects when version mismatches."""
    diagram = test_user.free_diagram
    initial_version = diagram.version
    new_data = pickle.dumps({"test": "conflict"})

    success, new_version = diagram.update_with_version_check(
        expected_version=initial_version + 999, new_data=new_data
    )
    assert success is False
    assert new_version is None
    assert diagram.version == initial_version


def test_update_with_version_check_using_diagram_data(test_user):
    """Test that update_with_version_check works with DiagramData objects."""
    diagram = test_user.free_diagram
    initial_version = diagram.version

    diagram_data = diagram.get_diagram_data()
    diagram_data.lastItemId = 456

    success, new_version = diagram.update_with_version_check(
        expected_version=initial_version, diagram_data=diagram_data
    )
    assert success is True
    assert new_version == initial_version + 1

    db.session.flush()
    db.session.refresh(diagram)
    assert diagram.version == initial_version + 1
    assert diagram.get_diagram_data().lastItemId == 456


def test_pickle_row_stays_pickle_byte_for_byte(test_user):
    """A row the Pro app already owns is stored exactly as the app sent it."""
    diagram = test_user.free_diagram
    assert not diagramjson.is_json(diagram.data)
    blob = pickle.dumps({"people": [{"id": 1, "name": "Ada"}]})

    diagram.update_with_version_check(diagram.version, new_data=blob)
    db.session.flush()
    db.session.refresh(diagram)
    assert diagram.data == blob
    assert diagram.pickled == blob


def test_json_row_stays_json_and_reads_back_as_pickle(test_user):
    """A row the chat app made keeps its form, and the Pro app still gets pickle."""
    diagram = Diagram(user_id=test_user.id, name="Chat", data=diagramjson.dumps({}))
    db.session.add(diagram)
    db.session.flush()
    blob = pickle.dumps({"people": [{"id": 1, "name": "Ada"}]})

    diagram.update_with_version_check(diagram.version, new_data=blob)
    db.session.flush()
    db.session.refresh(diagram)
    assert diagramjson.is_json(diagram.data)
    assert pickle.loads(diagram.pickled) == {"people": [{"id": 1, "name": "Ada"}]}


def test_model_imports_without_the_qt_gui_module():
    """The server must start where PyQt5.QtGui's system libraries are absent."""
    root = Path(__file__).parents[3]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['PyQt5.QtGui'] = None; "
            "import btcopilot.pro.routes, btcopilot.pro.models.diagram",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
