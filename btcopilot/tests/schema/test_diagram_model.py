"""Tests for Diagram model business logic (schema-level tests, not endpoint tests)."""

import os
import subprocess
import sys
from pathlib import Path

from btcopilot.extensions import db


def test_update_with_version_check_using_diagram_data(test_user):
    # R-0084
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


def test_model_imports_without_the_qt_gui_module():
    # R-0051
    """The server must start where PyQt5.QtGui's system libraries are absent."""
    root = Path(__file__).parents[3]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.modules['PyQt5.QtGui'] = None; "
            "import btcopilot.app, btcopilot.personal.routes, btcopilot.models.diagram",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
