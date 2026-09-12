"""Render the topic register, its tagged history and the rulings it cites into one HTML page
for the owner's audit artifact. The flush runs it, then republishes the page to the URL
recorded at the top of TOPICS.md.

  python bin/topicpage.py <out.html>
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"
RULINGS = HERE.parent.parent.parent.parent / "fdserver" / ".claude" / "worktrees" / "FD-362" / "doc" / "oracle" / "rulings.md"

STYLE = """:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f}}:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);margin:0;padding:28px 20px 60px;max-width:84ch}h1{font:600 22px var(--sans);margin:0 0 4px}.lead{color:var(--faint);margin:0 0 18px}
nav{display:flex;flex-wrap:wrap;gap:8px 16px;margin:0 0 26px;font-size:14px}nav a{color:var(--data);text-decoration:none}
details{border:1px solid var(--line);border-radius:12px;background:var(--panel);margin:0 0 12px}summary{cursor:pointer;padding:12px 16px;font:600 15px var(--sans);list-style:none}summary::-webkit-details-marker{display:none}
summary small{display:block;font:400 13px var(--sans);color:var(--faint);margin-top:2px}.body{padding:0 16px 14px;font-size:14px}.body p{margin:0 0 8px}
h4{font:600 12px var(--sans);color:var(--faint);letter-spacing:.04em;text-transform:uppercase;margin:14px 0 6px}.ev{border-left:2px solid var(--line);padding:4px 12px;margin:0 0 10px;font-size:13.5px}.ev b{display:block;font-weight:500;margin-bottom:2px}
.rul{font-size:13px;margin:0 0 6px}code{font:12.5px var(--mono);color:var(--data)}a{color:var(--data)}"""


def md(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", s)
    return s.replace("\n\n", "</p><p>").replace("\n", " ")


def main(out: str) -> int:
    topics = (DOC / "TOPICS.md").read_text()
    history = (DOC / "HISTORY.md").read_text()
    rules = {}
    if RULINGS.exists():
        for row in RULINGS.read_text().splitlines():
            if re.match(r"^R-\d{4} \|", row):
                rules[row.split(" | ")[0]] = row.split(" | ")[1]
    entries = re.split(r"^## ", history, flags=re.M)[1:]
    blocks = []
    for block in re.split(r"^## ", topics, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        tid, _, name = head.partition(" · ")
        blocks.append((tid.strip(), name.strip(), body))
    parts = [
        "<title>FD-362 Open Topics</title>",
        f"<style>{STYLE}</style>",
        "<h1>FD-362 — open topics</h1>",
        '<p class="lead">Every topic of the chat-first rebuild since its first session: what is '
        "decided, what is open, where it lives, and its full history. Rewritten by the flush at "
        "the end of every session.</p>",
        "<nav>" + "".join(f'<a href="#{t}">{html.escape(n)}</a>' for t, n, _ in blocks) + "</nav>",
    ]
    for tid, name, body in blocks:
        m = re.search(r"\*\*Status:\*\*\s*(.*?)(?=\n\*\*|\Z)", body, re.S)
        status = m.group(1).strip().replace("\n", " ") if m else ""
        parts.append(
            f'<details id="{tid}" open><summary>{html.escape(name)}<small>{html.escape(status)}'
            f'</small></summary><div class="body"><p>{md(body.strip())}</p>'
        )
        evs = [e for e in entries if re.search(rf"\[[^\]]*\b{tid}\b[^\]]*\]", e.splitlines()[0])]
        parts.append(f"<h4>History · {len(evs)} entries, oldest first</h4>")
        for e in evs:
            h, _, txt = e.partition("\n")
            txt = re.sub(r"<!--.*?-->", "", txt).strip()
            h = re.sub(r"\s*\[T-[^\]]*\]", "", h)
            parts.append(f'<div class="ev"><b>{html.escape(h)}</b>{md(txt)}</div>')
        ids = sorted(set(re.findall(r"R-\d{4}", body)))
        if ids:
            parts.append("<h4>Rulings this topic rests on</h4>")
            parts += [
                f'<p class="rul"><code>{i}</code> {html.escape(rules.get(i, "(not in store)"))}</p>'
                for i in ids
            ]
        parts.append("</div></details>")
    Path(out).write_text("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
