"""Render SCREENS.md as a picture catalogue: every screen as it actually renders, one caption
under each picture, and the list of behaviours folded away beneath it.

  python bin/screenspage.py <out.html>

The images are referenced as screens/<file>.png, so the page must be opened from a directory
that holds a screens/ folder — doc/chat-first/ or a copy of it.
"""
import html
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DOC = HERE / "doc" / "chat-first"

STYLE = """:root{--bg:#f7f6f2;--panel:#fff;--ink:#26312f;--faint:#67746f;--line:#d8d5cc;--data:#0e7d78;--ask:#a8720f;--sans:"Libre Franklin",-apple-system,system-ui,sans-serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--data:#3fc4bc;--ask:#e0a83f}}:root[data-theme="dark"]{--bg:#171d1c;--panel:#1f2725;--ink:#e6e8e4;--faint:#9aa5a0;--line:#39443f;--data:#3fc4bc;--ask:#e0a83f}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);margin:0;padding-block:28px 60px;padding-left:20px;padding-right:20px;max-width:1000px}
h1{font:600 22px var(--sans);margin:0 0 4px}.lead{color:var(--faint);margin:0 0 10px;max-width:84ch}
code{font:12.5px var(--mono);color:var(--data)}
.counts{font:500 13px var(--mono);color:var(--faint);margin:0 0 14px}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 24px;font-size:14px}nav a{color:var(--data);text-decoration:none}
h2{font:600 17px var(--sans);margin:34px 0 2px;padding-top:10px;border-top:1px solid var(--line)}
.for{color:var(--faint);font-size:14px;margin:0 0 14px;max-width:84ch}
.shots{display:flex;flex-wrap:wrap;gap:18px;margin:0 0 14px;align-items:flex-start}
figure{margin:0;max-width:100%}
figure img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:4px;background:var(--panel)}
figcaption{font-size:13px;line-height:1.45;color:var(--faint);margin-top:6px}
.none{font-size:14px;color:var(--faint);margin:0 0 14px}
details{border-top:1px solid var(--line);padding-top:8px}
summary{cursor:pointer;font:500 13.5px var(--sans);color:var(--data);list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ ";}details[open] summary::before{content:"▾ ";}
ul{margin:10px 0 0;padding:0 0 0 20px}li{margin:0 0 7px}
.pill{display:inline-block;font:500 11.5px var(--mono);border-radius:9px;padding:0 7px;margin-left:6px;white-space:nowrap;vertical-align:1px}
.built{border:1px solid var(--data);color:var(--data)}.drawn{border:1px solid var(--ask);color:var(--ask)}
.open{border:1px solid var(--ask);background:var(--ask);color:var(--panel)}
small.src{display:none;font:500 11.5px var(--mono);color:var(--faint);margin-left:6px}
#sources:checked~* small.src{display:inline}
#sources{vertical-align:-1px;margin:0 6px 18px 0}
label.toggle{font-size:13px;color:var(--faint)}"""

TAG = re.compile(r"\[(built|drawn|open)\]\s*(\{[^}]*\})?\s*$")
PIC = re.compile(r"^!\[(.*)\]\((.+?)\)$")
PHONE_CSS_WIDTH = 393
DESK_MAX_WIDTH = 840


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", s)


def css_width(rel: str) -> int:
    """The width to show a screenshot at: phone renders stay at phone size, wider renders are
    capped at the desktop width. Read from the PNG header, which is written at scale 2."""
    data = (DOC / rel).read_bytes()[16:24]
    native = struct.unpack(">I", data[:4])[0]
    return min(max(native // 2, PHONE_CSS_WIDTH), DESK_MAX_WIDTH)


def parse():
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
        purpose, items, pics = "", [], []
        for line in body.splitlines():
            line = line.strip()
            pic = PIC.match(line)
            if pic:
                pics.append((pic.group(2), pic.group(1)))
            elif line.startswith("What it is for:"):
                purpose = line[len("What it is for:") :].strip()
            elif line.startswith("- "):
                items.append(line[2:].strip())
        rows = []
        for item in items:
            m = TAG.search(item)
            status = m.group(1) if m else "built"
            ids = (m.group(2) or "").strip("{} ") if m else ""
            counts[status] += 1
            src = f'<small class="src">{html.escape(ids)}</small>' if ids else ""
            rows.append(
                f'<li>{inline(TAG.sub("", item).strip())}'
                f'<span class="pill {status}">{status}</span>{src}</li>'
            )
        sections.append((name, purpose, pics, rows))
    return blurb, updated, counts, sections


def main(out: str) -> int:
    blurb, updated, counts, sections = parse()
    slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
    parts = [
        "<title>Family Diagram Screens</title>",
        f"<style>{STYLE}</style>",
        "<h1>Family Diagram — every screen, as it looks</h1>",
        '<p class="lead">Each screen below is its real rendering, not a description of one. '
        f"{inline(blurb)}</p>",
        f'<p class="counts">{counts["built"]} built · {counts["drawn"]} drawn · '
        f'{counts["open"]} open · {html.escape(updated)}</p>',
        '<input type="checkbox" id="sources">'
        '<label class="toggle" for="sources">show sources</label>',
        "<nav>"
        + "".join(f'<a href="#{slug(n)}">{html.escape(n)}</a>' for n, _, _, _ in sections)
        + "</nav>",
    ]
    for name, purpose, pics, rows in sections:
        parts.append(f'<h2 id="{slug(name)}">{html.escape(name)}</h2>')
        if purpose:
            parts.append(f'<p class="for">{inline(purpose)}</p>')
        if pics:
            shots = "".join(
                f'<figure style="width:{css_width(src)}px">'
                f'<img src="{html.escape(src)}" alt="{html.escape(cap)}" loading="lazy">'
                f"<figcaption>{html.escape(cap)}</figcaption></figure>"
                for src, cap in pics
            )
            parts.append(f'<div class="shots">{shots}</div>')
        else:
            parts.append('<p class="none">No rendering yet.</p>')
        parts.append(
            f'<details><summary>what it does · {len(rows)} behaviours</summary>'
            f'<ul>{"".join(rows)}</ul></details>'
        )
    Path(out).write_text("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
