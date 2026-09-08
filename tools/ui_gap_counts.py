#!/usr/bin/env python3
"""Count row statuses in doc/chat-first/UI_GAP.md and print the summary tables.

A row's status is the last table cell, optionally suffixed `STATUS @commit`
or `STATUS — note` etc. Only the leading token before whitespace or '@' is
the status. Run: python3 tools/ui_gap_counts.py [path-to-UI_GAP.md]
"""
import re
import sys
from collections import defaultdict

STATUSES = ["MET", "PARTIAL", "CHANGED", "MISSING", "NEEDS-OWNER", "UNCHECKED", "N/A"]

def status_of(cell):
    cell = cell.strip()
    m = re.match(r"([A-Z][A-Z/\- ]*[A-Z/])", cell)
    token = m.group(1).strip() if m else cell
    for s in STATUSES:
        if token == s or token.startswith(s):
            return s
    raise ValueError(f"Unrecognized status cell: {cell!r}")

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "doc/chat-first/UI_GAP.md"
    group = None
    in_row_table = False
    totals = defaultdict(int)
    by_group = defaultdict(lambda: defaultdict(int))
    with open(path) as f:
        for line in f:
            gm = re.match(r"^##\s+(.*)$", line)
            if gm:
                group = gm.group(1).strip()
                in_row_table = False
                continue
            if not line.startswith("|"):
                in_row_table = False
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells[:1] == ["element"]:
                in_row_table = True
                continue
            if line.startswith("|---") or not in_row_table:
                continue
            if len(cells) < 4:
                continue
            status = status_of(cells[-1])
            totals[status] += 1
            if group:
                by_group[group][status] += 1

    total_rows = sum(totals.values())
    print("| status | rows |")
    print("|---|---|")
    for s in STATUSES:
        print(f"| {s} | {totals[s]} |")
    print(f"| **total** | **{total_rows}** |")
    print()
    print("| group | " + " | ".join(STATUSES) + " |")
    print("|---|" + "---|" * len(STATUSES))
    for g, counts in by_group.items():
        print(f"| {g} | " + " | ".join(str(counts[s]) for s in STATUSES) + " |")

if __name__ == "__main__":
    main()
