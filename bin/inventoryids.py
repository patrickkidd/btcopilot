"""Writes the ids of the cluster prompt's inventory to a plain file, so the
prompt's citation guard runs without the private corpus (R-0858).

  python bin/inventoryids.py [INVENTORY.md]          rewrites the ids file
  python bin/inventoryids.py [INVENTORY.md] --check  exits 1 when the file is stale

The inventory is `research/clusters/INVENTORY.md` in btcopilot-sources; with no
path given it is read under BTCOPILOT_SOURCES. Section 1 holds one table row per
source, its id in the first cell: passages P-nnn, statements S-nnn, rulings
R-nnnn, the derivation's rules DR-nn, btcopilot's docs DOC-nn and commit
messages GIT-n. Section 2 cites all six as the sources of prompt lines, so all
six go in the file. A first cell shaped like an id but of none of these shapes,
or an id given twice, stops the script: the ids are assigned once and kept.
"""

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IDS_FILE = REPO / "btcopilot" / "tests" / "live" / "clusters" / "inventory-ids.txt"
INVENTORY = Path("research/clusters/INVENTORY.md")
SOURCES = "BTCOPILOT_SOURCES"

SHAPES = re.compile(r"P-\d{3}|S-\d{3}|R-\d{4}|DR-\d{2}|DOC-\d{2}|GIT-\d+")
FIRST_CELL = re.compile(r"^\|\s*([A-Z]+-\d+)\s*\|")
SECTION_ONE = re.compile(r"^## 1\.")
NEXT_SECTION = re.compile(r"^## ")


def _order(source_id: str) -> tuple[str, int]:
    prefix, _, number = source_id.partition("-")
    return prefix, int(number)


def ids(text: str) -> list[str]:
    """Every id in section 1 of the inventory, sorted by prefix then number."""
    found: list[str] = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        if SECTION_ONE.match(line):
            inside = True
            continue
        if inside and NEXT_SECTION.match(line):
            break
        cell = FIRST_CELL.match(line) if inside else None
        if not cell:
            continue
        source_id = cell.group(1)
        if not SHAPES.fullmatch(source_id):
            raise ValueError(f"line {number}: {source_id} is not an inventory id shape")
        if source_id in found:
            raise ValueError(f"line {number}: {source_id} is given twice")
        found.append(source_id)
    if not found:
        raise ValueError("no ids found under '## 1.' in the inventory")
    return sorted(found, key=_order)


def listing(text: str) -> str:
    return "".join(f"{source_id}\n" for source_id in ids(text))


def inventory_path(args: list[str]) -> Path:
    if args:
        return Path(args[0])
    sources = os.environ.get(SOURCES)
    if not sources:
        sys.exit(f"name the inventory, or set {SOURCES} to the btcopilot-sources clone")
    return Path(sources) / INVENTORY


def main(argv: list[str]) -> int:
    check = "--check" in argv
    path = inventory_path([a for a in argv if a != "--check"])
    text = listing(path.read_text())
    if check:
        stale = not IDS_FILE.exists() or IDS_FILE.read_text() != text
        print(f"{IDS_FILE} {'is stale' if stale else 'matches'} {path}")
        return 1 if stale else 0
    IDS_FILE.write_text(text)
    print(f"{text.count(chr(10))} ids from {path} in {IDS_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
