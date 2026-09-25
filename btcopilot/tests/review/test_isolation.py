"""The review reaches the chat app through one module."""

import ast
from pathlib import Path

from btcopilot.tests.repo import PACKAGE as SOURCE

PACKAGE = SOURCE / "review"
DOOR = "adapter.py"
APP = (
    "chat chips clusters coacheval coachmodel coachturn discussions "
    "interactions lanes licence playturn pricing productevents profile promptdir "
    "prompts record recordtext refs routes seed timeline toolbox tracing "
    "transcription turnlog turns views"
).split()
APP_MODELS = (
    "change discussion interaction modelcall productevent speaker statement "
    "syntheticpersona tokenmeter"
).split()
FORBIDDEN = tuple(
    [f"btcopilot.{name}" for name in APP]
    + [f"btcopilot.models.{name}" for name in APP_MODELS]
)


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
            names += [f"{node.module}.{alias.name.lower()}" for alias in node.names]
    return names


def test_only_the_adapter_reaches_the_app():
    # R-0233
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
    # R-0245
    assert [
        name
        for name in imported_modules(PACKAGE / DOOR)
        if name.startswith(FORBIDDEN)
    ]
