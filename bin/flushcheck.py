"""The flush check: every topic block carries its fields, every open item is tagged with
what it is waiting on, every HISTORY tag names a topic, and the newest HISTORY entry is
dated today. Run from the btcopilot worktree."""
import datetime
import re
import sys
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "doc" / "chat-first"
FIELDS = ("Status", "Decided", "Open", "Lives in", "Next action", "Updated")
TAGS = ("ruling", "build", "verify", "waiting")


def open_items(block: str) -> list[str]:
    m = re.search(r"^\*\*Open:\*\*\s*(.*?)(?=\n\*\*|\Z)", block, re.M | re.S)
    field = " ".join(m.group(1).split()) if m else ""
    if not field or field.rstrip(".").lower() == "none":
        return []
    parts = re.split(r"\(\d+\)\s*", field)
    return [p.strip() for p in parts[1:] if p.strip()] or [field]


def main() -> int:
    topics = (DOC / "TOPICS.md").read_text()
    history = (DOC / "HISTORY.md").read_text()
    errors = []
    ids = set()
    for block in re.split(r"^## ", topics, flags=re.M)[1:]:
        head = block.splitlines()[0]
        m = re.match(r"(T-\d+)\s+·\s+(.+)", head)
        if not m:
            errors.append(f"topic heading without an id: {head!r}")
            continue
        ids.add(m.group(1))
        # a topic that is closed or parked may legitimately have nothing decided or open
        for field in FIELDS:
            if not re.search(rf"^\*\*{re.escape(field)}:\*\*", block, re.M) and not (
                field in ("Decided", "Open") and "CLOSED" in block
            ):
                errors.append(f"{m.group(1)} lacks the field {field}")
        for item in open_items(block):
            if not re.match(rf"\[({'|'.join(TAGS)})\]\s+\S", item):
                errors.append(
                    f"{m.group(1)} has an open item without a "
                    f"[{']/['.join(TAGS)}] tag: {item[:60]!r}"
                )
    names = re.findall(r"^## T-\d+\s+·\s+(.+)$", topics, re.M)
    for name in {n for n in names if names.count(n) > 1}:
        errors.append(f"two topic blocks share the name {name!r}")
    markers = re.findall(r"<!-- session: (\S+) -->", history)
    for marker in {m for m in markers if markers.count(m) > 1}:
        errors.append(f"HISTORY has two entries for session {marker}")
    for tag in re.findall(r"\[(T-\d+(?:,\s*T-\d+)*)\]", history):
        for one in re.split(r",\s*", tag):
            if one not in ids:
                errors.append(f"HISTORY tags unknown topic {one}")
    today = datetime.date.today()
    newest = history.rstrip().split("\n## ")[-1].splitlines()[0]
    # a heading may span days ("2026-09-10 and 11"); the day of the month is enough
    if today.isoformat() not in newest and not re.search(
        rf"{today.year}-{today.month:02d}-\d\d(?: and \d\d)*\b.*\b{today.day:02d}\b", newest
    ):
        errors.append(f"newest HISTORY entry is not dated today ({today.isoformat()})")
    for e in errors:
        print("flushcheck:", e)
    print("flushcheck: ok" if not errors else f"flushcheck: {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
