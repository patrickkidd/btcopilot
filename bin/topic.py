"""Audit the flushed state by topic, in plain words.

  python bin/topic.py                 every topic: name, status, how many open questions
  python bin/topic.py pro training    one topic matched by words: its block, then every
                                      HISTORY entry tagged with it (the event clock, oldest
                                      first), then the rulings its block cites
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
RULINGS = HERE.parent.parent.parent.parent / "fdserver" / ".claude" / "worktrees" / "FD-362" / "doc" / "oracle" / "rulings.md"


def blocks() -> list[tuple[str, str, str]]:
    text = (DOC / "TOPICS.md").read_text()
    out = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        tid, _, name = head.partition(" · ")
        out.append((tid.strip(), name.strip(), body))
    return out


def field(body: str, name: str) -> str:
    m = re.search(rf"\*\*{re.escape(name)}:\*\*\s*(.*?)(?=\n\*\*|\Z)", body, re.S)
    return m.group(1).strip() if m else ""


def main(words: list[str]) -> int:
    all_blocks = blocks()
    if not words:
        for tid, name, body in all_blocks:
            open_q = len(re.findall(r"\(\d+\)", field(body, "Open")))
            print(f"- {name} — {field(body, 'Status').splitlines()[0]} — {open_q} open")
        return 0
    key = [w.lower() for w in words]
    scored = sorted(
        all_blocks,
        key=lambda b: -sum(w in (b[1] + b[2]).lower() for w in key),
    )
    tid, name, body = scored[0]
    if sum(w in (name + body).lower() for w in key) == 0:
        print("no topic matches those words; run with no words to see the names")
        return 1
    print(f"# {name}\n{body.strip()}\n")
    history = (DOC / "HISTORY.md").read_text()
    print(f"# Event clock for '{name}', oldest first")
    for entry in re.split(r"^## ", history, flags=re.M)[1:]:
        head = entry.splitlines()[0]
        if re.search(rf"\[[^\]]*\b{tid}\b[^\]]*\]", head):
            print(f"\n## {entry.strip()}")
    ids = sorted(set(re.findall(r"R-\d{4}", body)))
    if ids and RULINGS.exists():
        rows = RULINGS.read_text().splitlines()
        print(f"\n# Rulings the block cites")
        for rid in ids:
            for row in rows:
                if row.startswith(rid + " |"):
                    print(row.split(" | ")[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
