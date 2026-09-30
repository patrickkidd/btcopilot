"""Counts from the repository, the private corpus, every checkout's eval
ledger and the efficiency skill, keyed by the ledger's loop names. Reads only.

    python3 files.py <since YYYY-MM-DD>
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EFFICIENCY = Path.home() / ".claude" / "skills" / "efficiency"
DATED = re.compile(r"(20\d\d-\d\d-\d\d)")


def clone():
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return Path(common).parent


def ledgers(root, since):
    rows = [
        json.loads(line)
        for path in root.glob("**/btcopilot/tests/live/results/ledger.jsonl")
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    recent = [r for r in rows if r["at"][:10] >= since]
    paid = [r for r in recent if r.get("source") != "subscription" and r.get("cost")]
    return {
        "lines_since": len(recent),
        "paid_lines_since": len(paid),
        "api_dollars_since": round(sum(r["cost"] for r in paid), 4),
        "last_paid": max((r["at"][:10] for r in paid), default=None),
    }


def prompts(since):
    heads = re.findall(
        r"^## (.+) \((20\d\d-\d\d-\d\d)\)$",
        (REPO / "doc" / "PROMPT_ENGINEERING_LOG.md").read_text(),
        re.M,
    )
    return [{"date": d, "title": t} for t, d in heads if d >= since]


def main(since):
    root = clone()
    corpus = (
        Path(os.environ.get("BTCOPILOT_SOURCES", root / "btcopilot-sources"))
        / "fd-corpus"
        / "private"
    )
    queue = sorted(corpus.glob("RULINGS_TO_APPEND_*.md"))[-1]
    waiting = sorted(set(re.findall(r"\*\*(R-\d{4})\*\*", queue.read_text())))
    marks = [
        x.split(" | ")[1]
        for x in (REPO / "btcopilot/tests/conventions/exceptions.txt")
        .read_text()
        .splitlines()
        if " | " in x and not x.startswith("#")
    ]
    cases = sorted(corpus.glob("correction-cases/*.md"))
    evals = sorted(
        p
        for p in (REPO / "quality" / "evals").glob("*.json")
        if p.name != "goldens.json"
    )
    corrections = DATED.findall(
        (EFFICIENCY / "references" / "corrections.md").read_text()
    )
    print(
        json.dumps(
            {
                "Your rulings and the check that every test cites one": {
                    "queue_file_date": DATED.search(queue.name).group(1),
                    "rulings_waiting": len(waiting),
                    "first": waiting[0] if waiting else None,
                    "last": waiting[-1] if waiting else None,
                    "test_owed": marks.count("TEST OWED"),
                    "waived": marks.count("WAIVED"),
                },
                "Corrections by the person to the coach's record": {
                    "correction_cases": len(cases),
                    "newest": DATED.search(cases[-1].name).group(1) if cases else None,
                },
                "Evals gating a prompt change": {
                    "prompt_changes_since": prompts(since),
                    "saved_replays": len(
                        list((REPO / "private" / "replays").iterdir())
                    ),
                    "live_cases": sum(
                        p.read_text().count("\ndef test_")
                        for p in (REPO / "btcopilot/tests/live").glob("test_*.py")
                    ),
                },
                "Recorded runs on the quality dashboard": {
                    "recorded_runs": len(evals),
                    "newest": DATED.search(evals[-1].name).group(1) if evals else None,
                },
                "Test spend": ledgers(root, since),
                "The efficiency skill": {
                    "rules": len(
                        re.findall(
                            r"^\d+\. ",
                            (EFFICIENCY / "ACCEPTANCE_CRITERIA.md").read_text(),
                            re.M,
                        )
                    ),
                    "dated_corrections_since": sum(
                        1 for d in corrections if d >= since
                    ),
                    "newest_correction": max(corrections, default=None),
                },
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main(sys.argv[1])
