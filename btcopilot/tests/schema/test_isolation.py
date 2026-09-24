"""Verify btcopilot.schema has no transitive imports of private btcopilot modules.

btcopilot.schema is the ONLY public submodule — it must work in the desktop
app builds where Flask, btcopilot.extensions, etc. are not
available.
"""

import importlib
import sys
import unittest.mock

import pytest

PRIVATE_MODULES = [
    "btcopilot.extensions",
    "btcopilot.personal",
    "btcopilot.app",
    "btcopilot.auth",
    "btcopilot.llmutil",
    "btcopilot.celery",
    "btcopilot.modelmixin",
    "flask",
]


def test_schema_import_isolation():
    # R-0051
    blocked = {mod: None for mod in PRIVATE_MODULES}
    with unittest.mock.patch.dict(sys.modules, blocked):
        if "btcopilot.schema" in sys.modules:
            del sys.modules["btcopilot.schema"]
        schema = importlib.import_module("btcopilot.schema")
    assert hasattr(schema, "DiagramData")
    assert hasattr(schema, "PDP")
    assert hasattr(schema, "get_all_pdp_item_ids")


