"""The guards of the human-oracle test system (private/oracle SPEC, section 7).

Every guard reads the store through btcopilot.oracle, so on a machine without a
sops key every guard fails rather than passing on nothing.
"""

import ast
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import pytest

from btcopilot import oracle
from btcopilot.oracle import ROOT, Kind, Status, Tag
from btcopilot.promptdir import encrypted

pytestmark = pytest.mark.conventions

HERE = Path(__file__).parent
FINGERPRINTS = HERE / "fingerprints.txt"
EXCEPTIONS = HERE / "exceptions.txt"
WEB = ROOT / "web"
CEILING = 150_000
SHINGLE = 12
LEAST = 8
ORACLE = re.compile(r"\[Oracle:?([^\]]*)\]")
IDS = re.compile(r"R-\d{4}(, R-\d{4})*")
LINE = re.compile(r"^\s*(#|//)\s*(R-\d{4}(,\s*R-\d{4})*)\s*$")
WORD = re.compile(r"[a-z0-9]+")
EXCUSES = {Status.TestOwed, Status.Waived}
# The one carve-out from the index-row shape: an exception line, and only in exceptions.txt.
EXCEPTION = re.compile(r"R-\d{4} \| (TEST OWED|WAIVED) \| [^|]+")


def cites(text: str | None) -> tuple[set[str], list[str]]:
    if text is None:
        return set(), ["its source line was not found"]
    ids, bad = set(), []
    for m in ORACLE.finditer(text):
        inner = m.group(1).strip()
        if IDS.fullmatch(inner) and m.group(0).startswith("[Oracle: "):
            ids.update(oracle.ID.findall(inner))
        else:
            bad.append(m.group(0))
    for line in text.splitlines():
        if m := LINE.match(line):
            ids.update(oracle.ID.findall(m.group(2)))
    return ids, bad


def above(lines: list[str], start: int) -> str:
    """The comment block ending on the line before `start` (1-based)."""
    i = start - 1
    while i > 0 and lines[i - 1].strip().startswith(("#", "//", "/*", "*")):
        i -= 1
    return "\n".join(lines[i : start - 1])


def pyzone(lines: list[str], node) -> str:
    start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    body = node.body
    first = body[1] if len(body) > 1 and ast.get_docstring(node) else body[0]
    head = lines[node.lineno - 1 : first.lineno - 1]
    return "\n".join([above(lines, start), ast.get_docstring(node) or "", *head])


@cache
def pymodule(path: Path) -> tuple[list[str], ast.Module]:
    text = path.read_text()
    return text.splitlines(), ast.parse(text)


def pytests() -> list[tuple[str, str]]:
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "--color=no",
         "-p", "no:cacheprovider", f"--rootdir={ROOT}", "btcopilot/tests"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    out = []
    for nodeid in sorted({l.split("[")[0] for l in done.stdout.splitlines() if "::" in l}):
        path, *names = nodeid.split("::")
        lines, tree = pymodule(ROOT / path)
        first = tree.body[0].lineno if tree.body else len(lines) + 1
        zones = [ast.get_docstring(tree) or "", "\n".join(lines[: first - 1])]
        scope = tree
        for name in names:
            scope = next(
                n for n in scope.body
                if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
            )
            zones.append(pyzone(lines, scope))
        out.append((nodeid, "\n".join(zones)))
    return out


def tszone(path: Path, line: int) -> str:
    lines = path.read_text().splitlines()
    first = next(
        (i for i, l in enumerate(lines) if re.match(r"\s*(test|it|describe)\b", l)), len(lines)
    )
    header = "\n".join(l for l in lines[:first] if l.strip().startswith(("//", "/*", "*")))
    return header + "\n" + above(lines, line)


def npx(*args: str) -> str:
    return subprocess.run(
        ["npx", *args], cwd=WEB, capture_output=True, text=True, check=True
    ).stdout


def call(verbs: str, name: str) -> re.Pattern:
    return re.compile(rf"\b({verbs})(\.\w+)*\(\s*[\"'`]" + re.escape(name) + r"[\"'`]")


def locate(lines: list[str], names: list[str]) -> int | None:
    """The line of a vitest test: its literal name, or for a test named at run
    time, the first call with a computed name inside its describe."""
    hit = [i for i, l in enumerate(lines) if call("it|test", names[-1]).search(l)]
    if hit:
        return hit[0] + 1
    if len(names) < 2:
        return None
    opens = [i for i, l in enumerate(lines) if call("describe", names[-2]).search(l)]
    computed = re.compile(r"\b(it|test)(\.\w+)*\(\s*[^\s\"'`]")
    return next((i + 1 for i in range(opens[0], len(lines)) if computed.search(lines[i])), None) if opens else None


def vitests() -> list[tuple[str, str]]:
    out = []
    for t in json.loads(npx("vitest", "list", "--json")):
        path = Path(t["file"])
        line = locate(path.read_text().splitlines(), t["name"].split(" > "))
        label = f"{path.relative_to(ROOT)}::{t['name']}"
        out.append((label, tszone(path, line) if line else None))
    return out


