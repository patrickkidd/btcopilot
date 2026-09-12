"""Mine the owner's own statements out of the local Claude Code transcripts into
doc/chat-first/trace.json — one row per thing he typed, in the order he typed it.

Nothing the assistant, a tool, a sub-agent or the harness produced is ever written.
Names and summaries written here are deterministic placeholders (named_by "script");
a flush session rewrites this session's rows by judgement and sets named_by "session",
and those rows are never recomputed.

  python bin/trace.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import TOPIC_WORDS  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
OUT = DOC / "trace.json"
PROJECTS = Path.home() / ".claude" / "projects"
DIRS = [
    "-Users-patrick-theapp-btcopilot--claude-worktrees-FD-362",
    "-Users-patrick-theapp-btcopilot--claude-worktrees-chat-first-app",
    "-Users-patrick-theapp",
    "-Users-patrick-theapp-2",
]
SINCE = "2026-08-25"
SUBJECTS = ("fd-362", "fd-360", "chat-first", "personal app", "coach")
MIN_CHARS = 12
OPENERS = (
    "i think", "i guess", "i mean", "ok", "okay", "yes", "yeah", "yep", "no", "and",
    "also", "so", "honestly", "again", "but", "well", "now", "just", "actually",
    "please", "hey", "right", "sure",
)
INJECTED = (
    "<task-notification>",
    "<command-name>",
    "<local-command-stdout>",
    "<local-command-stderr>",
    "[Request interrupted",
    "Another Claude session sent a message:",
    "Caveat: The messages below",
    "<teammate-message",
    "<user-prompt-submit-hook>",
    "API Error",
)


def clean(text: str) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    return text.strip()


def typed(entry: dict) -> str:
    if entry.get("type") != "user":
        return ""
    if entry.get("isSidechain") or entry.get("isMeta") or entry.get("isCompactSummary"):
        return ""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        blocks = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        if not blocks:
            return ""
        text = "\n".join(blocks)
    else:
        return ""
    text = clean(text)
    if len(text) < MIN_CHARS or text.startswith(INJECTED):
        return ""
    return text


def thread_of(text: str) -> str:
    low = text.lower()
    for topic, words in TOPIC_WORDS.items():
        if any(w in low for w in words):
            return topic
    return "unplaced"


def opening(text: str) -> str:
    """His phrase, minus the words he opens with; the phrase itself stays verbatim."""
    while True:
        low = text.lower()
        for word in OPENERS:
            if low.startswith(word) and (len(low) == len(word) or not low[len(word)].isalnum()):
                text = text[len(word):].lstrip(" ,.:;-—")
                break
        else:
            return text


def name_of(text: str) -> str:
    body = opening(" ".join(text.split()))
    head = re.split(r"(?<=[,.;:!?])(?:\s|$)", body)[0].strip()
    words = head.split()
    if len(words) < 4:
        words = body.split()
    return " ".join(words[:7]).rstrip(" ,;:-") or "(no words)"


def summary_of(text: str) -> str:
    one = " ".join(text.split())
    first = re.split(r"(?<=[.?!])\s", one)[0]
    if len(first) <= 110:
        return first
    return first[:109].rsplit(" ", 1)[0] + "…"


def relevant(path: Path) -> bool:
    with path.open("rb") as fh:
        blob = fh.read().lower()
    return any(s.encode() in blob for s in SUBJECTS)


def session_rows(path: Path) -> tuple[str, str, list[dict]]:
    sid, title, rows = path.stem, "", []
    for line in path.open():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("type") == "ai-title":
            title = entry.get("aiTitle") or title
            continue
        text = typed(entry)
        if not text:
            continue
        rows.append({"time": entry.get("timestamp", ""), "text": text, "uuid": entry.get("uuid", "")})
    if not rows or rows[0]["time"][:10] < SINCE:
        return sid, title, []
    return sid, title, rows


def statements() -> list[dict]:
    out = []
    for name in DIRS:
        folder = PROJECTS / name
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.jsonl")):
            if not relevant(path):
                continue
            sid, title, rows = session_rows(path)
            for i, row in enumerate(rows):
                text = row["text"]
                if i and text == rows[i - 1]["text"]:
                    continue
                out.append(
                    {
                        "id": f"{sid[:8]}#{i}",
                        "time": row["time"],
                        "session": sid[:8],
                        "session_title": title,
                        "thread": thread_of(text),
                        "name": name_of(text),
                        "summary": summary_of(text),
                        "text": text,
                        "named_by": "script",
                        "uuid": row["uuid"],
                    }
                )
    out.sort(key=lambda s: (s["time"], s["id"]))
    return out


def merge(fresh: list[dict]) -> list[dict]:
    if not OUT.exists():
        return fresh
    held = {s["id"]: s for s in json.loads(OUT.read_text()) if s.get("named_by") == "session"}
    for row in fresh:
        old = held.get(row["id"])
        if old:
            row.update({k: old[k] for k in ("name", "summary", "thread", "named_by") if k in old})
    return fresh


def main() -> int:
    rows = merge(statements())
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    by_session, by_thread = {}, {}
    for row in rows:
        key = f"{row['session']} {row['time'][:10]} {row['session_title'][:44]}"
        by_session[key] = by_session.get(key, 0) + 1
        by_thread[row["thread"]] = by_thread.get(row["thread"], 0) + 1
    print(f"{OUT}: {len(rows)} statements from {len(by_session)} sessions")
    for key, n in sorted(by_session.items()):
        print(f"  {n:4d}  {key}")
    for thread, n in sorted(by_thread.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {thread}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
