"""Render SCREENS.md — what every screen of the app does — into one HTML page for the beta
users. Statuses become pills and the ruling ids hide behind one toggle at the top.

  python bin/screenspage.py <out.html>
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"

STYLE = """:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--ask:#a8720f;--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--data:#3fc4bc;--ask:#e0a83f}}:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--data:#3fc4bc;--ask:#e0a83f}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);margin:0;padding:28px 20px 60px;max-width:84ch}
h1{font:600 22px var(--sans);margin:0 0 4px}.lead{color:var(--faint);margin:0 0 10px}
code{font:12.5px var(--mono);color:var(--data)}
.counts{font:500 13px var(--mono);color:var(--faint);margin:0 0 14px}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 24px;font-size:14px}nav a{color:var(--data);text-decoration:none}
h2{font:600 17px var(--sans);margin:28px 0 2px;padding-top:8px;border-top:1px solid var(--line)}
.for{color:var(--faint);font-size:14px;margin:0 0 10px}
ul{margin:0;padding:0 0 0 20px}li{margin:0 0 7px}
.pill{display:inline-block;font:500 11.5px var(--mono);border-radius:9px;padding:0 7px;margin-left:6px;white-space:nowrap;vertical-align:1px}
.built{border:1px solid var(--data);color:var(--data)}.drawn{border:1px solid var(--ask);color:var(--ask)}
.open{border:1px solid var(--ask);background:var(--ask);color:var(--panel)}
small.src{display:none;font:500 11.5px var(--mono);color:var(--faint);margin-left:6px}
#sources:checked~* small.src{display:inline}
#sources{vertical-align:-1px;margin:0 6px 18px 0}
label.toggle{font-size:13px;color:var(--faint)}"""

TAG = re.compile(r"\[(built|drawn|open)\]\s*(\{[^}]*\})?\s*$")


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def main(out: str) -> int:
    text = (DOC / "SCREENS.md").read_text()
    head, _, rest = text.partition("\n## ")
    lead = [ln.strip() for ln in head.splitlines() if ln.strip() and not ln.startswith("#")]
    lead = [ln for ln in lead if ln != "---"]
    updated = next((ln for ln in lead if ln.startswith("Updated")), "")
    blurb = " ".join(ln for ln in lead if not ln.startswith("Updated"))

    sections, counts = [], {"built": 0, "drawn": 0, "open": 0}
    for block in rest.split("\n## ") if rest else []:
        name, _, body = block.partition("\n")
        name = name.strip()
        purpose, items = "", []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("What it is for:"):
                purpose = line[len("What it is for:") :].strip()
            elif line.startswith("- "):
                items.append(line[2:].strip())
        rows = []
        for item in items:
            m = TAG.search(item)
            status = m.group(1) if m else "built"
            ids = (m.group(2) or "").strip("{} ") if m else ""
            counts[status] += 1
            sentence = TAG.sub("", item).strip()
            src = f'<small class="src">{html.escape(ids)}</small>' if ids else ""
            rows.append(
                f'<li>{inline(sentence)}<span class="pill {status}">{status}</span>{src}</li>'
            )
        sections.append((name, purpose, rows))

    slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
    parts = [
        "<title>Family Diagram Screens</title>",
        f"<style>{STYLE}</style>",
        "<h1>Family Diagram — what every screen does</h1>",
        f'<p class="lead">{inline(blurb)}</p>',
        f'<p class="counts">{counts["built"]} built · {counts["drawn"]} drawn · '
        f'{counts["open"]} open · {html.escape(updated)}</p>',
        '<input type="checkbox" id="sources">'
        '<label class="toggle" for="sources">show sources</label>',
        "<nav>"
        + "".join(f'<a href="#{slug(n)}">{html.escape(n)}</a>' for n, _, _ in sections)
        + "</nav>",
    ]
    for name, purpose, rows in sections:
        parts.append(f'<h2 id="{slug(name)}">{html.escape(name)}</h2>')
        if purpose:
            parts.append(f'<p class="for">{inline(purpose)}</p>')
        parts.append("<ul>" + "".join(rows) + "</ul>")
    Path(out).write_text("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
