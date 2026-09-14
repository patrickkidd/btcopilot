"""The event ledger: every dated item the corpus holds, one record each, from the
sources that already exist — history entries, rulings, decision-log entries, review-log
rows, commits in both worktrees, artifacts. Written to doc/chat-first/events.json by
the flush; nothing is authored here, only gathered and tagged.

  python bin/ledger.py            writes events.json and prints the counts
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
FD = HERE.parent.parent.parent.parent / "fdserver" / ".claude" / "worktrees" / "FD-362"
YEAR = "2026"

# Topic keywords: the same words the topic blocks use. A record that matches none stays
# untagged and shows as its own lane, so nothing is hidden by a bad guess.
TOPIC_WORDS = {
    "T-1": ["beta", "deploy", "merge", "sign-in", "signin", "login", "passkey", "invite", "home screen", "https", "release", "sandbox", "migration", "pickle", "isolation options", "must fix", "production", "stored blob", "json record", "change log", "schema comparison", "cascade", "one send at a time"],
    "T-2": ["coach", "prompt", "extraction", "extract", "tool", "who·what", "who from the links", "harness", "f1", "definition", "sarf", "agent loop", "refus", "shift", "variable", "loop engineering", "optimistic lock", "agent:", "/personal/", "markdown links", "personal api", "interaction store", "unknown provenance"],
    "T-3": ["pro app", "pro's", "pro save", "pro user", "pro loop", "pro drawer", "pro routes", "pro code", "pro reads", "pro chat", "pro users", "pro migration", "pro session", "pro statements", "pro-embed", "in-pro", "training", "coding", "coder", "irr study", "irr review", "irr compares", "one app", "layer", "case properties", "professional case", "documenting a case", "family switcher", "adds cases", "upload", "recording", "compare", "gold record", "protocol", "sessions need", "sessions accumulate", "session summaries", "session list", "settings-nested", "preferences hold", "stacked-cards"],
    "T-4": ["wipe", "re-code", "recode", "existing rows", "old rows", "transcript", "migrat"],
    "T-5": ["picture", "board", "cluster view", "chip", "title", "drawer", "editor", "slide", "button", "badge", "hamburger", "spotlight", "dot", "wire", "drawab", "move language", "ui", "shell", "navigation", "sessions sheet", "account", "avatar", "play-by-play", "play-through", "symbols", "timing", "legend", "arrow", "moment", "fixture", "golden", "vocabulary", "speaks", "voice is fine", "newest words", "drag-to-scroll", "selectable", "selected and copied", "warning", "caret", "offers to go again", "about page", "gallery", "scroll bar", "the app is called", "events and people lists", "diagram row", "one open at a time", "birth and death", "never ruled and is removed"],
    "T-6": ["cluster", "corpus", "case_", "clinic", "notability", "function-subset", "by example", "floor", "phase a", "bake-off", "mechanical grouping", "anonymization"],
    "T-7": ["arrange", "drawn family", "genogram"],
    "T-8": ["package boundary", "isolation option", "adapter", "lint", "auth module"],
    "T-9": ["process", "auditor", "sub-agent", "subagent", "flush", "corpus regime", "oracle", "ruling", "no coined", "estimate", "token", "eyeball", "worktree", "jira", "pivot", "two-clocks", "review log", "open items", "non-happy-path", "session discipline", "one epic", "keeps them in line", "handoff", "architecture session", "the owner's words", "mvp done condition", "early hook"],
}


def topics_for(text: str, tags: str = "") -> list[str]:
    hay = (text + " " + tags).lower()
    found = [t for t, words in TOPIC_WORDS.items() if any(w in hay for w in words)]
    return found or ["untagged"]


def date_of(stamp: str) -> str:
    m = re.search(r"(\d{2})-(\d{2})", stamp)
    return f"{YEAR}-{m.group(1)}-{m.group(2)}" if m else ""


def history() -> list[dict]:
    out = []
    text = (DOC / "HISTORY.md").read_text()
    for entry in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = entry.partition("\n")
        tags = re.findall(r"\[(T-[^\]]*)\]", head)
        topics = re.split(r",\s*", tags[0]) if tags else ["untagged"]
        m = re.search(r"(\d{4}-\d{2}-\d{2})", head)
        session = re.search(r"<!-- session: (\S+) -->", body)
        out.append({
            "id": f"H:{head[:60]}",
            "kind": "history",
            "date": m.group(1) if m else "",
            "session": session.group(1) if session else "",
            "topics": topics,
            "title": re.sub(r"\s*\[T-[^\]]*\]", "", head).strip(),
            "text": re.sub(r"<!--.*?-->", "", body).strip()[:1200],
            "source": "doc/chat-first/HISTORY.md",
        })
    return out


def rulings() -> list[dict]:
    out = []
    path = FD / "doc" / "oracle" / "rulings.md"
    if not path.exists():
        return out
    for row in path.read_text().splitlines():
        if not re.match(r"^R-\d{4} \|", row):
            continue
        cols = [c.strip() for c in row.split(" | ")]
        rid, text = cols[0], cols[1]
        kind = cols[2] if len(cols) > 2 else ""
        tags = cols[3] if len(cols) > 3 else ""
        status = cols[4] if len(cols) > 4 else ""
        stamp = cols[-1]
        succ = re.findall(r"superseded by (R-\d{4})|supersedes (R-\d{4})", text, re.I)
        out.append({
            "id": rid,
            "kind": "ruling" if kind != "defect" else "defect",
            "status": status,
            "date": date_of(stamp),
            "session": stamp,
            "topics": topics_for(text, tags),
            "title": text[:110],
            "text": text,
            "supersedes": [s for pair in succ for s in pair if s],
            "source": "fdserver doc/oracle/rulings.md",
        })
    return out


def decisions() -> list[dict]:
    out = []
    text = (HERE / "decisions" / "log.md").read_text()
    for entry in re.split(r"^##+ ", text, flags=re.M)[1:]:
        head, _, body = entry.partition("\n")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", head)
        if not m or m.group(1) < "2026-08-25":
            continue
        out.append({
            "id": f"D:{head[:60]}",
            "kind": "decision",
            "date": m.group(1),
            "session": "",
            "topics": topics_for(head + " " + body[:400]),
            "title": head,
            "text": body.strip()[:800],
            "source": "decisions/log.md",
        })
    return out


def review_rows() -> list[dict]:
    out = []
    text = (DOC / "REVIEW_LOG.md").read_text()
    for m in re.finditer(r"^(\d+)\.\s+(.*?)(?=^\d+\.\s|\n## |\Z)", text, re.M | re.S):
        body = " ".join(m.group(2).split())
        fixed = re.search(r"FIXED @([0-9a-f]{7})", body)
        out.append({
            "id": f"review-{m.group(1)}",
            "kind": "review",
            "date": "2026-09-08" if int(m.group(1)) < 63 else "2026-09-09",
            "session": "",
            "topics": topics_for(body),
            "title": body[:110],
            "text": body[:600],
            "commit": fixed.group(1) if fixed else "",
            "source": "doc/chat-first/REVIEW_LOG.md",
        })
    return out


def commits(repo: Path, label: str) -> list[dict]:
    out = []
    log = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%ad|%h|%s", "--date=short", "--since=2026-08-25", "FD-362"],
        capture_output=True, text=True,
    ).stdout
    for line in log.splitlines():
        date, sha, subject = line.split("|", 2)
        out.append({
            "id": f"{label}@{sha}",
            "kind": "build",
            "date": date,
            "session": "",
            "topics": topics_for(subject),
            "title": subject[:110],
            "text": subject,
            "source": f"{label} git log",
        })
    return out


def artifacts() -> list[dict]:
    out, seen = [], set()
    for path in list(DOC.glob("*.md")) + [HERE / "decisions" / "log.md"]:
        text = path.read_text()
        for m in re.finditer(r"(https://claude\.ai/code/artifact/[0-9a-f-]+)", text):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            around = text[max(0, m.start() - 160): m.start()]
            title = re.sub(r"\s+", " ", around).strip()[-120:]
            out.append({
                "id": url.rsplit("/", 1)[1][:8],
                "kind": "artifact",
                "date": "",
                "session": "",
                "topics": topics_for(around),
                "title": title,
                "text": url,
                "link": url,
                "source": str(path.relative_to(HERE)),
            })
    return out


def main() -> int:
    events = history() + rulings() + decisions() + review_rows() + commits(HERE, "btcopilot") + commits(FD, "fdserver") + artifacts()
    # an undated artifact takes the date of the first history entry that cites it
    hist = history()
    for e in events:
        if e["kind"] == "artifact" and not e["date"]:
            for h in hist:
                if e["link"] in h["text"]:
                    e["date"] = h["date"]
                    break
    events.sort(key=lambda e: (e["date"] or "9999", e["kind"]))
    (DOC / "events.json").write_text(json.dumps(events, indent=0, ensure_ascii=False))
    counts = {}
    for e in events:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    untagged = sum(1 for e in events if e["topics"] == ["untagged"])
    print(json.dumps({"total": len(events), **counts, "untagged": untagged}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
