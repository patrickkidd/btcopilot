"""Tests for Diagram model business logic (schema-level tests, not endpoint tests)."""

import pickle
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
    assert pickle.loads(diagram.data)["test"] == "atomic"


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
