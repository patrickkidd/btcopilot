"""Verify btcopilot.schema has no transitive imports of private btcopilot modules.

btcopilot.schema is the ONLY public submodule — it must work in the pro and
personal app builds where Flask, btcopilot.pdp, btcopilot.extensions, etc. are
not available.
"""

import importlib
import sys
import unittest.mock

import pytest

PRIVATE_MODULES = [
    "btcopilot.pdp",
    "btcopilot.extensions",
    "btcopilot.personal",
    "btcopilot.pro",
    "btcopilot.training",
    "btcopilot.app",
    "btcopilot.auth",
    "btcopilot.llmutil",
    "btcopilot.celery",
    "btcopilot.modelmixin",
    "flask",
]


def test_schema_import_isolation():
    blocked = {mod: None for mod in PRIVATE_MODULES}
    with unittest.mock.patch.dict(sys.modules, blocked):
        if "btcopilot.schema" in sys.modules:
            del sys.modules["btcopilot.schema"]
        schema = importlib.import_module("btcopilot.schema")
    assert hasattr(schema, "DiagramData")
    assert hasattr(schema, "PDP")
    assert hasattr(schema, "get_all_pdp_item_ids")


def test_commit_pdp_items_no_private_imports():
    """commit_pdp_items must not import private btcopilot modules at call time."""
    from btcopilot.schema import (
        DiagramData,
        PDP,
        Person,
        Event,
        EventKind,
        get_all_pdp_item_ids,
    )

    pdp = PDP(
        people=[Person(id=-1, name="Alice")],
        events=[Event(id=-2, kind=EventKind.Shift, person=-1)],
    )
    dd = DiagramData(pdp=pdp)

    blocked = {mod: None for mod in PRIVATE_MODULES}
    with unittest.mock.patch.dict(sys.modules, blocked):
        dd.commit_pdp_items([-1, -2])

    assert len(dd.people) == 1
    person = dd.people[0]
    pid = person["id"] if isinstance(person, dict) else person.id
    assert pid > 0
