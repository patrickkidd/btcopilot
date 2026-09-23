"""The review reaches the chat app through one module."""

import ast
from pathlib import Path

from btcopilot.tests.repo import PACKAGE as SOURCE

PACKAGE = SOURCE / "review"
DOOR = "adapter.py"
FORBIDDEN = ("btcopilot.personal",)


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_only_the_adapter_reaches_the_app():
    # no ruling
    leaks = {
        str(path.relative_to(PACKAGE)): [
            name
            for name in imported_modules(path)
            if name.startswith(FORBIDDEN)
        ]
        for path in PACKAGE.rglob("*.py")
        if path.name != DOOR
    }
    assert {where: names for where, names in leaks.items() if names} == {}


def test_the_adapter_is_where_it_is_reached():
    # no ruling
    assert [
        name
        for name in imported_modules(PACKAGE / DOOR)
        if name.startswith(FORBIDDEN)
    ]