def playwrights() -> list[tuple[str, str]]:
    report = json.loads(npx("playwright", "test", "--list", "--reporter=json"))
    root = Path(report["config"]["rootDir"])
    found = set()

    def walk(suite):
        for spec in suite.get("specs", []):
            found.add((root / spec["file"], spec["line"]))
        for child in suite.get("suites", []):
            walk(child)

    for suite in report["suites"]:
        walk(suite)
    return [(f"{p.relative_to(ROOT)}:{line}", tszone(p, line)) for p, line in sorted(found)]


@cache
def collected() -> dict[str, tuple[set[str], list[str]]]:
    return {label: cites(zone) for label, zone in [*pytests(), *vitests(), *playwrights()]}


def test_the_store_parses_into_closed_vocabularies():
    # R-0447, R-0331
    found = oracle.rulings()
    assert found
    assert [r.id for r in found.values() if r.evidence_count < 0] == []


def test_no_ruling_id_is_deleted_or_repointed():
    # R-0447, R-0331
    pinned = oracle.pinned(FINGERPRINTS.read_text())
    now = oracle.fingerprints()
    found = oracle.rulings()
    moved = sorted(rid for rid, ds in pinned.items() if rid not in found or not set(ds) <= now.get(rid, set()))
    assert moved == [], "these ids were deleted or lost a quote they were pinned to"
    current = FINGERPRINTS.read_text().splitlines()
    unpinned = [l for l in oracle.pin(FINGERPRINTS.read_text()).splitlines() if l not in current]
    assert unpinned == [], "put these lines in fingerprints.txt, replacing the id's line (bin/fingerprints.py does it with a key)"


def test_every_test_cites_a_live_ruling():
    # R-0447, R-0331, R-0421
    found = oracle.rulings()
    wrong = {}
    for label, (ids, bad) in collected().items():
        unknown = sorted(i for i in ids if i not in found)
        retired = sorted(i for i in ids if i in found and found[i].status is Status.Superseded)
        problems = bad + [f"unknown {i}" for i in unknown] + [f"superseded {i}" for i in retired]
        if problems or not ids:
            wrong[label] = problems or ["no citation"]
    assert wrong == {}


def exceptions() -> dict[str, tuple[Status, str]]:
    out = {}
    for line in EXCEPTIONS.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rid, stat, reason = [c.strip() for c in line.split(" | ")]
        assert rid not in out, f"{rid} is excepted twice"
        out[rid] = (Status(stat), reason)
    return out


def test_every_ruling_is_tested_or_excepted():
    # R-0447, R-0331
    found = oracle.rulings()
    excused = exceptions()
    assert sorted(set(excused) - set(found)) == []
    assert [rid for rid, (s, reason) in excused.items() if s not in EXCUSES or not reason] == []
    citing = Counter(i for ids, _ in collected().values() for i in ids)
    short = {}
    for r in found.values():
        if Tag.Process in r.tags or r.status is not Status.Ok or r.id in excused:
            continue
        owed = len(r.tags) if r.kind is Kind.Rule else 1
        if citing[r.id] < owed:
            short[r.id] = f"{citing[r.id]} of {owed}"
    assert short == {}, "write the citing tests, or record TEST OWED / WAIVED in exceptions.txt"


def test_the_index_stays_small_enough_to_read_whole():
    # R-0447, R-0331
    text = oracle.index()
    size = defaultdict(int)
    for row in text.splitlines():
        if oracle.ROW.match(row):
            for name, col in zip(oracle.FIELDS, row.split(" | ")):
                size[name] += len(col.encode())
        else:
            size["preamble"] += len(row.encode())
    total = len(text.encode())
    assert total <= CEILING, f"{total} bytes; largest fields: {sorted(size.items(), key=lambda kv: -kv[1])[:3]}"


def shingles(text: str) -> set[tuple[str, ...]]:
    words = WORD.findall(text.lower())
    n = min(SHINGLE, len(words))
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)} if words else set()


def tracked() -> list[Path]:
    done = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / p for p in done.stdout.split("\0") if p]


def test_no_tracked_file_carries_oracle_outside_the_store():
    # R-0447, R-0331
    marks = {}
    for r in oracle.rulings().values():
        quotes = [q for q in oracle.quotes().get(r.id, []) if len(q.split()) >= LEAST]
        for text in [r.statement, *quotes]:
            marks.update(dict.fromkeys(shingles(text), r.id))
    sizes = {len(m) for m in marks}
    leaks = {}
    for path in tracked():
        raw = path.read_bytes() if path.is_file() else b""
        if b"\0" in raw[:8192]:
            continue
        text = raw.decode(errors="replace")
        if encrypted(text):
            continue
        forgiven = EXCEPTION if path == EXCEPTIONS else None
        found = {
            f"line {n + 1}: index row"
            for n, l in enumerate(text.splitlines())
            if oracle.ROW.match(l) and not (forgiven and forgiven.fullmatch(l))
        }
        words = list(WORD.finditer(text.lower()))
        tokens = [w.group() for w in words]
        for n in sizes:
            for i in range(len(tokens) - n + 1):
                rid = marks.get(tuple(tokens[i : i + n]))
                if rid:
                    found.add(f"line {text.count(chr(10), 0, words[i].start()) + 1}: {rid}")
        if found:
            leaks[str(path.relative_to(ROOT))] = sorted(found)
    assert leaks == {}
