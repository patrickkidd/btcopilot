import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
CITE = re.compile(r"^\s*(#|//)\s*(R-0\d{3}(,\s*R-0\d{3})*|no ruling)\s*$")
TS_TEST = re.compile(r"^\s*(it|test)\(|^\s*(it|test)\.(only|skip|fixme|fail)\(\s*[\"'`]")


def _python():
    for path in sorted((ROOT / "btcopilot" / "tests").rglob("test_*.py")):
        lines = path.read_text().splitlines()
        for node in ast.walk(ast.parse("\n".join(lines))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                head = lines[node.lineno - 1 : node.body[0].lineno - 1]
                if not any(CITE.match(line) for line in head):
                    yield f"{path.relative_to(ROOT)}::{node.name}"


def _typescript():
    for tree in ("web/test", "web/tests/visual"):
        for path in sorted((ROOT / tree).glob("*.ts")):
            lines = path.read_text().splitlines()
            for i, line in enumerate(lines):
                if TS_TEST.match(line) and not (i and CITE.match(lines[i - 1])):
                    yield f"{path.relative_to(ROOT)}:{i + 1}"


def test_every_test_cites_a_ruling():
    # R-0421
    uncited = [*_python(), *_typescript()]
    assert uncited == [], "cite the ruling each test proves, or mark it no ruling"
